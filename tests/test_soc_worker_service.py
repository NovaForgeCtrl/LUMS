import json
import sqlite3
from datetime import datetime, timezone

import pytest

from server.soc.collector_store import CollectorStore
from server.soc.incident_store import IncidentStore
from server.soc.worker import (
    ClaimOwnershipLost,
    SOCWorker,
    SOCWorkerError,
    validate_worker_schema,
)
from server.soc.rule_catalog import load_catalog
from server.soc.worker_migration import run_migration


def test_preflight_rejects_empty_database_without_creating_tables():
    connection = sqlite3.connect(":memory:")
    try:
        with pytest.raises(SOCWorkerError, match="missing tables"):
            validate_worker_schema(connection)

        tables = connection.execute("""
            SELECT name FROM sqlite_master WHERE type = 'table'
        """).fetchall()
        assert tables == []
    finally:
        connection.close()


def test_preflight_rejects_missing_claim_migration():
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript("""
            CREATE TABLE soc_collector_agents (
                agent_id TEXT, display_name TEXT,
                certificate_sha256 TEXT, status TEXT,
                created_at TEXT, revoked_at TEXT
            );
            CREATE TABLE soc_event_inbox (
                inbox_id INTEGER, agent_id TEXT, event_id TEXT,
                payload_json TEXT, payload_sha256 TEXT, received_at TEXT,
                processing_status TEXT, processed_at TEXT, last_error TEXT,
                claim_token TEXT, claimed_at TEXT, attempts INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE soc_incidents (
                incident_id TEXT, title TEXT, summary TEXT, severity TEXT,
                status TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE soc_incident_evidence (
                evidence_id TEXT, incident_id TEXT, kind TEXT,
                reference_id TEXT, description TEXT, observed_at TEXT
            );
            CREATE TABLE soc_incident_history (
                history_id INTEGER, incident_id TEXT, old_status TEXT,
                new_status TEXT, changed_at TEXT, changed_by TEXT
            );
            CREATE TABLE schema_migrations (
                version TEXT PRIMARY KEY, applied_at TEXT NOT NULL
            );
        """)

        with pytest.raises(
            SOCWorkerError,
            match="001-soc-worker-claims is not recorded",
        ):
            validate_worker_schema(connection)

        count = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()[0]
        assert count == 0
    finally:
        connection.close()


def test_preflight_rejects_missing_claim_recovery_index():
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript("""
            CREATE TABLE soc_collector_agents (
                agent_id TEXT, display_name TEXT,
                certificate_sha256 TEXT, status TEXT,
                created_at TEXT, revoked_at TEXT
            );
            CREATE TABLE soc_event_inbox (
                inbox_id INTEGER, agent_id TEXT, event_id TEXT,
                payload_json TEXT, payload_sha256 TEXT, received_at TEXT,
                processing_status TEXT, processed_at TEXT, last_error TEXT,
                claim_token TEXT, claimed_at TEXT, attempts INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE soc_incidents (
                incident_id TEXT, title TEXT, summary TEXT, severity TEXT,
                status TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE soc_incident_evidence (
                evidence_id TEXT, incident_id TEXT, kind TEXT,
                reference_id TEXT, description TEXT, observed_at TEXT
            );
            CREATE TABLE soc_incident_history (
                history_id INTEGER, incident_id TEXT, old_status TEXT,
                new_status TEXT, changed_at TEXT, changed_by TEXT
            );
            CREATE TABLE schema_migrations (
                version TEXT PRIMARY KEY, applied_at TEXT NOT NULL
            );
            INSERT INTO schema_migrations(version, applied_at)
            VALUES ('001-soc-worker-claims', '2026-10-29T00:00:00+00:00');
        """)

        with pytest.raises(
            SOCWorkerError,
            match="idx_soc_event_inbox_claim_recovery is missing",
        ):
            validate_worker_schema(connection)
    finally:
        connection.close()


def _create_migrated_worker_database(tmp_path):
    path = tmp_path / "soc-worker-service-test.db"
    connection = sqlite3.connect(path, timeout=5)
    CollectorStore(connection)
    IncidentStore(connection)
    CollectorStore(connection).register_agent(
        "linux01", "Linux test host", "a" * 64
    )
    run_migration(path)
    return connection


def test_worker_constructor_rejects_empty_database_without_creating_tables():
    connection = sqlite3.connect(":memory:")
    try:
        catalog = load_catalog("server/soc/rules.json")

        with pytest.raises(SOCWorkerError, match="missing tables"):
            SOCWorker(connection, catalog)

        tables = connection.execute("""
            SELECT name FROM sqlite_master WHERE type = 'table'
        """).fetchall()
        assert tables == []
    finally:
        connection.close()


