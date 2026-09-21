#
LUMS Security

    Linux Update Management Server

    Security principles, operational requirements, hardening status, and responsible handling of sensitive information in LUMS.

Version: 2.5 Project: LUMS Slogan: Linux Update Management without the noise.
#
1. Security Philosophy

LUMS follows a simple principle:

    Centralized management does not mean centralized trust.

LUMS manages Linux clients, receives inventory information, and distributes update jobs.

The actual package installation takes place on the managed Linux client.

                    ┌─────────────────────┐
                    │      LUMS Server     │
                    │                     │
                    │ Nginx               │
                    │ Docker              │
                    │ Gunicorn            │
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
                    │ execution watcher   │
                    │ APT / dpkg          │
                    └─────────────────────┘
         

LUMS security depends on multiple layers:

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
Gunicorn
   ↓
Docker
   ↓
Database
   ↓
Operating System
   ↓
APT / dpkg
         

A weakness in one layer must never be used as a reason to disable another security layer.
#
2. Security Scope

This document covers:

    Docker deployment security
    Gunicorn application serving
    Database initialization
    Server authentication
    Client authentication
    Authorization
    TLS certificates
    Secret management
    SQLite database protection
    Nginx configuration
    systemd agent services
    Execution watcher security
    Update execution
    Logging
    Backup protection
    Incident handling
    Security testing
    Security maintenance
    Current security limitations
    Remaining hardening work

This document does not replace the official security documentation of:

    Ubuntu
    Debian
    Docker
    Python
    Flask
    Gunicorn
    Nginx
    SQLite
    APT
    dpkg
    systemd

#
3. Current Architecture

The current LUMS deployment uses:

    Flask inside a Docker container
    Gunicorn as the WSGI application server
    SQLite in a persistent Docker volume
    Nginx as an HTTPS reverse proxy
    A Linux reporting agent
    A separate execution watcher
    Bearer-token authentication
    systemd timers for scheduled execution
    A root-managed mounted Flask secret

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
   │ Docker port mapping
   ▼
Docker container :5000
   │
   ▼
Gunicorn
   │
   ├── Worker 1
   └── Worker 2
   │
   ▼
Flask application
   │
   ├── Authentication
   ├── Authorization
   ├── Inventory
   └── Update Jobs
   │
   ▼
SQLite database
         

The Docker application is bound to localhost:

127.0.0.1:5050 → container port 5000
         

The application is not directly exposed as a network service on ports 5000 or 5050.

The Flask secret is no longer supplied through the normal container environment.

Instead, production uses:

Host:
    /etc/lums/secrets/lums_secret

        │ read-only bind mount

Container:
    /run/secrets/lums_secret
         

The application reads the secret through:

LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
         

#
4. Current Deployment Security Status

The following controls have been implemented and tested:
Security control 	Status
HTTPS through Nginx 	Implemented
HTTP → HTTPS redirect 	Tested
TLS 1.2 / TLS 1.3 	Configured
Security headers 	Implemented and tested
Localhost Docker binding 	Implemented
Flask development server removed 	Completed
Gunicorn 23.0.0 	Implemented
Two Gunicorn workers 	Implemented
Database initialization before Gunicorn 	Implemented
Database initialization once per container start 	Tested
Bearer client authentication 	Implemented
Client/job authorization 	Implemented
Atomic job claiming 	Implemented
Interrupted-job recovery 	Implemented and tested
SQLite-aware backups 	Implemented
Backup permissions 	Restricted
Backup integrity verification 	Tested
Persistent Docker volume 	Implemented
Container non-privileged mode 	Confirmed
Container non-root user 	Completed and verified
Read-only container filesystem 	Completed and verified
Capability reduction 	Completed and verified
Secret file isolation 	Completed and verified
Secret read-only mount 	Completed and verified
Production restart after secret isolation 	Completed and verified
Client token lifecycle/rotation 	Completed and verified
Complete APT/dpkg collision prevention 	Not yet implemented
Full backup restore test 	Not yet completed
Automated security regression tests 	Not yet completed
Final security review 	Not yet completed

The security status is intentionally documented as incomplete where controls have not yet been implemented.
#
5. Current Installation
Component 	Configuration
Repository 	/opt/lums-public
Docker container 	lums
Docker image 	lums:latest
Docker volume 	lums-data
Internal application port 	5000
Host binding 	127.0.0.1:5050
HTTP port 	80
HTTPS port 	443
Database 	/var/lib/lums/lums.db
Environment file 	/etc/lums/docker/lums.env
Flask secret file 	/etc/lums/secrets/lums_secret
Container secret path 	/run/secrets/lums_secret
Server certificate 	/etc/lums/tls/lums.crt
Server private key 	/etc/lums/tls/lums.key
Agent directory 	/opt/lums-agent
Agent configuration 	/etc/default/lums-agent
Agent CA certificate 	/opt/lums-agent/lums-ca.crt
Reporting agent 	/opt/lums-agent/agent.py
Execution watcher 	/opt/lums-agent/watcher.py

Actual secrets, tokens, passwords, private keys, internal credentials, and sensitive infrastructure information must never be published.
#
6. Sensitive Information

The following information must be treated as sensitive:

LUMS server secret
Client tokens
Authentication hashes
Administrator passwords
TLS private keys
Session information
Database contents
Inventory information
Internal infrastructure information
Backup files
Application configuration
         

Important sensitive files include:

/etc/lums/docker/lums.env
/etc/lums/secrets/lums_secret
/etc/lums/tls/lums.key
/etc/default/lums-agent
         

The Docker volume contains the operational database:

lums-data:/var/lib/lums
         

Caution

Never commit sensitive files or their contents to Git.

Sensitive information must also be removed from:

    Screenshots
    Terminal output
    GitHub issues
    Pull requests
    Public documentation
    Chat messages
    Support requests
    Log exports

#
7. Server Secret Management
#
7.1 Secret File

Production LUMS no longer supplies the Flask secret through the normal Docker environment.

The production secret is stored on the host in:

/etc/lums/secrets/lums_secret
         

The file is managed by root and is readable by the LUMS container user through its group permissions.

Expected production permissions:

Owner: root
Group: 10001
Mode: 640
         

The containing directory is additionally restricted:

/etc/lums/secrets
root:root
0700
         

The secret file is mounted read-only into the container:

/etc/lums/secrets/lums_secret
        ↓
/run/secrets/lums_secret
         

The application receives only the path:

LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
         

The actual secret value must never be displayed in documentation.
#
7.2 Application Secret Loading

The Flask application loads the secret using the configured secret-file path.

Conceptually:

LUMS_SECRET_KEY_FILE
        │
        ▼
/run/secrets/lums_secret
        │
        ▼
Flask application
        │
        ▼
app.secret_key
         

The application supports an environment-variable fallback for controlled compatibility and development scenarios.

Production, however, uses the mounted secret file.

The production container does not contain:

LUMS_SECRET_KEY=<secret>
         

in its normal environment.
#
7.3 Secret Isolation Architecture

The production deployment uses:

Host
│
├── /etc/lums/secrets/
│      └── lums_secret
│
└── Docker
       │
       └── read-only bind mount
              │
              ▼
       /run/secrets/lums_secret
              │
              ▼
       Flask
         

This reduces exposure through:

docker inspect
         

because the secret value is no longer stored as a normal Docker environment variable.

Docker administrators can still access the host secret file if they have sufficient host or Docker privileges.

Therefore:

    Secret isolation reduces environment exposure; it does not eliminate the need to protect Docker and host administration privileges.

#
7.4 Production Secret Mount

The production container is started using:

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
         

The important properties are:

Secret value:
    not supplied as LUMS_SECRET_KEY

Secret path:
    supplied through LUMS_SECRET_KEY_FILE

Secret storage:
    host-managed file

Container access:
    read-only

Database:
    persistent lums-data volume

Root filesystem:
    read-only

Capabilities:
    none
         

#
7.5 Secret Isolation Verification

Production verification confirmed:

LUMS_SECRET_KEY:
    absent from container environment

LUMS_SECRET_KEY_FILE:
    /run/secrets/lums_secret

Secret file:
    readable by the application

Secret mount:
    read-only

ReadonlyRootfs:
    true

CapDrop:
    ["ALL"]

Privileged:
    false

User:
    lums
         

The application successfully:

    Started Gunicorn.
    Started both workers.
    Initialized the database.
    Served /login.
    Served authenticated client API requests.
    Survived container restart.
    Preserved the persistent database.

Secret isolation is therefore considered:

    Implemented and verified in production.

#
7.6 Secret Rotation — Completed and Verified

Secret isolation and secret rotation are intentionally separate security controls.

Secret isolation moved the Flask secret from the normal Docker environment into the root-managed file:

/etc/lums/secrets/lums_secret
         

The previous Flask secret had appeared in diagnostic output and was therefore treated as exposed.

A controlled rotation was first tested in an isolated environment. The test confirmed that changing the Flask secret invalidates the old session and that a new login using the new secret works.

Production rotation was then completed.

The production procedure was:

Create database backup
        ↓
Protect the existing secret temporarily
        ↓
Generate new secret
        ↓
Replace /etc/lums/secrets/lums_secret
        ↓
Restart LUMS
        ↓
Verify Gunicorn startup
        ↓
Verify HTTPS
        ↓
Verify security headers
        ↓
Verify database integrity
        ↓
Verify old session invalidation
        ↓
Verify new authentication
        ↓
Verify client communication
         

Production verification confirmed:

    The container started successfully.
    Gunicorn workers started successfully.
    The secret remained outside LUMS_SECRET_KEY.
    The mounted secret file remained readable by the application.
    HTTPS remained operational.
    Security headers remained present.
    SQLite integrity remained valid.
    The previous browser session was invalidated.
    Authentication with the new secret worked.
    Client and job data remained intact.

The temporary old-secret backup was removed after successful verification.

The actual secret value must never be documented.

    Secret rotation is completed and verified in production.

#
8. Client Authentication

LUMS clients authenticate using Bearer tokens.

The request must contain:

Authorization: Bearer <CLIENT_TOKEN>
         

The server validates the presented token before processing protected requests.

The current implementation stores a SHA-256 hexadecimal digest of the client token rather than the plaintext token.

Client Token
     │
     ▼
SHA-256
     │
     ▼
Hexadecimal Digest
     │
     ▼
Database
         

The token hashing format must remain consistent between:

    Token creation
    Token storage
    Token verification
    Token rotation
    Client registration

#
Security note

SHA-256 is a deterministic digest and is not a password-hashing algorithm.

The current token lifecycle has now been extended with explicit rotation and revocation behavior.

Current controls include:

    Cryptographically random token generation.
    SHA-256 hexadecimal digest storage instead of plaintext token storage.
    Bearer-token authentication.
    Enabled/revoked client checks.
    Explicit token rotation.
    Immediate invalidation of the previous token after rotation.
    Audit logging for successful token rotation.
    No plaintext token in the audit event.
    One-time presentation of the newly generated token through the administrative interface.

Token rotation is implemented through:

POST /api/clients/<client_id>/token/rotate
         

The endpoint requires:

    An authenticated administrator session.
    Valid CSRF protection.
    An existing client ID.

A successful rotation returns the newly generated token once so that the administrator can update the corresponding agent configuration.

The previous token is no longer accepted immediately after rotation.

The rotation workflow was tested with:

Token A
   ↓
Rotate
   ↓
Token B
   ├── Token A → 401
   └── Token B → 200
         

Future improvements may still include token expiration, token identifiers, and a token-storage design appropriate to a larger threat model. These are separate enhancements and are not required for the currently verified rotation workflow.
#
9. Client Token Protection

Client configuration is stored in:

/etc/default/lums-agent
         

Example:

LUMS_BASE="https://<LUMS_SERVER_IP>"
LUMS_TOKEN="<CLIENT_TOKEN>"
LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt"
         

The real token must never appear in:

    Git commits
    README files
    Documentation
    Screenshots
    Public issue reports
    Log files
    Chat messages

Use placeholders:

<LUMS_SERVER_IP>
<CLIENT_IP>
<CLIENT_TOKEN>
<CLIENT_ID>
<JOB_ID>
<ADMIN_PASSWORD>
         

Protect the configuration:

sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
         

#
9.1 Client Token Lifecycle — Completed and Verified

The client token lifecycle now supports controlled administrative rotation.

The lifecycle is:

Client registration
        ↓
Generate random token
        ↓
Store SHA-256 digest
        ↓
Agent uses plaintext token locally
        ↓
Bearer authentication
        ↓
Administrative rotation
        ↓
Generate replacement token
        ↓
Invalidate previous token
        ↓
Audit successful rotation
        ↓
Display replacement token once
        ↓
Update agent configuration
        ↓
Verify client reporting
         

The rotation endpoint is:

POST /api/clients/<client_id>/token/rotate
         

The endpoint is protected by both administrator authentication and CSRF validation.

The server performs the following checks before changing the token:

    Client exists.
    Administrative session is authenticated.
    CSRF validation succeeds.
    A new cryptographically random token is generated.
    Only the token digest is stored in the database.
    token_created_at is updated.
    token_revoked_at is cleared for the replacement token.
    A successful audit event is written.
    The plaintext token is returned only in the successful rotation response.

The previous token is invalid immediately after the database update.
#
Rotation testing

The lifecycle was tested in an isolated environment before production deployment.

Verified:

Admin session missing       → 401
CSRF missing                → 400
Unknown client              → 404
Successful rotation        → 200
Old token after rotation    → 401
New token after rotation    → 200
Audit event                 → present
Token value in audit        → absent
         

The frontend was also tested:

    Rotation confirmation is displayed.
    The new token is shown only after successful rotation.
    A copy-to-clipboard control is available.
    The token is not written to the audit log.
    Existing client deletion functionality remains available.

Production client communication was subsequently verified with the replacement token.

    Client token lifecycle / rotation is completed and verified.

#
10. Authorization

Authentication and authorization are separate concepts.

Authentication
    ↓
Who is this client?

Authorization
    ↓
What is this client allowed to access?
         

