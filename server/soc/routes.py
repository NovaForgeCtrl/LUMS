"""SOC page routes.

These routes provide the initial navigation and page skeleton.
They intentionally do not claim that live sensor data is available.
"""

import sqlite3
from datetime import datetime, timezone

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    render_template,
)

try:
    from ..security import (
        login_required,
        role_required,
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        current_user_role,
        current_user_permissions,
        get_csrf_token,
    )
except ImportError:
    from security import (
        login_required,
        role_required,
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        current_user_role,
        current_user_permissions,
        get_csrf_token,
    )


soc_bp = Blueprint("soc", __name__, url_prefix="/soc")

SOC_ROLES = (
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)

PAGE_DEFINITIONS = {
    "dashboard": {
        "title": "SOC Dashboard",
        "description": "Central overview of security events, alerts, sensors and incidents.",
        "sections": [
            ("Event pipeline", "The event pipeline will display ingestion, normalization and processing status."),
            ("Detection overview", "Detection statistics will be connected when the detection engine is integrated."),
            ("Sensor status", "Registered sensors and their health status will appear here."),
            ("Recent incidents", "Correlated incidents will be displayed here when incident processing is connected."),
        ],
    },
    "network_monitoring": {
        "title": "Network Monitoring",
        "description": "Network activity and sensor observations.",
        "sections": [
            ("Network sensors", "Sensor registration and live status are not connected yet."),
            ("Traffic overview", "Traffic metrics will be displayed after a network data source is connected."),
            ("Protocol activity", "Protocol statistics will be provided by the network analyzer."),
        ],
    },
    "events": {
        "title": "Event Explorer",
        "description": "Search and inspect normalized security events.",
        "sections": [
            ("Event search", "Search and filtering will be connected to the central event store."),
            ("Event details", "Normalized event details and related evidence will appear here."),
            ("Correlation", "Related events will be grouped after the correlation pipeline is connected."),
        ],
    },
    "network_analyzer": {
        "title": "Network Analyzer",
        "description": "Connections, protocols, hosts and network relationships.",
        "sections": [
            ("Connections", "TCP and UDP connection metadata will be displayed here."),
            ("Protocols", "DNS, HTTP, TLS and other protocol metadata will be integrated here."),
            ("Host relationships", "Communication relationships will be derived from collected network metadata."),
        ],
    },
    "pcap": {
        "title": "PCAP Investigation",
        "description": "Packet-capture references and investigation workspace.",
        "sections": [
            ("Capture references", "PCAP files and their metadata are not connected yet."),
            ("Investigation", "Investigation workflows will be added with the capture integration."),
            ("Retention", "Capture retention and storage policies will be configured separately."),
        ],
    },
    "incidents": {
        "title": "Incidents",
        "description": "Security incidents, evidence and investigation status.",
        "sections": [
            ("Incident queue", "Incident records will be connected to the SOC incident store."),
            ("Evidence", "Correlated events and other evidence will be attached to incidents."),
            ("Timeline", "Incident timelines will be assembled from stored event timestamps."),
        ],
    },
    "detections": {
        "title": "Detection Rules",
        "description": "Detection logic, rule catalog and rule lifecycle.",
        "sections": [
            ("Rule catalog", "The existing rule catalog will be connected to this interface."),
            ("Rule lifecycle", "Enablement, validation and version history will be added."),
            ("Detection results", "Detection matches will be displayed after engine integration."),
        ],
    },
    "sensors": {
        "title": "Sensor Management",
        "description": "Sensor inventory, registration and operational status.",
        "sections": [
            ("Sensor inventory", "Sensor registration and inventory are not connected yet."),
            ("Health and heartbeat", "Sensor health and heartbeat information will appear here."),
            ("Configuration", "Central sensor configuration will be added in a later implementation step."),
        ],
    },
    "reports": {
        "title": "Reports Overview",
        "description": "Central entry point for SOC and network reports.",
        "sections": [
            ("Security reports", "Security report generation is planned."),
            ("Network statistics", "Network statistics will be available after analyzer integration."),
            ("Export history", "Report export history is not connected yet."),
        ],
    },
    "security_reports": {
        "title": "Security Reports",
        "description": "Security posture, detections and incident reporting.",
        "sections": [
            ("Detection summary", "Detection summaries will be generated from stored detection results."),
            ("Incident summary", "Incident statistics will be generated from the incident store."),
            ("Reporting period", "Report filters and time ranges will be added with report generation."),
        ],
    },
    "network_reports": {
        "title": "Network Statistics",
        "description": "Network usage, protocols and connection statistics.",
        "sections": [
            ("Traffic statistics", "Traffic statistics require an integrated network data source."),
            ("Protocol distribution", "Protocol distribution will be calculated from analyzer metadata."),
            ("Connection trends", "Connection trends will be generated from stored flow records."),
        ],
    },
    "export_history": {
        "title": "Export History",
        "description": "Previously generated SOC and network report exports.",
        "sections": [
            ("Generated exports", "No export history source is connected yet."),
            ("Export status", "Export status and timestamps will be shown here."),
            ("Retention", "Export retention policies will be configured with the reporting backend."),
        ],
    },
}



def _get_soc_request_connection():
    """Reuse the request-local LUMS connection; app teardown owns closing it."""
    connection = getattr(g, "lums_alert_connection", None)
    if connection is not None:
        return connection

    connection_factory = current_app.config.get("LUMS_GET_CONNECTION")
    if not callable(connection_factory):
        raise RuntimeError("SOC database connection is not configured")

    connection = connection_factory()
    g.lums_alert_connection = connection
    return connection


