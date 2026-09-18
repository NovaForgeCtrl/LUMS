# LUMS Security

> **Linux Update Management Server**
>
> Security principles, operational requirements and responsible handling of sensitive information in LUMS.

---

## 1. Security Philosophy

LUMS is designed around a simple principle:

> **Centralized management does not mean centralized trust.**

The LUMS server manages clients, receives inventory information and distributes update jobs.

The actual package installation remains on the managed Linux client.

```text
                    ┌─────────────────────┐
                    │      LUMS Server    │
                    │                     │
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

Security therefore depends on multiple layers:

```text
Network
   ↓
TLS
   ↓
Authentication
   ↓
Authorization
   ↓
Application
   ↓
Database
   ↓
Operating System
   ↓
Package Management
```

A weakness in one layer must not be treated as a reason to disable another layer.

---

# 2. Security Scope

This document covers:

* server security
* client authentication
* authorization
* TLS
* secrets
* database protection
* systemd services
* Nginx
* Git repository security
* update execution
* logging
* incident handling

It does not replace the security documentation of the underlying operating system, Python, Flask, Nginx, SQLite or APT.

---

# 3. Sensitive Information

The following information must be treated as sensitive:

```text
LUMS server secrets
Client tokens
Authentication hashes
Passwords
TLS private keys
Session information
Database contents
Internal infrastructure information
```

Examples of sensitive files:

```text
/etc/lums.env
/etc/nginx/ssl/lums.key
/etc/default/lums-agent
/var/lib/lums/lums.db
```

> [!CAUTION]
> Never commit these files or their contents to the Git repository.

---

# 4. Secrets Management

## 4.1 Server Secret

The server environment is stored outside the Git repository:

```text
/etc/lums.env
```

The systemd service loads this file through:

```ini
EnvironmentFile=/etc/lums.env
```

The file must not be committed to Git.

---

## 4.2 Client Token

The client configuration is:

```text
/etc/default/lums-agent
```

The configuration contains the client token.

Example:

```ini
LUMS_BASE=https://192.168.2.229
LUMS_CA_FILE=/etc/nginx/ssl/lums.crt
LUMS_TOKEN=CLIENT_TOKEN
```

The real token must never appear in:

* Git commits
* README files
* screenshots
* documentation
* public issue reports
* example configuration files

Use placeholders instead:

```text
CLIENT_TOKEN
SERVER_IP
```

---

# 5. Client Authentication

LUMS clients authenticate using Bearer tokens.

The request contains:

```http
Authorization: Bearer <client-token>
```

The server does not need to store the plaintext client token.

The authentication model is:

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
SQLite
```

The corresponding authentication value is stored in the client database record.

Database:

```text
/var/lib/lums/lums.db
```

> [!IMPORTANT]
> The authentication format must remain consistent with the implementation in the LUMS security layer.

Do not replace the client authentication hash with:

* plaintext tokens
* password hashes
* arbitrary hashes
* another encoding format

unless the application implementation is changed accordingly.

---

# 6. Client Authorization

Authentication and authorization are separate concepts.

```text
Authentication
     │
     └── Who is this client?

Authorization
     │
     └── What is this client allowed to access?
```

A valid token does not automatically grant access to every client resource.

The server must ensure that authenticated clients operate within their own authorization scope.

For example:

```text
Client A
   │
   └── requests Client B data
            │
            ▼
        DENIED
```

This distinction is particularly important for:

```text
/api/client/me
client inventory
update jobs
job results
```

---

# 7. `/api/client/me`

Authenticated agents use:

```text
GET /api/client/me
```

to obtain their authenticated client context.

This endpoint is intentionally separate from administrative client management.

The agent should use its authenticated identity rather than supplying arbitrary client IDs for operations that belong to the current client.

---

# 8. TLS

LUMS uses HTTPS between clients and the server.

The current server certificate is:

```text
/etc/nginx/ssl/lums.crt
```

The private key is:

```text
/etc/nginx/ssl/lums.key
```

