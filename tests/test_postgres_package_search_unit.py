"""Database-free tests for PostgreSQL package-search routes."""

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from psycopg.types.json import Jsonb

from server import postgres_flask_security as pg_security
from server import postgres_package_search as package_search
from server.postgres_app import create_postgres_app
from server.security import hash_client_token


BASE_URL = "https://localhost"
TOKEN = "postgres-package-search-test-token"
TOKEN_HASH = hash_client_token(TOKEN)
CSRF_TOKEN = "postgres-package-search-test-csrf"


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

        if self.handler is not None:
            result = self.handler(self, sql, params)
            if result is not None:
                return result

        return FakeCursor()

    def close(self):
        self.closed = True


def client_auth_handler(valid=True):
    def handler(connection, sql, params):
        if "WHERE client_token_hash = %s" in sql:
            if not valid:
                return FakeCursor()

            return FakeCursor(one={
                "id": 1,
                "hostname": "package-search-agent-01",
                "enabled": True,
                "client_token_hash": TOKEN_HASH,
                "token_revoked_at": None,
            })

        return FakeCursor()

    return handler


def locked_client(**overrides):
    row = {
        "id": 1,
        "enabled": True,
        "client_token_hash": TOKEN_HASH,
        "token_revoked_at": None,
    }
    row.update(overrides)
    return row


