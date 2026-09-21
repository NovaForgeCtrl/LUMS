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
                       Flask :5000
                            │
                            ▼
                  /var/lib/lums/lums.db
                            │
                            ▼
                       lums-data
```

The persistent database is stored in the Docker volume:

```text
lums-data
```

The application source repository is:

```text
/opt/lums-public
```

The running application is inside the Docker container:

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

# 3. Troubleshooting Order

Use this order whenever possible:

```text
1. Network
2. HTTPS / TLS
3. Nginx
4. Docker
5. Flask
6. Database
7. Authentication
8. Authorization
9. Agent connectivity
10. Agent authentication
11. Agent reporting
12. Job creation
13. Job execution
14. APT / dpkg
15. Job result
16. Frontend
17. Theme system
18. Browser cache
```

If a lower layer is broken, do not spend time debugging a higher layer yet.

Example:

If:

```text
curl http://127.0.0.1:5050
```

already fails, debugging browser JavaScript is premature.

---

# 4. Important Paths

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

# 5. Docker Diagnostics

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
sudo docker inspect -f '{{.State.Status}}' lums
```

Expected:

```text
running
```

Check recent logs:

```bash
sudo docker logs --tail 100 lums
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

# 6. Docker Image

Check available LUMS images:

```bash
sudo docker images lums
```

Check the image used by the running container:

```bash
sudo docker inspect -f '{{.Config.Image}}' lums
```

Expected:

```text
lums:latest
```

After source changes, rebuild the image:

```bash
cd /opt/lums-public
sudo docker build -t lums:latest .
```

Verify the image:

```bash
sudo docker image inspect lums:latest
```

A successful build does not automatically mean the running container uses the new image.

The container must be recreated if the application files changed.

---

# 7. Docker Port Diagnostics

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

Test Flask directly:

```bash
curl -I http://127.0.0.1:5050
```

If this works but HTTPS does not, investigate Nginx/TLS.

If this fails, investigate Docker/Flask before Nginx.

---

# 8. Docker Volume Diagnostics

Check the persistent volume:

```bash
sudo docker volume inspect lums-data
```

Check that the volume is attached:

```bash
sudo docker inspect lums \
    --format '{{range .Mounts}}{{println .Name .Destination}}{{end}}'
```

Expected:

```text
lums-data /var/lib/lums
```

The database must remain on the persistent volume.

Do not delete the volume during normal container recreation.

---

# 9. Environment and Secrets

The environment file is:

```text
/etc/lums/docker/lums.env
```

Do not print the complete file.

Never use:

```bash
cat /etc/lums/docker/lums.env
```

when collecting diagnostic output for documentation or public bug reports.

Instead, check only whether required variables exist:

```bash
sudo awk -F= '
/^[A-Za-z_][A-Za-z0-9_]*=/ {
    print $1 "=<set>"
}' /etc/lums/docker/lums.env
```

This deliberately hides the values.

Inside the container:

```bash
sudo docker exec lums env | \
grep -E '^(LUMS_|FLASK_|PYTHON)' | \
sed 's/=.*$/=<set>/'
```

Never publish:

```text
passwords
tokens
API keys
private keys
session secrets
cookies
```

---

# 10. Flask Diagnostics

Check container logs:

```bash
sudo docker logs --tail 200 lums
```

Look for:

```text
Traceback
ERROR
Exception
sqlite
database
permission
```

Check the application process:

```bash
sudo docker exec lums ps aux
```

Check the application directory:

```bash
sudo docker exec lums ls -la /app
```

Check the server directory:

```bash
sudo docker exec lums ls -la /app/server
```

---

# 11. Nginx Diagnostics

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
sudo systemctl status nginx --no-pager
```

Check recent logs:

```bash
sudo journalctl -u nginx --since "30 minutes ago" --no-pager
```

Check access log:

```bash
sudo tail -n 100 /var/log/nginx/access.log
```

Check error log:

```bash
sudo tail -n 100 /var/log/nginx/error.log
```

---

# 12. Nginx 502 Bad Gateway

A `502 Bad Gateway` normally means Nginx cannot successfully reach the upstream application.

Check Flask directly:

```bash
curl -I http://127.0.0.1:5050
```

If this fails:

```text
Browser
  ↓
Nginx
  ↓
X
Flask
```

the problem is below Nginx.

Check:

```bash
sudo docker ps --filter name=lums
```

Then:

```bash
sudo docker logs --tail 100 lums
```

