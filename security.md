# LUMS Security Documentation

**LUMS — Linux Update Management Server**

This document describes the current security architecture, implemented security controls, security audit results, operational limitations, and security-related design decisions of LUMS.

The document reflects the **currently implemented system state**. Planned or future improvements are explicitly identified as such.

---

# Security Principles

LUMS follows a defense-in-depth approach for Linux update management.

The security model separates administrative authentication, client authentication, authorization, controlled update execution, and audit logging.

The primary security goals are:

* authenticated administrative access
* role-based authorization
* authenticated client communication
* controlled update execution
* protection against concurrent job execution
* recoverable update jobs
* protected secrets
* controlled container execution
* auditable security-sensitive operations
* predictable failure handling
* security regression testing

LUMS is intended primarily for controlled infrastructure, laboratory, and internal network environments.

It should not be exposed directly to the public Internet without an additional security review and appropriate network controls.

---

# Security Architecture

LUMS consists of the following security-relevant components:

* Web administration interface
* REST API
* SQLite database
* LUMS Agent on managed clients
* APT and pacman package-management backends
* Update-job and recovery mechanisms
* Nginx HTTPS reverse proxy
* Hardened Docker container

The basic management flow is:

Browser → HTTPS/Nginx → LUMS API → SQLite → LUMS Agent → Package Manager → Result → SQLite → Web UI

Authentication and authorization are deliberately separated.

A valid authenticated session does not automatically grant access to every administrative operation.

Authorization is enforced server-side. The web interface additionally hides functions that are not available to the current role, but UI visibility is never treated as a security boundary.

---

## Administrative Authentication

Administrative users authenticate through the LUMS web interface.

Passwords are never stored in plaintext. LUMS uses Argon2-based password hashing for password storage.

Administrative sessions use:

* authenticated server-side session handling
* session expiration
* session regeneration
* CSRF protection for state-changing browser requests
* login rate limiting
* session invalidation during logout
* server-side role validation

Authentication and authorization remain separate security controls.

A successfully authenticated user must still possess the required role for protected operations.

---

# Role-Based Access Control

LUMS currently supports three web-user roles:

* `administrator`
* `operator`
* `viewer`

Roles are stored server-side in the `users.role` database field.

The server determines the effective role from the authenticated session. Client-side role information is used only to control presentation of the web interface and never replaces server-side authorization.

## Administrator

Administrators have full administrative and operational access.

They can:

* view clients
* create clients
* disable clients
* rotate client tokens
* view installed packages and available updates
* create update jobs
* execute supported update operations
* view update-job history
* use package management
* use system-maintenance functions
* manage users
* manage user roles
* access administrative functions

## Operator

Operators can perform operational update-management tasks.

They can:

* view clients
* view installed packages and available updates
* create update jobs
* execute supported update operations
* view update-job history
* use package management
* use system-maintenance functions

Operators cannot:

* manage users
* change user roles
* create clients
* disable clients
* rotate client tokens

## Viewer

Viewers have restricted read-only access.

They can:

* view clients
* view installed software

The following management areas are hidden from Viewer accounts:

* Updates
* Update Jobs
* Update History
* Package Management
* System Maintenance

Viewer accounts cannot perform state-changing update-management operations.

The server independently enforces these restrictions through authentication and role authorization.

---

# Client Authentication

Every managed LUMS client uses an individual Bearer token.

The authentication mechanism follows the model:

`Authorization: Bearer <CLIENT_TOKEN>`

The server does not store client tokens as plaintext values.

Instead, LUMS stores a SHA-256 hexadecimal digest of the client token.

The authentication flow is:

Client Token → SHA-256 → Token Digest → SQLite

Client authentication verifies the authenticated token against the registered client and additionally checks the relevant client state.

The security model does not use a source IP address as the sole proof of client identity.

This allows LUMS to operate in:

* private laboratory networks
* isolated infrastructure
* NAT-based networks
* offline environments
* networks where client addresses may change

Client tokens can be rotated by authorized administrators.

A token rotation generates a replacement token, stores only its digest, invalidates the previous token, records the administrative action in the audit log, and presents the replacement token once.

Plaintext client-token values are not written to audit records.

---

# Security Audit

The security audit is performed incrementally.

Each audit area is reviewed against the actual implementation, followed by automated tests, isolated verification, or production verification where applicable.

Current audit areas:

