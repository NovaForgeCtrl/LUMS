# LUMS Troubleshooting

This guide provides troubleshooting procedures for the LUMS server, Linux agents, execution watcher, update jobs, authentication, package management, database, and Docker deployment.

The troubleshooting process should always begin with **observation before modification**.

The objective is to identify the first component where the expected behavior stops without unnecessarily changing configuration, database state, credentials, or security controls.

---

# 1. Troubleshooting Philosophy

LUMS consists of several independent components.

A successful client report does not automatically mean that update execution is working.

The main operational path is:

```text
Linux Client
    │
    ├── LUMS Agent
    │
    └── Execution Watcher
            │
            ▼
          HTTPS
            │
            ▼
        Nginx
            │
            ▼
        LUMS API
            │
            ▼
         SQLite
```

Update execution adds the package-management layer:

```text
Browser
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Update Job
   │
   ▼
Execution Watcher
   │
   ▼
LUMS Agent
   │
   ▼
APT / pacman
   │
   ▼
Result
   │
   ▼
LUMS API
   │
   ▼
SQLite
```

When troubleshooting, identify the **first failing component**.

For example:

```text
Agent report fails
    ↓
Check agent service
    ↓
Check network
    ↓
Check TLS
    ↓
Check client token
    ↓
Check LUMS API
```

Do not immediately:

* modify the database
* delete the Docker volume
* reinstall the Agent
* rotate credentials
* remove package-manager lock files
* disable security controls
* make the container privileged

These actions can destroy useful diagnostic information or create additional problems.

---

# 2. Diagnostic Baseline

Before investigating a specific problem, establish the current state of the main components.

The production LUMS deployment uses:

```text
Application port: 127.0.0.1:5050
External access: HTTPS through Nginx
Database: /var/lib/lums/lums.db
Docker volume: lums-data
Agent: 1.7.0
Watcher: 1.2.1
```

The production container is hardened with:

```text
Read-only root filesystem
No Linux capabilities
no-new-privileges
Non-root application user
Protected secret mount
Dedicated persistent data volume
```

The application port is intentionally bound only to the local host.

The expected network path is:

```text
Client / Browser
       │
       ▼
     HTTPS
       │
       ▼
    Nginx :443
       │
       ▼
127.0.0.1:5050
       │
       ▼
 Docker container
       │
       ▼
    LUMS :5000
```

---

# 3. First Diagnostic Checks

## 3.1 Check the LUMS Container

On the LUMS server:

```bash
sudo docker ps
```

The `lums` container should be running.

For a complete container overview:

```bash
sudo docker ps -a \
    --filter name=lums
```

Do not remove stopped containers before investigating them.

Older fallback containers may contain useful information when investigating a deployment problem.

---

## 3.2 Check Recent Application Logs

Inspect the most recent LUMS logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

For live output:

```bash
sudo docker logs \
    -f \
    lums
```

When investigating a specific request or job, start the log inspection before reproducing the problem where possible.

This makes it easier to correlate the client action with the corresponding server-side event.

---

## 3.3 Check Nginx

Check the reverse proxy:

```bash
sudo systemctl status nginx \
    --no-pager
```

Validate the configuration:

```bash
sudo nginx -t
```

A successful configuration test should report:

```text
syntax is ok
test is successful
```

If Nginx is not running, HTTPS access to LUMS will normally fail even when the Docker container itself is healthy.

---

## 3.4 Check the Agent

On a managed Linux client:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Inspect recent Agent output:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

For a `Type=oneshot` service, an inactive state after a successful execution can be normal.

The important information is the execution result.

A successful execution should end with:

```text
status=0/SUCCESS
```

---

## 3.5 Check the Execution Watcher

The watcher is a separate component from the reporting Agent.

Check it independently:

```bash
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Inspect recent output:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

A successful Agent report therefore does **not** prove that the execution watcher is functioning correctly.

---

## 3.6 Check LUMS Timers

Check all relevant timers:

```bash
sudo systemctl list-timers \
    --all | grep lums
```

The expected timers include the Agent and watcher scheduling mechanisms.

If a timer is missing or inactive, inspect the corresponding unit before changing anything.

---

# 4. LUMS Container Is Not Running

If the `lums` container is not running, do not immediately recreate it.

First inspect its state:

```bash
sudo docker ps -a \
    --filter name=lums
```

Then inspect the container:

```bash
sudo docker inspect lums
```

Check the recent logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Check the exit state:

```bash
sudo docker inspect \
    --format '{{.State.Status}} {{.State.ExitCode}}' \
    lums
```

The result may help distinguish between:

```text
Normal shutdown
Application failure
Configuration failure
Container runtime failure
Health/startup problem
```

If the container exited unexpectedly, preserve the logs and container state before replacing it.

---

# 5. Container Starts but LUMS Is Not Reachable

The LUMS application is not intended to be accessed directly through the Docker application port from the network.

The production application is bound to:

```text
127.0.0.1:5050
```

Verify the port binding:

```bash
sudo docker port lums
```

Also check the host listeners:

```bash
sudo ss -lntp | grep -E ':443|:5050'
```

The expected architecture is:

```text
HTTPS :443
    │
    ▼
  Nginx
    │
    ▼
127.0.0.1:5050
    │
    ▼
Docker
    │
    ▼
LUMS :5000
```

If the container is running but HTTPS fails, investigate the layers individually:

1. Docker container
2. Local application port
3. Nginx configuration
4. TLS
5. Firewall/network path

Do not expose port `5050` publicly as a troubleshooting shortcut.

---

# 6. Nginx Returns an Error

Check the service:

```bash
sudo systemctl status nginx \
    --no-pager
```

Validate the configuration:

```bash
sudo nginx -t
```

Inspect recent Nginx messages:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Then verify that the LUMS container is actually running:

```bash
sudo docker ps
```

A reverse-proxy error does not automatically mean that the LUMS application itself is broken.

Possible failure locations include:

```text
Browser
   ↓
TLS
   ↓
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker
   ↓
LUMS
```

Test the layers separately rather than changing several components at once.

---

# 7. HTTPS / TLS Problems

First test the HTTPS endpoint:

```bash
curl -I https://LUMS-SERVER/
```

If certificate verification fails, determine whether the problem is:

```text
Certificate
Certificate chain
Hostname
Trust store
Nginx configuration
Client CA configuration
```

Validate Nginx:

```bash
sudo nginx -t
```

If the certificate or TLS configuration was intentionally changed, reload Nginx:

```bash
sudo systemctl reload nginx
```

Then test again:

```bash
curl -I https://LUMS-SERVER/
```

Clients using a private certificate authority must trust the appropriate CA certificate.

Do not disable TLS certificate verification as a permanent workaround.

A successful connectivity test that bypasses certificate validation does not prove that the production TLS configuration is correct.

---

# 8. Agent Service Fails

Check the service:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Read the recent journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Start the service again only after inspecting the previous result:

```bash
sudo systemctl start \
    lums-agent.service
```

Then check:

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

Look for:

```text
Configuration errors
Missing environment values
TLS errors
Authentication failures
API errors
Python exceptions
Package-manager errors
```

Do not reinstall the Agent simply because a single execution failed.

---

# 9. Agent Reports `LUMS_TOKEN` Missing

The Agent normally receives its production configuration through its systemd service environment.

If the Agent is started manually from a shell, the systemd `EnvironmentFile` is not automatically loaded into that shell.

Therefore:

```bash
sudo /opt/lums-agent/agent.py --version
```

may behave differently from:

```bash
sudo systemctl start \
    lums-agent.service
```

when the token is supplied exclusively through systemd configuration.

When investigating authentication problems, test the actual service first:

```bash
sudo systemctl start \
    lums-agent.service
