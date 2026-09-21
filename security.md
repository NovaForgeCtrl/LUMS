# LUMS Security

> **Linux Update Management Server**
>
> Security principles, operational requirements, hardening status, and responsible handling of sensitive information in LUMS.

**Version:** 2.3
**Project:** LUMS
**Slogan:** Linux Update Management without the noise.

---

## 1. Security Philosophy

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
* Container hardening

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
   ▼
SQLite database
```

The Docker application is bound to localhost:

```text
127.0.0.1:5050 → container port 5000
```

The application is not directly exposed as a network service on ports `5000` or `5050`.

---

# 4. Current Deployment Security Status

The following controls have been implemented and verified:

| Security control                                 | Status                                               |
| ------------------------------------------------ | ---------------------------------------------------- |
| HTTPS through Nginx                              | Implemented and tested                               |
| HTTP → HTTPS redirect                            | Tested                                               |
| TLS 1.2 / TLS 1.3                                | Configured and tested                                |
| Security headers                                 | Implemented and tested                               |
| Localhost Docker binding                         | Implemented                                          |
| Flask development server removed                 | Completed                                            |
| Gunicorn 23.0.0                                  | Implemented                                          |
| Two Gunicorn workers                             | Implemented                                          |
| Database initialization before Gunicorn          | Implemented                                          |
| Database initialization once per container start | Tested                                               |
| Bearer client authentication                     | Implemented                                          |
| Client/job authorization                         | Implemented                                          |
| Atomic job claiming                              | Implemented                                          |
| Interrupted-job recovery                         | Implemented and tested                               |
| SQLite-aware backups                             | Implemented                                          |
| Backup integrity verification                    | Tested                                               |
| Persistent Docker volume                         | Implemented                                          |
| Container non-privileged mode                    | Confirmed                                            |
| Container non-root user                          | **Implemented and production verified**              |
| Read-only container filesystem                   | **Implemented and production verified**              |
| Linux capabilities                               | **ALL capabilities dropped and production verified** |
| Docker environment secret isolation              | **Open hardening item**                              |
| Client token lifecycle/rotation                  | **Future hardening**                                 |
| Complete APT/dpkg collision prevention           | **Not yet implemented**                              |
| Automated security regression tests              | **Future hardening**                                 |
| Restore test                                     | **Not yet completed**                                |

The security status is intentionally documented as incomplete where controls have not yet been implemented.

---

# 5. Current Production Container Security

The production container currently runs with the following security properties:

```text
Container:
    lums

Image:
    lums:latest

User:
    uid=10001(lums)
    gid=10001(lums)

Privileged:
    false

Root filesystem:
    read-only

Capabilities:
    ALL dropped

Persistent writable location:
    /var/lib/lums

Temporary writable location:
    /tmp

External application binding:
    127.0.0.1:5050

Internal application port:
    5000
