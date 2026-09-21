# LUMS Troubleshooting Guide

## Linux Update Management Server

This document provides a structured troubleshooting procedure for LUMS.

The most important rule is:

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

LUMS consists of several independent layers. A failure in one layer does not automatically mean that the complete installation is broken.

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
APT / dpkg
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
network.js
   ↓
Selected Theme
   ↓
Browser Cache / localStorage
```

Do not skip layers unless there is already clear evidence that the lower layers are working.

---

# 2. Current Architecture

Current LUMS deployment:

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

The persistent database is stored in:

```text
lums-data
```

The application source repository is:

```text
/opt/lums-public
```

The running application is inside:

```text
/app
```

The frontend files inside the container are located under:

```text
/app/server/static/
```

The corresponding source files are located under:

```text
/opt/lums-public/server/static/
```

---

# 3. Current Container Security State

The production LUMS container currently runs with:

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

Flask secret:
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

Do not use an older insecure recreation command from previous documentation.

---

# 4. Troubleshooting Order

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
11. Agent authentication
12. Agent reporting
13. Job creation
14. Job recovery
15. Job execution
16. APT / dpkg
17. Job result
18. Frontend
19. Theme system
20. Browser cache
```

If a lower layer is broken, do not spend time debugging a higher layer yet.

Example:

If:

```bash
curl -I http://127.0.0.1:5050
```

already fails, debugging browser JavaScript is premature.

---

# 5. Important Paths

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

## Runtime Frontend Files

Inside the container:

```text
/app/server/static/
```

## Persistent Database

Inside the container:

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

The Flask secret is no longer stored as a normal environment variable.

## Flask Secret

```text
/etc/lums/secrets/lums_secret
```

Inside the container:

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

# 6. Docker Diagnostics

Check whether the container exists:

```bash
sudo docker ps -a --filter name=lums
```

Expected:

```text
lums
```

Check the running container:

```bash
sudo docker ps --filter name=lums
```

Check the container status:

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

Follow live logs:

```bash
sudo docker logs -f lums
```

Stop following logs with:

```text
Ctrl+C
```

---

# 7. Docker Image

Check available LUMS images:

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

After source changes, rebuild the image:

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

A successful build does not automatically mean that the running container uses the new image.

The container must be recreated if application files changed.

---

# 8. Gunicorn Diagnostics

The production application server is:

```text
Gunicorn 23.0.0
```

The current configuration uses:

```text
2 workers
2 threads
120 second timeout
```

The Flask development server is not used in production.

Check the container logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Expected startup pattern:

```text
=== LUMS database initialization ===
=== Starting Gunicorn ===
Starting gunicorn 23.0.0
Listening at: http://0.0.0.0:5000
Using worker: gthread
Booting worker
Booting worker
```

If Gunicorn does not start, investigate the container logs before changing Nginx.

---

# 9. Docker Port Diagnostics

Current architecture:

```text
Host:
127.0.0.1:5050

Container:
5000
```

Check the port:

```bash
sudo ss -lntp | grep ':5050'
```

Expected pattern:

```text
127.0.0.1:5050
```

Test the application directly:

```bash
curl -I \
    http://127.0.0.1:5050/
```

Expected behavior:

```text
HTTP/1.1 302 FOUND
Location: /login
```

If this works but HTTPS does not, investigate Nginx/TLS.

If this fails, investigate Docker/Gunicorn/Flask before Nginx.

---

# 10. Docker Volume Diagnostics

Check the persistent volume:

```bash
sudo docker volume inspect \
    lums-data
```

Check that the volume is attached:

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

# 11. Container Hardening Diagnostics

Verify the current security state:

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

If any of these values unexpectedly differ after a deployment, stop and investigate before treating the deployment as complete.

---

# 12. Secret Diagnostics

The production Flask secret is loaded from:

```text
/run/secrets/lums_secret
```

The host source is:

```text
/etc/lums/secrets/lums_secret
```

Verify configuration without displaying the secret:

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

Never print:

```bash
cat /etc/lums/secrets/lums_secret
```

and never include the secret in diagnostic output.

---

# 13. Secret File Permissions

Check:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/secrets/lums_secret
```

The expected file ownership is:

```text
root:10001
```

with mode:

```text
640
```

The containing directory should be restricted to root:

```text
/etc/lums/secrets
```

with mode:

```text
700
```

If the secret file cannot be read by the container, verify permissions before changing application code.

---

# 14. Environment Diagnostics

The environment file is:

```text
/etc/lums/docker/lums.env
```

Do not print the complete file.

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
env | grep -E "^(LUMS_|FLASK_|PYTHON)" |
sed "s/=.*$/=<set>/"
'
```

