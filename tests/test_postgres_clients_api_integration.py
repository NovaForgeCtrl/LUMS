"""Real PostgreSQL integration tests for client management and agent API."""

import os
import secrets
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from server.migration_runner import run_migrations
from server.migrations import MIGRATIONS
from server.postgres_app import create_postgres_app
from server.security import hash_client_token


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
def postgres_clients_api_environment():
    database_url = os.environ.get("LUMS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("LUMS_TEST_DATABASE_URL is not configured")

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=5,
        application_name="lums-clients-api-test-setup",
    )

    schema_name = f"lums_clients_api_{uuid4().hex}"
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
                "Refusing client API tests outside the dedicated "
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
            "lums-clients-api-migrations",
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

        suffix = uuid4().hex[:10]
        admin_id = add_user(
            f"clients-admin-{suffix}",
            "administrator",
            "system-administrator",
        )
        viewer_id = add_user(
            f"clients-viewer-{suffix}",
            "viewer",
            "system-viewer",
        )

        def connection_factory():
            return _open_schema_connection(
                database_url,
                schema_name,
                "lums-clients-api-request",
            )

        app = create_postgres_app({
            "SECRET_KEY": "test-only-clients-integration-secret",
            "TESTING": True,
            "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
        })

        yield {
            "client": app.test_client(),
            "connection_factory": connection_factory,
            "admin_id": admin_id,
            "viewer_id": viewer_id,
            "admin_name": f"clients-admin-{suffix}",
            "viewer_name": f"clients-viewer-{suffix}",
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
        flask_session.clear()
        flask_session.update({
            "user_id": int(user_id),
            "username": username,
            "csrf_token": secrets.token_urlsafe(32),
        })
        flask_session.permanent = True
        csrf_token = flask_session["csrf_token"]

    return {"X-CSRF-Token": csrf_token}


def _read_rows(environment, statement, params=()):
    connection = environment["connection_factory"]()
    try:
        return connection.execute(statement, params).fetchall()
    finally:
        connection.close()


def _create_client(environment, ip="192.0.2.41", hostname="agent-01"):
    headers = _login_client(
        environment["client"],
        environment["admin_id"],
        environment["admin_name"],
    )
    return environment["client"].post(
        "/api/clients",
        json={
            "hostname": hostname,
            "ip": ip,
            "os": "Debian GNU/Linux",
            "kernel": "6.1.0",
            "architecture": "x86_64",
            "agent_version": "1.0.0",
        },
        headers=headers,
        base_url=BASE_URL,
    )


def _valid_report(hostname="agent-01", ip="192.0.2.41"):
    return {
        "hostname": hostname,
        "ip": ip,
        "os": "Debian GNU/Linux",
        "kernel": "6.1.0",
        "architecture": "x86_64",
        "agent_version": "1.0.0",
        "idle": False,
        "idle_seconds": 0,
        "idle_threshold_seconds": 300,
        "idle_source": "unknown",
        "idle_supported": False,
        "updates": [{
            "package": "curl",
            "installed_version": "8.0",
            "available_version": "8.1",
        }],
        "packages": {
            "curl": "8.0",
            "bash": "5.2",
        },
    }


def test_client_lifecycle_report_rotation_and_disable(
    postgres_clients_api_environment,
):
    environment = postgres_clients_api_environment
    client = environment["client"]

    created = _create_client(environment)
    assert created.status_code == 201

    created_data = created.get_json()
    client_id = created_data["client"]["id"]
    original_token = created_data["token"]

    stored = _read_rows(
        environment,
        """
        SELECT id, hostname, ip, client_token_hash, token_created_at
        FROM clients
        WHERE id = %s
        """,
        (client_id,),
    )
    assert len(stored) == 1
    assert stored[0]["client_token_hash"] == hash_client_token(
        original_token
    )
    assert stored[0]["client_token_hash"] != original_token
    assert stored[0]["token_created_at"] is not None

    original_headers = {
        "Authorization": f"Bearer {original_token}",
    }

    identity = client.get(
        "/api/client/me",
        headers=original_headers,
        base_url=BASE_URL,
    )
    assert identity.status_code == 200
    assert identity.get_json()["id"] == client_id

    report = client.post(
        "/api/report",
        json=_valid_report(),
        headers=original_headers,
        base_url=BASE_URL,
    )
    assert report.status_code == 200
    assert report.get_json() == {"status": "received"}

    listed = client.get(
        "/api/clients",
        headers=_login_client(
            client,
            environment["admin_id"],
            environment["admin_name"],
        ),
        base_url=BASE_URL,
    )
    assert listed.status_code == 200
    listed_client = next(
        item for item in listed.get_json()
        if item["id"] == client_id
    )
    assert listed_client["package_count"] == 2
    assert listed_client["update_count"] == 1

    details = client.get(
        f"/api/clients/{client_id}",
        base_url=BASE_URL,
    )
    assert details.status_code == 200
    assert details.get_json()["hostname"] == "agent-01"

    updates = client.get(
        f"/api/clients/{client_id}/updates",
        base_url=BASE_URL,
    )
    assert updates.status_code == 200
    assert [row["package"] for row in updates.get_json()] == ["curl"]

    packages = client.get(
        f"/api/clients/{client_id}/packages",
        base_url=BASE_URL,
    )
    assert packages.status_code == 200
    assert {row["package"] for row in packages.get_json()} == {
        "curl",
        "bash",
    }

    admin_headers = _login_client(
        client,
        environment["admin_id"],
        environment["admin_name"],
    )
    rotated = client.post(
        f"/api/clients/{client_id}/token/rotate",
        headers=admin_headers,
        base_url=BASE_URL,
    )
    assert rotated.status_code == 200

    new_token = rotated.get_json()["token"]
    assert new_token != original_token

    old_identity = client.get(
        "/api/client/me",
        headers=original_headers,
        base_url=BASE_URL,
    )
    assert old_identity.status_code == 401

    new_headers = {"Authorization": f"Bearer {new_token}"}
    new_identity = client.get(
        "/api/client/me",
        headers=new_headers,
        base_url=BASE_URL,
    )
    assert new_identity.status_code == 200

    connection = environment["connection_factory"]()
    try:
        job = connection.execute(
            """
            INSERT INTO update_jobs (
                client_id, status, created_at, action
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (
                client_id,
                "completed",
                datetime.now(timezone.utc),
                "UPDATE_PACKAGE",
            ),
        ).fetchone()

        connection.execute(
            """
            INSERT INTO update_history (
                client_id, job_id, status, package_count,
                successful_count, failed_count
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (client_id, job["id"], "completed", 1, 1, 0),
        )
    finally:
        connection.close()

    admin_headers = _login_client(
        client,
        environment["admin_id"],
        environment["admin_name"],
    )
    disabled = client.delete(
        f"/api/clients/{client_id}",
        headers=admin_headers,
        base_url=BASE_URL,
    )
    assert disabled.status_code == 200
    assert disabled.get_json()["status"] == "disabled"

    disabled_rows = _read_rows(
        environment,
        """
        SELECT enabled, token_revoked_at
        FROM clients
        WHERE id = %s
        """,
        (client_id,),
    )
    assert disabled_rows[0]["enabled"] is False
    assert disabled_rows[0]["token_revoked_at"] is not None

    assert _read_rows(
        environment,
        "SELECT id FROM available_updates WHERE client_id = %s",
        (client_id,),
    ) == []
    assert _read_rows(
        environment,
        "SELECT id FROM installed_packages WHERE client_id = %s",
        (client_id,),
    ) == []

    assert len(_read_rows(
        environment,
        "SELECT id FROM update_jobs WHERE client_id = %s",
        (client_id,),
    )) == 1
    assert len(_read_rows(
        environment,
        "SELECT id FROM update_history WHERE client_id = %s",
        (client_id,),
    )) == 1

    rejected = client.get(
        "/api/client/me",
        headers=new_headers,
        base_url=BASE_URL,
    )
    assert rejected.status_code == 401

    audit = _read_rows(
        environment,
        """
        SELECT action, target, result
        FROM audit_log
        WHERE actor_id = %s
        ORDER BY id
        """,
        (str(environment["admin_id"]),),
    )
    assert {row["action"] for row in audit} == {
        "client.create",
        "client.token.rotate",
        "client.disable",
    }
    assert all(row["result"] == "success" for row in audit)


def test_duplicate_ip_permission_and_csrf_are_enforced(
    postgres_clients_api_environment,
):
    environment = postgres_clients_api_environment
    client = environment["client"]

    created = _create_client(environment)
    assert created.status_code == 201

    duplicate = _create_client(
        environment,
        ip="192.0.2.41",
        hostname="agent-duplicate",
    )
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"] == "client_already_exists"

    viewer_headers = _login_client(
        client,
        environment["viewer_id"],
        environment["viewer_name"],
    )
    denied = client.post(
        "/api/clients",
        json={
            "hostname": "agent-forbidden",
            "ip": "192.0.2.42",
        },
        headers=viewer_headers,
        base_url=BASE_URL,
    )
    assert denied.status_code == 403

    _login_client(
        client,
        environment["admin_id"],
        environment["admin_name"],
    )
    rejected_csrf = client.post(
        "/api/clients",
        json={
            "hostname": "agent-no-csrf",
            "ip": "192.0.2.43",
        },
        base_url=BASE_URL,
    )
    assert rejected_csrf.status_code == 400

    clients = _read_rows(
        environment,
        "SELECT id FROM clients",
    )
    assert len(clients) == 1

    audit = _read_rows(
        environment,
        "SELECT action FROM audit_log",
    )
    assert [row["action"] for row in audit] == ["client.create"]


def test_report_unique_violation_rolls_back_all_client_changes(
    postgres_clients_api_environment,
):
    environment = postgres_clients_api_environment
    client = environment["client"]

    created = _create_client(environment)
    assert created.status_code == 201

    client_id = created.get_json()["client"]["id"]
    token = created.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    baseline = client.post(
        "/api/report",
        json=_valid_report(),
        headers=headers,
        base_url=BASE_URL,
    )
    assert baseline.status_code == 200

    failing_report = _valid_report(
        hostname="changed-before-rollback",
        ip="192.0.2.99",
    )
    failing_report["updates"] = [
        {
            "package": "curl",
            "installed_version": "8.0",
            "available_version": "8.1",
        },
        {
            "package": "curl",
            "installed_version": "8.0",
            "available_version": "8.2",
        },
    ]
    failing_report["packages"] = {"nano": "7.0"}

    failed = client.post(
        "/api/report",
        json=failing_report,
        headers=headers,
        base_url=BASE_URL,
    )
    assert failed.status_code == 500

    stored_client = _read_rows(
        environment,
        "SELECT hostname, ip FROM clients WHERE id = %s",
        (client_id,),
    )
    assert stored_client == [{
        "hostname": "agent-01",
        "ip": "192.0.2.41",
    }]

    stored_updates = _read_rows(
        environment,
        """
        SELECT package, installed_version, available_version
        FROM available_updates
        WHERE client_id = %s
        ORDER BY package
        """,
        (client_id,),
    )
    assert stored_updates == [{
        "package": "curl",
        "installed_version": "8.0",
        "available_version": "8.1",
    }]

    stored_packages = _read_rows(
        environment,
        """
        SELECT package, version
        FROM installed_packages
        WHERE client_id = %s
        ORDER BY package
        """,
        (client_id,),
    )
    assert stored_packages == [
        {"package": "bash", "version": "5.2"},
        {"package": "curl", "version": "8.0"},
    ]
