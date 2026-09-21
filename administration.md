# LUMS — Administration Guide

## Linux Update Management Server

**Version:** 2.4

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

# 2. Architecture

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
                    Linux Package Manager
```

The application itself is not directly exposed to the network.

Docker publishes the application only on localhost:

```text
127.0.0.1:5050 -> container:5000
```

Nginx provides the externally accessible HTTPS endpoint.

The current application server is:

```text
Gunicorn 23.0.0
```

The Flask development server is not used for the current production deployment.

---

# 3. Current Runtime Configuration

## 3.1 Repository

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

# 4. Important Paths

## 4.1 Application source

```text
/opt/lums-public
```

## 4.2 Docker configuration

```text
/etc/lums/docker/lums.env
```

## 4.3 Flask secret

```text
/etc/lums/secrets/lums_secret
```

The Flask secret is deliberately stored separately from the normal Docker environment file.

## 4.4 TLS

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

## 4.5 Database

Inside the container:

```text
/var/lib/lums/lums.db
```

Persistent storage:

```text
lums-data
```

## 4.6 Agent

```text
/opt/lums-agent/agent.py
/opt/lums-agent/watcher.py
/opt/lums-agent/lums-ca.crt
/etc/default/lums-agent
```

Do not place private keys, tokens, passwords or environment secrets inside Git.

---

# 5. Frontend Structure

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

The frontend is served by the Flask application and becomes part of the Docker image during deployment.

---

# 6. Theme System

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

# 7. Theme Administration

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

# 8. Enterprise Admin Theme

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

The Enterprise Admin theme is deliberately separated from the other themes.

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

# 9. Geek Network Visualization

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

# 10. Nerd Theme

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

# 11. Docker Administration

## 11.1 Check container

```bash
sudo docker ps
```

Expected container:

```text
lums
```

---

## 11.2 Check all containers

```bash
sudo docker ps -a
```

---

## 11.3 Inspect container

```bash
sudo docker inspect lums
```

---

## 11.4 Check container status

```bash
sudo docker inspect \
    -f '{{.State.Status}}' \
    lums
```

---

## 11.5 Check container restart policy

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

# 12. Container Security State

The current production container is hardened.

Expected properties:

```text
User:
    lums

UID:
    10001

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

This hardened configuration must be preserved during container recreation.

---

# 13. Docker Image

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

The image contains:

* Flask application
* Gunicorn
* frontend assets
* database initialization code
* Docker entrypoint
* theme assets
* application dependencies

---

# 14. Container Startup

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

The entrypoint runs:

```text
python3 /app/server/init_db.py
```

before starting Gunicorn.

The current Gunicorn configuration uses:

```text
2 workers
2 threads
120 second timeout
```

The Flask development server is not used.

---

# 15. Container Recreation

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

The hardened options are not optional in the current production deployment.

---

# 16. Critical Docker Rule

Never remove the persistent database volume as part of a normal application deployment.

The following command is destructive:

```bash
sudo docker volume rm lums-data
```

It removes persistent application data.

Do not execute it unless a complete reset is explicitly intended and a verified backup exists.

---

# 17. Docker Logs

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

# 18. Secret Administration

The Flask application secret is stored outside the normal environment file.

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

The normal environment must not contain:

```text
LUMS_SECRET_KEY=<secret>
```

---

# 19. Secret File Permissions

The secret directory should be:

```text
root:root
0700
```

The secret file should be readable by the container's UID/GID:

```text
root:10001
0640
```

Check:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/secrets/lums_secret
```

Expected:

```text
root:lums 640 /etc/lums/secrets/lums_secret
```

Never display the secret itself.

---

# 20. Secret Verification

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

# 21. Flask Secret Rotation

The production Flask secret has been rotated and verified.

A future rotation should be treated as a controlled security change.

Before rotation:

1. Verify the database is healthy.
2. Create a database backup.
3. Verify the backup.
4. Generate a replacement secret.
5. Replace the protected secret file.
6. Restart the LUMS container.
7. Verify Gunicorn startup.
8. Verify HTTPS.
9. Verify authentication.
10. Confirm old sessions are invalidated.

Changing the Flask secret invalidates existing Flask sessions.

Do not perform a secret rotation casually during an active administrative session.

Never record the old or new secret in documentation or logs.

---

# 22. Nginx Administration

Nginx provides the external HTTPS endpoint.

The architecture is:

```text
Internet / LAN Client
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

# 23. Nginx Configuration Test

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

# 24. Nginx Logs

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

