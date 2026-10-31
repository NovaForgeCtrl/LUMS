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
    ROLE_DEFAULT_PERMISSIONS,
    VALID_ROLES,
    _calculate_effective_permissions,
    _filter_permission_dependencies,
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
            role TEXT NOT NULL DEFAULT 'administrator',
            admin_note TEXT NOT NULL DEFAULT ''
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

    connection.execute(
        """
        CREATE TABLE user_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            PRIMARY KEY (user_id, permission),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO user_permissions (user_id, permission)
        VALUES (?, ?)
        """,
        [
            (user_id, permission)
            for user_id, role in [
                (1, ROLE_ADMINISTRATOR),
                (2, ROLE_OPERATOR),
                (3, ROLE_VIEWER),
            ]
            for permission in ROLE_DEFAULT_PERMISSIONS[role]
        ],
    )

    connection.execute(
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )

    from server.security_migration import migrate_user_profiles
    migrate_user_profiles(connection)

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
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


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
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


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
        CREATE TABLE user_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            PRIMARY KEY (user_id, permission),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
    connection.executemany(
        """
        INSERT INTO user_permissions (user_id, permission)
        VALUES (1, ?)
        """,
        [
            (permission,)
            for permission in ROLE_DEFAULT_PERMISSIONS[ROLE_ADMINISTRATOR]
        ],
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
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'administrator',
            admin_note TEXT NOT NULL DEFAULT ''
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
        CREATE TABLE user_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            PRIMARY KEY (user_id, permission),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
    connection.executemany(
        """
        INSERT INTO user_permissions (user_id, permission)
        VALUES (1, ?)
        """,
        [
            (permission,)
            for permission in ROLE_DEFAULT_PERMISSIONS[ROLE_ADMINISTRATOR]
        ],
    )

    from server.security_migration import migrate_user_profiles
    migrate_user_profiles(connection)

    connection.commit()
    connection.close()


def grant_test_permission(db_path, user_id, permission):
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        INSERT OR IGNORE INTO user_permissions (user_id, permission)
        VALUES (?, ?)
        """,
        (user_id, permission),
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
    grant_test_permission(db_path, 1, "permissions.manage")

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
    assert data["user"]["permissions"] == sorted(
        ROLE_DEFAULT_PERMISSIONS[ROLE_OPERATOR]
    )
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
        "username=test-operator, role=operator, "
        "permissions=clients.view,jobs.manage,packages.search,"
        "software.view,updates.view"
    )
    assert "pytest-password-123" not in audit["details"]


def test_permission_migration_seeds_role_presets():
    from server.security_migration import migrate_user_permissions

    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            role TEXT NOT NULL
        )
        """
    )
    connection.executemany(
        "INSERT INTO users (id, role) VALUES (?, ?)",
        [
            (1, ROLE_ADMINISTRATOR),
            (2, ROLE_OPERATOR),
            (3, ROLE_VIEWER),
        ],
    )

    migrate_user_permissions(connection)

    for user_id, role in [
        (1, ROLE_ADMINISTRATOR),
        (2, ROLE_OPERATOR),
        (3, ROLE_VIEWER),
    ]:
        stored = {
            row[0]
            for row in connection.execute(
                "SELECT permission FROM user_permissions WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        }
        assert stored == ROLE_DEFAULT_PERMISSIONS[role]

    connection.close()


def test_create_user_stores_custom_permissions(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "create-user-custom-permissions.db")
    create_user_test_database(db_path)
    grant_test_permission(db_path, 1, "permissions.manage")
    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )
    permissions = ["clients.view", "software.view"]

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/users",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={
                "username": "inventory-reader",
                "password": "pytest-password-123",
                "role": ROLE_OPERATOR,
                "permissions": permissions,
            },
        )

    assert response.status_code == 201
    assert response.get_json()["user"]["permissions"] == permissions

    connection = sqlite3.connect(db_path)
    stored_permissions = [
        row[0]
        for row in connection.execute(
            """
            SELECT permission
            FROM user_permissions
            WHERE user_id = 2
            ORDER BY permission
            """
        ).fetchall()
    ]
    connection.close()
    assert stored_permissions == permissions


