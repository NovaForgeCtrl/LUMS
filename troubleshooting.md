# LUMS Troubleshooting Guide

## Linux Update Management Server

This document helps diagnose common LUMS problems.

The most important rule is:

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

---

# 1. Troubleshooting Strategy

LUMS consists of several layers:

```text
┌───────────────────────────┐
│        Web Browser        │
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│          HTTPS            │
│         Nginx :443        │
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│          Flask            │
│      127.0.0.1:5000       │
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│          SQLite           │
└───────────────────────────┘

              ▲
              │
        HTTPS + Token
              │
              │
┌─────────────┴─────────────┐
│       Linux Agent         │
│                           │
│ Python / APT / dpkg       │
└───────────────────────────┘
```

Test the layers in this order:

```text
Network
   ↓
HTTPS / TLS
   ↓
Nginx
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

Do not skip directly to reinstalling components.

---

# 2. LUMS Does Not Start

Check:

```bash
sudo systemctl status lums.service
```

Then:

```bash
sudo journalctl \
    -u lums.service \
    -n 100 \
    --no-pager
```

Look for messages such as:

```text
ModuleNotFoundError
Permission denied
file not found
secret missing
database error
```

---

# 3. Missing LUMS Secret

If the service reports a missing secret, check:

```bash
sudo ls -l /etc/lums/lums.env
```

Check that the variable exists without printing it:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' /etc/lums/lums.env \
    && echo "Secret vorhanden" \
    || echo "Secret fehlt"
```

Expected ownership:

```text
root:lums
```

Expected permissions:

```text
640
```

The secret itself must never be copied into documentation or bug reports.

---

# 4. Python Module Missing

If logs contain:

```text
ModuleNotFoundError
```

check installed packages.

Flask:

```bash
python3 -c "import flask; print(flask.__version__)"
```

Argon2:

```bash
python3 -c "import argon2; print('argon2 OK')"
```

If Flask is missing:

```bash
sudo apt install -y python3-flask
```

If Argon2 is missing:

```bash
sudo apt install -y python3-argon2
```

---

# 5. Flask Health Check Fails

Run locally:

```bash
curl -i http://127.0.0.1:5000/api/health
```

If this fails:

```bash
sudo systemctl status lums.service
```

Then:

```bash
sudo ss -lntp | grep ':5000'
```

If nothing is listening, Flask is not running correctly.

---

# 6. Flask Is Listening on the Wrong Address

Correct:

```text
127.0.0.1:5000
```

Potentially unsafe:

```text
0.0.0.0:5000
```

Check:

```bash
sudo ss -lntp | grep ':5000'
```

If Flask is externally exposed, investigate the application startup configuration immediately.

The expected architecture is:

```text
Client
   │
   │ HTTPS
   ▼
Nginx :443
   │
   │ localhost
   ▼
Flask 127.0.0.1:5000
```

Port `5000` should not be directly accessible from the network.

---

# 7. Nginx Does Not Start

Test:

```bash
sudo nginx -t
```

Then:

```bash
sudo systemctl status nginx
```

Logs:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

If `nginx -t` fails, do not reload Nginx until the configuration problem has been fixed.

---

# 8. Nginx Returns 502 Bad Gateway

A `502 Bad Gateway` normally means Nginx cannot reach Flask.

Test Flask directly:

```bash
curl http://127.0.0.1:5000/api/health
```

If this fails:

```bash
sudo systemctl status lums.service
```

If Flask works, inspect Nginx:

```bash
sudo nginx -t
```

Verify that the proxy points to:

```text
proxy_pass http://127.0.0.1:5000;
```

Expected flow:

```text
Browser
   ↓
Nginx :443
   ↓
127.0.0.1:5000
   ↓
Flask
```

---

# 9. HTTPS Does Not Work

Test locally:

```bash
curl -k -i https://127.0.0.1/api/health
```

If it works locally but not remotely, investigate:

```text
firewall
network
routing
DNS
```

Check:

```bash
sudo ufw status verbose
```

