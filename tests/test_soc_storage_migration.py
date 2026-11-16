import sqlite3

import pytest

from server.soc.incident_store import IncidentStore
from server.soc.storage_migration import (
    initialize_storage,
    validate_storage_schema,
)


def create_empty_database(path):
    sqlite3.connect(path).close()


def test_storage_initialization_creates_all_soc_tables(tmp_path):
    path = tmp_path / "soc.sqlite"
    create_empty_database(path)

    initialize_storage(path)

    connection = sqlite3.connect(path)
    try:
        tables = {
            row[0]
            for row in connection.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
            """).fetchall()
        }

        assert {
            "soc_collector_agents",
            "soc_event_inbox",
            "soc_incidents",
            "soc_incident_evidence",
            "soc_incident_history",
        } <= tables

        validate_storage_schema(connection)
    finally:
        connection.close()


def test_storage_initialization_is_idempotent(tmp_path):
    path = tmp_path / "soc.sqlite"
    create_empty_database(path)

    initialize_storage(path)
    initialize_storage(path)

    connection = sqlite3.connect(path)
    try:
        validate_storage_schema(connection)
    finally:
        connection.close()


def test_storage_initialization_preserves_existing_data(tmp_path):
    path = tmp_path / "soc.sqlite"
    create_empty_database(path)

    initialize_storage(path)

    connection = sqlite3.connect(path)
    try:
        connection.execute("""
            INSERT INTO soc_collector_agents (
                agent_id,
                display_name,
                certificate_sha256,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            "linux01",
            "Linux test host",
            "a" * 64,
            "active",
            "2026-10-31T10:00:00+00:00",
        ))
        connection.commit()
    finally:
        connection.close()

    initialize_storage(path)

    connection = sqlite3.connect(path)
    try:
        row = connection.execute("""
            SELECT agent_id, display_name
            FROM soc_collector_agents
            WHERE agent_id = 'linux01'
        """).fetchone()

        assert row == ("linux01", "Linux test host")
    finally:
        connection.close()


def test_storage_initialization_rejects_incomplete_existing_table(tmp_path):
    path = tmp_path / "incomplete.sqlite"
    create_empty_database(path)

    connection = sqlite3.connect(path)
    try:
        connection.execute("""
            CREATE TABLE soc_event_inbox (
                inbox_id INTEGER PRIMARY KEY,
                agent_id TEXT,
                event_id TEXT
            )
        """)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        RuntimeError,
        match="soc_event_inbox is missing required columns",
    ):
        initialize_storage(path)


def test_storage_initialization_rejects_missing_database(tmp_path):
    path = tmp_path / "missing.sqlite"

    with pytest.raises(RuntimeError, match="Database does not exist"):
        initialize_storage(path)



def test_storage_initialization_rolls_back_all_soc_ddl_on_failure(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "soc-rollback.sqlite"
    create_empty_database(path)

    def fail_after_partial_incident_schema(self):
        self.connection.execute("""
            CREATE TABLE soc_incident_partial_probe (
                probe_id INTEGER PRIMARY KEY
            )
        """)
        raise sqlite3.OperationalError("injected incident schema failure")

    monkeypatch.setattr(
        IncidentStore,
        "_initialize_schema",
        fail_after_partial_incident_schema,
    )

    with pytest.raises(
        sqlite3.OperationalError,
        match="injected incident schema failure",
    ):
        initialize_storage(path)

    connection = sqlite3.connect(path)
    try:
        remaining_soc_objects = connection.execute("""
            SELECT type, name
            FROM sqlite_master
            WHERE name LIKE 'soc_%'
            ORDER BY type, name
        """).fetchall()

        assert remaining_soc_objects == []
    finally:
        connection.close()
