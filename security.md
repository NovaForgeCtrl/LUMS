# LUMS Security

> **Linux Update Management Server**
>
> Security principles, operational requirements, hardening status, and responsible handling of sensitive information in LUMS.

**Version:** 2.5
**Project:** LUMS
**Slogan:** Linux Update Management without the noise.

---

# 1. Security Philosophy

LUMS follows a simple principle:

> **Centralized management does not mean centralized trust.**

LUMS manages Linux clients, receives inventory information, and distributes update jobs.

The actual package installation takes place on the managed Linux client.

```text
                    ┌─────────────────────┐
                    │      LUMS Server     │
                    │                     │
                    │ Nginx               │
                    │ Docker              │
                    │ Gunicorn            │
                    │ Flask               │
                    │ Authentication      │
                    │ Authorization       │
                    │ Inventory           │
                    │ Update Jobs         │
                    └──────────┬──────────┘
                               │
                         HTTPS + Token
                               │
                    ┌──────────▼──────────┐
                    │    Linux Client     │
                    │                     │
                    │ lums-agent          │
                    │ execution watcher   │
                    │ APT / dpkg          │
                    └─────────────────────┘
```

LUMS security depends on multiple layers:

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
APT / dpkg
```

A weakness in one layer must never be used as a reason to disable another security layer.

---

# 2. Security Scope

This document covers:

* Docker deployment security
* Gunicorn application serving
* Database initialization
* Server authentication
* Client authentication
* Authorization
* TLS certificates
* Secret management
* SQLite database protection
* Nginx configuration
* systemd agent services
* Execution watcher security
* Update execution
* Logging
* Backup protection
* Incident handling
* Security testing
* Security maintenance
* Current security limitations
* Remaining hardening work

This document does not replace the official security documentation of:

* Ubuntu
* Debian
* Docker
* Python
* Flask
* Gunicorn
* Nginx
* SQLite
* APT
* dpkg
* systemd

---

# 3. Current Architecture

The current LUMS deployment uses:

* Flask inside a Docker container
* Gunicorn as the WSGI application server
* SQLite in a persistent Docker volume
* Nginx as an HTTPS reverse proxy
* A Linux reporting agent
* A separate execution watcher
* Bearer-token authentication
* systemd timers for scheduled execution
* A root-managed mounted Flask secret

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
Docker container :5000
   │
   ▼
Gunicorn
   │
   ├── Worker 1
   └── Worker 2
   │
   ▼
Flask application
   │
   ├── Authentication
   ├── Authorization
   ├── Inventory
   └── Update Jobs
   │
   ▼
SQLite database
```

The Docker application is bound to localhost:

```text
127.0.0.1:5050 → container port 5000
```

The application is not directly exposed as a network service on ports `5000` or `5050`.

The Flask secret is no longer supplied through the normal container environment.

Instead, production uses:

```text
Host:
    /etc/lums/secrets/lums_secret

        │ read-only bind mount

Container:
    /run/secrets/lums_secret
```

The application reads the secret through:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

---

# 4. Current Deployment Security Status

The following controls have been implemented and tested:

| Security control                                         | Status   |
| -------------------------------------------------------- | -------- |
| Non-root Docker container                                | Verified |
| Drop all Linux capabilities                              | Verified |
| Read-only root filesystem                                | Verified |
| Writable application data only through persistent volume | Verified |
| `/tmp` isolated through tmpfs                            | Verified |
| Secret isolation                                         | Verified |
| Protected mounted Flask secret                           | Verified |
| Secret mount read-only                                   | Verified |
| Production Flask secret rotation                         | Verified |
| Gunicorn deployment                                      | Verified |
| HTTPS reverse proxy                                      | Verified |
| Security headers                                         | Verified |
| Client authentication                                    | Verified |
| Client token lifecycle                                   | Verified |
| Client token rotation                                    | Verified |
| Interrupted-job recovery                                 | Verified |
| SQLite-aware backup                                      | Verified |
| Backup integrity verification                            | Verified |
| Production frontend deployment                           | Verified |
| Frontend token rotation workflow                         | Verified |

Remaining hardening:

```text
Update execution hardening
Full backup / restore test
Automated security tests
Final security review
```

---

# 5. Docker Security

The LUMS application runs as a dedicated non-root user.

The container user is:

```text
lums
UID 10001
```

The Docker image must not run as root.

Verify:

```bash
sudo docker inspect lums \
    --format 'User={{.Config.User}}'
```

Expected:

```text
User=lums
```

The application data directory is:

```text
/var/lib/lums
```

The persistent Docker volume is:

```text
lums-data
```

---

# 6. Linux Capability Hardening

The LUMS application does not require Linux capabilities.

Production therefore uses:

```bash
--cap-drop=ALL
```

Verify:

```bash
sudo docker inspect lums \
    --format 'CapDrop={{json .HostConfig.CapDrop}}'
```

Expected:

```text
CapDrop=["ALL"]
```

The container must also not be privileged:

```bash
sudo docker inspect lums \
    --format 'Privileged={{.HostConfig.Privileged}}'
```

Expected:

```text
Privileged=false
```

The application continues to function without additional Linux capabilities.

---

# 7. Read-Only Root Filesystem

The production container uses:

```bash
--read-only
```

The root filesystem is therefore not writable.

Writable state is deliberately limited to:

```text
/var/lib/lums
/tmp
```

The `/tmp` directory is provided through:

```bash
--tmpfs /tmp:rw,nosuid,nodev,noexec
```

The persistent database remains on:

```text
lums-data:/var/lib/lums
```

Verify:

```bash
sudo docker inspect lums \
    --format 'ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}'
```

Expected:

```text
ReadonlyRootfs=true
```

---

# 8. Secret Management

The Flask secret is security-sensitive.

The secret must never be:

* committed to Git,
* documented in plaintext,
* printed to logs,
* included in screenshots,
* included in bug reports,
* passed through normal container environment variables in production.

Production uses:

```text
/etc/lums/secrets/lums_secret
```

The host secret directory is protected.

Expected:

```text
/etc/lums/secrets
    root:root
    0700
```

The secret file is:

```text
root:10001
0640
```

The container receives it through a read-only mount:

```text
/etc/lums/secrets/lums_secret
        ↓
/run/secrets/lums_secret
```

The application is configured through:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

The normal environment variable:

```text
LUMS_SECRET_KEY
```

must not contain the production secret.

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

Verify the file:

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

# 9. Secret Rotation

Secret isolation and secret rotation are separate controls.

The production Flask secret was previously exposed through diagnostic output.

The value is intentionally not reproduced.

The replacement procedure was:

```text
Identify exposure
        ↓
Move secret outside normal environment
        ↓
Test rotation in isolation
        ↓
Generate replacement secret
        ↓
Replace protected secret file
        ↓
Restart LUMS
        ↓
Verify old sessions invalidated
        ↓
Verify new authentication
        ↓
Remove temporary old-secret backup
```

Production secret rotation was successfully completed.

The previous secret is no longer active.

A Flask secret change invalidates existing sessions.

This behavior was explicitly tested before production rotation.

---

# 10. Authentication

LUMS uses administrator authentication for the web interface.

Passwords are protected using Argon2.

Client authentication uses Bearer tokens.

Example:

```text
Authorization: Bearer <CLIENT_TOKEN>
```

The server hashes the supplied token before comparing it against the stored client token hash.

Client tokens are generated cryptographically.

The current token generation uses:

```python
secrets.token_urlsafe(32)
```

The token is never intentionally stored in plaintext.

---

# 11. Client Authentication

Client authentication is performed server-side.

The authentication flow is:

```text
Client
   │
   │ Authorization: Bearer <token>
   ▼
LUMS API
   │
   ▼
Hash supplied token
   │
   ▼
Lookup client token hash
   │
   ▼
Check enabled
   │
   ▼
Check token revocation state
   │
   ▼
Authenticated client
```

Protected endpoints use the authenticated client identity.

The client ID supplied by a request must not override the identity established by authentication.

---

# 12. Client Token Lifecycle

Client tokens are treated as credentials.

The current lifecycle includes:

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
Invalidate old token
   ↓
Issue replacement
   ↓
Update agent
   ↓
Verify communication
```

The plaintext token is returned only during token creation or rotation.

The token is not written to the audit log.

---

# 13. Client Token Rotation

Administrative token rotation is implemented through:

```text
POST /api/clients/<client_id>/token/rotate
```

The endpoint requires:

```text
Administrator session
+
CSRF validation
```

The endpoint:

1. Finds the client.
2. Generates a new cryptographically random token.
3. Hashes the token.
4. Replaces the stored token hash.
5. Updates `token_created_at`.
6. Clears the previous revocation timestamp.
7. Creates an audit event.
8. Returns the new token once.

The previous token becomes invalid immediately.

---

# 14. Client Token Rotation Authorization

The rotation endpoint rejects:

```text
No administrator session
```

with:

```text
401
```

A missing or invalid CSRF token is rejected with:

```text
400
```

An unknown client returns:

```text
404
```

Only a valid administrator session with valid CSRF protection can rotate a client token.

---

# 15. Client Token Audit Logging

Successful token rotation produces an audit event:

```text
action:
    client.token.rotate

target:
    client:<CLIENT_ID>

result:
    success
