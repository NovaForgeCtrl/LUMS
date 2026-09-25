# LUMS Troubleshooting Guide

> **Linux Update Management Server**
>
> Troubleshooting and diagnostic procedures for the LUMS server, agent, update jobs, package managers, Docker deployment, and client communication.

**Version:** 4.0
**Current Agent:** 1.7.0
**Project:** LUMS
**Slogan:** Linux Update Management without the noise.

---

# 1. Purpose

This document provides a structured troubleshooting procedure for LUMS.

The goal is to identify problems systematically instead of changing multiple components at the same time.

A typical LUMS request passes through several layers:

```text
Browser
   ↓
HTTPS
   ↓
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker
   ↓
Gunicorn
   ↓
Flask
   ↓
SQLite
```

Client communication follows a different path:

```text
LUMS Agent
   ↓
HTTPS
   ↓
Nginx
   ↓
LUMS API
   ↓
SQLite
```

Update execution adds another layer:

```text
Update Job
   ↓
Agent
   ↓
Idle Detection
   ↓
Job Claim
   ↓
Package Manager
   ↓
APT / dpkg
        or
pacman
   ↓
Result Reporting
```

When troubleshooting, determine first **which layer is actually failing**.

---

# 2. General Troubleshooting Principle

Do not immediately restart everything.

First collect evidence.

Recommended order:

```text
1. Observe the symptom
2. Identify the affected component
3. Check service state
4. Check logs
5. Check network communication
6. Check authentication
7. Check database state
8. Reproduce the problem
9. Apply one change
10. Test again
```

This is especially important for update jobs.

Restarting the server or agent can change the job state and therefore destroy useful information about the original failure.

---

# 3. Quick System Overview

The current LUMS deployment consists of:

```text
LUMS Server
├── Nginx
├── Docker
│   └── lums
│       ├── Gunicorn
│       ├── Flask
│       └── SQLite
│
├── /etc/lums/secrets/
│   └── lums_secret
│
└── Docker volume
    └── lums-data
```

Client:

```text
Linux Client
├── lums-agent.service
├── lums-agent.timer
├── lums-execution-watcher.service
├── lums-execution-watcher.timer
└── /opt/lums-agent/
```

The agent currently uses:

```text
Agent version: 1.7.0
```

---

# 4. First Checks

Before investigating a specific problem, check the basic server state.

## 4.1 Docker

```bash
sudo docker ps
```

Expected:

```text
lums
```

If the container is not running:

```bash
sudo docker ps -a
```

Then inspect the container:

```bash
sudo docker inspect lums
```

Useful properties include:

```text
Status
Image
ReadonlyRootfs
User
CapDrop
Privileged
RestartPolicy
Mounts
Ports
```

The production container is intentionally hardened.

Expected properties include:

```text
User: lums
ReadonlyRootfs: true
Privileged: false
CapDrop: ALL
RestartPolicy: unless-stopped
```

The application is bound to:

```text
127.0.0.1:5050
```

and the container listens internally on:

```text
5000
```

---

# 5. Check the LUMS Container Logs

The first diagnostic command for an application problem is:

```bash
sudo docker logs --tail 100 lums
```

For continuous monitoring:

```bash
sudo docker logs -f lums
```

Look for:

```text
ERROR
Traceback
Exception
database
authentication
migration
Gunicorn
worker
```

A normal startup contains messages similar to:

```text
=== LUMS database initialization ===
LUMS-Datenbank aktualisiert: /var/lib/lums/lums.db
=== Starting Gunicorn ===
Starting gunicorn
Listening at: http://0.0.0.0:5000
```

The Gunicorn listener is internal to the container.

External clients should communicate through HTTPS/Nginx rather than directly accessing port `5000`.

---

# 6. Check Gunicorn

Gunicorn runs inside the LUMS container.

Check the process:

```bash
sudo docker exec lums ps
```

If the container image does not provide `ps`, inspect the container processes with:

```bash
sudo docker top lums
```

Expected application process:

```text
gunicorn
```

The container should not require an interactive shell for normal operation.

---

# 7. Check Nginx

Check Nginx:

```bash
sudo systemctl status nginx --no-pager
```

Check the configuration:

```bash
sudo nginx -t
```

Expected:

```text
syntax is ok
test is successful
```

If Nginx is not running:

```bash
sudo systemctl restart nginx
```

Then verify:

```bash
sudo systemctl status nginx --no-pager
```

Do not repeatedly restart Nginx without first checking the configuration and logs.

---

# 8. Check Nginx Logs

Error log:

```bash
sudo tail -n 100 /var/log/nginx/error.log
```

Access log:

```bash
sudo tail -n 100 /var/log/nginx/access.log
```

For live monitoring:

```bash
sudo tail -f /var/log/nginx/error.log
```

Useful symptoms include:

```text
502 Bad Gateway
connection refused
upstream timed out
SSL errors
client request errors
```

A `502 Bad Gateway` generally means that Nginx cannot successfully communicate with the configured upstream.

The next check should therefore be the local LUMS application binding.

---

# 9. Check the Local Application Port

The production application is published locally as:

```text
127.0.0.1:5050
```

Check the listener:

```bash
sudo ss -ltnp | grep ':5050'
```

Expected:

```text
127.0.0.1:5050
```

If nothing is listening, check:

```bash
sudo docker ps
sudo docker logs --tail 100 lums
```

Then inspect the Docker port mapping:

```bash
sudo docker port lums
```

Expected mapping:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 10. HTTPS Test

Test the LUMS HTTPS endpoint locally:

```bash
curl -k -I https://127.0.0.1/
```

The exact HTTP status depends on the requested route.

Do not use:

```bash
curl -k https://127.0.0.1/health
```

as a generic health check unless a `/health` endpoint has explicitly been implemented.

LUMS does not use a generic `/health` endpoint as its primary diagnostic interface.

Instead, test an actual application/API endpoint.

For example:

```bash
curl -k -i https://127.0.0.1/api/clients
```

A successful response demonstrates that the request reached the application layer.

---

# 11. Test the API

The API can be tested directly through Nginx.

Example:

```bash
curl -k -i https://127.0.0.1/api/clients
```

A successful response confirms that the following path is functioning:

```text
curl
 ↓
TLS
 ↓
Nginx
 ↓
Docker port mapping
 ↓
Gunicorn
 ↓
Flask
```

If the request fails, determine the HTTP status before changing anything.

Useful status codes:

```text
200  Request successful
201  Resource created
204  Request successful without response body
400  Invalid request
401  Authentication failed
403  Request forbidden
404  Route/resource not found
409  Conflict
429  Rate limit
500  Internal server error
502  Nginx upstream problem
```

The status code should always be interpreted together with the relevant server or application log.

---

# 12. Authentication Problems

LUMS uses different authentication mechanisms for administrators and clients.

```text
Administrator
    ↓
Web login
    ↓
Session

Linux client
    ↓
Bearer token
    ↓
API
```

These authentication paths should not be treated as the same problem.

---

## 12.1 Administrator Login

If the administrator cannot log in, first check:

```bash
sudo docker logs --tail 100 lums
```

Then inspect the login response.

A failed login should not reveal whether the username exists.

The application uses a generic authentication error:

```text
Invalid username or password.
```

This avoids exposing account existence through different error messages.

---

# 13. Login Rate Limiting

LUMS includes login rate limiting.

The current lock escalation is:

```text
5 failed attempts → 30 seconds
6 failed attempts → 60 seconds
7 failed attempts → 120 seconds
8+ failed attempts → 300 seconds
```

The rate-limit key combines:

```text
normalized username
+
request source address
```

A blocked login is intentionally handled as an authentication failure from the user's perspective.

Do not repeatedly submit credentials during troubleshooting once rate limiting has been triggered.

Instead, inspect the application state and wait for the lock interval to expire.

---

# 14. Client Authentication Problems

The LUMS agent authenticates with its client-specific Bearer token.

A typical request path is:

```text
lums-agent
   ↓
HTTPS
   ↓
Bearer token
   ↓
LUMS API
```

A client authentication failure commonly appears as:

```text
401 Unauthorized
```

When this occurs, check the agent configuration first.

On the client:

```bash
sudo systemctl status lums-agent.service --no-pager
```

Then inspect the service logs:

```bash
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

Check the configured environment:

```bash
sudo systemctl cat lums-agent.service
```

If the agent uses an environment file:

```bash
sudo cat /etc/default/lums-agent
```

Do not paste the actual Bearer token into tickets, GitHub issues, documentation, screenshots, or chat messages.

---

# 15. Token Rotation Troubleshooting

LUMS stores a SHA-256 digest of the client token rather than the plaintext token.

When a client token is rotated:

```text
Old token
   ↓
invalid
```

and:

```text
New token
   ↓
valid
```

The plaintext token is returned only during the rotation operation.

If the old token is still being used by the agent, the API should reject the request.

Expected result:

```text
401 Unauthorized
```

After replacing the token on the client, restart the agent:

```bash
sudo systemctl restart lums-agent.service
```

Then check:

```bash
sudo systemctl status lums-agent.service --no-pager
```

and:

```bash
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

Finally verify that the client reports successfully again.

---

# 16. Do Not Put Tokens Into Git

Never commit:

```text
Bearer tokens
API tokens
LUMS_SECRET_KEY
passwords
private keys
TLS private keys
database credentials
```

into the repository.

Check the working tree before committing:

```bash
git status
```

Then inspect the diff:

```bash
git diff
```

For staged changes:

```bash
git diff --cached
```

Also run:

```bash
git diff --check
```

before committing.

If a secret was accidentally committed, rotating the secret is required. Simply deleting the line in a later commit does not remove the secret from Git history.

---

# 17. Agent Service Troubleshooting

Check the service:

```bash
sudo systemctl status lums-agent.service --no-pager
```

Check recent logs:

```bash
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

Check the timer:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

List timers:

```bash
systemctl list-timers --all | grep lums
```

The agent should normally be triggered through its systemd timer.

A manual test can be performed with:

```bash
sudo systemctl start lums-agent.service
```

Then:

```bash
sudo systemctl status lums-agent.service --no-pager
```

and:

```bash
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

---

# 18. Agent Reporting

A successful agent report should result in an accepted API response.

Typical diagnostic sequence:

```bash
sudo systemctl start lums-agent.service

sudo systemctl status lums-agent.service --no-pager

sudo journalctl -u lums-agent.service -n 100 --no-pager
```

Look for:

```text
REPORT ACCEPTED
```

and the reported inventory:

```text
installed packages
available updates
agent version
hostname
operating system
kernel
package manager
```

If the report fails with `401`, investigate authentication.

If it fails with a TLS error, investigate:

```text
CA configuration
certificate
hostname
Nginx
TLS configuration
```

If it fails with a connection error, investigate:

```text
network connectivity
DNS
routing
Nginx
server availability
```

---

# 19. Agent Version Mismatch

The current agent version is:

```text
1.7.0
```

Check the installed version on a client using the LUMS agent's normal version output or service logs.

If the server reports an unexpected version, verify that the intended agent files are actually installed.

Do not assume that editing the source directory automatically changes the installed systemd service.

A useful first check is:

```bash
sudo systemctl cat lums-agent.service
```

Then determine the executable path used by the service.

After an agent update:

```bash
sudo systemctl daemon-reload
sudo systemctl restart lums-agent.service
```

if the service definition itself changed.

Finally:

```bash
sudo systemctl status lums-agent.service --no-pager
```

---

# 20. Execution Watcher

Update execution is handled separately from the reporting agent.

Check:

```bash
sudo systemctl status lums-execution-watcher.service --no-pager
```

and:

```bash
sudo systemctl status lums-execution-watcher.timer --no-pager
```

Recent logs:

```bash
sudo journalctl -u lums-execution-watcher.service -n 100 --no-pager
```

The execution watcher is responsible for:

```text
job discovery
   ↓
idle-state evaluation
   ↓
job recovery
   ↓
atomic job claim
   ↓
package update
   ↓
result reporting
```

A reporting problem and an execution problem are therefore not necessarily the same issue.

---

# 21. Idle-State Problems

LUMS uses `loginctl` for idle detection.

The current idle threshold is:

```text
300 seconds
```

The agent can report:

```text
idle_source=loginctl
idle_supported=True
```

If an update job remains in:

```text
waiting_for_idle
```

check the client state first.

Useful command:

```bash
loginctl list-users
```

Then inspect the relevant session:

```bash
loginctl list-sessions
```

For a specific session:

```bash
loginctl show-session <SESSION_ID>
```

Useful properties include:

```text
IdleHint
IdleSinceHint
IdleSinceHintMonotonic
State
Remote
Type
```

Do not manually force an update merely because a job is waiting for idle state.

The waiting state is intentional.

---

# 22. First Diagnostic Rule

When a problem occurs, preserve the state before changing it.

Collect:

```bash
sudo docker ps
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo systemctl status lums-agent.service --no-pager
sudo systemctl status lums-execution-watcher.service --no-pager
```

Then inspect the relevant logs.

Only after the affected layer has been identified should a restart, configuration change, token rotation, or database operation be performed.

This keeps troubleshooting reproducible and reduces the chance of destroying useful diagnostic information.

# 23. Agent Service and Timer

The LUMS agent runs as a systemd `oneshot` service.

Check the service:

```bash
sudo systemctl status lums-agent.service --no-pager
```

Check recent logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

A successful `oneshot` service may return to:

```text
inactive (dead)
```

This does not automatically indicate a failure.

The recurring execution is controlled by:

```text
lums-agent.timer
```

Check the timer:

```bash
sudo systemctl status lums-agent.timer --no-pager
```

List all relevant timers:

```bash
systemctl list-timers --all | grep lums
```

The expected flow is:

```text
systemd timer
      ↓
lums-agent.service
      ↓
agent.py
      ↓
report
      ↓
exit
      ↓
next timer run
```

The timer and the `oneshot` service must therefore be checked separately.

---

# 24. Execution Watcher

Update execution is handled separately from normal agent reporting.

Check the watcher service:

```bash
sudo systemctl status \
    lums-execution-watcher.service \
    --no-pager
```

Check the timer:

```bash
sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager
```

Check recent logs:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

The watcher is responsible for the execution side of the update workflow:

```text
Job available
    ↓
Idle detection
    ↓
Recovery / lookup
    ↓
Atomic claim
    ↓
Update execution
    ↓
Result reporting
```

A healthy reporting agent does not automatically mean that update execution is healthy.

Likewise, a problem with the execution watcher does not necessarily mean that client reporting is broken.

---

# 25. Authentication: 401 vs. 403

A useful first diagnostic distinction is:

```text
401 Unauthorized
    ↓
Authentication problem
```

versus:

```text
403 Forbidden
    ↓
Authorization problem
```

This is a diagnostic starting point, not an absolute rule for every endpoint.

Always identify:

```text
endpoint
HTTP status
request type
client
server log
```

before replacing credentials.

For an agent authentication problem, check:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Then inspect the LUMS container:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

---

# 26. Agent Reporting

If a client appears online but does not report correctly, troubleshoot the complete reporting path:

```text
Agent
   ↓
Network
   ↓
TLS
   ↓
Authentication
   ↓
Report endpoint
   ↓
Database
   ↓
Frontend
```

Check the agent:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Then check the server:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

A successful report should produce an accepted response.

Typical successful output:

```text
REPORT ACCEPTED
```

The current agent version is:

```text
1.7.0
```

The current Debian and Arch clients have both been tested successfully with the 1.7.0 agent.

---

# 27. Inspecting Clients Without Exposing Tokens

Client information can be inspected without selecting authentication credentials.

If SQLite CLI is available inside the container:

```bash
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "SELECT id, hostname, ip, enabled FROM clients;"
```

Do **not** include token columns in diagnostic output that may later be copied into documentation, issues, screenshots, or chat.

If the SQLite CLI is not available in the image, use the application's existing API or Python/SQLite tooling instead.

The important diagnostic fields are generally:

```text
id
hostname
ip
enabled
last_seen
```

Authentication secrets are not troubleshooting data.

---

# 28. Client Token Problems

Each LUMS client has its own authentication token.

The token lifecycle is:

