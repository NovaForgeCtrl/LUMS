"""PostgreSQL-specific permission catalogue and RBAC calculation."""

from __future__ import annotations

if __package__:
    from .security import (
        PERMISSIONS as BASE_PERMISSIONS,
        PERMISSION_DEPENDENCIES as BASE_PERMISSION_DEPENDENCIES,
        ROLE_ADMINISTRATOR,
        ROLE_DEFAULT_PERMISSIONS as BASE_ROLE_DEFAULT_PERMISSIONS,
        ROLE_OPERATOR,
        ROLE_VIEWER,
    )
else:
    from security import (
        PERMISSIONS as BASE_PERMISSIONS,
        PERMISSION_DEPENDENCIES as BASE_PERMISSION_DEPENDENCIES,
        ROLE_ADMINISTRATOR,
        ROLE_DEFAULT_PERMISSIONS as BASE_ROLE_DEFAULT_PERMISSIONS,
        ROLE_OPERATOR,
        ROLE_VIEWER,
    )


SOC_PERMISSIONS = {
    "soc.view": "SOC-Ereignisse und Incidents ansehen",
    "soc.incidents.manage": "SOC-Incidents verwalten",
    "soc.collectors.manage": "SOC-Collector verwalten",
}

POSTGRES_PERMISSIONS = {
    **BASE_PERMISSIONS,
    **SOC_PERMISSIONS,
}

POSTGRES_ROLE_DEFAULT_PERMISSIONS = {
    ROLE_VIEWER: frozenset(
        set(BASE_ROLE_DEFAULT_PERMISSIONS[ROLE_VIEWER])
        | {"soc.view"}
    ),
    ROLE_OPERATOR: frozenset(
        set(BASE_ROLE_DEFAULT_PERMISSIONS[ROLE_OPERATOR])
        | {"soc.view", "soc.incidents.manage"}
    ),
    ROLE_ADMINISTRATOR: frozenset(
        set(BASE_ROLE_DEFAULT_PERMISSIONS[ROLE_ADMINISTRATOR])
        | {
            "soc.view",
            "soc.incidents.manage",
            "soc.collectors.manage",
        }
    ),
}

POSTGRES_PERMISSION_DEPENDENCIES = {
    **BASE_PERMISSION_DEPENDENCIES,
    "soc.incidents.manage": {"soc.view"},
    "soc.collectors.manage": {"soc.view"},
}

POSTGRES_ROLE_DESCRIPTIONS = {
    ROLE_VIEWER: (
        "Clients, installierte Software und SOC-Ereignisse ansehen."
    ),
    ROLE_OPERATOR: (
        "Viewer-Rechte sowie Updates, Update-Jobs und "
        "SOC-Incidents verwalten."
    ),
    ROLE_ADMINISTRATOR: (
        "Alle PostgreSQL-Bereiche einschließlich SOC-Incidents "
        "und SOC-Collectors verwalten."
    ),
}


def _calculate_postgres_effective_permissions(
    role_permissions,
    grants=(),
    denies=(),
):
    """Calculate effective PostgreSQL permissions and enforce dependencies."""
    effective = (set(role_permissions) | set(grants)) - set(denies)

    # Iterate until stable so transitive dependencies are enforced as well.
    changed = True
    while changed:
        changed = False

        for permission in tuple(effective):
            required = POSTGRES_PERMISSION_DEPENDENCIES.get(
                permission,
                set(),
            )

            if not required.issubset(effective):
                effective.remove(permission)
                changed = True

    return frozenset(effective)
