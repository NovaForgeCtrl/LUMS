import sqlite3

import pytest

from server.security_migration import (
    migrate_user_profiles,
    migrate_permission_delegation,
)


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


def test_delegation_migration_grants_one_eligible_active_user(connection):
    result = migrate_permission_delegation(connection)

    assert result is True

    delegated = connection.execute("""
        SELECT user_id
        FROM user_permissions
        WHERE permission = 'permissions.manage'
        ORDER BY user_id
    """).fetchall()

    assert len(delegated) == 1
    assert delegated[0]["user_id"] in (1, 2)

    disabled_has_permission = connection.execute("""
        SELECT 1
        FROM user_permissions
        WHERE user_id = 3 AND permission = 'permissions.manage'
    """).fetchone()

    assert disabled_has_permission is None


def test_delegation_migration_does_not_grant_every_administrator(connection):
    migrate_permission_delegation(connection)

    delegated_count = connection.execute("""
        SELECT COUNT(*)
        FROM user_permissions
        WHERE permission = 'permissions.manage'
    """).fetchone()[0]

    assert delegated_count == 1


def test_delegation_migration_retries_when_no_eligible_user_exists(connection):
    connection.execute("""
        DELETE FROM user_permissions
        WHERE permission = 'clients.view'
    """)

    result = migrate_permission_delegation(connection)

    assert result is False

    assert connection.execute("""
        SELECT COUNT(*)
        FROM user_permissions
        WHERE permission = 'permissions.manage'
    """).fetchone()[0] == 0


def test_delegation_migration_is_idempotent(connection):
    assert migrate_permission_delegation(connection) is True

    first_count = connection.execute("""
        SELECT COUNT(*)
        FROM user_permissions
        WHERE permission = 'permissions.manage'
    """).fetchone()[0]

    assert migrate_permission_delegation(connection) is True

    second_count = connection.execute("""
        SELECT COUNT(*)
        FROM user_permissions
        WHERE permission = 'permissions.manage'
    """).fetchone()[0]

    assert first_count == second_count == 1


def test_delegation_migration_removes_invalid_grants_when_valid_delegate_exists(
    connection,
):
    connection.execute("""
        INSERT INTO user_permissions (user_id, permission)
        VALUES (2, 'permissions.manage')
    """)
    connection.execute("""
        INSERT INTO user_permissions (user_id, permission)
        VALUES (3, 'permissions.manage')
    """)

    result = migrate_permission_delegation(connection)

    assert result is True

    valid_delegates = connection.execute("""
        SELECT p.user_id
        FROM user_permissions AS p
        JOIN users AS u ON u.id = p.user_id
        WHERE p.permission = 'permissions.manage'
          AND u.enabled = 1
          AND EXISTS (
              SELECT 1 FROM user_permissions AS p2
              WHERE p2.user_id = u.id
                AND p2.permission = 'users.manage'
          )
          AND EXISTS (
              SELECT 1 FROM user_permissions AS p3
              WHERE p3.user_id = u.id
                AND p3.permission = 'clients.view'
          )
        ORDER BY p.user_id
    """).fetchall()

    assert [row[0] for row in valid_delegates] == [2]

    invalid_grants = connection.execute("""
        SELECT p.user_id
        FROM user_permissions AS p
        JOIN users AS u ON u.id = p.user_id
        WHERE p.permission = 'permissions.manage'
          AND (
              u.enabled != 1
              OR NOT EXISTS (
                  SELECT 1 FROM user_permissions AS p2
                  WHERE p2.user_id = u.id
                    AND p2.permission = 'users.manage'
              )
              OR NOT EXISTS (
                  SELECT 1 FROM user_permissions AS p3
                  WHERE p3.user_id = u.id
                    AND p3.permission = 'clients.view'
              )
          )
    """).fetchall()

    assert invalid_grants == []


def test_delegation_migration_repairs_invalid_grant_when_no_valid_delegate_exists(
    connection,
):
    connection.execute("""
        INSERT INTO user_permissions (user_id, permission)
        VALUES (3, 'permissions.manage')
    """)

    result = migrate_permission_delegation(connection)

    assert result is True

    delegates = connection.execute("""
        SELECT p.user_id
        FROM user_permissions AS p
        JOIN users AS u ON u.id = p.user_id
        WHERE p.permission = 'permissions.manage'
          AND u.enabled = 1
          AND EXISTS (
              SELECT 1 FROM user_permissions AS p2
              WHERE p2.user_id = u.id
                AND p2.permission = 'users.manage'
          )
          AND EXISTS (
              SELECT 1 FROM user_permissions AS p3
              WHERE p3.user_id = u.id
                AND p3.permission = 'clients.view'
          )
        ORDER BY p.user_id
    """).fetchall()

    assert [row[0] for row in delegates] == [1]

    invalid_grants = connection.execute("""
        SELECT p.user_id
        FROM user_permissions AS p
        JOIN users AS u ON u.id = p.user_id
        WHERE p.permission = 'permissions.manage'
          AND (
              u.enabled != 1
              OR NOT EXISTS (
                  SELECT 1 FROM user_permissions AS p2
                  WHERE p2.user_id = u.id
                    AND p2.permission = 'users.manage'
              )
              OR NOT EXISTS (
                  SELECT 1 FROM user_permissions AS p3
                  WHERE p3.user_id = u.id
                    AND p3.permission = 'clients.view'
              )
          )
    """).fetchall()

    assert invalid_grants == []


def test_delegation_migration_keeps_all_valid_delegates_and_is_idempotent(
    connection,
):
    connection.execute("""
        INSERT INTO user_permissions (user_id, permission)
        VALUES (1, 'permissions.manage')
    """)
    connection.execute("""
        INSERT INTO user_permissions (user_id, permission)
        VALUES (2, 'permissions.manage')
    """)

    assert migrate_permission_delegation(connection) is True

    first_delegates = connection.execute("""
        SELECT user_id
        FROM user_permissions
        WHERE permission = 'permissions.manage'
        ORDER BY user_id
    """).fetchall()

    assert [row[0] for row in first_delegates] == [1, 2]

    assert migrate_permission_delegation(connection) is True

    second_delegates = connection.execute("""
        SELECT user_id
        FROM user_permissions
        WHERE permission = 'permissions.manage'
        ORDER BY user_id
    """).fetchall()

    assert [row[0] for row in second_delegates] == [1, 2]


def test_delegation_migration_removes_invalid_grant_and_retries_without_eligible_user(
    connection,
):
    connection.execute("""
        DELETE FROM user_permissions
        WHERE permission IN ('users.manage', 'clients.view')
    """)
    connection.execute("""
        INSERT INTO user_permissions (user_id, permission)
        VALUES (3, 'permissions.manage')
    """)

    result = migrate_permission_delegation(connection)

    assert result is False

    remaining = connection.execute("""
        SELECT COUNT(*)
        FROM user_permissions
        WHERE permission = 'permissions.manage'
    """).fetchone()[0]

    assert remaining == 0
