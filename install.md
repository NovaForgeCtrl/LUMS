# LUMS Installation Guide

## Linux Update Management Server

**Version:** 2.5
**Project:** LUMS
**Slogan:** Linux Update Management without the noise.

---

# 1. Overview

LUMS is a centralized Linux update management platform designed for controlled update distribution, client reporting, job management, and auditable execution.

The project is intended for laboratory environments, small infrastructures, and future production-oriented development.

LUMS currently includes:

* Flask-based backend
* Gunicorn WSGI application server
* SQLite database
* Docker deployment
* Nginx reverse proxy
* HTTPS encryption
* Linux client agent
* Separate execution watcher
* Centralized update jobs
* Client status reporting
* Audit logging
* Idle-aware update execution
* Client token lifecycle management
* Client token rotation
* Interrupted-job recovery
* Hardened Docker deployment

The project follows this troubleshooting principle:

> Do not reinstall everything immediately. Find the layer where the problem occurs.

---

## 2. Supported Installation Platforms

LUMS separates the **server platform** from the **client platform**.

### 2.1 Server

| Platform                | Status              |
| ----------------------- | ------------------- |
| Ubuntu Server 26.04 LTS | Reference platform  |
| Debian 13 Trixie        | Successfully tested |

Ubuntu Server 26.04 LTS remains the reference platform of the project.

Debian 13 Trixie has additionally been installed and tested end-to-end.

The Debian installation used:

* Docker Engine
* Docker image `lums:latest`
* persistent Docker volume
* Nginx
* HTTPS
* UFW
* systemd
* native LUMS agent
* native execution watcher

The complete Debian installation successfully reached the following state:

```text
Browser
   |
   v
Nginx HTTPS
   |
   v
127.0.0.1:5050
   |
   v
LUMS Docker container
   |
   v
Gunicorn / Flask
   |
   v
SQLite
   |
   v
Linux Agent
```

### 2.2 Client

The LUMS agent is designed for Debian/Ubuntu-based Linux systems.

The following client platform has been tested during the current installation work:

```text
Debian 13 Trixie
```

Ubuntu remains an intended client platform, but a platform should only be described as tested after an actual installation and verification.

---

# 3. Architecture

```text
                         Client Browser
                              |
                              | HTTPS :443
                              |
                    +----------------------+
                    |        Nginx         |
                    | HTTPS Reverse Proxy  |
                    +----------+-----------+
                               |
                               | HTTP localhost
                               |
                    +----------v-----------+
                    |      Docker Host     |
                    |                      |
                    |  127.0.0.1:5050      |
                    |          |           |
                    |  +-------v--------+  |
                    |  | LUMS Container |  |
                    |  |                |  |
                    |  | Gunicorn       |  |
                    |  | Flask :5000    |  |
                    |  +-------+--------+  |
                    |          |           |
                    |  +-------v--------+  |
                    |  | SQLite Volume |  |
                    |  | lums-data     |  |
                    |  +----------------+  |
                    +----------------------+
                               |
                    HTTPS / Bearer Auth
                               |
          +--------------------+--------------------+
          |                    |                    |
+---------v---------+ +--------v---------+ +--------v---------+
| Linux Client 01   | | Linux Client 02  | | Linux Client 03  |
|                   | |                  | |                  |
| lums-agent        | | lums-agent       | | lums-agent       |
| watcher.py        | | watcher.py       | | watcher.py       |
+-------------------+ +------------------+ +------------------+
```

---

# 4. Container Startup

The current container startup sequence is:

```text
Docker
   |
   v
docker-entrypoint.sh
   |
   +--> init_db.py
   |
   v
Gunicorn
   |
   +--> Worker 1
   |
   +--> Worker 2
   |
   v
Flask application
```

Database initialization therefore occurs before Gunicorn starts.

The Flask development server is not used for the current deployment.

---

# 5. Network Flow

```text
External HTTPS :443
        |
        v
Nginx
        |
        v
127.0.0.1:5050
        |
        v
Docker container :5000
        |
        v
Gunicorn
        |
        v
Flask
```

The Flask application is not directly exposed to the network.

The Docker host port is bound to localhost:

```text
127.0.0.1:5050:5000
```

Port `5000` remains internal to the container.

Port `5050` is only reachable through localhost on the Docker host.

---

# 6. Main Components

## 6.1 LUMS Server

The LUMS server provides:

* Web interface
* Client registration
* Client reporting
* Update job creation
* Job state management
* Job claiming
* Job result processing
* Audit logging
* Authentication
* Authorization
* Database access
* Client token rotation

The Flask application runs inside a Docker container.

Gunicorn provides the WSGI application server.

The current production deployment uses:

```text
Gunicorn 23.0.0
```

with multiple workers.

---

## 6.2 Nginx Reverse Proxy

Nginx provides:

* HTTPS termination
* TLS certificate handling
* HTTP-to-HTTPS redirection
* Reverse proxying to Gunicorn
* External access through port 443
* Security response headers

The laboratory configuration uses a self-signed TLS certificate.

Self-signed certificates require explicit trust configuration on clients and browsers.

---

## 6.3 Linux Agent

The LUMS agent is responsible for:

* Collecting system information
* Detecting installed packages
* Detecting available updates
* Reporting client status
* Sending data to the LUMS server
* Communicating through Bearer authentication

The reporting agent and execution watcher are separate components.

A successful report does not automatically validate update execution.

---

## 6.4 Execution Watcher

The execution watcher is separated from the reporting agent.

Its intended responsibilities include:

* Checking pending update jobs
* Checking client idle state
* Claiming jobs atomically
* Executing approved jobs
* Recovering interrupted jobs
* Sending execution results
* Reporting execution states

The recovery workflow has been implemented and tested.

The complete update execution hardening still requires separate validation.

---

# 7. Current Execution Model

The execution watcher uses an idle-aware execution model.

A job should only be executed when:

1. The client supports idle detection.
2. The configured idle threshold has been reached.
3. A pending job exists.
4. The job can be claimed successfully.
5. The package manager is not already being used by another process.

The default idle threshold is:

```text
300 seconds
```

The current idle detection uses:

```text
w -h
```

This primarily supports server, terminal, console, and SSH-oriented environments.

It is not universal desktop idle detection.

The watcher reports metadata such as:

```text
idle
idle_seconds
idle_threshold_seconds
idle_source
idle_supported
```

