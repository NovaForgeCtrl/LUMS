"""Isolated tests for migration definitions and checksum handling."""

from pathlib import Path
import sys

import pytest


SERVER_DIR = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import migration_runner

from migration_runner import (
    Migration,
    MigrationDefinitionError,
    MigrationHistoryError,
    MigrationRunnerError,
    migration_checksum,
    validate_migrations,
)

from psycopg.pq import TransactionStatus
from types import SimpleNamespace


def make_migration(version, statements=("SELECT 1",)):
    return Migration(
        version=version,
        description=f"Migration {version}",
        statements=statements,
    )


def test_checksum_is_stable_for_string_and_bytes():
    assert migration_checksum("SELECT 1;") == migration_checksum(b"SELECT 1;")
    assert len(migration_checksum("SELECT 1;")) == 64


def test_checksum_rejects_unsupported_source_type():
    with pytest.raises(TypeError, match="str or bytes"):
        migration_checksum(123)


def test_migration_checksum_is_derived_from_exact_statements():
    first = make_migration("001-core-schema", ("CREATE TABLE probe (id INTEGER)",))
    second = make_migration("001-core-schema", ("CREATE TABLE probe (id BIGINT)",))

    assert first.checksum != second.checksum


def test_migration_checksum_includes_statement_order():
    first = make_migration(
        "001-core-schema",
        ("CREATE TABLE first_probe (id INTEGER)", "CREATE TABLE second_probe (id INTEGER)"),
    )
    second = make_migration(
        "001-core-schema",
        ("CREATE TABLE second_probe (id INTEGER)", "CREATE TABLE first_probe (id INTEGER)"),
    )

    assert first.checksum != second.checksum


def test_empty_registry_is_valid():
    assert validate_migrations(()) == ()


def test_valid_registry_preserves_explicit_order():
    migrations = (
        make_migration("001-core-schema"),
        make_migration("002-security-foundation"),
        make_migration("003-soc-storage"),
    )
    assert validate_migrations(migrations) == migrations


def test_non_iterable_registry_is_rejected():
    with pytest.raises(MigrationDefinitionError, match="iterable"):
        validate_migrations(None)


def test_string_registry_is_rejected():
    with pytest.raises(MigrationDefinitionError, match="iterable"):
        validate_migrations("001-core-schema")


def test_non_migration_entry_is_rejected():
    with pytest.raises(MigrationDefinitionError, match="Migration instance"):
        validate_migrations(("001-core-schema",))


def test_invalid_version_is_rejected():
    with pytest.raises(MigrationDefinitionError, match="NNN-name"):
        validate_migrations((make_migration("core-schema"),))


def test_duplicate_versions_are_rejected():
    migrations = (
        make_migration("001-core-schema", ("SELECT 1",)),
        make_migration("001-core-schema", ("SELECT 2",)),
    )
    with pytest.raises(MigrationDefinitionError, match="duplicate"):
        validate_migrations(migrations)


def test_unsorted_versions_are_rejected():
    migrations = (
        make_migration("002-security-foundation"),
        make_migration("001-core-schema"),
    )
    with pytest.raises(MigrationDefinitionError, match="ascending"):
        validate_migrations(migrations)


def test_empty_description_is_rejected():
    migration = make_migration("001-core-schema")
    invalid = Migration(
        version=migration.version,
        description=" ",
        statements=migration.statements,
    )
    with pytest.raises(MigrationDefinitionError, match="description"):
        validate_migrations((invalid,))


def test_empty_statement_sequence_is_rejected():
    with pytest.raises(MigrationDefinitionError, match="no SQL statements"):
        validate_migrations((
            make_migration("001-core-schema", ()),
        ))


def test_mutable_statement_list_is_rejected():
    invalid = Migration(
        version="001-core-schema",
        description="Migration 001-core-schema",
        statements=["SELECT 1"],
    )
    with pytest.raises(MigrationDefinitionError, match="immutable tuple"):
        validate_migrations((invalid,))


@pytest.mark.parametrize(
    "statement",
    ["", "   ", "\x00"],
)
def test_invalid_sql_statement_is_rejected(statement):
    with pytest.raises(MigrationDefinitionError, match="invalid SQL statement"):
        validate_migrations((
            make_migration("001-core-schema", (statement,)),
        ))


