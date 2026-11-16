"""Isolated Flask authentication routes for the PostgreSQL backend."""

from __future__ import annotations

import hmac
import logging
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

if __package__:
    from .db_transactions import transaction
    from .i18n import (
        LANGUAGES,
        browser_language,
        locale_for,
        normalize_language,
        translations_for,
        translate,
    )
    from .postgres_login import authenticate_user
    from .security import (
        SESSION_CSRF_KEY,
        current_user_id,
        get_csrf_token,
        get_login_rate_limit_key,
        login_user,
    )
else:
    from db_transactions import transaction
    from i18n import (
        LANGUAGES,
        browser_language,
        locale_for,
        normalize_language,
        translations_for,
        translate,
    )
    from postgres_login import authenticate_user
    from security import (
        SESSION_CSRF_KEY,
        current_user_id,
        get_csrf_token,
        get_login_rate_limit_key,
        login_user,
    )


logger = logging.getLogger(__name__)

postgres_auth_bp = Blueprint("postgres_auth", __name__)


def _get_postgres_connection():
    """Open a connection using only the dedicated PostgreSQL factory."""
    factory = current_app.config.get(
        "LUMS_POSTGRES_GET_CONNECTION"
    )

    if not callable(factory):
        raise RuntimeError(
            "PostgreSQL connection factory is not configured"
        )

    return factory()


def _valid_form_csrf() -> bool:
    """Validate a submitted token even on the normally exempt /login path."""
    supplied_token = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
    )
    expected_token = session.get(SESSION_CSRF_KEY)

    if (
        not isinstance(supplied_token, str)
        or not isinstance(expected_token, str)
        or not supplied_token
        or not expected_token
    ):
        return False

    return hmac.compare_digest(
        supplied_token,
        expected_token,
    )


def _login_success_endpoint() -> str:
    endpoint = current_app.config.get(
        "LUMS_LOGIN_SUCCESS_ENDPOINT",
        "index",
    )

    if not isinstance(endpoint, str) or not endpoint.strip():
        raise RuntimeError(
            "LUMS_LOGIN_SUCCESS_ENDPOINT must be a non-empty endpoint name"
        )

    return endpoint


@postgres_auth_bp.context_processor
def postgres_auth_language_context():
    """Provide the same translation context as the main LUMS application."""
    language = normalize_language(
        session.get("language")
    ) or browser_language(request.accept_languages)

    return {
        "language": language,
        "language_locale": locale_for(language),
        "languages": LANGUAGES,
        "translations": translations_for(language),
        "tr": lambda message: translate(message, language),
    }


@postgres_auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        language = normalize_language(
            session.get("language")
        ) or browser_language(request.accept_languages)

        session["language"] = language

        return render_template(
            "login.html",
            csrf_token=get_csrf_token(),
        )

    if not _valid_form_csrf():
        return jsonify({
            "error": "csrf_validation_failed"
        }), 400

    username = (
        request.form.get("username") or ""
    ).strip()
    password = request.form.get("password") or ""

    selected_language = (
        normalize_language(request.form.get("language"))
        or browser_language(request.accept_languages)
    )

    rate_limit_key = get_login_rate_limit_key(
        username,
        request.remote_addr,
    )

    connection = None

    try:
        connection = _get_postgres_connection()

        result = authenticate_user(
            connection,
            username,
            password,
            rate_limit_key,
            selected_language=selected_language,
        )

    except Exception:
        logger.exception(
            "PostgreSQL authentication service failed"
        )

        return render_template(
            "login.html",
            csrf_token=get_csrf_token(),
            error="Authentication service temporarily unavailable.",
        ), 503

    finally:
        if connection is not None:
            connection.close()

    if not result.authenticated:
        # Unknown users, disabled users, wrong passwords and rate-limited
        # accounts deliberately receive the same visible response.
        return render_template(
            "login.html",
            csrf_token=get_csrf_token(),
            error="Invalid username or password.",
            username=username,
        ), 401

    # authenticate_user() has returned only after its write transaction
    # committed. Never establish the Flask session before this point.
    login_user(
        user_id=result.user_id,
        username=result.username,
    )

    session["language"] = (
        normalize_language(result.language)
        or selected_language
    )

    return redirect(
        url_for(_login_success_endpoint())
    )


@postgres_auth_bp.route("/language", methods=["POST"])
def change_language():
    if not _valid_form_csrf():
        return jsonify({
            "error": "csrf_validation_failed"
        }), 400

    language = normalize_language(
        request.form.get("language")
    )

    if language is None:
        return jsonify({
            "error": "invalid_language"
        }), 400

    user_id = current_user_id()

    if user_id is not None:
        connection = None
        user_exists = False

        try:
            connection = _get_postgres_connection()

            with transaction(connection):
                cursor = connection.execute(
                    """
                    UPDATE users
                    SET language = %s
                    WHERE id = %s
                    """,
                    (language, user_id),
                )

                user_exists = cursor.rowcount == 1

        except Exception:
            logger.exception(
                "Unable to save the PostgreSQL language preference"
            )

            return jsonify({
                "error": "language_preference_save_failed"
            }), 503

        finally:
            if connection is not None:
                connection.close()

        if not user_exists:
            return jsonify({
                "error": "user_not_found"
            }), 404

    # Update the session only after the database transaction succeeded.
    session["language"] = language

    referrer = request.referrer

    if referrer and urlsplit(referrer).netloc == request.host:
        return redirect(referrer)

    destination = (
        _login_success_endpoint()
        if user_id is not None
        else "postgres_auth.login"
    )

    return redirect(url_for(destination))


__all__ = [
    "postgres_auth_bp",
]
