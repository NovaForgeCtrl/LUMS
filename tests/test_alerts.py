import json
import sqlite3

import pytest

from server.alerts import (
    AlertManager,
    AlertRule,
    AlertSeverity,
    AlertStatus,
)


@pytest.fixture
def alert_env():
    """Isolated in-memory SQLite database; no external notification providers."""
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    manager = AlertManager(db)
    yield db, manager
    db.close()


def make_rule(
    rule_id="test-rule",
    *,
    enabled=True,
    escalation_path=None,
):
    return AlertRule(
        rule_id=rule_id,
        name="Test alert rule",
        description="Rule used by automated tests",
        condition="cpu_usage > threshold",
        threshold=80,
        severity=AlertSeverity.WARNING,
        enabled=enabled,
        escalation_path=escalation_path or [],
    )


def make_alert(manager, rule_id="test-rule"):
    assert manager.create_rule(make_rule(rule_id))
    alert = manager.trigger_alert(
        rule_id=rule_id,
        source="pytest-client",
        message="Synthetic test alert",
        metadata={"test": True},
    )
    assert alert is not None
    return alert


def test_create_rule_persists_rule(alert_env):
    db, manager = alert_env

    assert manager.create_rule(make_rule())

    row = db.execute(
        """
        SELECT name, condition, severity, enabled
        FROM alert_rules WHERE rule_id = ?
        """,
        ("test-rule",),
    ).fetchone()

    assert row == ("Test alert rule", "cpu_usage > threshold", "warning", 1)
    assert "test-rule" in manager.rules


def test_duplicate_rule_is_rejected(alert_env):
    db, manager = alert_env

    assert manager.create_rule(make_rule())
    assert not manager.create_rule(make_rule())

    assert db.execute(
        "SELECT COUNT(*) FROM alert_rules WHERE rule_id = ?",
        ("test-rule",),
    ).fetchone()[0] == 1


def test_disabled_rule_cannot_trigger_alert(alert_env):
    db, manager = alert_env

    assert manager.create_rule(make_rule(enabled=False))

    alert = manager.trigger_alert(
        "test-rule", "pytest-client", "Must not be created"
    )

    assert alert is None
    assert db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 0
    assert manager.active_alerts == {}


def test_triggered_alert_is_persisted(alert_env):
    db, manager = alert_env
    alert = make_alert(manager)

    row = db.execute(
        "SELECT status, source, message FROM alerts WHERE alert_id = ?",
        (alert.alert_id,),
    ).fetchone()

    assert row == ("triggered", "pytest-client", "Synthetic test alert")
    assert alert.alert_id in manager.active_alerts


def test_acknowledge_records_actor_and_history(alert_env):
    db, manager = alert_env
    alert = make_alert(manager)

    assert manager.acknowledge_alert(alert.alert_id, "pytest-operator")
    assert alert.status is AlertStatus.ACKNOWLEDGED
    assert alert.metadata["acknowledged_by"] == "pytest-operator"

    row = db.execute(
        """
        SELECT status, acknowledged_at, metadata
        FROM alerts WHERE alert_id = ?
        """,
        (alert.alert_id,),
    ).fetchone()
    assert row[0] == "acknowledged"
    assert row[1]
    assert "pytest-operator" in row[2]

    history = db.execute(
        """
        SELECT status, changed_by FROM alert_history
        WHERE alert_id = ? ORDER BY id
        """,
        (alert.alert_id,),
    ).fetchall()
    assert history == [("acknowledged", "pytest-operator")]


def test_escalation_increments_count_and_records_history(alert_env):
    db, manager = alert_env
    alert = make_alert(manager)

    assert manager.escalate_alert(alert.alert_id, "pytest-operator") == 1
    assert alert.status is AlertStatus.ESCALATED
    assert alert.escalation_count == 1

    row = db.execute(
        "SELECT status, escalation_count FROM alerts WHERE alert_id = ?",
        (alert.alert_id,),
    ).fetchone()
    assert row == ("escalated", 1)

    assert manager.escalate_alert(alert.alert_id, "pytest-operator") == 2
    assert db.execute(
        "SELECT escalation_count FROM alerts WHERE alert_id = ?",
        (alert.alert_id,),
    ).fetchone()[0] == 2



