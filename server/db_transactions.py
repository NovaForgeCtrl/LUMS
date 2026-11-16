"""Explicit transaction helpers for LUMS PostgreSQL connections."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg.pq import TransactionStatus

if __package__:
    from .db_errors import (
        DatabaseConnectionStateError,
        DatabaseTransactionStateError,
    )
else:
    from db_errors import (
        DatabaseConnectionStateError,
        DatabaseTransactionStateError,
    )


@contextmanager
def transaction(connection: Connection) -> Iterator[Connection]:
    """Run one top-level atomic transaction.

    LUMS connections must use autocommit=True.
    Nested transactions are rejected rather than started implicitly.

    The context commits on success and rolls back on exceptions.
    """
    if connection.closed:
        raise DatabaseConnectionStateError(
            "Cannot start a transaction on a closed connection."
        )

    if connection.autocommit is not True:
        raise DatabaseTransactionStateError(
            "LUMS transactions require an autocommit connection."
        )

    if connection.info.transaction_status != TransactionStatus.IDLE:
        raise DatabaseTransactionStateError(
            "A transaction is already active; nested transactions "
            "are not managed implicitly."
        )

    with connection.transaction():
        yield connection


def require_transaction(connection: Connection) -> None:
    """Require an active transaction owned by the calling application.

    Intended for methods named *_in_transaction. These methods must not
    start, commit, or roll back the caller's transaction.
    """
    if connection.closed:
        raise DatabaseConnectionStateError(
            "The database connection is closed."
        )

    if connection.autocommit is not True:
        raise DatabaseTransactionStateError(
            "LUMS transactions require an autocommit connection."
        )

    if connection.info.transaction_status != TransactionStatus.INTRANS:
        raise DatabaseTransactionStateError(
            "This operation requires an active caller-owned transaction."
        )


__all__ = [
    "transaction",
    "require_transaction",
]
