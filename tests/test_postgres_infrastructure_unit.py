from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from server import postgres_flask_security as pg_security
from server import postgres_infrastructure as infra
from server.postgres_app import create_postgres_app


BASE_URL = "https://localhost"
CSRF_TOKEN = "infrastructure-test-csrf"
ADMIN_PERMISSIONS = frozenset({
    "clients.view",
    "software.view",
    "users.manage",
    "infrastructure.manage",
})


class FakeCursor:
    def __init__(self, *, one=None, many=None):
        self._one = one
        self._many = list(many or [])

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._many)


class FakeConnection:
    def __init__(self, handler=None):
        self.handler = handler
        self.closed = False
        self.statements = []
        self.events = []

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.statements.append((normalized, params))

        if self.handler is not None:
            return self.handler(self, normalized, params)

        return FakeCursor()

    def close(self):
        self.closed = True


def _set_session(client, **values):
    with client.session_transaction(base_url=BASE_URL) as session:
        session.clear()
        session.update({
            "user_id": 7,
            "username": "administrator",
            "csrf_token": CSRF_TOKEN,
            **values,
        })


def _make_environment(monkeypatch, handler=None, permissions=None):
    connections = []

    def connection_factory():
        connection = FakeConnection(handler)
        connections.append(connection)
        return connection

    app = create_postgres_app({
        "SECRET_KEY": "postgres-infrastructure-unit-test",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
    })

    permissions = permissions or ADMIN_PERMISSIONS

    state = SimpleNamespace(
        user={
            "id": 7,
            "username": "administrator",
            "enabled": True,
            "role": "administrator",
        },
        permissions=permissions,
    )

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda connection, user_id: state,
    )

    @contextmanager
    def fake_transaction(connection):
        connection.events.append("transaction.begin")
        try:
            yield connection
        except BaseException:
            connection.events.append("transaction.rollback")
            raise
        else:
            connection.events.append("transaction.commit")

    def fake_audit(connection, **kwargs):
        assert "transaction.begin" in connection.events
        connection.events.append(("audit", kwargs))

    monkeypatch.setattr(infra, "transaction", fake_transaction)
    monkeypatch.setattr(infra, "audit_log", fake_audit)

    client = app.test_client()
    _set_session(client)

    return app, client, connections


def _write_headers():
    return {"X-CSRF-Token": CSRF_TOKEN}


def test_infrastructure_routes_are_registered():
    app = create_postgres_app({
        "SECRET_KEY": "postgres-infrastructure-routes",
        "TESTING": True,
    })

    expected = {
        "/infrastructure",
        "/api/infrastructure/topology",
        "/api/infrastructure/nodes",
        "/api/infrastructure/nodes/<int:node_id>",
        "/api/infrastructure/relations",
        "/api/infrastructure/relations/<int:relation_id>",
    }

    actual = {rule.rule for rule in app.url_map.iter_rules()}
    assert expected.issubset(actual)


