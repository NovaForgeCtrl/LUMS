"""PostgreSQL-native client management and agent reporting for LUMS."""

from __future__ import annotations

import hmac
from datetime import datetime, timezone

from flask import current_app, jsonify, request
from psycopg import Error as PsycopgError
from psycopg.errors import UniqueViolation

if __package__:
    from .db_transactions import transaction
    from .postgres_audit import audit_log
    from .postgres_flask_security import (
        authenticated_client,
        client_auth_required,
        csrf_required,
        current_user_id,
        login_required,
        role_required,
    )
    from .postgres_infrastructure import classify_health_client
    from .security import (
        generate_client_token,
        hash_client_token,
        is_valid_package_name,
    )
else:
    from db_transactions import transaction
    from postgres_audit import audit_log
    from postgres_flask_security import (
        authenticated_client,
        client_auth_required,
        csrf_required,
        current_user_id,
        login_required,
        role_required,
    )
    from postgres_infrastructure import classify_health_client
    from security import (
        generate_client_token,
        hash_client_token,
        is_valid_package_name,
    )


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


def _lock_authenticated_client(connection, client):
    """Revalidate and lock the client after bearer authentication."""
    locked_client = connection.execute(
        """
        SELECT
            id,
            hostname,
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
        return None

    return locked_client


def validate_client_report(data):
    """Validate the existing LUMS Agent report contract."""
    if not isinstance(data, dict) or not data:
        return False

    text_fields = (
        "hostname",
        "ip",
        "os",
        "kernel",
        "architecture",
        "agent_version",
    )

    if any(
        not isinstance(data.get(field), str)
        or not data[field].strip()
        for field in text_fields
    ):
        return False

    if "idle" in data and not isinstance(data["idle"], bool):
        return False

    for field in ("idle_seconds", "idle_threshold_seconds"):
        if field in data and (
            isinstance(data[field], bool)
            or not isinstance(data[field], int)
            or data[field] < (
                1 if field == "idle_threshold_seconds" else 0
            )
        ):
            return False

    if (
        "idle_source" in data
        and not isinstance(data["idle_source"], str)
    ):
        return False

    if (
        "idle_supported" in data
        and not isinstance(data["idle_supported"], bool)
    ):
        return False

    updates = data.get("updates", [])
    if not isinstance(updates, list):
        return False

    for update in updates:
        if not isinstance(update, dict):
            return False

        package = update.get("package")
        available_version = update.get("available_version")
        installed_version = update.get("installed_version")

        if (
            not is_valid_package_name(package)
            or not isinstance(available_version, str)
            or not available_version.strip()
            or (
                installed_version is not None
                and not isinstance(installed_version, str)
            )
        ):
            return False

    packages = data.get("packages", {})
    if not isinstance(packages, dict):
        return False

    return all(
        is_valid_package_name(package)
        and isinstance(version, str)
        and bool(version.strip())
        for package, version in packages.items()
    )


def _iso_timestamp(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def register_postgres_client_routes(app):
    """Register PostgreSQL-native client management and agent routes."""

    @login_required
    @role_required(permission="clients.manage")
    @csrf_required
    def create_client():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}

        hostname = str(data.get("hostname", "")).strip() or None
        ip = str(data.get("ip", "")).strip() or None
        os_name = str(data.get("os", "")).strip() or None
        kernel = str(data.get("kernel", "")).strip() or None
        architecture = str(data.get("architecture", "")).strip() or None
        agent_version = str(data.get("agent_version", "")).strip() or None

        if not ip:
            return jsonify({"error": "ip_required"}), 400

        connection = _get_connection()

        try:
            try:
                with transaction(connection):
                    # Serialize registrations for the same IP address.
                    connection.execute(
                        """
                        SELECT pg_advisory_xact_lock(
                            hashtextextended(%s, 0)
                        )
                        """,
                        (f"lums-client-ip:{ip}",),
                    )

                    existing = connection.execute(
                        "SELECT id FROM clients WHERE ip = %s LIMIT 1",
                        (ip,),
                    ).fetchone()

                    if existing:
                        return jsonify({
                            "error": "client_already_exists"
                        }), 409

                    token = generate_client_token()
                    token_hash = hash_client_token(token)
                    now = datetime.now(timezone.utc)

                    row = connection.execute(
                        """
                        INSERT INTO clients (
                            hostname, ip, os, kernel, architecture,
                            agent_version, last_seen, client_token_hash,
                            token_created_at, token_revoked_at, enabled
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, TRUE)
                        RETURNING id
                        """,
                        (
                            hostname,
                            ip,
                            os_name,
                            kernel,
                            architecture,
                            agent_version,
                            now,
                            token_hash,
                            now,
                        ),
                    ).fetchone()

                    client_id = row["id"]

                    audit_log(
                        connection,
                        actor_type="user",
                        actor_id=current_user_id(),
                        action="client.create",
                        target=f"client:{client_id}",
                        result="success",
                        details=f"hostname={hostname}",
                    )

                return jsonify({
                    "status": "created",
                    "client": {
                        "id": client_id,
                        "hostname": hostname,
                        "ip": ip,
                        "os": os_name,
                        "kernel": kernel,
                        "architecture": architecture,
                        "agent_version": agent_version,
                        "enabled": True,
                    },
                    "token": token,
                }), 201

            except UniqueViolation:
                return jsonify({
                    "error": "client_already_exists"
                }), 409

        except PsycopgError:
            current_app.logger.exception(
                "Failed to create PostgreSQL client"
            )
            return jsonify({
                "error": "client_creation_failed"
            }), 500

        finally:
            connection.close()

    @login_required
    @role_required(permission="clients.manage")
    @csrf_required
    def rotate_client_token(client_id):
        connection = _get_connection()

        try:
            with transaction(connection):
                client = connection.execute(
                    """
                    SELECT id, hostname, enabled
                    FROM clients
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (client_id,),
                ).fetchone()

                if client is None:
                    return jsonify({
                        "error": "client_not_found"
                    }), 404

                token = generate_client_token()
                token_hash = hash_client_token(token)
                now = datetime.now(timezone.utc)

                connection.execute(
                    """
                    UPDATE clients
                    SET client_token_hash = %s,
                        token_created_at = %s,
                        token_revoked_at = NULL
                    WHERE id = %s
                    """,
                    (token_hash, now, client_id),
                )

                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=current_user_id(),
                    action="client.token.rotate",
                    target=f"client:{client_id}",
                    result="success",
                    details=f"hostname={client['hostname']}",
                )

            return jsonify({
                "status": "rotated",
                "client": {
                    "id": client["id"],
                    "hostname": client["hostname"],
                    "enabled": client["enabled"],
                },
                "token": token,
            }), 200

        except PsycopgError:
            current_app.logger.exception(
                "Failed to rotate PostgreSQL client token"
            )
            return jsonify({
                "error": "client_token_rotation_failed"
            }), 500

        finally:
            connection.close()

    @login_required
    @role_required(permission="clients.manage")
    @csrf_required
    def disable_client(client_id):
        connection = _get_connection()

        try:
            with transaction(connection):
                client = connection.execute(
                    """
                    SELECT id, hostname
                    FROM clients
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (client_id,),
                ).fetchone()

                if client is None:
                    return jsonify({
                        "error": "client_not_found"
                    }), 404

                now = datetime.now(timezone.utc)

                connection.execute(
                    "DELETE FROM available_updates WHERE client_id = %s",
                    (client_id,),
                )
                connection.execute(
                    "DELETE FROM installed_packages WHERE client_id = %s",
                    (client_id,),
                )
                connection.execute(
                    """
                    UPDATE clients
                    SET enabled = FALSE,
                        token_revoked_at = %s
                    WHERE id = %s
                    """,
                    (now, client_id),
                )

                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=current_user_id(),
                    action="client.disable",
                    target=f"client:{client_id}",
                    result="success",
                    details=f"hostname={client['hostname']}",
                )

            return jsonify({
                "status": "disabled",
                "client_id": client_id,
                "hostname": client["hostname"],
            }), 200

        except PsycopgError:
            current_app.logger.exception(
                "Failed to disable PostgreSQL client"
            )
            return jsonify({
                "error": "client_disable_failed"
            }), 500

        finally:
            connection.close()

    @login_required
    @role_required(permission="clients.view")
    def list_clients():
        connection = _get_connection()

        try:
            rows = connection.execute(
                """
                SELECT
                    c.id,
                    c.hostname,
                    c.ip,
                    c.os,
                    c.kernel,
                    c.architecture,
                    c.agent_version,
                    c.last_seen,
                    c.idle,
                    c.idle_seconds,
                    c.idle_threshold_seconds,
                    c.idle_source,
                    c.idle_supported,
                    COUNT(DISTINCT p.id) AS package_count,
                    COUNT(DISTINCT u.id) AS update_count
                FROM clients c
                LEFT JOIN installed_packages p
                    ON p.client_id = c.id
                LEFT JOIN available_updates u
                    ON u.client_id = c.id
                WHERE c.enabled IS TRUE
                GROUP BY c.id
                ORDER BY c.hostname
                """
            ).fetchall()

            result = []

            for row in rows:
                item = dict(row)
                item["status"] = classify_health_client(
                    item["last_seen"]
                )
                item["last_seen"] = _iso_timestamp(
                    item["last_seen"]
                )
                result.append(item)

            return jsonify(result), 200

        except PsycopgError:
            current_app.logger.exception(
                "Failed to list PostgreSQL clients"
            )
            return jsonify({
                "error": "client_list_failed"
            }), 500

        finally:
            connection.close()

    @login_required
    @role_required(permission="clients.view")
    def client_details(client_id):
        connection = _get_connection()

        try:
            row = connection.execute(
                """
                SELECT
                    c.id,
                    c.hostname,
                    c.ip,
                    c.os,
                    c.kernel,
                    c.architecture,
                    c.agent_version,
                    c.last_seen,
                    (
                        SELECT COUNT(*)
                        FROM installed_packages p
                        WHERE p.client_id = c.id
                    ) AS package_count,
                    (
                        SELECT COUNT(*)
                        FROM available_updates u
                        WHERE u.client_id = c.id
                    ) AS update_count
                FROM clients c
                WHERE c.id = %s
                  AND c.enabled IS TRUE
                """,
                (client_id,),
            ).fetchone()

            if row is None:
                return jsonify({
                    "status": "error",
                    "message": "Client not found",
                }), 404

            result = dict(row)
            result["status"] = classify_health_client(
                result["last_seen"]
            )
            result["last_seen"] = _iso_timestamp(
                result["last_seen"]
            )

            return jsonify(result), 200

        except PsycopgError:
            current_app.logger.exception(
                "Failed to load PostgreSQL client details"
            )
            return jsonify({
                "error": "client_details_failed"
            }), 500

        finally:
            connection.close()

    @login_required
    @role_required(permission="updates.view")
    def client_updates(client_id):
        connection = _get_connection()

        try:
            rows = connection.execute(
                """
                SELECT id, package, installed_version, available_version
                FROM available_updates
                WHERE client_id = %s
                ORDER BY package
                """,
                (client_id,),
            ).fetchall()

            return jsonify([dict(row) for row in rows]), 200

        except PsycopgError:
            current_app.logger.exception(
                "Failed to load PostgreSQL client updates"
            )
            return jsonify({
                "error": "client_updates_failed"
            }), 500

        finally:
            connection.close()

    @login_required
    @role_required(permission="software.view")
    def client_packages(client_id):
        connection = _get_connection()

        try:
            rows = connection.execute(
                """
                SELECT package, version
                FROM installed_packages
                WHERE client_id = %s
                ORDER BY package
                """,
                (client_id,),
            ).fetchall()

            return jsonify([dict(row) for row in rows]), 200

        except PsycopgError:
            current_app.logger.exception(
                "Failed to load PostgreSQL client packages"
            )
            return jsonify({
                "error": "client_packages_failed"
            }), 500

        finally:
            connection.close()

    @client_auth_required
    def client_me():
        client = authenticated_client()

        return jsonify({
            "id": client["id"],
            "hostname": client["hostname"],
            "enabled": bool(client["enabled"]),
        }), 200

    @client_auth_required
    def client_report():
        data = request.get_json(silent=True)

        if not isinstance(data, dict) or not data:
            return jsonify({
                "status": "error",
                "message": "Invalid or missing JSON data",
            }), 400

        if not validate_client_report(data):
            return jsonify({
                "status": "error",
                "message": "Invalid client report data",
            }), 400

        client = authenticated_client()
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                locked_client = _lock_authenticated_client(
                    connection,
                    client,
                )

                if locked_client is None:
                    return jsonify({
                        "error": "client_authentication_required"
                    }), 401

                now = datetime.now(timezone.utc)

                connection.execute(
                    """
                    UPDATE clients
                    SET hostname = %s,
                        ip = %s,
                        os = %s,
                        kernel = %s,
                        architecture = %s,
                        agent_version = %s,
                        last_seen = %s,
                        idle = %s,
                        idle_seconds = %s,
                        idle_threshold_seconds = %s,
                        idle_source = %s,
                        idle_supported = %s
                    WHERE id = %s
                    """,
                    (
                        data["hostname"],
                        data["ip"],
                        data["os"],
                        data["kernel"],
                        data["architecture"],
                        data["agent_version"],
                        now,
                        data.get("idle", False),
                        data.get("idle_seconds", 0),
                        data.get("idle_threshold_seconds", 300),
                        data.get("idle_source", "unknown").strip() or "unknown",
                        data.get("idle_supported", False),
                        client["id"],
                    ),
                )

                connection.execute(
                    "DELETE FROM available_updates WHERE client_id = %s",
                    (client["id"],),
                )

                for update in data.get("updates", []):
                    connection.execute(
                        """
                        INSERT INTO available_updates (
                            client_id, package, installed_version,
                            available_version
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            client["id"],
                            update["package"],
                            update.get("installed_version"),
                            update["available_version"],
                        ),
                    )

                connection.execute(
                    "DELETE FROM installed_packages WHERE client_id = %s",
                    (client["id"],),
                )

                for package, version in data.get("packages", {}).items():
                    connection.execute(
                        """
                        INSERT INTO installed_packages (
                            client_id, package, version
                        )
                        VALUES (%s, %s, %s)
                        """,
                        (client["id"], package, version),
                    )

            return jsonify({"status": "received"}), 200

        except PsycopgError:
            current_app.logger.exception(
                "Failed to save PostgreSQL client report for client %s",
                client["id"],
            )
            return jsonify({
                "status": "error",
                "message": "Failed to save client report",
            }), 500

        finally:
            if connection is not None:
                connection.close()

    app.add_url_rule(
        "/api/clients",
        endpoint="postgres_clients_create",
        view_func=create_client,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/clients",
        endpoint="postgres_clients_list",
        view_func=list_clients,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/clients/<int:client_id>/token/rotate",
        endpoint="postgres_clients_rotate_token",
        view_func=rotate_client_token,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/clients/<int:client_id>",
        endpoint="postgres_clients_disable",
        view_func=disable_client,
        methods=["DELETE"],
    )
    app.add_url_rule(
        "/api/clients/<int:client_id>",
        endpoint="postgres_clients_details",
        view_func=client_details,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/clients/<int:client_id>/updates",
        endpoint="postgres_clients_updates",
        view_func=client_updates,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/clients/<int:client_id>/packages",
        endpoint="postgres_clients_packages",
        view_func=client_packages,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/client/me",
        endpoint="postgres_clients_me",
        view_func=client_me,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/report",
        endpoint="postgres_clients_report",
        view_func=client_report,
        methods=["POST"],
    )


__all__ = [
    "_get_connection",
    "_lock_authenticated_client",
    "register_postgres_client_routes",
    "validate_client_report",
]
