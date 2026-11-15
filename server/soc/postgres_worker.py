"""PostgreSQL-native persistent worker for the LUMS SOC event inbox.

This worker is intentionally separate from the SQLite worker. It requires
the centrally migrated PostgreSQL SOC schema and never creates or migrates
database objects itself.
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from psycopg import Connection, Error
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from ..db_transactions import transaction
from ..migration_runner import migration_checksum
from ..migrations.soc_storage import SOC_STORAGE_MIGRATION
from .collector_store import CollectorStoreError
from .incident_builder import IncidentBuilder
from .incidents import Incident
from .ingestion import EventIngestor
from .pipeline import SOCPipeline
from .postgres_collector_store import PostgresCollectorStore
from .postgres_incident_store import PostgresIncidentStore
from .rule_catalog import LoadedRuleCatalog
from .worker import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_STALE_SECONDS,
    ClaimOwnershipLost,
    SOCWorkerError,
    WorkerResult,
    _payload_for_engine,
    _utc_datetime,
)


_DEFAULT_RULES_PATH = Path(__file__).with_name("rules.json")

_REQUIRED_TABLE_COLUMNS = {
    "schema_migrations": {
        "version",
        "applied_at",
        "checksum",
        "description",
    },
    "soc_collector_agents": {
        "agent_id",
        "display_name",
        "certificate_sha256",
        "status",
        "created_at",
        "revoked_at",
    },
    "soc_event_inbox": {
        "inbox_id",
        "agent_id",
        "event_id",
        "payload_json",
        "payload_sha256",
        "received_at",
        "processing_status",
        "processed_at",
        "last_error",
        "claim_token",
        "claimed_at",
        "attempts",
    },
    "soc_incidents": {
        "incident_id",
        "title",
        "summary",
        "severity",
        "status",
        "created_at",
        "updated_at",
    },
    "soc_incident_evidence": {
        "evidence_sequence",
        "evidence_id",
        "incident_id",
        "kind",
        "reference_id",
        "description",
        "observed_at",
    },
    "soc_incident_history": {
        "history_id",
        "incident_id",
        "old_status",
        "new_status",
        "changed_at",
        "changed_by",
    },
}

_REQUIRED_CONSTRAINTS = {
    "ck_soc_event_inbox_status",
    "ck_soc_event_inbox_attempts",
    "ck_soc_event_inbox_claim_state",
    "uq_soc_event_inbox_agent_event",
    "fk_soc_event_inbox_agent",
    "pk_soc_incident_evidence",
    "uq_soc_incident_evidence_sequence",
    "fk_soc_incident_evidence_incident",
    "fk_soc_incident_history_incident",
}

_RECOVERY_INDEX = "idx_soc_event_inbox_claim_recovery"
_RECOVERY_INDEX_COLUMNS = "(processing_status,claimed_at,inbox_id)"


def validate_postgres_worker_schema(connection: Connection) -> None:
    """Validate the PostgreSQL worker schema without changing the database.

    This is a read-only preflight. The SQLite-only migration
    ``001-soc-worker-claims`` is deliberately not required here because
    PostgreSQL migration ``009-soc-storage`` already creates claim metadata.
    """
    if not isinstance(connection, Connection):
        raise TypeError("connection must be a psycopg.Connection")

    if connection.closed:
        raise SOCWorkerError("PostgreSQL worker connection is closed")

    if connection.autocommit is not True:
        raise SOCWorkerError(
            "PostgreSQL worker requires an autocommit connection"
        )

    if connection.info.transaction_status != TransactionStatus.IDLE:
        raise SOCWorkerError(
            "PostgreSQL worker schema validation requires an idle connection"
        )

    try:
        rows = connection.execute(
            """
            SELECT
                rel.relname AS table_name,
                att.attname AS column_name
            FROM pg_catalog.pg_class AS rel
            JOIN pg_catalog.pg_namespace AS ns
              ON ns.oid = rel.relnamespace
            JOIN pg_catalog.pg_attribute AS att
              ON att.attrelid = rel.oid
            WHERE ns.nspname = current_schema()
              AND rel.relkind IN ('r', 'p')
              AND att.attnum > 0
              AND NOT att.attisdropped
            """
        ).fetchall()

        actual: dict[str, set[str]] = {}
        for row in rows:
            actual.setdefault(row["table_name"], set()).add(
                row["column_name"]
            )

        missing_tables: list[str] = []
        missing_columns: list[str] = []

        for table, required in _REQUIRED_TABLE_COLUMNS.items():
            columns = actual.get(table)

            if columns is None:
                missing_tables.append(table)
                continue

            missing = required - columns
            if missing:
                missing_columns.append(
                    f"{table}: {', '.join(sorted(missing))}"
                )

        if missing_tables or missing_columns:
            details = []
            if missing_tables:
                details.append(
                    "missing tables: " + ", ".join(sorted(missing_tables))
                )
            if missing_columns:
                details.append(
                    "missing columns: " + "; ".join(missing_columns)
                )

            raise SOCWorkerError(
                "PostgreSQL SOC worker schema is incomplete; "
                + " | ".join(details)
            )

        typed_columns = connection.execute(
            """
            SELECT
                rel.relname AS table_name,
                att.attname AS column_name,
                pg_catalog.format_type(
                    att.atttypid,
                    att.atttypmod
                ) AS data_type,
                CASE
                    WHEN att.attnotnull THEN 'NO'
                    ELSE 'YES'
                END AS is_nullable,
                CASE
                    WHEN att.attidentity <> '' THEN 'YES'
                    ELSE 'NO'
                END AS is_identity
            FROM pg_catalog.pg_class AS rel
            JOIN pg_catalog.pg_namespace AS ns
              ON ns.oid = rel.relnamespace
            JOIN pg_catalog.pg_attribute AS att
              ON att.attrelid = rel.oid
            WHERE ns.nspname = current_schema()
              AND rel.relkind IN ('r', 'p')
              AND att.attnum > 0
              AND NOT att.attisdropped
              AND (
                  (rel.relname = 'soc_event_inbox'
                   AND att.attname IN (
                       'inbox_id', 'attempts', 'claimed_at'
                   ))
                  OR
                  (rel.relname = 'soc_incident_evidence'
                   AND att.attname = 'evidence_sequence')
                  OR
                  (rel.relname = 'soc_incident_history'
                   AND att.attname = 'history_id')
              )
            """
        ).fetchall()

        types = {
            (row["table_name"], row["column_name"]): row
            for row in typed_columns
        }

        expected_types = {
            ("soc_event_inbox", "inbox_id"): (
                "bigint", "NO", "YES"
            ),
            ("soc_event_inbox", "attempts"): (
                "integer", "NO", "NO"
            ),
            ("soc_event_inbox", "claimed_at"): (
                "timestamp with time zone", "YES", "NO"
            ),
            ("soc_incident_evidence", "evidence_sequence"): (
                "bigint", "NO", "YES"
            ),
            ("soc_incident_history", "history_id"): (
                "bigint", "NO", "YES"
            ),
        }

        for key, expected in expected_types.items():
            row = types.get(key)
            if row is None:
                raise SOCWorkerError(
                    f"PostgreSQL SOC worker column {key[0]}.{key[1]} "
                    "is missing"
                )

            actual_definition = (
                row["data_type"],
                row["is_nullable"],
                row["is_identity"],
            )

            if actual_definition != expected:
                raise SOCWorkerError(
                    f"PostgreSQL SOC worker column {key[0]}.{key[1]} "
                    "has an unexpected definition"
                )

        constraints = {
            row["conname"]
            for row in connection.execute(
                """
                SELECT conname
                FROM pg_constraint
                WHERE connamespace = current_schema()::regnamespace
                """
            ).fetchall()
        }

        missing_constraints = _REQUIRED_CONSTRAINTS - constraints
        if missing_constraints:
            raise SOCWorkerError(
                "PostgreSQL SOC worker constraints are missing: "
                + ", ".join(sorted(missing_constraints))
            )

        index_row = connection.execute(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND indexname = %s
              AND tablename = 'soc_event_inbox'
            """,
            (_RECOVERY_INDEX,),
        ).fetchone()

        if index_row is None:
            raise SOCWorkerError(
                f"Required PostgreSQL worker recovery index {_RECOVERY_INDEX} is missing"
            )

        normalized_index = "".join(
            index_row["indexdef"].replace('"', "").lower().split()
        )

        if _RECOVERY_INDEX_COLUMNS not in normalized_index:
            raise SOCWorkerError(
                f"PostgreSQL worker index {_RECOVERY_INDEX} "
                "has an unexpected definition"
            )

        migration = connection.execute(
            """
            SELECT checksum, description
            FROM schema_migrations
            WHERE version = %s
            """,
            (SOC_STORAGE_MIGRATION.version,),
        ).fetchone()

        if migration is None:
            raise SOCWorkerError(
                "Required PostgreSQL migration "
                f"{SOC_STORAGE_MIGRATION.version} is not recorded"
            )

        if (
            migration["checksum"] != SOC_STORAGE_MIGRATION.checksum
            or migration["description"] != SOC_STORAGE_MIGRATION.description
        ):
            raise SOCWorkerError(
                "PostgreSQL SOC storage migration checksum or description "
                "does not match the registered migration"
            )

    except SOCWorkerError:
        raise
    except Error as exc:
        raise SOCWorkerError(
            "Unable to validate PostgreSQL SOC worker schema"
        ) from exc


