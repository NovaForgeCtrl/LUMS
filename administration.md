#
LUMS Administration Guide

    Linux Update Management Server

    Centralized update management, client inventory, reporting and controlled package deployment for Linux systems.

#
1. Purpose

This guide covers the daily administration of LUMS:

    Docker and Nginx administration
    Client and agent management
    Reporting and execution watchers
    Idle-aware update jobs
    Database maintenance and backups
    TLS and authentication
    Git-based deployment
    Troubleshooting and recovery
    Security administration

LUMS centralizes management while update execution remains on the individual Linux client.
#
2. Architecture

Web Browser
    |
    | HTTPS :443
    v
Nginx
    |
    | HTTP localhost
    v
127.0.0.1:5050
    |
    v
Docker container: lums
    |
    | Flask :5000
    v
Docker volume: lums-data
    |
    v
/var/lib/lums/lums.db
         

Client-side operation:

lums-agent.timer
    |
    v
lums-agent.service
    |
    v
agent.py
    |
    +--> inventory/reporting
    +--> client state
    +--> update information

lums-execution-watcher.timer
    |
    v
lums-execution-watcher.service
    |
    v
watcher.py
    |
    +--> idle detection
    +--> pending-job lookup
    +--> atomic claim
    +--> package execution
    +--> result reporting
         

The Flask application is bound to 127.0.0.1:5050 and is exposed externally through Nginx.
#
3. Runtime Configuration

Component Value

Repository /opt/lums-public Docker container lums Docker image lums:latest Docker volume lums-data Flask port 5000 Host binding 127.0.0.1:5050 HTTPS 443 HTTP 80 Server environment /etc/lums/docker/lums.env Database /var/lib/lums/lums.db TLS certificate /etc/nginx/ssl/lums/lums.crt TLS private key /etc/nginx/ssl/lums/lums.key

Use the following placeholders in generic examples:

SERVER_IP
CLIENT_IP
CLIENT_TOKEN
         

Never publish real credentials, private keys or production secrets.
#
4. Client Paths

Component Path

Agent source /opt/lums-public/agent/agent.py Watcher source /opt/lums-public/agent/watcher.py Installed agent /opt/lums-agent/agent.py Installed watcher /opt/lums-agent/watcher.py Agent configuration /etc/default/lums-agent CA certificate /opt/lums-agent/lums-ca.crt Agent service lums-agent.service Agent timer lums-agent.timer Watcher service lums-execution-watcher.service Watcher timer lums-execution-watcher.timer
#
5. Docker Administration
#
Check the container

sudo docker ps --filter name=^/lums$
         

#
Check all containers

sudo docker ps -a
         

#
Check the state

sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
         

Expected:

running
         

#
Check restart policy

sudo docker inspect \
    --format '{{.HostConfig.RestartPolicy.Name}}' \
    lums
         

Expected:

unless-stopped
         

#
Start, stop and restart

sudo docker start lums
sudo docker stop lums
sudo docker restart lums
         

Stopping or restarting the container interrupts the web interface and API. The database remains persistent as long as lums-data is preserved.
#
6. Docker Logs

sudo docker logs --tail 100 lums
         

sudo docker logs --since 10m lums
         

sudo docker logs -f lums
         

Search for common errors:

sudo docker logs lums 2>&1 \
    | grep -iE 'error|exception|traceback|failed'
         

Do not publish logs containing tokens, session data or other sensitive information.
#
7. Nginx Administration

Validate configuration:

sudo nginx -t
         

Reload configuration:

sudo systemctl reload nginx
         

Check service status:

sudo systemctl status nginx --no-pager
         

View logs:

sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
         

Follow logs:

sudo journalctl -u nginx -f
         

Restart only when necessary:

sudo systemctl restart nginx
         

#
8. Network and Health Checks

Check listening ports:

sudo ss -lntp
         

Check Docker mapping:

sudo docker port lums
         

Expected:

5000/tcp -> 127.0.0.1:5050
         

Test the local backend:

curl -I http://127.0.0.1:5050/
         

Test the external HTTPS path:

curl -k -I https://SERVER_IP/
         

Test the API:

curl -k https://SERVER_IP/api/health
         

The -k option disables certificate verification and is intended only for diagnostics. Normal agent operation must use certificate verification.
#
9. TLS Administration

Certificate:

/etc/nginx/ssl/lums/lums.crt
         

Private key:

/etc/nginx/ssl/lums/lums.key
         

