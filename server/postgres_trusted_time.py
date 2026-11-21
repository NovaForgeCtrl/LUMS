"""PostgreSQL-native, read-only Trusted-Time status page and API."""

from __future__ import annotations

import os
from threading import Lock
from datetime import timedelta

from flask import current_app, jsonify, render_template, url_for

from .postgres_flask_security import (
    current_user_permissions,
    current_user_role,
    get_csrf_token,
    login_required,
    role_required,
)
from .soc.chrony_time_provider import (
    ChronyTrustedTimeProvider,
    UnixSocketChronyStatusReader,
)
from .soc.trusted_time import (
    TrustedTimeError,
    TrustedTimePolicy,
    read_trusted_time,
)


# Explicitly a preview policy. These values are not a production approval.
TRUSTED_TIME_PREVIEW_POLICY = TrustedTimePolicy(
    approved_sources=frozenset({
        "time.cloudflare.com+nts.netnod.se",
    }),
    max_sync_age=timedelta(minutes=10),
    max_offset=timedelta(milliseconds=100),
    max_uncertainty=timedelta(milliseconds=50),
    clock_consistency_tolerance=timedelta(milliseconds=100),
)


def _numeric_setting(config, config_name, env_name, default):
    value = config.get(config_name, os.environ.get(env_name, default))

    if isinstance(value, bool):
        raise RuntimeError(f"{config_name} must be an integer")

    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError(
            f"{config_name} must be an integer"
        ) from exc

    if result < 0:
        raise RuntimeError(f"{config_name} must not be negative")

    return result


def _build_provider(config):
    """Build one provider per Flask app process, or remain disabled."""
    if "LUMS_TRUSTED_TIME_PROVIDER" in config:
        return config["LUMS_TRUSTED_TIME_PROVIDER"]

    socket_path = config.get(
        "LUMS_CHRONY_STATUS_SOCKET",
        os.environ.get("LUMS_CHRONY_STATUS_SOCKET"),
    )

    # No socket mount means that this deployment has no host time provider.
    if not socket_path:
        return None

    expected_uid = _numeric_setting(
        config,
        "LUMS_CHRONY_STATUS_UID",
        "LUMS_CHRONY_STATUS_UID",
        986,
    )
    expected_gid = _numeric_setting(
        config,
        "LUMS_CHRONY_STATUS_GID",
        "LUMS_CHRONY_STATUS_GID",
        987,
    )

    reader = UnixSocketChronyStatusReader(
        socket_path,
        expected_server_uid=expected_uid,
        expected_server_gid=expected_gid,
    )

    # Constructed during app creation, not per request. Each Gunicorn worker
    # therefore gets its own tracker and process-start BOOTTIME reference.
    return ChronyTrustedTimeProvider(reader)


def _get_process_provider():
    """Initialize the provider lazily inside each Gunicorn worker.

    The Flask app may be created in the Gunicorn master before fork.
    A provider created there would retain the master's PID and fail its
    process-identity check in every worker. The lock is inherited unlocked
    and becomes process-local through the worker's copy-on-write memory.
    """
    pid = os.getpid()
    lock = current_app.extensions["lums_trusted_time_provider_lock"]

    with lock:
        provider_pid = current_app.extensions.get(
            "lums_trusted_time_provider_pid"
        )

        if provider_pid != pid:
            factory = current_app.extensions[
                "lums_trusted_time_provider_factory"
            ]
            provider = factory()

            current_app.extensions[
                "lums_trusted_time_provider"
            ] = provider
            current_app.extensions[
                "lums_trusted_time_provider_pid"
            ] = pid

        return current_app.extensions.get(
            "lums_trusted_time_provider"
        )


def _read_trusted_time_payload():
    provider = _get_process_provider()
    policy = current_app.extensions[
        "lums_trusted_time_policy"
    ]

    if provider is None:
        return jsonify({
            "status": "unavailable",
            "error": "trusted_time_not_configured",
        }), 503

    try:
        trusted = read_trusted_time(
            provider,
            policy,
            process_started_boottime_ns=(
                provider.process_started_boottime_ns
            ),
        )
    except Exception as exc:
        current_app.logger.warning(
            "Trusted-Time status is unavailable: %s",
            type(exc).__name__,
        )
        return jsonify({
            "status": "unavailable",
            "error": "trusted_time_unavailable",
        }), 503

    return jsonify({
        "status": "synchronized",
        "authenticated": True,
        "source_id": trusted.source_id,
        "observed_utc": trusted.utc_now.isoformat(),
        # This is deliberately a conservative upper-bound age estimate:
        # the provider anchors at a paired observation known to predate sync.
        "sync_age_upper_bound_ms": round(
            trusted.sync_age.total_seconds() * 1000,
            3,
        ),
        "offset_ms": round(
            trusted.offset.total_seconds() * 1000,
            3,
        ),
        "uncertainty_ms": round(
            trusted.uncertainty.total_seconds() * 1000,
            3,
        ),
        "policy": {
            "name": "Preview policy – not production approved",
            "max_sync_age_seconds": (
                policy.max_sync_age.total_seconds()
            ),
            "max_offset_ms": (
                policy.max_offset.total_seconds() * 1000
            ),
            "max_uncertainty_ms": (
                policy.max_uncertainty.total_seconds() * 1000
            ),
        },
        "authentication_basis": (
            "Pinned protected Chrony configuration, "
            "authselectmode=require and both approved NTS sources "
            "selected in the validated quorum. Live chronyc authdata "
            "is not queried by the unprivileged monitor."
        ),
    }), 200


def register_postgres_trusted_time_routes(app):
    """Register authenticated PostgreSQL Trusted-Time page and API."""
    if "LUMS_TRUSTED_TIME_PROVIDER" in app.config:
        # Explicit dependency injection is used by isolated tests.
        injected_provider = app.config["LUMS_TRUSTED_TIME_PROVIDER"]

        def provider_factory():
            return injected_provider
    else:
        # Production provider creation must happen after Gunicorn forks.
        def provider_factory():
            return _build_provider(app.config)

    policy = app.config.get(
        "LUMS_TRUSTED_TIME_POLICY",
        TRUSTED_TIME_PREVIEW_POLICY,
    )

    if not isinstance(policy, TrustedTimePolicy):
        raise TypeError(
            "LUMS_TRUSTED_TIME_POLICY must be a TrustedTimePolicy"
        )

    app.extensions["lums_trusted_time_provider_factory"] = (
        provider_factory
    )
    app.extensions["lums_trusted_time_provider"] = None
    app.extensions["lums_trusted_time_provider_pid"] = None
    app.extensions["lums_trusted_time_provider_lock"] = Lock()
    app.extensions["lums_trusted_time_policy"] = policy

    @login_required
    @role_required(permission="soc.view")
    def trusted_time_page():
        return render_template(
            "trusted_time.html",
            csrf_token=get_csrf_token(),
            user_role=current_user_role(),
            user_permissions=sorted(current_user_permissions()),
            postgres_backend=True,
            trusted_time_api_url=url_for(
                "postgres_trusted_time_api"
            ),
        )

    @login_required
    @role_required(permission="soc.view")
    def trusted_time_api():
        return _read_trusted_time_payload()

    app.add_url_rule(
        "/trusted-time",
        endpoint="postgres_trusted_time_page",
        view_func=trusted_time_page,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/trusted-time",
        endpoint="postgres_trusted_time_api",
        view_func=trusted_time_api,
        methods=["GET"],
    )


__all__ = [
    "TRUSTED_TIME_PREVIEW_POLICY",
    "register_postgres_trusted_time_routes",
]
