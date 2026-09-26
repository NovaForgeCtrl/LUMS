import os
import sys
from pathlib import Path
import sqlite3

os.environ.setdefault(
    "LUMS_SECRET_KEY",
    "pytest-only-test-secret",
)
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = PROJECT_ROOT / "server"
AGENT_ROOT = PROJECT_ROOT / "agent"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from server.security import (
    clear_login_rate_limit,
    hash_client_token,
    get_login_rate_limit_key,
    is_login_rate_limited,
    record_login_failure,
)


def create_rate_limit_database():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE login_rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rate_limit_key TEXT NOT NULL,
            username TEXT NOT NULL,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            first_failed_at TEXT NOT NULL,
            last_failed_at TEXT NOT NULL,
            locked_until TEXT
        )
        """
    )

    connection.commit()

    return connection


def test_get_login_rate_limit_key_normalizes_username():
    result = get_login_rate_limit_key(
        "  Admin  ",
        "192.168.2.141"
    )

    assert result == "admin|192.168.2.141"


def test_get_login_rate_limit_key_preserves_source():
    result = get_login_rate_limit_key(
        "Admin",
        "192.168.2.141"
    )

    assert result == "admin|192.168.2.141"


def test_login_rate_limit_locks_after_five_failures():
    connection = create_rate_limit_database()

    rate_limit_key = get_login_rate_limit_key(
        "Admin",
        "192.168.2.141"
    )

    for expected_attempt in range(1, 6):
        failed_attempts, locked_until = record_login_failure(
            connection,
            rate_limit_key,
            "Admin",
        )

        connection.commit()

        assert failed_attempts == expected_attempt

        if expected_attempt < 5:
            assert locked_until is None
        else:
            assert locked_until is not None

    assert is_login_rate_limited(
        connection,
        rate_limit_key,
    )

    connection.close()


def test_login_rate_limit_is_independent_per_key():
    connection = create_rate_limit_database()

    locked_key = get_login_rate_limit_key(
        "Admin",
        "192.168.2.141"
    )

    independent_key = get_login_rate_limit_key(
        "Admin",
        "192.168.2.142"
    )

    for _ in range(5):
        record_login_failure(
            connection,
            locked_key,
            "Admin",
        )
        connection.commit()

    assert is_login_rate_limited(
        connection,
        locked_key,
    )

    assert not is_login_rate_limited(
        connection,
        independent_key,
    )

    connection.close()


def test_login_rate_limit_lock_steps():
    expected_steps = {
        5: 30,
        6: 60,
        7: 120,
        8: 300,
    }

    connection = create_rate_limit_database()

    rate_limit_key = get_login_rate_limit_key(
        "Admin",
        "192.168.2.141"
    )

    for attempt in range(1, 9):
        failed_attempts, locked_until = record_login_failure(
            connection,
            rate_limit_key,
            "Admin",
        )

        connection.commit()

        assert failed_attempts == attempt

        if attempt < 5:
            assert locked_until is None
            continue

        assert locked_until is not None

        locked_until_dt = datetime.fromisoformat(
            locked_until
        )

        now = datetime.now(timezone.utc)

        remaining_seconds = (
            locked_until_dt - now
        ).total_seconds()

        expected_seconds = expected_steps[attempt]

        assert expected_seconds - 2 <= remaining_seconds <= expected_seconds + 2

    connection.close()


def test_clear_login_rate_limit_removes_lock():
    connection = create_rate_limit_database()

    rate_limit_key = get_login_rate_limit_key(
        "Admin",
        "192.168.2.141"
    )

    for _ in range(5):
        record_login_failure(
            connection,
            rate_limit_key,
            "Admin",
        )
        connection.commit()

    assert is_login_rate_limited(
        connection,
        rate_limit_key,
    )

    clear_login_rate_limit(
        connection,
        rate_limit_key,
    )
    connection.commit()

    assert not is_login_rate_limited(
        connection,
        rate_limit_key,
    )

    connection.close()


def create_report_test_database(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT UNIQUE,
            ip TEXT,
            os TEXT,
            kernel TEXT,
            architecture TEXT,
            agent_version TEXT,
            last_seen TEXT NOT NULL,
            idle INTEGER NOT NULL DEFAULT 0,
            idle_seconds INTEGER NOT NULL DEFAULT 0,
            idle_threshold_seconds INTEGER NOT NULL DEFAULT 300,
            idle_source TEXT NOT NULL DEFAULT 'unknown',
            idle_supported INTEGER NOT NULL DEFAULT 0,
            client_token_hash TEXT,
            token_created_at TEXT,
            token_revoked_at TEXT,
            enabled INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    connection.execute(
        """
        INSERT INTO clients (
            hostname,
            last_seen,
            client_token_hash,
            enabled
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            "pytest-client",
            datetime.now(timezone.utc).isoformat(),
            hash_client_token("pytest-client-token"),
            1,
        ),
    )

    connection.commit()
    connection.close()


