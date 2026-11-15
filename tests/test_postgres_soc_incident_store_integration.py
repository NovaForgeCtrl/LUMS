"""PostgreSQL integration tests for the SOC incident store."""

from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from postgres_test_support import require_test_database_url, run_cleanup
from server.migration_runner import run_migrations
from server.migrations.soc_storage import SOC_STORAGE_MIGRATION
from server.soc.incidents import Incident, IncidentEvidence
from server.soc.incident_store import (
    IncidentNotFoundError,
    IncidentStoreError,
)
from server.soc.postgres_incident_store import PostgresIncidentStore


CREATED = "2026-10-28T10:00:00+00:00"
UPDATED = "2026-10-28T10:05:00+00:00"
LATER = "2026-10-28T10:10:00+00:00"


@pytest.fixture
def postgres_environment():
    database_url = require_test_database_url()

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-soc-incident-setup",
    )

    connection = None
    schema_name = f"lums_soc_incident_test_{uuid4().hex}"
    schema_created = False

    try:
        identity = admin.execute(
            "SELECT current_database(), current_user"
        ).fetchone()

        if (
            identity["current_database"] != "lums_integration"
            or identity["current_user"] != "lums_pg_bootstrap"
        ):
            pytest.fail(
                "Refusing tests outside the dedicated integration database."
            )

        admin.execute(
            sql.SQL("CREATE SCHEMA {}").format(
                sql.Identifier(schema_name)
            )
        )
        schema_created = True

        connection = psycopg.connect(
            database_url,
            autocommit=True,
            row_factory=dict_row,
            application_name="lums-soc-incident-test",
        )
        connection.execute(
            sql.SQL("SET search_path TO {}").format(
                sql.Identifier(schema_name)
            )
        )

        run_migrations(connection, (SOC_STORAGE_MIGRATION,))

        yield connection, database_url, schema_name

    finally:
        run_cleanup(
            (
                "close test connection",
                lambda: connection.close() if connection is not None else None,
            ),
            (
                "drop test schema",
                lambda: admin.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema_name)
                    )
                ) if schema_created else None,
            ),
            ("close admin connection", admin.close),
        )


def make_evidence(
    evidence_id="ev-1",
    *,
    kind="event",
    reference_id="evt-1",
    description="Authentication failure observed",
    observed_at=CREATED,
):
    return IncidentEvidence(
        evidence_id=evidence_id,
        kind=kind,
        reference_id=reference_id,
        description=description,
        observed_at=observed_at,
    )


def make_incident(
    incident_id="inc-1",
    *,
    evidence=None,
    severity="warning",
    title="Repeated authentication failures",
    summary="Several authentication failures were detected.",
    created_at=CREATED,
    updated_at=None,
):
    timestamp = updated_at if updated_at is not None else created_at

    return Incident(
        incident_id=incident_id,
        title=title,
        summary=summary,
        severity=severity,
        status="open",
        created_at=created_at,
        updated_at=timestamp,
        evidence=tuple(
            evidence if evidence is not None else [make_evidence()]
        ),
    )