# 25. Network and Health Checks

## 25.1 Check local application binding

```bash
sudo ss -lntp | grep ':5050'
```

Expected:

```text
127.0.0.1:5050
```

Port `5000` should not be directly exposed by the host.

---

## 25.2 Test local application endpoint

```bash
curl -I \
    http://127.0.0.1:5050/
```

Expected behavior:

```text
HTTP/1.1 302 FOUND
Location: /login
```

---

## 25.3 Test HTTPS endpoint

Use the configured LUMS hostname:

```bash
curl -kI \
    https://<LUMS_HOST>/
```

The `-k` option is intended only for controlled certificate diagnostics.

It must not replace proper certificate trust in production automation.

---

# 26. TLS Administration

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

# 27. TLS Protocols

The current Nginx configuration permits:

```text
TLS 1.2
TLS 1.3
```

Older TLS protocol versions must remain disabled.

Verify the effective configuration:

```bash
sudo nginx -T | grep -n \
    'ssl_protocols'
```

Expected:

```text
ssl_protocols TLSv1.2 TLSv1.3;
```

---

# 28. Security Headers

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

# 29. Server Environment

The Docker environment file is:

```text
/etc/lums/docker/lums.env
```

It must not contain the production Flask secret.

Use placeholders when documenting environment values:

```text
LUMS_BASE=https://<LUMS_HOST>
LUMS_TOKEN=<CLIENT_TOKEN>
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

Never place actual credentials into documentation.

---

# 30. Agent Configuration

The agent is installed outside the Docker container.

Current paths include:

```text
/opt/lums-agent/agent.py
/opt/lums-agent/watcher.py
/opt/lums-agent/lums-ca.crt
/etc/default/lums-agent
```

A documented example should use:

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

---

# 31. Agent Authentication

The current LUMS implementation authenticates clients using Bearer tokens.

The HTTP header is:

```text
Authorization: Bearer <CLIENT_TOKEN>
```

The server:

1. extracts the Bearer token,
2. hashes the presented token,
3. looks up the client,
4. verifies that the client is enabled,
5. checks token revocation state,
6. authenticates the request.

The current database representation is a SHA-256 hexadecimal digest.

This is a token authentication representation.

It must not be described as password hashing.

---

# 32. Client Authorization

Authentication alone is not sufficient.

Client-specific operations are additionally scoped to the authenticated client identity.

For example:

```text
Client A
   |
   +-- can access Client A operations

Client B
   |
   +-- can access Client B operations
```

A client must not be able to access another client's jobs simply by changing a client ID in the URL.

Job ownership is verified server-side.

---

# 33. Client Token Rotation

Administrators can rotate a client token through the LUMS frontend.

The client page provides:

```text
🔐 Token rotieren
```

The operation requires:

```text
Authenticated administrator session
+
CSRF validation
```

The backend endpoint is:

```text
POST /api/clients/<client_id>/token/rotate
```

The rotation process:

```text
Existing token
      |
      v
Generate replacement
      |
      v
Store replacement hash
      |
      v
Previous token invalid
      |
      v
Return new token once
      |
      v
Update client agent
      |
      v
Verify communication
```

The plaintext replacement token is not written to the audit log.

---

# 34. Client Token Rotation Procedure

When rotating a production client token:

1. Open the client page.
2. Verify that the correct client is selected.
3. Select:

```text
🔐 Token rotieren
```

4. Confirm the operation.
5. Copy or securely store the new token.
6. Update the client's `/etc/default/lums-agent`.
7. Restart or manually execute the agent.
8. Verify successful authentication.
9. Verify that the client reports again.
10. Confirm the client is online in LUMS.

The previous token becomes invalid immediately.

Do not close the change before verifying the replacement token.

---

# 35. Token Rotation Verification

A successful rotation should produce:

```text
Old token
    |
    +--> 401

New token
    |
    +--> authenticated
```

The rotation audit event should contain:

```text
client.token.rotate
```

but must not contain the plaintext token.

The production client communication workflow has been successfully verified after token replacement.

---

# 36. Agent Service

Check the service:

```bash
sudo systemctl status lums-agent.service --no-pager
```

Run manually:

```bash
sudo systemctl start lums-agent.service
```

Check the result:

```bash
sudo systemctl status lums-agent.service --no-pager
```

View logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 37. Agent Timer

The installed systemd timer is authoritative.

Check:

```bash
systemctl list-timers --all | grep lums-agent
```

Inspect:

```bash
sudo systemctl cat lums-agent.timer
```

Check status:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Do not assume a timer interval from documentation when the installed unit can be inspected directly.

---

# 38. Execution Watcher

The execution watcher monitors update execution and related job state.

Current file:

```text
/opt/lums-agent/watcher.py
```

Systemd units:

```text
lums-execution-watcher.service
lums-execution-watcher.timer
```

Check:

```bash
sudo systemctl status \
    lums-execution-watcher.service \
    --no-pager