```text
Client registration
      ↓
Token generated
      ↓
Token digest stored
      ↓
Agent authenticates
```

The server stores the SHA-256 hexadecimal digest of the client token.

The plaintext token is not stored as the normal database credential.

If a token is rotated:

```text
Old token
    ↓
revoked

New token
    ↓
active
```

The old token must no longer authenticate.

If an agent suddenly receives:

```text
401 Unauthorized
```

after token rotation, verify that the agent configuration contains the new token.

Then restart the service:

```bash
sudo systemctl restart lums-agent.service
```

Check:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

and:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 29. Client Token Rotation Checklist

When rotating a client token:

```text
1. Rotate token on server
2. Securely record the new token
3. Replace the old token on the client
4. Do not commit the token
5. Restart the agent
6. Trigger/report
7. Verify successful authentication
8. Verify last_seen
```

The old token should fail authentication.

The new token should succeed.

Never test token rotation by publishing the old or new token in a diagnostic document.

---

# 30. Idle Detection

LUMS uses systemd-logind through:

```text
loginctl
```

The old:

```text
w -h
```

based approach is not the current implementation.

The agent evaluates relevant user sessions using information such as:

```text
Class
Type
TTY
State
IdleHint
IdleSinceHintMonotonic
```

The result includes:

```text
idle
idle_seconds
threshold_seconds
idle_source
idle_supported
```

The current source is:

```text
loginctl
```

The current threshold is:

```text
300 seconds
```

---

# 31. Idle Detection Diagnostics

List sessions:

```bash
loginctl list-sessions \
    --no-legend \
    --no-pager
```

Inspect an individual session:

```bash
loginctl show-session <SESSION_ID>
```

Useful properties:

```text
Class
Type
TTY
State
IdleHint
IdleSinceHintMonotonic
```

The agent can report:

```text
idle_source=loginctl
idle_supported=True
```

when idle detection is available.

A user actively working on the client should not be treated as idle merely because the agent cannot determine the session state.

---

# 32. Idle Detection Failure Behavior

Idle detection is intentionally conservative.

If logind information cannot be retrieved reliably, the agent does not pretend that the system is idle.

Conceptually:

```text
Idle confirmed
    ↓
Update may proceed

Idle not confirmed
    ↓
Do not assume idle
```

This is important because update operations can be disruptive.

An unknown state must therefore not silently become:

```text
idle = true
```

When investigating an unexpected `waiting_for_idle` state, check `loginctl` and the agent logs before changing the job.

---

# 33. Package Manager Detection

The agent uses a dedicated package-manager abstraction.

Current supported implementations:

```text
APT / dpkg
pacman
```

Conceptually:

```text
detect_package_manager()
        │
        ├── apt
        │      ↓
        │  AptPackageManager
        │
        └── pacman
               ↓
           PacmanPackageManager
```

This keeps distribution-specific package-manager logic outside the main update engine.

A package-management problem should therefore first be classified as:

```text
LUMS logic
        or
package-manager implementation
        or
repository/network problem
```

---

# 34. Debian / APT Diagnostics

On Debian-based clients:

```bash
command -v apt
command -v dpkg
```

Expected:

```text
/usr/bin/apt
/usr/bin/dpkg
```

Check package database consistency:

```bash
dpkg --audit
```

Check APT:

```bash
sudo apt-get check
```

Check available updates:

```bash
apt list --upgradable
```

Check an individual package:

```bash
dpkg-query -W <PACKAGE>
```

Check the candidate version:

```bash
apt-cache policy <PACKAGE>
```

Do not immediately run repair commands merely because LUMS reports a package problem.

First determine whether the package manager itself reports an error.

---

# 35. Arch / pacman Diagnostics

On Arch Linux clients:

```bash
command -v pacman
```

Expected:

```text
/usr/bin/pacman
```

Check installed packages:

```bash
pacman -Q
```

Check available updates:

```bash
pacman -Qu
```

Check an individual package:

```bash
pacman -Q <PACKAGE>
```

Check package information:

```bash
pacman -Si <PACKAGE>
```

Do not use Debian-specific troubleshooting commands on an Arch client.

The LUMS package-manager abstraction exists specifically so the agent can use the native package-management mechanism of each supported distribution.

---

# 36. Package Manager Locks

Package managers may refuse to operate when another package-management process already holds a lock.

On Debian-based systems:

```bash
sudo lsof \
    /var/lib/dpkg/lock-frontend
```

and:

```bash
sudo lsof \
    /var/lib/dpkg/lock
```

On Arch:

```bash
sudo lsof \
    /var/lib/pacman/db.lck
```

Do **not** blindly delete lock files.

First determine whether another legitimate package operation is currently running.

For example:

```text
Automatic update
    ↓
APT

LUMS
    ↓
APT
```

can create an external coordination problem.

LUMS controls its own update execution, but it cannot automatically prevent every manually started package-manager process on the operating system from running at the same time.

---

# 37. Update Jobs

When a job does not execute, determine where it stopped.

The current lifecycle is:

```text
Job created
    ↓
pending
    ↓
waiting_for_idle
    ↓
running
    ↓
success / partial / failed
```

An interrupted execution may additionally result in:

```text
abandoned
```

The execution path is:

```text
Job
 ↓
Agent retrieves job
 ↓
Idle check
 ↓
Atomic claim
 ↓
Package manager
 ↓
Update execution
 ↓
Result
 ↓
Server
 ↓
History
```

Check the server:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Check the agent:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Check the execution watcher:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

---

# 38. Supported Update Actions

The current update engine supports:

```text
UPDATE_SYSTEM
UPDATE_PACKAGE
INSTALL_PACKAGE
REMOVE_PACKAGE
```

The action is interpreted by the client-side package-manager abstraction.

Conceptually:

```text
LUMS action
      ↓
Package-manager abstraction
      ↓
APT / dpkg
or
pacman
```

The server does not need to contain separate copies of every distribution-specific command.

---

# 39. System Update Diagnostics

For Debian-based clients:

```text
UPDATE_SYSTEM
      ↓
apt-get upgrade -y
```

For Arch clients:

```text
UPDATE_SYSTEM
      ↓
pacman -Syu --noconfirm
```

The actual implementation is handled by the package-manager abstraction.

When a system update fails, determine whether the failure originated from:

```text
LUMS
Agent
Package manager
Repository
Network
Dependency resolution
Package state
Reboot requirement
```

Start with the agent log:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Then reproduce the package-manager problem directly on the affected client if appropriate.

---

# 40. Update Timeout Handling

Package operations are executed with timeout handling.

The current implementation uses selector-driven process output handling so that a silent child process cannot indefinitely block the timeout logic.

If a package operation exceeds its timeout:

```text
Timeout
   ↓
SIGTERM
   ↓
grace period
   ↓
SIGKILL fallback
```

The current termination grace period is:

```text
10 seconds
```

A timeout is therefore reported as an actual execution result rather than leaving the agent permanently blocked on a child process.

When troubleshooting a timeout, inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

and determine:

```text
which action
which package
how long it ran
whether SIGTERM was sent
whether kill fallback was required
```

Do not interpret every timeout as a package-manager bug. The timeout may also indicate:

```text
repository delay
network problem
package-manager deadlock
interactive package operation
broken package state
slow filesystem
external process contention
```

---

# 41. Simulation Mode

Simulation mode is useful for testing the job lifecycle without performing a real package update.

It can be used to test:

```text
job creation
job claiming
agent behavior
result reporting
frontend state
deployment
troubleshooting
```

Simulation does not prove that a real package-manager operation will succeed.

When troubleshooting a real update problem, verify that simulation is not enabled unintentionally.

After a simulation test:

```text
temporary test configuration
        ↓
remove / disable
        ↓
real execution
```

A successful simulation should therefore not be documented as a successful package update.

---

# 42. Interrupted Job Recovery

A job may remain in `running` if the agent disappears before submitting its final result.

LUMS contains recovery handling for this situation.

Conceptually:

```text
running
   ↓
agent disappears
   ↓
recovery
   ↓
abandoned
```

Recovery validates:

```text
job ownership
job state
client ownership
recovery conditions
```

The recovery reason is:

```text
Agent did not submit a final result.
```

The job is not falsely reported as successful.

