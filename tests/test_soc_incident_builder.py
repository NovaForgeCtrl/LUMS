from dataclasses import replace

import pytest

from server.soc.correlation import CorrelationMatch
from server.soc.incident_builder import IncidentBuilder
from server.soc.models import DetectionMatch
from server.soc.pipeline import PipelineResult


TIMESTAMP = "2026-10-28T10:00:00+00:00"


def detection(
    *,
    rule_id="rule-login",
    event_id="event-1",
    severity="warning",
):
    return DetectionMatch(
        rule_id=rule_id,
        rule_name="Repeated login failure",
        severity=severity,
        event_id=event_id,
        event_source="auth-host",
        event_type="login_failure",
        event_timestamp=TIMESTAMP,
        field="result",
        operator="eq",
        expected="failed",
        observed="failed",
        reason="result matched expected value",
    )


def correlation(
    *,
    rule_id="corr-login",
    event_ids=("event-1", "event-2"),
    event_timestamps=None,
    severity="critical",
):
    if event_timestamps is None:
        event_timestamps = tuple(
            (
                event_id,
                TIMESTAMP if index == 0
                else "2026-10-28T10:00:30+00:00",
            )
            for index, event_id in enumerate(event_ids)
        )

    return CorrelationMatch(
        rule_id=rule_id,
        rule_name="Login failure burst",
        severity=severity,
        event_type="login_failure",
        group_value="host-a",
        event_ids=event_ids,
        event_timestamps=event_timestamps,
        first_seen=event_timestamps[0][1],
        last_seen=event_timestamps[-1][1],
        count=len(event_ids),
        window_seconds=60,
        reason="2 login failures for host-a within 60s",
    )


def result(detections=(), correlations=()):
    return PipelineResult(
        events=(),
        detections=tuple(detections),
        correlations=tuple(correlations),
        duplicates=(),
    )


def test_detection_builds_open_incident_with_detection_and_event_evidence():
    incidents = IncidentBuilder().build(result(detections=[detection()]))

    assert len(incidents) == 1
    incident = incidents[0]
    assert incident.status == "open"
    assert incident.severity == "warning"
    assert incident.title == "Detection: Repeated login failure"
    assert {item.kind for item in incident.evidence} == {"detection", "event"}
    assert {item.reference_id for item in incident.evidence} == {
        "rule-login",
        "event-1",
    }
    assert incident.created_at == TIMESTAMP


def test_correlation_builds_incident_with_all_event_evidence():
    incidents = IncidentBuilder().build(result(correlations=[correlation()]))

    assert len(incidents) == 1
    incident = incidents[0]
    assert incident.severity == "critical"
    assert incident.title == "Correlation: Login failure burst"
    assert incident.created_at == "2026-10-28T10:00:30+00:00"
    assert sum(item.kind == "correlation" for item in incident.evidence) == 1
    assert {
        item.reference_id
        for item in incident.evidence
        if item.kind == "event"
    } == {"event-1", "event-2"}


def test_correlation_event_evidence_preserves_individual_timestamps():
    incidents = IncidentBuilder().build(
        result(
            correlations=[
                correlation(
                    event_timestamps=(
                        ("event-1", "2026-10-28T10:00:05+00:00"),
                        ("event-2", "2026-10-28T10:00:30+00:00"),
                    )
                )
            ]
        )
    )

    event_evidence = {
        item.reference_id: item.observed_at
        for item in incidents[0].evidence
        if item.kind == "event"
    }

    assert event_evidence == {
        "event-1": "2026-10-28T10:00:05+00:00",
        "event-2": "2026-10-28T10:00:30+00:00",
    }

    correlation_evidence = next(
        item for item in incidents[0].evidence
        if item.kind == "correlation"
    )
    assert correlation_evidence.observed_at == "2026-10-28T10:00:30+00:00"
    assert incidents[0].created_at == "2026-10-28T10:00:30+00:00"


