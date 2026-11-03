"""PostgreSQL-native authorization state loading for LUMS."""

from __future__ import annotations

from dataclasses import dataclass

from psycopg import Connection

if __package__:
    from .db_transactions import transaction
    from .postgres_rbac import (
        VALID_ROLES,
        resolve_user_permissions,
    )
else:
    from db_transactions import transaction
    from postgres_rbac import (
        VALID_ROLES,
        resolve_user_permissions,
    )


class PostgresAuthorizationError(RuntimeError):
    """Raised when PostgreSQL authorization state is invalid."""


@dataclass(frozen=True, slots=True)
class AuthorizationState:
    """Validated user and effective permissions for one request."""

    user: dict
    permissions: frozenset[str]


def load_authorization_state(
    connection: Connection,
    user_id: int,
) -> AuthorizationState | None:
    """Load an active user and resolve permissions from one DB snapshot.

    Returns None for deleted or disabled users.

    User data, role assignments, role permissions and overrides are read
    inside one read-only REPEATABLE READ transaction. This prevents a
    request from combining authorization data from different committed
    database states.

    Incomplete or invalid authorization data raises an exception.
    No legacy SQLite permission fallback is permitted.
    """
    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id < 1
    ):
        raise ValueError("user_id must be a positive integer")

    with transaction(connection):
        # This must be the first SQL statement in this transaction.
        connection.execute(
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
        )

        row = connection.execute(
            """
            SELECT id, username, enabled, role
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            return None

        user = dict(row)

        if user.get("enabled") is not True:
            return None

        role = user.get("role")

        if role not in VALID_ROLES:
            raise PostgresAuthorizationError(
                f"User id {user_id} has an invalid PostgreSQL role"
            )

        permissions = resolve_user_permissions(
            connection,
            user_id,
        )

        if not isinstance(permissions, frozenset):
            raise PostgresAuthorizationError(
                "PostgreSQL RBAC returned an invalid permission collection"
            )

        return AuthorizationState(
            user=user,
            permissions=permissions,
        )


__all__ = [
    "AuthorizationState",
    "PostgresAuthorizationError",
    "load_authorization_state",
]
