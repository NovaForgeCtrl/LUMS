import json
import os
import socket
import stat
import tempfile
import threading

import pytest

import server.soc.chrony_status_service as service_module
from server.soc.chrony_config import (
    DEFAULT_CONFIG_PATH,
    ValidatedChronyConfig,
)
from server.soc.chrony_status_service import (
    STATUS_REQUEST,
    ChronyStatusService,
    ChronyStatusServiceError,
    _peer_credentials,
    _read_only_chronyc,
)
from server.soc.chrony_time_provider import parse_status_document


TRACKING = (
    "CFC5577C,time.cloudflare.com,4,"
    "1795254866.549786796,"
    "0.000108656,0.000021184,0.000616593,"
    "25.752,0.011,0.668,0.018273009,0.000537179,"
    "64.4,Normal"
)

SOURCES = (
    "^,*,time.cloudflare.com,3,6,377,107,"
    "-0.000570636,-0.000549452,0.009808195\n"
    "^,+,nts.netnod.se,1,6,377,105,"
    "0.000300855,0.000300855,0.018632518\n"
)

CONFIG_DIGEST = (
    "0b36fbc86e90f5bd353419f106286955c50c37fbeb18bdbe8df9184f046cc7d5"
)


def valid_config():
    return ValidatedChronyConfig(
        path=DEFAULT_CONFIG_PATH,
        sha256=CONFIG_DIGEST,
        source_names=(
            "time.cloudflare.com",
            "nts.netnod.se",
        ),
    )


def make_service(**overrides):
    calls = []

    def config_loader():
        return valid_config()

    def command_runner(command):
        calls.append(command)

        if command == "tracking":
            return TRACKING
        if command == "sources":
            return SOURCES

        raise AssertionError(f"Unexpected Chrony command: {command}")

    defaults = {
        "socket_path": "/tmp/lums-chrony-status-test.sock",
        "service_uid": os.geteuid(),
        "service_gid": os.getegid(),
        "allowed_client_uid": os.geteuid(),
        "allowed_client_gid": os.getegid(),
        "config_loader": config_loader,
        "command_runner": command_runner,
    }
    defaults.update(overrides)

    service = ChronyStatusService(**defaults)
    return service, calls


class FakePeerCredentialsSocket:
    def __init__(self, pid, uid, gid):
        self.credentials = service_module.SO_PEERCRED_STRUCT.pack(
            pid, uid, gid
        )

    def getsockopt(self, level, option, length):
        assert level == socket.SOL_SOCKET
        assert option == socket.SO_PEERCRED
        assert length == service_module.SO_PEERCRED_STRUCT.size
        return self.credentials


@pytest.mark.parametrize("pid", [0, 1, 1234])
def test_peer_credentials_accept_nonnegative_pid(pid):
    connection = FakePeerCredentialsSocket(
        pid=pid,
        uid=10001,
        gid=10001,
    )

    assert _peer_credentials(connection) == (pid, 10001, 10001)


@pytest.mark.parametrize(
    "credentials",
    [
        (-1, 10001, 10001),
        (0, -1, 10001),
        (0, 10001, -1),
    ],
)
def test_peer_credentials_reject_negative_values(credentials):
    connection = FakePeerCredentialsSocket(*credentials)

    with pytest.raises(
        ChronyStatusServiceError,
        match="credentials are invalid",
    ):
        _peer_credentials(connection)


def exchange_request(service, request=STATUS_REQUEST):
    client, server = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    outcome = {}

    def serve():
        try:
            with server:
                service.handle_connection(server)
        except Exception as exc:
            outcome["error"] = exc

    thread = threading.Thread(target=serve)
    thread.start()

    chunks = []

    try:
        try:
            client.sendall(request)
            client.shutdown(socket.SHUT_WR)
        except (BrokenPipeError, ConnectionResetError):
            # An early server-side rejection is an expected test outcome.
            pass

        while True:
            try:
                chunk = client.recv(4096)
            except ConnectionResetError:
                break

            if not chunk:
                break

            chunks.append(chunk)
    finally:
        client.close()
        thread.join(timeout=3)

    assert not thread.is_alive()
    return b"".join(chunks), outcome.get("error")


def test_build_response_returns_validated_live_status_document():
    service, calls = make_service()

    payload = service.build_response()
    document = parse_status_document(payload)

    assert document.schema_version == 1
    assert document.config_sha256 == CONFIG_DIGEST
    assert document.tracking_csv == TRACKING
    assert document.sources_csv == SOURCES
    assert calls == ["tracking", "sources"]


