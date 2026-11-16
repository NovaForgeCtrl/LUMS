"""Database-free tests for PostgreSQL client management routes."""

from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest
from psycopg import Error as PsycopgError

from server import postgres_clients as clients_module
from server import postgres_flask_security as pg_security
from server.postgres_app import create_postgres_app


BASE_URL = "https://localhost"
CSRF_TOKEN = "client-route-test-csrf"

ADMIN_PERMISSIONS = frozenset({
    "clients.view",
    "clients.manage",
    "software.view",
    "updates.view",
})


class FakeCursor:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = list(many or [])

    def fetchone(self):
        return self.one

    def fetchall(self):
        return list(self.many)


class FakeConnection:
    def __init__(self, handler):
        self.handler = handler
        self.closed = False
        self.statements = []
        self.events = []

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.statements.append((normalized, params))
        return self.handler(self, normalized, params)

    def close(self):
        self.closed = True


def _make_environment(monkeypatch, handler):
    connections = []

    def connection_factory():
        connection = FakeConnection(handler)
        connections.append(connection)
        return connection

    app = create_postgres_app({
        "SECRET_KEY": "postgres-clients-route-unit-secret",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
    })

    state = SimpleNamespace(
        user={
            "id": 7,
            "username": "administrator",
            "enabled": True,
            "role": "administrator",
        },
        permissions=ADMIN_PERMISSIONS,
    )

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda connection, user_id: state,
    )

    @contextmanager
    def fake_transaction(connection):
        connection.events.append("transaction.begin")
        try:
            yield connection
        except BaseException:
            connection.events.append("transaction.rollback")
            raise
        else:
            connection.events.append("transaction.commit")

    def fake_audit(connection, **kwargs):
        assert "transaction.begin" in connection.events
        connection.events.append(("audit", kwargs))

    monkeypatch.setattr(
        clients_module,
        "transaction",
        fake_transaction,
    )
    monkeypatch.setattr(
        clients_module,
        "audit_log",
        fake_audit,
    )

    client = app.test_client()

    with client.session_transaction(base_url=BASE_URL) as session:
        session.clear()
        session.update({
            "user_id": 7,
            "username": "administrator",
            "csrf_token": CSRF_TOKEN,
        })

    return client, connections


def _write_headers():
    return {"X-CSRF-Token": CSRF_TOKEN}


def _route_connection(connections, prefix):
    return next(
        connection
        for connection in connections
        if any(
            statement.startswith(prefix)
            for statement, _ in connection.statements
        )
    )