def test_user_admin_note_migration_adds_empty_note():
    from server.security_migration import migrate_user_admin_notes

    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO users (id, username) VALUES (1, 'existing-user')"
    )

    migrate_user_admin_notes(connection)

    assert connection.execute(
        "SELECT admin_note FROM users WHERE id = 1"
    ).fetchone()[0] == ""
    connection.close()


def test_user_admin_note_migration_is_idempotent():
    from server.security_migration import migrate_user_admin_notes

    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY)"
    )

    migrate_user_admin_notes(connection)
    migrate_user_admin_notes(connection)

    note_columns = [
        row[1]
        for row in connection.execute("PRAGMA table_info(users)")
    ]
    assert note_columns.count("admin_note") == 1
    connection.close()


def test_backup_permission_migration_grants_existing_administrators():
    from server.security_migration import migrate_backup_permission

    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, role TEXT NOT NULL)"
    )
    connection.execute(
        """
        CREATE TABLE user_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            PRIMARY KEY (user_id, permission)
        )
        """
    )
    connection.executemany(
        "INSERT INTO users (id, role) VALUES (?, ?)",
        [
            (1, ROLE_ADMINISTRATOR),
            (2, ROLE_OPERATOR),
        ],
    )

    migrate_backup_permission(connection)
    migrate_backup_permission(connection)

    assert connection.execute(
        """
        SELECT user_id, permission
        FROM user_permissions
        ORDER BY user_id, permission
        """
    ).fetchall() == [(1, "backups.manage")]
    connection.close()


def test_admin_without_delegation_cannot_assign_permissions(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "admin-without-delegation.db")
    create_user_test_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/users",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={
                "username": "must-not-receive-rights",
                "password": "pytest-password-123",
                "role": ROLE_VIEWER,
                "permissions": ["clients.view"],
            },
        )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "permission_delegation_required",
    }


def test_create_user_starts_without_permissions(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "create-user-unassigned-permissions.db")
    create_user_test_database(db_path)
    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/users",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={
                "username": "needs-manual-permissions",
                "password": "pytest-password-123",
                "role": ROLE_VIEWER,
                "permissions": [],
            },
        )

    assert response.status_code == 201
    assert response.get_json()["user"]["permissions"] == []

    connection = sqlite3.connect(db_path)
    stored_permissions = connection.execute(
        "SELECT permission FROM user_permissions WHERE user_id = 2"
    ).fetchall()
    connection.close()
    assert stored_permissions == []


def test_admin_note_can_be_saved_without_auditing_note_content(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "admin-note.db")
    create_user_test_database(db_path)
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        INSERT INTO users (
            username, password_hash, created_at, enabled, role
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "noted-user",
            "pytest-password-hash",
            "2026-01-01T00:00:00+00:00",
            1,
            ROLE_VIEWER,
        ),
    )
    connection.commit()
    connection.close()

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )
    note = "Internal follow-up: <script>not executable</script>"

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.put(
            "/api/users/2/note",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={"note": note},
        )
        users_response = client.get("/api/users")

    assert response.status_code == 200
    assert response.get_json()["note"] == note
    assert users_response.status_code == 200
    assert users_response.get_json()[1]["admin_note"] == note

    connection = sqlite3.connect(db_path)
    saved_note = connection.execute(
        "SELECT admin_note FROM users WHERE id = 2"
    ).fetchone()[0]
    audit_details = connection.execute(
        "SELECT details FROM audit_log WHERE action = 'user.admin_note.update'"
    ).fetchone()[0]
    connection.close()

    assert saved_note == note
    assert note not in audit_details


