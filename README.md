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
* Role-based access control

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
     ┌──────┴───────┐
     │              │
 Management       Execution
     │              │
     ▼              ▼
 What should     What may
 happen?         happen?
     │              │
     └──────┬───────┘
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
* Role-based access control
* Automated testing
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

The production container is additionally hardened through:

```text
read-only root filesystem
CapDrop=ALL
non-root application user
restricted /tmp
file-based application secret
```

Persistent application state remains outside the container image in the:

```text
lums-data
```

Docker volume.

---

# Client Architecture

LUMS separates periodic reporting from update execution.

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

The reporting path is responsible for:

```text
Client authentication
       ↓
System information
       ↓
Package inventory
       ↓
Update inventory
       ↓
Agent status
       ↓
Report submission
```

## Execution

```text
lums-agent-watcher.timer
        │
        ▼
lums-agent-watcher.service
        │
        ▼
      watcher.py
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

The execution watcher also handles recovery of interrupted jobs and ensures that jobs are claimed atomically before execution.

---

# Security Audit Status

The security audit has completed the following areas:

```text
[x] SQLite Foreign Keys
[x] SQLite WAL / Busy Timeout
[x] Update Timeout / Process Termination
[x] Login Rate Limiting
[x] API Input Validation
[x] Session Revocation
[x] Token Rotation
[x] get_ip() / Offline-Network Handling
[x] Job Recovery / Checkpointing
[x] APT Robustness
[x] Arch Reboot Detection
[x] Unit Tests / Test Coverage
[x] Simulation Tests
[x] Continuous Integration
[x] Logging
[x] RBAC
[x] Versioning / Release Management Audit
```

The versioning and release-management audit confirmed that the project currently has no formal release tags or GitHub Releases. This is intentional while development continues.

Release infrastructure will be introduced separately when the project reaches an appropriate release stage.

The current automated test suite passes:

```text
79 passed
```

The security audit is therefore focused on the implemented system rather than treating unreleased functionality as completed.

## Update Jobs

Authorized users can create controlled update jobs according to their assigned role.

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

The current idle threshold is:

```text
300 seconds
```

The agent reports the active detection mechanism through:

```text
idle_source=loginctl
idle_supported=True
```

when supported.

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

Recovery is associated with the authenticated client and uses ownership and state checks to avoid unsafe races.

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

# Role-Based Access Control

LUMS provides role-based access control for administrative users.

The current roles are:

```text
administrator
operator
viewer
```

### Administrator

Administrators have full administrative access, including:

* Client management
* Token rotation
* Client removal
* Update job management
* User and security administration where implemented

### Operator

Operators can perform operational update-management tasks, including:

* View clients
* View package and update information
* View jobs and history
* Create and execute update jobs

Operators cannot perform administrator-only client or token management actions.

### Viewer

Viewers have read-only access to management information, including:

* Clients
* Packages
* Updates
* Jobs
* History

Viewers cannot create update jobs or perform administrative changes.

Client agents remain independently authenticated through their own Bearer tokens. Agent communication is therefore separate from the web application's user-role authorization.

---

# Security

LUMS includes several security and hardening mechanisms.

### Application

* Argon2 password hashing
* Session handling
* CSRF protection
* Security headers
* Client authentication
* Client-specific authorization
* Bearer token authentication
* Token rotation
* Login rate limiting
* Role-based access control
* Audit logging
* Input validation
* Update result validation
* Session revocation
* Recovery and execution safeguards

### Database

SQLite is configured with:

```text
foreign_keys = ON
busy_timeout = 5000
journal_mode = WAL
```

Database integrity and foreign-key checks are part of the security verification workflow.

### Container

The production container runs:

```text
User=lums
read-only root filesystem
CapDrop=ALL
Privileged=false
```

The container only receives the writable locations it actually needs.

Temporary storage is provided through a restricted `/tmp` tmpfs:

```text
rw,nosuid,nodev,noexec
```

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

# Security Audit Status

The security audit has completed the following areas:

```text
[x] SQLite Foreign Keys
[x] SQLite WAL / Busy Timeout
[x] Update Timeout / Process Termination
[x] Login Rate Limiting
[x] API Input Validation
[x] Session Revocation
[x] Token Rotation
[x] get_ip() / Offline-Network Handling
[x] Job Recovery / Checkpointing
[x] APT Robustness
[x] Arch Reboot Detection
[x] Unit Tests / Test Coverage
[x] Simulation Tests
[x] Continuous Integration
[x] Logging
[x] RBAC
```

The project currently has automated test coverage for the implemented security and application behavior.

The current test suite passes:

```text
79 passed
```

The update execution timeout uses:

```text
timeout
   ↓