def test_worker_constructor_accepts_fully_migrated_database(tmp_path):
    connection = _create_migrated_worker_database(tmp_path)
    try:
        catalog = load_catalog("server/soc/rules.json")
        worker = SOCWorker(connection, catalog)

        assert worker.connection is connection
        assert worker.collectors.connection is connection
        assert worker.incidents.connection is connection

        migration = connection.execute("""
            SELECT version
            FROM schema_migrations
            WHERE version = '001-soc-worker-claims'
        """).fetchone()
        assert migration is not None

        indexes = {
            row[1]
            for row in connection.execute(
                "PRAGMA index_list('soc_event_inbox')"
            ).fetchall()
        }
        assert "idx_soc_event_inbox_claim_recovery" in indexes
    finally:
        connection.close()




def test_run_once_isolates_invalid_json_claim_from_valid_claim(tmp_path):
    connection = _create_migrated_worker_database(tmp_path)
    try:
        collector = CollectorStore(connection)
        collector.ingest_batch("linux01", [
            {
                "event_id": "linux01:boot1:1",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": "2026-10-29T09:00:00+00:00",
                "fields": {"message": "failed login"},
            },
            {
                "event_id": "linux01:boot1:2",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": "2026-10-29T09:01:00+00:00",
                "fields": {"message": "another failed login"},
            },
        ])

        connection.execute("""
            UPDATE soc_event_inbox
            SET payload_json = ?
            WHERE event_id = ?
        """, ("{invalid-json", "linux01:boot1:1"))
        connection.commit()

        worker = SOCWorker(
            connection,
            load_catalog("server/soc/rules.json"),
            max_attempts=3,
        )

        processed_claims = []

        def process_valid_claim(claim):
            processed_claims.append(claim["event_id"])
            finished = worker.collectors.finish_claim(
                claim["inbox_id"], claim["claim_token"]
            )
            assert finished is True
            return 0

        worker._process_claim = process_valid_claim

        result = worker.run_once()

        assert result.claimed == 2
        assert result.processed == 1
        assert result.retried_or_failed == 1
        assert result.incidents_emitted == 0

        assert processed_claims == ["linux01:boot1:2"]

        rows = connection.execute("""
            SELECT event_id, processing_status, last_error, attempts
            FROM soc_event_inbox
            ORDER BY inbox_id
        """).fetchall()

        assert rows[0][0] == "linux01:boot1:1"
        assert rows[0][1] == "pending"
        assert "Invalid JSON payload" in rows[0][2]
        assert rows[0][3] == 1

        assert rows[1][0] == "linux01:boot1:2"
        assert rows[1][1] == "processed"
        assert rows[1][2] is None
        assert rows[1][3] == 1
    finally:
        connection.close()

def test_continuous_worker_waits_when_queue_is_empty(monkeypatch):
    import threading
    from server.soc.worker import WorkerResult, run_continuous

    class FakeWorker:
        def __init__(self):
            self.calls = 0

        def run_once(self):
            self.calls += 1
            stop_event.set()
            return WorkerResult(0, 0, 0, 0)

    stop_event = threading.Event()
    waits = []

    def fake_wait(interval):
        waits.append(interval)
        return stop_event.is_set()

    monkeypatch.setattr(stop_event, "wait", fake_wait)
    worker = FakeWorker()

    run_continuous(worker, stop_event, 0.5)

    assert worker.calls == 1
    assert waits == [0.5]


def test_continuous_worker_stops_without_starting_another_batch():
    import threading
    from server.soc.worker import run_continuous

    stop_event = threading.Event()
    stop_event.set()

    class FakeWorker:
        def run_once(self):
            raise AssertionError("Worker must not start after stop")

    run_continuous(FakeWorker(), stop_event, 1.0)


def test_continuous_worker_propagates_claim_errors():
    import threading
    from server.soc.worker import run_continuous

    class FakeWorker:
        def run_once(self):
            raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        run_continuous(FakeWorker(), threading.Event(), 1.0)


@pytest.mark.parametrize("interval", [0, -1, 3601, True, float("nan")])
def test_continuous_worker_rejects_invalid_poll_interval(interval):
    import threading
    from server.soc.worker import run_continuous

    class FakeWorker:
        def run_once(self):
            raise AssertionError("Worker must not run with invalid interval")

    with pytest.raises(ValueError, match="poll_interval"):
        run_continuous(FakeWorker(), threading.Event(), interval)


