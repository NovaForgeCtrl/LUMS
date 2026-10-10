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
            created_at TEXT NOT NULL,
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
            created_at,
            enabled,
            role
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                1,
                "administrator",
                "pytest-password-hash",
                "2026-01-01T00:00:00+00:00",
                1,
                ROLE_ADMINISTRATOR,
            ),
            (
                2,
                "operator",
                "pytest-password-hash",
                "2026-01-01T00:00:00+00:00",
                1,
                ROLE_OPERATOR,
            ),
            (
                3,
                "viewer",
                "pytest-password-hash",
                "2026-01-01T00:00:00+00:00",
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


def create_package_job_database(db_path):
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

    connection.execute(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY,
            hostname TEXT,
            enabled INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE update_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            action TEXT NOT NULL DEFAULT 'UPDATE_PACKAGE'
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE update_job_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            package TEXT NOT NULL,
            installed_version TEXT,
            target_version TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            action TEXT NOT NULL,
            target TEXT,
            result TEXT NOT NULL,
            details TEXT
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
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            1,
            "administrator",
            "pytest-password-hash",
            1,
            ROLE_ADMINISTRATOR,
        ),
    )

    connection.execute(
        """
        INSERT INTO clients (
            id,
            hostname,
            enabled
        )
        VALUES (?, ?, ?)
        """,
        (
            1,
            "pytest-client",
            1,
        ),
    )

    connection.commit()
    connection.close()


def test_real_route_install_package_accepts_valid_package(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "install-package-valid.db"
    )
    create_package_job_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        login_as(
            client,
            1,
            "administrator",
        )

        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/clients/1/update-jobs",
            headers={
                "X-CSRF-Token": "pytest-csrf-token",
            },
            json={
                "action": "INSTALL_PACKAGE",
                "packages": ["curl"],
            },
        )

    assert response.status_code == 201

    data = response.get_json()

    assert data["status"] == "created"
    assert data["action"] == "INSTALL_PACKAGE"
    assert data["client_id"] == 1
    assert len(data["packages"]) == 1
    assert data["packages"][0]["package"] == "curl"
    assert data["packages"][0]["installed_version"] is None
    assert data["packages"][0]["target_version"] == ""

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    job = connection.execute(
        """
        SELECT
            client_id,
            status,
            action
        FROM update_jobs
        """
    ).fetchone()

    package = connection.execute(
        """
        SELECT
            package,
            target_version,
            status
        FROM update_job_packages
        """
    ).fetchone()

    audit = connection.execute(
        """
        SELECT
            actor_type,
            actor_id,
            action,
            target,
            result,
            details
        FROM audit_log
        WHERE action = 'update_job.create'
        """
    ).fetchone()

    connection.close()

    assert job["client_id"] == 1
    assert job["status"] == "pending"
    assert job["action"] == "INSTALL_PACKAGE"

    assert package["package"] == "curl"
    assert package["target_version"] == ""
    assert package["status"] == "pending"

    assert audit is not None
    assert audit["actor_type"] == "user"
    assert audit["actor_id"] == "1"
    assert audit["action"] == "update_job.create"
    assert audit["target"].startswith("job:")
    assert audit["result"] == "success"
    assert audit["details"] == (
        "client=1 action=INSTALL_PACKAGE packages=1"
    )


@pytest.mark.parametrize(
    "package",
    [
        "-rf",
        "curl;id",
        "curl && id",
        "curl$(id)",
        "curl`id`",
        "curl|id",
    ],
)
def test_real_route_install_package_rejects_invalid_package_name(
    monkeypatch,
    tmp_path,
    package,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "install-package-invalid.db"
    )
    create_package_job_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        login_as(
            client,
            1,
            "administrator",
        )

        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/clients/1/update-jobs",
            headers={
                "X-CSRF-Token": "pytest-csrf-token",
            },
            json={
                "action": "INSTALL_PACKAGE",
                "packages": [package],
            },
        )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"
    assert data["message"] == "Invalid package name"
    assert data["packages"] == [package]

    connection = sqlite3.connect(db_path)

    job_count = connection.execute(
        "SELECT COUNT(*) FROM update_jobs"
    ).fetchone()[0]

    package_count = connection.execute(
        "SELECT COUNT(*) FROM update_job_packages"
    ).fetchone()[0]

    connection.close()

    assert job_count == 0
    assert package_count == 0


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


