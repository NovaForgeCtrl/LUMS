# LUMS Troubleshooting Guide

## Linux Update Management Server

This document provides a structured troubleshooting procedure for LUMS.

The most important rule is:

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

LUMS consists of several independent layers. A failure in one layer does not automatically mean that the complete installation is broken.

The purpose of this guide is to identify the affected layer, verify the underlying assumption, make the smallest necessary change, and verify the result.

---

# 1. Golden Rule

Troubleshoot from the outside toward the inside:

```text
Browser
   ↓
HTTPS / TLS
   ↓
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker container
   ↓
Gunicorn
   ↓
Flask application
   ↓
SQLite database
   ↓
Authentication / Authorization
   ↓
Agent
   ↓
Package Manager
   ↓
Job execution
   ↓
Job result
```

For frontend problems, add the following layer:

```text
Browser
   ↓
HTML
   ↓
CSS
   ↓
theme.js
   ↓
network.js / client.js
   ↓
Selected Theme
   ↓
localStorage
   ↓
Browser Cache
```

Do not skip layers unless there is already clear evidence that the lower layers are working.

Example:

If:

```bash
curl -I http://127.0.0.1:5050/
```

already fails, debugging browser JavaScript is premature.

---

# 2. Current Architecture

The current LUMS deployment consists of:

```text
                         Browser
                            │
                            ▼
                    HTTPS / TLS :443
                            │
                            ▼
                         Nginx
                            │
                            ▼
                    127.0.0.1:5050
                            │
                            ▼
                  Docker container: lums
                            │
                            ▼
                    Gunicorn :5000
                            │
                            ▼
                       Flask
                            │
                            ▼
                  /var/lib/lums/lums.db
                            │
                            ▼
                       lums-data
```

The application source repository is:

```text
/opt/lums-public
```

The application source inside the image is:

```text
/app
```

The server application is located under:

```text
/app/server/
```

Frontend assets are located under:

```text
/app/server/static/
```

Persistent application data is stored in:

```text
/var/lib/lums/
```

The database is:

```text
/var/lib/lums/lums.db
```

The persistent Docker volume is:

```text
lums-data
```

---

# 3. Client Architecture

A LUMS client consists of:

```text
systemd
   │
   ├── lums-agent.service
   │
   ├── lums-agent.timer
   │
   └── execution watcher
          │
          ▼
       agent.py
          │
          ▼
   HTTPS / TLS
          │
          ▼
       LUMS API
```

The agent detects the available package manager.

Currently supported package managers are:

```text
APT / dpkg
pacman
```

The abstraction is implemented through:

```text
agent/package_manager.py
```

The agent therefore does not assume that every Linux client is Debian-based.

---

# 4. Current Agent Version

The current tested agent version is:

```text
1.6.0
```

Verify:

```bash
grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/agent.py
```

Expected:

```text
AGENT_VERSION = "1.6.0"
```

The installed client should use the same agent implementation as the repository version intended for deployment.

---

# 5. Current Tested Distributions

LUMS has been tested end-to-end with:

```text
Debian 13
Arch Linux
```

The Debian client uses:

```text
APT / dpkg
```

The Arch client uses:

```text
pacman
```

A successful test includes more than package detection.

The complete chain is:

```text
Client
   ↓
Agent
   ↓
TLS
   ↓
Authentication
   ↓
Report
   ↓
Database
   ↓
Frontend
```

For update jobs:

```text
LUMS
   ↓
Job
   ↓
Agent
   ↓
Package Manager
   ↓
Execution
   ↓
Result
   ↓
LUMS
```

---

# 6. Current Container Security State

The production LUMS container is hardened.

Expected configuration:

```text
User:
    lums

UID:
    10001

Root filesystem:
    read-only

Capabilities:
    ALL dropped

Privileged:
    false

Temporary filesystem:
    /tmp tmpfs

Persistent data:
    lums-data

Secret:
    read-only secret file
```

The hardened container configuration is:

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

Do not use older insecure container commands from previous documentation.

---

# 7. Troubleshooting Order

Use this order whenever possible:

```text
1. Network
2. HTTPS / TLS
3. Nginx
4. Docker
5. Gunicorn
6. Flask
7. Database
8. Authentication
9. Authorization
10. Agent connectivity
11. Agent TLS
12. Agent authentication
13. Agent reporting
14. Job creation
15. Job claiming
16. Job recovery
17. Package manager
18. Job execution
19. Job result
20. Frontend
21. Theme system
22. Browser cache
```

If a lower layer is broken, do not spend time debugging a higher layer yet.

---

# 8. Important Paths

## Source Repository

```text
/opt/lums-public
```

## Server Application

```text
/opt/lums-public/server/
```

## Server Templates

```text
/opt/lums-public/server/templates/
```

## Server Static Files

```text
/opt/lums-public/server/static/
```

Important frontend files:

```text
/opt/lums-public/server/static/style.css
/opt/lums-public/server/static/theme.js
/opt/lums-public/server/static/network.js
/opt/lums-public/server/static/client.js
```

## Runtime Application

Inside the container:

```text
/app
```

## Runtime Frontend

```text
/app/server/static/
```

## Persistent Database

```text
/var/lib/lums/lums.db
```

## Docker Volume

```text
lums-data
```

## Docker Environment File

```text
/etc/lums/docker/lums.env
```

## Flask Secret

Host:

```text
/etc/lums/secrets/lums_secret
```

Container:

```text
/run/secrets/lums_secret
```

## TLS Files

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

## Agent

```text
/opt/lums-agent/agent.py
/opt/lums-agent/watcher.py
/opt/lums-agent/lums-ca.crt
/etc/default/lums-agent
```

---

# 9. Docker Diagnostics

Check whether the container exists:

```bash
sudo docker ps -a \
    --filter name=lums
```

Check whether it is running:

```bash
sudo docker ps \
    --filter name=lums
```

Check the state:

```bash
sudo docker inspect \
    -f '{{.State.Status}}' \
    lums
```

Expected:

```text
running
```

Check recent logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Follow logs:

```bash
sudo docker logs -f lums
```

Stop following:

```text
Ctrl+C
```

---

# 10. Docker Image Diagnostics

List LUMS images:

```bash
sudo docker images lums
```

Check the image used by the running container:

```bash
sudo docker inspect \
    -f '{{.Config.Image}}' \
    lums
```

Expected:

```text
lums:latest
```

Check the image ID:

```bash
sudo docker inspect \
    -f '{{.Image}}' \
    lums
```

After source changes:

```bash
cd /opt/lums-public

sudo docker build \
    -t lums:latest \
    .
```

Verify:

```bash
sudo docker image inspect \
    lums:latest
```

Important:

> Building a new image does not automatically update an existing container.

The container must be recreated when application files inside the image have changed.

---

