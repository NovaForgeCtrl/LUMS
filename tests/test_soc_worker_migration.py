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
