# LUMS Installation Guide

## Linux Update Management Server

**Project:** LUMS
**Slogan:** Linux Update Management without the noise.
**Repository:** `NovaForgeCtrl/LUMS`

---

# 1. Overview

LUMS is a centralized Linux update management platform for controlled update distribution, client reporting, package management, update-job execution, result validation and auditable administration.

The current architecture separates the management server from the managed Linux clients.

The server provides:

* Web-based administration
* Client management
* Client authentication
* Package inventory
* Available-update reporting
* Package search
* Package installation and removal
* Update-job management
* Job result validation
* Update history
* Role-based access control
* Audit logging
* SQLite-based persistent state

Linux clients provide:

* System information
* Installed-package inventory
* Available-update detection
* Package operations
* Update-job execution
* Idle-state detection
* Job checkpointing and recovery
* Reboot detection
* Result reporting

The current implementation supports:

```text
Debian / Ubuntu
    └── APT / dpkg

Arch Linux
    └── pacman
```

---

# 2. Architecture

The production architecture is:

```text
                         LUMS Server
                              │
                              │ HTTPS :443
                              ▼
                       ┌──────────────┐
                       │    Nginx     │
                       │  TLS / Proxy │
                       └──────┬───────┘
                              │
                              │ HTTP
                              ▼
                       127.0.0.1:5050
                              │
                              ▼
                    ┌───────────────────┐
                    │   Docker: lums    │
                    │                   │
                    │   Gunicorn        │
                    │   Flask :5000     │
                    │   SQLite          │
                    └─────────┬─────────┘
                              │
                              ▼
                         lums-data
                              │
                              ▼
                   /var/lib/lums/lums.db


        Linux Client
              │
              │ HTTPS + Bearer Token
              ▼
         LUMS API
              │
              ├── Report
              ├── Package Search
              ├── Job Retrieval
              └── Job Result
```

The LUMS application is **not intended to be directly exposed to the network**.

The application container is bound to:

```text
127.0.0.1:5050 → container:5000
```

Nginx is the external HTTPS entry point.

Port `5000` is not published directly.

Port `5050` must remain localhost-only.

---

# 3. Application Components

A complete LUMS installation consists of several components.

## 3.1 LUMS Server

The server contains:

```text
Flask
Gunicorn
SQLite
Web UI
REST API
Authentication
RBAC
Audit logging
Job management
Package management
```

The application runs inside the Docker container:

```text
lums
```

The persistent database is stored outside the container's writable application filesystem:

```text
lums-data:/var/lib/lums/lums.db
```

---

## 3.2 Nginx

Nginx provides:

```text
HTTPS termination
TLS certificate handling
HTTP → HTTPS redirect
Reverse proxy
External network entry point
```

The intended request path is:

```text
Browser
   │
   │ HTTPS
   ▼
Nginx
   │
   │ localhost HTTP
   ▼
127.0.0.1:5050
   │
   ▼
LUMS
```

The Flask/Gunicorn application should not be exposed directly to the LAN.

---

## 3.3 Linux Agent

The LUMS Agent runs on every managed Linux client.

The current Agent version is:

```text
1.7.0
```

The Agent is responsible for:

```text
System information
Installed packages
Available updates
Client reporting
Job retrieval
Job claiming
Package operations
Result reporting
Reboot detection
```

The Agent communicates with the LUMS server using HTTPS and a client-specific Bearer token.

---

## 3.4 Execution Watcher

The execution watcher is responsible for controlled update-job execution.

The current Watcher version is:

```text
1.2.1
```

The Watcher handles:

```text
Pending-job detection
Idle-state checks
Atomic job claiming
Update execution
Checkpoint handling
Interrupted-job recovery
Result processing
```

The Watcher is intentionally separated from ordinary client reporting.

---

# 4. Security Model

The installation must preserve the LUMS security baseline.

The production server uses:

```text
HTTPS
Bearer-token client authentication
Role-based web authorization
CSRF protection
Audit logging
Read-only container root filesystem
Dropped Linux capabilities
no-new-privileges
Non-root application user
Localhost-only application port
Persistent Docker volume
Read-only secret mount
```

The Docker container runs as the unprivileged user:

```text
lums
```

with UID:

```text
10001
```

The container must not run in privileged mode.

The root filesystem must remain read-only.

The application must not require write access to its application directory.

Persistent application data is stored through the dedicated Docker volume.

---

# 5. Current RBAC Model

LUMS currently provides three web roles:

```text
administrator
operator
viewer
```

## Administrator

Administrators can perform administrative operations including:

```text
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
Create and disable clients
Rotate client tokens
Manage users
Manage roles
```

---

## Operator

Operators can perform operational management:

```text
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
```

Operators do not have access to:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

---

## Viewer

Viewers have intentionally restricted access.

A Viewer can access:

```text
Clients
Installed software
```

The following management areas are hidden from the Viewer interface and protected server-side:

```text
Available updates
Update Jobs
Update History
Package Management
System Maintenance
```

UI hiding is therefore not the security boundary.

Server-side authorization remains mandatory.

---

# 6. Installation Requirements

## 6.1 LUMS Server

The current deployment requires a Linux host with:

```text
Docker Engine
Git
Nginx
OpenSSL
Network connectivity
Persistent storage
```

The server must have enough storage for:

```text
Docker images
SQLite database
Application data
Logs
Backups
```

The LUMS application itself runs inside Docker.

---

## 6.2 Linux Clients

Managed Linux clients require:

```text
Python 3
systemd
Supported package manager
Network connectivity to the LUMS server
Valid client token
Trusted TLS certificate
```

Supported package-management families:

```text
Debian / Ubuntu
    APT / dpkg

Arch Linux
    pacman
```

The client must be able to reach the LUMS HTTPS endpoint.

---

# 7. Recommended Directory Layout

The recommended server-side repository location is:

```text
/opt/lums-public/
```

The repository contains the application source, Agent source and tests.

A typical installation uses:

```text
/opt/lums-public/
    ├── agent/
    ├── server/
    ├── tests/
    ├── Dockerfile
    ├── requirements.txt
    └── requirements-dev.txt
```

Host-side configuration is kept outside the repository:

```text
/etc/lums/
    ├── secrets/
    │   └── lums_secret
    └── tls/
        ├── lums.crt
        └── lums.key
```

Persistent application data is stored in:

```text
lums-data:/var/lib/lums
```

The SQLite database is:

```text
/var/lib/lums/lums.db
```

The database must never be stored inside the Git working tree.

Secrets and private TLS material must also remain outside the repository.

---

# 8. Repository Preparation

Clone the repository into the intended installation directory:

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

Check the working tree:

```bash
git status
```

Inspect the current revision:

```bash
git log -1 --oneline --decorate
```

For controlled deployments, the exact commit used for the installation should be recorded.

Do not build production images from an unknown or unverified working tree.

---

# 9. Repository Security Check

Before building the production image, verify that sensitive files have not been placed into the repository.

Review the working tree:

```bash
git status --short
```

Review ignored files where appropriate:

```bash
git status --ignored --short
```

The repository must not contain:

```text
Production database files
Private TLS keys
Application secrets
Client tokens
Credential dumps
Backup databases
Runtime logs
Temporary backup files
```

The project uses repository ignore rules to prevent common backup artifacts from being accidentally tracked.

Before committing changes, inspect the staged file list carefully.

---

# 10. Prepare Host Configuration Directories

Create the required host-side directories:

```bash
sudo install -d -m 700 /etc/lums
sudo install -d -m 700 /etc/lums/secrets
sudo install -d -m 700 /etc/lums/tls
```

The secret directory contains the application secret.

The TLS directory contains the TLS certificate and private key.

Protecting these directories reduces the risk of accidental disclosure.

Verify:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums \
    /etc/lums/secrets \
    /etc/lums/tls
```

---

# 11. Create the Application Secret

The LUMS application secret is stored on the host rather than embedded directly into the Docker image.

The production secret path is:

```text
/etc/lums/secrets/lums_secret
```

Generate a random secret:

```bash
sudo sh -c 'umask 077 && openssl rand -hex 32 > /etc/lums/secrets/lums_secret'
```

Protect the resulting file:

```bash
sudo chmod 600 \
    /etc/lums/secrets/lums_secret
```

Verify the permissions without displaying the secret:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/secrets/lums_secret
```

Expected:

```text
600
```

The secret must never be:

```text
Committed to Git
Printed into logs
Included in the Docker image
Placed into screenshots
Published in issues
Included in documentation
```

The container receives the secret through a read-only bind mount.

---

# 12. Prepare TLS Material

LUMS uses HTTPS for external access.

The recommended host-side locations are:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Install the appropriate certificate and private key before configuring Nginx.

Protect the private key:

```bash
sudo chmod 600 \
    /etc/lums/tls/lums.key
```

The certificate may be readable by the Nginx service:

```bash
sudo chmod 644 \
    /etc/lums/tls/lums.crt
```

Verify:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

The private key must never be committed to Git or included in the Docker image.

---

# 13. Installation Principle

The installation should proceed in controlled stages:

```text
Repository
    ↓
Host configuration
    ↓
Application secret
    ↓
TLS material
    ↓
Docker image
    ↓
Persistent volume
    ↓
Hardened container
    ↓
Nginx / HTTPS
    ↓
Administrator
    ↓
Server validation
    ↓
Linux clients
```

Do not connect production clients before the server has passed its own validation checks.