The watcher must not execute update jobs while active user activity is detected.

Idle detection and package manager coordination require additional hardening for broader desktop and production use.

---

# 8. Job States

The current job lifecycle includes:

```text
pending
   |
   v
running
   |
   +----------+----------+------------+
   |          |          |            |
   v          v          v            v
success    partial     failed     abandoned
```

### 8.1 Pending

The job has been created but has not yet been claimed.

### 8.2 Running

The job has been claimed and is currently being processed.

### 8.3 Success

The job completed successfully.

### 8.4 Partial

The job completed with some operations succeeding and others failing.

### 8.5 Failed

The job could not be completed successfully.

### 8.6 Abandoned

An interrupted running job can be recovered as:

```text
abandoned
```

The recovery process records:

* Finished timestamp
* Recovery reason
* Update history
* Package statistics
* Existing reboot state

The current recovery reason is:

```text
Agent did not submit a final result.
```

---

# 9. Repository Structure

The repository contains the following relevant structure:

```text
LUMS/
├── agent/
│   ├── agent.py
│   ├── watcher.py
│   ├── lums-agent.service
│   ├── lums-agent.timer
│   └── lums-agent.env.example
├── server/
│   ├── app.py
│   ├── init_db.py
│   ├── security.py
│   ├── security_migration.py
│   ├── create_admin.py
│   ├── static/
│   ├── templates/
│   └── requirements.txt
├── Dockerfile
├── docker-entrypoint.sh
├── README.md
└── ...
```

The exact repository structure may change during development.

The current Dockerfile uses:

```text
python:3.13-slim
```

The server dependencies are defined in:

```text
server/requirements.txt
```

The current requirements include:

```text
Flask==3.1.3
argon2-cffi==25.1.0
gunicorn==23.0.0
```

---

# 10. Server Requirements

Recommended requirements:

* Linux operating system
* Docker Engine
* Nginx
* OpenSSL
* UFW or another firewall
* Persistent storage
* Backup storage

Docker Compose is optional because the current installation uses:

```text
docker build
docker run
```

The server must have sufficient storage for:

* Docker images
* Application files
* SQLite database
* Logs
* Backups
* TLS certificates

---

# 11. Directory Layout

Recommended directory layout:

```text
/opt/lums-public/
    Git repository

/etc/lums/
├── docker/
│   └── lums.env
├── secrets/
│   └── lums_secret
└── tls/
    ├── lums.crt
    └── lums.key

/var/backups/lums/
    SQLite backups

/opt/lums-agent/
├── agent.py
├── watcher.py
└── lums-ca.crt
```

The current Docker deployment uses the persistent volume:

```text
lums-data
```

The volume contains the application database.

---

# 12. Installation – Ubuntu Server 26.04 LTS

Ubuntu Server 26.04 LTS is the reference platform for LUMS.

The server installation consists of:

```text
Ubuntu
  |
  +-- Docker
  |
  +-- LUMS image
  |
  +-- Persistent SQLite volume
  |
  +-- Nginx
  |
  +-- HTTPS
  |
  +-- UFW
  |
  +-- Agent / Watcher
```

---

## 12.1 Update Ubuntu

```bash
sudo apt update
sudo apt upgrade -y
```

Install basic requirements:

```bash
sudo apt install -y \
  ca-certificates \
  curl \
  git \
  openssl \
  nginx \
  ufw
```

---

## 12.2 Docker

Install Docker Engine according to the current official Docker instructions for Ubuntu.

Verify:

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

Docker must be operational before continuing.

---

# 13. Installation – Debian 13 Trixie

Debian 13 is additionally supported and has been successfully tested end-to-end.

The Debian installation is functionally equivalent to the Ubuntu architecture but has several platform-specific points.

---

## 13.1 Update Debian

```bash
sudo apt update
sudo apt upgrade -y
```

Install basic requirements:

```bash
sudo apt install -y \
  ca-certificates \
  curl \
  git \
  openssl \
  nginx \
  ufw
```

---

## 13.2 Debian DVD/CD-ROM Repository

A fresh Debian installation may still contain an installation-media repository such as:

```text
deb cdrom:...
```

This can cause:

```text
apt update
```

to request installation media.

Check:

```bash
grep -RniE '^[[:space:]]*deb[[:space:]]+cdrom:' \
  /etc/apt/sources.list \
  /etc/apt/sources.list.d/ 2>/dev/null
```

If an installation-media entry is active, disable that repository.

For example:

```bash
sudo sed -i \
  's|^[[:space:]]*deb cdrom:|# deb cdrom:|' \
  /etc/apt/sources.list
```

Then:

```bash
sudo apt update
```

The Debian network repositories and required third-party repositories must remain available.

---

## 13.3 Docker on Debian 13

Install Docker from the official Docker repository.

Create the keyring directory:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
```

Download the Docker repository key:

```bash
sudo curl -fsSL \
  https://download.docker.com/linux/debian/gpg \
  -o /etc/apt/keyrings/docker.asc
```

Set permissions:

```bash
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

Configure the Docker repository:

```bash
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

Update package information:

```bash
sudo apt update
```

Install Docker:

```bash
sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

Enable Docker:

```bash
sudo systemctl enable --now docker
```

Verify:

```bash
sudo systemctl status docker --no-pager
```

Check:

```bash
sudo docker version
sudo docker info
```

The Debian 13 installation tested during development used Docker successfully with:

```text
Docker Engine
containerd
Buildx
Compose plugin
```

---

# 14. Clone or Update the Repository

Clone the repository:

```bash
sudo mkdir -p /opt
cd /opt

sudo git clone \
  <REPOSITORY_URL> \
  lums-public
```

If the repository already exists:

```bash
cd /opt/lums-public

git fetch origin
git status -sb
git pull --ff-only origin main
```

Review:

```bash
git log --oneline --decorate -5
git diff --check
```

---

# 15. Docker Environment Configuration

Create:

```bash
sudo install -d \
  -o root \
  -g root \
  -m 750 \
  /etc/lums/docker
```

Create:

```bash
sudo tee /etc/lums/docker/lums.env > /dev/null <<'EOF'
FLASK_ENV=production
LUMS_DB_PATH=/var/lib/lums/lums.db
EOF
```

Set permissions:

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

Expected:

```text
root:root 600 /etc/lums/docker/lums.env
```

