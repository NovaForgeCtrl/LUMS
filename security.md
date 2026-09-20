# LUMS Security

> **Linux Update Management Server**
>
> Security principles, operational requirements and responsible handling of sensitive information in LUMS.

---

## 1. Security Philosophy

LUMS follows a simple principle:

> **Centralized management does not mean centralized trust.**

LUMS manages Linux clients, receives inventory information and distributes update jobs.

The actual package installation remains on the managed Linux client.

```text
                    ┌─────────────────────┐
                    │      LUMS Server    │
                    │                     │
                    │ Docker              │
                    │ Flask               │
                    │ Authentication      │
                    │ Authorization       │
                    │ Inventory           │
                    │ Update Jobs         │
                    └──────────┬──────────┘
                               │
                         HTTPS + Token
                               │
                    ┌──────────▼──────────┐
                    │    Linux Client     │
                    │                     │
                    │ lums-agent          │
                    │ APT / dpkg          │
                    └─────────────────────┘
```

Security depends on multiple layers:

```text
Network
   ↓
TLS
   ↓
Nginx
   ↓
Authentication
   ↓
Authorization
   ↓
Application
   ↓
Docker
   ↓
Database
   ↓
Operating System
   ↓
APT / dpkg
```

A weakness in one layer must never be used as a reason to disable another security layer.

---

## 2. Security Scope

This document covers:

- Docker deployment security
- Server authentication
- Client authentication
- Authorization
- TLS
- Secrets
- SQLite database protection
- Nginx
- systemd agent services
- Git repository security
- Update execution
- Logging
- Backup protection
- Incident handling

This document does not replace the security documentation of:

- Ubuntu
- Debian
- Docker
- Python
- Flask
- Nginx
- SQLite
- APT
- dpkg

---

## 3. Current Installation

The current LUMS installation uses Docker and Nginx.

| Component | Configuration |
|---|---|
| Server IP | `IP Address` |
| Repository | `/opt/lums-public` |
| Docker container | `lums` |
| Docker image | `lums:latest` |
| Docker volume | `lums-data` |
| Internal Flask port | `5000` |
| Host binding | `127.0.0.1:5050` |
| HTTPS endpoint | `https://IP Address` |
| Nginx HTTP port | `80` |
| Nginx HTTPS port | `443` |
| Database | `/var/lib/lums/lums.db` |
| Environment file | `/etc/lums/docker/lums.env` |

The Docker application is only bound to localhost:

```text
127.0.0.1:5050 → Docker container port 5000
```

The external application endpoint is provided by Nginx:

```text
Client
   │
   │ HTTPS :443
   ▼
Nginx
   │
   │ HTTP localhost:5050
   ▼
Docker container
   │
   │ Flask :5000
   ▼
SQLite
```

---

## 4. Sensitive Information

The following information must be treated as sensitive:

```text
LUMS server secret
Client tokens
Authentication hashes
Administrator passwords
TLS private keys
Session information
Database contents
Internal infrastructure information
```

Important sensitive files:

```text
/etc/lums/docker/lums.env
/etc/nginx/ssl/lums/lums.key
/etc/default/lums-agent
```

The Docker volume contains the operational database:

```text
lums-data:/var/lib/lums
```

> [!CAUTION]
>
> Never commit sensitive files or their contents to Git.

---

## 5. Secrets Management

### 5.1 Docker Server Secret

The LUMS server secret is stored outside the Git repository:

```text
/etc/lums/docker/lums.env
```

The Docker container loads the file using:

```bash
sudo docker run \
    --env-file /etc/lums/docker/lums.env \
    ...
```

Protect the file:

```bash
sudo chown root:root /etc/lums/docker/lums.env
sudo chmod 600 /etc/lums/docker/lums.env
```

Check the permissions without displaying its content:

```bash
sudo ls -l /etc/lums/docker/lums.env
```

