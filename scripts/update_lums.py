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
import re
import shutil
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
TOKEN_PATH = "/etc/lums-host-updater/server-token"
TOKEN_DESTINATION = "/run/secrets/lums_host_updater_token"
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
    """Validate the current deployment as a source for a hardened replacement."""
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

    allowed_destinations = {
        DATABASE_DESTINATION,
        SECRET_DESTINATION,
    }
    if BACKUP_DESTINATION in mounts:
        allowed_destinations.add(BACKUP_DESTINATION)
    if TOKEN_DESTINATION in mounts:
        allowed_destinations.add(TOKEN_DESTINATION)
    if set(mounts) != allowed_destinations:
        raise UpdateError("The data, secret, token, or optional backup mounts are nonstandard.")

    data_mount = mounts[DATABASE_DESTINATION]
    data_volume = data_mount.get("Name")
    if (
        data_mount.get("Type") != "volume"
        or not isinstance(data_volume, str)
        or not data_volume
        or not data_mount.get("RW")
    ):
        raise UpdateError("The database must use a named, writable Docker volume.")

    secret_mount = mounts[SECRET_DESTINATION]
    secret_source = secret_mount.get("Source")
    if (
        secret_mount.get("Type") != "bind"
        or secret_mount.get("RW")
        or not secret_source
        or not Path(secret_source).is_file()
    ):
        raise UpdateError("The read-only application-secret mount is missing or invalid.")

    token_source = None
    if TOKEN_DESTINATION in mounts:
        token_mount = mounts[TOKEN_DESTINATION]
        token_source = token_mount.get("Source")
        if (
            token_mount.get("Type") != "bind"
            or token_mount.get("RW")
            or token_source != TOKEN_PATH
            or not Path(token_source).is_file()
        ):
            raise UpdateError("The host-updater token mount must be the expected read-only bind mount.")

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

    allowed_environment = {
        "LUMS_SECRET_KEY_FILE",
        "LUMS_BACKUP_DIR",
        "LUMS_HOST_UPDATER_TOKEN_FILE",
    }
    unexpected = set(environment) - allowed_environment
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
    if (token_source is not None) != ("LUMS_HOST_UPDATER_TOKEN_FILE" in environment):
        raise UpdateError("The updater-token mount and environment setting do not match.")
    if token_source is not None and environment["LUMS_HOST_UPDATER_TOKEN_FILE"] != TOKEN_DESTINATION:
        raise UpdateError("The updater-token environment setting is nonstandard.")

    source_tmpfs = host.get("Tmpfs") or {}
    if set(source_tmpfs) - TMPFS:
        raise UpdateError("The source container has unsupported tmpfs mount points.")
    target_tmpfs = {
        "/tmp": source_tmpfs.get("/tmp", "rw,noexec,nosuid,size=67108864"),
        "/run": source_tmpfs.get("/run", "rw,noexec,nosuid,size=16777216"),
    }

    return {
        "data_volume": data_volume,
        "secret_source": secret_source,
        "token_source": token_source,
        "backup_source": backup_source,
        "tmpfs": target_tmpfs,
        "user": config["User"],
        "environment": [
            f"{key}={value}" for key, value in sorted(environment.items())
        ],
        "labels": config.get("Labels") or {},
        # Never inherit arbitrary security options from the source container.
        "security_options": ["no-new-privileges:true"],
    }


