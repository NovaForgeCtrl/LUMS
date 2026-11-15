"""Pure unit tests for PostgreSQL SOC collector input normalization."""

import hashlib
import json

import pytest

from server.soc.postgres_collector_store import (
    PostgresCollectorStore,
    _normalize_payloads,
)


def test_payload_normalization_is_canonical_and_unicode_safe():
    first = {
        "event_id": "linux01:boot:1",
        "message": "Grüße aus Köln",
        "nested": {"z": 2, "a": 1},
    }
    replay = {
        "nested": {"a": 1, "z": 2},
        "message": "Grüße aus Köln",
        "event_id": "linux01:boot:1",
    }

    normalized = _normalize_payloads([first])
    replayed = _normalize_payloads([replay])

    expected_json = json.dumps(
        first,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    assert normalized == replayed
    assert normalized[0][0] == "linux01:boot:1"
    assert normalized[0][1] == expected_json
    assert normalized[0][2] == hashlib.sha256(
        expected_json.encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize(
    "payloads",
    [
        "not-a-batch",
        b"not-a-batch",
        {"event_id": "single-mapping"},
        [None],
        [{"event_id": ""}],
        [{"event_id": "invalid id"}],
        [{"event_id": "duplicate"}, {"event_id": "duplicate"}],
        [{"event_id": "nan", "value": float("nan")}],
        [{"event_id": "infinity", "value": float("inf")}],
    ],
)
def test_payload_normalization_rejects_invalid_batches(payloads):
    with pytest.raises(ValueError):
        _normalize_payloads(payloads)


def test_payload_normalization_rejects_oversized_event():
    payload = {
        "event_id": "linux01:large:1",
        "data": "x" * (64 * 1024),
    }

    with pytest.raises(ValueError, match="maximum encoded size"):
        _normalize_payloads([payload])


def test_payload_normalization_accepts_empty_batch():
    assert _normalize_payloads([]) == ()


@pytest.mark.parametrize(
    ("limit", "max_attempts", "stale_after_seconds"),
    [
        (0, 5, 300),
        (501, 5, 300),
        (1, 0, 300),
        (1, 101, 300),
        (1, 5, 0),
        (1, 5, 86401),
        (True, 5, 300),
        (1, False, 300),
        (1, 5, True),
    ],
)
def test_worker_limits_reject_invalid_values(
    limit,
    max_attempts,
    stale_after_seconds,
):
    with pytest.raises(ValueError):
        PostgresCollectorStore._validate_worker_limits(
            limit=limit,
            max_attempts=max_attempts,
            stale_after_seconds=stale_after_seconds,
        )
