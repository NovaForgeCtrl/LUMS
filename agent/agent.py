#!/usr/bin/env python3

import json
import os
import platform
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request


AGENT_VERSION = "1.6.0"

LUMS_BASE = os.environ.get(
    "LUMS_BASE",
    "http://127.0.0.1:5000"
)

LUMS_TOKEN = os.environ.get(
    "LUMS_TOKEN",
    ""
)

LUMS_REPORT_API = f"{LUMS_BASE}/api/report"

PACKAGE_TIMEOUT = 900

LUMS_CA_FILE = os.environ.get(
    "LUMS_CA_FILE",
    "/opt/lums-agent/lums-ca.crt"
)

LUMS_SSL_CONTEXT = ssl.create_default_context(
    cafile=LUMS_CA_FILE
)

SIMULATE_UPDATES = os.environ.get(
    "LUMS_SIMULATE_UPDATES",
    "0"
).lower() in ("1", "true", "yes", "on")


# ============================================================
# TERMINAL UI // MINIMAL CYBER HUD
# ============================================================

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

BLACK = "\033[30m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
WHITE = "\033[97m"


def c(color, text):
    return f"{color}{text}{RESET}"


def clear_line():
    sys.stdout.write("\r\033[2K")
    sys.stdout.flush()


def separator(width=64):
    print(c(DIM, "─" * width))


def status_ok(text):
    print(c(GREEN, f"  ✓ {text}"))


def status_warn(text):
    print(c(YELLOW, f"  ! {text}"))


def status_fail(text):
    print(c(RED, f"  ✕ {text}"))


def panel(title):
    print()
    print(
        c(CYAN, "  ◈ ") +
        c(WHITE + BOLD, title)
    )


def print_banner():
    print()

    print(
        c(CYAN, "╔══════════════════════════════════════════════════════════════╗")
    )

    print(
        c(CYAN, "║") +
        c(WHITE + BOLD, "  LUMS // UPDATE AGENT".ljust(62)) +
        c(CYAN, "║")
    )

    print(
        c(CYAN, "║") +
        c(GREEN + BOLD, "  segfault // override".ljust(62)) +
        c(CYAN, "║")
    )

    print(
        c(CYAN, "║") +
        c(DIM, "  Linux Update Management without the noise.".ljust(62)) +
        c(CYAN, "║")
    )

    print(
        c(CYAN, "╚══════════════════════════════════════════════════════════════╝")
    )

    print(
        f"  {c(CYAN, 'AGENT')} {c(GREEN, AGENT_VERSION)}"
    )


def print_system(data):
    panel("SYSTEM")

    print(
        f"  {c(CYAN, 'HOST'):16}"
        f"{c(WHITE, data['hostname'])}"
        f"    {c(CYAN, 'IP'):10}"
        f"{c(WHITE, data['ip'])}"
    )

    print(
        f"  {c(CYAN, 'OS'):16}"
        f"{c(WHITE, data['os'])}"
        f"    {c(CYAN, 'ARCH'):10}"
        f"{c(WHITE, data['architecture'])}"
    )

    print(
        f"  {c(CYAN, 'KERNEL'):16}"
        f"{c(WHITE, data['kernel'])}"
    )

    print(
        f"  {c(CYAN, 'PACKAGES'):16}"
        f"{c(WHITE, str(len(data['packages'])))}"
        f"    {c(CYAN, 'UPDATES'):10}"
        f"{c(YELLOW, str(len(data['updates'])))}"
    )


def print_connection_header():
    panel("LUMS CHANNEL")


def print_connection_state():
    print(
        f"  {c(GREEN, '● TLS')}  {c(GREEN, 'CONNECTED')}"
        f"    {c(GREEN, '● AUTH')}  {c(GREEN, 'VERIFIED')}"
    )


def hud_bar(progress, width=42, failed=False, cursor=True):
    progress = max(0.0, min(1.0, progress))

    filled = int(width * progress)
    empty = width - filled

    if failed:
        active_color = RED
    else:
        active_color = GREEN

    chars = ["█"] * filled + ["░"] * empty

    if cursor and 0 < filled < width:
        cursor_pos = min(filled, width - 1)
        chars[cursor_pos] = "◆"

    bar = ""

    for index, char in enumerate(chars):

        if char == "◆":
            bar += c(CYAN + BOLD, char)

        elif index < filled:
            bar += c(active_color, char)

        else:
            bar += c(DIM, char)

    hex_value = f"{int(progress * 255):02X}"

    return (
        f"{bar} "
        f"{c(BLACK + BOLD, '0x' + hex_value)}"
    )


