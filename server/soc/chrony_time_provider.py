"""Process-local fail-closed provider for authenticated Chrony time.

The host-side status service returns only read-only Chrony CSV data and
the digest of its validated configuration.

Each application worker owns an independent tracker. A worker must observe
a Chrony reference-time advance after its own process start before this
provider produces a TrustedTimeSnapshot.
"""

from __future__ import annotations

import json
import os
import re
import socket
import stat
import struct
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from server.soc.chrony_status import parse_chrony_status
from server.soc.chrony_sync_tracker import (
    ChronySyncTracker,
    ClockObservation,
    capture_clock_observation,
)
from server.soc.trusted_time import (
    TrustedTimeError,
    TrustedTimeSnapshot,
    boottime_ns,
)


EXPECTED_CHRONY_CONFIG_SHA256 = (
    "0b36fbc86e90f5bd353419f106286955c50c37fbeb18bdbe8df9184f046cc7d5"
)

STATUS_PROTOCOL_VERSION = 1
STATUS_REQUEST = b"LUMS-CHRONY-STATUS/1\n"
MAX_STATUS_RESPONSE = 32 * 1024
MAX_CSV_FIELD_SIZE = 8 * 1024


class ChronyStatusTransportError(RuntimeError):
    """Raised when the host status service cannot be queried safely."""


@dataclass(frozen=True)
class ChronyStatusDocument:
    schema_version: int
    config_sha256: str
    tracking_csv: str
    sources_csv: str


class ChronyStatusReader(Protocol):
    def read_status(self) -> ChronyStatusDocument:
        """Read one fresh, validated host-side Chrony status document."""
        ...


def _unique_json_object(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ChronyStatusTransportError(
                "status response contains duplicate JSON keys"
            )
        result[key] = value

    return result


def parse_status_document(payload: bytes) -> ChronyStatusDocument:
    """Parse the strict host-monitor response format."""
    if not isinstance(payload, bytes):
        raise ChronyStatusTransportError(
            "status response must be bytes"
        )

    if not payload or len(payload) > MAX_STATUS_RESPONSE:
        raise ChronyStatusTransportError(
            "status response is empty or too large"
        )

    try:
        text = payload.decode("utf-8", errors="strict")

        data = json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=lambda value: (
                (_ for _ in ()).throw(
                    ChronyStatusTransportError(
                        f"invalid JSON numeric constant: {value}"
                    )
                )
            ),
        )
    except ChronyStatusTransportError:
        raise
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ChronyStatusTransportError(
            "status response is not valid JSON"
        ) from exc

    expected_keys = {
        "schema_version",
        "config_sha256",
        "tracking_csv",
        "sources_csv",
    }

    if not isinstance(data, dict) or set(data) != expected_keys:
        raise ChronyStatusTransportError(
            "status response fields do not match the protocol"
        )

    version = data["schema_version"]
    digest = data["config_sha256"]
    tracking = data["tracking_csv"]
    sources = data["sources_csv"]

    if type(version) is not int or version != STATUS_PROTOCOL_VERSION:
        raise ChronyStatusTransportError(
            "unsupported status protocol version"
        )

    if (
        not isinstance(digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
    ):
        raise ChronyStatusTransportError(
            "status configuration digest is invalid"
        )

    for field, value in (
        ("tracking_csv", tracking),
        ("sources_csv", sources),
    ):
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value.encode("utf-8")) > MAX_CSV_FIELD_SIZE
            or "\x00" in value
        ):
            raise ChronyStatusTransportError(
                f"{field} is empty, oversized, or invalid"
            )

    return ChronyStatusDocument(
        schema_version=version,
        config_sha256=digest,
        tracking_csv=tracking,
        sources_csv=sources,
    )


def _read_socket_peer_credentials(
    connection: socket.socket,
) -> tuple[int, int, int]:
    """Read SO_PEERCRED as seen in the receiving process PID namespace.

    Linux may report PID 0 when the peer is outside this process's PID
    namespace. UID and GID remain the authentication criteria.
    """
    raw = connection.getsockopt(
        socket.SOL_SOCKET,
        socket.SO_PEERCRED,
        struct.calcsize("3i"),
    )

    if len(raw) != struct.calcsize("3i"):
        raise ChronyStatusTransportError(
            "Chrony status server returned invalid peer credentials"
        )

    return struct.unpack("3i", raw)


