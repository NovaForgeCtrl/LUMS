from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from server.soc.chrony_status import parse_chrony_status
from server.soc.chrony_sync_tracker import (
    ChronySyncTracker,
    ChronySyncTrackerError,
    ClockObservation,
)


UTC = timezone.utc

TRACKING_TEMPLATE = (
    "CFC5577C,time.cloudflare.com,4,"
    "{reference_time},"
    "0.000108656,0.000021184,0.000616593,"
    "25.752,0.011,0.668,0.018273009,0.000537179,"
    "64.4,Normal"
)

SOURCES = (
    "^,*,time.cloudflare.com,3,6,377,107,"
    "-0.000570636,-0.000549452,0.009808195\n"
    "^,+,nts.netnod.se,1,6,377,105,"
    "0.000300855,0.000300855,0.018632518\n"
)


def make_status(reference_time="1795254866.549786796"):
    tracking = TRACKING_TEMPLATE.format(
        reference_time=reference_time
    )
    return parse_chrony_status(tracking, SOURCES)


def observation(seconds: int, *, boot_base=10_000_000_000):
    return ClockObservation(
        utc=datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
        + timedelta(seconds=seconds),
        boottime_ns=boot_base + seconds * 1_000_000_000,
    )


def test_first_observation_only_establishes_baseline():
    tracker = ChronySyncTracker()

    result = tracker.observe(
        make_status(),
        observation(0),
    )

    assert result is None
    assert tracker.anchor is None


def test_same_reference_time_does_not_create_sync_anchor():
    tracker = ChronySyncTracker()
    status = make_status()

    assert tracker.observe(status, observation(0)) is None
    assert tracker.observe(status, observation(1)) is None
    assert tracker.anchor is None


def test_reference_advance_uses_previous_paired_observation():
    tracker = ChronySyncTracker()

    first = observation(0)
    second = observation(2)

    assert tracker.observe(make_status(), first) is None

    result = tracker.observe(
        make_status("1795254867.549786796"),
        second,
    )

    assert result is not None
    assert result.last_sync_utc == first.utc
    assert result.last_sync_boottime_ns == first.boottime_ns
    assert result.reference_time == Decimal("1795254867.549786796")
    assert result.reference_source == "time.cloudflare.com"
    assert result.source_id == (
        "time.cloudflare.com+nts.netnod.se"
    )
    assert result.detection_window == timedelta(seconds=2)


def test_same_reference_after_advance_preserves_original_anchor():
    tracker = ChronySyncTracker()

    first_status = make_status()
    advanced_status = make_status("1795254867.549786796")

    tracker.observe(first_status, observation(0))
    anchor = tracker.observe(advanced_status, observation(2))

    assert anchor is not None

    later = tracker.observe(
        advanced_status,
        observation(3),
    )

    assert later == anchor
    assert later.last_sync_boottime_ns == observation(0).boottime_ns


def test_next_reference_advance_moves_anchor_to_previous_observation():
    tracker = ChronySyncTracker()

    tracker.observe(make_status(), observation(0))
    tracker.observe(
        make_status("1795254867.549786796"),
        observation(1),
    )

    result = tracker.observe(
        make_status("1795254868.549786796"),
        observation(2),
    )

    assert result is not None
    assert result.last_sync_utc == observation(1).utc
    assert result.last_sync_boottime_ns == observation(1).boottime_ns


def test_reference_regression_invalidates_anchor_and_rebaselines():
    tracker = ChronySyncTracker()

    tracker.observe(make_status(), observation(0))
    tracker.observe(
        make_status("1795254867.549786796"),
        observation(1),
    )
    assert tracker.anchor is not None

    result = tracker.observe(
        make_status("1795254800.000000000"),
        observation(2),
    )

    assert result is None
    assert tracker.anchor is None


def test_after_reference_regression_new_advance_is_required():
    tracker = ChronySyncTracker()

    tracker.observe(make_status(), observation(0))
    tracker.observe(
        make_status("1795254867.549786796"),
        observation(1),
    )
    tracker.observe(
        make_status("1795254800.000000000"),
        observation(2),
    )

    result = tracker.observe(
        make_status("1795254801.000000000"),
        observation(3),
    )

    assert result is not None
    assert result.last_sync_boottime_ns == observation(2).boottime_ns