```

Check timer:

```bash
sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager
```

Inspect:

```bash
sudo systemctl cat \
    lums-execution-watcher.timer
```

List:

```bash
systemctl list-timers --all | grep lums
```

---

# 39. Execution Watcher Logs

View:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --no-pager \
    -n 100
```

Follow:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -f
```

---

# 40. Idle-Aware Execution

LUMS can use system activity information when determining whether controlled execution should take place.

The current implementation uses:

```text
w -h
```

for the relevant server/terminal/SSH-oriented activity detection.

This is not universal desktop idle detection.

When diagnosing unexpected execution behavior, inspect:

```text
idle
idle_seconds
idle_threshold_seconds
idle_source
idle_supported
```

The current default idle threshold is:

```text
300 seconds
```

Idle detection should not be interpreted as a security boundary.

It is an execution policy signal.

---

# 41. Update Job Lifecycle

A typical LUMS update workflow is:

```text
Client reports
      |
      v
LUMS records client state
      |
      v
Administrator creates update job
      |
      v
Job enters pending
      |
      v
Client claims job
      |
      v
Client executes operation
      |
      v
Client submits result
      |
      v
LUMS records result
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

The database is the authoritative application state.

---

# 42. Job Claiming

The client-side execution workflow uses the LUMS API to obtain work assigned to the authenticated client.

Typical flow:

```text
GET pending work
        |
        v
claim job
        |
        v
execute job
        |
        v
submit result
```

Job claiming is atomic.

The client must not execute a job merely because it appeared in a pending list.

The server verifies that the authenticated client is authorized for the requested job.

---

# 43. Job Result Reporting

After execution, the client reports the result back to LUMS.

A result contains the information required by the server to determine the outcome of the requested operation.

Typical information includes:

* job identifier
* client identity
* execution state
* result information
* timestamps
* package information
* reboot requirement where applicable

Never insert fabricated success information into the database simply to make the dashboard appear healthy.

---

# 44. Interrupted Job Recovery

A running job can become interrupted because of:

* client shutdown
* power loss
* watcher interruption
* network failure
* operating system restart
* package manager failure
* failed result submission

LUMS provides a controlled recovery operation:

```text
POST /api/update-jobs/<job_id>/abandon
```

The operation requires authenticated client access.

The server verifies:

1. The job exists.
2. The authenticated client owns the job.
3. The job is currently `running`.
4. The state transition has not already happened.

The job is then changed to:

```text
abandoned
```

and:

* `finished_at` is recorded.
* `recovery_reason` is recorded.
* `update_history` is written.
* package statistics are preserved.
* reboot state is preserved.

The current recovery reason is:

```text
Agent did not submit a final result.
```

---

# 45. Agent Recovery Behavior

When the agent starts and finds a running job, it attempts recovery.

The intended sequence is:

```text
Existing running job
        |
        v
Attempt abandon/recovery
        |
        +---- failure ---> stop
        |
        v
Recovery successful
        |
        v
Check pending jobs
        |
        v
Continue normally
```

The agent must not blindly claim another job if recovery fails.

This prevents an unresolved previous job from being silently ignored.

---

# 46. Job Recovery Verification

A controlled recovery test was performed using an artificial running job.

Verified:

```text
status:
    abandoned

finished_at:
    populated

recovery_reason:
    Agent did not submit a final result.

update_history:
    abandoned

package count:
    preserved

successful:
    0

failed:
    0
```

The artificial test data was removed after verification.

A normal real update job subsequently completed successfully.

The recovery mechanism is therefore part of the currently verified LUMS functionality.

---

# 47. Simulation Mode

LUMS supports simulation behavior for controlled update testing.

The relevant environment variable is:

```text
LUMS_SIMULATE_UPDATES
```

Simulation mode can be used for:

* development
* job lifecycle testing
* frontend testing
* agent testing
* deployment validation
* troubleshooting

Before real update execution, verify that simulation mode is not unintentionally enabled.

Temporary runtime configuration should be removed after testing.

---

# 48. Package Manager Safety

LUMS does not replace the Linux package manager.

