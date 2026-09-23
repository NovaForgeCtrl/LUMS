# LUMS Security

> **Linux Update Management Server**
>
> Security principles, operational requirements, hardening status, and responsible handling of sensitive information in LUMS.

**Version:** 3.0
**Project:** LUMS
**Slogan:** Linux Update Management without the noise.

---

# 1. Security Philosophy

LUMS follows a simple principle:

> **Centralized management does not mean centralized trust.**

LUMS manages Linux clients, receives inventory information, reports update status, and distributes update jobs.

The actual package-management operation takes place on the managed Linux client.

LUMS therefore separates the **management plane** from the **execution plane**.

```text
                    ┌──────────────────────────┐
                    │       LUMS Server        │
                    │                          │
                    │ Nginx                    │
                    │ HTTPS                    │
                    │ Gunicorn                 │
                    │ Flask                    │
                    │ Authentication           │
                    │ Authorization            │
                    │ Inventory                │
                    │ Update Jobs              │
                    │ SQLite                   │
                    └────────────┬─────────────┘
                                 │
                           HTTPS + Token
                                 │
              ┌──────────────────┴──────────────────┐
              │                                     │
      ┌───────▼────────┐                   ┌────────▼───────┐
      │ Debian Client  │                   │  Arch Client   │
      │                │                   │                │
      │ lums-agent     │                   │ lums-agent     │
      │ APT / dpkg     │                   │ pacman         │
      │ systemd        │                   │ systemd        │
      └────────────────┘                   └────────────────┘
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

This document covers:

* Docker deployment security
* Container privilege reduction
* Linux capabilities
* Read-only filesystems
* Secret management
* Secret rotation
* Administrator authentication
* Client authentication
* Client token lifecycle
* Authorization
* Job ownership
* Atomic job claiming
* Interrupted-job recovery
* TLS
* Nginx
* Security headers
* SQLite protection
* Backup handling
* Restore requirements
* systemd agent services
* Idle detection
* Package-manager abstraction
* Update execution
* Logging
* Git security
* Deployment security
* Incident handling
* Security testing
* Remaining hardening work

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

The current tested client package managers are:

```text
APT
pacman
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
   ├── Worker
   ├── Worker
   └── Flask application
          │
          ├── Authentication
          ├── Authorization
          ├── Inventory
          ├── Update Jobs
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

## Management Plane

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
Job management
```

The management plane is responsible for:

* administrator access,
* client authentication,
* inventory,
* job creation,
* job assignment,
* job status,
* audit information,
* client management.

## Execution Plane

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

* collecting package information,
* detecting available updates,
* claiming authorized jobs,
* executing package operations,
* reporting results.

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
1.6.0
```

The agent version is defined centrally in:

```text
agent/agent.py
```

The tested Arch client and repository copy were verified byte-for-byte identical.

The agent therefore uses the same tested implementation across the current Debian and Arch environments.

---

# 7. Security Status

The following controls are currently implemented and verified:

| Security control                            | Status   |
| ------------------------------------------- | -------- |
| Non-root Docker container                   | Verified |
| UID 10001 container user                    | Verified |
| `CAP_DROP=ALL`                              | Verified |
| Privileged container disabled               | Verified |
| Read-only root filesystem                   | Verified |
| `/tmp` isolated through tmpfs               | Verified |
| Secret supplied through protected file      | Verified |
| Secret mount read-only                      | Verified |
| Production Flask secret rotation            | Verified |
| Gunicorn deployment                         | Verified |
| HTTPS reverse proxy                         | Verified |
| Localhost-only application binding          | Verified |
| Security headers                            | Verified |
| Administrator authentication                | Verified |
| Client Bearer authentication                | Verified |
| Client token rotation                       | Verified |
| Token invalidation                          | Verified |
| Token rotation audit logging                | Verified |
| CSRF protection for administrative rotation | Verified |
| Atomic job claiming                         | Verified |
| Job ownership validation                    | Verified |
| Interrupted-job recovery                    | Verified |
| Debian client reporting                     | Verified |
| Arch client reporting                       | Verified |
| Debian update job execution                 | Verified |
| Arch update job execution                   | Verified |
| APT package-manager abstraction             | Verified |
| pacman package-manager abstraction          | Verified |
| systemd-logind idle detection               | Verified |

Remaining hardening work:

```text
Update execution hardening
Full backup / restore test
Automated security regression tests
Final security review
```

---

# 8. Docker Security

The LUMS application runs as a dedicated non-root user.

Current container identity:

```text
User:
    lums

UID:
    10001
```

The container must not run as root.

Verify:

```bash
sudo docker inspect lums \
    --format 'User={{.Config.User}}'
```

Expected:

```text
User=lums
```

Running the application as a dedicated non-root user reduces the impact of an application-level compromise.

---

# 9. Linux Capability Hardening

LUMS does not require additional Linux capabilities.

Production therefore uses:

```text
--cap-drop=ALL
```

Verify:

```bash
sudo docker inspect lums \
    --format 'CapDrop={{json .HostConfig.CapDrop}}'
```

Expected:

```text
["ALL"]
```

The container must also not be privileged.

Verify:

```bash
sudo docker inspect lums \
    --format 'Privileged={{.HostConfig.Privileged}}'
```

Expected:

```text
false
```

The application must continue functioning without additional Linux capabilities.

---

# 10. Read-Only Root Filesystem

The production container uses:

```text
--read-only
```

The container root filesystem is therefore not writable during normal operation.

Persistent application state is stored separately:

```text
lums-data
    ↓
/var/lib/lums
```

Temporary writable data uses:

```text
/tmp
    ↓
tmpfs
```

