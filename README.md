# LUMS

## Linux Update Management Server

> **Linux Update Management without the noise.**

LUMS is a lightweight Linux update management platform designed for small labs, test environments and infrastructure projects.

It provides a central server for Linux client inventory, update information, package information and agent communication.

The project focuses on:

* simple architecture
* transparent operation
* central client management
* secure agent authentication
* minimal dependencies
* auditable communication
* easy deployment
* documentation-first administration

---

# 1. Project Overview

LUMS consists of two primary components:

```text
                    ┌──────────────────────┐
                    │        LUMS          │
                    │   Management Server  │
                    │                      │
                    │ Flask + SQLite       │
                    │ Nginx + HTTPS        │
                    └──────────┬───────────┘
                               │
                    HTTPS / Bearer Token
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        ┌──────────┐     ┌──────────┐     ┌──────────┐
        │ Client 1 │     │ Client 2 │     │ Client N │
        │   Agent  │     │   Agent  │     │   Agent  │
        └──────────┘     └──────────┘     └──────────┘
```

## Server

The LUMS server provides:

* Web dashboard
* administrator authentication
* client management
* client authentication
* client inventory
* update inventory
* package inventory
* audit logging
* API endpoints
* SQLite persistence

## Agent

The LUMS agent runs on managed Linux systems and automatically collects:

* hostname
* IP address
* operating system
* kernel version
* architecture
* agent version
* available updates
* installed packages

The agent sends this information to the LUMS server using HTTPS and a client-specific Bearer token.

---

# 2. Repository Structure

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
├── LICENSE
└── README.md
```

---

# 3. Technology Stack

| Component          | Technology              |
| ------------------ | ----------------------- |
| Backend            | Python / Flask          |
| Database           | SQLite                  |
| Web server         | Nginx                   |
| Transport          | HTTPS                   |
| Authentication     | Argon2 / Bearer Tokens  |
| Frontend           | HTML / CSS / JavaScript |
| Agent              | Python                  |
| Service manager    | systemd                 |
| Package management | APT                     |
| Repository         | Git                     |

LUMS intentionally avoids unnecessary infrastructure dependencies.

---

# 4. Design Principles

LUMS follows several basic principles.

## Keep the architecture understandable

The system should remain understandable without requiring a large enterprise stack.

## Separate management and client communication

The administrator uses the web interface.

Linux clients communicate with the API.

```text
Administrator
     │
     ▼
Web UI
     │
     ▼
Flask
     │
     ▼
SQLite
```

Client communication follows a separate path:

```text
Linux Client
     │
     ▼
LUMS Agent
     │
     │ HTTPS + Bearer Token
     ▼
LUMS API
     │
     ▼
SQLite
```

## Store tokens safely

Client tokens are not stored in plaintext.

The server stores a SHA-256 hash of the client token.

The original token is displayed only when the client is created.

---

# 5. Server Requirements

A typical LUMS server requires:

* Linux
* Python 3
* Flask
* SQLite
* Nginx
* systemd
* HTTPS certificate
* sufficient disk space for package/update information

A small lab deployment can run comfortably on a VM.

Recommended starting point:

```text
2 CPU cores
4 GB RAM
20+ GB storage
```

Actual requirements depend on the number of managed clients and the amount of collected package/update data.

---

# 6. Agent Requirements

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

# 7. Installation Overview

A typical installation consists of these stages:

```text
1. Install server
        │
        ▼
2. Initialize database
        │
        ▼
3. Configure administrator
        │
        ▼
4. Configure Nginx / HTTPS
        │
        ▼
5. Start LUMS
        │
        ▼
6. Open dashboard
        │
        ▼
7. Create client
        │
        ▼
8. Install agent
        │
        ▼
9. Configure token
        │
        ▼
10. Send first report
```

---

# 8. Server Installation

Clone the repository:

```bash
git clone https://github.com/NovaForgeCtrl/LUMS.git
cd LUMS
```

The server application is located in:

```text
server/
```

Install the required Python dependencies according to the deployment environment.

Initialize the database:

```bash
python3 server/init_db.py
```

Create the administrator account:

```bash
python3 server/create_admin.py
```

The exact deployment commands may vary depending on the Linux distribution and installation environment.

---

# 9. Production Deployment

A recommended production-style layout is:

```text
/opt/lums-api/
    app.py
    security.py
    static/
    templates/

