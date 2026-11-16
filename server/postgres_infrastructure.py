"""PostgreSQL-native infrastructure topology routes for LUMS."""

from __future__ import annotations

import ipaddress
from datetime import datetime, timezone

from flask import current_app, jsonify, render_template, request

if __package__:
    from .db_errors import DatabaseDriverError, DatabaseIntegrityError
    from .db_transactions import transaction
    from .postgres_audit import audit_log
    from .postgres_flask_security import (
        current_user_id,
        current_user_permissions,
        current_user_role,
        csrf_required,
        get_csrf_token,
        login_required,
        role_required,
    )
    from .security import (
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
    )
else:
    from db_errors import DatabaseDriverError, DatabaseIntegrityError
    from db_transactions import transaction
    from postgres_audit import audit_log
    from postgres_flask_security import (
        current_user_id,
        current_user_permissions,
        current_user_role,
        csrf_required,
        get_csrf_token,
        login_required,
        role_required,
    )
    from security import (
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
    )


INFRASTRUCTURE_NODE_TYPES = frozenset({
    "server",
    "vm",
    "container",
    "network_device",
    "service",
    "storage",
})

INFRASTRUCTURE_RELATION_TYPES = frozenset({
    "depends_on",
    "hosts",
    "connects_to",
    "runs_on",
})

TOPOLOGY_FIELD_LIMITS = {
    "name": 120,
    "hostname": 253,
    "ip_address": 45,
    "role": 120,
    "location": 120,
    "notes": 1000,
    "details": 500,
}

RELATION_UNIQUE_INDEXES = frozenset({
    "uq_infrastructure_relations_node_node_type",
    "uq_infrastructure_relations_node_client_type",
    "uq_infrastructure_relations_client_node_type",
    "uq_infrastructure_relations_client_client_type",
})

RELATION_ENDPOINT_FOREIGN_KEYS = frozenset({
    "fk_infrastructure_relations_source_node",
    "fk_infrastructure_relations_source_client",
    "fk_infrastructure_relations_target_node",
    "fk_infrastructure_relations_target_client",
})


def _get_connection():
    factory = current_app.config.get(
        "LUMS_POSTGRES_GET_CONNECTION"
    )

    if not callable(factory):
        raise RuntimeError(
            "PostgreSQL connection factory is not configured"
        )

    return factory()


def classify_health_client(last_seen, now=None):
    """Classify PostgreSQL datetime or ISO timestamp values safely."""
    if isinstance(last_seen, str):
        if not last_seen.strip():
            return "unknown"

        try:
            last_seen = datetime.fromisoformat(last_seen)
        except (TypeError, ValueError, OverflowError):
            return "unknown"

    if not isinstance(last_seen, datetime):
        return "unknown"

    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)

    current_time = now or datetime.now(timezone.utc)

    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    try:
        difference = (
            current_time - last_seen
        ).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return "unknown"

    if difference < 0:
        return "unknown"
    if difference <= 120:
        return "online"
    if difference <= 600:
        return "unknown"

    return "offline"


def topology_node_input(payload):
    if not isinstance(payload, dict):
        return None, "invalid_node"

    values = {}

    for key, maximum in TOPOLOGY_FIELD_LIMITS.items():
        if key == "details":
            continue

        value = payload.get(key, "")

        if not isinstance(value, str):
            return None, "invalid_node"

        value = value.strip()

        if len(value) > maximum:
            return None, "field_too_long"

        values[key] = value

    node_type = payload.get("node_type")

    if (
        not isinstance(node_type, str)
        or node_type not in INFRASTRUCTURE_NODE_TYPES
    ):
        return None, "invalid_node_type"

    if not values["name"]:
        return None, "name_required"

    if values["ip_address"]:
        try:
            ipaddress.ip_address(values["ip_address"])
        except ValueError:
            return None, "invalid_ip_address"

    values["node_type"] = node_type
    return values, None


