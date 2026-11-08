"""Real PostgreSQL integration tests for the pending update-job agent API."""

import secrets
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from postgres_test_support import require_test_database_url, run_cleanup
from server.migration_runner import run_migrations
from server.migrations import MIGRATIONS
from server.postgres_app import create_postgres_app


BASE_URL = "https://localhost"


def _open_schema_connection(database_url, schema_name, application_name):
    connection = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=5,
        application_name=application_name,
    )
    try:
        connection.execute(
            sql.SQL("SET search_path TO {}").format(
                sql.Identifier(schema_name)
            )
        )
    except BaseException:
        run_cleanup((
            "close connection after search_path failure",
            connection.close,
        ))
        raise

    return connection


@pytest.fixture
def postgres_update_jobs_api_environment():
    database_url = require_test_database_url()

    admin = psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=5,
        application_name="lums-update-jobs-api-test-setup",
    )

    schema_name = f"lums_update_jobs_api_{uuid4().hex}"
    schema_created = False
    setup = None

    try:
        identity = admin.execute(
            "SELECT current_database(), current_user"
        ).fetchone()

        if (
            identity["current_database"] != "lums_integration"
            or identity["current_user"] != "lums_pg_bootstrap"
        ):
            pytest.fail(
                "Refusing update-job API tests outside the dedicated "
                "lums_integration database and lums_pg_bootstrap role."
            )

        admin.execute(
            sql.SQL("CREATE SCHEMA {}").format(
                sql.Identifier(schema_name)
            )
        )
        schema_created = True

        setup = _open_schema_connection(
            database_url,
            schema_name,
            "lums-update-jobs-api-migrations",
        )
        run_migrations(setup, MIGRATIONS)

        suffix = uuid4().hex[:10]
        admin_name = f"update-jobs-admin-{suffix}"
        created_at = datetime.now(timezone.utc).isoformat()

        user_row = setup.execute(
            """
            INSERT INTO users (
                username, password_hash, created_at, role
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (
                admin_name,
                "not-used-by-session-integration-test",
                created_at,
                "administrator",
            ),
        ).fetchone()

        role_row = setup.execute(
            "SELECT id FROM roles WHERE role_key = %s",
            ("system-administrator",),
        ).fetchone()

        if role_row is None:
            raise RuntimeError(
                "Missing seeded role: system-administrator"
            )

        setup.execute(
            """
            INSERT INTO user_roles (
                user_id, role_id, assigned_at, assigned_by
            )
            VALUES (%s, %s, %s, NULL)
            """,
            (user_row["id"], role_row["id"], created_at),
        )

        def connection_factory():
            return _open_schema_connection(
                database_url,
                schema_name,
                "lums-update-jobs-api-request",
            )

        app = create_postgres_app({
            "SECRET_KEY": "test-only-update-jobs-integration-secret",
            "TESTING": True,
            "LUMS_POSTGRES_GET_CONNECTION": connection_factory,
        })

        yield {
            "client": app.test_client(),
            "connection_factory": connection_factory,
            "admin_id": user_row["id"],
            "admin_name": admin_name,
            "schema_name": schema_name,
        }

    finally:
        run_cleanup(
            (
                "close setup connection",
                lambda: setup.close() if setup is not None else None,
            ),
            (
                "drop test schema",
                lambda: admin.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema_name)
                    )
                ) if schema_created else None,
            ),
            ("close admin connection", admin.close),
        )


def _login_admin(environment):
    client = environment["client"]

    with client.session_transaction(base_url=BASE_URL) as flask_session:
        flask_session.clear()
        flask_session.update({
            "user_id": int(environment["admin_id"]),
            "username": environment["admin_name"],
            "csrf_token": secrets.token_urlsafe(32),
        })
        flask_session.permanent = True
        csrf_token = flask_session["csrf_token"]

    return {"X-CSRF-Token": csrf_token}


def _create_agent(environment, hostname, ip="192.0.2.41"):
    response = environment["client"].post(
        "/api/clients",
        json={
            "hostname": hostname,
            "ip": ip,
            "os": "Debian GNU/Linux",
            "kernel": "6.1.0",
            "architecture": "x86_64",
            "agent_version": "1.0.0",
        },
        headers=_login_admin(environment),
        base_url=BASE_URL,
    )

    assert response.status_code == 201, response.get_json()
    data = response.get_json()

    return {
        "id": data["client"]["id"],
        "token": data["token"],
    }


def _insert_pending_job(
    environment,
    client_id,
    created_at,
    packages=(),
    reboot_required=False,
    action="UPDATE_PACKAGE",
):
    connection = environment["connection_factory"]()

    try:
        job = connection.execute(
            """
            INSERT INTO update_jobs (
                client_id,
                status,
                created_at,
                reboot_required,
                action
            )
            VALUES (%s, 'pending', %s, %s, %s)
            RETURNING id
            """,
            (
                client_id,
                created_at,
                reboot_required,
                action,
            ),
        ).fetchone()

        for package in packages:
            connection.execute(
                """
                INSERT INTO update_job_packages (
                    job_id,
                    package,
                    installed_version,
                    target_version,
                    status
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    job["id"],
                    package["package"],
                    package["installed_version"],
                    package["target_version"],
                    package["status"],
                ),
            )

        return job["id"]

    finally:
        run_cleanup((
            "close update-job test connection",
            connection.close,
        ))