def test_correlation_without_event_timestamp_fails_at_model_boundary():
    with pytest.raises(ValueError, match="exactly one timestamp"):
        correlation(
            event_timestamps=(("event-1", TIMESTAMP),)
        )


def test_correlation_event_evidence_is_chronological_not_lexical():
    incidents = IncidentBuilder().build(
        result(
            correlations=[
                correlation(
                    event_ids=("event-z", "event-a"),
                    event_timestamps=(
                        ("event-z", TIMESTAMP),
                        ("event-a", "2026-10-28T10:00:30+00:00"),
                    ),
                )
            ]
        )
    )

    event_evidence = [
        item for item in incidents[0].evidence
        if item.kind == "event"
    ]

    assert [item.reference_id for item in event_evidence] == [
        "event-z",
        "event-a",
    ]
    assert [item.observed_at for item in event_evidence] == [
        TIMESTAMP,
        "2026-10-28T10:00:30+00:00",
    ]


def test_same_input_produces_stable_incident_ids_and_evidence_ids():
    builder = IncidentBuilder()
    pipeline_result = result(
        detections=[detection()],
        correlations=[correlation()],
    )

    first = builder.build(pipeline_result)
    second = builder.build(pipeline_result)

    assert [item.incident_id for item in first] == [
        item.incident_id for item in second
    ]
    assert [
        [e.evidence_id for e in item.evidence] for item in first
    ] == [
        [e.evidence_id for e in item.evidence] for item in second
    ]


def test_distinct_detection_events_produce_distinct_incidents():
    incidents = IncidentBuilder().build(
        result(
            detections=[
                detection(event_id="event-1"),
                detection(event_id="event-2"),
            ]
        )
    )

    assert len(incidents) == 2
    assert len({item.incident_id for item in incidents}) == 2


def test_distinct_rules_for_same_event_produce_distinct_incidents():
    incidents = IncidentBuilder().build(
        result(
            detections=[
                detection(rule_id="rule-a"),
                detection(rule_id="rule-b"),
            ]
        )
    )

    assert len(incidents) == 2
    assert len({item.incident_id for item in incidents}) == 2


def test_correlation_event_order_does_not_change_incident_identity():
    builder = IncidentBuilder()
    first = builder.build(
        result(correlations=[correlation(event_ids=("event-1", "event-2"))])
    )
    second = builder.build(
        result(correlations=[correlation(event_ids=("event-2", "event-1"))])
    )

    assert first[0].incident_id == second[0].incident_id


def test_output_order_is_stable():
    builder = IncidentBuilder()
    first = builder.build(
        result(
            detections=[detection(event_id="event-z"), detection(event_id="event-a")]
        )
    )
    second = builder.build(
        result(
            detections=[detection(event_id="event-a"), detection(event_id="event-z")]
        )
    )

    assert [item.incident_id for item in first] == [
        item.incident_id for item in second
    ]


def test_empty_pipeline_result_produces_no_incidents():
    assert IncidentBuilder().build(result()) == ()


def test_invalid_input_type_is_rejected():
    with pytest.raises(TypeError, match="PipelineResult"):
        IncidentBuilder().build({})


def test_serialized_incident_contains_audit_evidence():
    incidents = IncidentBuilder().build(result(detections=[detection()]))
    payload = incidents[0].to_dict()

    assert payload["evidence_count"] == 2
    assert payload["status"] == "open"
    assert payload["evidence"][0]["evidence_id"]
    assert all(item["observed_at"] for item in payload["evidence"])


def test_incident_severity_is_inherited_from_detection():
    incidents = IncidentBuilder().build(
        result(detections=[detection(severity="critical")])
    )

    assert incidents[0].severity == "critical"


def test_multiple_correlation_windows_remain_separate_when_event_sets_differ():
    first = correlation(event_ids=("event-1", "event-2"))
    second = correlation(event_ids=("event-2", "event-3"))
    incidents = IncidentBuilder().build(result(correlations=[first, second]))

    assert len(incidents) == 2
    assert incidents[0].incident_id != incidents[1].incident_id
