"""PostgreSQL integration tests for the SOC collector store."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from postgres_test_support import require_test_database_url, run_cleanup
from server.migration_runner import run_migrations
from server.migrations.soc_storage import SOC_STORAGE_MIGRATION
from server.soc.collector_store import (
    CollectorNotFoundError,
    CollectorRevokedError,
    CollectorStoreError,
    EventIdConflictError,
)
from server.soc.postgres_collector_store import PostgresCollectorStore


@pytest.fixture
def postgres_environment():
    database_url = require_test_database_url()

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-soc-collector-setup",
    )

    connection = None
    schema_name = f"lums_soc_collector_test_{uuid4().hex}"
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
            application_name="lums-soc-collector-test",
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


def _register(store, agent_id="linux01", fingerprint="A" * 64):
    return store.register_agent(
        agent_id,
        "Linux integration test host",
        fingerprint,
    )


def _event(event_id, **values):
    return {
        "event_id": event_id,
        "source": "linux01",
        "event_type": "linux.auth.failure",
        **values,
    }


def test_register_lookup_and_duplicate_protection(postgres_environment):
    connection, _, _ = postgres_environment
    store = PostgresCollectorStore(connection)

    registered = _register(store)

    assert registered["agent_id"] == "linux01"
    assert registered["certificate_sha256"] == "a" * 64
    assert registered["status"] == "active"
    assert registered["created_at"].endswith("+00:00")

    assert store.get_agent_by_fingerprint("A" * 64) == registered
    assert store.get_agent_by_fingerprint("c" * 64) is None

    with pytest.raises(ValueError, match="already registered"):
        _register(store)

    with pytest.raises(ValueError, match="already registered"):
        _register(store, agent_id="linux02")


def test_fingerprint_validation_is_normalized(postgres_environment):
    connection, _, _ = postgres_environment
    store = PostgresCollectorStore(connection)

    with pytest.raises(ValueError, match="SHA-256"):
        store.register_agent(
            "linux-bad",
            "Invalid fingerprint",
            "not-a-fingerprint",
        )

    registered = store.register_agent(
        "linux-upper",
        "Uppercase fingerprint",
        "B" * 64,
    )

    assert registered["certificate_sha256"] == "b" * 64
    assert store.get_agent_by_fingerprint("B" * 64)["agent_id"] == (
        "linux-upper"
    )


def test_revoke_agent_is_idempotent_and_blocks_ingestion(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresCollectorStore(connection)
    _register(store)

    assert store.revoke_agent("linux01") is True
    first = store.get_agent_by_fingerprint("a" * 64)
    assert first["status"] == "revoked"

    assert store.revoke_agent("linux01") is True
    second = store.get_agent_by_fingerprint("a" * 64)
    assert second["revoked_at"] if "revoked_at" in second else True

    with pytest.raises(CollectorRevokedError):
        store.ingest_batch("linux01", [_event("linux01:revoked:1")])

    assert store.revoke_agent("missing-agent") is False


def test_ingest_is_canonical_idempotent_and_hashes_utf8(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresCollectorStore(connection)
    _register(store)

    payload = {
        "event_id": "linux01:boot:1",
        "message": "Grüße aus Köln",
        "nested": {"z": 2, "a": 1},
    }
    replay = {
        "nested": {"a": 1, "z": 2},
        "message": "Grüße aus Köln",
        "event_id": "linux01:boot:1",
    }

    first = store.ingest_batch("linux01", [payload])
    second = store.ingest_batch("linux01", [replay])

    assert first.accepted == 1
    assert first.duplicates == 0
    assert second.accepted == 0
    assert second.duplicates == 1
    assert second.event_ids == ("linux01:boot:1",)

    row = connection.execute(
        """
        SELECT payload_json, payload_sha256
        FROM soc_event_inbox
        WHERE agent_id = %s AND event_id = %s
        """,
        ("linux01", "linux01:boot:1"),
    ).fetchone()

    import hashlib
    import json

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    assert row["payload_json"] == encoded
    assert row["payload_sha256"] == hashlib.sha256(
        encoded.encode("utf-8")
    ).hexdigest()


def test_conflicting_event_id_rolls_back_the_entire_batch(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresCollectorStore(connection)
    _register(store)

    original = _event("linux01:conflict:1", message="original")
    store.ingest_batch("linux01", [original])

    changed = _event("linux01:conflict:1", message="changed")
    new_event = _event("linux01:new:2", message="must roll back")

    with pytest.raises(EventIdConflictError):
        store.ingest_batch("linux01", [new_event, changed])

    rows = connection.execute(
        """
        SELECT event_id
        FROM soc_event_inbox
        WHERE agent_id = %s
        ORDER BY inbox_id
        """,
        ("linux01",),
    ).fetchall()

    assert [row["event_id"] for row in rows] == [
        "linux01:conflict:1"
    ]


def test_unknown_agent_and_invalid_batches_are_rejected(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresCollectorStore(connection)

    with pytest.raises(CollectorNotFoundError):
        store.ingest_batch(
            "unknown-agent",
            [_event("unknown-agent:event:1")],
        )

    _register(store)

    with pytest.raises(ValueError, match="repeated event IDs"):
        store.ingest_batch(
            "linux01",
            [
                _event("linux01:duplicate:1", value=1),
                _event("linux01:duplicate:1", value=2),
            ],
        )

    with pytest.raises(ValueError, match="maximum event count"):
        store.ingest_batch(
            "linux01",
            [
                _event(f"linux01:batch:{number}")
                for number in range(501)
            ],
        )

    assert connection.execute(
        "SELECT COUNT(*) AS count FROM soc_event_inbox"
    ).fetchone()["count"] == 0


def test_claim_finish_and_token_guard(postgres_environment):
    connection, _, _ = postgres_environment
    store = PostgresCollectorStore(connection)
    _register(store)

    store.ingest_batch(
        "linux01",
        [
            _event("linux01:claim:1", sequence=1),
            _event("linux01:claim:2", sequence=2),
        ],
    )

    claims = store.claim_pending(limit=2)

    assert [item["event_id"] for item in claims] == [
        "linux01:claim:1",
        "linux01:claim:2",
    ]
    assert all(item["processing_status"] == "processing" for item in claims)
    assert all(item["attempts"] == 1 for item in claims)
    assert all(item["payload_error"] is None for item in claims)
    assert len({item["claim_token"] for item in claims}) == 2

    first = claims[0]

    assert store.finish_claim(
        first["inbox_id"],
        "not-the-current-token",
    ) is False

    assert store.finish_claim(
        first["inbox_id"],
        first["claim_token"],
    ) is True

    assert store.finish_claim(
        first["inbox_id"],
        first["claim_token"],
    ) is False

    rows = connection.execute(
        """
        SELECT event_id, processing_status, claim_token, claimed_at,
               processed_at, attempts
        FROM soc_event_inbox
        ORDER BY inbox_id
        """
    ).fetchall()

    assert rows[0]["processing_status"] == "processed"
    assert rows[0]["claim_token"] is None
    assert rows[0]["claimed_at"] is None
    assert rows[0]["processed_at"] is not None
    assert rows[0]["attempts"] == 1

    assert rows[1]["processing_status"] == "processing"


def test_fail_claim_retries_then_exhausts_attempt_limit(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresCollectorStore(connection)
    _register(store)

    store.ingest_batch(
        "linux01",
        [_event("linux01:retry:1")],
    )

    first = store.claim_next_pending()
    assert first is not None
    assert first["attempts"] == 1

    assert store.fail_claim(
        first["inbox_id"],
        "stale-token",
        "must not change state",
        max_attempts=2,
    ) is False

    assert store.fail_claim(
        first["inbox_id"],
        first["claim_token"],
        "temporary failure",
        max_attempts=2,
    ) is True

    retry = store.claim_next_pending()
    assert retry is not None
    assert retry["attempts"] == 2
    assert retry["claim_token"] != first["claim_token"]

    assert store.fail_claim(
        retry["inbox_id"],
        retry["claim_token"],
        "permanent failure",
        max_attempts=2,
    ) is True

    row = connection.execute(
        """
        SELECT processing_status, claim_token, claimed_at,
               last_error, attempts
        FROM soc_event_inbox
        WHERE inbox_id = %s
        """,
        (first["inbox_id"],),
    ).fetchone()

    assert row["processing_status"] == "failed"
    assert row["claim_token"] is None
    assert row["claimed_at"] is None
    assert row["last_error"] == "permanent failure"
    assert row["attempts"] == 2


def test_stale_claim_recovery_requeues_or_fails(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresCollectorStore(connection)
    _register(store)

    store.ingest_batch(
        "linux01",
        [
            _event("linux01:stale:retry"),
            _event("linux01:stale:terminal"),
        ],
    )

    claims = store.claim_pending(limit=2)
    assert len(claims) == 2

    old_timestamp = datetime.now(timezone.utc) - timedelta(minutes=10)

    connection.execute(
        """
        UPDATE soc_event_inbox
        SET claimed_at = %s
        WHERE inbox_id IN (%s, %s)
        """,
        (
            old_timestamp,
            claims[0]["inbox_id"],
            claims[1]["inbox_id"],
        ),
    )

    recovered = store.recover_stale_claims(
        stale_after_seconds=60,
        max_attempts=2,
    )
    assert recovered == 2

    rows = connection.execute(
        """
        SELECT inbox_id, processing_status, claim_token,
               claimed_at, last_error, attempts
        FROM soc_event_inbox
        ORDER BY inbox_id
        """
    ).fetchall()

    assert all(row["processing_status"] == "pending" for row in rows)
    assert all(row["claim_token"] is None for row in rows)
    assert all(row["claimed_at"] is None for row in rows)
    assert all(row["attempts"] == 1 for row in rows)

    retry = store.claim_pending(limit=2, max_attempts=2)
    assert len(retry) == 2
    assert all(item["attempts"] == 2 for item in retry)

    for item in retry:
        assert store.fail_claim(
            item["inbox_id"],
            item["claim_token"],
            "retry limit reached",
            max_attempts=2,
        )

    assert connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM soc_event_inbox
        WHERE processing_status = 'failed'
        """
    ).fetchone()["count"] == 2


