"""Validated, versioned JSON catalog for deterministic LUMS SOC rules.

Loading this module performs no I/O. Reading a catalog is explicit and
does not persist events, modify alert configuration, or execute responses.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .correlation import CorrelationRule
from .models import DetectionRule


CATALOG_VERSION = 1
MAX_CATALOG_BYTES = 1024 * 1024

_ROOT_KEYS = {"version", "rules"}
_COMMON_KEYS = {
    "id", "name", "description", "type", "event_type", "severity", "enabled"
}
_DETECTION_KEYS = _COMMON_KEYS | {"field", "operator", "value"}
_CORRELATION_KEYS = _COMMON_KEYS | {
    "group_by", "window_seconds", "minimum_count"
}
_ALLOWED_TYPES = {"detection", "correlation"}
_ALLOWED_SEVERITIES = {"info", "warning", "critical"}
_ALLOWED_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "in"}
_IDENTIFIER_PATTERN = __import__("re").compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"
)


class RuleCatalogError(ValueError):
    """A catalog is malformed, unsafe, or incompatible."""


@dataclass(frozen=True)
class LoadedRuleCatalog:
    """Validated rules ready for explicit use by the SOC pipeline."""

    version: int
    detection_rules: tuple[DetectionRule, ...]
    correlation_rules: tuple[CorrelationRule, ...]
    descriptions: Mapping[str, str]

    @property
    def rule_count(self) -> int:
        return len(self.detection_rules) + len(self.correlation_rules)


def _require_keys(
    item: Mapping[str, Any],
    required: set[str],
    allowed: set[str],
    location: str,
) -> None:
    missing = required - item.keys()
    unknown = item.keys() - allowed

    if missing:
        raise RuleCatalogError(
            f"{location}: missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise RuleCatalogError(
            f"{location}: unknown fields: {', '.join(sorted(unknown))}"
        )


def _nonempty_string(value: Any, field: str, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuleCatalogError(f"{location}: {field} must be a non-empty string")
    return value.strip()


def _identifier(value: Any, field: str, location: str) -> str:
    result = _nonempty_string(value, field, location)
    if not _IDENTIFIER_PATTERN.fullmatch(result):
        raise RuleCatalogError(f"{location}: invalid {field}")
    return result


def _json_safe(value: Any, location: str) -> None:
    try:
        encoded = json.dumps(value, allow_nan=False, ensure_ascii=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuleCatalogError(f"{location}: value must be valid JSON data") from exc

    if len(encoded.encode("utf-8")) > 16 * 1024:
        raise RuleCatalogError(f"{location}: value exceeds the size limit")


def load_catalog_data(data: Any) -> LoadedRuleCatalog:
    """Validate decoded JSON data and construct typed rule objects."""
    if not isinstance(data, dict):
        raise RuleCatalogError("Catalog root must be an object")

    _require_keys(data, {"version", "rules"}, _ROOT_KEYS, "catalog")

    version = data["version"]
    if isinstance(version, bool) or version != CATALOG_VERSION:
        raise RuleCatalogError("Unsupported catalog version")

    rules = data["rules"]
    if not isinstance(rules, list):
        raise RuleCatalogError("catalog.rules must be an array")
    if len(rules) > 500:
        raise RuleCatalogError("Catalog exceeds the 500-rule limit")

    detections: list[DetectionRule] = []
    correlations: list[CorrelationRule] = []
    descriptions: dict[str, str] = {}
    seen_ids: set[str] = set()

    for index, item in enumerate(rules):
        location = f"rules[{index}]"
        if not isinstance(item, dict):
            raise RuleCatalogError(f"{location} must be an object")

        rule_type = item.get("type")
        if rule_type not in _ALLOWED_TYPES:
            raise RuleCatalogError(f"{location}: unsupported rule type")

        required = (
            _DETECTION_KEYS
            if rule_type == "detection"
            else _CORRELATION_KEYS
        )
        _require_keys(item, required, required, location)

        rule_id = _identifier(item["id"], "id", location)
        if rule_id in seen_ids:
            raise RuleCatalogError(f"{location}: duplicate rule id {rule_id}")
        seen_ids.add(rule_id)

        name = _nonempty_string(item["name"], "name", location)
        event_type = _identifier(item["event_type"], "event_type", location)
        description = item["description"]
        if not isinstance(description, str):
            raise RuleCatalogError(f"{location}: description must be a string")
        if len(description) > 2000:
            raise RuleCatalogError(f"{location}: description is too long")

        severity = item["severity"]
        if severity not in _ALLOWED_SEVERITIES:
            raise RuleCatalogError(f"{location}: unsupported severity")

        enabled = item["enabled"]
        if not isinstance(enabled, bool):
            raise RuleCatalogError(f"{location}: enabled must be boolean")

        try:
            if rule_type == "detection":
                field = _nonempty_string(item["field"], "field", location)
                operator = item["operator"]
                if operator not in _ALLOWED_OPERATORS:
                    raise RuleCatalogError(
                        f"{location}: unsupported operator"
                    )

                _json_safe(item["value"], f"{location}.value")

                # Reject NaN and infinities and ensure the value is JSON-safe.
                rule = DetectionRule(
                    rule_id=rule_id,
                    name=name,
                    event_type=event_type,
                    field=field,
                    operator=operator,
                    value=item["value"],
                    severity=severity,
                    enabled=enabled,
                )
                detections.append(rule)
            else:
                group_by = _nonempty_string(
                    item["group_by"], "group_by", location
                )
                window_seconds = item["window_seconds"]
                minimum_count = item["minimum_count"]

                if (
                    isinstance(window_seconds, bool)
                    or not isinstance(window_seconds, int)
                    or not 1 <= window_seconds <= 86400
                ):
                    raise RuleCatalogError(
                        f"{location}: window_seconds must be 1..86400"
                    )
                if (
                    isinstance(minimum_count, bool)
                    or not isinstance(minimum_count, int)
                    or not 2 <= minimum_count <= 10000
                ):
                    raise RuleCatalogError(
                        f"{location}: minimum_count must be 2..10000"
                    )

                correlations.append(
                    CorrelationRule(
                        rule_id=rule_id,
                        name=name,
                        event_type=event_type,
                        group_by=group_by,
                        window_seconds=window_seconds,
                        minimum_count=minimum_count,
                        severity=severity,
                        enabled=enabled,
                    )
                )
        except RuleCatalogError:
            raise
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuleCatalogError(f"{location}: invalid rule definition") from exc

        descriptions[rule_id] = description

    return LoadedRuleCatalog(
        version=version,
        detection_rules=tuple(detections),
        correlation_rules=tuple(correlations),
        descriptions=dict(descriptions),
    )


def load_catalog(path: str | Path) -> LoadedRuleCatalog:
    """Load a bounded UTF-8 JSON catalog from an explicit filesystem path."""
    catalog_path = Path(path)

    try:
        with catalog_path.open("rb") as stream:
            raw = stream.read(MAX_CATALOG_BYTES + 1)
    except OSError as exc:
        raise RuleCatalogError("Could not read rule catalog") from exc

    if len(raw) > MAX_CATALOG_BYTES:
        raise RuleCatalogError("Catalog exceeds the 1 MiB size limit")

    try:
        text = raw.decode("utf-8")
        data = json.loads(
            text,
            parse_constant=lambda value: (
                _raise_invalid_constant(value)
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise RuleCatalogError("Catalog is not valid UTF-8 JSON") from exc

    return load_catalog_data(data)


def _raise_invalid_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")