def test_report_rejects_invalid_json(monkeypatch, tmp_path):
    from server import app

    db_path = str(tmp_path / "report-test.db")

    create_report_test_database(db_path)

    def get_test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setitem(
        app.app.config,
        "LUMS_GET_CONNECTION",
        get_test_connection,
    )

    client = app.app.test_client()

    headers = {
        "Authorization": "Bearer pytest-client-token",
    }

    cases = [
        {
            "data": "{invalid-json",
            "content_type": "application/json",
        },
        {
            "data": "",
            "content_type": "application/json",
        },
        {
            "json": [],
        },
        {
            "json": {},
        },
    ]

    for case in cases:
        response = client.post(
            "/api/report",
            headers=headers,
            **case,
        )

        assert response.status_code == 400
        assert response.get_json() == {
            "status": "error",
            "message": "Invalid or missing JSON data",
        }


def test_report_accepts_valid_json(monkeypatch, tmp_path):
    from server import app

    db_path = str(tmp_path / "report-test.db")

    create_report_test_database(db_path)

    def get_test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setitem(
        app.app.config,
        "LUMS_GET_CONNECTION",
        get_test_connection,
    )

    monkeypatch.setattr(
        app,
        "save_client",
        lambda client_id, data: client_id,
    )

    monkeypatch.setattr(
        app,
        "save_updates",
        lambda client_id, updates: None,
    )

    monkeypatch.setattr(
        app,
        "save_packages",
        lambda client_id, packages: None,
    )

    client = app.app.test_client()

    response = client.post(
        "/api/report",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
        json={
            "hostname": "test-client",
            "ip": "192.168.2.141",
            "updates": [],
            "packages": {},
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "received",
    }


def test_get_ip_uses_route_source(monkeypatch):
    import ssl

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

    import agent

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)

        class Result:
            stdout = "1.1.1.1 via 192.168.2.1 dev ens18 src 192.168.2.141 uid 1000\n"

        return Result()

    monkeypatch.setattr(agent.subprocess, "run", fake_run)

    assert agent.get_ip() == "192.168.2.141"
    assert len(calls) == 1
    assert calls[0] == [
        "ip",
        "-4",
        "route",
        "get",
        "1.1.1.1",
    ]


def test_get_ip_uses_interface_fallback(monkeypatch):
    import ssl

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

    import agent

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)

        class Result:
            pass

        if command[:5] == [
            "ip",
            "-4",
            "route",
            "get",
            "1.1.1.1",
        ]:
            raise agent.subprocess.CalledProcessError(
                1,
                command,
            )

        Result.stdout = (
            "2: ens18    inet 192.168.2.141/24 "
            "brd 192.168.2.255 scope global ens18\n"
            "3: docker0 inet 172.17.0.1/16 "
            "scope global docker0\n"
        )

        return Result()

    monkeypatch.setattr(agent.subprocess, "run", fake_run)

    assert agent.get_ip() == "192.168.2.141"
    assert len(calls) == 2
    assert calls[1] == [
        "ip",
        "-4",
        "-o",
        "addr",
        "show",
        "scope",
        "global",
    ]


def test_detect_package_manager_apt(monkeypatch):
    import package_manager

    def fake_which(command):
        if command == "apt":
            return "/usr/bin/apt"
        return None

    monkeypatch.setattr(
        package_manager.shutil,
        "which",
        fake_which,
    )

    assert (
        package_manager.detect_package_manager()
        == package_manager.PACKAGE_MANAGER_APT
    )


