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
APT / dpkg
pacman
```

This allows the same LUMS agent architecture to support Debian/Ubuntu systems as well as Arch Linux.

The server does not directly execute package-management commands on clients.

Instead, the architecture separates:

```text
Management
    ↓
Job coordination
    ↓
Client execution
    ↓
Native package manager
```

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
* Token invalidation
* Interrupted-job recovery
* Atomic job claiming
* Idle-aware execution
* Multi-distribution package management
* Login rate limiting
* SQLite foreign-key enforcement
* SQLite WAL mode
* SQLite busy timeout
* Controlled package-update timeout handling

The following client platforms have been tested:

```text
Debian 13 Trixie
Arch Linux
```

The current agent version is:

```text
1.7.0
```

The current Docker deployment uses a hardened container configuration:

```text
non-root user
read-only root filesystem
ALL Linux capabilities dropped
non-privileged container
/tmp through tmpfs
read-only application secret
persistent lums-data volume
localhost-only application binding
```

The current production application binding is:

```text
127.0.0.1:5050 → container:5000
```

External HTTPS access is provided by Nginx.

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
        | APT/dpkg  |      | pacman    |      | supported |
        +-----------+      +-----------+      +-----------+
```

The architecture deliberately separates the management plane from the execution plane.

```text
Management Plane
    |
    +-- Nginx
    +-- HTTPS
    +-- Gunicorn
    +-- Flask
    +-- Authentication
    +-- Authorization
    +-- SQLite
    +-- Job management

Execution Plane
    |
    +-- lums-agent
    +-- Execution Watcher
    +-- package_manager.py
    +-- APT / dpkg
    +-- pacman
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

The production application binding is:

```text
127.0.0.1:5050
```

The container application listens internally on:

```text
5000
```

---

## 4.2 Docker

The LUMS application runs inside a Docker container.

The container:

* runs as a non-root user
* uses a read-only root filesystem
* drops all Linux capabilities
* runs without privileged mode
* uses a temporary filesystem for `/tmp`
* receives the application secret through a read-only secret mount
* stores persistent application data in a Docker volume
* exposes the application only through the localhost-bound host port

The current application image is based on:

```text
python:3.13-slim
```

The current persistent Docker volume is:

```text
lums-data
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

The current production container uses Gunicorn rather than the Flask development server.

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
* Audit logging

The Flask application is located in:

```text
server/app.py
```

Inside the Docker image, the application is located under:

```text
/app
```

---

## 4.5 SQLite

SQLite stores LUMS application data.

The database is stored inside the persistent Docker volume:

```text
lums-data
```

The database path inside the container is:

```text
/var/lib/lums/lums.db
```

The database must therefore not be stored inside the disposable container filesystem.

The current SQLite connection configuration includes:

```text
foreign_keys = ON
busy_timeout = 5000
```

The database is configured for:

```text
WAL
```

journal mode.

This allows the application to handle normal concurrent database access more safely.

---

# 5. Client Architecture

A LUMS client contains two primary execution components:

```text
/opt/lums-agent/
├── agent.py
└── watcher.py
```

The components have different responsibilities.

The systemd units are:

```text
lums-agent.service
lums-agent.timer
lums-execution-watcher.service
lums-execution-watcher.timer
```

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
* Package-manager detection

The agent also provides the package-management abstraction used for update operations.

The current agent version is:

```text
1.7.0
```

---

## 5.2 Execution Watcher

The Execution Watcher is responsible for:

* Checking pending jobs
* Checking idle state
* Claiming jobs
* Executing jobs
* Handling execution results
* Reporting job completion
* Recovering interrupted jobs

The watcher runs independently of the normal reporting process.

The normal execution path is:

```text
lums-execution-watcher.timer
        |
        v
lums-execution-watcher.service
        |
        v
watcher.py
        |
        v
idle detection
        |
        v
job claiming
        |
        v
package manager
        |
        v
result reporting
```

---

# 6. Supported Linux Package Managers

LUMS currently supports:

```text
APT / dpkg
pacman
```

The package manager is detected automatically.

The agent contains separate implementations for the supported package-management systems.

The abstraction is located in:

```text
agent/package_manager.py
```

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

The package-manager abstraction keeps distribution-specific commands out of the general agent execution logic.

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

Package state
    dpkg-query

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

LUMS does not replace the native APT/dpkg package-management system.

---

# 8. pacman Support

Arch Linux uses pacman.

LUMS uses the native pacman interface.

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

Candidate information
    pacman -Si <package>
```

The Arch implementation is handled through the same package-manager abstraction as APT.

---

# 9. Tested Client Platforms

## Debian 13

The Debian 13 client has been successfully tested with:

```text
LUMS Agent 1.7.0
APT / dpkg
systemd
systemd timer
HTTPS
Bearer authentication
Client reporting
Update jobs
Idle detection
```

The current Debian client successfully reports its package inventory and update state to the LUMS server.

A successful report follows:

```text
Debian
    |
    v
lums-agent
    |
    v
HTTPS / Bearer authentication
    |
    v
LUMS API
    |
    v
SQLite
```

---

## Arch Linux

The Arch Linux client has been successfully tested with:

```text
LUMS Agent 1.7.0
pacman
systemd
systemd timer
HTTPS
Bearer authentication
Client reporting
Update jobs
Idle detection
```

The Arch client successfully reports to the LUMS server and has successfully executed an `UPDATE_SYSTEM` job through the current package-manager abstraction.

The execution path is:

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

The Arch client and repository agent implementation have also been verified byte-for-byte using SHA-256.

---

# 10. Repository Structure

The repository contains the main application components:

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

The repository also contains migration and supporting files as the project evolves.

The exact repository structure may change during development.

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

For laboratory environments, the current LUMS installation works on a small virtual machine.

The actual resource requirements depend on:

* number of clients
* reporting frequency
* update-job frequency
* database size
* log volume

---

# 12. Ubuntu Server Installation

Ubuntu Server 26.04 LTS is the current reference server platform.

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

Debian 13 Trixie has also been tested as a LUMS server platform.

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

The Docker installation method may vary by distribution.

Use the official Docker documentation for the distribution-specific installation procedure.

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

Do not overwrite local changes blindly.

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

The production deployment additionally verifies the runtime hardening of the created container.

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

The current production deployment keeps the application secret separate from the container image and ordinary environment configuration.

Create the secret directory:

```bash
sudo install -d \
  -o root \
  -g root \
  -m 700 \
  /etc/lums/secrets