---

# 16. Flask Secret File

Create:

```bash
sudo install -d \
  -o root \
  -g root \
  -m 700 \
  /etc/lums/secrets
```

Generate:

```bash
sudo openssl rand -base64 48 | \
  sudo tee /etc/lums/secrets/lums_secret > /dev/null
```

Set ownership:

```bash
sudo chown root:10001 \
  /etc/lums/secrets/lums_secret
```

Set permissions:

```bash
sudo chmod 640 \
  /etc/lums/secrets/lums_secret
```

Verify without printing the secret:

```bash
sudo stat \
  -c '%U:%G %a %n' \
  /etc/lums/secrets/lums_secret
```

Expected:

```text
root:lums 640 /etc/lums/secrets/lums_secret
```

### Debian note

On Debian the command may display:

```text
root:UNKNOWN 640 /etc/lums/secrets/lums_secret
```

if the host does not have a named group for numeric GID `10001`.

This does not automatically indicate an error.

The container uses the numeric group ID associated with the `lums` user/group.

Verify the numeric ownership:

```bash
sudo stat \
  -c '%u:%g %a %n' \
  /etc/lums/secrets/lums_secret
```

The expected group ID is:

```text
10001
```

Do not arbitrarily change the group ownership simply because the host cannot resolve the numeric group name.

---

# 17. Build the Docker Image

```bash
cd /opt/lums-public

sudo docker build -t lums:latest .
```

Verify:

```bash
sudo docker image ls lums
```

Verify the configured user:

```bash
sudo docker image inspect \
  lums:latest \
  --format 'User={{.Config.User}}'
```

Expected:

```text
User=lums
```

---

# 18. Persistent Docker Volume

Create:

```bash
sudo docker volume create lums-data
```

Verify:

```bash
sudo docker volume ls
```

Inspect:

```bash
sudo docker volume inspect lums-data
```

The volume contains persistent LUMS data.

Do not remove it during ordinary troubleshooting.

---

# 19. Database Initialization and Security Migration

The normal container entrypoint is:

```text
/app/docker-entrypoint.sh
```

It performs:

```text
init_db.py
    |
    v
Gunicorn
```

There is an important distinction between **normal container startup** and **manual execution of `security_migration.py`**.

The image's default entrypoint does not execute arbitrary commands appended to `docker run` directly. It always starts the entrypoint first.

Therefore, when manually executing:

```text
security_migration.py
```

the entrypoint must be overridden.

### Correct migration command

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

The important parts are:

```text
--entrypoint python3
```

and:

```text
/app/server/security_migration.py
```

and:

```text
-v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro
```

This is **not Debian-specific**.

The same rule applies to Ubuntu.

### Why the entrypoint override is required

The normal entrypoint performs:

```text
init_db.py
+
Gunicorn
```

Therefore a command such as:

```bash
lums:latest python3 security_migration.py
```

does not bypass the image entrypoint.

Without:

```text
--entrypoint python3
```

the migration command can be followed by an unwanted Gunicorn startup.

The production secret is also required because the Flask application loads its secret through:

```text
LUMS_SECRET_KEY_FILE
```

---

# 20. Verify Database

After migration:

```bash
sudo docker start lums
```

or create the production container if it does not exist.

Verify the database:

```bash
sudo docker exec lums \
  python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

print("Users:", db.execute(
    "SELECT COUNT(*) FROM users"
).fetchone()[0])

print("Admin:", db.execute(
    "SELECT username, enabled FROM users WHERE username = ?",
    ("admin",)
).fetchone())

db.close()
'
```

Expected:

```text
Users: 1
Admin: ('admin', 1)
```

The exact number of users may differ if additional administrators have been created.

The important point is that the administrator exists and is enabled.

---

# 21. Start the Hardened LUMS Container

Use:

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

Verify:

```bash
sudo docker ps
```

Logs:

```bash
sudo docker logs --tail 100 lums
```

---

# 22. Container Hardening Verification

Verify user:

```bash
sudo docker inspect lums \
  --format 'User={{.Config.User}}'
```

Expected:

```text
User=lums
```

Verify read-only root filesystem:

```bash
sudo docker inspect lums \
  --format 'ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}'
```

Expected:

```text
ReadonlyRootfs=true
```

Verify capabilities:

```bash
sudo docker inspect lums \
  --format 'CapDrop={{json .HostConfig.CapDrop}}'
```

Expected:

```text
CapDrop=["ALL"]
```

Verify privileged mode:

```bash
sudo docker inspect lums \
  --format 'Privileged={{.HostConfig.Privileged}}'
```

Expected:

```text
Privileged=false
```

---

# 23. Secret Verification

Verify that the secret is not supplied through the normal environment:

```bash
sudo docker exec lums sh -c '
if [ -n "${LUMS_SECRET_KEY:-}" ]; then
    echo "LUMS_SECRET_KEY=PRESENT"
else
    echo "LUMS_SECRET_KEY=ABSENT"
fi

echo "LUMS_SECRET_KEY_FILE=${LUMS_SECRET_KEY_FILE}"

if [ -r /run/secrets/lums_secret ]; then
    echo "SECRET_FILE=READABLE"
else
    echo "SECRET_FILE=NOT_READABLE"
fi
'
```

Expected:

```text
LUMS_SECRET_KEY=ABSENT
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
SECRET_FILE=READABLE
```

Never print:

```text
cat /run/secrets/lums_secret
```

---

# 24. Local Application Test

Test:

```bash
curl -i http://127.0.0.1:5050/
```

Expected:

```text
HTTP/1.1 302 FOUND
Location: /login
```

Test:

```bash
curl -i http://127.0.0.1:5050/login
```

Expected:

* HTTP 200
* Login form
* CSRF token
* Security response headers
* Session cookie

The application is served by Gunicorn.

The Flask development server is not part of the current deployment.

---

# 25. TLS Certificate Directory

Create:

```bash
sudo install -d \
  -o root \
  -g root \
  -m 750 \
  /etc/lums/tls
```

Expected:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Set:

```bash
sudo chown root:root /etc/lums/tls/lums.crt
sudo chown root:root /etc/lums/tls/lums.key

sudo chmod 644 /etc/lums/tls/lums.crt
sudo chmod 600 /etc/lums/tls/lums.key
```

---

# 26. Laboratory TLS Certificate