def test_reference_source_change_invalidates_anchor_and_rebaselines():
    tracker = ChronySyncTracker()

    tracker.observe(make_status(), observation(0))
    tracker.observe(
        make_status("1795254867.549786796"),
        observation(1),
    )
    assert tracker.anchor is not None

    netnod_tracking = TRACKING_TEMPLATE.format(
        reference_time="1795254868.549786796"
    ).replace(
        "CFC5577C,time.cloudflare.com,4,",
        "A28FBE10,nts.netnod.se,1,",
        1,
    )
    netnod_sources = "\n".join(
        (
            "^,+,time.cloudflare.com,3,6,377,107,"
            "-0.000570636,-0.000549452,0.009808195",
            "^,*,nts.netnod.se,1,6,377,105,"
            "0.000300855,0.000300855,0.018632518",
        )
    ) + "\n"
    changed_status = parse_chrony_status(
        netnod_tracking,
        netnod_sources,
    )

    result = tracker.observe(changed_status, observation(2))

    assert result is None
    assert tracker.anchor is None

    next_status = parse_chrony_status(
        netnod_tracking.replace(
            "1795254868.549786796",
            "1795254869.549786796",
        ),
        netnod_sources,
    )
    result = tracker.observe(next_status, observation(3))

    assert result is not None
    assert result.reference_source == "nts.netnod.se"
    assert result.last_sync_boottime_ns == observation(2).boottime_ns


def test_source_group_change_invalidates_anchor_and_rebaselines():
    tracker = ChronySyncTracker()

    tracker.observe(make_status(), observation(0))
    tracker.observe(
        make_status("1795254867.549786796"),
        observation(1),
    )
    assert tracker.anchor is not None

    changed_status = replace(
        make_status("1795254868.549786796"),
        source_id="time.cloudflare.com",
    )

    result = tracker.observe(changed_status, observation(2))

    assert result is None
    assert tracker.anchor is None


def test_wall_clock_rollback_invalidates_anchor():
    tracker = ChronySyncTracker()

    tracker.observe(make_status(), observation(0))
    tracker.observe(
        make_status("1795254867.549786796"),
        observation(1),
    )
    assert tracker.anchor is not None

    rollback = ClockObservation(
        utc=observation(1).utc - timedelta(seconds=2),
        boottime_ns=observation(2).boottime_ns,
    )

    result = tracker.observe(
        make_status("1795254868.549786796"),
        rollback,
    )

    assert result is None
    assert tracker.anchor is None


def test_wall_boottime_divergence_invalidates_anchor():
    tracker = ChronySyncTracker()

    tracker.observe(make_status(), observation(0))
    tracker.observe(
        make_status("1795254867.549786796"),
        observation(1),
    )
    assert tracker.anchor is not None

    divergent = ClockObservation(
        utc=observation(2).utc + timedelta(seconds=1),
        boottime_ns=observation(2).boottime_ns,
    )

    result = tracker.observe(
        make_status("1795254868.549786796"),
        divergent,
    )

    assert result is None
    assert tracker.anchor is None


def test_non_increasing_boottime_invalidates_anchor():
    tracker = ChronySyncTracker()

    first = observation(0)
    tracker.observe(make_status(), first)
    tracker.observe(
        make_status("1795254867.549786796"),
        observation(1),
    )
    assert tracker.anchor is not None

    repeated_boot = ClockObservation(
        utc=observation(2).utc,
        boottime_ns=observation(1).boottime_ns,
    )

    result = tracker.observe(
        make_status("1795254868.549786796"),
        repeated_boot,
    )

    assert result is None
    assert tracker.anchor is None


def test_detection_after_long_pause_keeps_earlier_anchor():
    tracker = ChronySyncTracker()

    first = observation(0)
    tracker.observe(make_status(), first)

    result = tracker.observe(
        make_status("1795254867.549786796"),
        observation(240),
    )

    assert result is not None
    assert result.last_sync_boottime_ns == first.boottime_ns
    assert result.detection_window == timedelta(seconds=240)


def test_invalidate_discards_baseline_and_anchor():
    tracker = ChronySyncTracker()

    tracker.observe(make_status(), observation(0))
    tracker.observe(
        make_status("1795254867.549786796"),
        observation(1),
    )
    assert tracker.anchor is not None

    tracker.invalidate()

    assert tracker.anchor is None
    assert tracker.observe(
        make_status("1795254867.549786796"),
        observation(2),
    ) is None


def test_rejects_non_chrony_status():
    tracker = ChronySyncTracker()

    with pytest.raises(ChronySyncTrackerError, match="invalid type"):
        tracker.observe(object(), observation(0))


@pytest.mark.parametrize(
    "invalid",
    [
        ClockObservation(
            utc=datetime(2026, 11, 21, 9, 0),
            boottime_ns=1,
        ),
        ClockObservation(
            utc=observation(0).utc,
            boottime_ns=True,
        ),
        ClockObservation(
            utc=observation(0).utc,
            boottime_ns=-1,
        ),
    ],
)
def test_rejects_invalid_clock_observations(invalid):
    tracker = ChronySyncTracker()

    with pytest.raises(ChronySyncTrackerError):
        tracker.observe(make_status(), invalid)


def test_capture_clock_observation_returns_aware_utc_and_boottime():
    from server.soc.chrony_sync_tracker import capture_clock_observation

    result = capture_clock_observation()

    assert result.utc.tzinfo is not None
    assert result.utc.utcoffset() == timedelta(0)
    assert type(result.boottime_ns) is int
    assert result.boottime_ns > 0
