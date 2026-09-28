# LUMS Installation Guide

## Linux Update Management Server

**Project:** LUMS
**Slogan:** Linux Update Management without the noise.
**Repository:** `NovaForgeCtrl/LUMS`

---

# 1. Overview

LUMS is a centralized Linux update management platform for controlled update distribution, client reporting, update-job management and auditable execution.

The current deployment uses:

* Flask
* Gunicorn
* SQLite
* Docker
* Nginx
* HTTPS/TLS
* Linux Agent
* Execution Watcher
* systemd timers
* Bearer-token authentication
* role-based web authorization
* audit logging
* idle-aware update execution

The current installation separates the management server from the Linux clients.

```text
                    LUMS Server
                         │
                         │ HTTPS
                         ▼
                    ┌─────────┐
                    │  Nginx  │
                    │ TLS     │
                    └────┬────┘
                         │
                         │ HTTP localhost
                         ▼
                 127.0.0.1:5050
                         │
                         ▼
                ┌─────────────────┐
                │ Docker: lums    │
                │                 │
                │ Gunicorn        │
                │ Flask :5000     │
                └────────┬────────┘
                         │
                         ▼
                 lums-data volume
                         │
                         ▼
                  lums.db / SQLite


        Linux Client
             │
             │ HTTPS + Bearer Token
             ▼
        LUMS API
             │
             ▼
      Report / Job / Result
```

The application is not intended to be exposed directly on the network.

The Docker application is bound to:

```text
127.0.0.1:5050 → container:5000
```

Nginx provides the external HTTPS entry point.

---

# 2. Requirements

## 2.1 LUMS Server

The current deployment requires:

* Linux host
* Docker Engine
* Git
* Nginx
* OpenSSL or an existing TLS certificate
* sufficient storage for the SQLite database and Docker image

The LUMS application itself runs inside the Docker container.

The application container uses:

```text
Python 3.13
Gunicorn 23.0.0
Flask
SQLite
```

The production container runs as the unprivileged user:

```text
lums
UID 10001
```

---

## 2.2 Linux Clients

Supported package-manager families currently include:

```text
Debian / Ubuntu
    ↓
APT / dpkg

Arch Linux
    ↓
pacman
```

The client requires:

* Python 3
* systemd
* the appropriate package manager
* network connectivity to the LUMS server
* a valid client token
* TLS trust configuration when using a private CA

The current agent version is:

```text
1.7.0
```

The execution watcher version is:

```text
1.2.1
```

---

# 3. Directory Layout

The recommended server-side layout is:

```text
/opt/lums-public/
    ├── server/
    ├── agent/
    ├── tests/
    ├── requirements.txt
    ├── requirements-dev.txt
    └── ...

/etc/lums/
    ├── docker/
    │   └── lums.env
    ├── secrets/
    │   └── lums_secret
    └── tls/
        ├── lums.crt
        └── lums.key

Docker:
    lums
    lums-data
```

The operational SQLite database is stored inside the Docker volume:

```text
lums-data:/var/lib/lums
```

with the database at:

```text
/var/lib/lums/lums.db
```

The database must not be stored inside the Git working tree.

---

# 4. Clone the Repository

Clone the repository to the intended LUMS installation directory:

```bash
sudo mkdir -p /opt
cd /opt

sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public
```

Enter the repository:

```bash
cd /opt/lums-public
```

Verify the working tree:

```bash
git status
```

The installation should start from a known repository state.

For a controlled deployment, inspect the current commit before building the image:

```bash
git log -1 --oneline --decorate
```

---

# 5. Prepare LUMS Configuration Directories

Create the required configuration directories:

```bash
sudo install -d -m 700 /etc/lums
sudo install -d -m 700 /etc/lums/docker
sudo install -d -m 700 /etc/lums/secrets
sudo install -d -m 700 /etc/lums/tls
```

The directory containing the LUMS secret must not be world-readable.

The TLS directory must also be protected because it contains the private key.

---

# 6. Create the LUMS Secret

Production does not place the Flask secret directly into the normal Docker environment.

Instead, the secret is stored on the host:

```text
/etc/lums/secrets/lums_secret
```

and mounted read-only into the container as:

```text
/run/secrets/lums_secret
```

Create a cryptographically random secret:

```bash
sudo umask 077

openssl rand -hex 32 | \
    sudo tee /etc/lums/secrets/lums_secret > /dev/null

sudo chmod 600 /etc/lums/secrets/lums_secret
```

Verify the permissions without printing the secret:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/secrets/lums_secret
```

The secret itself must never be:

* committed to Git
* included in documentation
* pasted into public issues
* printed into logs
* embedded into the Docker image

The container receives only the file reference:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

---

# 7. Create the Docker Environment File

Create:

```text
/etc/lums/docker/lums.env
```

Example:

```bash
sudo tee /etc/lums/docker/lums.env > /dev/null <<'EOF'
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
EOF
```

Protect the file:

```bash
sudo chmod 600 /etc/lums/docker/lums.env
```

Verify:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/docker/lums.env
```

Do not place passwords, client tokens or the actual Flask secret into this file.

The production secret is provided through the dedicated read-only secret mount.

---

# 8. Build the LUMS Image

From the repository:

```bash
cd /opt/lums-public
```

Build the image:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Verify that the image exists:

```bash
sudo docker image ls lums
```

