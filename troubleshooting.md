# LUMS Troubleshooting Guide

> **Linux Update Management Server**
>
> A practical troubleshooting guide for diagnosing LUMS,
> Docker, Nginx, TLS, authentication, agents, databases,
> Git and update-management problems.

---

> **LUMS — Linux Update Management without the noise.**
>
> Centralize the management.
> Keep execution controlled.
> Know what changed.
> Know where it happened.

---

## Golden Rule

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

LUMS consists of several independent components. A failure in one layer does not necessarily mean that the entire system is broken.

The recommended troubleshooting approach is:

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

---

# 1. Current LUMS Architecture

The current LUMS installation uses Docker for the application and Nginx as a TLS reverse proxy.

```text
┌───────────────────────────┐
│        Web Browser        │
└─────────────┬─────────────┘
              │
              │ HTTPS :443
              ▼
┌───────────────────────────┐
│          Nginx            │
│      TLS / Reverse Proxy  │
└─────────────┬─────────────┘
              │
              │ HTTP
              ▼
┌───────────────────────────┐
│       Docker Container    │
│           lums            │
│                           │
│       Flask :5000         │
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│       Docker Volume       │
│         lums-data         │
│                           │
│    /var/lib/lums/lums.db  │
└───────────────────────────┘


              ▲
              │
              │ HTTPS + Bearer Token
              │
┌─────────────┴─────────────┐
│       Linux Agent         │
│                           │
│ Python / APT / dpkg       │
│ systemd timer             │
└───────────────────────────┘
```

## Current Network Flow

```text
Client
   │
   │ HTTPS :443
   ▼
Nginx
   │
   │ HTTP localhost
   ▼
127.0.0.1:5050
   │
   │ Docker port mapping
   ▼
Container port 5000
   │
   ▼
Flask application
```

The Docker container is published using:

```text
127.0.0.1:5050 → 5000/tcp
```

Port `5000` is not directly exposed to the network.

---

# 2. Troubleshooting Order

Use the following order:

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
Client authorization
   ↓
Agent
   ↓
Report
   ↓
Update job
   ↓
APT / dpkg
   ↓
Result reporting
```

> [!IMPORTANT]
> Do not change multiple layers at the same time.
>
> Otherwise, it becomes difficult to determine which change actually solved the problem.

---

# 3. Important LUMS Paths

## Server

| Component | Path |
|---|---|
| Git source | `/opt/lums-public` |
| Docker image | `lums:latest` |
| Docker container | `lums` |
| Docker volume | `lums-data` |
| Database inside container | `/var/lib/lums/lums.db` |
| Secret file | `/etc/lums/docker/lums.env` |
| Nginx configuration | `/etc/nginx/sites-available/lums` |
| TLS certificate | `/etc/nginx/ssl/lums/lums.crt` |
| TLS private key | `/etc/nginx/ssl/lums/lums.key` |

## Client

| Component | Path |
|---|---|
| Agent source | `/opt/lums-public/agent/agent.py` |
| Installed agent | `/opt/lums-agent/agent.py` |
| Agent certificate | `/opt/lums-agent/lums-ca.crt` |
| Agent configuration | `/etc/default/lums-agent` |
| Agent service | `lums-agent.service` |
| Agent timer | `lums-agent.timer` |

> [!CAUTION]
> The following files contain runtime state or secrets and must not be overwritten by a normal Git deployment:
>
> - `/etc/lums/docker/lums.env`
> - `/etc/nginx/ssl/lums/lums.key`
> - `/etc/default/lums-agent`
> - Docker volume `lums-data`

---

# 4. Docker Container Does Not Start

Check whether the container exists:

```bash
sudo docker ps -a
```

Check the current container status:

```bash
sudo docker ps \
    --filter "name=^lums$"
```

Check the container logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Follow the logs live:

```bash
sudo docker logs \
    --follow \
    lums
```

Inspect the container configuration:

```bash
sudo docker inspect lums
```

Check the container exit code:

```bash
sudo docker inspect \
    --format '{{.State.Status}} {{.State.ExitCode}}' \
    lums
```

Possible causes:

```text
missing environment file
application error
database error
incorrect volume
invalid image
port conflict
permission problem
```

> [!IMPORTANT]
> Always inspect the first actual application error in the Docker logs before recreating the container.

---

# 5. Docker Container Keeps Restarting

Check the restart state:

```bash
sudo docker ps -a \
    --filter "name=^lums$"
