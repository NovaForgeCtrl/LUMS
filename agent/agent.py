#!/usr/bin/env python3

import json
import os
import platform
import socket
import ssl
import subprocess
import urllib.error
import urllib.request


AGENT_VERSION = "1.3.0"

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


def get_ip():
    return subprocess.check_output(
        [
            "bash",
            "-c",
            "ip route get 1.1.1.1 | awk '{print $7; exit}'"
        ],
        text=True
    ).strip()


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
    return {
        "hostname": socket.gethostname(),
        "ip": get_ip(),
        "os": platform.system(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "agent_version": AGENT_VERSION,
        "updates": get_updates(),
        "packages": get_packages()
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


def run_package_update(package):
    env = os.environ.copy()

    env["DEBIAN_FRONTEND"] = "noninteractive"
    env["LC_ALL"] = "C"

    command = [
        "apt-get",
        "install",
        "--only-upgrade",
        "-y",
        package
    ]

    print(
        "  $ " +
        " ".join(command)
    )

    target_version = get_candidate_version(
        package
    )

    if target_version:
        print(
            f"  Zielversion: {target_version}"
        )

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=env,
            timeout=PACKAGE_TIMEOUT
        )

    except subprocess.TimeoutExpired as error:

        stdout = error.stdout or ""
        stderr = error.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode(
                "utf-8",
                errors="replace"
            )

        if isinstance(stderr, bytes):
            stderr = stderr.decode(
                "utf-8",
                errors="replace"
            )

        output = (
            stdout +
            "\n" +
            stderr
        ).strip()

        return {
            "package": package,
            "status": "timeout",
            "message": (
                f"Package update timed out after "
                f"{PACKAGE_TIMEOUT} seconds.\n\n"
                f"{output[-3500:]}"
            ),
            "returncode": None
        }

    output = (
        result.stdout +
        "\n" +
        result.stderr
    ).strip()

    package_state = get_installed_package_state(
        package
    )

    installed_version = package_state.get(
        "version"
    )

    package_installed = package_state.get(
        "installed"
    )

    if result.returncode == 0:

        message = (
            f"Package update completed successfully.\n"
            f"Returncode: {result.returncode}\n"
            f"Installed version: "
            f"{installed_version or 'unknown'}\n\n"
            f"{output[-3500:]}"
        )

        return {
            "package": package,
            "status": "success",
            "message": message,
            "returncode": result.returncode
        }

    if (
        package_installed
        and target_version
        and installed_version == target_version
    ):

        message = (
            "apt-get returned a non-zero code, "
            "but the package is installed and the "
            "target version is present.\n"
            f"Returncode: {result.returncode}\n"
            f"Installed version: {installed_version}\n"
            f"Target version: {target_version}\n\n"
            f"{output[-3000:]}"
        )

        return {
            "package": package,
            "status": "success",
            "message": message,
            "returncode": result.returncode
        }

    if (
        package_installed
        and target_version is None
    ):

        message = (
            "apt-get returned a non-zero code, "
            "but the package is installed correctly. "
            "No candidate version was available "
            "for comparison.\n"
            f"Returncode: {result.returncode}\n"
            f"Installed version: {installed_version}\n\n"
            f"{output[-3000:]}"
        )

        return {
            "package": package,
            "status": "success",
            "message": message,
            "returncode": result.returncode
        }

    message = (
        f"Package update failed.\n"
        f"Returncode: {result.returncode}\n"
        f"Package status: "
        f"{package_state.get('status') or 'unknown'}\n"
        f"Installed version: "
        f"{installed_version or 'unknown'}\n"
        f"Target version: "
        f"{target_version or 'unknown'}\n\n"
        f"{output[-3500:]}"
    )

    return {
        "package": package,
        "status": "failed",
        "message": message,
        "returncode": result.returncode
    }


def reboot_required():
    return os.path.exists(
        "/var/run/reboot-required"
    )


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

    print()
    print("=== LUMS UPDATE JOB ===")
    print(f"Job-ID: {job_id}")
    print(f"Pakete: {len(job_packages)}")
    print()

    results = []

    for item in job_packages:

        package = item["package"]

        print(
            f"Update: {package}"
        )

        result = run_package_update(
            package
        )

        results.append(result)

        if result["status"] == "success":

            print(
                f"  ✓ {package}"
            )

        elif result["status"] == "timeout":

            print(
                f"  ⏱ {package}"
            )

        else:

            print(
                f"  ✗ {package}"
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

    reboot = reboot_required()

    print()
    print(
        f"Erfolgreich: {successful}"
    )

    print(
        f"Fehlgeschlagen: {failed}"
    )

    print(
        f"Timeout: {timed_out}"
    )

    print(
        f"Neustart erforderlich: {reboot}"
    )

    print()
    print(
        "Sende Ergebnis an LUMS..."
    )

    response = send_job_result(
        job_id,
        status,
        results,
        reboot
    )

    print(
        f"LUMS API: {response}"
    )


def main():

    data = collect_data()

    print("=== LUMS Agent ===")

    print(
        f"Hostname: {data['hostname']}"
    )

    print(
        f"IP: {data['ip']}"
    )

    print(
        f"Agent: {data['agent_version']}"
    )

    print(
        f"Updates: {len(data['updates'])}"
    )

    print(
        f"Pakete: {len(data['packages'])}"
    )

    print()
    print(
        "Sende Report an LUMS01..."
    )

    try:

        response = send_report(data)

        print(
            f"LUMS API: {response}"
        )

    except Exception as error:

        print(
            f"Fehler beim Senden des Reports: {error}"
        )

    try:

        client = get_client()

        if client is None:

            print(
                "Client nicht bei LUMS gefunden."
            )

            return

        job = get_pending_job(
            client["id"]
        )

        if not job:

            print()
            print(
                "Kein Update-Job vorhanden."
            )

            return

        if job.get("status") == "no_job":

            print()
            print(
                "Kein Update-Job vorhanden."
            )

            return

        execute_job(job)

        print()
        print(
            "Erfasse aktuellen Systemstatus nach dem Update..."
        )

        updated_data = collect_data()

        print(
            f"Updates nach dem Update: {len(updated_data['updates'])}"
        )

        print(
            "Sende aktualisierten Report an LUMS01..."
        )

        try:

            response = send_report(updated_data)

            print(
                f"LUMS API: {response}"
            )

        except Exception as error:

            print(
                f"Fehler beim Senden des aktualisierten Reports: {error}"
            )

    except Exception as error:

        print()
        print(
            f"Fehler bei der Job-Ausführung: {error}"
        )


if __name__ == "__main__":
    main()
