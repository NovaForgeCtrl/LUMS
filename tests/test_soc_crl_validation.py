from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

import server.soc.crl_validation as crl_validation

from server.soc.crl_validation import (
    CRLPolicy,
    CRLValidationError,
    validate_direct_crl,
)


UTC = timezone.utc


def make_name(common_name):
    return x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name)
    ])


def make_ca(
    now,
    *,
    crl_sign=True,
    ca=True,
    common_name="LUMS isolated CRL test CA",
):
    key = ec.generate_private_key(ec.SECP256R1())
    name = make_name(common_name)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before((now - timedelta(days=1)).replace(tzinfo=None))
        .not_valid_after((now + timedelta(days=30)).replace(tzinfo=None))
        .add_extension(
            x509.BasicConstraints(ca=ca, path_length=1 if ca else None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=ca,
                crl_sign=crl_sign,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    return key, certificate


def make_crl(
    ca_key,
    ca_certificate,
    now,
    *,
    revoked_serials=(),
    this_update=None,
    next_update=None,
    include_next_update=True,
    indirect=False,
    delta=False,
    authority_key=None,
):
    this_update = this_update or now - timedelta(minutes=5)
    next_update = (
        next_update
        if next_update is not None
        else now + timedelta(days=2)
    )

    builder = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(ca_certificate.subject)
        .last_update(this_update.replace(tzinfo=None))
    )

    if include_next_update:
        builder = builder.next_update(
            next_update.replace(tzinfo=None)
        )

    for serial in revoked_serials:
        entry = (
            x509.RevokedCertificateBuilder()
            .serial_number(serial)
            .revocation_date(
                (now - timedelta(minutes=1)).replace(tzinfo=None)
            )
            .build()
        )
        builder = builder.add_revoked_certificate(entry)

    authority_key = authority_key or ca_key

    builder = builder.add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(
            authority_key.public_key()
        ),
        critical=False,
    )

    if indirect:
        builder = builder.add_extension(
            x509.IssuingDistributionPoint(
                full_name=None,
                relative_name=None,
                only_contains_user_certs=False,
                only_contains_ca_certs=False,
                only_some_reasons=None,
                indirect_crl=True,
                only_contains_attribute_certs=False,
            ),
            critical=True,
        )

    if delta:
        builder = builder.add_extension(
            x509.DeltaCRLIndicator(1),
            critical=True,
        )

    return builder.sign(ca_key, hashes.SHA256())


def pem_ca(certificate):
    return certificate.public_bytes(serialization.Encoding.PEM)


def pem_crl(crl):
    return crl.public_bytes(serialization.Encoding.PEM)


@pytest.fixture
def pki():
    now = datetime.now(UTC)
    ca_key, ca_certificate = make_ca(now)
    policy = CRLPolicy(
        max_age=timedelta(days=1),
        clock_skew=timedelta(minutes=2),
    )
    return now, ca_key, ca_certificate, policy


def test_accepts_valid_direct_crl(pki):
    now, ca_key, ca_certificate, policy = pki
    crl = make_crl(ca_key, ca_certificate, now)

    result = validate_direct_crl(
        pem_ca(ca_certificate),
        pem_crl(crl),
        policy=policy,
        now=now,
    )

    assert result.ca_sha256
    assert result.crl_sha256
    assert result.ca_pem == pem_ca(ca_certificate)
    assert result.crl_pem == pem_crl(crl)
    assert result.revoked_serial_numbers == frozenset()


def test_reports_revoked_serial_number(pki):
    now, ca_key, ca_certificate, policy = pki
    revoked_serial = 123456789
    crl = make_crl(
        ca_key,
        ca_certificate,
        now,
        revoked_serials=[revoked_serial],
    )

    result = validate_direct_crl(
        pem_ca(ca_certificate),
        pem_crl(crl),
        policy=policy,
        now=now,
    )

    assert result.is_serial_revoked(revoked_serial)
    assert not result.is_serial_revoked(987654321)


def test_rejects_missing_crl(pki):
    now, _, ca_certificate, policy = pki

    with pytest.raises(CRLValidationError, match="CRL PEM is missing"):
        validate_direct_crl(
            pem_ca(ca_certificate),
            b"",
            policy=policy,
            now=now,
        )


def test_rejects_multiple_ca_certificates(pki):
    now, _, ca_certificate, policy = pki
    ca_pem = pem_ca(ca_certificate) + pem_ca(ca_certificate)

    crl = make_crl(
        make_ca(now)[0],
        ca_certificate,
        now,
    )

    with pytest.raises(CRLValidationError, match="exactly one"):
        validate_direct_crl(
            ca_pem,
            pem_crl(crl),
            policy=policy,
            now=now,
        )


def test_rejects_wrong_crl_issuer(pki):
    now, _, ca_certificate, policy = pki
    other_key, other_ca = make_ca(
        now,
        common_name="Different isolated CRL test CA",
    )
    crl = make_crl(other_key, other_ca, now)

    with pytest.raises(CRLValidationError, match="issuer does not match"):
        validate_direct_crl(
            pem_ca(ca_certificate),
            pem_crl(crl),
            policy=policy,
            now=now,
        )


