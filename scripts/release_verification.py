"""Fail-closed verification of downloaded LUMS release source artifacts."""

import hashlib
import os
import re
import stat
import tarfile
from pathlib import Path, PurePosixPath


MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 50_000
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_TOTAL_UNPACKED_BYTES = 500 * 1024 * 1024
MAX_CHECKSUM_BYTES = 4096
MAX_COMMIT_BYTES = 256


class ReleaseArtifactError(ValueError):
    """Raised when a release artifact cannot be trusted."""


def _regular_file(path, maximum_size, label):
    path = Path(path)

    try:
        metadata = path.lstat()
    except OSError as error:
        raise ReleaseArtifactError(
            f"{label} is unavailable."
        ) from error

    if not stat.S_ISREG(metadata.st_mode):
        raise ReleaseArtifactError(
            f"{label} must be a regular, non-symlink file."
        )

    if metadata.st_size > maximum_size:
        raise ReleaseArtifactError(
            f"{label} exceeds its permitted size."
        )

    return path


def _sha256(path):
    digest = hashlib.sha256()

    try:
        with path.open("rb") as stream:
            for chunk in iter(
                lambda: stream.read(1024 * 1024), b""
            ):
                digest.update(chunk)
    except OSError as error:
        raise ReleaseArtifactError(
            "The source archive could not be read."
        ) from error

    return digest.hexdigest()


def _safe_member_path(name):
    if (
        not isinstance(name, str)
        or not name
        or "\x00" in name
        or "\\" in name
    ):
        raise ReleaseArtifactError(
            "The source archive contains an invalid path."
        )

    # Tar directory names conventionally end with one slash.
    canonical = name[:-1] if name.endswith("/") else name

    if not canonical:
        raise ReleaseArtifactError(
            "The source archive contains an empty path."
        )

    parts = canonical.split("/")

    if (
        canonical.startswith("/")
        or any(part in ("", ".", "..") for part in parts)
    ):
        raise ReleaseArtifactError(
            "The source archive contains an unsafe path."
        )

    path = PurePosixPath(canonical)

    if path.is_absolute():
        raise ReleaseArtifactError(
            "The source archive contains an absolute path."
        )

    return path


def _validate_tar_archive(archive_path, expected_root):
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = []

            for member in archive:
                members.append(member)

                if len(members) > MAX_ARCHIVE_MEMBERS:
                    raise ReleaseArtifactError(
                        "The source archive contains too many entries."
                    )

            if not members:
                raise ReleaseArtifactError(
                    "The source archive is empty."
                )

            kinds = {}
            total_bytes = 0

            for member in members:
                path = _safe_member_path(member.name)
                name = path.as_posix()

                if name in kinds:
                    raise ReleaseArtifactError(
                        "The source archive contains duplicate paths."
                    )

                if path.parts[0] != expected_root:
                    raise ReleaseArtifactError(
                        "The source archive has an unexpected root directory."
                    )

                # Only ordinary files and directories are accepted.
                # In particular, symlinks and hard links are rejected.
                if member.isdir():
                    kind = "directory"
                elif member.isfile():
                    kind = "file"
                else:
                    raise ReleaseArtifactError(
                        "The source archive contains an unsupported entry type."
                    )

                if member.size < 0:
                    raise ReleaseArtifactError(
                        "The source archive contains an invalid file size."
                    )

                if kind == "file":
                    if member.size > MAX_FILE_BYTES:
                        raise ReleaseArtifactError(
                            "A source file exceeds the permitted size."
                        )

                    total_bytes += member.size

                    if total_bytes > MAX_TOTAL_UNPACKED_BYTES:
                        raise ReleaseArtifactError(
                            "The expanded source archive is too large."
                        )

                kinds[name] = kind

            root_kind = kinds.get(expected_root)

            if root_kind != "directory":
                raise ReleaseArtifactError(
                    "The expected source root directory is missing."
                )

            # Every parent directory must be explicitly represented.
            for name, kind in kinds.items():
                path = PurePosixPath(name)

                for index in range(1, len(path.parts)):
                    parent = PurePosixPath(
                        *path.parts[:index]
                    ).as_posix()

                    if kinds.get(parent) != "directory":
                        raise ReleaseArtifactError(
                            "The source archive has an invalid directory structure."
                        )

                if name != expected_root and kind not in (
                    "file",
                    "directory",
                ):
                    raise ReleaseArtifactError(
                        "The source archive contains an unsupported entry."
                    )

            # Read every payload so truncated or corrupt gzip/tar content
            # cannot pass merely because the member headers look valid.
            for member in members:
                if not member.isfile():
                    continue

                stream = archive.extractfile(member)

                if stream is None:
                    raise ReleaseArtifactError(
                        "A source archive member cannot be read."
                    )

                remaining = member.size

                while remaining:
                    chunk = stream.read(
                        min(1024 * 1024, remaining)
                    )

                    if not chunk:
                        raise ReleaseArtifactError(
                            "The source archive contains truncated content."
                        )

                    remaining -= len(chunk)

                if stream.read(1):
                    raise ReleaseArtifactError(
                        "A source archive member exceeds its declared size."
                    )

    except ReleaseArtifactError:
        raise
    except (
        OSError,
        EOFError,
        tarfile.TarError,
    ) as error:
        raise ReleaseArtifactError(
            "The source archive is unreadable or corrupt."
        ) from error


