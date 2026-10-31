#!/usr/bin/env python3
"""Initialize and validate the persistent SOC storage schema."""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from .collector_store import CollectorStore
from .incident_store import IncidentStore


DEFAULT_DB_PATH = "/var/lib/lums/lums.db"

REQUIRED_COLUMNS = {
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

REQUIRED_INDEXES = {
    "idx_soc_event_inbox_pending": (
        "soc_event_inbox",
        ("processing_status", "inbox_id"),
    ),
    "idx_soc_event_inbox_agent_received": (
        "soc_event_inbox",
        ("agent_id", "received_at"),
    ),
    "idx_soc_incidents_status_updated": (
        "soc_incidents",
        ("status", "updated_at"),
    ),
    "idx_soc_incident_evidence_reference": (
        "soc_incident_evidence",
        ("kind", "reference_id"),
    ),
}

REQUIRED_FOREIGN_KEYS = {
    "soc_event_inbox": {
        ("agent_id", "soc_collector_agents", "agent_id", "NO ACTION"),
    },
    "soc_incident_evidence": {
        ("incident_id", "soc_incidents", "incident_id", "CASCADE"),
    },
    "soc_incident_history": {
        ("incident_id", "soc_incidents", "incident_id", "CASCADE"),
    },
}


def _table_columns(
    connection: sqlite3.Connection,
    table: str,
) -> set[str]:
    return {
        row[1]
        for row in connection.execute(
            f'PRAGMA table_info("{table}")'
        ).fetchall()
    }


def _validate_existing_tables_before_creation(
    connection: sqlite3.Connection,
) -> None:
    """Reject malformed existing tables before stores create dependent indexes."""
    for table, required in REQUIRED_COLUMNS.items():
        exists = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table,),
        ).fetchone()

        if exists is None:
            continue

        actual = _table_columns(connection, table)
        missing = required - actual

        if missing:
            raise RuntimeError(
                f"{table} is missing required columns: "
                + ", ".join(sorted(missing))
            )


def _validate_tables(connection: sqlite3.Connection) -> None:
    for table, required in REQUIRED_COLUMNS.items():
        actual = _table_columns(connection, table)
        missing = required - actual

        if missing:
            raise RuntimeError(
                f"{table} is missing required columns: "
                + ", ".join(sorted(missing))
            )


def _validate_indexes(connection: sqlite3.Connection) -> None:
    for name, (expected_table, expected_columns) in REQUIRED_INDEXES.items():
        row = connection.execute(
            """
            SELECT tbl_name
            FROM sqlite_master
            WHERE type = 'index' AND name = ?
            """,
            (name,),
        ).fetchone()

        if row is None:
            raise RuntimeError(f"Required SOC index is missing: {name}")

        if row[0] != expected_table:
            raise RuntimeError(
                f"SOC index {name} belongs to an unexpected table"
            )

        actual_columns = tuple(
            item[2]
            for item in connection.execute(
                f'PRAGMA index_info("{name}")'
            ).fetchall()
        )

        if actual_columns != expected_columns:
            raise RuntimeError(
                f"SOC index {name} has an unexpected definition"
            )


def _validate_foreign_keys(connection: sqlite3.Connection) -> None:
    for table, expected in REQUIRED_FOREIGN_KEYS.items():
        actual = {
            (
                row[3],  # source column
                row[2],  # referenced table
                row[4],  # referenced column
                str(row[6]).upper(),  # ON DELETE
            )
            for row in connection.execute(
                f'PRAGMA foreign_key_list("{table}")'
            ).fetchall()
        }

        missing = expected - actual
        if missing:
            raise RuntimeError(
                f"{table} is missing required foreign keys: "
                + repr(sorted(missing))
            )


def validate_storage_schema(connection: sqlite3.Connection) -> None:
    """Reject incomplete or incompatible SOC base schemas."""
    _validate_tables(connection)
    _validate_indexes(connection)
    _validate_foreign_keys(connection)

    violations = connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if violations:
        raise RuntimeError(
            f"SOC database contains foreign-key violations: {violations[:5]!r}"
        )


def initialize_storage(db_path: str | Path) -> None:
    """Create missing SOC base tables and validate the resulting schema.

    Existing data is preserved. Existing incompatible tables are rejected;
    this initializer does not attempt destructive schema repair.
    """
    path = str(db_path)

    if not os.path.isfile(path):
        raise RuntimeError(f"Database does not exist: {path}")

    connection = sqlite3.connect(path, timeout=5.0)

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")

        # Own the complete SOC schema migration as one write transaction.
        # Store initializers must not commit or roll back this transaction.
        connection.execute("BEGIN IMMEDIATE")

        _validate_existing_tables_before_creation(connection)

        CollectorStore(connection, initialize_schema=True)
        IncidentStore(connection, initialize_schema=True)

        validate_storage_schema(connection)
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def main() -> int:
    db_path = os.environ.get("LUMS_DB_PATH", DEFAULT_DB_PATH)

    try:
        initialize_storage(db_path)
    except Exception as exc:
        print(
            f"[ERROR] SOC storage initialization failed: {exc}",
            file=sys.stderr,
        )
        return 1

    print("[OK] SOC base storage initialized and validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