Inspect the certificate:

sudo openssl x509 \
    -in /etc/nginx/ssl/lums/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
         

Inspect the Subject Alternative Name:

sudo openssl x509 \
    -in /etc/nginx/ssl/lums/lums.crt \
    -noout \
    -ext subjectAltName
         

Protect the private key:

sudo chown root:root \
    /etc/nginx/ssl/lums/lums.key

sudo chmod 600 \
    /etc/nginx/ssl/lums/lums.key
         

The address used by the agent must be represented in the certificate SAN.

Never permanently disable TLS verification.
#
10. Server Environment

The environment file is:

/etc/lums/docker/lums.env
         

Protect it:

sudo chown root:root \
    /etc/lums/docker/lums.env

sudo chmod 600 \
    /etc/lums/docker/lums.env
         

Check whether a required variable exists without displaying its value:

sudo grep -q '^LUMS_SECRET_KEY=' \
    /etc/lums/docker/lums.env \
    && echo "Secret vorhanden" \
    || echo "Secret fehlt"
         

Do not commit the environment file to Git.
#
11. Agent Configuration

Example:

LUMS_BASE=https://SERVER_IP
LUMS_TOKEN=CLIENT_TOKEN
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
         

The actual configuration is stored in:

/etc/default/lums-agent
         

Protect it:

sudo chown root:root \
    /etc/default/lums-agent

sudo chmod 600 \
    /etc/default/lums-agent
         

Display safe values:

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
12. Agent Service and Timer

Check the service:

sudo systemctl status \
    lums-agent.service \
    --no-pager
         

Run one reporting cycle:

sudo systemctl start lums-agent.service
         

View logs:

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
         

Enable the timer:

sudo systemctl enable --now lums-agent.timer
         

Check scheduled execution:

systemctl list-timers --all | grep lums-agent
         

The agent service is a oneshot service. After a successful run, inactive (dead) can be normal; the timer is responsible for starting it again.
#
13. Execution Watcher

The execution watcher is separate from reporting.

Current versions:

Agent:
    1.6.0

Watcher:
    1.2.1
         

The watcher performs the following sequence:

1. Check for a running job
2. Recover a running job if present
3. Request pending jobs
4. Determine local idle state
5. Verify idle support
6. Verify the configured idle threshold
7. Atomically claim a pending job
8. Execute only the claimed job
9. Submit the result
         

Enable the watcher timer:

sudo systemctl daemon-reload

sudo systemctl enable --now \
    lums-execution-watcher.timer
         

Check the timer:

sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager
         

Run one watcher cycle manually:

sudo systemctl start \
    lums-execution-watcher.service
         

View logs:

sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
         

The current laboratory timer runs approximately every 30 seconds.
#
14. Idle-Aware Execution

The current implementation uses:

w -h
         

for server, terminal and SSH-oriented idle detection.

The configured idle threshold is:

300 seconds
5 minutes
         

The watcher must not execute a job when:

    idle detection is unsupported
    the idle threshold has not been reached
    the job cannot be claimed atomically
    the client is not properly authenticated

The current implementation is not a universal desktop-idle provider. Desktop environments may require an additional provider in the future.
#
15. Idle Data

The agent reports fields similar to:

{
  "idle": false,
  "idle_seconds": 5,
  "threshold_seconds": 300,
  "idle_source": "w",
  "idle_supported": true
}
         

If idle detection is unavailable:

{
  "idle": false,
  "idle_seconds": 0,
  "threshold_seconds": 300,
  "idle_source": "w",
  "idle_supported": false
}
         

Unsupported idle detection must result in safe non-execution.
#
16. Update Job Lifecycle

The job lifecycle is:

pending
   |
   v
idle check
   |
   v
atomic claim
   |
   v
running
   |
   +--> success
   +--> partial
   +--> failed
         

A pending job is not executed simply because it exists.

The watcher first checks idle state and then performs an atomic claim.

Only the successfully claimed job may be executed.
#
17. Atomic Claiming

The claim endpoint is:

POST /api/clients/<client_id>/update-jobs/<job_id>/claim
         

The server uses an atomic database operation to prevent multiple agents or watcher cycles from claiming the same pending job.

If the job is no longer pending, the claim must fail safely and the job must not be executed by that request.
#
18. Running-Job Recovery

The watcher checks for an existing running job before requesting a new pending job.

This supports recovery after:

    service interruption
    watcher restart
    SSH disconnection
    system restart
    interrupted execution workflow