Check:

```bash
sudo ss -lntp | grep ':443'
```

---

# 10. Certificate Error

Inspect:

```bash
openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -dates
```

Inspect SAN:

```bash
openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -ext subjectAltName
```

The hostname or IP used by the client must match a SAN.

For example, if the agent connects to:

```text
https://192.168.2.134
```

the certificate should contain:

```text
IP Address:192.168.2.134
```

---

# 11. Agent Reports `CERTIFICATE_VERIFY_FAILED`

Check:

```bash
ls -l /opt/lums-agent/lums-ca.crt
```

Check configuration:

```bash
sudo grep '^LUMS_CA_FILE=' /etc/default/lums-agent
```

Expected:

```text
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

Test the certificate:

```bash
openssl x509 \
    -in /opt/lums-agent/lums-ca.crt \
    -noout \
    -subject \
    -dates
```

Do not solve the problem by permanently disabling certificate verification.

For diagnosis, distinguish between:

```text
TLS connection works
```

and:

```text
TLS certificate is trusted
```

These are not the same thing.

---

# 12. Agent Cannot Reach the Server

From the client:

```bash
ping SERVER_IP
```

Then:

```bash
curl -k https://SERVER_IP/api/health
```

If ping works but HTTPS does not:

```bash
sudo ufw status
```

Check the server:

```bash
sudo ss -lntp | grep ':443'
```

The important distinction is:

```text
Ping works
   ≠
HTTPS works
```

ICMP connectivity only proves that the host can be reached using ICMP.

---

# 13. Agent Returns `401 Unauthorized`

A `401 Unauthorized` means that the API rejected the authentication credentials.

First check that the token exists:

```bash
sudo grep -q '^LUMS_TOKEN=.' /etc/default/lums-agent \
    && echo "Token vorhanden" \
    || echo "Token fehlt"
```

Do not print the token.

Check the base URL:

```bash
sudo grep '^LUMS_BASE=' /etc/default/lums-agent
```

Expected example:

```text
LUMS_BASE=https://SERVER_IP
```

Possible causes:

```text
token missing
wrong token
wrong token hash in database
token revoked
client disabled
client does not exist
```

## Known LUMS installation issue

During the initial LUMS installation, a `401 Unauthorized` was caused by the client being registered with an authentication value that did not match the format expected by the existing API security logic.

The API expected the client token to be represented as a SHA-256 hexadecimal digest.

The relevant database is:

```text
/var/lib/lums/lums.db
```

The existing security implementation should always be inspected before changing the database manually.

Do not blindly replace authentication values with a different hashing scheme.

---

# 14. Agent Token Hash Mismatch

If the token itself is correct but the API continues returning:

```text
401 Unauthorized
```

investigate the complete authentication chain:

```text
Agent token
      ↓
/etc/default/lums-agent
      ↓
API authentication
      ↓
Token processing
      ↓
SQLite client record
      ↓
Client enabled state
```

The important point is that the token stored by the agent and the authentication value stored by the server must correspond to the implementation in `security.py`.

Inspect the relevant code before modifying the database.

The database is:

```text
/var/lib/lums/lums.db
```

If a manual correction is required, create a backup first.

---

# 15. Missing `LUMS_TOKEN` During Manual Agent Start

A common source of confusion is:

```bash
python3 /opt/lums-agent/agent.py
```

returning an error that:

```text
LUMS_TOKEN
```

is missing.

This does not necessarily mean that the token is missing from the configuration file.

The problem can be that `/etc/default/lums-agent` was not loaded into the current shell environment.

The configuration file contains values such as:

```text
LUMS_BASE=https://SERVER_IP
LUMS_TOKEN=CLIENT_TOKEN
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

A direct Python invocation does not automatically load this file.

For a manual test, load the environment first:

```bash
sudo bash -c '
set -a
source /etc/default/lums-agent
python3 /opt/lums-agent/agent.py
'
```

Alternatively, explicitly pass the variables:

```bash
sudo env \
    LUMS_BASE="https://SERVER_IP" \
    LUMS_TOKEN="$(sudo awk -F= '/^LUMS_TOKEN=/{print $2}' /etc/default/lums-agent)" \
    LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt" \
    python3 /opt/lums-agent/agent.py
```

This distinction is important:

```text
/etc/default/lums-agent exists
        │
        └── does not mean
            │
            ▼
Python automatically loaded it
```

---

# 16. Agent Configuration Is Incomplete

Check:

```bash
sudo grep -E '^(LUMS_BASE|LUMS_TOKEN|LUMS_CA_FILE)=' \
    /etc/default/lums-agent
```

Expected structure:

```text
LUMS_BASE=https://SERVER_IP
LUMS_TOKEN=CLIENT_TOKEN
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

Verify the token without displaying it:

```bash
sudo grep -q '^LUMS_TOKEN=.' /etc/default/lums-agent \
    && echo "Token vorhanden"
```

Protect the file:

```bash
sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

---

# 17. Agent Returns `403 Forbidden`

A `403` can mean that the authenticated client attempted to access another client's resource.

For example:

```text
Client 1
   │
   └── requests Client 2 resource
```

The server should reject this.

Check the client ID being used.

Do not interpret a `403` as a network or TLS problem.

At this stage:

```text
Network        ✓
TLS            ✓
Authentication ✓
Authorization  ✗
```

is a useful diagnostic model.

---

# 18. `/api/client/me` Fails

Test through the installed agent:

```bash
sudo env \
    LUMS_BASE="https://SERVER_IP" \
    LUMS_TOKEN="$(sudo awk -F= '/^LUMS_TOKEN=/{print $2}' /etc/default/lums-agent)" \
    LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt" \
    python3 - <<'PY'
import sys

sys.path.insert(0, "/opt/lums-agent")

import agent

print(agent.get_client())
PY
```

If this fails, investigate in this order:

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

---

# 19. Agent Sends Report but No Updates Appear

Check the client directly:

```bash
apt list --upgradable 2>/dev/null
```

Count:

```bash
apt list --upgradable 2>/dev/null | tail -n +2 | wc -l
```

If:

```text
0
```

the client currently has no available updates.

If updates are listed locally but not visible in LUMS, investigate:

```text
agent report
API endpoint
client ID
database
server-side inventory
```

---

# 20. LUMS Shows Old Updates

LUMS stores update information from the latest client report.

Run:

```bash
sudo systemctl start lums-agent.service
```

Then check:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

The report should update the server inventory.

---

# 21. Agent Timer Does Not Run

Check:

```bash
systemctl status lums-agent.timer
```

Then:

```bash
systemctl list-timers lums-agent.timer
```

Check that the timer exists:

```bash
ls -l /etc/systemd/system/lums-agent.timer
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Enable again:

```bash
sudo systemctl enable --now lums-agent.timer
```

---

# 22. Agent Service Does Not Run

Check:

```bash
sudo systemctl status lums-agent.service
```

Logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Check agent syntax:

```bash
sudo python3 -m py_compile /opt/lums-agent/agent.py
```

If the service fails but manual execution works, compare:

```text
environment variables
working directory
user
permissions
certificate path
systemd configuration
```

---

# 23. Timer Exists but Service Fails

Remember:

```text
timer
  ↓
starts
  ↓
service
```

The timer can be perfectly healthy while the service fails.

Therefore check both:

```bash
systemctl status lums-agent.timer
```

and:

```bash
systemctl status lums-agent.service
```

---

# 24. Update Job Remains `running`

First inspect the job:

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT id, client_id, status, created_at, started_at, finished_at FROM update_jobs ORDER BY id;"
```

