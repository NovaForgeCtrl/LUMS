#!/usr/bin/env python3
"""Explicit, idempotent schema migration for the persistent SOC worker."""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from .worker_schema import (
    RECOVERY_COLUMNS,
    RECOVERY_INDEX,
    validate_claim_columns,
    validate_recovery_index,
    validate_schema_migrations,
)


MIGRATION_VERSION = "001-soc-worker-claims"
DEFAULT_DB_PATH = "/var/lib/lums/lums.db"

_REQUIRED_INBOX_COLUMNS = {
    "inbox_id",
    "agent_id",
    "event_id",
    "payload_json",
    "payload_sha256",
    "received_at",
    "processing_status",
    "processed_at",
    "last_error",
}
_REQUIRED_MIGRATION_COLUMNS = {"version", "applied_at"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_recovery_index(connection: sqlite3.Connection) -> None:
    """Create a missing recovery index and reject an incorrect definition."""
    if not validate_recovery_index(connection):
        connection.execute(
            f"CREATE INDEX {RECOVERY_INDEX} "
            f"ON soc_event_inbox({', '.join(RECOVERY_COLUMNS)})"
        )

    if not validate_recovery_index(connection):
        raise RuntimeError(
            f"Recovery index {RECOVERY_INDEX} could not be created"
        )


def run_migration(db_path: str | Path) -> bool:
    """Apply the claim metadata migration atomically.

    The database and the existing SOC inbox must already be initialized.
    Returns True if the migration was applied, False if already recorded.
    """
    path = str(db_path)
    if not os.path.isfile(path):
        raise RuntimeError(f"Database does not exist: {path}")

    connection = sqlite3.connect(path, timeout=5.0)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")

        inbox_exists = connection.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'soc_event_inbox'
        """).fetchone()
        if inbox_exists is None:
            raise RuntimeError(
                "soc_event_inbox does not exist; initialize SOC storage first"
            )

        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(soc_event_inbox)"
            ).fetchall()
        }
        missing = _REQUIRED_INBOX_COLUMNS - columns
        if missing:
            raise RuntimeError(
                "soc_event_inbox is missing required columns: "
                + ", ".join(sorted(missing))
            )

        connection.execute("BEGIN IMMEDIATE")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """)

        migration_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(schema_migrations)"
            ).fetchall()
        }
        missing_migration_columns = (
            _REQUIRED_MIGRATION_COLUMNS - migration_columns
        )
        if missing_migration_columns:
            raise RuntimeError(
                "schema_migrations is missing required columns: "
                + ", ".join(sorted(missing_migration_columns))
            )

        validate_schema_migrations(connection)

        recorded = connection.execute("""
            SELECT 1
            FROM schema_migrations
            WHERE version = ?
        """, (MIGRATION_VERSION,)).fetchone()

        if recorded is not None:
            current_columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(soc_event_inbox)"
                ).fetchall()
            }
            required_claim_columns = {
                "claim_token", "claimed_at", "attempts"
            }
            if not required_claim_columns <= current_columns:
                raise RuntimeError(
                    "Migration is recorded but claim columns are missing; "
                    "manual recovery is required"
                )

            validate_claim_columns(connection)

            # A missing index can be safely restored. An incorrect one
            # indicates schema drift and must not be silently replaced.
            _ensure_recovery_index(connection)

            connection.commit()
            return False

        existing_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(soc_event_inbox)"
            ).fetchall()
        }

        if "claim_token" not in existing_columns:
            connection.execute(
                "ALTER TABLE soc_event_inbox ADD COLUMN claim_token TEXT"
            )
        if "claimed_at" not in existing_columns:
            connection.execute(
                "ALTER TABLE soc_event_inbox ADD COLUMN claimed_at TEXT"
            )
        if "attempts" not in existing_columns:
            connection.execute("""
                ALTER TABLE soc_event_inbox
                ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0
            """)

        # Reject incompatible pre-existing definitions before recording
        # the migration.
        validate_claim_columns(connection)

        _ensure_recovery_index(connection)

        connection.execute("""
            INSERT INTO schema_migrations(version, applied_at)
            VALUES (?, ?)
        """, (MIGRATION_VERSION, utc_now()))

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    db_path = os.environ.get("LUMS_DB_PATH", DEFAULT_DB_PATH)
    try:
        applied = run_migration(db_path)
    except Exception as exc:
        print(f"[ERROR] SOC worker migration failed: {exc}", file=sys.stderr)
        return 1

    state = "applied" if applied else "already applied"
    print(f"[OK] {MIGRATION_VERSION}: {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