/var/lib/lums/
    lums.db

/etc/default/
    lums-agent
```

The Flask application can be managed by systemd.

Example:

```text
lums.service
```

A reverse proxy such as Nginx should terminate HTTPS and forward requests to the Flask application.

---

# 10. HTTPS

LUMS is designed to use HTTPS for client communication.

The agent communicates with:

```text
https://<LUMS-SERVER>/api/report
```

When a private CA is used, the CA certificate is supplied to the agent.

Example:

```text
/opt/lums-agent/lums-ca.crt
```

The agent creates an SSL context using the configured CA file.

This prevents the client from blindly trusting arbitrary certificates.

---

# 11. Administrator Authentication

The web interface requires administrator authentication.

Passwords are handled using Argon2-based password hashing.

The application also supports:

* login
* logout
* session management
* CSRF protection
* security headers
* audit logging

Administrator credentials must never be stored in the repository.

---

# 12. Client Management

Clients are managed through the LUMS dashboard.

The current workflow intentionally keeps manual registration simple.

## Client creation

The administrator enters:

```text
IP address
```

The server generates:

```text
Client ID
Client Token
```

The token is displayed after successful creation.

The administrator then configures the agent on the Linux client.

---

# 13. Automatic Client Information

The administrator does **not** need to manually enter the client's system information.

After the agent connects, it automatically reports:

```text
Hostname
IP address
Operating system
Kernel
Architecture
Agent version
Available updates
Installed packages
```

Example:

```text
Hostname: client01
IP: 192.168.x.x
OS: Linux
Kernel: 6.x.x
Architecture: x86_64
Agent: 1.3.0
```

The server updates the client record when the report is received.

---

# 14. Client Token

Each client receives its own authentication token.

The token is used as:

```http
Authorization: Bearer <CLIENT_TOKEN>
```

The server stores only a SHA-256 hash of the token.

Conceptually:

```text
Client Token
     │
     ▼
SHA-256
     │
     ▼
Database
```

The plaintext token should never be committed to Git.

Do not put real tokens into:

```text
README.md
screenshots
Git commits
configuration examples
issue reports
```

---

# 15. Agent Configuration

The agent uses an environment file.

Example:

```text
LUMS_BASE=https://lums.example.internal
LUMS_TOKEN=<CLIENT_TOKEN>
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

The real configuration file must remain local to the client.

A safe example file is provided as:

```text
agent/lums-agent.env.example
```

Never commit the real `/etc/default/lums-agent` file if it contains a real token.

---

# 16. Agent Service

The agent is provided with a systemd service:

```text
agent/lums-agent.service
```

The service uses:

```ini
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/lums-agent/agent.py
EnvironmentFile=-/etc/default/lums-agent
```

Because the service is `oneshot`, it performs its task and exits.

This is intentional.

A timer can be used to execute the agent periodically.

---

# 17. Agent Timer

The repository also contains:

```text
agent/lums-agent.timer
```

A timer can periodically execute:

```text
lums-agent.service
```

This avoids keeping a permanent Python process running when continuous execution is not required.

---

# 18. Agent Data Collection

The agent collects the hostname:

```python
socket.gethostname()
```

The IP address is determined from the system routing information.

The agent also uses Python's `platform` module for:

```text
Operating system
Kernel
Architecture
```

The current agent version is defined in:

```python
AGENT_VERSION
```

---

# 19. Client Report

The agent sends a JSON report to:

```text
POST /api/report
```

The request contains information similar to:

```json
{
    "hostname": "client01",
    "ip": "192.168.x.x",
    "os": "Linux",
    "kernel": "6.x.x",
    "architecture": "x86_64",
    "agent_version": "1.3.0",
    "updates": [],
    "packages": {}
}
```

The actual update and package lists depend on the client.

---

# 20. Client Authentication

The `/api/report` endpoint requires client authentication.

The agent sends:

```http
Authorization: Bearer <CLIENT_TOKEN>
```

The server:

```text
1. extracts the Bearer token
2. hashes the token
3. compares it against the stored hash
4. verifies that the client exists
5. verifies that the client is enabled
6. accepts the report
7. updates client information
```

This ensures that arbitrary systems cannot submit client reports without a valid token.

---

# 21. Database