```

The effective container configuration includes:

```text
--read-only
--cap-drop=ALL
--tmpfs /tmp:rw,nosuid,nodev,noexec
-v lums-data:/var/lib/lums
```

The persistent database remains outside the read-only container root filesystem:

```text
lums-data:/var/lib/lums
```

---

# 6. Production Hardening Verification

The current production configuration has been explicitly verified after a container restart.

Expected security configuration:

```text
ReadonlyRootfs=true
CapDrop=["ALL"]
Privileged=false
```

The application user is:

```text
uid=10001(lums)
gid=10001(lums)
```

Effective Linux capabilities are:

```text
CapInh: 0000000000000000
CapPrm: 0000000000000000
CapEff: 0000000000000000
CapBnd: 0000000000000000
CapAmb: 0000000000000000
```

The container successfully survives a restart with these restrictions enabled.

The following were verified after restart:

```text
SQLite integrity: ok
users: present
clients: present
audit_log: present
schema_migrations: present
Users: 1
Clients: 1
Update jobs: 1
HTTPS status: 302
```

The application continues to return the expected HTTPS security headers.

> **Security Point 1 — Non-root container: VERIFIED**
>
> **Security Point 2 — Drop ALL capabilities: VERIFIED**
>
> **Security Point 3 — Read-only root filesystem: VERIFIED**

---

# 7. Current Installation

| Component                 | Configuration                 |
| ------------------------- | ----------------------------- |
| Repository                | `/opt/lums-public`            |
| Docker container          | `lums`                        |
| Docker image              | `lums:latest`                 |
| Docker volume             | `lums-data`                   |
| Internal application port | `5000`                        |
| Host binding              | `127.0.0.1:5050`              |
| HTTP port                 | `80`                          |
| HTTPS port                | `443`                         |
| Database                  | `/var/lib/lums/lums.db`       |
| Server environment file   | `/etc/lums/docker/lums.env`   |
| Server certificate        | `/etc/lums/tls/lums.crt`      |
| Server private key        | `/etc/lums/tls/lums.key`      |
| Agent directory           | `/opt/lums-agent`             |
| Agent configuration       | `/etc/default/lums-agent`     |
| Agent CA certificate      | `/opt/lums-agent/lums-ca.crt` |
| Reporting agent           | `/opt/lums-agent/agent.py`    |
| Execution watcher         | `/opt/lums-agent/watcher.py`  |

Actual secrets, tokens, passwords, private keys, internal credentials, and sensitive infrastructure information must never be published.

---

# 8. Sensitive Information

The following information must be treated as sensitive:

```text
LUMS server secret
Client tokens
Authentication hashes
Administrator passwords
TLS private keys
Session information
Database contents
Inventory information
Internal infrastructure information
Backup files
Application configuration
```

Important sensitive files include:

```text
/etc/lums/docker/lums.env
/etc/lums/tls/lums.key
/etc/default/lums-agent
```

The Docker volume contains the operational database:

```text
lums-data:/var/lib/lums
```

> [!CAUTION]
>
> Never commit sensitive files or their contents to Git.

Sensitive information must also be removed from:

* Screenshots
* Terminal output
* GitHub issues
* Pull requests
* Public documentation
* Chat messages
* Support requests
* Log exports

---

# 9. Server Secret Management

## 9.1 Environment File

The server environment file is stored outside the Git repository:

```text
/etc/lums/docker/lums.env
```

It is loaded when the Docker container is created:

```bash
sudo docker run \
    --env-file /etc/lums/docker/lums.env \
    ...
```

Protect the file:

```bash
sudo chown root:root /etc/lums/docker/lums.env
sudo chmod 600 /etc/lums/docker/lums.env
```

Check permissions without displaying contents:

```bash
sudo stat -c '%U:%G %a %n' \
    /etc/lums/docker/lums.env
```

Check whether the secret exists:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' \
    /etc/lums/docker/lums.env \
    && echo "Secret configured" \
    || echo "Secret missing"
```

Never print the complete environment file.

---

# 10. Docker Environment Secret Exposure

The current deployment passes `LUMS_SECRET_KEY` through the Docker environment.

The source file itself is protected:

```text
/etc/lums/docker/lums.env
root:root
0600
```

However, environment variables configured on a container can be visible through Docker inspection to users with sufficient Docker privileges.

Therefore:

> **A protected host environment file does not mean that the secret is invisible to Docker administrators.**

This remains an open hardening item.

Potential future approaches include:

* Docker secrets
* Protected mounted secret files
* External secret management
* Reducing the number of users with Docker administration privileges

The secret must never be printed during normal diagnostics.

---

# 11. Client Authentication

LUMS clients authenticate using Bearer tokens.

The request must contain:

```http
Authorization: Bearer <CLIENT_TOKEN>
```

The server validates the presented token before processing protected requests.

The current implementation stores a SHA-256 hexadecimal digest of the client token rather than the plaintext token.

```text
Client Token
     │
     ▼
SHA-256
     │
     ▼
Hexadecimal Digest
     │
     ▼
Database
```

