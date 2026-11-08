"""Isolated unit tests for the PostgreSQL migration CLI."""

from types import SimpleNamespace

from server import postgres_migrate


class FakeConnection:
    def __init__(self, close_error=None):
        self.closed = False
        self.close_calls = 0
        self.close_error = close_error

    def close(self):
        self.close_calls += 1

        if self.close_error is not None:
            raise self.close_error

        self.closed = True


def test_main_runs_migrations_and_closes_connection(monkeypatch, capsys):
    connection = FakeConnection()
    calls = {}

    def fake_connect(*, application_name):
        calls["application_name"] = application_name
        return connection

    def fake_run_migrations(received_connection, migrations):
        calls["connection"] = received_connection
        calls["migrations"] = migrations

        return SimpleNamespace(
            applied=("001-core-schema", "002-security-schema"),
            already_applied=("003-rbac-schema",),
        )

    monkeypatch.setattr(postgres_migrate, "connect", fake_connect)
    monkeypatch.setattr(
        postgres_migrate,
        "run_migrations",
        fake_run_migrations,
    )

    result = postgres_migrate.main([])

    captured = capsys.readouterr()

    assert result == 0
    assert calls["application_name"] == "lums-postgres-migrate"
    assert calls["connection"] is connection
    assert calls["migrations"] is postgres_migrate.MIGRATIONS

    assert "PostgreSQL migrations completed successfully." in captured.out
    assert "001-core-schema" in captured.out
    assert "002-security-schema" in captured.out
    assert "003-rbac-schema" in captured.out

    assert captured.err == ""
    assert connection.closed is True
    assert connection.close_calls == 1


def test_main_reports_when_no_migrations_are_pending(monkeypatch, capsys):
    connection = FakeConnection()

    monkeypatch.setattr(
        postgres_migrate,
        "connect",
        lambda **kwargs: connection,
    )
    monkeypatch.setattr(
        postgres_migrate,
        "run_migrations",
        lambda connection, migrations: SimpleNamespace(
            applied=(),
            already_applied=tuple(
                migration.version
                for migration in migrations
            ),
        ),
    )

    result = postgres_migrate.main([])

    captured = capsys.readouterr()

    assert result == 0
    assert "Newly applied migrations: none" in captured.out
    assert "Previously applied migrations:" in captured.out
    assert connection.closed is True


def test_main_handles_migration_runner_error(monkeypatch, capsys):
    connection = FakeConnection()

    monkeypatch.setattr(
        postgres_migrate,
        "connect",
        lambda **kwargs: connection,
    )

    def fail_migrations(connection, migrations):
        raise postgres_migrate.MigrationRunnerError(
            "migration history is inconsistent"
        )

    monkeypatch.setattr(
        postgres_migrate,
        "run_migrations",
        fail_migrations,
    )

    result = postgres_migrate.main([])

    captured = capsys.readouterr()

    assert result == 1
    assert "migration history is inconsistent" in captured.err
    assert connection.closed is True
    assert connection.close_calls == 1


def test_main_handles_unexpected_error_and_closes_connection(
    monkeypatch,
    capsys,
):
    connection = FakeConnection()

    monkeypatch.setattr(
        postgres_migrate,
        "connect",
        lambda **kwargs: connection,
    )

    def fail_migrations(connection, migrations):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(
        postgres_migrate,
        "run_migrations",
        fail_migrations,
    )

    result = postgres_migrate.main([])

    captured = capsys.readouterr()

    assert result == 1
    assert "unexpected failure" in captured.err
    assert connection.closed is True
    assert connection.close_calls == 1


def test_main_handles_connection_error(monkeypatch, capsys):
    def fail_connect(**kwargs):
        raise RuntimeError("connection unavailable")

    monkeypatch.setattr(
        postgres_migrate,
        "connect",
        fail_connect,
    )

    result = postgres_migrate.main([])

    captured = capsys.readouterr()

    assert result == 1
    assert "connection unavailable" in captured.err


def test_main_does_not_close_already_closed_connection(
    monkeypatch,
):
    connection = FakeConnection()
    connection.closed = True

    monkeypatch.setattr(
        postgres_migrate,
        "connect",
        lambda **kwargs: connection,
    )
    monkeypatch.setattr(
        postgres_migrate,
        "run_migrations",
        lambda connection, migrations: SimpleNamespace(
            applied=(),
            already_applied=(),
        ),
    )

    result = postgres_migrate.main([])

    assert result == 0
    assert connection.close_calls == 0


def test_main_reports_close_error_after_successful_migrations(
    monkeypatch,
    capsys,
):
    connection = FakeConnection(
        close_error=RuntimeError("close failed")
    )

    monkeypatch.setattr(
        postgres_migrate,
        "connect",
        lambda **kwargs: connection,
    )
    monkeypatch.setattr(
        postgres_migrate,
        "run_migrations",
        lambda connection, migrations: SimpleNamespace(
            applied=("001-core-schema",),
            already_applied=(),
        ),
    )

    result = postgres_migrate.main([])

    captured = capsys.readouterr()

    assert result == 1
    assert "PostgreSQL migrations completed successfully." in captured.out
    assert "001-core-schema" in captured.out
    assert "Could not close PostgreSQL connection" in captured.err
    assert "close failed" in captured.err
    assert connection.close_calls == 1


def test_main_preserves_migration_error_when_close_also_fails(
    monkeypatch,
    capsys,
):
    connection = FakeConnection(
        close_error=RuntimeError("close failed")
    )

    monkeypatch.setattr(
        postgres_migrate,
        "connect",
        lambda **kwargs: connection,
    )

    def fail_migrations(connection, migrations):
        raise postgres_migrate.MigrationRunnerError(
            "original migration failure"
        )

    monkeypatch.setattr(
        postgres_migrate,
        "run_migrations",
        fail_migrations,
    )

    result = postgres_migrate.main([])

    captured = capsys.readouterr()

    assert result == 1
    assert "original migration failure" in captured.err
    assert "Could not close PostgreSQL connection" in captured.err
    assert "close failed" in captured.err
    assert connection.close_calls == 1
