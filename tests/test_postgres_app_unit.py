"""Database-free tests for the PostgreSQL Flask application factory."""

from types import SimpleNamespace

from flask import Flask

import pytest

from server import postgres_app
from server import postgres_flask_security as pg_security
from server import postgres_login_routes
from server.postgres_login import LoginResult
from server.postgres_app import create_postgres_app


BASE_URL = "https://localhost"


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def create_test_app(connection_factory=None):
    config = {
        "SECRET_KEY": "pytest-postgres-app-secret",
        "TESTING": True,
    }

    if connection_factory is not None:
        config["LUMS_POSTGRES_GET_CONNECTION"] = connection_factory

    return create_postgres_app(config)


def set_session(client, **values):
    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        session.clear()
        session.update(values)


def make_authorization_state(
    permissions=frozenset({"clients.view"}),
):
    return SimpleNamespace(
        user={
            "id": 7,
            "username": "administrator",
            "enabled": True,
            "role": "administrator",
        },
        permissions=permissions,
    )


def test_factory_creates_postgres_app_without_opening_connection():
    calls = []

    def connection_factory():
        calls.append(True)
        return FakeConnection()

    app = create_test_app(connection_factory)

    assert isinstance(app, Flask)
    assert app.extensions["lums_database_backend"] == "postgresql"
    assert app.config["LUMS_POSTGRES_GET_CONNECTION"] is connection_factory
    assert calls == []


def test_factory_registers_only_postgres_compatible_blueprint():
    app = create_test_app()

    assert set(app.blueprints) == {"postgres_auth"}

    login_rules = [
        rule for rule in app.url_map.iter_rules()
        if rule.rule == "/login"
    ]
    language_rules = [
        rule for rule in app.url_map.iter_rules()
        if rule.rule == "/language"
    ]

    assert len(login_rules) == 1
    assert login_rules[0].endpoint == "postgres_auth.login"

    assert len(language_rules) == 1
    assert language_rules[0].endpoint == (
        "postgres_auth.change_language"
    )