terminate()
   ↓
10-second grace period
   ↓
kill() fallback
```

Login rate limiting currently escalates through:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

Versioning and release management have been reviewed as part of the audit, but release/versioning infrastructure has deliberately not yet been implemented. The project is still under active development and is not being presented as a finished release.

The remaining documentation work is tracked separately as the final audit area.

# Execution Watcher

The execution watcher is responsible for controlled update execution.

```text
lums-agent-watcher.timer
        │
        ▼
lums-agent-watcher.service
        │
        ▼
      watcher.py
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
1.7.0
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
lums-agent-watcher.service
lums-agent-watcher.timer
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

The automated simulation tests cover:

```text
UPDATE_SYSTEM
UPDATE_PACKAGE
INSTALL_PACKAGE
REMOVE_PACKAGE
Unknown actions
```

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
* Role-aware access control
* Multiple visual themes

Access to management functions depends on the authenticated user's role.

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

The database schema is maintained through versioned migrations.

The current security migration includes the user role field required for RBAC.

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
Package inventory
Update inventory
Update jobs
Job claiming
Job recovery
Checkpoint reporting
Result reporting
```

The API is divided conceptually into:

```text
Web / administrative operations
        │
        ├── Session authentication
        ├── CSRF protection
        └── Role-based authorization

Client operations
        │
        └── Bearer authentication
```

Client agents remain independently authenticated and are not subject to the web user's RBAC role.

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
| Automated Testing         | pytest / GitHub Actions |

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
├── tests/
│   ├── test_*.py
│   └── ...
│
├── .github/
│   └── workflows/
│       └── tests.yml
│
├── Dockerfile
├── docker-entrypoint.sh
├── .dockerignore
├── requirements-dev.txt
├── pytest.ini
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
Initialize database
      │
      ▼
Create administrator
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
Syntax Check
  │
  ▼
Unit Test
  │
  ▼
Debian Test
  │
  ▼
Arch Test
  │
  ▼
Integration Test
  │
  ▼
Production Verification
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

The project favors small, testable changes over large unverified changes.

---

# Automated Testing

LUMS uses pytest for automated testing.

The current test suite covers areas including:

```text
Security
Authentication
Session handling
RBAC
API validation
Update job validation
Job recovery
Package management
Simulation mode
```

The current full test suite passes:

```text
79 passed
```

Tests are also executed automatically through GitHub Actions on pushes to `main` and pull requests targeting `main`.

The CI workflow installs the development dependencies and runs:

```bash
python -m pytest -q
```

---

# Continuous Integration

The repository contains a GitHub Actions workflow for automated testing:

```text
.github/workflows/tests.yml
```

The workflow:

```text
Push / Pull Request
        │
        ▼
Checkout
        │
        ▼
Python 3.13
        │
        ▼
Install test dependencies
        │
        ▼
pytest
```

The workflow currently focuses on automated test execution.

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
Debian 13
Arch Linux
Docker
Nginx
Gunicorn
SQLite
systemd
```

The current agent version is:

```text
1.7.0
```

The current execution watcher version is:

```text
1.2.1
```

The current implementation includes end-to-end testing of:

```text
Client reporting
Client authentication
Client inventory
Package inventory
Update inventory
Update jobs
Atomic job claiming
Idle-aware execution
UPDATE_SYSTEM
Package update execution
Package installation
Package removal
Running-job recovery
Checkpoint handling
Token rotation
Session revocation
Login rate limiting
API input validation
Update result validation
APT update detection
Arch reboot detection
Container hardening
SQLite integrity verification
Simulation mode
RBAC
Automated tests
Continuous integration
Application logging
```