| Audit | Area                                   | Status                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | SQLite Foreign Keys                    | PASS                      |
| #02   | SQLite Runtime Configuration           | PASS                      |
| #03   | Update Timeout Handling                | PASS                      |
| #04   | Login Rate Limiting                    | PASS                      |
| #05   | API Input Validation                   | PASS                      |
| #06   | Session Revocation                     | PASS                      |
| #07   | Client Token Rotation                  | PASS                      |
| #08   | IP Address Handling / Offline Networks | PASS                      |
| #09   | Job Recovery / Checkpointing           | PASS                      |
| #10   | APT Robustness                         | PASS                      |
| #11   | Arch Reboot Detection                  | PASS                      |
| #12   | Unit Tests / API Result Validation     | PASS                      |
| #13   | Simulation Tests                       | PASS                      |
| #14   | Continuous Integration                 | PASS                      |
| #15   | Application / Audit Logging            | PASS                      |
| #16   | Versioning / Releases                  | REVIEWED — OPEN BY DESIGN |
| #17   | Role-Based Access Control              | PASS                      |
| #18   | Documentation Review                   | IN PROGRESS               |

Audit #16 is intentionally different from the technical security controls above.

LUMS currently has no official stable release, no release tag, and no GitHub Release. This is intentional because the project remains under active development.

Audit #18 remains open until the complete documentation set has been reviewed and synchronized with the current implementation.

# Security Audit #01

## SQLite Foreign Keys

SQLite foreign-key enforcement is enabled for application database connections.

The application explicitly enables:

`PRAGMA foreign_keys = ON`

This ensures that referential integrity is enforced for relationships between related database records.

The audit verified:

* runtime foreign-key enforcement
* foreign-key integrity
* client lifecycle behavior
* client disable behavior
* preservation of historical job information
* preservation of audit information

Client state is handled conservatively.

Where appropriate, clients are disabled rather than removed in a way that would destroy historical operational information.

**Status: PASS**

---

# Security Audit #02

## SQLite Runtime Configuration

The production SQLite database was reviewed for its runtime configuration.

The verified production configuration is:

* `journal_mode`: `delete`
* `busy_timeout`: `5000`
* `synchronous`: `2`

The application explicitly enables:

`PRAGMA foreign_keys = ON`

The production database therefore does **not** currently use WAL mode.

The database configuration was documented based on the actual verified production state rather than the historical development configuration.

The configured busy timeout reduces immediate database failures when another transaction temporarily holds the database.

The application-level foreign-key setting ensures referential integrity for each database connection.

The audit included production verification of the active SQLite configuration.

**Status: PASS**

---

# Security Audit #03

## Update Timeout and Process Handling

Update execution is protected against indefinitely blocking package-manager processes.

The execution flow is:

Start process
↓
Read process output
↓
Monitor timeout
↓
Timeout reached?
↓
Terminate process
↓
Grace period
↓
Process still running?
↓
Kill process if required
↓
Complete job

The implementation uses controlled subprocess handling so that silent processes cannot block indefinitely while waiting for output.

Timeout handling was tested against:

* silent processes
* normal process completion
* timeout conditions
* processes resistant to normal termination
* kill fallback
* integration-level timeout behavior

The timeout mechanism prevents a package-management operation from remaining indefinitely in an active state.

Errors and timeout conditions are returned as controlled job results and are recorded in the job state.

The current documented LUMS Agent version is:

`1.7.0`

**Status: PASS**

---

# Security Audit #04

## Login Rate Limiting

Administrative login attempts are rate limited.

The current escalation policy is:

* 5 failed attempts → 30 seconds
* 6 failed attempts → 60 seconds
* 7 failed attempts → 120 seconds
* 8 or more failed attempts → 300 seconds

The rate-limit state is persisted in SQLite.

Concurrent login failures use transactional database locking with:

`BEGIN IMMEDIATE`

This prevents concurrent authentication failures from bypassing the intended rate-limit state through race conditions.

A successful authentication clears the applicable failure state.

The audit covered:

* isolated rate-limit behavior
* concurrent authentication failures
* transaction rollback
* database-lock handling
* successful-login reset behavior
* rate-limit audit events
* production login behavior

The rate limiter therefore provides a server-side control against repeated authentication attempts rather than relying on client-side behavior.

**Status: PASS**

---

# Audit Status After Part 2

The first four security audit areas are complete:

| Audit | Area                              | Status |
| ----- | --------------------------------- | ------ |
| #01   | SQLite Foreign Keys               | PASS   |
| #02   | SQLite Runtime Configuration      | PASS   |
| #03   | Update Timeout / Process Handling | PASS   |
| #04   | Login Rate Limiting               | PASS   |