LUMS currently uses SQLite.

The database is stored outside the source repository.

Example:

```text
/var/lib/lums/lums.db
```

The database contains information such as:

```text
clients
updates
installed_packages
audit information
```

The exact schema can evolve with the project.

---

# 22. Client Database Model

A client record contains fields such as:

```text
id
hostname
ip
os
kernel
architecture
agent_version
last_seen
client_token_hash
token_created_at
token_revoked_at
enabled
```

Some fields are initially empty because the agent fills them after the first successful report.

This is intentional.

---

# 23. Client Lifecycle

The intended lifecycle is:

```text
                  ┌───────────────┐
                  │ Client created│
                  └───────┬───────┘
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
                 Client populated
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
          Inactive                Removed
```

---

# 24. Removing Clients

Clients can be removed through the dashboard.

Deletion also removes associated client-specific update/package records where applicable.

Before deleting a production client, verify that the client is no longer required.

---

# 25. Re-Adding a Client

A client can be registered again after deletion.

The recommended procedure is:

```text
1. Delete old client
2. Create new client
3. Generate new token
4. Configure the agent with the new token
5. Send a new report
```

A new token should be used instead of reusing an old credential.

---

# 26. Security Model

LUMS uses multiple security layers.

## Administrator side

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
Flask API
```

## Client side

```text
Agent
   │
   ▼
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
Report
```

---

# 27. CSRF Protection

Administrative state-changing requests use CSRF protection.

Examples include:

```text
POST /api/clients
DELETE /api/clients/<id>
```

The dashboard obtains the CSRF token from the page and sends it with the request.

Client-to-server reports are authenticated using the client Bearer token and therefore follow a separate authentication model.

---

# 28. Security Headers

The application applies security-related HTTP headers.

The exact header configuration belongs to the deployment and can be reviewed in the server security implementation.

Nginx should also be configured appropriately for:

* TLS
* HTTP security headers
* request forwarding
* access logging
* error logging

---

# 29. Audit Logging

Important administrative actions are recorded through the application's audit logging mechanism.

Examples include:

```text
client.create
client.delete
authentication events
```

Audit records help reconstruct administrative activity during troubleshooting or security investigations.

---

# 30. API Overview

The LUMS API contains separate areas for administrators and clients.

Examples include:

```text
POST /api/clients
DELETE /api/clients/<id>
POST /api/report
GET /api/client/me
```

The exact available endpoints should always be checked against the current application source.

---

# 31. API Authentication Model

There are two authentication contexts.

## Administrator API

Uses the authenticated web session and CSRF protection for state-changing operations.

## Client API

Uses:

```http
Authorization: Bearer <CLIENT_TOKEN>
```

The two authentication models should not be mixed.

---

# 32. Troubleshooting

The most important LUMS troubleshooting rule is:

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

LUMS can be divided into:

```text
┌─────────────────────┐
│ Browser / Dashboard │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Nginx / HTTPS       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Flask Application   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ SQLite              │
└─────────────────────┘

Client side:

┌─────────────────────┐
│ systemd             │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ LUMS Agent          │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ Network / HTTPS     │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ LUMS API            │
└─────────────────────┘
```

---

# 33. Check Server Service

Check the LUMS service:

```bash
sudo systemctl status lums.service --no-pager
```

Check whether it is active:

```bash
sudo systemctl is-active lums.service
```

View recent logs:

```bash
sudo journalctl -u lums.service -n 100 --no-pager
```

---

# 34. Check Agent Service

Check:

```bash
sudo systemctl status lums-agent --no-pager
```

Run the service manually:

```bash
sudo systemctl start lums-agent
```

View logs:

```bash
sudo journalctl -u lums-agent -n 100 --no-pager
```

---

# 35. Important Agent Detail

Running the agent directly like this:

```bash
sudo python3 /opt/lums-agent/agent.py
```

does **not** automatically load:

```text
/etc/default/lums-agent
```

The systemd service does load the environment file through:

```ini
EnvironmentFile=-/etc/default/lums-agent
```

Therefore, if the direct execution reports:

```text
LUMS_TOKEN ist nicht gesetzt.
```

that does not necessarily mean the configured systemd service is broken.

Test the actual service instead:

```bash
sudo systemctl start lums-agent
```

---

# 36. Check Agent Configuration

Never display a real token in public logs or documentation.

To check whether the configuration file exists:

```bash
sudo ls -l /etc/default/lums-agent
```

To inspect the configuration, redact the token before sharing output.

Example:

```text
LUMS_BASE=https://lums.example.internal
LUMS_TOKEN=***
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

