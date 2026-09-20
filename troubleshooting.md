
# LUMS Troubleshooting Guide

> **Linux Update Management Server**
>
> A practical troubleshooting guide for diagnosing LUMS,
> Docker, Nginx, TLS, authentication, agents, databases,
> Git and update-management problems.

> **LUMS — Linux Update Management without the noise.**
>
> Centralize the management.  
> Keep execution controlled.  
> Know what changed.  
> Know where it happened.

---

# 1. Golden Rule

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

LUMS consists of several independent components. A failure in one layer does not necessarily mean that the entire system is broken.

Recommended troubleshooting workflow:

```text
Observe
   ↓
Measure
   ↓
Identify the failing layer
   ↓
Change one thing
   ↓
Test again
   ↓
Document the result
```

Do not change several layers at the same time.

---

# 2. Current Architecture

```text
┌───────────────────────────┐
│        Web Browser        │
└─────────────┬─────────────┘
              │ HTTPS :443
              ▼
┌───────────────────────────┐
│          Nginx            │
│      TLS / Reverse Proxy  │
└─────────────┬─────────────┘
              │ HTTP localhost
              ▼
┌───────────────────────────┐
│       Docker Container    │
│           lums            │
│       Flask :5000         │
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│       Docker Volume       │
│         lums-data         │
│    /var/lib/lums/lums.db  │
└───────────────────────────┘


              ▲
              │ HTTPS + Bearer Token
              │
┌─────────────┴─────────────┐
│       Linux Agent         │
│   Python / APT / dpkg     │
│       systemd timers      │
└───────────────────────────┘
```

## Network Flow

```text
Client
   │ HTTPS :443
   ▼
Nginx
   │ HTTP localhost
   ▼
127.0.0.1:5050
   │ Docker port mapping
   ▼
Container port 5000
   │
   ▼
Flask application
```

Expected Docker binding:

```text
127.0.0.1:5050 → 5000/tcp
```

The Flask port is not directly exposed to the network.

---

# 3. Troubleshooting Order

Use this order whenever possible:

```text
Network
   ↓
HTTPS / TLS
   ↓
Nginx
   ↓
Docker
   ↓
Flask
   ↓
Authentication
   ↓
Authorization
   ↓
Agent
   ↓
Client report
   ↓
Update job
   ↓
APT / dpkg
   ↓
Result reporting
```

A successful test at one layer does not automatically prove that all following layers work.

For example:

```text
Ping works
   ≠
TCP/443 works
   ≠
TLS verification works
   ≠
Authentication works
   ≠
Authorization works
```

---

# 4. Important Paths

## Server

| Component | Path |
|---|---|
| Git repository | `/opt/lums-public` |
| Docker image | `lums:latest` |
| Docker container | `lums` |
| Docker volume | `lums-data` |
| Database | `/var/lib/lums/lums.db` |
| Environment file | `/etc/lums/docker/lums.env` |
| Nginx configuration | `/etc/nginx/sites-available/lums` |
| TLS certificate | `/etc/lums/tls/lums.crt` |
| TLS private key | `/etc/lums/tls/lums.key` |

## Client

| Component | Path |
|---|---|
| Installed agent | `/opt/lums-agent/agent.py` |
| Execution watcher | `/opt/lums-agent/watcher.py` |
| CA certificate | `/opt/lums-agent/lums-ca.crt` |
| Agent configuration | `/etc/default/lums-agent` |
| Agent service | `lums-agent.service` |
| Agent timer | `lums-agent.timer` |
| Watcher service | `lums-execution-watcher.service` |
| Watcher timer | `lums-execution-watcher.timer` |

> **CAUTION**
>
> The following resources contain secrets or persistent runtime data:
>
> - `/etc/lums/docker/lums.env`
> - `/etc/default/lums-agent`
> - `/etc/lums/tls/lums.key`
> - Docker volume `lums-data`

These resources must not be overwritten during a normal Git deployment.

---

# 5. Docker Diagnostics

## 5.1 Check the Container

```bash
sudo docker ps -a
```

```bash
sudo docker ps \
    --filter "name=^lums$"
```