The following audit areas are documented in the subsequent sections:

* #05 API Input Validation
* #06 Session Revocation
* #07 Client Token Rotation
* #08 IP Address Handling / Offline Networks
* #09 Job Recovery / Checkpointing
* #10 APT Robustness
* #11 Arch Reboot Detection
* #12 Unit Tests / API Result Validation
* #13 Simulation Tests
* #14 Continuous Integration
* #15 Application / Audit Logging
* #16 Versioning / Releases
* #17 Role-Based Access Control

Audit #18 — Documentation Review — remains open until the complete documentation set has been reviewed and synchronized with the current implementation.

# Security Audit #05

## API Input Validation

LUMS validates security-sensitive API input on the server side.

Client-supplied values are not trusted simply because they originate from the authenticated web interface or a registered client.

Validation is applied to relevant API parameters, including:

* client identifiers
* package names
* update-job actions
* package lists
* search parameters
* user-management parameters
* client-token operations
* job-result data

Package names are validated before they are passed to package-management operations.

The update-job API accepts only explicitly supported actions.

The currently supported package-related actions are:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Unexpected actions are rejected.

Package lists are validated before job creation.

For `UPDATE_PACKAGE`, the requested package must also be present in the client's available-update information.

Database queries use parameterized SQL rather than constructing SQL statements from untrusted input.

This prevents user-controlled values from being interpreted as SQL syntax.

The audit included negative input testing and SQL-injection-oriented test cases.

The validation controls were also verified through the automated test suite.

**Status: PASS**

---

# Security Audit #06

## Session Revocation

LUMS protects authenticated administrative sessions against continued use after logout.

Session handling includes:

* authenticated server-side sessions
* session expiration
* session regeneration
* logout invalidation
* server-side authentication checks
* server-side role validation

Logging out invalidates the active authenticated session.

Protected API endpoints require an authenticated session and do not rely on client-side state to determine whether the user remains authenticated.

Session state is therefore evaluated by the server for protected operations.

State-changing browser requests additionally require CSRF protection.

The audit verified that:

* authenticated access works normally
* protected endpoints reject unauthenticated requests
* logout invalidates the active session
* a previously authenticated session cannot continue using protected functionality after revocation
* role information is evaluated server-side

**Status: PASS**

---

# Security Audit #07

## Client Token Rotation

Each managed LUMS client uses an individual authentication token.

Client tokens are not stored as plaintext values.

Instead, LUMS stores the SHA-256 hexadecimal digest of the client token.

The authentication model is:

`Authorization: Bearer <CLIENT_TOKEN>`

The server hashes the supplied token and compares the resulting digest with the registered client token digest.

Authorized administrators can rotate a client's token.

Token rotation performs the following operations:

1. Generate a replacement token.
2. Calculate its SHA-256 digest.
3. Replace the stored client-token digest.
4. Invalidate the previous token.
5. Record the administrative action in the audit log.
6. Present the replacement token to the administrator.

The previous token cannot authenticate after rotation.

Plaintext token values are not written to audit logs.

The audit verified:

* successful token authentication
* token digest storage
* token rotation
* invalidation of the previous token
* authentication with the replacement token
* authorization requirements for token rotation
* audit logging
* protection against unauthorized rotation

Client token rotation is restricted to administrators.

Operators and viewers cannot rotate client tokens.

**Status: PASS**

---

# Security Audit #08

## IP Address Handling and Offline Networks

LUMS does not use a client's source IP address as the sole proof of client identity.

Client authentication is based on the registered client token.

This design is intentional because managed clients may operate in environments where their network address changes.

Supported deployment scenarios include:

* private laboratory networks
* NAT-based networks
* isolated infrastructure
* dynamically addressed clients
* offline environments
* controlled internal networks

The server therefore separates:

**Network location**

from:

**Client identity**

A valid client token identifies the registered client.

The client's network address may still be recorded for operational and audit purposes, but it is not treated as an authentication credential.

The implementation also avoids assumptions that a client must be reachable from a fixed address.

This is particularly important for laboratory environments and infrastructure where network topology may change without changing the logical identity of the managed system.

The audit verified client authentication without relying on a fixed source IP address.

**Status: PASS**

---

# Audit Status After Part 3

The following security audit areas are complete:

| Audit | Area                                   | Status |
| ----- | -------------------------------------- | ------ |
| #01   | SQLite Foreign Keys                    | PASS   |
| #02   | SQLite Runtime Configuration           | PASS   |
| #03   | Update Timeout / Process Handling      | PASS   |
| #04   | Login Rate Limiting                    | PASS   |
| #05   | API Input Validation                   | PASS   |
| #06   | Session Revocation                     | PASS   |
| #07   | Client Token Rotation                  | PASS   |
| #08   | IP Address Handling / Offline Networks | PASS   |

The next section covers:

* #09 Job Recovery / Checkpointing
* #10 APT Robustness
* #11 Arch Reboot Detection
* #12 Unit Tests / API Result Validation

# Security Audit #09

## Job Recovery and Checkpointing

LUMS update jobs are designed to recover safely from interrupted execution.

Update jobs maintain persistent state in the SQLite database.

Individual package operations are tracked separately from the overall job state.

This allows the Agent to determine which package operations have already completed successfully before an interrupted job is resumed.

During recovery, successfully completed package operations are not executed again.

The recovery logic therefore follows the principle:

`Persistent Job State → Determine Completed Work → Skip Completed Items → Continue Remaining Work`

This reduces the risk of unnecessary repeated package operations after:

* agent interruption
* process termination
* system restart
* temporary communication failure
* container restart
* other execution interruptions

The audit verified interrupted-job recovery and checkpoint behavior.

Recovery was tested with jobs containing multiple package operations and with previously successful package items.

The audit confirmed that completed work is preserved and remaining work can continue without unnecessarily repeating successful operations.

**Status: PASS**

---

# Security Audit #10

## APT Robustness

Debian-based package operations are executed through the LUMS package-management layer.

APT-related update operations were reviewed for reliable detection of package-manager state and update results.

The implementation accounts for cases where package-management commands may return successfully while requiring additional interpretation of their output or resulting system state.

APT update detection was hardened to avoid relying on a single simplistic command-output condition.

The audit included testing of:

* normal APT operations
* available package updates
* package installation
* package removal
* update-job execution
* APT result handling
* update detection behavior

The corresponding hardening was committed as:

`c76f331 security: harden apt update detection`

The objective is to ensure that LUMS does not incorrectly report package-management state based solely on incomplete or ambiguous command output.

**Status: PASS**

---

# Security Audit #11

## Arch Linux Reboot Detection

Arch Linux package operations can result in a system state where a reboot is required or recommended.

LUMS therefore evaluates the resulting system state after relevant package-management operations.

The Agent distinguishes normal package-operation completion from situations where a reboot is required.

The reboot state is reported back to the LUMS server as part of the job result.

This allows the management interface to distinguish between:

* successful package operation
* successful operation with reboot requirement
* failed operation

The audit verified Arch Linux reboot detection using the actual package-management execution path.

The implementation was tested against reboot-required conditions and normal completion conditions.

**Status: PASS**

---

# Security Audit #12

## Unit Tests and API Result Validation

Security-sensitive behavior is covered by automated tests.

The test suite includes coverage for authentication, authorization, API validation, update jobs, package management, client authentication, and result handling.

The Agent-to-server result path was specifically reviewed to ensure that job results cannot arbitrarily alter unrelated server-side state.

Result processing validates the submitted information before applying state changes to the corresponding update job.

The validation covers relevant result fields and expected job relationships.

This prevents an authenticated client from freely selecting unrelated jobs or injecting arbitrary state into the update-job database.

The security test suite also covers negative and unauthorized cases.

The current full automated test suite contains:

`155 passed`

The test suite was executed successfully after the RBAC and Viewer-access changes.

The relevant security controls were additionally verified through focused test runs during the audit.

**Status: PASS**

---

# Audit Status After Part 4

The following security audit areas are complete:

| Audit | Area                                   | Status |
| ----- | -------------------------------------- | ------ |
| #01   | SQLite Foreign Keys                    | PASS   |
| #02   | SQLite Runtime Configuration           | PASS   |
| #03   | Update Timeout / Process Handling      | PASS   |
| #04   | Login Rate Limiting                    | PASS   |
| #05   | API Input Validation                   | PASS   |
| #06   | Session Revocation                     | PASS   |
| #07   | Client Token Rotation                  | PASS   |
| #08   | IP Address Handling / Offline Networks | PASS   |
| #09   | Job Recovery / Checkpointing           | PASS   |
| #10   | APT Robustness                         | PASS   |
| #11   | Arch Reboot Detection                  | PASS   |
| #12   | Unit Tests / API Result Validation     | PASS   |

