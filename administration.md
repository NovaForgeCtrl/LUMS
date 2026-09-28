# LUMS — Administration Guide

## Linux Update Management Server

**Version:** 2.7

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

The system provides:

* client inventory
* client status reporting
* update information
* update job management
* controlled update execution
* execution tracking
* simulation mode
* administrative visibility
* audit information
* centralized configuration
* TLS-protected external access
* administrator authentication
* role-based authorization
* client authentication
* client token lifecycle management
* interrupted-job recovery
* application logging
* operational history

LUMS does not replace the underlying Linux package manager.

The package manager remains responsible for the actual package operation.

LUMS controls when and where an update operation is requested and records the resulting state.

The server manages the operation.

The client performs the actual package-management operation.

This separation is intentional:

```text
Management Plane
        ↓
LUMS Server
        ↓
Authorized Job
        ↓
Execution Plane
        ↓
Managed Client
```

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

The current Execution Watcher version is:

```text
1.2.1
```

Both Debian-based and Arch-based clients have been tested end-to-end with the current agent implementation.

Current verified environments:

```text
Debian 13
Arch Linux
```

Current tested package managers:

```text
APT / dpkg
pacman
```

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
                       Bearer Auth
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

The application and client execution planes are deliberately separated.

The server does not directly execute package-management commands on managed clients.

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

The current production container is intentionally replaceable.

The persistent state is kept separately from the container lifecycle.

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

The production container receives the secret through:

```text
/run/secrets/lums_secret
```

using:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

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

Frontend changes therefore require a new application image before they become active in the running container.

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

Theme state is presentation state only.

Changing the theme does not modify:

* authentication
* authorization
* client tokens
* update jobs
* agent communication
* database state
* audit history

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

Theme selection is therefore independent from server-side operational state.

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

Theme-specific styling must not alter application behavior.

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

The visualization is a frontend presentation feature only.

It does not participate in:

* authentication
* authorization
* job execution
* client communication
* database persistence
* audit logging

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

The Nerd theme does not modify server-side application behavior.

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

The container should be treated as a replaceable runtime instance.

Persistent application state must remain outside the container filesystem.

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

The container also uses:

```text
/tmp:
    tmpfs

/tmp flags:
    rw,nosuid,nodev,noexec
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

The production documentation intentionally does not rely on a fixed numeric UID here.

The configured container user is the authoritative runtime identity.

The hardened runtime configuration must be preserved during container recreation.

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

The image itself must not be treated as persistent storage.

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
   +--> database initialization / migrations
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

The entrypoint prepares the database before starting Gunicorn.

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

Gunicorn access and application logs are emitted to the container log stream.

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

After recreation, verify at minimum:

```text
container running
persistent volume mounted
secret readable
localhost binding present
read-only root filesystem
capabilities dropped
non-root user
HTTPS through Nginx
database integrity
```

The hardened options are part of the production configuration and must not be omitted from a normal deployment.

---

# 17. Critical Docker Rule

Never remove the persistent database volume as part of a normal application deployment.

The following command is destructive:

```bash
sudo docker volume rm lums-data
```

It removes persistent application data.

Do not execute it unless a complete reset is explicitly intended and a verified backup exists.

Normal container replacement is:

```text
stop
   ↓
remove container
   ↓
build / select image
   ↓
create container
   ↓
reuse lums-data
```

The volume must remain separate from the container lifecycle.

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

The application emits structured application log messages for important operational events.

Examples include:

```text
Client report
Update job created
Update job claimed
```

Gunicorn access and error output is also available through Docker logs.

For troubleshooting, start with:

```bash
sudo docker ps
sudo docker logs --tail 100 lums
```

before changing configuration.

Never use logs as a reason to expose secrets.

Review logs before publishing them externally.

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

The secret must never be committed to Git.

It must also never be written into application logs or audit details.

---

# 20. Secret File Permissions

The secret directory should be restricted.

The secret file is expected to be readable by the configured container group while remaining inaccessible to unrelated users.

Check:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/secrets/lums_secret
```

The currently documented production configuration is:

```text
root:lums 640 /etc/lums/secrets/lums_secret
```

Never display the secret itself.

When changing ownership or permissions, verify the running container can still read the mounted secret before considering the change complete.

A secret permission change should therefore be followed by:

```text
container startup check
        ↓
application log check
        ↓
authentication check
```

# 21. Secret Verification

Verify the secret configuration without printing the secret itself:

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

The actual secret value must never be printed.

---

# 22. Flask Secret Rotation

A Flask secret rotation is a controlled security change.

Before rotation:

1. Verify that the database is healthy.
2. Create a database backup.
3. Verify the backup.
4. Generate a replacement secret.
5. Replace the protected secret file.
6. Restart the LUMS container.
7. Verify application startup.
8. Verify HTTPS.
9. Verify authentication.
10. Confirm that old sessions are no longer accepted.

Changing the Flask secret invalidates existing Flask sessions.

The replacement secret must not be stored in:

```text
Git
Docker image layers
application logs
audit details
normal environment configuration
```

Never record the old or new secret in documentation or logs.

After rotation, the administrator should verify the complete authentication path before considering the change complete.

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

Nginx is responsible for the externally reachable HTTP/TLS layer.

The application should not be exposed directly on:

```text
0.0.0.0:5000
```

or:

```text
0.0.0.0:5050
```

The intended host-side application binding remains:

```text
127.0.0.1:5050
```

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

A configuration test should be performed before every intentional Nginx configuration reload.

If the test fails, do not reload the broken configuration.

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

When troubleshooting an HTTP error, correlate Nginx logs with:

```text
Docker logs
application logs
browser request
client request
```

A request reaching Nginx does not necessarily mean that it reached Flask.

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

The intended flow is:

```text
127.0.0.1:5050
        ↓
Docker
        ↓
5000/tcp
```

---

## 26.2 Test local application endpoint

```bash
curl -I \
    http://127.0.0.1:5050/
```

Expected behavior for an unauthenticated browser request:

```text
HTTP/1.1 302 FOUND
Location: /login
```

The exact HTTP status should be interpreted together with the current application routing.

LUMS does not currently provide a dedicated `/health` endpoint.

Therefore, requesting an endpoint that does not exist can legitimately return:

```text
404
```

without proving that the application itself is unavailable.

---

## 26.3 Test HTTPS endpoint

```bash
curl -kI \
    https://<LUMS_HOST>/
```

The `-k` option is intended only for controlled certificate diagnostics.

It must not replace proper certificate trust in production automation.

For normal operation, clients should validate the server certificate through the configured CA/trust chain.

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

After reloading, verify:

```bash
curl -kI \
    https://<LUMS_HOST>/
```

Certificate replacement is not complete until both the Nginx configuration and the externally reachable HTTPS endpoint have been verified.

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

If the active configuration differs from the documented state, verify the complete Nginx configuration before changing anything.

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

A frontend change that unexpectedly causes a CSP violation should be investigated before weakening the policy.

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

Current Watcher version:

```text
1.2.1
```

A documented configuration example is:

```text
LUMS_BASE=https://<LUMS_HOST>
LUMS_TOKEN=<CLIENT_TOKEN>
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

The actual client token must never be included in documentation.

Protect the configuration:

```bash
sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

