import base64
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID

import server.soc.certificate_identity as certificate_identity
from server.soc.certificate_identity import (
    CertificateIdentityError,
    MAX_CERTIFICATE_DER_BYTES,
    MAX_CERTIFICATE_HEADER_BYTES,
    fingerprint_from_base64url_der,
)


@pytest.fixture
def der_certificate():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "lums-test-collector"),
        ]
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(1)
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )

    return certificate.public_bytes(Encoding.DER)


def encode_der(der_bytes):
    return base64.urlsafe_b64encode(der_bytes).decode("ascii").rstrip("=")


def test_valid_certificate_returns_sha256_of_exact_der_bytes(der_certificate):
    value = encode_der(der_certificate)

    result = fingerprint_from_base64url_der(value)

    assert result == hashlib.sha256(der_certificate).hexdigest()
    assert len(result) == 64
    assert result == result.lower()


def test_rejects_missing_or_non_string_values():
    for value in (None, "", b"certificate", 123):
        with pytest.raises(CertificateIdentityError):
            fingerprint_from_base64url_der(value)


@pytest.mark.parametrize(
    "value",
    [
        "YWJj=",       # Padding is forbidden.
        "YWJj\n",      # Whitespace is forbidden.
        "YWJj+",       # Standard Base64 alphabet is forbidden.
        "YWJj/",       # Standard Base64 alphabet is forbidden.
        "YWJj=",       # Explicit padding is forbidden.
        "A",           # Impossible Base64 length.
        "äöü",         # Non-ASCII input.
    ],
)
def test_rejects_non_base64url_values(value):
    with pytest.raises(CertificateIdentityError):
        fingerprint_from_base64url_der(value)


def test_rejects_header_value_over_limit():
    value = "A" * (MAX_CERTIFICATE_HEADER_BYTES + 1)

    with pytest.raises(CertificateIdentityError):
        fingerprint_from_base64url_der(value)


def test_rejects_der_over_limit_independently(monkeypatch):
    oversized_der = b"x" * (MAX_CERTIFICATE_DER_BYTES + 1)
    value = encode_der(oversized_der)

    # Raise only the header limit in this test so the DER limit is reached.
    monkeypatch.setattr(
        certificate_identity,
        "MAX_CERTIFICATE_HEADER_BYTES",
        30_000,
    )

    with pytest.raises(CertificateIdentityError, match="DER length"):
        fingerprint_from_base64url_der(value)


def test_rejects_invalid_der():
    with pytest.raises(CertificateIdentityError):
        fingerprint_from_base64url_der(encode_der(b"not a certificate"))


def test_rejects_trailing_data_after_certificate(der_certificate):
    value = encode_der(der_certificate + b"\x00")

    with pytest.raises(CertificateIdentityError):
        fingerprint_from_base64url_der(value)


def test_rejects_noncanonical_base64url_representation(der_certificate):
    encoded = encode_der(der_certificate)

    # Change unused low-order bits in the final Base64 character while
    # retaining the same decoded bytes. The canonicality check must reject it.
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    remainder = len(der_certificate) % 3

    if remainder == 1:
        final_index = alphabet.index(encoded[-1])
        replacement_index = (final_index & 0b110000) | ((final_index + 1) & 0b001111)
    elif remainder == 2:
        final_index = alphabet.index(encoded[-1])
        replacement_index = (final_index & 0b111100) | ((final_index + 1) & 0b000011)
    else:
        pytest.skip("DER length has no unused Base64 bits")

    if replacement_index == alphabet.index(encoded[-1]):
        replacement_index = (replacement_index + 1) % len(alphabet)

    noncanonical = encoded[:-1] + alphabet[replacement_index]

    with pytest.raises(CertificateIdentityError):
        fingerprint_from_base64url_der(noncanonical)
