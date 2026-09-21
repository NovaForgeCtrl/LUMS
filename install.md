# LUMS Installation Guide

## Linux Update Management Server

**Version:** 2.4
**Project:** LUMS
**Slogan:** Linux Update Management without the noise.

---

## 1. Overview

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

### Current deployment status

The following components have been tested in the laboratory and production-like deployment:

* Docker image build
* Persistent Docker database volume
* Database initialization
* Security migration
* Administrator account creation
* Flask application startup
* Gunicorn application startup
* Local HTTP connectivity
* Nginx reverse proxy
* HTTPS connectivity
* Security response headers
* Linux agent installation
* Client token authentication
* Client token rotation
* Client system reporting
* Client database synchronization
* systemd reporting timer
* Interrupted-job recovery
* Non-root Docker execution
* Linux capability removal
* Read-only container root filesystem
* Protected secret-file deployment
* Production Flask secret rotation
* Production frontend deployment

The complete update execution hardening, full backup/restore test, automated security regression tests, and final security review remain separate development tasks.

---

## 2. Architecture

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
                    |  +----------------+  |
                    |  | LUMS Container  |  |
                    |  |                 |  |
                    |  | Gunicorn        |  |
                    |  | Flask :5000     |  |
                    |  +--------+-------+  |
                    |           |          |
                    |  +--------v-------+  |
                    |  | SQLite Volume  |  |
                    |  | lums-data      |  |
                    |  +----------------+  |
                    +----------------------+
                               |
                 HTTPS / Bearer Authentication
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

### Container startup

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

### Network flow

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

## 3. Main Components

### 3.1 LUMS Server

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

### 3.2 Nginx Reverse Proxy

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

### 3.3 Linux Agent

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

### 3.4 Execution Watcher

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

## 4. Current Execution Model

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

## 5. Job States

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

### 5.1 Pending

The job has been created but has not yet been claimed.

### 5.2 Running

The job has been claimed and is currently being processed.

### 5.3 Success

The job completed successfully.

### 5.4 Partial

The job completed with some operations succeeding and others failing.

### 5.5 Failed

The job could not be completed successfully.

### 5.6 Abandoned

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

Only implemented and tested states should be considered production-ready.

---

## 6. Repository Structure

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

A Docker Compose file is not required by the current tested deployment procedure.

---

## 7. Server Requirements

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

## 8. Directory Layout

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

## 9. Clone or Update the Repository

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

Review changes before deploying:

```bash
git log --oneline --decorate -5
git diff HEAD~1..HEAD
```

Check for whitespace problems:

```bash
git diff --check
```

Do not deploy unreviewed changes directly into a production-like environment.

---

## 10. Docker Environment Configuration

The current production deployment does not store the Flask secret in the normal Docker environment file.

The environment file contains non-secret configuration such as:

```text
FLASK_ENV=production
LUMS_DB_PATH=/var/lib/lums/lums.db
```

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
sudo touch /etc/lums/docker/lums.env

sudo chown root:root /etc/lums/docker/lums.env
sudo chmod 600 /etc/lums/docker/lums.env
```

Example:

```bash
sudo tee /etc/lums/docker/lums.env > /dev/null <<'EOF'
FLASK_ENV=production
LUMS_DB_PATH=/var/lib/lums/lums.db
EOF
```

Set the permissions:

```bash
sudo chown root:root /etc/lums/docker/lums.env
sudo chmod 600 /etc/lums/docker/lums.env
```

### Important

The Flask secret must not be placed in:

```text
LUMS_SECRET_KEY
```

for the production deployment.

The current production architecture uses:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

The secret is stored on the host at:

```text
/etc/lums/secrets/lums_secret
```

The application receives it through a read-only Docker bind mount.

---

## 11. Flask Secret File

Create the protected secret directory:

```bash
sudo install -d \
  -o root \
  -g root \
  -m 700 \
  /etc/lums/secrets
```

Generate a new secret:

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

The secret must never be:

* committed to Git,
* printed to logs,
* included in screenshots,
* pasted into documentation,
* exposed through `docker inspect`,
* stored in the normal Docker environment.

---

## 12. Docker Image

Build the Docker image:

```bash
cd /opt/lums-public

