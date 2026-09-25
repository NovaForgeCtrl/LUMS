# LUMS — Administration Guide

## Linux Update Management Server

**Version:** 2.6

This guide documents the administration, operation, deployment, maintenance, backup, recovery and troubleshooting of LUMS.

LUMS is designed as a centralized Linux update management system with controlled execution, client reporting, job tracking and administrative visibility.

The system separates:

* central management
* client reporting
* update job creation
* controlled execution
* execution monitoring
* persistent application data
* frontend presentation
* infrastructure services

The central principle is:

> **Do not change multiple layers at once. Identify the layer first, then change only what is required.**

---

# 1. Purpose

LUMS provides a central management interface for Linux update operations.

The system is designed to provide:

* client inventory
* client status reporting
* update information
* update job management
* controlled execution
* execution tracking
* simulation mode
* administrative visibility
* audit information
* centralized configuration
* TLS-protected external access
* client authentication
* client token lifecycle management
* interrupted-job recovery

LUMS does not replace the underlying Linux package manager.

The package manager remains responsible for the actual package operation.

LUMS controls when and where an update operation is requested and records the resulting state.

---

# 2. Supported Platforms

The current LUMS agent supports multiple Linux package-management backends.

Currently supported:

```text
APT / dpkg
pacman
```

The agent automatically detects the available package manager.

The current abstraction is implemented in:

```text
agent/package_manager.py
```

The detection order is:

```text
apt
 |
 +-- AptPackageManager

pacman
 |
 +-- PacmanPackageManager
```

If neither supported package manager is available, the agent stops with an explicit error.

The current agent version is:

```text
1.7.0
```

Both Debian-based and Arch-based clients have been tested end-to-end with the current agent.

---

# 3. Architecture

The current deployment consists of the following logical layers:

```text
                         Browser
                            |
                            | HTTPS :443
                            v
                    +----------------+
                    |     Nginx      |
                    | TLS / Reverse  |
                    |     Proxy      |
                    +-------+--------+
                            |
                            | HTTP localhost
                            v
                    +----------------+
                    | Docker: lums   |
                    |                |
                    | Gunicorn       |
                    | Flask          |
                    | Templates      |
                    | Static Assets  |
                    +-------+--------+
                            |
                            | Docker Volume
                            v
                    +----------------+
                    |   lums-data    |
                    |                |
                    | /var/lib/lums  |
                    | lums.db        |
                    +----------------+

                            ^
                            |
                       HTTPS / TLS
                            |
                    +-------+--------+
                    | LUMS Agent     |
                    |                |
                    | agent.py       |
                    | watcher.py     |
                    +-------+--------+
                            |
                            v
                 Package Manager Abstraction
                       /            \
                      /              \
                   APT/dpkg        pacman
```

The application itself is not directly exposed to the network.

Docker publishes the application only on localhost:

```text
127.0.0.1:5050 -> container:5000
```

Nginx provides the externally accessible HTTPS endpoint.

The production application server is Gunicorn.

The Flask development server is not used for the current production deployment.

---

# 4. Current Runtime Configuration

## 4.1 Repository

The application source repository is located at:

```text
/opt/lums-public
```

This directory contains the source tree used to build the Docker image.

Important distinction:

```text
/opt/lums-public
        |
        +-- Git source
        |
        +-- Docker build context
        +-- frontend source
        +-- server source
        +-- agent source

Docker image
        |
        +-- lums:latest

Docker container
        |
        +-- lums

Docker volume
        |
        +-- lums-data
        +-- /var/lib/lums/lums.db
```

The Git repository is not the database.

The Docker image is not the persistent database.

The container itself should not be treated as persistent application storage.

Persistent application data belongs in the Docker volume.

---

# 5. Important Paths

## 5.1 Application source

```text
/opt/lums-public
```

## 5.2 Docker configuration

```text
/etc/lums/docker/lums.env
```

## 5.3 Flask secret

```text
/etc/lums/secrets/lums_secret
```

The Flask secret is deliberately stored separately from the normal Docker environment configuration.

## 5.4 TLS

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

## 5.5 Database

Inside the container:

```text
/var/lib/lums/lums.db
```

Persistent storage:

```text
lums-data
```

## 5.6 Agent

```text
/opt/lums-agent/agent.py
/opt/lums-agent/watcher.py
/opt/lums-agent/lums-ca.crt
/etc/default/lums-agent
```

Do not place private keys, tokens, passwords or environment secrets inside Git.

---

# 6. Frontend Structure

The frontend is part of the application source tree.

Current runtime paths inside the container are:

```text
/app/server/templates/
/app/server/static/
```

Important frontend files include:

```text
/app/server/templates/login.html
/app/server/templates/index.html
/app/server/templates/client.html

/app/server/static/style.css
/app/server/static/theme.js
/app/server/static/network.js
/app/server/static/client.js
```

The frontend contains:

* HTML templates
* CSS
* JavaScript
* theme handling
* network visualization
* dashboard presentation
* client token rotation controls
* update management controls

The frontend is served by the Flask application and becomes part of the Docker image during deployment.

---

# 7. Theme System

LUMS currently provides six themes:

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

Theme selection is handled by:

```text
server/static/theme.js
```

The selected theme is stored in the browser using:

```text
localStorage
```

with the key:

```text
lums-theme
```

Theme selection therefore does not require a database entry.

The currently selected theme is applied through:

```html
<html data-theme="...">
```

Examples:

```html
<html data-theme="standard">
```

```html
<html data-theme="geek">
```

```html
<html data-theme="admin">
```

---

# 8. Theme Administration

The standard LUMS interface remains the default theme.

Available themes:

| Identifier    | User-facing name | Character               |
| ------------- | ---------------- | ----------------------- |
| `standard`    | Standard LUMS    | Original interface      |
| `LUMSStadium` | LUMS Stadium     | Stadium / Game-Day      |
| `golf`        | Golf Club        | Club / Golf             |
| `nerd`        | Nerd Mode        | Terminal / CRT / Matrix |
| `geek`        | Geek Lab         | Technical / Network     |
| `admin`       | Enterprise Admin | Operations Console      |

Theme state is client-side.

Changing a theme does not modify:

* database state
* authentication
* authorization
* update jobs
* client tokens
* agent communication
* audit logging

---

# 9. Enterprise Admin Theme

The Enterprise Admin theme is intentionally designed as an operational management console.

Its design principles are:

