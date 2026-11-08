"""PostgreSQL-backed Flask application during the LUMS migration.

Only PostgreSQL-compatible routes are registered here.
SQLite-dependent application blueprints remain in server.app.
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

if __package__:
    from .db import connect
    from .i18n import (
        LANGUAGES,
        browser_language,
        locale_for,
        normalize_language,
        translations_for,
        translate,
    )
    from .postgres_flask_security import (
        apply_security_headers,
        configure_session,
        csrf_required,
        current_user_permissions,
        current_user_role,
        get_csrf_token,
        login_required,
        logout_user,
        role_required,
    )
    from .postgres_login_routes import postgres_auth_bp
    from .postgres_clients import register_postgres_client_routes
    from .postgres_infrastructure import register_postgres_infrastructure_routes
    from .postgres_telemetry import register_postgres_telemetry_routes
    from .postgres_package_search import register_postgres_package_search_routes
    from .postgres_alerts import register_postgres_alert_routes
    from .postgres_alerts_dashboard import register_postgres_alert_dashboard_routes
    from .postgres_update_jobs import register_postgres_update_job_routes
    from .postgres_user_routes import register_postgres_user_routes
    from .security import (
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
    )
else:
    from db import connect
    from i18n import (
        LANGUAGES,
        browser_language,
        locale_for,
        normalize_language,
        translations_for,
        translate,
    )
    from postgres_flask_security import (
        apply_security_headers,
        configure_session,
        csrf_required,
        current_user_permissions,
        current_user_role,
        get_csrf_token,
        login_required,
        logout_user,
        role_required,
    )
    from postgres_login_routes import postgres_auth_bp
    from postgres_clients import register_postgres_client_routes
    from postgres_infrastructure import register_postgres_infrastructure_routes
    from postgres_telemetry import register_postgres_telemetry_routes
    from postgres_package_search import register_postgres_package_search_routes
    from postgres_alerts import register_postgres_alert_routes
    from postgres_alerts_dashboard import register_postgres_alert_dashboard_routes
    from postgres_update_jobs import register_postgres_update_job_routes
    from postgres_user_routes import register_postgres_user_routes
    from security import (
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
    )


def _load_secret_key() -> str:
    """Load the Flask secret using the existing LUMS secret convention."""
    secret_file = os.environ.get(
        "LUMS_SECRET_KEY_FILE",
        "/run/secrets/lums_secret",
    )

    try:
        secret = Path(secret_file).read_text(
            encoding="utf-8"
        ).strip()
    except FileNotFoundError:
        secret = os.environ.get("LUMS_SECRET_KEY")
    except (OSError, UnicodeError, ValueError):
        raise RuntimeError(
            "LUMS secret file could not be read."
        ) from None

    if not secret:
        raise RuntimeError(
            "LUMS secret is not configured. "
            "Provide LUMS_SECRET_KEY_FILE or LUMS_SECRET_KEY."
        )

    return secret


def create_postgres_app(config=None) -> Flask:
    """Create an isolated Flask application using PostgreSQL only."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    configure_session(app)

    app.config.update(
        LUMS_POSTGRES_GET_CONNECTION=connect,
        LUMS_LOGIN_ENDPOINT="postgres_auth.login",
        LUMS_LOGIN_SUCCESS_ENDPOINT="index",
    )

    if config is not None:
        app.config.update(config)

    app.secret_key = (
        app.config.get("SECRET_KEY")
        or _load_secret_key()
    )

    # Make the selected backend explicit for diagnostics and tests.
    app.extensions["lums_database_backend"] = "postgresql"

    @app.after_request
    def security_headers(response):
        return apply_security_headers(response)

    @app.before_request
    def initialize_language():
        if normalize_language(session.get("language")) is None:
            session["language"] = browser_language(
                request.accept_languages
            )

    @app.context_processor
    def language_context():
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

    app.register_blueprint(postgres_auth_bp)
    register_postgres_client_routes(app)
    register_postgres_infrastructure_routes(app)
    register_postgres_telemetry_routes(app)
    register_postgres_package_search_routes(app)
    register_postgres_alert_routes(app)
    register_postgres_alert_dashboard_routes(app)
    register_postgres_update_job_routes(app)
    register_postgres_user_routes(app)

    @app.post("/logout")
    @login_required
    @csrf_required
    def postgres_logout():
        logout_user()
        return redirect(url_for("postgres_auth.login"))

    @app.get("/")
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="clients.view",
    )
    def index():
        """Render the PostgreSQL-backed LUMS dashboard."""
        return render_template(
            "index.html",
            csrf_token=get_csrf_token(),
            user_role=current_user_role(),
            user_permissions=sorted(current_user_permissions()),
            postgres_backend=True,
        )

    @app.get("/api/status", endpoint="postgres_status")
    @login_required
    @role_required(
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        permission="clients.view",
    )
    def postgres_status():
        """Return PostgreSQL backend and migration status."""
        return jsonify({
            "application": "LUMS",
            "backend": "postgresql",
            "status": "migration_in_progress",
            "authenticated": True,
            "available_modules": [
                "authentication",
                "authorization",
                "language",
                "clients",
                "infrastructure",
                "telemetry",
                "package_search",
                "alerts",
                "alerts_dashboard",
                "updates",
                "user_management",
            ],
            "pending_modules": [
                "soc",
                "backups",
            ],
        })

    return app


__all__ = [
    "create_postgres_app",
]
