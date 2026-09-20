
# LUMS Installation Guide v2.0

## Linux Update Management Server

**LUMS** is a self-hosted Linux update management platform for centrally managing Linux systems, collecting system information, detecting available updates and executing controlled update jobs.

> Linux Update Management without the noise.

LUMS consists of two major components:

- **LUMS Server:** Flask application running inside Docker
- **LUMS Agent:** Native Python agent running directly on managed Linux systems

The server provides the web interface, REST API, authentication, client management, update jobs, audit logging and persistent database storage.

The agent collects system information, communicates with the server over HTTPS and executes update jobs locally using the native package manager.

---

# Table of Contents

1. [Architecture](#1-architecture)
2. [Prerequisites](#2-prerequisites)
3. [Prepare the Ubuntu Server](#3-prepare-the-ubuntu-server)
4. [Install Docker](#4-install-docker)
5. [Install Supporting Tools](#5-install-supporting-tools)
6. [Download the Repository](#6-download-the-repository)
7. [Review the Project](#7-review-the-project)
8. [Build the Docker Image](#8-build-the-docker-image)
9. [Create Persistent Storage](#9-create-persistent-storage)
10. [Configure the Secret Key](#10-configure-the-secret-key)
11. [Initialize the Database](#11-initialize-the-database)
12. [Run the Security Migration](#12-run-the-security-migration)
13. [Start the LUMS Container](#13-start-the-lums-container)
14. [Verify the Container](#14-verify-the-container)
15. [Configure the Server IP](#15-configure-the-server-ip)
16. [Create the TLS Certificate](#16-create-the-tls-certificate)
17. [Configure Nginx](#17-configure-nginx)
18. [Test HTTPS](#18-test-https)
19. [Configure the Firewall](#19-configure-the-firewall)
20. [Register a Client](#20-register-a-client)
21. [Install the Agent](#21-install-the-agent)
22. [Configure the Agent Certificate](#22-configure-the-agent-certificate)
23. [Configure Agent Authentication](#23-configure-agent-authentication)
24. [Test the Agent Manually](#24-test-the-agent-manually)
25. [Install the systemd Service](#25-install-the-systemd-service)
26. [Install the systemd Timer](#26-install-the-systemd-timer)
27. [Verify Automatic Execution](#27-verify-automatic-execution)
28. [Update Job Workflow](#28-update-job-workflow)
29. [Backup](#29-backup)
30. [Restore](#30-restore)
31. [Security Checklist](#31-security-checklist)
32. [Troubleshooting](#32-troubleshooting)
33. [Final Verification](#33-final-verification)

---

# 1. Architecture

The LUMS architecture separates the central management server from the managed Linux systems.

```text
                         LUMS SERVER
                    Ubuntu Linux Host
                              |
              +---------------+---------------+
              |                               |
            Nginx                          Docker
          HTTPS :443                    LUMS :5000
              |                               |
              |                        +------+------+
              |                        | Flask       |
              |                        | Web UI/API  |
              |                        +------+------+
              |                               |
              |                          lums-data
              |                               |
              +---------------+---------------+
                              |
                         HTTPS + Token
                              |
              +---------------+---------------+
              |                               |
       Linux Client                    Linux Client
       Native Agent                    Native Agent
              |                               |
       systemd Timer                   systemd Timer
              |                               |
          APT/dpkg                        APT/dpkg
```

## 1.1 Server Components

The LUMS server provides:

- Web interface
- REST API
- Client registration
- Client authentication
- System inventory
- Package inventory
- Update detection
- Update job management
- Update history
- Audit logging
- SQLite database
- HTTPS access through Nginx

## 1.2 Agent Components

The native agent provides:

- Hostname detection
- IP address detection
- Operating system information
- Kernel information
- Architecture detection
- Package inventory
- Available update detection
- Report transmission
- Client authentication
- Pending job retrieval
- Update job execution
- Result reporting

## 1.3 Component Separation

| Component | Location |
|---|---|
| LUMS Flask application | Docker container |
| SQLite database | Persistent Docker volume |
| Nginx | Linux host |
| TLS private key | Linux host |
| LUMS agent | Managed Linux host |
| systemd timer | Managed Linux host |
| APT/dpkg | Managed Linux host |

The agent runs outside Docker because it requires direct access to the managed operating system, package manager and systemd.

---

# 2. Prerequisites

## 2.1 LUMS Server

Recommended minimum configuration:

```text
Operating system: Ubuntu Server 26.04 LTS
CPU:              2 cores
RAM:              2–4 GB
Storage:          20 GB or more
Network:          Stable network connection
Docker:           Required
Nginx:            Required
```

The server must have a stable IP address that managed clients can reach.

Example:

```text
LUMS server IP:
IP Address
```

Throughout this document, replace:

```text
<LUMS_SERVER_IP>
```

with the actual server IP address.

## 2.2 Managed Linux Client

The agent requires:

```text
Linux
Python 3
systemd
APT-compatible package manager
Network access to the LUMS server
```

The agent is intended for Debian- and Ubuntu-based systems.

## 2.3 Important Security Information

The following values are sensitive:

- Flask secret key
- Administrator password
- Client authentication token
- TLS private key
- Agent configuration file

Never publish these values in GitHub repositories, screenshots or documentation.

---

# 3. Prepare the Ubuntu Server

Update the package lists:

```bash
sudo apt update
```

Install available updates:

```bash
sudo apt upgrade -y
```

Check the operating system:

```bash
cat /etc/os-release
```

Check the kernel:

```bash
uname -r
```

Check the IP address:

```bash
hostname -I
```

Check available storage:

```bash
df -h
```

Check systemd:

```bash
systemctl is-system-running
```

If Ubuntu requests a reboot:

```bash
sudo reboot
```

Reconnect after the reboot.

---

# 4. Install Docker

Install Docker from the Ubuntu repositories:

```bash
sudo apt install -y docker.io
```

Enable and start Docker:

```bash
sudo systemctl enable --now docker
```

Check the version:

```bash
docker --version
```

Check the service:

```bash
sudo systemctl status docker --no-pager
```

Add the current user to the Docker group:

```bash
sudo usermod -aG docker "$USER"
```

Apply the group membership:

```bash
newgrp docker
```

Test Docker:

```bash
docker ps
```

The command should work without requiring `sudo`.

> Group membership changes may require logging out and logging in again.

---

# 5. Install Supporting Tools

Install the required tools:

```bash
sudo apt install -y \
    nginx \
    git \
    openssl \
    curl \
    ca-certificates
```

Enable Nginx:

```bash
sudo systemctl enable --now nginx
```

Verify the installed tools:

```bash
nginx -v
```

```bash
git --version
```

```bash
openssl version
```

```bash
curl --version
```

Check Nginx:

```bash
sudo systemctl status nginx --no-pager
```

---

# 6. Download the Repository

Change to the `/opt` directory:

```bash
cd /opt
```

Clone the repository:

```bash
sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public
```

Set ownership of the working directory:

```bash
sudo chown -R "$USER":"$USER" /opt/lums-public
```

Enter the repository:

```bash
cd /opt/lums-public
```

Check the Git status:

```bash
git status
```

Check the current branch:

```bash
git branch --show-current
```

Check the latest commits:

```bash
git log --oneline --decorate -5
```

The working tree should be clean.

---

# 7. Review the Project

Review the repository structure:

```bash
find . -maxdepth 2 -type f | sort
```

Important files and directories include:

```text
Dockerfile
.dockerignore
server/
agent/
README.md
```

Review the Dockerfile:

```bash
sed -n '1,240p' Dockerfile
```

Review the server dependencies:

```bash
cat server/requirements.txt
```

Review the agent files:

```bash
find agent -maxdepth 2 -type f -print
```

Review the agent service definition:

```bash
cat agent/lums-agent.service
```

Review the timer definition:

```bash
cat agent/lums-agent.timer
```

> Review the project files before making changes. The repository is the authoritative source for the application structure.

---

# 8. Build the Docker Image

Build the LUMS image:

```bash
docker build -t lums:latest .
```

List the image:

```bash
docker images lums
```

Inspect the image:

```bash
docker image inspect lums:latest \
    --format '{{.Id}}'
```

Check the image size:

```bash
docker image inspect lums:latest \
    --format '{{.Size}}'
```

The build must complete without errors before continuing.

---

# 9. Create Persistent Storage

Create the Docker volume:

```bash
docker volume create lums-data
```

List Docker volumes:

```bash
docker volume ls
```

Inspect the volume:

```bash
docker volume inspect lums-data
```

The database will be stored in:

```text
/var/lib/lums/lums.db
```

The container volume is mounted to:

```text
/var/lib/lums
```

> Do not delete the `lums-data` volume unless you intentionally want to delete the LUMS database.

---

# 10. Configure the Secret Key

Create the configuration directory:

```bash
sudo mkdir -p /etc/lums/docker
```

Generate a secure secret key:

```bash
sudo sh -c '
    umask 077
    printf "LUMS_SECRET_KEY=%s\n" \
        "$(openssl rand -hex 64)" \
        > /etc/lums/docker/lums.env
'
```

Set directory permissions:

```bash
sudo chown root:root /etc/lums/docker
sudo chmod 700 /etc/lums/docker
```

Set file permissions:

```bash
sudo chown root:root /etc/lums/docker/lums.env
sudo chmod 600 /etc/lums/docker/lums.env
```

Verify the key exists without displaying it:

```bash
sudo grep -q '^LUMS_SECRET_KEY=.' \
    /etc/lums/docker/lums.env \
    && echo "LUMS_SECRET_KEY vorhanden"
```

Verify permissions:

```bash
sudo stat -c '%U:%G %a %n' \
    /etc/lums/docker/lums.env
```

Expected permissions:

```text
root:root 600 /etc/lums/docker/lums.env
```

The file must not be committed to Git.

---

# 11. Initialize the Database

Run the database initialization inside a temporary container:

```bash
docker run --rm \
    --env-file /etc/lums/docker/lums.env \
    -v lums-data:/var/lib/lums \
    lums:latest \
    python3 init_db.py
```

The database should be created at:

```text
/var/lib/lums/lums.db
```

Check the database using a temporary container:

```bash
docker run --rm \
    --env-file /etc/lums/docker/lums.env \
    -v lums-data:/var/lib/lums \
    lums:latest \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print("Database OK")
print("Tables:")
for row in db.execute(
    "SELECT name FROM sqlite_master WHERE type=\"table\" ORDER BY name"
):
    print(" -", row[0])
db.close()
'
```

The database must exist before continuing.

---

# 12. Run the Security Migration

Run the security migration:

```bash
docker run --rm -it \
    --env-file /etc/lums/docker/lums.env \
    -v lums-data:/var/lib/lums \
    lums:latest \
    python3 security_migration.py
```

Follow the prompts.

Create the administrator account and choose a strong password.

The security migration may create or update:

- Administrator user
- User table
- Audit log
- Schema migration records
- Client security fields
- Authentication-related database structures

Verify the database:

```bash
docker run --rm \
    --env-file /etc/lums/docker/lums.env \
    -v lums-data:/var/lib/lums \
    lums:latest \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for table in ("users", "audit_log", "schema_migrations"):
    result = db.execute(
        "SELECT name FROM sqlite_master WHERE type=\"table\" AND name=?",
        (table,)
    ).fetchone()
    print(table, "OK" if result else "MISSING")

db.close()
'
```

Do not store the administrator password in documentation.

---

# 13. Start the LUMS Container

Start the production container:

```bash
docker run -d \
    --name lums \
    --restart unless-stopped \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
```

Check the running containers:

```bash
docker ps
```

Check the LUMS container:

```bash
docker ps \
    --filter name=lums
```

Check the logs:

```bash
docker logs lums
```

Follow the logs:

```bash
docker logs -f lums
```

Press `Ctrl+C` to stop following the logs.

Verify the port mapping:

```bash
docker port lums
```

Expected:

```text
5000/tcp -> 127.0.0.1:5050
```

Port `5050` is bound only to localhost.

---

# 14. Verify the Container

Check the container state:

```bash
docker inspect lums \
    --format '{{.State.Status}}'
```

Expected:

```text
running
```

Test the local application:

```bash
curl -i http://127.0.0.1:5050/
```

Test the login page:

```bash
curl -i http://127.0.0.1:5050/login
```

The application should respond.

Check the database inside the running container:

```bash
docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print("Database OK")
print("Users:", db.execute("SELECT COUNT(*) FROM users").fetchone()[0])
db.close()
'
```

Check the container restart policy:

```bash
docker inspect lums \
    --format '{{.HostConfig.RestartPolicy.Name}}'
```

Expected:

```text
unless-stopped
```

---

# 15. Configure the Server IP

Determine the server IP address:

```bash
hostname -I
```

Alternative:

```bash
ip -br addr
```

Determine the default route:

```bash
ip route
```

Example:

```text
IP Address
```

Use the IP address that is reachable by the managed clients.

From this point onward, replace:

```text
<LUMS_SERVER_IP>
```

with the actual server IP.

> The IP address must be included in the TLS certificate's Subject Alternative Name.

---

# 16. Create the TLS Certificate

Create the TLS directory:

```bash
sudo mkdir -p /etc/lums/tls
```

Create the OpenSSL configuration:

```bash
sudo tee /etc/lums/tls/lums-openssl.cnf > /dev/null <<'EOF'
[req]
default_bits = 4096
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = DE
ST = NRW
L = Essen
O = LUMS
OU = Lab
CN = lums

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = lums
DNS.2 = container
IP.1 = <LUMS_SERVER_IP>
EOF
```

Edit the configuration and replace:

```text
<LUMS_SERVER_IP>
```

with the real IP address.

Generate the certificate:

```bash
sudo openssl req \
    -x509 \
    -nodes \
    -newkey rsa:4096 \
    -keyout /etc/lums/tls/lums.key \
    -out /etc/lums/tls/lums.crt \
    -days 825 \
    -config /etc/lums/tls/lums-openssl.cnf
```

Protect the private key:

```bash
sudo chown root:root /etc/lums/tls/lums.key
sudo chmod 600 /etc/lums/tls/lums.key
```

Protect the certificate:

```bash
sudo chown root:root /etc/lums/tls/lums.crt
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

Verify the SAN:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -ext subjectAltName
```

The server IP must be present in the SAN.

> A self-signed certificate is suitable for a laboratory environment. A trusted internal CA or publicly trusted certificate may be preferred for production environments.

---

# 17. Configure Nginx

Create the Nginx configuration:

```bash
sudo tee /etc/nginx/sites-available/lums > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;

    server_name _;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name _;

    ssl_certificate /etc/lums/tls/lums.crt;
    ssl_certificate_key /etc/lums/tls/lums.key;

    ssl_protocols TLSv1.2 TLSv1.3;

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

Disable the default Nginx site:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

Enable the LUMS site:

```bash
sudo ln -sf \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

Test the configuration:

```bash
sudo nginx -t
```

Expected:

```text
syntax is ok
test is successful
```

Reload Nginx:

```bash
sudo systemctl reload nginx
```

Check Nginx:

```bash
sudo systemctl status nginx --no-pager
```

---

# 18. Test HTTPS

Test HTTP redirection:

```bash
curl -I \
    http://<LUMS_SERVER_IP>/
```

The response should redirect to HTTPS.

Test HTTPS:

```bash
curl -k -I \
    https://<LUMS_SERVER_IP>/
```

Test the login endpoint:

```bash
curl -k -I \
    https://<LUMS_SERVER_IP>/login
```

The `-k` option allows testing with a self-signed certificate.

Open the following address in a browser:

```text
https://<LUMS_SERVER_IP>/
```

The LUMS login page should appear.

> The browser may display a certificate warning because the certificate is self-signed.

Do not expose port `5000` or `5050` directly to the network.

---

# 19. Configure the Firewall

Install UFW:

```bash
sudo apt install -y ufw
```

Allow SSH:

```bash
sudo ufw allow 22/tcp
```

Allow HTTPS:

```bash
sudo ufw allow 443/tcp
```

Allow HTTP for redirection:

```bash
sudo ufw allow 80/tcp
```

Enable the firewall:

```bash
sudo ufw enable
```

Check the firewall:

```bash
sudo ufw status verbose
```

Verify listening ports:

```bash
sudo ss -tulpn
```

The LUMS application should be bound locally:

```text
127.0.0.1:5050
```

Do not add firewall rules for ports `5000` or `5050`.

> Ensure that SSH access is allowed before enabling UFW on a remote server.

---

# 20. Register a Client

Log in to the LUMS web interface.

Open the client management section.

Register a client using its IP address.

Example:

```text
IP address:
192.168.2.210
```

The server generates a client authentication token.

Store the token securely.

The token is used by the agent in the HTTP Authorization header:

```text
Authorization: Bearer <CLIENT_TOKEN>
```

The agent automatically reports:

- Hostname
- Operating system
- Kernel
- Architecture
- Agent version
- Package inventory
- Available updates
- Last report time

The IP address must be registered correctly before the agent can authenticate.

> The client token must be treated like a password.

---

# 21. Install the Agent

Perform the following steps on the managed Linux client.

Create the agent directory:

```bash
sudo mkdir -p /opt/lums-agent
```

Copy the agent script:

```bash
sudo cp \
    /opt/lums-public/agent/agent.py \
    /opt/lums-agent/agent.py
```

Set ownership:

```bash
sudo chown root:root \
    /opt/lums-agent/agent.py
```

Set permissions:

```bash
sudo chmod 750 \
    /opt/lums-agent/agent.py
```

Check the file:

```bash
ls -l /opt/lums-agent/agent.py
```

If the repository is not available on the client, transfer `agent.py` securely using a method such as SCP.

---

# 22. Configure the Agent Certificate

The agent must trust the LUMS server certificate.

Create the configuration directory:

```bash
sudo mkdir -p /etc/lums
```

Copy the server certificate securely to the client.

Example:

```bash
scp \
    <USER>@<LUMS_SERVER_IP>:/etc/lums/tls/lums.crt \
    /tmp/lums-ca.crt
```

Install the certificate:

```bash
sudo install \
    -o root \
    -g root \
    -m 644 \
    /tmp/lums-ca.crt \
    /etc/lums/ca.crt
```

Remove the temporary file:

```bash
rm -f /tmp/lums-ca.crt
```

Verify the certificate:

```bash
ls -l /etc/lums/ca.crt
```

Verify the certificate:

```bash
openssl x509 \
    -in /etc/lums/ca.crt \
    -noout \
    -subject \
    -dates
```

The certificate must match the certificate used by Nginx.

---

# 23. Configure Agent Authentication

Create the agent configuration file:

```bash
sudo tee /etc/default/lums-agent > /dev/null <<'EOF'
LUMS_BASE="https://<LUMS_SERVER_IP>"
LUMS_TOKEN="PUT_CLIENT_TOKEN_HERE"
LUMS_CA_FILE="/etc/lums/ca.crt"
EOF
```

Replace:

```text
<LUMS_SERVER_IP>
```

with the LUMS server IP.

Replace:

```text
PUT_CLIENT_TOKEN_HERE
```

with the token generated during client registration.

Protect the file:

```bash
sudo chown root:root \
    /etc/default/lums-agent
```

```bash
sudo chmod 600 \
    /etc/default/lums-agent
```

Verify the server URL without displaying the token:

```bash
sudo grep '^LUMS_BASE=' \
    /etc/default/lums-agent
```

Verify the CA file:

```bash
sudo grep '^LUMS_CA_FILE=' \
    /etc/default/lums-agent
```

Verify that the token exists:

```bash
sudo grep -q '^LUMS_TOKEN=.' \
    /etc/default/lums-agent \
    && echo "Token vorhanden"
```

Check permissions:

```bash
sudo stat -c '%U:%G %a %n' \
    /etc/default/lums-agent
```

Expected:

```text
root:root 600 /etc/default/lums-agent
```

---

# 24. Test the Agent Manually

The agent reads its configuration from environment variables.

When running the Python script directly, load the configuration explicitly:

```bash
sudo bash -c '
    source /etc/default/lums-agent
    export LUMS_BASE
    export LUMS_TOKEN
    export LUMS_CA_FILE
    exec /usr/bin/python3 /opt/lums-agent/agent.py
'
```

A successful run should include:

```text
LUMS // UPDATE AGENT
AGENT 1.5.2

SYSTEM
HOST ...
IP ...
OS ...
ARCH ...
KERNEL ...

LUMS CHANNEL
REPORT      Sending system report...
REPORT ACCEPTED

CLIENT AUTHENTICATED
NO UPDATE JOB
```

The exact output depends on the client.

Expected successful results include:

```text
REPORT ACCEPTED
CLIENT AUTHENTICATED
```

If there is no pending update job:

```text
NO UPDATE JOB // SYSTEM CLEAN
```

The agent should complete its cycle and exit successfully.

Check the return code:

```bash
echo $?
```

Expected:

```text
0
```

> The direct test must load `/etc/default/lums-agent`. Systemd loads the file automatically when using the service.

---

# 25. Install the systemd Service

Create the service file:

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

Check the service configuration:

```bash
systemctl cat lums-agent.service
```

Run the service manually:

```bash
sudo systemctl start lums-agent.service
```

Check the service status:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager \
    -l
```

A successful oneshot service normally returns to:

```text
inactive (dead)
```

This is expected if the service completed successfully.

Verify the exit status:

```bash
sudo systemctl show \
    lums-agent.service \
    --property=ExecMainStatus
```

Expected:

```text
ExecMainStatus=0
```

---

# 26. Install the systemd Timer

Create the timer:

```bash
sudo tee /etc/systemd/system/lums-agent.timer > /dev/null <<'EOF'
[Unit]
Description=LUMS Linux Update Management Agent Timer

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Persistent=true
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
sudo systemctl enable --now \
    lums-agent.timer
```

Check the timer:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager \
    -l
```

List the timer:

```bash
systemctl list-timers --all | grep lums-agent
```

The timer configuration means:

| Setting | Meaning |
|---|---|
| `OnBootSec=2min` | First execution approximately two minutes after boot |
| `OnUnitActiveSec=15min` | Repeat approximately every 15 minutes |
| `Persistent=true` | Attempt to run after a missed execution |
| `Unit=lums-agent.service` | Start the agent service |

The timer starts the oneshot service:

```text
lums-agent.timer
       |
       v
lums-agent.service
       |
       v
agent.py
```

The service itself does not need to be permanently active. The timer starts it when required.

---

# 27. Verify Automatic Execution

Check the next scheduled execution:

```bash
systemctl list-timers \
    --all | grep lums-agent
```

Check the timer configuration:

```bash
systemctl cat lums-agent.timer
```

Trigger a manual execution:

```bash
sudo systemctl start lums-agent.service
```

Read the service log:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Follow the service log:

```bash
sudo journalctl \
    -u lums-agent.service \
    -f
```

Press `Ctrl+C` to stop following the log.

Look for:

```text
REPORT ACCEPTED
CLIENT AUTHENTICATED
```

Check the last execution:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager \
    -l
```

Check the timer:

```bash
sudo systemctl is-active \
    lums-agent.timer
```

Expected:

```text
active
```

---

# 28. Update Job Workflow

The general update workflow is:

```text
LUMS Web UI
     |
     v
LUMS API
     |
     v
Update Job Created
     |
     v
Agent Retrieves Pending Job
     |
     v
Agent Executes APT Operation
     |
     v
Agent Reports Result
     |
     v
LUMS Stores Result
```

Possible job states include:

```text
pending
running
success
failed
```

Before testing an update job:

1. Confirm the client is online.
2. Confirm the agent authentication works.
3. Confirm the client has reported its inventory.
4. Confirm the agent timer is active.
5. Confirm the package manager is available.

Create an update job through the LUMS web interface.

The agent retrieves pending jobs during its execution cycle.

The result should be reported to the server.

> Only test update jobs on systems where package updates are approved and where a recovery plan exists.

---

# 29. Backup

The most important LUMS data is stored in the Docker volume:

```text
lums-data
```

The SQLite database is located inside the container at:

```text
/var/lib/lums/lums.db
```

## 29.1 Create a Database Backup

Create a backup directory:

```bash
sudo mkdir -p /var/backups/lums
```

Copy the database from the container:

```bash
sudo docker cp \
    lums:/var/lib/lums/lums.db \
    /var/backups/lums/lums.db.backup
```

Protect the backup:

```bash
sudo chmod 600 \
    /var/backups/lums/lums.db.backup
```

Verify the backup:

```bash
sudo ls -lh \
    /var/backups/lums/lums.db.backup
```

## 29.2 Verify the Backup Database

```bash
sudo python3 -c '
import sqlite3

db = sqlite3.connect(
    "/var/backups/lums/lums.db.backup"
)

print("Backup database readable")

tables = db.execute(
    "SELECT name FROM sqlite_master WHERE type=\"table\""
).fetchall()

print("Tables:", len(tables))
db.close()
'
```

## 29.3 Backup Important Configuration

Back up the following files through a secure backup process:

```text
/etc/lums/docker/lums.env
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

The following files may contain authentication secrets:

```text
/etc/default/lums-agent
```

Do not store these files in a public Git repository.

---

# 30. Restore

> Perform restoration only after verifying the backup and ensuring that the LUMS container is stopped.

Stop the container:

```bash
docker stop lums
```

Copy the database backup into the Docker volume using a temporary container:

```bash
docker run --rm \
    -v lums-data:/var/lib/lums \
    -v /var/backups/lums:/backup:ro \
    lums:latest \
    sh -c '
        cp /backup/lums.db.backup \
           /var/lib/lums/lums.db
    '
```

Start the container:

```bash
docker start lums
```

Check the logs:

```bash
docker logs --tail 100 lums
```

Verify the database:

```bash
docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print("Users:", db.execute("SELECT COUNT(*) FROM users").fetchone()[0])
db.close()
'
```

> Always verify the restored database before using the application.

---

# 31. Security Checklist

## 31.1 Server Security

```text
[ ] System is updated
[ ] Docker is installed from a trusted source
[ ] Nginx is enabled
[ ] HTTPS is enabled
[ ] TLS private key is protected
[ ] Port 5000 is not publicly exposed
[ ] Port 5050 is not publicly exposed
[ ] Firewall is enabled
[ ] SSH access is protected
[ ] LUMS secret key is stored outside the image
[ ] Database uses persistent storage
```

## 31.2 Agent Security

```text
[ ] Agent configuration is protected
[ ] Client token is not published
[ ] HTTPS is used
[ ] CA certificate is configured
[ ] Agent script is owned by root
[ ] Agent service uses a protected environment file
[ ] Timer is active
[ ] Authentication was tested
```

## 31.3 Secrets That Must Not Be Committed

```text
/etc/lums/docker/lums.env
/etc/default/lums-agent
/etc/lums/tls/lums.key
Client authentication tokens
Administrator passwords
Private backup files
```

Review the Git status:

```bash
git status --short
```

Review ignored files:

```bash
git check-ignore -v \
    /etc/lums/docker/lums.env
```

System configuration files outside the repository should never be copied into the repository for convenience.

---

# 32. Troubleshooting

The most important troubleshooting rule is:

> Do not reinstall everything immediately. Find the layer where the problem occurs.

## 32.1 Check Docker

```bash
docker ps
```

```bash
docker logs lums
```

```bash
docker inspect lums
```

Check the container state:

```bash
docker inspect lums \
    --format '{{.State.Status}}'
```

## 32.2 Check Nginx

```bash
sudo nginx -t
```

```bash
sudo systemctl status nginx --no-pager
```

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

## 32.3 Check HTTPS

```bash
curl -k -I \
    https://<LUMS_SERVER_IP>/login
```

Check the certificate:

```bash
openssl s_client \
    -connect <LUMS_SERVER_IP>:443 \
    -servername lums \
    </dev/null
```

Verify the SAN:

```bash
openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -ext subjectAltName
```

## 32.4 Agent Token Errors

If the agent reports:

```text
LUMS_TOKEN ist nicht gesetzt.
```

Check the configuration:

```bash
sudo grep -q '^LUMS_TOKEN=.' \
    /etc/default/lums-agent \
    && echo "Token vorhanden"
```

For a direct Python test, explicitly load the environment file:

```bash
sudo bash -c '
    source /etc/default/lums-agent
    export LUMS_BASE LUMS_TOKEN LUMS_CA_FILE
    exec /usr/bin/python3 /opt/lums-agent/agent.py
'
```

The systemd service loads the environment file automatically.

## 32.5 TLS Errors

Check the CA file:

```bash
sudo ls -l \
    /etc/lums/ca.crt
```

Check the configured path:

```bash
sudo grep '^LUMS_CA_FILE=' \
    /etc/default/lums-agent
```

Check the certificate:

```bash
openssl x509 \
    -in /etc/lums/ca.crt \
    -noout \
    -subject \
    -dates
```

The certificate must match the server certificate and contain the correct server IP in its SAN.

## 32.6 Agent Service Errors

Check the service:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager \
    -l
```

Check the logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Run the agent directly with its environment:

```bash
sudo bash -c '
    source /etc/default/lums-agent
    export LUMS_BASE LUMS_TOKEN LUMS_CA_FILE
    exec /usr/bin/python3 /opt/lums-agent/agent.py
'
```

## 32.7 Timer Errors

Check the timer:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager \
    -l
```

List all timers:

```bash
systemctl list-timers --all
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Restart the timer:

```bash
sudo systemctl restart \
    lums-agent.timer
```

Check the timer configuration:

```bash
systemctl cat lums-agent.timer
```

## 32.8 Database Errors

Check the volume:

```bash
docker volume inspect lums-data
```

Check the database:

```bash
docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print("Database readable")
print("Users:", db.execute("SELECT COUNT(*) FROM users").fetchone()[0])
db.close()
'
```

Do not delete the Docker volume as a first troubleshooting step.

## 32.9 Network Errors

Check connectivity:

```bash
ping -c 4 <LUMS_SERVER_IP>
```

Check HTTPS connectivity:

```bash
curl -k -I \
    https://<LUMS_SERVER_IP>/login
```

Check listening ports:

```bash
sudo ss -tulpn
```

Check the firewall:

```bash
sudo ufw status verbose
```

---

# 33. Final Verification

The installation is complete when the following checks are successful.

## Server

```text
[ ] Ubuntu server is installed
[ ] System is updated
[ ] Docker is installed
[ ] Docker service is active
[ ] Nginx is installed
[ ] Git is installed
[ ] LUMS repository is cloned
[ ] Docker image builds successfully
[ ] lums-data volume exists
[ ] Database is initialized
[ ] Security migration completed
[ ] Administrator account exists
[ ] LUMS container is running
[ ] Container restart policy is configured
[ ] Database is persistent
```

## HTTPS

```text
[ ] TLS certificate was generated
[ ] Server IP exists in the SAN
[ ] TLS private key is protected
[ ] Nginx configuration is valid
[ ] HTTP redirects to HTTPS
[ ] HTTPS reaches the LUMS application
[ ] Port 5000 is not exposed
[ ] Port 5050 is not exposed
```

## Agent

```text
[ ] Agent directory exists
[ ] Agent script is installed
[ ] CA certificate is installed
[ ] LUMS_BASE is configured
[ ] LUMS_TOKEN is configured
[ ] LUMS_CA_FILE is configured
[ ] Configuration permissions are protected
[ ] Manual agent test succeeds
[ ] Report is accepted
[ ] Client authentication succeeds
[ ] Client information appears in the web interface
```

## Timer

```text
[ ] Service file exists
[ ] Timer file exists
[ ] systemd daemon was reloaded
[ ] Timer is enabled
[ ] Timer is active
[ ] Next execution is visible
[ ] Service executes successfully
[ ] Journal contains successful report
```

## Update Management

```text
[ ] Client is registered
[ ] Package inventory is reported
[ ] Available updates are detected
[ ] Update job can be created
[ ] Agent retrieves pending jobs
[ ] Update result is reported
[ ] Update history is stored
[ ] Post-update inventory is reported
```

## Backup

```text
[ ] Database backup was created
[ ] Backup is readable
[ ] Backup permissions are protected
[ ] Configuration backup strategy exists
[ ] Restore procedure is documented
```

---

# Final Architecture

```text
                    LUMS SERVER
                Ubuntu Linux Host
                         |
          +--------------+--------------+
          |                             |
        Nginx                         Docker
       HTTPS :443                  LUMS :5000
          |                             |
          |                       +-----+-----+
          |                       | Flask     |
          |                       | Web UI    |
          |                       | REST API  |
          |                       +-----+-----+
          |                             |
          |                        lums-data
          |                             |
          +--------------+--------------+
                         |
                    HTTPS + Token
                         |
          +--------------+--------------+
          |                             |
   Linux Client                  Linux Client
   Native Agent                  Native Agent
          |                             |
   systemd Timer                 systemd Timer
          |                             |
       APT/dpkg                      APT/dpkg
```

## Final Component Summary

```text
LUMS Server      -> Docker container
Web Interface    -> Flask application
Reverse Proxy    -> Nginx
HTTPS            -> TLS certificate
Database         -> Persistent Docker volume
Agent            -> Native Python application
Scheduling       -> systemd timer
Package Manager  -> APT/dpkg
Authentication    -> Client Bearer Token
System Inventory -> Agent report
```

---

# Installation Complete

LUMS is designed to provide centralized Linux update management while keeping the managed agent lightweight and native to the operating system.

The server manages the platform.

The agent manages communication and local system operations.

The Docker volume preserves the database.

Nginx provides HTTPS access.

The systemd timer schedules periodic agent execution.

> **LUMS — Linux Update Management without the noise.**
>
> `segfault // override`
