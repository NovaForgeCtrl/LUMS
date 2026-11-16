import gzip
import sqlite3
from pathlib import Path

import pytest

import server.database_backup as database_backup

from server.database_backup import (
    BackupPathError,
    BackupStorageError,
    create_database_backup,
    delete_database_backup,
    list_database_backups,
    restore_database_backup,
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
def test_backup_restore_round_trip_preserves_source_and_data(
    tmp_path,
    source_database,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()

    result = create_database_backup(
        source_database,
        backup_directory,
        "db",
    )
    backup_path = backup_directory / result["filename"]
    restored_path = tmp_path / "restored.db"

    # Restore only into a new temporary file. Never overwrite the source.
    restored_path.write_bytes(backup_path.read_bytes())

    with sqlite3.connect(restored_path) as restored:
        assert restored.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0] == "ok"
        assert restored.execute(
            "SELECT value FROM sample"
        ).fetchone()[0] == "backup data"

    with sqlite3.connect(source_database) as source:
        assert source.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0] == "ok"
        assert source.execute(
            "SELECT value FROM sample"
        ).fetchone()[0] == "backup data"


@pytest.mark.parametrize("backup_format", ["db", "db.gz"])
def test_restore_database_backup_restores_valid_backup(
    tmp_path,
    source_database,
    backup_format,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    created = create_database_backup(
        source_database,
        backup_directory,
        backup_format,
    )
    target = tmp_path / "target.db"
    with sqlite3.connect(target) as connection:
        connection.execute("CREATE TABLE old_data (value TEXT)")
        connection.execute("INSERT INTO old_data VALUES ('keep until valid')")

    result = restore_database_backup(
        backup_directory,
        created["filename"],
        target,
    )

    assert result["filename"] == created["filename"]
    assert result["database_path"] == str(target)
    with sqlite3.connect(target) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute(
            "SELECT value FROM sample"
        ).fetchone()[0] == "backup data"
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("SELECT value FROM old_data")


def test_restore_rejects_corrupt_backup_without_replacing_target(
    tmp_path,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    filename = "lums-backup-20261026T120000.000000Z-0123456789abcdef.db"
    (backup_directory / filename).write_bytes(b"not a sqlite database")
    target = tmp_path / "target.db"
    with sqlite3.connect(target) as connection:
        connection.execute("CREATE TABLE keep (value TEXT)")
        connection.execute("INSERT INTO keep VALUES ('original')")

    with pytest.raises(BackupStorageError):
        restore_database_backup(backup_directory, filename, target)

    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT value FROM keep"
        ).fetchone()[0] == "original"


def test_restore_rejects_wal_sidecar(tmp_path, source_database):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    created = create_database_backup(
        source_database,
        backup_directory,
        "db",
    )
    target = tmp_path / "target.db"
    Path(str(target) + "-wal").write_bytes(b"")
    with pytest.raises(BackupStorageError, match="WAL/SHM"):
        restore_database_backup(
            backup_directory,
            created["filename"],
            target,
        )


def test_restore_rejects_symlink_target(
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
    actual = tmp_path / "actual.db"
    actual.write_bytes(b"preserve")
    target = tmp_path / "linked.db"
    target.symlink_to(actual)

    with pytest.raises(BackupPathError):
        restore_database_backup(
            backup_directory,
            created["filename"],
            target,
        )
    assert actual.read_bytes() == b"preserve"


@pytest.mark.parametrize("backup_format", ["db", "db.gz"])
def test_restore_rejects_empty_backup_without_replacing_target(
    tmp_path,
    backup_format,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    filename = "lums-backup-20261026T120000.000000Z-0123456789abcdef.db"
    backup_path = backup_directory / filename

    if backup_format == "db.gz":
        filename += ".gz"
        backup_path = backup_directory / filename
        with gzip.open(backup_path, "wb"):
            pass
    else:
        backup_path.write_bytes(b"")

    target = tmp_path / "target.db"
    with sqlite3.connect(target) as connection:
        connection.execute("CREATE TABLE keep (value TEXT)")
        connection.execute("INSERT INTO keep VALUES ('original')")

    with pytest.raises(BackupStorageError):
        restore_database_backup(backup_directory, filename, target)

    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT value FROM keep"
        ).fetchone()[0] == "original"


def test_restore_rejects_valid_empty_sqlite_database_without_replacing_target(
    tmp_path,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    filename = "lums-backup-20261026T120000.000000Z-0123456789abcdef.db"
    empty_database = tmp_path / "empty.db"

    with sqlite3.connect(empty_database):
        pass

    (backup_directory / filename).write_bytes(empty_database.read_bytes())

    target = tmp_path / "target.db"
    with sqlite3.connect(target) as connection:
        connection.execute("CREATE TABLE keep (value TEXT)")
        connection.execute("INSERT INTO keep VALUES ('original')")

    with pytest.raises(BackupStorageError):
        restore_database_backup(backup_directory, filename, target)

    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT value FROM keep"
        ).fetchone()[0] == "original"


def test_restore_rejects_foreign_key_violation_without_replacing_target(
    tmp_path,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    source = tmp_path / "source-invalid-fk.db"

    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.executescript("""
            CREATE TABLE parent (
                id INTEGER PRIMARY KEY
            );
            CREATE TABLE child (
                id INTEGER PRIMARY KEY,
                parent_id INTEGER NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES parent(id)
            );
            INSERT INTO child (id, parent_id) VALUES (1, 999);
        """)

    # Das ungültige Backup direkt erzeugen: Die reguläre Backup-Funktion
    # muss solche Datenbanken inzwischen korrekt ablehnen.
    filename = (
        "lums-backup-20261026T120000.000000Z-0123456789abcdef.db"
    )
    backup_path = backup_directory / filename
    backup_path.write_bytes(source.read_bytes())

    target = tmp_path / "target.db"
    with sqlite3.connect(target) as connection:
        connection.execute(
            "CREATE TABLE sentinel (value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO sentinel VALUES ('original-target')"
        )

    with pytest.raises(BackupStorageError, match="Fremdschlüssel"):
        restore_database_backup(
            backup_directory,
            filename,
            target,
        )

    # Der fehlgeschlagene Restore darf das vorhandene Ziel nicht ersetzen.
    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT value FROM sentinel"
        ).fetchone()[0] == "original-target"
        assert connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'child'"
        ).fetchone() is None


@pytest.mark.parametrize("backup_format", ["db", "db.gz"])
def test_backup_creation_rejects_foreign_key_violations(
    tmp_path,
    backup_format,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    source = tmp_path / "invalid-fk.db"

    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.executescript("""
            CREATE TABLE parent (
                id INTEGER PRIMARY KEY
            );
            CREATE TABLE child (
                id INTEGER PRIMARY KEY,
                parent_id INTEGER NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES parent(id)
            );
            INSERT INTO child (id, parent_id) VALUES (1, 999);
        """)

    with pytest.raises(BackupStorageError):
        create_database_backup(
            source,
            backup_directory,
            backup_format,
        )

    # Kein unvollständiges oder ungültiges Backup darf veröffentlicht bleiben.
    assert list(backup_directory.iterdir()) == []


def test_restore_replace_failure_preserves_target_and_cleans_temp(
    tmp_path, source_database, monkeypatch
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    backup = create_database_backup(
        source_database,
        backup_directory,
        "db",
    )

    target = tmp_path / "target.db"
    with sqlite3.connect(target) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT)")
        connection.execute("INSERT INTO sentinel VALUES ('original-target')")

    def fail_replace(source, destination):
        raise OSError("simulated atomic replacement failure")

    monkeypatch.setattr(database_backup.os, "replace", fail_replace)

    with pytest.raises(BackupStorageError, match="beschädigt|validiert"):
        restore_database_backup(
            backup_directory,
            backup["filename"],
            target,
        )

    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT value FROM sentinel"
        ).fetchone()[0] == "original-target"

    assert list(tmp_path.glob(".lums-restore-*.db.tmp")) == []
