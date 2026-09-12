# LUMS – Linux Update Management Server

LUMS (Linux Update Management Server) is a lightweight update management solution for Linux environments.

It provides a central server for:

* registering Linux clients
* collecting system and package information
* detecting available updates
* displaying connected clients
* creating remote update jobs
* tracking update results
* recording update history
* detecting reboot requirements

The project is designed primarily for Linux homelabs, test environments and small infrastructures.

---

# Quick Start

This section provides a minimal setup for a new LUMS installation.

## 1. Clone the repository

```bash
git clone https://github.com/NovaForgeCtrl/LUMS.git
cd LUMS
```

## 2. Install the server requirements

On an Ubuntu Server:

```bash
sudo apt update
sudo apt install -y python3 python3-flask sqlite3 git curl
```

## 3. Install the LUMS server

Create the application directories:

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

## 4. Start LUMS

For a first test, start the Flask application directly:

```bash
sudo python3 /opt/lums-api/app.py
```

The server listens on port `5000`.

From another terminal, test the API:

```bash
curl http://127.0.0.1:5000/api/health
```

The web interface is available at:

```text
http://SERVER-IP:5000
```

Replace `SERVER-IP` with the IP address of the LUMS server.

For permanent installations, use a systemd service and optionally a reverse proxy such as Nginx. See the server installation section below.

---

# LUMS Agent

## 5. Install the LUMS Agent on a Linux client

The agent is installed on the Linux machine that should be managed by LUMS.

If the repository was cloned using the Quick Start instructions, the repository is located at:

```text
~/LUMS
```

Define the repository path:

```bash
LUMS_DIR="$HOME/LUMS"
```

Create the agent directory:

```bash
sudo mkdir -p /opt/lums-agent
```

Copy the agent:

```bash
sudo cp "$LUMS_DIR/agent/agent.py" /opt/lums-agent/
```

Install the systemd service:

```bash
sudo cp "$LUMS_DIR/agent/lums-agent.service" /etc/systemd/system/
```

Create the agent configuration:

```bash
sudo tee /etc/default/lums-agent > /dev/null <<'EOF'
LUMS_BASE=http://SERVER-IP:5000
EOF
```

Replace `SERVER-IP` with the IP address of the LUMS server.

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Start the agent:

```bash
sudo systemctl start lums-agent.service
```

Check the agent:

```bash
sudo systemctl status lums-agent.service
```

The agent is a one-shot service. After a successful run, systemd may show:

```text
Active: inactive (dead)
```

This is expected.

To inspect the agent output:

```bash
sudo journalctl -u lums-agent.service -n 50 --no-pager
```

A successful run should show that the client information was collected and the report was accepted by the LUMS API.

---

# 6. Connect the client

After the first successful agent run, the client reports information including:

* hostname
* IP address
* operating system
* kernel
* architecture
* agent version
* installed packages
* available updates

The client can then be managed through the LUMS web interface.

---

# 7. Enable periodic agent execution

For regular reporting, the agent can be executed using a systemd timer.

Create the timer:

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

Enable and start the timer:

```bash
sudo systemctl enable --now lums-agent.timer
```

Check the timer:

```bash
systemctl list-timers --all | grep lums
```

The agent will now run periodically.

---

# Quick Start Architecture

```text
                    LUMS Server
               ┌───────────────────┐
               │ Flask Webinterface │
               │ REST API           │
               │ SQLite             │
               └─────────┬─────────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
           Linux VM   Linux PC   Linux Server
           Agent      Agent      Agent
              │          │          │
              └──────────┴──────────┘
                    Update Jobs
```

---

# Features

## LUMS Server

* Flask-based web interface
* SQLite database
* Client inventory
* Available update tracking
* Installed package inventory
* Remote update jobs
* Per-package update status
* Update history
* Reboot-required information
* REST API

## LUMS Agent

The Linux client agent:

* reports system information
* reports installed packages
* detects available updates
* checks for pending update jobs
* installs selected package updates
* reports the result to the LUMS server
* detects whether a reboot is required
* supports systemd integration

---

