# LUMS SOC Collector – mTLS Implementation Plan

Status: Draft
Scope: First controlled isolated rollout
Branch: feature/soc-worker-service

## 1. Objective

Implement a mutually authenticated TLS boundary for SOC collectors.

The collector identity must originate from a client certificate
validated by a trusted TLS gateway. The Flask application must never
derive collector identity from arbitrary client-controlled HTTP headers
or request-body fields.

The collector endpoint remains disabled unless explicitly enabled.

## 2. Current implementation

The current application provides:

- POST /alerts/api/collector/v1/events
- LUMS_SOC_COLLECTOR_ENABLED feature gate
- LUMS_COLLECTOR_IDENTITY_PROVIDER injection point
- syntactic validation of a provider-returned 64-character hexadecimal
  fingerprint
- collector registration and revocation checks
- bounded event batch validation
- atomic ingestion and duplicate detection

The current fingerprint helper does not parse or validate X.509
certificates, inspect a TLS peer certificate or authenticate a proxy.
It trusts the configured provider's output after checking its format.

The current repository does not provide:

- a deployed mTLS gateway
- a configured production identity provider
- a trusted proxy-to-backend deployment boundary
- a Flask provider that parses Base64url-DER certificates
- real TLS integration tests for collector or gateway certificates

The current Flask tests simulate the identity provider with test
callbacks. They validate collector API behavior, not certificate
authentication or a real TLS trust boundary.

### Planned deployment topology

The target deployment separates the data plane, control plane and
application backend into independent containers:

- Envoy gateway: terminates collector-facing TLS and forwards
  authenticated collector requests.
- LUMS Control Plane: manages Envoy's dynamic configuration and
  secret delivery through xDS/SDS.
- LUMS Flask/Gunicorn backend: remains a separate application
  component and is not replaced by the gateway or control plane.

The planned network boundaries are:

- A dedicated internal control network connects Envoy and the
  LUMS Control Plane.
- A separate dedicated backend network connects Envoy and the
  Flask/Gunicorn backend.
- The Control Plane must not have direct network access to the
  application backend.
- The Control Plane must not publish a host port in the initial
  deployment design.
- Only the intended collector-facing HTTPS listener is exposed
  by the gateway.

The existing backend remains unchanged during the planning phase.
The dedicated networks are architectural targets only. Existing
test containers and networks must not be reused or modified without
separate approval.

The Control Plane manages configuration and certificate delivery;
it does not replace the gateway's TLS admission checks. Envoy must
enforce collector-side certificate and CRL requirements at the
actual TLS admission point. The backend independently enforces
gateway-client authentication and its own revocation requirements.

The exact Envoy release and immutable image digest, as well as the
Control Plane implementation language, libraries and versions,
remain subject to verification before implementation.

## 3. Target request flow

1. A collector establishes TLS with the gateway.
2. The gateway requests and verifies a client certificate.
3. The gateway rejects missing, untrusted or invalid certificates.
4. The gateway removes all client-supplied identity headers,
   including X-LUMS-Verified-Client-Cert.
5. The gateway forwards the verified leaf certificate as unpadded
   Base64url-encoded DER in X-LUMS-Verified-Client-Cert.
6. Flask accepts this header only across the authenticated gateway
   boundary, validates exactly one DER-encoded X.509 certificate and
   calculates SHA-256 over its DER bytes.
7. CollectorStore checks whether the fingerprint is registered and
   active.
8. EventIngestor validates the complete batch.
9. CollectorStore persists the batch atomically.

The request body must never define the collector identity.

## 4. Certificate fingerprint

The canonical identity is the lowercase hexadecimal SHA-256 digest
of the DER-encoded leaf certificate.

The fingerprint must be calculated by Flask from the verified
certificate material. It must not be copied from an arbitrary
fingerprint header.

The internal certificate header is:

X-LUMS-Verified-Client-Cert

Its value is the unpadded Base64url encoding of exactly one
DER-encoded X.509 leaf certificate.

The encoding contract is:

- RFC 4648 Base64url alphabet only: A-Z, a-z, 0-9, hyphen and underscore
- padding characters are not permitted
- whitespace and line breaks are not permitted
- the decoded value must contain exactly one valid DER X.509 certificate
- the decoded DER certificate must be no larger than 16 KiB
- the encoded header value must not exceed 21,846 bytes
- every gateway, proxy and backend hop must allow at least 24 KiB
  for this complete HTTP header field
- aggregate HTTP request-header limits must also accommodate this field
- intermediaries must never truncate or silently rewrite the value
- oversized values must be rejected explicitly, not partially accepted
- decoding must be strict and the encoding must be canonical
- the parsed certificate must be re-serialized as DER and compared
  byte-for-byte with the original decoded input
- any difference between the original DER bytes and the re-serialized
  DER bytes must cause rejection
- trailing bytes or additional certificate objects must cause rejection

The Flask provider must use a maintained X.509 implementation, such as
the Python cryptography library, to validate the DER certificate
structure. The dependency and supported version must be pinned and
reviewed before implementation.

The provider must reject:

- a missing or empty header
- invalid Base64url characters
- padding, whitespace or line breaks
- non-canonical Base64url encoding
- invalid or empty DER data
- malformed X.509 certificates
- trailing data or ambiguous certificate material
- DER certificates exceeding the configured size limit

The provider calculates the lowercase hexadecimal SHA-256 digest
directly from the validated DER bytes. It must never accept a
fingerprint supplied by the gateway or collector.

