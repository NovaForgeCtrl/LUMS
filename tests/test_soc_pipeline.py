import pytest

from server.soc.correlation import CorrelationRule
from server.soc.detection import DetectionRule
from server.soc.ingestion import IngestionError
from server.soc.pipeline import SOCPipeline


def event(event_id, second, username="alice", failures=4):
    return {
        "event_id": event_id,
        "source": "lab-host",
        "event_type": "auth.failure",
        "timestamp": f"2026-10-28T10:00:{second:02d}+00:00",
        "fields": {
            "username": username,
            "failure_count": failures,
        },
    }


def detection_rule():
    return DetectionRule(
        rule_id="failure-threshold",
        name="High authentication failure count",
        event_type="auth.failure",
        field="failure_count",
        operator="gte",
        value=4,
        severity="warning",
    )


def correlation_rule():
    return CorrelationRule(
        rule_id="repeat-user-failures",
        name="Repeated failures for one user",
        event_type="auth.failure",
        group_by="username",
        window_seconds=60,
        minimum_count=3,
        severity="critical",
    )


def test_pipeline_runs_ingestion_detection_and_correlation():
    result = SOCPipeline().process_batch(
        [event("evt-1", 1), event("evt-2", 10), event("evt-3", 20)],
        detection_rules=[detection_rule()],
        correlation_rules=[correlation_rule()],
    )

    assert result.event_count == 3
    assert result.detection_count == 3
    assert result.correlation_count == 1
    assert result.duplicate_count == 0
    assert result.correlations[0].group_value == "alice"


def test_pipeline_returns_empty_result_for_empty_batch():
    result = SOCPipeline().process_batch([])

    assert result.event_count == 0
    assert result.detections == ()
    assert result.correlations == ()
    assert result.duplicates == ()


def test_pipeline_rejects_invalid_batch_without_partial_result():
    with pytest.raises(IngestionError):
        SOCPipeline().process_batch([
            event("evt-1", 1),
            {"event_id": "broken"},
        ])


def test_pipeline_serializes_results_for_future_api_use():
    result = SOCPipeline().process_batch(
        [event("evt-1", 1)],
        detection_rules=[detection_rule()],
    )

    serialized = result.to_dict()
    assert serialized["event_count"] == 1
    assert serialized["detection_count"] == 1
    assert serialized["correlation_count"] == 0
    assert serialized["duplicate_count"] == 0
    assert serialized["detections"][0]["rule_id"] == "failure-threshold"


def test_pipeline_does_not_emit_detection_for_below_threshold():
    result = SOCPipeline().process_batch(
        [event("evt-1", 1, failures=1)],
        detection_rules=[detection_rule()],
    )

    assert result.detection_count == 0


def test_pipeline_keeps_different_users_separate():
    result = SOCPipeline().process_batch(
        [
            event("evt-1", 1, username="alice"),
            event("evt-2", 2, username="bob"),
            event("evt-3", 3, username="alice"),
        ],
        correlation_rules=[
            CorrelationRule(
                rule_id="two-failures",
                name="Two failures per user",
                event_type="auth.failure",
                group_by="username",
                window_seconds=60,
                minimum_count=2,
            )
        ],
    )

    assert result.correlation_count == 1
    assert result.correlations[0].group_value == "alice"


def test_pipeline_serialization_includes_event_details():
    result = SOCPipeline().process_batch([event("evt-1", 1)])
    item = result.to_dict()["events"][0]

    assert item["event_id"] == "evt-1"
    assert item["source"] == "lab-host"
    assert item["fields"]["username"] == "alice"


def test_pipeline_deduplicates_repeated_event_id_before_detection():
    result = SOCPipeline().process_batch(
        [
            event("evt-1", 1),
            event("evt-1", 2, username="bob"),
        ],
        detection_rules=[detection_rule()],
    )

    assert result.event_count == 1
    assert result.detection_count == 1
    assert result.duplicate_count == 1
    assert result.duplicates[0].reason == "event_id"
    assert result.duplicates[0].original_event_id == "evt-1"


def test_pipeline_deduplicates_identical_content_before_correlation():
    result = SOCPipeline().process_batch(
        [
            event("evt-1", 1),
            event("evt-2", 1),
            event("evt-3", 10),
        ],
        correlation_rules=[correlation_rule()],
    )

    assert result.event_count == 2
    assert result.duplicate_count == 1
    assert result.duplicates[0].reason == "content"
    assert result.correlation_count == 0


def test_pipeline_reports_duplicate_details_in_serialized_result():
    result = SOCPipeline().process_batch(
        [event("evt-1", 1), event("evt-2", 1)]
    )

    serialized = result.to_dict()

    assert serialized["duplicate_count"] == 1
    assert serialized["duplicates"][0] == {
        "original_event_id": "evt-1",
        "duplicate_event_id": "evt-2",
        "reason": "content",
    }


def test_pipeline_keeps_distinct_timestamps_as_distinct_events():
    result = SOCPipeline().process_batch(
        [event("evt-1", 1), event("evt-2", 2)]
    )

    assert result.event_count == 2
    assert result.duplicate_count == 0
