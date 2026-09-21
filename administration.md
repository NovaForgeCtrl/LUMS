# LUMS — Administration Guide

## Linux Update Management Server

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

LUMS does not replace the underlying Linux package manager.

The package manager remains responsible for the actual package operation.

LUMS controls when and where an update operation is requested and records the resulting state.

---

# 2. Architecture

The current deployment consists of the following logical layers:

```text
                         Browser
                            |
                            | HTTPS
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
                    | Flask          |
                    | Templates      |
                    | Static Assets  |
                    | SQLite         |
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
                    +----------------+
                            |
                            v
                    Linux Package Manager
```

The application itself is not directly exposed to the network.

Docker publishes the Flask application only on localhost:

```text
127.0.0.1:5050 -> container:5000
```

Nginx provides the externally accessible HTTPS endpoint.

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
        |
        +-- frontend source
        |
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

## 4.3 TLS

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Do not place private keys or environment secrets inside Git.

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
/app/server/templates/index.html
/app/server/templates/client.html

/app/server/static/style.css
/app/server/static/theme.js
/app/server/static/network.js
```

The frontend contains:

* HTML templates
* CSS
* JavaScript
* theme handling
* network visualization
* dashboard presentation

The frontend is served by the Flask application and therefore becomes part of the Docker image during deployment.

---

# 6. Theme System

LUMS currently provides the following theme identifiers:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

The `admin` identifier represents the user-facing:

```text
Enterprise Admin
```

theme.

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

---

# 7. Enterprise Admin Theme

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

The other themes should not be modified when making Enterprise Admin-specific changes.

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

---

# 8. Geek Network Visualization

The Geek theme provides the:

```text
The Living Network
```

visualization.

Its JavaScript implementation is located in:

```text
server/static/network.js
```

The network visualization contains:

* drifting nodes
* connection lines
* moving packets
* dynamic network activity

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

The network effect is started only when the Geek theme is active.

Reduced-motion preferences are respected.

---

# 9. Nerd Theme

The Nerd theme provides a terminal/CRT/Matrix-style visual presentation.

The Matrix-style effect is controlled by:

```text
server/static/theme.js
```

It is only activated when:

```text
lums-theme = nerd
```

The Nerd theme should remain independent from the Geek network visualization.

---

# 10. Docker Administration

## 10.1 Check container

```bash
sudo docker ps
```

Expected container:

```text
lums
```

---

## 10.2 Check all containers

```bash
sudo docker ps -a
```

---

## 10.3 Inspect container

```bash
sudo docker inspect lums
```

---

## 10.4 Check container status

```bash
sudo docker inspect -f '{{.State.Status}}' lums
```

---

## 10.5 Check container restart policy

```bash
sudo docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' lums
```

Expected:

```text
unless-stopped
```

---

# 11. Docker Image

The application image is:

```text
lums:latest
```

Build it from the repository:

```bash
cd /opt/lums-public
sudo docker build -t lums:latest .
```

Check the image:

```bash
sudo docker images lums
```

---

# 12. Container Recreation

Recreating the container does not remove the persistent database as long as the Docker volume is preserved.

Current recreation procedure:

```bash
sudo docker stop lums

sudo docker rm lums

sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
```

Verify:

```bash
sudo docker ps
```

Then check logs:

```bash
sudo docker logs --tail 100 lums
```

---

# 13. Critical Docker Rule

Never remove the persistent database volume as part of a normal application deployment.

The following command is destructive:

```bash
sudo docker volume rm lums-data
```

It removes the persistent application data.

Do not execute it unless a complete reset is intentionally required and the database is no longer needed.

---

# 14. Docker Logs

View recent logs:

```bash
sudo docker logs --tail 100 lums
```

Follow logs:

```bash
sudo docker logs -f lums
```

View logs with timestamps:

```bash
sudo docker logs --timestamps --tail 200 lums
```

For troubleshooting, start with:

```bash
sudo docker ps
sudo docker logs --tail 100 lums
```

before changing configuration.

---

# 15. Nginx Administration

Nginx provides the external HTTPS endpoint.

The architecture is:

```text
Internet / LAN Client
        |
        v
      HTTPS
        |
        v
      Nginx
        |
        v
