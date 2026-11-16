from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from server.soc.trusted_time import (
    TrustedTimeError,
    TrustedTimePolicy,
    TrustedTimeSnapshot,
    read_trusted_time,
    validate_trusted_time,
)


UTC = timezone.utc
NOW = datetime(2026, 11, 1, 16, 0, tzinfo=UTC)

PROCESS_START_NS = 1_000_000_000
LAST_SYNC_NS = 2_000_000_000
OBSERVED_NS = 3_000_000_000


@pytest.fixture
def policy():
    return TrustedTimePolicy(
        approved_sources=frozenset({"ntp.example.internal"}),
        max_sync_age=timedelta(minutes=10),
        max_offset=timedelta(milliseconds=100),
        max_uncertainty=timedelta(milliseconds=50),
        clock_consistency_tolerance=timedelta(milliseconds=100),
    )


@pytest.fixture
def snapshot():
    return TrustedTimeSnapshot(
        synchronized=True,
        authenticated=True,
        source_id="ntp.example.internal",
        last_sync_utc=NOW - timedelta(seconds=1),
        last_sync_boottime_ns=LAST_SYNC_NS,
        observed_utc=NOW,
        observed_boottime_ns=OBSERVED_NS,
        offset=timedelta(milliseconds=2),
        uncertainty=timedelta(milliseconds=3),
    )


def validate(snapshot, policy):
    return validate_trusted_time(
        snapshot,
        policy,
        process_started_boottime_ns=PROCESS_START_NS,
    )


def test_accepts_complete_authenticated_approved_time(snapshot, policy):
    result = validate(snapshot, policy)

    assert result.utc_now == NOW
    assert result.boottime_ns == OBSERVED_NS
    assert result.source_id == "ntp.example.internal"
    assert result.sync_age == timedelta(seconds=1)


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"synchronized": False}, "not confirmed"),
        ({"authenticated": False}, "not authenticated"),
        ({"source_id": "unapproved.example"}, "not approved"),
        ({"source_id": ""}, "identity is missing"),
        ({"last_sync_utc": None}, "last_sync_utc"),
        ({"observed_utc": None}, "observed_utc"),
        ({"last_sync_boottime_ns": None}, "last_sync_boottime_ns"),
        ({"observed_boottime_ns": None}, "observed_boottime_ns"),
        ({"offset": None}, "offset"),
        ({"uncertainty": None}, "uncertainty"),
    ],
)
def test_rejects_incomplete_or_untrusted_status(
    snapshot,
    policy,
    changes,
    message,
):
    with pytest.raises(TrustedTimeError, match=message):
        validate(replace(snapshot, **changes), policy)


def test_rejects_sync_before_process_start(snapshot, policy):
    stale = replace(
        snapshot,
        last_sync_boottime_ns=PROCESS_START_NS - 1,
    )

    with pytest.raises(TrustedTimeError, match="after process start"):
        validate(stale, policy)


def test_rejects_observation_before_last_sync(snapshot, policy):
    stale = replace(
        snapshot,
        observed_boottime_ns=LAST_SYNC_NS - 1,
    )

    with pytest.raises(TrustedTimeError, match="precedes"):
        validate(stale, policy)


def test_rejects_sync_older_than_policy(snapshot, policy):
    old = replace(
        snapshot,
        last_sync_boottime_ns=LAST_SYNC_NS,
        observed_boottime_ns=LAST_SYNC_NS + 700_000_000_000,
        last_sync_utc=NOW - timedelta(minutes=12),
    )

    with pytest.raises(TrustedTimeError, match="too old"):
        validate(old, policy)


def test_rejects_offset_above_limit(snapshot, policy):
    invalid = replace(
        snapshot,
        offset=timedelta(milliseconds=101),
    )

    with pytest.raises(TrustedTimeError, match="offset exceeds"):
        validate(invalid, policy)


def test_rejects_uncertainty_above_limit(snapshot, policy):
    invalid = replace(
        snapshot,
        uncertainty=timedelta(milliseconds=51),
    )

    with pytest.raises(TrustedTimeError, match="uncertainty exceeds"):
        validate(invalid, policy)


def test_rejects_negative_uncertainty(snapshot, policy):
    invalid = replace(
        snapshot,
        uncertainty=timedelta(seconds=-1),
    )

    with pytest.raises(TrustedTimeError, match="must not be negative"):
        validate(invalid, policy)


def test_rejects_wall_clock_rollback(snapshot, policy):
    invalid = replace(
        snapshot,
        observed_utc=NOW - timedelta(seconds=2),
    )

    with pytest.raises(TrustedTimeError, match="moved backwards"):
        validate(invalid, policy)


def test_rejects_wall_and_boottime_inconsistency(snapshot, policy):
    invalid = replace(
        snapshot,
        observed_utc=NOW + timedelta(seconds=1),
    )

    with pytest.raises(TrustedTimeError, match="inconsistent"):
        validate(invalid, policy)


