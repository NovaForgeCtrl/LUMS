"""Unit tests for PostgreSQL integration-test safety helpers."""

import os

import pytest

from postgres_test_support import (
    UnsafePostgresTestDatabaseURL,
    require_test_database_url,
    run_cleanup,
    validate_test_database_url,
)


VALID_URL = (
    "postgresql://lums_pg_bootstrap:test-secret"
    "@127.0.0.1:55439/lums_integration"
)

UNSAFE_ENVIRONMENT_VARIABLES = [
    "PGHOST",
    "PGHOSTADDR",
    "PGPORT",
    "PGDATABASE",
    "PGUSER",
    "PGPASSWORD",
    "PGPASSFILE",
    "PGSERVICE",
    "PGSERVICEFILE",
    "PGOPTIONS",
    "PGTARGETSESSIONATTRS",
    "PGLOADBALANCEHOSTS",
]


def _clear_libpq_environment(monkeypatch):
    for name in UNSAFE_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_accepts_exact_dedicated_local_endpoint(monkeypatch):
    _clear_libpq_environment(monkeypatch)

    assert validate_test_database_url(VALID_URL) == VALID_URL


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://lums_pg_bootstrap:secret@localhost:55439/lums_integration",
        "postgresql://lums_pg_bootstrap:secret@192.168.2.100:55439/lums_integration",
        "postgresql://lums_pg_bootstrap:secret@127.0.0.1:5432/lums_integration",
        "postgresql://lums_pg_bootstrap:secret@127.0.0.1:55439/postgres",
        "postgresql://other_user:secret@127.0.0.1:55439/lums_integration",
        "postgresql://lums_pg_bootstrap:secret@127.0.0.1/lums_integration",
        "postgresql://lums_pg_bootstrap:secret@127.0.0.1:55439/lums_integration?hostaddr=192.168.2.100",
        "postgresql://lums_pg_bootstrap:secret@127.0.0.1:55439/lums_integration?service=production",
    ],
)
def test_rejects_unexpected_connection_targets(url, monkeypatch):
    _clear_libpq_environment(monkeypatch)

    with pytest.raises(UnsafePostgresTestDatabaseURL):
        validate_test_database_url(url)


@pytest.mark.parametrize(
    "parameter",
    [
        "options=-csearch_path%3Dpublic",
        "sslmode=disable",
        "application_name=unexpected",
        "connect_timeout=1",
        "target_session_attrs=read-write",
        "channel_binding=disable",
        "unknown_parameter=value",
    ],
)
def test_rejects_additional_connection_parameters(parameter, monkeypatch):
    _clear_libpq_environment(monkeypatch)

    url = f"{VALID_URL}?{parameter}"

    with pytest.raises(UnsafePostgresTestDatabaseURL):
        validate_test_database_url(url)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not a valid connection string",
    ],
)
def test_rejects_empty_or_invalid_connection_strings(value, monkeypatch):
    _clear_libpq_environment(monkeypatch)

    with pytest.raises(UnsafePostgresTestDatabaseURL):
        validate_test_database_url(value)


def test_rejects_missing_password(monkeypatch):
    _clear_libpq_environment(monkeypatch)

    url = "postgresql://lums_pg_bootstrap@127.0.0.1:55439/lums_integration"

    with pytest.raises(UnsafePostgresTestDatabaseURL):
        validate_test_database_url(url)


def test_error_does_not_disclose_connection_credentials(monkeypatch):
    _clear_libpq_environment(monkeypatch)

    secret_url = (
        "postgresql://lums_pg_bootstrap:very-secret"
        "@192.168.2.100:55439/lums_integration"
    )

    with pytest.raises(UnsafePostgresTestDatabaseURL) as error:
        validate_test_database_url(secret_url)

    assert "very-secret" not in str(error.value)
    assert secret_url not in str(error.value)


