import gzip
import sqlite3

import pytest

from server.database_backup import (
    BackupStorageError,
    create_database_backup,
    list_database_backups,
)


@pytest.fixture
def source_database(tmp_path):
    database_path = tmp_path / "lums.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE sample (value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO sample (value) VALUES ('backup data')"
        )
    return database_path


@pytest.mark.parametrize("backup_format", ["db", "db.gz"])
def test_database_backup_is_integral_and_restorable(
    tmp_path,
    source_database,
    backup_format,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()

    result = create_database_backup(
        source_database,
        backup_directory,
        backup_format,
    )
    backup_path = backup_directory / result["filename"]

    assert backup_path.is_file()
    assert result["format"] == backup_format
    assert result["size_bytes"] == backup_path.stat().st_size

    restored_path = tmp_path / "restored.db"
    if backup_format == "db.gz":
        with gzip.open(backup_path, "rb") as compressed:
            restored_path.write_bytes(compressed.read())
    else:
        restored_path.write_bytes(backup_path.read_bytes())

    with sqlite3.connect(restored_path) as restored:
        assert restored.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0] == "ok"
        assert restored.execute(
            "SELECT value FROM sample"
        ).fetchone()[0] == "backup data"


def test_backup_listing_ignores_unrecognized_files(
    tmp_path,
    source_database,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    (backup_directory / "unrelated.db").write_text("not a backup")

    created = create_database_backup(
        source_database,
        backup_directory,
        "db",
    )

    backups = list_database_backups(backup_directory)

    assert [backup["filename"] for backup in backups] == [
        created["filename"],
    ]


def test_backup_requires_a_configured_writable_directory(
    tmp_path,
    source_database,
):
    missing_directory = tmp_path / "missing"

    with pytest.raises(BackupStorageError):
        create_database_backup(
            source_database,
            missing_directory,
            "db",
        )
