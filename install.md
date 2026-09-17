# LUMS Installation Guide

## Linux Update Management Server

This document describes how to install LUMS from scratch.

The guide is deliberately written for users who may have little or no Linux experience.

Follow the steps in order.

> **Important:** Do not skip verification steps during the first installation. They make troubleshooting much easier later.

---

# 1. What We Are Building

At the end of this guide you will have:

```text
                    LUMS SERVER
                 Ubuntu Server 26.04
                         │
                ┌────────┴────────┐
                │                 │
              Nginx             Flask
             HTTPS :443       127.0.0.1:5000
                                  │
                                  ▼
                               SQLite
                                  ▲
                                  │
                           HTTPS + Token
                                  │
                         ┌────────┴────────┐
                         │                 │
                    Linux Client      Linux Client
                    LUMS Agent        LUMS Agent
```

The server provides:

* Web interface
* API
* Client management
* Update jobs
* Database
* Authentication
* HTTPS

The client provides:

* System inventory
* Update detection
* Update execution
* Result reporting

---

# 2. Prerequisites

## Server

Recommended:

```text
Ubuntu Server 26.04 LTS
2 CPU cores
2–4 GB RAM
20 GB disk
working network connection
```

The server needs an IP address that clients can reach.

Example:

```text
 IP adress
```

Replace this address with the actual address of your server.

---

# 3. Open a Terminal

If you are using Ubuntu Server directly, you normally see a terminal after login.

If you are connecting remotely from another computer, use SSH:

```bash
ssh username@SERVER_IP
```

Example:

```bash
ssh admin@IP adress
```

---

# 4. Check the Operating System

Run:

```bash
cat /etc/os-release
```

You should see Ubuntu information.

Check the kernel:

```bash
uname -a
```

Check the architecture:

```bash
uname -m
```

Check Python:

```bash
python3 --version
```

---

# 5. Update Ubuntu

Before installing LUMS:

```bash
sudo apt update
```

Optionally install currently available system updates:

```bash
sudo apt upgrade
```

If asked for confirmation, answer:

```text
Y
```

After a major system update, reboot if Ubuntu requests it:

```bash
sudo reboot
```

Reconnect after the reboot.

---

# 6. Install Required Packages

Install the required software:

```bash
sudo apt install -y \
    python3 \
    python3-flask \
    python3-argon2 \
    sqlite3 \
    nginx \
    git \
    openssl \
    curl \
    rsync
```

Verify Python:

```bash
python3 --version
```

Verify SQLite:

```bash
sqlite3 --version
```

Verify Nginx:

```bash
nginx -v
```

Verify Git:

```bash
git --version
```

Verify OpenSSL:

```bash
openssl version
```

---

# 7. Create the LUMS Service User

LUMS should not run as root.

Create a dedicated system account:

```bash
sudo useradd \
    --system \
    --create-home \
    --home-dir /home/lums \
    --shell /usr/sbin/nologin \
    lums
```

Check it:

```bash
getent passwd lums
```

The shell should be:

```text
/usr/sbin/nologin
```

This account exists specifically for the LUMS service.

---

# 8. Create Required Directories

Run:

```bash
sudo mkdir -p /opt/lums-api
sudo mkdir -p /var/lib/lums
sudo mkdir -p /etc/lums/tls
```

Set ownership:

```bash
sudo chown lums:lums /opt/lums-api
sudo chown lums:lums /var/lib/lums

sudo chown root:root /etc/lums
sudo chown root:root /etc/lums/tls
```

Set permissions:

```bash
sudo chmod 750 /opt/lums-api
sudo chmod 750 /var/lib/lums
sudo chmod 750 /etc/lums
sudo chmod 750 /etc/lums/tls
```

---

# 9. Download LUMS

Go to `/opt`:

```bash
cd /opt
```

Clone the repository:

```bash
sudo git clone https://github.com/NovaForgeCtrl/LUMS.git lums-public
```

Enter the repository:

```bash
cd /opt/lums-public
```

Check:

```bash
sudo git status
```

---

# 10. Install the Server Application

Copy the server application:

```bash
sudo rsync -a \
    --delete \
    --exclude='.git/' \
    /opt/lums-public/server/ \
    /opt/lums-api/
```

Set ownership:

```bash
sudo chown -R lums:lums /opt/lums-api
```

Set directory permissions:

```bash
sudo chmod 750 /opt/lums-api
```

Check:

```bash
ls -la /opt/lums-api
```

You should see files such as:

```text
app.py
create_admin.py
init_db.py
security.py
security_migration.py
static/
templates/
```

