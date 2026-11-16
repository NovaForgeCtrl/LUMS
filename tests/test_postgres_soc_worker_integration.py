"""PostgreSQL integration tests for the SOC worker."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from secrets import token_urlsafe
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from postgres_test_support import require_test_database_url, run_cleanup
from server.migration_runner import run_migrations
from server.migrations.soc_storage import SOC_STORAGE_MIGRATION
from server.soc.collector_store import CollectorStoreError
from server.soc.incidents import Incident
from server.soc.postgres_collector_store import PostgresCollectorStore
from server.soc.postgres_worker import (
    PostgresSOCWorker,
    validate_postgres_worker_schema,
)
from server.soc.rule_catalog import load_catalog_data
from server.soc.worker import ClaimOwnershipLost, SOCWorkerError


EMPTY_CATALOG = load_catalog_data({"version": 1, "rules": []})

DETECTION_CATALOG = load_catalog_data({
    "version": 1,
    "rules": [
        {
            "id": "auth-failure",
            "name": "Authentication failure",
            "description": "Detect failed authentication",
            "type": "detection",
            "event_type": "linux.auth.failure",
            "severity": "critical",
            "enabled": True,
            "field": "message",
            "operator": "contains",
            "value": "failed",
        }
    ],
})


@pytest.fixture
def postgres_environment():
    database_url = require_test_database_url()

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-soc-worker-setup",
    )

    connection = None
    schema_name = f"lums_soc_worker_test_{uuid4().hex}"
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
            application_name="lums-soc-worker-test",
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


def _event(event_id, timestamp="2026-10-29T09:00:00+00:00", message="failed login"):
    return {
        "event_id": event_id,
        "source": "linux01",
        "event_type": "linux.auth.failure",
        "timestamp": timestamp,
        "fields": {
            "message": message,
            "user": "root",
        },
    }


def _prepare_agent(connection):
    store = PostgresCollectorStore(connection)
    store.register_agent(
        "linux01",
        "PostgreSQL worker test host",
        "a" * 64,
    )
    return store


def _make_worker(connection, catalog=EMPTY_CATALOG, **kwargs):
    return PostgresSOCWorker(connection, catalog, **kwargs)


def test_preflight_accepts_migrated_schema_without_modifying_it(
    postgres_environment,
):
    connection, _, _ = postgres_environment

    before = connection.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = current_schema()
        ORDER BY table_name
        """
    ).fetchall()

    validate_postgres_worker_schema(connection)
    worker = _make_worker(connection)

    after = connection.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = current_schema()
        ORDER BY table_name
        """
    ).fetchall()

    assert before == after
    assert isinstance(worker.collectors, PostgresCollectorStore)


def test_preflight_rejects_missing_recovery_index(
    postgres_environment,
):
    connection, _, _ = postgres_environment

    connection.execute(
        "DROP INDEX idx_soc_event_inbox_claim_recovery"
    )

    with pytest.raises(SOCWorkerError, match="recovery index"):
        _make_worker(connection)


def test_preflight_rejects_migration_checksum_mismatch(
    postgres_environment,
):
    connection, _, _ = postgres_environment

    connection.execute(
        """
        UPDATE schema_migrations
        SET checksum = %s
        WHERE version = %s
        """,
        ("0" * 64, "009-soc-storage"),
    )

    with pytest.raises(SOCWorkerError, match="checksum"):
        _make_worker(connection)


def test_worker_processes_a_real_detection_and_persists_incident(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    collectors = _prepare_agent(connection)

    collectors.ingest_batch(
        "linux01",
        [_event("linux01:worker:detection:1")],
    )

    worker = _make_worker(connection, DETECTION_CATALOG, batch_size=1)
    result = worker.run_once()

    assert result.claimed == 1
    assert result.processed == 1
    assert result.retried_or_failed == 0
    assert result.incidents_emitted == 1
    assert result.claims_lost == 0

    inbox = connection.execute(
        """
        SELECT processing_status, claim_token, claimed_at,
               processed_at, attempts
        FROM soc_event_inbox
        """
    ).fetchone()

    assert inbox["processing_status"] == "processed"
    assert inbox["claim_token"] is None
    assert inbox["claimed_at"] is None
    assert inbox["processed_at"] is not None
    assert inbox["attempts"] == 1

    incidents = worker.incidents.list_incidents()
    assert len(incidents) == 1
    assert incidents[0].severity == "critical"
    assert incidents[0].title == "Detection: Authentication failure"
    assert [item.kind for item in incidents[0].evidence] == [
        "detection",
        "event",
    ]
    assert len(worker.incidents.history(incidents[0].incident_id)) == 1


def test_worker_processes_without_incidents_when_no_rule_matches(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    collectors = _prepare_agent(connection)

    collectors.ingest_batch(
        "linux01",
        [_event("linux01:worker:no-match:1", message="successful login")],
    )

    worker = _make_worker(connection, EMPTY_CATALOG, batch_size=1)
    result = worker.run_once()

    assert result.claimed == 1
    assert result.processed == 1
    assert result.incidents_emitted == 0

    assert connection.execute(
        """
        SELECT processing_status
        FROM soc_event_inbox
        """
    ).fetchone()["processing_status"] == "processed"

    assert worker.incidents.list_incidents() == ()


def test_historical_payloads_are_filtered_and_returned_in_order(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    collectors = _prepare_agent(connection)

    events = [
        _event(
            "linux01:history:1",
            timestamp="2026-10-29T08:50:00+00:00",
            message="first historical event",
        ),
        _event(
            "linux01:history:2",
            timestamp="2026-10-29T08:55:00+00:00",
            message="malformed historical event",
        ),
        _event(
            "linux01:history:3",
            timestamp="2026-10-29T09:02:00+00:00",
            message="second historical event",
        ),
        _event(
            "linux01:history:4",
            timestamp="2026-10-29T07:00:00+00:00",
            message="outside correlation window",
        ),
        _event(
            "linux01:history:current",
            timestamp="2026-10-29T09:05:00+00:00",
            message="current event",
        ),
    ]

    collectors.ingest_batch("linux01", events)

    connection.execute(
        """
        UPDATE soc_event_inbox
        SET processing_status = 'processed',
            processed_at = CURRENT_TIMESTAMP
        WHERE event_id <> %s
        """,
        ("linux01:history:current",),
    )

    connection.execute(
        """
        UPDATE soc_event_inbox
        SET payload_json = %s
        WHERE event_id = %s
        """,
        ("{invalid-json", "linux01:history:2"),
    )

    current_id = connection.execute(
        """
        SELECT inbox_id
        FROM soc_event_inbox
        WHERE event_id = %s
        """,
        ("linux01:history:current",),
    ).fetchone()["inbox_id"]

    worker = _make_worker(
        connection,
        EMPTY_CATALOG,
        history_limit=10,
    )

    historical = worker._historical_payloads(
        current_inbox_id=current_id,
        current_event_timestamp="2026-10-29T09:05:00+00:00",
        max_window_seconds=3600,
    )

    assert [
        item["fields"]["_lums_original_event_id"]
        for item in historical
    ] == [
        "linux01:history:1",
        "linux01:history:3",
    ]


def test_invalid_claim_payload_is_retried_without_blocking_next_event(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    collectors = _prepare_agent(connection)

    collectors.ingest_batch(
        "linux01",
        [
            _event("linux01:worker:invalid:1"),
            _event("linux01:worker:valid:2"),
        ],
    )

    connection.execute(
        """
        UPDATE soc_event_inbox
        SET payload_json = %s
        WHERE event_id = %s
        """,
        ("{invalid-json", "linux01:worker:invalid:1"),
    )

    worker = _make_worker(connection, EMPTY_CATALOG, batch_size=2)
    result = worker.run_once()

    assert result.claimed == 2
    assert result.processed == 1
    assert result.retried_or_failed == 1
    assert result.incidents_emitted == 0

    rows = connection.execute(
        """
        SELECT event_id, processing_status, last_error, attempts
        FROM soc_event_inbox
        ORDER BY inbox_id
        """
    ).fetchall()

    assert rows[0]["processing_status"] == "pending"
    assert "Invalid JSON payload" in rows[0]["last_error"]
    assert rows[0]["attempts"] == 1

    assert rows[1]["processing_status"] == "processed"
    assert rows[1]["last_error"] is None
    assert rows[1]["attempts"] == 1


def test_incident_failure_rolls_back_inbox_finalization(
    postgres_environment,
    monkeypatch,
):
    connection, _, _ = postgres_environment
    collectors = _prepare_agent(connection)

    collectors.ingest_batch(
        "linux01",
        [_event("linux01:worker:atomicity:1")],
    )

    worker = _make_worker(connection, EMPTY_CATALOG, batch_size=1)
    incident = Incident.create(
        incident_id="inc-postgres-worker-atomicity",
        title="Worker atomicity test",
        summary="Incident persistence failure test",
        severity="warning",
        created_at="2026-10-29T09:00:00+00:00",
    )

    monkeypatch.setattr(
        worker.builder,
        "build",
        lambda result: (incident,),
    )

    def fail_save(incidents):
        raise RuntimeError("simulated incident persistence failure")

    monkeypatch.setattr(
        worker.incidents,
        "save_many_in_transaction",
        fail_save,
    )

    result = worker.run_once()

    assert result.claimed == 1
    assert result.processed == 0
    assert result.retried_or_failed == 1
    assert result.incidents_emitted == 0

    row = connection.execute(
        """
        SELECT processing_status, claim_token, claimed_at,
               last_error, attempts
        FROM soc_event_inbox
        """
    ).fetchone()

    assert row["processing_status"] == "pending"
    assert row["claim_token"] is None
    assert row["claimed_at"] is None
    assert "simulated incident persistence failure" in row["last_error"]
    assert row["attempts"] == 1
    assert worker.incidents.get(incident.incident_id) is None
    assert connection.info.transaction_status.name == "IDLE"


def test_lost_claim_token_prevents_incident_persistence(
    postgres_environment,
    monkeypatch,
):
    connection, _, _ = postgres_environment
    collectors = _prepare_agent(connection)

    collectors.ingest_batch(
        "linux01",
        [_event("linux01:worker:stale-token:1")],
    )

    worker = _make_worker(connection, EMPTY_CATALOG, batch_size=1)
    old_claim = worker.collectors.claim_next_pending()
    assert old_claim is not None

    incident = Incident.create(
        incident_id="inc-postgres-stale-token",
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

    connection.execute(
        """
        UPDATE soc_event_inbox
        SET claim_token = %s,
            claimed_at = CURRENT_TIMESTAMP
        WHERE inbox_id = %s
        """,
        ("new-owner-token", old_claim["inbox_id"]),
    )

    with pytest.raises(
        ClaimOwnershipLost,
        match="Claim token is no longer current",
    ):
        worker._process_claim(old_claim)

    row = connection.execute(
        """
        SELECT processing_status, claim_token, attempts
        FROM soc_event_inbox
        WHERE inbox_id = %s
        """,
        (old_claim["inbox_id"],),
    ).fetchone()

    assert row["processing_status"] == "processing"
    assert row["claim_token"] == "new-owner-token"
    assert row["attempts"] == 1
    assert worker.incidents.get(incident.incident_id) is None
    assert connection.info.transaction_status.name == "IDLE"


def test_run_once_counts_lost_claim_without_failing_new_owner(
    postgres_environment,
    monkeypatch,
):
    connection, _, _ = postgres_environment
    collectors = _prepare_agent(connection)

    collectors.ingest_batch(
        "linux01",
        [_event("linux01:worker:lost-claim:1")],
    )

    worker = _make_worker(connection, EMPTY_CATALOG, batch_size=1)

    def simulate_reclaim(claim):
        connection.execute(
            """
            UPDATE soc_event_inbox
            SET claim_token = %s
            WHERE inbox_id = %s
            """,
            ("new-owner-token", claim["inbox_id"]),
        )
        raise ClaimOwnershipLost(
            "Claim token is no longer current; refusing finalization"
        )

    def unexpected_fail_claim(*args, **kwargs):
        pytest.fail("fail_claim must not run for a lost claim")

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
    assert result.claims_lost == 1

    row = connection.execute(
        """
        SELECT processing_status, claim_token, attempts
        FROM soc_event_inbox
        """
    ).fetchone()

    assert row["processing_status"] == "processing"
    assert row["claim_token"] == "new-owner-token"
    assert row["attempts"] == 1


def test_run_once_respects_batch_limit(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    collectors = _prepare_agent(connection)

    collectors.ingest_batch(
        "linux01",
        [
            _event(f"linux01:worker:batch:{number}")
            for number in range(5)
        ],
    )

    worker = _make_worker(connection, EMPTY_CATALOG, batch_size=2)
    result = worker.run_once()

    assert result.claimed == 2
    assert result.processed == 2
    assert result.retried_or_failed == 0

    counts = connection.execute(
        """
        SELECT processing_status, COUNT(*) AS count
        FROM soc_event_inbox
        GROUP BY processing_status
        ORDER BY processing_status
        """
    ).fetchall()

    actual = {
        row["processing_status"]: row["count"]
        for row in counts
    }

    assert actual == {"pending": 3, "processed": 2}


def test_two_worker_instances_process_distinct_claims(
    postgres_environment,
):
    _, database_url, schema_name = postgres_environment
    setup_connection, _, _ = postgres_environment
    setup_store = _prepare_agent(setup_connection)

    setup_store.ingest_batch(
        "linux01",
        [
            _event("linux01:worker:parallel:1"),
            _event("linux01:worker:parallel:2"),
        ],
    )

    barrier = Barrier(2)

    def worker_thread():
        connection = psycopg.connect(
            database_url,
            autocommit=True,
            row_factory=dict_row,
            application_name="lums-soc-worker-parallel-test",
        )

        try:
            connection.execute(
                sql.SQL("SET search_path TO {}").format(
                    sql.Identifier(schema_name)
                )
            )

            worker = _make_worker(
                connection,
                EMPTY_CATALOG,
                batch_size=1,
            )
            claimed_ids = []

            def process_claim(claim):
                claimed_ids.append(claim["event_id"])
                barrier.wait(timeout=10)

                finished = worker.collectors.finish_claim(
                    claim["inbox_id"],
                    claim["claim_token"],
                )
                assert finished is True
                return 0

            worker._process_claim = process_claim
            result = worker.run_once()

            return tuple(claimed_ids), result

        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(worker_thread),
            executor.submit(worker_thread),
        ]
        results = [future.result(timeout=20) for future in futures]

    claimed = [
        event_id
        for event_ids, _ in results
        for event_id in event_ids
    ]

    assert len(claimed) == 2
    assert len(set(claimed)) == 2
    assert set(claimed) == {
        "linux01:worker:parallel:1",
        "linux01:worker:parallel:2",
    }

    assert all(result.claimed == 1 for _, result in results)
    assert all(result.processed == 1 for _, result in results)


def test_worker_refuses_to_manage_caller_owned_transaction(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    _prepare_agent(connection)

    worker = _make_worker(connection)

    with connection.transaction():
        with pytest.raises(SOCWorkerError):
            worker.run_once()

    assert connection.info.transaction_status.name == "IDLE"


def test_worker_retries_to_terminal_failure_after_attempt_limit(
    postgres_environment,
    monkeypatch,
):
    connection, _, _ = postgres_environment
    collectors = _prepare_agent(connection)

    collectors.ingest_batch(
        "linux01",
        [_event("linux01:worker:terminal:1")],
    )

    worker = _make_worker(
        connection,
        EMPTY_CATALOG,
        batch_size=1,
        max_attempts=1,
    )

    def always_fail(claim):
        raise RuntimeError("simulated permanent processing failure")

    monkeypatch.setattr(worker, "_process_claim", always_fail)

    result = worker.run_once()

    assert result.claimed == 1
    assert result.processed == 0
    assert result.retried_or_failed == 1

    row = connection.execute(
        """
        SELECT processing_status, attempts, claim_token, claimed_at,
               last_error
        FROM soc_event_inbox
        """
    ).fetchone()

    assert row["processing_status"] == "failed"
    assert row["attempts"] == 1
    assert row["claim_token"] is None
    assert row["claimed_at"] is None
    assert "simulated permanent processing failure" in row["last_error"]


def test_preflight_uses_catalog_without_table_data_privileges(
    postgres_environment,
):
    connection, _, schema_name = postgres_environment
    role_name = f"lums_soc_preflight_{uuid4().hex}"
    role_created = False
    role_active = False

    try:
        connection.execute(
            sql.SQL(
                """
                CREATE ROLE {} NOLOGIN
                NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOINHERIT NOREPLICATION NOBYPASSRLS
                """
            ).format(sql.Identifier(role_name))
        )
        role_created = True

        connection.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(schema_name),
                sql.Identifier(role_name),
            )
        )

        connection.execute(
            sql.SQL(
                "GRANT SELECT ON TABLE {}.schema_migrations TO {}"
            ).format(
                sql.Identifier(schema_name),
                sql.Identifier(role_name),
            )
        )

        connection.execute(
            sql.SQL("SET ROLE {}").format(sql.Identifier(role_name))
        )
        role_active = True

        identity = connection.execute(
            "SELECT current_user AS role_name"
        ).fetchone()
        assert identity["role_name"] == role_name

        privileges = connection.execute(
            """
            SELECT
                has_table_privilege(
                    current_user, %s, 'SELECT'
                ) AS can_read_agents,
                has_table_privilege(
                    current_user, %s, 'SELECT'
                ) AS can_read_inbox,
                has_schema_privilege(
                    current_user, current_schema(), 'CREATE'
                ) AS can_create_objects
            """,
            (
                f"{schema_name}.soc_collector_agents",
                f"{schema_name}.soc_event_inbox",
            ),
        ).fetchone()

        assert privileges["can_read_agents"] is False
        assert privileges["can_read_inbox"] is False
        assert privileges["can_create_objects"] is False

        visible = connection.execute(
            """
            SELECT DISTINCT table_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
            """
        ).fetchall()
        visible_names = {row["table_name"] for row in visible}

        assert "soc_collector_agents" not in visible_names
        assert "soc_event_inbox" not in visible_names

        validate_postgres_worker_schema(connection)
        worker = _make_worker(connection)

        assert isinstance(worker.collectors, PostgresCollectorStore)

    finally:
        if role_active:
            connection.execute("RESET ROLE")

        if role_created:
            connection.execute(
                sql.SQL(
                    "REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA {} FROM {}"
                ).format(
                    sql.Identifier(schema_name),
                    sql.Identifier(role_name),
                )
            )
            connection.execute(
                sql.SQL(
                    "REVOKE ALL PRIVILEGES ON SCHEMA {} FROM {}"
                ).format(
                    sql.Identifier(schema_name),
                    sql.Identifier(role_name),
                )
            )
            connection.execute(
                sql.SQL("DROP ROLE {}").format(
                    sql.Identifier(role_name)
                )
            )


def test_worker_processes_detection_with_minimal_column_privileges(
    postgres_environment,
):
    connection, database_url, schema_name = postgres_environment

    event_id = f"linux01:least-privilege:{uuid4().hex}"
    _prepare_agent(connection).ingest_batch(
        "linux01",
        [_event(event_id)],
    )

    privilege_role_name = f"lums_soc_worker_privs_{uuid4().hex}"
    login_role_name = f"lums_soc_worker_login_{uuid4().hex}"
    role_password = token_urlsafe(32)

    limited = None
    privilege_role_created = False
    login_role_created = False
    database_name = connection.execute(
        "SELECT current_database() AS name"
    ).fetchone()["name"]
    connect_grant_survived_cleanup = False

    try:
        connection.execute(
            sql.SQL(
                """
                CREATE ROLE {} NOLOGIN NOINHERIT
                NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS
                """
            ).format(sql.Identifier(privilege_role_name))
        )
        privilege_role_created = True

        connection.execute(
            sql.SQL(
                """
                CREATE ROLE {} LOGIN PASSWORD {}
                INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
                NOREPLICATION NOBYPASSRLS
                """
            ).format(
                sql.Identifier(login_role_name),
                sql.Literal(role_password),
            )
        )
        login_role_created = True

        connection.execute(
            sql.SQL(
                "GRANT {} TO {} WITH INHERIT TRUE, SET FALSE"
            ).format(
                sql.Identifier(privilege_role_name),
                sql.Identifier(login_role_name),
            )
        )

        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database_name),
                sql.Identifier(privilege_role_name),
            )
        )

        direct_connect = connection.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_database AS d
                CROSS JOIN LATERAL aclexplode(
                    COALESCE(d.datacl, acldefault('d', d.datdba))
                ) AS acl
                JOIN pg_roles AS grantee
                  ON grantee.oid = acl.grantee
                WHERE d.datname = current_database()
                  AND grantee.rolname = %s
                  AND acl.privilege_type = 'CONNECT'
            ) AS granted
            """,
            (privilege_role_name,),
        ).fetchone()
        assert direct_connect["granted"] is True

        connection.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(schema_name),
                sql.Identifier(privilege_role_name),
            )
        )

        column_grants = (
            (
                "schema_migrations",
                "SELECT",
                ("version", "checksum", "description"),
            ),
            (
                "soc_event_inbox",
                "SELECT",
                (
                    "inbox_id",
                    "agent_id",
                    "event_id",
                    "payload_json",
                    "received_at",
                    "processing_status",
                    "attempts",
                    "claimed_at",
                    "claim_token",
                    "last_error",
                ),
            ),
            (
                "soc_event_inbox",
                "UPDATE",
                (
                    "processing_status",
                    "processed_at",
                    "last_error",
                    "claim_token",
                    "claimed_at",
                    "attempts",
                ),
            ),
            (
                "soc_incidents",
                "SELECT",
                (
                    "incident_id",
                    "title",
                    "summary",
                    "severity",
                    "status",
                    "created_at",
                    "updated_at",
                ),
            ),
            (
                "soc_incidents",
                "INSERT",
                (
                    "incident_id",
                    "title",
                    "summary",
                    "severity",
                    "status",
                    "created_at",
                    "updated_at",
                ),
            ),
            (
                "soc_incident_evidence",
                "SELECT",
                (
                    "evidence_sequence",
                    "evidence_id",
                    "incident_id",
                    "kind",
                    "reference_id",
                    "description",
                    "observed_at",
                ),
            ),
            (
                "soc_incident_evidence",
                "INSERT",
                (
                    "evidence_id",
                    "incident_id",
                    "kind",
                    "reference_id",
                    "description",
                    "observed_at",
                ),
            ),
            (
                "soc_incident_history",
                "SELECT",
                ("incident_id",),
            ),
            (
                "soc_incident_history",
                "INSERT",
                (
                    "incident_id",
                    "old_status",
                    "new_status",
                    "changed_at",
                    "changed_by",
                ),
            ),
        )

        for table, privilege, columns in column_grants:
            connection.execute(
                sql.SQL("GRANT {} ({}) ON TABLE {}.{} TO {}").format(
                    sql.SQL(privilege),
                    sql.SQL(", ").join(
                        sql.Identifier(column) for column in columns
                    ),
                    sql.Identifier(schema_name),
                    sql.Identifier(table),
                    sql.Identifier(privilege_role_name),
                )
            )

        evidence_sequence = connection.execute(
            "SELECT pg_get_serial_sequence(%s, %s) AS name",
            (
                f"{schema_name}.soc_incident_evidence",
                "evidence_sequence",
            ),
        ).fetchone()["name"]

        history_sequence = connection.execute(
            "SELECT pg_get_serial_sequence(%s, %s) AS name",
            (
                f"{schema_name}.soc_incident_history",
                "history_id",
            ),
        ).fetchone()["name"]

        assert evidence_sequence is not None
        assert history_sequence is not None

        limited_dsn = make_conninfo(
            database_url,
            user=login_role_name,
            password=role_password,
            options=f"-csearch_path={schema_name}",
            application_name="lums-soc-worker-limited-integration",
        )

        limited = psycopg.connect(
            limited_dsn,
            autocommit=True,
            row_factory=dict_row,
        )

        identity = limited.execute(
            """
            SELECT
                current_user,
                session_user,
                current_schema(),
                r.rolsuper,
                r.rolcreatedb,
                r.rolcreaterole,
                r.rolbypassrls
            FROM pg_roles AS r
            WHERE r.rolname = current_user
            """
        ).fetchone()

        assert identity["current_user"] == login_role_name
        assert identity["session_user"] == login_role_name
        assert identity["current_schema"] == schema_name
        assert identity["rolsuper"] is False
        assert identity["rolcreatedb"] is False
        assert identity["rolcreaterole"] is False
        assert identity["rolbypassrls"] is False

        group_state = limited.execute(
            """
            SELECT
                rolcanlogin,
                rolsuper,
                rolcreatedb,
                rolcreaterole,
                rolbypassrls
            FROM pg_roles
            WHERE rolname = %s
            """,
            (privilege_role_name,),
        ).fetchone()

        assert group_state == {
            "rolcanlogin": False,
            "rolsuper": False,
            "rolcreatedb": False,
            "rolcreaterole": False,
            "rolbypassrls": False,
        }

        membership = limited.execute(
            """
            SELECT
                membership.inherit_option,
                membership.set_option,
                membership.admin_option
            FROM pg_auth_members AS membership
            JOIN pg_roles AS member
              ON member.oid = membership.member
            JOIN pg_roles AS granted
              ON granted.oid = membership.roleid
            WHERE member.rolname = current_user
              AND granted.rolname = %s
            """,
            (privilege_role_name,),
        ).fetchone()

        assert membership == {
            "inherit_option": True,
            "set_option": False,
            "admin_option": False,
        }

        database_privileges = limited.execute(
            """
            SELECT
                has_database_privilege(
                    current_user, current_database(), 'CONNECT'
                ) AS login_can_connect,
                has_database_privilege(
                    %s, current_database(), 'CONNECT'
                ) AS privilege_role_can_connect
            """,
            (privilege_role_name,),
        ).fetchone()
        assert database_privileges == {
            "login_can_connect": True,
            "privilege_role_can_connect": True,
        }

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            limited.execute(
                sql.SQL("SET ROLE {}").format(
                    sql.Identifier(privilege_role_name)
                )
            )

        assert limited.execute(
            "SELECT 1 AS usable"
        ).fetchone()["usable"] == 1

        privileges = limited.execute(
            """
            SELECT
                has_table_privilege(
                    current_user, %s, 'SELECT'
                ) AS agents_select,
                has_table_privilege(
                    current_user, %s, 'DELETE'
                ) AS inbox_delete,
                has_table_privilege(
                    current_user, %s, 'TRUNCATE'
                ) AS inbox_truncate,
                has_column_privilege(
                    current_user, %s, 'processing_status', 'UPDATE'
                ) AS inbox_status_update,
                has_column_privilege(
                    current_user, %s, 'payload_json', 'UPDATE'
                ) AS inbox_payload_update,
                has_column_privilege(
                    current_user, %s, 'updated_at', 'UPDATE'
                ) AS incident_updated_at_update,
                has_schema_privilege(
                    current_user, current_schema(), 'CREATE'
                ) AS schema_create
            """,
            (
                f"{schema_name}.soc_collector_agents",
                f"{schema_name}.soc_event_inbox",
                f"{schema_name}.soc_event_inbox",
                f"{schema_name}.soc_event_inbox",
                f"{schema_name}.soc_event_inbox",
                f"{schema_name}.soc_incidents",
            ),
        ).fetchone()

        assert privileges["agents_select"] is False
        assert privileges["inbox_delete"] is False
        assert privileges["inbox_truncate"] is False
        assert privileges["inbox_status_update"] is True
        assert privileges["inbox_payload_update"] is False
        assert privileges["incident_updated_at_update"] is False
        assert privileges["schema_create"] is False

        role_names = [login_role_name, privilege_role_name]

        ownership = limited.execute(
            """
            SELECT
                EXISTS (
                    SELECT 1
                    FROM pg_namespace
                    WHERE nspname = current_schema()
                      AND nspowner IN (
                          SELECT oid
                          FROM pg_roles
                          WHERE rolname = ANY(%s)
                      )
                ) AS owns_schema,
                EXISTS (
                    SELECT 1
                    FROM pg_class AS c
                    JOIN pg_namespace AS n
                      ON n.oid = c.relnamespace
                    WHERE n.nspname = current_schema()
                      AND c.relowner IN (
                          SELECT oid
                          FROM pg_roles
                          WHERE rolname = ANY(%s)
                      )
                ) AS owns_tables
            """,
            (role_names, role_names),
        ).fetchone()

        assert ownership["owns_schema"] is False
        assert ownership["owns_tables"] is False

        sequence_privileges = limited.execute(
            """
            SELECT
                has_sequence_privilege(
                    current_user, %s, 'USAGE'
                ) AS evidence_usage,
                has_sequence_privilege(
                    current_user, %s, 'USAGE'
                ) AS history_usage
            """,
            (evidence_sequence, history_sequence),
        ).fetchone()

        assert sequence_privileges["evidence_usage"] is False
        assert sequence_privileges["history_usage"] is False

        worker = _make_worker(
            limited,
            DETECTION_CATALOG,
            batch_size=1,
        )
        result = worker.run_once()

        assert result.claimed == 1
        assert result.processed == 1
        assert result.retried_or_failed == 0
        assert result.incidents_emitted == 1
        assert result.claims_lost == 0

        # Exercise failure handling and stale-claim recovery with the
        # same restricted worker login, not with the bootstrap connection.
        invalid_event_id = (
            f"linux01:least-privilege-invalid:{uuid4().hex}"
        )
        stale_event_id = (
            f"linux01:least-privilege-stale:{uuid4().hex}"
        )

        PostgresCollectorStore(connection).ingest_batch(
            "linux01",
            [
                _event(invalid_event_id),
                _event(stale_event_id),
            ],
        )

        connection.execute(
            """
            UPDATE soc_event_inbox
            SET payload_json = %s
            WHERE event_id = %s
            """,
            ("{invalid-json", invalid_event_id),
        )

        stale_row = connection.execute(
            """
            UPDATE soc_event_inbox
            SET
                processing_status = 'processing',
                attempts = 1,
                claim_token = %s,
                claimed_at = NOW() - INTERVAL '1 hour'
            WHERE event_id = %s
            RETURNING inbox_id
            """,
            ("stale-test-claim-token", stale_event_id),
        ).fetchone()
        assert stale_row is not None

        retry_worker = _make_worker(
            limited,
            EMPTY_CATALOG,
            batch_size=2,
        )
        retry_result = retry_worker.run_once()

        assert retry_result.claimed == 2
        assert retry_result.processed == 1
        assert retry_result.retried_or_failed == 1
        assert retry_result.claims_lost == 0

        limited.close()
        limited = None

        inbox = connection.execute(
            """
            SELECT processing_status, attempts, claim_token,
                   claimed_at, processed_at
            FROM soc_event_inbox
            WHERE event_id = %s
            """,
            (event_id,),
        ).fetchone()

        assert inbox is not None
        assert inbox["processing_status"] == "processed"
        assert inbox["attempts"] == 1
        assert inbox["claim_token"] is None
        assert inbox["claimed_at"] is None
        assert inbox["processed_at"] is not None

        invalid_state = connection.execute(
            """
            SELECT processing_status, attempts, claim_token,
                   claimed_at, last_error
            FROM soc_event_inbox
            WHERE event_id = %s
            """,
            (invalid_event_id,),
        ).fetchone()
        assert invalid_state is not None
        assert invalid_state["processing_status"] == "pending"
        assert invalid_state["attempts"] == 1
        assert invalid_state["claim_token"] is None
        assert invalid_state["claimed_at"] is None
        assert "Invalid JSON payload" in invalid_state["last_error"]

        stale_state = connection.execute(
            """
            SELECT processing_status, attempts, claim_token,
                   claimed_at, processed_at
            FROM soc_event_inbox
            WHERE event_id = %s
            """,
            (stale_event_id,),
        ).fetchone()
        assert stale_state is not None
        assert stale_state["processing_status"] == "processed"
        assert stale_state["attempts"] == 2
        assert stale_state["claim_token"] is None
        assert stale_state["claimed_at"] is None
        assert stale_state["processed_at"] is not None

        incidents = connection.execute(
            """
            SELECT incident_id, title, severity
            FROM soc_incidents
            """
        ).fetchall()

        assert len(incidents) == 1
        incident_id = incidents[0]["incident_id"]
        assert incidents[0]["title"] == (
            "Detection: Authentication failure"
        )
        assert incidents[0]["severity"] == "critical"

        evidence = connection.execute(
            """
            SELECT evidence_sequence, kind
            FROM soc_incident_evidence
            WHERE incident_id = %s
            ORDER BY evidence_sequence
            """,
            (incident_id,),
        ).fetchall()

        assert len(evidence) == 2
        assert all(row["evidence_sequence"] > 0 for row in evidence)
        assert {row["kind"] for row in evidence} == {
            "detection",
            "event",
        }

        history = connection.execute(
            """
            SELECT history_id, old_status, new_status, changed_by
            FROM soc_incident_history
            WHERE incident_id = %s
            """,
            (incident_id,),
        ).fetchall()

        assert len(history) == 1
        assert history[0]["history_id"] > 0
        assert history[0]["old_status"] is None
        assert history[0]["new_status"] == "open"
        assert history[0]["changed_by"] == "system"

    finally:
        if limited is not None:
            limited.close()

        if privilege_role_created and login_role_created:
            connection.execute(
                sql.SQL("REVOKE {} FROM {}").format(
                    sql.Identifier(privilege_role_name),
                    sql.Identifier(login_role_name),
                )
            )

        if login_role_created:
            connection.execute(
                sql.SQL("DROP OWNED BY {}").format(
                    sql.Identifier(login_role_name)
                )
            )

        if privilege_role_created:
            connection.execute(
                sql.SQL("DROP OWNED BY {}").format(
                    sql.Identifier(privilege_role_name)
                )
            )

            remaining_connect = connection.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_database AS d
                    CROSS JOIN LATERAL aclexplode(
                        COALESCE(d.datacl, acldefault('d', d.datdba))
                    ) AS acl
                    JOIN pg_roles AS grantee
                      ON grantee.oid = acl.grantee
                    WHERE d.datname = current_database()
                      AND grantee.rolname = %s
                      AND acl.privilege_type = 'CONNECT'
                ) AS granted
                """,
                (privilege_role_name,),
            ).fetchone()
            connect_grant_survived_cleanup = remaining_connect["granted"]

            # Ensure cleanup even if DROP OWNED did not remove the
            # database-level ACL. The assertion below still fails the test.
            if connect_grant_survived_cleanup:
                connection.execute(
                    sql.SQL(
                        "REVOKE CONNECT ON DATABASE {} FROM {}"
                    ).format(
                        sql.Identifier(database_name),
                        sql.Identifier(privilege_role_name),
                    )
                )

        if login_role_created:
            connection.execute(
                sql.SQL("DROP ROLE {}").format(
                    sql.Identifier(login_role_name)
                )
            )

        if privilege_role_created:
            connection.execute(
                sql.SQL("DROP ROLE {}").format(
                    sql.Identifier(privilege_role_name)
                )
            )

        assert connect_grant_survived_cleanup is False, (
            "DROP OWNED did not remove the worker role's database CONNECT grant"
        )