```

Inspect the restart policy:

```bash
sudo docker inspect \
    --format '{{.HostConfig.RestartPolicy}}' \
    lums
```

Inspect the logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Check the container state:

```bash
sudo docker inspect \
    --format '{{json .State}}' \
    lums
```

The configured restart policy is:

```text
unless-stopped
```

The important question is not:

> Why does Docker restart the container?

The important question is:

> Why does the application stop or fail?

Check the first Python, Flask, configuration or database error.

---

# 6. Docker Image Is Missing

List available images:

```bash
sudo docker images
```

Check specifically for the LUMS image:

```bash
sudo docker image inspect \
    lums:latest
```

If the image is missing, rebuild it from the repository:

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

> [!NOTE]
> Rebuilding an image does not automatically delete the Docker volume containing the database.

---

# 7. Docker Port Problem

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

The expected binding is:

```text
127.0.0.1:5050
```

Port `5000` is the internal Flask port inside the container.

Test the local Docker endpoint:

```bash
curl -i \
    http://127.0.0.1:5050/
```

A redirect to `/login` is an expected result when the application is running.

> [!CAUTION]
> Do not publish Flask directly to the network just to simplify troubleshooting.

---

# 8. Docker Volume Problems

List Docker volumes:

```bash
sudo docker volume ls
```

Inspect the LUMS volume:

```bash
sudo docker volume inspect \
    lums-data
```

Check the volume mount inside the container:

```bash
sudo docker inspect \
    --format '{{json .Mounts}}' \
    lums
```

The database is stored inside the volume:

```text
/var/lib/lums/lums.db
```

Check the database from inside the container:

```bash
sudo docker exec \
    lums \
    ls -l /var/lib/lums/
```

> [!CAUTION]
> Never use the following command as a routine troubleshooting step:

```bash
sudo docker volume rm lums-data
```

Deleting the volume can permanently delete the LUMS database.

---

# 9. Missing LUMS Secret

The Docker environment file is:

```text
/etc/lums/docker/lums.env
```

Check that the file exists:

```bash
sudo ls -l \
    /etc/lums/docker/lums.env
```

Check whether the required variable exists without displaying its value:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' \
    /etc/lums/docker/lums.env \
    && echo "Secret vorhanden" \
    || echo "Secret fehlt"
```

Check the file permissions:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/docker/lums.env
```

Expected protection:

```text
root:root 600
```

The secret must never be copied into:

- documentation
- GitHub issues
- screenshots
- bug reports
- chat messages
- public repositories

> [!CAUTION]
> Never use the following command in a public troubleshooting report:

```bash
cat /etc/lums/docker/lums.env
```

---

# 10. Docker Environment File Is Not Loaded

Inspect the container environment configuration:

```bash
sudo docker inspect \
    --format '{{json .Config.Env}}' \
    lums
```

Check that the environment file is supplied when the container is created.

The expected container creation pattern is:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
```

> [!IMPORTANT]
> Do not place secrets directly into Git-tracked Dockerfiles or shell scripts.

---

# 11. Flask Health Check Fails

The current Flask application is accessible through the Docker port mapping:

```text
127.0.0.1:5050
```

Test the application:

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

Check the published port:

```bash
sudo docker port lums
```

> [!NOTE]
> The application may return `302 FOUND` and redirect to `/login`. This can be a valid result and does not automatically indicate an error.

---

# 12. Flask Is Listening on the Wrong Address

The expected host-side binding is:

```text
127.0.0.1:5050
```

Check:

```bash
sudo ss -lntp | grep -E ':5050|:5000'
```

Expected architecture:

```text
Browser
   │
   │ HTTPS
   ▼
Nginx :443
   │
   │ localhost
   ▼
Docker 127.0.0.1:5050
   │
   ▼
Flask :5000
```

The following configuration would expose the published port to all interfaces:

```text
0.0.0.0:5050
```

Avoid this unless there is a specific, documented reason.

---

# 13. Nginx Does Not Start

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

> [!IMPORTANT]
> Do not reload Nginx until `nginx -t` reports a successful configuration test.

---

# 14. Nginx Returns `502 Bad Gateway`

A `502 Bad Gateway` usually means that Nginx cannot reach the upstream application.

Test the Docker application directly:

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

Check the Nginx configuration:

```bash
sudo nginx -t
```