The underlying package manager remains responsible for:

* dependency resolution
* package installation
* package removal
* package configuration
* repository interaction
* transaction execution

LUMS provides centralized orchestration and visibility.

The update execution layer remains a privileged infrastructure component.

Complete package manager collision prevention is still an area for further hardening.

In particular, LUMS must not assume that an internal application lock automatically prevents arbitrary external APT or dpkg commands.

---

# 49. Database Administration

The application database is:

```text
/var/lib/lums/lums.db
```

inside the container.

Persistent storage is provided through:

```text
lums-data
```

Check the volume:

```bash
sudo docker volume inspect lums-data
```

---

# 50. Accessing the Database

The database can be inspected from inside the running container.

Example:

```bash
sudo docker exec -it lums \
    sqlite3 /var/lib/lums/lums.db
```

Useful SQLite commands:

```sql
.tables
.schema
.quit
```

Always prefer application-level operations for normal administration.

Direct database modifications should be reserved for controlled recovery or maintenance.

---

# 51. Database Integrity Check

Run:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

A successful integrity check confirms SQLite consistency.

It does not by itself confirm that every application-level object is logically correct.

---

# 52. Database Backup

The database is persistent application state and must be backed up.

Create the backup directory:

```bash
sudo mkdir -p /var/backups/lums
sudo chmod 700 /var/backups/lums
```

Use a SQLite-aware backup:

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

Protect the backup:

```bash
sudo chmod 600 \
    /var/backups/lums/lums.db.backup
```

---

# 53. Timestamped Database Backup

For operational backups:

```bash
BACKUP="/var/backups/lums/lums-$(date +%F-%H%M%S).db"

sudo docker run --rm \
    --entrypoint python3 \
    -v lums-data:/var/lib/lums:ro \
    -v /var/backups/lums:/backup \
    lums:latest \
    -c "
import sqlite3

source = sqlite3.connect('/var/lib/lums/lums.db')
target = sqlite3.connect('/backup/$(basename "$BACKUP")')

with target:
    source.backup(target)

target.close()
source.close()

print('SQLite backup completed')
"
```

Protect it:

```bash
sudo chmod 600 "$BACKUP"
```

Verify:

```bash
sudo ls -lh "$BACKUP"
```

---

# 54. Backup Verification

A backup must be tested.

Run:

```bash
sqlite3 \
    /var/backups/lums/<BACKUP_FILE>.db \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

Alternatively, use the LUMS image:

```bash
sudo docker run --rm \
    -v /var/backups/lums:/backup:ro \
    lums:latest \
    python3 -c '
import sqlite3

db = sqlite3.connect(
    "file:/backup/<BACKUP_FILE>.db?mode=ro",
    uri=True
)

print(db.execute("PRAGMA integrity_check").fetchone()[0])

db.close()
'
```

A successful integrity check confirms that SQLite can read the backup.

A full restore test remains a separate validation requirement.

---

# 55. Full Database Restore

Before restoring:

1. Confirm the backup.
2. Verify its integrity.
3. Stop the application.
4. Preserve the current database.
5. Restore the backup.
6. Start LUMS.
7. Verify logs.
8. Verify authentication.
9. Verify clients.
10. Verify jobs.
11. Verify HTTPS.

Stop:

```bash
sudo docker stop lums
```

Create a safety copy before replacing the database.

Do not overwrite the production database blindly.

A complete isolated restore test remains outstanding.

---

# 56. Git Administration

The Git repository is:

```text
/opt/lums-public
```

Check status:

```bash
cd /opt/lums-public

git status -sb
```

Fetch:

```bash
git fetch origin
```

Recent commits:

```bash
git log --oneline --decorate -5
```

Remote:

```bash
git remote -v
```

---

# 57. Git Identity

The LUMS repository uses:

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

# 58. Git Deployment Workflow

A normal source update should follow:

```text
Git
 |
 v
Fetch
 |
 v
Review
 |
 v
Pull
 |
 v
Inspect
 |
 v
Build
 |
 v
Backup
 |
 v
Recreate
 |
 v
Validate
```

Example:

```bash
cd /opt/lums-public

git fetch origin

git status -sb

git log --oneline --decorate -5

git diff --check
```

Only after reviewing the changes:

```bash
git pull --ff-only origin main
```

Then:

```bash
sudo docker build \
    -t lums:latest \
    .
```

---

# 59. Production Deployment

Before replacing the running production container:

## 59.1 Check source

```bash
cd /opt/lums-public