def create_user_test_database(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'administrator'
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            action TEXT NOT NULL,
            target TEXT,
            result TEXT NOT NULL,
            details TEXT
        )
        """
    )

    connection.execute(
        """
        INSERT INTO users (
            username,
            password_hash,
            created_at,
            enabled,
            role
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "administrator",
            "pytest-password-hash",
            "2026-01-01T00:00:00+00:00",
            1,
            ROLE_ADMINISTRATOR,
        ),
    )

    connection.commit()
    connection.close()


def test_index_passes_user_role_to_template(
    monkeypatch,
    tmp_path,
):
    from flask import template_rendered
    from server import app as app_module

    db_path = str(
        tmp_path / "index-user-role.db"
    )

    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    rendered = {}

    def capture_template(sender, template, context):
        rendered["template"] = template.name
        rendered["user_role"] = context.get("user_role")

    template_rendered.connect(
        capture_template,
        app,
    )

    with app.test_client() as client:
        login_as(
            client,
            1,
            "administrator",
        )

        response = client.get("/")

    assert response.status_code == 200
    assert rendered["template"] == "index.html"
    assert rendered["user_role"] == ROLE_ADMINISTRATOR

def test_real_route_create_user_as_administrator(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "real-create-user.db"
    )

    create_user_test_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(
            client,
            1,
            "administrator",
        )

        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/users",
            headers={
                "X-CSRF-Token": "pytest-csrf-token",
            },
            json={
                "username": "test-operator",
                "password": "pytest-password-123",
                "role": ROLE_OPERATOR,
            },
        )

    assert response.status_code == 201

    data = response.get_json()

    assert data["status"] == "created"
    assert data["user"]["username"] == "test-operator"
    assert data["user"]["role"] == ROLE_OPERATOR
    assert data["user"]["enabled"] is True

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    user = connection.execute(
        """
        SELECT
            id,
            username,
            password_hash,
            enabled,
            role
        FROM users
        WHERE username = ?
        """,
        ("test-operator",),
    ).fetchone()

    audit = connection.execute(
        """
        SELECT
            actor_type,
            actor_id,
            action,
            target,
            result,
            details
        FROM audit_log
        WHERE action = 'user.create'
        """
    ).fetchone()

    connection.close()

    assert user is not None
    assert user["username"] == "test-operator"
    assert user["enabled"] == 1
    assert user["role"] == ROLE_OPERATOR
    assert user["password_hash"] != "pytest-password-123"
    assert user["password_hash"].startswith("$argon2")

    assert audit is not None
    assert audit["actor_type"] == "user"
    assert audit["actor_id"] == "1"
    assert audit["action"] == "user.create"
    assert audit["target"] == f"user:{user['id']}"
    assert audit["result"] == "success"
    assert audit["details"] == (
        "username=test-operator, role=operator"
    )
    assert "pytest-password-123" not in audit["details"]


@pytest.mark.parametrize(
    "user_id,username,role",
    [
        (2, "operator", ROLE_OPERATOR),
        (3, "viewer", ROLE_VIEWER),
    ],
)
def test_real_route_create_user_requires_administrator(
    monkeypatch,
    tmp_path,
    user_id,
    username,
    role,
):
    from server import app as app_module

    db_path = str(
        tmp_path / f"real-create-user-{role}.db"
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
            "/api/users",
            json={
                "username": "should-not-exist",
                "password": "pytest-password-123",
                "role": ROLE_OPERATOR,
            },
        )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required",
    }


def test_real_route_create_user_rejects_short_password(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "real-create-user-short-password.db"
    )

    create_user_test_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(
            client,
            1,
            "administrator",
        )

        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/users",
            headers={
                "X-CSRF-Token": "pytest-csrf-token",
            },
            json={
                "username": "short-password-user",
                "password": "short",
                "role": ROLE_OPERATOR,
            },
        )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "password_too_short",
    }


def test_real_route_create_user_rejects_invalid_role(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "real-create-user-invalid-role.db"
    )

    create_user_test_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(
            client,
            1,
            "administrator",
        )

        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/users",
            headers={
                "X-CSRF-Token": "pytest-csrf-token",
            },
            json={
                "username": "invalid-role-user",
                "password": "pytest-password-123",
                "role": "superuser",
            },
        )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_user_role",
    }