The following sections continue with Docker image construction and the hardened production deployment.

# 14. Build the LUMS Docker Image

Before building the production image, make sure the repository is in the intended state.

Enter the repository:

```bash
cd /opt/lums-public
```

Run the test suite before creating a production image:

```bash
./.venv-test/bin/pytest -q
```

The test count is expected to grow as the project evolves.

The important requirement is that the relevant test suite completes successfully before deployment.

Build the Docker image:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Verify that the image exists:

```bash
sudo docker image ls lums
```

Inspect the image:

```bash
sudo docker image inspect lums:latest
```

The production image is based on a pinned Python 3.13 slim base image.

The Dockerfile also uses pinned production dependencies where required.

---

# 15. Review the Docker Build

Before deploying the image, review the build output for unexpected errors or warnings.

Check the resulting image:

```bash
sudo docker inspect \
    lums:latest
```

Verify the configured application user:

```bash
sudo docker image inspect \
    lums:latest \
    --format '{{.Config.User}}'
```

The application is intended to run as:

```text
lums
```

The application must not require root privileges during normal execution.

Review the Dockerfile when changing the build process:

```bash
sed -n '1,240p' Dockerfile
```

Do not add secrets, certificates or production databases to the Docker build context.

The repository contains a `.dockerignore` file to reduce the risk of accidentally including runtime artifacts in the image.

---

# 16. Create the Persistent Docker Volume

Create the persistent LUMS data volume:

```bash
sudo docker volume create lums-data
```

Verify:

```bash
sudo docker volume inspect lums-data
```

The volume stores persistent application data:

```text
lums-data
    ↓
/var/lib/lums
    ↓
/var/lib/lums/lums.db
```

The container filesystem itself must not be treated as persistent application storage.

The database therefore survives container replacement as long as the `lums-data` volume is preserved.

> [!IMPORTANT]
> Never remove `lums-data` during a normal application upgrade.

Removing the volume removes the SQLite database stored inside it.

---

# 17. Verify the Persistent Volume

Before starting LUMS, confirm that the volume exists:

```bash
sudo docker volume inspect \
    lums-data
```

The volume can also be checked through Docker:

```bash
sudo docker volume ls | grep lums-data
```

A newly created volume will normally not contain a database yet.

The database is initialized by the LUMS application during deployment.

---

# 18. Production Container Configuration

The production container uses several security controls simultaneously.

The expected runtime baseline is:

```text
Non-root user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges
No privileged mode
Localhost-only application binding
Read-only application-secret mount
Persistent writable data volume
Dedicated /tmp tmpfs
```

The application port is published only to localhost:

```text
127.0.0.1:5050 → container:5000
```

The external HTTPS endpoint is provided by Nginx.

---

# 19. Start the Hardened LUMS Container

Before starting a new production container, make sure another container named `lums` is not already running:

```bash
sudo docker ps \
    --filter name=lums
```

If an existing deployment is being replaced, preserve the existing container until the new image has been validated.

Start the hardened container:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /run:rw,noexec,nosuid,size=16m \
    -p 127.0.0.1:5050:5000 \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    lums:latest
```

The application secret is mounted read-only.

The SQLite database is stored in the persistent volume.

The root filesystem is read-only.

All Linux capabilities are dropped.

The `no-new-privileges` security option prevents processes inside the container from gaining additional privileges.

---

# 20. Verify the Container State

Check the running container:

```bash
sudo docker ps \
    --filter name=lums
```

Expected state:

```text
Up ...
```

Check the container state directly:

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Expected:

```text
running
```

Inspect recent logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Application startup errors must be resolved before continuing with the installation.

---

# 21. Verify Container Security

Inspect the effective runtime security configuration:

```bash
sudo docker inspect lums \
    --format='User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}'
```

The expected baseline is:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

The exact formatting of the Docker output may vary.

The effective configuration is what matters.

---

# 22. Verify the Application Port

Check the published Docker port:

```bash
sudo docker port lums
```

Expected:

```text
5000/tcp -> 127.0.0.1:5050
```

The following is **not** acceptable for the production application:

```text
0.0.0.0:5050
```

or:

```text
0.0.0.0:5000
```

The application is intentionally accessible only through the local reverse-proxy path.

Check the listening sockets:

```bash
sudo ss -lntp | grep -E ':5050|:5000'
```

Only the localhost application binding should be present.

---

# 23. Verify the Secret Mount

Confirm that the secret is mounted:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Source "->" .Destination "RW=" .RW}}{{end}}'
```

The application secret should appear similar to:

```text
/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
```

The exact output may contain additional mount information.

The important property is:

```text
RW=false
```

Never print the secret contents.

A direct readability test is sufficient:

```bash
sudo docker exec lums \
    sh -c 'test -r /run/secrets/lums_secret && echo "secret mount: OK"'
```

Expected:

```text
secret mount: OK
```

---

# 24. Verify the Persistent Volume Mount

Inspect the container mounts:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Type .Source "->" .Destination "RW=" .RW}}{{end}}'
```

The LUMS data volume must be mounted at:

```text
/var/lib/lums
```

and must be writable:

```text
RW=true
```

The expected relationship is:

```text
lums-data
    ↓
/var/lib/lums
```

The root filesystem remains read-only while the dedicated data volume provides the required persistent write access.

---

# 25. Verify the Read-Only Root Filesystem

The application root filesystem must be read-only.

The container runtime should report:

```text
ReadonlyRootfs=true
```

A controlled write test can be performed inside the container.

For example:

```bash
sudo docker exec lums \
    sh -c 'touch /app/.write-test'
```

The command should fail because `/app` is part of the read-only container filesystem.

Do not disable the read-only root filesystem merely because an application component attempts to write outside its designated writable locations.

If the application requires persistent data, use the appropriate volume or runtime filesystem instead.

---

# 26. Verify the Writable Temporary Filesystem

The container provides a dedicated `/tmp` tmpfs.

Verify:

```bash
sudo docker exec lums \
    sh -c 'touch /tmp/lums-write-test && rm -f /tmp/lums-write-test && echo "tmpfs: OK"'
```

Expected:

```text
tmpfs: OK
```

The temporary filesystem is configured with:

```text
noexec
nosuid
```

and a size limit.

This provides temporary writable storage without making the container root filesystem writable.

---

# 27. Verify the Application Data Directory

The LUMS application requires write access to its persistent data directory.

Test:

```bash
sudo docker exec lums \
    sh -c 'touch /var/lib/lums/.write-test && rm -f /var/lib/lums/.write-test && echo "data volume: OK"'
```

Expected:

```text
data volume: OK
```

This confirms that the dedicated writable volume is available while the rest of the container remains read-only.

---

# 28. Verify the Application User

Confirm the effective runtime user:

```bash
sudo docker exec lums \
    id
```

The process should run as the unprivileged LUMS user.

Expected identity includes:

```text
uid=10001(lums)
```

The exact group information may vary according to the image configuration.

The container must not run as:

```text
root
```

during normal operation.

---

# 29. Database Initialization

After the container starts, check whether the database exists:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

If the application has initialized successfully, the database should be present.

The database is located at:

```text
/var/lib/lums/lums.db
```

inside the container and physically persists through:

```text
lums-data
```

The database must not be copied into:

```text
/opt/lums-public
```

or committed to Git.

---

# 30. Verify SQLite Runtime Configuration

The current LUMS production baseline uses:

```text
journal_mode = wal
busy_timeout = 5000 ms
synchronous = 2
foreign_keys = ON
```

The application explicitly enables foreign-key enforcement for database connections.

The database uses WAL mode for normal production operation.

The runtime configuration can be inspected from the application database.

For example:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for pragma in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    print(f"{pragma}={db.execute(f'PRAGMA {pragma}').fetchone()[0]}")

db.close()
PY
```

Expected values are equivalent to:

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

The application enables foreign keys explicitly.

---

# 31. Verify Database Integrity