* light gray background
* white panels
* dark blue/gray header
* restrained blue accents
* thin borders
* compact spacing
* small corner radius
* minimal shadows
* no gradients
* no neon effects
* no large decorative icons
* no unnecessary animations
* information-dense tables
* simple status indicators

Enterprise-specific CSS should remain scoped using:

```css
html[data-theme="admin"]
```

The dedicated CSS section is located at the end of:

```text
server/static/style.css
```

and is marked:

```text
/* =========================================================
   LUMS // ENTERPRISE ADMIN
   Operations Console
   ========================================================= */
```

Avoid global CSS changes when modifying Enterprise Admin.

---

# 10. Geek Network Visualization

The Geek theme provides:

```text
The Living Network
```

The implementation is located in:

```text
server/static/network.js
```

The script exposes:

```javascript
window.LumsNetwork
```

with:

```text
start
stop
destroy
```

The visualization contains:

* drifting nodes
* connection lines
* moving packets
* dynamic network activity

The network visualization is only active when:

```text
data-theme="geek"
```

is active.

For other themes the network visualization is stopped.

Reduced-motion preferences are respected.

---

# 11. Nerd Theme

The Nerd theme provides a terminal/CRT/Matrix-style visual presentation.

The Matrix-style effect is controlled by:

```text
server/static/theme.js
```

It is only activated when:

```text
lums-theme = nerd
```

The Nerd theme must remain independent from:

```text
Geek / The Living Network
```

Theme-specific visual effects must not leak into other themes.

---

# 12. Docker Administration

## 12.1 Check container

```bash
sudo docker ps
```

Expected container:

```text
lums
```

## 12.2 Check all containers

```bash
sudo docker ps -a
```

## 12.3 Inspect container

```bash
sudo docker inspect lums
```

## 12.4 Check container status

```bash
sudo docker inspect \
    -f '{{.State.Status}}' \
    lums
```

## 12.5 Check restart policy

```bash
sudo docker inspect \
    -f '{{.HostConfig.RestartPolicy.Name}}' \
    lums
```

Expected:

```text
unless-stopped
```

---

# 13. Container Security State

The current production container is hardened.

The verified runtime properties are:

```text
User:
    lums

ReadonlyRootfs:
    true

CapDrop:
    ALL

Privileged:
    false
```

Verify:

```bash
sudo docker inspect lums \
    --format \
    'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{json .HostConfig.CapDrop}} Privileged={{.HostConfig.Privileged}}'
```

Expected:

```text
User=lums ReadonlyRootfs=true CapDrop=["ALL"] Privileged=false
```

The production documentation intentionally does not rely on a fixed numeric UID here. The configured container user is the authoritative value.

The hardened configuration must be preserved during container recreation.

---

# 14. Docker Image

The application image is:

```text
lums:latest
```

Build it from the repository:

```bash
cd /opt/lums-public

sudo docker build \
    -t lums:latest \
    .
```

Check the image:

```bash
sudo docker images lums
```

Verify the configured container user:

```bash
sudo docker image inspect \
    lums:latest \
    --format 'User={{.Config.User}}'
```

Expected:

```text
User=lums
```

The current application image is based on:

```text
python:3.13-slim
```

The image contains:

* Flask application
* Gunicorn
* frontend assets
* database initialization code
* application dependencies
* theme assets
* required application source

---

# 15. Container Startup

The container starts through:

```text
/app/docker-entrypoint.sh
```

The startup sequence is:

```text
Docker
   |
   v
docker-entrypoint.sh
   |
   +--> init_db.py
   |
   v
Gunicorn
   |
   +--> Worker
   +--> Worker
   |
   v
Flask application
```

The entrypoint initializes the database before starting Gunicorn.

The production application uses Gunicorn rather than the Flask development server.

The current production Gunicorn deployment uses:

```text
Gunicorn 23.0.0
gthread worker
```

The internal application binding is:

```text
0.0.0.0:5000
```

The Docker host exposes that application only through:

```text
127.0.0.1:5050
```

---

# 16. Container Recreation

Recreating the container does not remove the persistent database as long as the Docker volume is preserved.

The current hardened recreation procedure is:

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
sudo docker ps
```

Then:

```bash
sudo docker logs --tail 100 lums
```

The hardened options are part of the production configuration.

---

# 17. Critical Docker Rule

Never remove the persistent database volume as part of a normal application deployment.

The following command is destructive:

```bash
sudo docker volume rm lums-data
```

It removes persistent application data.

Do not execute it unless a complete reset is explicitly intended and a verified backup exists.

---

# 18. Docker Logs

View recent logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Follow logs:

```bash
sudo docker logs \
    -f \
    lums
```

View logs with timestamps:

```bash
sudo docker logs \
    --timestamps \
    --tail 200 \
    lums
```

For troubleshooting, start with:

```bash
sudo docker ps
sudo docker logs --tail 100 lums
```

before changing configuration.

Never use logs as a reason to expose secrets.

---

# 19. Secret Administration

The Flask application secret is stored outside the normal environment configuration.

Current production path:

```text
/etc/lums/secrets/lums_secret
```

The container receives:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

The secret is mounted read-only:

```text
/etc/lums/secrets/lums_secret
        |
        | read-only
        v
/run/secrets/lums_secret
```

The production environment must not contain:

```text
LUMS_SECRET_KEY=<secret>
```

The protected file is intentionally separated from the normal application environment configuration.

---

# 20. Secret File Permissions

The secret directory should be restricted.

The secret file is expected to be readable by the container's configured group while remaining inaccessible to unrelated users.

Check:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/secrets/lums_secret
```

Expected configuration:

```text
root:lums 640 /etc/lums/secrets/lums_secret
```

Never display the secret itself.

---

# 21. Secret Verification

Verify configuration without printing the secret:

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

---

# 22. Flask Secret Rotation

A Flask secret rotation is a controlled security change.

Before rotation:

1. Verify the database is healthy.
2. Create a database backup.
3. Verify the backup.
4. Generate a replacement secret.
5. Replace the protected secret file.
6. Restart the LUMS container.
7. Verify application startup.
8. Verify HTTPS.
9. Verify authentication.
10. Confirm old sessions are invalidated.

Changing the Flask secret invalidates existing Flask sessions.

Never record the old or new secret in documentation or logs.

---

# 23. Nginx Administration

Nginx provides the external HTTPS endpoint.

The architecture is:

```text
Client
  |
  v
HTTPS :443
  |
  v
Nginx
  |
  v
127.0.0.1:5050
  |
  v
Docker :5000
  |
  v
Gunicorn
  |
  v
Flask
```

