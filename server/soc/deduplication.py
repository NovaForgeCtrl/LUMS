"""Deterministic, in-memory event deduplication for the LUMS SOC core."""

from collections.abc import Iterable
from dataclasses import dataclass
import json
from typing import Literal

from .models import SecurityEvent


DuplicateReason = Literal["event_id", "content"]


@dataclass(frozen=True)
class DuplicateEvent:
    """Describe an event discarded as a duplicate of an earlier event."""

    original_event_id: str
    duplicate_event_id: str
    reason: DuplicateReason


@dataclass(frozen=True)
class DeduplicationResult:
    """Unique events and duplicate records from a single batch."""

    events: tuple[SecurityEvent, ...]
    duplicates: tuple[DuplicateEvent, ...]

    @property
    def unique_count(self) -> int:
        return len(self.events)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicates)

    def to_dict(self) -> dict[str, object]:
        return {
            "events": [
                {
                    "event_id": event.event_id,
                    "source": event.source,
                    "event_type": event.event_type,
                    "timestamp": event.timestamp,
                    "fields": event.fields,
                }
                for event in self.events
            ],
            "duplicates": [
                {
                    "original_event_id": item.original_event_id,
                    "duplicate_event_id": item.duplicate_event_id,
                    "reason": item.reason,
                }
                for item in self.duplicates
            ],
            "unique_count": self.unique_count,
            "duplicate_count": self.duplicate_count,
        }


class EventDeduplicator:
    """Remove repeated events within one batch without external side effects.

    Duplicate detection uses two checks, in order:
    1. Repeated event IDs.
    2. Identical source, type, timestamp, and fields.

    Event order is preserved. This class does not retain state between calls.
    """

    @staticmethod
    def _fingerprint(event: SecurityEvent) -> str:
        canonical = {
            "source": event.source,
            "event_type": event.event_type,
            "timestamp": event.timestamp,
            "fields": event.fields,
        }
        try:
            return json.dumps(
                canonical,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Event fields must contain JSON-compatible values") from exc

    def deduplicate(
        self, events: Iterable[SecurityEvent]
    ) -> DeduplicationResult:
        if isinstance(events, (str, bytes, dict)):
            raise TypeError("events must be an iterable of SecurityEvent objects")

        unique_events: list[SecurityEvent] = []
        duplicates: list[DuplicateEvent] = []
        first_by_id: dict[str, SecurityEvent] = {}
        first_by_fingerprint: dict[str, SecurityEvent] = {}

        for event in events:
            if not isinstance(event, SecurityEvent):
                raise TypeError("all items must be SecurityEvent instances")

            existing_id = first_by_id.get(event.event_id)
            if existing_id is not None:
                duplicates.append(
                    DuplicateEvent(
                        original_event_id=existing_id.event_id,
                        duplicate_event_id=event.event_id,
                        reason="event_id",
                    )
                )
                continue

            fingerprint = self._fingerprint(event)
            existing_content = first_by_fingerprint.get(fingerprint)
            if existing_content is not None:
                duplicates.append(
                    DuplicateEvent(
                        original_event_id=existing_content.event_id,
                        duplicate_event_id=event.event_id,
                        reason="content",
                    )
                )
                # Track the ID too, so subsequent repetitions of this ID are
                # classified consistently as event-ID duplicates.
                first_by_id[event.event_id] = existing_content
                continue

            unique_events.append(event)
            first_by_id[event.event_id] = event
            first_by_fingerprint[fingerprint] = event

        return DeduplicationResult(
            events=tuple(unique_events),
            duplicates=tuple(duplicates),
        )