The expected upstream is:

```text
http://127.0.0.1:5050
```

Expected flow:

```text
Browser
   ↓
Nginx :443
   ↓
127.0.0.1:5050
   ↓
Docker container
   ↓
Flask :5000
```

---

# 15. HTTPS Does Not Work

Check whether Nginx listens on port `443`:

```bash
sudo ss -lntp | grep ':443'
```

Test HTTPS locally:

```bash
curl -k -i \
    https://127.0.0.1/
```

Test using the server IP:

```bash
curl -k -i \
    https://IP Address/
```

Test the HTTP redirect:

```bash
curl -I \
    http://IP Address/
```

The HTTP endpoint should redirect to HTTPS.

If the local test works but a remote client cannot connect, investigate:

```text
network
firewall
routing
client connectivity
TCP/443
```

Check UFW if it is in use:

```bash
sudo ufw status verbose
```

> [!NOTE]
> A successful local HTTPS test proves that Nginx and TLS work locally. It does not prove that remote clients can reach TCP/443.

---

# 16. Certificate Error

The current certificate paths are:

```text
/etc/nginx/ssl/lums/lums.crt
/etc/nginx/ssl/lums/lums.key
```

Inspect the certificate:

```bash
sudo openssl x509 \
    -in /etc/nginx/ssl/lums/lums.crt \
    -noout \
    -subject \
    -dates
```

Inspect the Subject Alternative Name:

```bash
sudo openssl x509 \
    -in /etc/nginx/ssl/lums/lums.crt \
    -noout \
    -ext subjectAltName
```

The current server address is:

```text
IP Address
```

The certificate should contain:

```text
IP Address:IP Address
```

as a Subject Alternative Name.

> [!IMPORTANT]
> The address used by the client must match a SAN in the certificate.

---

# 17. TLS Certificate Permissions

Check the certificate:

```bash
sudo ls -l \
    /etc/nginx/ssl/lums/lums.crt
```

Check the private key:

```bash
sudo ls -l \
    /etc/nginx/ssl/lums/lums.key
```

The private key must not be world-readable.

Check:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/nginx/ssl/lums/lums.key
```

After changing permissions, test the Nginx configuration:

```bash
sudo nginx -t
```

Reload only after a successful test:

```bash
sudo systemctl reload nginx
```

---

# 18. Agent Returns `CERTIFICATE_VERIFY_FAILED`

The agent configuration is:

```text
/etc/default/lums-agent
```

Check the configured CA file:

```bash
sudo grep '^LUMS_CA_FILE=' \
    /etc/default/lums-agent
```

The current agent certificate path is:

```text
/opt/lums-agent/lums-ca.crt
```

Check the file:

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

Verify the configured server address:

```bash
sudo grep '^LUMS_BASE=' \
    /etc/default/lums-agent
```

The configured hostname or IP must match the certificate SAN.

> [!WARNING]
> Do not permanently disable certificate verification to solve a TLS problem.

---

# 19. Agent Cannot Reach the Server

From the client, test basic connectivity:

```bash
ping IP Address
```

Test HTTPS:

```bash
curl -k \
    https://IP Address/
```

Check the server:

```bash
sudo ss -lntp | grep ':443'
```

Check the firewall:

```bash
sudo ufw status verbose
```

The following are separate tests:

```text
Ping works
   ≠
TCP/443 works
   ≠
TLS verification works
   ≠
Authentication works
```

Investigate each layer independently.

---

# 20. Agent Returns `401 Unauthorized`

A `401 Unauthorized` response means that the API rejected the authentication credentials.

Check that a token exists without displaying it:

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

Expected structure:

```text
LUMS_BASE=https://IP Address
```

Possible causes:

```text
token missing
wrong token
wrong token hash
token revoked
client disabled
client does not exist
incorrect server address
```

---

# 21. Client Authentication and SHA-256

LUMS client authentication uses a Bearer token.

The server stores the corresponding client authentication value as a SHA-256 hexadecimal digest.

The authentication chain is:

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
SQLite clients table
```

The database is stored in the Docker volume:

```text
lums-data
```

The database path inside the container is:

```text
/var/lib/lums/lums.db
```

If the token appears correct but authentication still returns `401`, inspect the implementation before changing the database.

> [!CAUTION]
> Do not replace the token hash with a password hash or another hashing format. The stored value must match the authentication implementation used by LUMS.

