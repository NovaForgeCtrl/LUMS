# LUMS — Security Documentation

> **Linux Update Management without the noise.**

> **Security is part of the system — not an optional feature.**

---

# Part 1 — Foundations, Architecture, Security Status, Docker & Container

## 1. Security Philosophy

LUMS is designed as a centralized Linux update management system for small infrastructure environments, laboratories, and test networks.

The security model follows a simple principle:

```text
Minimize trust.
Limit privileges.
Validate input.
Protect credentials.
Record security-relevant actions.
Recover safely.
Keep the architecture understandable.
```

Security mechanisms are implemented as part of the application architecture rather than being treated as an additional layer around the application.

The current security model covers:

* Web authentication.
* Session management.
* CSRF protection.
* API authentication.
* Per-client authentication tokens.
* Token hashing.
* Token rotation.
* Audit logging.
* SQLite integrity protection.
* SQLite concurrency handling.
* Update execution timeouts.
* Job ownership and atomic claiming.
* Running-job recovery.
* Idle-state enforcement.
* Container hardening.
* Secret isolation.
* HTTPS termination.
* Input validation.
* Package validation.
* Controlled update execution.

---

# 2. Security Scope

The security architecture protects the following components:

```text
Browser
   │
   ▼
Nginx / HTTPS
   │
   ▼
LUMS Web Application
   │
   ├── Authentication
   ├── Sessions
   ├── CSRF
   ├── API
   ├── Client Management
   ├── Update Jobs
   ├── Audit Logging
   │
   ▼
SQLite Database
   │
   ▼
LUMS Agent
   │
   ▼
Linux Client
```

The security boundary also includes the Docker runtime:

```text
Host
 │
 ├── Nginx
 ├── LUMS configuration
 ├── LUMS secrets
 │
 └── Docker
      │
      └── LUMS container
           │
           └── Application
```

Persistent application data and secrets are intentionally kept outside the Git repository.

---

# 3. Current Security Architecture

The current production architecture is:

```text
                         HTTPS
                           │
                           ▼
                    ┌─────────────┐
                    │    Nginx    │
                    │    :443     │
                    └──────┬──────┘
                           │
                           │ localhost
                           ▼
                    ┌─────────────┐
                    │ 127.0.0.1   │
                    │    :5050    │
                    └──────┬──────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │   Docker: lums    │
                 │                   │
                 │   Flask/Gunicorn  │
                 │       :5000       │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │   lums-data       │
                 │   SQLite DB       │
                 └───────────────────┘
```

The application port is not directly exposed to the network.

The Docker port mapping is:

```text
127.0.0.1:5050 → 5000/tcp
```

Port `5000` is internal to the container.

Port `5050` is bound only to localhost.

External access is provided through Nginx over HTTPS.

---

# 4. Security Boundaries

LUMS separates the following trust domains:

```text
Internet / User Browser
        │
        ▼
      Nginx
        │
        ▼
   LUMS Application
        │
        ├── Database
        ├── Secrets
        └── Job State
        │
        ▼
     LUMS Agent
        │
        ▼
    Linux Client
```

A client agent is not trusted merely because it can reach the API.

Client requests require authentication through the client-specific Bearer token.

The server validates the authenticated client before accepting protected agent operations.

---

# 5. Security Status

The following security improvements have already been implemented and tested as part of the current security audit:

| Audit | Area                                 | Status   |
| ----- | ------------------------------------ | -------- |
| #1    | SQLite Foreign Keys / Client State   | Complete |
| #2    | SQLite WAL / Busy Timeout            | Complete |
| #3    | Update Timeout / Process Termination | Complete |
| #4    | Login Rate Limiting                  | Complete |

The completed audits are part of the current production codebase.

Further security work remains planned.

The project therefore considers security to be an ongoing engineering process rather than a finished state.

---

# 6. SQLite Foreign Key Protection

LUMS enables SQLite foreign key enforcement for application database connections.

The application uses:

```python
connection.execute("PRAGMA foreign_keys = ON")
```

This prevents invalid foreign-key relationships from being silently accepted by SQLite.

The database has also been checked using:

```text
PRAGMA foreign_key_check
```

The production database currently passes the foreign-key integrity check.

---

# 7. SQLite Concurrency Protection

LUMS uses SQLite WAL mode for improved read/write concurrency.

The database is configured with:

```text
journal_mode = WAL
busy_timeout = 5000
```

The application connections also configure:

```text
busy_timeout = 5000
```

The current runtime configuration has been verified as:

```text
journal_mode: wal
busy_timeout: 5000
synchronous: 2
foreign_keys: 1
```

WAL mode reduces unnecessary reader/writer blocking while the busy timeout gives SQLite time to wait for short-lived database locks.

---

# 8. Database Integrity

The production database is checked during security validation.

The current database contains application state including:

* Clients.
* Installed packages.
* Available updates.
* Update jobs.
* Update job packages.
* Update history.
* Login rate-limit state.
* Audit records.

Database integrity checks are performed before security changes are considered complete.

The database is persistent through the Docker volume:

```text
lums-data
```

The Docker volume must not be deleted during normal application deployment.

---

# 9. Container Security

The LUMS production container is intentionally hardened.

The container is configured to:

* Run as the dedicated non-root `lums` user.
* Use a read-only root filesystem.
* Drop all Linux capabilities.
* Disable privileged execution.
* Use a restricted `/tmp` tmpfs.
* Store persistent application data in a dedicated Docker volume.
* Receive the application secret through a read-only secret mount.
* Bind the application port only to localhost on the host.

The production container therefore does not require root privileges for normal operation.

---

# 10. Current Container Runtime

The production container is:

```text
lums
```

The image is:

```text
lums:latest
```

The persistent volume is:

```text
lums-data
```

The application listens internally on:

```text
0.0.0.0:5000
```

The host exposes it only through:

```text
127.0.0.1:5050
```

The external HTTPS interface is handled by Nginx.

---

# 11. Hardened Container Configuration

The current production container is created using:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --tmpfs /tmp:rw,nosuid,nodev,noexec \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -p 127.0.0.1:5050:5000 \
    lums:latest
```

This configuration intentionally avoids exposing the application directly to the network.

---

# 12. Read-Only Root Filesystem

The container uses:

```text
--read-only
```

This makes the container root filesystem read-only at runtime.

The application therefore cannot arbitrarily modify files throughout the container filesystem.

Writable runtime locations must be explicitly provided.

The current configuration provides:

```text
/tmp
```

through a restricted tmpfs and:

```text
/var/lib/lums
```

through the persistent Docker volume.

---

# 13. Linux Capability Restrictions

The container uses:

```text
--cap-drop=ALL
```

The LUMS application does not require elevated Linux capabilities for normal operation.

Dropping all capabilities reduces the privileges available to the application if the process or one of its dependencies is compromised.

The container is also not run in privileged mode.

---

# 14. Restricted Temporary Storage

The container uses:

```text
--tmpfs /tmp:rw,nosuid,nodev,noexec
```

This provides temporary writable storage while applying additional restrictions:

```text
rw
nosuid
nodev
noexec
```

The application can use `/tmp` for temporary runtime data without requiring a writable container root filesystem.

---

# 15. Persistent Application Data

Persistent LUMS application data is stored in:

```text
lums-data
```

mounted into the container as:

```text
/var/lib/lums
```

The SQLite database is therefore independent from the lifecycle of the application container.

Recreating the container does not recreate the database.

The following operation is therefore safe during a normal frontend or application deployment:

```text
Stop container
      ↓
Remove container
      ↓
Recreate container
      ↓
Mount existing lums-data volume
```

The volume itself must not be removed.

---

# 16. Secret Handling

The LUMS application secret is not stored directly in the Git repository.

The runtime secret is supplied through:

```text
/etc/lums/secrets/lums_secret
```

The container receives it through a read-only mount:

```text
/etc/lums/secrets/lums_secret
    ↓
/run/secrets/lums_secret
```

The application is configured using:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

This keeps the secret separate from:

* Git source code.
* Docker image source.
* Application templates.
* Frontend assets.
* Persistent database contents.

---

# 17. Secret Permissions

The host-side secret file is treated as sensitive configuration.

It must not be committed to Git.

It must not be included in:

```text
README files
Documentation
Source code
Docker images
Database backups
```

The secret should remain readable only by the required privileged host context.

---

# 18. Docker Image and Runtime Separation

The LUMS deployment deliberately separates:

```text
Git source
      ≠
Docker image
      ≠
Running container
      ≠
Persistent database
      ≠
Secrets
```

The source repository contains the application code and frontend assets.

The Docker image contains the built application runtime.

The running container executes that image.

The Docker volume contains persistent application data.

The host-side secret contains sensitive cryptographic configuration.

This separation allows application updates without replacing persistent state.

---

# 19. Container Restart Policy

The production container uses:

```text
--restart unless-stopped
```

This allows Docker to automatically restart the application after an unexpected container termination or host restart.

The restart policy does not replace application-level monitoring or testing.

It is a recovery mechanism for the container runtime.

---

# 20. Application Runtime

The production application runs using Gunicorn.

The current runtime uses:

```text
Gunicorn 23.0.0
```

The application listens internally on:

```text
0.0.0.0:5000
```

The application is not intended to expose this port directly to external clients.

Nginx remains the external HTTPS entry point.

---

# 21. Security Headers

The LUMS web interface uses security-related HTTP response headers.

These headers are intended to reduce common browser-side attack surfaces and enforce the expected browser security policy.

The Content Security Policy is particularly important because it restricts which resources the browser may load or execute.

Frontend changes must therefore be tested against the active CSP.

Security headers must not be weakened merely to make frontend code easier to deploy.

---

# 22. Content Security Policy

The LUMS Content Security Policy restricts script and style sources.

The project should prefer:

```text
External stylesheet rules
External JavaScript
Scoped theme CSS
```

over inline JavaScript or inline style attributes.

For example, frontend code should not solve a CSP violation by adding:

```text
'unsafe-inline'
```

unless there is a documented security reason for doing so.

The preferred approach is to move presentation logic into the version-controlled frontend assets.

---

# 23. Frontend Security Boundary

LUMS themes are client-side presentation features.

Changing the selected theme must not modify:

* Authentication.
* Authorization.
* Client tokens.
* API permissions.
* Update jobs.
* Database state.
* Audit logging.
* Agent communication.

Theme-specific JavaScript must remain presentation-only.

A theme must never become a security boundary.

---

# 24. Current Security Model

The current LUMS security model can be summarized as:

```text
                HTTPS
                  │
                  ▼
             Nginx / TLS
                  │
                  ▼
          LUMS Web Application
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
   Authentication  API    CSRF
        │         │
        ▼         ▼
    Sessions    Tokens
        │         │
        └────┬────┘
             ▼
        Application
             │
      ┌──────┼──────┐
      ▼      ▼      ▼
   SQLite   Jobs   Audit
      │      │
      │      ▼
      │    Agent
      │      │
      │      ▼
      │   Linux Client
      │
      ▼
 Persistent Volume
