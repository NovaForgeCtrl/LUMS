# LUMS Troubleshooting Guide

> **Linux Update Management Server**
>
> A practical troubleshooting guide for diagnosing LUMS server, agent, authentication, TLS, database, Git and update-management problems.

---

## Golden Rule

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

LUMS consists of several independent components. A failure in one layer does not necessarily mean that the entire system is broken.

The recommended approach is:

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

# 1. Troubleshooting Strategy

The current LUMS architecture looks like this:

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
│          Flask            │
│      127.0.0.1:5000       │
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│          SQLite           │
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
└───────────────────────────┘
```

Troubleshoot in this order:

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

> [!IMPORTANT]
> Do not change multiple layers at the same time. Otherwise it becomes difficult to determine which change actually solved the problem.

---

# 2. Important LUMS Paths

Before troubleshooting, make sure the current paths are known.

## Server

| Component            | Path                               |
| -------------------- | ---------------------------------- |
| Git source           | `/opt/lums-public`                 |
| Deployed application | `/opt/lums-api`                    |
| Database             | `/var/lib/lums/lums.db`            |
| Server environment   | `/etc/lums.env`                    |
| Systemd service      | `/etc/systemd/system/lums.service` |
| TLS certificate      | `/etc/nginx/ssl/lums.crt`          |
| TLS private key      | `/etc/nginx/ssl/lums.key`          |

## Client

| Component           | Path                              |
| ------------------- | --------------------------------- |
| Agent source        | `/opt/lums-public/agent/agent.py` |
| Installed agent     | `/opt/lums-agent/agent.py`        |
| Agent configuration | `/etc/default/lums-agent`         |
| Agent service       | `lums-agent.service`              |
| Agent timer         | `lums-agent.timer`                |

> [!CAUTION]
> The following files contain runtime state or secrets and must not be overwritten by a normal Git deployment:
>
> * `/var/lib/lums/lums.db`
> * `/etc/lums.env`
> * `/etc/nginx/ssl/lums.key`
> * `/etc/default/lums-agent`

---

# 3. LUMS Does Not Start

Check the service:

```bash
sudo systemctl status lums.service
```

Check recent logs:

```bash
sudo journalctl \
    -u lums.service \
    -n 100 \
    --no-pager
```

Look for errors such as:

```text
ModuleNotFoundError
Permission denied
file not found
secret missing
database error
```

If the service fails immediately after a deployment, first check the Python syntax:

```bash
python3 -m py_compile \
    /opt/lums-api/app.py \
    /opt/lums-api/init_db.py
```

---

# 4. LUMS Service Keeps Restarting

Check:

```bash
sudo systemctl status lums.service
```

Then:

```bash
sudo journalctl \
    -u lums.service \
    -n 200 \
    --no-pager
```

Because the service uses:

```ini
Restart=on-failure
```

a repeated application failure can result in repeated restart attempts.

The important question is therefore not:

> Why does systemd restart it?

but:

> Why does the application exit?

Check the first actual Python or configuration error in the journal.

---

# 5. Missing LUMS Secret

The server environment file is:

```text
/etc/lums.env
```

Check that it exists:

```bash
sudo ls -l /etc/lums.env
```

Check whether the expected variable exists without displaying its value:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' /etc/lums.env \
    && echo "Secret vorhanden" \
    || echo "Secret fehlt"
```

The secret itself must never be copied into:

* documentation
* GitHub issues
* screenshots
* bug reports
* chat messages

> [!CAUTION]
> Never use `cat /etc/lums.env` in a public troubleshooting report.

---

# 6. Python Module Missing

If the journal contains:

```text
ModuleNotFoundError
```

check the relevant module.

Flask:

```bash
python3 -c "import flask; print(flask.__version__)"
```

Argon2:

```bash
python3 -c "import argon2; print('argon2 OK')"
```

The currently installed environment should provide the required Python dependencies.

If a dependency is actually missing, install the appropriate package and then retest the application.

> [!NOTE]
> Do not blindly reinstall the entire Python environment because of one missing module. First identify which module is missing and why.

---

# 7. Flask Health Check Fails

LUMS Flask listens locally on:

```text
127.0.0.1:5000
```

Test it directly:

```bash
curl -i http://127.0.0.1:5000/api/health
```

If this fails, check:

```bash
sudo systemctl status lums.service
```

Then:

```bash
sudo ss -lntp | grep ':5000'
```

If nothing is listening on port `5000`, Flask is not running correctly.

---

# 8. Flask Is Listening on the Wrong Address

