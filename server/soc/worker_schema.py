"""Shared validation for the SOC worker database schema."""

from __future__ import annotations

import re
import sqlite3


RECOVERY_INDEX = "idx_soc_event_inbox_claim_recovery"
RECOVERY_TABLE = "soc_event_inbox"
RECOVERY_COLUMNS = (
    "processing_status",
    "claimed_at",
    "inbox_id",
)


def _table_info(connection: sqlite3.Connection, table: str) -> dict:
    """Return SQLite column metadata indexed by column name."""
    return {
        row[1]: {
            "type": str(row[2] or "").strip().upper(),
            "notnull": int(row[3]),
            "default": row[4],
            "pk": int(row[5]),
        }
        for row in connection.execute(
            f'PRAGMA table_info("{table}")'
        ).fetchall()
    }


def validate_claim_columns(connection: sqlite3.Connection) -> None:
    """Validate the canonical SOC worker claim column definitions."""
    columns = _table_info(connection, "soc_event_inbox")

    expected = {
        "claim_token": ("TEXT", 0, None, 0),
        "claimed_at": ("TEXT", 0, None, 0),
        "attempts": ("INTEGER", 1, "0", 0),
    }

    for name, definition in expected.items():
        actual = columns.get(name)
        if actual is None:
            raise RuntimeError(f"Claim column {name} is missing")

        actual_definition = (
            actual["type"],
            actual["notnull"],
            (
                str(actual["default"]).strip()
                if actual["default"] is not None
                else None
            ),
            actual["pk"],
        )

        if actual_definition != definition:
            raise RuntimeError(
                f"Claim column {name} has an unexpected definition"
            )


def validate_schema_migrations(connection: sqlite3.Connection) -> None:
    """Validate the shared LUMS migration ledger column definitions."""
    columns = _table_info(connection, "schema_migrations")

    version = columns.get("version")
    if (
        version is None
        or version["type"] != "TEXT"
        or version["pk"] != 1
    ):
        raise RuntimeError(
            "schema_migrations column version has an unexpected definition"
        )

    applied_at = columns.get("applied_at")
    if (
        applied_at is None
        or applied_at["type"] != "TEXT"
        or applied_at["notnull"] != 1
        or applied_at["default"] is not None
        or applied_at["pk"] != 0
    ):
        raise RuntimeError(
            "schema_migrations column applied_at has an unexpected definition"
        )


def validate_recovery_index(connection: sqlite3.Connection) -> bool:
    """Validate the complete recovery index definition.

    Returns False if the index is missing. Raises RuntimeError if an index
    with the expected name exists but has an unexpected definition.
    """
    row = connection.execute(
        """
        SELECT tbl_name, sql
        FROM sqlite_master
        WHERE type = 'index' AND name = ?
        """,
        (RECOVERY_INDEX,),
    ).fetchone()

    if row is None:
        return False

    table_name, sql = row
    if table_name != RECOVERY_TABLE or not isinstance(sql, str):
        raise RuntimeError(
            f"Recovery index {RECOVERY_INDEX} has an unexpected definition"
        )

    index_list = connection.execute(
        f'PRAGMA index_list("{RECOVERY_TABLE}")'
    ).fetchall()
    metadata = next(
        (item for item in index_list if item[1] == RECOVERY_INDEX),
        None,
    )

    # PRAGMA index_list columns:
    # seq, name, unique, origin, partial
    if metadata is None or metadata[2] != 0 or metadata[4] != 0:
        raise RuntimeError(
            f"Recovery index {RECOVERY_INDEX} has an unexpected definition"
        )

    # PRAGMA index_xinfo columns:
    # seqno, cid, name, desc, coll, key
    index_info = connection.execute(
        f'PRAGMA index_xinfo("{RECOVERY_INDEX}")'
    ).fetchall()
    key_columns = tuple(
        (item[2], item[3], item[4])
        for item in index_info
        if item[5] == 1
    )
    expected_columns = tuple(
        (column, 0, "BINARY") for column in RECOVERY_COLUMNS
    )

    if key_columns != expected_columns:
        raise RuntimeError(
            f"Recovery index {RECOVERY_INDEX} has an unexpected definition"
        )

    def normalize_index_sql(value: str) -> str:
        return re.sub(r'[\s"`\[\]]+', "", value).lower()

    expected_sql = (
        f"CREATE INDEX {RECOVERY_INDEX} ON {RECOVERY_TABLE}"
        f"({','.join(RECOVERY_COLUMNS)})"
    )

    if normalize_index_sql(sql) != normalize_index_sql(expected_sql):
        raise RuntimeError(
            f"Recovery index {RECOVERY_INDEX} has an unexpected definition"
        )

    return True
