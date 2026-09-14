# 🛰️ LUMS — Linux Update Management Server

> **Linux Update Management without the noise.**

**LUMS** is a lightweight Linux update management system designed for homelabs, laboratories, test environments and small internal infrastructures.

It provides a central server for managing Linux clients, collecting system and package information, detecting available updates, creating remote update jobs and recording their results.

```text
                         ┌───────────────────────┐
                         │       LUMS Server     │
                         │                       │
                         │  Web UI               │
                         │  REST API             │
                         │  Authentication       │
                         │  Authorization        │
                         │  Audit Logging        │
                         │  SQLite               │
                         └───────────┬───────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
              ┌──────────┐    ┌──────────┐    ┌──────────┐
              │ Linux VM │    │ Linux PC │    │  Linux   │
              │  Agent   │    │  Agent   │    │ Server   │
              └──────────┘    └──────────┘    └──────────┘
                    │                │                │
                    └────────────────┼────────────────┘
                                     │
                              Update Jobs
```

---

# 👾 Built with Controlled Chaos

LUMS is a practical infrastructure project.

It was built around a simple idea:

> **Make Linux update management understandable, reproducible and useful.**

The project intentionally combines:

* Linux administration
* Python
* Flask
* SQLite
* REST APIs
* systemd
* Nginx
* TLS
* authentication
* authorization
* automation
* package management
* security
* documentation

### Built by

```text
segfault // override
```

*System Builder · Infrastructure / Security · Controlled Chaos*

> **Build it. Test it. Break it. Understand it. Harden it.**

---

# 📚 Table of Contents

