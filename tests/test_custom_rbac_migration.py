import sqlite3

import pytest

from server import security_migration as migration
from server.security import ROLE_DEFAULT_PERMISSIONS


def create_legacy_rbac_database(
    *,
    missing_markers=(),
    foreign_keys=True,
):
    """Create an isolated database matching the real legacy RBAC schema."""
    connection = sqlite3.connect(":memory:")

    if foreign_keys:
        connection.execute("PRAGMA foreign_keys = ON")

    connection.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'administrator'
        );

        CREATE TABLE user_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            PRIMARY KEY (user_id, permission),
            FOREIGN KEY (user_id)
                REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
    """)

    markers = (
        migration.PERMISSIONS_MIGRATION_VERSION,
        migration.ALERTING_PERMISSIONS_MIGRATION_VERSION,
    )

    connection.executemany(
        """
        INSERT INTO schema_migrations (version, applied_at)
        VALUES (?, ?)
        """,
        [
            (marker, "2026-01-01T00:00:00+00:00")
            for marker in markers
            if marker not in missing_markers
        ],
    )

    return connection


def add_user(connection, user_id, username, role, enabled=1):
    connection.execute(
        """
        INSERT INTO users (
            id, username, password_hash, created_at, enabled, role
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            username,
            "pytest-hash",
            "2026-01-01T00:00:00+00:00",
            enabled,
            role,
        ),
    )


def add_permissions(connection, user_id, permissions):
    connection.executemany(
        """
        INSERT INTO user_permissions (user_id, permission)
        VALUES (?, ?)
        """,
        [
            (user_id, permission)
            for permission in sorted(permissions)
        ],
    )


def run_custom_rbac_migration(connection):
    """Mirror the transaction boundary used by the production runner."""
    # Commit fixture setup before opening the migration transaction.
    connection.commit()

    if migration.migration_already_applied(
        connection,
        migration.CUSTOM_RBAC_MIGRATION_VERSION,
    ):
        return True

    connection.execute("BEGIN IMMEDIATE")

    try:
        migrated = migration.migrate_custom_rbac(connection)

        if not migrated:
            # Commit cleanup, but leave migration 018 pending.
            connection.commit()
            return False

        migration.record_migration(
            connection,
            migration.CUSTOM_RBAC_MIGRATION_VERSION,
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise


def table_names(connection):
    return {
        row[0]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )
    }


def test_custom_rbac_migration_preserves_effective_permissions():
    connection = create_legacy_rbac_database()

    try:
        # Two users with identical permissions must share one migration role.
        add_user(connection, 1, "admin-a", "administrator")
        add_user(connection, 2, "admin-b", "administrator")

        # A different permission set must produce a different role.
        add_user(connection, 3, "viewer", "viewer")

        # A disabled user must also receive exactly one role.
        add_user(
            connection,
            4,
            "disabled-operator",
            "operator",
            enabled=0,
        )

        # An incomplete dependency set becomes empty, exactly as at login.
        add_user(connection, 5, "incomplete", "viewer")

        add_permissions(
            connection,
            1,
            {
                "users.manage",
                "clients.view",
                "updates.view",
                "jobs.manage",
                "permissions.manage",
            },
        )
        add_permissions(
            connection,
            2,
            {
                "users.manage",
                "clients.view",
                "updates.view",
                "jobs.manage",
                "permissions.manage",
            },
        )
        add_permissions(
            connection,
            3,
            {"clients.view"},
        )
        add_permissions(
            connection,
            4,
            {"clients.view", "updates.view"},
        )
        add_permissions(
            connection,
            5,
            {"updates.view"},
        )

        legacy_permissions_before = {
            user_id: {
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
            for user_id in range(1, 6)
        }

        expected_permissions = {
            user_id: migration._effective_permissions_for_migration(
                permissions
            )
            for user_id, permissions in legacy_permissions_before.items()
        }

        run_custom_rbac_migration(connection)

        assert migration.migration_already_applied(
            connection,
            migration.CUSTOM_RBAC_MIGRATION_VERSION,
        )

        assert {
            "roles",
            "role_permissions",
            "user_roles",
            "user_permission_overrides",
        } <= table_names(connection)

        assignments = connection.execute("""
            SELECT user_id, role_id, COUNT(*)
            FROM user_roles
            GROUP BY user_id, role_id
            ORDER BY user_id
        """).fetchall()

        assert len(assignments) == 5
        assert all(row[2] == 1 for row in assignments)

        assigned_roles = {
            user_id: role_id
            for user_id, role_id, _count in assignments
        }

        assert assigned_roles[1] == assigned_roles[2]
        assert assigned_roles[1] != assigned_roles[3]
        assert assigned_roles[4] != assigned_roles[3]

        for user_id, expected in expected_permissions.items():
            actual = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT rp.permission
                    FROM user_roles AS ur
                    JOIN role_permissions AS rp
                      ON rp.role_id = ur.role_id
                    WHERE ur.user_id = ?
                    """,
                    (user_id,),
                )
            }

            assert actual == expected

        # The legacy source must remain untouched.
        legacy_permissions_after = {
            user_id: {
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
            for user_id in range(1, 6)
        }

        assert legacy_permissions_after == legacy_permissions_before

        assert connection.execute(
            "SELECT COUNT(*) FROM user_permission_overrides"
        ).fetchone()[0] == 0

        assert connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall() == []

    finally:
        connection.close()


def test_custom_rbac_migration_seeds_system_roles():
    connection = create_legacy_rbac_database()

    try:
        add_user(connection, 1, "role-seed-admin", "administrator")
        add_permissions(
            connection,
            1,
            {"users.manage", "clients.view"},
        )

        assert run_custom_rbac_migration(connection) is True

        for role_key in ("administrator", "operator", "viewer"):
            role = connection.execute(
                """
                SELECT id, is_system, is_migration
                FROM roles
                WHERE role_key = ?
                """,
                ("system-" + role_key,),
            ).fetchone()

            assert role is not None
            role_id, is_system, is_migration = role

            assert is_system == 1
            assert is_migration == 0

            actual_permissions = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT permission
                    FROM role_permissions
                    WHERE role_id = ?
                    """,
                    (role_id,),
                )
            }

            expected_permissions = (
                migration._effective_permissions_for_migration(
                    ROLE_DEFAULT_PERMISSIONS[role_key]
                )
            )

            assert actual_permissions == expected_permissions

    finally:
        connection.close()