def test_build_response_rejects_wrong_configuration_digest():
    config = ValidatedChronyConfig(
        path=DEFAULT_CONFIG_PATH,
        sha256="0" * 64,
        source_names=(
            "time.cloudflare.com",
            "nts.netnod.se",
        ),
    )

    service, calls = make_service(
        config_loader=lambda: config,
    )

    with pytest.raises(
        ChronyStatusServiceError,
        match="digest is not approved",
    ):
        service.build_response()

    assert calls == []


def test_build_response_rejects_unusable_chrony_status():
    service, _ = make_service(
        command_runner=lambda command: (
            TRACKING if command == "tracking" else SOURCES.replace(
                "nts.netnod.se",
                "unknown.example",
            )
        ),
    )

    with pytest.raises(
        ChronyStatusServiceError,
        match="does not meet",
    ):
        service.build_response()


def test_server_accepts_exact_authorized_read_only_request():
    service, calls = make_service()

    payload, error = exchange_request(service)

    assert error is None
    document = parse_status_document(payload)
    assert document.config_sha256 == CONFIG_DIGEST
    assert calls == ["tracking", "sources"]


def test_server_rejects_wrong_peer_identity(monkeypatch):
    service, calls = make_service()

    monkeypatch.setattr(
        service_module,
        "_peer_credentials",
        lambda connection: (1234, 20000, 20000),
    )

    payload, error = exchange_request(service)

    assert payload == b""
    assert isinstance(error, ChronyStatusServiceError)
    assert "peer identity" in str(error)
    assert calls == []


def test_server_rejects_unknown_request():
    service, calls = make_service()

    payload, error = exchange_request(
        service,
        b"LUMS-CHRONY-CONTROL/1\n",
    )

    assert payload == b""
    assert isinstance(error, ChronyStatusServiceError)
    assert "fixed protocol" in str(error)
    assert calls == []


def test_listener_creates_exact_socket_permissions():
    with tempfile.TemporaryDirectory() as temp_dir:
        directory = os.path.join(temp_dir, "runtime")
        os.mkdir(directory, 0o750)
        os.chmod(directory, 0o750)

        path = os.path.join(directory, "status.sock")

        service, _ = make_service(socket_path=path)
        listener = service._create_listener()

        try:
            info = os.lstat(path)

            assert stat.S_ISSOCK(info.st_mode)
            assert info.st_uid == os.geteuid()
            assert info.st_gid == os.getegid()
            assert stat.S_IMODE(info.st_mode) == 0o660
        finally:
            listener.close()
            os.unlink(path)


def test_listener_refuses_to_replace_existing_socket():
    with tempfile.TemporaryDirectory() as temp_dir:
        directory = os.path.join(temp_dir, "runtime")
        os.mkdir(directory, 0o750)

        path = os.path.join(directory, "status.sock")
        existing = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        existing.bind(path)

        service, _ = make_service(socket_path=path)

        try:
            with pytest.raises(
                ChronyStatusServiceError,
                match="already exists",
            ):
                service._create_listener()
        finally:
            existing.close()


def test_chronyc_runner_refuses_non_read_only_commands():
    with pytest.raises(
        ChronyStatusServiceError,
        match="not approved",
    ):
        _read_only_chronyc("makestep")




def test_serve_forever_graceful_stop_removes_socket_but_keeps_runtime_dir(
    tmp_path,
    monkeypatch,
):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(mode=0o750)
    os.chmod(runtime_dir, 0o750)

    socket_path = runtime_dir / "status.sock"
    service, _ = make_service(socket_path=str(socket_path))

    listener_ready = threading.Event()
    original_create_listener = service._create_listener

    def create_listener():
        listener = original_create_listener()
        listener_ready.set()
        return listener

    monkeypatch.setattr(
        service,
        "_create_listener",
        create_listener,
    )

    errors = []

    def run_service():
        try:
            service.serve_forever()
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=run_service)
    thread.start()

    try:
        assert listener_ready.wait(timeout=3)
        assert socket_path.is_socket()

        service.stop()
        thread.join(timeout=3)

        assert not thread.is_alive()
        assert errors == []
        assert not socket_path.exists()
        assert runtime_dir.is_dir()
    finally:
        service.stop()
        thread.join(timeout=3)

def test_protocol_request_is_fixed():
    assert STATUS_REQUEST == b"LUMS-CHRONY-STATUS/1\n"