* [Features](#-features)
* [Architecture](#-architecture)
* [Security Architecture](#-security-architecture)
* [Project Structure](#-project-structure)
* [Requirements](#-requirements)
* [Installation](#-installation)
* [Server Installation](#-server-installation)
* [Database](#-database)
* [Administrator Authentication](#-administrator-authentication)
* [Security Configuration](#-security-configuration)
* [systemd Service](#-systemd-service)
* [Nginx](#-nginx)
* [TLS](#-tls)
* [LUMS Agent](#-lums-agent)
* [Client Authentication](#-client-authentication)
* [Client Registration](#-client-registration)
* [Client Token Security](#-client-token-security)
* [Agent Timer](#-agent-timer)
* [Web Interface](#-web-interface)
* [Update Management](#-update-management)
* [Update Jobs](#-update-jobs)
* [Reboot Detection](#-reboot-detection)
* [REST API](#-rest-api)
* [Backups](#-backups)
* [Deployment](#-deployment)
* [Testing](#-testing)
* [End-to-End Test](#-end-to-end-test)
* [Troubleshooting](#-troubleshooting)
* [Recovery](#-recovery)
* [Aptly Integration](#-aptly-integration)
* [Repository Privacy](#-repository-privacy)
* [Security Model](#-security-model)
* [Development](#-development)
* [Project Philosophy](#-project-philosophy)
* [License](#-license)

---

# 🚀 Features

## Server

LUMS provides:

* Flask web application
* REST API
* SQLite database
* administrator login
* Argon2id password hashing
* secure server-side sessions
* session expiration
* session regeneration
* CSRF protection
* client authentication
* individual client tokens
* token hashing
* token revocation
* client enable/disable state
* client authorization
* audit logging
* security headers
* Content Security Policy
* client inventory
* package inventory
* available update detection
* remote update jobs
* update history
* reboot detection

## Agent

The LUMS Agent can:

* identify the Linux system
* report hostname
* report operating system information
* report kernel information
* report architecture
* report installed packages
* detect available updates
* retrieve pending update jobs
* install selected updates
* report update results
* detect reboot requirements
* authenticate with an individual client token
* run manually
* run automatically through systemd

---

# 🧭 Architecture

A typical deployment looks like this:

```text
                         ┌─────────────────────────┐
                         │       LUMS SERVER       │
                         │                         │
                         │ Flask                   │
                         │ REST API                │
                         │ SQLite                  │
                         │ Authentication          │
                         │ Authorization           │
                         │ Audit Logging            │
                         └────────────┬────────────┘
                                      │
                                   HTTPS
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
              ┌──────────┐      ┌──────────┐      ┌──────────┐
              │ Client 1 │      │ Client 2 │      │ Client 3 │
              │  Agent   │      │  Agent   │      │  Agent   │
              └──────────┘      └──────────┘      └──────────┘
                    │                 │                 │
                    └─────────────────┼─────────────────┘
                                      │
                              Package Management
                                      │
                                      ▼
                               Debian / Ubuntu
```

For a TLS-enabled deployment:

```text
Internet / LAN
      │
      │ HTTPS
      ▼
┌──────────────┐
│    Nginx     │
│              │
│ TLS          │
│ Reverse Proxy│
└──────┬───────┘
       │
       │ HTTP localhost
       ▼
┌──────────────┐
│    Flask     │
│   127.0.0.1  │
│    :5000     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    SQLite    │
│ /var/lib/lums│
└──────────────┘
```

---

# 🧱 Security Architecture

LUMS uses separate authentication models for administrators and managed clients.

```text
                    ┌─────────────────┐
                    │     LUMS        │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
      Administrator                     Linux Agent
              │                             │
              ▼                             ▼
       Web Session                    Bearer Token
              │                             │
              ▼                             ▼
       CSRF Protection                Client Identity
              │                             │
              └──────────────┬──────────────┘
                             ▼
                       Authorization
                             │
                             ▼
                        Audit Log
```

Administrator authentication uses:

* username
* password
* Argon2id
* server-side session
* CSRF token

Agent authentication uses:

* client identity
* individual bearer token
* SHA-256 token hash
* token revocation
* enabled/disabled state

These authentication systems are deliberately separated.

---

# 📁 Project Structure

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
│   ├── static/
│   │   ├── app.js
│   │   ├── client.js
│   │   └── style.css
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

# 🛠️ Requirements

## Server

Recommended:

* Ubuntu Server 26.04 LTS
* Python 3
* Flask
* SQLite
* Git
* curl
* Argon2 Python bindings
* Nginx for HTTPS deployments
* systemd

Install base packages:

```bash
sudo apt update

sudo apt install -y \
    python3 \
    python3-flask \
    python3-argon2 \
    sqlite3 \
    git \
    curl \
    nginx
```

## Client

The agent is designed primarily for Debian/Ubuntu Linux systems.

Required:

* Python 3
* systemd
* apt
* dpkg
* apt-cache
* network access to the LUMS server

---

# 📦 Installation

## 1. Clone the repository

```bash
git clone https://github.com/NovaForgeCtrl/LUMS.git
cd LUMS
```

Verify:

```bash
git status
```

Expected:

```text
On branch main
nothing to commit, working tree clean
```

---

# 🖥️ Server Installation

## 1. Create the LUMS service account

LUMS should not run as root.

Create a dedicated system user:

```bash
sudo useradd \
    --system \
    --home /home/lums \
    --create-home \
    --shell /usr/sbin/nologin \
    lums
```

Verify:

```bash
getent passwd lums
```

Expected:

```text
lums:x:...:/home/lums:/usr/sbin/nologin
```

The service account should not provide interactive shell access.

---

## 2. Create directories

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

Set directory permissions:

```bash
sudo chmod 750 /opt/lums-api
sudo chmod 750 /var/lib/lums
sudo chmod 750 /etc/lums
```

---

## 3. Install application files

From the repository:

```bash
sudo cp -r server/* /opt/lums-api/
```

Set ownership:

```bash
sudo chown -R lums:lums /opt/lums-api
```

Verify:

```bash
sudo find /opt/lums-api -maxdepth 2 -type f
```

---

# 🗄️ Database

Initialize the database:

```bash
sudo python3 /opt/lums-api/init_db.py
```

The default database is:

```text
/var/lib/lums/lums.db
```

Verify:

```bash
sudo ls -lh /var/lib/lums/
```

Expected:

```text
lums.db
```

Set ownership:

```bash
sudo chown lums:lums /var/lib/lums/lums.db
```

Restrict permissions:

```bash
sudo chmod 600 /var/lib/lums/lums.db
```

---

# 🧬 Security Database Migration

The security foundation is provided by:

```text
server/security_migration.py
```

It creates security-related database structures including:

```text
users
audit_log
schema_migrations
```

and extends the client structure with:

```text
client_token_hash
token_created_at
token_revoked_at
enabled
```

The migration is designed to be idempotent.

Always create a backup before running migrations against an existing production database.

---

# 🔐 Server Secret

Create the configuration file:

```bash
sudo touch /etc/lums/lums.env
```

Generate a random secret:

```bash
openssl rand -hex 32
```

Create the configuration:

```bash
sudo tee /etc/lums/lums.env > /dev/null <<'EOF'
LUMS_SECRET_KEY=REPLACE_WITH_RANDOM_SECRET
EOF
```

Replace:

```text
REPLACE_WITH_RANDOM_SECRET
```

with the generated value.

Do not commit this file.

Set permissions:

```bash
sudo chown root:lums /etc/lums/lums.env
sudo chmod 640 /etc/lums/lums.env
```

Verify permissions:

```bash
sudo ls -l /etc/lums/lums.env
```

Never display the contents of this file in logs, screenshots or Git commits.

---

# 👤 Administrator Account

Create the first administrator:

```bash
sudo python3 /opt/lums-api/create_admin.py
```

The administrator password is hashed using Argon2id.

Passwords are never stored in plaintext.

After creation, verify the user exists:

```bash
sudo sqlite3 /var/lib/lums/lums.db \
    "SELECT id, username, enabled FROM users;"
```

Do not retrieve or display the password hash unnecessarily.

---

# 🧱 File Permissions

A recommended layout is:

```text
/opt/lums-api
    lums:lums
    750

/var/lib/lums
    lums:lums
    750

/var/lib/lums/lums.db
    lums:lums
    600

/etc/lums/lums.env
    root:lums
    640

/etc/lums/tls/lums.key
    root:root
    600

/etc/lums/tls/lums.crt
    root:root
    644
```

The goal is:

> **LUMS should have access to the data it needs, but nothing more.**

---

# ⚙️ systemd Service

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

Enable the service:

```bash
sudo systemctl enable lums.service
```

Start:

```bash
sudo systemctl start lums.service
```

Check:

```bash
sudo systemctl status lums.service
```

---

# 🧪 Service Verification

Check whether Flask is listening:

```bash
sudo ss -lntp | grep 5000
```

Expected architecture:

```text
127.0.0.1:5000
```

Check the service log:

```bash
sudo journalctl -u lums.service -n 50 --no-pager
```

Follow logs live:

```bash
sudo journalctl -u lums.service -f
```

Test locally:

```bash
curl http://127.0.0.1:5000/
```

A redirect to `/login` is expected when authentication is enabled.

---

# 🌐 Nginx

For an HTTPS deployment, use Nginx as reverse proxy.

Create:

```bash
sudo tee /etc/nginx/sites-available/lums > /dev/null <<'EOF'
server {
    listen 80;
    server_name SERVER-IP;

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name SERVER-IP;

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
SERVER-IP
```

with the LUMS server address.

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

Remove the default site if appropriate:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

Test:

```bash
sudo nginx -t
```

Expected:

```text
syntax is ok
test is successful
```

Restart:

```bash
sudo systemctl restart nginx
```

---

# 🔒 TLS

LUMS should be accessed through HTTPS in normal deployments because:

* administrator credentials are transmitted
* session cookies are transmitted
* client bearer tokens are transmitted
* system information is transmitted
* update information is transmitted

For an internal laboratory, a self-signed certificate can be used.

Example:

```bash
sudo openssl req \
    -x509 \
    -nodes \
    -newkey rsa:4096 \
    -keyout /etc/lums/tls/lums.key \
    -out /etc/lums/tls/lums.crt \
    -days 825 \
    -subj "/CN=SERVER-IP"
```

Set permissions:

```bash
sudo chmod 600 /etc/lums/tls/lums.key
sudo chmod 644 /etc/lums/tls/lums.crt
```

Verify:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -dates
```

For production environments, use a properly managed certificate authority or trusted certificate.

---

# 🔍 HTTPS Test

Test:

```bash
curl -k -I https://SERVER-IP/
```

Expected:

```text
HTTP/1.1 302 FOUND
```

or another appropriate authenticated redirect.

HTTP should redirect:

```bash
curl -I http://SERVER-IP/
```

Expected:

```text
301
```

---

# 🛡️ Security Headers

LUMS applies security headers such as:

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Permissions-Policy
Content-Security-Policy
```

Check:

```bash
curl -k -I https://SERVER-IP/login
```

Verify the headers are present.

---

# 🔑 Web Login

Open:

```text
https://SERVER-IP/login
```

The login page provides:

* LUMS branding
* username field
* password field
* authentication button
* secure session handling

After successful login, the administrator can access the protected management interface.

---

# 🤖 LUMS Agent

The LUMS Agent runs on managed Linux clients.

Create the directory:

```bash
sudo mkdir -p /opt/lums-agent
```

Copy the agent:

```bash
sudo cp agent/agent.py /opt/lums-agent/
```

Set ownership:

```bash
sudo chown -R root:root /opt/lums-agent
```

Restrict permissions:

```bash
sudo chmod 750 /opt/lums-agent
sudo chmod 750 /opt/lums-agent/agent.py
```

---

# 🔑 Client Authentication

Every client uses its own authentication token.

The token is sent using:

```text
Authorization: Bearer <client-token>
```

The server stores only a hash of the client token.

The original token must therefore be treated like a password:

> **If the token is exposed, revoke it and create a new one.**

---

# 🖥️ Client Registration

A client must first exist in the LUMS database before its agent can authenticate.

The exact registration mechanism depends on the currently deployed API version.

The important security model is:

```text
1. Create client
2. Generate individual token
3. Store token securely
4. Configure agent
5. Start agent
6. Agent authenticates
7. Client information is reported
```

The token should be transferred only through a trusted administrative channel.

Never place client tokens:

* inside Git
* inside public documentation
* inside screenshots
* inside shell history when avoidable
* inside logs
* inside source code

---

# 🔐 Secure Token Storage on Client

A recommended approach is to store the token in a root-owned configuration file.

Example:

```bash
sudo tee /etc/lums-agent.env > /dev/null <<'EOF'
LUMS_BASE=https://SERVER-IP
LUMS_CLIENT_TOKEN=REPLACE_WITH_CLIENT_TOKEN
EOF
```

Set ownership:

```bash
sudo chown root:root /etc/lums-agent.env
```

Restrict permissions:

```bash
sudo chmod 600 /etc/lums-agent.env
```

Verify:

```bash
sudo ls -l /etc/lums-agent.env
```

Expected:

```text
-rw------- root root
```

Never run:

```bash
cat /etc/lums-agent.env
```

when screen sharing, recording a terminal or creating documentation.

---

# ⚙️ Agent systemd Service

Install:

```bash
sudo cp agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
```

The service should load the external configuration rather than storing the token directly inside the service definition.

Reload:

```bash
sudo systemctl daemon-reload
```

Start:

```bash
sudo systemctl start lums-agent.service
```

Check:

```bash
sudo systemctl status lums-agent.service
```

Logs:

```bash
sudo journalctl -u lums-agent.service -n 50 --no-pager
```

---

# ⏱️ Agent Timer

The agent can be executed periodically using systemd.

Example timer:

```bash
sudo tee /etc/systemd/system/lums-agent.timer > /dev/null <<'EOF'
[Unit]
Description=LUMS Linux Update Management Agent Timer

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Unit=lums-agent.service

[Install]
WantedBy=timers.target
EOF
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lums-agent.timer
```

Check:

```bash
systemctl list-timers --all | grep lums
```

---

# 📡 Agent Verification

Run manually:

```bash
sudo systemctl start lums-agent.service
```

Check:

```bash
sudo systemctl status lums-agent.service
```

Then:

```bash
sudo journalctl -u lums-agent.service \
    -n 100 \
    --no-pager
```

If the service is one-shot, the following can be normal:

```text
Active: inactive (dead)
```

The important part is whether the execution completed successfully.

---

# 🖥️ Client Dashboard

After the agent successfully reports to the server, the client should become visible through the LUMS interface.

The client information can include:

* hostname
* operating system
* kernel
* architecture
* IP information
* installed packages
* available updates
* reboot requirement
* last contact information

---

# 📦 Update Detection

The agent checks the Linux package system for available updates.

For Debian/Ubuntu systems this is based on the local APT package information.

A typical workflow is:

```text
APT
 │
 ▼
Available Packages
 │
 ▼
LUMS Agent
 │
 ▼
LUMS Server
 │
 ▼
Dashboard
```

The administrator can then decide which updates should be installed.

---

# ⚙️ Update Jobs

An administrator can create an update job for a client.

Typical workflow:

```text
Administrator
      │
      ▼
Select Client
      │
      ▼
Select Updates
      │
      ▼
Create Job
      │
      ▼
LUMS Server
      │
      ▼
Client Agent
      │
      ▼
APT / Package Manager
      │
      ▼
Install Updates
      │
      ▼
Report Result
      │
      ▼
LUMS Server
```

Possible job states:

```text
pending
running
success
partial
failed
```

---

# 📊 Update History

LUMS records update history.

This makes it possible to determine:

* which client was updated
* which packages were involved
* when the update occurred
* whether it succeeded
* whether an error occurred
* whether a reboot was required

---

# 🔄 Reboot Detection

After updates, the agent checks whether the system requires a reboot.

The result is reported to the LUMS server.

This allows the administrator to distinguish between:

```text
Updates installed
```

and:

```text
Updates installed
+
reboot required
```

---

# 📡 REST API

## Health

```http
GET /api/health
```

Used for basic availability testing.

---

## Client Reporting

```http
POST /api/report
```

Used by agents to report system information.

---

## Clients

```http
GET /api/clients
GET /api/clients/<client_id>
```

---

## Available Updates

```http
GET /api/clients/<client_id>/updates
```

---

## Installed Packages

```http
GET /api/clients/<client_id>/packages
```

---

## Update Jobs

```http
POST /api/clients/<client_id>/update-jobs
GET /api/clients/<client_id>/update-jobs
GET /api/clients/<client_id>/update-jobs/pending
GET /api/update-jobs/<job_id>
POST /api/update-jobs/<job_id>/result
```

---

## Update History

```http
GET /api/clients/<client_id>/update-history
GET /api/update-history
```

Administrative endpoints require administrator authentication.

Agent operations require client authentication.

---

# 🧪 Testing

LUMS contains several security-sensitive components that should be tested independently.

Important tests include:

### Password Security

* correct password succeeds
* incorrect password fails
* invalid hashes fail safely
* Argon2id is used

### Client Tokens

* tokens are randomly generated
* tokens are different
* hashes are stored instead of plaintext
* invalid tokens fail
* revoked tokens fail
* disabled clients fail authentication

### Sessions

* unauthenticated users are redirected
* login creates a session
* session contains the expected identity
* session regeneration occurs
* logout clears the session
* expired sessions cannot access protected resources

### CSRF

Test:

```text
No token
Invalid token
Valid token
```

State-changing operations must reject missing or invalid CSRF tokens.

### HTTP Security

Verify:

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Permissions-Policy
Content-Security-Policy
```

---

# 🔬 End-to-End Test

A complete deployment should be tested from beginning to end.

## Step 1 — Server

Check:

```bash
sudo systemctl status lums
```

and:

```bash
sudo systemctl status nginx
```

Both should be running.

---

## Step 2 — HTTPS

```bash
curl -k -I https://SERVER-IP/login
```

Expected:

```text
HTTP 200
```

---

## Step 3 — Login

Open:

```text
https://SERVER-IP/login
```

Log in with the administrator account.

---

## Step 4 — Client

On the client:

```bash
sudo systemctl start lums-agent.service
```

Check:

```bash
sudo journalctl -u lums-agent.service -n 50 --no-pager
```

---

## Step 5 — Dashboard

Return to the LUMS dashboard.

The client should appear.

---

## Step 6 — Updates

Verify that available updates are displayed.

---

## Step 7 — Create Job

Select one or more updates.

Create an update job.

---

## Step 8 — Agent

Run the agent:

```bash
sudo systemctl start lums-agent.service
```

---

## Step 9 — Result

Verify:

* job state
* package state
* update result
* update history
* reboot requirement

---

## Step 10 — Final State

A successful test should look approximately like:

```text
Client
  │
  ├── authenticated
  ├── inventory reported
  ├── updates detected
  ├── update job created
  ├── updates installed
  ├── result reported
  ├── history recorded
  └── reboot state reported
```

🎉 **LUMS End-to-End Test Complete**

---

# 💾 Backups

Always create a database backup before:

* migrations
* major updates
* application changes
* database changes
* deployment changes

Create a backup:

```bash
sudo cp \
    /var/lib/lums/lums.db \
    /var/lib/lums/lums.db.backup-$(date +%Y%m%d-%H%M%S)
```

Verify:

```bash
sudo ls -lh /var/lib/lums/
```

Restrict permissions:

```bash
sudo chmod 600 /var/lib/lums/*.db*
```

---

# ♻️ Database Backup Verification

A backup is only useful if it can actually be read.

Test:

```bash
sudo sqlite3 \
    /var/lib/lums/lums.db.backup-YYYYMMDD-HHMMSS \
    "PRAGMA integrity_check;"
```

Expected:

```text
ok
```

Do not consider a backup complete until its integrity has been verified.

---

# 🚢 Deployment

LUMS should use a controlled deployment process.

Recommended:

```text
GitHub
   │
   ▼
Pull / Fetch
   │
   ▼
Review changes
   │
   ▼
Backup database
   │
   ▼
Update application
   │
   ▼
Run migrations
   │
   ▼
Check permissions
   │
   ▼
Restart service
   │
   ▼
Check logs
   │
   ▼
Check HTTPS
   │
   ▼
Login test
   │
   ▼
Agent test
   │
   ▼
End-to-End verification
```

Do not blindly deploy with:

```bash
git pull && systemctl restart lums
```

without checking what changed.

---

# 🔄 Updating a Git Checkout

A controlled update can begin with:

```bash
cd /opt/lums-public

git fetch origin

git checkout main

git pull --ff-only origin main

git status
```

Expected:

```text
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

Review changes before deploying them to the active application directory.

---

# 🧯 Troubleshooting

## LUMS does not start

Check:

```bash
sudo systemctl status lums
```

Then:

```bash
sudo journalctl -u lums -n 100 --no-pager
```

Check whether port 5000 is occupied:

```bash
sudo ss -lntp | grep 5000
```

Check the secret:

```bash
sudo ls -l /etc/lums/lums.env
```

Do not print the secret itself.

---

# ❌ Nginx does not start

Run:

```bash
sudo nginx -t
```

If it reports an error, inspect the configuration:

```bash
sudo sed -n '1,240p' /etc/nginx/sites-available/lums
```

Then:

```bash
sudo journalctl -u nginx -n 100 --no-pager
```

---

# ❌ HTTPS does not work

Check:

```bash
sudo systemctl status nginx
```

Check certificates:

```bash
sudo ls -l /etc/lums/tls/
```

Check:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -dates
```

Check listening ports:

```bash
sudo ss -lntp | grep -E ':80|:443'
```

---

# ❌ Agent cannot connect

On the client:

```bash
sudo journalctl -u lums-agent.service \
    -n 100 \
    --no-pager
```

Check network connectivity:

```bash
ping SERVER-IP
```

Check HTTPS:

```bash
curl -k -I https://SERVER-IP/login
```

Check DNS if using a hostname:

```bash
getent hosts LUMS-HOSTNAME
```

---

# ❌ Client authentication fails

Check:

* token is correct
* token has not been revoked
* client is enabled
* client exists on the server
* Authorization header is present
* HTTPS endpoint is correct
* token file permissions are correct

Never solve an authentication problem by putting the token into source code.

---

# ❌ Client appears but has no updates

Check:

```bash
sudo apt update
```

Then:

```bash
apt list --upgradable
```

If APT itself cannot see updates, LUMS cannot report updates that the package manager does not know about.

Check:

```bash
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

---

# ❌ Update job fails

Check the job result in the dashboard.

Then inspect the client:

```bash
sudo journalctl -u lums-agent.service \
    -n 200 \
    --no-pager
```

Also check APT:

```bash
sudo apt update
```

and package manager state:

```bash
sudo dpkg --audit
```

If required:

```bash
sudo dpkg --configure -a
```

Only repair package manager state when you understand the reported problem.

---

# 💥 Server Does Not Start After a Change

Do **not** immediately start changing random files.

First:

```bash
sudo systemctl status lums
```

Then:

```bash
sudo journalctl -u lums -n 100 --no-pager
```

Check the application manually:

```bash
sudo -u lums \
    /usr/bin/python3 \
    /opt/lums-api/app.py
```

This can expose Python errors directly.

If a recent deployment caused the problem:

1. stop the service
2. preserve the current state
3. inspect the logs
4. compare the Git diff
5. restore the previous application version if necessary
6. restore the database only if required
7. verify permissions
8. restart
9. test again

Never restore a database unnecessarily just because the application failed to start.

---

# 🧯 Recovery

A basic recovery process:

```text
Failure
  │
  ▼
Stop / isolate service
  │
  ▼
Read logs
  │
  ▼
Identify change
  │
  ▼
Preserve current state
  │
  ▼
Restore previous application version
  │
  ▼
Check database integrity
  │
  ▼
Restart
  │
  ▼
Health test
  │
  ▼
Login test
  │
  ▼
Agent test
```

If the database itself is damaged:

```bash
sudo sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

A valid database should return:

```text
ok
```

Before restoring a backup, preserve the existing database:

```bash
sudo mv \
    /var/lib/lums/lums.db \
    /var/lib/lums/lums.db.failed
```

Then restore the known-good backup:

```bash
sudo cp \
    /var/lib/lums/lums.db.backup-YYYYMMDD-HHMMSS \
    /var/lib/lums/lums.db
```

Fix permissions:

```bash
sudo chown lums:lums /var/lib/lums/lums.db
sudo chmod 600 /var/lib/lums/lums.db
```

Restart:

```bash
sudo systemctl restart lums
```

Check:

```bash
sudo systemctl status lums
```

---

# 📦 Aptly Integration

LUMS does not require Aptly.

However, it can be combined with an internal APT repository.

Example:

```text
                 Ubuntu Repository
                         │
                         ▼
                      Aptly
                         │
                         ▼
               Internal APT Repository
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
          Client 1                Client 2
             │                       │
             └───────────┬───────────┘
                         ▼
                        LUMS
```

This allows an environment to separate:

```text
Package distribution
```

from:

```text
Update management
```

LUMS manages the update process.

Aptly can manage the package repository.

---

# 📝 Database Schema Overview

The LUMS database contains several logical areas.

## Clients

Stores information about managed systems.

Includes client identity, status and authentication metadata.

## Packages

Stores package inventory reported by clients.

## Available Updates

Stores updates detected by clients.

## Update Jobs

Stores requested update operations.

## Update Job Packages

Stores individual packages belonging to a job.

## Update History

Stores completed update operations.

## Users

Stores administrator identities and Argon2id password hashes.

## Audit Log

Stores security and administrative events.

## Schema Migrations

Tracks database migration versions.

---

# 🔐 Password Security

Administrator passwords are protected with Argon2id.

LUMS does not intentionally store plaintext passwords.

Password verification is performed through the password hashing implementation.

The password hashing implementation also supports detection of hashes that should be rehashed according to current parameters.

---

# 🔑 Token Security

Client tokens are generated using cryptographically secure randomness.

The server stores:

```text
SHA-256(client-token)
```

rather than the original token.

Validation calculates the hash of the supplied token and compares it securely.

A token can be revoked.

A disabled client cannot authenticate.

---

# 🍪 Session Security

LUMS sessions use:

```text
HttpOnly
Secure
SameSite=Strict
```

cookies.

The session lifetime is limited.

Login regenerates the session state.

Logout clears the session.

The browser management interface also implements inactivity handling.

---

# 🛡️ CSRF Security

Browser-based state-changing requests require a valid CSRF token.

Safe methods such as:

```text
GET
HEAD
OPTIONS
```

do not require a CSRF token.

Agent API requests use bearer authentication rather than browser session authentication.

---

# 📜 Audit Logging

Audit events contain:

```text
timestamp
actor type
actor ID
action
target
result
details
```

The audit log is intended to provide visibility into important administrative and security events.

It should not contain secrets.

---

# 🔒 Repository Privacy

Never commit:

```text
*.db
*.sqlite
*.sqlite3
*.backup
*.key
*.pem
*.crt
*.env
lums.env
lums-agent.env
production configuration
client tokens
passwords
logs
```

Check before committing:

```bash
git status
```

Review:

```bash
git diff
```

Review staged changes:

```bash
git diff --cached
```

A clean Git repository is part of the security model.

---

# 🧪 Pre-Deployment Checklist

Before deploying:

```text
[ ] Git working tree reviewed
[ ] Database backup created
[ ] Backup integrity checked
[ ] Application changes reviewed
[ ] Migration reviewed
[ ] Secret configuration verified
[ ] File permissions verified
[ ] systemd configuration verified
[ ] Nginx configuration tested
[ ] TLS certificate valid
[ ] LUMS service running
[ ] HTTPS working
[ ] Login working
[ ] Client authentication working
[ ] Agent working
[ ] Updates visible
[ ] Update job tested
[ ] Result recorded
[ ] Reboot state checked
```

---

# 🧪 Post-Deployment Checklist

After deployment:

```text
[ ] systemctl status lums
[ ] systemctl status nginx
[ ] journalctl -u lums
[ ] HTTPS test
[ ] Login test
[ ] Dashboard test
[ ] Client test
[ ] Agent test
[ ] Update detection test
[ ] Update job test
[ ] Audit log test
```

---

# 🧰 Development

Clone:

```bash
git clone https://github.com/NovaForgeCtrl/LUMS.git
cd LUMS
```

Install dependencies:

```bash
sudo apt update

sudo apt install -y \
    python3 \
    python3-flask \
    python3-argon2 \
    sqlite3 \
    git \
    curl
```

Initialize:

```bash
python3 server/init_db.py
```

Configure a development secret outside Git.

Run:

```bash
python3 server/app.py
```

For development, the Flask application can be tested locally.

Production deployments should use:

```text
systemd
+
Nginx
+
TLS
```

---

# 🧪 Development Workflow

Recommended:

```text
Create branch
    │
    ▼
Implement change
    │
    ▼
Run tests
    │
    ▼
Review diff
    │
    ▼
Test locally
    │
    ▼
Commit
    │
    ▼
Push
    │
    ▼
Pull Request
    │
    ▼
Review
    │
    ▼
Merge
    │
    ▼
Controlled deployment
```

Security-sensitive changes should never be deployed blindly.

---

# 🧠 Design Principles

LUMS follows several principles.

### Simple where possible

The system should remain understandable.

### Secure by design

Security should not be something added at the very end.

### Reproducible

Another administrator should be able to rebuild the environment.

### Observable

Failures should be visible through logs and audit information.

### Controlled

Updates and deployments should be deliberate.

### Internal-first

LUMS is primarily intended for controlled internal environments.

---

# 🎯 Intended Use

LUMS is especially suitable for:

* homelabs
* Linux training environments
* infrastructure labs
* small internal networks
* development environments
* testing environments
* educational projects
* security laboratories

It is **not intended to replace mature enterprise patch-management platforms** without additional development, testing and security review.

---

# ⚠️ Security Disclaimer

No software is completely secure.

LUMS provides multiple security controls, but administrators remain responsible for:

* network security
* firewall configuration
* TLS certificate management
* operating system updates
* database backups
* secret management
* access control
* monitoring
* incident response

Do not expose LUMS directly to the public Internet without a dedicated security review.

---

# 🧭 Roadmap

Potential future development areas include:

* richer dashboard statistics
* improved client discovery
* role-based administration
* package approval workflows
* maintenance windows
* scheduled update jobs
* improved reporting
* notification integrations
* repository management
* Debian package support improvements
* Ubuntu package support improvements
* additional Linux distributions
* stronger deployment automation
* automated backup verification
* API documentation
* dedicated migration tooling
* expanded automated testing

---

# 🏁 Project Philosophy

LUMS started as a practical Linux update-management experiment.

It grew into a complete infrastructure lab involving:

```text
Linux
    +
Python
    +
Flask
    +
SQLite
    +
REST
    +
systemd
    +
Nginx
    +
TLS
    +
Authentication
    +
Authorization
    +
Automation
    +
Security
```

The philosophy remains simple:

```text
Build.
Test.
Break.
Understand.
Harden.
Document.
Repeat.
```

---

# 👾 Signature

```text
┌──────────────────────────────────────────────┐
│                                              │
│             segfault // override             │
│                                              │
│       Infrastructure · Security              │
│             Controlled Chaos                 │
│                                              │
└──────────────────────────────────────────────┘
```

> **Technology without noise.**

---

# 📄 License

LUMS is licensed under the MIT License.

See:

```text
LICENSE
```

---

# 🔗 Project

**LUMS — Linux Update Management Server**

GitHub:

https://github.com/NovaForgeCtrl/LUMS

---

# 🛰️ Final Status

LUMS is designed to be:

```text
Lightweight
        ↓
Understandable
        ↓
Secure
        ↓
Reproducible
        ↓
Observable
        ↓
Useful
```

**Welcome to LUMS.**

```text
Build it.
Test it.
Break it.
Understand it.
Harden it.

segfault // override
```
