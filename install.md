# LUMS Installation Guide

## Linux Update Management Server

**Version:** 2.3  
**Project:** LUMS  
**Slogan:** Linux Update Management without the noise.

---

## 1. Overview

LUMS is a centralized Linux update management platform designed for controlled update distribution, client reporting, job management, and auditable execution.

The project is intended for laboratory environments, small infrastructures, and future production-oriented development.

LUMS currently includes:

- Flask-based backend
- SQLite database
- Docker deployment
- Nginx reverse proxy
- HTTPS encryption
- Linux client agent
- Separate execution watcher
- Centralized update jobs
- Client status reporting
- Audit logging
- Idle-aware update execution

The project follows this troubleshooting principle:

> Do not reinstall everything immediately. Find the layer where the problem occurs.

### Current deployment status

The following components have been tested in the laboratory deployment:

- Docker image build
- Persistent Docker database volume
- Database initialization
- Security migration
- Administrator account creation
- Flask application startup
- Local HTTP connectivity
- Nginx reverse proxy
- HTTPS connectivity
- Security response headers
- Linux agent installation
- Client token authentication
- Client system reporting
- Client database synchronization
- systemd reporting timer

The execution watcher and complete update execution workflow require separate validation.

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

### Network flow

```text
External HTTPS :443
        |
        v
Nginx
        |
        v
Localhost proxy port
        |
        v
Docker container port 5000
```

The Flask application is not directly exposed to the network.

The Docker host port should be bound to localhost:

```text
127.0.0.1:<HOST_PORT>:5000
```

Ports `5000` and the internal proxy port must not be exposed externally.

---

## 3. Main Components

### 3.1 LUMS Server

The LUMS server provides:

- Web interface
- Client registration
- Client reporting
- Update job creation
- Job state management
- Job claiming
- Job result processing
- Audit logging
- Authentication
- Authorization
- Database access

The Flask application runs inside a Docker container.

The current container starts Flask through its built-in development server.

A production-grade WSGI server has not yet been integrated and validated.

---

### 3.2 Nginx Reverse Proxy

Nginx provides:

- HTTPS termination
- TLS certificate handling
- HTTP-to-HTTPS redirection
- Reverse proxying to Flask
- External access through port 443

The laboratory configuration uses a self-signed TLS certificate.

Self-signed certificates require explicit trust configuration on clients and browsers.

---

### 3.3 Linux Agent

The LUMS agent is responsible for:

- Collecting system information
- Detecting installed packages
- Detecting available updates
- Reporting client status
- Sending data to the LUMS server
- Communicating through Bearer authentication

The reporting agent and execution watcher are separate components.

A successful report does not automatically validate update execution.

---

### 3.4 Execution Watcher

The execution watcher is separated from the reporting agent.

Its intended responsibilities include:

- Checking pending update jobs
- Checking client idle state
- Claiming jobs atomically
- Executing approved jobs
- Recovering interrupted jobs
- Sending execution results
- Reporting execution states

The complete execution workflow must be tested independently before production-oriented use.

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

Idle detection and package manager coordination require additional testing.

---

## 5. Job States

The intended job lifecycle is:

```text
pending
   |
   v
running
   |
   +----------+----------+
   |          |          |
   v          v          v
success    partial     failed
```

Recovery handling may be required when a client or watcher stops while a job is running.

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

### 5.6 Recovery

Interrupted jobs require careful recovery handling.

Recovery logic must prevent:

- Duplicate package operations
- Incorrect success states
- Permanent running jobs
- Unclear audit records

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
├── README.md
└── ...
```

The exact repository structure may change during development.

The Dockerfile currently uses:

```text
python:3.13-slim
```

The server dependencies are defined in:

```text
server/requirements.txt
```

A Docker Compose file is not required by the current tested deployment procedure.

---

## 7. Server Requirements

Recommended requirements:

- Linux operating system
- Docker Engine
- Nginx
- OpenSSL
- UFW or another firewall
- Persistent storage
- Backup storage
- Python tooling inside the Docker image

Docker Compose is optional because the current installation uses:

```text
docker build
docker run
```

The server must have sufficient storage for:

- Docker images
- Application files
- SQLite database
- Logs
- Backups
- TLS certificates

---

## 8. Directory Layout

Recommended directory layout:

```text
/opt/lums-public/
    Git repository

/opt/lums-api/
    Optional deployment-related files

/etc/lums/
├── docker/
│   └── lums.env
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

Do not deploy unreviewed changes directly into a production-like environment.

---

## 10. Docker Environment Configuration

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

Generate a secret key:

```bash
SECRET_KEY=$(python3 -c \
  'import secrets; print(secrets.token_hex(32))')
```

