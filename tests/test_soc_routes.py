import sqlite3

import pytest

from tests.test_rbac import (
    configure_test_database,
    create_rbac_database,
    login_as,
)


SOC_ENDPOINTS = {
    "soc.soc_dashboard",
    "soc.network_monitoring",
    "soc.event_explorer",
    "soc.network_analyzer",
    "soc.pcap_investigation",
    "soc.incidents",
    "soc.detection_rules",
    "soc.sensor_management",
    "soc.reports_overview",
    "soc.security_reports",
    "soc.network_reports",
    "soc.export_history",
}


@pytest.fixture
def soc_http_env(tmp_path, monkeypatch):
    from server import app as app_module

    db_path = str(tmp_path / "soc-routes-test.db")
    create_rbac_database(db_path)

    configure_test_database(monkeypatch, app_module, db_path)

    app_module.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )

    return {
        "app": app_module.app,
        "db_path": db_path,
        "client": app_module.app.test_client(),
    }


def set_user_permissions(db_path, permissions):
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "DELETE FROM user_permissions WHERE user_id = ?",
            (3,),
        )
        connection.executemany(
            """
            INSERT INTO user_permissions (user_id, permission)
            VALUES (?, ?)
            """,
            [(3, permission) for permission in permissions],
        )
        connection.commit()
    finally:
        connection.close()


def get_soc_rules(app):
    rules = sorted(
        (
            rule
            for rule in app.url_map.iter_rules()
            if rule.endpoint.startswith("soc.")
            and rule.endpoint != "soc.dashboard_api"
            and "GET" in rule.methods
        ),
        key=lambda rule: (rule.endpoint, rule.rule),
    )

    endpoints = {rule.endpoint for rule in rules}

    assert endpoints == SOC_ENDPOINTS
    assert len(rules) == 12

    return rules


def test_all_soc_routes_require_authentication(soc_http_env):
    env = soc_http_env
    rules = get_soc_rules(env["app"])

    for rule in rules:
        response = env["client"].get(
            rule.rule,
            base_url="https://localhost",
        )

        assert response.status_code == 302, (
            f"{rule.endpoint} returned {response.status_code}"
        )
        assert "/login" in response.headers["Location"], (
            f"{rule.endpoint} did not redirect to login"
        )


@pytest.mark.parametrize(
    "permissions, expected_status",
    [
        (["alerts.view"], 403),
        (["clients.view"], 200),
        ([], 403),
    ],
    ids=[
        "alerts-view-only-is-denied",
        "clients-view-is-allowed",
        "no-permission-is-denied",
    ],
)
def test_soc_routes_enforce_clients_view_permission(
    soc_http_env,
    permissions,
    expected_status,
):
    env = soc_http_env

    set_user_permissions(env["db_path"], permissions)
    login_as(env["client"], 3, "viewer")

    rules = get_soc_rules(env["app"])

    for rule in rules:
        response = env["client"].get(
            rule.rule,
            base_url="https://localhost",
        )

        assert response.status_code == expected_status, (
            f"{rule.endpoint} returned {response.status_code}; "
            f"expected {expected_status} for permissions {permissions}"
        )

        if expected_status == 403:
            assert response.get_json() == {
                "error": "authorization_required",
            }


def test_soc_pages_show_development_state_without_live_data(soc_http_env):
    env = soc_http_env

    set_user_permissions(
        env["db_path"],
        ["clients.view"],
    )
    login_as(env["client"], 3, "viewer")

    rules = get_soc_rules(env["app"])

    for rule in rules:
        response = env["client"].get(
            rule.rule,
            base_url="https://localhost",
        )

        assert response.status_code == 200

        # These structural markers must be present on every SOC page.
        assert b"soc-development-status" in response.data
        assert b"soc-page-notice" in response.data
        assert b"soc-page-heading" in response.data



def test_soc_dashboard_api_requires_authentication(soc_http_env):
    response = soc_http_env["client"].get(
        "/soc/api/dashboard",
        base_url="https://localhost",
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "authentication_required",
    }


