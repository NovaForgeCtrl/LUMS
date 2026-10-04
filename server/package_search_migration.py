#!/usr/bin/env python3

import os
import sqlite3
import sys
from datetime import datetime, timezone


DEFAULT_DB_PATH = "/var/lib/lums/lums.db"
MIGRATION_VERSION = "003-package-search"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


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


def create_package_search_table(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS package_search_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            result_json TEXT,
            error_message TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_package_search_client_status_id
        ON package_search_requests(client_id, status, id)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_package_search_client_created
        ON package_search_requests(client_id, created_at)
    """)


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
    print("===== PACKAGE SEARCH SCHEMA =====")
    print()
    print("[package_search_requests]")

    rows = connection.execute(
        "PRAGMA table_info(package_search_requests)"
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
        connection.execute("PRAGMA busy_timeout = 5000")

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
            create_package_search_table(connection)
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
