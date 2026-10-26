#!/usr/bin/env python3
"""Safely update the documented single-container LUMS Docker deployment."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener


CONTAINER_NAME = "lums"
DATA_VOLUME = "lums-data"
SECRET_DESTINATION = "/run/secrets/lums_secret"
DATABASE_DESTINATION = "/var/lib/lums"
BACKUP_DESTINATION = "/var/backups/lums"
BACKUP_DIRECTORY = Path(
    os.environ.get("LUMS_UPDATE_BACKUP_DIR", "/var/backups/lums-updates")
)
PORT_BINDINGS = {
    "5000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "5050"}]
}
TMPFS = {"/tmp", "/run"}


class UpdateError(RuntimeError):
    pass


def run(command, *, capture=False, check=True):
    result = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if check and result.returncode:
        detail = result.stderr.strip() if capture and result.stderr else ""
        raise UpdateError(
            f"Command failed ({result.returncode}): "
            f"{' '.join(command[:3])}{': ' + detail if detail else ''}"
        )
    return result


def sudo(command, *, capture=False, check=True):
    return run(["sudo", *command], capture=capture, check=check)


def docker_inspect():
    result = sudo(
        ["docker", "inspect", CONTAINER_NAME],
        capture=True,
        check=False,
    )
    if result.returncode:
        raise UpdateError(
            "Could not inspect the running 'lums' container. Confirm Docker "
            "is running and the production container is named 'lums'."
        )
    return json.loads(result.stdout)[0]


def validate_container(container):
    config = container["Config"]
    host = container["HostConfig"]
    if not container["State"]["Running"]:
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
        raise UpdateError(
            "The container capability-drop settings differ from the "
            "documented baseline."
        )
    if host.get("CapAdd"):
        raise UpdateError(
            "Additional Linux capabilities are configured; refusing to "
            "replace the container."
        )
    if "no-new-privileges:true" not in (host.get("SecurityOpt") or []):
        raise UpdateError("The container is missing no-new-privileges.")
    if set(host.get("Tmpfs") or {}) != TMPFS:
        raise UpdateError(
            "The container /tmp and /run tmpfs settings differ from the "
            "documented baseline."
        )
    if host.get("RestartPolicy", {}).get("Name") != "unless-stopped":
        raise UpdateError("The container restart policy is not 'unless-stopped'.")
    if host.get("Privileged"):
        raise UpdateError("The container is privileged; refusing to replace it.")
    if host.get("Init") or host.get("ExtraHosts"):
        raise UpdateError(
            "The container has unsupported custom runtime settings."
        )
    if any(
        host.get(key)
        for key in (
            "Dns", "DnsOptions", "DnsSearch", "Links", "Devices",
            "DeviceRequests", "Sysctls", "Ulimits",
        )
    ):
        raise UpdateError(
            "The container has custom DNS, device, sysctl, or ulimit "
            "settings that this updater does not replace."
        )
    if any(
        host.get(key) not in (None, 0, False)
        for key in (
            "Memory", "MemorySwap", "NanoCpus", "CpuShares",
            "CpuQuota", "CpuPeriod", "PidsLimit",
        )
    ):
        raise UpdateError(
            "Custom CPU or memory limits are configured; refusing to discard them."
        )
    if config.get("Healthcheck") or config.get("Entrypoint") != [
        "/app/docker-entrypoint.sh"
    ]:
        raise UpdateError(
            "The container entrypoint or health check differs from the image defaults."
        )

    mounts = {}
    for mount in container.get("Mounts", []):
        destination = mount["Destination"]
        if destination in mounts:
            raise UpdateError(f"Duplicate mount at {destination}.")
        mounts[destination] = mount
    if set(mounts) not in (
        {DATABASE_DESTINATION, SECRET_DESTINATION},
        {DATABASE_DESTINATION, SECRET_DESTINATION, BACKUP_DESTINATION},
    ):
        raise UpdateError(
            "The container mounts differ from the documented data, secret, "
            "and optional backup mounts."
        )
    data_mount = mounts[DATABASE_DESTINATION]
    if (
        data_mount.get("Type") != "volume"
        or data_mount.get("Name") != DATA_VOLUME
        or not data_mount.get("RW")
    ):
        raise UpdateError(
            "The database is not mounted from the expected 'lums-data' volume."
        )
    secret_mount = mounts[SECRET_DESTINATION]
    secret_source = secret_mount.get("Source")
    if (
        secret_mount.get("Type") != "bind"
        or secret_mount.get("RW")
        or not secret_source
        or not Path(secret_source).is_file()
    ):
        raise UpdateError(
            "The read-only application-secret mount is missing or invalid."
        )
    for destination, mount in mounts.items():
        if destination == DATABASE_DESTINATION:
            continue
        source = mount.get("Source", "")
        if not source or "," in source:
            raise UpdateError(f"Unsupported mount source for {destination}.")
        if destination == BACKUP_DESTINATION and (
            mount.get("Type") != "bind" or not mount.get("RW")
        ):
            raise UpdateError("The backup mount must be a writable host directory.")

    environment = {}
    for entry in config.get("Env") or []:
        if "\n" in entry or "\r" in entry:
            raise UpdateError(
                "The container has an unsupported multiline environment value."
            )
        key, separator, value = entry.partition("=")
        if separator and key.startswith("LUMS_"):
            environment[key] = value
    allowed_environment = {"LUMS_SECRET_KEY_FILE", "LUMS_BACKUP_DIR"}
    unexpected = set(environment) - allowed_environment
    if unexpected:
        raise UpdateError(
            "Unsupported custom LUMS environment variable(s): "
            + ", ".join(sorted(unexpected))
        )
    if environment.get("LUMS_SECRET_KEY_FILE") != SECRET_DESTINATION:
        raise UpdateError("The secret-file environment setting is nonstandard.")
    has_backup = BACKUP_DESTINATION in mounts
    if has_backup != ("LUMS_BACKUP_DIR" in environment):
        raise UpdateError(
            "The optional backup mount and environment setting do not match."
        )
    if has_backup and environment["LUMS_BACKUP_DIR"] != BACKUP_DESTINATION:
        raise UpdateError(
            "The backup directory environment setting is nonstandard."
        )

    return {
        "secret_source": secret_source,
        "backup_source": (
            mounts[BACKUP_DESTINATION]["Source"] if has_backup else None
        ),
        "tmpfs": host["Tmpfs"],
        "user": config["User"],
        "environment": config.get("Env") or [],
        "labels": config.get("Labels") or {},
        "security_options": host.get("SecurityOpt") or [],
    }


def repository_root():
    root = Path(__file__).resolve().parent.parent
    result = run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture=True,
        check=False,
    )
    if result.returncode:
        raise UpdateError("Run this script from a complete LUMS Git checkout.")
    return Path(result.stdout.strip())


def update_source(root):
    status = run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture=True,
    ).stdout
    if status.strip():
        raise UpdateError(
            "The Git checkout has local changes. Commit or stash them before updating."
        )
    branch = run(
        ["git", "-C", str(root), "branch", "--show-current"],
        capture=True,
    ).stdout.strip()
    if not branch:
        raise UpdateError("The Git checkout is not on a branch.")
    upstream = run(
        [
            "git", "-C", str(root), "rev-parse", "--abbrev-ref",
            "--symbolic-full-name", "@{upstream}",
        ],
        capture=True,
        check=False,
    )
    if upstream.returncode:
        raise UpdateError(
            "The current Git branch has no upstream. Configure its upstream "
            "before using this updater."
        )
    print(f"Updating branch {branch} (fast-forward only)...", flush=True)
    run(["git", "-C", str(root), "pull", "--ff-only"])
    return run(
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
        capture=True,
    ).stdout.strip()


def verify_volume():
    result = sudo(
        ["docker", "volume", "inspect", DATA_VOLUME],
        capture=True,
        check=False,
    )
    if result.returncode:
        raise UpdateError("The persistent 'lums-data' Docker volume was not found.")


def create_database_backup(timestamp):
    filename = f"lums-before-update-{timestamp}.db"
    container_path = f"/tmp/{filename}"
    if not BACKUP_DIRECTORY.is_absolute():
        raise UpdateError("LUMS_UPDATE_BACKUP_DIR must be an absolute path.")
    sudo(["mkdir", "-p", str(BACKUP_DIRECTORY)])
    sudo(["chmod", "700", str(BACKUP_DIRECTORY)])
    backup_code = (
        "import sqlite3,sys; "
        "src=sqlite3.connect('/var/lib/lums/lums.db'); "
        "dst=sqlite3.connect(sys.argv[1]); "
        "src.backup(dst); "
        "result=dst.execute('PRAGMA integrity_check').fetchone()[0]; "
        "dst.close(); src.close(); "
        "print(result); "
        "sys.exit(0 if result == 'ok' else 1)"
    )
    try:
        result = sudo(
            [
                "docker", "exec", CONTAINER_NAME, "python3", "-c",
                backup_code, container_path,
            ],
            capture=True,
        )
        if result.stdout.strip().splitlines()[-1:] != ["ok"]:
            raise UpdateError(
                "The SQLite pre-update backup failed its integrity check."
            )
        destination = BACKUP_DIRECTORY / filename
        sudo([
            "docker", "cp",
            f"{CONTAINER_NAME}:{container_path}",
            str(destination),
        ])
        sudo(["chmod", "600", str(destination)])
        host_check = sudo(
            [
                "python3", "-c",
                (
                    "import sqlite3,sys; "
                    "db=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro', "
                    "uri=True); "
                    "result=db.execute('PRAGMA integrity_check').fetchone()[0]; "
                    "db.close(); print(result); "
                    "sys.exit(0 if result == 'ok' else 1)"
                ),
                str(destination),
            ],
            capture=True,
        )
        if host_check.stdout.strip().splitlines()[-1:] != ["ok"]:
            raise UpdateError(
                "The copied pre-update backup failed its integrity check."
            )
        print(f"Verified database backup: {destination}", flush=True)
    finally:
        sudo(
            [
                "docker", "exec", CONTAINER_NAME, "rm", "-f",
                container_path,
            ],
            check=False,
        )


def docker_run_arguments(configuration, image):
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
        (
            f"type=bind,src={configuration['secret_source']},"
            f"dst={SECRET_DESTINATION},readonly"
        ),
        "--mount",
        f"type=volume,src={DATA_VOLUME},dst={DATABASE_DESTINATION}",
        "-e", f"LUMS_SECRET_KEY_FILE={SECRET_DESTINATION}",
    ]
    if configuration["backup_source"]:
        args.extend([
            "--mount",
            (
                f"type=bind,src={configuration['backup_source']},"
                f"dst={BACKUP_DESTINATION}"
            ),
            "-e", f"LUMS_BACKUP_DIR={BACKUP_DESTINATION}",
        ])
    for option in configuration["security_options"]:
        if option != "no-new-privileges:true":
            args.extend(["--security-opt", option])
    environment_file = configuration.get("environment_file")
    if environment_file:
        args.extend(["--env-file", str(environment_file)])
    for key, value in configuration["labels"].items():
        args.extend(["--label", f"{key}={value}"])
    args.append(image)
    return args


def check_application():
    opener = build_opener(ProxyHandler({}))
    for _ in range(30):
        try:
            with opener.open(
                "http://127.0.0.1:5050/login",
                timeout=3,
            ) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            time.sleep(2)
    raise UpdateError("The new LUMS container did not pass the local /login check.")


def replace_container(configuration, image, timestamp):
    rollback_name = f"lums-before-upgrade-{timestamp}"
    old_renamed = False
    try:
        sudo(["docker", "stop", CONTAINER_NAME])
        sudo(["docker", "rename", CONTAINER_NAME, rollback_name])
        old_renamed = True
        sudo(docker_run_arguments(configuration, image))
        check_application()
    except BaseException:
        print("Update failed; restoring the previous container...", file=sys.stderr)
        if old_renamed:
            sudo(["docker", "rm", "-f", CONTAINER_NAME], check=False)
            sudo(["docker", "rename", rollback_name, CONTAINER_NAME])
        sudo(["docker", "start", CONTAINER_NAME])
        raise
    print(
        f"Update is responding at /login. Previous container retained as "
        f"{rollback_name}.",
        flush=True,
    )


def main():
    if os.geteuid() == 0:
        raise UpdateError(
            "Do not run the updater with sudo; run it as your normal account. "
            "It will request Docker privileges when needed."
        )
    if shutil.which("sudo") is None or shutil.which("docker") is None:
        raise UpdateError("This updater requires sudo and Docker on the LUMS server.")
    sudo(["-v"])
    root = repository_root()
    configuration = validate_container(docker_inspect())
    verify_volume()
    commit = update_source(root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    image = f"lums:update-{commit}"
    print(f"Building {image}...", flush=True)
    sudo(["docker", "build", "--tag", image, str(root)])
    create_database_backup(timestamp)
    descriptor, env_file_name = tempfile.mkstemp(prefix="lums-update-env-")
    env_file = Path(env_file_name)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.writelines(
            f"{entry}\n" for entry in configuration["environment"]
        )
    configuration["environment_file"] = env_file
    try:
        replace_container(configuration, image, timestamp)
    finally:
        if env_file.exists():
            env_file.unlink()


if __name__ == "__main__":
    try:
        main()
    except (UpdateError, subprocess.CalledProcessError, OSError) as error:
        print(f"Update stopped: {error}", file=sys.stderr)
        sys.exit(1)
