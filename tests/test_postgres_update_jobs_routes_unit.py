"""Database-free unit tests for PostgreSQL update-job routes."""

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from psycopg import Error as PsycopgError

from server import postgres_flask_security as pg_security
from server import postgres_update_jobs as jobs_module
from server.postgres_app import create_postgres_app
from server.security import hash_client_token


BASE_URL = "https://localhost"
CSRF_TOKEN = "update-jobs-route-test-csrf"
CLIENT_TOKEN = "update-jobs-agent-test-token"
CLIENT_ID = 41
JOB_ID = 73

ADMIN_PERMISSIONS = frozenset({
    "clients.view",
    "clients.manage",
    "software.view",
    "updates.view",
    "jobs.manage",
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
        return self.handler(self, normalized, params)

    def close(self):
        self.closed = True


def _make_environment(
    monkeypatch,
    handler,
    audit_handler=None,
    permissions=ADMIN_PERMISSIONS,
):
    connections = []

    def connection_factory():
        connection = FakeConnection(handler)
        connections.append(connection)
        return connection

    app = create_postgres_app({
        "SECRET_KEY": "postgres-update-jobs-route-unit-secret",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
    })


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

        if audit_handler is not None:
            audit_handler(connection, **kwargs)
            return

        connection.events.append(("audit", kwargs))

    monkeypatch.setattr(
        jobs_module,
        "transaction",
        fake_transaction,
    )
    monkeypatch.setattr(
        jobs_module,
        "audit_log",
        fake_audit,
    )

    # The outer bearer-token check remains real. This isolates only the
    # second client validation performed inside the route transaction.
    monkeypatch.setattr(
        jobs_module,
        "_lock_authenticated_client",
        lambda connection, client: dict(client),
    )

    client = app.test_client()

    with client.session_transaction(base_url=BASE_URL) as session:
        session.clear()
        session.update({
            "user_id": 7,
            "username": "administrator",
            "csrf_token": CSRF_TOKEN,
        })

    return client, connections


def _agent_headers():
    return {
        "Authorization": f"Bearer {CLIENT_TOKEN}",
    }


def _write_headers():
    return {
        "X-CSRF-Token": CSRF_TOKEN,
    }


def _authenticated_client_row():
    return {
        "id": CLIENT_ID,
        "hostname": "agent-01",
        "enabled": True,
        "client_token_hash": hash_client_token(CLIENT_TOKEN),
        "token_revoked_at": None,
    }


def _route_connection(connections, prefix):
    return next(
        connection
        for connection in connections
        if any(
            statement.startswith(prefix)
            for statement, _ in connection.statements
        )
    )


def test_create_update_job_creates_job_and_audit(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith("SELECT package, installed_version"):
            return FakeCursor(many=[
                {
                    "package": "curl",
                    "installed_version": "7.88.1",
                    "available_version": "7.88.2",
                },
            ])

        if statement.startswith("INSERT INTO update_jobs"):
            return FakeCursor(one={"id": JOB_ID})

        if statement.startswith("INSERT INTO update_job_packages"):
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        json={
            "action": "UPDATE_PACKAGE",
            "packages": ["curl"],
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 201
    assert response.get_json() == {
        "status": "created",
        "job_id": JOB_ID,
        "client_id": CLIENT_ID,
        "hostname": "agent-01",
        "action": "UPDATE_PACKAGE",
        "package_count": 1,
        "packages": [{
            "package": "curl",
            "installed_version": "7.88.1",
            "target_version": "7.88.2",
        }],
    }

    connection = _route_connection(
        connections,
        "INSERT INTO update_jobs",
    )

    assert connection.events[-1] == "transaction.commit"
    assert any(
        isinstance(event, tuple)
        and event[0] == "audit"
        and event[1]["action"] == "update_job.create"
        for event in connection.events
    )
    assert all(item.closed for item in connections)


def test_create_update_job_rolls_back_when_audit_fails(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith("SELECT package, installed_version"):
            return FakeCursor(many=[
                {
                    "package": "curl",
                    "installed_version": "7.88.1",
                    "available_version": "7.88.2",
                },
            ])

        if statement.startswith("INSERT INTO update_jobs"):
            return FakeCursor(one={"id": JOB_ID})

        if statement.startswith("INSERT INTO update_job_packages"):
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {statement}")

    def failing_audit(connection, **kwargs):
        raise PsycopgError("synthetic audit failure")

    client, connections = _make_environment(
        monkeypatch,
        handler,
        audit_handler=failing_audit,
    )

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        json={
            "action": "UPDATE_PACKAGE",
            "packages": ["curl"],
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "error": "database_unavailable",
    }

    connection = _route_connection(
        connections,
        "INSERT INTO update_jobs",
    )

    assert connection.events == [
        "transaction.begin",
        "transaction.rollback",
    ]
    assert all(item.closed for item in connections)


def test_get_client_update_jobs_returns_jobs_and_package_counts(monkeypatch):
    created_at = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 11, 7, 10, 15, tzinfo=timezone.utc)

    def handler(connection, statement, params):
        if statement.startswith("SELECT id FROM clients"):
            assert params == (CLIENT_ID,)
            return FakeCursor(one={"id": CLIENT_ID})

        if statement.startswith("SELECT j.id, j.client_id, j.status"):
            assert params == (CLIENT_ID,)
            assert "LEFT JOIN update_job_packages" in statement
            assert "COUNT(p.id) AS package_count" in statement
            assert "GROUP BY j.id" in statement
            assert "ORDER BY j.id DESC" in statement
            return FakeCursor(many=[
                {
                    "id": 75,
                    "client_id": CLIENT_ID,
                    "status": "success",
                    "created_at": created_at,
                    "started_at": created_at,
                    "finished_at": finished_at,
                    "reboot_required": False,
                    "package_count": 2,
                },
                {
                    "id": 74,
                    "client_id": CLIENT_ID,
                    "status": "failed",
                    "created_at": created_at,
                    "started_at": None,
                    "finished_at": None,
                    "reboot_required": True,
                    "package_count": 0,
                },
            ])

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == [
        {
            "id": 75,
            "client_id": CLIENT_ID,
            "status": "success",
            "created_at": "2026-11-07T10:00:00+00:00",
            "started_at": "2026-11-07T10:00:00+00:00",
            "finished_at": "2026-11-07T10:15:00+00:00",
            "reboot_required": False,
            "package_count": 2,
        },
        {
            "id": 74,
            "client_id": CLIENT_ID,
            "status": "failed",
            "created_at": "2026-11-07T10:00:00+00:00",
            "started_at": None,
            "finished_at": None,
            "reboot_required": True,
            "package_count": 0,
        },
    ]
    route_connection = _route_connection(
        connections,
        "SELECT id FROM clients",
    )
    assert route_connection.closed
    assert all(connection.closed for connection in connections)


def test_get_client_update_jobs_returns_not_found_for_missing_client(
    monkeypatch,
):
    def handler(connection, statement, params):
        assert statement.startswith("SELECT id FROM clients")
        assert params == (CLIENT_ID,)
        return FakeCursor(one=None)

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        base_url=BASE_URL,
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "status": "error",
        "message": "Client not found",
    }
    route_connection = _route_connection(
        connections,
        "SELECT id FROM clients",
    )
    assert route_connection.closed
    assert all(connection.closed for connection in connections)
    assert len(route_connection.statements) == 1


def test_get_client_update_jobs_returns_empty_list_when_no_jobs(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith("SELECT id FROM clients"):
            assert params == (CLIENT_ID,)
            return FakeCursor(one={"id": CLIENT_ID})

        if statement.startswith("SELECT j.id, j.client_id, j.status"):
            assert params == (CLIENT_ID,)
            assert "ORDER BY j.id DESC" in statement
            return FakeCursor(many=[])

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == []
    route_connection = _route_connection(
        connections,
        "SELECT id FROM clients",
    )
    assert route_connection.closed
    assert all(connection.closed for connection in connections)


def test_get_pending_update_job_returns_oldest_pending_job(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        if statement.startswith("SELECT id, hostname FROM clients"):
            assert params == (CLIENT_ID,)
            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith(
            "SELECT id, client_id, created_at, reboot_required, action "
            "FROM update_jobs"
        ):
            assert params == (CLIENT_ID,)
            assert "status = 'pending'" in statement
            assert "ORDER BY id ASC" in statement
            return FakeCursor(one={
                "id": JOB_ID,
                "client_id": CLIENT_ID,
                "created_at": None,
                "reboot_required": True,
                "action": "UPDATE_PACKAGE",
            })

        if statement.startswith(
            "SELECT package, installed_version, target_version, status "
            "FROM update_job_packages"
        ):
            assert params == (JOB_ID,)
            return FakeCursor(many=[
                {
                    "package": "curl",
                    "installed_version": "7.88.1",
                    "target_version": "7.88.2",
                    "status": "pending",
                },
            ])

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/clients/{CLIENT_ID}/update-jobs/pending",
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "pending",
        "job_id": JOB_ID,
        "client_id": CLIENT_ID,
        "created_at": None,
        "action": "UPDATE_PACKAGE",
        "reboot_required": True,
        "packages": [{
            "package": "curl",
            "installed_version": "7.88.1",
            "target_version": "7.88.2",
            "status": "pending",
        }],
    }
    assert all(item.closed for item in connections)


def test_get_pending_update_job_returns_no_content_when_empty(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith(
            "SELECT id, client_id, created_at, reboot_required, action "
            "FROM update_jobs"
        ):
            return FakeCursor(one=None)

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/clients/{CLIENT_ID}/update-jobs/pending",
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 204
    assert all(item.closed for item in connections)


def test_get_pending_update_job_returns_not_found_for_missing_client(
    monkeypatch,
):
    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one=None)

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/clients/{CLIENT_ID}/update-jobs/pending",
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "status": "error",
        "message": "Client not found",
    }
    assert all(item.closed for item in connections)


def test_get_pending_update_job_rejects_different_client_id(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        raise AssertionError(
            f"Database must not be queried after client ID mismatch: "
            f"{statement}"
        )

    client, connections = _make_environment(monkeypatch, handler)
    other_client_id = CLIENT_ID + 1

    response = client.get(
        f"/api/clients/{other_client_id}/update-jobs/pending",
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "client_access_denied",
    }
    assert all(item.closed for item in connections)



def test_get_running_update_job_returns_oldest_running_job(monkeypatch):
    created_at = "2026-11-07T10:00:00+00:00"
    started_at = "2026-11-07T10:05:00+00:00"

    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        if statement.startswith("SELECT id, hostname FROM clients"):
            assert params == (CLIENT_ID,)
            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith(
            "SELECT id, client_id, created_at, started_at"
        ):
            assert params == (CLIENT_ID,)
            assert "status = 'running'" in statement
            assert "ORDER BY id ASC" in statement
            return FakeCursor(one={
                "id": JOB_ID,
                "client_id": CLIENT_ID,
                "created_at": created_at,
                "started_at": started_at,
                "reboot_required": True,
                "action": "UPDATE_PACKAGE",
            })

        if statement.startswith(
            "SELECT package, target_version, status FROM update_job_packages"
        ):
            assert params == (JOB_ID,)
            assert "ORDER BY id ASC" in statement
            return FakeCursor(many=[{
                "package": "curl",
                "target_version": "7.88.2",
                "status": "pending",
            }])

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/clients/{CLIENT_ID}/update-jobs/running",
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "running",
        "job_id": JOB_ID,
        "client_id": CLIENT_ID,
        "created_at": created_at,
        "started_at": started_at,
        "reboot_required": True,
        "action": "UPDATE_PACKAGE",
        "packages": [{
            "package": "curl",
            "target_version": "7.88.2",
            "status": "pending",
        }],
    }
    assert all(item.closed for item in connections)


def test_get_running_update_job_returns_no_content_when_empty(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith(
            "SELECT id, client_id, created_at, started_at"
        ):
            return FakeCursor(one=None)

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/clients/{CLIENT_ID}/update-jobs/running",
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 204
    assert all(item.closed for item in connections)


def test_get_running_update_job_returns_not_found_for_missing_client(
    monkeypatch,
):
    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one=None)

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/clients/{CLIENT_ID}/update-jobs/running",
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "status": "error",
        "message": "Client not found",
    }
    assert all(item.closed for item in connections)


def test_get_running_update_job_rejects_different_client_id(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        raise AssertionError(
            "Database must not be queried after client ID mismatch: "
            f"{statement}"
        )

    client, connections = _make_environment(monkeypatch, handler)
    other_client_id = CLIENT_ID + 1

    response = client.get(
        f"/api/clients/{other_client_id}/update-jobs/running",
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "client_access_denied",
    }
    assert all(item.closed for item in connections)


def test_claim_update_job_marks_pending_job_running(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        if statement.startswith("SELECT id, client_id, status"):
            return FakeCursor(one={
                "id": JOB_ID,
                "client_id": CLIENT_ID,
                "status": "pending",
                "created_at": None,
                "started_at": None,
                "finished_at": None,
                "reboot_required": False,
                "recovery_reason": None,
                "action": "UPDATE_PACKAGE",
            })

        if statement.startswith("UPDATE update_jobs"):
            return FakeCursor(rowcount=1)

        if statement.startswith("SELECT package, installed_version"):
            return FakeCursor(many=[
                {
                    "package": "curl",
                    "installed_version": "7.88.1",
                    "target_version": "7.88.2",
                    "status": "pending",
                },
            ])

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs/{JOB_ID}/claim",
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["status"] == "claimed"
    assert data["job_id"] == JOB_ID
    assert data["client_id"] == CLIENT_ID
    assert data["action"] == "UPDATE_PACKAGE"
    assert data["reboot_required"] is False
    assert data["packages"] == [{
        "package": "curl",
        "installed_version": "7.88.1",
        "target_version": "7.88.2",
        "status": "pending",
    }]
    assert data["started_at"]

    route_connection = _route_connection(
        connections,
        "UPDATE update_jobs",
    )

    assert route_connection.events[-1] == "transaction.commit"
    assert all(item.closed for item in connections)


def test_checkpoint_updates_package_status(monkeypatch):
    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        if statement.startswith("SELECT id, client_id, status"):
            return FakeCursor(one={
                "id": JOB_ID,
                "client_id": CLIENT_ID,
                "status": "running",
                "created_at": None,
                "started_at": None,
                "finished_at": None,
                "reboot_required": False,
                "recovery_reason": None,
                "action": "UPDATE_PACKAGE",
            })

        if statement.startswith(
            "SELECT id FROM update_job_packages"
        ):
            return FakeCursor(one={"id": 501})

        if statement.startswith("UPDATE update_job_packages"):
            return FakeCursor(rowcount=1)

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/checkpoint",
        json={
            "package": "curl",
            "status": "success",
            "message": "Package updated",
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "checkpointed",
        "job_id": JOB_ID,
        "package": "curl",
        "package_status": "success",
    }

    connection = _route_connection(
        connections,
        "UPDATE update_job_packages",
    )

    assert connection.events[-1] == "transaction.commit"
    assert all(item.closed for item in connections)


def test_agent_route_rejects_missing_bearer_token(monkeypatch):
    def handler(connection, statement, params):
        raise AssertionError(
            f"Database must not be queried without a bearer token: {statement}"
        )

    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs/{JOB_ID}/claim",
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "client_authentication_required",
    }
    assert connections == []


def _result_test_handler(
    *,
    action="UPDATE_PACKAGE",
    package_update_rowcount=1,
    job_update_rowcount=1,
    package_count=2,
    fail_on_statement=None,
    fail_on_statement_occurrence=1,
):
    history_inserts = []
    attempted_statements = []
    statement_occurrences = {}

    def handler(connection, statement, params):
        attempted_statements.append(statement)

        if (
            fail_on_statement is not None
            and statement.startswith(fail_on_statement)
        ):
            statement_occurrences[fail_on_statement] = (
                statement_occurrences.get(fail_on_statement, 0) + 1
            )
            if (
                statement_occurrences[fail_on_statement]
                == fail_on_statement_occurrence
            ):
                raise PsycopgError(
                    f"synthetic database failure: {fail_on_statement}"
                )

        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        if statement.startswith(
            "SELECT id, client_id, status, created_at"
        ):
            return FakeCursor(one={
                "id": JOB_ID,
                "client_id": CLIENT_ID,
                "status": "running",
                "created_at": None,
                "started_at": "2026-11-05T10:00:00+00:00",
                "finished_at": None,
                "reboot_required": False,
                "recovery_reason": None,
                "action": action,
            })

        if statement.startswith("SELECT package FROM update_job_packages"):
            return FakeCursor(many=[
                {"package": f"package-{index}"}
                for index in range(1, package_count + 1)
            ])

        if statement.startswith("UPDATE update_job_packages"):
            return FakeCursor(rowcount=package_update_rowcount)

        if statement.startswith("UPDATE update_jobs"):
            return FakeCursor(rowcount=job_update_rowcount)

        if statement.startswith("INSERT INTO update_history"):
            history_inserts.append((statement, params))
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {statement}")

    handler.attempted_statements = attempted_statements
    return handler, history_inserts


@pytest.mark.parametrize(
    ("package_statuses", "submitted_status", "expected_status"),
    [
        (["success", "success"], "success", "success"),
        (["success", "failed"], "partial", "partial"),
        (["failed", "failed"], "failed", "failed"),
    ],
)
def test_result_updates_packages_job_and_history(
    monkeypatch,
    package_statuses,
    submitted_status,
    expected_status,
):
    handler, history_inserts = _result_test_handler()
    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": submitted_status,
            "reboot_required": True,
            "packages": [
                {
                    "package": f"package-{index}",
                    "status": package_status,
                    "message": f"result-{index}",
                }
                for index, package_status in enumerate(
                    package_statuses,
                    start=1,
                )
            ],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "job_id": JOB_ID,
        "job_status": expected_status,
        "successful_count": package_statuses.count("success"),
        "failed_count": package_statuses.count("failed"),
        "reboot_required": True,
    }

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, status, created_at",
    )

    package_updates = [
        (statement, params)
        for statement, params in route_connection.statements
        if statement.startswith("UPDATE update_job_packages")
    ]
    assert len(package_updates) == 2

    job_updates = [
        (statement, params)
        for statement, params in route_connection.statements
        if statement.startswith("UPDATE update_jobs")
    ]
    assert len(job_updates) == 1
    assert job_updates[0][1][0] == expected_status

    assert len(history_inserts) == 1
    history_params = history_inserts[0][1]
    assert history_params[:7] == (
        CLIENT_ID,
        JOB_ID,
        expected_status,
        2,
        package_statuses.count("success"),
        package_statuses.count("failed"),
        True,
    )

    audit_events = [
        event[1]
        for event in route_connection.events
        if isinstance(event, tuple) and event[0] == "audit"
    ]
    assert audit_events == [{
        "actor_type": "client",
        "actor_id": CLIENT_ID,
        "action": "update_job.result",
        "target": f"job:{JOB_ID}",
        "result": "success",
        "details": (
            f"status={expected_status}; package_count=2; "
            f"successful_count={package_statuses.count('success')}; "
            f"failed_count={package_statuses.count('failed')}; "
            "reboot_required=true"
        ),
    }]
    assert route_connection.events[-1] == "transaction.commit"
    assert all(item.closed for item in connections)


def test_update_system_result_creates_history_without_packages(monkeypatch):
    handler, history_inserts = _result_test_handler(
        action="UPDATE_SYSTEM",
        package_count=0,
    )
    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": "success",
            "reboot_required": True,
            "packages": [],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "job_id": JOB_ID,
        "job_status": "success",
        "successful_count": 0,
        "failed_count": 0,
        "reboot_required": True,
    }

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, status, created_at",
    )

    assert not any(
        statement.startswith("UPDATE update_job_packages")
        for statement, _ in route_connection.statements
    )

    assert len(history_inserts) == 1
    assert history_inserts[0][1][:4] == (
        CLIENT_ID,
        JOB_ID,
        "success",
        True,
    )

    audit_events = [
        event[1]
        for event in route_connection.events
        if isinstance(event, tuple) and event[0] == "audit"
    ]
    assert audit_events == [{
        "actor_type": "client",
        "actor_id": CLIENT_ID,
        "action": "update_job.result",
        "target": f"job:{JOB_ID}",
        "result": "success",
        "details": (
            "status=success; package_count=0; successful_count=0; "
            "failed_count=0; reboot_required=true"
        ),
    }]
    assert route_connection.events[-1] == "transaction.commit"
    assert all(item.closed for item in connections)