def make_environment(
    monkeypatch,
    handlers,
    *,
    role="administrator",
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
        "SECRET_KEY": "postgres-package-search-unit-test",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": factory,
    })

    state = SimpleNamespace(
        user={
            "id": 7,
            "username": "package-search-user",
            "enabled": True,
            "role": role,
        },
        permissions=(
            permissions
            if permissions is not None
            else frozenset({"packages.search", "clients.view"})
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
        package_search,
        "transaction",
        fake_transaction,
    )
    monkeypatch.setattr(
        package_search,
        "audit_log",
        fake_audit,
    )

    return app, app.test_client(), connections


def set_session(client):
    with client.session_transaction(base_url=BASE_URL) as session:
        session.clear()
        session.update({
            "user_id": 7,
            "username": "package-search-user",
            "csrf_token": CSRF_TOKEN,
        })


def user_headers():
    return {"X-CSRF-Token": CSRF_TOKEN}


def agent_headers():
    return {"Authorization": f"Bearer {TOKEN}"}


def test_all_package_search_routes_are_registered():
    app = create_postgres_app({
        "SECRET_KEY": "postgres-package-search-routes",
        "TESTING": True,
    })

    expected = {
        "/api/clients/<int:client_id>/package-search",
        "/api/package-search/<int:search_id>/result",
        "/api/clients/<int:client_id>/package-search/pending",
        "/api/clients/<int:client_id>/package-search/<int:search_id>",
    }

    actual = [
        rule.rule
        for rule in app.url_map.iter_rules()
    ]

    for route in expected:
        assert actual.count(route) == 1, (
            f"Expected exactly one registration for {route!r}, "
            f"found {actual.count(route)}"
        )


def test_create_package_search_persists_and_audits_atomically(monkeypatch):
    def create_handler(connection, sql, params):
        if "FROM clients" in sql:
            assert "FOR SHARE" in sql
            return FakeCursor(one={
                "id": 41,
                "enabled": True,
            })

        if sql.startswith("INSERT INTO package_search_requests"):
            assert "'pending'" in sql
            return FakeCursor(one={"id": 91})

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, create_handler],
    )
    set_session(client)

    response = client.post(
        "/api/clients/41/package-search",
        json={"query": "  nginx  "},
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 202
    assert response.get_json() == {
        "status": "pending",
        "search_id": 91,
        "client_id": 41,
        "query": "nginx",
    }

    assert len(connections) == 2
    assert all(connection.closed for connection in connections)

    connection = connections[1]
    assert connection.events[0] == "begin"
    assert connection.events[-1] == "commit"

    audit_event = next(
        event for event in connection.events
        if isinstance(event, tuple) and event[0] == "audit"
    )
    assert audit_event[1]["action"] == "package_search.create"
    assert audit_event[1]["actor_id"] == 7
    assert audit_event[1]["target"] == "client:41"
    assert "search_id=91" in audit_event[1]["details"]


def test_create_rejects_viewer_even_with_package_permission(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [],
        role="viewer",
        permissions=frozenset({"packages.search"}),
    )
    set_session(client)

    response = client.post(
        "/api/clients/41/package-search",
        json={"query": "nginx"},
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert len(connections) == 1
    assert connections[0].closed


def test_create_requires_packages_search_permission(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [],
        role="administrator",
        permissions=frozenset({"clients.view"}),
    )
    set_session(client)

    response = client.post(
        "/api/clients/41/package-search",
        json={"query": "nginx"},
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert len(connections) == 1


def test_create_requires_csrf(monkeypatch):
    _, client, connections = make_environment(monkeypatch, [])
    set_session(client)

    response = client.post(
        "/api/clients/41/package-search",
        json={"query": "nginx"},
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert len(connections) == 1


def test_create_rejects_invalid_query_without_write_connection(monkeypatch):
    _, client, connections = make_environment(monkeypatch, [])
    set_session(client)

    response = client.post(
        "/api/clients/41/package-search",
        json={"query": " " + "x" * 129},
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_package_search_query"
    }
    assert len(connections) == 1


def test_create_rejects_unknown_client(monkeypatch):
    def handler(connection, sql, params):
        if "FROM clients" in sql:
            return FakeCursor()
        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.post(
        "/api/clients/999/package-search",
        json={"query": "nginx"},
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "client_not_found"}
    assert not any(
        sql.startswith("INSERT INTO package_search_requests")
        for sql, _ in connections[1].statements
    )


def test_create_rejects_disabled_client(monkeypatch):
    def handler(connection, sql, params):
        if "FROM clients" in sql:
            return FakeCursor(one={
                "id": 41,
                "enabled": False,
            })
        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, handler],
    )
    set_session(client)

    response = client.post(
        "/api/clients/41/package-search",
        json={"query": "nginx"},
        headers=user_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 409
    assert response.get_json() == {"error": "client_disabled"}
    assert not any(
        sql.startswith("INSERT INTO package_search_requests")
        for sql, _ in connections[1].statements
    )


def test_pending_search_requires_client_token(monkeypatch):
    _, client, connections = make_environment(monkeypatch, [])

    response = client.get(
        "/api/clients/1/package-search/pending",
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == (
        "client_authentication_required"
    )
    assert connections == []


def test_pending_search_rejects_invalid_client_token(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler(valid=False)],
    )

    response = client.get(
        "/api/clients/1/package-search/pending",
        headers={"Authorization": "Bearer invalid-token"},
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert len(connections) == 1
    assert connections[0].closed


def test_pending_search_rejects_wrong_client(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler()],
    )

    response = client.get(
        "/api/clients/2/package-search/pending",
        headers=agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "client_access_denied"
    }
    assert len(connections) == 1


def test_pending_search_claim_uses_skip_locked_and_revalidates_token(
    monkeypatch,
):
    def claim_handler(connection, sql, params):
        if "FROM clients" in sql and "FOR UPDATE" in sql:
            return FakeCursor(one=locked_client())

        if "FROM package_search_requests" in sql:
            assert "FOR UPDATE SKIP LOCKED" in sql
            assert "ORDER BY id ASC" in sql
            return FakeCursor(one={
                "id": 72,
                "query": "nginx",
                "created_at": datetime(
                    2026, 11, 2, 12, 0, tzinfo=timezone.utc
                ),
            })

        if sql.startswith("UPDATE package_search_requests"):
            assert "status = 'pending'" in sql
            return FakeCursor(one={"id": 72})

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler(), claim_handler],
    )

    response = client.get(
        "/api/clients/1/package-search/pending",
        headers=agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "running"
    assert data["search_id"] == 72
    assert data["client_id"] == 1
    assert data["query"] == "nginx"
    assert data["created_at"] == "2026-11-02T12:00:00+00:00"
    assert data["started_at"]

    connection = connections[1]
    assert connection.events == ["begin", "commit"]
    assert all(item.closed for item in connections)


def test_pending_search_rejects_revoked_token_under_lock(monkeypatch):
    def claim_handler(connection, sql, params):
        if "FROM clients" in sql and "FOR UPDATE" in sql:
            return FakeCursor(one=locked_client(
                token_revoked_at=datetime.now(timezone.utc)
            ))
        raise AssertionError(
            f"Queue query must not run for revoked token: {sql}"
        )

    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler(), claim_handler],
    )

    response = client.get(
        "/api/clients/1/package-search/pending",
        headers=agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == (
        "client_authentication_required"
    )
    assert connections[1].events == ["begin", "commit"]


def test_pending_search_returns_204_when_queue_is_empty(monkeypatch):
    def claim_handler(connection, sql, params):
        if "FROM clients" in sql and "FOR UPDATE" in sql:
            return FakeCursor(one=locked_client())

        if "FROM package_search_requests" in sql:
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler(), claim_handler],
    )

    response = client.get(
        "/api/clients/1/package-search/pending",
        headers=agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 204
    assert response.data == b""
    assert connections[1].events == ["begin", "commit"]


def test_result_completed_stores_jsonb_and_revalidates_client(monkeypatch):
    results = [
        {
            "package": "nginx",
            "version": "1.30.5-1",
            "description": "HTTP server",
        },
        {
            "package": "nginx-mod-stream",
            "version": "1.30.5-1",
            "description": "Stream module",
        },
    ]

    def result_handler(connection, sql, params):
        if "FROM clients" in sql and "FOR UPDATE" in sql:
            return FakeCursor(one=locked_client())

        if "FROM package_search_requests" in sql:
            return FakeCursor(one={
                "id": 72,
                "client_id": 1,
                "status": "running",
            })

        if sql.startswith("UPDATE package_search_requests"):
            assert "RETURNING id" in sql
            assert params[0] == "completed"
            assert isinstance(params[2], Jsonb)
            assert params[2].obj == results
            assert params[3] is None
            return FakeCursor(one={"id": 72})

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler(), result_handler],
    )

    response = client.post(
        "/api/package-search/72/result",
        json={
            "status": "completed",
            "results": results,
        },
        headers=agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "completed"
    assert data["search_id"] == 72
    assert data["result_count"] == 2
    assert data["finished_at"]

    assert connections[1].events == ["begin", "commit"]
    assert all(item.closed for item in connections)


def test_result_failed_stores_empty_jsonb_array(monkeypatch):
    def result_handler(connection, sql, params):
        if "FROM clients" in sql and "FOR UPDATE" in sql:
            return FakeCursor(one=locked_client())

        if "FROM package_search_requests" in sql:
            return FakeCursor(one={
                "id": 72,
                "client_id": 1,
                "status": "running",
            })

        if sql.startswith("UPDATE package_search_requests"):
            assert params[0] == "failed"
            assert isinstance(params[2], Jsonb)
            assert params[2].obj == []
            assert params[3] == "apt-cache search failed"
            return FakeCursor(one={"id": 72})

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler(), result_handler],
    )

    response = client.post(
        "/api/package-search/72/result",
        json={
            "status": "failed",
            "error_message": "apt-cache search failed",
        },
        headers=agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json()["result_count"] == 0
    assert connections[1].events == ["begin", "commit"]


def test_result_rejects_invalid_result_object(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler()],
    )

    response = client.post(
        "/api/package-search/72/result",
        json={
            "status": "completed",
            "results": ["not-an-object"],
        },
        headers=agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid result"}
    assert len(connections) == 1


def test_result_rejects_invalid_package_name(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler()],
    )

    response = client.post(
        "/api/package-search/72/result",
        json={
            "status": "completed",
            "results": [{"package": "nginx;id"}],
        },
        headers=agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid package"}
    assert len(connections) == 1


def test_result_rejects_more_than_fifty_results(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler()],
    )

    response = client.post(
        "/api/package-search/72/result",
        json={
            "status": "completed",
            "results": [
                {"package": f"package-{index}"}
                for index in range(51)
            ],
        },
        headers=agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "too many results"}
    assert len(connections) == 1