The private key is highly sensitive.

```text
/etc/nginx/ssl/lums.key
        │
        └── NEVER commit to Git
```

---

## 8.1 Certificate SAN

The current LUMS server uses:

```text
192.168.2.229
```

The certificate must contain the server address as a Subject Alternative Name:

```text
IP Address:192.168.2.229
```

The client must connect using an address that matches the certificate SAN.

---

## 8.2 Certificate Verification

Certificate verification must remain enabled during normal operation.

Do not permanently solve certificate problems by:

```text
disabling verification
ignoring certificate errors
using insecure HTTP
```

A diagnostic command may temporarily use:

```bash
curl -k
```

but `-k` means that certificate verification is bypassed.

It is therefore a diagnostic tool, not a security solution.

---

# 9. Network Exposure

The intended LUMS architecture is:

```text
Client
   │
   │ HTTPS :443
   ▼
Nginx
   │
   │ HTTP localhost
   ▼
Flask
127.0.0.1:5000
```

Flask should listen only on:

```text
127.0.0.1:5000
```

It should not be exposed directly as:

```text
0.0.0.0:5000
```

Port `5000` is an internal application port.

The externally accessible application interface is Nginx over HTTPS.

---

# 10. HTTP and HTTPS

The current Nginx configuration provides:

```text
HTTP :80
   │
   └── redirect
          ↓
HTTPS :443
```

Normal client communication should therefore use:

```text
https://SERVER_IP
```

rather than:

```text
http://SERVER_IP
```

The HTTP listener exists for redirection and should not be treated as the secure application endpoint.

---

# 11. Nginx Security

Nginx acts as the public-facing reverse proxy.

Responsibilities include:

* TLS termination
* HTTP → HTTPS redirection
* proxying requests to Flask
* exposing Flask only indirectly

The configuration should be validated before reload:

```bash
sudo nginx -t
```

Only after a successful configuration test should Nginx be reloaded.

```bash
sudo systemctl reload nginx
```

> [!IMPORTANT]
> Never reload a known-invalid Nginx configuration during production troubleshooting.

---

# 12. Flask Security

Flask is intentionally bound to:

```text
127.0.0.1:5000
```

This means clients cannot directly connect to the Flask application.

The expected path is:

```text
Internet / LAN
      │
      ▼
Nginx :443
      │
      ▼
Flask :5000
```

This separation reduces the externally exposed application surface.

---

# 13. Systemd Services

LUMS uses systemd for service management.

Server:

```text
lums.service
```

Client:

```text
lums-agent.service
lums-agent.timer
```

The agent is a oneshot service.

It does not need to run permanently.

```text
Timer
  ↓
Service
  ↓
Agent
  ↓
Exit
```

This limits the amount of time during which the client agent process is active.

---

# 14. Agent Security

The agent performs several security-sensitive operations:

```text
authenticate
report inventory
retrieve jobs
execute package updates
report results
```

The agent therefore requires access to:

```text
client token
TLS certificate
APT
system package management
```

The agent configuration must be protected accordingly.

---

# 15. Agent Configuration Protection

The configuration file:

```text
/etc/default/lums-agent
```

contains the client token.

It should therefore not be world-readable.

A restrictive configuration is:

```text
root:root
0600
```

Check:

```bash
sudo ls -l /etc/default/lums-agent
```

If necessary:

```bash
sudo chown root:root /etc/default/lums-agent
```

```bash
sudo chmod 600 /etc/default/lums-agent
```

---

# 16. Update Execution

LUMS does not directly install packages on the server.

The update workflow is:

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
APT
     │
     ▼
Package installation
     │
     ▼
Result
     │
     ▼
