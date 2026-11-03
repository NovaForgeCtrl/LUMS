"""Database-free tests for the PostgreSQL Flask application factory."""

from types import SimpleNamespace

from flask import Flask

from server import postgres_flask_security as pg_security
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
    assert response.get_json()["backend"] == "postgresql"
    assert response.get_json()["status"] == "migration_in_progress"

    assert postgres_calls == [True]
    assert sqlite_calls == []
    assert connection.closed is True


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
