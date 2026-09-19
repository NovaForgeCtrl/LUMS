# LUMS Installation Guide

## Linux Update Management Server

**LUMS** is a self-hosted Linux update management platform consisting of a central server and lightweight agents.

The LUMS server runs inside a **Docker container**.
The LUMS agent runs **natively on each managed Linux system** because it needs direct access to the host's package manager, system information and systemd.

This guide describes a complete installation from scratch.

It is deliberately written so that users with limited Linux experience can follow it step by step.

> **Important:** Do not skip verification steps during the first installation. They make troubleshooting significantly easier.

---

# 1. Architecture

The current LUMS architecture separates the central management platform from the systems being managed.

```text
                         LUMS SERVER
                    Linux Host / Ubuntu Server
                              │
                    ┌─────────┴─────────┐
                    │                   │
                 Nginx               Docker
                HTTPS :443          LUMS :5000
                    │                   │
                    │              ┌────┴────┐
                    │              │ Flask   │
                    │              │ Web UI  │
                    │              │ API     │
                    │              └────┬────┘
                    │                   │
                    │              lums-data
                    │                   │
                    └───────────────────┘
                              ▲
                              │ HTTPS
                              │ Bearer Token
                              │
             ┌────────────────┴────────────────┐
             │                                 │
       Linux Client                      Linux Client
       Native Agent                     Native Agent
             │                                 │
       systemd Timer                    systemd Timer
             │                                 │
          APT/dpkg                         APT/dpkg
```

## Server

The central LUMS server provides:

* Web interface
* REST API
* Client management
* Authentication
* Update jobs
* Package inventory
* Update history
* Audit logging
* SQLite database
* HTTPS access through Nginx

## Agent

The LUMS agent provides:

* System inventory
* Package inventory
* Update detection
* Update execution
* Job retrieval
* Result reporting
* Periodic communication with the LUMS server

The agent intentionally remains **outside Docker**.

> The server manages Linux systems. The agent needs direct access to the Linux system it manages.

---

# 2. Prerequisites

## LUMS Server

Recommended:

```text
Ubuntu Server 26.04 LTS
2 CPU cores
2–4 GB RAM
20 GB disk
working network connection
Docker
Nginx
```

The server needs a stable IP address that managed clients can reach.

Example:

```text
LUMS server IP:
192.168.2.226
```

Throughout this guide, replace:

```text
<LUMS_SERVER_IP>
```

with the actual server address.

---

## Managed Linux Client

The agent requires:

```text
Linux system
Python 3
systemd
APT-compatible package management
network access to the LUMS server
```

The agent is designed to run directly on the managed system.

---

# 3. Prepare the LUMS Server

Update the system:

```bash
sudo apt update
```

Optionally install available updates:

```bash
sudo apt upgrade
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

Check the installation:

```bash
docker --version
```

Add the current user to the Docker group:

```bash
sudo usermod -aG docker "$USER"
```

Apply the new group membership:

```bash
newgrp docker
```

Test Docker:

```bash
docker ps
```

The command should complete without requiring `sudo`.

---

# 5. Install Supporting Tools

Install the tools required for the LUMS host and reverse proxy:

```bash
sudo apt install -y \
    nginx \
    git \
    openssl \
    curl
```

Verify:

```bash
nginx -v
```

```bash
git --version
```

```bash
openssl version
```

---

# 6. Download LUMS

Clone the repository:

```bash
cd /opt
```

```bash
sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public
```

Enter the repository:

```bash
cd /opt/lums-public
```

Check the working tree:

```bash
sudo git status
```

---

# 7. Review the Docker Build Files

The repository contains the files required to build the LUMS server container:

```text
Dockerfile
.dockerignore
server/
```

The server dependencies are defined in:

```text
server/requirements.txt
```

The container contains:

```text
Flask
Argon2
LUMS Web UI
LUMS API
SQLite support
security components
```

The production database is **not stored inside the Docker image**.

---

# 8. Build the LUMS Container

Build the image:

```bash
docker build -t lums:latest .
```

Verify the image:

```bash
docker images lums
```

You should see:

```text
lums    latest    ...
```

---

# 9. Create Persistent LUMS Storage

The LUMS database must survive container recreation.

Create a Docker volume:

```bash
docker volume create lums-data
```

Verify:

```bash
docker volume ls
```

The volume should contain:

```text
lums-data
```

> **Important:** Never remove the `lums-data` volume unless you intentionally want to remove the LUMS database.

---

# 10. Create the LUMS Secret

The Flask application requires a secret key.

Create a protected environment file:

```bash
sudo mkdir -p /etc/lums/docker
```

Generate the secret:

```bash
sudo sh -c 'umask 077; printf "LUMS_SECRET_KEY=%s\n" "$(openssl rand -hex 64)" > /etc/lums/docker/lums.env'
```

Protect the directory:

```bash
sudo chown root:docker /etc/lums/docker
sudo chmod 750 /etc/lums/docker
```

Protect the environment file:

```bash
sudo chown root:docker /etc/lums/docker/lums.env
sudo chmod 640 /etc/lums/docker/lums.env
```

Verify without displaying the secret:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' /etc/lums/docker/lums.env \
    && echo "LUMS_SECRET_KEY vorhanden"
```

