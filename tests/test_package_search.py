import os
import sqlite3
import sys
from pathlib import Path

import pytest

os.environ.setdefault(
    "LUMS_SECRET_KEY",
    "pytest-only-test-secret",
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = PROJECT_ROOT / "server"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from server.security import (
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    hash_client_token,
)


def create_package_search_database(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'administrator'
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY,
            hostname TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE package_search_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            result_json TEXT,
            error_message TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id INTEGER,
            action TEXT NOT NULL,
            target TEXT,
            result TEXT NOT NULL,
            details TEXT
        )
        """
    )

    connection.executemany(
        """
        INSERT INTO users (
            id,
            username,
            password_hash,
            enabled,
            role
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                1,
                "administrator",
                "pytest-password-hash",
                1,
                ROLE_ADMINISTRATOR,
            ),
            (
                2,
                "operator",
                "pytest-password-hash",
                1,
                ROLE_OPERATOR,
            ),
            (
                3,
                "viewer",
                "pytest-password-hash",
                1,
                ROLE_VIEWER,
            ),
        ],
    )

    connection.executemany(
        """
        INSERT INTO clients (
            id,
            hostname,
            enabled
        )
        VALUES (?, ?, ?)
        """,
        [
            (1, "debiancontainer", 1),
            (2, "disabled-client", 0),
        ],
    )

    connection.commit()
    connection.close()


def configure_test_database(monkeypatch, app_module, db_path):
    def get_test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

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


def login_as(client, user_id, username):
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["username"] = username
        session.permanent = True


def get_csrf_token(client):
    with client.session_transaction() as session:
        token = session.get("csrf_token")

    if token is None:
        raise AssertionError("CSRF token was not created")

    return token


