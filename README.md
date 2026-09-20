
# LUMS

## Linux Update Management Server

> **Linux Update Management without the noise.**

LUMS is a lightweight Linux update management platform designed for small labs, test environments and infrastructure projects.

It provides centralized management for:

- Linux client inventory
- Update information
- Installed package information
- Client authentication
- Update jobs
- Agent communication
- Idle-aware execution
- Administrative auditing
- Controlled update execution

LUMS follows a documentation-first approach with a focus on:

- Simple architecture
- Transparent operation
- Central client management
- Secure agent authentication
- Minimal dependencies
- Auditable communication
- Controlled execution
- Easy deployment

---

# 1. Project Overview

LUMS consists of a central management server and Linux agents.

The server manages clients, inventory and update jobs.

The agent collects information, determines local idle state and executes authorized update jobs when the configured conditions are met.

```text
                    ┌─────────────────────────┐
                    │          LUMS           │
                    │     Management Server   │
                    │                         │
                    │   Flask + SQLite        │
                    │   Docker                │
                    └────────────┬────────────┘
                                 │
                         HTTP localhost
                                 │
                          127.0.0.1:5050
                                 │
                    ┌────────────▼────────────┐
                    │         Nginx           │
                    │      HTTPS / TLS        │
                    └────────────┬────────────┘
                                 │
                              HTTPS :443
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
        ┌──────────┐       ┌──────────┐       ┌──────────┐
        │ Client 1 │       │ Client 2 │       │ Client N │
        │  Agent   │       │  Agent   │       │  Agent   │
        └──────────┘       └──────────┘       └──────────┘
```

---

# 2. Current Feature Set

The current implementation includes:

- Flask-based management server
- SQLite persistence
- Docker deployment
- Nginx reverse proxy
- HTTPS/TLS communication
- Administrator authentication
- CSRF protection
- Security headers
- Client-specific Bearer tokens
- SHA-256 token digest storage
- Client inventory
- Installed package inventory
- Available update inventory
- Update job creation
- Package validation
- Atomic job claiming
- Running-job recovery
- Update result reporting
- Idle-state detection
- Idle-aware job execution
- Execution Watcher
- Simulation mode for safe end-to-end testing
- Audit logging

The project is actively developed. The API, database schema and deployment model may evolve.

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
┌───────────────┐
│ Docker        │
│ Container     │
│ "lums"        │
│               │
│ Flask :5000   │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Docker Volume │
│  lums-data    │
│               │
│ /var/lib/lums │
└───────┬───────┘
        │
        ▼
     lums.db
```

The Flask application is bound to localhost on the host:

```text
127.0.0.1:5050
```

The application is not intended to be directly exposed to the network.

Nginx provides the external HTTPS endpoint.

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
Job claim
        │
        ▼
Update execution
        │
        ▼
Result reporting
```

Reporting and job execution are intentionally separated.

The reporting timer does not need to execute an update job directly.

---

# 5. Current Deployment

The current laboratory deployment uses:

```text
Repository:
    /opt/lums-public

Server address:
    SERVER_IP

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

Server environment:
    /etc/lums/docker/lums.env

Database:
    /var/lib/lums/lums.db

TLS certificate:
    /etc/nginx/ssl/lums/lums.crt

TLS private key:
    /etc/nginx/ssl/lums/lums.key
```

Replace `SERVER_IP` with the actual server address in local documentation.

Never publish real internal IP addresses, credentials or private keys unnecessarily.

---

# 6. Repository Structure

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
│   │   └── style.css
│   │
│   └── templates/
│       ├── client.html
│       ├── index.html
│       └── login.html
│
├── Dockerfile
├── .dockerignore
├── LICENSE
└── README.md
```

Additional files may be added as development continues.

---

# 7. Technology Stack

| Component | Technology |
|---|---|
| Backend | Python / Flask |
| Database | SQLite |
| Containerization | Docker |
| Reverse proxy | Nginx |
| Transport | HTTPS / TLS |
| Administrator authentication | Argon2 |
| Client authentication | Bearer tokens |
| Frontend | HTML / CSS / JavaScript |
| Agent | Python |
| Scheduling | systemd timers |
| Package management | APT / dpkg |
| Repository | Git |

LUMS intentionally avoids unnecessary infrastructure dependencies.

---

# 8. Design Principles

## Understandable architecture

The server architecture remains intentionally small:

```text
Nginx
   ↓
