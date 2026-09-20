````markdown
# LUMS

## Linux Update Management Server

> **Linux Update Management without the noise.**

LUMS is a lightweight Linux update management platform designed for small labs, test environments and infrastructure projects.

It provides a central management server for:

- Linux client inventory
- update information
- package information
- client authentication
- update jobs
- agent communication
- administrative auditing

The project focuses on:

- simple architecture
- transparent operation
- central client management
- secure agent authentication
- minimal dependencies
- auditable communication
- controlled update execution
- easy deployment
- documentation-first administration

---

# 1. Project Overview

LUMS consists of two primary components:

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
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
              ┌──────────┐      ┌──────────┐      ┌──────────┐
              │ Client 1 │      │ Client 2 │      │ Client N │
              │  Agent   │      │  Agent   │      │  Agent   │
              └──────────┘      └──────────┘      └──────────┘
````

## Server

The LUMS server provides:

* Web dashboard
* administrator authentication
* client management
* client authentication
* client inventory
* update inventory
* package inventory
* update jobs
* audit logging
* API endpoints
* SQLite persistence

The current server deployment runs the Flask application inside a Docker container.

Nginx provides the external HTTPS endpoint and forwards requests to the local Docker binding.

## Agent

The LUMS agent runs on managed Linux systems and collects information such as:

* hostname
* IP address
* operating system
* kernel version
* architecture
* agent version
* available updates
* installed packages

The agent communicates with the LUMS server using HTTPS and a client-specific Bearer token.

---

# 2. Architecture

The current architecture is intentionally small:

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
                               │
                       ┌───────▼───────┐
                       │ Docker Volume │
                       │  lums-data    │
                       │               │
                       │ /var/lib/lums │
                       └───────┬───────┘
                               │
                               ▼
                           lums.db
```

The important security boundary is:

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
```

The Flask application is not directly exposed to the network.

---

# 3. Current Deployment

The current laboratory deployment uses:

```text
Server IP:
    ID Address

Repository:
    /opt/lums-public

Docker container:
    lums

Docker image:
    lums:latest

Docker volume:
    lums-data

Host application binding:
    127.0.0.1:5050

Container port:
    5000

HTTPS:
    443

Environment file:
    /etc/lums/docker/lums.env

Database inside container:
    /var/lib/lums/lums.db

TLS certificate:
    /etc/nginx/ssl/lums/lums.crt

TLS private key:
    /etc/nginx/ssl/lums/lums.key
```

The server can be accessed through:

```text
https://ID Address/
```

When deploying LUMS to another environment, replace the IP address with the appropriate server address.

---

# 4. Repository Structure

The repository contains the application source, agent, deployment files and documentation.

A typical current structure is:

```text
LUMS/
├── agent/
│   ├── agent.py
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

Additional files may be added as the project evolves.

---

# 5. Technology Stack

| Component                    | Technology              |
| ---------------------------- | ----------------------- |
| Backend                      | Python / Flask          |
| Database                     | SQLite                  |
| Containerization             | Docker                  |
| Reverse proxy                | Nginx                   |
| Transport                    | HTTPS / TLS             |
| Administrator authentication | Argon2                  |
| Client authentication        | Bearer Tokens           |
| Frontend                     | HTML / CSS / JavaScript |
| Agent                        | Python                  |
| Agent scheduling             | systemd timer           |
| Package management           | APT                     |
| Repository                   | Git                     |

LUMS intentionally avoids unnecessary infrastructure dependencies.

---

# 6. Design Principles

## Keep the architecture understandable

LUMS should remain understandable without requiring a large enterprise stack.

The core architecture is:

```text
Nginx
   ↓
Docker
   ↓
Flask
   ↓
SQLite
```

The client side remains similarly simple:

```text
systemd timer
   ↓
LUMS Agent
   ↓
HTTPS
   ↓
LUMS API
```

---

## Separate management and client communication

The administrator uses the web interface.

Linux clients communicate with the API.

Administrator path:

```text
Administrator
     │
     ▼
Web Browser
     │
     ▼
Nginx
     │
     ▼
Flask
     │
     ▼
SQLite
```

Client path:

```text
Linux Client
     │
     ▼
LUMS Agent
     │
     │ HTTPS + Bearer Token
     ▼
Nginx
     │
     ▼
Flask API
     │
     ▼