The production Flask secret should not appear as:

```text
LUMS_SECRET_KEY=<value>
```

The expected configuration is:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

---

# 15. Flask Diagnostics

Check container logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Look for:

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

Check the application directory:

```bash
sudo docker exec lums \
    ls -la /app
```

Check the server directory:

```bash
sudo docker exec lums \
    ls -la /app/server
```

---

# 16. Nginx Diagnostics

Check Nginx configuration:

```bash
sudo nginx -t
```

Expected:

```text
syntax is ok
test is successful
```

Check Nginx status:

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

Check recent logs:

```bash
sudo journalctl \
    -u nginx \
    --since "30 minutes ago" \
    --no-pager
```

Check access log:

```bash
sudo tail \
    -n 100 \
    /var/log/nginx/access.log
```

Check error log:

```bash
sudo tail \
    -n 100 \
    /var/log/nginx/error.log
```

---

# 17. Nginx 502 Bad Gateway

A `502 Bad Gateway` normally means Nginx cannot successfully reach the upstream application.

Check the application directly:

```bash
curl -I \
    http://127.0.0.1:5050/
```

If this fails:

```text
Browser
  ↓
Nginx
  ↓
X
Docker / Gunicorn / Flask
```

the problem is below Nginx.

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
sudo ss -lntp | grep ':5050'
```

---

# 18. HTTPS / TLS

Check configured certificate files:

```bash
sudo ls -l \
    /etc/lums/tls/
```

Check the certificate:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

Do not publish private key contents.

Never use:

```bash
sudo cat \
    /etc/lums/tls/lums.key
```

for public diagnostics.

---

# 19. TLS Certificate Diagnostics

Test the HTTPS endpoint:

```bash
curl -kI \
    https://<LUMS_SERVER_IP>/
```

For certificate inspection:

```bash
openssl s_client \
    -connect <LUMS_SERVER_IP>:443 \
    -servername <LUMS_SERVER_IP> \
    </dev/null
```

The current production configuration supports:

```text
TLS 1.2
TLS 1.3
```

Older TLS versions must remain disabled.

Check:

```bash
sudo nginx -T | \
    grep -n 'ssl_protocols'
```

Expected:

```text
ssl_protocols TLSv1.2 TLSv1.3;
```

---

# 20. HTTP Redirect

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

If HTTP serves the application directly instead of redirecting, investigate the Nginx configuration.

---

# 21. Security Headers

Test:

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

and:

```text
Permissions-Policy:
camera=(),
microphone=(),
geolocation=(),
payment=()
```

The Content Security Policy should include:

```text
default-src 'self';
script-src 'self';
style-src 'self';
img-src 'self' data:;
font-src 'self';
connect-src 'self';
object-src 'none';
base-uri 'self';
frame-ancestors 'none';
form-action 'self'
```

If security headers disappear after a deployment, investigate Nginx and response handling before modifying application authentication.

---

# 22. Agent TLS Problems

The agent uses:

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

Check certificate metadata:

```bash
sudo openssl x509 \
    -in /opt/lums-agent/lums-ca.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

Never publish private client credentials.

---

# 23. Agent Connectivity

Check the agent service:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Check recent logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Check connectivity:

```bash
curl -kI \
    https://<LUMS_SERVER_IP>/
```

If the agent cannot connect:

```text
Agent
  ↓
Network / DNS
  ↓
TLS
  ↓
Nginx
  ↓
LUMS
```

Check each layer separately.

---

# 24. Agent Authentication

LUMS currently stores the client token as a SHA-256 hexadecimal digest.

This is an authentication-token representation.

It must not be confused with the password hashing mechanism used for administrative passwords.

The agent sends:

```text
Authorization: Bearer <CLIENT_TOKEN>
```

If authentication fails with:

```text
401 Unauthorized
```

check:

```text
1. Client exists
2. Client is enabled
3. Token is present in the agent configuration
4. Token corresponds to the registered client
5. Token has not been revoked
6. Server receives the Authorization header
7. Client authentication succeeds
```

Do not display the token or stored token digest.

---

# 25. Client Token Rotation

LUMS supports authenticated client-token rotation.

The frontend provides:

```text
🔐 Token rotieren
```

The endpoint is:

```text
POST /api/clients/<client_id>/token/rotate
```

The operation requires:

```text
Authenticated administrator session
+
CSRF validation
```

After successful rotation:

```text
Old token
    ↓
401 Unauthorized

New token
    ↓
Authenticated
```

The new token is shown only once by the frontend.

It must then be securely transferred to the affected agent.

---

# 26. Token Rotation Troubleshooting

