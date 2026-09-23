# LUMS Installation Guide

## Linux Update Management Server

**Version:** 3.0
**Project:** LUMS
**Slogan:** Linux Update Management without the noise.

---

# 1. About LUMS

LUMS is a centralized Linux update management system for managing Linux clients, monitoring their update state, creating update jobs and executing controlled maintenance operations.

The project is designed around a simple principle:

> **Linux update management without the noise.**

LUMS does not attempt to replace the native package manager of a Linux distribution.

Instead, it provides a management layer above the existing package-management system.

The client agent detects the locally available package manager and uses the corresponding implementation.

Currently supported package managers are:

```text
APT
pacman
```

This allows the same LUMS agent architecture to support Debian/Ubuntu systems as well as Arch Linux.

---

# 2. Current Project Status

The current LUMS implementation consists of:

* LUMS server
* Web interface
* SQLite database
* Flask application
* Gunicorn
* Nginx reverse proxy
* HTTPS
* Docker deployment
* Hardened Docker container
* Linux client agent
* Execution watcher
* Client authentication
* Client reporting
* Update jobs
* Package installation
* Package removal
* Individual package updates
* Complete system updates
* Audit logging
* Client token management
* Token rotation
* Interrupted-job recovery
* Idle-aware execution
* Multi-distribution package management

The following client platforms have been tested:

```text
Debian 13 Trixie
Arch Linux
```

The current agent version is:

```text
1.6.0
```

---

# 3. Architecture

The current architecture consists of a management server and independently managed Linux clients.

```text
                              Browser
                                 |
                                 | HTTPS :443
                                 v
                         +---------------+
                         |     Nginx     |
                         | Reverse Proxy |
                         +-------+-------+
                                 |
                                 | localhost
                                 v
                         +---------------+
                         | Docker Host   |
                         |               |
                         | 127.0.0.1:5050|
                         +-------+-------+
                                 |
                                 v
                    +--------------------------+
                    |      LUMS Container       |
                    |                          |
                    |       Gunicorn           |
                    |           |              |
                    |         Flask            |
                    |           |              |
                    |         SQLite           |
                    +------------+-------------+
                                 |
                         HTTPS / Bearer Auth
                                 |
              +------------------+------------------+
              |                  |                  |
              v                  v                  v
        +-----------+      +-----------+      +-----------+
        | Debian 13 |      |   Arch    |      |  Client   |
        |           |      |  Linux    |      |           |
        | lums-agent|      | lums-agent |      | lums-agent|
        | watcher   |      | watcher   |      | watcher   |
        | APT       |      | pacman    |      | supported |
        +-----------+      +-----------+      +-----------+
```

---

# 4. Server Architecture

The LUMS server consists of several layers.

```text
Browser
   |
   v
Nginx
   |
   v
HTTPS
   |
   v
127.0.0.1:5050
   |
   v
Docker
   |
   v
Gunicorn
   |
   v
Flask
   |
   v
SQLite
```

Each layer has a separate responsibility.

---

## 4.1 Nginx

Nginx is the externally reachable web endpoint.

It provides:

* HTTPS
* TLS termination
* Reverse proxying
* HTTP-to-HTTPS redirection
* Security headers
* External access on port 443

The Flask application is not directly exposed to the network.

---

## 4.2 Docker

The LUMS application runs inside a Docker container.

The container:

* runs as a non-root user
* uses a read-only root filesystem
* drops Linux capabilities
* uses a temporary filesystem for `/tmp`
* receives the application secret through a read-only secret mount
* stores persistent application data in a Docker volume

The current application container uses:

```text
python:3.13-slim
```

---

## 4.3 Gunicorn

Gunicorn provides the WSGI application server.

The Flask development server is not used for the current deployment.

The normal process chain is:

```text
Docker
  |
  v
docker-entrypoint.sh
  |
  +--> Database initialization
  |
  v
Gunicorn
  |
  v
Flask
```

---

## 4.4 Flask

Flask provides:

* Web interface
* REST API
* Authentication
* Client API
* Job management
* Reporting
* Database access
* Security handling

The Flask application is located in:

```text
server/app.py
```

---

## 4.5 SQLite

SQLite stores LUMS application data.

The database is stored inside the persistent Docker volume:

```text
lums-data
```

The database must therefore not be stored inside the disposable container filesystem.

---

# 5. Client Architecture

A LUMS client contains two primary components:

```text
/opt/lums-agent/
├── agent.py
└── watcher.py
```

The components have different responsibilities.

---

## 5.1 LUMS Agent

The agent is responsible for:

* System information
* Hostname
* IP information
* Operating system information
* Kernel information
* Installed package count
* Available update count
* Client reporting
* Job result reporting
* Client authentication

The agent also provides the package-management abstraction used for update operations.

---

## 5.2 Execution Watcher

The watcher is responsible for:

* Checking pending jobs
* Checking idle state
* Claiming jobs
* Executing jobs
* Handling execution results
* Reporting job completion
* Recovering interrupted jobs

The watcher runs independently of the normal reporting process.

---

# 6. Supported Linux Package Managers

LUMS currently supports:

```text
APT
pacman
```

The package manager is detected automatically.

The agent contains:

```text
AptPackageManager
PacmanPackageManager
```

and selects the correct implementation during startup.

---

## 6.1 Package Manager Detection

The detection logic checks for the locally available package manager.

Conceptually:

```text
apt available?
    |
    +-- yes --> AptPackageManager
    |
    +-- no
         |
         v
pacman available?
    |
    +-- yes --> PacmanPackageManager
    |
    +-- no --> unsupported system
```

If no supported package manager is found, the agent terminates with an explicit error.