Flask/Gunicorn is therefore not directly exposed to the network.

---

# 24. Nginx Configuration Test

Before reloading Nginx:

```bash
sudo nginx -t
```

Only reload after the configuration test succeeds:

```bash
sudo systemctl reload nginx
```

Check status:

```bash
sudo systemctl status nginx --no-pager
```

---

# 25. Nginx Logs

Error log:

```bash
sudo tail \
    -n 100 \
    /var/log/nginx/error.log
```

Access log:

```bash
sudo tail \
    -n 100 \
    /var/log/nginx/access.log
```

Follow errors:

```bash
sudo tail \
    -f \
    /var/log/nginx/error.log
```

---

# 26. Network and Health Checks

## 26.1 Check local application binding

```bash
sudo ss -lntp | grep ':5050'
```

Expected:

```text
127.0.0.1:5050
```

Port `5000` should not be directly exposed by the host.

## 26.2 Test local application endpoint

```bash
curl -I \
    http://127.0.0.1:5050/
```

Expected behavior:

```text
HTTP/1.1 302 FOUND
Location: /login
```

## 26.3 Test HTTPS endpoint

```bash
curl -kI \
    https://<LUMS_HOST>/
```

The `-k` option is intended only for controlled certificate diagnostics.

It must not replace proper certificate trust in production automation.

---

# 27. TLS Administration

TLS certificates are stored outside the Git repository.

Current paths:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Private keys must never be committed to Git.

Check certificate information:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

Check permissions:

```bash
sudo stat /etc/lums/tls/lums.crt
sudo stat /etc/lums/tls/lums.key
```

After certificate changes:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

# 28. TLS Protocols

The current Nginx configuration permits:

```text
TLS 1.2
TLS 1.3
```

Older TLS protocol versions must remain disabled.

Verify:

```bash
sudo nginx -T | grep -n \
    'ssl_protocols'
```

Expected:

```text
ssl_protocols TLSv1.2 TLSv1.3;
```

---

# 29. Security Headers

The current HTTPS deployment provides:

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

The current Content Security Policy includes:

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

Verify:

```bash
curl -kI \
    https://<LUMS_HOST>/
```

Security headers should remain present after frontend and Nginx changes.

---

# 30. Agent Configuration

The LUMS agent is installed outside the Docker container.

Current paths include:

```text
/opt/lums-agent/agent.py
/opt/lums-agent/watcher.py
/opt/lums-agent/lums-ca.crt
/etc/default/lums-agent
```

Current agent version:

```text
1.7.0
```

A documented configuration example is:

```text
LUMS_BASE=https://<LUMS_HOST>
LUMS_TOKEN=<CLIENT_TOKEN>
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

Protect the configuration:

```bash
sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

Never print the real token during troubleshooting.

# 31. Job Recovery

Recovery changes an interrupted job from:

```text
running
```

to:

```text
abandoned
```

The recovery operation validates:

* job existence,
* client ownership,
* current job state,
* valid recovery transition.

The operation records:

```text
finished_at
recovery reason
update history
```

The job is not falsely reported as successful.

Recovery is designed to preserve the historical execution state rather than silently deleting or recreating the job.

---

# 32. Recovery Reason

The recovery reason distinguishes an interrupted execution from a normal failure or success.

The current recovery reason identifies that:

```text
Agent did not submit a final result.
```

This allows the history to distinguish:

```text
success
failed
abandoned
```

Recovery must remain visible in the job history.

---

# 33. Recovery Race Protection

Recovery uses a conditional state transition.

If another operation changes the job state first, the recovery operation must not overwrite the newer state.

Conceptually:

```text
running
   │
   ├── agent result
   │
   └── recovery
```

Only one valid transition should win.

This prevents stale recovery requests from silently modifying already-completed jobs.

The same principle applies to normal job claiming.

---

# 34. Recovery Testing

Controlled recovery testing verifies:

```text
status:
    abandoned

finished_at:
    populated

recovery_reason:
    Agent did not submit a final result.
```

The associated history entry must remain available.

Package statistics must remain associated with the historical job.

After recovery testing, temporary test data should be removed.

A successful normal update execution should then be verified to ensure that recovery did not break the normal execution path.

---

# 35. Agent Security

The LUMS agent communicates with the server using HTTPS.

The agent configuration contains the server endpoint, client credential and CA configuration.

Typical configuration:

```text
LUMS_BASE
LUMS_TOKEN
LUMS_CA_FILE
```

Example:

```text
LUMS_BASE="https://<LUMS_SERVER_HOSTNAME>"
LUMS_TOKEN="<CLIENT_TOKEN>"
LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt"
```

The actual credential is never documented.

TLS verification must remain enabled.

Certificate problems must be fixed rather than bypassed by disabling verification.

---

# 36. Agent Configuration Protection

The agent configuration is stored outside the Git repository.

Typical location:

```text
/etc/default/lums-agent
```

Sensitive values must not be committed.

Check permissions:

```bash
sudo stat \
    /etc/default/lums-agent
```

The actual token value must not appear in diagnostic output shared publicly.

The configuration should contain only the values required by the installed agent.

---

# 37. systemd Agent Service

The LUMS agent runs as a systemd service.

The service is designed as a `oneshot` operation.

A successful execution therefore normally ends with:

```text
inactive (dead)
```

after the agent process exits successfully.

This is expected behavior.

The recurring execution is handled by the corresponding timer.

Check:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Run manually when required:

```bash
sudo systemctl start \
    lums-agent.service
```

---

# 38. systemd Agent Timer

The agent timer periodically starts the service.

Conceptually:

```text
systemd timer
      ↓
lums-agent.service
      ↓
agent.py
      ↓
report / job processing
      ↓
exit
      ↓
wait for next timer
```

The timer remains active while the oneshot service starts and exits for each cycle.

Check:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Check the next scheduled execution:

```bash
systemctl list-timers \
    lums-agent.timer \
    --no-pager
```

---

# 39. Idle Detection

The current agent does not rely on:

```text
w -h
```

for idle detection.

Idle detection uses systemd-logind through:

```text
loginctl
```

The agent examines relevant user sessions and uses fields including:

```text
Class
Type
TTY
State
IdleHint
IdleSinceHintMonotonic
```

The current idle source is:

```text
loginctl
```

The agent reports:

```text
idle_source=loginctl
idle_supported=True
```

