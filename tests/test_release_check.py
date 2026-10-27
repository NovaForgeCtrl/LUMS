import hashlib
import io
import json
import tarfile
from contextlib import contextmanager
from urllib.parse import urlparse

import pytest

from scripts import release_check as check


TAG = "v1.2.3"
COMMIT = "a" * 40
ARCHIVE_NAME = f"lums-source-{TAG}.tar.gz"
CHECKSUM_NAME = f"{ARCHIVE_NAME}.sha256"
COMMIT_NAME = f"lums-source-{TAG}.commit"


def build_archive():
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        root = tarfile.TarInfo(f"lums-source-{TAG}/")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)

        readme = b"verified test source\n"
        info = tarfile.TarInfo(f"lums-source-{TAG}/README.md")
        info.size = len(readme)
        archive.addfile(info, io.BytesIO(readme))
    return buffer.getvalue()


def release_payload():
    names = (ARCHIVE_NAME, CHECKSUM_NAME, COMMIT_NAME)
    return {
        "draft": False,
        "prerelease": False,
        "tag_name": TAG,
        "html_url": f"https://github.com/{check.REPOSITORY}/releases/tag/{TAG}",
        "assets": [
            {
                "name": name,
                "browser_download_url": (
                    f"https://github.com/{check.REPOSITORY}/releases/download/{TAG}/{name}"
                ),
            }
            for name in names
        ],
    }


def fake_response(data):
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    return Response(data)


def test_verify_latest_release_downloads_and_verifies_without_extracting(monkeypatch):
    archive = build_archive()
    checksum = f"{hashlib.sha256(archive).hexdigest()}  {ARCHIVE_NAME}\n".encode()
    bodies = {
        check.LATEST_URL: json.dumps(release_payload()).encode(),
        f"{check.API_ROOT}/commits/{TAG}": json.dumps({"sha": COMMIT}).encode(),
        f"https://github.com/{check.REPOSITORY}/releases/download/{TAG}/{ARCHIVE_NAME}": archive,
        f"https://github.com/{check.REPOSITORY}/releases/download/{TAG}/{CHECKSUM_NAME}": checksum,
        f"https://github.com/{check.REPOSITORY}/releases/download/{TAG}/{COMMIT_NAME}": (COMMIT + "\n").encode(),
    }
    requests = []

    def fake_open(url):
        requests.append(url)
        return fake_response(bodies[url])

    monkeypatch.setattr(check, "_open_url", fake_open)
    result = check.verify_latest_release()

    assert result["verified"] is True
    assert result["tag"] == TAG
    assert result["commit"] == COMMIT
    assert len(requests) == 5


def test_release_parser_rejects_wrong_repository_url():
    payload = release_payload()
    payload["html_url"] = "https://github.com/attacker/repo/releases/tag/v1.2.3"

    with pytest.raises(check.ReleaseCheckError, match="release URL"):
        check._parse_release(payload)


def test_release_parser_rejects_duplicate_asset_names():
    payload = release_payload()
    payload["assets"].append(payload["assets"][0])

    with pytest.raises(check.ReleaseCheckError, match="Duplicate"):
        check._parse_release(payload)


def test_release_parser_rejects_untrusted_asset_url():
    payload = release_payload()
    payload["assets"][0]["browser_download_url"] = "https://attacker.invalid/source.tar.gz"

    with pytest.raises(check.ReleaseCheckError, match="not trusted"):
        check._parse_release(payload)


def test_release_parser_rejects_prerelease():
    payload = release_payload()
    payload["prerelease"] = True

    with pytest.raises(check.ReleaseCheckError, match="prerelease"):
        check._parse_release(payload)


def test_redirect_handler_rejects_plain_http():
    handler = check.SafeRedirectHandler()
    request = check.Request("https://github.com/example")
    with pytest.raises(check.ReleaseCheckError, match="untrusted"):
        handler.redirect_request(
            request, None, 302, "Found", {}, "http://attacker.invalid/file"
        )


def test_download_enforces_size_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(
        check,
        "_open_url",
        lambda url: fake_response(b"0123456789"),
    )
    target = tmp_path / "too-large.bin"

    with pytest.raises(check.ReleaseCheckError, match="size limit"):
        check._download("https://github.com/example", target, 5)


def test_download_rejects_existing_destination(monkeypatch, tmp_path):
    monkeypatch.setattr(
        check,
        "_open_url",
        lambda url: fake_response(b"new"),
    )
    target = tmp_path / "existing.bin"
    target.write_bytes(b"original")

    with pytest.raises(check.ReleaseCheckError):
        check._download("https://github.com/example", target, 10)

    assert target.read_bytes() == b"original"
