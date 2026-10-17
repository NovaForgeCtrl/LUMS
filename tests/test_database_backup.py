import gzip
import sqlite3

import pytest

from server.database_backup import (
    BackupPathError,
    BackupStorageError,
    create_database_backup,
    delete_database_backup,
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


def test_backup_creates_and_lists_a_safe_relative_subdirectory(
    tmp_path,
    source_database,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()

    created = create_database_backup(
        source_database,
        backup_directory,
        "db",
        relative_path="nas/daily",
    )

    assert (backup_directory / "nas" / "daily" / created["filename"]).is_file()
    assert list_database_backups(
        backup_directory,
        relative_path="nas/daily",
    )[0]["filename"] == created["filename"]


@pytest.mark.parametrize(
    "relative_path",
    [
        "../outside",
        "/outside",
        "nas/../../outside",
        r"nas\outside",
    ],
)
def test_backup_rejects_absolute_and_traversal_paths(
    tmp_path,
    source_database,
    relative_path,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()

    with pytest.raises(BackupStorageError):
        create_database_backup(
            source_database,
            backup_directory,
            "db",
            relative_path=relative_path,
        )


def test_backup_rejects_symlinked_subdirectory(
    tmp_path,
    source_database,
):
    backup_directory = tmp_path / "backups"
    outside_directory = tmp_path / "outside"
    backup_directory.mkdir()
    outside_directory.mkdir()
    (backup_directory / "external").symlink_to(
        outside_directory,
        target_is_directory=True,
    )

    with pytest.raises(BackupStorageError):
        create_database_backup(
            source_database,
            backup_directory,
            "db",
            relative_path="external",
        )


def test_database_backup_delete_removes_only_managed_backup_files(
    tmp_path,
    source_database,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    created = create_database_backup(
        source_database,
        backup_directory,
        "db",
    )

    assert delete_database_backup(
        backup_directory,
        created["filename"],
    ) == created["filename"]
    assert not (backup_directory / created["filename"]).exists()

    with pytest.raises(BackupPathError):
        delete_database_backup(backup_directory, "lums.db")


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
