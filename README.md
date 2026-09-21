# LUMS

## Linux Update Management Server

> **Linux Update Management without the noise.**

LUMS is a lightweight Linux update management platform designed for small labs, test environments and infrastructure projects.

It provides centralized management for:

* Linux client inventory
* Update information
* Installed package information
* Client authentication
* Client token lifecycle
* Update jobs
* Agent communication
* Idle-aware execution
* Administrative auditing
* Controlled update execution
* Running-job recovery

LUMS follows a documentation-first approach with a focus on:

* Simple architecture
* Transparent operation
* Central client management
* Secure agent authentication
* Minimal dependencies
* Auditable communication
* Controlled execution
* Easy deployment
* Container hardening
* Explicit recovery procedures

---

# 1. Project Overview

LUMS consists of a central management server and Linux agents.

The server manages clients, inventory and update jobs.

The agent collects information, determines local idle state and executes authorized update jobs when the configured conditions are met.

```text
                    ┌─────────────────────────┐
                    │         Nginx            │
                    │      HTTPS / TLS         │
                    │          :443            │
                    └────────────┬────────────┘
                                 │
                         HTTP localhost
                                 │
                          127.0.0.1:5050
                                 │
                    ┌────────────▼────────────┐
                    │      Docker: lums       │
                    │                         │
                    │      Gunicorn           │
                    │       Flask :5000       │
                    └────────────┬────────────┘
                                 │
                         Docker Volume
                                 │
                    ┌────────────▼────────────┐
                    │       lums-data         │
                    │                         │
                    │   /var/lib/lums         │
                    │        lums.db          │
                    └─────────────────────────┘


              ┌───────────────┐
              │   Client 1   │
              │    Agent     │
              └───────┬───────┘
                      │
                      │ HTTPS
                      ▼
                   Nginx


              ┌───────────────┐
              │   Client 2   │
              │    Agent     │
              └───────┬───────┘
                      │
                      │ HTTPS
                      ▼
                   Nginx


              ┌───────────────┐
              │   Client N   │
              │    Agent     │
              └───────┬───────┘
                      │
                      │ HTTPS
                      ▼
                   Nginx
```

The application is bound to localhost on the host:

```text
127.0.0.1:5050
```

The application is not intended to be directly exposed to the network.

Nginx provides the external HTTPS endpoint.

The Flask application is served through Gunicorn inside the container.

---

# 2. Current Feature Set

The current implementation includes:

* Flask-based management server
* SQLite persistence
* Docker deployment
* Nginx reverse proxy
* HTTPS/TLS communication
* Administrator authentication
* Argon2 password hashing
* Session handling
* CSRF protection
* Security headers
* Client-specific Bearer tokens
* SHA-256 token digest storage
* Client token rotation
* Client token invalidation through rotation
* Client inventory
* Installed package inventory
* Available update inventory
* Update job creation
* Package validation
* Atomic job claiming
* Running-job recovery
* Abandoned-job handling
* Update result reporting
* Idle-state detection
* Idle-aware job execution
* Execution Watcher
* Simulation mode for safe end-to-end testing
* Audit logging
* Multiple frontend themes
* Container non-root execution
* Read-only container root filesystem
* Dropped Linux capabilities
* File-based Flask secret handling
* Production Gunicorn serving

The project is actively developed.

The API, database schema and deployment model may evolve.

---

# 3. Architecture

## Server architecture

```text
Internet / LAN
      │
      │ HTTPS :443
      ▼
┌───────────────┐
│     Nginx     │
│ Reverse Proxy │
│   TLS / HTTPS │
└───────┬───────┘
        │
        │ HTTP
        │ 127.0.0.1:5050
        ▼
┌────────────────────────┐
│ Docker Container       │
│ "lums"                 │
│                        │
│ User: lums / UID 10001 │
│ Read-only root FS      │
│ Capabilities: none     │
│                        │
│ Gunicorn               │
│ Flask :5000            │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│ Docker Volume          │
│ lums-data              │
│                        │
│ /var/lib/lums          │
└──────────┬─────────────┘
           │
           ▼
        lums.db
```

The Flask application is bound to the container port:

```text
5000
```

The host publishes this only on:

```text
127.0.0.1:5050
```

Nginx provides the external HTTPS endpoint.

Port `5000` is not directly exposed to the network.

Port `5050` is bound only to localhost.

---

# 4. Client Architecture

The client side consists of two systemd-controlled processes:

```text
Reporting:

lums-agent.timer
        │
        ▼
lums-agent.service
        │
        ▼
agent.py
        │
        ▼
HTTPS report
```

```text
Execution:

lums-execution-watcher.timer
        │
        ▼
lums-execution-watcher.service
        │
        ▼
watcher.py
        │
        ▼
Idle detection
        │
        ▼
Job recovery / lookup
        │
        ▼
Atomic job claim
        │
        ▼
Update execution
        │
        ▼
Result reporting
```

Reporting and job execution are intentionally separated.

The reporting timer does not need to execute an update job directly.

The installed systemd timer configuration is authoritative for the actual execution schedule.

---

# 5. Current Deployment

The current laboratory deployment uses:

```text
Repository:
    /opt/lums-public

Server address:
    <LUMS_SERVER_IP>

Docker container:
    lums

Docker image:
    lums:latest

Docker volume:
    lums-data

Host binding:
    127.0.0.1:5050

Container port:
    5000

HTTPS:
    443

Application configuration:
    /etc/lums/docker/lums.env

Flask secret file:
    /etc/lums/secrets/lums_secret

Container secret path:
    /run/secrets/lums_secret

Database:
    /var/lib/lums/lums.db

TLS certificate:
    /etc/lums/tls/lums.crt

TLS private key:
    /etc/lums/tls/lums.key
```

The Flask secret is no longer supplied as the normal:

```text
LUMS_SECRET_KEY
```

environment variable.

The production container uses:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

The secret file is mounted read-only into the container.

Replace placeholders with local values when deploying.

Never publish real internal IP addresses, credentials or private keys unnecessarily.

---

# 6. Repository Structure

The current application source is organized approximately as follows:

```text
LUMS/
├── agent/
│   ├── agent.py
│   ├── watcher.py
│   ├── lums-agent.env.example
│   ├── lums-agent.service
│   └── lums-agent.timer
│
├── server/
│   ├── app.py
│   ├── create_admin.py
│   ├── init_db.py
│   ├── security.py
│   ├── security_migration.py
│   │
│   ├── static/
│   │   ├── app.js
│   │   ├── client.js
│   │   ├── network.js
│   │   ├── style.css
│   │   └── theme.js
│   │
│   └── templates/
│       ├── client.html
│       ├── index.html
│       └── login.html
│
├── Dockerfile
├── docker-entrypoint.sh
├── .dockerignore
├── LICENSE
└── README.md
```

Additional files may be added as development continues.

The exact repository structure should be treated as implementation detail and may evolve.

---

# 7. Technology Stack

| Component                    | Technology              |
| ---------------------------- | ----------------------- |
| Backend                      | Python / Flask          |
| WSGI server                  | Gunicorn                |
| Database                     | SQLite                  |
| Containerization             | Docker                  |
| Reverse proxy                | Nginx                   |
| Transport                    | HTTPS / TLS             |
| Administrator authentication | Argon2                  |
| Client authentication        | Bearer tokens           |
| Frontend                     | HTML / CSS / JavaScript |
| Agent                        | Python                  |
| Scheduling                   | systemd timers          |
| Package management           | APT / dpkg              |
| Repository                   | Git                     |

LUMS intentionally avoids unnecessary infrastructure dependencies.

---

# 8. Frontend and Theme System

LUMS includes multiple frontend themes.

Current theme identifiers are:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

The `admin` identifier represents the user-facing:

```text
Enterprise Admin
```

theme.

Theme selection is handled by:

```text
server/static/theme.js
```

The selected theme is stored in browser local storage using:

```text
lums-theme
```

The current theme is applied through:

```text
data-theme
```

on the root HTML element.

The frontend also includes:

```text
server/static/network.js
```

which provides the animated network visualization used by the Geek theme.

Theme-specific styling is primarily scoped through:

```text
html[data-theme="..."]
```

This allows the themes to remain visually separated.

Current themes:

```text
Standard LUMS
LUMS Stadium
Golf Club
Nerd Mode
Geek Lab
Enterprise Admin
```

The Enterprise Admin theme is intentionally designed as a restrained infrastructure management console.

The Geek theme provides:

```text
The Living Network
```

The Nerd theme provides a terminal/CRT/Matrix-style presentation.

Theme-specific visual effects do not modify backend functionality, authentication, authorization, database state or update execution.

The detailed theme architecture is documented separately.

---

# 9. Design Principles

## Understandable architecture

The server architecture remains intentionally small:

```text
Nginx
   ↓
Docker
   ↓
Gunicorn
   ↓
Flask
   ↓
SQLite
```

The client architecture is also separated into clear responsibilities:

```text
Reporting Timer
   ↓
Agent
   ↓
LUMS API
```

```text
Execution Timer
   ↓
Execution Watcher
   ↓
Idle Detection
   ↓
Job Recovery / Lookup
   ↓
Atomic Claim
   ↓
Execution
   ↓
Result API
```

## Persistent data outside the image

Application files are stored in the Docker image:

```text
lums:latest
```

Persistent data is stored in:

```text
lums-data
```

The database must survive container recreation.

Never remove the volume during a normal deployment.

## Secrets outside the image

The Flask secret is stored outside the Git repository and outside the Docker image:

```text
/etc/lums/secrets/lums_secret
```

The container receives it through a read-only bind mount:

```text
/run/secrets/lums_secret
```

The application reads the secret using:

```text
LUMS_SECRET_KEY_FILE
```

---

# 10. Server Requirements

A typical laboratory deployment requires:

* Linux
* Docker
* Nginx
* HTTPS certificate
* Network connectivity
* Sufficient storage

A practical starting point:

```text
2 CPU cores
4 GB RAM
20+ GB storage
```

Actual requirements depend on:

* Number of clients
* Inventory size
* Database growth
* Logging
* Update frequency
* Future features

These values are starting points for laboratory deployments, not hard minimum requirements.

---

# 11. Agent Requirements

The LUMS agent requires:

* Linux
* Python 3
* systemd
* APT
* Network connectivity
* Valid client token
* LUMS CA certificate when using a private CA

The agent is currently designed primarily for Linux server, terminal and SSH-oriented environments.

Desktop-specific idle detection may require an additional provider in the future.

---

# 12. Installation Overview

```text
1. Install Docker
        │
        ▼
2. Clone repository
        │
        ▼
3. Build Docker image
        │
        ▼
4. Create persistent volume
        │
        ▼
5. Configure application environment
        │
        ▼
6. Configure secret file
        │
        ▼
7. Start hardened container
        │
        ▼
8. Configure Nginx / HTTPS
        │
        ▼
9. Open dashboard
        │
        ▼
10. Create client
        │
        ▼
11. Install agent
        │
        ▼
12. Configure token and CA
        │
        ▼
13. Send first report
        │
        ▼
14. Enable execution watcher
```

---

# 13. Docker Build

```bash
cd /opt/lums-public

sudo docker build \
    -t lums:latest \
    .
```

Verify:

```bash
sudo docker images lums
```

Inspect:

```bash
sudo docker image inspect lums:latest
```

The resulting image should contain the current application source and Gunicorn configuration.

---

# 14. Persistent Docker Volume

Create the volume if it does not exist:

```bash
sudo docker volume create lums-data
```

Verify:

```bash
sudo docker volume inspect lums-data
```

The volume is mounted at:

```text
/var/lib/lums
```

The database is:

```text
/var/lib/lums/lums.db
```

The volume must not be deleted during normal application updates.

---

# 15. Server Environment and Secrets

Non-secret application configuration may be stored outside Git at:

```text
/etc/lums/docker/lums.env
```

Protect the file:

```bash
sudo chown root:root \
    /etc/lums/docker/lums.env

sudo chmod 600 \
    /etc/lums/docker/lums.env
```

The Flask secret is handled separately.

Production secret file:

```text
/etc/lums/secrets/lums_secret
```

Protect the directory:

```bash
sudo chown root:root \
    /etc/lums/secrets

sudo chmod 700 \
    /etc/lums/secrets
```

Protect the secret file:

```bash
sudo chown root:10001 \
    /etc/lums/secrets/lums_secret

sudo chmod 640 \
    /etc/lums/secrets/lums_secret
```

The production container receives the secret through:

```text
/run/secrets/lums_secret
```

with a read-only mount.

The actual secret value must never be printed in documentation, logs or troubleshooting output.

