# LUMS Installation Guide

## Linux Update Management Server

**Version:** 2.1  
**Project:** LUMS  
**Slogan:** Linux Update Management without the noise.  
**Repository:** `https://github.com/NovaForgeCtrl/LUMS.git`

---

## 1. Overview

LUMS is a centralized Linux update management platform designed for controlled update distribution, client reporting, job management, and auditable execution.

The project is intended for laboratory environments, small infrastructures, and future production-oriented development.

LUMS currently consists of:

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

The project is designed with a security-oriented approach:

> Do not reinstall everything immediately. Find the layer where the problem occurs.

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
                               | HTTP :5050
                               |
                    +----------v-----------+
                    |     Docker Host      |
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

The container is not directly exposed to the network.

---

### 3.2 Nginx Reverse Proxy

Nginx provides:

- HTTPS termination
- TLS certificate handling
- HTTP to HTTPS redirection
- Reverse proxying to the Flask application
- External access control

The Flask application is bound to the local host only.

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
Docker container port 5000
```

Ports `5000` and `5050` must not be exposed directly to the network.

---

### 3.3 Linux Agent

The LUMS agent is responsible for:

- Collecting system information
- Detecting installed packages
- Detecting available updates
- Reporting client status
- Sending data to the LUMS server
- Communicating using Bearer authentication

The agent does not directly represent the complete update execution workflow.

The current agent version is:

```text
AGENT 1.6.0
```

---

### 3.4 Execution Watcher

The execution watcher is separated from the reporting agent.

The watcher is responsible for:

- Checking pending update jobs
- Checking whether the client is idle
- Claiming jobs atomically
- Executing approved jobs
- Recovering interrupted running jobs
- Sending execution results
- Reporting execution states

This separation reduces the responsibilities of the reporting agent and allows update execution to be developed independently.

The current watcher version is:

```text
WATCHER 1.2.1
```

---

## 4. Current Execution Model

The execution watcher uses an idle-aware execution model.

A job should only be executed when:

1. The client supports idle detection.
2. The detected idle time reaches the configured threshold.
3. A pending job is available.
4. The job can be claimed successfully.
5. The package manager is not already being used by another process.

The current idle threshold is:

```text
300 seconds
```

The idle detection currently uses:

```text
w -h
```

This primarily supports server, terminal, console, and SSH-oriented environments.

It must not be considered universal desktop idle detection.

The watcher reports metadata such as:

```text
idle
idle_seconds
idle_threshold_seconds
idle_source
idle_supported
```

The watcher must not execute update jobs while active user activity is detected.

---

## 5. Job States

The job lifecycle uses the following states:

```text
pending
   |
   v
running
   |
   +------------------+
   |                  |
   v                  v
success            partial
   |
   v
failed
```

A job may also require recovery when the client or watcher stops while the job is running.

The implementation must handle interrupted jobs carefully to prevent permanent `running` states.

### 5.1 Pending

The job has been created but has not yet been claimed by a client.

### 5.2 Running

The job has been claimed and is currently being processed.

### 5.3 Success

The job completed successfully.

### 5.4 Partial

The job completed with some operations succeeding and others failing.

### 5.5 Failed

The job could not be completed successfully.

---

## 6. Repository Structure

A simplified repository structure:

```text
LUMS/
├── agent/
│   ├── agent.py
│   └── watcher.py
├── server/
│   ├── app.py
│   ├── security.py
│   ├── database.py
│   └── ...
├── templates/
├── static/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

The exact structure may change during development.

The server-side application and client-side agent must be versioned together whenever API changes affect both components.

---

## 7. Server Requirements

Recommended server requirements:

- Linux operating system
- Docker Engine
- Docker Compose plugin
- Nginx
- OpenSSL
- UFW or another firewall
- Python tooling inside the Docker image
- Persistent storage for the SQLite database

The server must have sufficient storage for:

- Docker images
- Application files
- Database files
- Logs
- Backups
- TLS certificates

---

## 8. Directory Layout

The following directory layout is recommended:

```text
/opt/lums-public/
    Git repository

/opt/lums-api/
    Deployment-related application files

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

The exact deployment structure may differ depending on the environment.

---

## 9. Clone or Update the Repository

Clone the repository:

```bash
sudo mkdir -p /opt
cd /opt

sudo git clone https://github.com/NovaForgeCtrl/LUMS.git lums-public
```

If the repository already exists:

```bash
cd /opt/lums-public

git fetch origin
git status -sb
git pull --ff-only origin main
```

Always review the changes before deploying:

```bash
git log --oneline --decorate -5
git diff HEAD~1..HEAD
```

Do not deploy unreviewed changes directly into a production-like environment.

---

## 10. Docker Environment Configuration

Create the configuration directory:

```bash
sudo install -d -o root -g root -m 750 /etc/lums/docker
```

Create the environment file:

```bash
sudo touch /etc/lums/docker/lums.env

sudo chown root:root /etc/lums/docker/lums.env
sudo chmod 600 /etc/lums/docker/lums.env
```

The environment file must contain only deployment-specific values.

Example:

```dotenv
FLASK_ENV=production
LUMS_DATABASE=/var/lib/lums/lums.db
```

Do not commit the environment file to Git.

Do not store:

- Passwords
- API tokens
- Private keys
- Secret keys
- Internal credentials

inside the public repository.

---

## 11. Docker Deployment

Build the Docker image:

```bash
cd /opt/lums-public

sudo docker build -t lums:latest .
```

Verify the image:

```bash
sudo docker image ls lums
```

The LUMS container should use the following port mapping:

```text
127.0.0.1:5050:5000
```

This means:

- Flask listens on port `5000` inside the container.
- The Docker host exposes the service only on `127.0.0.1:5050`.
- Nginx accesses the service locally.
- The Flask application is not directly accessible from the network.

---

## 12. Docker Volume

LUMS uses a persistent Docker volume for the SQLite database.

Expected volume:

```text
lums-data
```

Check the volume:

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

unless a complete, verified backup exists and data destruction is explicitly intended.

---

## 13. Starting the LUMS Container

Example container creation:

```bash
sudo docker run -d \
  --name lums \
  --restart unless-stopped \
  --env-file /etc/lums/docker/lums.env \
  -p 127.0.0.1:5050:5000 \
  -v lums-data:/var/lib/lums \
  lums:latest
```

Check the container:

```bash
sudo docker ps
```

Check the logs:

```bash
sudo docker logs --tail 100 lums
```

Follow the logs:

```bash
sudo docker logs -f lums
```

Check the container health:

```bash
sudo docker inspect lums
```

---

## 14. Updating the Docker Deployment

Before updating:

```bash
sudo docker ps
sudo docker volume inspect lums-data
sudo docker logs --tail 100 lums
```

Build the updated image:

```bash
cd /opt/lums-public

sudo docker build -t lums:latest .
```

Stop and remove only the container:

```bash
sudo docker stop lums
sudo docker rm lums
```

Do not remove the persistent database volume.

Start the updated container:

```bash
sudo docker run -d \
  --name lums \
  --restart unless-stopped \
  --env-file /etc/lums/docker/lums.env \
  -p 127.0.0.1:5050:5000 \
  -v lums-data:/var/lib/lums \
  lums:latest
```

Verify the deployment:

```bash
sudo docker ps
sudo docker logs --tail 100 lums
```

Test the local application endpoint:

```bash
curl -I http://127.0.0.1:5050
```

---

## 15. TLS Certificate Directory

Create the TLS directory:

```bash
sudo install -d -o root -g root -m 750 /etc/lums/tls
```

The expected server-side files are:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Set secure permissions:

```bash
sudo chown root:root /etc/lums/tls/lums.crt
sudo chown root:root /etc/lums/tls/lums.key