when idle detection is available.

The current idle threshold is:

```text
300 seconds
```

---

# 40. Idle Detection Diagnostics

List available sessions:

```bash
loginctl list-sessions \
    --no-legend \
    --no-pager
```

Inspect a session:

```bash
loginctl show-session \
    <SESSION_ID>
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

An active user session should result in:

```text
idle = false
```

An idle session may allow an update job to continue once the configured threshold has been reached.

The agent must not treat an unsupported or unreliable idle state as confirmed inactivity.

---

# 41. Idle Detection Failure Behavior

If logind information cannot be retrieved reliably, the agent does not pretend to know that the system is idle.

Failure is treated conservatively.

The agent therefore avoids using an unreliable idle state as permission to perform potentially disruptive operations.

The intended behavior is:

```text
Idle state known
      │
      ├── active
      │      ↓
      │   wait
      │
      └── idle
             ↓
          continue
```

If the state cannot be established reliably:

```text
unknown
   ↓
do not assume idle
```

---

# 42. Package Manager Detection

The agent automatically detects the installed package manager.

Current abstraction:

```text
detect_package_manager()
        │
        ├── apt      → AptPackageManager
        │
        └── pacman   → PacmanPackageManager
```

Implementation:

```text
agent/package_manager.py
```

Compile-check:

```bash
cd /opt/lums-public

python3 -m py_compile \
    agent/package_manager.py
```

The command should return without an error.

The package-manager abstraction keeps distribution-specific operations outside the main update engine.

---

# 43. Debian / APT Diagnostics

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

Do not delete package-manager lock files blindly.

---

# 44. Arch / pacman Diagnostics

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

# 45. Package Manager Locks

Package-manager locks must be investigated before attempting repair.

On Debian-based systems:

```bash
sudo lsof \
    /var/lib/dpkg/lock-frontend
```

and:

```bash
sudo lsof \
    /var/lib/dpkg/lock
```

On Arch:

```bash
sudo lsof \
    /var/lib/pacman/db.lck
```

Do not blindly delete lock files.

If another package operation is active, determine whether it is legitimate before taking corrective action.

The current LUMS execution lock protects LUMS-controlled operations, but it cannot automatically prevent every manually started package-manager process from the operating system.

---

# 46. Update Jobs

When a job does not execute, determine where it stopped.

Current lifecycle:

```text
Job created
    ↓
pending
    ↓
waiting_for_idle
    ↓
running
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

Possible terminal states include:

```text
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

# 47. Execution Watcher

The Execution Watcher monitors update execution independently from the normal reporting timer.

Current components:

```text
lums-execution-watcher.timer
        ↓
lums-execution-watcher.service
        ↓
watcher.py
```

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

View logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

The watcher participates in controlled recovery and job execution monitoring.

---

# 48. Supported Update Actions

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

# 49. Reboot Requirement

Some updates may require a reboot.

On Debian-based systems, check:

```bash
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot flag present"
```

Other distributions may provide additional mechanisms.

For example:

```bash
sudo needs-restarting -r
```

may be available depending on the distribution and installed packages.

Do not assume that every successful update requires a reboot.

LUMS does not treat successful package installation as an automatic instruction to reboot the client.

---

# 50. Database Diagnostics

LUMS uses SQLite for persistent application state.

The database is:

```text
/var/lib/lums/lums.db
```

The persistent Docker volume is:

```text
lums-data
```

Check database integrity without requiring the SQLite CLI:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
'
```

Expected:

```text
ok
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

# 51. SQLite Runtime Configuration

The current SQLite connection configuration includes:

```text
foreign_keys = ON
busy_timeout = 5000
```

The database uses:

```text
journal_mode = WAL
```

Verify:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for pragma in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    print(f"{pragma} =", db.execute(f"PRAGMA {pragma}").fetchone()[0])

db.close()
'
```

The expected runtime state is:

```text
journal_mode = wal
busy_timeout = 5000
foreign_keys = 1
```

The observed synchronous setting is:

```text
2
```

which corresponds to SQLite's normal `FULL` synchronous mode.

---

# 52. SQLite Migrations

Database schema changes are handled through migrations.

The current production migration sequence includes:

```text
001
002
003-login-rate-limiting
```

Migration 003 introduces:

```text
login_rate_limits
```

and its associated indexes.

Migrations should be:

* idempotent,
* applied in order,
* checked after execution,
* verified against database integrity.

Never modify migration history manually unless performing a controlled database recovery operation.

---

# 53. Login Rate Limiting

Administrator login attempts are rate-limited.

The current lock escalation is:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

The rate-limit key combines:

```text
normalized username
+
request source
```

Failed authentication attempts are stored in:

```text
login_rate_limits
```

Successful authentication clears the corresponding rate-limit record.

A blocked request returns the same generic authentication failure response as an invalid credential attempt.

The system does not disclose whether a username exists.

---

# 54. Login Rate-Limit Diagnostics

Check the table:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
rows = db.execute(
    """
    SELECT
        rate_limit_key,
        username,
        failed_attempts,
        first_failed_at,
        last_failed_at,
        locked_until
    FROM login_rate_limits
    """
).fetchall()

for row in rows:
    print(row)

db.close()
'
```

Do not expose this information publicly.

The table can contain usernames and source information.

After controlled testing, temporary test records should be removed.

---

# 55. Frontend Architecture

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

# 56. Frontend Source Paths

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

# 57. Current Themes

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

Theme state is stored client-side.

The localStorage key is:

```text
lums-theme
```

---

# 58. Browser Theme Selection

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

Changing the theme does not change database state or authentication state.

---

# 59. Theme JavaScript

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

Remember:

```text
Repository source
        ≠
running container
```

until the new image has actually been built and deployed.

---

# 60. Geek / The Living Network

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

The runtime script exposes:

```javascript
window.LumsNetwork
```

with:

```text
start
stop
destroy
```

The network visualization is active only for:

```text
data-theme="geek"
```

For other themes, the visualization is stopped.

Reduced-motion preferences are respected.

The Geek visualization is a presentation feature only and does not participate in:

* authentication,
* authorization,
* job execution,
* client communication,
* database persistence.

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

Theme changes are frontend presentation changes and should not alter:

```text
authentication
authorization
client communication
job execution
database state
```

---

# 63. Client Page / Token Rotation UI

The client page contains the client token rotation functionality.

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

Token rotation requires authenticated administrative access.

The rotation process:

```text
Administrator
      ↓
