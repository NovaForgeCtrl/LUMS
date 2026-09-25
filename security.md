# LUMS Security

> **Linux Update Management Server**
>
> Security principles, architecture, hardening status, security controls, testing, and remaining security work in LUMS.

**Version:** 4.0
**Project:** LUMS
**Slogan:** Linux Update Management without the noise.

---

# 1. Security Philosophy

LUMS follows a simple principle:

> **Centralized management does not mean centralized trust.**

LUMS manages Linux clients, receives inventory information, reports update status, distributes update jobs, and records security-relevant operations.

The actual package-management operation takes place on the managed Linux client.

LUMS therefore separates the:

* **Management Plane**
* **Execution Plane**

```text
                     ┌─────────────────────────────┐
                     │          LUMS Server         │
                     │                             │
                     │ Nginx                       │
                     │ HTTPS                       │
                     │ Gunicorn                    │
                     │ Flask                       │
                     │ Authentication              │
                     │ Authorization               │
                     │ Inventory                   │
                     │ Update Jobs                 │
                     │ Audit Logging               │
                     │ SQLite                      │
                     └──────────────┬──────────────┘
                                    │
                              HTTPS + Token
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
          ┌─────────▼─────────┐           ┌─────────▼─────────┐
          │   Debian Client   │           │    Arch Client    │
          │                   │           │                   │
          │   lums-agent      │           │   lums-agent      │
          │   APT / dpkg      │           │   pacman          │
          │   systemd        │           │   systemd         │
          └───────────────────┘           └───────────────────┘
```

Security is implemented in multiple layers:

```text
Network
   ↓
TLS
   ↓
Nginx
   ↓
Authentication
   ↓
Authorization
   ↓
Application
   ↓
Gunicorn
   ↓
Docker
   ↓
Database
   ↓
Operating System
   ↓
Package Manager
```

A weakness in one layer must never be used as a reason to disable another security layer.

---

# 2. Security Scope

This document covers the security-relevant parts of LUMS, including:

* Docker deployment security
* container privilege reduction
* Linux capability hardening
* read-only container filesystems
* secret management
* secret rotation
* administrator authentication
* login rate limiting
* client authentication
* client token lifecycle
* token rotation
* authorization
* job ownership
* atomic job claiming
* interrupted-job recovery
* update execution security
* update execution timeouts
* process termination
* TLS
* Nginx
* security headers
* SQLite protection
* SQLite concurrency handling
* SQLite foreign-key enforcement
* backup handling
* restore requirements
* systemd agent services
* idle detection
* package-manager abstraction
* APT / dpkg
* pacman
* audit logging
* Git security
* deployment security
* security testing
* remaining hardening work

This document does not replace the official security documentation of:

* Ubuntu
* Debian
* Arch Linux
* Docker
* Python
* Flask
* Gunicorn
* Nginx
* SQLite
* APT
* dpkg
* pacman
* systemd

---

# 3. Current Architecture

The current LUMS server uses:

* Flask
* Gunicorn
* SQLite
* Docker
* Nginx
* HTTPS
* Bearer-token client authentication
* Argon2 administrator password hashing
* systemd-managed Linux agents
* package-manager abstraction
* audit logging
* login rate limiting

The currently tested client package managers are:

```text
APT
pacman
```

The tested client environments include:

```text
Debian 13
Arch Linux
```

The application container is not directly exposed to the network.

Current network flow:

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
   │ Docker port mapping
   ▼
Docker :5000
   │
   ▼
Gunicorn
   │
   └── Flask application
          │
          ├── Authentication
          ├── Authorization
          ├── Inventory
          ├── Update Jobs
          ├── Login Rate Limiting
          └── Audit Logging
                 │
                 ▼
               SQLite
```

The current production application binding is:

```text
127.0.0.1:5050 → container:5000
```

The application is therefore only reachable locally through the Docker port mapping.

External HTTPS access is provided by Nginx.

---

# 4. Management Plane and Execution Plane

LUMS deliberately separates two operational areas.

## 4.1 Management Plane

```text
Nginx
   ↓
Gunicorn
   ↓
Flask
   ↓
Authentication
   ↓
Authorization
   ↓
SQLite
   ↓
Job Management
```

The management plane is responsible for:

* administrator access
* client authentication
* login protection
* inventory
* job creation
* job assignment
* job status
* audit information
* client management
* token lifecycle management

## 4.2 Execution Plane

```text
lums-agent
   ↓
package_manager.py
   ↓
APT / dpkg
      or
pacman
```

The execution plane is responsible for:

* collecting package information
* detecting available updates
* claiming authorized jobs
* executing package operations
* enforcing update execution timeouts
* reporting results

The server does not directly execute package-management commands on clients.

---

# 5. Current Supported Client Platforms

The current package-manager abstraction supports:

```text
APT
pacman
```

The tested environments include:

```text
Debian 13
Arch Linux
```

The agent detects the available package manager.

Current detection logic:

```text
apt available
    ↓
APT package manager

otherwise

pacman available
    ↓
pacman package manager

otherwise

unsupported system
```

The purpose of the abstraction is to keep distribution-specific package-management behavior outside the main agent execution logic.

---

# 6. Current Agent Version

The current LUMS agent version is:

```text
1.7.0
```

The agent version is defined centrally in:

```text
agent/agent.py
```

Version `1.7.0` includes the current update execution timeout handling.

The currently verified client environments are:

```text
Debian 13
Arch Linux
```

Both environments have successfully completed the LUMS reporting and update-management flow with the current agent version.

---

# 7. Security Status

The following security controls have been implemented and verified:

| Security Control                            | Status   |
| ------------------------------------------- | -------- |
| Non-root Docker container                   | Verified |
| Dedicated `lums` container user             | Verified |
| `CAP_DROP=ALL`                              | Verified |
| Privileged container disabled               | Verified |
| Read-only root filesystem                   | Verified |
| `/tmp` isolated through tmpfs               | Verified |
| `/tmp` uses `nosuid`                        | Verified |
| `/tmp` uses `nodev`                         | Verified |
| `/tmp` uses `noexec`                        | Verified |
| Protected secret file                       | Verified |
| Read-only secret mount                      | Verified |
| Production Flask secret rotation            | Verified |
| Gunicorn deployment                         | Verified |
| HTTPS reverse proxy                         | Verified |
| Localhost-only application binding          | Verified |
| Security headers                            | Verified |
| Administrator authentication                | Verified |
| Argon2 password hashing                     | Verified |
| Login rate limiting                         | Verified |
| Login rate-limit concurrency protection     | Verified |
| Login rate-limit audit logging              | Verified |
| Client Bearer authentication                | Verified |
| Client token rotation                       | Verified |
| Token invalidation                          | Verified |
| Token rotation audit logging                | Verified |
| CSRF protection for administrative rotation | Verified |
| SQLite foreign-key enforcement              | Verified |
| SQLite busy timeout                         | Verified |
| SQLite WAL mode                             | Verified |
| Atomic job claiming                         | Verified |
| Job ownership validation                    | Verified |
| Interrupted-job recovery                    | Verified |
| Update execution timeout                    | Verified |
| Process termination fallback                | Verified |
| Debian client reporting                     | Verified |
| Arch client reporting                       | Verified |
| Debian update-job execution                 | Verified |
| Arch update-job execution                   | Verified |
| APT package-manager abstraction             | Verified |
| pacman package-manager abstraction          | Verified |
| systemd-logind idle detection               | Verified |

The security audit is performed incrementally.

Current completed audit areas:

```text
Audit #1 — SQLite Foreign Keys
Audit #2 — SQLite WAL / Busy Timeout
Audit #3 — Update Timeout / Process Termination
Audit #4 — Login Rate Limiting
```

The completed security changes are committed to the Git repository.

---

# 8. Security Audit #1 — SQLite Foreign Keys

LUMS enables SQLite foreign-key enforcement for normal database connections.

The connection configuration includes:

```python
connection.execute("PRAGMA foreign_keys = ON")
```

This ensures that relationships between database tables are enforced by SQLite.

The production database was verified with:

```text
foreign_keys = 1
```

A foreign-key integrity check was also performed.

Expected result:

```text
foreign_key_check = []
```

The database must remain structurally consistent when clients, jobs, update history, and related records are modified.

Client removal is therefore treated separately from normal client disabling.

Active clients are disabled logically while historical job and audit information remains available.

---

# 9. Security Audit #2 — SQLite WAL and Busy Timeout

LUMS uses SQLite WAL mode for improved concurrency behavior.

The database initialization configures:

```text
journal_mode = WAL
busy_timeout = 5000
foreign_keys = ON
```

The runtime database configuration was verified as:

```text
journal_mode: wal
busy_timeout: 5000
synchronous: 2
foreign_keys: 1
```

The busy timeout gives SQLite additional time to wait for a locked database instead of immediately failing.

WAL mode improves concurrent read/write behavior for the LUMS workload.

The database remained intact after enabling the configuration.

Verified production data included:

```text
clients: 2
update_jobs: 7
update_job_packages: 3
update_history: 7
```

---

# 10. Security Audit #3 — Update Execution Timeout

Package-management processes must not be allowed to run indefinitely.

The update execution path therefore implements an explicit timeout.

The timeout handling is designed to avoid blocking indefinitely while waiting for process output.

The execution flow is:

```text
Start package process
        ↓