git status -sb
git diff --check
```

## 59.2 Create database backup

Use the SQLite-aware backup procedure from section 52.

## 59.3 Verify backup

Run:

```bash
sqlite3 \
    /var/backups/lums/<BACKUP_FILE>.db \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

## 59.4 Build image

```bash
sudo docker build \
    -t lums:latest \
    .
```

## 59.5 Recreate container

Use the hardened command:

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

---

# 60. Post-Deployment Validation

After deployment:

```bash
sudo docker ps
```

Then:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Verify hardening:

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

Verify secret configuration:

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

# 61. Database Post-Deployment Check

Run:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

Check application tables:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    '.tables'
```

---

# 62. Nginx Post-Deployment Check

Run:

```bash
sudo nginx -t
```

Then:

```bash
sudo systemctl reload nginx
```

Check:

```bash
sudo systemctl status nginx --no-pager
```

---

# 63. HTTPS Post-Deployment Check

```bash
curl -k -I \
    https://<LUMS_HOST>/
```

Expected behavior:

```text
HTTP/1.1 302 FOUND
Location: /login
```

Security headers should still be present.

---

# 64. Unauthenticated API Check

A protected client endpoint should reject unauthenticated access.

Example:

```bash
curl -k -i \
    https://<LUMS_HOST>/api/clients
```

Expected:

```text
HTTP/1.1 401 UNAUTHORIZED
```

This confirms that administrative API access is not anonymously exposed.

---

# 65. Agent Post-Deployment Check

On the client:

```bash
sudo systemctl start lums-agent.service
```

Check:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

A successful report should show authenticated communication.

Do not publish the token from the configuration.

---

# 66. Watcher Post-Deployment Check

Run:

```bash
sudo systemctl start \
    lums-execution-watcher.service
```

Check:

```bash
sudo systemctl status \
    lums-execution-watcher.service \
    --no-pager
```

Logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
```

Verify that no unintended simulation mode is active.

---

# 67. Frontend Deployment Validation

After frontend changes, verify that the new source is actually inside the running container.

Check Enterprise Admin:

```bash
sudo docker exec lums \
    sh -c \
    'grep -n "LUMS // ENTERPRISE ADMIN" /app/server/static/style.css'
```

Check theme handling:

```bash
sudo docker exec lums \
    sh -c \
    'grep -n "lums-theme" /app/server/static/theme.js'
```

Check network visualization:

```bash
sudo docker exec lums \
    sh -c \
    'test -f /app/server/static/network.js && echo OK'
```

Check client token rotation:

```bash
sudo docker exec lums \
    sh -c \
    'grep -n "rotate-client-token-button" /app/server/templates/client.html'
```

and:

```bash
sudo docker exec lums \
    sh -c \
    'grep -n "rotateClientToken" /app/server/static/client.js'
```

---

# 68. Browser Cache

Frontend changes may not become visible immediately because the browser can cache:

* CSS
* JavaScript
* HTML
* localStorage theme selection

If the application is running the expected image but the browser shows an old frontend:

1. Reload the page.
2. Perform a hard refresh.
3. Verify the selected theme.
4. Inspect browser developer tools.
5. Verify the running container files.

Do not rebuild the server repeatedly before verifying browser cache and localStorage state.

---

# 69. Theme Troubleshooting

Inspect:

```javascript
localStorage.getItem("lums-theme");
```

Then:

```javascript
document.documentElement.dataset.theme;
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

The HTML attribute should correspond:

```html
<html data-theme="admin">
```

Theme CSS uses selectors such as:

```css
html[data-theme="geek"]
```

and:

```css
html[data-theme="admin"]
```

---

# 70. Theme Isolation

When modifying Enterprise Admin:

```css
html[data-theme="admin"]
```

should be the primary scope.

When modifying Geek:

```css
html[data-theme="geek"]
```

should be the primary scope.

When modifying Nerd:

```css
html[data-theme="nerd"]
```

should be the primary scope.

Avoid global CSS changes unless the change is intentionally shared by every theme.

The goal is:

```text
Theme A
   |
   +-- own visual rules

Theme B
   |
   +-- own visual rules

Theme C
   |
   +-- own visual rules
```

---

# 71. Client Token Troubleshooting

If a client returns:

```text
401 Unauthorized
```

check:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Then check the server logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Verify:

* client identity
* token presence
* token validity
* configured server URL
* TLS trust
* client enabled state
* token revocation state

Do not print the token.

If the token was recently rotated, verify that the agent has been updated with the new token.

The previous token must no longer authenticate.

---

# 72. Common Problem: LUMS Container Not Running

Check:

```bash
sudo docker ps -a
```

Then:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Check the image:

```bash
sudo docker images lums
```

Check the volume:

```bash
sudo docker volume inspect lums-data
```

Check the secret:

```bash
sudo docker inspect lums \
    --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