## 5.2 Check Container Logs

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Follow logs live:

```bash
sudo docker logs \
    --follow \
    lums
```

## 5.3 Inspect the Container

```bash
sudo docker inspect lums
```

```bash
sudo docker inspect \
    --format '{{.State.Status}} {{.State.ExitCode}}' \
    lums
```

Possible causes:

```text
application error
missing environment variable
database error
incorrect volume
invalid image
port conflict
permission problem
```

Always inspect the first actual application error before recreating the container.

## 5.4 Restart Loop

```bash
sudo docker ps -a \
    --filter "name=^lums$"
```

```bash
sudo docker inspect \
    --format '{{.HostConfig.RestartPolicy}}' \
    lums
```

The configured restart policy is:

```text
unless-stopped
```

The important question is:

> Why does the application stop or fail?

Inspect the Python, Flask, configuration and database errors.

---

# 6. Docker Image

List images:

```bash
sudo docker images
```

Inspect the LUMS image:

```bash
sudo docker image inspect \
    lums:latest
```

Rebuild from the repository:

```bash
cd /opt/lums-public

sudo docker build \
    -t lums:latest \
    .
```

Verify the image:

```bash
sudo docker image inspect \
    lums:latest \
    --format '{{.Id}}'
```

> Rebuilding an image does not automatically delete the `lums-data` volume.

---

# 7. Docker Port Diagnostics

Check published ports:

```bash
sudo docker port lums
```

Expected result:

```text
5000/tcp -> 127.0.0.1:5050
```

Check listening ports:

```bash
sudo ss -lntp | grep -E ':5050|:5000'
```

Test the local Flask endpoint:

```bash
curl -i \
    http://127.0.0.1:5050/
```

A redirect to `/login` can be an expected result.

> **CAUTION**
>
> Do not publish Flask directly to the network merely to simplify troubleshooting.

---

# 8. Docker Volume Diagnostics

List volumes:

```bash
sudo docker volume ls
```

Inspect the LUMS volume:

```bash
sudo docker volume inspect \
    lums-data
```

Inspect container mounts:

```bash
sudo docker inspect \
    --format '{{json .Mounts}}' \
    lums
```

Check the database directory:

```bash
sudo docker exec \
    lums \
    ls -la /var/lib/lums/
```

Never remove the volume as a routine troubleshooting step:

```bash
sudo docker volume rm lums-data
```

Deleting the volume can permanently destroy the LUMS database.

---

# 9. Environment and Secrets

The server environment file is:

```text
/etc/lums/docker/lums.env
```

Check whether it exists:

```bash
sudo ls -l \
    /etc/lums/docker/lums.env
```

Check the secret without displaying its value:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' \
    /etc/lums/docker/lums.env \
    && echo "Secret vorhanden" \
    || echo "Secret fehlt"
```

Check permissions:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/docker/lums.env
```

Expected protection:

```text
root:root 600
```

Never publish:

```text
LUMS_SECRET_KEY
LUMS_TOKEN
passwords
private keys
Authorization headers
session information
```

Avoid:

```bash
cat /etc/lums/docker/lums.env
```

in public bug reports or screenshots.

## 9.1 Inspect Loaded Container Variables

```bash
sudo docker inspect \
    --format '{{json .Config.Env}}' \
    lums
```

The container should be created with the environment file:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
```

Do not place secrets in:

- Dockerfiles
- Git-tracked shell scripts
- public documentation
- GitHub issues
- screenshots

---

# 10. Flask Diagnostics

Test the local application:

```bash
curl -i \
    http://127.0.0.1:5050/
```

Check the container:

```bash
sudo docker ps \
    --filter "name=^lums$"
```

Check logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

A `302 FOUND` redirect to `/login` may indicate that the application is working.

---

# 11. Nginx Diagnostics

Test the configuration:

```bash
sudo nginx -t
```

Check the service:

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

Check logs:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Inspect the active configuration:

```bash
sudo nginx -T
```

Reload only after a successful configuration test:

```bash
sudo nginx -t \
    && sudo systemctl reload nginx