Read process output
        ↓
Monitor execution time
        ↓
Timeout reached?
     /       \
   No         Yes
   │           │
continue    terminate()
               ↓
          grace period
               ↓
        still running?
          /       \
        No         Yes
        │           │
      cleanup     kill()
                    ↓
                 cleanup
```

The implementation uses selector-based process output handling instead of relying on a blocking `readline()` operation that could prevent the timeout from being enforced.

The timeout handling was tested with:

* a silent child process
* a child process ignoring `SIGTERM`
* an integration test using a simulated hanging process

The expected timeout result was verified as:

```text
status = timeout
```

A termination grace period is used before the final `kill()` fallback.

This ensures that a normally terminating process gets an opportunity to exit cleanly while still preventing indefinite execution.

---

# 11. Security Audit #4 — Login Rate Limiting

Administrator login attempts are protected by progressive rate limiting.

The purpose is to reduce repeated authentication attempts against the web login endpoint.

Rate limiting is tracked using a normalized key derived from:

```text
username
+
request source
```

Conceptually:

```text
normalized_username|normalized_source
```

The rate-limit state is stored in the SQLite database.

The migration introducing this functionality is:

```text
003-login-rate-limiting
```

The corresponding table is:

```sql
login_rate_limits
```

The table tracks:

```text
rate_limit_key
username
failed_attempts
first_failed_at
last_failed_at
locked_until
```

A unique index protects the rate-limit key.

An additional index supports lookup of active lock information.

---

# 12. Progressive Login Locking

The current lock escalation is:

| Failed Attempts | Lock Duration |
| --------------- | ------------- |
| 1–4             | No lock       |
| 5               | 30 seconds    |
| 6               | 60 seconds    |
| 7               | 120 seconds   |
| 8+              | 300 seconds   |

The lock is evaluated before another authentication attempt is processed.

A blocked login attempt returns the same generic authentication error used for invalid credentials.

The application therefore does not reveal whether:

* the username exists,
* the password was incorrect,
* or the request was temporarily rate limited.

This avoids exposing additional account-state information through the login response.

---

# 13. Login Rate-Limit Concurrency

Rate-limit updates are protected against concurrent login attempts.

The update operation uses:

```text
BEGIN IMMEDIATE
```

This ensures that competing attempts cannot independently create the same rate-limit record and overwrite each other's counters.

A dedicated concurrency test used:

```text
10 concurrent login attempts
```

The verified result was:

```text
THREADS: 10
ERRORS: []
FINAL_FAILED_ATTEMPTS: 10
```

This confirmed that concurrent failures are serialized correctly for the same rate-limit key.

---

# 14. Login Rate-Limit Rollback

The rate-limit implementation was also tested for transaction rollback.

The verified flow was:

```text
First failure
    ↓
failed_attempts = 1
    ↓
transaction rollback
    ↓
rate-limit record absent
    ↓
retry
    ↓
failed_attempts = 1
```

The rollback test completed successfully.

This ensures that a failed database transaction does not leave partially committed rate-limit state behind.

---

# 15. Login Rate-Limit Audit Logging

Security-relevant login rate-limit events are recorded in the audit log.

Examples include:

```text
login.rate_limit
```

with results such as:

```text
locked
blocked
```

A lock event records the failed-attempt count.

A blocked request records that the login was temporarily rate limited.

The audit record does not contain:

* passwords
* client tokens
* Flask secrets
* authentication credentials

Production end-to-end testing verified the following sequence:

```text
Failed login attempts
        ↓
failed_attempts increases
        ↓
5th failure
        ↓
temporary lock
        ↓
additional attempt
        ↓
blocked
        ↓
audit events recorded
```

Temporary test records were removed after verification.

The production database was subsequently checked for:

```text
login_rate_limits: 0
integrity_check: ok
foreign_key_check: []
```

---

# 16. Login Rate-Limit Database Migration

The login rate-limit schema is introduced through an explicit migration:

```text
003-login-rate-limiting
```

The migration is designed to be idempotent and uses the same database safety principles as the main application:

```text
foreign_keys = ON
busy_timeout = 5000
```

The migration was applied successfully to the production database.

The resulting migration history contains:

```text
001-security-foundation
002-package-management
003-login-rate-limiting
```

The production database remained valid after the migration.

---

# 17. Client Authentication

Linux clients authenticate against the LUMS API using Bearer tokens.

Example:

```text
Authorization: Bearer <CLIENT_TOKEN>
```

The server does not store the plaintext client token as normal database state.

Instead, the supplied token is hashed and compared against the stored digest.

Conceptually:

```text
Generate random token
        ↓
Hash token
        ↓
Store digest
        ↓
Return plaintext token once
        ↓
Agent uses token
        ↓
Server hashes supplied token
        ↓
Compare digest
```

The token lifecycle is therefore separated from the stored credential representation.

---

# 18. Client Token Lifecycle

The client-token lifecycle is:

```text
Generate
   ↓
Hash
   ↓
Store hash
   ↓
Authenticate
   ↓
Rotate
   ↓
Invalidate previous token
   ↓
Issue replacement
   ↓
Update agent
   ↓
Verify communication
```

The plaintext token must not be written to:

* audit logs
* application logs
* Git
* documentation
* screenshots
* public bug reports

Token rotation creates a new credential and invalidates the previous credential.

---

# 19. Token Rotation

Administrative token rotation:

1. identifies the client,
2. generates a new cryptographically secure token,
3. hashes the token,
4. replaces the stored token hash,
5. updates token metadata,
6. invalidates the previous credential,
7. creates an audit event,
8. returns the new token once.

The previous token becomes invalid immediately.

The replacement token must then be installed on the corresponding agent.

---

# 20. Authorization and Job Ownership

Authentication establishes the identity of the caller.

Authorization determines what that identity is allowed to access.

For client-specific operations, LUMS validates the relationship between:

```text
Authenticated Client
        +
Requested Object
        +
Object Owner
```

For update jobs:

```text
authenticated_client.id
        ==
job.client_id
```

A client must not be able to access another client's jobs by changing a client ID in a request.

The same ownership validation applies to job-result reporting and recovery operations.

---

# 21. Atomic Job Claiming

Update jobs transition through controlled states.

A normal execution begins with:

```text
pending
   ↓
running
```

The claim operation is atomic.

Conceptually:

```text
Client A ──┐
           ├── claim