```

The audit record may contain non-sensitive client information such as:

```text
hostname=<HOSTNAME>
```

The actual token is never stored in the audit event.

The audit log therefore records:

```text
that a rotation happened
```

rather than:

```text
what the new token was
```

---

# 16. Frontend Token Rotation

The client detail page provides:

```text
🔐 Token rotieren
```

Before rotation, the administrator receives a confirmation dialog.

The warning explains:

* the previous token becomes invalid,
* the LUMS agent must be updated,
* the operation continues only after confirmation.

After successful rotation:

```text
Neuer Client-Token
```

is displayed.

The interface explicitly warns:

> Dieser Token wird nur jetzt angezeigt.

The token can be copied using:

```text
📋 Token kopieren
```

The token is not stored in the page as persistent application state.

---

# 17. Token Rotation Testing

The token rotation lifecycle was tested in an isolated environment.

Verified:

```text
Token A
   ↓
authenticated
   ↓
Rotate
   ↓
Token B
```

Then:

```text
Token A → 401
Token B → 200
```

The test also verified:

```text
No admin session
    → 401

Admin session without CSRF
    → 400

Unknown client
    → 404
```

The audit event was created successfully.

The token value was not written to the audit log.

The frontend was tested for:

```text
Rotation confirmation
Token display
Copy-to-clipboard
Successful rotation
```

---

# 18. Production Token Verification

After the token lifecycle was tested, the production agent was updated with the replacement client token.

The production agent subsequently reported successfully:

```text
✓ REPORT ACCEPTED
✓ CLIENT AUTHENTICATED
✓ NO UPDATE JOB
LUMS // Agent cycle complete.
status=0/SUCCESS
```

The client appeared online again in the LUMS interface.

This confirms:

```text
Token rotation
      ↓
Agent reconfiguration
      ↓
Authentication
      ↓
Inventory reporting
```

---

# 19. Authorization

Authentication answers:

```text
Who are you?
```

Authorization answers:

```text
What are you allowed to access?
```

LUMS validates authenticated client ownership for client-specific job operations.

A client cannot simply provide another client ID and access that client's job.

Protected job operations verify the relationship between:

```text
Authenticated client
        +
Requested job
        +
Owning client
```

---

# 20. Job Claiming

Job claiming is performed atomically.

This prevents multiple agents from claiming the same job under normal concurrent execution.

The claim operation uses a conditional state transition.

Conceptually:

```text
pending
   ↓
running
```

Only the client that successfully claims the job can continue execution.

---

# 21. Job Result Authorization

Job result reporting validates that the authenticated client owns the job.

A client must not be able to submit a result for another client's job.

The server therefore checks:

```text
authenticated_client.id
        ==
job.client_id
```

before accepting the result.

---

# 22. Interrupted Job Recovery

An update job can become stuck in:

```text
running
```

if the agent terminates unexpectedly.

LUMS provides controlled recovery.

The recovery endpoint is:

```text
POST /api/update-jobs/<job_id>/abandon
```

The operation:

* verifies the job exists,
* verifies client ownership,
* only permits recovery from `running`,
* marks the job `abandoned`,
* records `finished_at`,
* records a recovery reason,
* writes update history,
* preserves package statistics,
* prevents accidental new job execution when recovery fails.

---

# 23. Recovery Reason

Recovered jobs use:

```text
Agent did not submit a final result.
```

This distinguishes:

```text
success
failed
abandoned
```

rather than incorrectly representing an interrupted job as successful.

---

# 24. Recovery Race Protection

Recovery uses a conditional state transition.

If another operation has already changed the job state, the recovery operation returns a conflict rather than overwriting the newer state.

Conceptually:

```text
running
   │
   ├── agent result
   │
   └── recovery
```

Only one valid transition should win.

---

# 25. Recovery Testing

A controlled artificial job was created.

The agent encountered the `running` job and initiated recovery.

Verified:

```text
status:
    abandoned

finished_at:
    populated

recovery_reason:
    Agent did not submit a final result.

update_history:
    abandoned

package count:
    preserved

successful:
    0

failed:
    0
```

The artificial test data was removed afterwards.

A real update job was subsequently executed successfully.

This confirmed that recovery did not break normal job execution.

---

# 26. Agent Security

The LUMS agent communicates with the server through HTTPS.

The agent configuration includes:

```text
LUMS_BASE
LUMS_TOKEN
LUMS_CA
```

The agent uses the configured CA for TLS verification.

TLS verification must not be disabled merely to work around certificate problems.

The agent token must be protected as a credential.

---

# 27. Agent Configuration

The agent configuration is stored outside the Git repository.

Example:

```text
/etc/default/lums-agent
```

Sensitive values must not be committed.

Permissions should restrict unauthorized access.

The agent should run under its intended system account and only receive the permissions required for its functions.

---

# 28. Execution Watcher

The execution watcher is separate from normal inventory reporting.

The separation provides:

```text
Reporting
    ≠
