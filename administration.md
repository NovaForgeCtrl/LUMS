
# LUMS Administration Guide

> **Linux Update Management without the noise.**

Centralized update management, client inventory, reporting and controlled package deployment for Linux systems.

This guide documents the daily administration, maintenance, deployment and recovery of LUMS.

---

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Architecture](#2-architecture)
- [3. Runtime Configuration](#3-runtime-configuration)
- [4. Client Paths](#4-client-paths)
- [5. Docker Administration](#5-docker-administration)
- [6. Docker Logs](#6-docker-logs)
- [7. Nginx Administration](#7-nginx-administration)
- [8. Network and Health Checks](#8-network-and-health-checks)
- [9. TLS Administration](#9-tls-administration)
- [10. Server Environment](#10-server-environment)
- [11. Agent Configuration](#11-agent-configuration)
- [12. Agent Service and Timer](#12-agent-service-and-timer)
- [13. Execution Watcher](#13-execution-watcher)
- [14. Idle-Aware Execution](#14-idle-aware-execution)
- [15. Update Job Lifecycle](#15-update-job-lifecycle)
- [16. Simulation Mode](#16-simulation-mode)
- [17. Package Manager Safety](#17-package-manager-safety)
- [18. Database Administration](#18-database-administration)
- [19. Database Backup and Restore](#19-database-backup-and-restore)
- [20. Git Administration](#20-git-administration)
- [21. Docker Deployment](#21-docker-deployment)
- [22. Agent and Watcher Deployment](#22-agent-and-watcher-deployment)
- [23. Post-Deployment Validation](#23-post-deployment-validation)
- [24. Troubleshooting](#24-troubleshooting)
- [25. Security Administration](#25-security-administration)
- [26. Backup Strategy](#26-backup-strategy)
- [27. Recovery Strategy](#27-recovery-strategy)
- [28. Operational Principles](#28-operational-principles)
- [29. Final Checklist](#29-final-checklist)

---

# 1. Purpose

This guide covers the daily administration of LUMS:

- Docker administration
- Nginx administration
- Client and agent management
- Reporting and execution watchers
- Idle-aware update jobs
- Database maintenance
- Database backups and recovery
- TLS and authentication
- Git-based deployment
- Troubleshooting
- Security administration

LUMS centralizes management while package execution remains on the individual Linux client.

!!! note

    LUMS does not automatically reboot clients. Reboots remain an administrative decision.

---

# 2. Architecture

## 2.1 Server Architecture

```text
Web Browser
    |
    | HTTPS :443
    v
Nginx
    |
    | HTTP localhost
    v
127.0.0.1:5050
    |
    | Docker port mapping
    v
Docker Container: lums
    |
    | Flask :5000
    v
LUMS Application
    |
    v
Docker Volume: lums-data
    |
    v
/var/lib/lums/lums.db
```

The Flask application is accessible externally through Nginx.

The Docker application is bound to localhost:

```text
127.0.0.1:5050 → Container port 5000
```

Port `5000` must not be directly exposed to the network.

## 2.2 Client Architecture

```text
lums-agent.timer
    |
    v
lums-agent.service
    |
    v
agent.py
    |
    +--> Inventory
    +--> Reporting
    +--> Client state
    +--> Update information


lums-execution-watcher.timer
    |
    v
lums-execution-watcher.service
    |
    v
watcher.py
    |
    +--> Idle detection
    +--> Pending-job lookup
    +--> Atomic claim
    +--> Package execution
    +--> Result reporting
```

Reporting and update execution are separate processes.

---

# 3. Runtime Configuration

| Component | Value |
|---|---|
| Repository | `/opt/lums-public` |
| Docker container | `lums` |
| Docker image | `lums:latest` |
| Docker volume | `lums-data` |
| Flask port | `5000` |
| Host binding | `127.0.0.1:5050` |
| HTTP | `80` |
| HTTPS | `443` |
| Server environment | `/etc/lums/docker/lums.env` |
| Database | `/var/lib/lums/lums.db` |
| TLS certificate | `/etc/lums/tls/lums.crt` |
| TLS private key | `/etc/lums/tls/lums.key` |

## 3.1 Generic Placeholders

Use placeholders in documentation and examples:

```text
<LUMS_SERVER_IP>
<CLIENT_IP>
<CLIENT_ID>
<CLIENT_TOKEN>
<ADMIN_PASSWORD>
```

!!! danger

    Never publish real credentials, client tokens, private keys, session secrets or production database files.

---

# 4. Client Paths

| Component | Path |
|---|---|
| Agent source | `/opt/lums-public/agent/agent.py` |
| Watcher source | `/opt/lums-public/agent/watcher.py` |
| Installed agent | `/opt/lums-agent/agent.py` |
| Installed watcher | `/opt/lums-agent/watcher.py` |
| Agent configuration | `/etc/default/lums-agent` |
| CA certificate | `/opt/lums-agent/lums-ca.crt` |
| Agent service | `lums-agent.service` |
| Agent timer | `lums-agent.timer` |
| Watcher service | `lums-execution-watcher.service` |
| Watcher timer | `lums-execution-watcher.timer` |

The source files are maintained in Git.

The installed client files are deployed to the individual Linux clients.

---

# 5. Docker Administration

## 5.1 Check the Running Container

```bash
sudo docker ps \
    --filter "name=^/lums$"
```

## 5.2 Check All Containers

```bash
sudo docker ps -a
```

## 5.3 Check Container State

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Expected result:

```text
running
```

## 5.4 Check Restart Policy

```bash
sudo docker inspect \
    --format '{{.HostConfig.RestartPolicy.Name}}' \
    lums
```

Expected result:

```text
unless-stopped
```

## 5.5 Start, Stop and Restart

```bash
sudo docker start lums
sudo docker stop lums
sudo docker restart lums
```

Stopping or restarting the container interrupts the web interface and API.

The database remains persistent as long as the `lums-data` volume is preserved.

!!! danger

    Do not remove `lums-data` during normal application maintenance.

## 5.6 Inspect the Container Configuration

```bash
sudo docker inspect lums
```

Check the published ports:

```bash
sudo docker port lums
```

Check the mounted volumes:

```bash
sudo docker inspect \
    --format '{{json .Mounts}}' \
    lums
```

---

# 6. Docker Logs

## 6.1 View Recent Logs

```bash
sudo docker logs \
    --tail 100 \
    lums
```

## 6.2 View Recent Time Range

```bash
sudo docker logs \
    --since 10m \
    lums
```

## 6.3 Follow Logs

```bash
sudo docker logs \
    --follow \
    lums
```

## 6.4 Search for Errors

```bash
sudo docker logs lums 2>&1 \
    | grep -iE 'error|exception|traceback|failed'
```

!!! warning

    Review logs before sharing them. Remove tokens, session information, personal data and other sensitive content.

---

# 7. Nginx Administration

## 7.1 Validate Configuration

```bash
sudo nginx -t
```

Only continue when the configuration test succeeds.

## 7.2 Reload Configuration

```bash
sudo systemctl reload nginx
```

## 7.3 Check Service Status

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

## 7.4 View Logs

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Follow logs:

```bash
sudo journalctl \
    -u nginx \
    -f
```

## 7.5 Restart Nginx

```bash
sudo systemctl restart nginx
```

Restart Nginx only when required.

A configuration reload is normally preferable after a configuration change.

---

# 8. Network and Health Checks

## 8.1 Check Listening Ports

```bash
sudo ss -lntp
```

## 8.2 Check Docker Port Mapping

```bash
sudo docker port lums
```

Expected mapping:

```text
5000/tcp -> 127.0.0.1:5050
```

## 8.3 Test the Local Application

```bash
curl -I \
    http://127.0.0.1:5050/
```

A redirect to `/login` may be expected.

## 8.4 Test HTTPS

```bash
curl -k -I \
    https://<LUMS_SERVER_IP>/
```

## 8.5 Test the API

```bash
curl -k \
    https://<LUMS_SERVER_IP>/api/health
```

!!! warning

    The `-k` option disables certificate verification and is intended only for diagnostics.

Normal agent operation must use certificate verification.

---

# 9. TLS Administration

## 9.1 Certificate Paths

Certificate:

```text
/etc/lums/tls/lums.crt
```

Private key:

```text
/etc/lums/tls/lums.key
```

## 9.2 Inspect Certificate Information

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

## 9.3 Inspect Subject Alternative Names

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -ext subjectAltName
```

The address used by the agent must be represented in the certificate SAN.

## 9.4 Protect the Private Key

```bash
sudo chown root:root \
    /etc/lums/tls/lums.key

sudo chmod 600 \
    /etc/lums/tls/lums.key
```

Recommended certificate permissions:

```bash
sudo chmod 644 \
    /etc/lums/tls/lums.crt
```

!!! danger

    Never permanently disable TLS verification.

---

# 10. Server Environment

The Docker environment file is:

```text
/etc/lums/docker/lums.env
```

## 10.1 Protect the Environment File

```bash
sudo chown root:root \
    /etc/lums/docker/lums.env

sudo chmod 600 \
    /etc/lums/docker/lums.env
```

## 10.2 Check Whether a Variable Exists

The value is not displayed:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' \
    /etc/lums/docker/lums.env \
    && echo "Secret vorhanden" \
    || echo "Secret fehlt"
```

## 10.3 Inspect Variable Names Only

```bash
sudo sed \
    -E 's/=.*$/=<redacted>/' \
    /etc/lums/docker/lums.env
```

!!! warning

    Do not commit the environment file to Git or include it in screenshots.

---

# 11. Agent Configuration

The actual client configuration is stored in:

```text
/etc/default/lums-agent
```

Example configuration:

```dotenv
LUMS_BASE="https://<LUMS_SERVER_IP>"
LUMS_TOKEN="<CLIENT_TOKEN>"
LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt"
```

## 11.1 Protect the Configuration

```bash
sudo chown root:root \
    /etc/default/lums-agent

sudo chmod 600 \
    /etc/default/lums-agent
```

## 11.2 Display Safe Values

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

Never display the real client token in shared logs or screenshots.

---

# 12. Agent Service and Timer

## 12.1 Check the Service

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

## 12.2 Run One Reporting Cycle

```bash
sudo systemctl start \
    lums-agent.service
```

## 12.3 View Logs

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

## 12.4 Enable the Timer

```bash
sudo systemctl enable \
    --now \
    lums-agent.timer
```

## 12.5 Check Scheduled Execution

```bash
systemctl list-timers \
    --all \
    | grep lums-agent
```

The agent service is a `oneshot` service.

After a successful run, the service may show `inactive (dead)`. This can be normal because the timer starts it again.

The current reporting interval is approximately five minutes.

---

# 13. Execution Watcher

The execution watcher is separate from reporting.

## 13.1 Current Versions

| Component | Version |
|---|---|
| Agent | `1.6.0` |
| Watcher | `1.2.1` |

## 13.2 Watcher Workflow

```text
1. Check for a running job
2. Recover a running job if present
3. Request pending jobs
4. Determine local idle state
5. Verify idle support
6. Verify the configured idle threshold
7. Atomically claim a pending job
8. Execute only the claimed job
9. Submit the result
```

## 13.3 Enable the Watcher Timer

```bash
sudo systemctl daemon-reload

sudo systemctl enable \
    --now \
    lums-execution-watcher.timer
```

## 13.4 Check the Timer

```bash
sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager
```

## 13.5 Run One Watcher Cycle

```bash
sudo systemctl start \
    lums-execution-watcher.service
```

## 13.6 View Watcher Logs

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
```

The current laboratory timer runs approximately every 30 seconds.

---

# 14. Idle-Aware Execution

The current implementation uses:

```text
w -h
```

for server, terminal and SSH-oriented idle detection.

The configured idle threshold is:

```text
300 seconds
5 minutes
```

The watcher must not execute a job when:

- Idle detection is unsupported.
- The idle threshold has not been reached.
- The job cannot be claimed atomically.
- The client is not properly authenticated.
- No valid pending job exists.

!!! note

    The current implementation is not a universal desktop-idle provider. Desktop environments may require an additional idle-detection provider in the future.

## 14.1 Idle Metadata

The agent reports fields similar to:

```json
{
  "idle": false,
  "idle_seconds": 5,
  "idle_threshold_seconds": 300,
  "idle_source": "w",
  "idle_supported": true
}
```

If idle detection is unavailable:

```json
{
  "idle": false,
  "idle_seconds": 0,
  "idle_threshold_seconds": 300,
  "idle_source": "w",
  "idle_supported": false
}
```

Unsupported idle detection must result in safe non-execution.

---

# 15. Update Job Lifecycle

```text
pending
   |
   v
Idle check
   |
   v
Atomic claim
   |
   v
running
   |
   +--> success
   +--> partial
   +--> failed
```

A pending job is not executed simply because it exists.

The watcher first checks the local idle state and then performs an atomic claim.

Only the successfully claimed job may be executed.

## 15.1 Atomic Claiming

Claim endpoint:

```text
POST /api/clients/<CLIENT_ID>/update-jobs/<JOB_ID>/claim
```

The server uses an atomic database operation to prevent multiple agents or watcher cycles from claiming the same pending job.

If the job is no longer pending, the claim must fail safely.

The request must not execute a job that it failed to claim.

## 15.2 Running-Job Recovery

The watcher checks for an existing running job before requesting a new pending job.

This supports recovery after:

- Service interruption
- Watcher restart
- SSH disconnection
- System restart
- Interrupted execution workflow

A recovered running job is resumed without claiming it a second time.

## 15.3 Update Results

Result endpoint:

```text
POST /api/update-jobs/<JOB_ID>/result
```

A result may contain:

- Overall status
- Package results
- Successful package count
- Failed package count
- Timeout information
- Reboot requirement

Supported statuses:

```text
success
partial
failed
```

The server validates that:

- The job belongs to the authenticated client.
- The job is currently running.
- The result status is valid.

---

# 16. Simulation Mode

Simulation mode is intended for safe end-to-end testing.

It:

- Does not execute real APT updates.
- Does not modify installed packages.
- Simulates package results.
- Tests job claiming.
- Tests watcher behavior.
- Tests result reporting.
- Tests UI state changes.

The setting is:

```text
LUMS_SIMULATE_UPDATES
```

## 16.1 Inspect the Service

```bash
sudo systemctl cat \
    lums-execution-watcher.service
```

Temporary simulation mode:

```bash
sudo systemctl edit \
    --runtime \
    lums-execution-watcher.service
```

Add:

```ini
[Service]
Environment=LUMS_SIMULATE_UPDATES=1
```

Run a test cycle:

```bash
sudo systemctl start \
    lums-execution-watcher.service
```

Remove the temporary setting:

```bash
sudo systemctl revert \
    --runtime \
    lums-execution-watcher.service

sudo systemctl daemon-reload
```

!!! danger

    Simulation mode must not remain enabled outside testing.

A successful simulation does not prove that real APT/dpkg collisions are fully prevented.

---

# 17. Package Manager Safety

The current project does not provide complete coordination with arbitrary manual APT or dpkg commands.

Current limitations:

- A custom LUMS lock does not automatically control manual APT commands.
- An external package-manager process may already be active.
- Removing lock files is unsafe.
- Full coordination requires additional detection, waiting and operational policy.

Future hardening may include:

- LUMS execution lock
- Active process detection
- APT/dpkg lock checks
- Wait-and-retry behavior
- Execution timeouts
- Deferred job states
- Maintenance windows

!!! danger

    Never delete foreign APT or dpkg lock files.

## 17.1 APT Administration

The client performs package operations locally.

Update package metadata:

```bash
sudo apt update
```

List available updates:

```bash
apt list --upgradable
```

Inspect a package:

```bash
apt-cache policy <PACKAGE_NAME>
```

Inspect installation state:

```bash
dpkg -l <PACKAGE_NAME>
```

The current update operation is designed for package updates rather than a complete distribution upgrade.

If APT or dpkg is already broken, resolve the client-side package-manager problem first.

## 17.2 Reboot Handling

LUMS does not automatically reboot clients.

Check whether a reboot is required:

```bash
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot required"
```

A reboot remains an administrative decision.

---

# 18. Database Administration

The database is:

```text
/var/lib/lums/lums.db
```

It is stored in the Docker volume:

```text
lums-data
```

## 18.1 Check Database Integrity

```bash
sudo docker exec \
    lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
result = db.execute("PRAGMA integrity_check;").fetchone()[0]
print(result)
db.close()
'
```

Expected result:

```text
ok
```

!!! danger

    Do not remove the Docker volume as a first troubleshooting action.

## 18.2 Check the Database File

```bash
sudo docker exec \
    lums \
    ls -lh \
    /var/lib/lums/lums.db
```

---

# 19. Database Backup and Restore

## 19.1 Create Backup Directory

```bash
sudo install \
    -d \
    -m 700 \
    /var/backups/lums
```

## 19.2 Create a SQLite-Aware Backup

The following method uses SQLite's online backup mechanism from a temporary container.

```bash
sudo docker run --rm \
    -v lums-data:/var/lib/lums:ro \
    -v /var/backups/lums:/backup \
    lums:latest \
    python3 -c '
import sqlite3

source = sqlite3.connect("/var/lib/lums/lums.db")
target = sqlite3.connect("/backup/lums-$(date +%F-%H%M%S).db")

with target:
    source.backup(target)

target.close()
source.close()

print("SQLite backup completed")
'
```

!!! warning

    Shell command substitution does not occur inside the Python string. For a timestamped filename, define the filename in the shell before running the container.

Recommended version:

```bash
BACKUP_FILE="/var/backups/lums/lums-$(date +%F-%H%M%S).db"

sudo docker run --rm \
    -v lums-data:/var/lib/lums:ro \
    -v /var/backups/lums:/backup \
    lums:latest \
    python3 -c '
import sqlite3

source = sqlite3.connect("/var/lib/lums/lums.db")
target = sqlite3.connect("/backup/backup.db")

with target:
    source.backup(target)

target.close()
source.close()

print("SQLite backup completed")
'

sudo mv \
    /var/backups/lums/backup.db \
    "$BACKUP_FILE"

sudo chmod 600 \
    "$BACKUP_FILE"
```

## 19.3 Verify the Backup

```bash
sudo python3 -c '
import sqlite3
import sys

path = sys.argv[1]
db = sqlite3.connect(path)
result = db.execute("PRAGMA integrity_check;").fetchone()[0]
print(result)
db.close()
' "$BACKUP_FILE"
```

Expected result:

```text
ok
```

## 19.4 Restore Principles

Before restoring:

1. Stop normal administrative changes.
2. Create a backup of the current database.
3. Verify the restore source.
4. Stop the LUMS container.
5. Restore the database.
6. Check ownership and permissions.
7. Start the container.
8. Run `PRAGMA integrity_check`.
9. Test administrator authentication.
10. Test client authentication.
11. Test reporting and update jobs.

!!! danger

    Never overwrite the only available database copy.

A database restore should be tested in a controlled environment whenever possible.

---

# 20. Git Administration

Repository:

```text
/opt/lums-public
```

## 20.1 Check Status

```bash
cd /opt/lums-public

git status
```

## 20.2 Check Latest Commit

```bash
git log \
    -1 \
    --oneline \
    --decorate
```

## 20.3 Check Remote

```bash
git remote -v
```

## 20.4 Fetch Changes

```bash
git fetch origin
```

## 20.5 Update a Clean Working Tree

```bash
git pull \
    --ff-only \
    origin main
```

## 20.6 Check Synchronization

```bash
git rev-list \
    --left-right \
    --count \
    HEAD...origin/main
```

Expected after synchronization:

```text
0       0
```

Do not use `git reset --hard` without first reviewing local changes and confirming that no required work will be lost.

---

# 21. Git Validation

Before deployment:

```bash
cd /opt/lums-public

git status

git diff --check
```

## 21.1 Validate Python Syntax

```bash
python3 -m py_compile \
    server/app.py \
    server/init_db.py \
    agent/agent.py \
    agent/watcher.py
```

Do not deploy if validation fails.

## 21.2 Git Identity

The repository identity is:

| Setting | Value |
|---|---|
| Name | `xxxxx` |
| Email | `xxxxx` |

Check the configured identity:

```bash
git config user.name
git config user.email
```

---

# 22. Docker Deployment

A deployment should follow this order:

```text
Review Git changes
       |
       v
Validate source
       |
       v
Create SQLite backup
       |
       v
Build Docker image
       |
       v
Recreate container
       |
       v
Test local application
       |
       v
Test Nginx and HTTPS
       |
       v
Validate browser interface
```

## 22.1 Build the Image

```bash
cd /opt/lums-public

sudo docker build \
    -t lums:latest \
    .
```

## 22.2 Verify the Image

```bash
sudo docker image inspect \
    lums:latest
```

## 22.3 Recreate the Container

!!! warning

    Confirm that the database backup exists and that the `lums-data` volume will be reused.

```bash
sudo docker stop lums

sudo docker rm lums
```

Do not remove the volume.

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

## 22.4 Verify the Container

```bash
sudo docker ps \
    --filter "name=^/lums$"
```

```bash
sudo docker logs \
    --tail 100 \
    lums
```

!!! note

    `docker restart lums` restarts the existing container but does not load newly built image files. Source and frontend changes require an image rebuild and container recreation.

---

# 23. Agent and Watcher Deployment

After changing the agent or watcher source files, install both files on the client.

## 23.1 Install Agent

```bash
cd /opt/lums-public

sudo install \
    -o root \
    -g root \
    -m 0750 \
    agent/agent.py \
    /opt/lums-agent/agent.py
```

## 23.2 Install Watcher

```bash
sudo install \
    -o root \
    -g root \
    -m 0750 \
    agent/watcher.py \
    /opt/lums-agent/watcher.py
```

## 23.3 Validate the Installed Files

```bash
sudo python3 -m py_compile \
    /opt/lums-agent/agent.py \
    /opt/lums-agent/watcher.py
```

## 23.4 Reload Systemd

Only required when unit files or service configuration changed:

```bash
sudo systemctl daemon-reload
```

Trigger a reporting cycle:

```bash
sudo systemctl start \
    lums-agent.service
```

Trigger a watcher cycle:

```bash
sudo systemctl start \
    lums-execution-watcher.service
```

Review the corresponding logs after execution.

---

# 24. Post-Deployment Validation

## 24.1 Check Container State

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

## 24.2 Test Local Application

```bash
curl -I \
    http://127.0.0.1:5050/
```

## 24.3 Test HTTPS

```bash
curl -k -I \
    https://<LUMS_SERVER_IP>/
```

## 24.4 Test API

```bash
curl -k \
    https://<LUMS_SERVER_IP>/api/health
```

## 24.5 Validate Nginx

```bash
sudo nginx -t
```

## 24.6 Test Reporting Agent

```bash
sudo systemctl start \
    lums-agent.service
```

## 24.7 Test Watcher

```bash
sudo systemctl start \
    lums-execution-watcher.service
```

## 24.8 Review Logs

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
```

After frontend changes, refresh the browser using:

```text
Ctrl + F5
```

---

# 25. Troubleshooting

## 25.1 Troubleshooting Method

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

Troubleshoot in this order:

```text
Network
   |
   v
Nginx / TLS
   |
   v
Docker / Flask
   |
   v
SQLite
   |
   v
Agent
   |
   v
Watcher
   |
   v
APT / dpkg
```

## 25.2 Basic Diagnostic Sequence

```bash
ping <LUMS_SERVER_IP>

sudo ss -lntp

sudo nginx -t

sudo docker ps -a

sudo docker logs \
    --tail 100 \
    lums

curl -I \
    http://127.0.0.1:5050/

curl -k -I \
    https://<LUMS_SERVER_IP>/

curl -k \
    https://<LUMS_SERVER_IP>/api/health

sudo systemctl status \
    lums-agent.timer \
    --no-pager

sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager
```

## 25.3 Container Is Not Running

```bash
sudo docker ps -a \
    --filter "name=^/lums$"
```

```bash
sudo docker logs \
    --tail 200 \
    lums
```

```bash
sudo docker inspect \
    lums
```

Check:

- Container exit code.
- Environment configuration.
- Port conflicts.
- Image availability.
- Volume mounting.
- Application startup errors.

## 25.4 Port 5050 Is Unavailable

```bash
sudo ss -lntp \
    | grep ':5050'
```

```bash
sudo docker port \
    lums
```

```bash
curl -I \
    http://127.0.0.1:5050/
```

Check whether another process is using port `5050`.

## 25.5 Nginx Failure

```bash
sudo nginx -t
```

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Check:

- Configuration syntax.
- Upstream address.
- TLS certificate paths.
- TLS private key permissions.
- Docker availability.
- Port `5050`.

## 25.6 Agent Authentication Failure

Display safe configuration values:

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

Inspect agent logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Inspect server logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Possible causes:

- Invalid token.
- Incorrect server URL.
- Missing CA certificate.
- TLS SAN mismatch.
- Client not registered.
- Server unavailable.
- Incorrect token hash.
- Authentication or authorization failure.

## 25.7 Client Appears Offline

Run one reporting cycle:

```bash
sudo systemctl start \
    lums-agent.service
```

Review logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Possible causes:

- Timer is inactive.
- Network failure.
- TLS failure.
- Invalid token.
- Server unavailable.
- Agent exception.
- Database issue.

## 25.8 Update Job Is Not Executed

Check:

- Client is enabled.
- Client token is valid.
- Pending job exists.
- Idle detection is supported.
- Idle threshold is reached.
- Watcher timer is active.
- APT repositories work.
- No conflicting package manager is running.

Run a watcher cycle:

```bash
sudo systemctl start \
    lums-execution-watcher.service
```

Inspect logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
```

## 25.9 Theme or Frontend Problem

Check the browser theme:

```javascript
localStorage.getItem("lums-theme");
```

Check the applied theme:

```javascript
document.documentElement.dataset.theme;
```

Then verify:

1. Git source files.
2. Docker image build.
3. Running container.
4. Static assets.
5. Nginx response.
6. Browser cache.

Refresh the browser:

```text
Ctrl + F5
```

---

# 26. Security Administration

## 26.1 Files That Must Not Be Committed

Never commit:

```text
/etc/lums/docker/lums.env
/etc/default/lums-agent
TLS private keys
Client tokens
Production databases
Database backups
Private certificates
```

## 26.2 Recommended Permissions

| Resource | Permission |
|---|---|
| Server environment | `0600` |
| Agent configuration | `0600` |
| TLS private key | `0600` |
| Public certificate | `0644` |
| Database backups | `0600` |

## 26.3 Review Permissions

```bash
sudo ls -l \
    /etc/lums/docker/lums.env
```

```bash
sudo ls -l \
    /etc/default/lums-agent
```

```bash
sudo ls -l \
    /etc/lums/tls/
```

## 26.4 Search Repository for Sensitive Files

Run from the repository root:

```bash
cd /opt/lums-public

find . -type f \
    \( \
        -name "*.env" \
        -o -name "*.key" \
        -o -name "*.pem" \
        -o -name "*.db" \
    \)
```

Review the results before committing.

## 26.5 Security Principles

- Keep Flask behind Nginx.
- Bind the application to localhost.
- Use HTTPS for client/server communication.
- Keep TLS verification enabled.
- Store client token hashes rather than plaintext tokens.
- Keep secrets outside Git.
- Do not expose sensitive logs.
- Preserve authentication and authorization boundaries.
- Test security-sensitive changes before deployment.

---

# 27. Backup Strategy

A recoverable installation requires more than Git.

Back up the following components:

- SQLite database.
- Docker environment file.
- Nginx configuration.
- TLS certificate.
- TLS private key.
- Agent configuration.
- CA certificate.
- Git repository.
- Deployment documentation.

Git contains source code and documentation, but not runtime secrets or database state.

## 27.1 Recommended Sequence

```text
Backup
   |
   v
Change
   |
   v
Validate
   |
   v
Test
   |
   v
Document
```

## 27.2 Backup Considerations

Protect backups because they may contain:

- Client information.
- Inventory data.
- Administrative data.
- Configuration information.
- Historical update information.

Store backups outside the Git repository.

Restrict permissions and test restoration periodically.

---

# 28. Recovery Strategy

A complete recovery process may include:

1. Restore or reinstall the operating system.
2. Install Docker and Nginx.
3. Restore the Git repository.
4. Restore the environment configuration.
5. Restore TLS configuration.
6. Restore the database or Docker volume.
7. Build the Docker image.
8. Start the LUMS container.
9. Configure Nginx.
10. Test HTTPS.
11. Test administrator authentication.
12. Test client authentication.
13. Test reporting.
14. Test the execution watcher.
15. Test update-job handling.
16. Review logs.
17. Document the recovery.

Recovery should be tested against a known backup.

!!! warning

    A backup that has never been restored should not be treated as fully verified.

---

# 29. Operational Principles

- Identify the failing layer before reinstalling.
- Keep persistent data outside the Docker image.
- Keep secrets outside Git.
- Keep Flask behind Nginx.
- Bind the application to localhost only.
- Use HTTPS for client/server communication.
- Keep TLS verification enabled.
- Separate authentication and authorization.
- Store client token hashes rather than plaintext tokens.
- Keep update execution on the client.
- Do not automatically reboot clients.
- Back up before database changes.
- Validate configuration before restarting services.
- Use `git pull --ff-only` for routine synchronization.
- Preserve `lums-data` during deployments.
- Test security-sensitive changes.
- Document configuration changes.
- Do not expose secrets in logs or screenshots.
- Keep simulation mode disabled outside testing.
- Treat APT/dpkg coordination as an explicit operational concern.
- Verify recovery procedures regularly.

---

# 30. Final Checklist

## Git and Source

- [ ] Git working tree reviewed.
- [ ] Repository synchronized.
- [ ] `git diff --check` passes.
- [ ] Python syntax checks pass.
- [ ] No secrets are present in Git.
- [ ] Documentation matches the current deployment.

## Docker

- [ ] Docker image builds successfully.
- [ ] Container `lums` is running.
- [ ] Volume `lums-data` exists.
- [ ] Container restart policy is `unless-stopped`.
- [ ] Port `5000` is not directly exposed.
- [ ] Application is bound to `127.0.0.1:5050`.
- [ ] Container logs contain no unresolved startup errors.

## Nginx and TLS

- [ ] Nginx configuration passes.
- [ ] HTTPS works.
- [ ] TLS SAN is correct.
- [ ] TLS private key permissions are restricted.
- [ ] Certificate paths are correct.
- [ ] TLS verification remains enabled.

## Authentication and Security

- [ ] Environment file permissions are restricted.
- [ ] Agent configuration permissions are restricted.
- [ ] Administrator authentication works.
- [ ] Client authentication works.
- [ ] Client authorization works.
- [ ] Agent CA certificate is available.
- [ ] Client token configuration is valid.
- [ ] No sensitive information is exposed in logs.

## Agent and Watcher

- [ ] `lums-agent.timer` is active.
- [ ] `lums-execution-watcher.timer` is active.
- [ ] Agent reporting works.
- [ ] Idle detection works.
- [ ] Unsupported idle detection prevents execution.
- [ ] Update jobs can be created.
- [ ] Jobs are claimed atomically.
- [ ] Running jobs can be recovered.
- [ ] Results can be submitted.
- [ ] Simulation mode is disabled outside testing.

## Database and Recovery

- [ ] Database integrity check returns `ok`.
- [ ] Database backup exists.
- [ ] Backup permissions are restricted.
- [ ] Backup restoration procedure is documented.
- [ ] Recovery has been tested or scheduled for testing.
- [ ] The Docker volume is preserved during deployment.

---

> **LUMS — Linux Update Management without the noise.**

> Centralize the management. Keep execution controlled.

> Know what changed. Know where it happened.

> **One LUMS. Same Backend. Controlled Execution.**
