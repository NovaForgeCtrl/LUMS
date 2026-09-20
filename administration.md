# LUMS Administration Guide

> **Linux Update Management Server**
>
> Centralized update management, client inventory, reporting and controlled package deployment for Linux systems.

---

## Overview

This guide describes the day-to-day administration of **LUMS**, including:

- server administration
- Docker container management
- client and agent management
- update jobs
- package inventory
- database maintenance
- TLS and authentication
- Git-based deployment
- troubleshooting
- backups and recovery
- security-related administration

LUMS is designed to keep the management layer centralized while keeping update execution on the individual Linux clients.

The current deployment uses:

```text
Git
 ↓
Docker Image
 ↓
Docker Container
 ↓
Flask Application
 ↓
SQLite Volume
```

Nginx provides the external HTTPS endpoint.

---

# 1. System Architecture

```text
                         ┌─────────────────────┐
                         │      Web Browser     │
                         └──────────┬──────────┘
                                    │
                              HTTPS :443
                                    │
                         ┌──────────▼──────────┐
                         │       Nginx         │
                         │                     │
                         │ TLS / Reverse Proxy │
                         └──────────┬──────────┘
                                    │
                              HTTP localhost
                                    │
                           127.0.0.1:5050
                                    │
                         ┌──────────▼──────────┐
                         │    Docker Container  │
                         │        "lums"        │
                         │                      │
                         │       Flask          │
                         │ Authentication       │
                         │ Authorization        │
                         │ Client Management    │
                         │ Reporting            │
                         │ Update Jobs          │
                         │ Audit Logging        │
                         └──────────┬───────────┘
                                    │
                              /var/lib/lums
                                    │
                         ┌──────────▼──────────┐
                         │       SQLite        │
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

The important network boundary is:

```text
Internet / LAN
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

The Flask application is **not directly exposed to the network**.

---

# 2. Current Runtime Architecture

The current LUMS server uses:

```text
Nginx
   │
   └── HTTPS :443
          │
          ▼
127.0.0.1:5050
          │
          ▼
Docker container "lums"
          │
          └── Flask :5000
                 │
                 ▼
            lums-data
                 │
                 ▼
              lums.db
```

The Docker container is configured with:

```text
Container name:
    lums

Image:
    lums:latest

Restart policy:
    unless-stopped

Host binding:
    127.0.0.1:5050

Container port:
    5000

Persistent volume:
    lums-data

Container database path:
    /var/lib/lums/lums.db
```

---

# 3. Current Server Configuration

| Component | Current configuration |
|---|---|
| Server IP | `IP Address` |
| Source repository | `/opt/lums-public` |
| Docker container | `lums` |
| Docker image | `lums:latest` |
| Docker volume | `lums-data` |
| Flask container port | `5000` |
| Host application port | `127.0.0.1:5050` |
| HTTPS | `443` |
| HTTP | `80` |
| Environment file | `/etc/lums/docker/lums.env` |
| Database inside container | `/var/lib/lums/lums.db` |
| Certificate | `/etc/nginx/ssl/lums/lums.crt` |
| Private key | `/etc/nginx/ssl/lums/lums.key` |

> [!NOTE]
> `IP Address` is the current laboratory server address.
>
> When reusing this documentation on another installation, replace the address with the actual LUMS server address.

For generic commands, this documentation uses:

```text
SERVER_IP
```

---

# 4. Runtime Layout

## Server

| Component | Location |
|---|---|
| Source repository | `/opt/lums-public` |
| Docker container | `lums` |
| Docker image | `lums:latest` |
| Docker volume | `lums-data` |
| Application inside container | `/` |
| Database inside container | `/var/lib/lums/lums.db` |
| Environment file | `/etc/lums/docker/lums.env` |
| Nginx configuration | `/etc/nginx/` |
| TLS certificate | `/etc/nginx/ssl/lums/lums.crt` |
| TLS private key | `/etc/nginx/ssl/lums/lums.key` |

## Client

