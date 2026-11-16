"""PostgreSQL-backed HTML pages for the LUMS user interface."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app, render_template

if __package__:
    from .db_errors import DatabaseDriverError
    from .db_transactions import transaction
    from .postgres_flask_security import (
        current_user_permissions,
        current_user_role,
        get_csrf_token,
        login_required,
        role_required,
    )
    from .postgres_infrastructure import classify_health_client
else:
    from db_errors import DatabaseDriverError
    from db_transactions import transaction
    from postgres_flask_security import (
        current_user_permissions,
        current_user_role,
        get_csrf_token,
        login_required,
        role_required,
    )
    from postgres_infrastructure import classify_health_client


def _get_connection():
    factory = current_app.config.get(
        "LUMS_POSTGRES_GET_CONNECTION"
    )
    if not callable(factory):
        raise RuntimeError(
            "PostgreSQL connection factory is not configured"
        )
    return factory()


def _page_context():
    return {
        "csrf_token": get_csrf_token(),
        "user_role": current_user_role(),
        "user_permissions": sorted(current_user_permissions()),
        "postgres_backend": True,
    }


def register_postgres_ui_page_routes(app):
    """Register PostgreSQL-only HTML pages."""

    @login_required
    @role_required(permission="clients.view")
    def client_page():
        return render_template(
            "client.html",
            **_page_context(),
        )

    @login_required
    @role_required(permission="clients.view")
    def health_page():
        counts = {
            "total": 0,
            "online": 0,
            "unknown": 0,
            "offline": 0,
        }
        database_status = "unavailable"
        connection = None

        try:
            connection = _get_connection()

            with transaction(connection):
                connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL "
                    "REPEATABLE READ, READ ONLY"
                )
                rows = connection.execute(
                    """
                    SELECT last_seen
                    FROM clients
                    WHERE enabled IS TRUE
                    """
                ).fetchall()

                now = datetime.now(timezone.utc)

                counts["total"] = len(rows)
                for row in rows:
                    status = classify_health_client(
                        row["last_seen"],
                        now=now,
                    )
                    counts[status] += 1

            database_status = "ok"

        except DatabaseDriverError:
            current_app.logger.exception(
                "Unable to load PostgreSQL health dashboard."
            )
            counts = {
                "total": "—",
                "online": "—",
                "unknown": "—",
                "offline": "—",
            }

        finally:
            if connection is not None and not connection.closed:
                connection.close()

        return render_template(
            "health.html",
            **_page_context(),
            monitoring_only=False,
            database_status=database_status,
            client_counts=counts,
        )

    @login_required
    @role_required(permission="clients.view")
    def monitoring_page():
        return render_template(
            "health.html",
            **_page_context(),
            monitoring_only=True,
        )

    app.add_url_rule(
        "/client",
        endpoint="client_page",
        view_func=client_page,
        methods=["GET"],
    )
    app.add_url_rule(
        "/health",
        endpoint="health_page",
        view_func=health_page,
        methods=["GET"],
    )
    app.add_url_rule(
        "/monitoring",
        endpoint="monitoring_page",
        view_func=monitoring_page,
        methods=["GET"],
    )


__all__ = ["register_postgres_ui_page_routes"]