If a client stops authenticating immediately after token rotation:

```text
1. Verify the correct client was rotated.
2. Obtain the newly generated token.
3. Update /etc/default/lums-agent.
4. Restart the agent.
5. Check agent logs.
6. Check LUMS container logs.
7. Verify the client reports again.
```

Do not rotate the token repeatedly while troubleshooting.

Repeated rotations make it harder to determine which token is currently valid.

The rotation event is recorded in the audit log.

The plaintext token must never appear in the audit log.

---

# 27. Agent Environment

Check that the configuration exists:

```bash
sudo test -f \
    /etc/default/lums-agent \
    && echo "Agent configuration present" \
    || echo "Agent configuration missing"
```

Check variable names without values:

```bash
sudo awk -F= '
/^(LUMS_BASE|LUMS_TOKEN|LUMS_CA_FILE)=/ {
    print $1 "=<set>"
}' /etc/default/lums-agent
```

Expected variable names:

```text
LUMS_BASE
LUMS_TOKEN
LUMS_CA_FILE
```

Never print:

```text
LUMS_TOKEN
```

with its actual value.

---

# 28. Manual Agent Execution

Use the installed service configuration rather than manually exposing credentials.

Restart the service:

```bash
sudo systemctl restart \
    lums-agent.service
```

Then inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "5 minutes ago" \
    --no-pager
```

Check:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

---

# 29. Agent Returns 403

A `403 Forbidden` means authentication may have succeeded but authorization rejected the request.

Investigate:

```text
Authentication
        ↓
Authorization
        ↓
Endpoint permissions
```

Check the server logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Check the agent logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Do not immediately replace the token.

First determine which endpoint returned `403`.

---

# 30. Agent Reporting

If the client appears online but does not report correctly:

```text
Agent service
    ↓
HTTPS
    ↓
Authentication
    ↓
Report endpoint
    ↓
Database
    ↓
Frontend
```

Check recent agent logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Check server logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Check the client list:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "SELECT id, hostname, ip, enabled FROM clients;"
```

Do not query or print token columns in public diagnostics.

---

# 31. Agent Timers

List relevant timers:

```bash
systemctl list-timers --all | \
    grep -E 'lums|update'
```

Inspect:

```bash
sudo systemctl cat \
    lums-agent.timer
```

and:

```bash
sudo systemctl cat \
    lums-execution-watcher.timer
```

The actual schedule must always be taken from the installed timer configuration.

Check:

```bash
systemctl list-timers \
    lums-agent.timer \
    --no-pager
```

Check timer state:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

A oneshot service can show:

```text
inactive (dead)
```

after completing successfully.

That does not automatically mean the timer is broken.

---

# 32. Execution Watcher

Check:

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

The timer should be checked separately from the oneshot service.

---

# 33. Simulation Mode

If simulation mode is enabled for testing, verify its state before diagnosing a real update problem.

Simulation mode is useful for:

* job lifecycle testing
* agent testing
* frontend testing
* deployment validation
* troubleshooting

Simulation is not proof that a real package update succeeds.

After testing, disable temporary simulation settings.

---

# 34. Update Jobs

When a job does not execute, determine where it stopped.

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
APT / dpkg
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

Check the server logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Check agent logs:

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

---

# 35. Interrupted Job Recovery

A running job can become interrupted because of:

* client shutdown
* power loss
* network failure
* operating system restart
* package manager failure
* failed result submission
* agent interruption

LUMS provides:

```text
POST /api/update-jobs/<job_id>/abandon
```

The server verifies:

```text
1. Job exists
2. Authenticated client owns the job
3. Job is currently running
4. State transition has not already happened
```

The job is then changed to:

```text
abandoned
```

The recovery process records:

```text
finished_at
recovery_reason
update_history
package statistics
reboot state
```

The current recovery reason is:

```text
Agent did not submit a final result.
```

---

# 36. Recovery Failure Behavior

The agent must not silently continue to a new job if recovery of an existing running job fails.

Expected behavior:

```text
Existing running job
        |
        v
Attempt recovery
        |
        +---- failure ---> STOP
        |
        v
Recovery successful
        |
        v
Continue to pending jobs
```

This prevents an unresolved job from being silently ignored.

---

# 37. Job Recovery Diagnostics

If an agent repeatedly finds an existing running job:

Check:

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

Inspect the job through the LUMS interface.