def test_save_and_get_incident_with_ordered_evidence(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    expected = make_incident(
        evidence=[
            make_evidence("ev-1"),
            make_evidence(
                "ev-2",
                kind="detection",
                reference_id="rule-1",
                description="Detection evidence",
            ),
            make_evidence(
                "ev-3",
                kind="correlation",
                reference_id="series-1",
                description="Correlation evidence",
            ),
        ]
    )

    stored = store.save(expected)

    assert stored == expected
    assert store.get("inc-1") == expected

    assert [
        item.evidence_id for item in store.get("inc-1").evidence
    ] == ["ev-1", "ev-2", "ev-3"]

    assert connection.execute(
        "SELECT COUNT(*) AS count FROM soc_incidents"
    ).fetchone()["count"] == 1

    assert connection.execute(
        "SELECT COUNT(*) AS count FROM soc_incident_evidence"
    ).fetchone()["count"] == 3

    assert store.history("inc-1") == ({
        "old_status": None,
        "new_status": "open",
        "changed_at": CREATED,
        "changed_by": "system",
    },)


def test_repeated_save_is_idempotent_and_preserves_operator_status(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    original = make_incident()
    store.save(original)

    changed = store.transition(
        "inc-1",
        "investigating",
        changed_by="operator-1",
        updated_at=UPDATED,
    )

    replayed = store.save(original)

    assert replayed == changed
    assert replayed.status == "investigating"
    assert replayed.updated_at == UPDATED

    assert connection.execute(
        "SELECT COUNT(*) AS count FROM soc_incidents"
    ).fetchone()["count"] == 1

    assert connection.execute(
        "SELECT COUNT(*) AS count FROM soc_incident_evidence"
    ).fetchone()["count"] == 1

    assert len(store.history("inc-1")) == 2


def test_save_rejects_immutable_identity_conflict_without_mutation(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    original = make_incident()
    store.save(original)

    conflicting = make_incident(
        title="Different immutable title",
    )

    with pytest.raises(IncidentStoreError, match="immutable fields"):
        store.save(conflicting)

    assert store.get("inc-1") == original
    assert connection.execute(
        "SELECT COUNT(*) AS count FROM soc_incident_evidence"
    ).fetchone()["count"] == 1


def test_evidence_replay_is_idempotent_and_conflict_is_rejected(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    original = make_incident()
    store.save(original)

    replay = make_evidence()
    with connection.transaction():
        first = store.append_evidence_in_transaction(
            "inc-1",
            [replay],
            updated_at=LATER,
        )
    assert first.updated_at == CREATED

    appended = make_evidence(
        "ev-2",
        kind="detection",
        reference_id="rule-1",
        description="Second evidence",
    )

    with connection.transaction():
        second = store.append_evidence_in_transaction(
            "inc-1",
            [appended],
            updated_at=UPDATED,
        )

    assert second.updated_at == UPDATED
    assert [item.evidence_id for item in second.evidence] == [
        "ev-1", "ev-2"
    ]

    with connection.transaction():
        replayed = store.append_evidence_in_transaction(
            "inc-1",
            [appended],
            updated_at=LATER,
        )

    assert replayed.updated_at == UPDATED
    assert len(replayed.evidence) == 2

    conflicting = make_evidence(
        "ev-2",
        kind="detection",
        reference_id="different-rule",
        description="Conflicting evidence",
    )

    with connection.transaction():
        with pytest.raises(IncidentStoreError, match="different content"):
            store.append_evidence_in_transaction(
                "inc-1",
                [conflicting],
                updated_at=LATER,
            )

        assert connection.info.transaction_status.name == "INTRANS"

    assert store.get("inc-1") == replayed


def test_append_evidence_preserves_caller_transaction_and_rollback(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    store.save(make_incident())

    with pytest.raises(RuntimeError, match="rollback test"):
        with connection.transaction():
            stored = store.append_evidence_in_transaction(
                "inc-1",
                [make_evidence("ev-2")],
                updated_at=UPDATED,
            )

            assert [item.evidence_id for item in stored.evidence] == [
                "ev-1", "ev-2"
            ]

            raise RuntimeError("rollback test")

    persisted = store.get("inc-1")
    assert [item.evidence_id for item in persisted.evidence] == ["ev-1"]
    assert persisted.updated_at == CREATED


def test_append_evidence_never_moves_updated_at_backwards(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    store.save(make_incident())

    with connection.transaction():
        store.append_evidence_in_transaction(
            "inc-1",
            [make_evidence("ev-2")],
            updated_at=UPDATED,
        )

    with connection.transaction():
        stored = store.append_evidence_in_transaction(
            "inc-1",
            [make_evidence(
                "ev-3",
                reference_id="evt-3",
            )],
            updated_at="2026-10-28T08:00:00+00:00",
        )

    assert stored.updated_at == UPDATED
    assert [item.evidence_id for item in stored.evidence] == [
        "ev-1", "ev-2", "ev-3"
    ]


def test_append_evidence_rejects_unknown_incident(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    with connection.transaction():
        with pytest.raises(IncidentNotFoundError):
            store.append_evidence_in_transaction(
                "missing",
                [make_evidence("ev-2")],
            )


def test_save_many_is_atomic_and_preserves_input_order(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    stored = store.save_many((
        make_incident("inc-1"),
        make_incident(
            "inc-2",
            severity="critical",
            evidence=[make_evidence("ev-2")],
        ),
    ))

    assert [item.incident_id for item in stored] == [
        "inc-1", "inc-2"
    ]

    assert connection.execute(
        "SELECT COUNT(*) AS count FROM soc_incidents"
    ).fetchone()["count"] == 2


def test_save_many_rolls_back_all_items_on_conflicting_evidence(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    store.save(make_incident("inc-existing"))

    conflicting = make_incident(
        "inc-existing",
        evidence=[
            make_evidence(
                reference_id="different-reference",
            )
        ],
    )

    with pytest.raises(IncidentStoreError, match="different content"):
        store.save_many((
            make_incident("inc-new"),
            conflicting,
        ))

    assert store.get("inc-new") is None
    assert store.get("inc-existing") == make_incident("inc-existing")


def test_save_many_in_transaction_requires_and_preserves_caller_transaction(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    with pytest.raises(IncidentStoreError):
        store.save_many_in_transaction((make_incident(),))

    with connection.transaction():
        stored = store.save_many_in_transaction((
            make_incident("inc-1"),
            make_incident("inc-2"),
        ))

        assert len(stored) == 2
        assert connection.info.transaction_status.name == "INTRANS"

    assert store.get("inc-1") is not None
    assert store.get("inc-2") is not None


def test_worker_can_rollback_incident_save_in_shared_transaction(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    with pytest.raises(RuntimeError, match="worker failure"):
        with connection.transaction():
            store.save_many_in_transaction((
                make_incident("inc-atomic-1"),
                make_incident("inc-atomic-2"),
            ))

            raise RuntimeError("worker failure")

    assert store.get("inc-atomic-1") is None
    assert store.get("inc-atomic-2") is None

    assert connection.execute(
        "SELECT COUNT(*) AS count FROM soc_incident_history"
    ).fetchone()["count"] == 0


def test_status_transition_is_persisted_and_audited(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    store.save(make_incident())

    changed = store.transition(
        "inc-1",
        "investigating",
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


def test_same_status_transition_does_not_add_history(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    store.save(make_incident())
    before = store.history("inc-1")

    unchanged = store.transition(
        "inc-1",
        "open",
        changed_by="operator-1",
        updated_at=LATER,
    )

    assert unchanged.status == "open"
    assert unchanged.updated_at == CREATED
    assert store.history("inc-1") == before


def test_invalid_and_unknown_transitions_are_rejected(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    with pytest.raises(IncidentNotFoundError):
        store.transition(
            "missing",
            "resolved",
            changed_by="operator-1",
        )

    store.save(make_incident())

    with pytest.raises(ValueError):
        store.transition(
            "inc-1",
            "invalid",
            changed_by="operator-1",
        )

    with pytest.raises(ValueError, match="changed_by"):
        store.transition(
            "inc-1",
            "investigating",
            changed_by=" ",
        )


def test_list_incidents_filters_and_bounds_pagination(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    store.save_many((
        make_incident("inc-1"),
        make_incident(
            "inc-2",
            severity="critical",
            created_at="2026-10-28T10:01:00+00:00",
        ),
        make_incident(
            "inc-3",
            created_at="2026-10-28T10:02:00+00:00",
        ),
    ))

    store.transition(
        "inc-2",
        "investigating",
        changed_by="operator-2",
        updated_at=LATER,
    )

    assert [
        item.incident_id
        for item in store.list_incidents(limit=10)
    ] == ["inc-2", "inc-3", "inc-1"]

    assert [
        item.incident_id
        for item in store.list_incidents(
            status="investigating",
            limit=10,
        )
    ] == ["inc-2"]

    assert [
        item.incident_id
        for item in store.list_incidents(limit=1, offset=1)
    ] == ["inc-3"]

    with pytest.raises(ValueError):
        store.list_incidents(status="invalid")

    with pytest.raises(ValueError):
        store.list_incidents(limit=0)

    with pytest.raises(ValueError):
        store.list_incidents(limit=501)

    with pytest.raises(ValueError):
        store.list_incidents(offset=-1)


def test_history_unknown_incident_is_rejected(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    with pytest.raises(IncidentNotFoundError):
        store.history("missing")


def test_incident_deletion_cascades_to_evidence_and_history(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    store.save(make_incident())
    store.transition(
        "inc-1",
        "investigating",
        changed_by="operator-1",
        updated_at=UPDATED,
    )

    connection.execute(
        "DELETE FROM soc_incidents WHERE incident_id = %s",
        ("inc-1",),
    )

    assert connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM soc_incident_evidence
        WHERE incident_id = %s
        """,
        ("inc-1",),
    ).fetchone()["count"] == 0

    assert connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM soc_incident_history
        WHERE incident_id = %s
        """,
        ("inc-1",),
    ).fetchone()["count"] == 0


def test_non_utc_input_timestamps_are_compared_as_instants(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresIncidentStore(connection)

    original = make_incident()
    store.save(original)

    same_instant_different_offset = make_incident(
        created_at="2026-10-28T12:00:00+02:00",
    )

    stored = store.save(same_instant_different_offset)

    assert stored.created_at == CREATED
    assert stored == original


def test_concurrent_duplicate_save_is_idempotent(postgres_environment):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    _, database_url, schema_name = postgres_environment

    connections = []
    barrier = Barrier(2)

    try:
        for index in range(2):
            connection = psycopg.connect(
                database_url,
                autocommit=True,
                row_factory=dict_row,
                application_name=f"lums-incident-concurrent-save-{index}",
            )
            connection.execute(
                sql.SQL("SET search_path TO {}").format(
                    sql.Identifier(schema_name)
                )
            )
            connections.append(connection)

        incident = make_incident()

        def save_concurrently(connection):
            barrier.wait(timeout=10)
            return PostgresIncidentStore(connection).save(incident)

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                save_concurrently, connections[0]
            )
            second = executor.submit(
                save_concurrently, connections[1]
            )

            first_result = first.result(timeout=20)
            second_result = second.result(timeout=20)

        assert first_result == second_result
        assert first_result == incident

        assert connections[0].execute(
            "SELECT COUNT(*) AS amount FROM soc_incidents"
        ).fetchone()["amount"] == 1

        assert connections[0].execute(
            "SELECT COUNT(*) AS amount FROM soc_incident_evidence"
        ).fetchone()["amount"] == 1

        assert connections[0].execute(
            "SELECT COUNT(*) AS amount FROM soc_incident_history"
        ).fetchone()["amount"] == 1

    finally:
        for connection in connections:
            connection.close()