```

The design intentionally combines multiple independent security controls rather than relying on a single mechanism.

---

# 25. Security Audit Philosophy

Every security change should follow the same workflow:

```text
Change
  ↓
Syntax Check
  ↓
Unit Test
  ↓
Debian Test
  ↓
Arch Test
  ↓
Integration Test
  ↓
Git Diff Review
  ↓
Commit
```

A security change is not considered complete merely because the modified code appears correct.

The existing Debian and Arch test environments are part of the validation process.

---

# 26. Current Production Status

The current LUMS installation has successfully been tested with:

```text
Debian 13
Arch Linux
```

The current agent version is:

```text
1.7.0
```

The system supports the current multi-distribution package-management abstraction for:

```text
APT / dpkg
pacman
```

Security changes are tested against both supported client environments.

---

# 27. Completed Security Audits

## Audit #1 — SQLite Foreign Keys / Client State

Status:

```text
COMPLETE
```

Implemented:

* SQLite foreign key enforcement.
* Foreign-key integrity verification.
* Safe client disabling.
* Token revocation timestamp handling.
* Preservation of historical client/job data.

---

## Audit #2 — SQLite WAL / Busy Timeout

Status:

```text
COMPLETE
```

Implemented:

* SQLite WAL mode.
* 5000 ms busy timeout.
* Foreign-key enforcement on connections.
* Matching initialization settings.
* Runtime verification.

---

## Audit #3 — Update Timeout / Process Termination

Status:

```text
COMPLETE
```

Implemented:

* Selector-driven subprocess output handling.
* Update execution timeout.
* Graceful termination.
* 10-second termination grace period.
* Kill fallback when termination fails.
* Cleanup after process termination.

This prevents a blocked subprocess output operation from defeating the intended execution timeout.

---

## Audit #4 — Login Rate Limiting

Status:

```text
COMPLETE
```

Implemented:

* Persistent login rate-limit state.
* Per-username/source keying.
* Progressive lock durations.
* Concurrency-safe failure recording.
* Successful-login reset.
* Audit logging for rate-limit events.

Current lock progression:

```text
5 failures  → 30 seconds
6 failures  → 60 seconds
7 failures  → 120 seconds
8+ failures → 300 seconds
```

The rate-limit state is stored in the:

```text
login_rate_limits
```

table.

---

# 28. Security Status Summary

Current completed security work:

```text
✓ SQLite Foreign Keys
✓ Client State Protection
✓ SQLite WAL
✓ SQLite Busy Timeout
✓ Update Execution Timeout
✓ Process Termination Fallback
✓ Login Rate Limiting
✓ Container Non-Root Execution
✓ Read-Only Container Root
✓ Linux Capability Drop
✓ Restricted Temporary Storage
✓ File-Based Application Secret
✓ HTTPS Reverse Proxy
✓ CSRF Protection
✓ Argon2 Password Hashing
✓ Client Bearer Authentication
✓ SHA-256 Token Digest Storage
✓ Token Rotation
✓ Audit Logging
✓ Atomic Job Claiming
✓ Running-Job Recovery
✓ Idle-Aware Update Execution
```

Further security improvements remain part of the project roadmap.

---

# 29. Security Principle

The LUMS security architecture follows one central rule:

> **Security controls should reduce risk without making the system impossible to understand or maintain.**

LUMS therefore favors explicit mechanisms:

```text
Least privilege
        +
Explicit authentication
        +
Explicit authorization
        +
Controlled execution
        +
Persistent audit records
        +
Safe recovery
        +
Validated input
        +
Reproducible deployment
```

The goal is not to create a theoretically perfect security system.

The goal is to build a system where security decisions are visible, testable, documented, and maintainable.

---

# 30. End of Part 1

Part 1 establishes the security foundation of LUMS:

```text
Architecture
    ↓
Trust boundaries
    ↓
Container security
    ↓
Secret handling
    ↓
Database protection
    ↓
Security headers
    ↓
Security audit status
```

The following sections continue with the application security layer:

```text
Authentication
Sessions
Rate Limiting
Client Tokens
Token Rotation
API Authentication
API Input Validation
```

**End of Part 1.**

# Part 2 — Authentication, Rate Limiting, Tokens, Sessions & API

## 31. Authentication Overview

LUMS separates human administrator authentication from machine-to-machine agent authentication.

The two authentication paths are:

```text
Human User
    │
    ▼
Web Login
    │
    ▼
Session
    │
    ▼
LUMS Web Interface
```

and:

```text
LUMS Agent
    │
    ▼
Bearer Token
    │
    ▼
LUMS API
```

These mechanisms serve different purposes and are intentionally kept separate.

Administrator authentication does not use client agent tokens.

Agent communication does not use administrator session cookies.

---

# 32. Administrator Authentication

Administrator access is provided through the LUMS web login interface.

The authentication flow is:

```text
Username
   +
Password
   │
   ▼
Credential Validation
   │
   ▼
Argon2 Password Verification
   │
   ▼
Session Creation
   │
   ▼
Authenticated Web Interface
```

Invalid credentials must not reveal whether the username exists.

The login endpoint returns a generic authentication error for invalid credentials.

---

# 33. Password Storage

LUMS does not store administrator passwords in plaintext.

Passwords are stored using Argon2 password hashing.

The application verifies passwords against the stored password hash during login.

The plaintext administrator password is therefore never required by the application after authentication.

Password hashes must never be included in:

* Logs.
* Audit records.
* API responses.
* Documentation.
* Git commits.
* Database exports intended for public distribution.

---

# 34. Generic Login Errors

Authentication failures intentionally use a generic message:

```text
Invalid username or password.
```

The application does not expose whether:

```text
The username does not exist
```

or:

```text
The password is incorrect
```

This reduces unnecessary user enumeration through the login interface.

The same principle applies to disabled or otherwise unavailable accounts where appropriate.

---

# 35. Login Rate Limiting

LUMS implements persistent login rate limiting.

The rate limiter protects the login endpoint against repeated authentication attempts.

Rate limiting is based on a normalized combination of:

```text
Username
+
Request source
```

The normalized key is generated from:

```python
normalized_username = (username or "").strip().casefold()
normalized_source = (source or "").strip()
```

The resulting key has the form:

```text
username|source
```

---

# 36. Login Rate-Limit Storage

Rate-limit state is stored in:

```text
login_rate_limits
```

The table contains:

```text
id
rate_limit_key
username
failed_attempts
first_failed_at
last_failed_at
locked_until
```

The table uses a unique index on:

```text
rate_limit_key
```

An additional index exists for:

```text
locked_until
```

The migration creating the table is:

```text
003-login-rate-limiting
```

The migration is idempotent and uses the same SQLite safety mechanisms as the application database connections.

---

# 37. Progressive Login Locking

LUMS uses progressive lock durations.

The current configuration is:

```text
5 failures  → 30 seconds
6 failures  → 60 seconds
7 failures  → 120 seconds
8+ failures → 300 seconds
```

Attempts below the first threshold are recorded but do not trigger a temporary lock.

Once the threshold is reached, the login endpoint rejects further attempts until the corresponding lock expires.

---

# 38. Login Rate-Limit Concurrency

Failure recording uses:

```text
BEGIN IMMEDIATE
```

to protect concurrent updates to the rate-limit state.

This is important because multiple simultaneous authentication attempts could otherwise race while updating the same rate-limit record.

The concurrency behavior has been explicitly tested.

A concurrent test using multiple threads was initially able to expose database locking and unique-constraint behavior.

The implementation was then adjusted to use an explicit immediate transaction.

The final concurrency test completed without errors.

---

# 39. Successful Login Reset

A successful login clears the corresponding rate-limit state.

The intended lifecycle is:

```text
Failed attempts
      │
      ▼
Rate-limit state
      │
      ▼
Successful authentication
      │
      ▼
Rate-limit entry removed
```

This prevents previous failed attempts from permanently affecting an otherwise successful authentication sequence.

---

# 40. Rate-Limit Audit Events

Rate-limit actions are recorded in the audit log.

Relevant events include:

```text
login.rate_limit
```

and rate-limit lock events.

The audit record identifies the security-relevant event without storing sensitive credentials.

Passwords and authentication tokens must never be written to audit records.

---

# 41. Login Rate-Limit Validation

The rate limiter has been tested for:

* Initial failed attempts.
* Progressive thresholds.
* Lock activation.
* Independent rate-limit keys.
* Successful reset.
* Concurrency.
* Rollback behavior.
* Production end-to-end login behavior.

Production validation also confirmed that a blocked request does not continue increasing the stored failed-attempt counter.

---

# 42. Session Authentication

After successful administrator authentication, LUMS creates an authenticated web session.

The browser subsequently uses the session for protected web-interface requests.

The architecture therefore separates:

```text
Password
    ↓
Authentication
    ↓
Session
    ↓
Protected Web Requests
```

The administrator password is not repeatedly transmitted for every authenticated web request.

---

# 43. Session Security

Session handling is part of the web application's security boundary.

Session cookies must be treated as authentication credentials.

They must therefore not be exposed through:

* Application logs.
* Debug output.
* Audit records.
* Screenshots intended for public documentation.
* Git repositories.
* Client-side application data.

The frontend theme system does not have access to or authority over the authentication session.

---

# 44. Session Revocation

Server-side session revocation is a planned security enhancement.

The current architecture supports authenticated sessions but does not yet provide a dedicated server-side revocation mechanism for every already-issued session.

This means session invalidation behavior is currently governed by the existing session lifecycle and configured expiration behavior.

The future security enhancement is:

```text
Session
   │
   ▼
Server-side session state
   │
   ├── Active
   ├── Revoked
   └── Expired
```

The revocation mechanism must be implemented without weakening the existing authentication flow.

---

# 45. Session Lifetime

The configured session lifetime must be treated as part of the application's authentication policy.

Session lifetime should be reviewed together with:

* Session cookie configuration.
* Logout behavior.
* Server-side session revocation.
* Password changes.
* Account disabling.
* Security incidents.

Documentation should reflect the actual configured value rather than assuming a default framework value.

---

# 46. Logout

Administrator logout terminates the active web session.

The logout action is performed through a protected POST request.

The frontend uses:

```html
<form action="/logout" method="POST">
```

The logout request includes the application's CSRF token.

Logout must not be implemented as an unauthenticated GET request.

---

# 47. CSRF Protection

LUMS uses CSRF protection for state-changing browser requests.

The protection is particularly important for actions such as:

* Logout.
* Client management.
* Update-job creation.
* Administrative changes.
* Other state-changing web operations.

The CSRF token is associated with the authenticated browser session and must be included where required.

---

# 48. API Authentication

Machine-to-machine communication uses client-specific Bearer tokens.

A protected agent request therefore follows:

```text
LUMS Agent
    │
    │ Authorization: Bearer <token>
    ▼
