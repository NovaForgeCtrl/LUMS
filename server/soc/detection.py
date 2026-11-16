"""Safe, deterministic event matching for the LUMS SOC."""

from collections.abc import Iterable
from typing import Any

from .models import DetectionMatch, DetectionRule, SecurityEvent


class DetectionError(ValueError):
    """Raised when a rule or event cannot be evaluated safely."""


_MISSING = object()


class DetectionEngine:
    """Evaluate explicit field predicates without eval or dynamic code execution."""

    def evaluate(
        self,
        event: SecurityEvent,
        rules: Iterable[DetectionRule],
    ) -> list[DetectionMatch]:
        if not isinstance(event, SecurityEvent):
            raise DetectionError("Expected a SecurityEvent")

        matches: list[DetectionMatch] = []
        for rule in rules:
            if not isinstance(rule, DetectionRule):
                raise DetectionError("Expected DetectionRule objects")
            if not rule.enabled or rule.event_type != event.event_type:
                continue

            observed = event.fields.get(rule.field, _MISSING)
            if observed is _MISSING:
                continue

            try:
                matched = self._compare(rule.operator, observed, rule.value)
            except (TypeError, ValueError) as exc:
                raise DetectionError(
                    f"Rule {rule.rule_id} cannot compare field {rule.field}"
                ) from exc

            if matched:
                matches.append(
                    DetectionMatch(
                        rule_id=rule.rule_id,
                        rule_name=rule.name,
                        severity=rule.severity,
                        event_id=event.event_id,
                        event_source=event.source,
                        event_type=event.event_type,
                        event_timestamp=event.timestamp,
                        field=rule.field,
                        operator=rule.operator,
                        expected=rule.value,
                        observed=observed,
                        reason=(
                            f"{rule.event_type}.{rule.field} "
                            f"{rule.operator} {rule.value!r} "
                            f"(observed {observed!r})"
                        ),
                    )
                )
        return matches

    @staticmethod
    def _compare(operator: str, observed: Any, expected: Any) -> bool:
        if operator == "eq":
            return type(observed) is type(expected) and observed == expected
        if operator == "ne":
            return type(observed) is not type(expected) or observed != expected
        if operator == "gt":
            return observed > expected
        if operator == "gte":
            return observed >= expected
        if operator == "lt":
            return observed < expected
        if operator == "lte":
            return observed <= expected
        if operator == "contains":
            if not isinstance(observed, (str, list, tuple, set, dict)):
                raise ValueError("contains requires a container")
            return expected in observed
        if operator == "in":
            if not isinstance(expected, (list, tuple, set, frozenset, str)):
                raise ValueError("in requires an expected collection")
            return observed in expected
        raise DetectionError("Unsupported operator")
