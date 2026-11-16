"""PostgreSQL-native LUMS host-updater status and dashboard routes."""

from __future__ import annotations

import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, jsonify, render_template, request

if __package__:
    from .db_errors import DatabaseDriverError
    from .db_transactions import transaction
    from .postgres_flask_security import (
        current_user_permissions,
        current_user_role,
        get_csrf_token,
        login_required,
        role_required,
        csrf_required,
    )
    from .security import ROLE_ADMINISTRATOR, hash_client_token
    from .system_updates import ReleaseLookupError, latest_release
else:
    from db_errors import DatabaseDriverError
    from db_transactions import transaction
    from postgres_flask_security import (
        current_user_permissions,
        current_user_role,
        get_csrf_token,
        login_required,
        role_required,
        csrf_required,
    )
    from security import ROLE_ADMINISTRATOR, hash_client_token
    from system_updates import ReleaseLookupError, latest_release


def _get_connection():
    factory = current_app.config.get(
        "LUMS_POSTGRES_GET_CONNECTION"
    )

    if not callable(factory):
        raise RuntimeError(
            "PostgreSQL connection factory is not configured"
        )

    return factory()


def _decode_json(value, expected_type, fallback):
    """Decode stored JSON without propagating malformed history data."""
    if isinstance(value, expected_type):
        return value

    if not isinstance(value, str) or not value:
        return fallback

    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return fallback

    return decoded if isinstance(decoded, expected_type) else fallback


def _agent_is_online(last_seen, now=None):
    """Consider a host updater online only for a recent, valid heartbeat."""
    if not isinstance(last_seen, str) or not last_seen.strip():
        return False

    try:
        heartbeat = datetime.fromisoformat(last_seen)
    except (TypeError, ValueError, OverflowError):
        return False

    if heartbeat.tzinfo is None:
        heartbeat = heartbeat.replace(tzinfo=timezone.utc)

    current_time = now or datetime.now(timezone.utc)

    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    try:
        age = (current_time - heartbeat).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return False

    return 0 <= age <= 60


def _host_updater_auth_error():
    """Authenticate the dedicated host updater without a user session."""
    token_file = os.environ.get(
        "LUMS_HOST_UPDATER_TOKEN_FILE",
        "/run/secrets/lums_host_updater_token",
    )

    try:
        configured_token = Path(token_file).read_text(
            encoding="utf-8"
        ).strip()
    except (OSError, UnicodeError, ValueError):
        current_app.logger.error(
            "Host-updater token file is unavailable"
        )
        return jsonify({
            "error": "host_updater_not_configured"
        }), 503

    if len(configured_token) < 32:
        current_app.logger.error(
            "Host-updater token configuration is invalid"
        )
        return jsonify({
            "error": "host_updater_not_configured"
        }), 503

    authorization = request.headers.get("Authorization", "")
    scheme, separator, supplied_token = authorization.partition(" ")
    supplied_token = supplied_token.strip()

    if (
        not separator
        or scheme.lower() != "bearer"
        or not supplied_token
        or not hmac.compare_digest(
            hash_client_token(supplied_token),
            hash_client_token(configured_token),
        )
    ):
        return jsonify({
            "error": "host_updater_authentication_required"
        }), 401

    return None


