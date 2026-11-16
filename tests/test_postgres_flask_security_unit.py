"""Database-free tests for PostgreSQL Flask security decorators."""

from types import SimpleNamespace

import pytest
from flask import Blueprint, Flask, jsonify

from server import postgres_flask_security as pg_security


class FakeCursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row=None):
        self.row = row
        self.calls = []
        self.closed = False

    def execute(self, statement, params=None):
        self.calls.append((" ".join(statement.split()), params))
        return FakeCursor(self.row)

    def close(self):
        self.closed = True


def make_state(
    *,
    role="administrator",
    permissions=frozenset({"clients.view"}),
):
    return SimpleNamespace(
        user={
            "id": 7,
            "username": "administrator",
            "enabled": True,
            "role": role,
        },
        permissions=permissions,
    )


def create_app():
    app = Flask(__name__)
    app.secret_key = "pytest-postgres-security-secret"
    pg_security.configure_session(app)
    app.config["TESTING"] = True

    @app.get("/login")
    def login():
        return "login"

    return app


def set_session(client, **values):
    with client.session_transaction(
        base_url="https://localhost"
    ) as session:
        session.clear()
        session.update(values)


def configure_connection(monkeypatch, app, connection):
    app.config["LUMS_POSTGRES_GET_CONNECTION"] = lambda: connection


def test_postgres_adapter_never_uses_sqlite_connection_factory():
    app = create_app()
    sqlite_factory_calls = []

    def sqlite_connection_factory():
        sqlite_factory_calls.append(True)
        return FakeConnection()

    # Deliberately configure only the existing SQLite connection key.
    app.config["LUMS_GET_CONNECTION"] = sqlite_connection_factory

    @app.get("/api/protected")
    @pg_security.login_required
    def protected():
        return "allowed"

    client = app.test_client()
    set_session(client, user_id=7, username="administrator")

    response = client.get(
        "/api/protected",
        base_url="https://localhost",
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "authorization_state_unavailable"
    }
    assert sqlite_factory_calls == []


def test_login_required_uses_configured_blueprint_endpoint():
    app = create_app()

    auth_bp = Blueprint("postgres_auth", __name__)

    @auth_bp.get("/postgres-login")
    def login():
        return "postgres login"

    app.register_blueprint(auth_bp)
    app.config["LUMS_LOGIN_ENDPOINT"] = "postgres_auth.login"

    @app.get("/protected")
    @pg_security.login_required
    def protected():
        return "allowed"

    response = app.test_client().get(
        "/protected",
        base_url="https://localhost",
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/postgres-login")


def test_unauthenticated_web_request_redirects_to_login():
    app = create_app()

    @app.get("/protected")
    @pg_security.login_required
    def protected():
        return "allowed"

    response = app.test_client().get(
        "/protected",
        base_url="https://localhost",
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_unauthenticated_api_request_returns_401():
    app = create_app()

    @app.get("/soc/api/protected")
    @pg_security.login_required
    def protected():
        return "allowed"

    response = app.test_client().get(
        "/soc/api/protected",
        base_url="https://localhost",
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "authentication_required"
    }


def test_authenticated_request_uses_postgres_authorization_state(
    monkeypatch,
):
    app = create_app()
    connection = FakeConnection()
    configure_connection(monkeypatch, app, connection)

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda conn, user_id: make_state(),
    )

    @app.get("/protected")
    @pg_security.login_required
    def protected():
        return jsonify({
            "user_id": pg_security.current_user_id(),
            "role": pg_security.current_user_role(),
            "permissions": sorted(
                pg_security.current_user_permissions()
            ),
        })

    client = app.test_client()
    set_session(client, user_id=7, username="administrator")

    response = client.get(
        "/protected",
        base_url="https://localhost",
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "user_id": 7,
        "role": "administrator",
        "permissions": ["clients.view"],
    }
    assert connection.closed is True


def test_disabled_user_session_is_revoked(monkeypatch):
    app = create_app()
    connection = FakeConnection()
    configure_connection(monkeypatch, app, connection)

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda conn, user_id: None,
    )

    @app.get("/protected")
    @pg_security.login_required
    def protected():
        return "allowed"

    client = app.test_client()
    set_session(
        client,
        user_id=7,
        username="administrator",
    )

    response = client.get(
        "/protected",
        base_url="https://localhost",
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert connection.closed is True

    with client.session_transaction(
        base_url="https://localhost"
    ) as session:
        assert "user_id" not in session
        assert "username" not in session


def test_authorization_backend_failure_returns_503(monkeypatch):
    app = create_app()
    connection = FakeConnection()
    configure_connection(monkeypatch, app, connection)

    def fail(*args):
        raise RuntimeError("simulated authorization failure")

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        fail,
    )

    @app.get("/api/protected")
    @pg_security.login_required
    def protected():
        return "allowed"

    client = app.test_client()
    set_session(client, user_id=7)

    response = client.get(
        "/api/protected",
        base_url="https://localhost",
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "authorization_state_unavailable"
    }
    assert connection.closed is True