authenticated request
      ↓
token rotation
      ↓
new token generated
      ↓
SHA-256 digest stored
      ↓
old token invalidated
      ↓
new token returned once
```

The plaintext replacement token must not be written to audit records.

After rotation:

```text
old token
   ↓
401 / rejected

new token
   ↓
authenticated request
```

The client must subsequently be configured with the new token.

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

The resulting job follows the normal lifecycle:

```text
pending
   ↓
waiting_for_idle
   ↓
running
   ↓
success / partial / failed
```

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

A source change is not active in production until the corresponding image has been built and the container has been recreated or otherwise updated.

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

First determine whether the browser is still using cached frontend assets.

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

Before deployment, the working tree should be understood rather than blindly overwritten.

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

A production deployment should be traceable to a known source revision.

---

# 69. Git Identity

The LUMS Git identity is intentionally represented in public documentation without exposing a personal mailbox.

Check:

```bash
git config user.name
git config user.email
```

Expected name:

```text
NovaForgeCtrl
```

For public documentation, use a repository-safe placeholder for the email rather than publishing personal contact information.

The repository itself remains the authoritative location for the configured Git identity.

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

The persistent volume must remain attached when replacing the application container.

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

The intended application flow is:

```text
Browser
   ↓
HTTPS :443
   ↓
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker :5000
   ↓
Gunicorn / Flask
```

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

Application ports should not be opened externally merely for troubleshooting.

After temporary firewall changes, restore the intended configuration and retest.

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

The container's secret mount is intentionally read-only.

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

When reviewing logs, check the complete request or job flow rather than looking only at the final error message.

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
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
'
```

This sequence deliberately does not expose the actual Flask secret.

A `404` from an endpoint that does not exist is not by itself proof that Gunicorn or Flask is unavailable.

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

The current agent version is:

```text
1.7.0
```

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

Logs should also be reviewed for accidental credential exposure before being shared.

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

For client requests, also verify that the client is enabled and that its current token has not been invalidated through rotation.

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

A `404` does not automatically mean that Flask is unavailable.

LUMS does not currently provide a `/health` endpoint, so a request to such an endpoint may legitimately return `404`.

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

A `502` normally requires checking whether the upstream application is running and reachable.

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

Expected:

```text
FILE=/run/secrets/lums_secret
SECRET_FILE=READABLE
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

Expected:

```text
User=lums
ReadonlyRootfs=true
CapDrop=["ALL"]
Privileged=false
```

---

## Persistent volume accidentally removed

Symptom:

```text
Application starts with missing or newly initialized data.
```

Check:

```bash
sudo docker volume inspect \
    lums-data
```

Do not recreate the volume unless intentionally performing a destructive recovery or clean installation.

---

# 80. Known Installation Lessons

The LUMS installation process has demonstrated several important operational lessons.

### Source is not runtime

```text
/opt/lums-public
        ↓
Docker build
        ↓
lums:latest
        ↓
container
```

Changing source files alone does not change the running application.

---

### Container recreation must preserve data

The application container is disposable.

The database volume is persistent:

```text
lums-data
```

Therefore:

```text
Container
   ↓
replaceable

Database
   ↓
persistent
```

---

### Secrets must remain outside Git

Production secrets belong outside the repository.

The current Flask secret is provided through:

```text
/etc/lums/secrets/lums_secret
        ↓
/run/secrets/lums_secret
        ↓
LUMS_SECRET_KEY_FILE
```

---

### Security settings are part of deployment

A deployment is not complete merely because the application starts.

Verify:

```text
non-root execution
read-only root filesystem
capabilities dropped
localhost-only application binding
protected secret
persistent database volume
HTTPS
authentication
```

---

### Agent communication is a complete chain

When an update does not arrive, inspect the complete path:

```text
systemd timer
   ↓
lums-agent.service
   ↓
agent.py
   ↓
HTTPS
   ↓
Nginx
   ↓
Flask / Gunicorn
   ↓
job database
   ↓
agent retrieval
   ↓
job claim
   ↓
idle check
   ↓
package manager
   ↓
result reporting
```

A failure anywhere in this chain can prevent the expected result.

---

### Documentation must describe the tested system

The Administration Guide should reflect the actual deployed state.

When implementation changes, review at minimum:

```text
agent version
Docker runtime
database configuration
job lifecycle
security controls
authentication
token lifecycle
diagnostic commands
client verification
```

The documentation should not claim a feature is verified when it has only been implemented but not tested.

# 81. Debian Client Verification

The Debian client has successfully completed the current LUMS agent communication flow.

Verified:

```text
Agent:
    1.7.0

OS:
    Debian 13

Architecture:
    x86_64

Package manager:
    APT / dpkg

Report:
    accepted

Authentication:
    successful

Update job:
    successful
```

The client successfully completed inventory reporting and update-job execution.

The current agent version is:

```text
1.7.0
```

The installed client should correspond to the tested agent implementation.

---

# 82. Arch Linux Client Verification

The Arch Linux client has successfully completed the same LUMS management flow.

Verified:

```text
Agent:
    1.7.0

OS:
    Arch Linux

Architecture:
    x86_64

Kernel:
    7.2.6-arch2-1

Package manager:
    pacman

systemd:
    261.3-1

Python:
    3.14.7

pacman:
    7.1.0

Report:
    accepted

Authentication:
    successful

Update job:
    successful
```

The Arch client was successfully verified with the current agent implementation.

The installed agent version is:

```text
1.7.0
```

---

# 83. Cross-Distribution Update Flow

The current architecture supports:

```text
                    LUMS
                     │
             UPDATE_SYSTEM
                     │
          ┌──────────┴──────────┐
          │                     │
       Debian                 Arch
          │                     │
       lums-agent            lums-agent
          │                     │
        APT / dpkg             pacman
          │                     │
        result                result
          │                     │
          └──────────┬──────────┘
                     │
                     ▼
                  LUMS