@pytest.mark.parametrize(
    "permissions, expected_status",
    [
        (["alerts.view"], 403),
        (["clients.view"], 200),
        ([], 403),
    ],
    ids=[
        "alerts-view-only-is-denied",
        "clients-view-is-allowed",
        "no-permission-is-denied",
    ],
)
def test_soc_dashboard_api_enforces_clients_view(
    soc_http_env,
    permissions,
    expected_status,
):
    env = soc_http_env
    set_user_permissions(env["db_path"], permissions)
    login_as(env["client"], 3, "viewer")

    response = env["client"].get(
        "/soc/api/dashboard",
        base_url="https://localhost",
    )

    assert response.status_code == expected_status

    if expected_status == 403:
        assert response.get_json() == {
            "error": "authorization_required",
        }


def test_soc_dashboard_api_reports_uninitialized_sources(soc_http_env):
    env = soc_http_env
    set_user_permissions(env["db_path"], ["clients.view"])
    login_as(env["client"], 3, "viewer")

    response = env["client"].get(
        "/soc/api/dashboard",
        base_url="https://localhost",
    )

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["sources"] == {
        "events": {
            "available": False,
            "reason": "storage_not_ready",
        },
        "sensors": {
            "available": False,
            "reason": "storage_not_ready",
        },
        "incidents": {
            "available": False,
            "reason": "storage_not_ready",
        },
    }
    assert payload["recent_incidents"] == []


def test_soc_dashboard_api_reports_initialized_sources_and_bounded_data(
    soc_http_env,
):
    from server.soc.collector_store import CollectorStore
    from server.soc.incidents import Incident
    from server.soc.incident_store import IncidentStore

    env = soc_http_env
    connection = sqlite3.connect(env["db_path"])

    try:
        collectors = CollectorStore(connection)
        incidents = IncidentStore(connection)

        collectors.register_agent(
            "dashboard-agent-active",
            "Dashboard active agent",
            "a" * 64,
        )
        collectors.register_agent(
            "dashboard-agent-revoked",
            "Dashboard revoked agent",
            "b" * 64,
        )
        assert collectors.revoke_agent("dashboard-agent-revoked")

        result = collectors.ingest_batch(
            "dashboard-agent-active",
            [
                {"event_id": "dashboard-pending"},
                {"event_id": "dashboard-processing"},
                {"event_id": "dashboard-processed"},
                {"event_id": "dashboard-failed"},
            ],
        )
        assert result.accepted == 4

        connection.executemany(
            """
            UPDATE soc_event_inbox
            SET processing_status = ?
            WHERE event_id = ?
            """,
            [
                ("pending", "dashboard-pending"),
                ("processing", "dashboard-processing"),
                ("processed", "dashboard-processed"),
                ("failed", "dashboard-failed"),
            ],
        )
        connection.commit()

        incident_items = []
        for number in range(10):
            timestamp = f"2026-10-30T10:{number:02d}:00+00:00"
            status = ("open", "investigating", "resolved")[number % 3]

            incident = Incident.create(
                incident_id=f"dashboard-incident-{number:02d}",
                title=f"Dashboard incident {number:02d}",
                summary="Integration test incident",
                severity=("info", "warning", "critical")[number % 3],
                created_at=timestamp,
            )

            if status != "open":
                incident = incident.transition(
                    status,
                    updated_at=timestamp,
                )

            incident_items.append(incident)

        incidents.save_many(incident_items)

    finally:
        connection.close()

    set_user_permissions(env["db_path"], ["clients.view"])
    login_as(env["client"], 3, "viewer")

    response = env["client"].get(
        "/soc/api/dashboard",
        base_url="https://localhost",
    )

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["sources"] == {
        "events": {"available": True},
        "sensors": {"available": True},
        "incidents": {"available": True},
    }

    assert payload["events"] == {
        "pending": 1,
        "processing": 1,
        "processed": 1,
        "failed": 1,
    }

    assert payload["sensors"] == {
        "active": 1,
        "revoked": 1,
    }

    assert payload["incidents"]["status"] == {
        "open": 4,
        "investigating": 3,
        "resolved": 3,
    }

    assert payload["incidents"]["severity"] == {
        "info": 4,
        "warning": 3,
        "critical": 3,
    }

    recent = payload["recent_incidents"]
    assert len(recent) == 8
    assert [item["incident_id"] for item in recent] == [
        f"dashboard-incident-{number:02d}"
        for number in range(9, 1, -1)
    ]
