# LUMS – Linux Update Management Server

> **Linux Update Management without the noise.**

LUMS is a lightweight Linux update management server for homelabs, test environments and small internal infrastructures.

It provides a central place to:

* register and monitor Linux clients
* collect operating-system and package information
* detect available updates
* create update jobs
* execute updates through the LUMS Agent
* record update results
* detect reboot requirements
* maintain update history
* provide an authenticated administration interface
* audit security-relevant actions

```text
┌─────────────────────────────────────────────────────────────┐
│                           LUMS                              │
│              Linux Update Management Server                │
│                                                             │
│  Clients → Inventory → Updates → Jobs → Results → History  │
│                                                             │
│  Built with curiosity, testing and a little controlled      │
│  chaos.                                                     │
└─────────────────────────────────────────────────────────────┘
```

**Signature:** `segfault // override`
*System Builder · Infrastructure / Security · Controlled Chaos*

---

# 🚀 Features

## Client Management

LUMS collects information about connected Linux systems:

* hostname
* IP address
* operating system
* kernel version
* architecture
* LUMS Agent version
* last-seen timestamp
* installed package count
* available update count
* calculated client status

Client status is currently determined by the last report:

| Last report          | Status    |
| -------------------- | --------- |
| ≤ 2 minutes          | `online`  |
| > 2 and ≤ 10 minutes | `unknown` |
| > 10 minutes         | `offline` |

---

## 📦 Package Inventory

The LUMS Agent can report installed packages.

LUMS stores:

```text
client
 └── installed packages
      ├── package
      └── version
```

The inventory is refreshed when a new client report is received.

---

## 🔄 Update Detection

The agent reports available updates to the LUMS server.

For each update LUMS stores:

* package name
* installed version
* available version
* client

Example:

```text
openssl
    installed: 3.0.x
    available: 3.0.y
```

---

## 🛠 Update Jobs

Administrators can create update jobs for individual clients.

A job contains:

* target client
* selected packages
* installed versions
* target versions
* current job status
* creation timestamp
* start timestamp
* finish timestamp
* reboot requirement

Job states include:

```text
pending
running
success
partial
failed
```

---

## ♻️ Reboot Detection

The LUMS Agent can report whether a system reboot is required after an update.

The result is stored together with the update job and update history.

---

# 🧭 Architecture

```text
                         ┌──────────────────────┐
                         │       LUMS Server    │
                         │                      │
                         │ Flask Web Interface  │
                         │ REST API             │
                         │ Authentication       │
                         │ SQLite               │
                         │ Audit Logging        │
                         └──────────┬───────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
                 ▼                  ▼                  ▼
          ┌────────────┐     ┌────────────┐     ┌────────────┐
          │ Linux VM   │     │ Linux PC   │     │ Linux      │
          │ LUMS Agent │     │ LUMS Agent │     │ Server     │
          └────────────┘     └────────────┘     └────────────┘
                 │                  │                  │
                 └──────────────────┴──────────────────┘
                              Reports
                              Updates
                              Jobs
                              Results
```

Typical production-style deployment:

```text
                    Client
                      │
                      │ HTTPS
                      ▼
              ┌───────────────┐
              │     Nginx     │
              │ TLS endpoint  │
              └───────┬───────┘
                      │
                      │ localhost
                      ▼
              ┌───────────────┐
              │ Flask / LUMS  │
              │ 127.0.0.1:5000│
              └───────┬───────┘
                      │
                      ▼
                SQLite database
```

Nginx is therefore the external HTTPS endpoint while Flask remains bound to localhost.

---

# 📁 Project Structure

The repository is organized as follows:

```text
LUMS/
├── agent/
│   ├── agent.py
│   ├── lums-agent.env.example
│   └── lums-agent.service
│
├── docs/
│
├── scripts/
│
├── server/
│   ├── app.py
│   ├── init_db.py
│   ├── security.py
│   ├── security_migration.py
│   ├── create_admin.py
│   │
│   ├── static/
│   │   ├── app.js
│   │   ├── client.js
│   │   └── style.css
│   │
│   └── templates/
│       ├── client.html
│       ├── index.html
│       └── login.html
│
├── .gitignore
├── LICENSE
└── README.md
```

---

# 💻 Requirements

## Server

Recommended:

* Ubuntu Server 26.04 LTS
* Python 3
* SQLite 3
* Nginx
* systemd
* Git
* OpenSSL

Python packages:

```text
Flask
argon2-cffi / python3-argon2
```

The exact Python dependencies may depend on the distribution and installation method used.

---

## Clients

A LUMS client requires:

* Linux
* Python 3
* network connectivity to the LUMS server
* the LUMS Agent
* permission to query package information
* permission to execute package updates if update jobs are enabled

For Debian/Ubuntu systems, package management is based on APT.

---

# 🛠 Server Installation