class UnixSocketChronyStatusReader:
    """Read-only client for the dedicated host-side Unix socket service.

    Socket ownership, directory ownership, exact permissions and Linux
    SO_PEERCRED identity are all checked. A path or permission check alone
    is not accepted as authentication of the server process.
    """

    def __init__(
        self,
        socket_path: str | os.PathLike[str],
        *,
        expected_server_uid: int,
        expected_server_gid: int,
        timeout: float = 3.0,
    ) -> None:
        raw_path = os.fspath(socket_path)

        if (
            not isinstance(raw_path, str)
            or not raw_path.startswith("/")
            or ".." in Path(raw_path).parts
        ):
            raise ValueError("Chrony status socket path must be absolute")

        if len(os.fsencode(raw_path)) >= 104:
            raise ValueError("Chrony status socket path is too long")

        if (
            type(expected_server_uid) is not int
            or expected_server_uid < 0
            or type(expected_server_gid) is not int
            or expected_server_gid < 0
        ):
            raise ValueError("expected server UID/GID are invalid")

        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
            or timeout > 30
        ):
            raise ValueError("socket timeout must be between 0 and 30 seconds")

        self._socket_path = Path(raw_path)
        self._expected_server_uid = expected_server_uid
        self._expected_server_gid = expected_server_gid
        self._timeout = float(timeout)

    def _check_socket_path(self) -> None:
        try:
            directory = self._socket_path.parent.lstat()
            info = self._socket_path.lstat()
        except OSError as exc:
            raise ChronyStatusTransportError(
                "Chrony status socket cannot be inspected"
            ) from exc

        if not stat.S_ISDIR(directory.st_mode):
            raise ChronyStatusTransportError(
                "Chrony status socket directory is not a real directory"
            )

        if (
            directory.st_uid != self._expected_server_uid
            or directory.st_gid != self._expected_server_gid
            or stat.S_IMODE(directory.st_mode) != 0o750
        ):
            raise ChronyStatusTransportError(
                "Chrony status socket directory has unsafe ownership or mode"
            )

        if not stat.S_ISSOCK(info.st_mode):
            raise ChronyStatusTransportError(
                "Chrony status endpoint is not a Unix socket"
            )

        if (
            info.st_uid != self._expected_server_uid
            or info.st_gid != self._expected_server_gid
            or stat.S_IMODE(info.st_mode) != 0o660
            or info.st_nlink != 1
        ):
            raise ChronyStatusTransportError(
                "Chrony status socket has unsafe ownership or mode"
            )

    def read_status(self) -> ChronyStatusDocument:
        self._check_socket_path()

        if not hasattr(socket, "SO_PEERCRED"):
            raise ChronyStatusTransportError(
                "Linux SO_PEERCRED is unavailable"
            )

        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(self._timeout)

        try:
            connection.connect(os.fspath(self._socket_path))

            peer_pid, peer_uid, peer_gid = (
                _read_socket_peer_credentials(connection)
            )

            if (
                peer_pid < 0
                or peer_uid != self._expected_server_uid
                or peer_gid != self._expected_server_gid
            ):
                raise ChronyStatusTransportError(
                    "Chrony status server peer identity is not approved"
                )

            connection.sendall(STATUS_REQUEST)
            connection.shutdown(socket.SHUT_WR)

            chunks: list[bytes] = []
            total = 0

            while True:
                chunk = connection.recv(
                    min(4096, MAX_STATUS_RESPONSE + 1 - total)
                )

                if not chunk:
                    break

                chunks.append(chunk)
                total += len(chunk)

                if total > MAX_STATUS_RESPONSE:
                    raise ChronyStatusTransportError(
                        "Chrony status response exceeds the size limit"
                    )

        except ChronyStatusTransportError:
            raise
        except OSError as exc:
            raise ChronyStatusTransportError(
                "Chrony status socket communication failed"
            ) from exc
        finally:
            connection.close()

        return parse_status_document(b"".join(chunks))