Execution supervision
```

The watcher is responsible for detecting and handling execution state.

It must not bypass:

* authentication,
* authorization,
* job ownership,
* execution state,
* audit requirements.

---

# 29. APT / dpkg Security

Package installation is performed on the client.

The client uses:

```text
APT
dpkg
```

Package management is privileged and therefore represents a security-sensitive execution boundary.

LUMS must avoid uncontrolled concurrent package operations.

The current execution lock reduces collisions within LUMS-controlled operations.

However, complete collision prevention against arbitrary manually started package-manager processes is not yet fully implemented.

This remains a hardening task.

---

# 30. Update Execution Principles

Update execution should:

* run only authorized jobs,
* validate package information,
* preserve job ownership,
* record execution results,
* handle failures explicitly,
* detect interrupted jobs,
* avoid unnecessary reboot operations,
* maintain an auditable history.

The agent must never treat an invalid or unauthenticated job as executable.

---

# 31. Reboot Handling

A reboot should only occur when the update operation explicitly indicates that it is required.

LUMS should not automatically reboot a client merely because packages were installed.

The job result must distinguish:

```text
reboot required
```

from:

```text
reboot not required
```

---

# 32. Nginx Security

Nginx is the external HTTPS entry point.

The application itself is not directly exposed.

Expected architecture:

```text
Internet / LAN
      │
      ▼
    Nginx
   :443 HTTPS
      │
      ▼
127.0.0.1:5050
      │
      ▼
Docker :5000
```

Nginx should only proxy to the local application binding.

---

# 33. HTTP Redirect

HTTP is redirected to HTTPS.

Expected:

```text
HTTP :80
   ↓
301
   ↓
HTTPS :443
```

Test:

```bash
curl -I http://127.0.0.1/
```

or against the server's configured HTTP address.

The redirect prevents normal browser access from remaining on plaintext HTTP.

---

# 34. HTTPS Security Headers

The application currently provides security headers including:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy:
    camera=(),
    microphone=(),
    geolocation=(),
    payment=()
```

The Content Security Policy includes:

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

These headers should remain present after deployment changes.

---

# 35. TLS

TLS should support:

```text
TLS 1.2
TLS 1.3
```

Older protocols must remain disabled.

TLS certificates must contain the correct Subject Alternative Name.

Private key permissions must be restricted.

Test:

```bash
sudo nginx -t
```

Then:

```bash
curl -k -I https://127.0.0.1/
```

---

# 36. Docker Network Exposure

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

The service is not directly reachable through the host's LAN interface.

Do not replace it with:

```text
0.0.0.0:5050:5000
```

unless the network architecture is intentionally redesigned and protected by an appropriate firewall or proxy layer.

---

# 37. Port Security

Expected external services:

```text
22/tcp
80/tcp
443/tcp
```

Application ports:

```text
5000
5050
```

must remain internal.

Check:

```bash
sudo ss -lntp
```

Expected application binding:

```text
127.0.0.1:5050
```

---

# 38. Database Security

LUMS uses SQLite.

The database is stored in:

```text
/var/lib/lums/lums.db
```

The directory is backed by:

```text
lums-data
```

The database must not be stored inside the Git repository.

The database must not be deleted as a troubleshooting shortcut.

---

# 39. Database Integrity

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

---

# 40. Database Backup

SQLite backups must use a SQLite-aware backup method.

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

The temporary backup can then be moved into:

```text
/var/backups/lums/
```

and protected:

```bash
sudo chown root:root /var/backups/lums/lums.db.backup
sudo chmod 600 /var/backups/lums/lums.db.backup
```

---

# 41. Backup Verification

A backup is not considered valid merely because the file exists.

Verify:

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

---

# 42. Production Backup Before Frontend Deployment

Before the current frontend production deployment, a SQLite-aware backup was created:

```text
/var/backups/lums/lums.db.backup-token-rotation
```

The backup was verified:

```text
integrity = ok
users = 1
clients = 1
audit_log = 22
update_jobs = 1
update_history = 1
```

The backup was protected as:

```text
root:root
0600
```

This backup provides a rollback point for the frontend deployment.

---

# 43. Restore

A full restore procedure must be tested separately in an isolated environment.

The intended restore flow is:

```text
Verified backup
      ↓
Isolated LUMS environment
      ↓
Restore SQLite database
      ↓
Integrity check
      ↓
Application startup
      ↓
Authentication test
      ↓
Client test
      ↓
Job data verification
```

A full restore test remains outstanding.

---

# 44. Git Security

