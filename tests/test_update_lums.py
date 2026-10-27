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
        "LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret",
    ]
    assert config["labels"] == {"app": "lums"}
    args = update_lums.docker_run_arguments(config, "lums:update-test")
    assert "type=volume,src=lums-data,dst=/var/lib/lums" in args
    assert "127.0.0.1:5050:5000" in args
    assert "--read-only" in args


def test_validate_container_accepts_unhardened_source_but_builds_hardened_target(
    documented_container,
):
    host = documented_container["HostConfig"]
    host["ReadonlyRootfs"] = False
    host["CapDrop"] = []
    host["SecurityOpt"] = []
    host["Tmpfs"] = {}

    config = update_lums.validate_container(documented_container)
    args = update_lums.docker_run_arguments(config, "lums:update-test")

    assert "--read-only" in args
    assert "--cap-drop=ALL" in args
    assert "--security-opt=no-new-privileges:true" in args
    assert any(arg.startswith("/tmp:") for arg in args)
    assert any(arg.startswith("/run:") for arg in args)


def test_validate_container_preserves_read_only_updater_token(
    documented_container, tmp_path,
):
    token = tmp_path / "server-token"
    token.write_text("test-only-token", encoding="utf-8")
    documented_container["Mounts"].append({
        "Destination": "/run/secrets/lums_host_updater_token",
        "Type": "bind",
        "Source": "/etc/lums-host-updater/server-token",
        "RW": False,
    })
    # validate_container verifies the expected host path without reading token contents.
    # The file must exist in this test environment, so temporarily substitute Path.is_file.
    original_is_file = update_lums.Path.is_file

    def fake_is_file(path):
        if str(path) == "/etc/lums-host-updater/server-token":
            return True
        return original_is_file(path)

    update_lums.Path.is_file = fake_is_file
    try:
        documented_container["Config"]["Env"].append(
            "LUMS_HOST_UPDATER_TOKEN_FILE=/run/secrets/lums_host_updater_token"
        )
        config = update_lums.validate_container(documented_container)
        args = update_lums.docker_run_arguments(config, "lums:update-test")
    finally:
        update_lums.Path.is_file = original_is_file

    assert any(
        arg == (
            "type=bind,src=/etc/lums-host-updater/server-token,"
            "dst=/run/secrets/lums_host_updater_token,readonly"
        )
        for arg in args
    )
    assert "LUMS_HOST_UPDATER_TOKEN_FILE=/run/secrets/lums_host_updater_token" in args


def test_validate_container_preserves_actual_database_volume_name(
    documented_container,
):
    documented_container["Mounts"][0]["Name"] = "lums-data-f784d11-prod-20261026"

    config = update_lums.validate_container(documented_container)
    args = update_lums.docker_run_arguments(config, "lums:update-test")

    assert config["data_volume"] == "lums-data-f784d11-prod-20261026"
    assert (
        "type=volume,src=lums-data-f784d11-prod-20261026,dst=/var/lib/lums"
        in args
    )


def test_validate_container_rejects_exposed_non_loopback_port(
    documented_container,
):
    documented_container["HostConfig"]["PortBindings"]["5000/tcp"][0][
        "HostIp"
    ] = "0.0.0.0"

    with pytest.raises(update_lums.UpdateError, match="port binding"):
        update_lums.validate_container(documented_container)


def test_docker_run_does_not_forward_unvalidated_environment(
    documented_container,
):
    documented_container["Config"]["Env"].extend([
        "AWS_SECRET_ACCESS_KEY=must-not-be-forwarded",
        "LD_PRELOAD=/tmp/untrusted.so",
    ])

    config = update_lums.validate_container(documented_container)
    args = update_lums.docker_run_arguments(config, "lums:update-test")

    joined = "\\n".join(args)
    assert "AWS_SECRET_ACCESS_KEY" not in joined
    assert "must-not-be-forwarded" not in joined
    assert "LD_PRELOAD" not in joined
    assert "LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret" in joined


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