Verify permissions:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/default/lums-agent
```

Never print the real token during troubleshooting.

---

# 31. Agent Authentication

The agent authenticates against LUMS using a client-specific Bearer token.

Conceptually:

```text
Client
   |
   | HTTPS
   | Authorization: Bearer <CLIENT_TOKEN>
   v
LUMS API
   |
   v
Client identity
```

The server does not store the plaintext client token.

Instead, the token is represented by a SHA-256 digest.

Token rotation therefore follows:

```text
Administrator
      ↓
authenticated rotation request
      ↓
new token generated
      ↓
SHA-256 digest stored
      ↓
old token invalidated
      ↓
new token presented once
```

After rotation, the client must be configured with the replacement token.

The old token must no longer authenticate.

---

# 32. Client Token Rotation

Client token rotation is an administrative operation.

Before rotating a token:

1. Identify the correct client.
2. Verify that the administrator is authenticated.
3. Confirm that the client is the intended target.
4. Rotate the token through the LUMS administrative interface.
5. Store the replacement token securely.
6. Update the client configuration.
7. Trigger a controlled agent report.
8. Verify successful authentication.
9. Confirm that the old token is invalid.

The replacement token should be treated as a credential.

It must not be placed in:

```text
Git
screenshots
logs
audit details
public documentation
```

The plaintext token is intended to be presented only during the rotation workflow.

---

# 33. Client Token Diagnostics

When a client stops authenticating after a token change, verify the configuration without revealing the token.

Example:

```bash
sudo awk -F= '
/^LUMS_BASE=/ {
    print "LUMS_BASE=<set>"
}
/^LUMS_TOKEN=/ {
    print "LUMS_TOKEN=<set>"
}
/^LUMS_CA_FILE=/ {
    print "LUMS_CA_FILE=" $2
}
' /etc/default/lums-agent
```

Then verify the CA file:

```bash
test -f /opt/lums-agent/lums-ca.crt \
    && echo "CA file present" \
    || echo "CA file missing"
```

Check the service:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Trigger a controlled report:

```bash
sudo systemctl start \
    lums-agent.service
```

Then inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "10 minutes ago" \
    --no-pager
```

Do not test authentication by printing the actual token.

---

# 34. systemd Agent Service

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

For a successful oneshot service, the relevant result is the service execution result rather than whether the process remains running.

---

# 35. systemd Agent Timer

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

A healthy timer should show a future trigger time.

---

# 36. Execution Watcher Service

The Execution Watcher is separate from the normal reporting service.

Current components:

```text
lums-agent-watcher.service
lums-agent-watcher.timer
```

The current Watcher version is:

```text
1.2.1
```

The operational model is:

```text
lums-agent-watcher.timer
        ↓
lums-agent-watcher.service
        ↓
watcher.py
        ↓
job inspection / recovery / execution monitoring
```

Check the timer:

```bash
sudo systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Check the service:

```bash
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

View logs:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

The watcher participates in controlled job execution and interrupted-job recovery.

---

# 37. Idle Detection

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

The current idle threshold is:

```text
300 seconds
```

When idle detection is available, the agent reports:

```text
idle_source=loginctl
idle_supported=True
```

This information allows the server-side job state and client-side execution behavior to distinguish active and idle sessions.

---

# 38. Idle Detection Diagnostics

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

# 39. Idle Detection Failure Behavior

If logind information cannot be retrieved reliably, the agent does not pretend to know that the system is idle.

Failure is treated conservatively.

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

This prevents an uncertain session state from being interpreted as permission to perform a potentially disruptive update operation.

Idle detection is therefore a safety control, not merely a scheduling convenience.

---

# 40. Package Manager Detection

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

The current tested implementations are:

```text
AptPackageManager
PacmanPackageManager
```

The abstraction is responsible for operations such as:

```text
package inventory
update detection
package state
install
remove
package update
system update
candidate version lookup
```

The actual command remains distribution-specific.

# 41. APT Administration

For Debian-based clients, LUMS uses the APT/dpkg backend.

The relevant implementation is:

```text
agent/package_manager.py
```

The backend uses:

```text id="j7kq3x"
apt
apt-get
apt-cache
dpkg-query
```

The agent uses separate operations for:

```text id="3sm3jp"
package inventory
update detection
package state
package installation
package removal
package update
system update
candidate version lookup
```

The update detection command is executed with error checking enabled.

This is important because an APT command failure must not silently appear as an empty update list.

The current implementation therefore treats an unsuccessful update-detection command as an error.

---

# 42. APT Package Inventory

The installed package inventory is collected through:

```text id="4p6x2b"
dpkg-query
```

The agent reports the resulting package information to LUMS.

A successful report contains the installed package inventory together with:

```text id="8d5l0n"
client identity
hostname
IP information
package information
available updates
agent information
idle information
```

The server stores the latest client state.

The package inventory should therefore be interpreted as the state reported by the client during its most recent successful report.

---

# 43. APT Update Detection

Available updates are detected using:

```bash id="4c5x8w"
apt list --upgradable
```

The command is executed with subprocess error checking.

This distinction is important.

These two states must not be treated as equivalent:

```text id="0ik9ty"
No packages are upgradable
```

and:

```text id="e8z0n3"
APT update detection failed
```

The first is a valid clean state.

The second is an operational error.

The agent therefore propagates the failure instead of silently reporting an empty update list.

---

# 44. APT Package Installation

Package installation uses:

```bash id="gxy4gr"
apt-get install -y <package>
```

The exact package list is determined by the update job.

The package name must be validated by the server before a job is created.

The agent then executes only the packages belonging to the claimed job.

The actual result is reported per package.

A package can therefore result in:

```text id="qq4m3f"
success
failed
timeout
```

The server records the package result as part of the update history.

---

# 45. APT Package Removal

Package removal uses:

```bash id="yl2nuw"
apt-get remove -y <package>
```

Removal is an explicit job action.

The server validates the requested package and the client ownership before the job becomes executable.

Package removal must not be confused with update installation.

The job action determines which package-manager operation is executed.

---

# 46. APT Package Update

A package-specific update uses:

```bash id="4v3j3m"
apt-get install --only-upgrade -y <package>
```

This operation instructs APT to update the selected package without installing it as a new package when it is not already installed.

The server tracks the requested package as part of the update job.

The agent reports the result after execution.

---

# 47. APT System Update

A complete system update uses:

```bash id="qz1zri"
apt-get upgrade -y
```

This is a broader operation than updating an individual package.

The distinction is:

```text id="w9of0a"
UPDATE_PACKAGE
    ↓
selected package(s)

UPDATE_SYSTEM
    ↓
system-wide package update
```

System-wide operations should be treated as higher-impact administrative actions.

They should therefore be tested carefully before being used on production clients.

---

# 48. APT Candidate Version

The agent can query the candidate version of a package through:

```bash id="u5v2h3"
apt-cache policy <package>
```

The result is used when the agent needs package version information.

The candidate version represents the version APT currently considers installable from the configured repositories.

A candidate version is not by itself proof that the package update has already been installed.