Run an SQLite integrity check:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
result = db.execute("PRAGMA integrity_check").fetchone()[0]
print(result)
db.close()
PY
```

Expected:

```text
ok
```

Do not continue with deployment if the integrity check reports database corruption.

---

# 32. Verify Database Migrations

LUMS uses application migrations for database schema changes.

Inspect the migration-related files:

```bash
ls -lh \
    server/*migration*.py
```

The application performs required migrations during startup/deployment according to the current implementation.

After startup, inspect the application logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Migration errors must be investigated before creating users or connecting clients.

Do not manually modify the production SQLite schema unless the project documentation explicitly requires it.

---

# 33. Local Application Validation

Before configuring Nginx, confirm that the application responds locally.

The Docker application is bound to:

```text
127.0.0.1:5050
```

A local request can be tested with:

```bash
curl -I \
    http://127.0.0.1:5050/
```

The exact HTTP response depends on the current application route and authentication state.

The important requirement is that the request reaches the running LUMS application.

If the connection fails, inspect:

```bash
sudo docker ps \
    --filter name=lums
```

and:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Do not expose port `5050` externally as a troubleshooting workaround.

---

# 34. Initial Server Checkpoint

At this stage, the server should satisfy:

```text
[ ] Repository cloned
[ ] Working tree reviewed
[ ] Production tests completed
[ ] Docker image built
[ ] Persistent lums-data volume exists
[ ] Hardened container running
[ ] Container runs as lums
[ ] Root filesystem is read-only
[ ] All capabilities are dropped
[ ] no-new-privileges is enabled
[ ] Privileged mode is disabled
[ ] Secret is mounted read-only
[ ] Persistent data volume is mounted
[ ] Port 5050 is localhost-only
[ ] SQLite database exists
[ ] SQLite integrity check succeeds
[ ] Foreign keys are enabled
[ ] Local application endpoint responds
```

Do not connect production clients yet.

The next stage configures Nginx, HTTPS and the external LUMS endpoint.

# 35. Configure Nginx

Nginx provides the external HTTPS entry point for LUMS.

The application itself remains bound to:

```text
127.0.0.1:5050
```

The intended request path is:

```text
Client
   │
   │ HTTPS
   ▼
Nginx :443
   │
   │ HTTP localhost
   ▼
127.0.0.1:5050
   │
   ▼
LUMS container :5000
```

Create the Nginx site configuration:

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

with the hostname or address used by the installation.

Do not use the literal placeholder in a production configuration.

---

# 36. Enable the LUMS Nginx Configuration

Create the enabled-site link:

```bash
sudo ln -s \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

If the default Nginx site is not required, remove it:

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/default
```

Do not remove other Nginx configurations belonging to unrelated applications.

---

# 37. Validate the Nginx Configuration

Always test the configuration before reloading Nginx:

```bash
sudo nginx -t
```

Expected:

```text
syntax is ok
test is successful
```

Only after a successful configuration test should Nginx be reloaded:

```bash
sudo systemctl reload nginx
```

Verify the service:

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

Nginx must be running before continuing with HTTPS validation.

---

# 38. Verify TLS Certificate Files

Confirm that the configured certificate files exist:

```bash
sudo ls -lh \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Verify permissions:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

The private key should normally be:

```text
600
```

The certificate can normally be:

```text
644
```

Never print the private-key contents.

---

# 39. Verify the HTTPS Endpoint

Test HTTPS locally:

```bash
curl -kI \
    https://127.0.0.1/
```

When the certificate is trusted by the system, use certificate verification:

```bash
curl -I \
    https://LUMS-SERVER/
```

A successful response confirms that the request reaches the Nginx HTTPS endpoint.

The exact HTTP status depends on the requested route and authentication state.

The important requirement is that the TLS connection succeeds and the request reaches LUMS.

---

# 40. Verify HTTP to HTTPS Redirect

The HTTP listener must redirect clients to HTTPS.

Test:

```bash
curl -I \
    http://LUMS-SERVER/
```

Expected behavior:

```text
HTTP/1.1 301 ...
Location: https://...
```

The LUMS application should not be operated through an unencrypted HTTP connection.

Do not permanently configure clients with certificate verification disabled merely because the initial certificate is not trusted.

Fix the trust configuration instead.

---

# 41. Verify the External Network Path

Inspect the listening sockets:

```bash
sudo ss -lntp | grep -E ':80|:443|:5050|:5000'
```

The intended architecture is:

```text
80
 │
 └── HTTP redirect
        │
        ▼
443
 │
 └── Nginx
        │
        ▼
127.0.0.1:5050
        │
        ▼
Docker :5000
```

Port `5050` must not be exposed to the LAN.

Port `5000` must not be exposed directly.

The Docker application port is an internal reverse-proxy endpoint.

---

# 42. Verify Security Headers

Inspect the HTTPS response headers:

```bash
curl -kI \
    https://LUMS-SERVER/
```

Review the returned headers rather than assuming that the security configuration is active.

Relevant security headers may include:

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Content-Security-Policy
```

The exact headers depend on the current LUMS application and Nginx configuration.

If a required header is missing, inspect the effective Nginx configuration:

```bash
sudo nginx -T
```

and the application configuration:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Do not add security headers blindly without checking which layer is already responsible for them.

---

# 43. Verify Host Handling

The production deployment should not expose the application through an unintended default Nginx site.

Review the active configuration:

```bash
sudo nginx -T
```

Check the enabled sites:

```bash
ls -la \
    /etc/nginx/sites-enabled/
```

The intended LUMS virtual host should be present.

The default site should not unexpectedly serve the LUMS application.

When using an IP address as the LUMS endpoint, ensure that the configured `server_name` and certificate match the actual deployment model.

---

# 44. Verify Docker Exposure Again

After Nginx is configured, confirm that the application remains localhost-only:

```bash
sudo docker port lums
```

Expected:

```text
5000/tcp -> 127.0.0.1:5050
```

The reverse proxy does not require changing the Docker binding.

Do not change it to:

```text
0.0.0.0:5050
```

just because Nginx is listening on the network.

Nginx and Docker have deliberately separate exposure boundaries.

---

# 45. Create the Initial Administrator

The initial administrator must be created using the current repository's administrator initialization mechanism.

Before running an initialization command, inspect the available repository implementation:

```bash
cd /opt/lums-public
```

Review the security-related initialization files:

```bash
find server \
    -maxdepth 1 \
    -type f \
    -iname '*security*' \
    -o -iname '*migration*'
```

Then inspect the current migration/initialization implementation before executing it.

For example:

```bash
sed -n '1,260p' \
    server/security_migration.py
```

Use the initialization procedure provided by the exact repository revision being deployed.

> [!IMPORTANT]
> Do not copy an administrator password into shell history or documentation.

The initial administrator must receive:

```text
role = administrator
```

The administrator account is required for the first web login and subsequent client administration.

---

# 46. Verify the Administrator Account

After administrator initialization, verify the account without exposing authentication material.

A database inspection can be performed from the container:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

rows = db.execute(
    """
    SELECT id, username, enabled, role
    FROM users
    ORDER BY id
    """
).fetchall()

for row in rows:
    print(row)

db.close()
PY
```

Expected administrator properties include:

```text
enabled = 1
role = administrator
```

Do not print:

```text
password hashes
session data
client tokens
application secrets
```

---

# 47. Administrator Password

Use a unique administrator password.

The password should not be reused from:

```text
other servers
Linux accounts
GitHub accounts
email accounts
network devices
other LUMS installations
```

The LUMS application stores passwords using the configured password-hashing mechanism.

Do not attempt to replace the application password hash manually in SQLite.

If the administrator password must be changed, use the supported application mechanism.

---

# 48. First Web Login

Open the LUMS HTTPS endpoint:

```text
https://LUMS-SERVER/
```

Log in with the administrator account.

After authentication, the administrator should have access to the administrative interface.

The administrator interface should provide access to the areas permitted by the current RBAC implementation.

At minimum, the administrator should be able to access:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management
```

---

# 49. Verify Administrator RBAC

After login, verify that administrative functions are available.

The administrator should be able to access user management.

The administrator should also be able to perform client-management operations permitted by the current implementation.

Server-side authorization remains the security boundary.

The browser interface is not trusted merely because an element is visible or hidden.

---

# 50. Create an Operator

After the administrator account has been verified, create an operator account through the LUMS user-management interface.

The operator role is intended for operational update management.

An operator can access:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
```

An operator must not be able to perform administrator-only functions such as:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

Verify the permissions using the application interface and, where appropriate, the API authorization behavior.

---

# 51. Create a Viewer

A Viewer account can be created when read-only access is required.

The Viewer role is intentionally restricted.

A Viewer can access:

```text
Clients
Installed software
```

The following areas must not be available to a Viewer:

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

These restrictions are enforced server-side.

The interface may additionally hide unavailable functions.

---

# 52. Verify Viewer Isolation

Log in using a Viewer account and verify the visible interface.

The Viewer should not receive management controls.

The Viewer must not be able to bypass the UI and invoke protected endpoints directly.

An authorization failure should be returned for protected operations.

The expected principle is:

```text
UI restriction
     +
server-side authorization
     =
RBAC boundary
```

Never rely on JavaScript or hidden HTML elements as the only authorization mechanism.

---

# 53. Verify Session and CSRF Protection

After the first successful login, verify that the application uses its configured session and CSRF protections.

The installation should not disable CSRF protection to make API requests or browser actions work.

If a legitimate request fails with a CSRF error, inspect the application flow rather than disabling the protection.

Session-related behavior is documented in:

```text
docs/security.md
```

---

# 54. Verify Login Rate Limiting

The current login protection uses persistent failure tracking.

The configured progression is:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

Successful authentication clears the applicable failure state.

Do not repeatedly trigger failed authentication against a production installation simply to test the mechanism.

Use the existing test suite for repeated automated validation.

---

# 55. Server Validation Checkpoint

At this stage, verify:

```text
[ ] Nginx is running
[ ] Nginx configuration passes nginx -t
[ ] TLS certificate is installed
[ ] TLS private key is protected
[ ] HTTPS works
[ ] HTTP redirects to HTTPS
[ ] Docker remains localhost-only
[ ] Port 5000 is not externally exposed
[ ] Security headers are present as configured
[ ] Default Nginx site is not unintentionally serving LUMS
[ ] Administrator account exists
[ ] Administrator can log in
[ ] Administrator RBAC works
[ ] Operator role can be created
[ ] Viewer role can be created
[ ] Viewer restrictions are enforced server-side
[ ] CSRF protection remains enabled
[ ] Session protection remains enabled
```

Only after the server passes these checks should Linux clients be installed.

The next section covers the Linux Agent, client configuration, TLS trust and systemd integration.

# 56. Linux Client Installation

LUMS clients are Linux systems managed by the LUMS server.

A client installation consists of:

```text
Linux system
    ↓
LUMS Agent
    ↓
Client configuration
    ↓
Client token
    ↓
TLS trust
    ↓
systemd service
    ↓
Reporting timer
```

Update execution is handled separately by the execution watcher.

The current Agent version is:

```text
1.7.0
```

The current Watcher version is:

```text
1.2.1
```

---

# 57. Supported Linux Clients

The current package-management implementations support:

```text
Debian / Ubuntu
    ↓
APT / dpkg

Arch Linux
    ↓
pacman
```

Verify the operating system before installing the client:

```bash
cat /etc/os-release
```

Verify the architecture:

```bash
uname -m
```

Verify systemd:

```bash
systemctl --version
```

The client requires a functioning systemd installation.

---

# 58. Client Network Requirements

The client must be able to reach the LUMS HTTPS endpoint.

Test basic network connectivity:

```bash
ping LUMS-SERVER
```

A successful ping is not required when ICMP is blocked.

The important requirement is HTTPS connectivity.

Test the LUMS endpoint:

```bash
curl -I \
    https://LUMS-SERVER/
```

If the server uses a private CA, the client must trust that CA before continuing.

Do not disable TLS verification as a permanent workaround.

---

# 59. Obtain the LUMS Agent

The Agent source is included in the LUMS repository.

On the client, obtain the repository or otherwise transfer the required Agent files through the approved deployment method.

The relevant files are:

```text
agent/agent.py
agent/watcher.py
agent/package_manager.py
```

The recommended installation directory is:

```text
/opt/lums-agent
```

Create it:

```bash
sudo install -d -m 755 \
    /opt/lums-agent
```

---

# 60. Install the Agent Files

From the LUMS repository:

```bash
cd /opt/lums-public
```

Install the Agent:

```bash
sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py
```

Install the Watcher:

```bash
sudo cp \
    agent/watcher.py \
    /opt/lums-agent/watcher.py
```

Install the package-manager abstraction:

```bash
sudo cp \
    agent/package_manager.py \
    /opt/lums-agent/package_manager.py
```

Verify:

```bash
ls -lh \
    /opt/lums-agent/
```

The directory should contain the installed Agent components.

---

# 61. Verify Agent Versions

Verify the installed Agent version:

```bash
grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/agent.py
```

The current version is:

```text
1.7.0
```

Verify the Watcher:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

The current version is:

```text
1.2.1
```

If the installed versions do not match the intended deployment revision, stop and verify that the correct repository revision is being used.

---

# 62. Install systemd Service Files

The Agent and Watcher use separate systemd services.

Install the Agent service:

```bash
sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
```

Install the Watcher service:

```bash
sudo cp \
    agent/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent-watcher.service
```

Install the reporting timer:

```bash
sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer
```

Install the Watcher timer:

```bash
sudo cp \
    agent/lums-agent-watcher.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

---

# 63. Verify the systemd Units

Inspect the Agent service:

```bash
systemctl cat \
    lums-agent.service
```

Inspect the Watcher service:

```bash
systemctl cat \
    lums-agent-watcher.service
```

Inspect the Agent timer:

```bash
systemctl cat \
    lums-agent.timer
```

Inspect the Watcher timer:

```bash
systemctl cat \
    lums-agent-watcher.timer
```

The units should reference the installed files under:

```text
/opt/lums-agent/
```

Do not enable the timers until the client configuration and authentication have been completed.

---

# 64. Create the Client Configuration

The client configuration is stored outside the Git repository.

Use:

```text
/etc/default/lums-agent
```

Create the file:

```bash
sudo install -m 600 /dev/null \
    /etc/default/lums-agent
```

The configuration contains the LUMS server endpoint and the client token.

Example structure:

```text
LUMS_BASE=https://LUMS-SERVER
LUMS_TOKEN=<CLIENT-TOKEN>
```

Replace:

```text
LUMS-SERVER
```

with the actual LUMS server endpoint.

Replace:

```text
<CLIENT-TOKEN>
```

with the token assigned to this client.

Protect the configuration:

```bash
sudo chmod 600 \
    /etc/default/lums-agent
```

Verify without displaying its contents:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Expected:

```text
600
```

---

# 65. Client Tokens

Each LUMS client has its own authentication token.

The token is used as:

```text
Authorization: Bearer <CLIENT-TOKEN>
```

The server does not need the original token value after provisioning.

The server stores a cryptographic representation of the token for validation.

This means that client credentials should be treated like passwords.

Never place a real token into:

```text
Git
documentation
screenshots
issue reports
shell history
public configuration
```

---

# 66. Provision the Client Token

Create or provision the client from the LUMS administrator interface according to the current client-management workflow.

The resulting client token must be transferred to the intended client through a secure channel.

Store it only in:

```text
/etc/default/lums-agent
```

on the client.

Do not reuse one client token across multiple machines.

The intended relationship is:

```text
Client A
    ↓
Token A

Client B
    ↓
Token B

Client C
    ↓
Token C
```

A compromised token should therefore identify only its associated client.

---

# 67. Client Token Rotation

Client tokens can be rotated by an administrator.

The rotation flow is:

```text
Current token
     ↓
Administrator rotates token
     ↓
Old token invalidated
     ↓
New token issued
     ↓
Client configuration updated
```

After updating the client configuration, run the Agent manually to verify that authentication succeeds.

A rotated token must not continue to be accepted indefinitely.

---

# 68. TLS Trust

The LUMS Agent communicates with the server over HTTPS.

Certificate verification must remain enabled.

For a publicly trusted certificate, the normal operating-system trust store is sufficient.

For a private laboratory CA, install the CA certificate on the client.

Do not solve certificate problems by disabling verification.

The correct solution is to make the client trust the intended certificate authority.

---

# 69. Debian / Ubuntu TLS Trust

On Debian-family systems, a private CA can be installed into the system trust store.

Copy the CA certificate:

```bash
sudo cp \
    lums-ca.crt \
    /usr/local/share/ca-certificates/lums-ca.crt
```

Update the trust store:

```bash
sudo update-ca-certificates
```

Verify that the certificate is accepted:

```bash
curl -I \
    https://LUMS-SERVER/
```

If the command succeeds without `-k`, the system trust configuration is working.

---

# 70. Arch Linux TLS Trust

On Arch Linux, install the private CA using the system's configured trust-store mechanism.

After installing the CA, update the trust database according to the active trust-store configuration.

Verify:

```bash
curl -I \
    https://LUMS-SERVER/
```

The connection should succeed without:

```text
-k
```

Do not permanently configure the Agent to ignore certificate verification.

---

# 71. Verify the Package Manager

The Agent detects the supported package-management family.

For Debian/Ubuntu:

```bash
command -v apt
```

and:

```bash
command -v dpkg-query
```

Verify installed packages:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    | head
```

Verify available updates:

```bash
apt list --upgradable
```

For Arch Linux:

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

The package-manager abstraction uses the appropriate implementation automatically.

---

# 72. Verify Agent Permissions

Inspect the installation directory:

```bash
ls -ld \
    /opt/lums-agent
```

Inspect the installed files:

```bash
ls -lh \
    /opt/lums-agent/
```

The Agent does not need write access to its own source directory.

The client configuration remains protected separately:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Expected:

```text
600
```

The Agent requires sufficient system privileges to inspect package state and perform package operations.

The exact runtime privileges are defined by the installed systemd service.

---

# 73. Verify the Agent Configuration

Before starting the service, verify that the configuration file exists:

```bash
sudo test -r \
    /etc/default/lums-agent \
    && echo "agent configuration: OK"
```

Do not print the contents of the configuration file.

Verify that the required variables exist without exposing the token:

```bash
sudo sh -c '
set -a
. /etc/default/lums-agent
set +a

test -n "$LUMS_BASE" &&
echo "LUMS_BASE: configured"

test -n "$LUMS_TOKEN" &&
echo "LUMS_TOKEN: configured"
'
```

The token value itself must not be printed.

---

# 74. Test the Agent Manually

Before enabling the timer, execute the Agent once manually:

```bash
sudo systemctl start \
    lums-agent.service
```

Check the result:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

The Agent is a one-shot service.

After successful completion, it may show:

```text
Active: inactive (dead)
```

This is normal.

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

---

# 75. Verify the First Client Report

A successful Agent run should report the client to the LUMS server.

The complete path is:

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

Inspect the server logs when required:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

The client should appear in the LUMS web interface after a successful report.

The local service being successful is not sufficient by itself.

The server must accept the report.

---

# 76. Verify the Client in the Web Interface

Log in as an administrator or operator.

Open the client overview.

The new client should report information such as:

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

The reported information belongs to that client.

A client must not be able to access another client's resources.

---

# 77. Enable the Reporting Timer

Only after the manual Agent run succeeds should the reporting timer be enabled:

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

The timer periodically starts:

```text
lums-agent.service
```

The service itself remains a one-shot unit.

Therefore, it is normal for the service to return to:

```text
inactive (dead)
```

between timer executions.

---

# 78. Verify Scheduled Reporting

After enabling the timer, inspect the next scheduled execution:

```bash
systemctl list-timers \
    --all \
    --no-pager | grep lums-agent
```

After the timer has executed, inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Verify the corresponding client report in LUMS.

A healthy reporting cycle is:

```text
Timer
  ↓
Agent service
  ↓
System inventory
  ↓
Package inventory
  ↓
Update detection
  ↓
HTTPS report
  ↓
LUMS database
```

---

# 79. Client Installation Checkpoint

Before installing the execution watcher, verify:

```text
[ ] Supported Linux distribution
[ ] Python 3 available
[ ] systemd available
[ ] Package manager available
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher files installed
[ ] Client configuration exists
[ ] Client token protected
[ ] TLS certificate trusted
[ ] Agent service succeeds
[ ] Client report accepted
[ ] Client visible in LUMS
[ ] Reporting timer enabled
[ ] Scheduled reporting verified
```

Do not proceed to update-job testing until the reporting path is working.

The next section installs and validates the execution watcher.

# 80. Install the Execution Watcher

The LUMS execution watcher is responsible for detecting and executing pending update jobs on the client.

The architecture separates reporting from execution:

```text
Reporting
    │
    ▼
lums-agent.service
    │
    └── system inventory / update detection

Execution
    │
    ▼
lums-agent-watcher.service
    │
    └── pending update jobs
```

This separation allows regular client reporting to continue independently from update execution.

---

# 81. Verify the Watcher Installation

Verify that the Watcher is present:

```bash
ls -lh \
    /opt/lums-agent/watcher.py
```

Verify the installed version:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

The current Watcher version is:

```text
1.2.1
```

---

# 82. Verify the Watcher Service

Inspect the systemd unit:

```bash
systemctl cat \
    lums-agent-watcher.service
```

The service must reference:

```text
/opt/lums-agent/watcher.py
```

Verify the unit is known to systemd:

```bash
systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

The service may be inactive when no execution has been triggered.

This is not by itself an error.

---

# 83. Verify the Watcher Timer

Before enabling the Watcher timer, verify that:

- `/etc/default/lums-agent` exists and contains the correct client configuration.
- The LUMS server endpoint and client token are configured correctly.
- A manual Agent run succeeded and the server accepted the client report.
- Both Watcher unit files were installed from the repository.

Do not enable the timer while authentication or reporting is failing.


Inspect the timer:

```bash
systemctl cat \
    lums-agent-watcher.timer
```

Enable the timer only after verifying all prerequisites above:

```bash
sudo systemctl enable --now \
    lums-agent-watcher.timer
```

Verify:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Inspect the next scheduled execution:

```bash
systemctl list-timers \
    lums-agent-watcher.timer \
    --no-pager
```

---

# 84. Understand Idle-Aware Execution

The Watcher can use client idle information before executing update jobs.

The intended flow is:

```text
Pending job
    │
    ▼
Watcher
    │
    ▼
Idle detection
    │
    ├── idle state available
    │       │
    │       ▼
    │   idle threshold
    │       │
    │       ▼
    │   execute when allowed
    │
    └── idle state unavailable
            │
            ▼
        use configured
        fallback behavior
```

Idle detection must never be interpreted as authentication or authorization.

It is an execution scheduling mechanism only.

---

# 85. Verify Idle Detection

Run the idle detection path manually through the installed Agent/Watcher implementation.

Inspect the resulting service journal:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

If the platform does not provide the required idle information, the client may report idle detection as unavailable.

This is not automatically a failure.

The important distinction is:

```text
idle_supported = available
```

versus:

```text
idle_supported = unavailable
```

The client must not be assumed to be idle merely because no idle information was returned.

---

# 86. Create a Controlled Test Update Job

Do not begin installation testing with a large system update.

Use a small, known package for the first test.

The package should:

```text
exist in the configured repository
be safe to install
be removable again
not be required by the operating system
```

Example test package:

```text
sl
```

Before creating the job, verify whether it is already installed:

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

For Arch Linux, use a package that is available in the configured repositories and is suitable for a reversible test.

Do not blindly use `sl` on every distribution.

---

# 87. Verify Package Search

Use the LUMS Package Management interface to search for the selected package.

The search flow is:

```text
Browser
   ↓
LUMS API
   ↓
Package Search Request
   ↓
Client
   ↓
APT / pacman
   ↓
Package Search Result
   ↓
LUMS API
   ↓
Browser
```

Verify that the result contains the expected information:

```text
Package
Version
Description
Status
Action
```

For Arch Linux, repository information may also be returned.

---

# 88. Package Management Permissions

Package management is restricted by RBAC.

Administrator:

```text
Allowed
```

Operator:

```text
Allowed
```

Viewer:

```text
Not allowed
```

A Viewer must not be able to execute package installation or removal by directly calling the API.

The browser interface hiding the feature is only an additional usability restriction.

The server-side authorization is the actual security boundary.

---

# 89. Test Package Installation

Create an installation job through the LUMS interface.

The logical operation is:

```text
INSTALL_PACKAGE
```

The job is stored in the LUMS database before the Agent executes it.

The expected flow is:

```text
Create job
   ↓
PENDING
   ↓
Watcher detects job
   ↓
RUNNING
   ↓
Package manager
   ↓
SUCCESS
```

Monitor the job in the LUMS interface.

Do not manually modify the database to force a job state.

---

# 90. Verify the Installation Result

After the job reports success, verify the package locally.

On Debian/Ubuntu:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    sl
```

Verify the package manager agrees:

```bash
apt-cache policy \
    sl
```

The package must actually be installed.

A LUMS `SUCCESS` state must correspond to a successful client-side operation.

---

# 91. Verify the Job Result

Inspect the LUMS job history.

Verify:

```text
Action
Package
Client
Start time
Completion time
Result
```

The result returned by the client must be validated by the server.

Invalid or incomplete result data must not silently turn into a successful job.

This validation is part of the LUMS security and reliability model.

---

# 92. Test Package Removal

After verifying installation, create a removal job:

```text
REMOVE_PACKAGE
```

Monitor:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

After completion:

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

The package should no longer be installed.

If the package was not installed before the test, do not treat the absence as proof of a successful removal operation.

---

# 93. Test Package Update

Package updates use:

```text
UPDATE_PACKAGE
```

The server validates that the requested package is an available update before creating the corresponding job.

The general flow is:

```text
Client reports available updates
       ↓
User selects package
       ↓
Server validates package
       ↓
Update job created
       ↓
Watcher executes
       ↓
Result reported
```

Do not manually construct update requests that bypass the normal validation path.

---

# 94. Test System Update

A complete system update uses:

```text
UPDATE_SYSTEM
```

This operation affects the package-manager state of the client more broadly than a single-package operation.

For the first system-update test:

```text
Use a test client
Use a current backup
Monitor the console
Monitor the LUMS job
Do not interrupt the package manager
```

Do not use the production server itself as the first system-update test target.

---

# 95. Package Manager Locks

APT and pacman can use package-manager locks.

When an operation fails because another package-management process is active, inspect the running processes before taking action.

Debian/Ubuntu:

```bash
ps aux | grep -E \
    '[a]pt|[d]pkg|[u]nattended'
```

Arch Linux:

```bash
ps aux | grep -E \
    '[p]acman|[p]ar'
```

Do not delete package-manager lock files while the package manager is actually running.

A lock normally protects against concurrent package operations.

---

# 96. Distinguish LUMS Failures from Package Manager Failures

When a job fails, determine which layer failed.

```text
LUMS API
   │
   ├── Job creation failure
   │
   ▼
LUMS database
   │
   ├── State / persistence problem
   │
   ▼
Watcher
   │
   ├── Execution problem
   │
   ▼
Package manager
   │
   ├── APT / pacman failure
   │
   ▼
Operating system
```

Inspect the client journal:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Inspect the LUMS container:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Do not immediately retry a failed job without determining why it failed.

---

# 97. Verify Job Checkpointing

LUMS tracks job and package-item state.

For package-based jobs, individual package items can be checkpointed.

The intended behavior is:

```text
Package A → SUCCESS
Package B → SUCCESS
Package C → RUNNING
             │
             ▼
          interruption
             │
             ▼
          recovery
             │
             ▼
Package A → not repeated
Package B → not repeated
Package C → resumed / handled
```

This prevents completed package operations from unnecessarily being repeated after an interruption.

---

# 98. Test Controlled Job Recovery

Use a non-critical test job.

Start the job and observe its state:

```text
PENDING
```

then:

```text
RUNNING
```

Do not deliberately interrupt a production update.

For recovery testing, use a dedicated test client and a controlled package operation.

After an interruption or simulated failure, restart the Watcher:

```bash
sudo systemctl restart \
    lums-agent-watcher.timer
```

Then inspect:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Verify that already successful package items are not unnecessarily executed again.

---

# 99. Verify Reboot Detection

Some package operations may require a reboot.

The Agent/Watcher reports reboot requirements to LUMS.

The general flow is:

```text
Package operation
      ↓
Reboot requirement detected
      ↓
Result reported
      ↓
LUMS records reboot state
```

After a test operation that legitimately requires a reboot, verify the corresponding job result in the LUMS interface.

Do not reboot a production client solely to test the mechanism unless the system is intended for that test.

---

# 100. Verify Reporting After Reboot

When a test client is rebooted, verify that:

```text
systemd
   ↓
LUMS Agent timer
   ↓
Agent report
   ↓
LUMS server
```

continues to work.

Check:

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

and:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Then inspect the latest report in the LUMS interface.

---

# 101. Verify Update Detection

Run the Agent manually:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

The client should report:

```text
Installed packages
Available updates
Agent status
```

The server should update the client's current state.

Do not confuse:

```text
available updates
```

with:

```text
installed packages
```

They represent different data sets.

---

# 102. Verify Installed Software

Open the client's installed-software section in LUMS.

The package list should correspond to the client-side package manager.

For Debian/Ubuntu:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n'
```

For Arch:

```bash
pacman -Q
```

The LUMS inventory is informational until a job is explicitly created.

The installed-package filter does not itself modify the client.

---

# 103. Verify Package Search Separately

The Package Management search is separate from the installed-package filter.

The distinction is:

```text
Installed Package Filter
    ↓
Searches the package inventory already reported by the client

Package Management Search
    ↓
Requests package information from the client's package manager
```

Do not treat the two search functions as interchangeable.

A package may be available through APT or pacman without being installed.

---

# 104. Verify Viewer Package Isolation

Log in as a Viewer.

Verify that the Package Management interface is not available.

Then verify the server-side restriction by attempting an unauthorized package-management request through an approved test method.

The request must be rejected.

Viewer access must remain read-only.

---

# 105. Verify Operator Package Management

Log in as an Operator.

Verify access to:

```text
Package Search
Package Installation
Package Removal
Package Updates
Update Jobs
Update History
```

The Operator must not gain access to administrator-only user-management functions.

---

# 106. Verify Administrator Package Management

Log in as an Administrator.

Verify the same package-management capabilities as the Operator.

Additionally verify access to:

```text
User Management
Client Management
Client Token Rotation
```

Administrator permissions must remain server-side enforced.

---

# 107. First End-to-End Package Test

The first complete package-management test should follow this sequence:

```text
1. Client reports successfully
2. Package search succeeds
3. Package result is displayed
4. Administrator/Operator creates INSTALL_PACKAGE job
5. Job becomes PENDING
6. Watcher detects the job
7. Job becomes RUNNING
8. Package manager executes
9. Client reports result
10. Server validates result
11. Job becomes SUCCESS
12. Installed package is verified locally
13. Package is visible in LUMS inventory
```

Only after this sequence succeeds should broader update testing begin.

---

# 108. Client Execution Checkpoint

Verify:

```text
[ ] Watcher installed
[ ] Watcher version verified
[ ] Watcher timer enabled
[ ] Idle detection works or reports unavailable correctly
[ ] Package search works
[ ] Package installation works
[ ] Package removal works
[ ] Package update works
[ ] System update path is available
[ ] Job states transition correctly
[ ] Job results are validated
[ ] Package checkpointing works
[ ] Reboot detection works
[ ] Reporting continues after reboot
[ ] Viewer cannot mutate package state
[ ] Operator can manage packages
[ ] Administrator can manage packages
```

At this point, the core LUMS client execution path is installed and validated.

The next section covers full end-to-end validation, RBAC verification, backup/restore, maintenance, upgrades and final installation checks.

# 109. Full End-to-End Validation

After the server and at least one Linux client have been configured, perform a complete end-to-end validation.

The complete LUMS path is:

```text
Browser
   │
   ▼
Nginx / HTTPS
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Client Agent
   │
   ▼
Package Manager
   │
   ▼
Update Result
   │
   ▼
SQLite
   │
   ▼
Web Interface
```

Do not consider the installation complete merely because the web interface opens.

All major layers must be verified.

---

# 110. Server Health Check

Verify the LUMS container:

```bash
sudo docker ps \
    --filter name=lums
```

Verify the container state:

```bash
sudo docker inspect \
    lums \
    --format '{{.State.Status}}'
```

Expected:

```text
running
```

Inspect recent logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

The logs should not contain an active startup or migration failure.

---

# 111. Container Security Check

Verify the runtime security configuration:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Expected baseline:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Verify the network binding:

```bash
sudo docker port \
    lums
```

Expected:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 112. Persistent Storage Check

Verify the LUMS volume:

```bash
sudo docker volume inspect \
    lums-data
```

Verify that the application database exists:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

The database must reside in persistent storage.

Do not store the production database only inside the container filesystem.

---

# 113. SQLite Health Check

Inspect the current SQLite runtime configuration:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for name in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    value = db.execute(
        f"PRAGMA {name}"
    ).fetchone()[0]
    print(f"{name}={value}")

db.close()
PY
```

The current baseline is:

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

The application explicitly enables foreign-key enforcement.

---

# 114. SQLite Integrity Check

Run:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

result = db.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

print(result)

db.close()
PY
```

Expected:

```text
ok
```

Do not continue with a new production rollout if the integrity check reports corruption.

---

# 115. Verify Database Migrations

Inspect the migration state:

```bash
sudo docker logs \
    --tail 200 \
    lums | grep -i migration
```

The application must complete its configured migrations before normal operation.

Do not manually modify the migration state table unless the current LUMS migration procedure explicitly requires it.

---

# 116. Run the Automated Test Suite

On the LUMS development/test environment:

```bash
cd /opt/lums-public
```

Run:

```bash
./.venv-test/bin/pytest -q
```

The installation baseline currently includes:

```text
155 passed
```

The exact number may increase as additional tests are added.

The important requirement is:

```text
all tests pass
```

Do not ignore failing tests because the production web interface appears functional.

---

# 117. Verify RBAC

The current role model is:

| Function               | Administrator | Operator | Viewer |
| ---------------------- | ------------: | -------: | -----: |
| View clients           |           Yes |      Yes |    Yes |
| Installed software     |           Yes |      Yes |    Yes |
| Available updates      |           Yes |      Yes |     No |
| Create/execute jobs    |           Yes |      Yes |     No |
| Update history         |           Yes |      Yes |     No |
| Package management     |           Yes |      Yes |     No |
| System maintenance     |           Yes |      Yes |     No |
| Create/disable clients |           Yes |       No |     No |
| Rotate client tokens   |           Yes |       No |     No |
| User management        |           Yes |       No |     No |
| Role management        |           Yes |       No |     No |

The interface should reflect these permissions.

More importantly, the API must enforce them independently.

---

# 118. Verify Administrator Access

Log in as Administrator.

Verify access to:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management
```

Verify client-management functions:

```text
Create client
Disable client
Rotate client token
```

The Administrator should be able to perform these operations.

---

# 119. Verify Operator Access

Log in as Operator.

Verify access to:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
```

Verify that administrator-only functionality is unavailable:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

Do not rely only on hidden UI elements.

Protected API operations must reject unauthorized requests.

---

# 120. Verify Viewer Access

Log in as Viewer.

The Viewer should be able to access:

```text
Clients
Installed software
```

The following must not be available:

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

The Viewer must not be able to mutate client state.

---

# 121. Verify Client Authentication

Confirm that every client uses its own Bearer token.

The expected model is:

```text
Client A → Token A
Client B → Token B
Client C → Token C
```

Do not share tokens between clients.

Verify that a rotated or revoked token is no longer accepted.

Never place real tokens into test output or documentation.

---

# 122. Verify Update Detection

On a test client:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Then verify the client in the LUMS interface.

The reported information should include current package inventory and update information where supported.

---

# 123. Verify Update Job Creation

Create a controlled update job through the LUMS interface.

The job should initially appear as:

```text
PENDING
```

The Watcher then processes the job:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

or:

```text
PENDING
   ↓
RUNNING
   ↓
FAILED
```

depending on the actual operation result.

Do not manually change the database state.

---

# 124. Verify Job Execution

Inspect the client Watcher:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Inspect the LUMS server:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Compare the server-side job state with the client-side execution result.

The two must agree.

---

# 125. Verify Package Result Validation

A job must not become successful merely because the client submitted a syntactically valid response.

The server validates the returned result.

Verify this through the automated result-validation tests:

```bash
./.venv-test/bin/pytest -q \
    tests/test_job_result.py
```

A successful result must contain the expected structure and valid job context.

Malformed or inconsistent results must be rejected.

---

# 126. Verify Job Recovery

Use a dedicated test client for recovery testing.

The recovery model is:

```text
Job
 │
 ├── package item A → SUCCESS
 ├── package item B → SUCCESS
 └── package item C → interrupted
                       │
                       ▼
                    recovery
                       │
                       ▼
                  resume safely
```

After recovery, previously successful package items must not be unnecessarily repeated.

Inspect:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Then verify the final job state in LUMS.

---

# 127. Verify Reboot Detection

For a controlled test update that requires a reboot, verify that the client reports the reboot requirement.

After reboot:

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

and:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

The client must resume normal reporting after boot.

---

# 128. Verify Audit Logging

Perform a controlled administrative action, then inspect the LUMS audit log.

Relevant operations include:

```text
Login
User creation
Client creation
Client-token rotation
Job creation
Package management
```

Audit entries should provide enough information to reconstruct the administrative action without exposing secrets.

Do not log:

```text
Passwords
Client tokens
Application secrets
Private keys
Session secrets
```

---

# 129. Verify Log Redaction

Inspect recent logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Inspect client logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

and:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Authentication credentials and secrets must not appear in normal diagnostic output.

If a diagnostic command would expose a secret, do not paste its output into an issue, commit or documentation.

---

# 130. Verify Network Exposure

Inspect listening ports:

```bash
sudo ss -lntp
```

The LUMS application port should remain:

```text
127.0.0.1:5050
```

Nginx provides the external service:

```text
:80
:443
```

The application must not be directly exposed through:

```text
0.0.0.0:5050
```

or:

```text
0.0.0.0:5000
```

---

# 131. Verify Firewall Configuration

If a host firewall is enabled, inspect it:

```bash
sudo ufw status verbose
```

The deployment should expose only the services required by the host.

Do not create a firewall rule for port `5050` merely because Docker uses that port internally.

The intended architecture is:

```text
LAN
 │
 ▼
443
 │
 ▼
Nginx
 │
 ▼
127.0.0.1:5050
 │
 ▼
LUMS
```

---

# 132. Backup Strategy

The LUMS SQLite database is persistent application state.

At minimum, backups should protect:

```text
LUMS database
TLS material
LUMS application secret
Deployment configuration
```

Backups must be stored outside the active LUMS container.

Do not store backups inside:

```text
/app
```

or rely on the container filesystem.

The Docker volume:

```text
lums-data
```

contains persistent application data, but a Docker volume is not itself a backup.

---

# 133. Database Backup

Before backing up the database, identify the database file:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

A database backup should be performed using a consistent SQLite backup mechanism.

Do not copy a live SQLite database blindly while it is being modified if the backup procedure cannot guarantee consistency.

After creating a backup, verify that the backup file exists and is protected.

---

# 134. Configuration Backup

Protect the following deployment material:

```text
/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums
```

Do not publish these files.

The following files are particularly sensitive:

```text
/etc/lums/secrets/lums_secret
/etc/lums/tls/lums.key
```

Protect backup permissions accordingly.

---

# 135. Restore Planning

A restore should be tested on a non-production system before it is needed for disaster recovery.

The restore sequence is conceptually:

```text
Backup
  ↓
Verify backup integrity
  ↓
Prepare clean LUMS host
  ↓
Restore secret/configuration
  ↓
Restore database
  ↓
Restore TLS material
  ↓
Start LUMS
  ↓
Run integrity checks
  ↓
Validate users/clients/jobs
```

Do not overwrite a production database without first preserving the existing state.

---

# 136. Verify a Database Restore

After restoring a database, run:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

print(
    db.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]
)

db.close()
PY
```

Expected:

```text
ok
```

Then verify:

```text
users
clients
update jobs
package data
audit data
```

Do not assume that a successful SQLite integrity check proves that the complete application state is correct.

---

# 137. Maintenance Principles

Routine maintenance should follow:

```text
Observe
   ↓
Back up
   ↓
Change
   ↓
Verify
```

Do not perform unrelated maintenance during an active update job.

Before maintenance:

```bash
sudo docker ps \
    --filter name=lums
```

Check active jobs in the LUMS interface.

If an update is running, allow it to finish unless the maintenance operation specifically requires interruption.

---

# 138. Container Maintenance

Inspect the running image:

```bash
sudo docker inspect \
    lums \
    --format '{{.Config.Image}}'
```

Inspect the container:

```bash
sudo docker ps \
    --filter name=lums
```

Inspect recent logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Do not remove the persistent volume during ordinary container maintenance.

The volume contains application state.

---

# 139. Image Maintenance

Before replacing the production image:

```bash
cd /opt/lums-public
```

Run the automated tests:

```bash
./.venv-test/bin/pytest -q
```

Build the new image:

```bash
sudo docker build \
    -t lums:new \
    .
```

Do not replace the running container until the image has passed the required validation.

Keep the currently working container available until the replacement has been verified.

---

# 140. Controlled Container Replacement

When replacing the production container:

```text
Current container
       │
       ▼
Backup / checkpoint
       │
       ▼
Build new image
       │
       ▼
Validate image
       │
       ▼
Stop old container
       │
       ▼
Start new container
       │
       ▼
Validate runtime
       │
       ▼
Validate HTTPS
       │
       ▼
Validate application
```

The persistent volume must remain:

```text
lums-data
```

The secret mount must remain read-only.

The application port must remain localhost-only.

---

# 141. Verify Runtime Security After Replacement

After every container replacement, repeat:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Verify:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Also verify:

```bash
sudo docker port \
    lums
```

Expected:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 142. Verify Persistent Data After Replacement

After starting the replacement container:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Then:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY
```

Expected:

```text
ok
```

Finally verify that existing users and clients are still present through the LUMS interface.

---

# 143. Maintenance Completion Checkpoint

After maintenance, verify:

```text
[ ] Container running
[ ] Runtime hardening intact
[ ] Persistent volume mounted
[ ] Database accessible
[ ] SQLite integrity check passes
[ ] Nginx running
[ ] HTTPS working
[ ] Login working
[ ] Existing users present
[ ] Existing clients present
[ ] Agent reporting working
[ ] Watcher working
[ ] Update jobs working
[ ] Audit logging working
```

Only after these checks is the maintenance operation complete.

---

# 144. Installation State at This Point

A correctly installed LUMS environment now consists of:

```text
                    ┌──────────────────────┐
                    │       Browser        │
                    └──────────┬───────────┘
                               │ HTTPS
                               ▼
                    ┌──────────────────────┐
                    │        Nginx         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    LUMS Container    │
                    │                      │
                    │ Flask / Gunicorn     │
                    │ RBAC                 │
                    │ CSRF                 │
                    │ Audit Logging        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │       SQLite         │
                    │     lums-data        │
                    └──────────┬───────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
        ┌──────────────┐              ┌──────────────┐
        │ LUMS Agent   │              │ LUMS Watcher │
        │ 1.7.0        │              │ 1.2.1        │
        └──────┬───────┘              └──────┬───────┘
               │                             │
               ▼                             ▼
        Inventory / Report             Update Jobs
               │                             │
               └──────────────┬──────────────┘
                              ▼
                       APT / pacman
```

This is the intended operational architecture.

The next section covers upgrades, uninstallation and the final installation checklist.

# 145. Upgrade Procedure

LUMS upgrades should be performed in controlled steps.

The recommended sequence is:

```text
Review
   ↓
Backup
   ↓
Test
   ↓
Build
   ↓
Deploy
   ↓
Validate
```

Do not upgrade the production installation solely because a new Git revision exists.

Review the changes first:

```bash
cd /opt/lums-public

git status
git log --oneline -10
```

Review the relevant application, Agent and migration changes before deployment.

---

# 146. Create a Pre-Upgrade Backup

Before replacing the production container, create a current backup of the persistent LUMS state.

Verify the active volume:

```bash
sudo docker inspect \
    lums \
    --format '{{json .Mounts}}'
```

Confirm that:

```text
lums-data
```

is still mounted at:

```text
/var/lib/lums
```

Also protect the external configuration:

```text
/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/
```

Do not proceed with an upgrade if the required backup cannot be verified.

---

# 147. Stop Unnecessary Changes During an Upgrade

Before upgrading, inspect active jobs in the LUMS interface.

Avoid replacing the application while a critical update job is actively executing.

If necessary, wait until the job reaches a final state:

```text
SUCCESS
```

or:

```text
FAILED
```

Do not manually change a job from `RUNNING` to `SUCCESS` or `FAILED` simply to make an upgrade possible.

---

# 148. Update the Repository

Move to the repository:

```bash
cd /opt/lums-public
```

Inspect the current state:

```bash
git status
```

Update the repository using the normal project workflow.

After updating:

```bash
git log --oneline -5
```

Verify that the intended revision is checked out.

Do not deploy a repository containing unintended local modifications.

If local changes are present:

```bash
git status
```

Review them before continuing.

---

# 149. Run the Test Suite Before Building

Run:

```bash
./.venv-test/bin/pytest -q
```

All tests must pass.

The current baseline is:

```text
155 passed
```

The exact count can increase as new tests are added.

A changed test count is not automatically a problem.

The requirement is that the complete suite finishes successfully.

---

# 150. Build the Updated Image

Build a new image without immediately replacing the running container:

```bash
sudo docker build \
    -t lums:new \
    .
```

Verify the image:

```bash
sudo docker image inspect \
    lums:new
```

The build must complete successfully.

Do not use a failed or partially built image for production deployment.

---

# 151. Verify the Updated Image

Review the image metadata:

```bash
sudo docker image inspect \
    lums:new \
    --format '
User={{.Config.User}}
Entrypoint={{json .Config.Entrypoint}}
Cmd={{json .Config.Cmd}}
'
```

The image must preserve the expected non-root application model.

The production runtime must still provide:

```text
read-only root filesystem
dropped Linux capabilities
no-new-privileges
read-only secret mount
persistent application volume
localhost-only application port
```

---

# 152. Replace the Production Container

When the new image has passed validation, replace the running container using the established hardened configuration.

Stop the existing container:

```bash
sudo docker stop \
    lums
```

Remove only the container:

```bash
sudo docker rm \
    lums
```

Do **not** remove:

```text
lums-data
```

Start the replacement with the hardened runtime:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /run:rw,noexec,nosuid,size=16m \
    -p 127.0.0.1:5050:5000 \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    lums:new
```

---

# 153. Verify the Replacement Container

Check:

```bash
sudo docker ps \
    --filter name=lums
```

Then:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Verify the runtime:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Expected:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

---

# 154. Verify Application Availability

Check the local application endpoint:

```bash
curl -I \
    http://127.0.0.1:5050/
```

Then test the public HTTPS path:

```bash
curl -I \
    https://LUMS-SERVER/
```

Verify login through the browser.

Do not consider the upgrade complete until the external HTTPS path has also been tested.

---

# 155. Verify Persistent State After Upgrade

Check the database:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

Run:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY
```

Expected:

```text
ok
```

Verify through the web interface that:

```text
users
clients
jobs
audit history
package information
```

remain available.

---

# 156. Verify Client Communication After Upgrade

Run the Agent on a test client:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Verify that the server accepts the report.

Then verify the client in the LUMS interface.

---

# 157. Verify Update Execution After Upgrade

Create a controlled test job.

Verify:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

or an expected:

```text
FAILED
```

state when the operation genuinely fails.

Inspect the Watcher:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

This confirms that the upgrade did not break the execution path.

---

# 158. Verify Security Baseline After Upgrade

Every production upgrade must preserve the security baseline.

Verify:

```text
[ ] HTTPS
[ ] Bearer client authentication
[ ] RBAC
[ ] CSRF protection
[ ] Audit logging
[ ] Non-root container
[ ] Read-only root filesystem
[ ] Capabilities dropped
[ ] no-new-privileges
[ ] Protected secret mount
[ ] Persistent data volume
[ ] Localhost-only Docker port
[ ] Firewall policy
```

A functional upgrade that weakens these properties is not considered complete.

---

# 159. Rollback Procedure

If the new container fails validation, do not immediately destroy the previous deployment information.

First inspect:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

If the previous image is still available:

```bash
sudo docker images
```

restore the previously validated image using the same hardened container configuration.

The persistent volume remains:

```text
lums-data
```

Do not restore a database backup merely because the application container was replaced.

Only restore the database when the database itself must be recovered.

---

# 160. Uninstallation Preparation

Before uninstalling LUMS, decide whether the persistent application data must be retained.

The following are separate resources:

```text
Container
Image
Persistent volume
Configuration
TLS material
Nginx configuration
Client installations
```

Removing the container does not remove the Docker volume.

This distinction is intentional.

---

# 161. Remove the LUMS Container

Stop the container:

```bash
sudo docker stop \
    lums
```

Remove it:

```bash
sudo docker rm \
    lums
```

Verify:

```bash
sudo docker ps -a \
    --filter name=lums
```

The persistent volume is still present unless explicitly removed.

---

# 162. Remove the LUMS Docker Image

List images:

```bash
sudo docker images \
    'lums*'
```

Remove only images that are no longer required:

```bash
sudo docker rmi \
    lums:new
```

Repeat for other obsolete local LUMS images as appropriate.

Do not remove the image currently required for a rollback before the installation has been fully decommissioned.

---

# 163. Remove the Persistent Volume

Only perform this step when the LUMS database is no longer required.

Verify:

```bash
sudo docker volume inspect \
    lums-data
```

Create a final backup if required.

Then remove:

```bash
sudo docker volume rm \
    lums-data
```

This permanently removes the persistent application data stored in that volume.

Do not run this command during normal upgrades.

---

# 164. Remove LUMS Server Configuration

When the server is permanently decommissioned, remove the LUMS-specific configuration:

```text
/etc/lums/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums
```

Remove the Nginx site:

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/lums
```

Remove the configuration:

```bash
sudo rm -f \
    /etc/nginx/sites-available/lums
```

Then validate Nginx:

```bash
sudo nginx -t
```

Reload:

```bash
sudo systemctl reload nginx
```

Only remove `/etc/lums/` after verifying that no other application depends on it.

---

# 165. Remove Client Installations

LUMS clients must be decommissioned separately.

Disable the Agent timer:

```bash
sudo systemctl disable --now \
    lums-agent.timer
```

Disable the Watcher timer:

```bash
sudo systemctl disable --now \
    lums-agent-watcher.timer
```

Stop any remaining services:

```bash
sudo systemctl stop \
    lums-agent.service \
    lums-agent-watcher.service
```

Remove the installed systemd units:

```bash
sudo rm -f \
    /etc/systemd/system/lums-agent.service \
    /etc/systemd/system/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Remove the Agent installation:

```bash
sudo rm -rf \
    /opt/lums-agent
```

Remove the client configuration:

```bash
sudo rm -f \
    /etc/default/lums-agent
```

Only perform these steps when the client is genuinely being removed from LUMS management.

---

# 166. Final Server Installation Checklist

A completed LUMS installation should satisfy all of the following:

```text
SERVER
[ ] Debian/Linux host prepared
[ ] Docker installed
[ ] Nginx installed
[ ] Repository deployed
[ ] Application secret generated
[ ] TLS material installed
[ ] LUMS image built
[ ] Persistent volume created
[ ] Hardened container deployed
[ ] Container runs as non-root
[ ] Root filesystem is read-only
[ ] Linux capabilities dropped
[ ] no-new-privileges enabled
[ ] Secret mounted read-only
[ ] Persistent data volume mounted
[ ] Application bound to 127.0.0.1:5050
[ ] Nginx HTTPS configured
[ ] HTTP redirects to HTTPS
[ ] TLS verified
[ ] Database initialized
[ ] SQLite integrity check passes
[ ] Migrations complete
```

---

# 167. Final Client Installation Checklist

```text
CLIENT
[ ] Supported Linux distribution
[ ] systemd available
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher installed
[ ] Watcher version verified
[ ] Client configuration protected
[ ] Unique client token configured
[ ] TLS trust configured
[ ] Agent manual run succeeds
[ ] Initial report accepted
[ ] Client visible in LUMS
[ ] Reporting timer enabled
[ ] Watcher timer enabled
[ ] Idle detection verified
[ ] Package inventory verified
[ ] Update detection verified
```

---

# 168. Final Functional Checklist

```text
FUNCTIONALITY
[ ] Administrator login works
[ ] Operator login works
[ ] Viewer login works
[ ] Administrator RBAC verified
[ ] Operator RBAC verified
[ ] Viewer RBAC verified
[ ] Client authentication verified
[ ] Token rotation verified
[ ] Package search verified
[ ] Package installation verified
[ ] Package removal verified
[ ] Package update verified
[ ] System update path verified
[ ] Update jobs verified
[ ] Job result validation verified
[ ] Job recovery verified
[ ] Reboot detection verified
[ ] Audit logging verified
[ ] Logs contain no secrets
[ ] End-to-end reporting verified
[ ] End-to-end update execution verified
```

---

# 169. Final Security Checklist

```text
SECURITY
[ ] HTTPS enforced
[ ] Client Bearer authentication enabled
[ ] RBAC enforced server-side
[ ] CSRF protection enabled
[ ] Session protection enabled
[ ] Login rate limiting enabled
[ ] Password hashing enabled
[ ] Client token hashing enabled
[ ] Client token rotation available
[ ] Audit logging enabled
[ ] Secrets outside Git
[ ] Secrets outside Docker image
[ ] TLS private key protected
[ ] Docker root filesystem read-only
[ ] Linux capabilities dropped
[ ] no-new-privileges enabled
[ ] Container runs as non-root
[ ] Persistent data isolated in volume
[ ] Application port localhost-only
[ ] Firewall reviewed
[ ] Default Nginx site removed or controlled
[ ] Backup procedure defined
[ ] Restore procedure tested
```

---

# 170. Final Test Checklist

Run the complete automated test suite:

```bash
cd /opt/lums-public

./.venv-test/bin/pytest -q
```

The installation should only be considered complete when the complete test suite passes.

Then verify the production runtime manually:

```bash
sudo docker ps \
    --filter name=lums
```

```bash
sudo docker logs \
    --tail 100 \
    lums
```

```bash
curl -I \
    https://LUMS-SERVER/
```

```bash
sudo ss -lntp
```

---

# 171. Final Documentation Check

Before declaring the installation complete, verify that the documentation matches the actual deployment.

At minimum, review:

```text
docs/installation.md
docs/security.md
docs/troubleshooting.md
```

The documentation must not contain:

```text
old container commands
obsolete image names
obsolete RBAC rules
obsolete test counts
obsolete service paths
obsolete authentication mechanisms
real secrets
real client tokens
private keys
```

If the deployment changes, update the documentation together with the implementation.

---

# 172. Release Readiness

A successful installation does not automatically mean that LUMS has an official release.

The current project state deliberately separates:

```text
Working implementation
Security audit
Documentation review
Release preparation
Versioning
Git tag
GitHub Release
```

An official LUMS release should only be created after the complete implementation, security review, documentation review and final validation have been completed.

Until then, treat the repository as an actively developed project.

---

# 173. Operational Baseline

The current documented baseline is:

```text
LUMS Server
    Docker
    Nginx
    HTTPS
    SQLite
    RBAC
    CSRF
    Audit Logging
    Hardened Container

LUMS Agent
    Version 1.7.0

LUMS Watcher
    Version 1.2.1

Database
    journal_mode=wal
    busy_timeout=5000
    synchronous=2
    foreign_keys=ON (application connections)

Container
    non-root
    read-only root filesystem
    CapDrop=ALL
    no-new-privileges
    localhost-only application port

Roles
    Administrator
    Operator
    Viewer
```

This baseline should be treated as the reference state for troubleshooting and future maintenance.

---

# 174. Installation Complete

The installation is complete when:

```text
Server
  │
  ├── HTTPS works
  ├── Authentication works
  ├── RBAC works
  ├── Database is healthy
  ├── Container is hardened
  └── Persistent storage is verified
       │
       ▼
Client
  │
  ├── Agent reports
  ├── Watcher executes
  ├── Package manager works
  ├── Jobs complete
  ├── Results are validated
  └── Recovery works
       │
       ▼
Operations
  │
  ├── Backup exists
  ├── Restore is understood
  ├── Troubleshooting documentation is available
  └── Security baseline is maintained
```

The fundamental LUMS operational principle is:

```text
Observe first.
Change second.
Verify third.
Document last.
```

For production changes, extend this to:

```text
Backup
   ↓
Change
   ↓
Verify
   ↓
Document
```

A LUMS installation should always remain reproducible, auditable and recoverable.
