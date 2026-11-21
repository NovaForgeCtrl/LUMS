"""Conservative BOOTTIME anchoring for observed Chrony reference updates.

Chrony's tracking Ref time is a UTC timestamp, not a Linux BOOTTIME value.

This tracker never converts that UTC timestamp into BOOTTIME. It observes
a previous Chrony reference value and a paired UTC/BOOTTIME observation.
When a later reference value is observed, that previous observation becomes
a conservative lower-bound anchor: the reference update must have happened
after it.

This deliberately overestimates synchronization age. After tracker restart,
reference-time regression, or clock inconsistency, a new reference-time
advance must be observed before an anchor is returned.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from server.soc.chrony_status import ChronyStatus


UTC = timezone.utc
_NS_PER_SECOND = 1_000_000_000
_NS_PER_MICROSECOND = 1_000


class ChronySyncTrackerError(RuntimeError):
    """Raised when a reliable Chrony sync observation cannot be made."""


@dataclass(frozen=True)
class ClockObservation:
    """A paired wall-clock and CLOCK_BOOTTIME observation."""

    utc: datetime
    boottime_ns: int


@dataclass(frozen=True)
class ChronySyncAnchor:
    """Conservative lower-bound anchor preceding a newer Chrony Ref time."""

    last_sync_utc: datetime
    last_sync_boottime_ns: int
    reference_time: Decimal
    reference_source: str
    source_id: str
    detection_window: timedelta


def _duration_ns(value: timedelta) -> int:
    return (
        (value.days * 86_400 + value.seconds) * _NS_PER_SECOND
        + value.microseconds * _NS_PER_MICROSECOND
    )


def capture_clock_observation() -> ClockObservation:
    """Capture UTC and BOOTTIME as closely paired as possible."""
    clock_id = getattr(time, "CLOCK_BOOTTIME", None)
    if clock_id is None:
        raise ChronySyncTrackerError("CLOCK_BOOTTIME is unavailable")

    try:
        boot_before = time.clock_gettime_ns(clock_id)
        wall = datetime.now(UTC)
        boot_after = time.clock_gettime_ns(clock_id)
    except (OSError, OverflowError, ValueError) as exc:
        raise ChronySyncTrackerError(
            "paired UTC/BOOTTIME observation failed"
        ) from exc

    if (
        type(boot_before) is not int
        or type(boot_after) is not int
        or boot_before < 0
        or boot_after < boot_before
    ):
        raise ChronySyncTrackerError(
            "CLOCK_BOOTTIME returned an invalid observation"
        )

    # UTC was sampled between these two BOOTTIME readings. The midpoint
    # minimises the maximum pairing error without using wall-clock arithmetic.
    midpoint = boot_before + (boot_after - boot_before) // 2

    return ClockObservation(
        utc=wall,
        boottime_ns=midpoint,
    )


class ChronySyncTracker:
    """Track reference-time advances and retain conservative BOOTTIME anchors.

    The first valid observation only establishes a baseline. An anchor is
    returned only after a strictly newer Chrony Ref time is observed.

    If an observation pair is inconsistent, or the Ref time moves backwards,
    the prior anchor is discarded and the current observation becomes a new
    baseline. No stale anchor survives these conditions.
    """

    def __init__(
        self,
        *,
        clock_consistency_tolerance: timedelta = timedelta(milliseconds=100),
    ) -> None:
        if (
            not isinstance(clock_consistency_tolerance, timedelta)
            or clock_consistency_tolerance < timedelta(0)
        ):
            raise ValueError(
                "clock_consistency_tolerance must be non-negative"
            )

        self._tolerance_ns = _duration_ns(
            clock_consistency_tolerance
        )
        self._previous_reference_time: Decimal | None = None
        self._previous_observation: ClockObservation | None = None
        self._previous_source_id: str | None = None
        self._previous_reference_source: str | None = None
        self._anchor: ChronySyncAnchor | None = None

    @property
    def anchor(self) -> ChronySyncAnchor | None:
        return self._anchor

    def _set_baseline(
        self,
        status: ChronyStatus,
        observation: ClockObservation,
        reference_time: Decimal,
    ) -> None:
        self._previous_observation = observation
        self._previous_reference_time = reference_time
        self._previous_source_id = status.source_id
        self._previous_reference_source = (
            status.tracking.reference_address
        )
        self._anchor = None

    def invalidate(self) -> None:
        """Discard all history after a provider or monitor failure."""
        self._previous_reference_time = None
        self._previous_observation = None
        self._previous_source_id = None
        self._previous_reference_source = None
        self._anchor = None

    @staticmethod
    def _normalise_observation(
        observation: ClockObservation,
    ) -> ClockObservation:
        if not isinstance(observation, ClockObservation):
            raise ChronySyncTrackerError(
                "clock observation has an invalid type"
            )

        if (
            not isinstance(observation.utc, datetime)
            or observation.utc.tzinfo is None
            or observation.utc.utcoffset() is None
        ):
            raise ChronySyncTrackerError(
                "clock observation UTC must be timezone-aware"
            )

        if (
            type(observation.boottime_ns) is not int
            or observation.boottime_ns < 0
        ):
            raise ChronySyncTrackerError(
                "clock observation BOOTTIME is invalid"
            )

        try:
            utc = observation.utc.astimezone(UTC)
        except (OverflowError, ValueError) as exc:
            raise ChronySyncTrackerError(
                "clock observation UTC cannot be normalised"
            ) from exc

        return ClockObservation(
            utc=utc,
            boottime_ns=observation.boottime_ns,
        )

    def _observation_interval_is_consistent(
        self,
        previous: ClockObservation,
        current: ClockObservation,
    ) -> tuple[bool, int]:
        boot_elapsed = current.boottime_ns - previous.boottime_ns

        if boot_elapsed <= 0:
            return False, boot_elapsed

        wall_elapsed = current.utc - previous.utc

        if wall_elapsed < timedelta(0):
            return False, boot_elapsed

        wall_elapsed_ns = (
            (wall_elapsed.days * 86_400 + wall_elapsed.seconds)
            * _NS_PER_SECOND
            + wall_elapsed.microseconds * _NS_PER_MICROSECOND
        )

        if abs(wall_elapsed_ns - boot_elapsed) > self._tolerance_ns:
            return False, boot_elapsed

        return True, boot_elapsed

    def observe(
        self,
        status: ChronyStatus,
        observation: ClockObservation,
    ) -> ChronySyncAnchor | None:
        """Consume one validated Chrony status and paired clock observation.

        The returned anchor is the previous observation, not a conversion
        of Chrony's UTC Ref time. This makes the reported sync age
        conservative by the detection interval.
        """
        if not isinstance(status, ChronyStatus):
            raise ChronySyncTrackerError(
                "Chrony status has an invalid type"
            )

        current = self._normalise_observation(observation)
        reference_time = status.tracking.reference_time

        if (
            not isinstance(reference_time, Decimal)
            or not reference_time.is_finite()
            or reference_time <= 0
        ):
            self.invalidate()
            raise ChronySyncTrackerError(
                "Chrony reference time is invalid"
            )

        reference_source = status.tracking.reference_address
        source_id = status.source_id

        if not isinstance(reference_source, str) or not reference_source.strip():
            self.invalidate()
            raise ChronySyncTrackerError(
                "Chrony reference source is missing"
            )

        if not isinstance(source_id, str) or not source_id.strip():
            self.invalidate()
            raise ChronySyncTrackerError(
                "Chrony source identity is missing"
            )

        previous = self._previous_observation
        previous_reference = self._previous_reference_time
        previous_source_id = self._previous_source_id
        previous_reference_source = self._previous_reference_source

        if (
            previous is None
            or previous_reference is None
            or previous_source_id is None
            or previous_reference_source is None
        ):
            self._set_baseline(status, current, reference_time)
            return None

        # A change in the approved source group or selected reference
        # invalidates the old anchor. Require a later fresh reference update.
        if (
            source_id != previous_source_id
            or reference_source != previous_reference_source
        ):
            self._set_baseline(status, current, reference_time)
            return None

        consistent, boot_elapsed = (
            self._observation_interval_is_consistent(
                previous,
                current,
            )
        )

        if not consistent:
            self._set_baseline(status, current, reference_time)
            return None

        if reference_time < previous_reference:
            # Chronyd restart, reference-source time rollback, or other
            # discontinuity. Require a later fresh advance.
            self._set_baseline(status, current, reference_time)
            return None

        if reference_time == previous_reference:
            self._previous_observation = current
            return self._anchor

        detection_window_us = (
            boot_elapsed + _NS_PER_MICROSECOND - 1
        ) // _NS_PER_MICROSECOND

        try:
            detection_window = timedelta(
                microseconds=detection_window_us
            )
        except OverflowError as exc:
            self.invalidate()
            raise ChronySyncTrackerError(
                "Chrony detection interval is too large"
            ) from exc

        self._anchor = ChronySyncAnchor(
            last_sync_utc=previous.utc,
            last_sync_boottime_ns=previous.boottime_ns,
            reference_time=reference_time,
            reference_source=status.tracking.reference_address,
            source_id=status.source_id,
            detection_window=detection_window,
        )

        self._previous_observation = current
        self._previous_reference_time = reference_time
        self._previous_source_id = source_id
        self._previous_reference_source = reference_source

        return self._anchor
