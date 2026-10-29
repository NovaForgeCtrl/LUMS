"""SQLite persistence for auditable SOC incidents."""

from __future__ import annotations

import json
import sqlite3
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

    def __init__(self, connection: sqlite3.Connection):
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError("connection must be a sqlite3.Connection")
        self.connection = connection
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create only the SOC incident tables; never alter alert tables."""
        try:
            self.connection.executescript("""
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
                );

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
                );

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
                );

                CREATE INDEX IF NOT EXISTS idx_soc_incidents_status_updated
                    ON soc_incidents(status, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_soc_incident_evidence_reference
                    ON soc_incident_evidence(kind, reference_id);
            """)
        except sqlite3.Error as exc:
            raise IncidentStoreError("Unable to initialize SOC incident storage") from exc

    @staticmethod
    def _evidence_from_row(row) -> IncidentEvidence:
        return IncidentEvidence(
            evidence_id=row[0],
            kind=row[1],
            reference_id=row[2],
            description=row[3],
            observed_at=row[4],
        )

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

    def save(self, incident: Incident) -> Incident:
        """Insert an incident and its evidence atomically and idempotently.

        An existing incident's status and metadata are never overwritten by a
        replay. New evidence IDs may be appended without duplicating evidence.
        """
        if not isinstance(incident, Incident):
            raise TypeError("incident must be an Incident")

        try:
            self.connection.execute("BEGIN IMMEDIATE")
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

            for evidence in incident.evidence:
                self.connection.execute("""
                    INSERT INTO soc_incident_evidence (
                        evidence_id, incident_id, kind, reference_id,
                        description, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(incident_id, evidence_id) DO NOTHING
                """, (
                    evidence.evidence_id,
                    incident.incident_id,
                    evidence.kind,
                    evidence.reference_id,
                    evidence.description,
                    evidence.observed_at,
                ))

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

            for evidence in incident.evidence:
                self.connection.execute("""
                    INSERT INTO soc_incident_evidence (
                        evidence_id, incident_id, kind, reference_id,
                        description, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(incident_id, evidence_id) DO NOTHING
                """, (
                    evidence.evidence_id, incident.incident_id,
                    evidence.kind, evidence.reference_id,
                    evidence.description, evidence.observed_at,
                ))

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

    def save_many(self, incidents: Iterable[Incident]) -> tuple[Incident, ...]:
        """Save a batch atomically; either every incident is saved or none."""
        items = tuple(incidents)
        if any(not isinstance(item, Incident) for item in items):
            raise TypeError("all items must be Incident instances")

        try:
            self.connection.execute("BEGIN IMMEDIATE")
            stored = self.save_many_in_transaction(items)
            self.connection.commit()
            return stored
        except Exception as exc:
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

        try:
            self.connection.execute("BEGIN IMMEDIATE")
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