def test_host_backup_preflight_accepts_valid_read_only_host(monkeypatch):
    from types import SimpleNamespace

    def fake_sudo(command, *, capture=False, check=True):
        if command[:3] == ["docker", "exec", "lums"]:
            return SimpleNamespace(stdout="1000\n")
        if command[0] == "test":
            return SimpleNamespace(stdout="")
        if command[0] == "stat":
            return SimpleNamespace(
                stdout="directory|700|10001|10001|/var/backups/lums\n"
            )
        if command[0] == "df":
            return SimpleNamespace(
                stdout=(
                    "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
                    "/dev/test 1000000 100 900000 1% /var/backups\n"
                )
            )
        raise AssertionError(f"Unexpected command: {command!r}")

    monkeypatch.setattr(update_lums, "sudo", fake_sudo)
    result = update_lums.host_backup_preflight()

    assert result["database_bytes"] == 1000
    assert result["required_bytes"] == 3 * 1000 + 64 * 1024 * 1024
    assert result["available_bytes"] == 900000 * 1024
    assert result["directory"] == "/var/backups/lums"


def test_host_backup_preflight_rejects_wrong_directory_permissions(monkeypatch):
    from types import SimpleNamespace

    def fake_sudo(command, *, capture=False, check=True):
        if command[:3] == ["docker", "exec", "lums"]:
            return SimpleNamespace(stdout="1000\n")
        if command[0] == "test":
            return SimpleNamespace(stdout="")
        if command[0] == "stat":
            return SimpleNamespace(
                stdout="directory|755|10001|10001|/var/backups/lums\n"
            )
        raise AssertionError(f"Unexpected command: {command!r}")

    monkeypatch.setattr(update_lums, "sudo", fake_sudo)
    with pytest.raises(update_lums.UpdateError, match="ownership or permissions"):
        update_lums.host_backup_preflight()


def test_host_backup_preflight_rejects_insufficient_host_space(monkeypatch):
    from types import SimpleNamespace

    def fake_sudo(command, *, capture=False, check=True):
        if command[:3] == ["docker", "exec", "lums"]:
            return SimpleNamespace(stdout="1000\n")
        if command[0] == "test":
            return SimpleNamespace(stdout="")
        if command[0] == "stat":
            return SimpleNamespace(
                stdout="directory|700|10001|10001|/var/backups/lums\n"
            )
        if command[0] == "df":
            return SimpleNamespace(
                stdout=(
                    "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
                    "/dev/test 100 99 1 99% /var/backups\n"
                )
            )
        raise AssertionError(f"Unexpected command: {command!r}")

    monkeypatch.setattr(update_lums, "sudo", fake_sudo)
    with pytest.raises(update_lums.UpdateError, match="Insufficient backup space"):
        update_lums.host_backup_preflight()


def test_validate_backup_directory_rejects_insufficient_space(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    monkeypatch.setattr(
        update_lums.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=99),
    )

    with pytest.raises(update_lums.UpdateError, match="Insufficient backup space"):
        update_lums.validate_backup_directory(tmp_path, required_free_bytes=100)


def test_validate_backup_directory_accepts_sufficient_space(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    monkeypatch.setattr(
        update_lums.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=100),
    )

    assert update_lums.validate_backup_directory(
        tmp_path, required_free_bytes=100
    ) == tmp_path.resolve()


def test_validate_backup_directory_rejects_negative_space_requirement(tmp_path):
    with pytest.raises(
        update_lums.UpdateError,
        match="non-negative integer",
    ):
        update_lums.validate_backup_directory(tmp_path, required_free_bytes=-1)


def test_validate_backup_directory_accepts_existing_directory(tmp_path):
    result = update_lums.validate_backup_directory(tmp_path)
    assert result == tmp_path.resolve()


def test_validate_backup_directory_rejects_missing_directory(tmp_path):
    missing = tmp_path / "missing"

    with pytest.raises(
        update_lums.UpdateError,
        match="missing or is not a directory",
    ):
        update_lums.validate_backup_directory(missing)


def test_validate_backup_directory_rejects_file(tmp_path):
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("test", encoding="utf-8")

    with pytest.raises(
        update_lums.UpdateError,
        match="missing or is not a directory",
    ):
        update_lums.validate_backup_directory(file_path)


