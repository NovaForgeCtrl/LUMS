"""Transaction-scoped serialization for LUMS user and RBAC writes."""

from __future__ import annotations

from psycopg import Connection

if __package__:
    from .db_transactions import require_transaction
else:
    from db_transactions import require_transaction


# The migration runner uses (1280131411, 1).
# RBAC writes use a separate, transaction-scoped advisory lock.
_RBAC_LOCK_CLASS = 1_280_131_411
_RBAC_LOCK_OBJECT = 2


def acquire_rbac_write_lock(connection: Connection) -> None:
    """Serialize a user/RBAC write transaction.

    Call immediately after opening the transaction and before executing
    any other SQL statement in it.

    READ COMMITTED is set explicitly so statements executed after waiting
    for the advisory lock observe transactions committed while waiting.

    The caller owns the transaction. PostgreSQL releases this lock
    automatically on commit or rollback.
    """
    require_transaction(connection)

    # PostgreSQL requires SET TRANSACTION before any query or data change.
    # This deliberately fails closed if the caller invokes this helper late.
    connection.execute(
        "SET TRANSACTION ISOLATION LEVEL READ COMMITTED"
    )

    connection.execute(
        "SELECT pg_advisory_xact_lock(%s, %s)",
        (_RBAC_LOCK_CLASS, _RBAC_LOCK_OBJECT),
    )


__all__ = ["acquire_rbac_write_lock"]