---

# 22. Missing `LUMS_TOKEN` During Manual Agent Start

A common source of confusion is running:

```bash
python3 /opt/lums-agent/agent.py
```

and receiving an error that:

```text
LUMS_TOKEN
```

is missing.

A direct Python invocation does not automatically load:

```text
/etc/default/lums-agent
```

For a manual test, load the environment file explicitly:

```bash
sudo bash -c '
set -a
source /etc/default/lums-agent
set +a
exec /usr/bin/python3 /opt/lums-agent/agent.py
'
```

This differs from:

```bash
sudo systemctl start lums-agent.service
```

because systemd loads the configured environment file for the service.

---

# 23. Agent Configuration Check

Check the non-secret values:

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

Expected structure:

```text
LUMS_BASE=https://IP Address
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
LUMS_TOKEN=CLIENT_TOKEN
```

Protect the configuration:

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
sudo ls -l \
    /etc/default/lums-agent
```

---

# 24. Agent Returns `403 Forbidden`

A `403 Forbidden` is different from a `401 Unauthorized`.

```text
401
│
└── Authentication failed

403
│
└── Authentication succeeded,
    but the requested action is not authorized
```

A useful diagnostic model is:

```text
Network        ✓
TLS            ✓
Authentication ✓
Authorization  ✗
```

Possible causes:

```text
client is disabled
client is requesting another client's data
endpoint requires additional permissions
authorization rule rejects the request
```

---

# 25. `/api/client/me` Fails

Authenticated agents use:

```text
GET /api/client/me
```

to obtain their authenticated client context.

Investigate in this order:

```text
TLS
   ↓
Token
   ↓
Client registration
   ↓
Client enabled state
   ↓
Authorization
```

Run the agent manually:

```bash
sudo bash -c '
set -a
source /etc/default/lums-agent
set +a
exec /usr/bin/python3 /opt/lums-agent/agent.py
'
```

Inspect the service logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 26. Agent Sends Report but No Updates Appear

LUMS receives update information through the client report.

The inventory represents the state reported by the client.

Check the client locally:

```bash
apt list --upgradable 2>/dev/null
```

Count available updates:

```bash
apt list --upgradable 2>/dev/null \
    | tail -n +2 \
    | wc -l
```

If the result is:

```text
0
```

the client currently reports no available upgrades.

If packages are listed locally but not visible in LUMS, investigate:

```text
agent report
   ↓
API endpoint
   ↓
client identity
   ↓
database
   ↓
server inventory
```

Check the agent logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 27. LUMS Shows Old Inventory

The LUMS inventory is based on the latest successful client report.

Start the agent manually through systemd:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspect the result:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Check the timer:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

A successful report should result in the server receiving the new client state.

---

# 28. Agent Timer Does Not Run

Check the timer:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

List all timers:

```bash
systemctl list-timers \
    --all \
    | grep lums-agent
```

Inspect the timer definition:

```bash
systemctl cat \
    lums-agent.timer
```

Check the timer configuration:

```bash
systemctl show \
    lums-agent.timer \
    -p NextElapseUSecRealtime \
    -p LastTriggerUSec
```

If the unit files were changed:

```bash
sudo systemctl daemon-reload
```

Enable and start the timer:

```bash
sudo systemctl enable \
    --now \
    lums-agent.timer
```

> [!IMPORTANT]
> Enable the timer, not the oneshot service itself.

---

# 29. Agent Service Shows `inactive (dead)`

The LUMS agent is configured as a `oneshot` service.

After a successful execution, the service may show:

```text
inactive (dead)
```

This is normal.

The timer remains responsible for starting the service again.

Check the timer:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Check the most recent execution:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Expected behavior:

```text
Timer active
   ↓
Service starts
   ↓
Agent executes
   ↓
Report is sent
   ↓
Service exits successfully
   ↓
Service becomes inactive
   ↓
Timer schedules the next run
```

Do not permanently enable the service with:

```bash
sudo systemctl enable \
    lums-agent.service
```

Use the timer:

```bash
sudo systemctl enable \
    --now \
    lums-agent.timer
```

---

# 30. Agent Service Fails

Check:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager \
    -l
```

Check logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Check Python syntax:

```bash
python3 -m py_compile \
    /opt/lums-agent/agent.py
```

If manual execution works but systemd execution fails, compare:

```text
environment
user
permissions
certificate path
systemd configuration
file paths
network availability
```

