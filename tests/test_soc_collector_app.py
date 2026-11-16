import sqlite3

from flask import g

from server.soc.collector_app import create_app, get_connection


def test_collector_app_registers_only_the_ingestion_route():
    app = create_app()

    rules = list(app.url_map.iter_rules())

    assert len(rules) == 1
    assert rules[0].rule == "/alerts/api/collector/v1/events"
    assert "POST" in rules[0].methods


def test_collector_app_does_not_require_lums_session_secret():
    app = create_app()

    assert app.secret_key is None


def test_collector_app_is_disabled_by_default():
    app = create_app()
    client = app.test_client()

    response = client.post(
        "/alerts/api/collector/v1/events",
        json={"events": []},
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "soc_collector_disabled"
    }


def test_collector_app_does_not_expose_alert_or_soc_ui_routes():
    app = create_app()
    client = app.test_client()

    assert client.get("/alerts/").status_code == 404
    assert client.get("/soc/").status_code == 404


def test_collector_app_rejects_get_on_ingestion_endpoint():
    app = create_app()
    client = app.test_client()

    response = client.get("/alerts/api/collector/v1/events")

    assert response.status_code == 405


def test_enabled_collector_without_identity_provider_fails_closed():
    app = create_app({
        "LUMS_SOC_COLLECTOR_ENABLED": True,
    })
    client = app.test_client()

    response = client.post(
        "/alerts/api/collector/v1/events",
        json={"events": []},
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "collector_identity_required"
    }


def test_collector_database_connection_uses_expected_pragmas(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "collector-test.db"
    monkeypatch.setenv("LUMS_DB_PATH", str(db_path))

    connection = get_connection()

    try:
        assert connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0] == 1

        assert connection.execute(
            "PRAGMA busy_timeout"
        ).fetchone()[0] == 5000

        assert isinstance(connection, sqlite3.Connection)
    finally:
        connection.close()


def test_collector_app_closes_request_local_connection_after_http_request():
    class FakeConnection:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    connection = FakeConnection()
    app = create_app({
        "TESTING": True,
        "LUMS_GET_CONNECTION": lambda: connection,
    })

    def open_connection():
        g.lums_alert_connection = app.config["LUMS_GET_CONNECTION"]()
        return "ok"

    app.add_url_rule(
        "/test-connection-lifecycle",
        view_func=open_connection,
        methods=["GET"],
    )

    response = app.test_client().get("/test-connection-lifecycle")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "ok"
    assert connection.closed is True
