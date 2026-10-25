import sqlite3

from server import security_migration as migration


def create_legacy_database(path):
    """Create a temporary database with the pre-security clients schema."""
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")

    connection.executescript("""
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT UNIQUE,
            ip TEXT,
            os TEXT,
            kernel TEXT,
            architecture TEXT,
            agent_version TEXT,
            last_seen TEXT NOT NULL,
            idle INTEGER NOT NULL DEFAULT 0,
            idle_seconds INTEGER NOT NULL DEFAULT 0,
            idle_threshold_seconds INTEGER NOT NULL DEFAULT 300,
            idle_source TEXT NOT NULL DEFAULT 'unknown',
            idle_supported INTEGER NOT NULL DEFAULT 0
        );

        INSERT INTO clients (
            hostname, ip, last_seen
        ) VALUES (
            'integration-client', '192.0.2.10',
            '2026-01-01T00:00:00+00:00'
        );
    """)

    connection.commit()
    connection.close()


def test_full_security_migration_is_repeatable(tmp_path, monkeypatch):
    db_path = tmp_path / "lums-integration.sqlite"
    create_legacy_database(db_path)

    # No interactive password prompt; only temporary test data is used.
    migration.run_migration(
        db_path=str(db_path),
        admin_username="integration-admin",
        skip_admin=True,
    )

    connection = sqlite3.connect(db_path)
    try:
        versions = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations"
            )
        }

        assert migration.MIGRATION_VERSION in versions
        assert migration.RBAC_MIGRATION_VERSION in versions
        assert migration.PERMISSIONS_MIGRATION_VERSION in versions
        assert migration.USER_NOTES_MIGRATION_VERSION in versions
        assert migration.BACKUP_PERMISSION_MIGRATION_VERSION in versions
        assert migration.USER_LANGUAGE_MIGRATION_VERSION in versions
        assert migration.USER_PROFILES_MIGRATION_VERSION in versions
        assert migration.TELEMETRY_MIGRATION_VERSION in versions
        assert (
            migration.TELEMETRY_RETENTION_INDEX_MIGRATION_VERSION
            in versions
        )

        telemetry_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(client_telemetry)"
            )
        }
        assert {
            "id",
            "client_id",
            "recorded_at",
            "cpu_percent",
            "memory_percent",
            "memory_total_bytes",
            "memory_available_bytes",
        } <= telemetry_columns

        telemetry_indexes = {
            row[1]
            for row in connection.execute(
                "PRAGMA index_list(client_telemetry)"
            )
        }
        assert "idx_client_telemetry_client_time" in telemetry_indexes
        assert "idx_client_telemetry_recorded_at" in telemetry_indexes

        query_plan = connection.execute(
            """
            EXPLAIN QUERY PLAN
            DELETE FROM client_telemetry
            WHERE recorded_at < ?
            """,
            ("2026-01-01T00:00:00+00:00",),
        ).fetchall()
        assert any(
            "idx_client_telemetry_recorded_at" in str(row)
            for row in query_plan
        ), query_plan

        # SQLite must enforce telemetry value bounds.
        invalid_rows = [
            (1, "2026-01-01T00:00:00+00:00", 101, 50, 1000, 500),
            (1, "2026-01-01T00:00:00+00:00", 50, -1, 1000, 500),
            (1, "2026-01-01T00:00:00+00:00", 50, 50, 1000, 1001),
        ]
        for values in invalid_rows:
            try:
                connection.execute(
                    """
                    INSERT INTO client_telemetry (
                        client_id, recorded_at, cpu_percent,
                        memory_percent, memory_total_bytes,
                        memory_available_bytes
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            except sqlite3.IntegrityError:
                connection.rollback()
            else:
                raise AssertionError(
                    f"Ungültiger Telemetrie-Datensatz wurde akzeptiert: {values}"
                )

        client = connection.execute(
            "SELECT hostname, ip FROM clients WHERE id = 1"
        ).fetchone()
        assert client == ("integration-client", "192.0.2.10")

        profile_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(users)")
        }
        assert {
            "first_name",
            "last_name",
            "department",
            "function_id",
        } <= profile_columns

        assert connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0] == 0
    finally:
        connection.close()

    # Running the migration again must not duplicate migration records
    # or fail because the columns and tables already exist.
    migration.run_migration(
        db_path=str(db_path),
        admin_username="integration-admin",
        skip_admin=True,
    )

    connection = sqlite3.connect(db_path)
    try:
        recorded_versions = [
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations"
            )
        ]
        assert len(recorded_versions) == len(set(recorded_versions))

        assert connection.execute(
            "SELECT COUNT(*) FROM clients WHERE hostname = ?",
            ("integration-client",),
        ).fetchone()[0] == 1
    finally:
        connection.close()


def test_full_migration_delegates_permission_to_one_active_admin(tmp_path):
    db_path = tmp_path / "lums-delegation.sqlite"
    create_legacy_database(db_path)

    connection = sqlite3.connect(db_path)
    connection.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'viewer'
        );

        INSERT INTO users (
            username, password_hash, created_at, enabled, role
        ) VALUES
            ('admin-a', 'test-hash-a', '2026-01-01', 1, 'administrator'),
            ('admin-b', 'test-hash-b', '2026-01-01', 1, 'administrator'),
            ('admin-disabled', 'test-hash-c', '2026-01-01', 0, 'administrator');
    """)
    connection.commit()
    connection.close()

    migration.run_migration(
        db_path=str(db_path),
        admin_username="unused-test-admin",
        skip_admin=True,
    )

    connection = sqlite3.connect(db_path)
    try:
        managers = connection.execute("""
            SELECT u.username
            FROM users AS u
            JOIN user_permissions AS p ON p.user_id = u.id
            WHERE u.enabled = 1
              AND p.permission = 'permissions.manage'
              AND EXISTS (
                  SELECT 1 FROM user_permissions AS p2
                  WHERE p2.user_id = u.id
                    AND p2.permission = 'users.manage'
              )
              AND EXISTS (
                  SELECT 1 FROM user_permissions AS p3
                  WHERE p3.user_id = u.id
                    AND p3.permission = 'clients.view'
              )
        """).fetchall()

        assert len(managers) == 1

        disabled_has_permission = connection.execute("""
            SELECT COUNT(*)
            FROM users AS u
            JOIN user_permissions AS p ON p.user_id = u.id
            WHERE u.username = 'admin-disabled'
              AND p.permission = 'permissions.manage'
        """).fetchone()[0]

        assert disabled_has_permission == 0

        versions = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations"
            )
        }
        assert migration.PERMISSION_DELEGATION_MIGRATION_VERSION in versions
    finally:
        connection.close()

    # A repeated migration must not delegate the permission to another admin.
    migration.run_migration(
        db_path=str(db_path),
        admin_username="unused-test-admin",
        skip_admin=True,
    )

    connection = sqlite3.connect(db_path)
    try:
        active_manager_count = connection.execute("""
            SELECT COUNT(DISTINCT u.id)
            FROM users AS u
            JOIN user_permissions AS p ON p.user_id = u.id
            WHERE u.enabled = 1
              AND p.permission = 'permissions.manage'
        """).fetchone()[0]

        assert active_manager_count == 1
    finally:
        connection.close()


