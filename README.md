# LUMS

## Linux Update Management Server

> **Linux Update Management without the noise.**

LUMS is a lightweight Linux update management platform for small labs, test environments and infrastructure projects.

It provides centralized client management, package and update inventory, authenticated agent communication and controlled update execution — without requiring a large management stack.

```text
              ┌─────────────────────────────┐
              │            Nginx            │
              │          HTTPS / TLS        │
              └──────────────┬──────────────┘
                             │
                             │ localhost
                             ▼
              ┌─────────────────────────────┐
              │       Docker: lums          │
              │                             │
              │   Gunicorn → Flask          │
              │          :5000              │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │        lums-data            │
              │                             │
              │      SQLite / lums.db       │
              └─────────────────────────────┘
                       ▲          ▲
                       │          │
                    HTTPS      HTTPS
                       │          │
              ┌────────┴───┐  ┌──┴──────────┐
              │ Linux      │  │ Linux       │
              │ Client     │  │ Client      │
              │ Agent      │  │ Agent       │
              └────────────┘  └─────────────┘
```

---

# What is LUMS?

LUMS centralizes Linux update management without trying to replace the operating system's package manager.

The LUMS server manages:

* Linux client inventory
* Installed packages
* Available updates
* Client authentication
* Client tokens
* Update jobs
* Job execution state
* Execution results
* Administrative auditing
* Running-job recovery

The client agent handles:

* System reporting
* Package inventory
* Update inventory
* Idle-state detection
* Authorized update execution
* Result reporting

The operating system remains responsible for the actual package management.

```text
             LUMS
               │
       ┌───────┴────────┐
       │                │
   Management        Execution
       │                │
       ▼                ▼
   What should       What may
   happen?           happen?
       │                │
       └───────┬────────┘
               ▼
        Controlled action
```

---

# Why LUMS?

LUMS follows a simple idea:

> **Centralize the management. Keep execution controlled.**

The project focuses on:

* Simple architecture
* Transparent operation
* Minimal dependencies
* Secure client authentication
* Controlled execution
* Auditable changes
* Explicit recovery
* Container hardening
* Documentation-first development

LUMS is designed to remain understandable.

The goal is not to hide infrastructure behind layers of abstraction.

The goal is to make it possible to see:

```text
What changed?
      ↓
Where did it change?
      ↓
Which client was affected?
      ↓
What was executed?
      ↓
What result was reported?
```

---

# Features

## Client Management

LUMS maintains a central inventory of registered Linux clients.

Client information includes data such as:

* Hostname
* IP address
* Operating system
* Architecture
* Kernel
* Package count
* Available updates
* Agent version
* Last report
* Online state

---

## Package and Update Inventory

The agent reports installed packages and available updates to the LUMS server.

This allows administrators to see the state of clients centrally without replacing the native package manager.

---

## Update Jobs

Administrators can create controlled update jobs.

Supported job actions include:

```text
UPDATE_SYSTEM
UPDATE_PACKAGE
INSTALL_PACKAGE
REMOVE_PACKAGE
```

Jobs move through a controlled lifecycle:

```text
pending
   │
   ▼
running
   │
   ├── success
   ├── partial
   ├── failed
   └── abandoned
```

Jobs are claimed atomically so that the same job cannot accidentally be executed by multiple clients.

---

# Idle-Aware Execution

LUMS does not blindly execute update jobs as soon as they appear.

The client checks its local activity state before executing an update job.

The current Linux implementation uses:

```text
systemd-logind
        │
        ▼
     loginctl
        │
        ▼
  Idle state detection
```

This allows LUMS to defer execution while a relevant local session is active.

If idle detection is unavailable or cannot be determined safely, automatic execution does not proceed.

---

# Running-Job Recovery

A job must not remain permanently stuck in:

```text
running
```

if the client disappears during execution.

The execution watcher checks for existing running jobs before claiming new work.

```text
Running Job
     │
     ▼
Client interruption
     │
     ▼
Watcher detects state
     │
     ▼
Recovery
     │
     ├── Safe recovery
     │
     └── Abandoned
```

Recovery is associated with the authenticated client and uses state checks to avoid unsafe races.

This prevents a failed recovery from silently producing a second active execution.