---

# 7. APT Support

APT is used on Debian and Ubuntu systems.

LUMS uses the native tools of the operating system.

Examples:

```text
Installed packages
    dpkg-query

Available updates
    apt list --upgradable

Install package
    apt-get install -y

Remove package
    apt-get remove -y

Update package
    apt-get install --only-upgrade -y

Update system
    apt-get upgrade -y

Candidate version
    apt-cache policy
```

LUMS does not maintain its own package repository.

---

# 8. pacman Support

Arch Linux uses pacman.

LUMS uses:

```text
pacman -Q
pacman -Qu
pacman -S
pacman -R
pacman -Syu
pacman -Si
```

Examples:

```text
Installed packages
    pacman -Q

Available updates
    pacman -Qu

Package state
    pacman -Q <package>

Install
    pacman -S --noconfirm <package>

Remove
    pacman -R --noconfirm <package>

Update package
    pacman -S --noconfirm <package>

System update
    pacman -Syu --noconfirm
```

The Arch implementation is handled through the same package-manager abstraction as APT.

---

# 9. Tested Client Platforms

## Debian 13

The Debian 13 client has been successfully tested with:

```text
LUMS Agent 1.6.0
APT
systemd
systemd timer
HTTPS
Bearer authentication
Update jobs
```

The Debian client successfully reported:

```text
PACKAGES 355
UPDATES 0
```

and accepted update jobs.

---

## Arch Linux

The Arch Linux client has been successfully tested with:

```text
LUMS Agent 1.6.0
pacman
systemd
systemd timer
HTTPS
Bearer authentication
Update jobs
```

Example:

```text
HOST archlinux
IP xxx.xxx.xxx.xxx

OS Linux
ARCH x86_64
KERNEL 7.2.6-arch2-1

PACKAGES 190
UPDATES 0
```

The Arch client successfully reported to the LUMS server.

An `UPDATE_SYSTEM` job was also successfully executed.

This verified the complete path:

```text
Arch Linux
    |
    v
LUMS Agent
    |
    v
HTTPS
    |
    v
LUMS API
    |
    v
SQLite
    |
    v
Web UI
```

and the reverse execution path:

```text
Web UI
    |
    v
Update Job
    |
    v
LUMS API
    |
    v
Arch Agent
    |
    v
pacman
    |
    v
Result
```

---

# 10. Repository Structure

The repository currently contains the main application components:

```text
LUMS/
├── agent/
│   ├── agent.py
│   ├── package_manager.py
│   ├── watcher.py
│   ├── lums-agent.service
│   ├── lums-agent.timer
│   └── lums-agent.env.example
│
├── server/
│   ├── app.py
│   ├── init_db.py
│   ├── security.py
│   ├── security_migration.py
│   ├── create_admin.py
│   ├── templates/
│   ├── static/
│   └── requirements.txt
│
├── Dockerfile
├── docker-entrypoint.sh
├── README.md
└── ...
```

The structure can change during development.

---

# 11. Server Requirements

Recommended server requirements:

* 64-bit Linux
* At least 2 CPU cores
* At least 4 GB RAM
* Sufficient disk space
* Docker Engine
* Nginx
* OpenSSL
* Git
* UFW or another firewall

For laboratory environments, the current LUMS installation works comfortably on a small virtual machine.

---

# 12. Ubuntu Server Installation

Ubuntu Server 26.04 LTS is the reference server platform.

Start with:

```bash
sudo apt update
sudo apt upgrade -y
```

Install required packages:

```bash
sudo apt install -y \
  ca-certificates \
  curl \
  git \
  openssl \
  nginx \
  ufw
```

Verify:

```bash
lsb_release -a
uname -a
```

---

# 13. Debian 13 Server Installation

Debian 13 Trixie has also been successfully tested as a LUMS server platform.

Update the system:

```bash
sudo apt update
sudo apt upgrade -y
```

Install:

```bash
sudo apt install -y \
  ca-certificates \
  curl \
  git \
  openssl \
  nginx \
  ufw
```

Check:

```bash
cat /etc/os-release
uname -a
```

---

# 14. Docker Installation

Docker must be installed before building the LUMS container.

After installation:

```bash
sudo systemctl enable --now docker
```

Check:

```bash
sudo systemctl status docker --no-pager
```

Verify:

```bash
sudo docker version
sudo docker info
```

---

# 15. Clone the Repository

Clone the project:

```bash
cd /opt

sudo git clone \
  https://github.com/NovaForgeCtrl/LUMS.git \
  lums-public
```

Set ownership:

```bash
sudo chown -R "$USER":"$USER" /opt/lums-public
```

Enter the repository:

```bash
cd /opt/lums-public
```

Verify:

```bash
git status
```

---

# 16. Update an Existing Installation

For an existing installation:

```bash
cd /opt/lums-public

git fetch origin
git status -sb
```

Update only when the working tree is clean:

```bash
git pull --ff-only origin main
```

Verify:

```bash
git status -sb
```

Check the latest commits:

```bash
git log --oneline --decorate -5
```

Check for whitespace errors:

```bash
git diff --check
```

---

# 17. Verify Repository Synchronization

To verify that the local repository matches GitHub:

```bash
cd /opt/lums-public

git fetch origin

echo "=== STATUS ==="
git status -sb

echo
echo "=== LOCAL HEAD ==="
git rev-parse HEAD

echo
echo "=== GITHUB origin/main ==="
git rev-parse origin/main

echo
echo "=== DIFFERENCE ==="
git log --oneline --left-right HEAD...origin/main
```

If both hashes are identical and the final command produces no output, the local repository and `origin/main` are synchronized.

