import sqlite3
from datetime import datetime, timedelta, timezone


def test_health_status_helper_classifies_client_timestamps():
    from server.app import classify_health_client

    now = datetime.now(timezone.utc)

    assert classify_health_client(
        (now - timedelta(seconds=30)).isoformat(),
        now=now,
    ) == "online"

    assert classify_health_client(
        (now - timedelta(seconds=300)).isoformat(),
        now=now,
    ) == "unknown"

    assert classify_health_client(
        (now - timedelta(seconds=900)).isoformat(),
        now=now,
    ) == "offline"


def test_health_status_helper_handles_invalid_timestamps():
    from server.app import classify_health_client

    assert classify_health_client(None) == "unknown"
    assert classify_health_client("not-a-timestamp") == "unknown"


def test_health_status_helper_handles_naive_timestamps():
    from server.app import classify_health_client

    timestamp = datetime.now().isoformat()

    assert classify_health_client(timestamp) in {
        "online",
        "unknown",
        "offline",
    }


def test_health_dashboard_route_requires_authentication():
    from server import app as app_module

    with app_module.app.test_client() as client:
        response = client.get("/health")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]



def test_health_dashboard_allows_authenticated_user_with_permission(
    monkeypatch, tmp_path
):
    import sqlite3

    from server import app as app_module
    from tests.test_rbac import (
        configure_test_database,
        create_rbac_database,
        login_as,
    )

    db_path = str(tmp_path / "health-authorized.db")
    create_rbac_database(db_path)

    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY,
            last_seen TEXT
        )
        """
    )
    connection.commit()
    connection.close()

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    configure_test_database(monkeypatch, app_module, db_path)

    app_module.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        LUMS_BACKUP_DIR=str(backup_dir),
    )

    with app_module.app.test_client() as client:
        login_as(client, 3, "viewer")
        response = client.get("/health")

    assert response.status_code == 200
    assert (
        b"Systemstatus-Dashboard" in response.data
        or b"Health Dashboard" in response.data
    )
    assert b'href="/health"' in response.data
    assert b'lums-sidebar-link is-active' in response.data
    assert b'aria-current="page"' in response.data
    assert b'Systemstatus' in response.data or b'Health' in response.data


def test_health_dashboard_denies_authenticated_user_without_permission(
    monkeypatch, tmp_path
):
    from server import app as app_module
    from tests.test_rbac import (
        configure_test_database,
        create_rbac_database,
        login_as,
    )

    db_path = str(tmp_path / "health-denied.db")
    create_rbac_database(db_path)

    connection = sqlite3.connect(db_path)
    connection.execute(
        "DELETE FROM user_permissions WHERE user_id = ? AND permission = ?",
        (3, "clients.view"),
    )
    connection.commit()
    connection.close()

    configure_test_database(monkeypatch, app_module, db_path)
    app_module.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )

    with app_module.app.test_client() as client:
        login_as(client, 3, "viewer")
        response = client.get("/health")

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required",
    }

def test_public_api_health_endpoint_remains_lightweight():
    from server import app as app_module

    with app_module.app.test_client() as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "service": "LUMS API",
    }