SHA-256 is a deterministic digest and is not a password-hashing algorithm.

The current design should therefore be treated as a token-verification mechanism rather than password storage.

Future token hardening may include:

* Token identifiers
* Token rotation
* Token expiration
* Token revocation
* Reduced token exposure
* A storage design appropriate to the threat model
* Token audit events

Any change must be implemented consistently across server and clients and must be regression-tested.

---

# 12. Client Token Protection

Client configuration is stored in:

```text
/etc/default/lums-agent
```

Example:

```dotenv
LUMS_BASE="https://<LUMS_SERVER_IP>"
LUMS_TOKEN="<CLIENT_TOKEN>"
LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt"
```

The real token must never appear in:

* Git commits
* README files
* Documentation
* Screenshots
* Public issue reports
* Log files
* Chat messages

Use placeholders:

```text
<LUMS_SERVER_IP>
<CLIENT_IP>
<CLIENT_TOKEN>
<CLIENT_ID>
<JOB_ID>
<ADMIN_PASSWORD>
```

Protect the configuration:

```bash
sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

---

# 13. Authorization

Authentication and authorization are separate concepts.

```text
Authentication
    ↓
Who is this client?

Authorization
    ↓
What is this client allowed to access?
```

A valid client token must not automatically grant access to every client or job.

The server validates:

* Authenticated client identity
* Requested client ID
* Job ownership
* Job assignment
* Result submission permissions
* Recovery permissions
* Administrative permissions where applicable

Authorization is enforced server-side.

Frontend restrictions and hidden form fields are not security controls.

---

# 14. Protected API Endpoints

Protected client operations include:

```text
POST /api/report

GET /api/client/me

GET /api/clients/<client_id>/update-jobs

GET /api/clients/<client_id>/update-jobs/pending

GET /api/clients/<client_id>/update-jobs/running

POST /api/clients/<client_id>/update-jobs/<job_id>/claim

GET /api/update-jobs/<job_id>

POST /api/update-jobs/<job_id>/result

POST /api/update-jobs/<job_id>/abandon
```

The server must verify that the authenticated client is authorized to access the requested resource.

A client must not be able to:

* Read another client's inventory
* Retrieve another client's jobs
* Claim another client's job
* Submit results for another client
* Abandon another client's job
* Modify unauthorized job states

---

# 15. Client Identity

Client-specific operations should use authenticated identity wherever possible.

The endpoint:

```http
GET /api/client/me
```

provides authenticated client context.

The server must not rely solely on client-supplied identifiers.

Do not trust:

* Client IDs from request bodies
* URL parameters
* Hidden form fields
* Frontend restrictions
* User-controlled metadata

The server must validate:

```text
Authenticated client
        +
Requested resource
        =
Authorized access
```

---

# 16. TLS

LUMS uses HTTPS for communication between clients and the server.

Server certificate:

```text
/etc/lums/tls/lums.crt
```

Server private key:

```text
/etc/lums/tls/lums.key
```

Recommended permissions:

```bash
sudo chown root:root /etc/lums/tls/lums.key
sudo chmod 600 /etc/lums/tls/lums.key

sudo chown root:root /etc/lums/tls/lums.crt
sudo chmod 644 /etc/lums/tls/lums.crt
```

The private key must never be:

* Committed to Git
* Copied into the repository
* Printed in terminal output
* Included in public documentation
* Shared through public issue reports

---

# 17. TLS Configuration

The current Nginx configuration permits:

```text
TLS 1.2
TLS 1.3
```

Older protocol versions remain disabled.

Check:

```bash
sudo nginx -T | grep -n "ssl_protocols"
```

TLS must be tested after certificate or Nginx changes.

Example:

```bash
curl -k -I https://127.0.0.1/
```

The `-k` option is only appropriate for controlled diagnostics when certificate verification is intentionally bypassed.

Normal client operation must verify the configured CA.

---

# 18. Nginx Security Headers

The current deployment provides:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
Content-Security-Policy: ...
```