sudo docker build -t lums:latest .
```

Verify the image:

```bash
sudo docker image ls lums
```

The current Dockerfile:

* Uses Python 3.13 Slim
* Installs server requirements
* Installs Gunicorn
* Creates the non-root `lums` user
* Copies the server application
* Copies `docker-entrypoint.sh`
* Creates `/var/lib/lums`
* Uses port 5000 inside the container
* Starts through the entrypoint
* Runs the application as `lums`

The entrypoint performs:

```text
Database initialization
        ↓
Gunicorn startup
```

### Current build

The production image is expected to use the tested Docker image configuration.

Before deployment, verify:

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

## 13. Docker Volume

Create the persistent volume:

```bash
sudo docker volume create lums-data
```

List volumes:

```bash
sudo docker volume ls
```

Inspect the volume:

```bash
sudo docker volume inspect lums-data
```

The volume contains persistent application data.

### Important

Never delete the database volume during ordinary deployment or troubleshooting.

Do not execute:

```bash
sudo docker volume rm lums-data
```

unless:

* A complete backup exists.
* The backup has been verified.
* Data destruction is explicitly intended.

The persistent volume is independent from the Docker image.

Recreating the container must preserve:

```text
lums-data
```

---

## 14. Database Initialization

The current Docker container initializes the database through:

```text
/app/docker-entrypoint.sh
```

The entrypoint executes:

```text
python3 /app/server/init_db.py
```

before starting Gunicorn.

The initialization therefore occurs automatically during container startup.

The database is stored at:

```text
/var/lib/lums/lums.db
```

inside the persistent volume.

### Security migration

The security migration creates or updates:

* User records
* Audit logging
* Schema migration tracking
* Client token fields
* Client enablement fields
* Token creation timestamps
* Token revocation timestamps

On a completely fresh installation, the security migration may need to be performed separately.

Example:

```bash
sudo docker run --rm -it \
  --env-file /etc/lums/docker/lums.env \
  -v lums-data:/var/lib/lums \
  lums:latest \
  python3 security_migration.py \
  --admin-username admin
```

The command requests the administrator password interactively.

Do not place the administrator password in the repository or environment file.

### Validation

Verify that:

* The migration completes successfully.
* The administrator account exists.
* The database is stored in the persistent volume.
* The migration is not repeatedly applied unnecessarily.
* The container can restart without losing the database.

---

## 15. Starting the LUMS Container

The current hardened production configuration is:

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

This provides:

```text
Non-root container
+
All Linux capabilities dropped
+
Read-only root filesystem
+
Writable /tmp through tmpfs
+
Persistent database volume
+
Read-only secret mount
+
Localhost-only application binding
```

Check the container:

```bash
sudo docker ps -a --filter name=lums
```

Check the logs:

```bash
sudo docker logs --tail 100 lums
```

Follow the logs:

```bash
sudo docker logs -f lums
```

Inspect the container:

```bash
sudo docker inspect lums
```

### Expected startup

The logs should contain:

```text
=== LUMS database initialization ===
LUMS-Datenbank aktualisiert
=== Starting Gunicorn ===
Starting gunicorn 23.0.0
Listening at: http://0.0.0.0:5000
Booting worker
```

The application must run as:

```text
lums
UID 10001
```

---

## 16. Container Hardening Verification

Verify the container user:

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

Verify secret configuration:

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

---

## 17. Application Verification

Test the local HTTP endpoint:

```bash
curl -i http://127.0.0.1:5050/
```

Expected behavior:

```text
HTTP/1.1 302 FOUND
Location: /login
```

Test the login page:

```bash
curl -i http://127.0.0.1:5050/login
```

The response should contain:

* HTTP 200
* Login form
* CSRF token
* Security response headers
* Session cookie

The application is served by Gunicorn.

The Flask development server is no longer part of the current deployment.

---

## 18. TLS Certificate Directory

Create the TLS directory:

```bash
sudo install -d \
  -o root \
  -g root \
  -m 750 \
  /etc/lums/tls
```

Expected files:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Set ownership and permissions:

```bash
sudo chown root:root /etc/lums/tls/lums.crt
sudo chown root:root /etc/lums/tls/lums.key

sudo chmod 644 /etc/lums/tls/lums.crt
sudo chmod 600 /etc/lums/tls/lums.key
```

The private key must never be committed to Git.

---

## 19. Laboratory TLS Certificate

The laboratory deployment uses a self-signed certificate.

Replace the placeholders with environment-specific values:

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

Verify the certificate:

```bash
sudo openssl x509 \
  -in /etc/lums/tls/lums.crt \
  -noout \
  -subject \
  -issuer \
  -dates