def test_result_package_update_conflict_rolls_back(monkeypatch):
    handler, history_inserts = _result_test_handler(
        package_update_rowcount=0,
    )
    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": "success",
            "packages": [
                {"package": "package-1", "status": "success"},
                {"package": "package-2", "status": "success"},
            ],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "package_update_conflict",
        "package": "package-1",
    }

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, status, created_at",
    )

    assert route_connection.events == [
        "transaction.begin",
        "transaction.rollback",
    ]
    assert not history_inserts
    assert not any(
        statement.startswith("UPDATE update_jobs")
        for statement, _ in route_connection.statements
    )
    assert all(item.closed for item in connections)


def test_result_job_update_conflict_rolls_back_package_updates(monkeypatch):
    handler, history_inserts = _result_test_handler(
        job_update_rowcount=0,
    )
    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": "success",
            "packages": [
                {"package": "package-1", "status": "success"},
                {"package": "package-2", "status": "success"},
            ],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "job_update_conflict",
    }

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, status, created_at",
    )

    assert sum(
        statement.startswith("UPDATE update_job_packages")
        for statement, _ in route_connection.statements
    ) == 2

    assert route_connection.events == [
        "transaction.begin",
        "transaction.rollback",
    ]
    assert not history_inserts
    assert all(item.closed for item in connections)