@pytest.mark.parametrize(
    "missing_marker",
    [
        migration.PERMISSIONS_MIGRATION_VERSION,
        migration.ALERTING_PERMISSIONS_MIGRATION_VERSION,
    ],
)
def test_custom_rbac_migration_rejects_missing_prerequisite(
    missing_marker,
):
    connection = create_legacy_rbac_database(
        missing_markers=(missing_marker,),
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="prerequisites are missing",
        ):
            run_custom_rbac_migration(connection)

        assert not {
            "roles",
            "role_permissions",
            "user_roles",
            "user_permission_overrides",
        } & table_names(connection)

        assert not migration.migration_already_applied(
            connection,
            migration.CUSTOM_RBAC_MIGRATION_VERSION,
        )

    finally:
        connection.close()


def test_custom_rbac_migration_rejects_disabled_foreign_keys():
    connection = create_legacy_rbac_database(
        foreign_keys=False,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="foreign keys to be enabled",
        ):
            run_custom_rbac_migration(connection)

        assert not {
            "roles",
            "role_permissions",
            "user_roles",
            "user_permission_overrides",
        } & table_names(connection)

    finally:
        connection.close()


def test_custom_rbac_migration_rejects_invalid_legacy_role():
    connection = create_legacy_rbac_database()

    try:
        add_user(connection, 1, "invalid-role", "unknown-role")
        add_permissions(
            connection,
            1,
            {"users.manage", "clients.view"},
        )

        with pytest.raises(
            RuntimeError,
            match="invalid legacy roles",
        ):
            run_custom_rbac_migration(connection)

        assert not {
            "roles",
            "role_permissions",
            "user_roles",
            "user_permission_overrides",
        } & table_names(connection)

    finally:
        connection.close()


def test_custom_rbac_migration_rejects_unknown_permission():
    connection = create_legacy_rbac_database()

    try:
        add_user(connection, 1, "unknown-permission", "viewer")
        add_permissions(
            connection,
            1,
            {
                "users.manage",
                "clients.view",
                "permission.does.not.exist",
            },
        )

        with pytest.raises(
            RuntimeError,
            match="Unknown legacy permissions",
        ):
            run_custom_rbac_migration(connection)

        assert not {
            "roles",
            "role_permissions",
            "user_roles",
            "user_permission_overrides",
        } & table_names(connection)

    finally:
        connection.close()