Check whether the secret exists:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' \
    /etc/lums/docker/lums.env \
    && echo "Secret vorhanden" \
    || echo "Secret fehlt"
```

Never publish the contents of the environment file.

---

### 5.2 Client Token

The client configuration is stored in:

```text
/etc/default/lums-agent
```

Example structure:

```ini
LUMS_BASE=https://SERVER_IP
LUMS_TOKEN=CLIENT_TOKEN
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

The real token must never appear in:

- Git commits
- README files
- Screenshots
- Documentation
- Public issue reports
- Chat messages
- Log files

Use placeholders:

```text
SERVER_IP
CLIENT_TOKEN
JOB_ID
PACKAGE
```

---

## 6. Client Authentication

LUMS clients authenticate using Bearer tokens.

The request contains:

```http
Authorization: Bearer <client-token>
```

The server stores a SHA-256 hexadecimal digest of the client token instead of the plaintext token.

Authentication flow:

```text
Client Token
     │
     ▼
SHA-256
     │
     ▼
Hexadecimal Digest
     │
     ▼
SQLite clients table
```

The authentication format must remain consistent with the LUMS implementation.

Do not replace the client token hash with:

- Plaintext tokens
- Password hashes
- Arbitrary hashes
- Another encoding format

unless the application implementation is changed accordingly.

---

## 7. Client Authorization

Authentication and authorization are separate concepts.

```text
Authentication
    ↓
Who is this client?

Authorization
    ↓
What is this client allowed to access?
```

A valid token must not automatically provide access to every client resource.

The server must restrict clients to their permitted authorization scope.

Example:

```text
Client A
   │
   └── requests Client B data
            │
            ▼
          DENIED
```

This is particularly important for:

```text
/api/client/me
/api/report
/client inventory
/update jobs
/job results
```

---

## 8. Client Identity

The client should use its authenticated identity instead of trusting arbitrary client IDs supplied by the client.

The endpoint:

```text
GET /api/client/me
```

can be used to obtain the authenticated client context.

Client-specific operations must be validated on the server.

The server must not rely solely on:

- Client-supplied IDs
- Request parameters
- Hidden form fields
- Frontend restrictions

Authorization must be enforced server-side.

---

## 9. TLS

LUMS uses HTTPS between agents and the server.

Certificate:

```text
/etc/nginx/ssl/lums/lums.crt
```

Private key:

```text
/etc/nginx/ssl/lums/lums.key
```

The private key is highly sensitive.

Recommended permissions:

```bash
sudo chown root:root /etc/nginx/ssl/lums/lums.key
sudo chmod 600 /etc/nginx/ssl/lums/lums.key

sudo chmod 644 /etc/nginx/ssl/lums/lums.crt
```

---

## 10. Certificate SAN

The current LUMS server address is:

```text
IP Address
```

The certificate must contain the server IP as a Subject Alternative Name:

```text
IP Address:IP Address
```

Inspect the certificate:

```bash
sudo openssl x509 \
    -in /etc/nginx/ssl/lums/lums.crt \
    -noout \
    -subject \
    -dates
```

Inspect the SAN:

```bash
sudo openssl x509 \
    -in /etc/nginx/ssl/lums/lums.crt \
    -noout \
    -ext subjectAltName
```

The address used by the client must match a SAN in the certificate.

---

## 11. Certificate Verification

Certificate verification must remain enabled during normal operation.

Do not permanently solve TLS problems by:

- Disabling certificate verification
- Ignoring certificate errors
- Using insecure HTTP
- Removing the CA configuration

The following command bypasses certificate verification and is intended only for diagnostics:

```bash
curl -k https://IP Address/
```

Normal operation should use the configured CA certificate:

```bash
curl --cacert /opt/lums-agent/lums-ca.crt \
    https://IP Address/
```

---

## 12. Network Exposure