> **Security:** Never commit `lums.env` to Git and never place the secret inside the Docker image.

---

# 11. Initialize the LUMS Database

Start the container temporarily:

```bash
docker run --rm \
    --env-file /etc/lums/docker/lums.env \
    -v lums-data:/var/lib/lums \
    lums:latest \
    python3 init_db.py
```

The database is created inside the persistent Docker volume:

```text
/var/lib/lums/lums.db
```

The database therefore remains available even when the container is recreated.

---

# 12. Create the Administrator

Run the security migration:

```bash
docker run --rm -it \
    --env-file /etc/lums/docker/lums.env \
    -v lums-data:/var/lib/lums \
    lums:latest \
    python3 security_migration.py
```

Follow the prompts.

Create an administrator account and choose a strong password.

> Do not store the administrator password in this documentation.

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

Check:

```bash
docker ps
```

Expected:

```text
lums    Up ...
```

Check the logs:

```bash
docker logs lums
```

The Flask application should report that it is listening on port `5000`.

> Port `5000` is bound only to `127.0.0.1`. It is not directly exposed to the network.

---

# 14. Test the Container

Test the Flask application locally:

```bash
curl -i http://127.0.0.1:5050/login
```

A successful response should return the LUMS login page.

Check the container:

```bash
docker inspect lums --format '{{.State.Status}}'
```

Expected:

```text
running
```

---

# 15. Verify Persistent Database Storage

Check the database inside the container:

```bash
docker exec lums \
    python3 -c 'import sqlite3; c=sqlite3.connect("/var/lib/lums/lums.db"); print("Database OK"); print("Users:", c.execute("SELECT COUNT(*) FROM users").fetchone()[0]); c.close()'
```

The database must exist before continuing.

---

# 16. Determine the Server IP

Run:

```bash
hostname -I
```

or:

```bash
ip addr
```

Identify the IP address that managed clients will use.

Example:

```text
192.168.2.226
```

From this point onward:

```text
<LUMS_SERVER_IP>
```

means this address.

---

# 17. Create the TLS Certificate

Create the TLS configuration:

```bash
sudo mkdir -p /etc/lums/tls
```

Create:

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
IP.1 = <LUMS_SERVER_IP>
EOF
```

Replace:

```text
<LUMS_SERVER_IP>
```

with the actual server IP.

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
sudo chmod 600 /etc/lums/tls/lums.key
```

Protect the certificate:

```bash
sudo chmod 644 /etc/lums/tls/lums.crt
```

Verify:

```bash
openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -dates
```

Verify the SAN:

```bash
openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -ext subjectAltName
```

The server IP must be present in the SAN.

---

# 18. Configure Nginx

Create:

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

Disable the default site:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

Enable LUMS:

```bash
sudo ln -sf \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

Test:

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

---

# 19. Test HTTPS

Run:

```bash
curl -k -I \
    https://<LUMS_SERVER_IP>/login
```

A response such as:

```text
HTTP/1.1 401 UNAUTHORIZED
```

is expected when the request is unauthenticated.

The important part is that Nginx successfully reaches the LUMS container.

Open:

```text
https://<LUMS_SERVER_IP>/
```

The LUMS login page should appear.

Because the laboratory certificate is self-signed, the browser may display a certificate warning.

---

# 20. Configure the Firewall

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

Optionally allow HTTP for the HTTPS redirect:

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

Do **not** open port `5050` or `5000` to the network.

---

# 21. Register a Linux Client

Log in to the LUMS Web UI.

Open the client management section.

To register a new client, only the **IP address** is required.

Example:

```text
IP address:
192.168.2.210
```

LUMS generates a client authentication token.

> **Important:** Treat the client token like a password. Store it securely and never publish it.

The following information is automatically supplied by the agent after its first successful report:

```text
Hostname
Operating System
Kernel
Architecture
Agent Version
Last Seen
```

There is no need to manually enter this information during client registration.

---

# 22. Install the LUMS Agent

On the Linux client:

```bash
sudo mkdir -p /opt/lums-agent
```

Copy the agent from the LUMS repository:

```bash
sudo cp \
    /opt/lums-public/agent/agent.py \
    /opt/lums-agent/agent.py
