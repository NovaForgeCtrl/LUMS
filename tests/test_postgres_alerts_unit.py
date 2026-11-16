"""Database-free tests for PostgreSQL alert routes."""

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from psycopg.types.json import Jsonb

from server import postgres_alerts
from server import postgres_flask_security as pg_security
from server.postgres_app import create_postgres_app


BASE_URL = "https://localhost"
CSRF_TOKEN = "postgres-alert-test-csrf"


class FakeCursor:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = list(many or [])
        self.rowcount = 1 if one is not None else 0

    def fetchone(self):
        return self.one

    def fetchall(self):
        return list(self.many)


class FakeConnection:
    def __init__(self, handler=None):
        self.handler = handler
        self.closed = False
        self.statements = []
        self.events = []

    def execute(self, statement, params=None):
        sql = " ".join(statement.split())
        self.statements.append((sql, params))

        if self.handler is not None:
            result = self.handler(self, sql, params)
            if result is not None:
                return result

        return FakeCursor()

    def close(self):
        self.closed = True


def make_environment(
    monkeypatch,
    handlers,
    *,
    permissions=None,
):
    connections = []

    def factory():
        index = len(connections)
        handler = handlers[index] if index < len(handlers) else None
        connection = FakeConnection(handler)
        connections.append(connection)
        return connection

    app = create_postgres_app({
        "SECRET_KEY": "postgres-alert-unit-test",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": factory,
    })

    state = SimpleNamespace(
        user={
            "id": 7,
            "username": "alert-test-user",
            "enabled": True,
            "role": "administrator",
        },
        permissions=(
            permissions
            if permissions is not None
            else frozenset({"alerts.view", "alerts.manage"})
        ),
    )

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda connection, user_id: state,
    )

    @contextmanager
    def fake_transaction(connection):
        connection.events.append("begin")
        try:
            yield connection
        except BaseException:
            connection.events.append("rollback")
            raise
        else:
            connection.events.append("commit")

    def fake_audit(connection, **kwargs):
        assert "begin" in connection.events
        connection.events.append(("audit", kwargs))

    monkeypatch.setattr(
        postgres_alerts,
        "transaction",
        fake_transaction,
    )
    monkeypatch.setattr(
        postgres_alerts,
        "audit_log",
        fake_audit,
    )

    return app, app.test_client(), connections


def set_session(client):
    with client.session_transaction(base_url=BASE_URL) as session:
        session.clear()
        session.update({
            "user_id": 7,
            "username": "alert-test-user",
            "csrf_token": CSRF_TOKEN,
        })


def user_headers():
    return {"X-CSRF-Token": CSRF_TOKEN}


def make_alert_row(**overrides):
    row = {
        "alert_id": "rule-1_test-alert",
        "rule_id": "rule-1",
        "source": "pytest",
        "message": "Synthetic alert",
        "severity": "warning",
        "status": "triggered",
        "metadata": {"test": True},
        "triggered_at": datetime(
            2026, 11, 3, 10, 0, tzinfo=timezone.utc
        ),
        "acknowledged_at": None,
        "resolved_at": None,
        "escalation_count": 0,
    }
    row.update(overrides)
    return row


def test_all_registered_alert_routes_are_unique(monkeypatch):
    app, _, _ = make_environment(monkeypatch, [])

    expected = {
        ("/alerts/rules", "GET"),
        ("/alerts/rules", "POST"),
        ("/alerts/rules/<rule_id>", "PUT"),
        ("/alerts/rules/<rule_id>", "DELETE"),
        ("/alerts/current", "GET"),
        ("/alerts/history", "GET"),
        ("/alerts/trigger", "POST"),
        ("/alerts/<alert_id>/acknowledge", "POST"),
        ("/alerts/<alert_id>/resolve", "POST"),
        ("/alerts/<alert_id>/escalate", "POST"),
    }

    actual = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods
        if method not in {"HEAD", "OPTIONS"}
    }

    assert expected <= actual


def test_current_alerts_reads_persisted_active_rows(monkeypatch):
    row = make_alert_row()

    def handler(connection, sql, params):
        assert "FROM alerts" in sql
        assert "'triggered'" in sql
        assert "'acknowledged'" in sql
        assert "'escalated'" in sql
        return FakeCursor(many=[row])

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.get("/alerts/current", base_url=BASE_URL)

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 1
    assert data["alerts"][0]["alert_id"] == row["alert_id"]
    assert data["alerts"][0]["metadata"] == {"test": True}
    assert data["alerts"][0]["triggered_at"].endswith("+00:00")

    assert len(connections) == 2
    assert connections[1].events == ["begin", "commit"]
    assert all(connection.closed for connection in connections)


