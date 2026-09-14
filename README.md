# 🛰️ LUMS – Linux Update Management Server

> **Linux Update Management without the noise.**

**LUMS** is a lightweight update management solution for Linux environments.

It provides a central management server for:

* 🖥️ registering Linux clients
* 📦 collecting system and package information
* 🔎 detecting available updates
* 🧭 managing connected clients
* ⚙️ creating remote update jobs
* 📊 tracking update results
* 📝 recording update history
* 🔄 detecting reboot requirements
* 🔐 authenticating administrators and Linux clients
* 🛡️ auditing security-relevant actions

Designed primarily for **Linux homelabs, test environments and small internal infrastructures**.

---

## 👾 Built with Controlled Chaos

LUMS is a practical infrastructure project focused on learning, testing and building things that are actually useful.

**Built by**

```text
segfault // override
```

*System Builder · Infrastructure / Security · Controlled Chaos*

> **Build it. Test it. Break it. Understand it. Harden it.**

---

# 🚀 Features

## 🖥️ LUMS Server

* Flask-based web interface
* REST API
* SQLite database
* Administrator authentication
* Argon2id password hashing
* Secure server-side sessions
* Session expiration
* CSRF protection
* Client bearer-token authentication
* Client token hashing and revocation
* Client isolation
* Audit logging
* Security response headers
* Content Security Policy
* Client inventory
* Available update tracking
* Installed package inventory
* Remote update jobs
* Per-package update status
* Update history
* Reboot-required detection

## 🤖 LUMS Agent

The LUMS Agent runs on managed Linux systems and can:

* report system information
* report installed packages
* detect available updates
* receive pending update jobs
* install selected package updates
* report update results
* detect reboot requirements
* authenticate against the LUMS API
* run manually or through a systemd timer

---

# 🧭 Architecture