sudo chmod 644 /etc/lums/tls/lums.crt
sudo chmod 600 /etc/lums/tls/lums.key
```

The private key must never be committed to GitHub.

---

## 16. Example Certificate Configuration

Create a temporary OpenSSL configuration file:

```bash
cat > /tmp/lums-openssl.cnf <<'EOF'
[req]
default_bits = 4096
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = DE
ST = where you want
L = Local
O = LUMS
OU = Infrastructure
CN = lums

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = lums
DNS.2 = container
IP.1 = <LUMS_SERVER_IP>
EOF
```

Generate a self-signed certificate:

```bash
sudo openssl req \
  -x509 \
  -nodes \
  -days 825 \
  -newkey rsa:4096 \
  -keyout /etc/lums/tls/lums.key \
  -out /etc/lums/tls/lums.crt \
  -config /tmp/lums-openssl.cnf
```

Secure the private key:

```bash
sudo chown root:root /etc/lums/tls/lums.key
sudo chmod 600 /etc/lums/tls/lums.key
```

Remove the temporary configuration file:

```bash
rm -f /tmp/lums-openssl.cnf
```

### Certificate limitation

Self-signed certificates are suitable for controlled laboratories.

For broader deployments, use a trusted internal certificate authority or another suitable certificate management solution.

Clients must explicitly trust the correct certificate or CA certificate.

---

## 17. Nginx Configuration

Install Nginx if required:

```bash
sudo apt update
sudo apt install -y nginx
```

Create the LUMS site configuration:

```bash
sudo tee /etc/nginx/sites-available/lums > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;

    server_name lums;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name lums;

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

Disable the default site if necessary:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
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
sudo systemctl status nginx
```

---

## 18. Firewall Configuration

Install UFW if required:

```bash
sudo apt update
sudo apt install -y ufw
```

Allow SSH:

```bash
sudo ufw allow 22/tcp
```

Allow HTTP and HTTPS:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

Enable the firewall:

```bash
sudo ufw enable
```

Check the rules:

```bash
sudo ufw status verbose
```

Do not expose the following ports externally:

```text
5000
5050
```

The Flask application should only be reachable through Nginx.

---

## 19. Client Requirements

The Linux client requires:

- Python 3
- systemd
- Network connectivity to the LUMS server
- A valid client token
- The LUMS trust certificate
- Permission to query the package manager
- Permission to execute the configured update operations

The client must be configured individually.

Never reuse one client token across multiple independent clients.

---

## 20. Client Directory

Create the agent directory:

```bash
sudo install -d -o root -g root -m 750 /opt/lums-agent
```

Copy the agent files to the client.

If the repository is available locally:

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

If the repository is not available locally, transfer the files using a secure method such as SCP or another controlled file transfer process.

Verify the files:

```bash
sudo ls -l /opt/lums-agent
```

---

## 21. Client TLS Certificate

Install the trusted certificate:

```bash
sudo install \
  -o root \
  -g root \
  -m 644 \
  /tmp/lums-ca.crt \
  /opt/lums-agent/lums-ca.crt
```

Verify the certificate:

```bash
sudo openssl x509 \
  -in /opt/lums-agent/lums-ca.crt \
  -noout \
  -subject \
  -issuer \
  -dates
```

The configured certificate path must be:

```text
/opt/lums-agent/lums-ca.crt
```

---

## 22. Client Configuration

Create the client configuration file:

```bash
sudo touch /etc/default/lums-agent

sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

Edit the file using a secure administrative method.

Example configuration:

```dotenv
LUMS_BASE="https://<LUMS_SERVER_IP>"
LUMS_TOKEN="<CLIENT_TOKEN>"
LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt"
```

The file must be owned by root and must not be readable by regular users.

Verify the permissions:

```bash
sudo stat -c '%U:%G %a %n' /etc/default/lums-agent
```

Expected result:

```text
root:root 600 /etc/default/lums-agent
```

Never display the token in terminal output or documentation.

---

## 23. Bearer Authentication

The agent communicates with the LUMS server using a Bearer token.

The token must be transmitted using the HTTP authorization header:

```text
Authorization: Bearer <CLIENT_TOKEN>
```

The token must be:

- Unique per client
- Stored securely
- Protected from unauthorized access
- Revocable
- Never committed to Git
- Never written into public documentation

The server must validate the token on every protected endpoint.

Authentication and authorization must be enforced consistently for:

- Client reports
- Pending jobs
- Running jobs
- Job claiming
- Job status retrieval
- Job result submission

---

## 24. Reporting Service

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
sudo systemctl status lums-agent.service
```

View logs:

```bash
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

---

## 25. Reporting Timer

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

Enable and start the timer:

```bash
sudo systemctl daemon-reload

sudo systemctl enable --now lums-agent.timer
```

Check the timer:

```bash
systemctl status lums-agent.timer
```

List scheduled timers:

```bash
systemctl list-timers --all | grep lums
```

The reporting interval is approximately:

```text
5 minutes
```

The timer is responsible for regular client reporting.

Update execution is handled separately by the execution watcher.

---

## 26. Execution Watcher Service

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

Important:

The production service must not contain simulation mode settings.

Do not add:

```ini
Environment=LUMS_SIMULATE_UPDATES=1
```

to the permanent production service.

---

## 27. Execution Watcher Timer

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
systemctl status lums-execution-watcher.timer
```

List LUMS timers:

```bash
systemctl list-timers --all | grep lums
```

The watcher runs approximately every:

```text
30 seconds
```

---

## 28. Manual Watcher Execution

Run the watcher manually:

```bash
sudo systemctl start lums-execution-watcher.service
```

Check the status:

```bash
sudo systemctl status lums-execution-watcher.service
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

A manual execution is useful for controlled testing and troubleshooting.

---

## 29. Simulation Mode

Simulation mode is intended for testing the execution workflow without changing installed packages.

Simulation mode must be enabled temporarily.

Create a runtime-only override:

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

Verify that simulation mode is disabled:

```bash
sudo systemctl cat lums-execution-watcher.service
```

### Simulation requirements

Simulation mode still requires:

- A valid client configuration
- A valid client token
- A reachable LUMS server
- A pending update job
- Supported idle detection
- A sufficient idle period

Simulation mode must never be left enabled unintentionally.

---

## 30. Update Job API

The following API routes are used by the update job workflow.

### Create an update job

```http
POST /api/clients/<client_id>/update-jobs
```

### List update jobs for a client

```http
GET /api/clients/<client_id>/update-jobs
```

### List pending jobs

```http
GET /api/clients/<client_id>/update-jobs/pending
```

### List running jobs

```http
GET /api/clients/<client_id>/update-jobs/running
```

### Claim a job

```http
POST /api/clients/<client_id>/update-jobs/<job_id>/claim
```

### Get job status

```http
GET /api/update-jobs/<job_id>
```

### Submit job result

```http
POST /api/update-jobs/<job_id>/result
```

All protected routes must validate authentication and authorization.

A client must only be allowed to access jobs belonging to that client.

---

## 31. Job Claiming

Job claiming must be atomic.

The watcher must not execute a job merely because it appears in a list of pending jobs.

The expected workflow is:

```text
1. Find pending job
2. Verify client identity
3. Verify idle state
4. Attempt atomic claim
5. Confirm claim success
6. Execute the job
7. Submit the result
```

If another watcher or process claims the job first, the current watcher must not execute it.

This prevents duplicate execution in environments with multiple workers or repeated timer runs.

---

## 32. Job Recovery

A job may remain in the `running` state if:

- The client loses power
- The watcher process is terminated
- The network connection fails
- The operating system reboots
- The package manager process crashes

The watcher must support recovery logic for interrupted jobs.

Recovery must be implemented carefully to avoid:

- Duplicate package operations
- Incorrect success states
- Permanent running jobs
- Unclear audit records

Recovery behavior should always be documented when it changes.

---

## 33. Package Manager Safety

Complete APT and dpkg collision prevention is not fully implemented.

The current LUMS lock mechanism does not automatically force arbitrary user-issued APT commands to honor the LUMS lock.

Therefore, the following situation remains possible:

```text
LUMS watcher starts an operation
        +
User manually runs apt or dpkg
        =
Potential package manager collision
```

This is an important hardening topic for future development.

The system must not claim that all package manager collisions are already prevented.

Future improvements may include:

- Explicit package manager lock checks
- Detection of active APT or dpkg processes
- Deferral when the package manager is busy
- Stronger execution coordination
- Better recovery handling
- Clear user-facing status messages
- Additional audit events

Until complete coordination is implemented, update execution should be tested carefully in controlled environments.

---

## 34. Backup Strategy

The LUMS database is stored inside the Docker volume:

```text
lums-data
```

Backups must be created before:

- Major application updates
- Database migrations
- Authentication changes
- Destructive maintenance
- Restore tests
- Large architectural changes

Create the backup directory:

```bash
sudo mkdir -p /var/backups/lums
sudo chmod 700 /var/backups/lums
```

---

## 35. SQLite-Aware Backup

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

Verify the backup file:

```bash
sudo ls -lh /var/backups/lums/lums.db.backup
```

---

## 36. Backup Verification

A backup is not considered reliable until it has been tested.

Example verification:

```bash
sudo docker run --rm \
  -v /var/backups/lums:/backup:ro \
  lums:latest \
  python3 -c '
import sqlite3

db = sqlite3.connect("file:/backup/lums.db.backup?mode=ro", uri=True)

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

The backup should also be tested in an isolated restore environment.

---

## 37. Restore Considerations

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

A restore procedure must be tested before it is considered operationally reliable.

---

## 38. Service Verification

Check all LUMS services:

```bash
systemctl status lums-agent.service
systemctl status lums-agent.timer
systemctl status lums-execution-watcher.service
systemctl status lums-execution-watcher.timer
```

List timers:

```bash
systemctl list-timers --all | grep lums
```

Check recent agent logs:

```bash
sudo journalctl \
  -u lums-agent.service \
  -n 100 \
  --no-pager
```

Check recent watcher logs:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 100 \
  --no-pager
```

---

## 39. Network Verification

Check DNS or hostname resolution:

```bash
getent hosts <LUMS_SERVER_IP>
```

Test HTTPS connectivity:

```bash
curl \
  --cacert /opt/lums-agent/lums-ca.crt \
  https://<LUMS_SERVER_IP>/
```

Test certificate information:

```bash
openssl s_client \
  -connect <LUMS_SERVER_IP>:443 \
  -servername lums \
  -CAfile /opt/lums-agent/lums-ca.crt
```

Do not disable TLS verification as a permanent solution.

Avoid using:

```bash
curl -k
```

in production automation.

The option may be useful for controlled diagnostics, but it disables certificate verification.

---

## 40. Manual Agent Test

Run the agent directly:

```bash
sudo /usr/bin/python3 /opt/lums-agent/agent.py
```

The agent should:

- Load the configuration
- Contact the LUMS server
- Authenticate using the configured token
- Collect client information
- Submit the report
- Return a clear result

The agent reporting process and execution watcher are separate workflows.

A successful agent report does not automatically mean that update execution is working.

---

## 41. Troubleshooting Strategy

Troubleshoot LUMS layer by layer.

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

---

## 42. Common Problems

### 42.1 Agent returns 401

Possible causes:

- Invalid client token
- Incorrect token hash
- Wrong client ID
- Incorrect Authorization header
- Missing Bearer prefix
- Incorrect server URL
- Server-side authorization failure

Check the configuration permissions:

```bash
sudo stat -c '%U:%G %a %n' /etc/default/lums-agent
```

Check the service logs:

```bash
sudo journalctl \
  -u lums-agent.service \
  -n 100 \
  --no-pager
```

Never print the complete token during troubleshooting.

---

### 42.2 TLS Certificate Error

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
grep -E '^LUMS_CA_FILE=' /etc/default/lums-agent
```

Expected path:

```text
/opt/lums-agent/lums-ca.crt
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

---

### 42.3 Nginx Returns 502

Possible causes:

- Docker container is stopped
- Flask application is not listening
- Incorrect proxy port
- Docker port mapping is missing
- Container startup failure

Check Docker:

```bash
sudo docker ps
```

