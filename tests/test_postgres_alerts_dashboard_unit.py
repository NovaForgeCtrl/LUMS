"""Database-free tests for the PostgreSQL alerts dashboard."""

from types import SimpleNamespace

from server import postgres_flask_security as pg_security
from server.postgres_app import create_postgres_app
from server.i18n import translate


BASE_URL = "https://localhost"


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def make_client(monkeypatch, permissions):
    connections = []

    def connection_factory():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    app = create_postgres_app({
        "SECRET_KEY": "postgres-alert-dashboard-test",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
    })

    state = SimpleNamespace(
        user={
            "id": 7,
            "username": "dashboard-user",
            "enabled": True,
            "role": "administrator",
        },
        permissions=frozenset(permissions),
    )

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda connection, user_id: state,
    )

    client = app.test_client()

    with client.session_transaction(base_url=BASE_URL) as session:
        session["user_id"] = 7
        session["username"] = "dashboard-user"

    return app, client, connections


def test_dashboard_renders_for_alerts_view_without_manage_controls(
    monkeypatch,
):
    _, client, connections = make_client(
        monkeypatch,
        {"alerts.view"},
    )

    response = client.get("/alerts", base_url=BASE_URL)

    assert response.status_code == 200
    assert translate("Alerts & Monitoring", "de").encode("utf-8") in response.data
    assert b'data-can-manage="false"' in response.data
    assert b'id="alerts-current-body"' in response.data
    assert b'id="alerts-history-body"' in response.data
    assert b'id="alerts-rules-body"' in response.data
    assert b'id="alerts-rule-form"' not in response.data
    assert b"/static/postgres_alerts.js" in response.data
    assert len(connections) == 1
    assert connections[0].closed is True


def test_dashboard_renders_rule_management_for_alerts_manage(
    monkeypatch,
):
    _, client, connections = make_client(
        monkeypatch,
        {"alerts.view", "alerts.manage"},
    )

    response = client.get("/alerts", base_url=BASE_URL)

    assert response.status_code == 200
    assert b'data-can-manage="true"' in response.data
    assert b'id="alerts-rule-form"' in response.data
    assert b'id="alerts-rule-new"' in response.data
    assert len(connections) == 1
    assert connections[0].closed is True


def test_dashboard_rejects_user_without_alerts_view(monkeypatch):
    _, client, connections = make_client(
        monkeypatch,
        {"clients.view"},
    )

    response = client.get("/alerts", base_url=BASE_URL)

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required"
    }
    assert len(connections) == 1
    assert connections[0].closed is True


def test_dashboard_redirects_unauthenticated_user():
    calls = []

    def connection_factory():
        calls.append(True)
        return FakeConnection()

    app = create_postgres_app({
        "SECRET_KEY": "postgres-alert-dashboard-test",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
    })

    response = app.test_client().get(
        "/alerts",
        base_url=BASE_URL,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert calls == []


def test_dashboard_renders_postgres_api_urls_and_csrf_token(monkeypatch):
    _, client, connections = make_client(
        monkeypatch,
        {"alerts.view"},
    )

    response = client.get("/alerts", base_url=BASE_URL)

    assert response.status_code == 200

    expected = (
        b'data-current-url="/alerts/current"',
        b'data-history-url="/alerts/history"',
        b'data-rules-url="/alerts/rules"',
        b'data-ack-url="/alerts/__ALERT_ID__/acknowledge"',
        b'data-resolve-url="/alerts/__ALERT_ID__/resolve"',
        b'data-escalate-url="/alerts/__ALERT_ID__/escalate"',
        b'data-rule-update-url="/alerts/rules/__RULE_ID__"',
        b'data-rule-delete-url="/alerts/rules/__RULE_ID__"',
        b'data-rule-create-url="/alerts/rules"',
        b'name="csrf-token"',
    )

    for expected_value in expected:
        assert expected_value in response.data, expected_value

    assert b"/alerts/api/logs" not in response.data
    assert b"/alerts/api/soc" not in response.data

    assert len(connections) == 1
    assert connections[0].closed is True