| Component | Location |
|---|---|
| Agent source | `/opt/lums-public/agent/agent.py` |
| Installed agent | `/opt/lums-agent/agent.py` |
| Agent configuration | `/etc/default/lums-agent` |
| CA certificate | `/opt/lums-agent/lums-ca.crt` |
| systemd service | `lums-agent.service` |
| systemd timer | `lums-agent.timer` |

---

# 5. Important Paths

The following paths contain operationally important information.

```text
/etc/lums/docker/lums.env
/etc/nginx/ssl/lums/lums.key
/etc/nginx/ssl/lums/lums.crt
/etc/default/lums-agent
/opt/lums-agent/agent.py
/opt/lums-agent/lums-ca.crt
```

The database is stored inside the Docker volume:

```text
lums-data:/var/lib/lums/lums.db
```

> [!CAUTION]
> A Git deployment must never replace:
>
> - the Docker environment file
> - the Docker volume
> - the TLS private key
> - the agent token configuration
> - the production database

---

# 6. Docker Container Administration

## Check container

```bash
sudo docker ps --filter name=^/lums$
```

Expected state:

```text
Up
```

## Check all containers

```bash
sudo docker ps -a
```

## Inspect container

```bash
sudo docker inspect lums
```

## Check container state

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Expected:

```text
running
```

## Check restart policy

```bash
sudo docker inspect \
    --format '{{.HostConfig.RestartPolicy.Name}}' \
    lums
```

Expected:

```text
unless-stopped
```

---

# 7. Start LUMS

If the container already exists but is stopped:

```bash
sudo docker start lums
```

Check:

```bash
sudo docker ps --filter name=^/lums$
```

---

# 8. Stop LUMS

```bash
sudo docker stop lums
```

> [!WARNING]
> Stopping the container interrupts the LUMS web interface and API.
>
> The persistent database remains in the `lums-data` volume.

---

# 9. Restart LUMS

```bash
sudo docker restart lums
```

Check:

```bash
sudo docker ps --filter name=^/lums$
```

Then inspect recent logs:

```bash
sudo docker logs --tail 100 lums
```

---

# 10. Docker Logs

Follow the LUMS logs:

```bash
sudo docker logs -f lums
```

Show recent logs:

```bash
sudo docker logs --tail 100 lums
```

Show logs from the last few minutes:

```bash
sudo docker logs --since 10m lums
```

Search for errors:

```bash
sudo docker logs lums 2>&1 | grep -iE 'error|exception|traceback|failed'
```

> [!IMPORTANT]
> Do not publish logs containing tokens, secrets, session information or other sensitive data.

---

# 11. Nginx Administration

Check configuration:

```bash
sudo nginx -t
```

Reload configuration:

```bash
sudo systemctl reload nginx
```

Check service:

```bash
sudo systemctl status nginx --no-pager
```

Restart if required:

```bash
sudo systemctl restart nginx
```

View recent logs:

```bash
sudo journalctl -u nginx -n 100 --no-pager
```

Follow logs:

```bash
sudo journalctl -u nginx -f
```

---

# 12. Network Ports

Check listening ports:

```bash
sudo ss -lntp
```

The intended application binding is:

```text
127.0.0.1:5050
```

The Flask container itself listens on:

```text
5000
```

Port `5000` must not be exposed directly to the network.

Check Docker port mapping:

```bash
sudo docker port lums
```

Expected:

```text
5000/tcp -> 127.0.0.1:5050
```

The public endpoint is:

```text
https://SERVER_IP/
```

through Nginx.

---

# 13. HTTPS Health Check

The LUMS API provides:

```text
/api/health
```

Generic test:

```bash
curl -k https://SERVER_IP/api/health
```

Current laboratory server:

```bash
curl -k https://IP Address/api/health
```

Expected response:

```json
{
  "service": "LUMS API",
  "status": "ok"
}
```

> [!NOTE]
> `-k` disables certificate verification and should only be used for diagnostic testing.
>
> Normal client operation uses the configured CA certificate.

---

# 14. Local Docker Health Check

The Docker application can also be tested locally through the host binding:

```bash
curl -I http://127.0.0.1:5050/
```

This tests:

```text
Host
 ↓
127.0.0.1:5050
 ↓
Docker
 ↓
Flask
```

It does not test the complete external TLS path.