SQLite
```

---

## Keep persistent data outside the container image

The application itself is packaged into:

```text
lums:latest
```

Persistent runtime data is stored in:

```text
lums-data
```

This allows the application container to be recreated without deleting the database.

```text
Docker Image
    │
    ├── Application
    ├── Python
    └── Dependencies

Docker Volume
    │
    └── SQLite Database
```

---

## Store tokens safely

Client tokens are not stored in plaintext on the server.

The server stores a SHA-256 hexadecimal representation of the client token.

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

The original token is provided to the administrator during client creation and must then be configured on the client.

---

# 7. Server Requirements

A typical LUMS server requires:

* Linux
* Docker
* Nginx
* HTTPS certificate
* sufficient storage
* network connectivity

The Flask application and its Python dependencies run inside the Docker image.

A small laboratory deployment can run comfortably on a VM.

A practical starting point is:

```text
2 CPU cores
4 GB RAM
20+ GB storage
```

Actual requirements depend on:

* number of managed clients
* amount of inventory data
* database growth
* logging
* future features

---

# 8. Agent Requirements

The LUMS agent requires:

* Linux
* Python 3
* systemd
* APT
* network connectivity to the LUMS server
* a valid client token
* access to the LUMS CA certificate when using a private/internal CA

The agent collects system information using standard Linux tools and Python libraries.

---

# 9. Installation Overview

A typical installation consists of:

```text
1. Install Docker
        │
        ▼
2. Clone LUMS repository
        │
        ▼
3. Build Docker image
        │
        ▼
4. Create persistent Docker volume
        │
        ▼
5. Configure server environment
        │
        ▼
6. Start LUMS container
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
11. Configure token
        │
        ▼
12. Send first report
```

---

# 10. Server Source

Clone the repository:

```bash
git clone https://github.com/NovaForgeCtrl/LUMS.git
cd LUMS
```

For the current laboratory deployment:

```bash
cd /opt/lums-public
```

The server application is located under:

```text
server/
```

The Docker image packages the application and its required Python dependencies.

---

# 11. Docker Build

Build the current image:

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

Inspect the image:

```bash
sudo docker image inspect lums:latest
```

---

# 12. Persistent Docker Volume

Create the database volume if it does not already exist:

```bash
sudo docker volume create lums-data
```

Verify:

```bash
sudo docker volume inspect lums-data
```

The volume is mounted inside the container at:

```text
/var/lib/lums
```

The database is:

```text
/var/lib/lums/lums.db
```

The volume must survive application container recreation.

---

# 13. Server Environment

The server environment is stored outside Git:

```text
/etc/lums/docker/lums.env
```

The file is loaded into the container using:

```text
--env-file /etc/lums/docker/lums.env
```

The file should be protected:

```bash
sudo chown root:root \
    /etc/lums/docker/lums.env

sudo chmod 600 \
    /etc/lums/docker/lums.env
```

The environment file may contain sensitive configuration and must never be committed to the repository.

---

# 14. Starting the LUMS Container

The current container is started with:

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

Expected:

```text
lums    Up
```

---

# 15. Docker Runtime

The application listens inside the container on:

```text
5000
```

The host exposes it only on:

```text
127.0.0.1:5050
```

Therefore:

```text
127.0.0.1:5050
        │
        ▼
Docker
        │
        ▼
:5000
```

Port `5000` is not intended to be directly reachable from the network.

Check:

```bash
sudo docker port lums
```

Expected:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 16. Nginx

Nginx provides the external HTTPS endpoint.

The intended path is:

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

Check the configuration:

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

# 17. HTTPS

LUMS uses HTTPS for client communication.

The agent communicates with endpoints such as:

```text
https://<LUMS-SERVER>/api/report
```

The current laboratory endpoint is:

```text
https://ID Address/
```

The TLS certificate is:

```text
/etc/nginx/ssl/lums/lums.crt
```

The private key is:

```text
/etc/nginx/ssl/lums/lums.key
```

The private key must never be committed to Git.

---

# 18. TLS Verification

When a private CA is used, the CA certificate is provided to the agent.

Example:

```text
/opt/lums-agent/lums-ca.crt
```

The agent uses the configured CA file to verify the LUMS server certificate.

This is preferable to disabling certificate verification.

The following is acceptable for diagnostic testing:

```bash
curl -k https://ID Address/api/health
```

However, `-k` disables certificate verification and should not be used as the normal security model.

---

# 19. API Health Check

The LUMS API provides a health endpoint:

```text
/api/health
```

Test through HTTPS:

```bash
curl -k https://ID Address/api/health
```

The health endpoint can be used to verify that:

```text
Nginx
   ↓
