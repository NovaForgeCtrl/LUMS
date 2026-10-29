"""
LUMS Alert Management API Routes
REST endpoints for alert and rule management
"""

from flask import (Blueprint, request, jsonify, session, render_template, current_app, g, Response)
from functools import wraps
from werkzeug.local import LocalProxy
import uuid
import json
import logging
import sqlite3

if __package__:
    from .alerts import (
        AlertManager, AlertRule, Alert, AlertSeverity, AlertStatus,
    )
    from .security import login_required, role_required, csrf_required, current_user_id, current_user_role, current_user_permissions, get_csrf_token
else:
    from alerts import (
        AlertManager, AlertRule, Alert, AlertSeverity, AlertStatus,
    )
    from security import login_required, role_required, csrf_required, current_user_id, current_user_role, current_user_permissions, get_csrf_token

logger = logging.getLogger(__name__)

alerts_bp = Blueprint('alerts', __name__, url_prefix='/alerts')

def _get_alert_manager():
    """Return a manager bound to this Flask application context/request."""
    manager = getattr(g, "lums_alert_manager", None)
    if manager is None:
        connection_factory = current_app.config.get("LUMS_GET_CONNECTION")
        if not callable(connection_factory):
            raise RuntimeError("Alert database connection factory is not configured")
        connection = connection_factory()
        try:
            manager = AlertManager(connection)
        except Exception:
            connection.close()
            raise
        g.lums_alert_connection = connection
        g.lums_alert_manager = manager
    return manager


# Resolve the manager lazily; never share one SQLite connection across requests.
alert_manager = LocalProxy(_get_alert_manager)


# ============================================================
# ALERT DASHBOARD
# ============================================================

@alerts_bp.route('/', methods=['GET'])
@login_required
@role_required(permission="alerts.view")
def alert_dashboard():
    """Render the LUMS alert dashboard using the shared application layout."""
    try:
        alerts = alert_manager.get_alerts(limit=50)
        return render_template(
            "alerts.html",
            alerts=alerts,
            csrf_token=get_csrf_token(),
            user_role=current_user_role(),
            user_permissions=sorted(current_user_permissions()),
        )
    except Exception:
        logger.exception("Error loading dashboard")
        return {"error": "Internal server error"}, 500


# ============================================================
# ALERT RULES
def _validate_alert_rule_payload(data, existing=None):
    """Validate rule input before changing memory or the database."""
    import json

    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")

    allowed = {
        "name", "description", "condition", "threshold", "severity",
        "enabled", "escalation_path", "group_similar", "deduplicate",
    }
    if set(data) - allowed:
        raise ValueError("Unknown alert rule field")

    def prior(field, default):
        value = getattr(existing, field, default) if existing is not None else default
        if field == "severity" and isinstance(value, AlertSeverity):
            return value.value
        return value

    values = {
        "name": data.get("name", prior("name", None)),
        "description": data.get("description", prior("description", "")),
        "condition": data.get("condition", prior("condition", None)),
        "threshold": data.get("threshold", prior("threshold", None)),
        "severity": data.get("severity", prior("severity", "warning")),
        "enabled": data.get("enabled", prior("enabled", True)),
        "escalation_path": data.get("escalation_path", prior("escalation_path", [])),
        "group_similar": data.get("group_similar", prior("group_similar", True)),
        "deduplicate": data.get("deduplicate", prior("deduplicate", True)),
    }

    for field in ("name", "condition"):
        if not isinstance(values[field], str) or not values[field].strip():
            raise ValueError(f"Invalid {field}")
    if not isinstance(values["description"], str):
        raise ValueError("Invalid description")

    values["severity"] = AlertSeverity(values["severity"])

    for field in ("enabled", "group_similar", "deduplicate"):
        if not isinstance(values[field], bool):
            raise ValueError(f"Invalid {field}")

    path = values["escalation_path"]
    if not isinstance(path, list) or any(
        not isinstance(item, str) or not item.strip() for item in path
    ):
        raise ValueError("Invalid escalation_path")

    json.dumps(values["threshold"], allow_nan=False)
    return values