---

# 18. Docker Image

Build the LUMS image:

```bash
cd /opt/lums-public

sudo docker build -t lums:latest .
```

Check:

```bash
sudo docker image ls lums
```

Inspect the configured user:

```bash
sudo docker image inspect \
  lums:latest \
  --format 'User={{.Config.User}}'
```

The image is configured to run as the non-root user:

```text
lums
```

---

# 19. Persistent Database Volume

Create the database volume:

```bash
sudo docker volume create lums-data
```

Check:

```bash
sudo docker volume ls
```

Inspect:

```bash
sudo docker volume inspect lums-data
```

The database volume must survive container recreation.

Removing the container is therefore different from removing the data.

```text
Container
    |
    +-- disposable

lums-data
    |
    +-- persistent
```

Do not remove `lums-data` during ordinary troubleshooting.

---

# 20. LUMS Configuration

Create the configuration directory:

```bash
sudo install -d \
  -o root \
  -g root \
  -m 750 \
  /etc/lums/docker
```

Create the environment file:

```bash
sudo tee /etc/lums/docker/lums.env > /dev/null <<'EOF'
FLASK_ENV=production
LUMS_DB_PATH=/var/lib/lums/lums.db
EOF
```

Secure it:

```bash
sudo chown root:root /etc/lums/docker/lums.env
sudo chmod 600 /etc/lums/docker/lums.env
```

Verify:

```bash
sudo stat \
  -c '%U:%G %a %n' \
  /etc/lums/docker/lums.env
```

---

# 21. Application Secret

Create the secret directory:

```bash
sudo install -d \
  -o root \
  -g root \
  -m 700 \
  /etc/lums/secrets
```

Generate the secret:

```bash
sudo openssl rand -base64 48 | \
  sudo tee /etc/lums/secrets/lums_secret > /dev/null
```

The secret must never be committed to Git.

Set permissions:

```bash
sudo chmod 640 /etc/lums/secrets/lums_secret
```

The container receives the secret through a read-only mount:

```text
/run/secrets/lums_secret
```

The secret itself should never be printed into the terminal output or documentation.

---

# 22. Database Initialization

The Docker image contains the database initialization logic.

The normal startup path is:

```text
docker-entrypoint.sh
        |
        v
init_db.py
        |
        v
Gunicorn
```

The database is stored under:

```text
/var/lib/lums/lums.db
```

inside the persistent Docker volume.

---

# 23. Security Migration

Security migrations must not accidentally execute through the normal container entrypoint.

For direct execution, override the entrypoint.

Example:

```bash
sudo docker run --rm -it \
  --entrypoint python3 \
  --env-file /etc/lums/docker/lums.env \
  -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
  -v lums-data:/var/lib/lums \
  lums:latest \
  /app/server/security_migration.py \
  --admin-username admin
```

The important point is:

```text
--entrypoint python3
```

Without the entrypoint override, Docker executes the normal application startup path.

---

# 24. Admin Account

The LUMS administration account is stored in the application database.

Passwords are not stored as plaintext.

LUMS uses Argon2-based password hashing.

Administrative authentication should therefore use:

* strong password
* HTTPS
* protected secret
* controlled administrator access

Do not place administrative passwords into:

* Git
* Markdown documentation
* shell history
* screenshots
* public issue reports

---

# 25. Docker Container

The current container is intended to run with a hardened configuration.

Example architecture:

```text
Docker container
├── non-root user
├── read-only root filesystem
├── dropped capabilities
├── /tmp tmpfs
├── read-only secret
└── persistent application volume
```

The application data volume is:

```text
lums-data
```

The application secret is mounted read-only.

The container should not require privileged mode.

---

# 26. Container Hardening

The hardened deployment uses:

```text
--read-only
--cap-drop=ALL
--tmpfs /tmp
```

The application secret is mounted read-only.

The network-facing host port is bound to localhost:

```text
127.0.0.1:5050
```

This means the LUMS application itself is not directly reachable from other hosts.

External access occurs through Nginx.

---

# 27. Start the Container

The exact runtime configuration should reflect the current Dockerfile and deployment configuration.

The resulting container architecture is:

```text
Host
 |
 +-- 127.0.0.1:5050
 |
 +-- Docker
      |
      +-- lums
           |
           +-- :5000
           +-- /var/lib/lums
           +-- /run/secrets/lums_secret
```

Check the container:

```bash
sudo docker ps
```

Inspect:

```bash
sudo docker inspect lums
```

Check logs:

```bash
sudo docker logs lums
```

Follow logs:

```bash
sudo docker logs -f lums
```

---

# 28. Container Restart

Restart:

```bash
sudo docker restart lums
```

Wait:

```bash
sleep 5
```

Check:

```bash
sudo docker ps
```

Logs:

```bash
sudo docker logs --tail 100 lums
```

A successful startup should result in Gunicorn workers being started.

---

# 29. Nginx Configuration

Nginx provides the external HTTPS endpoint.

The basic flow is:

```text
HTTPS :443
    |
    v
Nginx
    |
    v
http://127.0.0.1:5050
```

The LUMS container must therefore be running before Nginx can successfully proxy requests.

---

# 30. TLS Certificate

For laboratory use, a self-signed certificate can be created.

Create the directory:

```bash
sudo install -d \
  -o root \
  -g root \
  -m 700 \
  /etc/lums/tls
```

Generate a private key:

```bash
sudo openssl genrsa \
  -out /etc/lums/tls/lums.key \
  4096
```

Generate a certificate:

```bash
sudo openssl req \
  -x509 \
  -new \
  -nodes \
  -key /etc/lums/tls/lums.key \
  -sha256 \
  -days 825 \
  -out /etc/lums/tls/lums.crt
```