The actual installed state must be determined separately.

---

# 49. pacman Administration

For Arch Linux clients, LUMS uses the pacman backend.

The implementation is:

```text id="0v0x5g"
agent/package_manager.py
```

The backend uses:

```text id="q7gq8f"
pacman
```

The supported operations are:

```text id="y9wz6m"
package inventory
update detection
package state
package installation
package removal
package update
system update
candidate version lookup
```

The package-manager abstraction allows the update engine to use the same job model for Debian-based and Arch-based clients.

---

# 50. pacman Package Inventory

Installed packages are queried with:

```bash id="xqg5a6"
pacman -Q
```

The resulting inventory is included in the client report.

The report allows LUMS to maintain a current view of the client package state.

The package inventory belongs to the client report.

It is not a live query from the LUMS server.

---

# 51. pacman Update Detection

Available updates are detected with:

```bash id="4rmqge"
pacman -Qu
```

The output is interpreted by the pacman backend.

A clean result means that no updates are currently reported by pacman.

An execution failure is different from an empty result and must remain distinguishable.

This follows the same principle used for APT:

```text id="v4v48x"
successful command + empty result
        ≠
command failure
```

---

# 52. pacman Package Installation

Package installation uses:

```bash id="9d7r6p"
pacman -S --noconfirm <package>
```

The requested package is taken from the authorized update job.

The agent does not accept arbitrary package commands from the network.

The job action and package list are determined by the LUMS server and validated before execution.

---

# 53. pacman Package Removal

Package removal uses:

```bash id="w7xj0m"
pacman -R --noconfirm <package>
```

Removal is handled as a separate job action.

The server-side job model determines whether the requested operation is:

```text id="0ctq6k"
install
remove
update
system update
```

The client executes the corresponding package-manager operation.

---

# 54. pacman Package Update

For a package-specific update, pacman uses:

```bash id="g8aj1z"
pacman -S --noconfirm <package>
```

The package is therefore explicitly requested from pacman.

The resulting command execution is monitored by the agent.

The result is reported back to LUMS.

---

# 55. pacman System Update

A complete Arch Linux system update uses:

```bash id="l5h2ut"
pacman -Syu --noconfirm
```

This operation can update multiple packages and potentially introduce a kernel or other system-level changes.

It is therefore treated as a system-level update job rather than an ordinary package update.

After a system update, the client may require a reboot.

LUMS therefore performs reboot-required detection separately from the package execution itself.

---

# 56. pacman Candidate Version

The candidate version is queried through:

```bash id="l4zv9x"
pacman -Si <package>
```

The candidate version represents the package version currently available from the configured repositories.

The installed version remains a separate piece of state.

This distinction is important when comparing:

```text id="xv7xw4"
installed version
        ↓
current local package state

candidate version
        ↓
currently available repository state
```

---

# 57. Reboot Detection

LUMS checks whether a reboot may be required after update operations.

For Debian-based systems, the current check uses:

```text id="g8y3ez"
/var/run/reboot-required
```

For Arch Linux, the agent uses the installed Linux kernel package information and compares available kernel module releases against the currently running kernel.

The Arch implementation uses:

```text id="eqf6a1"
pacman -Ql linux
```

and checks paths under:

```text id="jz2w0x"
/usr/lib/modules/
```

The running kernel is obtained through:

```text id="c1z3xk"
platform.release()
```

The purpose is to detect the common case where a new kernel is installed while the system is still running an older kernel.

---

# 58. Reboot Detection Safety

Reboot detection is intentionally conservative.

Unknown operating systems do not automatically receive a positive reboot-required state.

Errors during detection do not result in a fabricated reboot requirement.

The current behavior is conceptually:

```text id="d7qf8h"
known system
    |
    +-- reboot marker / kernel mismatch
    |       ↓
    |   reboot required
    |
    +-- no indication
            ↓
       no reboot detected
```

The detection mechanism is advisory state.

It does not itself reboot a client.

A reboot remains an explicit operational decision.

---

# 59. Update Job Model

An update job represents an authorized operation for a specific client.

Conceptually:

```text id="7m5x3e"
Client
   |
   v
Update Job
   |
   +-- Action
   |
   +-- Package(s)
   |
   +-- Status
   |
   +-- Ownership
   |
   +-- Execution state
   |
   +-- Result
   |
   +-- History
```

The job model separates:

```text id="yq2q9s"
requested operation
execution state
package result
historical record
```

A job belongs to one client.

A client cannot claim another client's job.

The server validates this ownership before execution.

---

# 60. Update Job Actions

The current job actions include:

```text id="v4w3u6"
UPDATE_PACKAGE
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_SYSTEM
```

The selected action determines the package-manager operation.

Examples:

```text id="0n9g0w"
UPDATE_PACKAGE
    ↓
apt-get install --only-upgrade -y <package>

INSTALL_PACKAGE
    ↓
apt-get install -y <package>

REMOVE_PACKAGE
    ↓
apt-get remove -y <package>

UPDATE_SYSTEM
    ↓
apt-get upgrade -y
```

or, on Arch:

```text id="zh4y6e"
UPDATE_PACKAGE
    ↓
pacman -S --noconfirm <package>

INSTALL_PACKAGE
    ↓
pacman -S --noconfirm <package>

REMOVE_PACKAGE
    ↓
pacman -R --noconfirm <package>

UPDATE_SYSTEM
    ↓
pacman -Syu --noconfirm
```

The package-manager abstraction keeps these differences out of the central job model.

# 61. Job Creation

Update jobs are created through the LUMS administrative interface.

The server validates the requested operation before creating the job.

The validation includes:

```text id="7v2h5p"
authenticated administrative user
        ↓
authorized role
        ↓
valid client
        ↓
client ownership
        ↓
valid action
        ↓
valid package input
        ↓
job creation
```

The resulting job is associated with the selected client.

The job is persisted in the database before execution begins.

Creating a job does not immediately mean that the package operation is running.

The job must first pass through the execution lifecycle.

---

# 62. Job Lifecycle

The operational lifecycle is:

```text id="0l6p1r"
created
   ↓
pending
   ↓
claimed
   ↓
running
   ↓
success / partial / failed
```

Interrupted execution can additionally result in a recovery path:

```text id="5n2m6x"
running
   ↓
interrupted
   ↓
recovery
   ↓
pending / abandoned / completed
```

The exact state depends on the execution and recovery conditions.

The important administrative distinction is:

```text id="f5q2q6"
pending
    = waiting for execution

running
    = execution has been claimed

completed
    = execution finished and result was recorded
```

A job must not be manually changed between states without understanding the corresponding execution state.

---

# 63. Atomic Job Claiming

A pending job must be claimed atomically.

The purpose is to prevent two execution paths from processing the same job simultaneously.

Conceptually:

```text id="m1j0k4"
Watcher A ──┐
            ├──> atomic claim ──> Job
Watcher B ──┘
```

Only one execution path should successfully transition the job into its running state.

The claim operation therefore combines:

```text id="t4qf8x"
job selection
+
ownership validation
+
state validation
+
state transition
```

This prevents a race condition in which multiple workers could otherwise start the same update job.

---

