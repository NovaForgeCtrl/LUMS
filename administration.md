# LUMS Administration Guide

> **Linux Update Management Server**
>
> Centralized update management, client inventory, reporting and controlled package deployment for Linux systems.

---

## Overview

This guide describes the day-to-day administration of **LUMS**, including:

* server administration
* client and agent management
* update jobs
* package inventory
* database maintenance
* TLS and authentication
* Git-based deployment
* troubleshooting
* backups and recovery
* security-related administration

LUMS is designed to keep the management layer centralized while keeping update execution on the individual Linux clients.

---

## 1. System Architecture

```text
                         ┌─────────────────────┐
                         │      Web Browser     │
                         └──────────┬──────────┘
                                    │
                              HTTPS :443
                                    │
                         ┌──────────▼──────────┐
                         │       Nginx         │
                         │   TLS / Reverse     │
                         │       Proxy         │
                         └──────────┬──────────┘
                                    │
                         HTTP 127.0.0.1:5000
                                    │
                         ┌──────────▼──────────┐
                         │    LUMS Flask API    │
                         │                      │
                         │ Authentication       │
                         │ Client Management    │
                         │ Reporting            │
                         │ Update Jobs          │
                         │ Audit Logging        │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │       SQLite        │
                         │   /var/lib/lums/    │
                         │      lums.db        │
                         └─────────────────────┘

        HTTPS + Bearer Token
                  │
                  ▼
        ┌─────────────────────┐
        │    Linux Client     │
        │                     │
        │    lums-agent       │
        │                     │
        │  APT / Inventory    │
        └─────────────────────┘
```

---

## 2. Runtime Layout

### Server

| Component            | Location                           |
| -------------------- | ---------------------------------- |
| Source repository    | `/opt/lums-public`                 |
| Deployed application | `/opt/lums-api`                    |
| Database             | `/var/lib/lums/lums.db`            |
| Server environment   | `/etc/lums.env`                    |
| Systemd service      | `/etc/systemd/system/lums.service` |
| Nginx configuration  | `/etc/nginx/`                      |
| TLS certificate      | `/etc/nginx/ssl/lums.crt`          |
| TLS private key      | `/etc/nginx/ssl/lums.key`          |

### Client

| Component           | Location                          |
| ------------------- | --------------------------------- |
| Agent source        | `/opt/lums-public/agent/agent.py` |
| Installed agent     | `/opt/lums-agent/agent.py`        |
| Agent configuration | `/etc/default/lums-agent`         |
| Systemd service     | `lums-agent.service`              |
| Systemd timer       | `lums-agent.timer`                |

---

## 3. Important Paths

The following paths should be treated as operationally important.

### Do not casually overwrite

```text
/var/lib/lums/lums.db
/etc/lums.env
/etc/nginx/ssl/lums.crt
/etc/nginx/ssl/lums.key
/etc/default/lums-agent
```

These contain runtime state, secrets or client-specific configuration.

> [!CAUTION]
> A Git deployment must **never** replace the LUMS database, server environment file, TLS private key or client token configuration.

---

# Server Administration

## 4. Check LUMS Service

Check the Flask application:

```bash
sudo systemctl status lums
```

Restart:

```bash
sudo systemctl restart lums
```

Stop:

```bash
sudo systemctl stop lums
```

Start:

```bash
sudo systemctl start lums
```

Enable at boot:

```bash
sudo systemctl enable lums
```

---

## 5. View LUMS Logs

Follow the service log:

```bash
sudo journalctl -u lums -f
```

Show recent logs:

```bash
sudo journalctl -u lums --since "30 minutes ago"
```

Show errors:

```bash
sudo journalctl -u lums -p err
```

---

## 6. Check Nginx

Check configuration:

```bash
sudo nginx -t
```

Reload configuration:

```bash
sudo systemctl reload nginx
```

Check status:

```bash
sudo systemctl status nginx
```

View logs:

```bash
sudo journalctl -u nginx -f
```

---

## 7. HTTPS Health Check

LUMS exposes a health endpoint:

```text
/api/health
```

Example:

```bash
curl -k https://192.168.2.229/api/health
```

Expected response:

```json
{
  "service": "LUMS API",
  "status": "ok"
}
```

> [!NOTE]
> `-k` is used because the current installation uses a self-signed certificate.

---

## 8. TLS Certificate

