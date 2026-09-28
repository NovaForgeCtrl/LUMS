# LUMS Troubleshooting

This guide provides troubleshooting procedures for the LUMS server, Linux agents, execution watchers, update jobs, authentication and Docker deployment.

The troubleshooting process should always start with observation before changing configuration.

A useful first step is to determine whether the problem occurs on:

```text
LUMS Server
Linux Agent
Execution Watcher
Network / TLS
Authentication
Database
Update Job
Package Manager
```

---

# 1. Troubleshooting Philosophy

LUMS consists of several independent components.

A successful agent report does not automatically mean that update execution is working.

The main communication path is:

```text
Linux Client
     │
     ├── Agent
     │
     └── Watcher
             │
             ▼
          HTTPS
             │
             ▼
        Nginx / LUMS
             │
             ▼
          SQLite
```

When troubleshooting, identify the first component where the expected behavior stops.

For example:

```text
Agent report fails
    ↓
check client service
    ↓
check TLS
    ↓
check token
    ↓
check LUMS API
```

Do not immediately modify the database or reinstall the client.

---

# 2. First Diagnostic Checks

On the LUMS server:

```bash
sudo docker ps
```

The `lums` container should be running.

Check the recent application output:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Check Nginx:

```bash
sudo systemctl status nginx --no-pager
```

Validate the Nginx configuration:

```bash
sudo nginx -t
```

From a client:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Check the watcher:

```bash
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Check both timers:

```bash
sudo systemctl list-timers \
    --all | grep lums
```

These checks establish whether the basic components are running before deeper investigation begins.

---

# 3. LUMS Container Is Not Running

Check the container:

```bash
sudo docker ps -a \
    --filter name=lums
```

Inspect the container:

```bash
sudo docker inspect lums
```

Check the logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

If the container exited, inspect the exit state:

```bash
sudo docker inspect \
    --format '{{.State.Status}} {{.State.ExitCode}}' \
    lums
```

Do not immediately remove the container.

The logs may contain the reason for the failure.

---

# 4. Container Starts but LUMS Is Not Reachable

The production container exposes the application only locally:

```text
127.0.0.1:5050
```

Nginx provides the external HTTPS endpoint.

Verify the port binding:

```bash
sudo docker port lums
```

Expected architecture:

```text
Browser
   │
 HTTPS :443
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

If the container is running but HTTPS fails, test each layer separately.

First:

```bash
sudo docker ps
```

Then:

```bash
sudo ss -lntp | grep -E ':443|:5050'
```

Then:

```bash
sudo nginx -t
```

Finally inspect:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

---

# 5. Nginx Returns an Error

Check the service:

```bash
sudo systemctl status nginx \
    --no-pager
```

Validate the configuration:

```bash
sudo nginx -t
```

Inspect the Nginx error log:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Also verify that LUMS itself is running:

```bash
sudo docker ps
```

A reverse-proxy error does not necessarily mean that the LUMS application itself is broken.

---

# 6. HTTPS / TLS Problems

First test the endpoint:

```bash
curl -I https://LUMS-SERVER/
```

If certificate verification fails, inspect the certificate configuration.

Check the configured TLS files:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Validate Nginx:

```bash
sudo nginx -t
```

If the certificate was recently replaced:

```bash
sudo systemctl reload nginx
```

Then test again:

```bash
curl -I https://LUMS-SERVER/
```

For clients using a private CA, verify that the client trusts the appropriate CA certificate.

Do not disable TLS verification as a permanent workaround.

---

# 7. Agent Service Fails

Check:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Read the complete recent journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Run the service again:

```bash
sudo systemctl start lums-agent.service
```

Then inspect:

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

For a `Type=oneshot` service, an inactive state after a successful run can be expected.

The important information is the exit result.

A successful run should end with:

```text
status=0/SUCCESS
```

---

# 8. Agent Reports `LUMS_TOKEN` Missing

The agent configuration is normally supplied through the systemd service environment.

If the agent is started manually from a shell, the systemd `EnvironmentFile` is not automatically loaded into that shell.

Therefore:

```bash
sudo /opt/lums-agent/agent.py --version
```

may behave differently from:

```bash
sudo systemctl start lums-agent.service
```

when the token is only configured through systemd.

When investigating authentication problems, test the actual systemd service first:

```bash
sudo systemctl start lums-agent.service
```

Then inspect:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Do not copy production tokens into shell commands unnecessarily.

---

# 9. Agent Cannot Reach the Server

First test basic network connectivity:

```bash
ping LUMS-SERVER
```

Then test HTTPS:

```bash
curl -I https://LUMS-SERVER/
```

If HTTPS works but the agent still fails, investigate:

```text
Token
TLS trust
Agent configuration
API response
Client identity
```

Inspect the agent journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

On the server, simultaneously inspect:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

This allows the administrator to determine whether the request reaches LUMS at all.

---

# 10. Client Report Is Rejected

A rejected report can result from authentication or validation failure.

Check the agent journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Then check the LUMS server logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Verify:

```text
Client token
Client identity
TLS connection
Request payload
Server availability
```

Client authentication uses a client-specific Bearer token.

The token is validated against its stored SHA-256 digest.

If the token has been rotated, the old token is no longer valid.

---

# 11. Token Rotation Problems

After rotating a client token:

```text
Old token → invalid
New token → valid
```

If the client stops reporting immediately after rotation, verify that the new token was installed into the client's configuration.

Then restart the agent service:

```bash
sudo systemctl restart \
    lums-agent.service
```

Check:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

If the old token is still configured, the server will reject the client.

Do not attempt to restore the old token simply to hide the error. Update the client configuration with the newly generated credential.

---

# 12. Agent Reports Successfully but No Updates Are Visible

A successful report does not necessarily mean that updates are available.

First check the client inventory in LUMS.

Then verify the native package manager.

Debian/Ubuntu:

```bash
apt list --upgradable
```

Arch Linux:

```bash
pacman -Qu
```

If the native package manager reports no updates, LUMS should not invent an update.

If the package manager reports updates but LUMS does not, inspect:

```text
Agent version
Agent journal
Package-manager detection
Server report
Client inventory
```

---

# 13. Debian/Ubuntu Package Detection Problems

Verify APT:

```bash
command -v apt
```

Verify dpkg:

```bash
command -v dpkg-query
```

Check available updates:

```bash
apt list --upgradable
```

The LUMS APT implementation treats a failing update-detection command as an error rather than silently interpreting the failure as an empty update list.

This prevents a broken APT query from being reported as:

```text
0 updates
```

when the actual package-manager operation failed.

---

# 14. Arch Linux Package Detection Problems

Verify pacman:

```bash
command -v pacman
```

Check available updates:

```bash
pacman -Qu
```

Check installed packages:

```bash
pacman -Q
```

The LUMS package-manager abstraction detects Arch Linux through the available `pacman` executable.

Do not install additional utilities merely because they are available on Debian-based systems.

For example, the absence of the separate `hostname` command does not by itself indicate that the LUMS agent is broken if `/etc/hostname` provides the system hostname.

---

# 15. Continue Troubleshooting

If the server, agent, TLS and authentication layers are working but an update job does not execute, continue with the execution-specific checks in the next section.

The next areas to inspect are:

```text
Execution Watcher
Idle Detection
Pending Jobs
Job Claiming
Package Manager Execution
Timeouts
Recovery
Result Reporting
```

# 16. Execution Watcher Is Not Running

Check the watcher service:

```bash id="bq9s8a"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Inspect recent logs:

```bash id="6f0d1a"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Start the watcher manually:

```bash id="0v5m2s"
sudo systemctl start \
    lums-agent-watcher.service
```

Then inspect the result:

```bash id="9n3b8e"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

The watcher is a separate component from the reporting agent.

A successful agent report therefore does not prove that the watcher is functioning correctly.

---

# 17. Watcher Timer Is Not Triggering

Check all LUMS timers:

```bash id="1qf8rs"
sudo systemctl list-timers \
    --all | grep lums
```

Inspect the watcher timer:

```bash id="9g7l3p"
sudo systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

If necessary, enable and start it:

```bash id="j0d7kg"
sudo systemctl enable --now \
    lums-agent-watcher.timer
```

Then check:

```bash id="x3g9qn"
systemctl list-timers \
    --all | grep lums-agent
```

The timer is responsible for periodically starting the watcher service.

---

# 18. Agent Timer Is Not Triggering

Check:

```bash id="u8kq3x"
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Check the next scheduled execution:

```bash id="6at6oe"
systemctl list-timers \
    --all | grep lums-agent
```

If the timer is disabled:

```bash id="qz7d5s"
sudo systemctl enable --now \
    lums-agent.timer
```

Then inspect the service journal:

```bash id="h0lq8n"
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 19. Idle Detection Is Not Working

LUMS uses Linux `systemd-logind` information for idle detection.

The current implementation uses:

```text id="qj2p6k"
loginctl
```

The default idle threshold is:

```text id="7h8w3a"
300 seconds
```

The agent reports information such as:

```text id="9b0h3v"
idle
idle_seconds
idle_threshold_seconds
idle_source
idle_supported
```

The expected source for a supported Linux client is:

```text id="a3r6t2"
idle_source=loginctl
```

---

# 20. Check `loginctl`

First check whether `loginctl` exists:

```bash id="p5b4s7"
command -v loginctl
```

Then:

```bash id="r6c9m1"
loginctl
```

List sessions:

```bash id="x1v7k4"
loginctl list-sessions
```

List users:

```bash id="s4m8q2"
loginctl list-users
```

If `loginctl` is unavailable or cannot provide a reliable idle state, the watcher must not assume that the client is safely idle.

Automatic execution should therefore not continue merely because idle detection failed.

---

# 21. Client Is Active but Job Is Pending

A pending job does not necessarily indicate an error.

The watcher intentionally waits when the client is not idle.

The normal flow is:

```text id="e4k6z2"
Pending Job
     ↓
Watcher
     ↓
Idle Check
     │
     ├── active
     │      ↓
     │    wait
     │
     └── idle
            ↓
          claim
```

The default idle threshold is 300 seconds.

Check the watcher journal:

```bash id="q9t5w3"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Do not repeatedly create new jobs simply because the current job has not executed yet.

---

# 22. Job Remains in `pending`

First verify that the client is reporting successfully.

Then inspect the watcher:

```bash id="a7m2c9"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Inspect its journal:

```bash id="e3n8k1"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Then check the client's idle state.

A pending job may be waiting because:

```text id="h5q1v9"
Client is active
Idle detection is unavailable
Watcher is not running
Watcher timer is not running
Job cannot be claimed
```

Investigate these conditions before modifying the job manually.

---

# 23. Job Cannot Be Claimed

LUMS claims jobs atomically.

The intended lifecycle is:

```text id="d7v3p8"
pending
   ↓
atomic claim
   ↓
running
```

Atomic claiming prevents two execution processes from executing the same job simultaneously.

If a job does not move from `pending` to `running`, inspect the watcher log first:

```bash id="m1x6s4"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Then inspect the server:

```bash id="c8r2y6"
sudo docker logs \
    --tail 200 \
    lums
```

Do not manually change database job states unless the normal recovery procedure has been exhausted and a verified backup exists.

---

# 24. Job Is Stuck in `running`

A job in `running` means that it has already been claimed.

First inspect the watcher:

```bash id="k2w8n5"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Check the agent:

```bash id="v6p3q9"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Check the server:

```bash id="b9r4x7"
sudo docker logs \
    --tail 200 \
    lums
```

Possible causes include:

```text id="r3n7w2"
Update process still running
Client interruption
Agent stopped
Watcher interruption
Network interruption
Missing final result
```

LUMS contains recovery handling specifically to prevent interrupted jobs from remaining permanently unresolved.

---

# 25. Interrupted Job Recovery

The recovery workflow is designed around jobs that were previously running but did not receive a final result.

Conceptually:

```text id="x5k2r9"
running
   ↓
client interruption
   ↓
watcher detects unresolved state
   ↓
recovery
   ↓
final state
```

A recovered job may become:

```text id="z8m4p1"
abandoned
```

The recovery process records relevant information such as:

```text id="u2c6s7"
Finished timestamp
Recovery reason
Update history
Package statistics
Reboot state
```

The server must not blindly create a second execution for an already-running job.

---

# 26. Job Is `abandoned`

An `abandoned` job indicates that an execution did not complete normally and was subsequently recovered.

Check:

```bash id="w7n1c5"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Then inspect:

```bash id="j4q8m2"
sudo docker logs \
    --tail 200 \
    lums
```

Determine:

```text id="v3p6r1"
Why did the client stop?
Was the update process interrupted?
Was the agent restarted?
Was network connectivity lost?
Did the client reboot?
```

Do not interpret `abandoned` as proof that no package changes occurred.

The final package state should be checked on the client before deciding what action to take next.

---

# 27. Job Is `failed`

A failed job means that the execution did not complete successfully.

Inspect the watcher:

```bash id="p6t2w8"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Inspect the agent:

```bash id="n4k7x1"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Check the native package manager directly.

Debian/Ubuntu:

```bash id="f8m3q6"
apt list --upgradable
```

Arch:

```bash id="c1v9s5"
pacman -Qu
```

A failed LUMS job should be investigated against the native package-manager state rather than retried blindly.

---

# 28. Job Is `partial`

A partial result means that the job contained multiple package operations and not all of them completed successfully.

Inspect the package-level results in the LUMS interface.

Then check the native package manager.

For Debian/Ubuntu:

```bash id="q5m8r2"
dpkg-query -W
```

For Arch:

```bash id="y7c3n1"
pacman -Q
```

Then determine which packages actually changed.

The LUMS result should be interpreted together with the package-manager state.

---

# 29. Update Times Out

If an update operation exceeds its configured execution timeout, LUMS uses controlled process termination.

The intended sequence is:

```text id="s2k6p9"
Update process
      ↓