LUMS API
    │
    ▼
Token Validation
    │
    ▼
Authenticated Client
```

Administrator browser sessions are not used for agent authentication.

---

# 49. Client-Specific Tokens

Every registered LUMS client has an individual authentication token.

Tokens are associated with a specific client record.

This provides client-level authentication rather than a single shared credential for all agents.

The server can therefore identify which registered client is making a protected API request.

---

# 50. Token Storage

LUMS does not need to store the plaintext client token.

The stored token representation is a SHA-256 hexadecimal digest.

The lifecycle is:

```text
Plaintext Token
      │
      ▼
SHA-256
      │
      ▼
Hex Digest
      │
      ▼
Database
```

The plaintext token is only available to the client at the appropriate point in the token lifecycle.

The database therefore does not need the original secret value to validate a request.

---

# 51. Token Generation

New client tokens are generated using a cryptographically secure random source.

The current implementation uses:

```python
secrets.token_urlsafe(32)
```

The generated plaintext token is then hashed before being stored.

The plaintext token is returned only when required by the token creation or rotation operation.

---

# 52. Bearer Token Validation

Protected API requests provide the token through the HTTP Authorization header.

The server validates:

* Client identifier.
* Client existence.
* Client enabled state.
* Stored token digest.
* Token revocation state.

A request is accepted only when all required authentication conditions are satisfied.

---

# 53. Disabled Clients

A client can be disabled without deleting its historical data.

Disabling a client sets:

```text
enabled = 0
```

and records a token revocation timestamp.

The client therefore becomes inactive while historical information remains available.

This preserves:

* Historical jobs.
* Historical reports.
* Audit information.
* Operational history.

The client record is not destroyed merely because the client is no longer active.

---

# 54. Token Revocation

Client tokens can be invalidated through client state changes and token rotation.

The relevant state includes:

```text
enabled
token_revoked_at
```

A disabled or revoked client must not be able to continue authenticating against protected agent endpoints.

---

# 55. Token Rotation

LUMS supports client token rotation.

The rotation process is:

```text
Existing Token
      │
      ▼
Rotation Requested
      │
      ▼
Generate New Random Token
      │
      ▼
Calculate SHA-256 Digest
      │
      ▼
Replace Stored Digest
      │
      ▼
Revoke Previous Token
      │
      ▼
Return New Token Once
```

The previous token is no longer accepted after rotation.

---

# 56. Token Rotation Security

Token rotation intentionally invalidates the previous token immediately.

This ensures that a token which has been rotated away cannot continue to authenticate indefinitely.

The trade-off is that an agent still using the previous token may receive:

```text
401 Unauthorized
```

until its configuration is updated.

A future token grace-period mechanism could reduce this operational impact, but it would introduce additional token lifecycle state and must therefore be evaluated carefully.

---

# 57. Token Rotation Audit Logging

Token rotation is recorded in the audit log.

The audit event may document that a token was rotated, but the plaintext token itself must never be recorded.

The following must never appear in an audit entry:

```text
Authorization: Bearer <token>
```

or:

```text
Plaintext client token
```

Only the security-relevant action is recorded.

---

# 58. API Client Identity

After successful authentication, the API associates the request with the authenticated client.

This allows the application to enforce client-specific behavior such as:

* Client inventory updates.
* Package reporting.
* Pending job retrieval.
* Job claiming.
* Job result reporting.
* Client-specific update history.

A client must not be able to authenticate as another registered client by supplying a valid token for a different client.

---

# 59. Agent Reporting

The LUMS Agent periodically reports system information to the server.

The report can contain information such as:

* Hostname.
* Operating system.
* Architecture.
* Kernel information.
* Installed packages.
* Available updates.
* Agent version.
* Client state.

The report is authenticated using the client-specific Bearer token.

---

# 60. Report Authentication

The report flow is:

```text
Agent
  │
  │ HTTPS
  │ Bearer Token
  ▼
/api/report
  │
  ▼
Authenticate Client
  │
  ▼
Validate Report
  │
  ▼
Update Client State
```

Authentication occurs before protected client state is modified.

Invalid authentication must not result in an accepted report.

---

# 61. Report Input Validation

The report endpoint must treat all client-provided data as untrusted input.

Validation must cover:

* Request format.
* JSON structure.
* Required fields.
* Field types.
* Client identity.
* Package data.
* Update data.
* Agent metadata.

Invalid input should result in an appropriate client error rather than an unexpected internal server error.

Malformed JSON should therefore be handled explicitly.

The expected behavior is:

```text
Invalid JSON
    ↓
400 Bad Request
```

rather than:

```text
Invalid JSON
    ↓
500 Internal Server Error
```

This area is part of the ongoing API input-validation audit.

---

# 62. API Error Handling

API error responses should not reveal internal implementation details.

Responses should avoid exposing:

* Python tracebacks.
* Database paths.
* SQL statements.
* Secret values.
* Internal filesystem details.
* Authentication credentials.

Errors should be represented using appropriate HTTP status codes.

Examples include:

```text
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
500 Internal Server Error
```

The exact response depends on the operation and failure condition.

---

# 63. API Authorization Boundary

Authentication and authorization are separate concepts.

A valid client token proves:

```text
This request belongs to an authenticated client.
```

It does not automatically grant arbitrary access to every operation.

Endpoints must still enforce the permissions and client ownership rules appropriate to the requested operation.

The server must never rely solely on data supplied by the client to determine authorization.

---

# 64. Client Ownership

Client-specific operations must be associated with the authenticated client identity.

For example, an authenticated client requesting its pending update jobs must receive jobs associated with that client rather than arbitrary jobs belonging to another client.

This prevents cross-client data access.

The same principle applies to:

* Reports.
* Job results.
* Running jobs.
* Client inventory.
* Update history.

---

# 65. Authentication Separation

The security architecture intentionally maintains separate credentials:

```text
Administrator
    │
    └── Username + Password
              ↓
           Web Session

Agent
    │
    └── Client Bearer Token
              ↓
             API
```

Neither credential should be accepted as a substitute for the other.

This separation reduces the impact of compromise in one authentication domain.

---

# 66. Theme Independence

The theme system does not participate in authentication.

Theme selection is stored locally in browser storage:

```text
lums-theme
```

The selected value does not grant permissions.

Changing:

```text
standard
```

to:

```text
admin
```

does not make a user an administrator.

The `admin` theme identifier is purely a presentation identifier and must not be confused with an authorization role.

---

# 67. Security-Relevant Browser State

The following browser-side state must not be treated as trusted authorization information:

* Theme selection.
* Visual state.
* UI visibility.
* Client-side labels.
* JavaScript variables.
* DOM attributes.

The server remains responsible for authentication and authorization.

Hiding a button in the frontend is not an authorization mechanism.

---

# 68. Login Flow

The complete administrator login flow is:

```text
Browser
   │
   ▼
/login
   │
   ├── Validate request
   ├── Check rate limit
   ├── Find user
   ├── Verify Argon2 password
   │
   ├── Failure
   │     ├── Record failure
   │     ├── Apply lock if required
   │     └── Audit event
   │
   └── Success
         ├── Clear rate limit
         ├── Create session
         ├── Audit success
         └── Redirect
```

The authentication path therefore combines credential verification with rate limiting and audit logging.

---

# 69. Agent Authentication Flow

The complete agent authentication flow is:

```text
LUMS Agent
    │
    ▼
HTTPS Request
    │
    ▼
Bearer Token
    │
    ▼
Client Lookup
    │
    ├── Client missing → 401
    ├── Client disabled → 401
    ├── Token invalid → 401
    ├── Token revoked → 401
    │
    ▼
Authenticated Client
    │
    ▼
Request Validation
    │
    ▼
Operation
```

This ensures that client authentication occurs before protected operations are performed.

---

# 70. Authentication Security Principles

The authentication architecture follows these principles:

```text
Passwords are never stored in plaintext.
Tokens are not stored in plaintext.
Clients have individual tokens.
Disabled clients cannot authenticate.
Rotated tokens become invalid.
Login failures are rate limited.
Authentication failures use generic messages.
Security events are audited.
Browser sessions and agent tokens remain separate.
Themes do not influence authorization.
```

These principles apply independently of the selected LUMS frontend theme.

---

# 71. Current Authentication Status

Implemented and tested:

```text
✓ Argon2 password hashing
✓ Administrator authentication
✓ Session-based web authentication
✓ CSRF protection
✓ Generic authentication errors
✓ Login rate limiting
✓ Progressive login locks
✓ Login rate-limit audit events
✓ Per-client Bearer tokens
✓ SHA-256 token digest storage
✓ Client token rotation
✓ Token invalidation
✓ Disabled-client protection
✓ Authenticated agent reporting
✓ Client-specific API authentication
```

Planned or under review:

```text
○ Server-side session revocation
○ Token rotation grace-period evaluation
○ Further API input validation
○ Additional API rate limiting
```

---

# 72. End of Part 2

Part 2 establishes the application authentication and API security model:

```text
Administrator
    ↓
Password
    ↓
Argon2
    ↓
Session
    ↓
Protected Web Interface
```

and:

```text
Agent
    ↓
Bearer Token
    ↓
SHA-256 Validation
    ↓
Authenticated Client
    ↓
Protected API
```

Both paths are protected by additional controls such as:

```text
Rate Limiting
CSRF Protection
Input Validation
Audit Logging
Client State Validation
```

**End of Part 2.**

# Part 3 — Jobs, Recovery, Agent, Idle Detection, Package Managers & Timeout

## 73. Update Job Security

LUMS update jobs represent controlled instructions for package operations on managed Linux clients.

The server manages job state.

The client performs the actual package operation.

This separation is fundamental to the LUMS security model:

```text
LUMS Server
    │
    ├── Create Job
    ├── Validate Packages
    ├── Assign Job
    └── Track State
            │
            ▼
       LUMS Agent
            │
            ├── Check Idle State
            ├── Claim Job
            ├── Execute Update
            └── Report Result
```

The server does not directly install packages on managed clients.

---

# 74. Job Lifecycle

The current job lifecycle is:

```text
pending
   │
   ▼
waiting_for_idle
   │
   ▼
running
   │
   ├── success
   ├── partial
   ├── failed
   └── abandoned