And:

```bash
sudo ss -lntp | grep ':5050'
```

---

# 13. HTTPS / TLS

Check the configured certificate files:

```bash
sudo ls -l /etc/lums/tls/
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
sudo cat /etc/lums/tls/lums.key
```

for public diagnostics.

---

# 14. TLS Certificate Diagnostics

Test the HTTPS endpoint:

```bash
curl -kI https://<LUMS_SERVER_IP>/
```

For certificate inspection:

```bash
openssl s_client \
    -connect <LUMS_SERVER_IP>:443 \
    -servername <LUMS_SERVER_IP> \
    </dev/null
```

For internal laboratory certificates, browser warnings may be expected depending on the trust configuration.

---

# 15. Agent TLS Problems

The agent uses the configured CA certificate:

```text
/opt/lums-agent/lums-ca.crt
```

Check that it exists:

```bash
sudo test -f /opt/lums-agent/lums-ca.crt \
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

# 16. Agent Connectivity

Check the agent service:

```bash
sudo systemctl status lums-agent --no-pager
```

Check recent logs:

```bash
sudo journalctl -u lums-agent \
    --since "30 minutes ago" \
    --no-pager
```

Check connectivity to the LUMS server:

```bash
curl -kI https://<LUMS_SERVER_IP>/
```

If the agent cannot connect:

```text
Agent
  ↓
DNS / Network
  ↓
TLS
  ↓
Nginx
  ↓
LUMS
```

Check each layer separately.

---

# 17. Agent Authentication

LUMS currently stores the client token in the database as a SHA-256 hexadecimal digest.

This is an authentication token digest.

It must not be confused with a password hashing scheme such as Argon2.

Do not display the stored digest publicly.

Check only that the client record exists:

```bash
sudo docker exec lums sqlite3 /var/lib/lums/lums.db \
"SELECT id, hostname FROM clients;"
```

Do not query or print token columns in public diagnostics.

If authentication fails with:

```text
401 Unauthorized
```

check:

```text
1. Client exists
2. Client ID is correct
3. Token is present in the agent environment
4. Token corresponds to the registered client
5. Server receives the expected Authorization header
6. Server authentication code is active
```

---

# 18. Agent Environment

Check that the configuration file exists:

```bash
sudo test -f /etc/default/lums-agent \
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

# 19. Manual Agent Execution

Before troubleshooting the timer, execute the agent manually.

Use the installed service environment rather than manually exposing credentials.

For example:

```bash
sudo systemctl stop lums-agent
sudo systemctl start lums-agent
```

Then inspect:

```bash
sudo journalctl -u lums-agent \
    --since "5 minutes ago" \
    --no-pager
```

After testing:

```bash
sudo systemctl status lums-agent --no-pager
```

---

# 20. Agent Returns 403

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
sudo docker logs --tail 200 lums
```

Check the agent logs:

```bash
sudo journalctl -u lums-agent \
    --since "30 minutes ago" \
    --no-pager
```

Do not immediately replace the token.

First determine which endpoint returned `403`.

---

# 21. Agent Reporting

If the client appears online but does not report correctly, check:

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
sudo journalctl -u lums-agent \
    --since "30 minutes ago" \
    --no-pager
```

Check server logs:

```bash
sudo docker logs --tail 200 lums
```

Check the database client list:

```bash
sudo docker exec lums sqlite3 /var/lib/lums/lums.db \
"SELECT id, hostname FROM clients;"
```

Do not expose client tokens.

---

# 22. Agent Timers

List relevant timers:

```bash
systemctl list-timers --all | grep -E 'lums|update'
```

Inspect the agent timer:

```bash
sudo systemctl cat lums-agent.timer
```

Inspect the watcher timer:

```bash
sudo systemctl cat lums-execution-watcher.timer
```

The actual schedule must always be taken from the installed timer configuration.

Do not assume a fixed interval if the timer configuration has changed.

Check the next run:

```bash
systemctl list-timers lums-agent.timer --no-pager
```

Check timer state:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

A oneshot service can show:

```text
inactive (dead)
```

after completing successfully.

That does not automatically mean the timer is broken.

---

# 23. Execution Watcher

Check:

```bash
sudo systemctl status lums-execution-watcher.timer --no-pager
```

Then:

```bash
sudo systemctl status lums-execution-watcher.service --no-pager
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

# 24. Simulation Mode

If a simulation mode exists, use it only for controlled testing.

A simulation should not be treated as proof that a real package update works.

Verify:

```text
Job creation
Job delivery
Agent execution
Result reporting
```

separately.

After testing, disable temporary simulation settings.

---

# 25. Update Jobs

When a job does not execute, determine where it stopped.

```text
Job created
    ↓
Job queued
    ↓
Agent retrieves job
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

Check the server logs:

```bash
sudo docker logs --tail 200 lums
```

Check the agent logs:

```bash
sudo journalctl -u lums-agent \
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

# 26. APT / dpkg Problems

On the client, check package state:

```bash
dpkg --audit
```

Check interrupted package configuration:

```bash
sudo dpkg --configure -a
```

Only run repair commands when the package manager is actually in a broken state.

Check APT:

```bash
apt-get check
```

Do not blindly delete APT lock files.

First determine which process owns the lock.

```bash
sudo lsof /var/lib/dpkg/lock-frontend
sudo lsof /var/lib/dpkg/lock
```

If another package operation is active, allow it to finish whenever possible.

---

# 27. Reboot Requirement

Some package updates require a reboot.

Check:

```bash
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot flag present"
```

Check packages requiring restart information if available:

```bash
sudo needs-restarting -r
```

The availability of `needs-restarting` depends on the installed distribution and packages.

Do not assume that every successful package installation requires a reboot.

---

# 28. Database Diagnostics

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
    ls -lh /var/lib/lums/lums.db
```

Do not dump the complete database into public bug reports.

The database can contain operational information and authentication-related data.

---

# 29. SQLite-Aware Database Backup

Do not copy the SQLite database blindly while it is actively being written.

A controlled temporary container can be used to access the persistent volume.

Example:

```bash
sudo docker run --rm \
    -v lums-data:/var/lib/lums:ro \
    lums:latest \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

Expected:

```text
ok
```

For an actual backup, create a copy using an SQLite-aware method where possible.

Example:

```bash
sudo docker run --rm \
    -v lums-data:/var/lib/lums:ro \
    -v "$PWD":/backup \
    lums:latest \
    sqlite3 /var/lib/lums/lums.db \
    ".backup '/backup/lums.db'"
```

Then verify:

```bash
sqlite3 ./lums.db "PRAGMA integrity_check;"
```

Expected:

```text
ok
```

Never publish the database backup itself unless it has been reviewed and sanitized.

---

# 30. Frontend / Theme Diagnostics

LUMS currently contains the following themes:

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

The technical identifier remains:

```text
admin
```

---

# 31. Frontend Source Paths

Source:

```text
/opt/lums-public/server/static/style.css
/opt/lums-public/server/static/theme.js
/opt/lums-public/server/static/network.js
```

Runtime:

```text
/app/server/static/style.css
/app/server/static/theme.js
/app/server/static/network.js
```

Check runtime files:

```bash
sudo docker exec lums \
    ls -lh \
    /app/server/static/style.css \
    /app/server/static/theme.js \
    /app/server/static/network.js
```

Check all relevant frontend files:

```bash
sudo docker exec lums \
    find /app/server/static -maxdepth 1 -type f \
    \( -name 'style.css' -o -name 'theme.js' -o -name 'network.js' \) \
    -print
```

---

# 32. Browser Theme Selection

Open the browser developer console.

Check:

```javascript
document.documentElement.dataset.theme
```

Expected values include:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

Check the stored theme:

```javascript
localStorage.getItem("lums-theme")
```

The value should correspond to the selected theme.

To remove the stored theme:

```javascript
localStorage.removeItem("lums-theme")
```

Then reload the page.

The Standard theme should act as the safe fallback.

---

# 33. Theme JavaScript

Check that `theme.js` exists:

```bash
sudo docker exec lums \
    test -f /app/server/static/theme.js \
    && echo "theme.js present" \
    || echo "theme.js missing"
```

Check the theme identifiers:

```bash
sudo docker exec lums \
    grep -nE 'standard|LUMSStadium|golf|nerd|geek|admin' \
    /app/server/static/theme.js
```

If a theme selector shows an incorrect option, first verify the runtime JavaScript rather than only the Git source.

---

# 34. Geek / The Living Network

The Geek theme uses:

```text
network.js
```

The network effect is intentionally limited to:

```text
theme = geek
```

Check the file:

```bash
sudo docker exec lums \
    test -f /app/server/static/network.js \
    && echo "network.js present" \
    || echo "network.js missing"