The certificate chain and certificate validity are validated by the
gateway. The gateway must require an explicit clientAuth extended
key usage (EKU) and digitalSignature key usage on collector leaf
certificates. Certificates without the required profile are rejected.

The application uses the validated leaf certificate bytes for
collector registration lookup. The backend-mTLS gateway
authentication is a separate trust check.

## 5. Proxy trust boundary

The backend must not be publicly reachable.

The deployment must ensure:

- only the designated gateway can reach the collector backend
- the gateway overwrites X-LUMS-Verified-Client-Cert on every request
- client-supplied copies of that header are discarded before forwarding
- the forwarded value contains unpadded Base64url-encoded DER only
- direct backend requests cannot authenticate using forged headers
- untrusted containers cannot join the trusted backend network
- the backend does not trust X-Forwarded-* headers without an explicit
  trusted-proxy configuration

The gateway-to-backend connection must use mutual TLS
(backend-mTLS).

The component that validates the collector TLS client certificate
must also generate and overwrite the internal certificate identity
header and establish the authenticated mTLS connection to the backend.

No untrusted intermediary may modify, replace or inject the internal
certificate identity header between collector certificate validation
and the Flask identity provider.

If the deployment uses multiple proxy or gateway components, the
trust-boundary design must explicitly identify:

- which component terminates collector TLS and validates the
  collector client certificate
- which component creates and overwrites the internal identity header
- which component authenticates to the backend using the designated
  gateway client certificate
- which network paths and intermediate components are trusted
- how header integrity is preserved across every intermediate hop

The component authenticating to the backend must be the designated
identity-trusted gateway, or a separately documented and tested
trusted component that receives the verified identity through an
integrity-protected channel.

A successful backend mTLS handshake alone does not prove that the
forwarded collector identity header was generated by the component
that validated the collector certificate.

The gateway must authenticate the Flask/Gunicorn backend using a
server certificate issued by a dedicated internal CA. The backend
server certificate must contain the serverAuth extended key usage
(EKU), and its SAN must match the configured backend DNS name.

The backend must authenticate the gateway using a gateway client
certificate issued by a dedicated gateway-client CA. This CA must
be reserved exclusively for the designated gateway identity and
must not issue certificates to unrelated services or containers.
This restriction must be enforced by CA issuance policy and access
controls, documented, and verified during deployment review.
The CA trust bundle must not contain unrelated issuing authorities
that could authenticate arbitrary internal clients as the gateway.
The gateway client certificate must contain the clientAuth EKU and
digitalSignature key usage.

### Certificate profiles and cryptographic policy

All end-entity certificates used for collector clients, the gateway
client and the backend server must explicitly contain
BasicConstraints with CA:FALSE. A CA certificate must contain
BasicConstraints with CA:TRUE and the keyCertSign key usage. A CA
that issues CRLs must additionally contain the cRLSign key usage.

The initial deployment cryptographic allowlist is:

- RSA public keys with a minimum modulus size of 3072 bits
- ECDSA public keys on NIST P-256 or P-384
- certificate signatures using SHA-256, SHA-384 or SHA-512
- TLS 1.2 or newer, with TLS 1.3 preferred where supported

The initial rollout must reject RSA keys below 3072 bits, DSA keys,
unsupported or weak elliptic curves, MD5 and SHA-1 certificate
signatures, and algorithms outside the explicitly configured
allowlist. Ed25519 is not part of the initial interoperability
profile and requires separate compatibility testing before adoption.

Every certificate profile must be checked against its intended
purpose:

- collector client leaf: CA:FALSE, clientAuth EKU and
  digitalSignature key usage
- gateway client leaf: CA:FALSE, clientAuth EKU and
  digitalSignature key usage; its identity is authorized by the
  dedicated gateway-client CA, which must issue certificates only
  to the designated gateway
- backend server leaf: CA:FALSE, serverAuth EKU and a DNS SAN
  matching the configured backend name

The collector identity remains the SHA-256 fingerprint of the
validated leaf DER certificate and is matched against the LUMS
collector registry. A collector SAN is not used as a substitute
for that registry identity.

The backend authorizes the gateway through the dedicated,
exclusive gateway-client CA trust boundary. The gateway certificate
SAN may be recorded for operational identification, but must not be
treated as independently verified by Gunicorn's standard
ssl.CERT_REQUIRED setting. If authorization by a specific gateway
SAN is required in a future deployment, it needs an additional
explicitly implemented and tested identity-verification mechanism.

Certificate-profile validation must reject CA:TRUE end-entity
certificates, missing or incorrect EKUs, missing required key usage,
weak keys, disallowed signature algorithms and backend DNS SAN
mismatches. These checks must be covered by automated negative tests.

Both sides must validate certificate chains and validity periods.
The backend must reject certificates that do not match the required
gateway-client certificate profile.

The gateway must verify the backend certificate identity against
the configured expected DNS name or Subject Alternative Name (SAN).
Trusting the issuing CA alone is insufficient.

The backend must require a valid gateway client certificate.
For the selected Gunicorn runtime, this requires explicit mandatory
client-certificate verification (ssl.CERT_REQUIRED). Merely
configuring a CA file is not sufficient.

Backend gateway-certificate revocation must be enforced through
Certificate Revocation Lists (CRLs). The Gunicorn SSL context must
load the trusted CA material and the applicable CRLs, and enable
OpenSSL CRL verification for the presented gateway certificate.
The exact verification scope must be documented and tested.