The next section covers:

* #13 Simulation Tests
* #14 Continuous Integration
* #15 Application / Audit Logging
* #16 Versioning / Releases

# Security Audit #13

## Simulation Tests

LUMS provides a simulation mechanism for testing update-management workflows without performing the corresponding package-management operation on the managed system.

Simulation is implemented at the Agent execution layer.

When simulation is enabled, package-management operations are represented and processed without applying the requested package change to the operating system.

This allows update-job behavior to be tested without intentionally modifying the managed system.

The simulation tests cover relevant update-management paths, including:

* package installation
* package removal
* package updates
* system updates
* job execution
* result reporting
* successful completion
* failure handling

The simulation mechanism was used during the security audit to verify job creation, Agent execution, result handling, and server-side state transitions independently from real package modifications.

Simulation mode is a testing mechanism and does not replace the authorization controls of normal update operations.

**Status: PASS**

---

# Security Audit #14

## Continuous Integration

LUMS uses automated testing to detect security and functional regressions before changes are considered complete.

The CI process executes the automated test suite against the project.

The test environment verifies the application and security-sensitive functionality independently from the production container.

The CI process includes validation of:

* authentication
* authorization
* RBAC
* API behavior
* update-job handling
* package-management behavior
* client authentication
* job-result validation
* security-sensitive error handling

The CI audit was reviewed after the security hardening changes.

The final verified test suite completed successfully.

The current full test result is:

`155 passed`

CI therefore provides an automated regression barrier for security-relevant application changes.

**Status: PASS**

---

# Security Audit #15

## Application and Audit Logging

LUMS records security-sensitive administrative and operational events through application-level audit logging.

Audit logging is designed to provide an operational history without storing sensitive credentials.

Relevant security-sensitive actions include events such as:

* authentication-related security events
* administrative actions
* client management
* client-token operations
* update-job creation
* update-job execution
* security-relevant failures

Sensitive credential material is excluded from audit records.

In particular:

* passwords are not logged
* plaintext client tokens are not logged
* secret values are not intentionally written to audit records

Audit records are associated with the relevant administrative or operational context where applicable.

The audit logging implementation was reviewed for:

* security-sensitive event coverage
* credential exclusion
* administrative traceability
* failure handling
* persistence of relevant audit information

The logging system is intended to support both operational troubleshooting and security investigation.

**Status: PASS**

---

# Security Audit #16

## Versioning and Releases

Versioning and release management were reviewed as part of the security audit.

LUMS is currently under active development and does not yet have an official stable release.

The current repository state therefore intentionally has:

* no official stable release version
* no release tag
* no GitHub Release

The current component versions include:

* LUMS Agent: `1.7.0`
* LUMS Watcher: `1.2.1`

There is currently no single formal version number representing the complete LUMS application.

This is an intentional project-state decision rather than an accidental omission.

The planned release process is:

1. Complete implementation work.
2. Complete the security review.
3. Review and synchronize the documentation.
4. Complete the full automated test suite.
5. Verify CI.
6. Define the release version.
7. Create the corresponding Git tag.
8. Publish the GitHub Release.
9. Preserve the release as the documented baseline.

No official release is created solely because the security audit reaches a particular audit number.

Release creation will take place only after the remaining implementation and documentation work has been completed.

**Status: REVIEWED — OPEN BY DESIGN**

---

# Audit Status After Part 5

The following security audit areas are complete:

| Audit | Area                                   | Status                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | SQLite Foreign Keys                    | PASS                      |
| #02   | SQLite Runtime Configuration           | PASS                      |
| #03   | Update Timeout / Process Handling      | PASS                      |
| #04   | Login Rate Limiting                    | PASS                      |
| #05   | API Input Validation                   | PASS                      |
| #06   | Session Revocation                     | PASS                      |
| #07   | Client Token Rotation                  | PASS                      |
| #08   | IP Address Handling / Offline Networks | PASS                      |
| #09   | Job Recovery / Checkpointing           | PASS                      |
| #10   | APT Robustness                         | PASS                      |
| #11   | Arch Reboot Detection                  | PASS                      |
| #12   | Unit Tests / API Result Validation     | PASS                      |
| #13   | Simulation Tests                       | PASS                      |
| #14   | Continuous Integration                 | PASS                      |
| #15   | Application / Audit Logging            | PASS                      |
| #16   | Versioning / Releases                  | REVIEWED — OPEN BY DESIGN |