def test_admin_note_rejects_oversized_value(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "oversized-admin-note.db")
    create_user_test_database(db_path)
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        INSERT INTO users (
            username, password_hash, created_at, enabled, role
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "noted-user",
            "pytest-password-hash",
            "2026-01-01T00:00:00+00:00",
            1,
            ROLE_VIEWER,
        ),
    )
    connection.commit()
    connection.close()
    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.put(
            "/api/users/2/note",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={"note": "x" * 2001},
        )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_admin_note",
    }


def test_admin_note_endpoint_requires_user_management_permission(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "admin-note-permission.db")
    create_rbac_database(db_path)
    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        2,
        "operator",
    )

    with app.test_client() as client:
        login_as(client, 2, "operator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.put(
            "/api/users/1/note",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={"note": "not authorized"},
        )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required",
    }


def test_administrator_can_create_and_list_database_backups(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "admin-backup.db")
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    create_rbac_database(db_path)
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY,
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
    connection.commit()
    connection.close()
    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )
    app.config["LUMS_BACKUP_DIR"] = backup_directory
    monkeypatch.setattr(app_module, "DB_PATH", db_path)

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/backups",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={
                "format": "db",
                "path": "nas/manual",
            },
        )
        backups_response = client.get("/api/backups?path=nas/manual")
        page_response = client.get("/backups")

    assert response.status_code == 201
    backup = response.get_json()["backup"]
    assert backup["filename"].endswith(".db")
    assert backup["size_bytes"] > 0
    assert backups_response.status_code == 200
    assert backups_response.get_json()["backups"][0]["filename"] == (
        backup["filename"]
    )
    assert page_response.status_code == 200
    assert b'id="create-backup-button"' in page_response.data
    assert b'id="backup-location-dialog"' in page_response.data
    assert b'id="backup-relative-path"' in page_response.data
    assert b'id="delete-backup-dialog"' in page_response.data
    assert b'id="confirm-delete-backup-button"' in page_response.data
    assert b"Vorhandene Backups" in page_response.data
    assert b"backup-restore.md" in page_response.data
    assert b'name="path"' not in page_response.data

    connection = sqlite3.connect(
        backup_directory / "nas" / "manual" / backup["filename"]
    )
    assert connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0] == "ok"
    assert connection.execute(
        "SELECT username FROM users WHERE id = 1"
    ).fetchone()[0] == "administrator"
    connection.close()

    connection = sqlite3.connect(db_path)
    assert connection.execute(
        "SELECT action FROM audit_log"
    ).fetchone()[0] == "database.backup.create"
    connection.close()

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        delete_response = client.delete(
            f"/api/backups/{backup['filename']}?path=nas/manual",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
        )
        after_delete_response = client.get(
            "/api/backups?path=nas/manual"
        )

    assert delete_response.status_code == 200
    assert delete_response.get_json() == {
        "status": "deleted",
        "filename": backup["filename"],
    }
    assert after_delete_response.get_json()["backups"] == []

    connection = sqlite3.connect(db_path)
    audit_actions = connection.execute(
        "SELECT action FROM audit_log ORDER BY id"
    ).fetchall()
    connection.close()
    assert audit_actions == [
        ("database.backup.create",),
        ("database.backup.delete",),
    ]



def test_database_backup_remains_created_when_audit_fails(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "backup-audit-create.db")
    backup_directory = tmp_path / "backup-audit-create"
    backup_directory.mkdir()
    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )
    app.config["LUMS_BACKUP_DIR"] = backup_directory
    monkeypatch.setattr(app_module, "DB_PATH", db_path)

    def fail_audit(*args, **kwargs):
        raise sqlite3.OperationalError("simulated audit failure")

    monkeypatch.setattr(app_module, "audit_log", fail_audit)

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/backups",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={"format": "db", "path": "manual"},
        )

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["error"] == "backup_audit_failed"

    backup = payload["backup"]
    backup_path = (
        backup_directory / "manual" / backup["filename"]
    )
    assert backup_path.is_file()
    assert backup_path.stat().st_size == backup["size_bytes"]


