"""Persistent, transactional worker for the LUMS SOC event inbox.

This module is deliberately not started by the web application. Run it
explicitly against an initialized database after applying worker_migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sqlite3
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .collector_store import CollectorStore
from .incident_builder import IncidentBuilder
from .incident_store import IncidentStore
from .pipeline import SOCPipeline
from .rule_catalog import LoadedRuleCatalog, load_catalog
from .worker_schema import (
    RECOVERY_INDEX,
    validate_claim_columns,
    validate_recovery_index,
    validate_schema_migrations,
)


DEFAULT_DB_PATH = "/var/lib/lums/lums.db"
DEFAULT_RULES_PATH = "/app/server/soc/rules.json"
DEFAULT_BATCH_SIZE = 25
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_STALE_SECONDS = 300
DEFAULT_HISTORY_LIMIT = 5000


class SOCWorkerError(RuntimeError):
    """Raised when the worker cannot safely process an inbox item."""


class ClaimOwnershipLost(SOCWorkerError):
    """Raised when a worker no longer owns the inbox claim."""


_REQUIRED_TABLE_COLUMNS = {
    "soc_collector_agents": {
        "agent_id", "display_name", "certificate_sha256",
        "status", "created_at", "revoked_at",
    },
    "soc_event_inbox": {
        "inbox_id", "agent_id", "event_id", "payload_json",
        "payload_sha256", "received_at", "processing_status",
        "processed_at", "last_error", "claim_token",
        "claimed_at", "attempts",
    },
    "soc_incidents": {
        "incident_id", "title", "summary", "severity",
        "status", "created_at", "updated_at",
    },
    "soc_incident_evidence": {
        "evidence_id", "incident_id", "kind", "reference_id",
        "description", "observed_at",
    },
    "soc_incident_history": {
        "history_id", "incident_id", "old_status", "new_status",
        "changed_at", "changed_by",
    },
    "schema_migrations": {"version", "applied_at"},
}


def validate_worker_schema(connection: sqlite3.Connection) -> None:
    """Validate the prepared worker schema without creating or changing it."""
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("connection must be a sqlite3.Connection")

    missing_tables = []
    missing_columns = []

    for table, required_columns in _REQUIRED_TABLE_COLUMNS.items():
        exists = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table,),
        ).fetchone()

        if exists is None:
            missing_tables.append(table)
            continue

        actual_columns = {
            row[1]
            for row in connection.execute(
                f'PRAGMA table_info("{table}")'
            ).fetchall()
        }
        missing = required_columns - actual_columns
        if missing:
            missing_columns.append(
                f"{table}: {', '.join(sorted(missing))}"
            )

    if missing_tables or missing_columns:
        details = []
        if missing_tables:
            details.append("missing tables: " + ", ".join(missing_tables))
        if missing_columns:
            details.append("missing columns: " + "; ".join(missing_columns))
        raise SOCWorkerError(
            "SOC worker schema is incomplete; no schema changes were made "
            "(" + " | ".join(details) + ")"
        )

    try:
        validate_schema_migrations(connection)
        validate_claim_columns(connection)
    except RuntimeError as exc:
        raise SOCWorkerError(
            "SOC worker schema has incompatible column definitions: "
            + str(exc)
        ) from exc

    migration = connection.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?",
        ("001-soc-worker-claims",),
    ).fetchone()
    if migration is None:
        raise SOCWorkerError(
            "Required migration 001-soc-worker-claims is not recorded; "
            "apply it explicitly before starting the worker"
        )

    try:
        index_valid = validate_recovery_index(connection)
    except RuntimeError as exc:
        raise SOCWorkerError(
            "Worker claim-recovery index has an unexpected definition"
        ) from exc

    if not index_valid:
        raise SOCWorkerError(
            f"Required index {RECOVERY_INDEX} is missing; "
            "apply the worker migration explicitly"
        )


@dataclass(frozen=True)
class WorkerResult:
    claimed: int
    processed: int
    retried_or_failed: int
    incidents_emitted: int
    claims_lost: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "claimed": self.claimed,
            "processed": self.processed,
            "retried_or_failed": self.retried_or_failed,
            "incidents_emitted": self.incidents_emitted,
            "claims_lost": self.claims_lost,
        }


def _utc_datetime(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Event timestamp must be a string")

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Event timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _internal_event_id(agent_id: str, event_id: str) -> str:
    """Namespace event identity by collector without exposing arbitrary input."""
    digest = hashlib.sha256(
        f"{agent_id}\0{event_id}".encode("utf-8")
    ).hexdigest()[:40]
    return f"evt-{digest}"


def _payload_for_engine(
    agent_id: str, event_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Build a validated event with a stable, collector-specific internal ID."""
    result = dict(payload)
    result["event_id"] = _internal_event_id(agent_id, event_id)
    fields = result.get("fields")
    if not isinstance(fields, dict):
        raise SOCWorkerError("Event fields must be an object")
    fields = dict(fields)
    # Keep original provenance available to future rules and incident review.
    fields.setdefault("_lums_collector_id", agent_id)
    fields.setdefault("_lums_original_event_id", event_id)
    result["fields"] = fields
    return result