A valid client token must not automatically grant access to every client or job.

The server validates:

    Authenticated client identity
    Requested client ID
    Job ownership
    Job assignment
    Result submission permissions
    Administrative permissions where applicable

Example:

Client A
   │
   └── Requests Client B data
            │
            ▼
          DENIED
         

Authorization must be enforced server-side.

Frontend restrictions and hidden form fields are not security controls.
#
11. Protected API Endpoints

Protected client operations include:

POST /api/report

GET /api/client/me

GET /api/clients/<client_id>/update-jobs

GET /api/clients/<client_id>/update-jobs/pending

GET /api/clients/<client_id>/update-jobs/running

POST /api/clients/<client_id>/update-jobs/<job_id>/claim

GET /api/update-jobs/<job_id>

POST /api/update-jobs/<job_id>/result

POST /api/update-jobs/<job_id>/abandon
         

The server must verify that the authenticated client is authorized to access the requested resource.

A client must not be able to:

    Read another client’s inventory
    Retrieve another client’s jobs
    Claim another client’s job
    Submit results for another client
    Abandon another client’s job
    Modify unauthorized job states

#
12. Client Identity

Client-specific operations should use authenticated identity wherever possible.

The endpoint:

GET /api/client/me
         

provides authenticated client context.

The server must not rely solely on client-supplied identifiers.

Do not trust:

    Client IDs from request bodies
    URL parameters
    Hidden form fields
    Frontend restrictions
    User-controlled metadata

The server must validate:

Authenticated client
        +
Requested resource
        =
Authorized access
         

#
13. TLS

LUMS uses HTTPS for communication between clients and the server.

Server certificate:

/etc/lums/tls/lums.crt
         

Server private key:

/etc/lums/tls/lums.key
         

Recommended permissions:

sudo chown root:root /etc/lums/tls/lums.key
sudo chmod 600 /etc/lums/tls/lums.key

sudo chown root:root /etc/lums/tls/lums.crt
sudo chmod 644 /etc/lums/tls/lums.crt
         

The private key must never be:

    Committed to Git
    Copied into the repository
    Printed in terminal output
    Included in public documentation
    Shared through public issue reports

#
14. TLS Configuration

The current Nginx configuration permits:

TLS 1.2
TLS 1.3
         

Older protocol versions must remain disabled.

Check:

sudo nginx -T | grep -n "ssl_protocols"
         

TLS must be tested after certificate or Nginx changes.

Example:

curl -k -I https://127.0.0.1/
         

The -k option is only appropriate for controlled diagnostics when certificate verification is intentionally bypassed.

Normal client operation must verify the configured CA.
#
15. Certificate Subject Alternative Name

The certificate must contain the hostname or IP address used by clients.

Inspect:

sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
         

Inspect the SAN:

sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -ext subjectAltName
         

The client connection address must match a valid SAN entry.

A certificate containing only a Common Name is not sufficient for modern hostname verification.
#
16. Nginx Security

Nginx is the public-facing reverse proxy.

Responsibilities:

    TLS termination
    HTTP-to-HTTPS redirection
    Forwarding requests to Docker
    Preventing direct external access to Flask
    Providing the external HTTPS endpoint

Validate:

sudo nginx -t
         

Reload only after a successful configuration test:

sudo systemctl reload nginx
         

Check:

sudo systemctl status nginx --no-pager
         

Review logs:

sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
         

The reverse proxy target remains local:

http://127.0.0.1:5050
         

#
17. Network Exposure

The intended architecture is:

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
         

Check Docker mappings:

sudo docker port lums
         

Check listening ports:

sudo ss -lntp
         

Expected application binding:

127.0.0.1:5050
         

The following must not be directly exposed to the network:

5000
5050
         

#
18. HTTP and HTTPS

Normal communication must use:

https://<LUMS_SERVER_IP>
         

Test HTTP:

curl -I http://<LUMS_SERVER_IP>/
         

HTTP should redirect to HTTPS.

Test HTTPS:

curl \
    --cacert /opt/lums-agent/lums-ca.crt \
    -I \
    https://<LUMS_SERVER_IP>/
         

Sensitive information must never be transmitted through unencrypted HTTP.
#
19. Security Headers

The application currently provides the following security headers:

X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
Content-Security-Policy: ...
         

The current CSP restricts scripts, styles, connections, objects, frames, and form actions to the intended application origins.

Check response headers:

curl -k -I https://127.0.0.1/
         

The current deployment has been tested successfully and returns the expected security headers.

HSTS may be added only after HTTPS deployment has been fully validated for the intended environment.
#
20. Gunicorn Application Server

The Flask development server is no longer used by the Docker deployment.

LUMS currently uses:

Gunicorn 23.0.0
         

The container starts Gunicorn with:

2 workers
2 threads per worker
120 second timeout
stdout access logging
stdout error logging
         

The application is loaded using:

app:app
         

The effective architecture is:

Nginx
   ↓
127.0.0.1:5050
   ↓
Docker :5000
   ↓
Gunicorn
   ├── Worker 1
   └── Worker 2
   ↓
Flask
         

The Flask development server is not used for the current deployment.
#
21. Database Initialization

Database initialization and application serving are intentionally separated.

The Docker startup sequence is:

Container start
      │
      ▼
init_db.py
      │
      │ successful
      ▼
Gunicorn
      │
      ├── Worker 1
      └── Worker 2
         

The database initialization script is:

/app/server/init_db.py
         

The container entrypoint is:

/app/docker-entrypoint.sh
         

The entrypoint executes:

python3 /app/server/init_db.py
         

before starting Gunicorn.

This prevents database initialization from occurring once per Gunicorn worker.

The previous architecture initialized the database during:

import init_db
         

inside app.py.

That import has been removed.
#
Verification

The production logs must show:

=== LUMS database initialization ===
LUMS-Datenbank aktualisiert: /var/lib/lums/lums.db
=== Starting Gunicorn ===
         

The database initialization message must appear once per container startup.
#
22. Entrypoint Failure Behavior

The Docker entrypoint uses:

set -eu
         

and:

exec gunicorn ...
         

Therefore:

    Database initialization failure prevents Gunicorn startup.
    Gunicorn becomes the container’s main process.
    Docker receives Gunicorn’s process signals directly.
    The application does not continue after a failed initialization step.

This is preferable to starting the application when the required database initialization has failed.
#
23. Docker Security

The LUMS container is now hardened with four important controls:

Dedicated non-root user
        +
Drop ALL Linux capabilities
        +
Read-only root filesystem
        +
Read-only mounted application secret
         

The current production container uses:

USER lums
         

with:

uid=10001
gid=10001
         

The container is additionally started with:

--cap-drop=ALL
         

and:

--read-only
         

The required writable temporary filesystem is provided explicitly:

--tmpfs /tmp:rw,nosuid,nodev,noexec
         

Persistent application data remains writable through:

-v lums-data:/var/lib/lums
         

The production secret is mounted read-only:

-v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro
         

The resulting architecture is:

Container
│
├── Root filesystem
│      └── READ-ONLY
│
├── /tmp
│      └── tmpfs / writable
│
├── /var/lib/lums
│      └── persistent Docker volume / writable
│
├── /run/secrets/lums_secret
│      └── read-only secret file
│
├── Linux capabilities
│      └── NONE
│
└── Application user
       └── lums / UID 10001
         

#
24. Container User — Verified

The production container does not run as root.

Verification:

sudo docker exec lums id
         

Expected:

uid=10001(lums) gid=10001(lums) groups=10001(lums)
         

The container image defines:

USER lums
         

The application data directory is owned by the application user:

lums:lums
         

The change was tested using an isolated container before production deployment.

The following were verified:

    SQLite read access
    SQLite write access
    Database integrity
    Gunicorn startup
    Login endpoint
    Container restart
    Persistent volume access

The non-root container is therefore considered implemented and validated.
#
25. Container Capabilities — Verified

The production container starts with:

--cap-drop=ALL
         

Verification:

sudo docker inspect lums \
    --format '
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
CapAdd={{json .HostConfig.CapAdd}}
CapDrop={{json .HostConfig.CapDrop}}
Privileged={{.HostConfig.Privileged}}
'
         

Expected:

ReadonlyRootfs=true
CapAdd=null
CapDrop=["ALL"]
Privileged=false
         

Effective capability verification:

sudo docker exec lums \
    sh -c 'grep "^Cap" /proc/1/status'
         

Current production result:

CapInh: 0000000000000000
CapPrm: 0000000000000000
CapEff: 0000000000000000
CapBnd: 0000000000000000
CapAmb: 0000000000000000
         

The capability reduction was tested separately before production deployment.

SQLite functionality and application startup remained operational with all capabilities dropped.

No additional Linux capability is currently required by LUMS.
#
26. Read-Only Root Filesystem — Verified

The production container uses:

--read-only
         

This makes the container root filesystem immutable during normal operation.

Writable locations are explicitly limited to:

/tmp
/var/lib/lums
         

The temporary directory is provided as:

--tmpfs /tmp:rw,nosuid,nodev,noexec
         

The persistent database volume remains:

lums-data:/var/lib/lums
         

The secret file is mounted separately as read-only:

/run/secrets/lums_secret
         

Verification:

sudo docker inspect lums \
    --format '{{.HostConfig.ReadonlyRootfs}}'
         

Expected:

true
         

Filesystem behavior was tested:

/tmp                    writable
/app                    not writable
/var/lib/lums           writable
/run/secrets/lums_secret readable
         

The application continued to provide:

    Gunicorn
    Flask
    SQLite
    Login
    HTTPS access
    Database persistence
    Container restart
    Secret-file access

The read-only root filesystem was tested independently before production deployment and was subsequently verified again after production restarts.

The control is therefore considered implemented and validated.
#
27. Production Docker Security Baseline

The current production container should be started using:

sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --tmpfs /tmp:rw,nosuid,nodev,noexec \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
         

Expected security properties:

Privileged:       false
User:             lums / UID 10001
Capabilities:     none
Root filesystem:  read-only
/tmp:             writable tmpfs
Database volume:  writable persistent volume
Secret mount:     read-only
Network binding:  localhost only
         

These properties have been verified in production.
#
28. Production Hardening Verification

The final production restart verification confirmed:

ReadonlyRootfs=true
CapAdd=null
CapDrop=["ALL"]
Privileged=false
         

Container identity:

uid=10001(lums)
gid=10001(lums)
         

Effective capabilities:

CapInh: 0000000000000000
CapPrm: 0000000000000000
CapEff: 0000000000000000
CapBnd: 0000000000000000
CapAmb: 0000000000000000
         

Secret configuration:

LUMS_SECRET_KEY:
    absent

LUMS_SECRET_KEY_FILE:
    /run/secrets/lums_secret

Secret mount:
    read-only
         

Database:

SQLite integrity: ok
users: present
clients: present
audit_log: present
schema_migrations: present
update_jobs: present
         

Production database counts remained intact during the hardening deployment.

HTTPS remained operational:

HTTPS status: 302
Location: /login
         

Security headers remained present after restart.

Client API verification remained operational:

Client authentication: working
Client report: HTTP 200
Pending jobs: expected response
Running jobs: expected response
         

The container was restarted after secret isolation and successfully returned to normal operation.

This confirms that:

Non-root
+
Drop ALL capabilities
+
Read-only root filesystem
+
Secret-file isolation
         

do not currently interfere with normal LUMS operation.
#
29. Agent Security

The reporting agent and execution watcher perform different tasks.
#
Reporting agent

Responsible for:

    Collecting system information
    Detecting installed packages
    Detecting available updates
    Reporting client information
    Communicating with the LUMS server

#
Execution watcher

Responsible for:

    Checking pending jobs
    Checking idle status
    Claiming jobs
    Executing configured update operations
    Recovering interrupted jobs
    Submitting execution results

The separation of responsibilities makes the execution workflow easier to review and troubleshoot.
#
30. Agent Configuration Protection

The agent configuration is:

/etc/default/lums-agent
         

Protect:

sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
         

Check:

sudo stat -c '%U:%G %a %n' \
    /etc/default/lums-agent
         

Expected:

root:root 600 /etc/default/lums-agent
         

Display configuration without exposing the token:

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
         

#
31. Agent Files

Expected files:

/opt/lums-agent/agent.py
/opt/lums-agent/watcher.py
/opt/lums-agent/lums-ca.crt
         

Recommended ownership:

sudo chown root:root \
    /opt/lums-agent/agent.py \
    /opt/lums-agent/watcher.py \
    /opt/lums-agent/lums-ca.crt
         

Recommended permissions:

sudo chmod 750 \
    /opt/lums-agent/agent.py \
    /opt/lums-agent/watcher.py

sudo chmod 644 \
    /opt/lums-agent/lums-ca.crt
         

The token-containing configuration remains separate from the application source.
#
32. systemd Reporting Service

The reporting service is:

lums-agent.service
         

The reporting timer is:

lums-agent.timer
         

The service uses:

Type=oneshot
         

Execution flow:

Timer
  ↓
Service
  ↓
Agent
  ↓
Report submission
  ↓
Exit
         

A successful oneshot service may show:

inactive (dead)
status 0/SUCCESS
         

This is normal after successful completion.

Enable:

sudo systemctl enable --now lums-agent.timer
         

Check:

sudo systemctl status lums-agent.timer --no-pager
         

View timers:

systemctl list-timers --all | grep lums
         

View logs:

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
         

The installed systemd timer configuration is authoritative for the reporting schedule.
#
33. Execution Watcher Security

The execution watcher runs independently from the reporting agent.

The watcher must:

    Load the protected configuration.
    Contact the LUMS server using HTTPS.
    Authenticate using the client token.
    Check whether a pending job exists.
    Check idle status.
    Verify the configured idle threshold.
    Attempt an atomic job claim.
    Execute only a successfully claimed job.
    Submit a validated result.
    Recover interrupted jobs safely.

The watcher must not execute a job merely because it appears in a pending list.
#
34. Idle-Aware Execution

The current watcher uses:

w -h
         

for idle detection.

This is primarily suitable for:

    Server environments
    Terminal sessions
    Console sessions
    SSH-oriented environments

