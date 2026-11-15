"""Unit tests for the standalone PostgreSQL SOC worker CLI."""

import json
import signal
import threading

import pytest

from server.soc import postgres_worker_cli as module
from server.soc.worker import WorkerResult


@pytest.fixture(autouse=True)
def _worker_database_secret(monkeypatch, tmp_path):
    secret_file = tmp_path / "worker_database_url"
    secret_file.write_text(
        "postgresql://worker@localhost/lums_test",
        encoding="utf-8",
    )
    monkeypatch.setenv("LUMS_SOC_DATABASE_URL_FILE", str(secret_file))




class FakeConnection:
    def __init__(self):
        self.closed = False
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        self.closed = True


class FakeWorker:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.calls = 0

    def run_once(self):
        self.calls += 1
        return WorkerResult(1, 1, 0, 1, 0)


def test_main_defaults_to_one_batch_and_closes_connection(monkeypatch, capsys):
    connection = FakeConnection()
    workers = []
    loaded_paths = []

    monkeypatch.setattr(
        module,
        "load_catalog",
        lambda path: loaded_paths.append(path) or object(),
    )
    monkeypatch.setattr(module, "connect", lambda **kwargs: connection)

    def create_worker(*args, **kwargs):
        worker = FakeWorker(*args, **kwargs)
        workers.append(worker)
        return worker

    monkeypatch.setattr(module, "PostgresSOCWorker", create_worker)

    def unexpected_continuous(*args):
        raise AssertionError("Default mode must not be continuous")

    monkeypatch.setattr(module, "run_continuous", unexpected_continuous)

    assert module.main([]) == 0

    assert len(workers) == 1
    assert workers[0].calls == 1
    assert workers[0].args[0] is connection
    assert workers[0].kwargs["batch_size"] == module.DEFAULT_BATCH_SIZE
    assert workers[0].kwargs["max_attempts"] == module.DEFAULT_MAX_ATTEMPTS
    assert workers[0].kwargs["stale_after_seconds"] == module.DEFAULT_STALE_SECONDS
    assert workers[0].kwargs["history_limit"] == module.DEFAULT_HISTORY_LIMIT
    assert loaded_paths == [module.DEFAULT_RULES_PATH]
    assert connection.closed is True
    assert connection.close_calls == 1

    output = json.loads(capsys.readouterr().out.strip())
    assert output["claimed"] == 1
    assert output["processed"] == 1


def test_main_passes_custom_limits_to_worker(monkeypatch):
    connection = FakeConnection()
    captured = {}

    monkeypatch.setattr(module, "load_catalog", lambda path: object())
    monkeypatch.setattr(module, "connect", lambda **kwargs: connection)

    def create_worker(*args, **kwargs):
        captured.update(kwargs)
        return FakeWorker(*args, **kwargs)

    monkeypatch.setattr(module, "PostgresSOCWorker", create_worker)

    result = module.main([
        "--once",
        "--batch-size", "7",
        "--max-attempts", "3",
        "--stale-after-seconds", "90",
        "--history-limit", "250",
    ])

    assert result == 0
    assert captured == {
        "batch_size": 7,
        "max_attempts": 3,
        "stale_after_seconds": 90,
        "history_limit": 250,
    }
    assert connection.closed is True


def test_main_continuous_registers_and_restores_signal_handlers(monkeypatch):
    connection = FakeConnection()
    registrations = []
    continuous_calls = []

    monkeypatch.setattr(module, "load_catalog", lambda path: object())
    monkeypatch.setattr(module, "connect", lambda **kwargs: connection)
    monkeypatch.setattr(module, "PostgresSOCWorker", FakeWorker)

    def fake_signal(signum, handler):
        registrations.append((signum, handler))
        return f"previous-{signum}"

    def fake_continuous(worker, stop_event, interval):
        continuous_calls.append((worker, interval))
        assert interval == 0.25

        registered = {
            signum: handler
            for signum, handler in registrations
            if callable(handler)
        }
        registered[signal.SIGTERM](signal.SIGTERM, None)
        assert stop_event.is_set()

    monkeypatch.setattr(module.signal, "signal", fake_signal)
    monkeypatch.setattr(module, "run_continuous", fake_continuous)

    result = module.main([
        "--continuous",
        "--poll-interval", "0.25",
    ])

    assert result == 0
    assert {signum for signum, _ in registrations[:2]} == {
        signal.SIGINT,
        signal.SIGTERM,
    }
    assert len(registrations) == 4
    assert continuous_calls[0][1] == 0.25
    assert connection.closed is True

    assert {
        signum: handler for signum, handler in registrations[2:]
    } == {
        signal.SIGINT: "previous-2",
        signal.SIGTERM: "previous-15",
    }