def _pending_request(environment, agent, client_id=None):
    requested_id = (
        agent["id"] if client_id is None else client_id
    )

    return environment["client"].get(
        f"/api/clients/{requested_id}/update-jobs/pending",
        headers={
            "Authorization": f"Bearer {agent['token']}",
        },
        base_url=BASE_URL,
    )


def test_pending_job_returns_job_and_packages(
    postgres_update_jobs_api_environment,
):
    environment = postgres_update_jobs_api_environment
    agent = _create_agent(environment, "pending-agent-01")
    created_at = datetime(2026, 11, 7, 10, 30, tzinfo=timezone.utc)

    job_id = _insert_pending_job(
        environment,
        agent["id"],
        created_at,
        packages=(
            {
                "package": "zlib1g",
                "installed_version": "1.2.13",
                "target_version": "1.3.1",
                "status": "pending",
            },
            {
                "package": "curl",
                "installed_version": "8.0.0",
                "target_version": "8.1.0",
                "status": "pending",
            },
        ),
        reboot_required=True,
    )

    response = _pending_request(environment, agent)

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "pending",
        "job_id": job_id,
        "client_id": agent["id"],
        "created_at": created_at.isoformat(),
        "action": "UPDATE_PACKAGE",
        "reboot_required": True,
        "packages": [
            {
                "package": "zlib1g",
                "installed_version": "1.2.13",
                "target_version": "1.3.1",
                "status": "pending",
            },
            {
                "package": "curl",
                "installed_version": "8.0.0",
                "target_version": "8.1.0",
                "status": "pending",
            },
        ],
    }


def test_pending_job_returns_oldest_pending_job(
    postgres_update_jobs_api_environment,
):
    environment = postgres_update_jobs_api_environment
    agent = _create_agent(environment, "pending-agent-oldest")

    oldest_id = _insert_pending_job(
        environment,
        agent["id"],
        datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc),
    )
    newer_id = _insert_pending_job(
        environment,
        agent["id"],
        datetime(2026, 11, 7, 11, 0, tzinfo=timezone.utc),
    )

    assert oldest_id < newer_id

    response = _pending_request(environment, agent)

    assert response.status_code == 200
    assert response.get_json()["job_id"] == oldest_id


def test_pending_job_returns_no_content_when_empty(
    postgres_update_jobs_api_environment,
):
    environment = postgres_update_jobs_api_environment
    agent = _create_agent(environment, "pending-agent-empty")

    response = _pending_request(environment, agent)

    assert response.status_code == 204


def test_pending_job_rejects_another_clients_id(
    postgres_update_jobs_api_environment,
):
    environment = postgres_update_jobs_api_environment
    agent_a = _create_agent(environment, "pending-agent-owner", "192.0.2.41")
    agent_b = _create_agent(environment, "pending-agent-foreign", "192.0.2.42")

    foreign_job_id = _insert_pending_job(
        environment,
        agent_b["id"],
        datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc),
    )

    response = _pending_request(
        environment,
        agent_a,
        client_id=agent_b["id"],
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "client_access_denied",
    }
    assert str(foreign_job_id) not in response.get_data(as_text=True)

# Read-only update-job and update-history API integration tests.