The intended architecture is:

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
Docker container :5000
```

The Docker application must not be exposed directly to the network.

Check the Docker port binding:

```bash
sudo docker port lums
```

Check listening ports:

```bash
sudo ss -lntp
```

Expected application binding:

```text
127.0.0.1:5050
```

Avoid exposing the application using:

```text
0.0.0.0:5000
```

unless the security architecture is deliberately redesigned and reviewed.

---

## 13. HTTP and HTTPS

Normal communication must use:

```text
https://SERVER_IP
```

Test the HTTP redirect:

```bash
curl -I http://IP Address/
```

Test HTTPS:

```bash
curl -k -I https://IP Address/
```

HTTP should redirect to HTTPS.

Sensitive information must never be transmitted through unencrypted HTTP.

---

## 14. Nginx Security

Nginx is the public-facing reverse proxy.

Responsibilities:

- TLS termination
- HTTP-to-HTTPS redirection
- Forwarding requests to Docker
- Preventing direct external access to Flask
- Providing the external HTTPS endpoint

Validate the configuration:

```bash
sudo nginx -t
```

Reload Nginx only after a successful configuration test:

```bash
sudo systemctl reload nginx
```

Check the service:

```bash
sudo systemctl status nginx --no-pager
```

---

## 15. Docker Security

The LUMS application runs inside the Docker container:

```text
lums
```

Check the container:

```bash
sudo docker ps --filter name=lums
```

Inspect the container:

```bash
sudo docker inspect lums
```

View the logs:

```bash
sudo docker logs --tail 100 lums
```

Follow the logs:

```bash
sudo docker logs -f lums
```

The Docker volume contains persistent application data.

Do not remove the volume during normal troubleshooting.

> [!CAUTION]
>
> Removing `lums-data` can permanently delete the LUMS database and operational state.

Never execute the following command without a verified backup:

```bash
sudo docker volume rm lums-data
```

---

## 16. Docker Environment Protection

The server environment file is:

```text
/etc/lums/docker/lums.env
```

The file must remain outside the Git repository:

```text
/opt/lums-public
```

Recommended permissions:

```text
Owner: root
Group: root
Mode: 0600
```

Apply the permissions:

```bash
sudo chown root:root /etc/lums/docker/lums.env
sudo chmod 600 /etc/lums/docker/lums.env
```

Do not copy the environment file into the project directory.

---

## 17. Agent Security

The agent performs security-sensitive operations:

```text
Authenticate
   ↓
Report inventory
   ↓
Retrieve update jobs
   ↓
Execute package updates
   ↓
Report results
```

The agent requires access to:

- Client token
- TLS CA certificate
- APT
- dpkg
- System package management

The agent configuration must therefore be protected.

---

## 18. Agent Configuration Protection

The agent configuration is:

```text
/etc/default/lums-agent
```

Recommended permissions:

```bash
sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

Check the permissions:

```bash
sudo ls -l /etc/default/lums-agent
```

Display configuration values without revealing the token:

```bash
sudo awk -F= '
/^LUMS_BASE=/ {
    print $1 "=" $2
}
/^LUMS_CA_FILE=/ {
    print $1 "=" $2
}
/^LUMS_TOKEN=/ {
    print "LUMS_TOKEN=<redacted>"
}
' /etc/default/lums-agent
```

---

## 19. Agent TLS Certificate

The agent uses a copied CA certificate:

```text
/opt/lums-agent/lums-ca.crt
```

Check the certificate:

```bash
sudo ls -l /opt/lums-agent/lums-ca.crt
```

Inspect the certificate:

```bash
sudo openssl x509 \
    -in /opt/lums-agent/lums-ca.crt \
    -noout \
    -subject \
    -dates
```

The certificate must correspond to the certificate presented by Nginx.

Do not permanently disable TLS verification to bypass certificate problems.

---

## 20. systemd Agent Services

The agent uses:

```text
lums-agent.service
lums-agent.timer
```

The service is a oneshot service.

