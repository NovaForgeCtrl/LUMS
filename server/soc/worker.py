"""Persistent, transactional worker for the LUMS SOC event inbox.

This module is deliberately not started by the web application. Run it
explicitly against an initialized database after applying worker_migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .collector_store import CollectorStore
from .incident_builder import IncidentBuilder
from .incident_store import IncidentStore
from .pipeline import SOCPipeline
from .rule_catalog import LoadedRuleCatalog, load_catalog


DEFAULT_DB_PATH = "/var/lib/lums/lums.db"
DEFAULT_RULES_PATH = "/app/server/soc/rules.json"
DEFAULT_BATCH_SIZE = 25
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_STALE_SECONDS = 300
DEFAULT_HISTORY_LIMIT = 5000


class SOCWorkerError(RuntimeError):
    """Raised when the worker cannot safely process an inbox item."""


@dataclass(frozen=True)
class WorkerResult:
    claimed: int
    processed: int
    retried_or_failed: int
    incidents_written: int

    def to_dict(self) -> dict[str, int]:
        return {
            "claimed": self.claimed,
            "processed": self.processed,
            "retried_or_failed": self.retried_or_failed,
            "incidents_written": self.incidents_written,
        }


def _utc_datetime(value: str) -> datetime:
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

        # These constructors initialize schema with executescript. They must
        # run before any processing transaction is opened.
        self.collectors = CollectorStore(connection)
        self.incidents = IncidentStore(connection)
        self.pipeline = SOCPipeline()
        self.builder = IncidentBuilder()
        self.catalog = catalog
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.stale_after_seconds = stale_after_seconds
        self.history_limit = history_limit

    def _historical_payloads(
        self, *, current_inbox_id: int, max_window_seconds: int
    ) -> list[dict[str, Any]]:
        """Load a bounded tail of already processed inbox events."""
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

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=max_window_seconds)
        payloads: list[dict[str, Any]] = []

        for row in reversed(rows):
            try:
                payload = json.loads(row["payload_json"])
                timestamp = _utc_datetime(payload["timestamp"])
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                # Old malformed records are not allowed to break unrelated
                # current events. They are excluded from correlation.
                continue

            if timestamp < cutoff or timestamp > now + timedelta(minutes=5):
                continue

            payloads.append(
                _payload_for_engine(
                    row["agent_id"], row["event_id"], payload
                )
            )

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

        max_window = max(
            (rule.window_seconds for rule in self.catalog.correlation_rules),
            default=1,
        )
        historical = self._historical_payloads(
            current_inbox_id=inbox_id,
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

        try:
            self.connection.execute("BEGIN IMMEDIATE")

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
                raise SOCWorkerError(
                    "Claim token is no longer current; refusing finalization"
                )

            self.incidents.save_many_in_transaction(incidents)
            self.connection.commit()
            return len(incidents)

        except Exception:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def run_once(self) -> WorkerResult:
        """Claim a bounded batch and process each claim independently."""
        claims = self.collectors.claim_pending(
            limit=self.batch_size,
            max_attempts=self.max_attempts,
            stale_after_seconds=self.stale_after_seconds,
        )
        processed = 0
        retried_or_failed = 0
        incidents_written = 0

        for claim in claims:
            try:
                incidents_written += self._process_claim(claim)
                processed += 1
            except Exception as exc:
                retried_or_failed += 1
                inbox_id = claim.get("inbox_id")
                claim_token = claim.get("claim_token")
                if isinstance(inbox_id, int) and isinstance(claim_token, str):
                    try:
                        self.collectors.fail_claim(
                            inbox_id,
                            claim_token,
                            f"{type(exc).__name__}: {exc}",
                            max_attempts=self.max_attempts,
                        )
                    except Exception as failure_exc:
                        # Do not hide the original failure. The claim remains
                        # recoverable through stale-claim recovery.
                        print(
                            "[ERROR] Could not record worker failure for "
                            f"inbox_id={inbox_id}: {failure_exc}",
                            file=sys.stderr,
                        )
                print(
                    "[ERROR] Event processing failed for "
                    f"inbox_id={inbox_id}: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )

        return WorkerResult(
            claimed=len(claims),
            processed=processed,
            retried_or_failed=retried_or_failed,
            incidents_written=incidents_written,
        )


def _open_connection(db_path: str) -> sqlite3.Connection:
    if not os.path.isfile(db_path):
        raise SOCWorkerError(f"Database does not exist: {db_path}")
    connection = sqlite3.connect(
        db_path, timeout=5.0, isolation_level=None
    )
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one bounded batch and exit (the default).",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    db_path = os.environ.get("LUMS_DB_PATH", DEFAULT_DB_PATH)
    rules_path = os.environ.get("LUMS_SOC_RULES_PATH", DEFAULT_RULES_PATH)
    connection: sqlite3.Connection | None = None

    try:
        catalog = load_catalog(Path(rules_path))
        connection = _open_connection(db_path)
        worker = SOCWorker(
            connection,
            catalog,
            batch_size=args.batch_size,
        )
        result = worker.run_once()
        print(json.dumps(result.to_dict(), sort_keys=True))
        return 0
    except Exception as exc:
        print(
            f"[ERROR] SOC worker stopped safely: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
