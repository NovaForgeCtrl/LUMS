"""PostgreSQL integration test for migration 008-alerts."""

from uuid import uuid4

import psycopg
from postgres_test_support import require_test_database_url, run_cleanup
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from server.migration_runner import run_migrations
from server.migrations.alerts import ALERTS_MIGRATION


@pytest.fixture
def postgres_environment():
    database_url = require_test_database_url()

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-alerts-migration-setup",
    )

    connection = None
    schema_name = f"lums_alerts_test_{uuid4().hex}"
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
            application_name="lums-alerts-migration-test",
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


def test_alerts_migration_creates_schema_and_is_idempotent(
    postgres_environment,
):
    connection = postgres_environment

    first = run_migrations(connection, (ALERTS_MIGRATION,))
    second = run_migrations(connection, (ALERTS_MIGRATION,))

    assert first.applied == ("008-alerts",)
    assert second.applied == ()
    assert second.already_applied == ("008-alerts",)

    expected_tables = {
        "alert_rules",
        "alerts",
        "alert_history",
        "notification_integrations",
        "alert_notifications_log",
        "schema_migrations",
    }

    rows = connection.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_type = 'BASE TABLE'
        """
    ).fetchall()

    assert expected_tables <= {row["table_name"] for row in rows}

    rows = connection.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND data_type = 'jsonb'
        """
    ).fetchall()

    actual_jsonb = {
        (row["table_name"], row["column_name"])
        for row in rows
    }

    assert {
        ("alert_rules", "threshold"),
        ("alert_rules", "escalation_path"),
        ("alerts", "metadata"),
        ("notification_integrations", "config"),
    } <= actual_jsonb

    rows = connection.execute(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = current_schema()
        """
    ).fetchall()

    assert {
        "idx_alerts_status_triggered_at",
        "idx_alerts_triggered_at",
        "idx_alert_history_alert_id_id",
        "idx_alert_notifications_alert_sent",
        "idx_alert_notifications_integration_sent",
    } <= {row["indexname"] for row in rows}

    history = connection.execute(
        """
        SELECT version, checksum, description
        FROM schema_migrations
        WHERE version = %s
        """,
        ("008-alerts",),
    ).fetchone()

    assert history["checksum"] == ALERTS_MIGRATION.checksum
    assert history["description"] == ALERTS_MIGRATION.description

    expected_constraints = {
        "ck_alert_rules_severity",
        "ck_alert_rules_escalation_path_array",
        "ck_alerts_severity",
        "ck_alerts_status",
        "ck_alerts_escalation_count",
        "ck_alert_history_status",
        "fk_alerts_rule",
        "fk_alert_history_alert",
        "fk_alert_notifications_alert",
        "fk_alert_notifications_integration",
    }

    rows = connection.execute(
        """
        SELECT conname
        FROM pg_constraint
        WHERE connamespace = current_schema()::regnamespace
        """
    ).fetchall()

    assert expected_constraints <= {
        row["conname"] for row in rows
    }

    rows = connection.execute(
        """
        SELECT constraint_name, delete_rule
        FROM information_schema.referential_constraints
        WHERE constraint_schema = current_schema()
        """
    ).fetchall()

    assert len(rows) == 4
    assert all(row["delete_rule"] == "NO ACTION" for row in rows)

    identity = connection.execute(
        """
        SELECT is_identity, data_type
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'alert_history'
          AND column_name = 'id'
        """
    ).fetchone()

    assert identity["is_identity"] == "YES"
    assert identity["data_type"] == "bigint"