The current CSP includes restrictions for:

```text
default-src
script-src
style-src
img-src
font-src
connect-src
object-src
base-uri
frame-ancestors
form-action
```

Current production verification returns the expected security headers.

Check:

```bash
curl -k -I https://127.0.0.1/
```

HSTS may be added only after HTTPS deployment has been fully validated for the intended environment.

---

# 19. Network Exposure

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
```

Check Docker mappings:

```bash
sudo docker port lums
```

Check listening ports:

```bash
sudo ss -lntp
```

Expected application binding:

```text
127.0.0.1:5050
```

The following must not be directly exposed to the network:

```text
5000
5050
```

---

# 20. Gunicorn Application Server

The Flask development server is no longer used by the Docker deployment.

LUMS currently uses:

```text
Gunicorn 23.0.0
```

The container starts Gunicorn with:

```text
2 workers
2 threads per worker
120 second timeout
stdout access logging
stdout error logging
```

The application is loaded using:

```text
app:app
```

The effective architecture is:

```text
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker :5000
   ↓
Gunicorn
   ├── Worker 1
   └── Worker 2
   ↓
Flask
```

The Flask development server is not used for the current deployment.

---

# 21. Database Initialization

Database initialization and application serving are intentionally separated.

The Docker startup sequence is:

```text
Container start
      │
      ▼
init_db.py
      │
      │ successful
      ▼
Gunicorn
      │
      ├── Worker 1
      └── Worker 2
```

The database initialization script is:

```text
/app/server/init_db.py
```

The container entrypoint is:

```text
/app/docker-entrypoint.sh
```

The entrypoint executes:

```text
python3 /app/server/init_db.py
```

before starting Gunicorn.

This prevents database initialization from occurring once per Gunicorn worker.

The production logs have been verified to show database initialization once per container startup.

---

# 22. Entrypoint Failure Behavior

The Docker entrypoint uses:

```sh
set -eu
```

and:

```sh
exec gunicorn ...
```

Therefore:

* Database initialization failure prevents Gunicorn startup.
* Gunicorn becomes the container's main process.
* Docker receives Gunicorn's process signals directly.
* The application does not continue after a failed initialization step.

---

# 23. Docker Security

The LUMS application runs inside:

```text
lums
```

The production container is intentionally hardened.

Current runtime properties:

```text
Non-root user
Read-only root filesystem
ALL Linux capabilities dropped
Non-privileged container
Persistent database volume
Writable /tmp tmpfs
Localhost-only host binding
```

The production deployment uses:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --tmpfs /tmp:rw,nosuid,nodev,noexec \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
```

The persistent volume must not be removed during normal frontend or application deployment.

> [!CAUTION]
>
> Removing `lums-data` can permanently delete the LUMS database and operational state.

Never execute:

```bash
sudo docker volume rm lums-data
```

without a verified backup and explicit approval.

---

# 24. Non-Root Container

The production container runs as:

```text
uid=10001(lums)
gid=10001(lums)
```

The container does not run the LUMS application as root.

The persistent database directory is writable by the LUMS runtime user:

```text
/var/lib/lums
```

The non-root configuration was tested using:

* Container startup
* Gunicorn startup
* Login endpoint
* SQLite write/read operations
* Database integrity checks
* Container restart
* Production deployment verification

> **Status: VERIFIED**

---

# 25. Linux Capability Hardening

The production container explicitly drops all Linux capabilities:

```text
--cap-drop=ALL
```

Verified runtime state:

```text
CapInh: 0000000000000000
CapPrm: 0000000000000000
CapEff: 0000000000000000
CapBnd: 0000000000000000
CapAmb: 0000000000000000
```

The application successfully performs its required operations without Linux capabilities.

No capability has been added back.

> **Status: VERIFIED**

---

# 26. Read-Only Root Filesystem

The production container uses:

```text
--read-only
```