The current certificate is configured for:

```text
192.168.2.229
```

Certificate:

```text
/etc/nginx/ssl/lums.crt
```

Private key:

```text
/etc/nginx/ssl/lums.key
```

Check certificate details:

```bash
sudo openssl x509 -in /etc/nginx/ssl/lums.crt -noout -text
```

Check the SAN:

```bash
sudo openssl x509 -in /etc/nginx/ssl/lums.crt -noout -ext subjectAltName
```

Expected:

```text
IP Address:192.168.2.229
```

> [!WARNING]
> The private key must never be committed to Git or shared publicly.

---

## 9. Server Environment

The LUMS environment file is:

```text
/etc/lums.env
```

It is loaded by the systemd service through:

```ini
EnvironmentFile=/etc/lums.env
```

Check the file:

```bash
sudo ls -l /etc/lums.env
```

> [!CAUTION]
> Do not publish the contents of `/etc/lums.env`.
>
> It contains server-side secrets.

---

# Client Administration

## 10. Agent Architecture

The LUMS agent runs as a `systemd` oneshot service.

The timer starts the agent periodically.

```text
lums-agent.timer
        │
        ▼
lums-agent.service
        │
        ▼
/opt/lums-agent/agent.py
        │
        ├── collect inventory
        ├── report client state
        ├── check update jobs
        └── execute approved updates
```

The agent does **not** remain permanently running.

---

## 11. Agent Configuration

Configuration:

```text
/etc/default/lums-agent
```

Example structure:

```ini
LUMS_BASE=https://192.168.2.229
LUMS_CA_FILE=/etc/nginx/ssl/lums.crt
LUMS_TOKEN=<client-token>
```

> [!CAUTION]
> Never publish the real `LUMS_TOKEN`.

---

## 12. Check Agent Service

```bash
sudo systemctl status lums-agent
```

Run manually:

```bash
sudo systemctl start lums-agent
```

View logs:

```bash
sudo journalctl -u lums-agent -n 100
```

Follow live logs:

```bash
sudo journalctl -u lums-agent -f
```

---

## 13. Check Agent Timer

```bash
sudo systemctl status lums-agent.timer
```

List timers:

```bash
systemctl list-timers --all | grep lums
```

The timer controls when the agent executes.

---

## 14. Manual Agent Test

A manual execution is useful when troubleshooting:

```bash
sudo systemctl start lums-agent
```

Then inspect:

```bash
sudo journalctl -u lums-agent -n 50 --no-pager
```

A successful run may contain:

```text
LUMS API: {"status":"received"}
Kein Update-Job vorhanden.
```

This confirms that the agent was able to:

* connect to LUMS
* validate TLS
* authenticate with its Bearer token
* submit its report
* query its client information
* check for pending update jobs

---

# Authentication

## 15. Client Authentication

LUMS clients authenticate using a Bearer token.

Requests contain:

```http
Authorization: Bearer <client-token>
```

The server does **not** need to store the plaintext client token.

Instead, the token is represented by a SHA-256 hash.

```text
Client Token
     │
     ▼
 SHA-256
     │
     ▼
Token Hash
     │
     ▼
SQLite
```

---

## 16. Client Authentication Rules

A client token must:

* exist
* match the stored SHA-256 hash
* belong to an enabled client
* not be revoked

Disabled or revoked clients must not be able to authenticate successfully.

---

## 17. Client API Identity

Authenticated agents use:

```text
GET /api/client/me
```

This endpoint provides the authenticated client context.

> [!NOTE]
> `/api/client/me` is intentionally different from the administrative client management endpoints.

---

# Client Management

## 18. Client Registration

Clients can be added through the LUMS administration interface.

The client database allows:

```text
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

`hostname` is optional.

This is important because the initial client registration can be performed using only the client IP address.

---

## 19. Client Status

LUMS uses the last successful agent report to determine client activity.

|         Last Seen | Status  |
| ----------------: | ------- |
|   `≤ 120 seconds` | Online  |
| `121–600 seconds` | Unknown |
|   `> 600 seconds` | Offline |

The default timer interval is approximately 15 minutes.

Therefore, a client can temporarily appear as unknown or offline without necessarily indicating a broken system.

---

## 20. Inventory

The inventory displayed by LUMS represents the information submitted by the client during its last successful report.

It is **not** a live query against APT.

The report can contain information such as:

* operating system
* kernel
* architecture
* agent version
* installed packages
* available packages

---

# Updates and Jobs

## 21. Update Management

LUMS separates update management into two stages:

```text
Administrator
     │
     ▼