The remaining numbered technical audit area is:

* #17 Role-Based Access Control

The documentation review is tracked separately as:

* #18 Documentation Review — IN PROGRESS

# Security Audit #17

## Role-Based Access Control

LUMS implements server-side Role-Based Access Control (RBAC) for administrative users.

The currently supported roles are:

* `administrator`
* `operator`
* `viewer`

The authenticated user's role is stored in the server-side session and is evaluated by protected routes.

The web interface may hide functionality that is unavailable to the current role, but this is only a usability measure.

The user interface is not considered a security boundary.

All security-sensitive authorization decisions are enforced server-side.

---

## RBAC Permission Model

| Function                  | Administrator | Operator | Viewer |
| ------------------------- | ------------: | -------: | -----: |
| View clients              |           Yes |      Yes |    Yes |
| View installed software   |           Yes |      Yes |    Yes |
| View available updates    |           Yes |      Yes |     No |
| Create update jobs        |           Yes |      Yes |     No |
| Execute update operations |           Yes |      Yes |     No |
| View update-job history   |           Yes |      Yes |     No |
| Package Management        |           Yes |      Yes |     No |
| System Maintenance        |           Yes |      Yes |     No |
| Create clients            |           Yes |       No |     No |
| Disable clients           |           Yes |       No |     No |
| Rotate client tokens      |           Yes |       No |     No |
| User Management           |           Yes |       No |     No |
| Change user roles         |           Yes |       No |     No |

Viewer accounts therefore provide intentionally limited read-only access.

Viewer users can access client information and installed software, but they cannot access the operational update-management areas.

---

## Authorization Enforcement

Protected operations use server-side authentication and role checks.

The authorization model follows the principle:

`Authenticate → Determine Role → Authorize Operation → Execute`

Authentication alone is not sufficient to access privileged operations.

State-changing operations additionally require CSRF protection where applicable.

Examples of protected administrative operations include:

* update-job creation
* package installation
* package removal
* package updates
* system updates
* package-management operations
* client creation
* client disabling
* client-token rotation
* user creation
* user-management functions

Protected endpoints explicitly define the roles that are permitted to perform the corresponding operation.

An unauthorized role is rejected by the server even if the user manually constructs the corresponding HTTP request.

This prevents bypassing the RBAC model by directly calling an API endpoint that is hidden in the web interface.

---

## Viewer Restrictions

Viewer access was reviewed separately because the Viewer role is intentionally restricted.

For Viewer sessions, the client interface does not expose:

* Updates
* Update Jobs
* Update History
* Package Management
* System Maintenance

The server additionally prevents Viewer accounts from performing the corresponding protected operations.

The JavaScript interface does not load privileged update-management data for Viewer sessions.

This reduces unnecessary exposure of operational information while maintaining server-side authorization as the actual security control.

Installed software remains available to Viewer accounts as a read-only information function.

---

## Administrative User Management

User management is restricted to Administrators.

Administrators can create users and assign supported roles.

User creation includes:

* username validation
* role validation
* password validation
* Argon2 password hashing
* duplicate-user detection
* audit logging
* CSRF protection
* server-side authorization

User-management endpoints are not accessible to Operators or Viewers.

Passwords are never stored in plaintext.

---

## RBAC Database Migration

Role information is stored in the user database record.

The application validates supported role values before storing them.

The RBAC database migration introduced the role information required by the authorization model while preserving existing user accounts.

Database-level constraints and application-level validation work together to prevent unsupported role values from becoming active authorization states.

---

## RBAC Security Testing

RBAC behavior is covered by automated tests.

The tests include:

* Administrator authorization
* Operator authorization
* Viewer restrictions
* protected API access
* unauthorized operations
* client-management restrictions
* update-job restrictions
* user-management restrictions
* client-page visibility
* role-specific interface behavior

Focused RBAC testing was performed after the Viewer-RBAC changes.

The complete RBAC test suite passed with:

`45 passed`

The complete application test suite subsequently passed with:

`155 passed`

The production deployment was additionally verified with separate Administrator, Operator, and Viewer accounts.

The production Viewer interface was verified to expose only the functionality intended for the Viewer role.

---

## RBAC Security Result

The RBAC implementation provides layered authorization:

1. Authentication establishes the user identity.
2. The server determines the user's role.
3. Protected routes enforce the required role.
4. CSRF protection applies to relevant browser state changes.
5. The web interface hides unavailable functionality.
6. Automated tests verify authorization boundaries.

