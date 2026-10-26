import io
import os
import tarfile
from pathlib import Path

import pytest

from scripts.volume_snapshot import (
    VolumeSnapshotError,
    VolumeSnapshotPathError,
    create_volume_snapshot,
    restore_volume_snapshot,
)


def _write_test_tree(root: Path) -> None:
    (root / "nested").mkdir()
    (root / "lums.db").write_bytes(b"test-database-state")
    (root / "nested" / "copy.db").write_bytes(b"other-db-copy")
    (root / "nested" / "wal").write_bytes(b"")
    (root / "lums.db").chmod(0o640)


def test_snapshot_restore_round_trip_preserves_files_and_modes(tmp_path):
    source = tmp_path / "source"
    backups = tmp_path / "backups"
    target = tmp_path / "target"
    source.mkdir()
    backups.mkdir()
    _write_test_tree(source)

    original = {
        path.relative_to(source).as_posix(): (
            path.read_bytes(),
            path.stat().st_mode & 0o777,
            path.stat().st_uid,
            path.stat().st_gid,
        )
        for path in source.rglob("*")
        if path.is_file()
    }

    result = create_volume_snapshot(source, backups)
    archive = backups / result["filename"]
    assert archive.is_file()
    assert result["size_bytes"] == archive.stat().st_size
    assert len(result["sha256"]) == 64

    restored = restore_volume_snapshot(
        backups, result["filename"], target
    )
    assert restored["entries_restored"] >= len(original)

    actual = {
        path.relative_to(target).as_posix(): (
            path.read_bytes(),
            path.stat().st_mode & 0o777,
            path.stat().st_uid,
            path.stat().st_gid,
        )
        for path in target.rglob("*")
        if path.is_file()
    }
    assert actual == original

    # Snapshotting never changes the source tree.
    for relative, (content, mode, uid, gid) in original.items():
        path = source / relative
        assert path.read_bytes() == content
        assert path.stat().st_mode & 0o777 == mode
        assert path.stat().st_uid == uid
        assert path.stat().st_gid == gid


def test_snapshot_rejects_backup_directory_inside_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    backups = source / "backups"
    backups.mkdir()

    with pytest.raises(VolumeSnapshotPathError):
        create_volume_snapshot(source, backups)


def test_snapshot_rejects_symlink_in_source(tmp_path):
    source = tmp_path / "source"
    backups = tmp_path / "backups"
    source.mkdir()
    backups.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("do not follow")
    (source / "link").symlink_to(outside)

    with pytest.raises(VolumeSnapshotPathError):
        create_volume_snapshot(source, backups)

    assert list(backups.iterdir()) == []


def test_restore_rejects_nonempty_target_without_overwriting(tmp_path):
    source = tmp_path / "source"
    backups = tmp_path / "backups"
    target = tmp_path / "target"
    source.mkdir()
    backups.mkdir()
    _write_test_tree(source)
    result = create_volume_snapshot(source, backups)
    target.mkdir()
    (target / "keep.txt").write_text("preserve me")

    with pytest.raises(VolumeSnapshotPathError):
        restore_volume_snapshot(backups, result["filename"], target)

    assert (target / "keep.txt").read_text() == "preserve me"


def test_restore_rejects_corrupt_archive_before_writing(tmp_path):
    backups = tmp_path / "backups"
    target = tmp_path / "target"
    backups.mkdir()
    filename = "lums-volume-20261026T120000.000000Z-0123456789abcdef.tar.gz"
    (backups / filename).write_bytes(b"not a tar archive")

    with pytest.raises(VolumeSnapshotError):
        restore_volume_snapshot(backups, filename, target)

    assert not target.exists()


def test_restore_rejects_path_traversal_before_writing(tmp_path):
    backups = tmp_path / "backups"
    target = tmp_path / "target"
    backups.mkdir()
    filename = "lums-volume-20261026T120000.000000Z-0123456789abcdef.tar.gz"

    with tarfile.open(backups / filename, "w:gz") as archive:
        data = b"must not escape"
        member = tarfile.TarInfo("../escaped.txt")
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))

    with pytest.raises(VolumeSnapshotPathError):
        restore_volume_snapshot(backups, filename, target)

    assert not target.exists()
    assert not (tmp_path / "escaped.txt").exists()


