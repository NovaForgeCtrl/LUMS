# LUMS Security

> **Linux Update Management Server**
>
> Security principles, operational requirements, and responsible handling of sensitive information in LUMS.

**Version:** 2.1
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
                    │ Docker              │
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

## 2. Security Scope

This document covers:

* Docker deployment security
* Server authentication
* Client authentication
* Authorization
* TLS certificates
* Secret management
* SQLite database protection
* Nginx configuration
* systemd agent services
* Execution watcher security
* Git repository security
* Update execution
* Logging
* Backup protection
* Incident handling
* Security maintenance

This document does not replace the official security documentation of:

* Ubuntu
* Debian
* Docker
* Python
* Flask
* Nginx
* SQLite
* APT
* dpkg
* systemd

---

## 3. Current Architecture

The current LUMS deployment uses:

* Flask inside a Docker container
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
   ▼
Docker container :5000
   │
   ▼
SQLite database
```

The Docker application must be bound to localhost:

```text
127.0.0.1:5050 → Docker container port 5000
```

The Flask application must not be directly exposed to the network.

---

## 4. Current Installation

| Component               | Configuration                 |
| ----------------------- | ----------------------------- |
| Repository              | `/opt/lums-public`            |
| Docker container        | `lums`                        |
| Docker image            | `lums:latest`                 |
| Docker volume           | `lums-data`                   |
| Internal Flask port     | `5000`                        |
| Host binding            | `127.0.0.1:5050`              |
| HTTP port               | `80`                          |
| HTTPS port              | `443`                         |
| Database                | `/var/lib/lums/lums.db`       |
| Server environment file | `/etc/lums/docker/lums.env`   |
| Server certificate      | `/etc/lums/tls/lums.crt`      |
| Server private key      | `/etc/lums/tls/lums.key`      |
| Agent directory         | `/opt/lums-agent`             |
| Agent configuration     | `/etc/default/lums-agent`     |
| Agent CA certificate    | `/opt/lums-agent/lums-ca.crt` |
| Reporting agent         | `/opt/lums-agent/agent.py`    |
| Execution watcher       | `/opt/lums-agent/watcher.py`  |

The configuration values in this document are examples. Actual secrets, tokens, passwords, and internal addresses must never be published.

---

## 5. Sensitive Information

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

## 6. Secret Management

### 6.1 Server Environment File

The server environment file is stored outside the Git repository:

```text
/etc/lums/docker/lums.env
```

The file is loaded by Docker:

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

Check permissions without displaying the contents:

```bash
sudo stat -c '%U:%G %a %n' \
    /etc/lums/docker/lums.env
```

Check whether the server secret exists:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' \
    /etc/lums/docker/lums.env \
    && echo "Secret configured" \
    || echo "Secret missing"
```

Never print the complete environment file in logs, screenshots, or documentation.

---

### 6.2 Client Token

The client configuration is stored in:

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

---

## 7. Client Authentication

LUMS clients authenticate using Bearer tokens.

The request must contain:

```http
Authorization: Bearer <CLIENT_TOKEN>
```

The server must validate the token before processing protected requests.

The current implementation stores a SHA-256 hexadecimal digest of the client token instead of the plaintext token.

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

The token hashing format must remain consistent between:

* Token creation
* Token storage
* Token verification
* Token rotation
* Client registration

Do not replace the expected hash format with another format unless the application implementation is updated and tested accordingly.

### Security note

SHA-256 is a deterministic digest and is not a password-hashing algorithm.

For future security improvements, consider a design based on:

* Token hashing with a suitable keyed or password-hashing approach
* Token identifiers
* Token rotation
* Token expiration
* Token revocation
* Reduced token exposure

Any change must be implemented consistently across the server and clients.

---

## 8. Authorization

Authentication and authorization are separate concepts.

```text
Authentication
    ↓
Who is this client?

Authorization
    ↓
What is this client allowed to access?
```

A valid token must not automatically grant access to every client or job.

The server must validate:

* Authenticated client identity
* Requested client ID
* Job ownership
* Job assignment
* Administrative permissions
* Result submission permissions

Example:

```text
Client A
   │
   └── Requests Client B data
            │
            ▼
          DENIED
```

Authorization must be enforced server-side.

Frontend restrictions and hidden form fields are not security controls.

---

## 9. Client Identity

Client-specific operations should use the authenticated identity wherever possible.

The following endpoint may be used to retrieve the authenticated client context:

```http
GET /api/client/me
```

