"""PostgreSQL-native asynchronous package search routes."""

from __future__ import annotations

import hmac
import json
from datetime import datetime, timezone

from flask import current_app, jsonify, request
from psycopg.types.json import Jsonb

if __package__:
    from .db_errors import DatabaseDriverError
    from .db_transactions import transaction
    from .postgres_audit import audit_log
    from .postgres_flask_security import (
        authenticated_client,
        current_user_id,
        csrf_required,
        login_required,
        role_required,
        client_auth_required,
    )
    from .security import (
        PACKAGE_NAME_MAX_LENGTH,
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
    )
else:
    from db_errors import DatabaseDriverError
    from db_transactions import transaction
    from postgres_audit import audit_log
    from postgres_flask_security import (
        authenticated_client,
        current_user_id,
        csrf_required,
        login_required,
        role_required,
        client_auth_required,
    )
    from security import (
        PACKAGE_NAME_MAX_LENGTH,
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
    )


PACKAGE_SEARCH_QUERY_MAX_LENGTH = 128
PACKAGE_SEARCH_MAX_RESULTS = 50


def _get_connection():
    factory = current_app.config.get(
        "LUMS_POSTGRES_GET_CONNECTION"
    )

    if not callable(factory):
        raise RuntimeError(
            "PostgreSQL connection factory is not configured"
        )

    return factory()


def normalize_package_search_query(query):
    if not isinstance(query, str):
        return None

    query = query.strip()

    if (
        not query
        or query.startswith("-")
        or len(query) > PACKAGE_SEARCH_QUERY_MAX_LENGTH
    ):
        return None

    return query


def _package_results_error(results):
    if not isinstance(results, list):
        return "invalid results"

    if len(results) > PACKAGE_SEARCH_MAX_RESULTS:
        return "too many results"

    for result in results:
        if not isinstance(result, dict):
            return "invalid result"

        package = result.get("package")

        if not isinstance(package, str):
            return "invalid package"

        package = package.strip()

        if (
            not package
            or len(package) > PACKAGE_NAME_MAX_LENGTH
            or not all(
                character.isalnum()
                or character in ".:+@_/-"
                for character in package
            )
        ):
            return "invalid package"

    return None


def _lock_authenticated_client(connection, client):
    locked_client = connection.execute(
        """
        SELECT
            id,
            enabled,
            client_token_hash,
            token_revoked_at
        FROM clients
        WHERE id = %s
        FOR UPDATE
        """,
        (client["id"],),
    ).fetchone()

    if (
        locked_client is None
        or locked_client["enabled"] is not True
        or locked_client["token_revoked_at"] is not None
        or not hmac.compare_digest(
            locked_client["client_token_hash"] or "",
            client["client_token_hash"] or "",
        )
    ):
        return False

    return True


def _iso_timestamp(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, str):
        return value

    raise TypeError("Unsupported package search timestamp")


def _completed_results(value):
    if value is None:
        return []

    if isinstance(value, str):
        value = json.loads(value)

    if not isinstance(value, list):
        raise ValueError("Package search result JSON is not an array")

    return value


