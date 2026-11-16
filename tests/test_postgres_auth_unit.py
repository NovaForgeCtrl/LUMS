"""Database-free unit tests for PostgreSQL authentication helpers."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus

from server.db_errors import DatabaseTransactionStateError
from server.postgres_auth import (
    clear_login_rate_limit,
    find_user,
    get_login_rate_limit,
    is_login_rate_limited,
)


class FakeCursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, *, row=None, transaction_status=TransactionStatus.IDLE):
        self.closed = False
        self.autocommit = True
        self.info = SimpleNamespace(
            transaction_status=transaction_status
        )
        self.row = row
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((statement, params))
        return FakeCursor(self.row)


def test_find_user_uses_parameterized_query_and_returns_language():
    expected = {
        "id": 7,
        "username": "administrator",
        "password_hash": "argon2-hash",
        "enabled": True,
        "role": "administrator",
        "language": "de",
    }
    connection = FakeConnection(row=expected)

    result = find_user(connection, "administrator")

    assert result == expected
    assert len(connection.calls) == 1

    statement, params = connection.calls[0]
    assert "FROM users" in statement
    assert "WHERE username = %s" in statement
    assert "language" in statement
    assert params == ("administrator",)


@pytest.mark.parametrize(
    "username",
    [None, 123, "invalid\x00username"],
)
def test_find_user_rejects_invalid_username(username):
    connection = FakeConnection()

    with pytest.raises(ValueError):
        find_user(connection, username)

    assert connection.calls == []


def test_get_login_rate_limit_returns_persisted_row():
    expected = {
        "id": 1,
        "rate_limit_key": "admin|127.0.0.1",
        "username": "admin",
        "failed_attempts": 5,
        "first_failed_at": "2026-11-02T08:00:00+00:00",
        "last_failed_at": "2026-11-02T08:01:00+00:00",
        "locked_until": "2026-11-02T08:01:30+00:00",
    }
    connection = FakeConnection(row=expected)

    result = get_login_rate_limit(
        connection,
        "admin|127.0.0.1",
    )

    assert result == expected
    assert connection.calls[0][1] == ("admin|127.0.0.1",)


@pytest.mark.parametrize(
    "rate_limit_key",
    ["", None, "invalid\x00key"],
)
def test_get_login_rate_limit_rejects_invalid_key(rate_limit_key):
    connection = FakeConnection()

    with pytest.raises(ValueError):
        get_login_rate_limit(connection, rate_limit_key)

    assert connection.calls == []


def test_rate_limit_is_false_when_record_does_not_exist():
    connection = FakeConnection(row=None)

    assert not is_login_rate_limited(
        connection,
        "admin|127.0.0.1",
    )


def test_rate_limit_is_false_without_locked_until():
    connection = FakeConnection(
        row={"locked_until": None}
    )

    assert not is_login_rate_limited(
        connection,
        "admin|127.0.0.1",
    )


def test_rate_limit_is_true_for_future_timestamp():
    future = (
        datetime.now(timezone.utc) + timedelta(minutes=1)
    ).isoformat()

    connection = FakeConnection(
        row={"locked_until": future}
    )

    assert is_login_rate_limited(
        connection,
        "admin|127.0.0.1",
    )


def test_rate_limit_is_false_for_expired_timestamp():
    expired = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    ).isoformat()

    connection = FakeConnection(
        row={"locked_until": expired}
    )

    assert not is_login_rate_limited(
        connection,
        "admin|127.0.0.1",
    )


def test_rate_limit_accepts_naive_timestamp_as_utc():
    future = (
        datetime.now(timezone.utc) + timedelta(minutes=1)
    ).replace(tzinfo=None).isoformat()

    connection = FakeConnection(
        row={"locked_until": future}
    )

    assert is_login_rate_limited(
        connection,
        "admin|127.0.0.1",
    )


@pytest.mark.parametrize(
    "locked_until",
    ["invalid-timestamp", 123, None],
)
def test_rate_limit_fails_closed_for_invalid_timestamp(locked_until):
    connection = FakeConnection(
        row={"locked_until": locked_until}
    )

    assert not is_login_rate_limited(
        connection,
        "admin|127.0.0.1",
    )


def test_clear_login_rate_limit_requires_caller_transaction():
    connection = FakeConnection(
        transaction_status=TransactionStatus.IDLE
    )

    with pytest.raises(DatabaseTransactionStateError):
        clear_login_rate_limit(
            connection,
            "admin|127.0.0.1",
        )

    assert connection.calls == []


def test_clear_login_rate_limit_uses_parameterized_delete():
    connection = FakeConnection(
        transaction_status=TransactionStatus.INTRANS
    )

    result = clear_login_rate_limit(
        connection,
        "admin|127.0.0.1",
    )

    assert result is None
    assert len(connection.calls) == 1

    statement, params = connection.calls[0]
    assert "DELETE FROM login_rate_limits" in statement
    assert "WHERE rate_limit_key = %s" in statement
    assert params == ("admin|127.0.0.1",)