If necessary, inspect the database:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "SELECT id, client_id, status, started_at, finished_at, recovery_reason FROM update_jobs;"
```

Do not manually change the status unless controlled recovery requires database-level intervention.

---

# 38. APT / dpkg Problems

On the client, check package state:

```bash
dpkg --audit
```

Check APT:

```bash
apt-get check
```

Only run repair commands when the package manager is actually in a broken state.

If package configuration is incomplete:

```bash
sudo dpkg --configure -a
```

Do not blindly delete APT lock files.

First determine which process owns the lock:

```bash
sudo lsof \
    /var/lib/dpkg/lock-frontend

sudo lsof \
    /var/lib/dpkg/lock
```

If another package operation is active, allow it to finish whenever possible.

---

# 39. Reboot Requirement

Some package updates require a reboot.

Check:

```bash
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot flag present"
```

Check package-specific restart information if available:

```bash
sudo needs-restarting -r
```

The availability of `needs-restarting` depends on the installed distribution and packages.

Do not assume that every successful package installation requires a reboot.

---

# 40. Database Diagnostics

Check the database:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

Expected:

```text
ok
```

Check database tables:

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

Do not dump the complete database into public bug reports.

The database contains operational and authentication-related data.

---

# 41. SQLite-Aware Database Backup

Use SQLite-aware backups.

Create a backup directory:

```bash
sudo mkdir -p \
    /var/backups/lums

sudo chmod 700 \
    /var/backups/lums
```

Create a backup:

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

# 42. Database Restore Warning

A database restore is a controlled maintenance operation.

Do not overwrite the production database immediately.

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

A full isolated backup/restore test remains a separate validation task.

---

# 43. Frontend / Theme Diagnostics

LUMS currently contains:

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

# 44. Frontend Source Paths

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

# 45. Browser Theme Selection

Open the browser developer console.

Check:

```javascript
document.documentElement.dataset.theme
```

Expected values:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

Check stored theme:

```javascript
localStorage.getItem("lums-theme")
```

To remove the stored theme:

```javascript
localStorage.removeItem("lums-theme")
```

Reload the page.

The Standard theme should act as the fallback.

---

# 46. Theme JavaScript

Check:

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

If a theme selector shows an incorrect option, verify the runtime JavaScript rather than only the Git source.

---

# 47. Geek / The Living Network

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

The network effect should only run when:

```text
theme = geek
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

# 48. Geek Network Diagnostics

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

If reduced motion is enabled, the network effect may intentionally remain disabled.

---

# 49. Nerd Theme Diagnostics

The Nerd theme uses the Matrix/terminal visual system.

Verify:

```javascript
document.documentElement.dataset.theme
```

Expected:

```text
nerd
```

If the Nerd effect does not appear:

```text
1. Check theme.js
2. Check browser console
3. Check theme value
4. Hard-refresh browser
5. Check reduced-motion behavior
```

Do not modify Geek or Enterprise Admin CSS while troubleshooting Nerd unless there is evidence that shared base styles are involved.

---

# 50. Enterprise Admin Diagnostics

The Enterprise Admin theme uses:

```text
admin
```

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
no large rounded cards
no large decorative icons
no unnecessary animations
information-dense tables
simple status indicators
```

Check the deployed CSS:

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

# 51. Theme Isolation

Theme changes should not unintentionally modify unrelated themes.

Examples:

```text
Geek
└── The Living Network

Nerd
└── Matrix / terminal visual system

Enterprise Admin
└── restrained operations console
```

If changing Enterprise Admin unexpectedly changes another theme, inspect CSS selectors before changing JavaScript.

---

# 52. Client Page / Token Rotation UI

The client page should contain:

```text
🔐 Token rotieren
```

Check the runtime template:

```bash
sudo docker exec lums \
    grep -n \
    'rotate-client-token-button' \
    /app/server/templates/client.html
```

Check the JavaScript:

```bash
sudo docker exec lums \
    grep -n \
    'rotateClientToken' \
    /app/server/static/client.js
```

The rotation result should display the new token only after a successful authenticated request.

The token must not be inserted into audit logs.

---

# 53. Frontend Deployment Sequence

After frontend changes:

```text
1. Edit source
2. Check source
3. Commit to Git
4. Build Docker image
5. Create SQLite backup
6. Verify backup
7. Recreate hardened container
8. Preserve lums-data
9. Test localhost
10. Test HTTPS
11. Hard-refresh browser
12. Verify theme behavior
13. Verify client page
```

Build:

```bash
cd /opt/lums-public

sudo docker build \
    -t lums:latest \
    .
```

Recreate with the current hardened runtime:

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

# 54. Browser Cache

If the source is correct but the browser still displays an old version:

```text
1. Hard refresh
2. Open Developer Tools
3. Disable cache temporarily
4. Reload
5. Inspect loaded CSS/JS
6. Check localStorage
7. Check data-theme
```

Firefox:

```text
Ctrl+Shift+R
```

Do not immediately rebuild the application because of a browser cache problem.

---

# 55. Git Diagnostics

Check repository status:

```bash
cd /opt/lums-public