```

The application secret is stored at:

```text
/etc/lums/secrets/lums_secret
```

The container receives it as:

```text
/run/secrets/lums_secret
```

through a read-only bind mount.

The application is configured to use:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

Do not place the actual secret into:

```text
Git
Markdown documentation
Dockerfile
public configuration files
```

---

# 21. Application Secret

Generate the application secret:

```bash
sudo openssl rand -base64 48 | \
  sudo tee /etc/lums/secrets/lums_secret > /dev/null
```

Secure it:

```bash
sudo chown root:root \
  /etc/lums/secrets/lums_secret

sudo chmod 640 \
  /etc/lums/secrets/lums_secret
```

Verify permissions without printing the secret:

```bash
sudo stat \
  -c '%U:%G %a %n' \
  /etc/lums/secrets/lums_secret
```

The expected deployment uses the secret as a protected file rather than exposing the secret value through ordinary container environment variables.

The container mount is read-only:

```text
/etc/lums/secrets/lums_secret
        |
        | read-only
        v
/run/secrets/lums_secret
```

Never print the contents of the secret into terminal logs or documentation.

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

The current database connection configuration enables:

```text
foreign_keys = ON
busy_timeout = 5000
```

The database uses:

```text
WAL
```

journal mode.

Database initialization and migrations must preserve the existing persistent database.

---

# 23. Security Migrations

Security migrations must not accidentally execute through the normal application entrypoint.

When a migration must be executed directly, override the entrypoint.

Example:

```bash
sudo docker run --rm -it \
  --entrypoint python3 \
  -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
  -v lums-data:/var/lib/lums \
  lums:latest \
  /app/server/security_migration.py
```

The important point is:

```text
--entrypoint python3
```

Without the entrypoint override, Docker executes the normal application startup path.

Before production migrations:

```text
backup
   ↓
migration
   ↓
integrity check
   ↓
application verification
```

Do not run destructive database operations against production without a verified backup.

---

# 24. Admin Account

The LUMS administration account is stored in the application database.

Passwords are not stored as plaintext.

LUMS uses Argon2-based password hashing.

Administrative authentication should therefore use:

* strong password
* HTTPS
* protected application secret
* controlled administrator access
* login rate limiting

The current login rate-limiting implementation progressively limits repeated failed authentication attempts.

Do not place administrative passwords into:

* Git
* Markdown documentation
* shell history
* screenshots
* public issue reports

---

# 25. Docker Container

The current production container runs with a hardened configuration.

The expected runtime properties are:

```text
User:
    lums

Root filesystem:
    read-only

Capabilities:
    ALL dropped

Privileged:
    false

Temporary filesystem:
    /tmp tmpfs

Persistent data:
    lums-data

Secret:
    read-only secret mount

Host binding:
    127.0.0.1:5050
```

The current production container is recreated using:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --tmpfs /tmp:rw,nosuid,nodev,noexec \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -p 127.0.0.1:5050:5000 \
    lums:latest
```

The application container is not intended to be exposed directly to the LAN.

External access is provided through Nginx.

---

# 26. Container Hardening

The hardened deployment uses:

```text
--read-only
--cap-drop=ALL
--tmpfs /tmp:rw,nosuid,nodev,noexec
```

The container does not use privileged mode.

The application secret is mounted read-only.

Persistent data is kept outside the disposable container filesystem.

The network-facing host port is bound to:

```text
127.0.0.1:5050
```

This means the LUMS application itself is only locally reachable through the Docker port mapping.

External HTTPS access is handled by Nginx.

---

# 27. Start the Container

After the image has been built and the persistent volume and secret are available:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --tmpfs /tmp:rw,nosuid,nodev,noexec \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -p 127.0.0.1:5050:5000 \
    lums:latest
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

A successful startup should show the database initialization followed by Gunicorn starting successfully.

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
    |
    v
Docker
    |
    v
Gunicorn :5000
```

The LUMS container must therefore be running before Nginx can successfully proxy requests.

The Flask/Gunicorn application is not intended to be exposed directly on a LAN address.

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
sudo chmod 600 \
  /etc/lums/tls/lums.key
```

The certificate must be trusted by clients if TLS verification is enabled.

Do not disable TLS verification as a permanent workaround for certificate problems.

Fix the trust configuration instead.


# 31. Nginx Reverse Proxy

Create the LUMS Nginx configuration:

```bash
sudo tee /etc/nginx/sites-available/lums >/dev/null <<'EOF'
server {
    listen 80;
    server_name <LUMS_SERVER_HOSTNAME>;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name <LUMS_SERVER_HOSTNAME>;

    ssl_certificate     /etc/lums/tls/lums.crt;
    ssl_certificate_key /etc/lums/tls/lums.key;

    location / {
        proxy_pass http://127.0.0.1:5050;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

Enable the configuration:

```bash
sudo ln -sf \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

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
sudo systemctl is-active nginx
```

---

# 32. HTTPS Verification

Verify the local application first:

```bash
curl -I \
    http://127.0.0.1:5050/
```

Then test HTTPS through Nginx:

```bash
curl -k -I \
    https://<LUMS_SERVER_HOSTNAME>/
```

The `-k` option is only appropriate when using a self-signed certificate that is not yet trusted by the client.

For a trusted certificate, do not use `-k`.

The important architecture is:

```text
Browser
   |
   | HTTPS
   v
Nginx
   |
   | HTTP localhost
   v
127.0.0.1:5050
```

There is no `/health` endpoint in the current LUMS application.

Therefore:

```bash
curl -k https://<LUMS_SERVER_HOSTNAME>/health
```

returning:

```text
404
```

does not indicate a failed LUMS installation.

Use an actual LUMS endpoint for application verification.

For example:

```bash
curl -k -I \
    https://<LUMS_SERVER_HOSTNAME>/api/clients
```

Authentication may be required depending on the endpoint.

---

# 33. Firewall

If UFW is used, allow SSH:

```bash
sudo ufw allow ssh
```

Allow HTTPS:

```bash
sudo ufw allow 443/tcp
```

If HTTP is required for the configured redirect:

```bash
sudo ufw allow 80/tcp
```

Enable:

```bash
sudo ufw enable
```

Check:

```bash
sudo ufw status verbose
```

Do not expose the Docker application port directly.

The following should remain a localhost-only binding:

```text
127.0.0.1:5050
```

Do not replace it with:

```text
0.0.0.0:5050
```

unless there is a deliberate architectural reason to do so.

---

# 34. LUMS Agent Installation

The LUMS agent is installed on each managed Linux client.

The agent consists of:

```text
agent.py
package_manager.py
watcher.py
```

The current tested agent version is:

```text
1.7.0
```

The agent communicates with the LUMS server over HTTPS.

The client does not need direct access to the Docker container.

Instead:

```text
Client
   |
   | HTTPS :443
   v
