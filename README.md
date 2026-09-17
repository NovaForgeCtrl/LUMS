# 🐧 LUMS

## Linux Update Management Server

**Linux Update Management without the noise.**

LUMS is a lightweight Linux update management system for centrally monitoring Linux clients, collecting update information and executing controlled package updates through an authenticated agent.

> **Build → Test → Break → Investigate → Understand → Harden → Document**

---

## Overview

LUMS consists of a central server and lightweight agents installed on Linux clients.

```text
                         ┌──────────────────────┐
                         │       Browser        │
                         └──────────┬───────────┘
                                    │
                                  HTTPS
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │        Nginx         │
                         │       TCP 443        │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       Flask          │
                         │    127.0.0.1:5000   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       SQLite         │
                         └──────────────────────┘
                                    ▲
                                    │
                              HTTPS + Token
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
             ┌──────┴──────┐                 ┌──────┴──────┐
             │ Linux       │                 │ Linux       │
             │ Client      │                 │ Client      │
             │             │                 │             │
             │ LUMS Agent  │                 │ LUMS Agent  │
             │ APT / dpkg  │                 │ APT / dpkg  │
             └─────────────┘                 └─────────────┘
```

The LUMS agent:

1. collects system information
2. detects available updates
3. authenticates against the LUMS API
4. sends a system report
5. checks for assigned update jobs
6. executes approved package updates
7. reports the result
8. sends a fresh system report after the update

---

# Features

* Linux client inventory
* Available update detection
* Central web interface
* Authenticated Linux agents
* Bearer-token authentication
* Per-client authorization
* Client isolation
* HTTPS communication
* TLS certificate verification
* SQLite database
* Argon2id password hashing
* Secure server sessions
* CSRF protection
* Security headers
* Audit logging
* Controlled update jobs
* Package-level update results
* Reboot-required detection
* systemd service integration
* systemd timer integration
* No automatic `apt autoremove`
* Lightweight architecture
* Suitable for labs and small environments

---

# Architecture

LUMS deliberately keeps the architecture simple.

```text
Linux Client
     │
     │ HTTPS / Bearer Token
     ▼
Nginx
     │
     │ localhost
     ▼
Flask API
     │
     ▼
SQLite
```

The Flask application listens only on:

```text
127.0.0.1:5000
```

External clients communicate with:

```text
TCP 443 / HTTPS
```

Port `5000` should never be exposed to the network.

---

# Requirements

## Server

Recommended:

* Ubuntu Server 26.04 LTS
* Python 3
* SQLite
* Nginx
* OpenSSL
* Git
* systemd
* 2 GB RAM or more
* 20 GB storage or more

## Client

The agent currently targets Debian/Ubuntu-style systems using:

* Python 3
* APT
* dpkg
* systemd

---

# Installation

The complete installation procedure is documented separately.

**Start here:**

➡️ [`INSTALL.md`](INSTALL.md)

The installation guide is intentionally written for users with little or no Linux experience.

It explains:

* what each component does
* how to prepare the server
* how to install dependencies
* how to create the LUMS service account
* how to configure the database
* how to configure HTTPS
* how to configure Nginx
* how to install the client agent
* how to create authentication tokens
* how to configure the systemd timer
* how to perform an end-to-end test

---

# Administration

After installation, use:

➡️ [`ADMINISTRATION.md`](ADMINISTRATION.md)

The administration guide covers:

* starting and stopping LUMS
* checking services
* managing clients
* client authentication
* update jobs
* database inspection
* logs
* backups
* agent management
* certificates
* Git updates
* security maintenance
* operational checks

---

# Troubleshooting

If something does not work:

➡️ [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)

The troubleshooting guide follows the LUMS architecture from the inside out:

```text
Database
   ↓
Flask
   ↓
Nginx
   ↓
HTTPS
   ↓
Firewall
   ↓
Network
   ↓
Agent
   ↓
Authentication
   ↓
Update Job
```

This makes it possible to isolate problems instead of reinstalling everything.

---

# Security Model

LUMS uses several layers of protection.

## Server

The Flask API runs as the dedicated:

```text
lums
```

system user.

It does not run as root.

---

## Network

Flask listens on:

```text
127.0.0.1:5000
```

Nginx provides:

```text
HTTPS :443
```

---

## Client Authentication

Clients authenticate using:

```http
Authorization: Bearer <CLIENT_TOKEN>
```