Client B ──┘
           ↓
       one winner
```

Two clients must not be able to successfully claim the same pending job through normal concurrent execution.

The winning client becomes responsible for executing and reporting the job.

---

# 22. Interrupted Job Recovery

An update job can be interrupted by:

* agent termination
* system shutdown
* network interruption
* process failure
* unexpected client failure

A job may therefore remain in:

```text
running
```

without receiving its expected final result.

LUMS provides controlled recovery for this condition.

The recovery transition is:

```text
running
   ↓
abandoned
```

Recovery validates:

* job existence
* client ownership
* current job state
* valid recovery transition

The operation records:

```text
finished_at
recovery reason
update history
```

The job is not falsely reported as successful.

---

# 23. Agent Security

The LUMS agent communicates with the server using HTTPS.

The agent configuration contains the required server endpoint, client credential, and CA configuration.

Typical configuration values are:

```text
LUMS_BASE
LUMS_TOKEN
LUMS_CA_FILE
```

The actual credential is never documented.

TLS verification must remain enabled.

Certificate problems must be fixed rather than bypassed by disabling certificate verification.

---

# 24. Idle Detection

The current agent uses systemd-logind for idle detection.

The detection mechanism is:

```text
loginctl
```

The agent evaluates relevant interactive sessions and uses logind information such as:

```text
Class
Type
TTY
State
IdleHint
IdleSinceHintMonotonic
```

The resulting state includes:

```text
idle
idle_seconds
threshold_seconds
idle_source
idle_supported
```

The current idle source is:

```text
loginctl
```

The purpose is to avoid unnecessarily disruptive update operations while an interactive user is actively working.

If idle information cannot be retrieved reliably, the agent does not treat the system as confirmed idle.

---

# 25. Package Manager Abstraction

Package management is implemented through a dedicated abstraction.

The current implementations are:

```text
AptPackageManager
PacmanPackageManager
```

Conceptually:

```text
                 package_manager.py
                         │
              ┌──────────┴──────────┐
              │                     │
       AptPackageManager     PacmanPackageManager
              │                     │
         apt / dpkg               pacman
```

This keeps distribution-specific behavior outside the main agent execution logic.

Supported operations include:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

The actual package-management operation is executed locally on the client.

---

# 26. Package Manager Coordination

Package-manager operations are security-sensitive because package managers generally require elevated privileges.

LUMS therefore controls execution of its own package-management operations.

However, LUMS cannot automatically prevent every manually started package-manager process on the operating system from running concurrently.

For example:

```text
LUMS
  ↓
apt

User
  ↓
apt
```

may still represent an external coordination problem.

The current LUMS execution locking reduces collisions within LUMS-controlled operations.

Complete coordination with arbitrary external package-manager processes remains a hardening task.

---

# 27. Update Execution Timeout Security

Update execution is treated as a controlled process boundary.

A package process that exceeds its configured execution timeout is terminated.

The termination sequence is:

```text
Timeout
   ↓
SIGTERM
   ↓
Grace period
   ↓
Process exited?
   ├── Yes → cleanup
   └── No
        ↓
      SIGKILL
        ↓
      cleanup
```

This prevents a hung package-management process from permanently blocking an update job.

The timeout implementation was specifically tested against processes that:

* produce no output
* remain alive beyond the timeout
* ignore the initial termination request

The final fallback uses process killing when graceful termination is insufficient.

---

# 28. Nginx Security

Nginx is the external HTTPS entry point.

The Flask/Gunicorn application is not directly exposed.

Current architecture:

```text
Network
   │
   ▼
Nginx :443
   │
   ▼
127.0.0.1:5050
   │
   ▼
Docker :5000
   │
   ▼
Gunicorn
```

The application port must remain internal.

HTTP is redirected to HTTPS.

The external application interface is therefore:

```text
HTTPS :443
```

while the internal application binding remains:

```text
127.0.0.1:5050
```

---

# 29. TLS

LUMS uses HTTPS for browser and client communication.

TLS verification must remain enabled for agents.

Modern TLS versions should be used.

Certificates must contain the appropriate Subject Alternative Name.

Private-key permissions must be restricted.

The Nginx configuration can be validated using:

```bash
sudo nginx -t
```

Self-signed certificates may be used in controlled laboratory environments when the appropriate CA or certificate is explicitly trusted by the client.

Certificate warnings must not be solved by disabling TLS verification.

---

# 30. Security Headers

The application provides security headers intended to reduce common browser-side attack surfaces.

The security policy includes controls such as:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
```

The permissions policy restricts unnecessary browser capabilities.

The Content Security Policy restricts application resources to expected origins.

Security headers must be rechecked after changes to:

* Nginx
* Flask response handling
* templates
* frontend assets
* authentication pages

---

# 31. Docker Security

The production LUMS container runs as a dedicated non-root user.

The hardened runtime uses:

```text
--read-only
--cap-drop=ALL
--tmpfs /tmp:rw,nosuid,nodev,noexec
```

The application secret is supplied through a protected file:

```text
/etc/lums/secrets/lums_secret
```

and mounted read-only into the container:

```text
/run/secrets/lums_secret
```

The production database is stored separately:

```text
lums-data
    ↓
/var/lib/lums
```

The application port is bound locally:

```text
127.0.0.1:5050:5000
```

The container therefore separates:

```text
Application image
    ≠
Persistent database
    ≠
Temporary files
    ≠
Security secrets
```

---

# 32. Production Container Hardening

The production container uses the following configuration:

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

The expected runtime properties are:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
```

The application must continue functioning without additional Linux capabilities.

---

# 33. Secret Management

Production secrets must never be:

* committed to Git
* written into documentation
* printed to logs
* included in screenshots
* included in public bug reports
* copied into source files

The production Flask secret is stored outside the repository:

```text
/etc/lums/secrets/lums_secret
```

It is mounted read-only:

```text
Host
    │
    │ read-only bind mount
    ▼
Container
/run/secrets/lums_secret
```

The application is configured using:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

The actual secret value is intentionally never documented.

---

# 34. Secret Environment Isolation

The production Flask secret must not be supplied through:

```text
LUMS_SECRET_KEY
```

The application instead reads the protected secret file:

```text
/run/secrets/lums_secret
```

The secret file must remain readable by the application while remaining protected from unauthorized access.

The secret mount is read-only.

---

# 35. Session Invalidation

Changing the Flask secret affects existing application sessions.

The expected behavior is:

```text
Old secret
    ↓
Existing session
    ↓
Secret rotation
    ↓
Existing session invalidated
```

A new login establishes a valid session using the replacement secret.

Secret rotation is therefore an operational security event that must be planned and verified.

---

# 36. SQLite Security

LUMS uses SQLite for persistent application state.

The production database is stored at:

```text
/var/lib/lums/lums.db
```

and is backed by:

```text
lums-data
```

The database must not be stored inside:

```text
/opt/lums-public
```

and must never be committed to Git.

The production volume must not be removed during ordinary troubleshooting.

Database connections enable:

```text
foreign_keys = ON
busy_timeout = 5000
```

The database is initialized using:

```text
journal_mode = WAL
```

These settings are part of the current database hardening.

---

# 37. SQLite Integrity Verification

SQLite integrity can be checked using:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
'
```

Expected:

```text
ok
```

Foreign-key consistency can additionally be checked using:

```sql
PRAGMA foreign_key_check;
```

Expected result:

```text
[]
```

An integrity check should be performed after major database-related deployment changes.

---

# 38. SQLite Backup

SQLite backups should use a SQLite-aware mechanism.

A backup must not simply be treated as a normal file copy while the database is actively changing.

A SQLite backup operation can use the SQLite backup API.

The resulting backup should be moved to a protected backup location.

Backups must not be committed to Git.

---

# 39. Backup Protection

LUMS database backups may contain sensitive application information, including:

* users
* clients
* audit records
* job information
* operational metadata

