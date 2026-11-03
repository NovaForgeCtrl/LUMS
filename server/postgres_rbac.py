"""PostgreSQL-native RBAC operations for a fresh LUMS installation."""

from __future__ import annotations

from datetime import datetime, timezone

from psycopg import Connection

if __package__:
    from .db_transactions import require_transaction
    from .security import (
        PERMISSIONS,
        PERMISSION_DEPENDENCIES,
        ROLE_ADMINISTRATOR,
        ROLE_DEFAULT_PERMISSIONS,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        VALID_ROLES,
        _calculate_effective_permissions,
    )
else:
    from db_transactions import require_transaction
    from security import (
        PERMISSIONS,
        PERMISSION_DEPENDENCIES,
        ROLE_ADMINISTRATOR,
        ROLE_DEFAULT_PERMISSIONS,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        VALID_ROLES,
        _calculate_effective_permissions,
    )


RBAC_TABLES = (
    "users",
    "roles",
    "role_permissions",
    "user_roles",
    "user_permission_overrides",
)

SYSTEM_ROLES = (
    (ROLE_ADMINISTRATOR, "Administrator"),
    (ROLE_OPERATOR, "Operator"),
    (ROLE_VIEWER, "Viewer"),
)

INITIAL_PERMISSION_MANAGER_SET = frozenset({
    "permissions.manage",
    "users.manage",
    "clients.view",
})


class PostgresRBACError(RuntimeError):
    """Raised when PostgreSQL RBAC data or schema is inconsistent."""


def _require_rbac_schema(connection: Connection) -> None:
    """Require the complete fresh-install RBAC schema in current_schema()."""
    rows = connection.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_type = 'BASE TABLE'
          AND table_name = ANY(%s)
        """,
        (list(RBAC_TABLES),),
    ).fetchall()

    existing = {row["table_name"] for row in rows}
    missing = set(RBAC_TABLES) - existing

    if missing:
        raise PostgresRBACError(
            "PostgreSQL RBAC schema is incomplete; missing tables: "
            + ", ".join(sorted(missing))
        )


def seed_system_roles(
    connection: Connection,
    *,
    timestamp: str | None = None,
) -> dict[str, int]:
    """Create or validate the three protected built-in system roles.

    The caller owns the transaction and must acquire the shared RBAC
    advisory lock. Existing roles are never silently repaired: inconsistent
    role metadata or permission sets fail closed.
    """
    require_transaction(connection)
    _require_rbac_schema(connection)

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    role_ids: dict[str, int] = {}

    for role_key, display_name in SYSTEM_ROLES:
        role_name = "system-" + role_key
        expected_permissions = set(
            ROLE_DEFAULT_PERMISSIONS[role_key]
        )

        existing_rows = connection.execute(
            """
            SELECT id, name, is_system, is_migration
            FROM roles
            WHERE role_key = %s
            FOR UPDATE
            """,
            (role_name,),
        ).fetchall()

        if len(existing_rows) > 1:
            raise PostgresRBACError(
                f"Multiple rows exist for system role {role_name}"
            )

        if existing_rows:
            existing = existing_rows[0]

            if (
                existing["name"] != display_name
                or existing["is_system"] is not True
                or existing["is_migration"] is not False
            ):
                raise PostgresRBACError(
                    f"Existing role {role_name} is not the protected "
                    "LUMS system role"
                )

            role_id = existing["id"]

            actual_permissions = {
                row["permission"]
                for row in connection.execute(
                    """
                    SELECT permission
                    FROM role_permissions
                    WHERE role_id = %s
                    """,
                    (role_id,),
                ).fetchall()
            }

            if actual_permissions != expected_permissions:
                raise PostgresRBACError(
                    f"Existing permissions for {role_name} do not "
                    "match the protected default permission set"
                )

            role_ids[role_key] = role_id
            continue

        row = connection.execute(
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
            VALUES (%s, %s, %s, TRUE, FALSE, %s, %s)
            RETURNING id
            """,
            (
                role_name,
                display_name,
                "Geschützte LUMS-Systemrolle",
                timestamp,
                timestamp,
            ),
        ).fetchone()

        if row is None:
            raise PostgresRBACError(
                f"PostgreSQL did not return the role id for {role_key}"
            )

        role_id = row["id"]

        for permission in sorted(expected_permissions):
            connection.execute(
                """
                INSERT INTO role_permissions (role_id, permission)
                VALUES (%s, %s)
                """,
                (role_id, permission),
            )

        role_ids[role_key] = role_id

    return role_ids


