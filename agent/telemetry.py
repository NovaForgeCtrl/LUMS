#!/usr/bin/env python3
"""LUMS CPU/RAM/network telemetry agent. Uses only the Python standard library."""

import json
import ipaddress
import math
import os
import platform
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from glob import glob
from pathlib import Path
from urllib.parse import urlsplit

AGENT_VERSION = "1.2.0"
TIMEOUT_SECONDS = 10
CPU_SAMPLE_INTERVAL = 0.2
COMMAND_TIMEOUT_SECONDS = 1
MAX_SYSTEM_PAYLOAD_BYTES = 32768


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


def read_network_counters(path="/proc/net/dev"):
    """Return cumulative received/sent bytes of all non-loopback interfaces."""
    received = 0
    sent = 0
    found = False

    with open(path, "r", encoding="ascii") as handle:
        for line in handle:
            name, separator, remainder = line.partition(":")
            name = name.strip()
            if not separator or name == "lo":
                continue
            fields = remainder.split()
            if len(fields) < 9:
                continue
            received += int(fields[0])
            sent += int(fields[8])
            found = True

    if not found:
        raise RuntimeError("No network interfaces found")
    return {"network_rx_bytes": received, "network_tx_bytes": sent}


def read_optional_network_counters():
    # Older or restricted systems must still report CPU and memory.
    try:
        return read_network_counters()
    except (OSError, ValueError, RuntimeError):
        return {}


def read_interface_details(path="/proc/net/dev", sys_class_net="/sys/class/net"):
    interfaces = []
    with open(path, "r", encoding="ascii") as handle:
        for line in handle:
            name, separator, remainder = line.partition(":")
            name = name.strip()
            if not separator or not name or len(name) > 32:
                continue
            fields = remainder.split()
            if len(fields) < 12:
                continue

            try:
                counters = [int(value) for value in fields[:12]]
            except ValueError:
                continue

            try:
                state = (
                    Path(sys_class_net, name, "operstate")
                    .read_text(encoding="ascii")
                    .strip()
                )
            except OSError:
                state = "unknown"
            if state not in (
                "up", "down", "unknown", "dormant", "lowerlayerdown"
            ):
                state = "unknown"

            interfaces.append({
                "name": name,
                "state": state,
                "rx_bytes": counters[0],
                "tx_bytes": counters[8],
                "rx_errors": counters[2],
                "tx_errors": counters[10],
                "rx_dropped": counters[3],
                "tx_dropped": counters[11],
            })
            if len(interfaces) >= 32:
                break

    return interfaces


def read_default_gateway(path="/proc/net/route"):
    try:
        with open(path, "r", encoding="ascii") as handle:
            next(handle, None)
            for line in handle:
                fields = line.split()
                if len(fields) < 4 or fields[1] != "00000000":
                    continue
                if not (int(fields[3], 16) & 2):
                    continue
                return socket.inet_ntoa(
                    struct.pack("<I", int(fields[2], 16))
                )
    except (OSError, ValueError, struct.error):
        return None
    return None


def read_dns_servers(path="/etc/resolv.conf"):
    servers = []
    try:
        with open(path, "r", encoding="ascii") as handle:
            for line in handle:
                fields = line.split()
                if len(fields) < 2 or fields[0] != "nameserver":
                    continue
                try:
                    address = str(ipaddress.ip_address(fields[1]))
                except ValueError:
                    continue
                if address not in servers:
                    servers.append(address)
                if len(servers) >= 8:
                    break
    except OSError:
        pass
    return servers


def read_temperature_sensors(root="/sys/class"):
    temperatures = []
    fans = []

    for path in sorted(glob(f"{root}/thermal/thermal_zone*/temp")):
        try:
            milli_degrees = int(Path(path).read_text(encoding="ascii").strip())
            zone = Path(path).parent
            name = (zone / "type").read_text(encoding="ascii").strip()
            temperatures.append({
                "name": name[:64] or zone.name,
                "celsius": round(milli_degrees / 1000, 1),
            })
        except (OSError, ValueError):
            continue

    for path in sorted(glob(f"{root}/hwmon/hwmon*/temp*_input")):
        try:
            milli_degrees = int(Path(path).read_text(encoding="ascii").strip())
            label_path = Path(path).with_name(
                Path(path).name.replace("_input", "_label")
            )
            try:
                name = label_path.read_text(encoding="ascii").strip()
            except OSError:
                name = Path(path).name[:-6]
            temperatures.append({
                "name": name[:64] or Path(path).parent.name,
                "celsius": round(milli_degrees / 1000, 1),
            })
        except (OSError, ValueError):
            continue

    for path in sorted(glob(f"{root}/hwmon/hwmon*/fan*_input")):
        try:
            rpm = int(Path(path).read_text(encoding="ascii").strip())
            fans.append({
                "name": Path(path).name[:-6],
                "rpm": rpm,
            })
        except (OSError, ValueError):
            continue

    return temperatures[:16], fans[:16]


