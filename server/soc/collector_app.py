"""
Standalone LUMS SOC Collector WSGI application.

This application exposes only the collector ingestion endpoint.
It does not import the regular LUMS web application and does not
run database initialization or migration code.
"""

import os
import sqlite3

from flask import Flask, g

from .collector_api import collector_bp


def get_connection():
    """Open a request-local SQLite connection using the LUMS DB path."""
    db_path = os.environ.get(
        "LUMS_DB_PATH",
        "/var/lib/lums/lums.db",
    )

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.row_factory = sqlite3.Row
    return connection


def create_app(config=None):
    """Create the isolated collector application without running migrations."""
    app = Flask(
        "lums_soc_collector",
        static_folder=None,
    )

    app.config["LUMS_GET_CONNECTION"] = get_connection

    # Fail closed. Activation and a trusted identity provider must be
    # explicitly configured by the future TLS/gateway integration.
    app.config["LUMS_SOC_COLLECTOR_ENABLED"] = False

    if config is not None:
        app.config.update(config)

    app.register_blueprint(collector_bp)

    @app.teardown_appcontext
    def close_collector_database_connection(exception=None):
        connection = getattr(g, "lums_alert_connection", None)
        if connection is not None:
            connection.close()
            g.lums_alert_connection = None

    return app


app = create_app()