```

Set ownership:

```bash
sudo chown root:root /opt/lums-agent/agent.py
```

Set permissions:

```bash
sudo chmod 755 /opt/lums-agent/agent.py
```

If the repository is not present on the client, copy `agent.py` to the client using your preferred secure transfer method.

---

# 23. Install the LUMS CA Certificate

The LUMS agent must trust the LUMS server certificate.

Create the certificate directory:

```bash
sudo mkdir -p /etc/lums
```

Copy the LUMS certificate to the client:

```bash
scp \
    <USER>@<LUMS_SERVER_IP>:/etc/lums/tls/lums.crt \
    /tmp/lums-ca.crt
```

Install it:

```bash
sudo install \
    -o root \
    -g root \
    -m 644 \
    /tmp/lums-ca.crt \
    /etc/lums/ca.crt
```

Verify:

```bash
ls -l /etc/lums/ca.crt
```

---

# 24. Configure the Agent

Create:

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

and:

```text
PUT_CLIENT_TOKEN_HERE
```

with the correct values.

Protect the configuration:

```bash
sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

Verify that the token exists without printing it:

```bash
sudo grep -q '^LUMS_TOKEN=.' /etc/default/lums-agent \
    && echo "Token vorhanden"
```

---

# 25. Test the Agent

Because `/etc/default/lums-agent` is an environment file, load it explicitly for a direct manual test:

```bash
sudo bash -c '
source /etc/default/lums-agent
export LUMS_BASE LUMS_TOKEN LUMS_CA_FILE
exec /usr/bin/python3 /opt/lums-agent/agent.py
'
```

The agent should:

1. identify the local system
2. collect package information
3. detect available updates
4. send a report
5. authenticate the client
6. check for pending update jobs

A successful run contains information similar to:

```text
AGENT 1.5.2

SYSTEM
HOST     update
IP       192.168.2.226
OS       Linux
ARCH     x86_64

LUMS CHANNEL
REPORT      Sending system report...
✓ REPORT ACCEPTED

✓ CLIENT AUTHENTICATED
✓ NO UPDATE JOB // SYSTEM CLEAN
```

The exact values depend on the client.

---

# 26. Install the Agent Service

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

Reload systemd:

```bash
sudo systemctl daemon-reload
```

---

# 27. Install the Agent Timer

Create:

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

Enable the timer:

```bash
sudo systemctl daemon-reload
```

```bash
sudo systemctl enable --now lums-agent.timer
```

Check:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

Expected:

```text
Active: active (waiting)
```

---

# 28. Verify the Timer

List the scheduled execution:

```bash
systemctl list-timers lums-agent.timer
```

The default schedule is:

```text
OnBootSec=2min
OnUnitActiveSec=15min
Persistent=true
```

This means:

* first execution approximately two minutes after boot
* subsequent executions every 15 minutes
* missed executions are handled after downtime because `Persistent=true`

The timer starts the oneshot service:

```text
lums-agent.timer
       │
       ▼
lums-agent.service
```

---

# 29. Verify the Automatic Agent Run

Wait until the timer executes the service, or trigger one manually:

```bash
sudo systemctl start lums-agent.service
```

Read the log:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

A successful run should contain:

```text
REPORT ACCEPTED
CLIENT AUTHENTICATED
```

and either:

```text
NO UPDATE JOB // SYSTEM CLEAN
```

or an update job execution.

---

# 30. Verify the Client in LUMS

Return to the LUMS Web UI.

The client should now contain automatically detected information:

```text
IP address
Hostname
Operating System
Kernel
Architecture
Agent Version
Last Seen
```

The IP address was entered during registration.

The remaining system information was supplied by the agent.

---

# 31. Test an Update Job

Create an update job for the test client.

The workflow is:

```text
LUMS Web UI
     │
     ▼
Docker LUMS API
     │
     ▼
Update Job
     │
     ▼
LUMS Agent
     │
     ▼
APT / Package Manager
     │
     ▼
Package Update
     │
     ▼
Result Report
     │
     ▼
Docker LUMS
```

The job should progress through states such as:

```text
pending
   ↓
running
   ↓
success
```

Package-level results should be visible in LUMS.

---

# 32. Verify the Post-Update State

On the client:

```bash
apt list --upgradable 2>/dev/null
```

If all available updates were successfully installed, no remaining package entries should be shown.

Run the agent again:

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

The updated inventory should be reported back to LUMS.

---

# 33. Verify Docker Persistence

The LUMS container can be recreated without losing the database because the database is stored in the Docker volume.

Check the volume:

```bash
docker volume inspect lums-data
```

Check the database:

```bash
docker exec lums \
    python3 -c 'import sqlite3; c=sqlite3.connect("/var/lib/lums/lums.db"); print("Users:", c.execute("SELECT COUNT(*) FROM users").fetchone()[0]); print("Clients:", c.execute("SELECT COUNT(*) FROM clients").fetchone()[0]); c.close()'
```

