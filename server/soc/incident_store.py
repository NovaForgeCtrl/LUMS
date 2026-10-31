"""SQLite persistence for auditable SOC incidents."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from .incidents import Incident, IncidentEvidence, utc_now_iso


class IncidentStoreError(RuntimeError):
    """Raised when persisted SOC incident data cannot be used safely."""


class IncidentNotFoundError(LookupError):
    """Raised when a requested incident does not exist."""


class IncidentStore:
    """Persist incident snapshots using an existing request-local connection.

    The caller owns the SQLite connection and its lifecycle. This store never
    closes it and does not create a separate database.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        initialize_schema: bool = True,
    ):
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError("connection must be a sqlite3.Connection")
        if not isinstance(initialize_schema, bool):
            raise TypeError("initialize_schema must be a bool")
        self.connection = connection
        if initialize_schema:
            self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create incident tables and indexes atomically when self-owned."""
        owns_transaction = not self.connection.in_transaction

        try:
            if owns_transaction:
                self.connection.execute("BEGIN IMMEDIATE")

            statements = (
                """
                CREATE TABLE IF NOT EXISTS soc_incidents (
                    incident_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    severity TEXT NOT NULL
                        CHECK (severity IN ('info', 'warning', 'critical')),
                    status TEXT NOT NULL
                        CHECK (status IN ('open', 'investigating', 'resolved')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS soc_incident_evidence (
                    evidence_id TEXT NOT NULL,
                    incident_id TEXT NOT NULL,
                    kind TEXT NOT NULL
                        CHECK (kind IN ('event', 'detection', 'correlation')),
                    reference_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY (incident_id, evidence_id),
                    FOREIGN KEY (incident_id)
                        REFERENCES soc_incidents(incident_id)
                        ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS soc_incident_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    old_status TEXT,
                    new_status TEXT NOT NULL
                        CHECK (new_status IN ('open', 'investigating', 'resolved')),
                    changed_at TEXT NOT NULL,
                    changed_by TEXT NOT NULL,
                    FOREIGN KEY (incident_id)
                        REFERENCES soc_incidents(incident_id)
                        ON DELETE CASCADE
                )
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_soc_incidents_status_updated
                    ON soc_incidents(status, updated_at DESC)
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_soc_incident_evidence_reference
                    ON soc_incident_evidence(kind, reference_id)
                """,
            )

            for statement in statements:
                self.connection.execute(statement)

            if owns_transaction:
                self.connection.commit()

        except sqlite3.Error as exc:
            if owns_transaction and self.connection.in_transaction:
                self.connection.rollback()
            raise IncidentStoreError(
                "Unable to initialize SOC incident storage"
            ) from exc

    def _ensure_transaction_available(self) -> None:
        """Refuse to manage a transaction owned by another caller."""
        if self.connection.in_transaction:
            raise IncidentStoreError(
                "Incident operation cannot run inside an existing transaction"
            )

    @staticmethod
    def _evidence_from_row(row) -> IncidentEvidence:
        return IncidentEvidence(
            evidence_id=row[0],
            kind=row[1],
            reference_id=row[2],
            description=row[3],
            observed_at=row[4],
        )

    def _insert_evidence(
        self,
        incident_id: str,
        evidence: IncidentEvidence,
    ) -> bool:
        """Insert evidence or accept an exact replay.

        Reusing an evidence ID with different content is an integrity error.
        The caller remains responsible for transaction management.
        """
        cursor = self.connection.execute("""
            INSERT INTO soc_incident_evidence (
                evidence_id, incident_id, kind, reference_id,
                description, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(incident_id, evidence_id) DO NOTHING
        """, (
            evidence.evidence_id,
            incident_id,
            evidence.kind,
            evidence.reference_id,
            evidence.description,
            evidence.observed_at,
        ))

        if cursor.rowcount == 1:
            return True

        existing = self.connection.execute("""
            SELECT kind, reference_id, description, observed_at
            FROM soc_incident_evidence
            WHERE incident_id = ? AND evidence_id = ?
        """, (incident_id, evidence.evidence_id)).fetchone()

        expected = (
            evidence.kind,
            evidence.reference_id,
            evidence.description,
            evidence.observed_at,
        )

        if existing is None:
            raise IncidentStoreError(
                "Evidence insert conflicted but the existing row is missing"
            )

        if tuple(existing) != expected:
            raise IncidentStoreError(
                "Evidence ID already exists with different content"
            )

        return False

    def _get_unchecked(self, incident_id: str) -> Incident | None:
        row = self.connection.execute("""
            SELECT incident_id, title, summary, severity, status,
                   created_at, updated_at
            FROM soc_incidents
            WHERE incident_id = ?
        """, (incident_id,)).fetchone()

        if row is None:
            return None

        evidence_rows = self.connection.execute("""
            SELECT evidence_id, kind, reference_id, description, observed_at
            FROM soc_incident_evidence
            WHERE incident_id = ?
            ORDER BY rowid
        """, (incident_id,)).fetchall()

        try:
            evidence = tuple(self._evidence_from_row(item) for item in evidence_rows)
            return Incident(
                incident_id=row[0],
                title=row[1],
                summary=row[2],
                severity=row[3],
                status=row[4],
                created_at=row[5],
                updated_at=row[6],
                evidence=evidence,
            )
        except (TypeError, ValueError) as exc:
            raise IncidentStoreError(
                f"Persisted incident {incident_id!r} failed validation"
            ) from exc

    def get(self, incident_id: str) -> Incident | None:
        """Return one incident with its evidence, or None if absent."""
        return self._get_unchecked(incident_id)

    def _validate_incident_identity(self, incident: Incident) -> None:
        """Reject reuse of an incident ID with different immutable content.

        Mutable operator-managed fields such as status and updated_at are
        deliberately excluded from this comparison.
        """
        row = self.connection.execute(
            """
            SELECT title, summary, severity, created_at
            FROM soc_incidents
            WHERE incident_id = ?
            """,
            (incident.incident_id,),
        ).fetchone()

        if row is None:
            raise IncidentStoreError(
                "Incident disappeared during identity validation"
            )

        expected = (
            incident.title,
            incident.summary,
            incident.severity,
            incident.created_at,
        )

        if tuple(row) != expected:
            raise IncidentStoreError(
                "Incident ID already exists with different content "
                "in immutable fields"
            )

    def save(self, incident: Incident) -> Incident:
        """Insert an incident and its evidence atomically and idempotently.

        An existing incident's status and metadata are never overwritten by a
        replay. Exact evidence replays are ignored; conflicting reuse of an
        evidence ID raises IncidentStoreError.
        """
        if not isinstance(incident, Incident):
            raise TypeError("incident must be an Incident")

        self._ensure_transaction_available()
        transaction_started = False
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            self.connection.execute("""
                INSERT INTO soc_incidents (
                    incident_id, title, summary, severity, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO NOTHING
            """, (
                incident.incident_id,
                incident.title,
                incident.summary,
                incident.severity,
                incident.status,
                incident.created_at,
                incident.updated_at,
            ))

            self._validate_incident_identity(incident)

            for evidence in incident.evidence:
                self._insert_evidence(incident.incident_id, evidence)

            self.connection.execute("""
                INSERT INTO soc_incident_history (
                    incident_id, old_status, new_status, changed_at, changed_by
                )
                SELECT incident_id, NULL, status, created_at, 'system'
                FROM soc_incidents
                WHERE incident_id = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM soc_incident_history
                      WHERE incident_id = soc_incidents.incident_id
                  )
            """, (incident.incident_id,))

            stored = self._get_unchecked(incident.incident_id)
            if stored is None:
                raise IncidentStoreError("Incident disappeared during save")
            self.connection.commit()
            return stored
        except Exception as exc:
            if transaction_started and self.connection.in_transaction:
                self.connection.rollback()
            if isinstance(exc, (TypeError, ValueError, IncidentStoreError)):
                raise
            raise IncidentStoreError("Unable to save SOC incident") from exc

    def save_many_in_transaction(
        self, incidents: Iterable[Incident]
    ) -> tuple[Incident, ...]:
        """Persist incidents without opening, committing, or rolling back.

        The caller must already own the transaction. This method deliberately
        leaves transaction management to the caller so incident data can be
        committed atomically with the corresponding inbox status.
        """
        items = tuple(incidents)
        if any(not isinstance(item, Incident) for item in items):
            raise TypeError("all items must be Incident instances")

        if not self.connection.in_transaction:
            raise IncidentStoreError(
                "save_many_in_transaction requires an active transaction"
            )

        for incident in items:
            self.connection.execute("""
                INSERT INTO soc_incidents (
                    incident_id, title, summary, severity, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO NOTHING
            """, (
                incident.incident_id, incident.title, incident.summary,
                incident.severity, incident.status,
                incident.created_at, incident.updated_at,
            ))

            self._validate_incident_identity(incident)

            for evidence in incident.evidence:
                self._insert_evidence(incident.incident_id, evidence)

            self.connection.execute("""
                INSERT INTO soc_incident_history (
                    incident_id, old_status, new_status, changed_at, changed_by
                )
                SELECT incident_id, NULL, status, created_at, 'system'
                FROM soc_incidents
                WHERE incident_id = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM soc_incident_history
                      WHERE incident_id = soc_incidents.incident_id
                  )
            """, (incident.incident_id,))

        stored = tuple(
            self._get_unchecked(item.incident_id) for item in items
        )
        if any(item is None for item in stored):
            raise IncidentStoreError(
                "An incident disappeared during batch save"
            )
        return stored

    def append_evidence_in_transaction(
        self,
        incident_id: str,
        evidence: Iterable[IncidentEvidence],
        *,
        updated_at: str | None = None,
    ) -> Incident:
        """Append evidence without managing the caller's transaction.

        Exact replays of existing evidence IDs are ignored. Reusing an
        evidence ID with different content raises IncidentStoreError.
        The incident's updated_at value changes only when at least one new
        evidence item was inserted. Incident status and status history are
        never modified.
        """
        if not isinstance(incident_id, str) or not incident_id.strip():
            raise ValueError("incident_id must not be empty")

        items = tuple(evidence)
        if any(not isinstance(item, IncidentEvidence) for item in items):
            raise TypeError("all evidence items must be IncidentEvidence instances")

        if not self.connection.in_transaction:
            raise IncidentStoreError(
                "append_evidence_in_transaction requires an active transaction"
            )

        timestamp = updated_at if updated_at is not None else utc_now_iso()

        if not isinstance(timestamp, str) or not timestamp:
            raise ValueError(
                "updated_at must be a timezone-aware ISO timestamp"
            )

        try:
            parsed_timestamp = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )
            if (
                parsed_timestamp.tzinfo is None
                or parsed_timestamp.utcoffset() is None
            ):
                raise ValueError("updated_at must be timezone-aware")
            timestamp_utc = parsed_timestamp.astimezone(timezone.utc)

            row = self.connection.execute(
                "SELECT updated_at FROM soc_incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
            if row is None:
                raise IncidentNotFoundError(incident_id)

            if not isinstance(row[0], str) or not row[0]:
                raise IncidentStoreError(
                    "Persisted incident updated_at is invalid"
                )

            existing_timestamp = datetime.fromisoformat(
                row[0].replace("Z", "+00:00")
            )
            if (
                existing_timestamp.tzinfo is None
                or existing_timestamp.utcoffset() is None
            ):
                raise IncidentStoreError(
                    "Persisted incident updated_at is not timezone-aware"
                )
            existing_timestamp_utc = existing_timestamp.astimezone(timezone.utc)

            if timestamp_utc < existing_timestamp_utc:
                timestamp = row[0]
            else:
                timestamp = timestamp_utc.isoformat()

            inserted = 0
            for item in items:
                inserted += self._insert_evidence(incident_id, item)

            if inserted:
                cursor = self.connection.execute("""
                    UPDATE soc_incidents
                    SET updated_at = ?
                    WHERE incident_id = ?
                """, (timestamp, incident_id))
                if cursor.rowcount != 1:
                    raise IncidentStoreError(
                        "Incident disappeared while appending evidence"
                    )

            stored = self._get_unchecked(incident_id)
            if stored is None:
                raise IncidentStoreError(
                    "Incident disappeared while appending evidence"
                )
            return stored
        except (ValueError, TypeError, IncidentNotFoundError, IncidentStoreError):
            raise
        except sqlite3.Error as exc:
            raise IncidentStoreError(
                "Unable to append SOC incident evidence"
            ) from exc

    def save_many(self, incidents: Iterable[Incident]) -> tuple[Incident, ...]:
        """Save a batch atomically; either every incident is saved or none."""
        items = tuple(incidents)
        if any(not isinstance(item, Incident) for item in items):
            raise TypeError("all items must be Incident instances")

        self._ensure_transaction_available()
        transaction_started = False
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            stored = self.save_many_in_transaction(items)
            self.connection.commit()
            return stored
        except Exception as exc:
            if transaction_started and self.connection.in_transaction:
                self.connection.rollback()
            if isinstance(exc, (TypeError, ValueError, IncidentStoreError)):
                raise
            raise IncidentStoreError("Unable to save SOC incident batch") from exc

    def list_incidents(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[Incident, ...]:
        """List incidents newest-updated first with bounded pagination."""
        if status is not None and status not in {
            "open", "investigating", "resolved"
        }:
            raise ValueError("unsupported incident status")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")

        try:
            if status is None:
                rows = self.connection.execute("""
                    SELECT incident_id FROM soc_incidents
                    ORDER BY updated_at DESC, incident_id
                    LIMIT ? OFFSET ?
                """, (limit, offset)).fetchall()
            else:
                rows = self.connection.execute("""
                    SELECT incident_id FROM soc_incidents
                    WHERE status = ?
                    ORDER BY updated_at DESC, incident_id
                    LIMIT ? OFFSET ?
                """, (status, limit, offset)).fetchall()

            incidents = tuple(
                self._get_unchecked(row[0]) for row in rows
            )
            if any(item is None for item in incidents):
                raise IncidentStoreError("Incident disappeared during listing")
            return incidents
        except sqlite3.Error as exc:
            raise IncidentStoreError("Unable to list SOC incidents") from exc

    def transition(
        self,
        incident_id: str,
        new_status: str,
        *,
        changed_by: str,
        updated_at: str | None = None,
    ) -> Incident:
        """Apply a domain-validated status transition and record its actor."""
        if not isinstance(changed_by, str) or not changed_by.strip():
            raise ValueError("changed_by must not be empty")
        timestamp = updated_at or utc_now_iso()

        self._ensure_transaction_available()
        transaction_started = False
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            current = self._get_unchecked(incident_id)
            if current is None:
                raise IncidentNotFoundError(incident_id)

            changed = current.transition(new_status, updated_at=timestamp)
            if changed is current:
                self.connection.commit()
                return current

            cursor = self.connection.execute("""
                UPDATE soc_incidents
                SET status = ?, updated_at = ?
                WHERE incident_id = ? AND status = ?
            """, (
                changed.status, changed.updated_at,
                incident_id, current.status,
            ))
            if cursor.rowcount != 1:
                raise IncidentStoreError("Incident status changed concurrently")

            self.connection.execute("""
                INSERT INTO soc_incident_history (
                    incident_id, old_status, new_status, changed_at, changed_by
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                incident_id, current.status, changed.status,
                changed.updated_at, changed_by.strip(),
            ))

            stored = self._get_unchecked(incident_id)
            if stored is None:
                raise IncidentStoreError("Incident disappeared during transition")
            self.connection.commit()
            return stored
        except Exception as exc:
            if transaction_started and self.connection.in_transaction:
                self.connection.rollback()
            if isinstance(
                exc,
                (ValueError, IncidentNotFoundError, IncidentStoreError),
            ):
                raise
            raise IncidentStoreError("Unable to transition SOC incident") from exc

    def history(self, incident_id: str) -> tuple[dict[str, object], ...]:
        """Return the immutable status history for one incident."""
        try:
            if self.connection.execute(
                "SELECT 1 FROM soc_incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone() is None:
                raise IncidentNotFoundError(incident_id)

            rows = self.connection.execute("""
                SELECT old_status, new_status, changed_at, changed_by
                FROM soc_incident_history
                WHERE incident_id = ?
                ORDER BY history_id
            """, (incident_id,)).fetchall()
            return tuple({
                "old_status": row[0],
                "new_status": row[1],
                "changed_at": row[2],
                "changed_by": row[3],
            } for row in rows)
        except IncidentNotFoundError:
            raise
        except sqlite3.Error as exc:
            raise IncidentStoreError("Unable to read SOC incident history") from exc