def test_database_backup_is_deleted_when_delete_audit_fails(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "backup-audit-delete.db")
    backup_directory = tmp_path / "backup-audit-delete"
    backup_directory.mkdir()
    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )
    app.config["LUMS_BACKUP_DIR"] = backup_directory
    monkeypatch.setattr(app_module, "DB_PATH", db_path)

    backup = app_module.create_database_backup(
        db_path,
        backup_directory,
        "db",
    )
    backup_path = backup_directory / backup["filename"]
    assert backup_path.is_file()

    def fail_audit(*args, **kwargs):
        raise sqlite3.OperationalError("simulated audit failure")

    monkeypatch.setattr(app_module, "audit_log", fail_audit)

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.delete(
            f"/api/backups/{backup['filename']}",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
        )

    assert response.status_code == 500
    assert response.get_json() == {
        "error": "backup_audit_failed",
    }
    assert not backup_path.exists()

def test_database_backup_requires_explicit_permission_and_supports_delegation(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "backup-permission.db")
    create_rbac_database(db_path)
    backup_directory = tmp_path / "operator-backups"
    backup_directory.mkdir()
    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        2,
        "operator",
    )
    app.config["LUMS_BACKUP_DIR"] = backup_directory

    with app.test_client() as client:
        login_as(client, 2, "operator")
        page_response = client.get("/backups")
        api_response = client.get("/api/backups")
        delete_response = client.delete(
            "/api/backups/lums-backup-20261017T000000.000000Z-0123456789abcdef.db",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
        )

    assert page_response.status_code == 403
    assert api_response.status_code == 403
    assert delete_response.status_code == 403

    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        INSERT INTO user_permissions (user_id, permission)
        VALUES (2, 'backups.manage')
        """
    )
    connection.commit()
    connection.close()

    with app.test_client() as client:
        login_as(client, 2, "operator")
        page_response = client.get("/backups")
        api_response = client.get("/api/backups")

    assert page_response.status_code == 200
    assert api_response.status_code == 200


def test_database_backup_rejects_invalid_format(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "invalid-backup-format.db")
    create_rbac_database(db_path)
    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/backups",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={"format": []},
        )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_backup_format",
    }


def test_database_backup_rejects_parent_path_traversal(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "backup-path-traversal.db")
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    create_rbac_database(db_path)
    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )
    app.config["LUMS_BACKUP_DIR"] = backup_directory
    monkeypatch.setattr(app_module, "DB_PATH", db_path)

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/backups",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={"format": "db", "path": "../outside"},
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_backup_path"


@pytest.mark.parametrize(
    "permissions",
    [
        ["jobs.manage"],
        ["clients.view", "unknown.permission"],
        "clients.view",
    ],
)
def test_create_user_rejects_invalid_permissions(
    monkeypatch,
    tmp_path,
    permissions,
):
    from server import app as app_module

    db_path = str(tmp_path / "invalid-user-permissions.db")
    create_user_test_database(db_path)
    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/users",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={
                "username": "invalid-rights",
                "password": "pytest-password-123",
                "role": ROLE_OPERATOR,
                "permissions": permissions,
            },
        )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_user_permissions",
    }


def test_update_user_permissions_controls_custom_role_access(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "update-user-permissions.db")
    create_user_test_database(db_path)
    grant_test_permission(db_path, 1, "permissions.manage")
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        INSERT INTO users (
            username, password_hash, created_at, enabled, role
        )
        VALUES (?, ?, ?, 1, ?)
        """,
        (
            "custom-viewer",
            "pytest-password-hash",
            "2026-01-02T00:00:00+00:00",
            ROLE_VIEWER,
        ),
    )
    connection.commit()
    connection.close()

    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )
    permissions = [
        "clients.view",
        "updates.view",
        "jobs.manage",
    ]

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.put(
            "/api/users/2/permissions",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={
                "role": ROLE_VIEWER,
                "permissions": permissions,
            },
        )

    assert response.status_code == 200
    assert response.get_json()["user"]["permissions"] == sorted(permissions)

    def get_test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    permission_app = Flask(__name__)
    permission_app.secret_key = "pytest-secret"
    permission_app.config["LUMS_GET_CONNECTION"] = get_test_connection

    @permission_app.route("/jobs")
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        permission="jobs.manage",
    )
    def jobs_route():
        return {"status": "allowed"}

    @permission_app.route("/users")
    @login_required
    @role_required(ROLE_ADMINISTRATOR, permission="users.manage")
    def users_route():
        return {"status": "allowed"}

    with permission_app.test_client() as client:
        login_as(client, 2, "custom-viewer")
        assert client.get("/jobs").status_code == 200
        assert client.get("/users").status_code == 403


