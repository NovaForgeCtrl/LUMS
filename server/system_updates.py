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
_FAILURE_CACHE_SECONDS = 30
_MAX_RESPONSE_BYTES = 1_000_000

_release_cache = None
_release_cache_time = 0.0
_failure_cache_message = None
_failure_cache_time = 0.0
_release_cache_lock = threading.Lock()


class ReleaseLookupError(RuntimeError):
    pass


class GitHubResponseTooLarge(ValueError):
    pass


def _github_request(url):
    return Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "LUMS-update-check",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


def _failure_message(error):
    if isinstance(error, HTTPError):
        status = error.code
        if status == 403:
            remaining = error.headers.get("X-RateLimit-Remaining", "")
            if remaining == "0":
                return (
                    "Das GitHub-API-Limit ist ausgeschöpft. "
                    "Bitte später erneut versuchen."
                )
            return (
                "GitHub hat die Anfrage mit HTTP 403 abgelehnt. "
                "Bitte später erneut versuchen."
            )
        if status == 429:
            return (
                "GitHub begrenzt momentan die Anfragen. "
                "Bitte später erneut versuchen."
            )
        if status == 404:
            return (
                "Das LUMS-Release wurde von GitHub nicht gefunden."
            )
        return f"GitHub ist momentan nicht verfügbar (HTTP {status})."

    if isinstance(error, (URLError, TimeoutError, OSError)):
        return "GitHub konnte wegen eines Netzwerkfehlers nicht abgefragt werden."

    if isinstance(error, GitHubResponseTooLarge):
        return "GitHub hat eine unerwartet große Antwort geliefert."

    if isinstance(error, (ValueError, json.JSONDecodeError)):
        return "GitHub hat keine gültige JSON-Antwort geliefert."

    return "GitHub konnte derzeit nicht abgefragt werden."


def latest_release():
    global _release_cache
    global _release_cache_time
    global _failure_cache_message
    global _failure_cache_time

    with _release_cache_lock:
        now = time.monotonic()

        if (
            _release_cache is not None
            and now - _release_cache_time < _RELEASE_CACHE_SECONDS
        ):
            return dict(_release_cache)

        if (
            _failure_cache_message is not None
            and now - _failure_cache_time < _FAILURE_CACHE_SECONDS
        ):
            raise ReleaseLookupError(_failure_cache_message)

        try:
            payload = _github_json(_github_request(RELEASES_URL))
            release = _parse_release(payload)

            commit_url = (
                f"https://api.github.com/repos/{REPOSITORY}/commits/"
                f"{quote(release['tag'], safe='')}"
            )
            commit_payload = _github_json(_github_request(commit_url))

            commit = (
                commit_payload.get("sha")
                if isinstance(commit_payload, dict)
                else None
            )
            if not isinstance(commit, str) or not re.fullmatch(
                r"[A-Fa-f0-9]{40}", commit
            ):
                raise ReleaseLookupError("Der Release-Commit ist ungültig.")

            release["commit"] = commit.lower()

        except ReleaseLookupError as error:
            _failure_cache_message = str(error)
            _failure_cache_time = time.monotonic()
            raise
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            message = _failure_message(error)
            _failure_cache_message = message
            _failure_cache_time = time.monotonic()
            raise ReleaseLookupError(message) from error

        _release_cache = release
        _release_cache_time = time.monotonic()
        _failure_cache_message = None
        _failure_cache_time = 0.0
        return dict(release)


def _github_json(request):
    with urlopen(request, timeout=8) as response:
        raw = response.read(_MAX_RESPONSE_BYTES + 1)

    if len(raw) > _MAX_RESPONSE_BYTES:
        raise GitHubResponseTooLarge(
            "GitHub response exceeds the permitted size."
        )

    payload = json.loads(raw)
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
        raise ReleaseLookupError(
            "Das GitHub-Release stammt nicht aus dem Ziel-Repository."
        )

    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise ReleaseLookupError("Die Release-Artefakte sind ungültig.")

    source_name = f"lums-source-{tag}.tar.gz"
    checksum_name = f"{source_name}.sha256"
    commit_name = f"lums-source-{tag}.commit"

    found = {}
    expected_names = {source_name, checksum_name, commit_name}

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        if isinstance(name, str) and name in expected_names:
            if name in found:
                raise ReleaseLookupError(
                    "Das Release enthält doppelte Artefaktnamen."
                )
            found[name] = asset

    if set(found) != expected_names:
        raise ReleaseLookupError(
            "Dieses Release ist noch nicht vollständig getestet und verpackt."
        )

    return {
        "tag": tag,
        "name": str(payload.get("name") or tag)[:200],
        "published_at": payload.get("published_at"),
        "url": payload.get("html_url"),
        "notes": str(payload.get("body") or "")[:20_000],
        "source_asset": _trusted_asset_url(found[source_name], tag, source_name),
        "checksum_asset": _trusted_asset_url(
            found[checksum_name], tag, checksum_name
        ),
        "commit_asset": _trusted_asset_url(
            found[commit_name], tag, commit_name
        ),
        "source_name": source_name,
    }


def _trusted_asset_url(asset, tag, name):
    url = asset.get("browser_download_url")
    expected = (
        f"https://github.com/{REPOSITORY}/releases/download/{tag}/{name}"
    )
    if url != expected:
        raise ReleaseLookupError("Ein Release-Artefakt hat eine ungültige URL.")
    return url
