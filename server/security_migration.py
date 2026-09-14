#!/usr/bin/env python3

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from getpass import getpass

from argon2 import PasswordHasher
from argon2.exceptions import HashingError


DEFAULT_DB_PATH = "/var/lib/lums/lums.db"
MIGRATION_VERSION = "001-security-foundation"


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


def migration_already_applied(connection):
    row = connection.execute(
        """
        SELECT version
        FROM schema_migrations
        WHERE version = ?
        """,
        (MIGRATION_VERSION,)
    ).fetchone()

    return row is not None


def record_migration(connection):
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (
            version,
            applied_at
        )
        VALUES (?, ?)
        """,
        (
            MIGRATION_VERSION,
            utc_now()
        )
    )


def print_schema(connection):
    print()
    print("===== SECURITY SCHEMA =====")

    for table in (
        "users",
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

        if migration_already_applied(connection):
            print(
                f"[INFO] Migration {MIGRATION_VERSION} "
                f"is already recorded"
            )
        else:
            migrate_clients(connection)

            if not skip_admin:
                create_admin(connection, admin_username)

            record_migration(connection)

            connection.commit()

            print()
            print(
                f"[OK] Migration {MIGRATION_VERSION} completed"
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