Nginx
   |
   v
LUMS API
```

---

# 35. Agent Directory

Create the agent directory:

```bash
sudo install -d \
    -o root \
    -g root \
    -m 755 \
    /opt/lums-agent
```

Copy the agent files into the directory.

For a repository checkout:

```bash
sudo cp \
    agent/agent.py \
    agent/package_manager.py \
    agent/watcher.py \
    /opt/lums-agent/
```

Set ownership:

```bash
sudo chown \
    -R root:root \
    /opt/lums-agent
```

Check:

```bash
sudo ls -la \
    /opt/lums-agent/
```

---

# 36. Agent Version Verification

Verify the installed agent:

```bash
sudo grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/agent.py
```

Expected:

```text
AGENT_VERSION = "1.7.0"
```

Verify the repository copy:

```bash
grep -n \
    'AGENT_VERSION' \
    /opt/lums-public/agent/agent.py
```

Both should report:

```text
1.7.0
```

A mismatch between repository and installed agent should be investigated before continuing.

---

# 37. Agent Configuration

The client configuration is stored in:

```text
/etc/default/lums-agent
```

Create it:

```bash
sudo tee /etc/default/lums-agent >/dev/null <<'EOF'
LUMS_BASE=https://<LUMS_SERVER_HOSTNAME>
LUMS_TOKEN=<CLIENT_TOKEN>
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
EOF
```

The actual token must not be published.

Secure the configuration:

```bash
sudo chown root:root \
    /etc/default/lums-agent

sudo chmod 600 \
    /etc/default/lums-agent
```

Verify the configuration without exposing the token:

```bash
sudo awk -F= '
/^(LUMS_BASE|LUMS_TOKEN|LUMS_CA_FILE)=/ {
    print $1 "=<set>"
}' /etc/default/lums-agent
```

Expected:

```text
LUMS_BASE=<set>
LUMS_TOKEN=<set>
LUMS_CA_FILE=<set>
```

---

# 38. Client Certificate Authority

If LUMS uses a self-signed server certificate, the client must trust the appropriate CA/certificate.

For the current laboratory deployment, the certificate used for LUMS HTTPS is installed on the client as:

```text
/opt/lums-agent/lums-ca.crt
```

Verify:

```bash
sudo test \
    -r /opt/lums-agent/lums-ca.crt \
    && echo "CA certificate present" \
    || echo "CA certificate missing"
```

Do not solve certificate problems by permanently disabling TLS verification.

The correct solution is to fix the trust configuration.

---

# 39. Agent systemd Service

Create:

```bash
sudo tee /etc/systemd/system/lums-agent.service >/dev/null <<'EOF'
[Unit]
Description=LUMS Linux Update Management Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
EnvironmentFile=/etc/default/lums-agent
ExecStart=/usr/bin/python3 /opt/lums-agent/agent.py
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

The agent is normally triggered through its timer.

---

# 40. Agent Timer

Create:

```bash
sudo tee /etc/systemd/system/lums-agent.timer >/dev/null <<'EOF'
[Unit]
Description=LUMS Agent Timer

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
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
sudo systemctl enable --now \
    lums-agent.timer
```

Check:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

List the next execution:

```bash
systemctl list-timers \
    lums-agent.timer
```

---

# 41. Manual Agent Execution

The agent can be executed manually for diagnostics:

```bash
sudo systemctl start \
    lums-agent.service
```

Check:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

View logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "10 minutes ago" \
    --no-pager
```

A successful reporting cycle should contain information similar to:

```text
REPORT ACCEPTED
```

The exact output can change between versions.

---

# 42. Agent Reporting

The normal reporting path is:

```text
lums-agent
    |
    v
HTTPS
    |
    v
LUMS API
    |
    v
client authentication
    |
    v
inventory processing
    |
    v
SQLite
```

The report contains information such as:

* hostname
* operating system
* architecture
* kernel
* agent version
* installed packages
* available updates
* package-manager information

The server stores the current inventory for the client.

---

# 43. Client Authentication

Clients authenticate using individual Bearer tokens.

The request conceptually uses:

```text
Authorization: Bearer <CLIENT_TOKEN>
```

Tokens are not stored as plaintext in the database.

LUMS stores a SHA-256 hexadecimal digest of the client token.

The authentication process therefore looks like:

```text
Client token
     |
     v
SHA-256
     |
     v
Stored digest
     |
     v
Client lookup
     |
     v
Enabled?
     |
     v
Authenticated
```

Disabled clients are rejected.

Revoked tokens are rejected.

---

# 44. Client Registration

A client must first exist in the LUMS server database.

The normal workflow is:

```text
Create client
      |
      v
Generate client token
      |
      v
Install token on client
      |
      v
Configure agent
      |
      v
Run agent
      |
      v
REPORT ACCEPTED
```

The plaintext client token should only be handled when initially provisioning or rotating the client.

Do not store plaintext tokens in documentation.

---

# 45. Client Token Rotation

A client token can be rotated if required.

Rotation creates a new token and invalidates the old token.

The lifecycle is:

```text
Old token
    |
    v
Rotate
    |
    +----> old token invalid
    |
    v
New token
    |
    v
Install on client
    |
    v
Report accepted
```

The plaintext token is returned only during the rotation operation.

Store it securely and update the client configuration immediately.

After rotation:

```bash
sudo systemctl restart \
    lums-agent.timer
```

Then perform a manual report:

```bash
sudo systemctl start \
    lums-agent.service
```

Verify:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "5 minutes ago" \
    --no-pager
```

The old token must no longer authenticate.

---

# 46. Login Rate Limiting

LUMS protects administrator authentication against repeated failed login attempts.

The current progressive lock steps are:

```text
5 failed attempts  → 30 seconds
6 failed attempts  → 60 seconds
7 failed attempts  → 120 seconds
8+ failed attempts → 300 seconds
```

The rate-limit key combines:

```text
normalized username
+
request source
```

A blocked login still returns the generic authentication error.

The application does not disclose whether a username exists.

The rate-limit state is stored in:

```text
login_rate_limits
```

The corresponding migration is:

