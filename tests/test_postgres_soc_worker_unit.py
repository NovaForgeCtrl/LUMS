"""Unit tests for the PostgreSQL SOC worker preflight and limits."""

import pytest

from server.soc.postgres_worker import (
    PostgresSOCWorker,
    validate_postgres_worker_schema,
)
from server.soc.rule_catalog import load_catalog_data
from server.soc.worker import SOCWorkerError


EMPTY_CATALOG = load_catalog_data({"version": 1, "rules": []})


def test_worker_rejects_non_psycopg_connection():
    with pytest.raises(TypeError, match="psycopg.Connection"):
        PostgresSOCWorker(object(), EMPTY_CATALOG)


def test_schema_validator_rejects_non_psycopg_connection():
    with pytest.raises(TypeError, match="psycopg.Connection"):
        validate_postgres_worker_schema(object())


@pytest.mark.parametrize(
    ("batch_size", "max_attempts", "stale", "history"),
    [
        (0, 5, 300, 5000),
        (501, 5, 300, 5000),
        (1, 0, 300, 5000),
        (1, 101, 300, 5000),
        (1, 5, 0, 5000),
        (1, 5, 86401, 5000),
        (1, 5, 300, 0),
        (1, 5, 300, 50001),
        (True, 5, 300, 5000),
        (1, False, 300, 5000),
        (1, 5, True, 5000),
        (1, 5, 300, True),
    ],
)
def test_worker_limits_reject_invalid_values(
    batch_size,
    max_attempts,
    stale,
    history,
):
    # The constructor validates connection/schema first. The pure bounds
    # are also exercised by constructing the same validator through a tiny
    # connection-free object.
    for name, value, low, high in (
        ("batch_size", batch_size, 1, 500),
        ("max_attempts", max_attempts, 1, 100),
        ("stale_after_seconds", stale, 1, 86400),
        ("history_limit", history, 1, 50000),
    ):
        invalid = (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not low <= value <= high
        )
        if invalid:
            with pytest.raises(ValueError):
                PostgresSOCWorker._validate_limit(
                    name, value, low, high
                )
            break


def test_worker_limit_validator_rejects_bool():
    with pytest.raises(ValueError):
        PostgresSOCWorker._validate_limit(
            "batch_size", True, 1, 500
        )


def test_worker_limit_validator_accepts_boundaries():
    PostgresSOCWorker._validate_limit("batch_size", 1, 1, 500)
    PostgresSOCWorker._validate_limit("batch_size", 500, 1, 500)