Then inspect packages:

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT job_id, package, status, message FROM update_job_packages WHERE job_id=JOB_ID;"
```

Replace:

```text
JOB_ID
```

with the actual number.

Do not manually reset jobs without first determining why the agent stopped.

---

# 25. Package Update Failed

Check the agent logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Then manually test the affected package:

```bash
sudo apt-get install --only-upgrade PACKAGE
```

Replace:

```text
PACKAGE
```

with the package name.

Check APT:

```bash
sudo apt update
```

Then:

```bash
apt list --upgradable 2>/dev/null
```

---

# 26. Reboot Required

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

LUMS does not automatically reboot the system.

---

# 27. Database Problems

Check:

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"PRAGMA integrity_check;"
```

Expected:

```text
ok
```

If the result is not `ok`, stop making unnecessary changes and restore or investigate the database carefully.

Before manual database changes, create a backup.

---

# 28. Permission Problems

Check:

```bash
ls -ld /opt/lums-api
ls -ld /var/lib/lums
ls -l /var/lib/lums/lums.db
ls -l /etc/lums/lums.env
```

Typical ownership:

```text
/opt/lums-api
lums:lums

/var/lib/lums
lums:lums

/etc/lums
root:root
```

The secret:

```text
/etc/lums/lums.env
```

should normally be:

```text
root:lums
640
```

---

# 29. Agent Configuration Permissions

Check:

```bash
sudo ls -l /etc/default/lums-agent
```

Expected:

```text
-rw------- root root
```

This is important because the file contains the client token.

---

# 30. Git Problems

Check repository status:

```bash
cd /opt/lums-public
sudo git status
```

Check differences:

```bash
sudo git diff
```

Check whitespace:

```bash
sudo git diff --check
```

If Git reports:

```text
dubious ownership
```

the repository ownership/configuration needs to be reviewed.

Do not blindly disable Git security checks globally.

---

# 31. Git Commit Identity

If Git reports:

```text
Author identity unknown
```

configure an appropriate Git identity:

```bash
git config --global user.name "YOUR_NAME"
git config --global user.email "YOUR_EMAIL"
```

Then verify:

```bash
git config --global --list
```

Do not place real credentials or secrets into the repository.

---

# 32. Nginx Configuration Problems

Check:

```bash
sudo nginx -t
```

If this fails, do not reload Nginx until the syntax error is fixed.

Inspect:

```bash
sudo cat /etc/nginx/sites-available/lums
```

Check the enabled configuration:

```bash
ls -la /etc/nginx/sites-enabled/
```

---

# 33. Port Diagnostics

Check all listening ports:

```bash
sudo ss -lntp
```

Important ports:

```text
22
80
443
5000
```

Expected LUMS architecture:

```text
22      SSH
80      HTTP → HTTPS redirect
443     HTTPS / Nginx
5000    Flask / localhost only
```

---

# 34. Firewall Diagnostics

Check:

```bash
sudo ufw status verbose
```

If HTTPS is blocked, ensure:

```bash
sudo ufw allow 443/tcp
```

If SSH is blocked, ensure SSH is allowed **before** enabling or changing UFW remotely.

Do not expose port `5000` just to make troubleshooting easier.

---

# 35. Logs: Where to Look

| Problem            | First place to check                 |
| ------------------ | ------------------------------------ |
| LUMS not starting  | `journalctl -u lums.service`         |
| Missing secret     | `/etc/lums/lums.env` + LUMS journal  |
| Python module      | LUMS journal                         |
| Flask problem      | `curl` + LUMS journal                |
| Nginx not starting | `journalctl -u nginx`                |
| HTTPS problem      | Nginx + certificate                  |
| TLS verification   | Agent configuration + CA certificate |
| Agent connectivity | `curl`, `ss`, `ufw`                  |
| Authentication     | Agent configuration + API/server log |
| Authorization      | Client ID + API logic                |
| Agent failure      | `journalctl -u lums-agent.service`   |
| Timer problem      | `systemctl list-timers`              |
| Update failure     | Agent journal + APT                  |
| Database issue     | SQLite integrity check               |
| Git problem        | `git status` + `git diff`            |

---

# 36. Recommended Diagnostic Sequence

When reporting a LUMS problem, collect the following information.

## Server