Secure the key:

```bash
sudo chmod 600 /etc/lums/tls/lums.key
```

The certificate must be trusted by clients if TLS verification is enabled.

---

# 31. Nginx Verification

Test the configuration:

```bash
sudo nginx -t
```

Reload:

```bash
sudo systemctl reload nginx
```

Check:

```bash
sudo systemctl status nginx --no-pager
```

---

# 32. Firewall

The firewall should expose only the required services.

Typical LUMS server access:

```text
22/tcp
443/tcp
```

SSH:

```bash
sudo ufw allow ssh
```

HTTPS:

```bash
sudo ufw allow 443/tcp
```

Enable:

```bash
sudo ufw enable
```

Check:

```bash
sudo ufw status verbose
```

The Docker application port:

```text
5050
```

should remain bound to localhost.

It should not be exposed directly to the LAN.

---

# 33. Client Installation

The client agent is installed under:

```text
/opt/lums-agent/
```

Create the directory:

```bash
sudo install -d \
  -o root \
  -g root \
  -m 755 \
  /opt/lums-agent
```

The client requires:

```text
agent.py
watcher.py
lums-ca.crt
```

where applicable.

---

# 34. Client Configuration

Create:

```text
/etc/default/lums-agent
```

Example:

```text
LUMS_BASE="https://192.168.2.141"
LUMS_TOKEN="CLIENT_TOKEN"
LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt"
```

The actual server address must match the LUMS deployment.

The client token is unique to each client.

Do not copy one client's token to another client.

---

# 35. Client TLS Certificate

If the server uses a self-signed CA/certificate, the client must explicitly trust the certificate.

Example:

```text
/opt/lums-agent/lums-ca.crt
```

Verify:

```bash
sudo ls -l /opt/lums-agent/lums-ca.crt
```

The agent uses:

```text
LUMS_CA_FILE
```

to perform TLS verification.

Avoid disabling TLS verification merely to work around certificate problems.

---

# 36. Client Agent Service

The systemd service is a oneshot service.

Example:

```ini
[Unit]
Description=LUMS Linux Update Management Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/lums-agent/agent.py
EnvironmentFile=-/etc/default/lums-agent

[Install]
WantedBy=multi-user.target
```

The service runs once and exits.

Therefore:

```text
inactive (dead)
```

after a successful execution is expected.

A timer is responsible for running it again.

---

# 37. Client Agent Timer

The timer periodically executes the agent.

Current configuration:

```ini
[Unit]
Description=Run LUMS Linux Update Management Agent periodically
After=network-online.target
Wants=network-online.target

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true
Unit=lums-agent.service

[Install]
WantedBy=timers.target
```

Enable:

```bash
sudo systemctl enable --now lums-agent.timer
```

Check:

```bash
systemctl status lums-agent.timer
```

List timers:

```bash
systemctl list-timers --all | grep lums
```

---

# 38. Manual Agent Test

Run:

```bash
sudo systemctl start lums-agent.service
```

Check:

```bash
sudo journalctl \
  -u lums-agent.service \
  -n 100 \
  --no-pager
```

A successful report contains information similar to:

```text
AGENT 1.6.0
HOST <hostname>
IP <address>
OS Linux
ARCH x86_64
KERNEL <kernel>

PACKAGES <count>
UPDATES <count>

LUMS CHANNEL
REPORT Sending system report...

✓ REPORT ACCEPTED
✓ CLIENT AUTHENTICATED
```

---

# 39. Agent Syntax Check

The repository agent can be checked without executing it:

```bash
python3 -m py_compile agent/agent.py
```

For environments where Python cannot write `__pycache__`, use an AST parse:

```bash
python3 - <<'PY'
import ast

with open("/opt/lums-agent/agent.py", "r", encoding="utf-8") as f:
    ast.parse(f.read())

print("SYNTAX OK")
PY
```

---

# 40. Agent Version

The current agent version is:

```text
1.6.0
```

Check:

```bash
grep -n 'AGENT_VERSION' \
  /opt/lums-agent/agent.py
```

Repository:

```bash
grep -n 'AGENT_VERSION' \
  /opt/lums-public/agent/agent.py
```

---

# 41. Verify Client File Integrity

The deployed client agent can be compared with the repository version.

Calculate the client hash:

```bash
sha256sum /opt/lums-agent/agent.py
```

Calculate the repository hash:

```bash
sha256sum /opt/lums-public/agent/agent.py
```

Identical SHA-256 hashes indicate byte-for-byte identical files.

This is useful after manually deploying an agent to a client.

---

# 42. Client Token Authentication

Each LUMS client has its own authentication token.

The token is sent as a Bearer token.

Conceptually:

```text
Authorization:
Bearer <CLIENT_TOKEN>
```

The server verifies the token against the registered client.

Each client should therefore have a unique credential.

If a client token is suspected to be compromised, rotate the token instead of reusing it.

---

# 43. Client Reporting

The agent periodically reports:

* Hostname
* IP address
* Operating system
* Architecture
* Kernel
* Installed package count
* Available update count
* Agent version
* Idle state
* Idle source
* Idle support

The server stores the received information.

The Web UI uses this data to display the current client state.

---

# 44. Idle Detection

The current idle detection implementation does not use:

```text
w -h
```

The old `w`-based implementation has been replaced.

The current implementation uses:

```text
systemd-logind
```

through:

```text
loginctl
```

This provides more reliable information about actual user sessions.

---

# 45. loginctl Idle Detection

The watcher queries:

```bash
loginctl list-sessions --no-legend --no-pager
```

