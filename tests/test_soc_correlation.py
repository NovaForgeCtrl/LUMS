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
    assert matches[0].event_timestamps == (
        ("e1", "2026-10-28T10:00:01+00:00"),
        ("e2", "2026-10-28T10:00:10+00:00"),
        ("e3", "2026-10-28T10:00:20+00:00"),
    )
    assert "within 60s" in matches[0].reason

    serialized = matches[0].to_dict()
    assert serialized["event_timestamps"] == [
        {"event_id": "e1", "timestamp": "2026-10-28T10:00:01+00:00"},
        {"event_id": "e2", "timestamp": "2026-10-28T10:00:10+00:00"},
        {"event_id": "e3", "timestamp": "2026-10-28T10:00:20+00:00"},
    ]


def test_correlation_match_rejects_non_chronological_timestamps():
    matches = CorrelationEngine().correlate(
        [event("e1", 1), event("e2", 10), event("e3", 20)],
        [rule()],
    )
    match = matches[0]

    with pytest.raises(ValueError, match="must be chronological"):
        type(match)(
            rule_id=match.rule_id,
            rule_name=match.rule_name,
            severity=match.severity,
            event_type=match.event_type,
            group_value=match.group_value,
            event_ids=match.event_ids,
            event_timestamps=(
                ("e1", "2026-10-28T10:00:20+00:00"),
                ("e2", "2026-10-28T10:00:10+00:00"),
                ("e3", "2026-10-28T10:00:01+00:00"),
            ),
            first_seen="2026-10-28T10:00:01+00:00",
            last_seen="2026-10-28T10:00:20+00:00",
            count=3,
            window_seconds=60,
            reason=match.reason,
        )


def test_correlation_match_rejects_inconsistent_seen_bounds():
    matches = CorrelationEngine().correlate(
        [event("e1", 1), event("e2", 10), event("e3", 20)],
        [rule()],
    )
    match = matches[0]

    with pytest.raises(ValueError, match="timestamp bounds"):
        type(match)(
            rule_id=match.rule_id,
            rule_name=match.rule_name,
            severity=match.severity,
            event_type=match.event_type,
            group_value=match.group_value,
            event_ids=match.event_ids,
            event_timestamps=match.event_timestamps,
            first_seen="2026-10-28T10:00:02+00:00",
            last_seen=match.last_seen,
            count=3,
            window_seconds=60,
            reason=match.reason,
        )


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


def test_inactivity_defaults_to_correlation_window():
    configured = rule(window_seconds=90)

    assert configured.inactivity_seconds == 90


def test_inactivity_can_be_configured_independently():
    configured = rule(window_seconds=90, inactivity_seconds=240)

    assert configured.window_seconds == 90
    assert configured.inactivity_seconds == 240


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "60"])
def test_invalid_inactivity_seconds_are_rejected(value):
    with pytest.raises(ValueError, match="inactivity_seconds"):
        rule(inactivity_seconds=value)


@pytest.mark.parametrize("severity", [[], {}])
def test_correlation_rule_rejects_unhashable_severities(severity):
    with pytest.raises(ValueError, match="Unsupported severity"):
        rule(severity=severity)


def test_inactivity_boundary_splits_groups_but_allows_exact_boundary():
    def timed_event(event_id, timestamp):
        return SecurityEvent(
            event_id=event_id,
            source="lab-host",
            event_type="auth.failure",
            fields={"username": "alice"},
            timestamp=timestamp,
        )

    events = [
        timed_event("e1", "2026-10-28T10:00:00+00:00"),
        timed_event("e2", "2026-10-28T10:01:00+00:00"),
        timed_event("e3", "2026-10-28T10:02:01+00:00"),
        timed_event("e4", "2026-10-28T10:02:30+00:00"),
    ]

    matches = CorrelationEngine().correlate(
        events,
        [
            rule(
                window_seconds=300,
                inactivity_seconds=60,
                minimum_count=2,
            )
        ],
    )

    assert [match.event_ids for match in matches] == [
        ("e1", "e2"),
        ("e3", "e4"),
    ]
    assert [match.count for match in matches] == [2, 2]

def test_window_limit_applies_even_when_inactivity_limit_is_larger():
    def timed_event(event_id, timestamp):
        return SecurityEvent(
            event_id=event_id,
            source="lab-host",
            event_type="auth.failure",
            fields={"username": "alice"},
            timestamp=timestamp,
        )

    events = [
        timed_event("e1", "2026-10-28T10:00:01+00:00"),
        timed_event("e2", "2026-10-28T10:00:30+00:00"),
        timed_event("e3", "2026-10-28T10:00:59+00:00"),
    ]

    matches = CorrelationEngine().correlate(
        events,
        [
            rule(
                window_seconds=20,
                inactivity_seconds=120,
                minimum_count=2,
            )
        ],
    )

    assert matches == []
