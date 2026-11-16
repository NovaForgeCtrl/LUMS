"""Database-free tests for PostgreSQL login and language routes."""

from contextlib import contextmanager
from pathlib import Path

import pytest
from flask import Flask

from server import postgres_login_routes as routes
from server.postgres_login import LoginResult
from server.security import configure_session


BASE_URL = "https://localhost"


class FakeConnection:
    def __init__(self, *, rowcount=1):
        self.rowcount = rowcount
        self.calls = []
        self.closed = False

    def execute(self, statement, params=None):
        self.calls.append(
            (" ".join(statement.split()), params)
        )
        return self

    def close(self):
        self.closed = True


def create_app():
    template_dir = (
        Path(__file__).resolve().parents[1]
        / "server"
        / "templates"
    )

    app = Flask(
        "postgres_login_routes_test",
        template_folder=str(template_dir),
    )
    app.secret_key = "pytest-postgres-login-routes-secret"
    app.config.update(
        TESTING=True,
        LUMS_LOGIN_SUCCESS_ENDPOINT="index",
    )

    configure_session(app)

    @app.get("/")
    def index():
        return "index"

    app.register_blueprint(routes.postgres_auth_bp)

    return app


def set_session(client, **values):
    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        session.clear()
        session.update(values)


def set_csrf(client, token="test-csrf-token", **values):
    set_session(client, csrf_token=token, **values)


def configure_postgres_connection(app, connection):
    app.config["LUMS_POSTGRES_GET_CONNECTION"] = (
        lambda: connection
    )