# Project Structure

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
│   ├── static/
│   │   ├── app.js
│   │   ├── client.js
│   │   └── style.css
│   └── templates/
│       ├── client.html
│       └── index.html
│
├── .gitignore
├── LICENSE
└── README.md
```

---

# Requirements

## Server

Recommended:

* Ubuntu Server 26.04 LTS
* Python 3
* Flask
* SQLite
* Git
* curl

Install the required packages:

```bash
sudo apt update
sudo apt install -y python3 python3-flask sqlite3 git curl
```

## Client

The agent is intended for Debian/Ubuntu based Linux systems.

Required tools include:

* Python 3
* systemd
* apt
* dpkg
* apt-cache

---

# Server Installation

Create the application directories:

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

Start the application:

```bash
sudo python3 /opt/lums-api/app.py
```

The Flask application listens on:

```text
http://0.0.0.0:5000
```

For local testing:

```bash
curl http://127.0.0.1:5000/api/health
```

A healthy server should return a JSON response.

---

# Database

The default database location is:

```text
/var/lib/lums/lums.db
```

The database is created by:

```bash
python3 server/init_db.py
```

The database contains tables for:

* clients
* available updates
* installed packages
* update jobs
* update job packages
* update history

The database contains runtime data and must not be committed to Git.

---

# LUMS Agent Installation

Create the agent directory:

```bash
sudo mkdir -p /opt/lums-agent
```

Copy the agent:

```bash
sudo cp agent/agent.py /opt/lums-agent/
```

Copy the systemd service:

```bash
sudo cp agent/lums-agent.service /etc/systemd/system/
```

Create the configuration file:

```bash
sudo tee /etc/default/lums-agent > /dev/null <<'EOF'
LUMS_BASE=http://SERVER-IP:5000
EOF
```

Replace `SERVER-IP` with the address of the LUMS server.

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Run the agent manually:

```bash
sudo systemctl start lums-agent.service
```

Check the result:

```bash
sudo systemctl status lums-agent.service
```

For detailed output:

```bash
sudo journalctl -u lums-agent.service -n 50 --no-pager
```

The agent is designed as a one-shot systemd service. It performs one reporting cycle and then exits.

For regular execution, use the systemd timer described below.

---

# Systemd Timer

The agent can be executed periodically using a systemd timer.

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

Then enable the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lums-agent.timer
```

Check the timer:

```bash
systemctl list-timers --all | grep lums
```

---

# Agent Configuration

The example configuration is provided in:

```text
agent/lums-agent.env.example
```

The main configuration variable is:

```text
LUMS_BASE
```

Example:

```text
LUMS_BASE=http://SERVER-IP:5000
```

Replace `SERVER-IP` with the IP address or hostname of the LUMS server.

Do not commit private infrastructure addresses or credentials to the public repository.

---

# REST API

The server provides endpoints for client communication and management.

## Health

```text
GET /api/health
```

## Client Reporting

```text
POST /api/report
```

The agent uses this endpoint to report:

* hostname
* IP address
* operating system
* kernel
* architecture
* agent version
* available updates
* installed packages

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

---

# Update Job States

Jobs can have the following overall states:

```text
pending
running
success
partial
failed
```

Individual packages can report:

```text
success
failed
timeout
```

A job is considered:

* `success` if all selected packages were updated successfully
* `partial` if some packages succeeded and others failed
* `failed` if no selected package was successfully updated

---

# Security

LUMS is currently designed for trusted laboratory and internal environments.

The API currently does not provide a full authentication and authorization layer.

Therefore:

**Do not expose the LUMS API directly to the public Internet.**

Recommended deployment:

```text
Linux Clients
      |
      v
  LUMS Agent
      |
      v
+-------------+
| LUMS Server |
|   Flask     |
|   SQLite    |
+-------------+
      |
      v
  Internal LAN
```

For production environments, additional security controls such as:

* authentication
* authorization
* TLS
* firewall restrictions
* reverse proxy
* audit logging

should be considered.

---

# Aptly Integration

LUMS can be used together with an internal APT repository such as Aptly.

A typical setup can look like:

```text
Ubuntu Repository
       |
       v
     Aptly
       |
       v
Internal APT Repository
       |
       v
 Linux Clients
       |
       v
     LUMS
```

Aptly repository data is intentionally not part of this Git repository.

---

# Development

Clone the repository:

```bash
git clone https://github.com/NovaForgeCtrl/LUMS.git
cd LUMS
```

Initialize the database:

```bash
sudo python3 server/init_db.py
```

Start the development server:

```bash
python3 server/app.py
```

Then open:

```text
http://127.0.0.1:5000
```

---

# Repository Privacy

This repository contains source code only.

The following data must never be committed:

* `lums.db`
* SQLite databases
* APT repository data
* Aptly data
* logs
* client inventory data
* private IP addresses
* passwords
* API tokens
* private keys
* local configuration files
* generated runtime data

The `.gitignore` file contains rules for common local and runtime data.

---

# License

LUMS is licensed under the MIT License.

See [LICENSE](LICENSE).

---

# Project

**LUMS – Linux Update Management Server**

GitHub:

https://github.com/NovaForgeCtrl/LUMS