---

# 43. Recovery Race Protection

Recovery must not overwrite a newer state transition.

Conceptually:

```text
                    ┌── agent result
running ────────────┤
                    └── recovery
```

Only the valid state transition should succeed.

This prevents a stale recovery operation from changing a job that has already completed.

If a recovery problem is suspected, inspect:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

and the watcher:

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

---

# 44. Recovery Verification

A recovered job should contain an appropriate final state and recovery information.

Expected recovery information includes:

```text
status:
    abandoned
```

and:

```text
recovery_reason:
    Agent did not submit a final result.
```

The associated history must remain available.

Package statistics must not silently disappear during recovery.

A recovery test should therefore verify:

```text
job state
finished_at
recovery reason
history
package statistics
```

After controlled testing, temporary test data should be removed.

---

# 45. Database Troubleshooting

LUMS uses SQLite for application persistence.

The database is stored inside the persistent Docker volume:

```text
lums-data
    ↓
/var/lib/lums/lums.db
```

The container itself is replaceable.

The persistent volume is separate.

Therefore:

```text
Container
replaceable

Volume
persistent
```

Do not remove the Docker volume merely because the container needs to be recreated.

---

# 46. SQLite Connection Settings

LUMS configures SQLite connections with:

```text
foreign_keys = ON
busy_timeout = 5000
```

The database uses:

```text
journal_mode = WAL
```

WAL means:

```text
Write-Ahead Logging
```

The relevant runtime values can be inspected from the database if diagnostic access is required.

Expected:

```text
foreign_keys = 1
busy_timeout = 5000
journal_mode = wal
```

These settings reduce common SQLite concurrency problems and ensure foreign-key enforcement is active.

---

# 47. SQLite Integrity Check

If database corruption or unexpected database behavior is suspected, check integrity before modifying the database.

Example:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

db = "/var/lib/lums/lums.db"
connection = sqlite3.connect(db)

print("integrity:", connection.execute(
    "PRAGMA integrity_check"
).fetchone()[0])

print("foreign_keys:", connection.execute(
    "PRAGMA foreign_keys"
).fetchone()[0])

print("journal_mode:", connection.execute(
    "PRAGMA journal_mode"
).fetchone()[0])

print("busy_timeout:", connection.execute(
    "PRAGMA busy_timeout"
).fetchone()[0])

connection.close()
'
```

Expected integrity result:

```text
integrity: ok
```

For foreign-key validation:

```bash
sudo docker exec lums \
    python3 -c '
import sqlite3

db = "/var/lib/lums/lums.db"
connection = sqlite3.connect(db)

rows = connection.execute(
    "PRAGMA foreign_key_check"
).fetchall()

print(rows)

connection.close()
'
```

Expected:

```text
[]
```

Do not modify or delete database files before collecting diagnostic information and creating an appropriate backup.

---

# 48. Database Locking Problems

SQLite uses a busy timeout of:

```text
5000 ms
```

If database operations still fail with locking errors, first determine whether multiple operations are competing for the database.

Look for errors such as:

```text
database is locked
```

Then inspect:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

and identify:

```text
request
migration
job claim
login operation
background operation
```

Do not solve SQLite locking problems by simply deleting the database.

The correct approach is to identify the competing transaction and verify that the application uses the configured connection handling correctly.

---

# 49. Migration Problems

Database migrations are part of the LUMS deployment process.

If a migration fails, inspect the container logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Do not manually edit the migration history table unless the migration procedure explicitly requires it.

Before attempting a migration repair:

```text
1. Stop making unrelated changes
2. Preserve the database
3. Create a backup
4. Record the migration error
5. Identify the migration version
6. Inspect the migration code
7. Verify the database schema
```

The current production database contains the login-rate-limiting migration:

```text
003-login-rate-limiting
```

The production database has been verified with:

```text
integrity_check = ok
foreign_key_check = []
```

---

# 50. Docker Image vs. Running Container

A common troubleshooting mistake is assuming that rebuilding an image automatically updates the running container.

It does not.

The deployment chain is:

```text
Source
   ↓
docker build
   ↓
Image
   ↓
Container creation
   ↓
Running application
```

After changing source code:

```bash
sudo docker build \
    -t lums:latest \
    .
```

A running container created from an older image will continue using that older image.

Verify the running container:

```bash
sudo docker inspect lums \
    --format '{{.Image}}'
```

Then compare the image used by the container with the image that was just built.

If the container must be replaced, preserve:

```text
lums-data
```

and:

```text
/etc/lums/secrets/lums_secret
```

before removing the old container.

---

# 51. Container Hardening Verification

After recreating the production container, verify the hardening configuration.

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{.HostConfig.CapDrop}}
RestartPolicy={{.HostConfig.RestartPolicy.Name}}
'
```

Expected:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=[ALL]
RestartPolicy=unless-stopped
```

Also verify the application binding:

```bash
sudo docker port lums
```

Expected:

```text
5000/tcp -> 127.0.0.1:5050
```

The LUMS application should not be unnecessarily exposed directly to the network.

---

# 52. Persistent Data vs. Container Recreation

Replacing the container should not remove:

```text
lums-data
```

or the external secret file.

Before container maintenance:

```bash
sudo docker volume inspect lums-data
```

Check the secret:

```bash
sudo stat \
    /etc/lums/secrets/lums_secret
```

The secret should remain outside the container image.

The application receives it through:

```text
LUMS_SECRET_KEY_FILE
        ↓
/run/secrets/lums_secret
```

Do not bake the secret into the Docker image.

---

# 53. Browser / Frontend Troubleshooting

If the API works but the frontend behaves incorrectly, do not immediately modify Flask.

First inspect:

```text
Browser console
Network requests
HTTP status codes
CSS
JavaScript
localStorage
Browser cache
```

The frontend deployment path is:

```text
Git source
   ↓
Docker build
   ↓
Docker image
   ↓
Container
   ↓
Nginx
   ↓
Browser
```

If a frontend change does not appear, verify that the new source was actually included in the image and that the running container was recreated.

For theme problems, also inspect:

```text
lums-theme
```

in browser localStorage.

A stale theme selection can make a frontend appear incorrect even when the backend is functioning normally.


# 53. HTTPS / TLS Diagnostics

LUMS exposes the web application through Nginx using HTTPS.

The expected path is:

```text
HTTPS :443
    ↓
Nginx
    ↓
127.0.0.1:5050
    ↓
Docker
    ↓
Gunicorn :5000
```

Check the TLS configuration files:

```bash
sudo ls -la /etc/lums/tls/
```

Inspect the public certificate:

```bash
sudo openssl x509 \
    -in /etc/lums/tls/lums.crt \
    -noout \
    -subject \
    -issuer \
    -dates
```

Never display or publish:

```text
/etc/lums/tls/lums.key
```

The private key must remain protected.

---

# 54. TLS Connection Test

Test the HTTPS endpoint:

```bash
curl -kI \
    https://<LUMS_SERVER_IP>/
```

For a self-signed certificate, `-k` may be required for local diagnostic testing.

This does **not** mean that TLS verification should be disabled in the LUMS agent.

The agent must continue to verify the configured CA/certificate.

For detailed TLS diagnostics:

```bash
openssl s_client \
    -connect <LUMS_SERVER_IP>:443 \
    -servername <LUMS_SERVER_IP> \
    </dev/null
```

Inspect the configured protocols:

```bash
sudo nginx -T | \
    grep -n 'ssl_protocols'
```

The expected modern configuration is:

```text
TLSv1.2
TLSv1.3
```

Older TLS versions should not be enabled.

---

# 55. HTTP Redirect

HTTP should redirect clients to HTTPS.

Test:

```bash
curl -I \
    http://<LUMS_SERVER_IP>/
```

The expected result is an HTTP redirect to the HTTPS endpoint.

If the redirect is missing, inspect the active Nginx configuration:

```bash
sudo nginx -T
```

Then check:

```bash
sudo nginx -t
```

Only reload Nginx after the configuration test succeeds:

```bash
sudo systemctl reload nginx
```

---

# 56. Nginx 502 Bad Gateway

A `502 Bad Gateway` normally means that Nginx cannot successfully communicate with its configured upstream.

Start with the local application binding:

```bash
curl -I \
    http://127.0.0.1:5050/
