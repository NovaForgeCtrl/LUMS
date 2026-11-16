"""Unit tests for the standalone PostgreSQL SOC collector application."""

import pytest

from flask import g

from server.soc.postgres_collector_api import (
    _postgres_collector_connection,
)
from server.soc.postgres_collector_app import (
    create_postgres_collector_app,
)


def test_postgres_collector_app_registers_only_the_ingestion_route():
    app = create_postgres_collector_app()

    rules = list(app.url_map.iter_rules())

    assert len(rules) == 1
    assert rules[0].rule == "/alerts/api/collector/v1/events"
    assert "POST" in rules[0].methods


def test_postgres_collector_app_has_no_session_secret():
    app = create_postgres_collector_app()

    assert app.secret_key is None


def test_postgres_collector_app_is_disabled_by_default():
    app = create_postgres_collector_app()
    client = app.test_client()

    response = client.post(
        "/alerts/api/collector/v1/events",
        json={"events": []},
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "soc_collector_disabled"
    }


def test_disabled_collector_does_not_call_identity_or_database_provider():
    calls = []

    def identity_provider():
        calls.append("identity")
        return "a" * 64

    def connection_factory():
        calls.append("database")
        raise AssertionError("Database must not be accessed while disabled")

    app = create_postgres_collector_app({
        "LUMS_COLLECTOR_IDENTITY_PROVIDER": identity_provider,
        "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
    })

    response = app.test_client().post(
        "/alerts/api/collector/v1/events",
        json={"events": []},
    )

    assert response.status_code == 503
    assert calls == []


def test_enabled_collector_without_identity_provider_fails_closed():
    app = create_postgres_collector_app({
        "LUMS_SOC_COLLECTOR_ENABLED": True,
    })

    response = app.test_client().post(
        "/alerts/api/collector/v1/events",
        json={"events": []},
        headers={
            "X-LUMS-Verified-Client-Cert": "A" * 128,
        },
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "collector_identity_required"
    }


def test_identity_provider_exception_fails_closed():
    def failing_provider():
        raise RuntimeError("identity provider unavailable")

    app = create_postgres_collector_app({
        "LUMS_SOC_COLLECTOR_ENABLED": True,
        "LUMS_COLLECTOR_IDENTITY_PROVIDER": failing_provider,
    })

    response = app.test_client().post(
        "/alerts/api/collector/v1/events",
        json={"events": []},
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "collector_identity_required"
    }


def test_invalid_identity_provider_output_fails_closed():
    for fingerprint in (
        None,
        "",
        "a" * 63,
        "g" * 64,
        "a" * 64 + "\n",
        123,
    ):
        app = create_postgres_collector_app({
            "LUMS_SOC_COLLECTOR_ENABLED": True,
            "LUMS_COLLECTOR_IDENTITY_PROVIDER": (
                lambda value=fingerprint: value
            ),
        })

        response = app.test_client().post(
            "/alerts/api/collector/v1/events",
            json={"events": []},
        )

        assert response.status_code == 401
        assert response.get_json() == {
            "error": "collector_identity_required"
        }


def test_postgres_collector_app_does_not_expose_ui_routes():
    app = create_postgres_collector_app()
    client = app.test_client()

    assert client.get("/alerts/").status_code == 404
    assert client.get("/soc/").status_code == 404


def test_postgres_collector_app_rejects_get_on_ingestion_endpoint():
    app = create_postgres_collector_app()

    response = app.test_client().get(
        "/alerts/api/collector/v1/events"
    )

    assert response.status_code == 405


def test_postgres_collector_connection_is_closed_after_request():
    class FakeConnection:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    connection = FakeConnection()

    app = create_postgres_collector_app({
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": lambda: connection,
    })

    def open_connection():
        assert _postgres_collector_connection() is connection
        assert _postgres_collector_connection() is connection
        return "ok"

    app.add_url_rule(
        "/test-postgres-connection-lifecycle",
        view_func=open_connection,
        methods=["GET"],
    )

    response = app.test_client().get(
        "/test-postgres-connection-lifecycle"
    )

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "ok"
    assert connection.closed is True