127.0.0.1:5050
        |
        v
Docker:5000
        |
        v
Flask
```

Flask is therefore not directly exposed to the network.

---

# 16. Nginx Configuration Test

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

# 17. Nginx Logs

Error log:

```bash
sudo tail -n 100 /var/log/nginx/error.log
```

Access log:

```bash
sudo tail -n 100 /var/log/nginx/access.log
```

Follow errors:

```bash
sudo tail -f /var/log/nginx/error.log
```

---

# 18. Network and Health Checks

## 18.1 Check local Flask binding

```bash
sudo ss -lntp | grep ':5050'
```

The expected binding is localhost only:

```text
127.0.0.1:5050
```

---

## 18.2 Test local application endpoint

```bash
curl -I http://127.0.0.1:5050/
```

---

## 18.3 Test HTTPS endpoint

Use the configured LUMS hostname:

```bash
curl -kI https://<LUMS_HOST>/
```

The `-k` option is intended only for testing certificates that are not trusted by the local system.

Do not use it as a replacement for proper certificate trust configuration.

---

# 19. TLS Administration

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

Check file permissions:

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

# 20. Server Environment

The Docker environment file is:

```text
/etc/lums/docker/lums.env
```

This file may contain sensitive configuration.

It must not be committed to Git.

When documenting the configuration, use placeholders.

For example:

```text
LUMS_BASE=https://<LUMS_HOST>
LUMS_TOKEN=<CLIENT_TOKEN>
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

Never place an actual token into documentation.

---

# 21. Agent Configuration

The agent is installed outside the Docker container.

Current paths include:

```text
/opt/lums-agent/agent.py
/opt/lums-agent/watcher.py
/opt/lums-agent/lums-ca.crt
/etc/default/lums-agent
```

The agent configuration contains the LUMS server endpoint and authentication information.

A documented example should therefore use:

```text
LUMS_BASE=https://<LUMS_HOST>
LUMS_TOKEN=<CLIENT_TOKEN>
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

Do not print the real token when troubleshooting.

A safe check is:

```bash
sudo grep -E '^[[:space:]]*LUMS_(BASE|CA_FILE)=' /etc/default/lums-agent
```

For the token, verify presence without displaying its value.

---

# 22. Agent Authentication

The current LUMS implementation uses a client token that is stored in the database as a SHA-256 hexadecimal digest.

This is an authentication token representation.

It must not be described as a password hashing scheme.

The distinction is important:

```text
Password
    |
    +-- password-specific password hashing

Client token
    |
    +-- SHA-256 digest used by the current implementation
```

Future hardening may change this mechanism.

Authentication failures should therefore be diagnosed against the currently installed implementation rather than against assumptions about how tokens "should" be stored.

---

# 23. Agent Service

Check the service:

```bash
sudo systemctl status lums-agent --no-pager
```

Start:

```bash
sudo systemctl start lums-agent
```

Stop:

```bash
sudo systemctl stop lums-agent
```

Restart:

```bash
sudo systemctl restart lums-agent
```

Enable:

```bash
sudo systemctl enable lums-agent
```

---

# 24. Agent Timer

The agent execution schedule is controlled by systemd.

Do not assume a fixed interval from documentation.

Check the actual installed schedule:

```bash
systemctl list-timers --all | grep lums-agent
```

Inspect the timer:

```bash
sudo systemctl cat lums-agent.timer
```

Check its status:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

This makes the installed configuration the authoritative source.

---

# 25. Agent Logs

View recent logs:

```bash
sudo journalctl -u lums-agent --no-pager -n 100
```

Follow logs:

```bash
sudo journalctl -u lums-agent -f
```

When troubleshooting authentication, look for:

```text
401
403
authentication
token
report
```

Do not paste real authentication tokens into logs, documentation or GitHub issues.

---

# 26. Execution Watcher

The execution watcher monitors update execution and related job state.

Current files:

```text
/opt/lums-agent/watcher.py
```

Systemd units:

```text
lums-execution-watcher.service
lums-execution-watcher.timer
```

Check the service:

```bash
sudo systemctl status lums-execution-watcher --no-pager
```

Check the timer:

```bash
sudo systemctl status lums-execution-watcher.timer --no-pager
```

Inspect the installed timer schedule:

```bash
sudo systemctl cat lums-execution-watcher.timer
```

List timers:

```bash
systemctl list-timers --all | grep lums
```

---

# 27. Execution Watcher Logs

```bash
sudo journalctl \
    -u lums-execution-watcher \
    --no-pager \
    -n 100
