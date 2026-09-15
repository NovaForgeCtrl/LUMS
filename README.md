# LUMS – Linux Update Management Server

> **Linux Update Management without the noise.**

```text
┌─────────────────────────────────────────────────────────────┐
│                           LUMS                              │
│              Linux Update Management Server                │
│                                                             │
│  Central Linux update management for labs and small        │
│  internal infrastructures.                                 │
│                                                             │
│  Build. Test. Break. Understand. Harden.                   │
└─────────────────────────────────────────────────────────────┘
```

**`segfault // override`**
*System Builder · Infrastructure / Security · Controlled Chaos*

> `segfault // override` is the project author's signature/nickname.
> It is **not** a software component, command, API or configuration option.

---

# 🚀 What is LUMS?

**LUMS** stands for **Linux Update Management Server**.

It is a lightweight Linux update management system designed for:

* homelabs
* virtual test environments
* learning environments
* small internal infrastructures
* Linux administration labs

LUMS provides a central web interface and REST API for managing Linux clients.

The basic workflow is:

```text
                  ┌─────────────────────┐
                  │     LUMS Server     │
                  │                     │
                  │ Flask               │
                  │ SQLite              │
                  │ Authentication      │
                  │ Audit Logging       │
                  │ Web Interface       │
                  └──────────┬──────────┘
                             │
                    HTTPS / REST API
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
       Linux Client     Linux Client     Linux Server
       LUMS Agent       LUMS Agent       LUMS Agent
            │                │                │
            └────────────────┴────────────────┘
                             │
                     Reports / Updates
                             │
                             ▼
                       Update Jobs
                             │
                             ▼
                       Job Results
                             │
                             ▼
                      Update History
```

---

# ✨ Features

## Client Management

LUMS can collect information about Linux clients:

* hostname
* IP address
* operating system
* kernel version
* architecture
* LUMS Agent version
* last report
* installed packages
* available updates

---

## 📦 Package Inventory

Clients can report installed packages to LUMS.

The server stores the package inventory per client.

---

## 🔄 Update Detection

Clients report available package updates.

LUMS can display available updates and use them as the basis for update jobs.

---

## 🛠 Update Jobs

Administrators can create update jobs for clients.

A job can contain:

* client
* selected packages
* installed version
* target version
* status
* start time
* finish time
* reboot requirement
* package-level results

Possible states:

```text
pending
running
success
partial
failed
```

---

## ♻️ Reboot Detection

The agent can report whether a reboot is required after updates.

This information becomes part of the update result and history.

---

## 🔐 Authentication

The web interface provides:

* administrator login
* Argon2 password hashing
* server-side sessions
* secure session cookies
* CSRF protection
* security headers
* audit logging

LUMS also contains a client-token security foundation for agent authentication.