A recovered running job is resumed without claiming it a second time.
#
19. Update Results

The result endpoint is:

POST /api/update-jobs/<job_id>/result
         

The result can contain:

    overall status
    package results
    successful package count
    failed package count
    timeout information
    reboot requirement

Supported overall statuses:

success
partial
failed
         

The server validates that:

    the job belongs to the authenticated client
    the job is currently running
    the result status is valid

#
20. Simulation Mode

Simulation mode is intended for safe end-to-end testing.

It:

    does not execute real APT updates
    does not modify installed packages
    simulates package results
    tests job claiming
    tests watcher behavior
    tests result reporting
    tests UI state changes

The setting is:

LUMS_SIMULATE_UPDATES
         

Simulation mode must be explicitly disabled after testing.

Verify the service definition:

sudo systemctl cat \
    lums-execution-watcher.service
         

Remove the simulation environment line from the service if it is present:

Environment=LUMS_SIMULATE_UPDATES=1
         

Then reload systemd:

sudo systemctl daemon-reload
         

A successful simulation does not prove that real APT/dpkg collisions are fully prevented.
#
21. Package Manager Safety

The current project does not yet provide complete coordination with arbitrary manual apt or dpkg commands.

Important limitations:

    A custom LUMS lock does not automatically control manual APT commands.
    An external package-manager process may already be active.
    Removing lock files is unsafe.
    Full coordination requires additional detection, waiting and operational policy.

Future hardening may include:

    LUMS execution lock
    active process detection
    dpkg/APT lock checks
    wait-and-retry behavior
    execution timeouts
    deferred job states
    maintenance windows

Never delete foreign APT or dpkg lock files.
#
22. APT Administration

The client performs package operations locally.

Check APT:

sudo apt update
         

List updates:

apt list --upgradable
         

Inspect a package:

apt-cache policy <package>
         

Inspect installation state:

dpkg -l <package>
         

The current update operation is designed for package updates rather than a complete distribution upgrade.

If APT or dpkg is already broken, resolve the client-side package-manager problem first.
#
23. Reboot Handling

LUMS does not automatically reboot clients.

Check whether a reboot is required:

test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot required"
         

A reboot remains an administrative decision.
#
24. Database Administration

The database is:

/var/lib/lums/lums.db
         

It is stored in:

lums-data
         

Check integrity:

sudo docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
result = db.execute("PRAGMA integrity_check;").fetchone()[0]
print(result)
db.close()
'
         

Expected:

ok
         

Do not remove the Docker volume as a first troubleshooting action.
#
25. Database Backup

Create the backup directory:

sudo install -d -m 700 /var/backups/lums
         

Create a SQLite-aware backup:

sudo docker exec lums \
    python3 -c '
import sqlite3

source = sqlite3.connect("/var/lib/lums/lums.db")
backup = sqlite3.connect("/tmp/lums-backup.db")

source.backup(backup)

backup.close()
source.close()
'
         

Copy it to the host:

sudo docker cp \
    lums:/tmp/lums-backup.db \
    "/var/backups/lums/lums-$(date +%F-%H%M%S).db"
         

Remove the temporary file:

sudo docker exec \
    lums \
    rm -f /tmp/lums-backup.db
         

Protect backups:

sudo find /var/backups/lums \
    -type f \
    -name "*.db" \
    -exec chmod 600 {} \;
         

Do not store backups inside the Git repository.
#
26. Restore Procedure

Before restoring a database:

    Stop normal administrative changes.
    Create a backup of the current database.
    Verify the restore source.
    Stop the container if required.
    Restore the database.
    Check ownership and permissions.
    Start the container.
    Run PRAGMA integrity_check.
    Test administrator authentication.
    Test client authentication.
    Test reporting and update jobs.

Never overwrite the only available database copy.
#
27. Git Administration

Repository:

/opt/lums-public
         

Check status:

cd /opt/lums-public
git status
         

Check latest commit:

git log -1 --oneline --decorate
         

Check remote:

git remote -v
         

Fetch:

git fetch origin
         

Update a clean working tree:

git pull --ff-only origin main
         

Check synchronization:

git rev-list --left-right --count HEAD...origin/main
         

Expected after synchronization:

0       0
         

#
28. Git Validation

Before deployment:

cd /opt/lums-public
git status
git diff --check
         

Validate Python syntax:

python3 -m py_compile \
    server/app.py \
    server/init_db.py \
    agent/agent.py \
    agent/watcher.py
         

