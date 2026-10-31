import sqlite3

import pytest

from server import create_admin as admin_cli
from server import security_migration as migration
from server.security import (
    ROLE_ADMINISTRATOR,
    ROLE_DEFAULT_PERMISSIONS,
    resolve_user_permissions,
)


TEST_PASSWORD = "pytest-only-password-2026"


def create_legacy_database(path):
    """Create an isolated database with the pre-security clients schema."""
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")

    connection.executescript("""
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT UNIQUE,
            ip TEXT,
            os TEXT,
            kernel TEXT,
            architecture TEXT,
            agent_version TEXT,
            last_seen TEXT NOT NULL,
            idle INTEGER NOT NULL DEFAULT 0,
            idle_seconds INTEGER NOT NULL DEFAULT 0,
            idle_threshold_seconds INTEGER NOT NULL DEFAULT 300,
            idle_source TEXT NOT NULL DEFAULT 'unknown',
            idle_supported INTEGER NOT NULL DEFAULT 0
        );

        INSERT INTO clients (hostname, ip, last_seen)
        VALUES (
            'create-admin-test-client',
            '192.0.2.20',
            '2026-01-01T00:00:00+00:00'
        );
    """)

    connection.commit()
    connection.close()


def set_test_password(monkeypatch):
    monkeypatch.setattr(
        admin_cli.getpass,
        "getpass",
        lambda _prompt: TEST_PASSWORD,
    )


def create_admin_without_prompt(monkeypatch, db_path, username):
    set_test_password(monkeypatch)
    admin_cli.create_admin(str(db_path), username)


def activate_custom_rbac_after_cli_bootstrap(
    db_path,
    monkeypatch,
):
    """Exercise the real migration runner around CLI administrator creation."""
    migration.run_migration(
        db_path=str(db_path),
        admin_username="unused-bootstrap-admin",
        skip_admin=True,
    )

    with sqlite3.connect(db_path) as connection:
        versions = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations"
            )
        }

    assert migration.PERMISSIONS_MIGRATION_VERSION in versions
    assert migration.PERMISSION_DELEGATION_MIGRATION_VERSION not in versions
    assert migration.CUSTOM_RBAC_MIGRATION_VERSION not in versions

    create_admin_without_prompt(
        monkeypatch,
        db_path,
        "bootstrap-admin",
    )

    migration.run_migration(
        db_path=str(db_path),
        admin_username="unused-bootstrap-admin",
        skip_admin=True,
    )

    with sqlite3.connect(db_path) as connection:
        versions = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations"
            )
        }

    assert migration.PERMISSION_DELEGATION_MIGRATION_VERSION in versions
    assert migration.CUSTOM_RBAC_MIGRATION_VERSION in versions


def get_user_id(connection, username):
    row = connection.execute(
        "SELECT id FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    assert row is not None
    return row[0]


def test_cli_admin_created_before_custom_rbac_gets_permissions(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "cli-admin-bootstrap.sqlite"
    create_legacy_database(db_path)

    migration.run_migration(
        db_path=str(db_path),
        admin_username="unused-bootstrap-admin",
        skip_admin=True,
    )

    create_admin_without_prompt(
        monkeypatch,
        db_path,
        "bootstrap-admin",
    )

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        user_id = get_user_id(connection, "bootstrap-admin")

        legacy_permissions = {
            row[0]
            for row in connection.execute(
                """
                SELECT permission
                FROM user_permissions
                WHERE user_id = ?
                """,
                (user_id,),
            )
        }

        assert legacy_permissions == set(
            ROLE_DEFAULT_PERMISSIONS[ROLE_ADMINISTRATOR]
        )

        audit_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM audit_log
            WHERE action = 'admin_created'
              AND target = ?
              AND result = 'success'
            """,
            (f"user:{user_id}",),
        ).fetchone()[0]

        assert audit_count == 1

    migration.run_migration(
        db_path=str(db_path),
        admin_username="unused-bootstrap-admin",
        skip_admin=True,
    )

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        user_id = get_user_id(connection, "bootstrap-admin")

        effective_permissions = resolve_user_permissions(
            connection,
            user_id,
            user_role=ROLE_ADMINISTRATOR,
        )

        assert set(ROLE_DEFAULT_PERMISSIONS[ROLE_ADMINISTRATOR]) <= (
            effective_permissions
        )
        assert "permissions.manage" in effective_permissions


def test_cli_admin_created_after_custom_rbac_gets_system_role(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "cli-admin-custom-rbac.sqlite"
    create_legacy_database(db_path)

    activate_custom_rbac_after_cli_bootstrap(
        db_path,
        monkeypatch,
    )

    create_admin_without_prompt(
        monkeypatch,
        db_path,
        "late-admin",
    )

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        user_id = get_user_id(connection, "late-admin")

        assignments = connection.execute(
            """
            SELECT COUNT(*)
            FROM user_roles
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()[0]

        assert assignments == 1

        effective_permissions = resolve_user_permissions(
            connection,
            user_id,
            user_role=ROLE_ADMINISTRATOR,
        )

        assert effective_permissions == set(
            ROLE_DEFAULT_PERMISSIONS[ROLE_ADMINISTRATOR]
        )
        assert "permissions.manage" not in effective_permissions

        audit_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM audit_log
            WHERE action = 'admin_created'
              AND target = ?
              AND result = 'success'
            """,
            (f"user:{user_id}",),
        ).fetchone()[0]

        assert audit_count == 1


def test_cli_admin_rolls_back_user_and_audit_on_rbac_failure(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "cli-admin-rollback.sqlite"
    create_legacy_database(db_path)

    activate_custom_rbac_after_cli_bootstrap(
        db_path,
        monkeypatch,
    )

    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TRIGGER reject_cli_admin_role
            BEFORE INSERT ON user_roles
            BEGIN
                SELECT RAISE(ABORT, 'simulated role assignment failure');
            END
        """)
        connection.commit()

    set_test_password(monkeypatch)

    with pytest.raises(
        sqlite3.IntegrityError,
        match="simulated role assignment failure",
    ):
        admin_cli.create_admin(str(db_path), "rollback-admin")

    with sqlite3.connect(db_path) as connection:
        user_count = connection.execute(
            "SELECT COUNT(*) FROM users WHERE username = ?",
            ("rollback-admin",),
        ).fetchone()[0]

        audit_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM audit_log
            WHERE action = 'admin_created'
              AND details LIKE ?
            """,
            ("%rollback-admin%",),
        ).fetchone()[0]

        assert user_count == 0
        assert audit_count == 0