```

Then inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Do not copy production tokens into shell commands unnecessarily.

Never print a production token into a diagnostic log.

---

# 10. Agent Cannot Reach the Server

Start with network connectivity:

```bash
ping LUMS-SERVER
```

Then test HTTPS:

```bash
curl -I https://LUMS-SERVER/
```

If HTTPS works but the Agent still fails, investigate:

```text
Client configuration
Client token
TLS trust
API response
Client identity
Agent version
```

Inspect the Agent:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

At the same time, inspect the server:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

This helps determine whether the request reaches LUMS at all.

If the client sees a connection failure and the server shows no corresponding request, investigate the network or TLS path before changing application configuration.

---

# 11. Continue Troubleshooting

If the basic server, Docker, Nginx, TLS, and Agent layers are working, continue with:

```text
Client Authentication
Token Rotation
Update Detection
Execution Watcher
Idle Detection
Pending Jobs
```

The next section continues with client authentication and token-related problems.

# 12. Client Authentication

LUMS uses client-specific authentication for Agent communication.

When a client is registered, the client receives credentials that are used for authenticated communication with the LUMS server.

Authentication failures should be investigated without exposing the client token.

---

## 12.1 Client Is Not Accepted by LUMS

If an Agent reports an authentication failure, first inspect the Agent log:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Then inspect the LUMS container logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Look for:

```text
401 Unauthorized
403 Forbidden
Invalid client token
Unknown client
Authentication failure
```

A `401` response generally indicates an authentication problem.

A `403` response may indicate that authentication succeeded but the requested operation is not permitted.

Do not immediately rotate the token.

First determine whether the problem is:

```text
Wrong token
Wrong client ID
Disabled client
Incorrect server URL
TLS problem
Malformed request
Server-side authentication failure
```

---

## 12.2 Client Exists but Authentication Fails

Verify that the client still exists in the LUMS administration interface.

Do not modify the client record solely because an Agent request failed.

If the client exists, compare the configured client identity with the identity used by the Agent.

The production token itself must never be printed into diagnostic output.

Use configuration metadata and service status for troubleshooting instead of exposing credentials.

---

# 13. Client Token Rotation

Client token rotation invalidates the previous token and replaces it with a new credential.

If a token was intentionally rotated, the affected Agent must receive the new token before it can authenticate again.

The expected sequence is:

```text
Administrator
    │
    ▼
Rotate client token
    │
    ▼
Old token becomes invalid
    │
    ▼
New token assigned to client
    │
    ▼
Agent configuration updated
    │
    ▼
Agent reports again
```

If the Agent continues using the old token, authentication will fail.

---

## 13.1 After Token Rotation

Check the Agent service:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Then run the Agent through systemd:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspect the result:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

If authentication still fails, inspect the server logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Do not rotate the token repeatedly.

Repeated rotation can make it harder to determine which credential is currently deployed on the client.

---

# 14. Client Is Disabled

A disabled client must not be treated as an active managed client.

If an Agent belonging to a disabled client attempts communication, inspect the server-side authentication result.

Check:

```text
Client identity
Client enabled state
Authentication result
Agent configuration
```

Do not re-enable the client merely to make an error disappear.

Determine why the client was disabled first.

---

# 15. Update Detection

Update detection consists of several independent steps.

The Agent must:

1. execute the package-manager query
2. parse the result
3. send the result to LUMS
4. LUMS must validate the result
5. LUMS must persist the result
6. the UI must display the current state

A failure in any step can make update information appear incorrect.

The basic flow is:

```text
APT / pacman
     │
     ▼
Agent
     │
     ▼
HTTPS
     │
     ▼
LUMS API
     │
     ▼
SQLite
     │
     ▼
Web UI
```

---

## 15.1 No Updates Are Displayed

First determine whether the client actually reported successfully.

Check:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Then inspect the server:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

If the Agent completed successfully but no updates are displayed, investigate the API and database state before changing the package manager.

---

## 15.2 Debian / Ubuntu Update Detection

The Debian package manager uses APT.

When investigating APT-related problems, first verify that APT itself is functioning:

```bash
sudo apt update
```

Do not automatically run package upgrades during troubleshooting.

The purpose of this test is to determine whether repository metadata can be refreshed successfully.

If APT reports repository, DNS, TLS, signature, or lock errors, resolve the underlying APT problem before investigating LUMS.

---

## 15.3 Arch Linux Update Detection

Arch Linux uses `pacman`.

Check repository metadata:

```bash
sudo pacman -Sy
```

Use this only when repository metadata refresh is actually required for the diagnostic.

Do not combine an unnecessary system upgrade with a diagnostic test.

For package-related errors, inspect the exact `pacman` output before changing configuration.

---

# 16. Available Updates Differ Between LUMS and the Client

Update information can change between two observations.

For example:

```text
Client reports updates
        ↓
Repository metadata changes
        ↓
Package is upgraded manually
        ↓
LUMS displays older information
```

Therefore, always consider the timestamp of the last successful client report.

A difference does not automatically indicate a database problem.

Check:

```text
Last Agent execution
Last successful report
Package-manager state
Repository metadata
Displayed update state
```

---

# 17. Package Management

LUMS package management is separate from the installed-package filter shown on the client page.

The package-management workflow is:

```text
User
 │
 ▼
Package Search
 │
 ▼
LUMS API
 │
 ▼
Agent
 │
 ▼
APT / pacman
 │
 ▼
Search Result
 │
 ▼
LUMS API
 │
 ▼
Web UI
```

Installing, removing, or updating a package uses the normal LUMS job mechanism.

The expected execution path is:

```text
Package Action
     │
     ▼
Update Job
     │
     ▼
Execution Watcher
     │
     ▼
Agent
     │
     ▼
APT / pacman
```

---

## 17.1 Package Search Returns No Results

First verify that the Agent is operational:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Then inspect the Agent journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

For Debian-based clients, verify APT metadata.

For Arch-based clients, verify pacman repository metadata.

Do not assume that an empty search result means the LUMS database is empty.

The search is performed through the client package manager.

---

## 17.2 Package Search Works but Installation Fails

A successful search only proves that the package manager could locate the package.

It does not prove that installation will succeed.

Possible causes include:

```text
Dependency conflicts
Repository changes
Package no longer available
Insufficient privileges
Package-manager lock
Disk-space problems
Network problems
Package-manager errors
```

Inspect the corresponding update job.

The Agent journal should contain the package-manager result.

---

# 18. Package Installation Jobs

Package installation uses the normal update-job infrastructure.

The relevant action is:

```text
INSTALL_PACKAGE
```

When troubleshooting an installation:

1. Check the job state in LUMS.
2. Check the Agent execution.
3. Check the package-manager output.
4. Check the final result reported to LUMS.

Do not manually modify the job status in SQLite.

The expected lifecycle is:

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

A failed package installation should remain traceable through the normal job and audit mechanisms.

---

# 19. Package Removal Jobs

Package removal follows the same job lifecycle.

The action is:

```text
REMOVE_PACKAGE
```

When a removal fails, inspect:

```text
Update job
Agent journal
Package-manager output
Final job result
```

Do not manually remove database records to hide a failed package operation.

A failed job is useful diagnostic information.

---

# 20. Package Update Jobs

A package-specific update uses:

```text
UPDATE_PACKAGE
```

The package must be known to LUMS as having an available update before the job is created.

If the UI does not offer the expected package update:

1. refresh update information
2. verify the package manager state
3. verify the available-update result
4. inspect the server logs if the state is inconsistent

Do not manually insert update records into SQLite.

---

# 21. System Update Jobs

A complete system update uses:

```text
UPDATE_SYSTEM
```

This is different from:

```text
UPDATE_PACKAGE
```

The system update may affect multiple packages and may require a reboot depending on the operating system and resulting package state.

When troubleshooting a system update, determine whether the failure occurred during:

```text
Update preparation
Package-manager execution
Result collection
Reboot detection
Post-reboot reporting
```

---

# 22. Package Manager Locks

Package managers may refuse an operation when another package-management process is already running.

Typical examples include:

```text
APT is already running
dpkg is locked
pacman is locked
```

First identify the process holding the lock.

Do not blindly delete lock files.

A lock file may indicate that another package-management process is legitimately active.

Removing it while a package operation is running can damage the package-management state.

The correct troubleshooting sequence is:

```text
Lock error
   ↓