Before starting the production container, inspect the image configuration:

```bash
sudo docker image inspect lums:latest
```

The image is based on Python 3.13 slim.

---

# 9. Create the Persistent Database Volume

Create the Docker volume:

```bash
sudo docker volume create lums-data
```

Verify it:

```bash
sudo docker volume inspect lums-data
```

The volume provides persistent storage for:

```text
/var/lib/lums/lums.db
```

The database therefore survives container recreation.

The container itself must not be treated as the location of persistent application state.

---

# 10. Start the Hardened Container

The production container uses the following security controls:

* non-root user
* read-only root filesystem
* all Linux capabilities dropped
* no privileged mode
* localhost-only port binding
* read-only secret mount
* persistent database volume
* dedicated `/tmp` tmpfs
* `nosuid`
* `nodev`
* `noexec`

Start the container:

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

Inspect its security configuration:

```bash
sudo docker inspect lums
```

The important properties should include:

```text
User: lums
ReadonlyRootfs: true
Privileged: false
CapDrop: ALL
```

The published port must remain:

```text
127.0.0.1:5050 → 5000/tcp
```

It must not be:

```text
0.0.0.0:5050
```

or directly expose port `5000`.

---

# 11. Initial Container Check

Check the container logs:

```bash
sudo docker logs --tail 100 lums
```

Check the container health/state:

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Expected:

```text
running
```

The application itself is intended to be reached through Nginx after TLS configuration.

The Docker application can be tested locally on the host before exposing it through the reverse proxy.

---

# 12. Database Initialization

The LUMS database is stored in:

```text
lums-data:/var/lib/lums/lums.db
```

Database initialization and security migrations are handled by the LUMS application deployment.

After startup, verify that the database exists:

```bash
sudo docker exec lums \
    ls -l /var/lib/lums/lums.db
```

Do not copy the database into the Git repository.

A production backup should be created separately from the Docker volume and protected accordingly.

# 13. Configure TLS

LUMS should be accessed through HTTPS.

Nginx provides the external TLS endpoint:

```text
Client
   │
   │ HTTPS :443
   ▼
Nginx
   │
   │ HTTP localhost
   ▼
127.0.0.1:5050
   │
   ▼
LUMS container :5000
```

The TLS certificate and private key are stored outside the Docker image.

Recommended paths:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Protect the private key:

```bash
sudo chmod 600 /etc/lums/tls/lums.key
```

The certificate may be readable by Nginx:

```bash
sudo chmod 644 /etc/lums/tls/lums.crt
```

Verify:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

> [!IMPORTANT]
> The TLS private key must never be committed to Git or included in the Docker image.

---

# 14. Configure Nginx

Create an Nginx virtual host for LUMS.

Example:

```bash
sudo tee /etc/nginx/sites-available/lums > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;

    server_name LUMS-SERVER;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name LUMS-SERVER;

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

Replace:

```text
LUMS-SERVER
```

with the hostname or address used by the LUMS installation.

Enable the configuration:

```bash
sudo ln -s \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

If the default site is not required, remove its enabled configuration:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

Test the Nginx configuration:

```bash
sudo nginx -t
```

Expected result:

```text
syntax is ok
test is successful
```

Reload Nginx:

```bash
sudo systemctl reload nginx
```

Check the service:

```bash
sudo systemctl status nginx --no-pager
```

---

# 15. Test HTTPS

From the LUMS server, test the HTTPS endpoint:

```bash
curl -kI https://127.0.0.1/
```

When using a certificate that is trusted by the system, use normal certificate verification instead:

```bash
curl -I https://LUMS-SERVER/
```

The HTTP endpoint should redirect to HTTPS:

```bash
curl -I http://LUMS-SERVER/
```

Expected behavior:

```text
HTTP/1.1 301 ...
Location: https://...
```

Do not use `curl -k` as a permanent client configuration.

It is only useful for testing certificates that are not yet trusted locally.

---

# 16. Verify the Docker Exposure

The LUMS application must remain bound to localhost.

Check the published port:

```bash
sudo docker port lums
```

Expected:

```text
5000/tcp -> 127.0.0.1:5050
```

Check the listening socket:

```bash
sudo ss -lntp | grep -E ':443|:5050|:5000'
```

The intended architecture is:

```text
:443
  │
  ▼
Nginx
  │
  ▼
127.0.0.1:5050
  │
  ▼
Docker :5000
```

Port `5000` must not be exposed directly to the LAN.

Port `5050` must also remain localhost-only.

---

# 17. Create the Initial Administrator

The initial administrator account is created using the LUMS security migration/admin initialization mechanism.

Run the initialization command provided by the repository:

```bash
sudo docker exec -it lums \
    python3 /app/server/security_migration.py \
    --db-path /var/lib/lums/lums.db
```

Follow the prompts for the initial administrator account.

> [!IMPORTANT]
> Use a unique administrator password. Do not reuse a password from another system.

The administrator receives the role:

```text
administrator
```

The current administrative roles are:

```text
administrator
operator
viewer
```

Their permissions are documented in:

```text
docs/security.md
```

---

# 18. Verify the Administrator Role

The database can be inspected from the container without exposing the password or authentication material.

For example:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

connection = sqlite3.connect("/var/lib/lums/lums.db")