def test_custom_rbac_migration_rejects_orphaned_permission():
    connection = create_legacy_rbac_database(
        foreign_keys=False,
    )

    try:
        add_user(connection, 1, "orphan-check-admin", "administrator")
        add_permissions(
            connection,
            1,
            {"users.manage", "clients.view"},
        )

        connection.execute(
            """
            INSERT INTO user_permissions (user_id, permission)
            VALUES (?, ?)
            """,
            (999, "clients.view"),
        )
        connection.commit()

        connection.execute("PRAGMA foreign_keys = ON")

        assert connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0] == 1

        with pytest.raises(
            RuntimeError,
            match="Orphaned user_permissions",
        ):
            run_custom_rbac_migration(connection)

        assert not {
            "roles",
            "role_permissions",
            "user_roles",
            "user_permission_overrides",
        } & table_names(connection)

    finally:
        connection.close()


def test_custom_rbac_migration_rejects_preexisting_target_table():
    connection = create_legacy_rbac_database()

    try:
        add_user(connection, 1, "preexisting-table-admin", "administrator")
        add_permissions(
            connection,
            1,
            {"users.manage", "clients.view"},
        )

        connection.execute("""
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY
            )
        """)
        connection.commit()

        with pytest.raises(
            RuntimeError,
            match="Unexpected pre-existing RBAC tables",
        ):
            run_custom_rbac_migration(connection)

        assert "roles" in table_names(connection)
        assert not migration.migration_already_applied(
            connection,
            migration.CUSTOM_RBAC_MIGRATION_VERSION,
        )

    finally:
        connection.close()


def test_custom_rbac_migration_rolls_back_all_changes_on_late_failure(
    monkeypatch,
):
    connection = create_legacy_rbac_database()

    try:
        add_user(connection, 1, "rollback-user", "viewer")
        add_permissions(
            connection,
            1,
            {"users.manage", "clients.view"},
        )

        original_permissions = connection.execute(
            """
            SELECT user_id, permission
            FROM user_permissions
            ORDER BY user_id, permission
            """
        ).fetchall()

        def fail_foreign_key_validation(_connection):
            raise RuntimeError("simulated late migration failure")

        monkeypatch.setattr(
            migration,
            "_validate_custom_rbac_foreign_keys",
            fail_foreign_key_validation,
        )

        with pytest.raises(
            RuntimeError,
            match="simulated late migration failure",
        ):
            run_custom_rbac_migration(connection)

        assert not {
            "roles",
            "role_permissions",
            "user_roles",
            "user_permission_overrides",
        } & table_names(connection)

        assert connection.execute(
            """
            SELECT user_id, permission
            FROM user_permissions
            ORDER BY user_id, permission
            """
        ).fetchall() == original_permissions

        assert not migration.migration_already_applied(
            connection,
            migration.CUSTOM_RBAC_MIGRATION_VERSION,
        )

    finally:
        connection.close()

def test_custom_rbac_migration_rejects_missing_legacy_table():
    connection = create_legacy_rbac_database()

    try:
        connection.execute("DROP TABLE user_permissions")
        connection.commit()

        with pytest.raises(
            RuntimeError,
            match="user_permissions is missing",
        ):
            run_custom_rbac_migration(connection)

        assert not {
            "roles",
            "role_permissions",
            "user_roles",
            "user_permission_overrides",
        } & table_names(connection)

        assert not migration.migration_already_applied(
            connection,
            migration.CUSTOM_RBAC_MIGRATION_VERSION,
        )

    finally:
        connection.close()


