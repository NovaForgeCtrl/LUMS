"""Deterministic, in-memory time-window correlation for SOC events."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from .models import SecurityEvent


@dataclass(frozen=True)
class CorrelationRule:
    rule_id: str
    name: str
    event_type: str
    group_by: str
    window_seconds: int
    minimum_count: int
    severity: str = "warning"
    enabled: bool = True

    def __post_init__(self) -> None:
        for label, value in (
            ("rule_id", self.rule_id),
            ("event_type", self.event_type),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} is required")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Rule name is required")
        if not isinstance(self.group_by, str) or not self.group_by.strip():
            raise ValueError("group_by is required")
        if (
            isinstance(self.window_seconds, bool)
            or not isinstance(self.window_seconds, int)
            or self.window_seconds < 1
        ):
            raise ValueError("window_seconds must be a positive integer")
        if (
            isinstance(self.minimum_count, bool)
            or not isinstance(self.minimum_count, int)
            or self.minimum_count < 2
        ):
            raise ValueError("minimum_count must be an integer >= 2")
        if self.severity not in {"info", "warning", "critical"}:
            raise ValueError("Unsupported severity")
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be boolean")


@dataclass(frozen=True)
class CorrelationMatch:
    rule_id: str
    rule_name: str
    severity: str
    event_type: str
    group_value: Any
    event_ids: tuple[str, ...]
    first_seen: str
    last_seen: str
    count: int
    window_seconds: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "event_type": self.event_type,
            "group_value": self.group_value,
            "event_ids": list(self.event_ids),
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "count": self.count,
            "window_seconds": self.window_seconds,
            "reason": self.reason,
        }


class CorrelationEngine:
    """Find event groups meeting a minimum count inside a sliding time window.

    The engine is stateless: it does not persist events or remember previous calls.
    Each call evaluates only the events supplied to it.
    """

    def correlate(
        self,
        events: Iterable[SecurityEvent],
        rules: Iterable[CorrelationRule],
    ) -> list[CorrelationMatch]:
        event_list = list(events)
        rule_list = list(rules)

        if any(not isinstance(event, SecurityEvent) for event in event_list):
            raise ValueError("All events must be SecurityEvent objects")
        if any(not isinstance(rule, CorrelationRule) for rule in rule_list):
            raise ValueError("All rules must be CorrelationRule objects")

        results: list[CorrelationMatch] = []

        for rule in rule_list:
            if not rule.enabled:
                continue

            groups: dict[str, list[tuple[datetime, SecurityEvent, Any]]] = defaultdict(list)

            for event in event_list:
                if event.event_type != rule.event_type:
                    continue
                if rule.group_by not in event.fields:
                    continue

                value = event.fields[rule.group_by]
                if value is None or isinstance(value, (dict, list, set)):
                    continue

                timestamp = datetime.fromisoformat(
                    event.timestamp.replace("Z", "+00:00")
                )
                # Use JSON-safe type + representation to avoid mixing values
                # such as integer 1 and string "1" into one group.
                key = f"{type(value).__name__}:{value!r}"
                groups[key].append((timestamp, event, value))

            for grouped_events in groups.values():
                grouped_events.sort(key=lambda item: (item[0], item[1].event_id))
                left = 0

                for right, current in enumerate(grouped_events):
                    while (
                        current[0] - grouped_events[left][0]
                    ).total_seconds() > rule.window_seconds:
                        left += 1

                    window = grouped_events[left:right + 1]
                    if len(window) < rule.minimum_count:
                        continue

                    # Emit once per qualifying window endpoint; this is useful
                    # for a streaming adapter to decide whether to deduplicate.
                    ids = tuple(item[1].event_id for item in window)
                    first = window[0][0].isoformat()
                    last = window[-1][0].isoformat()
                    group_value = current[2]

                    results.append(
                        CorrelationMatch(
                            rule_id=rule.rule_id,
                            rule_name=rule.name,
                            severity=rule.severity,
                            event_type=rule.event_type,
                            group_value=group_value,
                            event_ids=ids,
                            first_seen=first,
                            last_seen=last,
                            count=len(window),
                            window_seconds=rule.window_seconds,
                            reason=(
                                f"{len(window)} events of {rule.event_type} "
                                f"for {rule.group_by}={group_value!r} "
                                f"within {rule.window_seconds}s"
                            ),
                        )
                    )

        results.sort(key=lambda match: (match.last_seen, match.rule_id, match.event_ids))
        return results
