"""Persistent registry and idempotent inbox for independent LUMS collectors."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any


_AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_FINGERPRINT = re.compile(r"^[0-9a-fA-F]{64}$")
_EVENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
MAX_BATCH = 500
MAX_EVENT_BYTES = 64 * 1024


class CollectorStoreError(RuntimeError):
    """Base exception for collector storage failures."""


class CollectorNotFoundError(LookupError):
    """The collector is not registered."""


class CollectorRevokedError(PermissionError):
    """The collector has been revoked."""


class EventIdConflictError(ValueError):
    """An existing event ID was reused with different content."""


@dataclass(frozen=True)
class IngestBatchResult:
    accepted: int
    duplicates: int
    event_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "duplicates": self.duplicates,
            "event_ids": list(self.event_ids),
        }


class CollectorStore:
    """Use the caller-owned SQLite connection; never closes it.

    Registration and revocation are administrative operations. The API must
    derive authenticated_agent_id from verified mTLS identity, never from
    an untrusted request-body field.
    """

    def __init__(self, connection: sqlite3.Connection):
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError("connection must be a sqlite3.Connection")
        self.connection = connection
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        try:
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS soc_collector_agents (
                    agent_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    certificate_sha256 TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL
                        CHECK (status IN ('active', 'revoked')),
                    created_at TEXT NOT NULL,
                    revoked_at TEXT
                );

                CREATE TABLE IF NOT EXISTS soc_event_inbox (
                    inbox_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    processing_status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (processing_status IN
                            ('pending', 'processing', 'processed', 'failed')),
                    processed_at TEXT,
                    last_error TEXT,
                    UNIQUE (agent_id, event_id),
                    FOREIGN KEY (agent_id)
                        REFERENCES soc_collector_agents(agent_id)
                );

                CREATE INDEX IF NOT EXISTS idx_soc_event_inbox_pending
                    ON soc_event_inbox(processing_status, inbox_id);

                CREATE INDEX IF NOT EXISTS idx_soc_event_inbox_agent_received
                    ON soc_event_inbox(agent_id, received_at DESC);
            """)
        except sqlite3.Error as exc:
            raise CollectorStoreError(
                "Unable to initialize collector storage"
            ) from exc

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _validate_agent_id(agent_id: str) -> None:
        if not isinstance(agent_id, str) or not _AGENT_ID.fullmatch(agent_id):
            raise ValueError("Invalid agent_id")

    @staticmethod
    def _validate_fingerprint(fingerprint: str) -> str:
        if (
            not isinstance(fingerprint, str)
            or not _FINGERPRINT.fullmatch(fingerprint)
        ):
            raise ValueError(
                "certificate fingerprint must be a SHA-256 hex digest"
            )
        return fingerprint.lower()

    def register_agent(
        self, agent_id: str, display_name: str, certificate_sha256: str
    ) -> dict[str, str]:
        """Register an agent; call only from trusted administrator code."""
        self._validate_agent_id(agent_id)
        fingerprint = self._validate_fingerprint(certificate_sha256)

        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("display_name must not be empty")
        if len(display_name) > 200:
            raise ValueError("display_name is too long")

        created_at = self._now()
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            self.connection.execute("""
                INSERT INTO soc_collector_agents
                    (agent_id, display_name, certificate_sha256,
                     status, created_at)
                VALUES (?, ?, ?, 'active', ?)
            """, (
                agent_id, display_name.strip(), fingerprint, created_at
            ))
            self.connection.commit()
        except sqlite3.IntegrityError as exc:
            self.connection.rollback()
            raise ValueError(
                "Agent ID or certificate is already registered"
            ) from exc
        except sqlite3.Error as exc:
            self.connection.rollback()
            raise CollectorStoreError("Unable to register collector") from exc

        return {
            "agent_id": agent_id,
            "display_name": display_name.strip(),
            "certificate_sha256": fingerprint,
            "status": "active",
            "created_at": created_at,
        }

    def get_agent_by_fingerprint(
        self, certificate_sha256: str
    ) -> dict[str, str] | None:
        fingerprint = self._validate_fingerprint(certificate_sha256)
        try:
            row = self.connection.execute("""
                SELECT agent_id, display_name, certificate_sha256,
                       status, created_at
                FROM soc_collector_agents
                WHERE certificate_sha256 = ?
            """, (fingerprint,)).fetchone()
        except sqlite3.Error as exc:
            raise CollectorStoreError("Unable to look up collector") from exc

        if row is None:
            return None
        return {
            "agent_id": row[0],
            "display_name": row[1],
            "certificate_sha256": row[2],
            "status": row[3],
            "created_at": row[4],
        }

    def revoke_agent(self, agent_id: str) -> bool:
        self._validate_agent_id(agent_id)
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            cursor = self.connection.execute("""
                UPDATE soc_collector_agents
                SET status = 'revoked', revoked_at = COALESCE(revoked_at, ?)
                WHERE agent_id = ?
            """, (self._now(), agent_id))
            self.connection.commit()
            return cursor.rowcount == 1
        except sqlite3.Error as exc:
            self.connection.rollback()
            raise CollectorStoreError("Unable to revoke collector") from exc

    def ingest_batch(
        self,
        authenticated_agent_id: str,
        payloads: Iterable[Mapping[str, Any]],
    ) -> IngestBatchResult:
        """Persist a batch atomically for an already authenticated agent.

        Same ID and same payload is idempotent. Reusing an ID with different
        content fails the whole batch. This method does not authenticate TLS.
        """
        self._validate_agent_id(authenticated_agent_id)
        if isinstance(payloads, (str, bytes, Mapping)):
            raise ValueError("payloads must be an iterable of event objects")

        try:
            items = list(payloads)
        except (TypeError, RuntimeError) as exc:
            raise ValueError("could not read event batch") from exc

        if len(items) > MAX_BATCH:
            raise ValueError("batch exceeds maximum event count")
        if not items:
            return IngestBatchResult(0, 0, ())

        normalized: list[tuple[str, str, str]] = []
        for payload in items:
            if not isinstance(payload, Mapping):
                raise ValueError("each event must be an object")
            data = dict(payload)
            event_id = data.get("event_id")
            if not isinstance(event_id, str) or not _EVENT_ID.fullmatch(event_id):
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
            except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
                raise ValueError("event is not valid JSON data") from exc

            if len(raw) > MAX_EVENT_BYTES:
                raise ValueError("event exceeds maximum encoded size")
            normalized.append((
                event_id, encoded, hashlib.sha256(raw).hexdigest()
            ))

        if len({item[0] for item in normalized}) != len(normalized):
            raise ValueError("batch contains repeated event IDs")

        accepted = 0
        duplicates = 0
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            agent = self.connection.execute("""
                SELECT status FROM soc_collector_agents WHERE agent_id = ?
            """, (authenticated_agent_id,)).fetchone()

            if agent is None:
                raise CollectorNotFoundError(authenticated_agent_id)
            if agent[0] != "active":
                raise CollectorRevokedError(authenticated_agent_id)

            for event_id, encoded, digest in normalized:
                existing = self.connection.execute("""
                    SELECT payload_sha256 FROM soc_event_inbox
                    WHERE agent_id = ? AND event_id = ?
                """, (authenticated_agent_id, event_id)).fetchone()

                if existing is not None:
                    if existing[0] != digest:
                        raise EventIdConflictError(
                            f"event ID {event_id!r} reused with different content"
                        )
                    duplicates += 1
                    continue

                self.connection.execute("""
                    INSERT INTO soc_event_inbox (
                        agent_id, event_id, payload_json,
                        payload_sha256, received_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    authenticated_agent_id, event_id, encoded,
                    digest, self._now(),
                ))
                accepted += 1

            self.connection.commit()
        except (
            CollectorNotFoundError, CollectorRevokedError, EventIdConflictError
        ):
            self.connection.rollback()
            raise
        except sqlite3.Error as exc:
            self.connection.rollback()
            raise CollectorStoreError(
                "Unable to persist collector events"
            ) from exc

        return IngestBatchResult(
            accepted, duplicates, tuple(item[0] for item in normalized)
        )

    @staticmethod
    def _validate_worker_limits(
        *, limit: int, max_attempts: int, stale_after_seconds: int
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

    def _recover_stale_claims_in_transaction(
        self, *, cutoff: str, max_attempts: int
    ) -> int:
        """Recover expired claims; caller must own the write transaction."""
        self.connection.execute("""
            UPDATE soc_event_inbox
            SET processing_status = CASE
                    WHEN attempts >= ? THEN 'failed'
                    ELSE 'pending'
                END,
                claim_token = NULL,
                claimed_at = NULL,
                last_error = CASE
                    WHEN attempts >= ?
                    THEN COALESCE(
                        last_error,
                        'Worker claim expired; retry limit reached'
                    )
                    ELSE last_error
                END
            WHERE processing_status = 'processing'
              AND claimed_at IS NOT NULL
              AND claimed_at < ?
        """, (max_attempts, max_attempts, cutoff))
        return self.connection.execute(
            "SELECT changes()"
        ).fetchone()[0]

    def recover_stale_claims(
        self, *, stale_after_seconds: int = 300,
        max_attempts: int = 5,
    ) -> int:
        """Release expired claims or fail them after the retry limit."""
        self._validate_worker_limits(
            limit=1,
            max_attempts=max_attempts,
            stale_after_seconds=stale_after_seconds,
        )
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(seconds=stale_after_seconds)
        ).isoformat()
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            recovered = self._recover_stale_claims_in_transaction(
                cutoff=cutoff, max_attempts=max_attempts
            )
            self.connection.commit()
            return recovered
        except sqlite3.Error as exc:
            self.connection.rollback()
            raise CollectorStoreError(
                "Unable to recover stale worker claims"
            ) from exc

    def claim_pending(
        self, *, limit: int = 100, max_attempts: int = 5,
        stale_after_seconds: int = 300,
    ) -> tuple[dict[str, object], ...]:
        """Atomically reserve pending events for one worker.

        Each row gets a unique claim token. Attempts count successful claims.
        The caller must finalize or fail each claim using its returned token.
        """
        self._validate_worker_limits(
            limit=limit,
            max_attempts=max_attempts,
            stale_after_seconds=stale_after_seconds,
        )
        now = datetime.now(timezone.utc).isoformat()
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(seconds=stale_after_seconds)
        ).isoformat()
        claimed: list[dict[str, object]] = []

        try:
            self.connection.execute("BEGIN IMMEDIATE")
            self._recover_stale_claims_in_transaction(
                cutoff=cutoff, max_attempts=max_attempts
            )

            rows = self.connection.execute("""
                SELECT inbox_id, agent_id, event_id, payload_json,
                       received_at, attempts
                FROM soc_event_inbox
                WHERE processing_status = 'pending'
                  AND attempts < ?
                ORDER BY inbox_id
                LIMIT ?
            """, (max_attempts, limit)).fetchall()

            for row in rows:
                inbox_id, agent_id, event_id, payload_json, received_at, attempts = row
                token = uuid.uuid4().hex
                cursor = self.connection.execute("""
                    UPDATE soc_event_inbox
                    SET processing_status = 'processing',
                        claim_token = ?,
                        claimed_at = ?,
                        attempts = attempts + 1,
                        last_error = NULL
                    WHERE inbox_id = ?
                      AND processing_status = 'pending'
                      AND attempts = ?
                """, (token, now, inbox_id, attempts))

                if cursor.rowcount != 1:
                    raise CollectorStoreError(
                        "Inbox row changed during atomic claim"
                    )

                claimed.append({
                    "inbox_id": inbox_id,
                    "agent_id": agent_id,
                    "event_id": event_id,
                    "payload": json.loads(payload_json),
                    "received_at": received_at,
                    "processing_status": "processing",
                    "claim_token": token,
                    "claimed_at": now,
                    "attempts": attempts + 1,
                })

            self.connection.commit()
            return tuple(claimed)
        except Exception as exc:
            self.connection.rollback()
            if isinstance(exc, (ValueError, CollectorStoreError)):
                raise
            raise CollectorStoreError(
                "Unable to claim pending collector events"
            ) from exc

    def finish_claim(self, inbox_id: int, claim_token: str) -> bool:
        """Mark a claimed event processed only if its token is still current."""
        if isinstance(inbox_id, bool) or not isinstance(inbox_id, int) or inbox_id < 1:
            raise ValueError("inbox_id must be a positive integer")
        if not isinstance(claim_token, str) or not claim_token:
            raise ValueError("claim_token must not be empty")

        try:
            self.connection.execute("BEGIN IMMEDIATE")
            cursor = self.connection.execute("""
                UPDATE soc_event_inbox
                SET processing_status = 'processed',
                    processed_at = ?,
                    claim_token = NULL,
                    claimed_at = NULL,
                    last_error = NULL
                WHERE inbox_id = ?
                  AND processing_status = 'processing'
                  AND claim_token = ?
            """, (self._now(), inbox_id, claim_token))
            self.connection.commit()
            return cursor.rowcount == 1
        except sqlite3.Error as exc:
            self.connection.rollback()
            raise CollectorStoreError(
                "Unable to finalize worker claim"
            ) from exc

    def fail_claim(
        self, inbox_id: int, claim_token: str, error: str,
        *, max_attempts: int = 5,
    ) -> bool:
        """Record a failure and either retry later or exhaust the retry limit."""
        if isinstance(inbox_id, bool) or not isinstance(inbox_id, int) or inbox_id < 1:
            raise ValueError("inbox_id must be a positive integer")
        if not isinstance(claim_token, str) or not claim_token:
            raise ValueError("claim_token must not be empty")
        if not isinstance(error, str) or not error.strip():
            raise ValueError("error must not be empty")
        self._validate_worker_limits(
            limit=1, max_attempts=max_attempts, stale_after_seconds=1
        )
        safe_error = error.strip()[:2000]

        try:
            self.connection.execute("BEGIN IMMEDIATE")
            cursor = self.connection.execute("""
                UPDATE soc_event_inbox
                SET processing_status = CASE
                        WHEN attempts >= ? THEN 'failed'
                        ELSE 'pending'
                    END,
                    last_error = ?,
                    claim_token = NULL,
                    claimed_at = NULL
                WHERE inbox_id = ?
                  AND processing_status = 'processing'
                  AND claim_token = ?
            """, (max_attempts, safe_error, inbox_id, claim_token))
            self.connection.commit()
            return cursor.rowcount == 1
        except sqlite3.Error as exc:
            self.connection.rollback()
            raise CollectorStoreError(
                "Unable to record worker failure"
            ) from exc

    def list_pending(self, *, limit: int = 100) -> tuple[dict[str, object], ...]:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 500
        ):
            raise ValueError("limit must be between 1 and 500")

        try:
            rows = self.connection.execute("""
                SELECT inbox_id, agent_id, event_id, payload_json,
                       received_at, processing_status
                FROM soc_event_inbox
                WHERE processing_status = 'pending'
                ORDER BY inbox_id
                LIMIT ?
            """, (limit,)).fetchall()
        except sqlite3.Error as exc:
            raise CollectorStoreError("Unable to list pending events") from exc

        return tuple({
            "inbox_id": row[0],
            "agent_id": row[1],
            "event_id": row[2],
            "payload": json.loads(row[3]),
            "received_at": row[4],
            "processing_status": row[5],
        } for row in rows)