It is not a universal desktop idle detection mechanism.

The watcher uses metadata such as:

idle
idle_seconds
idle_threshold_seconds
idle_source
idle_supported
         

The current configured threshold is:

300 seconds
         

The watcher should only execute jobs when:

    Idle detection is supported.
    The idle threshold has been reached.
    A pending job exists.
    The job is assigned to the authenticated client.
    The job is successfully claimed.
    The package manager is available.

#
35. Atomic Job Claiming

Job claiming is performed atomically.

Expected workflow:

1. Find pending job
2. Verify client identity
3. Verify job authorization
4. Check idle state
5. Attempt atomic claim
6. Confirm claim success
7. Execute the job
8. Submit the result
         

If another watcher claims the job first, the current watcher must not execute it.

This prevents duplicate execution caused by:

    Repeated timer runs
    Concurrent requests
    Network retries
    Multiple watcher instances

#
36. Job Result Validation

The server validates job result submissions.

Possible result states include:

success
partial
failed
         

The server must validate:

    Job existence
    Client authorization
    Current job state
    Result format
    Result ownership
    Allowed state transitions

A client must not be able to submit an arbitrary successful result for a job it did not execute.
#
37. Interrupted Job Recovery

A job may remain in running if:

    The client loses power
    The watcher is terminated
    The system reboots
    The network connection fails
    The package manager process crashes
    Result submission fails

LUMS provides an explicit recovery mechanism:

POST /api/update-jobs/<job_id>/abandon
         

The endpoint:

    Requires client authentication.
    Verifies job ownership.
    Only operates on a running job.
    Changes the job state to abandoned.
    Records a recovery reason.
    Records the recovery in update history.
    Preserves package-count and execution metadata.
    Uses a conditional state update to avoid races.

The watcher detects an abandoned/stale running job and attempts recovery before claiming a new job.

If recovery fails, the watcher must not continue by claiming another job.
#
38. Recovery Testing

Recovery has been tested using a controlled synthetic job.

The test verified:

running
   ↓
abandoned
         

and confirmed:

    finished_at populated
    Recovery reason recorded
    Update history entry created
    Package count preserved
    Successful count preserved
    Failed count preserved
    No unintended reboot flag
    Synthetic test data removed afterward

A subsequent real update job was also successfully executed after the recovery test.

Recovery is therefore considered implemented and validated for the current workflow.
#
39. APT and dpkg Safety

Complete APT and dpkg collision prevention is not fully implemented.

The LUMS execution lock does not automatically force arbitrary user-issued APT or dpkg commands to honor it.

A potential collision remains possible:

LUMS watcher starts an operation
        +
User manually runs apt or dpkg
        =
Potential package manager collision
         

LUMS must not claim that all package manager collisions are prevented.

Future improvements may include:

    Detecting active APT or dpkg processes
    Deferring jobs while package management is busy
    Stronger execution coordination
    Better lock handling
    Job timeout handling
    Additional audit events
    Integration tests

#
40. Simulation Mode

Simulation mode is intended for testing the watcher workflow without changing installed packages.

Enable temporarily:

sudo systemctl edit --runtime lums-execution-watcher.service
         

Add:

[Service]
Environment=LUMS_SIMULATE_UPDATES=1
         

Run:

sudo systemctl start lums-execution-watcher.service
         

Review:

sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
         

Remove:

sudo systemctl revert --runtime lums-execution-watcher.service
sudo systemctl daemon-reload
         

Verify:

sudo systemctl cat lums-execution-watcher.service
         

Simulation mode must not remain enabled in normal operation.
#
41. Database Security

LUMS uses SQLite inside:

lums-data
         

Database path:

/var/lib/lums/lums.db
         

The database may contain:

    Client records
    Authentication hashes
    Inventory information
    Installed packages
    Available updates
    Update jobs
    Job results
    Audit information

Database access must be restricted to:

    The LUMS application
    Authorized administrators
    Controlled maintenance procedures

The database must never be committed to Git.
#
42. Database Integrity

Check:

sudo docker exec lums \
    python3 -c '
import sqlite3

connection = sqlite3.connect("/var/lib/lums/lums.db")
result = connection.execute(
    "PRAGMA integrity_check;"
).fetchone()[0]

print(result)
connection.close()
'
         

Expected:

ok
         

Do not modify the database manually without:

    A verified backup.
    A clear reason.
    An understanding of the schema.
    A controlled maintenance procedure.
    Validation after the change.

#
43. SQLite-Aware Backup

Create:

sudo mkdir -p /var/backups/lums
sudo chmod 700 /var/backups/lums
         

Because the current Docker image has an application entrypoint, a backup-only container must explicitly bypass that entrypoint.

For production backups, the helper container runs as root so that the protected backup directory can remain:

root:root
0700
         

Example:

sudo docker run --rm \
    --user 0:0 \
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
         

Protect:

sudo chmod 600 \
    /var/backups/lums/lums.db.backup
         

Check:

sudo ls -lh \
    /var/backups/lums/lums.db.backup
         

Recommended permissions:

Backup directory: 0700
Backup file:      0600
Owner:            root:root
         

#
44. Backup Verification

A backup must be verified.

Example:

sudo docker run --rm \
    --user 0:0 \
    --entrypoint python3 \
    -v /var/backups/lums:/backup:ro \
    lums:latest \
    -c '
import sqlite3

connection = sqlite3.connect(
    "/backup/lums.db.backup-readonly"
)

cursor = connection.cursor()

cursor.execute("PRAGMA integrity_check")
print("Backup SQLite integrity:", cursor.fetchone()[0])

connection.close()
'
         

Expected:

Backup SQLite integrity: ok
         

#
Current production verification

Production backups were successfully created and verified during the container hardening work.

Verified properties included:

Owner:       root:root
Permissions: 0600
SQLite:      integrity_check = ok
         

A backup integrity check confirms that the SQLite backup is structurally valid.

It does not by itself constitute a full restore test.

Backups should therefore also be tested in an isolated restore environment.
#
45. Database Restore

A database restore is a controlled maintenance operation.

Before restoring:

    Confirm the correct backup.
    Stop the LUMS container.
    Create a safety copy of the current database.
    Restore the backup.
    Check ownership and permissions.
    Start the container.
    Run a database integrity check.
    Test authentication.
    Test client reporting.
    Verify update jobs and audit data.

Never overwrite the only available database copy.

Do not restore a database while the application is actively writing to it.

A successful backup verification must not be confused with a successful restore test.
#
46. Git Repository Security

Repository:

/opt/lums-public
         

Before committing:

cd /opt/lums-public

git status
git diff
git diff --check
         

Check tracked files:

git ls-files
         

Never commit:

.env files
Environment files
Private keys
Client tokens
Passwords
Database files
Backup files
Session data
Internal credentials
Personal information
Secret files
         

Use placeholders:

<LUMS_SERVER_IP>
<CLIENT_IP>
<CLIENT_TOKEN>
<ADMIN_PASSWORD>
<JOB_ID>
         

#
47. Secure Git Workflow

Before pushing:

cd /opt/lums-public