Identify active process
   ↓
Determine whether it is legitimate
   ↓
Wait or resolve the process safely
   ↓
Retry operation
```

---

# 23. Package Manager Failure vs. LUMS Failure

Always distinguish between a package-manager failure and an LUMS failure.

For example:

```text
APT fails
    ↓
Agent reports APT failure
    ↓
LUMS stores FAILED result
```

In this case LUMS may be functioning correctly even though the job failed.

Conversely:

```text
APT succeeds
    ↓
Agent cannot report result
    ↓
LUMS never receives SUCCESS
```

Here the package operation may have succeeded while the LUMS reporting path failed.

The package-manager result and the LUMS job result must therefore be investigated separately.

---

# 24. Useful Diagnostic Separation

When a package job fails, classify the failure first:

```text
A. Package-manager failure
B. Agent execution failure
C. Agent reporting failure
D. Server/API failure
E. Database persistence failure
F. UI display problem
```

This classification prevents unrelated components from being modified.

A package-manager error should not automatically result in a Docker rebuild.

A UI display problem should not automatically result in deleting the database.

An authentication failure should not automatically result in reinstalling the Agent.

---

# 25. Next Troubleshooting Area

If client authentication, update detection, and package management are functioning, the next diagnostic area is the execution lifecycle itself:

```text
Update Job
    ↓
Watcher
    ↓
Agent
    ↓
Execution
    ↓
Result
    ↓
Checkpoint / Recovery
    ↓
Final Job State
```

The next section covers **Execution Watcher, Idle Detection, Job State, Recovery, and reboot handling**.

# 26. Update Job Execution

LUMS update jobs are executed asynchronously through the Agent and Execution Watcher.

The normal execution path is:

```text
User
 │
 ▼
LUMS API
 │
 ▼
SQLite
 │
 ▼
Pending Job
 │
 ▼
Execution Watcher
 │
 ▼
Agent
 │
 ▼
Package Manager
 │
 ▼
Result
 │
 ▼
LUMS API
 │
 ▼
SQLite
```

A job that is visible in the UI is not necessarily already being executed.

Always determine the current job state first.

---

## 26.1 Job Is Stuck in `PENDING`

If a job remains in `PENDING`, check the Execution Watcher before investigating the Agent.

Check the watcher:

```bash id="wq5h3v"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Inspect recent watcher output:

```bash id="8y0v7e"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Then check the Agent:

```bash id="j8x4qm"
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

A pending job normally indicates that the execution stage has not yet started.

Possible causes include:

```text
Watcher is not running
Watcher timer is not running
Client is offline
Client is not idle
Client has not reported recently
Job is not eligible for execution yet
```

Do not manually change the job state in SQLite.

---

# 27. Job Is Stuck in `RUNNING`

A `RUNNING` job indicates that execution has started.

First determine whether the Agent is actually executing the job.

Check:

```bash id="s2z5ek"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Then inspect the watcher:

```bash id="x4f6cb"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

A running job may take some time depending on:

```text
Package count
Repository speed
Network latency
Package-manager operations
System load
Reboot requirements
```

Do not terminate an active package operation solely because the UI has not updated yet.

First determine whether the underlying process is still active.

---

# 28. Job Is `FAILED`

A failed job does not necessarily indicate a LUMS server failure.

Determine which layer produced the failure.

Inspect:

```text id="5t9b83"
Job state
Agent execution result
Package-manager result
Server logs
Agent logs
```

The main categories are:

```text
Package-manager failure
Agent execution failure
Agent reporting failure
Server/API failure
Authentication failure
Recovery failure
```

The original error should be preserved whenever possible.

Do not replace a failed job with a manually created successful record.

---

# 29. Job Is `SUCCESS` but the Package Was Not Changed

A successful LUMS job means that the requested operation completed according to the Agent result.

If the expected package state does not match the job result, verify the client directly.

For Debian-based systems:

```bash id="gqdbm7"
dpkg-query -W \
    -f='${Package} ${Version}\n' \
    PACKAGE_NAME
```

For Arch Linux:

```bash id="2x9f7v"
pacman -Q \
    PACKAGE_NAME
```

Replace `PACKAGE_NAME` with the package being investigated.

Then compare the local package state with the LUMS result.

Possible explanations include:

```text
Package was changed after the job
Package name refers to a virtual/provided package
Package-manager output was interpreted differently than expected
The job result was generated before another local change
```

Do not modify the LUMS database until the discrepancy has been identified.

---

# 30. Execution Watcher

The Execution Watcher is responsible for discovering jobs that are eligible for execution.

The watcher must be treated as an independent component.

Check its service:

```bash id="w5m0c8"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Check its timer:

```bash id="3v1x7r"
sudo systemctl list-timers \
    --all | grep lums
```

Inspect its journal:

```bash id="d5m0xk"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

If the Agent works but jobs never start, the watcher should be one of the first components investigated.

---

# 31. Watcher Runs but Does Not Execute Jobs

A watcher execution does not automatically mean that a job will be started.

The job must satisfy the execution conditions.

Check:

```text id="m7p2zq"
Client exists
Client is enabled
Client is reachable
Client has recent status
Client is eligible
Job is pending
Job is not already completed
Execution conditions are satisfied
```

If the client is not eligible, the watcher may correctly leave the job pending.

This is not necessarily an error.

---

# 32. Idle Detection

LUMS can use client idle information when deciding whether a job should be executed.

The purpose is to avoid starting maintenance operations while the client is actively being used.

The idle decision should therefore be treated as a scheduling condition, not as an execution failure.

A client may report successfully while still being considered non-idle.

The troubleshooting sequence is:

```text
Agent reports
     ↓
Idle information available?
     ↓
Idle state acceptable?
     ↓
Job eligible?
     ↓
Watcher executes
```

---

## 32.1 Client Reports but Is Not Considered Idle

Check the Agent journal:

```bash id="5r2q1k"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Look for the reported idle information.

Then inspect the watcher:

```bash id="2a6v8m"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

The important distinction is:

```text
Agent communication successful
```

versus:

```text
Client eligible for maintenance execution
```

These are separate states.

---

# 33. Idle Detection Is Unavailable

Some systems may not provide all idle-state information.

An unavailable idle mechanism should not automatically be interpreted as a broken Agent.

Determine the reported capability first.

The relevant concepts are:

```text
Idle supported
Idle source
Idle state
Idle duration
```

If the platform cannot provide the expected idle information, investigate the Agent's platform-specific implementation rather than modifying the server database.

---

# 34. Update Job Recovery

LUMS uses checkpointing and recovery to prevent interrupted update jobs from being treated as completed.

A job may be interrupted because of:

```text
Agent restart
Client reboot
Network interruption
Package-manager interruption
Server restart
Watcher restart
System failure
```

Recovery must distinguish between work that was already completed and work that still needs execution.

The principle is:

```text
Completed work remains completed.
Incomplete work remains recoverable.
```

---

# 35. Interrupted Job

If a job was interrupted, first inspect its state.

Then inspect the Agent:

```bash id="3u8d4k"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Inspect the watcher:

```bash id="w4x1b9"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Do not manually mark the job as successful.

The recovery mechanism should determine which package items were already completed.

---

# 36. Recovery Repeats a Package Operation

