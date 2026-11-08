"""PostgreSQL-native update-job and update-history routes for LUMS."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app, jsonify, request

if __package__:
    from .db_errors import DatabaseDriverError
    from .db_transactions import transaction
    from .postgres_audit import audit_log
    from .postgres_clients import _lock_authenticated_client
    from .postgres_flask_security import (
        authenticated_client,
        client_auth_required,
        csrf_required,
        current_user_id,
        login_required,
        role_required,
    )
    from .security import (
        is_valid_package_name,
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
    )
else:
    from db_errors import DatabaseDriverError
    from db_transactions import transaction
    from postgres_audit import audit_log
    from postgres_clients import _lock_authenticated_client
    from postgres_flask_security import (
        authenticated_client,
        client_auth_required,
        csrf_required,
        current_user_id,
        login_required,
        role_required,
    )
    from security import (
        is_valid_package_name,
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
    )


_ALLOWED_ACTIONS = {
    "INSTALL_PACKAGE",
    "REMOVE_PACKAGE",
    "UPDATE_PACKAGE",
    "UPDATE_SYSTEM",
}

_ALLOWED_PACKAGE_STATUSES = {
    "success",
    "failed",
    "timeout",
}

_ALLOWED_RESULT_STATUSES = {
    "success",
    "partial",
    "failed",
}

_MAX_PACKAGE_RESULTS = 100
_MAX_RESULT_MESSAGE_LENGTH = 4096
_ABANDON_RECOVERY_REASON = (
    "Agent did not submit a final result."
)


class _UpdateJobTransactionAbort(Exception):
    """Abort a write transaction and return a controlled HTTP error."""

    def __init__(self, payload, status_code):
        super().__init__("Update-job transaction aborted")
        self.payload = payload
        self.status_code = status_code


def _get_connection():
    """Create an independent request-owned PostgreSQL connection."""
    factory = current_app.config.get(
        "LUMS_POSTGRES_GET_CONNECTION"
    )

    if not callable(factory):
        raise RuntimeError(
            "PostgreSQL connection factory is not configured"
        )

    return factory()


def _utc_now():
    return datetime.now(timezone.utc)


def _iso_timestamp(value):
    """Serialize PostgreSQL timestamps using the legacy ISO format."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def _serialize_row(row):
    """Convert a database row to JSON-compatible legacy values."""
    result = dict(row)

    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()

    return result


def _database_error(operation):
    current_app.logger.exception(
        "PostgreSQL update-job operation failed: %s",
        operation,
    )

    return jsonify({
        "error": "database_unavailable"
    }), 500


def _locked_agent(connection, client):
    """Revalidate the authenticated agent inside the transaction."""
    return _lock_authenticated_client(
        connection,
        client,
    )


def _job_for_update(connection, job_id, client_id):
    return connection.execute(
        """
        SELECT
            id,
            client_id,
            status,
            created_at,
            started_at,
            finished_at,
            reboot_required,
            recovery_reason,
            action
        FROM update_jobs
        WHERE id = %s
          AND client_id = %s
        FOR UPDATE
        """,
        (job_id, client_id),
    ).fetchone()