def topology_endpoint_input(payload, prefix):
    if not isinstance(payload, dict):
        return None

    kind = payload.get(f"{prefix}_type")
    raw_id = payload.get(f"{prefix}_id")

    if not isinstance(kind, str) or kind not in {"client", "node"}:
        return None

    if isinstance(raw_id, bool):
        return None

    if isinstance(raw_id, int):
        entity_id = raw_id
    elif isinstance(raw_id, str) and raw_id.isdecimal():
        try:
            entity_id = int(raw_id)
        except ValueError:
            return None
    else:
        return None

    if entity_id < 1:
        return None

    return kind, entity_id


def _constraint_name(error):
    diagnostic = getattr(error, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def is_duplicate_relation_error(error):
    return (
        getattr(error, "sqlstate", None) == "23505"
        and _constraint_name(error) in RELATION_UNIQUE_INDEXES
    )


def is_relation_endpoint_error(error):
    return (
        getattr(error, "sqlstate", None) == "23503"
        and _constraint_name(error) in RELATION_ENDPOINT_FOREIGN_KEYS
    )


def _topology_payload(connection):
    clients = connection.execute(
        """
        SELECT
            id,
            COALESCE(hostname, '') AS hostname,
            COALESCE(ip, '') AS ip,
            COALESCE(os, '') AS os,
            last_seen,
            enabled
        FROM clients
        ORDER BY lower(COALESCE(hostname, '')), id
        """
    ).fetchall()

    manual_nodes = connection.execute(
        """
        SELECT
            id,
            name,
            node_type,
            hostname,
            ip_address,
            role,
            location,
            notes,
            created_at,
            updated_at
        FROM infrastructure_nodes
        ORDER BY lower(name), id
        """
    ).fetchall()

    relation_rows = connection.execute(
        """
        SELECT
            id,
            source_node_id,
            source_client_id,
            target_node_id,
            target_client_id,
            relation_type,
            details
        FROM infrastructure_relations
        ORDER BY id
        """
    ).fetchall()

    nodes = [
        {
            "id": f"client:{row['id']}",
            "entity_type": "client",
            "entity_id": row["id"],
            "name": row["hostname"],
            "node_type": "client",
            "hostname": row["hostname"],
            "ip_address": row["ip"],
            "role": row["os"],
            "location": "",
            "status": (
                classify_health_client(row["last_seen"])
                if row["enabled"] else "disabled"
            ),
            "editable": False,
        }
        for row in clients
    ]

    nodes.extend(
        {
            "id": f"node:{row['id']}",
            "entity_type": "node",
            "entity_id": row["id"],
            "name": row["name"],
            "node_type": row["node_type"],
            "hostname": row["hostname"],
            "ip_address": row["ip_address"],
            "role": row["role"],
            "location": row["location"],
            "notes": row["notes"],
            "updated_at": row["updated_at"],
            "status": "unknown",
            "editable": True,
        }
        for row in manual_nodes
    )

    relations = [
        {
            "id": row["id"],
            "source": {
                "type": (
                    "node"
                    if row["source_node_id"] is not None
                    else "client"
                ),
                "id": (
                    row["source_node_id"]
                    if row["source_node_id"] is not None
                    else row["source_client_id"]
                ),
            },
            "target": {
                "type": (
                    "node"
                    if row["target_node_id"] is not None
                    else "client"
                ),
                "id": (
                    row["target_node_id"]
                    if row["target_node_id"] is not None
                    else row["target_client_id"]
                ),
            },
            "relation_type": row["relation_type"],
            "details": row["details"],
        }
        for row in relation_rows
    ]

    return {
        "nodes": nodes,
        "relations": relations,
    }


def register_postgres_infrastructure_routes(app):
    """Register the topology routes on the isolated PostgreSQL app."""

    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="clients.view",
    )
    def infrastructure_page():
        permissions = current_user_permissions()
        role = current_user_role()

        return render_template(
            "postgres_infrastructure.html",
            csrf_token=get_csrf_token(),
            user_role=role,
            user_permissions=permissions,
            can_manage=(
                role == ROLE_ADMINISTRATOR
                and "infrastructure.manage" in permissions
            ),
        )

    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="clients.view",
    )
    def infrastructure_topology():
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL "
                    "REPEATABLE READ, READ ONLY"
                )
                payload = _topology_payload(connection)

            return jsonify(payload)

        except DatabaseDriverError:
            current_app.logger.exception(
                "Unable to load PostgreSQL infrastructure topology."
            )
            return jsonify({
                "error": "topology_load_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    @login_required
    @role_required(ROLE_ADMINISTRATOR)
    @role_required(permission="infrastructure.manage")
    @csrf_required
    def create_infrastructure_node():
        values, error = topology_node_input(
            request.get_json(silent=True)
        )

        if error:
            return jsonify({"error": error}), 400

        timestamp = datetime.now(timezone.utc).isoformat()
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                row = connection.execute(
                    """
                    INSERT INTO infrastructure_nodes (
                        name,
                        node_type,
                        hostname,
                        ip_address,
                        role,
                        location,
                        notes,
                        created_at,
                        updated_at,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        values["name"],
                        values["node_type"],
                        values["hostname"],
                        values["ip_address"],
                        values["role"],
                        values["location"],
                        values["notes"],
                        timestamp,
                        timestamp,
                        current_user_id(),
                    ),
                ).fetchone()

                if row is None:
                    raise RuntimeError(
                        "PostgreSQL did not return the infrastructure node ID"
                    )

                node_id = row["id"]

                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=current_user_id(),
                    action="infrastructure.node.create",
                    target=str(node_id),
                )

            return jsonify({"id": node_id}), 201

        except DatabaseDriverError:
            current_app.logger.exception(
                "Unable to create PostgreSQL infrastructure node."
            )
            return jsonify({
                "error": "topology_save_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    @login_required
    @role_required(ROLE_ADMINISTRATOR)
    @role_required(permission="infrastructure.manage")
    @csrf_required
    def update_or_delete_infrastructure_node(node_id):
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                existing = connection.execute(
                    """
                    SELECT id
                    FROM infrastructure_nodes
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (node_id,),
                ).fetchone()

                if existing is None:
                    return jsonify({
                        "error": "node_not_found"
                    }), 404

                if request.method == "DELETE":
                    # Migration 005 has ON DELETE CASCADE for relationships.
                    connection.execute(
                        """
                        DELETE FROM infrastructure_nodes
                        WHERE id = %s
                        """,
                        (node_id,),
                    )

                    audit_log(
                        connection,
                        actor_type="user",
                        actor_id=current_user_id(),
                        action="infrastructure.node.delete",
                        target=str(node_id),
                    )

                else:
                    values, error = topology_node_input(
                        request.get_json(silent=True)
                    )

                    if error:
                        return jsonify({"error": error}), 400

                    connection.execute(
                        """
                        UPDATE infrastructure_nodes
                        SET
                            name = %s,
                            node_type = %s,
                            hostname = %s,
                            ip_address = %s,
                            role = %s,
                            location = %s,
                            notes = %s,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        (
                            values["name"],
                            values["node_type"],
                            values["hostname"],
                            values["ip_address"],
                            values["role"],
                            values["location"],
                            values["notes"],
                            datetime.now(timezone.utc).isoformat(),
                            node_id,
                        ),
                    )

                    audit_log(
                        connection,
                        actor_type="user",
                        actor_id=current_user_id(),
                        action="infrastructure.node.update",
                        target=str(node_id),
                    )

            return jsonify({"status": "saved"})

        except DatabaseDriverError:
            current_app.logger.exception(
                "Unable to change PostgreSQL infrastructure node %s.",
                node_id,
            )
            return jsonify({
                "error": "topology_save_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    @login_required
    @role_required(ROLE_ADMINISTRATOR)
    @role_required(permission="infrastructure.manage")
    @csrf_required
    def create_infrastructure_relation():
        payload = request.get_json(silent=True)

        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_relation"}), 400

        source = topology_endpoint_input(payload, "source")
        target = topology_endpoint_input(payload, "target")
        relation_type = payload.get("relation_type")
        details = payload.get("details", "")

        if (
            source is None
            or target is None
            or source == target
            or not isinstance(relation_type, str)
            or relation_type not in INFRASTRUCTURE_RELATION_TYPES
            or not isinstance(details, str)
            or len(details.strip()) > TOPOLOGY_FIELD_LIMITS["details"]
        ):
            return jsonify({"error": "invalid_relation"}), 400

        source_node_id = source[1] if source[0] == "node" else None
        source_client_id = source[1] if source[0] == "client" else None
        target_node_id = target[1] if target[0] == "node" else None
        target_client_id = target[1] if target[0] == "client" else None

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                for kind, entity_id in (source, target):
                    table = (
                        "clients"
                        if kind == "client"
                        else "infrastructure_nodes"
                    )

                    exists = connection.execute(
                        f"""
                        SELECT id
                        FROM {table}
                        WHERE id = %s
                        FOR KEY SHARE
                        """,
                        (entity_id,),
                    ).fetchone()

                    if exists is None:
                        return jsonify({
                            "error": "topology_endpoint_not_found"
                        }), 404

                row = connection.execute(
                    """
                    INSERT INTO infrastructure_relations (
                        source_node_id,
                        source_client_id,
                        target_node_id,
                        target_client_id,
                        relation_type,
                        details,
                        created_at,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        source_node_id,
                        source_client_id,
                        target_node_id,
                        target_client_id,
                        relation_type,
                        details.strip(),
                        datetime.now(timezone.utc).isoformat(),
                        current_user_id(),
                    ),
                ).fetchone()

                if row is None:
                    raise RuntimeError(
                        "PostgreSQL did not return the relation ID"
                    )

                relation_id = row["id"]

                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=current_user_id(),
                    action="infrastructure.relation.create",
                    target=str(relation_id),
                )

            return jsonify({"id": relation_id}), 201

        except DatabaseIntegrityError as exc:
            if is_duplicate_relation_error(exc):
                return jsonify({"error": "relation_exists"}), 409

            if is_relation_endpoint_error(exc):
                return jsonify({
                    "error": "topology_endpoint_not_found"
                }), 404

            current_app.logger.exception(
                "PostgreSQL rejected infrastructure relationship data."
            )
            return jsonify({
                "error": "topology_save_failed"
            }), 500

        except DatabaseDriverError:
            current_app.logger.exception(
                "Unable to create PostgreSQL infrastructure relation."
            )
            return jsonify({
                "error": "topology_save_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    @login_required
    @role_required(ROLE_ADMINISTRATOR)
    @role_required(permission="infrastructure.manage")
    @csrf_required
    def delete_infrastructure_relation(relation_id):
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                row = connection.execute(
                    """
                    DELETE FROM infrastructure_relations
                    WHERE id = %s
                    RETURNING id
                    """,
                    (relation_id,),
                ).fetchone()

                if row is None:
                    return jsonify({
                        "error": "relation_not_found"
                    }), 404

                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=current_user_id(),
                    action="infrastructure.relation.delete",
                    target=str(relation_id),
                )

            return jsonify({"status": "saved"})

        except DatabaseDriverError:
            current_app.logger.exception(
                "Unable to delete PostgreSQL infrastructure relation %s.",
                relation_id,
            )
            return jsonify({
                "error": "topology_save_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    app.add_url_rule(
        "/infrastructure",
        endpoint="infrastructure_page",
        view_func=infrastructure_page,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/infrastructure/topology",
        endpoint="infrastructure_topology",
        view_func=infrastructure_topology,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/infrastructure/nodes",
        endpoint="create_infrastructure_node",
        view_func=create_infrastructure_node,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/infrastructure/nodes/<int:node_id>",
        endpoint="update_or_delete_infrastructure_node",
        view_func=update_or_delete_infrastructure_node,
        methods=["PUT", "DELETE"],
    )
    app.add_url_rule(
        "/api/infrastructure/relations",
        endpoint="create_infrastructure_relation",
        view_func=create_infrastructure_relation,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/infrastructure/relations/<int:relation_id>",
        endpoint="delete_infrastructure_relation",
        view_func=delete_infrastructure_relation,
        methods=["DELETE"],
    )


__all__ = [
    "INFRASTRUCTURE_NODE_TYPES",
    "INFRASTRUCTURE_RELATION_TYPES",
    "TOPOLOGY_FIELD_LIMITS",
    "classify_health_client",
    "is_duplicate_relation_error",
    "is_relation_endpoint_error",
    "register_postgres_infrastructure_routes",
    "topology_endpoint_input",
    "topology_node_input",
]