def test_delegation_migration_stays_pending_without_eligible_user(tmp_path):
    db_path = tmp_path / "lums-no-eligible-admin.sqlite"
    create_legacy_database(db_path)

    connection = sqlite3.connect(db_path)
    connection.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'viewer'
        );

        INSERT INTO users (
            username, password_hash, created_at, enabled, role
        ) VALUES (
            'viewer-only', 'test-hash', '2026-01-01', 1, 'viewer'
        );
    """)
    connection.commit()
    connection.close()

    migration.run_migration(
        db_path=str(db_path),
        admin_username="unused-test-admin",
        skip_admin=True,
    )

    connection = sqlite3.connect(db_path)
    try:
        versions = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations"
            )
        }
        assert migration.PERMISSION_DELEGATION_MIGRATION_VERSION not in versions

        grants = connection.execute("""
            SELECT COUNT(*)
            FROM user_permissions
            WHERE permission = 'permissions.manage'
        """).fetchone()[0]
        assert grants == 0
    finally:
        connection.close()


def test_create_admin_rejects_existing_disabled_account(tmp_path):
    db_path = tmp_path / "disabled-admin.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1
        )
    """)
    connection.execute("""
        INSERT INTO users (username, password_hash, created_at, enabled)
        VALUES ('disabled-admin', 'test-hash', '2026-01-01', 0)
    """)
    connection.commit()

    try:
        import pytest

        with pytest.raises(RuntimeError):
            migration.create_admin(connection, "disabled-admin")
    finally:
        connection.close()
