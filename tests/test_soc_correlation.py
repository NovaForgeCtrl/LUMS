import pytest

from server.soc.correlation import CorrelationEngine, CorrelationRule
from server.soc.models import SecurityEvent


def event(event_id, second, username="alice", event_type="auth.failure"):
    return SecurityEvent(
        event_id=event_id,
        source="lab-host",
        event_type=event_type,
        fields={"username": username},
        timestamp=f"2026-10-28T10:00:{second:02d}+00:00",
    )


def rule(**overrides):
    data = {
        "rule_id": "repeat-auth-failures",
        "name": "Repeated authentication failures",
        "event_type": "auth.failure",
        "group_by": "username",
        "window_seconds": 60,
        "minimum_count": 3,
        "severity": "critical",
    }
    data.update(overrides)
    return CorrelationRule(**data)


def test_correlates_same_user_inside_time_window():
    matches = CorrelationEngine().correlate(
        [event("e1", 1), event("e2", 10), event("e3", 20)],
        [rule()],
    )

    assert len(matches) == 1
    assert matches[0].count == 3
    assert matches[0].group_value == "alice"
    assert set(matches[0].event_ids) == {"e1", "e2", "e3"}
    assert "within 60s" in matches[0].reason


def test_different_group_values_are_separated():
    matches = CorrelationEngine().correlate(
        [
            event("e1", 1, "alice"),
            event("e2", 2, "bob"),
            event("e3", 3, "alice"),
            event("e4", 4, "bob"),
        ],
        [rule(minimum_count=2)],
    )

    assert len(matches) == 2
    assert {match.group_value for match in matches} == {"alice", "bob"}


def test_events_outside_window_do_not_correlate():
    matches = CorrelationEngine().correlate(
        [event("e1", 1), event("e2", 30), event("e3", 59)],
        [rule(window_seconds=20)],
    )

    assert matches == []


def test_events_of_other_type_are_ignored():
    matches = CorrelationEngine().correlate(
        [
            event("e1", 1),
            event("e2", 2),
            event("e3", 3, event_type="process.start"),
        ],
        [rule(minimum_count=3)],
    )

    assert matches == []


def test_disabled_rule_is_ignored():
    assert CorrelationEngine().correlate(
        [event("e1", 1), event("e2", 2), event("e3", 3)],
        [rule(enabled=False)],
    ) == []


def test_missing_group_field_is_ignored():
    item = SecurityEvent(
        event_id="e2",
        source="lab-host",
        event_type="auth.failure",
        fields={},
        timestamp="2026-10-28T10:00:02+00:00",
    )
    assert CorrelationEngine().correlate(
        [event("e1", 1), item, event("e3", 3)],
        [rule(minimum_count=3)],
    ) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("window_seconds", 0),
        ("window_seconds", -1),
        ("minimum_count", 1),
        ("minimum_count", True),
        ("window_seconds", True),
    ],
)
def test_invalid_window_configuration_is_rejected(field, value):
    with pytest.raises(ValueError):
        rule(**{field: value})


def test_non_event_input_is_rejected():
    with pytest.raises(ValueError, match="SecurityEvent"):
        CorrelationEngine().correlate(["not-an-event"], [rule()])