git status -sb
```

Check remote:

```bash
git remote -v
```

Fetch:

```bash
git fetch origin
```

Check recent commits:

```bash
git log \
    --oneline \
    --decorate \
    -5
```

Check differences:

```bash
git diff
```

Check whitespace:

```bash
git diff --check
```

---

# 56. Git Deployment Checks

Before deployment:

```bash
cd /opt/lums-public

git status -sb
git fetch origin
git diff --check
```

If the local tree is clean and remote changes should be deployed:

```bash
git pull --ff-only origin main
```

Then:

```bash
git status -sb
```

Never overwrite local changes blindly.

---

# 57. Git Commit Identity

Current LUMS Git identity:

```text
Name:
xxxxxx
```

```text
Email:
xxxxx
```

Check:

```bash
git config user.name
git config user.email
```

---

# 58. Container Recreation

Recreating the container does not mean deleting the persistent database.

The important separation is:

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

Normal application deployment changes:

```text
source
   ↓
image
   ↓
container
```

while:

```text
lums-data
```

remains persistent.

Never add:

```bash
sudo docker volume rm lums-data
```

to normal deployment procedures.

That command is destructive.

---

# 59. Port Diagnostics

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
LUMS host-side binding

5000
Flask/Gunicorn inside Docker
```

Port `5050` should normally be bound only to:

```text
127.0.0.1
```

Port `5000` is internal to the container.

---

# 60. Firewall Diagnostics

Check firewall state:

```bash
sudo ufw status verbose
```

If nftables is used:

```bash
sudo nft list ruleset
```

Do not change firewall rules while diagnosing an application problem unless there is evidence that the firewall is involved.

---

# 61. Permission Diagnostics

Check source permissions:

```bash
ls -la \
    /opt/lums-public
```

Check TLS permissions:

```bash
sudo ls -la \
    /etc/lums/tls/
```

Check secret permissions:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/secrets/lums_secret
```

Check agent files:

```bash
sudo ls -la \
    /opt/lums-agent/
```

Do not make sensitive files world-readable as a troubleshooting workaround.

Avoid:

```bash
chmod 777
```

as a generic fix.

Determine which process actually needs access and correct that permission specifically.

---

# 62. Diagnostic Log Reference

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

# 63. Server Diagnostic Sequence

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
sudo docker logs --tail 50 lums

echo
echo "=== Port 5050 ==="
sudo ss -lntp | grep ':5050' || true

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

This sequence does not expose the actual secret.

---

# 64. Client Diagnostic Sequence

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

The token value is intentionally never displayed.

---

# 65. Public Bug Reports

Before publishing logs or screenshots, remove:

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

Use presence-only diagnostics instead.

---

# 66. Known Installation Lessons

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

does not automatically update an already running container.

After rebuilding, verify which image the container actually uses.

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

LUMS currently stores client authentication tokens as SHA-256 hexadecimal digests.

This is not the same mechanism used for password storage.

Passwords continue to use the application's password hashing mechanism.

---

## Lesson 6 — Do not expose secrets while troubleshooting

A diagnostic command is not safe merely because it is run locally.

Logs can later be copied into:

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
Store replacement
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

# 67. Final Checklist

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
[ ] lums-agent active
[ ] lums-agent.timer active
[ ] watcher timer active
[ ] CA file exists
[ ] LUMS_BASE configured
[ ] LUMS_TOKEN configured
[ ] LUMS_CA_FILE configured
[ ] Agent can reach LUMS
[ ] Agent authenticates
[ ] Agent reports successfully
```

## Jobs

```text
[ ] Job created
[ ] Job queued
[ ] Agent retrieves job
[ ] Job ownership verified
[ ] Agent claims job
[ ] Agent executes job
[ ] APT/dpkg succeeds
[ ] Result generated
[ ] Result reported
[ ] Server stores result
[ ] Frontend displays result
```

## Recovery

```text
[ ] Interrupted jobs can be identified
[ ] Running job ownership verified
[ ] Recovery endpoint available
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
[ ] Full isolated restore test still tracked
```

---

# 68. Final Principles

LUMS troubleshooting should follow a simple principle:

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

# 69. Current Architecture Summary

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
                         │                   │
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

The architecture deliberately separates:

```text
source
image
container
persistent data
secrets
agent
frontend
```

This separation makes LUMS easier to troubleshoot, update, rebuild and recover without unnecessarily destroying working components.

---

# 70. Final Rule

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
