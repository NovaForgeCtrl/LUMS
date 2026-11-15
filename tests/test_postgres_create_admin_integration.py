"""Least-privilege PostgreSQL integration test for initial admin bootstrap."""

from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from postgres_test_support import require_test_database_url, run_cleanup
import pytest

from server.migration_runner import run_migrations
from server.migrations import MIGRATIONS
from server.postgres_create_admin import create_initial_admin


@pytest.fixture
def restricted_environment():
    database_url = require_test_database_url()
    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-admin-bootstrap-lp-setup",
    )

    suffix = uuid4().hex
    schema_name = f"lums_admin_bootstrap_{suffix}"
    owner_role = f"lums_admin_owner_{suffix}"
    privilege_role = f"lums_admin_privs_{suffix}"
    login_role = f"lums_admin_login_{suffix}"
    login_password = uuid4().hex + uuid4().hex

    owner_created = False
    schema_created = False
    privilege_role_created = False
    login_role_created = False
    migration_connection = None
    limited_connection = None

    try:
        identity = admin.execute(
            "SELECT current_database(), current_user"
        ).fetchone()

        if (
            identity["current_database"] != "lums_integration"
            or identity["current_user"] != "lums_pg_bootstrap"
        ):
            pytest.fail(
                "Refusing bootstrap test outside the dedicated "
                "lums_integration database and lums_pg_bootstrap role."
            )

        admin.execute(
            sql.SQL(
                """
                CREATE ROLE {} NOLOGIN NOINHERIT
                NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS
                """
            ).format(sql.Identifier(owner_role))
        )
        owner_created = True

        admin.execute(
            sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                sql.Identifier(schema_name),
                sql.Identifier(owner_role),
            )
        )
        schema_created = True

        migration_connection = psycopg.connect(
            database_url,
            autocommit=True,
            row_factory=dict_row,
            application_name="lums-admin-bootstrap-migrations",
        )
        migration_connection.execute(
            sql.SQL("SET ROLE {}").format(sql.Identifier(owner_role))
        )
        migration_connection.execute(
            sql.SQL("SET search_path TO {}").format(
                sql.Identifier(schema_name)
            )
        )

        result = run_migrations(migration_connection, MIGRATIONS)
        assert result.applied == tuple(
            migration.version for migration in MIGRATIONS
        )
        assert result.already_applied == ()

        migration_connection.execute("RESET ROLE")
        migration_connection.close()
        migration_connection = None

        admin.execute(
            sql.SQL(
                """
                CREATE ROLE {} NOLOGIN NOINHERIT
                NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS
                """
            ).format(sql.Identifier(privilege_role))
        )
        privilege_role_created = True

        admin.execute(
            sql.SQL(
                """
                CREATE ROLE {} LOGIN PASSWORD {}
                INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS
                """
            ).format(
                sql.Identifier(login_role),
                sql.Literal(login_password),
            )
        )
        login_role_created = True

        admin.execute(
            sql.SQL(
                "GRANT {} TO {} WITH INHERIT TRUE, SET FALSE"
            ).format(
                sql.Identifier(privilege_role),
                sql.Identifier(login_role),
            )
        )

        admin.execute(
            sql.SQL(
                "GRANT CONNECT ON DATABASE lums_integration TO {}"
            ).format(sql.Identifier(login_role))
        )

        admin.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(schema_name),
                sql.Identifier(privilege_role),
            )
        )

        column_grants = (
            (
                "schema_migrations",
                "SELECT",
                ("version", "checksum"),
            ),
            (
                "users",
                "SELECT",
                ("id", "enabled", "role"),
            ),
            (
                "users",
                "INSERT",
                ("username", "password_hash", "created_at", "enabled", "role"),
            ),
            (
                "roles",
                "SELECT",
                ("id", "role_key", "name", "is_system", "is_migration"),
            ),
            (
                "role_permissions",
                "SELECT",
                ("role_id", "permission"),
            ),
            (
                "user_roles",
                "SELECT",
                ("user_id", "role_id"),
            ),
            (
                "user_roles",
                "INSERT",
                ("user_id", "role_id", "assigned_at", "assigned_by"),
            ),
            (
                "user_permission_overrides",
                "SELECT",
                ("user_id", "permission", "effect"),
            ),
            (
                "user_permission_overrides",
                "INSERT",
                ("user_id", "permission", "effect", "changed_at", "changed_by"),
            ),
            (
                "audit_log",
                "INSERT",
                (
                    "timestamp",
                    "actor_type",
                    "actor_id",
                    "action",
                    "target",
                    "result",
                    "details",
                ),
            ),
        )

        for table, privilege, columns in column_grants:
            admin.execute(
                sql.SQL("GRANT {} ({}) ON TABLE {}.{} TO {}").format(
                    sql.SQL(privilege),
                    sql.SQL(", ").join(
                        sql.Identifier(column) for column in columns
                    ),
                    sql.Identifier(schema_name),
                    sql.Identifier(table),
                    sql.Identifier(privilege_role),
                )
            )

        limited_connection = psycopg.connect(
            make_conninfo(
                database_url,
                user=login_role,
                password=login_password,
            ),
            autocommit=True,
            row_factory=dict_row,
            application_name="lums-admin-bootstrap-limited-login",
        )
        limited_connection.execute(
            sql.SQL("SET search_path TO {}").format(
                sql.Identifier(schema_name)
            )
        )

        yield {
            "admin": admin,
            "limited": limited_connection,
            "schema": schema_name,
            "owner_role": owner_role,
            "privilege_role": privilege_role,
            "login_role": login_role,
        }

    finally:
        cleanup = [
            (
                "close limited connection",
                lambda: limited_connection.close()
                if limited_connection is not None
                else None,
            ),
            (
                "close migration connection",
                lambda: migration_connection.close()
                if migration_connection is not None
                else None,
            ),
        ]

        if login_role_created and privilege_role_created:
            cleanup.append(
                (
                    "revoke temporary role membership",
                    lambda: admin.execute(
                        sql.SQL("REVOKE {} FROM {}").format(
                            sql.Identifier(privilege_role),
                            sql.Identifier(login_role),
                        )
                    ),
                )
            )

        if login_role_created:
            cleanup.append(
                (
                    "drop login role grants",
                    lambda: admin.execute(
                        sql.SQL("DROP OWNED BY {}").format(
                            sql.Identifier(login_role)
                        )
                    ),
                )
            )

        if privilege_role_created:
            cleanup.append(
                (
                    "drop privilege role grants",
                    lambda: admin.execute(
                        sql.SQL("DROP OWNED BY {}").format(
                            sql.Identifier(privilege_role)
                        )
                    ),
                )
            )

        if schema_created:
            cleanup.append(
                (
                    "drop isolated bootstrap schema",
                    lambda: admin.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                            sql.Identifier(schema_name)
                        )
                    ),
                )
            )

        if login_role_created:
            cleanup.append(
                (
                    "drop temporary login role",
                    lambda: admin.execute(
                        sql.SQL("DROP ROLE {}").format(
                            sql.Identifier(login_role)
                        )
                    ),
                )
            )

        if privilege_role_created:
            cleanup.append(
                (
                    "drop temporary privilege role",
                    lambda: admin.execute(
                        sql.SQL("DROP ROLE {}").format(
                            sql.Identifier(privilege_role)
                        )
                    ),
                )
            )

        if owner_created:
            cleanup.append(
                (
                    "drop temporary owner role",
                    lambda: admin.execute(
                        sql.SQL("DROP ROLE {}").format(
                            sql.Identifier(owner_role)
                        )
                    ),
                )
            )

        cleanup.append(("close setup connection", admin.close))
        run_cleanup(*cleanup)