def test_abandon_running_job_updates_history(monkeypatch):
    history_inserts = []

    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        if statement.startswith(
            "SELECT id, client_id, status, created_at"
        ):
            return FakeCursor(one={
                "id": JOB_ID,
                "client_id": CLIENT_ID,
                "status": "running",
                "created_at": None,
                "started_at": "2026-11-05T10:00:00+00:00",
                "finished_at": None,
                "reboot_required": True,
                "recovery_reason": None,
                "action": "UPDATE_PACKAGE",
            })

        if statement.startswith("SELECT COUNT(*) AS package_count"):
            return FakeCursor(one={"package_count": 3})

        if statement.startswith("UPDATE update_jobs"):
            return FakeCursor(rowcount=1)

        if statement.startswith("INSERT INTO update_history"):
            history_inserts.append(params)
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/abandon",
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    body = response.get_json()

    assert body["status"] == "abandoned"
    assert body["job_id"] == JOB_ID
    assert body["client_id"] == CLIENT_ID
    assert body["package_count"] == 3
    assert body["recovery_reason"]

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, status, created_at",
    )

    assert len(history_inserts) == 1
    assert history_inserts[0][:5] == (
        CLIENT_ID,
        JOB_ID,
        "abandoned",
        3,
        True,
    )

    assert route_connection.events[-1] == "transaction.commit"
    assert all(item.closed for item in connections)