def print_bar(progress, status="PROCESSING", elapsed=None, failed=False):
    if status.lower() == "timeout":
        failed = True

    bar = hud_bar(
        progress,
        width=42,
        failed=failed,
        cursor=False
    )

    if status.lower() == "success":
        state = c(GREEN + BOLD, "SUCCESS")

    elif status.lower() == "failed":
        state = c(RED + BOLD, "FAILED")

    elif status.lower() == "timeout":
        state = c(YELLOW + BOLD, "TIMEOUT")

    else:
        state = c(GREEN, "PROCESSING")

    if elapsed is not None:
        print(
            f"  {bar}  {state}"
            f"  {c(DIM, f'{elapsed:.2f}s')}"
        )
    else:
        print(
            f"  {bar}  {state}"
        )


def print_package_header(index, total, package):
    print()

    print(
        f"  {c(CYAN, f'[{index:02d}/{total:02d}]')}"
        f" {c(WHITE + BOLD, package)}"
    )


def print_package_stats(elapsed, progress):
    if elapsed > 0:
        rate = progress / elapsed
    else:
        rate = 0.0

    print(
        f"  {c(DIM, 'STATE'):10}"
        f"{c(GREEN, 'RUNNING'):10}"
        f"{c(DIM, 'RATE'):10}"
        f"{c(WHITE, f'{rate:.2f}')}"
        f"{c(DIM, 'ELAPSED'):12}"
        f"{c(WHITE, f'{elapsed:.2f}s')}"
    )


def animate_simulation(package, index, total, duration=1.8, fail=False):
    start = time.monotonic()

    while True:
        elapsed = time.monotonic() - start
        progress = min(elapsed / duration, 1.0)

        clear_line()

        activity = ["◈", "◇", "◆", "◇"][
            int(elapsed * 10) % 4
        ]

        bar = hud_bar(
            progress,
            width=42,
            failed=fail,
            cursor=True
        )

        state = (
            c(RED + BOLD, "FAILED")
            if fail
            else c(GREEN, "PROCESSING")
        )

        sys.stdout.write(
            f"\r  {c(CYAN + BOLD, activity)} "
            f"{bar}  {state} "
            f"{c(DIM, f'{elapsed:.2f}s')}"
        )

        sys.stdout.flush()

        if progress >= 1.0:
            break

        time.sleep(0.045)

    elapsed = time.monotonic() - start

    clear_line()

    if fail:
        final_progress = 0.78
        activity = c(RED + BOLD, "✕")
        state = c(RED + BOLD, "FAILED")
    else:
        final_progress = 1.0
        activity = c(GREEN + BOLD, "✓")
        state = c(GREEN + BOLD, "SUCCESS")

    bar = hud_bar(
        final_progress,
        width=42,
        failed=fail,
        cursor=False
    )

    sys.stdout.write(
        f"  {activity} "
        f"{bar}  {state} "
        f"{c(DIM, f'{elapsed:.2f}s')}\n"
    )

    sys.stdout.flush()


def print_matrix(results):
    successful = sum(
        1 for item in results
        if item["status"] == "success"
    )

    failed = sum(
        1 for item in results
        if item["status"] == "failed"
    )

    timeout = sum(
        1 for item in results
        if item["status"] == "timeout"
    )

    total = len(results)

    percentage = (
        (successful / total) * 100
        if total
        else 0
    )

    panel("UPDATE SUMMARY")

    print(
        f"  {c(GREEN, '✓')} "
        f"{c(WHITE, str(successful))} successful"
    )

    print(
        f"  {c(RED, '✕')} "
        f"{c(WHITE, str(failed))} failed"
    )

    print(
        f"  {c(YELLOW, '○')} "
        f"{c(WHITE, str(timeout))} timeout"
    )

    print()

    print(
        f"  TOTAL  {hud_bar(percentage / 100, width=42, cursor=False)}"
        f"  {c(WHITE + BOLD, f'{percentage:.1f}%')}"
    )