row = connection.execute(
    """
    SELECT id, username, enabled, role
    FROM users
    ORDER BY id
    """
).fetchall()

for item in row:
    print(item)

connection.close()
PY
```

A newly created administrator should have:

```text
role = administrator
```

Do not print password hashes or session data for troubleshooting output.

---

# 19. First Web Login

Open the LUMS HTTPS address in a browser:

```text
https://LUMS-SERVER/
```

Log in using the administrator account created during initialization.

After successful authentication, the dashboard should be available.

The web interface is protected by:

* administrator authentication
* session handling
* CSRF protection
* role-based authorization
* security headers

---

# 20. Verify the Security Headers

Check the HTTPS response headers:

```bash
curl -kI https://LUMS-SERVER/
```

The deployment should expose the configured security headers.

Inspect the response rather than assuming that Nginx or Flask configuration is active.

If a header is missing, check:

```bash
sudo nginx -T
```

and:

```bash
sudo docker logs --tail 100 lums
```

---

# 21. Verify the Application Container

Check the running container:

```bash
sudo docker ps --filter name=lums
```

Inspect the effective security configuration:

```bash
sudo docker inspect lums \
    --format='User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}}'
```

The production container should show:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
```

Verify the mounted resources:

```bash
sudo docker inspect lums \
    --format='{{json .Mounts}}'
```

The important mounts are:

```text
lums-data
/etc/lums/secrets/lums_secret
/tmp
```

The secret mount must be read-only.

---

# 22. Verify the Persistent Database

Check the database inside the running container:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

The database must be located below:

```text
/var/lib/lums/
```

and therefore inside:

```text
lums-data
```

Verify the volume:

```bash
sudo docker volume inspect lums-data
```

The Docker volume is persistent and must survive container recreation.

---

# 23. Verify the LUMS Secret Mount

Check that the secret file is available:

```bash
sudo docker exec lums \
    sh -c 'test -r /run/secrets/lums_secret && echo "secret mount: OK"'
```

Do **not** print the contents of the file.

Verify the mount from the host:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Source "->" .Destination "RW=" .RW}}{{end}}'
```

The secret should appear as:

```text
/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
```

---

# 24. Verify Container Restart Persistence

The database must survive a container restart.

Restart the container:

```bash
sudo docker restart lums
```

Wait for startup:

```bash
sleep 5
```

Check:

```bash
sudo docker ps --filter name=lums
```

Then verify the database again:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

The existing database must still be present.

The administrator account and existing LUMS data must not disappear merely because the container was restarted.

---

# 25. Initial Server Validation

Before installing clients, verify the following:

```text
[ ] Docker is installed
[ ] LUMS image builds successfully
[ ] lums container is running
[ ] lums-data volume exists
[ ] SQLite database exists
[ ] LUMS secret exists
[ ] Secret is mounted read-only
[ ] Container runs as non-root
[ ] Root filesystem is read-only
[ ] Linux capabilities are dropped
[ ] Port 5000 is not externally exposed
[ ] Port 5050 is bound to localhost
[ ] Nginx configuration is valid
[ ] HTTP redirects to HTTPS
[ ] HTTPS works
[ ] Administrator account exists
[ ] Administrator can log in
[ ] Database survives container restart
```

Only after these checks should Linux clients be connected to the LUMS server.

---

# 26. Next Step

The next installation stage is the Linux client.

The client installation covers:

```text
Linux client
    ↓
Agent installation
    ↓
Client token
    ↓
TLS trust
    ↓
systemd service
    ↓
systemd timer
    ↓
First report
    ↓
Client registration
```

The next section of this guide documents the installation on Debian/Ubuntu and Arch Linux.

# 27. Install the LUMS Agent

The LUMS Agent runs on every Linux client that should be managed by LUMS.

The agent is responsible for:

* collecting system information
* collecting installed packages
* detecting available updates
* reporting client state
* retrieving assigned update jobs
* claiming jobs
* executing package operations
* reporting update results
* handling interrupted jobs
* detecting reboot requirements

The current agent version is:

```text
1.7.0
```

The agent communicates with the LUMS server using HTTPS and a client-specific Bearer token.

---

# 28. Agent Installation Directory

The recommended installation directory is:

```text
/opt/lums-agent
```

Create it:

```bash
sudo install -d -m 755 /opt/lums-agent
```

The agent itself is installed as:

```text
/opt/lums-agent/agent.py
```

The execution watcher is installed alongside it:

```text
/opt/lums-agent/watcher.py
```

The package-manager abstraction is:

```text
/opt/lums-agent/package_manager.py
```

---

# 29. Obtain the Agent Files

The agent files are included in the LUMS repository.

From the cloned repository:

```bash
cd /opt/lums-public
```

Copy the agent components:

```bash
sudo cp agent/agent.py \
    /opt/lums-agent/agent.py

sudo cp agent/watcher.py \
    /opt/lums-agent/watcher.py

sudo cp agent/package_manager.py \
    /opt/lums-agent/package_manager.py
```

Verify:

```bash
ls -lh /opt/lums-agent/
```

The directory should contain the installed agent components.

---

# 30. Install the systemd Services

The repository contains the systemd service definitions for the reporting agent and execution watcher.

Install the service files:

```bash
sudo cp agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service

sudo cp agent/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent-watcher.service
```

Install the timers:

```bash
sudo cp agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer

sudo cp agent/lums-agent-watcher.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Verify the unit files:

```bash
systemctl cat lums-agent.service
```

and:

```bash
systemctl cat lums-agent-watcher.service
```

---

# 31. Agent Configuration

The agent requires the LUMS server address and client authentication token.

The configuration is stored outside the Git repository.

Use:

```text
/etc/default/lums-agent
```

Protect the configuration:

```bash
sudo install -m 600 /dev/null \
    /etc/default/lums-agent
```

The configuration should contain the LUMS server endpoint and the client token.

Example structure:

```text
LUMS_BASE=https://LUMS-SERVER
LUMS_TOKEN=<CLIENT-TOKEN>
```

Replace:

```text
LUMS-SERVER
```

with the actual LUMS server address.

Replace:

```text
<CLIENT-TOKEN>
```

with the token assigned to this client.

> [!CAUTION]
> Never commit `/etc/default/lums-agent` to Git.
>
> Never publish a real client token in documentation, screenshots or issue reports.

---

# 32. Client Token

Every LUMS client uses its own authentication token.

The token identifies the client to the LUMS API.

The token is sent as a Bearer token:

```text
Authorization: Bearer <CLIENT-TOKEN>
```

The server stores a cryptographic digest of the client token rather than the original token value.

A client token can be rotated by an administrator.

After rotation, the previous token is invalidated.

When a token is replaced:

```text
Old token
    ↓
invalidated

New token
    ↓
stored on client
    ↓
used for future API requests
```

After changing the token, restart or manually run the agent to verify authentication.

---

# 33. TLS Trust

The agent communicates with the LUMS server over HTTPS.

TLS certificate verification must remain enabled.

For a publicly trusted certificate, the normal system trust store can be used.

For a private laboratory CA, install the appropriate CA certificate on the client.

Example location:

```text
/opt/lums-agent/lums-ca.crt
```

The exact CA installation method depends on the Linux distribution.

On Debian/Ubuntu, a private CA can be installed into the system trust store:

```bash
sudo cp lums-ca.crt \
    /usr/local/share/ca-certificates/lums-ca.crt
```

Then update the trust store:

```bash
sudo update-ca-certificates
```

Verify that the CA is accepted by the system before running the agent.

On Arch Linux, install the CA into the appropriate system trust store and update the trust database according to the installed trust-store configuration.

> [!IMPORTANT]
> Do not disable TLS verification merely to make the agent connect.
>
> Fix the certificate or trust configuration instead.

---

# 34. Debian / Ubuntu

The LUMS Agent supports Debian-family systems using APT and dpkg.

Verify Python:

```bash
python3 --version
```

Verify APT:

```bash
command -v apt
```

Verify dpkg:

```bash
command -v dpkg-query
```

Expected package-manager detection:

```text
APT / dpkg
```

Test the installed package inventory:

```bash
dpkg-query -W -f='${binary:Package}\t${Version}\n' | head
```

Test update detection:

```bash
apt list --upgradable
```

The agent uses these package-manager interfaces through the LUMS package-manager abstraction.

---

# 35. Arch Linux

The LUMS Agent supports Arch Linux using pacman.

Verify Python:

```bash
python3 --version
```

Verify pacman:

```bash
command -v pacman
```

Verify installed packages:

```bash
pacman -Q | head
```

Verify available updates:

```bash
pacman -Qu
```

Expected package-manager detection:

```text
pacman
```

The agent does not require the `hostname` command solely for client identification.

The hostname can be obtained from the system hostname configuration.

---

# 36. Verify Agent Permissions

The agent needs sufficient privileges to inspect package state and execute package-management operations.

The systemd service should therefore be configured according to the repository's service definition.

The agent installation directory itself does not need to be writable by the agent.

Verify:

```bash
ls -ld /opt/lums-agent
```

and:

```bash
ls -l /opt/lums-agent/
```

The configuration containing the token should remain protected:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Expected permissions:

```text
600
```

---

# 37. Test the Agent Manually

Before enabling the timer, perform a controlled manual run through systemd.

Start:

```bash
sudo systemctl start lums-agent.service
```

Check the result:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

The agent is a one-shot service.

Therefore, after a successful execution, systemd may show:

```text
Active: inactive (dead)
```

This is expected.

The important result is:

```text
status=0/SUCCESS
```

Inspect the journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

A successful run should report the client information to the LUMS server.

---

# 38. Verify Client Authentication

The LUMS server must accept the client's Bearer token.

A successful report should result in an accepted client report.

The server-side Docker log can be inspected with:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

A successful report should result in an HTTP success response from:

```text
POST /api/report
```

The client must not be considered operational merely because the local agent service starts.

The complete path must work:

```text
Agent
   ↓
HTTPS
   ↓
Nginx
   ↓
LUMS API
   ↓
Bearer authentication
   ↓
Client lookup
   ↓
Report accepted
```

---

# 39. Enable the Reporting Timer

Once the manual run succeeds, enable the reporting timer:

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

Inspect the schedule:

```bash
systemctl list-timers \
    lums-agent.timer \
    --no-pager
```

The timer starts the one-shot agent service according to its configured schedule.

The service itself may return to:

```text
inactive (dead)
```

between executions.

This is normal for a `Type=oneshot` service.

---

# 40. Install the Execution Watcher

The execution watcher is separate from the reporting agent.

