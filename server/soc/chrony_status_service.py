"""Unprivileged, read-only host service exposing authenticated Chrony status."""

from __future__ import annotations

import json
import logging
import os
import socket
import signal
import stat
import struct
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from server.soc.chrony_config import (
    ChronyConfigError,
    load_protected_chrony_config,
)
from server.soc.chrony_status import (
    ChronyStatusError,
    parse_chrony_status,
)


LOGGER = logging.getLogger("lums.chrony_status_service")

HOST_SERVICE_UID = 986
HOST_SERVICE_GID = 987

ALLOWED_CLIENT_UID = 10001
ALLOWED_CLIENT_GID = 10001

DEFAULT_SOCKET_PATH = Path(
    "/run/lums-chrony-status/status.sock"
)

EXPECTED_CONFIG_SHA256 = (
    "0b36fbc86e90f5bd353419f106286955c50c37fbeb18bdbe8df9184f046cc7d5"
)

STATUS_PROTOCOL_VERSION = 1
STATUS_REQUEST = b"LUMS-CHRONY-STATUS/1\n"

MAX_REQUEST_SIZE = 128
MAX_RESPONSE_SIZE = 32 * 1024
MAX_CHRONYC_OUTPUT = 8 * 1024

SO_PEERCRED_STRUCT = struct.Struct("3i")


class ChronyStatusServiceError(RuntimeError):
    """Raised when the host status service cannot safely serve a request."""


def _peer_credentials(connection: socket.socket) -> tuple[int, int, int]:
    if not hasattr(socket, "SO_PEERCRED"):
        raise ChronyStatusServiceError(
            "Linux SO_PEERCRED is unavailable"
        )

    try:
        raw = connection.getsockopt(
            socket.SOL_SOCKET,
            socket.SO_PEERCRED,
            SO_PEERCRED_STRUCT.size,
        )
        pid, uid, gid = SO_PEERCRED_STRUCT.unpack(raw)
    except OSError as exc:
        raise ChronyStatusServiceError(
            "client peer credentials cannot be verified"
        ) from exc

    if pid < 0 or uid < 0 or gid < 0:
        raise ChronyStatusServiceError(
            "client peer credentials are invalid"
        )

    return pid, uid, gid