```

The management layer therefore remains distribution-independent while the client package-manager layer remains distribution-specific.

The agent detects the package manager and delegates package operations through:

```text
agent/package_manager.py
```

The current tested package managers are:

```text
APT / dpkg
pacman
```

---

# 84. Security Testing Checklist

## Container

```text
[x] Container runs as non-root
[x] Dedicated container user configured
[x] Container is not privileged
[x] All Linux capabilities dropped
[x] Root filesystem is read-only
[x] /tmp uses tmpfs
[x] /tmp uses nosuid
[x] /tmp uses nodev
[x] /tmp uses noexec
[x] Persistent database volume is separate
[x] Secret mount is separate
[x] Secret mount is read-only
[x] Application binding is localhost-only
```

The current runtime identity is documented as:

```text
User=lums
```

The numeric UID should only be documented when verified against the actual production runtime.

## Secrets

```text
[x] Flask secret isolated from normal environment
[x] Secret stored outside Git
[x] Secret mounted read-only
[x] Secret rotation tested
[x] Production secret rotated
[x] Old production secret invalidated
[x] Temporary old-secret material removed
[x] Client token generation uses cryptographically secure randomness
[x] Client token hash stored instead of plaintext
[x] Client token rotation implemented
[x] Previous client token invalidated
[x] Token rotation audit event implemented
[x] Token values excluded from audit records
```

## Authentication

```text
[x] Administrator authentication implemented
[x] Argon2 password hashing
[x] Invalid credentials rejected
[x] Client Bearer authentication implemented
[x] Invalid client token rejected
[x] Protected endpoints require authentication
[x] Token rotation requires administrator authentication
[x] CSRF protection for administrative token rotation
[x] Login rate limiting implemented
```

## Authorization

```text
[x] Client identity established server-side
[x] Client/job ownership checked
[x] Job result ownership checked
[x] Recovery ownership checked
[x] Atomic job claiming
[ ] Full role-based administrative authorization model
```

## Database

```text
[x] SQLite integrity verification
[x] Foreign-key enforcement
[x] Busy timeout
[x] WAL journal mode
[x] SQLite-aware backup
[x] Backup integrity verification
[ ] Full isolated restore test
```

---

# 85. Current Security Limitations

## 85.1 Package Manager Coordination

LUMS controls its own package-management operations.

It cannot automatically prevent arbitrary manually started package-manager processes from running simultaneously.

Further APT/dpkg coordination remains a hardening task.

---

## 85.2 Administrative Roles

The current administrative model is intentionally simple.

A full role-based access-control model has not yet been implemented.

The current authentication model therefore should not be described as a complete multi-role RBAC system.

---

## 85.3 SQLite Scaling

SQLite is appropriate for the current project scope and laboratory deployment.

Larger environments may eventually require a dedicated database service depending on:

* client count,
* concurrency,
* job volume,
* audit volume,
* availability requirements,
* backup requirements.

The current SQLite implementation has already been hardened with:

```text
foreign_keys = ON
busy_timeout = 5000
journal_mode = WAL
```

---

## 85.4 Restore Validation

SQLite backup creation and integrity verification are implemented.

A complete isolated restore test remains outstanding.

Backup verification therefore proves backup integrity, but does not replace a full restore test.

---

## 85.5 Automated Security Testing

Security checks currently exist at multiple manual and operational layers.

The completed audit work includes dedicated testing for:

```text
SQLite handling
update timeout handling
login rate limiting
```

A comprehensive automated security regression suite and CI integration remain future work.

---

# 86. Remaining Security Roadmap

## Phase 1 — Container Hardening

**Status: Complete**

Implemented and verified:

* non-root container,
* dropped capabilities,
* non-privileged runtime,
* read-only root filesystem,
* tmpfs `/tmp`,
* persistent database volume,
* protected secret mount,
* localhost-only application binding.

---

## Phase 2 — Secret Isolation and Rotation

**Status: Complete**

Implemented and verified:

* protected host secret,
* read-only secret mount,
* production secret replacement,
* old session invalidation,
* new authentication,
* protected secret handling.

---

## Phase 3 — Client Token Lifecycle

**Status: Complete**

Implemented and verified:

* cryptographically secure token generation,
* SHA-256 token digest storage,
* Bearer authentication,
* administrative rotation,
* immediate old-token invalidation,
* CSRF protection,
* audit event,
* one-time replacement-token presentation,
* production agent reconfiguration.

---

## Phase 4 — Multi-Distribution Package Management

**Status: Complete**

Implemented and tested:

```text
APT / dpkg
pacman
```

Verified environments:

```text
Debian 13
Arch Linux
```

---

## Phase 5 — Idle Detection

**Status: Complete**

The previous idle-detection approach was replaced by systemd-logind-based detection.

Current mechanism:

```text
loginctl
```

Current threshold:

```text
300 seconds
```

The agent reports the active source through:

```text
idle_source=loginctl
idle_supported=True
```

when supported.

---

## Phase 6 — Interrupted Job Recovery

**Status: Complete**

Implemented and tested:

* ownership validation,
* state validation,
* controlled recovery,
* `abandoned` state,
* recovery reason,
* history preservation,
* package-statistic preservation,
* race protection.

---

## Phase 7 — SQLite Connection Hardening

**Status: Complete**

Implemented:

```text
foreign_keys = ON
busy_timeout = 5000
journal_mode = WAL
```

Migration and runtime behavior were verified.

---

## Phase 8 — Update Execution Timeout Hardening

**Status: Complete**

The update execution path now uses selector-driven process output handling.

Timeout behavior includes:

```text
timeout
   ↓
terminate()
   ↓
10-second grace period
   ↓
kill() fallback
```

The final process status is reported as:

```text
timeout
```

when the timeout path is reached.

---

## Phase 9 — Login Rate Limiting

**Status: Complete**

Current lock escalation:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

The rate-limit key combines normalized username and request source.

Concurrent access was tested using database transaction locking.

---

## Phase 10 — Backup and Restore

**Status: Partially complete**

Implemented:

* SQLite-aware backup,
* protected backup storage,
* integrity verification.

Remaining:

```text
Full isolated restore test
```

---

## Phase 11 — Automated Security Tests

**Status: Planned**

Potential automated regression tests include:

* authentication,
* authorization,
* token rotation,
* token invalidation,
* CSRF,
* job ownership,
* job claiming,
* recovery,
* timeout handling,
* login rate limiting,
* security headers,
* container hardening,
* secret handling,
* database integrity.

---

## Phase 12 — Final Security Review

**Status: Planned**

The final review should compare:

```text
Documentation
      ↕
Implementation
      ↕