Create the configuration:

```bash
sudo tee /etc/lums/docker/lums.env > /dev/null <<EOF
FLASK_ENV=production
LUMS_SECRET_KEY=${SECRET_KEY}
LUMS_DB_PATH=/var/lib/lums/lums.db
EOF
```

Set the permissions:

```bash
sudo chown root:root /etc/lums/docker/lums.env
sudo chmod 600 /etc/lums/docker/lums.env
```

Remove the secret from the current shell:

```bash
unset SECRET_KEY
```

Never print or publish the secret key.

### Database configuration

The database path used by the deployment is:

```text
/var/lib/lums/lums.db
```

The database initialization and security migration scripts use the configured database path.

All application components should use a consistent database configuration.

---

## 11. Docker Image

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

- Uses Python 3.13 Slim
- Installs server requirements
- Copies the server application
- Uses port 5000 inside the container
- Starts the Flask application

### Current limitation

Some Docker installations may display a legacy builder warning.

A future improvement is to integrate and validate Docker BuildKit/buildx.

The warning does not necessarily prevent the image from being built.

---

## 12. Docker Volume

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

- A complete backup exists.
- The backup has been verified.
- Data destruction is explicitly intended.

---

## 13. Database Initialization

Initialize the database inside the Docker volume:

```bash
sudo docker run --rm \
  --env-file /etc/lums/docker/lums.env \
  -v lums-data:/var/lib/lums \
  lums:latest \
  python3 init_db.py
```

The initialization script creates the base database tables and applies its supported schema changes.

### Security migration

The security migration creates or updates:

- User records
- Audit logging
- Schema migration tracking
- Client token fields
- Client enablement fields

Run the migration:

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

- The migration completes successfully.
- The administrator account exists.
- The database is stored in the persistent volume.
- The migration is not repeatedly applied unnecessarily.

---

## 14. Starting the LUMS Container

Start the container:

```bash
sudo docker run -d \
  --name lums \
  --restart unless-stopped \
  --env-file /etc/lums/docker/lums.env \
  -p 127.0.0.1:<HOST_PORT>:5000 \
  -v lums-data:/var/lib/lums \
  lums:latest
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

### Expected behavior

The application should:

- Initialize the database
- Start Flask
- Listen on port 5000 inside the container
- Be reachable through the localhost port on the host

The current Flask development-server warning is expected.

A production WSGI server must be integrated and tested before production-oriented deployment.

---

## 15. Application Verification

Test the local HTTP endpoint:

```bash
curl -i http://127.0.0.1:<HOST_PORT>/
```

Expected behavior:

```text
HTTP/1.1 302 FOUND
Location: /login
```

Test the login page:

```bash
curl -i http://127.0.0.1:<HOST_PORT>/login
```

The response should contain:

- HTTP 200
- Login form
- CSRF token
- Security response headers
- Session cookie

Test the login workflow through HTTPS.

The session cookie should use appropriate security attributes when configured by the application.

---

## 16. TLS Certificate Directory

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

## 17. Laboratory TLS Certificate

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

## 18. Nginx Configuration

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
        proxy_pass http://127.0.0.1:<HOST_PORT>;

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

## 19. Firewall Configuration

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
<HOST_PORT>
```

The Flask application should only be reachable through the Nginx reverse proxy.

---

## 20. Client Requirements

The Linux client requires:

- Python 3
- systemd
- Network connectivity to the LUMS server
- A valid client token
- The LUMS trust certificate
- Permission to query the package manager
- Permission to execute configured update operations

Each client must be configured individually.

Never reuse one client token across multiple independent clients.

---

## 21. Client Directory

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

## 22. Client TLS Certificate

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

## 23. Client Configuration

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

## 24. Bearer Authentication

The agent communicates with the server using a Bearer token.

Expected HTTP header:

```text
Authorization: Bearer <CLIENT_TOKEN>
```

Tokens must be:

- Unique per client
- Stored securely
- Protected from unauthorized access
- Revocable
- Excluded from Git
- Excluded from public documentation

The server must validate authentication on every protected endpoint.

Authorization must verify that a client can only access its own data and jobs.

The following areas require consistent authentication and authorization:

- Client reports
- Pending jobs
- Running jobs
- Job claiming
- Job status retrieval
- Job result submission

Authentication and authorization must be tested independently for every protected endpoint.

---

## 25. Reporting Service

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

## 26. Reporting Timer

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

## 27. Execution Watcher Service

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

## 28. Execution Watcher Timer

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

## 29. Manual Watcher Execution

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

## 30. Simulation Mode

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