def test_detect_package_manager_pacman(monkeypatch):
    import package_manager

    def fake_which(command):
        if command == "pacman":
            return "/usr/bin/pacman"
        return None

    monkeypatch.setattr(
        package_manager.shutil,
        "which",
        fake_which,
    )

    assert (
        package_manager.detect_package_manager()
        == package_manager.PACKAGE_MANAGER_PACMAN
    )


def test_detect_package_manager_unknown(monkeypatch):
    import package_manager

    monkeypatch.setattr(
        package_manager.shutil,
        "which",
        lambda command: None,
    )

    assert package_manager.detect_package_manager() is None


def test_apt_package_manager_commands():
    from package_manager import AptPackageManager

    manager = AptPackageManager()

    assert manager.install_package("curl") == [
        "apt-get",
        "install",
        "-y",
        "curl",
    ]

    assert manager.remove_package("curl") == [
        "apt-get",
        "remove",
        "-y",
        "curl",
    ]

    assert manager.update_package("curl") == [
        "apt-get",
        "install",
        "--only-upgrade",
        "-y",
        "curl",
    ]

    assert manager.update_system() == [
        "apt-get",
        "upgrade",
        "-y",
    ]


def test_pacman_package_manager_commands():
    from package_manager import PacmanPackageManager

    manager = PacmanPackageManager()

    assert manager.install_package("curl") == [
        "pacman",
        "-S",
        "--noconfirm",
        "curl",
    ]

    assert manager.remove_package("curl") == [
        "pacman",
        "-R",
        "--noconfirm",
        "curl",
    ]

    assert manager.update_package("curl") == [
        "pacman",
        "-S",
        "--noconfirm",
        "curl",
    ]

    assert manager.update_system() == [
        "pacman",
        "-Syu",
        "--noconfirm",
    ]


def test_apt_get_package_state(monkeypatch):
    from package_manager import AptPackageManager

    class Result:
        stdout = "install ok installed|2.38.1-5"
        returncode = 0

    def fake_run(command, **kwargs):
        assert command == [
            "dpkg-query",
            "-W",
            "-f=${Status}|${Version}",
            "curl",
        ]
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = AptPackageManager()

    assert manager.get_package_state("curl") == {
        "installed": True,
        "status": "install ok installed",
        "version": "2.38.1-5",
        "raw": "install ok installed|2.38.1-5",
    }


def test_apt_get_package_state_not_installed(monkeypatch):
    from package_manager import AptPackageManager

    class Result:
        stdout = ""
        returncode = 1

    def fake_run(command, **kwargs):
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = AptPackageManager()

    assert manager.get_package_state("does-not-exist") == {
        "installed": False,
        "status": None,
        "version": None,
        "raw": "",
    }


def test_pacman_get_package_state(monkeypatch):
    from package_manager import PacmanPackageManager

    class Result:
        stdout = "curl 8.16.0-1\n"
        returncode = 0

    def fake_run(command, **kwargs):
        assert command == [
            "pacman",
            "-Q",
            "curl",
        ]
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = PacmanPackageManager()

    assert manager.get_package_state("curl") == {
        "installed": True,
        "status": "installed",
        "version": "8.16.0-1",
        "raw": "curl 8.16.0-1",
    }


def test_pacman_get_package_state_not_installed(monkeypatch):
    from package_manager import PacmanPackageManager

    class Result:
        stdout = ""
        returncode = 1

    def fake_run(command, **kwargs):
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = PacmanPackageManager()

    assert manager.get_package_state("does-not-exist") == {
        "installed": False,
        "status": None,
        "version": None,
        "raw": "",
    }


def test_apt_get_candidate_version(monkeypatch):
    from package_manager import AptPackageManager

    class Result:
        stdout = """curl:
  Installed: 8.16.0-1
  Candidate: 8.17.0-1
  Version table:
"""
        returncode = 0

    def fake_run(command, **kwargs):
        assert command == [
            "apt-cache",
            "policy",
            "curl",
        ]
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = AptPackageManager()

    assert manager.get_candidate_version("curl") == "8.17.0-1"


def test_apt_get_candidate_version_missing(monkeypatch):
    from package_manager import AptPackageManager

    class Result:
        stdout = """curl:
  Installed: 8.16.0-1
  Candidate: (none)
"""
        returncode = 0

    def fake_run(command, **kwargs):
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = AptPackageManager()

    assert manager.get_candidate_version("curl") == "(none)"


