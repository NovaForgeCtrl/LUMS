import json
import os
import sqlite3
from datetime import datetime, timezone

import pytest

os.environ.setdefault("LUMS_SECRET_KEY", "pytest-only-update-secret")

from server import app as app_module
from server.security import (
    ROLE_ADMINISTRATOR,
    ROLE_DEFAULT_PERMISSIONS,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)
from server import system_updates


def test_system_update_permission_is_granted_only_by_default_to_admins():
    assert "system.update" in ROLE_DEFAULT_PERMISSIONS[ROLE_ADMINISTRATOR]
    assert "system.update" not in ROLE_DEFAULT_PERMISSIONS[ROLE_OPERATOR]
    assert "system.update" not in ROLE_DEFAULT_PERMISSIONS[ROLE_VIEWER]


def release_payload(tag="v1.2.3"):
    base = (
        "https://github.com/NovaForgeCtrl/LUMS/releases/download/"
        f"{tag}/"
    )
    source = f"lums-source-{tag}.tar.gz"
    return {
        "tag_name": tag,
        "name": "LUMS 1.2.3",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-01-01T00:00:00Z",
        "html_url": f"https://github.com/NovaForgeCtrl/LUMS/releases/tag/{tag}",
        "body": "Tested release",
        "assets": [
            {
                "name": source,
                "browser_download_url": base + source,
            },
            {
                "name": source + ".sha256",
                "browser_download_url": base + source + ".sha256",
            },
            {
                "name": f"lums-source-{tag}.commit",
                "browser_download_url": base + f"lums-source-{tag}.commit",
            },
        ],
    }


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return self.body


def reset_release_cache():
    system_updates._release_cache = None
    system_updates._release_cache_time = 0
    system_updates._failure_cache_message = None
    system_updates._failure_cache_time = 0


def test_latest_release_requires_assets_created_after_tests(monkeypatch):
    reset_release_cache()
    commit = "a1" * 20
    responses = iter([
        FakeResponse(release_payload()),
        FakeResponse({"sha": commit}),
    ])
    monkeypatch.setattr(
        system_updates,
        "urlopen",
        lambda *_args, **_kwargs: next(responses),
    )

    release = system_updates.latest_release()

    assert release["tag"] == "v1.2.3"
    assert release["commit"] == commit
    assert release["source_name"] == "lums-source-v1.2.3.tar.gz"


