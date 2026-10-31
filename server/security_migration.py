#!/usr/bin/env python3

import argparse
import hashlib
import os
import sqlite3
import sys
from datetime import datetime, timezone
from getpass import getpass

from argon2 import PasswordHasher
from argon2.exceptions import HashingError

if __package__:
    from .security import (
        PERMISSIONS,
        PERMISSION_DEPENDENCIES,
        ROLE_DEFAULT_PERMISSIONS,
        VALID_ROLES,
    )
else:
    from security import (
        PERMISSIONS,
        PERMISSION_DEPENDENCIES,
        ROLE_DEFAULT_PERMISSIONS,
        VALID_ROLES,
    )


DEFAULT_DB_PATH = "/var/lib/lums/lums.db"
MIGRATION_VERSION = "001-security-foundation"
RBAC_MIGRATION_VERSION = "002-rbac"
PERMISSIONS_MIGRATION_VERSION = "003-user-permissions"
USER_NOTES_MIGRATION_VERSION = "004-user-admin-notes"
BACKUP_PERMISSION_MIGRATION_VERSION = "005-backup-permission"
USER_LANGUAGE_MIGRATION_VERSION = "006-user-language"
USER_PROFILES_MIGRATION_VERSION = "007-user-profiles"
PERMISSION_DELEGATION_MIGRATION_VERSION = "008-permission-delegation"
TELEMETRY_MIGRATION_VERSION = "009-telemetry"
TELEMETRY_RETENTION_INDEX_MIGRATION_VERSION = "010-telemetry-retention-index"
TELEMETRY_NETWORK_MIGRATION_VERSION = "011-telemetry-network"
TELEMETRY_SYSTEM_STATE_MIGRATION_VERSION = "012-telemetry-system-state"
TELEMETRY_DASHBOARD_MIGRATION_VERSION = "013-telemetry-dashboard"
TELEMETRY_EVENT_HISTORY_MIGRATION_VERSION = "014-telemetry-event-history"
SYSTEM_UPDATE_PERMISSION_MIGRATION_VERSION = "015-system-update-permission"
INFRASTRUCTURE_TOPOLOGY_MIGRATION_VERSION = "016-infrastructure-topology"
ALERTING_PERMISSIONS_MIGRATION_VERSION = "017-alerting-permissions"
CUSTOM_RBAC_MIGRATION_VERSION = "018-custom-rbac"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def column_exists(connection, table, column):
    rows = connection.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    return any(row[1] == column for row in rows)


def add_column_if_missing(connection, table, column, definition):
    if column_exists(connection, table, column):
        print(f"[OK] {table}.{column} already exists")
        return

    print(f"[ADD] {table}.{column}")

    connection.execute(
        f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
    )


def create_security_tables(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            action TEXT NOT NULL,
            target TEXT,
            result TEXT NOT NULL,
            details TEXT
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS system_update_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requested_at TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            target_tag TEXT NOT NULL,
            target_commit TEXT NOT NULL,
            status TEXT NOT NULL,
            step TEXT NOT NULL,
            progress_json TEXT NOT NULL DEFAULT '[]',
            details_json TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            rollback_status TEXT,
            updated_at TEXT NOT NULL,
            finished_at TEXT
        )
    """)
    add_column_if_missing(
        connection,
        "system_update_jobs",
        "target_commit",
        "TEXT NOT NULL DEFAULT ''",
    )
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_system_update_jobs_requested
        ON system_update_jobs(requested_at DESC)
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS system_update_agent (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_seen TEXT NOT NULL,
            current_version TEXT,
            deployment TEXT,
            status_message TEXT
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp
        ON audit_log(timestamp)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_actor
        ON audit_log(actor_type, actor_id)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_action
        ON audit_log(action)
    """)


def migrate_rbac(connection):
    add_column_if_missing(
        connection,
        "users",
        "role",
        "TEXT NOT NULL DEFAULT 'administrator'"
    )


