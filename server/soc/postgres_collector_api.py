"""PostgreSQL-backed LUMS SOC collector HTTP API.

This module accepts identity only from an explicitly configured trusted
identity provider. It does not authenticate TLS peers or trust HTTP headers
by itself. The deployment must enforce the documented gateway/backend mTLS
boundary before configuring the provider.
"""

from __future__ import annotations

import json
import logging
import re

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.exceptions import BadRequest

from .collector_store import (
    CollectorNotFoundError,
    CollectorRevokedError,
    CollectorStoreError,
    EventIdConflictError,
)
from .ingestion import EventIngestor, IngestionError
from .postgres_collector_store import PostgresCollectorStore


logger = logging.getLogger(__name__)

MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_BATCH_EVENTS = 500

_FINGERPRINT_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")


postgres_collector_bp = Blueprint(
    "postgres_collector",
    __name__,
    url_prefix="/alerts",
)


def _postgres_collector_connection():
    """Return the request-local PostgreSQL connection."""
    connection = getattr(g, "lums_postgres_collector_connection", None)
    if connection is not None:
        return connection

    connection_factory = current_app.config.get(
        "LUMS_POSTGRES_GET_CONNECTION"
    )
    if not callable(connection_factory):
        raise RuntimeError(
            "PostgreSQL collector connection factory is not configured"
        )

    connection = connection_factory()
    g.lums_postgres_collector_connection = connection
    return connection


def _verified_collector_fingerprint() -> str | None:
    """Return a fingerprint from the explicitly trusted identity provider.

    The provider is responsible for obtaining certificate material across
    the authenticated gateway boundary. This function validates only the
    returned fingerprint's syntax; it does not establish proxy trust.
    """
    provider = current_app.config.get(
        "LUMS_COLLECTOR_IDENTITY_PROVIDER"
    )
    if not callable(provider):
        return None

    try:
        fingerprint = provider()
    except Exception:
        logger.warning("PostgreSQL collector identity provider failed")
        return None

    if (
        not isinstance(fingerprint, str)
        or _FINGERPRINT_PATTERN.fullmatch(fingerprint) is None
    ):
        return None

    return fingerprint.lower()


def _reject_json_constant(value: str) -> None:
    """Reject non-standard JSON constants such as NaN and Infinity."""
    raise ValueError(f"Invalid JSON constant: {value}")


@postgres_collector_bp.route(
    "/api/collector/v1/events",
    methods=["POST"],
)
def ingest_postgres_collector_events():
    """Accept a bounded, validated event batch from a registered collector."""
    if current_app.config.get("LUMS_SOC_COLLECTOR_ENABLED") is not True:
        return jsonify({"error": "soc_collector_disabled"}), 503

    fingerprint = _verified_collector_fingerprint()
    if fingerprint is None:
        return jsonify({"error": "collector_identity_required"}), 401

    try:
        store = PostgresCollectorStore(
            _postgres_collector_connection()
        )

        # Reject unknown and revoked identities before reading the body.
        # ingest_batch rechecks status under the agent lifecycle lock.
        agent = store.get_agent_by_fingerprint(fingerprint)

        if agent is None:
            return jsonify({"error": "collector_not_registered"}), 403

        if agent["status"] != "active":
            return jsonify({"error": "collector_revoked"}), 403

        if (
            request.content_length is not None
            and request.content_length > MAX_REQUEST_BYTES
        ):
            return jsonify({"error": "request_too_large"}), 413

        try:
            raw = request.stream.read(MAX_REQUEST_BYTES + 1)
        except (BadRequest, ValueError):
            return jsonify({"error": "invalid_json_payload"}), 400

        if len(raw) > MAX_REQUEST_BYTES:
            return jsonify({"error": "request_too_large"}), 413

        try:
            payload = json.loads(
                raw,
                parse_constant=_reject_json_constant,
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
            RecursionError,
        ):
            return jsonify({"error": "invalid_json_payload"}), 400

        if not isinstance(payload, dict) or set(payload) != {"events"}:
            return jsonify({"error": "invalid_json_payload"}), 400

        events = payload["events"]

        if not isinstance(events, list) or not events:
            return jsonify({"error": "invalid_event_batch"}), 400

        if len(events) > MAX_BATCH_EVENTS:
            return jsonify({"error": "batch_too_large"}), 413

        if any(
            not isinstance(event, dict) or "timestamp" not in event
            for event in events
        ):
            raise IngestionError(
                "Collector event timestamp is required"
            )

        # Validate the complete batch before attempting persistence.
        EventIngestor(
            max_batch_events=MAX_BATCH_EVENTS,
        ).ingest_batch(events)

        # The store performs the final active-agent check under the
        # same advisory lock used by registration and revocation.
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

    except CollectorStoreError:
        logger.exception("PostgreSQL collector persistence failed")
        return jsonify({"error": "collector_ingestion_failed"}), 500

    except Exception:
        logger.exception("PostgreSQL collector request failed")
        return jsonify({"error": "collector_ingestion_failed"}), 500


__all__ = [
    "MAX_BATCH_EVENTS",
    "MAX_REQUEST_BYTES",
    "postgres_collector_bp",
]
