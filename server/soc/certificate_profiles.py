"""Strict X.509 certificate-profile validation for the SOC mTLS boundary.

This module validates end-entity certificate purpose, cryptographic
algorithms, validity against explicitly supplied trusted time, and the
backend server certificate's exact DNS SAN.

It does not build trust chains or perform revocation checks. Those remain
the responsibility of OpenSSL and the dedicated CRL validation layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import re

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID

from server.soc.trusted_time import TrustedTime


class CertificateProfileError(ValueError):
    """Raised when an X.509 certificate violates its required profile."""


_ALLOWED_SIGNATURE_HASHES = frozenset({
    "sha256",
    "sha384",
    "sha512",
})

_ALLOWED_EC_CURVES = frozenset({
    "secp256r1",
    "secp384r1",
})

_CERTIFICATE_PEM = re.compile(
    rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
    re.DOTALL,
)


def _require_trusted_time(value: TrustedTime) -> datetime:
    if not isinstance(value, TrustedTime):
        raise TypeError("trusted_time must be a TrustedTime instance")

    now = value.utc_now
    if (
        not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() is None
    ):
        raise CertificateProfileError(
            "Trusted time must contain an aware UTC datetime"
        )

    return now.astimezone(timezone.utc)


def _require_certificate_validity(
    certificate: x509.Certificate,
    now: datetime,
) -> None:
    if now < certificate.not_valid_before_utc:
        raise CertificateProfileError(
            "Certificate is not yet valid"
        )

    if now > certificate.not_valid_after_utc:
        raise CertificateProfileError(
            "Certificate has expired"
        )


def _load_backend_certificate_chain(data: bytes) -> list[x509.Certificate]:
    """Parse a leaf-first PEM chain and reject all non-certificate data."""
    if not isinstance(data, bytes) or not data:
        raise CertificateProfileError("Backend server certificate PEM is missing")

    blocks = _CERTIFICATE_PEM.findall(data)
    if not blocks:
        raise CertificateProfileError("Backend server certificate PEM is invalid")

    remainder = _CERTIFICATE_PEM.sub(b"", data)
    if remainder.strip():
        raise CertificateProfileError(
            "Unexpected data outside backend certificate PEM blocks"
        )

    certificates = []
    for index, block in enumerate(blocks):
        try:
            certificate = x509.load_pem_x509_certificate(block)
        except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
            raise CertificateProfileError(
                "Backend server certificate chain contains invalid PEM"
            ) from exc

        if index > 0:
            try:
                constraints = certificate.extensions.get_extension_for_class(
                    x509.BasicConstraints
                ).value
                usage = certificate.extensions.get_extension_for_class(
                    x509.KeyUsage
                ).value
            except x509.ExtensionNotFound as exc:
                raise CertificateProfileError(
                    "Intermediate certificate lacks CA constraints or key usage"
                ) from exc

            if not constraints.ca or not usage.key_cert_sign:
                raise CertificateProfileError(
                    "Certificates after the leaf must be CA certificates"
                )

        certificates.append(certificate)

    return certificates


def _require_end_entity(certificate: x509.Certificate) -> None:
    try:
        constraints = certificate.extensions.get_extension_for_class(
            x509.BasicConstraints
        ).value
    except x509.ExtensionNotFound as exc:
        raise CertificateProfileError(
            "Certificate has no BasicConstraints extension"
        ) from exc

    if constraints.ca is not False:
        raise CertificateProfileError(
            "End-entity certificate must explicitly have CA:FALSE"
        )


def _require_eku(
    certificate: x509.Certificate,
    expected_oid,
) -> None:
    try:
        eku = certificate.extensions.get_extension_for_class(
            x509.ExtendedKeyUsage
        ).value
    except x509.ExtensionNotFound as exc:
        raise CertificateProfileError(
            "Certificate has no ExtendedKeyUsage extension"
        ) from exc

    if len(eku) != 1 or eku[0] != expected_oid:
        raise CertificateProfileError(
            "Certificate EKU must contain only the required purpose"
        )


def _require_digital_signature_usage(
    certificate: x509.Certificate,
) -> None:
    try:
        usage = certificate.extensions.get_extension_for_class(
            x509.KeyUsage
        ).value
    except x509.ExtensionNotFound as exc:
        raise CertificateProfileError(
            "Certificate has no KeyUsage extension"
        ) from exc

    if usage.digital_signature is not True:
        raise CertificateProfileError(
            "Certificate does not permit digitalSignature"
        )


def _require_public_key_profile(
    certificate: x509.Certificate,
) -> None:
    public_key = certificate.public_key()

    if isinstance(public_key, rsa.RSAPublicKey):
        if public_key.key_size < 3072:
            raise CertificateProfileError(
                "RSA public key must be at least 3072 bits"
            )
        return

    if isinstance(public_key, ec.EllipticCurvePublicKey):
        if public_key.curve.name not in _ALLOWED_EC_CURVES:
            raise CertificateProfileError(
                "ECDSA public key must use NIST P-256 or P-384"
            )
        return

    raise CertificateProfileError(
        "Certificate public-key algorithm is not allowed"
    )


def _require_signature_hash(
    certificate: x509.Certificate,
) -> None:
    try:
        algorithm = certificate.signature_hash_algorithm
    except (UnsupportedAlgorithm, ValueError) as exc:
        raise CertificateProfileError(
            "Certificate signature algorithm is unsupported"
        ) from exc

    if algorithm is None or algorithm.name.lower() not in (
        _ALLOWED_SIGNATURE_HASHES
    ):
        raise CertificateProfileError(
            "Certificate signature must use SHA-256, SHA-384 or SHA-512"
        )


def _validate_common_leaf_profile(
    certificate: x509.Certificate,
    *,
    expected_eku,
    trusted_time: TrustedTime,
) -> None:
    now = _require_trusted_time(trusted_time)

    _require_certificate_validity(certificate, now)
    _require_end_entity(certificate)
    _require_eku(certificate, expected_eku)
    _require_digital_signature_usage(certificate)
    _require_public_key_profile(certificate)
    _require_signature_hash(certificate)


def validate_gateway_client_certificate(
    certificate_der: bytes,
    *,
    trusted_time: TrustedTime,
) -> x509.Certificate:
    """Validate the gateway client leaf profile after a successful TLS handshake.

    Chain validation and CRL checking must already have been performed by
    the SSLContext. This function adds the explicit gateway-client profile
    and trusted-time validity checks.
    """
    if not isinstance(certificate_der, bytes) or not certificate_der:
        raise CertificateProfileError(
            "Gateway client certificate DER is missing"
        )

    try:
        certificate = x509.load_der_x509_certificate(certificate_der)
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise CertificateProfileError(
            "Gateway client certificate DER is invalid"
        ) from exc

    _validate_common_leaf_profile(
        certificate,
        expected_eku=ExtendedKeyUsageOID.CLIENT_AUTH,
        trusted_time=trusted_time,
    )

    return certificate


def validate_backend_server_certificate(
    certificate_pem: bytes,
    private_key_pem: bytes,
    *,
    expected_dns_name: str,
    trusted_time: TrustedTime,
) -> x509.Certificate:
    """Validate the backend server leaf, private-key match and exact DNS SAN."""
    if not isinstance(certificate_pem, bytes) or not certificate_pem:
        raise CertificateProfileError(
            "Backend server certificate PEM is missing"
        )

    if not isinstance(private_key_pem, bytes) or not private_key_pem:
        raise CertificateProfileError(
            "Backend server private key PEM is missing"
        )

    if (
        not isinstance(expected_dns_name, str)
        or not expected_dns_name.strip()
        or expected_dns_name != expected_dns_name.strip()
        or "*" in expected_dns_name
    ):
        raise CertificateProfileError(
            "Expected backend DNS name must be an exact non-wildcard name"
        )

    certificate_chain = _load_backend_certificate_chain(certificate_pem)
    certificate = certificate_chain[0]

    try:
        private_key = serialization.load_pem_private_key(
            private_key_pem,
            password=None,
        )
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise CertificateProfileError(
            "Backend server private key PEM is invalid or encrypted"
        ) from exc

    _validate_common_leaf_profile(
        certificate,
        expected_eku=ExtendedKeyUsageOID.SERVER_AUTH,
        trusted_time=trusted_time,
    )

    try:
        san = certificate.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
    except x509.ExtensionNotFound as exc:
        raise CertificateProfileError(
            "Backend server certificate has no SAN extension"
        ) from exc

    expected = expected_dns_name.rstrip(".").lower()
    dns_names = {
        name.rstrip(".").lower()
        for name in san.get_values_for_type(x509.DNSName)
    }

    if expected not in dns_names:
        raise CertificateProfileError(
            "Backend server certificate DNS SAN does not match"
        )

    try:
        certificate_public_bytes = certificate.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        private_public_bytes = private_key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise CertificateProfileError(
            "Backend certificate/private-key types are incompatible"
        ) from exc

    if certificate_public_bytes != private_public_bytes:
        raise CertificateProfileError(
            "Backend server private key does not match its certificate"
        )

    return certificate


def validate_backend_server_files(
    certificate_path: str | os.PathLike[str],
    private_key_path: str | os.PathLike[str],
    *,
    expected_dns_name: str,
    trusted_time: TrustedTime,
) -> x509.Certificate:
    """Read and validate the configured backend certificate and key files."""
    try:
        certificate_pem = Path(certificate_path).read_bytes()
        private_key_pem = Path(private_key_path).read_bytes()
    except OSError as exc:
        raise CertificateProfileError(
            "Backend server certificate or key file cannot be read"
        ) from exc

    return validate_backend_server_certificate(
        certificate_pem,
        private_key_pem,
        expected_dns_name=expected_dns_name,
        trusted_time=trusted_time,
    )


__all__ = [
    "CertificateProfileError",
    "validate_backend_server_certificate",
    "validate_backend_server_files",
    "validate_gateway_client_certificate",
]
