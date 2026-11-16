"""Database-free unit tests for PostgreSQL audit logging."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus

from server.db_errors import DatabaseTransactionStateError
from server.postgres_audit import audit_log


class FakeConnection:
    def __init__(self, status=TransactionStatus.INTRANS):
        self.closed = False
        self.autocommit = True
        self.info = SimpleNamespace(transaction_status=status)
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((statement, params))


def test_audit_log_inserts_event_with_expected_fields():
    connection = FakeConnection()

    audit_log(
        connection,
        actor_type="user",
        actor_id=42,
        action="login",
        target="user:42",
        result="success",
        details="interactive login",
    )

    assert len(connection.calls) == 1
    statement, params = connection.calls[0]

    assert "INSERT INTO audit_log" in statement
    assert "VALUES (%s, %s, %s, %s, %s, %s, %s)" in statement

    timestamp, actor_type, actor_id, action, target, result, details = params

    parsed_timestamp = datetime.fromisoformat(timestamp)
    assert parsed_timestamp.tzinfo is not None

    assert actor_type == "user"
    assert actor_id == "42"
    assert action == "login"
    assert target == "user:42"
    assert result == "success"
    assert details == "interactive login"


def test_audit_log_supports_nullable_actor_and_optional_fields():
    connection = FakeConnection()

    audit_log(
        connection,
        actor_type="system",
        actor_id=None,
        action="admin_created",
    )

    _, params = connection.calls[0]

    assert params[1] == "system"
    assert params[2] is None
    assert params[3] == "admin_created"
    assert params[4] is None
    assert params[5] == "success"
    assert params[6] is None


def test_audit_log_requires_caller_transaction():
    connection = FakeConnection(
        status=TransactionStatus.IDLE
    )

    with pytest.raises(DatabaseTransactionStateError):
        audit_log(
            connection,
            actor_type="user",
            actor_id=1,
            action="login",
        )

    assert connection.calls == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"actor_type": ""},
        {"actor_type": None},
        {"action": ""},
        {"action": None},
        {"result": ""},
        {"result": None},
        {"target": 123},
        {"details": 123},
    ],
)
def test_audit_log_rejects_invalid_fields(kwargs):
    connection = FakeConnection()

    values = {
        "actor_type": "user",
        "actor_id": 1,
        "action": "login",
        "target": None,
        "result": "success",
        "details": None,
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        audit_log(connection, **values)

    assert connection.calls == []