def docker_run_arguments(configuration: dict[str, Any], image: str) -> list[str]:
    """Build a hardened replacement while retaining validated data and secrets."""
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
        f"type=volume,src={configuration['data_volume']},dst={DATABASE_DESTINATION}",
    ]

    if configuration.get("token_source"):
        args.extend([
            "--mount",
            f"type=bind,src={configuration['token_source']},dst={TOKEN_DESTINATION},readonly",
        ])

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
        ])

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
    """Check critical production invariants without changing the deployment."""
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
    if bindings != PORT_BINDINGS or not any(
        entry.get("HostIp") == "127.0.0.1"
        and entry.get("HostPort") == "5050"
        for entry in entries
    ):
        problems.append("Expected localhost-only port binding is missing or differs.")

    if config.get("Entrypoint") != ["/app/docker-entrypoint.sh"]:
        problems.append("Unexpected container entrypoint.")

    data_mounts = [
        mount for mount in mounts
        if mount.get("Destination") == DATABASE_DESTINATION
    ]
    if not (
        len(data_mounts) == 1
        and data_mounts[0].get("Type") == "volume"
        and isinstance(data_mounts[0].get("Name"), str)
        and data_mounts[0].get("Name")
        and data_mounts[0].get("RW") is True
    ):
        problems.append("A named writable database volume is missing.")

    if not mount_matches(
        mounts,
        destination=SECRET_DESTINATION,
        mount_type="bind",
        source=SECRET_PATH,
        rw=False,
    ):
        problems.append("Expected read-only application-secret mount is missing.")

    if not mount_matches(
        mounts,
        destination=TOKEN_DESTINATION,
        mount_type="bind",
        source=TOKEN_PATH,
        rw=False,
    ):
        problems.append("Expected read-only host-updater token mount is missing.")

    environment = {}
    for entry in config.get("Env") or []:
        key, separator, value = entry.partition("=")
        if separator:
            environment[key] = value
    if environment.get("LUMS_SECRET_KEY_FILE") != SECRET_DESTINATION:
        problems.append("Application-secret environment setting is nonstandard.")
    if environment.get("LUMS_HOST_UPDATER_TOKEN_FILE") != TOKEN_DESTINATION:
        problems.append("Host-updater token environment setting is missing or nonstandard.")

    backup_mounts = [
        mount for mount in mounts
        if mount.get("Destination") == BACKUP_DESTINATION
    ]
    if backup_mounts and not (
        len(backup_mounts) == 1
        and backup_mounts[0].get("Type") == "bind"
        and backup_mounts[0].get("Source") == BACKUP_SOURCE
        and backup_mounts[0].get("RW") is True
        and environment.get("LUMS_BACKUP_DIR") == BACKUP_DESTINATION
    ):
        problems.append("Optional backup mount and environment setting are inconsistent.")
    if not backup_mounts and "LUMS_BACKUP_DIR" in environment:
        problems.append("Backup environment setting exists without its mount.")

    if (host.get("RestartPolicy") or {}).get("Name") != "unless-stopped":
        problems.append("Restart policy is not unless-stopped.")
    if host.get("Privileged"):
        problems.append("Container is running in privileged mode.")

    return problems



BACKUP_FILENAME_PATTERN = re.compile(
    r"^lums-backup-\d{8}T\d{6}\.\d{6}Z-[a-f0-9]{16}\.db$"
)