def test_abandon_job_update_conflict_does_not_create_history(monkeypatch):
    history_inserts = []

    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        if statement.startswith(
            "SELECT id, client_id, status, created_at"
        ):
            return FakeCursor(one={
                "id": JOB_ID,
                "client_id": CLIENT_ID,
                "status": "running",
                "created_at": None,
                "started_at": "2026-11-05T10:00:00+00:00",
                "finished_at": None,
                "reboot_required": False,
                "recovery_reason": None,
                "action": "UPDATE_PACKAGE",
            })

        if statement.startswith("SELECT COUNT(*) AS package_count"):
            return FakeCursor(one={"package_count": 2})

        if statement.startswith("UPDATE update_jobs"):
            return FakeCursor(rowcount=0)

        if statement.startswith("INSERT INTO update_history"):
            history_inserts.append(params)
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/abandon",
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "job_recovery_conflict",
    }

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, status, created_at",
    )

    assert not history_inserts
    assert route_connection.events[-1] == "transaction.commit"
    assert all(item.closed for item in connections)


def test_create_update_job_requires_jobs_manage(monkeypatch):
    def unexpected_sql(connection, statement, params):
        raise AssertionError(
            f"Database query must not run: {statement}"
        )

    permissions = ADMIN_PERMISSIONS - {"jobs.manage"}

    client, connections = _make_environment(
        monkeypatch,
        unexpected_sql,
        permissions=permissions,
    )

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        json={"action": "UPDATE_SYSTEM"},
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required",
    }

    assert all(not connection.statements for connection in connections)
    assert all(connection.closed for connection in connections)


@pytest.mark.parametrize(
    "path",
    [
        f"/api/clients/{CLIENT_ID}/update-jobs",
        f"/api/update-jobs/{JOB_ID}",
        f"/api/clients/{CLIENT_ID}/update-history",
        "/api/update-history",
    ],
)
def test_update_job_read_routes_require_updates_view(
    monkeypatch,
    path,
):
    def unexpected_sql(connection, statement, params):
        raise AssertionError(
            f"Database query must not run: {statement}"
        )

    permissions = ADMIN_PERMISSIONS - {"updates.view"}

    client, connections = _make_environment(
        monkeypatch,
        unexpected_sql,
        permissions=permissions,
    )

    response = client.get(
        path,
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "authorization_required",
    }

    assert all(not connection.statements for connection in connections)
    assert all(connection.closed for connection in connections)


RESULT_VALIDATION_CASES = [
    (
        "non_object_json",
        ["not", "an object"],
        {"error": "invalid_json"},
    ),
    (
        "invalid_status_type",
        {"status": [], "packages": []},
        {"error": "invalid status"},
    ),
    (
        "invalid_packages_type",
        {"status": "success", "packages": "not-a-list"},
        {"error": "invalid packages"},
    ),
    (
        "too_many_packages",
        {
            "status": "success",
            "packages": [
                {
                    "package": f"package-{index}",
                    "status": "success",
                }
                for index in range(
                    jobs_module._MAX_PACKAGE_RESULTS + 1
                )
            ],
        },
        {"error": "too_many_package_results"},
    ),
    (
        "invalid_package_result_type",
        {"status": "success", "packages": [None]},
        {"error": "invalid package result"},
    ),
    (
        "empty_package_name",
        {
            "status": "success",
            "packages": [
                {"package": "   ", "status": "success"},
            ],
        },
        {"error": "invalid package"},
    ),
    (
        "duplicate_package",
        {
            "status": "success",
            "packages": [
                {"package": "curl", "status": "success"},
                {"package": "curl", "status": "failed"},
            ],
        },
        {
            "error": "duplicate package",
            "package": "curl",
        },
    ),
    (
        "invalid_package_status",
        {
            "status": "success",
            "packages": [
                {"package": "curl", "status": "unknown"},
            ],
        },
        {"error": "invalid package status"},
    ),
    (
        "invalid_package_message_type",
        {
            "status": "success",
            "packages": [
                {
                    "package": "curl",
                    "status": "success",
                    "message": 123,
                },
            ],
        },
        {
            "error": "invalid package message",
            "package": "curl",
        },
    ),
    (
        "oversized_package_message",
        {
            "status": "success",
            "packages": [
                {
                    "package": "curl",
                    "status": "success",
                    "message": "x" * (
                        jobs_module._MAX_RESULT_MESSAGE_LENGTH + 1
                    ),
                },
            ],
        },
        {
            "error": "package message too long",
            "package": "curl",
        },
    ),
]


@pytest.mark.parametrize(
    "case_name,payload,expected_body",
    RESULT_VALIDATION_CASES,
    ids=[case[0] for case in RESULT_VALIDATION_CASES],
)
def test_result_rejects_invalid_input_before_route_database_access(
    monkeypatch,
    case_name,
    payload,
    expected_body,
):
    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        raise AssertionError(
            f"Unexpected database query for {case_name}: {statement}"
        )

    client, connections = _make_environment(
        monkeypatch,
        handler,
    )

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json=payload,
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json() == expected_body

    # Only the outer bearer-token validation may access the database.
    # The route's job transaction must never be opened for invalid input.
    assert len(connections) == 1
    assert len(connections[0].statements) == 1
    assert connections[0].statements[0][0].startswith(
        "SELECT id, hostname, enabled, client_token_hash"
    )
    assert connections[0].closed


def _result_state_test_handler(
    *,
    job=None,
    other_job=None,
    packages=None,
):
    def handler(connection, statement, params):
        if statement.startswith(
            "SELECT id, hostname, enabled, client_token_hash"
        ):
            return FakeCursor(one=_authenticated_client_row())

        if statement.startswith(
            "SELECT id, client_id, status, created_at"
        ):
            return FakeCursor(one=job)

        if statement.startswith(
            "SELECT client_id FROM update_jobs"
        ):
            return FakeCursor(one=other_job)

        if statement.startswith(
            "SELECT package FROM update_job_packages"
        ):
            return FakeCursor(many=packages or [])

        raise AssertionError(f"Unexpected SQL: {statement}")

    return handler


def test_result_rejects_unknown_job(monkeypatch):
    handler = _result_state_test_handler(
        job=None,
        other_job=None,
    )
    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": "success",
            "packages": [],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "error": "job not found",
    }

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, status, created_at",
    )

    assert route_connection.events[-1] == "transaction.commit"
    assert all(item.closed for item in connections)


def test_result_rejects_job_owned_by_another_client(monkeypatch):
    handler = _result_state_test_handler(
        job=None,
        other_job={"client_id": CLIENT_ID + 1},
    )
    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": "success",
            "packages": [],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "client_access_denied",
    }

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, status, created_at",
    )

    assert route_connection.events[-1] == "transaction.commit"
    assert all(item.closed for item in connections)


def test_result_rejects_job_that_is_not_running(monkeypatch):
    handler = _result_state_test_handler(
        job={
            "id": JOB_ID,
            "client_id": CLIENT_ID,
            "status": "success",
            "created_at": None,
            "started_at": None,
            "finished_at": None,
            "reboot_required": False,
            "recovery_reason": None,
            "action": "UPDATE_PACKAGE",
        },
    )
    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": "success",
            "packages": [],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "job_not_running",
        "job_id": JOB_ID,
        "job_status": "success",
    }

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, status, created_at",
    )

    assert not any(
        statement.startswith("UPDATE update_jobs")
        for statement, _ in route_connection.statements
    )
    assert route_connection.events[-1] == "transaction.commit"
    assert all(item.closed for item in connections)