Backup files therefore require appropriate access control.

Example:

```bash
sudo chown root:root /var/backups/lums/lums.db.backup
sudo chmod 600 /var/backups/lums/lums.db.backup
```

Backup integrity must be verified before relying on the backup for recovery.

---

# 40. Restore Requirements

SQLite backup creation and integrity verification are implemented.

A complete isolated restore test remains a separate hardening task.

The intended restore workflow is:

```text
Verified backup
      ↓
Isolated LUMS environment
      ↓
Restore database
      ↓
SQLite integrity check
      ↓
Application startup
      ↓
Authentication test
      ↓
Client data verification
      ↓
Job/history verification
```

A backup should not be considered fully validated until an actual restore has been tested.

---

# 41. Git Security

The Git repository must never contain:

```text
Passwords
Client tokens
Flask secrets
TLS private keys
Production environment files
Database files
SQLite backups
Session secrets
Unredacted production data
```

Before committing changes:

```bash
cd /opt/lums-public

git status
git diff
git diff --check
```

All changed files must be reviewed before committing.

Production credentials must remain outside the repository.

---

# 42. Security Testing Principle

Security changes are validated incrementally.

The general workflow is:

```text
Change
  ↓
Syntax Check
  ↓
Unit / Isolated Test
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

Security-sensitive production changes additionally require deployment verification.

The goal is to verify both:

```text
Security property
```

and:

```text
Existing functionality
```

A security change must not silently break normal LUMS operation.

---

# 43. Security Audit History

Completed audits:

```text
Audit #1 — SQLite Foreign Keys
Audit #2 — SQLite WAL / Busy Timeout
Audit #3 — Update Timeout / Process Termination
Audit #4 — Login Rate Limiting
```

Corresponding commits:

```text
SQLite connection hardening
Update execution timeout hardening
Login rate-limiting implementation
```

The audit work is maintained as part of the normal LUMS development history.

---

# 44. Current Security Limitations

LUMS is an active development project.

The following areas remain intentionally open:

* complete restore testing
* automated security regression coverage
* complete external package-manager collision prevention
* full role-based administrative authorization
* final external network review
* additional API input validation
* session revocation improvements
* trusted client-source/IP handling for proxied deployments
* further job checkpointing and recovery hardening

These limitations are documented rather than treated as solved controls.

---

# 45. Security Roadmap

The security roadmap continues incrementally.

Current audit sequence:

```text
01 SQLite Foreign Keys                    COMPLETE
02 SQLite WAL / Busy Timeout             COMPLETE
03 Update Timeout / process.kill()       COMPLETE
04 Login Rate-Limiting                   COMPLETE
05 API Input Validation                  NEXT
06 Session Revocation
07 Token Rotation
08 get_ip() / Offline-Netze
09 Job Recovery / Checkpointing
10 APT Robustness
11 Arch Reboot Detection
12 Unit Tests
13 Simulation Tests
14 CI
15 Logging
16 Versionierung / Releases
17 RBAC
18 Complete Documentation Update
```

The roadmap is subject to change as implementation and testing reveal additional requirements.

---

# 46. Security Philosophy in Practice

LUMS follows a defense-in-depth approach.

The project does not assume that one mechanism is sufficient.

Instead:

```text
Authentication
      +
Authorization
      +
Token Security
      +
Rate Limiting
      +
Audit Logging
      +
Container Hardening
      +
Database Integrity
      +
Process Control
      +
TLS
      +
Operational Testing
```

form the overall security model.

The objective is not to claim that LUMS is universally secure.

The objective is to make security controls explicit, testable, auditable, and continuously improvable.

---

# 47. Responsible Disclosure

Security issues should be reported responsibly.

Do not publicly disclose:

* active credentials
* client tokens
* production secrets
* private keys
* unredacted databases
* sensitive infrastructure information

When sharing logs or screenshots:

```text
Collect
   ↓
Review
   ↓
Redact
   ↓
Review again
   ↓
Share
```

Credentials must be rotated immediately if accidental exposure occurs.

---

# 48. Final Security Principle

LUMS is designed around a simple operational principle:

> **If a security control cannot be verified, it should not be treated as complete.**

Security status is therefore based on implementation and testing rather than assumptions.

The security documentation is updated as the implementation evolves.

```text
Implement
   ↓
Test
   ↓
Verify
   ↓
Document
   ↓
Repeat
```

**LUMS — Linux Update Management without the noise.**



# 48. Incident Handling

Security-relevante Ereignisse müssen nachvollziehbar behandelt werden.

Ein Incident kann beispielsweise entstehen durch:

* kompromittierte Client-Credentials
* kompromittierte Administrator-Credentials
* versehentlich veröffentlichte Secrets
* kompromittierte TLS-Schlüssel
* unbefugten Zugriff auf die Datenbank
* unbefugten Zugriff auf Backups
* manipulierte Container-Images
* unerwartete Update-Ausführung
* fehlerhafte Job-Zustände
* ungewöhnliche Authentifizierungsaktivität

Der grundsätzliche Ablauf lautet:

```text
Incident erkannt
      ↓
Zugriff begrenzen
      ↓
Betroffene Credentials identifizieren
      ↓
Credentials rotieren / deaktivieren
      ↓
Logs und Audit-Daten sichern
      ↓
Ursache untersuchen
      ↓
Systemzustand verifizieren
      ↓
Maßnahmen dokumentieren
```

Ein Incident darf nicht ausschließlich anhand der aktuellen Systemfunktion beurteilt werden.

Auch wenn LUMS nach einem Vorfall weiterhin funktioniert, müssen mögliche kompromittierte Credentials und Daten überprüft werden.

---

# 49. Compromised Client Token

Wird ein Client-Token kompromittiert, muss der betreffende Client zunächst identifiziert werden.

Das alte Token darf nicht weiterverwendet werden.

Der vorgesehene Ablauf ist:

```text
Kompromittiertes Token
        ↓
Client identifizieren
        ↓
Token rotieren
        ↓
Altes Token ungültig
        ↓
Neues Token sicher bereitstellen
        ↓
Agent aktualisieren
        ↓
Agent-Verbindung testen
        ↓
Audit-Eintrag prüfen
```

Die Token-Rotation erzeugt ein neues Token.

Das vorherige Token wird durch die Rotation ungültig.

Das alte Token darf nicht erneut in Dokumentation, Logs oder Konfigurationsbeispielen auftauchen.

---

# 50. Compromised Administrator Credentials

Bei einem kompromittierten Administrator-Konto muss der Zugriff zunächst eingeschränkt werden.

Zu prüfen sind insbesondere:

* erfolgreiche und fehlgeschlagene Logins
* Audit-Einträge
* Änderungen an Clients
* Token-Rotationen
* erstellte Update-Jobs
* Job-Ergebnisse
* Änderungen an sicherheitsrelevanten Konfigurationen

Das Administrator-Passwort muss geändert werden.

Falls der Flask-Secret-Key kompromittiert wurde, muss zusätzlich der Secret-Key rotiert werden.

Die Maßnahmen müssen getrennt betrachtet werden:

```text
Administrator-Passwort
        ≠
Flask Secret
        ≠
Client Token
        ≠
TLS Private Key
```

Die Kompromittierung eines Credentials bedeutet daher nicht automatisch, dass alle anderen Credentials ersetzt werden müssen.

Die betroffenen Credentials müssen jedoch entsprechend ihrer tatsächlichen Gefährdung bewertet und gegebenenfalls rotiert werden.

---

# 51. Compromised Flask Secret

Der Flask Secret-Key ist ein sicherheitsrelevanter Bestandteil der Webanwendung.

Bei einer Kompromittierung gilt:

```text
Alter Secret-Key
       ↓
als kompromittiert betrachten
       ↓
neuen Secret-Key erzeugen
       ↓
Secret-Datei ersetzen
       ↓
