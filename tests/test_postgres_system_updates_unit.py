"""Database-free tests for PostgreSQL host-updater routes."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

from server import postgres_flask_security as pg_security
from server import postgres_system_updates as pg_updates
from server.postgres_app import create_postgres_app
from server.security import ROLE_ADMINISTRATOR, ROLE_OPERATOR


BASE_URL = "https://localhost"
HOST_TOKEN = "test-host-updater-secret-" + "x" * 32
ADMIN_PERMISSIONS = frozenset({
    "clients.view",
    "users.manage",
    "system.update",
})


class FakeResult:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = list(many or [])

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class FakeConnection:
    def __init__(self, handler=None):
        self.closed = False
        self.statements = []
        self.handler = handler

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.statements.append((normalized, params))

        if self.handler is not None:
            return self.handler(normalized, params)

        return FakeResult()

    def close(self):
        self.closed = True


def create_test_app(connection_factory):
    return create_postgres_app({
        "SECRET_KEY": "pytest-postgres-system-updates-secret",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
    })


def set_session(client, **values):
    with client.session_transaction(base_url=BASE_URL) as session:
        session.clear()
        session.update(values)


def install_authorization(
    monkeypatch,
    *,
    role=ROLE_ADMINISTRATOR,
    permissions=ADMIN_PERMISSIONS,
):
    state = SimpleNamespace(
        user={
            "id": 7,
            "username": "administrator",
            "enabled": True,
            "role": role,
        },
        permissions=frozenset(permissions),
    )

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda connection, user_id: state,
    )

    return state


@contextmanager
def fake_transaction(connection):
    """Replace transaction mechanics without opening a database."""
    assert connection.closed is False
    yield connection


def authenticate_browser(client):
    set_session(
        client,
        user_id=7,
        username="administrator",
        csrf_token="test-csrf-token",
    )


def configure_host_token(monkeypatch, tmp_path):
    token_file = tmp_path / "host-updater-token"
    token_file.write_text(HOST_TOKEN, encoding="utf-8")
    monkeypatch.setenv(
        "LUMS_HOST_UPDATER_TOKEN_FILE",
        str(token_file),
    )
    return {"Authorization": f"Bearer {HOST_TOKEN}"}


def test_factory_registers_postgres_system_update_routes():
    app = create_test_app(lambda: FakeConnection())

    actual = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods
        if method not in {"HEAD", "OPTIONS"}
    }

    assert {
        ("/updates", "GET"),
        ("/api/system-updates", "GET"),
        ("/api/system-updates", "POST"),
        ("/api/host-updater/heartbeat", "POST"),
    } <= actual


def test_updates_page_requires_authentication():
    app = create_test_app(lambda: FakeConnection())

    response = app.test_client().get(
        "/updates",
        base_url=BASE_URL,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_updates_page_renders_postgres_sidebar_and_customizer(monkeypatch):
    connection = FakeConnection()
    calls = []

    def connection_factory():
        calls.append(True)
        return connection

    app = create_test_app(connection_factory)
    install_authorization(monkeypatch)

    client = app.test_client()
    authenticate_browser(client)

    response = client.get("/updates", base_url=BASE_URL)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b'id="lums-sidebar-customizer"' in response.data
    assert b'data-nav-id="system-updates"' in response.data
    assert b'system-updates.js' in response.data
    assert b'name="csrf_token"' in response.data
    assert calls == [True]
    assert connection.closed is True


@pytest.mark.parametrize(
    ("role", "permissions"),
    [
        (ROLE_OPERATOR, ADMIN_PERMISSIONS),
        (
            ROLE_ADMINISTRATOR,
            frozenset({"clients.view", "users.manage"}),
        ),
    ],
)
def test_system_update_status_requires_admin_and_permission(
    monkeypatch,
    role,
    permissions,
):
    connection = FakeConnection()
    app = create_test_app(lambda: connection)

    install_authorization(
        monkeypatch,
        role=role,
        permissions=permissions,
    )

    client = app.test_client()
    authenticate_browser(client)

    response = client.get(
        "/api/system-updates",
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required"
    }
    assert connection.closed is True


def test_status_endpoint_requires_authentication():
    app = create_test_app(lambda: FakeConnection())

    response = app.test_client().get(
        "/api/system-updates",
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "authentication_required"
    }


def test_status_endpoint_loads_release_agent_and_history(
    monkeypatch,
):
    authorization_connection = FakeConnection()
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()

    agent_row = {
        "last_seen": timestamp,
        "current_version": "1.0.0",
        "deployment": "test-host",
        "status_message": "Heartbeat received",
    }

    job_row = {
        "id": 12,
        "requested_at": timestamp,
        "requested_by": "administrator",
        "target_tag": "v1.2.3",
        "target_commit": "a1" * 20,
        "status": "queued",
        "step": "preflight",
        "progress_json": json.dumps([
            {
                "at": timestamp,
                "step": "preflight",
                "message": "Auftrag angenommen.",
            }
        ]),
        "details_json": json.dumps({
            "summary": "Test release",
            "worker_id": "internal-worker-id",
            "approval": {"confirmed": True},
        }),
        "error": None,
        "rollback_status": None,
        "updated_at": timestamp,
        "finished_at": None,
    }

    def status_handler(statement, params):
        if statement.startswith("SET TRANSACTION"):
            return FakeResult()

        if statement.startswith("SELECT last_seen"):
            return FakeResult(one=agent_row)

        if statement.startswith("SELECT id, requested_at"):
            return FakeResult(many=[job_row])

        raise AssertionError(f"Unexpected SQL: {statement}")

    status_connection = FakeConnection(status_handler)
    calls = []

    def connection_factory():
        calls.append(True)
        if len(calls) == 1:
            return authorization_connection
        if len(calls) == 2:
            return status_connection
        raise AssertionError("Unexpected database connection")

    app = create_test_app(connection_factory)
    install_authorization(monkeypatch)

    monkeypatch.setattr(
        pg_updates,
        "latest_release",
        lambda: {
            "tag": "v1.2.3",
            "name": "LUMS 1.2.3",
            "commit": "a1" * 20,
            "url": "https://github.com/NovaForgeCtrl/LUMS/releases/tag/v1.2.3",
            "notes": "Test release",
        },
    )
    monkeypatch.setattr(
        pg_updates,
        "transaction",
        fake_transaction,
    )

    client = app.test_client()
    authenticate_browser(client)

    response = client.get(
        "/api/system-updates",
        base_url=BASE_URL,
    )

    assert response.status_code == 200

    payload = response.get_json()
    assert payload["release"]["tag"] == "v1.2.3"
    assert payload["agent"]["online"] is True
    assert payload["agent"]["current_version"] == "1.0.0"
    assert payload["update_execution_enabled"] is False

    assert len(payload["history"]) == 1
    history = payload["history"][0]
    assert history["id"] == 12
    assert history["progress"][0]["step"] == "preflight"
    assert history["details"] == {
        "summary": "Test release"
    }
    assert "worker_id" not in history["details"]
    assert "approval" not in history["details"]

    assert len(calls) == 2
    assert authorization_connection.closed is True
    assert status_connection.closed is True

    assert status_connection.statements[0][0] == (
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    )
    assert status_connection.statements[1][0].startswith(
        "SELECT last_seen"
    )
    assert status_connection.statements[2][0].startswith(
        "SELECT id, requested_at"
    )


def test_status_endpoint_keeps_working_when_release_lookup_fails(
    monkeypatch,
):
    authorization_connection = FakeConnection()

    def status_handler(statement, params):
        if statement.startswith("SET TRANSACTION"):
            return FakeResult()

        if statement.startswith("SELECT last_seen"):
            return FakeResult(one=None)
        if statement.startswith("SELECT id, requested_at"):
            return FakeResult(many=[])
        raise AssertionError(f"Unexpected SQL: {statement}")

    status_connection = FakeConnection(status_handler)
    calls = []

    def connection_factory():
        calls.append(True)
        return (
            authorization_connection
            if len(calls) == 1
            else status_connection
        )

    app = create_test_app(connection_factory)
    install_authorization(monkeypatch)

    def fail_release_lookup():
        raise pg_updates.ReleaseLookupError("GitHub test unavailable")

    monkeypatch.setattr(
        pg_updates,
        "latest_release",
        fail_release_lookup,
    )
    monkeypatch.setattr(
        pg_updates,
        "transaction",
        fake_transaction,
    )

    client = app.test_client()
    authenticate_browser(client)

    response = client.get(
        "/api/system-updates",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["release"] is None
    assert payload["release_error"] == "GitHub test unavailable"
    assert payload["agent"]["online"] is False
    assert payload["history"] == []
    assert payload["update_execution_enabled"] is False

    assert authorization_connection.closed is True
    assert status_connection.closed is True

    assert len(status_connection.statements) == 3
    assert status_connection.statements[0][0] == (
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    )
    assert status_connection.statements[1][0].startswith(
        "SELECT last_seen"
    )
    assert status_connection.statements[2][0].startswith(
        "SELECT id, requested_at"
    )


def test_status_endpoint_returns_503_on_database_error(monkeypatch):
    class SimulatedDatabaseError(Exception):
        pass

    monkeypatch.setattr(
        pg_updates,
        "DatabaseDriverError",
        SimulatedDatabaseError,
    )

    authorization_connection = FakeConnection()

    def fail_query(statement, params):
        raise SimulatedDatabaseError("simulated database failure")

    status_connection = FakeConnection(fail_query)
    calls = []

    def connection_factory():
        calls.append(True)
        return (
            authorization_connection
            if len(calls) == 1
            else status_connection
        )

    app = create_test_app(connection_factory)
    install_authorization(monkeypatch)

    monkeypatch.setattr(
        pg_updates,
        "latest_release",
        lambda: None,
    )
    monkeypatch.setattr(
        pg_updates,
        "transaction",
        fake_transaction,
    )

    client = app.test_client()
    authenticate_browser(client)

    response = client.get(
        "/api/system-updates",
        base_url=BASE_URL,
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "database_unavailable"
    }
    assert authorization_connection.closed is True
    assert status_connection.closed is True


def test_heartbeat_rejects_missing_or_invalid_token(
    monkeypatch,
    tmp_path,
):
    configure_host_token(monkeypatch, tmp_path)
    calls = []

    def connection_factory():
        calls.append(True)
        raise AssertionError("Database must not be opened")

    app = create_test_app(connection_factory)
    client = app.test_client()

    response = client.post(
        "/api/host-updater/heartbeat",
        base_url=BASE_URL,
        json={"version": "dev"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == (
        "host_updater_authentication_required"
    )
    assert calls == []


def test_heartbeat_rejects_missing_token_configuration(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "LUMS_HOST_UPDATER_TOKEN_FILE",
        str(tmp_path / "missing-token"),
    )

    app = create_test_app(
        lambda: (_ for _ in ()).throw(
            AssertionError("Database must not be opened")
        )
    )

    response = app.test_client().post(
        "/api/host-updater/heartbeat",
        base_url=BASE_URL,
        json={"version": "dev"},
        headers={"Authorization": f"Bearer {HOST_TOKEN}"},
    )

    assert response.status_code == 503
    assert response.get_json()["error"] == (
        "host_updater_not_configured"
    )


def test_heartbeat_persists_payload_without_enabling_updates(
    monkeypatch,
    tmp_path,
):
    headers = configure_host_token(monkeypatch, tmp_path)
    connection = FakeConnection()
    calls = []

    def connection_factory():
        calls.append(True)
        return connection

    app = create_test_app(connection_factory)
    client = app.test_client()

    response = client.post(
        "/api/host-updater/heartbeat",
        base_url=BASE_URL,
        headers=headers,
        json={
            "version": "dev",
            "deployment": "test-host",
            "status_message": "Heartbeat test",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["update_execution_enabled"] is False
    assert payload["last_seen"]

    assert len(calls) == 1
    assert connection.closed is True
    assert len(connection.statements) == 1

    statement, params = connection.statements[0]
    assert statement.startswith("INSERT INTO system_update_agent")
    assert "ON CONFLICT (id) DO UPDATE" in statement
    assert params[1:] == (
        "dev",
        "test-host",
        "Heartbeat test",
    )


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        ({"version": "x" * 81}, "invalid_version"),
        ({"deployment": "x" * 81}, "invalid_deployment"),
        ({"status_message": "x" * 501}, "invalid_status_message"),
        ({"status_message": "   "}, "invalid_status_message"),
    ],
)
def test_heartbeat_rejects_invalid_payload_fields(
    monkeypatch,
    tmp_path,
    payload,
    expected_error,
):
    headers = configure_host_token(monkeypatch, tmp_path)

    app = create_test_app(
        lambda: (_ for _ in ()).throw(
            AssertionError("Invalid payload must not open the database")
        )
    )

    response = app.test_client().post(
        "/api/host-updater/heartbeat",
        base_url=BASE_URL,
        headers=headers,
        json=payload,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == expected_error


def test_heartbeat_returns_500_and_closes_connection_on_database_error(
    monkeypatch,
    tmp_path,
):
    class SimulatedDatabaseError(Exception):
        pass

    monkeypatch.setattr(
        pg_updates,
        "DatabaseDriverError",
        SimulatedDatabaseError,
    )

    headers = configure_host_token(monkeypatch, tmp_path)

    def fail_query(statement, params):
        raise SimulatedDatabaseError("simulated write failure")

    connection = FakeConnection(fail_query)
    app = create_test_app(lambda: connection)

    response = app.test_client().post(
        "/api/host-updater/heartbeat",
        base_url=BASE_URL,
        headers=headers,
        json={"version": "dev"},
    )

    assert response.status_code == 500
    assert response.get_json()["error"] == (
        "heartbeat_storage_failed"
    )
    assert connection.closed is True


def test_update_request_requires_csrf_and_remains_disabled(
    monkeypatch,
):
    connections = []

    def connection_factory():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    app = create_test_app(connection_factory)
    install_authorization(monkeypatch)

    client = app.test_client()
    authenticate_browser(client)

    no_csrf = client.post(
        "/api/system-updates",
        base_url=BASE_URL,
        json={
            "confirmed": True,
            "target_tag": "v1.2.3",
            "target_commit": "a1" * 20,
        },
    )

    assert no_csrf.status_code == 400

    accepted_csrf_but_disabled = client.post(
        "/api/system-updates",
        base_url=BASE_URL,
        headers={"X-CSRF-Token": "test-csrf-token"},
        json={
            "confirmed": True,
            "target_tag": "v1.2.3",
            "target_commit": "a1" * 20,
        },
    )

    assert accepted_csrf_but_disabled.status_code == 503
    assert accepted_csrf_but_disabled.get_json()["error"] == (
        "update_execution_disabled"
    )

    # Both connections belong to authorization checks only.
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert all(connection.statements == [] for connection in connections)


def test_agent_online_check_rejects_stale_and_future_heartbeats():
    now = datetime.now(timezone.utc)

    assert pg_updates._agent_is_online(
        now.isoformat(),
        now=now,
    )
    assert pg_updates._agent_is_online(
        (now - timedelta(seconds=60)).isoformat(),
        now=now,
    )
    assert not pg_updates._agent_is_online(
        (now - timedelta(seconds=61)).isoformat(),
        now=now,
    )
    assert not pg_updates._agent_is_online(
        (now + timedelta(seconds=1)).isoformat(),
        now=now,
    )
    assert not pg_updates._agent_is_online(
        "not-a-timestamp",
        now=now,
    )
    assert not pg_updates._agent_is_online(None, now=now)