Execution flow:

```text
Timer
  ↓
Service
  ↓
Agent
  ↓
Exit
```

The timer remains active and starts the service at the configured interval.

An expected state after successful execution is:

```text
lums-agent.service
inactive (dead)
status 0/SUCCESS
```

This is normal for a successful oneshot service.

Enable the timer:

```bash
sudo systemctl enable --now lums-agent.timer
```

Check the timer:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

Check the next execution:

```bash
systemctl list-timers --all | grep lums-agent
```

Check the latest service execution:

```bash
sudo systemctl status lums-agent.service --no-pager
```

View service logs:

```bash
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

---

## 21. Update Execution

LUMS manages update jobs, but the client agent executes package operations.

```text
Administrator
     │
     ▼
LUMS update job
     │
     ▼
Client agent
     │
     ▼
APT / dpkg
     │
     ▼
Package installation
     │
     ▼
Result reporting
```

APT remains responsible for:

- Package dependency resolution
- Repository trust
- Package signatures
- Package installation
- dpkg operations

The agent must not silently bypass the operating system's package-management mechanisms.

---

## 22. Automatic Reboots

LUMS does not automatically reboot clients.

The agent checks:

```text
/var/run/reboot-required
```

Check manually:

```bash
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot required"
```

A required reboot is reported as an administrative condition.

The reboot remains a deliberate operational decision.

---

## 23. Database Security

LUMS uses SQLite inside the Docker volume:

```text
lums-data
```

The database path inside the container is:

```text
/var/lib/lums/lums.db
```

The database may contain:

- Clients
- Authentication hashes
- Inventory
- Available updates
- Installed packages
- Update jobs
- Job results
- Audit information

Database access must be restricted to the LUMS application and authorized administrators.

---

## 24. Database Integrity

Check the SQLite database from inside the running container:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

connection = sqlite3.connect("/var/lib/lums/lums.db")
result = connection.execute("PRAGMA integrity_check;").fetchone()[0]
print(result)
connection.close()
'
```

Expected result:

```text
ok
```

Do not modify the database manually without:

1. A verified backup
2. A clear reason
3. An understanding of the schema
4. A validation after the change

---

## 25. Database Backup

Create a backup directory:

```bash
sudo install -d -m 700 /var/backups/lums
```

Create a SQLite backup from inside the container:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

source = sqlite3.connect("/var/lib/lums/lums.db")
backup = sqlite3.connect("/var/lib/lums/lums.backup.db")

source.backup(backup)

backup.close()
source.close()
'
```

Copy the backup outside the container:

```bash
sudo docker cp \
    lums:/var/lib/lums/lums.backup.db \
    "/var/backups/lums/lums-$(date +%F_%H-%M-%S).db"
```

Remove the temporary backup:

```bash
sudo docker exec \
    lums \
    rm -f /var/lib/lums/lums.backup.db
```

Protect the backup files:

```bash
sudo find /var/backups/lums \
    -type f \
    -name "*.db" \
    -exec chmod 600 {} \;
```

Backups must not be committed to Git.

---

## 26. Database Restore

A database restore must be treated as a controlled maintenance operation.

Before restoring:

1. Stop the LUMS container.
2. Create a backup of the current database.
3. Verify the restore source.
4. Restore the database.
5. Check file permissions.
6. Start the container.
7. Run an integrity check.
8. Test authentication and client reporting.

Never overwrite the only available database copy.

---

## 27. Filesystem Permissions

Sensitive files must be owned by the appropriate administrative account.

Review permissions:

```bash
sudo ls -l /etc/lums/docker/lums.env
sudo ls -l /etc/default/lums-agent
sudo ls -l /etc/nginx/ssl/lums/
```

Recommended protection:

```text
Environment files: 0600
Private keys:      0600
Public certificates: 0644
Agent configuration: 0600
Backup directory: 0700
```

Permissions must be reviewed after:

- Installation
- Updates
- Manual changes
- File copies
- Restores
- Deployment operations

---

## 28. Git Repository Security

The repository is located at:

```text
/opt/lums-public
```

Before committing changes:

```bash
cd /opt/lums-public
git status
```

Review the changed files:

```bash
git diff
```

Check tracked files:

```bash
git ls-files
```

Do not commit:

```text
.env files
Private keys
Client tokens
Passwords
Database files
Backups
Session data
Internal IP information
Personal information
```

Use placeholders in documentation:

```text
SERVER_IP
CLIENT_IP
CLIENT_TOKEN
ADMIN_PASSWORD
```

---

## 29. Secure Git Workflow

Before pushing changes:

```bash
cd /opt/lums-public

