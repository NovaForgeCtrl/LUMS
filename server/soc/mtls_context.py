"""Fail-closed TLS context construction for the dedicated collector backend.

The configured gateway-client CA and its direct CRL are revalidated
immediately before the SSLContext is created. OpenSSL receives the exact
CA and CRL PEM bytes from that validation result.
"""

from __future__ import annotations

import os
import ssl
import tempfile
from pathlib import Path

from server.soc.crl_validation import (
    CRLPolicy,
    CRLValidationError,
    ValidatedCRL,
    validate_direct_crl,
)
from server.soc.trusted_time import TrustedTime


class MTLSContextError(RuntimeError):
    """Raised when a secure backend TLS context cannot be constructed."""


def build_backend_mtls_context(
    server_certfile: str | os.PathLike[str],
    server_keyfile: str | os.PathLike[str],
    validated_crl: ValidatedCRL,
    *,
    policy: CRLPolicy,
    trusted_time: TrustedTime,
) -> ssl.SSLContext:
    """Build a server context requiring a CRL-valid gateway client cert.

    The supplied ValidatedCRL is not blindly trusted: its original PEM
    material is validated again against the explicitly supplied TrustedTime.

    trusted_time must be the result of read_trusted_time(). The builder never
    falls back to the local system clock.

    The backend server certificate/key identify this TLS endpoint.
    The validated CA and CRL authenticate and revoke gateway client
    certificates. They are deliberately separate trust roles.
    """
    if not isinstance(validated_crl, ValidatedCRL):
        raise TypeError("validated_crl must be a ValidatedCRL instance")

    if not isinstance(policy, CRLPolicy):
        raise TypeError("policy must be a CRLPolicy instance")

    if not isinstance(trusted_time, TrustedTime):
        raise TypeError("trusted_time must be a TrustedTime instance")

    if not hasattr(ssl, "VERIFY_CRL_CHECK_LEAF"):
        raise MTLSContextError(
            "This Python/OpenSSL build does not support leaf CRL checking"
        )

    try:
        current_validation = validate_direct_crl(
            validated_crl.ca_pem,
            validated_crl.crl_pem,
            policy=policy,
            now=trusted_time.utc_now,
        )
    except (CRLValidationError, TypeError) as exc:
        raise MTLSContextError(
            "Gateway client CA/CRL validation failed"
        ) from exc

    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        context.load_cert_chain(
            certfile=os.fspath(server_certfile),
            keyfile=os.fspath(server_keyfile),
        )

        # OpenSSL accepts both trusted CA certificates and CRLs in the
        # same PEM trust input. This is the exact material preflighted above.
        trust_material = (
            current_validation.ca_pem
            + b"\n"
            + current_validation.crl_pem
        )
        with tempfile.TemporaryDirectory(prefix="lums-mtls-") as temp_dir:
            trust_file = Path(temp_dir) / "gateway-client-trust.pem"
            trust_file.write_bytes(trust_material)
            context.load_verify_locations(cafile=str(trust_file))

        context.verify_mode = ssl.CERT_REQUIRED
        context.verify_flags |= ssl.VERIFY_CRL_CHECK_LEAF

        return context

    except (OSError, UnicodeError, ValueError, ssl.SSLError) as exc:
        raise MTLSContextError(
            "Could not construct the backend mTLS context"
        ) from exc