def test_claim_pending_skips_rows_locked_by_another_connection(
    postgres_environment,
):
    connection, database_url, schema_name = postgres_environment
    store = PostgresCollectorStore(connection)
    _register(store)

    store.ingest_batch(
        "linux01",
        [
            _event(f"linux01:parallel:{number:03d}")
            for number in range(20)
        ],
    )

    other = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-soc-collector-concurrency-test",
    )

    try:
        other.execute(
            sql.SQL("SET search_path TO {}").format(
                sql.Identifier(schema_name)
            )
        )
        other_store = PostgresCollectorStore(other)

        # Hold the first ten pending rows locked on connection A.
        with connection.transaction():
            locked = connection.execute(
                """
                SELECT inbox_id
                FROM soc_event_inbox
                WHERE processing_status = 'pending'
                ORDER BY inbox_id
                LIMIT 10
                FOR UPDATE
                """
            ).fetchall()

            assert len(locked) == 10

            # Connection B must skip those ten locked rows and claim the next ten.
            second_batch = other_store.claim_pending(limit=10)

            assert len(second_batch) == 10
            locked_ids = {row["inbox_id"] for row in locked}
            second_ids = {row["inbox_id"] for row in second_batch}

            assert locked_ids.isdisjoint(second_ids)
            assert min(second_ids) > max(locked_ids)

        # Once connection A releases its locks, it can claim the first ten.
        first_batch = store.claim_pending(limit=10)

        assert len(first_batch) == 10
        first_ids = {row["inbox_id"] for row in first_batch}

        assert first_ids == {row["inbox_id"] for row in locked}
        assert first_ids.isdisjoint(second_ids)

        all_claimed_ids = first_ids | second_ids
        assert len(all_claimed_ids) == 20

    finally:
        other.close()


