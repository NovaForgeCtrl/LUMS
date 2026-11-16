"""Fail-closed validation of a direct X.509 Certificate Revocation List.

The CA certificate passed to this module must already be a trusted,
configured issuer certificate. This module does not build or validate
a certificate chain and does not create an SSLContext.

Only direct CRLs are supported. Delta CRLs and indirect CRLs are rejected.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
UTC = timezone.utc

_CERTIFICATE_PEM = re.compile(
    rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
    re.DOTALL,
)
_CRL_PEM = re.compile(
    rb"-----BEGIN X509 CRL-----.*?-----END X509 CRL-----",
    re.DOTALL,
)


class CRLValidationError(ValueError):
    """Raised when CA or CRL material fails preflight validation."""


@dataclass(frozen=True)
class CRLPolicy:
    """Explicit time policy; callers must choose both limits."""

    max_age: timedelta
    clock_skew: timedelta

    def __post_init__(self) -> None:
        if self.max_age <= timedelta(0):
            raise ValueError("max_age must be positive")
        if self.clock_skew < timedelta(0):
            raise ValueError("clock_skew must not be negative")


@dataclass(frozen=True)
class ValidatedCRL:
    """Validated objects and immutable metadata for one CA/CRL pair."""

    ca_certificate: x509.Certificate
    crl: x509.CertificateRevocationList
    this_update: datetime
    next_update: datetime
    revoked_serial_numbers: frozenset[int]
    ca_sha256: str
    crl_sha256: str
    ca_pem: bytes
    crl_pem: bytes

    def is_serial_revoked(self, serial_number: int) -> bool:
        return serial_number in self.revoked_serial_numbers


def _require_aware_utc(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise CRLValidationError("Current time is missing or invalid")

    if value.tzinfo is None or value.utcoffset() is None:
        raise CRLValidationError("Current time must be timezone-aware")

    try:
        return value.astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise CRLValidationError(
            "Current time cannot be normalized to UTC"
        ) from exc


def _load_exactly_one_pem(
    data: bytes,
    pattern: re.Pattern[bytes],
    loader,
    description: str,
):
    if not isinstance(data, bytes) or not data:
        raise CRLValidationError(f"{description} PEM is missing")

    blocks = pattern.findall(data)
    if len(blocks) != 1:
        raise CRLValidationError(
            f"Expected exactly one {description} PEM object"
        )

    # Permit only whitespace outside the one PEM object.
    remainder = pattern.sub(b"", data)
    if remainder.strip():
        raise CRLValidationError(
            f"Unexpected data outside {description} PEM object"
        )

    try:
        return loader(blocks[0])
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise CRLValidationError(
            f"Invalid {description} PEM object"
        ) from exc


def _validate_ca_certificate(
    ca: x509.Certificate,
    now: datetime,
) -> None:
    try:
        constraints = ca.extensions.get_extension_for_class(
            x509.BasicConstraints
        ).value
    except x509.ExtensionNotFound as exc:
        raise CRLValidationError(
            "CA certificate has no BasicConstraints extension"
        ) from exc

    if not constraints.ca:
        raise CRLValidationError(
            "CRL issuer certificate is not a CA"
        )

    try:
        usage = ca.extensions.get_extension_for_class(
            x509.KeyUsage
        ).value
    except x509.ExtensionNotFound as exc:
        raise CRLValidationError(
            "CA certificate has no KeyUsage extension"
        ) from exc

    if not usage.key_cert_sign:
        raise CRLValidationError(
            "CA certificate does not permit keyCertSign"
        )

    if not usage.crl_sign:
        raise CRLValidationError(
            "CA certificate does not permit cRLSign"
        )

    if now < ca.not_valid_before_utc or now > ca.not_valid_after_utc:
        raise CRLValidationError(
            "CRL issuer certificate is outside its validity period"
        )


def _validate_crl_extensions(
    crl: x509.CertificateRevocationList,
    ca: x509.Certificate,
) -> None:
    try:
        crl.extensions.get_extension_for_class(
            x509.DeltaCRLIndicator
        )
    except x509.ExtensionNotFound:
        pass
    else:
        raise CRLValidationError("Delta CRLs are not supported")

    try:
        issuing_point = crl.extensions.get_extension_for_class(
            x509.IssuingDistributionPoint
        ).value
    except x509.ExtensionNotFound:
        issuing_point = None

    if issuing_point is not None and issuing_point.indirect_crl:
        raise CRLValidationError("Indirect CRLs are not supported")

    # If both identifiers are present, they must identify the same CA key.
    try:
        authority_key_id = crl.extensions.get_extension_for_class(
            x509.AuthorityKeyIdentifier
        ).value
    except x509.ExtensionNotFound:
        authority_key_id = None

    try:
        subject_key_id = ca.extensions.get_extension_for_class(
            x509.SubjectKeyIdentifier
        ).value
    except x509.ExtensionNotFound:
        subject_key_id = None

    if (
        authority_key_id is not None
        and authority_key_id.key_identifier is not None
        and subject_key_id is not None
        and authority_key_id.key_identifier != subject_key_id.digest
    ):
        raise CRLValidationError(
            "CRL AuthorityKeyIdentifier does not match the CA"
        )


def validate_direct_crl(
    ca_pem: bytes,
    crl_pem: bytes,
    *,
    policy: CRLPolicy,
    now: datetime,
) -> ValidatedCRL:
    """Validate one direct CRL against its configured issuer certificate.

    The CRL's thisUpdate may be at most policy.clock_skew in the future.
    An already expired nextUpdate is rejected without applying clock
    skew as an expiry grace period. Maximum age is measured from thisUpdate.
    """
    if not isinstance(policy, CRLPolicy):
        raise TypeError("policy must be a CRLPolicy instance")

    current_time = _require_aware_utc(now)

    ca = _load_exactly_one_pem(
        ca_pem,
        _CERTIFICATE_PEM,
        x509.load_pem_x509_certificate,
        "CA certificate",
    )
    crl = _load_exactly_one_pem(
        crl_pem,
        _CRL_PEM,
        x509.load_pem_x509_crl,
        "CRL",
    )

    _validate_ca_certificate(ca, current_time)

    if crl.issuer != ca.subject:
        raise CRLValidationError(
            "CRL issuer does not match the configured CA"
        )

    try:
        signature_valid = crl.is_signature_valid(ca.public_key())
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise CRLValidationError(
            "CRL signature could not be verified"
        ) from exc

    if not signature_valid:
        raise CRLValidationError("CRL signature is invalid")

    _validate_crl_extensions(crl, ca)

    this_update = crl.last_update_utc
    next_update = crl.next_update_utc

    if next_update is None:
        raise CRLValidationError("CRL has no nextUpdate value")

    if next_update <= this_update:
        raise CRLValidationError(
            "CRL nextUpdate must be later than thisUpdate"
        )

    if this_update > current_time + policy.clock_skew:
        raise CRLValidationError(
            "CRL thisUpdate is too far in the future"
        )

    if current_time > next_update:
        raise CRLValidationError("CRL has expired")

    if current_time - this_update > policy.max_age:
        raise CRLValidationError(
            "CRL exceeds the configured maximum age"
        )

    revoked_serials = frozenset(
        entry.serial_number for entry in crl
    )

    ca_der = ca.public_bytes(serialization.Encoding.DER)
    crl_der = crl.public_bytes(serialization.Encoding.DER)

    return ValidatedCRL(
        ca_certificate=ca,
        crl=crl,
        this_update=this_update,
        next_update=next_update,
        revoked_serial_numbers=revoked_serials,
        ca_sha256=hashlib.sha256(ca_der).hexdigest(),
        crl_sha256=hashlib.sha256(crl_der).hexdigest(),
        ca_pem=ca_pem,
        crl_pem=crl_pem,
    )
