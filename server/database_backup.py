import gzip
import os
import re
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PurePosixPath
from secrets import token_hex


BACKUP_FORMATS = {"db", "db.gz"}
BACKUP_FILENAME_PATTERN = re.compile(
    r"^lums-backup-\d{8}T\d{6}\.\d{6}Z-[a-f0-9]{16}\.db(?:\.gz)?$"
)


class BackupStorageError(Exception):
    pass


class BackupPathError(BackupStorageError):
    pass


def resolve_backup_directory(root_directory, relative_path="", create=False):
    if (
        not isinstance(relative_path, str)
        or len(relative_path) > 512
        or "\x00" in relative_path
        or "\\" in relative_path
    ):
        raise BackupPathError("Ungültiger Backup-Unterordner.")

    relative = PurePosixPath(relative_path or ".")
    if relative.is_absolute() or ".." in relative.parts:
        raise BackupPathError("Ungültiger Backup-Unterordner.")

    root = Path(root_directory)
    if not root.is_dir():
        raise BackupStorageError(
            "Backup-Zielordner fehlt oder ist kein Verzeichnis."
        )

    root = root.resolve(strict=True)
    directory = root

    for part in relative.parts:
        if part in {"", "."}:
            continue

        directory = directory / part
        if directory.is_symlink():
            raise BackupPathError(
                "Backup-Unterordner darf keine symbolischen Links enthalten."
            )

        if not directory.exists():
            if not create:
                raise BackupStorageError(
                    "Backup-Unterordner ist nicht vorhanden."
                )
            try:
                directory.mkdir(mode=0o700)
            except FileExistsError:
                if directory.is_symlink() or not directory.is_dir():
                    raise BackupPathError(
                        "Ungültiger Backup-Unterordner."
                    )

        if not directory.is_dir():
            raise BackupPathError(
                "Backup-Unterordner ist kein Verzeichnis."
            )

    try:
        directory.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as error:
        raise BackupPathError(
            "Backup-Unterordner muss innerhalb des Speicherziels liegen."
        ) from error

    _require_backup_directory(directory)
    return directory


def _require_backup_directory(directory):
    directory = Path(directory)

    if not directory.is_dir():
        raise BackupStorageError(
            "Backup-Zielordner fehlt oder ist kein Verzeichnis."
        )

    if not os.access(directory, os.W_OK | os.X_OK):
        raise BackupStorageError(
            "Backup-Zielordner ist für LUMS nicht beschreibbar."
        )

    return directory


def list_database_backups(directory, limit=10, relative_path=""):
    directory = resolve_backup_directory(
        directory,
        relative_path=relative_path,
    )
    backups = []

    for path in directory.iterdir():
        if (
            not BACKUP_FILENAME_PATTERN.fullmatch(path.name)
            or not path.is_file()
        ):
            continue

        stat = path.stat()
        backups.append({
            "filename": path.name,
            "format": "db.gz" if path.name.endswith(".db.gz") else "db",
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(
                stat.st_mtime,
                timezone.utc,
            ).isoformat(),
        })

    backups.sort(
        key=lambda item: item["created_at"],
        reverse=True,
    )
    return backups[:limit]


def delete_database_backup(directory, filename, relative_path=""):
    if (
        not isinstance(filename, str)
        or not BACKUP_FILENAME_PATTERN.fullmatch(filename)
    ):
        raise BackupPathError("Ungültiger Backup-Dateiname.")

    directory = resolve_backup_directory(
        directory,
        relative_path=relative_path,
    )
    backup_path = directory / filename

    if backup_path.is_symlink():
        raise BackupPathError("Backup-Datei darf kein symbolischer Link sein.")

    if not backup_path.is_file():
        raise FileNotFoundError("Backup-Datei nicht gefunden.")

    backup_path.unlink()
    return filename


def create_database_backup(
    database_path,
    directory,
    backup_format,
    relative_path="",
):
    if backup_format not in BACKUP_FORMATS:
        raise ValueError("Unsupported database backup format.")

    directory = resolve_backup_directory(
        directory,
        relative_path=relative_path,
        create=True,
    )
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S.%fZ"
    )
    filename = (
        f"lums-backup-{timestamp}-{token_hex(8)}.{backup_format}"
    )
    destination = directory / filename
    temporary_db = None
    temporary_archive = None

    try:
        db_descriptor, temporary_db = tempfile.mkstemp(
            prefix=".lums-backup-",
            suffix=".db.tmp",
            dir=directory,
        )
        os.close(db_descriptor)
        os.chmod(temporary_db, 0o600)

        with closing(
            sqlite3.connect(database_path, timeout=10)
        ) as source:
            source.execute("PRAGMA busy_timeout = 5000")
            with closing(
                sqlite3.connect(temporary_db, timeout=10)
            ) as target:
                source.backup(target, pages=100, sleep=0.1)
                integrity = target.execute(
                    "PRAGMA integrity_check"
                ).fetchone()

        if integrity is None or integrity[0] != "ok":
            raise sqlite3.DatabaseError(
                "Database backup failed its integrity check."
            )

        if backup_format == "db":
            os.replace(temporary_db, destination)
            temporary_db = None
        else:
            archive_descriptor, temporary_archive = tempfile.mkstemp(
                prefix=".lums-backup-",
                suffix=".gz.tmp",
                dir=directory,
            )
            os.chmod(temporary_archive, 0o600)

            with (
                os.fdopen(archive_descriptor, "wb") as archive_file,
                open(temporary_db, "rb") as database_file,
                gzip.GzipFile(
                    fileobj=archive_file,
                    mode="wb",
                    mtime=0,
                ) as compressed_file,
            ):
                shutil.copyfileobj(database_file, compressed_file)

            os.replace(temporary_archive, destination)
            temporary_archive = None

        return {
            "filename": filename,
            "format": backup_format,
            "size_bytes": destination.stat().st_size,
        }
    finally:
        for temporary_path in (temporary_db, temporary_archive):
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)
