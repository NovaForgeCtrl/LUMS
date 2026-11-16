from dataclasses import replace
from datetime import datetime, timedelta, timezone
import socket
import ssl
import threading

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from server.soc.crl_validation import (
    CRLPolicy,
    validate_direct_crl,
)
from server.soc.mtls_context import (
    MTLSContextError,
    build_backend_mtls_context,
)
from server.soc.trusted_time import TrustedTime


UTC = timezone.utc


def _name(common_name):
    return x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name)
    ])


def _make_ca(now, common_name):
    key = ec.generate_private_key(ec.SECP256R1())
    name = _name(common_name)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before((now - timedelta(days=1)).replace(tzinfo=None))
        .not_valid_after((now + timedelta(days=30)).replace(tzinfo=None))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=1),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
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


def _make_leaf(
    issuer_key,
    issuer_certificate,
    now,
    common_name,
    *,
    eku,
    server_certificate=False,
):
    key = ec.generate_private_key(ec.SECP256R1())

    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(common_name))
        .issuer_name(issuer_certificate.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before((now - timedelta(days=1)).replace(tzinfo=None))
        .not_valid_after((now + timedelta(days=10)).replace(tzinfo=None))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([eku]),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(
                issuer_key.public_key()
            ),
            critical=False,
        )
    )

    if server_certificate:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost")
            ]),
            critical=False,
        )

    certificate = builder.sign(issuer_key, hashes.SHA256())
    return key, certificate


def _pem_certificate(certificate):
    return certificate.public_bytes(serialization.Encoding.PEM)


def _pem_private_key(key):
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _make_crl(ca_key, ca_certificate, now, revoked_serials=()):
    builder = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(ca_certificate.subject)
        .last_update((now - timedelta(minutes=5)).replace(tzinfo=None))
        .next_update((now + timedelta(days=1)).replace(tzinfo=None))
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(
                ca_key.public_key()
            ),
            critical=False,
        )
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

    return builder.sign(ca_key, hashes.SHA256())


def _write_server_material(tmp_path, now):
    server_ca_key, server_ca = _make_ca(now, "Isolated backend server CA")
    server_key, server_certificate = _make_leaf(
        server_ca_key,
        server_ca,
        now,
        "localhost",
        eku=ExtendedKeyUsageOID.SERVER_AUTH,
        server_certificate=True,
    )

    cert_path = tmp_path / "backend-server.pem"
    key_path = tmp_path / "backend-server-key.pem"
    ca_path = tmp_path / "backend-server-ca.pem"

    cert_path.write_bytes(_pem_certificate(server_certificate))
    key_path.write_bytes(_pem_private_key(server_key))
    ca_path.write_bytes(_pem_certificate(server_ca))

    return cert_path, key_path, ca_path


def _write_client_material(tmp_path, key, certificate, name):
    cert_path = tmp_path / f"{name}-client.pem"
    key_path = tmp_path / f"{name}-client-key.pem"
    cert_path.write_bytes(_pem_certificate(certificate))
    key_path.write_bytes(_pem_private_key(key))
    return cert_path, key_path


def _client_context(server_ca_path, client_material=None):
    context = ssl.create_default_context(
        ssl.Purpose.SERVER_AUTH,
        cafile=str(server_ca_path),
    )
    if client_material is not None:
        cert_path, key_path = client_material
        context.load_cert_chain(
            certfile=str(cert_path),
            keyfile=str(key_path),
        )
    return context


def _perform_handshake(server_context, client_context):
    server_socket, client_socket = socket.socketpair()
    server_socket.settimeout(4)
    client_socket.settimeout(4)

    server_result = []

    def server_handshake():
        try:
            with server_context.wrap_socket(
                server_socket,
                server_side=True,
            ) as tls_socket:
                tls_socket.do_handshake()

                # Require an application-data round trip. A client can
                # return from do_handshake() before it observes a
                # server-side certificate rejection.
                payload = tls_socket.recv(1)
                if payload != b"\x01":
                    raise AssertionError("Unexpected client payload")

                tls_socket.sendall(b"\x02")
                server_result.append("accepted")
        except Exception as exc:
            server_result.append(exc)

    thread = threading.Thread(target=server_handshake, daemon=True)
    thread.start()

    try:
        with client_context.wrap_socket(
            client_socket,
            server_hostname="localhost",
        ) as tls_socket:
            tls_socket.do_handshake()
            tls_socket.sendall(b"\x01")

            response = tls_socket.recv(1)
            if response != b"\x02":
                raise AssertionError("Server did not confirm the TLS session")

            client_result = "accepted"
    except Exception as exc:
        client_result = exc

    thread.join(timeout=5)
    if thread.is_alive():
        raise AssertionError("TLS server handshake thread did not terminate")

    return server_result[0], client_result