For the complete path use:

```bash
curl -k -I https://SERVER_IP/
```

---

# 15. TLS Certificate

Certificate:

```text
/etc/nginx/ssl/lums/lums.crt
```

Private key:

```text
/etc/nginx/ssl/lums/lums.key
```

Check certificate:

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

The current laboratory certificate should contain:

```text
IP Address:IP Address
```

The client must connect using an address contained in the certificate SAN.

---

# 16. TLS Private Key

Protect the private key:

```bash
sudo chown root:root \
    /etc/nginx/ssl/lums/lums.key

sudo chmod 600 \
    /etc/nginx/ssl/lums/lums.key
```

Check:

```bash
sudo ls -l /etc/nginx/ssl/lums/
```

> [!CAUTION]
> Never commit the TLS private key to Git.
>
> Never publish it in documentation, screenshots or issue reports.

---

# 17. Server Environment

The Docker environment file is:

```text
/etc/lums/docker/lums.env
```

It is passed to the container when the container is created:

```bash
--env-file /etc/lums/docker/lums.env
```

Protect it:

```bash
sudo chown root:root \
    /etc/lums/docker/lums.env

sudo chmod 600 \
    /etc/lums/docker/lums.env
```

Check permissions:

```bash
sudo ls -l /etc/lums/docker/lums.env
```

Check whether the secret exists without displaying it:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' \
    /etc/lums/docker/lums.env \
    && echo "Secret vorhanden" \
    || echo "Secret fehlt"
```

> [!CAUTION]
> Never use `cat` on the environment file when recording terminal output for documentation or public reports.

---

# 18. Agent Architecture

The LUMS agent runs as a systemd oneshot service.

The timer starts the service periodically:

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
        ├── query client identity
        ├── check update jobs
        └── execute approved updates
```

The agent does not remain permanently running.

After a successful execution, the oneshot service normally returns to:

```text
inactive (dead)
```

with:

```text
status 0/SUCCESS
```

This is expected behavior.

---

# 19. Agent Configuration

The configuration is:

```text
/etc/default/lums-agent
```

Example:

```ini
LUMS_BASE=https://SERVER_IP
LUMS_TOKEN=CLIENT_TOKEN
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

Current laboratory server:

```ini
LUMS_BASE=https://IP Address
```

The real token must never be placed in documentation.

---

# 20. Agent Configuration Permissions

Protect the configuration:

```bash
sudo chown root:root \
    /etc/default/lums-agent

sudo chmod 600 \
    /etc/default/lums-agent
```

Check:

```bash
sudo ls -l /etc/default/lums-agent
```

Display safe values without exposing the token:

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

# 21. Agent CA Certificate

The agent uses:

```text
/opt/lums-agent/lums-ca.crt
```

Check:

```bash
sudo ls -l /opt/lums-agent/lums-ca.crt
```

Inspect:

```bash
sudo openssl x509 \
    -in /opt/lums-agent/lums-ca.crt \
    -noout \
    -subject \
    -dates
```

The CA configuration must remain enabled.

Do not disable certificate verification as a permanent workaround.

---

# 22. Check Agent Service

```bash
sudo systemctl status lums-agent.service --no-pager
```

Run manually:

```bash
sudo systemctl start lums-agent.service
```

View recent logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Follow logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -f
```

---

# 23. Check Agent Timer

```bash
sudo systemctl status lums-agent.timer --no-pager
```

List LUMS timers:

```bash
systemctl list-timers --all | grep lums
```

Enable the timer:

```bash
sudo systemctl enable --now lums-agent.timer
```

Check the next execution:

```bash
systemctl list-timers --all | grep lums-agent
```

> [!IMPORTANT]
> Enable the timer, not the oneshot service, for normal periodic operation.

---

# 24. Manual Agent Test

Run the agent manually through systemd:

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

A successful run may report information such as:

```text
LUMS API: {"status":"received"}
Kein Update-Job vorhanden.
```

This indicates that the agent was able to communicate with the LUMS server and complete its current workflow.

---

# 25. Client Authentication

LUMS clients authenticate using Bearer tokens.

Requests contain:

```http
Authorization: Bearer <client-token>
```