def test_pacman_get_candidate_version(monkeypatch):
    from package_manager import PacmanPackageManager

    class Result:
        stdout = """Repository      : core
Name            : curl
Version         : 8.17.0-1
Architecture    : x86_64
"""
        returncode = 0

    def fake_run(command, **kwargs):
        assert command == [
            "pacman",
            "-Si",
            "curl",
        ]
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = PacmanPackageManager()

    assert manager.get_candidate_version("curl") == "8.17.0-1"


def test_pacman_get_candidate_version_missing(monkeypatch):
    from package_manager import PacmanPackageManager

    class Result:
        stdout = """Repository      : core
Name            : curl
Architecture    : x86_64
"""
        returncode = 0

    def fake_run(command, **kwargs):
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = PacmanPackageManager()

    assert manager.get_candidate_version("curl") is None


def test_apt_get_installed_packages(monkeypatch):
    from package_manager import AptPackageManager

    class Result:
        stdout = """curl 8.16.0-1
openssl 3.5.1-1
"""
        returncode = 0

    def fake_run(command, **kwargs):
        assert command == [
            "dpkg-query",
            "-W",
            "-f=${binary:Package} ${Version}\n",
        ]
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = AptPackageManager()

    assert manager.get_installed_packages() == {
        "curl": "8.16.0-1",
        "openssl": "3.5.1-1",
    }


def test_pacman_get_installed_packages(monkeypatch):
    from package_manager import PacmanPackageManager

    class Result:
        stdout = """curl 8.17.0-1
openssl 3.5.2-1
"""
        returncode = 0

    def fake_run(command, **kwargs):
        assert command == [
            "pacman",
            "-Q",
        ]
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = PacmanPackageManager()

    assert manager.get_installed_packages() == {
        "curl": "8.17.0-1",
        "openssl": "3.5.2-1",
    }


def test_apt_get_updates(monkeypatch):
    from package_manager import AptPackageManager

    class Result:
        stdout = """Listing...
curl/stable 8.17.0-1 amd64 [upgradable from: 8.16.0-1]
openssl/stable 3.5.2-1 amd64 [upgradable from: 3.5.1-1]
"""
        returncode = 0

    def fake_run(command, **kwargs):
        assert command == [
            "apt",
            "list",
            "--upgradable",
        ]
        assert kwargs["env"]["LC_ALL"] == "C"
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = AptPackageManager()

    assert manager.get_updates() == [
        {
            "package": "curl",
            "installed_version": "8.16.0-1",
            "available_version": "8.17.0-1",
        },
        {
            "package": "openssl",
            "installed_version": "3.5.1-1",
            "available_version": "3.5.2-1",
        },
    ]


def test_apt_get_updates_empty(monkeypatch):
    from package_manager import AptPackageManager

    class Result:
        stdout = "Listing...\n"
        returncode = 0

    def fake_run(command, **kwargs):
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = AptPackageManager()

    assert manager.get_updates() == []


def test_pacman_get_updates(monkeypatch):
    from package_manager import PacmanPackageManager

    class Result:
        stdout = """curl 8.17.0-1
openssl 3.5.2-1
"""
        returncode = 0

    def fake_run(command, **kwargs):
        assert command == [
            "pacman",
            "-Qu",
        ]
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = PacmanPackageManager()

    assert manager.get_updates() == [
        {
            "package": "curl",
            "installed_version": None,
            "available_version": "8.17.0-1",
        },
        {
            "package": "openssl",
            "installed_version": None,
            "available_version": "3.5.2-1",
        },
    ]


def test_pacman_get_updates_empty(monkeypatch):
    from package_manager import PacmanPackageManager

    class Result:
        stdout = ""
        returncode = 0

    def fake_run(command, **kwargs):
        return Result()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = PacmanPackageManager()

    assert manager.get_updates() == []


