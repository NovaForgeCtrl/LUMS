#!/usr/bin/env python3

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from getpass import getpass

from argon2 import PasswordHasher
from argon2.exceptions import HashingError

if __package__:
    from .security import ROLE_DEFAULT_PERMISSIONS
else:
    from security import ROLE_DEFAULT_PERMISSIONS


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


def print_schema(connection):
    print()
    print("===== SECURITY SCHEMA =====")

    for table in (
        "users",
        "user_permissions",
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
                    "remains pending"
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