The laboratory deployment uses a self-signed certificate.

Replace the placeholders:

```bash
sudo openssl req \
  -x509 \
  -nodes \
  -newkey rsa:4096 \
  -keyout /etc/lums/tls/lums.key \
  -out /etc/lums/tls/lums.crt \
  -days 365 \
  -subj "/C=<COUNTRY>/ST=<STATE>/L=<CITY>/O=<ORGANIZATION>/OU=<UNIT>/CN=<SERVER_NAME>" \
  -addext "subjectAltName=IP:<SERVER_IP>"
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
  -issuer \
  -dates
```

The certificate must contain a valid SAN for the hostname or IP address used by clients.

Self-signed certificates are suitable for controlled laboratory environments.

They require explicit trust configuration on clients and browsers.

---

# 27. Nginx Configuration

Create:

```bash
sudo tee /etc/nginx/sites-available/lums > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;

    server_name <SERVER_NAME_OR_IP>;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name <SERVER_NAME_OR_IP>;

    ssl_certificate     /etc/lums/tls/lums.crt;
    ssl_certificate_key /etc/lums/tls/lums.key;

    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://127.0.0.1:5050;

        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

Enable:

```bash
sudo ln -s \
  /etc/nginx/sites-available/lums \
  /etc/nginx/sites-enabled/lums
```

Test:

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

Test HTTPS:

```bash
curl -k -I https://<SERVER_NAME_OR_IP>/
```

The `-k` option is only intended for controlled diagnostics with the self-signed laboratory certificate.

---

# 28. Security Headers

Verify:

```bash
curl -k -I \
  https://<SERVER_NAME_OR_IP>/
```

Expected security headers include:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy:
    camera=(),
    microphone=(),
    geolocation=(),
    payment=()
```

The Content Security Policy includes:

```text
default-src 'self'
script-src 'self'
style-src 'self'
img-src 'self' data:
font-src 'self'
connect-src 'self'
object-src 'none'
base-uri 'self'
frame-ancestors 'none'
form-action 'self'
```

---

# 29. Firewall

Install UFW if required:

```bash
sudo apt update
sudo apt install -y ufw
```

Allow SSH before enabling:

```bash
sudo ufw allow <SSH_PORT>/tcp
```

Allow HTTP:

```bash
sudo ufw allow 80/tcp
```

Allow HTTPS:

```bash
sudo ufw allow 443/tcp
```

Review:

```bash
sudo ufw status verbose
```

Enable:

```bash
sudo ufw enable
```

Do not expose:

```text
5000
5050
```

The application must remain behind Nginx.

---

# 30. End-to-End Server Validation

At this point the server should provide:

```text
Browser
   |
   | HTTPS
   v
Nginx :443
   |
   | localhost
   v
127.0.0.1:5050
   |
   v
LUMS Docker container
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

Run:

```bash
sudo docker ps
```

```bash
sudo docker logs --tail 100 lums
```

```bash
sudo nginx -t
```

```bash
sudo systemctl status nginx --no-pager
```

```bash
sudo ufw status verbose
```

```bash
curl -i http://127.0.0.1:5050/
```

```bash
curl -k -i https://<SERVER_NAME_OR_IP>/login
```

Expected:

```text
HTTP/1.1 200 OK
```

for the actual HTTPS GET request to `/login`.

The server side is ready for client configuration once these checks succeed.

---

# 31. Important Platform Notes

## Ubuntu

Ubuntu 26.04 LTS is the reference server platform.

The previous Ubuntu installation used a Docker-based deployment with separate container responsibilities, including a container configuration where the protected secret was mounted into the application environment.

The exact historical Ubuntu layout must not be confused with the current hardened single-application-container architecture.

The important security principle remains:

```text
Secret
   |
   v
Protected host file
   |
   v
Read-only container mount
   |
   v
LUMS_SECRET_KEY_FILE
```

## Debian 13

The Debian 13 installation was performed from a fresh Debian installation and successfully tested end-to-end.

Important Debian-specific points were:

* Installation-media repository may remain active.
* Docker must be installed from a suitable Debian repository.
* Numeric GID `10001` may appear as `UNKNOWN` on the host.
* The LUMS secret must still be owned by the correct numeric GID.
* The same Docker entrypoint behavior applies.
* `security_migration.py` must be executed with `--entrypoint python3`.

These are platform or installation details, not changes to the LUMS security model.

---

# 32. Important Entry Point Rule

This is one of the most important details for future installations.

The image has:

```text
/app/docker-entrypoint.sh
```

as its default entrypoint.

That script executes:

```text
init_db.py
```

and then:

```text
gunicorn
```

Therefore this does **not** behave like a normal direct Python invocation:

```bash
lums:latest python3 security_migration.py
```

For direct script execution, use:

```bash
--entrypoint python3
```

and specify the actual path:

```text
/app/server/security_migration.py
```

Correct:

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

This applies equally to Ubuntu and Debian.

---

# 33. Transition to Client Installation

Once the server has passed the checks above, continue with:

```text
Part 2
```

Part 2 covers:

* Client requirements
* Client installation
* TLS trust
* Client tokens
* Bearer authentication
* Token rotation
* Reporting agent
* systemd timer
* Execution watcher
* Watcher timer
* Simulation mode
* Job lifecycle
* Job claiming
* Job recovery
* Package manager safety
* Backup
* Restore
* Verification
* Troubleshooting
* Security checklist
* Current limitations
* Final validation





# LUMS Installation Guide

## Linux Update Management Server

**Part 2 – Client, Execution, Betrieb, Security und Troubleshooting**

---

# 34. Client Requirements

The Linux client requires:

* Python 3
* systemd
* Network connectivity to the LUMS server
* A valid client token
* The LUMS trust certificate
* Permission to query the package manager
* Permission to execute configured update operations

Each client must be configured individually.

Never reuse one client token across multiple independent clients.

---

# 35. Client Directory

Create:

```bash
sudo install -d \
  -o root \
  -g root \
  -m 750 \
  /opt/lums-agent
```

Copy:

```bash
sudo install \
  -o root \
  -g root \
  -m 750 \
  /opt/lums-public/agent/agent.py \
  /opt/lums-agent/agent.py
```

```bash
sudo install \
  -o root \
  -g root \
  -m 750 \
  /opt/lums-public/agent/watcher.py \
  /opt/lums-agent/watcher.py