The server stores a SHA-256 hexadecimal representation of the client token rather than the plaintext token.

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

A client token must:

- exist
- match the stored SHA-256 digest
- belong to the correct client
- belong to an enabled client
- not be revoked

---

# 26. Client Identity

Authenticated agents use:

```text
GET /api/client/me
```

to obtain their authenticated client context.

The server must determine client identity from the authenticated token.

Client-supplied identifiers must not be treated as trusted authorization information.

---

# 27. Client Registration

Clients can be registered through the LUMS administration interface.

Client information can include:

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

The hostname is optional.

This allows initial registration using client information that may not yet include a hostname.

---

# 28. Client Status

LUMS uses the last successful report to determine client activity.

Current status interpretation:

| Last Seen | Status |
|---:|---|
| `≤ 120 seconds` | Online |
| `121–600 seconds` | Unknown |
| `> 600 seconds` | Offline |

The agent normally runs through the systemd timer.

The timer interval is approximately:

```text
15 minutes
```

Therefore, a client can temporarily appear as unknown or offline without necessarily indicating a failure.

The status thresholds and timer interval should be considered separately:

```text
Agent execution frequency
        ≠
Status threshold
```

---

# 29. Client Inventory

The inventory shown by LUMS represents information submitted by the client during its latest successful report.

It is not a live query against the client.

Information can include:

- operating system
- kernel
- architecture
- agent version
- installed packages
- available packages

The inventory timestamp should therefore always be considered when interpreting the data.

---

# 30. Update Management

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

The server manages the job.

The client performs the actual package operation.

---

# 31. Package Installation

Approved packages are installed on the client through APT.

The agent uses:

```bash
apt-get install --only-upgrade -y <package>
```

This intentionally performs package updates without requesting a complete distribution upgrade.

APT remains responsible for:

- dependency resolution
- repository handling
- package signatures
- package installation
- dpkg operations

---

# 32. Automatic Reboots

LUMS does not automatically reboot clients.

A reboot requirement can be detected using:

```text
/var/run/reboot-required
```

Check manually:

```bash
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot required"
```

A required reboot remains an administrative decision.

---

# 33. Database Architecture

LUMS uses SQLite.

The database is stored inside the Docker volume:

```text
lums-data
```

Inside the container:

```text
/var/lib/lums/lums.db
```

The volume provides persistence across container recreation.

```text
Docker Container
      │
      ▼
/var/lib/lums
      │
      ▼
Docker Volume
      │
      ▼
lums-data
```

The database must never be stored only inside the writable container filesystem.

---

# 34. Database Inspection

Enter the container:

```bash
sudo docker exec -it lums /bin/sh
```

The database is:

```text
/var/lib/lums/lums.db
```

Exit the container:

```bash
exit
```

For an integrity check without an interactive shell:

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

---

# 35. Database Backup

Do not use a simple filesystem copy while SQLite is actively being modified unless the database is safely quiesced.

For the running container, use SQLite's backup mechanism.

Create a backup directory:

```bash
sudo install -d -m 700 /var/backups/lums
```

Create a temporary SQLite backup inside the container:

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

Copy the backup to the host:

```bash
sudo docker cp \
    lums:/var/lib/lums/lums.backup.db \
    "/var/backups/lums/lums-$(date +%F_%H-%M-%S).db"
```

Remove the temporary backup:

```bash
sudo docker exec \
    lums \
    rm -f /var/lib/lums/lums.backup.db
```

Protect backups:

```bash
sudo find /var/backups/lums \
    -type f \
    -name "*.db" \
    -exec chmod 600 {} \;
```

---

# 36. Database Restore

A database restore is a controlled maintenance operation.

Before restoring:

1. Stop the LUMS container.
2. Create a backup of the current database.
3. Verify the restore source.
4. Restore the database.
5. Check ownership and permissions.
6. Start the container.
7. Run `PRAGMA integrity_check`.
8. Test administrator authentication.
9. Test client authentication.
10. Test client reporting.
11. Test update-job functionality.

Never overwrite the only available database copy.

---

# 37. Docker Volume Protection

Check the volume:

```bash
sudo docker volume inspect lums-data
```

List volumes:

```bash
sudo docker volume ls
```

The volume must remain available during normal container updates.

> [!CAUTION]
> Removing the container is not the same as removing the volume.
>
> The container can be recreated safely while the persistent volume remains intact.

Do not run:

```bash
sudo docker volume rm lums-data
```

unless the database has been intentionally backed up and the volume is deliberately being removed.

---

# 38. Git Repository

The source repository is:

```text
/opt/lums-public
```

Check:

```bash
cd /opt/lums-public
git status
```

The expected clean state is:

```text
nothing to commit, working tree clean
```

Check the current commit:

```bash
git log -1 --oneline --decorate
```

Check the configured remote:

```bash
git remote -v
```

---

# 39. Git Remote Synchronization

Fetch remote metadata:

```bash
cd /opt/lums-public
git fetch origin
```

Check remote commits:

```bash
git log HEAD..origin/main --oneline
```

Check local and remote divergence:

```bash
git rev-list --left-right --count HEAD...origin/main
```

Expected after synchronization:

```text
0       0
```

This means:

```text
Local commits ahead:  0
Remote commits ahead: 0
```

---

# 40. Update Git Repository

Only update a clean working tree.

Check:

```bash
cd /opt/lums-public
git status --short
```

If clean:

```bash
git pull --ff-only origin main
```

Then:

```bash
git status
```

And:

```bash
git log -1 --oneline --decorate
```

> [!IMPORTANT]
> `--ff-only` prevents Git from creating an unexpected merge commit during routine deployment.

---

# 41. Pre-Deployment Validation

Before rebuilding the Docker image:

```bash
cd /opt/lums-public
```

Check repository:

```bash
git status
```

Check whitespace errors:

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

If the project contains additional Python modules, validate those as well.

Do not deploy if validation fails.

---

# 42. Docker Image Build

Build the current application image:

```bash
cd /opt/lums-public

sudo docker build \
    -t lums:latest \
    .
```

Check the resulting image:

```bash
sudo docker images lums
```

Inspect:

```bash
sudo docker image inspect lums:latest
```

---

# 43. Docker Deployment

Before replacing the running container, verify:

```bash
sudo docker ps --filter name=^/lums$
sudo docker volume inspect lums-data
sudo ls -l /etc/lums/docker/lums.env
```

Stop the existing container:

```bash
sudo docker stop lums
```

Remove only the container:

```bash
sudo docker rm lums
```

> [!CAUTION]
> Do not remove `lums-data`.

Start the new container:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
```

Check:

```bash
sudo docker ps --filter name=^/lums$
```

Then:

```bash
sudo docker logs --tail 100 lums
```

---

# 44. Post-Deployment Validation

After deployment, verify the container:

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

Check HTTPS:

```bash
curl -k -I https://SERVER_IP/
```

Check API health:

```bash
curl -k https://SERVER_IP/api/health
```

Check Nginx:

```bash
sudo nginx -t
```

Check the agent afterwards:

```bash
sudo systemctl start lums-agent.service
```

Then:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 50 \
    --no-pager
```

---

# 45. Deployment Flow

The current deployment flow is:

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
Validation
   │
   ├── git diff --check
   └── Python syntax checks
   │
   ▼
docker build
   │
   ▼
Stop old container
   │
   ▼
Remove old container
   │
   ▼
Keep lums-data
   │
   ▼
Start new container
   │
   ▼
Health check
   │
   ▼
