"""Transaction-safe PostgreSQL login orchestration for LUMS."""

from __future__ import annotations

from dataclasses import dataclass

from psycopg import Connection

if __package__:
    from .i18n import normalize_language
    from .db_transactions import transaction
    from .postgres_auth import (
        clear_login_rate_limit,
        find_user,
        is_login_rate_limited,
    )
    from .postgres_audit import audit_log
    from .postgres_security import record_login_failure
    from .security import (
        hash_password,
        password_needs_rehash,
        verify_password,
    )
else:
    from i18n import normalize_language
    from db_transactions import transaction
    from postgres_auth import (
        clear_login_rate_limit,
        find_user,
        is_login_rate_limited,
    )
    from postgres_audit import audit_log
    from postgres_security import record_login_failure
    from security import (
        hash_password,
        password_needs_rehash,
        verify_password,
    )


@dataclass(frozen=True, slots=True)
class LoginResult:
    """Result of one authentication attempt.

    A failed result deliberately does not expose whether the username,
    password, or account state was responsible for the failure.
    """

    status: str
    user_id: int | None = None
    username: str | None = None
    language: str | None = None

    @property
    def authenticated(self) -> bool:
        return self.status == "authenticated"


def _audit_rate_limit_block(
    connection: Connection,
    username: str,
) -> None:
    audit_log(
        connection,
        actor_type="user",
        actor_id=username or None,
        action="login.rate_limit",
        target=None,
        result="blocked",
        details="login temporarily rate limited",
    )


def _record_failed_login(
    connection: Connection,
    username: str,
    rate_limit_key: str,
    user=None,
) -> None:
    """Record a failed attempt and its audit events in the active transaction."""
    failed_attempts, locked_until = record_login_failure(
        connection,
        rate_limit_key,
        username,
    )

    actor_id = user["id"] if user is not None else (username or None)
    target = f"user:{user['id']}" if user is not None else None

    audit_log(
        connection,
        actor_type="user",
        actor_id=actor_id,
        action="login",
        target=target,
        result="failure",
        details="invalid credentials",
    )

    if locked_until is not None:
        audit_log(
            connection,
            actor_type="user",
            actor_id=actor_id,
            action="login.rate_limit",
            target=target,
            result="locked",
            details=f"failed_attempts={failed_attempts}",
        )


def authenticate_user(
    connection: Connection,
    username: str,
    password: str,
    rate_limit_key: str,
    selected_language: str | None = None,
) -> LoginResult:
    """Authenticate one user and persist security changes atomically.

    Database reads and password verification are separated from write
    transactions where possible. Before a successful result is returned,
    the account is locked and revalidated inside a transaction.

    The caller owns the connection lifecycle. Flask session creation must
    happen only after this function returns an authenticated result.
    """
    if not isinstance(username, str) or "\x00" in username:
        raise ValueError(
            "username must be a string without null characters"
        )

    if not isinstance(password, str):
        raise ValueError("password must be a string")

    if not isinstance(rate_limit_key, str) or not rate_limit_key:
        raise ValueError("rate_limit_key must be a non-empty string")

    if selected_language is not None and not isinstance(
        selected_language, str
    ):
        raise ValueError("selected_language must be a string or None")

    # Check the lock in a short transaction. If another request has
    # established a lock, its state is visible before password verification.
    blocked = False

    with transaction(connection):
        if is_login_rate_limited(connection, rate_limit_key):
            _audit_rate_limit_block(connection, username)
            blocked = True

    if blocked:
        return LoginResult(status="rate_limited")

    user = find_user(connection, username)

    # Unknown, disabled, and invalid-password accounts use one generic
    # failure path to avoid account enumeration.
    if (
        user is None
        or user["enabled"] is not True
        or not verify_password(user["password_hash"], password)
    ):
        with transaction(connection):
            # Recheck because another request may have established a lock
            # after the initial check.
            if is_login_rate_limited(connection, rate_limit_key):
                _audit_rate_limit_block(connection, username)
                return LoginResult(status="rate_limited")

            _record_failed_login(
                connection,
                username,
                rate_limit_key,
                user if user is not None and user["enabled"] is True else None,
            )

        return LoginResult(status="invalid_credentials")

    original_hash = user["password_hash"]
    replacement_hash = (
        hash_password(password)
        if password_needs_rehash(original_hash)
        else None
    )

    result = LoginResult(status="invalid_credentials")

    with transaction(connection):
        # Prevent authentication using a password or account state that
        # changed after the initial password verification.
        current_user = connection.execute(
            """
            SELECT id, username, password_hash, enabled, role, language
            FROM users
            WHERE id = %s
            FOR UPDATE
            """,
            (user["id"],),
        ).fetchone()

        if (
            current_user is None
            or current_user["enabled"] is not True
            or current_user["password_hash"] != original_hash
        ):
            failure_user = (
                current_user
                if current_user is not None
                and current_user["enabled"] is True
                else None
            )

            if is_login_rate_limited(connection, rate_limit_key):
                _audit_rate_limit_block(connection, username)
                result = LoginResult(status="rate_limited")
            else:
                _record_failed_login(
                    connection,
                    username,
                    rate_limit_key,
                    failure_user,
                )
                result = LoginResult(status="invalid_credentials")

        elif is_login_rate_limited(connection, rate_limit_key):
            _audit_rate_limit_block(connection, username)
            result = LoginResult(status="rate_limited")

        else:
            preferred_language = normalize_language(
                current_user["language"]
            )
            fallback_language = (
                normalize_language(selected_language) or "de"
            )
            effective_language = (
                preferred_language or fallback_language
            )

            if preferred_language is None:
                connection.execute(
                    """
                    UPDATE users
                    SET language = %s
                    WHERE id = %s
                    """,
                    (effective_language, current_user["id"]),
                )

            if replacement_hash is not None:
                connection.execute(
                    """
                    UPDATE users
                    SET password_hash = %s
                    WHERE id = %s
                    """,
                    (replacement_hash, current_user["id"]),
                )

            clear_login_rate_limit(connection, rate_limit_key)

            audit_log(
                connection,
                actor_type="user",
                actor_id=current_user["id"],
                action="login",
                target=f"user:{current_user['id']}",
                result="success",
                details="interactive login",
            )

            result = LoginResult(
                status="authenticated",
                user_id=current_user["id"],
                username=current_user["username"],
                language=effective_language,
            )

    return result


__all__ = [
    "LoginResult",
    "authenticate_user",
]