The backend must fail closed if the required CRL is missing,
unavailable, expired, invalid or cannot be used for verification.
A certificate for which no applicable revocation information can
be established must not be accepted.

The initial implementation supports direct CRLs issued and signed
by the CA that issued the gateway client certificate. Indirect CRLs
and delta CRLs are explicitly out of scope until separately designed
and tested.

The CRL verification must establish that:

- the CRL is issued by the CA that issued the gateway client
  certificate
- the CRL signature is valid
- the CRL issuer is authorized to issue revocation information
- the CRL issuer certificate has BasicConstraints with CA:TRUE
- the CRL issuer certificate has KeyUsage with cRLSign enabled
- the CRL issuer certificate is the applicable issuer of the
  gateway client certificate under the configured direct-CRL model
- the CRL signature is verified with that issuer certificate's
  public key, not with a key selected only by an untrusted CRL field
- the CRL contains a valid thisUpdate and nextUpdate value
- thisUpdate must not be in the future beyond the explicitly
  documented clock-skew allowance
- nextUpdate must not be expired
- the CRL age must not exceed the explicitly configured maximum age
- CRLs without nextUpdate must be rejected
- the presented gateway certificate serial number is checked
  against the applicable CRL
- the backend SSL context explicitly enables
  ssl.VERIFY_CRL_CHECK_LEAF in addition to ssl.CERT_REQUIRED
- the configured OpenSSL verification flags actually enforce
  revocation checking for the presented gateway client leaf certificate
- the implementation must not rely on ssl.CERT_REQUIRED alone for
  certificate revocation checking

CRL distribution, maximum age, clock-skew allowance, renewal,
deployment and activation must be documented before implementation.
The maximum age must be an explicit deployment setting and must not
be inferred solely from nextUpdate.

Before creating or activating the backend SSL context, a dedicated
CRL preflight validator must independently verify the CRL issuer,
signature, thisUpdate, nextUpdate, clock-skew allowance and configured
maximum age. The same validated CRL material must then be loaded into
the OpenSSL SSL context for handshake-time revocation checking.

A failed or incomplete preflight must prevent backend TLS startup.
The implementation must not assume that OpenSSL CRL verification
flags alone enforce the additional maximum-age policy.

### Backend PEM trust bundle and SSL context activation

The initial Python/Gunicorn implementation must use a controlled PEM
bundle containing the applicable gateway-client issuing CA certificate
and its corresponding direct CRL.

The implementation must:

- construct the PEM bundle from the exact CA certificate and CRL
  material that passed the independent preflight validation
- verify that the bundle contains the intended CA certificate and
  corresponding CRL, without unrelated trust anchors or CRLs
- stage the bundle in a restricted directory with permissions that
  prevent unprivileged modification
- pass the staged bundle to the backend SSL context through
  ssl.SSLContext.load_verify_locations(cafile=...)
- set ssl.CERT_REQUIRED
- explicitly enable ssl.VERIFY_CRL_CHECK_LEAF in the SSL context
- verify at startup that the resulting SSL context has the required
  verification mode and flags enabled
- fail startup if bundle loading, SSL context configuration or
  verification-flag validation fails

The implementation must verify the behavior of
load_verify_locations(cafile=...) with the exact Python and OpenSSL
versions selected for deployment. A successful bundle load alone
does not prove that CRL checking is active.

The SSL context must use the exact staged CA and CRL bytes that passed
preflight. The staged bundle must not be replaced or modified while
an active SSL context depends on it.

For trust or CRL rotation, the implementation must validate and stage
a new bundle separately, create and validate a new SSL context, and
activate it through a controlled restart or supported context-reload
procedure. A failed update must leave the service unable to accept
connections with stale or unvalidated revocation material. The
activation procedure must be tested with real TLS handshakes.

Trust-store or CRL updates must not be assumed to take effect in
already-created SSL contexts.
The deployment must provide a controlled reload or restart
procedure and verify that the new material is active.

OCSP is not part of the initial backend-mTLS requirement.
It may be evaluated separately for the gateway if the selected
gateway implementation supports it with suitable fail-closed
behavior.

Collector certificate revocation is additionally enforced by the
application registry on every ingestion request. Gateway TLS
validation alone does not replace the application-level revocation
check.

The gateway must not silently continue with stale trust or
revocation data beyond the explicitly documented validity policy.

The exact certificate provisioning, rotation and trust-store
management must be documented and tested.

The backend listener must not be published on a host interface.
Network isolation must additionally restrict backend reachability
to the designated gateway.

A shared Docker network alone must not be assumed to provide
sufficient isolation if unrelated containers can join it.

X-LUMS-Verified-Client-Cert is trusted only after the backend TLS
layer has authenticated the gateway connection. The gateway must
remove any incoming client-supplied copy and overwrite the header
for every forwarded request. Flask must not treat the header as
authenticated identity if the backend-mTLS boundary is absent.

The implementation must use an explicit Gunicorn SSL context
configuration. It must set ssl.CERT_REQUIRED, load the dedicated
gateway-client CA trust material and applicable CRLs, and enable
the required OpenSSL CRL verification flags.

The backend TLS listener must:

- accept TLS connections only; no parallel plaintext HTTP listener
- bind only to the private backend interface or an equivalent
  non-public internal endpoint
- require TLS 1.2 or newer
- prefer TLS 1.3 where supported by the selected runtime
- present the configured backend server certificate and private key

The gateway must validate the backend certificate chain and expected
DNS SAN. Hostname verification must be enabled, not merely inferred
from successful CA validation.

