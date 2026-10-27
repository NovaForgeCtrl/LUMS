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


def test_replace_container_is_disabled_by_default(
    documented_container, monkeypatch,
):
    configuration = update_lums.validate_container(documented_container)
    commands = []
    monkeypatch.setattr(
        update_lums, "sudo",
        lambda command, **kwargs: commands.append(command),
    )

    with pytest.raises(update_lums.UpdateError, match="Container replacement is disabled"):
        update_lums.replace_container(
            configuration, "lums:update-test", "test-timestamp"
        )

    assert commands == []


def test_replace_container_cannot_be_enabled_by_flag(
    documented_container, monkeypatch,
):
    configuration = update_lums.validate_container(documented_container)
    commands = []
    monkeypatch.setattr(
        update_lums, "sudo",
        lambda command, **kwargs: commands.append(command),
    )

    with pytest.raises(update_lums.UpdateError, match="Container replacement is disabled"):
        update_lums.replace_container(
            configuration,
            "lums:update-test",
            "test-timestamp",
            allow_replace=True,
        )

    assert commands == []



def test_mount_matches_volume_by_name():
    mounts = [
        {
            "Destination": "/var/lib/lums",
            "Type": "volume",
            "Name": "lums-data",
            "Source": "/var/lib/docker/volumes/lums-data/_data",
            "RW": True,
        }
    ]

    assert update_lums.mount_matches(
        mounts,
        destination="/var/lib/lums",
        mount_type="volume",
        name="lums-data",
        rw=True,
    )
    assert not update_lums.mount_matches(
        mounts,
        destination="/var/lib/lums",
        mount_type="volume",
        name="wrong-volume",
        rw=True,
    )


def test_mount_matches_bind_mount_by_source():
    mounts = [
        {
            "Destination": "/run/secrets/lums_secret",
            "Type": "bind",
            "Source": "/etc/lums/secrets/lums_secret",
            "RW": False,
        }
    ]

    assert update_lums.mount_matches(
        mounts,
        destination="/run/secrets/lums_secret",
        mount_type="bind",
        source="/etc/lums/secrets/lums_secret",
        rw=False,
    )
    assert not update_lums.mount_matches(
        mounts,
        destination="/run/secrets/lums_secret",
        mount_type="bind",
        source="/wrong/path",
        rw=False,
    )


