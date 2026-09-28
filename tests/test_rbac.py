import os
import sqlite3
import sys
from pathlib import Path

import pytest
from flask import Flask

os.environ.setdefault(
    "LUMS_SECRET_KEY",
    "pytest-only-test-secret",
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = PROJECT_ROOT / "server"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.security import (
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    VALID_ROLES,
    current_user_role,
    login_required,
    role_required,
)


def create_rbac_database(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'administrator'
        )
        """
    )

    connection.executemany(
        """
        INSERT INTO users (
            id,
            username,
            password_hash,
            enabled,
            role
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                1,
                "administrator",
                "pytest-password-hash",
                1,
                ROLE_ADMINISTRATOR,
            ),
            (
                2,
                "operator",
                "pytest-password-hash",
                1,
                ROLE_OPERATOR,
            ),
            (
                3,
                "viewer",
                "pytest-password-hash",
                1,
                ROLE_VIEWER,
            ),
        ],
    )

    connection.commit()
    connection.close()


def configure_test_database(monkeypatch, app_module, db_path):
    def get_test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setitem(
        app_module.app.config,
        "LUMS_GET_CONNECTION",
        get_test_connection,
    )

    monkeypatch.setattr(
        app_module,
        "get_connection",
        get_test_connection,
    )


def login_as(client, user_id, username):
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["username"] = username
        session.permanent = True


def create_rbac_test_app(
    db_path=None,
    include_database=False,
):
    app = Flask(__name__)
    app.secret_key = "pytest-secret"

    if include_database:
        def get_test_connection():
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            return connection

        app.config["LUMS_GET_CONNECTION"] = get_test_connection

    return app


def install_rbac_route(
    app,
    path,
    endpoint,
    required_roles,
):
    @app.route(
        path,
        endpoint=endpoint,
    )
    @login_required
    @role_required(*required_roles)
    def rbac_route():
        return {
            "status": "allowed",
            "role": current_user_role(),
        }


def test_rbac_roles_are_defined():
    assert VALID_ROLES == {
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
    }


def test_role_required_rejects_empty_role_list():
    with pytest.raises(
        ValueError,
        match="requires at least one role",
    ):
        role_required()


def test_role_required_rejects_unknown_role():
    with pytest.raises(
        ValueError,
        match="Unknown LUMS role",
    ):
        role_required("unknown-role")


def test_current_user_role_returns_none_without_user():
    test_app = Flask(__name__)
    test_app.secret_key = "pytest-secret"

    with test_app.test_request_context("/"):
        assert current_user_role() is None


@pytest.mark.parametrize(
    "user_id,username,role",
    [
        (1, "administrator", ROLE_ADMINISTRATOR),
        (2, "operator", ROLE_OPERATOR),
        (3, "viewer", ROLE_VIEWER),
    ],
)
def test_role_required_allows_matching_role(
    tmp_path,
    user_id,
    username,
    role,
):
    db_path = str(
        tmp_path / f"rbac-allowed-{role}.db"
    )
    create_rbac_database(db_path)

    test_app = create_rbac_test_app(
        db_path,
        include_database=True,
    )

    install_rbac_route(
        test_app,
        "/test-rbac",
        "test_rbac",
        [role],
    )

    client = test_app.test_client()

    login_as(
        client,
        user_id,
        username,
    )

    with test_app.test_request_context():
        pass

    response = client.get(
        "/test-rbac",
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "allowed",
        "role": role,
    }


@pytest.mark.parametrize(
    "user_id,username,actual_role,required_role",
    [
        (
            2,
            "operator",
            ROLE_OPERATOR,
            ROLE_ADMINISTRATOR,
        ),
        (
            3,
            "viewer",
            ROLE_VIEWER,
            ROLE_OPERATOR,
        ),
        (
            3,
            "viewer",
            ROLE_VIEWER,
            ROLE_ADMINISTRATOR,
        ),
    ],
)
def test_role_required_rejects_wrong_role(
    tmp_path,
    user_id,
    username,
    actual_role,
    required_role,
):
    db_path = str(
        tmp_path
        / f"rbac-denied-{actual_role}-{required_role}.db"
    )
    create_rbac_database(db_path)

    test_app = create_rbac_test_app(
        db_path,
        include_database=True,
    )

    install_rbac_route(
        test_app,
        "/test-rbac-denied",
        "test_rbac_denied",
        [required_role],
    )

    client = test_app.test_client()

    login_as(
        client,
        user_id,
        username,
    )

    response = client.get(
        "/test-rbac-denied",
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required",
    }


