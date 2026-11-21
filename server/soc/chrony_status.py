"""Strict parser and validator for the unprivileged Chrony CSV monitor.

This module does not claim to verify NTS authentication by itself.
Authentication policy and the protected Chrony configuration are checked
by the host monitor integration.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR


EXPECTED_SOURCE_NAMES = (
    "time.cloudflare.com",
    "nts.netnod.se",
)

FULL_REACHABILITY = 0o377
DEFAULT_MAX_SOURCE_ERROR_SECONDS = Decimal("0.050")


class ChronyStatusError(ValueError):
    """Raised when Chrony status is incomplete or violates policy."""


@dataclass(frozen=True)
class ChronyTracking:
    reference_id: str
    reference_address: str
    stratum: int
    reference_time: Decimal
    system_time: Decimal
    last_offset: Decimal
    rms_offset: Decimal
    frequency: Decimal
    residual_frequency: Decimal
    skew: Decimal
    root_delay: Decimal
    root_dispersion: Decimal
    update_interval: Decimal
    leap_status: str


@dataclass(frozen=True)
class ChronySource:
    mode: str
    state: str
    name: str
    stratum: int
    poll: int
    reach: int
    last_rx: Decimal
    adjusted_offset: Decimal
    measured_offset: Decimal
    error_margin: Decimal


@dataclass(frozen=True)
class ChronyStatus:
    tracking: ChronyTracking
    sources: tuple[ChronySource, ...]
    source_id: str
    offset: timedelta
    uncertainty: timedelta


def _csv_rows(payload: str, *, field: str) -> list[list[str]]:
    if not isinstance(payload, str) or not payload.strip():
        raise ChronyStatusError(f"{field} output is empty or invalid")

    try:
        reader = csv.reader(io.StringIO(payload), strict=True)
        rows = [
            [item.strip() for item in row]
            for row in reader
            if row and any(item.strip() for item in row)
        ]
    except csv.Error as exc:
        raise ChronyStatusError(
            f"{field} output is malformed CSV"
        ) from exc

    if not rows:
        raise ChronyStatusError(f"{field} output contains no records")

    return rows


def _decimal(
    value: str,
    *,
    field: str,
    nonnegative: bool = False,
    positive: bool = False,
) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ChronyStatusError(f"{field} is not a valid decimal") from exc

    if not result.is_finite():
        raise ChronyStatusError(f"{field} must be finite")

    if nonnegative and result < 0:
        raise ChronyStatusError(f"{field} must not be negative")

    if positive and result <= 0:
        raise ChronyStatusError(f"{field} must be positive")

    return result


def _integer(
    value: str,
    *,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    if not re.fullmatch(r"[0-9]+", value):
        raise ChronyStatusError(f"{field} is not a valid integer")

    result = int(value, 10)
    if not minimum <= result <= maximum:
        raise ChronyStatusError(f"{field} is outside the permitted range")

    return result


def _seconds_to_timedelta(value: Decimal) -> timedelta:
    """Convert seconds to timedelta, rounding away from zero."""
    scaled = value * Decimal(1_000_000)

    rounding = ROUND_CEILING if scaled >= 0 else ROUND_FLOOR

    try:
        microseconds = int(scaled.to_integral_value(rounding=rounding))
        return timedelta(microseconds=microseconds)
    except (OverflowError, ValueError) as exc:
        raise ChronyStatusError(
            "Chrony time interval exceeds supported range"
        ) from exc


def parse_tracking_csv(payload: str) -> ChronyTracking:
    rows = _csv_rows(payload, field="tracking")

    if len(rows) != 1 or len(rows[0]) != 14:
        raise ChronyStatusError(
            "tracking must contain exactly one 14-field CSV record"
        )

    row = rows[0]

    if not row[0] or not row[1]:
        raise ChronyStatusError("tracking reference identity is missing")

    return ChronyTracking(
        reference_id=row[0],
        reference_address=row[1],
        stratum=_integer(
            row[2],
            field="tracking stratum",
            minimum=1,
            maximum=15,
        ),
        reference_time=_decimal(
            row[3],
            field="tracking reference time",
            positive=True,
        ),
        system_time=_decimal(
            row[4],
            field="tracking system time",
        ),
        last_offset=_decimal(
            row[5],
            field="tracking last offset",
        ),
        rms_offset=_decimal(
            row[6],
            field="tracking RMS offset",
            nonnegative=True,
        ),
        frequency=_decimal(
            row[7],
            field="tracking frequency",
        ),
        residual_frequency=_decimal(
            row[8],
            field="tracking residual frequency",
        ),
        skew=_decimal(
            row[9],
            field="tracking skew",
            nonnegative=True,
        ),
        root_delay=_decimal(
            row[10],
            field="tracking root delay",
            nonnegative=True,
        ),
        root_dispersion=_decimal(
            row[11],
            field="tracking root dispersion",
            nonnegative=True,
        ),
        update_interval=_decimal(
            row[12],
            field="tracking update interval",
            positive=True,
        ),
        leap_status=row[13],
    )


def parse_sources_csv(payload: str) -> tuple[ChronySource, ...]:
    rows = _csv_rows(payload, field="sources")
    sources: list[ChronySource] = []

    for index, row in enumerate(rows):
        if len(row) != 10:
            raise ChronyStatusError(
                f"sources record {index} must contain 10 fields"
            )

        if row[0] != "^":
            raise ChronyStatusError(
                f"sources record {index} is not an NTP server"
            )

        reach_text = row[5]
        if not re.fullmatch(r"[0-7]+", reach_text):
            raise ChronyStatusError(
                f"sources record {index} has invalid octal reachability"
            )

        reach = int(reach_text, 8)
        if not 0 <= reach <= FULL_REACHABILITY:
            raise ChronyStatusError(
                f"sources record {index} has invalid reachability"
            )

        sources.append(
            ChronySource(
                mode=row[0],
                state=row[1],
                name=row[2],
                stratum=_integer(
                    row[3],
                    field=f"sources record {index} stratum",
                    minimum=1,
                    maximum=15,
                ),
                poll=_integer(
                    row[4],
                    field=f"sources record {index} poll",
                    minimum=0,
                    maximum=30,
                ),
                reach=reach,
                last_rx=_decimal(
                    row[6],
                    field=f"sources record {index} last_rx",
                    nonnegative=True,
                ),
                adjusted_offset=_decimal(
                    row[7],
                    field=f"sources record {index} adjusted offset",
                ),
                measured_offset=_decimal(
                    row[8],
                    field=f"sources record {index} measured offset",
                ),
                error_margin=_decimal(
                    row[9],
                    field=f"sources record {index} error margin",
                    nonnegative=True,
                ),
            )
        )

    return tuple(sources)


def parse_chrony_status(
    tracking_csv: str,
    sources_csv: str,
    *,
    max_source_error_seconds: Decimal = DEFAULT_MAX_SOURCE_ERROR_SECONDS,
) -> ChronyStatus:
    """Validate Chrony tracking and source-selection status.

    Only the two explicitly approved NTS source names are accepted.
    Both must be selected (* and +), fully reachable, recently sampled,
    and within the configured per-source error bound.

    NTS authentication itself is not asserted by this parser.
    """
    if (
        not isinstance(max_source_error_seconds, Decimal)
        or not max_source_error_seconds.is_finite()
        or max_source_error_seconds <= 0
    ):
        raise ValueError("max_source_error_seconds must be a positive Decimal")

    tracking = parse_tracking_csv(tracking_csv)
    sources = parse_sources_csv(sources_csv)

    if tracking.leap_status != "Normal":
        raise ChronyStatusError("Chrony leap status is not Normal")

    if len(sources) != len(EXPECTED_SOURCE_NAMES):
        raise ChronyStatusError(
            "Chrony must report exactly the two approved time sources"
        )

    names = [source.name for source in sources]
    if len(set(names)) != len(names):
        raise ChronyStatusError("Chrony reported duplicate time sources")

    if set(names) != set(EXPECTED_SOURCE_NAMES):
        raise ChronyStatusError(
            "Chrony reported an unknown or missing time source"
        )

    states = [source.state for source in sources]
    if sorted(states) != ["*", "+"]:
        raise ChronyStatusError(
            "both approved sources must be selected (* and +)"
        )

    best_source = next(
        source for source in sources if source.state == "*"
    )
    if tracking.reference_address != best_source.name:
        raise ChronyStatusError(
            "tracking reference does not match the selected best source"
        )

    max_source_age_limit = Decimal("1200")

    for source in sources:
        max_source_age = min(
            max_source_age_limit,
            max(
                Decimal("180"),
                tracking.update_interval * Decimal("2") + Decimal("5"),
                (Decimal("2") ** source.poll) + Decimal("30"),
            ),
        )

        if source.reach != FULL_REACHABILITY:
            raise ChronyStatusError(
                f"{source.name} does not have full reachability"
            )

        if source.last_rx > max_source_age:
            raise ChronyStatusError(
                f"{source.name} last valid sample is too old"
            )

        if source.error_margin > max_source_error_seconds:
            raise ChronyStatusError(
                f"{source.name} error margin exceeds the configured limit"
            )

    ordered_names = [
        name for name in EXPECTED_SOURCE_NAMES if name in set(names)
    ]

    offset = _seconds_to_timedelta(tracking.system_time)

    uncertainty_seconds = (
        abs(tracking.system_time)
        + tracking.root_dispersion
        + tracking.root_delay / Decimal(2)
    )
    uncertainty = _seconds_to_timedelta(uncertainty_seconds)

    return ChronyStatus(
        tracking=tracking,
        sources=sources,
        source_id="+".join(ordered_names),
        offset=offset,
        uncertainty=uncertainty,
    )