def _running_result_job(*, action="UPDATE_PACKAGE"):
    return {
        "id": JOB_ID,
        "client_id": CLIENT_ID,
        "status": "running",
        "created_at": None,
        "started_at": None,
        "finished_at": None,
        "reboot_required": False,
        "recovery_reason": None,
        "action": action,
    }


def _assert_result_rejected_before_writes(route_connection):
    assert not any(
        statement.startswith(("UPDATE ", "INSERT "))
        for statement, _ in route_connection.statements
    )
    assert not any(
        isinstance(event, tuple) and event[0] == "audit"
        for event in route_connection.events
    )
    assert route_connection.events[-1] == "transaction.commit"


def test_result_rejects_incomplete_package_results(monkeypatch):
    handler = _result_state_test_handler(
        job=_running_result_job(),
        packages=[
            {"package": "curl"},
            {"package": "wget"},
        ],
    )
    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": "success",
            "packages": [
                {"package": "curl", "status": "success"},
            ],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "incomplete_package_results",
        "expected": 2,
        "received": 1,
    }

    route_connection = _route_connection(
        connections, "SELECT id, client_id, status, created_at"
    )
    _assert_result_rejected_before_writes(route_connection)
    assert all(item.closed for item in connections)


def test_result_rejects_unexpected_package_results(monkeypatch):
    handler = _result_state_test_handler(
        job=_running_result_job(),
        packages=[
            {"package": "curl"},
            {"package": "wget"},
        ],
    )
    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": "success",
            "packages": [
                {"package": "curl", "status": "success"},
                {"package": "alien", "status": "success"},
            ],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "package_result_mismatch",
        "missing_packages": ["wget"],
        "unexpected_packages": ["alien"],
    }

    route_connection = _route_connection(
        connections, "SELECT id, client_id, status, created_at"
    )
    _assert_result_rejected_before_writes(route_connection)
    assert all(item.closed for item in connections)


def test_result_rejects_inconsistent_overall_status(monkeypatch):
    handler = _result_state_test_handler(
        job=_running_result_job(),
        packages=[
            {"package": "curl"},
            {"package": "wget"},
        ],
    )
    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": "success",
            "packages": [
                {"package": "curl", "status": "success"},
                {"package": "wget", "status": "failed"},
            ],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "status_mismatch",
        "submitted_status": "success",
        "derived_status": "partial",
    }

    route_connection = _route_connection(
        connections, "SELECT id, client_id, status, created_at"
    )
    _assert_result_rejected_before_writes(route_connection)
    assert all(item.closed for item in connections)


def test_result_rejects_packages_for_system_update(monkeypatch):
    handler = _result_state_test_handler(
        job=_running_result_job(action="UPDATE_SYSTEM"),
        packages=[],
    )
    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": "success",
            "packages": [
                {"package": "unexpected", "status": "success"},
            ],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "system_update_must_not_contain_packages"
    }

    route_connection = _route_connection(
        connections, "SELECT id, client_id, status, created_at"
    )
    _assert_result_rejected_before_writes(route_connection)
    assert all(item.closed for item in connections)


def test_result_rolls_back_when_audit_fails(monkeypatch):
    handler, history_inserts = _result_test_handler()
    audit_calls = []

    def failing_audit(connection, **kwargs):
        audit_calls.append(kwargs)
        raise PsycopgError("synthetic result audit failure")

    client, connections = _make_environment(
        monkeypatch,
        handler,
        audit_handler=failing_audit,
    )

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": "success",
            "reboot_required": True,
            "packages": [
                {"package": "package-1", "status": "success"},
                {"package": "package-2", "status": "success"},
            ],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "error": "database_unavailable",
    }
    assert len(history_inserts) == 1
    assert audit_calls == [{
        "actor_type": "client",
        "actor_id": CLIENT_ID,
        "action": "update_job.result",
        "target": f"job:{JOB_ID}",
        "result": "success",
        "details": (
            "status=success; package_count=2; successful_count=2; "
            "failed_count=0; reboot_required=true"
        ),
    }]

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, status, created_at",
    )
    assert route_connection.events == [
        "transaction.begin",
        "transaction.rollback",
    ]
    assert all(item.closed for item in connections)


# ============================================================
# CREATE UPDATE JOB: INPUT VALIDATION
# ============================================================

CREATE_VALIDATION_CASES = [
    (
        "non_object_json",
        [],
        400,
        {
            "status": "error",
            "message": "Invalid or missing JSON data",
        },
    ),
    (
        "empty_json_object",
        {},
        400,
        {
            "status": "error",
            "message": "Invalid or missing JSON data",
        },
    ),
    (
        "invalid_action_type",
        {"action": []},
        400,
        {
            "status": "error",
            "message": "Invalid package action",
            "allowed_actions": sorted(jobs_module._ALLOWED_ACTIONS),
        },
    ),
    (
        "invalid_action",
        {"action": "EXECUTE_SHELL"},
        400,
        {
            "status": "error",
            "message": "Invalid package action",
            "allowed_actions": sorted(jobs_module._ALLOWED_ACTIONS),
        },
    ),
    (
        "missing_packages",
        {"action": "UPDATE_PACKAGE"},
        400,
        {
            "status": "error",
            "message": "packages must be a list",
        },
    ),
    (
        "packages_not_a_list",
        {
            "action": "UPDATE_PACKAGE",
            "packages": "curl",
        },
        400,
        {
            "status": "error",
            "message": "packages must be a list",
        },
    ),
    (
        "empty_packages",
        {
            "action": "UPDATE_PACKAGE",
            "packages": [],
        },
        400,
        {
            "status": "error",
            "message": "No packages selected",
        },
    ),
    (
        "invalid_package_name",
        {
            "action": "UPDATE_PACKAGE",
            "packages": ["-malicious"],
        },
        400,
        {
            "status": "error",
            "message": "Invalid package name",
            "packages": ["-malicious"],
        },
    ),
    (
        "package_not_a_string",
        {
            "action": "UPDATE_PACKAGE",
            "packages": ["curl", None],
        },
        400,
        {
            "status": "error",
            "message": "Invalid package name",
            "packages": [None],
        },
    ),
]


@pytest.mark.parametrize(
    "_case,payload,expected_status,expected_body",
    CREATE_VALIDATION_CASES,
)
def test_create_update_job_rejects_invalid_input_before_database_access(
    monkeypatch,
    _case,
    payload,
    expected_status,
    expected_body,
):
    def unexpected_sql(connection, statement, params):
        raise AssertionError(
            f"Database query must not run: {statement}"
        )

    client, connections = _make_environment(
        monkeypatch,
        unexpected_sql,
    )

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        json=payload,
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == expected_status
    assert response.get_json() == expected_body
    assert all(not connection.statements for connection in connections)
    assert all(not connection.events for connection in connections)
    assert all(connection.closed for connection in connections)


def test_create_update_job_rejects_malformed_json_before_database_access(
    monkeypatch,
):
    def unexpected_sql(connection, statement, params):
        raise AssertionError(
            f"Database query must not run: {statement}"
        )

    client, connections = _make_environment(
        monkeypatch,
        unexpected_sql,
    )

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        data="{ malformed",
        content_type="application/json",
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "message": "Invalid or missing JSON data",
    }
    assert all(not connection.statements for connection in connections)
    assert all(not connection.events for connection in connections)
    assert all(connection.closed for connection in connections)


# ============================================================
# CREATE UPDATE JOB: TRANSACTIONAL REJECTIONS
# ============================================================