Check the container logs:

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
sudo journalctl -u nginx -n 100 --no-pager
```

---

### 42.4 Watcher Does Not Execute a Job

Possible causes:

- No pending job exists
- Client token is invalid
- Idle detection is unsupported
- Idle threshold has not been reached
- Job has already been claimed
- Job is not assigned to the client
- The package manager is busy
- The watcher is not running
- The job state is invalid

Check the watcher logs:

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

Check the client idle information:

```bash
w -h
```

Do not assume that a connected SSH session always represents an active user, or that the current idle detection supports every desktop environment.

---

### 42.5 Job Remains Running

Possible causes:

- Client shutdown
- Watcher interruption
- Network failure
- Package manager process still running
- Recovery logic not triggered
- Result submission failed

Review:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  --since "1 hour ago" \
  --no-pager
```

Check the job state using the LUMS API or web interface.

Do not manually mark jobs as successful without verifying whether the package operation actually completed.

---

### 42.6 Agent Reports Successfully but No Job Executes

The reporting agent and execution watcher are separate.

A successful report only confirms that the reporting workflow completed.

Check the watcher independently:

```bash
systemctl status lums-execution-watcher.timer
```

```bash
sudo systemctl start lums-execution-watcher.service
```

Then inspect:

```bash
sudo journalctl \
  -u lums-execution-watcher.service \
  -n 100 \
  --no-pager
```

---

## 43. Security Checklist

### Server

- [ ] Docker container is not publicly exposed on port 5000
- [ ] Host port 5050 is bound to localhost
- [ ] Nginx provides HTTPS
- [ ] TLS private key is protected
- [ ] Firewall is enabled
- [ ] SSH access is restricted
- [ ] Environment files are not committed
- [ ] Database volume is persistent
- [ ] Backups are created
- [ ] Backups are verified
- [ ] Logs do not expose secrets

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

- [ ] Bearer authentication is enforced
- [ ] Authorization is checked for every client-specific endpoint
- [ ] Job claiming is atomic
- [ ] Job results are validated
- [ ] Invalid job states are rejected
- [ ] Audit events are recorded
- [ ] Error messages do not disclose secrets
- [ ] Database access is protected
- [ ] Recovery behavior is tested

---

## 44. Current Limitations

The following limitations must be considered during development.

### 44.1 Idle Detection

The current idle detection is based on `w -h`.

It is primarily suitable for terminal, server, and SSH-oriented environments.

It is not a universal desktop idle detection mechanism.

### 44.2 Package Manager Coordination

Complete collision prevention between LUMS and arbitrary user-issued APT or dpkg commands is not fully implemented.

The custom LUMS lock does not force every external package manager process to honor it.

This remains an important security and reliability development topic.

### 44.3 Self-Signed Certificates

Self-signed certificates require explicit trust configuration on clients.

They are suitable for controlled laboratory environments but may not be appropriate for every deployment scenario.

### 44.4 SQLite Scaling

SQLite is suitable for the current project scope and laboratory development.

Larger deployments may require a different database architecture depending on:

- Number of clients
- Job volume
- Concurrent requests
- Audit log size
- Backup requirements
- High availability requirements

---

## 45. Recommended Development Priorities

Recommended future development areas:

1. Complete Bearer authentication enforcement on every protected endpoint.
2. Strengthen client authorization checks.
3. Improve package manager collision prevention.
4. Improve watcher recovery behavior.
5. Add better job timeout handling.
6. Improve desktop idle detection support.
7. Add more detailed audit events.
8. Improve backup and restore automation.
9. Add database migration handling.
10. Add automated integration tests.
11. Add security regression tests.
12. Improve API documentation.
13. Add structured logging.
14. Add monitoring and alerting.
15. Review the complete update execution workflow before production use.

---

## 46. Final Validation

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
systemctl status nginx
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

---

## 47. Operational Principle

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

## 48. Project Statement

LUMS is designed around the following principle:

> Linux Update Management without the noise.

The project combines centralized reporting, controlled update jobs, idle-aware execution, and security-oriented infrastructure practices.

The system remains under active development.

All production-oriented functionality must be tested, reviewed, and documented before being considered reliable for critical environments.

---

**LUMS**

**Linux Update Management without the noise.**
