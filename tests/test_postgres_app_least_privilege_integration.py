"""Flask login/session integration using a restricted PostgreSQL role."""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from argon2 import PasswordHasher
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from postgres_test_support import require_test_database_url, run_cleanup
from server.migration_runner import run_migrations
from server.migrations import MIGRATIONS
from server.postgres_app import create_postgres_app
from server.rbac_lock import acquire_rbac_write_lock
from server.postgres_rbac import grant_initial_permission_manager
from server.security import password_needs_rehash


BASE_URL = "https://localhost"
TEST_PASSWORD = "lums-integration-password-2026"


def _grant_columns(admin, schema, role, table, privilege, columns):
    admin.execute(
        sql.SQL("GRANT {} ({}) ON TABLE {}.{} TO {}").format(
            sql.SQL(privilege),
            sql.SQL(", ").join(
                sql.Identifier(column) for column in columns
            ),
            sql.Identifier(schema),
            sql.Identifier(table),
            sql.Identifier(role),
        )
    )


def _open_app_connection(
    database_url, login_role, password, schema
):
    connection = psycopg.connect(
        make_conninfo(
            database_url,
            user=login_role,
            password=password,
        ),
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=5,
        application_name="lums-app-least-privilege-test",
    )
    try:
        connection.execute(
            sql.SQL("SET search_path TO {}").format(
                sql.Identifier(schema)
            )
        )
    except BaseException:
        connection.close()
        raise
    return connection


def _csrf_token(client):
    with client.session_transaction(base_url=BASE_URL) as session:
        token = session.get("csrf_token")
    assert isinstance(token, str) and token
    return token


def _submit_login(client, username, password):
    return client.post(
        "/login",
        base_url=BASE_URL,
        data={
            "username": username,
            "password": password,
            "language": "en",
            "csrf_token": _csrf_token(client),
        },
    )