def test_real_route_create_user_rejects_duplicate_username(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "real-create-user-duplicate.db"
    )

    create_user_test_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(
            client,
            1,
            "administrator",
        )

        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/users",
            headers={
                "X-CSRF-Token": "pytest-csrf-token",
            },
            json={
                "username": "administrator",
                "password": "pytest-password-123",
                "role": ROLE_OPERATOR,
            },
        )

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "user_already_exists",
    }


def test_real_route_create_user_requires_csrf(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "real-create-user-csrf.db"
    )

    create_user_test_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(
            client,
            1,
            "administrator",
        )

        response = client.post(
            "/api/users",
            json={
                "username": "csrf-user",
                "password": "pytest-password-123",
                "role": ROLE_OPERATOR,
            },
        )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "csrf_validation_failed",
    }


def test_real_route_create_user_requires_username(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "real-create-user-no-username.db"
    )

    create_user_test_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(
            client,
            1,
            "administrator",
        )

        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/users",
            headers={
                "X-CSRF-Token": "pytest-csrf-token",
            },
            json={
                "username": "",
                "password": "pytest-password-123",
                "role": ROLE_OPERATOR,
            },
        )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "username_required",
    }


def test_list_users_as_administrator(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "list-users-admin.db"
    )

    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(
            client,
            1,
            "administrator",
        )

        response = client.get("/api/users")

    assert response.status_code == 200

    users = response.get_json()

    assert isinstance(users, list)
    assert len(users) >= 1
    assert all(
        "password_hash" not in user
        for user in users
    )


def test_list_users_denied_for_operator(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "list-users-operator.db"
    )

    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        2,
        "operator",
    )

    with app.test_client() as client:
        login_as(
            client,
            2,
            "operator",
        )

        response = client.get("/api/users")

    assert response.status_code == 403


def test_list_users_denied_for_viewer(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "list-users-viewer.db"
    )

    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        3,
        "viewer",
    )

    with app.test_client() as client:
        login_as(
            client,
            3,
            "viewer",
        )

        response = client.get("/api/users")

    assert response.status_code == 403


@pytest.mark.parametrize(
    "user_id,username",
    [
        (1, "administrator"),
        (2, "operator"),
    ],
)
def test_client_page_shows_management_sections_for_operator_and_administrator(
    monkeypatch,
    tmp_path,
    user_id,
    username,
):
    from server import app as app_module

    db_path = str(
        tmp_path / f"client-page-{username}.db"
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

        response = client.get("/client?id=1")

    assert response.status_code == 200
    assert b">Updates<" in response.data
    assert b">Update-Jobs<" in response.data
    assert b">Update-Verlauf<" in response.data
    assert b">Paketverwaltung<" in response.data
    assert b'id="package-management"' in response.data
    assert b"window.lumsUserRole" in response.data


def test_client_page_shows_only_installed_software_for_viewer(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "client-page-viewer.db"
    )

    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        3,
        "viewer",
    )

    with app.test_client() as client:
        login_as(
            client,
            3,
            "viewer",
        )

        response = client.get("/client?id=1")

    assert response.status_code == 200
    assert b"Installierte Software und Systempakete" in response.data
    assert b'id="package-search"' in response.data
    assert b'id="packages-table"' in response.data

    assert b"<h2>Updates</h2>" not in response.data
    assert b"<h2>Update-Jobs</h2>" not in response.data
    assert b"<h2>Update-Verlauf</h2>" not in response.data
    assert b"<h2>Paketverwaltung</h2>" not in response.data
    assert b'id="package-management"' not in response.data
    assert "System vollständig aktualisieren".encode("utf-8") not in response.data
    assert b"Systemwartung" not in response.data
    assert b"window.lumsUserRole" in response.data


def test_users_page_visible_for_administrator(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "users-admin-ui.db"
    )

    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(
            client,
            1,
            "administrator",
        )

        response = client.get("/users")

    assert response.status_code == 200
    assert b'id="user-management"' in response.data
    assert b'id="users-list-status"' in response.data
    assert b'id="users-list-container"' in response.data
    assert b'id="users-list-body"' in response.data


def test_users_page_denied_for_operator(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "users-operator-ui.db"
    )

    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        2,
        "operator",
    )

    with app.test_client() as client:
        login_as(
            client,
            2,
            "operator",
        )

        response = client.get("/users")

    assert response.status_code == 403