When recovery is triggered, already successful package items should not be executed again unnecessarily.

The recovery model is based on item-level state.

Conceptually:

```text
Job
 ├── Package A → SUCCESS
 ├── Package B → SUCCESS
 ├── Package C → FAILED
 └── Package D → PENDING
```

Recovery should preserve the successful items and continue with the remaining work.

If this behavior appears incorrect, inspect the job and package-item history before changing the database.

---

# 37. Client Reboots During an Update

A reboot can interrupt the Agent process.

The expected recovery path is:

```text
Update starts
    ↓
Package operation
    ↓
Client reboot
    ↓
Agent starts again
    ↓
State is reported
    ↓
LUMS evaluates recovery
```

A reboot therefore does not automatically mean that the job failed permanently.

Inspect the Agent service after the client returns:

```bash id="jjh3u8"
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Then inspect recent executions:

```bash id="h7y5gk"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

---

# 38. Reboot Detection

Reboot detection is used to determine whether a system reboot occurred as part of an update operation.

This is particularly relevant when an update changes packages that require a restart or reboot.

For Arch Linux, reboot detection must not be confused with the package-manager exit status.

A package operation may succeed while the system still requires a reboot.

When troubleshooting reboot handling, compare:

```text
Package operation result
Reboot requirement
Actual reboot state
Post-reboot Agent report
Final LUMS job state
```

---

# 39. Job Result Was Not Reported

If the package operation appears to have completed but LUMS does not show the final result, investigate the reporting path.

Check the Agent:

```bash id="t0r8kf"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Then check the server:

```bash id="h5n1xv"
sudo docker logs \
    --tail 200 \
    lums
```

If the Agent reports an error while the package operation itself succeeded, classify the problem as a reporting failure rather than a package-management failure.

---

# 40. Server Restart During Job Execution

A server restart must not automatically be treated as proof that an update operation failed.

The job state must be evaluated after the server becomes available again.

Check:

```text id="j4t7yw"
Container state
Database availability
Job state
Client state
Agent report
Watcher state
```

The recovery mechanism is responsible for determining whether interrupted work can safely continue.

Do not manually rewrite job states after a server restart.

---

# 41. Database Is Available but Job State Looks Wrong

If SQLite is accessible but the job state appears inconsistent, inspect the application and audit logs before modifying the database.

Useful information includes:

```text
Job ID
Client ID
Job action
Job creation time
Current state
Package-item states
Agent result
Recovery events
Audit events
```

The database is an application data store, not a manual repair interface.

Direct modifications can bypass validation, authorization, auditing, and recovery logic.

---

# 42. Manual Job-State Changes

Manual SQL changes to update-job state should not be used as normal troubleshooting.

Avoid operations such as:

```sql id="8hbyqv"
UPDATE update_jobs ...
```

or:

```sql id="n1h7yr"
DELETE FROM update_jobs ...
```

unless a controlled database-recovery procedure explicitly requires them.

If a database-level repair is genuinely necessary, preserve a backup and document the exact change before applying it.

Normal operational problems should be resolved through the application and Agent mechanisms.

---

# 43. Watcher and Agent Diagnostic Matrix

Use the following matrix to identify the most likely layer:

| Symptom                                           | First component to inspect |
| ------------------------------------------------- | -------------------------- |
| Client cannot authenticate                        | Agent + LUMS API           |
| Client reports successfully but job stays pending | Execution Watcher          |
| Job becomes running but does not finish           | Agent + package manager    |
| Package operation fails                           | Package manager            |
| Package operation succeeds but result is missing  | Agent reporting            |
| Client rebooted during update                     | Agent + recovery           |
| Job remains inconsistent after restart            | Recovery + database state  |
| Job is never discovered                           | Watcher + timer            |
| Client is not eligible                            | Idle / client state        |
| UI shows outdated state                           | API + latest client report |

This matrix is a starting point, not a substitute for inspecting the actual logs and job state.

---

# 44. Next Troubleshooting Area

After verifying job execution, the next areas are:

```text
SQLite and database state
RBAC and user management
Authentication sessions
Application and audit logging
Container security
Tests and CI
```

These areas should be investigated separately from package execution.

# 45. SQLite and Database Troubleshooting

LUMS uses SQLite as its application database.

The production database is stored inside the persistent Docker volume:

```text id="9c6w3e"
/var/lib/lums/lums.db
```

The database is application-managed and must not normally be modified manually.

When investigating database-related problems, first determine whether the problem is:

```text id="4k4z1m"
Database availability
Database locking
Application configuration
Data consistency
Migration state
Application logic
```

---

# 46. Database Is Not Available

If LUMS reports a database error, first check whether the container is running:

```bash id="0l5q6h"
sudo docker ps
```

Then inspect the application logs:

```bash id="6j5p8m"
sudo docker logs \
    --tail 200 \
    lums
```

Do not immediately delete the Docker volume.

The persistent volume contains the production application data.

Deleting it can permanently remove:

```text id="4bq9rj"
Users
Clients
Client configuration
Update jobs
Audit data
Application state
```

---

# 47. SQLite Database Locking

SQLite locking problems should be investigated through the application logs.

Inspect:

```bash id="l8f6vk"
sudo docker logs \
    --tail 200 \
    lums
```

The production application uses:

```text id="2d3m8x"
journal_mode = delete
busy_timeout = 5000
synchronous = 2
```

The application also enables SQLite foreign-key enforcement on its database connections.

A database lock does not automatically mean that the database is corrupted.

Possible causes include:

```text id="9w4qcz"
Concurrent writes
Long-running transaction
Application process still using the database
Unexpected process termination
Filesystem problem
```

Do not delete SQLite journal files manually.

---

# 48. SQLite Foreign Keys

LUMS explicitly enables SQLite foreign-key enforcement at the application level.

This means that relationships between database records are validated by SQLite when the application connection is established.

If a foreign-key-related error occurs, inspect the application logs first.

Do not disable foreign-key enforcement to make an operation succeed.

A foreign-key failure can indicate an application logic or data-integrity problem.

---

# 49. SQLite Database Integrity

If database corruption is suspected, stop making unnecessary changes first.

Preserve the current state and inspect the application logs.

A controlled integrity check may be performed against a copy of the database.

Do not perform destructive repair operations directly against the production database unless a documented recovery procedure requires it.

The general principle is:

```text id="t4d1km"
Preserve
   ↓
Inspect
   ↓
Verify
   ↓
Recover
   ↓
Validate
```

Never start with:

```text id="z1f6rw"
Delete database
Recreate database
Recreate Docker volume
```

---

# 50. Database Migrations

LUMS uses application migrations to introduce database schema changes.

When a migration problem occurs, inspect the container logs:

```bash id="x4h9vf"
sudo docker logs \
    --tail 200 \
    lums
```

Look for:

```text id="m2x7kc"
Migration failure
SQL error
Duplicate column
Missing table
Constraint error
Migration already applied
```

Do not manually edit migration records unless the migration system specifically requires a controlled recovery procedure.

A migration that has already been applied should not normally be executed manually again.

---

# 51. Database Volume

The LUMS database is stored in the persistent Docker volume:

```text id="p6m3jw"
lums-data
```

Inspect the volume:

```bash id="v4c7yq"
sudo docker volume inspect \
    lums-data
```

The volume must remain persistent across normal container recreation.

The application container itself is disposable.

The application data is not.

Therefore:

```text id="z9f4ws"
Container
    ≠