def test_validate_backup_directory_rejects_symlink(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(actual, target_is_directory=True)

    with pytest.raises(
        update_lums.UpdateError,
        match="symbolic link",
    ):
        update_lums.validate_backup_directory(link)


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



def test_create_verified_database_backup(monkeypatch):
    import json
    from types import SimpleNamespace

    filename = "lums-backup-20261027T120000.123456Z-0123456789abcdef.db"
    commands = []

    def fake_sudo(command, *, capture=False, check=True):
        commands.append(command)
        return SimpleNamespace(stdout=json.dumps({
            "filename": filename,
            "size_bytes": 123456,
            "integrity": "ok",
            "foreign_key_violations": 0,
            "application_tables": 12,
        }))

    monkeypatch.setattr(update_lums, "sudo", fake_sudo)

    result = update_lums.create_verified_database_backup()

    assert result["filename"] == filename
    assert result["size_bytes"] == 123456
    assert result["integrity"] == "ok"
    assert result["foreign_key_violations"] == 0
    assert result["application_tables"] == 12
    assert result["directory"] == update_lums.BACKUP_SOURCE
    assert len(commands) == 1
    assert commands[0][:4] == ["docker", "exec", "lums", "python3"]
    assert "mode=ro&immutable=1" in commands[0][5]
    assert "uri=True" in commands[0][5]


@pytest.mark.parametrize("payload", [
    "not-json",
    "[]",
    "null",
    '{"filename":"../unexpected.db","size_bytes":10,"integrity":"ok",'
    '"foreign_key_violations":0,"application_tables":1}',
    '{"filename":"lums-backup-20261027T120000.123456Z-0123456789abcdef.db",'
    '"size_bytes":0,"integrity":"ok","foreign_key_violations":0,'
    '"application_tables":1}',
    '{"filename":"lums-backup-20261027T120000.123456Z-0123456789abcdef.db",'
    '"size_bytes":10,"integrity":"failed","foreign_key_violations":0,'
    '"application_tables":1}',
    '{"filename":"lums-backup-20261027T120000.123456Z-0123456789abcdef.db",'
    '"size_bytes":10,"integrity":"ok","foreign_key_violations":1,'
    '"application_tables":1}',
    '{"filename":"lums-backup-20261027T120000.123456Z-0123456789abcdef.db",'
    '"size_bytes":10,"integrity":"ok","foreign_key_violations":0,'
    '"application_tables":0}',
])
def test_create_verified_database_backup_rejects_invalid_result(
    monkeypatch, payload,
):
    from types import SimpleNamespace

    monkeypatch.setattr(
        update_lums,
        "sudo",
        lambda command, **kwargs: SimpleNamespace(stdout=payload),
    )

    with pytest.raises(update_lums.UpdateError):
        update_lums.create_verified_database_backup()


def test_main_refuses_production_replacement_after_preflight(
    monkeypatch, capsys,
):
    from types import SimpleNamespace

    monkeypatch.setattr(update_lums.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(update_lums, "check_tools", lambda: None)
    monkeypatch.setattr(
        update_lums, "repository_root", lambda: Path("/fake/lums")
    )
    monkeypatch.setattr(update_lums, "check_git", lambda root: None)
    monkeypatch.setattr(
        update_lums, "inspect_container", lambda: {"Config": {}, "State": {}}
    )
    monkeypatch.setattr(update_lums, "validate_deployment", lambda data: [])
    monkeypatch.setattr(
        update_lums, "print_report", lambda root, data: None
    )
    monkeypatch.setattr(
        update_lums,
        "host_backup_preflight",
        lambda: {
            "directory": "/fake/backups",
            "database_bytes": 1000,
            "required_bytes": 1024,
            "available_bytes": 2048,
        },
    )

    def forbidden_replace(*args, **kwargs):
        raise AssertionError("Container replacement must not be called")

    monkeypatch.setattr(update_lums, "replace_container", forbidden_replace)
    monkeypatch.setattr("sys.argv", ["update_lums.py"])

    assert update_lums.main() == 1
    captured = capsys.readouterr()
    assert "Production replacement is intentionally disabled" in captured.err
    assert "No changes were made" not in captured.out
