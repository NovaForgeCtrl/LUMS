"""Fail-closed trusted-time contract for SOC TLS admission.

This module deliberately does not implement an NTP client or assume that
systemd-timesyncd provides authenticated time. A provider must supply an
explicitly authenticated and approved time source plus a BOOTTIME reference
for the last successful synchronization.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol


UTC = timezone.utc


class TrustedTimeError(RuntimeError):
    """Raised when trustworthy time cannot be established."""


@dataclass(frozen=True)
class TrustedTimePolicy:
    """Explicit limits for one component's trusted-time validation."""

    approved_sources: frozenset[str]
    max_sync_age: timedelta
    max_offset: timedelta
    max_uncertainty: timedelta
    clock_consistency_tolerance: timedelta

    def __post_init__(self) -> None:
        if not isinstance(self.approved_sources, frozenset):
            raise TypeError("approved_sources must be a frozenset")

        if not self.approved_sources:
            raise ValueError("approved_sources must not be empty")

        if any(
            not isinstance(source, str) or not source.strip()
            for source in self.approved_sources
        ):
            raise ValueError("approved source identifiers must be non-empty")

        for name in (
            "max_sync_age",
            "max_offset",
            "max_uncertainty",
        ):
            value = getattr(self, name)
            if not isinstance(value, timedelta) or value <= timedelta(0):
                raise ValueError(f"{name} must be a positive timedelta")

        tolerance = self.clock_consistency_tolerance
        if not isinstance(tolerance, timedelta) or tolerance < timedelta(0):
            raise ValueError(
                "clock_consistency_tolerance must not be negative"
            )


@dataclass(frozen=True)
class TrustedTimeSnapshot:
    """One atomic provider snapshot.

    The provider is responsible for recording last_sync_boottime_ns at the
    instant a successful synchronization is confirmed. It must not derive
    that value later from wall-clock timestamps.

    observed_utc and observed_boottime_ns must describe the same observation.
    """

    synchronized: bool
    authenticated: bool
    source_id: str
    last_sync_utc: datetime
    last_sync_boottime_ns: int
    observed_utc: datetime
    observed_boottime_ns: int
    offset: timedelta
    uncertainty: timedelta


@dataclass(frozen=True)
class TrustedTime:
    """Validated time observation suitable for admission decisions."""

    utc_now: datetime
    boottime_ns: int
    sync_age: timedelta
    source_id: str
    offset: timedelta
    uncertainty: timedelta


class TrustedTimeProvider(Protocol):
    """Provider interface implemented by the deployment integration."""

    def get_snapshot(self) -> TrustedTimeSnapshot:
        """Return one internally consistent time-status snapshot."""
        ...


def boottime_ns() -> int:
    """Return Linux CLOCK_BOOTTIME in nanoseconds.

    CLOCK_BOOTTIME includes time spent suspended. There is intentionally no
    fallback to CLOCK_MONOTONIC or CLOCK_REALTIME.
    """
    clock_id = getattr(time, "CLOCK_BOOTTIME", None)
    if clock_id is None:
        raise TrustedTimeError("CLOCK_BOOTTIME is unavailable")

    try:
        value = time.clock_gettime_ns(clock_id)
    except (OSError, OverflowError, ValueError) as exc:
        raise TrustedTimeError("CLOCK_BOOTTIME cannot be read") from exc

    if type(value) is not int or value < 0:
        raise TrustedTimeError("CLOCK_BOOTTIME returned an invalid value")

    return value