def _read_only_chronyc(command: str) -> str:
    """Run exactly one approved read-only Chrony monitoring command."""
    if command not in {"tracking", "sources"}:
        raise ChronyStatusServiceError(
            "requested Chrony command is not approved"
        )

    try:
        result = subprocess.run(
            [
                "/usr/bin/chronyc",
                "-h",
                "127.0.0.1",
                "-N",
                "-c",
                command,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=5,
            check=False,
            close_fds=True,
            env={
                "LANG": "C",
                "LC_ALL": "C",
            },
        )
    except (
        OSError,
        subprocess.TimeoutExpired,
        UnicodeError,
    ) as exc:
        raise ChronyStatusServiceError(
            "Chrony monitoring command could not be executed"
        ) from exc

    if result.returncode != 0:
        raise ChronyStatusServiceError(
            "Chrony monitoring command failed"
        )

    if (
        not result.stdout
        or len(result.stdout.encode("utf-8")) > MAX_CHRONYC_OUTPUT
    ):
        raise ChronyStatusServiceError(
            "Chrony monitoring output is empty or oversized"
        )

    return result.stdout


class ChronyStatusService:
    """Serve one fixed read-only Chrony status protocol over a Unix socket."""

    def __init__(
        self,
        *,
        socket_path: str | os.PathLike[str] = DEFAULT_SOCKET_PATH,
        service_uid: int = HOST_SERVICE_UID,
        service_gid: int = HOST_SERVICE_GID,
        allowed_client_uid: int = ALLOWED_CLIENT_UID,
        allowed_client_gid: int = ALLOWED_CLIENT_GID,
        expected_config_sha256: str = EXPECTED_CONFIG_SHA256,
        config_loader: Callable = load_protected_chrony_config,
        command_runner: Callable[[str], str] = _read_only_chronyc,
        max_clients: int = 4,
    ) -> None:
        raw_path = os.fspath(socket_path)

        if (
            not isinstance(raw_path, str)
            or not raw_path.startswith("/")
            or ".." in Path(raw_path).parts
            or len(os.fsencode(raw_path)) >= 104
        ):
            raise ValueError("socket path is invalid")

        for name, value in (
            ("service_uid", service_uid),
            ("service_gid", service_gid),
            ("allowed_client_uid", allowed_client_uid),
            ("allowed_client_gid", allowed_client_gid),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} is invalid")

        if (
            not isinstance(expected_config_sha256, str)
            or len(expected_config_sha256) != 64
            or any(c not in "0123456789abcdef"
                   for c in expected_config_sha256)
        ):
            raise ValueError("expected configuration digest is invalid")

        if type(max_clients) is not int or not 1 <= max_clients <= 16:
            raise ValueError("max_clients must be between 1 and 16")

        if not callable(config_loader) or not callable(command_runner):
            raise TypeError("configuration and command readers must be callable")

        self.socket_path = Path(raw_path)
        self.service_uid = service_uid
        self.service_gid = service_gid
        self.allowed_client_uid = allowed_client_uid
        self.allowed_client_gid = allowed_client_gid
        self.expected_config_sha256 = expected_config_sha256
        self.config_loader = config_loader
        self.command_runner = command_runner

        self._stop_event = threading.Event()
        self._slots = threading.BoundedSemaphore(max_clients)
        self._listener: socket.socket | None = None

    def build_response(self) -> bytes:
        """Validate configuration and current Chrony data before serving."""
        try:
            config = self.config_loader()
        except (ChronyConfigError, OSError) as exc:
            raise ChronyStatusServiceError(
                "protected Chrony configuration validation failed"
            ) from exc

        if config.sha256 != self.expected_config_sha256:
            raise ChronyStatusServiceError(
                "Chrony configuration digest is not approved"
            )

        tracking = self.command_runner("tracking")
        sources = self.command_runner("sources")

        try:
            # Validate the pair on the host as well as in the application.
            parse_chrony_status(tracking, sources)
        except ChronyStatusError as exc:
            raise ChronyStatusServiceError(
                "Chrony status does not meet the host time policy"
            ) from exc

        response = {
            "schema_version": STATUS_PROTOCOL_VERSION,
            "config_sha256": config.sha256,
            "tracking_csv": tracking,
            "sources_csv": sources,
        }

        try:
            payload = json.dumps(
                response,
                ensure_ascii=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError) as exc:
            raise ChronyStatusServiceError(
                "Chrony status response could not be serialized"
            ) from exc

        if not payload or len(payload) > MAX_RESPONSE_SIZE:
            raise ChronyStatusServiceError(
                "Chrony status response exceeds the protocol size limit"
            )

        return payload

    def handle_connection(self, connection: socket.socket) -> None:
        """Verify the client and serve exactly one status request."""
        connection.settimeout(3.0)

        pid, uid, gid = _peer_credentials(connection)

        if (
            uid != self.allowed_client_uid
            or gid != self.allowed_client_gid
        ):
            raise ChronyStatusServiceError(
                "client peer identity is not approved"
            )

        received = bytearray()

        while len(received) <= MAX_REQUEST_SIZE:
            chunk = connection.recv(
                min(64, MAX_REQUEST_SIZE + 1 - len(received))
            )

            if not chunk:
                break

            received.extend(chunk)

        if bytes(received) != STATUS_REQUEST:
            raise ChronyStatusServiceError(
                "client request does not match the fixed protocol"
            )

        payload = self.build_response()
        connection.sendall(payload)

        LOGGER.debug(
            "Served Chrony status to approved peer pid=%d uid=%d gid=%d",
            pid,
            uid,
            gid,
        )

    def _create_listener(self) -> socket.socket:
        if (
            os.geteuid() != self.service_uid
            or os.getegid() != self.service_gid
        ):
            raise ChronyStatusServiceError(
                "service process UID/GID does not match its configuration"
            )

        try:
            directory = self.socket_path.parent.lstat()
        except OSError as exc:
            raise ChronyStatusServiceError(
                "runtime directory cannot be inspected"
            ) from exc

        if (
            not stat.S_ISDIR(directory.st_mode)
            or directory.st_uid != self.service_uid
            or directory.st_gid != self.service_gid
            or stat.S_IMODE(directory.st_mode) != 0o750
        ):
            raise ChronyStatusServiceError(
                "runtime directory ownership or permissions are unsafe"
            )

        try:
            self.socket_path.lstat()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise ChronyStatusServiceError(
                "socket path cannot be inspected"
            ) from exc
        else:
            # Never unlink an existing socket or filesystem object.
            raise ChronyStatusServiceError(
                "socket path already exists; refusing to replace it"
            )

        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            previous_umask = os.umask(0o117)
            try:
                listener.bind(os.fspath(self.socket_path))
            finally:
                os.umask(previous_umask)

            os.chmod(self.socket_path, 0o660)

            info = self.socket_path.lstat()

            if (
                not stat.S_ISSOCK(info.st_mode)
                or info.st_uid != self.service_uid
                or info.st_gid != self.service_gid
                or stat.S_IMODE(info.st_mode) != 0o660
                or info.st_nlink != 1
            ):
                raise ChronyStatusServiceError(
                    "created socket has unsafe ownership or permissions"
                )

            listener.listen(8)
            listener.settimeout(1.0)

            return listener

        except Exception:
            listener.close()
            try:
                info = self.socket_path.lstat()
                if (
                    stat.S_ISSOCK(info.st_mode)
                    and info.st_uid == self.service_uid
                    and info.st_gid == self.service_gid
                ):
                    self.socket_path.unlink()
            except OSError:
                pass
            raise

    def _serve_client(self, connection: socket.socket) -> None:
        try:
            with connection:
                self.handle_connection(connection)
        except (
            ChronyStatusServiceError,
            OSError,
            TimeoutError,
        ) as exc:
            LOGGER.warning("Rejected Chrony status request: %s", exc)
        finally:
            self._slots.release()

    def serve_forever(self) -> None:
        listener = self._create_listener()
        self._listener = listener

        LOGGER.info(
            "Chrony status service listening on %s",
            self.socket_path,
        )

        try:
            while not self._stop_event.is_set():
                try:
                    connection, _ = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self._stop_event.is_set():
                        break
                    raise

                if not self._slots.acquire(blocking=False):
                    connection.close()
                    continue

                thread = threading.Thread(
                    target=self._serve_client,
                    args=(connection,),
                    name="chrony-status-client",
                    daemon=True,
                )
                thread.start()

        finally:
            listener.close()
            self._listener = None

            # Remove only the socket inode created by this process.
            try:
                info = self.socket_path.lstat()
                if (
                    stat.S_ISSOCK(info.st_mode)
                    and info.st_uid == self.service_uid
                    and info.st_gid == self.service_gid
                ):
                    self.socket_path.unlink()
            except FileNotFoundError:
                pass

    def stop(self) -> None:
        """Request a graceful stop; accept() exits on its bounded timeout."""
        self._stop_event.set()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    service = ChronyStatusService()

    def request_shutdown(signum, frame):
        LOGGER.info(
            "Received shutdown signal %s; stopping Chrony status service",
            signum,
        )
        service.stop()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    service.serve_forever()


if __name__ == "__main__":
    main()
