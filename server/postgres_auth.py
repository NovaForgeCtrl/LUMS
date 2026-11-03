"""PostgreSQL-native authentication queries for LUMS."""

from __future__ import annotations

from datetime import datetime, timezone

from psycopg import Connection

if __package__:
    from .db_transactions import require_transaction
else:
    from db_transactions import require_transaction


def _validate_rate_limit_key(rate_limit_key: str) -> None:
    if (
        not isinstance(rate_limit_key, str)
        or not rate_limit_key
        or "\x00" in rate_limit_key
    ):
        raise ValueError(
            "rate_limit_key must be a non-empty string"
        )


def _parse_utc_datetime(value) -> datetime | None:
    """Parse ISO timestamps and normalize naive values to UTC."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except (TypeError, ValueError, OverflowError):
            return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def find_user(
    connection: Connection,
    username: str,
):
    """Find one account by its exact username.

    The returned psycopg dict row includes the language preference and
    the fields required by the existing Argon2 authentication flow.
    """
    if not isinstance(username, str) or "\x00" in username:
        raise ValueError(
            "username must be a string without null characters"
        )

    return connection.execute(
        """
        SELECT
            id,
            username,
            password_hash,
            enabled,
            role,
            language
        FROM users
        WHERE username = %s
        """,
        (username,),
    ).fetchone()


def get_login_rate_limit(
    connection: Connection,
    rate_limit_key: str,
):
    """Load the persisted login-failure state for one rate-limit key."""
    _validate_rate_limit_key(rate_limit_key)

    return connection.execute(
        """
        SELECT
            id,
            rate_limit_key,
            username,
            failed_attempts,
            first_failed_at,
            last_failed_at,
            locked_until
        FROM login_rate_limits
        WHERE rate_limit_key = %s
        """,
        (rate_limit_key,),
    ).fetchone()


def is_login_rate_limited(
    connection: Connection,
    rate_limit_key: str,
) -> bool:
    """Return whether a persisted login lock is still active."""
    row = get_login_rate_limit(connection, rate_limit_key)

    if row is None:
        return False

    locked_until = _parse_utc_datetime(row["locked_until"])

    if locked_until is None:
        return False

    return locked_until > datetime.now(timezone.utc)


def clear_login_rate_limit(
    connection: Connection,
    rate_limit_key: str,
) -> None:
    """Delete one login-failure record in the caller-owned transaction."""
    require_transaction(connection)
    _validate_rate_limit_key(rate_limit_key)

    connection.execute(
        """
        DELETE FROM login_rate_limits
        WHERE rate_limit_key = %s
        """,
        (rate_limit_key,),
    )


__all__ = [
    "clear_login_rate_limit",
    "find_user",
    "get_login_rate_limit",
    "is_login_rate_limited",
]