def test_restore_rejects_symlink_archive(tmp_path):
    backups = tmp_path / "backups"
    target = tmp_path / "target"
    backups.mkdir()
    real_archive = backups / "real.tar.gz"
    real_archive.write_bytes(b"not used")
    filename = "lums-volume-20261026T120000.000000Z-0123456789abcdef.tar.gz"
    (backups / filename).symlink_to(real_archive)

    with pytest.raises(VolumeSnapshotPathError):
        restore_volume_snapshot(backups, filename, target)

    assert not target.exists()


def test_restore_rejects_file_as_parent_directory(tmp_path):
    backups = tmp_path / "backups"
    target = tmp_path / "target"
    backups.mkdir()
    filename = "lums-volume-20261026T120000.000000Z-0123456789abcdef.tar.gz"

    with tarfile.open(backups / filename, "w:gz") as archive:
        data = b"parent is a file"
        parent = tarfile.TarInfo("nested")
        parent.size = len(data)
        archive.addfile(parent, io.BytesIO(data))

        child = tarfile.TarInfo("nested/child.txt")
        child.size = 1
        archive.addfile(child, io.BytesIO(b"x"))

    with pytest.raises(VolumeSnapshotPathError):
        restore_volume_snapshot(backups, filename, target)

    assert not target.exists()


def test_restore_rejects_missing_parent_directory_entry(tmp_path):
    backups = tmp_path / "backups"
    target = tmp_path / "target"
    backups.mkdir()
    filename = "lums-volume-20261026T120000.000000Z-0123456789abcdef.tar.gz"

    with tarfile.open(backups / filename, "w:gz") as archive:
        data = b"orphaned path"
        member = tarfile.TarInfo("missing/child.txt")
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))

    # Archives created by create_volume_snapshot include every directory.
    # A hand-crafted archive with an absent parent must be rejected.
    with pytest.raises(VolumeSnapshotPathError):
        restore_volume_snapshot(backups, filename, target)

    assert not target.exists()


def test_restore_publish_failure_cleans_staging_and_leaves_target_absent(
    tmp_path, monkeypatch
):
    import scripts.volume_snapshot as snapshot_module

    source = tmp_path / "source"
    backups = tmp_path / "backups"
    parent = tmp_path / "restore-parent"
    target = parent / "restored-volume"

    source.mkdir()
    backups.mkdir()
    parent.mkdir()
    _write_test_tree(source)

    result = create_volume_snapshot(source, backups)
    original_publish = snapshot_module._rename_noreplace

    def fail_staging_publish(src, dst):
        if Path(dst) == target:
            raise OSError("simulated publish failure")
        return original_publish(src, dst)

    monkeypatch.setattr(
        snapshot_module, "_rename_noreplace", fail_staging_publish
    )

    with pytest.raises(VolumeSnapshotError):
        restore_volume_snapshot(backups, result["filename"], target)

    assert not target.exists()
    assert list(parent.glob(".lums-restore-*")) == []
    assert (source / "lums.db").read_bytes() == b"test-database-state"


def test_restore_rejects_foreign_ownership_without_root(
    tmp_path, monkeypatch
):
    import scripts.volume_snapshot as snapshot_module

    if os.geteuid() == 0:
        pytest.skip("Test requires an unprivileged process.")

    source = tmp_path / "source"
    backups = tmp_path / "backups"
    parent = tmp_path / "restore-parent"
    target = parent / "restored-volume"

    source.mkdir()
    backups.mkdir()
    parent.mkdir()
    _write_test_tree(source)

    result = create_volume_snapshot(source, backups)
    archive_path = backups / result["filename"]

    # Rewrite a valid archive with a foreign owner on one regular file.
    rewritten = backups / "rewritten.tar.gz"
    with tarfile.open(archive_path, "r:gz") as original:
        with tarfile.open(rewritten, "w:gz") as output:
            for member in original.getmembers():
                stream = original.extractfile(member) if member.isfile() else None
                info = tarfile.TarInfo(member.name)
                info.type = member.type
                info.mode = member.mode
                info.uid = member.uid
                info.gid = member.gid
                info.mtime = member.mtime
                info.size = member.size
                if member.isfile() and member.name == "lums.db":
                    info.uid = os.geteuid() + 1
                output.addfile(info, stream)

    # Use the valid archive's required filename pattern for the rewritten copy.
    rewritten_name = "lums-volume-20261026T120000.000000Z-abcdef0123456789.tar.gz"
    renamed = backups / rewritten_name
    rewritten.rename(renamed)

    with pytest.raises(VolumeSnapshotError, match="requires root privileges"):
        restore_volume_snapshot(backups, rewritten_name, target)

    assert not target.exists()
    assert list(parent.glob(".lums-restore-*")) == []