---

# Client Authentication

Every client uses its own Bearer token.

```http
Authorization: Bearer <CLIENT_TOKEN>
```

Tokens are not stored as plaintext values.

LUMS stores a SHA-256 hexadecimal digest of the client token.

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

This means the server does not need to store the original token in order to authenticate the client.

---

# Token Rotation

Client tokens can be rotated from the administration interface.

A rotation:

1. Generates a new token.
2. Stores its digest.
3. Invalidates the previous token.
4. Records the operation in the audit log.
5. Displays the new token once.

After rotation:

```text
Old token → invalid
New token → valid
```

Plaintext tokens are not written to the audit log.

---

# Security

LUMS includes several security and hardening mechanisms.

### Application

* Argon2 password hashing
* Session handling
* CSRF protection
* Security headers
* Client-specific authorization
* Bearer token authentication
* Token rotation
* Audit logging

### Container

The production container runs:

```text
non-root
UID/GID 10001
read-only root filesystem
CapDrop=ALL
Privileged=false
```

The container only receives the writable locations it actually needs.

Temporary storage is provided through a restricted `/tmp` tmpfs.

The Flask secret is provided through a read-only secret file rather than a normal environment variable.

```text
Host:
    /etc/lums/secrets/lums_secret

Container:
    /run/secrets/lums_secret
```

The production application uses:

```text
LUMS_SECRET_KEY_FILE
```

instead of exposing the secret as:

```text
LUMS_SECRET_KEY
```

in the normal container environment.

---

# Architecture

The current server architecture is intentionally small:

```text
                     HTTPS
                       │
                       ▼
                ┌────────────┐
                │   Nginx    │
                │ TLS / :443 │
                └─────┬──────┘
                      │
              127.0.0.1:5050
                      │
                      ▼
             ┌────────────────┐
             │ Docker: lums   │
             │                │
             │ Gunicorn       │
             │ Flask          │
             └───────┬────────┘
                     │
                     ▼
             ┌────────────────┐
             │   lums-data    │
             │                │
             │ SQLite         │
             └────────────────┘
```

The Flask application listens on:

```text
5000
```

inside the container.

The host publishes it only on:

```text
127.0.0.1:5050
```

The application is therefore not intended to be directly exposed to the network.

Nginx provides the external HTTPS endpoint.

---

# Client Architecture

LUMS separates reporting from update execution.

## Reporting

```text
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
        │
        ▼
     LUMS API
```

## Execution

```text
lums-execution-watcher.timer
        │
        ▼
lums-execution-watcher.service
        │
        ▼
      watcher
        │
        ▼
   Idle detection
        │
        ▼
 Running-job recovery
        │
        ▼
   Pending job lookup
        │
        ▼
    Atomic claim
        │
        ▼
 Package manager
        │
        ▼
    Result report
```

The separation keeps periodic inventory reporting independent from update execution.

---

# Supported Linux Clients

The current agent architecture supports multiple Linux package managers.

## Debian / Ubuntu

```text
APT
dpkg
```

The agent can use:

```text
apt
apt-get
apt-cache
dpkg-query
```

for package inventory and update operations.

## Arch Linux

```text
pacman
```

The agent uses the native Arch package manager for:

```text
pacman -Q
pacman -Qu
pacman -S
pacman -R
pacman -Syu
```

The package-manager layer is abstracted inside the agent so that the rest of the update workflow does not need to know which package manager is being used.

```text
                 LUMS Agent
                     │
                     ▼
            Package Manager API
                 /        \
                /          \
             APT          pacman
              │              │
           Debian/        Arch Linux
           Ubuntu
```

---

# Agent

The current agent version is:

```text
1.6.0
```

The agent is written in Python and managed through systemd.

Installed components include:

```text
/opt/lums-agent/agent.py
/opt/lums-agent/watcher.py
/opt/lums-agent/lums-ca.crt
```

Configuration:

```text
/etc/default/lums-agent
```

The agent communicates with the LUMS server over HTTPS.

---

# Systemd Integration

The reporting agent uses:

```text
lums-agent.service
lums-agent.timer
```

The execution watcher uses:

```text
lums-execution-watcher.service
lums-execution-watcher.timer
```

