#!/usr/bin/env python3

import json
import os
import platform
import selectors
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from package_manager import (
    PACKAGE_MANAGER_APT,
    PACKAGE_MANAGER_PACMAN,
    AptPackageManager,
    PacmanPackageManager,
    detect_package_manager,
)

DETECTED_PACKAGE_MANAGER = detect_package_manager()

if DETECTED_PACKAGE_MANAGER == PACKAGE_MANAGER_APT:
    PACKAGE_MANAGER = AptPackageManager()
elif DETECTED_PACKAGE_MANAGER == PACKAGE_MANAGER_PACMAN:
    PACKAGE_MANAGER = PacmanPackageManager()
else:
    raise RuntimeError(
        "No supported package manager found. "
        "Supported package managers: apt, pacman"
    )


AGENT_VERSION = "1.7.0"

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
PACKAGE_TERMINATE_GRACE = 10

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

        simulated_command = PACKAGE_MANAGER.update_package(package)

        print(
            c(
                DIM,
                "  $ simulated "
                + " ".join(simulated_command)
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
    Determine local user inactivity using systemd-logind.

    The agent uses loginctl instead of parsing `w` output.

    Safety rule:
    - Only real user sessions are considered.
    - systemd manager sessions are ignored.
    - Any active user session blocks updates.
    - For idle sessions, IdleSinceHintMonotonic determines the
      actual idle duration.
    - The shortest idle duration is used, so one active session
      keeps the client blocked even when another session is idle.
    - No relevant user session means the client is considered idle.
    """

    threshold_seconds = 300

    try:
        result = subprocess.run(
            [
                "loginctl",
                "list-sessions",
                "--no-legend",
                "--no-pager"
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True
        )
    except (
        subprocess.SubprocessError,
        OSError
    ):
        return {
            "idle": False,
            "idle_seconds": 0,
            "threshold_seconds": threshold_seconds,
            "idle_source": "loginctl",
            "idle_supported": False
        }

    session_ids = []

    for line in result.stdout.splitlines():
        parts = line.split()

        if not parts:
            continue

        session_id = parts[0]

        if session_id.isdigit():
            session_ids.append(session_id)

    idle_values = []

    for session_id in session_ids:

        try:
            session_result = subprocess.run(
                [
                    "loginctl",
                    "show-session",
                    session_id,
                    "-p", "Class",
                    "-p", "Type",
                    "-p", "TTY",
                    "-p", "State",
                    "-p", "IdleHint",
                    "-p", "IdleSinceHintMonotonic"
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
        except (
            subprocess.SubprocessError,
            OSError
        ):
            return {
                "idle": False,
                "idle_seconds": 0,
                "threshold_seconds": threshold_seconds,
                "idle_source": "loginctl",
                "idle_supported": False
            }

        properties = {}

        for line in session_result.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                properties[key] = value

        if properties.get("Class") != "user":
            continue

        session_type = properties.get("Type", "")
        tty = properties.get("TTY", "")

        if not tty and session_type not in {
            "x11",
            "wayland",
            "mir"
        }:
            continue

        if properties.get("IdleHint") != "yes":
            idle_values.append(0)
            continue

        idle_since_raw = properties.get(
            "IdleSinceHintMonotonic",
            ""
        )

        try:
            idle_since_microseconds = int(
                idle_since_raw
            )

            if idle_since_microseconds <= 0:
                raise ValueError(
                    "invalid IdleSinceHintMonotonic"
                )

            now_monotonic = time.monotonic()

            idle_since_seconds = (
                idle_since_microseconds / 1_000_000
            )

            idle_seconds = max(
                0,
                int(
                    now_monotonic -
                    idle_since_seconds
                )
            )

        except (
            ValueError,
            TypeError,
            OverflowError
        ):
            return {
                "idle": False,
                "idle_seconds": 0,
                "threshold_seconds": threshold_seconds,
                "idle_source": "loginctl",
                "idle_supported": False
            }

        idle_values.append(idle_seconds)

    if not idle_values:
        return {
            "idle": True,
            "idle_seconds": threshold_seconds,
            "threshold_seconds": threshold_seconds,
            "idle_source": "loginctl",
            "idle_supported": True
        }

    idle_seconds = min(idle_values)

    return {
        "idle": idle_seconds >= threshold_seconds,
        "idle_seconds": idle_seconds,
        "threshold_seconds": threshold_seconds,
        "idle_source": "loginctl",
        "idle_supported": True
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
    return PACKAGE_MANAGER.get_installed_packages()


def get_updates():
    return PACKAGE_MANAGER.get_updates()


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
    return PACKAGE_MANAGER.get_package_state(package)


def get_candidate_version(package):
    return PACKAGE_MANAGER.get_candidate_version(package)


# ============================================================
# UPDATE ENGINE
# ============================================================

def animate_package_action(command, package, action):
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

    selector = selectors.DefaultSelector()
    selector.register(
        process.stdout,
        selectors.EVENT_READ
    )

    start = time.monotonic()
    output_lines = []
    output_buffer = ""

    try:

        while True:

            elapsed = time.monotonic() - start

            if elapsed > PACKAGE_TIMEOUT:
                process.terminate()

                try:
                    process.wait(
                        timeout=PACKAGE_TERMINATE_GRACE
                    )
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

                raise subprocess.TimeoutExpired(
                    command,
                    PACKAGE_TIMEOUT
                )

            events = selector.select(
                timeout=min(0.08, max(
                    0.0,
                    PACKAGE_TIMEOUT - elapsed
                ))
            )

            if events:

                try:
                    chunk = process.stdout.read(4096)
                except (ValueError, OSError):
                    chunk = ""

                if chunk:
                    output_buffer += chunk

                    lines = output_buffer.splitlines(
                        keepends=True
                    )

                    if lines and not lines[-1].endswith(
                        ("\n", "\r")
                    ):
                        output_buffer = lines.pop()
                    else:
                        output_buffer = ""

                    for line in lines:
                        output_lines.append(
                            line.rstrip()
                        )

                        if len(output_lines) > 250:
                            output_lines.pop(0)

                else:
                    try:
                        selector.unregister(
                            process.stdout
                        )
                    except Exception:
                        pass

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
                f"  {action:6} {c(CYAN, package):30} "
                f"{c(GREEN, hex_value)}"
            )

            sys.stdout.flush()

        if output_buffer:
            output_lines.append(
                output_buffer.rstrip()
            )

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

    finally:
        try:
            selector.unregister(process.stdout)
        except Exception:
            pass

        selector.close()

        try:
            process.stdout.close()
        except Exception:
            pass

    clear_line()

    return (
        process.returncode,
        "\n".join(output_lines)
    )


def run_package_update(package):
    command = PACKAGE_MANAGER.update_package(package)

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

        returncode, output = animate_package_action(
            command,
            package,
            "UPDATE"
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
                "Package manager returned a non-zero code, "
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
                "Package manager returned a non-zero code, "
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



def run_package_install(package):
    command = PACKAGE_MANAGER.install_package(package)

    print()
    print(
        c(CYAN, f"  INSTALL // {package}")
    )

    print(
        c(DIM, "  $ " + " ".join(command))
    )

    try:

        returncode, output = animate_package_action(
            command,
            package,
            "INSTALL"
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
                f"Package installation timed out after "
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

    if returncode == 0 and package_installed:

        print_bar(
            1.0,
            "success"
        )

        print()

        return {
            "package": package,
            "status": "success",
            "message": (
                f"Package installation completed successfully.\n"
                f"Returncode: {returncode}\n"
                f"Installed version: "
                f"{installed_version or 'unknown'}\n\n"
                f"{output[-3500:]}"
            ),
            "returncode": returncode
        }

    if package_installed:

        print_bar(
            1.0,
            "success"
        )

        print()

        return {
            "package": package,
            "status": "success",
            "message": (
                "Package manager returned a non-zero code, "
                "but the package is installed.\n"
                f"Returncode: {returncode}\n"
                f"Installed version: "
                f"{installed_version or 'unknown'}\n\n"
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
            f"Package installation failed.\n"
            f"Returncode: {returncode}\n"
            f"Package status: "
            f"{package_state.get('status') or 'unknown'}\n"
            f"Installed version: "
            f"{installed_version or 'unknown'}\n\n"
            f"{output[-3500:]}"
        ),
        "returncode": returncode
    }



def run_package_remove(package):
    command = PACKAGE_MANAGER.remove_package(package)

    print()
    print(
        c(CYAN, f"  REMOVE // {package}")
    )

    print(
        c(DIM, "  $ " + " ".join(command))
    )

    try:

        returncode, output = animate_package_action(
            command,
            package,
            "REMOVE"
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
                f"Package removal timed out after "
                f"{PACKAGE_TIMEOUT} seconds."
            ),
            "returncode": None
        }

    package_state = get_installed_package_state(
        package
    )

    package_installed = package_state.get(
        "installed"
    )

    if returncode == 0 and not package_installed:

        print_bar(
            1.0,
            "success"
        )

        print()

        return {
            "package": package,
            "status": "success",
            "message": (
                f"Package removal completed successfully.\n"
                f"Returncode: {returncode}\n\n"
                f"{output[-3500:]}"
            ),
            "returncode": returncode
        }

    if not package_installed:

        print_bar(
            1.0,
            "success"
        )

        print()

        return {
            "package": package,
            "status": "success",
            "message": (
                "Package manager returned a non-zero code, "
                "but the package is no longer installed.\n"
                f"Returncode: {returncode}\n\n"
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
            f"Package removal failed.\n"
            f"Returncode: {returncode}\n"
            f"Package status: "
            f"{package_state.get('status') or 'unknown'}\n\n"
            f"{output[-3500:]}"
        ),
        "returncode": returncode
    }


def run_system_update():
    command = PACKAGE_MANAGER.update_system()

    print()
    print(
        c(CYAN, "  UPDATE SYSTEM")
    )

    print(
        c(DIM, "  $ " + " ".join(command))
    )

    try:

        returncode, output = animate_package_action(
            command,
            "system",
            "SYSTEM"
        )

    except subprocess.TimeoutExpired:

        print_bar(
            0.78,
            "timeout"
        )

        print()

        return {
            "package": None,
            "status": "timeout",
            "message": (
                f"System update timed out after "
                f"{PACKAGE_TIMEOUT} seconds."
            ),
            "returncode": None
        }

    if returncode == 0:

        print_bar(
            1.0,
            "success"
        )

        print()

        return {
            "package": None,
            "status": "success",
            "message": (
                "System update completed successfully.\\n"
                f"Returncode: {returncode}\\n\\n"
                f"{output[-5000:]}"
            ),
            "returncode": returncode
        }

    print_bar(
        0.78,
        "failed"
    )

    print()

    return {
        "package": None,
        "status": "failed",
        "message": (
            "System update failed.\\n"
            f"Returncode: {returncode}\\n\\n"
            f"{output[-5000:]}"
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
    action = job.get("action", "UPDATE_PACKAGE")
    job_packages = job.get("packages", [])

    simulation = SIMULATE_UPDATES

    panel(
        "SIMULATION" if simulation else "UPDATE ENGINE"
    )

    print(
        f"  JOB        {c(CYAN, str(job_id))}"
    )

    print(
        f"  ACTION     {c(CYAN, action)}"
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
            f"  PACKAGE    "
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

    if action == "UPDATE_SYSTEM" and not simulation:

        result = run_system_update()

        results.append(result)

        if result["status"] == "success":

            status_ok(
                "SYSTEM UPDATE // SUCCESS"
            )

        elif result["status"] == "timeout":

            status_warn(
                "SYSTEM UPDATE // TIMEOUT"
            )

        else:

            status_fail(
                "SYSTEM UPDATE // FAILED"
            )

    else:

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

                if action == "UPDATE_PACKAGE":
                    simulated_command = PACKAGE_MANAGER.update_package(
                        package
                    )
                elif action == "INSTALL_PACKAGE":
                    simulated_command = PACKAGE_MANAGER.install_package(
                        package
                    )
                elif action == "REMOVE_PACKAGE":
                    simulated_command = PACKAGE_MANAGER.remove_package(
                        package
                    )
                else:
                    simulated_command = []

                print(
                    c(
                        DIM,
                        "  $ simulated "
                        + " ".join(simulated_command)
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

                if action == "UPDATE_PACKAGE":

                    result = run_package_update(
                        package
                    )

                elif action == "INSTALL_PACKAGE":

                    result = run_package_install(
                        package
                    )

                elif action == "REMOVE_PACKAGE":

                    result = run_package_remove(
                        package
                    )

                else:

                    result = {
                        "package": package,
                        "status": "failed",
                        "message": (
                            f"Unsupported package action: {action}"
                        ),
                        "returncode": None
                    }

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