@pytest.mark.parametrize(
    ("schema_sql", "expected_error"),
    [
        (
            """
            CREATE TABLE user_permissions (
                user_id INTEGER NOT NULL,
                permission TEXT NOT NULL,
                PRIMARY KEY (permission, user_id),
                FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            "must have PRIMARY KEY",
        ),
        (
            """
            CREATE TABLE user_permissions (
                user_id INTEGER NOT NULL,
                permission TEXT NOT NULL,
                PRIMARY KEY (user_id, permission),
                FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE RESTRICT
            )
            """,
            "must reference users.id ON DELETE CASCADE",
        ),
    ],
)
def test_custom_rbac_migration_rejects_invalid_legacy_schema(
    schema_sql,
    expected_error,
):
    connection = create_legacy_rbac_database()

    try:
        connection.execute("DROP TABLE user_permissions")
        connection.execute(schema_sql)
        connection.commit()

        with pytest.raises(
            RuntimeError,
            match=expected_error,
        ):
            run_custom_rbac_migration(connection)

        assert not {
            "roles",
            "role_permissions",
            "user_roles",
            "user_permission_overrides",
        } & table_names(connection)

        assert not migration.migration_already_applied(
            connection,
            migration.CUSTOM_RBAC_MIGRATION_VERSION,
        )

    finally:
        connection.close()


def test_custom_rbac_migration_stays_pending_and_can_be_retried():
    connection = create_legacy_rbac_database()

    try:
        add_user(
            connection,
            1,
            "temporarily-disabled-admin",
            "administrator",
            enabled=0,
        )
        add_permissions(
            connection,
            1,
            {
                "users.manage",
                "clients.view",
                "permissions.manage",
            },
        )

        assert run_custom_rbac_migration(connection) is False

        assert not migration.migration_already_applied(
            connection,
            migration.CUSTOM_RBAC_MIGRATION_VERSION,
        )
        assert not {
            "roles",
            "role_permissions",
            "user_roles",
            "user_permission_overrides",
        } & table_names(connection)

        # Invalid delegation cleanup must survive the pending migration.
        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM user_permissions
            WHERE user_id = 1
              AND permission = 'permissions.manage'
            """
        ).fetchone()[0] == 0

        # Nach Aktivierung erfüllt derselbe Benutzer die Voraussetzungen.
        connection.execute(
            "UPDATE users SET enabled = 1 WHERE id = 1"
        )
        connection.commit()

        assert run_custom_rbac_migration(connection) is True
        assert migration.migration_already_applied(
            connection,
            migration.CUSTOM_RBAC_MIGRATION_VERSION,
        )

        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM user_permissions
            WHERE user_id = 1
              AND permission = 'permissions.manage'
            """
        ).fetchone()[0] == 1

    finally:
        connection.close()


def test_custom_rbac_migration_keeps_valid_delegates_and_removes_invalid_grants():
    connection = create_legacy_rbac_database()

    try:
        add_user(connection, 1, "delegate-a", "administrator")
        add_user(connection, 2, "delegate-b", "administrator")
        add_user(
            connection,
            3,
            "disabled-delegate",
            "administrator",
            enabled=0,
        )
        add_user(connection, 4, "incomplete-delegate", "administrator")

        add_permissions(
            connection,
            1,
            {"users.manage", "clients.view", "permissions.manage"},
        )
        add_permissions(
            connection,
            2,
            {"users.manage", "clients.view", "permissions.manage"},
        )
        add_permissions(
            connection,
            3,
            {"users.manage", "clients.view", "permissions.manage"},
        )
        add_permissions(
            connection,
            4,
            {"users.manage", "permissions.manage"},
        )

        assert run_custom_rbac_migration(connection) is True

        delegates = [
            row[0]
            for row in connection.execute(
                """
                SELECT user_id
                FROM user_permissions
                WHERE permission = 'permissions.manage'
                ORDER BY user_id
                """
            )
        ]

        assert delegates == [1, 2]

    finally:
        connection.close()


def test_custom_rbac_migration_repairs_invalid_grants_and_grants_only_first_eligible_user_idempotently():
    connection = create_legacy_rbac_database()

    try:
        add_user(connection, 1, "eligible-admin-first", "administrator")
        add_user(connection, 2, "eligible-admin-second", "administrator")
        add_user(
            connection,
            3,
            "disabled-delegate",
            "administrator",
            enabled=0,
        )
        add_user(connection, 4, "incomplete-delegate", "administrator")

        add_permissions(
            connection,
            1,
            {"users.manage", "clients.view"},
        )
        add_permissions(
            connection,
            2,
            {"users.manage", "clients.view"},
        )
        add_permissions(
            connection,
            3,
            {"users.manage", "clients.view", "permissions.manage"},
        )
        add_permissions(
            connection,
            4,
            {"users.manage", "permissions.manage"},
        )

        assert run_custom_rbac_migration(connection) is True

        delegates = [
            row[0]
            for row in connection.execute(
                """
                SELECT user_id
                FROM user_permissions
                WHERE permission = 'permissions.manage'
                ORDER BY user_id
                """
            )
        ]

        assert delegates == [1]

        assert migration.migration_already_applied(
            connection,
            migration.CUSTOM_RBAC_MIGRATION_VERSION,
        )

        # A repeated invocation must not modify the established delegation.
        assert run_custom_rbac_migration(connection) is True

        delegates_after_retry = [
            row[0]
            for row in connection.execute(
                """
                SELECT user_id
                FROM user_permissions
                WHERE permission = 'permissions.manage'
                ORDER BY user_id
                """
            )
        ]

        assert delegates_after_retry == [1]

    finally:
        connection.close()
