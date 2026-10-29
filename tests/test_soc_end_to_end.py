"""End-to-end tests for the in-memory LUMS SOC processing chain."""

from server.soc.correlation import CorrelationRule
from server.soc.incident_builder import IncidentBuilder
from server.soc.models import DetectionRule
from server.soc.pipeline import SOCPipeline


def make_event(event_id, timestamp, username="demo-user"):
    return {
        "event_id": event_id,
        "source": "demo-auth",
        "event_type": "login_failure",
        "timestamp": timestamp,
        "fields": {
            "username": username,
            "result": "failed",
        },
    }


def rules():
    detection_rules = [
        DetectionRule(
            rule_id="detect-login-failure",
            name="Login failure detected",
            event_type="login_failure",
            field="result",
            operator="eq",
            value="failed",
            severity="warning",
        )
    ]
    correlation_rules = [
        CorrelationRule(
            rule_id="correlate-login-burst",
            name="Login failure burst",
            event_type="login_failure",
            group_by="username",
            window_seconds=60,
            minimum_count=2,
            severity="critical",
        )
    ]
    return detection_rules, correlation_rules


def test_synthetic_batch_flows_through_pipeline_into_incidents():
    payloads = [
        make_event("event-1", "2026-10-28T10:00:00+00:00"),
        make_event("event-2", "2026-10-28T10:00:10+00:00"),
        make_event("event-3", "2026-10-28T10:00:20+00:00"),
    ]
    detection_rules, correlation_rules = rules()

    pipeline_result = SOCPipeline().process_batch(
        payloads,
        detection_rules=detection_rules,
        correlation_rules=correlation_rules,
    )
    incidents = IncidentBuilder().build(pipeline_result)

    assert pipeline_result.event_count == 3
    assert pipeline_result.detection_count == 3
    assert pipeline_result.correlation_count >= 1
    assert len(incidents) == (
        pipeline_result.detection_count + pipeline_result.correlation_count
    )
    assert all(incident.status == "open" for incident in incidents)
    assert any(incident.severity == "critical" for incident in incidents)
    assert all(incident.evidence for incident in incidents)


def test_duplicate_event_is_removed_before_detection_and_correlation():
    event = make_event("event-1", "2026-10-28T10:00:00+00:00")
    payloads = [
        event,
        event,
        make_event("event-2", "2026-10-28T10:00:10+00:00"),
    ]
    detection_rules, correlation_rules = rules()

    pipeline_result = SOCPipeline().process_batch(
        payloads,
        detection_rules=detection_rules,
        correlation_rules=correlation_rules,
    )
    incidents = IncidentBuilder().build(pipeline_result)

    assert pipeline_result.event_count == 2
    assert pipeline_result.duplicate_count == 1
    assert pipeline_result.detection_count == 2
    assert pipeline_result.correlation_count >= 1
    assert len(incidents) == (
        pipeline_result.detection_count + pipeline_result.correlation_count
    )


def test_same_batch_produces_same_incident_ids():
    payloads = [
        make_event("event-1", "2026-10-28T10:00:00+00:00"),
        make_event("event-2", "2026-10-28T10:00:10+00:00"),
    ]
    detection_rules, correlation_rules = rules()
    pipeline = SOCPipeline()

    first_result = pipeline.process_batch(
        payloads,
        detection_rules=detection_rules,
        correlation_rules=correlation_rules,
    )
    second_result = pipeline.process_batch(
        payloads,
        detection_rules=detection_rules,
        correlation_rules=correlation_rules,
    )

    builder = IncidentBuilder()
    first_ids = {
        item.incident_id for item in builder.build(first_result)
    }
    second_ids = {
        item.incident_id for item in builder.build(second_result)
    }

    assert first_ids == second_ids
