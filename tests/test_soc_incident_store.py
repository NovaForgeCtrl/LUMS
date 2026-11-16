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
    title="Repeated authentication failures",
    summary="Several authentication failures were detected.",
    created_at=CREATED,
):
    return Incident.create(
        incident_id=incident_id,
        title=title,
        summary=summary,
        severity=severity,
        evidence=tuple(evidence if evidence is not None else [make_evidence()]),
        created_at=created_at,
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


@pytest.mark.parametrize("operation", ["save", "save_many", "transition"])
def test_transaction_methods_preserve_caller_transaction(
    store_env, operation
):
    from server.soc.incident_store import IncidentStoreError

    _, connection, store = store_env
    connection.execute("""
        CREATE TABLE transaction_guard_markers (
            name TEXT PRIMARY KEY
        )
    """)
    connection.commit()

    connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        "INSERT INTO transaction_guard_markers(name) VALUES (?)",
        (operation,),
    )

    calls = {
        "save": lambda: store.save(make_incident("caller-save")),
        "save_many": lambda: store.save_many((
            make_incident("caller-save-many"),
        )),
        "transition": lambda: store.transition(
            "inc-1", "investigating", changed_by="operator-1"
        ),
    }

    with pytest.raises(IncidentStoreError, match="existing transaction"):
        calls[operation]()

    assert connection.in_transaction is True

    connection.commit()

    marker = connection.execute(
        "SELECT name FROM transaction_guard_markers WHERE name = ?",
        (operation,),
    ).fetchone()
    assert marker == (operation,)


def test_save_many_in_transaction_keeps_caller_transaction_open(store_env):
    _, connection, store = store_env
    expected = make_incident("caller-owned-save")

    connection.execute("BEGIN IMMEDIATE")
    stored = store.save_many_in_transaction((expected,))

    assert stored == (expected,)
    assert connection.in_transaction is True

    connection.commit()

    assert store.get("caller-owned-save") == expected


def test_append_evidence_in_transaction_preserves_caller_transaction(store_env):
    _, connection, store = store_env
    store.save(make_incident())

    new_evidence = make_evidence(
        "ev-2", kind="correlation", reference_id="series-1"
    )

    connection.execute("BEGIN IMMEDIATE")
    stored = store.append_evidence_in_transaction(
        "inc-1", [new_evidence], updated_at=UPDATED
    )

    assert connection.in_transaction is True
    assert [item.evidence_id for item in stored.evidence] == ["ev-1", "ev-2"]
    assert stored.updated_at == UPDATED

    connection.commit()

    assert store.get("inc-1") == stored


def test_append_evidence_is_idempotent_and_does_not_update_timestamp(store_env):
    _, connection, store = store_env
    store.save(make_incident())

    connection.execute("BEGIN IMMEDIATE")
    first = store.append_evidence_in_transaction(
        "inc-1",
        [make_evidence("ev-2")],
        updated_at=UPDATED,
    )
    connection.commit()

    duplicate_timestamp = "2026-10-28T11:00:00+00:00"
    connection.execute("BEGIN IMMEDIATE")
    second = store.append_evidence_in_transaction(
        "inc-1",
        [make_evidence("ev-2")],
        updated_at=duplicate_timestamp,
    )
    connection.commit()

    assert second.updated_at == first.updated_at == UPDATED
    assert len(second.evidence) == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM soc_incident_evidence WHERE incident_id = 'inc-1'"
    ).fetchone()[0] == 2


def test_append_evidence_does_not_change_status_or_status_history(store_env):
    _, connection, store = store_env
    store.save(make_incident())
    store.transition(
        "inc-1",
        "investigating",
        changed_by="operator-1",
        updated_at=UPDATED,
    )
    history_before = store.history("inc-1")

    connection.execute("BEGIN IMMEDIATE")
    stored = store.append_evidence_in_transaction(
        "inc-1",
        [make_evidence("ev-2")],
        updated_at="2026-10-28T10:10:00+00:00",
    )
    connection.commit()

    assert stored.status == "investigating"
    assert store.history("inc-1") == history_before


def test_append_evidence_requires_caller_transaction(store_env):
    _, connection, store = store_env
    store.save(make_incident())

    from server.soc.incident_store import IncidentStoreError

    with pytest.raises(IncidentStoreError, match="active transaction"):
        store.append_evidence_in_transaction(
            "inc-1", [make_evidence("ev-2")]
        )

    assert connection.in_transaction is False
    assert len(store.get("inc-1").evidence) == 1


def test_append_evidence_rejects_unknown_incident_inside_transaction(store_env):
    _, connection, store = store_env

    connection.execute("BEGIN IMMEDIATE")
    with pytest.raises(IncidentNotFoundError):
        store.append_evidence_in_transaction(
            "missing", [make_evidence("ev-2")]
        )

    assert connection.in_transaction is True
    connection.rollback()


def test_append_evidence_never_moves_updated_at_backwards(store_env):
    _, connection, store = store_env
    store.save(make_incident())
    store.transition(
        "inc-1",
        "investigating",
        changed_by="operator-1",
        updated_at=UPDATED,
    )

    # 12:00 +03:00 entspricht 09:00 UTC und liegt vor 10:05 UTC.
    late_timestamp = "2026-10-28T12:00:00+03:00"

    connection.execute("BEGIN IMMEDIATE")
    stored = store.append_evidence_in_transaction(
        "inc-1",
        [make_evidence("ev-late")],
        updated_at=late_timestamp,
    )
    connection.commit()

    assert stored.updated_at == UPDATED
    assert [item.evidence_id for item in stored.evidence] == [
        "ev-1", "ev-late"
    ]
    assert stored.status == "investigating"


