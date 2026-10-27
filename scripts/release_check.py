#!/usr/bin/env python3
"""Download and verify a LUMS release without installing or deploying it."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

# Support both repository imports (scripts.release_check) and the
# standalone updater package, where both modules share the scripts directory.
try:
    from .release_verification import (
        ReleaseArtifactError,
        verify_release_artifacts,
    )
except ImportError:
    from release_verification import (
        ReleaseArtifactError,
        verify_release_artifacts,
    )

REPOSITORY = "NovaForgeCtrl/LUMS"
API_ROOT = f"https://api.github.com/repos/{REPOSITORY}"
LATEST_URL = f"{API_ROOT}/releases/latest"
MAX_JSON_BYTES = 1_000_000
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_CHECKSUM_BYTES = 4096
MAX_COMMIT_BYTES = 256
CHUNK_BYTES = 1024 * 1024
USER_AGENT = "LUMS-release-verifier"


class ReleaseCheckError(RuntimeError):
    """A release could not be downloaded and verified safely."""


class SafeRedirectHandler(HTTPRedirectHandler):
    """Permit HTTPS redirects only to the GitHub asset delivery hosts."""

    allowed_hosts = {
        "github.com",
        "release-assets.githubusercontent.com",
        "objects.githubusercontent.com",
    }

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in self.allowed_hosts
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise ReleaseCheckError("A release download redirected to an untrusted URL.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_url(url):
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"api.github.com", "github.com"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise ReleaseCheckError("Refusing a URL outside the configured HTTPS GitHub hosts.")

    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    opener = build_opener(SafeRedirectHandler())
    return opener.open(request, timeout=15)


def _fetch_json(url):
    try:
        with _open_url(url) as response:
            raw = response.read(MAX_JSON_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise ReleaseCheckError("Could not fetch GitHub release metadata.") from error

    if len(raw) > MAX_JSON_BYTES:
        raise ReleaseCheckError("GitHub metadata exceeded the permitted size.")

    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise ReleaseCheckError("GitHub returned invalid JSON.") from error

    if not isinstance(value, dict):
        raise ReleaseCheckError("GitHub returned an invalid metadata object.")
    return value


def _parse_release(payload):
    if payload.get("draft") is True or payload.get("prerelease") is True:
        raise ReleaseCheckError("Draft and prerelease releases are not accepted.")

    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", tag
    ):
        raise ReleaseCheckError("The release tag is invalid.")

    if payload.get("html_url") != (
        f"https://github.com/{REPOSITORY}/releases/tag/{tag}"
    ):
        raise ReleaseCheckError("The release URL does not match the configured repository.")

    names = {
        f"lums-source-{tag}.tar.gz",
        f"lums-source-{tag}.tar.gz.sha256",
        f"lums-source-{tag}.commit",
    }
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise ReleaseCheckError("Release assets are missing.")

    found = {}
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        if name in names:
            if name in found:
                raise ReleaseCheckError("Duplicate release asset names were found.")
            found[name] = asset

    if set(found) != names:
        raise ReleaseCheckError("The release does not contain all required artifacts.")

    urls = {}
    for name in names:
        expected = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{name}"
        if found[name].get("browser_download_url") != expected:
            raise ReleaseCheckError("A release asset URL is not trusted.")
        urls[name] = expected

    return tag, urls


def _download(url, destination, maximum_size):
    total = 0
    try:
        with _open_url(url) as response, Path(destination).open("xb") as output:
            while True:
                chunk = response.read(min(CHUNK_BYTES, maximum_size + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum_size:
                    raise ReleaseCheckError("A release artifact exceeded its size limit.")
                output.write(chunk)
            output.flush()
    except ReleaseCheckError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise ReleaseCheckError("A release artifact could not be downloaded safely.") from error

    if total == 0:
        raise ReleaseCheckError("A release artifact was empty.")


def verify_latest_release():
    """Download into a temporary directory and verify; never extract or install."""
    payload = _fetch_json(LATEST_URL)
    tag, urls = _parse_release(payload)

    if payload.get("draft") is True or payload.get("prerelease") is True:
        raise ReleaseCheckError("The latest release is not stable.")

    commit_payload = _fetch_json(
        f"{API_ROOT}/commits/{tag}"
    )
    commit = commit_payload.get("sha")
    if not isinstance(commit, str) or not re.fullmatch(r"[A-Fa-f0-9]{40}", commit):
        raise ReleaseCheckError("The expected release commit is invalid.")

    archive_name = f"lums-source-{tag}.tar.gz"
    checksum_name = f"{archive_name}.sha256"
    commit_name = f"lums-source-{tag}.commit"

    with tempfile.TemporaryDirectory(prefix="lums-release-check-") as temporary:
        directory = Path(temporary)
        archive = directory / archive_name
        checksum = directory / checksum_name
        commit_file = directory / commit_name

        _download(urls[archive_name], archive, MAX_ARCHIVE_BYTES)
        _download(urls[checksum_name], checksum, MAX_CHECKSUM_BYTES)
        _download(urls[commit_name], commit_file, MAX_COMMIT_BYTES)

        try:
            result = verify_release_artifacts(
                archive,
                checksum,
                commit_file,
                expected_tag=tag,
                expected_commit=commit.lower(),
            )
        except ReleaseArtifactError as error:
            raise ReleaseCheckError(
                "Release artifact verification failed; release rejected."
            ) from error

    return result


def main():
    try:
        result = verify_latest_release()
    except (ReleaseCheckError, ReleaseArtifactError) as error:
        print(f"Release verification FAILED: {error}", file=sys.stderr)
        return 1

    print("Release verification PASSED")
    print(f"Tag:    {result['tag']}")
    print(f"Commit: {result['commit']}")
    print(f"SHA256: {result['sha256']}")
    print("No archive was extracted. Nothing was installed or deployed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