def register_postgres_package_search_routes(app):
    """Register package-search routes on the isolated PostgreSQL app."""

    @login_required
    @role_required(ROLE_ADMINISTRATOR, ROLE_OPERATOR)
    @role_required(permission="packages.search")
    @csrf_required
    def create_package_search(client_id):
        payload = request.get_json(silent=True)

        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_request"}), 400

        query = normalize_package_search_query(
            payload.get("query")
        )

        if query is None:
            return jsonify({
                "error": "invalid_package_search_query"
            }), 400

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                client = connection.execute(
                    """
                    SELECT id, enabled
                    FROM clients
                    WHERE id = %s
                    FOR SHARE
                    """,
                    (client_id,),
                ).fetchone()

                if client is None:
                    return jsonify({
                        "error": "client_not_found"
                    }), 404

                if client["enabled"] is not True:
                    return jsonify({
                        "error": "client_disabled"
                    }), 409

                created_at = datetime.now(timezone.utc)

                row = connection.execute(
                    """
                    INSERT INTO package_search_requests (
                        client_id,
                        query,
                        status,
                        created_at
                    )
                    VALUES (%s, %s, 'pending', %s)
                    RETURNING id
                    """,
                    (
                        client_id,
                        query,
                        created_at,
                    ),
                ).fetchone()

                if row is None:
                    raise RuntimeError(
                        "PostgreSQL did not return the package search ID"
                    )

                search_id = row["id"]

                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=current_user_id(),
                    action="package_search.create",
                    target=f"client:{client_id}",
                    result="success",
                    details=f"search_id={search_id} query={query}",
                )

            current_app.logger.info(
                "PostgreSQL package search created: Search #%s "
                "Client %s Query=%r",
                search_id,
                client_id,
                query,
            )

            return jsonify({
                "status": "pending",
                "search_id": search_id,
                "client_id": client_id,
                "query": query,
            }), 202

        except DatabaseDriverError:
            current_app.logger.exception(
                "Unable to create PostgreSQL package search "
                "for client %s.",
                client_id,
            )
            return jsonify({
                "error": "package_search_create_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    @client_auth_required
    def package_search_result(search_id):
        client = authenticated_client()
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({"error": "invalid status"}), 400

        status = data.get("status")
        results = data.get("results", [])
        error_message = data.get("error_message")

        if status not in ("completed", "failed"):
            return jsonify({"error": "invalid status"}), 400

        if status == "completed":
            if not isinstance(results, list):
                return jsonify({"error": "invalid results"}), 400

            validation_error = _package_results_error(results)
            if validation_error is not None:
                return jsonify({"error": validation_error}), 400

            stored_results = Jsonb(results)
            stored_error = None

        else:
            if error_message is not None:
                if not isinstance(error_message, str):
                    return jsonify({
                        "error": "invalid error_message"
                    }), 400

                error_message = error_message.strip()

                if len(error_message) > 1024:
                    return jsonify({
                        "error": "error_message too long"
                    }), 400
            else:
                error_message = "Package search failed"

            results = []
            stored_results = Jsonb([])
            stored_error = error_message

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                if not _lock_authenticated_client(connection, client):
                    return jsonify({
                        "error": "client_authentication_required"
                    }), 401

                search = connection.execute(
                    """
                    SELECT id, client_id, status
                    FROM package_search_requests
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (search_id,),
                ).fetchone()

                if search is None:
                    return jsonify({
                        "error": "search_not_found"
                    }), 404

                if search["client_id"] != client["id"]:
                    return jsonify({
                        "error": "client_access_denied"
                    }), 403

                if search["status"] != "running":
                    return jsonify({
                        "error": "search_not_running",
                        "search_id": search_id,
                        "search_status": search["status"],
                    }), 409

                finished_at = datetime.now(timezone.utc)

                updated = connection.execute(
                    """
                    UPDATE package_search_requests
                    SET
                        status = %s,
                        finished_at = %s,
                        result_json = %s,
                        error_message = %s
                    WHERE id = %s
                      AND client_id = %s
                      AND status = 'running'
                    RETURNING id
                    """,
                    (
                        status,
                        finished_at,
                        stored_results,
                        stored_error,
                        search_id,
                        client["id"],
                    ),
                ).fetchone()

                if updated is None:
                    return jsonify({
                        "error": "search_not_running",
                        "search_id": search_id,
                        "search_status": search["status"],
                    }), 409

            current_app.logger.info(
                "PostgreSQL package search finished: Search #%s "
                "Client %s Status=%s Results=%d",
                search_id,
                client["id"],
                status,
                len(results),
            )

            return jsonify({
                "status": status,
                "search_id": search_id,
                "result_count": len(results),
                "finished_at": finished_at.isoformat(),
            })

        except DatabaseDriverError:
            current_app.logger.exception(
                "Unable to store PostgreSQL package search result "
                "for search %s.",
                search_id,
            )
            return jsonify({
                "error": "package_search_result_save_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    @client_auth_required
    def get_pending_package_search(client_id):
        client = authenticated_client()

        if client["id"] != client_id:
            return jsonify({
                "error": "client_access_denied"
            }), 403

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                if not _lock_authenticated_client(connection, client):
                    return jsonify({
                        "error": "client_authentication_required"
                    }), 401

                search = connection.execute(
                    """
                    SELECT id, query, created_at
                    FROM package_search_requests
                    WHERE client_id = %s
                      AND status = 'pending'
                    ORDER BY id ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                    """,
                    (client_id,),
                ).fetchone()

                if search is None:
                    return "", 204

                started_at = datetime.now(timezone.utc)

                claimed = connection.execute(
                    """
                    UPDATE package_search_requests
                    SET
                        status = 'running',
                        started_at = %s
                    WHERE id = %s
                      AND client_id = %s
                      AND status = 'pending'
                    RETURNING id
                    """,
                    (
                        started_at,
                        search["id"],
                        client_id,
                    ),
                ).fetchone()

                if claimed is None:
                    return jsonify({
                        "error": "search_claim_conflict"
                    }), 409

            current_app.logger.info(
                "PostgreSQL package search claimed: Search #%s "
                "Client %s Query=%r",
                search["id"],
                client_id,
                search["query"],
            )

            return jsonify({
                "status": "running",
                "search_id": search["id"],
                "client_id": client_id,
                "query": search["query"],
                "created_at": _iso_timestamp(search["created_at"]),
                "started_at": started_at.isoformat(),
            })

        except DatabaseDriverError:
            current_app.logger.exception(
                "Unable to claim PostgreSQL package search "
                "for client %s.",
                client_id,
            )
            return jsonify({
                "error": "package_search_claim_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    @login_required
    @role_required(ROLE_ADMINISTRATOR, ROLE_OPERATOR)
    @role_required(permission="packages.search")
    def get_package_search_status(client_id, search_id):
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                search = connection.execute(
                    """
                    SELECT
                        id,
                        client_id,
                        query,
                        status,
                        created_at,
                        started_at,
                        finished_at,
                        result_json,
                        error_message
                    FROM package_search_requests
                    WHERE id = %s
                      AND client_id = %s
                    """,
                    (
                        search_id,
                        client_id,
                    ),
                ).fetchone()

            if search is None:
                return jsonify({
                    "error": "search_not_found"
                }), 404

            results = []

            if search["status"] == "completed":
                try:
                    results = _completed_results(
                        search["result_json"]
                    )
                except (TypeError, ValueError, json.JSONDecodeError):
                    current_app.logger.exception(
                        "Invalid PostgreSQL package search result "
                        "JSON for search %s.",
                        search_id,
                    )
                    return jsonify({
                        "error": "invalid_search_result"
                    }), 500

            return jsonify({
                "status": search["status"],
                "search_id": search["id"],
                "client_id": search["client_id"],
                "query": search["query"],
                "created_at": _iso_timestamp(search["created_at"]),
                "started_at": _iso_timestamp(search["started_at"]),
                "finished_at": _iso_timestamp(search["finished_at"]),
                "results": results,
                "error_message": search["error_message"],
            })

        except DatabaseDriverError:
            current_app.logger.exception(
                "Unable to load PostgreSQL package search %s.",
                search_id,
            )
            return jsonify({
                "error": "package_search_status_load_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    app.add_url_rule(
        "/api/clients/<int:client_id>/package-search",
        endpoint="postgres_create_package_search",
        view_func=create_package_search,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/package-search/<int:search_id>/result",
        endpoint="postgres_package_search_result",
        view_func=package_search_result,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/clients/<int:client_id>/package-search/pending",
        endpoint="postgres_get_pending_package_search",
        view_func=get_pending_package_search,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/clients/<int:client_id>/package-search/<int:search_id>",
        endpoint="postgres_get_package_search_status",
        view_func=get_package_search_status,
        methods=["GET"],
    )


__all__ = [
    "normalize_package_search_query",
    "register_postgres_package_search_routes",
]