Docker
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
Job Claim
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

---

# 9. Server Requirements

A typical laboratory deployment requires:

- Linux
- Docker
- Nginx
- HTTPS certificate
- Network connectivity
- Sufficient storage

A practical starting point:

```text
2 CPU cores
4 GB RAM
20+ GB storage
```

Actual requirements depend on:

- Number of clients
- Inventory size
- Database growth
- Logging
- Update frequency
- Future features

---

# 10. Agent Requirements

The LUMS agent requires:

- Linux
- Python 3
- systemd
- APT
- Network connectivity
- Valid client token
- LUMS CA certificate when using a private CA

The agent is currently designed primarily for Linux server, terminal and SSH-oriented environments.

Desktop-specific idle detection may require an additional provider in the future.

---

# 11. Installation Overview

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
5. Configure environment
        │
        ▼
6. Start container
        │
        ▼
7. Configure Nginx / HTTPS
        │
        ▼
8. Open dashboard
        │
        ▼
9. Create client
        │
        ▼
10. Install agent
        │
        ▼
11. Configure token and CA
        │
        ▼
12. Send first report
        │
        ▼
13. Enable execution watcher
```

---

# 12. Docker Build

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

---

# 13. Persistent Docker Volume

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

# 14. Server Environment

The server environment is stored outside Git:

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

The file may contain sensitive configuration.

It must never be committed to the repository.

---

# 15. Starting the Container

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
```

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

# 16. Nginx and HTTPS

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
Docker / Flask
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

# 17. TLS Verification

The agent should verify the server certificate.

Example CA file:

```text
/opt/lums-agent/lums-ca.crt
```

Diagnostic test:

```bash
curl -k https://SERVER_IP/api/health
```

The `-k` option disables certificate verification and should only be used for troubleshooting.

It must not become the normal security configuration.

Inspect the certificate:

```bash
sudo openssl x509 \
    -in /etc/nginx/ssl/lums/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

Inspect SAN:

```bash
sudo openssl x509 \
    -in /etc/nginx/ssl/lums/lums.crt \
    -noout \
    -ext subjectAltName
```

---

# 18. API Health Check

The health endpoint is:

```text
/api/health
```

Test through HTTPS:

```bash
curl -k https://SERVER_IP/api/health
```

This verifies the path:

```text
Nginx
   ↓
Docker
   ↓
Flask
```

---

# 19. Administrator Authentication

The web interface requires administrator authentication.

The application includes:

- Password hashing using Argon2
- Login and logout
- Session handling
- CSRF protection
- Security headers
- Audit logging

Administrator passwords and session secrets must never be committed to Git.

---

# 20. Client Authentication

Each client receives an individual Bearer token.

The agent sends:

```http
Authorization: Bearer <CLIENT_TOKEN>
```

The server stores a SHA-256 hexadecimal digest of the token rather than the plaintext token.

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

- README files
- Screenshots
- Git commits
- Issue reports
- Public documentation

Use:

```text
<CLIENT_TOKEN>
```

for examples.

---

# 21. Agent Configuration

Example:

```text
LUMS_BASE=https://lums.example.internal
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

---

# 22. Agent Installation

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

# 23. Agent Service

The reporting service uses:

```ini
Type=oneshot
```

The agent performs one reporting cycle and exits.

This means the service may show:

```text
inactive (dead)
```

after a successful execution.

This is normal for a oneshot service.

The timer provides periodic execution.

---

# 24. Agent Timer

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

# 25. Execution Watcher

The execution watcher is responsible for:

1. Authenticating the client
2. Recovering an already-running job
3. Looking up pending jobs
4. Checking local idle state
5. Waiting until the idle threshold is reached
6. Atomically claiming a job
7. Executing the claimed job
8. Reporting the result

Current watcher version:

```text
1.2.1
```

The watcher is executed independently of the reporting service.

---

# 26. Execution Watcher Timer

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

The current laboratory timer runs approximately every 30 seconds.

---

# 27. Idle Detection

The agent checks local activity before executing an update job.

The current server and SSH-oriented implementation uses:

```text
w -h
```

The idle threshold is currently:

```text
300 seconds
```

Equivalent to:

```text
5 minutes
```

The agent supports idle values such as:

```text
0.00s
5.00s
30:16
1:02:03
2days
2days,01:15
1:49m
```