```text
003-login-rate-limiting
```

---

# 47. Login Rate-Limiting Diagnostics

Inspect the migration state:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "SELECT version, name FROM schema_migrations ORDER BY version;"
```

The current production database contains the login-rate-limiting migration.

Check the table:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    ".schema login_rate_limits"
```

Do not publish complete rate-limit database contents if they contain operational information that should remain private.

---

# 48. Idle Detection

Update execution is idle-aware.

The Execution Watcher checks whether a user is actively using the client before starting an update job.

The current idle detection uses:

```text
loginctl
```

The configured idle threshold is:

```text
300 seconds
```

Conceptually:

```text
User active
    |
    v
Wait
    |
    v
Idle threshold reached
    |
    v
Job may execute
```

This prevents an update job from unexpectedly starting while the system is actively being used.

---

# 49. Idle Detection Verification

Check the relevant systemd/logind state:

```bash
loginctl list-sessions
```

Check the agent/watcher logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

The current implementation reports idle-detection information including:

```text
idle_source=loginctl
idle_supported=True
```

If idle detection is unavailable, the watcher must not silently pretend that a valid idle state was detected.

Investigate the watcher logs instead.

---

# 50. Execution Watcher Installation

Install:

```text
watcher.py
```

into:

```text
/opt/lums-agent/
```

The corresponding systemd service is:

```text
lums-execution-watcher.service
```

The corresponding timer is:

```text
lums-execution-watcher.timer
```

The watcher is intentionally separate from the normal reporting timer.

This separation allows:

```text
Reporting
    |
    +-- inventory
    +-- system information
    +-- available updates

Execution
    |
    +-- idle detection
    +-- job claiming
    +-- update execution
    +-- recovery
```

---

# 51. Execution Watcher Service

Create:

```bash
sudo tee /etc/systemd/system/lums-execution-watcher.service >/dev/null <<'EOF'
[Unit]
Description=LUMS Update Execution Watcher
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
EnvironmentFile=/etc/default/lums-agent
ExecStart=/usr/bin/python3 /opt/lums-agent/watcher.py
User=root
Group=root
EOF
```

Reload:

```bash
sudo systemctl daemon-reload
```

---

# 52. Execution Watcher Timer

Create:

```bash
sudo tee /etc/systemd/system/lums-execution-watcher.timer >/dev/null <<'EOF'
[Unit]
Description=LUMS Update Execution Watcher Timer

[Timer]
OnBootSec=3min
OnUnitActiveSec=1min
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
sudo systemctl enable --now \
    lums-execution-watcher.timer
```

Check:

```bash
sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager
```

---

# 53. Execution Watcher Diagnostics

Check the timer:

```bash
systemctl list-timers \
    lums-execution-watcher.timer
```

Check recent executions:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

Run manually:

```bash
sudo systemctl start \
    lums-execution-watcher.service
```

Then inspect:

```bash
sudo systemctl status \
    lums-execution-watcher.service \
    --no-pager
```

---

# 54. Update Job Lifecycle

The current LUMS job lifecycle is:

```text
pending
   |
   v
waiting_for_idle
   |
   v
running
   |
   +------> success
   |
   +------> partial
   |
   +------> failed
   |
   +------> abandoned
```

A job may wait for the client to become idle before execution.

The job must be claimed atomically so that two executions cannot process the same job simultaneously.

---

# 55. Supported Update Actions

The current package-management abstraction supports actions including:

```text
INSTALL
REMOVE
UPDATE
UPDATE_SYSTEM
```

The exact package operation depends on the selected package manager.

Examples:

```text
Debian / Ubuntu
    |
    +-- apt-get install
    +-- apt-get remove
    +-- apt-get install --only-upgrade
    +-- apt-get upgrade

Arch
    |
    +-- pacman -S
    +-- pacman -R
    +-- pacman -S <package>
    +-- pacman -Syu
```

The server creates the job.

The client performs the actual package operation.

---

# 56. Atomic Job Claiming

The client must claim a job before executing it.

The conceptual sequence is:

```text
Find job
   |
   v
Validate ownership
   |
   v
Atomic claim
   |
   v
running
   |
   v
Execute
```

If another process has already claimed the job, the second process must not execute it.

This protects against duplicate execution.

---

# 57. Update Timeout Handling

Package operations are subject to controlled timeout handling.

The current implementation uses selector-driven process output rather than an indefinitely blocking `readline()` loop.

The timeout sequence is:

```text
Process running
      |
      v
Timeout reached
      |
      v
SIGTERM / terminate
      |
      v
Grace period
      |
      +---- process exits
      |
      v
SIGKILL / kill fallback
      |
      v
Cleanup
```

The current terminate grace period is:

```text
10 seconds
```

A timed-out update is reported as:

```text
timeout
```

This prevents a stuck package-manager process from blocking the execution worker indefinitely.

---

# 58. Interrupted Job Recovery

If a client disappears while a job is running, LUMS can recover the interrupted state.

Possible causes include:

```text
client shutdown
power loss
network failure
reboot
agent interruption
package-manager failure
failed result submission
```

Recovery verifies:

```text
job exists
client ownership matches
job is still running
state transition is valid
job was not already completed
job was not already abandoned
```

Recovery is protected against races.

An unresolved recovery failure must not be silently ignored.

---

# 59. Agent Recovery Behavior

The expected behavior is:

```text
Existing running job
        |
        v
Recovery attempt
        |
        +---- failure ----> STOP
        |
        v
Recovery successful
        |
        v
Continue processing
```

The agent must not simply skip an unresolved running job and continue with another update.

This prevents inconsistent job state.

---

# 60. First End-to-End Client Test

After installing and configuring the agent, perform the first report:

```bash
sudo systemctl start \
    lums-agent.service
```

Check:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "5 minutes ago" \
    --no-pager
```

Expected successful behavior:

```text
HTTPS connection
      |
      v
Bearer authentication
      |
      v
Inventory submission
      |
      v
REPORT ACCEPTED
```

Then verify the client in the LUMS web interface.

The client should show current information including:

```text
hostname
operating system
architecture
kernel
agent version
installed packages
available updates
last seen
```

For the current tested agent:

```text
Agent:
    1.7.0
```

Only after successful reporting should update-job execution be tested.

# 61. Update Job Verification

After the client has successfully reported to LUMS, an update job can be tested.

The general workflow is:

```text
Administrator
     |
     v
Web Interface
     |
     v
Create Update Job
     |
     v
pending
     |
     v
