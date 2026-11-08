"""Safety helpers for PostgreSQL integration tests."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

import pytest
from psycopg.conninfo import conninfo_to_dict


class UnsafePostgresTestDatabaseURL(ValueError):
    """Raised when the integration-test URL targets an unexpected server."""


_ALLOWED_PARAMETERS = {
    "host",
    "port",
    "dbname",
    "user",
    "password",
}

def run_cleanup(
    *actions: tuple[str, Callable[[], object]],
) -> None:
    """Run every cleanup action without masking an active exception.

    When an exception is already propagating, cleanup failures are
    attached as exception notes and the original exception is preserved.

    Without an active exception, the first cleanup failure is raised
    after all actions have been attempted. Further failures are attached
    as notes to that first exception.
    """
    cleanup_errors: list[tuple[str, BaseException]] = []

    for description, action in actions:
        try:
            action()
        except BaseException as exc:
            cleanup_errors.append((description, exc))

    if not cleanup_errors:
        return

    active_exception = sys.exc_info()[1]

    if active_exception is not None:
        for description, error in cleanup_errors:
            active_exception.add_note(
                f"Cleanup failed ({description}): "
                f"{type(error).__name__}: {error}"
            )
        return

    description, primary_error = cleanup_errors[0]

    for additional_description, error in cleanup_errors[1:]:
        primary_error.add_note(
            f"Additional cleanup failure ({additional_description}): "
            f"{type(error).__name__}: {error}"
        )

    primary_error.add_note(
        f"Primary cleanup failure: {description}"
    )
    raise primary_error.with_traceback(primary_error.__traceback__)


def validate_test_database_url(database_url: str) -> str:
    """Accept only the dedicated local PostgreSQL integration endpoint.

    Credentials and supplied connection strings are never included
    in validation error messages.
    """
    if not isinstance(database_url, str) or not database_url.strip():
        raise UnsafePostgresTestDatabaseURL(
            "The PostgreSQL integration-test URL is empty."
        )

    if any(
        name.startswith("PG") and value
        for name, value in os.environ.items()
    ):
        raise UnsafePostgresTestDatabaseURL(
            "Refusing PostgreSQL integration tests: "
            "PostgreSQL-related environment variables must be unset."
        )

    try:
        parameters = conninfo_to_dict(database_url)
    except Exception:
        raise UnsafePostgresTestDatabaseURL(
            "The PostgreSQL integration-test URL is invalid."
        ) from None

    unexpected_parameters = set(parameters) - _ALLOWED_PARAMETERS

    if unexpected_parameters:
        raise UnsafePostgresTestDatabaseURL(
            "Refusing PostgreSQL integration tests: "
            "the connection string contains unsupported parameters."
        )

    expected = {
        "host": "127.0.0.1",
        "port": "55439",
        "dbname": "lums_integration",
        "user": "lums_pg_bootstrap",
    }

    mismatches = [
        key
        for key, expected_value in expected.items()
        if parameters.get(key) != expected_value
    ]

    if mismatches:
        raise UnsafePostgresTestDatabaseURL(
            "Refusing PostgreSQL integration tests: the connection "
            "must target 127.0.0.1:55439, database lums_integration, "
            "user lums_pg_bootstrap."
        )

    if not parameters.get("password"):
        raise UnsafePostgresTestDatabaseURL(
            "Refusing PostgreSQL integration tests: "
            "an explicit password is required."
        )

    return database_url


def require_test_database_url() -> str:
    """Return a validated test URL or skip when none was configured."""
    database_url = os.environ.get("LUMS_TEST_DATABASE_URL")

    if not database_url:
        pytest.skip("LUMS_TEST_DATABASE_URL is not configured")

    return validate_test_database_url(database_url)


__all__ = [
    "UnsafePostgresTestDatabaseURL",
    "require_test_database_url",
    "run_cleanup",
    "validate_test_database_url",
]