# 11. Gunicorn Diagnostics

The production application server is Gunicorn.

The Flask development server is not used for production operation.

Check:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Look for:

```text
Starting Gunicorn
Listening at: http://0.0.0.0:5000
Booting worker
```

If Gunicorn does not start, investigate the container logs before changing Nginx.

Typical failure chain:

```text
Docker
   ↓
Gunicorn
   ↓
Flask import
   ↓
Application initialization
```

A Python import error can therefore appear as an apparently broken web server.

---

# 12. Docker Port Diagnostics

Current architecture:

```text
Host:
127.0.0.1:5050

Container:
5000
```

Check:

```bash
sudo ss -lntp | \
    grep ':5050'
```

Expected pattern:

```text
127.0.0.1:5050
```

Test directly:

```bash
curl -I \
    http://127.0.0.1:5050/
```

Expected behavior:

```text
HTTP/1.1 302 FOUND
Location: /login
```

If this works but HTTPS does not:

```text
Docker
   ↓
working

Nginx / TLS
   ↓
investigate
```

If this fails:

```text
Docker / Gunicorn / Flask
   ↓
investigate first
```

---

# 13. Docker Volume Diagnostics

Inspect the volume:

```bash
sudo docker volume inspect \
    lums-data
```

Check container mounts:

```bash
sudo docker inspect lums \
    --format \
    '{{range .Mounts}}{{println .Name .Destination}}{{end}}'
```

Expected:

```text
lums-data /var/lib/lums
```

The database must remain on the persistent volume.

Do not delete the volume during normal container recreation.

---

# 14. Container Hardening Diagnostics

Verify:

```bash
sudo docker inspect lums \
    --format \
    'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{json .HostConfig.CapDrop}} Privileged={{.HostConfig.Privileged}}'
```

Expected:

```text
User=lums
ReadonlyRootfs=true
CapDrop=["ALL"]
Privileged=false
```

If these values unexpectedly differ after deployment, investigate before considering the deployment complete.

---

# 15. Secret Diagnostics

The production Flask secret is loaded from:

```text
/run/secrets/lums_secret
```

The host source is:

```text
/etc/lums/secrets/lums_secret
```

Verify without displaying the secret:

```bash
sudo docker exec lums sh -c '
if [ -n "${LUMS_SECRET_KEY:-}" ]; then
    echo "LUMS_SECRET_KEY=PRESENT"
else
    echo "LUMS_SECRET_KEY=ABSENT"
fi

echo "LUMS_SECRET_KEY_FILE=${LUMS_SECRET_KEY_FILE}"

if [ -r /run/secrets/lums_secret ]; then
    echo "SECRET_FILE=READABLE"
else
    echo "SECRET_FILE=NOT_READABLE"
fi
'
```

Expected:

```text
LUMS_SECRET_KEY=ABSENT
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
SECRET_FILE=READABLE
```

Never run:

```bash
cat /etc/lums/secrets/lums_secret
```

during normal diagnostics.

Never put the secret into:

```text
logs
screenshots
documentation
Git
bug reports
chat messages
```

---

# 16. Secret File Permissions

Check:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/secrets/lums_secret
```

Expected:

```text
root:10001
```

with:

```text
640
```

The containing directory should be restricted:

```text
/etc/lums/secrets
```

Expected directory mode:

```text
700
```

If the secret cannot be read by the container, verify permissions before changing application code.

---

# 17. Environment Diagnostics

Do not print the complete environment file.

Use:

```bash
sudo awk -F= '
/^[A-Za-z_][A-Za-z0-9_]*=/ {
    print $1 "=<set>"
}' /etc/lums/docker/lums.env
```

Inside the container:

```bash
sudo docker exec lums sh -c '
env |
grep -E "^(LUMS_|FLASK_|PYTHON)" |
sed "s/=.*$/=<set>/"
'
```

The production Flask secret should not be present as:

```text
LUMS_SECRET_KEY=<value>
```

The expected secret configuration is:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

---

# 18. Flask Diagnostics

Check:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Search for:

```text
Traceback
ERROR
Exception
sqlite
database
permission
Gunicorn
worker
```

Check application files:

```bash
sudo docker exec lums \
    ls -la /app
```

Check server:

```bash
sudo docker exec lums \
    ls -la /app/server
```

---

# 19. Nginx Diagnostics

Check configuration:

```bash
sudo nginx -t
```

Expected:

```text
syntax is ok
test is successful
```

Check service:

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

Check logs:

```bash
sudo journalctl \
    -u nginx \
    --since "30 minutes ago" \
    --no-pager
```

Access log:

```bash
sudo tail \
    -n 100 \
    /var/log/nginx/access.log
```

Error log:

```bash
sudo tail \
    -n 100 \
    /var/log/nginx/error.log
```

---

# 20. Nginx 502 Bad Gateway

A `502 Bad Gateway` normally means that Nginx cannot successfully reach the upstream application.

First test:

```bash
curl -I \
    http://127.0.0.1:5050/
```

If this fails, investigate:

```text
Docker
Gunicorn
Flask
```

Check:

```bash
sudo docker ps \
    --filter name=lums
```

Then:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

And:

```bash
sudo ss -lntp | \
    grep ':5050'
```

Only if these work should the investigation move to Nginx.

---

# 21. HTTPS / TLS

Check certificates:

```bash
sudo ls -l \
    /etc/lums/tls/
```

Inspect the certificate:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

Never publish:

```text
/etc/lums/tls/lums.key
```

Do not display the private key during normal troubleshooting.

---

# 22. TLS Connection Diagnostics

Test HTTPS:

```bash
curl -kI \
    https://<LUMS_SERVER_IP>/
```

Inspect the TLS handshake:

```bash
openssl s_client \
    -connect <LUMS_SERVER_IP>:443 \
    -servername <LUMS_SERVER_IP> \
    </dev/null
```

Check configured protocols:

```bash
sudo nginx -T | \
    grep -n 'ssl_protocols'
```

The expected configuration is:

```text
TLSv1.2
TLSv1.3
```

Older TLS versions should not be enabled.

---

# 23. HTTP Redirect

HTTP should redirect to HTTPS.

Test:

```bash
curl -I \
    http://<LUMS_SERVER_IP>/
```

Expected:

```text
HTTP/1.1 301 Moved Permanently
Location: https://...
```

If HTTP serves the application directly, investigate Nginx configuration.

---

# 24. Security Headers

Check:

```bash
curl -kI \
    https://<LUMS_SERVER_IP>/
```

Expected security headers include:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
```

The current application also uses a restrictive permissions policy and Content Security Policy.

If security headers unexpectedly disappear after deployment:

```text
Check Nginx
   ↓
Check response handling
   ↓
Check Flask security-header middleware
```

Do not immediately modify authentication code.

---

# 25. Agent TLS Problems

