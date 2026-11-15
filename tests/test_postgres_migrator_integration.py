"""Least-privilege PostgreSQL integration test for the migration login."""

from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
import pytest

from postgres_test_support import require_test_database_url, run_cleanup
from server.migration_runner import run_migrations
from server.migrations import MIGRATIONS


def test_migrator_login_can_only_assume_owner_to_run_migrations():
    database_url = require_test_database_url()

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-migrator-lp-setup",
    )

    suffix = uuid4().hex
    owner_role = f"lums_migrator_owner_{suffix}"
    login_role = f"lums_migrator_login_{suffix}"
    unrelated_role = f"lums_migrator_unrelated_{suffix}"
    schema_name = f"lums_migrator_test_{suffix}"
    login_password = uuid4().hex + uuid4().hex

    owner_created = False
    login_created = False
    unrelated_created = False
    schema_created = False
    limited = None

    try:
        identity = admin.execute(
            "SELECT current_database(), current_user"
        ).fetchone()

        if (
            identity["current_database"] != "lums_integration"
            or identity["current_user"] != "lums_pg_bootstrap"
        ):
            pytest.fail(
                "Refusing migrator test outside lums_integration "
                "with lums_pg_bootstrap."
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

        admin.execute(
            sql.SQL(
                """
                CREATE ROLE {} LOGIN NOINHERIT PASSWORD {}
                NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS
                """
            ).format(
                sql.Identifier(login_role),
                sql.Literal(login_password),
            )
        )
        login_created = True

        admin.execute(
            sql.SQL(
                """
                CREATE ROLE {} NOLOGIN NOINHERIT
                NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS
                """
            ).format(sql.Identifier(unrelated_role))
        )
        unrelated_created = True

        admin.execute(
            sql.SQL(
                "GRANT CONNECT ON DATABASE lums_integration TO {}"
            ).format(sql.Identifier(login_role))
        )

        admin.execute(
            sql.SQL(
                "GRANT {} TO {} WITH INHERIT FALSE, SET TRUE"
            ).format(
                sql.Identifier(owner_role),
                sql.Identifier(login_role),
            )
        )

        limited = psycopg.connect(
            make_conninfo(
                database_url,
                user=login_role,
                password=login_password,
            ),
            autocommit=True,
            row_factory=dict_row,
            application_name="lums-migrator-lp-login",
        )

        login_identity = limited.execute(
            """
            SELECT
                session_user,
                current_user,
                rol.rolcanlogin,
                rol.rolinherit,
                rol.rolsuper,
                rol.rolcreatedb,
                rol.rolcreaterole,
                rol.rolreplication,
                rol.rolbypassrls
            FROM pg_roles AS rol
            WHERE rol.rolname = current_user
            """
        ).fetchone()

        assert login_identity == {
            "session_user": login_role,
            "current_user": login_role,
            "rolcanlogin": True,
            "rolinherit": False,
            "rolsuper": False,
            "rolcreatedb": False,
            "rolcreaterole": False,
            "rolreplication": False,
            "rolbypassrls": False,
        }

        membership = limited.execute(
            """
            SELECT
                granted.rolname,
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
            "rolname": owner_role,
            "inherit_option": False,
            "set_option": True,
            "admin_option": False,
        }]

        owner_properties = limited.execute(
            """
            SELECT
                rolcanlogin,
                rolsuper,
                rolcreatedb,
                rolcreaterole,
                rolreplication,
                rolbypassrls
            FROM pg_roles
            WHERE rolname = %s
            """,
            (owner_role,),
        ).fetchone()

        assert owner_properties == {
            "rolcanlogin": False,
            "rolsuper": False,
            "rolcreatedb": False,
            "rolcreaterole": False,
            "rolreplication": False,
            "rolbypassrls": False,
        }

        database_privileges = limited.execute(
            """
            SELECT
                has_database_privilege(
                    current_user, current_database(), 'CONNECT'
                ) AS can_connect,
                has_database_privilege(
                    current_user, current_database(), 'CREATE'
                ) AS can_create,
                has_database_privilege(
                    current_user, current_database(), 'TEMP'
                ) AS can_temp
            """
        ).fetchone()

        assert database_privileges["can_connect"] is True
        assert database_privileges["can_create"] is False

        schema_usage_before = limited.execute(
            "SELECT has_schema_privilege(current_user, %s, 'USAGE') AS allowed",
            (schema_name,),
        ).fetchone()["allowed"]

        assert schema_usage_before is False

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            limited.execute(
                sql.SQL("SET ROLE {}").format(
                    sql.Identifier(unrelated_role)
                )
            )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            limited.execute(
                sql.SQL("CREATE SCHEMA {}").format(
                    sql.Identifier(f"{schema_name}_forbidden")
                )
            )

        # This is the same role transition used by postgres_migrate.py.
        limited.execute(
            sql.SQL("SET ROLE {}").format(sql.Identifier(owner_role))
        )

        effective_identity = limited.execute(
            "SELECT session_user, current_user"
        ).fetchone()

        assert effective_identity == {
            "session_user": login_role,
            "current_user": owner_role,
        }

        limited.execute(
            sql.SQL("SET search_path TO {}").format(
                sql.Identifier(schema_name)
            )
        )

        first = run_migrations(limited, MIGRATIONS)

        expected_versions = tuple(
            migration.version for migration in MIGRATIONS
        )

        assert first.applied == expected_versions
        assert first.already_applied == ()

        history = limited.execute(
            """
            SELECT version, checksum
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()

        assert tuple(row["version"] for row in history) == expected_versions

        expected_checksums = {
            migration.version: migration.checksum
            for migration in MIGRATIONS
        }
        assert {
            row["version"]: row["checksum"]
            for row in history
        } == expected_checksums

        # A second run must be read-only and idempotent.
        second = run_migrations(limited, MIGRATIONS)
        assert second.applied == ()
        assert second.already_applied == expected_versions

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
              AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'i', 't')
            """,
            (schema_name,),
        ).fetchall()

        assert object_owners
        assert {row["owner"] for row in object_owners} == {owner_role}

        limited.execute("RESET ROLE")

        after_reset = limited.execute(
            """
            SELECT
                session_user,
                current_user,
                has_schema_privilege(
                    current_user, %s, 'USAGE'
                ) AS schema_usage,
                has_database_privilege(
                    current_user, current_database(), 'CREATE'
                ) AS database_create
            """,
            (schema_name,),
        ).fetchone()

        assert after_reset == {
            "session_user": login_role,
            "current_user": login_role,
            "schema_usage": False,
            "database_create": False,
        }

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            limited.execute(
                sql.SQL("CREATE TABLE {}.forbidden_table (id INTEGER)").format(
                    sql.Identifier(schema_name)
                )
            )

    finally:
        cleanup = [
            (
                "close limited migration connection",
                lambda: limited.close()
                if limited is not None
                else None,
            ),
        ]

        if login_created and owner_created:
            cleanup.append(
                (
                    "revoke owner membership",
                    lambda: admin.execute(
                        sql.SQL("REVOKE {} FROM {}").format(
                            sql.Identifier(owner_role),
                            sql.Identifier(login_role),
                        )
                    ),
                )
            )

        if schema_created:
            cleanup.append(
                (
                    "drop isolated migration schema",
                    lambda: admin.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                            sql.Identifier(schema_name)
                        )
                    ),
                )
            )

        if login_created:
            cleanup.append(
                (
                    "drop migrator login grants",
                    lambda: admin.execute(
                        sql.SQL("DROP OWNED BY {}").format(
                            sql.Identifier(login_role)
                        )
                    ),
                )
            )

        if unrelated_created:
            cleanup.append(
                (
                    "drop unrelated role grants",
                    lambda: admin.execute(
                        sql.SQL("DROP OWNED BY {}").format(
                            sql.Identifier(unrelated_role)
                        )
                    ),
                )
            )

        if owner_created:
            cleanup.append(
                (
                    "drop owner role grants",
                    lambda: admin.execute(
                        sql.SQL("DROP OWNED BY {}").format(
                            sql.Identifier(owner_role)
                        )
                    ),
                )
            )

        for role_name, created in (
            (unrelated_role, unrelated_created),
            (login_role, login_created),
            (owner_role, owner_created),
        ):
            if created:
                cleanup.append(
                    (
                        f"drop role {role_name}",
                        lambda role_name=role_name: admin.execute(
                            sql.SQL("DROP ROLE {}").format(
                                sql.Identifier(role_name)
                            )
                        ),
                    )
                )

        cleanup.append(("close setup connection", admin.close))
        run_cleanup(*cleanup)