def register_postgres_update_job_routes(app):
    """Register PostgreSQL-native update-job routes."""

    @app.post("/api/clients/<int:client_id>/update-jobs")
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        permission="jobs.manage",
    )
    @csrf_required
    def postgres_create_update_job(client_id):
        data = request.get_json(silent=True)

        if not isinstance(data, dict) or not data:
            return jsonify({
                "status": "error",
                "message": "Invalid or missing JSON data",
            }), 400

        action = data.get("action", "UPDATE_PACKAGE")

        if (
            not isinstance(action, str)
            or action not in _ALLOWED_ACTIONS
        ):
            return jsonify({
                "status": "error",
                "message": "Invalid package action",
                "allowed_actions": sorted(_ALLOWED_ACTIONS),
            }), 400

        if action == "UPDATE_SYSTEM":
            packages = []
        else:
            packages = data.get("packages")

            if not isinstance(packages, list):
                return jsonify({
                    "status": "error",
                    "message": "packages must be a list",
                }), 400

            invalid_packages = [
                package
                for package in packages
                if not is_valid_package_name(package)
            ]

            if invalid_packages:
                return jsonify({
                    "status": "error",
                    "message": "Invalid package name",
                    "packages": invalid_packages,
                }), 400

            packages = list(dict.fromkeys(
                package.strip()
                for package in packages
            ))

            if not packages:
                return jsonify({
                    "status": "error",
                    "message": "No packages selected",
                }), 400

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                client_row = connection.execute(
                    """
                    SELECT id, hostname
                    FROM clients
                    WHERE id = %s
                      AND enabled = TRUE
                    FOR UPDATE
                    """,
                    (client_id,),
                ).fetchone()

                if client_row is None:
                    return jsonify({
                        "status": "error",
                        "message": "Client not found",
                    }), 404

                update_rows = []

                if action == "UPDATE_SYSTEM":
                    available_count = connection.execute(
                        """
                        SELECT COUNT(*) AS package_count
                        FROM available_updates
                        WHERE client_id = %s
                        """,
                        (client_id,),
                    ).fetchone()["package_count"]

                    if available_count == 0:
                        return jsonify({
                            "status": "error",
                            "message": (
                                "No system updates are available. "
                                "No job was created."
                            ),
                        }), 409

                elif action == "UPDATE_PACKAGE":
                    update_rows = connection.execute(
                        """
                        SELECT
                            package,
                            installed_version,
                            available_version
                        FROM available_updates
                        WHERE client_id = %s
                          AND package = ANY(%s)
                        ORDER BY package
                        """,
                        (client_id, packages),
                    ).fetchall()

                    found_packages = {
                        row["package"]
                        for row in update_rows
                    }

                    invalid_packages = [
                        package
                        for package in packages
                        if package not in found_packages
                    ]

                    if invalid_packages:
                        return jsonify({
                            "status": "error",
                            "message": (
                                "One or more packages are "
                                "not available as updates"
                            ),
                            "invalid_packages": invalid_packages,
                        }), 400

                else:
                    update_rows = [
                        {
                            "package": package,
                            "installed_version": None,
                            "available_version": "",
                        }
                        for package in packages
                    ]

                created_at = _utc_now()

                job_row = connection.execute(
                    """
                    INSERT INTO update_jobs (
                        client_id,
                        status,
                        created_at,
                        action
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        client_id,
                        "pending",
                        created_at,
                        action,
                    ),
                ).fetchone()

                job_id = job_row["id"]

                for row in update_rows:
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
                            job_id,
                            row["package"],
                            row["installed_version"],
                            row["available_version"],
                            "pending",
                        ),
                    )

                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=current_user_id(),
                    action="update_job.create",
                    target=f"job:{job_id}",
                    result="success",
                    details=(
                        f"client={client_id} "
                        f"action={action} "
                        f"packages={len(update_rows)}"
                    ),
                )

            current_app.logger.info(
                "Update job created: Job #%s Client %s "
                "Action: %s Packages: %d",
                job_id,
                client_row["hostname"],
                action,
                len(update_rows),
            )

            return jsonify({
                "status": "created",
                "job_id": job_id,
                "client_id": client_id,
                "hostname": client_row["hostname"],
                "action": action,
                "package_count": len(update_rows),
                "packages": [
                    {
                        "package": row["package"],
                        "installed_version": row["installed_version"],
                        "target_version": row["available_version"],
                    }
                    for row in update_rows
                ],
            }), 201

        except DatabaseDriverError:
            return _database_error("create update job")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while creating update job"
            )
            return jsonify({
                "error": "internal_server_error"
            }), 500

        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/clients/<int:client_id>/update-jobs")
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="updates.view",
    )
    def postgres_client_update_jobs(client_id):
        connection = None

        try:
            connection = _get_connection()

            client_row = connection.execute(
                """
                SELECT id
                FROM clients
                WHERE id = %s
                """,
                (client_id,),
            ).fetchone()

            if client_row is None:
                return jsonify({
                    "status": "error",
                    "message": "Client not found",
                }), 404

            rows = connection.execute(
                """
                SELECT
                    j.id,
                    j.client_id,
                    j.status,
                    j.created_at,
                    j.started_at,
                    j.finished_at,
                    j.reboot_required,
                    COUNT(p.id) AS package_count
                FROM update_jobs j
                LEFT JOIN update_job_packages p
                    ON p.job_id = j.id
                WHERE j.client_id = %s
                GROUP BY j.id
                ORDER BY j.id DESC
                """,
                (client_id,),
            ).fetchall()

            return jsonify([
                _serialize_row(row)
                for row in rows
            ])

        except DatabaseDriverError:
            return _database_error("list client update jobs")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while listing client update jobs"
            )
            return jsonify({
                "error": "internal_server_error"
            }), 500

        finally:
            if connection is not None:
                connection.close()

    @app.post("/api/update-jobs/<int:job_id>/checkpoint")
    @client_auth_required
    def postgres_update_job_checkpoint(job_id):
        client = authenticated_client()
        data = request.get_json(silent=True)

        if not isinstance(data, dict) or not data:
            return jsonify({
                "error": "invalid_json"
            }), 400

        package = data.get("package")
        package_status = data.get("status")
        message = data.get("message")

        if not isinstance(package, str) or not package.strip():
            return jsonify({
                "error": "invalid_package"
            }), 400

        package = package.strip()

        if (
            not isinstance(package_status, str)
            or package_status not in _ALLOWED_PACKAGE_STATUSES
        ):
            return jsonify({
                "error": "invalid_status"
            }), 400

        if message is not None:
            if not isinstance(message, str):
                return jsonify({
                    "error": "invalid_message"
                }), 400

            if len(message) > _MAX_RESULT_MESSAGE_LENGTH:
                return jsonify({
                    "error": "message_too_long"
                }), 400

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                locked_client = _locked_agent(
                    connection,
                    client,
                )

                if locked_client is None:
                    return jsonify({
                        "error": "client_authentication_required"
                    }), 401

                job = _job_for_update(
                    connection,
                    job_id,
                    locked_client["id"],
                )

                if job is None:
                    other_job = connection.execute(
                        """
                        SELECT client_id
                        FROM update_jobs
                        WHERE id = %s
                        """,
                        (job_id,),
                    ).fetchone()

                    if other_job is None:
                        return jsonify({
                            "error": "job_not_found"
                        }), 404

                    return jsonify({
                        "error": "client_access_denied"
                    }), 403

                if job["status"] != "running":
                    return jsonify({
                        "error": "job_not_running",
                        "job_id": job_id,
                        "job_status": job["status"],
                    }), 409

                package_row = connection.execute(
                    """
                    SELECT id
                    FROM update_job_packages
                    WHERE job_id = %s
                      AND package = %s
                    FOR UPDATE
                    """,
                    (job_id, package),
                ).fetchone()

                if package_row is None:
                    return jsonify({
                        "error": "package_not_found"
                    }), 404

                update_cursor = connection.execute(
                    """
                    UPDATE update_job_packages
                    SET status = %s,
                        message = %s
                    WHERE id = %s
                      AND job_id = %s
                    """,
                    (
                        package_status,
                        message,
                        package_row["id"],
                        job_id,
                    ),
                )

                if update_cursor.rowcount != 1:
                    return jsonify({
                        "error": "package_update_conflict"
                    }), 409

            return jsonify({
                "status": "checkpointed",
                "job_id": job_id,
                "package": package,
                "package_status": package_status,
            }), 200

        except DatabaseDriverError:
            return _database_error("checkpoint update job")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while checkpointing update job"
            )
            return jsonify({
                "error": "internal_server_error"
            }), 500

        finally:
            if connection is not None:
                connection.close()

    @app.post("/api/update-jobs/<int:job_id>/result")
    @client_auth_required
    def postgres_update_job_result(job_id):
        client = authenticated_client()
        data = request.get_json(silent=True) or {}

        if not isinstance(data, dict):
            return jsonify({
                "error": "invalid_json"
            }), 400

        status = data.get("status")
        reboot_required = data.get("reboot_required") is True
        packages = data.get("packages", [])

        if (
            not isinstance(status, str)
            or status not in _ALLOWED_RESULT_STATUSES
        ):
            return jsonify({
                "error": "invalid status"
            }), 400

        if not isinstance(packages, list):
            return jsonify({
                "error": "invalid packages"
            }), 400

        if len(packages) > _MAX_PACKAGE_RESULTS:
            return jsonify({
                "error": "too_many_package_results"
            }), 400

        seen_packages = set()

        for package_result in packages:
            if not isinstance(package_result, dict):
                return jsonify({
                    "error": "invalid package result"
                }), 400

            package = package_result.get("package")
            package_status = package_result.get("status")
            message = package_result.get("message")

            if not isinstance(package, str) or not package.strip():
                return jsonify({
                    "error": "invalid package"
                }), 400

            package = package.strip()

            if package in seen_packages:
                return jsonify({
                    "error": "duplicate package",
                    "package": package,
                }), 400

            seen_packages.add(package)

            if (
                not isinstance(package_status, str)
                or package_status not in _ALLOWED_PACKAGE_STATUSES
            ):
                return jsonify({
                    "error": "invalid package status"
                }), 400

            if message is not None:
                if not isinstance(message, str):
                    return jsonify({
                        "error": "invalid package message",
                        "package": package,
                    }), 400

                if len(message) > _MAX_RESULT_MESSAGE_LENGTH:
                    return jsonify({
                        "error": "package message too long",
                        "package": package,
                    }), 400

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                locked_client = _locked_agent(
                    connection,
                    client,
                )

                if locked_client is None:
                    return jsonify({
                        "error": "client_authentication_required"
                    }), 401

                job = _job_for_update(
                    connection,
                    job_id,
                    locked_client["id"],
                )

                if job is None:
                    other_job = connection.execute(
                        """
                        SELECT client_id
                        FROM update_jobs
                        WHERE id = %s
                        """,
                        (job_id,),
                    ).fetchone()

                    if other_job is None:
                        return jsonify({
                            "error": "job not found"
                        }), 404

                    return jsonify({
                        "error": "client_access_denied"
                    }), 403

                if job["status"] != "running":
                    return jsonify({
                        "error": "job_not_running",
                        "job_id": job_id,
                        "job_status": job["status"],
                    }), 409

                job_packages = {
                    row["package"]
                    for row in connection.execute(
                        """
                        SELECT package
                        FROM update_job_packages
                        WHERE job_id = %s
                        ORDER BY id
                        FOR UPDATE
                        """,
                        (job_id,),
                    ).fetchall()
                }

                if job["action"] == "UPDATE_SYSTEM":
                    if packages:
                        return jsonify({
                            "error": (
                                "system_update_must_not_contain_packages"
                            )
                        }), 400

                    now = _utc_now()

                    update_cursor = connection.execute(
                        """
                        UPDATE update_jobs
                        SET status = %s,
                            finished_at = %s,
                            reboot_required = %s
                        WHERE id = %s
                          AND client_id = %s
                          AND status = 'running'
                        """,
                        (
                            status,
                            now,
                            reboot_required,
                            job_id,
                            locked_client["id"],
                        ),
                    )

                    if update_cursor.rowcount != 1:
                        raise _UpdateJobTransactionAbort(
                            {"error": "job_update_conflict"},
                            409,
                        )

                    connection.execute(
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
                        VALUES (%s, %s, %s, 0, 0, 0, %s, %s, %s)
                        """,
                        (
                            job["client_id"],
                            job_id,
                            status,
                            reboot_required,
                            job["started_at"],
                            now,
                        ),
                    )

                    successful_count = 0
                    failed_count = 0
                    final_status = status

                else:
                    expected_count = len(job_packages)

                    if len(packages) != expected_count:
                        return jsonify({
                            "error": "incomplete_package_results",
                            "expected": expected_count,
                            "received": len(packages),
                        }), 400

                    if seen_packages != job_packages:
                        missing_packages = sorted(
                            job_packages - seen_packages
                        )
                        unexpected_packages = sorted(
                            seen_packages - job_packages
                        )

                        return jsonify({
                            "error": "package_result_mismatch",
                            "missing_packages": missing_packages,
                            "unexpected_packages": unexpected_packages,
                        }), 400

                    successful_count = sum(
                        1
                        for item in packages
                        if item["status"] == "success"
                    )
                    failed_count = len(packages) - successful_count

                    if failed_count == 0:
                        final_status = "success"
                    elif successful_count > 0:
                        final_status = "partial"
                    else:
                        final_status = "failed"

                    if status != final_status:
                        return jsonify({
                            "error": "status_mismatch",
                            "submitted_status": status,
                            "derived_status": final_status,
                        }), 400

                    now = _utc_now()

                    for item in packages:
                        package = item["package"].strip()
                        package_cursor = connection.execute(
                            """
                            UPDATE update_job_packages
                            SET status = %s,
                                message = %s
                            WHERE job_id = %s
                              AND package = %s
                            """,
                            (
                                item["status"],
                                item.get("message"),
                                job_id,
                                package,
                            ),
                        )

                        if package_cursor.rowcount != 1:
                            raise _UpdateJobTransactionAbort(
                                {
                                    "error": "package_update_conflict",
                                    "package": package,
                                },
                                409,
                            )

                    update_cursor = connection.execute(
                        """
                        UPDATE update_jobs
                        SET status = %s,
                            finished_at = %s,
                            reboot_required = %s
                        WHERE id = %s
                          AND client_id = %s
                          AND status = 'running'
                        """,
                        (
                            final_status,
                            now,
                            reboot_required,
                            job_id,
                            locked_client["id"],
                        ),
                    )

                    if update_cursor.rowcount != 1:
                        raise _UpdateJobTransactionAbort(
                            {"error": "job_update_conflict"},
                            409,
                        )

                    connection.execute(
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
                        """,
                        (
                            job["client_id"],
                            job_id,
                            final_status,
                            len(packages),
                            successful_count,
                            failed_count,
                            reboot_required,
                            job["started_at"],
                            now,
                        ),
                    )

                audit_log(
                    connection,
                    actor_type="client",
                    actor_id=locked_client["id"],
                    action="update_job.result",
                    target=f"job:{job_id}",
                    result="success",
                    details=(
                        f"status={final_status}; "
                        f"package_count={len(packages)}; "
                        f"successful_count={successful_count}; "
                        f"failed_count={failed_count}; "
                        f"reboot_required={str(reboot_required).lower()}"
                    ),
                )

            return jsonify({
                "status": "ok",
                "job_id": job_id,
                "job_status": final_status,
                "successful_count": successful_count,
                "failed_count": failed_count,
                "reboot_required": reboot_required,
            })

        except _UpdateJobTransactionAbort as abort:
            return jsonify(abort.payload), abort.status_code

        except DatabaseDriverError:
            return _database_error("submit update job result")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while submitting update job result"
            )
            return jsonify({
                "error": "internal_server_error"
            }), 500

        finally:
            if connection is not None:
                connection.close()

    @app.post("/api/update-jobs/<int:job_id>/abandon")
    @client_auth_required
    def postgres_abandon_update_job(job_id):
        client = authenticated_client()
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                locked_client = _locked_agent(
                    connection,
                    client,
                )

                if locked_client is None:
                    return jsonify({
                        "error": "client_authentication_required"
                    }), 401

                job = _job_for_update(
                    connection,
                    job_id,
                    locked_client["id"],
                )

                if job is None:
                    other_job = connection.execute(
                        """
                        SELECT client_id
                        FROM update_jobs
                        WHERE id = %s
                        """,
                        (job_id,),
                    ).fetchone()

                    if other_job is None:
                        return jsonify({
                            "error": "job_not_found"
                        }), 404

                    return jsonify({
                        "error": "client_access_denied"
                    }), 403

                if job["status"] != "running":
                    return jsonify({
                        "error": "job_not_running"
                    }), 409

                package_count = connection.execute(
                    """
                    SELECT COUNT(*) AS package_count
                    FROM update_job_packages
                    WHERE job_id = %s
                    """,
                    (job_id,),
                ).fetchone()["package_count"]

                now = _utc_now()

                update_cursor = connection.execute(
                    """
                    UPDATE update_jobs
                    SET status = %s,
                        finished_at = %s,
                        recovery_reason = %s
                    WHERE id = %s
                      AND client_id = %s
                      AND status = 'running'
                    """,
                    (
                        "abandoned",
                        now,
                        _ABANDON_RECOVERY_REASON,
                        job_id,
                        locked_client["id"],
                    ),
                )

                if update_cursor.rowcount != 1:
                    return jsonify({
                        "error": "job_recovery_conflict"
                    }), 409

                connection.execute(
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
                    VALUES (%s, %s, %s, %s, 0, 0, %s, %s, %s)
                    """,
                    (
                        job["client_id"],
                        job_id,
                        "abandoned",
                        package_count,
                        job["reboot_required"],
                        job["started_at"],
                        now,
                    ),
                )

            return jsonify({
                "status": "abandoned",
                "job_id": job_id,
                "client_id": locked_client["id"],
                "package_count": package_count,
                "recovery_reason": _ABANDON_RECOVERY_REASON,
            }), 200

        except DatabaseDriverError:
            return _database_error("abandon update job")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while abandoning update job"
            )
            return jsonify({
                "error": "internal_server_error"
            }), 500

        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/clients/<int:client_id>/update-jobs/pending")
    @client_auth_required
    def postgres_get_pending_update_job(client_id):
        client = authenticated_client()

        if client["id"] != client_id:
            return jsonify({
                "error": "client_access_denied"
            }), 403

        connection = None

        try:
            connection = _get_connection()

            client_row = connection.execute(
                """
                SELECT id, hostname
                FROM clients
                WHERE id = %s
                """,
                (client_id,),
            ).fetchone()

            if client_row is None:
                return jsonify({
                    "status": "error",
                    "message": "Client not found",
                }), 404

            job = connection.execute(
                """
                SELECT
                    id,
                    client_id,
                    created_at,
                    reboot_required,
                    action
                FROM update_jobs
                WHERE client_id = %s
                  AND status = 'pending'
                ORDER BY id ASC
                LIMIT 1
                """,
                (client_id,),
            ).fetchone()

            if job is None:
                return jsonify({
                    "status": "no_job"
                }), 204

            package_rows = connection.execute(
                """
                SELECT
                    package,
                    installed_version,
                    target_version,
                    status
                FROM update_job_packages
                WHERE job_id = %s
                ORDER BY id ASC
                """,
                (job["id"],),
            ).fetchall()

            return jsonify({
                "status": "pending",
                "job_id": job["id"],
                "client_id": job["client_id"],
                "created_at": _iso_timestamp(job["created_at"]),
                "action": job["action"],
                "reboot_required": bool(job["reboot_required"]),
                "packages": [
                    {
                        "package": row["package"],
                        "installed_version": row["installed_version"],
                        "target_version": row["target_version"],
                        "status": row["status"],
                    }
                    for row in package_rows
                ],
            }), 200

        except DatabaseDriverError:
            return _database_error("get pending update job")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while getting pending update job"
            )
            return jsonify({
                "error": "internal_server_error"
            }), 500

        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/clients/<int:client_id>/update-jobs/running")
    @client_auth_required
    def postgres_get_running_update_job(client_id):
        client = authenticated_client()

        if client["id"] != client_id:
            return jsonify({
                "error": "client_access_denied"
            }), 403

        connection = None

        try:
            connection = _get_connection()

            client_row = connection.execute(
                """
                SELECT id, hostname
                FROM clients
                WHERE id = %s
                """,
                (client_id,),
            ).fetchone()

            if client_row is None:
                return jsonify({
                    "status": "error",
                    "message": "Client not found",
                }), 404

            job = connection.execute(
                """
                SELECT
                    id,
                    client_id,
                    created_at,
                    started_at,
                    reboot_required,
                    action
                FROM update_jobs
                WHERE client_id = %s
                  AND status = 'running'
                ORDER BY id ASC
                LIMIT 1
                """,
                (client_id,),
            ).fetchone()

            if job is None:
                return jsonify({
                    "status": "no_job"
                }), 204

            package_rows = connection.execute(
                """
                SELECT
                    package,
                    target_version,
                    status
                FROM update_job_packages
                WHERE job_id = %s
                ORDER BY id ASC
                """,
                (job["id"],),
            ).fetchall()

            return jsonify({
                "status": "running",
                "job_id": job["id"],
                "client_id": job["client_id"],
                "created_at": _iso_timestamp(job["created_at"]),
                "started_at": _iso_timestamp(job["started_at"]),
                "reboot_required": bool(job["reboot_required"]),
                "action": job["action"],
                "packages": [
                    {
                        "package": row["package"],
                        "target_version": row["target_version"],
                        "status": row["status"],
                    }
                    for row in package_rows
                ],
            }), 200

        except DatabaseDriverError:
            return _database_error("get running update job")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while getting running update job"
            )
            return jsonify({
                "error": "internal_server_error"
            }), 500

        finally:
            if connection is not None:
                connection.close()

    @app.post(
        "/api/clients/<int:client_id>/update-jobs/<int:job_id>/claim"
    )
    @client_auth_required
    def postgres_claim_update_job(client_id, job_id):
        client = authenticated_client()

        if client["id"] != client_id:
            return jsonify({
                "error": "client_access_denied"
            }), 403

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                locked_client = _locked_agent(
                    connection,
                    client,
                )

                if locked_client is None:
                    return jsonify({
                        "error": "client_authentication_required"
                    }), 401

                job = _job_for_update(
                    connection,
                    job_id,
                    client_id,
                )

                if job is None:
                    return jsonify({
                        "status": "error",
                        "message": "Job not found",
                    }), 404

                if job["status"] != "pending":
                    return jsonify({
                        "status": "not_claimable",
                        "job_id": job_id,
                        "job_status": job["status"],
                    }), 409

                started_at = _utc_now()

                update_cursor = connection.execute(
                    """
                    UPDATE update_jobs
                    SET status = 'running',
                        started_at = %s
                    WHERE id = %s
                      AND client_id = %s
                      AND status = 'pending'
                    """,
                    (
                        started_at,
                        job_id,
                        client_id,
                    ),
                )

                if update_cursor.rowcount != 1:
                    return jsonify({
                        "status": "error",
                        "message": "Job could not be claimed",
                    }), 409

                package_rows = connection.execute(
                    """
                    SELECT
                        package,
                        installed_version,
                        target_version,
                        status
                    FROM update_job_packages
                    WHERE job_id = %s
                    ORDER BY id ASC
                    """,
                    (job_id,),
                ).fetchall()

            current_app.logger.info(
                "Update job claimed: Job #%s Client %s Packages: %d",
                job_id,
                client_id,
                len(package_rows),
            )

            return jsonify({
                "status": "claimed",
                "job_id": job_id,
                "client_id": client_id,
                "started_at": started_at.isoformat(),
                "reboot_required": bool(job["reboot_required"]),
                "action": job["action"],
                "packages": [
                    {
                        "package": row["package"],
                        "installed_version": row["installed_version"],
                        "target_version": row["target_version"],
                        "status": row["status"],
                    }
                    for row in package_rows
                ],
            })

        except DatabaseDriverError:
            return _database_error("claim update job")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while claiming update job"
            )
            return jsonify({
                "error": "internal_server_error"
            }), 500

        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/update-jobs/<int:job_id>")
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="updates.view",
    )
    def postgres_update_job_details(job_id):
        connection = None

        try:
            connection = _get_connection()

            job_row = connection.execute(
                """
                SELECT
                    j.id,
                    j.client_id,
                    c.hostname,
                    c.ip,
                    j.status,
                    j.created_at,
                    j.started_at,
                    j.finished_at,
                    j.reboot_required
                FROM update_jobs j
                JOIN clients c
                    ON c.id = j.client_id
                WHERE j.id = %s
                """,
                (job_id,),
            ).fetchone()

            if job_row is None:
                return jsonify({
                    "status": "error",
                    "message": "Update job not found",
                }), 404

            package_rows = connection.execute(
                """
                SELECT
                    id,
                    package,
                    installed_version,
                    target_version,
                    status,
                    message
                FROM update_job_packages
                WHERE job_id = %s
                ORDER BY package
                """,
                (job_id,),
            ).fetchall()

            job = _serialize_row(job_row)
            job["packages"] = [
                _serialize_row(row)
                for row in package_rows
            ]
            job["package_count"] = len(package_rows)
            job["successful_count"] = sum(
                1
                for row in package_rows
                if row["status"] == "success"
            )
            job["failed_count"] = sum(
                1
                for row in package_rows
                if row["status"] == "failed"
            )

            return jsonify(job)

        except DatabaseDriverError:
            return _database_error("get update job details")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while getting update job details"
            )
            return jsonify({
                "error": "internal_server_error"
            }), 500

        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/clients/<int:client_id>/update-history")
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="updates.view",
    )
    def postgres_client_update_history(client_id):
        connection = None

        try:
            connection = _get_connection()

            rows = connection.execute(
                """
                SELECT
                    id,
                    client_id,
                    job_id,
                    status,
                    package_count,
                    successful_count,
                    failed_count,
                    reboot_required,
                    started_at,
                    finished_at
                FROM update_history
                WHERE client_id = %s
                ORDER BY id DESC
                """,
                (client_id,),
            ).fetchall()

            return jsonify([
                _serialize_row(row)
                for row in rows
            ])

        except DatabaseDriverError:
            return _database_error("get client update history")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while getting client update history"
            )
            return jsonify({
                "error": "internal_server_error"
            }), 500

        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/update-history")
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="updates.view",
    )
    def postgres_update_history():
        connection = None

        try:
            connection = _get_connection()

            rows = connection.execute(
                """
                SELECT
                    h.id,
                    h.client_id,
                    c.hostname,
                    c.ip,
                    h.job_id,
                    h.status,
                    h.package_count,
                    h.successful_count,
                    h.failed_count,
                    h.reboot_required,
                    h.started_at,
                    h.finished_at
                FROM update_history h
                JOIN clients c
                    ON c.id = h.client_id
                ORDER BY h.id DESC
                """
            ).fetchall()

            return jsonify([
                _serialize_row(row)
                for row in rows
            ])

        except DatabaseDriverError:
            return _database_error("get update history")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while getting update history"
            )
            return jsonify({
                "error": "internal_server_error"
            }), 500

        finally:
            if connection is not None:
                connection.close()


__all__ = [
    "register_postgres_update_job_routes",
]