```

A pending job must not be executed merely because it exists.

The execution watcher first evaluates the conditions required for execution.

Only a successfully claimed job may be executed.

---

# 75. Job Creation Validation

Update jobs are created through the LUMS management interface.

The server validates requested package information before creating the job.

Validation includes:

* Client identity.
* Requested package names.
* Available update inventory.
* Duplicate package handling.
* Job state initialization.

Unknown or invalid packages must not silently become executable update instructions.

The package list is normalized before being stored.

---

# 76. Waiting for Idle

A pending job can enter:

```text
waiting_for_idle
```

before execution.

This state reflects that the job exists but execution is intentionally deferred because the client is not yet considered idle.

The watcher must not bypass the idle requirement simply because a job is waiting.

---

# 77. Execution Watcher

The execution watcher is separate from the reporting agent.

The current watcher components are:

```text
lums-execution-watcher.service
lums-execution-watcher.timer
watcher.py
```

The execution flow is:

```text
Timer
   │
   ▼
Watcher Service
   │
   ▼
Protected Configuration
   │
   ▼
HTTPS / Bearer Authentication
   │
   ▼
Idle Detection
   │
   ▼
Job Retrieval
   │
   ▼
Atomic Claim
   │
   ▼
Package Execution
   │
   ▼
Result Reporting
```

The reporting agent and execution watcher therefore have separate responsibilities.

---

# 78. Watcher Authentication

The watcher communicates with the LUMS server using HTTPS and the client-specific Bearer token.

The watcher must load its protected configuration before contacting the server.

The client token must remain outside the application source tree.

The watcher must not:

* Log the plaintext token.
* Include the token in normal status output.
* Store the token in Git.
* Include the token in documentation.
* Expose the token through debug output.

---

# 79. Watcher Execution Requirements

Before executing an update job, the watcher must establish that:

1. The protected configuration can be loaded.
2. The LUMS server can be reached.
3. Client authentication succeeds.
4. A pending job exists.
5. Idle detection is supported.
6. The configured idle threshold has been reached.
7. The job belongs to the authenticated client.
8. The job can be claimed atomically.
9. The package manager is available.
10. Execution can be monitored safely.

If these requirements are not satisfied, the watcher must not blindly execute the job.

---

# 80. Idle Detection

The current watcher uses the system's `loginctl` interface for idle detection.

The configured idle threshold is:

```text
300 seconds
```

The watcher records idle-related information such as:

```text
idle
idle_seconds
idle_threshold_seconds
idle_source
idle_supported
```

The current execution policy is:

```text
Idle detection supported
        +
Idle threshold reached
        +
Pending job
        +
Authenticated client
        +
Successful atomic claim
        =
Eligible for execution
```

---

# 81. Unsupported Idle Detection

Idle detection is treated as a security and operational prerequisite.

If idle detection is unavailable or unsupported:

```text
idle_supported = false
```

the watcher must fail safely by avoiding update execution.

The absence of reliable idle information must not be interpreted as proof that the system is idle.

This prevents an unknown state from becoming an implicit authorization to execute package operations.

---

# 82. Idle Detection Limitations

Idle detection is not a universal desktop activity detector.

The current implementation is primarily intended for controlled Linux server, terminal, console, and infrastructure environments.

The security documentation must therefore not claim that LUMS can detect every possible form of user activity on every Linux desktop environment.

Idle-aware execution is an execution policy, not a replacement for a complete desktop session-management system.

---

# 83. Atomic Job Claiming

Job claiming is performed atomically.

The conceptual workflow is:

```text
Pending Job
     │
     ▼
Authorization Check
     │
     ▼
Atomic Claim
     │
     ├── Success
     │      ↓
     │    running
     │
     └── Already Claimed
            ↓
       No Execution
```

The server uses an atomic database operation to prevent competing requests from claiming the same job.

---

# 84. Duplicate Execution Protection

Atomic claiming protects against duplicate execution caused by:

* Multiple watcher cycles.
* Concurrent requests.
* Timer overlap.
* Network retries.
* Multiple watcher instances.
* Repeated execution attempts.

If a claim fails because the job is no longer pending, the watcher must not execute that job.

A failed claim is not an authorization to continue.

---

# 85. Job Result Validation

The result endpoint is:

```http
POST /api/update-jobs/<job_id>/result
```

The server validates:

* Job existence.
* Client ownership.
* Current job state.
* Result format.
* Allowed result status.
* Result ownership.

Supported overall result states are:

```text
success
partial
failed
```

A client must not be able to submit an arbitrary successful result for a job it did not execute.

---

# 86. Result Reporting

A result can contain information such as:

```text
Job ID
Package results
Overall status
Successful package count
Failed package count
Timeout information
Reboot requirement
```

The result is associated with the authenticated client and the corresponding update job.

This allows the server to maintain an auditable execution history without directly executing package operations itself.

---

# 87. Interrupted Jobs

A job may remain in the `running` state after:

* Client shutdown.
* System restart.
* Watcher interruption.
* Network failure.
* Package-manager failure.
* Result submission failure.
* Unexpected process termination.

An interrupted job must not simply be treated as successful.

LUMS therefore provides explicit recovery handling.

---

# 88. Running-Job Recovery

The recovery endpoint is:

```http
POST /api/update-jobs/<job_id>/abandon
```

Recovery validates:

* Client authentication.
* Job ownership.
* Current job state.
* Allowed state transition.

The job is moved from:

```text
running
```

to:

```text
abandoned
```

The recovery process records:

* Recovery reason.
* Completion timestamp.
* Update history information.
* Package counts.
* Execution metadata.

Conditional state updates are used to reduce race conditions during recovery.

---

# 89. Recovery Before New Execution

The watcher checks for an existing running job before claiming a new pending job.

Conceptually:

```text
Existing Running Job?
        │
        ├── Yes
        │    │
        │    ▼
        │  Recovery / Resume Handling
        │
        └── No
             │
             ▼
        Request Pending Job
```

The watcher must not simply abandon an uncertain running job and immediately start another operation.

If recovery fails, the watcher must stop rather than claiming a new job.

This prevents multiple ambiguous executions from accumulating.

---

# 90. Recovery Testing

Recovery has been tested with a controlled synthetic job.

The tested transition was:

```text
running
   │
   ▼
abandoned
```

Validation included:

* `finished_at` populated.
* Recovery reason recorded.
* Update history entry created.
* Package count preserved.
* Successful count preserved.
* Failed count preserved.
* No unintended reboot flag.
* Synthetic test data removed afterward.

A subsequent real update job was successfully executed after the recovery test.

Recovery is therefore implemented and validated for the current workflow.

---

# 91. Simulation Mode

LUMS provides simulation mode for controlled end-to-end testing.

Simulation mode:

* Does not execute real package updates.
* Does not modify installed packages.
* Simulates package results.
* Exercises job claiming.
* Exercises watcher behavior.
* Exercises result reporting.
* Exercises UI state changes.

The setting is:

```text
LUMS_SIMULATE_UPDATES
```

Simulation mode must only be enabled temporarily for testing.

---

# 92. Simulation Safety

A temporary simulation configuration can be applied through systemd:

```bash
sudo systemctl edit --runtime \
    lums-execution-watcher.service
```

The temporary setting is:

```ini
[Service]
Environment=LUMS_SIMULATE_UPDATES=1
```

After testing, the temporary override must be removed:

```bash
sudo systemctl revert --runtime \
    lums-execution-watcher.service

sudo systemctl daemon-reload
```

The service configuration should then be verified:

```bash
sudo systemctl cat \
    lums-execution-watcher.service
```

Simulation mode must not remain enabled during normal update execution.

A successful simulation does not prove that real APT/dpkg interactions are completely collision-free.

---

# 93. Package Manager Boundary

LUMS does not replace the operating system package manager.

On Debian-based systems, package operations remain the responsibility of:

```text
APT
  ↓
dpkg
```

LUMS provides the management and execution orchestration around these tools.

APT remains responsible for:

* Repository handling.
* Dependency resolution.
* Package signatures.
* Package installation.
* dpkg interaction.

---

# 94. Package Manager Coordination

Complete coordination with arbitrary manually started APT or dpkg operations is not fully implemented.

A potential collision can therefore still exist:

```text
LUMS watcher
     │
     ├── starts package operation
     │
     ▼
APT / dpkg

        +

User manually starts
APT / dpkg
```

A custom LUMS execution lock does not automatically force every external package-manager process to respect it.

This limitation must remain explicitly documented.

---

# 95. Package Manager Safety Rules

The following operational rule applies:

> Never delete foreign APT or dpkg lock files to force an update to continue.

Removing package-manager lock files can corrupt package-management state or leave the system in an inconsistent condition.

If APT or dpkg is already busy, LUMS should defer or fail safely rather than forcibly removing locks.

---

# 96. APT Package Operations

The agent uses the native APT tooling for Debian-based clients.

Typical operations include:

```text
Installed packages
    ↓
dpkg-query
```

```text
Available updates
    ↓
apt list --upgradable
```

```text
Package information
    ↓
apt-cache policy
```

```text
Package update
    ↓
apt-get install --only-upgrade
```

```text
System update
    ↓
apt-get upgrade
```

LUMS therefore remains dependent on the local package manager's normal security and dependency mechanisms.

---

# 97. Arch Package Operations

Arch Linux clients use `pacman`.

The package-manager abstraction provides corresponding operations for:

```text
Installed packages
    ↓
pacman -Q
```

```text
Available updates
    ↓
pacman -Qu
```

```text
Package information
    ↓
pacman -Si
```

```text
Package update
    ↓
pacman -S --noconfirm
```

```text
System update
    ↓
pacman -Syu --noconfirm
```

The same LUMS job-security model applies independently of the package manager.

---

# 98. Package Manager Abstraction

The agent detects the available package manager and uses the corresponding implementation.

The abstraction separates:

```text
LUMS Execution Logic
        │
        ▼
Package Manager Interface
        │
        ├── APT / dpkg
        │
        └── pacman
```

This prevents the central job workflow from depending on one specific distribution.

Security-sensitive execution rules remain above the package-manager implementation.

---

# 99. Update Execution Timeout

Package execution is subject to an explicit timeout.

The current implementation avoids relying on a blocking stdout read that could prevent timeout handling.

Execution uses selector-driven output handling so that the process can be monitored while remaining interruptible.

The timeout sequence is:

```text
Package Process
      │
      ▼
Timeout reached
      │
      ▼
terminate()
      │
      ▼
10-second grace period
      │
      ├── Process exits
      │
      └── Process remains
              │
              ▼
            kill()
