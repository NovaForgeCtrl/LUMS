import sqlite3

import pytest

from server.soc.incidents import Incident, IncidentEvidence
from server.soc.incident_store import (
    IncidentNotFoundError,
    IncidentStore,
)


CREATED = "2026-10-28T10:00:00+00:00"
UPDATED = "2026-10-28T10:05:00+00:00"


def make_evidence(
    evidence_id="ev-1",
    *,
    kind="event",
    reference_id="evt-1",
):
    return IncidentEvidence(
        evidence_id=evidence_id,
        kind=kind,
        reference_id=reference_id,
        description="Authentication failure observed",
        observed_at=CREATED,
    )


def make_incident(
    incident_id="inc-1",
    *,
    evidence=None,
    severity="warning",
):
    return Incident.create(
        incident_id=incident_id,
        title="Repeated authentication failures",
        summary="Several authentication failures were detected.",
        severity=severity,
        evidence=tuple(evidence if evidence is not None else [make_evidence()]),
        created_at=CREATED,
    )


@pytest.fixture
def store_env(tmp_path):
    path = tmp_path / "soc-store.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    store = IncidentStore(connection)
    yield path, connection, store
    connection.close()


def test_save_and_get_incident_with_evidence(store_env):
    _, connection, store = store_env
    expected = make_incident()

    stored = store.save(expected)

    assert stored == expected
    assert store.get("inc-1") == expected
    assert connection.execute(
        "SELECT COUNT(*) FROM soc_incidents"
    ).fetchone()[0] == 1
    assert connection.execute(
        "SELECT COUNT(*) FROM soc_incident_evidence"
    ).fetchone()[0] == 1


def test_incident_survives_connection_reopen(store_env):
    path, connection, store = store_env
    expected = make_incident()
    store.save(expected)
    connection.close()

    reopened_connection = sqlite3.connect(path)
    try:
        reopened_connection.execute("PRAGMA foreign_keys = ON")
        reopened_store = IncidentStore(reopened_connection)
        assert reopened_store.get("inc-1") == expected
    finally:
        reopened_connection.close()


def test_repeated_save_is_idempotent_and_does_not_reset_status(store_env):
    _, connection, store = store_env
    original = make_incident()
    store.save(original)
    changed = store.transition(
        "inc-1", "investigating",
        changed_by="operator-1",
        updated_at=UPDATED,
    )

    replayed = store.save(original)

    assert replayed == changed
    assert connection.execute(
        "SELECT COUNT(*) FROM soc_incidents"
    ).fetchone()[0] == 1
    assert connection.execute(
        "SELECT COUNT(*) FROM soc_incident_evidence"
    ).fetchone()[0] == 1


def test_save_appends_new_evidence_without_duplicate_ids(store_env):
    _, connection, store = store_env
    store.save(make_incident())
    replay = make_incident(
        evidence=[
            make_evidence(),
            make_evidence("ev-2", kind="detection", reference_id="rule-1"),
        ]
    )

    stored = store.save(replay)

    assert [item.evidence_id for item in stored.evidence] == ["ev-1", "ev-2"]
    assert connection.execute(
        "SELECT COUNT(*) FROM soc_incident_evidence"
    ).fetchone()[0] == 2


def test_save_many_persists_all_incidents(store_env):
    _, connection, store = store_env

    stored = store.save_many((
        make_incident("inc-1"),
        make_incident("inc-2", severity="critical"),
    ))

    assert [item.incident_id for item in stored] == ["inc-1", "inc-2"]
    assert connection.execute(
        "SELECT COUNT(*) FROM soc_incidents"
    ).fetchone()[0] == 2


def test_status_transition_is_persisted_and_audited(store_env):
    _, connection, store = store_env
    store.save(make_incident())

    changed = store.transition(
        "inc-1", "investigating",
        changed_by="operator-7",
        updated_at=UPDATED,
    )

    assert changed.status == "investigating"
    assert changed.updated_at == UPDATED
    assert store.history("inc-1") == (
        {
            "old_status": None,
            "new_status": "open",
            "changed_at": CREATED,
            "changed_by": "system",
        },
        {
            "old_status": "open",
            "new_status": "investigating",
            "changed_at": UPDATED,
            "changed_by": "operator-7",
        },
    )
    row = connection.execute(
        "SELECT status FROM soc_incidents WHERE incident_id = 'inc-1'"
    ).fetchone()
    assert row == ("investigating",)


def test_invalid_status_transition_rolls_back(store_env):
    _, connection, store = store_env
    store.save(make_incident())
    store.transition(
        "inc-1", "resolved", changed_by="operator-1", updated_at=UPDATED
    )

    with pytest.raises(ValueError, match="transition"):
        store.transition(
            "inc-1", "investigating",
            changed_by="operator-1",
            updated_at="2026-10-28T10:10:00+00:00",
        )

    assert store.get("inc-1").status == "resolved"
    assert len(store.history("inc-1")) == 2


def test_get_and_transition_unknown_incident(store_env):
    _, _, store = store_env

    assert store.get("missing") is None
    with pytest.raises(IncidentNotFoundError):
        store.transition("missing", "resolved", changed_by="operator-1")
    with pytest.raises(IncidentNotFoundError):
        store.history("missing")


def test_list_filters_status_and_bounds_pagination(store_env):
    _, _, store = store_env
    store.save_many((
        make_incident("inc-a"),
        make_incident("inc-b"),
        make_incident("inc-c", severity="critical"),
    ))
    store.transition(
        "inc-c", "investigating",
        changed_by="operator-1", updated_at=UPDATED,
    )

    assert [item.incident_id for item in store.list_incidents(limit=2)] == [
        "inc-c", "inc-a"
    ]
    assert [item.incident_id for item in store.list_incidents(
        status="investigating"
    )] == ["inc-c"]
    assert [item.incident_id for item in store.list_incidents(
        offset=1, limit=1
    )] == ["inc-a"]


@pytest.mark.parametrize("limit", [0, -1, 501, True, "10"])
def test_list_rejects_invalid_limit(store_env, limit):
    _, _, store = store_env
    with pytest.raises(ValueError, match="limit"):
        store.list_incidents(limit=limit)


def test_list_rejects_invalid_status_and_offset(store_env):
    _, _, store = store_env

    with pytest.raises(ValueError, match="status"):
        store.list_incidents(status="unknown")
    with pytest.raises(ValueError, match="offset"):
        store.list_incidents(offset=-1)


def test_store_does_not_change_existing_alert_tables(store_env):
    _, connection, store = store_env
    connection.execute("""
        CREATE TABLE alert_history (
            id INTEGER PRIMARY KEY,
            alert_id TEXT NOT NULL
        )
    """)
    connection.commit()

    IncidentStore(connection)

    tables = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert "alert_history" in tables
    assert "soc_incidents" in tables
    assert "soc_incident_evidence" in tables
    assert "soc_incident_history" in tables


def test_invalid_incident_type_is_rejected(store_env):
    _, _, store = store_env
    with pytest.raises(TypeError, match="Incident"):
        store.save({"incident_id": "not-an-incident"})