def test_main_defaults_to_single_batch(monkeypatch):
    import server.soc.worker as module

    class FakeConnection:
        closed = False

        def close(self):
            self.closed = True

    class FakeWorker:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        def run_once(self):
            self.calls += 1
            return module.WorkerResult(1, 1, 0, 0)

    connection = FakeConnection()
    workers = []

    monkeypatch.setattr(module, "load_catalog", lambda path: object())
    monkeypatch.setattr(module, "_open_connection", lambda path: connection)

    def create_worker(*args, **kwargs):
        worker = FakeWorker()
        workers.append(worker)
        return worker

    monkeypatch.setattr(module, "SOCWorker", create_worker)

    def unexpected_continuous(*args):
        raise AssertionError("Default mode must not be continuous")

    monkeypatch.setattr(module, "run_continuous", unexpected_continuous)

    assert module.main([]) == 0
    assert workers[0].calls == 1
    assert connection.closed is True


def test_main_continuous_registers_and_restores_signal_handlers(monkeypatch):
    import signal
    import server.soc.worker as module

    class FakeConnection:
        closed = False

        def close(self):
            self.closed = True

    class FakeWorker:
        def __init__(self, *args, **kwargs):
            pass

    connection = FakeConnection()
    registrations = []
    continuous_calls = []

    def fake_signal(signum, handler):
        registrations.append((signum, handler))
        return f"previous-{signum}"

    def fake_continuous(worker, stop_event, interval):
        continuous_calls.append((worker, interval))
        assert interval == 0.25

        registered = {
            signum: handler
            for signum, handler in registrations
            if callable(handler)
        }
        registered[signal.SIGTERM](signal.SIGTERM, None)
        assert stop_event.is_set()

    monkeypatch.setattr(module, "load_catalog", lambda path: object())
    monkeypatch.setattr(module, "_open_connection", lambda path: connection)
    monkeypatch.setattr(module, "SOCWorker", FakeWorker)
    monkeypatch.setattr(module.signal, "signal", fake_signal)
    monkeypatch.setattr(module, "run_continuous", fake_continuous)

    assert module.main(["--continuous", "--poll-interval", "0.25"]) == 0

    expected = {signal.SIGINT, signal.SIGTERM}
    assert {signum for signum, _ in registrations[:2]} == expected
    assert len(registrations) == 4
    assert continuous_calls[0][1] == 0.25
    assert connection.closed is True

    restored = registrations[2:]
    assert {
        signum: handler for signum, handler in restored
    } == {
        signal.SIGINT: "previous-2",
        signal.SIGTERM: "previous-15",
    }


def test_main_rejects_invalid_poll_interval():
    import server.soc.worker as module

    with pytest.raises(SystemExit) as exc:
        module.main(["--continuous", "--poll-interval", "0"])

    assert exc.value.code == 2


def test_run_once_isolates_valid_json_with_invalid_payload_shapes(tmp_path):
    connection = _create_migrated_worker_database(tmp_path)
    try:
        collector = CollectorStore(connection)
        collector.ingest_batch("linux01", [
            {
                "event_id": "linux01:boot1:1",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": "2026-10-29T09:00:00+00:00",
                "fields": {"message": "placeholder for invalid JSON shape"},
            },
            {
                "event_id": "linux01:boot1:2",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": "2026-10-29T09:01:00+00:00",
                "fields": {"message": "invalid fields object"},
            },
            {
                "event_id": "linux01:boot1:3",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": "2026-10-29T09:02:00+00:00",
                "fields": {"message": "valid event"},
            },
        ])

        connection.execute("""
            UPDATE soc_event_inbox
            SET payload_json = ?
            WHERE event_id = ?
        """, ("[]", "linux01:boot1:1"))

        connection.execute("""
            UPDATE soc_event_inbox
            SET payload_json = ?
            WHERE event_id = ?
        """, (
            '{"source":"linux01","event_type":"linux.auth.failure",'
            '"timestamp":"2026-10-29T09:01:00+00:00","fields":null}',
            "linux01:boot1:2",
        ))
        connection.commit()

        worker = SOCWorker(
            connection,
            load_catalog("server/soc/rules.json"),
            max_attempts=3,
        )

        result = worker.run_once()

        assert result.claimed == 3
        assert result.processed == 1
        assert result.retried_or_failed == 2

        rows = connection.execute("""
            SELECT event_id, processing_status, last_error, attempts
            FROM soc_event_inbox
            ORDER BY inbox_id
        """).fetchall()

        assert [row["processing_status"] for row in rows] == [
            "pending", "pending", "processed"
        ]
        assert "invalid shape" in rows[0]["last_error"]
        assert "fields must be an object" in rows[1]["last_error"]
        assert [row["attempts"] for row in rows] == [1, 1, 1]
    finally:
        connection.close()