```

If this fails, investigate:

```text
Docker
Gunicorn
Flask
```

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

And:

```bash
sudo ss -lntp | \
    grep ':5050'
```

Only after the local upstream is confirmed should the investigation move further into Nginx configuration.

Check Nginx:

```bash
sudo nginx -t
```

and:

```bash
sudo journalctl \
    -u nginx \
    --since "30 minutes ago" \
    --no-pager
```

---

# 57. Nginx Logs

Access log:

```bash
sudo tail \
    -n 100 \
    /var/log/nginx/access.log
```

Error log:

```bash
sudo tail \
    -n 100 \
    /var/log/nginx/error.log
```

Live error monitoring:

```bash
sudo tail \
    -f \
    /var/log/nginx/error.log
```

Useful errors include:

```text
502 Bad Gateway
upstream connection refused
upstream timed out
SSL errors
permission denied
invalid configuration
```

Always correlate the Nginx timestamp with the application and Docker logs.

---

# 58. Port Diagnostics

Check the relevant ports:

```bash
sudo ss -lntp | \
    grep -E ':(22|80|443|5000|5050)\b'
```

The intended architecture is:

```text
22
SSH

80
HTTP / redirect

443
HTTPS / Nginx

5050
LUMS host-side application binding

5000
Gunicorn inside Docker
```

Port `5050` should normally be bound only to:

```text
127.0.0.1
```

The application should therefore not be directly exposed on the LAN through port `5050`.

Port `5000` is the internal application port inside the container.

---

# 59. Firewall Diagnostics

If network connectivity fails, check the host firewall.

For UFW:

```bash
sudo ufw status verbose
```

If nftables is used:

```bash
sudo nft list ruleset
```

Do not modify firewall rules merely because an application is not responding.

First establish whether the firewall is actually involved.

A useful diagnostic path is:

```text
Client
   ↓
Network
   ↓
Server
   ↓
Port 443
   ↓
Nginx
```

If the client cannot reach port `443`, investigate network/firewall/TLS before changing Flask or SQLite.

---

# 60. Network Diagnostics

From a client, test basic connectivity:

```bash
ping <LUMS_SERVER_IP>
```

Then test TCP connectivity:

```bash
nc -vz \
    <LUMS_SERVER_IP> \
    443
```

If `nc` is unavailable, use:

```bash
timeout 5 \
    bash -c '</dev/tcp/<LUMS_SERVER_IP>/443'
```

Then test HTTPS:

```bash
curl -kI \
    https://<LUMS_SERVER_IP>/
```

Interpret failures in order:

```text
ping fails
    ↓
network / routing

ping works, TCP 443 fails
    ↓
firewall / listener / routing

TCP 443 works, HTTPS fails
    ↓
TLS / Nginx

HTTPS works, API fails
    ↓
application / authentication / endpoint
```

---

# 61. Secret Configuration

The production Flask secret is file-based.

The expected environment configuration is:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

The secret is mounted read-only:

```text
/etc/lums/secrets/lums_secret
        ↓
/run/secrets/lums_secret
```

Check the environment without displaying values:

```bash
sudo docker exec lums sh -c '
env |
grep -E "^(LUMS_|FLASK_|PYTHON)" |
sed "s/=.*$/=<set>/"
'
```

The production environment should not contain:

```text
LUMS_SECRET_KEY=<actual secret>
```

Instead, the file-based configuration should be visible as:

```text
LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret
```

Never print the actual secret during troubleshooting.

---

# 62. Secret File Permissions

Check the secret:

```bash
sudo stat \
    -c '%U:%G %a %n' \
    /etc/lums/secrets/lums_secret
```

The secret should be readable only by the identities that require it.

Check that the file exists:

```bash
sudo test \
    -s /etc/lums/secrets/lums_secret \
    && echo "secret file exists"
```

Do not use:

```bash
chmod 777
```

as a troubleshooting solution.

If the container cannot read the secret, determine:

```text
host file ownership
host file permissions
container user
bind mount
read-only mount
application configuration
```

---

# 63. Docker Container Diagnostics

Check the running container:

```bash
sudo docker ps \
    --filter name=lums
```

Inspect the image:

```bash
sudo docker inspect \
    -f '{{.Config.Image}}' \
    lums
```

Inspect the container ID:

```bash
sudo docker inspect \
    -f '{{.Id}}' \
    lums
```

Inspect the restart policy:

```bash
sudo docker inspect \
    -f '{{.HostConfig.RestartPolicy.Name}}' \
    lums
```

Expected:

```text
unless-stopped
```

---

# 64. Container Hardening Diagnostics

Verify the production runtime:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
RestartPolicy={{.HostConfig.RestartPolicy.Name}}
'
```

Expected security properties:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
RestartPolicy=unless-stopped
```

The container also uses a writable temporary filesystem:

```text
/tmp
```

with restrictive mount options.

The application data remains on:

```text
lums-data
```

The secret remains outside the image.

---

# 65. Docker Volume Diagnostics

Inspect the persistent volume:

```bash
sudo docker volume inspect \
    lums-data
```

Verify that the running container uses it:

```bash
sudo docker inspect lums \
    --format '{{json .Mounts}}'
```

The database must remain associated with:

```text
lums-data
```

Do **not** use this as a generic repair command:

```bash
sudo docker volume rm lums-data
```

Removing the volume is destructive and can remove the application database.

Container recreation and volume deletion are two completely different operations.

---

# 66. Container Recreation

A container can be replaced without deleting the persistent application volume.

The conceptual deployment is:

```text
Source
   ↓
Docker image
   ↓
Container
   ↓
lums-data
```

When rebuilding:

```bash
sudo docker build \
    -t lums:latest \
    .
```

the existing container does not automatically switch to the new image.

The container must be recreated when a new image should be deployed.

Before doing so, verify:

```text
lums-data
/etc/lums/secrets/lums_secret
/etc/lums/tls/
```

are preserved.

After recreation, verify:

```bash
sudo docker ps
sudo docker logs --tail 100 lums
```

and then test the application through Nginx.

---

# 67. Read-Only Root Filesystem Problems

The production container uses:

```text
ReadonlyRootfs=true
```

This is intentional.

If an application component attempts to write somewhere outside the persistent volume or `/tmp`, it may fail with a permission or read-only filesystem error.

When this happens, do not immediately disable the read-only root filesystem.

First identify the path being written:

```text
Traceback
permission denied
read-only file system
```

Then determine whether the path should instead be:

```text
persistent application data
temporary data
configuration
cache
```

The correct solution is to place writable data in the appropriate persistent volume or temporary filesystem.

---

# 68. Docker Logs After a Restart

After a container restart:

```bash
sudo docker restart lums
```

wait briefly and inspect:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

A normal startup should include the database initialization and Gunicorn startup.

For example:

```text
=== LUMS database initialization ===
LUMS-Datenbank aktualisiert: /var/lib/lums/lums.db
=== Starting Gunicorn ===
Starting gunicorn
Listening at: http://0.0.0.0:5000
```

If Gunicorn does not start, investigate the first error rather than repeatedly restarting the container.

---

# 69. Application Source Diagnostics

The repository is located at:

```text
/opt/lums-public
```

Check the working tree:

```bash
cd /opt/lums-public

git status
```

Inspect recent commits:

```bash
git log \
    --oneline \
    --decorate \
    -5
```

Check for whitespace errors:

```bash
git diff --check
```

If the running container appears to contain unexpected code, compare:

```text
Git source
    ↓
Docker build
    ↓
Image
    ↓
Running container
```

Do not assume that the Git working tree and running container are automatically identical.

---

# 70. Python Syntax Diagnostics

For Python source changes, run a syntax check before building the image.

Example:

```bash
cd /opt/lums-public

python3 -m py_compile \
    server/app.py
```

For the package-manager abstraction:

```bash
python3 -m py_compile \
    agent/package_manager.py
```

For the agent:

```bash
python3 -m py_compile \
    agent/agent.py
