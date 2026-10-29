"""Orchestration layer connecting ingestion, deduplication, detection, and correlation."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .correlation import CorrelationEngine, CorrelationMatch, CorrelationRule
from .deduplication import (
    DuplicateEvent,
    EventDeduplicator,
)
from .detection import DetectionEngine
from .ingestion import EventIngestor
from .models import DetectionMatch, DetectionRule, SecurityEvent


@dataclass(frozen=True)
class PipelineResult:
    """Immutable result of processing one batch of input events."""

    events: tuple[SecurityEvent, ...]
    detections: tuple[DetectionMatch, ...]
    correlations: tuple[CorrelationMatch, ...]
    duplicates: tuple[DuplicateEvent, ...]

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def detection_count(self) -> int:
        return len(self.detections)

    @property
    def correlation_count(self) -> int:
        return len(self.correlations)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_count": self.event_count,
            "detection_count": self.detection_count,
            "correlation_count": self.correlation_count,
            "duplicate_count": self.duplicate_count,
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
            "detections": [item.to_dict() for item in self.detections],
            "correlations": [item.to_dict() for item in self.correlations],
            "duplicates": [
                {
                    "original_event_id": item.original_event_id,
                    "duplicate_event_id": item.duplicate_event_id,
                    "reason": item.reason,
                }
                for item in self.duplicates
            ],
        }


class SOCPipeline:
    """Validate and analyze a bounded batch without external side effects."""

    def __init__(
        self,
        *,
        ingestor: EventIngestor | None = None,
        deduplicator: EventDeduplicator | None = None,
        detection_engine: DetectionEngine | None = None,
        correlation_engine: CorrelationEngine | None = None,
    ) -> None:
        self.ingestor = ingestor or EventIngestor()
        self.deduplicator = deduplicator or EventDeduplicator()
        self.detection_engine = detection_engine or DetectionEngine()
        self.correlation_engine = correlation_engine or CorrelationEngine()

    def process_batch(
        self,
        payloads: Iterable[Mapping[str, Any]],
        *,
        detection_rules: Iterable[DetectionRule] = (),
        correlation_rules: Iterable[CorrelationRule] = (),
    ) -> PipelineResult:
        """Validate all inputs, deduplicate events, then run analysis."""
        validated_events = self.ingestor.ingest_batch(payloads)
        deduplication = self.deduplicator.deduplicate(validated_events)
        events = deduplication.events

        detection_rule_list = list(detection_rules)
        correlation_rule_list = list(correlation_rules)

        detections: list[DetectionMatch] = []
        for event in events:
            detections.extend(
                self.detection_engine.evaluate(event, detection_rule_list)
            )

        correlations = self.correlation_engine.correlate(
            events, correlation_rule_list
        )

        return PipelineResult(
            events=events,
            detections=tuple(detections),
            correlations=tuple(correlations),
            duplicates=deduplication.duplicates,
        )