The agent trusts:

```text
/opt/lums-agent/lums-ca.crt
```

Check:

```bash
sudo test -f \
    /opt/lums-agent/lums-ca.crt \
    && echo "CA file present" \
    || echo "CA file missing"
```

Inspect:

```bash
sudo openssl x509 \
    -in /opt/lums-agent/lums-ca.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

If the CA file is missing or invalid, the agent may fail before authentication is even attempted.

---

# 26. Agent Connectivity

Check service:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Check logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Test HTTPS:

```bash
curl -kI \
    https://<LUMS_SERVER_IP>/
```

Break connectivity problems into:

```text
Agent
   ↓
Network
   ↓
TLS
   ↓
Nginx
   ↓
LUMS
```

---

# 27. Agent Authentication

LUMS stores client authentication tokens as SHA-256 hexadecimal digests.

This must not be confused with the password hashing mechanism.

Client authentication uses:

```text
Authorization: Bearer <CLIENT_TOKEN>
```

If the server returns:

```text
401 Unauthorized
```

check:

```text
1. Client exists
2. Client is enabled
3. Token is configured
4. Token corresponds to the registered client
5. Token has not been revoked
6. Authorization header reaches the server
7. Token authentication succeeds
```

Never display the token.

---

# 28. Client Token Rotation

LUMS supports authenticated client-token rotation.

The operation requires:

```text
Administrator authentication
+
CSRF validation
```

After rotation:

```text
Old token
    ↓
Invalid

New token
    ↓
Valid
```

The new token is displayed only as part of the controlled rotation workflow.

The plaintext token must not be stored in the audit log.

---

# 29. Token Rotation Troubleshooting

If a client stops authenticating immediately after rotation:

```text
1. Verify the correct client was rotated.
2. Obtain the newly generated token.
3. Update the agent configuration.
4. Restart the agent.
5. Inspect agent logs.
6. Inspect LUMS logs.
7. Verify a new report.
```

Check configuration without displaying the token:

```bash
sudo awk -F= '
/^(LUMS_BASE|LUMS_TOKEN|LUMS_CA_FILE)=/ {
    print $1 "=<set>"
}' /etc/default/lums-agent
```

Do not repeatedly rotate the same token during troubleshooting.

The rotation event is audited.

---

# 30. Agent Environment

Verify the file:

```bash
sudo test -f \
    /etc/default/lums-agent \
    && echo "Agent configuration present" \
    || echo "Agent configuration missing"
```

Verify variable names:

```bash
sudo awk -F= '
/^(LUMS_BASE|LUMS_TOKEN|LUMS_CA_FILE)=/ {
    print $1 "=<set>"
}' /etc/default/lums-agent
```

Expected:

```text
LUMS_BASE
LUMS_TOKEN
LUMS_CA_FILE
```

Never print the value of:

```text
LUMS_TOKEN
```

---

# 31. Manual Agent Execution

Prefer the systemd service configuration.

Restart:

```bash
sudo systemctl restart \
    lums-agent.service
```

Inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "5 minutes ago" \
    --no-pager
```

Check status:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

A oneshot service may correctly return to:

```text
inactive (dead)
```

after successful execution.

This does not mean the timer is broken.

---

# 32. Agent Timer

Check:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

List schedule:

```bash
systemctl list-timers \
    lums-agent.timer \
    --no-pager
```

Inspect configuration:

```bash
sudo systemctl cat \
    lums-agent.timer
```

The actual installed schedule is authoritative.

Do not assume that documentation and local timer configuration are identical.

---

# 33. Execution Watcher

If the execution watcher is installed, check:

```bash
sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager
```

Then:

```bash
sudo systemctl status \
    lums-execution-watcher.service \
    --no-pager
```

Check logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

The timer and the oneshot service must be checked separately.

---

# 34. Agent 401 vs 403

A useful first distinction is:

```text
401 Unauthorized
    ↓
Authentication problem
```

versus:

```text
403 Forbidden
    ↓
Authorization problem
```

This is not an absolute diagnostic rule for every HTTP implementation, but it is the correct first branch for LUMS troubleshooting.

Always identify the exact endpoint and response before replacing credentials.

---

# 35. Agent Reporting

If a client appears online but does not report correctly:

```text
Agent
   ↓
TLS
   ↓
Authentication
   ↓
Report endpoint
   ↓
Database
   ↓
Frontend
```

Check:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Then:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Inspect clients without exposing tokens:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "SELECT id, hostname, ip, enabled FROM clients;"
```

Do not select token columns for public diagnostics.

---

# 36. Idle Detection

LUMS does not use the old `w -h` based idle detection.

The current implementation uses:

```text
systemd-logind
loginctl
```

The agent checks user sessions and evaluates:

```text
Class
Type
TTY
State
IdleHint
IdleSinceHintMonotonic
```

Relevant user sessions are considered instead of relying on `w`.

This is important because:

```text
w -h
```

can be unreliable for determining whether a local graphical or terminal session is actually idle.

---

# 37. Idle Detection Diagnostics

Check available sessions:

```bash
loginctl list-sessions \
    --no-legend \
    --no-pager
```

Inspect a session:

```bash
loginctl show-session <SESSION_ID>
```

Useful fields include:

```text
Class
Type
TTY
State
IdleHint
IdleSinceHintMonotonic
```

The current agent reports:

```text
idle_source=loginctl
idle_supported=True
```

when systemd-logind is available.

A currently active user session should result in:

```text
idle = false
```

An unsupported or failed idle-detection mechanism must not silently be treated as an active idle state.

---

# 38. Package Manager Detection

The agent automatically detects the installed package manager.

Current abstraction:

```text
detect_package_manager()
        │
        ├── apt      → AptPackageManager
        │
        └── pacman   → PacmanPackageManager
```

Check the repository implementation:

```bash
sed -n '1,120p' \
    /opt/lums-public/agent/package_manager.py
```

Compile-check:

```bash
cd /opt/lums-public

python3 -m py_compile \
    agent/package_manager.py
```

The command should return without an error.

---

# 39. Debian / APT Diagnostics

On Debian-based clients:

```bash
command -v apt
command -v dpkg
```

Expected:

```text
/usr/bin/apt
/usr/bin/dpkg
```

Check package database:

```bash
dpkg --audit
```

Check APT:

```bash
sudo apt-get check
```

List updates:

```bash
apt list --upgradable
```

Only perform repair operations when there is evidence that the package system is actually damaged.

---

# 40. Arch / pacman Diagnostics

On Arch clients:

```bash
command -v pacman
```

Expected:

```text
/usr/bin/pacman
```

Check installed packages:

```bash
pacman -Q
```

Check available updates:

```bash
pacman -Qu
```

Check package state:

```bash
pacman -Q <PACKAGE>
```

Do not use Debian-specific commands on an Arch client.

The agent's package-manager abstraction is specifically intended to prevent such assumptions.

---

# 41. Package Manager Locks

On Debian-based systems, check package-manager locks before attempting repair:

```bash
sudo lsof \
    /var/lib/dpkg/lock-frontend