def test_postgres_login_page_is_available():
    app = create_test_app()

    response = app.test_client().get(
        "/login",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert b'name="csrf_token"' in response.data


def test_home_requires_authentication_and_redirects_to_postgres_login():
    app = create_test_app()

    response = app.test_client().get(
        "/",
        base_url=BASE_URL,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_home_uses_postgres_authorization_and_never_sqlite_fallback(
    monkeypatch,
):
    connection = FakeConnection()
    postgres_calls = []
    sqlite_calls = []

    def postgres_factory():
        postgres_calls.append(True)
        return connection

    def forbidden_sqlite_factory():
        sqlite_calls.append(True)
        raise AssertionError("SQLite factory must never be called")

    app = create_test_app(postgres_factory)

    # Deliberately configure the SQLite key as a trap.
    app.config["LUMS_GET_CONNECTION"] = forbidden_sqlite_factory

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda conn, user_id: make_authorization_state(),
    )

    client = app.test_client()
    set_session(
        client,
        user_id=7,
        username="administrator",
    )

    response = client.get(
        "/",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b'id="client-count"' in response.data
    assert b'data-nav-id="dashboard"' in response.data
    assert b'href="/infrastructure"' in response.data
    assert b"migration_in_progress" not in response.data

    assert postgres_calls == [True]
    assert sqlite_calls == []
    assert connection.closed is True




def test_successful_login_follows_redirect_to_postgres_dashboard(
    monkeypatch,
):
    connections = []

    def connection_factory():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    app = create_test_app(connection_factory)

    def authenticate(
        connection,
        username,
        password,
        rate_limit_key,
        *,
        selected_language=None,
    ):
        assert connection is connections[0]
        assert username == "administrator"
        assert password == "correct-password"
        assert selected_language == "de"

        return LoginResult(
            status="authenticated",
            user_id=7,
            username="administrator",
            language="de",
        )

    monkeypatch.setattr(
        postgres_login_routes,
        "authenticate_user",
        authenticate,
    )

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda connection, user_id: make_authorization_state(),
    )

    client = app.test_client()

    login_page = client.get(
        "/login",
        base_url=BASE_URL,
    )
    assert login_page.status_code == 200

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        anonymous_csrf = session["csrf_token"]

    response = client.post(
        "/login",
        base_url=BASE_URL,
        data={
            "username": "administrator",
            "password": "correct-password",
            "language": "de",
            "csrf_token": anonymous_csrf,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].headers["Location"].endswith("/")

    assert response.request.path == "/"
    assert response.mimetype == "text/html"

    assert b'id="client-count"' in response.data
    assert b'data-nav-id="dashboard"' in response.data
    assert b'href="/infrastructure"' in response.data
    assert b'action="/logout"' in response.data
    assert b"migration_in_progress" not in response.data

    assert len(connections) == 2
    assert all(connection.closed for connection in connections)

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert session["user_id"] == 7
        assert session["username"] == "administrator"
        assert session["language"] == "de"
        assert session["csrf_token"]
        assert session["csrf_token"] != anonymous_csrf

def test_home_rejects_user_without_clients_view(monkeypatch):
    connection = FakeConnection()
    app = create_test_app(lambda: connection)

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda conn, user_id: make_authorization_state(
            permissions=frozenset({"software.view"})
        ),
    )

    client = app.test_client()
    set_session(
        client,
        user_id=7,
        username="viewer",
    )

    response = client.get(
        "/",
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required"
    }
    assert connection.closed is True


def test_factory_does_not_register_sqlite_alert_or_soc_routes():
    app = create_test_app()

    endpoints = {
        rule.endpoint
        for rule in app.url_map.iter_rules()
    }

    assert not any(
        endpoint.startswith("alerts.")
        for endpoint in endpoints
    )
    assert not any(
        endpoint.startswith("soc.")
        for endpoint in endpoints
    )



def test_factory_registers_postgres_alert_routes_without_sqlite_blueprint():
    app = create_test_app()

    expected = {
        ("/alerts/rules", "GET"),
        ("/alerts/rules", "POST"),
        ("/alerts/rules/<rule_id>", "PUT"),
        ("/alerts/rules/<rule_id>", "DELETE"),
        ("/alerts/current", "GET"),
        ("/alerts/history", "GET"),
        ("/alerts/trigger", "POST"),
        ("/alerts/<alert_id>/acknowledge", "POST"),
        ("/alerts/<alert_id>/resolve", "POST"),
        ("/alerts/<alert_id>/escalate", "POST"),
    }

    actual = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods
        if method not in {"HEAD", "OPTIONS"}
    }

    assert expected <= actual
    assert not any(
        rule.endpoint.startswith("alerts.")
        for rule in app.url_map.iter_rules()
    )


def test_factory_registers_postgres_update_job_routes_and_module_status(
    monkeypatch,
):
    connection = FakeConnection()
    app = create_test_app(lambda: connection)

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda conn, user_id: make_authorization_state(),
    )

    expected_routes = {
        ("/api/clients/<int:client_id>/update-jobs", "POST"),
        ("/api/clients/<int:client_id>/update-jobs", "GET"),
        (
            "/api/clients/<int:client_id>/update-jobs/pending",
            "GET",
        ),
        ("/api/update-jobs/<int:job_id>/checkpoint", "POST"),
        ("/api/update-jobs/<int:job_id>/result", "POST"),
        ("/api/update-jobs/<int:job_id>/abandon", "POST"),
        ("/api/clients/<int:client_id>/update-jobs/running", "GET"),
        (
            "/api/clients/<int:client_id>/update-jobs/<int:job_id>/claim",
            "POST",
        ),
        ("/api/update-jobs/<int:job_id>", "GET"),
        ("/api/clients/<int:client_id>/update-history", "GET"),
        ("/api/update-history", "GET"),
    }

    actual_routes = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods
        if method not in {"HEAD", "OPTIONS"}
    }

    assert expected_routes <= actual_routes

    pending_rules = [
        rule
        for rule in app.url_map.iter_rules()
        if rule.rule == (
            "/api/clients/<int:client_id>/update-jobs/pending"
        )
    ]

    assert len(pending_rules) == 1
    assert pending_rules[0].endpoint == (
        "postgres_get_pending_update_job"
    )

    client = app.test_client()
    set_session(
        client,
        user_id=7,
        username="administrator",
    )

    response = client.get("/api/status", base_url=BASE_URL)

    assert response.status_code == 200

    payload = response.get_json()
    assert payload["backend"] == "postgresql"
    assert "updates" in payload["available_modules"]
    assert "updates" not in payload["pending_modules"]

    assert connection.closed is True


