"""Database-free tests for PostgreSQL login orchestration."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus

from server import postgres_login


class FakeCursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(
        self,
        *,
        user=None,
        locked_user=None,
        rate_limit_row=None,
        failed_attempts=1,
    ):
        self.closed = False
        self.autocommit = True
        self.info = SimpleNamespace(
            transaction_status=TransactionStatus.IDLE
        )
        self.user = user
        self.locked_user = locked_user if locked_user is not None else user
        self.rate_limit_row = rate_limit_row
        self.failed_attempts = failed_attempts
        self.calls = []
        self.transaction_count = 0

    @contextmanager
    def transaction(self):
        if self.info.transaction_status != TransactionStatus.IDLE:
            raise AssertionError("Unexpected nested transaction")

        self.info.transaction_status = TransactionStatus.INTRANS
        self.transaction_count += 1

        try:
            yield self
        finally:
            self.info.transaction_status = TransactionStatus.IDLE

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.calls.append((normalized, params))

        if "FROM login_rate_limits" in normalized:
            return FakeCursor(self.rate_limit_row)

        if "FROM users" in normalized and "FOR UPDATE" in normalized:
            return FakeCursor(self.locked_user)

        if "FROM users" in normalized:
            return FakeCursor(self.user)

        if "INSERT INTO login_rate_limits" in normalized:
            return FakeCursor({
                "failed_attempts": self.failed_attempts,
            })

        return FakeCursor()


def make_user(
    *,
    enabled=True,
    password_hash="original-hash",
    language="de",
):
    return {
        "id": 7,
        "username": "administrator",
        "password_hash": password_hash,
        "enabled": enabled,
        "role": "administrator",
        "language": language,
    }


def patch_password_functions(monkeypatch, *, valid=True, needs_rehash=False):
    monkeypatch.setattr(
        postgres_login,
        "verify_password",
        lambda stored, supplied: valid,
    )
    monkeypatch.setattr(
        postgres_login,
        "password_needs_rehash",
        lambda stored: needs_rehash,
    )
    monkeypatch.setattr(
        postgres_login,
        "hash_password",
        lambda supplied: "replacement-hash",
    )


def test_valid_login_returns_user_only_after_transaction(monkeypatch):
    patch_password_functions(monkeypatch)

    user = make_user()
    connection = FakeConnection(user=user)

    result = postgres_login.authenticate_user(
        connection,
        "administrator",
        "correct-password",
        "administrator|127.0.0.1",
    )

    assert result.authenticated is True
    assert result.status == "authenticated"
    assert result.user_id == 7
    assert result.username == "administrator"
    assert result.language == "de"
    assert connection.info.transaction_status == TransactionStatus.IDLE

    statements = [statement for statement, _ in connection.calls]
    assert any("FOR UPDATE" in statement for statement in statements)
    assert any("DELETE FROM login_rate_limits" in statement for statement in statements)
    assert any("INSERT INTO audit_log" in statement for statement in statements)


def test_invalid_password_records_failure_and_audit(monkeypatch):
    patch_password_functions(monkeypatch, valid=False)

    user = make_user()
    connection = FakeConnection(user=user, failed_attempts=3)

    result = postgres_login.authenticate_user(
        connection,
        "administrator",
        "wrong-password",
        "administrator|127.0.0.1",
    )

    assert result.authenticated is False
    assert result.status == "invalid_credentials"

    statements = [statement for statement, _ in connection.calls]
    assert any("INSERT INTO login_rate_limits" in statement for statement in statements)
    assert any("UPDATE login_rate_limits" in statement for statement in statements)
    assert any("INSERT INTO audit_log" in statement for statement in statements)
    assert not any("FOR UPDATE" in statement for statement in statements)


def test_active_rate_limit_blocks_before_user_lookup(monkeypatch):
    future = (
        datetime.now(timezone.utc) + timedelta(minutes=1)
    ).isoformat()

    connection = FakeConnection(
        rate_limit_row={"locked_until": future}
    )

    result = postgres_login.authenticate_user(
        connection,
        "administrator",
        "any-password",
        "administrator|127.0.0.1",
    )

    assert result.status == "rate_limited"
    assert result.authenticated is False

    statements = [statement for statement, _ in connection.calls]
    assert not any("FROM users" in statement for statement in statements)
    assert any("INSERT INTO audit_log" in statement for statement in statements)


def test_disabled_user_cannot_authenticate(monkeypatch):
    patch_password_functions(monkeypatch)

    user = make_user(enabled=False)
    connection = FakeConnection(user=user)

    result = postgres_login.authenticate_user(
        connection,
        "administrator",
        "correct-password",
        "administrator|127.0.0.1",
    )

    assert result.status == "invalid_credentials"
    assert result.authenticated is False

    statements = [statement for statement, _ in connection.calls]
    assert not any("FOR UPDATE" in statement for statement in statements)
    assert any("INSERT INTO login_rate_limits" in statement for statement in statements)


def test_changed_password_hash_is_rejected_after_revalidation(monkeypatch):
    patch_password_functions(monkeypatch)

    initial_user = make_user(password_hash="original-hash")
    changed_user = make_user(password_hash="new-hash")

    connection = FakeConnection(
        user=initial_user,
        locked_user=changed_user,
    )

    result = postgres_login.authenticate_user(
        connection,
        "administrator",
        "correct-password-for-old-hash",
        "administrator|127.0.0.1",
    )

    assert result.status == "invalid_credentials"
    assert result.authenticated is False

    statements = [statement for statement, _ in connection.calls]
    assert any("FOR UPDATE" in statement for statement in statements)
    assert any("INSERT INTO login_rate_limits" in statement for statement in statements)
    assert not any("DELETE FROM login_rate_limits" in statement for statement in statements)


def test_password_rehash_is_persisted_on_success(monkeypatch):
    patch_password_functions(monkeypatch, needs_rehash=True)

    user = make_user()
    connection = FakeConnection(user=user)

    result = postgres_login.authenticate_user(
        connection,
        "administrator",
        "correct-password",
        "administrator|127.0.0.1",
    )

    assert result.authenticated is True

    updates = [
        (statement, params)
        for statement, params in connection.calls
        if statement.startswith("UPDATE users")
    ]

    assert len(updates) == 1
    assert updates[0][1] == ("replacement-hash", 7)


def test_valid_stored_language_takes_precedence(monkeypatch):
    patch_password_functions(monkeypatch)

    connection = FakeConnection(user=make_user(language="en-GB"))

    result = postgres_login.authenticate_user(
        connection,
        "administrator",
        "correct-password",
        "administrator|127.0.0.1",
        selected_language="fr",
    )

    assert result.authenticated is True
    assert result.language == "en-GB"

    statements = [statement for statement, _ in connection.calls]
    assert not any(
        statement.startswith("UPDATE users SET language")
        for statement in statements
    )


def test_missing_stored_language_is_persisted(monkeypatch):
    patch_password_functions(monkeypatch)

    connection = FakeConnection(user=make_user(language=""))

    result = postgres_login.authenticate_user(
        connection,
        "administrator",
        "correct-password",
        "administrator|127.0.0.1",
        selected_language="fr-FR",
    )

    assert result.authenticated is True
    assert result.language == "fr"

    language_updates = [
        params
        for statement, params in connection.calls
        if statement.startswith("UPDATE users SET language")
    ]

    assert language_updates == [("fr", 7)]


def test_language_alias_is_normalized(monkeypatch):
    patch_password_functions(monkeypatch)

    connection = FakeConnection(user=make_user(language=""))

    result = postgres_login.authenticate_user(
        connection,
        "administrator",
        "correct-password",
        "administrator|127.0.0.1",
        selected_language="en",
    )

    assert result.authenticated is True
    assert result.language == "en-US"


def test_invalid_languages_fall_back_to_german(monkeypatch):
    patch_password_functions(monkeypatch)

    connection = FakeConnection(user=make_user(language="invalid"))

    result = postgres_login.authenticate_user(
        connection,
        "administrator",
        "correct-password",
        "administrator|127.0.0.1",
        selected_language="not-a-supported-language",
    )

    assert result.authenticated is True
    assert result.language == "de"

    language_updates = [
        params
        for statement, params in connection.calls
        if statement.startswith("UPDATE users SET language")
    ]

    assert language_updates == [("de", 7)]


@pytest.mark.parametrize(
    "username,password,rate_limit_key",
    [
        (None, "password", "key"),
        ("invalid\x00username", "password", "key"),
        ("username", None, "key"),
        ("username", "password", ""),
    ],
)
def test_login_rejects_invalid_input_without_database_access(
    username,
    password,
    rate_limit_key,
):
    connection = FakeConnection()

    with pytest.raises(ValueError):
        postgres_login.authenticate_user(
            connection,
            username,
            password,
            rate_limit_key,
        )

    assert connection.calls == []
    assert connection.transaction_count == 0


def test_database_connection_is_not_left_in_transaction(monkeypatch):
    patch_password_functions(monkeypatch, valid=False)

    connection = FakeConnection(user=make_user())

    postgres_login.authenticate_user(
        connection,
        "administrator",
        "wrong-password",
        "administrator|127.0.0.1",
    )

    assert connection.info.transaction_status == TransactionStatus.IDLE
