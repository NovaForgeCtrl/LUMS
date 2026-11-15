"""Pure unit tests for PostgreSQL SOC incident timestamp handling."""

from datetime import datetime, timezone

import pytest

from server.soc.postgres_incident_store import (
    PostgresIncidentStore,
    _timestamp_from_database,
    _timestamp_to_datetime,
)


def test_timestamp_input_is_normalized_to_utc():
    value = _timestamp_to_datetime(
        "2026-10-28T12:00:00+03:00",
        "created_at",
    )

    assert value == datetime(
        2026, 10, 28, 9, 0, tzinfo=timezone.utc
    )


def test_timestamp_input_accepts_z_suffix():
    value = _timestamp_to_datetime(
        "2026-10-28T09:00:00Z",
        "created_at",
    )

    assert value == datetime(
        2026, 10, 28, 9, 0, tzinfo=timezone.utc
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        123,
        True,
        "2026-10-28T09:00:00",
        "not-a-timestamp",
    ],
)
def test_timestamp_input_rejects_invalid_or_naive_values(value):
    with pytest.raises(ValueError, match="timezone-aware ISO timestamp"):
        _timestamp_to_datetime(value, "created_at")


def test_database_timestamp_is_returned_as_utc_iso():
    value = datetime.fromisoformat("2026-10-28T12:00:00+03:00")

    assert _timestamp_from_database(value, "created_at") == (
        "2026-10-28T09:00:00+00:00"
    )


@pytest.mark.parametrize(
    "value",
    [
        "2026-10-28T09:00:00",
        "not-a-datetime",
        None,
    ],
)
def test_database_timestamp_rejects_invalid_values(value):
    with pytest.raises(Exception):
        _timestamp_from_database(value, "created_at")


def test_constructor_rejects_non_psycopg_connection():
    with pytest.raises(TypeError, match="psycopg.Connection"):
        PostgresIncidentStore(object())