Agent test
```

The persistent data remains outside the image.

---

# 46. What Git Deployment Does Not Replace

A Git deployment replaces application source code through the Docker image.

It must not replace:

```text
/etc/lums/docker/lums.env
/etc/nginx/ssl/lums/lums.key
/etc/nginx/ssl/lums/lums.crt
/etc/default/lums-agent
/opt/lums-agent/lums-ca.crt
lums-data
```

These are runtime or environment-specific resources.

---

# 47. Troubleshooting Strategy

When something stops working:

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

LUMS consists of several layers:

```text
┌──────────────────────────┐
│       Web Browser        │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│         Nginx            │
│       HTTP / HTTPS       │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│      Docker / Flask      │
│       LUMS API           │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│        SQLite            │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│       LUMS Agent         │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│       APT / dpkg         │
└──────────────────────────┘
```

Troubleshoot from the outside toward the inside.

---

# 48. Basic Diagnostic Sequence

## Step 1 — Network

```bash
ping SERVER_IP
```

## Step 2 — Ports

```bash
sudo ss -lntp
```

## Step 3 — Nginx

```bash
sudo nginx -t
```

## Step 4 — Docker

```bash
sudo docker ps -a
```

## Step 5 — Container

```bash
sudo docker logs --tail 100 lums
```

## Step 6 — Local API

```bash
curl -I http://127.0.0.1:5050/
```

## Step 7 — HTTPS

```bash
curl -k -I https://SERVER_IP/
```

## Step 8 — API

```bash
curl -k https://SERVER_IP/api/health
```

## Step 9 — Agent

```bash
sudo systemctl status lums-agent.timer --no-pager
```

## Step 10 — Agent execution

```bash
sudo systemctl start lums-agent.service
```

## Step 11 — Agent logs

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 49. Common Problem: Container Not Running

Check:

```bash
sudo docker ps -a --filter name=^/lums$
```

Check logs:

```bash
sudo docker logs --tail 200 lums
```

Inspect state:

```bash
sudo docker inspect \
    --format '{{json .State}}' \
    lums
```

If necessary:

```bash
sudo docker restart lums
```

Do not delete the database volume as a first troubleshooting step.

---

# 50. Common Problem: Port 5050

Check:

```bash
sudo ss -lntp | grep ':5050'
```

Check Docker:

```bash
sudo docker port lums
```

Expected:

```text
5000/tcp -> 127.0.0.1:5050
```

Test locally:

```bash
curl -I http://127.0.0.1:5050/
```

If this fails, investigate Docker and Flask before investigating the browser or TLS.

---

# 51. Common Problem: Nginx

Validate:

```bash
sudo nginx -t
```

Check:

```bash
sudo systemctl status nginx --no-pager
```

View logs:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Test backend:

```bash
curl -I http://127.0.0.1:5050/
```

If the backend works but HTTPS does not, investigate Nginx and TLS.

---

# 52. Common Problem: TLS

Inspect certificate:

```bash
sudo openssl x509 \
    -in /etc/nginx/ssl/lums/lums.crt \
    -noout \
    -subject \
    -dates
```

Inspect SAN:

```bash
sudo openssl x509 \
    -in /etc/nginx/ssl/lums/lums.crt \
    -noout \
    -ext subjectAltName
```

Check the client CA:

```bash
sudo openssl x509 \
    -in /opt/lums-agent/lums-ca.crt \
    -noout \
    -subject \
    -dates
```

Do not disable TLS verification as the permanent fix.

---

# 53. Common Problem: Agent Authentication

Check configuration safely:

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

Check agent logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Check server logs:

```bash
sudo docker logs --tail 200 lums
```

Verify:

```text
LUMS_BASE
LUMS_TOKEN
LUMS_CA_FILE
```

The token stored in the client configuration must correspond to the token hash stored for that client.

---

# 54. Common Problem: Agent Timer

Check:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

List timers:

```bash
systemctl list-timers --all | grep lums-agent
```

Enable:

```bash
sudo systemctl enable --now lums-agent.timer
```

Trigger a manual run:

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

# 55. Common Problem: Client Appears Offline

Check the timer:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

Run the agent manually:

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

Then check the LUMS web interface.

Possible causes include:

```text
timer not running
network failure
TLS failure
invalid token
server unavailable
agent exception
database issue
```

Do not immediately reinstall the agent.

---

# 56. Common Problem: Update Job Not Executed

Check whether the client can authenticate.

Then:

```bash
sudo systemctl start lums-agent.service
```

Inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Check server logs:

```bash
sudo docker logs --tail 200 lums
```

Then verify the client has:

```text
enabled = true
valid authentication token
pending job
correct package name
working APT repositories
```

---

# 57. Common Problem: APT Failure

The LUMS server does not replace APT.

Check the client directly:

```bash
sudo apt update
```

Check package information:

```bash
apt-cache policy <package>
```

Check whether the package is installed:

```bash
dpkg -l <package>
```

Check pending updates:

```bash
apt list --upgradable
```

If APT itself is broken, resolve the client-side APT problem before troubleshooting LUMS.

---

# 58. Common Problem: Database Integrity

Run:

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

1. Stop normal administrative changes.
2. Preserve the database.
3. Create a backup copy.
4. Review recent logs.
5. Determine whether a valid backup exists.
6. Restore only after the situation is understood.

---

# 59. Security Administration

Never commit:

```text
/etc/lums/docker/lums.env
/etc/nginx/ssl/lums/lums.key
/etc/default/lums-agent
client tokens
production databases
database backups
private certificates
```

Never publish:

```text
server secrets
client tokens
TLS private keys
authentication hashes
production database contents
session secrets
```

Always protect:

```text
/etc/lums/docker/lums.env
/etc/nginx/ssl/lums/
etc/default/lums-agent
lums-data
```

---

# 60. File Permission Review

Review:

```bash
sudo ls -l /etc/lums/docker/lums.env
sudo ls -l /etc/default/lums-agent
sudo ls -l /etc/nginx/ssl/lums/
```

Recommended:

```text
Environment file:
    0600