def test_result_rejects_wrong_client(monkeypatch):
    def result_handler(connection, sql, params):
        if "FROM clients" in sql and "FOR UPDATE" in sql:
            return FakeCursor(one=locked_client())

        if "FROM package_search_requests" in sql:
            return FakeCursor(one={
                "id": 72,
                "client_id": 2,
                "status": "running",
            })

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler(), result_handler],
    )

    response = client.post(
        "/api/package-search/72/result",
        json={
            "status": "completed",
            "results": [],
        },
        headers=agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "client_access_denied"
    }
    assert not any(
        sql.startswith("UPDATE package_search_requests")
        for sql, _ in connections[1].statements
    )


def test_result_rejects_non_running_search(monkeypatch):
    def result_handler(connection, sql, params):
        if "FROM clients" in sql and "FOR UPDATE" in sql:
            return FakeCursor(one=locked_client())

        if "FROM package_search_requests" in sql:
            return FakeCursor(one={
                "id": 72,
                "client_id": 1,
                "status": "completed",
            })

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler(), result_handler],
    )

    response = client.post(
        "/api/package-search/72/result",
        json={
            "status": "completed",
            "results": [],
        },
        headers=agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "search_not_running",
        "search_id": 72,
        "search_status": "completed",
    }


def test_result_rejects_revoked_token_before_search_lookup(monkeypatch):
    def result_handler(connection, sql, params):
        if "FROM clients" in sql and "FOR UPDATE" in sql:
            return FakeCursor(one=locked_client(
                token_revoked_at=datetime.now(timezone.utc)
            ))

        raise AssertionError(
            f"Search lookup must not run after revocation: {sql}"
        )

    _, client, connections = make_environment(
        monkeypatch,
        [client_auth_handler(), result_handler],
    )

    response = client.post(
        "/api/package-search/72/result",
        json={
            "status": "completed",
            "results": [],
        },
        headers=agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert connections[1].events == ["begin", "commit"]


def test_status_returns_native_jsonb_array_and_iso_timestamps(monkeypatch):
    created = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    started = datetime(2026, 11, 2, 12, 1, tzinfo=timezone.utc)
    finished = datetime(2026, 11, 2, 12, 2, tzinfo=timezone.utc)
    results = [{"package": "nginx", "version": "1.30.5-1"}]

    def status_handler(connection, sql, params):
        if "FROM package_search_requests" in sql:
            return FakeCursor(one={
                "id": 72,
                "client_id": 41,
                "query": "nginx",
                "status": "completed",
                "created_at": created,
                "started_at": started,
                "finished_at": finished,
                "result_json": results,
                "error_message": None,
            })

        raise AssertionError(f"Unexpected SQL: {sql}")

    _, client, connections = make_environment(
        monkeypatch,
        [None, status_handler],
    )
    set_session(client)

    response = client.get(
        "/api/clients/41/package-search/72",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["status"] == "completed"
    assert data["search_id"] == 72
    assert data["client_id"] == 41
    assert data["results"] == results
    assert data["error_message"] is None
    assert data["created_at"] == created.isoformat()
    assert data["started_at"] == started.isoformat()
    assert data["finished_at"] == finished.isoformat()

    assert all(connection.closed for connection in connections)


def test_status_rejects_viewer_even_with_package_permission(monkeypatch):
    _, client, connections = make_environment(
        monkeypatch,
        [],
        role="viewer",
        permissions=frozenset({"packages.search"}),
    )
    set_session(client)

    response = client.get(
        "/api/clients/41/package-search/72",
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert len(connections) == 1