def test_append_evidence_rejects_naive_updated_at(store_env):
    _, connection, store = store_env
    store.save(make_incident())

    connection.execute("BEGIN IMMEDIATE")
    with pytest.raises(ValueError, match="timezone-aware"):
        store.append_evidence_in_transaction(
            "inc-1",
            [make_evidence("ev-2")],
            updated_at="2026-10-28T10:10:00",
        )

    assert connection.in_transaction is True
    connection.rollback()
    assert len(store.get("inc-1").evidence) == 1


def test_incident_add_evidence_accepts_exact_replay():
    incident = make_incident()
    evidence = incident.evidence[0]

    assert incident.add_evidence(evidence) is incident


def test_incident_add_evidence_rejects_same_id_with_different_content():
    incident = make_incident()
    conflicting = make_evidence(reference_id="different-reference")

    with pytest.raises(ValueError, match="different content"):
        incident.add_evidence(conflicting)


def test_save_rejects_evidence_id_conflict_without_changing_persisted_data(
    store_env,
):
    _, connection, store = store_env
    original = make_incident()
    store.save(original)

    conflicting = make_incident(
        evidence=[make_evidence(reference_id="different-reference")]
    )

    from server.soc.incident_store import IncidentStoreError

    with pytest.raises(IncidentStoreError, match="different content"):
        store.save(conflicting)

    assert store.get("inc-1") == original
    assert connection.execute(
        "SELECT COUNT(*) FROM soc_incident_evidence"
    ).fetchone()[0] == 1
    assert connection.in_transaction is False


def test_save_many_rejects_evidence_id_conflict_and_preserves_caller_transaction(
    store_env,
):
    _, connection, store = store_env
    original = make_incident()
    store.save(original)

    conflicting = make_incident(
        evidence=[make_evidence(reference_id="different-reference")]
    )

    from server.soc.incident_store import IncidentStoreError

    connection.execute("BEGIN")
    try:
        with pytest.raises(IncidentStoreError, match="different content"):
            store.save_many_in_transaction([conflicting])

        assert connection.in_transaction is True
    finally:
        connection.rollback()

    assert store.get("inc-1") == original


def test_append_evidence_rejects_evidence_id_conflict_and_preserves_transaction(
    store_env,
):
    _, connection, store = store_env
    original = make_incident()
    store.save(original)

    conflicting = make_evidence(reference_id="different-reference")

    from server.soc.incident_store import IncidentStoreError

    connection.execute("BEGIN")
    try:
        with pytest.raises(IncidentStoreError, match="different content"):
            store.append_evidence_in_transaction(
                "inc-1",
                [conflicting],
                updated_at=UPDATED,
            )
        assert connection.in_transaction is True
    finally:
        connection.rollback()

    assert store.get("inc-1") == original


@pytest.mark.parametrize("invalid_timestamp", [123, True, object(), ""])
def test_append_evidence_rejects_invalid_timestamp_type(
    store_env,
    invalid_timestamp,
):
    _, connection, store = store_env
    store.save(make_incident())

    connection.execute("BEGIN")
    try:
        with pytest.raises(ValueError, match="timezone-aware ISO timestamp"):
            store.append_evidence_in_transaction(
                "inc-1",
                [make_evidence("ev-2")],
                updated_at=invalid_timestamp,
            )
        assert connection.in_transaction is True
    finally:
        connection.rollback()

    assert [item.evidence_id for item in store.get("inc-1").evidence] == [
        "ev-1"
    ]


@pytest.mark.parametrize(
    ("field", "conflicting_value"),
    [
        ("title", "Different incident title"),
        ("summary", "Different incident summary"),
        ("severity", "critical"),
        ("created_at", "2026-10-28T10:01:00+00:00"),
    ],
)
def test_save_rejects_incident_identity_conflict(
    store_env,
    field,
    conflicting_value,
):
    from dataclasses import replace
    from server.soc.incident_store import IncidentStoreError

    _, connection, store = store_env
    original = make_incident()
    store.save(original)

    conflicting = replace(original, **{field: conflicting_value})

    with pytest.raises(IncidentStoreError, match="different content"):
        store.save(conflicting)

    assert store.get("inc-1") == original
    assert connection.in_transaction is False


@pytest.mark.parametrize(
    ("field", "conflicting_value"),
    [
        ("title", "Different incident title"),
        ("summary", "Different incident summary"),
        ("severity", "critical"),
        ("created_at", "2026-10-28T10:01:00+00:00"),
    ],
)
def test_save_many_rejects_incident_identity_conflict(
    store_env,
    field,
    conflicting_value,
):
    from dataclasses import replace
    from server.soc.incident_store import IncidentStoreError

    _, connection, store = store_env
    original = make_incident()
    store.save(original)

    conflicting = replace(original, **{field: conflicting_value})

    connection.execute("BEGIN")
    try:
        with pytest.raises(IncidentStoreError, match="different content"):
            store.save_many_in_transaction([conflicting])

        assert connection.in_transaction is True
    finally:
        connection.rollback()

    assert store.get("inc-1") == original


def test_incident_create_rejects_empty_created_at():
    with pytest.raises(ValueError, match="created_at"):
        Incident.create(
            incident_id="inc-empty-created-at",
            title="Timestamp validation",
            summary="Empty timestamp must be rejected.",
            severity="warning",
            created_at="",
        )


def test_incident_transition_rejects_empty_updated_at():
    incident = make_incident()

    with pytest.raises(ValueError, match="updated_at"):
        incident.transition("investigating", updated_at="")


def test_incident_add_evidence_rejects_empty_updated_at():
    incident = make_incident()
    evidence = make_evidence(
        "ev-empty-updated-at",
        reference_id="evt-empty-updated-at",
    )

    with pytest.raises(ValueError, match="updated_at"):
        incident.add_evidence(evidence, updated_at="")