@pytest.mark.parametrize(
    "user_id,username,role",
    [
        (1, "administrator", ROLE_ADMINISTRATOR),
        (2, "operator", ROLE_OPERATOR),
    ],
)
def test_package_search_allows_admin_and_operator(
    monkeypatch,
    tmp_path,
    user_id,
    username,
    role,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search.db")

    create_package_search_database(db_path)
    configure_test_database(
        monkeypatch,
        app_module,
        db_path,
    )

    client = app_module.app.test_client()

    login_as(client, user_id, username)

    with client.session_transaction() as session:
        session["csrf_token"] = "pytest-csrf-token"

    response = client.post(
        "/api/clients/1/package-search",
        json={
            "query": "nginx",
        },
        headers={
            "X-CSRF-Token": "pytest-csrf-token",
        },
    )

    assert response.status_code == 202

    assert response.get_json() == {
        "status": "pending",
        "search_id": 1,
        "client_id": 1,
        "query": "nginx",
    }

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    row = connection.execute(
        """
        SELECT
            client_id,
            query,
            status,
            created_at
        FROM package_search_requests
        WHERE id = 1
        """
    ).fetchone()

    assert row is not None
    assert row["client_id"] == 1
    assert row["query"] == "nginx"
    assert row["status"] == "pending"
    assert row["created_at"]

    connection.close()


def test_package_search_rejects_viewer(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-viewer.db")

    create_package_search_database(db_path)
    configure_test_database(
        monkeypatch,
        app_module,
        db_path,
    )

    client = app_module.app.test_client()

    login_as(
        client,
        3,
        "viewer",
    )

    with client.session_transaction() as session:
        session["csrf_token"] = "pytest-csrf-token"

    response = client.post(
        "/api/clients/1/package-search",
        json={
            "query": "nginx",
        },
        headers={
            "X-CSRF-Token": "pytest-csrf-token",
        },
    )

    assert response.status_code == 403

    connection = sqlite3.connect(db_path)

    count = connection.execute(
        """
        SELECT COUNT(*)
        FROM package_search_requests
        """
    ).fetchone()[0]

    assert count == 0

    connection.close()


def test_package_search_requires_csrf(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-csrf.db")

    create_package_search_database(db_path)
    configure_test_database(
        monkeypatch,
        app_module,
        db_path,
    )

    client = app_module.app.test_client()

    login_as(
        client,
        1,
        "administrator",
    )

    response = client.post(
        "/api/clients/1/package-search",
        json={
            "query": "nginx",
        },
    )

    assert response.status_code == 400

    connection = sqlite3.connect(db_path)

    count = connection.execute(
        """
        SELECT COUNT(*)
        FROM package_search_requests
        """
    ).fetchone()[0]

    assert count == 0

    connection.close()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"query": ""},
        {"query": "   "},
        {"query": "x" * 129},
        {"query": None},
        {"query": 123},
    ],
)
def test_package_search_rejects_invalid_query(
    monkeypatch,
    tmp_path,
    payload,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-invalid.db")

    create_package_search_database(db_path)
    configure_test_database(
        monkeypatch,
        app_module,
        db_path,
    )

    client = app_module.app.test_client()

    login_as(
        client,
        1,
        "administrator",
    )

    with client.session_transaction() as session:
        session["csrf_token"] = "pytest-csrf-token"

    response = client.post(
        "/api/clients/1/package-search",
        json=payload,
        headers={
            "X-CSRF-Token": "pytest-csrf-token",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_package_search_query",
    }

    connection = sqlite3.connect(db_path)

    count = connection.execute(
        """
        SELECT COUNT(*)
        FROM package_search_requests
        """
    ).fetchone()[0]

    assert count == 0

    connection.close()


def test_package_search_rejects_invalid_json(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-json.db")

    create_package_search_database(db_path)
    configure_test_database(
        monkeypatch,
        app_module,
        db_path,
    )

    client = app_module.app.test_client()

    login_as(
        client,
        1,
        "administrator",
    )

    with client.session_transaction() as session:
        session["csrf_token"] = "pytest-csrf-token"

    response = client.post(
        "/api/clients/1/package-search",
        data="{invalid-json",
        content_type="application/json",
        headers={
            "X-CSRF-Token": "pytest-csrf-token",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_request",
    }


def test_package_search_rejects_unknown_client(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-unknown.db")

    create_package_search_database(db_path)
    configure_test_database(
        monkeypatch,
        app_module,
        db_path,
    )

    client = app_module.app.test_client()

    login_as(
        client,
        1,
        "administrator",
    )

    with client.session_transaction() as session:
        session["csrf_token"] = "pytest-csrf-token"

    response = client.post(
        "/api/clients/999/package-search",
        json={
            "query": "nginx",
        },
        headers={
            "X-CSRF-Token": "pytest-csrf-token",
        },
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "error": "client_not_found",
    }


def test_package_search_rejects_disabled_client(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-disabled.db")

    create_package_search_database(db_path)
    configure_test_database(
        monkeypatch,
        app_module,
        db_path,
    )

    client = app_module.app.test_client()

    login_as(
        client,
        1,
        "administrator",
    )

    with client.session_transaction() as session:
        session["csrf_token"] = "pytest-csrf-token"

    response = client.post(
        "/api/clients/2/package-search",
        json={
            "query": "nginx",
        },
        headers={
            "X-CSRF-Token": "pytest-csrf-token",
        },
    )

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "client_disabled",
    }

    connection = sqlite3.connect(db_path)

    count = connection.execute(
        """
        SELECT COUNT(*)
        FROM package_search_requests
        """
    ).fetchone()[0]

    assert count == 0

    connection.close()


def test_package_search_strips_query_whitespace(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-whitespace.db")

    create_package_search_database(db_path)
    configure_test_database(
        monkeypatch,
        app_module,
        db_path,
    )

    client = app_module.app.test_client()

    login_as(
        client,
        1,
        "administrator",
    )

    with client.session_transaction() as session:
        session["csrf_token"] = "pytest-csrf-token"

    response = client.post(
        "/api/clients/1/package-search",
        json={
            "query": "  nginx  ",
        },
        headers={
            "X-CSRF-Token": "pytest-csrf-token",
        },
    )

    assert response.status_code == 202

    assert response.get_json()["query"] == "nginx"

    connection = sqlite3.connect(db_path)
    row = connection.execute(
        """
        SELECT query
        FROM package_search_requests
        WHERE id = 1
        """
    ).fetchone()

    assert row[0] == "nginx"

    connection.close()


def create_client_auth_database(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY,
            hostname TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            client_token_hash TEXT,
            token_revoked_at TEXT
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE package_search_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            result_json TEXT,
            error_message TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
        """
    )

    connection.execute(
        """
        INSERT INTO clients (
            id,
            hostname,
            enabled,
            client_token_hash,
            token_revoked_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            1,
            "debiancontainer",
            1,
            None,
            None,
        ),
    )

    connection.commit()
    connection.close()


def configure_client_auth(monkeypatch, app_module, db_path, token):
    connection = sqlite3.connect(db_path)

    connection.execute(
        """
        UPDATE clients
        SET client_token_hash = ?
        WHERE id = 1
        """,
        (
            hash_client_token(token),
        ),
    )

    connection.commit()
    connection.close()

    def get_test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

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

def insert_package_search(
    db_path,
    client_id=1,
    query="nginx",
    status="pending",
):
    connection = sqlite3.connect(db_path)

    cursor = connection.execute(
        """
        INSERT INTO package_search_requests (
            client_id,
            query,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            client_id,
            query,
            status,
            "2026-09-24T12:00:00+00:00",
        ),
    )

    search_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return search_id


def test_pending_package_search_claims_search(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-agent.db")

    create_client_auth_database(db_path)

    search_id = insert_package_search(
        db_path,
        client_id=1,
        query="nginx",
    )

    configure_client_auth(
        monkeypatch,
        app_module,
        db_path,
        token="pytest-client-token",
    )

    client = app_module.app.test_client()

    response = client.get(
        "/api/clients/1/package-search/pending",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "running"
    assert data["search_id"] == search_id
    assert data["client_id"] == 1
    assert data["query"] == "nginx"
    assert data["created_at"] == "2026-09-24T12:00:00+00:00"
    assert data["started_at"]


def test_pending_package_search_rejects_wrong_client(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-agent.db")

    create_client_auth_database(db_path)

    insert_package_search(
        db_path,
        client_id=1,
        query="nginx",
    )

    configure_client_auth(
        monkeypatch,
        app_module,
        db_path,
        token="pytest-client-token",
    )

    client = app_module.app.test_client()

    response = client.get(
        "/api/clients/2/package-search/pending",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert response.status_code == 403

    assert response.get_json() == {
        "error": "client_access_denied",
    }


def test_pending_package_search_returns_204_when_empty(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-agent.db")

    create_client_auth_database(db_path)

    configure_client_auth(
        monkeypatch,
        app_module,
        db_path,
        token="pytest-client-token",
    )

    client = app_module.app.test_client()

    response = client.get(
        "/api/clients/1/package-search/pending",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert response.status_code == 204


def test_pending_package_search_cannot_be_claimed_twice(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-agent.db")

    create_client_auth_database(db_path)

    search_id = insert_package_search(
        db_path,
        client_id=1,
        query="curl",
    )

    configure_client_auth(
        monkeypatch,
        app_module,
        db_path,
        token="pytest-client-token",
    )

    client = app_module.app.test_client()

    first_response = client.get(
        "/api/clients/1/package-search/pending",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert first_response.status_code == 200
    assert first_response.get_json()["search_id"] == search_id

    second_response = client.get(
        "/api/clients/1/package-search/pending",
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert second_response.status_code == 204

    connection = sqlite3.connect(db_path)
    row = connection.execute(
        """
        SELECT
            status,
            started_at
        FROM package_search_requests
        WHERE id = ?
        """,
        (search_id,),
    ).fetchone()
    connection.close()

    assert row[0] == "running"
    assert row[1]


def test_package_search_result_completed(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-result.db")

    create_client_auth_database(db_path)

    search_id = insert_package_search(
        db_path,
        client_id=1,
        query="nginx",
        status="running",
    )

    configure_client_auth(
        monkeypatch,
        app_module,
        db_path,
        token="pytest-client-token",
    )

    client = app_module.app.test_client()

    response = client.post(
        f"/api/package-search/{search_id}/result",
        json={
            "status": "completed",
            "results": [
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
            ],
        },
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "completed"
    assert data["search_id"] == search_id
    assert data["result_count"] == 2
    assert data["finished_at"]

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    row = connection.execute(
        """
        SELECT
            status,
            finished_at,
            result_json,
            error_message
        FROM package_search_requests
        WHERE id = ?
        """,
        (search_id,),
    ).fetchone()

    connection.close()

    assert row["status"] == "completed"
    assert row["finished_at"]
    assert row["error_message"] is None

    stored_results = __import__("json").loads(
        row["result_json"]
    )

    assert stored_results == [
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


def test_package_search_result_failed(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-result.db")

    create_client_auth_database(db_path)

    search_id = insert_package_search(
        db_path,
        client_id=1,
        query="nginx",
        status="running",
    )

    configure_client_auth(
        monkeypatch,
        app_module,
        db_path,
        token="pytest-client-token",
    )

    client = app_module.app.test_client()

    response = client.post(
        f"/api/package-search/{search_id}/result",
        json={
            "status": "failed",
            "error_message": "apt-cache search failed",
        },
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "failed"
    assert data["search_id"] == search_id
    assert data["result_count"] == 0
    assert data["finished_at"]

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    row = connection.execute(
        """
        SELECT
            status,
            finished_at,
            result_json,
            error_message
        FROM package_search_requests
        WHERE id = ?
        """,
        (search_id,),
    ).fetchone()

    connection.close()

    assert row["status"] == "failed"
    assert row["finished_at"]
    assert row["result_json"] == "[]"
    assert row["error_message"] == "apt-cache search failed"


def test_package_search_result_rejects_too_many_results(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-result.db")

    create_client_auth_database(db_path)

    search_id = insert_package_search(
        db_path,
        client_id=1,
        query="nginx",
        status="running",
    )

    configure_client_auth(
        monkeypatch,
        app_module,
        db_path,
        token="pytest-client-token",
    )

    client = app_module.app.test_client()

    results = [
        {
            "package": f"package-{index}",
            "version": "1.0",
            "description": "test",
        }
        for index in range(51)
    ]

    response = client.post(
        f"/api/package-search/{search_id}/result",
        json={
            "status": "completed",
            "results": results,
        },
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert response.status_code == 400

    assert response.get_json() == {
        "error": "too many results",
    }


def test_package_search_result_rejects_invalid_package(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-result.db")

    create_client_auth_database(db_path)

    search_id = insert_package_search(
        db_path,
        client_id=1,
        query="nginx",
        status="running",
    )

    configure_client_auth(
        monkeypatch,
        app_module,
        db_path,
        token="pytest-client-token",
    )

    client = app_module.app.test_client()

    response = client.post(
        f"/api/package-search/{search_id}/result",
        json={
            "status": "completed",
            "results": [
                {
                    "package": "nginx;id",
                    "version": "1.0",
                    "description": "invalid",
                },
            ],
        },
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert response.status_code == 400

    assert response.get_json() == {
        "error": "invalid package",
    }


def test_package_search_result_rejects_wrong_client(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-result.db")

    create_client_auth_database(db_path)

    search_id = insert_package_search(
        db_path,
        client_id=1,
        query="nginx",
        status="running",
    )

    configure_client_auth(
        monkeypatch,
        app_module,
        db_path,
        token="pytest-client-token",
    )

    client = app_module.app.test_client()

    response = client.post(
        f"/api/package-search/{search_id}/result",
        json={
            "status": "completed",
            "results": [],
        },
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert response.status_code == 200

    assert response.get_json()["status"] == "completed"


def test_package_search_result_not_found(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-result.db")

    create_client_auth_database(db_path)

    configure_client_auth(
        monkeypatch,
        app_module,
        db_path,
        token="pytest-client-token",
    )

    client = app_module.app.test_client()

    response = client.post(
        "/api/package-search/999/result",
        json={
            "status": "completed",
            "results": [],
        },
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert response.status_code == 404

    assert response.get_json() == {
        "error": "search_not_found",
    }


def test_package_search_result_rejects_non_running_search(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-result.db")

    create_client_auth_database(db_path)

    search_id = insert_package_search(
        db_path,
        client_id=1,
        query="nginx",
        status="completed",
    )

    configure_client_auth(
        monkeypatch,
        app_module,
        db_path,
        token="pytest-client-token",
    )

    client = app_module.app.test_client()

    response = client.post(
        f"/api/package-search/{search_id}/result",
        json={
            "status": "completed",
            "results": [],
        },
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert response.status_code == 409

    assert response.get_json() == {
        "error": "search_not_running",
        "search_id": search_id,
        "search_status": "completed",
    }


def test_package_search_result_cannot_be_submitted_twice(
    monkeypatch,
    tmp_path,
):
    from server import app as app_module

    db_path = str(tmp_path / "package-search-result.db")

    create_client_auth_database(db_path)

    search_id = insert_package_search(
        db_path,
        client_id=1,
        query="curl",
        status="running",
    )

    configure_client_auth(
        monkeypatch,
        app_module,
        db_path,
        token="pytest-client-token",
    )

    client = app_module.app.test_client()

    first_response = client.post(
        f"/api/package-search/{search_id}/result",
        json={
            "status": "completed",
            "results": [
                {
                    "package": "curl",
                    "version": "8.22.0-1",
                    "description": "command line tool",
                },
            ],
        },
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/package-search/{search_id}/result",
        json={
            "status": "completed",
            "results": [],
        },
        headers={
            "Authorization": "Bearer pytest-client-token",
        },
    )

    assert second_response.status_code == 409

    assert second_response.get_json() == {
        "error": "search_not_running",
        "search_id": search_id,
        "search_status": "completed",
    }