def test_latest_release_caches_network_failure(monkeypatch):
    reset_release_cache()
    calls = 0

    def fail_request(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise system_updates.URLError("offline")

    monkeypatch.setattr(system_updates, "urlopen", fail_request)

    with pytest.raises(
        system_updates.ReleaseLookupError, match="Netzwerkfehler"
    ):
        system_updates.latest_release()

    with pytest.raises(
        system_updates.ReleaseLookupError, match="Netzwerkfehler"
    ):
        system_updates.latest_release()

    assert calls == 1


def test_latest_release_retries_after_failure_cache_expires(monkeypatch):
    reset_release_cache()
    monkeypatch.setattr(system_updates, "_FAILURE_CACHE_SECONDS", 0)
    calls = 0

    def fail_request(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise system_updates.URLError("offline")

    monkeypatch.setattr(system_updates, "urlopen", fail_request)

    for _ in range(2):
        with pytest.raises(
            system_updates.ReleaseLookupError, match="Netzwerkfehler"
        ):
            system_updates.latest_release()

    assert calls == 2


def test_reset_release_cache_clears_failure_state():
    system_updates._failure_cache_message = "alter Fehler"
    system_updates._failure_cache_time = 123

    reset_release_cache()

    assert system_updates._release_cache is None
    assert system_updates._release_cache_time == 0
    assert system_updates._failure_cache_message is None
    assert system_updates._failure_cache_time == 0


def test_latest_release_reports_oversized_response(monkeypatch):
    reset_release_cache()
    response = FakeResponse({})
    response.body = b"x" * (system_updates._MAX_RESPONSE_BYTES + 1)
    monkeypatch.setattr(
        system_updates, "urlopen", lambda *_args, **_kwargs: response
    )

    with pytest.raises(
        system_updates.ReleaseLookupError, match="unerwartet große Antwort"
    ):
        system_updates.latest_release()


def test_latest_release_reports_invalid_json(monkeypatch):
    reset_release_cache()
    response = FakeResponse({})
    response.body = b"not valid json"
    monkeypatch.setattr(
        system_updates, "urlopen", lambda *_args, **_kwargs: response
    )

    with pytest.raises(
        system_updates.ReleaseLookupError, match="gültige JSON-Antwort"
    ):
        system_updates.latest_release()


def test_latest_release_rejects_invalid_commit_hash(monkeypatch):
    reset_release_cache()
    responses = iter([
        FakeResponse(release_payload()),
        FakeResponse({"sha": "not-a-valid-commit"}),
    ])
    monkeypatch.setattr(
        system_updates,
        "urlopen",
        lambda *_args, **_kwargs: next(responses),
    )

    with pytest.raises(
        system_updates.ReleaseLookupError, match="Commit ist ungültig"
    ):
        system_updates.latest_release()


def test_release_with_unhashable_asset_name_is_rejected():
    payload = release_payload()
    payload["assets"][0]["name"] = []

    with pytest.raises(
        system_updates.ReleaseLookupError,
        match="nicht vollständig getestet und verpackt",
    ):
        system_updates._parse_release(payload)


def test_release_without_tested_source_assets_is_not_available():
    payload = release_payload()
    payload["assets"] = []

    with pytest.raises(system_updates.ReleaseLookupError, match="getestet"):
        system_updates._parse_release(payload)


def test_release_assets_must_use_the_trusted_repository():
    payload = release_payload()
    payload["assets"][0]["browser_download_url"] = (
        "https://example.invalid/lums-source-v1.2.3.tar.gz"
    )

    with pytest.raises(system_updates.ReleaseLookupError, match="ungültige URL"):
        system_updates._parse_release(payload)


def test_release_page_must_be_from_the_trusted_repository():
    payload = release_payload()
    payload["html_url"] = "https://example.invalid/release"

    with pytest.raises(system_updates.ReleaseLookupError, match="Ziel-Repository"):
        system_updates._parse_release(payload)


@pytest.fixture
def update_api(tmp_path, monkeypatch):
    db_path = tmp_path / "updates.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL
        );
        CREATE TABLE user_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            PRIMARY KEY (user_id, permission)
        );
        CREATE TABLE system_update_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requested_at TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            target_tag TEXT NOT NULL,
            target_commit TEXT NOT NULL,
            status TEXT NOT NULL,
            step TEXT NOT NULL,
            progress_json TEXT NOT NULL DEFAULT '[]',
            details_json TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            rollback_status TEXT,
            updated_at TEXT NOT NULL,
            finished_at TEXT
        );
        CREATE TABLE system_update_agent (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_seen TEXT NOT NULL,
            current_version TEXT,
            deployment TEXT,
            status_message TEXT
        );
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            action TEXT NOT NULL,
            target TEXT,
            result TEXT NOT NULL,
            details TEXT
        );
    """)
    for user_id, username, role in (
        (1, "admin", ROLE_ADMINISTRATOR),
        (2, "operator", ROLE_OPERATOR),
        (3, "viewer", ROLE_VIEWER),
    ):
        connection.execute(
            """
            INSERT INTO users (id, username, password_hash, created_at, role)
            VALUES (?, ?, 'test-hash', '2026-01-01T00:00:00+00:00', ?)
            """,
            (user_id, username, role),
        )
        connection.executemany(
            """
            INSERT INTO user_permissions (user_id, permission)
            VALUES (?, ?)
            """,
            [
                (user_id, permission)
                for permission in ROLE_DEFAULT_PERMISSIONS[role]
            ],
        )
    connection.commit()
    connection.close()

    def get_connection():
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        return db

    monkeypatch.setattr(app_module, "get_connection", get_connection)
    monkeypatch.setattr(
        app_module,
        "latest_release",
        lambda: {
            "tag": "v1.2.3",
            "commit": "a1" * 20,
            "name": "LUMS 1.2.3",
            "published_at": "2026-01-01T00:00:00Z",
            "url": "https://github.com/NovaForgeCtrl/LUMS/releases/tag/v1.2.3",
            "notes": "Tested release",
            "source_asset": "https://github.com/NovaForgeCtrl/LUMS/releases/download/v1.2.3/source",
            "checksum_asset": "https://github.com/NovaForgeCtrl/LUMS/releases/download/v1.2.3/checksum",
            "commit_asset": "https://github.com/NovaForgeCtrl/LUMS/releases/download/v1.2.3/commit",
            "source_name": "lums-source-v1.2.3.tar.gz",
        },
    )
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    return db_path, app_module.app.test_client()


def login(client, user_id, username):
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["username"] = username
        session["csrf_token"] = "test-csrf-token"


@pytest.mark.parametrize(
    ("user_id", "username"),
    [(2, "operator"), (3, "viewer")],
)
def test_update_api_is_denied_to_operators_and_viewers(
    update_api, user_id, username
):
    _, client = update_api
    login(client, user_id, username)

    response = client.get("/api/system-updates")

    assert response.status_code == 403
    assert response.get_json() == {"error": "authorization_required"}



def test_host_updater_heartbeat_requires_dedicated_token(
    update_api, monkeypatch, tmp_path
):
    _, client = update_api
    token_file = tmp_path / "host-updater-token"
    token_file.write_text("test-host-updater-secret-" + "x" * 32)
    monkeypatch.setenv("LUMS_HOST_UPDATER_TOKEN_FILE", str(token_file))

    response = client.post(
        "/api/host-updater/heartbeat",
        json={"version": "dev", "deployment": "test",
              "status_message": "Heartbeat test"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == (
        "host_updater_authentication_required"
    )


def test_host_updater_heartbeat_records_status_without_enabling_updates(
    update_api, monkeypatch, tmp_path
):
    db_path, client = update_api
    token = "test-host-updater-secret-" + "x" * 32
    token_file = tmp_path / "host-updater-token"
    token_file.write_text(token)
    monkeypatch.setenv("LUMS_HOST_UPDATER_TOKEN_FILE", str(token_file))

    response = client.post(
        "/api/host-updater/heartbeat",
        headers={"Authorization": "Bearer " + token},
        json={
            "version": "dev",
            "deployment": "test-host",
            "status_message": "Heartbeat test",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert response.get_json()["update_execution_enabled"] is False

    connection = sqlite3.connect(db_path)
    row = connection.execute(
        """
        SELECT last_seen, current_version, deployment, status_message
        FROM system_update_agent WHERE id = 1
        """
    ).fetchone()
    connection.close()

    assert row is not None
    assert row[1:] == ("dev", "test-host", "Heartbeat test")
    assert row[0]


def test_host_updater_heartbeat_rejects_oversized_fields(
    update_api, monkeypatch, tmp_path
):
    _, client = update_api
    token = "test-host-updater-secret-" + "x" * 32
    token_file = tmp_path / "host-updater-token"
    token_file.write_text(token)
    monkeypatch.setenv("LUMS_HOST_UPDATER_TOKEN_FILE", str(token_file))

    response = client.post(
        "/api/host-updater/heartbeat",
        headers={"Authorization": "Bearer " + token},
        json={"status_message": "x" * 501},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_status_message"


def test_update_request_requires_live_agent_and_csrf(update_api):
    db_path, client = update_api
    login(client, 1, "admin")

    no_csrf = client.post("/api/system-updates", json={})
    assert no_csrf.status_code == 400

    with_csrf = client.post(
        "/api/system-updates",
        json={"tag": "untrusted-user-tag"},
        headers={"X-CSRF-Token": "test-csrf-token"},
    )
    assert with_csrf.status_code == 503
    assert "Host-Update-Dienst" in with_csrf.get_json()["error"]

    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        INSERT INTO system_update_agent (id, last_seen)
        VALUES (1, ?)
        """,
        (datetime.now(timezone.utc).isoformat(),),
    )
    connection.commit()
    connection.close()

    accepted = client.post(
        "/api/system-updates",
        json={"tag": "untrusted-user-tag"},
        headers={"X-CSRF-Token": "test-csrf-token"},
    )
    assert accepted.status_code == 202
    assert accepted.get_json()["target_tag"] == "v1.2.3"

    duplicate = client.post(
        "/api/system-updates",
        json={},
        headers={"X-CSRF-Token": "test-csrf-token"},
    )
    assert duplicate.status_code == 409
