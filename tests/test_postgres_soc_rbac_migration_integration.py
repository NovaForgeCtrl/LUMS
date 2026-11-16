"""PostgreSQL integration tests for migration 010-soc-rbac."""

from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from postgres_test_support import require_test_database_url, run_cleanup
from server.migration_runner import run_migrations
from server.migrations.core_schema import CORE_SCHEMA_MIGRATION
from server.migrations.security_schema import SECURITY_SCHEMA_MIGRATION
from server.migrations.rbac_schema import RBAC_SCHEMA_MIGRATION
from server.migrations.rbac_seed import RBAC_SEED_MIGRATION
from server.migrations.soc_rbac import SOC_RBAC_MIGRATION


BASE_MIGRATIONS = (
    CORE_SCHEMA_MIGRATION,
    SECURITY_SCHEMA_MIGRATION,
    RBAC_SCHEMA_MIGRATION,
    RBAC_SEED_MIGRATION,
)

TEST_MIGRATIONS = (*BASE_MIGRATIONS, SOC_RBAC_MIGRATION)

EXPECTED_SOC_PERMISSIONS = {
    ("system-administrator", "soc.view"),
    ("system-administrator", "soc.incidents.manage"),
    ("system-administrator", "soc.collectors.manage"),
    ("system-operator", "soc.view"),
    ("system-operator", "soc.incidents.manage"),
    ("system-viewer", "soc.view"),
}


@pytest.fixture
def postgres_environment():
    database_url = require_test_database_url()

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-soc-rbac-migration-setup",
    )

    connection = None
    schema_name = f"lums_soc_rbac_migration_{uuid4().hex}"
    schema_created = False

    try:
        identity = admin.execute(
            "SELECT current_database(), current_user"
        ).fetchone()

        if (
            identity["current_database"] != "lums_integration"
            or identity["current_user"] != "lums_pg_bootstrap"
        ):
            pytest.fail(
                "Refusing tests outside the dedicated integration database."
            )

        admin.execute(
            sql.SQL("CREATE SCHEMA {}").format(
                sql.Identifier(schema_name)
            )
        )
        schema_created = True

        connection = psycopg.connect(
            database_url,
            autocommit=True,
            row_factory=dict_row,
            application_name="lums-soc-rbac-migration-test",
        )
        connection.execute(
            sql.SQL("SET search_path TO {}").format(
                sql.Identifier(schema_name)
            )
        )

        base_result = run_migrations(connection, BASE_MIGRATIONS)
        assert base_result.applied == tuple(
            migration.version for migration in BASE_MIGRATIONS
        )

        yield connection

    finally:
        run_cleanup(
            (
                "close test connection",
                lambda: (
                    connection.close()
                    if connection is not None
                    else None
                ),
            ),
            (
                "drop test schema",
                lambda: admin.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema_name)
                    )
                ) if schema_created else None,
            ),
            ("close admin connection", admin.close),
        )


def _apply_soc_rbac(connection):
    return run_migrations(connection, TEST_MIGRATIONS)


def _soc_permissions(connection):
    rows = connection.execute(
        """
        SELECT roles.role_key, role_permissions.permission
        FROM roles
        JOIN role_permissions
          ON role_permissions.role_id = roles.id
        WHERE role_permissions.permission LIKE 'soc.%'
        ORDER BY roles.role_key, role_permissions.permission
        """
    ).fetchall()

    return {
        (row["role_key"], row["permission"])
        for row in rows
    }