The current automated test suite passes:

```text
79 passed
```

Versioning and release management have been audited, but release infrastructure has deliberately not yet been introduced.

There are currently no formal Git tags or GitHub Releases.

The project is therefore still under active development and is **not yet presented as a finished release**.

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
* Monitoring integrations
* Improved APT/dpkg coordination
* Desktop-specific idle providers
* Resource limits
* Automated security testing
* Full backup and restore validation
* Release and versioning workflow

The roadmap is subject to change as the project develops.


# Current Status

LUMS is an active development project.

The current implementation has been tested with:

```text
Debian 13
Arch Linux
Docker
Nginx
Gunicorn
SQLite
systemd
```

Current component versions:

```text
LUMS Server
    active development

Agent
    1.7.0

Execution Watcher
    1.2.1
```

The current implementation includes testing and verification of:

```text
Client reporting
Client authentication
Client inventory
Package inventory
Update inventory
Update jobs
Atomic job claiming
Idle-aware execution
UPDATE_SYSTEM
Package installation
Package removal
Running-job recovery
Checkpoint handling
Token rotation
Session revocation
Login rate limiting
API input validation
Update result validation
APT update detection
Arch reboot detection
Container hardening
SQLite integrity verification
Simulation mode
RBAC
Automated tests
Continuous integration
Application logging
```

The automated test suite currently passes:

```text
79 passed
```

The project has also been verified with both Debian-based and Arch Linux clients.

Versioning and release management have been audited, but formal release infrastructure has deliberately not yet been introduced.

There are currently:

```text
No formal release tag
No GitHub Release
No stable project version
```

This is intentional.

LUMS is still under active development and is **not currently presented as a finished release**.

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
* Monitoring integrations
* Improved APT/dpkg coordination
* Desktop-specific idle providers
* Resource limits
* Automated security testing
* Full backup and restore validation
* Release and versioning workflow

The roadmap is intentionally kept flexible.

Implemented functionality is not listed as future work merely to make the roadmap look larger.

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

The project is also intentionally transparent about its current state.

Implemented functionality should be documented as implemented.

Incomplete functionality should remain marked as incomplete.

Future ideas belong in the roadmap rather than being presented as existing features.

---

# Repository

The source repository is maintained under:

```text
NovaForgeCtrl/LUMS
```

The repository contains:

* Source code
* Docker configuration
* Agent components
* Server components
* Tests
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

Use the project's guestbook issue template.

---

# Project

**LUMS**

### Linux Update Management Server

> **Linux Update Management without the noise.**

> **Centralize the management. Keep execution controlled.**

> **Know what changed. Know where it happened.**

> **One LUMS. Same Backend. Controlled Execution.**

---

# Status

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

---

# Development Status

LUMS is currently in active development.

The project has progressed beyond the initial prototype and now contains:

```text
Central client management
Package and update inventory
Controlled update execution
Idle-aware execution
Job recovery
Checkpoint handling
Client authentication
Token rotation
Session revocation
RBAC
Audit logging
Container hardening
Automated testing
Continuous integration
Multi-distribution package management
```

The remaining work is primarily focused on continued development, validation, documentation and eventually establishing a formal release process.

Until then:

```text
No stable release
No release tag
No production release promise
```

Just a project that keeps getting tested, broken, fixed and documented.

```text
segfault // override
```


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

The source repository is maintained under:

```text
NovaForgeCtrl/LUMS
```

The repository contains:

* Source code
* Docker configuration
* Agent components
* Server components
* Tests
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

Use the project's guestbook issue template.

---

# Project

**LUMS**

### Linux Update Management Server

> **Linux Update Management without the noise.**

> **Centralize the management. Keep execution controlled.**

> **Know what changed. Know where it happened.**

> **One LUMS. Same Backend. Controlled Execution.**

---

# Status

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

