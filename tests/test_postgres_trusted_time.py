"""Tests for the PostgreSQL Trusted-Time page and read-only API."""

import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from server import postgres_flask_security as pg_security
from server.postgres_app import create_postgres_app
from server.postgres_trusted_time import TRUSTED_TIME_PREVIEW_POLICY
from server.soc.trusted_time import TrustedTimeSnapshot


BASE_URL = "https://localhost"
NOW = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeProvider:
    process_started_boottime_ns = 1_000_000_000

    def get_snapshot(self):
        return TrustedTimeSnapshot(
            synchronized=True,
            authenticated=True,
            source_id="time.cloudflare.com+nts.netnod.se",
            last_sync_utc=NOW - timedelta(seconds=1),
            last_sync_boottime_ns=2_000_000_000,
            observed_utc=NOW,
            observed_boottime_ns=3_000_000_000,
            offset=timedelta(milliseconds=2),
            uncertainty=timedelta(milliseconds=5),
        )


def _make_app(monkeypatch, *, permissions, provider):
    connection = FakeConnection()

    monkeypatch.setattr(
        pg_security,
        "load_authorization_state",
        lambda conn, user_id: SimpleNamespace(
            user={
                "id": 7,
                "username": "preview-user",
                "enabled": True,
                "role": "administrator",
            },
            permissions=frozenset(permissions),
        ),
    )

    app = create_postgres_app({
        "SECRET_KEY": "pytest-trusted-time-secret",
        "TESTING": True,
        "LUMS_POSTGRES_GET_CONNECTION": lambda: connection,
        "LUMS_TRUSTED_TIME_PROVIDER": provider,
    })

    client = app.test_client()
    with client.session_transaction(base_url=BASE_URL) as session:
        session.clear()
        session.update({
            "user_id": 7,
            "username": "preview-user",
        })

    return app, client, connection


def test_trusted_time_routes_are_registered_without_sqlite_soc_blueprint():
    app = create_postgres_app({
        "SECRET_KEY": "pytest-trusted-time-secret",
        "TESTING": True,
        "LUMS_TRUSTED_TIME_PROVIDER": None,
    })

    routes = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods
        if method not in {"HEAD", "OPTIONS"}
    }

    assert ("/trusted-time", "GET") in routes
    assert ("/api/trusted-time", "GET") in routes
    assert "soc" not in app.blueprints
    assert app.extensions["lums_trusted_time_provider"] is None