# 64. Job Ownership

Every update job belongs to a specific client.

The server validates the relationship:

```text id="v5nq6h"
job.client_id == requesting_client_id
```

before allowing client-side job operations.

This applies to operations such as:

```text id="4avqg2"
claim
checkpoint
result
abandon
```

A client must not be able to manipulate another client's job.

The ownership check is part of the security model.

---

# 65. Client-Side Job Discovery

The agent communicates with the LUMS API to determine whether work is available.

The conceptual flow is:

```text id="h4s8s2"
Agent
  |
  | authenticated request
  v
LUMS API
  |
  | pending job
  v
Client
```

The client does not receive arbitrary shell commands.

The job contains structured information such as:

```text id="x6j5k1"
action
package information
job identity
client ownership
```

The agent maps the authorized action to the appropriate package-manager operation.

---

# 66. Job Claim

Once a suitable job is discovered, the client attempts to claim it.

The server performs the atomic state transition.

Conceptually:

```text id="l0d4gk"
pending
   |
   | atomic claim
   v
running
```

If another execution path has already claimed the job, the second claim must not succeed.

This is one of the protections against duplicate package execution.

The client should therefore never assume that merely finding a pending job means that it owns the job.

---

# 67. Job Execution

After successful claiming:

```text id="r5z9p3"
running
   ↓
package manager
   ↓
command execution
   ↓
result collection
   ↓
result submission
```

The agent executes the operation locally.

The LUMS server does not execute:

```text id="8n2q8k"
apt
apt-get
pacman
dpkg
```

on behalf of the client.

The client performs the operation.

The server records the resulting state.

---

# 68. Update Timeout

Update execution is subject to a timeout.

The purpose is to prevent a package-manager process from remaining indefinitely in a running state.

The execution lifecycle includes:

```text id="j8t6q1"
start
  ↓
monitor
  ↓
timeout?
  ├── no → normal completion
  |
  └── yes
       ↓
    terminate
       ↓
    grace period
       ↓
    kill if necessary
```

The implementation therefore does not rely on a single indefinite subprocess call.

A timeout is represented separately from an ordinary package failure.

The package result can therefore contain:

```text id="0d3n7j"
success
failed
timeout
```

---

# 69. Timeout Process Handling

When a process exceeds the configured timeout, the agent first attempts graceful termination.

If the process does not exit during the grace period, the process is forcefully terminated.

The intended sequence is:

```text id="n7u5c2"
timeout
  ↓
terminate()
  ↓
grace period
  ↓
poll()
  ↓
kill() if still running
```

This prevents a timed-out package operation from leaving the agent permanently blocked.

Timeout handling is especially important for:

* package-manager stalls
* repository/network problems
* broken package scripts
* interrupted system operations

---

# 70. Package-Level Results

LUMS tracks package results individually.

A package result contains the package identity and execution status.

Valid package statuses are:

```text id="b0u8tr"
success
failed
timeout
```

The server validates incoming job results.

Invalid result data is rejected.

The server verifies:

```text id="o5n8j4"
valid job
+
correct client
+
job currently running
+
valid overall status
+
valid package result structure
+
package belongs to job
```

This prevents arbitrary package results from being attached to unrelated jobs.

---

# 71. Overall Job Result

The overall job status can be:

```text id="d9q1fk"
success
partial
failed
```

The distinction is important.

### Success

All relevant operations completed successfully.

### Partial

At least part of the requested operation completed, while another part did not.

### Failed

The requested operation did not complete successfully.

The server validates the submitted status before recording it.

---

# 72. Job Result Reporting

After execution, the client reports the result to LUMS.

Conceptually:

```text id="8a1g8j"
Package Manager
      ↓
Agent
      ↓
Result validation
      ↓
LUMS API
      ↓
Database
      ↓
History
```

The result endpoint does not blindly accept arbitrary package data.

The server validates the result structure before updating the database.

Successful result processing updates the relevant job/package state and creates the corresponding history information.

---

# 73. Update History

Completed package operations become part of the update history.

The history provides an administrative record of:

```text id="k4v3j9"
client
job
package
action
result
timestamp
```

The history should be used to answer operational questions such as:

```text id="j6y3x5"
Was this update executed?
Which client received it?
When was it executed?
Did it succeed?
Which package was involved?
```

History is not a substitute for application logs.

The two serve different purposes:

```text id="c9m5x1"
Application logs
    ↓
runtime / operational events

Update history
    ↓
persistent update records
```

---

# 74. Checkpointing

Long-running update operations use checkpoint information to preserve execution progress.

A checkpoint allows the server to distinguish between:

```text id="9k7v4n"
job known to be running
```

and:

```text id="x8w2r4"
job that may have stopped reporting
```

The checkpoint belongs to the authenticated client/job relationship.

The server validates that the reporting client owns the corresponding job.

Checkpoint information is therefore part of the recovery mechanism.

---

# 75. Running Job Recovery

A running job can become interrupted if the client:

* loses power
* loses network connectivity
* crashes
* reboots
* terminates the agent
* becomes otherwise unreachable

LUMS therefore does not assume that:

```text id="j3g4m8"
running
```

means:

```text id="m2p8z1"
process definitely still exists
```

The recovery mechanism evaluates stale execution state.

The purpose is to prevent a permanently running job from blocking future execution.

---

# 76. Recovery Principle

The recovery model follows:

```text id="5x8d2q"
active execution
      ↓
checkpoint updates
      ↓
communication stops
      ↓
stale execution detected
      ↓
recovery evaluation
      ↓
safe state transition
```

The server must distinguish a temporarily unreachable client from a genuinely abandoned execution as far as the available state allows.

Recovery therefore uses persisted job state rather than relying exclusively on the current network connection.

---

# 77. Abandoned Jobs

A job may eventually be classified as abandoned when recovery determines that the previous execution can no longer be considered active.

An abandoned job must remain visible in the administrative history.

The purpose is not to hide the interrupted execution.

Instead:

```text id="0v5f8p"
interrupted execution
        ↓
recovery decision
        ↓
visible final state
```

This allows administrators to identify interrupted operations and investigate the corresponding client.

An abandoned job should not silently disappear.

---

# 78. Recovery and Ownership

Recovery operations are also subject to client ownership.

A client must not be able to recover or modify another client's job.

The server therefore validates:

```text id="l7f1q0"
authenticated client
        ↓
client identity
        ↓
job ownership
        ↓
allowed recovery operation
```

This applies even when the job itself is already in a problematic state.

Recovery is therefore part of the authorization boundary rather than an administrative bypass.

---

# 79. Simulation Mode

LUMS supports simulation mode for controlled testing.

Simulation is intended to verify job handling without executing the real package-manager operation.

The test principle is:

```text id="w2t6p7"
LUMS job
   ↓
agent
   ↓
simulation
   ↓
result
```

The actual package-manager operation must not be executed while simulation is active.

Simulation tests cover:

```text id="q5n9y3"
UPDATE_PACKAGE
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_SYSTEM
unknown action
```

The tests explicitly guard against accidental execution of the real package-management commands.

Simulation mode is therefore useful for testing the job lifecycle without modifying the client package state.

---

