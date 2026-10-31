import sqlite3
import json
from datetime import datetime, timedelta, timezone

import pytest

import os
os.environ.setdefault("LUMS_SECRET_KEY", "pytest-only-test-secret")

from server import app as app_module
from server.security import (
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    ROLE_DEFAULT_PERMISSIONS,
    hash_client_token,
)


@pytest.fixture
def telemetry_env(tmp_path, monkeypatch):
    db_path = tmp_path / "telemetry-test.db"

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row

    connection.executescript(
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
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

        CREATE TABLE clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT UNIQUE NOT NULL,
            last_seen TEXT NOT NULL,
            client_token_hash TEXT,
            token_created_at TEXT,
            token_revoked_at TEXT,
            enabled INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE client_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            recorded_at TEXT NOT NULL,
            cpu_percent REAL NOT NULL
                CHECK (cpu_percent >= 0 AND cpu_percent <= 100),
            memory_percent REAL NOT NULL
                CHECK (memory_percent >= 0 AND memory_percent <= 100),
            memory_total_bytes INTEGER NOT NULL
                CHECK (memory_total_bytes > 0),
            memory_available_bytes INTEGER NOT NULL
                CHECK (
                    memory_available_bytes >= 0
                    AND memory_available_bytes <= memory_total_bytes
                ),
            network_rx_bytes INTEGER CHECK (
                network_rx_bytes IS NULL OR network_rx_bytes >= 0
            ),
            network_tx_bytes INTEGER CHECK (
                network_tx_bytes IS NULL OR network_tx_bytes >= 0
            ),
            disk_percent REAL CHECK (
                disk_percent IS NULL OR (disk_percent >= 0 AND disk_percent <= 100)
            ),
            FOREIGN KEY (client_id) REFERENCES clients(id)
                ON DELETE CASCADE
        );

        CREATE INDEX idx_client_telemetry_client_time
        ON client_telemetry(client_id, recorded_at);

        CREATE TABLE client_system_status (
            client_id INTEGER PRIMARY KEY,
            recorded_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients(id)
                ON DELETE CASCADE
        );

        CREATE TABLE user_dashboard_settings (
            user_id INTEGER PRIMARY KEY,
            settings_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE client_telemetry_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            recorded_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        );
        """
    )

    now = datetime.now(timezone.utc).isoformat()

    connection.execute(
        """
        INSERT INTO clients (
            id, hostname, last_seen, client_token_hash, enabled
        ) VALUES (1, 'pytest-client', ?, ?, 1)
        """,
        (now, hash_client_token("pytest-client-token")),
    )
    connection.execute(
        """
        INSERT INTO clients (
            id, hostname, last_seen, client_token_hash, enabled
        ) VALUES (2, 'other-client', ?, ?, 1)
        """,
        (now, hash_client_token("other-client-token")),
    )

    roles = [
        (1, "administrator", ROLE_ADMINISTRATOR),
        (2, "operator", ROLE_OPERATOR),
        (3, "viewer", ROLE_VIEWER),
    ]

    for user_id, username, role in roles:
        connection.execute(
            """
            INSERT INTO users (
                id, username, password_hash, created_at, enabled, role
            ) VALUES (?, ?, 'pytest-hash', ?, 1, ?)
            """,
            (user_id, username, now, role),
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

    def get_test_connection():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    monkeypatch.setitem(
        app_module.app.config,
        "LUMS_GET_CONNECTION",
        get_test_connection,
    )
    monkeypatch.setattr(
        app_module,
        "get_connection",
        get_test_connection,
    )
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "WTF_CSRF_ENABLED",
        False,
    )

    return {
        "app": app_module.app,
        "db_path": db_path,
        "connection": get_test_connection,
    }


def login_as(client, user_id=1, username="administrator"):
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["username"] = username
        session.permanent = True


def telemetry_payload(**overrides):
    payload = {
        "cpu_percent": 37.5,
        "memory_percent": 62.0,
        "memory_total_bytes": 8_000_000_000,
        "memory_available_bytes": 3_040_000_000,
    }
    payload.update(overrides)
    return payload


def system_snapshot(**overrides):
    snapshot = {
        "load_average": [0.5, 0.4, 0.3],
        "uptime_seconds": 12345,
        "os": "Ubuntu 24.04",
        "kernel": "6.8.0",
        "disk": {
            "total_bytes": 10000,
            "used_bytes": 4000,
            "free_bytes": 6000,
        },
        "interfaces": [
            {
                "name": "eth0",
                "state": "up",
                "rx_bytes": 1000,
                "tx_bytes": 500,
                "rx_errors": 0,
                "tx_errors": 0,
                "rx_dropped": 0,
                "tx_dropped": 0,
            }
        ],
        "dns_servers": ["192.0.2.53"],
        "gateway": "192.0.2.1",
        "gateway_reachable": True,
        "dns_reachable": True,
        "internet_reachable": False,
        "temperatures": [{"name": "CPU", "celsius": 42.5}],
        "fans": [{"name": "fan1", "rpm": 1200}],
        "services": {
            "available": True,
            "items": [{
                "name": "ssh.service",
                "state": "active",
                "substate": "running",
                "restarts": 1,
                "runtime_seconds": 3600,
            }],
        },
        "containers": {
            "available": True,
            "items": [
                {
                    "runtime": "docker",
                    "name": "lums",
                    "state": "up",
                }
            ],
        },
        "security_events": {
            "ssh_available": True,
            "ssh_failed_24h": 2,
            "ssh_last_failed_at": "2026-10-26T10:00:00+00:00",
            "journal_available": True,
            "journal_errors_1h": 1,
            "journal_warnings_1h": 3,
            "login_history_available": True,
            "login_events": [
                {
                    "timestamp": "2026-10-26T10:15:00+00:00",
                    "action": "login",
                }
            ],
            "boot_history_available": True,
            "boot_history": [{
                "started_at": "2026-10-26T08:00:00+00:00",
                "ended_at": "2026-10-26T10:30:00+00:00",
            }],
        },
    }
    snapshot.update(overrides)
    return snapshot


def test_telemetry_requires_client_token(telemetry_env):
    client = telemetry_env["app"].test_client()

    response = client.post(
        "/api/telemetry",
        json=telemetry_payload(),
    )

    assert response.status_code == 401


def test_telemetry_accepts_valid_sample_and_uses_server_timestamp(
    telemetry_env,
):
    client = telemetry_env["app"].test_client()
    before = datetime.now(timezone.utc)

    response = client.post(
        "/api/telemetry",
        headers={"Authorization": "Bearer pytest-client-token"},
        json=telemetry_payload(),
    )

    after = datetime.now(timezone.utc)

    assert response.status_code == 200
    assert response.get_json()["status"] == "received"

    connection = telemetry_env["connection"]()
    try:
        row = connection.execute(
            """
            SELECT client_id, recorded_at, cpu_percent, memory_percent,
                   memory_total_bytes, memory_available_bytes
            FROM client_telemetry
            """
        ).fetchone()

        assert row is not None
        assert row["client_id"] == 1
        assert row["cpu_percent"] == 37.5
        assert row["memory_percent"] == 62.0
        assert row["memory_total_bytes"] == 8_000_000_000
        assert row["memory_available_bytes"] == 3_040_000_000

        recorded_at = datetime.fromisoformat(row["recorded_at"])
        assert before <= recorded_at <= after
    finally:
        connection.close()


@pytest.mark.parametrize(
    "payload",
    [
        telemetry_payload(cpu_percent=101),
        telemetry_payload(cpu_percent=-1),
        telemetry_payload(memory_percent=101),
        telemetry_payload(memory_percent=-1),
        telemetry_payload(memory_total_bytes=0),
        telemetry_payload(memory_total_bytes=-1),
        telemetry_payload(memory_available_bytes=-1),
        telemetry_payload(memory_available_bytes=8_000_000_001),
        telemetry_payload(cpu_percent=True),
        telemetry_payload(memory_total_bytes=8.5),
        telemetry_payload(unexpected_field="not allowed"),
        [],
        {},
    ],
)
def test_telemetry_rejects_invalid_payload_without_saving(
    telemetry_env,
    payload,
):
    client = telemetry_env["app"].test_client()

    response = client.post(
        "/api/telemetry",
        headers={"Authorization": "Bearer pytest-client-token"},
        json=payload,
    )

    assert response.status_code == 400

    connection = telemetry_env["connection"]()
    try:
        count = connection.execute(
            "SELECT COUNT(*) FROM client_telemetry"
        ).fetchone()[0]
        assert count == 0
    finally:
        connection.close()


def test_telemetry_rejects_non_finite_cpu_value(telemetry_env):
    client = telemetry_env["app"].test_client()

    response = client.post(
        "/api/telemetry",
        headers={"Authorization": "Bearer pytest-client-token"},
        data=(
            '{"cpu_percent": NaN, "memory_percent": 50, '
            '"memory_total_bytes": 8000000000, '
            '"memory_available_bytes": 3000000000}'
        ),
        content_type="application/json",
    )

    assert response.status_code == 400


def test_telemetry_prunes_samples_older_than_seven_days(telemetry_env):
    connection = telemetry_env["connection"]()
    old_timestamp = (
        datetime.now(timezone.utc) - timedelta(days=8)
    ).isoformat()

    connection.execute(
        """
        INSERT INTO client_telemetry (
            client_id, recorded_at, cpu_percent, memory_percent,
            memory_total_bytes, memory_available_bytes
        ) VALUES (1, ?, 10, 20, 1000, 800)
        """,
        (old_timestamp,),
    )
    connection.commit()
    connection.close()

    response = telemetry_env["app"].test_client().post(
        "/api/telemetry",
        headers={"Authorization": "Bearer pytest-client-token"},
        json=telemetry_payload(),
    )

    assert response.status_code == 200

    connection = telemetry_env["connection"]()
    try:
        rows = connection.execute(
            "SELECT recorded_at FROM client_telemetry"
        ).fetchall()

        assert len(rows) == 1
        assert datetime.fromisoformat(rows[0]["recorded_at"]) > (
            datetime.now(timezone.utc) - timedelta(days=7)
        )
    finally:
        connection.close()


def test_telemetry_history_requires_login(telemetry_env):
    client = telemetry_env["app"].test_client()

    response = client.get("/api/clients/1/telemetry")

    assert response.status_code in (302, 401)


def test_telemetry_history_requires_clients_view_permission(
    telemetry_env,
):
    client = telemetry_env["app"].test_client()
    login_as(client, user_id=3, username="viewer")

    connection = telemetry_env["connection"]()
    connection.execute(
        """
        DELETE FROM user_permissions
        WHERE user_id = 3 AND permission = 'clients.view'
        """
    )
    connection.commit()
    connection.close()

    response = client.get("/api/clients/1/telemetry")

    assert response.status_code == 403


def test_telemetry_history_returns_only_requested_client(
    telemetry_env,
):
    client = telemetry_env["app"].test_client()
    login_as(client)

    connection = telemetry_env["connection"]()
    now = datetime.now(timezone.utc).isoformat()
    connection.executemany(
        """
        INSERT INTO client_telemetry (
            client_id, recorded_at, cpu_percent, memory_percent,
            memory_total_bytes, memory_available_bytes
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (1, now, 25, 50, 1000, 500),
            (2, now, 75, 80, 2000, 400),
        ],
    )
    connection.commit()
    connection.close()

    response = client.get("/api/clients/1/telemetry")

    assert response.status_code == 200
    data = response.get_json()
    assert data["client_id"] == 1
    assert len(data["samples"]) == 1
    assert data["samples"][0]["cpu_percent"] == 25