waiting_for_idle
     |
     v
Execution Watcher
     |
     v
running
     |
     v
Package Manager
     |
     v
Result
     |
     v
LUMS
```

The client must belong to the job.

The agent must authenticate successfully before it can retrieve or report a job.

---

# 62. Test Package Update

For an individual package update, select a package that is actually available for update.

The job should move through:

```text
pending
    ↓
waiting_for_idle
    ↓
running
    ↓
success
```

If the client is currently active, the job may remain in:

```text
waiting_for_idle
```

until the idle threshold is reached.

Do not interpret `waiting_for_idle` as a failed job.

---

# 63. Test System Update

The system update action is:

```text
UPDATE_SYSTEM
```

The server creates the job.

The client determines which native package-manager operation must be executed.

Debian-based systems use:

```text
apt-get upgrade -y
```

Arch Linux uses:

```text
pacman -Syu --noconfirm
```

The result is reported back to LUMS.

A successful job should contain a final result rather than remaining indefinitely in:

```text
running
```

---

# 64. Update Job Result

The result of an update job can be:

```text
success
partial
failed
abandoned
```

A successful execution does not necessarily mean that every requested package operation changed the system.

The final result must be interpreted together with:

```text
job status
package results
exit status
output
error information
```

The server stores the resulting job history.

---

# 65. Frontend Update Job Troubleshooting

If an update button is visible but no job appears:

```text
1. Inspect browser console
2. Inspect network requests
3. Verify POST request
4. Check authentication
5. Check server logs
6. Check job creation
7. Check client retrieval
```

The presence of a frontend button does not prove that the backend accepted the request.

The corresponding system action is:

```text
UPDATE_SYSTEM
```

When investigating a frontend problem, separate:

```text
Frontend
   ↓
API
   ↓
Database
   ↓
Agent
   ↓
Package Manager
```

Do not immediately modify the package manager when the actual problem is a frontend or API request.

---

# 66. Browser Cache

If a frontend change has been deployed but the browser still shows the old version:

```text
1. Hard refresh
2. Open Developer Tools
3. Disable cache temporarily
4. Reload
5. Inspect CSS
6. Inspect JavaScript
7. Check localStorage
8. Check data-theme
```

Firefox:

```text
Ctrl+Shift+R
```

LUMS stores the selected frontend theme in:

```text
lums-theme
```

If the theme appears incorrect, inspect the current browser `localStorage` state before changing the application source.

Do not rebuild the Docker image solely because of a browser-cache problem.

---

# 67. Git Diagnostics

Check repository state:

```bash
cd /opt/lums-public

git status -sb
```

Fetch:

```bash
git fetch origin
```

Check remote:

```bash
git remote -v
```

Recent commits:

```bash
git log \
    --oneline \
    --decorate \
    -5
```

Check changes:

```bash
git diff
```

Check whitespace:

```bash
git diff --check
```

A clean deployment should start from a known Git state.

---

# 68. Git Deployment Checks

Before deploying a repository update:

```bash
cd /opt/lums-public

git status -sb
git fetch origin
git diff --check
```

If the working tree is clean and the remote changes are intended:

```bash
git pull --ff-only origin main
```

Then:

```bash
git status -sb
```

Never use a destructive reset merely to make the working tree clean unless the local changes have been intentionally discarded.

---

# 69. Git Identity

The current LUMS Git identity is:

```text
Name:
NovaForgeCtrl

Email:
xxxxxxnoreply.github.com
```

Verify:

```bash
git config user.name
git config user.email
```

Expected:

```text
NovaForgeCtrl
xxxxxnoreply.github.com
```

The Git identity is unrelated to the LUMS administrator account.

Do not use the administrator password or application secrets as Git credentials.

---

# 70. Container Recreation

When replacing the application container, preserve:

```text
lums-data
```

and:

```text
/etc/lums/secrets/lums_secret
```

The normal sequence is:

```text
Create backup
      ↓
Stop container
      ↓
Remove container
      ↓
Create new container
      ↓
Verify database
      ↓
Verify application
      ↓
Verify HTTPS
```

Stop:

```bash
sudo docker stop lums
```

Remove:

```bash
sudo docker rm lums
```

Do not remove the persistent database volume.

Recreate using the tested configuration:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --tmpfs /tmp:rw,nosuid,nodev,noexec \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -p 127.0.0.1:5050:5000 \
    lums:latest
```

---

# 71. Port Diagnostics

Check relevant ports:

```bash
sudo ss -lntp | \
    grep -E ':(22|80|443|5000|5050)\b'
```

Expected architecture:

```text
22
SSH

80
HTTP / redirect

443
HTTPS / Nginx

5050
LUMS host-side application binding

5000
Gunicorn inside Docker
```

Port `5050` should normally be bound only to:

```text
127.0.0.1
```

The Docker container's application port is:

```text
5000
```

It should not be unnecessarily exposed directly to the network.

---

# 72. Firewall Diagnostics

Check UFW:

```bash
sudo ufw status verbose
```

If nftables is used:

```bash
sudo nft list ruleset
```

The intended external services are normally:

```text
SSH
HTTPS
```

HTTP may additionally be required for the HTTPS redirect.

Do not expose:

```text
5050
5000
```

to the LAN unless the architecture explicitly requires it.

Do not change firewall rules while diagnosing an application problem unless there is evidence that the firewall is involved.

---

# 73. Permission Diagnostics

Check the application source:

```bash
ls -la \
    /opt/lums-public
```

Check TLS:

```bash
sudo ls -la \
    /etc/lums/tls/
```

Check the secret without displaying its contents:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/secrets/lums_secret
```

Check the agent:

```bash
sudo ls -la \
    /opt/lums-agent/
```

Do not use:

```bash
chmod 777
```

as a generic troubleshooting solution.

Determine which process requires access and correct only the required ownership or permissions.

---

# 74. Diagnostic Log Reference

## Docker

```bash
sudo docker logs \
    --tail 200 \
    lums
```

## Nginx

```bash
sudo tail \
    -n 100 \
    /var/log/nginx/error.log
```

## Agent

```bash
sudo journalctl \
    -u lums-agent.service \
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
sudo journalctl \
    -u nginx \
    --since "30 minutes ago" \
    --no-pager
```

---

# 75. Server Diagnostic Sequence

Run the following when the server appears broken:

```bash
echo "=== Docker ==="
sudo docker ps --filter name=lums

echo
echo "=== Docker Image ==="
sudo docker inspect \
    -f '{{.Config.Image}}' \
    lums