git status
git diff --check
git diff
         

Review history:

git log --oneline --decorate -5
         

Review staged files:

git diff --cached --name-status
         

Configured repository identity:

Name:  NovaForgeCtrl
Email: 232026481+NovaForgeCtrl@users.noreply.github.com
         

Do not push unreviewed security-sensitive changes.

If a secret is accidentally committed:

    Revoke or rotate it immediately.
    Remove it from the current repository state.
    Review Git history.
    Determine whether it was publicly accessible.
    Document the incident.
    Do not assume deleting the latest file removes the secret from history.

#
48. Logging Security

LUMS server logs:

sudo docker logs --tail 100 lums
         

Follow:

sudo docker logs -f lums
         

Agent logs:

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
         

Watcher logs:

sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
         

Nginx logs:

sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
         

Logs must not contain:

    Plaintext tokens
    Passwords
    Server secrets
    Private keys
    Session secrets
    Complete authorization headers
    Unnecessary sensitive inventory information

Redact sensitive information before sharing logs.
#
49. Filesystem Permissions

Review:

sudo stat -c '%U:%G %a %n' \
    /etc/lums/docker/lums.env \
    /etc/lums/secrets/lums_secret \
    /etc/lums/tls/lums.key \
    /etc/default/lums-agent
         

Recommended:

Environment file:       0600
Secret file:            0640
Secret directory:      0700
Private keys:           0600
Public certificates:    0644
Agent configuration:    0600
Backup directory:       0700
Backup database files:  0600
         

The secret file is intentionally:

root:10001 0640
         

so the non-root LUMS container user can read it without making the secret world-readable.

Review permissions after:

    Installation
    Updates
    Manual changes
    File transfers
    Restores
    Deployment operations

#
50. Firewall Security

Only required services should be exposed.

Typical allowed ports:

22/tcp    SSH
80/tcp    HTTP redirect
443/tcp   HTTPS
         

Check:

sudo ufw status verbose
         

Application ports must not be publicly exposed:

5000
5050
         

Firewall rules must be reviewed after network or deployment changes.
#
51. Deployment Security

Before deployment:

cd /opt/lums-public

git status --short
git fetch origin
git log --oneline --decorate -3
         

Update:

git pull --ff-only origin main
         

Review:

git diff --check
         

Build:

sudo docker build -t lums:latest .
         

Before recreation:

sudo docker ps
sudo docker volume inspect lums-data
         

Create a verified SQLite backup before replacing a production container.

The current production deployment uses:

sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --tmpfs /tmp:rw,nosuid,nodev,noexec \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
         

Stop and remove only the container:

sudo docker stop lums
sudo docker rm lums
         

Do not remove:

lums-data
         

Verify:

sudo docker ps
sudo docker logs --tail 100 lums
sudo nginx -t
         

Test HTTPS:

curl -k -I https://127.0.0.1/
         

A successful Docker build does not prove that the complete deployment is working.
#
52. Deployment Verification

After container recreation verify:

1. Container running
2. Correct image
3. Correct localhost binding
4. Persistent volume still mounted
5. Database initialization runs once
6. Gunicorn starts
7. Two workers start
8. HTTPS returns expected response
9. Security headers remain present
10. Login remains accessible
11. Client reporting remains functional
12. Update jobs remain functional
13. Container runs as non-root
14. Root filesystem is read-only
15. All Linux capabilities are dropped
16. /tmp is available through tmpfs
17. Secret path is configured
18. Secret is not present as LUMS_SECRET_KEY
19. Secret mount is read-only
20. Container restart succeeds
         

Check:

sudo docker ps \
    --filter "name=^lums$" \
    --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"
         

Check volume:

sudo docker inspect lums \
    --format '{{range .Mounts}}{{.Name}} -> {{.Destination}} ({{.RW}}){{"\n"}}{{end}}'
         

Expected database volume:

lums-data -> /var/lib/lums (true)
         

Check the secret mount:

sudo docker inspect lums \
    --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} RW={{.RW}}{{"\n"}}{{end}}'
         

Expected:

/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
         

#
53. Incident Handling
#
53.1 Compromised Client Token

If a client token is compromised:

    Identify the affected client.
    Revoke or replace the token.
    Review recent client activity.
    Check server and application logs.
    Issue a new token.
    Update client configuration.
    Verify authentication.
    Document the incident.

Never continue using a known-compromised token.
#
53.2 Compromised Server Secret

If the server secret is compromised:

    Restrict access to the server.
    Review application logs.
    Generate a new secret.
    Replace the protected secret file.
    Restart the Docker container.
    Verify authentication and sessions.
    Review related credentials.
    Document the incident.

Changing the Flask secret may invalidate existing sessions.

The production secret should be rotated separately from normal secret-isolation deployment when possible so that session impact is understood and tested.
#
53.3 Compromised TLS Private Key

If the TLS private key is compromised:

    Replace the certificate and private key.
    Update trusted certificates on clients.
    Reload Nginx.
    Verify certificate validation.
    Review possible unauthorized access.
    Document the incident.

#
53.4 Exposed Database or Backup

If a database or backup becomes exposed:

    Restrict access immediately.
    Determine which information was exposed.
    Review authentication-related data.
    Rotate affected credentials or tokens.
    Replace compromised backups if necessary.
    Review access logs.
    Document the incident.

#
53.5 Previously Exposed Flask Secret

The Flask secret was previously exposed through diagnostic output.

The value is intentionally not reproduced here.

The incident was handled by:

Identify exposure
        ↓
Move secret out of normal Docker environment
        ↓
Test secret rotation in isolation
        ↓
Generate replacement secret
        ↓
Replace /etc/lums/secrets/lums_secret
        ↓
Restart production LUMS
        ↓
Verify old session invalidation
        ↓
Verify new authentication
        ↓
Remove temporary old-secret backup
         

The replacement secret is now active in production.

    The previously exposed Flask secret has been rotated and is no longer the active production secret.

#
54. Security Testing Checklist
#
Server

    Docker container is running
    Docker volume is mounted
    Application binds only to localhost
    Port 5000 is not externally exposed
    Port 5050 is not externally exposed
    Nginx configuration passes validation
    HTTPS is enabled
    HTTP redirects to HTTPS
    TLS certificate contains the correct SAN
    Private key permissions are restricted
    Environment file permissions are restricted
    Firewall rules reviewed as required

#
Application Server

    Flask development server removed
    Gunicorn 23.0.0 deployed
    Gunicorn workers start successfully
    Application import works
    Database initialization runs before Gunicorn
    Database initialization runs once per container start
    Gunicorn receives container signals correctly

#
Authentication

    Administrator authentication works
    Invalid credentials are rejected
    Client token authentication is implemented
    Invalid client tokens are rejected
    Client tokens are not intentionally logged
    Protected endpoints require authentication
    Token rotation lifecycle implemented and verified
    Flask secret rotation completed and verified

#
Authorization

    Client identity is authenticated server-side
    Client/job relationships are validated
    Atomic job claiming is implemented
    Job result ownership is validated
    Recovery ownership is validated
    Full administrative role model implemented