A service may appear as:

```text
inactive (dead)
```

after a successful oneshot execution.

That is normal.

The timer is the component that remains active and schedules the next execution.

---

# Simulation Mode

LUMS includes a simulation mode for safe end-to-end testing.

Simulation mode can exercise:

* Job creation
* Job claiming
* Agent communication
* Watcher behavior
* Result reporting
* UI state changes

without performing real package installation.

This is useful during development and integration testing.

Simulation mode must not accidentally remain enabled in a production environment.

---

# Web Interface

The LUMS dashboard provides:

* Client overview
* Client details
* Update information
* Update job management
* Job status
* Administrative functions
* Token rotation
* Multiple visual themes

The frontend is implemented using:

```text
HTML
CSS
JavaScript
```

No frontend framework is required for the core dashboard.

---

# Themes

LUMS currently includes:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

User-facing names include:

```text
Standard LUMS
LUMS Stadium
Golf Club
Nerd Mode
Geek Lab
Enterprise Admin
```

The themes are visual layers.

They do not change:

* Authentication
* Authorization
* Database behavior
* Job execution
* Client communication

The Geek theme additionally provides:

```text
The Living Network
```

through its network visualization.

---

# Database

LUMS uses SQLite.

Persistent application data is stored in:

```text
lums-data
```

with the database located at:

```text
/var/lib/lums/lums.db
```

The database is kept outside the container image so that rebuilding or recreating the application container does not destroy application state.

```text
Docker Image
     ≠
Container
     ≠
Persistent Volume
```

---

# Backup

LUMS uses SQLite-aware backups rather than blindly copying a live database file.

A backup can be verified with:

```sql
PRAGMA integrity_check;
```

Expected result:

```text
ok
```

Git contains source code and documentation.

It does not contain:

* Production database state
* Client tokens
* Flask secrets
* TLS private keys
* Runtime configuration

A complete recovery strategy therefore requires both application backups and protected configuration/secret backups.

---

# API

The LUMS API handles areas including:

```text
Client management
Client reporting
Client authentication
Token rotation
Client inventory
Update inventory
Update jobs
Job claiming
Job recovery
Result reporting
```

The API is divided conceptually into:

```text
Administrator operations
        │
        └── Session + CSRF

Client operations
        │
        └── Bearer authentication
```

The API is actively developed and may evolve between releases.

---

# Technology Stack

| Component                 | Technology              |
| ------------------------- | ----------------------- |
| Backend                   | Python / Flask          |
| WSGI                      | Gunicorn                |
| Database                  | SQLite                  |
| Container                 | Docker                  |
| Reverse Proxy             | Nginx                   |
| Transport                 | HTTPS / TLS             |
| Admin Passwords           | Argon2                  |
| Client Authentication     | Bearer Tokens           |
| Frontend                  | HTML / CSS / JavaScript |
| Agent                     | Python                  |
| Scheduling                | systemd timers          |
| Debian Package Management | APT / dpkg              |
| Arch Package Management   | pacman                  |
| Source Control            | Git                     |

---

# Project Structure

The repository is organized around the server and agent components:

```text
LUMS/
├── agent/
│   ├── agent.py
│   ├── watcher.py
│   ├── package_manager.py
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

The repository structure may evolve as development continues.

---

# Quick Start

A typical deployment follows this model:

```text
Clone repository
      │
      ▼
Build image
      │
      ▼
Create lums-data
      │
      ▼
Configure secret
      │
      ▼
Start hardened container
      │
      ▼
Configure Nginx / HTTPS
      │
      ▼
Open dashboard
      │
      ▼
Create client
      │
      ▼
Install agent
      │
      ▼
Configure token + CA
      │
      ▼
Send first report
```

Build the image:

```bash
cd /opt/lums-public

sudo docker build \
    -t lums:latest \
    .
```

Create the persistent volume:

```bash
sudo docker volume create lums-data
```

Start the hardened container:

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

Nginx then exposes the application through HTTPS.

For the complete installation procedure, see the project documentation.

---

# Development Workflow

LUMS follows a simple development cycle:

```text
Change
  │
  ▼
Test
  │
  ▼
Validate
  │
  ▼