```

If the repository uses additional Python modules, compile-check the affected files as well.

A syntax error should be fixed before investigating Docker or Nginx.

---

# 71. Frontend Cache Problems

If the backend API works but a frontend change does not appear, inspect the browser before changing the server.

Check:

```text
Browser cache
localStorage
JavaScript console
Network requests
Loaded CSS
Loaded JavaScript
```

For theme selection, inspect:

```text
lums-theme
```

A stale value can make the interface appear to ignore a newly selected theme.

If necessary, clear the stored theme selection and reload the page.

Do not change Flask code merely because a CSS or JavaScript change is not visible.

---

# 72. Theme Troubleshooting

LUMS currently contains multiple frontend themes.

If the API works but a theme looks incorrect, investigate:

```text
CSS
JavaScript
DOM
localStorage
browser cache
```

before changing backend code.

The frontend deployment chain is:

```text
Git source
   ↓
Docker build
   ↓
Docker image
   ↓
Container recreation
   ↓
Browser
```

If the browser still shows an older version, verify that the running container actually contains the changed frontend files.

---

# 73. Permission Diagnostics

Check repository permissions:

```bash
ls -la \
    /opt/lums-public
```

Check TLS files:

```bash
sudo ls -la \
    /etc/lums/tls/
```

Check the secret:

```bash
sudo stat \
    /etc/lums/secrets/lums_secret
```

Check the agent:

```bash
sudo ls -la \
    /opt/lums-agent/
```

Do not solve permission errors with:

```bash
chmod -R 777
```

Determine which process needs access and grant only the required permission.

---

# 74. Backup Diagnostics

LUMS uses SQLite-aware backup procedures.

Before performing potentially destructive database operations:

```text
1. Preserve the current database
2. Create a backup
3. Verify the backup
4. Record the reason
5. Only then modify the database
```

A backup is not considered verified merely because a file exists.

The backup should be checked for SQLite integrity.

The current project documentation still treats a complete isolated restore test as outstanding.

Therefore:

```text
Backup creation
    ≠
Full restore validation
```

---

# 75. SQLite-Aware Backup

When a database backup is required, prefer an SQLite-aware backup mechanism instead of blindly copying a live database file.

The purpose is to obtain a consistent database snapshot while SQLite is active.

After creating the backup, perform an integrity check against the backup.

Conceptually:

```text
Live database
      ↓
SQLite-aware backup
      ↓
Backup file
      ↓
integrity_check
```

The backup should not be stored inside the application source repository.

---

# 76. Backup Integrity Check

A backup should be checked before it is considered usable.

Example:

```bash
python3 - <<'PY'
import sqlite3

backup = "/path/to/lums-backup.db"

connection = sqlite3.connect(backup)

print(
    "integrity:",
    connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]
)

print(
    "foreign_key_check:",
    connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()
)

connection.close()
PY
```

Expected:

```text
integrity: ok
foreign_key_check: []
```

Replace the example path with the actual backup path.

Never publish a backup containing production credentials, client tokens, inventory information, or other sensitive data.

---

# 77. Full Restore Testing

Creating and verifying a backup does not prove that a complete restore procedure works.

A full restore test should be performed separately and in an isolated environment.

The conceptual procedure is:

```text
Production database
       ↓
SQLite-aware backup
       ↓
Isolated environment
       ↓
Restore
       ↓
Integrity check
       ↓
Application startup
       ↓
Functional test
```

Do not perform an experimental restore directly against the production database.

The current LUMS project documentation considers the full isolated restore test a remaining task.

---

# 78. Diagnostic Log Reference

## Docker

```bash
sudo docker logs \
    --tail 200 \
    lums
```

## Nginx

```bash
sudo tail \
    -n 100 \
    /var/log/nginx/error.log
```

## Nginx service

```bash
sudo journalctl \
    -u nginx \
    --since "30 minutes ago" \
    --no-pager
```

## Agent

```bash
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

## Agent timer

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

## Execution watcher

```bash
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager
```

## Execution watcher timer

```bash
sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager
```

---

# 79. Complete Server Diagnostic Sequence

When the server appears broken, run the following sequence before making changes:

```bash
echo "=== DOCKER ==="
sudo docker ps --filter name=lums

echo
echo "=== IMAGE ==="
sudo docker inspect \
    -f '{{.Config.Image}}' \
    lums

echo
echo "=== CONTAINER HARDENING ==="
sudo docker inspect lums \
    --format \
    'User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
CapDrop={{json .HostConfig.CapDrop}}
Privileged={{.HostConfig.Privileged}}
RestartPolicy={{.HostConfig.RestartPolicy.Name}}'

echo
echo "=== PORTS ==="
sudo docker port lums

echo
echo "=== HOST PORT 5050 ==="
sudo ss -lntp | \
    grep ':5050' || true

echo
echo "=== NGINX ==="
sudo systemctl status nginx --no-pager

echo
echo "=== NGINX CONFIG ==="
sudo nginx -t

echo
echo "=== DOCKER LOGS ==="
sudo docker logs --tail 100 lums

echo
echo "=== LUMS AGENT ==="
sudo systemctl status lums-agent.service --no-pager

echo
echo "=== EXECUTION WATCHER ==="
sudo systemctl status \
    lums-execution-watcher.service \
    --no-pager
```

This sequence should normally be collected before restarting multiple services.

---

# 80. Complete Client Diagnostic Sequence

On a LUMS client:

```bash
echo "=== HOST ==="
hostnamectl

echo
echo "=== AGENT SERVICE ==="
sudo systemctl status \
    lums-agent.service \
    --no-pager

echo
echo "=== AGENT TIMER ==="
sudo systemctl status \
    lums-agent.timer \
    --no-pager

echo
echo "=== EXECUTION WATCHER ==="
sudo systemctl status \
    lums-execution-watcher.service \
    --no-pager

echo
echo "=== WATCHER TIMER ==="
sudo systemctl status \
    lums-execution-watcher.timer \
    --no-pager

echo
echo "=== AGENT LOG ==="
sudo journalctl \
    -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager

echo
echo "=== WATCHER LOG ==="
sudo journalctl \
    -u lums-execution-watcher.service \
    --since "30 minutes ago" \
    --no-pager

echo
echo "=== PACKAGE MANAGER ==="
command -v apt || true
command -v pacman || true

echo
echo "=== SESSIONS ==="
loginctl list-sessions \
    --no-legend \
    --no-pager
```

Do not include authentication tokens or secret configuration values in the resulting diagnostic output.

---

# 81. Security-Relevant Troubleshooting Checks

After security-sensitive deployment changes, verify the following.

## Container

```text
[ ] Non-root container user
[ ] Read-only root filesystem
[ ] ALL capabilities dropped
[ ] Privileged=false
[ ] /tmp available as temporary filesystem
[ ] Persistent volume mounted
```

## Secret

```text
[ ] Secret is file-based
[ ] Secret mount is read-only
[ ] LUMS_SECRET_KEY is not used for the production secret
[ ] LUMS_SECRET_KEY_FILE is configured
[ ] Secret is not logged
[ ] Secret is not committed to Git
```

## Network

```text
[ ] Application binds to 127.0.0.1:5050
[ ] Container port 5000 is internal
[ ] HTTPS terminates at Nginx
[ ] HTTP redirects to HTTPS
[ ] TLS verification remains enabled for agents
```

## Authentication

```text
[ ] Administrator authentication works
[ ] Login rate limiting works
[ ] Client authentication works
[ ] Token rotation works
[ ] Previous token is invalidated
[ ] Authentication events are auditable
```

## Database

```text
[ ] SQLite integrity check passes
[ ] Foreign-key check passes
[ ] WAL mode is active
[ ] Busy timeout is configured
[ ] Persistent volume is mounted
[ ] Backup exists
[ ] Backup integrity is verified
```

---

# 82. Final Troubleshooting Checklist

## Server

```text
[ ] Docker container running
[ ] Correct image deployed
[ ] Gunicorn running
[ ] lums-data mounted
[ ] Application bound to 127.0.0.1:5050
[ ] Nginx running
[ ] nginx -t successful
[ ] HTTP redirects to HTTPS
[ ] HTTPS reachable
[ ] TLS certificate valid
[ ] TLS configuration verified
[ ] Security headers present
[ ] SQLite integrity check successful
[ ] Foreign-key check successful
```