```

This ensures that a package process cannot remain indefinitely attached to an update job solely because it stopped producing output.

---

# 100. Timeout Result Handling

A timeout is represented explicitly in the package result.

The resulting job state must reflect the actual execution outcome rather than being incorrectly reported as successful.

Timeout information is also available to the server as part of the job result.

This allows the management interface and update history to distinguish:

```text
Successful execution
```

from:

```text
Execution timeout
```

---

# 101. Process Cleanup

The package execution implementation performs process cleanup after execution.

Cleanup is required for both:

```text
Normal completion
```

and:

```text
Timeout / termination
```

The process must not be left running after the corresponding LUMS job has finished handling the execution result.

The terminate → grace → kill sequence provides a controlled fallback when graceful termination is not sufficient.

---

# 102. Timeout Testing

The timeout implementation has been tested using controlled child processes.

Tests included:

* Silent child timeout.
* Process termination.
* SIGTERM-resistant child.
* Kill fallback.
* Integration with a simulated hanging package process.
* Correct `timeout` result handling.

The resulting timeout behavior was verified before the implementation was deployed to the Debian and Arch clients.

---

# 103. Agent Version

The current LUMS Agent version is:

```text
1.7.0
```

The agent is responsible for:

* Client reporting.
* Inventory collection.
* Update discovery.
* Job interaction.
* Package execution.
* Result reporting.

The execution watcher operates alongside the reporting agent.

---

# 104. Reporting Service

The reporting service is:

```text
lums-agent.service
```

The reporting timer is:

```text
lums-agent.timer
```

The service uses a oneshot execution model.

The normal workflow is:

```text
Timer
   ↓
lums-agent.service
   ↓
agent.py
   ↓
HTTPS report
   ↓
Exit
```

A successful oneshot service may return to:

```text
inactive (dead)
```

with:

```text
status 0/SUCCESS
```

This is normal behavior for a successfully completed oneshot service.

---

# 105. Execution Watcher Service

The execution watcher is separate:

```text
lums-execution-watcher.service
lums-execution-watcher.timer
```

The watcher performs update execution independently of the periodic inventory report.

This separation allows:

```text
Reporting
```

and:

```text
Update Execution
```

to be monitored and diagnosed independently.

A successful agent report therefore does not automatically mean that an update job has executed.

---

# 106. Watcher Failure Handling

If the watcher cannot safely establish the conditions for execution, it should stop the current cycle.

Examples include:

* Authentication failure.
* Unsupported idle detection.
* Idle threshold not reached.
* No pending job.
* Job claim failure.
* Package manager unavailable.
* Recovery failure.
* Execution timeout.
* Result submission failure.

The watcher must not turn an unknown or failed security condition into automatic package execution.

---

# 107. Update Execution Security Boundary

The final execution boundary is the managed Linux client itself.

The architecture is:

```text
LUMS Server
    │
    │ Management decision
    ▼
Authenticated Client
    │
    ▼
Execution Watcher
    │
    ▼
Package Manager
    │
    ▼
Operating System
```

The server therefore does not directly execute arbitrary commands on the managed host.

The client-side agent and watcher are responsible for applying the authorized job through the supported package-manager abstraction.

---

# 108. Current Execution Security Status

Implemented and verified:

```text
✓ Agent 1.7.0
✓ Separate execution watcher
✓ HTTPS client communication
✓ Bearer authentication
✓ Idle-aware execution
✓ 300-second idle threshold
✓ Unsupported-idle safe behavior
✓ Atomic job claiming
✓ Client/job ownership checks
✓ Running-job recovery
✓ Abandoned-job handling
✓ Result validation
✓ Simulation mode
✓ APT package-manager abstraction
✓ pacman package-manager abstraction
✓ Execution timeout
✓ terminate() handling
✓ 10-second termination grace period
✓ kill() fallback
✓ Timeout result reporting
✓ Debian validation
✓ Arch Linux validation
```

Known limitation:

```text
○ Complete coordination with arbitrary external
  APT/dpkg operations is not yet implemented.
```

---

# 109. Security Principle

LUMS should never execute an update merely because a job exists.

Execution requires a chain of verified conditions:

```text
Authenticated Client
        ↓
Valid Job
        ↓
Authorized Client
        ↓
Idle State Supported
        ↓
Idle Threshold Reached
        ↓
Atomic Claim Successful
        ↓
Package Manager Available
        ↓
Controlled Execution
        ↓
Timeout Protection
        ↓
Validated Result
        ↓
Audited Job History
```

Every step exists to reduce the possibility of uncontrolled or ambiguous update execution.

---

# 110. End of Part 3

The LUMS execution model is therefore based on:

```text
Controlled
Authenticated
Idle-aware
Atomic
Time-bounded
Auditable
```

execution.

The remaining package-manager coordination limitation is intentionally documented rather than hidden.

**End of Part 3.**

# Part 4 — Nginx, TLS, Database, Backups, Git & Deployment

## 111. Nginx Security Boundary

Nginx is the external HTTPS entry point for LUMS.

The intended architecture is:

```text
Client
   │
   │ HTTPS :443
   ▼
Nginx
   │
   │ HTTP localhost
   ▼
127.0.0.1:5050
   │
   ▼
Docker container :5000
   │
   ▼
Gunicorn
   │
   ▼
Flask
```

The Flask application must not be directly exposed to the network.

The Docker port is intentionally bound to localhost:

```text
127.0.0.1:5050:5000
```

This ensures that external clients must pass through the Nginx security boundary.

---

# 112. Nginx Responsibilities

Nginx is responsible for:

* TLS termination.
* HTTPS access.
* HTTP-to-HTTPS redirection.
* Reverse proxying requests to LUMS.
* Preventing direct network access to the application container.
* Providing the external HTTP security boundary.

The reverse-proxy target is:

```text
http://127.0.0.1:5050
```

The application container itself listens internally on:

```text
0.0.0.0:5000
```

but this port is not directly exposed to the network.

---

# 113. Nginx Configuration Validation

Nginx configuration must be validated before reloading the service.

Use:

```bash
sudo nginx -t
```

Only after a successful configuration test should Nginx be reloaded:

```bash
sudo systemctl reload nginx
```

Check the service:

```bash
sudo systemctl status nginx --no-pager
```

Review recent logs when troubleshooting:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

A configuration change must never be assumed to be safe merely because the configuration file was edited successfully.

---

# 114. TLS

LUMS uses HTTPS for client and browser communication.

The production TLS files are:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

The certificate is public information.

The private key is a secret.

The private key must never be:

* Committed to Git.
* Included in Docker images.
* Included in public documentation.
* Printed in diagnostic output.
* Shared through public issue reports.

---

# 115. TLS Protocols

The current Nginx configuration is intended to permit modern TLS versions:

```text
TLS 1.2
TLS 1.3
```

Older protocol versions must remain disabled.

Verify the configuration with:

```bash
sudo nginx -T | grep -n "ssl_protocols"
```

TLS configuration must be reviewed whenever the certificate, Nginx configuration, or deployment architecture changes.

---

# 116. Certificate Validation

The certificate should contain the hostname or IP address used by LUMS clients in its Subject Alternative Name.

Inspect certificate information:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

Inspect the SAN:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -ext subjectAltName
```

The client connection address must match an appropriate SAN entry.

A Common Name alone must not be relied upon for modern hostname verification.

---

# 117. Self-Signed Certificates

Controlled laboratory deployments may use a self-signed certificate.

This requires explicit trust configuration on the clients.

The LUMS agent uses the configured CA certificate for TLS verification.

The certificate should therefore be distributed through the protected client configuration rather than bypassing TLS verification.

The following is acceptable only for controlled diagnostics:

```bash
curl -k -I https://127.0.0.1/
```

The `-k` option disables certificate verification and must not become the normal client security model.

Normal agent communication must verify the configured CA.

---

# 118. HTTP to HTTPS

Normal LUMS communication must use:

```text
https://<LUMS_SERVER>
```

HTTP should redirect to HTTPS.

Test HTTP:

```bash
curl -I http://<LUMS_SERVER>
```

Test HTTPS with the configured CA:

```bash
curl \
    --cacert /opt/lums-agent/lums-ca.crt \
    -I \
    https://<LUMS_SERVER>
```

Sensitive authentication information must never be intentionally transmitted over unencrypted HTTP.

---

# 119. Security Headers

The application provides security-related HTTP headers including:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
Content-Security-Policy: ...
```

The Content Security Policy restricts application resources such as:

* Scripts.
* Styles.
* Connections.
* Objects.
* Frames.
* Form actions.

Security headers should be verified after production deployment and after changes to Nginx or the frontend.

Check:

```bash
curl -k -I https://127.0.0.1/
```

---

# 120. Content Security Policy

The LUMS CSP intentionally avoids weakening the policy with:

```text
unsafe-inline
```

Inline styles or scripts that conflict with the CSP must instead be moved into the appropriate static resources.

This keeps the browser security boundary explicit.

Frontend changes must therefore be reviewed together with the CSP.

---

# 121. Gunicorn Application Server

The Docker deployment does not use the Flask development server.

LUMS uses Gunicorn as the production application server.

Current production runtime:

```text
Gunicorn 23.0.0
```

The application is loaded through:

```text
app:app
```

The architecture is:

```text
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker :5000
   ↓
Gunicorn
   ↓
Flask
```

Gunicorn is therefore the application process inside the production container.

---

# 122. Container Startup

Database initialization is separated from application startup.

The intended sequence is:

```text
Container Start
      │
      ▼
init_db.py
      │
      │ successful
      ▼
Gunicorn
      │
      ▼
Flask
```

The database initialization script is:

```text
/app/server/init_db.py
```

The Docker entrypoint is:

```text
/app/docker-entrypoint.sh
```

The entrypoint initializes the database before starting Gunicorn.

This prevents initialization from being executed independently by multiple application workers.

---

# 123. Entrypoint Failure Handling

The Docker entrypoint uses strict shell behavior.

Database initialization must succeed before Gunicorn is started.

If database initialization fails:

```text
Database initialization
        │
        ▼
      ERROR
        │
        ▼
Gunicorn does not start
```

This prevents the application from running against an unsuccessfully initialized database state.

Gunicorn is executed as the container's main process so that Docker can manage its process lifecycle directly.

---

# 124. SQLite Security Model

LUMS currently uses SQLite for persistent application state.

The database is stored inside the persistent Docker volume:

```text
lums-data:/var/lib/lums
```

The database therefore survives container recreation.

The container itself is disposable.

The persistent application data is not.

---

# 125. SQLite Connection Hardening

LUMS enables SQLite foreign-key enforcement for application database connections:

```sql
PRAGMA foreign_keys = ON;
```

The application also configures:

```sql
PRAGMA busy_timeout = 5000;
```

This provides a five-second busy timeout for database operations.

The resulting runtime configuration was verified as:

```text
foreign_keys: 1
busy_timeout: 5000
```

---

# 126. SQLite WAL Mode

The production database uses:

```text
journal_mode = WAL
```

Write-Ahead Logging improves concurrency behavior for the current LUMS workload.

The initialization path configures WAL mode.

The production runtime was verified with:

```text
journal_mode: wal
```

The observed SQLite settings also included:

```text
synchronous: 2
```

corresponding to SQLite's normal `FULL` synchronous mode.

---

# 127. SQLite Integrity

Database integrity must be checked after security-sensitive database changes and before important deployment operations.

Recommended check:

```bash
sqlite3 /path/to/lums.db \
    "PRAGMA integrity_check;"