git status
git diff --check
git diff
```

Review the commit history:

```bash
git log --oneline --decorate -5
```

Use the configured repository identity:

```text
Name:  NovaForgeCtrl
Email: 232026481+NovaForgeCtrl@users.noreply.github.com
```

Do not push unreviewed changes directly to the main branch.

---

## 30. Docker Deployment Updates

The LUMS application is deployed by building a Docker image and recreating the container.

Before updating:

```bash
cd /opt/lums-public

git status --short
git fetch origin
git log --oneline --decorate -3
```

Update the repository:

```bash
git pull --ff-only origin main
```

Build the Docker image:

```bash
sudo docker build -t lums:latest .
```

Stop and remove the container:

```bash
sudo docker stop lums
sudo docker rm lums
```

> [!CAUTION]
>
> Do not remove the `lums-data` volume.

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

Check the deployment:

```bash
sudo docker ps
sudo docker logs --tail 100 lums
```

Test the local application:

```bash
curl -I http://127.0.0.1:5050/
```

Test HTTPS through Nginx:

```bash
curl -k -I https://IP Address/
```

---

## 31. Deployment Requirements

Every deployment should verify:

- Docker image builds successfully
- Container starts successfully
- Environment file is available
- Persistent volume is mounted
- Nginx configuration is valid
- HTTPS is reachable
- Login works
- Client authentication works
- Client reporting works
- Update jobs remain available
- Database integrity is valid

A successful Docker build alone does not prove a successful deployment.

---

## 32. Logging

LUMS uses Docker logs for the server application:

```bash
sudo docker logs --tail 100 lums
```

Follow live logs:

```bash
sudo docker logs -f lums
```

The agent uses systemd journal logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Nginx logs can be reviewed using:

```bash
sudo journalctl -u nginx -n 100 --no-pager
```

Logs must not contain:

- Plaintext client tokens
- Passwords
- Server secrets
- Private keys
- Session secrets

---

## 33. Flask Deployment Considerations

The current LUMS application runs Flask inside the Docker container.

The Flask development server displays a warning when used.

This configuration is acceptable only for the current controlled laboratory environment.

For a production deployment, consider:

- A production WSGI server
- Process supervision
- Resource limits
- Container hardening
- Dedicated service accounts
- Security updates
- Monitoring
- Centralized logging
- Network segmentation

The current laboratory deployment must not automatically be considered production-ready.

---

## 34. Security Headers

The application should provide appropriate security headers where applicable.

Recommended headers include:

```text
Content-Security-Policy
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Strict-Transport-Security
```

Header configuration must be tested carefully to avoid breaking the application.

Check response headers:

```bash
curl -k -I https://IP Address/
```

HSTS should only be enabled after HTTPS is correctly configured and intended for the environment.

---

## 35. Incident Handling

If a client token is compromised:

1. Identify the affected client.
2. Revoke or replace the token.
3. Review recent client activity.
4. Check server logs.
5. Issue a new token.
6. Update the client configuration.
7. Verify successful authentication.
8. Document the incident.

If the server secret is compromised:

1. Restrict access to the server.
2. Review application logs.
3. Rotate the secret.
4. Restart the Docker container.
5. Verify authentication and sessions.
6. Review related credentials.
7. Document the incident.

If a TLS private key is compromised:

1. Replace the certificate and private key.
2. Update the trusted CA on clients.
3. Reload Nginx.
4. Verify certificate validation.
5. Review possible unauthorized access.

---

## 36. Security Testing Checklist

### Server

- [ ] Docker container is running
- [ ] Docker volume is mounted
- [ ] Application binds only to localhost
- [ ] Port `5000` is not externally exposed
- [ ] Nginx configuration passes validation
- [ ] HTTPS is enabled
- [ ] HTTP redirects to HTTPS
- [ ] TLS certificate contains the correct SAN
- [ ] Private key permissions are restricted
- [ ] Environment file permissions are restricted

### Authentication

- [ ] Administrator authentication works
- [ ] Invalid credentials are rejected
- [ ] Invalid client tokens are rejected
- [ ] Client tokens are not logged
- [ ] Client token hashes use the expected format
- [ ] Authentication endpoints require authentication where appropriate

### Authorization

- [ ] Clients cannot access other clients' data
- [ ] Client IDs are validated server-side
- [ ] Update jobs are restricted to authorized clients
- [ ] Job results are restricted to authorized clients
- [ ] Administrative endpoints are protected

### Agent

- [ ] Agent uses HTTPS
- [ ] TLS verification is enabled
- [ ] CA certificate is available
- [ ] Agent configuration is protected
- [ ] Timer is enabled
- [ ] Service execution succeeds
- [ ] Inventory reporting works
- [ ] Update job retrieval works
- [ ] Job result reporting works

### Database

- [ ] Database integrity check returns `ok`
- [ ] Backups are created
- [ ] Backups are protected
- [ ] Database files are not committed to Git
- [ ] Restore procedure is documented

### Git

- [ ] No secrets are committed
- [ ] No private keys are committed
- [ ] No tokens are committed
- [ ] No database files are committed
- [ ] Changes are reviewed before pushing
- [ ] Documentation uses placeholders

---

## 37. Responsible Security Reporting

Security issues should be reported responsibly.

A security report should contain:

- Short description
- Affected component
- Reproduction steps
- Expected behavior
- Actual behavior
- Potential impact
- Suggested mitigation
- Relevant logs with secrets removed

Never include:

- Passwords
- Client tokens
- Private keys
- Server secrets
- Personal information
- Complete production databases

Always redact sensitive information before sharing logs or screenshots.

---

## 38. Security Maintenance

Security reviews should be performed after:

- Application changes
- Authentication changes
- Authorization changes
- Docker changes
- Nginx changes
- Certificate changes
- Database schema changes
- Agent changes
- Deployment changes

Regularly review:

```text
Docker images
Operating system updates
Python dependencies
Flask dependencies
Nginx configuration
TLS certificates
File permissions
Database backups
Git history
Authentication behavior
Authorization behavior
```

---

## 39. Security Principles

The following principles apply to LUMS:

1. Never store secrets in Git.
2. Never expose the Flask application directly to the network.
3. Use HTTPS for client communication.
4. Keep TLS verification enabled.
5. Separate authentication from authorization.
6. Validate client identity server-side.
7. Protect the Docker environment file.
8. Protect client tokens.
9. Protect TLS private keys.
10. Keep database backups secure.
11. Do not remove persistent volumes during troubleshooting.
12. Do not automatically reboot clients.
13. Review changes before deployment.
14. Test security-sensitive changes.
15. Document incidents and configuration changes.

---

## 40. Final Principle

LUMS is designed to centralize Linux update management without removing operational control from the administrator.

The system should remain:

- Transparent
- Auditable
- Controlled
- Secure
- Documented
- Maintainable

> **LUMS — Linux Update Management without the noise.**
>
> **Secure the management plane. Keep execution controlled.**