def test_custom_login_endpoints_are_preserved():
    app = create_postgres_app({
        "SECRET_KEY": "pytest-custom-secret",
        "TESTING": True,
        "LUMS_LOGIN_ENDPOINT": "postgres_auth.login",
        "LUMS_LOGIN_SUCCESS_ENDPOINT": "index",
    })

    assert app.config["LUMS_LOGIN_ENDPOINT"] == (
        "postgres_auth.login"
    )
    assert app.config["LUMS_LOGIN_SUCCESS_ENDPOINT"] == "index"


def test_factory_does_not_mutate_caller_configuration():
    config = {
        "SECRET_KEY": "pytest-immutable-secret",
        "TESTING": True,
    }
    original = dict(config)

    create_postgres_app(config)

    assert config == original


def test_load_secret_key_reads_and_trims_secret_file(monkeypatch, tmp_path):
    secret_file = tmp_path / "lums_secret"
    secret_file.write_text("  test-secret-value \n", encoding="utf-8")
    monkeypatch.setenv("LUMS_SECRET_KEY_FILE", str(secret_file))
    monkeypatch.delenv("LUMS_SECRET_KEY", raising=False)

    assert postgres_app._load_secret_key() == "test-secret-value"


def test_load_secret_key_falls_back_only_when_file_is_missing(
    monkeypatch, tmp_path
):
    missing_file = tmp_path / "missing-secret"
    monkeypatch.setenv("LUMS_SECRET_KEY_FILE", str(missing_file))
    monkeypatch.setenv("LUMS_SECRET_KEY", "fallback-secret")

    assert postgres_app._load_secret_key() == "fallback-secret"


def test_load_secret_key_rejects_missing_file_without_fallback(
    monkeypatch, tmp_path
):
    missing_file = tmp_path / "missing-secret"
    monkeypatch.setenv("LUMS_SECRET_KEY_FILE", str(missing_file))
    monkeypatch.delenv("LUMS_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="LUMS secret is not configured"):
        postgres_app._load_secret_key()


def test_load_secret_key_rejects_empty_secret_file(monkeypatch, tmp_path):
    secret_file = tmp_path / "empty-secret"
    secret_file.write_text("  \n", encoding="utf-8")
    monkeypatch.setenv("LUMS_SECRET_KEY_FILE", str(secret_file))
    monkeypatch.setenv("LUMS_SECRET_KEY", "must-not-be-used")

    with pytest.raises(RuntimeError, match="LUMS secret"):
        postgres_app._load_secret_key()


def test_load_secret_key_hides_unreadable_file_path(monkeypatch, tmp_path):
    secret_directory = tmp_path / "secret-directory"
    secret_directory.mkdir()
    monkeypatch.setenv("LUMS_SECRET_KEY_FILE", str(secret_directory))

    with pytest.raises(RuntimeError) as exc_info:
        postgres_app._load_secret_key()

    assert str(secret_directory) not in str(exc_info.value)


def test_load_secret_key_hides_invalid_utf8_file_content(
    monkeypatch, tmp_path
):
    secret_file = tmp_path / "invalid-secret"
    secret_file.write_bytes(b"\xffprivate-secret-content")
    monkeypatch.setenv("LUMS_SECRET_KEY_FILE", str(secret_file))

    with pytest.raises(RuntimeError) as exc_info:
        postgres_app._load_secret_key()

    assert str(secret_file) not in str(exc_info.value)
    assert "private-secret-content" not in str(exc_info.value)