```

Expected result:

```text
ok
```

Foreign-key consistency can additionally be checked with:

```sql
PRAGMA foreign_key_check;
```

The expected result for a clean database is an empty result set.

---

# 128. SQLite Schema Migrations

LUMS uses versioned database migrations for security-sensitive schema changes.

Current migrations include:

```text
001
002
003-login-rate-limiting
```

Migration handling must remain idempotent where possible.

A migration must not silently destroy existing production data.

Before applying structural database changes:

```text
Backup
   ↓
Migration
   ↓
Integrity Check
   ↓
Application Test
```

---

# 129. Persistent Database Data

The persistent database contains security-relevant information including:

* Administrator accounts.
* Client records.
* Client token digests.
* Audit records.
* Update jobs.
* Update history.
* Package inventory.
* Migration state.
* Login rate-limit state.

The database must therefore be treated as sensitive application data.

It must not be:

* Committed to Git.
* Uploaded publicly.
* Included in public bug reports.
* Copied into documentation without sanitization.

---

# 130. Database Backups

A production database backup should be created before replacing or significantly modifying the production container.

The backup must be treated as sensitive data.

A backup is not considered trustworthy merely because the file was successfully copied.

It must also be verified.

The expected workflow is:

```text
Production Database
       │
       ▼
Verified Backup
       │
       ▼
Integrity Check
       │
       ▼
Deployment / Change
```

---

# 131. SQLite-Aware Backup Handling

Backups should be created in a way that is appropriate for SQLite.

After creating a backup, verify the resulting database independently.

For example:

```bash
sqlite3 /path/to/backup.db \
    "PRAGMA integrity_check;"
```

Expected:

```text
ok
```

Foreign-key consistency should also be checked where appropriate:

```bash
sqlite3 /path/to/backup.db \
    "PRAGMA foreign_key_check;"
```

An empty result indicates no reported foreign-key violations.

---

# 132. Backup Protection

Backup directories should not be world-readable.

Recommended protection includes:

```text
Backup directory
    0700

Backup database
    0600
```

Backups must not contain:

* Plaintext client tokens.
* Passwords.
* Private keys.
* TLS private keys.
* Server secrets.
* Unnecessary personal information.

Because the database contains authentication and audit information, access to backups must be restricted accordingly.

---

# 133. Restore Principle

A backup is only useful if it can be restored.

The intended restore workflow is:

```text
Verified Backup
      │
      ▼
Isolated Restore Environment
      │
      ▼
SQLite Integrity Check
      │
      ▼
Schema Verification
      │
      ▼
Application Startup
      │
      ▼
Authentication Test
      │
      ▼
Client / Job Data Test
```

A full isolated restore test remains a separate validation task.

Until that test is completed, backup integrity should not be confused with full disaster-recovery validation.

---

# 134. Persistent Volume Protection

The production database is stored in:

```text
lums-data
```

Container troubleshooting must distinguish between:

```text
Container
```

and:

```text
Persistent Volume
```

Removing the container is normally reversible.

Removing the persistent volume is destructive.

Therefore:

```bash
sudo docker stop lums
sudo docker rm lums
```

does not remove the database.

The following must **not** be executed casually:

```bash
sudo docker volume rm lums-data
```

A verified backup should exist before destructive storage operations.

---

# 135. Git Security Boundary

Git is treated as the source-code and documentation boundary.

The repository must never contain:

* Passwords.
* Client tokens.
* Flask secrets.
* TLS private keys.
* Production databases.
* Production backups.
* Private configuration containing credentials.

The repository should contain safe placeholders instead.

Examples:

```text
<LUMS_SERVER_IP>
<CLIENT_IP>
<CLIENT_TOKEN>
<CLIENT_ID>
<JOB_ID>
<ADMIN_PASSWORD>
```

---

# 136. Git Secret Review

Before committing changes:

```bash
git status
git diff
git diff --check
```

Review the complete diff rather than relying only on the changed filenames.

Before deployment, also verify repository state:

```bash
git status --short
git fetch origin
git log --oneline --decorate -3
```

The repository should be clean and the intended branch should be known before production deployment.

---

# 137. Git History

Removing a secret from the current working tree does not necessarily remove it from Git history.

If a secret was previously committed or otherwise exposed, it must be treated as compromised until rotated.

The LUMS Flask secret was previously exposed through diagnostic output.

The response was:

```text
Identify exposure
      ↓
Generate replacement secret
      ↓
Replace production secret
      ↓
Restart application
      ↓
Verify authentication
      ↓
Verify session invalidation
      ↓
Remove temporary old-secret backup
```

The previous value is intentionally not reproduced in this documentation.

---

# 138. Git Deployment Workflow

The production deployment workflow is:

```text
Working Tree
     │
     ▼
git status
     │
     ▼
git fetch
     │
     ▼
Review commits
     │
     ▼
git pull --ff-only
     │
     ▼
git diff --check
     │
     ▼
Docker Build
     │
     ▼
Backup Database
     │
     ▼
Container Recreation
     │
     ▼
Runtime Verification
     │
     ▼
HTTPS Verification
     │
     ▼
Client Verification
```

A successful `git pull` does not prove that the resulting application is production-ready.

---

# 139. Docker Build Security

The production image is built from the repository source.

The image build must be performed after reviewing the intended source state.

Example:

```bash
sudo docker build \
    -t lums:latest \
    .
```

The build itself must not receive production secrets through the Docker build context.

Secrets belong in runtime configuration, not in the image.

---

# 140. Production Container Recreation

Before recreating the production container:

```bash
sudo docker ps
sudo docker volume inspect lums-data
```

Create and verify a database backup.

Then stop and remove only the existing container:

```bash
sudo docker stop lums
sudo docker rm lums
```

The persistent volume remains untouched.

The hardened production container can then be recreated with:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --tmpfs /tmp:rw,nosuid,nodev,noexec \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -p 127.0.0.1:5050:5000 \
    lums:latest
```

The production container must retain:

```text
Non-root execution
Read-only root filesystem
No Linux capabilities
Read-only secret mount
Persistent database volume
Localhost-only application binding
```

---

# 141. Deployment Verification

After container recreation, verify:

```text
1. Container is running.
2. Correct image is running.
3. Correct localhost binding is present.
4. Persistent volume is mounted.
5. Database initialization succeeds.
6. Gunicorn starts.
7. HTTPS remains operational.
8. Security headers remain present.
9. Login remains accessible.
10. Client authentication remains functional.
11. Client reporting remains functional.
12. Update jobs remain functional.
13. Container runs as non-root.
14. Root filesystem remains read-only.
15. All capabilities remain dropped.
16. /tmp is available through tmpfs.
17. Secret file is configured.
18. LUMS_SECRET_KEY is not used as a normal environment secret.
19. Secret mount is read-only.
20. Container restart succeeds.
```

Check the container:

```bash
sudo docker ps \
    --filter "name=^lums$" \
    --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"
```

---

# 142. Volume Verification

Verify the persistent volume:

```bash
sudo docker inspect lums \
    --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} RW={{.RW}}{{"\n"}}{{end}}'
```

The database volume should appear as:

```text
lums-data -> /var/lib/lums RW=true
```

The secret mount should appear as:

```text
/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
```

The combination provides:

```text
Persistent Database
        +
Read-only Secret
        +
Read-only Container Root
```

---

# 143. Runtime Security Verification

Verify the container runtime configuration:

```bash
sudo docker inspect lums \
    --format '
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
CapAdd={{json .HostConfig.CapAdd}}
CapDrop={{json .HostConfig.CapDrop}}
Privileged={{.HostConfig.Privileged}}
'
```

Expected:

```text
ReadonlyRootfs=true
CapAdd=null
CapDrop=["ALL"]
Privileged=false
```

Verify the container identity:

```bash
sudo docker exec lums id
```

The application runs as the dedicated non-root user:

```text
lums
```

The exact numeric UID should be treated as an implementation detail and verified from the running image rather than hard-coded into documentation unless explicitly required.

---

# 144. Secret Runtime Verification

The production architecture intentionally uses:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

The secret itself is mounted read-only:

```text
/etc/lums/secrets/lums_secret
        ↓
/run/secrets/lums_secret
```

The plaintext Flask secret must not be supplied through:

```text
LUMS_SECRET_KEY
```

as a normal environment variable.

This keeps the secret outside the normal Docker environment configuration.

---

# 145. Post-Deployment Application Verification

After deployment, verify the application through the actual configured interface.

The production application does not provide a generic `/health` endpoint.

Therefore:

```bash
curl -k https://127.0.0.1/health
```

returning:

```text
404
```

is expected and does not represent a failed deployment.

Instead, verify actual application endpoints such as:

```text
/api/clients
/api/client/me
```

using the appropriate authentication context.

Unauthenticated access should be rejected where authentication is required.

---

# 146. Production Logs

After deployment, review:

```bash
sudo docker logs --tail 100 lums
```

The startup sequence should show database initialization followed by Gunicorn startup.

Also review:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

and on managed clients:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Watcher logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
```

Logs must not contain:

* Plaintext tokens.
* Passwords.
* Server secrets.
* Private keys.
* Complete Authorization headers.
* Unnecessary sensitive inventory data.

Sensitive information must be redacted before logs are shared.

---

# 147. Deployment Security Principle

A deployment is not complete when the container starts.

The complete verification chain is:

```text
Source
   ↓
Git Review
   ↓
Docker Build
   ↓
Database Backup
   ↓
Container Recreation
   ↓
Runtime Hardening Check
   ↓
Database Integrity
   ↓
Nginx Validation
   ↓
HTTPS Verification
   ↓
Authentication Verification
   ↓
Client Verification
   ↓
Job Verification
```

Only after the complete chain has been checked should the deployment be considered operationally verified.

---

# 148. End of Part 4

The LUMS deployment security model therefore protects four major boundaries:

```text
Network Boundary
    ↓
Nginx + TLS

Application Boundary
    ↓
Gunicorn + Flask

Data Boundary
    ↓
SQLite + Persistent Volume + Backups

Source / Deployment Boundary
    ↓
Git + Docker + Verified Deployment
```

The guiding rule remains:

```text
Backup before change.
Review before build.
Verify before production.
Preserve persistent data.
Never commit secrets.
Never assume a successful build equals a successful deployment.
```

**End of Part 4.**
# Part 5 — Incident Handling, Testing, Audit Status, Roadmap & Final Security Principles

## 149. Security Incident Handling

Security incidents must be handled as controlled operational events.

The general workflow is:

```text
Detection
   ↓
