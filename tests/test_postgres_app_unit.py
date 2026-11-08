"""Database-free tests for the PostgreSQL Flask application factory."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from flask import Flask

import pytest

from server import postgres_app
from server import postgres_flask_security as pg_security
from server import postgres_login_routes
from server import postgres_ui_pages
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



def test_postgres_ui_page_routes_are_registered():
    app = create_test_app()

    actual = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods
        if method not in {"HEAD", "OPTIONS"}
    }

    assert {
        ("/client", "GET"),
        ("/health", "GET"),
        ("/monitoring", "GET"),
    } <= actual


def test_postgres_client_page_renders_sidebar_customizer(monkeypatch):
    connection = FakeConnection()
    calls = []

    def connection_factory():
        calls.append(True)
        return connection

    app = create_test_app(connection_factory)

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda conn, user_id: make_authorization_state(),
    )

    client = app.test_client()
    set_session(client, user_id=7, username="administrator")

    response = client.get("/client?id=42", base_url=BASE_URL)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b'id="lums-sidebar-customizer"' in response.data
    assert b'id="lums-sidebar-editor-list"' in response.data
    assert b'data-nav-id="health"' in response.data
    assert b'data-nav-id="monitoring"' in response.data

    # Nur die Autorisierungsverbindung wird benötigt.
    assert calls == [True]
    assert connection.closed is True


def test_postgres_monitoring_page_does_not_open_page_database_connection(
    monkeypatch,
):
    connections = []

    def connection_factory():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    app = create_test_app(connection_factory)

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda conn, user_id: make_authorization_state(),
    )

    client = app.test_client()
    set_session(client, user_id=7, username="administrator")

    response = client.get("/monitoring", base_url=BASE_URL)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"Live system monitoring" in response.data
    assert b'id="lums-sidebar-customizer"' in response.data

    # Die Autorisierung benötigt eine Verbindung.
    # Die Monitoring-Seite selbst öffnet keine weitere.
    assert len(connections) == 1
    assert connections[0].closed is True


def test_postgres_ui_pages_require_authentication():
    app = create_test_app()
    client = app.test_client()

    for path in ("/client", "/health", "/monitoring"):
        response = client.get(path, base_url=BASE_URL)

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")


def test_postgres_ui_pages_reject_users_without_clients_view(
    monkeypatch,
):
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
    set_session(client, user_id=7, username="viewer")

    for path in ("/client", "/health", "/monitoring"):
        response = client.get(path, base_url=BASE_URL)

        assert response.status_code == 403
        assert response.get_json() == {
            "error": "authorization_required"
        }

    assert connection.closed is True


def test_postgres_health_page_uses_read_only_transaction(
    monkeypatch,
):
    authorization_connection = FakeConnection()

    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class FakeHealthConnection:
        def __init__(self):
            self.closed = False
            self.statements = []

        def execute(self, statement, params=None):
            normalized = " ".join(statement.split())
            self.statements.append(normalized)

            if normalized.startswith("SELECT last_seen"):
                now = datetime.now(timezone.utc)
                return FakeResult([
                    {"last_seen": now},
                    {"last_seen": now - timedelta(seconds=300)},
                    {"last_seen": now - timedelta(seconds=900)},
                ])

            return FakeResult([])

        def close(self):
            self.closed = True

    health_connection = FakeHealthConnection()
    factory_calls = []

    def connection_factory():
        factory_calls.append(True)
        if len(factory_calls) == 1:
            return authorization_connection
        if len(factory_calls) == 2:
            return health_connection
        raise AssertionError("Unexpected additional DB connection")

    app = create_test_app(connection_factory)

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda conn, user_id: make_authorization_state(),
    )

    @contextmanager
    def fake_transaction(connection):
        assert connection is health_connection
        assert connection.closed is False
        yield connection

    monkeypatch.setattr(
        postgres_ui_pages,
        "transaction",
        fake_transaction,
    )

    client = app.test_client()
    set_session(client, user_id=7, username="administrator")

    response = client.get("/health", base_url=BASE_URL)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"Health Dashboard" in response.data

    assert factory_calls == [True, True]
    assert authorization_connection.closed is True
    assert health_connection.closed is True

    assert len(health_connection.statements) == 2
    assert health_connection.statements[0] == (
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    )
    assert health_connection.statements[1].startswith(
        "SELECT last_seen FROM clients"
    )

    # Alle drei Client-Zustände werden korrekt ausgegeben.
    assert b'<div class="card-value">3</div>' in response.data
    assert b'<tr><td>Online</td><td>1</td></tr>' in response.data
    assert b'<tr><td>Unbekannt</td><td>1</td></tr>' in response.data
    assert b'<tr><td>Offline</td><td>1</td></tr>' in response.data


def test_postgres_health_page_handles_database_driver_error(
    monkeypatch,
):
    class SimulatedDatabaseError(Exception):
        pass

    monkeypatch.setattr(
        postgres_ui_pages,
        "DatabaseDriverError",
        SimulatedDatabaseError,
    )

    authorization_connection = FakeConnection()

    class FakeHealthConnection:
        def __init__(self):
            self.closed = False
            self.statements = []

        def execute(self, statement, params=None):
            normalized = " ".join(statement.split())
            self.statements.append(normalized)

            if normalized.startswith("SELECT last_seen"):
                raise SimulatedDatabaseError(
                    "simulated database failure"
                )

            return None

        def close(self):
            self.closed = True

    health_connection = FakeHealthConnection()
    factory_calls = []

    def connection_factory():
        factory_calls.append(True)

        if len(factory_calls) == 1:
            return authorization_connection

        if len(factory_calls) == 2:
            return health_connection

        raise AssertionError("Unexpected additional DB connection")

    app = create_test_app(connection_factory)

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda conn, user_id: make_authorization_state(),
    )

    @contextmanager
    def fake_transaction(connection):
        assert connection is health_connection
        yield connection

    monkeypatch.setattr(
        postgres_ui_pages,
        "transaction",
        fake_transaction,
    )

    client = app.test_client()
    set_session(client, user_id=7, username="administrator")

    response = client.get("/health", base_url=BASE_URL)

    assert response.status_code == 200
    assert response.mimetype == "text/html"

    # Bei einem Datenbankfehler dürfen keine falschen Nullwerte erscheinen.
    response_html = response.get_data(as_text=True)

    assert '<tr><td>Online</td><td>—</td></tr>' in response_html
    assert '<tr><td>Unbekannt</td><td>—</td></tr>' in response_html
    assert '<tr><td>Offline</td><td>—</td></tr>' in response_html

    assert factory_calls == [True, True]
    assert authorization_connection.closed is True
    assert health_connection.closed is True

    assert health_connection.statements[0] == (
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    )


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
