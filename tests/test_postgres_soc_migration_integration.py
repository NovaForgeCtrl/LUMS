"""PostgreSQL integration tests for migration 009-soc-storage."""

from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from postgres_test_support import require_test_database_url, run_cleanup
from server.migration_runner import run_migrations
from server.migrations.soc_storage import SOC_STORAGE_MIGRATION


@pytest.fixture
def postgres_environment():
    database_url = require_test_database_url()

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-soc-migration-setup",
    )

    connection = None
    schema_name = f"lums_soc_migration_test_{uuid4().hex}"
    schema_created = False

    try:
        identity = admin.execute(
            "SELECT current_database(), current_user"
        ).fetchone()

        if (
            identity["current_database"] != "lums_integration"
            or identity["current_user"] != "lums_pg_bootstrap"
        ):
            pytest.fail(
                "Refusing tests outside the dedicated integration database."
            )

        admin.execute(
            sql.SQL("CREATE SCHEMA {}").format(
                sql.Identifier(schema_name)
            )
        )
        schema_created = True

        connection = psycopg.connect(
            database_url,
            autocommit=True,
            row_factory=dict_row,
            application_name="lums-soc-migration-test",
        )
        connection.execute(
            sql.SQL("SET search_path TO {}").format(
                sql.Identifier(schema_name)
            )
        )

        yield connection

    finally:
        run_cleanup(
            (
                "close test connection",
                lambda: connection.close() if connection is not None else None,
            ),
            (
                "drop test schema",
                lambda: admin.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema_name)
                    )
                ) if schema_created else None,
            ),
            ("close admin connection", admin.close),
        )


def test_soc_storage_migration_creates_schema_and_is_idempotent(
    postgres_environment,
):
    connection = postgres_environment

    first = run_migrations(connection, (SOC_STORAGE_MIGRATION,))
    second = run_migrations(connection, (SOC_STORAGE_MIGRATION,))

    assert first.applied == ("009-soc-storage",)
    assert second.applied == ()
    assert second.already_applied == ("009-soc-storage",)

    rows = connection.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_type = 'BASE TABLE'
        """
    ).fetchall()

    expected_tables = {
        "soc_collector_agents",
        "soc_event_inbox",
        "soc_incidents",
        "soc_incident_evidence",
        "soc_incident_history",
        "schema_migrations",
    }
    assert expected_tables <= {row["table_name"] for row in rows}

    columns = connection.execute(
        """
        SELECT table_name, column_name, data_type,
               is_nullable, is_identity
        FROM information_schema.columns
        WHERE table_schema = current_schema()
        """
    ).fetchall()

    actual_columns = {
        (row["table_name"], row["column_name"]): row
        for row in columns
    }

    expected_timestamps = {
        ("soc_collector_agents", "created_at"),
        ("soc_collector_agents", "revoked_at"),
        ("soc_event_inbox", "received_at"),
        ("soc_event_inbox", "processed_at"),
        ("soc_event_inbox", "claimed_at"),
        ("soc_incidents", "created_at"),
        ("soc_incidents", "updated_at"),
        ("soc_incident_evidence", "observed_at"),
        ("soc_incident_history", "changed_at"),
    }

    for table, column in expected_timestamps:
        assert actual_columns[(table, column)]["data_type"] == (
            "timestamp with time zone"
        )

    identity_columns = {
        (row["table_name"], row["column_name"])
        for row in columns
        if row["is_identity"] == "YES"
    }

    assert {
        ("soc_event_inbox", "inbox_id"),
        ("soc_incident_evidence", "evidence_sequence"),
        ("soc_incident_history", "history_id"),
    } <= identity_columns

    indexes = connection.execute(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = current_schema()
        """
    ).fetchall()

    expected_indexes = {
        "idx_soc_event_inbox_pending",
        "idx_soc_event_inbox_agent_received",
        "idx_soc_event_inbox_claim_recovery",
        "idx_soc_incidents_status_updated",
        "idx_soc_incident_evidence_reference",
    }
    assert expected_indexes <= {row["indexname"] for row in indexes}

    history = connection.execute(
        """
        SELECT version, checksum, description
        FROM schema_migrations
        WHERE version = %s
        """,
        ("009-soc-storage",),
    ).fetchone()

    assert history["checksum"] == SOC_STORAGE_MIGRATION.checksum
    assert history["description"] == SOC_STORAGE_MIGRATION.description