def test_rejects_boolean_as_boottime(snapshot, policy):
    invalid = replace(snapshot, observed_boottime_ns=True)

    with pytest.raises(TrustedTimeError, match="observed_boottime_ns"):
        validate(invalid, policy)


def test_policy_requires_explicit_approved_source():
    with pytest.raises(ValueError, match="must not be empty"):
        TrustedTimePolicy(
            approved_sources=frozenset(),
            max_sync_age=timedelta(minutes=1),
            max_offset=timedelta(milliseconds=10),
            max_uncertainty=timedelta(milliseconds=10),
            clock_consistency_tolerance=timedelta(milliseconds=10),
        )


def test_policy_rejects_non_positive_limits():
    with pytest.raises(ValueError, match="max_sync_age"):
        TrustedTimePolicy(
            approved_sources=frozenset({"ntp.example.internal"}),
            max_sync_age=timedelta(0),
            max_offset=timedelta(milliseconds=10),
            max_uncertainty=timedelta(milliseconds=10),
            clock_consistency_tolerance=timedelta(milliseconds=10),
        )


def test_policy_rejects_negative_clock_tolerance():
    with pytest.raises(ValueError, match="must not be negative"):
        TrustedTimePolicy(
            approved_sources=frozenset({"ntp.example.internal"}),
            max_sync_age=timedelta(minutes=1),
            max_offset=timedelta(milliseconds=10),
            max_uncertainty=timedelta(milliseconds=10),
            clock_consistency_tolerance=timedelta(seconds=-1),
        )


def test_rejects_sync_at_exact_process_start(snapshot, policy):
    same_time = replace(
        snapshot,
        last_sync_boottime_ns=PROCESS_START_NS,
    )

    with pytest.raises(TrustedTimeError, match="after process start"):
        validate(same_time, policy)


def test_sync_age_rounds_fractional_microseconds_up(snapshot, policy):
    fractional = replace(
        snapshot,
        last_sync_boottime_ns=LAST_SYNC_NS,
        observed_boottime_ns=LAST_SYNC_NS + 1_001,
        last_sync_utc=NOW - timedelta(microseconds=1),
        observed_utc=NOW,
    )

    result = validate(fractional, policy)

    assert result.sync_age == timedelta(microseconds=2)





class StaticTimeProvider:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def get_snapshot(self):
        return self.snapshot


class FailingTimeProvider:
    def get_snapshot(self):
        raise OSError("simulated time service failure")


def test_read_trusted_time_accepts_valid_provider(snapshot, policy):
    provider = StaticTimeProvider(snapshot)

    result = read_trusted_time(
        provider,
        policy,
        process_started_boottime_ns=PROCESS_START_NS,
    )

    assert result.utc_now == NOW
    assert result.source_id == "ntp.example.internal"


@pytest.mark.parametrize("provider", [None, object()])
def test_read_trusted_time_rejects_missing_provider(provider, policy):
    with pytest.raises(TrustedTimeError, match="provider is unavailable"):
        read_trusted_time(
            provider,
            policy,
            process_started_boottime_ns=PROCESS_START_NS,
        )


def test_read_trusted_time_fails_closed_on_provider_exception(policy):
    with pytest.raises(
        TrustedTimeError,
        match="provider could not be queried",
    ):
        read_trusted_time(
            FailingTimeProvider(),
            policy,
            process_started_boottime_ns=PROCESS_START_NS,
        )


def test_read_trusted_time_rejects_invalid_provider_snapshot(policy):
    provider = StaticTimeProvider({"synchronized": True})

    with pytest.raises(
        TrustedTimeError,
        match="invalid snapshot",
    ):
        read_trusted_time(
            provider,
            policy,
            process_started_boottime_ns=PROCESS_START_NS,
        )


def test_rejects_datetime_elapsed_overflow(snapshot, policy):
    invalid = replace(
        snapshot,
        last_sync_utc=datetime.min.replace(tzinfo=UTC),
        observed_utc=datetime.max.replace(tzinfo=UTC),
        last_sync_boottime_ns=LAST_SYNC_NS,
        observed_boottime_ns=OBSERVED_NS,
    )

    with pytest.raises(TrustedTimeError):
        validate(invalid, policy)


def test_rejects_extreme_negative_offset(snapshot, policy):
    invalid = replace(
        snapshot,
        offset=timedelta.min,
    )

    with pytest.raises(TrustedTimeError):
        validate(invalid, policy)


def test_rejects_extreme_uncertainty(snapshot, policy):
    invalid = replace(
        snapshot,
        uncertainty=timedelta.max,
    )

    with pytest.raises(TrustedTimeError, match="uncertainty exceeds"):
        validate(invalid, policy)