```

---

# 12. Nginx Returns 502

A `502 Bad Gateway` usually means that Nginx cannot reach the upstream application.

Test the upstream directly:

```bash
curl -i \
    http://127.0.0.1:5050/
```

Check the container:

```bash
sudo docker ps \
    --filter "name=^lums$"
```

Check Docker logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Expected upstream:

```text
http://127.0.0.1:5050
```

Expected flow:

```text
Nginx :443
   ↓
127.0.0.1:5050
   ↓
Docker
   ↓
Flask :5000
```

---

# 13. HTTPS and TLS

Check port 443:

```bash
sudo ss -lntp | grep ':443'
```

Test HTTPS locally:

```bash
curl -k -i \
    https://127.0.0.1/
```

Test using the server address:

```bash
curl -k -i \
    https://<LUMS_SERVER_IP>/
```

Test HTTP redirection:

```bash
curl -I \
    http://<LUMS_SERVER_IP>/
```

Check firewall status:

```bash
sudo ufw status verbose
```

A successful local HTTPS test does not prove that remote clients can reach TCP/443.

Investigate separately:

```text
network
routing
firewall
TCP/443
certificate
client trust
```

---

# 14. TLS Certificate Diagnostics

Current certificate paths:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Inspect the certificate:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -dates
```

Inspect the SAN:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -ext subjectAltName
```

The client address must match a Subject Alternative Name in the certificate.

For an IP-based connection, the certificate requires an IP SAN:

```text
IP Address:<LUMS_SERVER_IP>
```

Check private-key permissions:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/tls/lums.key
```

The private key must not be world-readable.

Never permanently disable TLS verification to bypass a certificate problem.

---

# 15. Agent TLS Problems

Check the CA configuration:

```bash
sudo grep '^LUMS_CA_FILE=' \
    /etc/default/lums-agent
```

Check the CA file:

```bash
sudo ls -l \
    /opt/lums-agent/lums-ca.crt
```

Inspect the certificate:

```bash
sudo openssl x509 \
    -in /opt/lums-agent/lums-ca.crt \
    -noout \
    -subject \
    -dates
```

Check the server URL:

```bash
sudo grep '^LUMS_BASE=' \
    /etc/default/lums-agent
```

The configured server hostname or IP must match the certificate SAN.

Do not permanently use insecure TLS options such as disabled certificate verification.

---

# 16. Agent Connectivity

From the client:

```bash
ping <LUMS_SERVER_IP>
```

Test HTTPS:

```bash
curl -k \
    https://<LUMS_SERVER_IP>/
```

On the server:

```bash
sudo ss -lntp | grep ':443'
```

Check the firewall:

```bash
sudo ufw status verbose
```

Test the layers independently:

```text
Ping
   ↓
TCP/443
   ↓
TLS
   ↓
Authentication
   ↓
Authorization
   ↓
API request
```

---

# 17. Agent Authentication

LUMS uses Bearer-token authentication for clients.

Check token presence without displaying it:

```bash
sudo grep -q '^LUMS_TOKEN=.' \
    /etc/default/lums-agent \
    && echo "Token vorhanden" \
    || echo "Token fehlt"
```

Check the server URL:

```bash
sudo grep '^LUMS_BASE=' \
    /etc/default/lums-agent
```

Possible causes of `401 Unauthorized`:

```text
token missing
wrong token
wrong token digest
token revoked
client does not exist
client disabled
incorrect server address
```

The current implementation uses a SHA-256 hexadecimal digest for client authentication.

The stored value must match the current authentication implementation.

> **Security note**
>
> SHA-256 is deterministic. The long-term token-storage architecture should be reviewed as part of future security hardening.

Do not replace the configured digest format with an unrelated password-hashing scheme without changing and testing the complete authentication implementation.

---

# 18. Agent Environment

The agent configuration is:

```text
/etc/default/lums-agent
```

Expected structure:

```dotenv
LUMS_BASE="https://<LUMS_SERVER_IP>"
LUMS_TOKEN="<CLIENT_TOKEN>"
LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt"
```

Check non-secret values:

```bash
sudo grep -E \
    '^(LUMS_BASE|LUMS_CA_FILE)=' \
    /etc/default/lums-agent
```

Check token presence:

```bash
sudo grep -q '^LUMS_TOKEN=.' \
    /etc/default/lums-agent \
    && echo "Token vorhanden" \
    || echo "Token fehlt"
```

Protect the file:

```bash
sudo chown root:root \
    /etc/default/lums-agent
```

```bash
sudo chmod 600 \
    /etc/default/lums-agent
```

Verify:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/default/lums-agent
```

Expected:

```text
root:root 600
```

---

# 19. Manual Agent Execution

A direct Python invocation does not automatically load `/etc/default/lums-agent`.

Use the environment file explicitly:

```bash
sudo bash -c '
set -a
source /etc/default/lums-agent
set +a
exec /usr/bin/python3 /opt/lums-agent/agent.py
'
```

Compare this with:

```bash
sudo systemctl start \
    lums-agent.service
```

systemd supplies the configured environment file and service context.

---

# 20. Agent Returns 403

```text
401 Unauthorized
   ↓
Authentication failed

403 Forbidden
   ↓
Authentication succeeded,
but authorization rejected the request
```

Possible causes:

```text
client disabled
client requesting another client's data
missing permissions
authorization rule rejected the request
```

Diagnostic model:

```text
Network        ✓
TLS            ✓
Authentication ✓
Authorization  ✗
```

Inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 21. Agent Reporting

Check available updates locally:

```bash
apt list --upgradable 2>/dev/null
```

Count available updates:

```bash
apt list --upgradable 2>/dev/null \
    | tail -n +2 \
    | wc -l
```

Check the agent service:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

If updates exist locally but do not appear in LUMS, investigate:

```text
local package state
   ↓
agent collection
   ↓
API report
   ↓
client identity
   ↓
database
   ↓
web interface
```

The inventory reflects the latest successful report received by the server.

---

# 22. Agent Timers

The reporting timer runs approximately every five minutes.

Check the timer:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

List timers:

```bash
systemctl list-timers \
    --all \
    | grep lums-agent
```

Inspect the timer:

```bash
systemctl cat \
    lums-agent.timer
```

Show execution information:

```bash
systemctl show \
    lums-agent.timer \
    -p NextElapseUSecRealtime \
    -p LastTriggerUSec
```

Reload changed unit files:

```bash
sudo systemctl daemon-reload
```

Enable the timer:

```bash
sudo systemctl enable \
    --now \
    lums-agent.timer
```

> Enable the timer, not the oneshot service itself.

A oneshot service may show:

```text
inactive (dead)
```

after successful completion. This is normal when the timer remains active.

---

# 23. Execution Watcher

The execution watcher runs separately from the reporting agent.

Check the timer:

```bash
sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager
```

Check the service:

```bash
sudo systemctl status \
    lums-execution-watcher.service \
    --no-pager
```

Check logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -n 200 \
    --no-pager
```

The watcher uses idle detection where supported.

The current implementation is primarily oriented toward server, terminal and SSH activity. It must not be documented as universal desktop idle detection.

The watcher should only execute a job when:

```text
pending job exists
   ↓
idle detection is supported
   ↓
idle threshold is reached
   ↓
job is claimed atomically
   ↓
execution starts
```

---

# 24. Simulation Mode

Simulation mode must only be enabled temporarily.

Create a runtime override:

```bash
sudo systemctl edit --runtime \
    lums-execution-watcher.service
```

Add:

```ini
[Service]
Environment=LUMS_SIMULATE_UPDATES=1
```

Start the watcher:

```bash
sudo systemctl start \
    lums-execution-watcher.service
```

Remove the runtime override afterwards:

```bash
sudo systemctl revert --runtime \
    lums-execution-watcher.service
```

```bash
sudo systemctl daemon-reload
```

Simulation mode:

- does not change installed packages
- requires a real pending job
- requires supported idle detection
- must not remain enabled permanently

---

# 25. Update Jobs

Current job-related API routes include:

```text
POST /api/clients/<client_id>/update-jobs
GET  /api/clients/<client_id>/update-jobs
GET  /api/clients/<client_id>/update-jobs/pending
GET  /api/clients/<client_id>/update-jobs/running
POST /api/clients/<client_id>/update-jobs/<job_id>/claim
GET  /api/update-jobs/<job_id>
POST /api/update-jobs/<job_id>/result
```

If a job remains in `running`, inspect:

```text
watcher journal
client connectivity
job claim
package-manager state
result reporting
recovery logic
```

Do not manually reset a job before determining why processing stopped.

---

# 26. APT and dpkg Problems

Check running package-management processes:

```bash
ps aux | grep -E \
    'apt|apt-get|dpkg' \
    | grep -v grep
```

Check lock ownership:

```bash
sudo lsof \
    /var/lib/dpkg/lock-frontend \
    /var/lib/dpkg/lock \
    2>/dev/null
```

Never delete lock files while a package-management process is running.

> **Important limitation**
>
> LUMS currently does not provide complete lock coordination with arbitrary manually executed APT or dpkg commands.
>
> The LUMS job lock must not be interpreted as a universal system-wide package-manager lock.

Manual package testing:

```bash
sudo apt-get install \
    --only-upgrade \
    <PACKAGE>
```

Possible causes:

```text
dependency problem
package conflict
repository error
insufficient permissions
package-manager lock
reboot requirement
network failure
```

---

# 27. Reboot Requirement

Check whether a reboot is required:

```bash
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot required"
```

LUMS does not automatically reboot clients.

A reboot remains an administrative decision.

---

# 28. Database Diagnostics

The database is stored in:

```text
Docker volume: lums-data
Database: /var/lib/lums/lums.db
```

Check the database file:

```bash
sudo docker exec \
    lums \
    ls -l /var/lib/lums/lums.db
```

If SQLite is available inside the image:

```bash
sudo docker exec \
    lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

Expected result:

```text
ok
```

If the result differs from `ok`:

1. Stop unnecessary changes.
2. Create a backup.
3. Preserve logs.
4. Investigate the database issue.
5. Avoid structural changes without a verified backup.

---

# 29. SQLite-Aware Database Backup

Create a protected backup directory:

```bash
sudo mkdir -p \
    /var/backups/lums

sudo chmod 700 \
    /var/backups/lums
```

Create a consistent SQLite backup using a temporary backup container:

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
sudo chmod 600 \
    /var/backups/lums/lums.db.backup
```

Check the backup:

```bash
sudo ls -lh \
    /var/backups/lums/lums.db.backup
```

Optional integrity check:

```bash
sudo docker run --rm \
    -v /var/backups/lums:/backup:ro \
    lums:latest \
    python3 -c '
import sqlite3

db = sqlite3.connect("/backup/lums.db.backup")
result = db.execute("PRAGMA integrity_check").fetchone()[0]
print(result)
db.close()
'
```

> A backup that has never been tested cannot be considered a reliable recovery method.

---

# 30. Git Diagnostics

Repository:

```text
/opt/lums-public
```

Check status:

```bash
cd /opt/lums-public

git status
```

Inspect changes:

```bash
git diff
```

Check whitespace:

```bash
git diff --check
```

Fetch remote information:

```bash
git fetch origin
```

Compare branches:

```bash
git rev-list \
    --left-right \
    --count \
    HEAD...origin/main
```

Expected synchronized result:

```text
0       0
```

Do not use `git reset --hard` or force-push as routine troubleshooting methods.

---

# 31. Git Deployment Checks

Recommended sequence:

```text
git status
   ↓
git fetch origin
   ↓
git pull --ff-only
   ↓
syntax check
   ↓
git diff --check
   ↓
database backup
   ↓
Docker image build
   ↓
container recreation
   ↓
health check
```

```bash
cd /opt/lums-public

git status
git fetch origin
git pull --ff-only origin main
```

Check Python syntax:

```bash
python3 -m py_compile \
    server/app.py \
    server/init_db.py \
    agent/agent.py
```

Check whitespace:

```bash
git diff --check
```

Build the image:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Create a database backup before recreating the production container.