```

Follow:

```bash
sudo journalctl -u lums-execution-watcher -f
```

---

# 28. Idle-Aware Execution

LUMS can use system activity information when determining whether controlled execution should take place.

The current implementation uses:

```text
w -h
```

for the relevant server/terminal/SSH-oriented activity detection.

This should not be interpreted as a universal desktop-idle detection system.

The mechanism is intended to provide an operational activity signal for the LUMS execution workflow.

When diagnosing unexpected execution behavior, inspect the actual installed implementation and logs.

---

# 29. Update Job Lifecycle

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
Job enters pending state
      |
      v
Client claims job
      |
      v
Client executes operation
      |
      v
Client reports result
      |
      v
LUMS records result
      |
      v
Job becomes completed / failed
```

The exact state transitions are determined by the application implementation.

The database should therefore be treated as the authoritative application state.

---

# 30. Job Claiming

The client-side execution workflow uses the LUMS API to obtain work assigned to the client.

Relevant API routes should be verified against the installed application before troubleshooting or documenting an API contract.

A typical operational flow is:

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

Do not manually modify job state in SQLite unless performing a controlled recovery procedure.

---

# 31. Job Result Reporting

After execution, the client reports the result back to LUMS.

A result should contain the information required by the server to determine the outcome of the requested operation.

Typical information includes:

* job identifier
* client identifier
* execution state
* result information
* timestamps
* relevant package information

Never insert fabricated success information into the database simply to make the dashboard appear healthy.

---

# 32. Simulation Mode

LUMS supports simulation behavior for update operations.

The relevant environment configuration may include:

```text
LUMS_SIMULATE_UPDATES
```

When simulation mode is enabled, the update workflow can be tested without performing the intended real update operation.

This is useful for:

* development
* frontend testing
* job lifecycle testing
* agent testing
* deployment validation
* troubleshooting

Always verify the actual environment value before assuming simulation mode is active.

---

# 33. Package Manager Safety

LUMS does not replace the Linux package manager.

The underlying package manager remains responsible for:

* dependency resolution
* package installation
* package removal
* package configuration
* repository interaction
* transaction execution

LUMS provides centralized orchestration and visibility.

The update execution layer must therefore be treated as privileged infrastructure.

Testing should begin with simulation mode whenever possible.

---

# 34. Database Administration

The application database is:

```text
/var/lib/lums/lums.db
```

inside the container.

The directory is persistent through:

```text
lums-data
```

Docker volume.

Check the volume:

```bash
sudo docker volume inspect lums-data
```

---

# 35. Accessing the Database

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

# 36. Database Integrity Check

A basic SQLite integrity check:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

A healthy database should return:

```text
ok
```

---

# 37. Database Backup

The database is persistent application state and must be backed up.

Create a backup directory on the host:

```bash
sudo mkdir -p /var/backups/lums
```

A safe online SQLite backup can be created through a temporary container.

Example:

```bash
sudo docker run --rm \
    -v lums-data:/var/lib/lums:ro \
    -v /var/backups/lums:/backup \
    lums:latest \
    python3 -c '
import sqlite3
source = sqlite3.connect("/var/lib/lums/lums.db")
target = sqlite3.connect("/backup/lums-backup.db")
source.backup(target)
target.close()
source.close()
'
```

Verify:

```bash
sudo ls -lh /var/backups/lums/
```

---

# 38. Timestamped Database Backup

For operational backups, use a timestamped filename:

```bash
BACKUP="/var/backups/lums/lums-$(date +%F-%H%M%S).db"

sudo docker run --rm \
    -v lums-data:/var/lib/lums:ro \
    -v /var/backups/lums:/backup \
    lums:latest \
    python3 -c "
import sqlite3
source = sqlite3.connect('/var/lib/lums/lums.db')
target = sqlite3.connect('/backup/$(basename "$BACKUP")')
source.backup(target)
target.close()
source.close()
"
```

Verify the resulting file:

```bash
sudo ls -lh "$BACKUP"
```

---

# 39. Backup Verification

A backup is only useful if it can be read.

Test a backup:

```bash
sqlite3 /var/backups/lums/<BACKUP_FILE>.db \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

A backup that has never been tested should not be considered a verified recovery source.

---

# 40. Database Restore

Before restoring a database:

1. Stop LUMS.
2. Preserve the existing database.
3. Verify the backup.
4. Restore the database.
5. Start LUMS.
6. Check logs.
7. Check application functionality.

Stop the container:

```bash
sudo docker stop lums
```

Create a safety copy of the current database before replacing it.

Then restore the verified database into the persistent volume using a controlled maintenance procedure.

Do not overwrite the database blindly.

---

# 41. Git Administration

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

Check recent commits:

```bash
git log --oneline --decorate -5
```

Check remote:

```bash
git remote -v
```

---

# 42. Git Identity

The LUMS repository uses the project identity:

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

# 43. Git Deployment Workflow

A normal source update should follow this order:

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
Pull / checkout
 |
 v
Inspect changes
 |
 v
Build Docker image
 |
 v
Recreate container
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
```

Only after reviewing the changes:

```bash
git pull --ff-only
```

Then:

```bash
sudo docker build -t lums:latest .
```

---

# 44. Docker Deployment

After building a new image:

```bash
sudo docker stop lums

sudo docker rm lums

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
sudo docker ps
```

Then:

```bash
sudo docker logs --tail 100 lums
```

---

# 45. Deployment Rule

A deployment consists of separate layers:

```text
SOURCE
  |
  v
IMAGE
  |
  v
CONTAINER
  |
  v
PERSISTENT DATA
```

These layers must not be confused.

Changing source code:

```text
/opt/lums-public
```

does not automatically change the running container.

Building an image:

```text
lums:latest
```

does not automatically recreate the container.

Recreating the container does not remove:

```text
lums-data
```

unless the volume is explicitly removed.

---

# 46. Agent and Watcher Deployment

Agent and watcher updates are separate from the Docker application deployment.

The relevant files are located under:

```text
/opt/lums-agent/
```

Systemd units manage execution.

After changing agent code:

```bash
sudo systemctl daemon-reload
```

when unit files were changed.

Then restart the relevant services:

```bash
sudo systemctl restart lums-agent
sudo systemctl restart lums-execution-watcher
```

Check:

```bash
sudo systemctl status lums-agent --no-pager
sudo systemctl status lums-execution-watcher --no-pager
```

If timer definitions changed:

```bash
sudo systemctl daemon-reload
```

and verify:

```bash
systemctl list-timers --all | grep lums
```

---

# 47. Post-Deployment Validation

After a deployment, validate each layer separately.

## Layer 1 — Docker

```bash
sudo docker ps
```

Expected:

```text
lums
```

---

## Layer 2 — Application logs

```bash
sudo docker logs --tail 100 lums
```

Look for startup errors.

---

## Layer 3 — Local application

```bash
curl -I http://127.0.0.1:5050/
```

---

## Layer 4 — Nginx

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
```

---

## Layer 5 — HTTPS

```bash
curl -kI https://<LUMS_HOST>/
```

---

## Layer 6 — Agent

```bash
sudo systemctl status lums-agent --no-pager
```

---

## Layer 7 — Watcher

```bash
sudo systemctl status lums-execution-watcher --no-pager
```

---

## Layer 8 — Database

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

---

# 48. Frontend Deployment Validation

After frontend changes, verify that the new source is actually inside the running container.

For example:

```bash
sudo docker exec lums \
    sh -c 'grep -n "Enterprise Admin" /app/server/static/style.css'