@pytest.mark.parametrize(
    "scenario,action,expected_status,expected_message",
    [
        (
            "client_not_found",
            "UPDATE_SYSTEM",
            404,
            "Client not found",
        ),
        (
            "no_system_updates",
            "UPDATE_SYSTEM",
            409,
            (
                "No system updates are available. "
                "No job was created."
            ),
        ),
        (
            "package_not_available",
            "UPDATE_PACKAGE",
            400,
            (
                "One or more packages are "
                "not available as updates"
            ),
        ),
    ],
)
def test_create_update_job_rejections_do_not_write_or_audit(
    monkeypatch,
    scenario,
    action,
    expected_status,
    expected_message,
):
    def handler(connection, statement, params):
        if statement.startswith("SELECT id, hostname FROM clients"):
            if scenario == "client_not_found":
                return FakeCursor(one=None)

            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith("SELECT COUNT(*) AS package_count"):
            return FakeCursor(one={
                "package_count": 0,
            })

        if statement.startswith("SELECT package, installed_version"):
            return FakeCursor(many=[])

        raise AssertionError(
            f"Unexpected SQL for rejected request: {statement}"
        )

    client, connections = _make_environment(
        monkeypatch,
        handler,
    )

    payload = {"action": action}

    if action == "UPDATE_PACKAGE":
        payload["packages"] = ["curl"]

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        json=payload,
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == expected_status

    body = response.get_json()
    assert body["status"] == "error"
    assert body["message"] == expected_message

    for connection in connections:
        assert not any(
            statement.startswith((
                "INSERT INTO update_jobs",
                "INSERT INTO update_job_packages",
            ))
            for statement, _ in connection.statements
        )
        assert not any(
            isinstance(event, tuple) and event[0] == "audit"
            for event in connection.events
        )
        assert connection.closed

    route_connection = _route_connection(
        connections,
        "SELECT id, hostname FROM clients",
    )
    assert route_connection.events[-1] == "transaction.commit"


# ============================================================
# CREATE UPDATE JOB: ACTION-SPECIFIC SUCCESS
# ============================================================