The parser handles hours and minutes in values such as:

```text
1:49m
```

The shortest relevant idle duration is used.

---

# 28. Idle Status

The agent returns information similar to:

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

# 29. Job Lifecycle

The update job lifecycle is divided into several stages:

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
   └── failed
```

The client determines whether the local idle threshold has been reached.

The server manages the job state.

The agent must claim a job atomically before execution.

---

# 30. Atomic Job Claiming

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

# 31. Running-Job Recovery

The watcher checks for an already-running job before looking for new pending jobs.

This supports recovery after:

- Service interruption
- SSH disconnection
- Watcher restart
- System restart
- Partial execution lifecycle interruption

A detected running job is resumed without claiming it again.

```text
Running Job Detected
        │
        ▼
No New Claim
        │
        ▼
Resume Execution
```

---

# 32. Update Job Creation

Update jobs are created through the management interface.

The server validates that requested packages exist in the available update inventory for the selected client.

Invalid or unknown packages are rejected.

The package list is normalized and duplicate package names are removed.

The job is then stored in the database with its package records.

---

# 33. Update Execution

The agent executes packages locally using the operating system's package management infrastructure.

APT remains responsible for:

- Repository handling
- Dependency resolution
- Package signatures
- Package installation
- dpkg interaction

LUMS does not replace APT.

The current execution implementation reports individual package results and an overall job status.

Possible overall results include:

```text
success
partial
failed
```

---

# 34. Execution Results

The agent reports the result through:

```text
POST /api/update-jobs/<job_id>/result
```

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

- The job belongs to the authenticated client
- The job is currently running
- The submitted result has a valid status

A result cannot be submitted for a job that is no longer running.

---

# 35. Simulation Mode

LUMS includes a simulation mode for safe end-to-end testing.

Simulation mode:

- Does not execute real APT updates
- Does not modify installed packages
- Simulates successful package execution
- Exercises the job lifecycle
- Tests watcher behavior
- Tests result reporting
- Tests UI status updates

The simulation mode is controlled through:

```text
LUMS_SIMULATE_UPDATES
```

Simulation mode must not be unintentionally enabled in a production deployment.

After testing, verify the systemd service configuration.

---

# 36. Simulation Safety

Simulation mode is intended for:

- Development
- Testing
- End-to-end validation
- UI verification
- Job lifecycle testing

A successful simulation does not prove that real package-manager collisions are fully handled.

Real APT/dpkg coordination requires additional safeguards.

---

# 37. Package Manager Safety

The current project identifies package-manager coordination as an important future hardening area.

Potential safeguards include:

- LUMS execution lock
- Detection of active APT processes
- Detection of dpkg lock usage
- Wait-and-retry behavior
- Execution timeout
- Graceful deferral
- Explicit `waiting_for_package_manager` state
- No forced removal of lock files

LUMS must never delete foreign APT or dpkg lock files.

Important limitation:

A custom LUMS lock does not automatically coordinate with arbitrary manually executed `apt` or `dpkg` commands.

Full collision avoidance requires coordination with the package manager and operational policy.

---

# 38. Reboot Handling

LUMS does not automatically reboot clients.

A reboot requirement may be detected using:

```bash
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot required"
```

A reboot remains an administrative decision.

---

# 39. Database

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

- Clients
- Installed packages
- Available updates
- Update jobs
- Package job results
- Authentication-related client data
- Audit information

The schema may evolve over time.

---

# 40. Database Integrity

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

1. Stop unnecessary database changes
2. Preserve the current database
3. Create a backup
4. Review application logs
5. Review recent changes
6. Identify a valid backup
7. Restore only after verification

Never delete the Docker volume as a first troubleshooting step.

---

# 41. Database Backup

Create the backup directory:

```bash
sudo install -d -m 700 /var/backups/lums
```

Create a SQLite-aware backup:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

source = sqlite3.connect("/var/lib/lums/lums.db")
backup = sqlite3.connect("/tmp/lums-backup.db")

source.backup(backup)

backup.close()
source.close()
'
```

Copy the backup to the host:

```bash
sudo docker cp \
    lums:/tmp/lums-backup.db \
    "/var/backups/lums/lums-$(date +%F-%H%M%S).db"
```

Remove the temporary file:

```bash
sudo docker exec \
    lums \
    rm -f /tmp/lums-backup.db
```