LUMS
```

The client remains responsible for executing the actual package operation.

The agent uses:

```bash
apt-get install --only-upgrade -y PACKAGE
```

for approved package updates.

---

# 17. Automatic Reboots

LUMS does not automatically reboot clients after package updates.

The agent checks:

```text
/var/run/reboot-required
```

A required reboot is therefore reported rather than silently performed.

This is important for controlled infrastructure because automatic reboots can interrupt services unexpectedly.

---

# 18. APT and Package Security

LUMS relies on the operating system's package-management infrastructure.

The agent does not replace:

* APT
* dpkg
* package signatures
* repository trust
* operating-system security mechanisms

LUMS controls **which update job should be executed**.

APT remains responsible for the actual package installation process.

---

# 19. Database Security

LUMS uses SQLite:

```text
/var/lib/lums/lums.db
```

The database contains operational information such as:

```text
clients
client authentication data
inventory
available updates
installed packages
update jobs
job results
audit information
```

Database access must therefore be restricted to the appropriate service account and administrators.

---

## 19.1 Database Backups

Before structural changes:

```bash
sudo cp \
    /var/lib/lums/lums.db \
    /var/lib/lums/lums.db.backup
```

For troubleshooting:

```bash
sudo cp \
    /var/lib/lums/lums.db \
    /var/lib/lums/lums.db.before-troubleshooting
```

A backup should exist before:

* schema migrations
* manual database corrections
* recovery operations
* destructive troubleshooting

---

## 19.2 Database Integrity

Check:

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"PRAGMA integrity_check;"
```

Expected:

```text
ok
```

---

# 20. File System Protection

Important runtime locations include:

```text
/var/lib/lums/
/etc/lums.env
/etc/nginx/ssl/
/etc/default/lums-agent
```

These should not be writable by arbitrary users.

The application data is normally owned by:

```text
lums:lums
```

while sensitive system configuration remains protected by root.

Do not recursively change ownership of system directories without understanding the consequences.

---

# 21. Git Repository Security

The Git repository contains source code.

It must not contain production secrets.

Never commit:

```text
.env files
server secrets
client tokens
TLS private keys
production databases
passwords
API credentials
session secrets
```

Before committing:

```bash
git status
```

Review changes:

```bash
git diff
```

Check whitespace:

```bash
git diff --check
```

Before pushing security-sensitive changes, inspect the actual diff.

---

# 22. Secrets Outside Git

The separation should look like this:

```text
Git Repository
│
├── application source
├── agent source
├── documentation
└── configuration templates
          │
          X
          │
          └── NO production secrets


System
│
├── /etc/lums.env
├── /etc/default/lums-agent
├── /etc/nginx/ssl/
└── /var/lib/lums/lums.db
```

The Git repository contains the **code**.

The system contains the **runtime secrets and state**.

---

# 23. Deployment Security

The deployment process should never overwrite runtime secrets or database state.

The source tree is:

```text
/opt/lums-public
```

The deployed server application is:

```text
/opt/lums-api
```

Server deployment:

```bash
sudo rsync -a \
    --delete \
    --exclude='.git/' \
    /opt/lums-public/server/ \
    /opt/lums-api/
```

The deployment directory must remain separate from:

```text
/var/lib/lums/
/etc/
/etc/nginx/ssl/
```

> [!CAUTION]
> Never use a broad `rsync --delete` operation against `/etc`, `/var/lib/lums` or the complete server filesystem.

---

# 24. Secure Deployment Procedure

Before deployment:

```text
Git status
   ↓
Git synchronization
   ↓
Syntax check
   ↓
Diff validation
   ↓
Deployment
   ↓
Service restart
   ↓
Health check
```

Recommended checks:

```bash
git status
```

```bash
git fetch origin
```

```bash
git rev-list --left-right --count HEAD...origin/main
```

```bash
python3 -m py_compile \
    server/app.py \
    server/init_db.py \
    agent/agent.py
```

```bash
git diff --check
```

After deployment:

```bash
sudo systemctl status lums.service
```

Then:

```bash
curl -k https://192.168.2.229/api/health
```

---

# 25. Logging

Security-relevant events should be investigated through the appropriate logs.

Server:

```bash
sudo journalctl -u lums.service
```

Nginx:

```bash
sudo journalctl -u nginx
```

