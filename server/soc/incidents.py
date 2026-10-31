"""Pure domain model for auditable LUMS SOC incidents."""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Literal
import re


IncidentStatus = Literal["open", "investigating", "resolved"]
IncidentSeverity = Literal["info", "warning", "critical"]
EvidenceKind = Literal["event", "detection", "correlation"]

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_STATUSES = {"open", "investigating", "resolved"}
_SEVERITIES = {"info", "warning", "critical"}
_EVIDENCE_KINDS = {"event", "detection", "correlation"}


def _validate_identifier(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field_name} must be a valid identifier")


def _validate_timestamp(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a timezone-aware ISO timestamp")
    normalized = (
        value[:-1] + "+00:00" if value.endswith("Z") else value
    )
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be a timezone-aware ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must be a timezone-aware ISO timestamp")


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class IncidentEvidence:
    """One auditable piece of evidence attached to an incident."""

    evidence_id: str
    kind: EvidenceKind
    reference_id: str
    description: str
    observed_at: str

    def __post_init__(self) -> None:
        _validate_identifier(self.evidence_id, "evidence_id")
        _validate_identifier(self.reference_id, "reference_id")
        if self.kind not in _EVIDENCE_KINDS:
            raise ValueError("kind must be event, detection, or correlation")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must not be empty")
        _validate_timestamp(self.observed_at, "observed_at")

    def to_dict(self) -> dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "reference_id": self.reference_id,
            "description": self.description,
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True)
class Incident:
    """Immutable incident snapshot; transitions return a new snapshot."""

    incident_id: str
    title: str
    summary: str
    severity: IncidentSeverity
    status: IncidentStatus
    created_at: str
    updated_at: str
    evidence: tuple[IncidentEvidence, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier(self.incident_id, "incident_id")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must not be empty")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("summary must not be empty")
        if self.severity not in _SEVERITIES:
            raise ValueError("severity must be info, warning, or critical")
        if self.status not in _STATUSES:
            raise ValueError("status must be open, investigating, or resolved")
        _validate_timestamp(self.created_at, "created_at")
        _validate_timestamp(self.updated_at, "updated_at")
        if not isinstance(self.evidence, tuple):
            raise ValueError("evidence must be a tuple")
        if any(not isinstance(item, IncidentEvidence) for item in self.evidence):
            raise ValueError("evidence items must be IncidentEvidence instances")
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence IDs must be unique within an incident")

    @classmethod
    def create(
        cls,
        *,
        incident_id: str,
        title: str,
        summary: str,
        severity: IncidentSeverity,
        evidence: tuple[IncidentEvidence, ...] = (),
        created_at: str | None = None,
    ) -> "Incident":
        timestamp = (
            created_at if created_at is not None else utc_now_iso()
        )
        return cls(
            incident_id=incident_id,
            title=title,
            summary=summary,
            severity=severity,
            status="open",
            created_at=timestamp,
            updated_at=timestamp,
            evidence=evidence,
        )

    def transition(
        self,
        new_status: IncidentStatus,
        *,
        updated_at: str | None = None,
    ) -> "Incident":
        """Return a new incident snapshot after a permitted status transition."""
        if new_status not in _STATUSES:
            raise ValueError("unsupported incident status")
        allowed = {
            "open": {"investigating", "resolved"},
            "investigating": {"open", "resolved"},
            "resolved": {"open"},
        }
        if new_status == self.status:
            return self
        if new_status not in allowed[self.status]:
            raise ValueError(
                f"transition from {self.status} to {new_status} is not allowed"
            )
        timestamp = (
            updated_at if updated_at is not None else utc_now_iso()
        )
        _validate_timestamp(timestamp, "updated_at")
        return replace(self, status=new_status, updated_at=timestamp)

    def add_evidence(
        self,
        evidence: IncidentEvidence,
        *,
        updated_at: str | None = None,
    ) -> "Incident":
        """Return a new snapshot with evidence appended exactly once."""
        if not isinstance(evidence, IncidentEvidence):
            raise TypeError("evidence must be an IncidentEvidence instance")
        for existing in self.evidence:
            if existing.evidence_id == evidence.evidence_id:
                if existing != evidence:
                    raise ValueError(
                        "evidence_id already exists with different content"
                    )
                return self
        timestamp = (
            updated_at if updated_at is not None else utc_now_iso()
        )
        _validate_timestamp(timestamp, "updated_at")
        return replace(
            self,
            evidence=self.evidence + (evidence,),
            updated_at=timestamp,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "summary": self.summary,
            "severity": self.severity,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "evidence_count": len(self.evidence),
            "evidence": [item.to_dict() for item in self.evidence],
        }