```

Verify:

```bash
sudo ls -l /opt/lums-agent
```

---

# 36. Client TLS Certificate

Install the trusted certificate:

```bash
sudo install \
  -o root \
  -g root \
  -m 644 \
  /tmp/lums-ca.crt \
  /opt/lums-agent/lums-ca.crt
```

Verify:

```bash
sudo openssl x509 \
  -in /opt/lums-agent/lums-ca.crt \
  -noout \
  -subject \
  -issuer \
  -dates
```

The configured certificate path is:

```text
/opt/lums-agent/lums-ca.crt
```

TLS verification must remain enabled.

---

# 37. Client Configuration

Create:

```bash
sudo touch /etc/default/lums-agent

sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

Configuration:

```dotenv
LUMS_BASE="https://<LUMS_SERVER_NAME_OR_IP>"
LUMS_TOKEN="<CLIENT_TOKEN>"
LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt"
```

Verify:

```bash
sudo stat \
  -c '%U:%G %a %n' \
  /etc/default/lums-agent
```

Expected:

```text
root:root 600 /etc/default/lums-agent
```

Never print the complete client token during troubleshooting.

---

# 38. Bearer Authentication

The agent communicates using a Bearer token:

```text
Authorization: Bearer <CLIENT_TOKEN>
```

Tokens must be:

* Unique per client
* Stored securely
* Protected from unauthorized access
* Revocable
* Excluded from Git
* Excluded from public documentation

Protected operations include:

* Client reports
* Pending jobs
* Running jobs
* Job claiming
* Job status retrieval
* Job result submission
* Interrupted-job recovery

The server validates authentication and authorization.

A valid token does not automatically grant access to another client's data.

---

# 39. Client Token Lifecycle

The current lifecycle is:

```text
Generate
   |
   v
Hash
   |
   v
Store hash
   |
   v
Authenticate
   |
   v
Rotate
   |
   v
Invalidate previous token
   |
   v
Issue replacement
   |
   v
Update agent
   |
   v
Verify communication
```

Tokens are generated using cryptographically secure randomness.

The current generation method uses:

```python
secrets.token_urlsafe(32)
```

The stored representation is a SHA-256 hexadecimal digest.

The plaintext token is not stored in the database.

---

# 40. Client Token Rotation

Administrators can rotate a client token through the application.

The rotation workflow:

1. Finds the client.
2. Generates a new token.
3. Hashes the token.
4. Replaces the stored token hash.
5. Updates `token_created_at`.
6. Clears the previous revocation timestamp.
7. Creates an audit event.
8. Returns the new token once.

The previous token becomes invalid immediately.

The new token must be stored securely and then installed on the client.

---

# 41. Client Token Rotation Verification

The rotation workflow has been tested.

The expected lifecycle is:

```text
Token A
   |
   v
Authenticated
   |
   v
Rotate
   |
   v
Token B
```

After rotation:

```text
Token A -> rejected
Token B -> accepted
```

Negative tests include:

```text
No administrator session
    -> rejected

Administrator session without CSRF
    -> rejected

Unknown client
    -> rejected
```

The audit log must not contain the plaintext token.

---

# 42. Reporting Agent

Create:

```bash
sudo tee /etc/systemd/system/lums-agent.service > /dev/null <<'EOF'
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
EOF
```

Reload:

```bash
sudo systemctl daemon-reload
```

Run manually:

```bash
sudo systemctl start lums-agent.service
```

Check:

```bash
sudo systemctl status lums-agent.service --no-pager
```

Logs:

```bash
sudo journalctl \
  -u lums-agent.service \
  -n 100 \
  --no-pager
```

A `Type=oneshot` service normally becomes:

```text
inactive (dead)
```

after successful completion.

That is expected.

---

# 43. Reporting Timer

Create:

```bash
sudo tee /etc/systemd/system/lums-agent.timer > /dev/null <<'EOF'
[Unit]
Description=LUMS Linux Update Management Agent Timer
After=network-online.target
Wants=network-online.target

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true
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
systemctl status lums-agent.timer --no-pager
```

List timers:

```bash
systemctl list-timers --all | grep lums
```

The reporting interval is approximately:

```text
5 minutes
```

The reporting timer and execution watcher are separate.

---

# 44. Execution Watcher Service

Create:

```bash
sudo tee /etc/systemd/system/lums-execution-watcher.service > /dev/null <<'EOF'
[Unit]
Description=LUMS Execution Watcher
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/lums-agent/watcher.py
EnvironmentFile=-/etc/default/lums-agent
EOF
```

Reload:

```bash
sudo systemctl daemon-reload
```

The permanent service must not contain simulation mode.

Do not permanently add:

```ini
Environment=LUMS_SIMULATE_UPDATES=1
```

---

# 45. Execution Watcher Timer

Create:

```bash
sudo tee /etc/systemd/system/lums-execution-watcher.timer > /dev/null <<'EOF'
[Unit]
Description=LUMS Execution Watcher Timer
After=network-online.target
Wants=network-online.target

[Timer]
OnBootSec=30s
OnUnitActiveSec=30s
Persistent=true
Unit=lums-execution-watcher.service

[Install]
WantedBy=timers.target
EOF
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lums-execution-watcher.timer
```

Check:

```bash
systemctl status lums-execution-watcher.timer --no-pager
```

List:

```bash
systemctl list-timers --all | grep lums
```

The watcher runs approximately every:

```text
30 seconds
```

---

# 46. Manual Watcher Execution

Run:

```bash
sudo systemctl start lums-execution-watcher.service
```

Check:

```bash
sudo systemctl status \
  lums-execution-watcher.service \
  --no-pager
```

Logs:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 100 \
  --no-pager
```

A successful oneshot service may show:

```text
inactive (dead)
```

after completion.

That is expected.

---

# 47. Simulation Mode

Simulation mode is intended for controlled testing without changing installed packages.

Enable temporarily:

```bash
sudo systemctl edit --runtime \
  lums-execution-watcher.service
```

Add:

```ini
[Service]
Environment=LUMS_SIMULATE_UPDATES=1
```

Run:

```bash
sudo systemctl start \
  lums-execution-watcher.service
```

Inspect:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 100 \
  --no-pager
```

Remove the runtime override:

```bash
sudo systemctl revert --runtime \
  lums-execution-watcher.service

sudo systemctl daemon-reload
```