---

# 16. Starting the Container

The current production container uses the following hardened configuration:

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

The container is intentionally:

```text
non-root
read-only
not privileged
without Linux capabilities
```

The writable locations are explicitly limited.

The persistent application data is stored in:

```text
/var/lib/lums
```

Temporary files use:

```text
/tmp
```

which is provided through a restricted tmpfs.

Verify:

```bash
sudo docker ps --filter name=^/lums$
```

Check the port mapping:

```bash
sudo docker port lums
```

Expected:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 17. Nginx and HTTPS

Nginx provides the external HTTPS endpoint:

```text
Client
  │
  │ HTTPS :443
  ▼
Nginx
  │
  │ HTTP
  ▼
127.0.0.1:5050
  │
  ▼
Docker / Gunicorn / Flask
```

Test the configuration:

```bash
sudo nginx -t
```

Reload:

```bash
sudo systemctl reload nginx
```

Check:

```bash
sudo systemctl status nginx --no-pager
```

---

# 18. TLS Verification

The agent should verify the server certificate.

Example CA file:

```text
/opt/lums-agent/lums-ca.crt
```

Diagnostic test:

```bash
curl -k https://<LUMS_SERVER_HOST>/api/health
```

The `-k` option disables certificate verification and should only be used for troubleshooting.

It must not become the normal security configuration.

Inspect the certificate:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

Inspect SAN:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -ext subjectAltName
```

The SAN must match the hostname or address used by clients.

---

# 19. API Health Check

The health endpoint is:

```text
/api/health
```

Test through HTTPS:

```bash
curl -k https://<LUMS_SERVER_HOST>/api/health
```

This verifies the path:

```text
Nginx
   ↓
Docker
   ↓
Gunicorn
   ↓
Flask
```

A successful health response does not replace authentication and authorization testing.

---

# 20. Administrator Authentication

The web interface requires administrator authentication.

The application includes:

* Password hashing using Argon2
* Login and logout
* Session handling
* CSRF protection
* Security headers
* Audit logging

Administrator passwords and session secrets must never be committed to Git.

The Flask session secret is loaded from the dedicated secret file in the hardened production deployment.

Secret rotation invalidates existing Flask sessions.

---

# 21. Client Authentication

Each client receives an individual Bearer token.

The agent sends:

```http
Authorization: Bearer <CLIENT_TOKEN>
```

The server stores a SHA-256 hexadecimal digest of the token rather than the plaintext token.

This is token-digest storage and must not be confused with password hashing.

Conceptually:

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
SQLite
```

Real tokens must never appear in:

* README files
* Screenshots
* Git commits
* Issue reports
* Public documentation
* Audit log details

Use:

```text
<CLIENT_TOKEN>
```

for examples.

---

# 22. Client Token Rotation

LUMS supports client-token rotation.

The administrative endpoint is:

```text
POST /api/clients/<client_id>/token/rotate
```

The operation requires:

```text
Authenticated administrator session
+
Valid CSRF token
```

A successful rotation:

1. Generates a new cryptographically random token.
2. Stores the new SHA-256 digest.
3. Updates the token creation timestamp.
4. Invalidates the previous token.
5. Creates an audit entry.
6. Returns the new token once.

The previous token immediately becomes invalid.

The new token is not stored in plaintext in the database or audit log.

The frontend provides:

```text
🔐 Token rotieren
```

and:

```text
📋 Token kopieren
```

The newly generated token is displayed only in the rotation result view.

The administrator must update the corresponding LUMS agent configuration after rotation.

---

# 23. Agent Configuration

Example:

```text
LUMS_BASE=https://<LUMS_SERVER_HOST>
LUMS_TOKEN=<CLIENT_TOKEN>
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

The example configuration is stored in:

```text
agent/lums-agent.env.example
```

The actual configuration is installed locally at:

```text
/etc/default/lums-agent
```

Protect the configuration:

```bash
sudo chmod 600 /etc/default/lums-agent
```

The actual client token must never be published.

After token rotation, update the agent configuration with the new token before expecting reporting to succeed.

---

# 24. Agent Installation

The source files are:

```text
agent/agent.py
agent/watcher.py
```

The installed files are:

```text
/opt/lums-agent/agent.py
/opt/lums-agent/watcher.py
```

The CA certificate is:

```text
/opt/lums-agent/lums-ca.crt
```

The agent uses:

```text
lums-agent.service
lums-agent.timer
```

The execution watcher uses:

```text
lums-execution-watcher.service
lums-execution-watcher.timer
```

---

# 25. Agent Service

The reporting service uses a systemd timer and performs an individual reporting cycle.

The installed unit configuration is authoritative for its exact behavior and schedule.

The service may complete and become inactive after a successful oneshot execution.

This is normal when the service is triggered by a systemd timer.

Run manually:

```bash
sudo systemctl start lums-agent.service
```

---

# 26. Agent Timer

Enable the reporting timer:

```bash
sudo systemctl enable --now lums-agent.timer
```

Check:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

List scheduled execution:

```bash
systemctl list-timers --all | grep lums-agent
```

Run the service manually:

```bash
sudo systemctl start lums-agent.service
```

View logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 27. Execution Watcher

The execution watcher is responsible for:

1. Authenticating the client
2. Recovering an already-running job
3. Looking up pending jobs
4. Checking local idle state
5. Waiting until the idle threshold is reached
6. Atomically claiming a job
7. Executing the claimed job
8. Reporting the result

The watcher is executed independently of the reporting service.

Its exact schedule is defined by the installed systemd timer.

---

# 28. Execution Watcher Timer

Enable the watcher timer:

```bash
sudo systemctl daemon-reload

sudo systemctl enable --now \
    lums-execution-watcher.timer
```

Check:

```bash
systemctl status \
    lums-execution-watcher.timer \
    --no-pager
```

List the timer:

```bash
systemctl list-timers --all \
    | grep lums-execution-watcher
```

View watcher logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
```

The installed timer configuration is authoritative for the actual execution schedule.

---

# 29. Idle Detection

The agent checks local activity before executing an update job.

The current server and SSH-oriented implementation uses:

```text
w -h
```

The relevant idle threshold is configurable through the installed agent configuration and implementation.

The exact active value should be verified on the client rather than assumed from documentation.

The agent must not execute an update when idle detection is unsupported.

---

# 30. Idle Status

The agent can return information similar to:

```json
{
    "idle": false,
    "idle_seconds": 5,
    "threshold_seconds": 300,
    "idle_source": "w",
    "idle_supported": true
}
```

If the idle state cannot be determined safely:

```json
{
    "idle": false,
    "idle_seconds": 0,
    "threshold_seconds": 300,
    "idle_source": "w",
    "idle_supported": false
}
```

Automatic execution must not proceed when idle detection is unsupported.

This is a safety-first design decision.

---

# 31. Job Lifecycle

The update job lifecycle includes:

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

The client determines whether the local idle threshold has been reached.

The server manages the job state.

The agent must claim a job atomically before execution.

A job that is recovered because execution was interrupted may be marked:

```text
abandoned
```

when the agent cannot safely continue it.

---

# 32. Atomic Job Claiming

A pending job is not executed immediately.

The agent first claims the job through the API.

The server uses an atomic database operation to ensure that the same pending job is not claimed multiple times by competing requests.

Conceptually:

```text
Pending Job
    │
    ▼
Atomic Claim
    │
    ├── Successful → Running
    │
    └── Already claimed → No execution
```

Only the successfully claimed job may be executed.

---

# 33. Running-Job Recovery

The watcher checks for an already-running job before looking for new pending jobs.

This supports recovery after:

* Service interruption
* SSH disconnection
* Watcher restart
* System restart
* Partial execution lifecycle interruption

The recovery mechanism can safely abandon an interrupted running job rather than leaving it permanently stuck.

The recovery endpoint is:

```text
POST /api/update-jobs/<job_id>/abandon
```

The endpoint:

* Requires client authentication.
* Verifies that the job belongs to the authenticated client.
* Only permits recovery of a `running` job.
* Marks the job as `abandoned`.
* Records a recovery reason.
* Records the recovery in update history.
* Uses conditional state handling to avoid unsafe races.

The agent must not claim a new job if recovery of an existing running job fails.

This prevents a failed recovery from silently producing a second active execution.

---

# 34. Update Job Creation

Update jobs are created through the management interface.

The server validates that requested packages exist in the available update inventory for the selected client.

Invalid or unknown packages are rejected.

The package list is normalized and duplicate package names are removed.

The job is then stored in the database with its package records.

---

# 35. Update Execution

The agent executes packages locally using the operating system's package management infrastructure.

APT remains responsible for:

* Repository handling
* Dependency resolution
* Package signatures
* Package installation
* dpkg interaction

LUMS does not replace APT.

The execution implementation reports individual package results and an overall job status.

Possible overall results include:

```text
success
partial
failed
```

Interrupted execution may additionally result in:

```text
abandoned
```

---

# 36. Execution Results

The agent reports the result through the update-job result API.

The result contains information such as:

```text
Job ID
Package results
Overall status
Successful package count
Failed package count
Reboot requirement
```

The server verifies that:

* The job belongs to the authenticated client
* The job is currently running
* The submitted result has a valid status

A result cannot be submitted for a job that is no longer running.

The exact API route should be verified against the current server implementation.

---

# 37. Simulation Mode

LUMS includes a simulation mode for safe end-to-end testing.

Simulation mode:

* Does not execute real APT updates
* Does not modify installed packages
* Simulates package execution
* Exercises the job lifecycle
* Tests watcher behavior
* Tests result reporting
* Tests UI status updates

The simulation mode is controlled through:

```text
LUMS_SIMULATE_UPDATES
```

Simulation mode must not be unintentionally enabled in a production deployment.

After testing, verify the active environment configuration.

---

# 38. Simulation Safety

Simulation mode is intended for:

* Development
* Testing
* End-to-end validation
* UI verification
* Job lifecycle testing

A successful simulation does not prove that real package-manager collisions are fully handled.

Real APT/dpkg coordination requires additional safeguards.

---

# 39. Package Manager Safety

Package-manager coordination remains an open development and hardening area.

Potential safeguards include:

* LUMS execution lock
* Detection of active APT processes
* Detection of dpkg lock usage
* Wait-and-retry behavior
* Execution timeout
* Graceful deferral
* Explicit `waiting_for_package_manager` state
* No forced removal of lock files

LUMS must never delete foreign APT or dpkg lock files.

A custom LUMS lock does not automatically coordinate with arbitrary manually executed `apt` or `dpkg` commands.

Full collision avoidance requires coordination with the package manager and operational policy.

---

# 40. Reboot Handling

LUMS does not automatically reboot clients.

A reboot requirement may be detected using:

```bash
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot required"
```

A reboot remains an administrative decision.

---

# 41. Database

LUMS uses SQLite for persistent application data.

The database is located inside the container:

```text
/var/lib/lums/lums.db
```

The directory is backed by:

```text
lums-data
```

The database contains application state such as:

* Clients
* Installed packages
* Available updates
* Update jobs
* Package job results
* Authentication-related client data
* Audit information

The schema may evolve over time.

---

# 42. Database Integrity

Run an integrity check:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
result = db.execute("PRAGMA integrity_check;").fetchone()[0]
print(result)
db.close()
'
```

Expected:

```text
ok
```

If the result is not `ok`:

1. Stop unnecessary database changes.
2. Preserve the current database.
3. Create a backup.
4. Review application logs.
5. Review recent changes.
6. Identify a valid backup.
7. Restore only after verification.

Never delete the Docker volume as a first troubleshooting step.

---

# 43. Database Backup

Create the backup directory:

```bash
sudo install -d -m 700 /var/backups/lums
```

Create a SQLite-aware backup:

```bash
sudo docker run --rm \
    --entrypoint python3 \
    -v lums-data:/var/lib/lums:ro \
    -v /var/backups/lums:/backup \
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

Protect the backup:

```bash
sudo chmod 600 \
    /var/backups/lums/lums.db.backup
```

Verify integrity:

```bash
sudo sqlite3 \
    /var/backups/lums/lums.db.backup \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

The SQLite backup mechanism uses the SQLite backup API rather than copying the live database file byte-for-byte.

Backups must not be stored inside the Git repository.

A complete restore procedure should be tested separately before being considered a fully validated disaster-recovery procedure.

---

# 44. API Overview

The LUMS API provides functionality for areas including:

```text
Client management
Client reporting
Client authentication
Client token rotation
Client inventory
Update inventory
Update jobs
Job claiming
Running-job lookup
Running-job recovery
Job result reporting
```

Important authentication boundaries include:

```text
Administrative API operations
    ↓