Persistent database
```

Recreating the container must not be confused with recreating the data volume.

---

# 52. Database Disk Space

SQLite requires available filesystem space for normal operation.

Check the host filesystem:

```bash id="j6k1pt"
df -h
```

Also check inode availability:

```bash id="q2c5ra"
df -i
```

Low disk space can produce database errors that initially look like application problems.

If the database suddenly becomes read-only or writes begin failing, verify filesystem capacity before modifying SQLite configuration.

---

# 53. RBAC Troubleshooting

LUMS uses role-based access control.

The current roles are:

```text id="k8w5j2"
Administrator
Operator
Viewer
```

The permissions are intentionally different.

---

## 53.1 Administrator

Administrators can:

```text id="n4x7pa"
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

Administrator-only operations include user management and role administration.

---

## 53.2 Operator

Operators can:

```text id="b7c2mz"
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
```

Operators cannot:

```text id="q8v3kd"
Manage users
Manage roles
Create or disable clients
Rotate client tokens
```

---

## 53.3 Viewer

Viewers have deliberately restricted access.

A Viewer can:

```text id="y5m2rx"
View clients
View installed software
```

The following functionality is hidden from the Viewer interface and blocked server-side:

```text id="e8c4nw"
Available Updates
Update Jobs
Update History
Package Management
System Maintenance
```

This is an intentional security control.

If a Viewer can access one of these functions, treat the problem as an RBAC issue rather than simply a UI issue.

---

# 54. Viewer Sees Too Much

If a Viewer sees functionality that should not be available, check both layers:

```text id="x5j3mq"
Browser UI
    +
Server-side authorization
```

Hiding an element in JavaScript or HTML is not sufficient security.

The API must also reject unauthorized operations.

When investigating:

1. Determine the authenticated user's role.
2. Identify the affected endpoint.
3. Check the server response.
4. Inspect the application logs if necessary.
5. Verify the relevant RBAC test.

Do not solve an authorization problem by only hiding the UI element.

---

# 55. Viewer Cannot See Expected Data

A Viewer should still be able to access the information explicitly permitted by the current RBAC model.

If permitted client information is missing:

```text id="3h6q8f"
Verify login
   ↓
Verify role
   ↓
Verify client visibility
   ↓
Inspect API response
   ↓
Inspect browser console if necessary
```

Do not grant additional permissions merely because a page currently appears incomplete.

Determine whether the missing information is intentionally restricted first.

---

# 56. Operator Cannot Perform an Operation

If an Operator receives `403 Forbidden`, first determine whether the requested action is Administrator-only.

Operator access does not include:

```text id="n5y7cu"
User management
Role administration
Client creation/deactivation
Client token rotation
```

If the operation should be allowed for Operators, inspect the endpoint's authorization decorator and corresponding RBAC tests.

Do not temporarily promote the user to Administrator as a diagnostic shortcut.

---

# 57. Administrator Cannot Perform an Operation

An Administrator should have access to all currently supported administrative operations.

If an Administrator receives an authorization error:

```text id="q7d2nv"
Verify authenticated session
        ↓
Verify current role
        ↓
Verify endpoint authorization
        ↓
Inspect CSRF requirements
        ↓
Inspect application logs
```

For state-changing operations, a valid session alone may not be sufficient.

CSRF protection must also be satisfied where required.

---

# 58. User Management

User management is restricted to Administrators.

The user-management workflow is:

```text id="x4j6pw"
Administrator
    │
    ▼
User Management
    │
    ├── Create user
    ├── Assign role
    └── Enable / disable user
```

When a user cannot be created, check:

```text id="b3q9fz"
Current role
Username validation
Role validation
Duplicate username
Password validation
CSRF protection
Application logs
```

Do not create users directly in SQLite.

Direct database insertion bypasses password hashing, validation, authorization, and audit logging.

---

# 59. User Creation Fails

If user creation fails, inspect the browser response and server logs.

The API should validate:

```text id="7x3m5n"
Username
Role
Password requirements
Duplicate account
Authenticated administrator
CSRF token
```

If the request is rejected, determine which validation rule was triggered.

Do not weaken validation merely to make one account creation request succeed.

---

# 60. Password Problems

LUMS stores user passwords using a password-hashing mechanism rather than plaintext passwords.

If a user cannot log in:

```text id="9w3r5b"
Verify username
   ↓
Verify account enabled state
   ↓
Verify password
   ↓
Check login rate limiting
   ↓
Inspect authentication logs
```

Never store or log plaintext passwords.

Do not copy passwords into diagnostic commands or log files.

---

# 61. Disabled User Account

A disabled account must not be treated as an active login account.

If a disabled user can still authenticate, investigate:

```text id="z6t2hx"
Current account state
Authentication lookup
Session state
Session revocation
Browser session
Server-side authorization
```

Do not simply delete the account.

Preserving the account can be important for audit history.

---

# 62. Session Problems

LUMS uses server-side session handling.

When a user appears to have stale or unexpected access, first log out and establish a fresh session.

If the problem persists, investigate:

```text id="q1y7vm"
Account state
Role
Session state
Session revocation
Cookie configuration
CSRF protection
```

Do not disable session security controls to bypass a login problem.

---

# 63. Session Revocation

Session revocation is relevant when:

```text id="4n8z7p"
A password changes
A user is disabled
A role changes
A session must be invalidated
A security event requires forced logout
```

If a user appears to retain access after an account change, determine whether the existing session was correctly invalidated.

Test with a fresh browser session only after confirming the account state.

Do not assume that deleting browser cookies alone proves that server-side session revocation works.

---

# 64. Login Rate Limiting

LUMS applies login rate limiting to repeated failed authentication attempts.

The current behavior uses increasing lockout intervals:

```text id="p7k4xz"
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

The failure state is persisted in SQLite.

If login attempts are unexpectedly blocked, inspect the authentication state before changing the database.

A rate-limit response is not automatically an authentication failure.

It may indicate that the account has reached the configured failed-attempt threshold.

---

# 65. Login Works but API Returns `403`

A successful login proves authentication, not authorization.

A `403 Forbidden` response may indicate:

```text id="m9c2vx"
Insufficient role
Missing CSRF protection
Disallowed operation
Disabled functionality
```

Identify the exact endpoint before changing anything.

The correct troubleshooting question is:

```text id="0q4g1k"
"Is this user authenticated?"
```

followed by:

```text id="x8v5md"
"Is this authenticated user authorized for this operation?"
```

These are separate security checks.

---

# 66. CSRF Errors

State-changing browser requests are protected against cross-site request forgery.

If a state-changing request fails unexpectedly:

```text id="6z4qpn"
Verify authenticated session
        ↓
Verify CSRF token
        ↓
Verify request method
        ↓
Verify endpoint
        ↓
Inspect server response
```

Do not disable CSRF protection as a troubleshooting workaround.

A failed CSRF check is a security control working as intended.

---

# 67. Browser UI and API Disagree

If the UI shows that an action is available but the API rejects it:

```text id="v8n3ty"
Browser UI
   ↓
Displayed role/state
   ↓
API request
   ↓
Server-side authorization
```

The server-side result is authoritative.

The UI may contain stale state after:

```text id="4g7m2x"
Role changes
Session changes
Client changes
Page remains open for a long time
```

Reload the page and establish a fresh session before assuming that the server-side authorization is incorrect.

---

# 68. RBAC Diagnostic Matrix

| Symptom                         | First component to inspect              |
| ------------------------------- | --------------------------------------- |
| Viewer sees management UI       | Client page role handling               |
| Viewer API request succeeds     | Server-side RBAC                        |
| Operator receives `403`         | Endpoint permission model               |
| Administrator receives `403`    | Session / CSRF / endpoint authorization |
| User cannot be created          | Admin role + validation                 |
| Disabled user can log in        | Account state + session handling        |
| Login temporarily blocked       | Rate limiting                           |
| State-changing request rejected | CSRF / session                          |
| UI and API disagree             | Browser state + server authorization    |

The server-side authorization result is always more important than whether an interface element is visible.

---

# 69. Next Troubleshooting Area

The next diagnostic areas are:

```text id="8r5w2q"
Application and audit logging
Container security
Filesystem permissions
Docker runtime configuration
Tests and CI
Diagnostic snapshots
Final recovery checklist
```

These areas should be investigated without weakening the security baseline.

# 70. Application Logging

LUMS uses application logging to provide diagnostic information without exposing sensitive credentials.

When investigating an application problem, start with the most recent logs:

```bash id="f6m2qa"
sudo docker logs \
    --tail 200 \
    lums