@pytest.fixture
def postgres_collector_http_environment():
    """Create an isolated PostgreSQL schema and a restricted collector login."""
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from psycopg.rows import dict_row
    from secrets import token_urlsafe
    from uuid import uuid4

    from postgres_test_support import require_test_database_url, run_cleanup
    from server.migration_runner import run_migrations
    from server.migrations.soc_storage import SOC_STORAGE_MIGRATION
    from server.soc.postgres_collector_app import (
        create_postgres_collector_app,
    )

    database_url = require_test_database_url()
    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-pg-collector-http-setup",
    )

    schema_name = f"lums_soc_collector_http_{uuid4().hex}"
    schema_created = False
    connection = None

    privilege_role_name = f"lums_soc_collector_http_privs_{uuid4().hex}"
    login_role_name = f"lums_soc_collector_http_login_{uuid4().hex}"
    role_password = token_urlsafe(32)

    privilege_role_created = False
    login_role_created = False
    membership_created = False

    try:
        identity = admin.execute(
            "SELECT current_database(), current_user"
        ).fetchone()

        if (
            identity["current_database"] != "lums_integration"
            or identity["current_user"] != "lums_pg_bootstrap"
        ):
            pytest.fail(
                "Refusing HTTP integration tests outside "
                "the dedicated integration database."
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
            application_name="lums-pg-collector-http-admin",
        )
        connection.execute(
            sql.SQL("SET search_path TO {}").format(
                sql.Identifier(schema_name)
            )
        )
        run_migrations(connection, (SOC_STORAGE_MIGRATION,))

        database_name = identity["current_database"]

        admin.execute(
            sql.SQL(
                """
                CREATE ROLE {} NOLOGIN NOINHERIT
                NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS
                """
            ).format(sql.Identifier(privilege_role_name))
        )
        privilege_role_created = True

        admin.execute(
            sql.SQL(
                """
                CREATE ROLE {} LOGIN PASSWORD {}
                INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS
                """
            ).format(
                sql.Identifier(login_role_name),
                sql.Literal(role_password),
            )
        )
        login_role_created = True

        admin.execute(
            sql.SQL(
                "GRANT {} TO {} WITH INHERIT TRUE, SET FALSE"
            ).format(
                sql.Identifier(privilege_role_name),
                sql.Identifier(login_role_name),
            )
        )
        membership_created = True

        admin.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database_name),
                sql.Identifier(privilege_role_name),
            )
        )

        admin.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(schema_name),
                sql.Identifier(privilege_role_name),
            )
        )

        column_grants = (
            (
                "soc_collector_agents",
                "SELECT",
                (
                    "agent_id",
                    "display_name",
                    "certificate_sha256",
                    "status",
                    "created_at",
                ),
            ),
            (
                "soc_event_inbox",
                "SELECT",
                (
                    "inbox_id",
                    "agent_id",
                    "event_id",
                    "payload_sha256",
                ),
            ),
            (
                "soc_event_inbox",
                "INSERT",
                (
                    "agent_id",
                    "event_id",
                    "payload_json",
                    "payload_sha256",
                    "received_at",
                ),
            ),
        )

        for table, privilege, columns in column_grants:
            admin.execute(
                sql.SQL("GRANT {} ({}) ON TABLE {}.{} TO {}").format(
                    sql.SQL(privilege),
                    sql.SQL(", ").join(
                        sql.Identifier(column) for column in columns
                    ),
                    sql.Identifier(schema_name),
                    sql.Identifier(table),
                    sql.Identifier(privilege_role_name),
                )
            )

        limited_dsn = make_conninfo(
            database_url,
            user=login_role_name,
            password=role_password,
            options=f"-csearch_path={schema_name}",
            application_name="lums-pg-collector-http-limited",
        )

        identity_state = {"fingerprint": "a" * 64}

        connection_identities = []

        def open_limited_connection():
            limited = psycopg.connect(
                limited_dsn,
                autocommit=True,
                row_factory=dict_row,
                application_name="lums-pg-collector-http-request",
            )
            try:
                identity = limited.execute(
                    "SELECT current_user, session_user"
                ).fetchone()
                expected = {
                    "current_user": login_role_name,
                    "session_user": login_role_name,
                }
                if identity != expected:
                    raise AssertionError(
                        "HTTP collector connection did not use "
                        "its restricted login"
                    )
                connection_identities.append(identity)
                return limited
            except Exception:
                limited.close()
                raise

        app = create_postgres_collector_app({
            "TESTING": True,
            "LUMS_SOC_COLLECTOR_ENABLED": True,
            "LUMS_COLLECTOR_IDENTITY_PROVIDER": (
                lambda: identity_state["fingerprint"]
            ),
            "LUMS_POSTGRES_GET_CONNECTION": open_limited_connection,
        })

        yield {
            "admin": connection,
            "client": app.test_client(),
            "identity": identity_state,
            "schema": schema_name,
            "login_role": login_role_name,
            "connection_identities": connection_identities,
        }

    finally:
        if connection is not None:
            connection.close()

        if membership_created:
            admin.execute(
                sql.SQL("REVOKE {} FROM {}").format(
                    sql.Identifier(privilege_role_name),
                    sql.Identifier(login_role_name),
                )
            )

        if login_role_created:
            admin.execute(
                sql.SQL("DROP OWNED BY {}").format(
                    sql.Identifier(login_role_name)
                )
            )

        if privilege_role_created:
            admin.execute(
                sql.SQL("DROP OWNED BY {}").format(
                    sql.Identifier(privilege_role_name)
                )
            )

        if login_role_created:
            admin.execute(
                sql.SQL("DROP ROLE {}").format(
                    sql.Identifier(login_role_name)
                )
            )

        if privilege_role_created:
            admin.execute(
                sql.SQL("DROP ROLE {}").format(
                    sql.Identifier(privilege_role_name)
                )
            )

        run_cleanup(
            (
                "drop collector HTTP test schema",
                lambda: admin.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema_name)
                    )
                ) if schema_created else None,
            ),
            ("close collector HTTP admin connection", admin.close),
        )


