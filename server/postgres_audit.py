"""PostgreSQL-native audit logging for LUMS."""

from __future__ import annotations

from datetime import datetime, timezone

from psycopg import Connection

if __package__:
    from .db_transactions import require_transaction
else:
    from db_transactions import require_transaction


def audit_log(
    connection: Connection,
    actor_type: str,
    actor_id=None,
    action: str = "",
    target: str | None = None,
    result: str = "success",
    details: str | None = None,
) -> None:
    """Insert one audit event into the caller-owned transaction.

    This function never starts, commits, or rolls back a transaction.
    Audit records therefore remain atomic with the operation they describe.
    """
    require_transaction(connection)

    if not isinstance(actor_type, str) or not actor_type:
        raise ValueError("actor_type must be a non-empty string")

    if not isinstance(action, str) or not action:
        raise ValueError("action must be a non-empty string")

    if not isinstance(result, str) or not result:
        raise ValueError("result must be a non-empty string")

    if target is not None and not isinstance(target, str):
        raise ValueError("target must be a string or None")

    if details is not None and not isinstance(details, str):
        raise ValueError("details must be a string or None")

    timestamp = datetime.now(timezone.utc).isoformat()

    connection.execute(
        """
        INSERT INTO audit_log (
            timestamp,
            actor_type,
            actor_id,
            action,
            target,
            result,
            details
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            timestamp,
            actor_type,
            str(actor_id) if actor_id is not None else None,
            action,
            target,
            result,
            details,
        ),
    )


__all__ = ["audit_log"]