Production
```

The final security state should only be documented as fully reviewed after the remaining hardening tasks have been tested.

---

# 87. Responsible Security Reporting

Security issues should be reported responsibly.

A useful security report contains:

* short description,
* affected component,
* reproduction steps,
* expected behavior,
* actual behavior,
* potential impact,
* suggested mitigation,
* relevant redacted logs.

Never include:

* passwords,
* client tokens,
* private keys,
* Flask secrets,
* personal information,
* complete production databases,
* unredacted inventory data.

Sensitive information must be removed before logs, screenshots, or configuration files are shared.

---

# 88. Security Maintenance

Security reviews should be performed after:

* application changes,
* authentication changes,
* authorization changes,
* Docker changes,
* Nginx changes,
* certificate changes,
* database schema changes,
* agent changes,
* package-manager changes,
* watcher changes,
* deployment changes,
* secret changes.

Regularly review:

```text
Operating system updates
Docker images
Python dependencies
Flask dependencies
Gunicorn
Nginx
TLS configuration
File permissions
Database backups
Git history
Authentication
Authorization
Job execution
Package-manager coordination
Container privileges
Container capabilities
Secret handling
Secret rotation
Agent configuration
systemd services
systemd timers
```

---

# 89. Security Change Workflow

Security-sensitive changes should follow a controlled workflow:

```text
Inspect
   ↓
Understand current behavior
   ↓
Design change
   ↓
Implement
   ↓
Syntax check
   ↓
Unit test
   ↓
Debian test
   ↓
Arch test
   ↓
Integration test
   ↓
Production verification
   ↓
Document
```

A failed test should not be hidden by changing the documentation to match the failure.

The implementation must be corrected or the limitation documented.

After a completed change:

```bash
git status
git diff
git diff --check
```

should be reviewed before committing.

---

# 90. Current Security Roadmap Status

The current overall state is:

```text
[x] Non-root container
[x] Drop ALL capabilities
[x] Privileged container disabled
[x] Read-only root filesystem
[x] tmpfs /tmp
[x] Localhost-only application binding
[x] Protected secret file
[x] Read-only secret mount
[x] Secret isolation
[x] Flask secret rotation
[x] Administrator authentication
[x] Client authentication
[x] Client token hashing
[x] Client token rotation
[x] Client token invalidation
[x] Token rotation audit logging
[x] CSRF protection for token rotation
[x] Login rate limiting
[x] Job ownership validation
[x] Atomic job claiming
[x] Interrupted-job recovery
[x] Debian client communication
[x] Arch client communication
[x] APT support
[x] pacman support
[x] systemd-logind idle detection
[x] SQLite foreign keys
[x] SQLite busy timeout
[x] SQLite WAL
[x] Update timeout handling
[x] Gunicorn deployment
[x] HTTPS reverse proxy
[x] Security headers
[x] SQLite integrity verification
[x] SQLite-aware backup
[x] Backup integrity verification

[ ] Complete package-manager collision prevention
[ ] Full backup / restore test
[ ] Automated security regression tests
[ ] Full RBAC model
[ ] Final security review
```

The completed controls should not be interpreted as meaning that LUMS has no remaining security work.

Security hardening is continuous.

---

# 91. Security Verification Principles

LUMS follows several operational rules.

## Rule 1 — Do not trust configuration alone

A configuration file saying:

```text
read-only
```

is not sufficient.

The running container must be inspected.

---

## Rule 2 — Do not trust successful startup alone

A running container does not prove:

* authentication works,
* HTTPS works,
* database integrity is valid,
* clients can authenticate,
* update jobs work.

Each layer must be verified.

---

## Rule 3 — Verify backups

A backup must be:

```text
created
   ↓
protected
   ↓
integrity checked
   ↓
eventually restored in isolation
```

A file existing on disk does not prove that it is a usable recovery copy.

---

## Rule 4 — Treat exposed secrets as compromised

A secret that was exposed must not be considered safe merely because it is no longer visible.

It must be rotated.

---

## Rule 5 — Authentication does not equal authorization

A valid client token establishes client identity.

The server must still verify whether that client is authorized for the requested resource.

---

## Rule 6 — Package installation is privileged execution

Update jobs must be treated as privileged operations.

The system must control:

```text
who
what
where
when
result
```

---

## Rule 7 — Documentation follows verification

Documentation should describe the actual tested state.

If something is incomplete, it must be marked as incomplete.

---

# 92. Final Verified Architecture

The current verified security architecture is:

```text
                    Network
                       │
                       ▼
                  ┌─────────┐
                  │  Nginx  │
                  │  HTTPS  │
                  └────┬────┘
                       │
                127.0.0.1:5050
                       │
                       ▼
                ┌─────────────┐
                │    Docker   │
                │     lums    │
                └──────┬──────┘
                       │
                  Gunicorn :5000
                       │
                       ▼
                     Flask
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
     Authentication  Jobs       Audit
          │            │            │
          └────────────┼────────────┘
                       ▼
                    SQLite
                       │
                       ▼
                   lums-data
                       │
                       │ HTTPS + Bearer
                       ▼
              ┌──────────────────┐
              │     Clients      │
              └────────┬─────────┘
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
        Debian 13            Arch Linux
             │                   │
        lums-agent 1.7.0    lums-agent 1.7.0
             │                   │
        APT / dpkg             pacman
             │                   │
             └─────────┬─────────┘
                       ▼
                    Result
                       │
                       ▼
                    LUMS API
```

The architecture deliberately separates:

```text
Management Plane
```

from:

```text
Execution Plane
```

The server manages the desired operation.

The client performs the actual package-management operation.

---

# 93. Final Management / Execution Separation

The final architecture deliberately separates:

```text
Management Plane
       │
       ├── Nginx
       ├── HTTPS
       ├── Gunicorn
       ├── Flask
       ├── Authentication
       ├── Authorization
       ├── Inventory
       ├── Job Management
       └── SQLite

from

Execution Plane
       │
       ├── lums-agent
       ├── systemd
       ├── Execution Watcher
       ├── Package Manager Abstraction
       ├── APT / dpkg
       └── pacman
```

The server does not directly execute package-management commands on managed clients.

The client is responsible for:

```text
inventory
update detection
job claiming
idle evaluation
package execution
result reporting
```

This separation reduces the need for the server to have direct operating-system privileges on managed clients.

---

# 94. Final Security State

The current LUMS implementation has verified security controls across:

```text
Container
   ↓
Network
   ↓
TLS
   ↓
Authentication
   ↓
Authorization
   ↓
Secrets
   ↓
Tokens
   ↓
Jobs
   ↓
Recovery
   ↓
Idle Detection
   ↓
Agent
   ↓
Package Manager
   ↓
Database
   ↓