```

### Certificate limitation

Self-signed certificates are suitable for controlled laboratory environments.

Clients must explicitly trust the correct certificate or certificate authority.

The certificate must contain a valid Subject Alternative Name for the hostname or IP address used by the client.

For broader deployments, use an appropriate internal or public certificate authority.

---

## 20. Nginx Configuration

Check the existing configuration before making changes:

```bash
sudo nginx -T
```

Create the LUMS site configuration:

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

Enable the configuration:

```bash
sudo ln -s \
  /etc/nginx/sites-available/lums \
  /etc/nginx/sites-enabled/lums
```

Test the configuration:

```bash
sudo nginx -t
```

Reload Nginx:

```bash
sudo systemctl reload nginx
```

Check the service:

```bash
sudo systemctl status nginx --no-pager
```

### Validation

Test HTTPS:

```bash
curl -k -I https://<SERVER_NAME_OR_IP>/
```

The `-k` option disables certificate verification and should only be used for controlled diagnostics.

Do not use `curl -k` as a permanent solution in production automation.

---

## 21. Security Headers

Verify HTTPS response headers:

```bash
curl -k -I \
  https://<SERVER_NAME_OR_IP>/
```

The current deployment provides:

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

These headers must remain present after deployment changes.

---

## 22. Firewall Configuration

Review existing firewall rules before making changes.

Install UFW if required:

```bash
sudo apt update
sudo apt install -y ufw
```

Allow SSH before enabling the firewall:

```bash
sudo ufw allow <SSH_PORT>/tcp
```

Allow HTTP and HTTPS:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

Review the rules:

```bash
sudo ufw status verbose
```

Enable the firewall only after verifying required access:

```bash
sudo ufw enable
```

Do not expose these ports externally:

```text
5000
5050
```

The Flask/Gunicorn application should only be reachable through the Nginx reverse proxy.

---

## 23. Client Requirements

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

## 24. Client Directory

Create the agent directory:

```bash
sudo install -d \
  -o root \
  -g root \
  -m 750 \
  /opt/lums-agent
```

Copy the agent files:

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

The files must be reviewed and tested before update execution is enabled.

---

## 25. Client TLS Certificate

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

The certificate must correspond to the trusted server certificate or certificate authority.

---

## 26. Client Configuration

Create the configuration file:

```bash
sudo touch /etc/default/lums-agent

sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

Example:

```dotenv
LUMS_BASE="https://<LUMS_SERVER_NAME_OR_IP>"
LUMS_TOKEN="<CLIENT_TOKEN>"
LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt"
```

Verify permissions:

```bash
sudo stat \
  -c '%U:%G %a %n' \
  /etc/default/lums-agent
```

Expected result:

```text
root:root 600 /etc/default/lums-agent
```

Never display the complete client token during troubleshooting.

---

## 27. Bearer Authentication

The agent communicates with the server using a Bearer token.

Expected HTTP header:

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

The server validates authentication on protected client endpoints.

Authorization verifies that an authenticated client can only access its own client-specific data and jobs.

Protected operations include:

* Client reports
* Pending jobs
* Running jobs
* Job claiming
* Job status retrieval
* Job result submission
* Interrupted-job recovery

---

## 28. Client Token Lifecycle

Client tokens are treated as credentials.

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

## 29. Client Token Rotation

Administrators can rotate a client token through:

```text
POST /api/clients/<client_id>/token/rotate
```

The endpoint requires:

```text
Administrator session
+
CSRF validation
```

The rotation process:

1. Finds the client.
2. Generates a new token.
3. Hashes the token.
4. Replaces the stored token hash.
5. Updates `token_created_at`.
6. Clears the previous revocation timestamp.
7. Creates an audit event.
8. Returns the new token once.

The previous token becomes invalid immediately.

The new token is displayed only after successful rotation.

The frontend provides:

```text
🔐 Token rotieren
```

and:

```text
📋 Token kopieren
```

The interface warns that the token must be stored securely and the LUMS agent must be updated.

---

## 30. Client Token Rotation Verification

The rotation workflow has been tested in an isolated environment.

Verified:

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
Token A → 401
Token B → 200
```

Negative tests verified:

```text
No administrator session
    → 401

Administrator session without CSRF
    → 400

Unknown client
    → 404