No assumption about a configuration option is sufficient without
a real TLS integration test. The test must demonstrate successful
handshake with the designated gateway certificate and rejection
of missing, untrusted, expired and revoked gateway client certificates.

## 6. TLS gateway requirements

### Gateway implementation decision

Envoy has been selected as the gateway product for the target
architecture. The exact Envoy release and immutable image digest
have not yet been pinned. This selection does not authorize pulling
an image, creating a container or changing an existing deployment.

Envoy will terminate collector-facing TLS and act as the data-plane
gateway. A separate LUMS Control Plane container will manage dynamic
configuration and secret delivery through xDS/SDS over the dedicated
internal control network.

The initial deployment design keeps the following components
separate:

- Envoy gateway container
- LUMS Control Plane container
- Existing Flask/Gunicorn backend container

The Envoy-to-backend connection must use the separately defined
backend-mTLS trust boundary. The Envoy-to-Control-Plane connection
must use an authenticated and protected xDS/SDS channel. The Control
Plane must not be attached to the backend network or gain direct
backend access.

The following items remain implementation blockers and must be
verified before implementation phase 3:

- the exact Envoy release and immutable image digest
- Envoy support for the required collector certificate profile,
  CRL validation, freshness limits and fail-closed admission behavior
- the exact xDS/SDS resource model and authenticated transport
- Control Plane implementation language, libraries and pinned versions
- configuration acknowledgement, rejection and recovery behavior
- how CRL preflight and activation use exactly the same material
- how failed CRL updates preserve a valid active CRL without allowing
  expired or stale revocation information
- how the gateway atomically activates validated CRL material
- how client-supplied identity headers are removed and the verified
  certificate is forwarded
- how gateway-to-backend mTLS and backend hostname verification work
- how request and header size limits, access restrictions and safe
  logging are configured
- which properties are verified by automated tests and which require
  real TLS integration tests

The Control Plane must not be treated as a substitute for enforcement
at the TLS listener. If Envoy's supported CRL and TLS configuration
mechanisms cannot satisfy the required admission and freshness
semantics, the design must identify and test an additional enforcement
mechanism before implementation.

The gateway configuration must:

- require a client certificate
- validate the certificate against the configured CA
- reject expired and untrusted certificates
- enforce PKI revocation checking for collector client certificates
- use the applicable issuing CA's CRL for the initial rollout
- validate CRL issuer, signature, validity interval and configured
  maximum age before accepting collector certificates
- fail closed if required collector CRL material is missing, stale,
  invalid or unavailable
- must not treat the LUMS collector registry as a replacement for
  certificate-authority revocation checking
- require TLS 1.2 or newer and prefer TLS 1.3 where supported
- use a documented cipher and protocol policy
- validate the backend DNS SAN during backend TLS connection setup
- forward only the verified leaf certificate
- overwrite the internal identity header
- enforce request-body and request-header size limits
- allow at least 24 KiB for the complete internal certificate header
- reject oversized header fields without truncation
- avoid logging private keys or complete certificate contents
- expose only the intended collector endpoint

The gateway must not use an SHA-1 fingerprint as the collector identity.

Collector-side and backend-side certificate revocation are separate
trust domains:

- collector CRLs are used by the gateway to validate incoming
  collector client certificates
- gateway-client CRLs are used by the backend to validate the
  gateway's client certificate
- each CRL must be validated against the applicable issuing CA
  certificate for that trust domain
- CA certificates, CRLs and trust bundles must never be implicitly
  shared between these two trust domains
- rotation, renewal, freshness limits and failure handling must be
  configured and tested independently

The collector-side CRL policy must enforce the same issuer,
signature, CA:TRUE, cRLSign, thisUpdate, nextUpdate, clock-skew
and maximum-age requirements defined for backend-side CRL
validation, applied to the collector certificate's actual issuer.

Before accepting collector TLS connections, the gateway must
validate the applicable collector CRL independently of the backend
CRL preflight.

The gateway CRL preflight must verify:

- the CRL belongs to the actual issuing CA of the collector
  certificate
- the issuer certificate has BasicConstraints CA:TRUE
- the issuer certificate has KeyUsage with cRLSign enabled
- the CRL signature is valid for that issuer certificate
- thisUpdate and nextUpdate are present and valid
- clock-skew and configured maximum-age limits are respected
- the CRL material activated for TLS verification is exactly the
  material that passed preflight

A failed or incomplete collector CRL preflight must prevent the
gateway from accepting collector TLS connections. CRL updates must
use a controlled activation or reload procedure. The gateway must
not continue accepting certificates with stale revocation data
after a failed update.

The gateway must verify the collector certificate serial number
against the applicable collector CRL before forwarding the request.

### CRL activation and failed-update behavior

The following activation policy applies independently to collector-side
and backend-side CRL trust domains:

- initial startup must fail closed if no applicable CRL has passed
  preflight and been activated
- a candidate CRL or trust bundle must never replace the active material
  before all preflight checks and TLS-context or gateway activation checks
  have succeeded
- a failed candidate update must not invalidate an otherwise valid active
  CRL automatically
- the active CRL may remain in use after a failed candidate update only
  while its signature, issuer, thisUpdate, nextUpdate, clock-skew allowance
  and configured maximum age remain valid
- once the active CRL expires, exceeds its maximum age, becomes unavailable
  or can no longer be verified, the component must reject new TLS
  connections rather than continue with stale revocation information
- if the component cannot establish whether its active CRL is still valid,
  it must fail closed