```

and:

```bash
sudo lsof \
    /var/lib/dpkg/lock
```

Do not blindly delete lock files.

On Arch:

```bash
sudo lsof \
    /var/lib/pacman/db.lck
```

If another package operation is active, determine whether it is legitimate before taking corrective action.

---

# 42. Update Jobs

When a job does not execute, determine where it stopped:

```text
Job created
    ↓
Job queued
    ↓
Agent retrieves job
    ↓
Agent claims job
    ↓
Agent executes job
    ↓
Package Manager
    ↓
Result generated
    ↓
Result uploaded
    ↓
Server stores result
    ↓
Frontend displays result
```

Current job states include:

```text
pending
running
success
partial
failed
abandoned
```

Check server logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Check agent:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Check watcher:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

---

# 43. Supported Update Actions

The current agent update engine supports:

```text
UPDATE_SYSTEM
UPDATE_PACKAGE
INSTALL_PACKAGE
REMOVE_PACKAGE
```

The actual command depends on the detected package manager.

Conceptually:

```text
LUMS action
      │
      ▼
Package manager abstraction
      │
      ├── APT
      │
      └── pacman
```

Do not troubleshoot an Arch failure using only APT commands.

Likewise, do not assume pacman semantics on a Debian client.

---

# 44. System Update Diagnostics

For Debian:

```text
UPDATE_SYSTEM
    ↓
apt-get upgrade -y
```

For Arch:

```text
UPDATE_SYSTEM
    ↓
pacman -Syu --noconfirm
```

The exact command is implemented by the package-manager abstraction.

When a system update fails, inspect the agent logs first.

Then determine whether the failure came from:

```text
LUMS
Agent
Package Manager
Network / repository
Package dependency
Reboot requirement
```

---

# 45. Simulation Mode

If simulation mode is enabled for testing, verify its state before diagnosing a real package-update problem.

Simulation can be useful for:

```text
job lifecycle testing
agent testing
frontend testing
deployment validation
troubleshooting
```

Simulation is not proof that a real package operation succeeds.

After testing, disable temporary simulation settings.

---

# 46. Interrupted Job Recovery

A running job can become interrupted because of:

```text
client shutdown
power loss
network failure
operating system restart
package-manager failure
agent interruption
failed result submission
```

LUMS provides controlled recovery for interrupted jobs.

The recovery process verifies:

```text
1. Job exists
2. Client ownership is correct
3. Job is currently running
4. State transition is valid
5. The job has not already been completed or abandoned
```

The job can then transition to:

```text
abandoned
```

The recovery information includes the relevant job history and recovery reason.

The current recovery reason identifies that:

```text
Agent did not submit a final result.
```

---

# 47. Recovery Failure Behavior

The agent must not silently continue to a new job if recovery of an existing running job fails.

Expected behavior:

```text
Existing running job
        │
        ▼
Attempt recovery
        │
        ├── failure ──► STOP
        │
        ▼
Recovery successful
        │
        ▼
Continue processing
```

This prevents an unresolved running job from being silently ignored.

---

# 48. Job Recovery Diagnostics

If an agent repeatedly finds an existing running job:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Check watcher logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

Inspect jobs:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "SELECT id, client_id, status, started_at, finished_at, recovery_reason FROM update_jobs;"
```

Do not manually modify database state unless controlled database-level recovery is explicitly required.

---

# 49. Reboot Requirement

Some updates require a reboot.

Debian-based systems may expose:

```bash
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot flag present"
```

Some distributions provide additional restart-detection tools.

For example:

```bash
sudo needs-restarting -r
```

may be available depending on the distribution and installed packages.

Do not assume that every successful update requires a reboot.

---

# 50. Database Diagnostics

Check SQLite integrity:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

Expected:

```text
ok
```

List tables:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    ".tables"
```

Check database size:

```bash
sudo docker exec lums \
    ls -lh \
    /var/lib/lums/lums.db
```

Do not publish complete database dumps.

The database contains operational information and authentication-related data.

---

# 51. SQLite-Aware Backup

Use SQLite-aware backups rather than blindly copying a live database file.

Create backup directory:

```bash
sudo mkdir -p \
    /var/backups/lums

sudo chmod 700 \
    /var/backups/lums
```

Create backup:

```bash
sudo docker run --rm \
    --entrypoint python3 \
    -v lums-data:/var/lib/lums:ro \
    -v /var/backups/lums:/backup \
    lums:latest \
    -c '
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

Protect:

```bash
sudo chmod 600 \
    /var/backups/lums/lums.db.backup
```

Verify:

```bash
sqlite3 \
    /var/backups/lums/lums.db.backup \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

Never publish a production database backup.

---

# 52. Database Restore

A database restore is a controlled maintenance operation.

Before restoring:

```text
1. Verify the backup
2. Create a safety copy of the current database
3. Stop LUMS
4. Restore the database
5. Start LUMS
6. Check Gunicorn
7. Check database integrity
8. Check authentication
9. Check clients
10. Check jobs
11. Check HTTPS
```

A complete isolated backup-and-restore validation should be treated as its own test.

---

# 53. Frontend Architecture

The current frontend uses:

```text
HTML
CSS
JavaScript
localStorage
```

Important source files:

```text
style.css
theme.js
network.js
client.js
```

The frontend is deployed as part of the Docker image.

Therefore:

```text
Source change
   ↓
Docker build
   ↓
New image
   ↓
Container recreation
   ↓
Browser
```

Changing a source file does not change an already-running container automatically.

---

# 54. Frontend Source Paths

Source:

```text
/opt/lums-public/server/static/style.css
/opt/lums-public/server/static/theme.js
/opt/lums-public/server/static/network.js
/opt/lums-public/server/static/client.js
```

Runtime:

```text
/app/server/static/style.css
/app/server/static/theme.js
/app/server/static/network.js
/app/server/static/client.js
```

Check:

```bash
sudo docker exec lums \
    ls -lh \
    /app/server/static/style.css \
    /app/server/static/theme.js \
    /app/server/static/network.js \
    /app/server/static/client.js
```

---

# 55. Current Themes

The current theme identifiers are:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

The user-facing name of:

```text
admin
```

is:

```text
Enterprise Admin
```

---

# 56. Browser Theme Selection

Open the browser developer console.

Check:

```javascript
document.documentElement.dataset.theme
```

Expected:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

Check localStorage:

```javascript
localStorage.getItem("lums-theme")
```

Remove the stored theme:

```javascript
localStorage.removeItem("lums-theme")
```

Then reload the page.

The Standard theme should act as the fallback.

---

# 57. Theme JavaScript

Check runtime file:

```bash
sudo docker exec lums \
    test -f /app/server/static/theme.js \
    && echo "theme.js present" \
    || echo "theme.js missing"