def create_verified_database_backup() -> dict[str, Any]:
    """Create and verify a new SQLite backup inside the running LUMS container.

    This function does not replace or restart the container. The existing
    database backup implementation performs SQLite integrity and foreign-key
    checks before publishing the new backup.
    """
    script = r"""
import json
import re
import sqlite3
from pathlib import Path
from contextlib import closing
from database_backup import create_database_backup

directory = Path("/var/backups/lums")
database = Path("/var/lib/lums/lums.db")

if not database.is_file() or database.is_symlink():
    raise RuntimeError("Production database path is not a regular file.")
if not directory.is_dir() or directory.is_symlink():
    raise RuntimeError("Backup directory is not a real directory.")

result = create_database_backup(database, directory, "db")
filename = result.get("filename")
pattern = re.compile(
    r"^lums-backup-\d{8}T\d{6}\.\d{6}Z-[a-f0-9]{16}\.db$"
)
if not isinstance(filename, str) or not pattern.fullmatch(filename):
    raise RuntimeError("Backup implementation returned an invalid filename.")

backup = directory / filename
if backup.is_symlink() or not backup.is_file():
    raise RuntimeError("Created backup is not a regular file.")

size = backup.stat().st_size
if size <= 0 or result.get("size_bytes") != size:
    raise RuntimeError("Created backup size verification failed.")

backup_uri = backup.resolve().as_uri() + "?mode=ro&immutable=1"
with closing(sqlite3.connect(backup_uri, uri=True, timeout=10)) as connection:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()
    if integrity is None or integrity[0] != "ok":
        raise RuntimeError("Created backup failed integrity_check.")
    violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError("Created backup has foreign-key violations.")
    tables = connection.execute(
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchone()[0]
    if tables <= 0:
        raise RuntimeError("Created backup contains no application tables.")

print(json.dumps({
    "filename": filename,
    "size_bytes": size,
    "integrity": "ok",
    "foreign_key_violations": 0,
    "application_tables": tables,
}, sort_keys=True))
"""

    result = sudo(
        [
            "docker", "exec", CONTAINER_NAME,
            "python3", "-c", script,
        ],
        capture=True,
    )

    try:
        payload = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise UpdateError(
            "Backup command returned invalid JSON; update must stop."
        ) from exc

    if not isinstance(payload, dict):
        raise UpdateError(
            "Backup command returned an invalid response type; update must stop."
        )

    filename = payload.get("filename")
    size = payload.get("size_bytes")

    if not isinstance(filename, str) or not BACKUP_FILENAME_PATTERN.fullmatch(
        filename
    ):
        raise UpdateError(
            "Backup command returned an invalid filename; update must stop."
        )

    if (
        isinstance(size, bool)
        or not isinstance(size, int)
        or size <= 0
        or payload.get("integrity") != "ok"
        or payload.get("foreign_key_violations") != 0
        or isinstance(payload.get("application_tables"), bool)
        or not isinstance(payload.get("application_tables"), int)
        or payload["application_tables"] <= 0
    ):
        raise UpdateError(
            "Backup verification failed; update must stop."
        )

    return {
        "filename": filename,
        "size_bytes": size,
        "integrity": "ok",
        "foreign_key_violations": 0,
        "application_tables": payload["application_tables"],
        "directory": BACKUP_SOURCE,
    }


def validate_backup_directory(
    directory: str | Path,
    required_free_bytes: int = 0,
) -> Path:
    """Validate a backup directory and its available free space."""
    if (
        isinstance(required_free_bytes, bool)
        or not isinstance(required_free_bytes, int)
        or required_free_bytes < 0
    ):
        raise UpdateError("Required backup space must be a non-negative integer.")

    path = Path(directory)

    if path.is_symlink():
        raise UpdateError("Backup directory must not be a symbolic link.")

    if not path.exists() or not path.is_dir():
        raise UpdateError("Backup directory is missing or is not a directory.")

    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise UpdateError("Backup directory cannot be resolved safely.") from exc

    if resolved != path.absolute():
        raise UpdateError("Backup directory resolves to an unexpected path.")

    if not os.access(resolved, os.W_OK | os.X_OK):
        raise UpdateError("Backup directory is not writable by the updater.")

    try:
        free_bytes = shutil.disk_usage(resolved).free
    except OSError as exc:
        raise UpdateError("Available backup space cannot be checked.") from exc

    if free_bytes < required_free_bytes:
        raise UpdateError(
            f"Insufficient backup space: {free_bytes} bytes available; "
            f"{required_free_bytes} bytes required."
        )

    return resolved