Administrator session + CSRF

Client API operations
    ↓
Bearer client authentication
    ↓
Authenticated client identity
```

The exact endpoint set is part of the current application implementation and may evolve.

Before integrating an external client against the API, consult the current server source and authentication behavior.

---

# 45. Authentication and Authorization

Authentication identifies the client.

Authorization determines whether the authenticated client may perform the requested operation.

```text
Authentication:
    Who is this client?

Authorization:
    Is this client allowed to perform this operation?
```

A valid token must not grant unrestricted access to other clients.

Client-specific API operations must remain associated with the authenticated client identity.

Administrative operations require an authenticated administrator session.

---

# 46. CSRF Protection

Administrative state-changing operations use CSRF protection.

Examples include:

```text
POST /api/clients
DELETE /api/clients/<id>
POST /api/clients/<id>/token/rotate
```

The dashboard obtains and sends the required CSRF token.

Client reporting uses Bearer token authentication instead.

Missing or invalid CSRF validation is rejected by the application.

---

# 47. Audit Logging

The application includes an audit mechanism for administrative activity.

Audit events include areas such as:

* Authentication events
* Client creation
* Client deletion
* Client token rotation
* Administrative changes
* Update job operations

Token rotation audit entries contain identifying metadata such as the client hostname but do not contain the plaintext client token.

Audit information supports:

* Troubleshooting
* Change tracking
* Security investigations
* Administrative review

---

# 48. Troubleshooting Strategy

The most important rule is:

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

Troubleshoot from the outside toward the inside.

```text
Web Browser
     │
     ▼
Nginx / HTTPS
     │
     ▼
Docker / Gunicorn / Flask
     │
     ▼
SQLite
```

Client side:

```text
systemd timer
     │
     ▼
Agent / Watcher
     │
     ▼
HTTPS / Network
     │
     ▼
LUMS API
```

For container problems, additionally verify:

```text
Container state
     │
     ├── User
     ├── Root filesystem
     ├── Capabilities
     ├── Secret file
     └── Persistent volume
```

---

# 49. Docker Diagnostics

Check the container:

```bash
sudo docker ps --filter name=^/lums$
```

```bash
sudo docker ps -a
```

Check logs:

```bash
sudo docker logs --tail 100 lums
```

Follow logs:

```bash
sudo docker logs -f lums
```

Inspect configuration:

```bash
sudo docker inspect lums
```

Check the state:

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Expected:

```text
running
```

---

# 50. Container Hardening Diagnostics

Check the runtime identity and hardening:

```bash
sudo docker inspect \
    --format \
    'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{json .HostConfig.CapDrop}} Privileged={{.HostConfig.Privileged}}' \
    lums
```

Expected characteristics:

```text
User=lums
ReadonlyRootfs=true
CapDrop=["ALL"]
Privileged=false
```

Check the container user:

```bash
sudo docker exec lums id
```

Expected:

```text
uid=10001(lums)
gid=10001(lums)
```

Check temporary storage:

```bash
sudo docker exec lums sh -c \
    'touch /tmp/lums-test && rm -f /tmp/lums-test && echo "tmpfs writable"'
```

The application directory should not be writable.

The persistent database directory must remain writable:

```bash
sudo docker exec lums sh -c \
    'test -w /var/lib/lums && echo "database volume writable"'
```

Do not remove the read-only root filesystem merely to bypass an application error.

---

# 51. Secret Diagnostics

Never print the secret itself.

Check that the normal environment variable is absent:

```bash
sudo docker inspect lums \
    --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | grep '^LUMS_SECRET_KEY=' \
    || echo 'LUMS_SECRET_KEY absent'
```

Check the file-based configuration:

```bash
sudo docker inspect lums \
    --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | grep '^LUMS_SECRET_KEY_FILE='
```

Expected:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

Check readability:

```bash
sudo docker exec lums \
    test -r /run/secrets/lums_secret \
    && echo 'SECRET_FILE=READABLE' \
    || echo 'SECRET_FILE=NOT_READABLE'
```

Check the host file without printing its contents:

```bash
sudo stat \
    -c '%U:%G %a %s %n' \
    /etc/lums/secrets/lums_secret
```

Expected characteristics:

```text
root:10001
640
```

The secret must never be copied into logs or pasted into a troubleshooting session.

---

# 52. Gunicorn Diagnostics

Check the container logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

A normal startup contains messages similar to:

```text
=== LUMS database initialization ===
LUMS-Datenbank aktualisiert: /var/lib/lums/lums.db
=== Starting Gunicorn ===
Starting gunicorn 23.0.0
Listening at: http://0.0.0.0:5000
Using worker: gthread
Booting worker
```

The current configuration uses:

```text
Gunicorn:
    23.0.0

Workers:
    2

Threads:
    2

Timeout:
    120 seconds

Access log:
    stdout

Error log:
    stderr
```

If Gunicorn workers fail to boot:

1. Check the container logs.
2. Check the secret-file configuration.
3. Check database permissions.
4. Check the image version.
5. Check Python syntax and imports.
6. Do not immediately modify the persistent database.

---

# 53. Nginx Diagnostics

```bash
sudo nginx -t
```

```bash
sudo systemctl status nginx --no-pager
```

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Reload after configuration changes:

```bash
sudo systemctl reload nginx
```

Test HTTP redirect:

```bash
curl -I \
    http://<LUMS_SERVER_HOST>/
```

The expected production behavior is an HTTPS redirect.

---

# 54. Backend Diagnostics

Test the local backend:

```bash
curl -I \
    http://127.0.0.1:5050/
```

A redirect to:

```text
/login
```

can be expected.

If the local backend fails, investigate:

* Docker container
* Gunicorn
* Flask application
* Port mapping
* Secret file
* Database
* Container logs

before investigating TLS or the browser.

---

# 55. HTTPS Diagnostics

Test HTTPS:

```bash
curl -k -I \
    https://<LUMS_SERVER_HOST>/
```

The current production response may be:

```text
HTTP/1.1 302 FOUND
Location: /login
```

The hardened response includes headers such as:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
Content-Security-Policy: ...
```

TLS is restricted to:

```text
TLS 1.2
TLS 1.3
```

Do not disable TLS verification permanently to solve a client connection problem.

---

# 56. Agent Diagnostics

Check the reporting timer:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Run the reporting service:

```bash
sudo systemctl start lums-agent.service
```

Check logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Check the result:

```bash
sudo systemctl show \
    lums-agent.service \
    -p Result
```

Expected after success:

```text
Result=success
```

A successful report should authenticate the client and update the client inventory.

---

# 57. Watcher Diagnostics

Check the watcher timer:

```bash
sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager
```

Run a watcher cycle manually:

```bash
sudo systemctl start \
    lums-execution-watcher.service
```

View logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
```

Check the last result:

```bash
sudo systemctl show \
    lums-execution-watcher.service \
    -p Result
```

When a running job is detected, the watcher should perform the recovery logic before attempting to claim a new job.

---

# 58. Agent Configuration Diagnostics

Inspect configuration safely:

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

Expected configuration:

```text
LUMS_BASE
LUMS_TOKEN
LUMS_CA_FILE
```

Never print the real token to terminal logs or documentation.

---

# 59. Authentication Problems

If the server returns:

```text
401 Unauthorized
```

check:

1. Client token
2. Token rotation state
3. Stored token digest
4. Client enabled state
5. Authorization header
6. LUMS_BASE
7. Agent environment configuration
8. Client authorization logic

Do not disable authentication to solve an authentication problem.

If the client token was recently rotated:

```text
Old Token
    ↓
401 Unauthorized
```

is expected.

Update the agent with the newly generated token and rerun:

```bash
sudo systemctl start lums-agent.service
```

Then inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 50 \
    --no-pager
```

---

# 60. Client Token Rotation Diagnostics

If the administrator rotates a token:

```text
🔐 Token rotieren
```

the old token becomes invalid immediately.

Verify that the new token is supplied to the client agent.

The rotation endpoint requires:

```text
Authenticated administrator session
+
CSRF token
```

Expected failure conditions include:

```text
No administrator session
    → 401

Missing / invalid CSRF
    → 400

Unknown client
    → 404
```

After successful rotation:

```text
Old token → 401
New token → 200
```

The plaintext token must not appear in:

```text
Audit logs
Database
Git
Documentation
```

If the new token was not saved before leaving the rotation result screen, rotate the token again and update the agent with the newly displayed token.

---

# 61. TLS Problems

If the agent cannot connect:

```text
Check LUMS_BASE
Check hostname or IP address
Check network connectivity
Check Nginx
Check certificate
Check CA file
Check certificate SAN
```

The certificate SAN must match the hostname or address used by the agent.

Do not permanently disable certificate verification.

The following may be useful for diagnostics:

```bash
openssl s_client \
    -connect <LUMS_SERVER_HOST>:443 \
    -servername <LUMS_SERVER_HOST>
```

---

# 62. APT Diagnostics

LUMS depends on the client's package manager.

Check APT directly:

```bash
sudo apt update
```

Check available updates:

```bash
apt list --upgradable
```

Check package information:

```bash
apt-cache policy <PACKAGE>
```

Check installed package:

```bash
dpkg -l <PACKAGE>
```

If APT or dpkg is already broken, resolve the local package-manager issue before investigating LUMS.

Never remove package-manager lock files as a first troubleshooting action.

---

# 63. Database Diagnostics

Check database integrity:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check;").fetchone()[0])
db.close()
'
```

Expected:

```text
ok
```

Check the database file:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

Do not modify the database manually unless the operation is understood and a verified backup exists.

---

# 64. Git Workflow

The recommended workflow is:

```text
Modify
   │
   ▼
Test
   │
   ▼
git status
   │
   ▼
git diff
   │
   ▼
git diff --check
   │
   ▼
git add
   │
   ▼
git commit
   │
   ▼
git push
```

Check the working tree:

```bash
git status
```

Review changes:

```bash
git diff
```

Check whitespace:

```bash
git diff --check
```

Stage selected files:

```bash
git add <FILES>
```

Commit:

```bash
git commit -m "Description"
```

Push:

```bash
git push origin main
```

---

# 65. Git Identity

The repository uses:

```text
Name:
   xxxxx

Email:
   xxxxx
```

Check:

```bash
git config user.name
git config user.email
```

Configure locally:

```bash
git config user.name \
xxxx

git config user.email \
    xxxxx
```

---

# 66. Deployment Workflow

The recommended deployment sequence is:

```text
Git fetch
    │
    ▼
Git update
    │
    ▼
Validation
    │
    ├── git diff --check
    └── Python syntax checks
    │
    ▼
Database backup
    │
    ▼
Docker build
    │
    ▼
Verify image
    │
    ▼
Stop container
    │
    ▼
Remove container
    │
    ▼
Reuse lums-data
    │
    ▼
Create hardened container
    │
    ▼
Health check
    │
    ▼
Security verification
    │
    ▼
Agent test
    │
    ▼
Watcher test
```

---

# 67. Pre-Deployment Validation

```bash
cd /opt/lums-public

git status
```

```bash
git diff --check
```

Run Python syntax checks against the current source files:

```bash
python3 -m py_compile \
    server/app.py \
    server/init_db.py \
    agent/agent.py \
    agent/watcher.py
```

Do not deploy if validation fails.

---

# 68. Database Backup Before Deployment

Create the backup directory:

```bash
sudo install -d -m 700 /var/backups/lums
```

Create a SQLite-aware backup:

```bash
sudo docker run --rm \
    --entrypoint python3 \
    -v lums-data:/var/lib/lums:ro \
    -v /var/backups/lums:/backup \
    lums:latest \
    -c '
import sqlite3

source = sqlite3.connect("/var/lib/lums/lums.db")
target = sqlite3.connect("/backup/lums.db.backup-deployment")

with target:
    source.backup(target)

target.close()
source.close()

print("SQLite backup completed")
'
```

Protect it:

```bash
sudo chmod 600 \
    /var/backups/lums/lums.db.backup-deployment
```

Verify:

```bash
sudo sqlite3 \
    /var/backups/lums/lums.db.backup-deployment \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

---

# 69. Container Deployment

Build:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Verify the image:

```bash
sudo docker image inspect \
    lums:latest
```

Stop:

```bash
sudo docker stop lums
```

Remove only the container:

```bash
sudo docker rm lums
```

Recreate using the hardened production configuration:

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

Verify:

```bash
sudo docker ps --filter name=^/lums$
```

View logs:

```bash
sudo docker logs --tail 100 lums
```

---

# 70. Important Deployment Rule