The interface therefore does not provide the authorization mechanism by itself.

The server remains the authoritative security boundary.

**Status: PASS**

# Security Audit #18

## Documentation Review

The security documentation is reviewed against the currently implemented LUMS system.

The purpose of this review is to ensure that security documentation describes the actual implementation rather than an earlier development state.

The review covers:

* authentication
* authorization
* RBAC
* client authentication
* token handling
* session handling
* CSRF protection
* rate limiting
* SQLite configuration
* update execution
* job recovery
* package management
* container hardening
* network exposure
* secrets handling
* dependency and build security
* filesystem permissions
* application and audit logging
* versioning and release handling
* automated security testing

Documentation must distinguish between:

* implemented controls
* verified production behavior
* planned improvements
* intentionally open project decisions

Historical implementation details must not be presented as current production configuration.

In particular, the documentation reflects the current SQLite production configuration rather than the previously used WAL configuration.

The current production runtime is documented as:

* `journal_mode = delete`
* `busy_timeout = 5000`
* `synchronous = 2`
* application-level `PRAGMA foreign_keys = ON`

The current Viewer-RBAC behavior is also documented according to the implemented production interface.

Viewer users have access to:

* client information
* installed software

Viewer users do not have access to:

* Updates
* Update Jobs
* Update History
* Package Management
* System Maintenance

The documentation review also removes or replaces outdated references to earlier test counts, migration states, deployment configurations, and development-only behavior.

**Status: IN PROGRESS**

---

# Additional Security Hardening

The numbered security audit covers the primary application security controls.

Additional hardening was performed after the original audit sequence and is part of the current security baseline.

These controls are documented here because they represent important security properties of the current deployment.

---

## Container Hardening

The production LUMS container runs with a hardened Docker configuration.

The production container uses:

* non-root application user
* read-only root filesystem
* dropped Linux capabilities
* `no-new-privileges`
* restricted temporary filesystems
* read-only secret mount
* dedicated persistent application-data volume
* restart policy
* loopback-only host publication of the application port

The application root filesystem is therefore not writable during normal operation.

Writable locations are explicitly limited to the locations required by the application.

The production container was independently inspected to verify the effective runtime configuration.

The hardened runtime was also tested by verifying that:

* application filesystem writes fail
* `/tmp` remains available where required
* `/var/lib/lums` remains writable
* the secret file remains read-only
* the application remains operational

---

## Network Exposure

The LUMS application port is not directly exposed to the LAN.

The Docker application port is bound to the loopback interface:

`127.0.0.1:5050`

External access is provided through Nginx.

The production host exposes the intended network services through the firewall and reverse proxy.

The deployment was verified to prevent direct remote access to the internal Docker application port.

The firewall uses a default-deny model for incoming and routed traffic.

The intended externally reachable services are:

* SSH
* HTTP
* HTTPS

HTTP requests are redirected to HTTPS by the web server.

The default Nginx site was removed so that unrelated default content is not exposed.

---

## Transport Security

Administrative web access is provided through HTTPS.

HTTP is redirected to HTTPS.

The TLS endpoint is handled by Nginx rather than the Flask/Gunicorn application directly.

This keeps transport security and application serving separated.

The internal Gunicorn application port is therefore not intended to be a public HTTP endpoint.

The current deployment is intended for controlled internal infrastructure.

A future deployment with direct public-Internet exposure would require an additional security review.

---

## Secrets and Configuration

Production secrets are not stored in the application source tree.

The LUMS secret key is supplied through a protected secret file.

The production container receives the secret through:

`/run/secrets/lums_secret`

The secret file is mounted read-only.

The application reads the secret through the configured secret-file mechanism.

Repository and Docker build-context handling was reviewed to prevent accidental inclusion of:

* database files
* backup files
* secret files
* private keys
* certificates
* runtime logs
* local backup artifacts

The repository also ignores common temporary backup patterns used during development.

---

## Dependency and Build Security

The production Docker image uses a pinned Python base-image digest.

The production runtime dependencies are explicitly version-pinned.

The current production dependency set includes:

* Flask `3.1.3`
* argon2-cffi `25.1.0`
* Gunicorn `23.0.0`

The Docker build context is restricted through `.dockerignore`.

Repeated production builds were compared during the audit.

The relevant dependency and package metadata remained consistent between repeated builds, apart from expected generated Python bytecode differences.

This provides a reproducible baseline for the production image while keeping the build context limited.

