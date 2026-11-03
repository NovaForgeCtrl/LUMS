"""Isolated tests for migration definitions and checksum handling."""

from pathlib import Path
import sys

import pytest


SERVER_DIR = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from migration_runner import (
    Migration,
    MigrationDefinitionError,
    migration_checksum,
    validate_migrations,
)


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