#
Agent

    Agent uses HTTPS
    TLS verification is configured
    CA certificate is available
    Agent configuration is protected
    Reporting timer is configured
    Watcher timer is configured
    Inventory reporting works
    Update job retrieval works
    Atomic job claiming works
    Job result reporting works
    Interrupted-job recovery tested
    Complete APT/dpkg collision prevention

#
Database

    Database integrity can be checked
    SQLite-aware backups are implemented
    Backups are protected
    Backup integrity verification tested
    Restore procedure is documented
    Full restore test completed
    Database files are excluded from Git
    Backup files are excluded from Git

#
Docker

    Container is not privileged
    Application ports are localhost-only
    Persistent volume is used
    Container runs as non-root user
    Root filesystem is read-only
    All Linux capabilities are dropped
    Secret is removed from normal container environment
    Secret is supplied through protected mounted file
    Secret mount is read-only
    Production restart with secret-file architecture verified

#
Git

    Secrets excluded from documentation
    Private keys excluded
    Tokens excluded
    Database files excluded
    Backup files excluded
    Changes reviewed before deployment
    Documentation uses placeholders
    Historical Flask secret exposure identified
    Replacement Flask secret generated and deployed

#
55. Current Security Limitations
#
55.1 Secret Rotation

Secret isolation and production secret rotation are complete and verified.

The previous secret was treated as exposed, replaced with a newly generated value, and the production application was restarted and tested.

Changing the Flask secret invalidates existing sessions. This behavior was explicitly tested before production rotation and confirmed again after production deployment.
#
55.2 Client Token Lifecycle

Client token rotation is implemented and verified.

Current lifecycle controls include:

    Cryptographically random token generation.
    SHA-256 hexadecimal digest storage.
    Bearer authentication.
    Enabled/revoked checks.
    Administrative rotation.
    Immediate invalidation of the previous token.
    CSRF protection for the administrative rotation endpoint.
    Audit logging without the plaintext token.
    One-time presentation of the replacement token.
    Production client communication after rotation.

Token expiration and a more advanced token-storage model remain possible future enhancements, but token rotation itself is no longer a pending hardening task.
#
55.3 Idle Detection

The current idle detection uses:

w -h
         

It is primarily suitable for server, terminal, console, and SSH-oriented environments.

It is not a universal desktop idle detection mechanism.
#
55.4 Package Manager Coordination

Complete collision prevention between LUMS and arbitrary user-issued APT or dpkg commands is not fully implemented.

The LUMS execution lock does not automatically force every external package manager process to honor it.
#
55.5 Administrative Roles

LUMS currently has a single administrator-oriented authentication model.

A full role-based administrative authorization model has not yet been implemented.
#
55.6 SQLite Scaling

SQLite is suitable for the current project scope and laboratory development.

Larger deployments may require a different database architecture depending on:

    Number of clients
    Concurrent requests
    Job volume
    Audit log size
    Backup requirements
    High availability requirements

#
55.7 Self-Signed Certificates

Self-signed certificates require explicit trust configuration on clients.

They can be suitable for controlled laboratory environments but may not be appropriate for every deployment scenario.
#
56. Remaining Security Roadmap

The remaining hardening work should be performed incrementally.
#
Phase 1 — Secret Isolation and Rotation — Complete

The Flask secret is stored outside the normal Docker environment and mounted read-only into the container.

The previously exposed secret was replaced with a newly generated production secret.

Verified:

    Isolated rotation test.
    Old session invalidation.
    New authentication.
    Production restart.
    HTTPS operation.
    Database integrity.
    Client communication.

The secret value itself must never be documented.
#
Phase 2 — Client Token Lifecycle — Complete

Implemented and verified:

    Cryptographically random token generation.
    SHA-256 digest storage.
    Administrative token rotation.
    Immediate invalidation of the previous token.
    CSRF protection.
    Audit event without token disclosure.
    One-time token presentation.
    Agent reconfiguration and production reporting verification.

Possible future enhancements:

    Token expiration.
    Token identifiers.
    More advanced token storage appropriate to a larger deployment threat model.

#
Phase 3 — Update Execution Hardening

Continue improving:

    APT/dpkg collision prevention
    Job timeouts
    Recovery handling
    Execution auditing
    Package-manager state detection
    Integration testing

#
Phase 4 — Backup / Restore Validation

Perform an isolated restore test using a verified production backup.

Test:

Backup
  ↓
Isolated restore environment
  ↓
SQLite integrity
  ↓
Security schema
  ↓
Application startup
  ↓
Authentication
  ↓
Client/job data
         

Only after a successful restore test should the backup/restore control be considered fully validated.
#
Phase 5 — Automated Security Tests

Automate regression tests for:

    Authentication
    Authorization
    Token handling
    Job ownership
    Job claiming
    Job recovery
    Security headers
    Container hardening
    Database integrity
    Secret handling

#
Phase 6 — Final Security Review

After the individual hardening phases are complete:

Inspect
   ↓
Test
   ↓
Verify
   ↓
Production
   ↓
Verify
   ↓
Document
         

The final review should confirm that the documented security state matches the actual deployment.
#
57. Responsible Security Reporting

Security issues should be reported responsibly.

A security report should contain:

    Short description
    Affected component
    Reproduction steps
    Expected behavior
    Actual behavior
    Potential impact
    Suggested mitigation
    Relevant logs with secrets removed

Never include:

    Passwords
    Client tokens
    Private keys
    Server secrets
    Personal information
    Complete production databases
    Unredacted inventory data

Always redact sensitive information before sharing logs or screenshots.
#
58. Security Maintenance

Security reviews should be performed after:

    Application changes
    Authentication changes
    Authorization changes
    Docker changes
    Nginx changes
    Certificate changes
    Database schema changes
    Agent changes
    Watcher changes
    Deployment changes
    Secret changes

Regularly review:

Docker images
Operating system updates
Python dependencies
Flask dependencies
Gunicorn
Nginx configuration
TLS certificates
File permissions
Database backups
Git history
Authentication behavior
Authorization behavior
Job execution behavior
Package manager coordination
Container privileges
Container capabilities
Secret handling
Secret rotation
         

#
59. Current Security Roadmap Status

The current hardening state is:

[x] Non-root container
[x] Drop ALL capabilities
[x] Read-only root filesystem
[x] SQLite backup verification
[x] Interrupted-job recovery
[x] Production restart verification
[x] Secret isolation
[x] Protected mounted secret file
[x] Read-only secret mount
[x] Production restart after secret isolation
[x] Flask secret rotation
[x] Production secret rotation verification
[x] Client token lifecycle
[x] Client token rotation
[x] Client token revocation through rotation
[x] Client token rotation audit event
[x] Frontend token rotation workflow
[x] Production frontend deployment
[x] Production client communication after token rotation

[ ] Update execution hardening
[ ] Full backup / restore test
[ ] Automated security tests
[ ] Final security review
         

The following controls are therefore considered complete for the current implementation:

Container hardening
Secret isolation
Secret rotation
Client authentication
Client token rotation
Interrupted-job recovery
Production frontend deployment
         

The remaining work is intentionally separated into independent hardening phases:

Update execution hardening
        ↓
Full backup / restore test
        ↓
Automated security tests
        ↓
Final security review
         

The established workflow remains:

inspect
   ↓
design
   ↓
test
   ↓
verify
   ↓
production
   ↓
verify
   ↓
document
         

No security-sensitive change should be deployed blindly.
#
60. Final Security Principles

The following principles apply to LUMS:

    Never store secrets in Git.
    Never expose the Flask/Gunicorn application directly to the network.
    Use HTTPS for client communication.
    Keep TLS verification enabled.
    Separate authentication from authorization.
    Validate client identity server-side.
    Protect the Docker environment file.
    Protect client tokens.
    Protect TLS private keys.
    Protect the mounted Flask secret.
    Keep database backups secure.
    Do not remove persistent volumes during troubleshooting.
    Do not automatically reboot clients.
    Review changes before deployment.
    Test security-sensitive changes.
    Document incidents and configuration changes.
    Do not claim that incomplete security controls are fully implemented.
    Keep update execution controlled and auditable.
    Harden the container incrementally and test each change independently.
    Preserve persistent application data during frontend and container deployments.
    Treat secret isolation and secret rotation as separate controls.
    Treat previously exposed secrets as compromised until rotated.
    Rotate client tokens through the authenticated administrative workflow and verify the replacement token before closing the change.
    Keep production secrets outside Git and outside normal container environment variables where practical.
    Treat security hardening as a continuous process rather than a one-time configuration.

#
61. Final Verified Production State

The production deployment was rebuilt from the tested frontend image after a verified SQLite backup.

The final production checks confirmed:

Image:
    lums:latest

Container user:
    lums / UID 10001

ReadonlyRootfs:
    true

Capabilities:
    ALL dropped

Privileged:
    false

Secret environment variable:
    LUMS_SECRET_KEY absent

Secret path:
    /run/secrets/lums_secret

Secret mount:
    read-only

Database integrity:
    ok

HTTPS:
    302 → /login

Unauthenticated client API:
    401 authentication_required

Frontend token rotation control:
    visible in production
         

The production database remained intact:

users:          1
clients:        1
audit_log:      22
update_jobs:    1
update_history: 1
         

The backup used before the production frontend deployment was independently checked with SQLite integrity verification and returned:

integrity = ok
         

The token-rotation workflow was tested separately before production deployment, including old-token invalidation, new-token authentication, CSRF enforcement, audit logging, and frontend presentation/copy behavior.

    Client Token Lifecycle: VERIFIED

    Production Secret Rotation: VERIFIED

    Container Hardening: VERIFIED

#
62. Final Principle

LUMS is designed to centralize Linux update management without removing operational control from the administrator.

The system should remain:

    Transparent
    Auditable
    Controlled
    Secure
    Documented
    Maintainable

The current architecture deliberately separates:

Management Plane
       │
       ├── Nginx
       ├── Gunicorn
       ├── Flask
       ├── Authentication
       ├── Authorization
       └── Database

from

Execution Plane
       │
       ├── lums-agent
       ├── Execution Watcher
       └── APT / dpkg
         

Security improvements are implemented one controlled layer at a time.

The current verified security architecture is:

Internet / LAN
      │
      ▼
   Nginx
   HTTPS
      │
      ▼
127.0.0.1:5050
      │
      ▼
 Docker
 ┌──────────────────────────────┐
 │ non-root                     │
 │ UID 10001                    │
 │ capabilities: NONE           │
 │ root filesystem: READ-ONLY   │
 │                              │
 │ /tmp → tmpfs                 │
 │ /var/lib/lums → lums-data    │
 │ /run/secrets/lums_secret     │
 │          → READ-ONLY         │
 │                              │
 │ Gunicorn → Flask             │
 └──────────────────────────────┘
      │
      ▼
 SQLite
         

The hardening workflow remains:

Inspect
   ↓
Test
   ↓
Verify
   ↓
Production
   ↓
Verify
   ↓
Document
         

    LUMS — Linux Update Management without the noise.

    Secure the management plane. Keep execution controlled.

    One change. One test. One verified result.

    LUMS Security
    1. Security Philosophy
    2. Security Scope
    3. Current Architecture
    4. Current Deployment Security Status
    5. Current Installation
    6. Sensitive Information
    7. Server Secret Management
    7.1 Secret File
    7.2 Application Secret Loading
    7.3 Secret Isolation Architecture
    7.4 Production Secret Mount
    7.5 Secret Isolation Verification
    7.6 Secret Rotation — Completed and Verified
    8. Client Authentication
    Security note
    9. Client Token Protection
    9.1 Client Token Lifecycle — Completed and Verified
    Rotation testing
    10. Authorization
    11. Protected API Endpoints
    12. Client Identity
    13. TLS
    14. TLS Configuration
    15. Certificate Subject Alternative Name
    16. Nginx Security
    17. Network Exposure
    18. HTTP and HTTPS
    19. Security Headers
    20. Gunicorn Application Server
    21. Database Initialization
    Verification
    22. Entrypoint Failure Behavior
    23. Docker Security
    24. Container User — Verified
    25. Container Capabilities — Verified
    26. Read-Only Root Filesystem — Verified
    27. Production Docker Security Baseline
    28. Production Hardening Verification
    29. Agent Security
    Reporting agent
    Execution watcher
    30. Agent Configuration Protection
    31. Agent Files
    32. systemd Reporting Service
    33. Execution Watcher Security
    34. Idle-Aware Execution
    35. Atomic Job Claiming
    36. Job Result Validation
    37. Interrupted Job Recovery
    38. Recovery Testing
    39. APT and dpkg Safety
    40. Simulation Mode
    41. Database Security
    42. Database Integrity
    43. SQLite-Aware Backup
    44. Backup Verification
    Current production verification
    45. Database Restore
    46. Git Repository Security
    47. Secure Git Workflow
    48. Logging Security
    49. Filesystem Permissions
    50. Firewall Security
    51. Deployment Security
    52. Deployment Verification
    53. Incident Handling
    53.1 Compromised Client Token
    53.2 Compromised Server Secret
    53.3 Compromised TLS Private Key
    53.4 Exposed Database or Backup
    53.5 Previously Exposed Flask Secret
    54. Security Testing Checklist
    Server
    Application Server
    Authentication
    Authorization
    Agent
    Database
    Docker
    Git
    55. Current Security Limitations
    55.1 Secret Rotation
    55.2 Client Token Lifecycle
    55.3 Idle Detection
    55.4 Package Manager Coordination
    55.5 Administrative Roles
    55.6 SQLite Scaling
    55.7 Self-Signed Certificates
    56. Remaining Security Roadmap
    Phase 1 — Secret Isolation and Rotation — Complete
    Phase 2 — Client Token Lifecycle — Complete
    Phase 3 — Update Execution Hardening
    Phase 4 — Backup / Restore Validation
    Phase 5 — Automated Security Tests
    Phase 6 — Final Security Review
    57. Responsible Security Reporting
    58. Security Maintenance
    59. Current Security Roadmap Status
    60. Final Security Principles
    61. Final Verified Production State
    62. Final Principle
