"""Gunicorn TLS adapter for the dedicated PostgreSQL SOC collector."""

from __future__ import annotations

import errno
import socket
import ssl
from os import PathLike
from typing import Callable

from server.soc.admission import AdmissionController
from server.soc.connection_manager import (
    AdmissionConnectionManager,
    TrackedSocket,
)
from server.soc.crl_validation import CRLPolicy
from server.soc.mtls_context import build_backend_mtls_context
from server.soc.certificate_profiles import (
    validate_gateway_client_certificate,
)


class AdmissionSSLContext(ssl.SSLContext):
    """SSLContext subtype enforcing admission at the TLS handshake."""

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, ssl.PROTOCOL_TLS_SERVER)

    def __init__(
        self,
        controller: AdmissionController,
        server_certfile: str | PathLike[str],
        server_keyfile: str | PathLike[str],
        policy: CRLPolicy,
        *,
        expected_dns_name: str,
        handshake_timeout: float = 10.0,
        connection_manager: AdmissionConnectionManager | None = None,
    ) -> None:
        if not isinstance(controller, AdmissionController):
            raise TypeError("controller must be an AdmissionController")
        if not isinstance(policy, CRLPolicy):
            raise TypeError("policy must be a CRLPolicy")
        if (
            isinstance(handshake_timeout, bool)
            or not isinstance(handshake_timeout, (int, float))
            or handshake_timeout <= 0
        ):
            raise ValueError("handshake_timeout must be positive")

        self._controller = controller
        self._connection_manager = (
            connection_manager
            if connection_manager is not None
            else AdmissionConnectionManager()
        )
        self._server_certfile = server_certfile
        self._server_keyfile = server_keyfile
        if (
            not isinstance(expected_dns_name, str)
            or not expected_dns_name.strip()
            or expected_dns_name != expected_dns_name.strip()
            or "*" in expected_dns_name
        ):
            raise ValueError(
                "expected_dns_name must be an exact DNS name"
            )
        self._expected_dns_name = expected_dns_name
        self._policy = policy
        self._handshake_timeout = float(handshake_timeout)
        self._alpn_protocols = ()

    def set_alpn_protocols(self, protocols) -> None:
        self._alpn_protocols = tuple(protocols)

    @staticmethod
    def _close_socket(sock: socket.socket) -> None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def wrap_socket(
        self,
        sock: socket.socket,
        *,
        server_side: bool = False,
        suppress_ragged_eofs: bool = True,
        do_handshake_on_connect: bool = True,
    ) -> TrackedSocket:
        if server_side is not True:
            self._close_socket(sock)
            raise OSError(
                errno.ECONNRESET,
                "TLS admission requires an immediate server-side handshake",
            )

        original_timeout = None
        trusted_time = None
        wrapped = None
        tracked = None

        try:
            original_timeout = sock.gettimeout()
            sock.settimeout(self._handshake_timeout)

            handshake_generation = (
                self._connection_manager.begin_handshake()
            )

            with self._controller.admitted_handshake() as admission:
                if admission is None:
                    # Fail closed before TLS negotiation: do not present
                    # the backend certificate while admission is blocked.
                    raise PermissionError(
                        "Collector TLS admission is BLOCKED"
                    )
                else:
                    validated_crl, trusted_time = admission
                    try:
                        context = build_backend_mtls_context(
                            self._server_certfile,
                            self._server_keyfile,
                            validated_crl,
                            policy=self._policy,
                            trusted_time=trusted_time,
                            expected_dns_name=self._expected_dns_name,
                        )
                    except Exception:
                        self._controller.block()
                        raise

                if self._alpn_protocols:
                    context.set_alpn_protocols(
                        list(self._alpn_protocols)
                    )

                wrapped = context.wrap_socket(
                    sock,
                    server_side=True,
                    suppress_ragged_eofs=suppress_ragged_eofs,
                    do_handshake_on_connect=True,
                )

                tracked = None
                if admission is not None:
                    # OpenSSL has already authenticated the chain and
                    # checked the CRL. Enforce the leaf profile against
                    # the same trusted-time snapshot before registration.
                    validate_gateway_client_certificate(
                        wrapped.getpeercert(binary_form=True),
                        trusted_time=trusted_time,
                    )
                    wrapped.settimeout(original_timeout)
                    tracked = self._connection_manager.register(
                        wrapped,
                        handshake_generation,
                    )
                    wrapped = None

            if tracked is None:
                raise OSError(
                    errno.ECONNRESET,
                    "Backend TLS admission did not establish a tracked connection",
                )

            return tracked

        except Exception as exc:
            if tracked is not None:
                tracked.close()
            elif wrapped is not None:
                self._close_socket(wrapped)
            else:
                self._close_socket(sock)

            raise OSError(
                errno.ECONNRESET,
                "Backend TLS handshake was rejected",
            ) from exc


def make_gunicorn_ssl_context_callback(
    controller: AdmissionController,
    server_certfile: str | PathLike[str],
    server_keyfile: str | PathLike[str],
    policy: CRLPolicy,
    *,
    expected_dns_name: str,
    handshake_timeout: float = 10.0,
    connection_manager: AdmissionConnectionManager | None = None,
) -> Callable:
    """Create the Gunicorn 26.x ssl_context callback."""
    adapter = AdmissionSSLContext(
        controller,
        server_certfile,
        server_keyfile,
        policy,
        expected_dns_name=expected_dns_name,
        handshake_timeout=handshake_timeout,
        connection_manager=connection_manager,
    )

    def ssl_context_callback(config, default_ssl_context_factory):
        from gunicorn.sock import _get_alpn_protocols

        adapter.set_alpn_protocols(_get_alpn_protocols(config))
        return adapter

    ssl_context_callback.connection_manager = adapter._connection_manager
    return ssl_context_callback