The expected binding is:

```text
127.0.0.1:5000
```

The following would expose Flask directly to the network:

```text
0.0.0.0:5000
```

Check:

```bash
sudo ss -lntp | grep ':5000'
```

Expected architecture:

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

# 9. Nginx Does Not Start

Test the configuration:

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

If `nginx -t` fails:

> **Do not reload Nginx until the configuration problem has been fixed.**

---

# 10. Nginx Returns `502 Bad Gateway`

A `502 Bad Gateway` normally means that Nginx cannot reach the Flask application.

Test Flask directly:

```bash
curl http://127.0.0.1:5000/api/health
```

If this fails:

```bash
sudo systemctl status lums.service
```

If Flask works, check Nginx:

```bash
sudo nginx -t
```

The proxy should point to:

```text
http://127.0.0.1:5000
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

# 11. HTTPS Does Not Work

Check that Nginx is listening:

```bash
sudo ss -lntp | grep ':443'
```

Test locally:

```bash
curl -k -i https://127.0.0.1/api/health
```

Test using the server IP:

```bash
curl -k -i https://192.168.2.229/api/health
```

If the local test works but a client cannot connect, investigate:

```text
network
firewall
routing
client connectivity
```

Check UFW if it is in use:

```bash
sudo ufw status verbose
```

> [!NOTE]
> A successful local HTTPS test proves that Nginx and TLS are working locally. It does not prove that remote clients can reach TCP/443.

---

# 12. Certificate Error

The current certificate is:

```text
/etc/nginx/ssl/lums.crt
```

Inspect the certificate:

```bash
sudo openssl x509 \
    -in /etc/nginx/ssl/lums.crt \
    -noout \
    -subject \
    -dates
```

Inspect the SAN:

```bash
sudo openssl x509 \
    -in /etc/nginx/ssl/lums.crt \
    -noout \
    -ext subjectAltName
```

The current LUMS server address is:

```text
192.168.2.229
```

Therefore the certificate must contain:

```text
IP Address:192.168.2.229
```

as a Subject Alternative Name.

> [!IMPORTANT]
> The address used by the client must match a SAN in the certificate.

---

# 13. Agent Reports `CERTIFICATE_VERIFY_FAILED`

The agent configuration is:

```text
/etc/default/lums-agent
```

Check the CA configuration:

```bash
sudo grep '^LUMS_CA_FILE=' /etc/default/lums-agent
```

The current configuration should point to:

```text
/etc/nginx/ssl/lums.crt
```

on the client installation where that certificate has been copied appropriately.

Check the configured file:

```bash
sudo ls -l "$(sudo awk -F= '/^LUMS_CA_FILE=/{print $2}' /etc/default/lums-agent)"
```

Inspect the certificate:

```bash
sudo openssl x509 \
    -in /etc/nginx/ssl/lums.crt \
    -noout \
    -subject \
    -dates
```

> [!WARNING]
> Do not permanently disable certificate verification to solve a TLS problem.

The following are different states:

```text
TLS connection works
```

and:

```text
TLS certificate is trusted
```

A connection can succeed with verification disabled while the actual certificate trust configuration remains broken.

---

# 14. Agent Cannot Reach the Server

From the client, first test basic connectivity:

```bash
ping 192.168.2.229
```

Then test HTTPS:

```bash
curl -k https://192.168.2.229/api/health
```

If ping works but HTTPS does not:

```text
Ping works
   ≠
HTTPS works
```

Check the server:

```bash
sudo ss -lntp | grep ':443'
```

Then check the firewall:

```bash
sudo ufw status verbose
```

ICMP connectivity only proves that the host can be reached using ICMP.

---

# 15. Agent Returns `401 Unauthorized`

A `401 Unauthorized` means that the API rejected the authentication credentials.

First verify that a token exists without displaying it:

```bash
sudo grep -q '^LUMS_TOKEN=.' /etc/default/lums-agent \
    && echo "Token vorhanden" \
    || echo "Token fehlt"
```

Check the server URL:

```bash
sudo grep '^LUMS_BASE=' /etc/default/lums-agent
```

Expected structure:

```text
LUMS_BASE=https://192.168.2.229
```

Possible causes include:

```text
token missing
wrong token
wrong token hash
token revoked
client disabled
client does not exist
```

---

# 16. Client Authentication and SHA-256

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

Database:

```text
/var/lib/lums/lums.db
```

If the token itself appears correct but authentication still returns `401`, inspect the implementation before changing the database.

> [!CAUTION]
> Do not replace the token hash with a password hash or another hashing format simply because it looks more secure or familiar. The stored value must match the authentication implementation used by LUMS.

---

# 17. Agent Token Authentication Chain

When investigating authentication, check the complete chain:

```text
Agent token
      ↓