Its purpose is to detect and execute pending update jobs while respecting the client's idle state and recovery logic.

The current watcher version is:

```text
1.2.1
```

Verify:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

The watcher is installed as:

```text
lums-agent-watcher.service
```

with its corresponding timer:

```text
lums-agent-watcher.timer
```

---

# 41. Test the Execution Watcher

Run the watcher manually:

```bash
sudo systemctl start \
    lums-agent-watcher.service
```

Check:

```bash
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Inspect the journal:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

The watcher must not execute a job simply because one exists.

The current workflow includes idle-state handling.

The relevant execution flow is:

```text
Pending job
    ↓
Watcher
    ↓
Idle-state check
    ↓
Job lookup
    ↓
Atomic claim
    ↓
Update execution
    ↓
Checkpoint / recovery handling
    ↓
Result reporting
```

---

# 42. Enable the Watcher Timer

After the manual watcher test succeeds:

```bash
sudo systemctl enable --now \
    lums-agent-watcher.timer
```

Check:

```bash
sudo systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Inspect the schedule:

```bash
systemctl list-timers \
    lums-agent-watcher.timer \
    --no-pager
```

The reporting timer and watcher timer are independent:

```text
lums-agent.timer
        │
        ▼
   agent.service
        │
        ▼
    Reporting


lums-agent-watcher.timer
        │
        ▼
watcher.service
        │
        ▼
 Job execution
```

This separation prevents ordinary inventory reporting from being tightly coupled to update execution.

---

# 43. First Client Validation

After the timers are enabled, verify:

```text
[ ] Agent files installed
[ ] Watcher installed
[ ] Client configuration exists
[ ] Client token protected
[ ] TLS verification works
[ ] Agent service runs successfully
[ ] Client report is accepted
[ ] Client appears in the LUMS dashboard
[ ] Agent timer is enabled
[ ] Watcher service starts successfully
[ ] Watcher timer is enabled
[ ] Idle detection works
```

The client is now ready for controlled update-job testing.

The next installation section covers **client registration, update detection, job execution and recovery validation**.

# 44. Verify the Client in LUMS

After the first successful agent report, open the LUMS web interface.

The client should appear in the client overview.

Verify at least:

```text
Hostname
IP address
Operating system
Architecture
Agent version
Last report
Installed packages
Available updates
```

The client should report using its own client identity.

A client must never be able to access another client's resources.

---

# 45. Verify the Client API Authentication

Client API access uses the client-specific Bearer token.

The authentication flow is:

```text
Client
   │
   │ Authorization: Bearer <token>
   ▼
LUMS API
   │
   ▼
Token validation
   │
   ▼
Client identity
   │
   ▼
Authorized client operation
```

Invalid or rotated tokens must be rejected.

Do not test production authentication by placing real tokens into shell history or documentation.

For troubleshooting, use the systemd configuration rather than manually copying credentials into commands.

---

# 46. Verify Package Inventory

Run the reporting agent manually:

```bash
sudo systemctl start lums-agent.service
```

Inspect the result:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Inspect the journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

The client report contains package inventory information.

For Debian/Ubuntu, the agent uses APT/dpkg.

For Arch Linux, the agent uses pacman.

The server should display the reported package information for the corresponding client.

---

# 47. Verify Available Updates

The agent also reports available updates.

On Debian/Ubuntu, the package manager uses:

```bash
apt list --upgradable
```

On Arch Linux:

```bash
pacman -Qu
```

The package-manager abstraction normalizes the result for the LUMS application.

The workflow is:

```text
Package Manager
       ↓
LUMS Agent
       ↓
Update Detection
       ↓
HTTPS Report
       ↓
LUMS Server
       ↓
Client Update Inventory
```

A client with no available updates should report a clean state.

---

# 48. Create an Update Job

Update jobs are created from the LUMS web interface.

The general workflow is:

```text
Client
   ↓
Available Updates
   ↓
Select Package(s)
   ↓
Create Update Job
   ↓
Pending
```

The job remains pending until the client-side execution watcher can process it.

The job state can be inspected through the LUMS interface.

Typical states include:

```text
pending
running
success
partial
failed
```

The exact package-level result is also recorded.

---

# 49. Idle-Aware Execution

The execution watcher does not blindly execute every pending job immediately.

Before execution, the watcher checks whether the client is idle.

The current idle detection uses:

```text
systemd-logind / loginctl
```

The configured idle threshold is:

```text
300 seconds
```

The execution flow is:

```text
Pending Job
     ↓
Watcher
     ↓
Idle Detection
     │
     ├── Client active
     │       ↓
     │    wait
     │
     └── Client idle
             ↓
          continue
             ↓
        claim job
```

This prevents an update job from being executed while an interactive user is actively using the client.

---

# 50. Verify Idle Detection

Check the current login/idle state on the client:

```bash
loginctl
```

For more detailed session information:

```bash
loginctl list-users
```

and:

```bash
loginctl list-sessions
```

The watcher uses the available `systemd-logind` information to determine whether the client is considered idle.

If idle detection is not supported or cannot be determined, the watcher must not silently assume that the client is safe to update.

Inspect the watcher journal:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

---

# 51. Job Claiming

When the watcher is allowed to execute a job, it first claims the job.

The claim operation is atomic.

The intended flow is:

```text
Pending
   ↓
Atomic Claim
   ↓
Running
   ↓
Execution
```

This prevents multiple watcher processes from executing the same job simultaneously.

A job that has already been claimed must not be claimed again by another execution process.

---

# 52. Update Execution

The LUMS Agent uses the package-manager abstraction for update operations.

For Debian/Ubuntu:

```text
APT / dpkg
```

For Arch Linux:

```text
pacman
```

The package manager handles the actual operating-system package operation.

LUMS controls the job and records the result.

Conceptually:

```text
LUMS
 │
 ├── Job selection
 ├── Authorization
 ├── Claiming
 ├── Timeout handling
 ├── Checkpointing
 └── Result recording
        │
        ▼
Package Manager
        │
        ├── apt / dpkg
        │
        └── pacman
```

---

# 53. Update Timeout Handling

Update execution is subject to a timeout.

If the package operation does not finish within the configured execution window, the agent uses controlled process termination.

The termination sequence is designed to avoid leaving an indefinitely running update process behind.

Conceptually:

```text
Update process
      │
      ▼
   timeout
      │
      ▼
 graceful termination
      │
      ├── process exits
      │
      └── still running
              ↓
          kill fallback
```

The resulting package state is reported to the LUMS server.

A timed-out package must not be reported as successfully installed.

---

# 54. Package-Level Results

Update jobs track package-level results.

A package result can contain a state such as:

```text
success
failed
timeout
```

The server validates the submitted result before accepting it.

The job itself can result in:

```text
success
partial
failed
```

This distinction allows the server to represent situations where some packages succeeded while others did not.

---

# 55. Result Reporting

After execution, the client reports the result:

```text
Agent
   ↓
Update execution
   ↓
Package results
   ↓
Job result
   ↓
HTTPS
   ↓
LUMS API
```

The server validates:

* job existence
* client ownership
* current job state
* package membership
* package result structure
* package name
* package result status

Only valid results are accepted.

---

# 56. Update History

Completed jobs are recorded in the LUMS update history.

The history allows administrators and authorized users to determine:

```text
What happened?
When did it happen?
On which client?
Which packages were involved?
What was the result?
```

The history is separate from the current available-update inventory.

A package being present in the history does not mean that it is currently pending an update.

---

# 57. Reboot Requirement

Some package updates require a reboot.

The agent checks whether the operating system indicates that a reboot is required.

For Debian/Ubuntu, the traditional reboot marker is checked:

```text
/var/run/reboot-required
```

For Arch Linux, the agent compares the running kernel with the installed Linux package/module information.

The result is reported to LUMS.

Conceptually:

```text
Update
  ↓
Reboot Detection
  │
  ├── no reboot required
  │
  └── reboot required
```

---

# 58. Interrupted Job Recovery

LUMS includes recovery handling for jobs interrupted during execution.

The watcher can detect jobs that were previously running but did not complete normally.

The recovery flow is:

```text
Running Job
     │
     ├── normal completion
     │       ↓
     │     result
     │
     └── interruption
             ↓
          recovery
             ↓
       job state evaluated
             ↓
       continue / recover
```

The recovery mechanism uses job state and checkpoint information.

This prevents an interrupted process from leaving the server with an inconsistent permanent `running` state.

---

# 59. Verify Recovery

Recovery testing should be performed in a controlled test environment.

After an interrupted execution, inspect the job state in LUMS.

Also inspect the watcher journal:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Inspect the server logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

The expected behavior is that an interrupted job is detected and processed according to the recovery logic rather than remaining indefinitely unresolved.

---

# 60. Simulation Mode

LUMS provides simulation support for update execution testing.

Simulation mode allows the update workflow to be tested without executing the real package-manager operation.

The intended workflow is:

```text
Simulation
    ↓
Job handling
    ↓
Validation
    ↓
Result handling
```

without:

```text
apt-get ...
```

or:

```text
pacman ...
```

being executed.

Simulation tests verify that real package-manager execution is not accidentally triggered.

---

# 61. Recommended First Update Test

For a new client, use a controlled test package or a package update that is safe to test.

Do not begin a first production test with a complete system upgrade.

The recommended sequence is:

```text
1. Client reports successfully
2. Package inventory is visible
3. Available updates are visible
4. Create one controlled job
5. Confirm client idle state
6. Watcher claims the job
7. Package operation executes
8. Result is reported
9. Job reaches a final state
10. Update history contains the result
11. Reboot requirement is checked
```

After the first successful test, broader update jobs can be evaluated.

---

# 62. End-to-End Validation

A fully connected LUMS installation should now support:

```text
                 ┌──────────────┐
                 │ LUMS Server  │
                 │              │
                 │ Docker       │
                 │ Flask        │
                 │ SQLite       │
                 └──────┬───────┘
                        │
                    HTTPS
                        │
             ┌──────────┴──────────┐
             │                     │
             ▼                     ▼
       Debian/Ubuntu           Arch Linux
             │                     │
             ▼                     ▼
          Agent                  Agent
             │                     │
             ▼                     ▼
          Watcher                Watcher
             │                     │
             ▼                     ▼
         APT/dpkg               pacman
```

The complete workflow is:

```text
Client registration
       ↓
Inventory report
       ↓
Update detection
       ↓
Job creation
       ↓
Idle detection
       ↓
Atomic job claim
       ↓
Update execution
       ↓
Checkpoint / recovery
       ↓
Result validation
       ↓
Update history
       ↓
Reboot detection
```