Docker
   ↓
Flask
```

is operational.

---

# 20. Administrator Authentication

The web interface requires administrator authentication.

Passwords are handled using Argon2-based password hashing.

The application includes security mechanisms such as:

* login
* logout
* session handling
* CSRF protection
* security headers
* audit logging

Administrator credentials must never be stored in the repository.

---

# 21. Client Management

Clients are managed through the LUMS dashboard.

The current workflow keeps manual registration simple.

The administrator creates a client and receives a client-specific token.

The token is then configured on the Linux client.

The server associates the token with the client record.

---

# 22. Client Creation

A client registration contains the information required to establish client identity.

After creation, LUMS generates:

```text
Client ID
Client Token
```

The token is then configured on the managed Linux system.

The server does not require the administrator to manually enter every piece of system information.

The agent provides that information after the first successful report.

---

# 23. Automatic Client Information

After the agent connects successfully, the client record can contain:

```text
Hostname
IP address
Operating system
Kernel
Architecture
Agent version
Available updates
Installed packages
Last seen
```

Example:

```text
Hostname: client01
IP: 192.168.x.x
OS: Linux
Kernel: 6.x.x
Architecture: x86_64
Agent: 1.x.x
```

The values are supplied by the client agent.

---

# 24. Client Token

Each client receives an individual authentication token.

The token is sent as:

```http
Authorization: Bearer <CLIENT_TOKEN>
```

The server stores a SHA-256 hexadecimal digest rather than the plaintext token.

Conceptually:

```text
Client Token
     │
     ▼
SHA-256
     │
     ▼
Token Digest
     │
     ▼
Database
```

Real tokens must never be placed in:

```text
README.md
screenshots
Git commits
issue reports
documentation examples
```

Use:

```text
<CLIENT_TOKEN>
```

for examples.

---

# 25. Agent Configuration

The agent uses an environment configuration file.

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

The actual configuration is installed locally on the client:

```text
/etc/default/lums-agent
```

The real configuration must not be committed to Git.

---

# 26. Agent Installation

The agent source is:

```text
agent/agent.py
```

The installed agent is:

```text
/opt/lums-agent/agent.py
```

The CA certificate is:

```text
/opt/lums-agent/lums-ca.crt
```

The systemd service is:

```text
lums-agent.service
```

The timer is:

```text
lums-agent.timer
```

---

# 27. Agent Service

The service is intentionally configured as a:

```ini
Type=oneshot
```

The agent performs one execution and exits.

Conceptually:

```text
Timer
  │
  ▼
Agent Service
  │
  ▼
agent.py
  │
  ├── collect information
  ├── report to server
  ├── check jobs
  └── execute approved actions
  │
  ▼