Container neu starten
       ↓
bestehende Sessions ungültig
       ↓
neue Anmeldung erforderlich
```

Der neue Secret-Key darf niemals in:

* Git
* Dokumentation
* Logs
* Screenshots
* Tickets
* öffentlichen Issues

gespeichert werden.

---

# 52. Compromised TLS Private Key

Bei einer Kompromittierung des TLS Private Keys muss das betroffene Zertifikat als nicht mehr vertrauenswürdig betrachtet werden.

Der Ablauf lautet:

```text
Private Key kompromittiert
        ↓
neues Schlüsselpaar erzeugen
        ↓
neues Zertifikat erzeugen
        ↓
Nginx-Konfiguration aktualisieren
        ↓
nginx -t
        ↓
Nginx reload / restart
        ↓
TLS-Verbindung testen
        ↓
altes Zertifikat nicht weiterverwenden
```

Bei einer internen Laborumgebung kann eine eigene CA verwendet werden.

Das Prinzip bleibt jedoch identisch:

> Ein kompromittierter privater Schlüssel wird nicht weiterverwendet.

---

# 53. Exposed Database or Backup

Eine kompromittierte Datenbank oder ein kompromittiertes Backup muss als sensibles Sicherheitsereignis behandelt werden.

Möglicherweise enthalten sind:

* Benutzerinformationen
* Clientinformationen
* Audit-Daten
* Job-Historie
* Update-Metadaten
* Betriebsinformationen

Ein Datenbank-Backup darf deshalb nicht wie eine gewöhnliche temporäre Datei behandelt werden.

Bei einer Exposition muss geprüft werden:

```text
Welche Datei?
       ↓
Welche Version?
       ↓
Welche Daten enthalten?
       ↓
Wie lange exponiert?
       ↓
Wer konnte zugreifen?
       ↓
Welche Credentials müssen rotiert werden?
```

---

# 54. Audit Logging

LUMS verwendet Audit Logging für sicherheitsrelevante Verwaltungsaktionen.

Audit-Daten sollen nachvollziehbar machen:

* welcher Vorgang ausgeführt wurde
* welcher Client betroffen war
* welcher Job betroffen war
* welches Ergebnis vorlag
* wann der Vorgang stattfand
* ob ein Vorgang erfolgreich oder abgelehnt wurde

Beispiele für sicherheitsrelevante Ereignisse sind:

```text
login
login failure
login.rate_limit
client changes
token rotation
job creation
job recovery
job result
```

Audit Logging ersetzt keine Zugriffskontrolle.

Es dient der Nachvollziehbarkeit.

---

# 55. Audit Log Security

Audit-Einträge dürfen keine geheimen Credentials enthalten.

Insbesondere dürfen nicht gespeichert werden:

```text
Passwords
Client Tokens
Flask Secrets
TLS Private Keys
```

Bei Token-Rotationen darf das neu erzeugte Token nicht im Audit Log erscheinen.

Das Audit Log muss den Vorgang dokumentieren, nicht das geheime Credential selbst.

Beispiel:

```text
Token rotation
    ↓
Audit event
    ↓
Client ID
Action
Timestamp
Result
```

aber nicht:

```text
Token = <PLAINTEXT TOKEN>
```

---

# 56. Authentication Security

Die Administrator-Authentifizierung basiert auf einem gehashten Passwort.

LUMS verwendet Argon2 für die Passwortspeicherung.

Das eigentliche Passwort wird nicht als Klartext gespeichert.

Der Login-Prozess umfasst:

```text
Username
   ↓
Rate-Limit-Prüfung
   ↓
User Lookup
   ↓
Password Verification
   ↓
Session Creation
   ↓
Audit Event
```

Fehlgeschlagene Anmeldungen werden nicht mit unterschiedlichen Fehlermeldungen für:

```text
unknown user
```

und:

```text
wrong password
```

unterschieden.

Die Anwendung verwendet eine generische Authentifizierungsfehlermeldung.

---

# 57. Login Rate Limiting — Security Model

Die Login-Rate-Limitierung schützt die Administrator-Anmeldung vor wiederholten fehlgeschlagenen Anmeldeversuchen.

Das Modell ist bewusst progressiv:

```text
5 failures
    ↓
30 seconds

6 failures
    ↓
60 seconds

7 failures
    ↓
120 seconds

8+ failures
    ↓
300 seconds
```

Ein erfolgreicher Login setzt den Rate-Limit-Zustand zurück.

Damit bleibt eine normale erfolgreiche Anmeldung möglich, während wiederholte Fehlversuche schrittweise stärker eingeschränkt werden.

---

# 58. Client State Security

Clients besitzen einen administrativ steuerbaren Zustand.

Ein Client kann deaktiviert werden.

Dabei wird nicht einfach die gesamte historische Beziehung aus der Datenbank entfernt.

Stattdessen wird der Client logisch deaktiviert:

```text
enabled = 0
```

und das Token wird widerrufen.

Damit gilt:

```text
Client deaktiviert
       ↓
neue Authentifizierung abgelehnt
       ↓
historische Jobs bleiben erhalten
       ↓
Audit-Daten bleiben erhalten
```

Dies verhindert, dass eine Deaktivierung gleichzeitig historische Informationen zerstört.

---

# 59. Client Token Revocation

Bei einer Deaktivierung wird der Token-Zustand entsprechend aktualisiert.

Der Client kann danach keine neuen API-Anfragen mehr erfolgreich authentifizieren.

Eine spätere Reaktivierung darf nicht automatisch als Wiederherstellung eines zuvor kompromittierten Tokens verstanden werden.

Bei sicherheitsrelevanten Fällen sollte stattdessen ein neues Token ausgestellt werden.

---

# 60. API Input Validation

API-Eingaben müssen serverseitig validiert werden.

Clientseitige Validierung darf niemals als alleinige Sicherheitskontrolle betrachtet werden.

Zu validieren sind insbesondere:

* IDs
* Statuswerte
* Paketnamen
* Jobdaten
* Clientdaten
* Update-Ergebnisse
* administrative Parameter

Ein Request darf nicht automatisch als vertrauenswürdig behandelt werden, nur weil er von einem bereits authentifizierten Client stammt.

Die vollständige API-Input-Validation bleibt Teil des laufenden Security Audits.

---

# 61. API Error Handling

API-Fehler dürfen keine unnötigen internen Informationen offenlegen.

Insbesondere sollten Fehlerantworten keine Informationen enthalten wie:

* interne Dateipfade
* Secrets
* Datenbankpasswörter
* interne Stacktraces
* private Schlüssel
* interne Infrastrukturdetails

Interne Details gehören in geeignete Server-Logs.

Die externe API sollte eine kontrollierte Fehlermeldung zurückgeben.

---

# 62. Job State Validation

Update Jobs besitzen einen kontrollierten Lebenszyklus.

Der aktuelle Zustand bestimmt, welche nächste Aktion zulässig ist.

Beispiel:

```text
pending
   ↓
waiting_for_idle
   ↓
running
   ↓
success
```

Alternative Endzustände:

```text
partial
failed
abandoned
```

Ungültige Zustandsübergänge müssen abgelehnt werden.

Ein bereits abgeschlossener Job darf nicht erneut als laufender Job übernommen werden.

---

# 63. Waiting for Idle

Ein Job kann zunächst auf einen geeigneten Ausführungszeitpunkt warten.

Beispiel:

```text
pending
   ↓
waiting_for_idle
   ↓
idle detected
   ↓