def test_role_required_denies_missing_permission(monkeypatch):
    app = create_app()
    connection = FakeConnection()
    configure_connection(monkeypatch, app, connection)

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda conn, user_id: make_state(
            permissions=frozenset({"software.view"})
        ),
    )

    @app.get("/protected")
    @pg_security.login_required
    @pg_security.role_required(permission="clients.view")
    def protected():
        return "allowed"

    client = app.test_client()
    set_session(client, user_id=7)

    response = client.get(
        "/protected",
        base_url="https://localhost",
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required"
    }


def test_role_required_allows_required_permission(monkeypatch):
    app = create_app()
    connection = FakeConnection()
    configure_connection(monkeypatch, app, connection)

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda conn, user_id: make_state(
            permissions=frozenset({"clients.view"})
        ),
    )

    @app.get("/protected")
    @pg_security.login_required
    @pg_security.role_required(permission="clients.view")
    def protected():
        return "allowed"

    client = app.test_client()
    set_session(client, user_id=7)

    response = client.get(
        "/protected",
        base_url="https://localhost",
    )

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "allowed"


def test_role_required_rejects_unknown_permission():
    with pytest.raises(ValueError, match="Unknown LUMS permission"):
        pg_security.role_required(permission="unknown.permission")


def test_csrf_required_rejects_missing_token():
    app = create_app()

    @app.post("/change")
    @pg_security.csrf_required
    def change():
        return "changed"

    response = app.test_client().post(
        "/change",
        base_url="https://localhost",
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "csrf_validation_failed"
    }


def test_csrf_required_accepts_valid_session_token():
    app = create_app()

    @app.post("/change")
    @pg_security.csrf_required
    def change():
        return "changed"

    client = app.test_client()
    set_session(client, csrf_token="valid-csrf-token")

    response = client.post(
        "/change",
        base_url="https://localhost",
        headers={"X-CSRF-Token": "valid-csrf-token"},
    )

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "changed"


def test_client_authentication_requires_bearer_token():
    app = create_app()

    @app.get("/client")
    @pg_security.client_auth_required
    def client_route():
        return "allowed"

    response = app.test_client().get(
        "/client",
        base_url="https://localhost",
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "client_authentication_required"
    }


def test_client_authentication_uses_postgres_boolean_and_token_hash(
    monkeypatch,
):
    app = create_app()
    connection = FakeConnection(
        row={
            "id": 12,
            "hostname": "debian-client",
            "enabled": True,
            "client_token_hash": "stored-hash",
            "token_revoked_at": None,
        }
    )
    configure_connection(monkeypatch, app, connection)

    monkeypatch.setattr(
        pg_security,
        "get_bearer_token",
        lambda: "raw-client-token",
    )
    monkeypatch.setattr(
        pg_security,
        "hash_client_token",
        lambda token: "stored-hash",
    )

    @app.get("/client")
    @pg_security.client_auth_required
    def client_route():
        client = pg_security.authenticated_client()
        return jsonify({
            "id": client["id"],
            "hostname": client["hostname"],
        })

    response = app.test_client().get(
        "/client",
        base_url="https://localhost",
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "id": 12,
        "hostname": "debian-client",
    }

    statement, params = connection.calls[0]
    assert "WHERE client_token_hash = %s" in statement
    assert params == ("stored-hash",)
    assert connection.closed is True


@pytest.mark.parametrize(
    "row",
    [
        None,
        {
            "id": 12,
            "hostname": "disabled-client",
            "enabled": False,
            "client_token_hash": "stored-hash",
            "token_revoked_at": None,
        },
        {
            "id": 12,
            "hostname": "revoked-client",
            "enabled": True,
            "client_token_hash": "stored-hash",
            "token_revoked_at": "2026-11-02T08:00:00+00:00",
        },
    ],
    ids=["unknown", "disabled", "revoked"],
)
def test_client_authentication_rejects_invalid_client(
    monkeypatch,
    row,
):
    app = create_app()
    connection = FakeConnection(row=row)
    configure_connection(monkeypatch, app, connection)

    monkeypatch.setattr(
        pg_security,
        "get_bearer_token",
        lambda: "raw-client-token",
    )
    monkeypatch.setattr(
        pg_security,
        "hash_client_token",
        lambda token: "stored-hash",
    )

    @app.get("/client")
    @pg_security.client_auth_required
    def client_route():
        return "allowed"

    response = app.test_client().get(
        "/client",
        base_url="https://localhost",
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "client_authentication_required"
    }
    assert connection.closed is True


def test_client_authentication_database_failure_returns_503(
    monkeypatch,
):
    app = create_app()
    connection = FakeConnection()

    def fail(*args, **kwargs):
        raise RuntimeError("simulated database failure")

    connection.execute = fail
    configure_connection(monkeypatch, app, connection)

    monkeypatch.setattr(
        pg_security,
        "get_bearer_token",
        lambda: "raw-client-token",
    )
    monkeypatch.setattr(
        pg_security,
        "hash_client_token",
        lambda token: "stored-hash",
    )

    @app.get("/client")
    @pg_security.client_auth_required
    def client_route():
        return "allowed"

    response = app.test_client().get(
        "/client",
        base_url="https://localhost",
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "client_authentication_unavailable"
    }
    assert connection.closed is True