> **Important:** The Docker image is disposable. The `lums-data` volume contains persistent LUMS data.

---

# 34. Verify the Complete Architecture

The final installation should look like this:

```text
                         LINUX HOST
                              │
               ┌──────────────┴──────────────┐
               │                             │
             Nginx                     LUMS Agent
             :443                      service/timer
               │                             │
               ▼                             │
        Docker LUMS                         │
        :5000                                │
               │                             │
               ▼                             │
          lums-data                          │
               │                             │
               └────────────── HTTPS ◄───────┘
```

Important separation:

```text
LUMS Server  → Docker
Nginx        → Host
LUMS Agent   → Native Linux
Agent Timer  → Native systemd
Database     → Docker volume
Secrets      → Host filesystem
```

---

# 35. Security Checklist

Verify:

```text
[ ] LUMS secret is outside the Docker image
[ ] Client tokens are protected
[ ] TLS private key is protected
[ ] Port 5000 is not publicly exposed
[ ] Port 5050 is not publicly exposed
[ ] HTTPS is used for agent communication
[ ] Flask is reachable only through the intended path
[ ] UFW is enabled
[ ] Docker database uses persistent storage
[ ] Agent configuration is protected
```

Never commit:

```text
/etc/lums/docker/lums.env
/etc/default/lums-agent
/etc/lums/tls/lums.key
client tokens
administrator passwords
```

to Git.

---

# 36. Backup

The most important persistent LUMS data is stored in:

```text
Docker volume:
lums-data
```

At minimum, back up the SQLite database:

```text
/var/lib/lums/lums.db
```

inside the container.

Example:

```bash
docker cp \
    lums:/var/lib/lums/lums.db \
    /tmp/lums.db.backup
```

For production environments, integrate this database into the regular host backup strategy.

> A container can be recreated. The LUMS database must be preserved.

---

# 37. Troubleshooting

If an installation step fails:

1. Do not immediately reinstall LUMS.
2. Identify the layer where the problem occurs.
3. Check the relevant service or container.
4. Check the logs.
5. Verify network connectivity.
6. Verify authentication.
7. Verify TLS.
8. Only then change configuration.

Useful commands:

```bash
docker ps
```

```bash
docker logs lums
```

```bash
sudo systemctl status nginx
```

```bash
sudo nginx -t
```

```bash
sudo systemctl status lums-agent.timer --no-pager
```

```bash
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

For detailed troubleshooting, continue with:

[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)

---

# 38. Installation Complete

The installation is complete when all of the following are confirmed:

```text
[ ] Docker is installed
[ ] LUMS image builds successfully
[ ] lums-data volume exists
[ ] LUMS container is running
[ ] SQLite database is persistent
[ ] Administrator can log in
[ ] Nginx is active
[ ] HTTPS works
[ ] TLS certificate contains the server IP
[ ] Firewall is enabled
[ ] Client can reach LUMS
[ ] Client is registered by IP
[ ] Agent authentication works
[ ] Agent report works
[ ] Host information is populated automatically
[ ] Agent timer works
[ ] Update job works
[ ] Package results are stored
[ ] Post-update report works
[ ] Docker restart does not lose data
```

---

# 39. Final Architecture

```text
                    ┌─────────────────────────────┐
                    │        LUMS SERVER          │
                    │                             │
                    │      Linux Host             │
                    │                             │
                    │  ┌─────────┐                │
                    │  │ Nginx   │ :443           │
                    │  └────┬────┘                │
                    │       │                     │
                    │       ▼                     │
                    │  ┌───────────────┐          │
                    │  │ Docker        │          │
                    │  │               │          │
                    │  │ LUMS Server   │          │
                    │  │ Flask / API   │          │
                    │  │ Web UI        │          │
                    │  └───────┬───────┘          │
                    │          │                  │
                    │     ┌────▼────┐             │
                    │     │lums-data│             │
                    │     └─────────┘             │
                    └──────────────┬──────────────┘
                                   │
                              HTTPS + Token
                                   │
                ┌──────────────────┴──────────────────┐
                │                                     │
        ┌───────▼────────┐                   ┌────────▼───────┐
        │ Linux Client   │                   │ Linux Client   │
        │                │                   │                │
        │ LUMS Agent     │                   │ LUMS Agent     │
        │ systemd Timer  │                   │ systemd Timer  │
        │ APT / dpkg     │                   │ APT / dpkg     │
        └────────────────┘                   └────────────────┘
```

**LUMS server: containerized.**

**LUMS agent: native.**

**Database: persistent Docker volume.**

**HTTPS: Nginx.**

**Authentication: client token.**

**Client inventory: automatically supplied by the agent.**

---

## Installation complete.

**Linux Update Management without the noise.**
