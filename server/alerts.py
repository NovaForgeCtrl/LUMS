"""
LUMS Alert Management System
Comprehensive real-time alerting, notification routing, and escalation management
"""

from enum import Enum
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
import sqlite3
import json
import logging
import uuid

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

    @property
    def numeric_value(self) -> int:
        """Numeric value for sorting (higher = more severe)"""
        return {"critical": 3, "warning": 2, "info": 1}[self.value]


class AlertStatus(Enum):
    """Alert status throughout its lifecycle"""
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class AlertRule:
    """Alert rule definition and evaluation"""
    
    def __init__(self, rule_id: str, name: str, description: str, 
                 condition: str, threshold: Any, severity: AlertSeverity,
                 enabled: bool = True, escalation_path: Optional[List[str]] = None,
                 group_similar: bool = True, deduplicate: bool = True):
        self.rule_id = rule_id
        self.name = name
        self.description = description
        self.condition = condition  # e.g., "cpu_usage > threshold"
        self.threshold = threshold
        self.severity = severity
        self.enabled = enabled
        self.escalation_path = escalation_path or []
        self.group_similar = group_similar
        self.deduplicate = deduplicate
        self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary"""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "condition": self.condition,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "enabled": self.enabled,
            "escalation_path": self.escalation_path,
            "group_similar": self.group_similar,
            "deduplicate": self.deduplicate,
            "created_at": self.created_at.isoformat(),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AlertRule":
        """Create rule from dictionary"""
        return AlertRule(
            rule_id=data["rule_id"],
            name=data["name"],
            description=data["description"],
            condition=data["condition"],
            threshold=data["threshold"],
            severity=AlertSeverity(data["severity"]),
            enabled=data.get("enabled", True),
            escalation_path=data.get("escalation_path", []),
            group_similar=data.get("group_similar", True),
            deduplicate=data.get("deduplicate", True),
        )


class Alert:
    """Alert instance"""
    
    def __init__(self, alert_id: str, rule_id: str, source: str,
                 message: str, severity: AlertSeverity, status: AlertStatus = AlertStatus.TRIGGERED,
                 metadata: Optional[Dict[str, Any]] = None):
        self.alert_id = alert_id
        self.rule_id = rule_id
        self.source = source  # e.g., "client-01", "server", "system"
        self.message = message
        self.severity = severity
        self.status = status
        self.metadata = metadata or {}
        self.triggered_at = datetime.now(timezone.utc)
        self.acknowledged_at: Optional[datetime] = None
        self.resolved_at: Optional[datetime] = None
        self.escalation_count = 0

    def acknowledge(self, by_user: str) -> None:
        """Acknowledge this alert"""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now(timezone.utc)
        self.metadata["acknowledged_by"] = by_user

    def resolve(self) -> None:
        """Mark alert as resolved"""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now(timezone.utc)

    def escalate(self) -> None:
        """Escalate this alert"""
        self.status = AlertStatus.ESCALATED
        self.escalation_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary"""
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "source": self.source,
            "message": self.message,
            "severity": self.severity.value,
            "status": self.status.value,
            "metadata": self.metadata,
            "triggered_at": self.triggered_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "escalation_count": self.escalation_count,
        }


class NotificationProvider:
    """Base class for notification providers"""
    
    def send(self, alert: Alert, recipients: List[str]) -> bool:
        """Send notification for alert"""
        raise NotImplementedError