def test_telemetry_dashboard_settings_are_saved_per_user(telemetry_env):
    client = telemetry_env["app"].test_client()
    login_as(client)
    defaults = client.get("/api/telemetry/dashboard-settings")
    assert defaults.status_code == 200
    settings = defaults.get_json()
    settings["thresholds"]["cpu"] = 85
    settings["integrations"]["wazuh"] = True
    settings["layout"][0]["width"] = 6

    with client.session_transaction() as session:
        session["csrf_token"] = "test-csrf"
    saved = client.put(
        "/api/telemetry/dashboard-settings",
        headers={"X-CSRF-Token": "test-csrf"},
        json=settings,
    )
    assert saved.status_code == 200
    assert client.get(
        "/api/telemetry/dashboard-settings"
    ).get_json() == settings

    viewer = telemetry_env["app"].test_client()
    login_as(viewer, user_id=3, username="viewer")
    assert viewer.get(
        "/api/telemetry/dashboard-settings"
    ).get_json()["thresholds"]["cpu"] == 90


def test_dashboard_settings_remove_the_separate_system_monitor_widget(
    telemetry_env,
):
    client = telemetry_env["app"].test_client()
    login_as(client)
    settings = client.get("/api/telemetry/dashboard-settings").get_json()
    ids = [widget["id"] for widget in settings["layout"]]

    assert ids == ["summary", "clients", "history", "events", "backup"]
    assert "system" not in ids