Only explicitly required writable locations are provided.

Persistent application data:

```text
/var/lib/lums
```

Temporary runtime storage:

```text
/tmp
```

The temporary filesystem is configured as:

```text
--tmpfs /tmp:rw,nosuid,nodev,noexec
```

The following behavior was tested:

* Container startup
* Gunicorn startup
* SQLite operations
* Database integrity
* Application login
* Container restart
* Security configuration persistence
* HTTPS access

The container successfully restarted with the read-only root filesystem enabled.

> **Status: VERIFIED**

---

# 27. Agent Security

The reporting agent and execution watcher perform different tasks.

### Reporting agent

Responsible for:

* Collecting system information
* Detecting installed packages
* Detecting available updates
* Reporting client information
* Communicating with the LUMS server

### Execution watcher

Responsible for:

* Checking pending jobs
* Checking idle status
* Claiming jobs
* Executing configured update operations
* Recovering interrupted jobs
* Submitting execution results

The separation of responsibilities makes the execution workflow easier to review and troubleshoot.

---

# 28. Agent Configuration Protection

The agent configuration is:

```text
/etc/default/lums-agent
```

Protect:

```bash
sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

Check:

```bash
sudo stat -c '%U:%G %a %n' \
    /etc/default/lums-agent
```

Expected:

```text
root:root 600 /etc/default/lums-agent
```

Display configuration without exposing the token:

```bash
sudo awk -F= '
/^LUMS_BASE=/ {
    print $1 "=" $2
}
/^LUMS_CA_FILE=/ {
    print $1 "=" $2
}
/^LUMS_TOKEN=/ {
    print "LUMS_TOKEN=<redacted>"
}
' /etc/default/lums-agent
```

---

# 29. Execution Watcher Security

The execution watcher must:

1. Load the protected configuration.
2. Contact the LUMS server using HTTPS.
3. Authenticate using the client token.
4. Check whether a pending job exists.
5. Check idle status.
6. Verify the configured idle threshold.
7. Attempt an atomic job claim.
8. Execute only a successfully claimed job.
9. Submit a validated result.
10. Recover interrupted jobs safely.

The watcher must not execute a job merely because it appears in a pending list.

---

# 30. Idle-Aware Execution

The current watcher uses:

```text
w -h
```

for idle detection.

This is primarily suitable for:

* Server environments
* Terminal sessions
* Console sessions
* SSH-oriented environments

It is not a universal desktop idle detection mechanism.

The current configured threshold is:

```text
300 seconds
```

The watcher should only execute jobs when:

* Idle detection is supported.
* The idle threshold has been reached.
* A pending job exists.
* The job is assigned to the authenticated client.
* The job is successfully claimed.
* The package manager is available.

---

# 31. Atomic Job Claiming

Job claiming is performed atomically.

Expected workflow:

```text
1. Find pending job
2. Verify client identity
3. Verify job authorization
4. Check idle state
5. Attempt atomic claim
6. Confirm claim success
7. Execute the job
8. Submit the result
```

If another watcher claims the job first, the current watcher must not execute it.

This prevents duplicate execution caused by:

* Repeated timer runs
* Concurrent requests
* Network retries
* Multiple watcher instances

---

# 32. Interrupted Job Recovery

A job may remain in `running` if:

* The client loses power
* The watcher is terminated
* The system reboots
* The network connection fails
* The package manager process crashes
* Result submission fails

LUMS provides an explicit recovery mechanism:

```http
POST /api/update-jobs/<job_id>/abandon
```

The endpoint:

* Requires client authentication.
* Verifies job ownership.
* Only operates on a `running` job.
* Changes the job state to `abandoned`.
* Records a recovery reason.
* Records the recovery in update history.
* Preserves package-count and execution metadata.
* Uses a conditional state update to avoid races.

The watcher detects an interrupted running job and attempts recovery before claiming a new job.

If recovery fails, the watcher must not continue by claiming another job.

---

# 33. Recovery Testing

Recovery has been tested using a controlled synthetic job.

The test verified:

```text
running
   ↓