class EmailNotificationProvider(NotificationProvider):
    """Email notification provider"""
    
    def __init__(self, smtp_server: str, smtp_port: int, 
                 username: str, password: str, from_address: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_address = from_address

    def send(self, alert: Alert, recipients: List[str]) -> bool:
        """Send alert via email"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            subject = f"[{alert.severity.value.upper()}] {alert.message}"
            body = f"""
Alert Triggered at: {alert.triggered_at}
Rule: {alert.rule_id}
Severity: {alert.severity.value}
Source: {alert.source}
Message: {alert.message}

Metadata:
{json.dumps(alert.metadata, indent=2)}
            """
            
            msg = MIMEMultipart()
            msg['From'] = self.from_address
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"Email notification sent for alert {alert.alert_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False


class SlackNotificationProvider(NotificationProvider):
    """Slack notification provider"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, alert: Alert, recipients: List[str]) -> bool:
        """Send alert to Slack"""
        try:
            import requests
            
            color_map = {
                AlertSeverity.CRITICAL: "#FF0000",
                AlertSeverity.WARNING: "#FFA500",
                AlertSeverity.INFO: "#0099FF",
            }
            
            payload = {
                "attachments": [{
                    "color": color_map[alert.severity],
                    "title": alert.message,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value, "short": True},
                        {"title": "Source", "value": alert.source, "short": True},
                        {"title": "Rule", "value": alert.rule_id, "short": True},
                        {"title": "Time", "value": alert.triggered_at.isoformat(), "short": True},
                        {"title": "Status", "value": alert.status.value, "short": True},
                    ],
                    "ts": int(alert.triggered_at.timestamp()),
                }]
            }
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"Slack notification sent for alert {alert.alert_id}")
                return True
            else:
                logger.error(f"Slack notification failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False


class PagerDutyNotificationProvider(NotificationProvider):
    """PagerDuty notification provider"""
    
    def __init__(self, api_key: str, service_id: str):
        self.api_key = api_key
        self.service_id = service_id

    def send(self, alert: Alert, recipients: List[str]) -> bool:
        """Send alert to PagerDuty"""
        try:
            import requests
            
            severity_map = {
                AlertSeverity.CRITICAL: "critical",
                AlertSeverity.WARNING: "warning",
                AlertSeverity.INFO: "info",
            }
            
            headers = {
                "Authorization": f"Token token={self.api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "incident": {
                    "type": "incident",
                    "title": alert.message,
                    "urgency": "high" if alert.severity == AlertSeverity.CRITICAL else "low",
                    "service": {
                        "id": self.service_id,
                        "type": "service_reference",
                    },
                    "body": {
                        "type": "incident_body",
                        "details": f"Source: {alert.source}\nRule: {alert.rule_id}\nMetadata: {json.dumps(alert.metadata)}",
                    },
                }
            }
            
            response = requests.post(
                "https://api.pagerduty.com/incidents",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"PagerDuty notification sent for alert {alert.alert_id}")
                return True
            else:
                logger.error(f"PagerDuty notification failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to send PagerDuty notification: {e}")
            return False