```

The audit log records the rotation event without recording the plaintext token.

The frontend rotation button and copy-to-clipboard functionality have also been tested.

---

## 31. Production Token Verification

After the token lifecycle was tested, the production client agent was updated with the replacement token.

The production agent successfully reported:

```text
✓ REPORT ACCEPTED
✓ CLIENT AUTHENTICATED
✓ NO UPDATE JOB
LUMS // Agent cycle complete.
status=0/SUCCESS
```

The client subsequently appeared online again in the LUMS interface.

This confirms the complete operational sequence:

```text
Token rotation
      |
      v
Agent reconfiguration
      |
      v
Authentication
      |
      v
Client reporting
```

---

## 32. Reporting Service

Create the systemd service:

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
sudo systemctl status lums-agent.service --no-pager
```

View logs:

```bash
sudo journalctl \
  -u lums-agent.service \
  -n 100 \
  --no-pager
```

A successful report does not automatically confirm that update execution works.

---

## 33. Reporting Timer

Create the reporting timer:

```bash
sudo tee /etc/systemd/system/lums-agent.timer > /dev/null <<'EOF'
[Unit]
Description=LUMS Linux Update Management Agent Timer

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true
Unit=lums-agent.service

[Install]
WantedBy=timers.target
EOF
```

Enable the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lums-agent.timer
```

Check the timer:

```bash
systemctl status lums-agent.timer --no-pager
```

List scheduled timers:

```bash
systemctl list-timers --all | grep lums
```

The reporting interval is approximately:

```text
5 minutes
```

The reporting timer is separate from update execution.

---

## 34. Execution Watcher Service

Create the watcher service:

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

Reload systemd:

```bash
sudo systemctl daemon-reload
```

The permanent service must not contain simulation mode settings.

Do not add the following permanently:

```ini
Environment=LUMS_SIMULATE_UPDATES=1
```

Simulation mode should only be enabled temporarily for controlled testing.

---

## 35. Execution Watcher Timer

Create the watcher timer:

```bash
sudo tee /etc/systemd/system/lums-execution-watcher.timer > /dev/null <<'EOF'
[Unit]
Description=LUMS Execution Watcher Timer

[Timer]
OnBootSec=30s
OnUnitActiveSec=30s
Unit=lums-execution-watcher.service
Persistent=true

[Install]
WantedBy=timers.target
EOF
```

Enable and start the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lums-execution-watcher.timer
```

Check the timer:

```bash
systemctl status lums-execution-watcher.timer --no-pager
```

List timers:

```bash
systemctl list-timers --all | grep lums
```

The watcher runs approximately every:

```text
30 seconds
```

The exact execution timing depends on systemd scheduling and service runtime.

---

## 36. Manual Watcher Execution

Run the watcher manually:

```bash
sudo systemctl start lums-execution-watcher.service
```

Check the status:

```bash
sudo systemctl status lums-execution-watcher.service --no-pager
```

View logs:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 100 \
  --no-pager
```

Follow the logs:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -f
```

Manual execution is useful for controlled testing and troubleshooting.

---

## 37. Simulation Mode

Simulation mode is intended to test the execution workflow without changing installed packages.

Enable it temporarily:

```bash
sudo systemctl edit --runtime lums-execution-watcher.service
```

Add:

```ini
[Service]
Environment=LUMS_SIMULATE_UPDATES=1
```

Run the watcher:

```bash
sudo systemctl start lums-execution-watcher.service
```

Inspect the logs:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 100 \
  --no-pager
```

Remove the runtime override:

```bash
sudo systemctl revert --runtime lums-execution-watcher.service
sudo systemctl daemon-reload
```

Verify:

```bash
sudo systemctl cat lums-execution-watcher.service
```

Simulation mode still requires:

* Valid client configuration
* Valid client token
* Reachable LUMS server
* Pending update job
* Supported idle detection
* Sufficient idle period

Simulation mode must not be left enabled unintentionally.

---

## 38. Update Job API

The current update job workflow includes client-authenticated operations for:

```text
Client registration
Client reporting
Pending jobs
Running jobs
Job claiming
Job status
Job result submission
Job recovery
```

Representative routes include:

```text
POST /api/report

GET  /api/client/me

GET  /api/clients/<client_id>/update-jobs/pending

GET  /api/clients/<client_id>/update-jobs/running

POST /api/clients/<client_id>/update-jobs/<job_id>/claim

