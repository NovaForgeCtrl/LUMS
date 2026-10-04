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

from server.security import hash_client_token


TEST_TOKEN = "audit12-test-client-token"


def create_job_result_database(db_path):
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
            enabled INTEGER NOT NULL DEFAULT 1,
            client_token_hash TEXT,
            token_revoked_at TEXT
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE update_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            reboot_required INTEGER NOT NULL DEFAULT 0,
            recovery_reason TEXT,
            action TEXT NOT NULL DEFAULT 'UPDATE_PACKAGE'
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE update_job_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            package TEXT NOT NULL,
            installed_version TEXT,
            target_version TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            UNIQUE(job_id, package)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE update_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            package_count INTEGER NOT NULL,
            successful_count INTEGER NOT NULL,
            failed_count INTEGER NOT NULL,
            reboot_required INTEGER NOT NULL DEFAULT 0,
            started_at TEXT,
            finished_at TEXT
        )
        """
    )

    connection.execute(
        """
        INSERT INTO users (
            id,
            username,
            password_hash,
            enabled
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            1,
            "administrator",
            "pytest-password-hash",
            1,
        ),
    )

    connection.execute(
        """
        INSERT INTO clients (
            id,
            hostname,
            enabled,
            client_token_hash
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            1,
            "audit12-client",
            1,
            hash_client_token(TEST_TOKEN),
        ),
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


def create_running_job(
    db_path,
    *,
    client_id=1,
    action="UPDATE_PACKAGE",
    packages=None,
):
    if packages is None:
        packages = []

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        INSERT INTO update_jobs (
            client_id,
            status,
            created_at,
            started_at,
            action
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            client_id,
            "running",
            "2026-10-03T12:00:00+00:00",
            "2026-10-03T12:01:00+00:00",
            action,
        ),
    )

    job_id = connection.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    for package in packages:
        connection.execute(
            """
            INSERT INTO update_job_packages (
                job_id,
                package,
                target_version,
                status
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                job_id,
                package,
                "1.0",
                "pending",
            ),
        )

    connection.commit()
    connection.close()

    return job_id


def client_headers():
    return {
        "Authorization": f"Bearer {TEST_TOKEN}",
    }


@pytest.fixture
def job_result_test_context(monkeypatch, tmp_path):
    from server import app as app_module

    db_path = str(tmp_path / "job-result.db")

    create_job_result_database(db_path)
    configure_test_database(
        monkeypatch,
        app_module,
        db_path,
    )

    return (
        app_module.app.test_client(),
        db_path,
    )


def read_job(db_path, job_id):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    row = connection.execute(
        """
        SELECT
            status,
            action,
            reboot_required,
            finished_at
        FROM update_jobs
        WHERE id = ?
        """,
        (job_id,),
    ).fetchone()

    connection.close()

    return row


def read_packages(db_path, job_id):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    rows = connection.execute(
        """
        SELECT
            package,
            status,
            message
        FROM update_job_packages
        WHERE job_id = ?
        ORDER BY package
        """,
        (job_id,),
    ).fetchall()

    connection.close()

    return rows


def read_history(db_path, job_id):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    row = connection.execute(
        """
        SELECT
            status,
            package_count,
            successful_count,
            failed_count,
            reboot_required
        FROM update_history
        WHERE job_id = ?
        """,
        (job_id,),
    ).fetchone()

    connection.close()

    return row


def test_job_result_success_updates_job_packages_and_history(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=[
            "package-a",
            "package-b",
        ],
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json={
            "status": "success",
            "packages": [
                {
                    "package": "package-a",
                    "status": "success",
                    "message": "installed",
                },
                {
                    "package": "package-b",
                    "status": "success",
                    "message": "updated",
                },
            ],
        },
        headers=client_headers(),
    )

    assert response.status_code == 200

    body = response.get_json()

    assert body["job_status"] == "success"
    assert body["successful_count"] == 2
    assert body["failed_count"] == 0

    job = read_job(db_path, job_id)
    assert job["status"] == "success"
    assert job["finished_at"]

    packages = read_packages(db_path, job_id)

    assert [row["status"] for row in packages] == [
        "success",
        "success",
    ]

    history = read_history(db_path, job_id)

    assert history["status"] == "success"
    assert history["package_count"] == 2
    assert history["successful_count"] == 2
    assert history["failed_count"] == 0


def test_job_result_derives_partial_status(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=[
            "package-a",
            "package-b",
        ],
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json={
            "status": "partial",
            "packages": [
                {
                    "package": "package-a",
                    "status": "success",
                },
                {
                    "package": "package-b",
                    "status": "failed",
                },
            ],
        },
        headers=client_headers(),
    )

    assert response.status_code == 200

    body = response.get_json()

    assert body["job_status"] == "partial"
    assert body["successful_count"] == 1
    assert body["failed_count"] == 1


def test_job_result_derives_failed_status(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=[
            "package-a",
        ],
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json={
            "status": "failed",
            "packages": [
                {
                    "package": "package-a",
                    "status": "failed",
                },
            ],
        },
        headers=client_headers(),
    )

    assert response.status_code == 200

    body = response.get_json()

    assert body["job_status"] == "failed"
    assert body["successful_count"] == 0
    assert body["failed_count"] == 1