```

Check theme JavaScript:

```bash
sudo docker exec lums \
    sh -c 'grep -n "lums-theme" /app/server/static/theme.js'
```

Check network JavaScript:

```bash
sudo docker exec lums \
    sh -c 'test -f /app/server/static/network.js && echo OK'
```

This helps distinguish:

```text
source problem
```

from:

```text
Docker deployment problem
```

---

# 49. Browser Cache

Frontend changes may not become visible immediately because the browser can cache:

* CSS
* JavaScript
* HTML
* localStorage theme selection

If the application is running the expected image but the browser shows an old frontend:

1. reload the page
2. perform a hard refresh
3. verify the selected theme
4. inspect browser developer tools
5. verify the running container files

Do not rebuild the server repeatedly before verifying whether the browser is displaying cached frontend assets.

---

# 50. Theme Troubleshooting

If the wrong theme is displayed, check:

```text
Browser localStorage
        |
        v
lums-theme
        |
        v
theme.js
        |
        v
document.documentElement.dataset.theme
        |
        v
style.css
```

The selected theme can be inspected from browser developer tools.

The important HTML attribute is:

```text
data-theme
```

The CSS uses selectors such as:

```css
html[data-theme="geek"]
```

and:

```css
html[data-theme="admin"]
```

---

# 51. Theme Isolation

When modifying Enterprise Admin:

```text
html[data-theme="admin"]
```

should be the primary scope.

When modifying Geek:

```text
html[data-theme="geek"]
```

should be the primary scope.

When modifying Nerd:

```text
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

rather than allowing one theme to accidentally change another.

---

# 52. Troubleshooting Strategy

When something fails, do not immediately reinstall LUMS.

Use the following order:

```text
1. Browser
2. Nginx
3. Docker
4. Flask application
5. Database
6. Agent
7. Watcher
8. Package manager
```

Identify the first layer where the expected behavior disappears.

---

# 53. Common Problem: LUMS Container Not Running

Check:

```bash
sudo docker ps -a
```

Then:

```bash
sudo docker logs --tail 200 lums
```

Check the image:

```bash
sudo docker images lums
```

Check the volume:

```bash
sudo docker volume inspect lums-data
```

Do not delete the volume as a first troubleshooting step.

---

# 54. Common Problem: Browser Shows Old Frontend

Check:

```bash
sudo docker ps
```

Then:

```bash
sudo docker inspect lums \
    --format '{{.Image}}'
```

Compare with the current image:

```bash
sudo docker images lums
```

Verify the actual frontend files:

```bash
sudo docker exec lums \
    sh -c 'grep -n "Enterprise Admin" /app/server/static/style.css'
```

If the container contains the expected source, perform a browser hard refresh before rebuilding again.

---

# 55. Common Problem: Agent Returns HTTP 401

Check agent configuration:

```bash
sudo grep -E \
    '^[[:space:]]*LUMS_(BASE|CA_FILE)=' \
    /etc/default/lums-agent
```

Do not print the token.

Check service logs:

```bash
sudo journalctl \
    -u lums-agent \
    --no-pager \
    -n 100
```

Check server logs:

```bash
sudo docker logs --tail 200 lums
```

Verify:

* client identity
* token presence
* token correctness
* database token digest
* configured server URL
* TLS trust
* API authorization logic

The previous known authentication issue involved an incorrect token digest representation in the database.

The current implementation uses SHA-256 hexadecimal token digests.

---

# 56. Common Problem: Agent Cannot Reach LUMS

Check DNS or hostname resolution:

```bash
getent hosts <LUMS_HOST>
```

Test HTTPS:

```bash
curl -I https://<LUMS_HOST>/
```

If a private CA is used, verify the configured CA file:

```bash
sudo test -f /opt/lums-agent/lums-ca.crt \
    && echo "CA file present"
```

Check the agent configuration without exposing secrets.

---

# 57. Common Problem: Jobs Are Not Executing

Check:

```bash
sudo systemctl status lums-agent --no-pager
```

Then:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

Check timer schedule:

```bash
systemctl list-timers --all | grep lums-agent
```