def test_mutating_methods_reject_caller_owned_transactions(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresCollectorStore(connection)

    with connection.transaction():
        with pytest.raises(
            CollectorStoreError,
            match="existing transaction",
        ):
            store.register_agent(
                "linux-transaction",
                "Transaction guard",
                "d" * 64,
            )

    assert store.get_agent_by_fingerprint("d" * 64) is None


def test_list_pending_decodes_payload_and_preserves_order(
    postgres_environment,
):
    connection, _, _ = postgres_environment
    store = PostgresCollectorStore(connection)
    _register(store)

    store.ingest_batch(
        "linux01",
        [
            _event("linux01:list:1", sequence=1),
            _event("linux01:list:2", sequence=2),
        ],
    )

    rows = store.list_pending(limit=10)

    assert [row["event_id"] for row in rows] == [
        "linux01:list:1",
        "linux01:list:2",
    ]
    assert [row["payload"]["sequence"] for row in rows] == [1, 2]
    assert all(row["processing_status"] == "pending" for row in rows)

    assert store.claim_pending(limit=2)
    assert store.list_pending(limit=10) == ()

def _wait_for_advisory_lock_wait(observer, application_name):
    """Wait until the named PostgreSQL backend is blocked on an advisory lock."""
    deadline = time.monotonic() + 5.0

    while time.monotonic() < deadline:
        row = observer.execute(
            """
            SELECT wait_event_type, wait_event
            FROM pg_stat_activity
            WHERE application_name = %s
              AND state = 'active'
            """,
            (application_name,),
        ).fetchone()

        if (
            row is not None
            and row["wait_event_type"] == "Lock"
            and row["wait_event"] == "advisory"
        ):
            return

        time.sleep(0.01)

    pytest.fail(
        f"Backend {application_name!r} did not wait for an advisory lock."
    )


def test_ingestion_waits_for_concurrent_revocation_and_rechecks_agent_state(
    postgres_environment,
):
    setup_connection, database_url, schema_name = postgres_environment
    _register(PostgresCollectorStore(setup_connection))

    holder = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-soc-lifecycle-holder",
    )
    observer = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-soc-lifecycle-observer",
    )

    holder.execute(
        sql.SQL("SET search_path TO {}").format(
            sql.Identifier(schema_name)
        )
    )

    worker_application_name = (
        "lums-soc-lock-ingest-" + uuid4().hex[:8]
    )
    event_id = "linux01:revocation-race:" + uuid4().hex
    event = _event(event_id)

    def ingest_on_separate_connection():
        with psycopg.connect(
            database_url,
            autocommit=True,
            row_factory=dict_row,
            application_name=worker_application_name,
        ) as worker:
            worker.execute(
                sql.SQL("SET search_path TO {}").format(
                    sql.Identifier(schema_name)
                )
            )
            return PostgresCollectorStore(worker).ingest_batch(
                "linux01",
                [event],
            )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            with holder.transaction():
                PostgresCollectorStore(
                    holder
                )._lock_agent_lifecycle("linux01")

                future = executor.submit(
                    ingest_on_separate_connection
                )

                _wait_for_advisory_lock_wait(
                    observer,
                    worker_application_name,
                )

                # Simulate a revocation transaction holding the same
                # lifecycle lock. Ingestion must re-check status afterward.
                holder.execute(
                    """
                    UPDATE soc_collector_agents
                    SET status = 'revoked',
                        revoked_at = current_timestamp
                    WHERE agent_id = %s
                    """,
                    ("linux01",),
                )

            with pytest.raises(CollectorRevokedError):
                future.result(timeout=5)

        persisted = setup_connection.execute(
            """
            SELECT inbox_id
            FROM soc_event_inbox
            WHERE agent_id = %s AND event_id = %s
            """,
            ("linux01", event_id),
        ).fetchone()

        assert persisted is None

    finally:
        observer.close()
        holder.close()


