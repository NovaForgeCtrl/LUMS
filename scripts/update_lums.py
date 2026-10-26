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
from pathlib import Path
from typing import Any

CONTAINER_NAME = "lums"
DATA_VOLUME = "lums-data"
SECRET_PATH = "/etc/lums/secrets/lums_secret"
SECRET_DESTINATION = "/run/secrets/lums_secret"
DATABASE_DESTINATION = "/var/lib/lums"
BACKUP_SOURCE = "/var/backups/lums"
BACKUP_DESTINATION = "/var/backups/lums"
EXPECTED_PORT_BINDING = "127.0.0.1:5050"
EXPECTED_CONTAINER_PORT = "5000/tcp"


class UpdateError(RuntimeError):
    """Expected, actionable updater error."""


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
    rw: bool | None = None,
) -> bool:
    for mount in mounts:
        if mount.get("Destination") != destination:
            continue
        if mount_type is not None and mount.get("Type") != mount_type:
            continue
        if source is not None and mount.get("Source") != source:
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
        source=DATA_VOLUME,
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
