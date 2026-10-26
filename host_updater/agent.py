#!/usr/bin/env python3
"""Minimal LUMS host-updater heartbeat agent. Never executes updates."""

import json
import logging
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

LOG = logging.getLogger("lums-host-updater")
MAX_INTERVAL = 300
MIN_INTERVAL = 10
TIMEOUT = 5


def read_token():
    """Read the token from a systemd credential or an explicit file."""
    credentials_dir = os.environ.get("CREDENTIALS_DIRECTORY")
    if credentials_dir:
        path = Path(credentials_dir) / "host-updater-token"
    else:
        path = Path(os.environ.get(
            "LUMS_HOST_UPDATER_TOKEN_FILE",
            "/etc/lums-host-updater/token",
        ))

    token = path.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise ValueError("Host-updater token is missing or too short")
    return token


def build_request(base_url, token, version, deployment, status_message):
    base_url = base_url.rstrip("/")
    try:
        parsed_url = urlsplit(base_url)
        valid_port = parsed_url.port is not None
    except ValueError as exc:
        raise ValueError("Invalid LUMS endpoint URL") from exc

    if (
        parsed_url.scheme not in ("http", "https")
        or parsed_url.hostname != "127.0.0.1"
        or not valid_port
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ValueError("Only a loopback LUMS endpoint is permitted")

    payload = json.dumps({
        "version": version[:80],
        "deployment": deployment[:80],
        "status_message": status_message[:500],
    }).encode("utf-8")

    return Request(
        base_url + "/api/host-updater/heartbeat",
        data=payload,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )


def send_heartbeat(base_url, token, version, deployment, status_message,
                   opener=None):
    request = build_request(
        base_url, token, version, deployment, status_message
    )
    open_url = opener or urlopen
    with open_url(request, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise RuntimeError(
                f"Heartbeat returned HTTP {response.status}"
            )
        return json.loads(response.read(4096).decode("utf-8"))


def run():
    base_url = os.environ.get(
        "LUMS_HOST_UPDATER_URL", "http://127.0.0.1:5050"
    )
    version = os.environ.get("LUMS_HOST_UPDATER_VERSION", "unknown")
    deployment = os.environ.get(
        "LUMS_HOST_UPDATER_DEPLOYMENT", "host"
    )
    try:
        interval = int(os.environ.get(
            "LUMS_HOST_UPDATER_INTERVAL", "30"
        ))
    except ValueError:
        interval = 30
    interval = max(MIN_INTERVAL, min(MAX_INTERVAL, interval))

    LOG.info("Host updater started; update execution is disabled")

    while True:
        try:
            token = read_token()
            result = send_heartbeat(
                base_url, token, version, deployment,
                "Heartbeat received; update execution disabled",
            )
            if result.get("update_execution_enabled") is not False:
                LOG.error("Unexpected update-execution state; stopping")
                return 1
            LOG.info("Heartbeat accepted")
        except (OSError, ValueError, RuntimeError, HTTPError, URLError) as exc:
            # Do not log credentials, request headers, or response bodies.
            LOG.warning("Heartbeat failed (%s)", type(exc).__name__)
        except Exception:
            LOG.exception("Unexpected host-updater error")

        time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    raise SystemExit(run())