The current tmpfs configuration is:

```text
/tmp:rw,nosuid,nodev,noexec
```

Verify:

```bash
sudo docker inspect lums \
    --format 'ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}'
```

Expected:

```text
true
```

This prevents normal application writes from modifying the container image filesystem.

---

# 11. Container Filesystem Layout

The security-relevant filesystem layout is:

```text
Container
│
├── /                    READ-ONLY
│
├── /tmp                 tmpfs
│
├── /var/lib/lums       persistent Docker volume
│
└── /run/secrets/
      └── lums_secret   READ-ONLY
```

This deliberately separates:

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

# 12. Secret Management

The Flask application secret is security-sensitive.

Production secrets must never be:

* committed to Git,
* written into documentation,
* printed to logs,
* included in screenshots,
* included in bug reports,
* exposed through normal container environment variables,
* copied into source files.

Production uses:

```text
/etc/lums/secrets/lums_secret
```

The secret is mounted into the container:

```text
Host
/etc/lums/secrets/lums_secret
        │
        │ read-only bind mount
        ▼
Container
/run/secrets/lums_secret
```

The application is configured with:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

The actual secret value is intentionally never documented.

---

# 13. Secret File Permissions

The host secret directory should be restricted:

```text
/etc/lums/secrets
```

Expected:

```text
root:root
0700
```

The secret file itself is restricted to the required host and container identities.

A typical configuration is:

```text
root:10001
0640
```

Verify:

```bash
sudo stat /etc/lums/secrets/lums_secret
```

The secret mount inside the container must be read-only.

Verify:

```bash
sudo docker inspect lums \
    --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} RW={{.RW}}{{"\n"}}{{end}}'
```

Expected:

```text
/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
```

---

# 14. Secret Environment Isolation

The production Flask secret must not be supplied through:

```text
LUMS_SECRET_KEY
```

Verify:

```bash
sudo docker exec lums sh -c '
if [ -n "${LUMS_SECRET_KEY:-}" ]; then
    echo "PRESENT"
else
    echo "ABSENT"
fi
'
```

Expected:

```text
ABSENT
```

The application instead reads:

```text
/run/secrets/lums_secret
```

Verify:

```bash
sudo docker exec lums sh -c '
if [ -r /run/secrets/lums_secret ]; then
    echo "READABLE"
else
    echo "NOT READABLE"
fi
'
```

Expected:

```text
READABLE
```

---

# 15. Secret Rotation

Secret isolation and secret rotation are separate security controls.

The Flask secret was previously exposed through diagnostic output.

The previous value is intentionally not reproduced.

The exposure was treated as a credential compromise.

The rotation process was:

```text
Identify exposure
        ↓
Isolate secret from normal environment
        ↓
Test rotation in isolation
        ↓
Generate replacement secret
        ↓
Replace protected secret file
        ↓
Restart LUMS
        ↓
Verify old sessions
        ↓
Verify new authentication
        ↓
Remove temporary old-secret backup
```

The replacement production secret is now active.

The old value must not be reused.

---

# 16. Session Invalidation

Changing the Flask secret affects existing application sessions.

This behavior was explicitly tested before production rotation.

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

A new login establishes a valid session using the new secret.

This makes secret rotation an operational event that must be planned and verified.

---

# 17. Administrator Authentication

LUMS provides administrator authentication for the web interface.

Administrator passwords are protected using Argon2.

The password itself must never be stored in plaintext.

The authentication boundary is:

```text
Browser
   ↓
HTTPS
   ↓
Nginx
   ↓
Gunicorn
   ↓
Flask
   ↓
Authentication
```

Authentication and authorization are treated as separate concepts.

---

# 18. Client Authentication

Linux clients authenticate against the LUMS API using Bearer tokens.

Example:

```text
Authorization: Bearer <CLIENT_TOKEN>
```

The server hashes the supplied token and compares the resulting digest against the stored token digest.

The plaintext client token is not stored as normal database state.

The current token generation uses cryptographically secure randomness.

Conceptually:

```text
Generate random token
        ↓
Hash token
        ↓
Store hash
        ↓
Return token once
```

---

# 19. Client Token Lifecycle

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

The plaintext token is only presented when required for initial configuration or rotation.

It must not be written to:

* audit logs,
* application logs,
* Git,
* documentation,
* screenshots.

---

# 20. Client Token Rotation

Administrative token rotation is implemented through the client-management workflow.

The rotation operation:

1. identifies the client,
2. generates a new cryptographically random token,
3. hashes the token,
4. replaces the stored token hash,
5. updates token metadata,
6. invalidates the previous credential,
7. creates an audit event,
8. returns the new token once.

The previous token becomes invalid immediately.

---

# 21. Token Rotation Authorization

Token rotation is an administrative operation.

It requires:

```text
Valid administrator session
+
Valid CSRF protection
```

Expected failure behavior includes:

```text
No administrator session
    → 401

Missing/invalid CSRF token
    → 400

Unknown client
    → 404
```

A client token itself must never be sufficient to authorize administrative token rotation.

---

# 22. Token Rotation Audit Logging

Successful token rotation creates an audit event.

The audit event records that the operation occurred without storing the replacement credential.

Conceptually:

```text
action:
    client.token.rotate

target:
    client:<CLIENT_ID>

result:
    success
```

The actual token value is never written to the audit event.

This provides accountability without turning the audit log into a credential store.

---

# 23. Frontend Token Rotation

The client detail interface provides a token rotation control.

Before rotation, the administrator is warned that:

* the existing token becomes invalid,
* the LUMS agent must be updated,
* the new token will only be displayed once.