```

For continuous monitoring:

```bash id="x3v8kp"
sudo docker logs \
    -f \
    lums
```

When possible, reproduce the problem while monitoring the logs.

This makes it easier to correlate:

```text id="p8k4zw"
User action
    ↓
HTTP request
    ↓
Application event
    ↓
Database operation
    ↓
Agent interaction
```

---

# 71. Application Logs Contain an Error

First identify the component that produced the message.

Typical sources include:

```text id="w4c8rn"
Flask application
Gunicorn
Database layer
Authentication
Authorization
Package management
Job execution
Client reporting
```

Do not assume that the last log message is the root cause.

Look for the first relevant error in the event sequence.

When possible, correlate:

```text id="n6q2vy"
Timestamp
Client
Request
Job ID
Error
Result
```

---

# 72. Audit Logging

LUMS records security-relevant application actions in the audit log.

Audit logging is useful when investigating:

```text id="j8r4px"
User changes
Authentication events
Administrative actions
Client management
Token operations
Update-job creation
Security-relevant state changes
```

An audit event should be treated as evidence of an application event, not as a replacement for system logs.

Use application logs for technical execution details and audit logs for security-relevant application actions.

---

# 73. Audit Event Is Missing

If an expected audit event is missing:

1. Identify the exact action.
2. Identify the API endpoint.
3. Verify that the action actually reached the server.
4. Inspect the application logs.
5. Determine whether the action was rejected before the audit event should have been created.

Do not manually insert audit records simply to make an audit trail appear complete.

An audit record should correspond to a real application event.

---

# 74. Audit Log and Application Log Differ

The two logging systems have different purposes.

For example:

```text id="7q2m5k"
Application log
→ technical execution information

Audit log
→ security-relevant application event
```

A package-manager error may therefore appear in the application or Agent log without representing a separate administrative audit event.

Conversely, a user-management action should produce an auditable application event even if the operation itself is technically simple.

---

# 75. Sensitive Information in Logs

Never intentionally place the following into diagnostic output:

```text id="3m7v9x"
Client tokens
Application secret keys
Passwords
Session secrets
Private keys
TLS private material
```

If a diagnostic command would expose one of these values, use a redacted or metadata-only check instead.

When sharing logs for troubleshooting, review them for secrets before copying them into tickets, documentation, GitHub issues, or chat.

---

# 76. Docker Container Security

The production LUMS container is intentionally hardened.

The expected security properties include:

```text id="z4w6pt"
Non-root application user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges enabled
No privileged mode
Dedicated writable data volume
Read-only secret mount
Restricted temporary filesystems
```

If one of these properties changes unexpectedly, treat it as configuration drift.

Do not weaken the container to solve an application problem unless the security impact has been explicitly evaluated.

---

# 77. Verify Container Runtime Security

Inspect the container:

```bash id="b8x5jq"
sudo docker inspect lums
```

For a focused runtime check:

```bash id="r3n7cw"
sudo docker inspect \
    --format='ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}' \
    lums
```

The expected values include:

```text id="k5m2zr"
ReadonlyRootfs=true
Privileged=false
CapDrop=[ALL]
SecurityOpt=[no-new-privileges:true]
```

The exact formatting may vary between Docker versions.

The security properties themselves are what matter.

---

# 78. Container Runs as Root

The LUMS application should run as its dedicated unprivileged application user.

If the container unexpectedly runs as root, first inspect the image and runtime configuration:

```bash id="p6x4nz"
sudo docker inspect \
    --format='{{.Config.User}}' \
    lums
```

Then inspect the Dockerfile.

Do not solve application permission problems by switching the production container to root.

If a directory requires write access, identify the exact path and determine whether it should be persistent application data or temporary data.

---

# 79. Read-Only Root Filesystem

The production container uses a read-only root filesystem.

This protects the application image from unnecessary runtime modification.

If the application reports:

```text id="y5k8mc"
Read-only filesystem
Permission denied
Cannot create file
Cannot write temporary data
```

first determine **where** the application is attempting to write.

Expected writable locations are deliberately limited.

Persistent application data belongs in:

```text id="q9m3xr"
/var/lib/lums
```

Temporary runtime data may use the configured temporary filesystems.

Do not disable `--read-only` merely because an application path is unexpectedly writable.

---

# 80. `/tmp` Is Not Writable

If the application requires temporary storage, verify the temporary filesystem:

```bash id="a7w4vn"
sudo docker inspect \
    --format='{{json .HostConfig.Tmpfs}}' \
    lums
```

The production container provides a restricted `/tmp`.

The temporary filesystem is intended for transient data only.

Persistent data must not be stored there.

---

# 81. Secret Mount Problems

The LUMS application secret is provided through a protected file mount.

The secret should not be embedded directly into the image.

If LUMS reports a missing secret, first inspect the runtime configuration:

```bash id="j4p7zx"
sudo docker inspect \
    lums
```

Check that the secret mount exists and is read-only.

Do not print the contents of the secret.

A useful diagnostic is to verify that the file exists and has the expected permissions without displaying its contents.

---

# 82. Secret File Is Missing

If the secret file does not exist on the host, the container cannot authenticate or initialize correctly.

First determine whether the expected secret path exists.

Do not recreate the secret randomly.

A replacement secret may invalidate existing sessions or other cryptographic state depending on how the application uses it.

Any intentional secret replacement must therefore be treated as a controlled security operation.

---

# 83. Persistent Volume Is Not Writable

If LUMS cannot write application data, inspect the volume:

```bash id="y6c2mt"
sudo docker volume inspect \
    lums-data
```

Then inspect the container mounts:

```bash id="e5w8rq"
sudo docker inspect \
    --format='{{json .Mounts}}' \
    lums
```

The application database must reside on the persistent writable volume.

Do not make the entire container filesystem writable as a workaround.

The correct solution is to identify the specific path that requires persistence.

---

# 84. Docker Container Starts but Application Fails

If the container starts and immediately exits:

```bash id="t7x3mp"
sudo docker ps -a \
    --filter name=lums
```

Then inspect:

```bash id="n4q6vz"
sudo docker logs \
    --tail 200 \
    lums
```

Common causes include:

```text id="w3j8kc"
Application startup error
Missing secret
Database initialization error
Migration failure
Invalid environment configuration
Permission problem
Dependency problem
```

Do not immediately rebuild the image.

Determine whether the problem is in the image, runtime configuration, persistent data, or external configuration.

---

# 85. Docker Image vs. Container Configuration

A working image can still fail because of incorrect runtime configuration.

Always distinguish:

```text id="s7q2mj"
Docker image
    +
Container runtime configuration
    +
Persistent volume
    +
Secret/configuration
```

For example:

```text id="m5v9rz"
Image is valid
      +
Wrong volume
      =
Application failure
```

or:

```text id="r6c3pk"
Image is valid
      +
Missing secret
      =