- the active CRL must be revalidated periodically during operation;
  startup validation alone is insufficient
- the revalidation interval must be an explicit deployment setting,
  bounded and shorter than the remaining validity safety margin
- revalidation must check the active CRL's issuer, signature,
  thisUpdate, nextUpdate, clock-skew allowance and configured maximum age
- the component must ensure that the result of revalidation controls
  acceptance of new TLS connections; a background check that can fail
  without closing the acceptance path is insufficient
- if revalidation fails, the component must stop accepting new TLS
  connections until valid CRL material has passed preflight and has
  been activated
- a temporary failure of the CRL distribution source does not by itself
  invalidate a locally staged active CRL; that material may remain active
  only while its own signature, issuer and validity limits continue
  to pass revalidation
- the component must alert on distribution failures and on approaching
  CRL expiration or maximum-age limits
- successful activation must replace the active material atomically or
  through an equivalently controlled mechanism
- logs and monitoring must distinguish candidate-update failure from
  expiration or invalidation of the currently active CRL

The gateway and backend must apply this policy independently. A valid
backend CRL must not compensate for an invalid collector CRL, or vice versa.

### TLS admission state machine: CRL and trusted time

The gateway-side collector CRL and backend-side gateway-client CRL use
independent state machines. Their states, active CRL material, validation
results, activation and recovery must never be shared implicitly.

Each component must enforce its state machine at the TLS admission point.
A background validation task alone is insufficient if the TLS listener can
continue accepting new handshakes with invalid or expired revocation data.

#### States

| State | Meaning | New TLS handshakes |
|---|---|---|
| `READY` | Active CRL passed validation, remains within its validity and configured maximum-age limits, and trusted time is currently verified. | Allowed, subject to all other TLS checks. |
| `UPDATE_PENDING` | A candidate CRL is being retrieved or validated. The active CRL remains valid and trusted time remains verified. | Allowed using only the active CRL. |
| `BLOCKED` | No usable active CRL exists, CRL validity cannot be established, or trusted time is unavailable, stale, unverified or otherwise unusable. | Rejected. |
| `RECOVERY` | Candidate CRL passed preflight and is being activated and verified; trusted time must also pass fresh validation. | Rejected until CRL activation, trusted-time validation and required TLS verification succeed. |

#### Required transitions

- Initial startup enters `BLOCKED`. The component must not admit TLS
  handshakes until a valid CRL has passed preflight, has been activated,
  trusted time has been freshly validated, and the configured TLS
  verification has succeeded.
- `READY` enters `UPDATE_PENDING` when a CRL update is attempted.
- `UPDATE_PENDING` returns to `READY` if the candidate update fails,
  the active CRL remains valid and passes revalidation, and a fresh
  trusted-time check confirms that the time requirements are still met.
- `UPDATE_PENDING` enters `BLOCKED` immediately when the active CRL becomes
  invalid, expires, exceeds its configured maximum age, or can no longer be
  verified, or when trusted time becomes unavailable or untrustworthy.
- `UPDATE_PENDING` enters `RECOVERY` only after the candidate CRL has passed
  the complete preflight validation and is ready for activation.
- `RECOVERY` enters `READY` only after the new CRL material has been activated,
  trusted time has passed fresh validation, and the required TLS verification
  succeeds.
- Any CRL activation, trusted-time validation, context creation, listener
  reload, handshake verification or recovery failure enters `BLOCKED`.
- Loss of trusted-time status in `READY` or `UPDATE_PENDING` immediately
  enters `BLOCKED`; a previously valid CRL does not preserve admission
  when time can no longer be trusted.
- `BLOCKED` remains in effect until a valid candidate has passed preflight,
  activation, fresh trusted-time validation and TLS verification. A failed
  attempt must never silently restore admission.
- A failed candidate update must not replace or corrupt a still-valid active
  CRL. The component may continue using that active CRL only while it remains
  valid and passes revalidation.

#### TLS admission and existing connections

The implementation must distinguish between:

1. admission of new TLS connections and client-certificate handshakes; and
2. connections that were already established before a state transition.

In `BLOCKED` and `RECOVERY`, no new TLS handshake may be accepted. This must
be enforced by the actual gateway or backend TLS listener, not merely by
reporting an unhealthy status.

The implementation must document and test its policy for already-established
connections. It must not imply that updating a CRL automatically revalidates
or terminates an existing TLS session. If established connections are drained
or terminated, the mechanism and maximum drain period must be documented.
If they remain open temporarily, that behavior and its security implications
must be documented as well.

#### Admission deadline and recovery verification

The CRL validity policy must be enforced at the TLS admission boundary.
Periodic background revalidation alone is insufficient because a CRL may
expire or exceed its configured maximum age between two scheduled checks.

The implementation must:

- calculate the earliest admission deadline from nextUpdate, the configured
  maximum CRL age, and the documented clock-skew and safety-margin policy
- ensure that new TLS handshakes are blocked before that deadline is reached
- prevent a delayed or failed revalidation task from leaving TLS admission
  enabled beyond the calculated deadline
- re-evaluate the active CRL validity when changing admission state
- fail closed if the system cannot establish trustworthy time or determine
  whether the active CRL remains within its validity limits
- document how clock changes, clock rollback and time synchronization
  failures affect the admission decision

The implementation must combine trusted UTC wall-clock validation with
a monotonic runtime deadline:

- at successful CRL validation, record the trusted UTC validation time
  and the corresponding monotonic clock value