running
```

Dies verhindert, dass ein Update automatisch während einer aktiven interaktiven Sitzung ausgeführt wird.

Die Entscheidung wird auf dem Client getroffen, da dort die tatsächliche Benutzeraktivität bekannt ist.

---

# 64. Update Result Reporting

Nach Abschluss eines Update-Vorgangs meldet der Agent das Ergebnis an LUMS.

Das Ergebnis kann beispielsweise enthalten:

```text
success
partial
failed
timeout
```

Zusätzliche Informationen können Paketstatistiken und den Zustand des Clients enthalten.

Ein Update darf nicht allein deshalb als erfolgreich betrachtet werden, weil der Prozess gestartet wurde.

Entscheidend ist das tatsächliche Ergebnis des Paketmanagers.

---

# 65. Timeout Result Handling

Ein Timeout ist kein normaler Erfolg.

Wenn ein Paketmanager den definierten Timeout überschreitet:

```text
running
   ↓
timeout
   ↓
process termination
   ↓
result reporting
```

Das System muss den Vorgang entsprechend als fehlgeschlagenen bzw. zeitlich überschrittenen Vorgang behandeln.

Ein Timeout darf nicht als:

```text
success
```

gemeldet werden.

---

# 66. Package Statistics

Update-Jobs speichern Informationen über die betroffenen Pakete.

Diese Daten dienen unter anderem zur späteren Nachvollziehbarkeit.

Beispiele:

```text
packages requested
packages updated
packages failed
```

Die Paketstatistik wird auch bei Recovery-Vorgängen berücksichtigt.

Dadurch geht die historische Information über einen Job nicht automatisch verloren, wenn die ursprüngliche Ausführung unterbrochen wurde.

---

# 67. Reboot Handling

Ein Paket-Update kann einen Neustart erforderlich machen.

LUMS führt nicht automatisch jeden erforderlichen Neustart durch.

Der Neustartzustand muss entsprechend erkannt und dokumentiert werden.

Das Ziel ist:

```text
Update Management
        ≠
uncontrolled reboot management
```

Ein administrativ gewünschter Neustart muss daher als eigener Betriebsentscheid behandelt werden.

Die weitergehende Reboot-Erkennung für Arch Linux bleibt Teil des Security-/Robustness-Audits.

---

# 68. Debian Security Verification

Der Debian-Client wurde mit dem aktuellen Agenten getestet.

Aktueller Agent:

```text
1.7.0
```

Der erfolgreiche Ablauf umfasst:

```text
Agent startet
    ↓
Systeminformationen sammeln
    ↓
Paketinformationen sammeln
    ↓
HTTPS Report
    ↓
Server akzeptiert Report
    ↓
Client authentifiziert
    ↓
Pending Job prüfen
    ↓
Update ausführen
    ↓
Ergebnis melden
```

Die Kommunikation wurde erfolgreich verifiziert.

---

# 69. Arch Linux Security Verification

Der Arch-Client wurde ebenfalls mit Agent `1.7.0` getestet.

Die Paketverwaltung erfolgt über:

```text
pacman
```

Der Agent erkennt:

```text
Arch Linux
```

und verwendet die entsprechende `PacmanPackageManager`-Implementierung.

Der erfolgreiche Ablauf umfasst:

```text
Agent startet
    ↓
Systeminformationen sammeln
    ↓
pacman package inventory
    ↓
Update inventory
    ↓
HTTPS Report
    ↓
Job handling
    ↓
pacman execution
    ↓
Result reporting
```

Die Kommunikation mit dem aktuellen LUMS-Server wurde erfolgreich verifiziert.

---

# 70. Cross-Distribution Security Model

LUMS behandelt Distributionen nicht als identisch.

Die gemeinsame Schnittstelle befindet sich auf Ebene der Package-Manager-Abstraktion.

```text
                    LUMS Agent
                        │
                Package Manager
                   Interface
                 /           \
                /             \
              APT           pacman
               │               │
             dpkg            libalpm
```

Dadurch kann die gemeinsame Joblogik unabhängig vom konkreten Paketmanager arbeiten.

Distribution-spezifische Besonderheiten bleiben in den jeweiligen Implementierungen.

---

# 71. Docker Image Security

Das Docker-Image wird aus dem LUMS-Projekt gebaut.

Der Produktionscontainer verwendet ein dediziertes Image:

```text
lums:latest
```

Audit-spezifische Images können während der Entwicklung zusätzlich getaggt werden.

Nach einer erfolgreichen Prüfung wird das geprüfte Image als Produktionsimage verwendet.

Der Produktionscontainer darf nicht blind aus einem unbekannten oder ungetesteten Image gestartet werden.

---

# 72. Production Container Verification

Nach einem Container-Rebuild müssen mindestens folgende Eigenschaften geprüft werden:

```text
Container running
        ↓
User correct
        ↓
Root filesystem read-only
        ↓
Capabilities dropped
        ↓
Privileged disabled
        ↓
Secret mounted read-only
        ↓
Persistent volume present
        ↓
Port localhost-only
        ↓
Gunicorn running
        ↓
API reachable
```

Zusätzlich müssen vorhandene Daten erhalten bleiben.

Ein Container-Rebuild darf nicht mit dem Löschen des persistenten Datenvolumes verwechselt werden.

---

# 73. Container Replacement

Bei einem kontrollierten Produktionswechsel wird der bestehende Container nicht einfach durch Löschen des persistenten Volumes ersetzt.

Die grundlegende Struktur lautet:

```text
Stop old container
        ↓
Verify volume
        ↓
Verify secret
        ↓
Create new container
        ↓
Start
        ↓
Check logs
        ↓
Check runtime configuration
        ↓
Check API
        ↓
Check database
```

Das Datenvolume:

```text
lums-data
```

bleibt dabei erhalten.

Das Secret bleibt ebenfalls außerhalb des Containers erhalten.

---

# 74. Deployment Verification

Nach jedem sicherheitsrelevanten Deployment werden mindestens folgende Punkte geprüft:

```text
docker ps
docker inspect
docker logs
Nginx configuration
HTTPS endpoint
API endpoint
Database integrity
Client authentication
Client reporting
Job state
```

Ein erfolgreicher Containerstart alleine gilt nicht als ausreichende Deployment-Verifikation.

---

# 75. Database Migration Security

Datenbankmigrationen werden explizit versioniert.

Beispiel:

```text
001-security-foundation
002-package-management
003-login-rate-limiting
```

Migrationen müssen:

* reproduzierbar
* nachvollziehbar
* möglichst idempotent
* fehlerbehandelnd

implementiert werden.

Vor produktiven Schemaänderungen sollte ein Datenbankbackup erstellt werden.

---

# 76. Migration Rollback

Eine Migration darf bei einem Fehler keine teilweise angewendete Änderung hinterlassen.

Die Login-Rate-Limit-Migration wurde beispielsweise mit Transaktionsschutz implementiert.

Das Verhalten wurde explizit getestet.

Das Ziel:

```text
Migration startet
       ↓
Fehler
       ↓
Rollback
       ↓
alter Zustand bleibt erhalten
```

Eine erfolgreiche Migration muss anschließend durch Integritätsprüfungen verifiziert werden.

---

# 77. Database Concurrency

SQLite wird innerhalb LUMS von mehreren Komponenten genutzt.

Dazu gehören unter anderem:

* Web Requests
* Agent Reports
* Job Operations
* Audit Logging
* Rate Limiting

Die Datenbankverbindung verwendet deshalb:

```text
foreign_keys = ON
busy_timeout = 5000
```

und die Datenbank arbeitet mit:

```text
WAL
```

Concurrency-sensitive Operationen können zusätzlich explizite Transaktionen verwenden.

Beispielsweise verwendet das Login-Rate-Limiting bei konkurrierenden Updates:

```text
BEGIN IMMEDIATE
```

---

# 78. Logging Security

Logs müssen so behandelt werden, dass keine Secrets offengelegt werden.

Nicht in Logs gehören:

```text
Passwords
Bearer Tokens
Flask Secret
TLS Private Key
```

Bei Debugging-Ausgaben muss besonders darauf geachtet werden, dass HTTP-Headers nicht versehentlich vollständig ausgegeben werden.

Insbesondere:

```text
Authorization: Bearer ...
```

darf nicht unredigiert in einem Log landen.

---

# 79. Operational Log Review

Bei einem Fehler sollten Logs von mehreren Ebenen betrachtet werden:

```text
systemd
   ↓