Backups must not be stored inside the Git repository.

---

# 42. API Overview

Important API areas include:

```text
Client management
Client reporting
Client authentication
Client inventory
Update inventory
Update jobs
Job claiming
Running-job lookup
Job result reporting
```

Examples:

```text
POST /api/report
GET  /api/clients
POST /api/clients/<id>/update-jobs
GET  /api/clients/<id>/update-jobs/pending
GET  /api/clients/<id>/update-jobs/running
POST /api/clients/<id>/update-jobs/<job_id>/claim
POST /api/update-jobs/<job_id>/result
```

The exact endpoint set may evolve.

Always consult the current source code before integrating against the API.

---

# 43. Authentication and Authorization

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

---

# 44. CSRF Protection

Administrative state-changing operations use CSRF protection.

Examples:

```text
POST /api/clients
DELETE /api/clients/<id>
```

The dashboard obtains and sends the required CSRF token.

Client reporting uses Bearer token authentication instead.

---

# 45. Audit Logging

The application includes an audit mechanism for administrative activity.

Potential audit events include:

- Authentication events
- Client creation
- Client deletion
- Administrative changes
- Update job operations

Audit information supports:

- Troubleshooting
- Change tracking
- Security investigations
- Administrative review

---

# 46. Troubleshooting Strategy

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
Docker / Flask
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

---

# 47. Docker Diagnostics

```bash
sudo docker ps --filter name=^/lums$
```

```bash
sudo docker ps -a
```

```bash
sudo docker logs --tail 100 lums
```

```bash
sudo docker logs -f lums
```

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

# 48. Nginx Diagnostics

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

---

# 49. Backend Diagnostics

Test the local backend:

```bash
curl -I http://127.0.0.1:5050/
```

If this fails, investigate:

- Docker container
- Flask application
- Port mapping
- Environment configuration
- Container logs

before investigating TLS or the browser.

---

# 50. Agent Diagnostics

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

---

# 51. Watcher Diagnostics

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

---

# 52. Agent Configuration Diagnostics

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

# 53. Authentication Problems

If the server returns:

```text
401 Unauthorized
```

check:

1. Client token
2. Stored token digest
3. Client enabled state
4. Authorization header
5. LUMS_BASE
6. Agent environment configuration

Do not disable authentication to solve an authentication problem.

---

# 54. TLS Problems

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

---

# 55. APT Diagnostics

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
apt-cache policy <package>
```

Check installed package:

```bash
dpkg -l <package>
```

If APT or dpkg is already broken, resolve the local package-manager issue before investigating LUMS.

Never remove package-manager lock files as a first troubleshooting action.

---

# 56. Git Workflow

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
git add <files>
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

# 57. Git Identity

The repository uses:

```text
Name:
    NovaForgeCtrl

Email:
    232026481+NovaForgeCtrl@users.noreply.github.com
```

Check:

```bash
git config user.name
git config user.email
```

Configure locally:

```bash
git config user.name \
    "NovaForgeCtrl"

git config user.email \
    "232026481+NovaForgeCtrl@users.noreply.github.com"
```

---

# 58. Deployment Workflow

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
Stop container
    │
    ▼
Remove container
    │
    ▼
Reuse lums-data
    │
    ▼
Create new container
    │
    ▼
Health check
    │
    ▼
Agent test
    │
    ▼
Watcher test
```

---

# 59. Pre-Deployment Validation

```bash
cd /opt/lums-public

git status
```

```bash
git diff --check
```

```bash
python3 -m py_compile \
    server/app.py \
    server/init_db.py \
    agent/agent.py \
    agent/watcher.py
```

Do not deploy if validation fails.

---

# 60. Container Deployment

Build:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Create a database backup before replacing the container.

Stop:

```bash
sudo docker stop lums
```

Remove only the container:

```bash
sudo docker rm lums
```

Recreate:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
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

# 61. Important Deployment Rule

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

---

# 62. Post-Deployment Validation

Check the container:

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Test the local application:

```bash
curl -I http://127.0.0.1:5050/
```

Check Nginx:

```bash
sudo nginx -t
```

Test HTTPS:

```bash
curl -k -I https://SERVER_IP/
```

Test API:

```bash
curl -k https://SERVER_IP/api/health
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

---

# 63. Security Rules

Never commit:

```text
Real client tokens
Administrator passwords
TLS private keys
Production databases
Database backups
/etc/default/lums-agent
/etc/lums/docker/lums.env
Private certificates
Session secrets
```

Never publish:

```text
Client tokens
Passwords
Private keys
Production database contents
Authentication secrets
```

Use placeholders:

```text
SERVER_IP
CLIENT_IP
CLIENT_TOKEN
ADMIN_PASSWORD
```

---

# 64. Backup Strategy

A complete recovery strategy requires more than Git.

Important data includes:

```text
Application source
SQLite database
Docker environment
Nginx configuration
TLS certificate
TLS private key
Agent configuration
CA certificate
```

Git contains source code and documentation.

Git does not contain:

```text
Database state
Client tokens
Server secrets
TLS private keys
Runtime configuration
```

Therefore:

```text
Git backup
    +
Configuration backup
    +
Database backup
    =
Complete recovery capability
```

---

# 65. Recovery Strategy

A basic recovery sequence:

```text
1. Restore operating system
2. Install Docker
3. Install Nginx
4. Restore repository
5. Restore environment configuration
6. Restore TLS configuration
7. Restore or create lums-data
8. Build Docker image
9. Start LUMS
10. Configure Nginx
11. Test HTTPS
12. Test administrator authentication
13. Test client authentication
14. Test agent
15. Test execution watcher
16. Test update functionality
```

Recovery should be tested against a known backup.

---

# 66. Development vs Production

LUMS is suitable for:

- Laboratories
- Test environments
- Development environments
- Small infrastructure projects

A production deployment should additionally consider:

- TLS certificate lifecycle
- Backups
- Monitoring
- Log rotation
- Access control
- Firewall rules
- Least privilege
- Database protection
- Token rotation
- Vulnerability management
- Operating system updates
- Secure secret storage
- Container hardening
- Resource limits
- Production-grade WSGI serving
- Package-manager coordination

The current laboratory deployment must not automatically be considered production hardened.

---

# 67. Current Limitations

LUMS is an active development project.

Current limitations and future hardening areas include:

```text
Production WSGI server
Container hardening
Resource limits
Token rotation
Expanded authorization controls
Extended audit coverage
Automated backup handling
Advanced job scheduling
Client grouping
Repository management
Package deployment workflows
Monitoring integration
Desktop-specific idle providers
APT/dpkg collision handling
```

The current execution watcher uses local idle information and controlled job claiming.

Package-manager collision handling is not yet fully implemented.

---

# 68. Future Development

Potential future features include:

```text
Token rotation
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
```

Features should be implemented incrementally and validated through controlled tests.

---

# 69. Operational Philosophy

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

---

# 70. Quick Reference

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
curl -k https://SERVER_IP/api/health
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

---

# 71. Final Deployment Checklist

Before considering a LUMS deployment complete:

- [ ] Git working tree is clean
- [ ] Repository is synchronized
- [ ] `git diff --check` passes
- [ ] Python syntax checks pass
- [ ] Docker image builds successfully
- [ ] `lums` container is running
- [ ] `lums-data` volume exists
- [ ] Database is persistent
- [ ] Application is bound to `127.0.0.1:5050`
- [ ] Flask port `5000` is not directly exposed
- [ ] Nginx configuration passes
- [ ] HTTPS works
- [ ] TLS certificate contains the correct SAN
- [ ] TLS private key permissions are restricted
- [ ] Server environment permissions are restricted
- [ ] `/api/health` responds successfully
- [ ] Administrator authentication works
- [ ] Client authentication works
- [ ] Client authorization works
- [ ] Agent CA certificate is available
- [ ] Agent token configuration is valid
- [ ] Reporting timer is active
- [ ] Execution watcher timer is active
- [ ] Agent service executes successfully
- [ ] Client reports reach the server
- [ ] Client inventory is updated
- [ ] Idle detection works
- [ ] Update jobs can be created
- [ ] Update jobs can be claimed atomically
- [ ] Running-job recovery works
- [ ] Update results can be submitted
- [ ] Database integrity check returns `ok`
- [ ] Database backup exists
- [ ] No secrets are present in Git
- [ ] Simulation mode is disabled outside testing
- [ ] Documentation reflects the current deployment

---

# 72. Project

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

---

## Status

LUMS is an active development project.

The architecture, API, database schema and deployment model may evolve as development continues.

Always review the current source code and configuration examples before deploying a new version.