Do not delete the volume as the first troubleshooting step.

---

# 73. Common Problem: Gunicorn Does Not Start

Check:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Expected startup includes:

```text
=== LUMS database initialization ===
=== Starting Gunicorn ===
Starting gunicorn 23.0.0
Listening at: http://0.0.0.0:5000
Booting worker
```

Possible causes:

* Python import error
* missing dependency
* invalid application configuration
* missing secret file
* incorrect secret permissions
* database initialization failure

Verify the secret without exposing it:

```bash
sudo docker exec lums sh -c '
echo "LUMS_SECRET_KEY_FILE=${LUMS_SECRET_KEY_FILE}"

if [ -r /run/secrets/lums_secret ]; then
    echo "SECRET_FILE=READABLE"
else
    echo "SECRET_FILE=NOT_READABLE"
fi
'
```

---

# 74. Common Problem: Browser Shows Old Frontend

Check:

```bash
sudo docker ps
```

Then:

```bash
sudo docker inspect lums \
    --format '{{.Image}}'
```

Verify the frontend inside the container:

```bash
sudo docker exec lums \
    sh -c \
    'grep -n "LUMS // ENTERPRISE ADMIN" /app/server/static/style.css'
```

If the container contains the expected source:

1. Hard refresh the browser.
2. Check localStorage.
3. Check `data-theme`.
4. Inspect browser developer tools.

---

# 75. Common Problem: Agent Returns HTTP 401

Check configuration without exposing the token:

```bash
sudo grep -E \
    '^[[:space:]]*LUMS_(BASE|CA_FILE)=' \
    /etc/default/lums-agent
```

Check service logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    --no-pager \
    -n 100
```

Check server logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Verify:

* client identity
* token presence
* token correctness
* server URL
* TLS trust
* enabled state
* token revocation state

If a token was rotated, update the agent configuration first.

---

# 76. Common Problem: Agent Cannot Reach LUMS

Check hostname resolution:

```bash
getent hosts <LUMS_HOST>
```

Test HTTPS:

```bash
curl -I \
    https://<LUMS_HOST>/
```

If a private CA is used:

```bash
sudo test -f \
    /opt/lums-agent/lums-ca.crt \
    && echo "CA file present"
```

Check the agent configuration without displaying the token.

---

# 77. Common Problem: Jobs Are Not Executing

Check the reporting agent:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Check its timer:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Check the watcher:

```bash
sudo systemctl status \
    lums-execution-watcher.service \
    --no-pager
```

Check the watcher timer:

```bash
sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager
```

Check logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    -n 200 \
    --no-pager
```

Then investigate:

* pending job state
* authenticated client identity
* idle state
* job ownership
* job claim
* package manager state

Only after the LUMS workflow has been checked should the package manager itself be investigated.

---

# 78. Common Problem: Job Remains Running

Check the job through the LUMS interface first.

Then inspect watcher logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "1 hour ago" \
    --no-pager
```

If the job is genuinely abandoned, use the supported recovery workflow.

Do not manually mark the job successful without verifying the package operation.

---

# 79. Common Problem: Job Has Unexpected State

Inspect the job through the application first.

If database inspection is required:

```bash
sudo docker exec -it lums \
    sqlite3 /var/lib/lums/lums.db
```

Use:

```sql
.tables
.schema
```

before querying tables.

Do not modify application state until the cause has been identified.

---

# 80. Common Problem: Nginx Fails After a Change

Run:

```bash
sudo nginx -t
```

If the test fails:

```text
Do not reload Nginx.
```

Correct the configuration.

Run again:

```bash
sudo nginx -t
```

Only after success:

```bash
sudo systemctl reload nginx
```

---

# 81. Common Problem: TLS Failure

Check:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

Check:

```bash
sudo nginx -t
```

Check errors:

```bash
sudo tail \
    -n 100 \
    /var/log/nginx/error.log
```

Check certificate trust on the client.

Do not disable TLS verification as a permanent solution.

---

# 82. Security Administration

LUMS should be treated as infrastructure software.

Important security boundaries include:

```text
Browser
   |
   | HTTPS
   v
Nginx
   |
   | localhost
   v
Gunicorn
   |
   v
