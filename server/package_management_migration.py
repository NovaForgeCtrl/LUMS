#!/usr/bin/env python3

import os
import sqlite3
import sys
from datetime import datetime, timezone


DEFAULT_DB_PATH = "/var/lib/lums/lums.db"
MIGRATION_VERSION = "002-package-management"


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


def ensure_schema_migrations_table(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)


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


def migrate_update_jobs(connection):
    add_column_if_missing(
        connection,
        "update_jobs",
        "action",
        "TEXT NOT NULL DEFAULT 'UPDATE_PACKAGE'"
    )


def print_schema(connection):
    print()
    print("===== PACKAGE MANAGEMENT SCHEMA =====")
    print()
    print("[update_jobs]")

    rows = connection.execute(
        "PRAGMA table_info(update_jobs)"
    ).fetchall()

    for row in rows:
        print(
            f"  {row[1]:24} "
            f"{row[2]:16} "
            f"NOT NULL={row[3]} "
            f"DEFAULT={row[4]}"
        )

    print()


def run_migration(db_path):
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

        ensure_schema_migrations_table(connection)

        if migration_already_applied(connection):
            print(
                f"[INFO] Migration {MIGRATION_VERSION} "
                f"is already recorded"
            )
        else:
            migrate_update_jobs(connection)

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
    db_path = os.environ.get(
        "LUMS_DB_PATH",
        DEFAULT_DB_PATH
    )

    try:
        run_migration(db_path)
    except Exception as exc:
        print()
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