and then examines individual sessions using:

```bash
loginctl show-session <ID>
```

Relevant properties include:

```text
Class
Type
TTY
State
IdleHint
IdleSinceHintMonotonic
```

Only relevant user sessions are considered.

System sessions are ignored.

---

# 46. Active Session Behavior

If a relevant session reports:

```text
IdleHint=no
```

the system is considered active.

Example:

```text
idle=false
idle_seconds=0
idle_supported=true
idle_source=loginctl
```

This prevents update execution while the user is actively using the system.

---

# 47. Idle Session Behavior

For an idle session, LUMS uses:

```text
IdleSinceHintMonotonic
```

to calculate how long the session has been idle.

The configured threshold is:

```text
300 seconds
```

The effective idle state is determined using the relevant session with the shortest idle duration.

---

# 48. Idle Detection Failure

If the idle state cannot be determined reliably, the safe behavior is:

```text
do not automatically execute the update
```

The system must not interpret an error as:

```text
user is idle
```

This avoids executing potentially disruptive maintenance while the user's state is unknown.

---

# 49. Update Jobs

LUMS supports several job actions.

Current actions include:

```text
UPDATE_SYSTEM
UPDATE_PACKAGE
INSTALL_PACKAGE
REMOVE_PACKAGE
```

---

# 50. UPDATE_SYSTEM

`UPDATE_SYSTEM` performs a complete system update through the detected native package manager.

On Debian/Ubuntu:

```text
apt-get upgrade -y
```

On Arch Linux:

```text
pacman -Syu --noconfirm
```

The LUMS agent does not hard-code one package manager into the job logic.

Instead:

```text
UPDATE_SYSTEM
      |
      v
PACKAGE_MANAGER.update_system()
      |
      +--> APT
      |
      +--> pacman
```

---

# 51. UPDATE_PACKAGE

`UPDATE_PACKAGE` updates a specific package.

The operation is delegated to the package-manager abstraction.

APT:

```text
apt-get install --only-upgrade -y <package>
```

pacman:

```text
pacman -S --noconfirm <package>
```

---

# 52. INSTALL_PACKAGE

`INSTALL_PACKAGE` installs a package.

APT:

```text
apt-get install -y <package>
```

pacman:

```text
pacman -S --noconfirm <package>
```

---

# 53. REMOVE_PACKAGE

`REMOVE_PACKAGE` removes a package.

APT:

```text
apt-get remove -y <package>
```

pacman:

```text
pacman -R --noconfirm <package>
```

---

# 54. Job Lifecycle

A normal job follows:

```text
pending
   |
   v
running
   |
   v
success
```

Failure:

```text
pending
   |
   v
running
   |
   v
failed
```

Partial execution:

```text
pending
   |
   v
running
   |
   v
partial
```

Interrupted execution:

```text
running
   |
   v
abandoned
```

The state is stored centrally.

---

# 55. Job Claiming

A job must be claimed before execution.

This prevents multiple clients from executing the same job simultaneously.

Conceptually:

```text
pending
   |
   | claim
   v
running
```

Only after successful claiming may the client execute the operation.

---

# 56. Interrupted Jobs

If a client disappears while a job is running, the server can identify the interrupted state.

Such jobs can be recovered.

The purpose is to avoid leaving the management database permanently stuck in:

```text
running
```

when the client has already stopped processing the job.

---

# 57. Web Interface

The LUMS Web UI provides an overview of connected clients.

Client information includes:

```text
Hostname
IP address
Online state
Idle state
Update state
Agent version
Last report
```

Example:

```text
archlinux
xxx.xxx.xxx.xxx
online
Idle 05:00 / 05:00
Keine
1.6.0
23.09.2026 22:09
```

---

# 58. Available Updates

The Web UI provides a list of available package updates.

The user can select individual updates.

Conceptually:

```text
Verfügbare Updates

☑ package-a
☑ package-b
☑ package-c

[Ausgewählte Updates installieren]
```

Selected packages create individual update jobs.

---

# 59. System Maintenance

The Web UI also provides complete system maintenance.

Example:

```text
Systemwartung

[System vollständig aktualisieren]
```

The button creates:

```text
UPDATE_SYSTEM
```

The server then assigns the job to the appropriate client.

---

# 60. Client Status

The UI can display:

```text
online
offline
idle
active
```

The displayed idle state originates from the client-side idle detection.

The current idle source is:

```text
loginctl
```

when systemd-logind is available and supported.

---

# 61. Audit Logging

Important actions are recorded in the audit log.

The purpose of audit logging is to provide traceability.

Examples include:

* Authentication events
* Administrative actions
* Client operations
* Update job creation
* Job execution
* Security-related actions

The audit log is stored in the LUMS database.

---

# 62. Security Architecture

The current security model includes multiple layers.

```text
Internet / LAN
      |
      v
    Nginx
      |
      | HTTPS
      v
Docker
      |
      | non-root
      | read-only rootfs
      | dropped capabilities
      v
Gunicorn
      |
      v
Flask
      |
      +--> Authentication
      +--> Authorization
      +--> Token verification
      +--> Audit logging
      |
      v
SQLite
```

---

# 63. Password Security

Administrator passwords are protected using Argon2.

Passwords must never be stored as plaintext.

The LUMS application uses password hashing and verification through the security module.

The security implementation also supports password rehashing when required by the configured password policy.

---

# 64. Client Authentication

Client requests use Bearer authentication.

A client therefore requires:

```text
LUMS_BASE
LUMS_TOKEN
```

and, when using a private/self-signed CA:

```text
LUMS_CA_FILE
```

Example:

```text
LUMS_BASE="https://192.168.2.141"
LUMS_TOKEN="..."
LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt"
```

---

# 65. Secrets

Secrets must be kept outside the Git repository.

Do not commit:

```text
LUMS_TOKEN
LUMS_SECRET_KEY
lums_secret
administrator passwords
private TLS keys
```

Recommended locations:

```text
/etc/lums/secrets/
/etc/default/lums-agent
```

depending on the deployment component.

---

# 66. Docker Security

The current container deployment uses several hardening mechanisms.

### Non-root execution

The application runs as:

```text
lums
```

rather than root.

### Read-only root filesystem

The container root filesystem is read-only.

### Dropped capabilities

The container starts with:

```text
cap-drop=ALL
```

### Temporary filesystem

`/tmp` is provided through tmpfs.

### Read-only secret

The application secret is mounted read-only.

### Localhost binding

The application port is bound to:

```text
127.0.0.1:5050
```

rather than:

```text
0.0.0.0:5050
```

---

# 67. Backups

The SQLite database is persistent data and must be included in the backup strategy.

Before backup operations, identify the Docker volume:

```bash
sudo docker volume inspect lums-data
```

The backup strategy should cover:

```text
SQLite database
LUMS configuration
TLS certificates
LUMS secrets
```

Secrets should be protected separately from normal application backups.

A backup is only useful if it can also be restored.

---

# 68. Upgrade Procedure

Before upgrading LUMS:

```bash
cd /opt/lums-public
```

Check the repository:

```bash
git status -sb
```

Fetch:

```bash
git fetch origin
```

Review:

```bash
git log --oneline --decorate -10
```

Update:

```bash
git pull --ff-only origin main
```

Check:

```bash
git diff --check
```

Build:

```bash
sudo docker build -t lums:latest .
```

Then recreate/restart the container using the current deployment configuration.

---

# 69. Production Restart

A normal restart can be performed with:

```bash
sudo docker restart lums
```

Wait:

```bash
sleep 5
```

Check:

```bash
sudo docker ps
```

Check logs:

```bash
sudo docker logs --tail 100 lums
```

Check Nginx:

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
```

---

# 70. Client Upgrade

Update the client agent from the repository:

```bash
sudo cp \
  /opt/lums-public/agent/agent.py \
  /opt/lums-agent/agent.py
```

Update the watcher if required:

```bash
sudo cp \
  /opt/lums-public/agent/watcher.py \
  /opt/lums-agent/watcher.py
```

Verify ownership:

```bash
sudo chown root:root \
  /opt/lums-agent/agent.py \
  /opt/lums-agent/watcher.py
```

Check syntax:

```bash
python3 -m py_compile /opt/lums-agent/agent.py
```

Restart the timer if required:

```bash
sudo systemctl daemon-reload
sudo systemctl restart lums-agent.timer
```

---

# 71. Troubleshooting Strategy

LUMS consists of several independent layers.

When something fails, identify the layer first.

```text
Browser
   |
Nginx
   |
Docker
   |
Gunicorn
   |
Flask
   |
SQLite
   |
HTTPS
   |
Agent
   |
Watcher
   |
Package Manager
   |
Operating System
```

Do not immediately reinstall the complete system.

---

# 72. Check the Server

```bash
sudo docker ps
```

Check:

```bash
sudo docker logs --tail 100 lums
```

Check Nginx:

```bash
sudo systemctl status nginx --no-pager
```

Check configuration:

```bash
sudo nginx -t
```

Check HTTPS:

```bash
curl -kI https://127.0.0.1/
```

---

# 73. Check the Client

```bash
sudo systemctl status lums-agent.timer
```

Run manually:

```bash
sudo systemctl start lums-agent.service
```

Read logs:

```bash
sudo journalctl \
  -u lums-agent.service \
  -n 100 \
  --no-pager
```

---

# 74. Check the Watcher

Check its systemd unit if installed separately:

```bash
sudo systemctl status lums-watcher.service --no-pager
```

Read:

```bash
sudo journalctl \
  -u lums-watcher.service \
  -n 100 \
  --no-pager
```

If the watcher is not running, the client may still report successfully while update jobs remain pending.

---

# 75. Check Package Manager

Debian/Ubuntu:

```bash
command -v apt
command -v apt-get
command -v dpkg-query
```

Arch:

```bash
command -v pacman
```

Check updates manually.

APT:

```bash
apt list --upgradable
```

Arch:

```bash
pacman -Qu
```

---

# 76. Check Package Manager Detection

The agent should detect:

```text
apt
```

or:

```text
pacman
```

If neither exists, the agent reports an unsupported platform.

Check manually:

```bash
command -v apt
command -v pacman
```

---

# 77. Check TLS

Verify the configured CA:

```bash
sudo ls -l \
  /opt/lums-agent/lums-ca.crt
```

Check the environment:

```bash
sudo grep -E \
  '^LUMS_(BASE|CA_FILE)=' \
  /etc/default/lums-agent
```

Do not print the token.

Use:

```bash
sudo grep '^LUMS_TOKEN=' /etc/default/lums-agent \
  | sed 's/=.*/=<redacted>/'
```

---

# 78. Check Authentication

A successful client report should contain:

```text
✓ REPORT ACCEPTED
✓ CLIENT AUTHENTICATED
```

If authentication fails, verify:

1. Client token
2. Client ID
3. Server address
4. TLS certificate
5. Bearer header
6. Server logs
7. Database client record

Do not immediately recreate the client.

---

# 79. Check Client Registration

The client must exist in the LUMS database.

The server-side UI should show:

```text
Hostname
IP
Online state
Agent version
Last report
```

If the client is not shown, investigate reporting before investigating update execution.

---

# 80. Reporting vs. Execution

A successful report proves:

```text
Client
   |
   v