def test_escalation_count_uses_latest_database_value_across_managers(alert_env):
    db, manager_a = alert_env
    alert = make_alert(manager_a)

    # Simulate a second request with its own manager and stale in-memory state.
    manager_b = AlertManager(db)
    stale_alert_a = manager_a.active_alerts[alert.alert_id]
    assert stale_alert_a.escalation_count == 0

    assert manager_b.escalate_alert(alert.alert_id, "manager-b") == 1

    # Manager A still holds the original escalation_count (0).
    # The next escalation must nevertheless advance the persisted count to 2.
    assert manager_a.escalate_alert(alert.alert_id, "manager-a") == 2

    row = db.execute(
        "SELECT status, escalation_count FROM alerts WHERE alert_id = ?",
        (alert.alert_id,),
    ).fetchone()
    assert row == ("escalated", 2)

    history = db.execute(
        "SELECT status, reason FROM alert_history "
        "WHERE alert_id = ? ORDER BY id",
        (alert.alert_id,),
    ).fetchall()
    assert history == [
        ("escalated", "Alert escalated to level 1"),
        ("escalated", "Alert escalated to level 2"),
    ]

def test_resolve_keeps_database_history_and_removes_active_alert(alert_env):
    db, manager = alert_env
    alert = make_alert(manager)

    assert manager.resolve_alert(alert.alert_id, "pytest-operator")
    assert alert.status is AlertStatus.RESOLVED
    assert alert.alert_id not in manager.active_alerts

    row = db.execute(
        "SELECT status, resolved_at FROM alerts WHERE alert_id = ?",
        (alert.alert_id,),
    ).fetchone()
    assert row[0] == "resolved"
    assert row[1]

    assert db.execute(
        """
        SELECT status, changed_by FROM alert_history
        WHERE alert_id = ? ORDER BY id
        """,
        (alert.alert_id,),
    ).fetchall() == [("resolved", "pytest-operator")]


def test_active_state_and_history_survive_manager_recreation(alert_env):
    db, manager = alert_env
    alert = make_alert(manager)

    assert manager.acknowledge_alert(alert.alert_id, "pytest-operator")
    assert manager.escalate_alert(alert.alert_id, "pytest-operator") == 1

    restored = AlertManager(db)

    assert "test-rule" in restored.rules
    assert alert.alert_id in restored.active_alerts
    restored_alert = restored.active_alerts[alert.alert_id]
    assert restored_alert.status is AlertStatus.ESCALATED
    assert restored_alert.escalation_count == 1

    history = db.execute(
        """
        SELECT status FROM alert_history
        WHERE alert_id = ? ORDER BY id
        """,
        (alert.alert_id,),
    ).fetchall()
    assert history == [("acknowledged",), ("escalated",)]

    # A resolved alert must remain in the durable history after a reload.
    assert restored.resolve_alert(alert.alert_id, "pytest-operator")
    reloaded = AlertManager(db)
    assert alert.alert_id not in reloaded.active_alerts
    assert any(
        item.alert_id == alert.alert_id
        and item.status is AlertStatus.RESOLVED
        for item in reloaded.get_alerts()
    )



@pytest.mark.parametrize(
    "threshold",
    [
        80,
        "high",
        {"cpu": 80, "memory": [70, 90]},
        [10, 20, 30],
        None,
    ],
)
def test_threshold_round_trips_through_database(alert_env, threshold):
    db, manager = alert_env
    rule = make_rule()
    rule.threshold = threshold

    assert manager.create_rule(rule)

    stored = db.execute(
        "SELECT threshold FROM alert_rules WHERE rule_id = ?",
        (rule.rule_id,),
    ).fetchone()[0]
    assert stored is not None

    restored = AlertManager(db)
    assert restored.rules[rule.rule_id].threshold == threshold