```text
                         LUMS Server
              ┌─────────────────────────────┐
              │                             │
              │      Flask Web Interface    │
              │          REST API           │
              │                             │
              │          SQLite             │
              │                             │
              │     Authentication          │
              │     Authorization           │
              │     Audit Logging            │
              │                             │
              └──────────────┬──────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
           Linux VM       Linux PC       Linux Server
           LUMS Agent     LUMS Agent     LUMS Agent
              │              │              │
              └──────────────┴──────────────┘
                         Update Jobs
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

Install the required packages:

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

## Client

The agent is intended primarily for Debian/Ubuntu-based Linux systems.

Required components include:

* Python 3
* systemd
* apt
* dpkg
* apt-cache

---

# 🚀 Installation

## 1. Clone the repository

```bash
git clone https://github.com/NovaForgeCtrl/LUMS.git
cd LUMS
```

---

# 🖥️ Server Installation

Create the application and database directories:

```bash
sudo mkdir -p /opt/lums-api
sudo mkdir -p /var/lib/lums
```

Copy the server files:

```bash
sudo cp -r server/* /opt/lums-api/
```

Initialize the database:

```bash
sudo python3 /opt/lums-api/init_db.py
```

For a development or laboratory test installation, start Flask directly:

```bash
sudo python3 /opt/lums-api/app.py
```

The application uses port:

```text
5000
```

Test the API:

```bash
curl http://127.0.0.1:5000/api/health
```

A healthy server returns a JSON response indicating that the LUMS API is available.

> ⚠️ The Flask development server is intended for development and laboratory testing. Permanent deployments should use systemd and a TLS-enabled reverse proxy.

---

# 🔐 Security Configuration

Security is a core part of the current LUMS architecture.

LUMS requires a server-side secret for secure Flask session handling.

The secret must **never** be stored in Git.

Example:

```text
/etc/lums/lums.env
```

Example content:

```text
LUMS_SECRET_KEY=<random-secret>
```

The configuration file should be readable only by the LUMS service account or an appropriately restricted system group.

Example:

```bash
sudo chmod 640 /etc/lums/lums.env
```

Never commit this file.

---

# 👤 Administrator Authentication

LUMS provides an administrator login for the management interface.

Administrator passwords are protected using **Argon2id password hashing**.

Passwords are never stored in plaintext.

Create an administrator account:

```bash
sudo python3 /opt/lums-api/create_admin.py
```

The administrator account provides access to the protected management interface and administrative operations.

---

# 🧬 Database Migration

Security-related database structures are maintained through migrations.

The security foundation migration is located at:

```text
server/security_migration.py
```

It provides structures for:

* administrator users
* audit logging
* schema migration tracking
* client token hashes
* token metadata
* client enable/disable state
* token revocation

Migrations are designed to be repeatable and should be executed before using a newly deployed security-enabled version.

---

# 🔑 Web Authentication

Protected web pages require administrator authentication.

Unauthenticated users are redirected to:

```text
/login
```

The authentication system uses:

* secure sessions
* HttpOnly cookies
* Secure cookies
* SameSite protection
* session expiration
* session regeneration on login
* CSRF protection
* generic authentication failures

The management interface includes an explicit logout function.

The browser also performs automatic logout after a period of inactivity.

---

# 🛡️ CSRF Protection

State-changing browser requests are protected against Cross-Site Request Forgery.

Examples include:

* creating update jobs
* logging out
* other authenticated browser-side state changes

CSRF tokens are generated per session and validated server-side.

The LUMS Agent does not use browser sessions.

Agent requests authenticate using individual bearer tokens.

---

# 🤖 Client Authentication

Managed Linux clients authenticate using individual client tokens.

Requests use:

```text
Authorization: Bearer <client-token>
```

LUMS does **not** store the original client token.

Instead, the server stores a cryptographic hash of the token.

Client tokens can be:

* generated
* validated
* revoked
* disabled

Each client has its own authentication identity.

A client cannot use its token to access another client's jobs or data.

---

# 📜 Audit Logging

Security-relevant actions are recorded in the LUMS audit log.

Recorded information includes:

* timestamp
* actor type
* actor ID
* action
* target
* result
* optional details

Examples include:

* administrator login
* administrator logout
* client authentication
* client registration
* update job creation
* update job results

> 🔒 Passwords, tokens and other secrets must never be written to the audit log.

---

# 🧱 Security Headers

LUMS applies security-related HTTP response headers including:

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Permissions-Policy
Content-Security-Policy
```

The Content Security Policy restricts browser resources to trusted application sources and disables unnecessary capabilities.

---

# 🔒 TLS / Reverse Proxy

For permanent deployments, LUMS should not be exposed directly through the Flask development server.

Recommended architecture:

```text
                  HTTPS
                    │
                    ▼
             ┌─────────────┐
             │    Nginx    │
             │ TLS / Proxy │
             └──────┬──────┘
                    │
                    ▼
             ┌─────────────┐
             │    LUMS     │
             │ 127.0.0.1  │
             │    :5000    │
             └─────────────┘
```

The Flask application should bind to localhost when Nginx is used as the entry point.

Example:

```text
127.0.0.1:5000
```

Nginx terminates TLS and proxies requests to the local LUMS application.

For internal laboratory installations, a private CA or appropriately managed internal certificate can be used.

---

# 🤖 LUMS Agent Installation

The LUMS Agent is installed on every Linux system that should be managed.

Create the agent directory:

```bash
sudo mkdir -p /opt/lums-agent
```

Copy the agent:

```bash
sudo cp agent/agent.py /opt/lums-agent/
```

Install the systemd service:

```bash
sudo cp agent/lums-agent.service /etc/systemd/system/
```

Create the agent configuration:

```bash
sudo tee /etc/default/lums-agent > /dev/null <<'EOF'
LUMS_BASE=https://SERVER-IP
EOF
```

Replace `SERVER-IP` with the address or hostname of the LUMS server.

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Run the agent:

```bash
sudo systemctl start lums-agent.service
```

Check the result:

```bash
sudo systemctl status lums-agent.service
```

The agent is implemented as a one-shot service.

After a successful run, systemd may show:

```text
Active: inactive (dead)
```

This is expected.

Inspect the agent log:

```bash
sudo journalctl -u lums-agent.service -n 50 --no-pager
```

---

# ⏱️ Periodic Agent Execution

For regular reporting, use the systemd timer.

Create:

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

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Enable the timer:

```bash
sudo systemctl enable --now lums-agent.timer
```

Check the timer:

```bash
systemctl list-timers --all | grep lums
```

---

# 🌐 Multiple Clients

A single LUMS server can manage multiple Linux clients.

Each client receives its own:

* client identity
* authentication token
* system information
* available updates
* installed package information
* update jobs
* update history

```text
                         LUMS Server
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
          Client 1         Client 2         Client 3
           Agent             Agent            Agent
```

Clients are isolated from each other by the server-side authorization layer.

---

# 📡 Client Information

The agent reports information including:

* hostname
* IP address
* operating system
* kernel
* architecture
* agent version
* installed packages
* available updates

This information is displayed through the LUMS management interface.

---

# ⚙️ Update Jobs

Administrators can create update jobs for managed clients.

A job can contain multiple selected packages.

The client agent retrieves pending jobs, performs the requested package operations and reports the result to the server.

### Overall job states

```text
pending
running
success
partial
failed
```

### Package states

```text
success
failed
timeout
```

A job is considered:

* `success` if all selected packages completed successfully
* `partial` if at least one package succeeded but others failed
* `failed` if no selected package completed successfully

Update history is retained in the LUMS database.

---

# 🔄 Reboot Detection

After package operations, the agent checks whether the Linux client requires a reboot.

The reboot state is reported to the LUMS server and can be displayed as part of the client's system information.

---

# 💾 Database

The default database location is:

```text
/var/lib/lums/lums.db
```

The database contains runtime information such as:

* clients
* available updates
* installed packages
* update jobs
* update job packages
* update history
* administrator users
* audit events
* schema migration state

The SQLite database is runtime data and must never be committed to Git.

---

# 📡 REST API

LUMS exposes REST API endpoints for administration and agent communication.

## Health

```text
GET /api/health
```

## Client Reporting

```text
POST /api/report
```

The agent uses this endpoint to report client information.

## Clients

```text
GET /api/clients
GET /api/clients/<client_id>
```

## Client Updates

```text
GET /api/clients/<client_id>/updates
```

## Installed Packages

```text
GET /api/clients/<client_id>/packages
```

## Update Jobs

Create a job:

```text
POST /api/clients/<client_id>/update-jobs
```

Get jobs:

```text
GET /api/clients/<client_id>/update-jobs
```

Get the next pending job:

```text
GET /api/clients/<client_id>/update-jobs/pending
```

Report a job result:

```text
POST /api/update-jobs/<job_id>/result
```

Get a job:

```text
GET /api/update-jobs/<job_id>
```

## Update History

```text
GET /api/clients/<client_id>/update-history
GET /api/update-history
```

Protected administrative endpoints require an authenticated administrator session.

Agent-specific operations require valid client authentication.

---

# 🗂️ Project Structure

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

# 🧪 Testing

Security-sensitive components should be tested before deployment.

Important test areas include:

* password hashing
* password verification
* client token generation
* client token hashing
* client token validation
* session handling
* session expiration
* CSRF validation
* administrator authentication
* API authentication
* client authorization
* security headers
* update job authorization
* update job result validation

Production-like deployments should additionally verify:

* TLS configuration
* file permissions
* service account permissions
* database permissions
* secret handling
* backup and recovery
* firewall rules

---

# 🚢 Deployment

For permanent or production-like laboratory installations, use a controlled deployment process.

```text
GitHub
   │
   ▼
main
   │
   ▼
Review / Tests
   │
   ▼
Backup current installation
   │
   ▼
Deploy application
   │
   ▼
Run migrations
   │
   ▼
Restart LUMS
   │
   ▼
Health Check
   │
   ▼
Verify Login / API
```

Avoid uncontrolled deployment methods such as:

```bash
git pull && restart
```

without first creating a backup and verifying the changes.

---

# 💾 Backup

The LUMS SQLite database contains operational data and should be backed up before migrations or major deployments.

Example:

```bash
sudo cp \
    /var/lib/lums/lums.db \
    /var/lib/lums/lums.db.backup
```

Production backup procedures should also protect:

* LUMS database
* server configuration
* TLS certificates and private keys
* secret configuration

Secrets and private keys must remain outside Git.

---

# 📦 Aptly Integration

LUMS can be used together with an internal APT repository such as Aptly.

A typical environment can look like:

```text
              Ubuntu Mirrors
                    │
                    ▼
                  Aptly
                    │
                    ▼
            Internal APT Repository
                    │
             ┌──────┴──────┐
             ▼             ▼
          Client 1      Client 2
             │             │
             └──────┬──────┘
                    ▼
                   LUMS
```

Aptly repository data is intentionally not part of this repository.

LUMS does not require Aptly. Clients can also use normal Debian/Ubuntu package repositories.

---

# 🧱 Security Model

LUMS follows a defense-in-depth approach for internal infrastructures and laboratory environments.

```text
                    LUMS
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
   Administrator                 Linux Client
        │                           │
        ▼                           ▼
   Web Session                 Bearer Token
        │                           │
        ▼                           ▼
      CSRF                    Client Identity
        │                           │
        └─────────────┬─────────────┘
                      ▼
               Authorization
                      │
                      ▼
                 Audit Log
```

Current security controls include:

* Argon2id password hashing
* secure session cookies
* session expiration
* session regeneration
* CSRF protection
* individual client tokens
* SHA-256 client token hashes
* token revocation
* client enable/disable state
* client-specific authorization
* audit logging
* security headers
* Content Security Policy
* restricted service account
* external secret configuration
* TLS / reverse proxy support
* controlled deployment practices

LUMS should be deployed behind appropriate network controls.

It should **not be exposed directly to the public Internet** without a deliberate security review.

> 🔐 No software system can be considered absolutely secure. LUMS aims to provide defense in depth and controlled operation within its intended environment.

---

# 🔒 Repository Privacy

The Git repository contains source code and documentation only.

The following must never be committed:

* SQLite databases
* database backups
* APT repository data
* Aptly data
* logs
* client inventory data
* passwords
* client tokens
* runtime token hashes
* Flask/session secrets
* private keys
* TLS private keys
* local configuration files
* production-only infrastructure data

Before pushing changes, inspect:

```bash
git status
git diff
```

For staged changes:

```bash
git diff --cached
```

When working on security-sensitive changes, verify the final diff before pushing.

---

# 🧰 Development

Clone the repository:

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

Initialize a development database:

```bash
sudo python3 server/init_db.py
```

Configure a development secret outside the repository.

Start the application:

```bash
python3 server/app.py
```

The development server is intended for local testing only.

---

# 🧑‍💻 Project Philosophy

LUMS is not intended to be an enterprise-sized update management platform.

It is a practical project for:

* homelabs
* infrastructure experiments
* Linux administration
* security testing
* automation
* learning
* controlled environments

The project follows a simple philosophy:

```text
Build.
Test.
Break.
Understand.
Harden.
Repeat.
```

---

# 👾 Signature

```text
segfault // override
```

*Infrastructure · Security · Controlled Chaos*

> **Technology without noise.**

---

# 📄 License

LUMS is licensed under the MIT License.

See [LICENSE](LICENSE).

---

# 🔗 Project

**LUMS – Linux Update Management Server**

GitHub:

https://github.com/NovaForgeCtrl/LUMS