The following procedure assumes a fresh Ubuntu Server.

## 1. Update the operating system

```bash
sudo apt update
sudo apt upgrade -y
```

Install required tools:

```bash
sudo apt install -y \
    git \
    python3 \
    python3-pip \
    python3-venv \
    python3-argon2 \
    sqlite3 \
    nginx \
    openssl
```

Verify:

```bash
python3 --version
sqlite3 --version
nginx -v
git --version
```

---

# 👤 Create the LUMS Service Account

LUMS should not run as root.

Create a dedicated service account:

```bash
sudo useradd \
    --system \
    --create-home \
    --home-dir /home/lums \
    --shell /usr/sbin/nologin \
    lums
```

Verify:

```bash
getent passwd lums
```

Expected conceptually:

```text
lums:x:...:...::/home/lums:/usr/sbin/nologin
```

The account is intentionally not allowed to log in interactively.

---

# 📂 Create LUMS Directories

Create the application and data directories:

```bash
sudo mkdir -p /opt/lums-api
sudo mkdir -p /var/lib/lums
sudo mkdir -p /etc/lums
sudo mkdir -p /etc/lums/tls
```

Set ownership:

```bash
sudo chown -R lums:lums /opt/lums-api
sudo chown -R lums:lums /var/lib/lums
```

Restrict access:

```bash
sudo chmod 750 /opt/lums-api
sudo chmod 750 /var/lib/lums
sudo chmod 750 /etc/lums
sudo chmod 750 /etc/lums/tls
```

---

# 📥 Clone the Repository

Clone the repository into a location used for source/deployment management:

```bash
cd /opt
git clone https://github.com/NovaForgeCtrl/LUMS.git lums-public
```

Enter the repository:

```bash
cd /opt/lums-public
```

Check the current branch:

```bash
git branch
```

Switch to `main`:

```bash
git checkout main
```

Update:

```bash
git pull --ff-only origin main
```

---

# 📦 Deploy the Server Application

The repository and production deployment directory are intentionally separated.

Example:

```text
/opt/lums-public   → Git repository
/opt/lums-api      → deployed application
```

Deploy:

```bash
sudo rsync -a --delete \
    --exclude='.git/' \
    /opt/lums-public/server/ \
    /opt/lums-api/
```

Set ownership:

```bash
sudo chown -R lums:lums /opt/lums-api
```

Set directory permissions:

```bash
sudo chmod 750 /opt/lums-api
```

---

# 🔐 Configure the Server Secret

LUMS requires:

```text
LUMS_SECRET_KEY
```

The secret must **never** be committed to Git.

Generate a strong random value:

```bash
openssl rand -hex 64
```

Create the environment file:

```bash
sudo touch /etc/lums/lums.env
sudo chown root:lums /etc/lums/lums.env
sudo chmod 640 /etc/lums/lums.env
```

Edit the file using a root shell:

```bash
sudo sh -c 'cat > /etc/lums/lums.env <<EOF
LUMS_SECRET_KEY=REPLACE_WITH_A_RANDOM_SECRET
EOF'
```

Replace the placeholder with the generated secret.

Do not print the file contents into logs or documentation.

Verify only the permissions:

```bash
ls -l /etc/lums/lums.env
```

Expected:

```text
-rw-r----- root lums ... /etc/lums/lums.env
```

---

# 🗄 Database

The default LUMS database location is:

```text
/var/lib/lums/lums.db
```

The application expects the database to be available there.

Initialize the database using the project's database initialization script:

```bash
cd /opt/lums-api
sudo -u lums python3 init_db.py
```

Check:

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db '.tables'
```

Depending on the current schema, tables include structures such as:

```text
clients
available_updates
installed_packages
update_jobs
update_job_packages
update_history
users
audit_log
schema_migrations
```

---

# 🔐 Security Database Migration

LUMS contains a security foundation migration.

Run:

```bash
cd /opt/lums-api
sudo -u lums python3 security_migration.py
```

The migration is designed to be idempotent.

That means it can safely determine whether the migration has already been applied.

The migration creates the security-related structures and adds security fields to the client database.

---

# 👨‍💻 Create the Administrator

Create the initial administrator using:

```bash
cd /opt/lums-api
sudo -u lums python3 create_admin.py
```

The administrator password should:

* be long
* be unique
* not be stored in Git
* not be shared in chat logs
* not be placed into the README
* not be stored in plaintext

Passwords are stored using Argon2id hashing.

LUMS does not need the administrator's plaintext password after account creation.

---

# 🔒 Authentication

LUMS separates browser authentication from agent authentication.

## Administrator

The web interface uses:

```text
username
password
server-side session
CSRF protection
```

The session cookie is configured with:

```text
HttpOnly
Secure
SameSite=Strict
```

The server session lifetime is five minutes.

The browser interface additionally performs inactivity handling.

---

# 🛡 Password Security

Passwords are hashed using Argon2.

The application also checks whether an existing password hash needs to be upgraded:

```text
password
   │
   ▼