def test_run_once_claims_and_processes_events_one_at_a_time(tmp_path):
    connection = _create_migrated_worker_database(tmp_path)
    try:
        collector = CollectorStore(connection)
        collector.ingest_batch("linux01", [
            {
                "event_id": f"linux01:jit:{index}",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": f"2026-10-29T09:0{index}:00+00:00",
                "fields": {"message": f"event {index}"},
            }
            for index in range(1, 4)
        ])

        worker = SOCWorker(
            connection,
            load_catalog("server/soc/rules.json"),
            batch_size=3,
        )

        active_claim_counts = []

        def process_claim(claim):
            active = connection.execute("""
                SELECT COUNT(*)
                FROM soc_event_inbox
                WHERE processing_status = 'processing'
            """).fetchone()[0]
            active_claim_counts.append(active)

            assert active == 1
            assert worker.collectors.finish_claim(
                claim["inbox_id"], claim["claim_token"]
            )
            return 0

        worker._process_claim = process_claim
        result = worker.run_once()

        assert result.claimed == 3
        assert result.processed == 3
        assert result.retried_or_failed == 0
        assert active_claim_counts == [1, 1, 1]

        remaining = connection.execute("""
            SELECT COUNT(*)
            FROM soc_event_inbox
            WHERE processing_status = 'pending'
        """).fetchone()[0]
        assert remaining == 0
    finally:
        connection.close()


def test_continuous_worker_waits_after_successful_batch(monkeypatch):
    import threading
    from server.soc.worker import WorkerResult, run_continuous

    stop_event = threading.Event()
    waits = []

    class FakeWorker:
        def run_once(self):
            stop_event.set()
            return WorkerResult(1, 1, 0, 0)

    def fake_wait(interval):
        waits.append(interval)
        return stop_event.is_set()

    monkeypatch.setattr(stop_event, "wait", fake_wait)

    run_continuous(FakeWorker(), stop_event, 0.75)

    assert waits == [0.75]


def test_historical_payloads_skip_invalid_fields_without_aborting(tmp_path):
    from datetime import datetime, timezone

    connection = _create_migrated_worker_database(tmp_path)
    try:
        collector = CollectorStore(connection)
        timestamp = datetime.now(timezone.utc).isoformat()

        collector.ingest_batch("linux01", [{
            "event_id": "linux01:history:1",
            "source": "linux01",
            "event_type": "linux.auth.failure",
            "timestamp": timestamp,
            "fields": {"message": "historical event"},
        }])

        connection.execute("""
            UPDATE soc_event_inbox
            SET processing_status = 'processed',
                processed_at = ?,
                payload_json = ?
            WHERE event_id = ?
        """, (
            timestamp,
            '{"event_type":"linux.auth.failure",'
            '"timestamp":"' + timestamp + '","fields":null}',
            "linux01:history:1",
        ))
        connection.commit()

        worker = SOCWorker(
            connection,
            load_catalog("server/soc/rules.json"),
        )

        historical = worker._historical_payloads(
            current_inbox_id=999999,
            current_event_timestamp=timestamp,
            max_window_seconds=3600,
        )

        assert historical == []
    finally:
        connection.close()


def test_run_once_processes_current_event_when_history_contains_invalid_fields(
    tmp_path,
):
    from datetime import datetime, timezone

    connection = _create_migrated_worker_database(tmp_path)
    try:
        collector = CollectorStore(connection)
        timestamp = datetime.now(timezone.utc).isoformat()

        collector.ingest_batch("linux01", [
            {
                "event_id": "linux01:history:1",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": timestamp,
                "fields": {"message": "historical event"},
            },
            {
                "event_id": "linux01:current:1",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": timestamp,
                "fields": {"message": "current event"},
            },
        ])

        connection.execute("""
            UPDATE soc_event_inbox
            SET processing_status = 'processed',
                processed_at = ?,
                payload_json = ?
            WHERE event_id = ?
        """, (
            timestamp,
            '{"event_type":"linux.auth.failure",'
            '"timestamp":"' + timestamp + '","fields":null}',
            "linux01:history:1",
        ))
        connection.commit()

        worker = SOCWorker(
            connection,
            load_catalog("server/soc/rules.json"),
        )

        result = worker.run_once()

        rows = connection.execute("""
            SELECT event_id, processing_status
            FROM soc_event_inbox
            ORDER BY inbox_id
        """).fetchall()

        assert result.claimed == 1
        assert result.processed == 1
        assert result.retried_or_failed == 0
        assert [
            (row["event_id"], row["processing_status"])
            for row in rows
        ] == [
            ("linux01:history:1", "processed"),
            ("linux01:current:1", "processed"),
        ]
    finally:
        connection.close()