---

# 31. Timer Exists but Service Fails

The execution chain is:

```text
lums-agent.timer
       │
       ▼
lums-agent.service
       │
       ▼
agent.py
```

The timer can be healthy while the service itself fails.

Check both units:

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

```bash
systemctl status \
    lums-agent.service \
    --no-pager
```

The timer status alone does not prove that the agent executed successfully.

---

# 32. Update Job Remains `running`

First identify the database location:

```text
/var/lib/lums/lums.db
```

The database is stored in the Docker volume:

```text
lums-data
```

List the database files:

```bash
sudo docker exec \
    lums \
    ls -l /var/lib/lums/
```

If the SQLite client is available inside the container, inspect the jobs:

```bash
sudo docker exec \
    lums \
    sqlite3 /var/lib/lums/lums.db \
    "SELECT id, client_id, status, created_at, started_at, finished_at FROM update_jobs ORDER BY id;"
```

Inspect packages for a specific job:

```bash
sudo docker exec \
    lums \
    sqlite3 /var/lib/lums/lums.db \
    "SELECT job_id, package, status, message FROM update_job_packages WHERE job_id=JOB_ID;"
```

Replace:

```text
JOB_ID
```

with the actual job number.

> [!WARNING]
> Do not manually reset a job before determining why the client stopped processing it.

---

# 33. Package Update Failed

Check the agent log:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Inspect available upgrades:

```bash
apt list --upgradable 2>/dev/null
```

Manually test an affected package only when appropriate:

```bash
sudo apt-get install \
    --only-upgrade \
    PACKAGE
```

Replace:

```text
PACKAGE
```

with the affected package name.

Possible causes include:

```text
package conflict
dependency problem
repository error
insufficient permissions
package manager lock
reboot requirement
network failure
```

> [!NOTE]
> This guide intentionally does not use `apt update` as part of the standard LUMS troubleshooting workflow. Package-index maintenance is a separate administrative task.

---

# 34. APT or dpkg Lock

Check running package-management processes:

```bash
ps aux | grep -E \
    'apt|apt-get|dpkg' \
    | grep -v grep
```

Check package-manager processes:

```bash
sudo lsof \
    /var/lib/dpkg/lock-frontend \
    /var/lib/dpkg/lock \
    2>/dev/null
```

Do not delete lock files while a package-management process is running.

> [!CAUTION]
> Never remove package-manager lock files blindly. First determine which process owns the lock.

---

# 35. Reboot Required

The agent checks:

```text
/var/run/reboot-required
```

Check manually:

```bash
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot required"
```

LUMS does not automatically reboot the client.

A reboot remains an administrative decision.

---

# 36. Database Problems

The database is stored in the Docker volume:

```text
lums-data
```

The database path inside the container is:

```text
/var/lib/lums/lums.db
```

Check the database file:

```bash
sudo docker exec \
    lums \
    ls -l /var/lib/lums/lums.db
```

If SQLite is available inside the container, run an integrity check:

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

If the result is not:

```text
ok
```

stop making unnecessary changes.

Create a backup before further investigation.

> [!CAUTION]
> Never perform structural database changes without a valid backup.

---

# 37. LUMS Database Backup

Create a backup directory:

```bash
sudo mkdir -p \
    /var/backups/lums
```

Create an SQLite backup inside the container:

```bash
sudo docker exec \
    lums \
    python3 -c '
import sqlite3

source = sqlite3.connect("/var/lib/lums/lums.db")
backup = sqlite3.connect("/var/lib/lums/lums.backup.db")

source.backup(backup)

backup.close()
source.close()
'
```

Copy the backup out of the container:

```bash
sudo docker cp \
    lums:/var/lib/lums/lums.backup.db \
    "/var/backups/lums/lums-$(date +%F_%H-%M-%S).db"
```

Remove the temporary backup file:

```bash
sudo docker exec \
    lums \
    rm -f \
    /var/lib/lums/lums.backup.db
```

List the backups:

```bash
sudo ls -lh \
    /var/backups/lums/
```

> [!IMPORTANT]
> Test backups regularly. A backup that has never been tested cannot be considered a reliable recovery method.

---

# 38. Docker Volume Backup

Inspect the volume:

```bash
sudo docker volume inspect \
    lums-data
```

The volume contains persistent application data.

Do not remove it during routine troubleshooting.

