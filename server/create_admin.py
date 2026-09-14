#!/usr/bin/env python3

import argparse
import getpass
import sqlite3
import sys
from pathlib import Path

from security import hash_password, utc_now


DEFAULT_DB_PATH = "/var/lib/lums/lums.db"


def create_admin(db_path, username):
    username = username.strip()

    if not username:
        raise ValueError("Username must not be empty.")

    if len(username) > 64:
        raise ValueError("Username is too long.")

    password = getpass.getpass("Admin password: ")
    password_confirm = getpass.getpass("Confirm password: ")

    if password != password_confirm:
        raise ValueError("Passwords do not match.")

    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long.")

    password_hash = hash_password(password)

    connection = sqlite3.connect(db_path)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        existing = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if existing is not None:
            raise ValueError(
                f"User '{username}' already exists."
            )

        now = utc_now()

        cursor = connection.execute(
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
                now,
            ),
        )

        user_id = cursor.lastrowid

        connection.execute(
            """
            INSERT INTO audit_log (
                timestamp,
                actor_type,
                actor_id,
                action,
                target,
                result,
                details
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                "system",
                None,
                "admin_created",
                f"user:{user_id}",
                "success",
                f"Admin user '{username}' created",
            ),
        )

        connection.commit()

        print()
        print("Admin user created successfully.")
        print("User ID:", user_id)
        print("Username:", username)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(
        description="Create a LUMS administrator account."
    )

    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help=f"SQLite database path (default: {DEFAULT_DB_PATH})",
    )

    parser.add_argument(
        "--username",
        required=True,
        help="Administrator username",
    )

    args = parser.parse_args()

    if not Path(args.db_path).exists():
        print(
            f"ERROR: Database does not exist: {args.db_path}",
            file=sys.stderr,
        )
        return 1

    try:
        create_admin(
            db_path=args.db_path,
            username=args.username,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"ERROR: Could not create admin: {exc}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