def test_update_permissions_preserves_last_user_manager(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "preserve-user-manager.db")
    create_user_test_database(db_path)
    grant_test_permission(db_path, 1, "permissions.manage")
    app = configure_real_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.put(
            "/api/users/1/permissions",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={
                "role": ROLE_VIEWER,
                "permissions": ["clients.view"],
            },
        )

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "last_enabled_administrator",
    }


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
    grant_test_permission(db_path, 1, "permissions.manage")

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
    assert ">Update-Aufträge<".encode("utf-8") in response.data
    assert b">Update-Verlauf<" in response.data
    assert b">Paketverwaltung<" in response.data
    assert b'id="package-management"' in response.data
    assert b'"lumsUserRole":' in response.data


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
    assert "<h2>Update-Aufträge</h2>".encode("utf-8") not in response.data
    assert b"<h2>Update-Verlauf</h2>" not in response.data
    assert b"<h2>Paketverwaltung</h2>" not in response.data
    assert b'id="package-management"' not in response.data
    assert "System vollständig aktualisieren".encode("utf-8") not in response.data
    assert b'"jobs.manage"' not in response.data
    assert b'"lumsUserRole":' in response.data


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
    assert b'class="role-template-list"' in response.data
    assert b'id="create-user-permissions"' not in response.data
    assert (
        "Clients und installierte Software ansehen.".encode("utf-8")
        in response.data
    )
    assert (
        "Update-Jobs verwalten.".encode("utf-8")
        in response.data
    )
    assert "Datenbank-Backups.".encode("utf-8") in response.data


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