def test_require_url_skips_when_environment_variable_is_missing(monkeypatch):
    _clear_libpq_environment(monkeypatch)
    monkeypatch.delenv("LUMS_TEST_DATABASE_URL", raising=False)

    with pytest.raises(pytest.skip.Exception):
        require_test_database_url()


def test_require_url_validates_environment_variable(monkeypatch):
    _clear_libpq_environment(monkeypatch)
    monkeypatch.setenv("LUMS_TEST_DATABASE_URL", VALID_URL)

    assert require_test_database_url() == VALID_URL


def test_require_url_rejects_wrong_environment_target(monkeypatch):
    _clear_libpq_environment(monkeypatch)
    monkeypatch.setenv(
        "LUMS_TEST_DATABASE_URL",
        "postgresql://user:secret@192.168.2.100:55439/lums_integration",
    )

    with pytest.raises(UnsafePostgresTestDatabaseURL):
        require_test_database_url()


@pytest.mark.parametrize("variable", UNSAFE_ENVIRONMENT_VARIABLES)
def test_rejects_libpq_environment_overrides(monkeypatch, variable):
    _clear_libpq_environment(monkeypatch)
    monkeypatch.setenv(variable, "unexpected-override")

    with pytest.raises(UnsafePostgresTestDatabaseURL):
        validate_test_database_url(VALID_URL)


def test_run_cleanup_attempts_every_action_and_reports_all_failures():
    calls = []
    first_error = RuntimeError("first cleanup failed")
    second_error = ValueError("second cleanup failed")

    def fail(error):
        raise error

    def first_action():
        calls.append("first")
        fail(first_error)

    def successful_action():
        calls.append("successful")

    def second_action():
        calls.append("second")
        fail(second_error)

    with pytest.raises(RuntimeError, match="first cleanup failed") as captured:
        run_cleanup(
            ("first action", first_action),
            ("successful action", successful_action),
            ("second action", second_action),
        )

    assert calls == ["first", "successful", "second"]
    notes = getattr(captured.value, "__notes__", [])
    assert any("second cleanup failed" in note for note in notes)
    assert any("Primary cleanup failure: first action" in note for note in notes)


def test_run_cleanup_preserves_active_exception_and_adds_cleanup_notes():
    first_cleanup_error = RuntimeError("first cleanup failed")
    second_cleanup_error = ValueError("second cleanup failed")
    calls = []

    def fail(error):
        raise error

    def first_action():
        calls.append("first")
        fail(first_cleanup_error)

    def second_action():
        calls.append("second")
        fail(second_cleanup_error)

    with pytest.raises(LookupError, match="original test failure") as captured:
        try:
            raise LookupError("original test failure")
        except LookupError:
            run_cleanup(
                ("first action", first_action),
                ("second action", second_action),
            )
            raise

    assert calls == ["first", "second"]
    notes = getattr(captured.value, "__notes__", [])
    assert any("first cleanup failed" in note for note in notes)
    assert any("second cleanup failed" in note for note in notes)


def test_run_cleanup_completes_successful_actions_in_order():
    calls = []

    run_cleanup(
        ("first action", lambda: calls.append("first")),
        ("second action", lambda: calls.append("second")),
    )

    assert calls == ["first", "second"]


def _clear_all_postgres_environment(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith("PG"):
            monkeypatch.delenv(name, raising=False)


def test_rejects_unlisted_postgres_environment_override(monkeypatch):
    _clear_all_postgres_environment(monkeypatch)
    monkeypatch.setenv("PGAPPNAME", "unexpected-override")

    with pytest.raises(UnsafePostgresTestDatabaseURL):
        validate_test_database_url(VALID_URL)


def test_ignores_empty_postgres_prefixed_environment_variable(monkeypatch):
    _clear_all_postgres_environment(monkeypatch)
    monkeypatch.setenv("PGAPPNAME", "")

    assert validate_test_database_url(VALID_URL) == VALID_URL
