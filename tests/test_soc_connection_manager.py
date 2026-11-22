import socket

import pytest
from gunicorn import util

from server.soc.connection_manager import (
    AdmissionConnectionManager,
    ConnectionRevokedError,
    TrackedSocket,
)


def test_register_tracks_active_connection():
    manager = AdmissionConnectionManager()
    local, peer = socket.socketpair()

    try:
        generation = manager.begin_handshake()
        tracked = manager.register(local, generation)

        assert isinstance(tracked, TrackedSocket)
        assert manager.active_connections == 1
        assert tracked.fileno() >= 0
    finally:
        if manager.active_connections:
            tracked.close()
        peer.close()


def test_close_deregisters_connection_and_is_idempotent():
    manager = AdmissionConnectionManager()
    local, peer = socket.socketpair()

    tracked = manager.register(local, manager.begin_handshake())

    assert manager.active_connections == 1

    tracked.close()
    assert manager.active_connections == 0
    assert local.fileno() == -1

    # A second cleanup must not reintroduce an entry or raise.
    tracked.close()
    assert manager.active_connections == 0

    peer.close()


def test_gunicorn_close_graceful_deregisters_tracked_socket():
    manager = AdmissionConnectionManager()
    local, peer = socket.socketpair()

    tracked = manager.register(local, manager.begin_handshake())

    try:
        assert manager.active_connections == 1

        # Exercise Gunicorn's real socket cleanup implementation.
        util.close_graceful(
            tracked,
            timeout=0.01,
            max_drain=4096,
        )

        assert manager.active_connections == 0
        assert local.fileno() == -1
    finally:
        peer.close()


def test_revoke_all_closes_active_connections():
    manager = AdmissionConnectionManager()
    first, first_peer = socket.socketpair()
    second, second_peer = socket.socketpair()

    manager.register(first, manager.begin_handshake())
    manager.register(second, manager.begin_handshake())

    assert manager.active_connections == 2

    revoked = manager.revoke_all()

    assert revoked == 2
    assert manager.active_connections == 0
    assert first.fileno() == -1
    assert second.fileno() == -1

    # The peer observes the shutdown of both connections.
    assert first_peer.recv(1) == b""
    assert second_peer.recv(1) == b""

    first_peer.close()
    second_peer.close()


def test_revoke_invalidates_inflight_handshake_generation():
    manager = AdmissionConnectionManager()
    local, peer = socket.socketpair()

    old_generation = manager.begin_handshake()

    assert manager.revoke_all() == 0

    with pytest.raises(ConnectionRevokedError):
        manager.register(local, old_generation)

    assert manager.active_connections == 0
    assert local.fileno() == -1

    peer.close()


def test_new_generation_can_register_after_revoke():
    manager = AdmissionConnectionManager()
    old_generation = manager.begin_handshake()

    manager.revoke_all()

    new_generation = manager.begin_handshake()
    assert new_generation > old_generation

    local, peer = socket.socketpair()

    try:
        tracked = manager.register(local, new_generation)

        assert manager.active_connections == 1
        assert tracked.fileno() >= 0

        tracked.close()
        assert manager.active_connections == 0
    finally:
        peer.close()


def test_revoke_all_is_idempotent_without_active_connections():
    manager = AdmissionConnectionManager()

    assert manager.revoke_all() == 0
    assert manager.revoke_all() == 0
    assert manager.active_connections == 0