## Container Security

```text
[ ] User=lums
[ ] ReadonlyRootfs=true
[ ] CapDrop=ALL
[ ] Privileged=false
[ ] /tmp available
[ ] Persistent volume mounted
[ ] Secret mounted read-only
```

## Agent

```text
[ ] Agent version 1.7.0
[ ] HTTPS communication works
[ ] TLS verification enabled
[ ] Client token valid
[ ] Agent timer active
[ ] Inventory reporting works
[ ] Update detection works
[ ] Job retrieval works
[ ] Atomic job claiming works
[ ] Result reporting works
[ ] Idle detection works
```

## Execution

```text
[ ] Execution watcher active
[ ] Idle state evaluated correctly
[ ] Jobs transition correctly
[ ] Package operation starts
[ ] Timeout handling works
[ ] Result is reported
[ ] Recovery works
[ ] Abandoned jobs are distinguishable
```

## Package Manager

```text
[ ] Correct package manager detected
[ ] APT/dpkg works on Debian
[ ] pacman works on Arch
[ ] Package database is healthy
[ ] No conflicting package operation is active
[ ] Repository connectivity works
```

## Secrets and Git

```text
[ ] No passwords in Git
[ ] No client tokens in Git
[ ] No Flask/LUMS secret in Git
[ ] No TLS private key in Git
[ ] No production database in Git
[ ] No backup database in Git
[ ] Diagnostic output is redacted
```

---

# 83. Troubleshooting Lessons

## Lesson 1 — Find the failing layer

Do not reinstall the complete system before identifying the affected component.

```text
Browser
 ↓
TLS
 ↓
Nginx
 ↓
Docker
 ↓
Flask
 ↓
SQLite
 ↓
Agent
 ↓
Package Manager
 ↓
Job
```

---

## Lesson 2 — Container and volume are different

The container is replaceable.

The persistent volume contains application data.

```text
Container:
replaceable

Volume:
persistent
```

---

## Lesson 3 — Image and running container are different

Building:

```bash
docker build
```

does not automatically update an existing container.

After rebuilding, verify the image actually used by the running container.

---

## Lesson 4 — Authentication and authorization are different

```text
401
```

normally indicates an authentication problem.

```text
403
```

normally indicates an authorization problem.

Always identify the endpoint and exact response before changing credentials.

---

## Lesson 5 — Token digest and password hashing are different concepts

LUMS stores client authentication tokens as SHA-256 hexadecimal digests.

Administrative passwords use the application's password-hashing mechanism.

These are different mechanisms serving different purposes.

---

## Lesson 6 — Do not expose secrets while troubleshooting

Diagnostic output can later appear in:

```text
GitHub issues
documentation
screenshots
chat messages
support requests
```

Therefore diagnostic output should be treated as potentially public.

---

## Lesson 7 — Frontend changes require the complete deployment chain

Changing:

```text
CSS
JavaScript
HTML
```

does not automatically change the running application.

The complete chain is:

```text
Git source
   ↓
Docker build
   ↓
Docker image
   ↓
Container recreation
   ↓
Browser
```

---

## Lesson 8 — Theme bugs are not automatically backend bugs

If the API works but the interface looks wrong, investigate:

```text
CSS
JavaScript
DOM
localStorage
browser cache
```

before changing Flask.

---

## Lesson 9 — Preserve container hardening

A deployment is incomplete if the application works but the hardened runtime configuration has been lost.

Verify:

```text
Non-root
Read-only root filesystem
ALL capabilities dropped
Privileged=false
Protected secret mount
Localhost-only application binding
```

---

## Lesson 10 — Token rotation is a complete lifecycle

A rotation is not complete merely because a new token was generated.

The complete workflow is:

```text
Rotate
   ↓
Receive replacement
   ↓
Previous token invalid
   ↓
Update agent
   ↓
Authenticate
   ↓
Report
   ↓
Verify client online
```

---

## Lesson 11 — Package management is platform-specific

LUMS currently supports:

```text
APT / dpkg
pacman
```

Therefore:

```text
Debian
   ↓
APT / dpkg

Arch
   ↓
pacman
```

Do not diagnose every Linux client as though it were Debian.

---

## Lesson 12 — Idle detection is session-aware

LUMS uses:

```text
systemd-logind
loginctl
```

rather than the old:

```text
w -h
```

approach.

The current implementation considers relevant user sessions and their idle state.

---

# 84. Responsible Security Reporting

Security issues should be documented responsibly.

A useful report contains:

```text
Short description
Affected component
Reproduction steps
Expected behavior
Actual behavior
Potential impact
Suggested mitigation
Relevant redacted logs
```

Never include:

```text
Passwords
Client tokens
Private keys
LUMS secrets
Personal information
Complete production databases
Unredacted inventory data
```

Sensitive information must be removed before logs, screenshots, configuration files, or database excerpts are shared.

---

# 85. Security Maintenance

Security reviews should be repeated after changes to:

```text
Application
Authentication
Authorization
Docker
Nginx
TLS
Database schema
Agent
Package manager
Execution watcher
Deployment
Secrets
```

Regularly review:

```text
Operating system
Docker images
Python dependencies
Flask dependencies
Gunicorn
Nginx
TLS configuration
File permissions
Database backups
Git history
Authentication
Authorization
Job execution
Package-manager coordination
Container privileges
Container capabilities
Secret handling
Secret rotation
Agent configuration
systemd services
systemd timers
```

---

# 86. Security Change Workflow

Security-sensitive changes should follow a controlled workflow:

```text
Inspect
   ↓
Understand current behavior
   ↓
Design change
   ↓
Implement
   ↓
Syntax check
   ↓
Unit test
   ↓
Integration test
   ↓
Debian test
   ↓
Arch test
   ↓
Verify production configuration
   ↓
Deploy
   ↓
Verify production
   ↓
Document
```

A failed test should not be hidden by changing the documentation to match the failure.

The implementation, deployment, and documentation should describe the same verified state.

# 85. Job Recovery Decision Tree

When a job remains:

```text
running
```

longer than expected:

```text
                 Job still running
                         │
                         ▼
                Is the client online?
                    /          \
                  NO            YES
                  │              │
                  ▼              ▼
             Check recovery   Check agent
                              logs
                                │
                                ▼
                         Did agent submit
                         a final result?
                           /          \
                         YES           NO
                         │              │
                         ▼              ▼
                   Check result     Recovery
                   processing       required
```

Do not immediately delete the job.

First determine whether:

```text
execution
result submission
server processing
recovery
```

is the actual failing layer.

---

# 86. Frontend Recovery Decision Tree

When the frontend looks wrong:

```text
              Frontend problem
                     │
                     ▼
             Does API work?
                /       \
              NO         YES
              │           │
              ▼           ▼
         Backend      Is correct
         debugging    HTML loaded?
                          │
                          ▼
                     Is CSS loaded?
                          │
                          ▼
                    Is JS loaded?
                          │
                          ▼
                    Check theme
                          │
                          ▼
                    Check DOM
                          │
                          ▼
                  Check localStorage
                          │
                          ▼
                    Hard refresh
```

This prevents backend changes from being made for a browser-side problem.

---

# 87. Documentation Rule

When troubleshooting produces a verified result, document:

```text
Problem
    ↓
Observed behavior
    ↓
Affected layer
    ↓
Root cause
    ↓
Change
    ↓
Verification
```

Avoid documenting only:

```text
"Fixed."
```

A useful troubleshooting record should allow another administrator to understand why the change was made.

---

# 88. Final Principles

LUMS troubleshooting should follow:

```text
Observe
   ↓
Identify the layer
   ↓
Verify the assumption
   ↓
Change only what is necessary
   ↓
Test again
   ↓
Document the result
```

The most important rule remains:

> **Do not reinstall everything immediately. Find the layer where the problem occurs.**

A healthy LUMS installation is not defined by the absence of errors during installation.

It is defined by being able to determine:

```text
where a problem occurs,
why it occurs,
what component is responsible,
what changed,
and how the fix can be verified.
```

That is the purpose of this troubleshooting guide.

---

# 89. Current Architecture Summary