Exit
```

A successful oneshot service may therefore show:

```text
inactive (dead)
```

after completion.

This is normal.

The timer is what provides periodic execution.

---

# 28. Agent Timer

The repository provides:

```text
agent/lums-agent.timer
```

The timer periodically starts:

```text
lums-agent.service
```

Enable it with:

```bash
sudo systemctl enable --now lums-agent.timer
```

Check:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

List the next execution:

```bash
systemctl list-timers --all | grep lums-agent
```

---

# 29. Manual Agent Execution

To run the installed agent through its normal systemd configuration:

```bash
sudo systemctl start lums-agent.service
```

Then inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

This is preferable to directly executing:

```bash
sudo python3 /opt/lums-agent/agent.py
```

because the systemd service loads:

```text
/etc/default/lums-agent
```

through its environment configuration.

---

# 30. Agent Data Collection

The agent collects information including:

```text
hostname
IP address
operating system
kernel
architecture
agent version
available updates
installed packages
```

The agent uses standard Linux tools and Python functionality.

The current agent version is defined in:

```python
AGENT_VERSION
```

---

# 31. Client Report

The agent submits its report through:

```text
POST /api/report
```

A report contains information similar to:

```json
{
    "hostname": "client01",
    "ip": "192.168.x.x",
    "os": "Linux",
    "kernel": "6.x.x",
    "architecture": "x86_64",
    "agent_version": "1.x.x",
    "updates": [],
    "packages": {}
}
```

The exact data depends on the client system.

---

# 32. Client Authentication

The `/api/report` endpoint requires client authentication.

The agent sends:

```http
Authorization: Bearer <CLIENT_TOKEN>
```

The server then:

```text
1. extracts the Bearer token
2. hashes the token
3. compares the digest with the stored value
4. identifies the client
5. checks the client state
6. accepts the report
7. updates the client information
```

This prevents unauthenticated systems from submitting arbitrary client reports.

---

# 33. Client Authorization

Authentication and authorization are separate concepts.

Authentication answers:

```text
"Who is this client?"
```

Authorization answers:

```text
"Is this client allowed to perform this operation?"
```

A valid token alone should not automatically grant unrestricted access.

Client-specific API operations must remain associated with the authenticated client identity.

---

# 34. Database

LUMS uses SQLite for its current persistent data store.

The database is located inside the Docker container at:

```text
/var/lib/lums/lums.db
```

The directory is backed by:

```text
lums-data
```

The database contains application state such as:

```text
clients
update information
package information
audit information
authentication-related client data
```

The schema may evolve as the project develops.

---

# 35. Database Persistence

The database is intentionally stored in a Docker volume.

```text
Container
    │
    ▼
/var/lib/lums
    │
    ▼
lums-data
    │
    ▼
SQLite
```

Recreating the container does not remove the database as long as:

```text
lums-data
```

is preserved.

Never remove the volume during a normal application deployment.

---

# 36. Database Integrity

The database can be checked using SQLite from inside the container:

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

A result other than `ok` requires investigation before continuing with normal administrative changes.

---

# 37. Database Backup

Backups should be created before:

* database migrations
* major application changes
* structural modifications
* recovery operations

A SQLite-aware backup can be created through the running container.

Example:

```bash
sudo install -d -m 700 /var/backups/lums
```

Create a temporary SQLite backup:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

source = sqlite3.connect("/var/lib/lums/lums.db")
backup = sqlite3.connect("/var/lib/lums/lums.backup.db")

source.backup(backup)

backup.close()
source.close()
'
```

Copy it to the host:

```bash
sudo docker cp \
    lums:/var/lib/lums/lums.backup.db \
    "/var/backups/lums/lums-$(date +%F_%H-%M-%S).db"
```

Remove the temporary file:

```bash
sudo docker exec \
    lums \
    rm -f /var/lib/lums/lums.backup.db
```

Backups must not be stored inside the Git repository.

---

# 38. Update Management

LUMS separates update management from update execution.

The architecture is:

```text
Administrator
     │
     ▼
LUMS Dashboard
     │
     ▼
Update Job
     │
     ▼
LUMS Server
     │
     ▼
LUMS Agent
     │
     ▼
APT
```

The server manages the desired operation.

The client performs the package operation locally.

---

# 39. APT

The LUMS agent uses the operating system's package management infrastructure.

APT remains responsible for:

* repository handling
* dependency resolution
* package signatures
* package installation
* dpkg interaction

LUMS does not replace APT.

If APT itself is broken, the client-side APT problem must be resolved separately.

---

# 40. Automatic Reboots

LUMS does not automatically reboot clients.

A reboot requirement can be checked using:

```bash
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot required"
```

A reboot remains an administrative decision.

---

# 41. API Overview

The application provides separate API areas for administrator and client operations.

Examples include:

```text
POST /api/clients
DELETE /api/clients/<id>
POST /api/report
GET /api/client/me
```

The exact endpoint set may evolve with the application.

Always consult the current source code when developing against the API.

---

# 42. Authentication Model

LUMS currently uses two authentication contexts.

## Administrator

Administrative access uses:

```text
HTTPS
   │
   ▼
Login
   │
   ▼
Session
   │
   ▼
CSRF protection
   │
   ▼
Administrative API
```

## Client

Client access uses:

```text
HTTPS
   │
   ▼
Bearer Token
   │
   ▼
Token Hash Verification
   │
   ▼
Client Authorization
   │
   ▼
Client API
```

The two authentication mechanisms serve different purposes.

---

# 43. CSRF Protection

Administrative state-changing operations use CSRF protection.

Examples include:

```text
POST /api/clients
DELETE /api/clients/<id>
```