def test_process_claim_preserves_caller_transaction(tmp_path):
    connection = _create_migrated_worker_database(tmp_path)
    try:
        collector = CollectorStore(connection)
        collector.ingest_batch("linux01", [{
            "event_id": "linux01:transaction-guard:1",
            "source": "linux01",
            "event_type": "linux.auth.failure",
            "timestamp": "2026-10-29T09:00:00+00:00",
            "fields": {"message": "failed login"},
        }])

        worker = SOCWorker(
            connection,
            load_catalog("server/soc/rules.json"),
        )
        claim = worker.collectors.claim_next_pending()
        assert claim is not None

        connection.execute("""
            CREATE TABLE transaction_guard_markers (
                name TEXT PRIMARY KEY
            )
        """)
        connection.commit()

        connection.execute("BEGIN IMMEDIATE")
        connection.execute("""
            INSERT INTO transaction_guard_markers(name)
            VALUES ('worker')
        """)

        with pytest.raises(
            SOCWorkerError,
            match="inside an existing transaction",
        ):
            worker._process_claim(claim)

        assert connection.in_transaction is True

        connection.commit()

        marker = connection.execute("""
            SELECT name FROM transaction_guard_markers
            WHERE name = 'worker'
        """).fetchone()
        assert marker["name"] == "worker"

        status = connection.execute("""
            SELECT processing_status
            FROM soc_event_inbox
            WHERE event_id = 'linux01:transaction-guard:1'
        """).fetchone()
        assert status["processing_status"] == "processing"
    finally:
        connection.close()


def test_process_claim_rolls_back_inbox_finalization_when_incident_save_fails(
    tmp_path,
    monkeypatch,
):
    from server.soc.incidents import Incident

    connection = _create_migrated_worker_database(tmp_path)
    try:
        collector = CollectorStore(connection)
        collector.ingest_batch("linux01", [{
            "event_id": "linux01:atomicity:1",
            "source": "linux01",
            "event_type": "linux.auth.failure",
            "timestamp": "2026-10-29T09:00:00+00:00",
            "fields": {"message": "failed login"},
        }])

        worker = SOCWorker(
            connection,
            load_catalog("server/soc/rules.json"),
            max_attempts=3,
        )

        incident = Incident.create(
            incident_id="inc-atomicity-test",
            title="Atomicity test",
            summary="Incident persistence failure test",
            severity="warning",
            created_at="2026-10-29T09:00:00+00:00",
        )

        monkeypatch.setattr(
            worker.builder,
            "build",
            lambda result: (incident,),
        )

        def fail_incident_save(incidents):
            raise RuntimeError("simulated incident persistence failure")

        monkeypatch.setattr(
            worker.incidents,
            "save_many_in_transaction",
            fail_incident_save,
        )

        result = worker.run_once()

        assert result.claimed == 1
        assert result.processed == 0
        assert result.retried_or_failed == 1
        assert result.incidents_emitted == 0

        inbox = connection.execute("""
            SELECT processing_status, claim_token, claimed_at,
                   last_error, attempts
            FROM soc_event_inbox
            WHERE event_id = 'linux01:atomicity:1'
        """).fetchone()

        assert inbox["processing_status"] == "pending"
        assert inbox["claim_token"] is None
        assert inbox["claimed_at"] is None
        assert "simulated incident persistence failure" in inbox["last_error"]
        assert inbox["attempts"] == 1

        assert connection.execute(
            "SELECT COUNT(*) FROM soc_incidents"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM soc_incident_evidence"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM soc_incident_history"
        ).fetchone()[0] == 0

        assert connection.in_transaction is False
    finally:
        connection.close()


def test_process_claim_rejects_reclaimed_token_without_saving_incidents(
    tmp_path,
    monkeypatch,
):
    from datetime import datetime, timedelta, timezone

    from server.soc.incidents import Incident

    connection = _create_migrated_worker_database(tmp_path)
    try:
        collector = CollectorStore(connection)
        collector.ingest_batch("linux01", [{
            "event_id": "linux01:stale-token:1",
            "source": "linux01",
            "event_type": "linux.auth.failure",
            "timestamp": "2026-10-29T09:00:00+00:00",
            "fields": {"message": "failed login"},
        }])

        worker = SOCWorker(
            connection,
            load_catalog("server/soc/rules.json"),
            max_attempts=3,
            stale_after_seconds=60,
        )

        old_claim = worker.collectors.claim_next_pending()
        assert old_claim is not None

        expired = (
            datetime.now(timezone.utc) - timedelta(minutes=10)
        ).isoformat()
        connection.execute("""
            UPDATE soc_event_inbox
            SET claimed_at = ?
            WHERE inbox_id = ?
        """, (expired, old_claim["inbox_id"]))
        connection.commit()

        assert worker.collectors.recover_stale_claims(
            stale_after_seconds=60,
            max_attempts=3,
        ) == 1

        new_claim = worker.collectors.claim_next_pending(
            recover_stale=False,
        )
        assert new_claim is not None
        assert new_claim["claim_token"] != old_claim["claim_token"]

        incident = Incident.create(
            incident_id="inc-stale-token-test",
            title="Stale token test",
            summary="Old worker must not persist incidents",
            severity="warning",
            created_at="2026-10-29T09:00:00+00:00",
        )
        monkeypatch.setattr(
            worker.builder,
            "build",
            lambda result: (incident,),
        )

        with pytest.raises(
            SOCWorkerError,
            match="Claim token is no longer current",
        ):
            worker._process_claim(old_claim)

        inbox = connection.execute("""
            SELECT processing_status, claim_token, claimed_at, attempts
            FROM soc_event_inbox
            WHERE inbox_id = ?
        """, (old_claim["inbox_id"],)).fetchone()

        assert inbox["processing_status"] == "processing"
        assert inbox["claim_token"] == new_claim["claim_token"]
        assert inbox["claimed_at"] == new_claim["claimed_at"]
        assert inbox["attempts"] == 2

        assert connection.execute(
            "SELECT COUNT(*) FROM soc_incidents"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM soc_incident_evidence"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM soc_incident_history"
        ).fetchone()[0] == 0

        assert connection.in_transaction is False
    finally:
        connection.close()