@pytest.mark.parametrize(
    "action,expected_package_count,request_packages",
    [
        ("UPDATE_SYSTEM", 0, ["ignored-package"]),
        ("INSTALL_PACKAGE", 1, ["curl"]),
        ("REMOVE_PACKAGE", 1, ["curl"]),
    ],
)
def test_create_update_job_supports_remaining_actions(
    monkeypatch,
    action,
    expected_package_count,
    request_packages,
):
    inserted_job_packages = []

    def handler(connection, statement, params):
        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith("SELECT COUNT(*) AS package_count"):
            return FakeCursor(one={
                "package_count": 2,
            })

        if statement.startswith("INSERT INTO update_jobs"):
            return FakeCursor(one={"id": JOB_ID})

        if statement.startswith("INSERT INTO update_job_packages"):
            inserted_job_packages.append(params)
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(
        monkeypatch,
        handler,
    )

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        json={
            "action": action,
            "packages": request_packages,
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 201

    body = response.get_json()
    assert body["status"] == "created"
    assert body["job_id"] == JOB_ID
    assert body["client_id"] == CLIENT_ID
    assert body["hostname"] == "agent-01"
    assert body["action"] == action
    assert body["package_count"] == expected_package_count

    if action == "UPDATE_SYSTEM":
        assert body["packages"] == []
        assert inserted_job_packages == []
    else:
        assert body["packages"] == [{
            "package": "curl",
            "installed_version": None,
            "target_version": "",
        }]
        assert len(inserted_job_packages) == 1
        assert inserted_job_packages[0][1:] == (
            "curl",
            None,
            "",
            "pending",
        )

    connection = _route_connection(
        connections,
        "INSERT INTO update_jobs",
    )

    audit_events = [
        event[1]
        for event in connection.events
        if isinstance(event, tuple) and event[0] == "audit"
    ]

    assert audit_events == [{
        "actor_type": "user",
        "actor_id": 7,
        "action": "update_job.create",
        "target": f"job:{JOB_ID}",
        "result": "success",
        "details": (
            f"client={CLIENT_ID} "
            f"action={action} "
            f"packages={expected_package_count}"
        ),
    }]

    assert connection.events[-1] == "transaction.commit"
    assert all(item.closed for item in connections)


# ============================================================
# CREATE UPDATE JOB: PACKAGE NORMALIZATION
# ============================================================

@pytest.mark.parametrize(
    "requested_packages,expected_packages",
    [
        (
            ["curl", "curl"],
            ["curl"],
        ),
        (
            ["curl", " curl "],
            ["curl"],
        ),
        (
            ["curl", " curl ", "wget", "curl"],
            ["curl", "wget"],
        ),
    ],
)
def test_create_update_job_normalizes_package_names(
    monkeypatch,
    requested_packages,
    expected_packages,
):
    captured_package_queries = []
    inserted_job_packages = []

    def handler(connection, statement, params):
        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith("SELECT package, installed_version"):
            captured_package_queries.append(params[1])

            return FakeCursor(many=[
                {
                    "package": package,
                    "installed_version": "1.0",
                    "available_version": "2.0",
                }
                for package in reversed(expected_packages)
            ])

        if statement.startswith("INSERT INTO update_jobs"):
            return FakeCursor(one={"id": JOB_ID})

        if statement.startswith("INSERT INTO update_job_packages"):
            inserted_job_packages.append(params)
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(
        monkeypatch,
        handler,
    )

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        json={
            "action": "UPDATE_PACKAGE",
            "packages": requested_packages,
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 201

    body = response.get_json()

    assert captured_package_queries == [expected_packages]
    assert body["package_count"] == len(expected_packages)

    assert {
        item["package"]
        for item in body["packages"]
    } == set(expected_packages)

    assert {
        item[1]
        for item in inserted_job_packages
    } == set(expected_packages)

    assert len(inserted_job_packages) == len(expected_packages)

    route_connection = _route_connection(
        connections,
        "INSERT INTO update_jobs",
    )

    assert route_connection.events[-1] == "transaction.commit"
    assert all(connection.closed for connection in connections)


# ============================================================
# CREATE UPDATE JOB: MIXED PACKAGE AVAILABILITY
# ============================================================

def test_create_update_job_rejects_mixed_package_availability(
    monkeypatch,
):
    inserted_statements = []
    queried_packages = []

    def handler(connection, statement, params):
        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith("SELECT package, installed_version"):
            queried_packages.extend(params[1])

            return FakeCursor(many=[
                {
                    "package": "curl",
                    "installed_version": "1.0",
                    "available_version": "2.0",
                },
                {
                    "package": "wget",
                    "installed_version": "1.0",
                    "available_version": "2.0",
                },
            ])

        if statement.startswith((
            "INSERT INTO update_jobs",
            "INSERT INTO update_job_packages",
        )):
            inserted_statements.append(statement)
            raise AssertionError(
                "No job data may be inserted for mixed availability"
            )

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(
        monkeypatch,
        handler,
    )

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        json={
            "action": "UPDATE_PACKAGE",
            "packages": [
                "curl",
                "nicht-verfuegbar",
                "wget",
            ],
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400

    body = response.get_json()

    assert body["status"] == "error"
    assert body["invalid_packages"] == ["nicht-verfuegbar"]

    assert queried_packages == [
        "curl",
        "nicht-verfuegbar",
        "wget",
    ]

    assert inserted_statements == []

    for connection in connections:
        assert not any(
            isinstance(event, tuple) and event[0] == "audit"
            for event in connection.events
        )
        assert connection.closed

    route_connection = _route_connection(
        connections,
        "SELECT id, hostname FROM clients",
    )

    assert route_connection.events[-1] == "transaction.commit"


# ============================================================
# CREATE UPDATE JOB: MULTIPLE UNAVAILABLE PACKAGES
# ============================================================

def test_create_update_job_reports_all_unavailable_packages(
    monkeypatch,
):
    queried_packages = []

    def handler(connection, statement, params):
        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith("SELECT package, installed_version"):
            queried_packages.extend(params[1])

            return FakeCursor(many=[
                {
                    "package": "curl",
                    "installed_version": "1.0",
                    "available_version": "2.0",
                },
            ])

        if statement.startswith((
            "INSERT INTO update_jobs",
            "INSERT INTO update_job_packages",
        )):
            raise AssertionError(
                "Unavailable packages must prevent job creation"
            )

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(
        monkeypatch,
        handler,
    )

    requested_packages = [
        "curl",
        "missing-one",
        "missing-two",
    ]

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        json={
            "action": "UPDATE_PACKAGE",
            "packages": requested_packages,
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 400

    body = response.get_json()

    assert body["status"] == "error"
    assert body["invalid_packages"] == [
        "missing-one",
        "missing-two",
    ]

    assert queried_packages == requested_packages

    for connection in connections:
        assert not any(
            statement.startswith((
                "INSERT INTO update_jobs",
                "INSERT INTO update_job_packages",
            ))
            for statement, _ in connection.statements
        )

        assert not any(
            isinstance(event, tuple) and event[0] == "audit"
            for event in connection.events
        )

        assert connection.closed

    route_connection = _route_connection(
        connections,
        "SELECT id, hostname FROM clients",
    )

    assert route_connection.events[-1] == "transaction.commit"


# ============================================================
# CREATE UPDATE JOB: DATABASE FAILURE DURING JOB INSERT
# ============================================================

def test_create_update_job_rolls_back_when_job_insert_fails(
    monkeypatch,
):
    def handler(connection, statement, params):
        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith("SELECT package, installed_version"):
            return FakeCursor(many=[
                {
                    "package": "curl",
                    "installed_version": "1.0",
                    "available_version": "2.0",
                },
            ])

        if statement.startswith("INSERT INTO update_jobs"):
            raise PsycopgError("synthetic job insert failure")

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(
        monkeypatch,
        handler,
    )

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        json={
            "action": "UPDATE_PACKAGE",
            "packages": ["curl"],
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "error": "database_unavailable",
    }

    route_connection = _route_connection(
        connections,
        "SELECT id, hostname FROM clients",
    )

    assert route_connection.events == [
        "transaction.begin",
        "transaction.rollback",
    ]

    assert not any(
        isinstance(event, tuple) and event[0] == "audit"
        for connection in connections
        for event in connection.events
    )

    assert not any(
        statement.startswith("INSERT INTO update_job_packages")
        for connection in connections
        for statement, _ in connection.statements
    )

    assert all(connection.closed for connection in connections)


# ============================================================
# CREATE UPDATE JOB: DATABASE FAILURE DURING PACKAGE INSERT
# ============================================================

def test_create_update_job_rolls_back_when_package_insert_fails(
    monkeypatch,
):
    def handler(connection, statement, params):
        if statement.startswith("SELECT id, hostname FROM clients"):
            return FakeCursor(one={
                "id": CLIENT_ID,
                "hostname": "agent-01",
            })

        if statement.startswith("SELECT package, installed_version"):
            return FakeCursor(many=[
                {
                    "package": "curl",
                    "installed_version": "1.0",
                    "available_version": "2.0",
                },
            ])

        if statement.startswith("INSERT INTO update_jobs"):
            return FakeCursor(one={"id": JOB_ID})

        if statement.startswith("INSERT INTO update_job_packages"):
            raise PsycopgError("synthetic package insert failure")

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(
        monkeypatch,
        handler,
    )

    response = client.post(
        f"/api/clients/{CLIENT_ID}/update-jobs",
        json={
            "action": "UPDATE_PACKAGE",
            "packages": ["curl"],
        },
        headers=_write_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "error": "database_unavailable",
    }

    route_connection = _route_connection(
        connections,
        "INSERT INTO update_jobs",
    )

    statements = [
        statement
        for statement, _ in route_connection.statements
    ]

    assert any(
        statement.startswith("INSERT INTO update_jobs")
        for statement in statements
    )
    assert any(
        statement.startswith("INSERT INTO update_job_packages")
        for statement in statements
    )

    assert route_connection.events == [
        "transaction.begin",
        "transaction.rollback",
    ]

    assert not any(
        isinstance(event, tuple) and event[0] == "audit"
        for connection in connections
        for event in connection.events
    )

    assert all(connection.closed for connection in connections)


@pytest.mark.parametrize(
    (
        "failed_statement",
        "fail_occurrence",
        "expected_package_updates",
        "expected_job_updates",
    ),
    [
        ("UPDATE update_job_packages", 2, 2, 0),
        ("UPDATE update_jobs", 1, 2, 1),
        ("INSERT INTO update_history", 1, 2, 1),
    ],
)
def test_result_rolls_back_when_database_write_fails(
    monkeypatch,
    failed_statement,
    fail_occurrence,
    expected_package_updates,
    expected_job_updates,
):
    handler, history_inserts = _result_test_handler(
        fail_on_statement=failed_statement,
        fail_on_statement_occurrence=fail_occurrence,
    )
    client, connections = _make_environment(monkeypatch, handler)

    response = client.post(
        f"/api/update-jobs/{JOB_ID}/result",
        json={
            "status": "success",
            "reboot_required": True,
            "packages": [
                {"package": "package-1", "status": "success"},
                {"package": "package-2", "status": "success"},
            ],
        },
        headers=_agent_headers(),
        base_url=BASE_URL,
    )

    assert response.status_code == 500
    assert sum(
        statement.startswith("UPDATE update_job_packages")
        for statement in handler.attempted_statements
    ) == expected_package_updates

    assert sum(
        statement.startswith("UPDATE update_jobs")
        for statement in handler.attempted_statements
    ) == expected_job_updates

    assert sum(
        statement.startswith(failed_statement)
        for statement in handler.attempted_statements
    ) == fail_occurrence

    assert response.get_json() == {
        "error": "database_unavailable",
    }

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, status, created_at",
    )

    assert route_connection.events == [
        "transaction.begin",
        "transaction.rollback",
    ]

    assert not any(
        isinstance(event, tuple) and event[0] == "audit"
        for event in route_connection.events
    )

    assert not history_inserts
    assert all(item.closed for item in connections)


# Single-job details and update-history read-route tests.


def test_get_update_job_details_returns_job_packages_and_counts(monkeypatch):
    created_at = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 11, 7, 10, 15, tzinfo=timezone.utc)

    def handler(connection, statement, params):
        if statement.startswith("SELECT j.id, j.client_id, c.hostname"):
            assert params == (JOB_ID,)
            assert "JOIN clients c" in statement
            return FakeCursor(one={
                "id": JOB_ID,
                "client_id": CLIENT_ID,
                "hostname": "agent-01",
                "ip": "192.0.2.41",
                "status": "completed",
                "created_at": created_at,
                "started_at": created_at,
                "finished_at": finished_at,
                "reboot_required": True,
            })

        if statement.startswith("SELECT id, package, installed_version"):
            assert params == (JOB_ID,)
            assert "ORDER BY package" in statement
            return FakeCursor(many=[
                {
                    "id": 2,
                    "package": "alpha",
                    "installed_version": "1.0",
                    "target_version": "1.1",
                    "status": "success",
                    "message": None,
                },
                {
                    "id": 1,
                    "package": "beta",
                    "installed_version": "2.0",
                    "target_version": "2.1",
                    "status": "failed",
                    "message": "package manager error",
                },
                {
                    "id": 3,
                    "package": "gamma",
                    "installed_version": "3.0",
                    "target_version": "3.1",
                    "status": "success",
                    "message": None,
                },
            ])

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/update-jobs/{JOB_ID}",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data == {
        "id": JOB_ID,
        "client_id": CLIENT_ID,
        "hostname": "agent-01",
        "ip": "192.0.2.41",
        "status": "completed",
        "created_at": "2026-11-07T10:00:00+00:00",
        "started_at": "2026-11-07T10:00:00+00:00",
        "finished_at": "2026-11-07T10:15:00+00:00",
        "reboot_required": True,
        "packages": [
            {
                "id": 2,
                "package": "alpha",
                "installed_version": "1.0",
                "target_version": "1.1",
                "status": "success",
                "message": None,
            },
            {
                "id": 1,
                "package": "beta",
                "installed_version": "2.0",
                "target_version": "2.1",
                "status": "failed",
                "message": "package manager error",
            },
            {
                "id": 3,
                "package": "gamma",
                "installed_version": "3.0",
                "target_version": "3.1",
                "status": "success",
                "message": None,
            },
        ],
        "package_count": 3,
        "successful_count": 2,
        "failed_count": 1,
    }

    route_connection = _route_connection(
        connections,
        "SELECT j.id, j.client_id, c.hostname",
    )
    assert route_connection.closed
    assert all(connection.closed for connection in connections)


def test_get_update_job_details_returns_not_found_for_unknown_job(
    monkeypatch,
):
    def handler(connection, statement, params):
        assert statement.startswith(
            "SELECT j.id, j.client_id, c.hostname"
        )
        assert params == (JOB_ID,)
        return FakeCursor(one=None)

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/update-jobs/{JOB_ID}",
        base_url=BASE_URL,
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "status": "error",
        "message": "Update job not found",
    }

    route_connection = _route_connection(
        connections,
        "SELECT j.id, j.client_id, c.hostname",
    )
    assert len(route_connection.statements) == 1
    assert route_connection.closed
    assert all(connection.closed for connection in connections)


