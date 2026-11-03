"""Unit and isolated PostgreSQL integration tests for the RBAC write lock."""

import os
from pathlib import Path
import sys
from threading import Thread
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row


SERVER_DIR = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from db_errors import DatabaseTransactionStateError
from db_transactions import transaction
from rbac_lock import acquire_rbac_write_lock


LOCK_CLASS = 1_280_131_411
LOCK_OBJECT = 2
LOCK_WORKER_APP = "lums-rbac-lock-worker"


class FakeConnection:
    def __init__(self, *, status=TransactionStatus.INTRANS, fail_at=None):
        self.closed = False
        self.autocommit = True
        self.info = SimpleNamespace(transaction_status=status)
        self.statements = []
        self.fail_at = fail_at

    def execute(self, statement, params=None):
        self.statements.append((statement, params))
        if self.fail_at == len(self.statements):
            raise RuntimeError("simulated SQL failure")
        return None


def test_rbac_lock_requires_an_active_transaction():
    connection = FakeConnection(status=TransactionStatus.IDLE)

    with pytest.raises(DatabaseTransactionStateError):
        acquire_rbac_write_lock(connection)

    assert connection.statements == []


def test_rbac_lock_sets_isolation_before_acquiring_lock():
    connection = FakeConnection()

    acquire_rbac_write_lock(connection)

    assert connection.statements == [
        (
            "SET TRANSACTION ISOLATION LEVEL READ COMMITTED",
            None,
        ),
        (
            "SELECT pg_advisory_xact_lock(%s, %s)",
            (LOCK_CLASS, LOCK_OBJECT),
        ),
    ]


def test_rbac_lock_does_not_acquire_lock_if_isolation_setup_fails():
    connection = FakeConnection(fail_at=1)

    with pytest.raises(RuntimeError, match="simulated SQL failure"):
        acquire_rbac_write_lock(connection)

    assert len(connection.statements) == 1
    assert connection.statements[0][0] == (
        "SET TRANSACTION ISOLATION LEVEL READ COMMITTED"
    )


def test_rbac_lock_propagates_lock_acquisition_failure():
    connection = FakeConnection(fail_at=2)

    with pytest.raises(RuntimeError, match="simulated SQL failure"):
        acquire_rbac_write_lock(connection)

    assert len(connection.statements) == 2


@pytest.fixture
def postgres_environment():
    database_url = os.environ.get("LUMS_TEST_DATABASE_URL")

    if not database_url:
        pytest.skip("LUMS_TEST_DATABASE_URL is not configured")

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-rbac-lock-test-setup",
    )

    schema_name = f"lums_rbac_lock_test_{uuid4().hex}"

    try:
        identity = admin.execute(
            "SELECT current_database(), current_user"
        ).fetchone()

        if (
            identity["current_database"] != "lums_integration"
            or identity["current_user"] != "lums_pg_bootstrap"
        ):
            pytest.fail(
                "Refusing RBAC lock tests outside the dedicated "
                "lums_integration database and lums_pg_bootstrap role."
            )

        admin.execute(
            sql.SQL("CREATE SCHEMA {}").format(
                sql.Identifier(schema_name)
            )
        )

        yield database_url, schema_name

    finally:
        admin.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                sql.Identifier(schema_name)
            )
        )
        admin.close()


def _set_search_path(connection, schema_name):
    connection.execute(
        sql.SQL("SET search_path TO {}").format(
            sql.Identifier(schema_name)
        )
    )


def test_rbac_lock_serializes_transactions_and_exposes_committed_state(
    postgres_environment,
):
    database_url, schema_name = postgres_environment

    first = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-rbac-lock-owner",
    )
    observer = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-rbac-lock-observer",
    )

    worker_errors = []
    worker_results = []
    worker = None

    try:
        _set_search_path(first, schema_name)
        _set_search_path(observer, schema_name)

        observer.execute(
            """
            CREATE TABLE rbac_lock_probe (
                id INTEGER PRIMARY KEY
            )
            """
        )

        def wait_for_lock():
            second = None
            try:
                second = psycopg.connect(
                    database_url,
                    autocommit=True,
                    row_factory=dict_row,
                    application_name=LOCK_WORKER_APP,
                )
                _set_search_path(second, schema_name)

                with transaction(second):
                    acquire_rbac_write_lock(second)
                    row = second.execute(
                        "SELECT COUNT(*) AS total FROM rbac_lock_probe"
                    ).fetchone()
                    worker_results.append(row["total"])

            except BaseException as exc:
                worker_errors.append(exc)
            finally:
                if second is not None:
                    second.close()

        waiting_observed = False

        with transaction(first):
            acquire_rbac_write_lock(first)

            isolation = first.execute(
                "SHOW transaction_isolation"
            ).fetchone()
            assert isolation["transaction_isolation"] == "read committed"

            first.execute(
                "INSERT INTO rbac_lock_probe(id) VALUES (1)"
            )

            worker = Thread(target=wait_for_lock, daemon=True)
            worker.start()

            deadline = monotonic() + 10
            while monotonic() < deadline:
                row = observer.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_locks AS locks
                        JOIN pg_stat_activity AS activity
                          ON activity.pid = locks.pid
                        WHERE locks.locktype = 'advisory'
                          AND locks.classid = %s::oid
                          AND locks.objid = %s::oid
                          AND locks.objsubid = 2
                          AND NOT locks.granted
                          AND activity.application_name = %s
                    ) AS waiting
                    """,
                    (LOCK_CLASS, LOCK_OBJECT, LOCK_WORKER_APP),
                ).fetchone()

                if row["waiting"]:
                    waiting_observed = True
                    break

                sleep(0.01)

            assert waiting_observed, (
                "Second transaction did not wait for the RBAC advisory lock."
            )

        # The first transaction has committed here. The waiting transaction
        # must acquire the lock and then see the committed row.
        worker.join(timeout=10)

        assert not worker.is_alive(), "RBAC lock worker did not finish."
        assert worker_errors == []
        assert worker_results == [1]

    finally:
        if worker is not None and worker.is_alive():
            worker.join(timeout=10)
        observer.close()
        first.close()