Argon2 verification
   │
   ├── valid
   │
   └── hash parameters outdated
             │
             ▼
        rehash password
```

Plaintext passwords are never stored in the database.

---

# 🧱 CSRF Protection

State-changing browser operations use CSRF protection.

Examples:

```text
POST /logout
POST /api/clients/<id>/update-jobs
```

A missing or invalid CSRF token results in a rejected request.

The login route is treated separately because a new session does not yet exist.

---

# 🔑 Client Authentication

LUMS contains infrastructure for individual client tokens.

The security design uses:

```text
Client
   │
   │ Bearer token
   ▼
LUMS
   │
   ▼
SHA-256 token hash
   │
   ▼
Client record
```

The server stores the hash rather than the plaintext token.

A token can be:

* generated randomly
* associated with one client
* revoked
* disabled
* verified using constant-time comparison

Example HTTP header:

```http
Authorization: Bearer CLIENT_TOKEN
```

## Important current implementation note

The current `server/security.py` already contains the client-token authentication foundation.

However, the currently documented `app.py` must be checked before claiming that every agent endpoint is protected by that mechanism.

In particular, the following agent-facing endpoints must be reviewed before a production deployment:

```text
POST /api/report

GET /api/clients/<client_id>/update-jobs/pending

POST /api/update-jobs/<job_id>/result
```

The README intentionally does **not** claim that these endpoints are fully token-protected unless the corresponding decorators and client/job authorization checks are active in the deployed version.

This distinction matters.

**Security documentation must describe the code that actually runs.**

---

# ⚙️ systemd Service

The recommended production service runs LUMS as the unprivileged `lums` user.

Create:

```bash
sudo tee /etc/systemd/system/lums.service > /dev/null <<'EOF'
[Unit]
Description=LUMS Linux Update Management Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple

User=lums
Group=lums

WorkingDirectory=/opt/lums-api

EnvironmentFile=/etc/lums/lums.env

ExecStart=/usr/bin/python3 /opt/lums-api/app.py

Restart=on-failure
RestartSec=5

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

ReadWritePaths=/var/lib/lums

[Install]
WantedBy=multi-user.target
EOF
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Enable:

```bash
sudo systemctl enable lums
```

Start:

```bash
sudo systemctl start lums
```

Check:

```bash
sudo systemctl status lums
```

Follow logs:

```bash
sudo journalctl -u lums -f
```

---

# 🩺 First Service Test

Before configuring Nginx, verify that Flask itself works.

Check listening sockets:

```bash
sudo ss -ltnp | grep 5000
```

Expected:

```text
127.0.0.1:5000
```

Test locally:

```bash
curl http://127.0.0.1:5000/api/health
```

Expected:

```json
{
  "service": "LUMS API",
  "status": "ok"
}
```

If this fails, **do not continue with Nginx troubleshooting yet**.

Fix Flask/systemd first.

---

# 🌐 Nginx Configuration

Nginx acts as the HTTPS reverse proxy.

Create:

```bash
sudo tee /etc/nginx/sites-available/lums > /dev/null <<'EOF'
server {
    listen 80;
    server_name SERVER_IP;

    location /aptly/ {
        alias /srv/lums/aptly/public/;
        autoindex on;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name SERVER_IP;

    ssl_certificate     /etc/lums/tls/lums.crt;
    ssl_certificate_key /etc/lums/tls/lums.key;

    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://127.0.0.1:5000;

        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
EOF
```

Replace:

```text
SERVER_IP
```

with the actual server address.

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

Remove the default site if necessary:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

Test:

```bash
sudo nginx -t
```

Only if the test succeeds:

```bash
sudo systemctl reload nginx
```

---

# 🔒 TLS Certificate

For an internal lab, a self-signed certificate can be used.

Create:

```bash
sudo openssl req \
    -x509 \
    -nodes \
    -newkey rsa:4096 \
    -keyout /etc/lums/tls/lums.key \
    -out /etc/lums/tls/lums.crt \
    -days 825 \
    -subj "/CN=SERVER_IP" \
    -addext "subjectAltName=IP:SERVER_IP"
```

Replace `SERVER_IP`.

Protect the private key:

```bash
sudo chown root:root /etc/lums/tls/lums.key
sudo chmod 600 /etc/lums/tls/lums.key
```

Certificate:

```bash
sudo chmod 644 /etc/lums/tls/lums.crt
```

Check:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -dates
```

For production environments, use an appropriate trusted certificate instead of a self-signed certificate.

---

# 🌍 Web Interface

Once Nginx and TLS are running:

```text
https://SERVER_IP/
```

The application redirects unauthenticated users to:

```text
/login
```

The login page provides:

```text
segfault // override