- calculate the remaining validity duration using the earliest applicable
  limit: nextUpdate, configured maximum CRL age and the documented
  safety margin
- derive a monotonic admission deadline from that remaining duration
- never extend an established monotonic admission deadline because the
  system wall clock moves backwards
- if wall-clock and monotonic-clock observations become inconsistent beyond
  the documented tolerance, or trustworthy time cannot be established,
  transition to BLOCKED
- a forward wall-clock correction that makes the CRL invalid or expired
  must cause immediate re-evaluation and must never extend admission
- after process restart, do not reuse a previously calculated monotonic
  deadline; validate the CRL again against trustworthy time before enabling
  the TLS listener

The monotonic deadline supplements, but does not replace, validation of
the CRL issuer, signature, thisUpdate, nextUpdate and configured maximum age.

#### Trusted time requirements

The deployment must define an explicit trusted-time contract for both
the gateway and backend. A generic operating-system synchronization flag
alone is not sufficient evidence that the current UTC time is trustworthy.

The time provider or monitoring interface must expose enough information
to evaluate:

- whether synchronization with an explicitly approved time source is active
- the identity of the selected time source
- the time of the last successful synchronization
- the estimated clock offset or uncertainty
- whether the configured maximum synchronization age is exceeded
- whether the estimated offset or uncertainty exceeds the configured limit

The deployment must document its approved time sources, synchronization
mechanism, maximum synchronization age, maximum accepted offset or
uncertainty and failure behavior. These values must be explicit configuration,
not implicit software defaults.

The age of the last successful time synchronization must also be
protected against wall-clock rollback:

- record the monotonic clock value when a successful synchronization
  is confirmed
- calculate synchronization age using monotonic elapsed time, not only
  the difference between two UTC timestamps
- a wall-clock rollback must never make an old synchronization appear fresh
- after process or system restart, require a fresh successful time
  synchronization before enabling the normal TLS listener
- if the monotonic reference is unavailable or cannot be trusted, treat
  synchronization freshness as unknown and transition to `BLOCKED`

The component must transition to `BLOCKED` when:

- no approved time source can be verified
- synchronization status is unavailable or reports unsynchronized
- the last successful synchronization is older than the configured limit
- estimated offset or uncertainty exceeds the configured limit
- the time provider returns incomplete, contradictory or invalid status

Recovery requires a fresh successful time validation and a fresh CRL
validation before the normal TLS listener can return to `READY`.

Gateway and backend time validation must be independent. A valid time status
on one component does not establish trustworthy time on the other.


The gateway and backend must enforce these deadlines independently.


Recovery verification must not require temporarily exposing the normal
collector-facing or backend-facing listener to unverified connections.

The implementation must provide a staging or otherwise isolated verification
path that:

- uses the exact candidate CA and CRL material intended for activation
- uses the same TLS verification settings as the intended active listener
- is not reachable through the normal application or collector network path
- performs a real TLS handshake with the expected valid peer certificate
- verifies rejection of a revoked or otherwise invalid peer certificate
- confirms that the intended certificate and CRL material is active

Only after this verification succeeds may the component transition from
`RECOVERY` to `READY` and admit new connections on its normal listener.

The staging verification path must not create a temporary bypass around
client-certificate verification, CRL checking or network restrictions.

#### Component-specific enforcement

The gateway must enforce its own state machine against the collector-side
PKI CRL. Its chosen implementation must provide a tested mechanism to stop
admitting new collector TLS handshakes while `BLOCKED` or `RECOVERY`, and to
resume admission only after successful recovery.

The backend must enforce its own state machine against the gateway-client CRL.
The selected Python/OpenSSL/Gunicorn deployment must provide a tested way to
prevent new backend TLS handshakes while `BLOCKED` or `RECOVERY`. If a new
SSL context cannot be activated safely at runtime, a controlled listener
restart or equivalent mechanism is required. The listener must not become
available before the validated context is active.

The gateway and backend must report their states independently. A healthy
gateway CRL state does not compensate for an invalid backend CRL, and vice
versa.

#### Required state-transition integration tests

Run the following tests independently for the gateway collector CRL and the
backend gateway-client CRL:

- Startup without a CRL, with a missing CRL, or with an invalid CRL remains
  `BLOCKED`; a real TLS handshake is rejected.
- A valid CRL can be activated and verified, trusted time passes fresh
  validation, and the component reaches `READY`; a real valid handshake
  succeeds only after both conditions are satisfied.
- Starting a candidate update enters `UPDATE_PENDING` while the active CRL
  remains valid; new handshakes continue to use only the active CRL.
- A malformed, incorrectly signed, unauthorized, stale or otherwise invalid
  candidate does not replace the active CRL.
- If the candidate fails while the active CRL remains valid and trusted
  time passes a fresh validation, the component returns to or remains in
  `READY`. If trusted time cannot be verified, the component enters
  `BLOCKED` instead.
- If the active CRL expires or exceeds the configured maximum age during an
  update failure, the component enters `BLOCKED` and a new real TLS handshake
  is rejected.
- A valid candidate enters `RECOVERY`; new handshakes remain blocked until
  activation, fresh trusted-time validation and TLS verification have
  completed.
- Successful activation, fresh trusted-time validation and TLS
  verification transition to `READY`; a real handshake using the newly
  active trust and CRL material succeeds only after all three succeed.
- Activation, SSL-context creation, reload, restart or verification failure
  transitions to `BLOCKED`; new handshakes remain rejected.
