"""Strict parsing of a gateway-forwarded X.509 leaf certificate.

This module validates the encoding and DER certificate structure only.
It does NOT validate certificate trust, chain, validity period, revocation,
or the authenticity of the connection that supplied the certificate.
Those checks belong to the TLS gateway and authenticated backend boundary.
"""

import base64
import binascii
import hashlib
import re

from cryptography.hazmat.primitives.serialization import Encoding
from cryptography import x509


MAX_CERTIFICATE_DER_BYTES = 16 * 1024
MAX_CERTIFICATE_HEADER_BYTES = 21_846

_BASE64URL_PATTERN = re.compile(r"[A-Za-z0-9_-]+\Z")


class CertificateIdentityError(ValueError):
    """Raised when a forwarded certificate value is invalid."""


def fingerprint_from_base64url_der(value: object) -> str:
    """Return the lowercase SHA-256 fingerprint of one canonical DER cert.

    The input must be an unpadded Base64url string containing exactly one
    DER-encoded X.509 certificate. No trust decision is made here.
    """
    if not isinstance(value, str):
        raise CertificateIdentityError("Invalid certificate identity value")

    if not value or len(value) > MAX_CERTIFICATE_HEADER_BYTES:
        raise CertificateIdentityError("Invalid certificate identity length")

    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise CertificateIdentityError(
            "Invalid certificate identity encoding"
        ) from exc

    if _BASE64URL_PATTERN.fullmatch(value) is None:
        raise CertificateIdentityError("Invalid certificate identity encoding")

    # A Base64 string with a length congruent to 1 modulo 4 is impossible.
    if len(value) % 4 == 1:
        raise CertificateIdentityError("Invalid certificate identity encoding")

    padded = value + ("=" * ((-len(value)) % 4))

    try:
        der_bytes = base64.b64decode(
            padded.encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise CertificateIdentityError(
            "Invalid certificate identity encoding"
        ) from exc

    if not der_bytes or len(der_bytes) > MAX_CERTIFICATE_DER_BYTES:
        raise CertificateIdentityError("Invalid certificate DER length")

    # Reject alternative/non-canonical Base64url representations.
    canonical_value = base64.urlsafe_b64encode(der_bytes).decode("ascii").rstrip("=")
    if canonical_value != value:
        raise CertificateIdentityError("Non-canonical certificate identity")

    try:
        certificate = x509.load_der_x509_certificate(der_bytes)
        canonical_der = certificate.public_bytes(Encoding.DER)
    except (ValueError, TypeError) as exc:
        raise CertificateIdentityError("Invalid DER certificate") from exc

    # Also rejects trailing data and non-canonical DER encodings.
    if canonical_der != der_bytes:
        raise CertificateIdentityError("Non-canonical DER certificate")

    return hashlib.sha256(der_bytes).hexdigest()