timeout
      ↓
termination request
      ↓
grace period
      ↓
kill fallback
```

Check the watcher journal:

```bash id="n8v4q3"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Then verify the package state using the native package manager.

Do not assume that a timeout means that nothing changed.

Package operations should always be checked after an interrupted or timed-out execution.

---

# 30. Package Manager Is Locked

If APT or pacman reports that another package operation is already running, do not immediately delete lock files.

First determine whether another package operation is actually active.

For Debian/Ubuntu, inspect the relevant processes and package-manager state.

For Arch Linux, check whether pacman is already running.

LUMS is designed to avoid blindly starting a second package operation.

The correct response is to identify the existing operation and allow it to finish or recover it appropriately.

---

# 31. Continue Troubleshooting

At this stage, the basic server, client, authentication, watcher, idle detection and job lifecycle problems have been covered.

The next section should focus on:

```text id="k7p2m9"
Package installation/removal
UPDATE_SYSTEM
Result reporting
Reboot detection
Database problems
RBAC
Logging
Container hardening
```
# 32. Package Installation Fails

If an `INSTALL_PACKAGE` job fails, first determine whether the problem is specific to LUMS or to the native package manager.

Check the client journal:

```bash id="m7c4x9"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Then inspect the native package manager.

Debian/Ubuntu:

```bash id="p8n2k6"
apt-cache policy <package>
```

Check the installed state:

```bash id="f4q7w1"
dpkg-query -W <package>
```

Arch Linux:

```bash id="d9s5v3"
pacman -Si <package>
```

Check the installed state:

```bash id="r2k8m6"
pacman -Q <package>
```

If the package manager itself reports an error, resolve that client-side problem before retrying the LUMS job.

---

# 33. Package Removal Fails

For `REMOVE_PACKAGE` jobs, verify that the package is actually installed.

Debian/Ubuntu:

```bash id="j6v3q9"
dpkg-query -W <package>
```

Arch Linux:

```bash id="n4k7s2"
pacman -Q <package>
```

Then inspect the watcher journal:

```bash id="x8m5c1"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

A failed removal should not be interpreted as successful simply because the job was created.

Verify the actual package state after the operation.

---

# 34. `UPDATE_PACKAGE` Does Not Complete

Check whether the package has an available candidate.

Debian/Ubuntu:

```bash id="v7q2m4"
apt-cache policy <package>
```

Arch Linux:

```bash id="c3n8x5"
pacman -Si <package>
```

Then compare the installed version with the available version.

Also inspect:

```bash id="k5r1p8"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

If the native package manager cannot perform the requested update independently, LUMS cannot complete the operation successfully either.

---

# 35. `UPDATE_SYSTEM` Fails

`UPDATE_SYSTEM` uses the native package-manager system update operation.

For Debian/Ubuntu, investigate APT first:

```bash id="q4m9v7"
sudo apt update
```

Then:

```bash id="z8k2c5"
apt list --upgradable
```

For Arch Linux:

```bash id="w6p3n1"
sudo pacman -Syu
```

Do not repeatedly start system-wide update jobs while the package manager is already processing another operation.

Check the watcher journal before retrying:

```bash id="s5c7r2"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

---

# 36. Package Manager Collision

LUMS controls its own update execution, but it cannot automatically control every package-manager command started independently by an administrator.

For example, an administrator may manually run:

```bash id="b2f7m4"
sudo apt upgrade
```

while a LUMS job is waiting to execute.

Do not delete APT or dpkg lock files to force the operation.

Instead:

1. Determine whether another package operation is running.
2. Allow the legitimate operation to finish.
3. Check the package-manager state.
4. Retry the LUMS job if appropriate.

The current implementation does not provide complete coordination with arbitrary manually started APT/dpkg processes.

---

# 37. Never Delete Package-Manager Lock Files

Do not use commands such as:

```text id="c8m5r1"
rm /var/lib/dpkg/lock*
rm /var/lib/apt/lists/lock
```

as a generic troubleshooting procedure.

A lock file may represent an active package-manager operation.

Removing it can leave the package database in an inconsistent state.

Resolve the process that owns the operation instead.