# 80. Recommended Job Test

Before using a newly deployed LUMS installation for real updates, perform a controlled test.

Recommended sequence:

```text id="n2g8v5"
1. Verify client report
2. Verify package inventory
3. Verify available updates
4. Create a controlled job
5. Confirm client idle state
6. Confirm job claim
7. Monitor execution
8. Verify result
9. Verify history
10. Verify final client state
```

For development or validation environments, simulation should be used before executing a real package-management operation.

For production changes, select a known test package or otherwise controlled operation where appropriate.

The objective is to validate the complete chain:

```text id="w5k3r1"
Web UI
 ↓
API
 ↓
Database
 ↓
Job
 ↓
Agent
 ↓
Package Manager
 ↓
Result
 ↓
History
```

A successful dashboard response alone is not sufficient proof that the complete execution chain works.
# 81. Debian Client Administration

The Debian client is managed through the LUMS agent.

The current verified Debian environment is:

```text id="j3r5y7"
Debian 13
```

The client uses:

```text id="q8h4m1"
APT / dpkg
LUMS Agent 1.7.0
```

A successful client cycle includes:

```text id="8j6s4k"
package inventory
        ↓
update detection
        ↓
HTTPS report
        ↓
server authentication
        ↓
client state update
```

The current Debian client has successfully completed real agent execution and update reporting.

The expected successful service result is:

```text id="q2v5k8"
status=0/SUCCESS
```

Because the agent service is a oneshot service, the service may subsequently appear as:

```text id="6f3m8w"
inactive (dead)
```

This is normal after a successful execution.

---

# 82. Arch Linux Client Administration

The Arch client is managed through the same LUMS agent architecture.

The current verified environment is:

```text id="5k9r2v"
Arch Linux
x86_64
pacman
```

The client uses:

```text id="n8j4p6"
LUMS Agent 1.7.0
Execution Watcher 1.2.1
```

The current Arch package-management implementation has been tested directly.

The regression check confirmed:

```text id="4q7s3m"
package_manager = pacman
```

and successful package-state/candidate-version handling.

The client has also completed a successful real agent execution and reported a clean update state.

The Arch client therefore uses the same management lifecycle as the Debian client while retaining its native package-manager implementation.

---

# 83. Client Authentication Model

LUMS uses two separate authentication boundaries.

## Administrative users

Administrative users authenticate through the web application.

They use:

```text id="p5k8x1"
username
password
session
role
```

## Managed clients

Managed clients authenticate through:

```text id="s2v7q4"
Bearer token
```

The two authentication systems must not be confused.

Conceptually:

```text id="y8m2c6"
Administrator
    ↓
Web authentication
    ↓
Session
    ↓
Role authorization

Client
    ↓
Bearer token
    ↓
Client identity
    ↓
Client/job ownership
```

A client token does not grant administrative web access.

An administrative user session does not replace client authentication for agent API calls.

---

# 84. Authorization Model

The current LUMS authorization model consists of:

```text id="w4m7p2"
Administrative RBAC
+
Client identity
+
Client/job ownership
+
Endpoint-specific authorization
```

The server validates the authenticated identity before allowing protected operations.

For clients, this includes:

```text id="j6n8x3"
client identity
job ownership
result ownership
checkpoint ownership
recovery ownership
```

For administrative users, authorization is determined by the user's role.

The current administrative roles are:

```text id="q7v2m5"
administrator
operator
viewer
```

The full role-based administrative authorization model is implemented.

---

# 85. Role-Based Access Control

## 85.1 Administrator

The `administrator` role has full administrative access.

Administrator permissions include:

```text id="8f2n5k"
view clients
view updates
view packages
view jobs
view history

create clients
delete/disable clients
rotate client tokens

create update jobs
execute update jobs

manage users
manage roles
```

The administrator is the only administrative role with user and role management capabilities.

---

## 85.2 Operator

The `operator` role is intended for operational update management.

Operators can:

```text id="x6m4q9"
view clients
view updates
view packages
view jobs
view history

create update jobs
execute update jobs
```

Operators cannot:

```text id="b5q8w2"
create administrative users
manage roles
rotate client tokens
delete clients
```

This separates day-to-day update operations from identity and infrastructure administration.

---

## 85.3 Viewer

The `viewer` role provides read-only administrative visibility.

Viewers can:

```text id="r7k3p1"
view dashboard
view clients
view updates
view packages
view jobs
view history
```

Viewers cannot:

```text id="m8q5z4"
create clients
create update jobs
rotate tokens
delete clients
manage users
manage roles
```

The role is intended for monitoring and observation without modification privileges.

---

# 86. RBAC Permission Matrix

The current administrative permission model is:

| Route / Function      | Administrator | Operator | Viewer |
| --------------------- | :-----------: | :------: | :----: |
| Dashboard             |       ✓       |     ✓    |    ✓   |
| View clients          |       ✓       |     ✓    |    ✓   |
| View client details   |       ✓       |     ✓    |    ✓   |
| View client updates   |       ✓       |     ✓    |    ✓   |
| View client packages  |       ✓       |     ✓    |    ✓   |
| View update jobs      |       ✓       |     ✓    |    ✓   |
| View update history   |       ✓       |     ✓    |    ✓   |
| Create client         |       ✓       |     —    |    —   |
| Create update job     |       ✓       |     ✓    |    —   |
| Execute update job    |       ✓       |     ✓    |    —   |
| Rotate client token   |       ✓       |     —    |    —   |
| Delete/disable client |       ✓       |     —    |    —   |
| User management       |       ✓       |     —    |    —   |
| Role management       |       ✓       |     —    |    —   |
| Logout                |       ✓       |     ✓    |    ✓   |

Agent endpoints remain separate from this administrative RBAC model.

Agent authentication continues to use client-specific Bearer tokens.

---

# 87. RBAC Implementation

The role definitions are implemented centrally in:

```text id="q1f8s6"
server/security.py
```

Current constants:

```text id="3j7m2v"
administrator
operator
viewer
```

Valid roles are restricted to the defined role set.

The authenticated user is stored in the request context after successful authentication.

Role authorization is applied using:

```text id="8k4r1p"
role_required(...)
```

The decorator rejects unauthorized administrative operations.

The authorization result is distinct from authentication.

Conceptually:

```text id="v6q3m9"
Not authenticated
        ↓
401 / login

Authenticated
        ↓
Role checked
        ↓
Role allowed?
   ├── yes → continue
   └── no  → 403
```

---

# 88. RBAC Database Migration

Administrative roles are stored in the users table.

The migration adds:

```text id="m7q2x8"
users.role
```

with the default role:

```text id="v3n6p1"
administrator
```

The RBAC migration is:

```text id="j8r4w2"
002-rbac
```

The migration is designed to be idempotent.

This allows an existing LUMS installation to receive the role field without recreating the database.

After migration, an existing administrator receives:

```text id="c5y7k3"
role = administrator
```

The role must be verified after migration.

---

# 89. RBAC Verification

Verify the database role:

```bash id="q4m7x2"
sudo docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
row = db.execute(
    "SELECT id, username, enabled, role FROM users ORDER BY id"
).fetchall()

for item in row:
    print(item)
'
```