Flask
   |
   v
SQLite
```

and:

```text
LUMS
   |
   | authenticated API
   v
Agent
   |
   v
Package Manager
```

The agent therefore represents a privileged execution component.

---

# 83. Container Security

The current production security baseline is:

```text
Non-root
    |
    +-- UID 10001

Capabilities
    |
    +-- ALL dropped

Root filesystem
    |
    +-- read-only

Temporary storage
    |
    +-- /tmp tmpfs

Database
    |
    +-- persistent lums-data volume

Flask secret
    |
    +-- read-only secret mount

Network
    |
    +-- localhost Docker binding
```

Verify:

```bash
sudo docker inspect lums \
    --format \
    'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{json .HostConfig.CapDrop}} Privileged={{.HostConfig.Privileged}}'
```

This configuration must be retained during deployment.

---

# 84. Secrets

The following values must never be committed to Git:

* client tokens
* passwords
* Flask secrets
* private TLS keys
* production environment credentials
* database files containing production state

Documentation should use:

```text
<LUMS_HOST>
<CLIENT_ID>
<CLIENT_TOKEN>
<JOB_ID>
<PACKAGE>
```

Never document actual credentials.

---

# 85. Logs and Sensitive Data

Before publishing logs:

```text
remove tokens
remove passwords
remove private keys
remove session secrets
remove unnecessary personal data
```

A useful troubleshooting report contains:

* component
* timestamp
* error message
* relevant configuration state
* software version
* command used

without exposing credentials.

---

# 86. Database Security

The SQLite database contains application state and operational information.

Access should therefore be restricted to LUMS administrators.

Do not expose:

```text
/var/lib/lums
```

through Nginx.

Do not publish the SQLite database as a web resource.

Do not place the database in the Git repository.

---

# 87. Backup Strategy

A practical LUMS backup strategy should cover:

```text
1. SQLite database
2. TLS material
3. Docker environment configuration
4. Protected Flask secret
5. Agent configuration
6. Agent CA certificate
7. Source repository
```

The source repository alone is not a complete backup.

Persistent application state and deployment configuration must also be protected.

Secret backups must be handled with the same or stronger access controls as the active secret.

---

# 88. Recovery Strategy

A basic recovery sequence is:

```text
Restore host
      |
      v
Restore LUMS configuration
      |
      v
Restore TLS material
      |
      v
Restore protected secret
      |
      v
Restore Docker image/source
      |
      v
Restore lums-data
      |
      v
Start container
      |
      v
Validate database
      |
      v
Validate Nginx
      |
      v
Validate HTTPS
      |
      v
Validate agent
      |
      v
Validate watcher
```

Recovery should be performed layer by layer.

A complete isolated full restore test remains an outstanding validation task.

---

# 89. Full Application Reset

A complete LUMS reset is different from a normal redeployment.

Normal redeployment:

```text
replace container
keep volume
```

Full reset:

```text
replace container
remove persistent data
initialize new database
```

The second operation is destructive.

Before a full reset:

1. Create a database backup.
2. Verify its integrity.
3. Preserve required configuration.
4. Confirm that data destruction is intentional.

A full reset should never be used as a routine troubleshooting shortcut.

---

# 90. Controlled Cleanup

Inspect Docker storage:

```bash
sudo docker system df
```

Do not blindly execute:

```bash
docker system prune -a
```

on a production-like system.

Review unused images and containers first.

Treat Docker volumes separately from disposable containers and images.

---

# 91. Operational Deployment Workflow

The recommended deployment sequence is:

```text
1. Check Git status
       |
       v
2. Review changes
       |
       v
3. Check configuration
       |
       v
4. Create SQLite backup
       |
       v
5. Verify backup
       |
       v
6. Build Docker image
       |
       v
7. Verify image
       |
       v
8. Recreate hardened container
       |
       v
9. Check Gunicorn logs
       |
       v
10. Check container hardening
       |
       v
11. Check database integrity
       |
       v
12. Check local HTTP
       |
       v
13. Check Nginx
       |
       v
14. Check HTTPS
       |
       v
15. Check frontend
       |
       v
16. Check agent
       |
       v
17. Check watcher
       |
       v