- A restart with missing, invalid, expired or stale active CRL does not
  briefly expose a TLS listener that accepts new connections.
- Tests verify the documented behavior of already-established connections
  separately from new handshakes.
- Tests verify that the admission deadline is calculated from nextUpdate,
  configured maximum age and the documented safety margin.
- Tests verify that new TLS handshakes are rejected before the admission
  deadline, including when periodic revalidation is delayed or fails.
- Tests verify fail-closed behavior after clock rollback, unavailable
  trustworthy time or an invalid time-synchronization state.
- Tests verify that an unapproved or unverifiable time source causes
  `BLOCKED` independently on gateway and backend.
- Tests verify that unavailable or unsynchronized time-provider status
  causes `BLOCKED`.
- Tests verify that an excessively old last-successful synchronization
  causes `BLOCKED`.
- Tests verify that clock offset or uncertainty above the configured
  threshold causes `BLOCKED`.
- Tests verify that incomplete, contradictory or invalid time-provider
  status causes `BLOCKED`.
- Tests verify that gateway and backend evaluate their time status
  independently and cannot inherit each other's `READY` state.
- Tests verify that a wall-clock rollback cannot extend the monotonic
  admission deadline.
- Tests verify that a forward wall-clock correction causing CRL expiry
  blocks new TLS handshakes immediately.
- Tests verify that inconsistent wall-clock and monotonic-clock observations
  beyond the configured tolerance cause fail-closed behavior.
- Tests verify that process restart requires fresh CRL validation and does
  not reuse a previous process's monotonic deadline.
- Tests verify that wall-clock rollback cannot make an old time
  synchronization appear fresh.
- Tests verify that synchronization freshness is measured using monotonic
  elapsed time.
- Tests verify that process or system restart requires fresh successful
  time synchronization before TLS admission resumes.
- Tests verify that an unavailable monotonic reference causes `BLOCKED`.
- Tests verify that the isolated recovery path uses the exact candidate
  CA and CRL material and the same TLS verification settings as the
  intended active listener.
- The isolated recovery path accepts a valid peer certificate and rejects
  a revoked or otherwise invalid peer certificate.
- Tests verify that the normal listener remains blocked while recovery
  verification is pending or unsuccessful.
- Tests verify that successful recovery verification activates the intended
  material before the normal listener accepts new TLS handshakes.
- State reporting and logs distinguish candidate-update failure, active-CRL
  invalidation, blocked admission and successful recovery without logging
  private keys, certificate contents or sensitive request data.

The tests must exercise the actual selected gateway product and version and
the actual backend Python/OpenSSL/Gunicorn combination. Unit tests of the
state-transition logic alone are not sufficient.

## 7. Flask requirements

The Flask identity provider must:

- be disabled unless explicitly configured
- accept certificate material only across the trusted proxy boundary
- never fall back to request-body or arbitrary client headers
- calculate the SHA-256 fingerprint from DER bytes
- fail closed on every parsing or trust-boundary error
- return no certificate contents in error responses or logs

The existing collector feature gate remains fail-closed.

## 8. Required security tests

### Identity provider

- provider missing
- provider raises an exception
- certificate missing
- missing certificate header
- invalid Base64url alphabet or padding
- whitespace and line breaks
- non-canonical Base64url encoding
- empty or malformed DER
- malformed X.509 certificate
- trailing DER data or ambiguous certificate material
- DER re-serialization differs byte-for-byte from the original input
- certificate exceeding the configured size limit
- gateway rejects an oversized certificate header
- no intermediary truncates or rewrites the certificate header
- valid leaf certificate produces the expected SHA-256
- fingerprint is calculated from DER bytes, never supplied by a header
- no fallback to a client-supplied fingerprint

### Proxy boundary

- direct backend request with forged identity header is rejected
- client-supplied identity header is overwritten by the gateway
- missing client certificate is rejected
- untrusted client certificate is rejected
- expired client certificate is rejected
- client certificate without the required clientAuth EKU is rejected
- client certificate without the required digitalSignature key usage
  is rejected
- valid registered certificate is accepted
- a PKI-revoked collector certificate is rejected by the gateway
  even if its LUMS registry entry is still active
- collector CRL preflight rejects an unauthorized issuer, invalid
  signature, missing nextUpdate, expired CRL and excessive age
- gateway startup or activation is blocked when collector CRL
  preflight fails
- the gateway activates exactly the CRL material that passed preflight
- missing, stale, invalid or unavailable collector CRL material
  causes the gateway to fail closed
- a PKI-valid certificate whose LUMS registry entry is revoked
  is rejected by the application

### Collector API

- collector feature disabled by default
- unknown certificate is rejected
- revoked collector is rejected
- valid event batch is accepted
- duplicate batch is idempotent
- conflicting event ID returns conflict
- invalid batch is not partially persisted
- oversized request is rejected

## 9. Integration and operational validation

Before the first controlled rollout:

- test with a real test CA and generated test certificates
- test gateway and Flask together
- verify direct backend access is blocked
- verify collector certificate rotation without losing auditability
- verify that a CA-revoked collector certificate is rejected by the
  gateway even when its application registry entry remains active
- verify that an administratively revoked collector registry entry
  is rejected on the next ingestion request, including after
  application restart
- verify that missing or stale collector CRL material prevents
  gateway acceptance
- verify a collector CRL signed by an unauthorized issuer is rejected
- verify a collector CRL issuer certificate without CA:TRUE is rejected
- verify a collector CRL issuer certificate without cRLSign KeyUsage
  is rejected
