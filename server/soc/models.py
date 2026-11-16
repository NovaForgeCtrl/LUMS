"""Typed data models for the LUMS SOC detection core."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import re


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _identifier(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid {field_name}")
    return value


def _timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if not isinstance(value, str):
        raise ValueError("Invalid timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class SecurityEvent:
    event_id: str
    source: str
    event_type: str
    fields: dict[str, Any] = field(default_factory=dict)
    timestamp: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.event_id, "event_id")
        _identifier(self.source, "source")
        _identifier(self.event_type, "event_type")
        if not isinstance(self.fields, dict):
            raise ValueError("Event fields must be an object")
        object.__setattr__(self, "fields", dict(self.fields))
        object.__setattr__(self, "timestamp", _timestamp(self.timestamp))


@dataclass(frozen=True)
class DetectionRule:
    rule_id: str
    name: str
    event_type: str
    field: str
    operator: str
    value: Any
    severity: str = "warning"
    enabled: bool = True

    def __post_init__(self) -> None:
        _identifier(self.rule_id, "rule_id")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Rule name is required")
        _identifier(self.event_type, "event_type")
        if not isinstance(self.field, str) or not self.field.strip():
            raise ValueError("Rule field is required")
        if (
            not isinstance(self.operator, str)
            or self.operator not in {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "in"}
        ):
            raise ValueError("Unsupported operator")
        if (
            not isinstance(self.severity, str)
            or self.severity not in {"info", "warning", "critical"}
        ):
            raise ValueError("Unsupported severity")
        if not isinstance(self.enabled, bool):
            raise ValueError("Rule enabled must be boolean")


@dataclass(frozen=True)
class DetectionMatch:
    rule_id: str
    rule_name: str
    severity: str
    event_id: str
    event_source: str
    event_type: str
    event_timestamp: str
    field: str
    operator: str
    expected: Any
    observed: Any
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "event_id": self.event_id,
            "event_source": self.event_source,
            "event_type": self.event_type,
            "event_timestamp": self.event_timestamp,
            "field": self.field,
            "operator": self.operator,
            "expected": self.expected,
            "observed": self.observed,
            "reason": self.reason,
        }