class WebhookNotificationProvider(NotificationProvider):
    """Generic webhook notification provider"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, alert: Alert, recipients: List[str]) -> bool:
        """Send alert via webhook"""
        try:
            import requests
            
            payload = alert.to_dict()
            payload["recipients"] = recipients
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code in [200, 201, 204]:
                logger.info(f"Webhook notification sent for alert {alert.alert_id}")
                return True
            else:
                logger.error(f"Webhook notification failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False


class AlertManager:
    """Central alert management system"""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self._initialize_db()
        self.notification_providers: Dict[str, NotificationProvider] = {}
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self._load_state()

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """Parse a persisted ISO or SQLite timestamp without inventing a new one."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid persisted alert timestamp")
            return None

    def _load_state(self) -> None:
        """Restore rules and non-resolved alerts from the persistent database."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT rule_id, name, description, condition, threshold,
                       severity, enabled, escalation_path, group_similar,
                       deduplicate, created_at
                FROM alert_rules
            """)
            for row in cursor.fetchall():
                try:
                    threshold = row[4]
                    try:
                        threshold = json.loads(threshold)
                    except (TypeError, ValueError):
                        pass

                    try:
                        escalation_path = json.loads(row[7]) if row[7] else []
                    except (TypeError, ValueError):
                        escalation_path = []
                    if not isinstance(escalation_path, list):
                        escalation_path = []

                    rule = AlertRule(
                        rule_id=row[0],
                        name=row[1],
                        description=row[2] or "",
                        condition=row[3],
                        threshold=threshold,
                        severity=AlertSeverity(row[5]),
                        enabled=bool(row[6]),
                        escalation_path=escalation_path,
                        group_similar=bool(row[8]),
                        deduplicate=bool(row[9]),
                    )
                    created_at = self._parse_datetime(row[10])
                    if created_at:
                        rule.created_at = created_at
                    self.rules[rule.rule_id] = rule
                except (ValueError, TypeError, KeyError) as exc:
                    logger.warning("Skipping invalid persisted alert rule: %s", exc)

            cursor.execute("""
                SELECT alert_id, rule_id, source, message, severity, status,
                       metadata, triggered_at, acknowledged_at, resolved_at,
                       escalation_count
                FROM alerts
                WHERE status IN ('triggered', 'acknowledged', 'escalated')
            """)
            for row in cursor.fetchall():
                try:
                    metadata = json.loads(row[6]) if row[6] else {}
                    if not isinstance(metadata, dict):
                        metadata = {}

                    alert = Alert(
                        alert_id=row[0],
                        rule_id=row[1],
                        source=row[2],
                        message=row[3],
                        severity=AlertSeverity(row[4]),
                        status=AlertStatus(row[5]),
                        metadata=metadata,
                    )
                    triggered_at = self._parse_datetime(row[7])
                    acknowledged_at = self._parse_datetime(row[8])
                    resolved_at = self._parse_datetime(row[9])
                    if triggered_at:
                        alert.triggered_at = triggered_at
                    alert.acknowledged_at = acknowledged_at
                    alert.resolved_at = resolved_at
                    alert.escalation_count = int(row[10] or 0)
                    self.active_alerts[alert.alert_id] = alert
                except (ValueError, TypeError, KeyError) as exc:
                    logger.warning("Skipping invalid persisted alert: %s", exc)

        except sqlite3.Error:
            logger.exception("Failed to restore alert state from database")
            raise

    def _initialize_db(self) -> None:
        """Initialize alert tables"""
        cursor = self.db.cursor()
        
        # Alert Rules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                rule_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                condition TEXT NOT NULL,
                threshold TEXT NOT NULL,
                severity TEXT NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                escalation_path TEXT,
                group_similar BOOLEAN DEFAULT 1,
                deduplicate BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                rule_id TEXT NOT NULL,
                source TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                metadata TEXT,
                triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acknowledged_at TIMESTAMP,
                resolved_at TIMESTAMP,
                escalation_count INTEGER DEFAULT 0,
                FOREIGN KEY (rule_id) REFERENCES alert_rules(rule_id)
            )
        """)
        
        # Alert History table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT NOT NULL,
                status TEXT NOT NULL,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                changed_by TEXT,
                reason TEXT,
                FOREIGN KEY (alert_id) REFERENCES alerts(alert_id)
            )
        """)
        
        # Notification Integrations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_integrations (
                integration_id TEXT PRIMARY KEY,
                provider_type TEXT NOT NULL,
                name TEXT NOT NULL,
                config TEXT NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Alert Notifications Log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_notifications_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT NOT NULL,
                integration_id TEXT NOT NULL,
                recipients TEXT,
                success BOOLEAN,
                error_message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (alert_id) REFERENCES alerts(alert_id),
                FOREIGN KEY (integration_id) REFERENCES notification_integrations(integration_id)
            )
        """)
        
        self.db.commit()

    def create_rule(self, rule: AlertRule) -> bool:
        """Create new alert rule"""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO alert_rules 
                (rule_id, name, description, condition, threshold, severity, 
                 enabled, escalation_path, group_similar, deduplicate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule.rule_id, rule.name, rule.description, rule.condition,
                json.dumps(rule.threshold), rule.severity.value, rule.enabled,
                json.dumps(rule.escalation_path), rule.group_similar, rule.deduplicate
            ))
            self.db.commit()
            self.rules[rule.rule_id] = rule
            logger.info(f"Alert rule created: {rule.rule_id}")
            return True
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                logger.exception("Rollback failed after alert rule creation error")
            logger.exception("Failed to create alert rule")
            return False

    def trigger_alert(self, rule_id: str, source: str, message: str,
                     metadata: Optional[Dict[str, Any]] = None) -> Alert:
        """Trigger a new alert"""
        try:
            rule = self.rules.get(rule_id)
            if not rule or not rule.enabled:
                logger.warning(f"Rule {rule_id} not found or disabled")
                return None
            
            alert = Alert(
                alert_id=f"{rule_id}_{uuid.uuid4()}",
                rule_id=rule_id,
                source=source,
                message=message,
                severity=rule.severity,
                metadata=metadata
            )
            
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO alerts 
                (alert_id, rule_id, source, message, severity, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id, rule_id, source, message,
                rule.severity.value, alert.status.value, json.dumps(metadata or {})
            ))
            self.db.commit()
            
            self.active_alerts[alert.alert_id] = alert
            logger.info(f"Alert triggered: {alert.alert_id}")
            
            # Notify
            # Notification failure must not hide an already persisted alert.
            try:
                self._notify_alert(alert, rule)
            except Exception:
                logger.exception(
                    "Alert %s was persisted, but notification processing failed",
                    alert.alert_id,
                )
            
            return alert
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                logger.exception("Rollback failed after alert trigger error")
            logger.exception("Failed to trigger alert")
            return None

    def acknowledge_alert(self, alert_id: str, by_user: str) -> bool:
        """Atomically acknowledge an alert and record its history."""
        alert = self.active_alerts.get(alert_id)
        if alert is None:
            logger.warning("Alert %s not found", alert_id)
            return False

        old_status = alert.status
        old_acknowledged_at = alert.acknowledged_at
        old_metadata = dict(alert.metadata)
        changed_at = datetime.now(timezone.utc).isoformat()

        try:
            cursor = self.db.cursor()
            cursor.execute("BEGIN")
            cursor.execute("""
                UPDATE alerts
                SET status = ?, acknowledged_at = ?,
                    metadata = ?
                WHERE alert_id = ?
                  AND status IN ('triggered', 'escalated')
            """, (
                AlertStatus.ACKNOWLEDGED.value,
                changed_at,
                json.dumps({**alert.metadata, "acknowledged_by": str(by_user)}),
                alert_id,
            ))
            if cursor.rowcount != 1:
                self.db.rollback()
                return False

            cursor.execute("""
                INSERT INTO alert_history
                    (alert_id, status, changed_at, changed_by, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (
                alert_id,
                AlertStatus.ACKNOWLEDGED.value,
                changed_at,
                str(by_user),
                "Alert acknowledged",
            ))
            self.db.commit()

            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.fromisoformat(changed_at)
            alert.metadata["acknowledged_by"] = str(by_user)
            logger.info("Alert acknowledged: %s by %s", alert_id, by_user)
            return True
        except Exception:
            self.db.rollback()
            alert.status = old_status
            alert.acknowledged_at = old_acknowledged_at
            alert.metadata = old_metadata
            logger.exception("Failed to acknowledge alert")
            return False

    def resolve_alert(self, alert_id: str, by_user: str = "system") -> bool:
        """Atomically resolve an alert and record its history."""
        alert = self.active_alerts.get(alert_id)
        if alert is None:
            logger.warning("Alert %s not found", alert_id)
            return False

        changed_at = datetime.now(timezone.utc).isoformat()
        try:
            cursor = self.db.cursor()
            cursor.execute("BEGIN")
            cursor.execute("""
                UPDATE alerts
                SET status = ?, resolved_at = ?
                WHERE alert_id = ?
                  AND status IN ('triggered', 'acknowledged', 'escalated')
            """, (AlertStatus.RESOLVED.value, changed_at, alert_id))
            if cursor.rowcount != 1:
                self.db.rollback()
                return False

            cursor.execute("""
                INSERT INTO alert_history
                    (alert_id, status, changed_at, changed_by, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (
                alert_id,
                AlertStatus.RESOLVED.value,
                changed_at,
                str(by_user),
                "Alert resolved",
            ))
            self.db.commit()

            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.fromisoformat(changed_at)
            self.active_alerts.pop(alert_id, None)
            logger.info("Alert resolved: %s", alert_id)
            return True
        except Exception:
            self.db.rollback()
            logger.exception("Failed to resolve alert")
            return False

    def escalate_alert(self, alert_id: str, by_user: str = "system") -> Optional[int]:
        """Atomically escalate using the latest persisted escalation count."""
        alert = self.active_alerts.get(alert_id)
        if alert is None:
            logger.warning("Alert %s not found", alert_id)
            return None

        changed_at = datetime.now(timezone.utc).isoformat()

        try:
            cursor = self.db.cursor()
            # Acquire the SQLite write lock before reading the counter. This
            # prevents separate request-local managers from using stale counts.
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("""
                SELECT status, escalation_count
                FROM alerts
                WHERE alert_id = ?
            """, (alert_id,))
            row = cursor.fetchone()

            if row is None or row[0] not in (
                AlertStatus.TRIGGERED.value,
                AlertStatus.ACKNOWLEDGED.value,
                AlertStatus.ESCALATED.value,
            ):
                self.db.rollback()
                return None

            new_count = int(row[1] or 0) + 1

            cursor.execute("""
                UPDATE alerts
                SET status = ?, escalation_count = ?
                WHERE alert_id = ?
                  AND status IN ('triggered', 'acknowledged', 'escalated')
            """, (
                AlertStatus.ESCALATED.value,
                new_count,
                alert_id,
            ))

            if cursor.rowcount != 1:
                self.db.rollback()
                return None

            cursor.execute("""
                INSERT INTO alert_history
                    (alert_id, status, changed_at, changed_by, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (
                alert_id,
                AlertStatus.ESCALATED.value,
                changed_at,
                str(by_user),
                f"Alert escalated to level {new_count}",
            ))

            self.db.commit()

            # Change in-memory state only after the transaction commits.
            alert.status = AlertStatus.ESCALATED
            alert.escalation_count = new_count
            logger.info("Alert escalated: %s (count=%s)", alert_id, new_count)
            return new_count

        except Exception:
            try:
                self.db.rollback()
            except Exception:
                logger.exception("Rollback failed after alert escalation error")
            logger.exception("Failed to escalate alert")
            return None

    def _notify_alert(self, alert: Alert, rule: AlertRule) -> None:
        """Send notifications for alert"""
        for integration_id in rule.escalation_path:
            provider = self.notification_providers.get(integration_id)
            if provider:
                success = provider.send(alert, [])
                self._log_notification(alert.alert_id, integration_id, success)

    def _log_notification(self, alert_id: str, integration_id: str, success: bool) -> None:
        """Log notification attempt"""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO alert_notifications_log 
                (alert_id, integration_id, success)
                VALUES (?, ?, ?)
            """, (alert_id, integration_id, success))
            self.db.commit()
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                logger.exception(
                    "Rollback failed after notification logging error"
                )
            logger.exception("Failed to log notification")

    def get_alerts(self, limit: int = 100, offset: int = 0) -> List[Alert]:
        """Return alerts using their persisted status and timestamps."""
        try:
            safe_limit = max(1, min(int(limit), 1000))
            safe_offset = max(0, int(offset))
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT alert_id, rule_id, source, message, severity, status,
                       metadata, triggered_at, acknowledged_at, resolved_at,
                       escalation_count
                FROM alerts
                ORDER BY triggered_at DESC
                LIMIT ? OFFSET ?
            """, (safe_limit, safe_offset))

            alerts = []
            for row in cursor.fetchall():
                try:
                    metadata = json.loads(row[6]) if row[6] else {}
                    if not isinstance(metadata, dict):
                        metadata = {}

                    alert = Alert(
                        alert_id=row[0],
                        rule_id=row[1],
                        source=row[2],
                        message=row[3],
                        severity=AlertSeverity(row[4]),
                        status=AlertStatus(row[5]),
                        metadata=metadata,
                    )
                    triggered_at = self._parse_datetime(row[7])
                    acknowledged_at = self._parse_datetime(row[8])
                    resolved_at = self._parse_datetime(row[9])
                    if triggered_at:
                        alert.triggered_at = triggered_at
                    alert.acknowledged_at = acknowledged_at
                    alert.resolved_at = resolved_at
                    alert.escalation_count = int(row[10] or 0)
                    alerts.append(alert)
                except (ValueError, TypeError, KeyError) as exc:
                    logger.warning("Skipping invalid alert row: %s", exc)

            return alerts
        except Exception:
            logger.exception("Failed to get alerts")
            return []