def test_get_login_renders_template_and_creates_csrf_token():
    app = create_app()
    client = app.test_client()

    response = client.get(
        "/login",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert b'name="csrf_token"' in response.data

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert session["csrf_token"]
        assert session["language"] == "de"
        assert session["csrf_token"].encode() in response.data


@pytest.mark.parametrize(
    "csrf_token",
    [None, "wrong-token"],
    ids=["missing-token", "invalid-token"],
)
def test_login_rejects_invalid_csrf_before_database_access(
    csrf_token,
):
    app = create_app()
    factory_calls = []

    app.config["LUMS_POSTGRES_GET_CONNECTION"] = (
        lambda: factory_calls.append(True)
    )

    client = app.test_client()
    set_csrf(client, "expected-token")

    data = {
        "username": "administrator",
        "password": "correct-password",
    }

    if csrf_token is not None:
        data["csrf_token"] = csrf_token

    response = client.post(
        "/login",
        base_url=BASE_URL,
        data=data,
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "csrf_validation_failed"
    }
    assert factory_calls == []

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert "user_id" not in session


def test_login_rejects_sqlite_connection_factory_fallback():
    app = create_app()
    sqlite_factory_calls = []

    app.config["LUMS_GET_CONNECTION"] = (
        lambda: sqlite_factory_calls.append(True)
    )

    client = app.test_client()
    set_csrf(client)

    response = client.post(
        "/login",
        base_url=BASE_URL,
        data={
            "username": "administrator",
            "password": "correct-password",
            "csrf_token": "test-csrf-token",
        },
    )

    assert response.status_code == 503
    assert sqlite_factory_calls == []

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert "user_id" not in session


def test_invalid_credentials_do_not_create_authenticated_session(
    monkeypatch,
):
    app = create_app()
    connection = FakeConnection()
    configure_postgres_connection(app, connection)

    calls = []

    def authenticate(
        conn,
        username,
        password,
        rate_limit_key,
        *,
        selected_language=None,
    ):
        calls.append(
            (
                conn,
                username,
                password,
                rate_limit_key,
                selected_language,
            )
        )
        return LoginResult(status="invalid_credentials")

    monkeypatch.setattr(
        routes,
        "authenticate_user",
        authenticate,
    )

    client = app.test_client()
    set_csrf(client)

    response = client.post(
        "/login",
        base_url=BASE_URL,
        data={
            "username": " administrator ",
            "password": "wrong-password",
            "language": "fr-FR",
            "csrf_token": "test-csrf-token",
        },
    )

    assert response.status_code == 401
    assert connection.closed is True

    assert len(calls) == 1
    assert calls[0][0] is connection
    assert calls[0][1] == "administrator"
    assert calls[0][2] == "wrong-password"
    assert calls[0][3].startswith("administrator|")
    assert calls[0][4] == "fr"

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert "user_id" not in session
        assert session["csrf_token"] == "test-csrf-token"


def test_successful_login_creates_session_after_connection_close(
    monkeypatch,
):
    app = create_app()
    connection = FakeConnection()
    configure_postgres_connection(app, connection)

    monkeypatch.setattr(
        routes,
        "authenticate_user",
        lambda *args, **kwargs: LoginResult(
            status="authenticated",
            user_id=7,
            username="administrator",
            language="en-GB",
        ),
    )

    original_login_user = routes.login_user
    login_user_calls = []

    def checked_login_user(user_id, username):
        assert connection.closed is True
        login_user_calls.append((user_id, username))
        original_login_user(user_id, username)

    monkeypatch.setattr(
        routes,
        "login_user",
        checked_login_user,
    )

    client = app.test_client()
    set_csrf(client, "anonymous-csrf-token")

    response = client.post(
        "/login",
        base_url=BASE_URL,
        data={
            "username": "administrator",
            "password": "correct-password",
            "language": "fr",
            "csrf_token": "anonymous-csrf-token",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert connection.closed is True
    assert login_user_calls == [(7, "administrator")]

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert session["user_id"] == 7
        assert session["username"] == "administrator"
        assert session["language"] == "en-GB"
        assert session["csrf_token"]
        assert session["csrf_token"] != "anonymous-csrf-token"


def test_login_service_failure_does_not_create_session(monkeypatch):
    app = create_app()
    connection = FakeConnection()
    configure_postgres_connection(app, connection)

    def fail(*args, **kwargs):
        raise RuntimeError("simulated login transaction failure")

    monkeypatch.setattr(
        routes,
        "authenticate_user",
        fail,
    )

    client = app.test_client()
    set_csrf(client)

    response = client.post(
        "/login",
        base_url=BASE_URL,
        data={
            "username": "administrator",
            "password": "correct-password",
            "csrf_token": "test-csrf-token",
        },
    )

    assert response.status_code == 503
    assert connection.closed is True

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert "user_id" not in session


def test_anonymous_language_change_updates_only_session():
    app = create_app()
    client = app.test_client()
    set_csrf(client, language="de")

    response = client.post(
        "/language",
        base_url=BASE_URL,
        data={
            "language": "en",
            "csrf_token": "test-csrf-token",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert session["language"] == "en-US"


def test_language_change_rejects_invalid_language():
    app = create_app()
    client = app.test_client()
    set_csrf(client, language="de")

    response = client.post(
        "/language",
        base_url=BASE_URL,
        data={
            "language": "unsupported-language",
            "csrf_token": "test-csrf-token",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_language"
    }

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert session["language"] == "de"


def test_authenticated_language_change_persists_before_session_update(
    monkeypatch,
):
    app = create_app()
    connection = FakeConnection()
    configure_postgres_connection(app, connection)

    @contextmanager
    def fake_transaction(conn):
        assert conn is connection
        yield

    monkeypatch.setattr(
        routes,
        "transaction",
        fake_transaction,
    )

    client = app.test_client()
    set_csrf(
        client,
        language="de",
        user_id=7,
        username="administrator",
    )

    response = client.post(
        "/language",
        base_url=BASE_URL,
        data={
            "language": "en",
            "csrf_token": "test-csrf-token",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    assert connection.closed is True
    assert len(connection.calls) == 1

    statement, params = connection.calls[0]
    assert statement == (
        "UPDATE users SET language = %s WHERE id = %s"
    )
    assert params == ("en-US", 7)

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert session["language"] == "en-US"


def test_language_change_does_not_update_session_if_transaction_fails(
    monkeypatch,
):
    app = create_app()
    connection = FakeConnection()
    configure_postgres_connection(app, connection)

    @contextmanager
    def failing_transaction(conn):
        yield
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(
        routes,
        "transaction",
        failing_transaction,
    )

    client = app.test_client()
    set_csrf(
        client,
        language="de",
        user_id=7,
        username="administrator",
    )

    response = client.post(
        "/language",
        base_url=BASE_URL,
        data={
            "language": "en",
            "csrf_token": "test-csrf-token",
        },
    )

    assert response.status_code == 503
    assert connection.closed is True

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert session["language"] == "de"


def test_language_change_returns_404_for_missing_user(
    monkeypatch,
):
    app = create_app()
    connection = FakeConnection(rowcount=0)
    configure_postgres_connection(app, connection)

    @contextmanager
    def fake_transaction(conn):
        yield

    monkeypatch.setattr(
        routes,
        "transaction",
        fake_transaction,
    )

    client = app.test_client()
    set_csrf(
        client,
        language="de",
        user_id=999,
    )

    response = client.post(
        "/language",
        base_url=BASE_URL,
        data={
            "language": "fr",
            "csrf_token": "test-csrf-token",
        },
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "error": "user_not_found"
    }
    assert connection.closed is True

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert session["language"] == "de"


def test_language_change_rejects_invalid_csrf_without_database_access():
    app = create_app()
    factory_calls = []

    app.config["LUMS_POSTGRES_GET_CONNECTION"] = (
        lambda: factory_calls.append(True)
    )

    client = app.test_client()
    set_csrf(client, language="de")

    response = client.post(
        "/language",
        base_url=BASE_URL,
        data={
            "language": "fr",
            "csrf_token": "wrong-token",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "csrf_validation_failed"
    }
    assert factory_calls == []

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert session["language"] == "de"


def test_session_configuration_uses_secure_cookie_defaults():
    app = create_app()

    assert app.config["SESSION_COOKIE_NAME"] == "lums_session"
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Strict"
    assert app.config["SESSION_COOKIE_PATH"] == "/"
    assert app.config["PERMANENT_SESSION_LIFETIME"] == 1800
    assert app.config["SESSION_REFRESH_EACH_REQUEST"] is True


def test_login_connection_factory_failure_returns_503_without_session():
    app = create_app()
    factory_calls = []
    sqlite_factory_calls = []

    def fail_to_connect():
        factory_calls.append(True)
        raise RuntimeError("simulated PostgreSQL connection failure")

    app.config["LUMS_POSTGRES_GET_CONNECTION"] = fail_to_connect
    app.config["LUMS_GET_CONNECTION"] = (
        lambda: sqlite_factory_calls.append(True)
    )

    client = app.test_client()
    set_csrf(client)

    response = client.post(
        "/login",
        base_url=BASE_URL,
        data={
            "username": "administrator",
            "password": "correct-password",
            "csrf_token": "test-csrf-token",
        },
    )

    assert response.status_code == 503
    assert "simulated PostgreSQL connection failure" not in (
        response.get_data(as_text=True)
    )
    assert factory_calls == [True]
    assert sqlite_factory_calls == []

    with client.session_transaction(
        base_url=BASE_URL
    ) as session:
        assert "user_id" not in session
        assert session["csrf_token"] == "test-csrf-token"
