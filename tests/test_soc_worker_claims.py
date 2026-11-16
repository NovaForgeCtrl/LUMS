import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from server.soc.collector_store import CollectorStore
from server.soc.worker_migration import run_migration
from server.soc.worker_schema import inspect_claim_consistency


@pytest.fixture
def worker_db(tmp_path):
    path = tmp_path / "soc-worker-test.db"
    connection = sqlite3.connect(path, timeout=5)
    connection.execute("PRAGMA foreign_keys = ON")
    store = CollectorStore(connection)
    store.register_agent("linux01", "Linux test host", "a" * 64)
    run_migration(path)
    store.ingest_batch("linux01", [
        {
            "event_id": "linux01:boot1:1",
            "source": "linux01",
            "event_type": "linux.auth.failure",
            "timestamp": "2026-10-29T09:00:00+00:00",
            "fields": {"message": "failed login"},
        }
    ])
    try:
        yield path, connection, store
    finally:
        connection.close()


def test_claim_pending_sets_token_and_increments_attempts(worker_db):
    _, _, store = worker_db

    claims = store.claim_pending()

    assert len(claims) == 1
    claim = claims[0]
    assert claim["processing_status"] == "processing"
    assert claim["claim_token"]
    assert claim["attempts"] == 1

    row = store.connection.execute("""
        SELECT processing_status, claim_token, claimed_at, attempts
        FROM soc_event_inbox WHERE inbox_id = ?
    """, (claim["inbox_id"],)).fetchone()

    assert row[0] == "processing"
    assert row[1] == claim["claim_token"]
    assert row[2] is not None
    assert row[3] == 1


def test_second_worker_cannot_claim_same_event(worker_db):
    path, _, first_store = worker_db
    first = first_store.claim_pending()
    second_connection = sqlite3.connect(path, timeout=5)
    try:
        second_store = CollectorStore(second_connection)
        second = second_store.claim_pending()
        assert len(first) == 1
        assert second == ()
    finally:
        second_connection.close()


def test_finish_claim_requires_current_token(worker_db):
    _, _, store = worker_db
    claim = store.claim_pending()[0]

    assert store.finish_claim(claim["inbox_id"], "wrong-token") is False

    row = store.connection.execute("""
        SELECT processing_status FROM soc_event_inbox WHERE inbox_id = ?
    """, (claim["inbox_id"],)).fetchone()
    assert row[0] == "processing"

    assert store.finish_claim(
        claim["inbox_id"], claim["claim_token"]
    ) is True

    row = store.connection.execute("""
        SELECT processing_status, claim_token, claimed_at, processed_at
        FROM soc_event_inbox WHERE inbox_id = ?
    """, (claim["inbox_id"],)).fetchone()

    assert row[0] == "processed"
    assert row[1] is None
    assert row[2] is None
    assert row[3] is not None


def test_fail_claim_requeues_before_retry_limit(worker_db):
    _, _, store = worker_db
    claim = store.claim_pending(max_attempts=3)[0]

    assert store.fail_claim(
        claim["inbox_id"], claim["claim_token"],
        "temporary failure", max_attempts=3,
    ) is True

    row = store.connection.execute("""
        SELECT processing_status, last_error, claim_token, attempts
        FROM soc_event_inbox WHERE inbox_id = ?
    """, (claim["inbox_id"],)).fetchone()

    assert row == ("pending", "temporary failure", None, 1)


def test_fail_claim_marks_failed_at_retry_limit(worker_db):
    _, _, store = worker_db
    claim = store.claim_pending(max_attempts=1)[0]

    assert store.fail_claim(
        claim["inbox_id"], claim["claim_token"],
        "permanent failure", max_attempts=1,
    ) is True

    row = store.connection.execute("""
        SELECT processing_status, last_error, attempts
        FROM soc_event_inbox WHERE inbox_id = ?
    """, (claim["inbox_id"],)).fetchone()

    assert row == ("failed", "permanent failure", 1)
    assert store.claim_pending() == ()