def test_revocation_waits_for_concurrent_agent_lifecycle_lock(
    postgres_environment,
):
    setup_connection, database_url, schema_name = postgres_environment
    _register(PostgresCollectorStore(setup_connection))

    holder = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-soc-revoke-holder",
    )
    observer = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name="lums-soc-revoke-observer",
    )

    holder.execute(
        sql.SQL("SET search_path TO {}").format(
            sql.Identifier(schema_name)
        )
    )

    revoker_application_name = (
        "lums-soc-lock-revoke-" + uuid4().hex[:8]
    )

    def revoke_on_separate_connection():
        with psycopg.connect(
            database_url,
            autocommit=True,
            row_factory=dict_row,
            application_name=revoker_application_name,
        ) as revoker:
            revoker.execute(
                sql.SQL("SET search_path TO {}").format(
                    sql.Identifier(schema_name)
                )
            )
            return PostgresCollectorStore(revoker).revoke_agent(
                "linux01"
            )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            with holder.transaction():
                PostgresCollectorStore(
                    holder
                )._lock_agent_lifecycle("linux01")

                future = executor.submit(
                    revoke_on_separate_connection
                )

                _wait_for_advisory_lock_wait(
                    observer,
                    revoker_application_name,
                )

            assert future.result(timeout=5) is True

        agent = PostgresCollectorStore(
            setup_connection
        ).get_agent_by_fingerprint("a" * 64)

        assert agent is not None
        assert agent["status"] == "revoked"

    finally:
        observer.close()
        holder.close()