def test_soc_storage_constraints_and_foreign_key_actions(
    postgres_environment,
):
    connection = postgres_environment
    run_migrations(connection, (SOC_STORAGE_MIGRATION,))

    constraints = connection.execute(
        """
        SELECT conname, contype, confdeltype
        FROM pg_constraint
        WHERE connamespace = current_schema()::regnamespace
        """
    ).fetchall()

    by_name = {row["conname"]: row for row in constraints}

    assert by_name["fk_soc_event_inbox_agent"]["confdeltype"] == "a"
    assert (
        by_name["fk_soc_incident_evidence_incident"]["confdeltype"] == "c"
    )
    assert (
        by_name["fk_soc_incident_history_incident"]["confdeltype"] == "c"
    )

    now = datetime.now(timezone.utc)
    fingerprint = "a" * 64
    digest = "b" * 64

    connection.execute(
        """
        INSERT INTO soc_collector_agents (
            agent_id, display_name, certificate_sha256,
            status, created_at
        ) VALUES (%s, %s, %s, 'active', %s)
        """,
        ("agent-test", "Integration test agent", fingerprint, now),
    )

    connection.execute(
        """
        INSERT INTO soc_event_inbox (
            agent_id, event_id, payload_json, payload_sha256, received_at
        ) VALUES (%s, %s, %s, %s, %s)
        """,
        ("agent-test", "event-test-1", '{"event_id":"event-test-1"}', digest, now),
    )

    with pytest.raises(psycopg.errors.UniqueViolation):
        connection.execute(
            """
            INSERT INTO soc_event_inbox (
                agent_id, event_id, payload_json,
                payload_sha256, received_at
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                "agent-test",
                "event-test-1",
                '{"event_id":"event-test-1"}',
                digest,
                now,
            ),
        )

    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            """
            INSERT INTO soc_event_inbox (
                agent_id, event_id, payload_json,
                payload_sha256, received_at, processing_status
            ) VALUES (%s, %s, %s, %s, %s, 'processing')
            """,
            (
                "agent-test",
                "event-invalid-claim",
                '{"event_id":"event-invalid-claim"}',
                digest,
                now,
            ),
        )

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        connection.execute(
            "DELETE FROM soc_collector_agents WHERE agent_id = %s",
            ("agent-test",),
        )

    connection.execute(
        """
        INSERT INTO soc_incidents (
            incident_id, title, summary, severity, status,
            created_at, updated_at
        ) VALUES (%s, %s, %s, 'warning', 'open', %s, %s)
        """,
        (
            "incident-test",
            "Integration test incident",
            "Incident used to verify SOC schema constraints.",
            now,
            now,
        ),
    )

    first_evidence = connection.execute(
        """
        INSERT INTO soc_incident_evidence (
            evidence_id, incident_id, kind, reference_id,
            description, observed_at
        ) VALUES (%s, %s, 'event', %s, %s, %s)
        RETURNING evidence_sequence
        """,
        (
            "evidence-1",
            "incident-test",
            "event-1",
            "First evidence",
            now,
        ),
    ).fetchone()

    second_evidence = connection.execute(
        """
        INSERT INTO soc_incident_evidence (
            evidence_id, incident_id, kind, reference_id,
            description, observed_at
        ) VALUES (%s, %s, 'detection', %s, %s, %s)
        RETURNING evidence_sequence
        """,
        (
            "evidence-2",
            "incident-test",
            "rule-1",
            "Second evidence",
            now,
        ),
    ).fetchone()

    assert second_evidence["evidence_sequence"] > (
        first_evidence["evidence_sequence"]
    )

    connection.execute(
        """
        INSERT INTO soc_incident_history (
            incident_id, old_status, new_status, changed_at, changed_by
        ) VALUES (%s, NULL, 'open', %s, 'system')
        """,
        ("incident-test", now),
    )

    connection.execute(
        """
        INSERT INTO soc_incident_history (
            incident_id, old_status, new_status, changed_at, changed_by
        ) VALUES (%s, 'open', 'investigating', %s, 'operator-test')
        """,
        ("incident-test", now),
    )

    connection.execute(
        "DELETE FROM soc_incidents WHERE incident_id = %s",
        ("incident-test",),
    )

    assert connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM soc_incident_evidence
        WHERE incident_id = %s
        """,
        ("incident-test",),
    ).fetchone()["count"] == 0

    assert connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM soc_incident_history
        WHERE incident_id = %s
        """,
        ("incident-test",),
    ).fetchone()["count"] == 0