class PostgresSOCWorker:
    """Claim and process SOC events using PostgreSQL-native transactions."""

    @staticmethod
    def _validate_limit(
        name: str,
        value: object,
        low: int,
        high: int,
    ) -> None:
        """Validate an integer limit without accepting bool as an integer."""
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not low <= value <= high
        ):
            raise ValueError(f"{name} must be between {low} and {high}")

    def _ensure_idle_connection(self) -> None:
        """Reject closed, non-autocommit, or caller-transaction connections."""
        if self.connection.closed:
            raise SOCWorkerError("PostgreSQL worker connection is closed")

        if self.connection.autocommit is not True:
            raise SOCWorkerError(
                "PostgreSQL worker requires an autocommit connection"
            )

        if (
            self.connection.info.transaction_status
            != TransactionStatus.IDLE
        ):
            raise SOCWorkerError(
                "Worker cannot run inside an existing transaction"
            )

    def __init__(
        self,
        connection: Connection,
        catalog: LoadedRuleCatalog,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        stale_after_seconds: int = DEFAULT_STALE_SECONDS,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> None:
        validate_postgres_worker_schema(connection)

        for name, value, low, high in (
            ("batch_size", batch_size, 1, 500),
            ("max_attempts", max_attempts, 1, 100),
            ("stale_after_seconds", stale_after_seconds, 1, 86400),
            ("history_limit", history_limit, 1, 50000),
        ):
            self._validate_limit(name, value, low, high)

        if not isinstance(catalog, LoadedRuleCatalog):
            raise TypeError("catalog must be a LoadedRuleCatalog")

        if connection.row_factory is not dict_row:
            raise TypeError(
                "PostgreSQL SOC worker requires psycopg dict_row results"
            )

        self.connection = connection
        self.collectors = PostgresCollectorStore(connection)
        self.incidents = PostgresIncidentStore(connection)
        self.pipeline = SOCPipeline(
            ingestor=EventIngestor(
                max_batch_events=history_limit + 1
            )
        )
        self.builder = IncidentBuilder()
        self.catalog = catalog
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.stale_after_seconds = stale_after_seconds
        self.history_limit = history_limit

    def _historical_payloads(
        self,
        *,
        current_inbox_id: int,
        current_event_timestamp: str,
        max_window_seconds: int,
    ) -> list[dict[str, Any]]:
        """Load recent processed events in bounded pages, oldest first."""
        event_time = _utc_datetime(current_event_timestamp)
        cutoff = event_time - timedelta(seconds=max_window_seconds)
        future_limit = datetime.now(timezone.utc) + timedelta(minutes=5)

        payloads: list[dict[str, Any]] = []
        before_inbox_id = current_inbox_id
        page_size = min(self.history_limit, 500)

        while len(payloads) < self.history_limit:
            rows = self.connection.execute(
                """
                SELECT inbox_id, agent_id, event_id, payload_json
                FROM soc_event_inbox
                WHERE processing_status = 'processed'
                  AND inbox_id < %s
                ORDER BY inbox_id DESC
                LIMIT %s
                """,
                (before_inbox_id, page_size),
            ).fetchall()

            if not rows:
                break

            for row in rows:
                try:
                    payload = json.loads(row["payload_json"])
                    if not isinstance(payload, dict):
                        continue

                    timestamp = _utc_datetime(payload["timestamp"])

                    if timestamp < cutoff or timestamp > future_limit:
                        continue

                    historical_payload = _payload_for_engine(
                        row["agent_id"],
                        row["event_id"],
                        payload,
                    )

                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    json.JSONDecodeError,
                    RecursionError,
                    SOCWorkerError,
                ):
                    # Malformed historical events must not block current work.
                    continue

                payloads.append(historical_payload)

                if len(payloads) >= self.history_limit:
                    break

            if len(payloads) >= self.history_limit or len(rows) < page_size:
                break

            before_inbox_id = rows[-1]["inbox_id"]

        return list(reversed(payloads))

    def _process_claim(self, claim: dict[str, object]) -> int:
        """Analyze a claim and atomically finalize it with all incidents."""
        inbox_id = claim.get("inbox_id")
        agent_id = claim.get("agent_id")
        event_id = claim.get("event_id")
        claim_token = claim.get("claim_token")
        payload = claim.get("payload")

        if (
            isinstance(inbox_id, bool)
            or not isinstance(inbox_id, int)
            or inbox_id < 1
            or not isinstance(agent_id, str)
            or not isinstance(event_id, str)
            or not isinstance(claim_token, str)
            or not claim_token
            or not isinstance(payload, dict)
        ):
            raise SOCWorkerError("Claim returned an invalid shape")

        self._ensure_idle_connection()

        max_window = max(
            (
                rule.window_seconds
                for rule in self.catalog.correlation_rules
            ),
            default=1,
        )

        historical = self._historical_payloads(
            current_inbox_id=inbox_id,
            current_event_timestamp=payload["timestamp"],
            max_window_seconds=max_window,
        )
        current = _payload_for_engine(agent_id, event_id, payload)

        pipeline_result = self.pipeline.process_batch(
            [*historical, current],
            detection_rules=self.catalog.detection_rules,
            correlation_rules=self.catalog.correlation_rules,
        )
        incidents = self.builder.build(pipeline_result)

        # The inbox row and every incident/evidence/history record share
        # one PostgreSQL transaction. A lost token aborts the whole unit.
        with transaction(self.connection):
            finalized = self.connection.execute(
                """
                UPDATE soc_event_inbox
                SET
                    processing_status = 'processed',
                    processed_at = %s,
                    claim_token = NULL,
                    claimed_at = NULL,
                    last_error = NULL
                WHERE inbox_id = %s
                  AND processing_status = 'processing'
                  AND claim_token = %s
                RETURNING inbox_id
                """,
                (
                    datetime.now(timezone.utc),
                    inbox_id,
                    claim_token,
                ),
            ).fetchone()

            if finalized is None:
                raise ClaimOwnershipLost(
                    "Claim token is no longer current; refusing finalization"
                )

            self.incidents.save_many_in_transaction(incidents)

        return len(incidents)

    def run_once(self) -> WorkerResult:
        """Process at most batch_size events in one bounded run."""
        self._ensure_idle_connection()

        claimed_count = 0
        processed = 0
        retried_or_failed = 0
        incidents_emitted = 0
        claims_lost = 0
        last_inbox_id = None

        for batch_index in range(self.batch_size):
            claim = self.collectors.claim_next_pending(
                max_attempts=self.max_attempts,
                stale_after_seconds=self.stale_after_seconds,
                recover_stale=(batch_index == 0),
                after_inbox_id=last_inbox_id,
            )

            if claim is None:
                break

            last_inbox_id = claim["inbox_id"]
            claimed_count += 1

            try:
                payload_error = claim.get("payload_error")

                if payload_error is not None:
                    if not isinstance(payload_error, str):
                        raise SOCWorkerError(
                            "Claim returned an invalid payload error"
                        )
                    raise SOCWorkerError(payload_error)

                incidents_emitted += self._process_claim(claim)
                processed += 1

            except ClaimOwnershipLost as exc:
                claims_lost += 1
                print(
                    "[WARN] Claim ownership lost for "
                    f"inbox_id={claim['inbox_id']}: {exc}",
                    file=sys.stderr,
                )
                continue

            except Exception as exc:
                retried_or_failed += 1
                inbox_id = claim.get("inbox_id")
                claim_token = claim.get("claim_token")

                if (
                    isinstance(inbox_id, bool)
                    or not isinstance(inbox_id, int)
                    or inbox_id < 1
                    or not isinstance(claim_token, str)
                    or not claim_token
                ):
                    raise SOCWorkerError(
                        "Could not record worker failure: "
                        "claim identifiers are invalid"
                    ) from exc

                try:
                    failure_recorded = self.collectors.fail_claim(
                        inbox_id,
                        claim_token,
                        f"{type(exc).__name__}: {exc}",
                        max_attempts=self.max_attempts,
                    )
                except Exception as failure_exc:
                    raise SOCWorkerError(
                        "Could not record worker failure for "
                        f"inbox_id={inbox_id}"
                    ) from failure_exc

                if failure_recorded is not True:
                    raise SOCWorkerError(
                        "Could not record worker failure for "
                        f"inbox_id={inbox_id}: claim is no longer owned"
                    ) from exc

                print(
                    "[ERROR] Event processing failed for "
                    f"inbox_id={inbox_id}: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )

        return WorkerResult(
            claimed=claimed_count,
            processed=processed,
            retried_or_failed=retried_or_failed,
            incidents_emitted=incidents_emitted,
            claims_lost=claims_lost,
        )


def run_continuous(
    worker: PostgresSOCWorker,
    stop_event: threading.Event,
    poll_interval: float,
) -> None:
    """Run bounded PostgreSQL worker batches until stop is requested."""
    if (
        isinstance(poll_interval, bool)
        or not isinstance(poll_interval, (int, float))
        or not 0.1 <= poll_interval <= 3600
    ):
        raise ValueError(
            "poll_interval must be between 0.1 and 3600 seconds"
        )

    while not stop_event.is_set():
        result = worker.run_once()
        print(json.dumps(result.to_dict(), sort_keys=True), flush=True)
        stop_event.wait(poll_interval)


__all__ = [
    "PostgresSOCWorker",
    "validate_postgres_worker_schema",
    "run_continuous",
]