Agent configuration:
    0600

TLS private key:
    0600

Public certificate:
    0644
```

Review permissions after:

- installation
- deployment
- manual changes
- certificate replacement
- configuration changes
- database restoration

---

# 61. Git Security

Before committing:

```bash
cd /opt/lums-public
git status
git diff --check
git diff
```

Check tracked files:

```bash
git ls-files
```

Search for potentially sensitive files:

```bash
find . \
    -type f \
    \( \
        -name "*.env" \
        -o -name "*.key" \
        -o -name "*.pem" \
        -o -name "*.db" \
    \)
```

No secrets should be committed.

Use placeholders in documentation:

```text
SERVER_IP
CLIENT_IP
CLIENT_TOKEN
ADMIN_PASSWORD
```

---

# 62. Git Identity

The configured repository identity is:

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

# 63. Backup Strategy

Important LUMS data includes:

```text
SQLite database
Docker environment configuration
TLS configuration
Agent configuration
Certificates
Git repository
```

The most important persistent application state is:

```text
lums-data
```

A backup should include the database and required configuration.

Do not rely only on the Git repository.

Git contains application source code.

Git does not contain:

```text
database state
client tokens
server secrets
TLS private keys
runtime configuration
```

---

# 64. Recovery Strategy

A basic recovery sequence is:

```text
1. Restore operating system
        ↓
2. Install Docker
        ↓
3. Restore LUMS repository
        ↓
4. Restore environment file
        ↓
5. Restore TLS configuration
        ↓
6. Restore lums-data / database
        ↓
7. Build Docker image
        ↓
8. Start LUMS container
        ↓
9. Configure Nginx
        ↓
10. Test HTTPS
        ↓
11. Test authentication
        ↓
12. Test agent
        ↓
13. Test update jobs
```

Recovery should always be tested against a known backup.

---

# 65. Maintenance

Regularly review:

```text
Docker image
Operating system
Python dependencies
Flask dependencies
Nginx
TLS certificates
Agent source
Agent configuration
Database backups
Git repository
Authentication
Authorization
```

Before major changes:

```text
Backup
 ↓
Change
 ↓
Validate
 ↓
Test
 ↓
Document
```

---

# 66. Operational Principles

LUMS follows these principles:

1. Do not reinstall before identifying the failing layer.
2. Keep persistent data outside the Docker image.
3. Keep secrets outside Git.
4. Keep the Flask application behind Nginx.
5. Bind the Docker application to localhost only.
6. Use HTTPS for client/server communication.
7. Keep TLS verification enabled.
8. Separate authentication from authorization.
9. Store client token hashes rather than plaintext tokens.
10. Keep update execution on the client.
11. Do not automatically reboot managed systems.
12. Back up the database before structural changes.
13. Validate configuration before restarting services.
14. Use `git pull --ff-only` for routine synchronization.
15. Preserve the Docker volume during application deployments.
16. Test every security-sensitive change.
17. Document configuration changes.
18. Do not expose secrets in logs or screenshots.

---

# 67. Quick Reference — Server

```text
Repository:
    /opt/lums-public

