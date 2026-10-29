"""Deterministic incident creation from LUMS SOC pipeline results."""

from hashlib import sha256
import json

from .incidents import Incident, IncidentEvidence
from .pipeline import PipelineResult


def _stable_id(prefix: str, *parts: object) -> str:
    """Create a deterministic, identifier-safe ID from structured values."""
    payload = json.dumps(
        parts,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    digest = sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}-{digest}"


class IncidentBuilder:
    """Convert detections and correlations into auditable incidents.

    Each detection creates one incident per rule/event pair.
    Each correlation creates one incident per rule/event-window pair.
    Reprocessing the same pipeline result therefore produces stable IDs.
    This builder does not persist incidents or perform response actions.
    """

    def build(self, result: PipelineResult) -> tuple[Incident, ...]:
        if not isinstance(result, PipelineResult):
            raise TypeError("result must be a PipelineResult")

        incidents: list[Incident] = []

        for match in result.detections:
            incident_id = _stable_id(
                "inc", "detection", match.rule_id, match.event_id
            )
            evidence = (
                IncidentEvidence(
                    evidence_id=_stable_id(
                        "ev", "detection", match.rule_id, match.event_id
                    ),
                    kind="detection",
                    reference_id=match.rule_id,
                    description=(
                        f"Detection rule '{match.rule_name}' matched: "
                        f"{match.reason}"
                    ),
                    observed_at=match.event_timestamp,
                ),
                IncidentEvidence(
                    evidence_id=_stable_id("ev", "event", match.event_id),
                    kind="event",
                    reference_id=match.event_id,
                    description=(
                        f"Event {match.event_id} from {match.event_source} "
                        f"({match.event_type})"
                    ),
                    observed_at=match.event_timestamp,
                ),
            )
            incidents.append(
                Incident.create(
                    incident_id=incident_id,
                    title=f"Detection: {match.rule_name}",
                    summary=match.reason,
                    severity=match.severity,
                    evidence=evidence,
                    created_at=match.event_timestamp,
                )
            )

        for match in result.correlations:
            ordered_event_ids = tuple(sorted(set(match.event_ids)))
            incident_id = _stable_id(
                "inc",
                "correlation",
                match.rule_id,
                ordered_event_ids,
            )
            evidence = [
                IncidentEvidence(
                    evidence_id=_stable_id(
                        "ev",
                        "correlation",
                        match.rule_id,
                        ordered_event_ids,
                    ),
                    kind="correlation",
                    reference_id=match.rule_id,
                    description=(
                        f"Correlation rule '{match.rule_name}' matched: "
                        f"{match.reason}"
                    ),
                    observed_at=match.last_seen,
                )
            ]
            for event_id in ordered_event_ids:
                evidence.append(
                    IncidentEvidence(
                        evidence_id=_stable_id("ev", "event", event_id),
                        kind="event",
                        reference_id=event_id,
                        description=(
                            f"Event {event_id} contributed to correlation "
                            f"rule {match.rule_id}"
                        ),
                        observed_at=match.last_seen,
                    )
                )

            incidents.append(
                Incident.create(
                    incident_id=incident_id,
                    title=f"Correlation: {match.rule_name}",
                    summary=match.reason,
                    severity=match.severity,
                    evidence=tuple(evidence),
                    created_at=match.last_seen,
                )
            )

        # Stable output order, independent of the order in the input tuples.
        incidents.sort(key=lambda item: item.incident_id)
        return tuple(incidents)