GET  /api/update-jobs/<job_id>

POST /api/update-jobs/<job_id>/result

POST /api/update-jobs/<job_id>/abandon
```

The exact available routes must always be verified against the current application implementation.

Protected routes validate:

* Authentication
* Client identity
* Authorization
* Valid request data
* Valid job ownership

The server must not rely solely on a client-provided ID.

---

## 39. Job Claiming

Job claiming is atomic.

The watcher must not execute a job merely because it appears in a pending-job list.

Expected workflow:

```text
1. Find a pending job
2. Verify client identity
3. Verify idle state
4. Attempt an atomic claim
5. Confirm claim success
6. Execute the job
7. Submit the result
```

If another process claims the job first, the current watcher must not execute it.

This prevents duplicate execution when multiple workers or repeated timer runs are present.

Atomic claim behavior has been tested as part of the current job workflow.

---

## 40. Job Recovery

A job may remain in the `running` state if:

* The client loses power
* The watcher is terminated
* The network connection fails
* The operating system reboots
* The package manager process crashes
* Result submission fails

LUMS now provides controlled recovery for interrupted running jobs.

The recovery endpoint is:

```text
POST /api/update-jobs/<job_id>/abandon
```

The recovery process:

1. Verifies the job exists.
2. Verifies authenticated client ownership.
3. Only permits recovery from `running`.
4. Changes the job to `abandoned`.
5. Records `finished_at`.
6. Records a recovery reason.
7. Writes update history.
8. Preserves package statistics.
9. Prevents the agent from continuing blindly if recovery fails.

The agent does not claim a new job when recovery fails.

---

## 41. Job Recovery Verification

A controlled recovery test was performed using an artificial running job.

The agent detected the interrupted state and performed recovery.

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

The synthetic test data was removed afterwards.

A real update job was subsequently executed successfully.

This confirmed that the recovery mechanism does not prevent normal job execution.

---

## 42. Package Manager Safety

Complete package manager collision prevention is not fully implemented.

The current custom LUMS lock mechanism does not automatically force arbitrary user-issued APT or dpkg commands to honor the lock.

Possible situation:

```text
LUMS watcher starts an operation
        +
User manually runs apt or dpkg
        =
Potential package manager collision
```

Possible future improvements include:

* Explicit APT and dpkg lock checks
* Detection of active package manager processes
* Deferral when the package manager is busy
* Stronger execution coordination
* Better recovery handling
* Clear user-facing status messages
* Additional audit events

Update execution must continue to be tested in a controlled laboratory environment until stronger coordination is implemented and validated.

---

## 43. Backup Strategy

The LUMS database is stored inside the Docker volume:

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

Create the backup directory:

```bash
sudo mkdir -p /var/backups/lums
sudo chmod 700 /var/backups/lums
```

A backup must be verified before the original database is replaced or removed.

---

## 44. SQLite-Aware Backup

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

Protect the backup:

```bash
sudo chmod 600 /var/backups/lums/lums.db.backup
```

Verify the file:

```bash
sudo ls -lh /var/backups/lums/lums.db.backup
```

The backup process should be performed with awareness of concurrent database writes.

---

## 45. Backup Verification

Verify the SQLite backup:

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

Expected result:

```text
Integrity check: ok
```

A successful integrity check does not replace a complete restore test.

The backup should also be restored in an isolated environment.

---

## 46. Restore Considerations

A restore must not be performed while the production container is actively writing to the database.

Before restoring:

1. Confirm the correct backup.
2. Stop the LUMS container.
3. Preserve the current database.
4. Restore the backup.
5. Start the container.
6. Check the application logs.
7. Verify clients, jobs, and authentication.
8. Perform an integrity check.

Example:

```bash
sudo docker stop lums
```

Do not overwrite the production database without creating a safety copy first.

### Current status

The SQLite backup mechanism has been verified successfully.

A complete isolated full restore test remains outstanding.

The restore procedure should therefore not yet be considered fully validated.

---

## 47. Service Verification

Check the LUMS services:

```bash
systemctl status lums-agent.service --no-pager
systemctl status lums-agent.timer --no-pager
systemctl status lums-execution-watcher.service --no-pager
systemctl status lums-execution-watcher.timer --no-pager
```

List timers:

```bash
systemctl list-timers --all | grep lums
```

Check agent logs:

```bash
sudo journalctl \
  -u lums-agent.service \
  -n 100 \
  --no-pager