---

# 37. HTTPS Problems

If the agent cannot connect, check:

```text
LUMS_BASE
CA certificate
DNS / hostname
network connectivity
TCP port
Nginx
TLS certificate
```

For internal testing, verify the server is reachable from the client.

Do not permanently disable TLS certificate verification merely to hide a certificate configuration problem.

---

# 38. Authentication Problems

If the server returns:

```text
401 Unauthorized
```

check:

```text
1. Client token
2. Token hash stored by the server
3. Client enabled state
4. Authorization header
5. LUMS_BASE
6. Agent configuration
```

The server stores the SHA-256 hash of the token.

A token copied incorrectly will therefore fail authentication.

---

# 39. Client Not Updating

If the client exists but information is missing:

```text
1. Check lums-agent
2. Check token
3. Check HTTPS
4. Run the agent
5. Check server logs
6. Check database
```

The first successful report should populate:

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

# 40. SSH Troubleshooting

SSH is independent from LUMS.

Check the SSH service:

```bash
sudo systemctl status ssh --no-pager
```

If it is installed but inactive:

```bash
sudo systemctl start ssh
```

Check whether port 22 is listening:

```bash
sudo ss -tlnp | grep ':22'
```

If a remote connection returns:

```text
Connection timed out
```

check:

```text
network connectivity
routing
firewall
SSH listener
```

UFW can be checked with:

```bash
sudo ufw status verbose
```

---

# 41. Database Troubleshooting

The SQLite database is normally located at:

```text
/var/lib/lums/lums.db
```

Inspect the database:

```bash
sudo sqlite3 /var/lib/lums/lums.db
```

Example:

```sql
.tables
```

Client records can be inspected with:

```sql
SELECT
    id,
    hostname,
    ip,
    os,
    kernel,
    architecture,
    agent_version,
    last_seen
FROM clients;
```

Never publish production database contents.

---

# 42. Git Workflow

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

Review changes:

```bash
git diff
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

# 43. What Must Never Be Committed

Never commit:

```text
real client tokens
administrator passwords
private keys
TLS private keys
production databases
/etc/default/lums-agent
personal credentials
internal secrets
```

Use example files instead.

For example:

```text
lums-agent.env.example
```

should contain placeholders:

```text
LUMS_BASE=https://lums.example.internal
LUMS_TOKEN=<CLIENT_TOKEN>
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

---

# 44. Development Workflow

A recommended development cycle is:

```text
Change one component
        │
        ▼
Run syntax checks
        │
        ▼
Restart affected service
        │
        ▼
Test manually
        │
        ▼
Check logs
        │
        ▼
Test dashboard/API
        │
        ▼
Commit
        │
        ▼
Push
```

Python syntax can be checked with:

```bash
python3 -m py_compile server/app.py
```

---

# 45. Backup Strategy

Before major database migrations or structural changes, create a database backup.

Example:

```bash
sudo cp /var/lib/lums/lums.db \
    /var/lib/lums/lums.db.bak-before-change
```

Do not place these backups inside the Git repository.

Database backups should be handled separately from source-code version control.

---

# 46. Development vs Production

LUMS can be used in a laboratory environment and can be adapted for production use.

However, a production deployment should additionally consider:

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

---

# 47. Current Agent Version

The current agent defines its version in:

```python
AGENT_VERSION
```

The version is included in every client report.

This allows the server to identify which agent version is running on each client.

---

# 48. Future Development

Potential future features include:

```text
Token rotation
Client enable/disable
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
```

These features should be implemented incrementally to keep the core system understandable.

---

# 49. Philosophy

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

> **Linux Update Management without the noise.**

---

# 50. License

See the [`LICENSE`](LICENSE) file for the applicable license.

---

# 51. Project

**LUMS**

Linux Update Management Server

Repository:

https://github.com/NovaForgeCtrl/LUMS

Maintained by:

**NovaForgeCtrl**

---

## Status

LUMS is an active development project.

The architecture, API and database schema may change as development continues.

Always review the current source code and configuration examples before deploying a new version.