---

# 38. Simulation Mode

LUMS provides simulation support for testing the update workflow without executing real package operations.

Simulation is useful for testing:

```text id="u4n8p2"
Job creation
Job claiming
Watcher behavior
Result reporting
UI state transitions
```

Simulation must not be mistaken for a real package update.

A successful simulation does not prove that a real APT/dpkg or pacman operation will succeed.

---

# 39. Disable Simulation After Testing

Before using real update execution, verify that simulation is not enabled.

If simulation was configured through the watcher service, inspect the service definition:

```bash id="x7m3q9"
sudo systemctl cat \
    lums-agent-watcher.service
```

Look for an environment setting such as:

```text id="p2c6v8"
LUMS_SIMULATE_UPDATES=1
```

If present, remove the simulation setting from the service configuration.

Then reload systemd:

```bash id="k9r4w1"
sudo systemctl daemon-reload
```

Restart the watcher if required:

```bash id="n6t2q5"
sudo systemctl restart \
    lums-agent-watcher.service
```

Do not assume that a successful simulation means that the production update path is currently active.

---

# 40. Update Result Is Rejected

The server validates submitted update results.

A result must correspond to:

```text id="v5c8n2"
An existing job
The authenticated client
A job currently in the expected state
A package belonging to that job
A valid package result
```

If the result is rejected, inspect the agent and watcher journals:

```bash id="r7m1x4"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

and:

```bash id="f3q8k6"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Then inspect the server:

```bash id="w2n9c5"
sudo docker logs \
    --tail 200 \
    lums
```

Do not manually mark the job successful in the database.

---

# 41. Job Result Does Not Match Package State

A LUMS result should be compared with the actual package-manager state.

Debian/Ubuntu:

```bash id="h6r2m9"
dpkg-query -W <package>
```

Arch:

```bash id="c7p4x1"
pacman -Q <package>
```

For available updates:

Debian/Ubuntu:

```bash id="m8v3q5"
apt list --upgradable
```

Arch:

```bash id="t4n7k2"
pacman -Qu
```

This is particularly important after:

```text id="b5q8m1"
Timeout
Interrupted execution
Client reboot
Network failure
Abandoned job
```

A job state describes the LUMS execution result; the package manager remains the authoritative source for the actual installed package state.

---

# 42. Reboot Is Required

LUMS can detect whether a reboot is required after an update.

For Debian/Ubuntu, check:

```bash id="q9w4m6"
test -f /var/run/reboot-required \
    && echo "Reboot required" \
    || echo "No reboot required"
```

For Arch Linux, LUMS compares the running kernel with the installed Linux package/module information.

A required reboot does not mean that LUMS automatically reboots the client.

The reboot remains an administrative decision.

---

# 43. Reboot Detection Appears Incorrect

First determine the operating system:

```bash id="j3k7v9"
cat /etc/os-release
```

On Debian/Ubuntu, check:

```bash id="s6m2x8"
ls -l /var/run/reboot-required
```

On Arch Linux, check the running kernel:

```bash id="p4c9n1"
uname -r
```

Then inspect the installed Linux package information:

```bash id="v8q5m3"
pacman -Q linux
```

If the LUMS result differs from the local operating-system state, inspect the agent journal before changing anything.

---

# 44. SQLite Database Problems

The production database is stored at:

```text id="n2f7c4"
/var/lib/lums/lums.db
```

Inside the Docker deployment, this path is backed by:

```text id="q8m4v1"
lums-data
```

Do not remove the Docker volume as a first troubleshooting step.

Check the container:

```bash id="x5r9k2"
sudo docker ps
```

Then check database integrity.

Example:

```bash id="w7c3n8"
sudo docker exec lums \
    python3 -c '
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
result = db.execute("PRAGMA integrity_check;").fetchone()[0]
print(result)
db.close()
'
```

Expected result:

```text id="e4p6s1"
ok
```

If the result is not `ok`, stop and create a backup before performing destructive database operations.

---

# 45. SQLite Busy or Locked Errors

LUMS uses SQLite with application-level database handling designed for concurrent access.

If SQLite reports that the database is busy or locked, first inspect whether multiple application processes or maintenance operations are interacting with the database.

Check the container:

```bash id="m1q8v5"
sudo docker ps
```

Inspect recent logs:

```bash id="b6r3k9"
sudo docker logs \
    --tail 200 \
    lums
```

Do not immediately delete:

```text id="p5n7c2"
lums.db
```

and do not remove the Docker volume.

The database contains client, job, authentication and history information.

---

# 46. Database Restore