def test_trusted_time_page_requires_authentication():
    app = create_postgres_app({
        "SECRET_KEY": "pytest-trusted-time-secret",
        "TESTING": True,
        "LUMS_TRUSTED_TIME_PROVIDER": FakeProvider(),
    })

    response = app.test_client().get(
        "/trusted-time",
        base_url=BASE_URL,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_trusted_time_api_requires_authentication():
    app = create_postgres_app({
        "SECRET_KEY": "pytest-trusted-time-secret",
        "TESTING": True,
        "LUMS_TRUSTED_TIME_PROVIDER": FakeProvider(),
    })

    response = app.test_client().get(
        "/api/trusted-time",
        base_url=BASE_URL,
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "authentication_required"
    }


def test_trusted_time_page_and_api_require_soc_view(monkeypatch):
    app, client, connection = _make_app(
        monkeypatch,
        permissions={"clients.view"},
        provider=FakeProvider(),
    )

    page = client.get("/trusted-time", base_url=BASE_URL)
    api = client.get("/api/trusted-time", base_url=BASE_URL)

    assert page.status_code == 403
    assert api.status_code == 403
    assert connection.closed is True


def test_trusted_time_page_renders_preview_and_authentication_explanation(
    monkeypatch,
):
    app, client, connection = _make_app(
        monkeypatch,
        permissions={"soc.view"},
        provider=FakeProvider(),
    )

    response = client.get("/trusted-time", base_url=BASE_URL)

    assert response.status_code == 200
    assert b"Trusted Time" in response.data
    assert b"Preview policy" in response.data
    assert b"authdata" in response.data
    assert b"/api/trusted-time" in response.data
    assert b'data-nav-id="trusted-time"' in response.data
    assert connection.closed is True


def test_trusted_time_api_returns_validated_preview_snapshot(monkeypatch):
    app, client, connection = _make_app(
        monkeypatch,
        permissions={"soc.view"},
        provider=FakeProvider(),
    )

    response = client.get("/api/trusted-time", base_url=BASE_URL)

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["status"] == "synchronized"
    assert payload["authenticated"] is True
    assert payload["source_id"] == (
        "time.cloudflare.com+nts.netnod.se"
    )
    assert payload["sync_age_upper_bound_ms"] == 1000.0
    assert payload["offset_ms"] == 2.0
    assert payload["uncertainty_ms"] == 5.0
    assert payload["policy"]["name"] == (
        "Preview policy – not production approved"
    )
    assert "authdata" in payload["authentication_basis"]
    assert connection.closed is True


def test_trusted_time_api_fails_closed_without_host_provider(monkeypatch):
    app, client, connection = _make_app(
        monkeypatch,
        permissions={"soc.view"},
        provider=None,
    )

    response = client.get("/api/trusted-time", base_url=BASE_URL)

    assert response.status_code == 503
    assert response.get_json() == {
        "status": "unavailable",
        "error": "trusted_time_not_configured",
    }
    assert connection.closed is True



def test_provider_is_created_lazily_and_recreated_after_worker_pid_change(
    monkeypatch,
):
    from server import postgres_trusted_time

    created = []

    def build_provider(config):
        provider = object()
        created.append(provider)
        return provider

    monkeypatch.setattr(
        postgres_trusted_time,
        "_build_provider",
        build_provider,
    )

    app = create_postgres_app({
        "SECRET_KEY": "pytest-trusted-time-secret",
        "TESTING": True,
    })

    # App construction can happen in the Gunicorn master. It must not
    # construct the PID-bound provider before workers are forked.
    assert created == []
    assert app.extensions["lums_trusted_time_provider"] is None
    assert app.extensions["lums_trusted_time_provider_pid"] is None

    with app.app_context():
        monkeypatch.setattr(
            postgres_trusted_time.os,
            "getpid",
            lambda: 41001,
        )
        first = postgres_trusted_time._get_process_provider()

        assert first is created[0]
        assert app.extensions["lums_trusted_time_provider_pid"] == 41001

        monkeypatch.setattr(
            postgres_trusted_time.os,
            "getpid",
            lambda: 41002,
        )
        second = postgres_trusted_time._get_process_provider()

        assert second is created[1]
        assert second is not first
        assert app.extensions["lums_trusted_time_provider_pid"] == 41002

    assert len(created) == 2



@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires os.fork")
def test_provider_is_initialized_independently_in_each_forked_process():
    from server import postgres_trusted_time

    app = create_postgres_app({
        "SECRET_KEY": "pytest-trusted-time-fork-secret",
        "TESTING": True,
    })
    app.extensions["lums_trusted_time_provider_factory"] = (
        lambda: {"created_by_pid": os.getpid()}
    )

    children = []
    for _ in range(2):
        rfd, wfd = os.pipe()
        pid = os.fork()

        if pid == 0:
            os.close(rfd)
            try:
                with app.app_context():
                    provider = postgres_trusted_time._get_process_provider()
                    result = {
                        "child_pid": os.getpid(),
                        "provider_pid": provider["created_by_pid"],
                        "extension_pid": app.extensions[
                            "lums_trusted_time_provider_pid"
                        ],
                    }
                os.write(wfd, json.dumps(result).encode() + b"\n")
                os._exit(0)
            except BaseException as exc:
                os.write(wfd, json.dumps({"error": repr(exc)}).encode() + b"\n")
                os._exit(1)

        os.close(wfd)
        children.append((pid, rfd))

    results = []
    for pid, rfd in children:
        with os.fdopen(rfd, "rb") as stream:
            result = json.loads(stream.readline())
        _, status = os.waitpid(pid, 0)
        result["exit_status"] = os.waitstatus_to_exitcode(status)
        results.append(result)

    assert len(results) == 2
    assert all(r["exit_status"] == 0 for r in results)
    assert all(
        r["child_pid"] == r["provider_pid"] == r["extension_pid"]
        for r in results
    )
    assert results[0]["child_pid"] != results[1]["child_pid"]
    assert app.extensions["lums_trusted_time_provider"] is None
    assert app.extensions["lums_trusted_time_provider_pid"] is None


def test_preview_policy_is_explicit_and_not_a_production_policy():
    policy = TRUSTED_TIME_PREVIEW_POLICY

    assert policy.approved_sources == frozenset({
        "time.cloudflare.com+nts.netnod.se",
    })
    assert policy.max_sync_age == timedelta(minutes=10)
    assert policy.max_offset == timedelta(milliseconds=100)
    assert policy.max_uncertainty == timedelta(milliseconds=50)
    assert policy.clock_consistency_tolerance == timedelta(
        milliseconds=100
    )