```

Check theme identifiers:

```bash
sudo docker exec lums \
    grep -nE \
    'standard|LUMSStadium|golf|nerd|geek|admin' \
    /app/server/static/theme.js
```

If a theme selector contains an incorrect option, verify the runtime JavaScript rather than only the repository source.

---

# 58. Geek / The Living Network

The Geek theme uses:

```text
network.js
```

Check:

```bash
sudo docker exec lums \
    test -f /app/server/static/network.js \
    && echo "network.js present" \
    || echo "network.js missing"
```

Browser:

```javascript
window.LumsNetwork
```

Expected object:

```text
start
stop
destroy
```

Check:

```javascript
document.getElementById("lums-network-canvas")
```

The network effect should only run for:

```text
geek
```

It must not run for:

```text
standard
LUMSStadium
golf
nerd
admin
```

---

# 59. Geek Network Diagnostics

If the Geek background does not appear:

```text
1. Verify theme = geek
2. Verify network.js exists
3. Verify network.js is loaded
4. Verify window.LumsNetwork exists
5. Verify the network canvas exists
6. Check browser console
7. Check reduced-motion settings
8. Hard-refresh browser
```

Check:

```javascript
document.documentElement.dataset.theme
```

Then:

```javascript
window.LumsNetwork
```

If reduced motion is enabled, the visual network effect may intentionally remain disabled.

---

# 60. Nerd Theme Diagnostics

The Nerd theme uses the Matrix/terminal visual system.

Verify:

```javascript
document.documentElement.dataset.theme
```

Expected:

```text
nerd
```

If the effect does not appear:

```text
1. Check theme.js
2. Check browser console
3. Check theme value
4. Hard-refresh browser
5. Check reduced-motion behavior
```

Do not modify unrelated theme CSS without evidence that shared selectors are involved.

---

# 61. Enterprise Admin Diagnostics

The Enterprise Admin theme uses:

```text
admin
```

It is intentionally restrained and information-oriented.

Expected characteristics:

```text
light gray background
white panels
dark blue / gray header
restrained blue accent
thin borders
compact spacing
small radius
minimal shadows
no gradients
no neon glow
no large decorative effects
information-dense tables
simple status indicators
```

Check deployed CSS:

```bash
sudo docker exec lums \
    grep -n -A10 -B4 \
    'LUMS // ENTERPRISE ADMIN' \
    /app/server/static/style.css
```

Enterprise Admin CSS should remain scoped to:

```text
html[data-theme="admin"]
```

---

# 62. Theme Isolation

Changing one theme must not unintentionally modify another theme.

Examples:

```text
Geek
└── The Living Network

Nerd
└── Matrix / terminal visual system

Enterprise Admin
└── restrained operations console
```

If a theme change unexpectedly affects another theme:

```text
Check CSS selectors
   ↓
Check theme.js
   ↓
Check DOM
   ↓
Check shared base styles
```

Do not immediately change backend code.

---

# 63. Client Page / Token Rotation UI

The client page should contain:

```text
🔐 Token rotieren
```

Check runtime template:

```bash
sudo docker exec lums \
    grep -n \
    'rotate-client-token-button' \
    /app/server/templates/client.html
```

Check JavaScript:

```bash
sudo docker exec lums \
    grep -n \
    'rotateClientToken' \
    /app/server/static/client.js
```

The rotation result should only be displayed after a successful authenticated request.

The token must not be inserted into audit logs.

---

# 64. Update UI

The frontend supports the system-maintenance action:

```text
Systemwartung
[System vollständig aktualisieren]
```

The corresponding API job uses:

```text
UPDATE_SYSTEM
```

If the button appears but does nothing:

```text
1. Inspect browser console
2. Check network request
3. Verify POST request
4. Check server logs
5. Check authentication
6. Check job creation
7. Check agent retrieval
```

A frontend button existing in the DOM does not prove that the backend job was created successfully.

---

# 65. Frontend Deployment Sequence

After frontend changes:

```text
1. Edit source
2. Validate source
3. Check Git diff
4. Commit to Git
5. Build Docker image
6. Create SQLite backup
7. Verify backup
8. Recreate hardened container
9. Preserve lums-data
10. Test localhost
11. Test HTTPS
12. Hard-refresh browser
13. Verify frontend
14. Verify client page
15. Verify themes
```

Build:

```bash
cd /opt/lums-public

sudo docker build \
    -t lums:latest \
    .
```

Recreate:

```bash
sudo docker stop lums

sudo docker rm lums

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

Verify:

```bash
sudo docker ps \
    --filter name=lums
```

Then:

```bash
curl -I \
    http://127.0.0.1:5050/
```

---

# 66. Browser Cache

If the source is correct but the browser displays an old version:

```text
1. Hard refresh
2. Open Developer Tools
3. Disable cache temporarily
4. Reload
5. Inspect loaded CSS
6. Inspect loaded JavaScript
7. Check localStorage
8. Check data-theme
```

Firefox:

```text
Ctrl+Shift+R
```

Do not rebuild the application simply because of a browser cache problem.

---

# 67. Git Diagnostics

Check status:

```bash
cd /opt/lums-public

git status -sb
```

Fetch:

```bash
git fetch origin
```

Check remote:

```bash
git remote -v
```

Recent commits:

```bash
git log \
    --oneline \
    --decorate \
    -5
```

Check working-tree changes:

```bash
git diff
```

Check whitespace:

```bash
git diff --check
```

---

# 68. Git Deployment Checks

Before deployment:

```bash
cd /opt/lums-public

git status -sb
git fetch origin
git diff --check
```

If local changes are clean and remote changes should be deployed:

```bash
git pull --ff-only origin main
```

Then:

```bash
git status -sb
```

Never overwrite local changes blindly.

---

# 69. Git Identity

The current LUMS Git identity is:

```text
Name:
NovaForgeCtrl

Email:
xxxxnoreply.github.com
```

Check:

```bash
git config user.name
git config user.email
```

Expected:

```text
NovaForgeCtrl
xxxxxxnoreply.github.com
```

---

# 70. Container Recreation

The following components are separate:

```text
Source:
    /opt/lums-public

Image:
    lums:latest

Container:
    lums

Persistent data:
    lums-data

Flask secret:
    /etc/lums/secrets/lums_secret

TLS:
    /etc/lums/tls/
```

Normal deployment flow:

```text
source
   ↓
image
   ↓
container
```

Persistent data remains:

```text
lums-data
```

Never include this in normal deployment:

```bash
sudo docker volume rm lums-data
```

That command is destructive.

---

# 71. Port Diagnostics