Before major changes:

```bash
sudo docker ps \
    --filter "name=^lums$"
```

Create a database backup before:

```text
image replacement
database migration
security migration
manual database changes
major deployment
```

---

# 39. Permission Problems

Check the Docker environment file:

```bash
sudo ls -l \
    /etc/lums/docker/lums.env
```

Check the Nginx TLS directory:

```bash
sudo ls -ld \
    /etc/nginx/ssl/lums/
```

Check the agent configuration:

```bash
sudo ls -l \
    /etc/default/lums-agent
```

Check the Docker volume:

```bash
sudo docker volume inspect \
    lums-data
```

Do not blindly change ownership of complete directory trees.

> [!IMPORTANT]
> Change only the affected resource and verify the result afterwards.

---

# 40. Agent Configuration Permissions

Check:

```bash
sudo ls -l \
    /etc/default/lums-agent
```

The file contains the client token and should not be world-readable.

Expected protection:

```text
root:root
0600
```

Correct the permissions if necessary:

```bash
sudo chown root:root \
    /etc/default/lums-agent
```

```bash
sudo chmod 600 \
    /etc/default/lums-agent
```

---

# 41. Git Problems

The source repository is:

```text
/opt/lums-public
```

Check the current status:

```bash
cd /opt/lums-public

git status
```

Check differences:

```bash
git diff
```

Check whitespace errors:

```bash
git diff --check
```

Fetch remote information:

```bash
git fetch origin
```

Check whether local and remote branches differ:

```bash
git rev-list \
    --left-right \
    --count \
    HEAD...origin/main
```

Expected result when synchronized:

```text
0       0
```

> [!WARNING]
> Do not use `git reset --hard` or force-push as a routine troubleshooting method.

---

# 42. Git Repository Has Uncommitted Changes

If:

```bash
git status
```

shows modified files, stop before running a deployment pull.

Inspect:

```bash
git diff
```

Determine whether the changes are:

```text
intentional
local-only
unfinished
generated
accidental
```

Do not overwrite local work without first understanding what changed.

---

# 43. Git Commit Identity

If Git reports:

```text
Author identity unknown
```

configure the repository identity:

```bash
cd /opt/lums-public

git config user.name \
    "NovaForgeCtrl"
```

```bash
git config user.email \
    "232026481+NovaForgeCtrl@users.noreply.github.com"
```

Verify:

```bash
git config --get \
    user.name
```

```bash
git config --get \
    user.email
```

Do not put passwords, tokens or private credentials into Git configuration or repository files.

---

# 44. Nginx Configuration Problems

Test:

```bash
sudo nginx -t
```

Inspect the active configuration:

```bash
sudo nginx -T
```

Check enabled sites:

```bash
sudo ls -la \
    /etc/nginx/sites-enabled/
```

Inspect the LUMS site:

```bash
sudo cat \
    /etc/nginx/sites-available/lums
```

Reload only after a successful test:

```bash
sudo nginx -t \
    && sudo systemctl reload nginx
```

---

# 45. Port Diagnostics

List listening TCP ports:

```bash
sudo ss -lntp
```

Important LUMS ports:

| Port | Purpose |
|---:|---|
| `22` | SSH |
| `80` | HTTP → HTTPS redirect |
| `443` | HTTPS / Nginx |
| `5050` | Docker-published Flask port, localhost only |
| `5000` | Flask inside the container |

Expected architecture:

```text
22      SSH
80      HTTP → HTTPS redirect
443     HTTPS / Nginx
5050    Docker localhost port
5000    Flask inside Docker
```

> [!CAUTION]
> Do not expose port `5000` or `5050` to the network just to simplify troubleshooting.

---

# 46. Firewall Diagnostics

Check UFW:

```bash
sudo ufw status verbose
```

If HTTPS is blocked, the firewall must allow:

```text
TCP/443
```

If HTTP redirection is required, allow:

```text
TCP/80
```

Before changing SSH firewall rules remotely, make sure SSH access remains available.

> [!WARNING]
> Never lock yourself out of the server by changing firewall rules remotely without verifying the current SSH access path.

---

# 47. Deployment Problems

The current application runs in Docker.

The recommended deployment sequence is:

```text
Git
 ↓
git status
 ↓
git fetch
 ↓
git pull --ff-only
 ↓
syntax check
 ↓
git diff --check
 ↓
Docker image build
 ↓
container recreation
 ↓
health check
```