If corruption or accidental data loss requires a restore, use a known-good SQLite-aware backup.

Before restoration:

```text id="r9m4x6"
Stop
   ↓
Backup current state
   ↓
Restore known-good database
   ↓
Integrity check
   ↓
Start LUMS
   ↓
Application validation
```

Never overwrite the only remaining copy of the database with an unverified backup.

After restoration, verify:

```text id="k2v7q4"
Database integrity
Administrator login
Client records
Update jobs
Update history
```

---

# 47. RBAC: Access Denied

LUMS currently supports three web roles:

```text id="c8m2r5"
administrator
operator
viewer
```

The intended permissions are:

```text id="v4n7p1"
Administrator
    full administrative access

Operator
    view clients
    view updates
    create/execute update jobs
    no user administration

Viewer
    view clients
    view updates
    view jobs
    no modifications
```

A `403` response does not necessarily indicate an authentication problem.

It can mean that the authenticated user does not have the required role.

---

# 48. RBAC: Administrator

The administrator role has access to administrative functions including:

```text id="q5x9m3"
User management
Role management
Client creation
Client token rotation
Client deletion
Update operations
```

If an administrator receives an authorization error, verify the role stored for the user.

The role should be:

```text id="w3k8r6"
administrator
```

Do not change the database manually as the first troubleshooting step.

---

# 49. RBAC: Operator

An operator can perform operational update-management tasks but does not have user-administration privileges.

An operator can:

```text id="n6p2v8"
View clients
View package/update information
Create update jobs
Execute permitted update operations
View job information
```

An operator cannot perform administrator-only functions such as:

```text id="s4m7c1"
User management
Role management
Client token rotation
Client deletion
```

A `403` response for these operations is therefore expected behavior.

---

# 50. RBAC: Viewer

A viewer is intentionally restricted to read-only access.

A viewer can inspect:

```text id="y2q6m9"
Clients
Packages
Updates
Jobs
History
```

A viewer cannot create or modify operational resources.

If a viewer receives:

```json
{"error":"authorization_required"}
```

for a modifying API endpoint, the response is consistent with the role model.

---

# 51. Invalid or Missing User Role

LUMS validates user roles against the supported role set.

Valid roles are:

```text id="k5r8p3"
administrator
operator
viewer
```

An invalid role must not silently receive administrative privileges.

If a role-related error occurs, inspect:

```text id="u7m4x1"
LUMS server logs
User record
Recent migration status
```

The RBAC database migration is:

```text id="c9n2v6"
002-rbac
```

Do not manually remove the `role` column from the database.

---

# 52. Authentication Works but Authorization Fails

Authentication and authorization are separate checks:

```text id="z4p8m2"
Authentication
      ↓
Who are you?
      ↓
Authenticated user
      ↓
Authorization
      ↓
What are you allowed to do?
```

Therefore:

```text id="a7q3n9"
401
```

generally indicates an authentication problem, while:

```text id="m6v2c8"
403
```

can indicate that the authenticated user lacks the required permission.

Use the server logs and current user role to distinguish the two.

---

# 53. Continue Troubleshooting

The next section covers the remaining infrastructure-level problems:

```text id="r8k4m1"
Application logging
Audit logging
Container hardening
Secrets
Permissions
CI / tests
Version information
Final diagnostic checklist
```
# 54. Application Logging

The LUMS server uses application logging for operational events.

Inspect the most recent container logs:

```bash id="q6m2v8"
sudo docker logs \
    --tail 200 \
    lums
```

Follow the logs live:

```bash id="r4k9p1"
sudo docker logs \
    -f \
    lums
```

Important events include:

```text id="c7n3x5"
Client reports
Update job creation
Update job claiming
HTTP requests
Application errors
Gunicorn errors
```

If a request appears to disappear without a visible application result, check both the application log and the Gunicorn access/error output.

---

# 55. Audit Logging

Security-sensitive administrative actions are recorded separately through the LUMS audit log.

The audit log is intended to provide traceability for actions such as:

```text id="m8q2v6"
Login attempts
Successful logins
Failed logins
Rate-limited logins
Logout
Client creation
Client token rotation
Client disable/delete operations
```

Audit logging should not be confused with normal application logging.

Application logs are primarily operational.

Audit logs provide security-relevant historical information.

---

# 56. Login Problems

If the login page is reachable but authentication fails, first inspect the server logs:

```bash id="p3r7k9"
sudo docker logs \
    --tail 200 \
    lums
```

Check:

```text id="x5m1c8"
Username
Account enabled state
Password
Session state
CSRF protection
Rate limiting
```