Verify:

```bash
sudo systemctl cat \
  lums-execution-watcher.service
```

Simulation mode must not remain enabled unintentionally.

---

# 48. Job Lifecycle

The current lifecycle is:

```text
pending
   |
   v
running
   |
   +----------+----------+------------+
   |          |          |            |
   v          v          v            v
success    partial     failed     abandoned
```

The watcher must not execute a job simply because it is visible as pending.

The workflow is:

```text
Find pending job
      |
      v
Verify client
      |
      v
Check idle state
      |
      v
Attempt atomic claim
      |
      v
Confirm claim
      |
      v
Execute
      |
      v
Submit result
```

---

# 49. Job Claiming

Job claiming is atomic.

This prevents multiple workers or repeated timer executions from processing the same job simultaneously.

The watcher must verify:

* Client identity
* Job ownership
* Job state
* Idle state
* Claim success

If another process claims the job first, the current watcher must not execute it.

---

# 50. Job Recovery

A job may remain in `running` if:

* The client loses power
* The watcher is terminated
* The network connection fails
* The operating system reboots
* The package manager crashes
* Result submission fails

LUMS provides controlled recovery for interrupted jobs.

The recovery workflow:

1. Verify the job exists.
2. Verify authenticated client ownership.
3. Permit recovery only from `running`.
4. Change the job to `abandoned`.
5. Record `finished_at`.
6. Record a recovery reason.
7. Write update history.
8. Preserve package statistics.
9. Prevent the agent from continuing blindly if recovery fails.

The agent does not claim a new job when recovery fails.

---

# 51. Job Recovery Verification

A controlled recovery test was performed using an artificial running job.

Verified:

```text
status:
    abandoned

finished_at:
    populated

recovery_reason:
    Agent did not submit a final result.

update_history:
    abandoned

package count:
    preserved

successful:
    0

failed:
    0

reboot:
    not required
```

Synthetic test data must be removed after testing.

A real update job should subsequently be verified independently.

---

# 52. Package Manager Safety

Complete package-manager collision prevention is not fully implemented.

The current custom LUMS lock does not automatically force arbitrary external APT or dpkg commands to honor the lock.

Possible situation:

```text
LUMS watcher starts an operation
        +
User manually runs apt or dpkg
        =
Potential package manager collision
```

Possible future improvements:

* Explicit APT/dpkg lock checks
* Detection of active package-manager processes
* Deferral when package manager is busy
* Stronger execution coordination
* Better recovery handling
* Clear user-facing status
* Additional audit events

Update execution should continue to be tested in controlled environments until stronger coordination has been implemented and validated.

---

# 53. Backup Strategy

The LUMS database is stored in:

```text
lums-data
```

Backups should be created before:

* Application updates
* Database migrations
* Authentication changes
* Destructive maintenance
* Restore tests
* Architectural changes
* Production container recreation

Create:

```bash
sudo mkdir -p /var/backups/lums
sudo chmod 700 /var/backups/lums
```

A backup must be verified before the original database is replaced or removed.

---

# 54. SQLite-Aware Backup

A SQLite-aware backup is preferred over copying an active database file directly.

Example:

```bash
sudo docker run --rm \
  --entrypoint python3 \
  -v lums-data:/var/lib/lums:ro \
  -v /var/backups/lums:/backup \
  lums:latest \
  -c '
import sqlite3

source = sqlite3.connect("/var/lib/lums/lums.db")
target = sqlite3.connect("/backup/lums.db.backup")

with target:
    source.backup(target)

target.close()
source.close()

print("SQLite backup completed")
'
```

Protect:

```bash
sudo chmod 600 \
  /var/backups/lums/lums.db.backup
```

Verify:

```bash
sudo ls -lh \
  /var/backups/lums/lums.db.backup
```

---

# 55. Backup Verification

Verify:

```bash
sudo docker run --rm \
  -v /var/backups/lums:/backup:ro \
  lums:latest \
  python3 -c '
import sqlite3

db = sqlite3.connect(
    "file:/backup/lums.db.backup?mode=ro",
    uri=True
)

result = db.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

print("Integrity check:", result)

db.close()
'
```

Expected:

```text
Integrity check: ok
```

An integrity check does not replace a complete restore test.

---

# 56. Restore

A restore must not be performed while the production container is actively writing to the database.

Before restoring:

1. Confirm the correct backup.
2. Stop the LUMS container.
3. Preserve the current database.
4. Restore the backup.
5. Start the container.
6. Check logs.
7. Verify authentication.
8. Verify clients and jobs.
9. Perform an integrity check.

Example:

```bash
sudo docker stop lums
```

Do not overwrite the production database without a safety copy.

The current SQLite backup mechanism has been verified.

A complete isolated full restore test remains outstanding.

---

# 57. Service Verification

Check:

```bash
systemctl status \
  lums-agent.service \
  --no-pager
```

```bash
systemctl status \
  lums-agent.timer \
  --no-pager
```

```bash
systemctl status \
  lums-execution-watcher.service \
  --no-pager
```

```bash
systemctl status \
  lums-execution-watcher.timer \
  --no-pager
```

List timers:

```bash
systemctl list-timers --all | grep lums
```

Agent logs:

```bash
sudo journalctl \
  -u lums-agent.service \
  -n 100 \
  --no-pager
```

Watcher logs:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 100 \
  --no-pager
```

The agent and watcher must be validated independently.

---

# 58. Network Verification

Test HTTPS:

```bash
curl \
  --cacert /opt/lums-agent/lums-ca.crt \
  https://<LUMS_SERVER_NAME_OR_IP>/
```

Test TLS:

```bash
openssl s_client \
  -connect <LUMS_SERVER_NAME_OR_IP>:443 \
  -servername <SERVER_NAME> \
  -CAfile /opt/lums-agent/lums-ca.crt
```

Do not disable TLS verification permanently.

Avoid:

```bash
curl -k
```

in production automation.

`curl -k` is suitable only for controlled diagnostics.

---

# 59. Manual Agent Test

Run:

```bash
sudo /usr/bin/python3 \
  /opt/lums-agent/agent.py
```

The agent should:

* Load configuration
* Contact the server
* Authenticate
* Collect client information
* Submit the report
* Return a clear result

A successful report does not confirm that the execution watcher works.

---

# 60. Successful Agent Test

A successful test resembles:

```text
AGENT 1.x.x
HOST <hostname>
OS Linux
ARCH <architecture>
KERNEL <kernel>