Before deployment:

```bash
cd /opt/lums-public
```

Check the repository:

```bash
git status
```

Fetch remote changes:

```bash
git fetch origin
```

Synchronize safely:

```bash
git pull --ff-only \
    origin main
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

Build the Docker image:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Inspect the image:

```bash
sudo docker image inspect \
    lums:latest
```

> [!CAUTION]
> Create a database backup before recreating the production container.

---

# 48. Recreating the LUMS Container

Before recreating the container, confirm that the persistent volume exists:

```bash
sudo docker volume inspect \
    lums-data
```

Stop and remove only the container:

```bash
sudo docker stop \
    lums
```

```bash
sudo docker rm \
    lums
```

Recreate the container using the existing volume:

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

> [!CAUTION]
> Do not remove the `lums-data` volume when recreating the container.

---

# 49. Deployment Protection

A deployment must not overwrite:

- Docker volume `lums-data`
- `/etc/lums/docker/lums.env`
- `/etc/nginx/ssl/lums/`
- `/etc/default/lums-agent`

The Git repository contains source code.

Runtime state and secrets are stored separately.

```text
Git source
   ≠
Runtime database
   ≠
Secret configuration
   ≠
TLS private key
```

---

# 50. Logs: Where to Look

| Problem | First place to check |
|---|---|
| Container not starting | `docker logs lums` |
| Container restarting | Docker state + logs |
| Missing secret | `/etc/lums/docker/lums.env` |
| Flask problem | Docker logs + curl |
| Nginx not starting | `journalctl -u nginx` |
| HTTP 502 | Docker application + Nginx |
| HTTPS problem | Nginx + certificate |
| TLS verification | Agent config + certificate |
| Agent connectivity | `curl`, `ss`, firewall |
| `401 Unauthorized` | Token + authentication logic |
| `403 Forbidden` | Client authorization |
| Agent failure | `journalctl -u lums-agent.service` |
| Timer problem | `systemctl list-timers` |
| Update failure | Agent journal + APT |
| Job stuck | SQLite + agent journal |
| Database issue | SQLite integrity check |
| Git problem | `git status` + `git diff` |

---

# 51. Recommended Server Diagnostic Sequence

Check Docker:

```bash
sudo docker ps -a
```

Check Docker logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Check Nginx:

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

Test Nginx:

```bash
sudo nginx -t
```

Check listening ports:

```bash
sudo ss -lntp
```

Check firewall:

```bash
sudo ufw status verbose
```

Test the local Docker endpoint:

```bash
curl -i \
    http://127.0.0.1:5050/
```

Test HTTPS:

```bash
curl -k -i \
    https://IP Address/
```

---

# 52. Recommended Client Diagnostic Sequence

Check the timer:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Check the service:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Check logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Check available upgrades:

```bash
apt list --upgradable 2>/dev/null
```

Check the server URL:

```bash
sudo grep '^LUMS_BASE=' \
    /etc/default/lums-agent
```

Check the CA path:

```bash
sudo grep '^LUMS_CA_FILE=' \
    /etc/default/lums-agent
```

Check token presence:

```bash
sudo grep -q '^LUMS_TOKEN=.' \
    /etc/default/lums-agent \
    && echo "Token vorhanden" \
    || echo "Token fehlt"
