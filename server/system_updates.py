import json
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


REPOSITORY = "NovaForgeCtrl/LUMS"
RELEASES_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
_RELEASE_CACHE_SECONDS = 300
_release_cache = None
_release_cache_time = 0.0
_release_cache_lock = threading.Lock()


class ReleaseLookupError(RuntimeError):
    pass


def latest_release():
    global _release_cache, _release_cache_time

    with _release_cache_lock:
        if (
            _release_cache is not None
            and time.monotonic() - _release_cache_time < _RELEASE_CACHE_SECONDS
        ):
            return dict(_release_cache)

        request = Request(
            RELEASES_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "LUMS-update-check",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            payload = _github_json(request)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            raise ReleaseLookupError(
                "GitHub konnte derzeit nicht abgefragt werden."
            ) from error

        release = _parse_release(payload)
        commit_request = Request(
            (
                f"https://api.github.com/repos/{REPOSITORY}/commits/"
                f"{quote(release['tag'], safe='')}"
            ),
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "LUMS-update-check",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            commit_payload = _github_json(commit_request)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            raise ReleaseLookupError(
                "Der Release-Commit konnte nicht verifiziert werden."
            ) from error
        commit = commit_payload.get("sha") if isinstance(
            commit_payload, dict
        ) else None
        if not isinstance(commit, str) or not re.fullmatch(
            r"[A-Fa-f0-9]{40}", commit
        ):
            raise ReleaseLookupError("Der Release-Commit ist ungültig.")
        release["commit"] = commit.lower()
        _release_cache = release
        _release_cache_time = time.monotonic()
        return dict(release)


def _github_json(request):
    with urlopen(request, timeout=8) as response:
        payload = json.loads(response.read(1_000_001))
    if not isinstance(payload, dict):
        raise ValueError("GitHub returned an invalid response.")
    return payload


def _parse_release(payload):
    if not isinstance(payload, dict) or payload.get("draft") or payload.get(
        "prerelease"
    ):
        raise ReleaseLookupError("Es ist kein stabiles LUMS-Release verfügbar.")

    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", tag
    ):
        raise ReleaseLookupError("Das GitHub-Release hat einen ungültigen Tag.")
    expected_release_url = (
        f"https://github.com/{REPOSITORY}/releases/tag/{tag}"
    )
    if payload.get("html_url") != expected_release_url:
        raise ReleaseLookupError("Das GitHub-Release stammt nicht aus dem Ziel-Repository.")

    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise ReleaseLookupError("Die Release-Artefakte sind ungültig.")

    source_name = f"lums-source-{tag}.tar.gz"
    checksum_name = f"{source_name}.sha256"
    commit_name = f"lums-source-{tag}.commit"
    source_asset = None
    checksum_asset = None
    commit_asset = None
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if asset.get("name") == source_name:
            source_asset = asset
        elif asset.get("name") == checksum_name:
            checksum_asset = asset
        elif asset.get("name") == commit_name:
            commit_asset = asset

    if (
        source_asset is None
        or checksum_asset is None
        or commit_asset is None
    ):
        raise ReleaseLookupError(
            "Dieses Release ist noch nicht vollständig getestet und verpackt."
        )

    return {
        "tag": tag,
        "name": str(payload.get("name") or tag)[:200],
        "published_at": payload.get("published_at"),
        "url": payload.get("html_url"),
        "notes": str(payload.get("body") or "")[:20_000],
        "source_asset": _trusted_asset_url(source_asset, tag, source_name),
        "checksum_asset": _trusted_asset_url(
            checksum_asset, tag, checksum_name
        ),
        "commit_asset": _trusted_asset_url(commit_asset, tag, commit_name),
        "source_name": source_name,
    }


def _trusted_asset_url(asset, tag, name):
    url = asset.get("browser_download_url")
    expected = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{name}"
    if url != expected:
        raise ReleaseLookupError("Ein Release-Artefakt hat eine ungültige URL.")
    return url
