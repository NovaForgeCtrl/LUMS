"""Database-free tests for PostgreSQL client validation and routes."""

import pytest

from server import postgres_clients
from server.postgres_app import create_postgres_app


VALID_REPORT = {
    "hostname": "client-01",
    "ip": "192.0.2.10",
    "os": "Debian GNU/Linux",
    "kernel": "6.1.0",
    "architecture": "x86_64",
    "agent_version": "1.0.0",
}


def report(**changes):
    data = dict(VALID_REPORT)
    data.update(changes)
    return data


def test_valid_minimal_report():
    assert postgres_clients.validate_client_report(VALID_REPORT) is True


def test_valid_complete_report():
    data = report(
        idle=False,
        idle_seconds=0,
        idle_threshold_seconds=300,
        idle_source="x11",
        idle_supported=True,
        updates=[{
            "package": "curl",
            "installed_version": "1.0",
            "available_version": "1.1",
        }],
        packages={"curl": "1.0"},
    )
    assert postgres_clients.validate_client_report(data) is True


@pytest.mark.parametrize("data", [None, {}, [], "invalid", 42])
def test_invalid_root_payload(data):
    assert postgres_clients.validate_client_report(data) is False


@pytest.mark.parametrize(
    "field",
    ["hostname", "ip", "os", "kernel", "architecture", "agent_version"],
)
def test_missing_required_field(field):
    data = report()
    del data[field]
    assert postgres_clients.validate_client_report(data) is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hostname", ""),
        ("ip", "  "),
        ("os", None),
        ("kernel", 123),
        ("idle", 1),
        ("idle_seconds", True),
        ("idle_seconds", -1),
        ("idle_threshold_seconds", 0),
        ("idle_source", 123),
        ("idle_supported", 1),
    ],
)
def test_invalid_fields(field, value):
    assert postgres_clients.validate_client_report(
        report(**{field: value})
    ) is False


@pytest.mark.parametrize(
    "updates",
    [
        {},
        "curl",
        [None],
        [{"package": "-curl", "available_version": "1.1"}],
        [{"package": "curl", "available_version": " "}],
        [{
            "package": "curl",
            "available_version": "1.1",
            "installed_version": 123,
        }],
    ],
)
def test_invalid_updates(updates):
    assert postgres_clients.validate_client_report(
        report(updates=updates)
    ) is False


@pytest.mark.parametrize(
    "packages",
    [[], "curl", {"-curl": "1.0"}, {"curl": ""}, {"curl": 123}],
)
def test_invalid_installed_packages(packages):
    assert postgres_clients.validate_client_report(
        report(packages=packages)
    ) is False


def test_client_routes_are_registered():
    app = create_postgres_app({
        "SECRET_KEY": "postgres-clients-route-test",
        "TESTING": True,
    })

    actual = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods
        if method not in {"HEAD", "OPTIONS"}
    }

    expected = {
        ("/api/clients", "GET"),
        ("/api/clients", "POST"),
        ("/api/clients/<int:client_id>", "GET"),
        ("/api/clients/<int:client_id>", "DELETE"),
        ("/api/clients/<int:client_id>/token/rotate", "POST"),
        ("/api/clients/<int:client_id>/updates", "GET"),
        ("/api/clients/<int:client_id>/packages", "GET"),
        ("/api/client/me", "GET"),
        ("/api/report", "POST"),
    }

    assert expected <= actual
