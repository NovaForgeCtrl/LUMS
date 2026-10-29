import pytest

from server.soc.incidents import Incident, IncidentEvidence


CREATED = "2026-10-28T10:00:00+00:00"
UPDATED = "2026-10-28T10:05:00+00:00"


def evidence(evidence_id="ev-1", kind="event", reference_id="evt-1"):
    return IncidentEvidence(
        evidence_id=evidence_id,
        kind=kind,
        reference_id=reference_id,
        description="Authentication failure observed",
        observed_at=CREATED,
    )


def incident():
    return Incident.create(
        incident_id="inc-1",
        title="Repeated authentication failures",
        summary="Several authentication failures were detected.",
        severity="warning",
        evidence=(evidence(),),
        created_at=CREATED,
    )


def test_create_starts_open_and_preserves_evidence():
    item = incident()

    assert item.status == "open"
    assert item.created_at == CREATED
    assert item.updated_at == CREATED
    assert len(item.evidence) == 1


def test_transition_to_investigating_returns_new_snapshot():
    original = incident()
    changed = original.transition("investigating", updated_at=UPDATED)

    assert original.status == "open"
    assert changed.status == "investigating"
    assert changed.updated_at == UPDATED
    assert changed is not original


def test_resolve_and_reopen_are_supported():
    resolved = incident().transition("resolved", updated_at=UPDATED)
    reopened = resolved.transition("open", updated_at="2026-10-28T10:10:00+00:00")

    assert resolved.status == "resolved"
    assert reopened.status == "open"


def test_invalid_status_transition_is_rejected():
    with pytest.raises(ValueError, match="not allowed"):
        incident().transition("open", updated_at=UPDATED) if False else incident().transition(
            "investigating", updated_at=UPDATED
        ).transition("open", updated_at=UPDATED).transition(
            "investigating", updated_at=UPDATED
        ).transition("open", updated_at=UPDATED).transition(
            "investigating", updated_at=UPDATED
        ).transition("resolved", updated_at=UPDATED).transition(
            "investigating", updated_at=UPDATED
        )


def test_duplicate_evidence_is_not_added_twice():
    original = incident()
    changed = original.add_evidence(evidence(), updated_at=UPDATED)

    assert changed is original
    assert len(changed.evidence) == 1


def test_new_evidence_returns_new_snapshot():
    original = incident()
    extra = evidence("ev-2", "detection", "rule-1")

    changed = original.add_evidence(extra, updated_at=UPDATED)

    assert len(original.evidence) == 1
    assert len(changed.evidence) == 2
    assert changed.updated_at == UPDATED
    assert changed.evidence[-1] == extra


def test_serialization_includes_status_severity_and_evidence():
    serialized = incident().to_dict()

    assert serialized["incident_id"] == "inc-1"
    assert serialized["status"] == "open"
    assert serialized["severity"] == "warning"
    assert serialized["evidence_count"] == 1
    assert serialized["evidence"][0]["reference_id"] == "evt-1"


@pytest.mark.parametrize("severity", ["low", "urgent", ""])
def test_invalid_severity_is_rejected(severity):
    with pytest.raises(ValueError, match="severity"):
        Incident.create(
            incident_id="inc-1",
            title="Test incident",
            summary="Test summary",
            severity=severity,
            created_at=CREATED,
        )


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        IncidentEvidence(
            evidence_id="ev-1",
            kind="event",
            reference_id="evt-1",
            description="Test evidence",
            observed_at="2026-10-28T10:00:00",
        )


def test_duplicate_evidence_ids_in_constructor_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        Incident.create(
            incident_id="inc-1",
            title="Test incident",
            summary="Test summary",
            severity="info",
            evidence=(evidence(), evidence()),
            created_at=CREATED,
        )