def test_real_flask_login_and_session_use_restricted_database_role():
    database_url = require_test_database_url()

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=5,
        application_name="lums-app-least-privilege-setup",
    )

    suffix = uuid4().hex[:12]
    schema = f"lums_app_lp_{suffix}"
    owner = f"lums_app_lp_owner_{suffix}"
    privileges = f"lums_app_lp_privs_{suffix}"
    login = f"lums_app_lp_login_{suffix}"
    password = secrets.token_urlsafe(36)
    username = f"app-lp-viewer-{suffix}"

    owner_created = False
    privileges_created = False
    login_created = False
    membership_created = False
    schema_created = False
    setup = None
    app_connections = []

    try:
        identity = admin.execute(
            "SELECT current_database(), current_user"
        ).fetchone()

        if (
            identity["current_database"] != "lums_integration"
            or identity["current_user"] != "lums_pg_bootstrap"
        ):
            pytest.fail(
                "Refusing test outside lums_integration/"
                "lums_pg_bootstrap."
            )

        admin.execute(
            sql.SQL(
                """
                CREATE ROLE {} NOLOGIN NOINHERIT
                NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS
                """
            ).format(sql.Identifier(owner))
        )
        owner_created = True

        admin.execute(
            sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                sql.Identifier(schema), sql.Identifier(owner)
            )
        )
        schema_created = True

        setup = psycopg.connect(
            database_url,
            autocommit=True,
            row_factory=dict_row,
            connect_timeout=5,
            application_name="lums-app-least-privilege-migrations",
        )
        setup.execute(
            sql.SQL("SET ROLE {}").format(sql.Identifier(owner))
        )
        setup.execute(
            sql.SQL("SET search_path TO {}").format(
                sql.Identifier(schema)
            )
        )

        migration_result = run_migrations(setup, MIGRATIONS)
        assert migration_result.applied == tuple(
            migration.version for migration in MIGRATIONS
        )
        assert migration_result.already_applied == ()

        # A deliberately outdated Argon2 hash exercises password rehash.
        old_hasher = PasswordHasher(
            time_cost=1,
            memory_cost=1024,
            parallelism=1,
        )
        old_hash = old_hasher.hash(TEST_PASSWORD)
        assert password_needs_rehash(old_hash)

        created_at = datetime.now(timezone.utc).isoformat()

        # The test actor is the sole initial administrator.  Bootstrap the
        # permission-manager override through the production RBAC helper.
        with setup.transaction():
            acquire_rbac_write_lock(setup)

            user = setup.execute(
                """
                INSERT INTO users (
                    username, password_hash, created_at,
                    enabled, role, language
                )
                VALUES (%s, %s, %s, TRUE, 'administrator', '')
                RETURNING id
                """,
                (username, old_hash, created_at),
            ).fetchone()

            admin_role = setup.execute(
                """
                SELECT id
                FROM roles
                WHERE role_key = 'system-administrator'
                """
            ).fetchone()
            assert admin_role is not None

            setup.execute(
                """
                INSERT INTO user_roles (
                    user_id, role_id, assigned_at, assigned_by
                )
                VALUES (%s, %s, %s, NULL)
                """,
                (user["id"], admin_role["id"], created_at),
            )

            assert grant_initial_permission_manager(
                setup,
                user["id"],
                timestamp=created_at,
            ) is True

        setup.execute("RESET ROLE")
        setup.close()
        setup = None

        admin.execute(
            sql.SQL(
                """
                CREATE ROLE {} NOLOGIN NOINHERIT
                NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS
                """
            ).format(sql.Identifier(privileges))
        )
        privileges_created = True

        admin.execute(
            sql.SQL(
                """
                CREATE ROLE {} LOGIN PASSWORD {}
                INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS
                """
            ).format(sql.Identifier(login), sql.Literal(password))
        )
        login_created = True

        admin.execute(
            sql.SQL(
                "GRANT {} TO {} WITH INHERIT TRUE, SET FALSE"
            ).format(sql.Identifier(privileges), sql.Identifier(login))
        )
        membership_created = True

        admin.execute(
            sql.SQL(
                "GRANT CONNECT ON DATABASE lums_integration TO {}"
            ).format(sql.Identifier(login))
        )
        admin.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(schema), sql.Identifier(privileges)
            )
        )

        grants = (
            # Authentication and user listing.
            ("users", "SELECT", (
                "id", "username", "password_hash", "enabled", "role",
                "language", "created_at", "admin_note", "first_name",
                "last_name", "department", "function_id",
            )),
            ("user_roles", "SELECT", ("user_id", "role_id")),
            ("roles", "SELECT", (
                "id", "role_key", "is_system", "is_migration",
            )),
            ("role_permissions", "SELECT", ("role_id", "permission")),
            ("user_permission_overrides", "SELECT", (
                "user_id", "permission", "effect",
            )),
            ("user_functions", "SELECT", (
                "id", "name", "created_at", "created_by",
            )),

            # Columns required by PostgreSQL API delete operations.
            ("alert_rules", "SELECT", ("rule_id",)),
            ("infrastructure_nodes", "SELECT", ("id",)),
            # SELECT FOR UPDATE also requires UPDATE on at least one column.
            ("infrastructure_nodes", "UPDATE", ("name",)),
            ("infrastructure_relations", "SELECT", ("id",)),

            # Client management, agent authentication and client views.
            ("clients", "SELECT", (
                "id", "hostname", "ip", "os", "kernel", "architecture",
                "agent_version", "last_seen", "idle", "idle_seconds",
                "idle_threshold_seconds", "idle_source", "idle_supported",
                "enabled", "client_token_hash", "token_created_at",
                "token_revoked_at",
            )),
            ("available_updates", "SELECT", (
                "id", "client_id", "package",
                "installed_version", "available_version",
            )),
            ("installed_packages", "SELECT", (
                "id", "client_id", "package", "version",
            )),

            # Telemetry history, system snapshots and generated events.
            ("client_telemetry", "SELECT", (
                "client_id", "recorded_at", "cpu_percent",
                "memory_percent", "memory_total_bytes",
                "memory_available_bytes", "network_rx_bytes",
                "network_tx_bytes", "disk_percent",
            )),
            ("client_system_status", "SELECT", (
                "client_id", "recorded_at", "payload_json",
            )),
            ("client_telemetry_events", "SELECT", (
                "client_id", "recorded_at", "event_type", "metric", "value",
            )),
            ("user_dashboard_settings", "SELECT", (
                "user_id", "settings_json", "updated_at",
            )),

            # Only the columns written by authentication and user routes.
            ("users", "UPDATE", (
                "language", "password_hash", "role",
                "first_name", "last_name", "department",
                "function_id", "admin_note",
            )),
            ("users", "INSERT", (
                "username", "password_hash", "created_at",
                "enabled", "role",
            )),

            # Client registration, token rotation, disable and agent reports.
            ("clients", "INSERT", (
                "hostname", "ip", "os", "kernel", "architecture",
                "agent_version", "last_seen", "client_token_hash",
                "token_created_at", "token_revoked_at", "enabled",
            )),
            ("clients", "UPDATE", (
                "hostname", "ip", "os", "kernel", "architecture",
                "agent_version", "last_seen", "idle", "idle_seconds",
                "idle_threshold_seconds", "idle_source", "idle_supported",
                "client_token_hash", "token_created_at",
                "token_revoked_at", "enabled",
            )),
            ("available_updates", "INSERT", (
                "client_id", "package", "installed_version",
                "available_version",
            )),
            ("installed_packages", "INSERT", (
                "client_id", "package", "version",
            )),

            # Telemetry ingestion and event generation.
            ("client_telemetry", "INSERT", (
                "client_id", "recorded_at", "cpu_percent",
                "memory_percent", "memory_total_bytes",
                "memory_available_bytes", "network_rx_bytes",
                "network_tx_bytes", "disk_percent",
            )),
            ("client_system_status", "INSERT", (
                "client_id", "recorded_at", "payload_json",
            )),
            ("client_system_status", "UPDATE", (
                "recorded_at", "payload_json",
            )),
            ("client_telemetry_events", "INSERT", (
                "client_id", "recorded_at", "event_type", "metric", "value",
            )),

            # Per-user telemetry dashboard configuration.
            ("user_dashboard_settings", "INSERT", (
                "user_id", "settings_json", "updated_at",
            )),
            ("user_dashboard_settings", "UPDATE", (
                "settings_json", "updated_at",
            )),

            # User/RBAC association writes.
            ("user_roles", "INSERT", (
                "user_id", "role_id", "assigned_at", "assigned_by",
            )),
            ("user_permission_overrides", "INSERT", (
                "user_id", "permission", "effect",
                "changed_at", "changed_by",
            )),

            # User-function creation.
            ("user_functions", "INSERT", (
                "name", "created_at", "created_by",
            )),

            # Login rate limiting.
            ("login_rate_limits", "SELECT", (
                "id", "rate_limit_key", "username", "failed_attempts",
                "first_failed_at", "last_failed_at", "locked_until",
            )),
            ("login_rate_limits", "INSERT", (
                "rate_limit_key", "username", "failed_attempts",
                "first_failed_at", "last_failed_at", "locked_until",
            )),
            ("login_rate_limits", "UPDATE", (
                "username", "failed_attempts",
                "last_failed_at", "locked_until",
            )),

            # Atomic audit entries.
            ("audit_log", "INSERT", (
                "timestamp", "actor_type", "actor_id",
                "action", "target", "result", "details",
            )),
        )

        for table, privilege, columns in grants:
            _grant_columns(
                admin, schema, privileges, table, privilege, columns
            )

        # DELETE is table-level because PostgreSQL has no column-level
        # DELETE privilege. The foreign-key actions are tested separately.
        for table in (
            "login_rate_limits",
            "users",
            "user_roles",
            "user_permission_overrides",
            "user_functions",
            "available_updates",
            "installed_packages",
            "client_telemetry",
            "client_telemetry_events",
            "alert_rules",
            "infrastructure_nodes",
            "infrastructure_relations",
        ):
            admin.execute(
                sql.SQL(
                    "GRANT DELETE ON TABLE {}.{} TO {}"
                ).format(
                    sql.Identifier(schema),
                    sql.Identifier(table),
                    sql.Identifier(privileges),
                )
            )

        def connection_factory():
            connection = _open_app_connection(
                database_url, login, password, schema
            )
            app_connections.append(connection)
            return connection

        app = create_postgres_app({
            "SECRET_KEY": "test-only-app-least-privilege-secret",
            "TESTING": True,
            "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
        })
        client = app.test_client()

        # Obtain the anonymous login CSRF token.
        response = client.get("/login", base_url=BASE_URL)
        assert response.status_code == 200

        # First failed login: INSERT into login_rate_limits.
        response = _submit_login(
            client, username, "incorrect-password"
        )
        assert response.status_code == 401

        # Second failed login: ON CONFLICT DO UPDATE.
        response = _submit_login(
            client, username, "incorrect-password"
        )
        assert response.status_code == 401

        with client.session_transaction(base_url=BASE_URL) as session:
            assert "user_id" not in session

        failed_state = admin.execute(
            sql.SQL(
                """
                SELECT failed_attempts
                FROM {}.login_rate_limits
                WHERE username = %s
                """
            ).format(sql.Identifier(schema)),
            (username,),
        ).fetchone()
        assert failed_state["failed_attempts"] == 2

        # Successful login: row lock, password rehash, language update,
        # rate-limit DELETE, audit INSERT and session creation.
        response = _submit_login(client, username, TEST_PASSWORD)
        assert response.status_code == 302

        with client.session_transaction(base_url=BASE_URL) as session:
            assert session["user_id"] == user["id"]
            assert session["username"] == username

        # A real protected route runs the read-only authorization loader.
        response = client.get("/api/status", base_url=BASE_URL)
        assert response.status_code == 200
        assert response.get_json()["backend"] == "postgresql"
        assert response.get_json()["authenticated"] is True

        # Exercise the real user-management routes through Flask.
        # All requests use the restricted PostgreSQL application login.
        response = client.get("/api/users", base_url=BASE_URL)
        assert response.status_code == 200, response.get_json()
        assert any(
            item["id"] == user["id"]
            for item in response.get_json()
        )

        function_name = f"app-lp-function-{suffix}"
        response = client.post(
            "/api/user-functions",
            base_url=BASE_URL,
            json={"name": function_name},
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert response.status_code == 201, response.get_json()
        function_id = response.get_json()["function"]["id"]

        response = client.get(
            "/api/user-functions",
            base_url=BASE_URL,
        )
        assert response.status_code == 200, response.get_json()
        assert any(
            item["id"] == function_id
            and item["name"] == function_name
            for item in response.get_json()
        )

        target_username = f"app-lp-target-{suffix}"
        response = client.post(
            "/api/users",
            base_url=BASE_URL,
            json={
                "username": target_username,
                "password": TEST_PASSWORD + "-target",
                "role": "viewer",
            },
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert response.status_code == 201, response.get_json()

        created_user = response.get_json()["user"]
        target_id = created_user["id"]
        assert created_user["username"] == target_username
        assert created_user["permissions"] == [
            "clients.view",
            "soc.view",
            "software.view",
        ]

        response = client.put(
            f"/api/users/{target_id}/profile",
            base_url=BASE_URL,
            json={
                "first_name": "Integration",
                "last_name": "Target",
                "department": "Least Privilege",
                "function_id": function_id,
            },
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert response.status_code == 200, response.get_json()
        assert response.get_json()["function_id"] == function_id

        response = client.put(
            f"/api/users/{target_id}/note",
            base_url=BASE_URL,
            json={"note": "Restricted-role integration test"},
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert response.status_code == 200, response.get_json()
        assert response.get_json()["note"] == (
            "Restricted-role integration test"
        )

        # A custom permission selection creates a real deny override.
        response = client.put(
            f"/api/users/{target_id}/permissions",
            base_url=BASE_URL,
            json={
                "role": "viewer",
                "permissions": ["clients.view"],
            },
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert response.status_code == 200, response.get_json()
        assert response.get_json()["user"]["permissions"] == [
            "clients.view"
        ]

        override = admin.execute(
            sql.SQL(
                """
                SELECT permission, effect
                FROM {}.user_permission_overrides
                WHERE user_id = %s
                """
            ).format(sql.Identifier(schema)),
            (target_id,),
        ).fetchall()
        assert {
            (row["permission"], row["effect"])
            for row in override
        } == {
            ("soc.view", "deny"),
            ("software.view", "deny"),
        }

        response = client.get("/api/users", base_url=BASE_URL)
        assert response.status_code == 200, response.get_json()
        listed_target = next(
            item for item in response.get_json()
            if item["id"] == target_id
        )
        assert listed_target["first_name"] == "Integration"
        assert listed_target["last_name"] == "Target"
        assert listed_target["department"] == "Least Privilege"
        assert listed_target["admin_note"] == (
            "Restricted-role integration test"
        )
        assert listed_target["function_id"] == function_id
        assert listed_target["permissions"] == ["clients.view"]

        # Verify ON DELETE SET NULL without direct UPDATE permission
        # on users.function_id for the application role.
        admin.execute(
            sql.SQL(
                "REVOKE UPDATE (function_id) ON TABLE {}.users FROM {}"
            ).format(
                sql.Identifier(schema),
                sql.Identifier(privileges),
            )
        )
        function_update = admin.execute(
            """
            SELECT has_column_privilege(
                %s, %s, 'function_id', 'UPDATE'
            ) AS allowed
            """,
            (login, f"{schema}.users"),
        ).fetchone()
        assert function_update["allowed"] is False

        response = client.delete(
            f"/api/user-functions/{function_id}",
            base_url=BASE_URL,
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert response.status_code == 200, response.get_json()

        function_fk_state = admin.execute(
            sql.SQL(
                "SELECT function_id FROM {}.users WHERE id = %s"
            ).format(sql.Identifier(schema)),
            (target_id,),
        ).fetchone()
        assert function_fk_state["function_id"] is None

        function_remaining = admin.execute(
            sql.SQL(
                "SELECT count(*) AS total FROM {}.user_functions WHERE id = %s"
            ).format(sql.Identifier(schema)),
            (function_id,),
        ).fetchone()
        assert function_remaining["total"] == 0

        # Restore the normal application column grant after the FK test.
        admin.execute(
            sql.SQL(
                "GRANT UPDATE (function_id) ON TABLE {}.users TO {}"
            ).format(
                sql.Identifier(schema),
                sql.Identifier(privileges),
            )
        )

        # Prepare the remaining user-referencing FK rows as schema owner.
        # The application role must not receive direct UPDATE/DELETE rights
        # on these referencing tables just to make the FK actions work.
        fixture_connection = psycopg.connect(
            database_url,
            autocommit=True,
            row_factory=dict_row,
            connect_timeout=5,
            application_name="lums-app-least-privilege-fk-fixtures",
        )
        try:
            fixture_connection.execute(
                sql.SQL("SET ROLE {}").format(sql.Identifier(owner))
            )
            fixture_connection.execute(
                sql.SQL("SET search_path TO {}").format(
                    sql.Identifier(schema)
                )
            )

            fk_role = fixture_connection.execute(
                """
                INSERT INTO roles (
                    role_key, name, description,
                    is_system, is_migration,
                    created_at, updated_at,
                    created_by, updated_by
                )
                VALUES (%s, %s, %s, FALSE, FALSE, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    f"app-lp-fk-role-{suffix}",
                    f"FK reference role {suffix}",
                    "Integration-test-only FK reference",
                    created_at,
                    created_at,
                    target_id,
                    target_id,
                ),
            ).fetchone()

            fk_function = fixture_connection.execute(
                """
                INSERT INTO user_functions (
                    name, created_at, created_by
                )
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (
                    f"app-lp-fk-function-{suffix}",
                    created_at,
                    target_id,
                ),
            ).fetchone()

            node_a = fixture_connection.execute(
                """
                INSERT INTO infrastructure_nodes (
                    name, node_type, created_at, updated_at, created_by
                )
                VALUES (%s, 'server', %s, %s, %s)
                RETURNING id
                """,
                (
                    f"app-lp-fk-node-a-{suffix}",
                    created_at,
                    created_at,
                    target_id,
                ),
            ).fetchone()

            node_b = fixture_connection.execute(
                """
                INSERT INTO infrastructure_nodes (
                    name, node_type, created_at, updated_at, created_by
                )
                VALUES (%s, 'vm', %s, %s, %s)
                RETURNING id
                """,
                (
                    f"app-lp-fk-node-b-{suffix}",
                    created_at,
                    created_at,
                    target_id,
                ),
            ).fetchone()

            fk_relation = fixture_connection.execute(
                """
                INSERT INTO infrastructure_relations (
                    source_node_id,
                    target_node_id,
                    relation_type,
                    details,
                    created_at,
                    created_by
                )
                VALUES (%s, %s, 'depends_on', %s, %s, %s)
                RETURNING id
                """,
                (
                    node_a["id"],
                    node_b["id"],
                    "FK integration reference",
                    created_at,
                    target_id,
                ),
            ).fetchone()

            fixture_connection.execute(
                """
                INSERT INTO user_dashboard_settings (
                    user_id, settings_json, updated_at
                )
                VALUES (%s, '{}'::jsonb, %s)
                """,
                (target_id, datetime.now(timezone.utc)),
            )

            reference_user = fixture_connection.execute(
                """
                INSERT INTO users (
                    username, password_hash, created_at, enabled, role
                )
                VALUES (%s, %s, %s, TRUE, 'viewer')
                RETURNING id
                """,
                (
                    f"app-lp-fk-reference-{suffix}",
                    old_hash,
                    created_at,
                ),
            ).fetchone()

            viewer_role = fixture_connection.execute(
                """
                SELECT id
                FROM roles
                WHERE role_key = 'system-viewer'
                """
            ).fetchone()
            assert viewer_role is not None

            fixture_connection.execute(
                """
                INSERT INTO user_roles (
                    user_id, role_id, assigned_at, assigned_by
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    reference_user["id"],
                    viewer_role["id"],
                    created_at,
                    target_id,
                ),
            )

            fixture_connection.execute(
                """
                INSERT INTO user_permission_overrides (
                    user_id, permission, effect, changed_at, changed_by
                )
                VALUES (%s, 'software.view', 'deny', %s, %s)
                """,
                (
                    reference_user["id"],
                    created_at,
                    target_id,
                ),
            )

            # One deletable and one FK-protected alert rule.
            delete_alert_rule_id = f"app-lp-delete-rule-{suffix}"
            referenced_alert_rule_id = f"app-lp-referenced-rule-{suffix}"

            for rule_id, rule_name in (
                (delete_alert_rule_id, f"Delete rule {suffix}"),
                (referenced_alert_rule_id, f"Referenced rule {suffix}"),
            ):
                fixture_connection.execute(
                    """
                    INSERT INTO alert_rules (
                        rule_id, name, condition, threshold, severity
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    """,
                    (
                        rule_id,
                        rule_name,
                        "cpu_usage",
                        '{"operator":">","value":90}',
                        "warning",
                    ),
                )

            fixture_connection.execute(
                """
                INSERT INTO alerts (
                    alert_id, rule_id, source, message, severity, status
                )
                VALUES (%s, %s, %s, %s, 'warning', 'triggered')
                """,
                (
                    f"app-lp-alert-{suffix}",
                    referenced_alert_rule_id,
                    "least-privilege-test",
                    "Rule reference prevents deletion",
                ),
            )

            def add_node(name, node_type):
                return fixture_connection.execute(
                    """
                    INSERT INTO infrastructure_nodes (
                        name, node_type, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (name, node_type, created_at, created_at),
                ).fetchone()["id"]

            direct_source_node_id = add_node(
                f"app-lp-direct-source-{suffix}", "server"
            )
            direct_target_node_id = add_node(
                f"app-lp-direct-target-{suffix}", "vm"
            )
            cascade_source_node_id = add_node(
                f"app-lp-cascade-source-{suffix}", "server"
            )
            cascade_target_node_id = add_node(
                f"app-lp-cascade-target-{suffix}", "vm"
            )

            def add_relation(source_id, target_id, relation_type, details):
                return fixture_connection.execute(
                    """
                    INSERT INTO infrastructure_relations (
                        source_node_id, target_node_id,
                        relation_type, details, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        source_id,
                        target_id,
                        relation_type,
                        details,
                        created_at,
                    ),
                ).fetchone()["id"]

            direct_relation_id = add_relation(
                direct_source_node_id,
                direct_target_node_id,
                "depends_on",
                "Direct relation DELETE test",
            )

            cascade_relation_id = add_relation(
                cascade_source_node_id,
                cascade_target_node_id,
                "hosts",
                "Node DELETE cascade test",
            )
        finally:
            fixture_connection.close()

        # Confirm that the application role cannot directly update the
        # SET NULL columns or delete the dashboard row.
        fk_direct_privileges = admin.execute(
            """
            SELECT
                has_column_privilege(
                    %s, %s, 'created_by', 'UPDATE'
                ) AS roles_created_by_update,
                has_column_privilege(
                    %s, %s, 'updated_by', 'UPDATE'
                ) AS roles_updated_by_update,
                has_column_privilege(
                    %s, %s, 'created_by', 'UPDATE'
                ) AS functions_created_by_update,
                has_column_privilege(
                    %s, %s, 'assigned_by', 'UPDATE'
                ) AS user_roles_assigned_by_update,
                has_column_privilege(
                    %s, %s, 'changed_by', 'UPDATE'
                ) AS overrides_changed_by_update,
                has_column_privilege(
                    %s, %s, 'created_by', 'UPDATE'
                ) AS nodes_created_by_update,
                has_column_privilege(
                    %s, %s, 'created_by', 'UPDATE'
                ) AS relations_created_by_update,
                has_table_privilege(
                    %s, %s, 'DELETE'
                ) AS dashboard_settings_delete
            """,
            (
                login, f"{schema}.roles",
                login, f"{schema}.roles",
                login, f"{schema}.user_functions",
                login, f"{schema}.user_roles",
                login, f"{schema}.user_permission_overrides",
                login, f"{schema}.infrastructure_nodes",
                login, f"{schema}.infrastructure_relations",
                login, f"{schema}.user_dashboard_settings",
            ),
        ).fetchone()

        assert fk_direct_privileges == {
            "roles_created_by_update": False,
            "roles_updated_by_update": False,
            "functions_created_by_update": False,
            "user_roles_assigned_by_update": False,
            "overrides_changed_by_update": False,
            "nodes_created_by_update": False,
            "relations_created_by_update": False,
            "dashboard_settings_delete": False,
        }

        # Both association rows exist before testing ON DELETE CASCADE.
        for table in ("user_roles", "user_permission_overrides"):
            row = admin.execute(
                sql.SQL(
                    "SELECT count(*) AS total FROM {}.{} WHERE user_id = %s"
                ).format(
                    sql.Identifier(schema),
                    sql.Identifier(table),
                ),
                (target_id,),
            ).fetchone()
            assert row["total"] > 0, table

        # Revoke direct child-table DELETE rights. The parent-row deletion
        # must still perform its declared FK cascades.
        for table in ("user_roles", "user_permission_overrides"):
            admin.execute(
                sql.SQL(
                    "REVOKE DELETE ON TABLE {}.{} FROM {}"
                ).format(
                    sql.Identifier(schema),
                    sql.Identifier(table),
                    sql.Identifier(privileges),
                )
            )

        child_delete_state = admin.execute(
            """
            SELECT
                has_table_privilege(%s, %s, 'DELETE') AS user_roles_delete,
                has_table_privilege(%s, %s, 'DELETE') AS overrides_delete
            """,
            (
                login,
                f"{schema}.user_roles",
                login,
                f"{schema}.user_permission_overrides",
            ),
        ).fetchone()
        assert child_delete_state == {
            "user_roles_delete": False,
            "overrides_delete": False,
        }

        response = client.delete(
            f"/api/users/{target_id}",
            base_url=BASE_URL,
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert response.status_code == 200, response.get_json()

        deleted_user = admin.execute(
            sql.SQL(
                "SELECT count(*) AS total FROM {}.users WHERE id = %s"
            ).format(sql.Identifier(schema)),
            (target_id,),
        ).fetchone()
        assert deleted_user["total"] == 0

        for table in ("user_roles", "user_permission_overrides"):
            row = admin.execute(
                sql.SQL(
                    "SELECT count(*) AS total FROM {}.{} WHERE user_id = %s"
                ).format(
                    sql.Identifier(schema),
                    sql.Identifier(table),
                ),
                (target_id,),
            ).fetchone()
            assert row["total"] == 0, table

        # All remaining ON DELETE SET NULL references must survive with
        # their referencing rows intact and their user reference cleared.
        role_fk_state = admin.execute(
            sql.SQL(
                """
                SELECT created_by, updated_by
                FROM {}.roles
                WHERE id = %s
                """
            ).format(sql.Identifier(schema)),
            (fk_role["id"],),
        ).fetchone()
        assert role_fk_state == {
            "created_by": None,
            "updated_by": None,
        }

        function_fk_creator = admin.execute(
            sql.SQL(
                """
                SELECT created_by
                FROM {}.user_functions
                WHERE id = %s
                """
            ).format(sql.Identifier(schema)),
            (fk_function["id"],),
        ).fetchone()
        assert function_fk_creator == {"created_by": None}

        node_fk_state = admin.execute(
            sql.SQL(
                """
                SELECT id, created_by
                FROM {}.infrastructure_nodes
                WHERE id = ANY(%s)
                ORDER BY id
                """
            ).format(sql.Identifier(schema)),
            ([node_a["id"], node_b["id"]],),
        ).fetchall()
        assert len(node_fk_state) == 2
        assert all(row["created_by"] is None for row in node_fk_state)

        relation_fk_state = admin.execute(
            sql.SQL(
                """
                SELECT created_by
                FROM {}.infrastructure_relations
                WHERE id = %s
                """
            ).format(sql.Identifier(schema)),
            (fk_relation["id"],),
        ).fetchone()
        assert relation_fk_state == {"created_by": None}

        # A referenced alert rule must be protected by its database FK.
        response = client.delete(
            f"/alerts/rules/{referenced_alert_rule_id}",
            base_url=BASE_URL,
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert response.status_code == 409, response.get_json()

        referenced_rule_state = admin.execute(
            sql.SQL(
                "SELECT count(*) AS total FROM {}.alert_rules "
                "WHERE rule_id = %s"
            ).format(sql.Identifier(schema)),
            (referenced_alert_rule_id,),
        ).fetchone()
        assert referenced_rule_state["total"] == 1

        failed_rule_audit = admin.execute(
            sql.SQL(
                """
                SELECT count(*) AS total
                FROM {}.audit_log
                WHERE actor_id = %s
                  AND action = 'alerts.rule.delete'
                  AND target = %s
                """
            ).format(sql.Identifier(schema)),
            (str(user["id"]), f"alert-rule:{referenced_alert_rule_id}"),
        ).fetchone()
        assert failed_rule_audit["total"] == 0

        # An unreferenced rule can be deleted by the restricted app.
        response = client.delete(
            f"/alerts/rules/{delete_alert_rule_id}",
            base_url=BASE_URL,
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert response.status_code == 200, response.get_json()

        deleted_rule_state = admin.execute(
            sql.SQL(
                "SELECT count(*) AS total FROM {}.alert_rules "
                "WHERE rule_id = %s"
            ).format(sql.Identifier(schema)),
            (delete_alert_rule_id,),
        ).fetchone()
        assert deleted_rule_state["total"] == 0

        rule_delete_audit = admin.execute(
            sql.SQL(
                """
                SELECT result
                FROM {}.audit_log
                WHERE actor_id = %s
                  AND action = 'alerts.rule.delete'
                  AND target = %s
                """
            ).format(sql.Identifier(schema)),
            (str(user["id"]), f"alert-rule:{delete_alert_rule_id}"),
        ).fetchall()
        assert [row["result"] for row in rule_delete_audit] == ["success"]

        # Direct relation deletion must preserve both endpoint nodes.
        response = client.delete(
            f"/api/infrastructure/relations/{direct_relation_id}",
            base_url=BASE_URL,
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert response.status_code == 200, response.get_json()
        assert response.get_json() == {"status": "saved"}

        direct_relation_state = admin.execute(
            sql.SQL(
                "SELECT count(*) AS total FROM {}.infrastructure_relations "
                "WHERE id = %s"
            ).format(sql.Identifier(schema)),
            (direct_relation_id,),
        ).fetchone()
        assert direct_relation_state["total"] == 0

        direct_node_state = admin.execute(
            sql.SQL(
                "SELECT count(*) AS total FROM {}.infrastructure_nodes "
                "WHERE id = ANY(%s)"
            ).format(sql.Identifier(schema)),
            ([direct_source_node_id, direct_target_node_id],),
        ).fetchone()
        assert direct_node_state["total"] == 2

        relation_delete_audit = admin.execute(
            sql.SQL(
                """
                SELECT result
                FROM {}.audit_log
                WHERE actor_id = %s
                  AND action = 'infrastructure.relation.delete'
                  AND target = %s
                """
            ).format(sql.Identifier(schema)),
            (str(user["id"]), str(direct_relation_id)),
        ).fetchall()
        assert [row["result"] for row in relation_delete_audit] == ["success"]

        # Node deletion must cascade without direct DELETE on relations.
        admin.execute(
            sql.SQL(
                "REVOKE DELETE ON TABLE {}.infrastructure_relations FROM {}"
            ).format(
                sql.Identifier(schema),
                sql.Identifier(privileges),
            )
        )

        try:
            relation_delete_privilege = admin.execute(
                """
                SELECT has_table_privilege(
                    %s, %s, 'DELETE'
                ) AS allowed
                """,
                (login, f"{schema}.infrastructure_relations"),
            ).fetchone()
            assert relation_delete_privilege["allowed"] is False

            response = client.delete(
                f"/api/infrastructure/nodes/{cascade_source_node_id}",
                base_url=BASE_URL,
                headers={"X-CSRF-Token": _csrf_token(client)},
            )
            assert response.status_code == 200, response.get_json()
            assert response.get_json() == {"status": "saved"}

            deleted_node_state = admin.execute(
                sql.SQL(
                    "SELECT count(*) AS total FROM {}.infrastructure_nodes "
                    "WHERE id = %s"
                ).format(sql.Identifier(schema)),
                (cascade_source_node_id,),
            ).fetchone()
            assert deleted_node_state["total"] == 0

            retained_node_state = admin.execute(
                sql.SQL(
                    "SELECT count(*) AS total FROM {}.infrastructure_nodes "
                    "WHERE id = %s"
                ).format(sql.Identifier(schema)),
                (cascade_target_node_id,),
            ).fetchone()
            assert retained_node_state["total"] == 1

            cascade_relation_state = admin.execute(
                sql.SQL(
                    "SELECT count(*) AS total FROM {}.infrastructure_relations "
                    "WHERE id = %s"
                ).format(sql.Identifier(schema)),
                (cascade_relation_id,),
            ).fetchone()
            assert cascade_relation_state["total"] == 0

        finally:
            # Restore the original fixture ACL before the exact ACL audit.
            admin.execute(
                sql.SQL(
                    "GRANT DELETE ON TABLE {}.infrastructure_relations TO {}"
                ).format(
                    sql.Identifier(schema),
                    sql.Identifier(privileges),
                )
            )

        node_delete_audit = admin.execute(
            sql.SQL(
                """
                SELECT result
                FROM {}.audit_log
                WHERE actor_id = %s
                  AND action = 'infrastructure.node.delete'
                  AND target = %s
                """
            ).format(sql.Identifier(schema)),
            (str(user["id"]), str(cascade_source_node_id)),
        ).fetchall()
        assert [row["result"] for row in node_delete_audit] == ["success"]

        reference_assignment = admin.execute(
            sql.SQL(
                """
                SELECT assigned_by
                FROM {}.user_roles
                WHERE user_id = %s
                """
            ).format(sql.Identifier(schema)),
            (reference_user["id"],),
        ).fetchone()
        assert reference_assignment == {"assigned_by": None}

        reference_override = admin.execute(
            sql.SQL(
                """
                SELECT changed_by
                FROM {}.user_permission_overrides
                WHERE user_id = %s AND permission = 'software.view'
                """
            ).format(sql.Identifier(schema)),
            (reference_user["id"],),
        ).fetchone()
        assert reference_override == {"changed_by": None}

        dashboard_remaining = admin.execute(
            sql.SQL(
                """
                SELECT count(*) AS total
                FROM {}.user_dashboard_settings
                WHERE user_id = %s
                """
            ).format(sql.Identifier(schema)),
            (target_id,),
        ).fetchone()
        assert dashboard_remaining["total"] == 0

        # Restore normal RBAC mutation grants after the FK cascade test.
        for table in ("user_roles", "user_permission_overrides"):
            admin.execute(
                sql.SQL(
                    "GRANT DELETE ON TABLE {}.{} TO {}"
                ).format(
                    sql.Identifier(schema),
                    sql.Identifier(table),
                    sql.Identifier(privileges),
                )
            )

        # Exercise client administration and the agent API through Flask.
        # The user-facing routes use the restricted application DB role;
        # the agent routes use a real bearer token issued by the API.
        agent_hostname = f"app-lp-agent-{suffix}"
        agent_ip = "198.51.100.223"

        created_client = client.post(
            "/api/clients",
            base_url=BASE_URL,
            json={
                "hostname": agent_hostname,
                "ip": agent_ip,
                "os": "Debian GNU/Linux",
                "kernel": "6.1.0",
                "architecture": "x86_64",
                "agent_version": "1.0.0",
            },
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert created_client.status_code == 201, created_client.get_json()

        created_client_data = created_client.get_json()
        client_id = created_client_data["client"]["id"]
        original_client_token = created_client_data["token"]
        assert isinstance(original_client_token, str)
        assert original_client_token

        stored_client = admin.execute(
            sql.SQL(
                """
                SELECT
                    id, hostname, ip, client_token_hash,
                    token_created_at, enabled
                FROM {}.clients
                WHERE id = %s
                """
            ).format(sql.Identifier(schema)),
            (client_id,),
        ).fetchone()
        assert stored_client is not None
        assert stored_client["hostname"] == agent_hostname
        assert stored_client["ip"] == agent_ip
        assert stored_client["client_token_hash"]
        assert stored_client["client_token_hash"] != original_client_token
        assert stored_client["token_created_at"] is not None
        assert stored_client["enabled"] is True

        original_agent_headers = {
            "Authorization": f"Bearer {original_client_token}",
        }

        agent_identity = client.get(
            "/api/client/me",
            base_url=BASE_URL,
            headers=original_agent_headers,
        )
        assert agent_identity.status_code == 200, agent_identity.get_json()
        assert agent_identity.get_json()["id"] == client_id
        assert agent_identity.get_json()["hostname"] == agent_hostname

        agent_report = {
            "hostname": agent_hostname,
            "ip": agent_ip,
            "os": "Debian GNU/Linux",
            "kernel": "6.1.0",
            "architecture": "x86_64",
            "agent_version": "1.0.1",
            "idle": False,
            "idle_seconds": 0,
            "idle_threshold_seconds": 300,
            "idle_source": "integration-test",
            "idle_supported": True,
            "updates": [
                {
                    "package": "curl",
                    "installed_version": "8.0",
                    "available_version": "8.1",
                },
            ],
            "packages": {
                "curl": "8.0",
                "bash": "5.2",
            },
        }

        reported = client.post(
            "/api/report",
            base_url=BASE_URL,
            json=agent_report,
            headers=original_agent_headers,
        )
        assert reported.status_code == 200, reported.get_json()
        assert reported.get_json() == {"status": "received"}

        client_list = client.get(
            "/api/clients",
            base_url=BASE_URL,
        )
        assert client_list.status_code == 200, client_list.get_json()
        listed_client = next(
            item for item in client_list.get_json()
            if item["id"] == client_id
        )
        assert listed_client["hostname"] == agent_hostname
        assert listed_client["package_count"] == 2
        assert listed_client["update_count"] == 1

        client_details = client.get(
            f"/api/clients/{client_id}",
            base_url=BASE_URL,
        )
        assert client_details.status_code == 200, client_details.get_json()
        assert client_details.get_json()["hostname"] == agent_hostname

        client_updates = client.get(
            f"/api/clients/{client_id}/updates",
            base_url=BASE_URL,
        )
        assert client_updates.status_code == 200, client_updates.get_json()
        assert [
            row["package"] for row in client_updates.get_json()
        ] == ["curl"]

        client_packages = client.get(
            f"/api/clients/{client_id}/packages",
            base_url=BASE_URL,
        )
        assert client_packages.status_code == 200, client_packages.get_json()
        assert {
            row["package"] for row in client_packages.get_json()
        } == {"bash", "curl"}

        # Exercise real telemetry ingestion and all user-facing read paths
        # while the agent token is still valid.
        def telemetry_system_snapshot(service_state, ssh_failed, rx_bytes):
            snapshot_time = datetime.now(timezone.utc).isoformat()
            return {
                "load_average": [0.5, 0.4, 0.3],
                "uptime_seconds": 12345,
                "os": "Debian GNU/Linux 13",
                "kernel": "6.12.0",
                "disk": {
                    "total_bytes": 10000,
                    "used_bytes": 4000,
                    "free_bytes": 6000,
                },
                "interfaces": [{
                    "name": "eth0",
                    "state": "up",
                    "rx_bytes": rx_bytes,
                    "tx_bytes": rx_bytes // 2,
                    "rx_errors": 0,
                    "tx_errors": 0,
                    "rx_dropped": 0,
                    "tx_dropped": 0,
                }],
                "dns_servers": ["192.0.2.53"],
                "gateway": "192.0.2.1",
                "gateway_reachable": True,
                "dns_reachable": True,
                "internet_reachable": True,
                "temperatures": [{"name": "CPU", "celsius": 42.5}],
                "fans": [{"name": "fan1", "rpm": 1200}],
                "services": {
                    "available": True,
                    "items": [{
                        "name": "ssh.service",
                        "state": service_state,
                        "substate": service_state,
                        "restarts": 1,
                        "runtime_seconds": 3600,
                    }],
                },
                "containers": {
                    "available": True,
                    "items": [{
                        "runtime": "docker",
                        "name": "lums",
                        "state": "up",
                    }],
                },
                "security_events": {
                    "ssh_available": True,
                    "ssh_failed_24h": ssh_failed,
                    "ssh_last_failed_at": snapshot_time,
                    "journal_available": True,
                    "journal_errors_1h": 1,
                    "journal_warnings_1h": 3,
                    "login_history_available": True,
                    "login_events": [{
                        "timestamp": snapshot_time,
                        "action": "login",
                    }],
                    "boot_history_available": True,
                    "boot_history": [{
                        "started_at": snapshot_time,
                        "ended_at": snapshot_time,
                    }],
                },
            }

        first_telemetry_payload = {
            "cpu_percent": 35.5,
            "memory_percent": 61.0,
            "memory_total_bytes": 8_000_000_000,
            "memory_available_bytes": 3_120_000_000,
            "network_rx_bytes": 10000,
            "network_tx_bytes": 5000,
            "system": telemetry_system_snapshot(
                "failed", 2, 10000
            ),
        }

        first_telemetry = client.post(
            "/api/telemetry",
            base_url=BASE_URL,
            json=first_telemetry_payload,
            headers=original_agent_headers,
        )
        assert first_telemetry.status_code == 200, (
            first_telemetry.get_json()
        )
        assert first_telemetry.get_json() == {"status": "received"}

        second_telemetry_payload = {
            "cpu_percent": 45.5,
            "memory_percent": 66.0,
            "memory_total_bytes": 8_000_000_000,
            "memory_available_bytes": 2_720_000_000,
            "network_rx_bytes": 20000,
            "network_tx_bytes": 10000,
            "system": telemetry_system_snapshot(
                "active", 3, 20000
            ),
        }

        second_telemetry = client.post(
            "/api/telemetry",
            base_url=BASE_URL,
            json=second_telemetry_payload,
            headers=original_agent_headers,
        )
        assert second_telemetry.status_code == 200, (
            second_telemetry.get_json()
        )
        assert second_telemetry.get_json() == {"status": "received"}

        # Read the actual telemetry history through the authenticated UI API.
        telemetry_history = client.get(
            f"/api/clients/{client_id}/telemetry?hours=24",
            base_url=BASE_URL,
        )
        assert telemetry_history.status_code == 200, (
            telemetry_history.get_json()
        )
        history_data = telemetry_history.get_json()
        assert history_data["client_id"] == client_id
        assert history_data["hostname"] == agent_hostname
        assert len(history_data["samples"]) == 2
        assert [
            row["cpu_percent"] for row in history_data["samples"]
        ] == [35.5, 45.5]
        assert all(
            row["disk_percent"] == 40.0
            for row in history_data["samples"]
        )

        # The dashboard GET must return defaults without requiring a row.
        dashboard_default = client.get(
            "/api/telemetry/dashboard-settings",
            base_url=BASE_URL,
        )
        assert dashboard_default.status_code == 200, (
            dashboard_default.get_json()
        )
        assert dashboard_default.get_json() == {
            "layout": [
                {"id": "summary", "width": 12, "visible": True},
                {"id": "clients", "width": 4, "visible": True},
                {"id": "history", "width": 8, "visible": True},
                {"id": "events", "width": 12, "visible": True},
                {"id": "backup", "width": 6, "visible": True},
            ],
            "thresholds": {
                "cpu": 90,
                "memory": 90,
                "disk": 90,
            },
            "integrations": {
                "wazuh": False,
                "suricata": False,
            },
        }

        custom_dashboard_settings = {
            "layout": [
                {"id": "summary", "width": 12, "visible": True},
                {"id": "clients", "width": 6, "visible": True},
                {"id": "history", "width": 8, "visible": True},
                {"id": "events", "width": 12, "visible": True},
                {"id": "backup", "width": 4, "visible": False},
            ],
            "thresholds": {
                "cpu": 85,
                "memory": 88,
                "disk": 92,
            },
            "integrations": {
                "wazuh": True,
                "suricata": False,
            },
        }

        dashboard_saved = client.put(
            "/api/telemetry/dashboard-settings",
            base_url=BASE_URL,
            json=custom_dashboard_settings,
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert dashboard_saved.status_code == 200, (
            dashboard_saved.get_json()
        )
        assert dashboard_saved.get_json() == {"status": "saved"}

        dashboard_reloaded = client.get(
            "/api/telemetry/dashboard-settings",
            base_url=BASE_URL,
        )
        assert dashboard_reloaded.status_code == 200, (
            dashboard_reloaded.get_json()
        )
        assert dashboard_reloaded.get_json() == custom_dashboard_settings

        # Read persisted and derived system events through the UI endpoint.
        telemetry_events = client.get(
            f"/api/clients/{client_id}/telemetry/events?hours=24",
            base_url=BASE_URL,
        )
        assert telemetry_events.status_code == 200, (
            telemetry_events.get_json()
        )
        event_data = telemetry_events.get_json()
        assert event_data["client_id"] == client_id
        assert event_data["hostname"] == agent_hostname
        event_kinds = {
            event["kind"] for event in event_data["events"]
        }
        assert {
            "service_failed",
            "service_recovered",
            "ssh_failure",
        } <= event_kinds

        # Verify JSON and CSV exports through their actual HTTP routes.
        telemetry_json_export = client.get(
            f"/api/clients/{client_id}/telemetry/export"
            "?hours=24&format=json",
            base_url=BASE_URL,
        )
        assert telemetry_json_export.status_code == 200, (
            telemetry_json_export.get_json()
        )
        assert len(telemetry_json_export.get_json()["samples"]) == 2

        telemetry_csv_export = client.get(
            f"/api/clients/{client_id}/telemetry/export"
            "?hours=24&format=csv",
            base_url=BASE_URL,
        )
        assert telemetry_csv_export.status_code == 200
        assert telemetry_csv_export.mimetype == "text/csv"
        assert "cpu_percent" in telemetry_csv_export.get_data(as_text=True)

        events_csv_export = client.get(
            f"/api/clients/{client_id}/telemetry/events"
            "?hours=24&format=csv",
            base_url=BASE_URL,
        )
        assert events_csv_export.status_code == 200
        assert events_csv_export.mimetype == "text/csv"
        assert "service_failed" in events_csv_export.get_data(
            as_text=True
        )

        telemetry_overview = client.get(
            "/api/telemetry/overview",
            base_url=BASE_URL,
        )
        assert telemetry_overview.status_code == 200, (
            telemetry_overview.get_json()
        )
        overview_client = next(
            item for item in telemetry_overview.get_json()["clients"]
            if item["client_id"] == client_id
        )
        assert overview_client["hostname"] == agent_hostname
        assert overview_client["latest"]["cpu_percent"] == 45.5
        assert overview_client["system"]["services"]["items"][0][
            "state"
        ] == "active"

        # Verify the persisted rows independently via the bootstrap
        # connection. The application role itself has no elevated access.
        persisted_telemetry = admin.execute(
            sql.SQL(
                """
                SELECT
                    cpu_percent, memory_percent,
                    memory_total_bytes, memory_available_bytes,
                    network_rx_bytes, network_tx_bytes, disk_percent
                FROM {}.client_telemetry
                WHERE client_id = %s
                ORDER BY recorded_at ASC
                """
            ).format(sql.Identifier(schema)),
            (client_id,),
        ).fetchall()
        assert len(persisted_telemetry) == 2
        assert [
            row["cpu_percent"] for row in persisted_telemetry
        ] == [35.5, 45.5]
        assert all(
            row["disk_percent"] == 40.0
            for row in persisted_telemetry
        )

        persisted_system = admin.execute(
            sql.SQL(
                """
                SELECT recorded_at, payload_json
                FROM {}.client_system_status
                WHERE client_id = %s
                """
            ).format(sql.Identifier(schema)),
            (client_id,),
        ).fetchone()
        assert persisted_system is not None
        assert persisted_system["payload_json"]["services"]["items"][0][
            "state"
        ] == "active"
        assert persisted_system["payload_json"]["interfaces"][0][
            "rx_bytes"
        ] == 20000

        persisted_events = admin.execute(
            sql.SQL(
                """
                SELECT event_type, metric, value
                FROM {}.client_telemetry_events
                WHERE client_id = %s
                ORDER BY recorded_at ASC, event_type ASC
                """
            ).format(sql.Identifier(schema)),
            (client_id,),
        ).fetchall()
        assert len(persisted_events) == 4
        assert {
            (row["event_type"], row["metric"])
            for row in persisted_events
        } == {
            ("service_failed", "ssh.service"),
            ("service_recovered", "ssh.service"),
            ("ssh_failure", "ssh"),
        }
        assert [
            row["value"] for row in persisted_events
            if row["event_type"] == "ssh_failure"
        ] == [2, 3]

        persisted_dashboard = admin.execute(
            sql.SQL(
                """
                SELECT settings_json
                FROM {}.user_dashboard_settings
                WHERE user_id = %s
                """
            ).format(sql.Identifier(schema)),
            (user["id"],),
        ).fetchone()
        assert persisted_dashboard is not None
        assert persisted_dashboard["settings_json"] == (
            custom_dashboard_settings
        )

        # Prove that the real ingestion route removes expired telemetry
        # and event rows using the restricted application role.
        retention_recorded_at = (
            datetime.now(timezone.utc) - timedelta(days=8)
        )

        old_telemetry_row = admin.execute(
            sql.SQL(
                """
                INSERT INTO {}.client_telemetry (
                    client_id, recorded_at, cpu_percent, memory_percent,
                    memory_total_bytes, memory_available_bytes,
                    network_rx_bytes, network_tx_bytes, disk_percent
                )
                VALUES (%s, %s, 1.0, 2.0, 1000, 980, NULL, NULL, NULL)
                RETURNING id
                """
            ).format(sql.Identifier(schema)),
            (client_id, retention_recorded_at),
        ).fetchone()

        old_event_row = admin.execute(
            sql.SQL(
                """
                INSERT INTO {}.client_telemetry_events (
                    client_id, recorded_at, event_type, metric, value
                )
                VALUES (%s, %s, 'retention_probe', 'retention', 1.0)
                RETURNING id
                """
            ).format(sql.Identifier(schema)),
            (client_id, retention_recorded_at),
        ).fetchone()

        assert old_telemetry_row is not None
        assert old_event_row is not None

        old_telemetry_seed = admin.execute(
            sql.SQL(
                """
                SELECT count(*) AS total
                FROM {}.client_telemetry
                WHERE id = %s
                """
            ).format(sql.Identifier(schema)),
            (old_telemetry_row["id"],),
        ).fetchone()
        old_event_seed = admin.execute(
            sql.SQL(
                """
                SELECT count(*) AS total
                FROM {}.client_telemetry_events
                WHERE id = %s
                """
            ).format(sql.Identifier(schema)),
            (old_event_row["id"],),
        ).fetchone()
        assert old_telemetry_seed["total"] == 1
        assert old_event_seed["total"] == 1

        retention_ingestion = client.post(
            "/api/telemetry",
            base_url=BASE_URL,
            json={
                "cpu_percent": 12.5,
                "memory_percent": 45.0,
                "memory_total_bytes": 8_000_000_000,
                "memory_available_bytes": 4_400_000_000,
            },
            headers=original_agent_headers,
        )
        assert retention_ingestion.status_code == 200, (
            retention_ingestion.get_json()
        )
        assert retention_ingestion.get_json() == {"status": "received"}

        # The old fixture rows must have been removed by the application role.
        old_telemetry_remaining = admin.execute(
            sql.SQL(
                """
                SELECT count(*) AS total
                FROM {}.client_telemetry
                WHERE id = %s
                """
            ).format(sql.Identifier(schema)),
            (old_telemetry_row["id"],),
        ).fetchone()
        old_event_remaining = admin.execute(
            sql.SQL(
                """
                SELECT count(*) AS total
                FROM {}.client_telemetry_events
                WHERE id = %s
                """
            ).format(sql.Identifier(schema)),
            (old_event_row["id"],),
        ).fetchone()
        assert old_telemetry_remaining["total"] == 0
        assert old_event_remaining["total"] == 0

        retention_cutoff = (
            datetime.now(timezone.utc) - timedelta(days=7)
        )
        stale_telemetry = admin.execute(
            sql.SQL(
                """
                SELECT count(*) AS total
                FROM {}.client_telemetry
                WHERE client_id = %s AND recorded_at < %s
                """
            ).format(sql.Identifier(schema)),
            (client_id, retention_cutoff),
        ).fetchone()
        stale_events = admin.execute(
            sql.SQL(
                """
                SELECT count(*) AS total
                FROM {}.client_telemetry_events
                WHERE client_id = %s AND recorded_at < %s
                """
            ).format(sql.Identifier(schema)),
            (client_id, retention_cutoff),
        ).fetchone()
        assert stale_telemetry["total"] == 0
        assert stale_events["total"] == 0

        # Recent records and generated events must remain untouched.
        retained_telemetry = admin.execute(
            sql.SQL(
                """
                SELECT count(*) AS total
                FROM {}.client_telemetry
                WHERE client_id = %s AND recorded_at >= %s
                """
            ).format(sql.Identifier(schema)),
            (client_id, retention_cutoff),
        ).fetchone()
        retained_events = admin.execute(
            sql.SQL(
                """
                SELECT count(*) AS total
                FROM {}.client_telemetry_events
                WHERE client_id = %s AND recorded_at >= %s
                """
            ).format(sql.Identifier(schema)),
            (client_id, retention_cutoff),
        ).fetchone()
        assert retained_telemetry["total"] == 3
        assert retained_events["total"] == 4

        # Rotate the token and prove the previous token is no longer valid.
        rotated_client = client.post(
            f"/api/clients/{client_id}/token/rotate",
            base_url=BASE_URL,
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert rotated_client.status_code == 200, rotated_client.get_json()

        new_client_token = rotated_client.get_json()["token"]
        assert new_client_token != original_client_token

        old_token_identity = client.get(
            "/api/client/me",
            base_url=BASE_URL,
            headers=original_agent_headers,
        )
        assert old_token_identity.status_code == 401

        new_agent_headers = {
            "Authorization": f"Bearer {new_client_token}",
        }
        new_token_identity = client.get(
            "/api/client/me",
            base_url=BASE_URL,
            headers=new_agent_headers,
        )
        assert new_token_identity.status_code == 200

        rotated_state = admin.execute(
            sql.SQL(
                """
                SELECT client_token_hash, token_created_at, token_revoked_at
                FROM {}.clients
                WHERE id = %s
                """
            ).format(sql.Identifier(schema)),
            (client_id,),
        ).fetchone()
        assert rotated_state["client_token_hash"] != stored_client[
            "client_token_hash"
        ]
        assert rotated_state["client_token_hash"] != new_client_token
        assert rotated_state["token_created_at"] is not None
        assert rotated_state["token_revoked_at"] is None

        # Disable the client. This deletes its report-owned package rows,
        # but deliberately does not delete the client itself.
        disabled_client = client.delete(
            f"/api/clients/{client_id}",
            base_url=BASE_URL,
            headers={"X-CSRF-Token": _csrf_token(client)},
        )
        assert disabled_client.status_code == 200, disabled_client.get_json()
        assert disabled_client.get_json()["status"] == "disabled"

        disabled_state = admin.execute(
            sql.SQL(
                """
                SELECT enabled, token_revoked_at
                FROM {}.clients
                WHERE id = %s
                """
            ).format(sql.Identifier(schema)),
            (client_id,),
        ).fetchone()
        assert disabled_state["enabled"] is False
        assert disabled_state["token_revoked_at"] is not None

        for table in ("available_updates", "installed_packages"):
            remaining_rows = admin.execute(
                sql.SQL(
                    "SELECT count(*) AS total FROM {}.{} WHERE client_id = %s"
                ).format(
                    sql.Identifier(schema),
                    sql.Identifier(table),
                ),
                (client_id,),
            ).fetchone()
            assert remaining_rows["total"] == 0, table

        disabled_identity = client.get(
            "/api/client/me",
            base_url=BASE_URL,
            headers=new_agent_headers,
        )
        assert disabled_identity.status_code == 401

        # The application role can update only explicitly granted client
        # columns and cannot physically delete clients.
        client_privileges = connection_factory()
        try:
            client_privilege_state = client_privileges.execute(
                """
                SELECT
                    has_column_privilege(
                        current_user, %s, 'hostname', 'INSERT'
                    ) AS client_hostname_insert,
                    has_column_privilege(
                        current_user, %s, 'enabled', 'UPDATE'
                    ) AS client_enabled_update,
                    has_column_privilege(
                        current_user, %s, 'id', 'UPDATE'
                    ) AS client_id_update,
                    has_table_privilege(
                        current_user, %s, 'DELETE'
                    ) AS clients_delete,
                    has_table_privilege(
                        current_user, %s, 'DELETE'
                    ) AS updates_delete,
                    has_table_privilege(
                        current_user, %s, 'DELETE'
                    ) AS packages_delete
                """,
                (
                    f"{schema}.clients",
                    f"{schema}.clients",
                    f"{schema}.clients",
                    f"{schema}.clients",
                    f"{schema}.available_updates",
                    f"{schema}.installed_packages",
                ),
            ).fetchone()

            assert client_privilege_state == {
                "client_hostname_insert": True,
                "client_enabled_update": True,
                "client_id_update": False,
                "clients_delete": False,
                "updates_delete": True,
                "packages_delete": True,
            }

            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                client_privileges.execute(
                    sql.SQL(
                        "DELETE FROM {}.clients WHERE id = %s"
                    ).format(sql.Identifier(schema)),
                    (client_id,),
                )
        finally:
            client_privileges.close()

        persisted_user = admin.execute(
            sql.SQL(
                """
                SELECT language, password_hash
                FROM {}.users
                WHERE id = %s
                """
            ).format(sql.Identifier(schema)),
            (user["id"],),
        ).fetchone()

        assert persisted_user["language"] == "en-US"
        assert not password_needs_rehash(persisted_user["password_hash"])

        remaining = admin.execute(
            sql.SQL(
                """
                SELECT count(*) AS count
                FROM {}.login_rate_limits
                WHERE username = %s
                """
            ).format(sql.Identifier(schema)),
            (username,),
        ).fetchone()
        assert remaining["count"] == 0

        audit = admin.execute(
            sql.SQL(
                """
                SELECT result
                FROM {}.audit_log
                WHERE actor_id = %s AND action = 'login'
                ORDER BY id
                """
            ).format(sql.Identifier(schema)),
            (str(user["id"]),),
        ).fetchall()
        assert [row["result"] for row in audit] == [
            "failure", "failure", "success"
        ]

        # Verify effective and forbidden privileges.
        connection = connection_factory()
        try:
            identity = connection.execute(
                "SELECT current_user, session_user"
            ).fetchone()
            assert identity == {
                "current_user": login,
                "session_user": login,
            }

            state = connection.execute(
                """
                SELECT
                    has_schema_privilege(
                        current_user, %s, 'USAGE'
                    ) AS schema_usage,
                    has_schema_privilege(
                        current_user, %s, 'CREATE'
                    ) AS schema_create,
                    has_table_privilege(
                        current_user, %s, 'DELETE'
                    ) AS users_delete,
                    has_table_privilege(
                        current_user, %s, 'UPDATE'
                    ) AS roles_update,
                    has_table_privilege(
                        current_user, %s, 'DELETE'
                    ) AS roles_delete,
                    has_table_privilege(
                        current_user, %s, 'INSERT'
                    ) AS role_permissions_insert,
                    has_column_privilege(
                        current_user, %s, 'language', 'UPDATE'
                    ) AS language_update,
                    has_column_privilege(
                        current_user, %s, 'enabled', 'UPDATE'
                    ) AS enabled_update
                """,
                (
                    schema, schema,
                    f"{schema}.users",
                    f"{schema}.roles",
                    f"{schema}.roles",
                    f"{schema}.role_permissions",
                    f"{schema}.users",
                    f"{schema}.users",
                ),
            ).fetchone()

            assert state == {
                "schema_usage": True,
                "schema_create": False,
                "users_delete": True,
                "roles_update": False,
                "roles_delete": False,
                "role_permissions_insert": False,
                "language_update": True,
                "enabled_update": False,
            }

            # Identity inserts above succeeded without explicit sequence
            # grants. Confirm that no sequence USAGE privilege was granted.
            for table in (
                "login_rate_limits",
                "audit_log",
                "clients",
                "client_telemetry",
                "client_telemetry_events",
            ):
                sequence = admin.execute(
                    "SELECT pg_get_serial_sequence(%s, 'id') AS name",
                    (f"{schema}.{table}",),
                ).fetchone()["name"]
                assert sequence is not None

                allowed = connection.execute(
                    """
                    SELECT has_sequence_privilege(
                        current_user, %s, 'USAGE'
                    ) AS allowed
                    """,
                    (sequence,),
                ).fetchone()["allowed"]
                assert allowed is False

            # Audit every effective table-level and column-level privilege
            # in the isolated schema against the explicit grant declaration.
            expected_column_privileges = {
                (table, privilege, column)
                for table, privilege, columns in grants
                for column in columns
            }
            actual_column_rows = connection.execute(
                """
                SELECT
                    c.relname AS table_name,
                    a.attname AS column_name,
                    requested.privilege_type
                FROM pg_catalog.pg_class AS c
                JOIN pg_catalog.pg_namespace AS n
                    ON n.oid = c.relnamespace
                JOIN pg_catalog.pg_attribute AS a
                    ON a.attrelid = c.oid
                CROSS JOIN (
                    VALUES ('SELECT'), ('INSERT'), ('UPDATE'),
                           ('REFERENCES')
                ) AS requested(privilege_type)
                WHERE n.nspname = %s
                  AND c.relkind IN ('r', 'p')
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                  AND has_column_privilege(
                      current_user,
                      c.oid,
                      a.attnum,
                      requested.privilege_type
                  )
                ORDER BY c.relname, a.attname,
                         requested.privilege_type
                """,
                (schema,),
            ).fetchall()

            actual_column_privileges = {
                (
                    row["table_name"],
                    row["privilege_type"],
                    row["column_name"],
                )
                for row in actual_column_rows
            }

            assert actual_column_privileges == expected_column_privileges, (
                "Unexpected or missing column privileges: "
                f"extra={sorted(actual_column_privileges - expected_column_privileges)}, "
                f"missing={sorted(expected_column_privileges - actual_column_privileges)}"
            )

            expected_table_privileges = {
                (table, "DELETE")
                for table in (
                    "login_rate_limits",
                    "users",
                    "user_roles",
                    "user_permission_overrides",
                    "user_functions",
                    "available_updates",
                    "installed_packages",
                    "client_telemetry",
                    "client_telemetry_events",
                    "alert_rules",
                    "infrastructure_nodes",
                    "infrastructure_relations",
                )
            }

            actual_table_rows = connection.execute(
                """
                SELECT
                    c.relname AS table_name,
                    requested.privilege_type
                FROM pg_catalog.pg_class AS c
                JOIN pg_catalog.pg_namespace AS n
                    ON n.oid = c.relnamespace
                CROSS JOIN (
                    VALUES ('SELECT'), ('INSERT'), ('UPDATE'),
                           ('DELETE'), ('TRUNCATE'), ('REFERENCES'),
                           ('TRIGGER')
                ) AS requested(privilege_type)
                WHERE n.nspname = %s
                  AND c.relkind IN ('r', 'p')
                  AND has_table_privilege(
                      current_user,
                      c.oid,
                      requested.privilege_type
                  )
                ORDER BY c.relname, requested.privilege_type
                """,
                (schema,),
            ).fetchall()

            actual_table_privileges = {
                (row["table_name"], row["privilege_type"])
                for row in actual_table_rows
            }

            assert actual_table_privileges == expected_table_privileges, (
                "Unexpected or missing table privileges: "
                f"extra={sorted(actual_table_privileges - expected_table_privileges)}, "
                f"missing={sorted(expected_table_privileges - actual_table_privileges)}"
            )

            actual_sequence_rows = connection.execute(
                """
                SELECT
                    c.oid,
                    c.relname AS sequence_name,
                    requested.privilege_type
                FROM pg_catalog.pg_class AS c
                JOIN pg_catalog.pg_namespace AS n
                    ON n.oid = c.relnamespace
                CROSS JOIN (
                    VALUES ('USAGE'), ('SELECT'), ('UPDATE')
                ) AS requested(privilege_type)
                WHERE n.nspname = %s
                  AND c.relkind = 'S'
                  AND has_sequence_privilege(
                      current_user,
                      c.oid,
                      requested.privilege_type
                  )
                ORDER BY c.relname, requested.privilege_type
                """,
                (schema,),
            ).fetchall()

            assert actual_sequence_rows == [], (
                "Unexpected sequence privileges: "
                f"{actual_sequence_rows}"
            )

            forbidden_statements = (
                (
                    sql.SQL(
                        "UPDATE {}.roles SET name = name WHERE id = 1"
                    ).format(sql.Identifier(schema)),
                    None,
                ),
                (
                    sql.SQL(
                        "DELETE FROM {}.roles WHERE id = %s"
                    ).format(sql.Identifier(schema)),
                    (fk_role["id"],),
                ),
                (
                    sql.SQL(
                        """
                        INSERT INTO {}.role_permissions (role_id, permission)
                        VALUES (1, 'forbidden.test')
                        """
                    ).format(sql.Identifier(schema)),
                    None,
                ),
                (
                    sql.SQL(
                        "UPDATE {}.users SET enabled = FALSE WHERE id = %s"
                    ).format(sql.Identifier(schema)),
                    (user["id"],),
                ),
                (
                    sql.SQL(
                        "UPDATE {}.user_functions SET name = name WHERE id = 1"
                    ).format(sql.Identifier(schema)),
                    None,
                ),
                (
                    sql.SQL(
                        "DELETE FROM {}.clients WHERE id = %s"
                    ).format(sql.Identifier(schema)),
                    (client_id,),
                ),
                (
                    sql.SQL(
                        "CREATE TABLE {}.forbidden_app_table (id BIGINT)"
                    ).format(sql.Identifier(schema)),
                    None,
                ),
            )

            for statement, parameters in forbidden_statements:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    connection.execute(statement, parameters)

            for forbidden_role in (privileges, owner):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    connection.execute(
                        sql.SQL("SET ROLE {}").format(
                            sql.Identifier(forbidden_role)
                        )
                    )
        finally:
            connection.close()

    finally:
        cleanup = []

        for connection in app_connections:
            cleanup.append((
                "close app connection",
                lambda connection=connection: (
                    connection.close() if not connection.closed else None
                ),
            ))

        if setup is not None:
            cleanup.append(("close migration connection", setup.close))

        if membership_created:
            cleanup.append((
                "revoke membership",
                lambda: admin.execute(
                    sql.SQL("REVOKE {} FROM {}").format(
                        sql.Identifier(privileges), sql.Identifier(login)
                    )
                ),
            ))

        if login_created:
            cleanup.append((
                "drop login-owned privileges",
                lambda: admin.execute(
                    sql.SQL("DROP OWNED BY {}").format(sql.Identifier(login))
                ),
            ))

        if privileges_created:
            cleanup.append((
                "drop privilege-owned grants",
                lambda: admin.execute(
                    sql.SQL("DROP OWNED BY {}").format(
                        sql.Identifier(privileges)
                    )
                ),
            ))

        if schema_created:
            cleanup.append((
                "drop isolated schema",
                lambda: admin.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema)
                    )
                ),
            ))

        for created, role in (
            (login_created, login),
            (privileges_created, privileges),
            (owner_created, owner),
        ):
            if created:
                cleanup.append((
                    f"drop role {role}",
                    lambda role=role: admin.execute(
                        sql.SQL("DROP ROLE {}").format(sql.Identifier(role))
                    ),
                ))

        cleanup.append(("close bootstrap connection", admin.close))
        run_cleanup(*cleanup)
