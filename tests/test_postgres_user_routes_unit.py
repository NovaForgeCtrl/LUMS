"""Database-free unit tests for PostgreSQL user-management routes."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from psycopg import Error as PsycopgError

from server import postgres_flask_security as pg_security
from server import postgres_user_routes as users_module
from server.postgres_app import create_postgres_app


BASE_URL = "https://localhost"
CSRF_TOKEN = "postgres-user-route-test-csrf"
ACTOR_ID = 7

ADMIN_PERMISSIONS = frozenset({
    "clients.view",
    "clients.manage",
    "users.manage",
    "permissions.manage",
})


class FakeCursor:
    def __init__(self, one=None, many=None, rowcount=1):
        self.one = one
        self.many = list(many or [])
        self.rowcount = rowcount

    def fetchone(self):
        return self.one

    def fetchall(self):
        return list(self.many)


class FakeConnection:
    def __init__(self, handler):
        self.handler = handler
        self.closed = False
        self.statements = []
        self.events = []

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.statements.append((normalized, params))
        self.events.append(("sql", normalized, params))
        return self.handler(self, normalized, params)

    def close(self):
        self.closed = True


def _make_environment(
    monkeypatch,
    handler,
    *,
    audit_handler=None,
    permissions=ADMIN_PERMISSIONS,
    actor_id=ACTOR_ID,
    effective_permissions=None,
    actor_permissions=ADMIN_PERMISSIONS,
    actor_enabled=True,
    actor_exists=True,
):
    connections = []

    def connection_factory():
        def route_handler(connection, statement, params):
            if statement.startswith(
                "SELECT id, enabled FROM users WHERE id = %s FOR UPDATE"
            ):
                if not actor_exists:
                    return FakeCursor(one=None)
                return FakeCursor(one={
                    "id": actor_id,
                    "enabled": actor_enabled,
                })
            return handler(connection, statement, params)

        connection = FakeConnection(route_handler)
        connections.append(connection)
        return connection

    app = create_postgres_app({
        "SECRET_KEY": "postgres-user-route-unit-secret",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
    })

    state = SimpleNamespace(
        user={
            "id": actor_id,
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

    def fake_lock(connection):
        assert "transaction.begin" in connection.events
        connection.events.append("rbac.lock")

    def fake_audit(connection, **kwargs):
        assert "transaction.begin" in connection.events
        if audit_handler is not None:
            audit_handler(connection, **kwargs)
            return
        connection.events.append(("audit", kwargs))

    monkeypatch.setattr(users_module, "transaction", fake_transaction)
    monkeypatch.setattr(users_module, "acquire_rbac_write_lock", fake_lock)
    monkeypatch.setattr(users_module, "audit_log", fake_audit)
    monkeypatch.setattr(
        users_module,
        "store_user_permissions",
        lambda *args, **kwargs: None,
    )

    def resolve_test_permissions(connection, user_id):
        if user_id == actor_id:
            return set(actor_permissions)
        return set(effective_permissions or ())

    monkeypatch.setattr(
        users_module,
        "resolve_user_permissions",
        resolve_test_permissions,
    )

    client = app.test_client()
    with client.session_transaction(base_url=BASE_URL) as session:
        session.clear()
        session.update({
            "user_id": actor_id,
            "username": "administrator",
            "csrf_token": CSRF_TOKEN,
        })

    return client, connections


def _write_headers():
    return {"X-CSRF-Token": CSRF_TOKEN}


def _route_connection(connections, prefix):
    return next(
        connection
        for connection in connections
        if any(
            statement.startswith(prefix)
            for statement, _ in connection.statements
        )
    )


def _user_row(
    user_id=23,
    username="operator-one",
    role="operator",
    enabled=True,
):
    return {
        "id": user_id,
        "username": username,
        "role": role,
        "enabled": enabled,
    }


def test_create_user_commits_permissions_and_audit(monkeypatch):
    created = _user_row()

    def handler(connection, statement, params):
        if statement.startswith("INSERT INTO users"):
            assert "rbac.lock" in connection.events
            assert params[0] == "operator-one"
            return FakeCursor(one=created)
        return FakeCursor()

    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        "/api/users",
        json={
            "username": " operator-one ",
            "password": "a-long-enough-password",
            "role": "operator",
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["status"] == "created"
    assert payload["user"]["id"] == created["id"]
    assert payload["user"]["permissions"] == sorted(
        users_module.ROLE_DEFAULT_PERMISSIONS["operator"]
    )

    route = _route_connection(connections, "INSERT INTO users")
    assert route.events[0] == "transaction.begin"
    assert route.events[1] == "rbac.lock"
    assert route.events[-1] == "transaction.commit"
    assert any(
        isinstance(event, tuple)
        and event[0] == "audit"
        and event[1]["action"] == "user.create"
        for event in route.events
    )
    assert all(connection.closed for connection in connections)


@pytest.mark.parametrize(
    ("body", "expected_error"),
    [
        (
            {"username": "", "password": "long-enough-password", "role": "operator"},
            "username_required",
        ),
        (
            {"username": "operator", "password": "short", "role": "operator"},
            "password_too_short",
        ),
        (
            {"username": "operator", "password": "long-enough-password", "role": "invalid"},
            "invalid_user_role",
        ),
    ],
)
def test_create_user_rejects_invalid_input_before_database(
    monkeypatch,
    body,
    expected_error,
):
    def handler(connection, statement, params):
        return FakeCursor()

    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        "/api/users",
        json=body,
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == expected_error
    assert not any(connection.statements for connection in connections)
    assert all(connection.closed for connection in connections)


def test_create_user_requires_permission_delegation(monkeypatch):
    def handler(connection, statement, params):
        return FakeCursor()

    permissions = ADMIN_PERMISSIONS - {"permissions.manage"}
    client, connections = _make_environment(
        monkeypatch,
        handler,
        permissions=permissions,
    )

    response = client.post(
        "/api/users",
        json={
            "username": "operator-one",
            "password": "a-long-enough-password",
            "role": "operator",
            "permissions": ["clients.view"],
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "permission_delegation_required"
    assert not any(connection.statements for connection in connections)
    assert all(connection.closed for connection in connections)


def test_create_user_rolls_back_when_audit_fails(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith("INSERT INTO users"):
            return FakeCursor(one=_user_row())
        return FakeCursor()

    def audit_failure(connection, **kwargs):
        raise PsycopgError("simulated audit failure")

    client, connections = _make_environment(
        monkeypatch,
        handler,
        audit_handler=audit_failure,
    )

    response = client.post(
        "/api/users",
        json={
            "username": "operator-one",
            "password": "a-long-enough-password",
            "role": "operator",
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 500
    assert response.get_json()["error"] == "database_unavailable"

    route = _route_connection(connections, "INSERT INTO users")
    assert "transaction.rollback" in route.events
    assert "transaction.commit" not in route.events
    assert all(connection.closed for connection in connections)


def test_update_user_permissions_commits(monkeypatch):
    target = _user_row()

    def handler(connection, statement, params):
        if statement.startswith("SELECT id, username, role, enabled FROM users"):
            return FakeCursor(one=target)
        return FakeCursor()

    client, connections = _make_environment(
        monkeypatch,
        handler,
        effective_permissions=set(),
    )

    response = client.put(
        "/api/users/23/permissions",
        json={"role": "operator", "permissions": []},
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "updated"

    route = _route_connection(
        connections,
        "SELECT id, username, role, enabled FROM users",
    )
    assert route.events[0] == "transaction.begin"
    assert route.events[1] == "rbac.lock"
    assert any(
        statement.startswith("UPDATE users SET role")
        for statement, _ in route.statements
    )
    assert route.events[-1] == "transaction.commit"
    assert all(connection.closed for connection in connections)


def test_update_user_permissions_protects_last_administrator(monkeypatch):
    target = _user_row()
    effective = {"users.manage"}

    def handler(connection, statement, params):
        if statement.startswith("SELECT id, username, role, enabled FROM users"):
            return FakeCursor(one=target)
        if statement.startswith("SELECT id FROM users WHERE enabled IS TRUE"):
            return FakeCursor(many=[{"id": 23}])
        return FakeCursor()

    client, connections = _make_environment(
        monkeypatch,
        handler,
        effective_permissions=effective,
    )

    response = client.put(
        "/api/users/23/permissions",
        json={"role": "operator", "permissions": []},
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "last_enabled_administrator"

    route = _route_connection(
        connections,
        "SELECT id, username, role, enabled FROM users",
    )
    assert "transaction.rollback" in route.events
    assert not any(
        statement.startswith("UPDATE users SET role")
        for statement, _ in route.statements
    )
    assert all(connection.closed for connection in connections)


def test_update_user_permissions_returns_not_found(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith("SELECT id, username, role, enabled FROM users"):
            return FakeCursor(one=None)
        return FakeCursor()

    client, connections = _make_environment(
        monkeypatch,
        handler,
        effective_permissions=set(),
    )

    response = client.put(
        "/api/users/999/permissions",
        json={"role": "operator", "permissions": []},
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "user_not_found"
    route = _route_connection(
        connections,
        "SELECT id, username, role, enabled FROM users",
    )
    assert "transaction.rollback" in route.events
    assert all(connection.closed for connection in connections)


def test_delete_user_rejects_self_before_database(monkeypatch):
    def handler(connection, statement, params):
        return FakeCursor()

    client, connections = _make_environment(
        monkeypatch,
        handler,
        actor_id=23,
    )

    response = client.delete(
        "/api/users/23",
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "cannot_delete_self"
    assert not any(connection.statements for connection in connections)
    assert all(connection.closed for connection in connections)


def test_delete_user_protects_last_administrator(monkeypatch):
    target = _user_row()
    effective = {"users.manage"}

    def handler(connection, statement, params):
        if statement.startswith("SELECT id, username, role, enabled FROM users"):
            return FakeCursor(one=target)
        if statement.startswith("SELECT id FROM users WHERE enabled IS TRUE"):
            return FakeCursor(many=[{"id": 23}])
        return FakeCursor()

    client, connections = _make_environment(
        monkeypatch,
        handler,
        effective_permissions=effective,
    )

    response = client.delete(
        "/api/users/23",
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "last_enabled_administrator"

    route = _route_connection(
        connections,
        "SELECT id, username, role, enabled FROM users",
    )
    assert "transaction.rollback" in route.events
    assert not any(
        statement.startswith("DELETE FROM users")
        for statement, _ in route.statements
    )
    assert all(connection.closed for connection in connections)


def test_delete_user_commits_and_audits(monkeypatch):
    target = _user_row()

    def handler(connection, statement, params):
        if statement.startswith("SELECT id, username, role, enabled FROM users"):
            return FakeCursor(one=target)
        return FakeCursor()

    client, connections = _make_environment(
        monkeypatch,
        handler,
        effective_permissions=set(),
    )

    response = client.delete(
        "/api/users/23",
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == {"status": "deleted", "user_id": 23}

    route = _route_connection(
        connections,
        "SELECT id, username, role, enabled FROM users",
    )
    assert route.events[0] == "transaction.begin"
    assert route.events[1] == "rbac.lock"
    assert any(
        statement.startswith("DELETE FROM users")
        for statement, _ in route.statements
    )
    assert any(
        isinstance(event, tuple)
        and event[0] == "audit"
        and event[1]["action"] == "user.delete"
        for event in route.events
    )
    assert route.events[-1] == "transaction.commit"
    assert all(connection.closed for connection in connections)

def test_update_user_permissions_protects_last_permission_manager(monkeypatch):
    target = _user_row()
    manager_permissions = {
        "permissions.manage",
        "users.manage",
        "clients.view",
    }
    permission_map = {
        23: manager_permissions,
        24: {"users.manage", "clients.view"},
    }

    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, username, role, enabled FROM users"
        ):
            return FakeCursor(one=target)
        if statement.startswith(
            "SELECT id FROM users WHERE enabled IS TRUE"
        ):
            return FakeCursor(many=[{"id": 23}, {"id": 24}])
        return FakeCursor()

    client, connections = _make_environment(monkeypatch, handler)

    monkeypatch.setattr(
        users_module,
        "resolve_user_permissions",
        lambda connection, user_id: set(permission_map.get(user_id, ADMIN_PERMISSIONS)),
    )

    response = client.put(
        "/api/users/23/permissions",
        json={
            "role": "operator",
            "permissions": ["users.manage", "clients.view"],
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "last_enabled_permission_manager"

    route = _route_connection(
        connections,
        "SELECT id, username, role, enabled FROM users",
    )
    assert "transaction.rollback" in route.events
    assert "transaction.commit" not in route.events
    assert not any(
        statement.startswith("UPDATE users SET role")
        for statement, _ in route.statements
    )
    assert all(connection.closed for connection in connections)


def test_delete_user_protects_last_permission_manager(monkeypatch):
    target = _user_row()
    manager_permissions = {
        "permissions.manage",
        "users.manage",
        "clients.view",
    }
    permission_map = {
        23: manager_permissions,
        24: {"users.manage", "clients.view"},
    }

    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, username, role, enabled FROM users"
        ):
            return FakeCursor(one=target)
        if statement.startswith(
            "SELECT id FROM users WHERE enabled IS TRUE"
        ):
            return FakeCursor(many=[{"id": 23}, {"id": 24}])
        return FakeCursor()

    client, connections = _make_environment(monkeypatch, handler)

    monkeypatch.setattr(
        users_module,
        "resolve_user_permissions",
        lambda connection, user_id: set(permission_map.get(user_id, ADMIN_PERMISSIONS)),
    )

    response = client.delete(
        "/api/users/23",
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "last_enabled_permission_manager"

    route = _route_connection(
        connections,
        "SELECT id, username, role, enabled FROM users",
    )
    assert "transaction.rollback" in route.events
    assert "transaction.commit" not in route.events
    assert not any(
        statement.startswith("DELETE FROM users")
        for statement, _ in route.statements
    )
    assert all(connection.closed for connection in connections)

def test_create_user_revalidates_users_manage_inside_transaction(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith("INSERT INTO users"):
            raise AssertionError("INSERT must not run after permission revocation")
        return FakeCursor()

    client, connections = _make_environment(
        monkeypatch,
        handler,
        actor_permissions={"permissions.manage"},
    )

    response = client.post(
        "/api/users",
        json={
            "username": "operator-two",
            "password": "a-long-enough-password",
            "role": "operator",
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "authorization_required"

    route = _route_connection(
        connections,
        "SELECT id, enabled FROM users WHERE id = %s FOR UPDATE",
    )
    assert route.events[0] == "transaction.begin"
    assert route.events[1] == "rbac.lock"
    assert route.events[2][0] == "sql"
    assert route.events[2][1].startswith(
        "SELECT id, enabled FROM users WHERE id = %s FOR UPDATE"
    )
    assert "transaction.rollback" in route.events
    assert "transaction.commit" not in route.events
    assert not any(
        statement.startswith("INSERT INTO users")
        for statement, _ in route.statements
    )
    assert all(connection.closed for connection in connections)

def test_update_user_permissions_revalidates_actor_inside_transaction(monkeypatch):
    target = _user_row()

    def handler(connection, statement, params):
        if statement.startswith("UPDATE users SET role"):
            raise AssertionError("UPDATE must not run after permission revocation")
        if statement.startswith("SELECT id, username, role, enabled FROM users"):
            return FakeCursor(one=target)
        return FakeCursor()

    client, connections = _make_environment(
        monkeypatch,
        handler,
        actor_permissions={"users.manage"},
    )

    response = client.put(
        "/api/users/23/permissions",
        json={"role": "operator", "permissions": []},
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "authorization_required"

    route = _route_connection(
        connections,
        "SELECT id, enabled FROM users WHERE id = %s FOR UPDATE",
    )
    assert route.events[0] == "transaction.begin"
    assert route.events[1] == "rbac.lock"
    assert "transaction.rollback" in route.events
    assert "transaction.commit" not in route.events
    assert not any(
        statement.startswith("UPDATE users SET role")
        for statement, _ in route.statements
    )
    assert all(connection.closed for connection in connections)

def test_delete_user_revalidates_actor_inside_transaction(monkeypatch):
    target = _user_row()

    def handler(connection, statement, params):
        if statement.startswith("DELETE FROM users"):
            raise AssertionError("DELETE must not run after permission revocation")
        if statement.startswith("SELECT id, username, role, enabled FROM users"):
            return FakeCursor(one=target)
        return FakeCursor()

    client, connections = _make_environment(
        monkeypatch,
        handler,
        actor_permissions=set(),
    )

    response = client.delete(
        "/api/users/23",
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "authorization_required"

    route = _route_connection(
        connections,
        "SELECT id, enabled FROM users WHERE id = %s FOR UPDATE",
    )
    assert route.events[0] == "transaction.begin"
    assert route.events[1] == "rbac.lock"
    assert "transaction.rollback" in route.events
    assert "transaction.commit" not in route.events
    assert not any(
        statement.startswith("DELETE FROM users")
        for statement, _ in route.statements
    )
    assert all(connection.closed for connection in connections)

def test_delete_user_rejects_disabled_actor_inside_transaction(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith("DELETE FROM users"):
            raise AssertionError("DELETE must not run for a disabled actor")
        return FakeCursor()

    client, connections = _make_environment(
        monkeypatch,
        handler,
        actor_enabled=False,
    )

    response = client.delete(
        "/api/users/23",
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"

    route = _route_connection(
        connections,
        "SELECT id, enabled FROM users WHERE id = %s FOR UPDATE",
    )
    assert route.events[0] == "transaction.begin"
    assert route.events[1] == "rbac.lock"
    assert "transaction.rollback" in route.events
    assert "transaction.commit" not in route.events
    assert not any(
        statement.startswith("DELETE FROM users")
        for statement, _ in route.statements
    )
    assert all(connection.closed for connection in connections)

def test_delete_user_rejects_missing_actor_inside_transaction(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith("DELETE FROM users"):
            raise AssertionError("DELETE must not run for a missing actor")
        return FakeCursor()

    client, connections = _make_environment(
        monkeypatch,
        handler,
        actor_exists=False,
    )

    response = client.delete(
        "/api/users/23",
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"

    route = _route_connection(
        connections,
        "SELECT id, enabled FROM users WHERE id = %s FOR UPDATE",
    )
    assert route.events[0] == "transaction.begin"
    assert route.events[1] == "rbac.lock"
    assert "transaction.rollback" in route.events
    assert "transaction.commit" not in route.events
    assert not any(
        statement.startswith("DELETE FROM users")
        for statement, _ in route.statements
    )
    assert all(connection.closed for connection in connections)