- Valid client configuration
- Valid client token
- Reachable LUMS server
- Pending update job
- Supported idle detection
- Sufficient idle period

Simulation mode must not be left enabled unintentionally.

---

## 31. Update Job API

The following routes are part of the intended update job workflow:

```text
POST /api/clients/<client_id>/update-jobs
GET  /api/clients/<client_id>/update-jobs
GET  /api/clients/<client_id>/update-jobs/pending
GET  /api/clients/<client_id>/update-jobs/running
POST /api/clients/<client_id>/update-jobs/<job_id>/claim
GET  /api/update-jobs/<job_id>
POST /api/update-jobs/<job_id>/result
```

The exact available routes must be verified against the current application implementation.

All protected routes must validate:

- Authentication
- Client identity
- Authorization
- Valid request data
- Valid job ownership

The server must not rely solely on a client-provided ID.

---

## 32. Job Claiming

Job claiming must be atomic.

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

Atomic claim behavior must be verified through integration tests.

---

## 33. Job Recovery

A job may remain in the `running` state if:

- The client loses power
- The watcher is terminated
- The network connection fails
- The operating system reboots
- The package manager process crashes
- Result submission fails

Recovery logic must be tested carefully.

The system must avoid:

- Duplicate package operations
- Incorrect success states
- Permanent running jobs
- Missing audit records
- Unclear recovery behavior

Recovery must not mark a job successful without verifying the actual package operation.

---

## 34. Package Manager Safety

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

- Explicit APT and dpkg lock checks
- Detection of active package manager processes
- Deferral when the package manager is busy
- Stronger execution coordination
- Better recovery handling
- Clear user-facing status messages
- Additional audit events

Update execution must be tested in a controlled laboratory environment until stronger coordination is implemented and validated.

---

## 35. Backup Strategy

The LUMS database is stored inside the Docker volume:

```text
lums-data
```

Backups should be created before:

- Application updates
- Database migrations
- Authentication changes
- Destructive maintenance
- Restore tests
- Architectural changes

Create the backup directory:

```bash
sudo mkdir -p /var/backups/lums
sudo chmod 700 /var/backups/lums
```

A backup must be verified before the original database is replaced or removed.

---

## 36. SQLite-Aware Backup

A SQLite-aware backup is preferred over copying an active database file directly.

Example:

```bash
sudo docker run --rm \
  -v lums-data:/var/lib/lums:ro \
  -v /var/backups/lums:/backup \
  lums:latest \
  python3 -c '
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

The backup and restore procedure should be tested regularly.

---

## 37. Backup Verification

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

## 38. Restore Considerations

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

The restore process must be tested before it is considered operationally reliable.

---

## 39. Service Verification

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

## 40. Network Verification

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

## 41. Manual Agent Test

Run the agent directly:

```bash
sudo /usr/bin/python3 /opt/lums-agent/agent.py
```

The agent should:

- Load the configuration
- Contact the LUMS server
- Authenticate with the client token
- Collect client information
- Submit the report
- Return a clear result

A successful agent report does not confirm that the execution watcher is working.

The reporting and execution workflows must be tested independently.

---

## 42. Troubleshooting Strategy

Troubleshoot LUMS layer by layer:

```text
Layer 1: Client operating system
Layer 2: Python and local files
Layer 3: Client configuration
Layer 4: TLS certificate trust
Layer 5: Network connectivity
Layer 6: Nginx
Layer 7: Docker container
Layer 8: Flask application
Layer 9: Authentication
Layer 10: Database
Layer 11: Update job workflow
Layer 12: Package manager execution
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

## 43. Common Problems

### 43.1 Agent Returns 401

Possible causes:

- Invalid client token
- Incorrect token hash
- Wrong client ID
- Incorrect Authorization header
- Missing Bearer prefix
- Incorrect server URL
- Server-side authorization failure

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

---

### 43.2 TLS Certificate Error

Possible causes:

- Wrong CA certificate
- Incorrect certificate path
- Expired certificate
- Hostname mismatch
- Missing Subject Alternative Name
- Incorrect server certificate
- Certificate not installed on the client

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

### 43.3 Nginx Returns 502

Possible causes:

- Docker container is stopped
- Flask application is not listening
- Incorrect proxy port
- Missing Docker port mapping
- Container startup failure

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
curl -I http://127.0.0.1:<HOST_PORT>
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

### 43.4 Watcher Does Not Execute a Job

Possible causes:

- No pending job exists
- Client token is invalid
- Idle detection is unsupported
- Idle threshold has not been reached
- Job has already been claimed
- Job is not assigned to the client
- Package manager is busy
- Watcher is not running
- Job state is invalid

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