The dashboard obtains the required CSRF token and sends it with applicable requests.

Client reporting uses Bearer token authentication instead.

---

# 44. Security Headers

LUMS applies security-related HTTP headers through its security implementation.

Nginx also forms part of the external security boundary and should be configured for:

* TLS
* secure request forwarding
* access logging
* error logging
* appropriate HTTP security headers

---

# 45. Audit Logging

Administrative actions are recorded through the application's audit mechanism.

Examples may include:

```text
authentication events
client creation
client deletion
administrative changes
```

Audit information can assist with:

* troubleshooting
* change tracking
* security investigations
* administrative review

---

# 46. Client Lifecycle

The intended client lifecycle is:

```text
                 ┌──────────────────┐
                 │ Client created   │
                 └────────┬─────────┘
                          │
                          ▼
                  Token generated
                          │
                          ▼
                   Agent configured
                          │
                          ▼
                    First report
                          │
                          ▼
                       Active
                          │
             ┌────────────┴────────────┐
             │                         │
             ▼                         ▼
          Disabled                  Deleted
             │                         │
             ▼                         ▼
          Inactive                 Removed
```

---

# 47. Removing Clients

Clients can be removed through the administrative interface.

Before removing a client, verify that it is no longer required.

When a client is removed, associated records may also be removed depending on the current application implementation.

---

# 48. Re-Adding a Client

If a client has been removed and must be registered again:

```text
1. Create a new client
2. Generate a new token
3. Configure the agent
4. Verify the CA certificate
5. Run the agent
6. Verify the first report
```

A new token should be used instead of reusing an old credential.

---

# 49. Troubleshooting

The most important LUMS troubleshooting rule is:

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

LUMS can be divided into:

```text
┌──────────────────────────┐
│       Web Browser        │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│       Nginx / HTTPS      │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│    Docker / Flask API    │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│         SQLite           │
└──────────────────────────┘

Client side:

┌──────────────────────────┐
│     systemd timer        │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│       LUMS Agent         │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│       HTTPS / Network    │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│        LUMS API          │
└──────────────────────────┘
```

Troubleshoot from the outside toward the inside.

---

# 50. Docker Diagnostics

Check the container:

```bash
sudo docker ps --filter name=^/lums$
```

Check all containers:

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

Inspect:

```bash
sudo docker inspect lums
```

Check the container state:

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

# 51. Nginx Diagnostics

Check:

```bash
sudo nginx -t
```

Check service:

```bash
sudo systemctl status nginx --no-pager
```

View recent logs:

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

# 52. Local Backend Test

The Docker application is bound to:

```text
127.0.0.1:5050
```

Test it locally:

```bash
curl -I http://127.0.0.1:5050/
```

If this fails, investigate:

```text
Docker
Flask
container logs
port mapping
environment configuration
```

before investigating TLS or the browser.

---

# 53. HTTPS Test

Test the complete HTTPS path:

```bash
curl -k -I https://ID Address/
```

Health endpoint:

```bash
curl -k https://ID Address/api/health
```

If the local backend works but HTTPS does not, investigate:

```text
Nginx
TLS certificate
TLS private key
Nginx upstream configuration
firewall
```

---

# 54. Agent Diagnostics

Check the timer:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

Run manually:

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

The oneshot service may show:

```text
inactive (dead)
```

after a successful execution.

Check the exit status:

```bash
sudo systemctl show \
    lums-agent.service \
    -p Result
```

Expected after a successful execution:

```text
Result=success
```

---

# 55. Agent Configuration Diagnostics

Check that the configuration exists:

```bash
sudo ls -l /etc/default/lums-agent
```

Inspect safely:

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

The expected configuration contains:

```text
LUMS_BASE
LUMS_TOKEN
LUMS_CA_FILE
```

---

# 56. Authentication Problems

If the server returns:

```text
401 Unauthorized
```

check:

```text
1. Client token
2. Stored token hash
3. Client enabled state
4. Authorization header
5. LUMS_BASE
6. Agent configuration
```

The client token must match the SHA-256 digest stored by the server.

Do not solve authentication problems by disabling authentication.

---

# 57. TLS Problems

If the agent cannot connect:

```text
Check LUMS_BASE
Check DNS / hostname
Check network connectivity
Check Nginx
Check certificate
Check CA file
Check certificate SAN
```

