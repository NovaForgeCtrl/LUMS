import json
import os
import socket
import stat
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import server.soc.chrony_time_provider as provider_module
from server.soc.chrony_time_provider import (
    EXPECTED_CHRONY_CONFIG_SHA256,
    STATUS_REQUEST,
    ChronyStatusDocument,
    ChronyStatusTransportError,
    ChronyTrustedTimeProvider,
    UnixSocketChronyStatusReader,
    parse_status_document,
)
from server.soc.chrony_sync_tracker import ClockObservation
from server.soc.trusted_time import (
    TrustedTimeError,
    TrustedTimePolicy,
    read_trusted_time,
)


UTC = timezone.utc

REF1 = "1795254866.549786796"
REF2 = "1795254867.549786796"

PROCESS_START_NS = 9_000_000_000
BOOT_BASE_NS = 10_000_000_000

CONFIG_DIGEST = EXPECTED_CHRONY_CONFIG_SHA256


def make_document(
    reference_time=REF1,
    *,
    reference_source="time.cloudflare.com",
    config_sha256=CONFIG_DIGEST,
):
    if reference_source == "time.cloudflare.com":
        reference_id = "CFC5577C"
        stratum = "4"
        sources = (
            "^,*,time.cloudflare.com,3,6,377,1,"
            "-0.000570636,-0.000549452,0.009808195\n"
            "^,+,nts.netnod.se,1,6,377,1,"
            "0.000300855,0.000300855,0.018632518\n"
        )
    else:
        reference_id = "A28FBE10"
        stratum = "1"
        sources = (
            "^,+,time.cloudflare.com,3,6,377,1,"
            "-0.000570636,-0.000549452,0.009808195\n"
            "^,*,nts.netnod.se,1,6,377,1,"
            "0.000300855,0.000300855,0.018632518\n"
        )

    tracking = (
        f"{reference_id},{reference_source},{stratum},"
        f"{reference_time},"
        "0.000108656,0.000021184,0.000616593,"
        "25.752,0.011,0.668,0.018273009,0.000537179,"
        "64.4,Normal"
    )

    return ChronyStatusDocument(
        schema_version=1,
        config_sha256=config_sha256,
        tracking_csv=tracking,
        sources_csv=sources,
    )


class SequenceReader:
    def __init__(self, documents):
        self.documents = list(documents)
        self.calls = 0

    def read_status(self):
        if not self.documents:
            raise OSError("no status document configured")

        index = min(self.calls, len(self.documents) - 1)
        self.calls += 1
        return self.documents[index]


class SequenceClock:
    def __init__(self, observations):
        self.observations = list(observations)
        self.calls = 0

    def __call__(self):
        if not self.observations:
            raise OSError("no clock observation configured")

        index = min(self.calls, len(self.observations) - 1)
        self.calls += 1
        return self.observations[index]


def make_observation(seconds):
    return ClockObservation(
        utc=datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
        + timedelta(seconds=seconds),
        boottime_ns=BOOT_BASE_NS + seconds * 1_000_000_000,
    )


@pytest.fixture
def provider_factory(monkeypatch):
    monkeypatch.setattr(
        provider_module,
        "boottime_ns",
        lambda: PROCESS_START_NS,
    )

    def factory(documents, observations):
        return ChronyTrustedTimeProvider(
            SequenceReader(documents),
            clock_observer=SequenceClock(observations),
        )

    return factory


def test_provider_waits_for_reference_advance_after_process_start(
    provider_factory,
):
    provider = provider_factory(
        [make_document()],
        [make_observation(0)],
    )

    with pytest.raises(
        TrustedTimeError,
        match="no post-process-start",
    ):
        provider.get_snapshot()

    assert provider.process_started_boottime_ns == PROCESS_START_NS



def test_provider_returns_snapshot_after_fresh_reference_advance(
    provider_factory,
):
    provider = provider_factory(
        [
            make_document(REF1),
            make_document(REF2),
        ],
        [
            make_observation(0),  # before first query
            make_observation(1),  # after first query
            make_observation(2),  # before second query
            make_observation(3),  # after second query
        ],
    )

    with pytest.raises(TrustedTimeError, match="no post-process-start"):
        provider.get_snapshot()

    snapshot = provider.get_snapshot()

    assert snapshot.synchronized is True
    assert snapshot.authenticated is True
    assert snapshot.source_id == (
        "time.cloudflare.com+nts.netnod.se"
    )
    assert snapshot.last_sync_utc == make_observation(0).utc
    assert snapshot.last_sync_boottime_ns == BOOT_BASE_NS
    assert snapshot.observed_utc == make_observation(3).utc
    assert snapshot.observed_boottime_ns == (
        BOOT_BASE_NS + 3_000_000_000
    )