```

Check the network object:

```javascript
window.LumsNetwork
```

Expected:

```text
start
stop
destroy
```

Check the canvas:

```javascript
document.getElementById("lums-network-canvas")
```

The network effect should only run when the selected theme is:

```text
geek
```

It should not run for:

```text
standard
LUMSStadium
golf
nerd
admin
```

---

# 35. Geek Network Diagnostics

If the Geek background does not appear:

```text
1. Verify theme = geek
2. Verify network.js exists
3. Verify network.js is loaded
4. Verify LumsNetwork exists
5. Verify the network canvas exists
6. Check browser console
7. Check reduced-motion settings
8. Hard-refresh the browser
```

Browser check:

```javascript
document.documentElement.dataset.theme
```

Then:

```javascript
window.LumsNetwork
```

If reduced motion is enabled, the visual network effect may intentionally remain disabled.

---

# 36. Nerd Theme Diagnostics

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

Do not modify Geek or Enterprise Admin CSS while troubleshooting Nerd unless there is evidence that the shared base styles are involved.

---

# 37. Enterprise Admin Diagnostics

The Enterprise Admin theme uses:

```text
admin
```

The visual design is intentionally restrained.

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

If Enterprise Admin looks wrong, check:

```bash
sudo docker exec lums \
    grep -n -A10 -B4 \
    'LUMS // ENTERPRISE ADMIN' \
    /app/server/static/style.css
```

The Enterprise Admin CSS should remain scoped to:

```text
html[data-theme="admin"]
```

Do not modify other themes as a workaround.

---

# 38. Theme Isolation

Theme changes should not unintentionally modify unrelated themes.

The intended relationship is:

```text
standard
   │
   ├── base styles
   │
   ├── LUMSStadium
   ├── golf
   ├── nerd
   ├── geek
   └── admin
```

Special effects should remain scoped.

Examples:

```text
Geek → network.js
Nerd → Matrix/terminal effect
Enterprise Admin → restrained enterprise CSS
```

If changing Enterprise Admin unexpectedly changes another theme, check CSS selectors before changing JavaScript.

---

# 39. Frontend Deployment Sequence

After frontend changes:

```text
1. Edit source
2. Check source
3. Commit to Git
4. Build Docker image
5. Recreate container
6. Preserve lums-data
7. Test localhost
8. Test HTTPS
9. Hard-refresh browser
10. Verify theme behavior
```

Build:

```bash
cd /opt/lums-public
sudo docker build -t lums:latest .
```

Recreate:

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
sudo docker ps --filter name=lums
```

Then:

```bash
curl -I http://127.0.0.1:5050
```

---

# 40. Browser Cache

If the source is correct but the browser still displays an old version:

```text
1. Hard refresh
2. Open Developer Tools
3. Disable cache temporarily
4. Reload
5. Inspect loaded CSS/JS
```

Firefox:

```text
Ctrl+Shift+R
```

If necessary, inspect the actual loaded asset in Developer Tools → Network.

Do not immediately rebuild the entire application because of a browser cache problem.

---

# 41. Git Diagnostics

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
git log --oneline --decorate -5
```

Check differences:

```bash
git diff
```

---

# 42. Git Deployment Checks

Before deployment:

```bash
cd /opt/lums-public
git status -sb
git fetch origin
```

If the local tree is clean and the remote changes should be deployed:

```bash
git pull --ff-only
```

Then inspect:

```bash
git status -sb
```

Never overwrite local changes blindly.

---

# 43. Git Commit Identity

Current LUMS Git identity:

```text
Name:
NovaForgeCtrl
```

```text
Email:
232026481+NovaForgeCtrl@users.noreply.github.com
```

Check:

```bash
git config user.name
git config user.email
```

Do not include unrelated personal information in public documentation.

---

# 44. Container Recreation

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

Secrets:
 /etc/lums/docker/lums.env
```

A normal application update changes:

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

Do not add:

```bash
sudo docker volume rm lums-data
```

to normal deployment procedures.

That command is destructive.

---

# 45. Port Diagnostics

Check all relevant ports:

```bash
sudo ss -lntp | grep -E ':(22|80|443|5000|5050)\b'
```

Expected architecture:

```text
22
SSH

80
HTTP / optional redirect

443
HTTPS / Nginx

5050
LUMS host-side Flask binding

5000
Flask inside Docker
```

Port `5050` should normally be bound only to:

```text
127.0.0.1
```

Port `5000` is the internal container port.

---

# 46. Firewall Diagnostics

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

# 47. Permission Diagnostics

Check source permissions:

```bash
ls -la /opt/lums-public
```

Check TLS permissions:

```bash
sudo ls -la /etc/lums/tls/
```

Check agent files:

```bash
sudo ls -la /opt/lums-agent/
```

Do not make sensitive files world-readable as a troubleshooting workaround.

Avoid:

```bash
chmod 777
```

as a generic fix.

Determine which process actually needs access and correct that permission specifically.

---

# 48. Diagnostic Log Reference

## Docker

```bash
sudo docker logs --tail 200 lums
```

## Nginx

```bash
sudo tail -n 100 /var/log/nginx/error.log
```

## Agent

```bash
sudo journalctl -u lums-agent \
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
sudo journalctl -u nginx \
    --since "30 minutes ago" \
    --no-pager
```

---

# 49. Server Diagnostic Sequence

Run the following sequence when the server appears broken:

```bash
echo "=== Docker ==="
sudo docker ps --filter name=lums

echo
echo "=== Docker Logs ==="
sudo docker logs --tail 50 lums

echo
echo "=== Port 5050 ==="
sudo ss -lntp | grep ':5050' || true

echo
echo "=== Flask ==="
curl -I http://127.0.0.1:5050 || true

echo
echo "=== Nginx ==="
sudo nginx -t

echo
echo "=== Nginx Status ==="
sudo systemctl is-active nginx

echo
echo "=== LUMS Database ==="
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

This sequence does not expose credentials.

---

# 50. Client Diagnostic Sequence

On the client:

```bash
echo "=== Agent Service ==="
sudo systemctl is-active lums-agent

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
sudo journalctl -u lums-agent \
    --since "30 minutes ago" \
    --no-pager
```

The token value is intentionally never displayed.

---

# 51. Public Bug Reports

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

Replace sensitive values with placeholders:

```text
<LUMS_SERVER_IP>
<CLIENT_ID>
<JOB_ID>
<CLIENT_TOKEN>
<PACKAGE>
<USERNAME>
```

Do not post:

```bash
cat /etc/lums/docker/lums.env
```

or:

```bash
cat /etc/default/lums-agent
```

to a public issue.

Use presence-only diagnostics instead.

---

# 52. Known Installation Lessons

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

Passwords should continue to use the application's password hashing mechanism.

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

# 53. Final Checklist

## Server

```text
[ ] Docker container running
[ ] Correct image deployed
[ ] lums-data mounted
[ ] Flask reachable on 127.0.0.1:5050
[ ] Nginx running
[ ] nginx -t successful
[ ] HTTPS reachable
[ ] TLS certificate valid
[ ] SQLite integrity check successful
```

## Authentication

```text
[ ] Client exists
[ ] Token configuration exists
[ ] Token value not exposed
[ ] Authentication endpoint works
[ ] Authorization is checked separately
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
```

## Jobs

```text
[ ] Job created
[ ] Job queued
[ ] Agent retrieves job
[ ] Agent executes job
[ ] APT/dpkg succeeds
[ ] Result generated
[ ] Result reported
[ ] Server stores result
[ ] Frontend displays result
```

## Frontend

```text
[ ] style.css present
[ ] theme.js present
[ ] network.js present
[ ] index.html loads assets
[ ] client.html loads assets
[ ] localStorage theme is correct
[ ] Standard works
[ ] LUMSStadium works
[ ] Golf works
[ ] Nerd works
[ ] Geek works
[ ] Enterprise Admin works
```

## Geek

```text
[ ] theme = geek
[ ] network.js loaded
[ ] window.LumsNetwork exists
[ ] network canvas exists
[ ] reduced-motion setting checked
```

## Enterprise Admin

```text
[ ] theme = admin
[ ] Enterprise Admin CSS loaded
[ ] admin CSS remains scoped
[ ] no unintended theme changes
[ ] no unnecessary visual effects
```

## Security

```text
[ ] No tokens in documentation
[ ] No passwords in documentation
[ ] No private keys in documentation
[ ] No session cookies in bug reports
[ ] No database dumps in public issues
[ ] Diagnostic commands redact secrets
```

---

# 54. Final Principles

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

# 55. Current Architecture Summary

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
                         │ Flask :5000       │
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
             └── network.js
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
/etc/lums/docker/lums.env
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