Inspect the server certificate:

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

Inspect the client CA:

```bash
sudo openssl x509 \
    -in /opt/lums-agent/lums-ca.crt \
    -noout \
    -subject \
    -dates
```

Do not permanently disable certificate verification.

---

# 58. Client Not Updating

If a client exists but information is not changing:

```text
1. Check lums-agent.timer
2. Run lums-agent.service manually
3. Check agent logs
4. Check LUMS_BASE
5. Check token
6. Check CA certificate
7. Check network
8. Check Docker logs
9. Check client state
```

The first successful report should populate or update fields such as:

```text
hostname
ip
os
kernel
architecture
agent_version
last_seen
```

---

# 59. APT Problems

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

If APT itself is broken, resolve the APT problem on the client before investigating the LUMS server.

---

# 60. Database Troubleshooting

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

If the result is not `ok`:

```text
1. Stop making unnecessary changes
2. Preserve the current database
3. Create a backup
4. Review Docker logs
5. Review recent changes
6. Identify a valid backup
7. Restore only after verification
```

Never delete the volume as a first troubleshooting step.

---

# 61. Git Workflow

LUMS is maintained using Git.

Typical workflow:

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
git add
   │
   ▼
git commit
   │
   ▼
git push
```

Before committing:

```bash
git status
```

Review:

```bash
git diff
```

Check for whitespace errors:

```bash
git diff --check
```

Stage:

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

# 62. Git Identity

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

---

# 63. Safe Repository Update

Before pulling:

```bash
cd /opt/lums-public
git status
```

Fetch:

```bash
git fetch origin
```

Review:

```bash
git log HEAD..origin/main --oneline
```

Update only with a clean working tree:

```bash
git pull --ff-only origin main
```

Then:

```bash
git status
```

---

# 64. Deployment Workflow

The current application deployment uses Docker.

The recommended sequence is:

```text
Git
 │
 ▼
git fetch
 │
 ▼
git pull --ff-only
 │
 ▼
Validation
 │
 ├── git diff --check
 └── Python syntax checks
 │
 ▼
Docker build
 │
 ▼
Database backup
 │
 ▼
Stop container
 │
 ▼
Remove container
 │
 ▼
Keep lums-data
 │
 ▼
Create new container
 │
 ▼
Health check
 │
 ▼
Agent test
```

---

# 65. Pre-Deployment Validation

Before rebuilding:

```bash
cd /opt/lums-public
```

Check:

```bash
git status
```

Check whitespace:

```bash
git diff --check
```

Check Python syntax:

```bash
python3 -m py_compile \
    server/app.py \
    server/init_db.py \
    agent/agent.py
```

Do not deploy if validation fails.

---

# 66. Docker Deployment

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

Logs:

```bash
sudo docker logs --tail 100 lums
```

---

# 67. Important Deployment Rule

Normal application deployment must never remove:

```text
lums-data
```

The following is safe during a normal image deployment:

```text
remove container
create container
reuse volume
```

The following is destructive:

```bash
sudo docker volume rm lums-data
```

Do not execute that command unless the database is intentionally being destroyed and a verified backup exists.

---

# 68. Post-Deployment Validation

Check container:

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Expected:

```text
running
```

Check local application:

```bash
curl -I http://127.0.0.1:5050/
```

Check Nginx:

```bash
sudo nginx -t
```

Check HTTPS:

```bash
curl -k -I https://ID Address/
```

Check API:

```bash
curl -k https://ID Address/api/health
```

Run the client agent:

```bash
sudo systemctl start lums-agent.service
```

Check:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 50 \
    --no-pager
```

---

# 69. Security Rules

Never commit:

```text
real client tokens
administrator passwords
TLS private keys
production databases
database backups
/etc/default/lums-agent
/etc/lums/docker/lums.env
private certificates
session secrets
```

Never publish:

```text
client tokens
passwords
private keys
production database contents
authentication secrets
session secrets
```

Use placeholders:

```text
SERVER_IP
CLIENT_IP
CLIENT_TOKEN
ADMIN_PASSWORD
```

---

# 70. Important Runtime Files

## Server

```text
/opt/lums-public
/etc/lums/docker/lums.env
/etc/nginx/ssl/lums/lums.crt
/etc/nginx/ssl/lums/lums.key
```

## Docker

```text
lums
lums:latest
lums-data
```