Commit
  │
  ▼
Push
```

Before committing:

```bash
git status
```

```bash
git diff
```

```bash
git diff --check
```

Python syntax should be checked before deployment.

The project favors small, testable changes over large unverified changes.

---

# Documentation

The project follows a documentation-first approach.

Documentation covers areas including:

```text
Installation
Architecture
Agent setup
Client management
Update jobs
Security
Troubleshooting
Backup
Recovery
Deployment
```

The documentation is intended to describe the actual implementation rather than an idealized future architecture.

When implementation changes, documentation should be updated accordingly.

---

# Security Philosophy

LUMS does not assume that a container automatically makes an application secure.

The deployment therefore combines multiple layers:

```text
HTTPS
  +
Authentication
  +
Authorization
  +
CSRF protection
  +
Security headers
  +
Token lifecycle
  +
Audit logging
  +
Container hardening
  +
Database persistence
  +
Controlled execution
```

No individual control is treated as a complete security boundary by itself.

---

# Current Status

LUMS is an active development project.

The current implementation has been tested with:

```text
Debian Linux
Arch Linux
Docker
Nginx
Gunicorn
SQLite
systemd
```

The current agent version is:

```text
1.6.0
```

The current implementation includes end-to-end testing of:

```text
Client reporting
Client authentication
Client inventory
Update inventory
Update jobs
Atomic job claiming
Idle-aware execution
UPDATE_SYSTEM
Package installation jobs
Running-job recovery
Token rotation
Container hardening
SQLite integrity verification
```

The project is **not yet presented as a finished enterprise management platform**.

The architecture is intentionally evolving.

---

# Roadmap

Potential future development includes:

* Scheduled maintenance windows
* Client groups
* Automatic client enrollment
* Agent update management
* Package deployment workflows
* Repository management
* Enhanced reporting
* Dashboard statistics
* Role-based access control
* Extended audit logging
* Monitoring integrations
* Improved APT/dpkg coordination
* Desktop-specific idle providers
* Resource limits
* Automated security testing
* Full backup and restore validation

The roadmap is subject to change as the project develops.

---

# Design Philosophy

LUMS is built around a simple principle:

> **Know what changed. Know where it happened. Keep execution controlled.**

The project deliberately favors:

```text
Simple architecture
        +
Explicit behavior
        +
Documented decisions
        +
Controlled execution
```

over unnecessary complexity.

LUMS should remain understandable enough that an administrator can inspect the system and understand what it is doing.

---

# Repository

**GitHub**

https://github.com/NovaForgeCtrl/LUMS

The repository contains:

* Source code
* Docker configuration
* Agent components
* Server components
* Documentation
* License

Production secrets and private runtime configuration are intentionally kept outside the repository.

---

# License

LUMS is released under the:

**MIT License**

See [`LICENSE`](LICENSE) for the complete license text.

---

# Community

Found something interesting?

Have an idea?

Want to leave feedback?

You can use the LUMS guestbook:

[💬 Guestbook](https://github.com/NovaForgeCtrl/whoami/issues/new?template=guestbook.md)

---

# Project

**LUMS**

### Linux Update Management Server

> **Linux Update Management without the noise.**

> **Centralize the management. Keep execution controlled.**

> **Know what changed. Know where it happened.**

> **One LUMS. Same Backend. Controlled Execution.**

---

## Status

LUMS is actively developed.

The architecture, API, database schema and deployment model may evolve as development continues.

Always review the current source code and configuration examples before deploying a new version.

```text
                 ┌─────────────────────┐
                 │        LUMS         │
                 │                     │
                 │ Central Management  │
                 │ Controlled Execution│
                 │ Auditable Changes   │
                 └──────────┬──────────┘
                            │
             ┌──────────────┼──────────────┐
             │              │              │
          Client A       Client B       Client N
             │              │              │
             └──────────────┼──────────────┘
                            │
                         HTTPS
                            │
                            ▼
                       Same Backend
```

> **LUMS — Linux Update Management without the noise.**
>
> **One LUMS. Many clients. Same backend. Controlled execution.**
>
> [💬 Guestbook](https://github.com/NovaForgeCtrl/whoami/issues/new?template=guestbook.md)