def _insert_update_history(
    environment,
    client_id,
    job_id,
    status,
    package_count,
    successful_count,
    failed_count,
    started_at,
    finished_at,
    reboot_required=False,
):
    connection = environment["connection_factory"]()

    try:
        row = connection.execute(
            """
            INSERT INTO update_history (
                client_id,
                job_id,
                status,
                package_count,
                successful_count,
                failed_count,
                reboot_required,
                started_at,
                finished_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                client_id,
                job_id,
                status,
                package_count,
                successful_count,
                failed_count,
                reboot_required,
                started_at,
                finished_at,
            ),
        ).fetchone()

        return row["id"]

    finally:
        run_cleanup((
            "close update-history test connection",
            connection.close,
        ))


def test_update_job_details_returns_job_packages_and_counts(
    postgres_update_jobs_api_environment,
):
    environment = postgres_update_jobs_api_environment
    agent = _create_agent(
        environment,
        "job-details-agent",
    )

    created_at = datetime(
        2026, 11, 7, 10, 0, tzinfo=timezone.utc
    )
    started_at = datetime(
        2026, 11, 7, 10, 5, tzinfo=timezone.utc
    )
    finished_at = datetime(
        2026, 11, 7, 10, 10, tzinfo=timezone.utc
    )

    job_id = _insert_pending_job(
        environment,
        agent["id"],
        created_at,
        reboot_required=True,
    )

    connection = environment["connection_factory"]()

    try:
        connection.execute(
            """
            UPDATE update_jobs
            SET status = 'completed',
                started_at = %s,
                finished_at = %s
            WHERE id = %s
            """,
            (started_at, finished_at, job_id),
        )

        packages = (
            ("zlib1g", "1.2.13", "1.3.1", "success", "Updated"),
            ("curl", "8.0.0", "8.1.0", "failed", "Install failed"),
            ("bash", "5.2.0", "5.2.1", "success", None),
        )

        for package, installed, target, status, message in packages:
            connection.execute(
                """
                INSERT INTO update_job_packages (
                    job_id,
                    package,
                    installed_version,
                    target_version,
                    status,
                    message
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    job_id,
                    package,
                    installed,
                    target,
                    status,
                    message,
                ),
            )
    finally:
        run_cleanup((
            "close job-details setup connection",
            connection.close,
        ))

    headers = _login_admin(environment)
    response = environment["client"].get(
        f"/api/update-jobs/{job_id}",
        headers=headers,
        base_url=BASE_URL,
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["id"] == job_id
    assert data["client_id"] == agent["id"]
    assert data["hostname"] == "job-details-agent"
    assert data["ip"] == "192.0.2.41"
    assert data["status"] == "completed"
    assert data["created_at"] == created_at.isoformat()
    assert data["started_at"] == started_at.isoformat()
    assert data["finished_at"] == finished_at.isoformat()
    assert data["reboot_required"] is True

    assert [package["package"] for package in data["packages"]] == [
        "bash",
        "curl",
        "zlib1g",
    ]

    assert data["package_count"] == 3
    assert data["successful_count"] == 2
    assert data["failed_count"] == 1

    assert data["packages"] == [
        {
            "id": data["packages"][0]["id"],
            "package": "bash",
            "installed_version": "5.2.0",
            "target_version": "5.2.1",
            "status": "success",
            "message": None,
        },
        {
            "id": data["packages"][1]["id"],
            "package": "curl",
            "installed_version": "8.0.0",
            "target_version": "8.1.0",
            "status": "failed",
            "message": "Install failed",
        },
        {
            "id": data["packages"][2]["id"],
            "package": "zlib1g",
            "installed_version": "1.2.13",
            "target_version": "1.3.1",
            "status": "success",
            "message": "Updated",
        },
    ]


def test_update_job_details_returns_404_for_unknown_job(
    postgres_update_jobs_api_environment,
):
    environment = postgres_update_jobs_api_environment
    headers = _login_admin(environment)

    response = environment["client"].get(
        "/api/update-jobs/999999999",
        headers=headers,
        base_url=BASE_URL,
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "status": "error",
        "message": "Update job not found",
    }


def test_client_update_history_returns_newest_first(
    postgres_update_jobs_api_environment,
):
    environment = postgres_update_jobs_api_environment
    agent = _create_agent(
        environment,
        "client-history-agent",
    )

    first_job = _insert_pending_job(
        environment,
        agent["id"],
        datetime(2026, 11, 7, 8, 0, tzinfo=timezone.utc),
    )
    second_job = _insert_pending_job(
        environment,
        agent["id"],
        datetime(2026, 11, 7, 9, 0, tzinfo=timezone.utc),
    )

    first_started = datetime(
        2026, 11, 7, 8, 1, tzinfo=timezone.utc
    )
    first_finished = datetime(
        2026, 11, 7, 8, 5, tzinfo=timezone.utc
    )
    second_started = datetime(
        2026, 11, 7, 9, 1, tzinfo=timezone.utc
    )
    second_finished = datetime(
        2026, 11, 7, 9, 5, tzinfo=timezone.utc
    )

    first_history_id = _insert_update_history(
        environment,
        agent["id"],
        first_job,
        "completed",
        4,
        4,
        0,
        first_started,
        first_finished,
    )
    second_history_id = _insert_update_history(
        environment,
        agent["id"],
        second_job,
        "completed",
        3,
        2,
        1,
        second_started,
        second_finished,
        reboot_required=True,
    )

    response = environment["client"].get(
        f"/api/clients/{agent['id']}/update-history",
        headers=_login_admin(environment),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()

    assert [row["id"] for row in data] == [
        second_history_id,
        first_history_id,
    ]
    assert [row["job_id"] for row in data] == [
        second_job,
        first_job,
    ]

    assert data[0] == {
        "id": second_history_id,
        "client_id": agent["id"],
        "job_id": second_job,
        "status": "completed",
        "package_count": 3,
        "successful_count": 2,
        "failed_count": 1,
        "reboot_required": True,
        "started_at": second_started.isoformat(),
        "finished_at": second_finished.isoformat(),
    }


def test_client_update_history_returns_empty_list(
    postgres_update_jobs_api_environment,
):
    environment = postgres_update_jobs_api_environment
    agent = _create_agent(
        environment,
        "client-history-empty-agent",
    )

    response = environment["client"].get(
        f"/api/clients/{agent['id']}/update-history",
        headers=_login_admin(environment),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == []


def test_update_history_returns_all_clients_newest_first(
    postgres_update_jobs_api_environment,
):
    environment = postgres_update_jobs_api_environment

    agent_a = _create_agent(
        environment,
        "global-history-agent-a",
        "192.0.2.41",
    )
    agent_b = _create_agent(
        environment,
        "global-history-agent-b",
        "192.0.2.42",
    )

    job_a = _insert_pending_job(
        environment,
        agent_a["id"],
        datetime(2026, 11, 7, 8, 0, tzinfo=timezone.utc),
    )
    job_b = _insert_pending_job(
        environment,
        agent_b["id"],
        datetime(2026, 11, 7, 9, 0, tzinfo=timezone.utc),
    )

    started_a = datetime(
        2026, 11, 7, 8, 1, tzinfo=timezone.utc
    )
    finished_a = datetime(
        2026, 11, 7, 8, 5, tzinfo=timezone.utc
    )
    started_b = datetime(
        2026, 11, 7, 9, 1, tzinfo=timezone.utc
    )
    finished_b = datetime(
        2026, 11, 7, 9, 5, tzinfo=timezone.utc
    )

    history_a = _insert_update_history(
        environment,
        agent_a["id"],
        job_a,
        "completed",
        2,
        2,
        0,
        started_a,
        finished_a,
    )
    history_b = _insert_update_history(
        environment,
        agent_b["id"],
        job_b,
        "failed",
        5,
        3,
        2,
        started_b,
        finished_b,
        reboot_required=True,
    )

    response = environment["client"].get(
        "/api/update-history",
        headers=_login_admin(environment),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    data = response.get_json()

    assert [row["id"] for row in data] == [
        history_b,
        history_a,
    ]

    assert data[0] == {
        "id": history_b,
        "client_id": agent_b["id"],
        "hostname": "global-history-agent-b",
        "ip": "192.0.2.42",
        "job_id": job_b,
        "status": "failed",
        "package_count": 5,
        "successful_count": 3,
        "failed_count": 2,
        "reboot_required": True,
        "started_at": started_b.isoformat(),
        "finished_at": finished_b.isoformat(),
    }

    assert data[1]["client_id"] == agent_a["id"]
    assert data[1]["hostname"] == "global-history-agent-a"
    assert data[1]["ip"] == "192.0.2.41"


def test_update_history_returns_empty_list(
    postgres_update_jobs_api_environment,
):
    environment = postgres_update_jobs_api_environment

    response = environment["client"].get(
        "/api/update-history",
        headers=_login_admin(environment),
        base_url=BASE_URL,
    )

    assert response.status_code == 200
    assert response.get_json() == []

