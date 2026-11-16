"""Standalone PostgreSQL LUMS SOC Collector WSGI application.

This application exposes only the PostgreSQL collector ingestion endpoint.
It never initializes or migrates the database and is disabled by default.

Collector identity must come from an explicitly configured trusted
identity provider. A forwarded certificate header is not trusted merely
because this application can read it; the gateway/backend mTLS boundary
must be independently enforced by the deployment.
"""

from __future__ import annotations

from flask import Flask, g

from ..db import connect
from .postgres_collector_api import postgres_collector_bp


def create_postgres_collector_app(config=None) -> Flask:
    """Create an isolated PostgreSQL collector app without migrations."""
    app = Flask(
        "lums_postgres_soc_collector",
        static_folder=None,
    )

    app.config.update(
        LUMS_POSTGRES_GET_CONNECTION=connect,
        LUMS_SOC_COLLECTOR_ENABLED=False,
    )

    if config is not None:
        app.config.update(config)

    app.register_blueprint(postgres_collector_bp)

    @app.teardown_appcontext
    def close_postgres_collector_connection(exception=None):
        connection = getattr(
            g,
            "lums_postgres_collector_connection",
            None,
        )
        if connection is not None:
            try:
                connection.close()
            finally:
                g.lums_postgres_collector_connection = None

    return app


app = create_postgres_collector_app()


__all__ = [
    "app",
    "create_postgres_collector_app",
]