Never commit:

```text
Passwords
API tokens
Client tokens
TLS private keys
Environment files
Database files
SQLite backups
Session secrets
Personal data
```

Review:

```bash
git status
git diff
git diff --check
```

Before committing.

The configured project identity is:

```text
Name:
    xxxxx

Email:
    xxxxx
```

---

# 45. Docker Image Security

The production image should be built from reviewed source.

Before deployment:

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

Verify:

```text
User=lums
```

The running container must use the tested image.

A successful image build alone does not prove that the application is secure or functional.

---

# 46. Production Container

Current production deployment:

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

This configuration provides:

```text
Non-root
+
No Linux capabilities
+
Read-only root filesystem
+
Read-only secret mount
+
Persistent database volume
+
Localhost-only application binding
```

---

# 47. Container Restart Verification

After production deployment:

```bash
sudo docker restart lums
```

Then verify:

```bash
sudo docker ps \
    --filter "name=^lums$"
```

Logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

The expected startup sequence includes:

```text
LUMS database initialization
Starting Gunicorn
Starting gunicorn 23.0.0
Listening at 0.0.0.0:5000
Booting worker
```

No crash loop should occur.

---

# 48. Browser Security

The browser stores the selected LUMS frontend theme locally.

Theme selection is presentation-only.

The theme value:

```text
lums-theme
```

does not affect:

* authentication,
* authorization,
* database state,
* update jobs,
* agent communication,
* client permissions.

The browser must not be treated as a trusted authorization source.

---

# 49. Logging

Logs may contain:

* HTTP requests
* application errors
* job identifiers
* client identifiers
* operational information

Logs must not contain:

* passwords
* client tokens
* Flask secrets
* TLS private keys

When sharing logs, sensitive values must be removed.

---

# 50. Firewall Security

Only required services should be exposed.

Typical allowed ports:

```text
22/tcp    SSH
80/tcp    HTTP redirect
443/tcp   HTTPS
```

Check:

```bash
sudo ufw status verbose
```

Application ports must not be publicly exposed:

```text
5000
5050
```

Firewall rules must be reviewed after network or deployment changes.

---

# 51. Deployment Security

Before deployment:

```bash
cd /opt/lums-public

git status --short
git fetch origin
git log --oneline --decorate -3
```

Update:

```bash
git pull --ff-only origin main
```

Review:

```bash
git diff --check
```

Build:

```bash
sudo docker build -t lums:latest .
```

Before recreation:

```bash
sudo docker ps
sudo docker volume inspect lums-data
```

Create a verified SQLite backup before replacing a production container.

The current production deployment uses:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --tmpfs /tmp:rw,nosuid,nodev,noexec \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
```

Stop and remove only the container:

```bash
sudo docker stop lums
sudo docker rm lums
```

Do not remove:

```text
lums-data
```

Verify:

```bash
sudo docker ps
sudo docker logs --tail 100 lums
sudo nginx -t
```

Test HTTPS:

```bash
curl -k -I https://127.0.0.1/
```

A successful Docker build does not prove that the complete deployment is working.

---

# 52. Deployment Verification

After container recreation verify:

```text
1. Container running
2. Correct image
3. Correct localhost binding
4. Persistent volume still mounted
5. Database initialization runs once
6. Gunicorn starts
7. Two workers start
8. HTTPS returns expected response
9. Security headers remain present
10. Login remains accessible
11. Client reporting remains functional
12. Update jobs remain functional
13. Container runs as non-root
14. Root filesystem is read-only
15. All Linux capabilities are dropped
16. /tmp is available through tmpfs
17. Secret path is configured
18. Secret is not present as LUMS_SECRET_KEY
19. Secret mount is read-only
20. Container restart succeeds
```

Check:

```bash
sudo docker ps \
    --filter "name=^lums$" \
    --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"
```

Check volume:

```bash
sudo docker inspect lums \
    --format '{{range .Mounts}}{{.Name}} -> {{.Destination}} ({{.RW}}){{"\n"}}{{end}}'
```

Expected database volume:

```text
lums-data -> /var/lib/lums (true)
```

Check the secret mount:

```bash
sudo docker inspect lums \
    --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} RW={{.RW}}{{"\n"}}{{end}}'