REPORT Sending system report...

✓ REPORT ACCEPTED
✓ CLIENT AUTHENTICATED
✓ NO UPDATE JOB

LUMS // Agent cycle complete.
```

The exact agent version and package counts depend on the installed repository version and client system.

---

# 61. Troubleshooting Strategy

Troubleshoot layer by layer:

```text
Layer 1: Client operating system
Layer 2: Python and local files
Layer 3: Client configuration
Layer 4: TLS certificate trust
Layer 5: Network connectivity
Layer 6: Nginx
Layer 7: Docker container
Layer 8: Gunicorn
Layer 9: Flask application
Layer 10: Authentication
Layer 11: Authorization
Layer 12: Database
Layer 13: Update job workflow
Layer 14: Package manager execution
```

Do not reinstall everything immediately.

First identify the failing layer.

Recommended workflow:

```text
Observe
   |
   v
Understand
   |
   v
Change one layer
   |
   v
Test
   |
   v
Document
   |
   v
Deploy
```

---

# 62. Common Problems

## 62.1 Agent Returns 401

Possible causes:

* Invalid client token
* Incorrect token hash
* Incorrect Authorization header
* Missing Bearer prefix
* Incorrect server URL
* Client disabled
* Token revoked
* Token replaced

Check permissions:

```bash
sudo stat \
  -c '%U:%G %a %n' \
  /etc/default/lums-agent
```

Check logs:

```bash
sudo journalctl \
  -u lums-agent.service \
  -n 100 \
  --no-pager
```

Never print the complete token.

---

## 62.2 TLS Certificate Error

Possible causes:

* Wrong certificate
* Incorrect certificate path
* Expired certificate
* Hostname mismatch
* Missing SAN
* Wrong server certificate
* Certificate not installed

Check:

```bash
sudo openssl x509 \
  -in /opt/lums-agent/lums-ca.crt \
  -noout \
  -subject \
  -issuer \
  -dates
```

Do not disable certificate verification permanently.

---

## 62.3 Nginx Returns 502

Possible causes:

* Container stopped
* Gunicorn stopped
* Wrong proxy port
* Missing port mapping
* Container startup failure
* Gunicorn worker failure

Check:

```bash
sudo docker ps
```

```bash
sudo docker logs --tail 100 lums
```

```bash
curl -I http://127.0.0.1:5050
```

```bash
sudo nginx -t
```

```bash
sudo journalctl \
  -u nginx \
  -n 100 \
  --no-pager
```

---

## 62.4 Gunicorn Does Not Start

Check:

```bash
sudo docker logs --tail 100 lums
```

Expected:

```text
Starting gunicorn 23.0.0
Listening at: http://0.0.0.0:5000
Booting worker
```

Possible causes:

* Python import error
* Missing dependency
* Invalid configuration
* Missing secret
* Incorrect permissions
* Database initialization failure

Check:

```bash
sudo docker exec lums sh -c '
echo "LUMS_SECRET_KEY_FILE=${LUMS_SECRET_KEY_FILE}"

if [ -r /run/secrets/lums_secret ]; then
    echo "SECRET_FILE=READABLE"
else
    echo "SECRET_FILE=NOT_READABLE"
fi
'
```

Never print the secret.

---

## 62.5 Watcher Does Not Execute a Job

Possible causes:

* No pending job
* Invalid client token
* Idle detection unsupported
* Idle threshold not reached
* Job already claimed
* Job not assigned
* Package manager busy
* Watcher not running
* Invalid job state

Check:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 100 \
  --no-pager
```

Check:

```bash
systemctl status \
  lums-execution-watcher.timer
```

Check idle state:

```bash
w -h
```

---

## 62.6 Job Remains Running

Possible causes:

* Client shutdown
* Watcher interruption
* Network failure
* Package manager still running
* Result submission failure

Check:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  --since "1 hour ago" \
  --no-pager
```

Use the supported recovery workflow.

Do not manually mark a job successful without verifying the package operation.

---

## 62.7 Agent Reports Successfully but No Job Executes

Reporting and execution are separate.

Check:

```bash
systemctl status \
  lums-execution-watcher.timer
```

Run:

```bash
sudo systemctl start \
  lums-execution-watcher.service
```

Inspect:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 100 \
  --no-pager
```

---

## 62.8 Frontend Changes Are Not Visible

If frontend changes are not visible:

```text
1. Check Git source.
2. Build Docker image.
3. Recreate container.
4. Check container logs.
5. Test localhost.
6. Reload browser.
7. Check browser cache.
```

For theme-related problems:

```javascript
localStorage.getItem("lums-theme");
```

and:

```javascript
document.documentElement.dataset.theme;
```

Frontend files are part of the Docker image.

Changing the repository does not automatically change an already-running container.

---

# 63. Security Checklist

## Server

* [x] Docker container is not publicly exposed on port 5000
* [x] Host proxy port is bound to localhost
* [x] Nginx provides HTTPS
* [x] TLS private key is protected
* [x] Firewall rules have been reviewed
* [x] SSH access is preserved
* [x] Environment files are not committed
* [x] Database volume is persistent
* [x] SQLite-aware backups are implemented
* [x] Backup integrity verification works
* [x] Logs do not intentionally expose secrets
* [x] Production WSGI server is integrated
* [x] Gunicorn has been validated
* [x] Container runs as non-root
* [x] All Linux capabilities are dropped
* [x] Root filesystem is read-only
* [x] Secret is supplied through protected mounted file
* [x] Secret mount is read-only
* [x] Production secret rotation is complete
* [ ] Full backup/restore test

## Client

* [x] Client token is unique
* [x] Client configuration is owned by root
* [x] Client configuration has mode 600
* [x] TLS certificate is installed
* [x] TLS verification is enabled
* [x] Agent files are owned by root
* [x] Watcher files are owned by root
* [x] Simulation mode is disabled after testing
* [x] Client token rotation has been tested
* [x] Replacement token has been verified
* [ ] Complete update execution hardening

## Application