def print_error_panel(package):
    print(
        f"  {c(RED, '✕')} "
        f"{c(RED + BOLD, package)} "
        f"{c(DIM, '// simulated failure')}"
    )


def print_simulation_report(results, started):
    elapsed = time.monotonic() - started

    successful = sum(
        1 for item in results
        if item["status"] == "success"
    )

    failed = sum(
        1 for item in results
        if item["status"] == "failed"
    )

    timeout = sum(
        1 for item in results
        if item["status"] == "timeout"
    )

    panel("FINAL REPORT")

    print(
        f"  {c(CYAN, 'RESULT'):14}"
        f"{c(GREEN, 'SIMULATION COMPLETE')}"
    )

    print(
        f"  {c(CYAN, 'SUCCESS'):14}"
        f"{c(GREEN, str(successful))}"
        f"    {c(CYAN, 'FAILED'):10}"
        f"{c(RED, str(failed))}"
    )

    print(
        f"  {c(CYAN, 'TIMEOUT'):14}"
        f"{c(YELLOW, str(timeout))}"
        f"    {c(CYAN, 'RUNTIME'):10}"
        f"{c(WHITE, f'{elapsed:.2f}s')}"
    )

    print(
        f"  {c(CYAN, 'APT'):14}"
        f"{c(GREEN, 'DISABLED')}"
        f"    {c(CYAN, 'LUMS RESULT'):10}"
        f"{c(GREEN, 'NOT SENT')}"
    )


def simulate_job():
    started = time.monotonic()

    panel("SIMULATION")

    print(
        f"  {c(CYAN, 'MODE'):14}"
        f"{c(YELLOW + BOLD, 'SIMULATION')}"
    )

    print(
        f"  {c(CYAN, 'APT'):14}"
        f"{c(GREEN, 'DISABLED')}"
    )

    print(
        f"  {c(CYAN, 'ENGINE'):14}"
        f"{c(GREEN, 'READ-ONLY')}"
    )

    print()

    status_warn(
        "Visual test only // no packages will be changed."
    )

    packages = [
        "linux-image-generic",
        "libssl3",
        "openssl",
        "python3-cryptography",
        "sqlite3",
        "curl",
        "ca-certificates",
        "netplan.io",
    ]

    results = []
    total = len(packages)

    panel("UPDATE ENGINE")

    for index, package in enumerate(
        packages,
        start=1
    ):

        print_package_header(
            index,
            total,
            package
        )

        print(
            c(
                DIM,
                "  $ simulated apt-get install "
                "--only-upgrade -y " + package
            )
        )

        fail = package == "sqlite3"

        animate_simulation(
            package,
            index,
            total,
            duration=1.4,
            fail=fail
        )

        if fail:

            status_fail(
                f"{package} // FAILED"
            )

            print_error_panel(package)

            results.append({
                "package": package,
                "status": "failed",
                "message": "Simulated failure.",
                "returncode": 1
            })

        else:

            status_ok(
                f"{package} // SUCCESS"
            )

            results.append({
                "package": package,
                "status": "success",
                "message": "Simulated success.",
                "returncode": 0
            })

        overall = index / total

        print(
            f"  {c(DIM, 'TOTAL PROGRESS')} "
            f"{hud_bar(overall, width=42, cursor=False)} "
            f"{c(WHITE, f'{overall * 100:05.1f}%')}"
        )

    print_matrix(results)

    print_simulation_report(
        results,
        started
    )

    print()

    status_ok(
        "SIMULATION COMPLETE // NO LUMS JOB RESULT SENT"
    )


# ============================================================
# LUMS API
# ============================================================

def get_auth_headers(extra=None):
    if not LUMS_TOKEN:
        raise RuntimeError(
            "LUMS_TOKEN ist nicht gesetzt."
        )

    headers = {
        "Authorization": f"Bearer {LUMS_TOKEN}"
    }

    if extra:
        headers.update(extra)

    return headers