def _postgres_http_collector_event(event_id, username="tester"):
    from datetime import datetime, timezone

    return {
        "event_id": event_id,
        "source": "linux-test-01",
        "event_type": "auth.failure",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fields": {"username": username},
    }


def test_postgres_collector_http_ingests_with_limited_login(
    postgres_collector_http_environment,
):
    from server.soc.postgres_collector_store import PostgresCollectorStore

    env = postgres_collector_http_environment
    store = PostgresCollectorStore(env["admin"])

    store.register_agent(
        "linux-http-01",
        "HTTP integration test collector",
        env["identity"]["fingerprint"],
    )

    event_id = "linux01:http:" + __import__("uuid").uuid4().hex
    event = _postgres_http_collector_event(event_id)

    first = env["client"].post(
        "/alerts/api/collector/v1/events",
        json={"events": [event]},
    )
    replay = env["client"].post(
        "/alerts/api/collector/v1/events",
        json={"events": [event]},
    )

    assert first.status_code == 202
    assert first.get_json()["status"] == "accepted"
    assert first.get_json()["accepted"] == 1
    assert first.get_json()["duplicates"] == 0

    assert replay.status_code == 202
    assert replay.get_json()["accepted"] == 0
    assert replay.get_json()["duplicates"] == 1

    row = env["admin"].execute(
        """
        SELECT event_id, payload_json
        FROM soc_event_inbox
        WHERE agent_id = %s AND event_id = %s
        """,
        ("linux-http-01", event_id),
    ).fetchone()

    assert row is not None
    assert row["event_id"] == event_id
    assert '"username":"tester"' in row["payload_json"]

    assert len(env["connection_identities"]) == 2
    assert all(
        identity == {
            "current_user": env["login_role"],
            "session_user": env["login_role"],
        }
        for identity in env["connection_identities"]
    )