Check relevant ports:

```bash
sudo ss -lntp | \
    grep -E ':(22|80|443|5000|5050)\b'
```

Expected architecture:

```text
22
SSH

80
HTTP / redirect

443
HTTPS / Nginx

5050
LUMS host-side application binding

5000
Gunicorn inside Docker
```

Port `5050` should normally be bound only to:

```text
127.0.0.1
```

Port `5000` should remain internal to the Docker container.

---

# 72. Firewall Diagnostics

Check UFW:

```bash
sudo ufw status verbose
```

If nftables is used:

```bash
sudo nft list ruleset
```

Do not change firewall rules while diagnosing an application problem unless there is evidence that the firewall is involved.

---

# 73. Permission Diagnostics

Source:

```bash
ls -la \
    /opt/lums-public
```

TLS:

```bash
sudo ls -la \
    /etc/lums/tls/
```

Secret:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/secrets/lums_secret
```

Agent:

```bash
sudo ls -la \
    /opt/lums-agent/
```

Do not use:

```bash
chmod 777
```

as a generic troubleshooting solution.

Determine which process requires access and correct that specific permission.

---

# 74. Diagnostic Log Reference

## Docker

```bash
sudo docker logs \
    --tail 200 \
    lums
```

## Nginx

```bash
sudo tail \
    -n 100 \
    /var/log/nginx/error.log
```

## Agent

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

## Execution Watcher

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

## Nginx Service

```bash
sudo journalctl \
    -u nginx \
    --since "30 minutes ago" \
    --no-pager
```

---

# 75. Server Diagnostic Sequence

Run the following sequence when the server appears broken:

```bash
echo "=== Docker ==="
sudo docker ps --filter name=lums

echo
echo "=== Docker Image ==="
sudo docker inspect \
    -f '{{.Config.Image}}' \
    lums

echo
echo "=== Docker Hardening ==="
sudo docker inspect lums \
    --format \
    'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{json .HostConfig.CapDrop}} Privileged={{.HostConfig.Privileged}}'

echo
echo "=== Docker Logs ==="
sudo docker logs \
    --tail 50 \
    lums

echo
echo "=== Port 5050 ==="
sudo ss -lntp | \
    grep ':5050' || true

echo
echo "=== Flask / Gunicorn ==="
curl -I \
    http://127.0.0.1:5050/ \
    || true

echo
echo "=== Nginx ==="
sudo nginx -t

echo
echo "=== Nginx Status ==="
sudo systemctl is-active nginx

echo
echo "=== Secret Configuration ==="
sudo docker exec lums sh -c '
echo "LUMS_SECRET_KEY_FILE=${LUMS_SECRET_KEY_FILE}"

if [ -n "${LUMS_SECRET_KEY:-}" ]; then
    echo "LUMS_SECRET_KEY=PRESENT"
else
    echo "LUMS_SECRET_KEY=ABSENT"
fi

if [ -r /run/secrets/lums_secret ]; then
    echo "SECRET_FILE=READABLE"
else
    echo "SECRET_FILE=NOT_READABLE"
fi
'

echo
echo "=== LUMS Database ==="
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

This sequence deliberately does not expose the actual Flask secret.

---

# 76. Client Diagnostic Sequence

On the client:

```bash
echo "=== Agent Service ==="
sudo systemctl is-active lums-agent.service

echo
echo "=== Agent Timer ==="
sudo systemctl is-active lums-agent.timer

echo
echo "=== Watcher Timer ==="
sudo systemctl is-active lums-execution-watcher.timer

echo
echo "=== Agent Configuration ==="
sudo awk -F= '
/^(LUMS_BASE|LUMS_TOKEN|LUMS_CA_FILE)=/ {
    print $1 "=<set>"
}' /etc/default/lums-agent

echo
echo "=== CA File ==="
test -f /opt/lums-agent/lums-ca.crt \
    && echo "present" \
    || echo "missing"

echo
echo "=== Agent Logs ==="
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager

echo
echo "=== Watcher Logs ==="
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

The token value is never displayed.

---

# 77. Public Bug Reports

Before publishing diagnostics, remove:

```text
passwords
tokens
API keys
private keys
cookies
session identifiers
internal hostnames
internal IP addresses
personal usernames
personal email addresses
database dumps
```

Replace sensitive values with:

```text
<LUMS_SERVER_IP>
<CLIENT_ID>
<JOB_ID>
<CLIENT_TOKEN>
<PACKAGE>
<USERNAME>
```

Do not publish:

```bash
cat /etc/lums/docker/lums.env
```

or:

```bash
cat /etc/default/lums-agent
```

Use presence-only diagnostics.

---

# 78. Common HTTP Errors

## 301

Usually:

```text
HTTP → HTTPS redirect
```

Check Nginx redirect configuration.

---

## 302

Usually:

```text
Unauthenticated browser request
        ↓
/login
```

This can be normal.

---

## 401

Usually:

```text
Authentication failed
```

Check:

```text
session
credentials
client token
Authorization header
token validity
```

---

## 403

Usually:

```text
Authorization denied
```

Check:

```text
authenticated identity
permissions
CSRF validation
endpoint authorization
```

---

## 404

Check:

```text
URL
route
HTTP method
frontend request
Nginx configuration
```

A 404 does not automatically mean that Flask is unavailable.

---

## 500

Check:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Look for the corresponding request and traceback.

---

## 502

Check:

```text
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker
   ↓
Gunicorn
```

---

# 79. Common Deployment Mistakes

## Image rebuilt but container not recreated

Symptom:

```text
Source contains new code.
Browser still shows old behavior.
```

Check:

```bash
sudo docker inspect \
    -f '{{.Image}}' \
    lums
```

Then compare against:

```bash
sudo docker image inspect \
    lums:latest \
    -f '{{.Id}}'
```

---

## Container recreated without persistent volume

Symptom:

```text
Database appears empty.
```

Check:

```bash
sudo docker inspect lums \
    --format \
    '{{range .Mounts}}{{println .Name .Destination}}{{end}}'
```

Expected:

```text
lums-data /var/lib/lums
```

---

## Secret configuration lost

Symptom:

```text
Application starts but sessions/authentication behave unexpectedly.
```

Check:

```bash
sudo docker exec lums sh -c '
echo "FILE=${LUMS_SECRET_KEY_FILE}"
test -r /run/secrets/lums_secret \
    && echo "SECRET_FILE=READABLE" \
    || echo "SECRET_FILE=NOT_READABLE"
'
```

---

## Hardened runtime lost

Symptom:

```text
Application works, but deployment security changed.
```

Check:

```bash
sudo docker inspect lums \
    --format \
    'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{json .HostConfig.CapDrop}} Privileged={{.HostConfig.Privileged}}'