---

# 32. Git Commit Identity

Configure the repository identity:

```bash
cd /opt/lums-public

git config user.name \
    "NovaForgeCtrl"

git config user.email \
    "232026481+NovaForgeCtrl@users.noreply.github.com"
```

Verify:

```bash
git config --get user.name
git config --get user.email
```

Never store passwords, tokens or private credentials in Git configuration or repository files.

---

# 33. Container Recreation

Verify the persistent volume:

```bash
sudo docker volume inspect \
    lums-data
```

Stop and remove only the container:

```bash
sudo docker stop lums
```

```bash
sudo docker rm lums
```

Recreate using the existing volume:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
```

Check the result:

```bash
sudo docker ps \
    --filter "name=^lums$"
```

Check logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Test locally:

```bash
curl -i \
    http://127.0.0.1:5050/
```

> **CAUTION**
>
> Never remove `lums-data` during routine container recreation.

---

# 34. Port Diagnostics

List listening ports:

```bash
sudo ss -lntp
```

| Port | Purpose |
|---:|---|
| `22` | SSH |
| `80` | HTTP to HTTPS redirect |
| `443` | HTTPS / Nginx |
| `5050` | Docker-published Flask port, localhost only |
| `5000` | Flask inside Docker |

Do not expose ports `5000` or `5050` to the network unnecessarily.

---

# 35. Firewall Diagnostics

Check UFW:

```bash
sudo ufw status verbose
```

Required public access may include:

```text
TCP/443
TCP/80
```

Only allow port 80 when HTTP-to-HTTPS redirection is required.

Before changing firewall rules remotely, confirm that SSH access remains available.

Never lock yourself out of the server through an untested remote firewall change.

---

# 36. Permission Diagnostics

Check the environment file:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/docker/lums.env
```

Check the agent configuration:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/default/lums-agent
```

Check the TLS private key:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/tls/lums.key
```

Do not blindly change ownership of complete directory trees.

Change only the affected resource and verify the result afterwards.

---

# 37. Diagnostic Log Reference

| Problem | First location |
|---|---|
| Container not starting | `docker logs lums` |
| Container restarting | Docker state and logs |
| Flask problem | Docker logs and curl |
| Nginx failure | `journalctl -u nginx` |
| HTTP 502 | Upstream and Nginx |
| HTTPS problem | Nginx and certificate |
| TLS verification | Agent configuration and certificate |
| 401 Unauthorized | Token and authentication logic |
| 403 Forbidden | Authorization logic |
| Agent failure | `journalctl -u lums-agent.service` |
| Timer failure | `systemctl list-timers` |
| Update failure | Agent journal and APT |
| Stuck job | Watcher journal and SQLite |
| Database issue | SQLite integrity check |
| Git problem | `git status` and `git diff` |

---

# 38. Server Diagnostic Sequence

```bash
sudo docker ps -a
```

```bash
sudo docker logs \
    --tail 100 \
    lums
```

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

```bash
sudo nginx -t
```

```bash
sudo ss -lntp
```

```bash
sudo ufw status verbose
```

```bash
curl -i \
    http://127.0.0.1:5050/
```

```bash
curl -k -i \
    https://<LUMS_SERVER_IP>/
```

---

# 39. Client Diagnostic Sequence

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

```bash
sudo grep '^LUMS_BASE=' \
    /etc/default/lums-agent
```

```bash
sudo grep '^LUMS_CA_FILE=' \
    /etc/default/lums-agent
```

```bash
sudo grep -q '^LUMS_TOKEN=.' \
    /etc/default/lums-agent \
    && echo "Token vorhanden" \
    || echo "Token fehlt"
```

```bash
apt list --upgradable 2>/dev/null
```

Manual test:

```bash
sudo bash -c '
set -a
source /etc/default/lums-agent
set +a
exec /usr/bin/python3 /opt/lums-agent/agent.py
'
```

---

# 40. Public Bug Reports

Before sharing logs, redact:

```text
LUMS_SECRET_KEY
LUMS_TOKEN
passwords
private keys
Authorization headers
session information
```

Review for:

```text
internal IP addresses
hostnames
usernames
database paths
client identifiers
```

Use placeholders:

```text
<LUMS_SERVER_IP>
<CLIENT_TOKEN>
<PACKAGE>
<JOB_ID>
<CLIENT_ID>
```

Never use real production credentials as examples.

---

# 41. Known Installation Lessons

## 41.1 Client Authentication

The current implementation uses a SHA-256 hexadecimal digest for client authentication.

The stored value must match the implementation exactly.

Do not substitute another hash format without changing and testing the authentication logic.

## 41.2 Database Schema

Client registration must respect the current database schema.

Optional client information, such as hostname data, must not be assumed to be mandatory unless the schema requires it.

When registration fails:

```text
inspect API response
   ↓
inspect application logs
   ↓
inspect schema
   ↓
check submitted fields
```

Do not modify the database schema directly without a backup and a documented migration plan.

## 41.3 TLS SAN

The certificate must contain the address used by the client.

For IP-based access:

```text
IP Address:<LUMS_SERVER_IP>
```

must be present in the certificate SAN.

## 41.4 Manual Execution

Manual Python execution and systemd execution are different environments.

Compare:

```text
environment
user
permissions
working directory
certificate path
network availability
systemd configuration
```

## 41.5 Python File Changes

For larger Python changes, prefer complete file replacement:

```bash
sudo tee /path/to/file.py > /dev/null <<'EOF'
# Complete file content
EOF
```

This reduces accidental indentation errors and creates reproducible file contents.

---

# 42. Final Checklist

## Server

```text
[ ] Docker container exists
[ ] Docker container is running
[ ] Docker logs contain no unexplained errors
[ ] Docker volume lums-data exists
[ ] Environment file exists
[ ] Environment file is protected with 600
[ ] Flask responds on 127.0.0.1:5050
[ ] Docker port mapping is correct
[ ] Nginx is running
[ ] nginx -t succeeds
[ ] HTTP redirects to HTTPS
[ ] HTTPS works
[ ] Certificate contains the correct SAN
[ ] TCP/443 is reachable
[ ] Port 5000 is not publicly exposed
[ ] Port 5050 is bound to localhost
```

## Client

```text
[ ] Client is registered
[ ] Client is enabled
[ ] Token exists
[ ] Token matches the authentication logic
[ ] Token is not revoked
[ ] LUMS_BASE is correct
[ ] LUMS_CA_FILE is correct
[ ] TLS verification succeeds
[ ] Agent can reach the server
[ ] Agent report reaches the server
[ ] Agent timer is active
[ ] Agent service executes successfully
[ ] Watcher timer is active
[ ] Idle detection is supported
[ ] Update job exists
[ ] Package update succeeds
[ ] Result is reported
[ ] Inventory is updated
```

## Maintenance

```text
[ ] SQLite database is healthy
[ ] Current database backup exists
[ ] Backup integrity was tested
[ ] Git repository is synchronized
[ ] No unintended uncommitted changes exist
[ ] Docker image builds successfully
[ ] Container uses the existing volume
[ ] Application was tested after deployment
[ ] Secrets were excluded from logs
[ ] Security limitations are documented
```

---

# 43. Final Principles

When something fails:

```text
Don't reinstall immediately.
Don't delete the Docker volume.
Don't disable security.
Don't permanently disable TLS verification.
Don't disable authentication.
Don't expose port 5000.
Don't expose port 5050 unnecessarily.
Don't paste secrets into bug reports.
Don't change five things at once.
Don't modify the database without a backup.
Don't assume a timer guarantees successful execution.
Don't assume a job lock prevents every manual APT command.
```

Instead:

```text
Observe
   ↓
Measure
   ↓
Identify the failing layer
   ↓
Change one thing
   ↓
Test again
   ↓
Document the result
```

The goal of troubleshooting is not merely to make LUMS work again.

The goal is to understand **why** it failed and leave behind a reproducible solution.

---

> **LUMS — Linux Update Management without the noise.**
>
> Centralize the management.  
> Keep execution controlled.  
> Know what changed.  
> Know where it happened.