Repeated failed login attempts may trigger the configured login rate-limiting behavior.

Do not repeatedly submit credentials while diagnosing a rate-limited account.

---

# 57. Session Problems

If a previously working session suddenly becomes invalid, check whether:

```text id="v8q4n2"
The user logged out
The session was revoked
The Flask application secret changed
The browser still holds an old session cookie
```

A changed application secret invalidates existing sessions.

If necessary, remove the old browser session for the LUMS site and log in again.

Do not disable CSRF protection as a troubleshooting workaround.

---

# 58. Client Token Problems

Client authentication uses client-specific tokens.

If a client suddenly receives authentication failures after a token rotation:

1. Verify that the client has the current token.
2. Verify the configured server URL.
3. Verify the client service configuration.
4. Restart the client service if required.
5. Trigger a controlled report.
6. Inspect the server logs.

On the client:

```bash id="n7c3m5"
sudo systemctl cat lums-agent.service
```

Then inspect:

```bash id="w2r8k6"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

The previous token is intentionally invalid after a successful rotation.

---

# 59. Secret File Problems

The production container does not rely on the Flask secret being exposed as a normal environment variable.

The secret is supplied through a protected mounted file.

Inspect the container configuration:

```bash id="f6m3q9"
sudo docker inspect lums \
    --format '{{json .Config.Env}}'
```

The expected configuration includes the secret-file reference rather than the plaintext secret itself.

Inspect the mount:

```bash id="c8v1x5"
sudo docker inspect lums \
    --format '{{json .Mounts}}'
```

The secret should be mounted read-only.

Never print the contents of the secret into a terminal log or paste it into an issue, commit or chat.

---

# 60. Container Is Unexpectedly Writable

The production container uses a read-only root filesystem.

Check:

```bash id="m4q7p2"
sudo docker inspect lums \
    --format '{{.HostConfig.ReadonlyRootfs}}'
```

Expected:

```text id="k9x2c6"
true
```

Persistent application data belongs in the Docker volume.

Temporary writable data belongs in the configured `/tmp` tmpfs.

Do not make the complete container filesystem writable merely to work around an application error.

---

# 61. Container Has Unexpected Capabilities

The production container drops Linux capabilities.

Check:

```bash id="r5n8v3"
sudo docker inspect lums \
    --format '{{json .HostConfig.CapDrop}}'
```

Expected:

```text id="y7m1q4"
["ALL"]
```

Also verify:

```bash id="p2c6k8"
sudo docker inspect lums \
    --format '{{.HostConfig.Privileged}}'
```

Expected:

```text id="d4v9x1"
false
```

Do not enable privileged mode as a troubleshooting shortcut.

---

# 62. Container Runs as the Wrong User

LUMS is intended to run as the non-root application user.

Check:

```bash id="q8m3r5"
sudo docker exec lums id
```

The application should run as the dedicated `lums` user rather than root.

If the container unexpectedly runs as root, inspect the image and container configuration before continuing with production operation.

---

# 63. LUMS Cannot Write Application Data

Because the root filesystem is read-only, only explicitly writable locations should be used for runtime data.

The primary persistent database path is:

```text id="x6k2m9"
/var/lib/lums/lums.db
```

If the application reports a permission or read-only filesystem error:

1. Check the Docker volume.
2. Check the container user.
3. Check the mount configuration.
4. Check the application logs.

Inspect mounts:

```bash id="b4n7v2"
sudo docker inspect lums \
    --format '{{json .Mounts}}'
```

Do not disable the read-only root filesystem to hide the underlying permission problem.

---

# 64. Tests Fail Locally

Run the complete test suite from the project environment:

```bash id="c5r8m1"
.venv-test/bin/python -m pytest -q
```

The expected current baseline is:

```text
79 passed
```

If tests fail after a code change:

1. Read the first failing test.
2. Determine whether the failure is caused by the change.
3. Fix the implementation or test as appropriate.
4. Run the targeted test again.
5. Run the complete suite again.

Do not ignore a failing test merely because another test succeeds.

---

# 65. GitHub Actions CI Fails

LUMS uses GitHub Actions for the test workflow.

The workflow:

```text id="n3v7q2"
Checkout
    ↓
Python 3.13
    ↓
Install test dependencies
    ↓