def migrate_user_permissions(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            PRIMARY KEY (user_id, permission),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    users = connection.execute(
        "SELECT id, role FROM users"
    ).fetchall()

    for user in users:
        permissions = ROLE_DEFAULT_PERMISSIONS.get(
            user[1],
            ROLE_DEFAULT_PERMISSIONS["viewer"],
        )

        connection.executemany(
            """
            INSERT OR IGNORE INTO user_permissions (user_id, permission)
            VALUES (?, ?)
            """,
            [
                (user[0], permission)
                for permission in permissions
            ],
        )


def migrate_user_admin_notes(connection):
    add_column_if_missing(
        connection,
        "users",
        "admin_note",
        "TEXT NOT NULL DEFAULT ''",
    )


def migrate_backup_permission(connection):
    connection.execute(
        """
        INSERT OR IGNORE INTO user_permissions (user_id, permission)
        SELECT users.id, 'backups.manage'
        FROM users
        WHERE users.role = 'administrator'
        """
    )


def migrate_system_update_permission(connection):
    connection.execute(
        """
        INSERT OR IGNORE INTO user_permissions (user_id, permission)
        SELECT users.id, 'system.update'
        FROM users
        WHERE users.role = 'administrator'
        """
    )


def migrate_infrastructure_topology(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS infrastructure_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            node_type TEXT NOT NULL CHECK (
                node_type IN (
                    'server', 'vm', 'container', 'network_device',
                    'service', 'storage'
                )
            ),
            hostname TEXT NOT NULL DEFAULT '',
            ip_address TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS infrastructure_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_node_id INTEGER,
            source_client_id INTEGER,
            target_node_id INTEGER,
            target_client_id INTEGER,
            relation_type TEXT NOT NULL CHECK (
                relation_type IN (
                    'depends_on', 'hosts', 'connects_to', 'runs_on'
                )
            ),
            details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            created_by INTEGER,
            CHECK (
                (source_node_id IS NOT NULL) != (source_client_id IS NOT NULL)
            ),
            CHECK (
                (target_node_id IS NOT NULL) != (target_client_id IS NOT NULL)
            ),
            FOREIGN KEY (source_node_id)
                REFERENCES infrastructure_nodes(id) ON DELETE CASCADE,
            FOREIGN KEY (source_client_id)
                REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY (target_node_id)
                REFERENCES infrastructure_nodes(id) ON DELETE CASCADE,
            FOREIGN KEY (target_client_id)
                REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_infrastructure_relations_source
        ON infrastructure_relations(
            source_node_id, source_client_id, relation_type
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_infrastructure_relations_target
        ON infrastructure_relations(
            target_node_id, target_client_id, relation_type
        )
    """)
    connection.execute(
        """
        INSERT OR IGNORE INTO user_permissions (user_id, permission)
        SELECT users.id, 'infrastructure.manage'
        FROM users
        WHERE users.role = 'administrator'
        """
    )


def migrate_alerting_permissions(connection):
    """Grant alert permissions to existing administrator accounts."""
    connection.execute(
        """
        INSERT OR IGNORE INTO user_permissions (user_id, permission)
        SELECT users.id, 'alerts.view'
        FROM users
        WHERE users.role = 'administrator'
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO user_permissions (user_id, permission)
        SELECT users.id, 'alerts.manage'
        FROM users
        WHERE users.role = 'administrator'
        """
    )


def migrate_user_language(connection):
    add_column_if_missing(
        connection,
        "users",
        "language",
        "TEXT NOT NULL DEFAULT ''",
    )



def migrate_user_profiles(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            created_at TEXT NOT NULL DEFAULT '',
            created_by INTEGER,
            FOREIGN KEY (created_by)
                REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    add_column_if_missing(
        connection,
        "users",
        "first_name",
        "TEXT NOT NULL DEFAULT ''",
    )
    add_column_if_missing(
        connection,
        "users",
        "last_name",
        "TEXT NOT NULL DEFAULT ''",
    )
    add_column_if_missing(
        connection,
        "users",
        "department",
        "TEXT NOT NULL DEFAULT ''",
    )
    add_column_if_missing(
        connection,
        "users",
        "function_id",
        "INTEGER REFERENCES user_functions(id) ON DELETE SET NULL",
    )


def migrate_permission_delegation(connection):
    """
    Ensure every permissions.manage grant belongs to an enabled user
    who also has users.manage and clients.view.

    Keep all valid delegates. If none remain, grant the permission to
    the first eligible enabled user. Return False if no such user exists,
    allowing the migration runner to retry later.
    """
    connection.execute("""
        DELETE FROM user_permissions
        WHERE permission = 'permissions.manage'
          AND NOT EXISTS (
              SELECT 1
              FROM users
              WHERE users.id = user_permissions.user_id
                AND users.enabled = 1
                AND EXISTS (
                    SELECT 1
                    FROM user_permissions AS user_admin
                    WHERE user_admin.user_id = users.id
                      AND user_admin.permission = 'users.manage'
                )
                AND EXISTS (
                    SELECT 1
                    FROM user_permissions AS client_view
                    WHERE client_view.user_id = users.id
                      AND client_view.permission = 'clients.view'
                )
          )
    """)

    active_delegate = connection.execute("""
        SELECT users.id
        FROM users
        JOIN user_permissions AS delegated
            ON delegated.user_id = users.id
           AND delegated.permission = 'permissions.manage'
        WHERE users.enabled = 1
          AND EXISTS (
              SELECT 1
              FROM user_permissions AS user_admin
              WHERE user_admin.user_id = users.id
                AND user_admin.permission = 'users.manage'
          )
          AND EXISTS (
              SELECT 1
              FROM user_permissions AS client_view
              WHERE client_view.user_id = users.id
                AND client_view.permission = 'clients.view'
          )
        ORDER BY users.id
        LIMIT 1
    """).fetchone()

    if active_delegate is not None:
        print(
            "[INFO] Valid enabled permission manager exists "
            f"(user_id={active_delegate[0]})"
        )
        return True

    eligible = connection.execute("""
        SELECT users.id
        FROM users
        WHERE users.enabled = 1
          AND EXISTS (
              SELECT 1
              FROM user_permissions AS user_admin
              WHERE user_admin.user_id = users.id
                AND user_admin.permission = 'users.manage'
          )
          AND EXISTS (
              SELECT 1
              FROM user_permissions AS client_view
              WHERE client_view.user_id = users.id
                AND client_view.permission = 'clients.view'
          )
        ORDER BY users.id
        LIMIT 1
    """).fetchone()

    if eligible is None:
        print(
            "[WARN] Migration 008 cannot grant permissions.manage: "
            "no enabled user has both users.manage and clients.view. "
            "The migration will be retried on a later run."
        )
        return False

    connection.execute("""
        INSERT INTO user_permissions (user_id, permission)
        VALUES (?, 'permissions.manage')
    """, (eligible[0],))

    print(
        "[OK] Granted permissions.manage to eligible enabled "
        f"user_id={eligible[0]}"
    )
    return True


def migrate_clients(connection):
    add_column_if_missing(
        connection,
        "clients",
        "client_token_hash",
        "TEXT"
    )

    add_column_if_missing(
        connection,
        "clients",
        "token_created_at",
        "TEXT"
    )

    add_column_if_missing(
        connection,
        "clients",
        "token_revoked_at",
        "TEXT"
    )

    add_column_if_missing(
        connection,
        "clients",
        "enabled",
        "INTEGER NOT NULL DEFAULT 1"
    )


def create_admin(connection, username):
    existing = connection.execute(
        """
        SELECT id, username, enabled
        FROM users
        WHERE username = ?
        """,
        (username,)
    ).fetchone()

    if existing:
        if not existing[2]:
            raise RuntimeError(
                f"Admin user '{username}' exists but is disabled. "
                "Enable the account or choose another username."
            )

        print(
            f"[OK] Admin user '{username}' already exists "
            f"(id={existing[0]}, enabled={existing[2]})"
        )
        return

    print()
    print(f"Creating LUMS admin user: {username}")

    password = getpass("Admin password: ")
    password_confirm = getpass("Confirm password: ")

    if not password:
        raise RuntimeError("Password must not be empty")

    if password != password_confirm:
        raise RuntimeError("Passwords do not match")

    if len(password) < 12:
        raise RuntimeError(
            "Password must contain at least 12 characters"
        )

    password_hasher = PasswordHasher()

    try:
        password_hash = password_hasher.hash(password)
    except HashingError as exc:
        raise RuntimeError(
            f"Argon2 password hashing failed: {exc}"
        ) from exc

    connection.execute(
        """
        INSERT INTO users (
            username,
            password_hash,
            created_at,
            enabled
        )
        VALUES (?, ?, ?, 1)
        """,
        (
            username,
            password_hash,
            utc_now()
        )
    )

    print(f"[OK] Admin user '{username}' created")


def migration_already_applied(connection, version):
    row = connection.execute(
        """
        SELECT version
        FROM schema_migrations
        WHERE version = ?
        """,
        (version,)
    ).fetchone()

    return row is not None


def record_migration(connection, version):
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (
            version,
            applied_at
        )
        VALUES (?, ?)
        """,
        (
            version,
            utc_now()
        )
    )




def _effective_permissions_for_migration(permissions):
    """Apply exactly the dependency filtering used by the current login."""
    effective = set(permissions)

    while True:
        invalid = {
            permission
            for permission in effective
            if not PERMISSION_DEPENDENCIES.get(
                permission, set()
            ).issubset(effective)
        }

        if not invalid:
            return effective

        effective.difference_update(invalid)



def _validate_legacy_rbac_schema(connection):
    """Fail closed if the legacy RBAC schema differs from expectations."""

    expected_columns = {
        "users": {"id", "username", "role", "enabled"},
        "user_permissions": {"user_id", "permission"},
    }

    for table_name, required_columns in expected_columns.items():
        rows = connection.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()

        actual_columns = {row[1] for row in rows}
        missing_columns = required_columns - actual_columns

        if missing_columns:
            raise RuntimeError(
                f"Legacy RBAC schema mismatch in {table_name}: "
                f"missing columns {sorted(missing_columns)!r}"
            )

    users_info = connection.execute(
        "PRAGMA table_info(users)"
    ).fetchall()

    users_id = next(
        (row for row in users_info if row[1] == "id"),
        None,
    )

    if users_id is None or users_id[5] != 1:
        raise RuntimeError(
            "Legacy RBAC schema mismatch: users.id "
            "must be the primary key"
        )

    permission_info = connection.execute(
        "PRAGMA table_info(user_permissions)"
    ).fetchall()

    primary_key_order = {
        row[1]: row[5]
        for row in permission_info
        if row[5]
    }

    if primary_key_order != {"user_id": 1, "permission": 2}:
        raise RuntimeError(
            "Legacy RBAC schema mismatch: "
            "user_permissions must have PRIMARY KEY "
            "(user_id, permission)"
        )

    foreign_keys = connection.execute(
        "PRAGMA foreign_key_list(user_permissions)"
    ).fetchall()

    expected_foreign_key = any(
        row[2] == "users"
        and row[3] == "user_id"
        and row[4] == "id"
        and row[6].upper() == "CASCADE"
        for row in foreign_keys
    )

    if not expected_foreign_key:
        raise RuntimeError(
            "Legacy RBAC schema mismatch: "
            "user_permissions.user_id must reference "
            "users.id ON DELETE CASCADE"
        )


def _validate_custom_rbac_foreign_keys(connection):
    """Check foreign-key integrity of all newly created RBAC tables."""

    tables = (
        "roles",
        "role_permissions",
        "user_roles",
        "user_permission_overrides",
    )

    violations = []

    for table_name in tables:
        rows = connection.execute(
            f"PRAGMA foreign_key_check({table_name})"
        ).fetchall()

        violations.extend(
            (table_name, row)
            for row in rows
        )

    if violations:
        raise RuntimeError(
            "Custom RBAC foreign-key integrity check failed: "
            + repr(violations[:20])
        )


def migrate_custom_rbac(connection):
    """
    Introduce custom RBAC without changing existing effective permissions.

    Existing users receive protected migration roles representing their
    exact current effective permission sets. Legacy user_permissions remains
    untouched as a compatibility and verification source.
    """

    foreign_keys_enabled = connection.execute(
        "PRAGMA foreign_keys"
    ).fetchone()[0]

    if foreign_keys_enabled != 1:
        raise RuntimeError(
            "Custom RBAC migration requires SQLite foreign keys "
            "to be enabled"
        )

    # Migration 008 must complete before custom RBAC becomes authoritative.
    # Otherwise a later legacy permissions.manage grant would be ignored.
    required_migrations = (
        PERMISSIONS_MIGRATION_VERSION,
        PERMISSION_DELEGATION_MIGRATION_VERSION,
        ALERTING_PERMISSIONS_MIGRATION_VERSION,
    )

    missing_migrations = [
        version
        for version in required_migrations
        if not migration_already_applied(connection, version)
    ]

    if missing_migrations:
        raise RuntimeError(
            "Custom RBAC migration prerequisites are missing: "
            + ", ".join(missing_migrations)
        )

    # Migration 003 must have created the legacy permission table.
    table = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'user_permissions'
        """
    ).fetchone()

    if table is None:
        raise RuntimeError(
            "Migration 003 is recorded, but user_permissions is missing"
        )

    _validate_legacy_rbac_schema(connection)

    target_tables = (
        "roles",
        "role_permissions",
        "user_roles",
        "user_permission_overrides",
    )

    existing_tables = []

    for table_name in target_tables:
        row = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table_name,),
        ).fetchone()

        if row is not None:
            existing_tables.append(table_name)

    if existing_tables:
        raise RuntimeError(
            "Unexpected pre-existing RBAC tables without migration 018: "
            + ", ".join(existing_tables)
        )

    users = connection.execute(
        """
        SELECT id, username, role, enabled
        FROM users
        ORDER BY id
        """
    ).fetchall()

    invalid_roles = [
        (user[0], user[1], user[2])
        for user in users
        if user[2] not in VALID_ROLES
    ]

    if invalid_roles:
        raise RuntimeError(
            "Cannot migrate users with invalid legacy roles: "
            + repr(invalid_roles)
        )

    # The central permission catalog is the single source of truth.
    known_permissions = set(PERMISSIONS)

    legacy_permissions = {
        user[0]: set()
        for user in users
    }

    permission_rows = connection.execute(
        """
        SELECT user_id, permission
        FROM user_permissions
        ORDER BY user_id, permission
        """
    ).fetchall()

    user_ids = set(legacy_permissions)
    orphaned_rows = []

    for user_id, permission in permission_rows:
        if user_id not in user_ids:
            orphaned_rows.append((user_id, permission))
            continue

        legacy_permissions[user_id].add(permission)

    if orphaned_rows:
        raise RuntimeError(
            "Orphaned user_permissions rows detected: "
            + repr(orphaned_rows[:20])
        )

    unknown_permissions = sorted({
        permission
        for permissions in legacy_permissions.values()
        for permission in permissions
        if permission not in known_permissions
    })

    if unknown_permissions:
        raise RuntimeError(
            "Unknown legacy permissions require manual review: "
            + ", ".join(unknown_permissions)
        )

    expected_permissions = {
        user_id: _effective_permissions_for_migration(permissions)
        for user_id, permissions in legacy_permissions.items()
    }

    timestamp = utc_now()

    # All DDL and data changes are part of the caller's BEGIN IMMEDIATE
    # transaction. The migration marker is written by the runner in the
    # same transaction.
    connection.execute("""
        CREATE TABLE roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            is_system INTEGER NOT NULL DEFAULT 0
                CHECK (is_system IN (0, 1)),
            is_migration INTEGER NOT NULL DEFAULT 0
                CHECK (is_migration IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by INTEGER,
            updated_by INTEGER,
            CHECK (NOT (is_system = 1 AND is_migration = 1)),
            FOREIGN KEY (created_by)
                REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (updated_by)
                REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    connection.execute("""
        CREATE TABLE role_permissions (
            role_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            PRIMARY KEY (role_id, permission),
            FOREIGN KEY (role_id)
                REFERENCES roles(id) ON DELETE CASCADE
        )
    """)

    connection.execute("""
        CREATE TABLE user_roles (
            user_id INTEGER PRIMARY KEY,
            role_id INTEGER NOT NULL,
            assigned_at TEXT NOT NULL,
            assigned_by INTEGER,
            FOREIGN KEY (user_id)
                REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id)
                REFERENCES roles(id) ON DELETE RESTRICT,
            FOREIGN KEY (assigned_by)
                REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    connection.execute("""
        CREATE TABLE user_permission_overrides (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            effect TEXT NOT NULL
                CHECK (effect IN ('grant', 'deny')),
            changed_at TEXT NOT NULL,
            changed_by INTEGER,
            PRIMARY KEY (user_id, permission),
            FOREIGN KEY (user_id)
                REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (changed_by)
                REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    connection.execute("""
        CREATE INDEX idx_role_permissions_permission
        ON role_permissions(permission)
    """)

    connection.execute("""
        CREATE INDEX idx_user_roles_role
        ON user_roles(role_id)
    """)

    connection.execute("""
        CREATE INDEX idx_user_permission_overrides_permission
        ON user_permission_overrides(permission, effect)
    """)

    # Seed protected built-in roles for future assignments.
    system_roles = (
        ("administrator", "Administrator"),
        ("operator", "Operator"),
        ("viewer", "Viewer"),
    )

    for role_key, display_name in system_roles:
        role_id = connection.execute(
            """
            INSERT INTO roles (
                role_key,
                name,
                description,
                is_system,
                is_migration,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 1, 0, ?, ?)
            """,
            (
                "system-" + role_key,
                display_name,
                "Geschützte LUMS-Systemrolle",
                timestamp,
                timestamp,
            ),
        ).lastrowid

        default_permissions = _effective_permissions_for_migration(
            ROLE_DEFAULT_PERMISSIONS[role_key]
        )

        connection.executemany(
            """
            INSERT INTO role_permissions (role_id, permission)
            VALUES (?, ?)
            """,
            [
                (role_id, permission)
                for permission in sorted(default_permissions)
            ],
        )

    # Group users by identical effective permission sets.
    grouped_users = {}

    for user_id, permissions in expected_permissions.items():
        permission_tuple = tuple(sorted(permissions))
        grouped_users.setdefault(permission_tuple, []).append(user_id)

    for permission_tuple, grouped_user_ids in sorted(
        grouped_users.items()
    ):
        canonical_permissions = "\0".join(permission_tuple)
        digest = hashlib.sha256(
            canonical_permissions.encode("utf-8")
        ).hexdigest()

        role_key = "legacy-" + digest

        role_id = connection.execute(
            """
            INSERT INTO roles (
                role_key,
                name,
                description,
                is_system,
                is_migration,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 0, 1, ?, ?)
            """,
            (
                role_key,
                "Übernommene Berechtigungen " + digest[:8],
                "Automatisch aus den bisherigen effektiven "
                "Benutzerberechtigungen übernommen. "
                "Geschützte Migrationsrolle.",
                timestamp,
                timestamp,
            ),
        ).lastrowid

        connection.executemany(
            """
            INSERT INTO role_permissions (role_id, permission)
            VALUES (?, ?)
            """,
            [
                (role_id, permission)
                for permission in permission_tuple
            ],
        )

        connection.executemany(
            """
            INSERT INTO user_roles (
                user_id,
                role_id,
                assigned_at,
                assigned_by
            )
            VALUES (?, ?, ?, NULL)
            """,
            [
                (user_id, role_id, timestamp)
                for user_id in grouped_user_ids
            ],
        )

    # No individual overrides are created in this migration.
    # Every existing effective permission is represented by the user's
    # protected migration role.

    # Verify one role assignment per user.
    assignment_rows = connection.execute(
        """
        SELECT user_id, COUNT(*)
        FROM user_roles
        GROUP BY user_id
        """
    ).fetchall()

    assignments = {
        user_id: count
        for user_id, count in assignment_rows
    }

    for user in users:
        if assignments.get(user[0]) != 1:
            raise RuntimeError(
                f"RBAC migration did not assign exactly one role "
                f"to user id {user[0]}"
            )

    if len(assignments) != len(users):
        raise RuntimeError(
            "RBAC migration produced unexpected user role assignments"
        )

    # Verify effective permissions through the new role mapping.
    for user_id, expected in expected_permissions.items():
        rows = connection.execute(
            """
            SELECT role_permissions.permission
            FROM user_roles
            JOIN role_permissions
              ON role_permissions.role_id = user_roles.role_id
            WHERE user_roles.user_id = ?
            """,
            (user_id,),
        ).fetchall()

        actual = _effective_permissions_for_migration(
            {row[0] for row in rows}
        )

        if actual != expected:
            raise RuntimeError(
                f"Permission mismatch for user id {user_id}: "
                f"expected={sorted(expected)!r}, "
                f"actual={sorted(actual)!r}"
            )

    # Verify that no individual overrides were accidentally introduced.
    override_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM user_permission_overrides
        """
    ).fetchone()[0]

    if override_count != 0:
        raise RuntimeError(
            "Unexpected individual permission overrides after migration"
        )

    _validate_custom_rbac_foreign_keys(connection)

    print(
        "[OK] Custom RBAC schema created; "
        f"{len(users)} users migrated into "
        f"{len(grouped_users)} protected migration roles"
    )


def print_schema(connection):
    print()
    print("===== SECURITY SCHEMA =====")

    for table in (
        "users",
        "user_permissions",
        "roles",
        "role_permissions",
        "user_roles",
        "user_permission_overrides",
        "audit_log",
        "schema_migrations"
    ):
        print()
        print(f"[{table}]")

        rows = connection.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()

        for row in rows:
            print(
                f"  {row[1]:24} "
                f"{row[2]:16} "
                f"NOT NULL={row[3]} "
                f"DEFAULT={row[4]}"
            )

    print()
    print("[clients security columns]")

    rows = connection.execute(
        "PRAGMA table_info(clients)"
    ).fetchall()

    security_columns = {
        "client_token_hash",
        "token_created_at",
        "token_revoked_at",
        "enabled"
    }

    for row in rows:
        if row[1] in security_columns:
            print(
                f"  {row[1]:24} "
                f"{row[2]:16} "
                f"NOT NULL={row[3]} "
                f"DEFAULT={row[4]}"
            )



def migrate_telemetry(connection):
    """Create storage for real client CPU and memory measurements."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS client_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            recorded_at TEXT NOT NULL,
            cpu_percent REAL NOT NULL
                CHECK (cpu_percent >= 0 AND cpu_percent <= 100),
            memory_percent REAL NOT NULL
                CHECK (memory_percent >= 0 AND memory_percent <= 100),
            memory_total_bytes INTEGER NOT NULL
                CHECK (memory_total_bytes > 0),
            memory_available_bytes INTEGER NOT NULL
                CHECK (
                    memory_available_bytes >= 0
                    AND memory_available_bytes <= memory_total_bytes
                ),
            FOREIGN KEY (client_id) REFERENCES clients(id)
                ON DELETE CASCADE
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_client_telemetry_client_time
        ON client_telemetry(client_id, recorded_at)
    """)


def migrate_telemetry_retention_index(connection):
    """Index timestamps to make retention cleanup more efficient."""
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_client_telemetry_recorded_at
        ON client_telemetry(recorded_at)
    """)


def migrate_telemetry_network(connection):
    """Store optional cumulative network byte counters reported by agents."""
    for column in ("network_rx_bytes", "network_tx_bytes"):
        add_column_if_missing(
            connection,
            "client_telemetry",
            column,
            f"INTEGER CHECK ({column} IS NULL OR {column} >= 0)",
        )


def migrate_telemetry_system_state(connection):
    """Store the latest detailed host snapshot without duplicating it in history."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS client_system_status (
            client_id INTEGER PRIMARY KEY,
            recorded_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients(id)
                ON DELETE CASCADE
        )
    """)


def migrate_telemetry_dashboard(connection):
    add_column_if_missing(
        connection,
        "client_telemetry",
        "disk_percent",
        "REAL CHECK (disk_percent IS NULL OR (disk_percent >= 0 AND disk_percent <= 100))",
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_dashboard_settings (
            user_id INTEGER PRIMARY KEY,
            settings_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)


def migrate_telemetry_event_history(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS client_telemetry_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            recorded_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL,
            FOREIGN KEY (client_id) REFERENCES clients(id)
                ON DELETE CASCADE
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_client_telemetry_events_client_time
        ON client_telemetry_events(client_id, recorded_at)
    """)


def run_migration(db_path, admin_username, skip_admin):
    if not os.path.exists(db_path):
        raise RuntimeError(
            f"Database does not exist: {db_path}"
        )

    connection = sqlite3.connect(db_path)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        print(f"Database: {db_path}")
        print(f"Migration: {MIGRATION_VERSION}")
        print()

        create_security_tables(connection)

        if migration_already_applied(
            connection,
            MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration {MIGRATION_VERSION} "
                f"is already recorded"
            )
        else:
            migrate_clients(connection)

            if not skip_admin:
                create_admin(connection, admin_username)

            record_migration(
                connection,
                MIGRATION_VERSION
            )

            connection.commit()

            print()
            print(
                f"[OK] Migration {MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            RBAC_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration {RBAC_MIGRATION_VERSION} "
                f"is already recorded"
            )
        else:
            migrate_rbac(connection)

            record_migration(
                connection,
                RBAC_MIGRATION_VERSION
            )

            connection.commit()

            print()
            print(
                f"[OK] Migration {RBAC_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            PERMISSIONS_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration {PERMISSIONS_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_user_permissions(connection)

            record_migration(
                connection,
                PERMISSIONS_MIGRATION_VERSION
            )

            connection.commit()

            print()
            print(
                f"[OK] Migration {PERMISSIONS_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            USER_NOTES_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration {USER_NOTES_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_user_admin_notes(connection)
            record_migration(
                connection,
                USER_NOTES_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration {USER_NOTES_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            BACKUP_PERMISSION_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration {BACKUP_PERMISSION_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_backup_permission(connection)
            record_migration(
                connection,
                BACKUP_PERMISSION_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration "
                f"{BACKUP_PERMISSION_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            USER_LANGUAGE_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration {USER_LANGUAGE_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_user_language(connection)
            record_migration(
                connection,
                USER_LANGUAGE_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration "
                f"{USER_LANGUAGE_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            USER_PROFILES_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration {USER_PROFILES_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_user_profiles(connection)
            record_migration(
                connection,
                USER_PROFILES_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration {USER_PROFILES_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            CUSTOM_RBAC_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration {PERMISSION_DELEGATION_MIGRATION_VERSION} "
                "skipped because custom RBAC is already active"
            )
        elif migration_already_applied(
            connection,
            PERMISSION_DELEGATION_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration {PERMISSION_DELEGATION_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            if migrate_permission_delegation(connection):
                record_migration(
                    connection,
                    PERMISSION_DELEGATION_MIGRATION_VERSION
                )
                connection.commit()
                print(
                    f"[OK] Migration "
                    f"{PERMISSION_DELEGATION_MIGRATION_VERSION} completed"
                )
            else:
                connection.commit()
                print(
                    f"[WARN] Migration "
                    f"{PERMISSION_DELEGATION_MIGRATION_VERSION} "
                    "remains pending; custom RBAC activation is deferred"
                )

        if migration_already_applied(
            connection,
            TELEMETRY_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration {TELEMETRY_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_telemetry(connection)
            record_migration(
                connection,
                TELEMETRY_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration {TELEMETRY_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            TELEMETRY_RETENTION_INDEX_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration "
                f"{TELEMETRY_RETENTION_INDEX_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_telemetry_retention_index(connection)
            record_migration(
                connection,
                TELEMETRY_RETENTION_INDEX_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration "
                f"{TELEMETRY_RETENTION_INDEX_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            TELEMETRY_NETWORK_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration {TELEMETRY_NETWORK_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_telemetry_network(connection)
            record_migration(
                connection,
                TELEMETRY_NETWORK_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration "
                f"{TELEMETRY_NETWORK_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            TELEMETRY_SYSTEM_STATE_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration "
                f"{TELEMETRY_SYSTEM_STATE_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_telemetry_system_state(connection)
            record_migration(
                connection,
                TELEMETRY_SYSTEM_STATE_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration "
                f"{TELEMETRY_SYSTEM_STATE_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            TELEMETRY_DASHBOARD_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration "
                f"{TELEMETRY_DASHBOARD_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_telemetry_dashboard(connection)
            record_migration(
                connection,
                TELEMETRY_DASHBOARD_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration "
                f"{TELEMETRY_DASHBOARD_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            TELEMETRY_EVENT_HISTORY_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration "
                f"{TELEMETRY_EVENT_HISTORY_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_telemetry_event_history(connection)
            record_migration(
                connection,
                TELEMETRY_EVENT_HISTORY_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration "
                f"{TELEMETRY_EVENT_HISTORY_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            SYSTEM_UPDATE_PERMISSION_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration "
                f"{SYSTEM_UPDATE_PERMISSION_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_system_update_permission(connection)
            record_migration(
                connection,
                SYSTEM_UPDATE_PERMISSION_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration "
                f"{SYSTEM_UPDATE_PERMISSION_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            INFRASTRUCTURE_TOPOLOGY_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration "
                f"{INFRASTRUCTURE_TOPOLOGY_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_infrastructure_topology(connection)
            record_migration(
                connection,
                INFRASTRUCTURE_TOPOLOGY_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration "
                f"{INFRASTRUCTURE_TOPOLOGY_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            ALERTING_PERMISSIONS_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration "
                f"{ALERTING_PERMISSIONS_MIGRATION_VERSION} "
                "is already recorded"
            )
        else:
            migrate_alerting_permissions(connection)
            record_migration(
                connection,
                ALERTING_PERMISSIONS_MIGRATION_VERSION
            )
            connection.commit()
            print(
                f"[OK] Migration "
                f"{ALERTING_PERMISSIONS_MIGRATION_VERSION} completed"
            )

        if migration_already_applied(
            connection,
            CUSTOM_RBAC_MIGRATION_VERSION
        ):
            print(
                f"[INFO] Migration "
                f"{CUSTOM_RBAC_MIGRATION_VERSION} "
                "is already recorded"
            )
        elif not migration_already_applied(
            connection,
            PERMISSION_DELEGATION_MIGRATION_VERSION
        ):
            print(
                f"[WARN] Migration "
                f"{CUSTOM_RBAC_MIGRATION_VERSION} remains pending: "
                f"{PERMISSION_DELEGATION_MIGRATION_VERSION} "
                "has not completed"
            )
        else:
            connection.execute("BEGIN IMMEDIATE")
            try:
                migrate_custom_rbac(connection)
                record_migration(
                    connection,
                    CUSTOM_RBAC_MIGRATION_VERSION
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

            print(
                f"[OK] Migration "
                f"{CUSTOM_RBAC_MIGRATION_VERSION} completed"
            )

        print_schema(connection)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(
        description="LUMS security foundation database migration"
    )

    parser.add_argument(
        "--db-path",
        default=os.environ.get(
            "LUMS_DB_PATH",
            DEFAULT_DB_PATH
        ),
        help="Path to LUMS SQLite database"
    )

    parser.add_argument(
        "--admin-username",
        default="admin",
        help="Initial LUMS administrator username"
    )

    parser.add_argument(
        "--skip-admin",
        action="store_true",
        help="Do not create the initial administrator"
    )

    args = parser.parse_args()

    try:
        run_migration(
            db_path=args.db_path,
            admin_username=args.admin_username,
            skip_admin=args.skip_admin
        )
    except Exception as exc:
        print()
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