def test_dashboard_settings_migrate_saved_system_monitor_widget(telemetry_env):
    client = telemetry_env["app"].test_client()
    login_as(client)
    settings = client.get("/api/telemetry/dashboard-settings").get_json()
    settings["layout"].insert(
        3, {"id": "system", "width": 12, "visible": True}
    )
    connection = telemetry_env["connection"]()
    connection.execute(
        """
        INSERT INTO user_dashboard_settings (
            user_id, settings_json, updated_at
        ) VALUES (1, ?, ?)
        """,
        (json.dumps(settings), datetime.now(timezone.utc).isoformat()),
    )
    connection.commit()
    connection.close()

    response = client.get("/api/telemetry/dashboard-settings")
    migrated = response.get_json()
    connection = telemetry_env["connection"]()
    stored = connection.execute(
        "SELECT settings_json FROM user_dashboard_settings WHERE user_id = 1"
    ).fetchone()
    connection.close()

    assert response.status_code == 200
    assert "system" not in [widget["id"] for widget in migrated["layout"]]
    assert "system" not in stored["settings_json"]


def test_telemetry_dashboard_settings_reject_invalid_threshold(telemetry_env):
    client = telemetry_env["app"].test_client()
    login_as(client)
    settings = client.get(
        "/api/telemetry/dashboard-settings"
    ).get_json()
    settings["thresholds"]["disk"] = 100
    with client.session_transaction() as session:
        session["csrf_token"] = "test-csrf"

    response = client.put(
        "/api/telemetry/dashboard-settings",
        headers={"X-CSRF-Token": "test-csrf"},
        json=settings,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_dashboard_settings"


def test_telemetry_events_and_exports_are_bounded_and_authenticated(telemetry_env):
    client = telemetry_env["app"].test_client()
    login_as(client)
    now = datetime.now(timezone.utc)
    connection = telemetry_env["connection"]()
    connection.executemany(
        """
        INSERT INTO client_telemetry (
            client_id, recorded_at, cpu_percent, memory_percent,
            memory_total_bytes, memory_available_bytes, disk_percent
        ) VALUES (1, ?, ?, ?, 1000, 500, ?)
        """,
        [
            ((now - timedelta(seconds=60)).isoformat(), 95, 60, 40),
            ((now - timedelta(seconds=30)).isoformat(), 80, 60, 92),
        ],
    )
    connection.commit()
    connection.close()

    events = client.get("/api/clients/1/telemetry/events?hours=1")
    assert events.status_code == 200
    event_items = events.get_json()["events"]
    assert any(item["kind"] == "threshold_exceeded" for item in event_items)
    assert any(item["metric"] == "cpu" for item in event_items)
    assert any(item["metric"] == "disk" for item in event_items)

    event_csv = client.get(
        "/api/clients/1/telemetry/events?hours=1&format=csv"
    )
    assert event_csv.status_code == 200
    assert event_csv.mimetype == "text/csv"
    assert b"timestamp,kind,metric,value,threshold" in event_csv.data

    history_csv = client.get(
        "/api/clients/1/telemetry/export?hours=1&format=csv"
    )
    assert history_csv.status_code == 200
    assert b"disk_percent" in history_csv.data
    history_json = client.get(
        "/api/clients/1/telemetry/export?hours=1&format=json"
    )
    assert history_json.status_code == 200
    assert history_json.get_json()["samples"][0]["disk_percent"] == 40


def test_ingestion_persists_service_and_ssh_event_transitions(telemetry_env):
    client = telemetry_env["app"].test_client()
    login_as(client)
    now = datetime.now(timezone.utc)
    auth_headers = {"Authorization": "Bearer pytest-client-token"}
    first = system_snapshot()
    first["services"]["items"][0]["state"] = "failed"
    first["security_events"]["ssh_last_failed_at"] = now.isoformat()
    first["security_events"]["ssh_failed_24h"] = 3
    failed_response = client.post(
        "/api/telemetry",
        headers=auth_headers,
        json=telemetry_payload(system=first),
    )
    assert failed_response.status_code == 200

    recovered = json.loads(json.dumps(first))
    recovered["services"]["items"][0]["state"] = "active"
    recovery_response = client.post(
        "/api/telemetry",
        headers=auth_headers,
        json=telemetry_payload(system=recovered),
    )
    assert recovery_response.status_code == 200

    connection = telemetry_env["connection"]()
    events = connection.execute(
        """
        SELECT event_type, metric, value
        FROM client_telemetry_events
        WHERE client_id = 1
        ORDER BY id
        """
    ).fetchall()
    connection.close()

    assert [(row["event_type"], row["metric"]) for row in events] == [
        ("service_failed", "ssh.service"),
        ("ssh_failure", "ssh"),
        ("service_recovered", "ssh.service"),
    ]
    assert events[1]["value"] == 3
    history = client.get(
        "/api/clients/1/telemetry/events?hours=1"
    ).get_json()["events"]
    assert [event["kind"] for event in history].count("service_failed") == 1
    assert [event["kind"] for event in history].count("service_recovered") == 1
    assert [event["kind"] for event in history].count("ssh_failure") == 1




@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("enabled", 0),
        ("token_revoked_at", "2026-10-25T00:00:00+00:00"),
    ],
)
def test_telemetry_rejects_disabled_or_revoked_client(
    telemetry_env, field, value
):
    connection = telemetry_env["connection"]()
    connection.execute(
        f"UPDATE clients SET {field} = ? WHERE id = 1",
        (value,),
    )
    connection.commit()
    connection.close()

    response = telemetry_env["app"].test_client().post(
        "/api/telemetry",
        headers={"Authorization": "Bearer pytest-client-token"},
        json=telemetry_payload(),
    )

    assert response.status_code == 401