After successful rotation, the replacement token can be copied.

The token is not intended to remain permanently visible in the interface.

The browser is treated as a presentation layer and not as a trusted authorization source.

---

# 24. Token Rotation Verification

The token lifecycle was tested independently.

The verified flow was:

```text
Token A
   ↓
Authentication succeeds
   ↓
Rotate
   ↓
Token B
```

Then:

```text
Token A → rejected
Token B → accepted
```

The tests also covered:

```text
No administrator session
    → rejected

Invalid/missing CSRF protection
    → rejected

Unknown client
    → rejected
```

The audit event was created successfully.

The token value was not stored in the audit event.

---

# 25. Production Token Verification

After token rotation testing, the production agent was updated with the replacement credential.

The agent successfully reported to LUMS.

The verified flow was:

```text
Agent
   ↓
HTTPS
   ↓
Bearer authentication
   ↓
Client identification
   ↓
System report
   ↓
LUMS API
   ↓
Database
```

The production client subsequently appeared online again.

This verified the complete credential-rotation path.

---

# 26. Authorization

Authentication answers:

```text
Who are you?
```

Authorization answers:

```text
What are you allowed to do?
```

LUMS validates authenticated client ownership for client-specific operations.

A client must not be able to access another client's jobs merely by changing a client ID in a request.

The server therefore derives the authenticated client identity from the authentication layer.

---

# 27. Job Ownership

Client-specific job operations validate:

```text
Authenticated client
        +
Requested job
        +
Job owner
```

Conceptually:

```text
authenticated_client.id
        ==
job.client_id
```

If the relationship does not match, the operation must be rejected.

This prevents cross-client job access.

---

# 28. Atomic Job Claiming

Job claiming is performed using an atomic state transition.

The intended transition is:

```text
pending
   ↓
running
```

The operation must ensure that two clients cannot successfully claim the same pending job through normal concurrent execution.

Conceptually:

```text
Client A ──┐
           ├── claim
Client B ──┘
           ↓
       one winner
```

The winning client becomes responsible for executing and reporting the job.

---

# 29. Job Result Authorization

A job result must be associated with the authenticated client that owns the job.

The server therefore validates:

```text
authenticated client
        ==
job owner
```

before accepting a result.

A client cannot legitimately submit a result for another client's job.

---

# 30. Interrupted Jobs

An update operation can be interrupted by:

* agent termination,
* system shutdown,
* network interruption,
* process failure,
* unexpected client failure.

A job may therefore remain in:

```text
running
```

without receiving its expected final result.

LUMS provides controlled recovery for this situation.

---

# 31. Job Recovery

Recovery changes an interrupted job from:

```text
running
```

to:

```text
abandoned
```

The recovery operation validates:

* job existence,
* client ownership,
* current job state,
* valid recovery transition.

The operation records:

```text
finished_at
recovery reason
update history
```

The job is not falsely reported as successful.

---

# 32. Recovery Reason

The recovery reason distinguishes an interrupted execution from a normal failure or success.

The current recovery reason is:

```text
Agent did not submit a final result.
```

This allows the history to distinguish:

```text
success
failed
abandoned
```

---

# 33. Recovery Race Protection

Recovery uses a conditional state transition.

If another operation changes the job state first, the recovery operation must not overwrite the newer state.

Conceptually:

```text
running
   │
   ├── agent result
   │
   └── recovery
```

Only one valid transition should win.

This prevents stale recovery requests from silently modifying already-completed jobs.

---

# 34. Recovery Testing

Controlled recovery testing verified:

```text
status:
    abandoned

finished_at:
    populated

recovery_reason:
    Agent did not submit a final result.
```

The associated history entry was preserved.

Package statistics were preserved.

The test data was removed afterwards.

A real update job was subsequently executed successfully.

This confirmed that recovery did not break normal update execution.

---

# 35. Agent Security

The LUMS agent communicates with the server using HTTPS.

The agent configuration contains the server endpoint, client credential, and CA configuration.

Typical configuration:

```text
LUMS_BASE
LUMS_TOKEN
LUMS_CA_FILE
```

Example:

```text
LUMS_BASE="https://Server IP"
LUMS_TOKEN="<REDACTED>"
LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt"
```

The actual credential is never documented.

TLS verification must remain enabled.

Certificate problems must be fixed rather than bypassed by disabling verification.

---

# 36. Agent Configuration Protection

The agent configuration is stored outside the Git repository.

Typical location:

```text
/etc/default/lums-agent
```

The configuration should be readable only by the identities that require it.

Sensitive values must never be committed.

Verify:

```bash
sudo stat /etc/default/lums-agent
```

The actual token value must not appear in diagnostic output shared publicly.

---

# 37. systemd Agent Service

The LUMS agent runs as a systemd service.

The service is designed as a `oneshot` operation.

A successful execution therefore normally ends with:

```text
inactive (dead)
```

after the agent process exits successfully.

This is expected behavior.

The recurring execution is handled by the corresponding timer.

---

# 38. systemd Agent Timer

The agent timer periodically starts the service.

Current scheduling uses a recurring systemd timer.

Conceptually:

```text
systemd timer
      ↓
lums-agent.service
      ↓
agent.py
      ↓
report / job execution
      ↓
exit
      ↓
wait for next timer
```

The timer remains active while the oneshot service starts and exits for each cycle.

---

# 39. Idle Detection

The current agent does not rely on:

```text
w -h
```

for idle detection.

Idle detection uses:

```text
systemd-logind
```

through:

```text
loginctl
```

The agent examines relevant user sessions and uses:

```text
Class
Type
TTY
State
IdleHint
IdleSinceHintMonotonic
```