def test_restore_does_not_replace_target_created_before_publish(
    tmp_path, monkeypatch
):
    import scripts.volume_snapshot as snapshot_module

    source = tmp_path / "source"
    backups = tmp_path / "backups"
    parent = tmp_path / "restore-parent"
    target = parent / "restored-volume"

    source.mkdir()
    backups.mkdir()
    parent.mkdir()
    _write_test_tree(source)

    result = create_volume_snapshot(source, backups)
    original_publish = snapshot_module._rename_noreplace
    injected = False

    def create_target_before_publish(src, dst):
        nonlocal injected
        if Path(dst) == target and not injected:
            injected = True
            target.mkdir()
        return original_publish(src, dst)

    monkeypatch.setattr(
        snapshot_module, "_rename_noreplace", create_target_before_publish
    )

    with pytest.raises(VolumeSnapshotError):
        restore_volume_snapshot(backups, result["filename"], target)

    assert target.is_dir()
    assert list(target.iterdir()) == []
    assert list(parent.glob(".lums-restore-*")) == []


@pytest.mark.parametrize("limit_case", ["count", "file_size", "total_size"])
def test_restore_rejects_archives_over_configured_limits(
    tmp_path, monkeypatch, limit_case
):
    import scripts.volume_snapshot as snapshot_module

    backups = tmp_path / "backups"
    parent = tmp_path / "restore-parent"
    backups.mkdir()
    parent.mkdir()

    monkeypatch.setattr(snapshot_module, "MAX_ARCHIVE_MEMBERS", 1)
    monkeypatch.setattr(snapshot_module, "MAX_FILE_BYTES", 4)
    monkeypatch.setattr(snapshot_module, "MAX_TOTAL_BYTES", 5)

    filename = "lums-volume-20261026T120000.000000Z-0123456789abcdef.tar.gz"
    archive_path = backups / filename

    if limit_case == "count":
        entries = [("a", b""), ("b", b"")]
    elif limit_case == "file_size":
        entries = [("a", b"12345")]
    else:
        entries = [("a", b"123"), ("b", b"456")]

    with tarfile.open(archive_path, "w:gz") as archive:
        for name, payload in entries:
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))

    with pytest.raises(VolumeSnapshotError, match="limit"):
        restore_volume_snapshot(
            backups, filename, parent / "restored"
        )

    assert not (parent / "restored").exists()
    assert list(parent.iterdir()) == []


def test_snapshot_rejects_source_tree_changed_during_creation(
    tmp_path, monkeypatch
):
    import scripts.volume_snapshot as snapshot_module

    source = tmp_path / "source"
    backups = tmp_path / "backups"
    source.mkdir()
    backups.mkdir()
    _write_test_tree(source)

    original_signature = snapshot_module._source_tree_signature
    calls = 0

    def change_source_after_archive(path):
        nonlocal calls
        calls += 1
        if calls == 2:
            (path / "added-during-snapshot.txt").write_text("changed")
        return original_signature(path)

    monkeypatch.setattr(
        snapshot_module, "_source_tree_signature", change_source_after_archive
    )

    with pytest.raises(VolumeSnapshotError, match="changed during snapshot"):
        create_volume_snapshot(source, backups)

    assert list(backups.iterdir()) == []