@pytest.mark.parametrize("hours", ["0", "169", "abc", "-1"])
def test_telemetry_history_rejects_invalid_hours(telemetry_env, hours):
    client = telemetry_env["app"].test_client()
    login_as(client)

    response = client.get(
        f"/api/clients/1/telemetry?hours={hours}"
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_hours"


def test_telemetry_history_downsamples_and_keeps_endpoints(telemetry_env):
    client = telemetry_env["app"].test_client()
    login_as(client)

    count = 1205
    now = datetime.now(timezone.utc)
    connection = telemetry_env["connection"]()
    rows = []

    for index in range(count):
        timestamp = (now - timedelta(seconds=count - index)).isoformat()
        rows.append(
            (
                1, timestamp, index % 101, 50,
                8_000_000_000, 3_000_000_000,
            )
        )

    connection.executemany(
        """
        INSERT INTO client_telemetry (
            client_id, recorded_at, cpu_percent, memory_percent,
            memory_total_bytes, memory_available_bytes
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.commit()
    connection.close()

    response = client.get("/api/clients/1/telemetry?hours=24")

    assert response.status_code == 200
    samples = response.get_json()["samples"]
    assert len(samples) == 1000
    assert samples[0]["recorded_at"] == rows[0][1]
    assert samples[-1]["recorded_at"] == rows[-1][1]
    assert all(
        samples[index]["recorded_at"] <= samples[index + 1]["recorded_at"]
        for index in range(len(samples) - 1)
    )


def post_sample(client, **overrides):
    return client.post(
        "/api/telemetry",
        headers={"Authorization": "Bearer pytest-client-token"},
        json=telemetry_payload(**overrides),
    )


def test_telemetry_stores_optional_network_counters(telemetry_env):
    client = telemetry_env["app"].test_client()

    response = post_sample(
        client, network_rx_bytes=1_000, network_tx_bytes=500
    )

    assert response.status_code == 200
    connection = telemetry_env["connection"]()
    try:
        row = connection.execute(
            "SELECT network_rx_bytes, network_tx_bytes FROM client_telemetry"
        ).fetchone()
        assert (row["network_rx_bytes"], row["network_tx_bytes"]) == (
            1_000, 500
        )
    finally:
        connection.close()


@pytest.mark.parametrize(
    "extra",
    [
        {"network_rx_bytes": 10},
        {"network_tx_bytes": 10},
        {"network_rx_bytes": -1, "network_tx_bytes": 0},
        {"network_rx_bytes": 1.5, "network_tx_bytes": 0},
        {"network_rx_bytes": True, "network_tx_bytes": 0},
        {"network_rx_bytes": 2**63, "network_tx_bytes": 0},
    ],
)
def test_telemetry_rejects_invalid_network_counters(telemetry_env, extra):
    response = post_sample(telemetry_env["app"].test_client(), **extra)

    assert response.status_code == 400


def insert_counter_rows(telemetry_env, rows):
    connection = telemetry_env["connection"]()
    now = datetime.now(timezone.utc)
    connection.executemany(
        """
        INSERT INTO client_telemetry (
            client_id, recorded_at, cpu_percent, memory_percent,
            memory_total_bytes, memory_available_bytes,
            network_rx_bytes, network_tx_bytes
        ) VALUES (1, ?, 10, 20, 1000, 800, ?, ?)
        """,
        [
            ((now - timedelta(seconds=age)).isoformat(), rx, tx)
            for age, rx, tx in rows
        ],
    )
    connection.commit()
    connection.close()


def test_history_calculates_network_rates_and_handles_gaps(telemetry_env):
    client = telemetry_env["app"].test_client()
    login_as(client)
    insert_counter_rows(
        telemetry_env,
        [
            (60, 1_000, 100),
            (50, 3_000, 600),   # 10 s: 200 B/s down, 50 B/s up
            (40, 100, 50),      # counter reset: no rate
            (30, None, None),   # old agent: no rate
            (20, 500, 500),     # previous had no counters: no rate
            (700, None, None),
        ],
    )

    samples = client.get("/api/clients/1/telemetry?hours=1").get_json()[
        "samples"
    ]
    rates = [s["network_rx_bytes_per_second"] for s in samples]

    assert rates == [None, None, 200.0, None, None, None]
    assert samples[2]["network_tx_bytes_per_second"] == 50.0
    assert "network_rx_bytes" not in samples[0]


def test_overview_returns_latest_values_per_enabled_client(telemetry_env):
    client = telemetry_env["app"].test_client()
    login_as(client)
    insert_counter_rows(
        telemetry_env, [(20, 1_000, 0), (10, 2_000, 1_000)]
    )

    response = client.get("/api/telemetry/overview")

    assert response.status_code == 200
    entries = {e["hostname"]: e for e in response.get_json()["clients"]}
    assert entries["pytest-client"]["latest"]["network_rx_bytes_per_second"] == 100.0
    assert entries["pytest-client"]["telemetry_stale"] is False
    assert entries["other-client"]["latest"] is None
    assert entries["other-client"]["telemetry_stale"] is True


def test_system_snapshot_is_validated_stored_and_exposed_with_rates(
    telemetry_env,
):
    client = telemetry_env["app"].test_client()
    login_as(client)

    first = post_sample(
        telemetry_env["app"].test_client(),
        system=system_snapshot(),
    )
    assert first.status_code == 200

    connection = telemetry_env["connection"]()
    connection.execute(
        """
        UPDATE client_system_status
        SET recorded_at = ?
        WHERE client_id = 1
        """,
        (
            (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(),
        ),
    )
    row = connection.execute(
        "SELECT payload_json FROM client_system_status WHERE client_id = 1"
    ).fetchone()
    prior = json.loads(row["payload_json"])
    prior["interfaces"][0]["rx_bytes"] = 1000
    prior["interfaces"][0]["tx_bytes"] = 500
    connection.execute(
        "UPDATE client_system_status SET payload_json = ? WHERE client_id = 1",
        (json.dumps(prior),),
    )
    connection.commit()
    connection.close()

    second_snapshot = system_snapshot()
    second_snapshot["interfaces"][0]["rx_bytes"] = 6000
    second_snapshot["interfaces"][0]["tx_bytes"] = 2500
    second = post_sample(
        telemetry_env["app"].test_client(),
        system=second_snapshot,
    )
    assert second.status_code == 200

    response = client.get("/api/telemetry/overview")
    assert response.status_code == 200
    entry = next(
        item for item in response.get_json()["clients"]
        if item["hostname"] == "pytest-client"
    )
    interface = entry["system"]["interfaces"][0]
    assert interface["name"] == "eth0"
    assert interface["rx_bytes_per_second"] > 0
    assert interface["tx_bytes_per_second"] > 0
    service = entry["system"]["services"]["items"][0]
    assert service["state"] == "active"
    assert service["restarts"] == 1
    assert service["runtime_seconds"] == 3600
    assert entry["system"]["containers"]["items"][0]["name"] == "lums"
    assert entry["system"]["security_events"]["ssh_failed_24h"] == 2
    assert entry["system_age_seconds"] is not None


@pytest.mark.parametrize(
    "system",
    [
        {"unexpected": "field"},
        system_snapshot(uptime_seconds=-1),
        system_snapshot(disk={"total_bytes": 10, "used_bytes": 12, "free_bytes": 1}),
        system_snapshot(interfaces=[{
            "name": "eth0", "state": "up", "rx_bytes": 1, "tx_bytes": 2,
            "rx_errors": 0, "tx_errors": 0, "rx_dropped": 0,
            "tx_dropped": 0, "extra": True,
        }]),
        system_snapshot(gateway="not-an-address"),
        system_snapshot(temperatures=[{"name": "CPU", "celsius": 999}]),
        system_snapshot(services={"available": True, "items": [{"name": "x", "state": "running"}]}),
    ],
)
def test_telemetry_rejects_invalid_system_snapshots(telemetry_env, system):
    response = post_sample(telemetry_env["app"].test_client(), system=system)
    assert response.status_code == 400
    connection = telemetry_env["connection"]()
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM client_telemetry"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM client_system_status"
        ).fetchone()[0] == 0
    finally:
        connection.close()


def test_telemetry_accepts_legacy_system_snapshot(telemetry_env):
    system = system_snapshot()
    system.pop("security_events")
    system["services"]["items"] = [
        {"name": "ssh.service", "state": "active"}
    ]
    system["containers"]["items"][0]["state"] = "running"

    response = post_sample(telemetry_env["app"].test_client(), system=system)

    assert response.status_code == 200


def test_overview_requires_clients_view_permission(telemetry_env):
    client = telemetry_env["app"].test_client()
    login_as(client, user_id=3, username="viewer")
    connection = telemetry_env["connection"]()
    connection.execute(
        "DELETE FROM user_permissions "
        "WHERE user_id = 3 AND permission = 'clients.view'"
    )
    connection.commit()
    connection.close()

    assert client.get("/api/telemetry/overview").status_code == 403