The production administrator should report:

```text id="m2x8v5"
role = administrator
```

The application test suite contains dedicated RBAC coverage.

The current RBAC test result is:

```text id="n7k4p2"
20 passed
```

The complete current test suite contains:

```text id="c8m5q1"
79 passed
```

The production deployment has also been verified to contain the RBAC implementation and migrated administrator role.

---

# 90. Security Audit Status

The LUMS security audit is organized into the following areas:

```text id="w2q6m9"
01 SQLite Foreign Keys
02 SQLite WAL / Busy Timeout
03 Update Timeout / Process Handling
04 Login Rate Limiting
05 API Input Validation
06 Session Revocation
07 Token Rotation
08 get_ip / Offline Networks
09 Job Recovery / Checkpointing
10 APT Robustness
11 Arch Reboot Detection
12 Unit Tests / API Result Validation
13 Simulation Tests
14 CI
15 Application Logging
16 Versioning / Releases
17 RBAC
18 Complete Documentation
```

Audit items:

```text id="9x4m7k"
01  ✓
02  ✓
03  ✓
04  ✓
05  ✓
06  ✓
07  ✓
08  ✓
09  ✓
10  ✓
11  ✓
12  ✓
13  ✓
14  ✓
15  ✓
16  ✓ audited / implementation pending
17  ✓
18  in progress
```

The documentation audit is the current final audit phase.

---

# 91. SQLite Security

The current SQLite configuration includes:

```text id="v5m8q2"
foreign_keys = ON
busy_timeout = 5000
journal_mode = WAL
synchronous = 2
```

Foreign-key enforcement is explicitly enabled by the application connection setup.

The busy timeout reduces immediate failures caused by short-lived concurrent access.

WAL mode improves concurrent read/write behavior compared with the previous configuration.

SQLite remains intentionally lightweight.

The current design is appropriate for the intended LUMS deployment model.

It is not intended to be treated as a high-scale multi-node database architecture.

---

# 92. Authentication Security

Administrative passwords are stored using Argon2 hashing.

The application also provides:

```text id="h7m3q9"
login rate limiting
session handling
session revocation
CSRF protection
security headers
```

Failed authentication attempts are recorded through the application audit mechanism where appropriate.

Successful authentication is also recorded.

Logout events are auditable.

Authentication and authorization remain separate controls.

---

# 93. Client Token Security

Client tokens are stored server-side as SHA-256 digests rather than plaintext credentials.

The lifecycle is:

```text id="p8q4m1"
generate
   ↓
present to administrator/client
   ↓
hash
   ↓
store digest
   ↓
authenticate
   ↓
rotate
   ↓
invalidate old token
```

A rotated token replaces the previous credential.

The previous token must no longer authenticate.

Client tokens must never be placed in Git or ordinary application logs.

---

# 94. Security Audit Implementation Summary

The completed audit items cover:

```text id="q7m4x2"
database integrity
database concurrency
process timeout handling
authentication rate limiting
API input validation
session revocation
token rotation
network/IP handling
job recovery
APT error handling
Arch reboot detection
automated testing
simulation testing
continuous integration
application logging
RBAC
```

Audit #16 has been reviewed.

The current project does not yet have:

```text id="f5n8r2"
stable release tag
GitHub Release
final release version
```

The release/versioning strategy has therefore been audited but is intentionally not presented as implemented.

The project remains in active development.

---

# 95. Application Logging

The server uses Python application logging for operational events.

The application logger is configured with:

```text id="k4m7x9"
INFO
```

and emits timestamped messages.

Important application events include:

```text id="m6q2p8"
client reports
update job creation
update job claiming
```

Gunicorn access and error logs are also emitted to the Docker log stream.

View application/runtime logs with:

```bash id="v9q3m1"
sudo docker logs \
    --tail 100 \
    lums
```

Follow them with:

```bash id="x5n8k2"
sudo docker logs \
    -f \
    lums
```

Application logs and audit records serve different purposes.

Application logs describe runtime behavior.

Audit records describe security-relevant administrative events.

---

# 96. Audit Logging

LUMS maintains a dedicated audit log for security-relevant actions.

The audit mechanism records information such as:

```text id="r8m3q5"
actor type
actor identity
action
target
result
details
timestamp
```

Examples include:

```text id="n2k7v4"
login success
login failure
login rate-limit events
logout
client creation
client token rotation
client disable/delete operations
```

Audit details must never contain secrets.

The audit log should therefore be considered security metadata rather than a general application debug log.

---

# 97. Logging Diagnostics

When investigating a server-side issue, start with:

```bash id="p7m4x1"
sudo docker logs \
    --tail 100 \
    lums
```

For a live incident:

```bash id="c6q8m3"
sudo docker logs \
    -f \
    lums
```

For client-side execution:

```bash id="h4n7q2"
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

For the Execution Watcher:

```bash id="w8m2k5"
sudo journalctl \
    -u lums-agent-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

The diagnostic sequence should be:

```text id="v3q7m1"
server
  ↓
agent
  ↓
watcher
  ↓
job
  ↓
package manager
```

Do not change all layers simultaneously.

Identify the failing layer first.

---

# 98. Automated Tests

The project contains automated unit and integration-oriented tests for important application behavior.

Current test areas include:

```text id="n4k8p2"
security
authentication
authorization
RBAC
job handling
API validation
package manager behavior
recovery
simulation
```

The current complete test result is:

```text id="m7q3x5"
79 passed
```

The test suite is executed with:

```bash id="j5n8q2"
python -m pytest -q
```

A clean test run is required before treating a code change as ready for integration.

Tests are especially important after changes to:

```text id="r6m2v8"
security.py
app.py
database handling
job handling
package_manager.py
agent.py
watcher.py
```

---

# 99. Simulation Tests

Simulation tests ensure that update-job handling can be exercised without invoking real package-management operations.

The tests cover:

```text id="q8m4x2"
UPDATE_PACKAGE
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_SYSTEM
unknown action
```

The tests explicitly protect against accidental execution of the real package-manager commands.

Simulation therefore provides a safe regression layer for job dispatch and result handling.

A successful simulation test does not prove that a real package update will succeed.

It proves that the LUMS execution path can process the corresponding job type without invoking the real package operation.

---

# 100. Continuous Integration

The project uses GitHub Actions for automated testing.

The workflow is:

```text id="v4m7q2"
.github/workflows/tests.yml
```

The workflow runs for:

```text id="m8q3x5"
push → main
pull request → main
```

The workflow:

```text id="q6n2k8"
checkout
   ↓
Python 3.13
   ↓
install test dependencies
   ↓
pytest
```

The workflow has:

```yaml id="f3m8q1"
permissions:
  contents: read
```

The purpose of CI is to prevent changes from silently bypassing the automated test suite.

Local tests and CI therefore form two complementary verification layers:

```text id="j7q4m2"
local development
      ↓
pytest
      ↓
Git commit
      ↓
GitHub
      ↓
CI
```

# 101. Database Backup

The LUMS database is stored in the persistent Docker volume:

```text id="f7m2q8"
/var/lib/lums/lums.db
```

Before performing major application, database or security changes, create a backup.

