"""
LUMS Alert Management API Routes
REST endpoints for alert and rule management
"""

from flask import Blueprint, request, jsonify, session, render_template_string
from functools import wraps
from datetime import datetime, timedelta
import uuid
import logging

from alerts import (
    AlertManager, AlertRule, Alert, AlertSeverity, AlertStatus,
    EmailNotificationProvider, SlackNotificationProvider,
    PagerDutyNotificationProvider, WebhookNotificationProvider
)

logger = logging.getLogger(__name__)

alerts_bp = Blueprint('alerts', __name__, url_prefix='/alerts')

# Global alert manager instance (will be initialized in app)
alert_manager = None


def require_permission(permission):
    """Decorator to check user permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check permission logic here
            # This would typically check against user_permissions from session
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================
# ALERT DASHBOARD
# ============================================================

@alerts_bp.route('/', methods=['GET'])
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
        return {"error": str(e)}, 500


# ============================================================
# ALERT RULES
# ============================================================

@alerts_bp.route('/rules', methods=['GET'])
def list_rules():
    """List all alert rules"""
    try:
        rules = [rule.to_dict() for rule in alert_manager.rules.values()]
        return jsonify({"rules": rules}), 200
    except Exception as e:
        logger.error(f"Error listing rules: {e}")
        return {"error": str(e)}, 500


@alerts_bp.route('/rules', methods=['POST'])
def create_rule():
    """Create new alert rule"""
    try:
        data = request.get_json()
        
        rule_id = str(uuid.uuid4())
        rule = AlertRule(
            rule_id=rule_id,
            name=data.get("name"),
            description=data.get("description"),
            condition=data.get("condition"),
            threshold=data.get("threshold"),
            severity=AlertSeverity(data.get("severity", "warning")),
            enabled=data.get("enabled", True),
            escalation_path=data.get("escalation_path", []),
            group_similar=data.get("group_similar", True),
            deduplicate=data.get("deduplicate", True),
        )
        
        if alert_manager.create_rule(rule):
            return jsonify({
                "message": "Rule created successfully",
                "rule": rule.to_dict()
            }), 201
        else:
            return {"error": "Failed to create rule"}, 500
    except Exception as e:
        logger.error(f"Error creating rule: {e}")
        return {"error": str(e)}, 400


@alerts_bp.route('/rules/<rule_id>', methods=['PUT'])
def update_rule(rule_id):
    """Update alert rule"""
    try:
        data = request.get_json()
        rule = alert_manager.rules.get(rule_id)
        
        if not rule:
            return {"error": "Rule not found"}, 404
        
        # Update fields
        rule.name = data.get("name", rule.name)
        rule.description = data.get("description", rule.description)
        rule.condition = data.get("condition", rule.condition)
        rule.threshold = data.get("threshold", rule.threshold)
        rule.severity = AlertSeverity(data.get("severity", rule.severity.value))
        rule.enabled = data.get("enabled", rule.enabled)
        rule.escalation_path = data.get("escalation_path", rule.escalation_path)
        rule.group_similar = data.get("group_similar", rule.group_similar)
        rule.deduplicate = data.get("deduplicate", rule.deduplicate)
        
        return jsonify({
            "message": "Rule updated successfully",
            "rule": rule.to_dict()
        }), 200
    except Exception as e:
        logger.error(f"Error updating rule: {e}")
        return {"error": str(e)}, 400


@alerts_bp.route('/rules/<rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    """Delete alert rule"""
    try:
        if rule_id in alert_manager.rules:
            del alert_manager.rules[rule_id]
            return jsonify({"message": "Rule deleted successfully"}), 200
        else:
            return {"error": "Rule not found"}, 404
    except Exception as e:
        logger.error(f"Error deleting rule: {e}")
        return {"error": str(e)}, 500


# ============================================================
# ALERTS
# ============================================================

@alerts_bp.route('/current', methods=['GET'])
def get_current_alerts():
    """Get current active alerts"""
    try:
        alerts = [alert.to_dict() for alert in alert_manager.active_alerts.values()]
        return jsonify({"alerts": alerts, "count": len(alerts)}), 200
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return {"error": str(e)}, 500


@alerts_bp.route('/history', methods=['GET'])
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
        return {"error": str(e)}, 500


@alerts_bp.route('/trigger', methods=['POST'])
def trigger_alert():
    """Manually trigger an alert (for testing)"""
    try:
        data = request.get_json()
        
        alert = alert_manager.trigger_alert(
            rule_id=data.get("rule_id"),
            source=data.get("source", "api"),
            message=data.get("message"),
            metadata=data.get("metadata")
        )
        
        if alert:
            return jsonify({
                "message": "Alert triggered successfully",
                "alert": alert.to_dict()
            }), 201
        else:
            return {"error": "Failed to trigger alert"}, 500
    except Exception as e:
        logger.error(f"Error triggering alert: {e}")
        return {"error": str(e)}, 400


@alerts_bp.route('/<alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    try:
        user_id = session.get("user_id", "unknown")
        
        if alert_manager.acknowledge_alert(alert_id, user_id):
            return jsonify({"message": "Alert acknowledged"}), 200
        else:
            return {"error": "Alert not found"}, 404
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        return {"error": str(e)}, 500


@alerts_bp.route('/<alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    """Resolve an alert"""
    try:
        if alert_manager.resolve_alert(alert_id):
            return jsonify({"message": "Alert resolved"}), 200
        else:
            return {"error": "Alert not found"}, 404
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        return {"error": str(e)}, 500


@alerts_bp.route('/<alert_id>/escalate', methods=['POST'])
def escalate_alert(alert_id):
    """Escalate an alert"""
    try:
        alert = alert_manager.active_alerts.get(alert_id)
        if not alert:
            return {"error": "Alert not found"}, 404
        
        alert.escalate()
        return jsonify({
            "message": "Alert escalated",
            "escalation_count": alert.escalation_count
        }), 200
    except Exception as e:
        logger.error(f"Error escalating alert: {e}")
        return {"error": str(e)}, 500


@alerts_bp.route('/clear-all', methods=['POST'])
def clear_all_alerts():
    """Clear all resolved alerts"""
    try:
        count = 0
        for alert_id in list(alert_manager.active_alerts.keys()):
            alert = alert_manager.active_alerts[alert_id]
            if alert.status == AlertStatus.RESOLVED:
                del alert_manager.active_alerts[alert_id]
                count += 1
        
        return jsonify({"message": f"Cleared {count} alerts"}), 200
    except Exception as e:
        logger.error(f"Error clearing alerts: {e}")
        return {"error": str(e)}, 500


# ============================================================
# NOTIFICATIONS & INTEGRATIONS
# ============================================================

@alerts_bp.route('/integrations', methods=['GET'])
def list_integrations():
    """List configured notification integrations"""
    try:
        integrations = list(alert_manager.notification_providers.keys())
        return jsonify({"integrations": integrations}), 200
    except Exception as e:
        logger.error(f"Error listing integrations: {e}")
        return {"error": str(e)}, 500


@alerts_bp.route('/integrations/email', methods=['POST'])
def setup_email_integration():
    """Setup email notification integration"""
    try:
        data = request.get_json()
        
        provider = EmailNotificationProvider(
            smtp_server=data.get("smtp_server"),
            smtp_port=data.get("smtp_port", 587),
            username=data.get("username"),
            password=data.get("password"),
            from_address=data.get("from_address"),
        )
        
        integration_id = f"email_{int(datetime.utcnow().timestamp())}"
        alert_manager.notification_providers[integration_id] = provider
        
        return jsonify({
            "message": "Email integration setup successfully",
            "integration_id": integration_id
        }), 201
    except Exception as e:
        logger.error(f"Error setting up email: {e}")
        return {"error": str(e)}, 400


@alerts_bp.route('/integrations/slack', methods=['POST'])
def setup_slack_integration():
    """Setup Slack notification integration"""
    try:
        data = request.get_json()
        
        provider = SlackNotificationProvider(
            webhook_url=data.get("webhook_url")
        )
        
        integration_id = f"slack_{int(datetime.utcnow().timestamp())}"
        alert_manager.notification_providers[integration_id] = provider
        
        return jsonify({
            "message": "Slack integration setup successfully",
            "integration_id": integration_id
        }), 201
    except Exception as e:
        logger.error(f"Error setting up Slack: {e}")
        return {"error": str(e)}, 400


@alerts_bp.route('/integrations/pagerduty', methods=['POST'])
def setup_pagerduty_integration():
    """Setup PagerDuty notification integration"""
    try:
        data = request.get_json()
        
        provider = PagerDutyNotificationProvider(
            api_key=data.get("api_key"),
            service_id=data.get("service_id")
        )
        
        integration_id = f"pagerduty_{int(datetime.utcnow().timestamp())}"
        alert_manager.notification_providers[integration_id] = provider
        
        return jsonify({
            "message": "PagerDuty integration setup successfully",
            "integration_id": integration_id
        }), 201
    except Exception as e:
        logger.error(f"Error setting up PagerDuty: {e}")
        return {"error": str(e)}, 400


@alerts_bp.route('/integrations/webhook', methods=['POST'])
def setup_webhook_integration():
    """Setup generic webhook integration"""
    try:
        data = request.get_json()
        
        provider = WebhookNotificationProvider(
            webhook_url=data.get("webhook_url")
        )
        
        integration_id = f"webhook_{int(datetime.utcnow().timestamp())}"
        alert_manager.notification_providers[integration_id] = provider
        
        return jsonify({
            "message": "Webhook integration setup successfully",
            "integration_id": integration_id
        }), 201
    except Exception as e:
        logger.error(f"Error setting up webhook: {e}")
        return {"error": str(e)}, 400


@alerts_bp.route('/integrations/<integration_id>/test', methods=['POST'])
def test_integration(integration_id):
    """Test notification integration"""
    try:
        provider = alert_manager.notification_providers.get(integration_id)
        if not provider:
            return {"error": "Integration not found"}, 404
        
        # Create a test alert
        test_alert = Alert(
            alert_id="test_" + str(int(datetime.utcnow().timestamp() * 1000)),
            rule_id="test",
            source="test",
            message="This is a test notification from LUMS",
            severity=AlertSeverity.INFO,
        )
        
        success = provider.send(test_alert, ["admin@example.com"])
        
        return jsonify({
            "message": "Integration test completed",
            "success": success
        }), 200 if success else 500
    except Exception as e:
        logger.error(f"Error testing integration: {e}")
        return {"error": str(e)}, 500


@alerts_bp.route('/integrations/<integration_id>', methods=['DELETE'])
def remove_integration(integration_id):
    """Remove notification integration"""
    try:
        if integration_id in alert_manager.notification_providers:
            del alert_manager.notification_providers[integration_id]
            return jsonify({"message": "Integration removed successfully"}), 200
        else:
            return {"error": "Integration not found"}, 404
    except Exception as e:
        logger.error(f"Error removing integration: {e}")
        return {"error": str(e)}, 500


# ============================================================
# INITIALIZATION
# ============================================================

def init_alerts_manager(db_connection):
    """Initialize the global alert manager"""
    global alert_manager
    alert_manager = AlertManager(db_connection)
    logger.info("Alert manager initialized")