Docker
   ↓
Gunicorn
   ↓
Flask
   ↓
Nginx
   ↓
Agent
   ↓
Package Manager
```

Dadurch kann unterschieden werden zwischen:

* Netzwerkfehler
* Authentifizierungsfehler
* API-Fehler
* Datenbankfehler
* Agent-Fehler
* Paketmanagerfehler
* Timeout
* Recovery

---

# 80. Security Documentation Rules

Die Security-Dokumentation muss zwischen drei Zuständen unterscheiden:

```text
Implemented
Verified
Planned
```

Dabei bedeutet:

### Implemented

Die Funktion existiert im Code.

### Verified

Die Funktion wurde zusätzlich getestet und das Verhalten wurde bestätigt.

### Planned

Die Funktion ist noch nicht vollständig umgesetzt oder geprüft.

Ein geplanter Punkt darf nicht als implementierte Sicherheitskontrolle dargestellt werden.

---

# 81. Security Status Maintenance

Bei Änderungen an der Implementierung muss geprüft werden, ob diese Dokumentation noch korrekt ist.

Besonders relevant sind Änderungen an:

```text
server/app.py
server/security.py
server/init_db.py
server/migrations
agent/agent.py
agent/package_manager.py
agent/watcher.py
Dockerfile
docker-compose / docker run configuration
Nginx
systemd services
systemd timers
```

Nach sicherheitsrelevanten Änderungen muss die Dokumentation aktualisiert werden.

---

# 82. Security Regression Testing

Eine bereits getestete Sicherheitsfunktion darf durch spätere Änderungen nicht unbemerkt verschlechtert werden.

Beispiele:

```text
Login Rate Limiting
        ↓
spätere Auth-Änderung
        ↓
Regression Test
```

oder:

```text
Docker hardening
        ↓
neues Deployment
        ↓
runtime inspection
```

oder:

```text
Token rotation
        ↓
API change
        ↓
old token test
+
new token test
```

Die geplante automatisierte Security-Test-Suite soll diese Regressionen langfristig reproduzierbar prüfen.

---

# 83. Security Test Categories

Die zukünftige Testabdeckung soll unter anderem folgende Bereiche umfassen:

```text
Authentication
Authorization
Rate Limiting
CSRF
Session Handling
Client Tokens
Token Rotation
Token Revocation
Job Ownership
Atomic Job Claiming
Job Recovery
Package Execution
Timeout Handling
Database Integrity
Database Concurrency
Security Headers
Secret Handling
Container Hardening
```

Bereits vorhandene isolierte Tests sollen schrittweise in eine reproduzierbare Teststruktur überführt werden.

---

# 84. Simulation Testing

LUMS besitzt eine Simulationsmöglichkeit für Update-Abläufe.

Simulationen dienen dazu, die Joblogik zu testen, ohne einen echten Paketmanager-Vorgang auszuführen.

Simulationen sollen insbesondere prüfen:

```text
Job creation
Job claiming
Execution flow
Result handling
Failure handling
Timeout behavior
Recovery
```

Simulationen ersetzen jedoch keine echten Debian- und Arch-Tests.

Die reale Paketmanager-Ausführung bleibt erforderlich.

---

# 85. CI Security

Continuous Integration soll langfristig sicherheitsrelevante Regressionen automatisch erkennen.

Geplante Bereiche:

```text
Syntax checks
Unit tests
Security tests
Simulation tests
Static checks
Git diff validation
```

CI soll dabei keine Produktions-Secrets benötigen.

Test-Credentials müssen ausschließlich für Testzwecke erzeugt werden.

Produktionsdaten dürfen nicht Bestandteil der CI-Pipeline sein.

---

# 86. Security Audit Phases

Der Security Audit wird schrittweise durchgeführt.

Der aktuelle Audit-Stand umfasst:

```text
Phase 1
SQLite Foreign Keys
        ↓
COMPLETE

Phase 2
SQLite WAL / Busy Timeout
        ↓
COMPLETE

Phase 3
Update Timeout / process.kill()
        ↓
COMPLETE

Phase 4
Login Rate Limiting
        ↓
COMPLETE
```

Die nächsten vorgesehenen Bereiche sind:

```text
Phase 5
API Input Validation

Phase 6
Session Revocation

Phase 7
Token Rotation

Phase 8
get_ip() / Offline Networks

Phase 9
Job Recovery / Checkpointing

Phase 10
APT Robustness

Phase 11
Arch Reboot Detection

Phase 12
Unit Tests

Phase 13
Simulation Tests

Phase 14
CI

Phase 15
Logging

Phase 16
Versioning / Releases

Phase 17
RBAC

Phase 18
Complete Documentation Update
```

Die Reihenfolge kann während der Entwicklung angepasst werden, wenn neue technische Abhängigkeiten oder Sicherheitsprobleme festgestellt werden.

---

# 87. Responsible Security Reporting

Security-Probleme sollten verantwortungsvoll gemeldet werden.

Ein sinnvoller Security Report enthält:

* kurze Beschreibung
* betroffene Komponente
* Reproduktionsschritte
* erwartetes Verhalten
* tatsächliches Verhalten
* mögliche Auswirkungen
* relevante, redigierte Logs
* gegebenenfalls einen Vorschlag zur Behebung

Nicht veröffentlicht werden dürfen:

```text
Passwords
Client Tokens
Private Keys
Flask Secrets
Personal Information
Complete Production Databases
Unredacted Inventory Data
```

Logs, Screenshots und Konfigurationsdateien müssen vor der Weitergabe geprüft und redigiert werden.

---

# 88. Security Maintenance

Security Reviews sollten nach folgenden Änderungen erneut durchgeführt werden:

* Application Changes
* Authentication Changes
* Authorization Changes
* Docker Changes
* Nginx Changes
* Certificate Changes
* Database Schema Changes
* Agent Changes
* Package Manager Changes
* Watcher Changes
* Deployment Changes
* Secret Changes

Regelmäßig geprüft werden sollten insbesondere:

```text
Operating System
Docker Images
Python Dependencies
Flask Dependencies
Gunicorn
Nginx
TLS Configuration
File Permissions
Database Backups
Git History
Authentication
Authorization
Job Execution
Package Manager Coordination
Container Privileges
Container Capabilities
Secret Handling
Secret Rotation
Agent Configuration
systemd Services
systemd Timers
```

---

# 89. Security Change Workflow

Security-sensitive Änderungen folgen einem kontrollierten Ablauf:

```text
Inspect
   ↓
Understand current behavior
   ↓
Design change
   ↓
Implement
   ↓
Syntax Check
   ↓
Unit / Isolated Test
   ↓
Debian Test
   ↓
Arch Test
   ↓
Integration Test
   ↓
Git Diff Review
   ↓
Production Deployment
   ↓
Production Verification
   ↓
