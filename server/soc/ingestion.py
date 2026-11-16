"""Input validation and normalization for the LUMS SOC event pipeline.

This module deliberately performs no network I/O, persistence, detection,
correlation, or automated response.
"""

from collections.abc import Mapping, Iterable
import json
from typing import Any

from .models import SecurityEvent


class IngestionError(ValueError):
    """An incoming event is invalid or exceeds configured limits."""


class EventIngestor:
    """Validate event payloads and convert them to SecurityEvent instances."""

    REQUIRED_KEYS = frozenset({
        "event_id",
        "source",
        "event_type",
        "fields",
    })
    OPTIONAL_KEYS = frozenset({"timestamp"})
    ALLOWED_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS

    def __init__(
        self,
        *,
        max_event_bytes: int = 64 * 1024,
        max_depth: int = 8,
        max_nodes: int = 2048,
        max_string_length: int = 4096,
        max_batch_events: int = 500,
    ) -> None:
        limits = {
            "max_event_bytes": max_event_bytes,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "max_string_length": max_string_length,
            "max_batch_events": max_batch_events,
        }
        for name, value in limits.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")

        self.max_event_bytes = max_event_bytes
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.max_string_length = max_string_length
        self.max_batch_events = max_batch_events

    def ingest(self, payload: Mapping[str, Any]) -> SecurityEvent:
        """Validate one mapping and return a normalized event."""
        if not isinstance(payload, Mapping):
            raise IngestionError("Event payload must be an object")

        try:
            # Copy the top-level mapping so caller mutation cannot change
            # the payload while it is being validated.
            data = dict(payload)
            self._validate_keys(data)

            encoded = json.dumps(
                data,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except IngestionError:
            raise
        except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
            raise IngestionError("Event is not valid JSON data") from exc

        if len(encoded) > self.max_event_bytes:
            raise IngestionError("Event exceeds maximum encoded size")

        self._validate_tree(data)

        try:
            event = SecurityEvent(
                event_id=data["event_id"],
                source=data["source"],
                event_type=data["event_type"],
                fields=data["fields"],
                timestamp=data.get("timestamp"),
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise IngestionError(f"Invalid event: {exc}") from exc

        return event

    def ingest_json(self, raw: str | bytes) -> SecurityEvent:
        """Decode and validate one JSON document."""
        if isinstance(raw, bytes):
            if len(raw) > self.max_event_bytes:
                raise IngestionError("Event exceeds maximum encoded size")
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise IngestionError("Event must be UTF-8 encoded") from exc
        elif not isinstance(raw, str):
            raise IngestionError("JSON input must be text or UTF-8 bytes")

        if len(raw.encode("utf-8")) > self.max_event_bytes:
            raise IngestionError("Event exceeds maximum encoded size")

        def reject_constant(value: str) -> None:
            raise ValueError(f"Invalid JSON constant: {value}")

        try:
            payload = json.loads(raw, parse_constant=reject_constant)
        except (json.JSONDecodeError, ValueError, RecursionError) as exc:
            raise IngestionError("Malformed JSON event") from exc

        if not isinstance(payload, dict):
            raise IngestionError("JSON event must be an object")

        return self.ingest(payload)

    def ingest_batch(
        self,
        payloads: Iterable[Mapping[str, Any]],
    ) -> list[SecurityEvent]:
        """Validate a bounded batch; no partial result is returned on failure."""
        if isinstance(payloads, (str, bytes, Mapping)):
            raise IngestionError("Batch must be an iterable of event objects")

        results: list[SecurityEvent] = []
        try:
            for payload in payloads:
                if len(results) >= self.max_batch_events:
                    raise IngestionError("Batch exceeds maximum event count")
                results.append(self.ingest(payload))
        except IngestionError:
            raise
        except (TypeError, RuntimeError) as exc:
            raise IngestionError("Could not read event batch") from exc

        return results

    def _validate_keys(self, data: dict[str, Any]) -> None:
        missing = self.REQUIRED_KEYS - data.keys()
        unknown = data.keys() - self.ALLOWED_KEYS

        if missing:
            raise IngestionError(
                "Missing required fields: " + ", ".join(sorted(missing))
            )
        if unknown:
            raise IngestionError(
                "Unknown top-level fields: " + ", ".join(sorted(unknown))
            )

        if not isinstance(data["fields"], dict):
            raise IngestionError("'fields' must be an object")

    def _validate_tree(self, root: Any) -> None:
        """Bound the JSON tree and reject non-JSON Python values."""
        node_count = 0
        stack: list[tuple[Any, int]] = [(root, 0)]

        while stack:
            value, depth = stack.pop()
            node_count += 1

            if node_count > self.max_nodes:
                raise IngestionError("Event exceeds maximum value count")
            if depth > self.max_depth:
                raise IngestionError("Event exceeds maximum nesting depth")

            if value is None or isinstance(value, (bool, int)):
                continue

            if isinstance(value, float):
                # json.dumps rejects NaN/Infinity; finite values are safe.
                continue

            if isinstance(value, str):
                if len(value) > self.max_string_length:
                    raise IngestionError("Event contains an oversized string")
                continue

            if isinstance(value, list):
                stack.extend((item, depth + 1) for item in value)
                continue

            if isinstance(value, dict):
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise IngestionError("Object keys must be strings")
                    if len(key) > self.max_string_length:
                        raise IngestionError("Event contains an oversized key")
                    stack.append((key, depth + 1))
                    stack.append((item, depth + 1))
                continue

            raise IngestionError(
                f"Unsupported value type: {type(value).__name__}"
            )
