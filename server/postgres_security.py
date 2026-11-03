"""PostgreSQL-native security operations for LUMS."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from psycopg import Connection

if __package__:
    from .db_transactions import require_transaction
else:
    from db_transactions import require_transaction


LOGIN_RATE_LIMIT_LOCK_STEPS = (
    (5, 30),
    (6, 60),
    (7, 120),
    (8, 300),
)


def record_login_failure(
    connection: Connection,
    rate_limit_key: str,
    username: str,
) -> tuple[int, str | None]:
    """Atomically increment one login-failure counter.

    The caller must own an active transaction. The UPSERT serializes
    concurrent updates to the same unique rate_limit_key.

    Timestamps for the completed update are generated after the UPSERT
    has acquired its row lock, preventing stale timestamps after waits.

    This function never starts, commits, or rolls back a transaction.
    """
    require_transaction(connection)

    if (
        not isinstance(rate_limit_key, str)
        or not rate_limit_key
        or "\x00" in rate_limit_key
    ):
        raise ValueError("rate_limit_key must be a non-empty string")

    if not isinstance(username, str) or "\x00" in username:
        raise ValueError(
            "username must be a string without null characters"
        )

    inserted_at = datetime.now(timezone.utc).isoformat()

    row = connection.execute(
        """
        INSERT INTO login_rate_limits (
            rate_limit_key,
            username,
            failed_attempts,
            first_failed_at,
            last_failed_at,
            locked_until
        )
        VALUES (%s, %s, 1, %s, %s, NULL)
        ON CONFLICT (rate_limit_key) DO UPDATE
        SET
            username = EXCLUDED.username,
            failed_attempts = login_rate_limits.failed_attempts + 1
        RETURNING failed_attempts
        """,
        (rate_limit_key, username, inserted_at, inserted_at),
    ).fetchone()

    if row is None or not isinstance(row["failed_attempts"], int):
        raise RuntimeError(
            "PostgreSQL did not return the updated login-failure counter"
        )

    failed_attempts = row["failed_attempts"]

    recorded_at = datetime.now(timezone.utc)
    lock_seconds = None

    for threshold, seconds in LOGIN_RATE_LIMIT_LOCK_STEPS:
        if failed_attempts >= threshold:
            lock_seconds = seconds

    locked_until = (
        (recorded_at + timedelta(seconds=lock_seconds)).isoformat()
        if lock_seconds is not None
        else None
    )

    connection.execute(
        """
        UPDATE login_rate_limits
        SET last_failed_at = %s,
            locked_until = %s
        WHERE rate_limit_key = %s
        """,
        (recorded_at.isoformat(), locked_until, rate_limit_key),
    )

    return failed_attempts, locked_until


__all__ = [
    "LOGIN_RATE_LIMIT_LOCK_STEPS",
    "record_login_failure",
]
