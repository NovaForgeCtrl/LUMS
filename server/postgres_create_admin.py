"""Explicit first-administrator bootstrap for a fresh PostgreSQL LUMS install.

This module is separate from the existing SQLite create_admin.py.
Importing this module never opens a database connection.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime, timezone

if __package__:
    from .db import connect
    from .db_transactions import transaction
    from .migrations import MIGRATIONS
    from .postgres_audit import audit_log
    from .postgres_rbac import (
        PostgresRBACError,
        grant_initial_permission_manager,
        seed_system_roles,
        store_user_permissions,
    )
    from .rbac_lock import acquire_rbac_write_lock
    from .security import (
        ROLE_ADMINISTRATOR,
        ROLE_DEFAULT_PERMISSIONS,
        hash_password,
    )
else:
    from db import connect
    from db_transactions import transaction
    from migrations import MIGRATIONS
    from postgres_audit import audit_log
    from postgres_rbac import (
        PostgresRBACError,
        grant_initial_permission_manager,
        seed_system_roles,
        store_user_permissions,
    )
    from rbac_lock import acquire_rbac_write_lock
    from security import (
        ROLE_ADMINISTRATOR,
        ROLE_DEFAULT_PERMISSIONS,
        hash_password,
    )


BASELINE_MIGRATION_VERSIONS = (
    "001-core-schema",
    "002-security-schema",
    "003-rbac-schema",
    "004-rbac-system-roles",
)

MINIMUM_PASSWORD_LENGTH = 12
MAXIMUM_USERNAME_LENGTH = 64


class PostgresAdminBootstrapError(RuntimeError):
    """Raised when a safe first-administrator bootstrap is not possible."""


def _validate_username(username: str) -> str:
    if not isinstance(username, str) or "\x00" in username:
        raise ValueError("Username must be a valid string.")

    username = username.strip()

    if not username:
        raise ValueError("Username must not be empty.")

    if len(username) > MAXIMUM_USERNAME_LENGTH:
        raise ValueError("Username is too long.")

    return username


def _validate_password(password: str) -> None:
    if not isinstance(password, str):
        raise ValueError("Password must be a string.")

    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MINIMUM_PASSWORD_LENGTH} characters long."
        )


def _require_baseline_migrations(connection) -> None:
    """Require the baseline migrations and verify their registered checksums."""
    registered = {
        migration.version: migration
        for migration in MIGRATIONS
    }

    missing_from_code = (
        set(BASELINE_MIGRATION_VERSIONS) - set(registered)
    )
    if missing_from_code:
        raise PostgresAdminBootstrapError(
            "The application does not register required baseline migrations: "
            + ", ".join(sorted(missing_from_code))
        )

    history = connection.execute(
        """
        SELECT to_regclass('schema_migrations') AS table_name
        """
    ).fetchone()

    if history is None or history["table_name"] is None:
        raise PostgresAdminBootstrapError(
            "PostgreSQL migrations have not been applied."
        )

    rows = connection.execute(
        """
        SELECT version, checksum
        FROM schema_migrations
        WHERE version = ANY(%s)
        """,
        (list(BASELINE_MIGRATION_VERSIONS),),
    ).fetchall()

    actual = {
        row["version"]: row["checksum"]
        for row in rows
    }

    missing = set(BASELINE_MIGRATION_VERSIONS) - set(actual)
    if missing:
        raise PostgresAdminBootstrapError(
            "Required PostgreSQL migrations are missing: "
            + ", ".join(sorted(missing))
        )

    mismatched = [
        version
        for version in BASELINE_MIGRATION_VERSIONS
        if actual[version] != registered[version].checksum
    ]
    if mismatched:
        raise PostgresAdminBootstrapError(
            "PostgreSQL migration checksums do not match this application: "
            + ", ".join(sorted(mismatched))
        )


def create_initial_admin(
    connection,
    username: str,
    password: str,
) -> int:
    """Create the sole first administrator atomically.

    Migrations 001 through 004 must already have been applied.
    The caller owns the connection lifecycle.
    """
    username = _validate_username(username)
    _validate_password(password)

    # Expensive password hashing is done before acquiring the RBAC lock.
    password_hash = hash_password(password)
    timestamp = datetime.now(timezone.utc).isoformat()

    with transaction(connection):
        # Must be the first SQL operation in this transaction.
        acquire_rbac_write_lock(connection)

        _require_baseline_migrations(connection)

        user_count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            """
        ).fetchone()["total"]

        if user_count != 0:
            raise PostgresAdminBootstrapError(
                "Initial administrator bootstrap is only permitted "
                "when the users table is empty."
            )

        # Migration 004 seeds the roles. This call validates that their
        # protected definitions and permission sets are complete.
        seed_system_roles(
            connection,
            timestamp=timestamp,
        )

        row = connection.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                created_at,
                enabled,
                role
            )
            VALUES (%s, %s, %s, TRUE, %s)
            RETURNING id
            """,
            (
                username,
                password_hash,
                timestamp,
                ROLE_ADMINISTRATOR,
            ),
        ).fetchone()

        if row is None:
            raise PostgresAdminBootstrapError(
                "PostgreSQL did not return the new administrator ID."
            )

        user_id = row["id"]

        if (
            isinstance(user_id, bool)
            or not isinstance(user_id, int)
            or user_id < 1
        ):
            raise PostgresAdminBootstrapError(
                "PostgreSQL returned an invalid administrator ID."
            )

        store_user_permissions(
            connection,
            user_id,
            ROLE_ADMINISTRATOR,
            ROLE_DEFAULT_PERMISSIONS[ROLE_ADMINISTRATOR],
            actor_id=None,
            timestamp=timestamp,
        )

        granted = grant_initial_permission_manager(
            connection,
            user_id,
            timestamp=timestamp,
        )

        if granted is not True:
            raise PostgresAdminBootstrapError(
                "The initial administrator delegation grant was not created."
            )

        audit_log(
            connection,
            actor_type="system",
            actor_id=None,
            action="admin_created",
            target=f"user:{user_id}",
            result="success",
            details=(
                f"Initial PostgreSQL administrator '{username}' created."
            ),
        )

    return user_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create the first administrator for a fresh PostgreSQL LUMS install."
        )
    )
    parser.add_argument(
        "--username",
        required=True,
        help="Initial administrator username",
    )
    args = parser.parse_args(argv)

    connection = None

    try:
        password = getpass.getpass("Admin password: ")
        password_confirm = getpass.getpass("Confirm password: ")

        if password != password_confirm:
            raise ValueError("Passwords do not match.")

        connection = connect(
            application_name="lums-postgres-create-admin"
        )

        user_id = create_initial_admin(
            connection,
            args.username,
            password,
        )

        print()
        print("Initial PostgreSQL administrator created successfully.")
        print("User ID:", user_id)
        print("Username:", args.username.strip())
        return 0

    except (
        ValueError,
        PostgresAdminBootstrapError,
        PostgresRBACError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    except Exception as exc:
        print(
            "ERROR: Could not create initial PostgreSQL administrator: "
            f"{exc}",
            file=sys.stderr,
        )
        return 1

    finally:
        if connection is not None and not connection.closed:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BASELINE_MIGRATION_VERSIONS",
    "PostgresAdminBootstrapError",
    "create_initial_admin",
    "main",
]
