"""Isolated tests for the shared LUMS database layer.

These tests do not connect to PostgreSQL.
"""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row


SERVER_DIR = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import db
from db_errors import (
    DatabaseConfigurationError,
    DatabaseConnectionStateError,
    DatabaseTransactionStateError,
)
from db_transactions import require_transaction, transaction


class FakeConnection:
    """Small connection double for transaction lifecycle tests."""

    def __init__(self):
        self.closed = False
        self.autocommit = True
        self.info = SimpleNamespace(
            transaction_status=TransactionStatus.IDLE
        )
        self.committed = False
        self.rolled_back = False

    @contextmanager
    def transaction(self):
        if self.info.transaction_status != TransactionStatus.IDLE:
            raise AssertionError("Fake transaction already active")

        self.info.transaction_status = TransactionStatus.INTRANS

        try:
            yield self
        except BaseException:
            self.rolled_back = True
            self.info.transaction_status = TransactionStatus.IDLE
            raise
        else:
            self.committed = True
            self.info.transaction_status = TransactionStatus.IDLE


def test_get_database_url_returns_trimmed_value():
    result = db.get_database_url({
        "DATABASE_URL": "  postgresql://lums@localhost/lums  "
    })

    assert result == "postgresql://lums@localhost/lums"


def test_get_database_url_rejects_missing_value():
    with pytest.raises(DatabaseConfigurationError):
        db.get_database_url({})


def test_get_database_url_does_not_fall_back_to_legacy_sqlite_path():
    with pytest.raises(DatabaseConfigurationError):
        db.get_database_url({
            "LUMS_DB_PATH": "/var/lib/lums/lums.db"
        })


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "sqlite:///var/lib/lums/lums.db",
        "mysql://localhost/lums",
        "postgresql://localhost/lums#fragment",
        "postgresql://lums@db:notaport/lums",
        "postgresql://lums@db:0/lums",
        "postgresql://lums@db:65536/lums",
        "postgresql:///lums?host=db&port=notaport",
        "postgresql://host1:5432,host2:65536/lums",
    ],
)
def test_get_database_url_rejects_invalid_values(value):
    with pytest.raises(DatabaseConfigurationError):
        db.get_database_url({"DATABASE_URL": value})


def test_get_database_url_rejects_non_mapping():
    with pytest.raises(TypeError):
        db.get_database_url([])


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://lums@db:1/lums",
        "postgresql://lums@db:65535/lums",
        "postgresql://host1:5432,host2:5433/lums",
        "postgresql:///lums?host=/var/run/postgresql",
    ],
)
def test_get_database_url_accepts_valid_connection_urls(value):
    assert db.get_database_url({"DATABASE_URL": value}) == value


def test_connect_uses_dict_rows_and_autocommit(monkeypatch):
    captured = {}
    expected_connection = object()

    def fake_connect(conninfo, **kwargs):
        captured["conninfo"] = conninfo
        captured.update(kwargs)
        return expected_connection

    monkeypatch.setattr(db.psycopg, "connect", fake_connect)

    result = db.connect(
        "postgresql://lums@localhost/lums",
        connect_timeout=7,
        application_name="lums-api",
    )

    assert result is expected_connection
    assert captured["conninfo"] == "postgresql://lums@localhost/lums"
    assert captured["autocommit"] is True
    assert captured["row_factory"] is dict_row
    assert captured["connect_timeout"] == 7
    assert captured["application_name"] == "lums-api"


@pytest.mark.parametrize("timeout", [True, 0, -1, 61, "5"])
def test_connect_rejects_invalid_timeout(timeout):
    with pytest.raises(ValueError):
        db.connect(
            "postgresql://lums@localhost/lums",
            connect_timeout=timeout,
        )


@pytest.mark.parametrize(
    "application_name",
    ["", " ", "x" * 64, "lums\x00api"],
)
def test_connect_rejects_invalid_application_name(application_name):
    with pytest.raises(ValueError):
        db.connect(
            "postgresql://lums@localhost/lums",
            application_name=application_name,
        )


def test_transaction_commits_on_success():
    connection = FakeConnection()

    with transaction(connection) as active:
        assert active is connection
        assert (
            connection.info.transaction_status
            == TransactionStatus.INTRANS
        )

    assert connection.committed is True
    assert connection.rolled_back is False
    assert (
        connection.info.transaction_status
        == TransactionStatus.IDLE
    )


def test_transaction_rolls_back_on_exception():
    connection = FakeConnection()

    with pytest.raises(RuntimeError):
        with transaction(connection):
            raise RuntimeError("simulated failure")

    assert connection.committed is False
    assert connection.rolled_back is True
    assert (
        connection.info.transaction_status
        == TransactionStatus.IDLE
    )


def test_transaction_rejects_nested_transaction():
    connection = FakeConnection()

    with pytest.raises(DatabaseTransactionStateError):
        with transaction(connection):
            with transaction(connection):
                pass

    assert connection.rolled_back is True


def test_transaction_rejects_non_autocommit_connection():
    connection = FakeConnection()
    connection.autocommit = False

    with pytest.raises(DatabaseTransactionStateError):
        with transaction(connection):
            pass


def test_transaction_rejects_closed_connection():
    connection = FakeConnection()
    connection.closed = True

    with pytest.raises(DatabaseConnectionStateError):
        with transaction(connection):
            pass


def test_require_transaction_accepts_caller_owned_transaction():
    connection = FakeConnection()
    connection.info.transaction_status = TransactionStatus.INTRANS

    assert require_transaction(connection) is None


def test_require_transaction_rejects_non_autocommit_connection():
    connection = FakeConnection()
    connection.autocommit = False
    connection.info.transaction_status = TransactionStatus.INTRANS

    with pytest.raises(DatabaseTransactionStateError):
        require_transaction(connection)


@pytest.mark.parametrize(
    "status",
    [
        TransactionStatus.IDLE,
        TransactionStatus.INERROR,
        TransactionStatus.UNKNOWN,
    ],
)
def test_require_transaction_rejects_inactive_or_failed_transaction(status):
    connection = FakeConnection()
    connection.info.transaction_status = status

    with pytest.raises(DatabaseTransactionStateError):
        require_transaction(connection)