to determine whether an interactive user session is currently idle.

---

# 40. Idle Detection Security

The purpose of idle detection is to avoid unnecessarily disruptive package operations while a user is actively working.

The current implementation:

* ignores irrelevant system sessions,
* considers user sessions,
* recognizes graphical and TTY sessions,
* detects active sessions through `IdleHint`,
* calculates idle duration using the logind monotonic timestamp,
* reports whether idle detection is supported.

The result includes:

```text
idle
idle_seconds
threshold_seconds
idle_source
idle_supported
```

The current source is:

```text
loginctl
```

---

# 41. Idle Detection Failure Behavior

If logind information cannot be retrieved reliably, the agent does not pretend to know that the system is idle.

Failure is treated conservatively.

The agent therefore avoids using an unreliable idle state as permission to perform potentially disruptive operations.

This is preferable to treating an unknown state as confirmed user inactivity.

---

# 42. Package Manager Abstraction

Package management is implemented through a dedicated abstraction.

The agent detects:

```text
APT
pacman
```

and selects the appropriate implementation.

Conceptually:

```text
                 package_manager.py
                         │
             ┌───────────┴───────────┐
             │                       │
       AptPackageManager      PacmanPackageManager
             │                       │
        apt / dpkg                 pacman
```

This prevents distribution-specific package-manager commands from being duplicated throughout the main agent.

---

# 43. APT / dpkg

On Debian-based clients, LUMS uses:

```text
apt
apt-get
apt-cache
dpkg-query
```

Examples of supported operations include:

```text
Package inventory
Update detection
Package installation
Package removal
Package updates
System updates
```

The actual package operation occurs on the client.

---

# 44. pacman

On Arch Linux clients, LUMS uses:

```text
pacman
```

Examples of supported operations include:

```text
Package inventory
Update detection
Package installation
Package removal
Package updates
System updates
```

System update operations use the native Arch package-management mechanism.

The LUMS agent does not attempt to translate Arch package management into APT semantics.

---

# 45. Update Execution Security

Update execution is a privileged client-side operation.

LUMS therefore treats package management as a security-sensitive execution boundary.

Update jobs must:

* be authenticated,
* belong to the correct client,
* be valid jobs,
* transition through controlled states,
* be executed by the intended agent,
* produce an explicit result,
* remain auditable.

The agent must not execute arbitrary unauthenticated commands received from the network.

---

# 46. Package Operation Abstraction

The supported package operations are represented through the package-manager abstraction.

Examples include:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

The action is interpreted by the client agent and passed to the selected package-manager implementation.

This separates:

```text
LUMS job semantics
```

from:

```text
Distribution-specific package commands
```

---

# 47. Package Manager Coordination

Package-manager operations are security-sensitive because package managers generally require elevated privileges.

LUMS therefore uses controlled execution for its own package operations.

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

The current LUMS execution lock reduces collisions within LUMS-controlled operations.

Complete coordination with arbitrary external package-manager processes remains a hardening task.

---

# 48. Reboot Handling

LUMS must not reboot a client merely because packages were installed.

A reboot requirement is separate from successful package installation.

The system should distinguish:

```text
Update successful
```

from:

```text
Reboot required
```

Any future automatic reboot mechanism must be explicitly designed, authorized, logged, and tested.

---

# 49. Nginx Security

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

---

# 50. HTTP to HTTPS

HTTP access is redirected to HTTPS.

Conceptually:

```text
HTTP :80
   ↓
redirect
   ↓
HTTPS :443
```

Test:

```bash
curl -I http://127.0.0.1/
```

The expected result is an HTTP redirect to the HTTPS endpoint.

---

# 51. TLS

LUMS uses HTTPS for client and browser communication.

TLS verification must remain enabled for agents.

Supported modern TLS versions should include:

```text
TLS 1.2
TLS 1.3
```

Older insecure protocols must remain disabled.

Certificates must contain the correct Subject Alternative Name.

Private key permissions must be restricted.

Validate the Nginx configuration:

```bash
sudo nginx -t
```

---

# 52. Self-Signed Certificates

Self-signed certificates may be used in controlled laboratory environments.

In that case, the client must explicitly trust the appropriate CA or certificate.

The LUMS agent must still verify the certificate chain.

A certificate warning must not be solved by disabling TLS verification.

For larger or externally accessible deployments, a certificate infrastructure appropriate to the deployment environment should be used.

---

# 53. Security Headers

The application provides security headers intended to reduce common browser-side attack surfaces.

The current policy includes:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
```

The permissions policy restricts unnecessary browser capabilities such as:

```text
camera
microphone
geolocation
payment
```

The Content Security Policy restricts application resources to expected origins.

The policy includes restrictions equivalent to:

```text
default-src 'self'
script-src 'self'
style-src 'self'
img-src 'self' data:
font-src 'self'
connect-src 'self'
object-src 'none'
base-uri 'self'
frame-ancestors 'none'
form-action 'self'
```

Security headers must be rechecked after Nginx or frontend changes.

---

# 54. Docker Network Exposure

The application uses:

```text
127.0.0.1:5050:5000
```

This means:

```text
Host localhost:5050
        ↓