Create / approve update job
     │
     ▼
LUMS Server
     │
     ▼
Client Agent
     │
     ▼
APT
```

The server decides **what** should be updated.

The client performs the actual package installation.

---

## 22. Package Installation

The agent installs approved packages using:

```bash
apt-get install --only-upgrade -y <package>
```

This means LUMS does not intentionally perform a complete distribution upgrade.

---

## 23. Automatic Reboots

The agent does **not** automatically reboot the client.

After package updates, reboot requirements can be detected through:

```text
/var/run/reboot-required
```

A reboot remains an administrative decision.

> [!NOTE]
> This prevents LUMS from unexpectedly rebooting managed systems after an update job.

---

# Database Administration

## 24. Database Location

LUMS uses SQLite.

Database:

```text
/var/lib/lums/lums.db
```

Check:

```bash
sudo ls -lh /var/lib/lums/lums.db
```

---

## 25. Database Backup

Before structural database changes, create a backup:

```bash
sudo cp /var/lib/lums/lums.db \
        /var/lib/lums/lums.db.backup
```

For migrations, use a more descriptive filename:

```text
lums.db.before-client-schema-fix
```

> [!CAUTION]
> Never modify the production database schema without creating a backup first.

---

## 26. Inspect Database

Open the SQLite database:

```bash
sudo sqlite3 /var/lib/lums/lums.db
```

List tables:

```sql
.tables
```

Inspect the client schema:

```sql
PRAGMA table_info(clients);
```

Exit:

```sql
.quit
```

---

# Git Administration

## 27. Repository

The LUMS source repository is:

```text
/opt/lums-public
```

The Git remote is:

```text
origin
```

Main branch:

```text
main
```

---

## 28. Check Git Status

Always check the working tree before pulling changes:

```bash
cd /opt/lums-public
git status
```

The expected state for a clean deployment repository is:

```text
nothing to commit, working tree clean
```

---

## 29. Check Remote Changes

Fetch remote metadata:

```bash
git fetch origin
```

Check commits that exist remotely but not locally:

```bash
git log HEAD..origin/main --oneline
```

---

## 30. Update the Repository

If the working tree is clean:

```bash
git pull --ff-only origin main
```

Using `--ff-only` prevents Git from silently creating an unwanted merge commit.

> [!WARNING]
> Do not use `git reset --hard` or force-push as a routine synchronization method.

---

## 31. Verify Repository State

```bash
git status
```

Then:

```bash
git log -1 --oneline
```

For an exact synchronization check:

```bash
git fetch origin && git rev-list --left-right --count HEAD...origin/main
```

Expected:

```text
0       0
```

This means:

```text
Local commits ahead:  0
Remote commits ahead: 0
```

---

# Deployment

## 32. Deployment Flow

The recommended deployment flow is:

```text
GitHub
   │
   ▼
git fetch
   │
   ▼
git pull --ff-only
   │
   ▼
Syntax check
   │
   ▼
rsync
   │
   ▼
/opt/lums-api
   │
   ▼
systemctl restart lums
   │
   ▼
Health check
```

---

## 33. Pre-Deployment Checks

Before deploying:

```bash
cd /opt/lums-public
git status
```

Then verify Python syntax:

```bash
python3 -m py_compile \
    server/app.py \
    server/init_db.py \
    agent/agent.py
```

Check Git differences:

```bash
git diff --check
```

> [!IMPORTANT]
> Deployment should stop if the syntax check or Git validation fails.

---

## 34. Deploy Server Code

The server application can be synchronized using:

```bash
sudo rsync -a \
    --delete \
    --exclude='.git/' \
    /opt/lums-public/server/ \
    /opt/lums-api/
```

The deployment directory contains application code only.

The following must remain outside the deployment:

```text
/var/lib/lums/lums.db
/etc/lums.env
/etc/nginx/ssl/
/etc/default/lums-agent
```

---

## 35. Restart LUMS

After deployment:

```bash
sudo systemctl restart lums
```

Check:

```bash
sudo systemctl status lums
```

Then test:

```bash
curl -k https://192.168.2.229/api/health
```

---

## 36. Agent Deployment

When the agent source changes, synchronize the agent:

```bash
sudo install -m 0755 \
    /opt/lums-public/agent/agent.py \
    /opt/lums-agent/agent.py