pytest
```

If CI fails while local tests pass, compare:

```text id="m5c9x4"
Python version
Dependencies
Repository state
Workflow changes
Test environment
```

Inspect the workflow file:

```text
.github/workflows/tests.yml
```

A local success does not automatically prove that the CI environment is correct.

---

# 66. Documentation Appears Outdated

LUMS documentation contains multiple areas that can change independently:

```text id="v2k8p6"
Server
Agent
Watcher
Docker deployment
Security model
RBAC
Installation
Troubleshooting
```

If documentation contradicts the running system, verify the implementation first.

Useful checks include:

```bash id="q4m7n1"
git status
```

and:

```bash id="r9c3x5"
git log --oneline -5
```

Then inspect the actual running container:

```bash id="w6p2k8"
sudo docker exec lums \
    python3 --version
```

Documentation should describe the current implementation rather than an older development state.

---

# 67. Version Information

LUMS currently has component versions that should not be confused with a stable project release.

Current component versions:

```text id="k3r8m5"
LUMS Agent   1.7.0
Watcher      1.2.1
```

The project itself does not currently have a stable release/tag that should be treated as a production release identifier.

Therefore, do not invent a release number when troubleshooting.

Use the Git commit and component versions when identifying the exact software state.

---

# 68. Collect a Diagnostic Snapshot

When a problem cannot be resolved immediately, collect a non-secret diagnostic snapshot.

Start with:

```bash id="f7m2c9"
echo "=== CONTAINER ==="
sudo docker ps -a --filter name=lums

echo
echo "=== CONTAINER CONFIG ==="
sudo docker inspect lums \
    --format 'ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} User={{.Config.User}}'

echo
echo "=== SERVER LOG ==="
sudo docker logs --tail 100 lums

echo
echo "=== AGENT ==="
sudo systemctl status lums-agent.service --no-pager

echo
echo "=== WATCHER ==="
sudo systemctl status lums-agent-watcher.service --no-pager

echo
echo "=== AGENT LOG ==="
sudo journalctl -u lums-agent.service -n 100 --no-pager

echo
echo "=== WATCHER LOG ==="
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager
```

Before sharing the output, check it for:

```text id="n4q8v6"
Tokens
Secrets
Private keys
Passwords
Session data
Internal information that should remain private
```

Never include plaintext client tokens or the LUMS secret in a diagnostic report.

---

# 69. Final Troubleshooting Checklist

Use this checklist before making destructive changes.

```text id="p6c2r9"
[ ] Is the LUMS container running?
[ ] Is localhost:5050 reachable?
[ ] Is Nginx running?
[ ] Is HTTPS working?
[ ] Is the TLS certificate valid?
[ ] Is the LUMS secret mounted correctly?
[ ] Is the container running as the lums user?
[ ] Is the root filesystem still read-only?
[ ] Are all capabilities dropped?
[ ] Is privileged mode disabled?
[ ] Is the agent service working?
[ ] Is the watcher service working?
[ ] Are the timers active?
[ ] Is the client token current?
[ ] Is the client report accepted?
[ ] Is the client idle state supported?
[ ] Is the client actually idle?
[ ] Is a job pending?
[ ] Can the job be claimed?
[ ] Is the native package manager healthy?
[ ] Is another package operation running?
[ ] Did the package operation actually succeed?
[ ] Was the result accepted by the server?
[ ] Is the reboot state correct?
[ ] Is SQLite integrity OK?
[ ] Is the user's RBAC role correct?
[ ] Do server logs show the expected request?
[ ] Do audit logs contain the expected security event?
[ ] Does the complete test suite pass?
[ ] Does GitHub Actions pass?
```

---

# 70. Recovery Principle

When troubleshooting LUMS, prefer the smallest reversible action.

Recommended order:

```text id="x8m4q2"
Observe
   ↓
Read logs
   ↓
Verify configuration
   ↓
Verify service state
   ↓
Verify native package-manager state
   ↓
Verify database integrity
   ↓
Retry the smallest affected operation
   ↓
Create a backup
   ↓
Perform controlled recovery
```

Avoid destructive shortcuts such as:

```text id="c5n9v7"
Deleting the Docker volume
Deleting the SQLite database
Removing package-manager lock files
Disabling security controls
Running the container privileged
Exposing the application publicly
Printing secrets for debugging
```

The goal of troubleshooting is to identify the actual failure while preserving the security and persistence guarantees of the system.

---

# 71. End of Troubleshooting Guide

If the issue is still unresolved after the checks above, document:

```text id="m2r7k4"
1. What was expected?
2. What actually happened?
3. Which client was affected?
4. Which job was affected?
5. Which services were running?
6. What do the relevant logs show?
7. What configuration was verified?
8. What recovery steps were already attempted?
9. Was any data changed?
10. Can the problem be reproduced?
```

This information provides a reliable starting point for further diagnosis without unnecessarily changing the production system.