def _require_aware_datetime(value: object, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise TrustedTimeError(f"{field} is missing or invalid")

    if value.tzinfo is None or value.utcoffset() is None:
        raise TrustedTimeError(f"{field} must be timezone-aware")

    try:
        return value.astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise TrustedTimeError(f"{field} cannot be normalized to UTC") from exc


def _require_boottime(value: object, field: str) -> int:
    # bool is a subclass of int; it is not a valid clock reading.
    if type(value) is not int or value < 0:
        raise TrustedTimeError(f"{field} is missing or invalid")
    return value


def _require_duration(value: object, field: str) -> timedelta:
    if not isinstance(value, timedelta):
        raise TrustedTimeError(f"{field} is missing or invalid")
    return value


def validate_trusted_time(
    snapshot: TrustedTimeSnapshot,
    policy: TrustedTimePolicy,
    *,
    process_started_boottime_ns: int,
) -> TrustedTime:
    """Validate one provider snapshot or fail closed.

    The process-start reference prevents a service restart from reusing a
    synchronization event that happened before that service instance began.
    """
    if not isinstance(policy, TrustedTimePolicy):
        raise TypeError("policy must be a TrustedTimePolicy instance")

    if not isinstance(snapshot, TrustedTimeSnapshot):
        raise TrustedTimeError("time provider returned an invalid snapshot")

    process_started = _require_boottime(
        process_started_boottime_ns,
        "process_started_boottime_ns",
    )
    last_sync_boot = _require_boottime(
        snapshot.last_sync_boottime_ns,
        "last_sync_boottime_ns",
    )
    observed_boot = _require_boottime(
        snapshot.observed_boottime_ns,
        "observed_boottime_ns",
    )

    if snapshot.synchronized is not True:
        raise TrustedTimeError("time synchronization is not confirmed")

    if snapshot.authenticated is not True:
        raise TrustedTimeError("time source is not authenticated")

    if (
        not isinstance(snapshot.source_id, str)
        or not snapshot.source_id.strip()
    ):
        raise TrustedTimeError("time source identity is missing")

    if snapshot.source_id not in policy.approved_sources:
        raise TrustedTimeError("time source is not approved")

    if last_sync_boot <= process_started:
        raise TrustedTimeError(
            "no successful time synchronization after process start"
        )

    if observed_boot < last_sync_boot:
        raise TrustedTimeError(
            "observed BOOTTIME precedes the last synchronization"
        )

    last_sync_utc = _require_aware_datetime(
        snapshot.last_sync_utc,
        "last_sync_utc",
    )
    observed_utc = _require_aware_datetime(
        snapshot.observed_utc,
        "observed_utc",
    )

    offset = _require_duration(snapshot.offset, "offset")
    uncertainty = _require_duration(
        snapshot.uncertainty,
        "uncertainty",
    )

    if uncertainty < timedelta(0):
        raise TrustedTimeError("time uncertainty must not be negative")

    if abs(offset) > policy.max_offset:
        raise TrustedTimeError("time offset exceeds the configured limit")

    if uncertainty > policy.max_uncertainty:
        raise TrustedTimeError(
            "time uncertainty exceeds the configured limit"
        )

    elapsed_ns = observed_boot - last_sync_boot

    # Round up to the next microsecond. A fractional microsecond must never
    # make the synchronization appear younger than it actually is.
    elapsed_microseconds = (elapsed_ns + 999) // 1000

    try:
        sync_age = timedelta(microseconds=elapsed_microseconds)
    except OverflowError as exc:
        raise TrustedTimeError(
            "time synchronization age is outside the supported range"
        ) from exc

    if sync_age > policy.max_sync_age:
        raise TrustedTimeError(
            "last successful time synchronization is too old"
        )

    wall_elapsed = observed_utc - last_sync_utc
    if wall_elapsed < timedelta(0):
        raise TrustedTimeError(
            "wall clock moved backwards since synchronization"
        )

    difference = abs(wall_elapsed - sync_age)
    if difference > policy.clock_consistency_tolerance:
        raise TrustedTimeError(
            "wall clock and BOOTTIME observations are inconsistent"
        )

    return TrustedTime(
        utc_now=observed_utc,
        boottime_ns=observed_boot,
        sync_age=sync_age,
        source_id=snapshot.source_id,
        offset=offset,
        uncertainty=uncertainty,
    )


def read_trusted_time(
    provider: TrustedTimeProvider,
    policy: TrustedTimePolicy,
    *,
    process_started_boottime_ns: int,
) -> TrustedTime:
    """Read and validate a provider snapshot.

    Provider failures are converted into a fail-closed TrustedTimeError.
    """
    if provider is None or not callable(
        getattr(provider, "get_snapshot", None)
    ):
        raise TrustedTimeError("trusted-time provider is unavailable")

    try:
        snapshot = provider.get_snapshot()
    except Exception as exc:
        raise TrustedTimeError(
            "trusted-time provider could not be queried"
        ) from exc

    return validate_trusted_time(
        snapshot,
        policy,
        process_started_boottime_ns=process_started_boottime_ns,
    )