```

---

# 80. Known Installation Lessons

## Lesson 1 — Find the failing layer

Do not reinstall the complete system before identifying the failing component.

---

## Lesson 2 — Container and volume are different

The container is replaceable.

The persistent volume contains application data.

```text
Container:
replaceable

Volume:
persistent
```

---

## Lesson 3 — Image and running container are different

Building:

```bash
docker build
```

does not automatically update an existing container.

After rebuilding, verify the image actually used by the running container.

---

## Lesson 4 — Authentication and authorization are different

```text
401
```

normally indicates an authentication problem.

```text
403
```

normally indicates an authorization problem.

Always identify the exact endpoint before changing credentials.

---

## Lesson 5 — Token digest and password hash are different concepts

LUMS stores client authentication tokens as SHA-256 hexadecimal digests.

Administrative passwords use the application's password hashing mechanism.

These are different security mechanisms serving different purposes.

---

## Lesson 6 — Do not expose secrets while troubleshooting

A local diagnostic command is not automatically safe.

Logs may later be copied into:

```text
GitHub issues
documentation
screenshots
chat messages
support requests
```

Therefore diagnostic output should be safe by default.

---

## Lesson 7 — Frontend changes require the complete deployment chain

A changed:

```text
style.css
theme.js
network.js
client.js
index.html
client.html
```

does not automatically mean the running application contains the change.

The chain is:

```text
Git source
   ↓
Docker build
   ↓
Docker image
   ↓
Container recreation
   ↓
Browser
```

---

## Lesson 8 — Theme bugs are not automatically application bugs

If the API works but a theme is visually incorrect:

```text
Backend may be healthy.
```

Investigate:

```text
CSS
JavaScript
DOM
localStorage
browser cache
reduced-motion settings
```

before changing Flask.

---

## Lesson 9 — Preserve container hardening

A deployment is incomplete if the application works but the hardened runtime configuration has been lost.

Always verify:

```text
Non-root
Read-only root filesystem
ALL capabilities dropped
Privileged=false
Protected secret mount
Localhost-only application binding
```

---

## Lesson 10 — Token rotation is a complete lifecycle

A token rotation is not complete merely because the API returned a new token.

The complete workflow is:

```text
Rotate
   ↓
Receive replacement
   ↓
Previous token invalid
   ↓
Securely transfer replacement
   ↓
Update agent
   ↓
Authenticate
   ↓
Report
   ↓
Verify client online
```

---

## Lesson 11 — Package manager is platform-specific

LUMS currently supports:

```text
APT / dpkg
pacman
```

Therefore:

```text
Debian
   ↓
APT / dpkg

Arch
   ↓
pacman
```

Do not diagnose all Linux clients as though they were Debian systems.

---

## Lesson 12 — Idle detection is session-aware

LUMS uses:

```text
systemd-logind
loginctl
```

rather than relying on:

```text
w -h
```

The session-aware implementation is important for correctly identifying active user sessions.

---

# 81. Current Security-Relevant Troubleshooting Checks

The following checks should be performed after security-sensitive deployment changes.

## Container

```text
[ ] Non-root user
[ ] UID 10001
[ ] Read-only root filesystem
[ ] ALL capabilities dropped
[ ] Privileged=false
[ ] /tmp is tmpfs
```

## Secret

```text
[ ] Secret is file-based
[ ] Secret mount is read-only
[ ] LUMS_SECRET_KEY is absent
[ ] LUMS_SECRET_KEY_FILE is configured
[ ] Secret is not logged
```

## Network

```text
[ ] Application binds to 127.0.0.1:5050
[ ] Container port 5000 is not unnecessarily exposed
[ ] HTTPS terminates at Nginx
[ ] HTTP redirects to HTTPS
```

## Authentication

```text
[ ] Administrator authentication works
[ ] Client authentication works
[ ] Token rotation works
[ ] Previous token is invalidated
[ ] Rotation is audited
```

## Database

```text
[ ] SQLite integrity check passes
[ ] Persistent volume is mounted
[ ] Backup is created
[ ] Backup integrity is verified
```

---

# 82. Final Checklist

## Server

```text
[ ] Docker container running
[ ] Correct image deployed
[ ] Gunicorn running
[ ] lums-data mounted
[ ] Flask reachable on 127.0.0.1:5050
[ ] Nginx running
[ ] nginx -t successful
[ ] HTTP redirects to HTTPS
[ ] HTTPS reachable
[ ] TLS certificate valid
[ ] TLS 1.2 / 1.3 active
[ ] Security headers present
[ ] SQLite integrity check successful
```

## Container Security

```text
[ ] User=lums
[ ] UID 10001
[ ] ReadonlyRootfs=true
[ ] CapDrop=ALL
[ ] Privileged=false
[ ] /tmp is tmpfs
[ ] Persistent volume mounted
```

## Secrets

```text
[ ] LUMS_SECRET_KEY absent
[ ] LUMS_SECRET_KEY_FILE configured
[ ] Secret file readable by container
[ ] Secret file mounted read-only
[ ] Secret directory protected
[ ] No secrets in logs
[ ] No secrets in documentation
```

## Authentication

```text
[ ] Client exists
[ ] Client enabled
[ ] Token configured
[ ] Token value not exposed
[ ] Authentication works
[ ] Authorization is checked separately
[ ] Token rotation works
[ ] Old token becomes invalid
[ ] New token authenticates
[ ] Rotation is audited
```

## Agent

```text
[ ] lums-agent.service works
[ ] lums-agent.timer active
[ ] Execution watcher checked
[ ] CA file exists
[ ] LUMS_BASE configured
[ ] LUMS_TOKEN configured
[ ] LUMS_CA_FILE configured
[ ] Agent can reach LUMS
[ ] Agent authenticates
[ ] Agent reports successfully
[ ] Agent version verified
[ ] Package manager detected
```

## Debian / APT

```text
[ ] apt available
[ ] dpkg available
[ ] Package database healthy
[ ] apt-get check succeeds
[ ] Updates can be detected
[ ] Package operations complete
```

## Arch / pacman

```text
[ ] pacman available
[ ] Package database healthy
[ ] pacman -Qu works
[ ] Updates can be detected
[ ] Package operations complete
```

## Jobs

```text
[ ] Job created
[ ] Job queued
[ ] Agent retrieves job
[ ] Job ownership verified
[ ] Agent claims job
[ ] Agent executes job
[ ] Package manager succeeds
[ ] Result generated
[ ] Result reported
[ ] Server stores result
[ ] Frontend displays result
```

## Recovery

```text
[ ] Interrupted jobs can be identified
[ ] Running job ownership verified
[ ] Recovery available
[ ] Abandon operation audited
[ ] Recovery history recorded
[ ] Agent stops if recovery fails
[ ] Agent continues after successful recovery
```

## Frontend

```text
[ ] style.css present
[ ] theme.js present
[ ] network.js present
[ ] client.js present
[ ] index.html loads assets
[ ] client.html loads assets
[ ] localStorage theme is correct
[ ] Standard works
[ ] LUMSStadium works
[ ] Golf works
[ ] Nerd works
[ ] Geek works
[ ] Enterprise Admin works
[ ] Token rotation button visible
[ ] System maintenance button works
```

## Geek

```text
[ ] theme = geek
[ ] network.js loaded
[ ] window.LumsNetwork exists
[ ] network canvas exists
[ ] reduced-motion setting checked
[ ] Network effect disabled for other themes
```

## Enterprise Admin

```text
[ ] theme = admin
[ ] Enterprise Admin CSS loaded
[ ] admin CSS remains scoped
[ ] no unintended theme changes
[ ] no unnecessary visual effects
```

## Backup

```text
[ ] SQLite-aware backup created
[ ] Backup permissions restricted
[ ] Backup integrity verified
[ ] Full isolated restore test tracked
```

---

# 83. Server Recovery Decision Tree

When LUMS appears completely unavailable:

```text
                    LUMS unavailable
                           │
                           ▼
                Is Docker running?
                     /          \
                   NO            YES
                   │              │
                   ▼              ▼
             Docker issue    Is port 5050 open?
                              /          \
                            NO            YES
                            │              │
                            ▼              ▼
                    Container /       Does curl work?
                    Gunicorn /          /       \
                    Flask              NO        YES
                                       │          │
                                       ▼          ▼
                                App/container   Nginx /
                                investigation   TLS issue
