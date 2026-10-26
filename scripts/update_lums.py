#!/usr/bin/env python3
"""Guarded updater for LUMS.

Initial conservative implementation:
- validates the repository and Docker deployment
- supports a read-only check mode
- refuses to update production until backup/rollback behavior is explicitly tested
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
from typing import Any

CONTAINER_NAME = "lums"
DATA_VOLUME = "lums-data"
SECRET_PATH = "/etc/lums/secrets/lums_secret"
SECRET_DESTINATION = "/run/secrets/lums_secret"
DATABASE_DESTINATION = "/var/lib/lums"
BACKUP_SOURCE = "/var/backups/lums"
BACKUP_DESTINATION = "/var/backups/lums"
TMPFS = {"/tmp", "/run"}
PORT_BINDINGS = {
    "5000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "5050"}]
}
EXPECTED_PORT_BINDING = "127.0.0.1:5050"
EXPECTED_CONTAINER_PORT = "5000/tcp"


class UpdateError(RuntimeError):
    """Expected, actionable updater error."""


def sudo(command, *, capture=False, check=True):
    """Run a command through sudo; callers decide when this is appropriate."""
    return run(["sudo", *command], check=check, capture=capture)


def validate_container(container: dict[str, Any]) -> dict[str, Any]:
    """Validate the documented deployment before any replacement is attempted."""
    config = container.get("Config") or {}
    host = container.get("HostConfig") or {}
    state = container.get("State") or {}

    if not state.get("Running"):
        raise UpdateError("The 'lums' container is not running.")
    if config.get("User") not in ("lums", "10001", "10001:10001"):
        raise UpdateError("The container does not use the documented LUMS user.")
    if host.get("NetworkMode") not in ("bridge", "default"):
        raise UpdateError("Only the documented Docker bridge network is supported.")
    if host.get("PortBindings") != PORT_BINDINGS:
        raise UpdateError(
            "The container port binding differs from the documented "
            "127.0.0.1:5050 -> 5000/tcp binding."
        )
    if not host.get("ReadonlyRootfs"):
        raise UpdateError("The container root filesystem is not read-only.")
    if sorted(host.get("CapDrop") or []) != ["ALL"]:
        raise UpdateError("The container must drop all Linux capabilities.")
    if host.get("CapAdd"):
        raise UpdateError("Additional Linux capabilities are not supported.")
    if "no-new-privileges:true" not in (host.get("SecurityOpt") or []):
        raise UpdateError("The container is missing no-new-privileges.")
    if set(host.get("Tmpfs") or {}) != TMPFS:
        raise UpdateError("The container /tmp and /run tmpfs settings are unsupported.")
    if host.get("RestartPolicy", {}).get("Name") != "unless-stopped":
        raise UpdateError("The container restart policy is not 'unless-stopped'.")
    if host.get("Privileged"):
        raise UpdateError("The container is privileged; refusing replacement.")
    if host.get("Init") or host.get("ExtraHosts"):
        raise UpdateError("Unsupported custom runtime settings are configured.")

    for key in (
        "Dns", "DnsOptions", "DnsSearch", "Links", "Devices",
        "DeviceRequests", "Sysctls", "Ulimits",
    ):
        if host.get(key):
            raise UpdateError(f"Unsupported custom Docker setting: {key}.")

    for key in (
        "Memory", "MemorySwap", "NanoCpus", "CpuShares",
        "CpuQuota", "CpuPeriod", "PidsLimit",
    ):
        if host.get(key) not in (None, 0, False):
            raise UpdateError(f"Custom resource limit is not supported: {key}.")

    if config.get("Healthcheck") or config.get("Entrypoint") != [
        "/app/docker-entrypoint.sh"
    ]:
        raise UpdateError("The container entrypoint or health check is nonstandard.")

    mounts: dict[str, dict[str, Any]] = {}
    for mount in container.get("Mounts", []):
        destination = mount.get("Destination")
        if not destination or destination in mounts:
            raise UpdateError(f"Missing or duplicate mount destination: {destination}.")
        mounts[destination] = mount

    allowed_mounts = {
        frozenset({DATABASE_DESTINATION, SECRET_DESTINATION}),
        frozenset({DATABASE_DESTINATION, SECRET_DESTINATION, BACKUP_DESTINATION}),
    }
    if frozenset(mounts) not in allowed_mounts:
        raise UpdateError("The data, secret, or optional backup mounts are nonstandard.")

    data_mount = mounts[DATABASE_DESTINATION]
    if (
        data_mount.get("Type") != "volume"
        or data_mount.get("Name") != DATA_VOLUME
        or not data_mount.get("RW")
    ):
        raise UpdateError("The database is not mounted from the expected 'lums-data' volume.")

    secret_mount = mounts[SECRET_DESTINATION]
    secret_source = secret_mount.get("Source")
    if (
        secret_mount.get("Type") != "bind"
        or secret_mount.get("RW")
        or not secret_source
        or not Path(secret_source).is_file()
    ):
        raise UpdateError("The read-only application-secret mount is missing or invalid.")

    backup_source = None
    if BACKUP_DESTINATION in mounts:
        backup_mount = mounts[BACKUP_DESTINATION]
        backup_source = backup_mount.get("Source")
        if (
            backup_mount.get("Type") != "bind"
            or not backup_mount.get("RW")
            or not backup_source
            or "," in backup_source
        ):
            raise UpdateError("The optional backup mount is invalid.")

    environment: dict[str, str] = {}
    for entry in config.get("Env") or []:
        if "\n" in entry or "\r" in entry:
            raise UpdateError("Multiline environment entries are unsupported.")
        key, separator, value = entry.partition("=")
        if separator and key.startswith("LUMS_"):
            environment[key] = value

    unexpected = set(environment) - {"LUMS_SECRET_KEY_FILE", "LUMS_BACKUP_DIR"}
    if unexpected:
        raise UpdateError(
            "Unsupported custom LUMS environment variable(s): "
            + ", ".join(sorted(unexpected))
        )
    if environment.get("LUMS_SECRET_KEY_FILE") != SECRET_DESTINATION:
        raise UpdateError("The secret-file environment setting is nonstandard.")
    if (backup_source is not None) != ("LUMS_BACKUP_DIR" in environment):
        raise UpdateError("The backup mount and LUMS_BACKUP_DIR setting do not match.")
    if backup_source is not None and environment["LUMS_BACKUP_DIR"] != BACKUP_DESTINATION:
        raise UpdateError("The backup directory environment setting is nonstandard.")

    return {
        "secret_source": secret_source,
        "backup_source": backup_source,
        "tmpfs": host["Tmpfs"],
        "user": config["User"],
        "environment": config.get("Env") or [],
        "labels": config.get("Labels") or {},
        "security_options": host.get("SecurityOpt") or [],
    }


def docker_run_arguments(configuration: dict[str, Any], image: str) -> list[str]:
    """Build the replacement command while retaining validated runtime settings."""
    args = [
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "--restart", "unless-stopped",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--user", configuration["user"],
        "--tmpfs", f"/tmp:{configuration['tmpfs']['/tmp']}",
        "--tmpfs", f"/run:{configuration['tmpfs']['/run']}",
        "-p", "127.0.0.1:5050:5000",
        "--mount",
        f"type=bind,src={configuration['secret_source']},dst={SECRET_DESTINATION},readonly",
        "--mount",
        f"type=volume,src={DATA_VOLUME},dst={DATABASE_DESTINATION}",
    ]

    environment_file = configuration.get("environment_file")
    if environment_file:
        args.extend(["--env-file", str(environment_file)])
    else:
        for entry in configuration.get("environment", []):
            key, separator, value = entry.partition("=")
            if separator:
                args.extend(["-e", f"{key}={value}"])

    if configuration.get("backup_source"):
        args.extend([
            "--mount",
            f"type=bind,src={configuration['backup_source']},dst={BACKUP_DESTINATION}",
            "-e", f"LUMS_BACKUP_DIR={BACKUP_DESTINATION}",
        ])

    for option in configuration.get("security_options", []):
        if option != "no-new-privileges:true":
            args.extend(["--security-opt", option])

    for key, value in configuration.get("labels", {}).items():
        args.extend(["--label", f"{key}={value}"])

    args.append(image)
    return args


def check_application() -> None:
    """Wait for the local login endpoint; this does not prove DB rollback safety."""
    opener = build_opener(ProxyHandler({}))
    for attempt in range(30):
        try:
            with opener.open("http://127.0.0.1:5050/login", timeout=3) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            if attempt < 29:
                time.sleep(2)
    raise UpdateError("The new LUMS container did not pass the local /login check.")


def replace_container(
    configuration: dict[str, Any],
    image: str,
    timestamp: str,
    *,
    allow_replace: bool = False,
) -> None:
    """Fail closed until database backup and restore are implemented.

    This function deliberately never replaces a container. The keyword
    argument is retained temporarily for compatibility with existing callers,
    but cannot enable replacement.
    """
    raise UpdateError(
        "Container replacement is disabled. Database backup, migration "
        "safety, and tested database restoration are required before "
        "container replacement can be implemented."
    )


def run(
    command: list[str],
    *,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=check,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
    except FileNotFoundError as exc:
        raise UpdateError(f"Required command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise UpdateError(
            f"Command failed ({exc.returncode}): {' '.join(command)}"
            + (f"\n{detail}" if detail else "")
        ) from exc


def repository_root() -> Path:
    root = Path(__file__).resolve().parent.parent
    if not (root / ".git").exists():
        raise UpdateError(f"Not a Git checkout: {root}")
    return root


def inspect_container() -> dict[str, Any]:
    result = run(
        [
            "sudo",
            "docker",
            "inspect",
            CONTAINER_NAME,
            "--format",
            "{{json .}}",
        ]
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise UpdateError("Docker returned invalid inspect JSON.") from exc
    return data


def mount_matches(
    mounts: list[dict[str, Any]],
    *,
    destination: str,
    mount_type: str | None = None,
    source: str | None = None,
    name: str | None = None,
    rw: bool | None = None,
) -> bool:
    for mount in mounts:
        if mount.get("Destination") != destination:
            continue
        if mount_type is not None and mount.get("Type") != mount_type:
            continue
        if source is not None and mount.get("Source") != source:
            continue
        if name is not None and mount.get("Name") != name:
            continue
        if rw is not None and mount.get("RW") is not rw:
            continue
        return True
    return False


def validate_deployment(data: dict[str, Any]) -> list[str]:
    """Check critical invariants without changing the running deployment."""
    config = data.get("Config") or {}
    host = data.get("HostConfig") or {}
    state = data.get("State") or {}
    mounts = data.get("Mounts") or []
    problems: list[str] = []

    if not state.get("Running"):
        problems.append("Production container is not running.")

    if config.get("User") != "lums":
        problems.append("Container user is not 'lums'.")

    if host.get("NetworkMode") != "bridge":
        problems.append("Unexpected Docker network mode.")

    bindings = host.get("PortBindings") or {}
    entries = bindings.get(EXPECTED_CONTAINER_PORT) or []
    if not any(
        entry.get("HostIp") == "127.0.0.1"
        and entry.get("HostPort") == "5050"
        for entry in entries
    ):
        problems.append("Expected localhost-only port binding is missing.")

    if config.get("Entrypoint") != ["/app/docker-entrypoint.sh"]:
        problems.append("Unexpected container entrypoint.")

    if not mount_matches(
        mounts,
        destination=DATABASE_DESTINATION,
        mount_type="volume",
        name=DATA_VOLUME,
        rw=True,
    ):
        problems.append("Expected writable lums-data volume is missing.")

    if not mount_matches(
        mounts,
        destination=SECRET_DESTINATION,
        mount_type="bind",
        source=SECRET_PATH,
        rw=False,
    ):
        problems.append("Expected read-only secret mount is missing.")

    if not mount_matches(
        mounts,
        destination=BACKUP_DESTINATION,
        mount_type="bind",
        source=BACKUP_SOURCE,
        rw=True,
    ):
        problems.append("Expected writable backup mount is missing.")

    restart_policy = (host.get("RestartPolicy") or {}).get("Name")
    if restart_policy != "unless-stopped":
        problems.append("Restart policy is not unless-stopped.")

    if host.get("Privileged"):
        problems.append("Container is running in privileged mode.")

    return problems


def git_status(root: Path) -> str:
    return run(
        ["git", "-C", str(root), "status", "--porcelain"]
    ).stdout.strip()


def check_git(root: Path) -> None:
    if git_status(root):
        raise UpdateError(
            "Repository has local changes. Commit or safely back them up "
            "before updating."
        )

    branch = run(
        ["git", "-C", str(root), "branch", "--show-current"]
    ).stdout.strip()

    if branch != "main":
        raise UpdateError(
            f"Refusing to update from branch '{branch}'. "
            "Switch to main deliberately before using an update workflow."
        )

    upstream = run(
        [
            "git",
            "-C",
            str(root),
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
        ]
    ).stdout.strip()

    if upstream != "origin/main":
        raise UpdateError(
            f"Expected upstream origin/main, got '{upstream}'."
        )


def check_tools() -> None:
    for tool in ("git", "python3", "sudo"):
        result = subprocess.run(
            ["sh", "-c", f"command -v {tool}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise UpdateError(f"Required tool is unavailable: {tool}")


def print_report(root: Path, data: dict[str, Any]) -> None:
    config = data.get("Config") or {}
    state = data.get("State") or {}

    commit = run(
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"]
    ).stdout.strip()

    print("LUMS guarded updater — check report")
    print("-----------------------------------")
    print(f"Repository: {root}")
    print(f"Git commit: {commit}")
    print(f"Container:  {CONTAINER_NAME}")
    print(f"Image:      {config.get('Image', '<unknown>')}")
    print(f"Running:    {state.get('Running', False)}")
    print(f"User:       {config.get('User', '<unknown>')}")
    print()
    print("No container, database, or repository changes were made.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Conservative LUMS updater and deployment checker."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check repository and deployment without changing anything",
    )
    args = parser.parse_args()

    if os.geteuid() == 0:
        print(
            "Run this script as your normal user; it invokes sudo when needed.",
            file=sys.stderr,
        )
        return 2

    try:
        check_tools()
        root = repository_root()
        check_git(root)

        data = inspect_container()
        problems = validate_deployment(data)

        print_report(root, data)

        if problems:
            print("\nDeployment checks requiring attention:")
            for problem in problems:
                print(f"- {problem}")
            print(
                "\nUpdate refused. Resolve these checks before proceeding."
            )
            return 1

        if args.check:
            print("\nChecks passed. No changes were made.")
            return 0

        raise UpdateError(
            "Production replacement is intentionally disabled in this "
            "initial implementation. Database backup, migration safety, "
            "and rollback must be tested before enabling it."
        )

    except UpdateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