The server must not rely solely on client-supplied identifiers.

Do not trust:

* Client IDs from request bodies
* URL parameters
* Hidden form fields
* Frontend restrictions
* User-controlled metadata

The server must validate the relationship between:

```text
Authenticated client
        +
Requested resource
        =
Authorized access
```

---

## 10. Protected API Endpoints

The following endpoints require consistent authentication and authorization:

```text
POST /api/report

GET /api/clients/<client_id>/update-jobs

GET /api/clients/<client_id>/update-jobs/pending

GET /api/clients/<client_id>/update-jobs/running

POST /api/clients/<client_id>/update-jobs/<job_id>/claim

GET /api/update-jobs/<job_id>

POST /api/update-jobs/<job_id>/result
```

The server must verify that the authenticated client is authorized to access the requested resource.

A client must not be able to:

* Read another client's inventory
* Retrieve another client's jobs
* Claim another client's job
* Submit results for another client
* Modify unauthorized job states

---

## 11. TLS

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
* Included in backups intended for public distribution
* Printed in terminal output
* Shared through public issue reports

---

## 12. Certificate Subject Alternative Name

The certificate must contain the hostname or IP address used by the clients.

Inspect the certificate:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

Inspect the Subject Alternative Name:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -ext subjectAltName
```

The client connection address must match a valid SAN entry.

A certificate containing only a Common Name is not sufficient for modern hostname verification.

---

## 13. Certificate Verification

Certificate verification must remain enabled during normal operation.

Do not permanently solve TLS problems by:

* Disabling certificate verification
* Ignoring certificate errors
* Using unencrypted HTTP
* Removing the CA configuration
* Using insecure client settings

Diagnostic example:

```bash
curl -k https://<LUMS_SERVER_IP>/
```

The `-k` option disables certificate verification and must not be used in normal automation.

Normal operation should use the configured CA certificate:

```bash
curl \
    --cacert /opt/lums-agent/lums-ca.crt \
    https://<LUMS_SERVER_IP>/
```

The client configuration must contain:

```dotenv
LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt"
```

---

## 14. Nginx Security

Nginx is the public-facing reverse proxy.

Responsibilities:

* TLS termination
* HTTP-to-HTTPS redirection
* Forwarding requests to Docker
* Preventing direct external access to Flask
* Providing the external HTTPS endpoint

Validate the configuration:

```bash
sudo nginx -t
```

Reload Nginx only after a successful configuration test:

```bash
sudo systemctl reload nginx
```

Check the service:

```bash
sudo systemctl status nginx --no-pager
```

Check the Nginx logs:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

The reverse proxy target should be local:

```text
http://127.0.0.1:5050
```

---

## 15. Network Exposure

The intended network architecture is:

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

Check Docker port mappings:

```bash
sudo docker port lums
```

Check listening ports:

```bash
sudo ss -lntp
```

The application should bind to:

```text
127.0.0.1:5050
```

Avoid exposing the application using:

```text
0.0.0.0:5000
0.0.0.0:5050
```

unless the security architecture is deliberately redesigned and reviewed.

---

## 16. HTTP and HTTPS

Normal communication must use HTTPS:

```text
https://<LUMS_SERVER_IP>
```

Test the HTTP redirect:

```bash
curl -I http://<LUMS_SERVER_IP>/
```

Test HTTPS:

```bash
curl \
    --cacert /opt/lums-agent/lums-ca.crt \
    -I \
    https://<LUMS_SERVER_IP>/
```

HTTP should redirect to HTTPS.

Sensitive information must never be transmitted through unencrypted HTTP.

---

## 17. Docker Security

The LUMS application runs inside the Docker container:

```text
lums
```

Check the container:

```bash
sudo docker ps --filter name=lums
```

Inspect the container:

```bash
sudo docker inspect lums
```

View the logs:

```bash
sudo docker logs --tail 100 lums
```

Follow the logs:

```bash
sudo docker logs -f lums
```

The container must use a persistent volume:

```text
lums-data
```

The volume contains operational application data.

> [!CAUTION]
>
> Removing `lums-data` can permanently delete the LUMS database and operational state.

Never execute the following command without a verified backup and explicit approval:

```bash
sudo docker volume rm lums-data
```

---

## 18. Docker Environment Protection

The server environment file is:

```text
/etc/lums/docker/lums.env
```

The file must remain outside the Git repository:

```text
/opt/lums-public
```

Recommended permissions:

```text
Owner: root
Group: root
Mode: 0600
```

Apply the permissions:

```bash
sudo chown root:root /etc/lums/docker/lums.env
sudo chmod 600 /etc/lums/docker/lums.env
```

Do not copy the environment file into:

* The Git repository
* Public documentation directories
* Web server document roots
* Unprotected temporary directories

---

## 19. Agent Security

The reporting agent and execution watcher perform different tasks.

### Reporting agent

The reporting agent is responsible for:

* Collecting system information
* Detecting installed packages
* Detecting available updates
* Reporting client information
* Communicating with the LUMS server

### Execution watcher

The execution watcher is responsible for:

* Checking pending jobs
* Checking idle status
* Claiming jobs
* Executing configured update operations
* Recovering interrupted jobs
* Submitting execution results

The separation of responsibilities makes the execution workflow easier to review and troubleshoot.

---

## 20. Agent Configuration Protection

The agent configuration is:

```text
/etc/default/lums-agent
```

Protect the file:

```bash
sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

