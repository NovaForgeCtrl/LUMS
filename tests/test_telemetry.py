import sqlite3
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
            FOREIGN KEY (client_id) REFERENCES clients(id)
                ON DELETE CASCADE
        );

        CREATE INDEX idx_client_telemetry_client_time
        ON client_telemetry(client_id, recorded_at);
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
