from server.migrations import MIGRATIONS
from server.migrations.rbac_seed import (
    RBAC_SEED_MIGRATION,
    RBAC_SEED_PERMISSIONS,
)
from server.security import (
    ROLE_ADMINISTRATOR,
    ROLE_DEFAULT_PERMISSIONS,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)


def test_rbac_seed_migration_is_registered_after_schema():
    versions = [migration.version for migration in MIGRATIONS]

    assert versions[:4] == [
        "001-core-schema",
        "002-security-schema",
        "003-rbac-schema",
        "004-rbac-system-roles",
    ]
    assert versions[4:] == [
        "005-infrastructure-topology",
        "006-telemetry",
        "007-package-search",
        "008-alerts",
    ]


def test_rbac_seed_permissions_are_a_frozen_snapshot_of_current_defaults():
    assert RBAC_SEED_PERMISSIONS == {
        ROLE_ADMINISTRATOR: frozenset(
            ROLE_DEFAULT_PERMISSIONS[ROLE_ADMINISTRATOR]
        ),
        ROLE_OPERATOR: frozenset(
            ROLE_DEFAULT_PERMISSIONS[ROLE_OPERATOR]
        ),
        ROLE_VIEWER: frozenset(
            ROLE_DEFAULT_PERMISSIONS[ROLE_VIEWER]
        ),
    }


def test_administrator_system_role_does_not_receive_permission_delegation():
    assert "permissions.manage" not in RBAC_SEED_PERMISSIONS[
        ROLE_ADMINISTRATOR
    ]


def test_seed_migration_uses_static_sql_and_is_checksum_ready():
    assert isinstance(RBAC_SEED_MIGRATION.statements, tuple)
    assert len(RBAC_SEED_MIGRATION.statements) == 12

    for statement in RBAC_SEED_MIGRATION.statements:
        assert isinstance(statement, str)
        assert statement.strip()
        assert "%s" not in statement
        assert "?" not in statement

    assert len(RBAC_SEED_MIGRATION.checksum) == 64


def test_seed_migration_protects_existing_role_definitions():
    sql = "\n".join(RBAC_SEED_MIGRATION.statements)

    for role_key in (
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
    ):
        assert f"system-{role_key}" in sql

    assert "is_system IS TRUE" in sql
    assert "is_migration IS FALSE" in sql
    assert "RBAC permission mismatch" in sql
    assert "ON CONFLICT (role_key) DO NOTHING" in sql
    assert "ON CONFLICT (role_id, permission) DO NOTHING" in sql