@pytest.fixture
def tls_material(tmp_path):
    now = datetime.now(UTC)

    gateway_ca_key, gateway_ca = _make_ca(
        now,
        "Isolated gateway client CA",
    )

    revoked_key, revoked_certificate = _make_leaf(
        gateway_ca_key,
        gateway_ca,
        now,
        "revoked-gateway-client",
        eku=ExtendedKeyUsageOID.CLIENT_AUTH,
    )
    valid_key, valid_certificate = _make_leaf(
        gateway_ca_key,
        gateway_ca,
        now,
        "valid-gateway-client",
        eku=ExtendedKeyUsageOID.CLIENT_AUTH,
    )

    crl = _make_crl(
        gateway_ca_key,
        gateway_ca,
        now,
        revoked_serials=[revoked_certificate.serial_number],
    )

    policy = CRLPolicy(
        max_age=timedelta(hours=12),
        clock_skew=timedelta(minutes=2),
    )

    validated = validate_direct_crl(
        _pem_certificate(gateway_ca),
        crl.public_bytes(serialization.Encoding.PEM),
        policy=policy,
        now=now,
    )

    server_cert_path, server_key_path, server_ca_path = (
        _write_server_material(tmp_path, now)
    )

    valid_client = _write_client_material(
        tmp_path,
        valid_key,
        valid_certificate,
        "valid",
    )
    revoked_client = _write_client_material(
        tmp_path,
        revoked_key,
        revoked_certificate,
        "revoked",
    )

    other_ca_key, other_ca = _make_ca(
        now,
        "Untrusted client CA",
    )
    other_key, other_certificate = _make_leaf(
        other_ca_key,
        other_ca,
        now,
        "untrusted-client",
        eku=ExtendedKeyUsageOID.CLIENT_AUTH,
    )
    untrusted_client = _write_client_material(
        tmp_path,
        other_key,
        other_certificate,
        "untrusted",
    )

    trusted_time = TrustedTime(
        utc_now=now,
        boottime_ns=3_000_000_000,
        sync_age=timedelta(seconds=1),
        source_id="isolated-test-time",
        offset=timedelta(milliseconds=1),
        uncertainty=timedelta(milliseconds=2),
    )

    return {
        "policy": policy,
        "trusted_time": trusted_time,
        "validated": validated,
        "server_cert": server_cert_path,
        "server_key": server_key_path,
        "server_ca": server_ca_path,
        "valid_client": valid_client,
        "revoked_client": revoked_client,
        "untrusted_client": untrusted_client,
    }


def _server_context(material):
    return build_backend_mtls_context(
        material["server_cert"],
        material["server_key"],
        material["validated"],
        policy=material["policy"],
        trusted_time=material["trusted_time"],
    )


def test_context_requires_client_certificate_and_crl_check(tls_material):
    context = _server_context(tls_material)

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.verify_flags & ssl.VERIFY_CRL_CHECK_LEAF
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2


def test_accepts_valid_gateway_client_certificate(tls_material):
    server_context = _server_context(tls_material)
    client_context = _client_context(
        tls_material["server_ca"],
        tls_material["valid_client"],
    )

    server_result, client_result = _perform_handshake(
        server_context,
        client_context,
    )

    assert server_result == "accepted"
    assert client_result == "accepted"


def test_rejects_revoked_gateway_client_certificate(tls_material):
    server_context = _server_context(tls_material)
    client_context = _client_context(
        tls_material["server_ca"],
        tls_material["revoked_client"],
    )

    server_result, client_result = _perform_handshake(
        server_context,
        client_context,
    )

    assert isinstance(server_result, ssl.SSLError)
    assert client_result != "accepted"


def test_rejects_client_from_untrusted_ca(tls_material):
    server_context = _server_context(tls_material)
    client_context = _client_context(
        tls_material["server_ca"],
        tls_material["untrusted_client"],
    )

    server_result, client_result = _perform_handshake(
        server_context,
        client_context,
    )

    assert isinstance(server_result, ssl.SSLError)
    assert client_result != "accepted"


def test_rejects_connection_without_client_certificate(tls_material):
    server_context = _server_context(tls_material)
    client_context = _client_context(tls_material["server_ca"])

    server_result, client_result = _perform_handshake(
        server_context,
        client_context,
    )

    assert isinstance(server_result, ssl.SSLError)
    assert client_result != "accepted"


def test_revalidates_original_crl_material_before_context_creation(
    tls_material,
):
    invalidated = replace(
        tls_material["validated"],
        crl_pem=b"not a valid CRL",
    )

    with pytest.raises(MTLSContextError) as exc_info:
        build_backend_mtls_context(
            tls_material["server_cert"],
            tls_material["server_key"],
            invalidated,
            policy=tls_material["policy"],
            trusted_time=tls_material["trusted_time"],
        )

    assert "validation failed" in str(exc_info.value)


def test_rejects_missing_server_certificate_file(tls_material, tmp_path):
    with pytest.raises(MTLSContextError):
        build_backend_mtls_context(
            tmp_path / "missing-server.pem",
            tls_material["server_key"],
            tls_material["validated"],
            policy=tls_material["policy"],
            trusted_time=tls_material["trusted_time"],
        )



def test_context_rejects_unvalidated_time_object(tls_material):
    with pytest.raises(TypeError, match="TrustedTime instance"):
        build_backend_mtls_context(
            tls_material["server_cert"],
            tls_material["server_key"],
            tls_material["validated"],
            policy=tls_material["policy"],
            trusted_time=None,
        )


def test_context_uses_supplied_trusted_time_for_crl_validation(
    tls_material,
):
    # The CRL is valid at fixture creation time, but expired three days later.
    # This must fail even if the host's local clock still says otherwise.
    future_trusted_time = replace(
        tls_material["trusted_time"],
        utc_now=tls_material["trusted_time"].utc_now + timedelta(days=3),
    )

    with pytest.raises(MTLSContextError, match="validation failed"):
        build_backend_mtls_context(
            tls_material["server_cert"],
            tls_material["server_key"],
            tls_material["validated"],
            policy=tls_material["policy"],
            trusted_time=future_trusted_time,
        )