18. Verify application
```

Do not skip the backup step for production-like database changes.

---

# 92. Operational Principles

The following principles should guide LUMS administration.

### Principle 1 — Find the layer

Do not reinstall everything because one component failed.

---

### Principle 2 — Preserve state

The database is persistent application state.

Protect it.

---

### Principle 3 — Separate source from runtime

Git source, Docker image, container and database volume are different things.

---

### Principle 4 — Verify before changing

Use:

```bash
docker ps
docker logs
systemctl status
journalctl
nginx -t
sqlite integrity_check
```

before changing configuration.

---

### Principle 5 — Do not expose secrets

Logs, screenshots, documentation and Git commits must not contain credentials.

---

### Principle 6 — Test deployment in layers

```text
Build
    |
    v
Container
    |
    v
Local HTTP
    |
    v
Nginx
    |
    v
HTTPS
    |
    v
Frontend
    |
    v
Agent
    |
    v
Watcher
    |
    v
Execution
```

---

### Principle 7 — Simulation before execution

When testing update workflows, simulation mode should be used whenever possible.

---

### Principle 8 — Do not confuse a working UI with a working backend

The dashboard can render while another layer is broken.

Always validate:

```text
Frontend
Backend
Database
Agent
Watcher
```

independently.

---

### Principle 9 — Preserve container hardening

A deployment is incomplete if the application works but the hardened runtime configuration has been lost.

Always verify:

```text
Non-root
Read-only root filesystem
ALL capabilities dropped
Non-privileged container
Protected secret mount
Localhost-only application binding
```

---

### Principle 10 — Rotate credentials through controlled workflows

Client tokens must be rotated through the authenticated administrative workflow.

After rotation:

```text
New token
    |
    v
Agent update
    |
    v
Authentication
    |
    v
Client report
```

The change is not complete until replacement communication has been verified.

---

# 93. Current Security State

The following controls have been implemented and verified:

```text
[x] Non-root Docker container
[x] UID 10001
[x] ALL Linux capabilities dropped
[x] Read-only root filesystem
[x] /tmp provided through tmpfs
[x] Protected Flask secret file
[x] Secret mounted read-only
[x] Production Flask secret rotation
[x] HTTPS
[x] TLS 1.2 / TLS 1.3
[x] Security response headers
[x] Bearer authentication
[x] Client authorization
[x] Client token lifecycle
[x] Client token rotation
[x] Token rotation audit logging
[x] Interrupted-job recovery
[x] Recovery ownership validation
[x] Production frontend deployment
[x] Production client communication after token rotation
[x] SQLite-aware backup
[x] Backup integrity verification
```

Remaining security/development tasks include:

```text
[ ] Complete update execution hardening
[ ] Full backup / restore test
[ ] Automated security regression tests
[ ] Final security review
```

---

# 94. Final Administration Checklist

## Docker

```bash
sudo docker ps

sudo docker logs \
    --tail 100 \
    lums
```

## Container hardening

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

## Secret

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

## Persistent storage

```bash
sudo docker volume inspect lums-data
```

## Database

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

## Nginx

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
```

## HTTPS

```bash
curl -kI \
    https://<LUMS_HOST>/
```

## Agent

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

## Agent timer

```bash
systemctl list-timers --all | grep lums-agent
```

## Watcher

```bash
sudo systemctl status \
    lums-execution-watcher.service \
    --no-pager
```

## Watcher timer

```bash
systemctl list-timers --all | grep lums-execution
```

## Git

```bash
cd /opt/lums-public
git status -sb
git diff --check
```

## Image

```bash
sudo docker images lums
```

## Frontend

Verify:

```text
/app/server/static/style.css
/app/server/static/theme.js
/app/server/static/network.js
/app/server/static/client.js
/app/server/templates/login.html
/app/server/templates/index.html
/app/server/templates/client.html
```

## Client token rotation

Verify the client page contains:

```text
🔐 Token rotieren
```

and that a rotated token is never written into logs or audit records.

---

# 95. Final Principle

LUMS is intentionally built as a layered system.

```text
Source
  |
  v
Docker Image
  |
  v
Hardened Container
  |
  +-- Gunicorn
  |
  +-- Flask
  |
  +-- SQLite
  |
  +-- Frontend
  |
  v
Nginx
  |
  v
HTTPS

        +

Agent
  |
  v
Watcher
  |
  v
Package Manager
```

When something breaks, the goal is not to rebuild everything.

The goal is to identify exactly where the chain breaks.

That is the difference between:

```text
"I'll reinstall it."
```

and:

```text
"I know which layer failed."
```

---

# LUMS

**LUMS — Linux Update Management without the noise.**

**Centralize the management.**

**Keep execution controlled.**

**Know what changed.**

**Know where it happened.**

**One LUMS. Same Backend. Controlled Execution.**