---

# 63. Final Client Checklist

Before considering a client installation complete:

```text
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher installed
[ ] Watcher version verified
[ ] Client token configured
[ ] Token file protected
[ ] TLS verification works
[ ] Agent service succeeds
[ ] Client report accepted
[ ] Client visible in LUMS
[ ] Package inventory available
[ ] Update inventory available
[ ] Agent timer enabled
[ ] Watcher timer enabled
[ ] Idle detection works
[ ] Controlled update job tested
[ ] Job result recorded
[ ] Update history updated
[ ] Reboot detection tested
```

A client that passes these checks is ready for normal LUMS operation.

---

# 64. Installation Complete

At this point the LUMS installation consists of:

```text
LUMS Server
    │
    ├── Nginx
    ├── HTTPS/TLS
    ├── Docker
    ├── Gunicorn
    ├── Flask
    └── SQLite

Linux Clients
    │
    ├── LUMS Agent
    ├── Reporting Timer
    ├── Execution Watcher
    └── Watcher Timer
```

The installation is complete once the server and clients have passed their respective validation checklists.

For operational problems, continue with:

```text
docs/troubleshooting.md
```

For security details and the completed security audit, see:

```text
docs/security.md
```
# 65. Operational Maintenance

Once LUMS is installed and validated, regular maintenance should focus on:

```text
Application
Database
Container
TLS certificates
Secrets
Clients
Logs
Backups
```

The LUMS server should be treated like any other infrastructure component.

Changes should be tested before they are applied to a production installation.

---

# 66. Updating the LUMS Container

Before rebuilding or replacing the LUMS container, verify the current state:

```bash
sudo docker ps
```

Check the current image:

```bash
sudo docker images lums
```

Check the current container configuration:

```bash
sudo docker inspect lums
```

Check recent application logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

The database is stored in the persistent Docker volume:

```text
lums-data
```

The container itself is therefore disposable, while the persistent application data remains outside the container filesystem.

---

# 67. Rebuild the LUMS Image

After updating the LUMS source code:

```bash
cd /opt/lums-public
```

Build the image:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Verify the resulting image:

```bash
sudo docker images lums
```

Before replacing the running container, verify the image locally where practical.

Run the test suite from the repository:

```bash
python -m pytest -q
```

The production container should only be replaced after the application has passed the relevant tests.

---

# 68. Preserve Persistent Data

The following data must not be stored only inside the disposable container filesystem:

```text
SQLite database
LUMS secret
TLS private key
TLS certificate
```

The database is stored in:

```text
lums-data:/var/lib/lums
```

The application secret is mounted from:

```text
/etc/lums/secrets/lums_secret
```

TLS material is stored under:

```text
/etc/lums/tls/
```

Do not remove these locations during a normal container update.

---

# 69. Create a Database Backup

Before major changes, migrations, or maintenance, create a database backup.

Example:

```bash
sudo docker run --rm \
    --user 10001:10001 \
    -v lums-data:/var/lib/lums \
    -v /opt/lums-backups:/backup \
    --entrypoint python3 \
    lums:latest \
    -c '
import sqlite3
src = sqlite3.connect("/var/lib/lums/lums.db")
dst = sqlite3.connect("/backup/lums-backup.db")
src.backup(dst)
dst.close()
src.close()
print("SQLite backup completed")
'
```

Verify the resulting file:

```bash
ls -lh /opt/lums-backups/
```

The backup should be stored on separate persistent storage where possible.

A backup located on the same physical disk as the production database does not protect against disk failure.

---

# 70. Verify Database Integrity

A SQLite integrity check can be performed using:

```bash
sudo docker run --rm \
    --user 10001:10001 \
    -v lums-data:/var/lib/lums \
    --entrypoint python3 \
    lums:latest \
    -c '
import sqlite3
db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
'
```

Expected result:

```text
ok
```

Do not continue with destructive maintenance if the integrity check reports an error.

---

# 71. Restore a Database Backup

Database restoration is a destructive operation.

Stop the LUMS container before replacing the active database:

```bash
sudo docker stop lums
```

Create a copy of the current database before restoring anything:

```bash
sudo cp \
    /opt/lums-current-backup.db \
    /opt/lums-current-before-restore.db
```

Restore the known-good backup into the persistent volume:

```bash
sudo docker run --rm \
    --user 10001:10001 \
    -v lums-data:/var/lib/lums \
    -v /opt/lums-backups:/backup \
    --entrypoint python3 \
    lums:latest \
    -c '
import sqlite3
src = sqlite3.connect("/backup/lums-backup.db")
dst = sqlite3.connect("/var/lib/lums/lums.db")
src.backup(dst)
dst.close()
src.close()
print("SQLite restore completed")
'
```

Run the integrity check again before starting LUMS.

Then start the container:

```bash
sudo docker start lums
```

Inspect the logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

A restore should always be followed by application-level validation.

---

# 72. TLS Certificate Maintenance

LUMS is normally accessed through Nginx using HTTPS.

TLS files are stored outside the application container:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

After replacing certificates, validate the Nginx configuration:

```bash
sudo nginx -t
```

Then reload Nginx:

```bash
sudo systemctl reload nginx
```

Verify HTTPS:

```bash
curl -I https://LUMS-SERVER/
```

Do not place private TLS keys into the Git repository.

---

# 73. Secret Maintenance

The application secret is stored separately from the container image:

```text
/etc/lums/secrets/lums_secret
```

The container receives it through:

```text
/run/secrets/lums_secret
```

The application reads it using:

```text
LUMS_SECRET_KEY_FILE
```

The secret must not be committed to Git.

Do not place real production secrets into:

```text
README files
documentation
shell history
issue reports
screenshots
Git commits
```

If the secret is compromised, replace it according to the application's secret-handling procedure and validate the resulting authentication/session behavior.

---

# 74. Client Token Rotation

Client authentication uses client-specific Bearer tokens.

When a client token is rotated:

```text
Old token
   ↓
invalidated
   ↓
new token
   ↓
client configuration updated
```

The client must be updated with the new token before normal reporting resumes.

A rotated token must not remain valid indefinitely.

Treat client tokens as credentials.

---

# 75. Updating Clients

The LUMS server and clients should be updated deliberately.

A typical client maintenance sequence is:

```text
1. Check current agent version
2. Check current watcher version
3. Update the files
4. Verify permissions
5. Verify configuration
6. Run the agent
7. Verify the report
8. Run the watcher
9. Inspect logs
```

For the current release-independent development state, the agent and watcher versions are tracked independently from the LUMS server.

Current versions:

```text
Agent:   1.7.0
Watcher: 1.2.1
```

These version numbers do not represent a released LUMS project version.

---

# 76. Restarting LUMS Safely

For a normal container restart:

```bash
sudo docker restart lums
```

Wait for the application to initialize:

```bash
sleep 5
```

Then inspect:

```bash
sudo docker ps
```

and:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Verify HTTPS afterwards:

```bash
curl -I https://LUMS-SERVER/
```

Finally verify that a client can report successfully.

---

# 77. Log Inspection

Application logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Follow live logs:

```bash
sudo docker logs \
    -f \
    lums
```

Agent logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Watcher logs:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Timer status:

```bash
sudo systemctl list-timers \
    --all | grep lums
```

Logs should be checked before changing configuration when diagnosing operational problems.

---

# 78. Uninstalling a Client

To remove a LUMS client, first stop and disable its services and timers.

For example:

```bash
sudo systemctl disable --now lums-agent.timer
sudo systemctl disable --now lums-agent-watcher.timer
```

Stop the corresponding services if required:

```bash
sudo systemctl stop \
    lums-agent.service \
    lums-agent-watcher.service
```

Remove the installed client files only after verifying that they are no longer needed.

Remove the client credentials from the client configuration.

The corresponding client should also be disabled or removed from the LUMS server.

Do not delete a server-side client record blindly if its historical update information is still required.

---

# 79. Uninstalling the LUMS Server

Server removal should be performed in stages.

First stop the application:

```bash
sudo docker stop lums
```

Before removing anything, create a final database backup.

Verify:

```bash
ls -lh /opt/lums-backups/
```

Then remove the container:

```bash
sudo docker rm lums
```

The persistent database volume can be removed separately:

```bash
sudo docker volume rm lums-data
```

**Warning:** Removing `lums-data` permanently removes the SQLite database stored in that volume.

Only perform this step after confirming that the database is no longer required and a valid backup exists.

---

# 80. Removing the LUMS Image

After the application has been removed, the Docker image can also be removed:

```bash
sudo docker image rm lums:latest
```

Verify:

```bash
sudo docker images lums
```

Do not remove an image that is still required by another container.

---

# 81. Removing External Configuration

After uninstalling the application, review:

```text
/etc/lums/
/opt/lums-public/
/opt/lums-backups/
```

Also review:

```text
/etc/nginx/
/etc/systemd/system/
```

Only remove configuration that belongs to the LUMS installation.

If Nginx hosts other applications, do not remove the entire Nginx configuration.

---

# 82. Final Uninstallation Checklist

Before declaring the installation removed:

```text
[ ] Final database backup created
[ ] Backup integrity verified
[ ] LUMS container stopped
[ ] LUMS container removed
[ ] Persistent volume reviewed
[ ] Persistent volume removed only if intended
[ ] LUMS image removed if no longer required
[ ] Client services disabled
[ ] Client timers disabled
[ ] Client credentials removed
[ ] Server-side client records reviewed
[ ] LUMS Nginx configuration reviewed
[ ] TLS files reviewed
[ ] Secret files reviewed
[ ] Repository files reviewed
```

---

# 83. Installation Lifecycle

The complete LUMS lifecycle is therefore:

```text
Install
   ↓
Configure
   ↓
Harden
   ↓
Register clients
   ↓
Report inventory
   ↓
Detect updates
   ↓
Execute controlled jobs
   ↓
Record results
   ↓
Monitor
   ↓
Backup
   ↓
Maintain
   ↓
Upgrade
   ↓
Retire
```

The persistent database, credentials, TLS material, client configuration and operational history should be treated as infrastructure data throughout this lifecycle.

---

# 84. Next Documentation

The installation guide describes deployment and normal operational procedures.

For security architecture and the completed security audit, see:

```text
docs/security.md
```

For operational errors and recovery procedures, see:

```text
docs/troubleshooting.md
```

The troubleshooting guide should be consulted before changing production configuration in response to an unexpected error.
