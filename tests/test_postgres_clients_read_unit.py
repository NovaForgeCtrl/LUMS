"""Database-free tests for PostgreSQL client read routes and access control."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from server import postgres_flask_security as pg_security
from server.postgres_app import create_postgres_app


BASE_URL = "https://localhost"
CSRF_TOKEN = "client-read-test-csrf"

ALL_PERMISSIONS = frozenset({
    "clients.view",
    "clients.manage",
    "updates.view",
    "software.view",
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
        self.statements = []
        self.closed = False

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.statements.append((normalized, params))
        return self.handler(self, normalized, params)

    def close(self):
        self.closed = True


def make_environment(monkeypatch, handler, permissions=None):
    connections = []

    def connection_factory():
        connection = FakeConnection(handler)
        connections.append(connection)
        return connection

    app = create_postgres_app({
        "SECRET_KEY": "postgres-client-read-unit-secret",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
    })

    state = SimpleNamespace(
        user={
            "id": 7,
            "username": "client-reader",
            "enabled": True,
            "role": "administrator",
        },
        permissions=(
            ALL_PERMISSIONS if permissions is None else permissions
        ),
    )

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda connection, user_id: state,
    )

    client = app.test_client()

    with client.session_transaction(base_url=BASE_URL) as session:
        session.clear()
        session.update({
            "user_id": 7,
            "username": "client-reader",
            "csrf_token": CSRF_TOKEN,
        })

    return client, connections


def test_client_list_returns_counts_status_and_iso_timestamp(monkeypatch):
    last_seen = datetime.now(timezone.utc) - timedelta(seconds=30)

    def handler(connection, statement, params):
        if "FROM clients c" in statement:
            assert "WHERE c.enabled IS TRUE" in statement
            return FakeCursor(many=[{
                "id": 41,
                "hostname": "agent-01",
                "ip": "192.0.2.41",
                "os": "Debian",
                "kernel": "6.1.0",
                "architecture": "x86_64",
                "agent_version": "1.0.0",
                "last_seen": last_seen,
                "idle": False,
                "idle_seconds": 0,
                "idle_threshold_seconds": 300,
                "idle_source": "x11",
                "idle_supported": True,
                "package_count": 120,
                "update_count": 4,
            }])

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = make_environment(monkeypatch, handler)

    response = client.get("/api/clients", base_url=BASE_URL)

    assert response.status_code == 200
    data = response.get_json()

    assert len(data) == 1
    assert data[0]["id"] == 41
    assert data[0]["hostname"] == "agent-01"
    assert data[0]["package_count"] == 120
    assert data[0]["update_count"] == 4
    assert data[0]["status"] == "online"
    assert data[0]["last_seen"] == last_seen.isoformat()
    assert connections[-1].closed is True


def test_client_details_returns_counts_and_status(monkeypatch):
    last_seen = datetime.now(timezone.utc) - timedelta(minutes=3)

    def handler(connection, statement, params):
        if "FROM clients c" in statement:
            assert params == (41,)
            return FakeCursor(one={
                "id": 41,
                "hostname": "agent-01",
                "ip": "192.0.2.41",
                "os": "Debian",
                "kernel": "6.1.0",
                "architecture": "x86_64",
                "agent_version": "1.0.0",
                "last_seen": last_seen,
                "package_count": 120,
                "update_count": 4,
            })

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = make_environment(monkeypatch, handler)

    response = client.get(
        "/api/clients/41",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["id"] == 41
    assert data["package_count"] == 120
    assert data["update_count"] == 4
    assert data["status"] == "unknown"
    assert data["last_seen"] == last_seen.isoformat()
    assert connections[-1].closed is True


def test_missing_client_details_returns_404(monkeypatch):
    def handler(connection, statement, params):
        if "FROM clients c" in statement:
            return FakeCursor(one=None)

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = make_environment(monkeypatch, handler)

    response = client.get(
        "/api/clients/999",
        base_url=BASE_URL,
    )

    assert response.status_code == 404
    assert response.get_json()["message"] == "Client not found"
    assert connections[-1].closed is True


def test_client_updates_are_returned_in_query_order(monkeypatch):
    expected = [
        {
            "id": 1,
            "package": "curl",
            "installed_version": "1.0",
            "available_version": "1.1",
        },
        {
            "id": 2,
            "package": "openssl",
            "installed_version": "2.0",
            "available_version": "2.1",
        },
    ]

    def handler(connection, statement, params):
        if "FROM available_updates" in statement:
            assert params == (41,)
            assert "ORDER BY package" in statement
            return FakeCursor(many=expected)

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = make_environment(monkeypatch, handler)

    response = client.get(
        "/api/clients/41/updates",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == expected
    assert connections[-1].closed is True


def test_client_packages_are_returned_in_query_order(monkeypatch):
    expected = [
        {"package": "curl", "version": "1.0"},
        {"package": "openssl", "version": "2.0"},
    ]

    def handler(connection, statement, params):
        if "FROM installed_packages" in statement:
            assert params == (41,)
            assert "ORDER BY package" in statement
            return FakeCursor(many=expected)

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = make_environment(monkeypatch, handler)

    response = client.get(
        "/api/clients/41/packages",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == expected
    assert connections[-1].closed is True


def test_client_list_requires_clients_view(monkeypatch):
    def handler(connection, statement, params):
        raise AssertionError(
            f"Read route must not execute SQL: {statement}"
        )

    client, connections = make_environment(
        monkeypatch,
        handler,
        permissions=frozenset({"software.view"}),
    )

    response = client.get("/api/clients", base_url=BASE_URL)

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required"
    }
    assert len(connections) == 1
    assert connections[0].closed is True


def test_client_updates_require_updates_view(monkeypatch):
    def handler(connection, statement, params):
        raise AssertionError(
            f"Read route must not execute SQL: {statement}"
        )

    client, connections = make_environment(
        monkeypatch,
        handler,
        permissions=frozenset({"clients.view"}),
    )

    response = client.get(
        "/api/clients/41/updates",
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert connections[0].closed is True


def test_client_packages_require_software_view(monkeypatch):
    def handler(connection, statement, params):
        raise AssertionError(
            f"Read route must not execute SQL: {statement}"
        )

    client, connections = make_environment(
        monkeypatch,
        handler,
        permissions=frozenset({"clients.view"}),
    )

    response = client.get(
        "/api/clients/41/packages",
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert connections[0].closed is True


def test_client_creation_requires_csrf(monkeypatch):
    def handler(connection, statement, params):
        raise AssertionError(
            f"Client creation must not execute SQL: {statement}"
        )

    client, connections = make_environment(
        monkeypatch,
        handler,
        permissions=ALL_PERMISSIONS,
    )

    response = client.post(
        "/api/clients",
        json={
            "hostname": "agent-02",
            "ip": "192.0.2.42",
        },
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "csrf_validation_failed"
    }
    assert len(connections) == 1
    assert connections[0].closed is True
