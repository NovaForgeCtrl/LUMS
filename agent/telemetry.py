#!/usr/bin/env python3
"""LUMS CPU/RAM telemetry agent. Uses only the Python standard library."""

import json
import math
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

AGENT_VERSION = "1.0.0"
TIMEOUT_SECONDS = 10
CPU_SAMPLE_INTERVAL = 0.2


def read_cpu_counters(path="/proc/stat"):
    with open(path, "r", encoding="ascii") as handle:
        first_line = handle.readline().strip()

    fields = first_line.split()
    if not fields or fields[0] != "cpu" or len(fields) < 5:
        raise RuntimeError("Unable to read aggregate CPU counters")

    values = [int(value) for value in fields[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return sum(values), idle


def calculate_cpu_percent(before, after):
    total_delta = after[0] - before[0]
    idle_delta = after[1] - before[1]

    if total_delta <= 0 or idle_delta < 0:
        raise RuntimeError("Invalid CPU counter delta")

    busy = 100.0 * (total_delta - idle_delta) / total_delta
    return round(min(100.0, max(0.0, busy)), 2)


def read_cpu_percent():
    before = read_cpu_counters()
    time.sleep(CPU_SAMPLE_INTERVAL)
    after = read_cpu_counters()
    return calculate_cpu_percent(before, after)


def read_memory():
    values = {}
    with open("/proc/meminfo", "r", encoding="ascii") as handle:
        for line in handle:
            key, separator, remainder = line.partition(":")
            if not separator:
                continue
            if key in ("MemTotal", "MemAvailable"):
                fields = remainder.split()
                if not fields or (len(fields) > 1 and fields[1] != "kB"):
                    raise RuntimeError("Unexpected /proc/meminfo format")
                values[key] = int(fields[0]) * 1024

    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", -1)
    if total <= 0 or available < 0 or available > total:
        raise RuntimeError("Invalid memory values in /proc/meminfo")

    percent = round(100.0 * (total - available) / total, 2)
    return {
        "memory_percent": percent,
        "memory_total_bytes": total,
        "memory_available_bytes": available,
    }


def build_sample(cpu_percent, memory):
    if isinstance(cpu_percent, bool) or not isinstance(cpu_percent, (int, float)):
        raise ValueError("Invalid CPU percentage")
    if not math.isfinite(cpu_percent) or not 0 <= cpu_percent <= 100:
        raise ValueError("CPU percentage out of range")

    sample = {
        "cpu_percent": float(cpu_percent),
        **memory,
    }
    total = sample.get("memory_total_bytes")
    available = sample.get("memory_available_bytes")
    percent = sample.get("memory_percent")

    if (
        isinstance(total, bool)
        or not isinstance(total, int)
        or total <= 0
        or isinstance(available, bool)
        or not isinstance(available, int)
        or not 0 <= available <= total
        or isinstance(percent, bool)
        or not isinstance(percent, (int, float))
        or not math.isfinite(percent)
        or not 0 <= percent <= 100
    ):
        raise ValueError("Invalid memory sample")

    return sample


def make_ssl_context(ca_file):
    if ca_file:
        path = Path(ca_file)
        if not path.is_file():
            raise RuntimeError(
                f"Configured LUMS_CA_FILE does not exist: {path}"
            )
        try:
            return ssl.create_default_context(cafile=str(path))
        except (OSError, ssl.SSLError) as exc:
            raise RuntimeError(
                f"Unable to load configured LUMS_CA_FILE: {path}"
            ) from exc

    return ssl.create_default_context()


def send_sample(base_url, token, sample, context, opener=None):
    if not token:
        raise RuntimeError("LUMS_TOKEN is not configured")

    parts = urlsplit(base_url)
    if parts.scheme not in ("https", "http") or not parts.netloc:
        raise RuntimeError("LUMS_BASE must be an absolute HTTP(S) URL")
    if parts.username or parts.password:
        raise RuntimeError("Credentials must not be embedded in LUMS_BASE")
    if parts.scheme != "https" and parts.hostname not in (
        "localhost", "127.0.0.1", "::1"
    ):
        raise RuntimeError("HTTPS is required for non-local LUMS endpoints")

    payload = json.dumps(sample, allow_nan=False).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/telemetry",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    open_request = opener or urllib.request.urlopen
    with open_request(
        request,
        timeout=TIMEOUT_SECONDS,
        context=context,
    ) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Telemetry API returned HTTP {response.status}")
        response.read()


def main():
    base_url = os.environ.get("LUMS_BASE", "http://127.0.0.1:5000")
    token = os.environ.get("LUMS_TOKEN", "")
    ca_file = os.environ.get("LUMS_CA_FILE")

    try:
        sample = build_sample(read_cpu_percent(), read_memory())
        context = make_ssl_context(ca_file)
        send_sample(base_url, token, sample, context)
    except (OSError, ValueError, RuntimeError, ssl.SSLError,
            urllib.error.URLError) as exc:
        # Never print the token or request headers.
        print(f"LUMS telemetry failed: {exc}", file=sys.stderr)
        return 1

    print("LUMS telemetry sample sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