Backups
```

Security audit items currently completed include:

```text
01 SQLite Foreign Keys
02 SQLite WAL / Busy Timeout
03 Update Timeout / process.kill()
04 Login Rate-Limiting
```

The remaining work is explicitly limited to the documented open hardening areas.

The project should not claim a final security review until those remaining areas have been tested.

---

# 95. Final Security Principles

The following principles apply to LUMS:

1. Never store secrets in Git.
2. Never expose the Flask/Gunicorn application directly to the network.
3. Use HTTPS for client communication.
4. Keep TLS verification enabled.
5. Separate authentication from authorization.
6. Validate client identity server-side.
7. Protect administrator credentials.
8. Protect client tokens.
9. Protect TLS private keys.
10. Protect the mounted Flask secret.
11. Keep database backups secure.
12. Verify backups rather than trusting file existence.
13. Do not remove persistent volumes during ordinary troubleshooting.
14. Do not automatically reboot clients.
15. Review changes before deployment.
16. Test security-sensitive changes.
17. Document incidents and configuration changes.
18. Do not claim incomplete security controls are fully implemented.
19. Keep update execution controlled and auditable.
20. Harden the container incrementally.
21. Treat secret isolation and secret rotation as separate controls.
22. Treat previously exposed secrets as compromised until rotated.
23. Rotate client tokens through the authenticated administrative workflow.
24. Verify replacement credentials before closing a credential change.
25. Keep production secrets outside Git and outside normal container environment variables where practical.
26. Use distribution-specific package-manager implementations behind a controlled abstraction.
27. Validate job ownership on the server.
28. Use atomic state transitions for job claiming and recovery.
29. Prefer conservative behavior when system state cannot be reliably determined.
30. Keep production documentation synchronized with verified implementation state.
31. Test recovery paths, not only successful paths.
32. Treat security hardening as a continuous process rather than a one-time configuration.

---

# 96. Final Principle

LUMS is designed to centralize Linux update management without removing operational control from the administrator.

The system should remain:

* Transparent
* Auditable
* Controlled
* Secure
* Documented
* Maintainable

The architecture deliberately separates:

```text
Management Plane
       │
       ├── Nginx
       ├── Gunicorn
       ├── Flask
       ├── Authentication
       ├── Authorization
       ├── Inventory
       ├── Job Management
       └── Database

from

Execution Plane
       │
       ├── lums-agent
       ├── systemd
       ├── Execution Watcher
       ├── Package Manager Abstraction
       └── APT / dpkg / pacman
```

Security improvements are implemented one controlled layer at a time.

The established hardening workflow remains:

```text
Inspect
   ↓
Test
   ↓
Verify
   ↓
Production
   ↓
Verify
   ↓
Document
```

> **LUMS — Linux Update Management without the noise.**

---

# 97. Current Agent State

The currently tested LUMS agent version is:

```text
1.7.0
```

The current agent components are:

```text
lums-agent.service
lums-agent.timer
```

and, for execution monitoring:

```text
lums-execution-watcher.service
lums-execution-watcher.timer
```

The agent uses:

```text
HTTPS
Bearer authentication
CA verification
package-manager abstraction
systemd-logind idle detection
```

Current tested environments:

```text
Debian 13
Arch Linux
```

Current package managers:

```text
APT / dpkg
pacman
```

The version documented here must be updated whenever the deployed agent version changes.

---

# 98. Current Production Security State

The current production container should verify as:

```text
User:
    lums

ReadonlyRootfs:
    true

Privileged:
    false

Capabilities:
    ALL dropped

/tmp:
    tmpfs

Application binding:
    127.0.0.1:5050

Persistent data:
    lums-data

Secret:
    /run/secrets/lums_secret
```

The production secret is supplied through:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

The host-side secret is:

```text
/etc/lums/secrets/lums_secret
```

The secret mount is read-only.

The application database is:

```text
/var/lib/lums/lums.db
```

and is backed by:

```text
lums-data
```

The current database hardening includes:

```text
foreign_keys = ON
busy_timeout = 5000
journal_mode = WAL
```

The current authentication hardening includes:

```text
Argon2 administrator passwords
Bearer client authentication
SHA-256 token digests
client token rotation
token invalidation
login rate limiting
CSRF protection
```

---

# 99. Administration Verification Baseline

A healthy current LUMS deployment should be verifiable through the following baseline:

```text
Server
    ↓
Docker container running
    ↓
Gunicorn running
    ↓
Nginx running
    ↓
HTTPS available
    ↓
Administrator authentication
    ↓
Client authentication
    ↓
Client inventory
    ↓
Update detection
    ↓
Job creation
    ↓
waiting_for_idle
    ↓
Job execution
    ↓
Result reporting
    ↓
Audit history
```

For clients:

```text
Debian 13
    ↓
lums-agent 1.7.0
    ↓
APT / dpkg
```

and:

```text
Arch Linux
    ↓
lums-agent 1.7.0
    ↓
pacman
```

For interrupted execution:

```text
running
    ↓
recovery
    ↓
abandoned
```

For normal execution:

```text
pending
    ↓
waiting_for_idle
    ↓
running
    ↓
success / partial / failed
```

A production verification should test the complete chain rather than only checking whether the container is running.

---

# 100. Final Architecture

The complete LUMS architecture is:

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
                         │   Docker: lums    │
                         │                   │
                         │     Gunicorn      │
                         │        │          │
                         │      Flask        │
                         └─────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
              Authentication    Jobs           Audit
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                              SQLite WAL
                                   │
                              lums-data
                                   │
                    HTTPS + Bearer Authentication
                                   │
                  ┌────────────────┴────────────────┐
                  │                                 │
                  ▼                                 ▼
           Debian 13 Client                  Arch Linux Client
                  │                                 │
          lums-agent 1.7.0                  lums-agent 1.7.0
                  │                                 │
             APT / dpkg                         pacman
                  │                                 │
                  └────────────────┬────────────────┘
                                   │
                                Results
                                   │
                                   ▼
                                LUMS API
```

The operational model is therefore:

```text
Management
    ↓
LUMS Server
    ↓
Authorized Job
    ↓
Client
    ↓
Idle Check
    ↓
Package Manager
    ↓
Execution
    ↓
Result
    ↓
Audit / History
```

The final administrative principle is:

```text
Do not assume.
Verify.

Do not overwrite.
Preserve.

Do not expose.
Protect.

Do not claim.
Test.

Do not reinstall first.
Find the failing layer.
```

**LUMS — Linux Update Management without the noise.**