The server stores a SHA-256 hash of the client token rather than the clear-text token.

---

## Client Isolation

A client may only access resources belonging to itself.

For example:

```text
Client 1 → Client 1 jobs     allowed
Client 1 → Client 2 jobs     denied
```

---

## TLS

Agent communication uses HTTPS with certificate verification.

The agent does not disable TLS verification.

For laboratory installations, a self-signed certificate can be used.

For production environments, an appropriate internal or public PKI should be considered.

---

# Update Model

LUMS does not automatically run all available updates.

Instead, the server creates an update job for a specific client.

The agent retrieves the job and executes the requested packages.

Example:

```text
LUMS
  │
  │ Update Job
  ▼
Agent
  │
  ├── package A
  ├── package B
  ├── package C
  └── package D
        │
        ▼
    apt-get
        │
        ▼
     Result
        │
        ▼
      LUMS
```

The agent uses:

```bash
apt-get install --only-upgrade -y <package>
```

LUMS does not automatically execute:

```bash
apt autoremove
```

---

# Automatic Reporting

The agent periodically reports the current state of the client.

The default timer configuration is:

```text
First execution:
approximately 2 minutes after boot

Subsequent execution:
every 15 minutes
```

The timer is implemented using systemd.

---

# Project Structure

```text
LUMS/
│
├── README.md
├── INSTALL.md
├── ADMINISTRATION.md
├── TROUBLESHOOTING.md
│
├── agent/
│   ├── agent.py
│   ├── lums-agent.env.example
│   ├── lums-agent.service
│   └── lums-agent.timer
│
└── server/
    ├── app.py
    ├── create_admin.py
    ├── init_db.py
    ├── security.py
    ├── security_migration.py
    ├── static/
    └── templates/
```

---

# Runtime Paths

After installation, the main paths are:

| Component            | Path                                     |
| -------------------- | ---------------------------------------- |
| Git repository       | `/opt/lums-public`                       |
| Production API       | `/opt/lums-api`                          |
| Database             | `/var/lib/lums/lums.db`                  |
| Server configuration | `/etc/lums/lums.env`                     |
| TLS files            | `/etc/lums/tls/`                         |
| Agent                | `/opt/lums-agent/agent.py`               |
| Agent configuration  | `/etc/default/lums-agent`                |
| LUMS systemd service | `/etc/systemd/system/lums.service`       |
| Agent service        | `/etc/systemd/system/lums-agent.service` |
| Agent timer          | `/etc/systemd/system/lums-agent.timer`   |

---

# API

The LUMS API provides authenticated endpoints for client communication.

Important endpoints include:

```text
GET  /api/health
GET  /api/client/me
POST /api/report
GET  /api/clients/<id>/update-jobs/pending
POST /api/update-jobs/<id>/result
```

The health endpoint is intentionally unauthenticated so that service availability can be checked.

Client-management endpoints require authentication where appropriate.

---

# Current Status

LUMS has been tested end-to-end with:

```text
Client authentication
        ✓
TLS certificate verification
        ✓
System reporting
        ✓
Update inventory
        ✓
Update job retrieval
        ✓
Package updates
        ✓
Update result reporting
        ✓
Post-update reporting
        ✓
systemd timer
        ✓
```

A complete test successfully processed multiple packages with:

```text
Successful: 10
Failed:      0
Timeout:     0
Reboot:      not required
```

---

# Important Security Notes

Never commit the following to Git:

```text
/etc/lums/lums.env
/etc/default/lums-agent
```

Never publish:

```text
LUMS_SECRET_KEY
LUMS_TOKEN
```

Do not expose:

```text
TCP 5000
```

Do not disable TLS certificate verification as a workaround.

---

# Philosophy

LUMS is designed to remain understandable.

The goal is not to hide everything behind layers of abstraction.

The goal is to make the complete system understandable:

```text
Build
  ↓
Test
  ↓
Break
  ↓
Investigate
  ↓
Understand
  ↓
Harden
  ↓
Document
```

---

# License

See [`LICENSE`](LICENSE).

---

# Documentation

| Document                                   | Purpose               |
| ------------------------------------------ | --------------------- |
| [`README.md`](README.md)                   | Project overview      |
| [`INSTALL.md`](INSTALL.md)                 | Complete installation |
| [`ADMINISTRATION.md`](ADMINISTRATION.md)   | Daily administration  |
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) | Troubleshooting       |