SECURE ACCESS

Username
Password

AUTHENTICATE
```

After successful authentication, the user is redirected to the dashboard.

---

# 🤖 LUMS Agent

The agent runs on Linux clients.

Typical architecture:

```text
LUMS Agent
     │
     ├── hostname
     ├── IP
     ├── OS
     ├── kernel
     ├── architecture
     ├── agent version
     ├── installed packages
     └── available updates
              │
              ▼
          LUMS Server
```

The agent should communicate with the server using the configured LUMS base URL.

Example:

```text
https://SERVER_IP
```

---

# 📄 Agent Configuration

Example configuration file:

```text
/etc/lums/lums-agent.env
```

Example:

```ini
LUMS_BASE=https://SERVER_IP
```

If client-token authentication is enabled for the deployed agent/API version, the token must be stored separately and securely.

Do not commit real tokens to Git.

---

# 🔑 Secure Client Token Storage

Never put a real token into:

```text
Git
README.md
shell history
chat messages
public configuration
world-readable files
```

A recommended configuration file:

```bash
sudo touch /etc/lums/lums-agent.env
sudo chown root:root /etc/lums/lums-agent.env
sudo chmod 600 /etc/lums/lums-agent.env
```

Example:

```ini
LUMS_BASE=https://SERVER_IP
LUMS_CLIENT_TOKEN=REPLACE_WITH_CLIENT_TOKEN
```

Then:

```bash
sudo chmod 600 /etc/lums/lums-agent.env
```

Only privileged users should be able to read the file.

---

# 🖥️ First Client Registration

The current application automatically creates or updates a client when `/api/report` receives a report.

The client is identified by hostname in the current implementation.

Conceptually:

```text
Agent starts
    │
    ▼
Collect system information
    │
    ▼
POST /api/report
    │
    ▼
LUMS
    │
    ├── hostname already known?
    │       │
    │       ├── no → create client
    │       └── yes → update client
    │
    ▼
Save updates
    │
    ▼
Save package inventory
```

This is the current registration mechanism.

If explicit token-based enrollment is introduced later, the documentation should be updated to describe the exact enrollment flow rather than assuming one exists.

---

# 🔄 Agent Execution

The agent can be run manually during testing:

```bash
sudo python3 /path/to/agent.py
```

For production-style operation, use systemd.

Example:

```bash
sudo cp agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable lums-agent
sudo systemctl start lums-agent
```

Check:

```bash
sudo systemctl status lums-agent
```

Logs:

```bash
sudo journalctl -u lums-agent -f
```

---

# ⏱️ Periodic Agent Execution

A periodic agent can be implemented using systemd timers.

Example architecture:

```text
lums-agent.timer
       │
       ▼
lums-agent.service
       │
       ▼
collect information
       │
       ▼
send report
```

Check timers:

```bash
systemctl list-timers
```

If the timer is enabled:

```bash
sudo systemctl enable --now lums-agent.timer
```

---

# 📡 REST API

## Health

```http
GET /api/health
```

Returns service health.

Example:

```json
{
  "status": "ok",
  "service": "LUMS API"
}
```

---

## Client Report

```http
POST /api/report
```

Receives:

* hostname
* IP
* OS
* kernel
* architecture
* agent version
* updates
* installed packages

Example conceptual payload:

```json
{
  "hostname": "client01",
  "ip": "192.168.2.210",
  "os": "Ubuntu 26.04.1 LTS",
  "kernel": "6.x",
  "architecture": "x86_64",
  "agent_version": "1.0",
  "updates": [],
  "packages": {}
}
```

---

## List Clients

```http
GET /api/clients
```

Requires administrator authentication.

---

## Client Details

```http
GET /api/clients/<client_id>
```

---

## Client Updates

```http
GET /api/clients/<client_id>/updates
```

---

## Installed Packages

```http
GET /api/clients/<client_id>/packages
```

---

## Create Update Job

```http
POST /api/clients/<client_id>/update-jobs
```

Requires administrator authentication and CSRF protection.

Example:

```json
{
  "packages": [
    "openssl",
    "curl"
  ]
}
```

---

## Pending Update Job

```http
GET /api/clients/<client_id>/update-jobs/pending
```

Used by the agent to claim the next pending job.

The implementation uses a SQLite transaction with:

```sql
BEGIN IMMEDIATE
```

to reduce the risk of two agents claiming the same pending job simultaneously.

---

## Update Job Result

```http
POST /api/update-jobs/<job_id>/result
```

Example:

```json
{
  "status": "success",
  "reboot_required": false,
  "packages": [
    {
      "package": "openssl",
      "status": "success",
      "message": "Updated successfully"
    }
  ]
}
```

---

## Update Job Details

```http
GET /api/update-jobs/<job_id>
```

---

## Client Update History

```http
GET /api/clients/<client_id>/update-history
```

---

## Global Update History

```http
GET /api/update-history
```

---

# 🗃 Database Model

The database contains the core LUMS state.

Conceptually:

```text
clients
   │
   ├── installed_packages
   │
   ├── available_updates
   │
   └── update_jobs
          │
          └── update_job_packages
                  │
                  ▼
             update_history