def _soc_table_exists(connection, table_name):
    """Check a fixed internal table name without modifying the database."""
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _soc_table_has_columns(connection, table_name, required_columns):
    """Check a fixed internal table and its required columns without writes."""
    if not _soc_table_exists(connection, table_name):
        return False

    columns = {
        row[1]
        for row in connection.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    }
    return set(required_columns).issubset(columns)


def _dashboard_source_unavailable():
    return {
        "available": False,
        "reason": "storage_not_ready",
    }


@soc_bp.get("/api/dashboard")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def dashboard_api():
    """Return bounded, aggregate-only SOC dashboard data."""
    try:
        connection = _get_soc_request_connection()

        event_source_available = _soc_table_has_columns(
            connection,
            "soc_event_inbox",
            {"processing_status"},
        )
        sensor_source_available = _soc_table_has_columns(
            connection,
            "soc_collector_agents",
            {"status"},
        )
        incident_source_available = _soc_table_has_columns(
            connection,
            "soc_incidents",
            {"incident_id", "title", "severity", "status", "updated_at"},
        )

        event_counts = {
            "pending": 0,
            "processing": 0,
            "processed": 0,
            "failed": 0,
        }
        if event_source_available:
            for row in connection.execute(
                """
                SELECT processing_status, COUNT(*)
                FROM soc_event_inbox
                GROUP BY processing_status
                """
            ).fetchall():
                status, count = row[0], row[1]
                if status in event_counts:
                    event_counts[status] = count

        sensor_counts = {
            "active": 0,
            "revoked": 0,
        }
        if sensor_source_available:
            for row in connection.execute(
                """
                SELECT status, COUNT(*)
                FROM soc_collector_agents
                GROUP BY status
                """
            ).fetchall():
                status, count = row[0], row[1]
                if status in sensor_counts:
                    sensor_counts[status] = count

        incident_counts = {
            "status": {
                "open": 0,
                "investigating": 0,
                "resolved": 0,
            },
            "severity": {
                "info": 0,
                "warning": 0,
                "critical": 0,
            },
        }
        recent_incidents = []

        if incident_source_available:
            for row in connection.execute(
                """
                SELECT status, COUNT(*)
                FROM soc_incidents
                GROUP BY status
                """
            ).fetchall():
                status, count = row[0], row[1]
                if status in incident_counts["status"]:
                    incident_counts["status"][status] = count

            for row in connection.execute(
                """
                SELECT severity, COUNT(*)
                FROM soc_incidents
                GROUP BY severity
                """
            ).fetchall():
                severity, count = row[0], row[1]
                if severity in incident_counts["severity"]:
                    incident_counts["severity"][severity] = count

            recent_incidents = [
                {
                    "incident_id": row[0],
                    "title": row[1],
                    "severity": row[2],
                    "status": row[3],
                    "updated_at": row[4],
                }
                for row in connection.execute(
                    """
                    SELECT incident_id, title, severity, status, updated_at
                    FROM soc_incidents
                    ORDER BY updated_at DESC, incident_id
                    LIMIT 8
                    """
                ).fetchall()
            ]

        return jsonify({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": {
                "events": (
                    {"available": True}
                    if event_source_available
                    else _dashboard_source_unavailable()
                ),
                "sensors": (
                    {"available": True}
                    if sensor_source_available
                    else _dashboard_source_unavailable()
                ),
                "incidents": (
                    {"available": True}
                    if incident_source_available
                    else _dashboard_source_unavailable()
                ),
            },
            "events": event_counts,
            "sensors": sensor_counts,
            "incidents": incident_counts,
            "recent_incidents": recent_incidents,
        }), 200

    except (sqlite3.Error, RuntimeError):
        current_app.logger.exception("SOC dashboard data could not be loaded")
        return jsonify({
            "error": "soc_dashboard_unavailable",
        }), 503


def _render_soc_page(page_key):
    page = PAGE_DEFINITIONS[page_key]
    return render_template(
        "soc_page.html",
        page=page,
        page_key=page_key,
        csrf_token=get_csrf_token(),
        user_role=current_user_role(),
        user_permissions=sorted(current_user_permissions()),
    )


@soc_bp.get("/")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def soc_dashboard():
    return _render_soc_page("dashboard")


@soc_bp.get("/network-monitoring")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def network_monitoring():
    return _render_soc_page("network_monitoring")


@soc_bp.get("/events")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def event_explorer():
    return _render_soc_page("events")


@soc_bp.get("/network-analyzer")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def network_analyzer():
    return _render_soc_page("network_analyzer")


@soc_bp.get("/pcap")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def pcap_investigation():
    return _render_soc_page("pcap")


@soc_bp.get("/incidents")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def incidents():
    return _render_soc_page("incidents")


@soc_bp.get("/detections")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def detection_rules():
    return _render_soc_page("detections")


@soc_bp.get("/sensors")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def sensor_management():
    return _render_soc_page("sensors")


@soc_bp.get("/reports")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def reports_overview():
    return _render_soc_page("reports")


@soc_bp.get("/reports/security")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def security_reports():
    return _render_soc_page("security_reports")


@soc_bp.get("/reports/network")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def network_reports():
    return _render_soc_page("network_reports")


@soc_bp.get("/reports/exports")
@login_required
@role_required(*SOC_ROLES, permission="clients.view")
def export_history():
    return _render_soc_page("export_history")