# ============================================================

@alerts_bp.route('/rules', methods=['GET'])
@login_required
@role_required(permission="alerts.view")
def list_rules():
    """List all alert rules"""
    try:
        rules = [rule.to_dict() for rule in alert_manager.rules.values()]
        return jsonify({"rules": rules}), 200
    except Exception as e:
        logger.error(f"Error listing rules: {e}")
        return {"error": "Internal server error"}, 500


@alerts_bp.route('/rules', methods=['POST'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def create_rule():
    """Create new alert rule."""
    try:
        data = request.get_json(silent=True)
        values = _validate_alert_rule_payload(data)
        rule = AlertRule(rule_id=str(uuid.uuid4()), **values)

        if alert_manager.create_rule(rule):
            return jsonify({
                "message": "Rule created successfully",
                "rule": rule.to_dict()
            }), 201
        return {"error": "Failed to create rule"}, 500
    except (TypeError, ValueError, OverflowError):
        return {"error": "Invalid request"}, 400
    except Exception:
        logger.exception("Error creating alert rule")
        return {"error": "Internal server error"}, 500

@alerts_bp.route('/rules/<rule_id>', methods=['PUT'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def update_rule(rule_id):
    """Update an alert rule transactionally."""
    manager = alert_manager
    rule = manager.rules.get(rule_id)
    if rule is None:
        return {"error": "Rule not found"}, 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {"error": "Invalid request"}, 400

    try:
        # Validate candidate values before any persistent or in-memory change.
        values = _validate_alert_rule_payload(data, existing=rule)

        cursor = manager.db.execute(
            """
            UPDATE alert_rules
            SET name = ?, description = ?, condition = ?, threshold = ?,
                severity = ?, enabled = ?, escalation_path = ?,
                group_similar = ?, deduplicate = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE rule_id = ?
            """,
            (
                values["name"], values["description"], values["condition"],
                json.dumps(values["threshold"]), values["severity"].value,
                int(values["enabled"]), json.dumps(values["escalation_path"]),
                int(values["group_similar"]), int(values["deduplicate"]),
                rule_id,
            ),
        )
        if cursor.rowcount != 1:
            manager.db.rollback()
            return {"error": "Rule not found"}, 404
        manager.db.commit()

        # Publish the new in-memory state only after the commit succeeds.
        for field, value in values.items():
            setattr(rule, field, value)

        return jsonify({
            "message": "Rule updated successfully",
            "rule": rule.to_dict()
        }), 200
    except (TypeError, ValueError, OverflowError):
        manager.db.rollback()
        return {"error": "Invalid request"}, 400
    except Exception:
        manager.db.rollback()
        logger.exception("Failed to persist alert rule update")
        return {"error": "Internal server error"}, 500


@alerts_bp.route('/rules/<rule_id>', methods=['DELETE'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def delete_rule(rule_id):
    """Delete an alert rule using the request-scoped database connection."""
    manager = alert_manager

    if rule_id not in manager.rules:
        return {"error": "Rule not found"}, 404

    try:
        cursor = manager.db.execute(
            "DELETE FROM alert_rules WHERE rule_id = ?",
            (rule_id,),
        )
        if cursor.rowcount != 1:
            manager.db.rollback()
            return {"error": "Rule not found"}, 404

        manager.db.commit()
        manager.rules.pop(rule_id, None)

        return jsonify({"message": "Rule deleted successfully"}), 200

    except sqlite3.IntegrityError:
        manager.db.rollback()
        logger.warning(
            "Alert rule deletion rejected by a database constraint: %s",
            rule_id,
        )
        return {
            "error": "Rule cannot be deleted while it is referenced"
        }, 409
    except Exception:
        manager.db.rollback()
        logger.exception("Failed to persist alert rule deletion")
        return {"error": "Internal server error"}, 500


# ============================================================
# ALERTS
# ============================================================

@alerts_bp.route('/current', methods=['GET'])
@login_required
@role_required(permission="alerts.view")
def get_current_alerts():
    """Get current active alerts"""
    try:
        alerts = [alert.to_dict() for alert in alert_manager.active_alerts.values()]
        return jsonify({"alerts": alerts, "count": len(alerts)}), 200
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return {"error": "Internal server error"}, 500


@alerts_bp.route('/history', methods=['GET'])
@login_required
@role_required(permission="alerts.view")
def get_alert_history():
    """Get alert history"""
    try:
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)
        
        alerts = alert_manager.get_alerts(limit=limit, offset=offset)
        return jsonify({
            "alerts": [alert.to_dict() for alert in alerts],
            "count": len(alerts)
        }), 200
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return {"error": "Internal server error"}, 500


@alerts_bp.route('/trigger', methods=['POST'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def trigger_alert():
    """Manually trigger an alert after validating the JSON payload."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return {"error": "Invalid request"}, 400

    allowed = {"rule_id", "source", "message", "metadata"}
    if set(data) - allowed:
        return {"error": "Invalid request"}, 400

    for field in ("rule_id", "message"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            return {"error": "Invalid request"}, 400

    source_value = data.get("source", "api")
    if not isinstance(source_value, str) or not source_value.strip():
        return {"error": "Invalid request"}, 400

    metadata = data.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        return {"error": "Invalid request"}, 400

    try:
        alert = alert_manager.trigger_alert(
            rule_id=data["rule_id"].strip(),
            source=source_value.strip(),
            message=data["message"].strip(),
            metadata=metadata,
        )

        if alert:
            return jsonify({
                "message": "Alert triggered successfully",
                "alert": alert.to_dict()
            }), 201

        return {"error": "Failed to trigger alert"}, 400

    except (TypeError, ValueError, OverflowError):
        return {"error": "Invalid request"}, 400
    except Exception:
        logger.exception("Error triggering alert")
        return {"error": "Internal server error"}, 500


@alerts_bp.route('/<alert_id>/acknowledge', methods=['POST'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    try:
        user_id = str(current_user_id())
        
        if alert_manager.acknowledge_alert(alert_id, user_id):
            return jsonify({"message": "Alert acknowledged"}), 200
        else:
            return {"error": "Alert not found"}, 404
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        return {"error": "Internal server error"}, 500


@alerts_bp.route('/<alert_id>/resolve', methods=['POST'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def resolve_alert(alert_id):
    """Resolve an alert"""
    try:
        if alert_manager.resolve_alert(alert_id, str(current_user_id())):
            return jsonify({"message": "Alert resolved"}), 200
        else:
            return {"error": "Alert not found"}, 404
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        return {"error": "Internal server error"}, 500


@alerts_bp.route('/<alert_id>/escalate', methods=['POST'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def escalate_alert(alert_id):
    """Escalate an alert"""
    try:
        alert = alert_manager.active_alerts.get(alert_id)
        if not alert:
            return {"error": "Alert not found"}, 404
        
        escalation_count = alert_manager.escalate_alert(
            alert_id, str(current_user_id())
        )
        if escalation_count is None:
            return {"error": "Alert could not be escalated"}, 409
        return jsonify({
            "message": "Alert escalated",
            "escalation_count": escalation_count
        }), 200
    except Exception as e:
        logger.error(f"Error escalating alert: {e}")
        return {"error": "Internal server error"}, 500


@alerts_bp.route('/clear-all', methods=['POST'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def clear_all_alerts():
    """Clear all resolved alerts"""
    return {"error": "Bulk clearing is disabled to preserve alert history"}, 501


# ============================================================
# NOTIFICATIONS & INTEGRATIONS
# ============================================================

@alerts_bp.route('/integrations', methods=['GET'])
@login_required
@role_required(permission="alerts.view")
def list_integrations():
    """List configured notification integrations"""
    return jsonify({"integrations": [], "available": False}), 200


@alerts_bp.route('/integrations/email', methods=['POST'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def setup_email_integration():
    """Setup email notification integration"""
    return {"error": "Notification integrations are disabled pending secure persistent configuration"}, 501


@alerts_bp.route('/integrations/slack', methods=['POST'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def setup_slack_integration():
    """Setup Slack notification integration"""
    return {"error": "Notification integrations are disabled pending secure persistent configuration"}, 501


@alerts_bp.route('/integrations/pagerduty', methods=['POST'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def setup_pagerduty_integration():
    """Setup PagerDuty notification integration"""
    return {"error": "Notification integrations are disabled pending secure persistent configuration"}, 501


@alerts_bp.route('/integrations/webhook', methods=['POST'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def setup_webhook_integration():
    """Setup generic webhook integration"""
    return {"error": "Notification integrations are disabled pending secure persistent configuration"}, 501


@alerts_bp.route('/integrations/<integration_id>/test', methods=['POST'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def test_integration(integration_id):
    """Test notification integration"""
    return {"error": "Notification integrations are disabled pending secure persistent configuration"}, 501


@alerts_bp.route('/integrations/<integration_id>', methods=['DELETE'])
@login_required
@role_required(permission="alerts.manage")
@csrf_required
def remove_integration(integration_id):
    """Remove notification integration"""
    return {"error": "Notification integrations are disabled pending secure persistent configuration"}, 501


# ============================================================
# SOC LAB — SYNTHETISCHE SZENARIEN, KEINE PERSISTENZ
# ============================================================




# ============================================================
# PERSISTED LOG VIEW — READ ONLY
# ============================================================

def _log_table_exists(connection, table_name):
    """Check schema existence without creating or migrating tables."""
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _collect_persisted_log_rows(connection, source="", status="", query=""):
    """Read persisted SOC inbox and audit records without changing the database."""
    rows = []
    search = query.casefold().strip()

    if source in ("", "soc") and _log_table_exists(connection, "soc_event_inbox"):
        records = connection.execute("""
            SELECT inbox_id, agent_id, event_id, received_at,
                   processing_status, processed_at, last_error, payload_json
            FROM soc_event_inbox
            ORDER BY received_at DESC, inbox_id DESC
            LIMIT 5000
        """).fetchall()

        for record in records:
            item = dict(record)
            row = {
                "timestamp": item.get("received_at") or "",
                "source": "soc",
                "actor": item.get("agent_id") or "",
                "event": item.get("event_id") or "",
                "status": item.get("processing_status") or "",
                "details": item.get("last_error") or "",
                "record_id": item.get("inbox_id"),
                "processed_at": item.get("processed_at"),
                "payload": item.get("payload_json") or "",
            }
            rows.append(row)

    if source in ("", "audit") and _log_table_exists(connection, "audit_log"):
        records = connection.execute("""
            SELECT id, timestamp, actor_type, actor_id, action,
                   target, result, details
            FROM audit_log
            ORDER BY timestamp DESC, id DESC
            LIMIT 5000
        """).fetchall()

        for record in records:
            item = dict(record)
            rows.append({
                "timestamp": item.get("timestamp") or "",
                "source": "audit",
                "actor": " / ".join(
                    part for part in (
                        item.get("actor_type") or "",
                        item.get("actor_id") or "",
                    ) if part
                ),
                "event": item.get("action") or "",
                "status": item.get("result") or "",
                "details": " | ".join(
                    part for part in (
                        item.get("target") or "",
                        item.get("details") or "",
                    ) if part
                ),
                "record_id": item.get("id"),
                "processed_at": "",
                "payload": "",
            })

    if status:
        rows = [row for row in rows if row["status"].casefold() == status.casefold()]

    if search:
        rows = [
            row for row in rows
            if search in " ".join(str(value or "") for value in row.values()).casefold()
        ]

    rows.sort(key=lambda row: row["timestamp"], reverse=True)
    return rows


def _log_query_parameters():
    source = request.args.get("source", "").strip().lower()
    status = request.args.get("status", "").strip().lower()
    query = request.args.get("q", "").strip()

    if source not in ("", "soc", "audit"):
        return None, ("invalid_source", 400)
    if status not in (
        "", "pending", "processing", "processed", "failed", "success", "failure"
    ):
        return None, ("invalid_status", 400)
    if len(query) > 200:
        return None, ("search_too_long", 400)

    return {"source": source, "status": status, "q": query}, None


@alerts_bp.route("/api/logs", methods=["GET"])
@login_required
@role_required(permission="alerts.view")
def get_persisted_logs():
    """Return bounded, read-only records from persistent SOC and audit tables."""
    params, error = _log_query_parameters()
    if error:
        code, status_code = error
        return jsonify({"error": code}), status_code

    try:
        connection = _collector_connection()
        rows = _collect_persisted_log_rows(
            connection, params["source"], params["status"], params["q"]
        )
        return jsonify({
            "logs": rows[:500],
            "count": min(len(rows), 500),
            "truncated": len(rows) > 500,
        }), 200
    except Exception:
        logger.exception("Could not read persisted SOC logs")
        return jsonify({"error": "logs_unavailable"}), 500


@alerts_bp.route("/api/logs/export", methods=["GET"])
@login_required
@role_required(permission="alerts.view")
def export_persisted_logs():
    """Export the same read-only log view as CSV, JSON, or plain text."""
    import csv
    import io

    params, error = _log_query_parameters()
    if error:
        code, status_code = error
        return jsonify({"error": code}), status_code

    fmt = request.args.get("format", "csv").strip().lower()
    if fmt not in ("csv", "json", "txt"):
        return jsonify({"error": "invalid_export_format"}), 400

    try:
        connection = _collector_connection()
        rows = _collect_persisted_log_rows(
            connection, params["source"], params["status"], params["q"]
        )[:5000]

        if fmt == "json":
            body = json.dumps(rows, ensure_ascii=False, indent=2)
            mimetype = "application/json; charset=utf-8"
        elif fmt == "txt":
            body = "\n".join(
                f'{row["timestamp"]} [{row["source"]}] '
                f'{row["status"]} {row["event"]} — {row["actor"]} '
                f'{row["details"]}'.rstrip()
                for row in rows
            )
            mimetype = "text/plain; charset=utf-8"
        else:
            output = io.StringIO(newline="")
            fields = [
                "timestamp", "source", "actor", "event", "status",
                "details", "record_id", "processed_at", "payload",
            ]
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            body = output.getvalue()
            mimetype = "text/csv; charset=utf-8"

        filename = f"lums-logs.{fmt}"
        return Response(
            body,
            mimetype=mimetype,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception:
        logger.exception("Could not export persisted SOC logs")
        return jsonify({"error": "logs_unavailable"}), 500


# ============================================================
# INDEPENDENT SOC COLLECTOR API
# ============================================================

def _collector_connection():
    """Get a request-local DB connection without initializing AlertManager."""
    connection = getattr(g, "lums_alert_connection", None)
    if connection is not None:
        return connection

    connection_factory = current_app.config.get("LUMS_GET_CONNECTION")
    if not callable(connection_factory):
        raise RuntimeError("Collector database connection factory is not configured")

    connection = connection_factory()
    g.lums_alert_connection = connection
    return connection


def _verified_collector_fingerprint():
    """Return a SHA-256 fingerprint supplied by trusted TLS integration.

    The callback must derive this value from a verified client certificate.
    It must never copy a value directly from an untrusted HTTP header or body.
    """
    provider = current_app.config.get("LUMS_COLLECTOR_IDENTITY_PROVIDER")
    if not callable(provider):
        return None

    try:
        fingerprint = provider()
    except Exception:
        logger.warning("Collector identity provider failed", exc_info=True)
        return None

    if not isinstance(fingerprint, str):
        return None

    import re
    if re.fullmatch(r"[0-9a-fA-F]{64}", fingerprint) is None:
        return None

    return fingerprint.lower()


@alerts_bp.route("/api/collector/v1/events", methods=["POST"])
def ingest_collector_events():
    """Accept bounded events only when SOC collection is explicitly enabled."""
    from werkzeug.exceptions import BadRequest

    if current_app.config.get("LUMS_SOC_COLLECTOR_ENABLED") is not True:
        return jsonify({"error": "soc_collector_disabled"}), 503

    fingerprint = _verified_collector_fingerprint()
    if fingerprint is None:
        return jsonify({"error": "collector_identity_required"}), 401

    import json

    max_request_bytes = 4 * 1024 * 1024
    if (
        request.content_length is not None
        and request.content_length > max_request_bytes
    ):
        return jsonify({"error": "request_too_large"}), 413

    try:
        # Read only one byte beyond the limit; do not buffer an unlimited body.
        raw = request.stream.read(max_request_bytes + 1)
    except (BadRequest, ValueError):
        return jsonify({"error": "invalid_json_payload"}), 400

    if len(raw) > max_request_bytes:
        return jsonify({"error": "request_too_large"}), 413

    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"error": "invalid_json_payload"}), 400

    if not isinstance(payload, dict) or set(payload) != {"events"}:
        return jsonify({"error": "invalid_json_payload"}), 400

    events = payload["events"]
    if not isinstance(events, list) or not events:
        return jsonify({"error": "invalid_event_batch"}), 400
    if len(events) > 500:
        return jsonify({"error": "batch_too_large"}), 413

    try:
        if __package__:
            from .soc.ingestion import EventIngestor, IngestionError
            from .soc.collector_store import (
                CollectorStore, CollectorNotFoundError,
                CollectorRevokedError, EventIdConflictError,
            )
        else:
            from soc.ingestion import EventIngestor, IngestionError
            from soc.collector_store import (
                CollectorStore, CollectorNotFoundError,
                CollectorRevokedError, EventIdConflictError,
            )
    except Exception:
        logger.exception("Collector event ingestion dependencies could not be loaded")
        return jsonify({"error": "collector_ingestion_failed"}), 500

    try:
        # Collector events must include their source event timestamp.
        # Keep generic EventIngestor behavior unchanged for other callers.
        if any(
            not isinstance(event, dict) or "timestamp" not in event
            for event in events
        ):
            raise IngestionError("Collector event timestamp is required")

        # Validate the complete batch before persisting any event.
        EventIngestor().ingest_batch(events)

        store = CollectorStore(_collector_connection())
        agent = store.get_agent_by_fingerprint(fingerprint)
        if agent is None:
            return jsonify({"error": "collector_not_registered"}), 403
        if agent["status"] != "active":
            return jsonify({"error": "collector_revoked"}), 403

        result = store.ingest_batch(agent["agent_id"], events)
        return jsonify({
            "status": "accepted",
            **result.to_dict(),
        }), 202

    except IngestionError:
        return jsonify({"error": "invalid_event"}), 400
    except EventIdConflictError:
        return jsonify({"error": "event_id_conflict"}), 409
    except CollectorNotFoundError:
        return jsonify({"error": "collector_not_registered"}), 403
    except CollectorRevokedError:
        return jsonify({"error": "collector_revoked"}), 403
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_event_batch"}), 400
    except Exception:
        logger.exception("Collector event ingestion failed")
        return jsonify({"error": "collector_ingestion_failed"}), 500




# ============================================================
# INITIALIZATION
# ============================================================