def test_get_update_job_details_returns_zero_counts_without_packages(
    monkeypatch,
):
    created_at = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)

    def handler(connection, statement, params):
        if statement.startswith("SELECT j.id, j.client_id, c.hostname"):
            assert params == (JOB_ID,)
            return FakeCursor(one={
                "id": JOB_ID,
                "client_id": CLIENT_ID,
                "hostname": "agent-01",
                "ip": "192.0.2.41",
                "status": "pending",
                "created_at": created_at,
                "started_at": None,
                "finished_at": None,
                "reboot_required": False,
            })

        if statement.startswith("SELECT id, package, installed_version"):
            assert params == (JOB_ID,)
            return FakeCursor(many=[])

        raise AssertionError(f"Unexpected SQL: {statement}")

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/update-jobs/{JOB_ID}",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == JOB_ID
    assert data["packages"] == []
    assert data["package_count"] == 0
    assert data["successful_count"] == 0
    assert data["failed_count"] == 0
    assert data["started_at"] is None
    assert data["finished_at"] is None

    route_connection = _route_connection(
        connections,
        "SELECT j.id, j.client_id, c.hostname",
    )
    assert route_connection.closed
    assert all(connection.closed for connection in connections)


def test_get_client_update_history_returns_rows_in_descending_order(
    monkeypatch,
):
    started_at = datetime(2026, 11, 7, 9, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 11, 7, 9, 15, tzinfo=timezone.utc)

    def handler(connection, statement, params):
        assert statement.startswith(
            "SELECT id, client_id, job_id, status"
        )
        assert params == (CLIENT_ID,)
        assert "FROM update_history" in statement
        assert "WHERE client_id = %s" in statement
        assert "ORDER BY id DESC" in statement
        return FakeCursor(many=[
            {
                "id": 102,
                "client_id": CLIENT_ID,
                "job_id": 74,
                "status": "success",
                "package_count": 2,
                "successful_count": 2,
                "failed_count": 0,
                "reboot_required": False,
                "started_at": started_at,
                "finished_at": finished_at,
            },
            {
                "id": 101,
                "client_id": CLIENT_ID,
                "job_id": 73,
                "status": "failed",
                "package_count": 1,
                "successful_count": 0,
                "failed_count": 1,
                "reboot_required": True,
                "started_at": None,
                "finished_at": None,
            },
        ])

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/clients/{CLIENT_ID}/update-history",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == [
        {
            "id": 102,
            "client_id": CLIENT_ID,
            "job_id": 74,
            "status": "success",
            "package_count": 2,
            "successful_count": 2,
            "failed_count": 0,
            "reboot_required": False,
            "started_at": "2026-11-07T09:00:00+00:00",
            "finished_at": "2026-11-07T09:15:00+00:00",
        },
        {
            "id": 101,
            "client_id": CLIENT_ID,
            "job_id": 73,
            "status": "failed",
            "package_count": 1,
            "successful_count": 0,
            "failed_count": 1,
            "reboot_required": True,
            "started_at": None,
            "finished_at": None,
        },
    ]

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, job_id, status",
    )
    assert route_connection.closed
    assert all(connection.closed for connection in connections)


def test_get_client_update_history_returns_empty_list(monkeypatch):
    def handler(connection, statement, params):
        assert statement.startswith(
            "SELECT id, client_id, job_id, status"
        )
        assert params == (CLIENT_ID,)
        return FakeCursor(many=[])

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        f"/api/clients/{CLIENT_ID}/update-history",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == []

    route_connection = _route_connection(
        connections,
        "SELECT id, client_id, job_id, status",
    )
    assert route_connection.closed
    assert all(connection.closed for connection in connections)


def test_get_global_update_history_returns_rows_with_client_details(
    monkeypatch,
):
    started_at = datetime(2026, 11, 7, 8, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 11, 7, 8, 10, tzinfo=timezone.utc)

    def handler(connection, statement, params):
        assert statement.startswith(
            "SELECT h.id, h.client_id, c.hostname, c.ip"
        )
        assert params is None
        assert "JOIN clients c" in statement
        assert "ORDER BY h.id DESC" in statement
        return FakeCursor(many=[
            {
                "id": 202,
                "client_id": CLIENT_ID,
                "hostname": "agent-01",
                "ip": "192.0.2.41",
                "job_id": 82,
                "status": "success",
                "package_count": 3,
                "successful_count": 3,
                "failed_count": 0,
                "reboot_required": False,
                "started_at": started_at,
                "finished_at": finished_at,
            },
            {
                "id": 201,
                "client_id": 42,
                "hostname": "agent-02",
                "ip": "192.0.2.42",
                "job_id": 81,
                "status": "failed",
                "package_count": 2,
                "successful_count": 1,
                "failed_count": 1,
                "reboot_required": True,
                "started_at": None,
                "finished_at": None,
            },
        ])

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        "/api/update-history",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == [
        {
            "id": 202,
            "client_id": CLIENT_ID,
            "hostname": "agent-01",
            "ip": "192.0.2.41",
            "job_id": 82,
            "status": "success",
            "package_count": 3,
            "successful_count": 3,
            "failed_count": 0,
            "reboot_required": False,
            "started_at": "2026-11-07T08:00:00+00:00",
            "finished_at": "2026-11-07T08:10:00+00:00",
        },
        {
            "id": 201,
            "client_id": 42,
            "hostname": "agent-02",
            "ip": "192.0.2.42",
            "job_id": 81,
            "status": "failed",
            "package_count": 2,
            "successful_count": 1,
            "failed_count": 1,
            "reboot_required": True,
            "started_at": None,
            "finished_at": None,
        },
    ]

    route_connection = _route_connection(
        connections,
        "SELECT h.id, h.client_id, c.hostname, c.ip",
    )
    assert route_connection.closed
    assert all(connection.closed for connection in connections)


def test_get_global_update_history_returns_empty_list(monkeypatch):
    def handler(connection, statement, params):
        assert statement.startswith(
            "SELECT h.id, h.client_id, c.hostname, c.ip"
        )
        assert params is None
        return FakeCursor(many=[])

    client, connections = _make_environment(monkeypatch, handler)

    response = client.get(
        "/api/update-history",
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == []

    route_connection = _route_connection(
        connections,
        "SELECT h.id, h.client_id, c.hostname, c.ip",
    )
    assert route_connection.closed
    assert all(connection.closed for connection in connections)