class ChronyTrustedTimeProvider:
    """Thread-safe, process-local implementation of TrustedTimeProvider.

    authenticated=True is asserted only after:
      * the exact approved configuration digest is received;
      * the protected host service supplied the status document;
      * both approved NTS sources pass the strict parser;
      * both sources are selected (* and +);
      * their reachability and quality checks pass.

    The provider does not independently execute chronyc authdata. The
    authentication guarantee is based on the pinned protected configuration,
    authselectmode=require, and Chrony's selected-source status.
    """

    def __init__(
        self,
        status_reader: ChronyStatusReader,
        *,
        expected_config_sha256: str = EXPECTED_CHRONY_CONFIG_SHA256,
        clock_observer=capture_clock_observation,
    ) -> None:
        if not callable(getattr(status_reader, "read_status", None)):
            raise TypeError("status_reader must implement read_status()")

        if (
            not isinstance(expected_config_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_config_sha256) is None
        ):
            raise ValueError("expected Chrony configuration digest is invalid")

        if not callable(clock_observer):
            raise TypeError("clock_observer must be callable")

        try:
            started = boottime_ns()
        except TrustedTimeError:
            raise
        except Exception as exc:
            raise TrustedTimeError(
                "provider process start BOOTTIME is unavailable"
            ) from exc

        self._pid = os.getpid()
        self._process_started_boottime_ns = started
        self._reader = status_reader
        self._expected_digest = expected_config_sha256
        self._clock_observer = clock_observer

        self._tracker = ChronySyncTracker()
        self._lock = threading.Lock()

    @property
    def process_started_boottime_ns(self) -> int:
        return self._process_started_boottime_ns

    def _require_original_process(self) -> None:
        if os.getpid() != self._pid:
            self._tracker.invalidate()
            raise TrustedTimeError(
                "trusted-time provider was inherited across a process fork"
            )

    def _capture_observation(self) -> ClockObservation:
        """Capture and validate a paired UTC/BOOTTIME observation."""
        observation = self._clock_observer()

        if not isinstance(observation, ClockObservation):
            raise ValueError("clock observer returned an invalid object")

        if (
            not isinstance(observation.utc, datetime)
            or observation.utc.tzinfo is None
            or observation.utc.utcoffset() is None
        ):
            raise ValueError("clock observer returned invalid UTC")

        if (
            type(observation.boottime_ns) is not int
            or observation.boottime_ns < 0
        ):
            raise ValueError("clock observer returned invalid BOOTTIME")

        return ClockObservation(
            utc=observation.utc.astimezone(timezone.utc),
            boottime_ns=observation.boottime_ns,
        )

    def get_snapshot(self) -> TrustedTimeSnapshot:
        """Return one verified snapshot or fail closed."""
        with self._lock:
            self._require_original_process()

            try:
                # The first paired observation precedes the fresh Chrony
                # query. It is used only as the conservative event boundary.
                before_query = self._capture_observation()

                document = self._reader.read_status()

                if not isinstance(document, ChronyStatusDocument):
                    raise ValueError(
                        "host monitor returned an invalid status document"
                    )

                if document.config_sha256 != self._expected_digest:
                    raise TrustedTimeError(
                        "host Chrony configuration digest is not approved"
                    )

                status = parse_chrony_status(
                    document.tracking_csv,
                    document.sources_csv,
                )

                # The returned snapshot uses a second paired observation
                # taken after the host status response has been received
                # and parsed. Query latency is therefore included in age.
                after_query = self._capture_observation()

                if after_query.boottime_ns < before_query.boottime_ns:
                    raise ValueError(
                        "BOOTTIME moved backwards during status query"
                    )

                anchor = self._tracker.observe(
                    status,
                    before_query,
                )

            except Exception as exc:
                self._tracker.invalidate()

                if isinstance(exc, TrustedTimeError):
                    raise

                raise TrustedTimeError(
                    "Chrony trusted-time provider failed"
                ) from exc

            if anchor is None:
                raise TrustedTimeError(
                    "no post-process-start Chrony reference advance "
                    "has been observed"
                )

            if (
                anchor.last_sync_boottime_ns
                <= self._process_started_boottime_ns
            ):
                self._tracker.invalidate()
                raise TrustedTimeError(
                    "Chrony reference advance predates this process"
                )

            if (
                after_query.boottime_ns
                < anchor.last_sync_boottime_ns
            ):
                self._tracker.invalidate()
                raise TrustedTimeError(
                    "Chrony sync anchor is ahead of the observation"
                )

            return TrustedTimeSnapshot(
                synchronized=True,
                authenticated=True,
                source_id=status.source_id,
                last_sync_utc=anchor.last_sync_utc,
                last_sync_boottime_ns=anchor.last_sync_boottime_ns,
                observed_utc=after_query.utc,
                observed_boottime_ns=after_query.boottime_ns,
                offset=status.offset,
                uncertainty=status.uncertainty,
            )