def test_rejects_invalid_crl_signature(pki):
    now, ca_key, ca_certificate, policy = pki
    wrong_key, _ = make_ca(now)

    crl = make_crl(
        wrong_key,
        ca_certificate,
        now,
        authority_key=ca_key,
    )

    with pytest.raises(CRLValidationError, match="signature is invalid"):
        validate_direct_crl(
            pem_ca(ca_certificate),
            pem_crl(crl),
            policy=policy,
            now=now,
        )


def test_rejects_ca_without_crl_sign_usage(pki):
    now, _, _, policy = pki
    ca_key, ca_certificate = make_ca(now, crl_sign=False)
    crl = make_crl(ca_key, ca_certificate, now)

    with pytest.raises(CRLValidationError, match="cRLSign"):
        validate_direct_crl(
            pem_ca(ca_certificate),
            pem_crl(crl),
            policy=policy,
            now=now,
        )


def test_rejects_certificate_that_is_not_a_ca(pki):
    now, _, _, policy = pki
    ca_key, ca_certificate = make_ca(now, ca=False)
    crl = make_crl(ca_key, ca_certificate, now)

    with pytest.raises(CRLValidationError, match="not a CA"):
        validate_direct_crl(
            pem_ca(ca_certificate),
            pem_crl(crl),
            policy=policy,
            now=now,
        )


def test_rejects_crl_without_next_update(
    pki,
    monkeypatch,
):
    now, _, ca_certificate, policy = pki

    class FakeCRL:
        issuer = ca_certificate.subject
        last_update_utc = now - timedelta(minutes=5)
        next_update_utc = None

        def is_signature_valid(self, public_key):
            return True

    fake_crl = FakeCRL()

    def fake_loader(
        pem_data,
        pattern,
        loader,
        description,
    ):
        if description == "CA certificate":
            return ca_certificate

        if description == "CRL":
            return fake_crl

        raise AssertionError(
            f"Unexpected PEM description: {description}"
        )

    monkeypatch.setattr(
        crl_validation,
        "_load_exactly_one_pem",
        fake_loader,
    )
    monkeypatch.setattr(
        crl_validation,
        "_validate_crl_extensions",
        lambda crl, ca: None,
    )

    with pytest.raises(
        CRLValidationError,
        match="no nextUpdate",
    ):
        validate_direct_crl(
            b"test CA",
            b"test CRL",
            policy=policy,
            now=now,
        )

def test_rejects_expired_crl(pki):
    now, ca_key, ca_certificate, policy = pki
    crl = make_crl(
        ca_key,
        ca_certificate,
        now,
        this_update=now - timedelta(days=2),
        next_update=now - timedelta(minutes=1),
    )

    with pytest.raises(CRLValidationError, match="expired"):
        validate_direct_crl(
            pem_ca(ca_certificate),
            pem_crl(crl),
            policy=policy,
            now=now,
        )


def test_rejects_crl_exceeding_maximum_age(pki):
    now, ca_key, ca_certificate, policy = pki
    crl = make_crl(
        ca_key,
        ca_certificate,
        now,
        this_update=now - timedelta(days=2),
        next_update=now + timedelta(days=2),
    )

    with pytest.raises(CRLValidationError, match="maximum age"):
        validate_direct_crl(
            pem_ca(ca_certificate),
            pem_crl(crl),
            policy=policy,
            now=now,
        )


def test_rejects_crl_too_far_in_future(pki):
    now, ca_key, ca_certificate, policy = pki
    crl = make_crl(
        ca_key,
        ca_certificate,
        now,
        this_update=now + timedelta(minutes=10),
        next_update=now + timedelta(days=2),
    )

    with pytest.raises(CRLValidationError, match="future"):
        validate_direct_crl(
            pem_ca(ca_certificate),
            pem_crl(crl),
            policy=policy,
            now=now,
        )


def test_rejects_indirect_crl(pki):
    now, ca_key, ca_certificate, policy = pki
    crl = make_crl(
        ca_key,
        ca_certificate,
        now,
        indirect=True,
    )

    with pytest.raises(CRLValidationError, match="Indirect CRLs"):
        validate_direct_crl(
            pem_ca(ca_certificate),
            pem_crl(crl),
            policy=policy,
            now=now,
        )


def test_rejects_delta_crl(pki):
    now, ca_key, ca_certificate, policy = pki
    crl = make_crl(
        ca_key,
        ca_certificate,
        now,
        delta=True,
    )

    with pytest.raises(CRLValidationError, match="Delta CRLs"):
        validate_direct_crl(
            pem_ca(ca_certificate),
            pem_crl(crl),
            policy=policy,
            now=now,
        )


def test_rejects_naive_current_time(pki):
    _, ca_key, ca_certificate, policy = pki
    now = datetime.now(UTC)
    crl = make_crl(ca_key, ca_certificate, now)

    with pytest.raises(CRLValidationError, match="timezone-aware"):
        validate_direct_crl(
            pem_ca(ca_certificate),
            pem_crl(crl),
            policy=policy,
            now=datetime.now(),
        )


def test_rejects_nonpositive_policy():
    with pytest.raises(ValueError, match="max_age"):
        CRLPolicy(
            max_age=timedelta(0),
            clock_skew=timedelta(minutes=1),
        )

    with pytest.raises(ValueError, match="clock_skew"):
        CRLPolicy(
            max_age=timedelta(days=1),
            clock_skew=timedelta(seconds=-1),
        )