def register_postgres_system_update_routes(app):
    """Register PostgreSQL-native host-updater routes and dashboard."""

    @login_required
    @role_required(ROLE_ADMINISTRATOR)
    @role_required(permission="system.update")
    def system_updates_page():
        return render_template(
            "updates.html",
            csrf_token=get_csrf_token(),
            user_role=current_user_role(),
            user_permissions=sorted(current_user_permissions()),
            postgres_backend=True,
        )

    @login_required
    @role_required(ROLE_ADMINISTRATOR)
    @role_required(permission="system.update")
    def system_updates_status():
        release = None
        release_error = None

        try:
            release = latest_release()
        except ReleaseLookupError as error:
            release_error = str(error)

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL "
                    "REPEATABLE READ, READ ONLY"
                )

                agent = connection.execute(
                    """
                    SELECT
                        last_seen,
                        current_version,
                        deployment,
                        status_message
                    FROM system_update_agent
                    WHERE id = 1
                    """
                ).fetchone()

                jobs = connection.execute(
                    """
                    SELECT
                        id,
                        requested_at,
                        requested_by,
                        target_tag,
                        target_commit,
                        status,
                        step,
                        progress_json,
                        details_json,
                        error,
                        rollback_status,
                        updated_at,
                        finished_at
                    FROM system_update_jobs
                    ORDER BY id DESC
                    LIMIT 20
                    """
                ).fetchall()

            agent_data = dict(agent) if agent is not None else {
                "online": False,
            }

            if agent is not None:
                agent_data["online"] = _agent_is_online(
                    agent_data.get("last_seen")
                )

            history = []

            for row in jobs:
                item = dict(row)

                progress = _decode_json(
                    item.pop("progress_json", None),
                    list,
                    [],
                )

                details = _decode_json(
                    item.pop("details_json", None),
                    dict,
                    {},
                )

                # Only expose the summary required by the UI.
                # Internal worker and approval metadata stay server-side.
                summary = details.get("summary")
                item["progress"] = progress
                item["details"] = {
                    "summary": summary[:500]
                } if isinstance(summary, str) else {}

                history.append(item)

            return jsonify({
                "release": release,
                "release_error": release_error,
                "agent": agent_data,
                "history": history,
                "update_execution_enabled": False,
            }), 200

        except DatabaseDriverError:
            current_app.logger.exception(
                "Unable to load PostgreSQL host-updater status."
            )
            return jsonify({
                "error": "database_unavailable"
            }), 503

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    @login_required
    @role_required(ROLE_ADMINISTRATOR)
    @role_required(permission="system.update")
    @csrf_required
    def request_system_update():
        payload = request.get_json(silent=True)

        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_json"}), 400

        if payload.get("confirmed") is not True:
            return jsonify({
                "error": "explicit_confirmation_required"
            }), 400

        requested_tag = payload.get("target_tag")
        requested_commit = payload.get("target_commit")

        if (
            not isinstance(requested_tag, str)
            or not requested_tag
            or not isinstance(requested_commit, str)
            or not requested_commit
        ):
            return jsonify({
                "error": "invalid_release_target"
            }), 400

        # Fail closed until the complete host-update worker lifecycle
        # has been ported, tested and explicitly released.
        return jsonify({
            "error": "update_execution_disabled",
            "message": (
                "Die Update-Ausführung ist deaktiviert. "
                "Es wurde kein Updateauftrag angelegt."
            ),
        }), 503

    @app.post("/api/host-updater/heartbeat")
    def host_updater_heartbeat():
        auth_error = _host_updater_auth_error()

        if auth_error:
            return auth_error

        payload = request.get_json(silent=True)

        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_json"}), 400

        version = payload.get("version")
        deployment = payload.get("deployment")
        status_message = payload.get(
            "status_message",
            "Heartbeat received",
        )

        for field, value, limit in (
            ("version", version, 80),
            ("deployment", deployment, 80),
            ("status_message", status_message, 500),
        ):
            if value is not None and (
                not isinstance(value, str)
                or len(value) > limit
            ):
                return jsonify({
                    "error": "invalid_" + field
                }), 400

        if (
            not isinstance(status_message, str)
            or not status_message.strip()
        ):
            return jsonify({
                "error": "invalid_status_message"
            }), 400

        now = datetime.now(timezone.utc).isoformat()
        connection = None

        try:
            connection = _get_connection()

            connection.execute(
                """
                INSERT INTO system_update_agent (
                    id,
                    last_seen,
                    current_version,
                    deployment,
                    status_message
                )
                VALUES (1, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    last_seen = EXCLUDED.last_seen,
                    current_version = EXCLUDED.current_version,
                    deployment = EXCLUDED.deployment,
                    status_message = EXCLUDED.status_message
                """,
                (
                    now,
                    version,
                    deployment,
                    status_message.strip(),
                ),
            )

        except DatabaseDriverError:
            current_app.logger.exception(
                "Could not record PostgreSQL host-updater heartbeat."
            )
            return jsonify({
                "error": "heartbeat_storage_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

        return jsonify({
            "status": "ok",
            "last_seen": now,
            "update_execution_enabled": False,
        }), 200

    app.add_url_rule(
        "/updates",
        endpoint="postgres_system_updates_page",
        view_func=system_updates_page,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/system-updates",
        endpoint="postgres_system_updates_status",
        view_func=system_updates_status,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/system-updates",
        endpoint="postgres_request_system_update",
        view_func=request_system_update,
        methods=["POST"],
    )


__all__ = ["register_postgres_system_update_routes"]
