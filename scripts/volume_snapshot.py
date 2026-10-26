"""Fail-closed archive and restore helpers for isolated LUMS volume snapshots.

No Docker commands are executed. The caller must ensure the source data is
quiescent before creating a snapshot.
"""

import ctypes
import errno
import hashlib
import os
import re
import secrets
import shutil
import stat
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


ARCHIVE_PATTERN = re.compile(
    r"^lums-volume-\d{8}T\d{6}\.\d{6}Z-[a-f0-9]{16}\.tar\.gz$"
)

# Defensive limits for local LUMS volume snapshots.
MAX_ARCHIVE_MEMBERS = 100_000
MAX_FILE_BYTES = 2 * 1024**3
MAX_TOTAL_BYTES = 10 * 1024**3


class VolumeSnapshotError(RuntimeError):
    """Base error for snapshot operations."""


class VolumeSnapshotPathError(VolumeSnapshotError):
    """Unsafe source, destination, or archive path."""


def _require_real_directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise VolumeSnapshotPathError(
            f"{label} must be a real directory, not a symlink."
        )
    return path.resolve(strict=True)


def _validate_source_tree(source: Path) -> None:
    for path in source.rglob("*"):
        try:
            info = path.lstat()
        except OSError as error:
            raise VolumeSnapshotError(
                f"Cannot inspect source entry: {path.name}"
            ) from error

        if stat.S_ISLNK(info.st_mode):
            raise VolumeSnapshotPathError(
                f"Symbolic links are not supported: {path.name}"
            )
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise VolumeSnapshotPathError(
                f"Special files are not supported: {path.name}"
            )


def _source_tree_signature(source: Path) -> tuple:
    """Capture source metadata to detect changes during snapshot creation."""
    entries = []
    try:
        for path in sorted(source.rglob("*")):
            info = path.lstat()
            entries.append((
                path.relative_to(source).as_posix(),
                info.st_dev,
                info.st_ino,
                info.st_mode,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
            ))
    except OSError as error:
        raise VolumeSnapshotError(
            "Cannot verify source tree stability."
        ) from error
    return tuple(entries)


def _safe_member_name(name: str) -> PurePosixPath:
    if not isinstance(name, str) or not name or "\x00" in name:
        raise VolumeSnapshotPathError("Invalid archive member name.")

    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise VolumeSnapshotPathError(
            f"Unsafe archive member path: {name!r}"
        )
    if any(part in {"", "."} for part in path.parts):
        raise VolumeSnapshotPathError(
            f"Non-canonical archive member path: {name!r}"
        )
    return path


def _validate_archive(archive_path: Path) -> list[tarfile.TarInfo]:
    if archive_path.is_symlink() or not archive_path.is_file():
        raise VolumeSnapshotPathError(
            "Snapshot archive must be a regular file."
        )

    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = []
            for member in archive:
                members.append(member)
                if len(members) > MAX_ARCHIVE_MEMBERS:
                    raise VolumeSnapshotError(
                        "Snapshot archive exceeds the entry-count limit."
                    )

            if not members:
                raise VolumeSnapshotError("Snapshot archive is empty.")

            total_bytes = 0
            for member in members:
                if member.isfile():
                    if member.size < 0 or member.size > MAX_FILE_BYTES:
                        raise VolumeSnapshotError(
                            "Snapshot file exceeds the per-file size limit."
                        )
                    total_bytes += member.size
                    if total_bytes > MAX_TOTAL_BYTES:
                        raise VolumeSnapshotError(
                            "Snapshot archive exceeds the total size limit."
                        )

            seen: set[str] = set()
            kinds: dict[str, str] = {}

            for member in members:
                safe_path = _safe_member_name(member.name)
                safe_name = safe_path.as_posix()

                if safe_name in seen:
                    raise VolumeSnapshotPathError(
                        f"Duplicate archive member: {safe_name}"
                    )
                seen.add(safe_name)

                if not (member.isdir() or member.isfile()):
                    raise VolumeSnapshotPathError(
                        f"Unsupported archive entry: {member.name!r}"
                    )
                if member.isfile() and member.size < 0:
                    raise VolumeSnapshotError(
                        "Invalid archive member size."
                    )

                kinds[safe_name] = (
                    "directory" if member.isdir() else "file"
                )

            # Every parent must be explicitly present as a directory.
            # Snapshot archives created by this module include directories.
            for member in members:
                safe_path = _safe_member_name(member.name)
                for index in range(1, len(safe_path.parts)):
                    parent_name = PurePosixPath(
                        *safe_path.parts[:index]
                    ).as_posix()
                    if kinds.get(parent_name) != "directory":
                        raise VolumeSnapshotPathError(
                            f"Missing or non-directory parent: {parent_name}"
                        )

            # Read all file payloads to detect truncated or corrupt streams.
            for member in members:
                if not member.isfile():
                    continue

                stream = archive.extractfile(member)
                if stream is None:
                    raise VolumeSnapshotError(
                        f"Cannot read archive member: {member.name}"
                    )

                remaining = member.size
                while remaining:
                    chunk = stream.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise VolumeSnapshotError(
                            f"Truncated archive member: {member.name}"
                        )
                    remaining -= len(chunk)

            return members

    except (tarfile.TarError, OSError, EOFError) as error:
        raise VolumeSnapshotError(
            "Snapshot archive is unreadable or corrupt."
        ) from error