Containment
   ↓
Investigation
   ↓
Remediation
   ↓
Verification
   ↓
Documentation
```

The objective is not only to restore normal operation but also to establish what happened and verify that the underlying security condition has been addressed.

---

# 150. Incident Identification

Potential security incidents may be identified through:

* Application logs.
* Authentication failures.
* Rate-limit events.
* Audit records.
* Unexpected client authentication.
* Invalid or revoked tokens.
* Unexpected job execution.
* Container configuration changes.
* Unexpected database changes.
* TLS problems.
* Git history.
* Unexpected filesystem changes.
* Monitoring systems.

An unusual event should be investigated before being dismissed as harmless.

---

# 151. Secret Exposure

If a LUMS secret is exposed, it must be treated as compromised.

Examples include:

* Flask secrets.
* Client tokens.
* TLS private keys.
* Passwords.
* Environment files.
* Database credentials.

The response should be:

```text
Identify Secret
      ↓
Contain Exposure
      ↓
Rotate / Revoke
      ↓
Deploy Replacement
      ↓
Verify
      ↓
Review Exposure
      ↓
Document
```

The old secret must not simply be deleted and assumed safe.

---

# 152. Flask Secret Incident Procedure

If the Flask secret is exposed:

1. Generate a new cryptographically secure secret.
2. Replace the production secret.
3. Restart the application.
4. Verify that old sessions are invalidated where applicable.
5. Verify new authentication.
6. Verify HTTPS operation.
7. Verify database integrity.
8. Verify client communication.
9. Review where the old secret was exposed.
10. Remove unnecessary copies of the old secret.
11. Review Git history if the secret entered the repository.
12. Document the incident.

The secret value itself must never be written into this documentation.

---

# 153. Client Token Incident Procedure

If a client token is suspected to be compromised:

```text
Suspected Compromise
        ↓
Identify Client
        ↓
Rotate Token
        ↓
Old Token Invalidated
        ↓
Configure New Token
        ↓
Verify Agent Authentication
        ↓
Verify Reporting
        ↓
Audit Event
```

The old token must not remain active merely because the client has not yet been reconfigured.

Token rotation therefore provides a direct containment mechanism.

---

# 154. TLS Private-Key Incident

If the TLS private key is exposed:

1. Treat the key as compromised.
2. Generate or obtain a replacement certificate and private key.
3. Install the replacement securely.
4. Verify the certificate chain.
5. Reload Nginx.
6. Verify HTTPS.
7. Reconfigure clients if required.
8. Remove unnecessary copies of the old key.
9. Review how the key was exposed.

The private key must never be reproduced in incident documentation.

---

# 155. Compromised Administrator Account

If administrator credentials are suspected to be compromised:

```text
Suspected Account Compromise
          ↓
Restrict Access
          ↓
Change Password
          ↓
Review Authentication Logs
          ↓
Review Audit Log
          ↓
Review Client / Job Activity
          ↓
Review Session State
          ↓
Verify Deployment
```

Particular attention should be given to:

* Client creation.
* Token rotation.
* Job creation.
* Job execution.
* Configuration changes.
* Unexpected authentication events.

---

# 156. Unexpected Update Execution

If an update job executes unexpectedly:

1. Identify the job.
2. Identify the authenticated client.
3. Review job creation.
4. Review job claiming.
5. Review watcher logs.
6. Review idle-state information.
7. Review package-manager activity.
8. Review audit records.
9. Determine whether execution was authorized.
10. Preserve relevant logs before cleanup.

Do not immediately delete the job or audit information.

Historical evidence is important during an investigation.

---

# 157. Container Security Incident

If unexpected container behavior is detected:

```text
Container Event
      ↓
Inspect Runtime
      ↓
Inspect Image
      ↓
Inspect Mounts
      ↓
Inspect Processes
      ↓
Inspect Logs
      ↓
Compare Configuration
      ↓
Contain
      ↓
Rebuild / Redeploy
      ↓
Verify
```

Useful checks include:

```bash
sudo docker inspect lums
```

```bash
sudo docker logs --tail 200 lums
```

```bash
sudo docker ps
```

The deployed image should be compared against the expected Git revision and build state.

---

# 158. Database Incident Handling

If unexpected database changes are detected:

1. Preserve the current database.
2. Create a verified copy.
3. Stop application writes if necessary.
4. Review audit records.
5. Review application logs.
6. Check SQLite integrity.
7. Check foreign-key integrity.
8. Determine whether the change was authorized.
9. Restore only through a controlled procedure if required.

Never overwrite the only database copy during an investigation.

---

# 159. Evidence Preservation

Security investigations should preserve relevant evidence.

Potential evidence includes:

* Docker logs.
* Nginx logs.
* systemd journal entries.
* LUMS audit records.
* SQLite database copies.
* Git history.
* Configuration files.
* Container metadata.
* Agent logs.
* Watcher logs.

Evidence should be copied before destructive troubleshooting actions.

Sensitive evidence must be protected and redacted before external sharing.

---

# 160. Responsible Security Reporting

A security report should contain:

* Short description.
* Affected component.
* Reproduction steps.
* Expected behavior.
* Actual behavior.
* Potential impact.
* Suggested mitigation.
* Relevant timestamps.
* Relevant logs with secrets removed.

Never include:

* Passwords.
* Client tokens.
* Private keys.
* Server secrets.
* Personal information.
* Complete production databases.
* Unredacted inventory information.

The report should contain enough information to reproduce and investigate the issue without exposing additional secrets.

---

# 161. Security Testing Philosophy

Security changes are not considered complete merely because the code compiles.

The LUMS validation workflow is:

```text
Change
  ↓
Syntax Check
  ↓
Unit Test
  ↓
Debian Test
  ↓
Arch Test
  ↓
Integration Test
  ↓
Git Review
  ↓
Production Deployment
  ↓
Production Verification
```

This workflow deliberately separates development validation from production validation.

---

# 162. Syntax Validation

Python changes should first pass a syntax check.

For example:

```bash
python3 -m py_compile server/app.py
```

and for agent code:

```bash
python3 -m py_compile agent/agent.py
```

The exact files depend on the change.

A syntax check is only the first validation layer.

---

# 163. Unit Testing

Security-sensitive logic should be testable independently.

Relevant areas include:

* Authentication.
* Rate limiting.
* Token hashing.
* Token rotation.
* Client state.
* Job claiming.
* Recovery.
* Timeout handling.
* Package-manager abstraction.
* Input validation.

Unit tests should avoid requiring production credentials or production databases.

---

# 164. Login Rate-Limit Tests

The login rate limiter has been tested for:

```text
1–4 failures
    ↓
No lock

5 failures
    ↓
30-second lock

6 failures
    ↓
60-second lock

7 failures
    ↓
120-second lock

8+ failures
    ↓
300-second lock
```

Additional tests covered:

* Independent rate-limit keys.
* Reset after successful authentication.
* Concurrent failures.
* Rollback behavior.
* Production end-to-end behavior.
* Audit events.

The concurrency implementation was explicitly tested after a first test exposed database locking and unique-constraint behavior.

---

# 165. SQLite Tests

SQLite hardening has been verified for:

```text
journal_mode = wal
busy_timeout = 5000
foreign_keys = 1
synchronous = 2
```

Database validation also includes:

```text
PRAGMA integrity_check
PRAGMA foreign_key_check
```

The production database passed the relevant integrity checks after the security changes.

---

# 166. Timeout Tests

Update execution timeout handling has been tested using controlled processes.

Test cases include:

* Silent child process.
* Timeout handling.
* Normal termination.
* SIGTERM-resistant process.
* Kill fallback.
* Simulated hanging package execution.
* Correct timeout result reporting.

The implementation uses selector-driven output handling so that timeout processing is not defeated by a blocking stdout read.

---

# 167. Recovery Tests

Job recovery has been tested using a controlled running job.

The tested transition was:

```text
running
   ↓
abandoned
```

Validation included:

* Completion timestamp.
* Recovery reason.
* Update history.
* Package statistics.
* Job state.
* Reboot state.
* Subsequent normal job execution.

The test data was removed after validation.

---

# 168. Authentication Tests

The authentication test model includes:

```text
No token
    → 401

Invalid token
    → 401

Revoked token
    → 401

Disabled client
    → 401

Valid token
    → accepted
```

Cross-client access must remain rejected.

For example:

```text
Client A requests Client B job
    → rejected

Client A submits Client B result
    → rejected

Client A reports as Client B
    → rejected
```

The exact status code depends on the endpoint's authorization behavior.

---

# 169. End-to-End Testing

The complete LUMS workflow should be tested as:

```text
1. LUMS server running
2. SQLite working
3. Nginx running
4. HTTPS working
5. Administrator login works
6. Agent starts
7. Client reports
8. Client appears
9. Package inventory is available
10. Updates are detected
11. Administrator creates update job
12. Job enters the execution workflow
13. Client claims job
14. Client executes update
15. Client reports result
16. Job reaches final state
17. Update history is created
18. Reboot state is recorded where applicable
```

This test validates the interaction between the management plane and execution plane.

---

# 170. Debian Validation

The Debian client has been validated against the current LUMS Agent 1.7.0.

The successful report included:

```text
PACKAGES355
UPDATES0
```

The client successfully communicated with the production server.

The execution workflow was also validated through the current watcher implementation.

---

# 171. Arch Linux Validation

The Arch Linux client has also been validated with Agent 1.7.0.

The package-manager abstraction uses:

```text
pacman
```

and the current test environment reported no available updates through:

```text
pacman -Qu
```

The client successfully reported to LUMS.

The Arch workflow therefore validates that the agent architecture is not limited to Debian-based systems.

---

# 172. Security Audit Workflow

Each security audit follows the same controlled process:

```text
Identify
   ↓
Inspect
   ↓
Design Fix
   ↓
Implement
   ↓
Syntax Check
   ↓
Unit Test
   ↓
Debian Test
   ↓
Arch Test
   ↓
Integration Test
   ↓
Production Verification
   ↓
Git Review
   ↓