```bash
sudo systemctl status lums.service --no-pager
```

```bash
sudo systemctl status nginx --no-pager
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

LUMS logs:

```bash
sudo journalctl \
    -u lums.service \
    -n 100 \
    --no-pager
```

Nginx logs:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

---

## Client

```bash
sudo systemctl status lums-agent.timer --no-pager
```

```bash
sudo systemctl status lums-agent.service --no-pager
```

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

```bash
apt list --upgradable 2>/dev/null
```

Check configuration without displaying the token:

```bash
sudo grep '^LUMS_BASE=' /etc/default/lums-agent
```

```bash
sudo grep '^LUMS_CA_FILE=' /etc/default/lums-agent
```

```bash
sudo grep -q '^LUMS_TOKEN=.' /etc/default/lums-agent \
    && echo "Token vorhanden" \
    || echo "Token fehlt"
```

---

# 37. Do Not Share Secrets in Bug Reports

Before posting logs publicly, remove:

```text
LUMS_SECRET_KEY
LUMS_TOKEN
passwords
private keys
```

Also review logs for:

```text
Authorization headers
session information
internal addresses
```

Never use a real client token as an example in documentation.

Use:

```text
CLIENT_TOKEN
```

instead.

---

# 38. Known Installation Lessons

The first LUMS installation exposed several problems that are worth documenting because they can otherwise look unrelated.

## 38.1 Authentication Hash

The client authentication value in SQLite must correspond to the hashing logic implemented by LUMS.

The relevant database is:

```text
/var/lib/lums/lums.db
```

Do not assume that a normal password hash can be substituted for the authentication format expected by the API.

---

## 38.2 Environment Variables

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

## 38.3 Manual Python Execution

This:

```bash
python3 /opt/lums-agent/agent.py
```

and this:

```bash
sudo systemctl start lums-agent.service
```

are not equivalent execution environments.

systemd can provide:

```text
environment
user
working directory
permissions
service configuration
```

A manual Python process does not automatically receive all of those settings.

---

## 38.4 Python Indentation Errors

Large Python blocks pasted directly into a terminal can produce:

```text
IndentationError
```

because Python uses indentation as part of its syntax.

For larger changes, prefer writing the complete file:

```bash
sudo tee /path/to/file.py > /dev/null <<'EOF'
...
EOF
```

This produces reproducible file contents and avoids accidental indentation damage.

---

## 38.5 Do Not Change Multiple Layers at Once

If HTTPS fails, do not simultaneously modify:

```text
Nginx
Flask
UFW
TLS
Agent
```

Instead:

```text
1. Test Flask
2. Test Nginx
3. Test HTTPS
4. Test client connectivity
5. Test TLS verification
6. Test authentication
7. Test authorization
8. Test reporting
```

This makes the actual cause much easier to identify.

---

# 39. Final Troubleshooting Checklist

```text
[ ] Is the LUMS service running?
[ ] Does Flask answer locally?
[ ] Is Flask bound only to 127.0.0.1?
[ ] Is Nginx running?
[ ] Does nginx -t succeed?
[ ] Does HTTPS work?
[ ] Does the certificate contain the correct SAN?
[ ] Is TCP 443 reachable?
[ ] Is the client registered?
[ ] Is the client enabled?
[ ] Does the token exist?
[ ] Does the token match the server authentication logic?
[ ] Does TLS verification succeed?
[ ] Does /api/client/me work?
[ ] Does the report work?
[ ] Does the timer exist?
[ ] Does the timer trigger the service?
[ ] Does APT see the expected updates?
[ ] Does the update job exist?
[ ] Did the package update succeed?
[ ] Was the result reported?
[ ] Was the post-update report sent?
[ ] Is the database healthy?
```

---

# 40. The Golden Rule

When something fails:

```text
Don't reinstall.
Don't disable security.
Don't use -k as a permanent solution.
Don't disable authentication.
Don't expose port 5000.
Don't paste secrets into bug reports.
Don't change five things at once.
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