```text
                         ┌───────────────────┐
                         │      Browser      │
                         └─────────┬─────────┘
                                   │
                                HTTPS
                                   │
                         ┌─────────▼─────────┐
                         │       Nginx       │
                         └─────────┬─────────┘
                                   │
                            127.0.0.1:5050
                                   │
                         ┌─────────▼─────────┐
                         │   Docker / LUMS   │
                         │    Gunicorn :5000 │
                         └─────────┬─────────┘
                                   │
                         ┌─────────▼─────────┐
                         │      SQLite       │
                         │    lums-data      │
                         └───────────────────┘
                                   │
                         HTTPS + Bearer Token
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
             Debian 13 Client              Arch Linux Client
                    │                             │
             lums-agent 1.7.0              lums-agent 1.7.0
                    │                             │
               APT / dpkg                    pacman
                    │                             │
                    └──────────────┬──────────────┘
                                   │
                                Result
                                   │
                                   ▼
                                LUMS API
```

The server provides management and coordination.

The clients perform the actual package-management operations.

---

# 90. Current Security Roadmap Status

The current overall state is:

```text
[x] Non-root container
[x] UID 10001
[x] Drop ALL capabilities
[x] Privileged container disabled
[x] Read-only root filesystem
[x] tmpfs /tmp
[x] Localhost-only application binding
[x] Protected secret file
[x] Read-only secret mount
[x] Secret isolation
[x] Flask secret rotation
[x] Administrator authentication
[x] Client authentication
[x] Client token hashing
[x] Client token rotation
[x] Client token invalidation
[x] Token rotation audit logging
[x] CSRF protection for token rotation
[x] Job ownership validation
[x] Atomic job claiming
[x] Interrupted-job recovery
[x] Debian client communication
[x] Arch client communication
[x] APT support
[x] pacman support
[x] systemd-logind idle detection
[x] Gunicorn deployment
[x] HTTPS reverse proxy
[x] Security headers
[x] SQLite integrity verification
[x] SQLite-aware backup
[x] Backup integrity verification

[ ] Complete package-manager collision prevention
[ ] Full backup / restore test
[ ] Automated security regression tests
[ ] Final security review
```

The completed controls should not be interpreted as meaning that LUMS has no remaining security work.

Security hardening is continuous.

---

# 91. Security Verification Principles

LUMS follows several operational rules.

## Rule 1 — Do not trust configuration alone

A configuration file saying:

```text
read-only
```

is not sufficient.

The running container must be inspected.

---

## Rule 2 — Do not trust successful startup alone

A running container does not prove:

* authentication works,
* HTTPS works,
* database integrity is valid,
* clients can authenticate,
* update jobs work.

Each layer must be verified.

---

## Rule 3 — Do not trust a backup merely because it exists

A backup must be:

```text
created
   ↓
protected
   ↓
integrity checked
   ↓
eventually restored in isolation
```

---

## Rule 4 — Treat exposed secrets as compromised

A secret that was exposed must not be considered safe merely because it is no longer visible.

It must be rotated.

---

## Rule 5 — Authentication does not equal authorization

A valid client token only establishes client identity.

The server must still verify whether that client is authorized for the requested resource.

---

## Rule 6 — Package installation is privileged execution

Update jobs must be treated as privileged operations.

The system must control:

```text
who
what
where
when
result
```

---

## Rule 7 — Documentation follows verification

Documentation should describe the actual tested state.

If something is incomplete, it must be marked as incomplete.

---

# 92. Final Management Architecture

The final architecture separates the management plane from the execution plane.

```text
Management Plane
       │
       ├── Nginx
       ├── HTTPS
       ├── Gunicorn
       ├── Flask
       ├── Authentication
       ├── Authorization
       ├── Inventory
       ├── Job Management
       └── SQLite
```

from:

```text
Execution Plane
       │
       ├── lums-agent
       ├── systemd
       ├── Package Manager Abstraction
       ├── APT / dpkg
       └── pacman
```

The server manages the desired operation.

The client performs the actual package-management operation.

This separation reduces the need for the server to have direct operating-system privileges on managed clients.

---

# 93. Final Management / Execution Separation

The separation can be summarized as:

```text
                    LUMS Server
                         │
          ┌──────────────┴──────────────┐
          │                             │
     Management                     Persistence
          │                             │
     Nginx / HTTPS                  SQLite
          │                         lums-data
       Gunicorn
          │
        Flask
          │
     Authentication
          │
      Job Control
          │
          └──────────────┬──────────────┘
                         │
                    HTTPS + Token
                         │
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
      Debian 13                    Arch Linux
          │                             │
    lums-agent                     lums-agent
          │                             │
      APT / dpkg                    pacman
          │                             │
          └──────────────┬──────────────┘
                         │
                       Result
                         │
                         ▼
                    LUMS API
```

The management plane determines **what should happen**.

The execution plane determines **how the local operating system performs it**.

---

# 94. Final Security State

The current LUMS implementation has verified security controls across:

```text
Container
   ↓
Network
   ↓
TLS
   ↓
Authentication
   ↓
Authorization
   ↓
Secrets
   ↓
Tokens
   ↓
Jobs
   ↓
Recovery
   ↓
Agent
   ↓
Package Manager
   ↓
Database
   ↓
Backups
```

The remaining work is explicitly limited to the documented open hardening areas.

The project should not claim a final security review until those remaining areas have been tested.

---

# 95. Final Security Principles

The following principles apply to LUMS:

1. Never store secrets in Git.
2. Never expose the Flask/Gunicorn application directly to the network.
3. Use HTTPS for client communication.
4. Keep TLS verification enabled.
5. Separate authentication from authorization.
6. Validate client identity server-side.
7. Protect administrator credentials.
8. Protect client tokens.
9. Protect TLS private keys.
10. Protect the mounted Flask secret.
11. Keep database backups secure.
12. Verify backups rather than trusting file existence.
13. Do not remove persistent volumes during ordinary troubleshooting.
14. Do not automatically reboot clients.
15. Review changes before deployment.
16. Test security-sensitive changes.
17. Document incidents and configuration changes.
18. Do not claim incomplete security controls are fully implemented.
19. Keep update execution controlled and auditable.
20. Harden the container incrementally.
21. Treat secret isolation and secret rotation as separate controls.
22. Treat previously exposed secrets as compromised until rotated.
23. Rotate client tokens through the authenticated administrative workflow.
24. Verify replacement credentials before closing a credential change.
25. Keep production secrets outside Git and outside normal container environment variables where practical.
26. Use distribution-specific package-manager implementations behind a controlled abstraction.
27. Validate job ownership on the server.
28. Use atomic state transitions for job claiming and recovery.
29. Prefer conservative behavior when system state cannot be reliably determined.
30. Keep production documentation synchronized with verified implementation state.
31. Test recovery paths, not only successful paths.
32. Treat security hardening as a continuous process rather than a one-time configuration.

---

# 96. Final Principle

LUMS is designed to centralize Linux update management without removing operational control from the administrator.

The system should remain:

* Transparent
* Auditable
* Controlled
* Secure
* Documented
* Maintainable

The architecture deliberately separates:

```text
Management
     ↓
Coordination
     ↓
Execution
```

The server does not need to directly control the operating system of every client.

Instead:

```text
LUMS Server
     ↓
authorized job
     ↓
LUMS Agent
     ↓
local package manager
     ↓
result
     ↓
LUMS Server
```

This separation provides a clear troubleshooting boundary.

When something fails, identify the boundary first.

When something changes, verify the affected layer.

When something is fixed, document the verified result.

When something remains incomplete, document it as incomplete.

That is the operational principle behind the LUMS troubleshooting process.

---

# 97. Troubleshooting Guide Complete

This guide is intended to be used as an operational reference.

The recommended troubleshooting order is:

```text
1. Observe
2. Collect evidence
3. Identify the affected layer
4. Verify the assumption
5. Make the smallest necessary change
6. Test
7. Verify production behavior
8. Document the result
```

The most important diagnostic rule is:

> **Do not change everything at once.**

A controlled troubleshooting process makes it possible to determine:

```text
what failed,
where it failed,
why it failed,
what was changed,
and whether the change actually solved the problem.
```

**LUMS — Linux Update Management without the noise.**
