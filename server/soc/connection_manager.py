"""Lifecycle registry for established SOC backend TLS connections."""

from __future__ import annotations

import socket
import threading


class ConnectionRevokedError(ConnectionError):
    """Raised when a connection is registered after hard revocation."""


class AdmissionConnectionManager:
    """Track established TLS sockets independently of handshake leases."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._connections: dict[int, socket.socket] = {}
        self._next_id = 1
        self._generation = 0

    @property
    def active_connections(self) -> int:
        with self._lock:
            return len(self._connections)

    def begin_handshake(self) -> int:
        """Return the generation that a new handshake must retain."""
        with self._lock:
            return self._generation

    def register(
        self,
        connection: socket.socket,
        generation: int,
    ) -> TrackedSocket:
        if not callable(getattr(connection, "close", None)):
            raise TypeError("connection must provide close()")

        with self._lock:
            rejected = generation != self._generation
            if not rejected:
                connection_id = self._next_id
                self._next_id += 1
                self._connections[connection_id] = connection

        if rejected:
            try:
                connection.close()
            finally:
                raise ConnectionRevokedError(
                    "Connection handshake was invalidated by hard-revoke"
                )

        return TrackedSocket(self, connection_id, connection)

    def close_connection(
        self,
        connection_id: int,
        connection: socket.socket,
    ) -> None:
        with self._lock:
            self._connections.pop(connection_id, None)

        try:
            connection.close()
        except OSError:
            pass

    def revoke_all(self) -> int:
        """Invalidate in-flight handshakes and close all active connections."""
        with self._lock:
            self._generation += 1
            connections = tuple(self._connections.values())
            self._connections.clear()

        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                connection.close()
            except OSError:
                pass

        return len(connections)


class TrackedSocket:
    """Transparent socket proxy that deregisters on Gunicorn socket cleanup."""

    __slots__ = ("_manager", "_connection_id", "_connection")

    def __init__(
        self,
        manager: AdmissionConnectionManager,
        connection_id: int,
        connection: socket.socket,
    ) -> None:
        self._manager = manager
        self._connection_id = connection_id
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self) -> None:
        self._manager.close_connection(
            self._connection_id,
            self._connection,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