echo
echo "=== Docker Hardening ==="
sudo docker inspect lums \
    --format \
    'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{json .HostConfig.CapDrop}} Privileged={{.HostConfig.Privileged}}'

echo
echo "=== Docker Logs ==="
sudo docker logs \
    --tail 50 \
    lums

echo
echo "=== Port 5050 ==="
sudo ss -lntp | \
    grep ':5050' || true

echo
echo "=== Local Application ==="
curl -I \
    http://127.0.0.1:5050/ \
    || true

echo
echo "=== Nginx ==="
sudo nginx -t

echo
echo "=== Nginx Status ==="
sudo systemctl is-active nginx

echo
echo "=== Secret Configuration ==="
sudo docker exec lums sh -c '
echo "LUMS_SECRET_KEY_FILE=${LUMS_SECRET_KEY_FILE}"

if [ -n "${LUMS_SECRET_KEY:-}" ]; then
    echo "LUMS_SECRET_KEY=PRESENT"
else
    echo "LUMS_SECRET_KEY=ABSENT"
fi

if [ -r /run/secrets/lums_secret ]; then
    echo "SECRET_FILE=READABLE"
else
    echo "SECRET_FILE=NOT_READABLE"
fi
'

echo
echo "=== LUMS Database ==="
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

The sequence deliberately does not print the actual Flask secret.

---

# 76. Client Diagnostic Sequence

Run on the client:

```bash
echo "=== Agent Service ==="
sudo systemctl is-active lums-agent.service

echo
echo "=== Agent Timer ==="
sudo systemctl is-active lums-agent.timer

echo
echo "=== Watcher Timer ==="
sudo systemctl is-active lums-execution-watcher.timer

echo
echo "=== Agent Version ==="
grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/agent.py

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
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager

echo
echo "=== Watcher Logs ==="
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

The token value is intentionally not displayed.

---

# 77. Database Diagnostics

Check SQLite integrity:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

Expected:

```text
ok
```

Check foreign keys:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA foreign_key_check;"
```

Expected:

```text
```

An empty result means no foreign-key violations were found.

Check journal mode:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA journal_mode;"
```

Expected:

```text
wal
```

Check busy timeout:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA busy_timeout;"
```

The application connections use:

```text
5000 ms
```

---

# 78. SQLite Backup

The LUMS database is persistent application data.

Before replacing the production container or performing a database migration, create a SQLite-aware backup.

Create the backup directory:

```bash
sudo install -d \
    -o root \
    -g root \
    -m 700 \
    /var/backups/lums
```

A SQLite-aware backup can be created using Python:

```bash
sudo docker run --rm \
    --entrypoint python3 \
    -v lums-data:/var/lib/lums:ro \
    -v /var/backups/lums:/backup \
    lums:latest \
    -c '
import sqlite3

source = "/var/lib/lums/lums.db"
target = "/backup/lums.db"

src = sqlite3.connect(source)
dst = sqlite3.connect(target)

with dst:
    src.backup(dst)

src.close()
dst.close()

print(target)
'
```

Verify the backup:

```bash
sudo ls -lh \
    /var/backups/lums/lums.db
```

The backup must not be treated as valid merely because a file exists.

---

# 79. Backup Integrity Verification

Run:

```bash
sudo docker run --rm \
    --entrypoint python3 \
    -v /var/backups/lums:/backup:ro \
    lums:latest \
    -c '
import sqlite3

db = sqlite3.connect("/backup/lums.db")
result = db.execute("PRAGMA integrity_check;").fetchone()[0]
print(result)
db.close()
'
```

Expected:

```text
ok
```

Also verify the foreign-key state:

```bash
sudo docker run --rm \
    --entrypoint python3 \
    -v /var/backups/lums:/backup:ro \
    lums:latest \
    -c '
import sqlite3

db = sqlite3.connect("/backup/lums.db")
rows = list(db.execute("PRAGMA foreign_key_check;"))
print(rows)
db.close()
'
```

Expected:

```text
[]
```

A backup should be protected from unauthorized access.

---

# 80. Full Restore Testing

A backup has greater value when restoration has actually been tested.

A full restore test should use an isolated environment.

The principle is:

```text
Production
    |
    v
SQLite-aware backup
    |
    v
Isolated database
    |
    v
Integrity check
    |
    v
Application startup
    |
    v
Functional verification
```

Do not experiment with a production database when testing restore procedures.

The current LUMS documentation should continue to distinguish:

```text
Backup verified
```

from:

```text
Full restore tested
```

These are not the same state.

---

# 81. Production Deployment Checklist

## Repository

```text
[ ] Working tree reviewed
[ ] Remote state reviewed
[ ] git diff --check successful
[ ] Intended commit deployed
```

## Image

```text
[ ] Docker build successful
[ ] Correct image deployed
[ ] Image inspected
```

## Container

```text
[ ] Container running
[ ] User=lums
[ ] ReadonlyRootfs=true
[ ] CapDrop=ALL
[ ] Privileged=false
[ ] /tmp mounted as tmpfs
[ ] lums-data mounted
[ ] Secret mounted read-only
```

## Network

```text
[ ] 127.0.0.1:5050 active
[ ] Nginx active
[ ] HTTPS reachable
[ ] HTTP redirect works
[ ] Port 5050 not externally exposed
[ ] Container port 5000 not unnecessarily exposed
```

## Database

```text
[ ] SQLite integrity check passes
[ ] Foreign-key check passes
[ ] WAL enabled
[ ] Persistent volume present
[ ] Backup created
[ ] Backup integrity verified
```

## Authentication

```text
[ ] Administrator login works
[ ] Login rate limiting active
[ ] Client authentication works
[ ] Client token is not exposed
[ ] Token rotation works
[ ] Old token is invalid
```

## Client

```text
[ ] Agent version 1.7.0
[ ] Agent timer active
[ ] Execution watcher timer active
[ ] CA configured
[ ] Client token configured
[ ] Report accepted
[ ] Inventory visible
```

## Update Execution

```text
[ ] Job creation works
[ ] Job ownership is correct
[ ] Idle detection works
[ ] Job claiming works
[ ] Package manager detected
[ ] Update executes
[ ] Result is reported
[ ] History is stored
```

---

# 82. Debian Client Checklist