Check logs:

```bash
sudo journalctl -u lums-agent --no-pager -n 200
```

Then check:

```bash
sudo systemctl status lums-execution-watcher --no-pager
```

and:

```bash
sudo journalctl \
    -u lums-execution-watcher \
    --no-pager \
    -n 200
```

Only after checking the agent and watcher should the package manager itself be investigated.

---

# 58. Common Problem: Jobs Have Unexpected State

Inspect the job through the LUMS interface first.

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

Do not modify state until the cause has been identified.

---

# 59. Common Problem: Nginx Fails After a Change

Run:

```bash
sudo nginx -t
```

If the test fails, do not reload Nginx.

Inspect the error message and correct the configuration.

Then:

```bash
sudo nginx -t
```

again.

Only after success:

```bash
sudo systemctl reload nginx
```

---

# 60. Common Problem: TLS Failure

Check certificate:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

Check Nginx:

```bash
sudo nginx -t
```

Check Nginx errors:

```bash
sudo tail -n 100 /var/log/nginx/error.log
```

Check certificate trust on the client.

Do not disable TLS verification as a permanent solution.

---

# 61. Security Administration

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

# 62. Secrets

The following values must never be committed to Git:

* client tokens
* passwords
* private TLS keys
* production secrets
* environment files containing credentials

Documentation should use placeholders:

```text
<LUMS_HOST>
<CLIENT_ID>
<CLIENT_TOKEN>
<JOB_ID>
<PACKAGE>
```

Never document:

```text
real-token-value
real-password
real-private-key
```

---

# 63. Logs and Sensitive Data

Logs may contain operational information.

Before publishing logs:

```text
remove tokens
remove passwords
remove private keys
remove internal credentials
remove unnecessary personal data
```

A useful troubleshooting report contains:

* component
* timestamp
* error message
* relevant configuration state
* software version where relevant
* command used

without exposing secrets.

---

# 64. Database Security

The SQLite database contains application state and potentially sensitive operational information.

Access should therefore be restricted to the LUMS host administrators.

Do not expose:

```text
/var/lib/lums
```

through Nginx.

Do not publish the SQLite database as a downloadable web resource.

Do not place the database in the Git repository.

---

# 65. Backup Strategy

A practical LUMS backup strategy should cover:

```text
1. SQLite database
2. TLS material
3. Docker environment configuration
4. Agent configuration
5. Agent CA certificate
6. Source repository
```

The source repository alone is not a complete backup.

The persistent application state must also be protected.

---

# 66. Recovery Strategy

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

---

# 67. Full Application Reset

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

Before a full reset, create a database backup.

A reset should therefore never be performed casually as a troubleshooting shortcut.

---

# 68. Controlled Cleanup

Unused Docker objects can be inspected:

```bash
sudo docker system df
```

Do not blindly execute:

```bash
docker system prune -a
```

on a production-like lab system.

Review what is no longer needed first.

The same principle applies to Docker volumes.

Persistent data must be treated separately from disposable containers and images.

---

# 69. Operational Principles

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

# 70. Final Administration Checklist

## Docker

```bash
sudo docker ps
sudo docker logs --tail 100 lums
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

## Nginx

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
```

## HTTPS

```bash
curl -kI https://<LUMS_HOST>/
```

## Agent

```bash
sudo systemctl status lums-agent --no-pager
```

## Agent timer

```bash
systemctl list-timers --all | grep lums-agent
```

## Watcher

```bash
sudo systemctl status lums-execution-watcher --no-pager
```

## Watcher timer

```bash
systemctl list-timers --all | grep lums-execution
```

## Git

```bash
cd /opt/lums-public
git status -sb
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
/app/server/templates/index.html
/app/server/templates/client.html
```

---

# 71. Final Principle

LUMS is intentionally built as a layered system.

```text
Source
  |
  v
Docker Image
  |
  v
Container
  |
  v
Flask
  |
  +---- SQLite
  |
  +---- Frontend
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

Centralize the management.
Keep execution controlled.

Know what changed.
Know where it happened.

**One LUMS. Same Backend. Controlled Execution.**
