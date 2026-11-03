"""Real PostgreSQL integration tests for the alerts API."""

import os
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from server.migration_runner import run_migrations
from server.migrations import MIGRATIONS
from server.postgres_app import create_postgres_app
from server.security import login_user


BASE_URL = "https://localhost"


def _open_schema_connection(database_url, schema_name, application_name):
    connection = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=5,
        application_name=application_name,
    )
    connection.execute(
        sql.SQL("SET search_path TO {}").format(
            sql.Identifier(schema_name)
        )
    )
    return connection


@pytest.fixture
def postgres_alerts_api_environment():
    database_url = os.environ.get("LUMS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("LUMS_TEST_DATABASE_URL is not configured")

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-alerts-api-test-setup",
    )

    schema_name = f"lums_alerts_api_{uuid4().hex}"
    schema_created = False
    setup = None

    try:
        identity = admin.execute(
            "SELECT current_database(), current_user"
        ).fetchone()

        if (
            identity["current_database"] != "lums_integration"
            or identity["current_user"] != "lums_pg_bootstrap"
        ):
            pytest.fail(
                "Refusing alerts API tests outside the dedicated "
                "lums_integration database and lums_pg_bootstrap role."
            )

        admin.execute(
            sql.SQL("CREATE SCHEMA {}").format(
                sql.Identifier(schema_name)
            )
        )
        schema_created = True

        setup = _open_schema_connection(
            database_url,
            schema_name,
            "lums-alerts-api-migrations",
        )
        run_migrations(setup, MIGRATIONS)

        def add_user(username, role, role_key):
            created_at = datetime.now(timezone.utc).isoformat()

            row = setup.execute(
                """
                INSERT INTO users (
                    username, password_hash, created_at, role
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (
                    username,
                    "not-used-by-session-integration-test",
                    created_at,
                    role,
                ),
            ).fetchone()

            role_row = setup.execute(
                "SELECT id FROM roles WHERE role_key = %s",
                (role_key,),
            ).fetchone()

            if role_row is None:
                raise RuntimeError(f"Missing seeded role: {role_key}")

            setup.execute(
                """
                INSERT INTO user_roles (
                    user_id, role_id, assigned_at, assigned_by
                )
                VALUES (%s, %s, %s, NULL)
                """,
                (row["id"], role_row["id"], created_at),
            )
            return row["id"]

        admin_id = add_user(
            "alerts-integration-admin",
            "administrator",
            "system-administrator",
        )
        viewer_id = add_user(
            "alerts-integration-viewer",
            "viewer",
            "system-viewer",
        )

        def connection_factory():
            return _open_schema_connection(
                database_url,
                schema_name,
                "lums-alerts-api-request",
            )

        app = create_postgres_app({
            "SECRET_KEY": "test-only-alerts-integration-secret",
            "TESTING": True,
            "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
        })

        yield {
            "client": app.test_client(),
            "connection_factory": connection_factory,
            "admin_id": admin_id,
            "viewer_id": viewer_id,
            "schema_name": schema_name,
        }

    finally:
        if setup is not None:
            setup.close()

        if schema_created:
            admin.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema_name)
                )
            )

        admin.close()


def _login_client(client, user_id, username):
    with client.session_transaction(base_url=BASE_URL) as flask_session:
        login_user(user_id, username)
        csrf_token = flask_session["csrf_token"]

    return {"X-CSRF-Token": csrf_token}


def _valid_rule_payload(name):
    return {
        "name": name,
        "description": "PostgreSQL integration test rule",
        "condition": "cpu_usage",
        "threshold": {
            "operator": ">",
            "value": 90,
        },
        "severity": "warning",
        "enabled": True,
        "escalation_path": ["operator", "administrator"],
        "group_similar": True,
        "deduplicate": True,
    }


def _read_rows(environment, statement, params=()):
    connection = environment["connection_factory"]()
    try:
        return connection.execute(statement, params).fetchall()
    finally:
        connection.close()


def test_alerts_api_lifecycle_persists_history_and_audit(
    postgres_alerts_api_environment,
):
    environment = postgres_alerts_api_environment
    client = environment["client"]
    admin_id = environment["admin_id"]

    headers = _login_client(
        client,
        admin_id,
        "alerts-integration-admin",
    )

    created = client.post(
        "/alerts/rules",
        json=_valid_rule_payload("Integration CPU rule"),
        headers=headers,
        base_url=BASE_URL,
    )
    assert created.status_code == 201
    rule_id = created.get_json()["rule"]["rule_id"]

    updated = client.put(
        f"/alerts/rules/{rule_id}",
        json={
            "name": "Integration CPU rule updated",
            "description": "Updated by integration test",
        },
        headers=headers,
        base_url=BASE_URL,
    )
    assert updated.status_code == 200
    assert updated.get_json()["rule"]["name"] == (
        "Integration CPU rule updated"
    )

    triggered = client.post(
        "/alerts/trigger",
        json={
            "rule_id": rule_id,
            "source": "integration-test",
            "message": "Synthetic PostgreSQL alert",
            "metadata": {"test": True, "component": "alerts"},
        },
        headers=headers,
        base_url=BASE_URL,
    )
    assert triggered.status_code == 201
    alert_id = triggered.get_json()["alert"]["alert_id"]
    assert triggered.get_json()["alert"]["status"] == "triggered"

    current = client.get(
        "/alerts/current",
        base_url=BASE_URL,
    )
    assert current.status_code == 200
    assert current.get_json()["count"] == 1

    escalated = client.post(
        f"/alerts/{alert_id}/escalate",
        headers=headers,
        base_url=BASE_URL,
    )
    assert escalated.status_code == 200
    assert escalated.get_json()["escalation_count"] == 1

    acknowledged = client.post(
        f"/alerts/{alert_id}/acknowledge",
        headers=headers,
        base_url=BASE_URL,
    )
    assert acknowledged.status_code == 200

    resolved = client.post(
        f"/alerts/{alert_id}/resolve",
        headers=headers,
        base_url=BASE_URL,
    )
    assert resolved.status_code == 200

    history_response = client.get(
        "/alerts/history?limit=10",
        base_url=BASE_URL,
    )
    assert history_response.status_code == 200
    assert history_response.get_json()["count"] == 1

    current_after_resolution = client.get(
        "/alerts/current",
        base_url=BASE_URL,
    )
    assert current_after_resolution.status_code == 200
    assert current_after_resolution.get_json()["count"] == 0

    temporary_rule = client.post(
        "/alerts/rules",
        json=_valid_rule_payload("Temporary delete rule"),
        headers=headers,
        base_url=BASE_URL,
    )
    assert temporary_rule.status_code == 201
    temporary_rule_id = temporary_rule.get_json()["rule"]["rule_id"]

    deleted = client.delete(
        f"/alerts/rules/{temporary_rule_id}",
        headers=headers,
        base_url=BASE_URL,
    )
    assert deleted.status_code == 200

    alert_rows = _read_rows(
        environment,
        """
        SELECT status, escalation_count, metadata
        FROM alerts
        WHERE alert_id = %s
        """,
        (alert_id,),
    )
    assert len(alert_rows) == 1
    assert alert_rows[0]["status"] == "resolved"
    assert alert_rows[0]["escalation_count"] == 1
    assert alert_rows[0]["metadata"]["test"] is True
    assert alert_rows[0]["metadata"]["acknowledged_by"] == str(admin_id)

    history_rows = _read_rows(
        environment,
        """
        SELECT status, changed_by
        FROM alert_history
        WHERE alert_id = %s
        ORDER BY id
        """,
        (alert_id,),
    )
    assert [row["status"] for row in history_rows] == [
        "escalated",
        "acknowledged",
        "resolved",
    ]
    assert all(row["changed_by"] == str(admin_id) for row in history_rows)

    audit_rows = _read_rows(
        environment,
        """
        SELECT action, target, actor_id, result
        FROM audit_log
        WHERE actor_id = %s
        ORDER BY id
        """,
        (str(admin_id),),
    )
    assert {row["action"] for row in audit_rows} == {
        "alerts.rule.create",
        "alerts.rule.update",
        "alerts.trigger",
        "alerts.escalate",
        "alerts.acknowledge",
        "alerts.resolve",
        "alerts.rule.delete",
    }
    assert all(row["result"] == "success" for row in audit_rows)

    rule_rows = _read_rows(
        environment,
        """
        SELECT rule_id, name
        FROM alert_rules
        WHERE rule_id IN (%s, %s)
        """,
        (rule_id, temporary_rule_id),
    )
    assert rule_rows == [
        {
            "rule_id": rule_id,
            "name": "Integration CPU rule updated",
        }
    ]


def test_alerts_api_enforces_permissions_and_csrf(
    postgres_alerts_api_environment,
):
    environment = postgres_alerts_api_environment
    client = environment["client"]

    viewer_headers = _login_client(
        client,
        environment["viewer_id"],
        "alerts-integration-viewer",
    )

    denied_view = client.get(
        "/alerts/rules",
        base_url=BASE_URL,
    )
    assert denied_view.status_code == 403

    denied_manage = client.post(
        "/alerts/rules",
        json=_valid_rule_payload("Viewer must not create this"),
        headers=viewer_headers,
        base_url=BASE_URL,
    )
    assert denied_manage.status_code == 403

    _login_client(
        client,
        environment["admin_id"],
        "alerts-integration-admin",
    )

    rejected_csrf = client.post(
        "/alerts/rules",
        json=_valid_rule_payload("CSRF must reject this"),
        base_url=BASE_URL,
    )
    assert rejected_csrf.status_code == 400

    rules = _read_rows(
        environment,
        "SELECT rule_id FROM alert_rules",
    )
    audit = _read_rows(
        environment,
        "SELECT id FROM audit_log",
    )
    assert rules == []
    assert audit == []