HTTPS
   |
   v
LUMS API
   |
   v
Database
```

It does not prove:

```text
Watcher
   |
   v
Job execution
   |
   v
Package manager
```

These are separate test paths.

---

# 81. Recommended Test Sequence

When testing a new client, use this order:

```text
1. Network
2. HTTPS
3. TLS verification
4. Authentication
5. Reporting
6. Client registration
7. Idle detection
8. Job creation
9. Job claiming
10. Job execution
11. Result reporting
12. UI verification
```

This makes failures easier to isolate.

---

# 82. Debian Test

Verify:

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

Create a controlled update job through the LUMS UI.

Verify:

```text
pending
    |
    v
running
    |
    v
success
```

---

# 83. Arch Test

Verify:

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

Check:

```bash
pacman -Qu
```

Create a controlled job through LUMS.

Verify the job transitions to:

```text
success
```

The Arch `UPDATE_SYSTEM` path has already been successfully verified with the current implementation.

---

# 84. Systemd Timer Verification

The service itself is a oneshot service.

Therefore:

```text
lums-agent.service
```

may show:

```text
inactive (dead)
```

after completion.

This is expected.

The timer should instead show:

```text
active (waiting)
```

Check:

```bash
systemctl status lums-agent.timer
```

List the next execution:

```bash
systemctl list-timers --all | grep lums
```

---

# 85. Common Misinterpretation

This:

```text
lums-agent.service
inactive (dead)
```

does not necessarily mean the agent is broken.

For a successful oneshot service:

```text
start
  |
  v
execute
  |
  v
exit 0
  |
  v
inactive
```

The timer starts it again later.

---

# 86. Agent Logs

Use:

```bash
sudo journalctl \
  -u lums-agent.service \
  -n 100 \
  --no-pager
```

Follow:

```bash
sudo journalctl \
  -u lums-agent.service \
  -f
```

The logs should show the agent version and reporting process.

---

# 87. Database Inspection

The SQLite database is persistent application data.

Never modify it directly unless the procedure explicitly requires it.

For diagnostic inspection, use the application tools or a read-only SQLite session where possible.

The database contains information such as:

```text
users
clients
audit_log
update_jobs
```

The exact schema can change during development.

---

# 88. Safe Docker Troubleshooting

First:

```bash
sudo docker ps
```

Then:

```bash
sudo docker logs --tail 100 lums
```

Then:

```bash
sudo docker inspect lums
```

Then verify the volume:

```bash
sudo docker volume inspect lums-data
```

Only after these checks should container recreation be considered.

Do not delete:

```text
lums-data
```

unless data destruction is explicitly intended.

---

# 89. Full Container Recreation

If the application container itself must be recreated:

```text
Stop/remove container
        |
        v
Keep lums-data
        |
        v
Build image
        |
        v
Create new container
        |
        v
Start
```

The persistent volume remains separate from the container.

This is one of the main advantages of the current Docker architecture.

---

# 90. Complete Reset

A complete reset is different from a normal reinstall.

A complete reset may remove:

```text
LUMS container
Docker image
Docker volume
configuration
TLS material
secrets
repository
```

This destroys persistent application state.

Do not perform a complete reset as a first troubleshooting step.

---

# 91. Development Workflow

Changes should be made in the repository:

```text
/opt/lums-public
```

After changes:

```bash
git status
```

Review:

```bash
git diff
```

Check:

```bash
git diff --check
```

Run syntax checks.

Then rebuild the application image if server-side files changed:

```bash
sudo docker build -t lums:latest .
```

Deploy the updated image.

---

# 92. Git Workflow

Before committing:

```bash
git status
git diff
git diff --check
```

Set the project Git identity:

```bash
git config user.name "NovaForgeCtrl"
git config user.email "xxxxxx.noreply.github.com"
```

Commit:

```bash
git add .
git commit -m "Describe the change"
```

Push:

```bash
git push origin main
```

Verify:

```bash
git fetch origin
git status -sb
```

---

# 93. Recommended Commit Principle

Commits should describe one logical change.

Examples:

```text
Add Arch package support
Improve idle detection
Harden Docker deployment
Fix update job execution
Add Debian 13 documentation
```

Avoid large unrelated commits where possible.

---

# 94. Release Principle

LUMS is not considered ready for a final release merely because the application starts.

Before a release, the following areas should be tested:

```text
Server installation
Client installation
Authentication
Authorization
TLS
Reporting
Job creation
Job claiming
Job execution
Package installation
Package removal
Package updates
System updates
Idle detection
Failure handling
Recovery
Audit logging
Docker hardening
Backup
Restore
Debian
Ubuntu
Arch Linux
```

The documentation should reflect the actual tested state.

---

# 95. Security Audit

Security work should be treated as a separate verification phase.

Relevant areas include:

* Authentication
* Authorization
* Session handling
* Password hashing
* Token storage
* Token rotation
* TLS
* HTTP security headers
* API authentication
* Docker isolation
* File permissions
* Secret handling
* SQLite access
* Audit logging
* Input validation
* Job authorization
* Job execution
* Error handling
* Logging
* Backup protection

Documentation should be updated after security changes have been tested rather than documenting unverified assumptions as completed functionality.

---

# 96. Security Principles

LUMS follows these general principles:

> **Least privilege**

Components should receive only the permissions they require.

> **Defense in depth**

Security should not depend on one mechanism.

> **Fail safely**

An unknown state should not automatically result in an update being executed.

> **Separate management and execution**

Reporting, job management and execution are separate layers.

> **Do not expose unnecessary services**

The application is bound to localhost behind Nginx.

---

# 97. Current Reference Deployment

A current reference deployment can be summarized as:

```text
SERVER
Ubuntu Server 26.04 LTS
Docker
Nginx
HTTPS
Gunicorn
Flask
SQLite
```

with:

```text
CLIENT 1
Debian 13
APT
LUMS Agent 1.6.0
systemd timer
```

and:

```text
CLIENT 2
Arch Linux
pacman
LUMS Agent 1.6.0
systemd timer
```

---

# 98. Reference Network

Example laboratory network:

```text
LUMS Server
192.168.2.141