abandoned
```

and confirmed:

* `finished_at` populated
* Recovery reason recorded
* Update history entry created
* Package count preserved
* Successful count preserved
* Failed count preserved
* No unintended reboot flag
* Synthetic test data removed afterward

A subsequent real update job was also successfully executed after the recovery test.

> **Status: VERIFIED**

---

# 34. APT and dpkg Safety

Complete APT and dpkg collision prevention is not fully implemented.

The LUMS execution lock does not automatically force arbitrary user-issued APT or dpkg commands to honor it.

A potential collision remains possible:

```text
LUMS watcher starts an operation
        +
User manually runs apt or dpkg
        =
Potential package manager collision
```

LUMS must not claim that all package manager collisions are prevented.

Future improvements may include:

* Detecting active APT or dpkg processes
* Deferring jobs while package management is busy
* Stronger execution coordination
* Better lock handling
* Job timeout handling
* Additional audit events
* Integration tests

---

# 35. Database Security

LUMS uses SQLite inside:

```text
lums-data
```

Database path:

```text
/var/lib/lums/lums.db
```

The database may contain:

* Client records
* Authentication hashes
* Inventory information
* Installed packages
* Available updates
* Update jobs
* Job results
* Audit information

Database access must be restricted to:

* The LUMS application
* Authorized administrators
* Controlled maintenance procedures

The database must never be committed to Git.

---

# 36. Database Integrity

Check:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

connection = sqlite3.connect("/var/lib/lums/lums.db")
result = connection.execute(
    "PRAGMA integrity_check;"
).fetchone()[0]

print(result)
connection.close()
'
```

Expected:

```text
ok
```

Do not modify the database manually without:

1. A verified backup.
2. A clear reason.
3. An understanding of the schema.
4. A controlled maintenance procedure.
5. Validation after the change.

---

# 37. SQLite-Aware Backup

The production backup procedure uses a root helper container because the backup destination is protected:

```bash
sudo docker run --rm \
    --user 0:0 \
    --entrypoint python3 \
    -v lums-data:/var/lib/lums:ro \
    -v /var/backups/lums:/backup \
    lums:latest \
    -c '
import sqlite3

source = sqlite3.connect("/var/lib/lums/lums.db")
target = sqlite3.connect("/backup/lums.db.backup-readonly")

with target:
    source.backup(target)

target.close()
source.close()

print("SQLite backup completed")
'
```

Protect:

```bash
sudo chmod 600 \
    /var/backups/lums/lums.db.backup-readonly
```

Recommended permissions:

```text
Backup directory: 0700
Backup file:      0600
Owner:            root:root
```

---

# 38. Current Backup Verification

The current production backup was successfully created and verified.

Backup:

```text
/var/backups/lums/lums.db.backup-readonly
```

Verified properties:

```text
Owner:       root:root
Permissions: 0600
SQLite integrity: ok
```

The backup size at the time of verification was approximately:

```text
136 KiB
```

The backup is therefore currently considered a valid SQLite backup.

> **Backup creation and integrity verification: VERIFIED**

This does not yet constitute a full restore test.

---

# 39. Database Restore

A database restore is a controlled maintenance operation.

Before restoring:

1. Confirm the correct backup.
2. Stop the LUMS container.
3. Create a safety copy of the current database.
4. Restore the backup.
5. Check ownership and permissions.
6. Start the container.
7. Run a database integrity check.
8. Test authentication.
9. Test client reporting.
10. Verify update jobs and audit data.

Never overwrite the only available database copy.

Do not restore a database while the application is actively writing to it.

> **Restore test: NOT YET COMPLETED**

---

# 40. Git Repository Security

Repository:

```text
/opt/lums-public
```

Before committing:

```bash
cd /opt/lums-public

git status
git diff
git diff --check
```

Check tracked files:

```bash
git ls-files
```

Never commit:

```text
.env files
Environment files
Private keys
Client tokens
Passwords
Database files
Backup files
Session data
Internal credentials
Personal information
```

Use placeholders:

```text
<LUMS_SERVER_IP>
<CLIENT_IP>
<CLIENT_TOKEN>
<ADMIN_PASSWORD>
<JOB_ID>
```

---

# 41. Logging Security

LUMS server logs:

```bash
sudo docker logs --tail 100 lums
```

Follow:

```bash
sudo docker logs -f lums
```

Agent logs:

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

Nginx logs:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Logs must not contain:

* Plaintext tokens
* Passwords
* Server secrets
* Private keys
* Session secrets
* Complete authorization headers
* Unnecessary sensitive inventory information

Redact sensitive information before sharing logs.

---

# 42. Filesystem Permissions

Review:

```bash
sudo stat -c '%U:%G %a %n' \
    /etc/lums/docker/lums.env \
    /etc/lums/tls/lums.key \
    /etc/default/lums-agent
```

Recommended:

```text
Environment files:       0600
Private keys:            0600
Public certificates:     0644
Agent configuration:     0600
Backup directory:        0700
Backup database files:   0600
```

Review permissions after:

* Installation
* Updates
* Manual changes
* File transfers
* Restores
* Deployment operations

---

# 43. Firewall Security

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

# 44. Deployment Security

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

Create and verify a SQLite backup before replacing a production container.

Stop and remove only the container:

```bash
sudo docker stop lums
sudo docker rm lums
```

Do not remove:

```text
lums-data
```

Start the hardened container:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --tmpfs /tmp:rw,nosuid,nodev,noexec \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
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

# 45. Deployment Verification

After container recreation verify:

```text
1. Container running
2. Correct image
3. Correct localhost binding
4. Persistent volume still mounted
5. Read-only root filesystem active
6. ALL capabilities dropped
7. Container runs as non-root
8. Database initialization runs once
9. Gunicorn starts
10. Two workers start
11. HTTPS returns expected response
12. Security headers remain present
13. Login remains accessible
14. Database integrity is valid
15. Client reporting remains functional
16. Update jobs remain functional
```

Check:

```bash
sudo docker ps \
    --filter "name=^lums$" \
    --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"
```

Check hardening:

```bash
sudo docker inspect lums \
    --format '
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
CapAdd={{json .HostConfig.CapAdd}}
CapDrop={{json .HostConfig.CapDrop}}
Privileged={{.HostConfig.Privileged}}
'
```

Check runtime identity:

```bash
sudo docker exec lums id
```

Check capabilities:

```bash
sudo docker exec lums \
    sh -c 'grep "^Cap" /proc/1/status'
```

---

# 46. Incident Handling

## 46.1 Compromised Client Token

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

## 46.2 Compromised Server Secret

If the server secret is compromised:

1. Restrict access to the server.
2. Review application logs.
3. Rotate the secret.
4. Restart the Docker container.
5. Verify authentication and sessions.
6. Review related credentials.
7. Document the incident.

Changing the Flask secret may invalidate existing sessions.

---

## 46.3 Compromised TLS Private Key

If the TLS private key is compromised:

1. Replace the certificate and private key.
2. Update trusted certificates on clients.
3. Reload Nginx.
4. Verify certificate validation.
5. Review possible unauthorized access.
6. Document the incident.

---

## 46.4 Exposed Database or Backup

If a database or backup becomes exposed:

1. Restrict access immediately.
2. Determine which information was exposed.
3. Review authentication-related data.
4. Rotate affected credentials or tokens.
5. Replace compromised backups if necessary.
6. Review access logs.
7. Document the incident.

---

# 47. Security Testing Checklist

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
* [ ] Firewall rules require periodic review

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
* [ ] Token rotation lifecycle fully implemented
* [ ] Server secret rotation completed

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
* [x] Production backup created and verified
* [x] Backup permissions are restricted
* [x] Backup verification is documented
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
* [x] ALL Linux capabilities are dropped
* [ ] Secret removed from normal container environment where practical

