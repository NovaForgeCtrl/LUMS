"""PostgreSQL persistence for authenticated SOC collectors and event inbox."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg import Connection, Error, IntegrityError
from psycopg.pq import TransactionStatus

from ..db_transactions import require_transaction, transaction
from .collector_store import (
    _EVENT_ID,
    MAX_BATCH,
    MAX_EVENT_BYTES,
    CollectorNotFoundError,
    CollectorRevokedError,
    CollectorStore,
    CollectorStoreError,
    EventIdConflictError,
    IngestBatchResult,
)

_COLLECTOR_LIFECYCLE_LOCK_CLASS = 1_280_131_412
# Independent advisory-lock namespace for collector lifecycle.



def _normalize_payloads(
    payloads: Iterable[Mapping[str, Any]],
) -> tuple[tuple[str, str, str], ...]:
    """Apply the exact canonical JSON and SHA-256 contract of SQLite."""
    if isinstance(payloads, (str, bytes, Mapping)):
        raise ValueError("payloads must be an iterable of event objects")

    try:
        items = list(payloads)
    except (TypeError, RuntimeError) as exc:
        raise ValueError("could not read event batch") from exc

    if len(items) > MAX_BATCH:
        raise ValueError("batch exceeds maximum event count")

    normalized: list[tuple[str, str, str]] = []

    for payload in items:
        if not isinstance(payload, Mapping):
            raise ValueError("each event must be an object")

        data = dict(payload)
        event_id = data.get("event_id")

        if (
            not isinstance(event_id, str)
            or not _EVENT_ID.fullmatch(event_id)
        ):
            raise ValueError("invalid event_id")

        try:
            encoded = json.dumps(
                data,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            raw = encoded.encode("utf-8")
        except (
            TypeError,
            ValueError,
            UnicodeError,
            RecursionError,
        ) as exc:
            raise ValueError("event is not valid JSON data") from exc

        if len(raw) > MAX_EVENT_BYTES:
            raise ValueError("event exceeds maximum encoded size")

        normalized.append((
            event_id,
            encoded,
            hashlib.sha256(raw).hexdigest(),
        ))

    if len({item[0] for item in normalized}) != len(normalized):
        raise ValueError("batch contains repeated event IDs")

    return tuple(normalized)


def _iso_timestamp(value: datetime | str | None) -> str | None:
    """Convert PostgreSQL timestamp values to the existing ISO string API."""
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    if isinstance(value, str):
        return value

    raise TypeError("Unsupported timestamp value")


class PostgresCollectorStore:
    """Use a caller-owned PostgreSQL connection and centrally migrated schema.

    This class never creates tables, closes connections, or changes database
    privileges. Mutating operations manage one explicit top-level transaction.
    Methods ending in ``_in_transaction`` are intentionally absent until a
    caller-owned worker transaction requires them.
    """

    def __init__(self, connection: Connection):
        if not isinstance(connection, Connection):
            raise TypeError("connection must be a psycopg.Connection")

        self.connection = connection

    def _lock_agent_lifecycle(self, agent_id: str) -> None:
        """Serialize registration, revocation and ingestion for one agent."""
        self.connection.execute(
            "SELECT pg_advisory_xact_lock(%s, hashtext(%s))",
            (_COLLECTOR_LIFECYCLE_LOCK_CLASS, agent_id),
        )

    def _ensure_transaction_available(self) -> None:
        if self.connection.closed:
            raise CollectorStoreError("Database connection is closed")

        if self.connection.autocommit is not True:
            raise CollectorStoreError(
                "PostgreSQL collector operations require autocommit=True"
            )

        if (
            self.connection.info.transaction_status
            != TransactionStatus.IDLE
        ):
            raise CollectorStoreError(
                "Collector operation cannot run inside an existing transaction"
            )

    @staticmethod
    def _validate_worker_limits(
        *,
        limit: int,
        max_attempts: int,
        stale_after_seconds: int,
    ) -> None:
        for name, value, minimum, maximum in (
            ("limit", limit, 1, 500),
            ("max_attempts", max_attempts, 1, 100),
            ("stale_after_seconds", stale_after_seconds, 1, 86400),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                raise ValueError(
                    f"{name} must be between {minimum} and {maximum}"
                )

    @staticmethod
    def _agent_dict(row) -> dict[str, str]:
        return {
            "agent_id": row["agent_id"],
            "display_name": row["display_name"],
            "certificate_sha256": row["certificate_sha256"],
            "status": row["status"],
            "created_at": _iso_timestamp(row["created_at"]),
        }

    def register_agent(
        self,
        agent_id: str,
        display_name: str,
        certificate_sha256: str,
    ) -> dict[str, str]:
        """Register an agent; callers must enforce administrator authorization."""
        CollectorStore._validate_agent_id(agent_id)
        fingerprint = CollectorStore._validate_fingerprint(
            certificate_sha256
        )

        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("display_name must not be empty")

        if len(display_name) > 200:
            raise ValueError("display_name is too long")

        created_at = datetime.now(timezone.utc)
        self._ensure_transaction_available()

        try:
            with transaction(self.connection):
                self._lock_agent_lifecycle(agent_id)
                self.connection.execute(
                    """
                    INSERT INTO soc_collector_agents (
                        agent_id,
                        display_name,
                        certificate_sha256,
                        status,
                        created_at
                    )
                    VALUES (%s, %s, %s, 'active', %s)
                    """,
                    (
                        agent_id,
                        display_name.strip(),
                        fingerprint,
                        created_at,
                    ),
                )
        except IntegrityError as exc:
            raise ValueError(
                "Agent ID or certificate is already registered"
            ) from exc
        except Error as exc:
            raise CollectorStoreError(
                "Unable to register collector"
            ) from exc

        return {
            "agent_id": agent_id,
            "display_name": display_name.strip(),
            "certificate_sha256": fingerprint,
            "status": "active",
            "created_at": created_at.isoformat(),
        }

    def get_agent_by_fingerprint(
        self,
        certificate_sha256: str,
    ) -> dict[str, str] | None:
        fingerprint = CollectorStore._validate_fingerprint(
            certificate_sha256
        )

        try:
            row = self.connection.execute(
                """
                SELECT
                    agent_id,
                    display_name,
                    certificate_sha256,
                    status,
                    created_at
                FROM soc_collector_agents
                WHERE certificate_sha256 = %s
                """,
                (fingerprint,),
            ).fetchone()
        except Error as exc:
            raise CollectorStoreError(
                "Unable to look up collector"
            ) from exc

        if row is None:
            return None

        return self._agent_dict(row)

    def revoke_agent(self, agent_id: str) -> bool:
        CollectorStore._validate_agent_id(agent_id)
        self._ensure_transaction_available()

        try:
            with transaction(self.connection):
                self._lock_agent_lifecycle(agent_id)
                row = self.connection.execute(
                    """
                    UPDATE soc_collector_agents
                    SET
                        status = 'revoked',
                        revoked_at = COALESCE(
                            revoked_at,
                            CURRENT_TIMESTAMP
                        )
                    WHERE agent_id = %s
                    RETURNING agent_id
                    """,
                    (agent_id,),
                ).fetchone()
        except Error as exc:
            raise CollectorStoreError(
                "Unable to revoke collector"
            ) from exc

        return row is not None

    def ingest_batch(
        self,
        authenticated_agent_id: str,
        payloads: Iterable[Mapping[str, Any]],
    ) -> IngestBatchResult:
        """Persist one atomic batch for an agent authenticated by trusted mTLS.

        Identical event ID and payload replays are idempotent. Reusing an
        event ID with different content aborts and rolls back the whole batch.
        This method does not authenticate TLS itself.
        """
        CollectorStore._validate_agent_id(authenticated_agent_id)
        normalized = _normalize_payloads(payloads)

        if not normalized:
            return IngestBatchResult(0, 0, ())

        self._ensure_transaction_available()

        accepted = 0
        duplicates = 0

        try:
            with transaction(self.connection):
                # Serialize with registration and revocation. This avoids
                # requiring UPDATE privilege on soc_collector_agents.
                self._lock_agent_lifecycle(authenticated_agent_id)
                agent = self.connection.execute(
                    """
                    SELECT status
                    FROM soc_collector_agents
                    WHERE agent_id = %s
                    """,
                    (authenticated_agent_id,),
                ).fetchone()

                if agent is None:
                    raise CollectorNotFoundError(
                        authenticated_agent_id
                    )

                if agent["status"] != "active":
                    raise CollectorRevokedError(
                        authenticated_agent_id
                    )

                for event_id, encoded, digest in normalized:
                    inserted = self.connection.execute(
                        """
                        INSERT INTO soc_event_inbox (
                            agent_id,
                            event_id,
                            payload_json,
                            payload_sha256,
                            received_at
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (agent_id, event_id) DO NOTHING
                        RETURNING inbox_id
                        """,
                        (
                            authenticated_agent_id,
                            event_id,
                            encoded,
                            digest,
                            datetime.now(timezone.utc),
                        ),
                    ).fetchone()

                    if inserted is not None:
                        accepted += 1
                        continue

                    existing = self.connection.execute(
                        """
                        SELECT payload_sha256
                        FROM soc_event_inbox
                        WHERE agent_id = %s AND event_id = %s
                        """,
                        (authenticated_agent_id, event_id),
                    ).fetchone()

                    if existing is None:
                        raise CollectorStoreError(
                            "Event insert conflicted but the existing row is missing"
                        )

                    if existing["payload_sha256"] != digest:
                        raise EventIdConflictError(
                            f"event ID {event_id!r} reused with different content"
                        )

                    duplicates += 1

        except (
            CollectorNotFoundError,
            CollectorRevokedError,
            EventIdConflictError,
            CollectorStoreError,
        ):
            raise
        except Error as exc:
            raise CollectorStoreError(
                "Unable to persist collector events"
            ) from exc

        return IngestBatchResult(
            accepted,
            duplicates,
            tuple(item[0] for item in normalized),
        )

    def _recover_stale_claims_in_transaction(
        self,
        *,
        cutoff: datetime,
        max_attempts: int,
    ) -> int:
        """Recover expired claims inside the caller's active transaction."""
        require_transaction(self.connection)

        cursor = self.connection.execute(
            """
            UPDATE soc_event_inbox
            SET
                processing_status = CASE
                    WHEN attempts >= %s THEN 'failed'
                    ELSE 'pending'
                END,
                claim_token = NULL,
                claimed_at = NULL,
                last_error = CASE
                    WHEN attempts >= %s
                    THEN COALESCE(
                        last_error,
                        'Worker claim expired; retry limit reached'
                    )
                    ELSE last_error
                END
            WHERE processing_status = 'processing'
              AND claimed_at IS NOT NULL
              AND claimed_at < %s
            """,
            (max_attempts, max_attempts, cutoff),
        )

        return cursor.rowcount

    def recover_stale_claims(
        self,
        *,
        stale_after_seconds: int = 300,
        max_attempts: int = 5,
    ) -> int:
        """Release expired claims or fail them after the retry limit."""
        self._validate_worker_limits(
            limit=1,
            max_attempts=max_attempts,
            stale_after_seconds=stale_after_seconds,
        )
        self._ensure_transaction_available()

        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(seconds=stale_after_seconds)
        )

        try:
            with transaction(self.connection):
                return self._recover_stale_claims_in_transaction(
                    cutoff=cutoff,
                    max_attempts=max_attempts,
                )
        except Error as exc:
            raise CollectorStoreError(
                "Unable to recover stale worker claims"
            ) from exc

    @staticmethod
    def _decode_claims(
        claimed_rows: list[tuple[dict[str, object], str]],
    ) -> tuple[dict[str, object], ...]:
        claimed: list[dict[str, object]] = []

        for claim, payload_json in claimed_rows:
            try:
                claim["payload"] = json.loads(payload_json)
                claim["payload_error"] = None
            except (ValueError, TypeError, RecursionError) as exc:
                claim["payload"] = None
                claim["payload_error"] = (
                    f"Invalid JSON payload: {type(exc).__name__}"
                )

            claimed.append(claim)

        return tuple(claimed)

    def _claim_pending(
        self,
        *,
        limit: int,
        max_attempts: int,
        stale_after_seconds: int,
        recover_stale: bool,
        after_inbox_id: int | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Atomically reserve pending rows using PostgreSQL row locks.

        SKIP LOCKED allows independent workers to claim different rows without
        waiting for rows already reserved by another worker.
        """
        self._validate_worker_limits(
            limit=limit,
            max_attempts=max_attempts,
            stale_after_seconds=stale_after_seconds,
        )

        if not isinstance(recover_stale, bool):
            raise TypeError("recover_stale must be a bool")

        if (
            after_inbox_id is not None
            and (
                isinstance(after_inbox_id, bool)
                or not isinstance(after_inbox_id, int)
                or after_inbox_id < 1
            )
        ):
            raise ValueError("after_inbox_id must be a positive integer")

        self._ensure_transaction_available()

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=stale_after_seconds)
        claimed_rows: list[tuple[dict[str, object], str]] = []

        try:
            with transaction(self.connection):
                if recover_stale:
                    self._recover_stale_claims_in_transaction(
                        cutoff=cutoff,
                        max_attempts=max_attempts,
                    )

                rows = self.connection.execute(
                    """
                    SELECT
                        inbox_id,
                        agent_id,
                        event_id,
                        payload_json,
                        received_at,
                        attempts
                    FROM soc_event_inbox
                    WHERE processing_status = 'pending'
                      AND attempts < %s
                      AND (
                          %s::BIGINT IS NULL
                          OR inbox_id > %s::BIGINT
                      )
                    ORDER BY inbox_id
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (
                        max_attempts,
                        after_inbox_id,
                        after_inbox_id,
                        limit,
                    ),
                ).fetchall()

                for row in rows:
                    token = uuid.uuid4().hex

                    updated = self.connection.execute(
                        """
                        UPDATE soc_event_inbox
                        SET
                            processing_status = 'processing',
                            claim_token = %s,
                            claimed_at = %s,
                            attempts = attempts + 1,
                            last_error = NULL
                        WHERE inbox_id = %s
                          AND processing_status = 'pending'
                          AND attempts = %s
                        RETURNING attempts
                        """,
                        (
                            token,
                            now,
                            row["inbox_id"],
                            row["attempts"],
                        ),
                    ).fetchone()

                    if updated is None:
                        raise CollectorStoreError(
                            "Inbox row changed during atomic claim"
                        )

                    claimed_rows.append(({
                        "inbox_id": row["inbox_id"],
                        "agent_id": row["agent_id"],
                        "event_id": row["event_id"],
                        "received_at": _iso_timestamp(row["received_at"]),
                        "processing_status": "processing",
                        "claim_token": token,
                        "claimed_at": now.isoformat(),
                        "attempts": updated["attempts"],
                    }, row["payload_json"]))

        except (ValueError, CollectorStoreError, TypeError):
            raise
        except Error as exc:
            raise CollectorStoreError(
                "Unable to claim pending collector events"
            ) from exc

        return self._decode_claims(claimed_rows)

    def claim_pending(
        self,
        *,
        limit: int = 100,
        max_attempts: int = 5,
        stale_after_seconds: int = 300,
    ) -> tuple[dict[str, object], ...]:
        """Claim a batch and recover stale claims first."""
        return self._claim_pending(
            limit=limit,
            max_attempts=max_attempts,
            stale_after_seconds=stale_after_seconds,
            recover_stale=True,
        )

    def claim_next_pending(
        self,
        *,
        max_attempts: int = 5,
        stale_after_seconds: int = 300,
        recover_stale: bool = False,
        after_inbox_id: int | None = None,
    ) -> dict[str, object] | None:
        """Claim one event; stale recovery is optional in this transaction."""
        if not isinstance(recover_stale, bool):
            raise TypeError("recover_stale must be a bool")

        claims = self._claim_pending(
            limit=1,
            max_attempts=max_attempts,
            stale_after_seconds=stale_after_seconds,
            recover_stale=recover_stale,
            after_inbox_id=after_inbox_id,
        )

        return claims[0] if claims else None

    def finish_claim(
        self,
        inbox_id: int,
        claim_token: str,
    ) -> bool:
        """Finalize an event only if the supplied token is still current."""
        if (
            isinstance(inbox_id, bool)
            or not isinstance(inbox_id, int)
            or inbox_id < 1
        ):
            raise ValueError("inbox_id must be a positive integer")

        if not isinstance(claim_token, str) or not claim_token:
            raise ValueError("claim_token must not be empty")

        self._ensure_transaction_available()

        try:
            with transaction(self.connection):
                row = self.connection.execute(
                    """
                    UPDATE soc_event_inbox
                    SET
                        processing_status = 'processed',
                        processed_at = %s,
                        claim_token = NULL,
                        claimed_at = NULL,
                        last_error = NULL
                    WHERE inbox_id = %s
                      AND processing_status = 'processing'
                      AND claim_token = %s
                    RETURNING inbox_id
                    """,
                    (
                        datetime.now(timezone.utc),
                        inbox_id,
                        claim_token,
                    ),
                ).fetchone()
        except Error as exc:
            raise CollectorStoreError(
                "Unable to finalize worker claim"
            ) from exc

        return row is not None

    def fail_claim(
        self,
        inbox_id: int,
        claim_token: str,
        error: str,
        *,
        max_attempts: int = 5,
    ) -> bool:
        """Record a failure and requeue or exhaust the retry limit."""
        if (
            isinstance(inbox_id, bool)
            or not isinstance(inbox_id, int)
            or inbox_id < 1
        ):
            raise ValueError("inbox_id must be a positive integer")

        if not isinstance(claim_token, str) or not claim_token:
            raise ValueError("claim_token must not be empty")

        if not isinstance(error, str) or not error.strip():
            raise ValueError("error must not be empty")

        self._validate_worker_limits(
            limit=1,
            max_attempts=max_attempts,
            stale_after_seconds=1,
        )

        safe_error = error.strip()[:2000]
        self._ensure_transaction_available()

        try:
            with transaction(self.connection):
                row = self.connection.execute(
                    """
                    UPDATE soc_event_inbox
                    SET
                        processing_status = CASE
                            WHEN attempts >= %s THEN 'failed'
                            ELSE 'pending'
                        END,
                        last_error = %s,
                        claim_token = NULL,
                        claimed_at = NULL
                    WHERE inbox_id = %s
                      AND processing_status = 'processing'
                      AND claim_token = %s
                    RETURNING inbox_id
                    """,
                    (
                        max_attempts,
                        safe_error,
                        inbox_id,
                        claim_token,
                    ),
                ).fetchone()
        except Error as exc:
            raise CollectorStoreError(
                "Unable to record worker failure"
            ) from exc

        return row is not None

    def list_pending(
        self,
        *,
        limit: int = 100,
    ) -> tuple[dict[str, object], ...]:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 500
        ):
            raise ValueError("limit must be between 1 and 500")

        try:
            rows = self.connection.execute(
                """
                SELECT
                    inbox_id,
                    agent_id,
                    event_id,
                    payload_json,
                    received_at,
                    processing_status
                FROM soc_event_inbox
                WHERE processing_status = 'pending'
                ORDER BY inbox_id
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        except Error as exc:
            raise CollectorStoreError(
                "Unable to list pending events"
            ) from exc

        return tuple({
            "inbox_id": row["inbox_id"],
            "agent_id": row["agent_id"],
            "event_id": row["event_id"],
            "payload": json.loads(row["payload_json"]),
            "received_at": _iso_timestamp(row["received_at"]),
            "processing_status": row["processing_status"],
        } for row in rows)


__all__ = [
    "PostgresCollectorStore",
    "_normalize_payloads",
]