Check the permissions:

```bash
sudo stat -c '%U:%G %a %n' \
    /etc/default/lums-agent
```

Expected permissions:

```text
root:root 600 /etc/default/lums-agent
```

Display configuration values without exposing the token:

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

## 21. Agent Files

The agent files are stored in:

```text
/opt/lums-agent/
```

Expected files:

```text
/opt/lums-agent/agent.py
/opt/lums-agent/watcher.py
/opt/lums-agent/lums-ca.crt
```

Recommended ownership:

```bash
sudo chown root:root \
    /opt/lums-agent/agent.py \
    /opt/lums-agent/watcher.py \
    /opt/lums-agent/lums-ca.crt
```

Recommended permissions:

```bash
sudo chmod 750 \
    /opt/lums-agent/agent.py \
    /opt/lums-agent/watcher.py

sudo chmod 644 \
    /opt/lums-agent/lums-ca.crt
```

The agent configuration containing the token must remain separate from the application source files.

---

## 22. systemd Reporting Service

The reporting service is:

```text
lums-agent.service
```

The reporting timer is:

```text
lums-agent.timer
```

The service uses `Type=oneshot`.

Execution flow:

```text
Timer
  ↓
Service
  ↓
Agent
  ↓
Report submission
  ↓
Exit
```

A successful oneshot service may show:

```text
inactive (dead)
status 0/SUCCESS
```

This is normal after successful completion.

Enable the timer:

```bash
sudo systemctl enable --now lums-agent.timer
```

Check the timer:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

View scheduled timers:

```bash
systemctl list-timers --all | grep lums
```

View service logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

The installed systemd timer configuration is authoritative for the reporting schedule.

---

## 23. Execution Watcher Security

The execution watcher runs independently from the reporting agent.

The watcher must:

1. Load the protected configuration.
2. Contact the LUMS server using HTTPS.
3. Authenticate using the client token.
4. Check whether a pending job exists.
5. Check idle detection support.
6. Verify the configured idle threshold.
7. Attempt an atomic job claim.
8. Execute only a successfully claimed job.
9. Submit a validated result.
10. Handle interrupted execution carefully.

The watcher must not execute a job merely because it appears in a list of pending jobs.

---

## 24. Idle-Aware Execution

The current watcher uses `w -h` for idle detection.

This is primarily suitable for:

* Server environments
* Terminal sessions
* Console sessions
* SSH-oriented environments

It is not a universal desktop idle detection mechanism.

The watcher uses metadata such as:

```text
idle
idle_seconds
idle_threshold_seconds
idle_source
idle_supported
```

The configured idle threshold is:

```text
300 seconds
```

The watcher should only execute jobs when:

* Idle detection is supported.
* The idle threshold has been reached.
* A pending job exists.
* The job is assigned to the authenticated client.
* The job is successfully claimed.
* The package manager is available for execution.

The watcher must not execute update jobs while active user activity is detected.

---

## 25. Job Claiming

Job claiming must be atomic.

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
* Multiple workers
* Concurrent requests
* Network retries
* Multiple watcher instances

---

## 26. Job Result Validation

The watcher may submit result states such as:

```text
success
partial
failed
```

The server must validate:

* Job existence
* Client authorization
* Current job state
* Result format
* Result ownership
* Allowed state transitions

A client must not be able to submit an arbitrary successful result for a job it did not execute.

---

## 27. Job Recovery

A job may remain in the `running` state if:

* The client loses power
* The watcher is terminated
* The system reboots
* The network connection fails
* The package manager process crashes
* Result submission fails

