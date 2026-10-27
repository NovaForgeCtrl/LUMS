import hashlib
import io
import tarfile

import pytest

from scripts.release_verification import (
    ReleaseArtifactError,
    verify_release_artifacts,
)


TAG = "v1.2.3"
COMMIT = "a" * 40
ARCHIVE_NAME = f"lums-source-{TAG}.tar.gz"


def make_artifacts(tmp_path, members=None, commit=COMMIT):
    archive_path = tmp_path / ARCHIVE_NAME
    checksum_path = tmp_path / f"{ARCHIVE_NAME}.sha256"
    commit_path = tmp_path / f"lums-source-{TAG}.commit"

    if members is None:
        members = [
            ("dir", f"lums-source-{TAG}/", b""),
            ("file", f"lums-source-{TAG}/README.md", b"hello LUMS\n"),
        ]

    with tarfile.open(archive_path, "w:gz") as archive:
        for kind, name, payload in members:
            info = tarfile.TarInfo(name)

            if kind == "dir":
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                archive.addfile(info)
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "../../outside"
                archive.addfile(info)
            elif kind == "hardlink":
                info.type = tarfile.LNKTYPE
                info.linkname = f"lums-source-{TAG}/README.md"
                archive.addfile(info)
            else:
                info.size = len(payload)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(payload))

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path.write_text(
        f"{digest}  {ARCHIVE_NAME}\n",
        encoding="ascii",
    )
    commit_path.write_text(commit + "\n", encoding="ascii")

    return archive_path, checksum_path, commit_path


def verify(paths, expected_commit=COMMIT):
    return verify_release_artifacts(
        *paths,
        expected_tag=TAG,
        expected_commit=expected_commit,
    )


def test_valid_artifacts_are_verified(tmp_path):
    paths = make_artifacts(tmp_path)

    result = verify(paths)

    assert result["verified"] is True
    assert result["tag"] == TAG
    assert result["commit"] == COMMIT
    assert result["sha256"] == hashlib.sha256(
        paths[0].read_bytes()
    ).hexdigest()


def test_modified_archive_fails_checksum(tmp_path):
    paths = make_artifacts(tmp_path)
    paths[0].write_bytes(paths[0].read_bytes() + b"tampered")

    with pytest.raises(ReleaseArtifactError, match="SHA-256"):
        verify(paths)


def test_wrong_checksum_filename_is_rejected(tmp_path):
    paths = make_artifacts(tmp_path)
    paths[1].write_text(
        "0" * 64 + "  some-other-file.tar.gz\n",
        encoding="ascii",
    )

    with pytest.raises(ReleaseArtifactError, match="checksum"):
        verify(paths)


def test_commit_must_match_expected_release_commit(tmp_path):
    paths = make_artifacts(tmp_path, commit="b" * 40)

    with pytest.raises(ReleaseArtifactError, match="commit"):
        verify(paths)


@pytest.mark.parametrize(
    "members",
    [
        [
            ("dir", f"lums-source-{TAG}/", b""),
            ("file", f"lums-source-{TAG}/../escape.txt", b"bad"),
        ],
        [
            ("dir", f"lums-source-{TAG}/", b""),
            ("symlink", f"lums-source-{TAG}/link", b""),
        ],
        [
            ("dir", f"lums-source-{TAG}/", b""),
            ("hardlink", f"lums-source-{TAG}/link", b""),
        ],
        [
            ("dir", f"lums-source-{TAG}/", b""),
            ("file", f"other-root/file.txt", b"bad"),
        ],
    ],
)
def test_unsafe_archive_entries_are_rejected(tmp_path, members):
    paths = make_artifacts(tmp_path, members=members)

    with pytest.raises(ReleaseArtifactError):
        verify(paths)


def test_duplicate_archive_paths_are_rejected(tmp_path):
    root = f"lums-source-{TAG}/"
    paths = make_artifacts(
        tmp_path,
        members=[
            ("dir", root, b""),
            ("file", root + "README.md", b"one"),
            ("file", root + "README.md", b"two"),
        ],
    )

    with pytest.raises(ReleaseArtifactError, match="duplicate"):
        verify(paths)


def test_invalid_expected_commit_is_rejected(tmp_path):
    paths = make_artifacts(tmp_path)

    with pytest.raises(ReleaseArtifactError, match="expected commit"):
        verify(paths, expected_commit="not-a-commit")


def test_symlink_archive_is_rejected(tmp_path):
    paths = make_artifacts(tmp_path)
    real_archive = paths[0]
    link = tmp_path / "linked-archive.tar.gz"
    link.symlink_to(real_archive)

    # Use a link with the expected filename in a separate directory.
    destination = tmp_path / "linked"
    destination.mkdir()
    linked_archive = destination / ARCHIVE_NAME
    linked_archive.symlink_to(real_archive)

    with pytest.raises(ReleaseArtifactError, match="regular"):
        verify_release_artifacts(
            linked_archive,
            paths[1],
            paths[2],
            expected_tag=TAG,
            expected_commit=COMMIT,
        )