Commit
```

This makes each security change independently traceable.

---

# 173. Completed Security Audit #1

## SQLite Foreign Keys and Client State

Implemented:

```python
PRAGMA foreign_keys = ON
```

Client lifecycle improvements include soft-disabling rather than immediately deleting active client state.

Disabling a client also records:

```text
enabled = 0
token_revoked_at = <timestamp>
```

Historical jobs and audit information remain available.

Validation included:

* Runtime foreign-key enforcement.
* Foreign-key integrity.
* Client disable behavior.
* Client authentication rejection.
* Historical data preservation.

Commit:

```text
a992da5
security: harden SQLite connection handling
```

---

# 174. Completed Security Audit #2

## SQLite WAL and Busy Timeout

Implemented:

```text
PRAGMA busy_timeout = 5000
PRAGMA journal_mode = WAL
```

alongside existing foreign-key enforcement.

Verified production state:

```text
journal_mode: wal
busy_timeout: 5000
synchronous: 2
foreign_keys: 1
```

Database integrity and foreign-key checks passed.

Commit:

```text
a992da5
security: harden SQLite connection handling
```

---

# 175. Completed Security Audit #3

## Update Timeout and Process Handling

The update execution implementation was hardened against blocking process output.

Implemented:

```text
Selector-driven output
        ↓
Timeout
        ↓
terminate()
        ↓
10-second grace period
        ↓
kill() fallback
```

Tests covered:

* Silent processes.
* Timeout.
* SIGTERM-resistant processes.
* Kill fallback.
* Integration timeout behavior.

The final agent version became:

```text
1.7.0
```

Commit:

```text
efe4049
security: harden package update timeout handling
```

---

# 176. Completed Security Audit #4

## Login Rate Limiting

Implemented persistent login rate limiting using migration:

```text
003-login-rate-limiting
```

Current lock progression:

```text
5  → 30 seconds
6  → 60 seconds
7  → 120 seconds
8+ → 300 seconds
```

The implementation uses:

```text
BEGIN IMMEDIATE
```

for concurrent failure updates.

Validated:

* Isolated rate-limit logic.
* Concurrent failures.
* Rollback.
* Production login behavior.
* Locking.
* Audit events.
* Reset after successful authentication.

Commit:

```text
6ef0abb
security: add login rate limiting
```

---

# 177. Current Audit Status

The completed security audits are:

```text
[x] SQLite Foreign Keys
[x] SQLite WAL / Busy Timeout
[x] Update Timeout / Process Handling
[x] Login Rate Limiting
```

The next security areas remain:

```text
[ ] API Input Validation
[ ] Session Revocation
[ ] Token Rotation Grace-Period Review
[ ] Client/API Rate Limiting
[ ] Migration Consolidation
[ ] Automated Test Suite
[ ] CI
[ ] Final Security Review
```

Some controls may already have partial implementation independent of their formal audit phase.

The documentation must distinguish between:

```text
Implemented
```

and:

```text
Fully audited and verified
```

---

# 178. Security Roadmap

The remaining roadmap is intentionally incremental.

## Phase 1 — API Input Validation

Review:

* JSON validation.
* Required fields.
* Data types.
* Invalid JSON behavior.
* Package input validation.
* Error handling.
* Authorization boundaries.

The goal is to ensure malformed client input results in controlled API responses.

---

## Phase 2 — Session Revocation

Evaluate server-side session revocation.

Potential states:

```text
Active
Revoked
Expired
```

The implementation should support incident response without weakening normal session handling.

---

## Phase 3 — Token Lifecycle Review

Client token rotation is already implemented.

Further review may evaluate:

* Token expiration.
* Token identifiers.
* Grace periods.
* Revocation state.
* Larger-deployment token storage requirements.

Any grace period must be designed carefully because it intentionally allows an old credential to remain temporarily valid.

---

## Phase 4 — Client/API Rate Limiting

The login endpoint already has persistent rate limiting.

Additional API rate limiting may be evaluated for:

* Client reports.
* Job requests.
* Job result submission.
* Authentication endpoints.
* Administrative operations.

The implementation should consider the low-volume laboratory environment as well as future larger deployments.

---

## Phase 5 — Migration Consolidation

LUMS currently contains both:

```text
Versioned migrations
```

and some older initialization-time schema handling.

The long-term goal is to consolidate schema evolution into one clearly defined migration model.

This reduces ambiguity when deploying future database versions.

---

## Phase 6 — Automated Security Tests

Automated regression tests should cover:

* Authentication.
* Authorization.
* Token handling.
* Client ownership.
* Job claiming.
* Job recovery.
* Rate limiting.
* Security headers.
* Database integrity.
* Container hardening.
* Secret handling.
* Package execution timeout.

The objective is to prevent previously fixed security issues from silently returning.

---

## Phase 7 — CI

Continuous integration should eventually execute the relevant automated checks for repository changes.

A future CI workflow may include:

```text
Push / Pull Request
        ↓
Syntax Check
        ↓
Unit Tests
        ↓
Security Tests
        ↓
Integration Tests
        ↓
Build Verification
```

Production deployment should remain a separate controlled step.

---

# 179. Backup and Restore Validation

Production SQLite backups have already been created and structurally verified.

A successful integrity check means:

```text
SQLite backup
    ↓
PRAGMA integrity_check
    ↓
ok
```

This does not prove that the application can be fully restored.

The remaining validation is therefore:

```text
Verified Backup
      ↓
Isolated Restore
      ↓
SQLite Integrity
      ↓
Schema Verification
      ↓
Application Startup
      ↓
Authentication
      ↓
Client Communication
      ↓
Job / Audit Verification
```

Only then can the complete backup/restore workflow be considered validated.

---

# 180. Security Maintenance

Security reviews should be repeated after:

* Application changes.
* Authentication changes.
* Authorization changes.
* Docker changes.
* Nginx changes.
* Certificate changes.
* Database schema changes.
* Agent changes.
* Watcher changes.
* Deployment changes.
* Secret changes.

Regular reviews should include:

```text
Docker images
Operating system updates
Python dependencies
Flask dependencies
Gunicorn
Nginx configuration
TLS certificates
File permissions
Database backups
Git history
Authentication
Authorization
Job execution
Package-manager coordination
Container privileges
Container capabilities
Secret handling
Secret rotation
```

---

# 181. Security Documentation Principle

The documentation must describe the actual implementation.

A security control must not be documented as complete merely because:

* It was planned.
* It exists in a design document.
* It exists in a branch.
* A partial implementation exists.
* A manual test was performed once without sufficient verification.

The documentation should distinguish:

```text
Planned
    ↓
Implemented
    ↓
Tested
    ↓
Production Verified
```

This prevents the documentation itself from becoming a source of false security assumptions.

---

# 182. Security Transparency

Known limitations should remain documented.

Examples include:

```text
APT/dpkg collision coordination
Session revocation
API rate limiting
Full backup/restore validation
Automated regression coverage
CI integration
```

A documented limitation is preferable to silently implying that the system provides a control that it does not actually provide.

---

# 183. Final Security Principles

The following principles define the LUMS security model:

1. Never store secrets in Git.
2. Never expose the Flask/Gunicorn application directly to the network.
3. Use HTTPS for client communication.
4. Keep TLS verification enabled.
5. Separate authentication from authorization.
6. Validate client identity server-side.
7. Protect client tokens.
8. Protect TLS private keys.
9. Keep production secrets outside normal source-controlled configuration.
10. Keep database backups protected.
11. Do not remove persistent volumes during routine troubleshooting.
12. Do not remove APT or dpkg lock files to force package operations.
13. Do not automatically reboot clients without an explicit execution policy.
14. Review security-sensitive changes before deployment.
15. Test security-sensitive changes independently.
16. Verify production behavior after deployment.
17. Preserve audit information during incident handling.
18. Never expose credentials in logs or documentation.
19. Treat previously exposed secrets as compromised until rotated.
20. Keep update execution controlled and auditable.
21. Do not confuse authentication with authorization.
22. Do not trust frontend state as an authorization mechanism.
23. Do not claim incomplete security controls as fully implemented.
24. Preserve historical operational data where appropriate.
25. Treat security hardening as a continuous process.

---

# 184. Final Verified Security Model

The current LUMS architecture separates management and execution responsibilities:

```text
                    MANAGEMENT PLANE
                           │
                           ▼
                       Nginx / TLS
                           │
                           ▼
                    Gunicorn / Flask
                           │
              ┌────────────┴────────────┐
              │                         │
        Authentication             Authorization
              │                         │
              └────────────┬────────────┘
                           │
                           ▼
                         SQLite
                           │
                           │
                    EXECUTION PLANE
                           │
                           ▼
                    LUMS Agent 1.7.0
                           │
                           ▼
               Execution Watcher
                           │
                    Idle Detection
                           │
                    Atomic Job Claim
                           │
                           ▼
                 Package Manager
                  ┌────────┴────────┐
                  │                 │
                 APT             pacman
                  │                 │
                  ▼                 ▼
                Debian            Arch
```

The separation allows LUMS to manage update operations centrally while leaving package execution on the managed client.

---

# 185. Final Security Workflow

The established LUMS security workflow is:

```text
Inspect
   ↓
Understand
   ↓
Design
   ↓
Implement
   ↓
Syntax Check
   ↓
Unit Test
   ↓
Debian Test
   ↓
Arch Test
   ↓
Integration Test
   ↓
Production Deployment
   ↓
Production Verification
   ↓
Git Review
   ↓
Document
```

No security-sensitive change should be deployed blindly.

---

# 186. Final Security Statement

LUMS is designed to centralize Linux update management without removing operational control from the administrator.

The system remains:

```text
Transparent
Auditable
Controlled
Secure
Documented
Maintainable
```

Security improvements are implemented one controlled layer at a time.

The objective is not to claim that LUMS is perfectly secure.

The objective is to make every security boundary explicit, testable, reviewable, and maintainable.

---

# 187. Final Architecture

The current verified security architecture is:

```text
Internet / LAN
      │
      ▼
   Nginx
   HTTPS
      │
      ▼
127.0.0.1:5050
      │
      ▼
 Docker Container
 ┌──────────────────────────────┐
 │ non-root                     │
 │ capabilities: NONE           │
 │ root filesystem: READ-ONLY   │
 │                              │
 │ /tmp → tmpfs                 │
 │                              │
 │ /var/lib/lums → lums-data    │
 │                              │
 │ /run/secrets/lums_secret     │
 │             → READ-ONLY      │
 │                              │
 │ Gunicorn → Flask             │
 └──────────────────────────────┘
      │
      ▼
    SQLite
```

The execution side remains:

```text
LUMS Server
      │
      ▼
Authenticated Client
      │
      ▼
Execution Watcher
      │
      ▼
Idle Detection
      │
      ▼
Atomic Job Claim
      │
      ▼
APT / pacman
      │
      ▼
Controlled Update
      │
      ▼
Validated Result
      │
      ▼
Audit History
```

---

# 188. Final Security Principles — Summary

```text
ONE LUMS
ONE SECURITY MODEL

AUTHENTICATE
      ↓
AUTHORIZE
      ↓
VALIDATE
      ↓
EXECUTE
      ↓
VERIFY
      ↓
AUDIT
      ↓
DOCUMENT
```

And the project principle remains:

> **Linux Update Management without the noise.**

The security principle is equally simple:

> **One change. One test. One verified result.**