def test_infrastructure_page_renders_postgres_template(monkeypatch):
    app, client, connections = _make_environment(monkeypatch)

    response = client.get(
        "/infrastructure",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert b'id="topology-map"' in response.data
    assert b'id="topology-node-form"' in response.data
    assert b"_postgres_sidebar" not in response.data
    assert len(connections) == 1
    assert connections[0].closed is True


def test_viewer_can_read_page_but_cannot_see_management_controls(
    monkeypatch,
):
    _, client, _ = _make_environment(
        monkeypatch,
        permissions=frozenset({"clients.view"}),
    )

    response = client.get(
        "/infrastructure",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert b'id="topology-map"' in response.data
    assert b'id="topology-node-form"' not in response.data
    assert b'id="topology-relation-form"' not in response.data


def test_topology_read_serializes_clients_nodes_and_relations(monkeypatch):
    now = datetime.now(timezone.utc)

    def handler(connection, sql, params):
        if sql.startswith("SET TRANSACTION"):
            return FakeCursor()

        if "FROM clients" in sql:
            return FakeCursor(many=[{
                "id": 41,
                "hostname": "debian-edge",
                "ip": "192.0.2.41",
                "os": "Debian GNU/Linux",
                "last_seen": now - timedelta(seconds=30),
                "enabled": True,
            }])

        if "FROM infrastructure_nodes" in sql:
            return FakeCursor(many=[{
                "id": 88,
                "name": "Core router",
                "node_type": "network_device",
                "hostname": "router-01",
                "ip_address": "192.0.2.1",
                "role": "Gateway",
                "location": "Server room",
                "notes": "",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }])

        if "FROM infrastructure_relations" in sql:
            return FakeCursor(many=[{
                "id": 12,
                "source_node_id": None,
                "source_client_id": 41,
                "target_node_id": 88,
                "target_client_id": None,
                "relation_type": "depends_on",
                "details": "Default gateway",
            }])

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        "/api/infrastructure/topology",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["nodes"][0]["id"] == "client:41"
    assert data["nodes"][0]["status"] == "online"
    assert data["nodes"][0]["editable"] is False

    assert data["nodes"][1]["id"] == "node:88"
    assert data["nodes"][1]["editable"] is True

    assert data["relations"] == [{
        "id": 12,
        "source": {"type": "client", "id": 41},
        "target": {"type": "node", "id": 88},
        "relation_type": "depends_on",
        "details": "Default gateway",
    }]

    route_connection = connections[-1]
    assert "transaction.begin" in route_connection.events
    assert "transaction.commit" in route_connection.events
    assert route_connection.closed is True


def test_create_infrastructure_node_is_atomic_with_audit(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith("INSERT INTO infrastructure_nodes"):
            return FakeCursor(one={"id": 91})

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        "/api/infrastructure/nodes",
        base_url=BASE_URL,
        json={
            "name": "Core router",
            "node_type": "network_device",
            "hostname": "router-01",
            "ip_address": "192.0.2.1",
            "role": "Gateway",
            "location": "Server room",
        },
        headers=_write_headers(),
    )

    assert response.status_code == 201
    assert response.get_json() == {"id": 91}

    connection = connections[-1]
    assert connection.events[0] == "transaction.begin"
    assert connection.events[1][0] == "audit"
    assert connection.events[-1] == "transaction.commit"
    assert connection.closed is True

    audit = connection.events[1][1]
    assert audit["action"] == "infrastructure.node.create"
    assert audit["target"] == "91"


def test_invalid_node_input_does_not_open_route_connection(monkeypatch):
    _, client, connections = _make_environment(monkeypatch)

    response = client.post(
        "/api/infrastructure/nodes",
        base_url=BASE_URL,
        json={
            "name": "Invalid router",
            "node_type": "network_device",
            "ip_address": "999.999.999.999",
        },
        headers=_write_headers(),
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_ip_address"}

    # Only the connection used by login_required was opened.
    assert len(connections) == 1
    assert connections[0].closed is True


def test_node_update_and_delete_use_postgres_transactions(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith("SELECT id FROM infrastructure_nodes"):
            return FakeCursor(one={"id": 88})

        if sql.startswith("UPDATE infrastructure_nodes"):
            return FakeCursor()

        if sql.startswith("DELETE FROM infrastructure_nodes"):
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = _make_environment(monkeypatch, handler)

    update = client.put(
        "/api/infrastructure/nodes/88",
        base_url=BASE_URL,
        json={
            "name": "Updated router",
            "node_type": "network_device",
            "hostname": "router-02",
        },
        headers=_write_headers(),
    )

    assert update.status_code == 200
    assert update.get_json() == {"status": "saved"}

    delete = client.delete(
        "/api/infrastructure/nodes/88",
        base_url=BASE_URL,
        json={},
        headers=_write_headers(),
    )

    assert delete.status_code == 200
    assert delete.get_json() == {"status": "saved"}

    # Authentication and route execution each own a separate connection.
    # Identify the route connections by their executed SQL, not list position.
    update_connection = next(
        connection
        for connection in connections
        if any(
            sql.startswith("UPDATE infrastructure_nodes")
            for sql, _ in connection.statements
        )
    )
    delete_connection = next(
        connection
        for connection in connections
        if any(
            sql.startswith("DELETE FROM infrastructure_nodes")
            for sql, _ in connection.statements
        )
    )

    assert update_connection.events[0] == "transaction.begin"
    assert update_connection.events[-1] == "transaction.commit"
    assert delete_connection.events[0] == "transaction.begin"
    assert delete_connection.events[-1] == "transaction.commit"

    assert any(
        event[1]["action"] == "infrastructure.node.update"
        for event in update_connection.events
        if isinstance(event, tuple) and event[0] == "audit"
    )
    assert any(
        event[1]["action"] == "infrastructure.node.delete"
        for event in delete_connection.events
        if isinstance(event, tuple) and event[0] == "audit"
    )

    assert update_connection.closed is True
    assert delete_connection.closed is True

def test_create_relation_checks_endpoints_and_writes_audit(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith("SELECT id FROM clients"):
            return FakeCursor(one={"id": 41})

        if sql.startswith("SELECT id FROM infrastructure_nodes"):
            return FakeCursor(one={"id": 88})

        if sql.startswith("INSERT INTO infrastructure_relations"):
            return FakeCursor(one={"id": 15})

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        "/api/infrastructure/relations",
        base_url=BASE_URL,
        json={
            "source_type": "client",
            "source_id": 41,
            "target_type": "node",
            "target_id": 88,
            "relation_type": "depends_on",
            "details": "Default gateway",
        },
        headers=_write_headers(),
    )

    assert response.status_code == 201
    assert response.get_json() == {"id": 15}

    connection = connections[-1]
    insert = next(
        (sql, params)
        for sql, params in connection.statements
        if sql.startswith("INSERT INTO infrastructure_relations")
    )

    assert insert[1][:6] == (
        None, 41, 88, None, "depends_on", "Default gateway"
    )
    assert connection.events[-1] == "transaction.commit"
    assert any(
        event[1]["action"] == "infrastructure.relation.create"
        for event in connection.events
        if isinstance(event, tuple) and event[0] == "audit"
    )


def test_relation_with_missing_endpoint_returns_404(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith("SELECT id FROM clients"):
            return FakeCursor(one={"id": 41})

        if sql.startswith("SELECT id FROM infrastructure_nodes"):
            return FakeCursor(one=None)

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        "/api/infrastructure/relations",
        base_url=BASE_URL,
        json={
            "source_type": "client",
            "source_id": 41,
            "target_type": "node",
            "target_id": 88,
            "relation_type": "depends_on",
        },
        headers=_write_headers(),
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "error": "topology_endpoint_not_found"
    }
    assert "transaction.commit" in connections[-1].events


def test_relation_delete_returns_404_when_missing(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith("DELETE FROM infrastructure_relations"):
            return FakeCursor(one=None)

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = _make_environment(monkeypatch, handler)

    response = client.delete(
        "/api/infrastructure/relations/123",
        base_url=BASE_URL,
        json={},
        headers=_write_headers(),
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "relation_not_found"}
    assert "transaction.commit" in connections[-1].events


def test_user_without_infrastructure_permission_is_rejected(monkeypatch):
    _, client, connections = _make_environment(
        monkeypatch,
        permissions=frozenset({"clients.view"}),
    )

    response = client.post(
        "/api/infrastructure/nodes",
        base_url=BASE_URL,
        json={
            "name": "Forbidden",
            "node_type": "server",
        },
        headers=_write_headers(),
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required"
    }

    # Authorization connection only; no write connection.
    assert len(connections) == 1
    assert connections[0].closed is True


def test_csrf_failure_prevents_infrastructure_write(monkeypatch):
    _, client, connections = _make_environment(monkeypatch)

    response = client.post(
        "/api/infrastructure/nodes",
        base_url=BASE_URL,
        json={
            "name": "Core server",
            "node_type": "server",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "csrf_validation_failed"
    }
    assert len(connections) == 1
    assert connections[0].closed is True


def test_relation_error_classification_uses_constraint_names():
    duplicate = SimpleNamespace(
        sqlstate="23505",
        diag=SimpleNamespace(
            constraint_name=(
                "uq_infrastructure_relations_node_client_type"
            )
        ),
    )

    unrelated_unique_error = SimpleNamespace(
        sqlstate="23505",
        diag=SimpleNamespace(constraint_name="uq_clients_hostname"),
    )

    missing_endpoint = SimpleNamespace(
        sqlstate="23503",
        diag=SimpleNamespace(
            constraint_name=(
                "fk_infrastructure_relations_target_node"
            )
        ),
    )

    assert infra.is_duplicate_relation_error(duplicate) is True
    assert infra.is_duplicate_relation_error(unrelated_unique_error) is False
    assert infra.is_relation_endpoint_error(missing_endpoint) is True


def test_topology_input_validation_and_health_classification():
    values, error = infra.topology_node_input({
        "name": "  Core router  ",
        "node_type": "network_device",
        "hostname": " router-01 ",
        "ip_address": "192.0.2.1",
    })

    assert error is None
    assert values["name"] == "Core router"
    assert values["hostname"] == "router-01"

    assert infra.topology_node_input({
        "name": "x",
        "node_type": "unknown",
    })[1] == "invalid_node_type"

    assert infra.topology_endpoint_input({
        "source_type": "node",
        "source_id": True,
    }, "source") is None

    now = datetime.now(timezone.utc)
    assert infra.classify_health_client(now - timedelta(seconds=30), now) == "online"
    assert infra.classify_health_client(now - timedelta(seconds=300), now) == "unknown"
    assert infra.classify_health_client(now - timedelta(seconds=900), now) == "offline"
    assert infra.classify_health_client("not-a-timestamp", now) == "unknown"


class FakeIntegrityViolation(Exception):
    def __init__(self, sqlstate, constraint_name):
        super().__init__(constraint_name)
        self.sqlstate = sqlstate
        self.diag = SimpleNamespace(
            constraint_name=constraint_name
        )


def _relation_payload():
    return {
        "source_type": "client",
        "source_id": 41,
        "target_type": "node",
        "target_id": 88,
        "relation_type": "depends_on",
        "details": "Default gateway",
    }


def _relation_endpoint_handler(connection, sql, params):
    if sql.startswith("SELECT id FROM clients"):
        return FakeCursor(one={"id": 41})

    if sql.startswith("SELECT id FROM infrastructure_nodes"):
        return FakeCursor(one={"id": 88})

    raise AssertionError(f"Unexpected SQL: {sql}")


def test_duplicate_relation_integrity_error_returns_409(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith("INSERT INTO infrastructure_relations"):
            raise FakeIntegrityViolation(
                "23505",
                "uq_infrastructure_relations_node_client_type",
            )
        return _relation_endpoint_handler(connection, sql, params)

    monkeypatch.setattr(
        infra,
        "DatabaseIntegrityError",
        FakeIntegrityViolation,
    )

    _, client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        "/api/infrastructure/relations",
        base_url=BASE_URL,
        json=_relation_payload(),
        headers=_write_headers(),
    )

    assert response.status_code == 409
    assert response.get_json() == {"error": "relation_exists"}

    connection = connections[-1]
    assert connection.events[0] == "transaction.begin"
    assert connection.events[-1] == "transaction.rollback"
    assert not any(
        isinstance(event, tuple) and event[0] == "audit"
        for event in connection.events
    )
    assert connection.closed is True


def test_relation_foreign_key_integrity_error_returns_404(monkeypatch):
    def handler(connection, sql, params):
        if sql.startswith("INSERT INTO infrastructure_relations"):
            raise FakeIntegrityViolation(
                "23503",
                "fk_infrastructure_relations_target_node",
            )
        return _relation_endpoint_handler(connection, sql, params)

    monkeypatch.setattr(
        infra,
        "DatabaseIntegrityError",
        FakeIntegrityViolation,
    )

    _, client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        "/api/infrastructure/relations",
        base_url=BASE_URL,
        json=_relation_payload(),
        headers=_write_headers(),
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "error": "topology_endpoint_not_found"
    }

    connection = connections[-1]
    assert connection.events[-1] == "transaction.rollback"
    assert connection.closed is True


def test_unrelated_unique_violation_is_not_mapped_to_relation_duplicate(
    monkeypatch,
):
    def handler(connection, sql, params):
        if sql.startswith("INSERT INTO infrastructure_relations"):
            raise FakeIntegrityViolation(
                "23505",
                "uq_clients_hostname",
            )
        return _relation_endpoint_handler(connection, sql, params)

    monkeypatch.setattr(
        infra,
        "DatabaseIntegrityError",
        FakeIntegrityViolation,
    )

    _, client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        "/api/infrastructure/relations",
        base_url=BASE_URL,
        json=_relation_payload(),
        headers=_write_headers(),
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "error": "topology_save_failed"
    }
    assert response.get_json()["error"] != "relation_exists"
    assert connections[-1].events[-1] == "transaction.rollback"