- verify the collector CRL signature against the actual issuing CA
  certificate
- verify an invalid collector CRL signature is rejected
- verify a collector CRL without nextUpdate is rejected
- verify an expired collector CRL is rejected
- verify a collector CRL exceeding the configured maximum age is rejected
- verify a collector CRL with a future thisUpdate beyond allowed
  clock skew is rejected
- verify a collector certificate listed as revoked is rejected
  before the request reaches Flask
- verify gateway startup or CRL activation fails when collector
  CRL preflight fails
- verify the gateway activates exactly the collector CRL material
  that passed preflight
- verify a failed CRL reload cannot leave the gateway accepting
  collector certificates with stale revocation data
- verify successful collector CRL rotation and controlled activation
- verify collector admission is blocked before nextUpdate or the
  configured maximum-age deadline, including delayed revalidation
- verify collector admission fails closed after clock rollback or
  loss of trustworthy system time
- verify collector admission fails closed for an unapproved time source,
  unsynchronized status or unavailable time-provider data
- verify collector admission fails closed when last synchronization
  exceeds the configured maximum age
- verify collector admission fails closed when offset or uncertainty
  exceeds the configured threshold
- verify incomplete or contradictory collector time status is rejected
- verify collector synchronization age is measured using monotonic time
- verify collector clock rollback cannot make an old synchronization fresh
- verify collector process or system restart requires fresh time synchronization
- verify unavailable collector monotonic reference causes fail-closed admission
- verify collector recovery through an isolated staging TLS path
  using the exact candidate CRL and trust material
- verify the staging path accepts a valid collector certificate and
  rejects a revoked collector certificate
- verify the normal collector listener remains blocked until staging
  verification succeeds
- verify backend admission is blocked before nextUpdate or the
  configured maximum-age deadline, including delayed revalidation
- verify backend admission fails closed after clock rollback or
  loss of trustworthy system time
- verify backend admission fails closed for an unapproved time source,
  unsynchronized status or unavailable time-provider data
- verify backend admission fails closed when last synchronization
  exceeds the configured maximum age
- verify backend admission fails closed when offset or uncertainty
  exceeds the configured threshold
- verify incomplete or contradictory backend time status is rejected
- verify backend synchronization age is measured using monotonic time
- verify backend clock rollback cannot make an old synchronization fresh
- verify backend process or system restart requires fresh time synchronization
- verify unavailable backend monotonic reference causes fail-closed admission
- verify backend recovery through an isolated staging TLS path
  using the exact candidate CRL and trust material
- verify the staging path accepts the designated gateway certificate
  and rejects a revoked gateway certificate
- verify the normal backend listener remains blocked until staging
  verification succeeds
- verify gateway client-certificate rotation with an explicitly
  documented overlap period and removal of the old backend trust material
- verify backend server certificate rotation and hostname validation
- verify that expired certificates are rejected
- verify that collector certificates without the required EKU or
  key usage are rejected
- verify that PKI-revoked gateway client certificates are rejected by the backend
- verify that unrelated certificates cannot authenticate as the
  backend gateway
- verify backend certificate hostname/SAN mismatch is rejected
- verify backend gateway-client CRL checking fails closed
- verify a backend gateway-client CRL signed by an unauthorized issuer is rejected
- verify a backend CRL issuer certificate without CA:TRUE is rejected
- verify a backend CRL issuer certificate without cRLSign KeyUsage is rejected
- verify a backend CRL signature is checked against the applicable issuer
  certificate, not an unrelated certificate
- verify an invalid backend gateway-client CRL signature is rejected
- verify a backend gateway-client CRL outside its validity interval is rejected
- verify a backend gateway-client CRL without nextUpdate is rejected
- verify a backend gateway-client CRL exceeding the configured maximum age is rejected
- verify a backend gateway-client CRL with a future thisUpdate beyond allowed clock skew
  is rejected
- verify backend startup is blocked when CRL preflight fails
- verify the SSL context uses the same CRL material that passed preflight
- verify a PKI-revoked gateway client certificate is rejected by the backend
- verify the backend SSL context has ssl.VERIFY_CRL_CHECK_LEAF enabled
  together with ssl.CERT_REQUIRED
- verify a real TLS handshake rejects a gateway client leaf certificate
  whose serial number is listed in the applicable CRL
- verify a valid, non-revoked gateway client certificate completes the
  TLS handshake successfully
- verify a gateway client certificate without applicable backend CRL information is rejected
- verify stale or unavailable backend gateway-client CRL data is handled as documented
- verify that trust-store changes take effect as documented
- verify gateway and application restart behavior
- verify logs do not expose private key material or certificate contents
- verify database integrity and event persistence
- document backup and rollback procedures

All tests must use newly created isolated test resources.

Production containers, production databases and existing test
containers must remain untouched until separately approved.

## 10. Implementation phases

1. Finalize this security specification and trust-boundary design.
2. Add and pin the reviewed X.509 parsing dependency, then implement
   and unit-test the strict Base64url-DER certificate identity provider.
3. Implement the isolated mTLS gateway configuration.
4. Add proxy-boundary and certificate integration tests.
5. Run isolated end-to-end and failure/restart tests.
6. Review deployment, monitoring, backup and rollback readiness.

## 11. Explicit non-goals

This document does not authorize:

- production deployment
- production database migration
- production worker startup
- enabling the collector API in production
- modification or replacement of existing test containers
- bypassing updater or container replacement safeguards

Each deployment stage requires separate validation and approval.