Recovery logic must prevent permanent running jobs.

Recovery must be designed carefully to avoid:

* Duplicate package operations
* Incorrect success states
* Missing audit information
* Permanent job locks
* Unclear execution results

Recovery behavior must be tested before being used in critical environments.

---

## 28. APT and dpkg Safety

Complete APT and dpkg collision prevention is not fully implemented.

The custom LUMS lock does not automatically force arbitrary user-issued APT or dpkg commands to honor the LUMS lock.

A potential collision may occur when:

```text
LUMS watcher starts an operation
        +
User manually runs apt or dpkg
        =
Potential package manager collision
```

This is an important reliability and security limitation.

LUMS must not claim that all package manager collisions are already prevented.

Potential future improvements include:

* Detecting active APT or dpkg processes
* Deferring jobs while the package manager is busy
* Stronger execution coordination
* Better lock handling
* Job timeout handling
* Improved recovery logic
* Clearer audit events
* Additional integration tests

Until this is fully addressed, update execution must be tested carefully in controlled environments.

---

## 29. Simulation Mode

Simulation mode is intended for testing the watcher workflow without changing installed packages.

Enable it temporarily:

```bash
sudo systemctl edit --runtime lums-execution-watcher.service
```

Add:

```ini
[Service]
Environment=LUMS_SIMULATE_UPDATES=1
```

Run the watcher:

```bash
sudo systemctl start lums-execution-watcher.service
```

Review the logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
```

Remove the runtime override:

```bash
sudo systemctl revert --runtime lums-execution-watcher.service
sudo systemctl daemon-reload
```

Verify the configuration:

```bash
sudo systemctl cat lums-execution-watcher.service
```

Simulation mode must not be permanently enabled in production.

Simulation mode still requires:

* A valid client token
* A reachable LUMS server
* A valid pending job
* Supported idle detection
* A sufficient idle period

---

## 30. Database Security

LUMS uses SQLite inside the Docker volume:

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

The database must not be published or copied into the public repository.

---

## 31. Database Integrity

Check the SQLite database:

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

Expected result:

```text
ok
```

Do not modify the database manually without:

1. A verified backup.
2. A clear reason.
3. An understanding of the schema.
4. A controlled maintenance window.
5. Validation after the change.

---

## 32. SQLite-Aware Backup

Create the backup directory:

```bash
sudo mkdir -p /var/backups/lums
sudo chmod 700 /var/backups/lums
```

A SQLite-aware backup is preferred over copying an active database file directly.

Example:

```bash
sudo docker run --rm \
    -v lums-data:/var/lib/lums:ro \
    -v /var/backups/lums:/backup \
    lums:latest \
    python3 -c '
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

Protect the backup:

```bash
sudo chmod 600 /var/backups/lums/lums.db.backup
```

Check the backup:

```bash
sudo ls -lh /var/backups/lums/lums.db.backup
```

---

## 33. Backup Verification

A backup must be verified before it is considered reliable.

Example:

```bash
sudo docker run --rm \
    -v /var/backups/lums:/backup:ro \
    lums:latest \
    python3 -c '
import sqlite3

database = sqlite3.connect(
    "file:/backup/lums.db.backup?mode=ro",
    uri=True
)

result = database.execute(
    "PRAGMA integrity_check;"
).fetchone()[0]

print("Integrity check:", result)

database.close()
'
```

Expected result:

```text
Integrity check: ok
```

Backups should also be tested in an isolated restore environment.

---

## 34. Database Restore

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

---

## 35. Git Repository Security

The repository is located at:

```text
/opt/lums-public
```

Before committing changes:

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

Do not commit:

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

Use placeholders in documentation:

```text
<LUMS_SERVER_IP>
<CLIENT_IP>
<CLIENT_TOKEN>
<ADMIN_PASSWORD>
<JOB_ID>
```

---

## 36. Secure Git Workflow

Before pushing changes:

```bash
cd /opt/lums-public

git status
git diff --check
git diff
```

Review the recent history:

```bash
git log --oneline --decorate -5
```

Review the files included in the commit:

```bash
git diff --cached --name-status
```

Use the configured repository identity:

```text
Name:  NovaForgeCtrl
Email: 232026481+NovaForgeCtrl@users.noreply.github.com
```

Do not push unreviewed changes directly to the main branch.

If a secret is accidentally committed:

1. Revoke or rotate the secret immediately.
2. Remove the secret from the repository.
3. Review the Git history.
4. Check whether the secret was publicly accessible.
5. Document the incident.
6. Do not assume that deleting the latest file removes the secret from history.