```

Expected:

```text
/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
```

---

# 53. Incident Handling

## 53.1 Compromised Client Token

If a client token is compromised:

1. Identify the affected client.
2. Revoke or replace the token.
3. Review recent client activity.
4. Check server and application logs.
5. Issue a new token.
6. Update client configuration.
7. Verify authentication.
8. Document the incident.

Never continue using a known-compromised token.

---

## 53.2 Compromised Server Secret

If the server secret is compromised:

1. Restrict access to the server.
2. Review application logs.
3. Generate a new secret.
4. Replace the protected secret file.
5. Restart the Docker container.
6. Verify authentication and sessions.
7. Review related credentials.
8. Document the incident.

Changing the Flask secret may invalidate existing sessions.

The production secret should be rotated separately from normal secret-isolation deployment when possible so that session impact is understood and tested.

---

## 53.3 Compromised TLS Private Key

If the TLS private key is compromised:

1. Replace the certificate and private key.
2. Update trusted certificates on clients.
3. Reload Nginx.
4. Verify certificate validation.
5. Review possible unauthorized access.
6. Document the incident.

---

## 53.4 Exposed Database or Backup

If a database or backup becomes exposed:

1. Restrict access immediately.
2. Determine which information was exposed.
3. Review authentication-related data.
4. Rotate affected credentials or tokens.
5. Replace compromised backups if necessary.
6. Review access logs.
7. Document the incident.

---

## 53.5 Previously Exposed Flask Secret

The Flask secret was previously exposed through diagnostic output.

The value is intentionally not reproduced here.

The incident was handled by:

```text
Identify exposure
        ↓
Move secret out of normal Docker environment
        ↓
Test secret rotation in isolation
        ↓
Generate replacement secret
        ↓
Replace /etc/lums/secrets/lums_secret
        ↓
Restart production LUMS
        ↓
Verify old session invalidation
        ↓
Verify new authentication
        ↓
Remove temporary old-secret backup
```

The replacement secret is now active in production.

> **The previously exposed Flask secret has been rotated and is no longer the active production secret.**

---

# 54. Security Testing Checklist

## Server

* [x] Docker container is running
* [x] Docker volume is mounted
* [x] Application binds only to localhost
* [x] Port `5000` is not externally exposed
* [x] Port `5050` is not externally exposed
* [x] Nginx configuration passes validation
* [x] HTTPS is enabled
* [x] HTTP redirects to HTTPS
* [x] TLS certificate contains the correct SAN
* [x] Private key permissions are restricted
* [x] Environment file permissions are restricted
* [x] Firewall rules reviewed as required

## Application Server

* [x] Flask development server removed
* [x] Gunicorn 23.0.0 deployed
* [x] Gunicorn workers start successfully
* [x] Application import works
* [x] Database initialization runs before Gunicorn
* [x] Database initialization runs once per container start
* [x] Gunicorn receives container signals correctly

## Authentication

* [x] Administrator authentication works
* [x] Invalid credentials are rejected
* [x] Client token authentication is implemented
* [x] Invalid client tokens are rejected
* [x] Client tokens are not intentionally logged
* [x] Protected endpoints require authentication
* [x] Token rotation lifecycle implemented and verified
* [x] Flask secret rotation completed and verified

## Authorization

* [x] Client identity is authenticated server-side
* [x] Client/job relationships are validated
* [x] Atomic job claiming is implemented
* [x] Job result ownership is validated
* [x] Recovery ownership is validated
* [ ] Full administrative role model implemented

## Agent

* [x] Agent uses HTTPS
* [x] TLS verification is configured
* [x] CA certificate is available
* [x] Agent configuration is protected
* [x] Reporting timer is configured
* [x] Watcher timer is configured
* [x] Inventory reporting works
* [x] Update job retrieval works
* [x] Atomic job claiming works
* [x] Job result reporting works
* [x] Interrupted-job recovery tested
* [ ] Complete APT/dpkg collision prevention

## Database

* [x] Database integrity can be checked
* [x] SQLite-aware backups are implemented
* [x] Backups are protected
* [x] Backup integrity verification tested
* [x] Restore procedure is documented
* [ ] Full restore test completed
* [x] Database files are excluded from Git
* [x] Backup files are excluded from Git

## Docker

* [x] Container is not privileged
* [x] Application ports are localhost-only
* [x] Persistent volume is used
* [x] Container runs as non-root user
* [x] Root filesystem is read-only
* [x] All Linux capabilities are dropped
* [x] Secret is removed from normal container environment
* [x] Secret is supplied through protected mounted file
* [x] Secret mount is read-only
* [x] Production restart with secret-file architecture verified

## Git

* [x] Secrets excluded from documentation
* [x] Private keys excluded
* [x] Tokens excluded
* [x] Database files excluded
* [x] Backup files excluded
* [x] Changes reviewed before deployment
* [x] Documentation uses placeholders
* [x] Historical Flask secret exposure identified
* [x] Replacement Flask secret generated and deployed

---

# 55. Current Security Limitations

## 55.1 Secret Rotation

Secret isolation and production secret rotation are complete and verified.

The previous secret was treated as exposed, replaced with a newly generated value, and the production application was restarted and tested.

Changing the Flask secret invalidates existing sessions. This behavior was explicitly tested before production rotation and confirmed again after production deployment.

---

## 55.2 Client Token Lifecycle

Client token rotation is implemented and verified.

Current lifecycle controls include:

* Cryptographically random token generation.
* SHA-256 hexadecimal digest storage.
* Bearer authentication.
* Enabled/revoked checks.
* Administrative rotation.
* Immediate invalidation of the previous token.
* CSRF protection for the administrative rotation endpoint.
* Audit logging without the plaintext token.
* One-time presentation of the replacement token.
* Production client communication after rotation.

Token expiration and a more advanced token-storage model remain possible future enhancements, but token rotation itself is no longer a pending hardening task.

---

## 55.3 Idle Detection

The current idle detection uses:

```text
w -h
```

It is primarily suitable for server, terminal, console, and SSH-oriented environments.

It is not a universal desktop idle detection mechanism.

---

## 55.4 Package Manager Coordination

Complete collision prevention between LUMS and arbitrary user-issued APT or dpkg commands is not fully implemented.

The LUMS execution lock does not automatically force every external package manager process to honor it.

---

## 55.5 Administrative Roles

LUMS currently has a single administrator-oriented authentication model.

A full role-based administrative authorization model has not yet been implemented.

---

## 55.6 SQLite Scaling

SQLite is suitable for the current project scope and laboratory development.

Larger deployments may require a different database architecture depending on:

* Number of clients
* Concurrent requests
* Job volume
* Audit log size
* Backup requirements
* High availability requirements

---

## 55.7 Self-Signed Certificates

Self-signed certificates require explicit trust configuration on clients.

They can be suitable for controlled laboratory environments but may not be appropriate for every deployment scenario.

---

# 56. Remaining Security Roadmap

The remaining hardening work should be performed incrementally.

## Phase 1 — Secret Isolation and Rotation — Complete

The Flask secret is stored outside the normal Docker environment and mounted read-only into the container.

The previously exposed secret was replaced with a newly generated production secret.

Verified:

* Isolated rotation test.
* Old session invalidation.
* New authentication.
* Production restart.
* HTTPS operation.
* Database integrity.
* Client communication.

The secret value itself must never be documented.

---

## Phase 2 — Client Token Lifecycle — Complete

Implemented and verified:

* Cryptographically random token generation.
* SHA-256 digest storage.
* Administrative token rotation.
* Immediate invalidation of the previous token.
* CSRF protection.
* Audit event without token disclosure.
* One-time token presentation.
* Agent reconfiguration and production reporting verification.

Possible future enhancements:

* Token expiration.
* Token identifiers.
* More advanced token storage appropriate to a larger deployment threat model.

---

## Phase 3 — Update Execution Hardening

Continue improving:

* APT/dpkg collision prevention
* Job timeouts
* Recovery handling
* Execution auditing
* Package-manager state detection
* Integration testing

---

## Phase 4 — Backup / Restore Validation

Perform an isolated restore test using a verified production backup.

Test:

```text
Backup
  ↓
