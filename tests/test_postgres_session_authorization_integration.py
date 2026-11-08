"""PostgreSQL integration tests for session-based authorization."""

import secrets
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from postgres_test_support import require_test_database_url, run_cleanup
from server.migration_runner import run_migrations
from server.migrations import MIGRATIONS
from server.postgres_app import create_postgres_app


BASE_URL = "https://localhost"


def _open_schema_connection(database_url, schema_name, application_name):
    connection = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=5,
        application_name=application_name,
    )

    try:
        connection.execute(
            sql.SQL("SET search_path TO {}").format(
                sql.Identifier(schema_name)
            )
        )
    except BaseException:
        run_cleanup((
            "close connection after search_path failure",
            connection.close,
        ))
        raise

    return connection


@pytest.fixture
def postgres_session_authorization_environment():
    database_url = require_test_database_url()

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=5,
        application_name="lums-session-authorization-test-setup",
    )

    schema_name = f"lums_session_auth_{uuid4().hex}"
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
                "Refusing session authorization tests outside the "
                "dedicated lums_integration database and "
                "lums_pg_bootstrap role."
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
            "lums-session-authorization-migrations",
        )
        run_migrations(setup, MIGRATIONS)

        suffix = uuid4().hex[:10]
        username = f"session-auth-admin-{suffix}"
        created_at = datetime.now(timezone.utc).isoformat()

        user_row = setup.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                created_at,
                role,
                enabled
            )
            VALUES (%s, %s, %s, %s, TRUE)
            RETURNING id
            """,
            (
                username,
                "not-used-by-session-integration-test",
                created_at,
                "administrator",
            ),
        ).fetchone()

        role_row = setup.execute(
            "SELECT id FROM roles WHERE role_key = %s",
            ("system-administrator",),
        ).fetchone()

        if role_row is None:
            raise RuntimeError(
                "Missing seeded role: system-administrator"
            )

        setup.execute(
            """
            INSERT INTO user_roles (
                user_id,
                role_id,
                assigned_at,
                assigned_by
            )
            VALUES (%s, %s, %s, NULL)
            """,
            (user_row["id"], role_row["id"], created_at),
        )

        def connection_factory():
            return _open_schema_connection(
                database_url,
                schema_name,
                "lums-session-authorization-request",
            )

        app = create_postgres_app({
            "SECRET_KEY": "test-only-session-authorization-secret",
            "TESTING": True,
            "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
        })

        yield {
            "app": app,
            "client": app.test_client(),
            "connection_factory": connection_factory,
            "user_id": user_row["id"],
            "username": username,
            "schema_name": schema_name,
        }

    finally:
        run_cleanup(
            (
                "close setup connection",
                lambda: setup.close() if setup is not None else None,
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


def _login_user(environment):
    client = environment["client"]

    with client.session_transaction(base_url=BASE_URL) as flask_session:
        flask_session.clear()
        flask_session.update({
            "user_id": int(environment["user_id"]),
            "username": environment["username"],
            "csrf_token": secrets.token_urlsafe(32),
        })
        flask_session.permanent = True


def test_existing_session_is_rejected_after_user_is_disabled(
    postgres_session_authorization_environment,
):
    environment = postgres_session_authorization_environment
    _login_user(environment)

    database = environment["connection_factory"]()
    try:
        database.execute(
            "UPDATE users SET enabled = FALSE WHERE id = %s",
            (environment["user_id"],),
        )
    finally:
        database.close()

    response = environment["client"].get(
        "/api/clients",
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "authentication_required"
    }

    with environment["client"].session_transaction(
        base_url=BASE_URL
    ) as flask_session:
        assert "user_id" not in flask_session


def test_existing_session_uses_current_permission_overrides(
    postgres_session_authorization_environment,
):
    environment = postgres_session_authorization_environment
    _login_user(environment)

    database = environment["connection_factory"]()
    try:
        database.execute(
            """
            INSERT INTO user_permission_overrides (
                user_id,
                permission,
                effect,
                changed_at,
                changed_by
            )
            VALUES (%s, %s, 'deny', %s, NULL)
            """,
            (
                environment["user_id"],
                "clients.view",
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    finally:
        database.close()

    response = environment["client"].get(
        "/api/clients",
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required"
    }

    # A permission denial must not destroy an otherwise valid session.
    with environment["client"].session_transaction(
        base_url=BASE_URL
    ) as flask_session:
        assert flask_session["user_id"] == environment["user_id"]


def test_authorization_connection_failure_returns_503(
    postgres_session_authorization_environment,
):
    environment = postgres_session_authorization_environment
    _login_user(environment)

    def fail_to_connect():
        raise RuntimeError(
            "simulated PostgreSQL authorization connection failure"
        )

    environment["app"].config[
        "LUMS_POSTGRES_GET_CONNECTION"
    ] = fail_to_connect

    response = environment["client"].get(
        "/api/clients",
        base_url=BASE_URL,
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "authorization_state_unavailable"
    }
    assert "simulated PostgreSQL" not in response.get_data(as_text=True)