---

## 37. Logging Security

The LUMS server uses Docker logs:

```bash
sudo docker logs --tail 100 lums
```

Follow live logs:

```bash
sudo docker logs -f lums
```

The reporting agent uses the systemd journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

The execution watcher uses:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
```

Nginx logs can be reviewed using:

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
* Sensitive inventory information

Redact sensitive information before sharing logs.

---

## 38. Filesystem Permissions

Review sensitive file permissions:

```bash
sudo stat -c '%U:%G %a %n' \
    /etc/lums/docker/lums.env \
    /etc/lums/tls/lums.key \
    /etc/default/lums-agent
```

Recommended permissions:

```text
Environment files:       0600
Private keys:            0600
Public certificates:     0644
Agent configuration:     0600
Backup directory:        0700
Backup database files:   0600
```

Permissions must be reviewed after:

* Installation
* Updates
* Manual changes
* File transfers
* Restores
* Deployment operations

---

## 39. Firewall Security

Only required services should be exposed.

Typical allowed ports:

```text
22/tcp    SSH
80/tcp    HTTP redirect
443/tcp   HTTPS
```

Check the firewall:

```bash
sudo ufw status verbose
```

The following application ports should not be publicly exposed:

```text
5000
5050
```

Firewall rules must be reviewed after network or deployment changes.

---

## 40. Deployment Security

Before updating LUMS:

```bash
cd /opt/lums-public

git status --short
git fetch origin
git log --oneline --decorate -3
```

Update the repository:

```bash
git pull --ff-only origin main
```

Build the image:

```bash
sudo docker build -t lums:latest .
```

Before recreating the container:

```bash
sudo docker ps
sudo docker volume inspect lums-data
```

Stop and remove only the container:

```bash
sudo docker stop lums
sudo docker rm lums
```

Do not remove the persistent volume.

Start the updated container:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
```

Verify the deployment:

```bash
sudo docker ps
sudo docker logs --tail 100 lums
sudo nginx -t
```

A successful Docker build does not prove that the complete deployment is working correctly.

---

## 41. Security Headers

The application should provide suitable security headers where applicable.

Potential headers include:

```text
Content-Security-Policy
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Strict-Transport-Security
```

Headers must be tested carefully to avoid breaking the application.

Check response headers:

```bash
curl \
    --cacert /opt/lums-agent/lums-ca.crt \
    -I \
    https://<LUMS_SERVER_IP>/
```

HSTS should only be enabled after HTTPS has been configured and tested correctly.

---

## 42. Flask Deployment Considerations

The current LUMS application runs Flask inside a Docker container.

The Flask development server is suitable only for the current controlled laboratory environment.

A production-oriented deployment should consider:

* A production WSGI server
* Process supervision
* Resource limits
* Container hardening
* Dedicated service accounts
* Dependency updates
* Monitoring
* Centralized logging
* Network segmentation
* Regular security reviews

The current laboratory deployment must not automatically be considered production-ready.

---

## 43. Incident Handling

### 43.1 Compromised Client Token

If a client token is compromised:

1. Identify the affected client.
2. Revoke or replace the token.
3. Review recent client activity.
4. Check server and application logs.
5. Issue a new token.
6. Update the client configuration.
7. Verify authentication.
8. Document the incident.

Never continue using a known-compromised token.

---

### 43.2 Compromised Server Secret

If the server secret is compromised:

1. Restrict access to the server.
2. Review application logs.
3. Rotate the secret.
4. Restart the Docker container.
5. Verify authentication and sessions.
6. Review related credentials.
7. Document the incident.

The exact rotation procedure depends on how the secret is used by the application.

---

### 43.3 Compromised TLS Private Key

If the TLS private key is compromised:

1. Replace the certificate and private key.
2. Update trusted certificates on clients.
3. Reload Nginx.
4. Verify certificate validation.
5. Review possible unauthorized access.
6. Document the incident.

---

### 43.4 Exposed Database or Backup

If a database or backup becomes exposed:

1. Restrict access immediately.
2. Determine which information was exposed.
3. Review authentication-related data.
4. Rotate affected credentials or tokens.
5. Replace compromised backups if necessary.
6. Review access logs.
7. Document the incident.

---

## 44. Security Testing Checklist

### Server