def test_users_page_denied_for_viewer(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(
        tmp_path / "users-viewer-ui.db"
    )

    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        3,
        "viewer",
    )

    with app.test_client() as client:
        login_as(
            client,
            3,
            "viewer",
        )

        response = client.get("/users")

    assert response.status_code == 403


def test_real_route_delete_user_as_administrator(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "real-delete-user.db")
    create_user_test_database(db_path)

    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        INSERT INTO users (
            username, password_hash, created_at, enabled, role
        )
        VALUES (?, ?, ?, 1, ?)
        """,
        (
            "delete-me",
            "pytest-password-hash",
            "2026-01-02T00:00:00+00:00",
            ROLE_OPERATOR,
        ),
    )
    target_id = connection.execute(
        "SELECT id FROM users WHERE username = ?",
        ("delete-me",),
    ).fetchone()[0]
    connection.commit()
    connection.close()

    app = configure_real_app_session_user(
        monkeypatch, app_module, db_path, 1, "administrator"
    )

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.delete(
            f"/api/users/{target_id}",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
        )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "deleted",
        "user_id": target_id,
    }

    connection = sqlite3.connect(db_path)
    remaining = connection.execute(
        "SELECT id FROM users WHERE id = ?", (target_id,)
    ).fetchone()
    audit = connection.execute(
        """
        SELECT actor_id, action, target, result, details
        FROM audit_log
        WHERE action = 'user.delete'
        """
    ).fetchone()
    connection.close()

    assert remaining is None
    assert audit is not None
    assert audit[0] == "1"
    assert audit[1] == "user.delete"
    assert audit[2] == f"user:{target_id}"
    assert audit[3] == "success"
    assert "delete-me" in audit[4]


def test_real_route_delete_user_rejects_self_deletion(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "delete-self.db")
    create_user_test_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch, app_module, db_path, 1, "administrator"
    )

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.delete(
            "/api/users/1",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
        )

    assert response.status_code == 400
    assert response.get_json() == {"error": "cannot_delete_self"}

    connection = sqlite3.connect(db_path)
    user = connection.execute(
        "SELECT username FROM users WHERE id = 1"
    ).fetchone()
    connection.close()
    assert user == ("administrator",)


def test_real_route_delete_user_requires_csrf(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "delete-csrf.db")
    create_user_test_database(db_path)

    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        INSERT INTO users (
            username, password_hash, created_at, enabled, role
        )
        VALUES (?, ?, ?, 1, ?)
        """,
        (
            "delete-me",
            "pytest-password-hash",
            "2026-01-02T00:00:00+00:00",
            ROLE_OPERATOR,
        ),
    )
    target_id = connection.execute(
        "SELECT id FROM users WHERE username = ?",
        ("delete-me",),
    ).fetchone()[0]
    connection.commit()
    connection.close()

    app = configure_real_app_session_user(
        monkeypatch, app_module, db_path, 1, "administrator"
    )

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        response = client.delete(f"/api/users/{target_id}")

    assert response.status_code == 400
    assert response.get_json() == {"error": "csrf_validation_failed"}

    connection = sqlite3.connect(db_path)
    user = connection.execute(
        "SELECT username FROM users WHERE id = ?", (target_id,)
    ).fetchone()
    connection.close()
    assert user == ("delete-me",)



def test_real_route_delete_user_preserves_enabled_administrator(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "delete-admin-preserves-one.db")
    create_user_test_database(db_path)

    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        INSERT INTO users (
            username, password_hash, created_at, enabled, role
        )
        VALUES (?, ?, ?, 1, ?)
        """,
        (
            "second-admin",
            "pytest-password-hash",
            "2026-01-02T00:00:00+00:00",
            ROLE_ADMINISTRATOR,
        ),
    )
    second_admin_id = connection.execute(
        "SELECT id FROM users WHERE username = ?",
        ("second-admin",),
    ).fetchone()[0]
    connection.commit()
    connection.close()

    app = configure_real_app_session_user(
        monkeypatch, app_module, db_path, 1, "administrator"
    )

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.delete(
            f"/api/users/{second_admin_id}",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
        )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "deleted",
        "user_id": second_admin_id,
    }

    connection = sqlite3.connect(db_path)
    remaining_admins = connection.execute(
        "SELECT id FROM users WHERE enabled = 1 AND role = ?",
        (ROLE_ADMINISTRATOR,),
    ).fetchall()
    connection.close()

    assert remaining_admins == [(1,)]