```text
[ ] Debian 13
[ ] Python available
[ ] apt available
[ ] dpkg available
[ ] lums-agent.service installed
[ ] lums-agent.timer enabled
[ ] lums-execution-watcher.service installed
[ ] lums-execution-watcher.timer enabled
[ ] CA certificate present
[ ] LUMS_BASE configured
[ ] LUMS_TOKEN configured
[ ] Agent version 1.7.0
[ ] REPORT ACCEPTED
[ ] Updates detected correctly
[ ] Update job tested
```

---

# 83. Arch Linux Client Checklist

```text
[ ] Arch Linux
[ ] Python available
[ ] pacman available
[ ] lums-agent.service installed
[ ] lums-agent.timer enabled
[ ] lums-execution-watcher.service installed
[ ] lums-execution-watcher.timer enabled
[ ] CA certificate present
[ ] LUMS_BASE configured
[ ] LUMS_TOKEN configured
[ ] Agent version 1.7.0
[ ] REPORT ACCEPTED
[ ] pacman -Qu works
[ ] Update job tested
```

---

# 84. Cross-Distribution Verification

The same LUMS management layer can manage the tested distributions:

```text
                         LUMS
                           |
                   Update Management
                           |
              +------------+------------+
              |                         |
              v                         v
          Debian 13                 Arch Linux
              |                         |
          lums-agent                lums-agent
              |                         |
           APT/dpkg                  pacman
              |                         |
              +------------+------------+
                           |
                           v
                         Result
```

The server does not need distribution-specific package-management logic for every client.

Instead, the client-side abstraction selects the native package manager.

---

# 85. Final Installation Verification

The installation is considered functionally verified when the complete path works:

```text
Browser
   |
   v
HTTPS / Nginx
   |
   v
LUMS API
   |
   v
SQLite
   |
   v
Client Job
   |
   v
Execution Watcher
   |
   v
Idle Detection
   |
   v
Atomic Claim
   |
   v
Package Manager
   |
   v
Result
   |
   v
LUMS
```

The verification should include both:

```text
Reporting
```

and:

```text
Update execution
```

A successful web login alone is not sufficient.

---

# 86. Installation Troubleshooting Decision Tree

If the installation does not work:

```text
                    LUMS problem
                         |
                         v
                 Is container running?
                    /          \
                  NO            YES
                  |              |
                  v              v
            Docker logs     Is Nginx running?
                              /        \
                            NO          YES
                            |            |
                            v            v
                       Nginx logs    Can HTTPS
                                     reach LUMS?
                                      /      \
                                    NO        YES
                                    |          |
                                    v          v
                              TLS / network   Authentication
                              diagnostics     / API diagnostics
                                                  |
                                                  v
                                            Can client report?
                                             /           \
                                           NO             YES
                                           |               |
                                           v               v
                                      CA / token /      Job execution
                                      network           diagnostics
```

For client-side problems, verify:

```text
Agent
   ↓
CA
   ↓
Token
   ↓
Report
   ↓
Database
   ↓
Frontend
```

This order avoids changing unrelated components while diagnosing a failure.


# 87. Responsible Security Reporting

Security issues should be reported responsibly.

A useful security report contains:

* short description,
* affected component,
* reproduction steps,
* expected behavior,
* actual behavior,
* potential impact,
* suggested mitigation,
* relevant redacted logs.

Never include:

* passwords,
* client tokens,
* private keys,
* Flask secrets,
* personal information,
* complete production databases,
* unredacted inventory data.

Sensitive information must be removed before logs, screenshots, or configuration files are shared.

---

# 88. Security Maintenance

Security reviews should be performed after:

* application changes,
* authentication changes,
* authorization changes,
* Docker changes,
* Nginx changes,
* certificate changes,
* database schema changes,
* agent changes,
* package-manager changes,
* watcher changes,
* deployment changes,
* secret changes.

Regularly review:

```text
Operating system updates
Docker images
Python dependencies
Flask dependencies
Gunicorn
Nginx
TLS configuration
File permissions
Database backups
Git history
Authentication
Authorization
Job execution
Package-manager coordination
Container privileges
Container capabilities
Secret handling
Secret rotation
Agent configuration
systemd services
systemd timers
```

---

# 89. Security Change Workflow

Security-sensitive changes should follow a controlled workflow:

```text
Inspect
   ↓
Understand current behavior
   ↓
Design change
   ↓
Implement
   ↓
Test locally
   ↓
Test integration
   ↓
Verify production configuration
   ↓
Deploy
   ↓
Verify production
   ↓
Document
```

A failed test should not be hidden by changing the documentation to match the failure.

The implementation must be corrected or the limitation documented.

---

# 90. Current Security Roadmap Status

The current security work is tracked incrementally.

Completed and verified controls include:

```text
[x] Non-root container
[x] Drop ALL capabilities
[x] Privileged container disabled
[x] Read-only root filesystem
[x] tmpfs /tmp
[x] Localhost-only application binding
[x] Protected secret file
[x] Read-only secret mount
[x] Secret isolation
[x] Flask secret rotation
[x] Administrator authentication
[x] Client authentication
[x] Client token hashing
[x] Client token rotation
[x] Client token invalidation
[x] Token rotation audit logging
[x] CSRF protection for token rotation
[x] Login rate limiting
[x] Job ownership validation
[x] Atomic job claiming
[x] Interrupted-job recovery
[x] Update execution timeout handling
[x] Debian client communication
[x] Arch client communication
[x] APT support
[x] pacman support
[x] systemd-logind idle detection
[x] Gunicorn deployment
[x] HTTPS reverse proxy
[x] Security headers
[x] SQLite foreign-key enforcement
[x] SQLite busy timeout
[x] SQLite WAL mode
[x] SQLite integrity verification
[x] SQLite-aware backup
[x] Backup integrity verification
```

Remaining hardening work includes:

```text
[ ] Complete package-manager collision prevention
[ ] Full backup / restore test
[ ] Automated security regression tests
[ ] Remaining security audit phases
[ ] Final security review
```

The completed controls do not mean that LUMS has no remaining security work.

Security hardening is continuous.

Documentation must reflect the actually verified production state.

---

# 91. Security Verification Principles

LUMS follows several operational rules.

## Rule 1 — Do not trust configuration alone

A configuration file saying:

```text
read-only
```

is not sufficient.

The running container must be inspected.

---

## Rule 2 — Do not trust successful startup alone

A running container does not prove:

* authentication works,
* HTTPS works,
* database integrity is valid,
* clients can authenticate,
* update jobs work.

Each layer must be verified.

---

## Rule 3 — Do not trust a backup merely because it exists