def test_initial_admin_bootstrap_works_without_owner_or_write_privileges(
    restricted_environment,
):
    env = restricted_environment
    admin = env["admin"]
    limited = env["limited"]
    schema_name = env["schema"]
    owner_role = env["owner_role"]
    privilege_role = env["privilege_role"]
    login_role = env["login_role"]

    identity = limited.execute(
        """
        SELECT
            session_user,
            current_user,
            role.rolcanlogin,
            role.rolinherit,
            role.rolsuper,
            role.rolcreatedb,
            role.rolcreaterole,
            role.rolreplication,
            role.rolbypassrls
        FROM pg_roles AS role
        WHERE role.rolname = current_user
        """
    ).fetchone()

    assert identity["session_user"] == login_role
    assert identity["current_user"] == login_role
    assert identity["rolcanlogin"] is True
    assert identity["rolinherit"] is True
    assert identity["rolsuper"] is False
    assert identity["rolcreatedb"] is False
    assert identity["rolcreaterole"] is False
    assert identity["rolreplication"] is False
    assert identity["rolbypassrls"] is False

    membership = limited.execute(
        """
        SELECT
            granted.rolname,
            member.rolname AS member_name,
            membership.inherit_option,
            membership.set_option,
            membership.admin_option
        FROM pg_auth_members AS membership
        JOIN pg_roles AS granted
          ON granted.oid = membership.roleid
        JOIN pg_roles AS member
          ON member.oid = membership.member
        WHERE member.rolname = current_user
        """
    ).fetchall()

    assert membership == [{
        "rolname": privilege_role,
        "member_name": login_role,
        "inherit_option": True,
        "set_option": False,
        "admin_option": False,
    }]

    schema_privileges = limited.execute(
        """
        SELECT
            has_schema_privilege(current_user, %s, 'USAGE') AS usage,
            has_schema_privilege(current_user, %s, 'CREATE') AS create
        """,
        (schema_name, schema_name),
    ).fetchone()

    assert schema_privileges["usage"] is True
    assert schema_privileges["create"] is False

    for table in (
        "users",
        "roles",
        "role_permissions",
        "user_roles",
        "user_permission_overrides",
        "schema_migrations",
        "audit_log",
    ):
        qualified_name = f"{schema_name}.{table}"
        privileges = limited.execute(
            """
            SELECT
                has_table_privilege(current_user, %s, 'UPDATE') AS update,
                has_table_privilege(current_user, %s, 'DELETE') AS delete,
                has_table_privilege(current_user, %s, 'TRUNCATE') AS truncate,
                has_table_privilege(current_user, %s, 'REFERENCES') AS references,
                has_table_privilege(current_user, %s, 'TRIGGER') AS trigger
            """,
            (
                qualified_name,
                qualified_name,
                qualified_name,
                qualified_name,
                qualified_name,
            ),
        ).fetchone()

        assert privileges == {
            "update": False,
            "delete": False,
            "truncate": False,
            "references": False,
            "trigger": False,
        }, table

    for forbidden_role in (privilege_role, owner_role):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            limited.execute(
                sql.SQL("SET ROLE {}").format(
                    sql.Identifier(forbidden_role)
                )
            )

    user_id = create_initial_admin(
        limited,
        "least-privilege-admin",
        "a-long-test-password-2026",
    )

    assert isinstance(user_id, int)
    assert user_id > 0

    persisted_user = admin.execute(
        sql.SQL(
            """
            SELECT id, username, enabled, role
            FROM {}.users
            WHERE id = %s
            """
        ).format(sql.Identifier(schema_name)),
        (user_id,),
    ).fetchone()

    assert persisted_user == {
        "id": user_id,
        "username": "least-privilege-admin",
        "enabled": True,
        "role": "administrator",
    }

    assignment = admin.execute(
        sql.SQL(
            """
            SELECT roles.role_key
            FROM {}.user_roles AS assignments
            JOIN {}.roles AS roles
              ON roles.id = assignments.role_id
            WHERE assignments.user_id = %s
            """
        ).format(
            sql.Identifier(schema_name),
            sql.Identifier(schema_name),
        ),
        (user_id,),
    ).fetchall()

    assert assignment == [{"role_key": "system-administrator"}]

    overrides = admin.execute(
        sql.SQL(
            """
            SELECT permission, effect
            FROM {}.user_permission_overrides
            WHERE user_id = %s
            """
        ).format(sql.Identifier(schema_name)),
        (user_id,),
    ).fetchall()

    assert overrides == [{
        "permission": "permissions.manage",
        "effect": "grant",
    }]

    audit = admin.execute(
        sql.SQL(
            """
            SELECT action, target, result
            FROM {}.audit_log
            WHERE target = %s
            """
        ).format(sql.Identifier(schema_name)),
        (f"user:{user_id}",),
    ).fetchall()

    assert audit == [{
        "action": "admin_created",
        "target": f"user:{user_id}",
        "result": "success",
    }]

    # The bootstrap login must not gain mutation or schema privileges
    # as a side effect of creating the administrator.
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        limited.execute(
            sql.SQL("UPDATE {}.users SET enabled = FALSE WHERE id = %s").format(
                sql.Identifier(schema_name)
            ),
            (user_id,),
        )

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        limited.execute(
            sql.SQL("DELETE FROM {}.users WHERE id = %s").format(
                sql.Identifier(schema_name)
            ),
            (user_id,),
        )

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        limited.execute(
            sql.SQL("CREATE TABLE {}.bootstrap_forbidden (id INTEGER)").format(
                sql.Identifier(schema_name)
            )
        )

    # The objects remain owned by the separate NOLOGIN owner role.
    schema_owner = admin.execute(
        """
        SELECT pg_get_userbyid(nspowner) AS owner
        FROM pg_namespace
        WHERE nspname = %s
        """,
        (schema_name,),
    ).fetchone()
    assert schema_owner["owner"] == owner_role

    object_owners = admin.execute(
        """
        SELECT DISTINCT pg_get_userbyid(c.relowner) AS owner
        FROM pg_class AS c
        JOIN pg_namespace AS n
          ON n.oid = c.relnamespace
        WHERE n.nspname = %s
          AND c.relkind IN ('r', 'p', 'S')
        """,
        (schema_name,),
    ).fetchall()

    assert object_owners
    assert {row["owner"] for row in object_owners} == {owner_role}

    # Identity sequence privileges are not granted to the bootstrap login.
    for table in ("users", "audit_log"):
        sequence_name = admin.execute(
            "SELECT pg_get_serial_sequence(%s, 'id') AS name",
            (f"{schema_name}.{table}",),
        ).fetchone()["name"]
        assert sequence_name is not None

        sequence_usage = limited.execute(
            "SELECT has_sequence_privilege(current_user, %s, 'USAGE') AS allowed",
            (sequence_name,),
        ).fetchone()["allowed"]
        assert sequence_usage is False