```

Check watcher logs:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 100 \
  --no-pager
```

The agent and watcher must be validated separately.

---

## 48. Network Verification

Test HTTPS connectivity:

```bash
curl \
  --cacert /opt/lums-agent/lums-ca.crt \
  https://<LUMS_SERVER_NAME_OR_IP>/
```

Test certificate information:

```bash
openssl s_client \
  -connect <LUMS_SERVER_NAME_OR_IP>:443 \
  -servername <SERVER_NAME> \
  -CAfile /opt/lums-agent/lums-ca.crt
```

Do not disable TLS verification as a permanent solution.

Avoid using:

```bash
curl -k
```

in production automation.

The option may be used for controlled diagnostics only.

---

## 49. Manual Agent Test

Run the agent directly:

```bash
sudo /usr/bin/python3 /opt/lums-agent/agent.py
```

The agent should:

* Load the configuration
* Contact the LUMS server
* Authenticate with the client token
* Collect client information
* Submit the report
* Return a clear result

A successful agent report does not confirm that the execution watcher is working.

The reporting and execution workflows must be tested independently.

---

## 50. Troubleshooting Strategy

Troubleshoot LUMS layer by layer:

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

Do not reinstall all components immediately.

First identify the layer where the problem occurs.

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

## 51. Common Problems

### 51.1 Agent Returns 401

Possible causes:

* Invalid client token
* Incorrect token hash
* Incorrect Authorization header
* Missing Bearer prefix
* Incorrect server URL
* Server-side authentication failure
* Client disabled
* Client token revoked or replaced

Check configuration permissions:

```bash
sudo stat \
  -c '%U:%G %a %n' \
  /etc/default/lums-agent
```

Check service logs:

```bash
sudo journalctl \
  -u lums-agent.service \
  -n 100 \
  --no-pager
```

Never print the complete token during troubleshooting.

If the token was intentionally rotated, update the agent with the newly generated token.

---

### 51.2 TLS Certificate Error

Possible causes:

* Wrong CA certificate
* Incorrect certificate path
* Expired certificate
* Hostname mismatch
* Missing Subject Alternative Name
* Incorrect server certificate
* Certificate not installed on the client

Check the configured path:

```bash
grep -E '^LUMS_CA_FILE=' \
  /etc/default/lums-agent
```

Check the certificate:

```bash
sudo openssl x509 \
  -in /opt/lums-agent/lums-ca.crt \
  -noout \
  -subject \
  -issuer \
  -dates
```

Do not disable certificate verification as a permanent fix.

---

### 51.3 Nginx Returns 502

Possible causes:

* Docker container is stopped
* Gunicorn is not running
* Incorrect proxy port
* Missing Docker port mapping
* Container startup failure
* Gunicorn worker startup failure

Check Docker:

```bash
sudo docker ps
```

Check container logs:

```bash
sudo docker logs --tail 100 lums
```

Check the local proxy target:

```bash
curl -I http://127.0.0.1:5050
```

Check Nginx:

```bash
sudo nginx -t

sudo journalctl \
  -u nginx \
  -n 100 \
  --no-pager
```

---

### 51.4 Gunicorn Does Not Start

Check:

```bash
sudo docker logs --tail 100 lums
```

Expected startup includes:

```text
Starting gunicorn 23.0.0
Listening at: http://0.0.0.0:5000
Booting worker
```

Possible causes:

* Python import error
* Missing dependency
* Invalid application configuration
* Missing secret file
* Incorrect permissions
* Database initialization failure

Verify the secret configuration:

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

Never print the secret itself.

---

### 51.5 Watcher Does Not Execute a Job

Possible causes:

* No pending job exists
* Client token is invalid
* Idle detection is unsupported
* Idle threshold has not been reached
* Job has already been claimed
* Job is not assigned to the client
* Package manager is busy
* Watcher is not running
* Job state is invalid

Check watcher logs:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 100 \
  --no-pager
```

Check the timer:

```bash
systemctl status lums-execution-watcher.timer
```

Check idle information:

```bash
w -h
```

The current idle detection is not universal desktop idle detection.

---

### 51.6 Job Remains Running

Possible causes:

* Client shutdown
* Watcher interruption
* Network failure
* Package manager still running
* Result submission failed

Review logs:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  --since "1 hour ago" \
  --no-pager
```

Verify the job state through the LUMS API or web interface.