@pytest.mark.parametrize(
    "arguments",
    [
        ["--batch-size", "0"],
        ["--batch-size", "501"],
        ["--max-attempts", "0"],
        ["--max-attempts", "101"],
        ["--stale-after-seconds", "0"],
        ["--stale-after-seconds", "86401"],
        ["--history-limit", "0"],
        ["--history-limit", "50001"],
        ["--poll-interval", "0"],
        ["--poll-interval", "3601"],
        ["--once", "--continuous"],
    ],
)
def test_main_rejects_invalid_arguments(arguments):
    with pytest.raises(SystemExit) as exc:
        module.main(arguments)

    assert exc.value.code == 2


def test_main_closes_connection_when_worker_initialization_fails(
    monkeypatch,
    capsys,
):
    connection = FakeConnection()

    monkeypatch.setattr(module, "load_catalog", lambda path: object())
    monkeypatch.setattr(module, "connect", lambda **kwargs: connection)

    def fail_worker(*args, **kwargs):
        raise RuntimeError("simulated schema preflight failure")

    monkeypatch.setattr(module, "PostgresSOCWorker", fail_worker)

    assert module.main([]) == 1
    assert connection.closed is True
    assert "simulated schema preflight failure" in capsys.readouterr().err


def test_run_continuous_stops_after_stop_event(monkeypatch, capsys):
    stop_event = threading.Event()

    class StoppingWorker:
        def run_once(self):
            stop_event.set()
            return WorkerResult(1, 1, 0, 0, 0)

    module.run_continuous(
        StoppingWorker(),
        stop_event,
        0.1,
    )

    output = json.loads(capsys.readouterr().out.strip())
    assert output["processed"] == 1


@pytest.mark.parametrize("interval", [0, 0.09, 3600.1, True, "1"])
def test_run_continuous_rejects_invalid_poll_interval(interval):
    with pytest.raises(ValueError, match="poll_interval"):
        module.run_continuous(
            FakeWorker(),
            threading.Event(),
            interval,
        )


def test_worker_database_url_requires_dedicated_secret(monkeypatch):
    monkeypatch.delenv("LUMS_SOC_DATABASE_URL_FILE")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://app@localhost/lums_app",
    )

    with pytest.raises(RuntimeError, match="LUMS_SOC_DATABASE_URL_FILE"):
        module._get_worker_database_url()


def test_worker_database_url_reads_dedicated_secret(monkeypatch, tmp_path):
    secret_file = tmp_path / "worker_database_url"
    secret_file.write_text(
        "postgresql://worker@localhost/lums_worker",
        encoding="utf-8",
    )
    monkeypatch.setenv("LUMS_SOC_DATABASE_URL_FILE", str(secret_file))

    assert module._get_worker_database_url() == (
        "postgresql://worker@localhost/lums_worker"
    )


def test_main_does_not_fall_back_to_application_database(
    monkeypatch,
    capsys,
):
    monkeypatch.delenv("LUMS_SOC_DATABASE_URL_FILE")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://app@localhost/lums_app",
    )
    connect_calls = []
    monkeypatch.setattr(
        module,
        "connect",
        lambda **kwargs: connect_calls.append(kwargs),
    )

    assert module.main([]) == 1
    assert connect_calls == []
    assert "LUMS_SOC_DATABASE_URL_FILE" in capsys.readouterr().err


def test_worker_database_url_rejects_missing_secret_file(
    monkeypatch,
    tmp_path,
):
    secret_file = tmp_path / "missing_worker_database_url"
    monkeypatch.setenv("LUMS_SOC_DATABASE_URL_FILE", str(secret_file))

    with pytest.raises(
        RuntimeError,
        match="could not be read",
    ):
        module._get_worker_database_url()


def test_worker_database_url_rejects_empty_secret_file(
    monkeypatch,
    tmp_path,
):
    secret_file = tmp_path / "empty_worker_database_url"
    secret_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("LUMS_SOC_DATABASE_URL_FILE", str(secret_file))

    with pytest.raises(
        RuntimeError,
        match="is empty",
    ):
        module._get_worker_database_url()


def test_main_passes_dedicated_worker_secret_to_connect(
    monkeypatch,
    tmp_path,
):
    secret_file = tmp_path / "dedicated_worker_database_url"
    expected_url = "postgresql://dedicated-worker@localhost/lums_worker"
    secret_file.write_text(expected_url, encoding="utf-8")
    monkeypatch.setenv("LUMS_SOC_DATABASE_URL_FILE", str(secret_file))

    connection = FakeConnection()
    connect_calls = []

    def fake_connect(**kwargs):
        connect_calls.append(kwargs)
        return connection

    monkeypatch.setattr(module, "load_catalog", lambda path: object())
    monkeypatch.setattr(module, "connect", fake_connect)
    monkeypatch.setattr(module, "PostgresSOCWorker", FakeWorker)

    assert module.main(["--once"]) == 0

    assert len(connect_calls) == 1
    assert connect_calls[0]["database_url"] == expected_url
    assert connect_calls[0]["application_name"] == (
        "lums-postgres-soc-worker"
    )
    assert connection.closed is True
