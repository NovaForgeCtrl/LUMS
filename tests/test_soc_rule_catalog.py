import json

import pytest

from server.soc.correlation import CorrelationRule
from server.soc.models import DetectionRule
from server.soc.rule_catalog import (
    CATALOG_VERSION,
    RuleCatalogError,
    load_catalog,
    load_catalog_data,
)


def detection(**overrides):
    item = {
        "id": "LINUX-AUTH-001",
        "name": "Authentication failure threshold",
        "description": "Detect a high number of failed authentications.",
        "type": "detection",
        "event_type": "auth.failure",
        "field": "failure_count",
        "operator": "gte",
        "value": 5,
        "severity": "warning",
        "enabled": True,
    }
    item.update(overrides)
    return item


def correlation(**overrides):
    item = {
        "id": "LINUX-AUTH-002",
        "name": "Repeated failures",
        "description": "Correlate failures by username.",
        "type": "correlation",
        "event_type": "auth.failure",
        "group_by": "username",
        "window_seconds": 300,
        "minimum_count": 5,
        "severity": "critical",
        "enabled": True,
    }
    item.update(overrides)
    return item


def catalog(*rules, version=CATALOG_VERSION):
    return {"version": version, "rules": list(rules)}


def test_loads_detection_and_correlation_rules():
    result = load_catalog_data(catalog(detection(), correlation()))

    assert result.version == 1
    assert result.rule_count == 2
    assert isinstance(result.detection_rules[0], DetectionRule)
    assert isinstance(result.correlation_rules[0], CorrelationRule)
    assert result.descriptions["LINUX-AUTH-001"].startswith("Detect")


def test_rules_are_immutable_tuples():
    result = load_catalog_data(catalog(detection()))

    assert isinstance(result.detection_rules, tuple)
    assert isinstance(result.correlation_rules, tuple)


@pytest.mark.parametrize("data", [
    [],
    None,
    "not an object",
    {},
    {"version": 1, "rules": [], "unexpected": True},
    {"version": True, "rules": []},
    {"version": 99, "rules": []},
    {"version": 1, "rules": {}},
])
def test_rejects_invalid_catalog_roots(data):
    with pytest.raises(RuleCatalogError):
        load_catalog_data(data)


def test_rejects_unknown_rule_fields():
    with pytest.raises(RuleCatalogError, match="unknown fields"):
        load_catalog_data(catalog(detection(unexpected=True)))


def test_rejects_missing_rule_fields():
    item = detection()
    del item["field"]

    with pytest.raises(RuleCatalogError, match="missing fields"):
        load_catalog_data(catalog(item))


def test_rejects_duplicate_ids_across_rule_types():
    first = detection()
    second = correlation(id=first["id"])

    with pytest.raises(RuleCatalogError, match="duplicate rule id"):
        load_catalog_data(catalog(first, second))


@pytest.mark.parametrize("operator", ["exec", "__import__", "matches", ""])
def test_rejects_unsupported_operators(operator):
    with pytest.raises(RuleCatalogError, match="unsupported operator"):
        load_catalog_data(catalog(detection(operator=operator)))


@pytest.mark.parametrize("severity", ["high", "low", "emergency", ""])
def test_rejects_unsupported_severities(severity):
    with pytest.raises(RuleCatalogError, match="unsupported severity"):
        load_catalog_data(catalog(detection(severity=severity)))


@pytest.mark.parametrize("enabled", [0, 1, "true", None])
def test_enabled_must_be_boolean(enabled):
    with pytest.raises(RuleCatalogError, match="enabled must be boolean"):
        load_catalog_data(catalog(detection(enabled=enabled)))


@pytest.mark.parametrize("window", [True, 0, -1, 86401, 1.5, "300"])
def test_rejects_invalid_correlation_windows(window):
    with pytest.raises(RuleCatalogError, match="window_seconds"):
        load_catalog_data(catalog(correlation(window_seconds=window)))


@pytest.mark.parametrize("minimum", [True, 0, 1, 10001, 2.5, "5"])
def test_rejects_invalid_correlation_minimum_counts(minimum):
    with pytest.raises(RuleCatalogError, match="minimum_count"):
        load_catalog_data(catalog(correlation(minimum_count=minimum)))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), object()])
def test_rejects_non_json_detection_values(value):
    with pytest.raises(RuleCatalogError, match="valid JSON data"):
        load_catalog_data(catalog(detection(value=value)))


def test_rejects_oversized_detection_value():
    with pytest.raises(RuleCatalogError, match="size limit"):
        load_catalog_data(catalog(detection(value="x" * 17000)))


def test_disabled_rule_remains_disabled():
    result = load_catalog_data(catalog(detection(enabled=False)))

    assert result.detection_rules[0].enabled is False


def test_loads_json_file(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(
        json.dumps(catalog(detection()), ensure_ascii=False),
        encoding="utf-8",
    )

    result = load_catalog(path)

    assert result.rule_count == 1
    assert result.detection_rules[0].rule_id == "LINUX-AUTH-001"


def test_rejects_malformed_json_file(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text('{"version": 1, "rules": [}', encoding="utf-8")

    with pytest.raises(RuleCatalogError, match="valid UTF-8 JSON"):
        load_catalog(path)


def test_rejects_oversized_catalog_file(tmp_path):
    path = tmp_path / "rules.json"
    path.write_bytes(b" " * (1024 * 1024 + 1))

    with pytest.raises(RuleCatalogError, match="1 MiB"):
        load_catalog(path)


def test_empty_catalog_is_valid():
    result = load_catalog_data(catalog())

    assert result.rule_count == 0
    assert result.detection_rules == ()
    assert result.correlation_rules == ()


def test_correlation_inactivity_defaults_to_window():
    result = load_catalog_data(catalog(correlation(window_seconds=180)))

    assert result.correlation_rules[0].window_seconds == 180
    assert result.correlation_rules[0].inactivity_seconds == 180


def test_correlation_inactivity_can_differ_from_window():
    result = load_catalog_data(
        catalog(correlation(window_seconds=180, inactivity_seconds=420))
    )

    assert result.correlation_rules[0].window_seconds == 180
    assert result.correlation_rules[0].inactivity_seconds == 420


@pytest.mark.parametrize(
    "value", [True, 0, -1, 86401, 1.5, "300"]
)
def test_rejects_invalid_correlation_inactivity(value):
    with pytest.raises(RuleCatalogError, match="inactivity_seconds"):
        load_catalog_data(
            catalog(correlation(inactivity_seconds=value))
        )


@pytest.mark.parametrize("version", [1.0, "1", None])
def test_rejects_non_integer_catalog_versions(version):
    with pytest.raises(RuleCatalogError, match="Unsupported catalog version"):
        load_catalog_data(catalog(version=version))


@pytest.mark.parametrize("rule_type", [[], {}])
def test_rejects_unhashable_rule_types(rule_type):
    with pytest.raises(RuleCatalogError, match="unsupported rule type"):
        load_catalog_data(catalog(detection(type=rule_type)))


@pytest.mark.parametrize("severity", [[], {}])
def test_rejects_unhashable_severities(severity):
    with pytest.raises(RuleCatalogError, match="unsupported severity"):
        load_catalog_data(catalog(detection(severity=severity)))


@pytest.mark.parametrize("operator", [[], {}])
def test_rejects_unhashable_operators(operator):
    with pytest.raises(RuleCatalogError, match="unsupported operator"):
        load_catalog_data(catalog(detection(operator=operator)))