Isolated restore environment
  ↓
SQLite integrity
  ↓
Security schema
  ↓
Application startup
  ↓
Authentication
  ↓
Client/job data
```

Only after a successful restore test should the backup/restore control be considered fully validated.

---

## Phase 5 — Automated Security Tests

Automate regression tests for:

* Authentication
* Authorization
* Token handling
* Job ownership
* Job claiming
* Job recovery
* Security headers
* Container hardening
* Database integrity
* Secret handling

---

## Phase 6 — Final Security Review

After the individual hardening phases are complete:

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

The final review should confirm that the documented security state matches the actual deployment.

---

# 57. Responsible Security Reporting

Security issues should be reported responsibly.

A security report should contain:

* Short description
* Affected component
* Reproduction steps
* Expected behavior
* Actual behavior
* Potential impact
* Suggested mitigation
* Relevant logs with secrets removed

Never include:

* Passwords
* Client tokens
* Private keys
* Server secrets
* Personal information
* Complete production databases
* Unredacted inventory data

Always redact sensitive information before sharing logs or screenshots.

---

# 58. Security Maintenance

Security reviews should be performed after:

* Application changes
* Authentication changes
* Authorization changes
* Docker changes
* Nginx changes
* Certificate changes
* Database schema changes
* Agent changes
* Watcher changes
* Deployment changes
* Secret changes

Regularly review:

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
Authentication behavior
Authorization behavior
Job execution behavior
Package manager coordination
Container privileges
Container capabilities
Secret handling
Secret rotation
```

---

# 59. Current Security Roadmap Status

The current hardening state is:

```text
[x] Non-root container
[x] Drop ALL capabilities
[x] Read-only root filesystem
[x] SQLite backup verification
[x] Interrupted-job recovery
[x] Production restart verification
[x] Secret isolation
[x] Protected mounted secret file
[x] Read-only secret mount
[x] Production restart after secret isolation
[x] Flask secret rotation
[x] Production secret rotation verification
[x] Client token lifecycle
[x] Client token rotation
[x] Client token revocation through rotation
[x] Client token rotation audit event
[x] Frontend token rotation workflow
[x] Production frontend deployment
[x] Production client communication after token rotation

[ ] Update execution hardening
[ ] Full backup / restore test
[ ] Automated security tests
[ ] Final security review
```

The following controls are therefore considered complete for the current implementation:

```text
Container hardening
Secret isolation
Secret rotation
Client authentication
Client token rotation
Interrupted-job recovery
Production frontend deployment
```

The remaining work is intentionally separated into independent hardening phases:

```text
Update execution hardening
        ↓
Full backup / restore test
        ↓
Automated security tests
        ↓
Final security review
```

The established workflow remains:

```text
inspect
   ↓
design
   ↓
test
   ↓
verify
   ↓
production
   ↓
verify
   ↓
document
```

No security-sensitive change should be deployed blindly.

---

# 60. Final Security Principles

The following principles apply to LUMS:

1. Never store secrets in Git.
2. Never expose the Flask/Gunicorn application directly to the network.
3. Use HTTPS for client communication.
4. Keep TLS verification enabled.
5. Separate authentication from authorization.
6. Validate client identity server-side.
7. Protect the Docker environment file.
8. Protect client tokens.
9. Protect TLS private keys.
10. Protect the mounted Flask secret.
11. Keep database backups secure.
12. Do not remove persistent volumes during troubleshooting.
13. Do not automatically reboot clients.
14. Review changes before deployment.
15. Test security-sensitive changes.
16. Document incidents and configuration changes.
17. Do not claim that incomplete security controls are fully implemented.
18. Keep update execution controlled and auditable.
19. Harden the container incrementally and test each change independently.
20. Preserve persistent application data during frontend and container deployments.
21. Treat secret isolation and secret rotation as separate controls.
22. Treat previously exposed secrets as compromised until rotated.
23. Rotate client tokens through the authenticated administrative workflow and verify the replacement token before closing the change.
24. Keep production secrets outside Git and outside normal container environment variables where practical.
25. Treat security hardening as a continuous process rather than a one-time configuration.

---

# 61. Final Verified Production State

The production deployment was rebuilt from the tested frontend image after a verified SQLite backup.

The final production checks confirmed:

```text
Image:
    lums:latest

Container user:
    lums / UID 10001

ReadonlyRootfs:
    true

Capabilities:
    ALL dropped

Privileged:
    false

Secret environment variable:
    LUMS_SECRET_KEY absent

Secret path:
    /run/secrets/lums_secret

Secret mount:
    read-only

Database integrity:
    ok

HTTPS:
    302 → /login

Unauthenticated client API:
    401 authentication_required

Frontend token rotation control:
    visible in production
```

The production database remained intact:

```text
users:          1
clients:        1
audit_log:      22
update_jobs:    1
update_history: 1
```

The backup used before the production frontend deployment was independently checked with SQLite integrity verification and returned:

```text
integrity = ok
```

The token-rotation workflow was tested separately before production deployment, including old-token invalidation, new-token authentication, CSRF enforcement, audit logging, and frontend presentation/copy behavior.

> **Client Token Lifecycle: VERIFIED**

> **Production Secret Rotation: VERIFIED**

> **Container Hardening: VERIFIED**

---

# 62. Final Principle

LUMS is designed to centralize Linux update management without removing operational control from the administrator.

The system should remain:

* Transparent
* Auditable
* Controlled
* Secure
* Documented
* Maintainable

The current architecture deliberately separates:

```text
Management Plane
       │
       ├── Nginx
       ├── Gunicorn
       ├── Flask
       ├── Authentication
       ├── Authorization
       └── Database

from

Execution Plane
       │
       ├── lums-agent
       ├── Execution Watcher
       └── APT / dpkg
```

Security improvements are implemented one controlled layer at a time.

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
 Docker
 ┌──────────────────────────────┐
 │ non-root                     │
 │ UID 10001                    │
 │ capabilities: NONE           │
 │ root filesystem: READ-ONLY   │
 │                              │
 │ /tmp → tmpfs                 │
 │ /var/lib/lums → lums-data    │
 │ /run/secrets/lums_secret     │
 │          → READ-ONLY         │
 │                              │
 │ Gunicorn → Flask             │
 └──────────────────────────────┘
      │
      ▼
 SQLite
```

The hardening workflow remains:

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