def test_postgres_collector_http_rejects_conflicts(
    postgres_collector_http_environment,
):
    from server.soc.postgres_collector_store import PostgresCollectorStore

    env = postgres_collector_http_environment
    PostgresCollectorStore(env["admin"]).register_agent(
        "linux-http-01",
        "HTTP integration test collector",
        env["identity"]["fingerprint"],
    )

    event_id = "linux01:http-conflict:" + __import__("uuid").uuid4().hex

    first = env["client"].post(
        "/alerts/api/collector/v1/events",
        json={
            "events": [
                _postgres_http_collector_event(event_id, "alice")
            ]
        },
    )
    conflicting = env["client"].post(
        "/alerts/api/collector/v1/events",
        json={
            "events": [
                _postgres_http_collector_event(event_id, "bob")
            ]
        },
    )

    assert first.status_code == 202
    assert conflicting.status_code == 409
    assert conflicting.get_json() == {
        "error": "event_id_conflict"
    }

    assert env["admin"].execute(
        """
        SELECT count(*) AS total
        FROM soc_event_inbox
        WHERE agent_id = %s AND event_id = %s
        """,
        ("linux-http-01", event_id),
    ).fetchone()["total"] == 1


def test_postgres_collector_http_rejects_invalid_batch_without_partial_write(
    postgres_collector_http_environment,
):
    from server.soc.postgres_collector_store import PostgresCollectorStore

    env = postgres_collector_http_environment
    PostgresCollectorStore(env["admin"]).register_agent(
        "linux-http-01",
        "HTTP integration test collector",
        env["identity"]["fingerprint"],
    )

    valid = _postgres_http_collector_event(
        "linux01:http-atomic:" + __import__("uuid").uuid4().hex
    )
    invalid = _postgres_http_collector_event(
        "linux01:http-invalid:" + __import__("uuid").uuid4().hex
    )
    invalid.pop("event_type")

    response = env["client"].post(
        "/alerts/api/collector/v1/events",
        json={"events": [valid, invalid]},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_event"}

    assert env["admin"].execute(
        "SELECT count(*) AS total FROM soc_event_inbox"
    ).fetchone()["total"] == 0


def test_postgres_collector_http_rejects_unknown_and_revoked_agents(
    postgres_collector_http_environment,
):
    from server.soc.postgres_collector_store import PostgresCollectorStore

    env = postgres_collector_http_environment
    store = PostgresCollectorStore(env["admin"])

    store.register_agent(
        "linux-http-01",
        "HTTP integration test collector",
        "a" * 64,
    )

    env["identity"]["fingerprint"] = "b" * 64
    unknown = env["client"].post(
        "/alerts/api/collector/v1/events",
        json={
            "events": [
                _postgres_http_collector_event(
                    "linux01:http-unknown:" + __import__("uuid").uuid4().hex
                )
            ]
        },
    )

    assert unknown.status_code == 403
    assert unknown.get_json() == {
        "error": "collector_not_registered"
    }

    env["identity"]["fingerprint"] = "a" * 64
    assert store.revoke_agent("linux-http-01") is True

    revoked = env["client"].post(
        "/alerts/api/collector/v1/events",
        json={
            "events": [
                _postgres_http_collector_event(
                    "linux01:http-revoked:" + __import__("uuid").uuid4().hex
                )
            ]
        },
    )

    assert revoked.status_code == 403
    assert revoked.get_json() == {
        "error": "collector_revoked"
    }

def test_postgres_collector_http_rejects_declared_oversized_body(
    postgres_collector_http_environment,
):
    from server.soc.postgres_collector_api import MAX_REQUEST_BYTES
    from server.soc.postgres_collector_store import PostgresCollectorStore

    env = postgres_collector_http_environment
    PostgresCollectorStore(env["admin"]).register_agent(
        "linux-http-01",
        "HTTP integration test collector",
        env["identity"]["fingerprint"],
    )

    response = env["client"].post(
        "/alerts/api/collector/v1/events",
        data=b"x" * (MAX_REQUEST_BYTES + 1),
        content_type="application/json",
    )

    assert response.status_code == 413
    assert response.get_json() == {"error": "request_too_large"}
    assert env["admin"].execute(
        "SELECT count(*) AS total FROM soc_event_inbox"
    ).fetchone()["total"] == 0


def test_postgres_collector_http_rejects_batch_over_500_events(
    postgres_collector_http_environment,
):
    from server.soc.postgres_collector_api import MAX_BATCH_EVENTS
    from server.soc.postgres_collector_store import PostgresCollectorStore

    env = postgres_collector_http_environment
    PostgresCollectorStore(env["admin"]).register_agent(
        "linux-http-01",
        "HTTP integration test collector",
        env["identity"]["fingerprint"],
    )

    events = [
        _postgres_http_collector_event(
            f"linux01:http-limit:{index}:{__import__('uuid').uuid4().hex}"
        )
        for index in range(MAX_BATCH_EVENTS + 1)
    ]

    response = env["client"].post(
        "/alerts/api/collector/v1/events",
        json={"events": events},
    )

    assert response.status_code == 413
    assert response.get_json() == {"error": "batch_too_large"}
    assert env["admin"].execute(
        "SELECT count(*) AS total FROM soc_event_inbox"
    ).fetchone()["total"] == 0


def test_postgres_collector_http_rejects_malformed_json_and_envelopes(
    postgres_collector_http_environment,
):
    from server.soc.postgres_collector_store import PostgresCollectorStore

    env = postgres_collector_http_environment
    PostgresCollectorStore(env["admin"]).register_agent(
        "linux-http-01",
        "HTTP integration test collector",
        env["identity"]["fingerprint"],
    )

    malformed = env["client"].post(
        "/alerts/api/collector/v1/events",
        data=b'{"events": [NaN]}',
        content_type="application/json",
    )
    empty = env["client"].post(
        "/alerts/api/collector/v1/events",
        json={"events": []},
    )
    extra_key = env["client"].post(
        "/alerts/api/collector/v1/events",
        json={"events": [], "agent_id": "attacker-controlled"},
    )

    assert malformed.status_code == 400
    assert malformed.get_json() == {"error": "invalid_json_payload"}
    assert empty.status_code == 400
    assert empty.get_json() == {"error": "invalid_event_batch"}
    assert extra_key.status_code == 400
    assert extra_key.get_json() == {"error": "invalid_json_payload"}

    assert env["admin"].execute(
        "SELECT count(*) AS total FROM soc_event_inbox"
    ).fetchone()["total"] == 0


def test_postgres_collector_http_rejects_missing_or_timezone_naive_timestamp(
    postgres_collector_http_environment,
):
    from server.soc.postgres_collector_store import PostgresCollectorStore

    env = postgres_collector_http_environment
    PostgresCollectorStore(env["admin"]).register_agent(
        "linux-http-01",
        "HTTP integration test collector",
        env["identity"]["fingerprint"],
    )

    missing_timestamp = _postgres_http_collector_event(
        "linux01:http-no-timestamp:" + __import__("uuid").uuid4().hex
    )
    missing_timestamp.pop("timestamp")

    naive_timestamp = _postgres_http_collector_event(
        "linux01:http-naive-timestamp:" + __import__("uuid").uuid4().hex
    )
    naive_timestamp["timestamp"] = "2026-10-29T09:00:00"

    missing = env["client"].post(
        "/alerts/api/collector/v1/events",
        json={"events": [missing_timestamp]},
    )
    naive = env["client"].post(
        "/alerts/api/collector/v1/events",
        json={"events": [naive_timestamp]},
    )

    assert missing.status_code == 400
    assert missing.get_json() == {"error": "invalid_event"}
    assert naive.status_code == 400
    assert naive.get_json() == {"error": "invalid_event"}

    assert env["admin"].execute(
        "SELECT count(*) AS total FROM soc_event_inbox"
    ).fetchone()["total"] == 0
