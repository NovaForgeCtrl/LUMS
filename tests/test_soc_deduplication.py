import pytest

from server.soc.deduplication import EventDeduplicator
from server.soc.models import SecurityEvent


def make_event(
    event_id="event-1",
    *,
    source="host-1",
    event_type="login.failed",
    timestamp="2026-10-28T10:00:00+00:00",
    fields=None,
):
    return SecurityEvent(
        event_id=event_id,
        source=source,
        event_type=event_type,
        timestamp=timestamp,
        fields=fields if fields is not None else {"user": "alice", "count": 1},
    )


def test_keeps_unique_events_in_input_order():
    events = [
        make_event("event-1"),
        make_event("event-2", fields={"user": "bob"}),
    ]

    result = EventDeduplicator().deduplicate(events)

    assert result.events == tuple(events)
    assert result.duplicates == ()
    assert result.unique_count == 2
    assert result.duplicate_count == 0


def test_deduplicates_repeated_event_id():
    first = make_event("event-1")
    repeated_id = make_event(
        "event-1",
        fields={"user": "different", "count": 99},
    )

    result = EventDeduplicator().deduplicate([first, repeated_id])

    assert result.events == (first,)
    assert result.duplicate_count == 1
    assert result.duplicates[0].reason == "event_id"
    assert result.duplicates[0].original_event_id == "event-1"


def test_deduplicates_identical_content_with_different_ids():
    first = make_event("event-1")
    repeated_content = make_event("event-2")

    result = EventDeduplicator().deduplicate([first, repeated_content])

    assert result.events == (first,)
    assert result.duplicates[0].reason == "content"
    assert result.duplicates[0].duplicate_event_id == "event-2"


@pytest.mark.parametrize(
    "changes",
    [
        {"source": "host-2"},
        {"event_type": "login.success"},
        {"timestamp": "2026-10-28T10:00:01+00:00"},
        {"fields": {"user": "bob", "count": 1}},
    ],
)
def test_different_fingerprint_is_not_a_duplicate(changes):
    first = make_event("event-1")
    second = make_event("event-2", **changes)

    result = EventDeduplicator().deduplicate([first, second])

    assert result.unique_count == 2
    assert result.duplicate_count == 0


def test_repeated_content_then_repeated_id_is_classified_consistently():
    first = make_event("event-1")
    same_content = make_event("event-2")
    repeat_second_id = make_event(
        "event-2",
        fields={"user": "someone-else"},
    )

    result = EventDeduplicator().deduplicate(
        [first, same_content, repeat_second_id]
    )

    assert result.unique_count == 1
    assert [item.reason for item in result.duplicates] == [
        "content",
        "event_id",
    ]


def test_deduplication_has_no_state_between_calls():
    event = make_event()
    deduplicator = EventDeduplicator()

    first_result = deduplicator.deduplicate([event])
    second_result = deduplicator.deduplicate([event])

    assert first_result.unique_count == 1
    assert second_result.unique_count == 1


def test_result_serializes_counts_and_duplicate_reasons():
    result = EventDeduplicator().deduplicate(
        [make_event("event-1"), make_event("event-2")]
    )

    serialized = result.to_dict()

    assert serialized["unique_count"] == 1
    assert serialized["duplicate_count"] == 1
    assert serialized["duplicates"][0]["reason"] == "content"


def test_rejects_non_event_items():
    with pytest.raises(TypeError, match="SecurityEvent"):
        EventDeduplicator().deduplicate([{"event_id": "event-1"}])


def test_rejects_string_as_event_collection():
    with pytest.raises(TypeError, match="iterable of SecurityEvent"):
        EventDeduplicator().deduplicate("not-a-batch")
