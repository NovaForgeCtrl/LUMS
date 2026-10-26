import sqlite3
from datetime import datetime, timezone

from tests.test_rbac import (
    configure_test_database,
    create_rbac_database,
    login_as,
)


def _configure_topology_database(monkeypatch, app_module, db_path):
    create_rbac_database(db_path)
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY,
            hostname TEXT NOT NULL,
            ip TEXT,
            os TEXT,
            last_seen TEXT,
            enabled INTEGER NOT NULL DEFAULT 1
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
        """
    )
    connection.execute(
        """
        INSERT INTO clients (id, hostname, ip, os, last_seen, enabled)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (
            41,
            "debian-edge",
            "192.0.2.41",
            "Debian GNU/Linux",
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    from server.security_migration import migrate_infrastructure_topology

    migrate_infrastructure_topology(connection)
    connection.commit()
    connection.close()
    configure_test_database(monkeypatch, app_module, str(db_path))


def _login_with_csrf(client, user_id, username):
    login_as(client, user_id, username)
    with client.session_transaction() as session:
        session["csrf_token"] = "topology-test-csrf"


def test_topology_page_requires_client_view_permission():
    from server import app as app_module

    with app_module.app.test_client() as client:
        response = client.get("/infrastructure")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_topology_page_follows_theme_and_hides_controls_for_viewers(
    monkeypatch, tmp_path
):
    from server import app as app_module

    db_path = tmp_path / "topology-page.db"
    _configure_topology_database(monkeypatch, app_module, db_path)
    app_module.app.config.update(TESTING=True)

    with app_module.app.test_client() as client:
        _login_with_csrf(client, 3, "viewer")
        response = client.get("/infrastructure")

    assert response.status_code == 200
    assert b'href="/infrastructure"' in response.data
    assert b'id="lums-sidebar-toggle"' in response.data
    assert b'id="topology-map"' in response.data
    assert b'id="topology-node-form"' not in response.data
    assert b'theme.js' in response.data


def test_topology_imports_clients_and_admin_can_manage_nodes_and_relations(
    monkeypatch, tmp_path
):
    from server import app as app_module

    db_path = tmp_path / "topology-api.db"
    _configure_topology_database(monkeypatch, app_module, db_path)
    app_module.app.config.update(TESTING=True)

    with app_module.app.test_client() as client:
        _login_with_csrf(client, 1, "administrator")
        initial = client.get("/api/infrastructure/topology")
        assert initial.status_code == 200
        assert initial.get_json()["nodes"] == [
            {
                "id": "client:41",
                "entity_type": "client",
                "entity_id": 41,
                "name": "debian-edge",
                "node_type": "client",
                "hostname": "debian-edge",
                "ip_address": "192.0.2.41",
                "role": "Debian GNU/Linux",
                "location": "",
                "status": "online",
                "editable": False,
            }
        ]

        invalid = client.post(
            "/api/infrastructure/nodes",
            json={
                "name": "Core router",
                "node_type": "network_device",
                "ip_address": "999.999.999.999",
            },
            headers={"X-CSRF-Token": "topology-test-csrf"},
        )
        assert invalid.status_code == 400
        assert invalid.get_json()["error"] == "invalid_ip_address"

        created = client.post(
            "/api/infrastructure/nodes",
            json={
                "name": "Core router",
                "node_type": "network_device",
                "hostname": "router-01",
                "ip_address": "192.0.2.1",
                "role": "Gateway",
                "location": "Server room",
            },
            headers={"X-CSRF-Token": "topology-test-csrf"},
        )
        assert created.status_code == 201
        node_id = created.get_json()["id"]

        relation = {
            "source_type": "client",
            "source_id": 41,
            "target_type": "node",
            "target_id": node_id,
            "relation_type": "depends_on",
            "details": "Default gateway",
        }
        linked = client.post(
            "/api/infrastructure/relations",
            json=relation,
            headers={"X-CSRF-Token": "topology-test-csrf"},
        )
        assert linked.status_code == 201
        duplicate = client.post(
            "/api/infrastructure/relations",
            json=relation,
            headers={"X-CSRF-Token": "topology-test-csrf"},
        )
        assert duplicate.status_code == 409

        topology = client.get("/api/infrastructure/topology").get_json()
        assert len(topology["nodes"]) == 2
        assert topology["relations"] == [
            {
                "id": linked.get_json()["id"],
                "source": {"type": "client", "id": 41},
                "target": {"type": "node", "id": node_id},
                "relation_type": "depends_on",
                "details": "Default gateway",
            }
        ]

        deleted = client.delete(
            f"/api/infrastructure/nodes/{node_id}",
            headers={"X-CSRF-Token": "topology-test-csrf"},
            json={},
        )
        assert deleted.status_code == 200
        after_delete = client.get("/api/infrastructure/topology").get_json()
        assert after_delete["nodes"] == [topology["nodes"][0]]
        assert after_delete["relations"] == []


def test_only_administrators_can_change_topology(monkeypatch, tmp_path):
    from server import app as app_module

    db_path = tmp_path / "topology-rbac.db"
    _configure_topology_database(monkeypatch, app_module, db_path)
    app_module.app.config.update(TESTING=True)

    with app_module.app.test_client() as client:
        _login_with_csrf(client, 2, "operator")
        response = client.post(
            "/api/infrastructure/nodes",
            json={"name": "Forbidden", "node_type": "server"},
            headers={"X-CSRF-Token": "topology-test-csrf"},
        )

    assert response.status_code == 403
    assert response.get_json() == {"error": "authorization_required"}