### 43.5 Job Remains Running

Possible causes:

- Client shutdown
- Watcher interruption
- Network failure
- Package manager still running
- Recovery logic not triggered
- Result submission failed

Review logs:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  --since "1 hour ago" \
  --no-pager
```

Verify the job state through the LUMS API or web interface.

Do not manually mark a job successful without verifying the package operation.

---

### 43.6 Agent Reports Successfully but No Job Executes

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

## 44. Security Checklist

### Server

- [ ] Docker container is not publicly exposed on port 5000
- [ ] Host proxy port is bound to localhost
- [ ] Nginx provides HTTPS
- [ ] TLS private key is protected
- [ ] Firewall rules have been reviewed
- [ ] SSH access is preserved
- [ ] Environment files are not committed
- [ ] Database volume is persistent
- [ ] Backups are created
- [ ] Backups are verified
- [ ] Logs do not expose secrets
- [ ] Production WSGI server is integrated and tested before production use

### Client

- [ ] Client token is unique
- [ ] Client configuration is owned by root
- [ ] Client configuration has mode 600
- [ ] TLS certificate is installed
- [ ] TLS verification is enabled
- [ ] Agent files are owned by root
- [ ] Watcher files are owned by root
- [ ] Simulation mode is disabled after testing
- [ ] Update execution is tested in a controlled environment

### Application

- [ ] Bearer authentication is enforced on protected endpoints
- [ ] Authorization is checked for every client-specific endpoint
- [ ] Job claiming is atomic
- [ ] Job results are validated
- [ ] Invalid job states are rejected
- [ ] Audit events are recorded
- [ ] Error messages do not disclose secrets
- [ ] Database access is protected
- [ ] Recovery behavior is tested
- [ ] Integration tests exist for critical workflows

---

## 45. Current Limitations

### 45.1 Flask Development Server

The current Docker container starts Flask through the integrated development server.

A production-grade WSGI server has not yet been integrated and validated.

### 45.2 Idle Detection

The current idle detection uses `w -h`.

It is primarily suitable for terminal, server, and SSH-oriented environments.

It is not a universal desktop idle detection mechanism.

### 45.3 Package Manager Coordination

Complete collision prevention between LUMS and arbitrary user-issued APT or dpkg commands is not fully implemented.

The custom LUMS lock does not force every external package manager process to honor it.

### 45.4 Self-Signed Certificates

Self-signed certificates require explicit trust configuration on clients.

They are suitable for controlled laboratory environments but may not be appropriate for every deployment scenario.

### 45.5 SQLite Scaling

SQLite is suitable for the current project scope and laboratory development.

Larger deployments may require a different database architecture depending on:

- Number of clients
- Job volume
- Concurrent requests
- Audit log size
- Backup requirements
- High availability requirements

### 45.6 Deployment Configuration Consistency

Database path handling must remain consistent across:

- Application code
- Initialization scripts
- Migration scripts
- Backup procedures
- Restore procedures

---

## 46. Recommended Development Priorities

The following areas require further development and validation:

1. Complete Bearer authentication enforcement on every protected endpoint.
2. Strengthen client authorization checks.
3. Integrate and validate a production WSGI server.
4. Improve package manager collision prevention.
5. Improve watcher recovery behavior.
6. Add job timeout handling.
7. Improve desktop idle detection support.
8. Add detailed audit events.
9. Improve backup and restore procedures.
10. Add database migration handling.
11. Add automated integration tests.
12. Add security regression tests.
13. Improve API documentation.
14. Add structured logging.
15. Add monitoring and alerting.
16. Review the complete update execution workflow before production use.

---

## 47. Final Validation

Perform the following validation after installation or an update:

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
systemctl status nginx --no-pager
```

```bash
curl -I http://127.0.0.1:<HOST_PORT>
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

- HTTPS is accessible
- The LUMS container is running
- The database volume is mounted
- The agent can report
- The watcher can reach the server
- Authentication works
- Pending jobs are visible
- Job claiming is atomic
- Simulation mode is disabled
- Backups exist
- No sensitive data is present in Git

Only mark a component as validated after an actual successful test.

---

## 48. Operational Principle

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
Document
   |
   v
Deploy
```

The goal is not to hide complexity.

The goal is to make complexity visible, manageable, and auditable.

---

## 49. Project Statement

LUMS is designed around the following principle:

> Linux Update Management without the noise.

The project combines centralized reporting, controlled update jobs, idle-aware execution, and security-oriented infrastructure practices.

The system remains under active development.

All production-oriented functionality must be tested, reviewed, and documented before being considered reliable for critical environments.

---

**LUMS**

**Linux Update Management without the noise.**