```

Security data:

```text
users
   │
   └── audit_log

schema_migrations
```

---

# 🔐 Security Model

LUMS uses several layers of security.

## Passwords

Passwords use Argon2id.

---

## Sessions

Browser authentication uses server-side Flask sessions.

Cookie security:

```text
HttpOnly
Secure
SameSite=Strict
```

---

## CSRF

State-changing browser requests require a valid CSRF token.

---

## Client Tokens

The security foundation supports individual random client tokens.

Only token hashes are stored.

---

## Audit Logging

Security-relevant actions are recorded in:

```text
audit_log
```

Examples include:

```text
login
logout
failed login
administrative actions
```

---

## Security Headers

LUMS sets headers including:

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Permissions-Policy
Content-Security-Policy
```

The CSP restricts scripts, styles and connections to the application origin unless explicitly allowed.

---

# 🚨 Important Security Principle

LUMS should not be exposed directly to the public Internet without a deliberate security review.

The intended environments are:

* homelabs
* internal networks
* test environments
* small infrastructures
* learning environments

Security is implemented using defense in depth.

No software should be described as:

> 100% secure.

---

# 🧪 Testing

Before deploying a new version, test the individual layers separately.

---

## 1. Check Git

```bash
cd /opt/lums-public
git status
```

Expected:

```text
working tree clean
```

---

## 2. Check Python

```bash
python3 --version
```

---

## 3. Check Database

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

---

## 4. Check LUMS Service

```bash
sudo systemctl status lums
```

---

## 5. Check Flask

```bash
curl http://127.0.0.1:5000/api/health
```

Expected:

```json
{
  "status": "ok",
  "service": "LUMS API"
}
```

---

## 6. Check Nginx

```bash
sudo nginx -t
```

Expected:

```text
syntax is ok
test is successful
```

---

## 7. Check HTTPS

```bash
curl -k https://SERVER_IP/api/health
```

Expected:

```json
{
  "status": "ok",
  "service": "LUMS API"
}
```

---

# 🧪 Complete End-to-End Test

The complete test should verify the entire LUMS workflow.

```text
Server
  │
  ├── Flask running
  ├── SQLite working
  ├── Nginx working
  └── HTTPS working
          │
          ▼
       Client
          │
          ├── Agent starts
          ├── Report sent
          ├── Client appears
          ├── Updates detected
          │
          ▼
      Administrator
          │
          ├── Login
          ├── Select client
          ├── Select update
          └── Create job
                  │
                  ▼
               Client
                  │
                  ├── Claims job
                  ├── Installs package
                  ├── Determines reboot requirement
                  └── Sends result
                          │
                          ▼
                        LUMS
                          │
                          ├── Job completed
                          └── History recorded
```

---

## Test 1 – Login

Open:

```text
https://SERVER_IP/login
```

Authenticate with the administrator account.

---

## Test 2 – Client Report

Run the agent manually on the client.

Check server logs:

```bash
sudo journalctl -u lums -f
```

Look for a client report.

---

## Test 3 – Client Appears

Open:

```text
https://SERVER_IP/
```

Verify the client appears in the dashboard.

Check its:

* hostname
* IP
* operating system
* kernel
* architecture
* agent version
* status

---

## Test 4 – Updates

Verify that available updates are visible.

---

## Test 5 – Create Job

Select one or more available updates and create an update job.

Verify that:

```text
status = pending
```

---

## Test 6 – Agent Claims Job

Run the agent.

The job should change:

```text
pending
   ↓
running
```

---

## Test 7 – Package Update

The agent executes the selected package update.

---

## Test 8 – Result

The client sends:

```text
success
partial
```

or:

```text
failed
```

The job should become completed.

---

## Test 9 – History

Open the update history.

Verify:

* client
* job ID
* status
* package count
* successful count
* failed count
* reboot requirement
* start time
* finish time

---

# 💾 Backup Before an Update

Always make a backup before changing the production deployment.

At minimum, back up:

```text
database
configuration
TLS material
deployment configuration
```

Create a backup directory:

```bash
sudo mkdir -p /var/lib/lums/backups
sudo chmod 700 /var/lib/lums/backups
```

Back up the database:

```bash
sudo cp \
    /var/lib/lums/lums.db \
    /var/lib/lums/backups/lums.db.$(date +%Y%m%d-%H%M%S)
```

Protect it:

```bash
sudo chmod 600 /var/lib/lums/backups/*
```

Verify the database:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

---

# 🧰 SQLite Online Backup