Application startup failure
```

Do not rebuild an otherwise valid image to fix a runtime configuration problem.

---

# 86. Docker Build Problems

If a new image cannot be built, inspect the Dockerfile first.

Check the base image and dependency definitions.

The production Dockerfile uses a pinned Python base-image digest.

This provides reproducibility and prevents the build from silently moving to an unrelated base-image revision.

If a build suddenly changes behavior, compare:

```text id="e3y7pn"
Dockerfile
Base-image digest
Requirements
Application source
Build context
```

---

# 87. `.dockerignore` Problems

The Docker build context should not contain unnecessary local files or sensitive material.

The repository uses `.dockerignore` to exclude files such as:

```text id="k2x8vw"
Local backups
Temporary files
Editor artifacts
Backup copies
Other unnecessary runtime material
```

If a build unexpectedly contains a file that should not be present, inspect:

```bash id="q5m8cz"
cat .dockerignore
```

Do not solve build-context problems by copying sensitive files into the image.

---

# 88. Filesystem Permission Problems

If LUMS reports permission errors, identify the exact path first.

Useful information:

```bash id="p4r7yn"
sudo docker inspect \
    lums
```

and:

```bash id="n8v2km"
sudo docker logs \
    --tail 200 \
    lums
```

The important distinction is:

```text id="x6c9pw"
Application data
Temporary data
Application source
Secret material
Host configuration
```

Each has different expected permissions.

Do not recursively change ownership or permissions across the entire filesystem as a troubleshooting shortcut.

---

# 89. Production Configuration Drift

Configuration drift occurs when the running environment no longer matches the intended security baseline.

Examples include:

```text id="r5j8tx"
Container runs as root
Port 5050 exposed externally
Read-only filesystem disabled
Capabilities restored
Privileged mode enabled
Secret mounted read-write
Unexpected container running
```

If drift is detected:

1. Record the current state.
2. Determine when it changed.
3. Identify the responsible configuration.
4. Correct the configuration deliberately.
5. Re-run the relevant security verification.

Do not make several unrelated changes at once.

---

# 90. Unexpected Network Exposure

The application port should remain local:

```text id="n7w4cp"
127.0.0.1:5050
```

Check listeners:

```bash id="y2m6vk"
sudo ss -lntp
```

If `5050` is exposed on a non-loopback address, investigate the Docker port mapping immediately.

Do not expose the application port simply because Nginx appears difficult to diagnose.

The intended architecture is:

```text id="h3x8qm"
Network
   ↓
Nginx :443
   ↓
127.0.0.1:5050
   ↓
LUMS
```

---

# 91. Unexpected Docker Containers

List all containers:

```bash id="c6w9rz"
sudo docker ps -a
```

Unexpected containers should be identified before they are removed.

Check:

```text id="m8x2kf"
Container name
Image
Creation time
Ports
Volumes
Restart policy
```

Do not delete an unknown container without determining whether it is part of the LUMS deployment or a required fallback environment.

---

# 92. Docker Volume Must Not Be Deleted During Normal Troubleshooting

The following operation is destructive:

```bash id="q7v3mc"
sudo docker volume rm lums-data
```

It must not be used as a general troubleshooting step.

Deleting the volume can remove the application database and associated persistent state.

If a clean installation is intentionally required, treat it as a separate migration or recovery operation and verify backups first.

---

# 93. Security Baseline After Runtime Changes

After changing production Docker configuration, verify the security baseline again.

At minimum verify:

```text id="z5n8xp"
Container runs as intended user
Root filesystem is read-only
Capabilities are dropped
Privileged mode is disabled
no-new-privileges is enabled
Secret mount is read-only
Database volume is writable
Application port is loopback-only
```

A configuration that makes the application work but weakens these properties should not be considered a successful fix.

---

# 94. Next Troubleshooting Area

The remaining troubleshooting topics are:

```text id="v4m7yx"
Tests and CI
Diagnostic snapshots
Common failure combinations
Recovery principles
Final troubleshooting checklist
```

The final sections provide a compact procedure for collecting enough information to diagnose a problem without unnecessarily changing the production environment.

# 95. Tests and CI

Automated tests are an important part of troubleshooting LUMS.

Before investigating a production problem as an application defect, verify whether the relevant behavior is already covered by the test suite.

The current full test suite should pass before a release is considered ready.

Run the complete test suite from the repository:

```bash id="m4x8kp"
./.venv-test/bin/pytest -q
```

A successful run should report all tests as passed.

The current project baseline is:

```text id="v7c3nm"
155 passed
```

The exact number may increase as additional tests are added.

Therefore, the important condition is that the complete test suite succeeds rather than relying permanently on a fixed test count.

---

# 96. A Test Failure Does Not Automatically Mean Production Is Broken

A failed test can be caused by:

```text id="q8r5wy"
Application regression
Test regression
Dependency change
Environment problem
Missing test dependency
Incorrect test configuration
```

First inspect the complete failure output.

Do not modify production configuration simply because a local test fails.

The correct sequence is:

```text id="n4m7tx"
Test failure
    ↓
Read complete error
    ↓
Identify affected component
    ↓
Reproduce locally
    ↓
Determine root cause
    ↓
Apply controlled fix
    ↓
Run relevant tests
    ↓
Run full test suite
```

---

# 97. RBAC Test Failures

When investigating authorization problems, run the RBAC tests first:

```bash id="k6w2pv"
./.venv-test/bin/pytest -q tests/test_rbac.py
```

The tests cover role-specific behavior and authorization boundaries.

If the problem concerns the client page, use the relevant subset when appropriate:

```bash id="z5n8rc"
./.venv-test/bin/pytest -q \
    tests/test_rbac.py -k client_page
```

Do not weaken authorization to make a test pass.

A failed authorization test may indicate a security regression.

---

# 98. Package Search Test Failures

Package-management functionality has dedicated test coverage.

When investigating package-search behavior:

```bash id="b7x3mf"
./.venv-test/bin/pytest -q \
    tests/test_package_search.py
```

If the failure involves package execution or job results, also inspect the relevant job-result tests.

The test suite should be used to distinguish:

```text id="y9r4nk"
Application logic problem
Package-search problem
Agent problem
Integration problem
```

---

# 99. Job Result Validation Tests

Job-result handling is security-sensitive because the server must not blindly trust arbitrary client input.

Run the relevant tests when investigating result validation:

```bash id="w6q2vz"
./.venv-test/bin/pytest -q \
    tests/test_job_result.py
```

A failure here should be treated as an application correctness and security issue.

Do not bypass result validation to make a client report succeed.

---

# 100. CI Failures

LUMS uses continuous integration to verify the project before changes are accepted.

If CI fails:

1. Identify the failed job.
2. Read the complete error.
3. Determine whether the failure is code, dependency, test, or environment related.
4. Reproduce locally where possible.
5. Fix the root cause.
6. Run the relevant tests.
7. Run the complete test suite.

Do not ignore CI failures simply because the production environment currently appears functional.

---

# 101. Diagnostic Snapshot

When asking for help with a LUMS problem, collect a minimal diagnostic snapshot.

The goal is to provide enough information to identify the failing component without exposing secrets.

A useful snapshot includes:

```bash id="x8p4qn"
sudo docker ps
```

```bash id="c5m7vz"
sudo docker logs --tail 100 lums
```

```bash id="f2w9yk"
sudo systemctl status nginx --no-pager
```

```bash id="n6r3tx"
sudo systemctl status lums-agent.service --no-pager
```

```bash id="q7v4mc"
sudo systemctl status lums-agent-watcher.service --no-pager
```

```bash id="z3k8wp"
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

```bash id="h5m2rx"
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager
```

```bash id="p9x6kc"
sudo ss -lntp
```

Use only the commands relevant to the problem.

Do not dump the complete environment into a support request.

---

# 102. Diagnostic Snapshot Must Not Contain Secrets

Before sharing diagnostic output, check for:

```text id="r4m8yn"
Passwords
Client tokens
Application secret keys
Session secrets
Private keys
TLS private material
Credentials
```

Redact sensitive values before sharing.

Do not assume that a log is safe simply because it came from a system service.

---

# 103. Failure Combination Matrix