def test_execute_job_simulation_update_package(monkeypatch):
    import agent

    monkeypatch.setattr(
        agent,
        "SIMULATE_UPDATES",
        True,
    )

    monkeypatch.setattr(
        agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    calls = []

    def fake_send_job_result(
        job_id,
        status,
        results,
        reboot,
    ):
        calls.append({
            "job_id": job_id,
            "status": status,
            "results": results,
            "reboot": reboot,
        })

        return "SIMULATION ACCEPTED"

    monkeypatch.setattr(
        agent,
        "send_job_result",
        fake_send_job_result,
    )

    def fail_if_real_update_runs(*_args, **_kwargs):
        raise AssertionError(
            "run_package_update() must not run during simulation"
        )

    monkeypatch.setattr(
        agent,
        "run_package_update",
        fail_if_real_update_runs,
    )

    job = {
        "job_id": 999,
        "action": "UPDATE_PACKAGE",
        "packages": [
            {
                "package": "curl",
            }
        ],
    }

    agent.execute_job(job)

    assert calls == [
        {
            "job_id": 999,
            "status": "success",
            "results": [
                {
                    "package": "curl",
                    "status": "success",
                    "message": "E2E simulation success.",
                    "returncode": 0,
                }
            ],
            "reboot": False,
        }
    ]


def test_execute_job_simulation_install_package(monkeypatch):
    import agent

    monkeypatch.setattr(
        agent,
        "SIMULATE_UPDATES",
        True,
    )

    monkeypatch.setattr(
        agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    calls = []

    def fake_send_job_result(
        job_id,
        status,
        results,
        reboot,
    ):
        calls.append({
            "job_id": job_id,
            "status": status,
            "results": results,
            "reboot": reboot,
        })

        return "SIMULATION ACCEPTED"

    monkeypatch.setattr(
        agent,
        "send_job_result",
        fake_send_job_result,
    )

    def fail_if_real_install_runs(*_args, **_kwargs):
        raise AssertionError(
            "run_package_install() must not run during simulation"
        )

    monkeypatch.setattr(
        agent,
        "run_package_install",
        fail_if_real_install_runs,
    )

    job = {
        "job_id": 1000,
        "action": "INSTALL_PACKAGE",
        "packages": [
            {
                "package": "curl",
            }
        ],
    }

    agent.execute_job(job)

    assert calls[0]["status"] == "success"
    assert calls[0]["reboot"] is False
    assert calls[0]["results"] == [
        {
            "package": "curl",
            "status": "success",
            "message": "E2E simulation success.",
            "returncode": 0,
        }
    ]


def test_execute_job_simulation_remove_package(monkeypatch):
    import agent

    monkeypatch.setattr(
        agent,
        "SIMULATE_UPDATES",
        True,
    )

    monkeypatch.setattr(
        agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    calls = []

    def fake_send_job_result(
        job_id,
        status,
        results,
        reboot,
    ):
        calls.append({
            "job_id": job_id,
            "status": status,
            "results": results,
            "reboot": reboot,
        })

        return "SIMULATION ACCEPTED"

    monkeypatch.setattr(
        agent,
        "send_job_result",
        fake_send_job_result,
    )

    def fail_if_real_remove_runs(*_args, **_kwargs):
        raise AssertionError(
            "run_package_remove() must not run during simulation"
        )

    monkeypatch.setattr(
        agent,
        "run_package_remove",
        fail_if_real_remove_runs,
    )

    job = {
        "job_id": 1001,
        "action": "REMOVE_PACKAGE",
        "packages": [
            {
                "package": "curl",
            }
        ],
    }

    agent.execute_job(job)

    assert calls[0]["status"] == "success"
    assert calls[0]["reboot"] is False
    assert calls[0]["results"] == [
        {
            "package": "curl",
            "status": "success",
            "message": "E2E simulation success.",
            "returncode": 0,
        }
    ]


def test_execute_job_simulation_update_system(monkeypatch):
    import agent

    monkeypatch.setattr(
        agent,
        "SIMULATE_UPDATES",
        True,
    )

    monkeypatch.setattr(
        agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    calls = []

    def fake_send_job_result(
        job_id,
        status,
        results,
        reboot,
    ):
        calls.append({
            "job_id": job_id,
            "status": status,
            "results": results,
            "reboot": reboot,
        })

        return "SIMULATION ACCEPTED"

    monkeypatch.setattr(
        agent,
        "send_job_result",
        fake_send_job_result,
    )

    def fail_if_real_system_update_runs(*_args, **_kwargs):
        raise AssertionError(
            "run_system_update() must not run during simulation"
        )

    monkeypatch.setattr(
        agent,
        "run_system_update",
        fail_if_real_system_update_runs,
    )

    job = {
        "job_id": 1002,
        "action": "UPDATE_SYSTEM",
        "packages": [],
    }

    agent.execute_job(job)

    assert calls[0]["status"] == "success"
    assert calls[0]["reboot"] is False
    assert calls[0]["results"] == []




def test_execute_job_simulation_unknown_action(monkeypatch):
    import agent

    monkeypatch.setattr(
        agent,
        "SIMULATE_UPDATES",
        True,
    )

    monkeypatch.setattr(
        agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    calls = []

    def fake_send_job_result(
        job_id,
        status,
        results,
        reboot,
    ):
        calls.append({
            "job_id": job_id,
            "status": status,
            "results": results,
            "reboot": reboot,
        })

        return "SIMULATION ACCEPTED"

    monkeypatch.setattr(
        agent,
        "send_job_result",
        fake_send_job_result,
    )

    job = {
        "job_id": 1003,
        "action": "INVALID_ACTION",
        "packages": [
            {
                "package": "curl",
            }
        ],
    }

    agent.execute_job(job)

    assert calls[0]["status"] == "success"
    assert calls[0]["reboot"] is False
    assert calls[0]["results"] == [
        {
            "package": "curl",
            "status": "success",
            "message": "E2E simulation success.",
            "returncode": 0,
        }
    ]


def test_execute_job_real_update_package_failure(monkeypatch):
    import agent

    monkeypatch.setattr(
        agent,
        "SIMULATE_UPDATES",
        False,
    )

    monkeypatch.setattr(
        agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    calls = []

    def fake_send_job_result(
        job_id,
        status,
        results,
        reboot,
    ):
        calls.append({
            "job_id": job_id,
            "status": status,
            "results": results,
            "reboot": reboot,
        })

        return "FAILURE ACCEPTED"

    monkeypatch.setattr(
        agent,
        "send_job_result",
        fake_send_job_result,
    )

    def fake_run_package_update(package):
        return {
            "package": package,
            "status": "failed",
            "message": "Simulated package update failure.",
            "returncode": 1,
        }

    monkeypatch.setattr(
        agent,
        "run_package_update",
        fake_run_package_update,
    )

    monkeypatch.setattr(
        agent,
        "reboot_required",
        lambda: False,
    )

    job = {
        "job_id": 1004,
        "action": "UPDATE_PACKAGE",
        "packages": [
            {
                "package": "curl",
            }
        ],
    }

    agent.execute_job(job)

    assert calls[0]["job_id"] == 1004
    assert calls[0]["status"] == "failed"
    assert calls[0]["reboot"] is False
    assert calls[0]["results"] == [
        {
            "package": "curl",
            "status": "failed",
            "message": "Simulated package update failure.",
            "returncode": 1,
        }
    ]


def test_execute_job_real_update_package_timeout(monkeypatch):
    import agent

    monkeypatch.setattr(
        agent,
        "SIMULATE_UPDATES",
        False,
    )

    monkeypatch.setattr(
        agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    calls = []

    def fake_send_job_result(
        job_id,
        status,
        results,
        reboot,
    ):
        calls.append({
            "job_id": job_id,
            "status": status,
            "results": results,
            "reboot": reboot,
        })

        return "TIMEOUT ACCEPTED"

    monkeypatch.setattr(
        agent,
        "send_job_result",
        fake_send_job_result,
    )

    def fake_run_package_update(package):
        return {
            "package": package,
            "status": "timeout",
            "message": "Package update timed out.",
            "returncode": None,
        }

    monkeypatch.setattr(
        agent,
        "run_package_update",
        fake_run_package_update,
    )

    monkeypatch.setattr(
        agent,
        "reboot_required",
        lambda: False,
    )

    job = {
        "job_id": 1005,
        "action": "UPDATE_PACKAGE",
        "packages": [
            {
                "package": "curl",
            }
        ],
    }

    agent.execute_job(job)

    assert calls[0]["job_id"] == 1005
    assert calls[0]["status"] == "failed"
    assert calls[0]["reboot"] is False
    assert calls[0]["results"] == [
        {
            "package": "curl",
            "status": "timeout",
            "message": "Package update timed out.",
            "returncode": None,
        }
    ]