Container :5000
```

It must not be casually changed to:

```text
0.0.0.0:5050:5000
```

Doing so would expose the application port on the network interface.

If the network architecture is changed, firewall and reverse-proxy controls must be redesigned and retested.

---

# 55. Port Security

The externally required services are expected to be limited to those required by the deployment.

Typical services:

```text
22/tcp
80/tcp
443/tcp
```

The application ports:

```text
5000
5050
```

must remain internal.

Check listening sockets:

```bash
sudo ss -lntp
```

The LUMS application should appear bound to:

```text
127.0.0.1:5050
```

rather than:

```text
0.0.0.0:5050
```

---

# 56. Firewall Security

Only required network services should be exposed.

For environments using UFW:

```bash
sudo ufw status verbose
```

Application ports should not be opened merely for troubleshooting.

If temporary access is required during testing, it should be removed afterwards.

Firewall configuration must be reviewed after:

* network changes,
* Nginx changes,
* Docker changes,
* new services,
* port changes.

---

# 57. Database Security

LUMS uses SQLite.

The database is stored in:

```text
/var/lib/lums/lums.db
```

The directory is backed by:

```text
lums-data
```

The database must not be stored inside:

```text
/opt/lums-public
```

or committed to Git.

The persistent volume must not be removed during ordinary troubleshooting.

---

# 58. Database Integrity

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

An integrity check should be performed after major database-related deployment changes.

---

# 59. SQLite Backup

SQLite backups should use a SQLite-aware mechanism.

A backup must not simply be treated as a normal file copy while the database is actively changing.

Example:

```bash
sudo docker run --rm \
    --entrypoint python3 \
    -v lums-data:/var/lib/lums:ro \
    -v /tmp:/backup \
    lums:latest \
    -c '
import sqlite3

source = sqlite3.connect("/var/lib/lums/lums.db")
target = sqlite3.connect("/backup/lums.db.backup")

with target:
    source.backup(target)

target.close()
source.close()

print("SQLite backup completed")
'
```

The resulting backup should be moved to a protected backup location.

Example:

```text
/var/backups/lums/
```

---

# 60. Backup Protection

Backup files contain sensitive application information.

They may contain:

* users,
* clients,
* audit records,
* job information,
* operational metadata.

Backups therefore require access control.

Example:

```bash
sudo chown root:root /var/backups/lums/lums.db.backup
sudo chmod 600 /var/backups/lums/lums.db.backup
```

Backups must never be committed to Git.

---

# 61. Backup Verification

A backup is not considered valid merely because the file exists.

Verify the SQLite integrity:

```bash
sudo python3 - <<'PY'
import sqlite3

path = "/var/backups/lums/lums.db.backup"

db = sqlite3.connect(path)

print(
    "integrity =",
    db.execute("PRAGMA integrity_check").fetchone()[0]
)

db.close()
PY
```

Expected:

```text
integrity = ok
```

Backup verification should be performed before relying on the backup for recovery.

---

# 62. Restore

A complete restore test remains outstanding.

The intended procedure is:

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

# 63. Git Security

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

Before committing:

```bash
cd /opt/lums-public

git status
git diff
git diff --check
```

Review all changed files.

The Git identity for LUMS commits is:

```text
Name:
NovaForgeCtrl

Email:
xxxxnoreply.github.com
```

---

# 64. Git Repository Verification

The repository should be checked before deployment.

Example:

```bash
cd /opt/lums-public

git fetch origin

echo "=== STATUS ==="
git status -sb

echo "=== LOCAL HEAD ==="
git rev-parse HEAD

echo "=== GITHUB origin/main ==="
git rev-parse origin/main

echo "=== DIFFERENCE ==="
git log --oneline --left-right HEAD...origin/main
```

A clean synchronized repository should show:

```text
## main...origin/main
```

with matching commit IDs and no left/right differences.

---

# 65. Docker Image Security

The production image must be built from reviewed source.

Build:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Inspect:

```bash
sudo docker image inspect \
    lums:latest
```

Verify that the image specifies the intended non-root user.

A successful image build does not prove:

* application correctness,
* deployment correctness,
* database integrity,
* security correctness,
* client communication.

Those properties must be tested separately.

---

# 66. Production Container

The hardened container configuration uses:

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

This provides:

```text
Non-root execution
+
No Linux capabilities
+
Read-only root filesystem
+
Protected secret file
+
Read-only secret mount
+
Persistent database volume
+
Localhost-only application binding
```

---

# 67. Container Restart Verification

After deployment:

```bash
sudo docker restart lums
```

Then:

```bash
sudo docker ps \
    --filter "name=^lums$"
```

Review logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

The application should start without a crash loop.

Gunicorn should successfully start the application workers.

---

# 68. Container Runtime Verification

Check the runtime configuration:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
'
```

Expected properties:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
```

---

# 69. Volume Verification

Check mounts:

```bash
sudo docker inspect lums \
    --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} RW={{.RW}}{{"\n"}}{{end}}'
```

The database volume should be present:

```text
lums-data -> /var/lib/lums RW=true
```

The secret mount should be present:

```text
/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
```

Persistent application data must survive container recreation.

---

# 70. Deployment Security Workflow

Before deployment:

```bash
cd /opt/lums-public

git status --short
git fetch origin
git log --oneline --decorate -3
git diff --check
```

Update only when the working tree is in the expected state:

```bash
git pull --ff-only origin main
```

Build:

```bash
sudo docker build -t lums:latest .
```

Before replacing a production container:

```text
Verify source
   ↓
Verify image
   ↓
Verify database
   ↓
Create SQLite backup
   ↓
Verify backup
   ↓
Replace container
   ↓
Verify application
   ↓
Verify HTTPS
   ↓