Some symptoms become easier to diagnose when several components are considered together.

| Symptom                                | Most likely area to inspect first  |
| -------------------------------------- | ---------------------------------- |
| Browser cannot connect                 | Nginx / TLS / network              |
| Nginx works but application fails      | Docker / LUMS                      |
| LUMS works but client cannot report    | Agent / TLS / token                |
| Client reports but job stays pending   | Watcher / eligibility              |
| Job runs but package fails             | APT / pacman                       |
| Package succeeds but result is missing | Agent reporting                    |
| Result reaches server but UI is stale  | API / database / browser state     |
| Viewer can mutate data                 | Server-side RBAC                   |
| User cannot log in                     | Account / password / rate limiting |
| Login works but action is rejected     | RBAC / CSRF                        |
| Database writes fail                   | SQLite / disk / permissions        |
| Container loses data after recreation  | Persistent volume configuration    |
| Application writes to root filesystem  | Container filesystem configuration |
| Port 5050 is externally reachable      | Docker / firewall configuration    |

This table identifies the first place to investigate, not necessarily the final root cause.

---

# 104. Common Troubleshooting Mistakes

Avoid the following shortcuts:

## Do not delete the database

```text id="h7k2px"
Deleting lums.db
Deleting lums-data
```

can destroy persistent application state.

---

## Do not disable security controls

Do not permanently disable:

```text id="j5r9cw"
RBAC
CSRF protection
TLS validation
Container hardening
Read-only filesystem
no-new-privileges
Capability restrictions
```

A workaround that removes a security control is not a completed fix.

---

## Do not run the container as privileged

Avoid:

```text id="b3x7mz"
--privileged
```

as a troubleshooting solution.

If the application requires additional access, determine exactly what access is required.

---

## Do not expose port 5050

Do not change:

```text id="v8n4qr"
127.0.0.1:5050
```

to:

```text id="p2m6wy"
0.0.0.0:5050
```

simply to bypass Nginx.

The application is intentionally protected behind the reverse proxy.

---

## Do not modify job states manually

Avoid directly changing:

```text id="r7c5xn"
update_jobs
update_job_packages
```

to hide an operational problem.

Use the application, Agent, watcher, and recovery mechanisms.

---

## Do not delete package-manager locks blindly

A lock may indicate an active package-manager process.

Identify the process first.

---

## Do not rotate credentials repeatedly

Repeated token or secret rotation can create additional authentication problems.

First determine which credential is currently configured and which credential the server expects.

---

# 105. Recovery Principles

The following principles apply to all LUMS troubleshooting:

### Preserve first

Keep:

```text id="q3m8vx"
Logs
Job state
Database
Container state
Configuration
Error messages
```

until the problem is understood.

### Change one thing at a time

When several changes are made simultaneously, the original cause becomes harder to identify.

### Verify after every change

After a controlled change:

```text id="z6w2kp"
Re-test
Check logs
Verify state
Confirm security properties
```

### Prefer reversible changes

Whenever possible, use changes that can be reverted without destroying application state.

### Keep security controls active

A successful troubleshooting result must not introduce an unnecessary security regression.

---

# 106. Production Troubleshooting Sequence

For a general LUMS production problem, use this order:

```text id="f4n8rx"
1. Identify the symptom
        ↓
2. Identify the affected component
        ↓
3. Inspect current state
        ↓
4. Inspect relevant logs
        ↓
5. Reproduce safely
        ↓
6. Determine the first failing layer
        ↓
7. Apply the smallest required change
        ↓
8. Re-test
        ↓
9. Verify security controls
        ↓
10. Document the result
```

This order prevents unrelated components from being changed unnecessarily.

---

# 107. Full System Diagnostic Path

When the affected component is unknown, follow the complete path:

```text id="u7x3mp"
Browser
  │
  ▼
Nginx / HTTPS
  │
  ▼
Docker
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Update Job
  │
  ▼
Watcher
  │
  ▼
Agent
  │
  ▼
APT / pacman
  │
  ▼
Client state
  │
  ▼
Agent result
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Web UI
```

At each stage, ask:

```text id="k5r2qy"
Did the request reach this component?

Did this component process it?

Did it produce the expected result?

Did the next component receive that result?
```

The first `NO` normally identifies the area that requires investigation.

---

# 108. Release Troubleshooting

Before preparing a release, verify:

```text id="m8x4vp"
Full test suite passes
CI passes
Security audit is complete
Documentation is current
Production configuration matches the documented baseline
No unexpected debug configuration remains
No secrets are included in the repository
Docker hardening remains active
RBAC behavior is correct
Package management works
Update-job execution works
Recovery behavior is verified
```

A release should not be created merely because the application starts successfully.

---

# 109. Troubleshooting Checklist

Use this checklist before declaring a production problem resolved:

```text id="y6q3kn"
[ ] Root cause identified
[ ] Relevant logs inspected
[ ] No unnecessary data was deleted
[ ] No credentials were exposed
[ ] No security control was disabled
[ ] Relevant functionality tested
[ ] Full test suite considered where appropriate
[ ] Docker security baseline verified
[ ] Network exposure verified
[ ] Agent state verified
[ ] Watcher state verified
[ ] Job state verified
[ ] Recovery state verified
[ ] Database state verified where relevant
[ ] Documentation updated if behavior changed
```

---

# 110. When to Stop Troubleshooting

Stop making changes when:

```text id="v9m4xr"
The root cause is identified
    AND
The corrective action is understood
    AND
The system is stable
    AND
Security controls remain intact
```

If the root cause is not understood, preserve the current state rather than repeatedly changing the environment.

A cleanly preserved failure is easier to diagnose than a partially modified system.

---

# 111. Final Recovery Principle

The most important LUMS troubleshooting rule is:

> **Observe first. Change second. Verify third.**

LUMS contains several independent security and execution layers.

A problem in one layer should not automatically result in changes to another.

The preferred troubleshooting approach is therefore:

```text id="c8w5zn"
Observe
   ↓
Classify
   ↓
Isolate
   ↓
Correct
   ↓
Verify
   ↓
Document
```

This keeps troubleshooting controlled, reproducible, and compatible with the LUMS security baseline.

---

# 112. Documentation Maintenance

This document should be updated whenever a documented operational behavior changes.

Documentation changes should remain consistent with:

```text id="q7m3vx"
Security documentation
Deployment documentation
Agent behavior
Watcher behavior
RBAC model
Package-management behavior
Docker runtime configuration
Test baseline
```

Outdated troubleshooting instructions can be dangerous when they recommend deprecated commands or security-weakening workarounds.

When a production behavior changes, update the relevant documentation before treating the troubleshooting procedure as complete.

---

# 113. Current Baseline

The current LUMS baseline documented by this troubleshooting guide includes:

```text id="m4x8qp"
Agent version: 1.7.0
Watcher version: 1.2.1

Application port:
127.0.0.1:5050

Database:
SQLite

SQLite journal mode:
delete

SQLite busy timeout:
5000 ms

SQLite synchronous:
2

SQLite foreign keys:
Enabled by the application

Container:
Non-root
Read-only root filesystem
Capabilities dropped
no-new-privileges enabled
Privileged mode disabled

RBAC:
Administrator
Operator
Viewer

Viewer:
Clients + Installed Software only

Full test suite:
Passing baseline
```

The exact test count may change as the project grows.

The security and architectural properties are the important baseline.

---

# 114. End of Troubleshooting Guide

LUMS troubleshooting should remain evidence-driven and security-conscious.

When in doubt:

```text id="r9x4kw"
Preserve the state.
Inspect the evidence.
Identify the failing layer.
Make the smallest safe change.
Verify the result.
Document what happened.
```

Do not trade security or data integrity for a quick workaround.

---

**End of LUMS Troubleshooting Guide**
