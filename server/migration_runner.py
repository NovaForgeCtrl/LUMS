"""Central PostgreSQL-only migration runner for LUMS."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256

from psycopg import Connection
from psycopg.pq import TransactionStatus

if __package__:
    from .db_errors import (
        DatabaseConnectionStateError,
        DatabaseTransactionStateError,
    )
    from .db_transactions import transaction
else:
    from db_errors import (
        DatabaseConnectionStateError,
        DatabaseTransactionStateError,
    )
    from db_transactions import transaction


_VERSION_PATTERN = re.compile(
    r"^[0-9]{3,4}-[a-z0-9]+(?:-[a-z0-9]+)*$"
)
_CHECKSUM_PATTERN = re.compile(r"^[0-9a-f]{64}$")

_MIGRATION_LOCK_CLASS = 1_280_131_411
_MIGRATION_LOCK_OBJECT = 1


class MigrationRunnerError(RuntimeError):
    """Base exception for migration-runner failures."""


class MigrationDefinitionError(MigrationRunnerError, ValueError):
    """Invalid migration registration."""


class MigrationHistoryError(MigrationRunnerError):
    """Inconsistent database migration history."""


@dataclass(frozen=True, slots=True)
class Migration:
    """An immutable migration consisting exclusively of static SQL."""

    version: str
    description: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        """Hash the exact ordered SQL statements executed by this migration."""
        if not isinstance(self.statements, tuple):
            raise MigrationDefinitionError(
                "migration statements must be an immutable tuple"
            )

        payload = b"\x00".join(
            statement.encode("utf-8")
            for statement in self.statements
        )
        return sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class MigrationRunResult:
    applied: tuple[str, ...]
    already_applied: tuple[str, ...]


def migration_checksum(source: str | bytes) -> str:
    """Calculate SHA-256 over a string or byte sequence."""
    if isinstance(source, str):
        data = source.encode("utf-8")
    elif isinstance(source, bytes):
        data = source
    else:
        raise TypeError("migration source must be str or bytes")

    return sha256(data).hexdigest()


def validate_migrations(
    migrations: Iterable[Migration],
) -> tuple[Migration, ...]:
    """Validate and freeze an explicitly ordered migration sequence."""
    if isinstance(migrations, (str, bytes)):
        raise MigrationDefinitionError(
            "migrations must be an iterable of Migration objects"
        )

    try:
        items = tuple(migrations)
    except TypeError as exc:
        raise MigrationDefinitionError(
            "migrations must be an iterable of Migration objects"
        ) from exc

    seen: set[str] = set()
    versions: list[str] = []

    for migration in items:
        if not isinstance(migration, Migration):
            raise MigrationDefinitionError(
                "every migration must be a Migration instance"
            )

        if (
            not isinstance(migration.version, str)
            or len(migration.version) > 80
            or not _VERSION_PATTERN.fullmatch(migration.version)
        ):
            raise MigrationDefinitionError(
                "migration version must use the NNN-name format"
            )

        if migration.version in seen:
            raise MigrationDefinitionError(
                f"duplicate migration version: {migration.version}"
            )

        if (
            not isinstance(migration.description, str)
            or not migration.description.strip()
            or migration.description != migration.description.strip()
            or len(migration.description) > 200
        ):
            raise MigrationDefinitionError(
                f"invalid description for migration {migration.version}"
            )

        if not isinstance(migration.statements, tuple):
            raise MigrationDefinitionError(
                f"migration {migration.version} statements must be an immutable tuple"
            )

        if not migration.statements:
            raise MigrationDefinitionError(
                f"migration {migration.version} has no SQL statements"
            )

        for statement in migration.statements:
            if (
                not isinstance(statement, str)
                or not statement.strip()
                or "\x00" in statement
            ):
                raise MigrationDefinitionError(
                    f"migration {migration.version} contains an invalid SQL statement"
                )

        checksum = migration.checksum
        if not _CHECKSUM_PATTERN.fullmatch(checksum):
            raise MigrationDefinitionError(
                f"migration {migration.version} has an invalid SHA-256 checksum"
            )

        seen.add(migration.version)
        versions.append(migration.version)

    if versions != sorted(versions):
        raise MigrationDefinitionError(
            "migrations must be registered in ascending version order"
        )

    return items


def _validate_connection(connection: Connection) -> None:
    if connection.closed:
        raise DatabaseConnectionStateError(
            "Cannot run migrations on a closed database connection."
        )

    if connection.autocommit is not True:
        raise DatabaseTransactionStateError(
            "The migration runner requires an autocommit connection."
        )

    if connection.info.transaction_status != TransactionStatus.IDLE:
        raise DatabaseTransactionStateError(
            "The migration runner cannot start inside an existing transaction."
        )


def _ensure_history_table(connection: Connection) -> None:
    """Create and validate the shared application migration-history table."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            checksum TEXT NOT NULL,
            description TEXT NOT NULL
        )
        """
    )

    rows = connection.execute(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'schema_migrations'
        """
    ).fetchall()

    actual = {
        row["column_name"]: (row["data_type"], row["is_nullable"])
        for row in rows
    }

    expected = {
        "version": ("text", "NO"),
        "applied_at": ("timestamp with time zone", "NO"),
        "checksum": ("text", "NO"),
        "description": ("text", "NO"),
    }

    mismatches = [
        column
        for column, definition in expected.items()
        if actual.get(column) != definition
    ]

    if mismatches:
        raise MigrationHistoryError(
            "schema_migrations has an incompatible definition; "
            "invalid or missing columns: " + ", ".join(mismatches)
        )

    primary_key = connection.execute(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_catalog = kcu.constraint_catalog
         AND tc.constraint_schema = kcu.constraint_schema
         AND tc.constraint_name = kcu.constraint_name
         AND tc.table_name = kcu.table_name
        WHERE tc.table_schema = current_schema()
          AND tc.table_name = 'schema_migrations'
          AND tc.constraint_type = 'PRIMARY KEY'
        """
    ).fetchall()

    if [row["column_name"] for row in primary_key] != ["version"]:
        raise MigrationHistoryError(
            "schema_migrations must have version as its only primary-key column"
        )


def _load_and_validate_history(
    connection: Connection,
    migrations: tuple[Migration, ...],
) -> set[str]:
    rows = connection.execute(
        "SELECT version, checksum FROM schema_migrations"
    ).fetchall()

    registered = {
        migration.version: migration
        for migration in migrations
    }
    applied: set[str] = set()

    for row in rows:
        version = row["version"]
        migration = registered.get(version)

        if migration is None:
            raise MigrationHistoryError(
                f"database contains an unregistered migration: {version}"
            )

        if row["checksum"] != migration.checksum:
            raise MigrationHistoryError(
                f"checksum mismatch for applied migration: {version}"
            )

        applied.add(version)

    return applied


def run_migrations(
    connection: Connection,
    migrations: Iterable[Migration],
) -> MigrationRunResult:
    """Apply pending SQL migrations under a PostgreSQL advisory lock.

    The caller owns and must close the connection. It must use autocommit=True
    and must not already have an active transaction.

    Every migration's SQL statements and its history entry are committed
    atomically. Each tuple entry must contain exactly one static SQL statement.
    """
    _validate_connection(connection)
    ordered = validate_migrations(migrations)

    lock_acquired = False

    try:
        connection.execute(
            "SELECT pg_advisory_lock(%s, %s)",
            (_MIGRATION_LOCK_CLASS, _MIGRATION_LOCK_OBJECT),
        )
        lock_acquired = True

        _ensure_history_table(connection)
        applied_versions = _load_and_validate_history(
            connection,
            ordered,
        )

        newly_applied: list[str] = []
        already_applied: list[str] = []

        for migration in ordered:
            if migration.version in applied_versions:
                already_applied.append(migration.version)
                continue

            with transaction(connection):
                for statement in migration.statements:
                    connection.execute(statement)

                connection.execute(
                    """
                    INSERT INTO schema_migrations (
                        version, checksum, description
                    ) VALUES (%s, %s, %s)
                    """,
                    (
                        migration.version,
                        migration.checksum,
                        migration.description,
                    ),
                )

            newly_applied.append(migration.version)

        return MigrationRunResult(
            applied=tuple(newly_applied),
            already_applied=tuple(already_applied),
        )

    finally:
        if lock_acquired and not connection.closed:
            connection.execute(
                "SELECT pg_advisory_unlock(%s, %s)",
                (_MIGRATION_LOCK_CLASS, _MIGRATION_LOCK_OBJECT),
            )


__all__ = [
    "Migration",
    "MigrationDefinitionError",
    "MigrationHistoryError",
    "MigrationRunResult",
    "MigrationRunnerError",
    "migration_checksum",
    "run_migrations",
    "validate_migrations",
]
