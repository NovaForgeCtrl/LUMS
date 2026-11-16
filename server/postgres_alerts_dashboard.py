"""PostgreSQL-native Alerts dashboard page."""

from __future__ import annotations

from flask import render_template

if __package__:
    from .postgres_flask_security import (
        current_user_permissions,
        get_csrf_token,
        login_required,
        role_required,
    )
else:
    from postgres_flask_security import (
        current_user_permissions,
        get_csrf_token,
        login_required,
        role_required,
    )


def register_postgres_alert_dashboard_routes(app):
    """Register the isolated PostgreSQL alerts dashboard."""

    @login_required
    @role_required(permission="alerts.view")
    def postgres_alert_dashboard():
        permissions = current_user_permissions()

        return render_template(
            "postgres_alerts.html",
            csrf_token=get_csrf_token(),
            user_permissions=permissions,
            can_manage="alerts.manage" in permissions,
        )

    app.add_url_rule(
        "/alerts",
        endpoint="postgres_alert_dashboard",
        view_func=postgres_alert_dashboard,
        methods=["GET"],
    )