def test_non_string_sql_statement_is_rejected():
    with pytest.raises(MigrationDefinitionError, match="invalid SQL statement"):
        validate_migrations((
            make_migration("001-core-schema", (123,)),
        ))


class FakeCursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeHistoryConnection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query, params=None):
        if "SELECT version, checksum FROM schema_migrations" in query:
            return SimpleNamespace(fetchall=lambda: self.rows)
        raise AssertionError(f"Unexpected SQL in history test: {query!r}")


def test_migration_history_requires_contiguous_prefix():
    migrations = (
        make_migration("001-core-schema"),
        make_migration("002-security-schema"),
        make_migration("003-rbac-schema"),
    )
    connection = FakeHistoryConnection(
        [
            {"version": "001-core-schema", "checksum": migrations[0].checksum},
            {"version": "003-rbac-schema", "checksum": migrations[2].checksum},
        ]
    )

    with pytest.raises(MigrationHistoryError, match="contains a gap"):
        migration_runner._load_and_validate_history(connection, migrations)


def test_migration_history_allows_single_migration_subset():
    migration = make_migration("008-alerts")
    connection = FakeHistoryConnection(
        [
            {"version": migration.version, "checksum": migration.checksum},
        ]
    )

    assert migration_runner._load_and_validate_history(
        connection,
        (migration,),
    ) == {migration.version}


class FakeLockConnection:
    def __init__(self, unlock_result=True, unlock_error=None):
        self.closed = False
        self.autocommit = True
        self.info = SimpleNamespace(
            transaction_status=TransactionStatus.IDLE
        )
        self.unlock_result = unlock_result
        self.unlock_error = unlock_error

    def execute(self, query, params=None):
        if "pg_advisory_lock" in query:
            return FakeCursor()

        if "pg_advisory_unlock" in query:
            if self.unlock_error is not None:
                raise self.unlock_error
            return FakeCursor({"unlocked": self.unlock_result})

        raise AssertionError(f"Unexpected SQL in lock test: {query!r}")


def test_runner_reports_advisory_unlock_returning_false(monkeypatch):
    monkeypatch.setattr(
        migration_runner,
        "_ensure_history_table",
        lambda connection: None,
    )
    monkeypatch.setattr(
        migration_runner,
        "_load_and_validate_history",
        lambda connection, migrations: set(),
    )

    connection = FakeLockConnection(unlock_result=False)

    with pytest.raises(
        MigrationRunnerError,
        match="Could not release PostgreSQL migration advisory lock",
    ):
        migration_runner.run_migrations(connection, ())


def test_runner_reports_advisory_unlock_exception(monkeypatch):
    monkeypatch.setattr(
        migration_runner,
        "_ensure_history_table",
        lambda connection: None,
    )
    monkeypatch.setattr(
        migration_runner,
        "_load_and_validate_history",
        lambda connection, migrations: set(),
    )

    connection = FakeLockConnection(
        unlock_error=RuntimeError("simulated unlock failure")
    )

    with pytest.raises(
        MigrationRunnerError,
        match="Could not release PostgreSQL migration advisory lock",
    ) as exc_info:
        migration_runner.run_migrations(connection, ())

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "simulated unlock failure" in str(exc_info.value.__cause__)


def test_runner_preserves_primary_error_when_unlock_also_fails(monkeypatch):
    primary_error = MigrationHistoryError("simulated history failure")

    monkeypatch.setattr(
        migration_runner,
        "_ensure_history_table",
        lambda connection: (_ for _ in ()).throw(primary_error),
    )

    connection = FakeLockConnection(
        unlock_error=RuntimeError("simulated unlock failure")
    )

    with pytest.raises(MigrationHistoryError) as exc_info:
        migration_runner.run_migrations(connection, ())

    assert exc_info.value is primary_error
    assert any(
        "simulated unlock failure" in note
        for note in getattr(exc_info.value, "__notes__", ())
    )


def test_runner_accepts_successful_advisory_unlock(monkeypatch):
    monkeypatch.setattr(
        migration_runner,
        "_ensure_history_table",
        lambda connection: None,
    )
    monkeypatch.setattr(
        migration_runner,
        "_load_and_validate_history",
        lambda connection, migrations: set(),
    )

    result = migration_runner.run_migrations(
        FakeLockConnection(unlock_result=True),
        (),
    )

    assert result.applied == ()
    assert result.already_applied == ()
