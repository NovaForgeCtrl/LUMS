import sqlite3

import pytest


@pytest.fixture
def guard_test_context(monkeypatch, tmp_path):
    from server import app as app_module

    db_path = str(tmp_path / "empty-system-update-guard.db")
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    connection.executescript("""
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'administrator',
            admin_note TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE user_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            PRIMARY KEY (user_id, permission)
        );

        CREATE TABLE clients (
            id INTEGER PRIMARY KEY,
            hostname TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE available_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            package TEXT NOT NULL,
            installed_version TEXT,
            available_version TEXT
        );

        CREATE TABLE update_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            action TEXT NOT NULL
        );

        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor_type TEXT,
            actor_id TEXT,
            action TEXT NOT NULL,
            target TEXT,
            result TEXT,
            details TEXT
        );
    """)

    connection.execute("""
        INSERT INTO users (
            id, username, password_hash, created_at, enabled, role
        ) VALUES (1, 'guard-admin', 'not-used', '2026-01-01T00:00:00+00:00',
                  1, 'administrator')
    """)
    connection.executemany(
        """
        INSERT INTO user_permissions (user_id, permission)
        VALUES (1, ?)
        """,
        [
            ("clients.view",),
            ("updates.view",),
            ("jobs.manage",),
        ],
    )
    connection.execute("""
        INSERT INTO clients (id, hostname, enabled)
        VALUES (1, 'guard-test-client', 1)
    """)
    connection.commit()
    connection.close()

    def get_test_connection():
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        return db

    monkeypatch.setitem(
        app_module.app.config,
        "LUMS_GET_CONNECTION",
        get_test_connection,
    )
    monkeypatch.setattr(app_module, "get_connection", get_test_connection)

    app_module.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    client = app_module.app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["username"] = "guard-admin"
        session["csrf_token"] = "pytest-csrf-token"

    yield client, db_path

    monkeypatch.setitem(
        app_module.app.config,
        "LUMS_GET_CONNECTION",
        None,
    )


def test_update_system_without_available_updates_creates_no_job(
    guard_test_context,
):
    client, db_path = guard_test_context

    response = client.post(
        "/api/clients/1/update-jobs",
        json={"action": "UPDATE_SYSTEM"},
        headers={"X-CSRF-Token": "pytest-csrf-token"},
    )

    assert response.status_code == 409
    assert response.get_json()["status"] == "error"
    assert "No system updates are available" in response.get_json()["message"]

    connection = sqlite3.connect(db_path)
    job_count = connection.execute(
        "SELECT COUNT(*) FROM update_jobs"
    ).fetchone()[0]
    connection.close()

    assert job_count == 0


def test_update_system_with_available_updates_creates_job(
    guard_test_context,
):
    client, db_path = guard_test_context

    connection = sqlite3.connect(db_path)
    connection.execute("""
        INSERT INTO available_updates (
            client_id, package, installed_version, available_version
        ) VALUES (1, 'test-package', '1.0', '1.1')
    """)
    connection.commit()
    connection.close()

    response = client.post(
        "/api/clients/1/update-jobs",
        json={"action": "UPDATE_SYSTEM"},
        headers={"X-CSRF-Token": "pytest-csrf-token"},
    )

    assert response.status_code == 201
    result = response.get_json()
    assert result["status"] == "created"
    assert result["action"] == "UPDATE_SYSTEM"
    assert result["client_id"] == 1

    connection = sqlite3.connect(db_path)
    job = connection.execute("""
        SELECT client_id, status, action
        FROM update_jobs
    """).fetchone()
    job_count = connection.execute(
        "SELECT COUNT(*) FROM update_jobs"
    ).fetchone()[0]
    connection.close()

    assert job_count == 1
    assert job == (1, "pending", "UPDATE_SYSTEM")
