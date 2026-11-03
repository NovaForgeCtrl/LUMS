"""PostgreSQL-native LUMS alert management routes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from flask import current_app, jsonify, request
from psycopg.types.json import Jsonb

if __package__:
    from .db_errors import (
        DatabaseDriverError,
        DatabaseIntegrityError,
    )
    from .db_transactions import transaction
    from .postgres_audit import audit_log
    from .postgres_flask_security import (
        csrf_required,
        current_user_id,
        login_required,
        role_required,
    )
else:
    from db_errors import (
        DatabaseDriverError,
        DatabaseIntegrityError,
    )
    from db_transactions import transaction
    from postgres_audit import audit_log
    from postgres_flask_security import (
        csrf_required,
        current_user_id,
        login_required,
        role_required,
    )


ALERT_SEVERITIES = frozenset({
    "critical", "warning", "info"
})

ALERT_STATUSES = frozenset({
    "triggered", "acknowledged", "resolved", "escalated"
})

ACTIVE_ALERT_STATUSES = (
    "triggered", "acknowledged", "escalated"
)

RULE_FIELDS = (
    "rule_id",
    "name",
    "description",
    "condition",
    "threshold",
    "severity",
    "enabled",
    "escalation_path",
    "group_similar",
    "deduplicate",
    "created_at",
)

ALERT_FIELDS = (
    "alert_id",
    "rule_id",
    "source",
    "message",
    "severity",
    "status",
    "metadata",
    "triggered_at",
    "acknowledged_at",
    "resolved_at",
    "escalation_count",
)


def _get_connection():
    factory = current_app.config.get(
        "LUMS_POSTGRES_GET_CONNECTION"
    )
    if not callable(factory):
        raise RuntimeError(
            "PostgreSQL connection factory is not configured"
        )
    return factory()


def _close_connection(connection):
    if connection is not None and not connection.closed:
        connection.close()


def _iso_timestamp(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return value


def _json_object(value):
    """Psycopg already decodes JSONB; never decode native strings again."""
    return value if isinstance(value, dict) else {}


def _json_array(value):
    """Return a decoded JSONB array or an empty list for invalid data."""
    return value if isinstance(value, list) else []


def _rule_dict(row):
    return {
        "rule_id": row["rule_id"],
        "name": row["name"],
        "description": row["description"] or "",
        "condition": row["condition"],
        "threshold": row["threshold"],
        "severity": row["severity"],
        "enabled": row["enabled"],
        "escalation_path": _json_array(row["escalation_path"]),
        "group_similar": row["group_similar"],
        "deduplicate": row["deduplicate"],
        "created_at": _iso_timestamp(row["created_at"]),
    }


def _alert_dict(row):
    return {
        "alert_id": row["alert_id"],
        "rule_id": row["rule_id"],
        "source": row["source"],
        "message": row["message"],
        "severity": row["severity"],
        "status": row["status"],
        "metadata": _json_object(row["metadata"]),
        "triggered_at": _iso_timestamp(row["triggered_at"]),
        "acknowledged_at": _iso_timestamp(row["acknowledged_at"]),
        "resolved_at": _iso_timestamp(row["resolved_at"]),
        "escalation_count": row["escalation_count"],
    }


def _validate_alert_rule_payload(data, existing=None):
    """Apply the existing alert-rule input contract."""
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")

    allowed = {
        "name",
        "description",
        "condition",
        "threshold",
        "severity",
        "enabled",
        "escalation_path",
        "group_similar",
        "deduplicate",
    }
    if set(data) - allowed:
        raise ValueError("Unknown alert rule field")

    def prior(field, default):
        if existing is not None:
            value = existing.get(field, default)
        else:
            value = default

        return value

    values = {
        "name": data.get("name", prior("name", None)),
        "description": data.get(
            "description",
            prior("description", ""),
        ),
        "condition": data.get(
            "condition",
            prior("condition", None),
        ),
        "threshold": data.get(
            "threshold",
            prior("threshold", None),
        ),
        "severity": data.get(
            "severity",
            prior("severity", "warning"),
        ),
        "enabled": data.get("enabled", prior("enabled", True)),
        "escalation_path": data.get(
            "escalation_path",
            prior("escalation_path", []),
        ),
        "group_similar": data.get(
            "group_similar",
            prior("group_similar", True),
        ),
        "deduplicate": data.get(
            "deduplicate",
            prior("deduplicate", True),
        ),
    }

    for field in ("name", "condition"):
        if (
            not isinstance(values[field], str)
            or not values[field].strip()
        ):
            raise ValueError(f"Invalid {field}")

    if not isinstance(values["description"], str):
        raise ValueError("Invalid description")

    if (
        not isinstance(values["severity"], str)
        or values["severity"] not in ALERT_SEVERITIES
    ):
        raise ValueError("Invalid severity")

    for field in ("enabled", "group_similar", "deduplicate"):
        if not isinstance(values[field], bool):
            raise ValueError(f"Invalid {field}")

    path = values["escalation_path"]
    if not isinstance(path, list) or any(
        not isinstance(item, str) or not item.strip()
        for item in path
    ):
        raise ValueError("Invalid escalation_path")

    json.dumps(values["threshold"], allow_nan=False)
    return values


def _write_audit(
    connection,
    action,
    target,
    details=None,
):
    audit_log(
        connection,
        actor_type="user",
        actor_id=current_user_id(),
        action=action,
        target=target,
        result="success",
        details=details,
    )


def register_postgres_alert_routes(app):
    """Register PostgreSQL-native alert management API routes."""

    @login_required
    @role_required(permission="alerts.view")
    def list_rules():
        connection = None
        try:
            connection = _get_connection()
            with transaction(connection):
                rows = connection.execute(
                    """
                    SELECT rule_id, name, description, condition,
                           threshold, severity, enabled, escalation_path,
                           group_similar, deduplicate, created_at
                    FROM alert_rules
                    ORDER BY created_at DESC, rule_id ASC
                    """
                ).fetchall()

            return jsonify({
                "rules": [_rule_dict(row) for row in rows]
            }), 200

        except DatabaseDriverError:
            current_app.logger.exception(
                "Failed to load PostgreSQL alert rules"
            )
            return jsonify({
                "error": "alert_rules_load_failed"
            }), 500

        finally:
            _close_connection(connection)

    @login_required
    @role_required(permission="alerts.manage")
    @csrf_required
    def create_rule():
        data = request.get_json(silent=True)

        try:
            values = _validate_alert_rule_payload(data)
        except (TypeError, ValueError, OverflowError):
            return jsonify({"error": "Invalid request"}), 400

        rule_id = str(uuid.uuid4())
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                row = connection.execute(
                    """
                    INSERT INTO alert_rules (
                        rule_id,
                        name,
                        description,
                        condition,
                        threshold,
                        severity,
                        enabled,
                        escalation_path,
                        group_similar,
                        deduplicate
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING
                        rule_id, name, description, condition,
                        threshold, severity, enabled, escalation_path,
                        group_similar, deduplicate, created_at
                    """,
                    (
                        rule_id,
                        values["name"],
                        values["description"],
                        values["condition"],
                        Jsonb(values["threshold"]),
                        values["severity"],
                        values["enabled"],
                        Jsonb(values["escalation_path"]),
                        values["group_similar"],
                        values["deduplicate"],
                    ),
                ).fetchone()

                if row is None:
                    raise RuntimeError(
                        "PostgreSQL did not return the created alert rule"
                    )

                _write_audit(
                    connection,
                    "alerts.rule.create",
                    f"alert-rule:{rule_id}",
                )

            return jsonify({
                "message": "Rule created successfully",
                "rule": _rule_dict(row),
            }), 201

        except DatabaseDriverError:
            current_app.logger.exception(
                "Failed to create PostgreSQL alert rule"
            )
            return jsonify({
                "error": "alert_rule_create_failed"
            }), 500

        finally:
            _close_connection(connection)

    @login_required
    @role_required(permission="alerts.manage")
    @csrf_required
    def update_rule(rule_id):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid request"}), 400

        connection = None
        try:
            connection = _get_connection()

            with transaction(connection):
                existing = connection.execute(
                    """
                    SELECT rule_id, name, description, condition,
                           threshold, severity, enabled, escalation_path,
                           group_similar, deduplicate, created_at
                    FROM alert_rules
                    WHERE rule_id = %s
                    FOR UPDATE
                    """,
                    (rule_id,),
                ).fetchone()

                if existing is None:
                    return jsonify({"error": "Rule not found"}), 404

                try:
                    values = _validate_alert_rule_payload(
                        data,
                        existing=existing,
                    )
                except (TypeError, ValueError, OverflowError):
                    return jsonify({"error": "Invalid request"}), 400

                row = connection.execute(
                    """
                    UPDATE alert_rules
                    SET
                        name = %s,
                        description = %s,
                        condition = %s,
                        threshold = %s,
                        severity = %s,
                        enabled = %s,
                        escalation_path = %s,
                        group_similar = %s,
                        deduplicate = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE rule_id = %s
                    RETURNING
                        rule_id, name, description, condition,
                        threshold, severity, enabled, escalation_path,
                        group_similar, deduplicate, created_at
                    """,
                    (
                        values["name"],
                        values["description"],
                        values["condition"],
                        Jsonb(values["threshold"]),
                        values["severity"],
                        values["enabled"],
                        Jsonb(values["escalation_path"]),
                        values["group_similar"],
                        values["deduplicate"],
                        rule_id,
                    ),
                ).fetchone()

                if row is None:
                    return jsonify({"error": "Rule not found"}), 404

                _write_audit(
                    connection,
                    "alerts.rule.update",
                    f"alert-rule:{rule_id}",
                )

            return jsonify({
                "message": "Rule updated successfully",
                "rule": _rule_dict(row),
            }), 200

        except DatabaseDriverError:
            current_app.logger.exception(
                "Failed to update PostgreSQL alert rule %s",
                rule_id,
            )
            return jsonify({
                "error": "alert_rule_update_failed"
            }), 500

        finally:
            _close_connection(connection)

    @login_required
    @role_required(permission="alerts.manage")
    @csrf_required
    def delete_rule(rule_id):
        connection = None
        try:
            connection = _get_connection()

            with transaction(connection):
                deleted = connection.execute(
                    """
                    DELETE FROM alert_rules
                    WHERE rule_id = %s
                    RETURNING rule_id
                    """,
                    (rule_id,),
                ).fetchone()

                if deleted is None:
                    return jsonify({"error": "Rule not found"}), 404

                _write_audit(
                    connection,
                    "alerts.rule.delete",
                    f"alert-rule:{rule_id}",
                )

            return jsonify({
                "message": "Rule deleted successfully"
            }), 200

        except DatabaseIntegrityError:
            return jsonify({
                "error": "Rule cannot be deleted while it is referenced"
            }), 409

        except DatabaseDriverError:
            current_app.logger.exception(
                "Failed to delete PostgreSQL alert rule %s",
                rule_id,
            )
            return jsonify({
                "error": "alert_rule_delete_failed"
            }), 500

        finally:
            _close_connection(connection)

    @login_required
    @role_required(permission="alerts.view")
    def get_current_alerts():
        connection = None
        try:
            connection = _get_connection()

            with transaction(connection):
                rows = connection.execute(
                    """
                    SELECT alert_id, rule_id, source, message, severity,
                           status, metadata, triggered_at, acknowledged_at,
                           resolved_at, escalation_count
                    FROM alerts
                    WHERE status IN (
                        'triggered', 'acknowledged', 'escalated'
                    )
                    ORDER BY triggered_at DESC, alert_id ASC
                    """
                ).fetchall()

            alerts = [_alert_dict(row) for row in rows]
            return jsonify({
                "alerts": alerts,
                "count": len(alerts),
            }), 200

        except DatabaseDriverError:
            current_app.logger.exception(
                "Failed to load current PostgreSQL alerts"
            )
            return jsonify({
                "error": "current_alerts_load_failed"
            }), 500

        finally:
            _close_connection(connection)

    @login_required
    @role_required(permission="alerts.view")
    def get_alert_history():
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)
        safe_limit = max(1, min(limit or 100, 1000))
        safe_offset = max(0, offset or 0)
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                rows = connection.execute(
                    """
                    SELECT alert_id, rule_id, source, message, severity,
                           status, metadata, triggered_at, acknowledged_at,
                           resolved_at, escalation_count
                    FROM alerts
                    ORDER BY triggered_at DESC, alert_id ASC
                    LIMIT %s OFFSET %s
                    """,
                    (safe_limit, safe_offset),
                ).fetchall()

            alerts = [_alert_dict(row) for row in rows]
            return jsonify({
                "alerts": alerts,
                "count": len(alerts),
            }), 200

        except DatabaseDriverError:
            current_app.logger.exception(
                "Failed to load PostgreSQL alert history"
            )
            return jsonify({
                "error": "alert_history_load_failed"
            }), 500

        finally:
            _close_connection(connection)

    @login_required
    @role_required(permission="alerts.manage")
    @csrf_required
    def trigger_alert():
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({"error": "Invalid request"}), 400

        allowed = {"rule_id", "source", "message", "metadata"}
        if set(data) - allowed:
            return jsonify({"error": "Invalid request"}), 400

        rule_id = data.get("rule_id")
        message = data.get("message")
        source = data.get("source", "api")
        metadata = data.get("metadata")

        if (
            not isinstance(rule_id, str)
            or not rule_id.strip()
            or not isinstance(message, str)
            or not message.strip()
            or not isinstance(source, str)
            or not source.strip()
        ):
            return jsonify({"error": "Invalid request"}), 400

        if metadata is not None and not isinstance(metadata, dict):
            return jsonify({"error": "Invalid request"}), 400

        metadata = metadata or {}
        try:
            json.dumps(metadata, allow_nan=False)
        except (TypeError, ValueError, OverflowError):
            return jsonify({"error": "Invalid request"}), 400

        rule_id = rule_id.strip()
        message = message.strip()
        source = source.strip()
        alert_id = f"{rule_id}_{uuid.uuid4()}"
        triggered_at = datetime.now(timezone.utc)
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                rule = connection.execute(
                    """
                    SELECT rule_id, severity, enabled
                    FROM alert_rules
                    WHERE rule_id = %s
                    FOR SHARE
                    """,
                    (rule_id,),
                ).fetchone()

                if rule is None or rule["enabled"] is not True:
                    return jsonify({
                        "error": "Failed to trigger alert"
                    }), 400

                row = connection.execute(
                    """
                    INSERT INTO alerts (
                        alert_id,
                        rule_id,
                        source,
                        message,
                        severity,
                        status,
                        metadata,
                        triggered_at
                    )
                    VALUES (%s, %s, %s, %s, %s, 'triggered', %s, %s)
                    RETURNING
                        alert_id, rule_id, source, message, severity,
                        status, metadata, triggered_at, acknowledged_at,
                        resolved_at, escalation_count
                    """,
                    (
                        alert_id,
                        rule_id,
                        source,
                        message,
                        rule["severity"],
                        Jsonb(metadata),
                        triggered_at,
                    ),
                ).fetchone()

                if row is None:
                    raise RuntimeError(
                        "PostgreSQL did not return the triggered alert"
                    )

                _write_audit(
                    connection,
                    "alerts.trigger",
                    f"alert:{alert_id}",
                    details=f"rule_id={rule_id} source={source}",
                )

            return jsonify({
                "message": "Alert triggered successfully",
                "alert": _alert_dict(row),
            }), 201

        except DatabaseDriverError:
            current_app.logger.exception(
                "Failed to trigger PostgreSQL alert for rule %s",
                rule_id,
            )
            return jsonify({
                "error": "alert_trigger_failed"
            }), 500

        finally:
            _close_connection(connection)

    @login_required
    @role_required(permission="alerts.manage")
    @csrf_required
    def acknowledge_alert(alert_id):
        actor_id = str(current_user_id())
        changed_at = datetime.now(timezone.utc)
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                alert = connection.execute(
                    """
                    SELECT status, metadata
                    FROM alerts
                    WHERE alert_id = %s
                    FOR UPDATE
                    """,
                    (alert_id,),
                ).fetchone()

                if alert is None or alert["status"] not in (
                    "triggered",
                    "escalated",
                ):
                    return jsonify({"error": "Alert not found"}), 404

                metadata = {
                    **_json_object(alert["metadata"]),
                    "acknowledged_by": actor_id,
                }

                updated = connection.execute(
                    """
                    UPDATE alerts
                    SET status = %s,
                        acknowledged_at = %s,
                        metadata = %s
                    WHERE alert_id = %s
                      AND status IN ('triggered', 'escalated')
                    RETURNING alert_id
                    """,
                    (
                        "acknowledged",
                        changed_at,
                        Jsonb(metadata),
                        alert_id,
                    ),
                ).fetchone()

                if updated is None:
                    return jsonify({"error": "Alert not found"}), 404

                connection.execute(
                    """
                    INSERT INTO alert_history (
                        alert_id, status, changed_at, changed_by, reason
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        alert_id,
                        "acknowledged",
                        changed_at,
                        actor_id,
                        "Alert acknowledged",
                    ),
                )

                _write_audit(
                    connection,
                    "alerts.acknowledge",
                    f"alert:{alert_id}",
                )

            return jsonify({"message": "Alert acknowledged"}), 200

        except DatabaseDriverError:
            current_app.logger.exception(
                "Failed to acknowledge PostgreSQL alert %s",
                alert_id,
            )
            return jsonify({
                "error": "alert_acknowledge_failed"
            }), 500

        finally:
            _close_connection(connection)

    @login_required
    @role_required(permission="alerts.manage")
    @csrf_required
    def resolve_alert(alert_id):
        actor_id = str(current_user_id())
        changed_at = datetime.now(timezone.utc)
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                alert = connection.execute(
                    """
                    SELECT status
                    FROM alerts
                    WHERE alert_id = %s
                    FOR UPDATE
                    """,
                    (alert_id,),
                ).fetchone()

                if alert is None or alert["status"] not in (
                    "triggered",
                    "acknowledged",
                    "escalated",
                ):
                    return jsonify({"error": "Alert not found"}), 404

                updated = connection.execute(
                    """
                    UPDATE alerts
                    SET status = %s,
                        resolved_at = %s
                    WHERE alert_id = %s
                      AND status IN (
                          'triggered', 'acknowledged', 'escalated'
                      )
                    RETURNING alert_id
                    """,
                    (
                        "resolved",
                        changed_at,
                        alert_id,
                    ),
                ).fetchone()

                if updated is None:
                    return jsonify({"error": "Alert not found"}), 404

                connection.execute(
                    """
                    INSERT INTO alert_history (
                        alert_id, status, changed_at, changed_by, reason
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        alert_id,
                        "resolved",
                        changed_at,
                        actor_id,
                        "Alert resolved",
                    ),
                )

                _write_audit(
                    connection,
                    "alerts.resolve",
                    f"alert:{alert_id}",
                )

            return jsonify({"message": "Alert resolved"}), 200

        except DatabaseDriverError:
            current_app.logger.exception(
                "Failed to resolve PostgreSQL alert %s",
                alert_id,
            )
            return jsonify({
                "error": "alert_resolve_failed"
            }), 500

        finally:
            _close_connection(connection)

    @login_required
    @role_required(permission="alerts.manage")
    @csrf_required
    def escalate_alert(alert_id):
        actor_id = str(current_user_id())
        changed_at = datetime.now(timezone.utc)
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                alert = connection.execute(
                    """
                    SELECT status, escalation_count
                    FROM alerts
                    WHERE alert_id = %s
                    FOR UPDATE
                    """,
                    (alert_id,),
                ).fetchone()

                if alert is None:
                    return jsonify({"error": "Alert not found"}), 404

                if alert["status"] not in ACTIVE_ALERT_STATUSES:
                    return jsonify({
                        "error": "Alert could not be escalated"
                    }), 409

                new_count = int(alert["escalation_count"] or 0) + 1

                updated = connection.execute(
                    """
                    UPDATE alerts
                    SET status = %s,
                        escalation_count = %s
                    WHERE alert_id = %s
                      AND status IN (
                          'triggered', 'acknowledged', 'escalated'
                      )
                    RETURNING escalation_count
                    """,
                    (
                        "escalated",
                        new_count,
                        alert_id,
                    ),
                ).fetchone()

                if updated is None:
                    return jsonify({
                        "error": "Alert could not be escalated"
                    }), 409

                connection.execute(
                    """
                    INSERT INTO alert_history (
                        alert_id, status, changed_at, changed_by, reason
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        alert_id,
                        "escalated",
                        changed_at,
                        actor_id,
                        f"Alert escalated to level {new_count}",
                    ),
                )

                _write_audit(
                    connection,
                    "alerts.escalate",
                    f"alert:{alert_id}",
                    details=f"escalation_count={new_count}",
                )

            return jsonify({
                "message": "Alert escalated",
                "escalation_count": new_count,
            }), 200

        except DatabaseDriverError:
            current_app.logger.exception(
                "Failed to escalate PostgreSQL alert %s",
                alert_id,
            )
            return jsonify({
                "error": "alert_escalate_failed"
            }), 500

        finally:
            _close_connection(connection)

    app.add_url_rule(
        "/alerts/<alert_id>/acknowledge",
        endpoint="postgres_alert_acknowledge",
        view_func=acknowledge_alert,
        methods=["POST"],
    )
    app.add_url_rule(
        "/alerts/<alert_id>/resolve",
        endpoint="postgres_alert_resolve",
        view_func=resolve_alert,
        methods=["POST"],
    )
    app.add_url_rule(
        "/alerts/<alert_id>/escalate",
        endpoint="postgres_alert_escalate",
        view_func=escalate_alert,
        methods=["POST"],
    )
    app.add_url_rule(
        "/alerts/current",
        endpoint="postgres_alert_current",
        view_func=get_current_alerts,
        methods=["GET"],
    )
    app.add_url_rule(
        "/alerts/history",
        endpoint="postgres_alert_history",
        view_func=get_alert_history,
        methods=["GET"],
    )
    app.add_url_rule(
        "/alerts/trigger",
        endpoint="postgres_alert_trigger",
        view_func=trigger_alert,
        methods=["POST"],
    )
    app.add_url_rule(
        "/alerts/rules",
        endpoint="postgres_alert_list_rules",
        view_func=list_rules,
        methods=["GET"],
    )
    app.add_url_rule(
        "/alerts/rules",
        endpoint="postgres_alert_create_rule",
        view_func=create_rule,
        methods=["POST"],
    )
    app.add_url_rule(
        "/alerts/rules/<rule_id>",
        endpoint="postgres_alert_update_rule",
        view_func=update_rule,
        methods=["PUT"],
    )
    app.add_url_rule(
        "/alerts/rules/<rule_id>",
        endpoint="postgres_alert_delete_rule",
        view_func=delete_rule,
        methods=["DELETE"],
    )


__all__ = [
    "register_postgres_alert_routes",
]
