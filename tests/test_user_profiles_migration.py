import sqlite3

import pytest

from server.security_migration import migrate_user_profiles


@pytest.fixture
def connection():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    db.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL DEFAULT 'test-hash',
            created_at TEXT NOT NULL DEFAULT '2026-01-01T00:00:00+00:00',
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'viewer'
        );

        CREATE TABLE user_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            PRIMARY KEY (user_id, permission),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        INSERT INTO users (username, role, enabled)
        VALUES
            ('admin-a', 'administrator', 1),
            ('admin-b', 'administrator', 1),
            ('disabled-admin', 'administrator', 0);

        INSERT INTO user_permissions (user_id, permission)
        VALUES
            (1, 'users.manage'),
            (1, 'clients.view'),
            (2, 'users.manage'),
            (2, 'clients.view'),
            (3, 'users.manage'),
            (3, 'clients.view');
    """)

    try:
        yield db
    finally:
        db.close()


def test_user_profile_migration_preserves_existing_users(connection):
    migrate_user_profiles(connection)

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(users)")
    }

    assert {
        "first_name",
        "last_name",
        "department",
        "function_id",
    } <= columns

    user = connection.execute(
        "SELECT username, role, enabled FROM users WHERE id = 1"
    ).fetchone()

    assert tuple(user) == ("admin-a", "administrator", 1)

    table = connection.execute("""
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'user_functions'
    """).fetchone()

    assert table is not None


def test_user_profile_migration_is_idempotent(connection):
    migrate_user_profiles(connection)
    migrate_user_profiles(connection)

    columns = [
        row["name"]
        for row in connection.execute("PRAGMA table_info(users)")
    ]

    assert columns.count("first_name") == 1
    assert columns.count("function_id") == 1


def test_user_functions_are_unique_case_insensitively(connection):
    migrate_user_profiles(connection)

    connection.execute("""
        INSERT INTO user_functions (name)
        VALUES ('Infrastructure')
    """)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("""
            INSERT INTO user_functions (name)
            VALUES ('infrastructure')
        """)