def test_stale_claim_is_recovered_for_retry(worker_db):
    _, connection, store = worker_db
    claim = store.claim_pending(max_attempts=3)[0]
    expired = (
        datetime.now(timezone.utc) - timedelta(minutes=10)
    ).isoformat()

    connection.execute("""
        UPDATE soc_event_inbox SET claimed_at = ? WHERE inbox_id = ?
    """, (expired, claim["inbox_id"]))
    connection.commit()

    assert store.recover_stale_claims(
        stale_after_seconds=60, max_attempts=3,
    ) == 1

    row = connection.execute("""
        SELECT processing_status, claim_token, claimed_at, attempts
        FROM soc_event_inbox WHERE inbox_id = ?
    """, (claim["inbox_id"],)).fetchone()

    assert row == ("pending", None, None, 1)

    replacement = store.claim_pending(max_attempts=3)
    assert len(replacement) == 1
    assert replacement[0]["claim_token"] != claim["claim_token"]
    assert replacement[0]["attempts"] == 2


def test_stale_claim_at_retry_limit_becomes_failed(worker_db):
    _, connection, store = worker_db
    claim = store.claim_pending(max_attempts=1)[0]
    expired = (
        datetime.now(timezone.utc) - timedelta(minutes=10)
    ).isoformat()

    connection.execute("""
        UPDATE soc_event_inbox SET claimed_at = ? WHERE inbox_id = ?
    """, (expired, claim["inbox_id"]))
    connection.commit()

    assert store.recover_stale_claims(
        stale_after_seconds=60, max_attempts=1,
    ) == 1

    row = connection.execute("""
        SELECT processing_status, claim_token, last_error
        FROM soc_event_inbox WHERE inbox_id = ?
    """, (claim["inbox_id"],)).fetchone()

    assert row[0] == "failed"
    assert row[1] is None
    assert "retry limit" in row[2].lower()


def test_old_claim_token_cannot_finalize_reclaimed_event(worker_db):
    _, connection, store = worker_db
    old_claim = store.claim_pending(max_attempts=3)[0]
    expired = (
        datetime.now(timezone.utc) - timedelta(minutes=10)
    ).isoformat()

    connection.execute("""
        UPDATE soc_event_inbox SET claimed_at = ? WHERE inbox_id = ?
    """, (expired, old_claim["inbox_id"]))
    connection.commit()

    assert store.recover_stale_claims(
        stale_after_seconds=60, max_attempts=3,
    ) == 1

    new_claim = store.claim_pending(max_attempts=3)[0]
    assert new_claim["claim_token"] != old_claim["claim_token"]

    assert store.finish_claim(
        old_claim["inbox_id"], old_claim["claim_token"]
    ) is False

    assert store.finish_claim(
        new_claim["inbox_id"], new_claim["claim_token"]
    ) is True


@pytest.mark.parametrize("limit", [0, -1, 501, True])
def test_claim_limit_validation(worker_db, limit):
    _, _, store = worker_db
    with pytest.raises(ValueError):
        store.claim_pending(limit=limit)


def test_claims_only_pending_rows(worker_db):
    _, _, store = worker_db
    claim = store.claim_pending()[0]
    assert store.finish_claim(claim["inbox_id"], claim["claim_token"])
    assert store.claim_pending() == ()



def test_invalid_json_does_not_block_valid_events_in_claim_batch(worker_db):
    _, connection, store = worker_db

    store.ingest_batch("linux01", [
        {
            "event_id": "linux01:boot1:2",
            "source": "linux01",
            "event_type": "linux.auth.failure",
            "timestamp": "2026-10-29T09:01:00+00:00",
            "fields": {"message": "another failed login"},
        }
    ])

    connection.execute("""
        UPDATE soc_event_inbox
        SET payload_json = ?
        WHERE event_id = ?
    """, ("{invalid-json", "linux01:boot1:1"))
    connection.commit()

    claims = store.claim_pending(limit=10)

    assert len(claims) == 2

    claims_by_event = {
        claim["event_id"]: claim for claim in claims
    }

    invalid_claim = claims_by_event["linux01:boot1:1"]
    valid_claim = claims_by_event["linux01:boot1:2"]

    assert invalid_claim["payload"] is None
    assert isinstance(invalid_claim["payload_error"], str)
    assert invalid_claim["payload_error"]

    assert isinstance(valid_claim["payload"], dict)
    assert valid_claim["payload"]["event_id"] == "linux01:boot1:2"
    assert valid_claim["payload_error"] is None