def test_historical_payloads_skip_non_string_timestamp(tmp_path):
    connection = _create_migrated_worker_database(tmp_path)
    try:
        collector = CollectorStore(connection)
        timestamp = datetime.now(timezone.utc).isoformat()

        collector.ingest_batch("linux01", [
            {
                "event_id": "linux01:history:valid",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": timestamp,
                "fields": {"message": "valid historical event"},
            },
            {
                "event_id": "linux01:history:invalid",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": timestamp,
                "fields": {"message": "invalid historical event"},
            },
            {
                "event_id": "linux01:history:current",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": timestamp,
                "fields": {"message": "current event"},
            },
        ])

        connection.row_factory = sqlite3.Row
        rows = connection.execute("""
            SELECT inbox_id, event_id, payload_json
            FROM soc_event_inbox
            ORDER BY inbox_id
        """).fetchall()

        valid_row, invalid_row, current_row = rows

        invalid_payload = json.loads(invalid_row["payload_json"])
        invalid_payload["timestamp"] = 123456789
        connection.execute("""
            UPDATE soc_event_inbox
            SET processing_status = 'processed'
            WHERE inbox_id IN (?, ?)
        """, (valid_row["inbox_id"], invalid_row["inbox_id"]))
        connection.execute("""
            UPDATE soc_event_inbox
            SET payload_json = ?
            WHERE inbox_id = ?
        """, (json.dumps(invalid_payload), invalid_row["inbox_id"]))
        connection.commit()

        worker = SOCWorker(
            connection,
            load_catalog("server/soc/rules.json"),
        )

        historical = worker._historical_payloads(
            current_inbox_id=current_row["inbox_id"],
            current_event_timestamp=timestamp,
            max_window_seconds=3600,
        )

        assert len(historical) == 1
        assert (
            historical[0]["fields"]["_lums_original_event_id"]
            == "linux01:history:valid"
        )
        assert historical[0]["fields"]["message"] == "valid historical event"
    finally:
        connection.close()


def _create_worker_with_failing_event(tmp_path):
    connection = _create_migrated_worker_database(tmp_path)
    collector = CollectorStore(connection)

    collector.ingest_batch("linux01", [{
        "event_id": "linux01:failure-recording:1",
        "source": "linux01",
        "event_type": "linux.auth.failure",
        "timestamp": "2026-10-29T09:00:00+00:00",
        "fields": {"message": "test event"},
    }])

    worker = SOCWorker(
        connection,
        load_catalog("server/soc/rules.json"),
        max_attempts=3,
    )

    def fail_processing(claim):
        raise RuntimeError("simulated processing failure")

    worker._process_claim = fail_processing
    return connection, worker


def test_run_once_aborts_when_fail_claim_returns_false(tmp_path, monkeypatch):
    connection, worker = _create_worker_with_failing_event(tmp_path)
    try:
        def refuse_failure_recording(*args, **kwargs):
            return False

        monkeypatch.setattr(
            worker.collectors,
            "fail_claim",
            refuse_failure_recording,
        )

        with pytest.raises(
            SOCWorkerError,
            match="claim is no longer owned",
        ):
            worker.run_once()

        row = connection.execute("""
            SELECT processing_status, claim_token, claimed_at
            FROM soc_event_inbox
            WHERE event_id = 'linux01:failure-recording:1'
        """).fetchone()

        assert row["processing_status"] == "processing"
        assert row["claim_token"] is not None
        assert row["claimed_at"] is not None
    finally:
        connection.close()


