"""Database-free tests for PostgreSQL client authentication and reporting."""

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from psycopg import Error as PsycopgError

from server import postgres_clients as pg_clients
from server import postgres_flask_security as pg_security
from server.postgres_app import create_postgres_app


BASE_URL = "https://localhost"
TOKEN = "test-agent-token"
TOKEN_HASH = "test-agent-token-hash"

CLIENT = {
    "id": 41,
    "hostname": "agent-01",
    "enabled": True,
    "client_token_hash": TOKEN_HASH,
    "token_revoked_at": None,
}

REPORT = {
    "hostname": "agent-01",
    "ip": "192.0.2.41",
    "os": "Debian",
    "kernel": "6.1.0",
    "architecture": "x86_64",
    "agent_version": "1.0.0",
    "updates": [{
        "package": "curl",
        "installed_version": "1.0",
        "available_version": "1.1",
    }],
    "packages": {"curl": "1.0"},
}


class FakeCursor:
    def __init__(self, one=None):
        self.one = one

    def fetchone(self):
        return self.one


class FakeConnection:
    def __init__(self, handler):
        self.handler = handler
        self.statements = []
        self.events = []
        self.closed = False

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.statements.append((normalized, params))
        return self.handler(self, normalized, params)

    def close(self):
        self.closed = True


def make_environment(monkeypatch, handler):
    connections = []

    def connection_factory():
        connection = FakeConnection(handler)
        connections.append(connection)
        return connection

    monkeypatch.setattr(
        pg_security,
        "hash_client_token",
        lambda token: TOKEN_HASH,
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

    monkeypatch.setattr(
        pg_clients,
        "transaction",
        fake_transaction,
    )

    app = create_postgres_app({
        "SECRET_KEY": "postgres-client-agent-unit-secret",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
    })

    return app.test_client(), connections


def bearer_headers():
    return {"Authorization": f"Bearer {TOKEN}"}


def test_client_me_returns_authenticated_client(monkeypatch):
    def handler(connection, statement, params):
        if "WHERE client_token_hash = %s" in statement:
            return FakeCursor(one=dict(CLIENT))
        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = make_environment(monkeypatch, handler)

    response = client.get(
        "/api/client/me",
        headers=bearer_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "id": 41,
        "hostname": "agent-01",
        "enabled": True,
    }
    assert len(connections) == 1
    assert connections[0].closed is True


@pytest.mark.parametrize(
    "changes",
    [
        {"enabled": False},
        {"token_revoked_at": datetime.now(timezone.utc)},
    ],
)
def test_client_auth_rejects_disabled_or_revoked_token(
    monkeypatch,
    changes,
):
    auth_client = {**CLIENT, **changes}

    def handler(connection, statement, params):
        if "WHERE client_token_hash = %s" in statement:
            return FakeCursor(one=auth_client)
        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = make_environment(monkeypatch, handler)

    response = client.get(
        "/api/client/me",
        headers=bearer_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == (
        "client_authentication_required"
    )
    assert len(connections) == 1
    assert connections[0].closed is True


def test_client_report_revalidates_token_and_saves_atomically(
    monkeypatch,
):
    def handler(connection, statement, params):
        if "WHERE client_token_hash = %s" in statement:
            return FakeCursor(one=dict(CLIENT))

        if "WHERE id = %s FOR UPDATE" in statement:
            return FakeCursor(one=dict(CLIENT))

        if statement.startswith("UPDATE clients SET hostname"):
            return FakeCursor()

        if statement.startswith("DELETE FROM available_updates"):
            return FakeCursor()

        if statement.startswith("INSERT INTO available_updates"):
            return FakeCursor()

        if statement.startswith("DELETE FROM installed_packages"):
            return FakeCursor()

        if statement.startswith("INSERT INTO installed_packages"):
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = make_environment(monkeypatch, handler)

    payload = {
        **REPORT,
        "id": 999,
        "client_id": 999,
    }

    response = client.post(
        "/api/report",
        json=payload,
        headers=bearer_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == {"status": "received"}
    assert len(connections) == 2

    auth_connection, report_connection = connections
    assert auth_connection.closed is True
    assert report_connection.closed is True

    statements = report_connection.statements
    assert any("FOR UPDATE" in sql for sql, _ in statements)

    client_update = next(
        params for sql, params in statements
        if sql.startswith("UPDATE clients SET hostname")
    )
    assert client_update[-1] == 41

    update_insert = next(
        params for sql, params in statements
        if sql.startswith("INSERT INTO available_updates")
    )
    assert update_insert[0] == 41

    package_insert = next(
        params for sql, params in statements
        if sql.startswith("INSERT INTO installed_packages")
    )
    assert package_insert[0] == 41

    assert report_connection.events == [
        "transaction.begin",
        "transaction.commit",
    ]


def test_client_report_rejects_token_changed_after_authentication(
    monkeypatch,
):
    changed_client = {
        **CLIENT,
        "client_token_hash": "different-token-hash",
    }

    def handler(connection, statement, params):
        if "WHERE client_token_hash = %s" in statement:
            return FakeCursor(one=dict(CLIENT))

        if "WHERE id = %s FOR UPDATE" in statement:
            return FakeCursor(one=changed_client)

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = make_environment(monkeypatch, handler)

    response = client.post(
        "/api/report",
        json=REPORT,
        headers=bearer_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert len(connections) == 2

    report_connection = connections[-1]
    assert report_connection.events == [
        "transaction.begin",
        "transaction.commit",
    ]
    assert not any(
        sql.startswith(("UPDATE clients", "DELETE FROM", "INSERT INTO"))
        for sql, _ in report_connection.statements
    )
    assert all(connection.closed for connection in connections)


def test_client_report_rolls_back_on_package_write_failure(monkeypatch):
    def handler(connection, statement, params):
        if "WHERE client_token_hash = %s" in statement:
            return FakeCursor(one=dict(CLIENT))

        if "WHERE id = %s FOR UPDATE" in statement:
            return FakeCursor(one=dict(CLIENT))

        if statement.startswith("UPDATE clients"):
            return FakeCursor()

        if statement.startswith("DELETE FROM"):
            return FakeCursor()

        if statement.startswith("INSERT INTO available_updates"):
            return FakeCursor()

        if statement.startswith("INSERT INTO installed_packages"):
            raise PsycopgError("synthetic package write failure")

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = make_environment(monkeypatch, handler)

    response = client.post(
        "/api/report",
        json=REPORT,
        headers=bearer_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 500
    assert response.get_json()["status"] == "error"

    report_connection = connections[-1]
    assert report_connection.events == [
        "transaction.begin",
        "transaction.rollback",
    ]
    assert all(connection.closed for connection in connections)


def test_client_report_rejects_invalid_payload_before_route_connection(
    monkeypatch,
):
    def handler(connection, statement, params):
        if "WHERE client_token_hash = %s" in statement:
            return FakeCursor(one=dict(CLIENT))
        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = make_environment(monkeypatch, handler)

    response = client.post(
        "/api/report",
        json={"hostname": "incomplete"},
        headers=bearer_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert len(connections) == 1
    assert connections[0].closed is True


def test_client_report_without_bearer_does_not_open_connection(
    monkeypatch,
):
    def handler(connection, statement, params):
        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = make_environment(monkeypatch, handler)

    response = client.post(
        "/api/report",
        json=REPORT,
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert connections == []