Agent:

```bash
sudo journalctl -u lums-agent.service
```

Timer:

```bash
sudo journalctl -u lums-agent.timer
```

When sharing logs externally, inspect them for:

```text
tokens
Authorization headers
passwords
session information
internal infrastructure details
```

---

# 26. Logging Principle

Logs should help answer:

```text
What happened?
When did it happen?
Which component was involved?
What operation failed?
```

Logs should **not** become a source of plaintext credentials.

Never deliberately log:

```text
client tokens
server secrets
passwords
private keys
Authorization headers
```

---

# 27. Security Headers

The LUMS application uses HTTP security headers as part of the web security layer.

These should be verified after changes to the Flask/Nginx stack.

Example:

```bash
curl -k -I https://192.168.2.229/
```

Review the response headers for the expected security configuration.

> [!NOTE]
> Header configuration is part of the application/web layer and should be tested after changes to Nginx or Flask security middleware.

---

# 28. Authentication vs Authorization

A useful troubleshooting and security model is:

```text
                    ┌───────────────┐
Request ───────────►│ Authentication│
                    └───────┬───────┘
                            │
                       Who are you?
                            │
                            ▼
                    ┌───────────────┐
                    │ Authorization │
                    └───────┬───────┘
                            │
                     What may you do?
                            │
                            ▼
                         Resource
```

Typical failures:

```text
401 Unauthorized
    ↓
Authentication problem
```

```text
403 Forbidden
    ↓
Authorization problem
```

This distinction is useful when investigating agent/API problems.

---

# 29. Security Maintenance

When modifying LUMS:

1. Understand the current implementation.
2. Make the smallest required change.
3. Test the affected layer.
4. Check for regressions.
5. Review the Git diff.
6. Update the documentation.
7. Commit the change.
8. Verify the deployed state.

Avoid large, unrelated changes during security troubleshooting.

---

# 30. Security Changes Require Testing

Examples of security-sensitive changes include:

```text
authentication
authorization
TLS
session handling
security headers
database schema
client tokens
Nginx configuration
systemd permissions
file ownership
```

After such changes, perform at least:

```text
syntax check
service check
API health check
authentication test
agent test
```

Where appropriate, also verify:

```text
authorization
TLS verification
database integrity
Git diff
```

---

# 31. Incident Handling

If a client token is suspected to be compromised:

```text
1. Identify the affected client
        ↓
2. Revoke the token
        ↓
3. Generate a replacement token
        ↓
4. Update the client configuration
        ↓
5. Test authentication
        ↓
6. Review relevant logs
```

Do not continue using a known-compromised token.

---

## 31.1 Compromised Server Secret

If the server secret is suspected to be compromised:

```text
1. Stop and assess the affected secret
2. Rotate the secret according to the application design
3. Restart affected services
4. Verify authentication and sessions
5. Review relevant logs
6. Document the incident
```

The exact rotation procedure depends on which secret was compromised.

---

# 32. Database Exposure

If:

```text
/var/lib/lums/lums.db
```

is accidentally exposed or copied outside the trusted environment:

1. Treat the database as sensitive.
2. Determine who or what accessed it.
3. Review client authentication records.
4. Assess whether token-related data was exposed.
5. Rotate affected credentials where necessary.
6. Review logs.
7. Document the incident.

Do not assume that a database copy is harmless simply because plaintext client tokens are not stored.

---

# 33. Private Key Exposure

If:

```text
/etc/nginx/ssl/lums.key
```

is exposed:

> **Treat the TLS private key as compromised.**

The certificate/key pair should be replaced and the new certificate deployed.

Do not continue treating the exposed private key as trustworthy.

---

# 34. Security Testing Principles

Security testing should verify the actual security boundaries.

Examples:

```text
Can Flask be reached externally?
        ↓
Should be NO

Can an unauthenticated client access protected API endpoints?
        ↓
Should be NO

Can Client A access Client B resources?
        ↓
Should be NO

Can a revoked client authenticate?
        ↓
Should be NO

Can an invalid TLS certificate be silently accepted?
        ↓
Should be NO in normal operation

Are production secrets present in Git?
        ↓
Should be NO
```