Verify client communication
```

---

# 71. Production Container Replacement

When only the container must be replaced:

```bash
sudo docker stop lums
sudo docker rm lums
```

The persistent volume must remain.

Do not remove:

```text
lums-data
```

unless intentionally performing a complete data-destruction operation with a verified backup and explicit recovery plan.

Recreate the container using the tested hardened configuration.

---

# 72. Deployment Verification

After deployment verify:

```text
1. Container running
2. Correct image
3. Correct container user
4. Localhost-only application binding
5. Persistent volume mounted
6. Database accessible
7. Database integrity valid
8. Gunicorn starts
9. HTTPS works
10. HTTP redirects to HTTPS
11. Security headers remain present
12. Administrator login works
13. Client authentication works
14. Client reporting works
15. Update jobs remain available
16. Job execution works
17. Root filesystem is read-only
18. All capabilities are dropped
19. Secret environment variable is absent
20. Secret file is readable
21. Secret mount is read-only
22. Container restart works
```

---

# 73. Logging

Logs may contain operational information such as:

* HTTP requests,
* timestamps,
* job identifiers,
* client identifiers,
* application errors,
* package statistics,
* execution status.

Logs must not intentionally contain:

* passwords,
* client tokens,
* Flask secrets,
* TLS private keys.

Before sharing logs externally:

```text
Review
   ↓
Redact
   ↓
Review again
   ↓
Share
```

---

# 74. Audit Logging

Security-relevant administrative actions should produce audit information.

Examples include:

```text
Authentication events
Client changes
Token rotation
Job operations
Recovery operations
Security-sensitive administrative actions
```

Audit information should contain enough information to understand:

```text
what happened
when it happened
which object was affected
whether the operation succeeded
```

Sensitive credentials must not be stored in audit records.

---

# 75. Incident Handling

Security incidents should be handled systematically.

General workflow:

```text
Detect
   ↓
Contain
   ↓
Investigate
   ↓
Rotate affected credentials
   ↓
Recover
   ↓
Verify
   ↓
Document
```

Do not destroy evidence unnecessarily during troubleshooting.

---

# 76. Compromised Client Token

If a client token is compromised:

1. Identify the affected client.
2. Rotate the token.
3. Verify the old token is invalid.
4. Update the client configuration.
5. Verify the new token.
6. Review recent client activity.
7. Review relevant logs.
8. Document the incident.

The known-compromised token must not remain active.

---

# 77. Compromised Flask Secret

If the Flask secret is compromised:

1. Restrict access if necessary.
2. Treat the existing secret as compromised.
3. Generate a replacement.
4. Replace the protected secret file.
5. Restart LUMS.
6. Verify old sessions are invalid.
7. Verify new authentication.
8. Review related credentials.
9. Remove temporary copies of the old secret.
10. Document the incident.

The compromised secret must not be reused.

---

# 78. Compromised TLS Private Key

If a TLS private key is compromised:

1. Replace the certificate/private-key pair.
2. Update trusted certificates where required.
3. Reload Nginx.
4. Verify certificate validation.
5. Review access logs.
6. Determine the affected period.
7. Document the incident.

---

# 79. Exposed Database or Backup

If a database or backup becomes exposed:

1. Restrict access.
2. Determine what data was exposed.
3. Review authentication-related information.
4. Rotate affected credentials.
5. Review client tokens where appropriate.
6. Replace compromised backups if necessary.
7. Review access logs.
8. Document the incident.

---

# 80. Previously Exposed Flask Secret

The previous Flask secret exposure is treated as a completed security incident.

The value is intentionally not reproduced.

The response was:

```text
Exposure identified
        ↓
Secret isolation implemented
        ↓
Rotation tested
        ↓
Replacement secret generated
        ↓
Protected secret file updated
        ↓
Production restarted
        ↓
Old sessions invalidated
        ↓
New authentication verified
        ↓
Temporary old-secret material removed
```

The previous value is no longer the active production secret.

---

# 81. Debian Client Verification

The Debian client has successfully completed the LUMS agent communication flow.

Verified:

```text
Agent:
    1.6.0

OS:
    Debian

Architecture:
    x86_64

Package manager:
    APT

Report:
    accepted

Authentication:
    successful

Update job:
    successful
```

The client successfully completed both inventory reporting and update-job execution.

---

# 82. Arch Linux Client Verification

The Arch Linux client has successfully completed the same LUMS management flow.

Verified:

```text
Agent:
    1.6.0

OS:
    Arch Linux

Architecture:
    x86_64

Kernel:
    7.2.6-arch2-1

Package manager:
    pacman

systemd:
    261.3-1

Python:
    3.14.7

pacman:
    7.1.0

Report:
    accepted

Authentication:
    successful

Update job:
    successful
```

The Arch agent was additionally verified against the repository copy.

The SHA-256 checksum matched the repository version.

---

# 83. Cross-Distribution Update Flow

The current architecture supports:

```text
                    LUMS
                     │
             UPDATE_SYSTEM
                     │
          ┌──────────┴──────────┐
          │                     │
       Debian                 Arch
          │                     │
       lums-agent            lums-agent
          │                     │
        APT                  pacman
          │                     │
        result                result
          │                     │
          └──────────┬──────────┘
                     │
                     ▼
                  LUMS
