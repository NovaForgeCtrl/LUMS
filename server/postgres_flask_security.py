"""Flask authentication and authorization decorators for PostgreSQL."""

from __future__ import annotations

from functools import wraps

from flask import (
    abort,
    current_app,
    jsonify,
    redirect,
    request,
    url_for,
)

if __package__:
    from .postgres_authorization import load_authorization_state
    from .security import (
        PERMISSIONS,
        VALID_ROLES,
        apply_security_headers,
        configure_session,
        current_user_id,
        current_user_permissions,
        current_user_role,
        get_bearer_token,
        get_csrf_token,
        hash_client_token,
        login_user,
        logout_user,
        validate_csrf,
    )
else:
    from postgres_authorization import load_authorization_state
    from security import (
        PERMISSIONS,
        VALID_ROLES,
        apply_security_headers,
        configure_session,
        current_user_id,
        current_user_permissions,
        current_user_role,
        get_bearer_token,
        get_csrf_token,
        hash_client_token,
        login_user,
        logout_user,
        validate_csrf,
    )


def _is_api_request() -> bool:
    """Recognize APIs, including APIs nested inside Flask blueprints."""
    path = request.path
    return path.startswith("/api/") or "/api/" in path


def _get_connection():
    """Create an independent request-owned PostgreSQL connection."""
    connection_factory = current_app.config.get("LUMS_POSTGRES_GET_CONNECTION")

    if not callable(connection_factory):
        raise RuntimeError(
            "PostgreSQL connection factory is not configured"
        )

    return connection_factory()


def _redirect_to_login():
    """Redirect to the login endpoint configured by the application."""
    endpoint = current_app.config.get(
        "LUMS_LOGIN_ENDPOINT",
        "login",
    )

    if not isinstance(endpoint, str) or not endpoint.strip():
        raise RuntimeError(
            "LUMS_LOGIN_ENDPOINT must be a non-empty endpoint name"
        )

    return redirect(url_for(endpoint))


def login_required(view):
    """Verify the session against the current PostgreSQL authorization state."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = current_user_id()

        if user_id is None:
            if _is_api_request():
                return jsonify({
                    "error": "authentication_required"
                }), 401

            return _redirect_to_login()

        connection = None

        try:
            connection = _get_connection()

            state = load_authorization_state(
                connection,
                user_id,
            )

        except Exception:
            current_app.logger.exception(
                "Failed to resolve PostgreSQL authorization state "
                "for user id %r",
                user_id,
            )

            request.environ.pop("lums.user", None)
            request.environ.pop("lums.permissions", None)

            if _is_api_request():
                return jsonify({
                    "error": "authorization_state_unavailable"
                }), 503

            abort(
                503,
                description=(
                    "Authorization state is temporarily unavailable."
                ),
            )

        finally:
            if connection is not None:
                connection.close()

        if state is None:
            logout_user()
            request.environ.pop("lums.user", None)
            request.environ.pop("lums.permissions", None)

            if _is_api_request():
                return jsonify({
                    "error": "authentication_required"
                }), 401

            return _redirect_to_login()

        request.environ["lums.user"] = state.user
        request.environ["lums.permissions"] = state.permissions

        return view(*args, **kwargs)

    return wrapped


def role_required(*roles, permission=None):
    """Authorize a request using its PostgreSQL-resolved user state."""
    required_roles = set(roles)

    if not required_roles and permission is None:
        raise ValueError(
            "role_required() requires at least one role."
        )

    if not required_roles.issubset(VALID_ROLES):
        invalid_roles = sorted(
            required_roles - VALID_ROLES
        )
        raise ValueError(
            f"Unknown LUMS role(s): {invalid_roles}"
        )

    if permission is not None and permission not in PERMISSIONS:
        raise ValueError(
            f"Unknown LUMS permission: {permission}"
        )

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = request.environ.get("lums.user")

            if user is None:
                if _is_api_request():
                    return jsonify({
                        "error": "authentication_required"
                    }), 401

                return _redirect_to_login()

            authorized = (
                permission in current_user_permissions()
                if permission is not None
                else user["role"] in required_roles
            )

            if not authorized:
                return jsonify({
                    "error": "authorization_required"
                }), 403

            return view(*args, **kwargs)

        return wrapped

    return decorator


def csrf_required(view):
    """Enforce the existing LUMS CSRF policy."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not validate_csrf():
            return jsonify({
                "error": "csrf_validation_failed"
            }), 400

        return view(*args, **kwargs)

    return wrapped


def client_auth_required(view):
    """Authenticate a client using its persisted PostgreSQL token hash."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        token = get_bearer_token()

        if not token:
            return jsonify({
                "error": "client_authentication_required"
            }), 401

        connection = None

        try:
            connection = _get_connection()

            token_hash = hash_client_token(token)

            client = connection.execute(
                """
                SELECT
                    id,
                    hostname,
                    enabled,
                    client_token_hash,
                    token_revoked_at
                FROM clients
                WHERE client_token_hash = %s
                """,
                (token_hash,),
            ).fetchone()

            if (
                client is None
                or client["enabled"] is not True
                or client["token_revoked_at"] is not None
            ):
                return jsonify({
                    "error": "client_authentication_required"
                }), 401

            request.environ["lums.client"] = dict(client)

        except Exception:
            current_app.logger.exception(
                "PostgreSQL client authentication failed"
            )
            return jsonify({
                "error": "client_authentication_unavailable"
            }), 503

        finally:
            if connection is not None:
                connection.close()

        return view(*args, **kwargs)

    return wrapped


def authenticated_client():
    """Return the client authenticated for the current request."""
    return request.environ.get("lums.client")


__all__ = [
    "apply_security_headers",
    "authenticated_client",
    "client_auth_required",
    "configure_session",
    "current_user_id",
    "current_user_permissions",
    "current_user_role",
    "csrf_required",
    "get_csrf_token",
    "login_required",
    "login_user",
    "logout_user",
    "role_required",
]