---

# 11. Create the Server Secret

LUMS requires a secret key.

Generate one:

```bash
sudo sh -c 'umask 077; printf "LUMS_SECRET_KEY=%s\n" "$(openssl rand -hex 64)" > /etc/lums/lums.env'
```

Set ownership:

```bash
sudo chown root:lums /etc/lums/lums.env
```

Set permissions:

```bash
sudo chmod 640 /etc/lums/lums.env
```

Verify that the variable exists without displaying the secret:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' /etc/lums/lums.env \
    && echo "LUMS_SECRET_KEY vorhanden"
```

Never copy the secret into this documentation.

---

# 12. Initialize the Database

Run:

```bash
sudo -u lums python3 /opt/lums-api/init_db.py
```

The database should be created at:

```text
/var/lib/lums/lums.db
```

Set permissions:

```bash
sudo chmod 640 /var/lib/lums/lums.db
```

Check:

```bash
ls -l /var/lib/lums/lums.db
```

---

# 13. Create the Administrator

Run:

```bash
sudo -u lums python3 /opt/lums-api/security_migration.py
```

Follow the prompts.

Create an administrator account.

Use a strong password.

Do not store the password in this document.

---

# 14. Create the LUMS systemd Service

Create:

```bash
sudo tee /etc/systemd/system/lums.service > /dev/null <<'EOF'
[Unit]
Description=LUMS API
After=network.target

[Service]
Type=simple
User=lums
Group=lums
WorkingDirectory=/opt/lums-api
EnvironmentFile=/etc/lums/lums.env
ExecStart=/usr/bin/python3 /opt/lums-api/app.py
Restart=on-failure
RestartSec=5

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/lib/lums

[Install]
WantedBy=multi-user.target
EOF
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Start LUMS:

```bash
sudo systemctl start lums.service
```

Check:

```bash
sudo systemctl status lums.service
```

Look for:

```text
Active: active (running)
```

---

# 15. Test Flask

Run:

```bash
curl -i http://127.0.0.1:5000/api/health
```

Expected:

```text
HTTP/1.1 200 OK
```

and:

```json
{
  "service": "LUMS API",
  "status": "ok"
}
```

Check the listening address:

```bash
sudo ss -lntp | grep ':5000'
```

It should contain:

```text
127.0.0.1:5000
```

Do not continue until this works.

---

# 16. Determine the Server IP

Run:

```bash
ip addr
```

or:

```bash
hostname -I
```

Find the address that clients will use.

Example:

```text
Ip  adress
```

From this point onward, this guide uses:

```text
Ip adress
```

Replace it with your actual address.

---

# 17. Create the TLS Configuration

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
IP.1 = IP adress
EOF
```

**Important:**

Change:

```text
IP.1 = IP adress
```

to the actual LUMS server IP.

---

# 18. Generate the TLS Certificate

Run:

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

Certificate:

```bash
sudo chmod 644 /etc/lums/tls/lums.crt
```

Check the certificate:

```bash
openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -dates
```

Check the SAN:

```bash
openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -ext subjectAltName
```

The server IP should be present.

---

# 19. Configure Nginx

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
        proxy_pass http://127.0.0.1:5000;

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

Reload:

```bash
sudo systemctl reload nginx
```

---

# 20. Test HTTPS

Run:

```bash
curl -k -i https:// IP adress/api/health
```

Expected:

```text
HTTP/1.1 200 OK
```

The `-k` is used because the certificate is self-signed.

---

# 21. Configure the Firewall

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

Do **not** open port 5000.

---

# 22. Open the Web Interface

Open:

```text
https:// IP adress/
```

Because the lab uses a self-signed certificate, the browser may display a certificate warning.

That is expected.

---

# 23. Install the Linux Agent

On the client:

```bash
sudo mkdir -p /opt/lums-agent
```

Copy the agent:

```bash
sudo cp \
    ~/lums-public/agent/agent.py \
    /opt/lums-agent/agent.py
```

Set ownership:

```bash
sudo chown root:root /opt/lums-agent/agent.py
```

Set executable permissions:

```bash
sudo chmod 755 /opt/lums-agent/agent.py
```

---

# 24. Test Client Connectivity

From the client:

```bash
curl -k https:// IP adress/api/health
```

Expected:

```json
{
  "service": "LUMS API",
  "status": "ok"
}
```

If this does not work, stop here and use `TROUBLESHOOTING.md`.

---

# 25. Register the Client

Create the client in LUMS.

Record its client ID.

Example:

```text
Client ID: 1
Hostname: test
```

Generate an authentication token.

The token must be treated as a password.

---

# 26. Configure the Agent

Create:

```bash
sudo tee /etc/default/lums-agent > /dev/null <<'EOF'
LUMS_BASE=https:// IP adress
LUMS_TOKEN=PUT_CLIENT_TOKEN_HERE
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
EOF
```

Replace:

```text
PUT_CLIENT_TOKEN_HERE
```

with the actual client token.

Protect the file:

```bash
sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