Do not deploy if validation fails.
#
29. Git Identity

The repository identity is:

Name:
    NovaForgeCtrl

Email:
    232026481+NovaForgeCtrl@users.noreply.github.com
         

Check:

git config user.name
git config user.email
         

#
30. Docker Deployment

Create a database backup before deployment.

Build the image:

cd /opt/lums-public

sudo docker build \
    -t lums:latest \
    .
         

Stop the old container:

sudo docker stop lums
         

Remove only the container:

sudo docker rm lums
         

Do not remove lums-data.

Start the new container:

sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --env-file /etc/lums/docker/lums.env \
    -p 127.0.0.1:5050:5000 \
    -v lums-data:/var/lib/lums \
    lums:latest
         

Check:

sudo docker ps --filter name=^/lums$
sudo docker logs --tail 100 lums
         

#
31. Updating the Installed Agent and Watcher

After changing agent source files, install both files:

cd /opt/lums-public

sudo install \
    -o root \
    -g root \
    -m 0750 \
    agent/agent.py \
    /opt/lums-agent/agent.py

sudo install \
    -o root \
    -g root \
    -m 0750 \
    agent/watcher.py \
    /opt/lums-agent/watcher.py
         

Reload systemd if unit files changed:

sudo systemctl daemon-reload
         

Restart or trigger the relevant timer only after validation.
#
32. Post-Deployment Validation

Check the container:

sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
         

Test the local backend:

curl -I http://127.0.0.1:5050/
         

Test HTTPS:

curl -k -I https://SERVER_IP/
         

Test the API:

curl -k https://SERVER_IP/api/health
         

Check Nginx:

sudo nginx -t
         

Test the reporting agent:

sudo systemctl start lums-agent.service
         

Test the watcher:

sudo systemctl start \
    lums-execution-watcher.service
         

Review both logs.
#
33. Troubleshooting Method

    Do not reinstall everything immediately. Find the layer where the problem occurs.

Troubleshoot in this order:

Network
  |
  v
Nginx / TLS
  |
  v
Docker / Flask
  |
  v
SQLite
  |
  v
Agent
  |
  v
Watcher
  |
  v
APT / dpkg
         

Basic sequence:

ping SERVER_IP
sudo ss -lntp
sudo nginx -t
sudo docker ps -a
sudo docker logs --tail 100 lums
curl -I http://127.0.0.1:5050/
curl -k -I https://SERVER_IP/
curl -k https://SERVER_IP/api/health
sudo systemctl status lums-agent.timer --no-pager
sudo systemctl status lums-execution-watcher.timer --no-pager
         

#
34. Common Problems
#
Container is not running

sudo docker ps -a --filter name=^/lums$
sudo docker logs --tail 200 lums
sudo docker inspect lums
         

#
Port 5050 is unavailable

sudo ss -lntp | grep ':5050'
sudo docker port lums
curl -I http://127.0.0.1:5050/
         

#
Nginx failure

sudo nginx -t
sudo systemctl status nginx --no-pager
sudo journalctl -u nginx -n 100 --no-pager
         

#
Agent authentication failure

Check safely:

sudo awk -F= '
/^LUMS_BASE=/ { print $1 "=" $2 }
/^LUMS_CA_FILE=/ { print $1 "=" $2 }
/^LUMS_TOKEN=/ { print "LUMS_TOKEN=<redacted>" }
' /etc/default/lums-agent
         

Then inspect:

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

sudo docker logs --tail 200 lums
         

#
Client appears offline

sudo systemctl start lums-agent.service
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
         

Possible causes:

    timer not running
    network failure
    TLS failure
    invalid token
    server unavailable
    agent exception
    database issue

#
Update job is not executed

Check:

    client is enabled
    token is valid
    pending job exists
    idle detection is supported
    idle threshold is reached
    watcher timer is active
    APT repositories work

Inspect:

sudo systemctl start \
    lums-execution-watcher.service

sudo journalctl \
    -u lums-execution-watcher.service \
    -n 100 \
    --no-pager
         

#
35. Security Administration

Never commit:

/etc/lums/docker/lums.env
/etc/default/lums-agent
TLS private keys
client tokens
production databases
database backups
private certificates
         

Recommended permissions:

Resource Permission

Environment file 0600 Agent configuration 0600 TLS private key 0600 Public certificate 0644 Database backups 0600

Review permissions:

sudo ls -l /etc/lums/docker/lums.env
sudo ls -l /etc/default/lums-agent
sudo ls -l /etc/nginx/ssl/lums/
         

Search the repository for sensitive file types:

find . -type f \
    \( \
        -name "*.env" \
        -o -name "*.key" \
        -o -name "*.pem" \
        -o -name "*.db" \
    \)
         

#
36. Backup Strategy

A recoverable installation requires more than Git.

Back up:

    SQLite database
    Docker environment file
    Nginx configuration
    TLS certificate
    TLS private key
    Agent configuration
    CA certificate
    Git repository

Git contains source code and documentation, but not runtime secrets or database state.

Recommended sequence:

Backup
  |
  v
Change
  |
  v
Validate
  |
  v
Test
  |
  v
Document
         

#
37. Recovery Strategy

    Restore the operating system.
    Install Docker and Nginx.
    Restore the repository.
    Restore environment configuration.
    Restore TLS configuration.
    Restore the database or Docker volume.
    Build the Docker image.
    Start the container.
    Configure Nginx.
    Test HTTPS.
    Test administrator authentication.
    Test client authentication.
    Test reporting.
    Test the execution watcher.
    Test update-job handling.

Recovery should be tested against a known backup.
#
38. Operational Principles

    Identify the failing layer before reinstalling.
    Keep persistent data outside the Docker image.
    Keep secrets outside Git.
    Keep Flask behind Nginx.
    Bind the application to localhost only.
    Use HTTPS for client/server communication.
    Keep TLS verification enabled.
    Separate authentication and authorization.
    Store client token hashes rather than plaintext tokens.
    Keep update execution on the client.
    Do not automatically reboot clients.
    Back up before database changes.
    Validate configuration before restarting services.
    Use git pull --ff-only for routine synchronization.
    Preserve lums-data during deployments.
    Test security-sensitive changes.
    Document configuration changes.
    Do not expose secrets in logs or screenshots.
    Keep simulation mode disabled outside testing.
    Treat APT/dpkg coordination as an explicit operational concern.

#
39. Final Checklist

    Git working tree is clean
    Repository is synchronized
    git diff --check passes
    Python syntax checks pass
    Docker image builds successfully
    Container lums is running
    Volume lums-data exists
    Port 5000 is not directly exposed
    Application is bound to 127.0.0.1:5050
    Nginx configuration passes
    HTTPS works
    TLS SAN is correct
    TLS private key permissions are restricted
    Environment file permissions are restricted
    API health check works
    Administrator authentication works
    Client authentication works
    Client authorization works
    Agent CA certificate is available
    Agent token configuration is valid
    lums-agent.timer is active
    lums-execution-watcher.timer is active
    Agent reporting works
    Idle detection works
    Update jobs can be created
    Jobs are claimed atomically
    Running jobs can be recovered
    Results can be submitted
    Database integrity check returns ok
    Database backup exists
    Simulation mode is disabled outside testing
    No secrets are present in Git
    Documentation matches the current deployment

    LUMS — Linux Update Management without the noise.

    Centralize the management. Keep execution controlled.

    Know what changed. Know where it happened.

    LUMS Administration Guide
    1. Purpose
    2. Architecture
    3. Runtime Configuration
    4. Client Paths
    5. Docker Administration
    Check the container
    Check all containers
    Check the state
    Check restart policy
    Start, stop and restart
    6. Docker Logs
    7. Nginx Administration
    8. Network and Health Checks
    9. TLS Administration
    10. Server Environment
    11. Agent Configuration
    12. Agent Service and Timer
    13. Execution Watcher
    14. Idle-Aware Execution
    15. Idle Data
    16. Update Job Lifecycle
    17. Atomic Claiming
    18. Running-Job Recovery
    19. Update Results
    20. Simulation Mode
    21. Package Manager Safety
    22. APT Administration
    23. Reboot Handling
    24. Database Administration
    25. Database Backup
    26. Restore Procedure
    27. Git Administration
    28. Git Validation
    29. Git Identity
    30. Docker Deployment
    31. Updating the Installed Agent and Watcher
    32. Post-Deployment Validation
    33. Troubleshooting Method
    34. Common Problems
    Container is not running
    Port 5050 is unavailable
    Nginx failure
    Agent authentication failure
    Client appears offline
    Update job is not executed
    35. Security Administration
    36. Backup Strategy
    37. Recovery Strategy
    38. Operational Principles
    39. Final Checklist