def _validate_permission_selection(permissions) -> set[str]:
    if not isinstance(
        permissions,
        (list, tuple, set, frozenset),
    ):
        raise ValueError("Permissions must be a collection")

    permission_list = list(permissions)
    selected = set(permission_list)

    if len(selected) != len(permission_list):
        raise ValueError("Duplicate permissions are not allowed")

    unknown = selected - set(PERMISSIONS)
    if unknown:
        raise ValueError(
            "Unknown permissions: " + ", ".join(sorted(unknown))
        )

    for permission in selected:
        missing = (
            PERMISSION_DEPENDENCIES.get(permission, set())
            - selected
        )
        if missing:
            raise ValueError(
                f"Permission {permission!r} is missing dependencies: "
                + ", ".join(sorted(missing))
            )

    return selected


def store_user_permissions(
    connection: Connection,
    user_id: int,
    role: str,
    permissions,
    *,
    actor_id: int | None = None,
    timestamp: str | None = None,
) -> str:
    """Persist one user's selected permissions using a protected system role.

    The caller owns the transaction and must acquire the shared RBAC advisory
    lock before performing manager-count checks or any RBAC write.
    """
    require_transaction(connection)
    _require_rbac_schema(connection)

    if role not in VALID_ROLES:
        raise ValueError(f"Invalid user role: {role!r}")

    selected = _validate_permission_selection(permissions)

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    role_rows = connection.execute(
        """
        SELECT id
        FROM roles
        WHERE role_key = %s
          AND is_system IS TRUE
          AND is_migration IS FALSE
        """,
        ("system-" + role,),
    ).fetchall()

    if len(role_rows) != 1:
        raise PostgresRBACError(
            "Expected exactly one protected system role: system-" + role
        )

    role_id = role_rows[0]["id"]

    base_permissions = {
        row["permission"]
        for row in connection.execute(
            """
            SELECT permission
            FROM role_permissions
            WHERE role_id = %s
            """,
            (role_id,),
        ).fetchall()
    }

    unknown_base = base_permissions - set(PERMISSIONS)
    if unknown_base:
        raise PostgresRBACError(
            "System role contains unknown permissions: "
            + ", ".join(sorted(unknown_base))
        )

    grants = selected - base_permissions
    denies = base_permissions - selected

    connection.execute(
        "DELETE FROM user_roles WHERE user_id = %s",
        (user_id,),
    )
    connection.execute(
        "DELETE FROM user_permission_overrides WHERE user_id = %s",
        (user_id,),
    )

    connection.execute(
        """
        INSERT INTO user_roles (
            user_id,
            role_id,
            assigned_at,
            assigned_by
        )
        VALUES (%s, %s, %s, %s)
        """,
        (user_id, role_id, timestamp, actor_id),
    )

    overrides = [
        (user_id, permission, "grant", timestamp, actor_id)
        for permission in sorted(grants)
    ]
    overrides.extend(
        (user_id, permission, "deny", timestamp, actor_id)
        for permission in sorted(denies)
    )

    for override in overrides:
        connection.execute(
            """
            INSERT INTO user_permission_overrides (
                user_id,
                permission,
                effect,
                changed_at,
                changed_by
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            override,
        )

    return "custom"


def resolve_user_permissions(
    connection: Connection,
    user_id: int,
) -> frozenset[str]:
    """Resolve effective permissions from PostgreSQL role and override data."""
    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id < 1
    ):
        raise ValueError("user_id must be a positive integer")

    _require_rbac_schema(connection)

    assignments = connection.execute(
        """
        SELECT
            ur.role_id,
            r.id AS resolved_role_id
        FROM user_roles AS ur
        LEFT JOIN roles AS r
          ON r.id = ur.role_id
        WHERE ur.user_id = %s
        """,
        (user_id,),
    ).fetchall()

    if len(assignments) != 1:
        raise PostgresRBACError(
            f"User id {user_id} must have exactly one RBAC role assignment"
        )

    assignment = assignments[0]

    if assignment["resolved_role_id"] is None:
        raise PostgresRBACError(
            f"User id {user_id} references a missing RBAC role"
        )

    role_id = assignment["role_id"]

    role_permissions = {
        row["permission"]
        for row in connection.execute(
            """
            SELECT permission
            FROM role_permissions
            WHERE role_id = %s
            """,
            (role_id,),
        ).fetchall()
    }

    override_rows = connection.execute(
        """
        SELECT permission, effect
        FROM user_permission_overrides
        WHERE user_id = %s
        """,
        (user_id,),
    ).fetchall()

    grants: set[str] = set()
    denies: set[str] = set()

    for row in override_rows:
        permission = row["permission"]
        effect = row["effect"]

        if effect == "grant":
            grants.add(permission)
        elif effect == "deny":
            denies.add(permission)
        else:
            raise PostgresRBACError(
                f"User id {user_id} has an invalid permission override effect"
            )

    unknown = (role_permissions | grants | denies) - set(PERMISSIONS)
    if unknown:
        raise PostgresRBACError(
            "PostgreSQL RBAC data contains unknown permissions: "
            + ", ".join(sorted(unknown))
        )

    return _calculate_effective_permissions(
        role_permissions,
        grants,
        denies,
    )


def grant_initial_permission_manager(
    connection: Connection,
    user_id: int,
    *,
    timestamp: str | None = None,
) -> bool:
    """Grant delegation to the sole initial administrator during bootstrap.

    This is only for a fresh database bootstrap, immediately after the first
    administrator and its default system-role assignment have been created.
    It refuses to run once more than one user exists.

    The caller must already hold the shared RBAC advisory lock.
    """
    require_transaction(connection)
    _require_rbac_schema(connection)

    user_count = connection.execute(
        "SELECT COUNT(*) AS total FROM users"
    ).fetchone()["total"]

    if user_count != 1:
        raise PostgresRBACError(
            "Initial permission-manager bootstrap requires exactly one user"
        )

    user = connection.execute(
        """
        SELECT id, enabled, role
        FROM users
        WHERE id = %s
        FOR UPDATE
        """,
        (user_id,),
    ).fetchone()

    if user is None:
        raise PostgresRBACError(
            "Initial administrator does not exist"
        )

    if user["enabled"] is not True:
        raise PostgresRBACError(
            "Initial administrator must be enabled"
        )

    if user["role"] != ROLE_ADMINISTRATOR:
        raise PostgresRBACError(
            "Initial permission manager must have the administrator role"
        )

    # Also verify the actual RBAC assignment. The legacy-compatible
    # users.role column alone is not authoritative for PostgreSQL RBAC.
    assignment_rows = connection.execute(
        """
        SELECT
            r.role_key,
            r.name,
            r.is_system,
            r.is_migration
        FROM user_roles AS ur
        JOIN roles AS r
          ON r.id = ur.role_id
        WHERE ur.user_id = %s
        FOR UPDATE OF ur, r
        """,
        (user_id,),
    ).fetchall()

    if len(assignment_rows) != 1:
        raise PostgresRBACError(
            "Initial permission manager requires exactly one "
            "RBAC role assignment"
        )

    assignment = assignment_rows[0]

    if (
        assignment["role_key"] != "system-administrator"
        or assignment["name"] != "Administrator"
        or assignment["is_system"] is not True
        or assignment["is_migration"] is not False
    ):
        raise PostgresRBACError(
            "Initial permission manager requires the protected "
            "system-administrator RBAC role"
        )

    effective = resolve_user_permissions(connection, user_id)

    if not {
        "users.manage",
        "clients.view",
    }.issubset(effective):
        raise PostgresRBACError(
            "Initial administrator lacks the required delegation prerequisites"
        )

    if "permissions.manage" in effective:
        return False

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    connection.execute(
        """
        INSERT INTO user_permission_overrides (
            user_id,
            permission,
            effect,
            changed_at,
            changed_by
        )
        VALUES (%s, 'permissions.manage', 'grant', %s, NULL)
        ON CONFLICT (user_id, permission) DO UPDATE
        SET
            effect = 'grant',
            changed_at = EXCLUDED.changed_at,
            changed_by = NULL
        """,
        (user_id, timestamp),
    )

    resolved = resolve_user_permissions(connection, user_id)
    if not INITIAL_PERMISSION_MANAGER_SET.issubset(resolved):
        raise PostgresRBACError(
            "Initial permission-manager grant did not become effective"
        )

    return True


__all__ = [
    "PostgresRBACError",
    "RBAC_TABLES",
    "SYSTEM_ROLES",
    "grant_initial_permission_manager",
    "resolve_user_permissions",
    "seed_system_roles",
    "store_user_permissions",
]