def test_run_once_aborts_when_fail_claim_raises(tmp_path, monkeypatch):
    connection, worker = _create_worker_with_failing_event(tmp_path)
    try:
        def raise_failure_recording(*args, **kwargs):
            raise RuntimeError("simulated database failure")

        monkeypatch.setattr(
            worker.collectors,
            "fail_claim",
            raise_failure_recording,
        )

        with pytest.raises(
            SOCWorkerError,
            match="Could not record worker failure",
        ) as exc_info:
            worker.run_once()

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert "simulated database failure" in str(exc_info.value.__cause__)

        row = connection.execute("""
            SELECT processing_status
            FROM soc_event_inbox
            WHERE event_id = 'linux01:failure-recording:1'
        """).fetchone()

        assert row["processing_status"] == "processing"
    finally:
        connection.close()



def test_run_once_correlates_delayed_event_against_event_time(tmp_path):
    from datetime import datetime, timedelta, timezone
    from server.soc.rule_catalog import load_catalog_data

    connection = _create_migrated_worker_database(tmp_path)
    try:
        collector = CollectorStore(connection)

        # Beide Events liegen zwei Tage zurück. Das historische Event liegt
        # nur 30 Sekunden vor dem aktuellen Event und muss korrelieren.
        current_time = datetime.now(timezone.utc) - timedelta(days=2)
        historical_time = current_time - timedelta(seconds=30)

        collector.ingest_batch("linux01", [
            {
                "event_id": "linux01:delayed:history",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": historical_time.isoformat(),
                "fields": {"source_ip": "192.0.2.10"},
            },
            {
                "event_id": "linux01:delayed:current",
                "source": "linux01",
                "event_type": "linux.auth.failure",
                "timestamp": current_time.isoformat(),
                "fields": {"source_ip": "192.0.2.10"},
            },
        ])

        connection.execute("""
            UPDATE soc_event_inbox
            SET processing_status = 'processed',
                processed_at = ?
            WHERE event_id = ?
        """, (
            datetime.now(timezone.utc).isoformat(),
            "linux01:delayed:history",
        ))
        connection.commit()

        catalog = load_catalog_data({
            "version": 1,
            "rules": [{
                "id": "test-delayed-auth-failures",
                "name": "Repeated authentication failures",
                "description": "Test-only delayed event correlation",
                "type": "correlation",
                "event_type": "linux.auth.failure",
                "group_by": "source_ip",
                "window_seconds": 60,
                "minimum_count": 2,
                "severity": "warning",
                "enabled": True,
            }],
        })

        worker = SOCWorker(connection, catalog)
        result = worker.run_once()

        assert result.claimed == 1
        assert result.processed == 1
        assert result.retried_or_failed == 0
        assert result.incidents_emitted == 1

        correlation_evidence = connection.execute("""
            SELECT COUNT(*)
            FROM soc_incident_evidence
            WHERE kind = 'correlation'
        """).fetchone()[0]

        assert correlation_evidence >= 1

        current_status = connection.execute("""
            SELECT processing_status
            FROM soc_event_inbox
            WHERE event_id = ?
        """, ("linux01:delayed:current",)).fetchone()[0]

        assert current_status == "processed"
    finally:
        connection.close()