def test_check_application_accepts_http_200(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Opener:
        def open(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(
        update_lums,
        "build_opener",
        lambda *args, **kwargs: Opener(),
    )

    update_lums.check_application()


def test_check_application_rejects_repeated_http_503(monkeypatch):
    from urllib.error import HTTPError

    class Opener:
        def __init__(self):
            self.calls = 0

        def open(self, *args, **kwargs):
            self.calls += 1
            raise HTTPError(
                url="http://127.0.0.1:5050/login",
                code=503,
                msg="Service Unavailable",
                hdrs=None,
                fp=None,
            )

    opener = Opener()
    sleeps = []

    monkeypatch.setattr(
        update_lums,
        "build_opener",
        lambda *args, **kwargs: opener,
    )
    monkeypatch.setattr(
        update_lums.time,
        "sleep",
        lambda seconds: sleeps.append(seconds),
    )

    with pytest.raises(
        update_lums.UpdateError,
        match="did not pass the local /login check",
    ):
        update_lums.check_application()

    assert opener.calls == 30
    assert sleeps == [2] * 29


def test_check_git_fetches_origin_main_and_accepts_matching_commit(
    monkeypatch, tmp_path,
):
    calls = []
    commit = "a1" * 20

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[-1] == "--porcelain":
            return type("Result", (), {"stdout": ""})()
        if "--show-current" in command:
            return type("Result", (), {"stdout": "main\n"})()
        if "--symbolic-full-name" in command:
            return type("Result", (), {"stdout": "origin/main\n"})()
        if "fetch" in command:
            return type("Result", (), {"stdout": ""})()
        if "HEAD^{commit}" in command:
            return type("Result", (), {"stdout": commit + "\n"})()
        if "origin/main^{commit}" in command:
            return type("Result", (), {"stdout": commit + "\n"})()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(update_lums, "run", fake_run)

    update_lums.check_git(tmp_path)

    fetch_index = next(i for i, cmd in enumerate(calls) if "fetch" in cmd)
    head_index = next(
        i for i, cmd in enumerate(calls) if "HEAD^{commit}" in cmd
    )
    remote_index = next(
        i for i, cmd in enumerate(calls) if "origin/main^{commit}" in cmd
    )
    assert fetch_index < head_index < remote_index
    assert calls[fetch_index][-4:] == ["fetch", "--no-tags", "origin", "main"]


def test_check_git_rejects_local_main_behind_or_different_from_remote(
    monkeypatch, tmp_path,
):
    def fake_run(command, **kwargs):
        if command[-1] == "--porcelain":
            return type("Result", (), {"stdout": ""})()
        if "--show-current" in command:
            return type("Result", (), {"stdout": "main\n"})()
        if "--symbolic-full-name" in command:
            return type("Result", (), {"stdout": "origin/main\n"})()
        if "fetch" in command:
            return type("Result", (), {"stdout": ""})()
        if "HEAD^{commit}" in command:
            return type("Result", (), {"stdout": "a1" * 20})()
        if "origin/main^{commit}" in command:
            return type("Result", (), {"stdout": "b2" * 20})()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(update_lums, "run", fake_run)

    with pytest.raises(update_lums.UpdateError, match="does not match"):
        update_lums.check_git(tmp_path)


def test_check_git_aborts_when_fetch_fails(monkeypatch, tmp_path):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[-1] == "--porcelain":
            return type("Result", (), {"stdout": ""})()
        if "--show-current" in command:
            return type("Result", (), {"stdout": "main\n"})()
        if "--symbolic-full-name" in command:
            return type("Result", (), {"stdout": "origin/main\n"})()
        if "fetch" in command:
            raise update_lums.UpdateError("simulated fetch failure")
        raise AssertionError("Commit inspection must not run after fetch fails")

    monkeypatch.setattr(update_lums, "run", fake_run)

    with pytest.raises(update_lums.UpdateError, match="fetch failure"):
        update_lums.check_git(tmp_path)

    assert any("fetch" in command for command in calls)
    assert not any("HEAD^{commit}" in command for command in calls)


def test_check_repository_freshness_fetches_and_accepts_matching_commit(
    monkeypatch, tmp_path,
):
    calls = []
    commit = "a1" * 20

    def fake_run(command, **kwargs):
        calls.append(command)
        if "--show-current" in command:
            return type("Result", (), {"stdout": "main\n"})()
        if "--symbolic-full-name" in command:
            return type("Result", (), {"stdout": "origin/main\n"})()
        if "fetch" in command:
            return type("Result", (), {"stdout": ""})()
        if "HEAD^{commit}" in command:
            return type("Result", (), {"stdout": commit + "\n"})()
        if "origin/main^{commit}" in command:
            return type("Result", (), {"stdout": commit + "\n"})()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(update_lums, "run", fake_run)
    update_lums.check_repository_freshness(tmp_path)

    fetch_index = next(i for i, command in enumerate(calls) if "fetch" in command)
    head_index = next(i for i, command in enumerate(calls) if "HEAD^{commit}" in command)
    remote_index = next(
        i for i, command in enumerate(calls)
        if "origin/main^{commit}" in command
    )
    assert calls[fetch_index][-4:] == ["fetch", "--no-tags", "origin", "main"]
    assert fetch_index < head_index < remote_index
    assert not any("--porcelain" in command for command in calls)


def test_check_repository_freshness_rejects_different_commit(
    monkeypatch, tmp_path,
):
    def fake_run(command, **kwargs):
        if "--show-current" in command:
            return type("Result", (), {"stdout": "main\n"})()
        if "--symbolic-full-name" in command:
            return type("Result", (), {"stdout": "origin/main\n"})()
        if "fetch" in command:
            return type("Result", (), {"stdout": ""})()
        if "HEAD^{commit}" in command:
            return type("Result", (), {"stdout": "a1" * 20})()
        if "origin/main^{commit}" in command:
            return type("Result", (), {"stdout": "b2" * 20})()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(update_lums, "run", fake_run)

    with pytest.raises(update_lums.UpdateError, match="does not match"):
        update_lums.check_repository_freshness(tmp_path)


def test_check_repository_freshness_aborts_when_fetch_fails(
    monkeypatch, tmp_path,
):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if "--show-current" in command:
            return type("Result", (), {"stdout": "main\n"})()
        if "--symbolic-full-name" in command:
            return type("Result", (), {"stdout": "origin/main\n"})()
        if "fetch" in command:
            raise update_lums.UpdateError("simulated fetch failure")
        raise AssertionError("Commit inspection must not run after fetch fails")

    monkeypatch.setattr(update_lums, "run", fake_run)

    with pytest.raises(update_lums.UpdateError, match="fetch failure"):
        update_lums.check_repository_freshness(tmp_path)

    assert any("fetch" in command for command in calls)
    assert not any("HEAD^{commit}" in command for command in calls)