A backup must be:

```text
created
   ↓
protected
   ↓
integrity checked
   ↓
eventually restored in isolation
```

The final isolated restore test remains a separate verification step.

---

## Rule 4 — Treat exposed secrets as compromised

A secret that was exposed must not be considered safe merely because it is no longer visible.

It must be rotated.

The previous Flask secret exposure is treated as a completed security incident.

The previous value must never be reproduced in documentation.

---

## Rule 5 — Authentication does not equal authorization

A valid client token establishes client identity.

The server must still verify whether that client is authorized for the requested resource.

Client state, ownership and job authorization must be validated server-side.

---

## Rule 6 — Package installation is privileged execution

Update jobs must be treated as privileged operations.

The system must control:

```text
who
what
where
when
result
```

The client agent performs the actual package-management operation.

The server does not directly execute package-management commands on managed clients.

---

## Rule 7 — Documentation follows verification

Documentation should describe the actual tested state.

If something is incomplete, it must be marked as incomplete.

The documentation must not claim that a security control is complete merely because an implementation exists.

---

# 92. Final Verified Architecture

The current LUMS architecture is:

```text
                    Network
                       │
                       ▼
                  ┌─────────┐
                  │  Nginx  │
                  │  HTTPS  │
                  └────┬────┘
                       │
                 localhost only
                       │
                       ▼
              ┌────────────────┐
              │ 127.0.0.1:5050│
              └───────┬────────┘
                      │
                Docker mapping
                      │
                      ▼
              ┌────────────────┐
              │ LUMS Container │
              │                │
              │    Gunicorn    │
              │       ↓        │
              │     Flask      │
              │       ↓        │
              │     SQLite     │
              └───────┬────────┘
                      │
                 HTTPS + Bearer
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
   Debian 13 Client        Arch Linux Client
          │                       │
     lums-agent 1.7.0       lums-agent 1.7.0
          │                       │
     APT / dpkg                pacman
          │                       │
          └───────────┬───────────┘
                      │
                      ▼
                   Result
                      │
                      ▼
                  LUMS API
```

The management plane remains separated from the execution plane.

```text
Management Plane
       │
       ├── Nginx
       ├── HTTPS
       ├── Gunicorn
       ├── Flask
       ├── Authentication
       ├── Authorization
       ├── Inventory
       ├── Job Management
       └── SQLite

              from

Execution Plane
       │
       ├── lums-agent
       ├── systemd
       ├── Execution Watcher
       ├── Package Manager Abstraction
       ├── APT / dpkg
       └── pacman
```

The server manages the desired operation.

The client performs the actual package-management operation.

This separation reduces the need for the server to have direct operating-system privileges on managed clients.

---

# 93. Final Management / Execution Separation

The final architecture deliberately separates:

```text
Management Plane
       │
       ├── Nginx
       ├── HTTPS
       ├── Gunicorn
       ├── Flask
       ├── Authentication
       ├── Authorization
       ├── Inventory
       ├── Job Management
       └── SQLite
```

from:

```text
Execution Plane
       │
       ├── lums-agent
       ├── systemd
       ├── Execution Watcher
       ├── Package Manager Abstraction
       ├── APT / dpkg
       └── pacman
```

The server manages jobs and records their state.

The client validates and executes authorized package operations.

The Execution Watcher handles idle-aware execution and recovery logic.

This separation keeps privileged package-management operations on the managed client instead of moving them into the central server.

---

# 94. Final Security State

The current LUMS implementation has verified security controls across:

```text
Container
   ↓
Network
   ↓
TLS
   ↓
Authentication
   ↓
Authorization
   ↓
Secrets
   ↓
Tokens
   ↓
Login Protection
   ↓
Jobs
   ↓
Timeout Handling
   ↓
Recovery
   ↓
Agent
   ↓
Package Manager
   ↓
Database
   ↓
Backups
```

The current production container uses:

```text
Non-root user
Read-only root filesystem
Dropped capabilities
Non-privileged runtime
Protected secret file
Read-only secret mount
Persistent database volume
tmpfs /tmp
Localhost-only application binding
```

The remaining work is explicitly limited to the documented open hardening areas.

The project should not claim a final security review until the remaining security audit phases have been completed and verified.

---

# 95. Final Security Principles

The following principles apply to LUMS:

1. Never store secrets in Git.
2. Never expose the Flask/Gunicorn application directly to the network.
3. Use HTTPS for client communication.
4. Keep TLS verification enabled.
5. Separate authentication from authorization.
6. Validate client identity server-side.
7. Protect administrator credentials.
8. Protect client tokens.
9. Protect TLS private keys.
10. Protect the mounted Flask secret.
11. Keep database backups secure.
12. Verify backups rather than trusting file existence.
13. Do not remove persistent volumes during ordinary troubleshooting.
14. Do not automatically reboot clients.
15. Review changes before deployment.
16. Test security-sensitive changes.
17. Document incidents and configuration changes.
18. Do not claim incomplete security controls are fully implemented.
19. Keep update execution controlled and auditable.
20. Harden the container incrementally.
21. Treat secret isolation and secret rotation as separate controls.
22. Treat previously exposed secrets as compromised until rotated.
23. Rotate client tokens through the authenticated administrative workflow.
24. Verify replacement credentials before closing a credential change.
25. Keep production secrets outside Git and outside normal container environment variables where practical.
26. Use distribution-specific package-manager implementations behind a controlled abstraction.
27. Validate job ownership on the server.
28. Use atomic state transitions for job claiming and recovery.
29. Prefer conservative behavior when system state cannot be reliably determined.
30. Keep production documentation synchronized with verified implementation state.
31. Test recovery paths, not only successful paths.
32. Treat security hardening as a continuous process rather than a one-time configuration.

---

# 96. Final Principle

LUMS is designed to centralize Linux update management without removing operational control from the administrator.

The system should remain:

* Transparent
* Auditable
* Controlled
* Secure
* Documented
* Maintainable

The architecture deliberately separates:

```text
Central management
        from
Client-side execution
```

LUMS should therefore remain a system that does not hide what happens during an update.

The administrator should be able to determine:

```text
what was requested
        ↓
which client received the job
        ↓
why the job was executed
        ↓
which package manager was used
        ↓
what happened during execution
        ↓
which result was reported
        ↓
what was recorded in the audit trail
```

The goal is not to make Linux update management invisible.

The goal is to make it understandable, controlled and auditable.

**Linux Update Management without the noise.**