def verify_release_artifacts(
    archive_path,
    checksum_path,
    commit_path,
    expected_tag,
    expected_commit,
):
    """Verify the archive, its published checksum, commit and structure.

    This function only reads local files. It does not download, extract,
    install, execute or deploy the release.
    """
    if not isinstance(expected_tag, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}",
        expected_tag,
    ):
        raise ReleaseArtifactError("The expected release tag is invalid.")

    if not isinstance(expected_commit, str) or not re.fullmatch(
        r"[A-Fa-f0-9]{40}",
        expected_commit,
    ):
        raise ReleaseArtifactError("The expected commit is invalid.")

    archive_name = f"lums-source-{expected_tag}.tar.gz"
    checksum_name = f"{archive_name}.sha256"
    root_name = f"lums-source-{expected_tag}"

    archive = _regular_file(
        archive_path, MAX_ARCHIVE_BYTES, "Source archive"
    )
    checksum = _regular_file(
        checksum_path, MAX_CHECKSUM_BYTES, "Checksum file"
    )
    commit_file = _regular_file(
        commit_path, MAX_COMMIT_BYTES, "Commit file"
    )

    if archive.name != archive_name:
        raise ReleaseArtifactError(
            "The source archive filename does not match the release tag."
        )

    if checksum.name != checksum_name:
        raise ReleaseArtifactError(
            "The checksum filename does not match the release tag."
        )

    try:
        checksum_text = checksum.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as error:
        raise ReleaseArtifactError(
            "The checksum file is unreadable."
        ) from error

    # Matches the two-column output generated by sha256sum.
    checksum_match = re.fullmatch(
        r"([A-Fa-f0-9]{64})[ \t]+(\*?[^ \t\r\n]+)",
        checksum_text,
    )

    if not checksum_match:
        raise ReleaseArtifactError(
            "The checksum file has an invalid format."
        )

    declared_digest, declared_filename = checksum_match.groups()

    if declared_filename.removeprefix("*") != archive_name:
        raise ReleaseArtifactError(
            "The checksum refers to a different source archive."
        )

    actual_digest = _sha256(archive)

    if actual_digest != declared_digest.lower():
        raise ReleaseArtifactError(
            "The source archive SHA-256 checksum does not match."
        )

    try:
        commit_text = commit_file.read_text(
            encoding="ascii"
        ).strip()
    except (OSError, UnicodeError) as error:
        raise ReleaseArtifactError(
            "The commit file is unreadable."
        ) from error

    if not re.fullmatch(r"[A-Fa-f0-9]{40}", commit_text):
        raise ReleaseArtifactError(
            "The commit file contains an invalid commit."
        )

    if commit_text.lower() != expected_commit.lower():
        raise ReleaseArtifactError(
            "The source archive commit does not match the expected release commit."
        )

    _validate_tar_archive(archive, root_name)

    return {
        "tag": expected_tag,
        "commit": expected_commit.lower(),
        "sha256": actual_digest,
        "archive_name": archive_name,
        "verified": True,
    }
