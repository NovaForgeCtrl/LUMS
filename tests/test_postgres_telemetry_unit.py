"""Database-free tests for PostgreSQL telemetry routes."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from psycopg.types.json import Jsonb

from server import postgres_flask_security as pg_security
from server import postgres_telemetry as telemetry
from server.postgres_app import create_postgres_app
from server.security import hash_client_token


BASE_URL = "https://localhost"
TOKEN = "postgres-telemetry-test-token"
TOKEN_HASH = hash_client_token(TOKEN)


class FakeCursor:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = list(many or [])

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

        # Transaction characteristics are handled by the driver.
        # The fake adapter records the statement but does not delegate it
        # to query-specific handlers.
        if sql.startswith("SET TRANSACTION "):
            return FakeCursor()

        if self.handler:
            result = self.handler(self, sql, params)
            if result is not None:
                return result
        return FakeCursor()

    def close(self):
        self.closed = True


def auth_handler(valid=True):
    def handler(connection, sql, params):
        if "WHERE client_token_hash = %s" in sql:
            if not valid:
                return FakeCursor()
            return FakeCursor(one={
                "id": 1,
                "hostname": "telemetry-agent-01",
                "enabled": True,
                "client_token_hash": TOKEN_HASH,
                "token_revoked_at": None,
            })
        return FakeCursor()
    return handler


def locked_client():
    return {
        "id": 1,
        "enabled": True,
        "client_token_hash": TOKEN_HASH,
        "token_revoked_at": None,
    }


def write_handler(previous=None, locked=None):
    def handler(connection, sql, params):
        if "FOR UPDATE" in sql:
            return FakeCursor(one=locked or locked_client())
        if "FROM client_system_status" in sql:
            return FakeCursor(one=previous)
        return FakeCursor()
    return handler


def make_environment(monkeypatch, handlers, permissions=None):
    connections = []

    def factory():
        index = len(connections)
        handler = handlers[index] if index < len(handlers) else None
        connection = FakeConnection(handler)
        connections.append(connection)
        return connection

    app = create_postgres_app({
        "SECRET_KEY": "postgres-telemetry-test-secret",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": factory,
    })

    state = SimpleNamespace(
        user={
            "id": 7,
            "username": "telemetry-user",
            "enabled": True,
            "role": "administrator",
        },
        permissions=permissions or frozenset({"clients.view"}),
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

    monkeypatch.setattr(telemetry, "transaction", fake_transaction)
    return app, app.test_client(), connections


def set_session(client):
    with client.session_transaction(base_url=BASE_URL) as session:
        session.clear()
        session.update({
            "user_id": 7,
            "username": "telemetry-user",
            "csrf_token": "postgres-telemetry-test-csrf",
        })


def payload(**overrides):
    result = {
        "cpu_percent": 37.5,
        "memory_percent": 62.0,
        "memory_total_bytes": 8_000_000_000,
        "memory_available_bytes": 3_040_000_000,
    }
    result.update(overrides)
    return result


def system_snapshot():
    now = datetime.now(timezone.utc).isoformat()
    return {
        "load_average": [0.5, 0.4, 0.3],
        "uptime_seconds": 12345,
        "os": "Debian GNU/Linux 13",
        "kernel": "6.12.0",
        "disk": {
            "total_bytes": 10000,
            "used_bytes": 4000,
            "free_bytes": 6000,
        },
        "interfaces": [{
            "name": "eth0",
            "state": "up",
            "rx_bytes": 1000,
            "tx_bytes": 500,
            "rx_errors": 0,
            "tx_errors": 0,
            "rx_dropped": 0,
            "tx_dropped": 0,
        }],
        "dns_servers": ["192.0.2.53"],
        "gateway": "192.0.2.1",
        "gateway_reachable": True,
        "dns_reachable": True,
        "internet_reachable": True,
        "temperatures": [{"name": "CPU", "celsius": 42.5}],
        "fans": [{"name": "fan1", "rpm": 1200}],
        "services": {
            "available": True,
            "items": [{
                "name": "ssh.service",
                "state": "failed",
                "substate": "failed",
                "restarts": 1,
                "runtime_seconds": 3600,
            }],
        },
        "containers": {
            "available": True,
            "items": [{
                "runtime": "docker",
                "name": "lums",
                "state": "up",
            }],
        },
        "security_events": {
            "ssh_available": True,
            "ssh_failed_24h": 2,
            "ssh_last_failed_at": now,
            "journal_available": True,
            "journal_errors_1h": 1,
            "journal_warnings_1h": 3,
            "login_history_available": True,
            "login_events": [{
                "timestamp": now,
                "action": "login",
            }],
            "boot_history_available": True,
            "boot_history": [{
                "started_at": now,
                "ended_at": now,
            }],
        },
    }


def test_missing_client_token_does_not_open_database(monkeypatch):
    _, client, connections = make_environment(monkeypatch, [])

    response = client.post(
        "/api/telemetry",
        json=payload(),
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == (
        "client_authentication_required"
    )
    assert connections == []


def test_invalid_client_token_is_rejected(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [auth_handler(valid=False)],
    )

    response = client.post(
        "/api/telemetry",
        headers={"Authorization": "Bearer invalid-token"},
        json=payload(),
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert len(connections) == 1
    assert connections[0].closed


def test_invalid_payload_is_rejected_before_write_connection(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [auth_handler()],
    )

    response = client.post(
        "/api/telemetry",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=payload(cpu_percent=101),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert len(connections) == 1
    assert connections[0].closed


def test_ingestion_locks_client_and_commits_retention(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [auth_handler(), write_handler()],
    )

    response = client.post(
        "/api/telemetry",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=payload(network_rx_bytes=1000, network_tx_bytes=500),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == {"status": "received"}
    assert len(connections) == 2

    connection = connections[1]
    assert all(item.closed for item in connections)
    assert connection.events == ["begin", "commit"]

    statements = [sql for sql, params in connection.statements]
    lock_index = next(
        i for i, sql in enumerate(statements) if "FOR UPDATE" in sql
    )
    insert_index = next(
        i for i, sql in enumerate(statements)
        if "INSERT INTO client_telemetry (" in sql
    )
    assert lock_index < insert_index

    deletes = [
        params
        for sql, params in connection.statements
        if sql.startswith("DELETE FROM client_telemetry")
        or sql.startswith("DELETE FROM client_telemetry_events")
    ]
    assert len(deletes) == 2
    assert all(
        isinstance(params[0], datetime)
        and params[0].tzinfo is not None
        for params in deletes
    )


def test_ingestion_rechecks_revoked_token_under_lock(monkeypatch):
    revoked = locked_client()
    revoked["token_revoked_at"] = datetime.now(timezone.utc)

    _, client, connections = make_environment(
        monkeypatch,
        [auth_handler(), write_handler(locked=revoked)],
    )

    response = client.post(
        "/api/telemetry",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=payload(),
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    connection = connections[1]
    assert any("FOR UPDATE" in sql for sql, _ in connection.statements)
    assert not any(
        "INSERT INTO client_telemetry (" in sql
        for sql, _ in connection.statements
    )
    assert connection.events == ["begin", "commit"]


def test_snapshot_uses_jsonb_and_persists_transition_events(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [auth_handler(), write_handler()],
    )

    response = client.post(
        "/api/telemetry",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=payload(system=system_snapshot()),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    connection = connections[1]

    status_insert = next(
        params for sql, params in connection.statements
        if sql.startswith("INSERT INTO client_system_status")
    )
    assert isinstance(status_insert[2], Jsonb)
    assert status_insert[2].obj["os"] == "Debian GNU/Linux 13"

    event_statements = [
        (sql, params)
        for sql, params in connection.statements
        if sql.startswith("INSERT INTO client_telemetry_events")
    ]
    assert len(event_statements) == 2
    assert any(
        "'ssh_failure', 'ssh'" in sql and params[2] == 2
        for sql, params in event_statements
    )
    assert any(
        params[2] == "service_failed"
        and params[3] == "ssh.service"
        for sql, params in event_statements
    )


def test_timestamp_parser_accepts_postgres_datetime_and_iso():
    aware = datetime(2026, 11, 2, 12, 30, tzinfo=timezone.utc)
    naive = datetime(2026, 11, 2, 12, 30)

    assert telemetry.parse_telemetry_time(aware) == aware
    assert telemetry.parse_telemetry_time(naive).tzinfo == timezone.utc
    assert telemetry.parse_telemetry_time(
        "2026-11-02T12:30:00+00:00"
    ) == aware
    assert telemetry.parse_telemetry_time(None) is None


def test_history_serializes_postgres_datetimes_and_calculates_rates(
    monkeypatch,
):
    first_time = datetime.now(timezone.utc) - timedelta(seconds=10)
    second_time = first_time + timedelta(seconds=10)

    def history_handler(connection, sql, params):
        if "FROM clients" in sql:
            return FakeCursor(one={
                "id": 1,
                "hostname": "telemetry-agent-01",
            })
        if "FROM client_telemetry" in sql:
            return FakeCursor(many=[
                {
                    "recorded_at": first_time,
                    "cpu_percent": 10.0,
                    "memory_percent": 20.0,
                    "memory_total_bytes": 1000,
                    "memory_available_bytes": 800,
                    "network_rx_bytes": 1000,
                    "network_tx_bytes": 500,
                    "disk_percent": 40.0,
                },
                {
                    "recorded_at": second_time,
                    "cpu_percent": 15.0,
                    "memory_percent": 25.0,
                    "memory_total_bytes": 1000,
                    "memory_available_bytes": 750,
                    "network_rx_bytes": 2000,
                    "network_tx_bytes": 1000,
                    "disk_percent": 45.0,
                },
            ])
        return FakeCursor()

    _, client, connections = make_environment(
        monkeypatch,
        [None, history_handler],
    )
    set_session(client)

    response = client.get(
        "/api/clients/1/telemetry?hours=24",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["hostname"] == "telemetry-agent-01"
    assert len(data["samples"]) == 2
    assert data["samples"][0]["recorded_at"] == first_time.isoformat()
    assert data["samples"][1]["recorded_at"] == second_time.isoformat()
    assert data["samples"][1]["network_rx_bytes_per_second"] == 100.0
    assert data["samples"][1]["network_tx_bytes_per_second"] == 50.0
    assert all(connection.closed for connection in connections)


def test_history_rejects_invalid_hours_without_route_query(monkeypatch):
    _, client, connections = make_environment(monkeypatch, [None])
    set_session(client)

    response = client.get(
        "/api/clients/1/telemetry?hours=169",
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_hours"
    assert len(connections) == 1
    assert connections[0].closed


def test_all_postgres_telemetry_routes_are_registered(monkeypatch):
    app, _, connections = make_environment(monkeypatch, [])

    routes = {rule.rule for rule in app.url_map.iter_rules()}

    assert {
        "/api/telemetry",
        "/api/telemetry/dashboard-settings",
        "/api/telemetry/overview",
        "/api/clients/<int:client_id>/telemetry",
        "/api/clients/<int:client_id>/telemetry/events",
        "/api/clients/<int:client_id>/telemetry/export",
    }.issubset(routes)
    assert connections == []


def test_dashboard_settings_get_returns_defaults(monkeypatch):
    def handler(connection, sql, params):
        if "FROM user_dashboard_settings" in sql:
            assert params == (7,)
            return FakeCursor()
        return FakeCursor()

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.get(
        "/api/telemetry/dashboard-settings",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == (
        telemetry.default_telemetry_dashboard_settings()
    )
    assert all(connection.closed for connection in connections)
    assert connections[1].events == ["begin", "commit"]


def test_dashboard_settings_put_uses_jsonb_and_transaction(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [None, None],
    )
    set_session(client)

    settings = telemetry.default_telemetry_dashboard_settings()
    settings["thresholds"]["cpu"] = 85
    settings["integrations"]["wazuh"] = True

    response = client.put(
        "/api/telemetry/dashboard-settings",
        headers={"X-CSRF-Token": "postgres-telemetry-test-csrf"},
        json=settings,
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == {"status": "saved"}

    connection = connections[1]
    insert = next(
        params for sql, params in connection.statements
        if sql.startswith("INSERT INTO user_dashboard_settings")
    )

    assert insert[0] == 7
    assert isinstance(insert[1], Jsonb)
    assert insert[1].obj == settings
    assert isinstance(insert[2], datetime)
    assert connection.events == ["begin", "commit"]
    assert all(item.closed for item in connections)


def test_dashboard_settings_get_migrates_legacy_system_widget(monkeypatch):
    settings = telemetry.default_telemetry_dashboard_settings()
    settings["layout"].insert(
        2,
        {"id": "system", "width": 12, "visible": True},
    )

    def handler(connection, sql, params):
        if "FROM user_dashboard_settings" in sql:
            return FakeCursor(one={"settings_json": settings})
        return FakeCursor()

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.get(
        "/api/telemetry/dashboard-settings",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    migrated = response.get_json()
    assert "system" not in [
        widget["id"] for widget in migrated["layout"]
    ]

    update = next(
        params for sql, params in connections[1].statements
        if sql.startswith("UPDATE user_dashboard_settings")
    )
    assert isinstance(update[0], Jsonb)
    assert "system" not in [
        widget["id"] for widget in update[0].obj["layout"]
    ]
    assert isinstance(update[1], datetime)
    assert connections[1].events == ["begin", "commit"]


def test_dashboard_settings_put_requires_csrf(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [None],
    )
    set_session(client)

    response = client.put(
        "/api/telemetry/dashboard-settings",
        json=telemetry.default_telemetry_dashboard_settings(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "csrf_validation_failed"
    assert len(connections) == 1
    assert connections[0].closed


def test_telemetry_events_include_threshold_persisted_and_system_events(
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    system = {
        "services": {
            "items": [{
                "name": "ssh.service",
                "state": "failed",
            }],
        },
        "security_events": {
            "ssh_failed_24h": 4,
            "ssh_last_failed_at": now.isoformat(),
        },
    }

    def handler(connection, sql, params):
        if "FROM clients" in sql:
            return FakeCursor(one={
                "id": 1,
                "hostname": "telemetry-agent-01",
            })

        if "FROM user_dashboard_settings" in sql:
            return FakeCursor()

        if "FROM client_telemetry_events" in sql:
            return FakeCursor(many=[{
                "recorded_at": now,
                "event_type": "ssh_failure",
                "metric": "ssh",
                "value": 4,
            }])

        if "FROM client_system_status" in sql:
            return FakeCursor(one={
                "recorded_at": now,
                "payload_json": system,
            })

        if "FROM client_telemetry" in sql:
            return FakeCursor(many=[{
                "recorded_at": now - timedelta(seconds=5),
                "cpu_percent": 95.0,
                "memory_percent": 20.0,
                "memory_total_bytes": 1000,
                "memory_available_bytes": 800,
                "network_rx_bytes": None,
                "network_tx_bytes": None,
                "disk_percent": 10.0,
            }])

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.get(
        "/api/clients/1/telemetry/events?hours=24",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["client_id"] == 1
    assert data["hostname"] == "telemetry-agent-01"

    events = data["events"]
    kinds = [event["kind"] for event in events]

    assert "threshold_exceeded" in kinds
    assert "ssh_failure" in kinds
    assert "service_failed" in kinds
    assert kinds.count("ssh_failure") == 1
    assert events == sorted(
        events,
        key=lambda event: event["timestamp"],
        reverse=True,
    )
    assert connections[1].events == ["begin", "commit"]
    assert all(connection.closed for connection in connections)


def test_telemetry_events_csv_export(monkeypatch):
    now = datetime.now(timezone.utc)

    def handler(connection, sql, params):
        if "FROM clients" in sql:
            return FakeCursor(one={
                "id": 1,
                "hostname": "telemetry-agent-01",
            })
        if "FROM user_dashboard_settings" in sql:
            return FakeCursor()
        if "FROM client_telemetry_events" in sql:
            return FakeCursor(many=[{
                "recorded_at": now,
                "event_type": "service_failed",
                "metric": "ssh.service",
                "value": None,
            }])
        if "FROM client_system_status" in sql:
            return FakeCursor()
        if "FROM client_telemetry" in sql:
            return FakeCursor()
        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.get(
        "/api/clients/1/telemetry/events?hours=24&format=csv",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "telemetry-events-client-1.csv" in (
        response.headers["Content-Disposition"]
    )
    assert "timestamp,kind,metric,value,threshold" in (
        response.get_data(as_text=True)
    )
    assert "service_failed" in response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    assert all(connection.closed for connection in connections)


def test_telemetry_events_reject_invalid_format_before_route_connection(
    monkeypatch,
):
    _, client, connections = make_environment(
        monkeypatch,
        [None],
    )
    set_session(client)

    response = client.get(
        "/api/clients/1/telemetry/events?format=xml",
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_format"
    assert len(connections) == 1
    assert connections[0].closed


def test_telemetry_export_json_serializes_postgres_datetimes(monkeypatch):
    now = datetime.now(timezone.utc)
    sample_time = now - timedelta(seconds=10)

    def handler(connection, sql, params):
        if "FROM clients" in sql:
            return FakeCursor(one={
                "id": 1,
                "hostname": "telemetry-agent-01",
            })
        if "FROM client_telemetry" in sql:
            return FakeCursor(many=[{
                "recorded_at": sample_time,
                "cpu_percent": 22.0,
                "memory_percent": 44.0,
                "memory_total_bytes": 1000,
                "memory_available_bytes": 600,
                "network_rx_bytes": None,
                "network_tx_bytes": None,
                "disk_percent": 40.0,
            }])
        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.get(
        "/api/clients/1/telemetry/export?hours=24&format=json",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["client_id"] == 1
    assert data["hostname"] == "telemetry-agent-01"
    assert data["samples"][0]["recorded_at"] == sample_time.isoformat()
    assert response.headers["Cache-Control"] == "no-store"
    assert "attachment; filename=" in (
        response.headers["Content-Disposition"]
    )
    assert all(connection.closed for connection in connections)


def test_telemetry_export_csv_contains_expected_columns(monkeypatch):
    sample_time = datetime.now(timezone.utc)

    def handler(connection, sql, params):
        if "FROM clients" in sql:
            return FakeCursor(one={
                "id": 1,
                "hostname": "telemetry-agent-01",
            })
        if "FROM client_telemetry" in sql:
            return FakeCursor(many=[{
                "recorded_at": sample_time,
                "cpu_percent": 22.0,
                "memory_percent": 44.0,
                "memory_total_bytes": 1000,
                "memory_available_bytes": 600,
                "network_rx_bytes": None,
                "network_tx_bytes": None,
                "disk_percent": 40.0,
            }])
        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.get(
        "/api/clients/1/telemetry/export?hours=24&format=csv",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    csv_text = response.get_data(as_text=True)
    assert response.mimetype == "text/csv"
    assert "recorded_at,cpu_percent,memory_percent" in csv_text
    assert sample_time.isoformat() in csv_text
    assert response.headers["Cache-Control"] == "no-store"
    assert all(connection.closed for connection in connections)


def test_telemetry_overview_preserves_ui_fields_and_health(monkeypatch):
    now = datetime.now(timezone.utc)
    previous_time = now - timedelta(seconds=20)
    latest_time = now - timedelta(seconds=10)
    system = system_snapshot()

    def handler(connection, sql, params):
        if "FROM clients" in sql:
            return FakeCursor(many=[{
                "id": 1,
                "hostname": "telemetry-agent-01",
                "last_seen": now - timedelta(seconds=5),
            }])

        if "FROM client_telemetry" in sql:
            return FakeCursor(many=[
                {
                    "recorded_at": latest_time,
                    "cpu_percent": 30.0,
                    "memory_percent": 40.0,
                    "memory_total_bytes": 1000,
                    "memory_available_bytes": 600,
                    "network_rx_bytes": 3000,
                    "network_tx_bytes": 1500,
                },
                {
                    "recorded_at": previous_time,
                    "cpu_percent": 20.0,
                    "memory_percent": 30.0,
                    "memory_total_bytes": 1000,
                    "memory_available_bytes": 700,
                    "network_rx_bytes": 1000,
                    "network_tx_bytes": 500,
                },
            ])

        if "FROM client_system_status" in sql:
            return FakeCursor(one={
                "recorded_at": latest_time,
                "payload_json": system,
            })

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.get(
        "/api/telemetry/overview",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["clients"]) == 1

    entry = data["clients"][0]
    assert entry["client_id"] == 1
    assert entry["hostname"] == "telemetry-agent-01"
    assert entry["status"] == "online"
    assert entry["last_seen"] == (
        now - timedelta(seconds=5)
    ).isoformat()
    assert entry["telemetry_stale"] is False
    assert entry["telemetry_age_seconds"] >= 0
    assert entry["system_age_seconds"] >= 0
    assert entry["system"]["os"] == "Debian GNU/Linux 13"
    assert entry["latest"]["recorded_at"] == latest_time.isoformat()
    assert entry["latest"]["network_rx_bytes_per_second"] == 200.0
    assert entry["latest"]["network_tx_bytes_per_second"] == 100.0
    assert all(connection.closed for connection in connections)
    assert connections[1].events == ["begin", "commit"]