def test_user_profile_function_id_accepts_integer(monkeypatch, tmp_path):
    from server import app as app_module

    db_path = str(tmp_path / "user-profile-function-id.db")
    create_rbac_database(db_path)

    connection = sqlite3.connect(db_path)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT '',
            actor_type TEXT NOT NULL DEFAULT '',
            actor_id TEXT,
            action TEXT NOT NULL,
            target TEXT,
            result TEXT NOT NULL,
            details TEXT
        )
    """)
    connection.execute(
        "INSERT INTO user_functions (name) VALUES (?)",
        ("Infrastructure",),
    )
    function_id = connection.execute(
        "SELECT id FROM user_functions WHERE name = ?",
        ("Infrastructure",),
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

        response = client.put(
            "/api/users/2/profile",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={
                "first_name": "Ada",
                "last_name": "Lovelace",
                "department": "IT",
                "function_id": function_id,
            },
        )

    assert response.status_code == 200
    assert response.get_json()["function_id"] == function_id

    connection = sqlite3.connect(db_path)
    saved = connection.execute(
        """
        SELECT first_name, last_name, department, function_id
        FROM users WHERE id = 2
        """
    ).fetchone()
    connection.close()

    assert saved == ("Ada", "Lovelace", "IT", function_id)


def test_user_profile_function_id_rejects_string(monkeypatch, tmp_path):
    from server import app as app_module

    db_path = str(tmp_path / "user-profile-string-function-id.db")
    create_rbac_database(db_path)

    app = configure_real_app_session_user(
        monkeypatch, app_module, db_path, 1, "administrator"
    )

    with app.test_client() as client:
        login_as(client, 1, "administrator")
        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.put(
            "/api/users/2/profile",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={
                "first_name": "Ada",
                "last_name": "Lovelace",
                "department": "IT",
                "function_id": "1",
            },
        )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_user_function"}


# ============================================================
# CUSTOM RBAC ROUTE TEST FIXTURES
# ============================================================

def create_custom_rbac_user_test_database(
    db_path,
    *,
    extra_users=(),
):
    """Create a route-test database migrated through custom RBAC 018."""
    from server import security_migration as migration

    create_user_test_database(db_path)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        for username, role in extra_users:
            connection.execute(
                """
                INSERT INTO users (
                    username,
                    password_hash,
                    created_at,
                    enabled,
                    role
                )
                VALUES (?, ?, ?, 1, ?)
                """,
                (
                    username,
                    "pytest-password-hash",
                    "2026-01-02T00:00:00+00:00",
                    role,
                ),
            )

        # Migration 003: populate legacy permissions for every test user.
        migration.migrate_user_permissions(connection)
        migration.record_migration(
            connection,
            migration.PERMISSIONS_MIGRATION_VERSION,
        )

        # The administrator must be allowed to delegate permissions.
        # Its standard role deliberately excludes permissions.manage.
        connection.execute(
            """
            INSERT OR IGNORE INTO user_permissions (user_id, permission)
            VALUES (1, 'permissions.manage')
            """
        )

        # Execute migration 017 rather than merely inserting its marker.
        migration.migrate_alerting_permissions(connection)
        migration.record_migration(
            connection,
            migration.ALERTING_PERMISSIONS_MIGRATION_VERSION,
        )

        # Complete migration 008 before switching to custom RBAC.
        if not migration.migrate_permission_delegation(connection):
            raise RuntimeError(
                "Test fixture has no eligible permission manager for migration 008"
            )
        migration.record_migration(
            connection,
            migration.PERMISSION_DELEGATION_MIGRATION_VERSION,
        )

        connection.commit()

        # Mirror the production transaction boundary for migration 018.
        connection.execute("BEGIN IMMEDIATE")
        migration.migrate_custom_rbac(connection)
        migration.record_migration(
            connection,
            migration.CUSTOM_RBAC_MIGRATION_VERSION,
        )
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def configure_custom_rbac_app_session_user(
    monkeypatch,
    app_module,
    db_path,
    user_id,
    username,
):
    """Configure app routes with foreign keys enabled on every DB connection."""
    def get_test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
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


def test_custom_rbac_create_user_persists_role_and_overrides(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module
    from server.security import resolve_user_permissions

    db_path = str(
        tmp_path / "custom-rbac-create-user.db"
    )
    create_custom_rbac_user_test_database(db_path)

    app = configure_custom_rbac_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    permissions = [
        "alerts.view",
        "clients.view",
        "software.view",
    ]

    with app.test_client() as client:
        login_as(client, 1, "administrator")

        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.post(
            "/api/users",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={
                "username": "custom-operator",
                "password": "pytest-password-123",
                "role": ROLE_OPERATOR,
                "permissions": permissions,
            },
        )

    assert response.status_code == 201
    assert response.get_json()["user"]["permissions"] == permissions

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    assignment = connection.execute(
        """
        SELECT roles.role_key
        FROM user_roles
        JOIN roles ON roles.id = user_roles.role_id
        WHERE user_roles.user_id = 2
        """
    ).fetchall()

    assert len(assignment) == 1
    assert assignment[0]["role_key"] == "system-operator"

    overrides = {
        (row["permission"], row["effect"])
        for row in connection.execute(
            """
            SELECT permission, effect
            FROM user_permission_overrides
            WHERE user_id = 2
            """
        ).fetchall()
    }

    assert overrides == {
        ("alerts.view", "grant"),
        ("jobs.manage", "deny"),
        ("packages.search", "deny"),
        ("updates.view", "deny"),
    }

    # The new route must not write the legacy permission table.
    legacy_rows = connection.execute(
        """
        SELECT COUNT(*)
        FROM user_permissions
        WHERE user_id = 2
        """
    ).fetchone()[0]
    assert legacy_rows == 0

    effective_permissions = resolve_user_permissions(
        connection,
        2,
        ROLE_OPERATOR,
    )
    assert effective_permissions == set(permissions)

    connection.close()


def test_custom_rbac_update_user_persists_role_and_overrides(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module
    from server.security import resolve_user_permissions

    db_path = str(
        tmp_path / "custom-rbac-update-user.db"
    )
    create_custom_rbac_user_test_database(
        db_path,
        extra_users=(("custom-viewer", ROLE_VIEWER),),
    )

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    old_assignment = connection.execute(
        """
        SELECT roles.role_key
        FROM user_roles
        JOIN roles ON roles.id = user_roles.role_id
        WHERE user_roles.user_id = 2
        """
    ).fetchone()

    assert old_assignment is not None
    assert old_assignment["role_key"].startswith("legacy-")
    connection.close()

    app = configure_custom_rbac_app_session_user(
        monkeypatch,
        app_module,
        db_path,
        1,
        "administrator",
    )

    permissions = [
        "clients.view",
        "jobs.manage",
        "updates.view",
    ]

    with app.test_client() as client:
        login_as(client, 1, "administrator")

        with client.session_transaction() as session:
            session["csrf_token"] = "pytest-csrf-token"

        response = client.put(
            "/api/users/2/permissions",
            headers={"X-CSRF-Token": "pytest-csrf-token"},
            json={
                "role": ROLE_VIEWER,
                "permissions": permissions,
            },
        )

    assert response.status_code == 200
    assert response.get_json()["user"]["permissions"] == permissions

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    assignment = connection.execute(
        """
        SELECT roles.role_key
        FROM user_roles
        JOIN roles ON roles.id = user_roles.role_id
        WHERE user_roles.user_id = 2
        """
    ).fetchall()

    assert len(assignment) == 1
    assert assignment[0]["role_key"] == "system-viewer"

    overrides = {
        (row["permission"], row["effect"])
        for row in connection.execute(
            """
            SELECT permission, effect
            FROM user_permission_overrides
            WHERE user_id = 2
            """
        ).fetchall()
    }

    assert overrides == {
        ("jobs.manage", "grant"),
        ("software.view", "deny"),
        ("updates.view", "grant"),
    }

    effective_permissions = resolve_user_permissions(
        connection,
        2,
        ROLE_VIEWER,
    )
    assert effective_permissions == set(permissions)

    connection.close()


# Direct unit tests for custom RBAC permission calculation.
def test_filter_permission_dependencies_keeps_permissions_with_prerequisites():
    permissions = {
        "clients.view", "updates.view", "jobs.manage",
        "alerts.view", "alerts.manage",
    }
    assert _filter_permission_dependencies(permissions) == frozenset(permissions)
    assert permissions == {
        "clients.view", "updates.view", "jobs.manage",
        "alerts.view", "alerts.manage",
    }


def test_filter_permission_dependencies_removes_permissions_with_missing_prerequisites():
    assert _filter_permission_dependencies(
        {"software.view", "updates.view", "packages.search"}
    ) == frozenset()


def test_filter_permission_dependencies_removes_permission_when_one_prerequisite_is_missing():
    assert _filter_permission_dependencies(
        {"clients.view", "jobs.manage"}
    ) == frozenset({"clients.view"})


def test_calculate_effective_permissions_applies_grants_denies_and_dependencies():
    role_permissions = {
        "clients.view", "updates.view", "jobs.manage",
        "alerts.view", "alerts.manage",
    }

    effective = _calculate_effective_permissions(
        role_permissions,
        grants={"software.view"},
        denies={"alerts.view"},
    )

    assert effective == frozenset({
        "clients.view", "updates.view", "jobs.manage", "software.view",
    })