Debian client / LUMS server host
192.168.2.141

Arch client
xxx.xxx.xxx.xxx
```

The actual IP addresses are environment-specific.

Do not copy laboratory addresses blindly into another environment.

---

# 99. End-to-End Communication

The complete communication path is:

```text
                    LUMS SERVER

Browser
   |
   | HTTPS
   v
Nginx
   |
   | localhost
   v
Docker
   |
   v
Gunicorn
   |
   v
Flask
   |
   v
SQLite
   ^
   |
   | HTTPS / Bearer
   |
+--+----------------------+
|                         |
|                         |
v                         v

Debian 13             Arch Linux
LUMS Agent             LUMS Agent
APT                    pacman
Watcher                Watcher
```

---

# 100. Successful End-to-End Test

A complete successful update cycle is:

```text
Client starts
    |
    v
Agent collects system information
    |
    v
Agent detects package manager
    |
    v
Agent reports to LUMS
    |
    v
Server authenticates client
    |
    v
Server stores report
    |
    v
Administrator creates update job
    |
    v
Job becomes pending
    |
    v
Client watcher checks job
    |
    v
Idle state is checked
    |
    v
Job is claimed
    |
    v
Package manager executes
    |
    v
Result is generated
    |
    v
Result is reported
    |
    v
Server stores result
    |
    v
Web UI displays final state
```

---

# 101. Verification Checklist

## Server

```text
[ ] Operating system installed
[ ] Docker installed
[ ] Docker enabled
[ ] Repository cloned
[ ] Image built
[ ] Persistent volume created
[ ] Secret created
[ ] Configuration created
[ ] Container running
[ ] Gunicorn running
[ ] Nginx running
[ ] TLS working
[ ] Firewall configured
```

## Client

```text
[ ] Supported Linux distribution
[ ] Supported package manager
[ ] Agent installed
[ ] Watcher installed
[ ] CA certificate installed
[ ] Client token configured
[ ] systemd service installed
[ ] systemd timer installed
[ ] Agent report successful
[ ] Client visible in UI
[ ] Idle detection working
```

## Update execution

```text
[ ] UPDATE_PACKAGE tested
[ ] INSTALL_PACKAGE tested
[ ] REMOVE_PACKAGE tested
[ ] UPDATE_SYSTEM tested
[ ] Job claiming tested
[ ] Successful result tested
[ ] Failed result tested
[ ] Interrupted job handling tested
[ ] Audit log verified
```

---

# 102. Troubleshooting Checklist

When something does not work, check in this order:

```text
1. Network connectivity
2. DNS / IP configuration
3. HTTPS
4. TLS certificate
5. Docker container
6. Nginx
7. Flask / Gunicorn
8. Authentication
9. Client registration
10. Agent reporting
11. Watcher
12. Idle detection
13. Job state
14. Package manager
15. Operating system
```

Do not skip directly to:

```text
reinstall everything
```

---

# 103. Important Operational Rules

### Never expose secrets

Do not publish:

```text
tokens
passwords
private keys
application secrets
```

### Never delete the database casually

The database lives inside:

```text
lums-data
```

### Do not disable TLS verification as a permanent workaround

Fix the certificate trust problem instead.

### Do not assume a oneshot service is broken

Check the timer.

### Do not assume successful reporting means successful execution

Test the watcher and job pipeline separately.

### Do not use `w -h` for current idle detection

The current implementation uses:

```text
loginctl
systemd-logind
```

### Do not assume APT is the only package manager

The current agent supports:

```text
APT
pacman
```

---

# 104. Current Agent Status

The current LUMS agent version is:

```text
1.6.0
```

The current implementation has been verified on:

```text
Debian 13 Trixie
Arch Linux
```

The Arch deployment has been verified byte-for-byte against the repository agent using SHA-256.

The current architecture therefore uses one common agent implementation with distribution-specific package-manager backends.

---

# 105. Final Architecture Summary

```text
                         +------------------+
                         |      Browser     |
                         +--------+---------+
                                  |
                                HTTPS
                                  |
                         +--------v---------+
                         |      Nginx       |
                         +--------+---------+
                                  |
                           localhost:5050
                                  |
                         +--------v---------+
                         | Docker / LUMS    |
                         |                  |
                         | Gunicorn         |
                         | Flask            |
                         | SQLite           |
                         +--------+---------+
                                  |
                              HTTPS API
                                  |
              +-------------------+-------------------+
              |                                       |
      +-------v--------+                      +-------v--------+
      | Debian 13      |                      | Arch Linux     |
      |                |                      |                |
      | LUMS Agent     |                      | LUMS Agent     |
      | Execution      |                      | Execution      |
      | Watcher        |                      | Watcher        |
      |                |                      |                |
      | APT            |                      | pacman         |
      +----------------+                      +----------------+
```

The architecture is intentionally modular.

The server handles management.

The agent handles reporting.

The watcher handles execution.

The native package manager handles the actual Linux package operation.

This separation allows LUMS to manage different Linux distributions without replacing their native package-management systems.
