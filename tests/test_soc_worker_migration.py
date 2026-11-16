import sqlite3

import pytest

from server.soc.collector_store import CollectorStore
from server.soc.worker_migration import MIGRATION_VERSION, run_migration


def make_database(path):
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    CollectorStore(connection)
    connection.commit()
    connection.close()


def columns(path):
    connection = sqlite3.connect(path)
    try:
        return {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(soc_event_inbox)"
            ).fetchall()
        }
    finally:
        connection.close()


def test_migration_adds_claim_metadata_atomically(tmp_path):
    path = tmp_path / "soc.sqlite"
    make_database(path)

    assert run_migration(path) is True
    assert {"claim_token", "claimed_at", "attempts"} <= columns(path)

    connection = sqlite3.connect(path)
    try:
        row = connection.execute("""
            SELECT version FROM schema_migrations WHERE version = ?
        """, (MIGRATION_VERSION,)).fetchone()
        assert row == (MIGRATION_VERSION,)

        index = connection.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type = 'index'
              AND name = 'idx_soc_event_inbox_claim_recovery'
        """).fetchone()
        assert index is not None
    finally:
        connection.close()


def test_migration_is_idempotent(tmp_path):
    path = tmp_path / "soc.sqlite"
    make_database(path)

    assert run_migration(path) is True
    assert run_migration(path) is False

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("""
            SELECT COUNT(*) FROM schema_migrations WHERE version = ?
        """, (MIGRATION_VERSION,)).fetchone()[0] == 1
    finally:
        connection.close()


def test_migration_refuses_database_without_inbox(tmp_path):
    path = tmp_path / "empty.sqlite"
    sqlite3.connect(path).close()

    with pytest.raises(RuntimeError, match="soc_event_inbox"):
        run_migration(path)


def test_migration_refuses_missing_database(tmp_path):
    path = tmp_path / "missing.sqlite"

    with pytest.raises(RuntimeError, match="does not exist"):
        run_migration(path)


def test_migration_preserves_existing_inbox_rows(tmp_path):
    path = tmp_path / "soc.sqlite"
    make_database(path)

    connection = sqlite3.connect(path)
    try:
        connection.execute("""
            INSERT INTO soc_collector_agents (
                agent_id, display_name, certificate_sha256,
                status, created_at
            ) VALUES ('linux01', 'Linux test host', ?, 'active', ?)
        """, ("a" * 64, "2026-10-29T09:00:00+00:00"))
        connection.execute("""
            INSERT INTO soc_event_inbox (
                agent_id, event_id, payload_json, payload_sha256, received_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            "linux01",
            "event-1",
            '{"event_id":"event-1","source":"linux01",'
            '"event_type":"test","fields":{}}',
            "b" * 64,
            "2026-10-29T09:00:00+00:00",
        ))
        connection.commit()
    finally:
        connection.close()

    assert run_migration(path) is True

    connection = sqlite3.connect(path)
    try:
        row = connection.execute("""
            SELECT event_id, processing_status, attempts, claim_token, claimed_at
            FROM soc_event_inbox
        """).fetchone()
        assert row == ("event-1", "pending", 0, None, None)
    finally:
        connection.close()


def test_migration_restores_missing_recovery_index(tmp_path):
    path = tmp_path / "soc.sqlite"
    make_database(path)

    assert run_migration(path) is True

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "DROP INDEX idx_soc_event_inbox_claim_recovery"
        )
        connection.commit()
    finally:
        connection.close()

    # The migration is already recorded, but may restore the missing index.
    assert run_migration(path) is False

    connection = sqlite3.connect(path)
    try:
        index = connection.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type = 'index'
              AND name = 'idx_soc_event_inbox_claim_recovery'
              AND tbl_name = 'soc_event_inbox'
        """).fetchone()
        assert index is not None

        columns = [
            row[2]
            for row in connection.execute(
                "PRAGMA index_info('idx_soc_event_inbox_claim_recovery')"
            ).fetchall()
        ]
        assert columns == [
            "processing_status", "claimed_at", "inbox_id"
        ]
    finally:
        connection.close()


def test_migration_rejects_recovery_index_with_wrong_definition(tmp_path):
    path = tmp_path / "soc.sqlite"
    make_database(path)

    assert run_migration(path) is True

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "DROP INDEX idx_soc_event_inbox_claim_recovery"
        )
        connection.execute("""
            CREATE INDEX idx_soc_event_inbox_claim_recovery
            ON soc_event_inbox(inbox_id, claimed_at, processing_status)
        """)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(RuntimeError, match="unexpected definition"):
        run_migration(path)


def test_migration_rejects_unique_recovery_index(tmp_path):
    path = tmp_path / "soc.sqlite"
    make_database(path)
    assert run_migration(path) is True

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "DROP INDEX idx_soc_event_inbox_claim_recovery"
        )
        connection.execute("""
            CREATE UNIQUE INDEX idx_soc_event_inbox_claim_recovery
            ON soc_event_inbox(
                processing_status, claimed_at, inbox_id
            )
        """)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(RuntimeError, match="unexpected definition"):
        run_migration(path)


def test_migration_rejects_partial_recovery_index(tmp_path):
    path = tmp_path / "soc.sqlite"
    make_database(path)
    assert run_migration(path) is True

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "DROP INDEX idx_soc_event_inbox_claim_recovery"
        )
        connection.execute("""
            CREATE INDEX idx_soc_event_inbox_claim_recovery
            ON soc_event_inbox(
                processing_status, claimed_at, inbox_id
            )
            WHERE processing_status = 'pending'
        """)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(RuntimeError, match="unexpected definition"):
        run_migration(path)

def test_migration_rejects_incomplete_inbox_schema(tmp_path):
    path = tmp_path / "incomplete-inbox.sqlite"
    make_database(path)

    connection = sqlite3.connect(path)
    try:
        connection.execute("DROP TABLE soc_event_inbox")
        connection.execute("""
            CREATE TABLE soc_event_inbox (
                inbox_id INTEGER PRIMARY KEY,
                agent_id TEXT,
                event_id TEXT,
                payload_json TEXT,
                received_at TEXT,
                processing_status TEXT,
                processed_at TEXT,
                last_error TEXT
            )
        """)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        RuntimeError,
        match="soc_event_inbox is missing required columns: payload_sha256",
    ):
        run_migration(path)

    connection = sqlite3.connect(path)
    try:
        columns_after = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(soc_event_inbox)"
            ).fetchall()
        }
        assert "claim_token" not in columns_after
        assert "claimed_at" not in columns_after
        assert "attempts" not in columns_after

        migration_table = connection.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'schema_migrations'
        """).fetchone()
        assert migration_table is None
    finally:
        connection.close()