---

# 35. Security Checklist

## Repository

```text
[ ] No passwords committed
[ ] No client tokens committed
[ ] No server secrets committed
[ ] No TLS private keys committed
[ ] No production database committed
[ ] Git diff reviewed
[ ] Git working tree understood
```

## Server

```text
[ ] Flask listens only on 127.0.0.1
[ ] Nginx provides the external HTTPS endpoint
[ ] Port 5000 is not externally exposed
[ ] TLS certificate contains the correct SAN
[ ] TLS private key is protected
[ ] /etc/lums.env is protected
[ ] LUMS service runs with the intended service account
[ ] Database permissions are restricted
```

## Client

```text
[ ] Client token is protected
[ ] Agent configuration is not world-readable
[ ] TLS verification is enabled
[ ] Agent authenticates using Bearer token
[ ] Revoked clients cannot authenticate
[ ] Disabled clients cannot authenticate
[ ] Agent does not automatically reboot systems
```

## Database

```text
[ ] Database is stored outside Git
[ ] Backups exist before migrations
[ ] SQLite integrity check passes
[ ] Authentication data is protected
[ ] Database permissions are restricted
```

---

# 36. Security Rules at a Glance

```text
DO
────────────────────────────────────────
✓ Use HTTPS
✓ Validate TLS certificates
✓ Protect client tokens
✓ Store secrets outside Git
✓ Restrict Flask to localhost
✓ Protect the SQLite database
✓ Back up before migrations
✓ Review Git diffs
✓ Test authentication
✓ Test authorization
✓ Rotate compromised credentials
✓ Document security changes


DO NOT
────────────────────────────────────────
✗ Commit secrets
✗ Commit private keys
✗ Publish client tokens
✗ Expose Flask port 5000
✗ Disable TLS verification permanently
✗ Disable authentication for convenience
✗ Use plaintext client tokens in the database
✗ Modify production DB without a backup
✗ Force-push security-sensitive changes
✗ Automatically reboot managed systems
✗ Publish production database contents
```

---

# 37. Responsible Security Reporting

If a security issue is discovered, provide enough information to reproduce the problem without exposing sensitive information.

Include where possible:

```text
LUMS version / commit
affected component
affected endpoint
observed behavior
expected behavior
reproduction steps
relevant sanitized logs
```

Never include:

```text
client tokens
server secrets
passwords
private keys
production database dumps
session credentials
```

Use placeholders such as:

```text
SERVER_IP
CLIENT_TOKEN
JOB_ID
PACKAGE
```

---

# 38. Security Documentation Principle

Security documentation should describe the actual implementation.

If the implementation changes, update this document.

Examples:

```text
authentication changes
       ↓
update SECURITY.md

TLS changes
       ↓
update SECURITY.md

new API authorization rules
       ↓
update SECURITY.md

new secret locations
       ↓
update SECURITY.md
```

Documentation that describes an old security model can itself become a security problem.

---

# 39. Final Security Principle

LUMS security is not one feature.

It is the combination of:

```text
                ┌─────────────┐
                │    TLS      │
                └──────┬──────┘
                       │
                ┌──────▼──────┐
                │   Network   │
                └──────┬──────┘
                       │
                ┌──────▼──────┐
                │   AuthN     │
                └──────┬──────┘
                       │
                ┌──────▼──────┐
                │   AuthZ     │
                └──────┬──────┘
                       │
                ┌──────▼──────┐
                │ Application │
                └──────┬──────┘
                       │
                ┌──────▼──────┐
                │  Database   │
                └──────┬──────┘
                       │
                ┌──────▼──────┐
                │ OS / APT    │
                └─────────────┘
```

No individual layer should be treated as the entire security model.

> **LUMS — Linux Update Management without the noise.**
>
> **Secure the management plane. Keep execution controlled.**