```

The management layer therefore remains distribution-independent while the client package-manager layer remains distribution-specific.

---

# 84. Security Testing Checklist

## Container

* [x] Container runs as non-root
* [x] UID 10001 verified
* [x] Container is not privileged
* [x] All Linux capabilities dropped
* [x] Root filesystem is read-only
* [x] `/tmp` uses tmpfs
* [x] `/tmp` uses `nosuid`
* [x] `/tmp` uses `nodev`
* [x] `/tmp` uses `noexec`
* [x] Persistent database volume is separate
* [x] Secret mount is separate
* [x] Secret mount is read-only
* [x] Application binding is localhost-only

## Secrets

* [x] Flask secret isolated from normal environment
* [x] Secret stored outside Git
* [x] Secret mounted read-only
* [x] Secret rotation tested
* [x] Production secret rotated
* [x] Old production secret invalidated
* [x] Temporary old-secret material removed
* [x] Client token generation uses cryptographically secure randomness
* [x] Client token hash stored instead of plaintext
* [x] Client token rotation implemented
* [x] Previous client token invalidated
* [x] Token rotation audit event implemented
* [x] Token values excluded from audit records

## Authentication

* [x] Administrator authentication implemented
* [x] Argon2 password hashing
* [x] Invalid credentials rejected
* [x] Client Bearer authentication implemented
* [x] Invalid client token rejected
* [x] Protected endpoints require authentication
* [x] Token rotation requires administrator authentication
* [x] CSRF protection for administrative token rotation

## Authorization

* [x] Client identity established server-side
* [x] Client/job ownership checked
* [x] Job result ownership checked
* [x] Recovery ownership checked
* [x] Atomic job claiming
* [ ] Full role-based administrative authorization model

## Agent

* [x] Agent uses HTTPS
* [x] TLS verification enabled
* [x] CA configuration supported
* [x] Agent credentials stored outside Git
* [x] systemd timer configured
* [x] Inventory reporting works
* [x] Update detection works
* [x] Job retrieval works
* [x] Atomic job claiming works
* [x] Job result reporting works
* [x] Interrupted-job recovery tested
* [x] APT package-manager support
* [x] pacman package-manager support
* [x] Debian tested
* [x] Arch tested
* [x] systemd-logind idle detection
* [ ] Complete external APT/dpkg collision prevention

## Database

* [x] SQLite database isolated from Git
* [x] Integrity check available
* [x] SQLite-aware backup method
* [x] Backup permissions restricted
* [x] Backup integrity verification
* [ ] Full restore test
* [ ] Automated backup verification

## Network

* [x] Nginx reverse proxy
* [x] HTTPS
* [x] HTTP redirect
* [x] Localhost-only application port
* [x] Security headers
* [x] TLS verification for agent communication
* [x] Application ports not intentionally exposed externally
* [ ] Final external network review

## Git

* [x] Production secrets excluded
* [x] Tokens excluded
* [x] TLS private keys excluded
* [x] Database excluded
* [x] Backups excluded
* [x] Documentation uses placeholders
* [x] Changes reviewed before deployment
* [x] Git working tree checked before deployment

---

# 85. Current Security Limitations

## 85.1 Package Manager Coordination

LUMS controls its own package-management operations but cannot automatically prevent arbitrary manually started package-manager processes from running simultaneously.

Further coordination remains a hardening task.

---

## 85.2 Administrative Roles

The current administrative model is intentionally simple.

A full role-based access-control model has not yet been implemented.

---

## 85.3 SQLite Scaling

SQLite is appropriate for the current project scope and laboratory deployment.

Larger environments may eventually require a dedicated database service depending on:

* client count,
* concurrency,
* job volume,
* audit volume,
* availability requirements,
* backup requirements.

---

## 85.4 Restore Validation

SQLite backup creation and integrity verification are implemented.

A complete isolated restore test remains outstanding.

---

## 85.5 Automated Security Testing

Security checks currently exist at multiple manual and operational layers.

A comprehensive automated security regression suite remains future work.

---

# 86. Remaining Security Roadmap

## Phase 1 — Container Hardening

**Status: Complete**

Implemented and verified:

* non-root container,
* UID 10001,
* dropped capabilities,
* non-privileged runtime,
* read-only root filesystem,
* tmpfs `/tmp`,
* persistent database volume,
* protected secret mount,
* localhost-only application binding.

---

## Phase 2 — Secret Isolation and Rotation

**Status: Complete**

Implemented and verified:

* protected host secret,
* read-only secret mount,
* no production secret in normal environment,
* isolated rotation testing,
* production secret replacement,
* old session invalidation,
* new authentication,
* production restart.

---

## Phase 3 — Client Token Lifecycle

**Status: Complete**

Implemented and verified:

* cryptographically secure token generation,
* token hashing,
* Bearer authentication,
* administrative rotation,
* immediate old-token invalidation,
* CSRF protection,
* audit event,
* one-time replacement-token presentation,
* production agent reconfiguration,
* successful production communication.

---

## Phase 4 — Multi-Distribution Package Management

**Status: Complete**

Implemented and tested:

```text
APT
pacman
```

The package-manager abstraction is used by the agent rather than embedding distribution-specific commands throughout the update engine.

Verified:

```text
Debian
Arch Linux
```

---

## Phase 5 — Idle Detection

**Status: Complete**

The previous `w -h` implementation was replaced by systemd-logind-based detection.

Current mechanism:

```text
loginctl
```

The implementation considers relevant interactive user sessions and logind idle state.

---

## Phase 6 — Interrupted Job Recovery

**Status: Complete**

Implemented and tested:

* ownership validation,
* state validation,
* controlled recovery,
* `abandoned` state,
* recovery reason,
* history preservation,
* package-statistic preservation,
* race protection.

---

## Phase 7 — Update Execution Hardening

**Status: In progress**

Remaining work includes:

* stronger APT/dpkg coordination,
* job timeout handling,
* additional package-manager state validation,
* broader execution regression testing,
* additional failure-path testing.

---

## Phase 8 — Backup and Restore

**Status: Partially complete**

Implemented:

* SQLite-aware backup,
* protected backup storage,
* integrity verification.

Remaining:

```text
Full isolated restore test
```

---

## Phase 9 — Automated Security Tests

**Status: Planned**

Potential automated tests:

* authentication,
* authorization,
* token rotation,
* token invalidation,
* CSRF,
* job ownership,
* job claiming,
* recovery,
* security headers,
* container hardening,
* secret handling,
* database integrity.

---

## Phase 10 — Final Security Review

**Status: Planned**

The final review should occur after the remaining hardening phases.

The review should compare:

```text
Documentation
      ↕