def test_role_required_rejects_unauthenticated_api_request():
    test_app = create_rbac_test_app()

    @test_app.route("/api/test-rbac")
    @login_required
    @role_required(ROLE_ADMINISTRATOR)
    def rbac_api_route():
        return {
            "status": "allowed",
        }

    client = test_app.test_client()

    response = client.get(
        "/api/test-rbac",
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "authentication_required",
    }


def test_role_required_rejects_unauthenticated_web_request():
    test_app = create_rbac_test_app()

    @test_app.route("/login")
    def login():
        return "login"

    @test_app.route("/test-rbac-web")
    @login_required
    @role_required(ROLE_ADMINISTRATOR)
    def rbac_web_route():
        return {
            "status": "allowed",
        }

    client = test_app.test_client()

    response = client.get(
        "/test-rbac-web",
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/login"
    )


def test_login_required_rejects_invalid_user_role(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "rbac-invalid-role.db"
    )

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        INSERT INTO users (
            id,
            username,
            password_hash,
            enabled,
            role
        )
        VALUES (
            1,
            'invalid',
            'pytest-password-hash',
            1,
            'not-a-real-role'
        )
        """
    )

    connection.commit()
    connection.close()

    configure_test_database(
        monkeypatch,
        app_module,
        db_path,
    )

    with app_module.app.test_client() as client:
        login_as(
            client,
            1,
            "invalid",
        )

        response = client.get("/")

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "invalid_user_role",
    }

    with client.session_transaction() as session:
        assert "user_id" not in session
        assert "username" not in session


def configure_real_app_session_user(
    monkeypatch,
    app_module,
    db_path,
    user_id,
    username,
):
    configure_test_database(
        monkeypatch,
        app_module,
        db_path,
    )

    app_module.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )

    def fake_login_user(user_id, username):
        from flask import session

        session["user_id"] = user_id
        session["username"] = username
        session.permanent = True

    monkeypatch.setattr(
        app_module,
        "login_user",
        fake_login_user,
    )

    return app_module.app


@pytest.mark.parametrize(
    "user_id,username,role",
    [
        (2, "operator", ROLE_OPERATOR),
        (3, "viewer", ROLE_VIEWER),
    ],
)
def test_real_route_create_client_requires_administrator(
    monkeypatch,
    tmp_path,
    user_id,
    username,
    role,
):
    from server import app as app_module

    db_path = str(
        tmp_path / f"real-create-client-{role}.db"
    )
    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        user_id,
        username,
    )

    with app.test_client() as client:
        login_as(
            client,
            user_id,
            username,
        )

        response = client.post(
            "/api/clients",
            json={
                "hostname": "rbac-test-client",
                "ip": "192.0.2.10",
                "os": "Test",
                "kernel": "test",
                "architecture": "x86_64",
                "agent_version": "test",
            },
        )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required",
    }


@pytest.mark.parametrize(
    "user_id,username,role",
    [
        (3, "viewer", ROLE_VIEWER),
    ],
)
def test_real_route_create_update_job_requires_operator_or_administrator(
    monkeypatch,
    tmp_path,
    user_id,
    username,
    role,
):
    from server import app as app_module

    db_path = str(
        tmp_path / f"real-create-job-{role}.db"
    )
    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        user_id,
        username,
    )

    with app.test_client() as client:
        login_as(
            client,
            user_id,
            username,
        )

        response = client.post(
            "/api/clients/1/update-jobs",
            json={
                "action": "UPDATE_PACKAGE",
                "package": "test-package",
            },
        )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required",
    }


@pytest.mark.parametrize(
    "user_id,username,role",
    [
        (2, "operator", ROLE_OPERATOR),
        (3, "viewer", ROLE_VIEWER),
    ],
)
def test_real_route_rotate_client_token_requires_administrator(
    monkeypatch,
    tmp_path,
    user_id,
    username,
    role,
):
    from server import app as app_module

    db_path = str(
        tmp_path / f"real-rotate-token-{role}.db"
    )
    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        user_id,
        username,
    )

    with app.test_client() as client:
        login_as(
            client,
            user_id,
            username,
        )

        response = client.post(
            "/api/clients/1/token/rotate",
        )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required",
    }


@pytest.mark.parametrize(
    "user_id,username,role",
    [
        (2, "operator", ROLE_OPERATOR),
        (3, "viewer", ROLE_VIEWER),
    ],
)
def test_real_route_delete_client_requires_administrator(
    monkeypatch,
    tmp_path,
    user_id,
    username,
    role,
):
    from server import app as app_module

    db_path = str(
        tmp_path / f"real-delete-client-{role}.db"
    )
    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        user_id,
        username,
    )

    with app.test_client() as client:
        login_as(
            client,
            user_id,
            username,
        )

        response = client.delete(
            "/api/clients/1",
        )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required",
    }