If the job is genuinely abandoned, use the supported recovery workflow rather than manually changing the database.

Do not manually mark a job successful without verifying the package operation.

---

### 51.7 Agent Reports Successfully but No Job Executes

The reporting agent and execution watcher are separate components.

A successful report only confirms that the reporting workflow completed.

Check the watcher:

```bash
systemctl status lums-execution-watcher.timer
```

Run it manually:

```bash
sudo systemctl start lums-execution-watcher.service
```

Inspect the logs:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 100 \
  --no-pager
```

---

### 51.8 Enterprise / Frontend Changes Are Not Visible

If frontend changes are not visible:

```text
1. Check Git source.
2. Build the Docker image.
3. Recreate the container.
4. Check container logs.
5. Test localhost.
6. Reload the browser.
7. Check browser cache.
```

For theme-related issues also check:

```javascript
localStorage.getItem("lums-theme");
```

and:

```javascript
document.documentElement.dataset.theme;
```

The frontend is part of the Docker image and is not automatically updated inside an already-running container.

---

## 52. Security Checklist

### Server

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

### Client

* [x] Client token is unique
* [x] Client configuration is owned by root
* [x] Client configuration has mode 600
* [x] TLS certificate is installed
* [x] TLS verification is enabled
* [x] Agent files are owned by root
* [x] Watcher files are owned by root
* [x] Simulation mode is disabled after testing
* [x] Client token rotation has been tested
* [x] Replacement token has been verified in production
* [ ] Complete update execution hardening

### Application

* [x] Bearer authentication is enforced on protected client endpoints
* [x] Authorization is checked for client-specific operations
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

## 53. Current Limitations

### 53.1 Idle Detection

The current idle detection uses:

```text
w -h
```

It is primarily suitable for terminal, server, and SSH-oriented environments.

It is not a universal desktop idle detection mechanism.

---

### 53.2 Package Manager Coordination

Complete collision prevention between LUMS and arbitrary user-issued APT or dpkg commands is not fully implemented.

The custom LUMS lock does not force every external package manager process to honor it.

---

### 53.3 Full Backup Restore Test

SQLite-aware backup and integrity verification are implemented.

A complete isolated backup/restore test remains outstanding.

---

### 53.4 SQLite Scaling

SQLite is suitable for the current project scope and laboratory development.

Larger deployments may require a different database architecture depending on:

* Number of clients
* Job volume
* Concurrent requests
* Audit log size
* Backup requirements
* High availability requirements

---

### 53.5 Self-Signed Certificates

Self-signed certificates require explicit trust configuration on clients.

They are suitable for controlled laboratory environments but may not be appropriate for every deployment scenario.

---

### 53.6 Administrative Roles

LUMS currently uses a single administrator-oriented authentication model.

A full role-based administrative authorization model has not yet been implemented.

---

### 53.7 Token Expiration

Client token rotation is implemented and verified.

Token expiration and a more advanced token lifecycle model remain possible future enhancements.

---

### 53.8 Deployment Configuration Consistency

Database path handling must remain consistent across:

* Application code
* Initialization scripts
* Migration scripts
* Backup procedures
* Restore procedures

---

## 54. Recommended Development Priorities

The following areas remain for further development and validation:

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

Already completed security controls should not be treated as unfinished:

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
```

---

## 55. Final Validation

Perform the following validation after installation or an update:

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
* The LUMS container is running
* Gunicorn is running
* The database volume is mounted
* The agent can report
* The watcher can reach the server
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
* `/tmp` is provided through tmpfs
* Secret is loaded from `/run/secrets/lums_secret`
* `LUMS_SECRET_KEY` is absent
* Secret mount is read-only

Only mark a component as validated after an actual successful test.

---

## 56. Operational Principle

LUMS should be developed and operated with controlled changes.

The preferred workflow is:

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

## 57. Security Hardening Principle

LUMS security improvements are implemented incrementally.

The current hardening workflow is:

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

The current verified security architecture is:

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

## 58. Project Statement

LUMS is designed around the following principle:

> Linux Update Management without the noise.

The project combines centralized reporting, controlled update jobs, idle-aware execution, auditable recovery, and security-oriented infrastructure practices.

The current architecture deliberately separates:

```text
Management Plane
       |
       +-- Nginx
       +-- Gunicorn
       +-- Flask
       +-- Authentication
       +-- Authorization
       +-- Database

from

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