def test_process_claim_rolls_back_on_conflicting_evidence_id(
    tmp_path,
    monkeypatch,
):
    from server.soc.incidents import Incident, IncidentEvidence

    connection = _create_migrated_worker_database(tmp_path)
    try:
        collector = CollectorStore(connection)
        collector.ingest_batch("linux01", [{
            "event_id": "linux01:evidence-conflict:1",
            "source": "linux01",
            "event_type": "linux.auth.failure",
            "timestamp": "2026-10-29T09:00:00+00:00",
            "fields": {"message": "failed login"},
        }])

        worker = SOCWorker(
            connection,
            load_catalog("server/soc/rules.json"),
            max_attempts=3,
        )

        existing_evidence = IncidentEvidence(
            evidence_id="ev-worker-conflict",
            kind="event",
            reference_id="linux01:original-event",
            description="Original persisted evidence",
            observed_at="2026-10-29T08:55:00+00:00",
        )
        existing_incident = Incident.create(
            incident_id="inc-worker-evidence-conflict",
            title="Original incident",
            summary="Original persisted summary",
            severity="warning",
            evidence=(existing_evidence,),
            created_at="2026-10-29T08:55:00+00:00",
        )
        worker.incidents.save(existing_incident)

        conflicting_evidence = IncidentEvidence(
            evidence_id="ev-worker-conflict",
            kind="event",
            reference_id="linux01:different-event",
            description="Different evidence using the same ID",
            observed_at="2026-10-29T09:00:00+00:00",
        )
        conflicting_incident = Incident.create(
            incident_id="inc-worker-evidence-conflict",
            title="Conflicting incident",
            summary="This must not overwrite the original",
            severity="critical",
            evidence=(conflicting_evidence,),
            created_at="2026-10-29T09:00:00+00:00",
        )

        monkeypatch.setattr(
            worker.builder,
            "build",
            lambda result: (conflicting_incident,),
        )

        result = worker.run_once()

        assert result.claimed == 1
        assert result.processed == 0
        assert result.retried_or_failed == 1
        assert result.incidents_emitted == 0

        inbox = connection.execute("""
            SELECT processing_status, claim_token, claimed_at,
                   last_error, attempts
            FROM soc_event_inbox
            WHERE event_id = 'linux01:evidence-conflict:1'
        """).fetchone()

        assert inbox["processing_status"] == "pending"
        assert inbox["claim_token"] is None
        assert inbox["claimed_at"] is None
        assert "different content" in inbox["last_error"]
        assert inbox["attempts"] == 1

        stored_incident = connection.execute("""
            SELECT title, summary, severity, status
            FROM soc_incidents
            WHERE incident_id = 'inc-worker-evidence-conflict'
        """).fetchone()

        assert tuple(stored_incident) == (
            "Original incident",
            "Original persisted summary",
            "warning",
            "open",
        )

        stored_evidence = connection.execute("""
            SELECT evidence_id, reference_id, description, observed_at
            FROM soc_incident_evidence
            WHERE incident_id = 'inc-worker-evidence-conflict'
        """).fetchall()

        assert len(stored_evidence) == 1
        assert tuple(stored_evidence[0]) == (
            "ev-worker-conflict",
            "linux01:original-event",
            "Original persisted evidence",
            "2026-10-29T08:55:00+00:00",
        )

        history_count = connection.execute("""
            SELECT COUNT(*)
            FROM soc_incident_history
            WHERE incident_id = 'inc-worker-evidence-conflict'
        """).fetchone()[0]
        assert history_count == 1

        assert connection.in_transaction is False
    finally:
        connection.close()


def test_run_once_counts_lost_claim_without_failing_new_owner(
    tmp_path,
    monkeypatch,
):
    connection = _create_migrated_worker_database(tmp_path)
    try:
        collector = CollectorStore(connection)
        collector.ingest_batch("linux01", [{
            "event_id": "linux01:lost-claim:1",
            "source": "linux01",
            "event_type": "linux.auth.failure",
            "timestamp": "2026-10-29T09:00:00+00:00",
            "fields": {"message": "failed login"},
        }])

        worker = SOCWorker(
            connection,
            load_catalog("server/soc/rules.json"),
            max_attempts=3,
        )

        def simulate_reclaim(claim):
            connection.execute(
                """
                UPDATE soc_event_inbox
                SET claim_token = ?
                WHERE inbox_id = ?
                """,
                ("new-owner-token", claim["inbox_id"]),
            )
            connection.commit()
            raise ClaimOwnershipLost(
                "Claim token is no longer current; refusing finalization"
            )

        def unexpected_fail_claim(*args, **kwargs):
            pytest.fail(
                "fail_claim must not be called for a lost claim"
            )

        monkeypatch.setattr(worker, "_process_claim", simulate_reclaim)
        monkeypatch.setattr(
            worker.collectors,
            "fail_claim",
            unexpected_fail_claim,
        )

        result = worker.run_once()

        assert result.claimed == 1
        assert result.processed == 0
        assert result.retried_or_failed == 0
        assert result.incidents_emitted == 0
        assert result.claims_lost == 1

        inbox = connection.execute(
            """
            SELECT processing_status, claim_token, attempts
            FROM soc_event_inbox
            WHERE inbox_id = (
                SELECT inbox_id FROM soc_event_inbox
                WHERE event_id = 'linux01:lost-claim:1'
            )
            """
        ).fetchone()

        assert tuple(inbox) == (
            "processing",
            "new-owner-token",
            1,
        )
    finally:
        connection.close()


def test_preflight_rejects_malformed_claim_column_definition(tmp_path):
    connection = _create_migrated_worker_database(tmp_path)
    connection.close()

    connection = sqlite3.connect(
        tmp_path / "soc-worker-service-test.db"
    )
    try:
        connection.execute("""
            ALTER TABLE soc_event_inbox
            RENAME COLUMN attempts TO attempts_original
        """)
        connection.execute("""
            ALTER TABLE soc_event_inbox
            ADD COLUMN attempts TEXT
        """)
        connection.commit()

        with pytest.raises(
            SOCWorkerError,
            match="incompatible column definitions",
        ):
            validate_worker_schema(connection)
    finally:
        connection.close()