Verify the token exists without printing it:

```bash
sudo grep -q '^LUMS_TOKEN=.' /etc/default/lums-agent \
    && echo "Token vorhanden"
```

---

# 27. Install the LUMS Certificate on the Client

Copy the server certificate to the client.

For example:

```bash
scp username@IP address:/etc/lums/tls/lums.crt /tmp/lums.crt
```

Install:

```bash
sudo install \
    -o root \
    -g root \
    -m 644 \
    /tmp/lums.crt \
    /opt/lums-agent/lums-ca.crt
```

---

# 28. Test TLS

Run:

```bash
sudo env \
    LUMS_BASE="https://IP adress" \
    LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt" \
    python3 - <<'PY'
import ssl
import urllib.request

context = ssl.create_default_context(
    cafile="/opt/lums-agent/lums-ca.crt"
)

with urllib.request.urlopen(
    "https://IP adress/api/health",
    context=context
) as response:
    print(response.status)
    print(response.read().decode())
PY
```

Expected:

```text
200
{"service":"LUMS API","status":"ok"}
```

---

# 29. Test Agent Authentication

Run:

```bash
sudo env \
    LUMS_BASE="https://IP adress" \
    LUMS_TOKEN="$(sudo awk -F= '/^LUMS_TOKEN=/{print $2}' /etc/default/lums-agent)" \
    LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt" \
    python3 - <<'PY'
import sys

sys.path.insert(0, "/opt/lums-agent")

import agent

client = agent.get_client()

print("Client-ID:", client["id"])
print("Hostname:", client["hostname"])
print("Enabled:", client["enabled"])
PY
```

Expected:

```text
Client-ID: 1
Hostname: test
Enabled: True
```

---

# 30. Run the Agent Manually

```bash
sudo env \
    LUMS_BASE="https://IP adress" \
    LUMS_TOKEN="$(sudo awk -F= '/^LUMS_TOKEN=/{print $2}' /etc/default/lums-agent)" \
    LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt" \
    python3 /opt/lums-agent/agent.py
```

The agent should:

1. identify itself
2. collect updates
3. send a report
4. check for an update job

If no job exists, it should report:

```text
Kein Update-Job vorhanden.
```

---

# 31. Install the Agent Service

Copy:

```bash
sudo cp \
    ~/lums-public/agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
```

---

# 32. Install the Agent Timer

Copy:

```bash
sudo cp \
    ~/lums-public/agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer
```

Reload:

```bash
sudo systemctl daemon-reload
```

Enable:

```bash
sudo systemctl enable --now lums-agent.timer
```

Check:

```bash
systemctl status lums-agent.timer
```

---

# 33. Check Timer Schedule

```bash
systemctl list-timers lums-agent.timer
```

The default configuration is:

```text
OnBootSec=2min
OnUnitActiveSec=15min
Persistent=true
```

---

# 34. Perform the First Complete Test

Start the agent:

```bash
sudo systemctl start lums-agent.service
```

Check:

```bash
sudo systemctl status lums-agent.service
```

Read the logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Then open the LUMS web interface.

The client should now be visible.

---

# 35. Test an Update Job

Create an update job for a test client.

The client will retrieve it during its next agent run.

The job should transition through states such as:

```text
pending
   ↓
running
   ↓
success
```

The package results should be visible afterwards.

---

# 36. Verify the Final State

On the client:

```bash
apt list --upgradable 2>/dev/null
```

If no updates remain, there should be no package entries.

Then run:

```bash
sudo systemctl start lums-agent.service
```

The fresh report will update the inventory on the server.

---

# 37. Installation Complete

The installation is complete when:

```text
[ ] LUMS service is active
[ ] Nginx is active
[ ] HTTPS works
[ ] Flask is only listening locally
[ ] Firewall is enabled
[ ] Administrator can log in
[ ] Client exists
[ ] Client authentication works
[ ] Agent report works
[ ] Timer works
[ ] Update job works
[ ] Update result is stored
[ ] Post-update report works
```

For daily operation continue with:

[`administration.md`](administration.md)

For problems:

[`troubleshooting.md`](troubleshooting.md)