Documentation
```

Nach Änderungen werden insbesondere geprüft:

```bash
git status
git diff
git diff --check
```

Ein fehlgeschlagener Test darf nicht einfach durch eine Änderung der Dokumentation kaschiert werden.

Entweder wird die Implementierung korrigiert oder die Einschränkung wird dokumentiert.

---

# 90. Current Security Roadmap Status

Der aktuelle Stand lässt sich zusammenfassen als:

```text
[x] Non-root Docker container
[x] Dedicated application user
[x] Drop ALL capabilities
[x] Privileged container disabled
[x] Read-only root filesystem
[x] tmpfs /tmp
[x] Localhost-only application binding
[x] Protected secret file
[x] Read-only secret mount
[x] Secret isolation
[x] Flask secret rotation
[x] Administrator authentication
[x] Argon2 password hashing
[x] Login rate limiting
[x] Login rate-limit concurrency protection
[x] Login rate-limit audit logging
[x] Client authentication
[x] Client token hashing
[x] Client token rotation
[x] Client token invalidation
[x] Token rotation audit logging
[x] CSRF protection for administrative token rotation
[x] Job ownership validation
[x] Atomic job claiming
[x] Interrupted-job recovery
[x] Debian client communication
[x] Arch client communication
[x] APT support
[x] pacman support
[x] systemd-logind idle detection
[x] Gunicorn deployment
[x] HTTPS reverse proxy
[x] Security headers
[x] SQLite foreign-key enforcement
[x] SQLite WAL mode
[x] SQLite busy timeout
[x] SQLite integrity verification
[x] SQLite-aware backup
[x] Backup integrity verification
[x] Update execution timeout
[x] SIGTERM → grace period → SIGKILL fallback
[x] Production container hardening

[ ] Complete API input validation audit
[ ] Session revocation hardening
[ ] get_ip() / offline-network handling
[ ] Complete job checkpointing
[ ] Stronger APT/dpkg coordination
[ ] Arch reboot detection
[ ] Automated unit/security regression suite
[ ] Automated simulation test suite
[ ] CI security checks
[ ] Final logging review
[ ] Versioning / release security review
[ ] RBAC
[ ] Complete isolated backup restore test
[ ] Final security review
```

The completed items represent implemented and tested controls.

The open items remain security and robustness work.

---

# 91. Security Verification Principles

LUMS follows several operational rules.

## Rule 1 — Do not trust configuration alone

A configuration file stating:

```text
read-only
```

is not sufficient.

The running container must be inspected.

---

## Rule 2 — Do not trust successful startup alone

A running container does not prove that:

* authentication works,
* HTTPS works,
* database integrity is valid,
* clients can authenticate,
* update jobs work.

Each relevant layer must be tested.

---

## Rule 3 — Do not trust a backup merely because it exists

A backup must be:

```text
created
   ↓
protected
   ↓
integrity checked
   ↓
restored in isolation
```

The final step remains a separate verification requirement.

---

## Rule 4 — Treat exposed secrets as compromised

A secret that has been exposed must not be considered safe merely because the exposure is no longer visible.

It must be rotated.

---

## Rule 5 — Authentication does not equal authorization

A valid credential establishes identity.

It does not automatically grant access to every resource.

Authorization must still be checked.

---

## Rule 6 — Package installation is privileged execution

Update jobs execute operations that normally require elevated privileges.

The system must therefore control:

```text
Who
What
Where
When
Result
```

---

## Rule 7 — Documentation follows verification

Documentation should describe the actual tested state.

Incomplete functionality must remain explicitly marked as incomplete.

---

# 92. Final Verified Architecture

The current verified architecture is:

```text
                         Network
                            │
                            ▼
                       ┌─────────┐
                       │  Nginx  │
                       │  HTTPS  │
                       └────┬────┘
                            │
                     localhost only
                            │
                            ▼
                   ┌─────────────────┐
                   │ 127.0.0.1:5050 │
                   └────────┬────────┘
                            │
                       Docker mapping
                            │
                            ▼
             ┌──────────────────────────────┐
             │        LUMS Container        │
             │                              │
             │ User: lums                   │
             │ Privileged: false            │
             │ Capabilities: ALL dropped    │
             │ Root FS: read-only           │
             │                              │
             │ /tmp → tmpfs                 │
             │ /var/lib/lums → lums-data    │
             │ /run/secrets/lums_secret     │
             │          → read-only         │
             │                              │
             │ Gunicorn                     │
             │      ↓                       │
             │ Flask                        │
             │      ↓                       │
             │ SQLite                       │
             └──────────────┬───────────────┘
                            │
                     HTTPS + Bearer Token
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
       Debian 13 Client            Arch Linux Client
              │                           │
       lums-agent 1.7.0            lums-agent 1.7.0
              │                           │
          APT / dpkg                    pacman
              │                           │
              └─────────────┬─────────────┘
                            │
                            ▼
                       Result Report
                            │
                            ▼
                         LUMS API
```

---

# 93. Final Management / Execution Separation

The architecture deliberately separates:

```text
Management Plane
       │
       ├── Nginx
       ├── HTTPS
       ├── Gunicorn
       ├── Flask
       ├── Authentication
       ├── Authorization
       ├── Inventory
       ├── Job Management
       ├── Rate Limiting
       ├── Audit Logging
       └── SQLite

from

Execution Plane
       │
       ├── lums-agent
       ├── systemd
       ├── Idle Detection
       ├── Package Manager Abstraction
       ├── APT / dpkg
       └── pacman
```

The server manages the desired operation.

The client performs the actual package-management operation.

This separation reduces the need for the central server to directly execute operating-system commands on managed clients.

---

# 94. Final Security State

The current LUMS implementation has verified controls across:

```text
Container
   ↓
Network
   ↓
TLS
   ↓
Authentication
   ↓
Rate Limiting
   ↓
Authorization
   ↓
Secrets
   ↓
Tokens
   ↓
Jobs
   ↓
Recovery
   ↓
Agent
   ↓
Package Manager
   ↓
Database
   ↓
Backups
```

The project still has open security work.

A final security review must therefore not be claimed until the remaining audit areas have been implemented and tested.

---

# 95. Final Security Principles

The following principles apply to LUMS:

1. Never store secrets in Git.
2. Never expose the Flask/Gunicorn application directly to the network.
3. Use HTTPS for client communication.
4. Keep TLS verification enabled.
5. Separate authentication from authorization.
6. Validate client identity server-side.
7. Protect administrator credentials.
8. Protect client tokens.
9. Protect TLS private keys.
10. Protect the mounted Flask secret.
11. Keep database backups secure.
12. Verify backups rather than trusting file existence.
13. Do not remove persistent volumes during ordinary troubleshooting.
14. Do not automatically reboot clients.
15. Review changes before deployment.
16. Test security-sensitive changes.
17. Document incidents and configuration changes.
18. Do not claim incomplete security controls are fully implemented.
19. Keep update execution controlled and auditable.
20. Harden the container incrementally.
21. Treat secret isolation and secret rotation as separate controls.
22. Treat previously exposed secrets as compromised until rotated.
23. Rotate client tokens through the authenticated administrative workflow.
24. Verify replacement credentials before closing a credential change.
25. Keep production secrets outside Git and outside normal container environment variables where practical.
26. Use distribution-specific package-manager implementations behind a controlled abstraction.
27. Validate job ownership on the server.
28. Use atomic state transitions for job claiming and recovery.
29. Prefer conservative behavior when system state cannot be reliably determined.
30. Keep production documentation synchronized with verified implementation state.
31. Test recovery paths, not only successful paths.
32. Treat security hardening as a continuous process rather than a one-time configuration.

---

# 96. Final Principle

LUMS is designed to centralize Linux update management without removing operational control from the administrator.

The system should remain:

* Transparent
* Auditable
* Controlled
* Secure
* Documented
* Maintainable

The architecture deliberately separates:

```text
Management Plane
       │
       ├── Nginx
       ├── Gunicorn
       ├── Flask
       ├── Authentication
       ├── Authorization
       ├── Inventory
       ├── Rate Limiting
       ├── Job Management
       └── Database

from

Execution Plane
       │
       ├── lums-agent
       ├── systemd
       ├── Idle Detection
       ├── Package Manager Abstraction
       └── APT / dpkg / pacman
```

Security improvements are implemented one controlled layer at a time.

The established hardening workflow remains:

```text
Inspect
   ↓
Test
   ↓
Verify
   ↓
Production
   ↓
Verify
   ↓
Document
```

> **LUMS — Linux Update Management without the noise.**
>
> **Secure the management plane. Keep execution controlled.**
>
> **One change. One test. One verified result.**