Normal deployment must never remove:

```text
lums-data
```

Safe normal deployment:

```text
Stop container
Remove container
Create new container
Reuse volume
```

Destructive operation:

```bash
sudo docker volume rm lums-data
```

Do not execute this unless the database is intentionally being destroyed and a verified backup exists.

The same principle applies to secret files and TLS configuration.

Do not regenerate or replace secrets merely because the container is being recreated.

---

# 71. Post-Deployment Validation

Check the container:

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Check hardening:

```bash
sudo docker inspect \
    --format \
    'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{json .HostConfig.CapDrop}} Privileged={{.HostConfig.Privileged}}' \
    lums
```

Expected:

```text
User=lums
ReadonlyRootfs=true
CapDrop=["ALL"]
Privileged=false
```

Check secret handling:

```bash
sudo docker inspect lums \
    --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | grep '^LUMS_SECRET_KEY=' \
    || echo 'LUMS_SECRET_KEY absent'
```

```bash
sudo docker inspect lums \
    --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | grep '^LUMS_SECRET_KEY_FILE='
```

Expected:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

Test the local application:

```bash
curl -I \
    http://127.0.0.1:5050/
```

Check Nginx:

```bash
sudo nginx -t
```

Test HTTPS:

```bash
curl -k -I \
    https://<LUMS_SERVER_HOST>/
```

Run the agent:

```bash
sudo systemctl start lums-agent.service
```

Check agent logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 50 \
    --no-pager
```

Check watcher:

```bash
sudo systemctl start \
    lums-execution-watcher.service
```

Finally verify database integrity:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3
db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check;").fetchone()[0])
db.close()
'
```

Expected:

```text
ok
```

---

# 72. Security Rules

Never commit:

```text
Real client tokens
Administrator passwords
TLS private keys
Production databases
Database backups
/etc/default/lums-agent
Private secret files
Private certificates
Session secrets
```

The file:

```text
/etc/lums/docker/lums.env
```

must also remain outside Git when it contains sensitive or deployment-specific configuration.

Never publish:

```text
Client tokens
Passwords
Private keys
Production database contents
Authentication secrets
Flask secret values
```

Use placeholders:

```text
<LUMS_SERVER_IP>
<LUMS_SERVER_HOST>
<CLIENT_IP>
<CLIENT_TOKEN>
<ADMIN_PASSWORD>
<JOB_ID>
<PACKAGE>
```

---

# 73. Backup Strategy

A complete recovery strategy requires more than Git.

Important data includes:

```text
Application source
SQLite database
Runtime configuration
Nginx configuration
TLS certificate
TLS private key
Agent configuration
CA certificate
Flask secret
```

Git contains source code and documentation.

Git does not contain:

```text
Database state
Client tokens
Server secrets
TLS private keys
Runtime configuration
Agent credentials
```

Therefore:

```text
Git backup
    +
Configuration backup
    +
Secret backup
    +
Database backup
    =
Complete recovery capability
```

Secret backups must be protected separately from normal application backups.

---

# 74. Recovery Strategy

A basic recovery sequence:

```text
1. Restore operating system
2. Install Docker
3. Install Nginx
4. Restore repository
5. Restore runtime configuration
6. Restore Flask secret
7. Restore TLS configuration
8. Restore or create lums-data
9. Build Docker image
10. Start hardened LUMS container
11. Configure Nginx
12. Test HTTPS
13. Test administrator authentication
14. Test client authentication
15. Test agent
16. Test execution watcher
17. Test update functionality
```

Recovery should be tested against a known backup.

A complete production restore test remains a separate validation activity and must not be assumed merely because backups have passed an integrity check.

---

# 75. Development vs Production

LUMS is suitable for:

* Laboratories
* Test environments
* Development environments
* Small infrastructure projects

The current deployment already includes several production-oriented controls:

* Gunicorn
* Non-root container execution
* Read-only root filesystem
* Dropped Linux capabilities
* Restricted localhost port binding
* File-based secret handling
* HTTPS
* Security headers
* Client authentication
* Client token rotation
* CSRF protection
* Audit logging
* SQLite-aware backups
* Running-job recovery

A larger production deployment should additionally consider:

* TLS certificate lifecycle
* Tested backup restoration
* Monitoring
* Log rotation
* Access control
* Firewall rules
* Resource limits
* Vulnerability management
* Operating system updates
* Secure secret storage
* Package-manager coordination
* Automated security testing
* Formal recovery procedures

The current laboratory deployment should not automatically be considered equivalent to a fully managed enterprise production environment.

---

# 76. Current Security and Hardening State

The following controls are currently implemented and verified in the production deployment:

```text
✓ Gunicorn WSGI serving
✓ Non-root container
✓ UID/GID 10001
✓ Read-only root filesystem
✓ ALL Linux capabilities dropped
✓ Privileged mode disabled
✓ Restricted temporary filesystem
✓ Persistent Docker volume
✓ Secret-file based Flask secret
✓ Read-only secret mount
✓ Flask secret rotation
✓ HTTPS / TLS
✓ Security headers
✓ CSRF protection
✓ Argon2 administrator passwords
✓ Client Bearer authentication
✓ Client-specific authorization
✓ Client token rotation
✓ Token invalidation after rotation
✓ Token rotation audit logging
✓ Running-job recovery
✓ Atomic job claiming
✓ SQLite integrity verification
✓ SQLite-aware database backups
```

These controls were introduced incrementally and validated through controlled testing.

---

# 77. Current Limitations

LUMS is an active development project.

Current limitations and future hardening areas include:

```text
Resource limits
Expanded authorization controls
Extended audit coverage
Automated backup handling
Full backup / restore validation
Automated security tests
Advanced job scheduling
Client grouping
Repository management
Package deployment workflows
Monitoring integration
Desktop-specific idle providers
APT/dpkg collision handling
```

The following are **not** current open hardening gaps anymore:

```text
Production WSGI serving
Container non-root execution
Read-only container root filesystem
Capability dropping
File-based Flask secret handling
Flask secret rotation
Client token rotation
Running-job recovery
```

---

# 78. Future Development

Potential future features include:

```text
Client enable / disable
Client token revocation
Automatic client enrollment
Agent update management
Scheduled jobs
Update approval workflows
Client groups
Repository management
Package deployment
Reporting
Dashboard statistics
Role-based access control
Enhanced audit logging
Monitoring integration
APT/dpkg coordination
Maintenance windows
Execution notifications
Resource limits
Automated security tests
Full backup / restore testing
```

