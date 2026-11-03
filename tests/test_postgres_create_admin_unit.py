from __future__ import annotations

from contextlib import contextmanager

import pytest

from server import postgres_create_admin as bootstrap
from server.security import (
    ROLE_ADMINISTRATOR,
    ROLE_DEFAULT_PERMISSIONS,
)


class FakeCursor:
    def __init__(self, *, one=None, many=None):
        self._one = one
        self._many = list(many or [])

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._many)


class FakeConnection:
    closed = False

    def __init__(
        self,
        *,
        user_count=0,
        migration_rows=None,
        history_table="schema_migrations",
    ):
        self.events = []
        self.user_count = user_count
        self.history_table = history_table
        self.inserted_user = None

        if migration_rows is None:
            migration_rows = [
                {
                    "version": migration.version,
                    "checksum": migration.checksum,
                }
                for migration in bootstrap.MIGRATIONS
                if migration.version in bootstrap.BASELINE_MIGRATION_VERSIONS
            ]

        self.migration_rows = list(migration_rows)

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.events.append(("sql", normalized, params))

        if "to_regclass('schema_migrations')" in normalized:
            return FakeCursor(
                one={"table_name": self.history_table}
            )

        if normalized.startswith(
            "SELECT version, checksum FROM schema_migrations"
        ):
            return FakeCursor(many=self.migration_rows)

        if normalized.startswith(
            "SELECT COUNT(*) AS total FROM users"
        ):
            return FakeCursor(
                one={"total": self.user_count}
            )

        if normalized.startswith("INSERT INTO users"):
            self.inserted_user = params
            return FakeCursor(one={"id": 41})

        raise AssertionError(
            f"Unexpected SQL in bootstrap unit test: {normalized}"
        )


def patch_successful_dependencies(
    monkeypatch,
    connection,
    *,
    grant_result=True,
):
    @contextmanager
    def fake_transaction(conn):
        assert conn is connection
        conn.events.append("transaction.begin")

        try:
            yield conn
        except BaseException:
            conn.events.append("transaction.rollback")
            raise
        else:
            conn.events.append("transaction.commit")

    monkeypatch.setattr(
        bootstrap,
        "transaction",
        fake_transaction,
    )
    monkeypatch.setattr(
        bootstrap,
        "hash_password",
        lambda password: "argon2-test-hash",
    )
    monkeypatch.setattr(
        bootstrap,
        "acquire_rbac_write_lock",
        lambda conn: conn.events.append("rbac.lock"),
    )
    monkeypatch.setattr(
        bootstrap,
        "seed_system_roles",
        lambda conn, **kwargs: conn.events.append("rbac.seed"),
    )

    def fake_store(
        conn,
        user_id,
        role,
        permissions,
        *,
        actor_id=None,
        timestamp=None,
    ):
        conn.events.append("rbac.assign")
        assert user_id == 41
        assert role == ROLE_ADMINISTRATOR
        assert set(permissions) == set(
            ROLE_DEFAULT_PERMISSIONS[ROLE_ADMINISTRATOR]
        )
        assert actor_id is None
        assert timestamp

    monkeypatch.setattr(
        bootstrap,
        "store_user_permissions",
        fake_store,
    )

    def fake_grant(conn, user_id, *, timestamp=None):
        conn.events.append("rbac.initial_grant")
        assert user_id == 41
        assert timestamp
        return grant_result

    monkeypatch.setattr(
        bootstrap,
        "grant_initial_permission_manager",
        fake_grant,
    )

    def fake_audit(conn, **kwargs):
        conn.events.append("audit")
        assert kwargs["action"] == "admin_created"
        assert kwargs["target"] == "user:41"
        assert kwargs["result"] == "success"

    monkeypatch.setattr(
        bootstrap,
        "audit_log",
        fake_audit,
    )


def test_create_initial_admin_runs_all_steps_in_one_transaction(
    monkeypatch,
):
    connection = FakeConnection()
    patch_successful_dependencies(monkeypatch, connection)

    user_id = bootstrap.create_initial_admin(
        connection,
        "  first-admin  ",
        "a-long-test-password",
    )

    assert user_id == 41
    assert connection.inserted_user is not None
    assert connection.inserted_user[0] == "first-admin"
    assert connection.inserted_user[1] == "argon2-test-hash"
    assert connection.inserted_user[3] == ROLE_ADMINISTRATOR

    events = connection.events
    assert events[0:2] == [
        "transaction.begin",
        "rbac.lock",
    ]

    seed_index = events.index("rbac.seed")
    insert_index = next(
        index
        for index, event in enumerate(events)
        if (
            isinstance(event, tuple)
            and event[0] == "sql"
            and event[1].startswith("INSERT INTO users")
        )
    )

    assert seed_index < insert_index
    assert events[insert_index + 1:] == [
        "rbac.assign",
        "rbac.initial_grant",
        "audit",
        "transaction.commit",
    ]