Implementation
      ↕
Production
```

The final security state should only be documented as verified after the actual deployment has been tested.

---

# 87. Responsible Security Reporting

Security issues should be reported responsibly.

A useful security report contains:

* short description,
* affected component,
* reproduction steps,
* expected behavior,
* actual behavior,
* potential impact,
* suggested mitigation,
* relevant redacted logs.

Never include:

* passwords,
* client tokens,
* private keys,
* Flask secrets,
* personal information,
* complete production databases,
* unredacted inventory data.

Sensitive information must be removed before logs, screenshots, or configuration files are shared.

---

# 88. Security Maintenance

Security reviews should be performed after:

* application changes,
* authentication changes,
* authorization changes,
* Docker changes,
* Nginx changes,
* certificate changes,
* database schema changes,
* agent changes,
* package-manager changes,
* watcher changes,
* deployment changes,
* secret changes.

Regularly review:

```text
Operating system updates
Docker images
Python dependencies
Flask dependencies
Gunicorn
Nginx
TLS configuration
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
Agent configuration
systemd services
systemd timers
```

---

# 89. Security Change Workflow

Security-sensitive changes should follow a controlled workflow:

```text
Inspect
   ↓
Understand current behavior
   ↓
Design change
   ↓
Implement
   ↓
Test locally
   ↓
Test integration
   ↓
Verify production configuration
   ↓
Deploy
   ↓
Verify production
   ↓
Document
```

A failed test should not be hidden by changing the documentation to match the failure.

The implementation must be corrected or the limitation documented.

---

# 90. Current Security Roadmap Status

The current overall state is:

```text
[x] Non-root container
[x] UID 10001
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
[x] Client authentication
[x] Client token hashing
[x] Client token rotation
[x] Client token invalidation
[x] Token rotation audit logging
[x] CSRF protection for token rotation
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
[x] SQLite integrity verification
[x] SQLite-aware backup
[x] Backup integrity verification

[ ] Complete package-manager collision prevention
[ ] Full backup / restore test
[ ] Automated security regression tests
[ ] Final security review
```

The completed controls should not be interpreted as meaning that LUMS has no remaining security work.

Security hardening is continuous.

---

# 91. Security Verification Principles

LUMS follows several operational rules.

## Rule 1 — Do not trust configuration alone

A configuration file saying:

```text
read-only
```

is not sufficient.

The running container must be inspected.

---

## Rule 2 — Do not trust successful startup alone

A running container does not prove:

* authentication works,
* HTTPS works,
* database integrity is valid,
* clients can authenticate,
* update jobs work.

Each layer must be verified.

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
eventually restored in isolation
```

---

## Rule 4 — Treat exposed secrets as compromised

A secret that was exposed must not be considered safe merely because it is no longer visible.

It must be rotated.

---

## Rule 5 — Authentication does not equal authorization

A valid client token only establishes client identity.

The server must still verify whether that client is authorized for the requested resource.

---

## Rule 6 — Package installation is privileged execution

Update jobs must be treated as privileged operations.

The system must control:

```text
who
what
where
when
result
```

---

## Rule 7 — Documentation follows verification

Documentation should describe the actual tested state.

If something is incomplete, it must be marked as incomplete.

---

# 92. Final Verified Architecture

The current verified security architecture is:

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
              ┌────────────────┐
              │ 127.0.0.1:5050│
              └───────┬────────┘
                      │
                Docker mapping
                      │
                      ▼
        ┌─────────────────────────────┐
        │       LUMS Container        │
        │                             │
        │ User: lums / UID 10001      │
        │ Privileged: false           │
        │ Capabilities: ALL dropped   │
        │ Root FS: read-only          │
        │                             │
        │ /tmp → tmpfs                │
        │ /var/lib/lums → lums-data   │
        │ /run/secrets/lums_secret    │
        │          → read-only        │
        │                             │
        │ Gunicorn                    │
        │      ↓                      │
        │ Flask                       │
        │      ↓                      │
        │ SQLite                      │
        └──────────────┬──────────────┘
                       │
                       │ HTTPS + Bearer Token
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
   Debian 13 Client          Arch Linux Client
          │                         │
     lums-agent 1.6.0         lums-agent 1.6.0
          │                         │
        APT / dpkg                pacman
          │                         │
          └────────────┬────────────┘
                       │
                       ▼
                    Result
                       │
                       ▼
                  LUMS API
```

---

# 93. Final Management / Execution Separation

The final architecture deliberately separates:

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
       └── SQLite

from

Execution Plane
       │
       ├── lums-agent
       ├── systemd
       ├── Package Manager Abstraction
       ├── APT / dpkg
       └── pacman
```

The server manages the desired operation.

The client performs the actual package-management operation.

This separation reduces the need for the server to have direct operating-system privileges on managed clients.

---

# 94. Final Security State

The current LUMS implementation has verified security controls across:

```text
Container
   ↓
Network
   ↓
TLS
   ↓
Authentication
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

The remaining work is explicitly limited to the documented open hardening areas.

The project should not claim a final security review until those remaining areas have been tested.

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
       ├── Job Management
       └── Database

from

Execution Plane
       │
       ├── lums-agent
       ├── systemd
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
> **Secure the management plane. Keep execution controlled.**
> **One change. One test. One verified result.**