```

Then perform a syntax check:

```bash
python3 -m py_compile /opt/lums-public/agent/agent.py
```

Restart is normally not required for a oneshot agent because the script is executed when the service starts.

A manual test can be performed with:

```bash
sudo systemctl start lums-agent
```

---

# Troubleshooting

## 37. Recommended Troubleshooting Order

When something stops working, do **not** immediately reinstall LUMS.

Check the layers in order:

```text
1. Network
      │
2. TLS
      │
3. Nginx
      │
4. Flask / systemd
      │
5. Authentication
      │
6. Database
      │
7. Client Agent
      │
8. APT / Package Management
```

This makes it possible to identify the actual failing layer.

---

## 38. Basic Diagnostic Sequence

### Server

```bash
sudo systemctl status lums
```

### Nginx

```bash
sudo nginx -t
```

### API

```bash
curl -k https://192.168.2.229/api/health
```

### Logs

```bash
sudo journalctl -u lums -n 100 --no-pager
```

### Agent

```bash
sudo systemctl status lums-agent
```

### Agent logs

```bash
sudo journalctl -u lums-agent -n 100 --no-pager
```

### Timer

```bash
systemctl list-timers --all | grep lums
```

---

# Security Administration

## 39. Security Rules

The following rules apply to the LUMS environment.

### Never commit

```text
/etc/lums.env
/etc/nginx/ssl/lums.key
/etc/default/lums-agent
client tokens
database files containing sensitive data
```

### Never publish

```text
server secrets
client tokens
TLS private keys
production database contents
authentication hashes
```

### Always protect

```text
/var/lib/lums/
/etc/lums.env
/etc/nginx/ssl/
```

---

## 40. Operational Principles

LUMS follows several important operational principles:

1. **Do not reinstall before identifying the failing layer.**
2. **Back up the database before structural changes.**
3. **Validate configuration before restarting services.**
4. **Use Git for source-code synchronization.**
5. **Keep runtime state outside the Git deployment tree.**
6. **Never commit secrets.**
7. **Use HTTPS for client/server communication.**
8. **Authenticate clients with Bearer tokens.**
9. **Store client token hashes rather than plaintext tokens.**
10. **Do not automatically reboot managed systems.**
11. **Keep update execution on the client.**
12. **Use `--ff-only` for routine Git synchronization.**

---

# Quick Reference

## Server

```text
Source:
    /opt/lums-public

Application:
    /opt/lums-api

Database:
    /var/lib/lums/lums.db

Environment:
    /etc/lums.env

TLS certificate:
    /etc/nginx/ssl/lums.crt

TLS key:
    /etc/nginx/ssl/lums.key

Service:
    lums.service
```

## Client

```text
Source:
    /opt/lums-public/agent/agent.py

Installed agent:
    /opt/lums-agent/agent.py

Configuration:
    /etc/default/lums-agent

Service:
    lums-agent.service

Timer:
    lums-agent.timer
```

## Important API Endpoints

| Endpoint                   | Purpose                       |
| -------------------------- | ----------------------------- |
| `/api/health`              | API health check              |
| `/api/client/me`           | Authenticated client identity |
| `/api/report`              | Client inventory/report       |
| Client job endpoint        | Retrieve pending update jobs  |
| Client job-result endpoint | Submit job result             |

---

# Final Checklist

Before considering a LUMS deployment complete:

* [ ] Git working tree is clean
* [ ] Repository is synchronized with `origin/main`
* [ ] `git diff --check` passes
* [ ] Python syntax checks pass
* [ ] Nginx configuration passes
* [ ] `lums.service` is running
* [ ] `/api/health` responds successfully
* [ ] TLS certificate contains the correct SAN
* [ ] Database exists
* [ ] Client token configuration is valid
* [ ] `lums-agent.service` executes successfully
* [ ] `lums-agent.timer` is active
* [ ] Client reports reach the server
* [ ] Update jobs can be retrieved
* [ ] Update results can be submitted
* [ ] No secrets are present in Git

---

> **LUMS — Linux Update Management without the noise.**
>
> Centralize the management. Keep execution controlled.
> **Know what changed. Know where it happened.**