@pytest.mark.parametrize(
    "payload",
    [
        {
            "status": "success",
            "packages": [
                {
                    "package": "package-a",
                    "status": "success",
                },
            ],
        },
        {
            "status": "success",
            "packages": [
                {
                    "package": "package-a",
                    "status": "success",
                },
                {
                    "package": "package-a",
                    "status": "success",
                },
            ],
        },
    ],
)
def test_job_result_rejects_invalid_package_sets(
    job_result_test_context,
    payload,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=[
            "package-a",
            "package-b",
        ],
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json=payload,
        headers=client_headers(),
    )

    assert response.status_code == 400

    job = read_job(db_path, job_id)

    assert job["status"] == "running"


def test_job_result_rejects_unexpected_package(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=["expected-package"],
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json={
            "status": "success",
            "packages": [
                {
                    "package": "unexpected-package",
                    "status": "success",
                },
            ],
        },
        headers=client_headers(),
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "package_result_mismatch"

    assert read_job(db_path, job_id)["status"] == "running"


def test_job_result_rejects_status_manipulation(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=["package-a"],
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json={
            "status": "success",
            "packages": [
                {
                    "package": "package-a",
                    "status": "failed",
                },
            ],
        },
        headers=client_headers(),
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "status_mismatch"

    assert read_job(db_path, job_id)["status"] == "running"


def test_job_result_rejects_oversized_message(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=["package-a"],
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json={
            "status": "success",
            "packages": [
                {
                    "package": "package-a",
                    "status": "success",
                    "message": "x" * 4097,
                },
            ],
        },
        headers=client_headers(),
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "package message too long"


def test_job_result_rejects_invalid_message_type(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=["package-a"],
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json={
            "status": "success",
            "packages": [
                {
                    "package": "package-a",
                    "status": "success",
                    "message": 123,
                },
            ],
        },
        headers=client_headers(),
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid package message"


def test_job_result_rejects_too_many_packages(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=[],
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json={
            "status": "success",
            "packages": [
                {
                    "package": f"package-{index}",
                    "status": "success",
                }
                for index in range(101)
            ],
        },
        headers=client_headers(),
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "too_many_package_results"


def test_job_result_rejects_late_result(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=["package-a"],
    )

    connection = sqlite3.connect(db_path)

    connection.execute(
        """
        UPDATE update_jobs
        SET status = 'success'
        WHERE id = ?
        """,
        (job_id,),
    )

    connection.commit()
    connection.close()

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json={
            "status": "success",
            "packages": [
                {
                    "package": "package-a",
                    "status": "success",
                },
            ],
        },
        headers=client_headers(),
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "job_not_running"


def test_job_result_rejects_wrong_client(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        client_id=2,
        packages=["package-a"],
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json={
            "status": "success",
            "packages": [
                {
                    "package": "package-a",
                    "status": "success",
                },
            ],
        },
        headers=client_headers(),
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "client_access_denied"


def test_update_system_result_requires_no_packages(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        action="UPDATE_SYSTEM",
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json={
            "status": "success",
            "reboot_required": True,
            "packages": [],
        },
        headers=client_headers(),
    )

    assert response.status_code == 200

    body = response.get_json()

    assert body["job_status"] == "success"
    assert body["successful_count"] == 0
    assert body["failed_count"] == 0
    assert body["reboot_required"] is True

    job = read_job(db_path, job_id)

    assert job["status"] == "success"
    assert job["reboot_required"] == 1

    history = read_history(db_path, job_id)

    assert history["status"] == "success"
    assert history["package_count"] == 0
    assert history["successful_count"] == 0
    assert history["failed_count"] == 0
    assert history["reboot_required"] == 1


def test_update_system_result_rejects_packages(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        action="UPDATE_SYSTEM",
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/result",
        json={
            "status": "success",
            "packages": [
                {
                    "package": "unexpected-package",
                    "status": "success",
                },
            ],
        },
        headers=client_headers(),
    )

    assert response.status_code == 400
    assert (
        response.get_json()["error"]
        == "system_update_must_not_contain_packages"
    )

    assert read_job(db_path, job_id)["status"] == "running"


def test_checkpoint_success(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=["package-a"],
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/checkpoint",
        json={
            "package": "package-a",
            "status": "success",
            "message": "checkpoint completed",
        },
        headers=client_headers(),
    )

    assert response.status_code == 200

    assert response.get_json() == {
        "status": "checkpointed",
        "job_id": job_id,
        "package": "package-a",
        "package_status": "success",
    }

    row = read_packages(db_path, job_id)[0]

    assert row["status"] == "success"
    assert row["message"] == "checkpoint completed"


def test_checkpoint_rejects_invalid_message_type(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=["package-a"],
    )

    response = client.post(
        f"/api/update-jobs/{job_id}/checkpoint",
        json={
            "package": "package-a",
            "status": "success",
            "message": 123,
        },
        headers=client_headers(),
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_message"

    assert read_packages(db_path, job_id)[0]["status"] == "pending"


def test_checkpoint_rejects_non_running_job(
    job_result_test_context,
):
    client, db_path = job_result_test_context

    job_id = create_running_job(
        db_path,
        packages=["package-a"],
    )

    connection = sqlite3.connect(db_path)

    connection.execute(
        """
        UPDATE update_jobs
        SET status = 'success'
        WHERE id = ?
        """,
        (job_id,),
    )

    connection.commit()
    connection.close()

    response = client.post(
        f"/api/update-jobs/{job_id}/checkpoint",
        json={
            "package": "package-a",
            "status": "success",
        },
        headers=client_headers(),
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "job_not_running"