```

Run a manual test:

```bash
sudo bash -c '
set -a
source /etc/default/lums-agent
set +a
exec /usr/bin/python3 /opt/lums-agent/agent.py
'
```

---

# 53. Do Not Share Secrets in Bug Reports

Before posting logs publicly, remove or redact:

```text
LUMS_SECRET_KEY
LUMS_TOKEN
passwords
private keys
Authorization headers
session information
```

Review logs for internal information such as:

```text
internal IP addresses
hostnames
usernames
database paths
```

Use placeholders in documentation:

```text
SERVER_IP
CLIENT_TOKEN
PACKAGE
JOB_ID
```

Never use a real production token as an example.

---

# 54. Known LUMS Installation Lessons

## 54.1 Client Authentication Hash

The API expects the client authentication value in the format implemented by the current security layer.

The current implementation uses a SHA-256 hexadecimal digest.

The database is stored in:

```text
lums-data
```

The database path inside the container is:

```text
/var/lib/lums/lums.db
```

A different password-hashing scheme must not be substituted.

---

## 54.2 Client Database Schema

Client registration previously failed because the database schema required:

```text
hostname NOT NULL
```

while the frontend could initially submit only:

```json
{
  "ip": "CLIENT_IP"
}
```

The schema was corrected so that:

```text
hostname TEXT UNIQUE
```

is optional.

This allows a client to be registered before its hostname information is available.

---

## 54.3 TLS SAN

The certificate must contain the IP address used by the client.

The current server IP is:

```text
IP Address
```

The certificate must contain:

```text
IP Address:IP Address
```

as a Subject Alternative Name.

---

## 54.4 Agent Environment

The agent requires:

```text
LUMS_BASE
LUMS_TOKEN
LUMS_CA_FILE
```

The configuration belongs in:

```text
/etc/default/lums-agent
```

A correctly configured file does not automatically mean that a manually started Python process has loaded it.

---

## 54.5 `/api/client/me`

Authenticated agents use:

```text
/api/client/me
```

to obtain their authenticated client context.

This endpoint must not be confused with administrative client-management endpoints.

---

## 54.6 Manual Python Execution vs systemd

These are different execution environments:

```bash
python3 /opt/lums-agent/agent.py
```

and:

```bash
sudo systemctl start lums-agent.service
```

systemd can provide:

```text
environment
user
working directory
permissions
service configuration
```

A manually started Python process does not automatically receive all of those settings.

---

## 54.7 Python Indentation

Large Python blocks pasted directly into a terminal can cause:

```text
IndentationError
```

For larger file changes, prefer complete file replacement:

```bash
sudo tee /path/to/file.py > /dev/null <<'EOF'
...
EOF
```

This creates reproducible file contents and reduces accidental indentation problems.

---

# 55. Do Not Change Multiple Layers at Once

For example, if HTTPS fails, do not immediately change:

```text
Nginx
Docker
UFW
TLS
Agent
```

Instead:

```text
1. Test Docker application
      ↓
2. Test Nginx
      ↓
3. Test HTTPS
      ↓
4. Test client connectivity
      ↓
5. Test TLS verification
      ↓
6. Test authentication
      ↓
7. Test authorization
      ↓
8. Test reporting
```

This keeps the troubleshooting process reproducible.

---

# 56. Final Troubleshooting Checklist

## Server

```text
[ ] Is the Docker container present?
[ ] Is the Docker container running?
[ ] Are the Docker logs free of application errors?
[ ] Does the Docker volume lums-data exist?
[ ] Does the secret file exist?
[ ] Is the secret file protected with 600?
[ ] Does Flask answer on 127.0.0.1:5050?
[ ] Is the published Docker port correct?
[ ] Is Nginx running?
[ ] Does nginx -t succeed?
[ ] Does HTTP redirect to HTTPS?
[ ] Does HTTPS work?
[ ] Does the certificate contain the correct SAN?
[ ] Is TCP 443 reachable?
[ ] Is port 5000 not exposed to the network?
```

## Client

```text
[ ] Is the client registered?
[ ] Is the client enabled?
[ ] Does the token exist?
[ ] Does the token match the SHA-256 authentication logic?
[ ] Is the token revoked?
[ ] Is LUMS_BASE correct?
[ ] Is LUMS_CA_FILE correct?
[ ] Does TLS verification succeed?
[ ] Does /api/client/me work?
[ ] Does the report reach the server?
[ ] Is the agent timer active?
[ ] Does the timer trigger the service?
[ ] Does the agent execute successfully?
[ ] Does APT report the expected package state?
[ ] Does the update job exist?
[ ] Does the package update succeed?
[ ] Is the result reported?
[ ] Is the post-update inventory current?
```

## Maintenance

```text
[ ] Is the SQLite database healthy?
[ ] Has a current database backup been created?
[ ] Is the Git repository synchronized?
[ ] Are there uncommitted changes?
[ ] Was the Docker image built successfully?
[ ] Was the container recreated using the existing volume?
[ ] Was the application tested after deployment?
[ ] Were secrets excluded from logs and documentation?
```

---

# 57. The Golden Rule

When something fails:

```text
Don't reinstall.
Don't delete the Docker volume.
Don't disable security.
Don't permanently disable TLS verification.
Don't disable authentication.
Don't expose port 5000.
Don't expose port 5050 unnecessarily.
Don't paste secrets into bug reports.
Don't change five things at once.
Don't modify the database without a backup.
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