## Git

* [x] Secrets excluded from documentation
* [x] Private keys excluded
* [x] Tokens excluded
* [x] Database files excluded
* [x] Backup files excluded
* [x] Changes reviewed before deployment
* [x] Documentation uses placeholders
* [ ] Historical secret exposure review where applicable

---

# 48. Current Security Limitations

## 48.1 Docker Environment Secret

`LUMS_SECRET_KEY` is currently supplied through the Docker environment.

The host environment file is protected with `0600`, but Docker-level inspection can expose configured environment variables to sufficiently privileged users.

A stronger secret-delivery mechanism remains a future hardening task.

---

## 48.2 Server Secret Rotation

The server secret requires lifecycle management.

A future hardening step should address:

* Secret rotation
* Session impact
* Controlled deployment
* Verification after rotation
* Incident handling

A secret rotation must not be performed blindly because changing the Flask secret may invalidate existing sessions.

---

## 48.3 Token Lifecycle

The current client token architecture works but does not yet provide a complete lifecycle management model.

Future work includes:

* Token rotation
* Expiration
* Revocation workflows
* Token audit events
* Improved storage strategy

---

## 48.4 Idle Detection

The current idle detection uses:

```text
w -h
```

It is primarily suitable for server, terminal, console, and SSH-oriented environments.

It is not a universal desktop idle detection mechanism.

---

## 48.5 Package Manager Coordination

Complete collision prevention between LUMS and arbitrary user-issued APT or dpkg commands is not fully implemented.

The LUMS execution lock does not automatically force every external package manager process to honor it.

---

## 48.6 Token Hashing

The current implementation uses a SHA-256 hexadecimal digest for client token verification.

This format should be reviewed as the authentication architecture evolves.

---

## 48.7 Self-Signed Certificates

Self-signed certificates require explicit trust configuration on clients.

They can be suitable for controlled laboratory environments but may not be appropriate for every deployment scenario.

---

## 48.8 SQLite Scaling

SQLite is suitable for the current project scope and laboratory development.

Larger deployments may require a different database architecture depending on:

* Number of clients
* Concurrent requests
* Job volume
* Audit log size
* Backup requirements
* High availability requirements

---

# 49. Remaining Security Roadmap

Security hardening is performed incrementally.

Current status:

```text
[x] Non-root container
[x] Drop ALL capabilities
[x] Read-only root filesystem
[x] Production restart verification
[x] SQLite backup creation
[x] SQLite backup integrity verification

[ ] Secret isolation
[ ] Server secret rotation
[ ] Client token lifecycle
[ ] Update execution hardening
[ ] Automated security tests
[ ] Full backup restore test
[ ] Final security review
```

The workflow remains:

```text
inspect
    ↓
test
    ↓
verify
    ↓
production
    ↓
restart
    ↓
verify again
```

No security hardening change should be considered complete merely because the Docker build succeeds.

---

# 50. Responsible Security Reporting

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

# 51. Security Maintenance

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
```

---

# 52. Final Security Principles

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
10. Keep database backups secure.
11. Do not remove persistent volumes during troubleshooting.
12. Do not automatically reboot clients.
13. Review changes before deployment.
14. Test security-sensitive changes.
15. Document incidents and configuration changes.
16. Do not claim that incomplete security controls are fully implemented.
17. Keep update execution controlled and auditable.
18. Harden the container incrementally and test each change independently.
19. Preserve persistent application data during frontend and container deployments.
20. Treat security hardening as a continuous process rather than a one-time configuration.
21. Verify production hardening after container restarts.
22. Keep recovery paths auditable and ownership-controlled.
23. Verify backups before relying on them for recovery.

---

# 53. Final Principle

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

> **LUMS — Linux Update Management without the noise.**

> **Secure the management plane. Keep execution controlled.**

> **One change. One test. One verified result.**