def test_fresh_claim_is_not_recovered(worker_db):
    _, connection, store = worker_db
    claim = store.claim_pending(max_attempts=3)[0]

    before = connection.execute("""
        SELECT processing_status, claim_token, claimed_at, attempts
        FROM soc_event_inbox WHERE inbox_id = ?
    """, (claim["inbox_id"],)).fetchone()

    assert store.recover_stale_claims(
        stale_after_seconds=3600,
        max_attempts=3,
    ) == 0

    after = connection.execute("""
        SELECT processing_status, claim_token, claimed_at, attempts
        FROM soc_event_inbox WHERE inbox_id = ?
    """, (claim["inbox_id"],)).fetchone()

    assert after == before
    assert after[0] == "processing"
    assert after[1] == claim["claim_token"]
    assert after[2] is not None
    assert after[3] == 1


def test_processing_claim_without_timestamp_is_not_recovered(worker_db):
    _, connection, store = worker_db
    claim = store.claim_pending(max_attempts=3)[0]

    connection.execute("""
        UPDATE soc_event_inbox
        SET claimed_at = NULL
        WHERE inbox_id = ?
    """, (claim["inbox_id"],))
    connection.commit()

    assert store.recover_stale_claims(
        stale_after_seconds=60,
        max_attempts=3,
    ) == 0

    row = connection.execute("""
        SELECT processing_status, claim_token, claimed_at, attempts
        FROM soc_event_inbox WHERE inbox_id = ?
    """, (claim["inbox_id"],)).fetchone()

    assert row == (
        "processing",
        claim["claim_token"],
        None,
        1,
    )


def test_claim_consistency_accepts_pending_and_valid_processing_claims(worker_db):
    _, connection, store = worker_db

    expected = {
        "consistent": True,
        "inconsistent_count": 0,
        "inconsistent_ids": [],
    }

    # A newly ingested event has no claim metadata.
    assert inspect_claim_consistency(connection) == expected

    # A valid processing claim has both token and timestamp.
    claim = store.claim_pending()[0]
    assert claim["claim_token"]
    assert inspect_claim_consistency(connection) == expected


@pytest.mark.parametrize(
    ("claim_token", "claimed_at"),
    [
        (None, "2026-10-29T09:00:00+00:00"),
        ("token", None),
        (None, None),
        ("", "2026-10-29T09:00:00+00:00"),
        ("token", ""),
    ],
)
def test_claim_consistency_reports_incomplete_processing_claim(
    worker_db, claim_token, claimed_at
):
    _, connection, store = worker_db
    claim = store.claim_pending()[0]

    connection.execute(
        """
        UPDATE soc_event_inbox
        SET claim_token = ?, claimed_at = ?
        WHERE inbox_id = ?
        """,
        (claim_token, claimed_at, claim["inbox_id"]),
    )
    connection.commit()

    result = inspect_claim_consistency(connection)

    assert result == {
        "consistent": False,
        "inconsistent_count": 1,
        "inconsistent_ids": [claim["inbox_id"]],
    }


@pytest.mark.parametrize("status", ["pending", "processed", "failed"])
def test_claim_consistency_reports_residual_claim_metadata(worker_db, status):
    _, connection, store = worker_db
    claim = store.claim_pending()[0]

    connection.execute(
        """
        UPDATE soc_event_inbox
        SET processing_status = ?, claim_token = ?, claimed_at = ?
        WHERE inbox_id = ?
        """,
        (
            status,
            "stale-token",
            "2026-10-29T09:00:00+00:00",
            claim["inbox_id"],
        ),
    )
    connection.commit()

    result = inspect_claim_consistency(connection)

    assert result["consistent"] is False
    assert result["inconsistent_count"] == 1
    assert result["inconsistent_ids"] == [claim["inbox_id"]]


def test_claim_consistency_does_not_modify_database(worker_db):
    _, connection, store = worker_db
    claim = store.claim_pending()[0]

    before = connection.execute(
        """
        SELECT processing_status, claim_token, claimed_at, attempts
        FROM soc_event_inbox WHERE inbox_id = ?
        """,
        (claim["inbox_id"],),
    ).fetchone()

    inspect_claim_consistency(connection)

    after = connection.execute(
        """
        SELECT processing_status, claim_token, claimed_at, attempts
        FROM soc_event_inbox WHERE inbox_id = ?
        """,
        (claim["inbox_id"],),
    ).fetchone()

    assert after == before
