import pytest

from server.soc import (
    DetectionEngine,
    DetectionError,
    DetectionRule,
    SecurityEvent,
)


def make_event(**overrides):
    data = {
        "event_id": "evt-001",
        "source": "lab-host",
        "event_type": "auth.failure",
        "fields": {"username": "demo", "failure_count": 7},
        "timestamp": "2026-10-28T10:00:00+00:00",
    }
    data.update(overrides)
    return SecurityEvent(**data)


def make_rule(**overrides):
    data = {
        "rule_id": "auth-failures",
        "name": "Repeated authentication failures",
        "event_type": "auth.failure",
        "field": "failure_count",
        "operator": "gte",
        "value": 5,
        "severity": "warning",
    }
    data.update(overrides)
    return DetectionRule(**data)


def test_matching_rule_returns_explainable_match():
    matches = DetectionEngine().evaluate(make_event(), [make_rule()])

    assert len(matches) == 1
    match = matches[0]
    assert match.rule_id == "auth-failures"
    assert match.event_id == "evt-001"
    assert match.observed == 7
    assert match.expected == 5
    assert "observed 7" in match.reason


def test_below_threshold_does_not_match():
    event = make_event(fields={"failure_count": 2})
    assert DetectionEngine().evaluate(event, [make_rule()]) == []


def test_disabled_rule_does_not_match():
    assert DetectionEngine().evaluate(
        make_event(), [make_rule(enabled=False)]
    ) == []


def test_different_event_type_does_not_match():
    rule = make_rule(event_type="process.start")
    assert DetectionEngine().evaluate(make_event(), [rule]) == []


def test_missing_field_does_not_match():
    event = make_event(fields={"username": "demo"})
    assert DetectionEngine().evaluate(event, [make_rule()]) == []


@pytest.mark.parametrize(
    ("operator", "observed", "expected", "result"),
    [
        ("eq", "admin", "admin", True),
        ("ne", "guest", "admin", True),
        ("gt", 9, 5, True),
        ("gte", 5, 5, True),
        ("lt", 2, 5, True),
        ("lte", 5, 5, True),
        ("contains", "administrator", "admin", True),
        ("in", "critical", ["warning", "critical"], True),
    ],
)
def test_supported_operators(operator, observed, expected, result):
    rule = make_rule(operator=operator, value=expected)
    event = make_event(fields={"failure_count": observed})
    assert bool(DetectionEngine().evaluate(event, [rule])) is result


def test_unknown_operator_is_rejected():
    with pytest.raises(ValueError, match="Unsupported operator"):
        make_rule(operator="python")


def test_invalid_timestamp_is_rejected():
    with pytest.raises(ValueError, match="Invalid timestamp"):
        make_event(timestamp="not-a-timestamp")


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone"):
        make_event(timestamp="2026-10-28T10:00:00")


def test_invalid_event_type_is_rejected():
    with pytest.raises(ValueError, match="event_type"):
        make_event(event_type="not a valid type")


def test_comparison_type_mismatch_is_reported():
    event = make_event(fields={"failure_count": "seven"})
    with pytest.raises(DetectionError, match="cannot compare"):
        DetectionEngine().evaluate(event, [make_rule()])


@pytest.mark.parametrize("operator", [[], {}])
def test_detection_rule_rejects_unhashable_operators(operator):
    with pytest.raises(ValueError, match="Unsupported operator"):
        make_rule(operator=operator)


@pytest.mark.parametrize("severity", [[], {}])
def test_detection_rule_rejects_unhashable_severities(severity):
    with pytest.raises(ValueError, match="Unsupported severity"):
        make_rule(severity=severity)