A SQLite online backup can be created without replacing the live database:

```bash id="k4n8p2"
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    ".backup '/tmp/lums-backup.db'"
```

If the container image does not provide the `sqlite3` command, use an external SQLite backup method instead.

The important principle is:

```text id="q8m3v5"
live database
      ↓
consistent backup
      ↓
verify backup
      ↓
make change
```

The backup must not be treated as valid merely because the command completed.

It should also be checked for integrity.

---

# 102. Database Integrity

SQLite integrity can be checked with:

```bash id="n5q7m2"
sudo docker exec lums \
    python3 -c '
import sqlite3
db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
'
```

Expected:

```text id="x3m8q4"
ok
```

An integrity result other than:

```text id="p7k2v9"
ok
```

requires investigation before further administrative changes are made.

The integrity check should be performed after:

* database restoration
* migration testing
* major schema changes
* unexpected application termination
* suspected storage problems

---

# 103. Database Restore

Database restoration is a controlled administrative operation.

The general procedure is:

```text id="m8q4x2"
stop application writes
       ↓
preserve current database
       ↓
restore verified backup
       ↓
run integrity check
       ↓
start application
       ↓
verify migrations
       ↓
verify authentication
       ↓
verify clients
       ↓
verify jobs/history
```

Never overwrite the current database before preserving the existing state.

A failed restore should therefore remain reversible.

A complete isolated restore test is a separate validation activity and must not be represented as completed unless it has actually been performed.

---

# 104. Database Migrations

LUMS uses versioned security/application migrations.

Current verified migration identifiers include:

```text id="w3m7q2"
001-security-foundation
002-rbac
```

The migration mechanism records applied migrations and avoids reapplying migrations that have already been completed.

The RBAC migration adds:

```text id="q5n8m3"
users.role
```

with:

```text id="v2k7x4"
administrator
```

as the default role.

Before applying a migration to an important installation:

```text id="r8m4q1"
backup
  ↓
migration
  ↓
integrity check
  ↓
application startup
  ↓
functional verification
```

Do not manually modify migration history unless the consequences are fully understood.

---

# 105. Migration Verification

Check the migration table through SQLite:

```bash id="k7m3x9"
sudo docker exec lums \
    python3 -c '
import sqlite3
db = sqlite3.connect("/var/lib/lums/lums.db")
for row in db.execute("SELECT * FROM schema_migrations ORDER BY 1"):
    print(row)
'
```

The exact table layout should be interpreted according to the current application schema.

The important administrative requirement is that already-applied migrations are recorded and not repeatedly executed.

After a migration, verify:

```text id="p4n8v2"
database integrity
application startup
administrator login
role assignment
client reporting
job handling
```

---

# 106. Production Deployment Baseline

The current production baseline is:

```text id="q8m5x1"
Docker
Python 3.13
Gunicorn 23.0.0
Flask
SQLite
Nginx
HTTPS
```

The LUMS container runs:

```text id="m7k3v9"
non-root user
read-only root filesystem
all Linux capabilities dropped
non-privileged container
/tmp as restricted tmpfs
localhost-only host binding
file-based application secret
persistent Docker volume
```

The current application image is:

```text id="x4n8q2"
lums:latest
```

The persistent application database is:

```text id="v6m3k8"
lums-data:/var/lib/lums
```

This baseline should be preserved when rebuilding or recreating the production container.

---

# 107. Production Network Baseline

The application container is not intended to be directly reachable from the LAN.

The host-side binding is:

```text id="m8q4v2"
127.0.0.1:5050
```

Nginx provides the external HTTPS endpoint.

The intended traffic flow is:

```text id="n5k7x3"
LAN / Client
      |
      | HTTPS
      v
Nginx :443
      |
      | HTTP localhost
      v
127.0.0.1:5050
      |
      v
Docker :5000
      |
      v
Gunicorn
```

This limits direct exposure of the application server.

Verify the binding with:

```bash id="q3m8v6"
sudo docker port lums
```

and:

```bash id="x7k4n2"
sudo ss -lntp | grep -E ':443|:5050'
```

The expected application binding remains localhost-only.

---

# 108. Production Security Baseline

The current security baseline includes:

```text id="p6m3q8"
TLS
secure authentication
Argon2 password hashing
login rate limiting
session revocation
CSRF protection
security headers
client Bearer authentication
SHA-256 client-token digests
token rotation
API input validation
client/job ownership checks
atomic job claiming
job recovery
execution timeout handling
APT failure handling
Arch reboot detection
RBAC
application logging
audit logging
container hardening
automated tests
CI
```

The baseline is the result of the completed security audit items #01–#17.

Documentation is the remaining audit area:

```text id="k8q4m2"
Audit #18 — Complete Documentation
```

---

# 109. Operational Verification

After major production changes, perform a short operational verification.

Recommended sequence:

```text id="v4m7x2"
1. Container running
2. Database integrity
3. Nginx running
4. HTTPS reachable
5. Login works
6. Administrator role correct
7. Client reports successfully
8. Package inventory visible
9. Updates visible
10. Job creation works
11. Agent receives job
12. Watcher operates
13. Job result recorded
14. History updated
15. Logs contain expected events
```

For security-sensitive changes, additionally verify:

```text id="m5q8x3"
token authentication
role authorization
session behavior
container hardening
secret availability
```

Do not consider a deployment complete merely because the container reports:

```text id="x2k7v4"
Up
```

The application and operational path must also be verified.

---

# 110. Incident Evidence Preservation

When investigating an unexpected failure, preserve evidence before destructive actions.

Useful information includes:

```bash id="q8m4v1"
sudo docker ps -a
sudo docker inspect lums
sudo docker logs --tail 200 lums
sudo journalctl -u lums-agent.service --since "1 hour ago" --no-pager
sudo journalctl -u lums-agent-watcher.service --since "1 hour ago" --no-pager
```

For the database:

```bash id="n7k3x5"
sudo docker exec lums \
    python3 -c '
import sqlite3
db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
'
```

Do not immediately:

```text id="m4q8v2"
delete the container
delete the volume
delete the database
delete logs
rotate credentials
reinstall the agent
```

unless the operational situation requires it and sufficient evidence has already been preserved.

The diagnostic principle remains:

```text id="x5n8q3"
observe
   ↓
identify
   ↓
reproduce
   ↓
change
   ↓
test
   ↓
verify
```

---

# 111. Version and Release Status

The project is currently under active development.

The current component versions are:

```text id="v7m3q8"
LUMS Agent: 1.7.0
Execution Watcher: 1.2.1
```

The project currently has:

```text id="k4n8x2"
CI workflow
automated tests
security audit
RBAC
application logging
```

However, the project does not currently have:

```text id="q6m3v9"
stable release
Git tag
GitHub Release
final project version
```

Audit #16 therefore documents the versioning/release situation without prematurely declaring a release.

The absence of a release is intentional while development and documentation continue.

---

# 112. Release Preparation

A future release should only be created after the project reaches the desired development state.

The expected release process can later include:

```text id="m8q4x1"
final implementation
       ↓
security review
       ↓
documentation review
       ↓
full test suite
       ↓
CI
       ↓
version assignment
       ↓
Git tag
       ↓
GitHub Release
```

