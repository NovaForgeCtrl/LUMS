import sqlite3

import pytest

from server.soc.collector_store import (
    CollectorNotFoundError,
    CollectorRevokedError,
    CollectorStore,
    EventIdConflictError,
)


@pytest.fixture
def store():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    instance = CollectorStore(connection)
    instance.register_agent(
        "linux01", "Linux test host", "a" * 64
    )
    try:
        yield instance
    finally:
        connection.close()


def event(event_id="linux01:boot1:1", message="failed login"):
    return {
        "event_id": event_id,
        "source": "linux01",
        "event_type": "linux.auth.failure",
        "timestamp": "2026-10-29T09:00:00+00:00",
        "fields": {"message": message},
    }


def test_register_agent_normalizes_fingerprint(store):
    agent = store.get_agent_by_fingerprint("A" * 64)
    assert agent["agent_id"] == "linux01"
    assert agent["status"] == "active"
    assert agent["certificate_sha256"] == "a" * 64


def test_unknown_fingerprint_returns_none(store):
    assert store.get_agent_by_fingerprint("b" * 64) is None


def test_duplicate_agent_or_fingerprint_is_rejected(store):
    with pytest.raises(ValueError):
        store.register_agent("linux01", "Duplicate ID", "b" * 64)
    with pytest.raises(ValueError):
        store.register_agent("linux02", "Duplicate certificate", "a" * 64)


def test_invalid_fingerprint_is_rejected(store):
    with pytest.raises(ValueError):
        store.register_agent("linux02", "Host", "not-a-fingerprint")


def test_ingest_batch_persists_pending_event(store):
    result = store.ingest_batch("linux01", [event()])
    assert result.accepted == 1
    assert result.duplicates == 0
    pending = store.list_pending()
    assert len(pending) == 1
    assert pending[0]["event_id"] == "linux01:boot1:1"
    assert pending[0]["payload"]["fields"]["message"] == "failed login"
    assert pending[0]["processing_status"] == "pending"


def test_identical_retry_is_idempotent(store):
    first = store.ingest_batch("linux01", [event()])
    second = store.ingest_batch("linux01", [event()])
    assert first.accepted == 1
    assert second.accepted == 0
    assert second.duplicates == 1
    assert len(store.list_pending()) == 1


def test_same_event_id_with_different_payload_is_rejected_atomically(store):
    store.ingest_batch("linux01", [event()])
    with pytest.raises(EventIdConflictError):
        store.ingest_batch("linux01", [
            event("linux01:boot1:2"),
            event("linux01:boot1:1", "different content"),
        ])
    assert [item["event_id"] for item in store.list_pending()] == [
        "linux01:boot1:1"
    ]


def test_unknown_agent_cannot_ingest(store):
    with pytest.raises(CollectorNotFoundError):
        store.ingest_batch("unknown", [event()])


def test_revoked_agent_cannot_ingest(store):
    assert store.revoke_agent("linux01") is True
    with pytest.raises(CollectorRevokedError):
        store.ingest_batch("linux01", [event()])


def test_revoking_unknown_agent_returns_false(store):
    assert store.revoke_agent("unknown") is False


def test_batch_rejects_duplicate_ids_inside_same_batch(store):
    with pytest.raises(ValueError):
        store.ingest_batch("linux01", [event(), event()])


def test_batch_rejects_invalid_json_values(store):
    bad = event()
    bad["fields"]["not_json"] = object()
    with pytest.raises(ValueError):
        store.ingest_batch("linux01", [bad])


def test_batch_size_is_bounded(store):
    with pytest.raises(ValueError):
        store.ingest_batch("linux01", [
            event(f"linux01:boot1:{number}") for number in range(501)
        ])


def test_list_pending_limit_is_bounded(store):
    with pytest.raises(ValueError):
        store.list_pending(limit=0)
    with pytest.raises(ValueError):
        store.list_pending(limit=501)


def test_store_does_not_create_or_modify_alert_tables(store):
    names = {
        row[0] for row in store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "alerts" not in names
    assert "alert_rules" not in names
    assert "soc_collector_agents" in names
    assert "soc_event_inbox" in names


@pytest.mark.parametrize("operation", [
    "register_agent",
    "revoke_agent",
    "ingest_batch",
    "recover_stale_claims",
    "claim_pending",
    "claim_next_pending",
    "finish_claim",
    "fail_claim",
])
def test_transaction_methods_preserve_caller_transaction(store, operation):
    from server.soc.collector_store import CollectorStoreError

    connection = store.connection
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
        "register_agent": lambda: store.register_agent(
            "linux02", "Second test host", "b" * 64
        ),
        "revoke_agent": lambda: store.revoke_agent("linux01"),
        "ingest_batch": lambda: store.ingest_batch("linux01", [event()]),
        "recover_stale_claims": lambda: store.recover_stale_claims(),
        "claim_pending": lambda: store.claim_pending(),
        "claim_next_pending": lambda: store.claim_next_pending(),
        "finish_claim": lambda: store.finish_claim(1, "test-token"),
        "fail_claim": lambda: store.fail_claim(
            1, "test-token", "test failure"
        ),
    }

    with pytest.raises(CollectorStoreError, match="existing transaction"):
        calls[operation]()

    assert connection.in_transaction is True

    connection.commit()

    marker = connection.execute(
        "SELECT name FROM transaction_guard_markers WHERE name = ?",
        (operation,),
    ).fetchone()
    assert marker == (operation,)