def test_rbac_lock_is_acquired_before_first_sql_statement(monkeypatch):
    connection = FakeConnection()
    patch_successful_dependencies(monkeypatch, connection)

    bootstrap.create_initial_admin(
        connection,
        "first-admin",
        "a-long-test-password",
    )

    assert connection.events[0:2] == [
        "transaction.begin",
        "rbac.lock",
    ]
    assert isinstance(connection.events[2], tuple)
    assert connection.events[2][0] == "sql"


def test_existing_users_prevent_initial_admin_bootstrap(monkeypatch):
    connection = FakeConnection(user_count=1)
    patch_successful_dependencies(monkeypatch, connection)

    with pytest.raises(
        bootstrap.PostgresAdminBootstrapError,
        match="users table is empty",
    ):
        bootstrap.create_initial_admin(
            connection,
            "second-admin",
            "a-long-test-password",
        )

    assert connection.inserted_user is None
    assert "rbac.seed" not in connection.events
    assert "rbac.assign" not in connection.events
    assert "rbac.initial_grant" not in connection.events
    assert connection.events[-1] == "transaction.rollback"


def test_missing_migration_history_prevents_bootstrap(monkeypatch):
    connection = FakeConnection(history_table=None)
    patch_successful_dependencies(monkeypatch, connection)

    with pytest.raises(
        bootstrap.PostgresAdminBootstrapError,
        match="migrations have not been applied",
    ):
        bootstrap.create_initial_admin(
            connection,
            "first-admin",
            "a-long-test-password",
        )

    assert "rbac.seed" not in connection.events
    assert connection.inserted_user is None
    assert connection.events[-1] == "transaction.rollback"


def test_missing_baseline_migration_prevents_bootstrap(monkeypatch):
    connection = FakeConnection()
    connection.migration_rows = connection.migration_rows[:-1]
    patch_successful_dependencies(monkeypatch, connection)

    with pytest.raises(
        bootstrap.PostgresAdminBootstrapError,
        match="migrations are missing",
    ):
        bootstrap.create_initial_admin(
            connection,
            "first-admin",
            "a-long-test-password",
        )

    assert "rbac.seed" not in connection.events
    assert connection.inserted_user is None
    assert connection.events[-1] == "transaction.rollback"


def test_migration_checksum_mismatch_prevents_bootstrap(monkeypatch):
    connection = FakeConnection()
    first = connection.migration_rows[0]
    connection.migration_rows[0] = {
        "version": first["version"],
        "checksum": "0" * 64,
    }
    patch_successful_dependencies(monkeypatch, connection)

    with pytest.raises(
        bootstrap.PostgresAdminBootstrapError,
        match="checksums do not match",
    ):
        bootstrap.create_initial_admin(
            connection,
            "first-admin",
            "a-long-test-password",
        )

    assert "rbac.seed" not in connection.events
    assert connection.inserted_user is None
    assert connection.events[-1] == "transaction.rollback"


def test_failed_initial_permission_grant_rolls_back_admin_creation(
    monkeypatch,
):
    connection = FakeConnection()
    patch_successful_dependencies(
        monkeypatch,
        connection,
        grant_result=False,
    )

    with pytest.raises(
        bootstrap.PostgresAdminBootstrapError,
        match="delegation grant was not created",
    ):
        bootstrap.create_initial_admin(
            connection,
            "first-admin",
            "a-long-test-password",
        )

    assert connection.inserted_user is not None
    assert "audit" not in connection.events
    assert connection.events[-1] == "transaction.rollback"


@pytest.mark.parametrize(
    ("username", "password", "message"),
    [
        ("   ", "a-long-test-password", "Username must not be empty"),
        ("a" * 65, "a-long-test-password", "Username is too long"),
        ("valid-user", "short", "at least 12 characters"),
    ],
)
def test_invalid_input_is_rejected_before_transaction(
    monkeypatch,
    username,
    password,
    message,
):
    connection = FakeConnection()
    patch_successful_dependencies(monkeypatch, connection)

    with pytest.raises(ValueError, match=message):
        bootstrap.create_initial_admin(
            connection,
            username,
            password,
        )

    assert connection.events == []
    assert connection.inserted_user is None