class SOCWorker:
    """Claim and process inbox rows with transactional incident finalization."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        catalog: LoadedRuleCatalog,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        stale_after_seconds: int = DEFAULT_STALE_SECONDS,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> None:
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError("connection must be a sqlite3.Connection")

        # Validate before changing connection settings or constructing stores.
        # This check is read-only and applies to every worker entry point.
        validate_worker_schema(connection)

        for name, value, low, high in (
            ("batch_size", batch_size, 1, 500),
            ("max_attempts", max_attempts, 1, 100),
            ("stale_after_seconds", stale_after_seconds, 1, 86400),
            ("history_limit", history_limit, 1, 50000),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not low <= value <= high
            ):
                raise ValueError(f"{name} must be between {low} and {high}")
        if not isinstance(catalog, LoadedRuleCatalog):
            raise TypeError("catalog must be a LoadedRuleCatalog")

        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA busy_timeout = 5000")

        # Startup validation is performed before constructing the worker.
        # Stores must never create or migrate schema in the worker process.
        self.collectors = CollectorStore(
            connection, initialize_schema=False
        )
        self.incidents = IncidentStore(
            connection, initialize_schema=False
        )
        self.pipeline = SOCPipeline()
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
        """Load processed events within the current event's correlation window."""
        event_time = _utc_datetime(current_event_timestamp)
        cutoff = event_time - timedelta(seconds=max_window_seconds)
        future_limit = datetime.now(timezone.utc) + timedelta(minutes=5)

        rows = self.connection.execute(
            """
            SELECT inbox_id, agent_id, event_id, payload_json
            FROM soc_event_inbox
            WHERE processing_status = 'processed'
              AND inbox_id < ?
            ORDER BY inbox_id DESC
            LIMIT ?
            """,
            (current_inbox_id, self.history_limit),
        ).fetchall()

        payloads: list[dict[str, Any]] = []

        for row in reversed(rows):
            try:
                payload = json.loads(row["payload_json"])
                timestamp = _utc_datetime(payload["timestamp"])

                if timestamp < cutoff or timestamp > future_limit:
                    continue

                historical_payload = _payload_for_engine(
                    row["agent_id"], row["event_id"], payload
                )
            except (
                ValueError,
                TypeError,
                KeyError,
                json.JSONDecodeError,
                SOCWorkerError,
            ):
                # Old malformed records are excluded without breaking
                # processing of the current event.
                continue

            payloads.append(historical_payload)

        return payloads

    def _process_claim(self, claim: dict[str, object]) -> int:
        inbox_id = claim["inbox_id"]
        agent_id = claim["agent_id"]
        event_id = claim["event_id"]
        claim_token = claim["claim_token"]
        payload = claim["payload"]

        if (
            isinstance(inbox_id, bool)
            or not isinstance(inbox_id, int)
            or not isinstance(agent_id, str)
            or not isinstance(event_id, str)
            or not isinstance(claim_token, str)
            or not isinstance(payload, dict)
        ):
            raise SOCWorkerError("Claim returned an invalid shape")

        if self.connection.in_transaction:
            raise SOCWorkerError(
                "Worker cannot process a claim inside an existing transaction"
            )

        max_window = max(
            (rule.window_seconds for rule in self.catalog.correlation_rules),
            default=1,
        )
        historical = self._historical_payloads(
            current_inbox_id=inbox_id,
            current_event_timestamp=payload["timestamp"],
            max_window_seconds=max_window,
        )
        current = _payload_for_engine(agent_id, event_id, payload)

        # Include persisted events in the evaluation so correlation can cross
        # worker batches. Deterministic incident IDs and evidence inserts make
        # re-evaluation idempotent.
        pipeline_result = self.pipeline.process_batch(
            [*historical, current],
            detection_rules=self.catalog.detection_rules,
            correlation_rules=self.catalog.correlation_rules,
        )
        incidents = self.builder.build(pipeline_result)

        transaction_started = False
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            transaction_started = True

            # The inbox status and all incident records must commit together.
            cursor = self.connection.execute(
                """
                UPDATE soc_event_inbox
                SET processing_status = 'processed',
                    processed_at = ?,
                    claim_token = NULL,
                    claimed_at = NULL,
                    last_error = NULL
                WHERE inbox_id = ?
                  AND processing_status = 'processing'
                  AND claim_token = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    inbox_id,
                    claim_token,
                ),
            )
            if cursor.rowcount != 1:
                raise ClaimOwnershipLost(
                    "Claim token is no longer current; refusing finalization"
                )

            self.incidents.save_many_in_transaction(incidents)
            self.connection.commit()
            return len(incidents)

        except Exception:
            if transaction_started and self.connection.in_transaction:
                self.connection.rollback()
            raise

    def run_once(self) -> WorkerResult:
        """Claim and process events one at a time within a bounded batch."""
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
                # The old token must never be used to fail or modify a
                # claim that may already belong to another worker.
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
    worker: SOCWorker,
    stop_event: threading.Event,
    poll_interval: float,
) -> None:
    """Run bounded batches until a stop signal is requested."""
    if (
        isinstance(poll_interval, bool)
        or not isinstance(poll_interval, (int, float))
        or not 0.1 <= poll_interval <= 3600
    ):
        raise ValueError("poll_interval must be between 0.1 and 3600 seconds")

    while not stop_event.is_set():
        # Worker errors deliberately propagate to main().
        # The process then exits nonzero for supervisor-managed recovery.
        result = worker.run_once()
        print(json.dumps(result.to_dict(), sort_keys=True), flush=True)

        # Bound the polling rate even when the queue stays busy.
        stop_event.wait(poll_interval)


def _open_connection(db_path: str) -> sqlite3.Connection:
    if not os.path.isfile(db_path):
        raise SOCWorkerError(f"Database does not exist: {db_path}")
    connection = sqlite3.connect(
        db_path, timeout=5.0, isolation_level=None
    )
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="Process one bounded batch and exit (the default).",
    )
    mode.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously until SIGINT or SIGTERM.",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Seconds to wait between continuous batches (0.1-3600).",
    )
    args = parser.parse_args(argv)

    if not 0.1 <= args.poll_interval <= 3600:
        parser.error("--poll-interval must be between 0.1 and 3600 seconds")

    db_path = os.environ.get("LUMS_DB_PATH", DEFAULT_DB_PATH)
    rules_path = os.environ.get("LUMS_SOC_RULES_PATH", DEFAULT_RULES_PATH)
    connection: sqlite3.Connection | None = None
    stop_event = threading.Event()
    previous_handlers: dict[int, Any] = {}

    try:
        catalog = load_catalog(Path(rules_path))
        connection = _open_connection(db_path)
        worker = SOCWorker(
            connection,
            catalog,
            batch_size=args.batch_size,
        )

        if args.continuous:
            def request_stop(signum: int, frame: Any) -> None:
                # Do not interrupt transactions or perform I/O in the handler.
                stop_event.set()

            for signum in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[signum] = signal.signal(
                    signum, request_stop
                )

            run_continuous(worker, stop_event, args.poll_interval)
        else:
            result = worker.run_once()
            print(json.dumps(result.to_dict(), sort_keys=True), flush=True)

        return 0
    except Exception as exc:
        print(
            f"[ERROR] SOC worker stopped safely: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