def _assert_migration_not_recorded(connection):
    row = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM schema_migrations
        WHERE version = %s
        """,
        (SOC_RBAC_MIGRATION.version,),
    ).fetchone()

    assert row["count"] == 0


def test_soc_rbac_migration_applies_exact_permissions_and_is_idempotent(
    postgres_environment,
):
    connection = postgres_environment

    first = _apply_soc_rbac(connection)
    second = _apply_soc_rbac(connection)

    assert first.applied == ("010-soc-rbac",)
    assert second.applied == ()
    assert second.already_applied == tuple(
        migration.version for migration in TEST_MIGRATIONS
    )
    assert _soc_permissions(connection) == EXPECTED_SOC_PERMISSIONS

    history = connection.execute(
        """
        SELECT version, checksum, description
        FROM schema_migrations
        WHERE version = %s
        """,
        ("010-soc-rbac",),
    ).fetchone()

    assert history["checksum"] == SOC_RBAC_MIGRATION.checksum
    assert history["description"] == SOC_RBAC_MIGRATION.description


def test_soc_rbac_migration_does_not_modify_user_assignments_or_overrides(
    postgres_environment,
):
    connection = postgres_environment

    user = connection.execute(
        """
        INSERT INTO users (username, password_hash, created_at)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        ("soc-rbac-migration-test", "not-a-real-password-hash", "test"),
    ).fetchone()

    role = connection.execute(
        """
        SELECT id
        FROM roles
        WHERE role_key = 'system-operator'
        """
    ).fetchone()

    connection.execute(
        """
        INSERT INTO user_roles (user_id, role_id, assigned_at)
        VALUES (%s, %s, %s)
        """,
        (user["id"], role["id"], "before-migration"),
    )

    connection.execute(
        """
        INSERT INTO user_permission_overrides (
            user_id, permission, effect, changed_at
        )
        VALUES (%s, %s, %s, %s)
        """,
        (
            user["id"],
            "soc.collectors.manage",
            "deny",
            "before-migration",
        ),
    )

    before_roles = connection.execute(
        """
        SELECT user_id, role_id, assigned_at, assigned_by
        FROM user_roles
        ORDER BY user_id
        """
    ).fetchall()

    before_overrides = connection.execute(
        """
        SELECT user_id, permission, effect, changed_at, changed_by
        FROM user_permission_overrides
        ORDER BY user_id, permission
        """
    ).fetchall()

    _apply_soc_rbac(connection)

    after_roles = connection.execute(
        """
        SELECT user_id, role_id, assigned_at, assigned_by
        FROM user_roles
        ORDER BY user_id
        """
    ).fetchall()

    after_overrides = connection.execute(
        """
        SELECT user_id, permission, effect, changed_at, changed_by
        FROM user_permission_overrides
        ORDER BY user_id, permission
        """
    ).fetchall()

    assert after_roles == before_roles
    assert after_overrides == before_overrides
    assert _soc_permissions(connection) == EXPECTED_SOC_PERMISSIONS


@pytest.mark.parametrize(
    "mutation",
    (
        """
        UPDATE roles
        SET name = 'Unexpected Administrator'
        WHERE role_key = 'system-administrator'
        """,
        """
        INSERT INTO role_permissions (role_id, permission)
        SELECT id, 'unexpected.permission'
        FROM roles
        WHERE role_key = 'system-viewer'
        """,
        """
        DELETE FROM role_permissions
        WHERE role_id = (
            SELECT id
            FROM roles
            WHERE role_key = 'system-viewer'
        )
          AND permission = 'clients.view'
        """,
    ),
    ids=(
        "changed-system-role-metadata",
        "additional-frozen-permission",
        "missing-frozen-permission",
    ),
)
def test_soc_rbac_precondition_rejects_modified_baseline_without_changes(
    postgres_environment,
    mutation,
):
    connection = postgres_environment
    connection.execute(mutation)

    with pytest.raises(
        psycopg.errors.RaiseException,
        match="SOC RBAC precondition failed",
    ):
        _apply_soc_rbac(connection)

    assert _soc_permissions(connection) == set()
    _assert_migration_not_recorded(connection)


def test_soc_rbac_postcondition_failure_rolls_back_all_insertions(
    postgres_environment,
):
    connection = postgres_environment

    connection.execute(
        """
        CREATE FUNCTION inject_unexpected_soc_permission()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF NEW.permission = 'soc.view' THEN
                INSERT INTO role_permissions (role_id, permission)
                VALUES (NEW.role_id, 'soc.unexpected');
            END IF;

            RETURN NEW;
        END;
        $function$
        """
    )

    connection.execute(
        """
        CREATE TRIGGER inject_unexpected_soc_permission
        AFTER INSERT ON role_permissions
        FOR EACH ROW
        EXECUTE FUNCTION inject_unexpected_soc_permission()
        """
    )

    with pytest.raises(
        psycopg.errors.RaiseException,
        match="SOC RBAC postcondition failed: permission set differs",
    ):
        _apply_soc_rbac(connection)

    # The six intended inserts and the trigger's extra insert must all
    # have been rolled back with the failed migration transaction.
    assert _soc_permissions(connection) == set()
    _assert_migration_not_recorded(connection)

    # The original migration 004 baseline must remain intact.
    baseline_count = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM role_permissions
        """
    ).fetchone()

    assert baseline_count["count"] == 19