def test_collector_ingests_with_minimal_column_privileges(
    postgres_environment,
):
    connection, database_url, schema_name = postgres_environment

    _register(PostgresCollectorStore(connection))

    privilege_role_name = f"lums_soc_collector_privs_{uuid4().hex}"
    login_role_name = f"lums_soc_collector_login_{uuid4().hex}"
    role_password = uuid4().hex + uuid4().hex

    limited = None
    privilege_role_created = False
    login_role_created = False
    membership_created = False

    try:
        database_name = connection.execute(
            "SELECT current_database() AS name"
        ).fetchone()["name"]

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
        membership_created = True

        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database_name),
                sql.Identifier(privilege_role_name),
            )
        )

        connection.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(schema_name),
                sql.Identifier(privilege_role_name),
            )
        )

        column_grants = (
            (
                "soc_collector_agents",
                "SELECT",
                (
                    "agent_id",
                    "display_name",
                    "certificate_sha256",
                    "status",
                    "created_at",
                ),
            ),
            (
                "soc_event_inbox",
                "SELECT",
                (
                    "inbox_id",
                    "agent_id",
                    "event_id",
                    "payload_sha256",
                ),
            ),
            (
                "soc_event_inbox",
                "INSERT",
                (
                    "agent_id",
                    "event_id",
                    "payload_json",
                    "payload_sha256",
                    "received_at",
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

        limited_dsn = make_conninfo(
            database_url,
            user=login_role_name,
            password=role_password,
            options=f"-csearch_path={schema_name}",
            application_name="lums-soc-collector-limited",
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
                r.rolreplication,
                r.rolbypassrls,
                r.rolinherit,
                has_database_privilege(
                    current_user, current_database(), 'CONNECT'
                ) AS can_connect
            FROM pg_roles AS r
            WHERE r.rolname = current_user
            """
        ).fetchone()

        assert identity == {
            "current_user": login_role_name,
            "session_user": login_role_name,
            "current_schema": schema_name,
            "rolsuper": False,
            "rolcreatedb": False,
            "rolcreaterole": False,
            "rolreplication": False,
            "rolbypassrls": False,
            "rolinherit": True,
            "can_connect": True,
        }

        group_state = limited.execute(
            """
            SELECT
                rolcanlogin,
                rolsuper,
                rolcreatedb,
                rolcreaterole,
                rolreplication,
                rolbypassrls,
                rolinherit
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
            "rolreplication": False,
            "rolbypassrls": False,
            "rolinherit": False,
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

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            limited.execute(
                sql.SQL("SET ROLE {}").format(
                    sql.Identifier(privilege_role_name)
                )
            )

        assert limited.execute(
            "SELECT 1 AS usable"
        ).fetchone()["usable"] == 1

        expected_columns = {
            "soc_collector_agents": {
                "SELECT": {
                    "agent_id",
                    "display_name",
                    "certificate_sha256",
                    "status",
                    "created_at",
                },
                "INSERT": set(),
                "UPDATE": set(),
                "REFERENCES": set(),
            },
            "soc_event_inbox": {
                "SELECT": {
                    "inbox_id",
                    "agent_id",
                    "event_id",
                    "payload_sha256",
                },
                "INSERT": {
                    "agent_id",
                    "event_id",
                    "payload_json",
                    "payload_sha256",
                    "received_at",
                },
                "UPDATE": set(),
                "REFERENCES": set(),
            },
        }

        for table, expected in expected_columns.items():
            table_reference = f"{schema_name}.{table}"

            rows = limited.execute(
                """
                SELECT
                    a.attname,
                    has_column_privilege(
                        current_user, %s, a.attname, 'SELECT'
                    ) AS can_select,
                    has_column_privilege(
                        current_user, %s, a.attname, 'INSERT'
                    ) AS can_insert,
                    has_column_privilege(
                        current_user, %s, a.attname, 'UPDATE'
                    ) AS can_update,
                    has_column_privilege(
                        current_user, %s, a.attname, 'REFERENCES'
                    ) AS can_reference
                FROM pg_catalog.pg_attribute AS a
                WHERE a.attrelid = %s::regclass
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                ORDER BY a.attnum
                """,
                (
                    table_reference,
                    table_reference,
                    table_reference,
                    table_reference,
                    table_reference,
                ),
            ).fetchall()

            actual = {
                "SELECT": {
                    row["attname"]
                    for row in rows
                    if row["can_select"]
                },
                "INSERT": {
                    row["attname"]
                    for row in rows
                    if row["can_insert"]
                },
                "UPDATE": {
                    row["attname"]
                    for row in rows
                    if row["can_update"]
                },
                "REFERENCES": {
                    row["attname"]
                    for row in rows
                    if row["can_reference"]
                },
            }

            assert actual == expected, (
                f"Unexpected effective column privileges on {table}: "
                f"{actual!r}"
            )

        tables_without_table_level_grants = (
            "schema_migrations",
            "soc_collector_agents",
            "soc_event_inbox",
            "soc_incidents",
            "soc_incident_evidence",
            "soc_incident_history",
        )

        table_privileges = (
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "TRUNCATE",
            "REFERENCES",
            "TRIGGER",
        )

        for table in tables_without_table_level_grants:
            table_reference = f"{schema_name}.{table}"

            for privilege in table_privileges:
                granted = limited.execute(
                    """
                    SELECT has_table_privilege(
                        current_user, %s, %s
                    ) AS granted
                    """,
                    (table_reference, privilege),
                ).fetchone()["granted"]

                assert granted is False, (
                    f"Unexpected table-level {privilege} on {table}"
                )

        schema_privileges = limited.execute(
            """
            SELECT
                has_schema_privilege(
                    current_user, current_schema(), 'USAGE'
                ) AS can_use,
                has_schema_privilege(
                    current_user, current_schema(), 'CREATE'
                ) AS can_create
            """
        ).fetchone()

        assert schema_privileges == {
            "can_use": True,
            "can_create": False,
        }

        sequence_name = connection.execute(
            "SELECT pg_get_serial_sequence(%s, %s) AS name",
            (
                f"{schema_name}.soc_event_inbox",
                "inbox_id",
            ),
        ).fetchone()["name"]

        assert sequence_name is not None

        sequence_privileges = limited.execute(
            """
            SELECT
                has_sequence_privilege(
                    current_user, %s, 'USAGE'
                ) AS can_use,
                has_sequence_privilege(
                    current_user, %s, 'SELECT'
                ) AS can_select,
                has_sequence_privilege(
                    current_user, %s, 'UPDATE'
                ) AS can_update
            """,
            (sequence_name, sequence_name, sequence_name),
        ).fetchone()

        assert sequence_privileges == {
            "can_use": False,
            "can_select": False,
            "can_update": False,
        }

        role_names = [login_role_name, privilege_role_name]

        ownership = limited.execute(
            """
            SELECT
                EXISTS (
                    SELECT 1
                    FROM pg_namespace
                    WHERE nspname = current_schema()
                      AND nspowner = ANY(
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
                      AND c.relowner = ANY(
                          SELECT oid
                          FROM pg_roles
                          WHERE rolname = ANY(%s)
                      )
                ) AS owns_objects
            """,
            (role_names, role_names),
        ).fetchone()

        assert ownership == {
            "owns_schema": False,
            "owns_objects": False,
        }

        store = PostgresCollectorStore(limited)

        registered = store.get_agent_by_fingerprint("A" * 64)
        assert registered is not None
        assert registered["agent_id"] == "linux01"
        assert registered["status"] == "active"

        event_id = f"linux01:limited-collector:{uuid4().hex}"
        payload = _event(event_id, message="limited collector integration")

        first = store.ingest_batch("linux01", [payload])
        replay = store.ingest_batch("linux01", [payload])

        assert first.accepted == 1
        assert first.duplicates == 0
        assert replay.accepted == 0
        assert replay.duplicates == 1
        assert replay.event_ids == (event_id,)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            limited.execute(
                """
                SELECT payload_json
                FROM soc_event_inbox
                WHERE agent_id = %s AND event_id = %s
                """,
                ("linux01", event_id),
            )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            limited.execute(
                """
                DELETE FROM soc_event_inbox
                WHERE agent_id = %s AND event_id = %s
                """,
                ("linux01", event_id),
            )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            limited.execute(
                "TRUNCATE TABLE soc_event_inbox"
            )

        with pytest.raises(
            CollectorStoreError,
            match="Unable to register collector",
        ):
            store.register_agent(
                "linux02",
                "Must not be registered by collector identity",
                "b" * 64,
            )

        with pytest.raises(
            CollectorStoreError,
            match="Unable to revoke collector",
        ):
            store.revoke_agent("linux01")

        assert connection.execute(
            """
            SELECT status
            FROM soc_collector_agents
            WHERE agent_id = %s
            """,
            ("linux01",),
        ).fetchone()["status"] == "active"

        assert connection.execute(
            """
            SELECT count(*) AS total
            FROM soc_event_inbox
            WHERE agent_id = %s AND event_id = %s
            """,
            ("linux01", event_id),
        ).fetchone()["total"] == 1

    finally:
        if limited is not None:
            limited.close()

        if membership_created:
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