def get_idle_status():
    """
    Determine local user inactivity.

    For server/TTY/SSH clients we use `w -h` because loginctl's
    IdleHint is not reliable for headless TTY/SSH sessions.

    Safety rule:
    - Any relevant active session resets the idle state.
    - The shortest idle duration is used.
    - Unknown or malformed activity information is treated as active.
    - The agent itself does not create a persistent user session and
      therefore does not artificially keep the client active.
    """

    threshold_seconds = 300

    def parse_idle_seconds(value):
        """
        Parse the IDLE column from `w`.

        Supported examples:
            0.00s
            5.00s
            30:16
            1:02:03
            2days
            2days,01:15
        """

        value = value.strip()

        if not value:
            raise ValueError("empty idle value")

        # Seconds, e.g. 0.00s / 5.00s
        if value.endswith("s"):
            return max(
                0,
                int(float(value[:-1]))
            )

        # Days, e.g. 2days
        if value.endswith("days"):
            days_part = value[:-4]
            return max(
                0,
                int(float(days_part) * 86400)
            )

        # Optional combined format:
        # 2days,01:15
        if "days," in value:
            days_part, time_part = value.split(",", 1)

            days = int(days_part.replace("days", "").strip())

            parts = time_part.split(":")

            if len(parts) == 2:
                hours = 0
                minutes = int(parts[0])
                seconds = int(parts[1])

            elif len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])

            else:
                raise ValueError("invalid day/time idle format")

            return max(
                0,
                days * 86400
                + hours * 3600
                + minutes * 60
                + seconds
            )

        # HH:MMm
        # Example: 1:49m = 1 hour and 49 minutes
        if value.endswith("m") and ":" in value:
            time_value = value[:-1]
            parts = time_value.split(":")

            if len(parts) == 2:
                hours = int(parts[0])
                minutes = int(parts[1])

                return max(
                    0,
                    hours * 3600
                    + minutes * 60
                )

            raise ValueError(
                f"unsupported minute idle value: {value}"
            )

        # HH:MM
        parts = value.split(":")

        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = int(parts[1])

            return max(
                0,
                minutes * 60 + seconds
            )

        # HH:MM:SS
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])

            return max(
                0,
                hours * 3600
                + minutes * 60
                + seconds
            )

        raise ValueError(
            f"unsupported idle value: {value}"
        )

    try:
        result = subprocess.run(
            [
                "w",
                "-h"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        idle_values = []

        for line in result.stdout.splitlines():

            if not line.strip():
                continue

            parts = line.split()

            # Expected minimum:
            #
            # USER TTY FROM LOGIN@ IDLE JCPU PCPU WHAT
            #
            if len(parts) < 7:
                continue

            user = parts[0]
            tty = parts[1]
            idle_value = parts[4]

            # Ignore non-terminal pseudo entries.
            if not tty:
                continue

            # `w` reports the current command itself as a process
            # but this does not represent user activity.
            #
            # We intentionally do not treat the presence of the
            # session as activity. Only the IDLE column matters.

            try:
                idle_seconds = parse_idle_seconds(
                    idle_value
                )
            except (ValueError, TypeError):
                return {
                    "idle": False,
                    "idle_seconds": 0,
                    "threshold_seconds": threshold_seconds,
                    "idle_source": "w",
                    "idle_supported": False
                }

            idle_values.append(idle_seconds)

        if not idle_values:
            return {
                "idle": False,
                "idle_seconds": 0,
                "threshold_seconds": threshold_seconds,
                "idle_source": "w",
                "idle_supported": False
            }

        # Safety rule:
        # The most recently active session determines the client state.
        idle_seconds = min(idle_values)

        return {
            "idle": idle_seconds >= threshold_seconds,
            "idle_seconds": idle_seconds,
            "threshold_seconds": threshold_seconds,
            "idle_source": "w",
            "idle_supported": True
        }

    except (
        subprocess.CalledProcessError,
        ValueError,
        OSError
    ):
        return {
            "idle": False,
            "idle_seconds": 0,
            "threshold_seconds": threshold_seconds,
            "idle_source": "w",
            "idle_supported": False
        }

def get_ip():
    return subprocess.check_output(
        [
            "bash",
            "-c",
            "ip route get 1.1.1.1 | awk '{print $7; exit}'"
        ],
        text=True
    ).strip()


# ============================================================
# PACKAGE INFORMATION
# ============================================================

def get_packages():
    result = subprocess.run(
        [
            "dpkg-query",
            "-W",
            "-f=${binary:Package} ${Version}\n"
        ],
        capture_output=True,
        text=True,
        check=True
    )

    packages = {}

    for line in result.stdout.splitlines():
        parts = line.split(" ", 1)

        if len(parts) == 2:
            package, version = parts
            packages[package] = version

    return packages


def get_updates():
    env = os.environ.copy()
    env["LC_ALL"] = "C"

    result = subprocess.run(
        ["apt", "list", "--upgradable"],
        capture_output=True,
        text=True,
        env=env
    )

    updates = []

    for line in result.stdout.splitlines():

        if "/" not in line:
            continue

        if "upgradable" not in line:
            continue

        parts = line.split()

        if len(parts) < 2:
            continue

        package_info = parts[0]
        available_version = parts[1]

        package = package_info.split("/")[0]

        installed_version = None

        if "upgradable from:" in line:
            installed_version = line.split(
                "upgradable from:",
                1
            )[1].strip().rstrip("]")

        updates.append({
            "package": package,
            "installed_version": installed_version,
            "available_version": available_version
        })

    return updates


def collect_data():
    idle_status = get_idle_status()

    return {
        "hostname": socket.gethostname(),
        "ip": get_ip(),
        "os": platform.system(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "agent_version": AGENT_VERSION,
        "updates": get_updates(),
        "packages": get_packages(),
        "idle": idle_status["idle"],
        "idle_seconds": idle_status["idle_seconds"],
        "idle_threshold_seconds": idle_status["threshold_seconds"],
        "idle_source": idle_status["idle_source"],
        "idle_supported": idle_status["idle_supported"]
    }

def send_report(data):
    payload = json.dumps(data).encode("utf-8")

    request = urllib.request.Request(
        LUMS_REPORT_API,
        data=payload,
        headers=get_auth_headers({
            "Content-Type": "application/json"
        }),
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=10,
        context=LUMS_SSL_CONTEXT
    ) as response:

        return response.read().decode("utf-8")


def get_client():
    request = urllib.request.Request(
        f"{LUMS_BASE}/api/client/me",
        headers=get_auth_headers()
    )

    with urllib.request.urlopen(
        request,
        timeout=10,
        context=LUMS_SSL_CONTEXT
    ) as response:

        return json.loads(
            response.read().decode("utf-8")
        )


def get_pending_job(client_id):
    url = (
        f"{LUMS_BASE}/api/clients/"
        f"{client_id}/update-jobs/pending"
    )

    request = urllib.request.Request(
        url,
        headers=get_auth_headers()
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=10,
            context=LUMS_SSL_CONTEXT
        ) as response:

            if response.status == 204:
                return None

            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:

        if error.code == 204:
            return None

        raise



def get_running_job(client_id):
    url = (
        f"{LUMS_BASE}/api/clients/"
        f"{client_id}/update-jobs/running"
    )

    request = urllib.request.Request(
        url,
        headers=get_auth_headers()
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=10,
            context=LUMS_SSL_CONTEXT
        ) as response:

            if response.status == 204:
                return None

            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:

        if error.code == 204:
            return None

        raise

def claim_job(client_id, job_id):
    url = (
        f"{LUMS_BASE}/api/clients/"
        f"{client_id}/update-jobs/"
        f"{job_id}/claim"
    )

    request = urllib.request.Request(
        url,
        method="POST",
        headers=get_auth_headers()
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=10,
            context=LUMS_SSL_CONTEXT
        ) as response:

            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:

        if error.code == 409:
            try:
                body = json.loads(
                    error.read().decode("utf-8")
                )
            except Exception:
                body = {
                    "status": "not_claimable"
                }

            return body

        raise


# ============================================================
# PACKAGE STATE
# ============================================================

def get_installed_package_state(package):
    result = subprocess.run(
        [
            "dpkg-query",
            "-W",
            "-f=${Status}|${Version}",
            package
        ],
        capture_output=True,
        text=True
    )

    output = result.stdout.strip()

    if result.returncode != 0:
        return {
            "installed": False,
            "status": None,
            "version": None,
            "raw": output
        }

    parts = output.split("|", 2)

    if len(parts) != 2:
        return {
            "installed": False,
            "status": output,
            "version": None,
            "raw": output
        }

    package_status = parts[0]
    version = parts[1]

    installed = (
        package_status == "install ok installed"
    )

    return {
        "installed": installed,
        "status": package_status,
        "version": version,
        "raw": output
    }


def get_candidate_version(package):
    result = subprocess.run(
        [
            "apt-cache",
            "policy",
            package
        ],
        capture_output=True,
        text=True
    )

    for line in result.stdout.splitlines():

        line = line.strip()

        if line.startswith("Candidate:"):
            return line.split(
                ":",
                1
            )[1].strip()

    return None


# ============================================================
# UPDATE ENGINE
# ============================================================

def animate_update(command, package):
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    env["LC_ALL"] = "C"

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        bufsize=1
    )

    start = time.monotonic()
    output_lines = []

    try:

        while True:

            if time.monotonic() - start > PACKAGE_TIMEOUT:
                process.kill()
                process.wait()

                raise subprocess.TimeoutExpired(
                    command,
                    PACKAGE_TIMEOUT
                )

            line = process.stdout.readline()

            if line:
                output_lines.append(
                    line.rstrip()
                )

                if len(output_lines) > 250:
                    output_lines.pop(0)

            returncode = process.poll()

            if returncode is not None:
                break

            elapsed = time.monotonic() - start
            cycle = (elapsed % 8.0) / 8.0
            progress = 0.08 + (cycle * 0.84)

            clear_line()

            value = int(progress * 255)
            hex_value = f"0x{value:02X}"

            sys.stdout.write(
                f"  UPDATE {c(CYAN, package):30} "
                f"{c(GREEN, hex_value)}"
            )

            sys.stdout.flush()

            time.sleep(0.08)

        remaining = process.stdout.read()

        if remaining:
            output_lines.extend(
                remaining.splitlines()
            )

    except subprocess.TimeoutExpired:
        raise

    except Exception:
        process.kill()
        process.wait()
        raise

    clear_line()

    return (
        process.returncode,
        "\n".join(output_lines)
    )


def run_package_update(package):
    command = [
        "apt-get",
        "install",
        "--only-upgrade",
        "-y",
        package
    ]

    print()
    print(
        c(CYAN, f"  UPDATE // {package}")
    )

    print(
        c(DIM, "  $ " + " ".join(command))
    )

    target_version = get_candidate_version(package)

    if target_version:
        print(
            f"  Zielversion: {c(WHITE, target_version)}"
        )

    try:

        returncode, output = animate_update(
            command,
            package
        )

    except subprocess.TimeoutExpired:

        print_bar(
            0.78,
            "timeout"
        )

        print()

        return {
            "package": package,
            "status": "timeout",
            "message": (
                f"Package update timed out after "
                f"{PACKAGE_TIMEOUT} seconds."
            ),
            "returncode": None
        }

    package_state = get_installed_package_state(
        package
    )

    installed_version = package_state.get(
        "version"
    )

    package_installed = package_state.get(
        "installed"
    )

    if returncode == 0:

        print_bar(
            1.0,
            "success"
        )

        print()

        return {
            "package": package,
            "status": "success",
            "message": (
                f"Package update completed successfully.\n"
                f"Returncode: {returncode}\n"
                f"Installed version: "
                f"{installed_version or 'unknown'}\n\n"
                f"{output[-3500:]}"
            ),
            "returncode": returncode
        }

    if (
        package_installed
        and target_version
        and installed_version == target_version
    ):

        print_bar(
            1.0,
            "success"
        )

        print()

        return {
            "package": package,
            "status": "success",
            "message": (
                "apt-get returned a non-zero code, "
                "but the package is installed and the "
                "target version is present.\n"
                f"Returncode: {returncode}\n"
                f"Installed version: {installed_version}\n"
                f"Target version: {target_version}\n\n"
                f"{output[-3000:]}"
            ),
            "returncode": returncode
        }

    if (
        package_installed
        and target_version is None
    ):

        print_bar(
            1.0,
            "success"
        )

        print()

        return {
            "package": package,
            "status": "success",
            "message": (
                "apt-get returned a non-zero code, "
                "but the package is installed correctly. "
                "No candidate version was available "
                "for comparison.\n"
                f"Returncode: {returncode}\n"
                f"Installed version: {installed_version}\n\n"
                f"{output[-3000:]}"
            ),
            "returncode": returncode
        }

    print_bar(
        0.78,
        "failed"
    )

    print()

    return {
        "package": package,
        "status": "failed",
        "message": (
            f"Package update failed.\n"
            f"Returncode: {returncode}\n"
            f"Package status: "
            f"{package_state.get('status') or 'unknown'}\n"
            f"Installed version: "
            f"{installed_version or 'unknown'}\n"
            f"Target version: "
            f"{target_version or 'unknown'}\n\n"
            f"{output[-3500:]}"
        ),
        "returncode": returncode
    }


def reboot_required():
    return os.path.exists(
        "/var/run/reboot-required"
    )


# ============================================================
# JOB RESULT
# ============================================================

def send_job_result(
    job_id,
    status,
    packages,
    reboot
):
    payload = json.dumps({
        "status": status,
        "reboot_required": reboot,
        "packages": packages
    }).encode("utf-8")

    request = urllib.request.Request(
        f"{LUMS_BASE}/api/update-jobs/{job_id}/result",
        data=payload,
        headers=get_auth_headers({
            "Content-Type": "application/json"
        }),
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=10,
        context=LUMS_SSL_CONTEXT
    ) as response:

        return response.read().decode("utf-8")


def execute_job(job):
    job_id = job["job_id"]
    job_packages = job.get("packages", [])

    simulation = SIMULATE_UPDATES

    panel(
        "SIMULATION" if simulation else "UPDATE ENGINE"
    )

    print(
        f"  JOB        {c(CYAN, str(job_id))}"
    )

    print(
        f"  PACKAGES   {c(WHITE, str(len(job_packages)))}"
    )

    if simulation:

        print(
            f"  MODE       "
            f"{c(YELLOW + BOLD, "SIMULATION")}"
        )

        print(
            f"  APT        "
            f"{c(GREEN, "DISABLED")}"
        )

        print(
            f"  ENGINE     "
            f"{c(GREEN, "READ-ONLY")}"
        )

        print()

        status_warn(
            "E2E simulation // no packages will be changed."
        )

    print()

    results = []

    total = len(job_packages)

    for index, item in enumerate(
        job_packages,
        start=1
    ):

        package = item["package"]

        print(
            c(
                WHITE + BOLD,
                f"[{index:02d}/{total:02d}] {package}"
            )
        )

        if simulation:

            print(
                c(
                    DIM,
                    "  $ simulated apt-get install "
                    "--only-upgrade -y " + package
                )
            )

            time.sleep(1.0)

            result = {
                "package": package,
                "status": "success",
                "message": "E2E simulation success.",
                "returncode": 0
            }

        else:

            result = run_package_update(
                package
            )

        results.append(result)

        if result["status"] == "success":

            status_ok(
                f"{package} // SUCCESS"
            )

        elif result["status"] == "timeout":

            status_warn(
                f"{package} // TIMEOUT"
            )

        else:

            status_fail(
                f"{package} // FAILED"
            )

    successful = sum(
        1
        for item in results
        if item["status"] == "success"
    )

    failed = sum(
        1
        for item in results
        if item["status"] == "failed"
    )

    timed_out = sum(
        1
        for item in results
        if item["status"] == "timeout"
    )

    if failed == 0 and timed_out == 0:
        status = "success"

    elif successful > 0:
        status = "partial"

    else:
        status = "failed"

    reboot = False if simulation else reboot_required()

    panel("UPDATE RESULT")

    print(
        f"  SUCCESS    {c(GREEN, str(successful))}"
    )

    print(
        f"  FAILED     {c(RED, str(failed))}"
    )

    print(
        f"  TIMEOUT    {c(YELLOW, str(timed_out))}"
    )

    print(
        f"  REBOOT     "
        f"{c(YELLOW, 'REQUIRED' if reboot else 'NOT REQUIRED')}"
    )

    print()

    print(
        c(CYAN, "  SENDING RESULT TO LUMS...")
    )

    response = send_job_result(
        job_id,
        status,
        results,
        reboot
    )

    status_ok(
        f"LUMS API // {response}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print_banner()

    if SIMULATE_UPDATES:
        simulate_job()

        print()
        separator()

        print(
            c(
                GREEN + BOLD,
                "LUMS // Simulation cycle complete."
            )
        )

        print()

        return

    data = collect_data()

    print_system(data)

    print_connection_header()

    print(
        c(CYAN, "  REPORT      ") +
        "Sending system report..."
    )

    try:

        response = send_report(data)

        status_ok(
            f"REPORT ACCEPTED // {response}"
        )

    except Exception as error:

        status_fail(
            f"REPORT FAILED // {error}"
        )

    try:

        client = get_client()

        if client is None:

            status_fail(
                "CLIENT NOT FOUND"
            )

            return

        status_ok(
            f"CLIENT AUTHENTICATED // ID {client['id']}"
        )

        job = get_pending_job(
            client["id"]
        )

        if not job:

            status_ok(
                "NO UPDATE JOB // SYSTEM CLEAN"
            )

            print()
            print(
                c(
                    GREEN,
                    "LUMS // Agent cycle complete."
                )
            )

            return

        if job.get("status") == "no_job":

            status_ok(
                "NO UPDATE JOB // SYSTEM CLEAN"
            )

            print()
            print(
                c(
                    GREEN,
                    "LUMS // Agent cycle complete."
                )
            )

            return

        idle = bool(data.get("idle"))
        idle_seconds = max(
            0,
            int(data.get("idle_seconds", 0))
        )
        idle_threshold = max(
            1,
            int(data.get("idle_threshold_seconds", 300))
        )

        if not idle or idle_seconds < idle_threshold:

            remaining = max(
                0,
                idle_threshold - idle_seconds
            )

            minutes = remaining // 60
            seconds = remaining % 60

            status_warn(
                "UPDATE JOB // WAITING FOR IDLE // "
                f"{minutes:02d}:{seconds:02d} remaining"
            )

            print()
            print(
                c(
                    YELLOW,
                    "  UPDATE REMAINS PENDING"
                )
            )

            print(
                c(
                    YELLOW,
                    "  NO CLAIM // NO EXECUTION"
                )
            )

            print()
            print(
                c(
                    GREEN,
                    "LUMS // Agent cycle complete."
                )
            )

            return

        status_ok(
            "IDLE THRESHOLD REACHED"
        )

        print()
        print(
            c(
                CYAN,
                f"  CLAIMING JOB #{job['job_id']}..."
            )
        )

        claimed_job = claim_job(
            client["id"],
            job["job_id"]
        )

        if claimed_job.get("status") != "claimed":

            status_warn(
                "JOB NOT CLAIMED // "
                f"{claimed_job.get('status', 'unknown')}"
            )

            print()
            print(
                c(
                    YELLOW,
                    "  NO EXECUTION"
                )
            )

            print()
            print(
                c(
                    GREEN,
                    "LUMS // Agent cycle complete."
                )
            )

            return

        status_ok(
            f"JOB CLAIMED // #{claimed_job['job_id']}"
        )

        execute_job(claimed_job)

        panel("POST-UPDATE")

        print(
            c(
                CYAN,
                "  COLLECTING CURRENT SYSTEM STATE..."
            )
        )

        updated_data = collect_data()

        print(
            f"  UPDATES    "
            f"{c(YELLOW, str(len(updated_data['updates'])))}"
        )

        print(
            c(
                CYAN,
                "  SENDING UPDATED REPORT..."
            )
        )

        try:

            response = send_report(
                updated_data
            )

            status_ok(
                f"UPDATED REPORT // {response}"
            )

        except Exception as error:

            status_fail(
                f"UPDATED REPORT FAILED // {error}"
            )

    except Exception as error:

        print()

        status_fail(
            f"JOB EXECUTION ERROR // {error}"
        )

    print()
    separator()

    print(
        c(
            GREEN + BOLD,
            "LUMS // Agent cycle complete."
        )
    )

    print()


if __name__ == "__main__":
    main()