def test_provider_snapshot_passes_existing_trusted_time_contract(
    provider_factory,
):
    provider = provider_factory(
        [
            make_document(REF1),
            make_document(REF2),
        ],
        [
            make_observation(0),
            make_observation(1),
            make_observation(2),
            make_observation(3),
        ],
    )

    policy = TrustedTimePolicy(
        approved_sources=frozenset({
            "time.cloudflare.com+nts.netnod.se",
        }),
        max_sync_age=timedelta(minutes=10),
        max_offset=timedelta(milliseconds=100),
        max_uncertainty=timedelta(milliseconds=50),
        clock_consistency_tolerance=timedelta(milliseconds=100),
    )

    with pytest.raises(TrustedTimeError):
        provider.get_snapshot()

    result = read_trusted_time(
        provider,
        policy,
        process_started_boottime_ns=(
            provider.process_started_boottime_ns
        ),
    )

    assert result.source_id == (
        "time.cloudflare.com+nts.netnod.se"
    )
    assert result.sync_age == timedelta(seconds=3)

def test_provider_rejects_configuration_digest_mismatch(
    provider_factory,
):
    provider = provider_factory(
        [
            make_document(config_sha256="0" * 64),
        ],
        [make_observation(0)],
    )

    with pytest.raises(
        TrustedTimeError,
        match="digest is not approved",
    ):
        provider.get_snapshot()

    assert provider._tracker.anchor is None


def test_provider_rejects_inherited_instance_after_fork(
    provider_factory,
):
    provider = provider_factory(
        [make_document()],
        [make_observation(0)],
    )

    provider._pid += 1

    with pytest.raises(
        TrustedTimeError,
        match="inherited across a process fork",
    ):
        provider.get_snapshot()



def test_provider_invalidates_anchor_after_reader_failure(monkeypatch):
    monkeypatch.setattr(
        provider_module,
        "boottime_ns",
        lambda: PROCESS_START_NS,
    )

    class FailsOnceReader:
        def __init__(self):
            self.calls = 0

        def read_status(self):
            self.calls += 1

            if self.calls == 2:
                raise OSError("host monitor unavailable")

            if self.calls in (1, 3):
                return make_document(REF1)

            return make_document(REF2)

    reader = FailsOnceReader()
    clock = SequenceClock([
        make_observation(0),  # first query: before
        make_observation(1),  # first query: after
        make_observation(2),  # failed query: before
        make_observation(3),  # third query: before
        make_observation(4),  # third query: after
        make_observation(5),  # fourth query: before
        make_observation(6),  # fourth query: after
    ])

    provider = ChronyTrustedTimeProvider(
        reader,
        clock_observer=clock,
    )

    with pytest.raises(TrustedTimeError, match="no post-process-start"):
        provider.get_snapshot()

    with pytest.raises(TrustedTimeError, match="provider failed"):
        provider.get_snapshot()

    assert provider._tracker.anchor is None

    with pytest.raises(TrustedTimeError, match="no post-process-start"):
        provider.get_snapshot()

    assert provider._tracker.anchor is None

    snapshot = provider.get_snapshot()
    assert snapshot.authenticated is True
    assert snapshot.last_sync_boottime_ns == (
        make_observation(3).boottime_ns
    )
    assert snapshot.observed_boottime_ns == (
        make_observation(6).boottime_ns
    )

def test_provider_invalidates_anchor_after_transport_failure(monkeypatch):
    class FailingReader:
        def read_status(self):
            raise OSError("host monitor unavailable")

    monkeypatch.setattr(
        provider_module,
        "boottime_ns",
        lambda: PROCESS_START_NS,
    )

    provider = ChronyTrustedTimeProvider(
        FailingReader(),
        clock_observer=lambda: make_observation(0),
    )

    with pytest.raises(
        TrustedTimeError,
        match="provider failed",
    ):
        provider.get_snapshot()

    assert provider._tracker.anchor is None