Docker container:
    lums

Docker image:
    lums:latest

Docker volume:
    lums-data

Database inside container:
    /var/lib/lums/lums.db

Environment:
    /etc/lums/docker/lums.env

TLS certificate:
    /etc/nginx/ssl/lums/lums.crt

TLS private key:
    /etc/nginx/ssl/lums/lums.key

Application binding:
    127.0.0.1:5050

Container port:
    5000

HTTPS:
    443

HTTP:
    80
```

---

# 68. Quick Reference — Client

```text
Source:
    /opt/lums-public/agent/agent.py

Installed agent:
    /opt/lums-agent/agent.py

Configuration:
    /etc/default/lums-agent

CA certificate:
    /opt/lums-agent/lums-ca.crt

Service:
    lums-agent.service

Timer:
    lums-agent.timer
```

---

# 69. Quick Reference — Docker

## Status

```bash
sudo docker ps --filter name=^/lums$
```

## Logs

```bash
sudo docker logs --tail 100 lums
```

## Restart

```bash
sudo docker restart lums
```

## Inspect

```bash
sudo docker inspect lums
```

## Volume

```bash
sudo docker volume inspect lums-data
```

## Port mapping

```bash
sudo docker port lums
```

---

# 70. Quick Reference — Agent

## Timer

```bash
sudo systemctl status lums-agent.timer --no-pager
```

## Manual execution

```bash
sudo systemctl start lums-agent.service
```

## Logs

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

## Next execution

```bash
systemctl list-timers --all | grep lums-agent
```

---

# 71. Quick Reference — Health Checks

## Docker

```bash
sudo docker ps --filter name=^/lums$
```

## Local backend

```bash
curl -I http://127.0.0.1:5050/
```

## Nginx

```bash
sudo nginx -t
```

## HTTPS

```bash
curl -k -I https://SERVER_IP/
```

## API

```bash
curl -k https://SERVER_IP/api/health
```

## Agent

```bash
sudo systemctl start lums-agent.service
```

## Agent logs

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 50 \
    --no-pager
```

---

# 72. Final Deployment Checklist

Before considering a LUMS deployment complete:

- [ ] Git working tree is clean
- [ ] Repository is synchronized with `origin/main`
- [ ] `git diff --check` passes
- [ ] Python syntax checks pass
- [ ] Docker image builds successfully
- [ ] `lums` container is running
- [ ] `lums-data` volume is mounted
- [ ] Application is bound to `127.0.0.1:5050`
- [ ] Port `5000` is not directly exposed
- [ ] Nginx configuration passes
- [ ] HTTPS works
- [ ] TLS certificate contains the correct SAN
- [ ] TLS private key permissions are restricted
- [ ] Environment file permissions are restricted
- [ ] `/api/health` responds successfully
- [ ] Administrator authentication works
- [ ] Client authentication works
- [ ] Client authorization works
- [ ] Agent CA certificate is available
- [ ] Agent token configuration is valid
- [ ] `lums-agent.timer` is active
- [ ] `lums-agent.service` executes successfully
- [ ] Client reports reach the server
- [ ] Client inventory is updated
- [ ] Update jobs can be created
- [ ] Update jobs can be retrieved
- [ ] Update results can be submitted
- [ ] Database integrity check returns `ok`
- [ ] Database backup exists
- [ ] No secrets are present in Git
- [ ] Documentation reflects the current deployment

---

# 73. Final Administration Principle

LUMS is designed to centralize Linux update management without removing operational control from the administrator.

The system should remain:

- Transparent
- Auditable
- Controlled
- Secure
- Documented
- Maintainable

The administrator should always know:

```text
What changed
      ↓
Where it changed
      ↓
Which client was affected
      ↓
What the client executed
      ↓
What result was reported
```

> **LUMS — Linux Update Management without the noise.**
>
> **Centralize the management. Keep execution controlled.**
>
> **Know what changed. Know where it happened.**