def test_create_client_stores_hash_and_returns_plaintext_once(
    monkeypatch,
):
    monkeypatch.setattr(
        clients_module,
        "generate_client_token",
        lambda: "one-time-client-secret",
    )
    monkeypatch.setattr(
        clients_module,
        "hash_client_token",
        lambda token: "stored-token-hash",
    )

    def handler(connection, statement, params):
        if statement.startswith("SELECT pg_advisory_xact_lock"):
            return FakeCursor()

        if statement.startswith("SELECT id FROM clients WHERE ip"):
            return FakeCursor(one=None)

        if statement.startswith("INSERT INTO clients"):
            return FakeCursor(one={"id": 41})

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        "/api/clients",
        json={
            "hostname": "agent-01",
            "ip": "192.0.2.41",
            "os": "Debian",
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["client"]["id"] == 41
    assert data["token"] == "one-time-client-secret"

    connection = _route_connection(
        connections,
        "INSERT INTO clients",
    )
    insert = next(
        params
        for statement, params in connection.statements
        if statement.startswith("INSERT INTO clients")
    )

    assert insert[0:2] == ("agent-01", "192.0.2.41")
    assert insert[7] == "stored-token-hash"
    assert isinstance(insert[8], datetime)
    assert "one-time-client-secret" not in repr(insert)

    audit = next(
        event[1]
        for event in connection.events
        if isinstance(event, tuple) and event[0] == "audit"
    )
    assert audit["action"] == "client.create"
    assert audit["target"] == "client:41"
    assert connection.events[-1] == "transaction.commit"
    assert all(item.closed for item in connections)


def test_rotate_client_token_replaces_hash_and_audits(monkeypatch):
    monkeypatch.setattr(
        clients_module,
        "generate_client_token",
        lambda: "rotated-client-secret",
    )
    monkeypatch.setattr(
        clients_module,
        "hash_client_token",
        lambda token: "rotated-token-hash",
    )

    def handler(connection, statement, params):
        if statement.startswith("SELECT id, hostname, enabled FROM clients"):
            return FakeCursor(one={
                "id": 41,
                "hostname": "agent-01",
                "enabled": True,
            })

        if statement.startswith("UPDATE clients"):
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        "/api/clients/41/token/rotate",
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "rotated"
    assert data["token"] == "rotated-client-secret"
    assert data["client"]["enabled"] is True

    connection = _route_connection(
        connections,
        "UPDATE clients",
    )
    update = next(
        (statement, params)
        for statement, params in connection.statements
        if statement.startswith("UPDATE clients")
    )

    assert "client_token_hash = %s" in update[0]
    assert "token_revoked_at = NULL" in update[0]
    assert update[1][0] == "rotated-token-hash"
    assert update[1][2] == 41

    assert connection.events[-1] == "transaction.commit"
    assert any(
        event[1]["action"] == "client.token.rotate"
        for event in connection.events
        if isinstance(event, tuple) and event[0] == "audit"
    )
    assert all(item.closed for item in connections)


def test_disable_client_removes_current_state_but_keeps_client(
    monkeypatch,
):
    def handler(connection, statement, params):
        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one={
                "id": 41,
                "hostname": "agent-01",
            })

        if statement.startswith("DELETE FROM available_updates"):
            return FakeCursor()

        if statement.startswith("DELETE FROM installed_packages"):
            return FakeCursor()

        if statement.startswith("UPDATE clients"):
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.delete(
        "/api/clients/41",
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "disabled",
        "client_id": 41,
        "hostname": "agent-01",
    }

    connection = _route_connection(
        connections,
        "DELETE FROM available_updates",
    )
    statements = [
        statement for statement, _ in connection.statements
    ]

    assert any(
        statement.startswith("DELETE FROM available_updates")
        for statement in statements
    )
    assert any(
        statement.startswith("DELETE FROM installed_packages")
        for statement in statements
    )
    assert any(
        statement.startswith("UPDATE clients")
        and "enabled = FALSE" in statement
        and "token_revoked_at" in statement
        for statement in statements
    )
    assert not any(
        statement.startswith("DELETE FROM clients")
        for statement in statements
    )

    assert connection.events[-1] == "transaction.commit"
    assert any(
        event[1]["action"] == "client.disable"
        for event in connection.events
        if isinstance(event, tuple) and event[0] == "audit"
    )
    assert all(item.closed for item in connections)


def test_create_client_rolls_back_when_audit_fails(monkeypatch):
    monkeypatch.setattr(
        clients_module,
        "generate_client_token",
        lambda: "must-not-be-returned",
    )
    monkeypatch.setattr(
        clients_module,
        "hash_client_token",
        lambda token: "stored-token-hash",
    )

    def handler(connection, statement, params):
        if statement.startswith("SELECT pg_advisory_xact_lock"):
            return FakeCursor()

        if statement.startswith("SELECT id FROM clients WHERE ip"):
            return FakeCursor(one=None)

        if statement.startswith("INSERT INTO clients"):
            return FakeCursor(one={"id": 42})

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    def failing_audit(connection, **kwargs):
        raise PsycopgError("synthetic audit failure")

    monkeypatch.setattr(
        clients_module,
        "audit_log",
        failing_audit,
    )

    response = client.post(
        "/api/clients",
        json={"hostname": "agent-02", "ip": "192.0.2.42"},
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 500
    assert "token" not in response.get_json()

    connection = _route_connection(
        connections,
        "INSERT INTO clients",
    )
    assert connection.events == [
        "transaction.begin",
        "transaction.rollback",
    ]
    assert all(item.closed for item in connections)
