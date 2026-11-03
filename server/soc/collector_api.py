"""
LUMS SOC Collector API.

Contains only the collector event-ingestion endpoint.
The module does not initialize or migrate database schemas.
"""

import logging

from flask import Blueprint, current_app, g, jsonify, request


logger = logging.getLogger(__name__)

collector_bp = Blueprint(
    "collector",
    __name__,
    url_prefix="/alerts",
)


def _collector_connection():
    """Get a request-local DB connection without initializing AlertManager."""
    connection = getattr(g, "lums_alert_connection", None)
    if connection is not None:
        return connection

    connection_factory = current_app.config.get("LUMS_GET_CONNECTION")
    if not callable(connection_factory):
        raise RuntimeError(
            "Collector database connection factory is not configured"
        )

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


@collector_bp.route("/api/collector/v1/events", methods=["POST"])
def ingest_collector_events():
    """Accept bounded events only from enabled, registered collectors."""
    from werkzeug.exceptions import BadRequest

    if current_app.config.get("LUMS_SOC_COLLECTOR_ENABLED") is not True:
        return jsonify({"error": "soc_collector_disabled"}), 503

    fingerprint = _verified_collector_fingerprint()
    if fingerprint is None:
        return jsonify({"error": "collector_identity_required"}), 401

    try:
        if __package__ == "server.soc":
            from server.soc.ingestion import EventIngestor, IngestionError
            from server.soc.collector_store import (
                CollectorStore,
                CollectorNotFoundError,
                CollectorRevokedError,
                EventIdConflictError,
            )
        else:
            from .ingestion import EventIngestor, IngestionError
            from .collector_store import (
                CollectorStore,
                CollectorNotFoundError,
                CollectorRevokedError,
                EventIdConflictError,
            )
    except Exception:
        logger.exception(
            "Collector event ingestion dependencies could not be loaded"
        )
        return jsonify({"error": "collector_ingestion_failed"}), 500

    try:
        # Runtime requests must never create or migrate database schema.
        # SOC storage is initialized by the application entrypoint.
        store = CollectorStore(
            _collector_connection(),
            initialize_schema=False,
        )

        # Reject unknown or revoked identities before reading and validating
        # an attacker-controlled request body.
        agent = store.get_agent_by_fingerprint(fingerprint)
        if agent is None:
            return jsonify({"error": "collector_not_registered"}), 403
        if agent["status"] != "active":
            return jsonify({"error": "collector_revoked"}), 403

        max_request_bytes = 4 * 1024 * 1024
        if (
            request.content_length is not None
            and request.content_length > max_request_bytes
        ):
            return jsonify({"error": "request_too_large"}), 413

        try:
            raw = request.stream.read(max_request_bytes + 1)
        except (BadRequest, ValueError):
            return jsonify({"error": "invalid_json_payload"}), 400

        if len(raw) > max_request_bytes:
            return jsonify({"error": "request_too_large"}), 413

        import json

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

        if any(
            not isinstance(event, dict) or "timestamp" not in event
            for event in events
        ):
            raise IngestionError("Collector event timestamp is required")

        # Validate the complete batch before persisting any event.
        EventIngestor().ingest_batch(events)

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
