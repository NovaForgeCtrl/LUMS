"""Database-free tests for PostgreSQL authorization state loading."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus

from server import postgres_authorization as authorization


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row=None):
        self.row = row
        self.calls = []
        self.transaction_count = 0
        self.closed = False
        self.autocommit = True
        self.info = SimpleNamespace(
            transaction_status=TransactionStatus.IDLE
        )

    @contextmanager
    def transaction(self):
        if self.info.transaction_status != TransactionStatus.IDLE:
            raise AssertionError("Unexpected nested transaction")

        self.info.transaction_status = TransactionStatus.INTRANS
        self.transaction_count += 1

        try:
            yield self
        finally:
            self.info.transaction_status = TransactionStatus.IDLE

    def execute(self, statement, params=None):
        self.calls.append((" ".join(statement.split()), params))

        if "FROM users" in statement:
            return FakeCursor(self.row)

        return FakeCursor(None)


def make_user(*, enabled=True, role="administrator"):
    return {
        "id": 7,
        "username": "administrator",
        "enabled": enabled,
        "role": role,
    }


def test_active_user_receives_resolved_permissions(monkeypatch):
    expected_permissions = frozenset({
        "clients.view",
        "software.view",
    })

    called = []

    def resolve(connection, user_id):
        assert connection.info.transaction_status == TransactionStatus.INTRANS
        called.append((connection, user_id))
        return expected_permissions

    monkeypatch.setattr(
        authorization,
        "resolve_user_permissions",
        resolve,
    )

    connection = FakeConnection(row=make_user())

    result = authorization.load_authorization_state(
        connection,
        7,
    )

    assert result is not None
    assert result.user["id"] == 7
    assert result.user["username"] == "administrator"
    assert result.permissions == expected_permissions
    assert called == [(connection, 7)]
    assert connection.info.transaction_status == TransactionStatus.IDLE


def test_authorization_uses_read_only_repeatable_read_snapshot(
    monkeypatch,
):
    monkeypatch.setattr(
        authorization,
        "resolve_user_permissions",
        lambda connection, user_id: frozenset({"clients.view"}),
    )

    connection = FakeConnection(row=make_user())

    authorization.load_authorization_state(connection, 7)

    assert connection.calls[0] == (
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        None,
    )

    assert "FROM users" in connection.calls[1][0]
    assert connection.calls[1][1] == (7,)
    assert connection.transaction_count == 1


def test_missing_user_returns_none_without_rbac_lookup(monkeypatch):
    called = []

    monkeypatch.setattr(
        authorization,
        "resolve_user_permissions",
        lambda *args: called.append(args),
    )

    connection = FakeConnection(row=None)

    result = authorization.load_authorization_state(
        connection,
        7,
    )

    assert result is None
    assert called == []
    assert connection.info.transaction_status == TransactionStatus.IDLE


def test_disabled_user_returns_none_without_rbac_lookup(monkeypatch):
    called = []

    monkeypatch.setattr(
        authorization,
        "resolve_user_permissions",
        lambda *args: called.append(args),
    )

    connection = FakeConnection(
        row=make_user(enabled=False)
    )

    result = authorization.load_authorization_state(
        connection,
        7,
    )

    assert result is None
    assert called == []


def test_invalid_role_fails_closed(monkeypatch):
    called = []

    monkeypatch.setattr(
        authorization,
        "resolve_user_permissions",
        lambda *args: called.append(args),
    )

    connection = FakeConnection(
        row=make_user(role="unknown-role")
    )

    with pytest.raises(
        authorization.PostgresAuthorizationError,
        match="invalid PostgreSQL role",
    ):
        authorization.load_authorization_state(connection, 7)

    assert called == []


def test_invalid_permission_result_fails_closed(monkeypatch):
    monkeypatch.setattr(
        authorization,
        "resolve_user_permissions",
        lambda *args: {"clients.view"},
    )

    connection = FakeConnection(row=make_user())

    with pytest.raises(
        authorization.PostgresAuthorizationError,
        match="invalid permission collection",
    ):
        authorization.load_authorization_state(connection, 7)


def test_rbac_errors_are_not_hidden(monkeypatch):
    def fail(*args):
        raise authorization.PostgresAuthorizationError(
            "RBAC schema unavailable"
        )

    monkeypatch.setattr(
        authorization,
        "resolve_user_permissions",
        fail,
    )

    connection = FakeConnection(row=make_user())

    with pytest.raises(
        authorization.PostgresAuthorizationError,
        match="schema unavailable",
    ):
        authorization.load_authorization_state(connection, 7)

    assert connection.info.transaction_status == TransactionStatus.IDLE


@pytest.mark.parametrize(
    "user_id",
    [None, True, False, 0, -1, "7", 7.0],
)
def test_invalid_user_id_is_rejected_without_query(user_id):
    connection = FakeConnection(row=make_user())

    with pytest.raises(ValueError):
        authorization.load_authorization_state(connection, user_id)

    assert connection.calls == []
    assert connection.transaction_count == 0


def test_returned_user_is_detached_from_driver_row(monkeypatch):
    monkeypatch.setattr(
        authorization,
        "resolve_user_permissions",
        lambda *args: frozenset({"clients.view"}),
    )

    original = make_user()
    connection = FakeConnection(row=original)

    result = authorization.load_authorization_state(connection, 7)

    assert result.user == original
    assert result.user is not original


def test_authorization_state_is_immutable():
    state = authorization.AuthorizationState(
        user={"id": 7},
        permissions=frozenset({"clients.view"}),
    )

    with pytest.raises(AttributeError):
        state.permissions = frozenset()