def test_invalid_persisted_escalation_path_does_not_break_manager_load(alert_env):
    db, manager = alert_env
    assert manager.create_rule(make_rule())

    db.execute(
        "UPDATE alert_rules SET escalation_path = ? WHERE rule_id = ?",
        ("{not-valid-json", "test-rule"),
    )
    db.commit()

    restored = AlertManager(db)
    assert restored.rules["test-rule"].escalation_path == []

# HTTP route tests: authentication, permissions, CSRF and persistence.
# Every test uses a temporary SQLite database; no live DB is accessed.

import os
from contextlib import closing

os.environ.setdefault("LUMS_SECRET_KEY", "pytest-only-test-secret")


@pytest.fixture
def alert_http_env(tmp_path, monkeypatch):
    import server.app as app_module

    db_path = tmp_path / "alerts-http-test.db"

    def connect_test_db():
        connection = sqlite3.connect(str(db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    with closing(connect_test_db()) as connection:
        connection.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL DEFAULT 'test',
                created_at TEXT NOT NULL DEFAULT '2026-01-01T00:00:00Z',
                enabled INTEGER NOT NULL DEFAULT 1,
                role TEXT NOT NULL,
                admin_note TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE user_permissions (
                user_id INTEGER NOT NULL,
                permission TEXT NOT NULL,
                PRIMARY KEY (user_id, permission),
                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            );

            INSERT INTO users (id, username, role) VALUES
                (1, 'test-admin', 'administrator'),
                (2, 'test-operator', 'operator'),
                (3, 'test-viewer', 'viewer');

            INSERT INTO user_permissions (user_id, permission) VALUES
                (1, 'alerts.view'),
                (1, 'alerts.manage');
        """)
        connection.commit()

    monkeypatch.setitem(
        app_module.app.config, "LUMS_GET_CONNECTION", connect_test_db
    )
    monkeypatch.setattr(app_module, "get_connection", connect_test_db)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)

    client = app_module.app.test_client()

    def authenticate(user_id, username):
        with client.session_transaction(base_url="https://localhost") as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["csrf_token"] = "pytest-csrf-token"
            sess.permanent = True

    return {
        "app": app_module.app,
        "client": client,
        "db_path": db_path,
        "connect": connect_test_db,
        "authenticate": authenticate,
    }


def _alert_http_payload(**overrides):
    payload = {
        "name": "HTTP integration rule",
        "description": "Created by an isolated HTTP test",
        "condition": "cpu_usage > threshold",
        "threshold": 80,
        "severity": "warning",
        "enabled": True,
        "escalation_path": [],
        "group_similar": True,
        "deduplicate": True,
    }
    payload.update(overrides)
    return payload


def _alert_http_create(env, **overrides):
    return env["client"].post(
        "/alerts/rules",
        base_url="https://localhost",
        json=_alert_http_payload(**overrides),
        headers={"X-CSRF-Token": "pytest-csrf-token"},
    )


def test_alert_rules_redirects_when_not_authenticated(alert_http_env):
    response = alert_http_env["client"].get(
        "/alerts/rules", base_url="https://localhost"
    )
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")


def test_alert_rules_forbidden_without_view_permission(alert_http_env):
    env = alert_http_env
    env["authenticate"](3, "test-viewer")

    response = env["client"].get(
        "/alerts/rules", base_url="https://localhost"
    )
    assert response.status_code == 403


def test_alert_rule_create_requires_csrf(alert_http_env):
    env = alert_http_env
    env["authenticate"](1, "test-admin")

    response = env["client"].post(
        "/alerts/rules",
        base_url="https://localhost",
        json=_alert_http_payload(),
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "csrf_validation_failed"


def test_alert_rule_create_forbidden_for_operator(alert_http_env):
    env = alert_http_env
    env["authenticate"](2, "test-operator")

    response = env["client"].post(
        "/alerts/rules",
        base_url="https://localhost",
        headers={"X-CSRF-Token": "pytest-csrf-token"},
        json=_alert_http_payload(),
    )
    assert response.status_code == 403


def test_alert_http_create_and_list_rule(alert_http_env):
    env = alert_http_env
    env["authenticate"](1, "test-admin")

    response = _alert_http_create(
        env, threshold={"operator": ">", "value": 80}
    )
    assert response.status_code == 201
    created_rule = response.get_json()["rule"]
    rule_id = created_rule["rule_id"]
    assert created_rule["threshold"] == {"operator": ">", "value": 80}

    # A subsequent request reloads the manager from the persisted database.
    response = env["client"].get(
        "/alerts/rules", base_url="https://localhost"
    )
    assert response.status_code == 200
    persisted = next(
        rule for rule in response.get_json()["rules"]
        if rule["rule_id"] == rule_id
    )
    assert persisted["threshold"] == {"operator": ">", "value": 80}


def test_alert_http_update_persists_changes(alert_http_env):
    env = alert_http_env
    env["authenticate"](1, "test-admin")

    created = _alert_http_create(env)
    assert created.status_code == 201
    rule_id = created.get_json()["rule"]["rule_id"]

    updated = env["client"].put(
        f"/alerts/rules/{rule_id}",
        base_url="https://localhost",
        json={"name": "Updated HTTP rule", "threshold": 95},
        headers={"X-CSRF-Token": "pytest-csrf-token"},
    )
    assert updated.status_code == 200

    listed = env["client"].get(
        "/alerts/rules", base_url="https://localhost"
    )
    persisted = next(
        rule for rule in listed.get_json()["rules"]
        if rule["rule_id"] == rule_id
    )
    assert persisted["name"] == "Updated HTTP rule"
    assert persisted["threshold"] == 95


def test_alert_http_delete_rule(alert_http_env):
    env = alert_http_env
    env["authenticate"](1, "test-admin")

    created = _alert_http_create(env)
    assert created.status_code == 201
    rule_id = created.get_json()["rule"]["rule_id"]

    deleted = env["client"].delete(
        f"/alerts/rules/{rule_id}",
        base_url="https://localhost",
        headers={"X-CSRF-Token": "pytest-csrf-token"},
    )
    assert deleted.status_code == 200

    listed = env["client"].get(
        "/alerts/rules", base_url="https://localhost"
    )
    assert all(
        rule["rule_id"] != rule_id
        for rule in listed.get_json()["rules"]
    )



@pytest.mark.parametrize(
    "payload",
    [
        [],
        "not-an-object",
        42,
        None,
        {},
        {"rule_id": "", "message": "test"},
        {"rule_id": "rule", "message": ""},
        {"rule_id": 123, "message": "test"},
        {"rule_id": "rule", "message": 123},
        {"rule_id": "rule", "message": "test", "source": ""},
        {"rule_id": "rule", "message": "test", "source": 123},
        {"rule_id": "rule", "message": "test", "metadata": []},
        {"rule_id": "rule", "message": "test", "metadata": "not-an-object"},
        {"rule_id": "rule", "message": "test", "unexpected": True},
    ],
)
def test_alert_http_trigger_rejects_invalid_payloads(alert_http_env, payload):
    env = alert_http_env
    env["authenticate"](1, "test-admin")

    response = env["client"].post(
        "/alerts/trigger",
        base_url="https://localhost",
        json=payload,
        headers={"X-CSRF-Token": "pytest-csrf-token"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid request"

    with closing(env["connect"]()) as connection:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'alerts'"
        ).fetchone()

        count = (
            connection.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            if table_exists
            else 0
        )
    assert count == 0


def test_alert_http_trigger_rejects_malformed_json(alert_http_env):
    env = alert_http_env
    env["authenticate"](1, "test-admin")

    response = env["client"].post(
        "/alerts/trigger",
        base_url="https://localhost",
        data='{"rule_id":',
        content_type="application/json",
        headers={"X-CSRF-Token": "pytest-csrf-token"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid request"

    with closing(env["connect"]()) as connection:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'alerts'"
        ).fetchone()

        count = (
            connection.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            if table_exists
            else 0
        )
    assert count == 0


def test_alert_http_rejects_deleting_referenced_rule(alert_http_env):
    env = alert_http_env
    env["authenticate"](1, "test-admin")

    created = _alert_http_create(env)
    assert created.status_code == 201
    rule_id = created.get_json()["rule"]["rule_id"]

    triggered = env["client"].post(
        "/alerts/trigger",
        base_url="https://localhost",
        json={
            "rule_id": rule_id,
            "source": "pytest",
            "message": "Synthetic referenced alert",
            "metadata": {"test": True},
        },
        headers={"X-CSRF-Token": "pytest-csrf-token"},
    )
    assert triggered.status_code == 201

    deleted = env["client"].delete(
        f"/alerts/rules/{rule_id}",
        base_url="https://localhost",
        headers={"X-CSRF-Token": "pytest-csrf-token"},
    )
    assert deleted.status_code == 409
    assert deleted.get_json()["error"] == (
        "Rule cannot be deleted while it is referenced"
    )

    listed = env["client"].get(
        "/alerts/rules", base_url="https://localhost"
    )
    assert any(
        rule["rule_id"] == rule_id
        for rule in listed.get_json()["rules"]
    )


def test_triggered_alert_ids_are_unique(alert_env):
    db, manager = alert_env
    assert manager.create_rule(make_rule())

    first = manager.trigger_alert(
        "test-rule", "pytest-client", "First synthetic alert"
    )
    second = manager.trigger_alert(
        "test-rule", "pytest-client", "Second synthetic alert"
    )

    assert first is not None
    assert second is not None
    assert first.alert_id != second.alert_id
    assert first.alert_id.startswith("test-rule_")
    assert second.alert_id.startswith("test-rule_")
    assert db.execute(
        "SELECT COUNT(*) FROM alerts WHERE rule_id = ?",
        ("test-rule",),
    ).fetchone()[0] == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": 123},
        {"condition": " "},
        {"description": None},
        {"severity": "unknown"},
        {"enabled": "false"},
        {"group_similar": 1},
        {"deduplicate": None},
        {"escalation_path": "not-a-list"},
        {"escalation_path": ["ok", 4]},
        {"threshold": float("nan")},
        {"unknown_field": "rejected"},
    ],
)
def test_alert_http_create_rejects_invalid_rule_payloads(alert_http_env, overrides):
    env = alert_http_env
    env["authenticate"](1, "test-admin")

    response = _alert_http_create(env, **overrides)

    assert response.status_code == 400
    # Invalid input must be rejected before a rule is persisted.
    # The isolated HTTP fixture may not initialize alert tables when the
    # request is rejected before AlertManager is used.
    with closing(env["connect"]()) as db:
        table = db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'alert_rules'"
        ).fetchone()
        if table is not None:
            count = db.execute("SELECT COUNT(*) FROM alert_rules").fetchone()[0]
            assert count == 0


@pytest.mark.parametrize(
    "updates",
    [
        {"name": ""},
        {"condition": None},
        {"description": 123},
        {"severity": "unknown"},
        {"enabled": "yes"},
        {"group_similar": 0},
        {"deduplicate": "true"},
        {"escalation_path": [None]},
        {"threshold": float("nan")},
        {"unknown_field": "rejected"},
    ],
)
def test_alert_http_update_rejects_invalid_rule_payloads(alert_http_env, updates):
    import json

    env = alert_http_env
    env["authenticate"](1, "test-admin")
    created = _alert_http_create(env)
    assert created.status_code == 201
    original = created.get_json()["rule"]

    response = env["client"].put(
        f"/alerts/rules/{original['rule_id']}",
        base_url="https://localhost",
        json=updates,
        headers={"X-CSRF-Token": "pytest-csrf-token"},
    )
    assert response.status_code == 400

    with closing(env["connect"]()) as db:
        row = db.execute(
            "SELECT name, description, condition, threshold, severity, enabled, "
            "escalation_path, group_similar, deduplicate FROM alert_rules "
            "WHERE rule_id = ?",
            (original["rule_id"],),
        ).fetchone()

    assert row is not None
    assert row["name"] == original["name"]
    assert row["description"] == original["description"]
    assert row["condition"] == original["condition"]
    assert json.loads(row["threshold"]) == original["threshold"]
    assert row["severity"] == original["severity"]
    assert row["enabled"] == int(original["enabled"])
    assert json.loads(row["escalation_path"]) == original["escalation_path"]
    assert row["group_similar"] == int(original["group_similar"])
    assert row["deduplicate"] == int(original["deduplicate"])

def test_notification_exception_does_not_hide_persisted_alert(alert_env):
    db, manager = alert_env
    assert manager.create_rule(make_rule())

    def fail_notification(alert, rule):
        raise RuntimeError("simulated notification failure")

    manager._notify_alert = fail_notification

    alert = manager.trigger_alert(
        "test-rule", "pytest-client", "Alert remains persisted"
    )

    assert alert is not None
    assert alert.alert_id in manager.active_alerts
    assert db.execute(
        "SELECT status FROM alerts WHERE alert_id = ?",
        (alert.alert_id,),
    ).fetchone() == ("triggered",)
    assert not db.in_transaction


def test_notification_log_failure_rolls_back_transaction(alert_env):
    db, manager = alert_env

    # Foreign keys are enabled by the alert_env fixture. This deliberately
    # uses a nonexistent alert to force the log insert to fail.
    manager._log_notification(
        "missing-alert", "missing-integration", False
    )

    assert not db.in_transaction
    assert db.execute(
        "SELECT COUNT(*) FROM alert_notifications_log"
    ).fetchone()[0] == 0


@pytest.mark.parametrize("transition", ["acknowledge", "resolve", "escalate"])
def test_status_transition_rolls_back_when_history_insert_fails(
    alert_env, transition
):
    db, manager = alert_env
    assert manager.create_rule(make_rule())

    alert = manager.trigger_alert(
        "test-rule", "pytest-client", "Rollback regression"
    )
    assert alert is not None

    original_status = alert.status
    original_escalation_count = alert.escalation_count
    original_acknowledged_at = alert.acknowledged_at
    original_resolved_at = alert.resolved_at
    original_metadata = dict(alert.metadata)

    db.execute("""
        CREATE TRIGGER fail_alert_history_insert
        BEFORE INSERT ON alert_history
        BEGIN
            SELECT RAISE(ABORT, 'simulated history insert failure');
        END
    """)
    db.commit()

    if transition == "acknowledge":
        result = manager.acknowledge_alert(alert.alert_id, "pytest-operator")
        assert result is False
    elif transition == "resolve":
        result = manager.resolve_alert(alert.alert_id, "pytest-operator")
        assert result is False
    else:
        result = manager.escalate_alert(alert.alert_id, "pytest-operator")
        assert result is None

    row = db.execute(
        "SELECT status, escalation_count, acknowledged_at, resolved_at, metadata "
        "FROM alerts WHERE alert_id = ?",
        (alert.alert_id,),
    ).fetchone()

    assert row[0] == original_status.value
    assert row[1] == original_escalation_count
    assert row[2] == (
        original_acknowledged_at.isoformat()
        if original_acknowledged_at is not None
        else None
    )
    assert row[3] == (
        original_resolved_at.isoformat()
        if original_resolved_at is not None
        else None
    )
    assert json.loads(row[4]) == original_metadata

    assert alert.status == original_status
    assert alert.escalation_count == original_escalation_count
    assert alert.acknowledged_at == original_acknowledged_at
    assert alert.resolved_at == original_resolved_at
    assert alert.metadata == original_metadata
    assert alert.alert_id in manager.active_alerts
    assert not db.in_transaction