**Important:** see [Agent Authentication Status](#agent-authentication-status) below before assuming all agent endpoints are currently token-protected.

---

# 🧭 Supported Operating Systems

This section intentionally distinguishes between **tested**, **expected to work**, and **officially supported**.

## LUMS Server

| Operating system                 | Status                                |
| -------------------------------- | ------------------------------------- |
| **Ubuntu Server 26.04 LTS**      | ✅ Primary/tested platform             |
| Ubuntu versions other than 26.04 | 🟡 Not specifically validated         |
| Other distributions              | ❌ Not officially supported            |

### Is Ubuntu 26.04 required?

**For the current documented installation: Ubuntu Server 26.04 LTS is the reference platform.**

This does **not** mean that LUMS fundamentally requires Ubuntu 26.04.

LUMS is primarily a Python/Flask/SQLite application and does not depend on Ubuntu-specific application code.

However, the installation instructions, package names, service configuration and current lab testing are based on Ubuntu 26.04.

Therefore:

> **Ubuntu Server 26.04 = supported reference platform.**


---

## Linux Clients

The agent is intended for Linux systems.

The current lab focuses primarily on Debian/Ubuntu-based systems using APT.

Other distributions may require agent changes because package-management commands differ.

---

# 🐍 Python Requirements

The server uses Python 3.

The currently required Python-side components are:

| Dependency                                            | Purpose                                              |           Required |
| ----------------------------------------------------- | ---------------------------------------------------- | -----------------: |
| `Flask`                                               | Web application / REST API                           |                  ✅ |
| `argon2-cffi` / distribution package `python3-argon2` | Password hashing                                     |                  ✅ |
| Python standard library                               | Database, hashing, sessions, dates, security helpers |         ✅ built-in |
| SQLite                                                | Database                                             | ✅ system component |

The application does **not** require a large Python framework stack.

## Installing the dependencies on Ubuntu 26.04

```bash
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-argon2 \
    sqlite3
```

Nginx and Git are separate system requirements:

```bash
sudo apt install -y \
    nginx \
    git \
    openssl
```

---

# 📁 Repository Structure

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

# 🛠 Server Installation

The following procedure uses Ubuntu Server 26.04.

## 1. Update Ubuntu

```bash
sudo apt update
sudo apt upgrade -y
```

⚠️ **Risk:** `apt upgrade` changes installed system packages.

On production systems, review pending updates before applying them.

---

## 2. Install required packages

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

# 👤 Create the LUMS Service User

LUMS should not run as root.

```bash
sudo useradd \
    --system \
    --create-home \
    --home-dir /home/lums \
    --shell /usr/sbin/nologin \
    lums
```

Check:

```bash
getent passwd lums
```

The shell should be:

```text
/usr/sbin/nologin
```

This prevents interactive login as the service account.

---

# 📂 Create Required Directories

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

Permissions:

```bash
sudo chmod 750 /opt/lums-api
sudo chmod 750 /var/lib/lums
sudo chmod 750 /etc/lums
sudo chmod 750 /etc/lums/tls
```

---

# 📥 Clone the Repository

```bash
cd /opt
sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public
```

Change ownership of the checkout to the administrator account that maintains the source tree if appropriate.

Enter the repository:

```bash
cd /opt/lums-public
```

Switch to the main branch:

```bash
sudo git checkout main
```

Update:

```bash
sudo git pull --ff-only origin main
```

> Do not use `git pull` blindly on a deployment tree with local modifications.

---

# 📦 Deploy the Server

LUMS uses two separate locations:

```text
/opt/lums-public
        │
        │ source / Git
        ▼
/opt/lums-api
        │
        │ production deployment
        ▼
systemd
```

Deploy:

```bash
sudo rsync -a --delete \
    --exclude='.git/' \
    /opt/lums-public/server/ \
    /opt/lums-api/
```

⚠️ **Risk:** `rsync --delete` can remove files from the destination.

Only use it when `/opt/lums-api` is intentionally the deployment target.

Restore ownership:

```bash
sudo chown -R lums:lums /opt/lums-api
```

---

# 🔐 Configure the LUMS Secret

LUMS requires:

```text
LUMS_SECRET_KEY
```

Generate a random secret:

```bash
openssl rand -hex 64
```

Create the environment file:

```bash
sudo touch /etc/lums/lums.env
sudo chown root:lums /etc/lums/lums.env
sudo chmod 640 /etc/lums/lums.env
```

Create it:

```bash
sudo tee /etc/lums/lums.env > /dev/null <<'EOF'
LUMS_SECRET_KEY=REPLACE_WITH_GENERATED_SECRET
EOF
```

Replace:

```text
REPLACE_WITH_GENERATED_SECRET
```

with the generated value.

Do **not** commit this file.

Do **not** print the secret.

Verify only its permissions:

```bash
ls -l /etc/lums/lums.env
```

Expected conceptually:

```text
root lums 640
```

---

# 🗄 Initialize the Database

The default database is:

```text
/var/lib/lums/lums.db
```

Initialize:

```bash
cd /opt/lums-api
sudo -u lums python3 init_db.py
```

Check:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    '.tables'
```

---

# 🔐 Apply the Security Migration

```bash
cd /opt/lums-api
sudo -u lums python3 security_migration.py
```

The migration creates or extends the security-related database structures.

It is designed to be idempotent.

---

# 👨‍💻 Create the Administrator

```bash
cd /opt/lums-api
sudo -u lums python3 create_admin.py
```

Use a strong, unique password.

Never place the password in:

* Git
* README files
* shell scripts
* screenshots
* chat messages
* public documentation

Passwords are stored using Argon2id hashing.

---

# ⚙️ LUMS systemd Service

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

Reload:

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

---

# 🩺 Test Flask Before Nginx

Check the listening socket:

```bash
sudo ss -ltnp | grep 5000
```

LUMS should listen locally:

```text
127.0.0.1:5000
```

Test:

```bash
curl http://127.0.0.1:5000/api/health
```

If this does not work, **stop here**.

Do not troubleshoot Nginx yet.

Check:

```bash
sudo journalctl -u lums -n 100 --no-pager
```

---

# 🔥 Firewall

A server should expose only the services it actually needs.

For a typical LUMS server:

```text
SSH     TCP 22
HTTPS   TCP 443
```

HTTP port 80 may be required if it is used only to redirect HTTP to HTTPS.

## Install UFW

```bash
sudo apt install -y ufw
```

Check current state:

```bash
sudo ufw status verbose
```

⚠️ **Important:** Before enabling UFW, make sure SSH is explicitly allowed.

---

## Allow SSH

```bash
sudo ufw allow 22/tcp
```

## Allow HTTPS

```bash
sudo ufw allow 443/tcp
```

## Optional HTTP redirect

If Nginx listens on port 80:

```bash
sudo ufw allow 80/tcp
```

Enable:

```bash
sudo ufw enable
```

⚠️ **Risk:** Enabling a firewall can disconnect you if required access was not allowed first.

Verify:

```bash
sudo ufw status numbered
```

Recommended result:

```text
22/tcp   ALLOW
80/tcp   ALLOW
443/tcp  ALLOW
```

depending on your chosen configuration.

---

# 🔒 Recommended Firewall Model

Do **not** expose Flask directly.

Do not create:

```text
5000/tcp ALLOW
```

for normal operation.

The desired architecture is:

```text
Internet / LAN
      │
      ▼
   TCP 443
      │
      ▼
    Nginx
      │
      ▼
127.0.0.1:5000
      │
      ▼
    Flask
```

Port `5000` remains local.

---

# 🌐 Nginx

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
sudo ln -s \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

Remove the default site if necessary:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

⚠️ **Risk:** Removing the default Nginx site changes the web server configuration.

Test:

```bash
sudo nginx -t
```

Only if successful:

```bash
sudo systemctl reload nginx
```

---

# 🔒 TLS

For an internal lab, a self-signed certificate is sufficient for testing.

Generate:

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

For a real production environment, use an appropriately trusted certificate.

---

# 🤖 LUMS Agent Installation

This section describes the complete basic client installation.

The client should have:

* Python 3
* Git if installing from the repository
* access to the LUMS server over HTTPS
* the LUMS Agent files

## 1. Install client requirements

On Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    ca-certificates
```

---

## 2. Obtain the agent

Clone the repository:

```bash
cd /opt
sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums
```

The agent is located at:

```text
/opt/lums/agent/agent.py
```

---

## 3. Create the agent configuration

Create:

```bash
sudo mkdir -p /etc/lums
```

Create:

```bash
sudo tee /etc/lums/lums-agent.env > /dev/null <<'EOF'
LUMS_BASE=https://SERVER_IP
EOF
```

Replace:

```text
SERVER_IP
```

with the LUMS server.

Protect the configuration:

```bash
sudo chmod 600 /etc/lums/lums-agent.env
```

---

# 🔑 Agent Token

The repository contains client-token security support.

However, **the currently documented `app.py` does not yet enforce client-token authentication on every agent endpoint**.

Therefore the current implementation must not be documented as if this were already complete.

The endpoints requiring additional protection are:

```text
POST /api/report
GET  /api/clients/<client_id>/update-jobs/pending
POST /api/update-jobs/<job_id>/result
```

The intended final design is:

```text
Agent
  │
  │ Authorization: Bearer <client-token>
  ▼
LUMS
  │
  ├── hash token
  ├── find client
  ├── verify enabled/revoked state
  └── authorize client/job relationship
```

Until this integration is deployed and tested, treat the agent API as a lab-only interface.

---

# ⚙️ Complete Agent systemd Service

Create:

```bash
sudo tee /etc/systemd/system/lums-agent.service > /dev/null <<'EOF'
[Unit]
Description=LUMS Linux Update Management Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot

User=root
Group=root

EnvironmentFile=/etc/lums/lums-agent.env

ExecStart=/usr/bin/python3 /opt/lums/agent/agent.py

NoNewPrivileges=false
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF
```

### Why does the agent currently use root?

Package installation and system update operations generally require administrative privileges.

The server itself should run as the restricted `lums` account.

The agent is different because its purpose includes performing package-management operations on the client.

This is an important trust boundary.

---

# ⏱️ Agent Timer

The preferred periodic execution model is a systemd timer.

Create:

```bash
sudo tee /etc/systemd/system/lums-agent.timer > /dev/null <<'EOF'
[Unit]
Description=Run LUMS Agent periodically

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF
```

Reload:

```bash
sudo systemctl daemon-reload
```

Enable:

```bash
sudo systemctl enable --now lums-agent.timer
```

Check:

```bash
systemctl list-timers lums-agent.timer
```

Run manually for testing:

```bash
sudo systemctl start lums-agent.service
```

Check:

```bash
sudo systemctl status lums-agent.service
```

Logs:

```bash
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

---

# 🧪 First Agent Test

Before enabling the timer, run:

```bash
sudo systemctl start lums-agent.service
```

Then:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

On the server:

```bash
sudo journalctl \
    -u lums \
    -n 100 \
    --no-pager
```

The client should appear in LUMS.

---

# 🖥️ Client Registration

The current implementation uses the report endpoint for client registration.

The flow is:

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
LUMS identifies hostname
    │
    ├── client exists → update
    │
    └── client missing → create
    │
    ▼
Store updates
    │
    ▼
Store package inventory
```

This is the **current** registration mechanism.

A future explicit enrollment flow can replace or extend it.

---

# 🔐 Agent Authentication Status

This section is intentionally explicit.

The project already contains security helpers for:

* random client tokens
* SHA-256 token hashing
* token verification
* token revocation
* client enable/disable state
* bearer-token extraction
* authenticated client handling

However, security helpers existing in `security.py` do not automatically secure an endpoint.

The current application must explicitly apply the authentication layer.

The following endpoints require special attention:

```text
POST /api/report
GET /api/clients/<client_id>/update-jobs/pending
POST /api/update-jobs/<job_id>/result
```

## Required authorization rules

### `/api/report`

The authenticated client should determine which client record may be updated.

The hostname supplied by the client must not become the sole authorization mechanism.

---

### `/api/.../pending`

The authenticated client must match:

```text
requested client_id
```

Otherwise one client could potentially request another client's pending jobs.

---

### `/api/.../result`

The server must:

1. load the job
2. determine its `client_id`
3. authenticate the caller
4. verify that the caller's client ID matches the job's client ID
5. only then accept the result

This prevents one client from submitting results for another client's job.

---

# 🧪 Automated Security Tests for Agent Endpoints

The agent endpoints should have automated tests covering both authentication and authorization.

At minimum:

```text
/api/report
/api/clients/<client_id>/update-jobs/pending
/api/update-jobs/<job_id>/result
```

## Required test matrix

| Test                             | Expected |
| -------------------------------- | -------- |
| No token                         | `401`    |
| Invalid token                    | `401`    |
| Revoked token                    | `401`    |
| Disabled client                  | `401`    |
| Valid token                      | accepted |
| Client A requests Client B job   | `403`    |
| Client A submits Client B result | `403`    |
| Client A reports as Client B     | rejected |
| Valid client/job relationship    | accepted |

---

# 🧪 Example Automated Test Structure

A test suite should contain cases similar to:

```python
def test_report_requires_client_auth(client):
    response = client.post("/api/report", json={
        "hostname": "client01"
    })

    assert response.status_code == 401
```

Invalid token:

```python
def test_report_rejects_invalid_token(client):
    response = client.post(
        "/api/report",
        headers={"Authorization": "Bearer invalid-token"},
        json={"hostname": "client01"},
    )

    assert response.status_code == 401
```

A client must not access another client's pending job:

```python
def test_client_cannot_claim_another_clients_job(client):
    response = client.get(
        "/api/clients/2/update-jobs/pending",
        headers={"Authorization": "Bearer CLIENT_A_TOKEN"},
    )

    assert response.status_code == 403
```

A client must not submit another client's result:

```python
def test_client_cannot_submit_another_clients_result(client):
    response = client.post(
        "/api/update-jobs/2/result",
        headers={"Authorization": "Bearer CLIENT_A_TOKEN"},
        json={
            "status": "success",
            "reboot_required": False,
        },
    )

    assert response.status_code == 403
```

A valid client/job relationship should succeed.

The exact test implementation must match the actual Flask application and database fixtures.

---

# 🧪 Complete End-to-End Test

Run the complete workflow:

```text
1. LUMS server running
2. SQLite working
3. Nginx running
4. HTTPS working
5. Admin login works
6. Agent starts
7. Client reports
8. Client appears
9. Updates appear
10. Admin creates update job
11. Agent claims job
12. Agent performs update
13. Agent reports result
14. Job becomes completed
15. Update history is created
16. Reboot state is recorded
```

---

# 🔐 Security Headers

LUMS sets security headers including:

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Permissions-Policy
Content-Security-Policy
```

The CSP restricts:

* scripts
* styles
* frames
* forms
* objects
* network connections

to controlled origins.

---

# 🍪 Session Security

Browser sessions use:

```text
HttpOnly
Secure
SameSite=Strict
```

The session lifetime is configured for five minutes.

The dashboard also contains client-side inactivity handling.

The server-side session remains authoritative.

---

# 🛡 Password Security

Passwords are handled using Argon2id.

The application supports password verification and hash re-evaluation.

The database stores:

```text
password hash
```

not:

```text
plaintext password
```

---

# 🧾 Audit Logging

Security-relevant actions are written to:

```text
audit_log
```

The log contains information such as:

* timestamp
* actor type
* actor ID
* action
* target
* result
* details

Example query:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'SELECT timestamp, actor_type, action, result
     FROM audit_log
     ORDER BY id DESC
     LIMIT 20;'
```

---

# 💾 Backups

The most important LUMS state is stored in:

```text
/var/lib/lums/
```

At minimum back up:

```text
lums.db
```

Recommended:

```bash
sudo mkdir -p /var/lib/lums/backups
sudo chmod 700 /var/lib/lums/backups
```

SQLite-native backup:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    ".backup '/var/lib/lums/backups/lums.db.$(date +%Y%m%d-%H%M%S)'"
```

Check:

```bash
sudo ls -lh /var/lib/lums/backups/
```

---

# 🔄 Updating LUMS Safely

Before updating:

```bash
cd /opt/lums-public
git status
```

Then:

```bash
git fetch origin
git log --oneline HEAD..origin/main
```

If the changes are expected:

```bash
git pull --ff-only origin main
```

Create an application backup:

```bash
sudo cp -a \
    /opt/lums-api \
    "/opt/lums-api.backup-$(date +%Y%m%d-%H%M%S)"
```

Deploy:

```bash
sudo rsync -a --delete \
    --exclude='.git/' \
    /opt/lums-public/server/ \
    /opt/lums-api/
```

Syntax-check:

```bash
python3 -m py_compile /opt/lums-api/app.py
```

Restart:

```bash
sudo systemctl restart lums
```

Verify:

```bash
sudo systemctl status lums
curl http://127.0.0.1:5000/api/health
```

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

# ⚠️ Commands That Require Extra Attention

The following commands can change or destroy state:

```text
rsync --delete
rm
rm -rf
apt upgrade
apt autoremove
systemctl restart
systemctl stop
systemctl disable
ufw enable
ufw reset
sqlite restore
database migration
```

Never execute these blindly on a production system.

---

# 📋 Command – Purpose – Risk

| Command                   | Purpose                                       | Risk          |
| ------------------------- | --------------------------------------------- | ------------- |
| `apt update`              | Refresh package metadata                      | 🟢 Low        |
| `apt upgrade`             | Install system updates                        | 🟠 Medium     |
| `apt autoremove`          | Remove packages considered unnecessary        | 🟠 Medium     |
| `git pull --ff-only`      | Update source tree                            | 🟢 Low/Medium |
| `rsync -a`                | Copy deployment files                         | 🟢 Low        |
| `rsync -a --delete`       | Synchronize and delete destination-only files | 🔴 High       |
| `systemctl start lums`    | Start LUMS                                    | 🟢 Low        |
| `systemctl stop lums`     | Stop LUMS                                     | 🟠 Medium     |
| `systemctl restart lums`  | Restart LUMS                                  | 🟠 Medium     |
| `systemctl restart nginx` | Restart web server                            | 🟠 Medium     |
| `systemctl reload nginx`  | Reload Nginx config                           | 🟢 Low/Medium |
| `ufw enable`              | Enable firewall                               | 🟠 Medium     |
| `ufw reset`               | Reset firewall rules                          | 🔴 High       |
| `rm file`                 | Delete file                                   | 🟠 Medium     |
| `rm -rf directory`        | Recursive deletion                            | 🔴 Very high  |
| `sqlite .backup`          | Create SQLite backup                          | 🟢 Low        |
| `cp database backup`      | Copy database                                 | 🟢 Low        |
| database restore          | Replace current database                      | 🔴 High       |

---

# 🚨 Commands That Restart Services

These commands can cause temporary service interruption:

```bash
sudo systemctl restart lums
```

```bash
sudo systemctl restart nginx
```

```bash
sudo systemctl restart lums-agent.service
```

A safer Nginx configuration change is generally:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

because configuration is tested before reload.

---

# 🚨 If LUMS Stops Starting

Do not immediately reinstall everything.

Check:

```bash
sudo systemctl status lums --no-pager
```

Then:

```bash
sudo journalctl \
    -u lums \
    -n 100 \
    --no-pager
```

Check Python:

```bash
python3 -m py_compile /opt/lums-api/app.py
```

Check secret:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' /etc/lums/lums.env \
    && echo "Secret configured" \
    || echo "Secret missing"
```

Check database:

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

# 🔙 Rollback

Stop LUMS:

```bash
sudo systemctl stop lums
```

Find the previous deployment:

```bash
ls -ld /opt/lums-api.backup-*
```

Move the broken deployment away:

```bash
sudo mv \
    /opt/lums-api \
    "/opt/lums-api.failed-$(date +%Y%m%d-%H%M%S)"
```

Restore the desired backup:

```bash
sudo mv \
    /opt/lums-api.backup-TIMESTAMP \
    /opt/lums-api
```

Fix ownership:

```bash
sudo chown -R lums:lums /opt/lums-api
```

Syntax-check:

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

# 🧪 Database Integrity

Always check the SQLite database after unexpected shutdowns or before recovery:

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

# 📦 Aptly Integration

LUMS can coexist with an Aptly package repository.

Example:

```text
Linux Client
     │
     │ APT
     ▼
   Aptly
     │
     ▼
Ubuntu repository

LUMS
     │
     │ update management
     ▼
Linux Client
```

Aptly can be served statically by Nginx:

```nginx
location /aptly/ {
    alias /srv/lums/aptly/public/;
    autoindex on;
}
```

Aptly does not need to be a systemd service when Nginx serves its published files directly.

---

# 🔍 Troubleshooting

## LUMS service is down

```bash
sudo systemctl status lums
sudo journalctl -u lums -n 100 --no-pager
```

---

## Flask works but HTTPS does not

Check:

```bash
sudo nginx -t
sudo systemctl status nginx
sudo journalctl -u nginx -n 100 --no-pager
```

---

## HTTPS works but client cannot connect

Check:

```bash
curl -k https://SERVER_IP/api/health
```

From the client:

```bash
curl -k https://SERVER_IP/api/health
```

Check firewall:

```bash
sudo ufw status verbose
```

---

## Client does not appear

Check the agent:

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

Server logs:

```bash
sudo journalctl \
    -u lums \
    -n 100 \
    --no-pager
```

---

## Client reports but updates are missing

Check:

```bash
sudo apt update
```

on the client.

Then run:

```bash
sudo systemctl start lums-agent.service
```

Check the agent logs.

---

# 🧪 Security Test Checklist

Before considering a release complete:

```text
[ ] Correct password accepted
[ ] Wrong password rejected
[ ] Unknown user rejected
[ ] Disabled user rejected
[ ] Session created
[ ] Session cleared on logout
[ ] CSRF token generated
[ ] Missing CSRF rejected
[ ] Invalid CSRF rejected
[ ] Security headers present
[ ] CSP present
[ ] Database integrity verified
[ ] Agent without authentication rejected
[ ] Agent with invalid token rejected
[ ] Revoked token rejected
[ ] Disabled client rejected
[ ] Client A cannot access Client B
[ ] Client A cannot claim Client B job
[ ] Client A cannot submit Client B result
[ ] Valid client can report
[ ] Valid client can claim own job
[ ] Valid client can submit own result
```

---

# 🧪 Recommended Test Commands

Check service:

```bash
sudo systemctl status lums --no-pager
```

Check agent:

```bash
sudo systemctl status lums-agent.service --no-pager
```

Check timer:

```bash
systemctl list-timers lums-agent.timer
```

Check ports:

```bash
sudo ss -ltnp
```

Check Flask:

```bash
curl http://127.0.0.1:5000/api/health
```

Check HTTPS:

```bash
curl -k https://SERVER_IP/api/health
```

Check Nginx:

```bash
sudo nginx -t
```

Check SQLite:

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

---

# 🚢 Deployment Model

The recommended deployment separates source and runtime:

```text
GitHub
   │
   ▼
/opt/lums-public
   │
   │ reviewed deployment
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

This allows:

* Git-based version control
* controlled deployment
* backups
* rollback
* testing
* clear separation of source and runtime state

---

# 🧱 Security Principles

LUMS follows several basic security principles.

## Least Privilege

The server runs as:

```text
lums
```

rather than root.

---

## Secrets Outside Git

Secrets belong in:

```text
/etc/lums/
```

not in the repository.

---

## Defense in Depth

Security is not based on a single control.

The system combines:

```text
TLS
+
authentication
+
sessions
+
CSRF
+
password hashing
+
security headers
+
audit logging
+
filesystem permissions
+
systemd hardening
+
firewall
```

---

## Internal Infrastructure

LUMS is primarily intended for:

* internal networks
* homelabs
* test environments
* small infrastructures

It should not simply be placed on the public Internet without additional security review.

---

# 📋 Final Installation Checklist

## Server

```text
[ ] Ubuntu Server 26.04 installed
[ ] System updated
[ ] Required packages installed
[ ] lums user created
[ ] /opt/lums-api created
[ ] /var/lib/lums created
[ ] /etc/lums created
[ ] Repository cloned
[ ] Application deployed
[ ] LUMS_SECRET_KEY configured
[ ] Database initialized
[ ] Security migration applied
[ ] Administrator created
[ ] systemd service installed
[ ] LUMS service running
```

## Network

```text
[ ] SSH allowed
[ ] HTTPS allowed
[ ] Optional HTTP redirect allowed
[ ] Flask port 5000 not publicly exposed
[ ] UFW enabled
[ ] TLS configured
[ ] Nginx configured
[ ] nginx -t successful
```

## Agent

```text
[ ] Python installed
[ ] Agent installed
[ ] Agent configuration created
[ ] Agent configuration protected
[ ] systemd service installed
[ ] systemd timer installed
[ ] Agent starts successfully
[ ] Client report received
[ ] Client visible in dashboard
```

## Update workflow

```text
[ ] Updates detected
[ ] Update job created
[ ] Agent claims job
[ ] Package updated
[ ] Result reported
[ ] Job completed
[ ] Reboot requirement recorded
[ ] History recorded
```

## Recovery

```text
[ ] Database backup exists
[ ] Application backup exists
[ ] Rollback procedure understood
[ ] Database integrity check tested
```

## Security

```text
[ ] Admin password protected
[ ] HTTPS enabled
[ ] CSRF tested
[ ] Security headers tested
[ ] Agent authentication tested
[ ] Client isolation tested
[ ] Audit logging tested
```

---

# 🏁 Quick Reference

### LUMS service

```bash
sudo systemctl status lums
```

### LUMS logs

```bash
sudo journalctl -u lums -f
```

### Agent

```bash
sudo systemctl status lums-agent.service
```

### Agent logs

```bash
sudo journalctl -u lums-agent.service -f
```

### Agent timer

```bash
systemctl list-timers lums-agent.timer
```

### Nginx

```bash
sudo nginx -t
```

### HTTPS health

```bash
curl -k https://SERVER_IP/api/health
```

### Database integrity

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    'PRAGMA integrity_check;'
```

### Backup

```bash
sudo -u lums sqlite3 \
    /var/lib/lums/lums.db \
    ".backup '/var/lib/lums/backups/lums.db.$(date +%Y%m%d-%H%M%S)'"
```

---

# 🧠 Project Philosophy

LUMS is intentionally built with relatively simple and inspectable components:

```text
Python
Flask
SQLite
Linux
systemd
Nginx
```

The goal is not to hide complexity behind layers of orchestration.

The goal is to understand the system.

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

---

# 🐛 The `segfault // override` Principle

Every homelab eventually reaches this point:

```text
"That works."

        ↓

"Can we make it better?"

        ↓

"Let's add security."

        ↓

"Now we need logging."

        ↓

"Oh."

        ↓

"This could be a lab."
```

And that is basically how LUMS happened.

**`segfault // override`**

*System Builder · Infrastructure / Security · Controlled Chaos*

> **Build it. Test it. Break it. Understand it. Harden it.**

---

# 📜 License

See [`LICENSE`](LICENSE).

---

# 🔗 Repository

GitHub:

https://github.com/NovaForgeCtrl/LUMS

---

# ❤️ LUMS

```text
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                         L U M S                             │
│                                                             │
│       Linux Update Management without the noise.            │
│                                                             │
│       Build. Test. Break. Understand. Harden.              │
│                                                             │
│                   segfault // override                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Designed for **homelabs, learning, testing and small internal infrastructures**.