```

If:

```bash
curl -I http://127.0.0.1:5050/
```

works, the application stack is at least reachable locally.

Continue with:

```text
HTTPS
   ↓
Nginx
   ↓
Certificate
   ↓
Headers
   ↓
Browser
```

---

# 84. Client Recovery Decision Tree

When a client appears offline:

```text
                    Client offline
                          │
                          ▼
                  Is agent service OK?
                     /          \
                   NO            YES
                   │              │
                   ▼              ▼
              systemd issue   Is timer active?
                                /       \
                              NO         YES
                              │           │
                              ▼           ▼
                         timer issue   Can HTTPS
                                      reach LUMS?
                                      /       \
                                    NO         YES
                                    │           │
                                    ▼           ▼
                                Network /   Authentication
                                TLS issue    / reporting
```

Then verify:

```text
Agent
   ↓
CA
   ↓
Token
   ↓
Report
   ↓
Database
   ↓
Frontend
```

---

# 85. Job Recovery Decision Tree

When a job remains:

```text
running
```

longer than expected:

```text
                 Job still running
                         │
                         ▼
                Is the client online?
                    /          \
                  NO            YES
                  │              │
                  ▼              ▼
             Check recovery   Check agent
                              logs
                                │
                                ▼
                         Did agent submit
                         a final result?
                           /          \
                         YES           NO
                         │              │
                         ▼              ▼
                   Check result     Recovery
                   processing       required
```

Do not immediately delete the job.

First determine whether:

```text
execution
result submission
server processing
recovery
```

is the actual failing layer.

---

# 86. Frontend Recovery Decision Tree

When the frontend looks wrong:

```text
              Frontend problem
                     │
                     ▼
             Does API work?
                /       \
              NO         YES
              │           │
              ▼           ▼
         Backend      Is correct
         debugging    HTML loaded?
                          │
                          ▼
                     Is CSS loaded?
                          │
                          ▼
                    Is JS loaded?
                          │
                          ▼
                    Check theme
                          │
                          ▼
                    Check DOM
                          │
                          ▼
                  Check localStorage
                          │
                          ▼
                    Hard refresh
```

This prevents backend changes from being made for a browser-side problem.

---

# 87. Documentation Rule

When troubleshooting produces a verified result, document:

```text
Problem
    ↓
Observed behavior
    ↓
Affected layer
    ↓
Root cause
    ↓
Change
    ↓
Verification
```

Avoid documenting only:

```text
"Fixed."
```

A useful troubleshooting record should allow another administrator to understand why the change was made.

---

# 88. Final Principles

LUMS troubleshooting should follow:

```text
Observe
   ↓
Identify the layer
   ↓
Verify the assumption
   ↓
Change only what is necessary
   ↓
Test again
   ↓
Document the result
```

The most important rule remains:

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

A healthy LUMS installation is not defined by the absence of errors during installation.

It is defined by being able to determine:

```text
where a problem occurs,
why it occurs,
what component is responsible,
what changed,
and how the fix can be verified.
```

That is the purpose of this troubleshooting guide.

---

# 89. Current Architecture Summary

```text
                         ┌───────────────────┐
                         │      Browser      │
                         └─────────┬─────────┘
                                   │
                                HTTPS
                                   │
                         ┌─────────▼─────────┐
                         │       Nginx       │
                         └─────────┬─────────┘
                                   │
                         127.0.0.1:5050
                                   │
                         ┌─────────▼─────────┐
                         │ Docker: lums      │
                         │                   │
                         │ Gunicorn :5000    │
                         │       ↓           │
                         │ Flask             │
                         │       ↓           │
                         │ /app/server/      │
                         │   static/         │
                         └─────────┬─────────┘
                                   │
                         ┌─────────▼─────────┐
                         │    lums-data      │
                         │                   │
                         │ lums.db           │
                         └───────────────────┘
```

Frontend:

```text
/opt/lums-public/server/static/
             │
             ├── style.css
             ├── theme.js
             ├── network.js
             └── client.js
             │
             ▼
/app/server/static/
```

Themes:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

Special behavior:

```text
nerd
└── Matrix / terminal visual system

geek
└── The Living Network
    └── network.js

admin
└── Enterprise Admin
    └── restrained infrastructure console
```

Persistent data:

```text
lums-data
└── /var/lib/lums/lums.db
```

Secrets:

```text
/etc/lums/secrets/lums_secret
        │
        └── read-only
              ↓
        /run/secrets/lums_secret
```

Agent:

```text
/opt/lums-agent/
├── agent.py
├── watcher.py
└── lums-ca.crt
```

Package manager abstraction:

```text
                    package_manager.py
                           │
                    ┌──────┴──────┐
                    │             │
                   APT          pacman
                    │             │
                 Debian         Arch
```

The architecture deliberately separates:

```text
source
image
container
persistent data
secrets
agent
package manager
frontend
```

This separation makes LUMS easier to troubleshoot, update, rebuild and recover without unnecessarily destroying working components.

---

# 90. Final Rule

```text
ONE LUMS
ONE BACKEND
ONE DATABASE
MANY LAYERS
CLEAR BOUNDARIES
CONTROLLED CHANGES
VERIFIED RESULTS
```

> **Find the layer. Fix the layer. Verify the layer.**
