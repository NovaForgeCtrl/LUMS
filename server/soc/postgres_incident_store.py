"""PostgreSQL persistence for auditable SOC incidents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from psycopg import Connection, Error

from ..db_transactions import require_transaction, transaction
from ..db_errors import DatabaseTransactionStateError
from .incidents import Incident, IncidentEvidence, utc_now_iso
from .incident_store import (
    IncidentNotFoundError,
    IncidentStoreError,
)


def _timestamp_to_datetime(value: str, field_name: str) -> datetime:
    """Validate an ISO timestamp and normalize its instant to UTC."""
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"{field_name} must be a timezone-aware ISO timestamp"
        )

    normalized = (
        value[:-1] + "+00:00" if value.endswith("Z") else value
    )

    try:
        parsed = datetime.fromisoformat(normalized)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"{field_name} must be a timezone-aware ISO timestamp"
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(
            f"{field_name} must be a timezone-aware ISO timestamp"
        )

    return parsed.astimezone(timezone.utc)


def _timestamp_from_database(value: datetime, field_name: str) -> str:
    """Return a canonical UTC ISO timestamp from PostgreSQL TIMESTAMPTZ."""
    if not isinstance(value, datetime):
        raise IncidentStoreError(
            f"Persisted {field_name} is not a datetime"
        )

    if value.tzinfo is None or value.utcoffset() is None:
        raise IncidentStoreError(
            f"Persisted {field_name} is not timezone-aware"
        )

    return value.astimezone(timezone.utc).isoformat()


def _evidence_from_row(row) -> IncidentEvidence:
    return IncidentEvidence(
        evidence_id=row["evidence_id"],
        kind=row["kind"],
        reference_id=row["reference_id"],
        description=row["description"],
        observed_at=_timestamp_from_database(
            row["observed_at"],
            "evidence observed_at",
        ),
    )


class PostgresIncidentStore:
    """Use a caller-owned PostgreSQL connection and migrated SOC tables.

    The store never creates tables or closes the connection. Normal mutating
    methods own an explicit top-level transaction. Methods ending in
    ``_in_transaction`` require a caller-owned transaction and never manage
    its lifecycle.
    """

    def __init__(self, connection: Connection):
        if not isinstance(connection, Connection):
            raise TypeError("connection must be a psycopg.Connection")

        self.connection = connection

    def _require_caller_transaction(self) -> None:
        """Preserve the IncidentStore domain exception contract."""
        try:
            require_transaction(self.connection)
        except DatabaseTransactionStateError as exc:
            raise IncidentStoreError(
                "This operation requires an active caller-owned transaction"
            ) from exc

    def _ensure_transaction_available(self) -> None:
        if self.connection.closed:
            raise IncidentStoreError("Database connection is closed")

        if self.connection.autocommit is not True:
            raise IncidentStoreError(
                "PostgreSQL incident operations require autocommit=True"
            )

        if self.connection.info.transaction_status.name != "IDLE":
            raise IncidentStoreError(
                "Incident operation cannot run inside an existing transaction"
            )

    def _get_unchecked(self, incident_id: str) -> Incident | None:
        row = self.connection.execute(
            """
            SELECT
                incident_id,
                title,
                summary,
                severity,
                status,
                created_at,
                updated_at
            FROM soc_incidents
            WHERE incident_id = %s
            """,
            (incident_id,),
        ).fetchone()

        if row is None:
            return None

        evidence_rows = self.connection.execute(
            """
            SELECT
                evidence_id,
                kind,
                reference_id,
                description,
                observed_at
            FROM soc_incident_evidence
            WHERE incident_id = %s
            ORDER BY evidence_sequence
            """,
            (incident_id,),
        ).fetchall()

        try:
            evidence = tuple(
                _evidence_from_row(item)
                for item in evidence_rows
            )

            return Incident(
                incident_id=row["incident_id"],
                title=row["title"],
                summary=row["summary"],
                severity=row["severity"],
                status=row["status"],
                created_at=_timestamp_from_database(
                    row["created_at"],
                    "incident created_at",
                ),
                updated_at=_timestamp_from_database(
                    row["updated_at"],
                    "incident updated_at",
                ),
                evidence=evidence,
            )
        except (TypeError, ValueError, IncidentStoreError) as exc:
            raise IncidentStoreError(
                f"Persisted incident {incident_id!r} failed validation"
            ) from exc

    def get(self, incident_id: str) -> Incident | None:
        """Return one incident and its evidence, or None if absent."""
        if not isinstance(incident_id, str) or not incident_id.strip():
            raise ValueError("incident_id must not be empty")

        try:
            return self._get_unchecked(incident_id)
        except Error as exc:
            raise IncidentStoreError(
                "Unable to retrieve SOC incident"
            ) from exc

    def _validate_incident_identity(self, incident: Incident) -> None:
        """Validate immutable incident fields without locking the row.

        The preceding INSERT ... ON CONFLICT arbitrates concurrent creation
        of the same incident ID. This check only reads immutable fields;
        it must not require UPDATE privilege on the incident table.
        Status, updated_at and evidence are intentionally excluded.
        Timestamp identity is compared as an instant, not as input text.
        """
        row = self.connection.execute(
            """
            SELECT title, summary, severity, created_at
            FROM soc_incidents
            WHERE incident_id = %s
            """,
            (incident.incident_id,),
        ).fetchone()

        if row is None:
            raise IncidentStoreError(
                "Incident disappeared during identity validation"
            )

        expected_created_at = _timestamp_to_datetime(
            incident.created_at,
            "created_at",
        )

        actual_created_at = row["created_at"]

        if (
            not isinstance(actual_created_at, datetime)
            or actual_created_at.tzinfo is None
            or actual_created_at.utcoffset() is None
        ):
            raise IncidentStoreError(
                "Persisted incident created_at is invalid"
            )

        if (
            row["title"] != incident.title
            or row["summary"] != incident.summary
            or row["severity"] != incident.severity
            or actual_created_at.astimezone(timezone.utc)
            != expected_created_at
        ):
            raise IncidentStoreError(
                "Incident ID already exists with different content "
                "in immutable fields"
            )

    def _insert_evidence(
        self,
        incident_id: str,
        evidence: IncidentEvidence,
    ) -> bool:
        """Insert evidence or accept an exact replay.

        A reused evidence ID with different content is an integrity error.
        The caller is responsible for transaction management.
        """
        observed_at = _timestamp_to_datetime(
            evidence.observed_at,
            "observed_at",
        )

        inserted = self.connection.execute(
            """
            INSERT INTO soc_incident_evidence (
                evidence_id,
                incident_id,
                kind,
                reference_id,
                description,
                observed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (incident_id, evidence_id) DO NOTHING
            RETURNING evidence_sequence
            """,
            (
                evidence.evidence_id,
                incident_id,
                evidence.kind,
                evidence.reference_id,
                evidence.description,
                observed_at,
            ),
        ).fetchone()

        if inserted is not None:
            return True

        existing = self.connection.execute(
            """
            SELECT kind, reference_id, description, observed_at
            FROM soc_incident_evidence
            WHERE incident_id = %s AND evidence_id = %s
            """,
            (incident_id, evidence.evidence_id),
        ).fetchone()

        if existing is None:
            raise IncidentStoreError(
                "Evidence insert conflicted but the existing row is missing"
            )

        actual_observed_at = existing["observed_at"]

        if (
            not isinstance(actual_observed_at, datetime)
            or actual_observed_at.tzinfo is None
            or actual_observed_at.utcoffset() is None
        ):
            raise IncidentStoreError(
                "Persisted evidence observed_at is invalid"
            )

        expected = (
            evidence.kind,
            evidence.reference_id,
            evidence.description,
            observed_at,
        )
        actual = (
            existing["kind"],
            existing["reference_id"],
            existing["description"],
            actual_observed_at.astimezone(timezone.utc),
        )

        if actual != expected:
            raise IncidentStoreError(
                "Evidence ID already exists with different content"
            )

        return False

    def _ensure_initial_history(self, incident_id: str) -> None:
        """Add the initial system history exactly once under the row lock."""
        self.connection.execute(
            """
            INSERT INTO soc_incident_history (
                incident_id,
                old_status,
                new_status,
                changed_at,
                changed_by
            )
            SELECT
                incident_id,
                NULL,
                status,
                created_at,
                'system'
            FROM soc_incidents AS incident
            WHERE incident_id = %s
              AND NOT EXISTS (
                  SELECT 1
                  FROM soc_incident_history AS history
                  WHERE history.incident_id = incident.incident_id
              )
            """,
            (incident_id,),
        )

    def _save_one_in_transaction(self, incident: Incident) -> Incident:
        """Save one incident within an already active transaction."""
        self._require_caller_transaction()

        self.connection.execute(
            """
            INSERT INTO soc_incidents (
                incident_id,
                title,
                summary,
                severity,
                status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (incident_id) DO NOTHING
            """,
            (
                incident.incident_id,
                incident.title,
                incident.summary,
                incident.severity,
                incident.status,
                _timestamp_to_datetime(
                    incident.created_at,
                    "created_at",
                ),
                _timestamp_to_datetime(
                    incident.updated_at,
                    "updated_at",
                ),
            ),
        )

        self._validate_incident_identity(incident)

        for evidence in incident.evidence:
            self._insert_evidence(incident.incident_id, evidence)

        self._ensure_initial_history(incident.incident_id)

        stored = self._get_unchecked(incident.incident_id)
        if stored is None:
            raise IncidentStoreError(
                "Incident disappeared during save"
            )

        return stored

    def save(self, incident: Incident) -> Incident:
        """Insert an incident and its evidence atomically and idempotently."""
        if not isinstance(incident, Incident):
            raise TypeError("incident must be an Incident")

        self._ensure_transaction_available()

        try:
            with transaction(self.connection):
                return self._save_one_in_transaction(incident)
        except (TypeError, ValueError, IncidentStoreError):
            raise
        except Error as exc:
            raise IncidentStoreError(
                "Unable to save SOC incident"
            ) from exc

    def save_many_in_transaction(
        self,
        incidents: Iterable[Incident],
    ) -> tuple[Incident, ...]:
        """Persist incidents without managing the caller's transaction."""
        self._require_caller_transaction()

        items = tuple(incidents)

        if any(not isinstance(item, Incident) for item in items):
            raise TypeError("all items must be Incident instances")

        try:
            return tuple(
                self._save_one_in_transaction(item)
                for item in items
            )
        except (TypeError, ValueError, IncidentStoreError):
            raise
        except Error as exc:
            raise IncidentStoreError(
                "Unable to save SOC incident batch"
            ) from exc

    def append_evidence_in_transaction(
        self,
        incident_id: str,
        evidence: Iterable[IncidentEvidence],
        *,
        updated_at: str | None = None,
    ) -> Incident:
        """Append evidence in the caller's transaction.

        Exact replays are ignored. A conflicting evidence ID is rejected.
        updated_at advances only when new evidence was actually inserted,
        and never moves backwards. Incident status and status history are
        not modified.
        """
        if not isinstance(incident_id, str) or not incident_id.strip():
            raise ValueError("incident_id must not be empty")

        items = tuple(evidence)
        if any(
            not isinstance(item, IncidentEvidence)
            for item in items
        ):
            raise TypeError(
                "all evidence items must be IncidentEvidence instances"
            )

        self._require_caller_transaction()

        timestamp = _timestamp_to_datetime(
            updated_at if updated_at is not None else utc_now_iso(),
            "updated_at",
        )

        try:
            row = self.connection.execute(
                """
                SELECT updated_at
                FROM soc_incidents
                WHERE incident_id = %s
                FOR UPDATE
                """,
                (incident_id,),
            ).fetchone()

            if row is None:
                raise IncidentNotFoundError(incident_id)

            existing_timestamp = row["updated_at"]

            if (
                not isinstance(existing_timestamp, datetime)
                or existing_timestamp.tzinfo is None
                or existing_timestamp.utcoffset() is None
            ):
                raise IncidentStoreError(
                    "Persisted incident updated_at is invalid"
                )

            existing_timestamp = existing_timestamp.astimezone(
                timezone.utc
            )

            if timestamp < existing_timestamp:
                timestamp = existing_timestamp

            inserted = 0
            for item in items:
                inserted += self._insert_evidence(incident_id, item)

            if inserted:
                updated = self.connection.execute(
                    """
                    UPDATE soc_incidents
                    SET updated_at = %s
                    WHERE incident_id = %s
                    RETURNING incident_id
                    """,
                    (timestamp, incident_id),
                ).fetchone()

                if updated is None:
                    raise IncidentStoreError(
                        "Incident disappeared while appending evidence"
                    )

            stored = self._get_unchecked(incident_id)

            if stored is None:
                raise IncidentStoreError(
                    "Incident disappeared while appending evidence"
                )

            return stored

        except (
            ValueError,
            TypeError,
            IncidentNotFoundError,
            IncidentStoreError,
        ):
            raise
        except Error as exc:
            raise IncidentStoreError(
                "Unable to append SOC incident evidence"
            ) from exc

    def save_many(
        self,
        incidents: Iterable[Incident],
    ) -> tuple[Incident, ...]:
        """Save a batch atomically; either every incident is saved or none."""
        items = tuple(incidents)

        if any(not isinstance(item, Incident) for item in items):
            raise TypeError("all items must be Incident instances")

        self._ensure_transaction_available()

        try:
            with transaction(self.connection):
                return self.save_many_in_transaction(items)
        except (TypeError, ValueError, IncidentStoreError):
            raise
        except Error as exc:
            raise IncidentStoreError(
                "Unable to save SOC incident batch"
            ) from exc

    def list_incidents(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[Incident, ...]:
        """List incidents newest-updated first with bounded pagination."""
        if status is not None and (
            not isinstance(status, str)
            or status not in {"open", "investigating", "resolved"}
        ):
            raise ValueError("unsupported incident status")

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 500
        ):
            raise ValueError("limit must be between 1 and 500")

        if (
            isinstance(offset, bool)
            or not isinstance(offset, int)
            or offset < 0
        ):
            raise ValueError("offset must be a non-negative integer")

        try:
            if status is None:
                rows = self.connection.execute(
                    """
                    SELECT incident_id
                    FROM soc_incidents
                    ORDER BY updated_at DESC, incident_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                ).fetchall()
            else:
                rows = self.connection.execute(
                    """
                    SELECT incident_id
                    FROM soc_incidents
                    WHERE status = %s
                    ORDER BY updated_at DESC, incident_id
                    LIMIT %s OFFSET %s
                    """,
                    (status, limit, offset),
                ).fetchall()

            incidents = tuple(
                self._get_unchecked(row["incident_id"])
                for row in rows
            )

            if any(item is None for item in incidents):
                raise IncidentStoreError(
                    "Incident disappeared during listing"
                )

            return incidents

        except IncidentStoreError:
            raise
        except Error as exc:
            raise IncidentStoreError(
                "Unable to list SOC incidents"
            ) from exc

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

        if not isinstance(incident_id, str) or not incident_id.strip():
            raise ValueError("incident_id must not be empty")

        timestamp = _timestamp_to_datetime(
            updated_at if updated_at is not None else utc_now_iso(),
            "updated_at",
        )

        self._ensure_transaction_available()

        try:
            with transaction(self.connection):
                locked = self.connection.execute(
                    """
                    SELECT incident_id
                    FROM soc_incidents
                    WHERE incident_id = %s
                    FOR UPDATE
                    """,
                    (incident_id,),
                ).fetchone()

                if locked is None:
                    raise IncidentNotFoundError(incident_id)

                current = self._get_unchecked(incident_id)
                if current is None:
                    raise IncidentNotFoundError(incident_id)

                changed = current.transition(
                    new_status,
                    updated_at=timestamp.isoformat(),
                )

                if changed is current:
                    return current

                updated = self.connection.execute(
                    """
                    UPDATE soc_incidents
                    SET status = %s, updated_at = %s
                    WHERE incident_id = %s AND status = %s
                    RETURNING incident_id
                    """,
                    (
                        changed.status,
                        timestamp,
                        incident_id,
                        current.status,
                    ),
                ).fetchone()

                if updated is None:
                    raise IncidentStoreError(
                        "Incident status changed concurrently"
                    )

                self.connection.execute(
                    """
                    INSERT INTO soc_incident_history (
                        incident_id,
                        old_status,
                        new_status,
                        changed_at,
                        changed_by
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        incident_id,
                        current.status,
                        changed.status,
                        timestamp,
                        changed_by.strip(),
                    ),
                )

                stored = self._get_unchecked(incident_id)

                if stored is None:
                    raise IncidentStoreError(
                        "Incident disappeared during transition"
                    )

                return stored

        except (
            ValueError,
            IncidentNotFoundError,
            IncidentStoreError,
        ):
            raise
        except Error as exc:
            raise IncidentStoreError(
                "Unable to transition SOC incident"
            ) from exc

    def history(
        self,
        incident_id: str,
    ) -> tuple[dict[str, object], ...]:
        """Return the immutable status history in insertion order."""
        if not isinstance(incident_id, str) or not incident_id.strip():
            raise ValueError("incident_id must not be empty")

        try:
            exists = self.connection.execute(
                """
                SELECT 1
                FROM soc_incidents
                WHERE incident_id = %s
                """,
                (incident_id,),
            ).fetchone()

            if exists is None:
                raise IncidentNotFoundError(incident_id)

            rows = self.connection.execute(
                """
                SELECT old_status, new_status, changed_at, changed_by
                FROM soc_incident_history
                WHERE incident_id = %s
                ORDER BY history_id
                """,
                (incident_id,),
            ).fetchall()

            return tuple({
                "old_status": row["old_status"],
                "new_status": row["new_status"],
                "changed_at": _timestamp_from_database(
                    row["changed_at"],
                    "incident history changed_at",
                ),
                "changed_by": row["changed_by"],
            } for row in rows)

        except IncidentNotFoundError:
            raise
        except Error as exc:
            raise IncidentStoreError(
                "Unable to read SOC incident history"
            ) from exc


__all__ = [
    "PostgresIncidentStore",
    "_timestamp_to_datetime",
    "_timestamp_from_database",
]