def run_read_only_command(arguments):
    try:
        result = subprocess.run(
            arguments,
            check=False,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def read_service_status():
    output = run_read_only_command([
        "systemctl", "list-units", "--type=service", "--all",
        "--no-legend", "--no-pager",
    ])
    if output is None:
        return {"available": False, "items": []}

    services = []
    for line in output.splitlines():
        fields = line.split(maxsplit=4)
        if len(fields) < 4:
            continue
        state = fields[2]
        if state not in ("active", "failed", "inactive"):
            continue
        services.append({
            "name": fields[0][:128],
            "state": state,
        })
        if len(services) >= 60:
            break
    return {"available": True, "items": services}


def read_container_status():
    containers = []
    available = False
    for runtime in ("docker", "podman"):
        output = run_read_only_command([
            runtime, "ps", "--all", "--format", "{{.Names}}\t{{.State}}",
        ])
        if output is None:
            continue
        available = True
        for line in output.splitlines():
            name, separator, state = line.partition("\t")
            if not separator or not name.strip():
                continue
            containers.append({
                "runtime": runtime,
                "name": name.strip()[:128],
                "state": state.strip()[:64],
            })
            if len(containers) >= 60:
                break
        if len(containers) >= 60:
            break
    return {"available": available, "items": containers}


def read_network_reachability(gateway, dns_servers):
    gateway_reachable = None
    if gateway and shutil.which("ping"):
        gateway_reachable = run_read_only_command([
            "ping", "-n", "-c", "1", "-W", "1", gateway,
        ]) is not None

    dns_reachable = None
    if dns_servers and shutil.which("getent"):
        dns_reachable = run_read_only_command([
            "getent", "ahosts", "example.com",
        ]) is not None

    internet_reachable = None
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=1):
            internet_reachable = True
    except OSError:
        internet_reachable = False

    return {
        "gateway_reachable": gateway_reachable,
        "dns_reachable": dns_reachable,
        "internet_reachable": internet_reachable,
    }


def read_system_snapshot():
    try:
        load_average = [round(value, 2) for value in os.getloadavg()]
    except (AttributeError, OSError):
        load_average = None

    uptime_seconds = None
    try:
        uptime_seconds = int(
            float(Path("/proc/uptime").read_text(encoding="ascii").split()[0])
        )
    except (OSError, ValueError, IndexError):
        pass

    disk = None
    try:
        usage = shutil.disk_usage("/")
        disk = {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        }
    except OSError:
        pass

    os_name = platform.system()
    try:
        for line in Path("/etc/os-release").read_text(
            encoding="utf-8"
        ).splitlines():
            key, separator, value = line.partition("=")
            if key == "PRETTY_NAME" and separator:
                os_name = value.strip().strip('"')[:128]
                break
    except OSError:
        pass

    gateway = read_default_gateway()
    dns_servers = read_dns_servers()
    temperatures, fans = read_temperature_sensors()
    try:
        interfaces = read_interface_details()
    except OSError:
        interfaces = []
    return {
        "load_average": load_average,
        "uptime_seconds": uptime_seconds,
        "os": os_name[:128],
        "kernel": platform.release()[:128],
        "disk": disk,
        "interfaces": interfaces,
        "dns_servers": dns_servers,
        "gateway": gateway,
        **read_network_reachability(gateway, dns_servers),
        "temperatures": temperatures,
        "fans": fans,
        "services": read_service_status(),
        "containers": read_container_status(),
    }


def build_sample(cpu_percent, memory, network=None, system=None):
    if isinstance(cpu_percent, bool) or not isinstance(cpu_percent, (int, float)):
        raise ValueError("Invalid CPU percentage")
    if not math.isfinite(cpu_percent) or not 0 <= cpu_percent <= 100:
        raise ValueError("CPU percentage out of range")

    sample = {
        "cpu_percent": float(cpu_percent),
        **memory,
        **(network or {}),
    }
    if system is not None:
        if not isinstance(system, dict):
            raise ValueError("Invalid system snapshot")
        try:
            encoded_system = json.dumps(system, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid system snapshot") from exc
        if len(encoded_system) > MAX_SYSTEM_PAYLOAD_BYTES:
            raise ValueError("System snapshot is too large")
        sample["system"] = system
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

    if network:
        counters = (
            sample.get("network_rx_bytes"),
            sample.get("network_tx_bytes"),
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            for value in counters
        ):
            raise ValueError("Invalid network counters")

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
        sample = build_sample(
            read_cpu_percent(),
            read_memory(),
            read_optional_network_counters(),
            read_system_snapshot(),
        )
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