def host_backup_preflight() -> dict[str, int | str]:
    """Read-only validation of the protected host backup directory and space."""
    database_result = sudo(
        [
            "docker", "exec", CONTAINER_NAME,
            "stat", "-c", "%s", f"{DATABASE_DESTINATION}/lums.db",
        ],
        capture=True,
    )
    raw_size = database_result.stdout.strip()
    if not raw_size.isdigit() or int(raw_size) <= 0:
        raise UpdateError(
            "Database size is missing or invalid; backup preflight refused."
        )
    database_size = int(raw_size)

    # Conservative preliminary reserve for temporary copies and overhead.
    required_bytes = database_size * 3 + 64 * 1024 * 1024

    # Inspect the fixed host path without changing permissions or creating files.
    sudo(["test", "-d", BACKUP_SOURCE])
    sudo(["test", "!", "-L", BACKUP_SOURCE])

    metadata = sudo(
        ["stat", "-c", "%F|%a|%u|%g|%n", "--", BACKUP_SOURCE],
        capture=True,
    ).stdout.strip()

    fields = metadata.split("|", 4)
    if len(fields) != 5:
        raise UpdateError("Could not parse backup directory metadata safely.")

    file_type, mode, uid, gid, actual_path = fields
    if file_type != "directory" or actual_path != BACKUP_SOURCE:
        raise UpdateError("Backup path is not the expected real directory.")
    if (mode, uid, gid) != ("700", "10001", "10001"):
        raise UpdateError(
            "Backup directory ownership or permissions differ from the "
            "expected mode 0700 and UID/GID 10001:10001."
        )

    disk_lines = sudo(
        ["df", "-Pk", "--", BACKUP_SOURCE],
        capture=True,
    ).stdout.strip().splitlines()

    if len(disk_lines) < 2:
        raise UpdateError("Could not read available host backup space.")

    columns = disk_lines[-1].split()
    if len(columns) < 6:
        raise UpdateError("Host disk-space output is malformed.")

    try:
        available_bytes = int(columns[3]) * 1024
    except (ValueError, IndexError) as exc:
        raise UpdateError("Available host backup space is invalid.") from exc

    if available_bytes < required_bytes:
        raise UpdateError(
            f"Insufficient backup space: {available_bytes} bytes available; "
            f"{required_bytes} bytes required."
        )

    return {
        "database_bytes": database_size,
        "required_bytes": required_bytes,
        "available_bytes": available_bytes,
        "directory": BACKUP_SOURCE,
    }


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

    check_main_matches_origin(root)


def check_main_matches_origin(root: Path) -> None:
    """Fetch origin/main and require HEAD to match the refreshed remote commit."""
    run(["git", "-C", str(root), "fetch", "--no-tags", "origin", "main"])

    local_commit = run(
        ["git", "-C", str(root), "rev-parse", "--verify", "HEAD^{commit}"]
    ).stdout.strip()
    remote_commit = run(
        ["git", "-C", str(root), "rev-parse", "--verify", "origin/main^{commit}"]
    ).stdout.strip()

    if not local_commit or not remote_commit or local_commit != remote_commit:
        raise UpdateError(
            "Local main does not match the freshly fetched origin/main. "
            "No deployment changes were made."
        )


def check_repository_freshness(root: Path) -> None:
    """Check branch/upstream and repository freshness without requiring a clean tree."""
    branch = run(
        ["git", "-C", str(root), "branch", "--show-current"]
    ).stdout.strip()
    if branch != "main":
        raise UpdateError(
            f"Expected branch main for repository freshness check, got '{branch}'."
        )

    upstream = run(
        [
            "git", "-C", str(root), "rev-parse",
            "--abbrev-ref", "--symbolic-full-name", "@{upstream}",
        ]
    ).stdout.strip()
    if upstream != "origin/main":
        raise UpdateError(
            f"Expected upstream origin/main, got '{upstream}'."
        )

    check_main_matches_origin(root)


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
    parser.add_argument(
        "--check-repository",
        action="store_true",
        help="fetch origin/main and compare commits without requiring a clean tree",
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

        if args.check_repository:
            check_repository_freshness(root)
            print("Repository freshness check passed. No working files were changed.")
            return 0

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

        backup_status = host_backup_preflight()
        print("\nHost backup preflight passed (read-only).")
        print(f"Backup directory: {backup_status['directory']}")
        print(f"Database size:    {backup_status['database_bytes']} bytes")
        print(f"Space required:   {backup_status['required_bytes']} bytes")
        print(f"Space available:  {backup_status['available_bytes']} bytes")

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