A safer SQLite-native backup can also be created:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    ".backup '/var/lib/lums/backups/lums.db.$(date +%Y%m%d-%H%M%S)'"
```

Afterward:

```bash
sudo ls -lh /var/lib/lums/backups/
```

---

# 🔄 Updating LUMS

Never update blindly.

First:

```bash
cd /opt/lums-public
git status
```

Make sure there are no unwanted local changes.

Fetch:

```bash
git fetch origin
```

Review:

```bash
git log --oneline HEAD..origin/main
```

If the changes are expected:

```bash
git pull --ff-only origin main
```

---

# 💾 Backup Before Deployment

Before replacing the deployed application:

```bash
sudo cp -a \
    /opt/lums-api \
    /opt/lums-api.backup-$(date +%Y%m%d-%H%M%S)
```

Then deploy:

```bash
sudo rsync -a --delete \
    --exclude='.git/' \
    /opt/lums-public/server/ \
    /opt/lums-api/
```

Restore ownership:

```bash
sudo chown -R lums:lums /opt/lums-api
```

---

# 🔄 Restart After Deployment

Check syntax first:

```bash
python3 -m py_compile /opt/lums-api/app.py
```

Then:

```bash
sudo systemctl restart lums
```

Check immediately:

```bash
sudo systemctl status lums
```

Then:

```bash
curl http://127.0.0.1:5000/api/health
```

Only after that:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

# 🚨 Server Does Not Start

If:

```bash
sudo systemctl restart lums
```

fails, **do not immediately start changing random files.**

First inspect the service:

```bash
sudo systemctl status lums --no-pager
```

Then:

```bash
sudo journalctl -u lums -n 100 --no-pager
```

For live debugging:

```bash
sudo journalctl -u lums -f
```

---

# 🔍 Common LUMS Startup Problems

## Missing Secret

Error similar to:

```text
LUMS_SECRET_KEY is not configured
```

Check:

```bash
sudo ls -l /etc/lums/lums.env
```

Check that the variable exists without printing the secret:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' /etc/lums/lums.env \
    && echo "Secret configured" \
    || echo "Secret missing"
```

Restart:

```bash
sudo systemctl restart lums
```

---

# 🐍 Python Syntax Error

Run:

```bash
python3 -m py_compile /opt/lums-api/app.py
```

If it returns an error, fix the Python source before restarting.

---

# 📂 Permission Problem

Check:

```bash
ls -ld /opt/lums-api
ls -ld /var/lib/lums
ls -l /var/lib/lums/lums.db
```

Expected application ownership:

```text
lums:lums
```

The service must be able to access:

```text
/opt/lums-api
/var/lib/lums
```

---

# 🗄 Database Problem

Check:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

Expected:

```text
ok
```

If the database is damaged, stop LUMS before restoring a backup:

```bash
sudo systemctl stop lums
```

Restore the selected backup:

```bash
sudo cp \
    /var/lib/lums/backups/BACKUP_FILE \
    /var/lib/lums/lums.db
```

Fix ownership:

```bash
sudo chown lums:lums /var/lib/lums/lums.db
sudo chmod 600 /var/lib/lums/lums.db
```

Check integrity again:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

Then:

```bash
sudo systemctl start lums
```

---

# 🌐 Nginx Does Not Work

First:

```bash
sudo nginx -t
```

If successful:

```bash
sudo systemctl status nginx
```

Then:

```bash
sudo journalctl -u nginx -n 100 --no-pager
```

Test Flask independently:

```bash
curl http://127.0.0.1:5000/api/health
```

If Flask works but HTTPS does not:

```text
Flask       → working
Nginx       → investigate
TLS         → investigate
Firewall    → investigate
```

If Flask itself does not work:

```text
Nginx is not the first problem.
Fix LUMS/systemd first.
```

---

# 🔙 Rollback

If a new deployment breaks the application:

Stop LUMS:

```bash
sudo systemctl stop lums
```

Identify the previous deployment:

```bash
ls -ld /opt/lums-api.backup-*
```

Move the broken deployment aside:

```bash
sudo mv \
    /opt/lums-api \
    /opt/lums-api.failed-$(date +%Y%m%d-%H%M%S)
```

Restore the previous deployment:

```bash
sudo mv \
    /opt/lums-api.backup-TIMESTAMP \
    /opt/lums-api
```

Correct ownership:

```bash
sudo chown -R lums:lums /opt/lums-api
```

Test:

```bash
python3 -m py_compile /opt/lums-api/app.py
```

Start:

```bash
sudo systemctl start lums
```

Verify:

```bash
curl http://127.0.0.1:5000/api/health
```

---

# 🔎 Troubleshooting Checklist

When something breaks, work from the inside out.