/etc/default/lums-agent
      ↓
Bearer Authorization header
      ↓
API authentication
      ↓
SHA-256 token processing
      ↓
SQLite client record
      ↓
enabled / revoked state
```

The important database:

```text
/var/lib/lums/lums.db
```

Before any manual database correction, create a backup.

---

# 18. Missing `LUMS_TOKEN` During Manual Agent Start

A common source of confusion is running:

```bash
python3 /opt/lums-agent/agent.py
```

and receiving an error that:

```text
LUMS_TOKEN
```

is missing.

This does not necessarily mean that the token is missing from:

```text
/etc/default/lums-agent
```

The problem may simply be that the environment file was not loaded into the current shell.

The file contains values such as:

```text
LUMS_BASE=https://192.168.2.229
LUMS_TOKEN=CLIENT_TOKEN
LUMS_CA_FILE=/etc/nginx/ssl/lums.crt
```

A direct Python invocation does not automatically load `/etc/default/lums-agent`.

For a manual test:

```bash
sudo bash -c '
set -a
source /etc/default/lums-agent
python3 /opt/lums-agent/agent.py
'
```

This is different from:

```bash
sudo systemctl start lums-agent.service
```

because systemd provides the service environment separately.

---

# 19. Agent Configuration Is Incomplete

Check the configuration structure:

```bash
sudo grep -E '^(LUMS_BASE|LUMS_CA_FILE)=' \
    /etc/default/lums-agent
```

Check that a token exists without printing it:

```bash
sudo grep -q '^LUMS_TOKEN=.' /etc/default/lums-agent \
    && echo "Token vorhanden" \
    || echo "Token fehlt"
```

Expected structure:

```text
LUMS_BASE=https://192.168.2.229
LUMS_CA_FILE=/etc/nginx/ssl/lums.crt
LUMS_TOKEN=CLIENT_TOKEN
```

Protect the configuration file appropriately:

```bash
sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

---

# 20. Agent Returns `403 Forbidden`

A `403 Forbidden` is different from a `401 Unauthorized`.

A useful model is:

```text
401
│
└── Authentication failed

403
│
└── Authentication succeeded,
    but the requested action is not authorized
```

For example:

```text
Client 1
   │
   └── requests Client 2 resource
```

The server should reject this.

At this stage:

```text
Network        ✓
TLS            ✓
Authentication ✓
Authorization  ✗
```

is a useful diagnostic model.

---

# 21. `/api/client/me` Fails

The authenticated client identity endpoint is:

```text
GET /api/client/me
```

If this endpoint fails, investigate:

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

A useful manual test is to execute the agent with its configured environment:

```bash
sudo bash -c '
set -a
source /etc/default/lums-agent
python3 /opt/lums-agent/agent.py
'
```

Then inspect the agent journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 22. Agent Sends Report but No Updates Appear

LUMS receives update information through the client report.

The inventory therefore represents the state reported by the client.

Check the client locally:

```bash
apt list --upgradable 2>/dev/null
```

Count available updates:

```bash
apt list --upgradable 2>/dev/null | tail -n +2 | wc -l
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

---

# 23. LUMS Shows Old Inventory

The LUMS inventory is based on the client's latest successful report.

Run the agent manually:

```bash
sudo systemctl start lums-agent.service
```

Then inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

A successful report should result in the server receiving the new client state.

---

# 24. Agent Timer Does Not Run

Check the timer:

```bash
systemctl status lums-agent.timer
```

List the timer:

```bash
systemctl list-timers --all | grep lums-agent
```

Check the unit:

```bash
systemctl cat lums-agent.timer
```

If the timer configuration was changed:

```bash
sudo systemctl daemon-reload
```

Enable and start it:

```bash
sudo systemctl enable --now lums-agent.timer
```

---

# 25. Agent Service Does Not Run

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

Check syntax:

```bash
python3 -m py_compile /opt/lums-agent/agent.py
```

If manual execution works but systemd execution fails, compare:

```text
environment
user
permissions
working directory
certificate path
systemd configuration
```

---

# 26. Timer Exists but Service Fails

Remember:

```text
lums-agent.timer
       │
       ▼
lums-agent.service
       │
       ▼