def create_volume_snapshot(source_directory, backup_directory) -> dict:
    """Create and verify a snapshot; never overwrite an existing archive."""
    source = _require_real_directory(
        Path(source_directory), "Snapshot source"
    )
    destination_dir = _require_real_directory(
        Path(backup_directory), "Backup destination"
    )

    try:
        destination_dir.relative_to(source)
    except ValueError:
        pass
    else:
        raise VolumeSnapshotPathError(
            "Backup destination must be outside the source tree."
        )

    _validate_source_tree(source)
    source_signature = _source_tree_signature(source)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S.%fZ"
    )
    filename = (
        f"lums-volume-{timestamp}-{secrets.token_hex(8)}.tar.gz"
    )
    destination = destination_dir / filename

    fd, temporary_name = tempfile.mkstemp(
        prefix=".lums-volume-", suffix=".tmp", dir=destination_dir
    )
    os.close(fd)
    temporary = Path(temporary_name)

    try:
        os.chmod(temporary, 0o600)
        with tarfile.open(temporary, mode="w:gz") as archive:
            for path in sorted(source.rglob("*")):
                archive.add(
                    path,
                    arcname=path.relative_to(source).as_posix(),
                    recursive=False,
                )

        if _source_tree_signature(source) != source_signature:
            raise VolumeSnapshotError(
                "Source tree changed during snapshot creation."
            )

        _validate_archive(temporary)
        os.link(temporary, destination)

        digest = hashlib.sha256()
        with destination.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)

        return {
            "filename": filename,
            "size_bytes": destination.stat().st_size,
            "sha256": digest.hexdigest(),
        }
    except (OSError, tarfile.TarError) as error:
        raise VolumeSnapshotError(
            "Could not create or publish the snapshot."
        ) from error
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _extract_to_staging(archive_path: Path, staging: Path) -> int:
    """Extract only validated regular files and directories to staging."""
    members = _validate_archive(archive_path)
    member_paths = {
        member.name: _safe_member_name(member.name)
        for member in members
    }

    # Directories are created first with temporary usable permissions.
    directories = [
        member for member in members if member.isdir()
    ]
    files = [member for member in members if member.isfile()]

    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            for member in directories:
                relative = member_paths[member.name]
                output = staging.joinpath(*relative.parts)
                output.mkdir(parents=True, exist_ok=True)

            for member in files:
                relative = member_paths[member.name]
                output = staging.joinpath(*relative.parts)
                output.parent.mkdir(parents=True, exist_ok=True)

                if output.exists() or output.is_symlink():
                    raise VolumeSnapshotPathError(
                        f"Duplicate restore target: {relative.as_posix()}"
                    )

                stream = archive.extractfile(member)
                if stream is None:
                    raise VolumeSnapshotError(
                        f"Cannot read: {member.name}"
                    )

                fd = os.open(
                    output,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL
                    | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
                with os.fdopen(fd, "wb") as destination:
                    remaining = member.size
                    while remaining:
                        chunk = stream.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise VolumeSnapshotError(
                                f"Truncated member: {member.name}"
                            )
                        destination.write(chunk)
                        remaining -= len(chunk)

                if os.geteuid() == 0:
                    os.chown(output, member.uid, member.gid)
                os.chmod(output, member.mode & 0o777)

        # Apply directory ownership and modes only after files are written.
        for member in sorted(
            directories,
            key=lambda item: len(member_paths[item.name].parts),
            reverse=True,
        ):
            output = staging.joinpath(*member_paths[member.name].parts)
            if os.geteuid() == 0:
                os.chown(output, member.uid, member.gid)
            os.chmod(output, member.mode & 0o777)

        return len(members)
    except VolumeSnapshotError:
        raise
    except (OSError, tarfile.TarError) as error:
        raise VolumeSnapshotError(
            "Snapshot extraction failed."
        ) from error


def _rename_noreplace(source: Path, target: Path) -> None:
    """Atomically rename a path without replacing an existing destination.

    Linux renameat2(RENAME_NOREPLACE) is required. Fail closed if unavailable.
    """

    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise VolumeSnapshotError(
            "Safe no-replace publication is unavailable on this system."
        )

    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int

    at_fdcwd = -100
    rename_noreplace = 1

    result = renameat2(
        at_fdcwd,
        os.fsencode(source),
        at_fdcwd,
        os.fsencode(target),
        rename_noreplace,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        if error_number == errno.EEXIST:
            raise FileExistsError(
                error_number,
                "Restore target already exists.",
                str(target),
            )
        raise OSError(
            error_number,
            os.strerror(error_number),
            str(target),
        )


def restore_volume_snapshot(
    backup_directory, filename, target_directory
) -> dict:
    """Restore to staging and atomically publish to a new target path."""
    if not isinstance(filename, str) or not ARCHIVE_PATTERN.fullmatch(filename):
        raise VolumeSnapshotPathError("Invalid snapshot filename.")

    backup_dir = _require_real_directory(
        Path(backup_directory), "Backup directory"
    )

    requested_target = Path(target_directory)
    if requested_target.name in {"", ".", ".."}:
        raise VolumeSnapshotPathError("Invalid restore target.")

    if requested_target.exists() or requested_target.is_symlink():
        raise VolumeSnapshotPathError(
            "Restore target must not already exist."
        )

    parent = _require_real_directory(
        requested_target.parent, "Restore target parent"
    )
    target = parent / requested_target.name
    archive_path = backup_dir / filename

    if archive_path.is_symlink() or not archive_path.is_file():
        raise VolumeSnapshotPathError(
            "Snapshot archive must be a regular file."
        )

    # Validate the entire archive before creating staging data.
    members = _validate_archive(archive_path)

    # Non-root processes cannot restore arbitrary archived ownership.
    if os.geteuid() != 0:
        uid = os.geteuid()
        gid = os.getegid()
        if any(member.uid != uid or member.gid != gid for member in members):
            raise VolumeSnapshotError(
                "Restoring archived ownership requires root privileges."
            )

    staging = Path(tempfile.mkdtemp(
        prefix=".lums-restore-", dir=parent
    ))

    try:
        count = _extract_to_staging(archive_path, staging)

        # Do not overwrite a target that appeared while extraction ran.
        if target.exists() or target.is_symlink():
            raise VolumeSnapshotPathError(
                "Restore target appeared during restoration."
            )

        # Staging and target share a parent/filesystem. Publish the complete
        # tree with one rename rather than moving entries individually.
        _rename_noreplace(staging, target)
        staging = None

        return {
            "filename": filename,
            "entries_restored": count,
        }
    except VolumeSnapshotError:
        raise
    except OSError as error:
        raise VolumeSnapshotError(
            "Snapshot restore failed; the target was not published."
        ) from error
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
