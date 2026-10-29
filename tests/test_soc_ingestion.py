import json

import pytest

from server.soc.ingestion import EventIngestor, IngestionError
from server.soc.models import SecurityEvent


def payload(**overrides):
    data = {
        "event_id": "evt-001",
        "source": "lab-host",
        "event_type": "auth.failure",
        "fields": {
            "username": "demo",
            "failure_count": 3,
            "context": {"origin": "test"},
        },
        "timestamp": "2026-10-28T10:00:00+01:00",
    }
    data.update(overrides)
    return data


def test_valid_event_is_normalized():
    event = EventIngestor().ingest(payload())

    assert isinstance(event, SecurityEvent)
    assert event.event_id == "evt-001"
    assert event.source == "lab-host"
    assert event.fields["failure_count"] == 3
    assert event.timestamp == "2026-10-28T09:00:00+00:00"


def test_missing_required_field_is_rejected():
    data = payload()
    del data["source"]

    with pytest.raises(IngestionError, match="Missing required fields"):
        EventIngestor().ingest(data)


def test_unknown_top_level_field_is_rejected():
    with pytest.raises(IngestionError, match="Unknown top-level fields"):
        EventIngestor().ingest(payload(untrusted_extra="unexpected"))


def test_fields_must_be_an_object():
    with pytest.raises(IngestionError, match="'fields' must be an object"):
        EventIngestor().ingest(payload(fields=["not", "an", "object"]))


def test_invalid_identifier_is_reported_as_ingestion_error():
    with pytest.raises(IngestionError, match="Invalid event_id"):
        EventIngestor().ingest(payload(event_id="not a valid identifier"))


def test_json_string_is_accepted():
    event = EventIngestor().ingest_json(json.dumps(payload()))
    assert event.event_id == "evt-001"


def test_utf8_json_bytes_are_accepted():
    data = payload(fields={"message": "Prüfung erfolgreich"})
    event = EventIngestor().ingest_json(
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    )
    assert event.fields["message"] == "Prüfung erfolgreich"


@pytest.mark.parametrize("raw", [
    "{broken json",
    "[]",
    "null",
    '{"event_id":"e","source":"s","event_type":"t","fields":{},"x":NaN}',
])
def test_malformed_or_non_object_json_is_rejected(raw):
    with pytest.raises(IngestionError):
        EventIngestor().ingest_json(raw)


def test_non_utf8_bytes_are_rejected():
    with pytest.raises(IngestionError, match="UTF-8"):
        EventIngestor().ingest_json(b"\xff\xfe")


def test_event_size_limit_is_enforced():
    ingestor = EventIngestor(max_event_bytes=100)

    with pytest.raises(IngestionError, match="maximum encoded size"):
        ingestor.ingest(payload(fields={"message": "x" * 500}))


def test_string_limit_is_enforced():
    ingestor = EventIngestor(max_string_length=10)

    with pytest.raises(IngestionError, match="oversized string"):
        ingestor.ingest(payload(fields={"message": "x" * 11}))


def test_nesting_depth_limit_is_enforced():
    nested = "leaf"
    for _ in range(5):
        nested = {"child": nested}

    ingestor = EventIngestor(max_depth=3)

    with pytest.raises(IngestionError, match="nesting depth"):
        ingestor.ingest(payload(fields={"nested": nested}))


def test_node_count_limit_is_enforced():
    ingestor = EventIngestor(max_nodes=8)

    with pytest.raises(IngestionError, match="value count"):
        ingestor.ingest(payload(fields={"many": list(range(20))}))


def test_nan_is_rejected():
    with pytest.raises(IngestionError, match="valid JSON data"):
        EventIngestor().ingest(payload(fields={"value": float("nan")}))


def test_batch_returns_all_validated_events():
    ingestor = EventIngestor()
    result = ingestor.ingest_batch([
        payload(event_id="evt-001"),
        payload(event_id="evt-002"),
    ])

    assert [item.event_id for item in result] == ["evt-001", "evt-002"]


def test_batch_limit_is_enforced_without_returning_partial_results():
    ingestor = EventIngestor(max_batch_events=2)

    with pytest.raises(IngestionError, match="maximum event count"):
        ingestor.ingest_batch([
            payload(event_id="evt-001"),
            payload(event_id="evt-002"),
            payload(event_id="evt-003"),
        ])


def test_invalid_batch_member_fails_the_whole_batch():
    ingestor = EventIngestor()

    with pytest.raises(IngestionError):
        ingestor.ingest_batch([
            payload(event_id="evt-001"),
            {"event_id": "missing-other-fields"},
        ])


@pytest.mark.parametrize("setting", [
    "max_event_bytes",
    "max_depth",
    "max_nodes",
    "max_string_length",
    "max_batch_events",
])
def test_limits_must_be_positive_integers(setting):
    with pytest.raises(ValueError):
        EventIngestor(**{setting: 0})


def test_batch_input_must_be_an_iterable_of_objects():
    with pytest.raises(IngestionError, match="iterable of event objects"):
        EventIngestor().ingest_batch(payload())