def test_migration_rejects_incompatible_schema_migrations_table(tmp_path):
    path = tmp_path / "incompatible-migrations.sqlite"
    make_database(path)

    connection = sqlite3.connect(path)
    try:
        connection.execute("""
            CREATE TABLE schema_migrations (
                version TEXT PRIMARY KEY
            )
        """)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        RuntimeError,
        match="schema_migrations is missing required columns: applied_at",
    ):
        run_migration(path)

    connection = sqlite3.connect(path)
    try:
        columns_after = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(schema_migrations)"
            ).fetchall()
        }
        assert columns_after == {"version"}

        inbox_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(soc_event_inbox)"
            ).fetchall()
        }
        assert "claim_token" not in inbox_columns
        assert "claimed_at" not in inbox_columns
        assert "attempts" not in inbox_columns

        recovery_index = connection.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type = 'index'
              AND name = 'idx_soc_event_inbox_claim_recovery'
        """).fetchone()
        assert recovery_index is None

        migration_rows = connection.execute(
            "SELECT version FROM schema_migrations"
        ).fetchall()
        assert migration_rows == []
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("column", "definition", "expected_metadata"),
    [
        ("claim_token", "claim_token INTEGER", ("INTEGER", 0, None, 0)),
        ("claimed_at", "claimed_at INTEGER", ("INTEGER", 0, None, 0)),
        (
            "attempts",
            "attempts TEXT NOT NULL DEFAULT 0",
            ("TEXT", 1, "0", 0),
        ),
        (
            "attempts",
            "attempts INTEGER DEFAULT 0",
            ("INTEGER", 0, "0", 0),
        ),
        (
            "attempts",
            "attempts INTEGER NOT NULL DEFAULT 1",
            ("INTEGER", 1, "1", 0),
        ),
    ],
)
def test_migration_rejects_malformed_existing_claim_columns(
    tmp_path, column, definition, expected_metadata
):
    path = tmp_path / "malformed-claim.sqlite"
    make_database(path)

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            f"ALTER TABLE soc_event_inbox ADD COLUMN {definition}"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(RuntimeError, match="unexpected definition"):
        run_migration(path)

    connection = sqlite3.connect(path)
    try:
        actual = {
            row[1]: tuple(row[2:])
            for row in connection.execute(
                "PRAGMA table_info(soc_event_inbox)"
            ).fetchall()
        }

        assert column in actual
        assert actual[column] == expected_metadata

        for claim_column in {"claim_token", "claimed_at", "attempts"} - {
            column
        }:
            assert claim_column not in actual

        migration_table = connection.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'schema_migrations'
        """).fetchone()
        assert migration_table is None

        recovery_index = connection.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type = 'index'
              AND name = 'idx_soc_event_inbox_claim_recovery'
        """).fetchone()
        assert recovery_index is None
    finally:
        connection.close()


@pytest.mark.parametrize(
    "definition",
    [
        """
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE schema_migrations (
            version TEXT,
            applied_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT
        )
        """,
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at INTEGER NOT NULL
        )
        """,
    ],
)
def test_migration_rejects_malformed_schema_migrations_definitions(
    tmp_path, definition
):
    path = tmp_path / "malformed-migrations.sqlite"
    make_database(path)

    connection = sqlite3.connect(path)
    try:
        connection.execute(definition)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(RuntimeError, match="unexpected definition"):
        run_migration(path)

    connection = sqlite3.connect(path)
    try:
        inbox_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(soc_event_inbox)"
            ).fetchall()
        }
        assert "claim_token" not in inbox_columns
        assert "claimed_at" not in inbox_columns
        assert "attempts" not in inbox_columns

        recovery_index = connection.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type = 'index'
              AND name = 'idx_soc_event_inbox_claim_recovery'
        """).fetchone()
        assert recovery_index is None

        migration_rows = connection.execute(
            "SELECT * FROM schema_migrations"
        ).fetchall()
        assert migration_rows == []
    finally:
        connection.close()
