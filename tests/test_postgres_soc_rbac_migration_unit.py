"""Unit tests for PostgreSQL migration 010-soc-rbac."""

from server.migrations import MIGRATIONS
from server.migrations.soc_rbac import SOC_RBAC_MIGRATION


EXPECTED_VERSIONS = [
    "001-core-schema",
    "002-security-schema",
    "003-rbac-schema",
    "004-rbac-system-roles",
    "005-infrastructure-topology",
    "006-telemetry",
    "007-package-search",
    "008-alerts",
    "009-soc-storage",
    "010-soc-rbac",
]


def test_soc_rbac_migration_is_registered_after_soc_storage():
    versions = [migration.version for migration in MIGRATIONS]

    assert versions == EXPECTED_VERSIONS
    assert MIGRATIONS[-1] is SOC_RBAC_MIGRATION


def test_soc_rbac_migration_contains_three_static_statements():
    migration = SOC_RBAC_MIGRATION

    assert migration.version == "010-soc-rbac"
    assert isinstance(migration.statements, tuple)
    assert len(migration.statements) == 3
    assert len(migration.checksum) == 64

    for statement in migration.statements:
        assert isinstance(statement, str)
        assert statement.strip()
        assert "?" not in statement
        assert "%s" not in statement


def test_precondition_checks_frozen_migration_004_snapshot():
    sql = SOC_RBAC_MIGRATION.statements[0]

    for expected in (
        "SOC RBAC precondition failed: system role mismatch",
        "SOC RBAC precondition failed: frozen migration 004 permissions differ",
        "system-administrator",
        "system-operator",
        "system-viewer",
        "alerts.manage",
        "alerts.view",
        "backups.manage",
        "clients.manage",
        "clients.view",
        "infrastructure.manage",
        "jobs.manage",
        "packages.search",
        "software.view",
        "system.update",
        "updates.view",
        "users.manage",
    ):
        assert expected in sql

    for forbidden in (
        "soc.view",
        "soc.incidents.manage",
        "soc.collectors.manage",
    ):
        assert forbidden not in sql


def test_insert_adds_only_the_six_expected_soc_role_assignments():
    sql = SOC_RBAC_MIGRATION.statements[1]

    expected = (
        "('system-administrator', 'soc.view')",
        "('system-administrator', 'soc.incidents.manage')",
        "('system-administrator', 'soc.collectors.manage')",
        "('system-operator', 'soc.view')",
        "('system-operator', 'soc.incidents.manage')",
        "('system-viewer', 'soc.view')",
    )

    for item in expected:
        assert item in sql

    assert "ON CONFLICT (role_id, permission) DO NOTHING" in sql
    assert "user_roles" not in sql
    assert "user_permission_overrides" not in sql


def test_postcondition_checks_exact_new_permission_sets():
    sql = SOC_RBAC_MIGRATION.statements[2]

    assert "SOC RBAC postcondition failed: system role mismatch" in sql
    assert "SOC RBAC postcondition failed: permission set differs" in sql

    for permission in (
        "soc.view",
        "soc.incidents.manage",
        "soc.collectors.manage",
    ):
        assert permission in sql

    assert sql.count("'soc.view'") == 6
    assert sql.count("'soc.incidents.manage'") == 4
    assert sql.count("'soc.collectors.manage'") == 2