def test_alert_history_applies_bounded_pagination(monkeypatch):
    row = make_alert_row()

    def handler(connection, sql, params):
        assert "ORDER BY triggered_at DESC" in sql
        assert "LIMIT %s OFFSET %s" in sql
        assert params == (25, 10)
        return FakeCursor(many=[row])

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.get(
        "/alerts/history?limit=25&offset=10",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json()["count"] == 1
    assert connections[1].events == ["begin", "commit"]
    assert all(connection.closed for connection in connections)


def test_trigger_persists_alert_jsonb_and_audits_atomically(monkeypatch):
    metadata = {"test": True, "values": [1, 2, 3]}
    row = make_alert_row(metadata=metadata)

    def handler(connection, sql, params):
        if "FROM alert_rules" in sql:
            assert "FOR SHARE" in sql
            assert params == ("rule-1",)
            return FakeCursor(one={
                "rule_id": "rule-1",
                "severity": "warning",
                "enabled": True,
            })

        if sql.startswith("INSERT INTO alerts"):
            assert "RETURNING" in sql
            assert isinstance(params[5], Jsonb)
            assert params[5].obj == metadata
            return FakeCursor(one=row)

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.post(
        "/alerts/trigger",
        json={
            "rule_id": "rule-1",
            "source": "pytest",
            "message": "Synthetic alert",
            "metadata": metadata,
        },
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["alert"]["alert_id"] == row["alert_id"]
    assert data["alert"]["metadata"] == metadata

    connection = connections[1]
    assert connection.events[0] == "begin"
    assert connection.events[-1] == "commit"

    audit_event = next(
        event for event in connection.events
        if isinstance(event, tuple) and event[0] == "audit"
    )
    assert audit_event[1]["action"] == "alerts.trigger"
    assert audit_event[1]["actor_id"] == 7
    assert all(item.closed for item in connections)


def test_trigger_rejects_disabled_rule_without_insert(monkeypatch):
    def handler(connection, sql, params):
        if "FROM alert_rules" in sql:
            return FakeCursor(one={
                "rule_id": "rule-1",
                "severity": "warning",
                "enabled": False,
            })
        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.post(
        "/alerts/trigger",
        json={
            "rule_id": "rule-1",
            "message": "Synthetic alert",
        },
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert not any(
        sql.startswith("INSERT INTO alerts")
        for sql, _ in connections[1].statements
    )
    assert all(item.closed for item in connections)


def test_trigger_rejects_invalid_payload_before_write_connection(
    monkeypatch,
):
    _, client, connections = make_environment(monkeypatch, [])
    set_session(client)

    response = client.post(
        "/alerts/trigger",
        json={
            "rule_id": "rule-1",
            "message": "Synthetic alert",
            "unexpected": True,
        },
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert len(connections) == 1
    assert connections[0].closed


def test_alert_view_permission_is_required(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [],
        permissions=frozenset({"clients.view"}),
    )
    set_session(client)

    response = client.get("/alerts/current", base_url=BASE_URL)

    assert response.status_code == 403
    assert len(connections) == 1
    assert connections[0].closed


def test_alert_manage_permission_is_required(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [],
        permissions=frozenset({"alerts.view"}),
    )
    set_session(client)

    response = client.post(
        "/alerts/trigger",
        json={
            "rule_id": "rule-1",
            "message": "Synthetic alert",
        },
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert len(connections) == 1
    assert connections[0].closed


def test_alert_trigger_requires_csrf(monkeypatch):
    _, client, connections = make_environment(monkeypatch, [])
    set_session(client)

    response = client.post(
        "/alerts/trigger",
        json={
            "rule_id": "rule-1",
            "message": "Synthetic alert",
        },
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert len(connections) == 1
    assert connections[0].closed


def post_alert_status(monkeypatch, handler, action):
    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.post(
        f"/alerts/test-alert/{action}",
        headers=user_headers(),
        base_url=BASE_URL,
    )
    return response, connections


def test_acknowledge_alert_updates_metadata_history_and_audit(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith("SELECT status, metadata FROM alerts"):
            assert "FOR UPDATE" in sql
            return FakeCursor(one={
                "status": "triggered",
                "metadata": {"existing": True},
            })

        if sql.startswith("UPDATE alerts"):
            assert params[0] == "acknowledged"
            assert isinstance(params[2], Jsonb)
            assert params[2].obj == {
                "existing": True,
                "acknowledged_by": "7",
            }
            return FakeCursor(one={"alert_id": "test-alert"})

        if sql.startswith("INSERT INTO alert_history"):
            assert params[0] == "test-alert"
            assert params[1] == "acknowledged"
            assert params[3] == "7"
            assert params[4] == "Alert acknowledged"
            connection.events.append("history")
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {sql}")

    response, connections = post_alert_status(
        monkeypatch,
        handler,
        "acknowledge",
    )

    assert response.status_code == 200
    assert response.get_json() == {"message": "Alert acknowledged"}

    events = connections[1].events
    assert events[0] == "begin"
    assert events[1] == "history"
    assert events[2][0] == "audit"
    assert events[2][1]["action"] == "alerts.acknowledge"
    assert events[-1] == "commit"
    assert all(connection.closed for connection in connections)


def test_resolve_alert_updates_history_and_audit_atomically(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith("SELECT status FROM alerts"):
            assert "FOR UPDATE" in sql
            return FakeCursor(one={"status": "acknowledged"})

        if sql.startswith("UPDATE alerts"):
            assert params[0] == "resolved"
            assert params[2] == "test-alert"
            return FakeCursor(one={"alert_id": "test-alert"})

        if sql.startswith("INSERT INTO alert_history"):
            assert params[1] == "resolved"
            assert params[3] == "7"
            assert params[4] == "Alert resolved"
            connection.events.append("history")
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {sql}")

    response, connections = post_alert_status(
        monkeypatch,
        handler,
        "resolve",
    )

    assert response.status_code == 200
    assert response.get_json() == {"message": "Alert resolved"}

    events = connections[1].events
    assert events[0] == "begin"
    assert events[1] == "history"
    assert events[2][0] == "audit"
    assert events[2][1]["action"] == "alerts.resolve"
    assert events[-1] == "commit"
    assert all(connection.closed for connection in connections)


def test_escalate_alert_uses_locked_persisted_counter(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith(
            "SELECT status, escalation_count FROM alerts"
        ):
            assert "FOR UPDATE" in sql
            return FakeCursor(one={
                "status": "acknowledged",
                "escalation_count": 4,
            })

        if sql.startswith("UPDATE alerts"):
            assert params == ("escalated", 5, "test-alert")
            return FakeCursor(one={"escalation_count": 5})

        if sql.startswith("INSERT INTO alert_history"):
            assert params[1] == "escalated"
            assert params[3] == "7"
            assert params[4] == "Alert escalated to level 5"
            connection.events.append("history")
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {sql}")

    response, connections = post_alert_status(
        monkeypatch,
        handler,
        "escalate",
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "Alert escalated",
        "escalation_count": 5,
    }

    events = connections[1].events
    assert events[0] == "begin"
    assert events[1] == "history"
    assert events[2][0] == "audit"
    assert events[2][1]["action"] == "alerts.escalate"
    assert events[-1] == "commit"
    assert all(connection.closed for connection in connections)


def test_alert_status_transition_rolls_back_when_history_insert_fails(
    monkeypatch,
):
    def handler(connection, sql, params):
        if sql.startswith("SELECT status, metadata FROM alerts"):
            return FakeCursor(one={
                "status": "triggered",
                "metadata": {},
            })

        if sql.startswith("UPDATE alerts"):
            return FakeCursor(one={"alert_id": "test-alert"})

        if sql.startswith("INSERT INTO alert_history"):
            raise postgres_alerts.DatabaseDriverError(
                "simulated history failure"
            )

        raise AssertionError(f"Unexpected SQL: {sql}")

    response, connections = post_alert_status(
        monkeypatch,
        handler,
        "acknowledge",
    )

    assert response.status_code == 500
    assert connections[1].events == ["begin", "rollback"]
    assert all(connection.closed for connection in connections)


def test_alert_status_transition_rolls_back_when_audit_fails(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith("SELECT status, metadata FROM alerts"):
            return FakeCursor(one={
                "status": "triggered",
                "metadata": {},
            })

        if sql.startswith("UPDATE alerts"):
            return FakeCursor(one={"alert_id": "test-alert"})

        if sql.startswith("INSERT INTO alert_history"):
            connection.events.append("history")
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    # Install the failing audit mock after make_environment, because
    # make_environment initially installs its normal audit recorder.
    def fail_audit(connection, **kwargs):
        raise postgres_alerts.DatabaseDriverError(
            "simulated audit failure"
        )

    monkeypatch.setattr(postgres_alerts, "audit_log", fail_audit)

    response = client.post(
        "/alerts/test-alert/acknowledge",
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 500
    assert connections[1].events == [
        "begin",
        "history",
        "rollback",
    ]
    assert all(connection.closed for connection in connections)


def make_rule_row(**overrides):
    row = {
        "rule_id": "rule-1",
        "name": "CPU alert",
        "description": "CPU usage threshold",
        "condition": "cpu_usage > threshold",
        "threshold": {"cpu": 80},
        "severity": "warning",
        "enabled": True,
        "escalation_path": ["mail"],
        "group_similar": True,
        "deduplicate": True,
        "created_at": datetime(
            2026, 11, 3, 9, 0, tzinfo=timezone.utc
        ),
    }
    row.update(overrides)
    return row


def test_list_rules_returns_persisted_jsonb_values(monkeypatch):
    row = make_rule_row()

    def handler(connection, sql, params):
        assert "FROM alert_rules" in sql
        assert "ORDER BY created_at DESC" in sql
        return FakeCursor(many=[row])

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.get("/alerts/rules", base_url=BASE_URL)

    assert response.status_code == 200
    rule = response.get_json()["rules"][0]
    assert rule["rule_id"] == "rule-1"
    assert rule["threshold"] == {"cpu": 80}
    assert rule["escalation_path"] == ["mail"]
    assert rule["severity"] == "warning"
    assert rule["created_at"].endswith("+00:00")
    assert connections[1].events == ["begin", "commit"]
    assert all(connection.closed for connection in connections)


def test_create_rule_persists_jsonb_and_audits_atomically(monkeypatch):
    row = make_rule_row()

    def handler(connection, sql, params):
        if sql.startswith("INSERT INTO alert_rules"):
            assert "RETURNING" in sql
            assert params[1] == "CPU alert"
            assert isinstance(params[4], Jsonb)
            assert params[4].obj == {"cpu": 80}
            assert params[5] == "warning"
            assert isinstance(params[7], Jsonb)
            assert params[7].obj == ["mail"]
            return FakeCursor(one={
                **row,
                "rule_id": params[0],
            })

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.post(
        "/alerts/rules",
        json={
            "name": "CPU alert",
            "description": "CPU usage threshold",
            "condition": "cpu_usage > threshold",
            "threshold": {"cpu": 80},
            "severity": "warning",
            "enabled": True,
            "escalation_path": ["mail"],
            "group_similar": True,
            "deduplicate": True,
        },
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 201
    rule = response.get_json()["rule"]
    assert rule["name"] == "CPU alert"
    assert rule["threshold"] == {"cpu": 80}
    assert rule["escalation_path"] == ["mail"]

    events = connections[1].events
    assert events[0] == "begin"
    assert events[1][0] == "audit"
    assert events[1][1]["action"] == "alerts.rule.create"
    assert events[-1] == "commit"
    assert all(connection.closed for connection in connections)


def test_update_rule_preserves_omitted_fields_and_audits(monkeypatch):
    original = make_rule_row()

    def handler(connection, sql, params):
        if sql.startswith("SELECT rule_id"):
            assert "FOR UPDATE" in sql
            return FakeCursor(one=original)

        if sql.startswith("UPDATE alert_rules"):
            assert params[0] == "Updated CPU alert"
            assert params[1] == original["description"]
            assert params[2] == original["condition"]
            assert isinstance(params[3], Jsonb)
            assert params[3].obj == original["threshold"]
            assert params[4] == "critical"
            assert params[7] == original["group_similar"]
            assert params[8] == original["deduplicate"]
            return FakeCursor(one={
                **original,
                "name": "Updated CPU alert",
                "severity": "critical",
            })

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.put(
        "/alerts/rules/rule-1",
        json={
            "name": "Updated CPU alert",
            "severity": "critical",
        },
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    rule = response.get_json()["rule"]
    assert rule["name"] == "Updated CPU alert"
    assert rule["severity"] == "critical"
    assert rule["threshold"] == original["threshold"]

    events = connections[1].events
    assert events[0] == "begin"
    assert events[1][0] == "audit"
    assert events[1][1]["action"] == "alerts.rule.update"
    assert events[-1] == "commit"
    assert all(connection.closed for connection in connections)


def test_delete_rule_returns_success_and_audits(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith("DELETE FROM alert_rules"):
            assert "RETURNING rule_id" in sql
            assert params == ("rule-1",)
            return FakeCursor(one={"rule_id": "rule-1"})

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.delete(
        "/alerts/rules/rule-1",
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "Rule deleted successfully"
    }

    events = connections[1].events
    assert events[0] == "begin"
    assert events[1][0] == "audit"
    assert events[1][1]["action"] == "alerts.rule.delete"
    assert events[-1] == "commit"
    assert all(connection.closed for connection in connections)


def test_delete_referenced_rule_returns_conflict(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith("DELETE FROM alert_rules"):
            raise postgres_alerts.DatabaseIntegrityError(
                "rule is referenced"
            )

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.delete(
        "/alerts/rules/rule-1",
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "Rule cannot be deleted while it is referenced"
    }
    assert connections[1].events == ["begin", "rollback"]
    assert all(connection.closed for connection in connections)