* [ ] Docker container is running
* [ ] Docker volume is mounted
* [ ] Application binds only to localhost
* [ ] Port `5000` is not externally exposed
* [ ] Port `5050` is not externally exposed
* [ ] Nginx configuration passes validation
* [ ] HTTPS is enabled
* [ ] HTTP redirects to HTTPS
* [ ] TLS certificate contains the correct SAN
* [ ] Private key permissions are restricted
* [ ] Environment file permissions are restricted
* [ ] Firewall rules are reviewed

### Authentication

* [ ] Administrator authentication works
* [ ] Invalid credentials are rejected
* [ ] Invalid client tokens are rejected
* [ ] Client tokens are not logged
* [ ] Token hashes use the expected format
* [ ] Protected endpoints require authentication
* [ ] Token rotation has been tested

### Authorization

* [ ] Clients cannot access other clients' data
* [ ] Client IDs are validated server-side
* [ ] Update jobs are restricted to authorized clients
* [ ] Job claims are restricted to authorized clients
* [ ] Job results are restricted to authorized clients
* [ ] Administrative endpoints are protected
* [ ] Unauthorized state changes are rejected

### Agent

* [ ] Agent uses HTTPS
* [ ] TLS verification is enabled
* [ ] CA certificate is available
* [ ] Agent configuration is protected
* [ ] Reporting timer is enabled
* [ ] Watcher timer is enabled
* [ ] Inventory reporting works
* [ ] Update job retrieval works
* [ ] Atomic job claiming works
* [ ] Job result reporting works
* [ ] Simulation mode is disabled after testing

### Database

* [ ] Database integrity check returns `ok`
* [ ] Backups are created
* [ ] Backups are protected
* [ ] Backups are verified
* [ ] Restore procedure is documented
* [ ] Database files are not committed to Git
* [ ] Backup files are not committed to Git

### Git

* [ ] No secrets are committed
* [ ] No private keys are committed
* [ ] No tokens are committed
* [ ] No database files are committed
* [ ] No backups are committed
* [ ] Changes are reviewed before pushing
* [ ] Documentation uses placeholders
* [ ] Git history is reviewed after accidental exposure

---

## 45. Current Security Limitations

The following limitations must be considered.

### 45.1 Idle Detection

The current idle detection uses `w -h`.

It is primarily suitable for server, terminal, console, and SSH-oriented environments.

It is not a universal desktop idle detection mechanism.

### 45.2 Package Manager Coordination

Complete collision prevention between LUMS and arbitrary user-issued APT or dpkg commands is not fully implemented.

The LUMS lock does not automatically force every external package manager process to honor it.

### 45.3 Token Hashing

The current implementation uses a SHA-256 hexadecimal digest for client token verification.

This format must be reviewed as the authentication architecture evolves.

### 45.4 Self-Signed Certificates

Self-signed certificates require explicit trust configuration on clients.

They are suitable for controlled laboratory environments but may not be appropriate for every deployment scenario.

### 45.5 SQLite Scaling

SQLite is suitable for the current project scope and laboratory development.

Larger deployments may require a different database architecture depending on:

* Number of clients
* Concurrent requests
* Job volume
* Audit log size
* Backup requirements
* High availability requirements

---

## 46. Recommended Security Improvements

Recommended future improvements:

1. Enforce Bearer authentication on every protected endpoint.
2. Strengthen client authorization checks.
3. Review the client token hashing strategy.
4. Implement token rotation and revocation.
5. Improve package manager collision prevention.
6. Add package manager busy detection.
7. Improve watcher recovery handling.
8. Add job timeout handling.
9. Improve desktop idle detection support.
10. Add detailed audit events.
11. Add security regression tests.
12. Add automated integration tests.
13. Improve backup and restore procedures.
14. Add database migration handling.
15. Improve structured logging.
16. Add monitoring and alerting.
17. Review container hardening.
18. Review the complete update execution workflow before production use.

---

## 47. Responsible Security Reporting

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

## 48. Security Maintenance

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
Nginx configuration
TLS certificates
File permissions
Database backups
Git history
Authentication behavior
Authorization behavior
Job execution behavior
Package manager coordination
```

---

## 49. Final Security Principles

The following principles apply to LUMS:

1. Never store secrets in Git.
2. Never expose the Flask application directly to the network.
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

---

## 50. Final Principle

LUMS is designed to centralize Linux update management without removing operational control from the administrator.

The system should remain:

* Transparent
* Auditable
* Controlled
* Secure
* Documented
* Maintainable

> **LUMS — Linux Update Management without the noise.**

> **Secure the management plane. Keep execution controlled.**