No final release version is defined in this administration guide yet.

The current document therefore describes the operational state rather than inventing a release number.

---

# 113. Current Audit Baseline

The complete security audit currently stands at:

| Audit | Area                               |    Status   |
| ----- | ---------------------------------- | :---------: |
| #01   | SQLite Foreign Keys                |      ✓      |
| #02   | SQLite WAL / Busy Timeout          |      ✓      |
| #03   | Update Timeout / Process Handling  |      ✓      |
| #04   | Login Rate Limiting                |      ✓      |
| #05   | API Input Validation               |      ✓      |
| #06   | Session Revocation                 |      ✓      |
| #07   | Token Rotation                     |      ✓      |
| #08   | get_ip / Offline Networks          |      ✓      |
| #09   | Job Recovery / Checkpointing       |      ✓      |
| #10   | APT Robustness                     |      ✓      |
| #11   | Arch Reboot Detection              |      ✓      |
| #12   | Unit Tests / API Result Validation |      ✓      |
| #13   | Simulation Tests                   |      ✓      |
| #14   | CI                                 |      ✓      |
| #15   | Application Logging                |      ✓      |
| #16   | Versioning / Releases              |  ✓ audited  |
| #17   | RBAC                               |      ✓      |
| #18   | Complete Documentation             | in progress |

Audit #16 is intentionally marked as:

```text id="v5m8q2"
audited
```

rather than:

```text id="p7k3x4"
release implemented
```

because the project has not yet created a release/tag.

---

# 114. Documentation Baseline

The administration guide should remain consistent with:

```text id="q8m4v2"
README.md
docs/security.md
docs/install.md
docs/troubleshooting.md
```

The documentation must use the same terminology for:

```text id="n6k3x8"
Agent
Execution Watcher
client token
update job
RBAC
administrator
operator
viewer
simulation
recovery
audit
```

The following must not reappear as current project state:

```text id="m4q8v1"
RBAC not implemented
only Audit #01–#04 completed
Watcher under an obsolete name
no automated tests
no CI
no application logging
```

Those statements describe earlier development stages and are no longer the current baseline.

---

# 115. Administrative Roles — Final Summary

The current administrative model is:

```text id="x7m3q8"
                    LUMS
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
   Administrator   Operator    Viewer
          |           |           |
          |           |           |
       Full        Operations   Read-only
       access       access      access
```

Administrator:

```text id="q4n8m2"
identity management
client management
token management
update management
read access
```

Operator:

```text id="m7k3x1"
update management
read access
```

Viewer:

```text id="v8q4n5"
read access
```

The role system is implemented server-side.

It is not merely a frontend visibility mechanism.

Authorization is enforced by the backend.

---

# 116. Administrative Security Principle

Administrative access should follow least privilege.

The intended model is:

```text id="k5m8q2"
need to observe
    ↓
Viewer

need to operate updates
    ↓
Operator

need to administer identities and infrastructure
    ↓
Administrator
```

Roles should not be granted based solely on convenience.

If an account only needs monitoring access, it should not require administrative privileges.

If an account performs update operations but does not manage identities, Operator is the corresponding role.

---

# 117. Client Security Principle

Managed clients are treated as independently authenticated execution nodes.

The server must never rely solely on:

```text id="x3m7q8"
IP address
hostname
network location
```

for client identity.

Client authentication is based on the client-specific Bearer token.

Job operations additionally verify client/job ownership.

This creates the security boundary:

```text id="q8m4v1"
network location
      +
client credential
      +
server-side ownership
```

rather than trusting network position alone.

---

# 118. Operational Safety Principle

LUMS is designed to avoid blind execution.

Important controls include:

```text id="m5q8x2"
authentication
authorization
idle detection
job ownership
atomic claiming
timeouts
checkpointing
recovery
result validation
history
audit logging
```

The intended operational flow is:

```text id="v7k3m9"
request
  ↓
validate
  ↓
authorize
  ↓
create job
  ↓
claim atomically
  ↓
verify execution conditions
  ↓
execute
  ↓
report
  ↓
validate result
  ↓
record history
```

Each stage provides an opportunity to detect an invalid or unexpected state.

---

# 119. Administration Philosophy

LUMS administration should follow a controlled-change process.

For significant changes:

```text id="q4m8x2"
backup
   ↓
inspect
   ↓
change
   ↓
test
   ↓
verify
   ↓
document
```

For security-sensitive changes:

```text id="m7n3v8"
backup
   ↓
security impact
   ↓
implementation
   ↓
automated tests
   ↓
deployment
   ↓
runtime verification
   ↓
audit/documentation
```

This is especially important for:

* authentication
* authorization
* tokens
* database migrations
* container hardening
* package execution
* recovery behavior
* TLS configuration

---

# 120. Final Architecture

The current LUMS architecture can be summarized as:

```text id="x8m4q2"
                         Administrator
                              |
                              | HTTPS
                              v
                       +--------------+
                       |    Nginx     |
                       | TLS / Proxy  |
                       +------+-------+
                              |
                              v
                       +--------------+
                       | Docker LUMS  |
                       |              |
                       | Gunicorn     |
                       | Flask        |
                       | RBAC         |
                       | API          |
                       +------+-------+
                              |
                    +---------+---------+
                    |                   |
                    v                   v
              +-----------+       +-----------+
              | SQLite    |       | Audit /   |
              | lums.db   |       | Logging   |
              +-----------+       +-----------+
                    |
                    |
          Persistent Docker Volume
                    |
                    v
                lums-data


       HTTPS / Bearer Authentication
                    ^
                    |
          +---------+---------+
          |                   |
          v                   v
    Debian Client        Arch Client
          |                   |
       Agent 1.7.0         Agent 1.7.0
          |                   |
      APT / dpkg             pacman
          |                   |
          +---------+---------+
                    |
             Execution Watcher
                1.2.1
                    |
                    v
             Job execution
             recovery
             monitoring
```

The administrative security model is:

```text id="m6q3v8"
Administrator
     |
     +-- full administrative access

Operator
     |
     +-- operational update access

Viewer
     |
     +-- read-only access
```

The client security model is:

```text id="q8m4x2"
Client
   |
   +-- Bearer token
   |
   +-- client identity
   |
   +-- job ownership
   |
   +-- result ownership
   |
   +-- recovery ownership
```

The operational model is:

```text id="v4m7x1"
Report
  ↓
Inventory
  ↓
Updates
  ↓
Job
  ↓
Claim
  ↓
Idle Check
  ↓
Execute
  ↓
Checkpoint
  ↓
Result
  ↓
History
  ↓
Recovery if required
```

The security model is:

```text id="n8q3m5"
Authenticate
     ↓
Authorize
     ↓
Validate
     ↓
Execute
     ↓
Record
     ↓
Verify
```

And the administrative principle remains:

> **Observe first. Change deliberately. Test everything. Verify the result.**

LUMS is currently an actively developed project with the major security audit items #01–#17 completed or audited, while the final documentation audit (#18) is being completed.

The system is functional, tested and hardened, but it is not yet represented as a final stable release.

