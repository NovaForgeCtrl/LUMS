"""
LUMS Alert Management API Routes
REST endpoints for alert and rule management
"""

from flask import (Blueprint, request, jsonify, session, render_template_string, current_app, g)
from functools import wraps
from werkzeug.local import LocalProxy
from datetime import datetime, timezone, timedelta
import uuid
import json
import logging
import sqlite3

if __package__:
    from .alerts import (
        AlertManager, AlertRule, Alert, AlertSeverity, AlertStatus,
    )
    from .security import login_required, role_required, csrf_required, current_user_id
else:
    from alerts import (
        AlertManager, AlertRule, Alert, AlertSeverity, AlertStatus,
    )
    from security import login_required, role_required, csrf_required, current_user_id

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
    """Alert management dashboard"""
    try:
        alerts = alert_manager.get_alerts(limit=50)
        return render_template_string("""
        <div class="alerts-dashboard">
            <h1>{{ tr("Alerts & Monitoring") }}</h1>
            <div class="alerts-tabs">
                <button class="tab-btn active" data-tab="overview">{{ tr("Alert overview") }}</button>
                <button class="tab-btn" data-tab="history">{{ tr("Alert history") }}</button>
                <button class="tab-btn" data-tab="rules">{{ tr("Alert rules") }}</button>
                <button class="tab-btn" data-tab="integrations">{{ tr("Integrations & Webhooks") }}</button>
            </div>
            
            <div id="overview" class="tab-content active">
                <table class="alerts-table">
                    <thead>
                        <tr>
                            <th>{{ tr("Alert name") }}</th>
                            <th>{{ tr("Severity level") }}</th>
                            <th>{{ tr("Alert status") }}</th>
                            <th>{{ tr("Alert timestamp") }}</th>
                            <th>{{ tr("Action") }}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for alert in alerts %}
                        <tr>
                            <td>{{ alert.message }}</td>
                            <td><span class="severity-{{ alert.severity.value }}">{{ alert.severity.value }}</span></td>
                            <td>{{ alert.status.value }}</td>
                            <td>{{ alert.triggered_at }}</td>
                            <td>
                                {% if alert.status.value != 'resolved' %}
                                <button class="btn-acknowledge" data-alert-id="{{ alert.alert_id }}">{{ tr("Acknowledged") }}</button>
                                <button class="btn-resolve" data-alert-id="{{ alert.alert_id }}">{{ tr("Alert resolved") }}</button>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        """, alerts=alerts
        )
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
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
# INITIALIZATION
# ============================================================