---

## Filesystem and Runtime Permissions

The production application runs as the dedicated `lums` user rather than root.

Persistent application data is stored in the dedicated LUMS data volume.

The application root filesystem is read-only.

Runtime write access is restricted to explicitly required locations.

The production runtime was verified to reject unauthorized writes to the application filesystem.

This reduces the impact of accidental or malicious file modification inside the application container.

---

# Security Audit Conclusion

The current LUMS implementation has undergone a broad security review covering:

* authentication
* authorization
* RBAC
* session security
* CSRF protection
* login rate limiting
* client-token security
* API validation
* SQL injection resistance
* SQLite integrity
* update execution
* timeout handling
* job recovery
* package-management robustness
* result validation
* simulation
* continuous integration
* audit logging
* container hardening
* network exposure
* transport security
* secrets handling
* filesystem permissions
* dependency and build security

The numbered audit results are:

| Audit | Area                                   | Status                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | SQLite Foreign Keys                    | PASS                      |
| #02   | SQLite Runtime Configuration           | PASS                      |
| #03   | Update Timeout / Process Handling      | PASS                      |
| #04   | Login Rate Limiting                    | PASS                      |
| #05   | API Input Validation                   | PASS                      |
| #06   | Session Revocation                     | PASS                      |
| #07   | Client Token Rotation                  | PASS                      |
| #08   | IP Address Handling / Offline Networks | PASS                      |
| #09   | Job Recovery / Checkpointing           | PASS                      |
| #10   | APT Robustness                         | PASS                      |
| #11   | Arch Reboot Detection                  | PASS                      |
| #12   | Unit Tests / API Result Validation     | PASS                      |
| #13   | Simulation Tests                       | PASS                      |
| #14   | Continuous Integration                 | PASS                      |
| #15   | Application / Audit Logging            | PASS                      |
| #16   | Versioning / Releases                  | REVIEWED — OPEN BY DESIGN |
| #17   | Role-Based Access Control              | PASS                      |
| #18   | Documentation Review                   | IN PROGRESS               |

The technical security controls reviewed in audits #01–#15 and #17 have passed.

Audit #16 remains intentionally open because LUMS has not yet reached its first official stable release.

Audit #18 remains open until the complete project documentation has been reviewed and synchronized with the final implementation state.

No security audit result should be interpreted as a guarantee that LUMS is free from vulnerabilities.

Security is an ongoing process.

Changes to the application, Agent, dependencies, container configuration, network exposure, authentication model, or deployment architecture should trigger another security review of the affected controls.

---

# Security Baseline

The current security baseline is based on the verified implementation and production deployment state.

The baseline includes:

* server-side authentication
* server-side RBAC
* Argon2 password hashing
* SHA-256 client-token digests
* CSRF protection
* login rate limiting
* parameterized SQL
* validated API input
* controlled package-manager execution
* update-job recovery
* audit logging
* hardened Docker runtime
* HTTPS through Nginx
* loopback-only application-port exposure
* firewall restrictions
* protected production secrets
* pinned production dependencies
* restricted filesystem permissions
* automated security testing

Future changes should preserve these properties unless a deliberate architectural change replaces them with an equivalent or stronger control.

---

# Security Maintenance

Security controls should be revalidated when significant changes are introduced.

Examples include:

* authentication changes
* new user roles
* new API endpoints
* package-management changes
* Agent execution changes
* database migrations
* dependency updates
* Dockerfile changes
* container-runtime changes
* reverse-proxy changes
* firewall changes
* secret-management changes
* release preparation

Security testing should be performed before publishing an official release.

The security documentation should be updated whenever the verified security baseline changes.

---

# Release Readiness

The first official LUMS release will be created only after:

1. implementation work is complete
2. security review is complete
3. documentation review is complete
4. the full automated test suite passes
5. CI passes
6. the final version is defined
7. the Git tag is created
8. the GitHub Release is published

Until then, LUMS remains an actively developed project.

---

# Final Statement

LUMS is designed as a controlled Linux update-management platform with security as a core architectural concern.

The security model does not rely on a single protective mechanism.

Instead, authentication, authorization, validation, controlled execution, persistence, recovery, logging, container isolation, network restrictions, and automated testing work together as layered controls.

The project deliberately favors explicit server-side enforcement over security-by-interface.

The current security baseline is documented according to the verified implementation state rather than historical development behavior.

---

**LUMS — Linux Update Management without the noise.**

`segfault // override`
