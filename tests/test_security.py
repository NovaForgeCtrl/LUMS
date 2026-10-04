import os
import sys
from pathlib import Path
import sqlite3
import subprocess
import pytest

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
    hash_password,
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


def create_login_test_database(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'administrator'
        )
        """
    )

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

    connection.execute(
        """
        INSERT INTO users (
            id,
            username,
            password_hash,
            created_at,
            enabled,
            role
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            "administrator",
            hash_password("correct-password-123"),
            datetime.now(timezone.utc).isoformat(),
            1,
            "administrator",
        ),
    )

    connection.execute(
        """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            action TEXT NOT NULL,
            target TEXT,
            result TEXT NOT NULL,
            details TEXT
        )
        """
    )

    connection.commit()
    connection.close()


def configure_login_test_app(monkeypatch, app_module, db_path):
    def get_test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(
        app_module,
        "get_connection",
        get_test_connection,
    )

    app_module.app.config.update(
        TESTING=True,
    )

    return app_module.app


def test_login_with_valid_password_creates_session(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "login-valid.db")
    create_login_test_database(db_path)

    app = configure_login_test_app(
        monkeypatch,
        app_module,
        db_path,
    )

    with app.test_client() as client:
        response = client.post(
            "/login",
            data={
                "username": "administrator",
                "password": "correct-password-123",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")

        with client.session_transaction() as session:
            assert session["user_id"] == 1
            assert session["username"] == "administrator"
            assert session["csrf_token"]


def test_login_with_invalid_password_is_rejected(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "login-invalid.db")
    create_login_test_database(db_path)

    app = configure_login_test_app(
        monkeypatch,
        app_module,
        db_path,
    )

    with app.test_client() as client:
        response = client.post(
            "/login",
            data={
                "username": "administrator",
                "password": "wrong-password",
            },
            follow_redirects=False,
        )

        assert response.status_code == 401

        with client.session_transaction() as session:
            assert "user_id" not in session
            assert "username" not in session


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

    monkeypatch.setattr(
        app,
        "get_connection",
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


def test_get_ip_falls_back_to_loopback_when_offline(monkeypatch):
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
            stdout = ""

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

        return Result()

    monkeypatch.setattr(agent.subprocess, "run", fake_run)

    assert agent.get_ip() == "127.0.0.1"
    assert len(calls) == 2

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


def test_apt_get_updates_failure(monkeypatch):
    from package_manager import AptPackageManager

    class Result:
        stdout = ""
        stderr = "Temporary APT failure."
        returncode = 100

    def fake_run(command, **kwargs):
        result = Result()

        if kwargs.get("check") and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                command,
                output=result.stdout,
                stderr=result.stderr,
            )

        return result

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = AptPackageManager()

    with pytest.raises(subprocess.CalledProcessError):
        manager.get_updates()


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


def test_pacman_get_updates_failure(monkeypatch):
    from package_manager import PacmanPackageManager

    class Result:
        stdout = ""
        stderr = "Temporary pacman failure."
        returncode = 1

    def fake_run(command, **kwargs):
        assert command == [
            "pacman",
            "-Qu",
        ]

        result = Result()

        if kwargs.get("check") and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                command,
                output=result.stdout,
                stderr=result.stderr,
            )

        return result

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = PacmanPackageManager()

    with pytest.raises(subprocess.CalledProcessError):
        manager.get_updates()


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


def test_update_job_checkpoint_persists_package_status(
    monkeypatch,
    tmp_path,
):
    from server import app

    db_path = str(tmp_path / "checkpoint-test.db")

    connection = sqlite3.connect(db_path)

    connection.execute(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY,
            hostname TEXT,
            client_token_hash TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            token_revoked_at TEXT
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE update_jobs (
            id INTEGER PRIMARY KEY,
            client_id INTEGER NOT NULL,
            status TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE update_job_packages (
            id INTEGER PRIMARY KEY,
            job_id INTEGER NOT NULL,
            package TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT
        )
        """
    )

    connection.execute(
        """
        INSERT INTO clients (
            id,
            hostname,
            client_token_hash,
            enabled
        )
        VALUES (
            1,
            'pytest-client',
            ?,
            1
        )
        """,
        (
            hash_client_token("pytest-client-token"),
        ),
    )

    connection.execute(
        """
        INSERT INTO update_jobs (
            id,
            client_id,
            status
        )
        VALUES (
            999,
            1,
            'running'
        )
        """
    )

    connection.execute(
        """
        INSERT INTO update_job_packages (
            id,
            job_id,
            package,
            status,
            message
        )
        VALUES (
            1,
            999,
            'openssl',
            'pending',
            NULL
        )
        """
    )

    connection.commit()
    connection.close()

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
        "get_connection",
        get_test_connection,
    )

    client = app.app.test_client()

    response = client.post(
        "/api/update-jobs/999/checkpoint",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
        json={
            "package": "openssl",
            "status": "success",
            "message": "Recovery update success.",
        },
    )

    assert response.status_code == 200

    assert response.get_json() == {
        "status": "checkpointed",
        "job_id": 999,
        "package": "openssl",
        "package_status": "success",
    }

    connection = sqlite3.connect(db_path)
    row = connection.execute(
        """
        SELECT status, message
        FROM update_job_packages
        WHERE job_id = 999
          AND package = 'openssl'
        """
    ).fetchone()
    connection.close()

    assert row == (
        "success",
        "Recovery update success.",
    )


def test_update_job_checkpoint_rejects_invalid_state(
    monkeypatch,
    tmp_path,
):
    from server import app

    db_path = str(tmp_path / "checkpoint-negative-test.db")

    connection = sqlite3.connect(db_path)

    connection.execute(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY,
            hostname TEXT,
            client_token_hash TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            token_revoked_at TEXT
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE update_jobs (
            id INTEGER PRIMARY KEY,
            client_id INTEGER NOT NULL,
            status TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE update_job_packages (
            id INTEGER PRIMARY KEY,
            job_id INTEGER NOT NULL,
            package TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT
        )
        """
    )

    connection.execute(
        """
        INSERT INTO clients (
            id,
            hostname,
            client_token_hash,
            enabled
        )
        VALUES (
            1,
            'pytest-client',
            ?,
            1
        )
        """,
        (
            hash_client_token("pytest-client-token"),
        ),
    )

    connection.execute(
        """
        INSERT INTO clients (
            id,
            hostname,
            client_token_hash,
            enabled
        )
        VALUES (
            2,
            'other-client',
            ?,
            1
        )
        """,
        (
            hash_client_token("other-client-token"),
        ),
    )

    connection.execute(
        """
        INSERT INTO update_jobs (
            id,
            client_id,
            status
        )
        VALUES
            (999, 1, 'running'),
            (1000, 1, 'success'),
            (1001, 2, 'running')
        """
    )

    connection.execute(
        """
        INSERT INTO update_job_packages (
            id,
            job_id,
            package,
            status,
            message
        )
        VALUES
            (1, 999, 'openssl', 'pending', NULL),
            (2, 1000, 'curl', 'success', 'Already completed.')
        """
    )

    connection.commit()
    connection.close()

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
        "get_connection",
        get_test_connection,
    )

    client = app.app.test_client()

    def post(token, job_id, payload):
        return client.post(
            f"/api/update-jobs/{job_id}/checkpoint",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json=payload,
        )

    response = post(
        "pytest-client-token",
        999,
        {
            "package": "does-not-exist",
            "status": "success",
            "message": "Invalid package.",
        },
    )
    assert response.status_code == 404
    assert response.get_json()["error"] == "package_not_found"

    response = post(
        "pytest-client-token",
        999,
        {
            "package": "openssl",
            "status": "running",
            "message": "Invalid status.",
        },
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_status"

    response = post(
        "pytest-client-token",
        999,
        {
            "package": "",
            "status": "success",
            "message": "Invalid package.",
        },
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_package"

    response = post(
        "pytest-client-token",
        1000,
        {
            "package": "curl",
            "status": "success",
            "message": "Job already finished.",
        },
    )
    assert response.status_code == 409
    assert response.get_json()["error"] == "job_not_running"

    response = post(
        "pytest-client-token",
        1001,
        {
            "package": "openssl",
            "status": "success",
            "message": "Wrong client.",
        },
    )
    assert response.status_code == 403
    assert response.get_json()["error"] == "client_access_denied"

    response = post(
        "pytest-client-token",
        404404,
        {
            "package": "openssl",
            "status": "success",
            "message": "Unknown job.",
        },
    )
    assert response.status_code == 404
    assert response.get_json()["error"] == "job_not_found"

    response = post(
        "pytest-client-token",
        999,
        {
            "package": "openssl",
            "status": "failed",
            "message": "Package failed.",
        },
    )
    assert response.status_code == 200

    connection = sqlite3.connect(db_path)
    row = connection.execute(
        """
        SELECT status, message
        FROM update_job_packages
        WHERE job_id = 999
          AND package = 'openssl'
        """
    ).fetchone()
    connection.close()

    assert row == (
        "failed",
        "Package failed.",
    )


def test_send_job_package_checkpoint(monkeypatch):
    import json
    import ssl

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

    import agent

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"CHECKPOINT ACCEPTED"

    def fake_urlopen(
        request,
        timeout,
        context,
    ):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["headers"] = dict(request.headers)
        captured["payload"] = request.data
        captured["timeout"] = timeout
        captured["context"] = context

        return FakeResponse()

    monkeypatch.setattr(
        agent.urllib.request,
        "urlopen",
        fake_urlopen,
    )

    monkeypatch.setattr(
        agent,
        "LUMS_BASE",
        "https://lums.example",
    )

    monkeypatch.setattr(
        agent,
        "get_auth_headers",
        lambda extra=None: {
            **{
                "Authorization": "Bearer test-token",
            },
            **(extra or {}),
        },
    )

    response = agent.send_job_package_checkpoint(
        999,
        "openssl",
        "success",
        "Recovery update success.",
    )

    assert response == "CHECKPOINT ACCEPTED"
    assert captured["url"] == (
        "https://lums.example/api/update-jobs/999/checkpoint"
    )
    assert captured["method"] == "POST"
    assert captured["timeout"] == 10

    payload = json.loads(
        captured["payload"].decode("utf-8")
    )

    assert payload == {
        "package": "openssl",
        "status": "success",
        "message": "Recovery update success.",
    }

    assert captured["headers"]["Authorization"] == (
        "Bearer test-token"
    )
    assert captured["headers"]["Content-type"] == (
        "application/json"
    )


def test_execute_job_checkpoint_failure_does_not_report_success(
    monkeypatch,
):
    import ssl

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

    import agent

    monkeypatch.setattr(
        agent,
        "SIMULATE_UPDATES",
        False,
    )

    monkeypatch.setattr(
        agent,
        "reboot_required",
        lambda: False,
    )

    update_calls = []
    result_calls = []

    def fake_run_package_update(package):
        update_calls.append(package)

        return {
            "package": package,
            "status": "success",
            "message": "Package update succeeded.",
            "returncode": 0,
        }

    def failing_checkpoint(
        job_id,
        package,
        status,
        message,
    ):
        raise RuntimeError(
            "Checkpoint server unavailable."
        )

    def fake_send_job_result(
        job_id,
        status,
        results,
        reboot,
    ):
        result_calls.append({
            "job_id": job_id,
            "status": status,
            "results": results,
            "reboot": reboot,
        })

        return "RESULT ACCEPTED"

    monkeypatch.setattr(
        agent,
        "run_package_update",
        fake_run_package_update,
    )

    monkeypatch.setattr(
        agent,
        "send_job_package_checkpoint",
        failing_checkpoint,
    )

    monkeypatch.setattr(
        agent,
        "send_job_result",
        fake_send_job_result,
    )

    job = {
        "job_id": 1000,
        "action": "UPDATE_PACKAGE",
        "packages": [
            {
                "package": "openssl",
                "target_version": "2.0",
                "status": "pending",
            },
        ],
    }

    try:
        agent.execute_job(job)
    except RuntimeError as error:
        assert str(error) == (
            "Checkpoint server unavailable."
        )

    assert update_calls == ["openssl"]

    assert result_calls == []

def test_execute_job_resumes_only_unfinished_packages(monkeypatch):
    import ssl

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

    import agent

    monkeypatch.setattr(
        agent,
        "SIMULATE_UPDATES",
        False,
    )

    monkeypatch.setattr(
        agent,
        "reboot_required",
        lambda: False,
    )

    update_calls = []
    checkpoint_calls = []
    result_calls = []

    def fake_run_package_update(package):
        update_calls.append(package)

        return {
            "package": package,
            "status": "success",
            "message": "Recovery update success.",
            "returncode": 0,
        }

    def fake_checkpoint_job_package(
        job_id,
        package,
        status,
        message,
    ):
        checkpoint_calls.append({
            "job_id": job_id,
            "package": package,
            "status": status,
            "message": message,
        })

        return "CHECKPOINT ACCEPTED"

    def fake_send_job_result(
        job_id,
        status,
        results,
        reboot,
    ):
        result_calls.append({
            "job_id": job_id,
            "status": status,
            "results": results,
            "reboot": reboot,
        })

        return "RESULT ACCEPTED"

    monkeypatch.setattr(
        agent,
        "run_package_update",
        fake_run_package_update,
    )

    monkeypatch.setattr(
        agent,
        "send_job_package_checkpoint",
        fake_checkpoint_job_package,
        raising=False,
    )

    monkeypatch.setattr(
        agent,
        "send_job_result",
        fake_send_job_result,
    )

    job = {
        "job_id": 999,
        "action": "UPDATE_PACKAGE",
        "packages": [
            {
                "package": "curl",
                "target_version": "1.0",
                "status": "success",
            },
            {
                "package": "openssl",
                "target_version": "2.0",
                "status": "pending",
            },
        ],
    }

    agent.execute_job(job)

    assert update_calls == [
        "openssl",
    ]

    assert checkpoint_calls == [
        {
            "job_id": 999,
            "package": "openssl",
            "status": "success",
            "message": "Recovery update success.",
        }
    ]

    assert result_calls[0]["job_id"] == 999
    assert result_calls[0]["status"] == "success"
    assert result_calls[0]["reboot"] is False


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
    import ssl

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

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

    checkpoint_calls = []

    def fake_send_job_package_checkpoint(
        job_id,
        package,
        status,
        message,
    ):
        checkpoint_calls.append({
            "job_id": job_id,
            "package": package,
            "status": status,
            "message": message,
        })

        return "CHECKPOINT ACCEPTED"

    monkeypatch.setattr(
        agent,
        "send_job_package_checkpoint",
        fake_send_job_package_checkpoint,
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
    import ssl

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

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

    checkpoint_calls = []

    def fake_send_job_package_checkpoint(
        job_id,
        package,
        status,
        message,
    ):
        checkpoint_calls.append({
            "job_id": job_id,
            "package": package,
            "status": status,
            "message": message,
        })

        return "CHECKPOINT ACCEPTED"

    monkeypatch.setattr(
        agent,
        "send_job_package_checkpoint",
        fake_send_job_package_checkpoint,
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


def test_login_required_revokes_session_when_user_disabled(monkeypatch, tmp_path):
    from server import app as app_module

    db_path = str(tmp_path / "session-revocation.db")

    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'administrator'
        )
        """
    )
    connection.execute(
        """
        INSERT INTO users (
            id,
            username,
            password_hash,
            enabled,
            role
        )
        VALUES (
            1,
            'admin',
            'pytest-password-hash',
            1,
            'administrator'
        )
        """
    )
    connection.commit()
    connection.close()

    def get_test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setitem(
        app_module.app.config,
        "LUMS_GET_CONNECTION",
        get_test_connection,
    )

    client = app_module.app.test_client()

    with client.session_transaction() as session:
        session["user_id"] = 1
        session["username"] = "admin"
        session.permanent = True

    connection = sqlite3.connect(db_path)
    connection.execute(
        "UPDATE users SET enabled = 0 WHERE id = 1"
    )
    connection.commit()
    connection.close()

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    with client.session_transaction() as session:
        assert "user_id" not in session
        assert "username" not in session


def test_client_token_rotation_invalidates_old_token(monkeypatch, tmp_path):
    from server import app
    from server.security import authenticate_client

    db_path = str(tmp_path / "token-rotation.db")

    create_report_test_database(db_path)

    connection = sqlite3.connect(db_path)

    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'administrator'
        )
        """
    )

    connection.execute(
        """
        INSERT INTO users (
            id,
            username,
            password_hash,
            enabled,
            role
        )
        VALUES (
            1,
            'admin',
            'pytest-password-hash',
            1,
            'administrator'
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id INTEGER,
            action TEXT NOT NULL,
            target TEXT,
            result TEXT NOT NULL,
            details TEXT
        )
        """
    )

    connection.commit()
    connection.close()

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
        "get_connection",
        get_test_connection,
    )

    client = app.app.test_client()

    with client.session_transaction() as session:
        session["user_id"] = 1
        session["username"] = "admin"
        session["csrf_token"] = "pytest-csrf-token"
        session.permanent = True

    old_token = "pytest-client-token"

    response = client.post(
        "/api/clients/1/token/rotate",
        headers={
            "X-CSRF-Token": "pytest-csrf-token",
        },
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["status"] == "rotated"
    assert payload["client"]["id"] == 1
    assert payload["client"]["hostname"] == "pytest-client"

    new_token = payload["token"]

    assert new_token
    assert new_token != old_token

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    row = connection.execute(
        """
        SELECT
            client_token_hash,
            token_created_at,
            token_revoked_at,
            enabled
        FROM clients
        WHERE id = 1
        """
    ).fetchone()

    assert row["enabled"] == 1
    assert row["token_created_at"] is not None
    assert row["token_revoked_at"] is None
    assert row["client_token_hash"] == hash_client_token(
        new_token
    )
    assert row["client_token_hash"] != hash_client_token(
        old_token
    )

    connection.close()

    with app.app.test_request_context(
        "/api/client/me",
        headers={
            "Authorization": f"Bearer {old_token}",
        },
    ):
        connection = get_test_connection()

        try:
            assert authenticate_client(connection) is None
        finally:
            connection.close()

    with app.app.test_request_context(
        "/api/client/me",
        headers={
            "Authorization": f"Bearer {new_token}",
        },
    ):
        connection = get_test_connection()

        try:
            authenticated = authenticate_client(connection)

            assert authenticated is not None
            assert authenticated["id"] == 1
            assert authenticated["hostname"] == "pytest-client"
        finally:
            connection.close()


def test_reboot_required_debian_marker(monkeypatch):
    import ssl

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

    import agent

    monkeypatch.setattr(
        agent.os.path,
        "exists",
        lambda path: path == "/var/run/reboot-required",
    )

    monkeypatch.setattr(
        agent.shutil,
        "which",
        lambda command: None,
    )

    assert agent.reboot_required() is True


def test_reboot_required_debian_without_marker(monkeypatch):
    import ssl

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

    import agent

    monkeypatch.setattr(
        agent.os.path,
        "exists",
        lambda path: False,
    )

    monkeypatch.setattr(
        agent.shutil,
        "which",
        lambda command: None,
    )

    assert agent.reboot_required() is False


def test_reboot_required_arch_running_kernel_is_installed(
    monkeypatch,
):
    import ssl

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

    import agent

    monkeypatch.setattr(
        agent.os.path,
        "exists",
        lambda path: False,
    )

    monkeypatch.setattr(
        agent.shutil,
        "which",
        lambda command: "/usr/bin/pacman",
    )

    monkeypatch.setattr(
        agent.platform,
        "release",
        lambda: "7.2.6-arch2-1",
    )

    class Result:
        stdout = (
            "linux /usr/lib/modules/\n"
            "linux /usr/lib/modules/7.2.6-arch2-1/\n"
            "linux /usr/lib/modules/7.2.6-arch2-1/kernel/\n"
        )

    monkeypatch.setattr(
        agent.subprocess,
        "run",
        lambda *args, **kwargs: Result(),
    )

    assert agent.reboot_required() is False


def test_reboot_required_arch_new_kernel_installed(
    monkeypatch,
):
    import ssl

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

    import agent

    monkeypatch.setattr(
        agent.os.path,
        "exists",
        lambda path: False,
    )

    monkeypatch.setattr(
        agent.shutil,
        "which",
        lambda command: "/usr/bin/pacman",
    )

    monkeypatch.setattr(
        agent.platform,
        "release",
        lambda: "7.2.6-arch2-1",
    )

    class Result:
        stdout = (
            "linux /usr/lib/modules/\n"
            "linux /usr/lib/modules/7.2.7-arch3-1/\n"
            "linux /usr/lib/modules/7.2.7-arch3-1/kernel/\n"
        )

    monkeypatch.setattr(
        agent.subprocess,
        "run",
        lambda *args, **kwargs: Result(),
    )

    assert agent.reboot_required() is True


def test_reboot_required_arch_pacman_failure(
    monkeypatch,
):
    import ssl
    import subprocess

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

    import agent

    monkeypatch.setattr(
        agent.os.path,
        "exists",
        lambda path: False,
    )

    monkeypatch.setattr(
        agent.shutil,
        "which",
        lambda command: "/usr/bin/pacman",
    )

    monkeypatch.setattr(
        agent.platform,
        "release",
        lambda: "7.2.6-arch2-1",
    )

    def failing_run(*args, **kwargs):
        raise subprocess.CalledProcessError(
            1,
            ["pacman", "-Ql", "linux"],
        )

    monkeypatch.setattr(
        agent.subprocess,
        "run",
        failing_run,
    )

    assert agent.reboot_required() is False

# ============================================================
# UPDATE JOB RESULT API
# ============================================================

def create_update_job_result_database(db_path):
    connection = sqlite3.connect(db_path)

    connection.execute(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY,
            hostname TEXT,
            client_token_hash TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            token_revoked_at TEXT
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE update_jobs (
            id INTEGER PRIMARY KEY,
            client_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT,
            started_at TEXT,
            finished_at TEXT,
            reboot_required INTEGER NOT NULL DEFAULT 0,
            action TEXT
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE update_job_packages (
            id INTEGER PRIMARY KEY,
            job_id INTEGER NOT NULL,
            package TEXT NOT NULL,
            installed_version TEXT,
            target_version TEXT,
            status TEXT NOT NULL,
            message TEXT
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE update_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            package_count INTEGER NOT NULL,
            successful_count INTEGER NOT NULL,
            failed_count INTEGER NOT NULL,
            reboot_required INTEGER NOT NULL,
            started_at TEXT,
            finished_at TEXT
        )
        """
    )

    connection.execute(
        """
        INSERT INTO clients (
            id,
            hostname,
            client_token_hash,
            enabled
        )
        VALUES
            (1, 'pytest-client', ?, 1),
            (2, 'other-client', ?, 1)
        """,
        (
            hash_client_token("pytest-client-token"),
            hash_client_token("other-client-token"),
        ),
    )

    connection.execute(
        """
        INSERT INTO update_jobs (
            id,
            client_id,
            status,
            created_at,
            started_at,
            reboot_required,
            action
        )
        VALUES
            (
                999,
                1,
                'running',
                '2026-09-26T10:00:00+00:00',
                '2026-09-26T10:01:00+00:00',
                0,
                'UPDATE_PACKAGE'
            ),
            (
                1000,
                1,
                'success',
                '2026-09-26T09:00:00+00:00',
                '2026-09-26T09:01:00+00:00',
                0,
                'UPDATE_PACKAGE'
            ),
            (
                1001,
                2,
                'running',
                '2026-09-26T10:00:00+00:00',
                '2026-09-26T10:01:00+00:00',
                0,
                'UPDATE_PACKAGE'
            )
        """
    )

    connection.execute(
        """
        INSERT INTO update_job_packages (
            id,
            job_id,
            package,
            installed_version,
            target_version,
            status,
            message
        )
        VALUES
            (
                1,
                999,
                'openssl',
                '3.5.2-1',
                '3.5.3-1',
                'pending',
                NULL
            )
        """
    )

    connection.commit()
    connection.close()


def setup_update_job_result_test(
    monkeypatch,
    tmp_path,
):
    from server import app

    db_path = str(
        tmp_path / "update-job-result-test.db"
    )

    create_update_job_result_database(
        db_path
    )

    def get_test_connection():
        connection = sqlite3.connect(
            db_path
        )
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setitem(
        app.app.config,
        "LUMS_GET_CONNECTION",
        get_test_connection,
    )

    monkeypatch.setattr(
        app,
        "get_connection",
        get_test_connection,
    )

    client = app.app.test_client()

    return client, get_test_connection


def test_update_job_result_accepts_valid_result(
    monkeypatch,
    tmp_path,
):
    client, get_connection = (
        setup_update_job_result_test(
            monkeypatch,
            tmp_path,
        )
    )

    response = client.post(
        "/api/update-jobs/999/result",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
        json={
            "status": "success",
            "reboot_required": False,
            "packages": [
                {
                    "package": "openssl",
                    "status": "success",
                    "message": "Update successful.",
                }
            ],
        },
    )

    assert response.status_code == 200

    assert response.get_json() == {
        "status": "ok",
        "job_id": 999,
        "job_status": "success",
        "successful_count": 1,
        "failed_count": 0,
        "reboot_required": False,
    }

    connection = get_connection()

    job = connection.execute(
        """
        SELECT status, reboot_required
        FROM update_jobs
        WHERE id = 999
        """
    ).fetchone()

    package = connection.execute(
        """
        SELECT status, message
        FROM update_job_packages
        WHERE job_id = 999
          AND package = 'openssl'
        """
    ).fetchone()

    history = connection.execute(
        """
        SELECT
            status,
            package_count,
            successful_count,
            failed_count
        FROM update_history
        WHERE job_id = 999
        """
    ).fetchone()

    connection.close()

    assert job["status"] == "success"
    assert job["reboot_required"] == 0

    assert package["status"] == "success"
    assert package["message"] == "Update successful."

    assert history["status"] == "success"
    assert history["package_count"] == 1
    assert history["successful_count"] == 1
    assert history["failed_count"] == 0


def test_update_job_result_rejects_unknown_job(
    monkeypatch,
    tmp_path,
):
    client, _ = setup_update_job_result_test(
        monkeypatch,
        tmp_path,
    )

    response = client.post(
        "/api/update-jobs/9999/result",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
        json={
            "status": "success",
            "packages": [],
        },
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "error": "job not found"
    }


def test_update_job_result_rejects_foreign_client(
    monkeypatch,
    tmp_path,
):
    client, _ = setup_update_job_result_test(
        monkeypatch,
        tmp_path,
    )

    response = client.post(
        "/api/update-jobs/1001/result",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
        json={
            "status": "success",
            "packages": [],
        },
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "client_access_denied"
    }


def test_update_job_result_rejects_non_running_job(
    monkeypatch,
    tmp_path,
):
    client, _ = setup_update_job_result_test(
        monkeypatch,
        tmp_path,
    )

    response = client.post(
        "/api/update-jobs/1000/result",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
        json={
            "status": "success",
            "packages": [],
        },
    )

    assert response.status_code == 409

    assert response.get_json() == {
        "error": "job_not_running",
        "job_id": 1000,
        "job_status": "success",
    }


def test_update_job_result_rejects_invalid_job_status(
    monkeypatch,
    tmp_path,
):
    client, _ = setup_update_job_result_test(
        monkeypatch,
        tmp_path,
    )

    response = client.post(
        "/api/update-jobs/999/result",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
        json={
            "status": "banana",
            "packages": [],
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid status"
    }


def test_update_job_result_requires_package_list(
    monkeypatch,
    tmp_path,
):
    client, _ = setup_update_job_result_test(
        monkeypatch,
        tmp_path,
    )

    response = client.post(
        "/api/update-jobs/999/result",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
        json={
            "status": "success",
            "packages": "openssl",
        },
    )

    assert response.status_code == 400


def test_update_job_result_requires_package_objects(
    monkeypatch,
    tmp_path,
):
    client, _ = setup_update_job_result_test(
        monkeypatch,
        tmp_path,
    )

    response = client.post(
        "/api/update-jobs/999/result",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
        json={
            "status": "success",
            "packages": [
                "openssl"
            ],
        },
    )

    assert response.status_code == 400


def test_update_job_result_rejects_invalid_package_status(
    monkeypatch,
    tmp_path,
):
    client, _ = setup_update_job_result_test(
        monkeypatch,
        tmp_path,
    )

    response = client.post(
        "/api/update-jobs/999/result",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
        json={
            "status": "success",
            "packages": [
                {
                    "package": "openssl",
                    "status": "banana",
                }
            ],
        },
    )

    assert response.status_code == 400


def test_update_job_result_rejects_package_not_in_job(
    monkeypatch,
    tmp_path,
):
    client, _ = setup_update_job_result_test(
        monkeypatch,
        tmp_path,
    )

    response = client.post(
        "/api/update-jobs/999/result",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
        json={
            "status": "success",
            "packages": [
                {
                    "package": "does-not-exist",
                    "status": "success",
                }
            ],
        },
    )

    assert response.status_code == 400


def test_apt_search_packages(monkeypatch):
    from package_manager import AptPackageManager

    captured = []

    class SearchResult:
        stdout = (
            "nginx - small, powerful, scalable web server\n"
            "nginx-common - small, powerful, scalable web server - common files\n"
            "nginx-core - nginx core server\n"
        )

    class ShowResult:
        stdout = (
            "Package: nginx\n"
            "Version: 1.30.5-1\n"
            "\n"
            "Package: nginx-common\n"
            "Version: 1.30.5-1\n"
        )

    def fake_run(command, **kwargs):
        captured.append({
            "command": command,
            "kwargs": kwargs,
        })

        if command == [
            "apt-cache",
            "search",
            "nginx",
        ]:
            return SearchResult()

        if command == [
            "apt-cache",
            "show",
            "nginx",
            "nginx-common",
        ]:
            return ShowResult()

        raise AssertionError(
            f"Unexpected command: {command}"
        )

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = AptPackageManager()

    results = manager.search_packages(
        "nginx",
        max_results=2,
    )

    assert [entry["command"] for entry in captured] == [
        [
            "apt-cache",
            "search",
            "nginx",
        ],
        [
            "apt-cache",
            "show",
            "nginx",
            "nginx-common",
        ],
    ]

    assert len(results) == 2

    assert results[0] == {
        "package": "nginx",
        "version": "1.30.5-1",
        "description": (
            "small, powerful, scalable web server"
        ),
    }

    assert results[1] == {
        "package": "nginx-common",
        "version": "1.30.5-1",
        "description": (
            "small, powerful, scalable web server - common files"
        ),
    }


def test_pacman_search_packages(monkeypatch):
    from package_manager import PacmanPackageManager

    captured = {}

    class FakeResult:
        stdout = (
            "extra/nginx 1.30.5-1\n"
            "    HTTP server and reverse proxy\n"
            "core/nginx-mainline 1.29.1-1\n"
            "    Mainline nginx server\n"
            "extra/nginx-mod-stream 1.30.5-1\n"
            "    Stream module for nginx\n"
        )

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeResult()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = PacmanPackageManager()

    results = manager.search_packages(
        "nginx",
        max_results=2,
    )

    assert captured["command"] == [
        "pacman",
        "-Ss",
        "nginx",
    ]

    assert len(results) == 2

    assert results[0] == {
        "package": "nginx",
        "version": "1.30.5-1",
        "description": (
            "HTTP server and reverse proxy"
        ),
        "repository": "extra",
    }

    assert results[1] == {
        "package": "nginx-mainline",
        "version": "1.29.1-1",
        "description": (
            "Mainline nginx server"
        ),
        "repository": "core",
    }


def test_package_search_respects_result_limit(monkeypatch):
    from package_manager import AptPackageManager

    class FakeResult:
        stdout = "\n".join(
            f"package{index} - description {index}"
            for index in range(100)
        )

    def fake_run(command, **kwargs):
        return FakeResult()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = AptPackageManager()

    results = manager.search_packages(
        "package",
        max_results=50,
    )

    assert len(results) == 50


def test_package_search_respects_result_limit(monkeypatch):
    from package_manager import AptPackageManager

    class FakeResult:
        stdout = "\n".join(
            f"package{index} - description {index}"
            for index in range(100)
        )

    def fake_run(command, **kwargs):
        return FakeResult()

    monkeypatch.setattr(
        "package_manager.subprocess.run",
        fake_run,
    )

    manager = AptPackageManager()

    results = manager.search_packages(
        "package",
        max_results=50,
    )

    assert len(results) == 50

def test_main_simulation_does_not_send_lums_job_result(monkeypatch):
    import ssl

    monkeypatch.setattr(
        ssl,
        "create_default_context",
        lambda *args, **kwargs: None,
    )

    import agent

    monkeypatch.setattr(
        agent,
        "SIMULATE_UPDATES",
        True,
    )

    simulation_calls = []

    def fake_simulate_job():
        simulation_calls.append(True)

    def fail_if_result_is_sent(*_args, **_kwargs):
        raise AssertionError(
            "send_job_result() must not run in main() simulation mode"
        )

    def fail_if_collect_data_runs(*_args, **_kwargs):
        raise AssertionError(
            "collect_data() must not run in main() simulation mode"
        )

    monkeypatch.setattr(
        agent,
        "simulate_job",
        fake_simulate_job,
    )

    monkeypatch.setattr(
        agent,
        "send_job_result",
        fail_if_result_is_sent,
    )

    monkeypatch.setattr(
        agent,
        "collect_data",
        fail_if_collect_data_runs,
    )

    agent.main()

    assert simulation_calls == [True]