Features should be implemented incrementally and validated through controlled tests.

Security-sensitive changes should be tested in an isolated environment before production deployment.

---

# 79. Operational Philosophy

LUMS is not intended to become an unnecessarily complicated enterprise platform.

The goal is:

```text
Linux
   +
Central Management
   +
Security
   +
Transparency
   +
Documentation
```

The administrator should be able to answer:

```text
What changed?
       │
       ▼
Where did it change?
       │
       ▼
Which client was affected?
       │
       ▼
What did the client execute?
       │
       ▼
What result was reported?
```

The same principle applies to security:

```text
What changed?
       │
       ▼
Who changed it?
       │
       ▼
Which client or job was affected?
       │
       ▼
What was recorded?
       │
       ▼
Can the change be verified?
```

---

# 80. Source / Image / Runtime Separation

The LUMS deployment intentionally separates source code, images, runtime state and secrets.

```text
Git source
    ≠
Docker image
    ≠
Running container
    ≠
Persistent database
    ≠
Secret configuration
```

| Component             | Location                        |
| --------------------- | ------------------------------- |
| Git source            | `/opt/lums-public`              |
| Docker image          | `lums:latest`                   |
| Running container     | `lums`                          |
| Persistent database   | Docker volume `lums-data`       |
| Database path         | `/var/lib/lums/lums.db`         |
| Flask secret          | `/etc/lums/secrets/lums_secret` |
| Container secret      | `/run/secrets/lums_secret`      |
| Runtime configuration | `/etc/lums/docker/lums.env`     |
| Agent configuration   | `/etc/default/lums-agent`       |
| TLS configuration     | `/etc/lums/tls/`                |
| Nginx configuration   | `/etc/nginx/`                   |

This separation prevents frontend or backend deployment from accidentally replacing persistent application data or secrets.

---

# 81. Quick Reference

## Docker

```bash
sudo docker ps --filter name=^/lums$
```

```bash
sudo docker logs --tail 100 lums
```

```bash
sudo docker restart lums
```

```bash
sudo docker inspect lums
```

```bash
sudo docker volume inspect lums-data
```

```bash
sudo docker port lums
```

Hardening:

```bash
sudo docker inspect \
    --format \
    'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{json .HostConfig.CapDrop}} Privileged={{.HostConfig.Privileged}}' \
    lums
```

## Nginx

```bash
sudo nginx -t
```

```bash
sudo systemctl reload nginx
```

```bash
sudo systemctl status nginx --no-pager
```

## API

```bash
curl -k https://<LUMS_SERVER_HOST>/api/health
```

## Agent

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

```bash
sudo systemctl start lums-agent.service
```

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

## Execution Watcher

```bash
sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager
```

```bash
sudo systemctl start \
    lums-execution-watcher.service
```

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
```

## Database

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check;").fetchone()[0])
db.close()
'
```

Expected:

```text
ok
```

---

# 82. Final Deployment Checklist

Before considering a LUMS deployment complete:

* [ ] Git working tree is clean
* [ ] Repository is synchronized
* [ ] `git diff --check` passes
* [ ] Python syntax checks pass
* [ ] Docker image builds successfully
* [ ] `lums` container is running
* [ ] Container runs as non-root user
* [ ] Container UID is 10001
* [ ] Container root filesystem is read-only
* [ ] All Linux capabilities are dropped
* [ ] Container is not privileged
* [ ] `/tmp` uses the configured tmpfs
* [ ] `lums-data` volume exists
* [ ] Database is persistent
* [ ] Application is bound to `127.0.0.1:5050`
* [ ] Flask port `5000` is not directly exposed
* [ ] Gunicorn is running
* [ ] Nginx configuration passes
* [ ] HTTPS works
* [ ] TLS certificate contains the correct SAN
* [ ] TLS private key permissions are restricted
* [ ] Runtime configuration permissions are restricted
* [ ] Flask secret is stored outside the image
* [ ] Flask secret is mounted read-only
* [ ] `LUMS_SECRET_KEY` is absent from the container environment
* [ ] `LUMS_SECRET_KEY_FILE` points to the secret file
* [ ] `/api/health` responds successfully
* [ ] Administrator authentication works
* [ ] Client authentication works
* [ ] Client authorization works
* [ ] Client token rotation works
* [ ] Old client tokens become invalid after rotation
* [ ] Token rotation is recorded in the audit log
* [ ] Agent CA certificate is available
* [ ] Agent token configuration is valid
* [ ] Reporting timer is active
* [ ] Execution watcher timer is active
* [ ] Agent service executes successfully
* [ ] Client reports reach the server
* [ ] Client inventory is updated
* [ ] Idle detection works
* [ ] Update jobs can be created
* [ ] Update jobs can be claimed atomically
* [ ] Running-job recovery works
* [ ] Update results can be submitted
* [ ] Database integrity check returns `ok`
* [ ] Database backup exists
* [ ] Backup integrity has been checked
* [ ] No secrets are present in Git
* [ ] Simulation mode is disabled outside testing
* [ ] Documentation reflects the current deployment

---

# 83. Project

**LUMS**

Linux Update Management Server

Repository:

https://github.com/NovaForgeCtrl/LUMS

Maintained by:

**NovaForgeCtrl**

> **LUMS — Linux Update Management without the noise.**
>
> **Centralize the management. Keep execution controlled.**
>
> **Know what changed. Know where it happened.**
>
> **One LUMS. Same Backend. Controlled Execution.**

---

## Status

LUMS is an active development project.

The architecture, API, database schema and deployment model may evolve as development continues.

The current documented production state includes:

```text
One LUMS
    │
    ├── Nginx / HTTPS
    │
    ├── Hardened Docker container
    │      ├── non-root
    │      ├── read-only root filesystem
    │      ├── CapDrop=ALL
    │      └── Privileged=false
    │
    ├── Gunicorn / Flask
    │
    ├── SQLite / lums-data
    │
    ├── File-based Flask secret
    │
    ├── Client Bearer authentication
    │
    ├── Client token rotation
    │
    ├── Running-job recovery
    │
    └── Controlled update execution
```

Always review the current source code and configuration examples before deploying a new version.

> **Linux Update Management without the noise.**
>
> **One LUMS. Many clients. Same backend. Controlled execution.**