## Database

Inside the container:

```text
/var/lib/lums/lums.db
```

## Client

```text
/opt/lums-agent/agent.py
/opt/lums-agent/lums-ca.crt
/etc/default/lums-agent
```

---

# 71. Backup Strategy

Important LUMS data includes:

```text
SQLite database
Docker environment configuration
TLS configuration
TLS private key
Agent configuration
CA certificate
Git repository
```

Git only contains application source and documentation.

Git does not contain:

```text
database state
client tokens
server secrets
TLS private keys
runtime configuration
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

# 72. Recovery Strategy

A basic recovery sequence is:

```text
1. Restore operating system
        │
        ▼
2. Install Docker
        │
        ▼
3. Install Nginx
        │
        ▼
4. Restore LUMS repository
        │
        ▼
5. Restore environment file
        │
        ▼
6. Restore TLS configuration
        │
        ▼
7. Create / restore lums-data
        │
        ▼
8. Build Docker image
        │
        ▼
9. Start LUMS
        │
        ▼
10. Configure Nginx
        │
        ▼
11. Test HTTPS
        │
        ▼
12. Test administrator authentication
        │
        ▼
13. Test client authentication
        │
        ▼
14. Test agent
        │
        ▼
15. Test update functionality
```

Recovery should always be tested against a known backup.

---

# 73. Development vs Production

LUMS is suitable for:

* laboratories
* test environments
* development environments
* small infrastructure projects

A production deployment should additionally consider:

* TLS certificate lifecycle
* backups
* monitoring
* log rotation
* access control
* firewall rules
* least privilege
* database protection
* token rotation
* vulnerability management
* operating system updates
* secure secret storage
* container hardening
* resource limits
* production-grade WSGI serving

The current laboratory deployment should not automatically be considered production hardened.

---

# 74. Current Limitations

LUMS is an active development project.

Current areas that may require further hardening or development include:

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
```

These should be implemented incrementally.

---

# 75. Future Development

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
```

The core principle remains:

```text
Keep the system understandable.
Keep execution controlled.
Keep administration auditable.
```

---

# 76. Operational Philosophy

LUMS is intentionally not designed to become another unnecessarily complicated enterprise platform.

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

without unnecessary complexity.

The administrator should always be able to answer:

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

# 77. Quick Reference

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

---

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

---

## LUMS API

```bash
curl -k https://ID Address/api/health
```

---

## Agent

```bash
sudo systemctl status lums-agent.timer --no-pager
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

---

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

# 78. Final Deployment Checklist

Before considering a LUMS deployment complete:

* [ ] Git working tree is clean
* [ ] Repository is synchronized
* [ ] `git diff --check` passes
* [ ] Python syntax checks pass
* [ ] Docker image builds successfully
* [ ] `lums` container is running
* [ ] `lums-data` volume exists
* [ ] Database is persistent
* [ ] Application is bound to `127.0.0.1:5050`
* [ ] Flask port `5000` is not directly exposed
* [ ] Nginx configuration passes
* [ ] HTTPS works
* [ ] TLS certificate contains the correct SAN
* [ ] TLS private key permissions are restricted
* [ ] Server environment permissions are restricted
* [ ] `/api/health` responds successfully
* [ ] Administrator authentication works
* [ ] Client authentication works
* [ ] Client authorization works
* [ ] Agent CA certificate is available
* [ ] Agent token configuration is valid
* [ ] `lums-agent.timer` is active
* [ ] `lums-agent.service` executes successfully
* [ ] Client reports reach the server
* [ ] Client inventory is updated
* [ ] Update jobs can be created
* [ ] Update jobs can be retrieved
* [ ] Update results can be submitted
* [ ] Database integrity check returns `ok`
* [ ] Database backup exists
* [ ] No secrets are present in Git
* [ ] Documentation reflects the current deployment

---

# 79. Project

**LUMS**

Linux Update Management Server

Repository:

https://github.com/NovaForgeCtrl/LUMS

Maintained by:

**NovaForgeCtrl**

---

## Status

LUMS is an active development project.

The architecture, API, database schema and deployment model may evolve as development continues.

Always review the current source code and configuration examples before deploying a new version.

> **LUMS — Linux Update Management without the noise.**

> **Centralize the management. Keep execution controlled.**

> **Know what changed. Know where it happened.**

```
```
