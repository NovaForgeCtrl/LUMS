import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_lums.py"
SPEC = importlib.util.spec_from_file_location("update_lums", MODULE_PATH)
update_lums = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(update_lums)


@pytest.fixture
def documented_container(tmp_path):
    secret = tmp_path / "lums_secret"
    secret.write_text("test-only-secret", encoding="utf-8")
    return {
        "Config": {
            "User": "lums",
            "Entrypoint": ["/app/docker-entrypoint.sh"],
            "Healthcheck": None,
            "Env": [
                "PATH=/usr/local/bin:/usr/bin",
                "LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret",
            ],
            "Labels": {"app": "lums"},
        },
        "HostConfig": {
            "NetworkMode": "bridge",
            "PortBindings": {
                "5000/tcp": [
                    {"HostIp": "127.0.0.1", "HostPort": "5050"}
                ]
            },
            "ReadonlyRootfs": True,
            "CapDrop": ["ALL"],
            "CapAdd": [],
            "SecurityOpt": ["no-new-privileges:true"],
            "Tmpfs": {
                "/tmp": "rw,noexec,nosuid,size=67108864",
                "/run": "rw,noexec,nosuid,size=16777216",
            },
            "RestartPolicy": {"Name": "unless-stopped"},
            "Privileged": False,
            "Init": False,
            "ExtraHosts": [],
            "Memory": 0,
            "MemorySwap": 0,
            "NanoCpus": 0,
            "CpuShares": 0,
            "CpuQuota": 0,
            "CpuPeriod": 0,
            "PidsLimit": 0,
        },
        "State": {"Running": True},
        "Mounts": [
            {
                "Destination": "/var/lib/lums",
                "Type": "volume",
                "Name": "lums-data",
                "RW": True,
            },
            {
                "Destination": "/run/secrets/lums_secret",
                "Type": "bind",
                "Source": str(secret),
                "RW": False,
            },
        ],
    }


def test_validate_documented_container_and_preserve_runtime_settings(
    documented_container,
):
    config = update_lums.validate_container(documented_container)

    assert config["user"] == "lums"
    assert config["secret_source"].endswith("lums_secret")
    assert config["environment"] == [
        "PATH=/usr/local/bin:/usr/bin",
        "LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret",
    ]
    assert config["labels"] == {"app": "lums"}
    args = update_lums.docker_run_arguments(config, "lums:update-test")
    assert "type=volume,src=lums-data,dst=/var/lib/lums" in args
    assert "127.0.0.1:5050:5000" in args
    assert "--read-only" in args


def test_validate_container_rejects_database_volume_changes(
    documented_container,
):
    documented_container["Mounts"][0]["Name"] = "different-volume"

    with pytest.raises(update_lums.UpdateError, match="lums-data"):
        update_lums.validate_container(documented_container)


def test_validate_container_rejects_exposed_non_loopback_port(
    documented_container,
):
    documented_container["HostConfig"]["PortBindings"]["5000/tcp"][0][
        "HostIp"
    ] = "0.0.0.0"

    with pytest.raises(update_lums.UpdateError, match="port binding"):
        update_lums.validate_container(documented_container)


def test_validate_container_rejects_unhandled_custom_environment(
    documented_container,
):
    documented_container["Config"]["Env"].append("LUMS_DB_PATH=/custom/db")

    with pytest.raises(update_lums.UpdateError, match="environment variable"):
        update_lums.validate_container(documented_container)


def test_validate_container_preserves_optional_backup_mount(
    documented_container, tmp_path,
):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    documented_container["Mounts"].append({
        "Destination": "/var/backups/lums",
        "Type": "bind",
        "Source": str(backup_directory),
        "RW": True,
    })
    documented_container["Config"]["Env"].append(
        "LUMS_BACKUP_DIR=/var/backups/lums"
    )

    config = update_lums.validate_container(documented_container)
    args = update_lums.docker_run_arguments(config, "lums:update-test")

    assert config["backup_source"] == str(backup_directory)
    assert "LUMS_BACKUP_DIR=/var/backups/lums" in args


def test_failed_health_check_restores_previous_container(
    documented_container, monkeypatch,
):
    configuration = update_lums.validate_container(documented_container)
    commands = []

    def record_sudo(command, **_kwargs):
        commands.append(command)

    def fail_health_check():
        raise update_lums.UpdateError("health check failed")

    monkeypatch.setattr(update_lums, "sudo", record_sudo)
    monkeypatch.setattr(update_lums, "check_application", fail_health_check)

    with pytest.raises(update_lums.UpdateError, match="health check failed"):
        update_lums.replace_container(
            configuration,
            "lums:update-test",
            "20261026T111213123456Z",
        )

    assert ["docker", "rename", "lums", "lums-before-upgrade-20261026T111213123456Z"] in commands
    assert ["docker", "rm", "-f", "lums"] in commands
    assert ["docker", "rename", "lums-before-upgrade-20261026T111213123456Z", "lums"] in commands
    assert ["docker", "start", "lums"] in commands