agent.py
```

The timer can be completely healthy while the service itself fails.

Therefore check both:

```bash
systemctl status lums-agent.timer
```

and:

```bash
systemctl status lums-agent.service
```

---

# 27. Update Job Remains `running`

First inspect the jobs:

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT id, client_id, status, created_at, started_at, finished_at FROM update_jobs ORDER BY id;"
```

Then inspect packages for the affected job:

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
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

# 28. Package Update Failed

Check the agent log:

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

with the affected package name.

Inspect available upgrades:

```bash
apt list --upgradable 2>/dev/null
```

> [!NOTE]
> This guide intentionally does not use `apt update`. Package-index maintenance is outside the LUMS troubleshooting workflow documented here.

---

# 29. Reboot Required

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

# 30. Database Problems

The LUMS database is:

```text
/var/lib/lums/lums.db
```

Check integrity:

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"PRAGMA integrity_check;"
```

Expected:

```text
ok
```

If the result is not:

```text
ok
```

stop making unnecessary changes.

Create a backup before further investigation:

```bash
sudo cp \
    /var/lib/lums/lums.db \
    /var/lib/lums/lums.db.before-troubleshooting
```

> [!CAUTION]
> Never perform structural database changes on the production database without a backup.

---

# 31. Permission Problems

Check the deployed application:

```bash
sudo ls -ld /opt/lums-api
```

Check the database:

```bash
sudo ls -ld /var/lib/lums
sudo ls -l /var/lib/lums/lums.db
```

Check the server environment:

```bash
sudo ls -l /etc/lums.env
```

Check TLS files:

```bash
sudo ls -l /etc/nginx/ssl/
```

The LUMS application and database are normally operated by:

```text
lums:lums
```

The server environment file is protected separately.

> [!IMPORTANT]
> Do not blindly change ownership of the complete `/etc`, `/opt` or `/var/lib` hierarchy. Change only the affected resource.

---

# 32. Agent Configuration Permissions

Check:

```bash
sudo ls -l /etc/default/lums-agent
```

The file contains the client token and should therefore not be world-readable.

A suitable restrictive configuration is:

```text
root:root
0600
```

If permissions were changed unintentionally:

```bash
sudo chown root:root /etc/default/lums-agent
```

```bash
sudo chmod 600 /etc/default/lums-agent
```

---

# 33. Git Problems

The source repository is:

```text
/opt/lums-public
```

Check status:

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
git rev-list --left-right --count HEAD...origin/main
```

Expected:

```text
0       0
```

This means the local branch and `origin/main` are synchronized.

> [!WARNING]
> Do not use `git reset --hard` or force-push as a routine troubleshooting method.

---

# 34. Git Repository Has Uncommitted Changes

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

# 35. Git Commit Identity

If Git reports:

```text
Author identity unknown
```

configure the repository identity appropriately.

For the LUMS project:

```bash
git config user.name "NovaForgeCtrl"
```

```bash
git config user.email "232026481+NovaForgeCtrl@users.noreply.github.com"
```

Verify:

```bash
git config --get user.name
```

```bash
git config --get user.email
```

Do not put passwords, tokens or private credentials into Git configuration or repository files.

---

# 36. Nginx Configuration Problems

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
sudo ls -la /etc/nginx/sites-enabled/
```

If the LUMS site configuration is known:

```bash
sudo cat /etc/nginx/sites-available/lums
```

Do not reload Nginx until:

```text
nginx -t
```

reports a successful configuration test.

---

# 37. Port Diagnostics

List listening TCP ports:

```bash
sudo ss -lntp
```

Important LUMS ports:

|   Port | Purpose                |
| -----: | ---------------------- |
|   `22` | SSH                    |
|   `80` | HTTP → HTTPS redirect  |
|  `443` | HTTPS / Nginx          |
| `5000` | Flask / localhost only |

Expected LUMS architecture:

```text
22      SSH
80      HTTP → HTTPS redirect
443     HTTPS / Nginx
5000    Flask / localhost only
```

> [!CAUTION]
> Do not expose port `5000` to the network just to simplify troubleshooting.

---

# 38. Firewall Diagnostics

Check UFW:

```bash
sudo ufw status verbose
```

If HTTPS is blocked, the firewall must allow TCP/443.

Before changing SSH firewall rules remotely, make sure SSH access remains available.

> [!WARNING]
> Never lock yourself out of the server by changing firewall rules remotely without verifying the current SSH access path.

---

# 39. Deployment Problems

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
rsync
 ↓
systemctl restart lums
 ↓
health check
```

Before deployment:

```bash
cd /opt/lums-public
```

Check:

```bash
git status
```

Fetch:

```bash
git fetch origin
```

Synchronize:

```bash
git pull --ff-only origin main
```

Check syntax:

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

Deploy the server code:

```bash
sudo rsync -a \
    --delete \
    --exclude='.git/' \
    /opt/lums-public/server/ \
    /opt/lums-api/
```

Restart:

```bash
sudo systemctl restart lums.service
```

Verify:

```bash
sudo systemctl status lums.service --no-pager
```

Finally:

```bash
curl -k https://192.168.2.229/api/health
```

> [!CAUTION]
> The deployment must not overwrite:
>
> * `/var/lib/lums/lums.db`
> * `/etc/lums.env`
> * `/etc/nginx/ssl/`
> * `/etc/default/lums-agent`

---

# 40. Logs: Where to Look

| Problem            | First place to check               |
| ------------------ | ---------------------------------- |
| LUMS not starting  | `journalctl -u lums.service`       |
| LUMS restarting    | LUMS journal                       |
| Missing secret     | `/etc/lums.env` + LUMS journal     |
| Python module      | LUMS journal                       |
| Flask problem      | `curl` + LUMS journal              |
| Nginx not starting | `journalctl -u nginx`              |
| HTTP 502           | Flask + Nginx                      |
| HTTPS problem      | Nginx + certificate                |
| TLS verification   | Agent config + certificate         |
| Agent connectivity | `curl`, `ss`, firewall             |
| `401 Unauthorized` | Token + authentication logic       |
| `403 Forbidden`    | Client authorization               |
| Agent failure      | `journalctl -u lums-agent.service` |
| Timer problem      | `systemctl list-timers`            |
| Update failure     | Agent journal + APT                |
| Job stuck          | SQLite + agent journal             |
| Database issue     | SQLite integrity check             |
| Git problem        | `git status` + `git diff`          |

---

# 41. Recommended Diagnostic Sequence

## Server

Start with:

```bash
sudo systemctl status lums.service --no-pager
```

Then:

```bash
sudo systemctl status nginx --no-pager
```

Then:

```bash
sudo nginx -t
```

Then:

```bash
sudo ss -lntp
```

Then:

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

Check the timer:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

Check the service:

```bash
sudo systemctl status lums-agent.service --no-pager
```

Check the logs:

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
sudo grep '^LUMS_BASE=' /etc/default/lums-agent
```

Check the CA path:

```bash
sudo grep '^LUMS_CA_FILE=' /etc/default/lums-agent
```

Check token presence without displaying it:

```bash
sudo grep -q '^LUMS_TOKEN=.' /etc/default/lums-agent \
    && echo "Token vorhanden" \
    || echo "Token fehlt"
```

---

# 42. Do Not Share Secrets in Bug Reports

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

# 43. Known LUMS Installation Lessons

The initial LUMS installation exposed several problems that are useful to document.

## 43.1 Client Authentication Hash

The API expects the client authentication value in the format implemented by the current security layer.

The current implementation uses a SHA-256 hexadecimal digest.

Database:

```text
/var/lib/lums/lums.db
```

A different password-hashing scheme must not be substituted.

---

## 43.2 Client Database Schema

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

## 43.3 TLS SAN

The original certificate did not contain the required IP SAN.

The certificate was regenerated with:

```text
subjectAltName = IP:192.168.2.229
```

The current certificate therefore matches the server address used by the LUMS client.

---

## 43.4 Agent Environment

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

## 43.5 `/api/client/me`

Authenticated agents use:

```text
/api/client/me
```

to obtain their authenticated client context.

This endpoint must not be confused with administrative client-management endpoints.

---

## 43.6 Manual Python Execution vs systemd

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

## 43.7 Python Indentation

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

# 44. Do Not Change Multiple Layers at Once

For example, if HTTPS fails, do not immediately change:

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

# 45. Final Troubleshooting Checklist

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
[ ] Does the token match the SHA-256 authentication logic?
[ ] Is the token revoked?
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
[ ] Is the SQLite database healthy?
[ ] Is the Git repository synchronized?
```

---

# 46. The Golden Rule

When something fails:

```text
Don't reinstall.
Don't disable security.
Don't permanently disable TLS verification.
Don't disable authentication.
Don't expose port 5000.
Don't paste secrets into bug reports.
Don't change five things at once.
Don't modify the production database without a backup.
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
> Centralize the management. Keep execution controlled.
> **Know what changed. Know where it happened.**