* [x] Bearer authentication is enforced
* [x] Authorization is checked
* [x] Job claiming is atomic
* [x] Job results are validated
* [x] Job ownership is validated
* [x] Interrupted-job recovery is implemented
* [x] Recovery ownership is validated
* [x] Audit events are recorded
* [x] Client token rotation is audited
* [x] Tokens are not written to audit logs
* [x] Database access is protected
* [x] Security headers are present
* [ ] Automated security regression tests
* [ ] Final security review

---

# 64. Current Limitations

## 64.1 Idle Detection

The current idle detection uses:

```text
w -h
```

It is primarily suitable for terminal, server, and SSH-oriented environments.

It is not a universal desktop idle detection mechanism.

---

## 64.2 Package Manager Coordination

Complete collision prevention between LUMS and arbitrary user-issued APT or dpkg commands is not fully implemented.

The custom LUMS lock does not force every external package manager process to honor it.

---

## 64.3 Full Backup Restore Test

SQLite-aware backup and integrity verification are implemented.

A complete isolated backup/restore test remains outstanding.

---

## 64.4 SQLite Scaling

SQLite is suitable for the current project scope and laboratory development.

Larger deployments may require a different database architecture depending on:

* Number of clients
* Job volume
* Concurrent requests
* Audit log size
* Backup requirements
* High availability requirements

---

## 64.5 Self-Signed Certificates

Self-signed certificates require explicit trust configuration.

They are suitable for controlled laboratory environments but may not be appropriate for every deployment scenario.

---

## 64.6 Administrative Roles

LUMS currently uses a single administrator-oriented authentication model.

A full role-based administrative authorization model has not yet been implemented.

---

## 64.7 Token Expiration

Client token rotation is implemented and verified.

Token expiration and a more advanced token lifecycle remain possible future enhancements.

---

# 65. Recommended Development Priorities

Remaining areas include:

1. Complete update execution hardening.
2. Improve package manager collision prevention.
3. Improve watcher recovery and timeout behavior.
4. Improve desktop idle detection support.
5. Complete full backup and restore testing.
6. Add automated integration tests.
7. Add security regression tests.
8. Improve API documentation.
9. Add structured logging.
10. Add monitoring and alerting.
11. Review the complete update execution workflow before production use.
12. Perform the final security review.

Already implemented controls include:

```text
Non-root container
Drop ALL capabilities
Read-only root filesystem
Secret isolation
Production secret rotation
Client token lifecycle
Client token rotation
Interrupted-job recovery
Production frontend deployment
Production client communication
```

---

# 66. Final Validation

Run:

```bash
sudo docker ps
```

```bash
sudo docker logs --tail 100 lums
```

```bash
sudo docker inspect lums \
  --format 'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{json .HostConfig.CapDrop}} Privileged={{.HostConfig.Privileged}}'
```

```bash
sudo nginx -t
```

```bash
systemctl status nginx --no-pager
```

```bash
curl -I http://127.0.0.1:5050/
```

```bash
curl -k -I https://<LUMS_SERVER_NAME_OR_IP>/
```

```bash
systemctl status lums-agent.timer
```

```bash
systemctl status lums-execution-watcher.timer
```

```bash
systemctl list-timers --all | grep lums
```

```bash
sudo journalctl \
  -u lums-agent.service \
  -n 50 \
  --no-pager
```

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 50 \
  --no-pager
```

Verify:

* HTTPS is accessible
* LUMS container is running
* Gunicorn is running
* Database volume is mounted
* Agent can report
* Watcher can reach the server
* Authentication works
* Client authorization works
* Pending jobs are visible
* Job claiming is atomic
* Interrupted-job recovery works
* Simulation mode is disabled
* Backups exist
* Backup integrity can be verified
* No sensitive data is present in Git
* Container runs as non-root
* ALL Linux capabilities are dropped
* Root filesystem is read-only
* `/tmp` uses tmpfs
* Secret is loaded from `/run/secrets/lums_secret`
* `LUMS_SECRET_KEY` is absent
* Secret mount is read-only

Only mark a component as validated after an actual successful test.

---

# 67. Operational Principle

LUMS should be developed and operated with controlled changes.

Preferred workflow:

```text
Observe
   |
   v
Understand
   |
   v
Change one layer
   |
   v
Test
   |
   v
Verify
   |
   v
Document
   |
   v
Deploy
   |
   v
Verify again
```

The goal is not to hide complexity.

The goal is to make complexity visible, manageable, and auditable.

---

# 68. Security Hardening Principle

LUMS security improvements are implemented incrementally.

Current workflow:

```text
Inspect
   |
   v
Design
   |
   v
Test
   |
   v
Verify
   |
   v
Production
   |
   v
Verify
   |
   v
Document
```

Current security architecture:

```text
Internet / LAN
      |
      v
   Nginx
   HTTPS
      |
      v
127.0.0.1:5050
      |
      v
 Docker
 +------------------------------+
 | non-root                     |
 | UID 10001                    |
 | capabilities: NONE           |
 | root filesystem: READ-ONLY   |
 |                              |
 | /tmp -> tmpfs                |
 | /var/lib/lums -> lums-data   |
 | /run/secrets/lums_secret     |
 |          -> READ-ONLY        |
 |                              |
 | Gunicorn -> Flask            |
 +------------------------------+
      |
      v
   SQLite
```

The following security controls have been verified:

```text
[x] Non-root container
[x] Drop ALL capabilities
[x] Read-only root filesystem
[x] Secret isolation
[x] Production secret rotation
[x] Client token lifecycle
[x] Client token rotation
[x] Interrupted-job recovery
[x] Production frontend deployment
[x] Production client communication
```

Remaining:

```text
[ ] Update execution hardening
[ ] Full backup / restore test
[ ] Automated security tests
[ ] Final security review
```

---

# 69. Project Statement

LUMS is designed around the following principle:

> Linux Update Management without the noise.

The project combines centralized reporting, controlled update jobs, idle-aware execution, auditable recovery, and security-oriented infrastructure practices.

The architecture deliberately separates:

```text
Management Plane
       |
       +-- Nginx
       +-- Gunicorn
       +-- Flask
       +-- Authentication
       +-- Authorization
       +-- Database
```

from:

```text
Execution Plane
       |
       +-- lums-agent
       +-- Execution Watcher
       +-- APT / dpkg
```

The system remains under active development.

All production-oriented functionality must be tested, reviewed, and documented before being considered reliable for critical environments.

> **One LUMS. Controlled updates. Auditable execution.**

---

**LUMS**

**Linux Update Management without the noise.**