def test_status_document_accepts_exact_protocol_fields():
    payload = json.dumps({
        "schema_version": 1,
        "config_sha256": CONFIG_DIGEST,
        "tracking_csv": "tracking-data",
        "sources_csv": "sources-data",
    }).encode()

    result = parse_status_document(payload)

    assert result.schema_version == 1
    assert result.config_sha256 == CONFIG_DIGEST
    assert result.tracking_csv == "tracking-data"


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"not-json",
        b'{"schema_version": 2}',
        b'{"schema_version": true}',
        b'{"schema_version": 1, "schema_version": 1}',
        b'{"schema_version": 1, "config_sha256": "bad", '
        b'"tracking_csv": "x", "sources_csv": "y"}',
        json.dumps({
            "schema_version": 1,
            "config_sha256": CONFIG_DIGEST,
            "tracking_csv": "x",
            "sources_csv": "y",
            "extra": "forbidden",
        }).encode(),
    ],
)
def test_status_document_rejects_invalid_protocol(payload):
    with pytest.raises(ChronyStatusTransportError):
        parse_status_document(payload)


def test_status_document_rejects_oversized_csv():
    payload = json.dumps({
        "schema_version": 1,
        "config_sha256": CONFIG_DIGEST,
        "tracking_csv": "x" * 9000,
        "sources_csv": "y",
    }).encode()

    with pytest.raises(ChronyStatusTransportError):
        parse_status_document(payload)


def _create_test_socket_directory(temp_dir):
    directory = Path(temp_dir) / "status"
    directory.mkdir(mode=0o750)
    os.chmod(directory, 0o750)
    return directory


def _make_socket_reader(path):
    return UnixSocketChronyStatusReader(
        str(path),
        expected_server_uid=os.geteuid(),
        expected_server_gid=os.getegid(),
    )


def test_unix_socket_reader_accepts_peer_pid_zero_from_other_pid_namespace(monkeypatch):
    from server.soc import chrony_time_provider as provider_module

    # Simulate a host process whose PID is not visible from the container's
    # PID namespace. UID/GID are still the exact expected server identity.
    monkeypatch.setattr(
        provider_module,
        "_read_socket_peer_credentials",
        lambda connection: (0, os.geteuid(), os.getegid()),
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        directory = _create_test_socket_directory(temp_dir)
        path = directory / "chrony-status.sock"

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(path))
        os.chmod(path, 0o660)
        server.listen(1)

        response = json.dumps({
            "schema_version": 1,
            "config_sha256": CONFIG_DIGEST,
            "tracking_csv": "tracking-data",
            "sources_csv": "sources-data",
        }).encode()

        errors = []

        def serve_one():
            try:
                connection, _ = server.accept()
                with connection:
                    request = bytearray()

                    while True:
                        chunk = connection.recv(1024)
                        if not chunk:
                            break
                        request.extend(chunk)

                    if bytes(request) != STATUS_REQUEST:
                        raise AssertionError("unexpected client request")

                    connection.sendall(response)
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=serve_one)
        thread.start()

        try:
            document = _make_socket_reader(path).read_status()
        finally:
            thread.join(timeout=3)
            server.close()

        assert not thread.is_alive()
        assert not errors
        assert document.config_sha256 == CONFIG_DIGEST
        assert document.tracking_csv == "tracking-data"


def test_unix_socket_reader_rejects_world_access():
    with tempfile.TemporaryDirectory() as temp_dir:
        directory = _create_test_socket_directory(temp_dir)
        path = directory / "chrony-status.sock"

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(path))
        os.chmod(path, 0o666)

        try:
            reader = _make_socket_reader(path)

            with pytest.raises(
                ChronyStatusTransportError,
                match="unsafe ownership or mode",
            ):
                reader.read_status()
        finally:
            server.close()


def test_unix_socket_reader_rejects_unsafe_directory_mode():
    with tempfile.TemporaryDirectory() as temp_dir:
        directory = _create_test_socket_directory(temp_dir)
        path = directory / "chrony-status.sock"

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(path))
        os.chmod(path, 0o660)
        os.chmod(directory, 0o770)

        try:
            reader = _make_socket_reader(path)

            with pytest.raises(
                ChronyStatusTransportError,
                match="directory has unsafe ownership or mode",
            ):
                reader.read_status()
        finally:
            server.close()
