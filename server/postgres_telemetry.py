"""PostgreSQL-native telemetry ingestion and history routes for LUMS."""

from __future__ import annotations

import csv
import hmac
import ipaddress
import io
import json
import math
from datetime import datetime, timedelta, timezone

from flask import Response, current_app, jsonify, request
from psycopg.types.json import Jsonb

if __package__:
    from .db_errors import DatabaseDriverError
    from .db_transactions import transaction
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
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
    )
else:
    from db_errors import DatabaseDriverError
    from db_transactions import transaction
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
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
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


def parse_telemetry_time(value):
    """Parse an ISO timestamp or PostgreSQL datetime as UTC-aware time."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except (TypeError, ValueError, OverflowError):
            return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def _decode_json_object(value):
    """Accept psycopg-decoded JSONB objects and legacy JSON text."""
    if isinstance(value, str):
        value = json.loads(value)

    if not isinstance(value, dict):
        raise ValueError("Stored telemetry JSON must be an object")

    return value


def _iso_timestamp(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return value




def _csv_response(filename, fieldnames, rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)

    return Response(
        output.getvalue(),
        content_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )

def telemetry_history_rows(connection, client_id, hours, downsample=True):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = connection.execute(
        """
        SELECT recorded_at, cpu_percent, memory_percent,
               memory_total_bytes, memory_available_bytes,
               network_rx_bytes, network_tx_bytes, disk_percent
        FROM client_telemetry
        WHERE client_id = %s AND recorded_at >= %s
        ORDER BY recorded_at ASC
        """,
        (client_id, cutoff),
    ).fetchall()

    rows = add_network_rates(rows)

    if downsample and len(rows) > TELEMETRY_MAX_RESPONSE_POINTS:
        last_index = len(rows) - 1
        denominator = TELEMETRY_MAX_RESPONSE_POINTS - 1
        rows = [
            rows[
                (index * last_index + denominator // 2) // denominator
            ]
            for index in range(TELEMETRY_MAX_RESPONSE_POINTS)
        ]

    return rows


def register_postgres_telemetry_routes(app):
    """Register PostgreSQL-only telemetry ingestion and history routes."""

    @app.post("/api/telemetry")
    @client_auth_required
    def ingest_telemetry():
        client = authenticated_client()
        data = request.get_json(silent=True)

        required_fields = {
            "cpu_percent",
            "memory_percent",
            "memory_total_bytes",
            "memory_available_bytes",
        }
        network_fields = {"network_rx_bytes", "network_tx_bytes"}
        optional_fields = network_fields | {"system"}

        if (
            not isinstance(data, dict)
            or not required_fields <= set(data)
            or not set(data) <= required_fields | optional_fields
            or len(set(data) & network_fields) == 1
        ):
            return jsonify({
                "status": "error",
                "message": "Invalid telemetry payload",
            }), 400

        cpu = data["cpu_percent"]
        memory = data["memory_percent"]
        memory_total = data["memory_total_bytes"]
        memory_available = data["memory_available_bytes"]
        network_rx = data.get("network_rx_bytes")
        network_tx = data.get("network_tx_bytes")

        def valid_counter(value):
            return (
                isinstance(value, int)
                and not isinstance(value, bool)
                and 0 <= value <= TELEMETRY_MAX_COUNTER_VALUE
            )

        def valid_percentage(value):
            import math

            return (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and 0 <= value <= 100
            )

        if (
            not valid_percentage(cpu)
            or not valid_percentage(memory)
            or isinstance(memory_total, bool)
            or not isinstance(memory_total, int)
            or memory_total <= 0
            or isinstance(memory_available, bool)
            or not isinstance(memory_available, int)
            or memory_available < 0
            or memory_available > memory_total
            or (
                "network_rx_bytes" in data
                and not (
                    valid_counter(network_rx)
                    and valid_counter(network_tx)
                )
            )
            or (
                "system" in data
                and not validate_system_snapshot(data["system"])
            )
        ):
            return jsonify({
                "status": "error",
                "message": "Invalid telemetry values",
            }), 400

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=TELEMETRY_RETENTION_DAYS)
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                # Serialize ingestion for this client. This prevents two
                # concurrent snapshots from deriving transitions from
                # the same outdated system status.
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
                    return jsonify({
                        "error": "client_authentication_required"
                    }), 401

                if "system" in data:
                    previous_row = connection.execute(
                        """
                        SELECT recorded_at, payload_json
                        FROM client_system_status
                        WHERE client_id = %s
                        """,
                        (client["id"],),
                    ).fetchone()

                    previous = None
                    elapsed = 0

                    if previous_row is not None:
                        previous = _decode_json_object(
                            previous_row["payload_json"]
                        )
                        previous_time = parse_telemetry_time(
                            previous_row["recorded_at"]
                        )
                        if previous_time is not None:
                            elapsed = (
                                now - previous_time
                            ).total_seconds()

                    record_telemetry_system_events(
                        connection,
                        client["id"],
                        now,
                        previous,
                        data["system"],
                    )

                    system = add_system_interface_rates(
                        data["system"],
                        previous,
                        elapsed,
                    )

                    connection.execute(
                        """
                        INSERT INTO client_system_status (
                            client_id, recorded_at, payload_json
                        ) VALUES (%s, %s, %s)
                        ON CONFLICT (client_id) DO UPDATE SET
                            recorded_at = EXCLUDED.recorded_at,
                            payload_json = EXCLUDED.payload_json
                        """,
                        (
                            client["id"],
                            now,
                            Jsonb(system),
                        ),
                    )

                disk_percent = None
                system_data = data.get("system")
                disk = (
                    system_data.get("disk")
                    if isinstance(system_data, dict)
                    else None
                )
                if disk:
                    disk_percent = round(
                        100 * disk["used_bytes"] / disk["total_bytes"],
                        2,
                    )

                connection.execute(
                    """
                    INSERT INTO client_telemetry (
                        client_id, recorded_at, cpu_percent,
                        memory_percent, memory_total_bytes,
                        memory_available_bytes, network_rx_bytes,
                        network_tx_bytes, disk_percent
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        client["id"],
                        now,
                        float(cpu),
                        float(memory),
                        memory_total,
                        memory_available,
                        network_rx,
                        network_tx,
                        disk_percent,
                    ),
                )

                connection.execute(
                    """
                    DELETE FROM client_telemetry
                    WHERE recorded_at < %s
                    """,
                    (cutoff,),
                )
                connection.execute(
                    """
                    DELETE FROM client_telemetry_events
                    WHERE recorded_at < %s
                    """,
                    (cutoff,),
                )

            return jsonify({"status": "received"}), 200

        except (
            DatabaseDriverError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            current_app.logger.exception(
                "Failed to save PostgreSQL telemetry from client %s",
                client["id"],
            )
            return jsonify({
                "status": "error",
                "message": "Failed to save telemetry",
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    @app.get("/api/clients/<int:client_id>/telemetry")
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="clients.view",
    )
    def client_telemetry(client_id):
        try:
            hours = int(request.args.get("hours", "24"))
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_hours"}), 400

        if not 1 <= hours <= TELEMETRY_MAX_HISTORY_HOURS:
            return jsonify({"error": "invalid_hours"}), 400

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL "
                    "REPEATABLE READ, READ ONLY"
                )

                client = connection.execute(
                    """
                    SELECT id, hostname
                    FROM clients
                    WHERE id = %s AND enabled = TRUE
                    """,
                    (client_id,),
                ).fetchone()

                if client is None:
                    return jsonify({
                        "error": "client_not_found"
                    }), 404

                rows = telemetry_history_rows(
                    connection,
                    client_id,
                    hours,
                )

                samples = []
                for row in rows:
                    sample = dict(row)
                    sample["recorded_at"] = _iso_timestamp(
                        sample["recorded_at"]
                    )
                    samples.append(sample)

            return jsonify({
                "client_id": client_id,
                "hostname": client["hostname"],
                "hours": hours,
                "samples": samples,
            })

        except DatabaseDriverError:
            current_app.logger.exception(
                "Failed to load PostgreSQL telemetry for client %s",
                client_id,
            )
            return jsonify({
                "error": "telemetry_query_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()



    @app.route(
        "/api/telemetry/dashboard-settings",
        methods=["GET", "PUT"],
    )
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="clients.view",
    )
    @csrf_required
    def telemetry_dashboard_settings():
        user_id = current_user_id()
        settings_input = None

        if request.method == "PUT":
            settings_input = request.get_json(silent=True)
            if not validate_telemetry_dashboard_settings(settings_input):
                return jsonify({
                    "error": "invalid_dashboard_settings"
                }), 400

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                if request.method == "GET":
                    row = connection.execute(
                        """
                        SELECT settings_json
                        FROM user_dashboard_settings
                        WHERE user_id = %s
                        """,
                        (user_id,),
                    ).fetchone()

                    if row is None:
                        return jsonify(
                            default_telemetry_dashboard_settings()
                        )

                    settings = _decode_json_object(row["settings_json"])
                    migrated = migrate_telemetry_dashboard_settings(
                        settings
                    )

                    if (
                        migrated != settings
                        and validate_telemetry_dashboard_settings(migrated)
                    ):
                        settings = migrated
                        connection.execute(
                            """
                            UPDATE user_dashboard_settings
                            SET settings_json = %s, updated_at = %s
                            WHERE user_id = %s
                            """,
                            (
                                Jsonb(settings),
                                datetime.now(timezone.utc),
                                user_id,
                            ),
                        )

                    if not validate_telemetry_dashboard_settings(settings):
                        current_app.logger.error(
                            "Invalid telemetry dashboard settings "
                            "for PostgreSQL user %s",
                            user_id,
                        )
                        return jsonify({
                            "error": "dashboard_settings_invalid"
                        }), 500

                    return jsonify(settings)

                connection.execute(
                    """
                    INSERT INTO user_dashboard_settings (
                        user_id, settings_json, updated_at
                    ) VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        settings_json = EXCLUDED.settings_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        user_id,
                        Jsonb(settings_input),
                        datetime.now(timezone.utc),
                    ),
                )

            return jsonify({"status": "saved"})

        except (
            DatabaseDriverError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            current_app.logger.exception(
                "Unable to load or save PostgreSQL dashboard settings "
                "for user %s",
                user_id,
            )
            return jsonify({
                "error": "dashboard_settings_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    @app.get(
        "/api/clients/<int:client_id>/telemetry/events"
    )
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="clients.view",
    )
    def client_telemetry_events(client_id):
        hours = parse_telemetry_hours()
        if hours is None:
            return jsonify({"error": "invalid_hours"}), 400

        export_format = request.args.get("format", "json").lower()
        if export_format not in ("json", "csv"):
            return jsonify({"error": "invalid_format"}), 400

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL "
                    "REPEATABLE READ, READ ONLY"
                )

                client = connection.execute(
                    """
                    SELECT id, hostname
                    FROM clients
                    WHERE id = %s AND enabled = TRUE
                    """,
                    (client_id,),
                ).fetchone()

                if client is None:
                    return jsonify({
                        "error": "client_not_found"
                    }), 404

                settings_row = connection.execute(
                    """
                    SELECT settings_json
                    FROM user_dashboard_settings
                    WHERE user_id = %s
                    """,
                    (current_user_id(),),
                ).fetchone()

                settings = (
                    _decode_json_object(settings_row["settings_json"])
                    if settings_row is not None
                    else default_telemetry_dashboard_settings()
                )
                settings = migrate_telemetry_dashboard_settings(settings)

                if not validate_telemetry_dashboard_settings(settings):
                    return jsonify({
                        "error": "dashboard_settings_invalid"
                    }), 500

                rows = telemetry_history_rows(
                    connection,
                    client_id,
                    hours,
                    downsample=False,
                )
                events = telemetry_events_from_rows(
                    rows,
                    settings["thresholds"],
                )

                cutoff = (
                    datetime.now(timezone.utc)
                    - timedelta(hours=hours)
                )

                persisted_rows = connection.execute(
                    """
                    SELECT recorded_at, event_type, metric, value
                    FROM client_telemetry_events
                    WHERE client_id = %s AND recorded_at >= %s
                    ORDER BY recorded_at DESC
                    LIMIT 500
                    """,
                    (client_id, cutoff),
                ).fetchall()

                events.extend({
                    "timestamp": _iso_timestamp(row["recorded_at"]),
                    "kind": row["event_type"],
                    "metric": row["metric"],
                    "value": row["value"],
                    "threshold": None,
                } for row in persisted_rows)

                system_row = connection.execute(
                    """
                    SELECT recorded_at, payload_json
                    FROM client_system_status
                    WHERE client_id = %s
                    """,
                    (client_id,),
                ).fetchone()

                if system_row is not None:
                    system_time = parse_telemetry_time(
                        system_row["recorded_at"]
                    )
                    system = _decode_json_object(
                        system_row["payload_json"]
                    )
                    security = system.get("security_events", {})

                    failed_at = parse_telemetry_time(
                        security.get("ssh_last_failed_at")
                    )

                    if failed_at is not None and failed_at >= cutoff:
                        if not any(
                            event["kind"] == "ssh_failure"
                            and event["metric"] == "ssh"
                            for event in events
                        ):
                            events.append({
                                "timestamp": failed_at.isoformat(),
                                "kind": "ssh_failure",
                                "metric": "ssh",
                                "value": security.get("ssh_failed_24h"),
                                "threshold": None,
                            })

                    services = system.get(
                        "services", {}
                    ).get("items", [])

                    if system_time is not None and system_time >= cutoff:
                        for service in services:
                            if service.get("state") == "failed":
                                name = service.get("name", "service")
                                if not any(
                                    event["kind"] == "service_failed"
                                    and event["metric"] == name
                                    for event in events
                                ):
                                    events.append({
                                        "timestamp": system_time.isoformat(),
                                        "kind": "service_failed",
                                        "metric": name,
                                        "value": None,
                                        "threshold": None,
                                    })

                minimum_time = datetime.min.replace(
                    tzinfo=timezone.utc
                )
                events.sort(
                    key=lambda event: (
                        parse_telemetry_time(event["timestamp"])
                        or minimum_time
                    ),
                    reverse=True,
                )
                events = events[:500]

            if export_format == "csv":
                return _csv_response(
                    f"telemetry-events-client-{client_id}.csv",
                    ("timestamp", "kind", "metric", "value", "threshold"),
                    events,
                )

            return jsonify({
                "client_id": client_id,
                "hostname": client["hostname"],
                "hours": hours,
                "events": events,
            })

        except (
            DatabaseDriverError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            current_app.logger.exception(
                "Failed to load PostgreSQL telemetry events "
                "for client %s",
                client_id,
            )
            return jsonify({
                "error": "telemetry_events_query_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    @app.get(
        "/api/clients/<int:client_id>/telemetry/export"
    )
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="clients.view",
    )
    def export_client_telemetry(client_id):
        hours = parse_telemetry_hours()
        if hours is None:
            return jsonify({"error": "invalid_hours"}), 400

        export_format = request.args.get("format", "csv").lower()
        if export_format not in ("csv", "json"):
            return jsonify({"error": "invalid_format"}), 400

        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL "
                    "REPEATABLE READ, READ ONLY"
                )

                client = connection.execute(
                    """
                    SELECT id, hostname
                    FROM clients
                    WHERE id = %s AND enabled = TRUE
                    """,
                    (client_id,),
                ).fetchone()

                if client is None:
                    return jsonify({
                        "error": "client_not_found"
                    }), 404

                rows = telemetry_history_rows(
                    connection,
                    client_id,
                    hours,
                    downsample=False,
                )

                fields = (
                    "recorded_at",
                    "cpu_percent",
                    "memory_percent",
                    "memory_total_bytes",
                    "memory_available_bytes",
                    "disk_percent",
                    "network_rx_bytes_per_second",
                    "network_tx_bytes_per_second",
                )

                samples = []
                for row in rows:
                    sample = {
                        key: row.get(key)
                        for key in fields
                    }
                    sample["recorded_at"] = _iso_timestamp(
                        sample["recorded_at"]
                    )
                    samples.append(sample)

            if export_format == "csv":
                return _csv_response(
                    f"telemetry-client-{client_id}-{hours}h.csv",
                    fields,
                    samples,
                )

            response = jsonify({
                "client_id": client_id,
                "hostname": client["hostname"],
                "hours": hours,
                "samples": samples,
            })
            response.headers["Content-Disposition"] = (
                f'attachment; filename="telemetry-client-{client_id}-'
                f'{hours}h.json"'
            )
            response.headers["Cache-Control"] = "no-store"
            return response

        except DatabaseDriverError:
            current_app.logger.exception(
                "Failed to export PostgreSQL telemetry "
                "for client %s",
                client_id,
            )
            return jsonify({
                "error": "telemetry_export_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

    @app.get("/api/telemetry/overview")
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="clients.view",
    )
    def telemetry_overview():
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL "
                    "REPEATABLE READ, READ ONLY"
                )

                clients = connection.execute(
                    """
                    SELECT id, hostname, last_seen
                    FROM clients
                    WHERE enabled = TRUE
                    ORDER BY lower(hostname)
                    """
                ).fetchall()

                now = datetime.now(timezone.utc)
                result = []

                for client in clients:
                    latest_rows = connection.execute(
                        """
                        SELECT
                            recorded_at,
                            cpu_percent,
                            memory_percent,
                            memory_total_bytes,
                            memory_available_bytes,
                            network_rx_bytes,
                            network_tx_bytes
                        FROM client_telemetry
                        WHERE client_id = %s
                        ORDER BY recorded_at DESC
                        LIMIT 2
                        """,
                        (client["id"],),
                    ).fetchall()

                    samples = add_network_rates(
                        reversed(latest_rows)
                    )
                    latest = dict(samples[-1]) if samples else None

                    age = None
                    if latest is not None:
                        recorded = parse_telemetry_time(
                            latest["recorded_at"]
                        )
                        if recorded is not None:
                            age = max(
                                0,
                                int((now - recorded).total_seconds()),
                            )
                        latest["recorded_at"] = _iso_timestamp(
                            latest["recorded_at"]
                        )

                    system_row = connection.execute(
                        """
                        SELECT recorded_at, payload_json
                        FROM client_system_status
                        WHERE client_id = %s
                        """,
                        (client["id"],),
                    ).fetchone()

                    system_age = None
                    system = None

                    if system_row is not None:
                        system_recorded = parse_telemetry_time(
                            system_row["recorded_at"]
                        )
                        if system_recorded is not None:
                            system_age = max(
                                0,
                                int(
                                    (now - system_recorded).total_seconds()
                                ),
                            )

                        system = _decode_json_object(
                            system_row["payload_json"]
                        )

                    result.append({
                        "client_id": client["id"],
                        "hostname": client["hostname"],
                        "status": classify_health_client(
                            client["last_seen"],
                            now=now,
                        ),
                        "last_seen": _iso_timestamp(client["last_seen"]),
                        "telemetry_age_seconds": age,
                        "telemetry_stale": (
                            age is None
                            or age > TELEMETRY_STALE_SECONDS
                        ),
                        "system_age_seconds": system_age,
                        "system": system,
                        "latest": latest,
                    })

            return jsonify({"clients": result})

        except (
            DatabaseDriverError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            current_app.logger.exception(
                "Failed to load PostgreSQL telemetry overview"
            )
            return jsonify({
                "error": "telemetry_query_failed"
            }), 500

        finally:
            if connection is not None and not connection.closed:
                connection.close()

# Shared telemetry validation and calculation helpers.

TELEMETRY_RETENTION_DAYS = 7

TELEMETRY_MAX_HISTORY_HOURS = 168

TELEMETRY_MAX_RESPONSE_POINTS = 1000

TELEMETRY_MAX_COUNTER_VALUE = 2**63 - 1

TELEMETRY_MAX_RATE_GAP_SECONDS = 300

TELEMETRY_STALE_SECONDS = 120

TELEMETRY_WIDGET_WIDTHS = (4, 6, 8, 12)

TELEMETRY_WIDGET_IDS = (
    "summary", "clients", "history", "events", "backup",
)

TELEMETRY_INTEGRATIONS = ("wazuh", "suricata")

def default_telemetry_dashboard_settings():
    return {
        "layout": [
            {"id": "summary", "width": 12, "visible": True},
            {"id": "clients", "width": 4, "visible": True},
            {"id": "history", "width": 8, "visible": True},
            {"id": "events", "width": 12, "visible": True},
            {"id": "backup", "width": 6, "visible": True},
        ],
        "thresholds": {"cpu": 90, "memory": 90, "disk": 90},
        "integrations": {"wazuh": False, "suricata": False},
    }

def validate_telemetry_dashboard_settings(settings):
    if not isinstance(settings, dict) or set(settings) != {
        "layout", "thresholds", "integrations",
    }:
        return False
    layout = settings["layout"]
    if not isinstance(layout, list) or len(layout) != len(TELEMETRY_WIDGET_IDS):
        return False
    seen = set()
    for widget in layout:
        if (
            not isinstance(widget, dict)
            or set(widget) != {"id", "width", "visible"}
            or widget["id"] not in TELEMETRY_WIDGET_IDS
            or widget["id"] in seen
            or isinstance(widget["width"], bool)
            or widget["width"] not in TELEMETRY_WIDGET_WIDTHS
            or not isinstance(widget["visible"], bool)
        ):
            return False
        seen.add(widget["id"])
    thresholds = settings["thresholds"]
    if (
        not isinstance(thresholds, dict)
        or set(thresholds) != {"cpu", "memory", "disk"}
        or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 50 <= value <= 99
            for value in thresholds.values()
        )
    ):
        return False
    integrations = settings["integrations"]
    return (
        isinstance(integrations, dict)
        and set(integrations) == set(TELEMETRY_INTEGRATIONS)
        and all(isinstance(value, bool) for value in integrations.values())
    )

def migrate_telemetry_dashboard_settings(settings):
    if (
        not isinstance(settings, dict)
        or not isinstance(settings.get("layout"), list)
        or not any(
            isinstance(widget, dict) and widget.get("id") == "system"
            for widget in settings["layout"]
        )
    ):
        return settings

    migrated = dict(settings)
    migrated["layout"] = [
        widget for widget in settings["layout"]
        if not (isinstance(widget, dict) and widget.get("id") == "system")
    ]
    return migrated

def add_network_rates(rows):
    """Turn cumulative byte counters into bytes per second.

    Rows must be ordered by time. A rate is None when counters are missing,
    were reset (reboot), or the gap between samples is too long.
    """
    samples = []
    previous = None
    for row in rows:
        sample = dict(row)
        rx = sample.pop("network_rx_bytes", None)
        tx = sample.pop("network_tx_bytes", None)
        sample["network_rx_bytes_per_second"] = None
        sample["network_tx_bytes_per_second"] = None

        current_time = parse_telemetry_time(sample["recorded_at"])
        if (
            previous is not None
            and current_time is not None
            and rx is not None
            and tx is not None
        ):
            prev_time, prev_rx, prev_tx = previous
            seconds = (current_time - prev_time).total_seconds()
            if (
                prev_rx is not None
                and 0 < seconds <= TELEMETRY_MAX_RATE_GAP_SECONDS
                and rx >= prev_rx
                and tx >= prev_tx
            ):
                sample["network_rx_bytes_per_second"] = round(
                    (rx - prev_rx) / seconds, 2
                )
                sample["network_tx_bytes_per_second"] = round(
                    (tx - prev_tx) / seconds, 2
                )

        previous = (
            (current_time, rx, tx) if current_time is not None else None
        )
        samples.append(sample)
    return samples

def validate_system_snapshot(system):
    def is_counter(value):
        return (
            isinstance(value, int)
            and not isinstance(value, bool)
            and 0 <= value <= TELEMETRY_MAX_COUNTER_VALUE
        )

    def is_text(value, maximum):
        return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum

    def is_optional_bool(value):
        return value is None or isinstance(value, bool)

    required = {
        "load_average", "uptime_seconds", "os", "kernel", "disk",
        "interfaces", "dns_servers", "gateway", "gateway_reachable",
        "dns_reachable", "internet_reachable", "temperatures", "fans",
        "services", "containers",
    }
    if not isinstance(system, dict) or set(system) not in (
        required, required | {"security_events"}
    ):
        return False

    loads = system["load_average"]
    if loads is not None and (
        not isinstance(loads, list)
        or len(loads) != 3
        or any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
            or value > 1_000_000
            or not math.isfinite(value)
            for value in loads
        )
    ):
        return False

    uptime = system["uptime_seconds"]
    if uptime is not None and not is_counter(uptime):
        return False
    if not is_text(system["os"], 128) or not is_text(system["kernel"], 128):
        return False

    disk = system["disk"]
    if disk is not None and (
        not isinstance(disk, dict)
        or set(disk) != {"total_bytes", "used_bytes", "free_bytes"}
        or not all(is_counter(disk[key]) for key in disk)
        or disk["total_bytes"] <= 0
        or disk["used_bytes"] > disk["total_bytes"]
        or disk["free_bytes"] > disk["total_bytes"]
    ):
        return False

    interfaces = system["interfaces"]
    if not isinstance(interfaces, list) or len(interfaces) > 32:
        return False
    interface_names = set()
    for interface in interfaces:
        if (
            not isinstance(interface, dict)
            or set(interface) != {
                "name", "state", "rx_bytes", "tx_bytes", "rx_errors",
                "tx_errors", "rx_dropped", "tx_dropped",
            }
            or not is_text(interface["name"], 32)
            or interface["name"] in interface_names
            or interface["state"] not in (
                "up", "down", "unknown", "dormant", "lowerlayerdown"
            )
            or not all(
                is_counter(interface[key])
                for key in (
                    "rx_bytes", "tx_bytes", "rx_errors", "tx_errors",
                    "rx_dropped", "tx_dropped",
                )
            )
        ):
            return False
        interface_names.add(interface["name"])

    dns_servers = system["dns_servers"]
    if not isinstance(dns_servers, list) or len(dns_servers) > 8:
        return False
    try:
        if any(
            not isinstance(server, str)
            or str(ipaddress.ip_address(server)) != server
            for server in dns_servers
        ):
            return False
        if system["gateway"] is not None:
            if not isinstance(system["gateway"], str):
                return False
            ipaddress.IPv4Address(system["gateway"])
    except (ipaddress.AddressValueError, TypeError):
        return False

    if not all(
        is_optional_bool(system[key])
        for key in (
            "gateway_reachable", "dns_reachable", "internet_reachable"
        )
    ):
        return False

    temperatures = system["temperatures"]
    if not isinstance(temperatures, list) or len(temperatures) > 16:
        return False
    for sensor in temperatures:
        value = sensor.get("celsius") if isinstance(sensor, dict) else None
        if (
            not isinstance(sensor, dict)
            or set(sensor) != {"name", "celsius"}
            or not is_text(sensor["name"], 64)
            or not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not -50 <= value <= 250
            or not math.isfinite(value)
        ):
            return False

    fans = system["fans"]
    if not isinstance(fans, list) or len(fans) > 16:
        return False
    for fan in fans:
        if (
            not isinstance(fan, dict)
            or set(fan) != {"name", "rpm"}
            or not is_text(fan["name"], 64)
            or not is_counter(fan["rpm"])
            or fan["rpm"] > 100_000
        ):
            return False

    legacy_snapshot = "security_events" not in system
    for key, max_items in (
        ("services", 60 if legacy_snapshot else 20),
        ("containers", 60),
    ):
        collection = system[key]
        if (
            not isinstance(collection, dict)
            or set(collection) != {"available", "items"}
            or not isinstance(collection["available"], bool)
            or not isinstance(collection["items"], list)
            or len(collection["items"]) > max_items
        ):
            return False
        for item in collection["items"]:
            if key == "services":
                if not isinstance(item, dict) or not is_text(item.get("name"), 128):
                    return False
                if set(item) == {"name", "state"}:
                    if item["state"] not in ("active", "failed", "inactive"):
                        return False
                elif (
                    set(item) != {
                        "name", "state", "substate", "restarts",
                        "runtime_seconds",
                    }
                    or item["state"] not in (
                        "active", "failed", "inactive", "unknown"
                    )
                    or not is_text(item["substate"], 64)
                    or (
                        item["restarts"] is not None
                        and not is_counter(item["restarts"])
                    )
                    or (
                        item["runtime_seconds"] is not None
                        and not is_counter(item["runtime_seconds"])
                    )
                ):
                    return False
            elif (
                not isinstance(item, dict)
                or set(item) != {"runtime", "name", "state"}
                or item["runtime"] not in ("docker", "podman")
                or not is_text(item["name"], 128)
                or not is_text(item["state"], 64)
                or (
                    not legacy_snapshot
                    and item["state"] not in (
                        "up", "stopped", "unhealthy", "unknown"
                    )
                )
            ):
                return False

    if legacy_snapshot:
        try:
            return len(json.dumps(system, allow_nan=False).encode("utf-8")) <= 32768
        except (TypeError, ValueError):
            return False

    events = system["security_events"]
    if not isinstance(events, dict) or set(events) != {
        "ssh_available", "ssh_failed_24h", "ssh_last_failed_at",
        "journal_available", "journal_errors_1h", "journal_warnings_1h",
        "login_history_available", "login_events",
        "boot_history_available", "boot_history",
    }:
        return False
    for key in (
        "ssh_available", "journal_available",
        "login_history_available", "boot_history_available",
    ):
        if not isinstance(events[key], bool):
            return False
    for key in (
        "ssh_failed_24h", "journal_errors_1h", "journal_warnings_1h",
    ):
        if not is_counter(events[key]):
            return False
    last_ssh = events["ssh_last_failed_at"]
    if last_ssh is not None and (
        not is_text(last_ssh, 64) or parse_telemetry_time(last_ssh) is None
    ):
        return False
    login_events = events["login_events"]
    if not isinstance(login_events, list) or len(login_events) > 20:
        return False
    for event in login_events:
        if (
            not isinstance(event, dict)
            or set(event) != {"timestamp", "action"}
            or not is_text(event["timestamp"], 64)
            or parse_telemetry_time(event["timestamp"]) is None
            or event["action"] not in ("login", "logout")
        ):
            return False
    boot_history = events["boot_history"]
    if not isinstance(boot_history, list) or len(boot_history) > 10:
        return False
    for boot in boot_history:
        if (
            not isinstance(boot, dict)
            or set(boot) != {"started_at", "ended_at"}
            or not is_text(boot["started_at"], 64)
            or not is_text(boot["ended_at"], 64)
        ):
            return False

    try:
        return len(json.dumps(system, allow_nan=False).encode("utf-8")) <= 32768
    except (TypeError, ValueError):
        return False

def add_system_interface_rates(system, previous, seconds):
    result = dict(system)
    previous_interfaces = {
        interface["name"]: interface
        for interface in (previous or {}).get("interfaces", [])
    }
    interfaces = []
    for interface in system["interfaces"]:
        current = dict(interface)
        old = previous_interfaces.get(current["name"])
        rx_rate = None
        tx_rate = None
        if old and 0 < seconds <= TELEMETRY_MAX_RATE_GAP_SECONDS:
            if current["rx_bytes"] >= old["rx_bytes"]:
                rx_rate = round(
                    (current["rx_bytes"] - old["rx_bytes"]) / seconds, 2
                )
            if current["tx_bytes"] >= old["tx_bytes"]:
                tx_rate = round(
                    (current["tx_bytes"] - old["tx_bytes"]) / seconds, 2
                )
        current["rx_bytes_per_second"] = rx_rate
        current["tx_bytes_per_second"] = tx_rate
        interfaces.append(current)
    result["interfaces"] = interfaces
    return result

def record_telemetry_system_events(
    connection, client_id, recorded_at, previous, current
):
    previous_services = {
        item["name"]: item["state"]
        for item in (previous or {}).get("services", {}).get("items", [])
    }
    for service in current.get("services", {}).get("items", []):
        name = service["name"]
        old_state = previous_services.get(name)
        state = service["state"]
        if state == "failed" and old_state != "failed":
            event_type = "service_failed"
        elif state in ("active", "inactive") and old_state == "failed":
            event_type = "service_recovered"
        else:
            continue
        connection.execute(
            """
            INSERT INTO client_telemetry_events (
                client_id, recorded_at, event_type, metric, value
            ) VALUES (%s, %s, %s, %s, NULL)
            """,
            (client_id, recorded_at, event_type, name),
        )

    security = current.get("security_events", {})
    old_security = (previous or {}).get("security_events", {})
    last_failed = parse_telemetry_time(
        security.get("ssh_last_failed_at")
    )
    previous_failed = parse_telemetry_time(
        old_security.get("ssh_last_failed_at")
    )
    recorded_time = parse_telemetry_time(recorded_at)
    if (
        last_failed is not None
        and (previous_failed is None or last_failed > previous_failed)
        and recorded_time is not None
        and last_failed <= recorded_time + timedelta(minutes=5)
    ):
        connection.execute(
            """
            INSERT INTO client_telemetry_events (
                client_id, recorded_at, event_type, metric, value
            ) VALUES (%s, %s, 'ssh_failure', 'ssh', %s)
            """,
            (
                client_id,
                last_failed,
                security.get("ssh_failed_24h"),
            ),
        )

def telemetry_events_from_rows(rows, thresholds, now=None):
    now = now or datetime.now(timezone.utc)
    events = []
    active = {"cpu": False, "memory": False, "disk": False}
    previous_time = None
    metric_keys = (
        ("cpu", "cpu_percent"),
        ("memory", "memory_percent"),
        ("disk", "disk_percent"),
    )
    for row in rows:
        recorded = parse_telemetry_time(row["recorded_at"])
        if recorded is None:
            continue
        if previous_time is not None:
            gap = (recorded - previous_time).total_seconds()
            if gap > TELEMETRY_STALE_SECONDS:
                events.append({
                    "timestamp": (
                        previous_time
                        + timedelta(seconds=TELEMETRY_STALE_SECONDS)
                    ).isoformat(),
                    "kind": "telemetry_lost",
                    "metric": None,
                    "value": None,
                    "threshold": None,
                })
                events.append({
                    "timestamp": recorded.isoformat(),
                    "kind": "telemetry_restored",
                    "metric": None,
                    "value": None,
                    "threshold": None,
                })
        for metric, key in metric_keys:
            value = row[key]
            exceeded = value is not None and value >= thresholds[metric]
            if exceeded and not active[metric]:
                events.append({
                    "timestamp": recorded.isoformat(),
                    "kind": "threshold_exceeded",
                    "metric": metric,
                    "value": value,
                    "threshold": thresholds[metric],
                })
            elif not exceeded and active[metric]:
                events.append({
                    "timestamp": recorded.isoformat(),
                    "kind": "threshold_recovered",
                    "metric": metric,
                    "value": value,
                    "threshold": thresholds[metric],
                })
            active[metric] = exceeded
        previous_time = recorded

    if previous_time is not None:
        if (now - previous_time).total_seconds() > TELEMETRY_STALE_SECONDS:
            events.append({
                "timestamp": (
                    previous_time
                    + timedelta(seconds=TELEMETRY_STALE_SECONDS)
                ).isoformat(),
                "kind": "telemetry_lost",
                "metric": None,
                "value": None,
                "threshold": None,
            })
    return sorted(events, key=lambda event: event["timestamp"], reverse=True)[:500]

def parse_telemetry_hours():
    try:
        hours = int(request.args.get("hours", "24"))
    except (TypeError, ValueError):
        return None
    return hours if 1 <= hours <= TELEMETRY_MAX_HISTORY_HOURS else None