```text
1. Is the server running?
       │
       ▼
2. Is the LUMS service running?
       │
       ▼
3. Does Flask respond locally?
       │
       ▼
4. Does SQLite work?
       │
       ▼
5. Does Nginx configuration pass?
       │
       ▼
6. Does HTTPS work?
       │
       ▼
7. Can the client reach the server?
       │
       ▼
8. Does the agent run?
       │
       ▼
9. Does the client report arrive?
       │
       ▼
10. Does the update workflow work?
```

Useful commands:

```bash
sudo systemctl status lums
sudo journalctl -u lums -n 100 --no-pager

sudo systemctl status nginx
sudo nginx -t
sudo journalctl -u nginx -n 100 --no-pager

sudo ss -ltnp

curl http://127.0.0.1:5000/api/health
curl -k https://SERVER_IP/api/health

sudo -u lums sqlite3 /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

---

# 📊 Useful Database Checks

Number of clients:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'SELECT COUNT(*) FROM clients;'
```

Number of users:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'SELECT COUNT(*) FROM users;'
```

Number of update jobs:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'SELECT COUNT(*) FROM update_jobs;'
```

Recent jobs:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'SELECT id, client_id, status, created_at FROM update_jobs ORDER BY id DESC LIMIT 10;'
```

Recent audit events:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'SELECT timestamp, actor_type, action, result FROM audit_log ORDER BY id DESC LIMIT 20;'
```

Do not expose database contents publicly.

---

# 📦 Aptly Integration

LUMS can coexist with an Aptly-based internal package mirror.

Example:

```text
                 LUMS
                  │
                  │ update management
                  ▼
             Linux Clients
                  │
                  │ APT
                  ▼
                Aptly
                  │
                  ▼
          Ubuntu repositories
```

Aptly may be served by Nginx under:

```text
/aptly/
```

Example Nginx location:

```nginx
location /aptly/ {
    alias /srv/lums/aptly/public/;
    autoindex on;
}
```

Aptly is independent of the Flask application.

Therefore:

```text
LUMS service stopped
       ≠
Aptly package repository stopped
```

if both are served independently by Nginx.

---

# 🔄 Recommended Update Procedure

Before changing LUMS:

```text
1. Check system health
2. Check Git status
3. Back up SQLite
4. Back up deployed application
5. Pull changes
6. Review changes
7. Deploy
8. Run syntax check
9. Restart LUMS
10. Check systemd
11. Check Flask
12. Check Nginx
13. Login through HTTPS
14. Test client reporting
15. Test update job
```

Never skip the backup just because the change looks small.

---

# 🧱 Repository Privacy

The repository should not contain:

```text
passwords
API tokens
client tokens
private keys
Flask secret keys
personal credentials
internal secrets
```

The following types of files must remain outside Git:

```text
/etc/lums/lums.env
/etc/lums/lums-agent.env
/etc/lums/tls/*.key
```

The `.gitignore` should contain appropriate secret/configuration patterns such as:

```gitignore
lums.env
lums-*.env
lums-agent.env
lums-agent.conf
```

Private infrastructure addresses should also not be unnecessarily documented in a public repository.

Use placeholders:

```text
SERVER_IP
CLIENT_IP
```

instead of real internal addresses.

---

# 🧪 Development

For development, the Flask application can be started directly:

```bash
cd /opt/lums-api
```

Set the required secret in the shell:

```bash
export LUMS_SECRET_KEY="$(openssl rand -hex 64)"
```

Start:

```bash
python3 app.py
```

The current application binds to:

```text
127.0.0.1:5000
```

This is intentional for the reverse-proxy architecture.

Do not expose Flask directly to an untrusted network without understanding the security implications.

---

# 🧪 Security Testing

Security testing should verify at least:

## Authentication

```text
✓ unauthenticated dashboard rejected
✓ wrong password rejected
✓ unknown user rejected
✓ disabled user rejected
✓ successful login works
✓ logout works
```

## Session Security

```text
✓ session created after login
✓ session contains authenticated user
✓ CSRF token exists
✓ logout clears session
✓ Secure cookie enabled
✓ HttpOnly cookie enabled
✓ SameSite=Strict
```

## CSRF

```text
✓ missing token rejected
✓ invalid token rejected
✓ valid token accepted
```

## Password Security

```text
✓ Argon2 hash generated
✓ correct password accepted
✓ wrong password rejected
✓ outdated hash can be upgraded
```

## Client Token Foundation

```text
✓ random tokens generated
✓ tokens differ
✓ hashes differ
✓ correct token verifies
✓ wrong token fails
✓ revoked token fails
✓ disabled client fails
```

---

# 🧪 Recommended Pre-Release Checklist

Before merging a change:

```text
[ ] Python syntax check
[ ] Database integrity check
[ ] Unit/security tests
[ ] Login test
[ ] Logout test
[ ] CSRF test
[ ] Client report test
[ ] Client list test
[ ] Update detection test
[ ] Update job creation test
[ ] Agent job claim test
[ ] Update result test
[ ] Update history test
[ ] Reboot detection test
[ ] HTTPS test
[ ] Nginx syntax test
[ ] systemd restart test
[ ] Backup created
[ ] Rollback plan confirmed
```

---

# 🚢 Production-Style Deployment

A controlled deployment can follow this model:

```text
Developer / Git
       │
       ▼
GitHub main
       │
       ▼
/opt/lums-public
       │
       │ controlled deployment
       ▼
/opt/lums-api
       │
       ▼
systemd
       │
       ▼
Flask
       │
       ▼
Nginx
       │
       ▼
HTTPS
```

The source checkout and deployed application should not be treated as the same thing.

This makes it possible to:

* review Git changes
* keep deployment controlled
* back up the deployed version
* roll back
* test before restarting production

---

# 🧰 Recommended Operational Commands

## Service

```bash
sudo systemctl start lums
sudo systemctl stop lums
sudo systemctl restart lums
sudo systemctl status lums
```

## Logs

```bash
sudo journalctl -u lums
sudo journalctl -u lums -f
sudo journalctl -u lums -n 100 --no-pager
```

## Nginx

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl restart nginx
sudo systemctl status nginx
```

## Database

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db
```

Integrity:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

## Network

```bash
ip addr
ip route
ss -ltnp
```

---

# 🧠 Design Philosophy

LUMS is deliberately not intended to become a huge enterprise platform.

The goal is a practical system that is:

```text
small
understandable
auditable
testable
extensible
```

The architecture favors technologies that are easy to inspect:

```text
Python
Flask
SQLite
systemd
Nginx
Linux
```

No unnecessary orchestration layer is required.

---

# 🧪 Lab Philosophy

LUMS is also a learning project.

The recommended workflow is:

```text
Build
  ↓
Test
  ↓
Break
  ↓
Investigate
  ↓
Understand
  ↓
Harden
  ↓
Document
```

A failed service is not necessarily a disaster.

It is often the most useful part of the lab.

---

# 🐛 Why the Name?

LUMS is the technical project name.

The human signature behind the project is:

```text
segfault // override
```

It is a nickname/signature and **not a software component, command, function, API or configuration option**.

It represents the project's general philosophy:

> Build it. Break it. Understand it. Harden it.

Or, in classic homelab fashion:

> “Oh, that could still be turned into a lab.” 😎

---

# 📜 License

See:

```text
LICENSE
```

for the applicable project license.

---

# 🔗 Project

GitHub:

`https://github.com/NovaForgeCtrl/LUMS`

Repository:

```text
NovaForgeCtrl/LUMS
```

---

# 🏁 Final Quick Start

For an experienced administrator, the shortest installation path is:

```bash
sudo apt update
sudo apt install -y \
    git \
    python3 \
    python3-pip \
    python3-venv \
    python3-argon2 \
    sqlite3 \
    nginx \
    openssl

sudo useradd \
    --system \
    --create-home \
    --home-dir /home/lums \
    --shell /usr/sbin/nologin \
    lums

sudo mkdir -p \
    /opt/lums-api \
    /var/lib/lums \
    /etc/lums \
    /etc/lums/tls

sudo chown -R lums:lums \
    /opt/lums-api \
    /var/lib/lums
```

Then:

```text
1. Clone repository
2. Deploy server/
3. Configure LUMS_SECRET_KEY
4. Initialize database
5. Run security migration
6. Create administrator
7. Configure systemd
8. Configure TLS
9. Configure Nginx
10. Start LUMS
11. Verify /api/health
12. Login
13. Install agent
14. Register/report client
15. Verify updates
16. Create update job
17. Execute job
18. Verify result
19. Verify history
20. Create backup
```

---

# ✅ Definition of Done

A LUMS installation can be considered operational when all of the following are true:

```text
[✓] LUMS service is running
[✓] SQLite database is accessible
[✓] Flask responds locally
[✓] Nginx configuration is valid
[✓] HTTPS works
[✓] Administrator login works
[✓] CSRF protection works
[✓] Client can report
[✓] Client appears in dashboard
[✓] Package inventory is stored
[✓] Available updates are stored
[✓] Update job can be created
[✓] Agent can process the job
[✓] Result is recorded
[✓] Reboot requirement is recorded
[✓] Update history is available
[✓] Audit logging works
[✓] Database backup exists
[✓] Recovery procedure has been tested
```

---

## LUMS

**Linux Update Management without the noise.**

```text
        ┌─────────────────────────────────────┐
        │             L U M S                 │
        │                                     │
        │   Build. Test. Break. Understand.  │
        │             Harden.                 │
        │                                     │
        │       segfault // override          │
        └─────────────────────────────────────┘
```

*Designed for homelabs, learning, testing and small internal infrastructures.*
