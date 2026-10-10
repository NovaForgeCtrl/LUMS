# LUMS — Administration Guide

> **Linux Update Management without the noise.**

This guide describes the day-to-day administration and operation of LUMS after the server and clients have been installed.

It focuses on administrative tasks performed through the LUMS web interface and on controlled operational tasks on the LUMS server and managed clients.

Installation procedures are documented separately in `installation.md`.

Troubleshooting procedures are documented separately in `troubleshooting.md`.

Security architecture and audit information are documented separately in `security.md`.

---

## 1. Administration Overview

LUMS provides centralized administration of Linux software inventory, available updates, package operations, update jobs, managed clients, users, and operational history.

The administrative model separates responsibilities between three roles:

* **Administrator**
* **Operator**
* **Viewer**

The role assigned to a user determines which administrative functions are available.

LUMS also separates server-side administrative operations from client-side package execution.

The normal operational flow is:

```text
Administrator / Operator
        │
        ▼
   LUMS Web UI
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
   Managed Client
        │
        ▼
 APT / pacman / system
        │
        ▼
      Result
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
    Web Interface
```

The LUMS server does not directly execute package-management commands on managed clients.

Package operations are executed by the LUMS Agent installed on the managed system.

---

## 2. Administrative Responsibilities

LUMS administration can be divided into several areas.

### User Administration

Administrators manage:

* LUMS users
* user roles
* account status
* administrative access

User management is restricted to the **Administrator** role.

Operators cannot create or manage LUMS users.

Viewers have no user-management permissions.

---

### Client Administration

Administrators manage:

* registered clients
* client status
* client authentication
* client tokens
* token rotation
* client enablement and disablement

Client administration is intentionally restricted because client authentication determines which systems are allowed to report to LUMS.

---

### Update Administration

Administrators and Operators can:

* view available updates
* create update jobs
* execute package operations
* review update history
* manage individual packages
* perform system updates

The Viewer role cannot perform update operations.

---

### Package Administration

LUMS supports package-management operations through the native package manager of the client.

Current supported package-management backends include:

* **APT/dpkg** for Debian-based systems
* **pacman** for Arch Linux

LUMS does not replace the operating-system package manager.

Instead, LUMS provides a centralized interface for requesting and tracking package operations.

---

### Operational Administration

Administrators and Operators may need to monitor:

* running update jobs
* failed jobs
* completed jobs
* client reporting
* reboot requirements
* package-manager errors
* audit activity

The detailed troubleshooting procedures for these conditions are documented in `troubleshooting.md`.

---

## 3. Administrative Roles

LUMS currently provides three roles.

| Role          | Purpose                                  |
| ------------- | ---------------------------------------- |
| Administrator | Full administrative control              |
| Operator      | Day-to-day operational management        |
| Viewer        | Read-only client and software visibility |

The role is enforced server-side.

Hiding an interface element is therefore not considered a security control by itself.

Unauthorized API operations must also be rejected by the server.

---

## 4. Administrator

The Administrator role provides the highest level of LUMS application privileges.

Administrators can:

* view managed clients
* view installed software
* view available updates
* create and execute update jobs
* review update history
* perform package-management operations
* perform system maintenance
* create clients
* disable clients
* rotate client tokens
* create and manage LUMS users
* assign user roles

Administrator privileges should be granted only to users who require full administrative access.

Administrative accounts should not be used for routine read-only monitoring when an Operator or Viewer account is sufficient.

---

## 5. Operator

The Operator role is intended for day-to-day update and system administration.

Operators can:

* view managed clients
* view installed software
* view available updates
* create and execute update jobs
* review update history
* perform package-management operations
* perform system maintenance

Operators cannot:

* create or manage LUMS users
* assign user roles
* create or disable clients
* rotate client tokens

This separation allows routine update operations without granting full account and client-management privileges.

---

## 6. Viewer

The Viewer role provides read-only visibility.

Viewers can:

* view managed clients
* view installed software

The following administrative functions are unavailable to Viewers:

* available update management
* update-job creation
* update-job execution
* update history
* package management
* system maintenance
* user management
* client management
* token rotation

The corresponding mutating API operations are also protected server-side.

Viewer access is therefore intended for users who need visibility without operational control.

---

## 7. Role Selection Guidelines

Use the smallest role that provides the required functionality.

### Administrator

Use when the user must manage:

* users
* roles
* clients
* client authentication
* tokens
* updates
* packages
* system operations

### Operator

Use when the user needs to perform routine operational work such as:

* checking updates
* installing packages
* removing packages
* updating packages
* executing update jobs
* reviewing job history

### Viewer

Use when the user only needs visibility into:

* clients
* installed software

---

## 8. Administrative Security Principle

LUMS administration follows the principle of least privilege.

Administrative access should be limited to the functionality required for the user's task.

In particular:

* do not use Administrator accounts for routine viewing
* do not share accounts between administrators
* do not share client tokens
* do not place credentials in documentation
* do not expose client tokens in screenshots or logs
* do not bypass the LUMS web interface by modifying the database directly unless a documented recovery procedure explicitly requires it

When an administrative operation fails, investigate the cause before changing persistent state.

Use the principle:

> **Observe first. Change second. Verify third.**

---

## 9. Administrative Workflow

A normal administrative workflow should follow this sequence:

```text
1. Authenticate
      │
      ▼
2. Verify role
      │
      ▼
3. Select client / operation
      │
      ▼
4. Review current state
      │
      ▼
5. Perform required operation
      │
      ▼
6. Monitor job
      │
      ▼
7. Verify result
      │
      ▼
8. Review history / audit information
```

Administrative actions should always be verified after execution.

A successful API request does not by itself prove that the requested package or system operation completed successfully.

The final state reported by the managed client is the relevant operational result.

---

## 10. Separation of Documentation

The LUMS documentation set is intentionally divided into separate operational guides.

| Document             | Purpose                                 |
| -------------------- | --------------------------------------- |
| `installation.md`    | Installation and initial deployment     |
| `administration.md`  | Day-to-day administration               |
| `security.md`        | Security architecture and audit results |
| `troubleshooting.md` | Diagnosis and recovery                  |

This guide should therefore avoid duplicating detailed installation and troubleshooting procedures.

Instead, it describes what administrators can manage, what each operation means, and how normal administrative workflows are performed.

## 11. User Management

User management is available only to users with the **Administrator** role.

Administrators can create and manage LUMS application accounts through the dedicated user-management interface.

User accounts are separate from managed-client authentication.

A LUMS user authenticates to the web application with an application account.

A managed client authenticates to the LUMS API with a client token.

These authentication mechanisms must not be confused.

```text
LUMS User
    │
    │ username + password
    ▼
Web Interface
    │
    ▼
LUMS Application

Managed Client
    │
    │ client token
    ▼
LUMS API
```

---

## 12. Creating Users

Only Administrators can create new LUMS users.

When creating a user, the Administrator specifies:

* username
* password
* role

Available roles are:

* `administrator`
* `operator`
* `viewer`

The server validates the supplied values before creating the account.

Passwords are not stored as plaintext.

LUMS uses Argon2-based password hashing for application credentials.

After creation, verify that:

* the username appears in the user list
* the assigned role is correct
* the account is enabled
* the user can authenticate successfully

Do not transmit passwords through documentation, tickets, screenshots, or other insecure channels.

---

## 13. User Roles

User roles should be assigned according to the minimum required privilege.

| Role          | User Management | Client Management | Updates | Package Management | Read-only Access |
| ------------- | --------------: | ----------------: | ------: | -----------------: | ---------------: |
| Administrator |             Yes |               Yes |     Yes |                Yes |              Yes |
| Operator      |              No |                No |     Yes |                Yes |              Yes |
| Viewer        |              No |                No |      No |                 No |              Yes |

Role enforcement occurs on the server.

The web interface reflects the assigned role, but the server remains the authoritative security boundary.

---

## 14. Disabling User Accounts

When an account should no longer be allowed to access LUMS, disable the account rather than sharing or repurposing the credentials.

Examples include:

* an administrator leaving the project
* an operator no longer requiring access
* temporary removal of administrative access
* security response to a compromised account

After disabling an account, verify that authentication is rejected.

Existing authenticated sessions should also be considered during account-security investigations.

Do not manually modify the `users` table unless a documented recovery procedure explicitly requires database-level intervention.

---

## 15. Password Administration

Passwords are application credentials and must be treated as sensitive information.

Administrators should ensure that:

* passwords are not shared
* passwords are not stored in Git
* passwords are not placed in documentation
* passwords are not included in screenshots
* passwords are not written into shell history unnecessarily
* users receive their credentials through an appropriate secure channel

LUMS stores password hashes rather than plaintext passwords.

If a password is suspected to be compromised, replace it through the appropriate account-management procedure rather than attempting to recover the original password.

---

## 16. Sessions

LUMS uses authenticated application sessions for web access.

Session handling is part of the application's security boundary.

Administrators should treat an unexpected authenticated session as a security event if the associated account should no longer have access.

Relevant situations include:

* disabled account still appearing active
* unexpected administrative access
* suspected credential compromise
* unexpected browser session
* security investigation

For detailed session and authentication troubleshooting, see `troubleshooting.md`.

---

## 17. Login Rate Limiting

LUMS applies rate limiting to repeated failed login attempts.

The current progression is:

| Failed attempts |     Lockout |
| --------------: | ----------: |
|               5 |  30 seconds |
|               6 |  60 seconds |
|               7 | 120 seconds |
|              8+ | 300 seconds |

Rate-limit state is persisted in SQLite.

A successful login clears the applicable failed-attempt state.

Repeated authentication failures should be investigated rather than bypassing the rate limiter.

Possible causes include:

* incorrect credentials
* outdated saved credentials
* an automated client using incorrect credentials
* repeated manual login attempts
* a possible credential attack

---

## 18. Client Management

Managed clients are Linux systems running the LUMS Agent.

A client provides LUMS with information such as:

* client identity
* installed software
* available updates
* package-management results
* update-job results
* reboot state
* operational status

The LUMS server stores the client state and exposes it through the web interface.

The client performs the actual package-management operations locally.

---

## 19. Client Authentication

Each managed client authenticates to LUMS using a client token.

The token acts as a credential for the managed client.

Treat client tokens with the same care as passwords.

Never:

* commit tokens to Git
* place tokens in public documentation
* include tokens in screenshots
* paste tokens into issue trackers
* expose tokens in diagnostic output
* share one client's token with another client

A token should only be installed on the client for which it was issued.

---

## 20. Client Registration

A new client must first be registered with LUMS.

The registration process establishes the server-side client identity and authentication credential.

After registration:

1. install the LUMS Agent
2. configure the client token
3. configure the LUMS server endpoint
4. establish TLS trust
5. perform an initial agent run
6. verify that the client reports successfully
7. confirm the client appears in the LUMS interface

A client should not be considered operational merely because the Agent service starts successfully.

The server must receive and accept a valid client report.

---

## 21. Client Status

The client view should be used to distinguish between different operational states.

Examples include:

* client registered but not reporting
* client reporting normally
* client reporting stale information
* client disabled
* client authentication failure
* client-side package-manager failure

When a client stops reporting, first determine whether the problem is:

1. network connectivity
2. TLS trust
3. client authentication
4. Agent execution
5. server availability
6. server-side processing

Avoid changing client credentials before establishing which layer is actually failing.

---

## 22. Client Token Rotation

Client tokens can be rotated when required.

Typical reasons include:

* suspected token exposure
* credential rotation policy
* administrative maintenance
* replacement of a client configuration
* security incident response

Token rotation changes the credential accepted for the client.

After rotation:

1. obtain the new client token
2. update the client configuration
3. run the Agent
4. verify successful authentication
5. verify the resulting client report
6. confirm normal reporting resumes

Do not remove the old client configuration until the new authentication path has been verified.

---

## 23. Disabling a Client

A client can be disabled when it should no longer participate in LUMS operations.

Examples include:

* system decommissioning
* temporary maintenance
* client replacement
* suspected credential compromise

Before disabling a client, check whether active update jobs are associated with it.

After disabling:

* verify that the client is no longer treated as operational
* review relevant update-job history
* preserve audit information required for investigation

Do not delete persistent client data merely because a client is temporarily offline.

---

## 24. Client Administration Checklist

When adding or changing a client, verify the complete chain:

```text
[ ] Client exists in LUMS
[ ] Client is enabled
[ ] Client token is valid
[ ] TLS trust is valid
[ ] LUMS Agent is installed
[ ] Agent configuration is valid
[ ] Initial report succeeds
[ ] Client appears in the Web UI
[ ] Installed software is reported
[ ] Available updates are reported
[ ] Update jobs can be tracked
[ ] Results are returned correctly
```

A client is operational only when the complete reporting and authentication chain works.

---

## 25. Administrative Principle

User administration and client administration should remain separate.

A LUMS application account determines **what a person is allowed to do**.

A client token determines **which managed system is allowed to communicate with LUMS**.

```text
Application User
      │
      └── Role / Permissions

Managed Client
      │
      └── Client Token / Identity
```

Do not use one mechanism as a substitute for the other.

## 26. Software Inventory

LUMS maintains software information reported by managed clients.

The software inventory allows administrators and operators to determine which packages are installed on a client.

The inventory is collected by the LUMS Agent and reported to the server.

The server then makes the reported information available through the client interface.

The inventory should be treated as a snapshot of the client's reported state.

It does not replace the native package manager.

---

## 27. Installed Software

The **Installed Software** section displays packages reported by the selected client.

Administrators and Operators can use the local package filter to narrow the displayed inventory.

The installed-software filter is a local interface function.

It is separate from the package-management search.

This distinction is important:

```text
Installed Software
    │
    └── Filter already reported package inventory

Package Management
    │
    └── Search the client's package repositories
```

An installed package may therefore not appear in the package-management search if it is no longer available in a configured repository.

---

## 28. Available Updates

LUMS also collects information about packages for which updates are available.

Available-update information is generated on the managed client using its native package-management system.

The reported information can be used to identify packages that require attention.

Before creating an update job, review:

* client identity
* package name
* currently installed version
* available version
* package status
* whether the client is currently reachable

Do not assume that every available update should immediately be installed.

Operational requirements, maintenance windows, application dependencies, and client state should be considered before execution.

---

## 29. Package Management

LUMS provides centralized package-management operations for supported Linux clients.

Current package-management actions include:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

The operation is requested through LUMS but executed locally by the LUMS Agent.

The Agent delegates the actual package operation to the native package manager.

```text
LUMS Web UI
      │
      ▼
LUMS API
      │
      ▼
Update Job
      │
      ▼
LUMS Agent
      │
      ├── APT / dpkg
      │
      └── pacman
```

LUMS therefore remains independent of the package database and package-management implementation of the operating system.

---

## 30. Package Search

The **Package Management** interface provides a package search that is separate from the installed-software filter.

The search requests package information from the managed client.

On Debian-based systems, the Agent uses the APT package-management tools.

On Arch Linux, the Agent uses `pacman`.

Search results may contain:

* package name
* package version
* package description
* repository information where available

Package search does not install anything.

A search is therefore a read-only operation.

---

## 31. Installing a Package

Administrators and Operators can create package-installation jobs.

The normal workflow is:

1. select the managed client
2. open **Package Management**
3. search for the required package
4. review the result
5. select the installation action
6. create the job
7. monitor execution
8. verify the result
9. refresh or recheck the installed software

The package is installed by the Agent using the native package manager.

The successful creation of the job does not mean that installation has already completed.

The final job result must be checked.

---

## 32. Removing a Package

Package removal follows the same controlled job workflow.

Before removing a package, verify:

* the correct client
* the correct package
* the intended operation
* whether other software depends on the package

After execution, verify the resulting job status and the client's reported software state.

LUMS does not bypass package-manager dependency handling.

The native package manager remains responsible for resolving the operation.

---

## 33. Updating a Package

A specific package can be updated when an update is available.

The workflow is:

```text
Available Update
      │
      ▼
Review Package
      │
      ▼
Create UPDATE_PACKAGE Job
      │
      ▼
Agent Execution
      │
      ▼
Result Validation
```

LUMS validates the package information before creating the corresponding update job.

If the package is no longer listed as updateable, the job request should not be treated as a valid update operation.

This prevents stale update information from being blindly executed.

---

## 34. Updating the System

`UPDATE_SYSTEM` performs a broader system update using the client's native package-management mechanism.

This operation affects more than one package and should therefore be treated as a maintenance operation.

Before starting a system update, verify:

* client availability
* maintenance window
* currently running jobs
* package-manager state
* available disk space where relevant
* whether a reboot may be required

After the update, verify:

* job result
* client report
* installed software
* available updates
* reboot state

---

## 35. Update Jobs

All mutating package and update operations are represented as LUMS update jobs.

This provides a common execution and tracking model.

Typical job lifecycle:

```text
PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► FAILED
   │
   ▼
SUCCESS
```

A job may also require additional handling when the client becomes unavailable or execution is interrupted.

The job history should be used as the authoritative operational record rather than relying solely on the current client view.

---

## 36. Job Creation

Before creating an update job, verify the intended operation carefully.

Check:

* client
* action
* package
* target version where applicable
* current package state
* maintenance requirements

Supported actions include:

| Action            | Purpose                      |
| ----------------- | ---------------------------- |
| `INSTALL_PACKAGE` | Install a package            |
| `REMOVE_PACKAGE`  | Remove a package             |
| `UPDATE_PACKAGE`  | Update a specific package    |
| `UPDATE_SYSTEM`   | Perform a system-wide update |

Update-job creation is restricted to **Administrator** and **Operator** roles.

Viewers cannot create update jobs.

---

## 37. Job Execution

After creation, the job is processed by the LUMS Agent.

The Agent receives the job and executes the requested operation locally.

The server tracks the resulting state.

The Agent does not treat a successful HTTP request as proof that the package operation succeeded.

Instead, the actual package-manager result is returned to LUMS.

This distinction is important:

```text
API request accepted
        ≠
Package operation successful
```

The final execution result must therefore always be checked.

---

## 38. Job Results

A completed job should contain an explicit result.

Relevant outcomes include:

* successful execution
* failed execution
* package-manager error
* interrupted execution
* recovery-related state
* reboot-related state where applicable

Administrators and Operators should inspect the result when a job fails rather than immediately repeating the same operation.

Repeated execution without understanding the original failure can make diagnosis more difficult.

---

## 39. Job History

The update history provides an operational record of previous update activity.

Use it to answer questions such as:

* Was this package already updated?
* Which client executed the operation?
* When was the job created?
* When did execution begin?
* When did execution finish?
* Did the operation succeed?
* Did the package manager report an error?

Historical job information is especially important when investigating repeated failures or interrupted maintenance operations.

---

## 40. Failed Jobs

When a job fails:

1. record the client and job ID
2. inspect the job result
3. determine whether the failure occurred on the server or client
4. inspect the relevant Agent logs
5. inspect the native package-manager state
6. correct the underlying problem
7. retry only after the cause is understood

Common causes include:

* unavailable repositories
* package-manager locks
* network problems
* invalid package requests
* dependency conflicts
* insufficient disk space
* interrupted package operations
* client authentication or communication problems

Detailed diagnostic procedures are documented in `troubleshooting.md`.

---

## 41. Package-Manager Locks

APT and pacman may prevent concurrent package operations.

If a package-management operation fails because the package manager is already in use:

* identify the active package-management process
* determine which operation is running
* wait for the legitimate operation to finish when appropriate
* retry the LUMS operation afterward

Do **not** blindly delete package-manager lock files while the package manager is running.

Removing a lock file does not resolve the underlying concurrent operation and can damage package-management state.

---

## 42. Idle-Aware Execution

LUMS can use client idle information when determining whether an update job should execute.

This mechanism is intended to avoid interrupting active interactive use of a managed system.

Idle detection is performed by the Agent on the client.

If idle information is unavailable, the Agent must report that condition rather than inventing an idle state.

Administrators should distinguish between:

* client is idle
* client is active
* idle detection unavailable
* client unreachable

These states have different operational meanings.

---

## 43. Update Execution Monitoring

During maintenance, monitor:

* job state
* client connectivity
* Agent activity
* package-manager result
* reboot requirement

Do not assume that a job remaining in `RUNNING` indefinitely means that the package manager is still working.

If execution appears stuck, investigate the client and Agent state before creating another job.

---

## 44. Reboot Requirements

Some package and system updates may require a reboot.

LUMS tracks reboot-related state reported by the managed client.

After a system update:

1. inspect the reported reboot state
2. determine whether a reboot is required
3. perform the reboot during an appropriate maintenance window
4. allow the Agent to report again
5. verify the client returns to normal operation

A reboot requirement should not automatically be interpreted as an update failure.

---

## 45. Operational Update Checklist

For routine package maintenance:

```text
[ ] Correct client selected
[ ] Client is reachable
[ ] Current software state reviewed
[ ] Available updates reviewed
[ ] Correct package/action selected
[ ] Maintenance requirements checked
[ ] Update job created
[ ] Job execution monitored
[ ] Job result verified
[ ] Installed software verified
[ ] Available updates rechecked
[ ] Reboot state checked
[ ] Job history reviewed if required
```

The operation is complete only after the resulting client state has been verified.

---

## 46. Package Management Principle

LUMS provides centralized orchestration and visibility.

The managed operating system remains responsible for actual package management.

Therefore:

> **LUMS requests and tracks the operation. The native package manager performs it.**

This separation allows LUMS to manage different Linux systems while preserving the package-management semantics of each operating system.

## 47. Job Recovery

LUMS is designed to handle interrupted update jobs without blindly repeating operations that have already completed successfully.

Update execution uses checkpoint information to track progress.

This is particularly important when:

* the Agent is interrupted
* the client reboots
* the server is restarted
* network communication is temporarily unavailable
* a package operation completes before the result is reported

The recovery mechanism uses the recorded job state to determine which work still needs to be performed.

---

## 48. Package-Level Checkpointing

Jobs containing multiple package operations are processed individually.

A successful package operation is recorded before the Agent proceeds to the next operation.

Conceptually:

```text
Job
 │
 ├── Package A → SUCCESS
 │
 ├── Package B → SUCCESS
 │
 ├── Package C → interrupted
 │
 └── Package D → PENDING
```

After recovery, already completed package operations should not be executed again unnecessarily.

The remaining work can then continue from the recorded state.

This reduces the risk of repeating package operations after an interruption.

---

## 49. Interrupted Jobs

When an update job is interrupted, do not immediately create a replacement job.

First determine:

1. which job was interrupted
2. which package operation was active
3. which package operations already succeeded
4. whether the package manager completed the operation
5. whether the Agent recovered the job automatically
6. whether the client requires a reboot

The existing job history and Agent logs should be inspected before manual intervention.

---

## 50. Agent Recovery

The Agent is responsible for continuing recoverable work after an interruption.

Recovery should preserve successful package results wherever possible.

If a package operation is already recorded as successful, recovery must not blindly execute that same operation again.

If recovery cannot safely determine the state of an operation, the condition should be treated as an operational problem and investigated.

Do not manually change job states in the database simply to make a job appear complete.

---

## 51. Server Restart During a Job

A restart of the LUMS server does not necessarily mean that the client-side package operation was interrupted.

The server and client have separate execution states.

After a server restart:

1. verify that the LUMS container is running
2. verify database availability
3. verify the client can communicate with LUMS
4. inspect affected update jobs
5. check Agent reports
6. verify the final package state

The client-side execution result remains the important source of truth for the package operation.

---

## 52. Client Restart During a Job

A client restart may interrupt Agent execution or occur because the update itself requires a reboot.

These situations must be distinguished.

### Expected reboot

The update completed and the system requires a reboot.

### Unexpected interruption

The system restarted before the operation completed or before the result could be reported.

After the client returns:

1. allow the Agent to start normally
2. verify communication with LUMS
3. inspect the affected job
4. verify package state
5. check reboot status
6. allow recovery to continue when applicable

---

## 53. Reboot Detection

LUMS can track reboot requirements reported by the managed client.

Reboot detection is not the same as detecting whether the machine is currently reachable.

These are separate states:

```text
Client reachable
        │
        ├── reboot not required
        │
        └── reboot required

Client unreachable
        │
        └── current state cannot be confirmed
```

Administrators should therefore avoid treating an unreachable client as proof that a reboot is required.

---

## 54. Post-Reboot Verification

After a required reboot:

1. wait for the operating system to become available
2. verify the Agent service or timer
3. verify client authentication
4. verify the client report
5. inspect the affected update job
6. verify installed package versions
7. verify available updates
8. check whether another reboot is required

A reboot should be considered operationally complete only after the client has successfully reported again.

---

## 55. Update Job Monitoring

Administrators and Operators should monitor jobs during planned maintenance.

Important states include:

| State     | Meaning                                  |
| --------- | ---------------------------------------- |
| `PENDING` | Job exists but execution has not started |
| `RUNNING` | Job execution is in progress             |
| `SUCCESS` | Execution completed successfully         |
| `FAILED`  | Execution completed with an error        |

A job state should always be interpreted together with its result information.

For example, a `FAILED` job should be investigated using its recorded result rather than simply retried.

---

## 56. Execution Watcher

The LUMS Agent includes a dedicated execution watcher.

The watcher is responsible for monitoring update-job execution on the client.

Its purpose is to support reliable execution handling independently from the reporting workflow.

The current watcher version is:

**Watcher 1.2.1**

The Agent version is:

**Agent 1.7.0**

These versions should be verified after client upgrades.

---

## 57. Watcher Monitoring

Administrators can inspect the watcher through systemd on the managed client.

Useful checks include:

```bash
systemctl status lums-agent-watcher.service --no-pager
```

and:

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

The timer can be inspected with:

```bash
systemctl status lums-agent-watcher.timer --no-pager
```

The exact active/inactive state of a oneshot service should be interpreted together with its timer and journal.

An `inactive (dead)` state is not automatically an error for a oneshot service.

---

## 58. Reporting and Execution Timers

LUMS separates regular client reporting from execution monitoring.

The reporting timer is responsible for scheduled Agent execution.

The watcher timer is responsible for scheduled watcher execution.

Inspect both when diagnosing client-side scheduling problems:

```bash
systemctl list-timers --all | grep lums-agent
```

Expected units include:

```text
lums-agent.timer
lums-agent-watcher.timer
```

If a timer is not running, inspect:

```bash
systemctl status lums-agent.timer --no-pager
systemctl status lums-agent-watcher.timer --no-pager
```

Then inspect the corresponding journal entries.

---

## 59. Audit Logging

LUMS records important administrative and security-relevant application actions in the audit log.

Audit information can help establish:

* which operation occurred
* which user initiated it
* which client was affected
* when the operation occurred
* whether the operation was accepted
* which administrative action was performed

Audit information should be treated as operational evidence.

It should not be casually deleted or modified.

---

## 60. Administrative Audit Events

Relevant administrative activity includes operations such as:

* user creation
* role assignment
* client management
* token rotation
* update-job creation
* package-management operations
* authentication-related security events

The exact event data depends on the operation.

Administrators should use audit information together with job history when investigating unexpected activity.

---

## 61. Audit Log Handling

Audit logs should be handled carefully.

Do not:

* modify historical audit entries to hide an operation
* expose sensitive credentials in exported logs
* publish logs containing client tokens
* publish passwords or authentication material
* copy sensitive log output into public issue trackers

If logs must be shared for troubleshooting, redact credentials and other sensitive information first.

---

## 62. Application Logs

Application logs describe the internal operation of the LUMS server.

Useful sources include:

```bash
sudo docker logs --tail 100 lums
```

For live monitoring:

```bash
sudo docker logs -f lums
```

When investigating a problem, narrow the time window where possible.

Do not automatically dump the entire production log when a smaller relevant section is sufficient.

---

## 63. Agent Logs

Client-side Agent activity can be inspected through systemd:

```bash
journalctl -u lums-agent.service --no-pager -n 100
```

For watcher activity:

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

For a specific time window, systemd journal filtering can be used.

Example:

```bash
journalctl -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Logs should be correlated with the affected job ID whenever possible.

---

## 64. Log Correlation

When investigating an update problem, correlate information across the system:

```text id="jv3j7c"
Web UI
  │
  ├── Job ID
  │
  ▼
LUMS API / Application Log
  │
  ▼
Update Job
  │
  ▼
Agent
  │
  ▼
Native Package Manager
```

This prevents the common mistake of assuming that a problem observed in one layer originated in that same layer.

---

## 65. Administrative Monitoring Checklist

During normal operation, periodically verify:

```text
[ ] LUMS container is running
[ ] HTTPS endpoint is available
[ ] Database is accessible
[ ] Clients are reporting
[ ] No unexpected failed jobs
[ ] No unexplained authentication failures
[ ] Agent timers are active
[ ] Watcher timers are active
[ ] Package-manager operations complete normally
[ ] Audit activity is available
[ ] Logs contain no unexplained recurring errors
```

The frequency of these checks should match the operational importance of the LUMS deployment.

---

## 66. Recovery Principle

When an update problem occurs, the safest administrative approach is:

```text
Observe
   │
   ▼
Identify affected job/client
   │
   ▼
Inspect state and logs
   │
   ▼
Determine actual failure point
   │
   ▼
Correct underlying problem
   │
   ▼
Allow recovery or retry
   │
   ▼
Verify final state
   │
   ▼
Document significant incidents
```

Avoid destructive recovery actions unless the actual failure state is understood.

In particular, do not manually delete jobs, database records, package-manager locks, or persistent client data merely to restore a clean-looking interface.

> **Preserve evidence first. Repair state second. Verify the result third.**

## 67. Database Administration

LUMS uses SQLite as its application database.

The production database is stored inside the persistent Docker volume:

```text
/var/lib/lums/lums.db
```

The database is persistent across container replacement as long as the Docker volume is preserved.

The database contains application state such as:

* users
* managed clients
* update jobs
* package information
* audit information
* authentication-related state
* migration state

Administrators should treat the database as critical application data.

---

## 68. SQLite Runtime Configuration

The current production SQLite baseline is:

| Setting        | Value                      |
| -------------- | -------------------------- |
| `journal_mode` | `wal`                      |
| `busy_timeout` | `5000`                     |
| `synchronous`  | `2`                        |
| `foreign_keys` | enabled by the application |

The application explicitly enables SQLite foreign-key enforcement for database connections.

Administrators should not change these settings casually.

Changes to database runtime configuration should be tested before being introduced into production.

---

## 69. Database Integrity

Database integrity should be checked when there are indications of database corruption or unexpected application behavior.

A typical SQLite integrity check is:

```bash id="f0g8sl"
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

A healthy database should return:

```text
ok
```

If the integrity check reports errors, do not continue modifying application state blindly.

Preserve the affected database and investigate the cause.

---

## 70. Database Migrations

LUMS uses application migrations to introduce database changes.

Migrations should be allowed to run through the application's normal startup and migration mechanism.

Administrators should not manually modify migration state simply to bypass an error.

After an application update, verify:

1. the container starts successfully
2. migrations complete
3. the application is reachable
4. existing users remain available
5. existing clients remain available
6. existing job history remains available

---

## 71. Persistent Docker Volume

The Docker volume containing LUMS application data is a critical persistent resource.

The production volume is:

```text
lums-data
```

Inspect it with:

```bash id="f3z2kd"
sudo docker volume inspect lums-data
```

The volume must remain attached when replacing the LUMS container.

Removing the container does **not** remove the volume automatically.

Removing the volume, however, permanently removes the persistent application data unless a separate backup exists.

---

## 72. Container Administration

The LUMS application runs inside a hardened Docker container.

The production security baseline includes:

* non-root application user
* read-only root filesystem
* dropped Linux capabilities
* `no-new-privileges`
* restricted temporary filesystems
* read-only secret mount
* dedicated persistent data volume
* localhost-only application port

The container should not be started with weaker security settings merely because troubleshooting becomes more convenient.

---

## 73. Container Status

Check the current container state with:

```bash id="4n6p2v"
sudo docker ps --filter name=lums
```

Inspect the complete runtime configuration with:

```bash id="k1q4z8"
sudo docker inspect lums
```

Important properties include:

* running state
* restart policy
* user
* read-only root filesystem
* capabilities
* security options
* port bindings
* volume mounts

---

## 74. Container Security Verification

The hardened runtime should continue to provide the expected properties.

For example:

```bash id="0u7x3n"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

The expected baseline is equivalent to:

```text
lums true false
```

Capabilities should remain dropped:

```bash id="k5n8ae"
sudo docker inspect lums \
    --format '{{json .HostConfig.CapDrop}}'
```

Expected:

```text
["ALL"]
```

Security options should include:

```text
no-new-privileges:true
```

---

## 75. Application Port

The LUMS application listens on the host through the loopback interface.

The expected mapping is:

```text
127.0.0.1:5050 → container:5000
```

Verify it with:

```bash id="b6v2w0"
sudo docker port lums
```

The application port should not be exposed directly to the LAN.

External access is provided through Nginx over HTTPS.

---

## 76. Nginx and HTTPS

Nginx provides the external HTTPS entry point for LUMS.

The normal request path is:

```text
Client Browser
      │
      ▼
HTTPS :443
      │
      ▼
Nginx
      │
      ▼
127.0.0.1:5050
      │
      ▼
LUMS Container
```

The Docker application port should remain bound to localhost.

Administrators should therefore avoid exposing port `5050` directly through the firewall or Docker configuration.

---

## 77. HTTPS Verification

After Nginx changes, always validate the configuration before reloading:

```bash id="7f1h9m"
sudo nginx -t
```

If the configuration is valid:

```bash id="4g5s2w"
sudo systemctl reload nginx
```

Then verify HTTPS:

```bash id="2w8v6c"
curl -kI https://127.0.0.1/
```

A successful HTTPS response confirms that Nginx can reach the LUMS application.

Certificate validation should also be tested using the hostname or address that administrators normally use.

Do not permanently disable certificate verification with `-k`.

---

## 78. HTTP Redirect

The HTTP endpoint should redirect clients to HTTPS.

Verify:

```bash id="w5q0rx"
curl -I http://127.0.0.1/
```

The expected behavior is an HTTP redirect to the HTTPS endpoint.

Administrative access should use HTTPS.

---

## 79. TLS Certificate Maintenance

TLS certificates and private keys are external to the Docker image.

Typical locations are:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Private keys must remain protected.

Before replacing a certificate:

1. verify the new certificate
2. verify the matching private key
3. verify file permissions
4. validate the Nginx configuration
5. reload Nginx
6. verify HTTPS
7. verify application login

Never place private TLS keys into the Git repository or Docker image.

---

## 80. Secret Management

The application secret is stored outside the container image.

The production secret is mounted read-only into the container:

```text
/etc/lums/secrets/lums_secret
        │
        ▼
/run/secrets/lums_secret
```

The application receives the secret through:

```text
LUMS_SECRET_KEY_FILE
```

Administrators must never:

* commit the secret
* print the secret
* include the secret in documentation
* expose it in screenshots
* place it into an image layer

If the secret is suspected to be exposed, treat it as compromised and follow the appropriate secret-rotation procedure.

---

## 81. Backup Strategy

LUMS data should be backed up before significant administrative changes.

At minimum, consider protecting:

* SQLite application data
* application configuration
* TLS material
* application secrets
* client configuration information
* relevant operational documentation

Backups should be stored separately from the production container and its persistent Docker volume.

A backup that exists only inside the same host or Docker volume does not provide adequate protection against loss of that host or volume.

---

## 82. Database Backup

The SQLite database should be backed up using a SQLite-aware method rather than simply copying an actively modified database file without consideration of its state.

Before performing a backup:

1. identify the production database
2. ensure the backup destination is available
3. create the backup using an appropriate SQLite-safe method
4. verify that the backup exists
5. record when it was created

Do not assume that a successful file copy automatically means that a valid recoverable database backup exists.

---

## 83. Backup Verification

A backup is not considered reliable until it has been tested.

Periodically verify that a backup can be:

* read
* opened as SQLite data
* checked for integrity
* restored into an isolated test environment

For example, an extracted test copy can be checked with:

```bash id="p3v7cx"
sqlite3 /path/to/test-copy.db \
    "PRAGMA integrity_check;"
```

Expected result:

```text
ok
```

A production backup should never be tested by overwriting the active production database.

---

## 84. Restore Principle

Restoration is a controlled administrative operation.

Before restoring:

1. identify the correct backup
2. verify its integrity
3. determine the required recovery point
4. stop or isolate application activity as appropriate
5. preserve the current production state
6. restore the backup
7. verify database integrity
8. start the application
9. verify migrations
10. verify users and clients
11. verify job history
12. verify normal client reporting

Do not overwrite the only copy of the production database during recovery.

---

## 85. Restore Verification

After a restore, verify at minimum:

```text id="q6r2yh"
[ ] Container starts
[ ] Database opens
[ ] SQLite integrity check passes
[ ] Users are present
[ ] Roles are correct
[ ] Clients are present
[ ] Client authentication works
[ ] Job history is present
[ ] Audit information is available
[ ] HTTPS works
[ ] Clients can report
[ ] New operations can be created
```

A restore is complete only after the application and its managed clients have been verified.

---

## 86. Server Backup Principle

The most important administrative rule for persistent LUMS data is:

> **Never perform a destructive database or volume operation without a verified recovery path.**

In particular, do not remove `lums-data` merely because the container is being rebuilt or replaced.

Container replacement and persistent-data deletion are separate operations.

---

## 87. Administrative Server Checklist

Before making a significant server-side change:

```text id="7h3m0p"
[ ] Current container state recorded
[ ] Current image recorded
[ ] Database backup available
[ ] Backup integrity verified
[ ] Active jobs reviewed
[ ] Client reporting state reviewed
[ ] Configuration changes documented
[ ] TLS material available
[ ] Secret handling verified
[ ] Rollback path known
```

Only after these conditions have been considered should a significant production change proceed.

---

## 88. Server Administration Principle

LUMS separates application state from the disposable application container.

```text
Disposable
└── LUMS Container

Persistent
├── SQLite Database
└── lums-data Volume

External
├── TLS Material
└── Application Secret
```

This separation allows the application container to be replaced without intentionally destroying persistent application data.

> **Replace the application when necessary. Preserve the data unless data deletion is explicitly intended.**

## 89. Routine Maintenance

Routine maintenance keeps the LUMS installation reliable and reduces the risk of unexpected operational problems.

Typical maintenance activities include:

* reviewing failed update jobs
* checking client reporting
* reviewing application logs
* reviewing audit activity
* verifying backups
* checking available disk space
* reviewing Docker container state
* checking TLS certificate validity
* reviewing security updates
* verifying the current LUMS version and image

Maintenance should be performed during an appropriate maintenance window when changes can affect production clients.

---

## 90. Maintenance Before Changes

Before performing maintenance that may affect the LUMS server:

1. review active update jobs
2. verify that clients are not undergoing unexpected maintenance
3. create or verify a current backup
4. record the current container and image state
5. document the planned change
6. ensure a rollback path exists

Do not begin maintenance by immediately stopping or deleting production components.

First establish the current state.

---

## 91. Docker Image Maintenance

LUMS application images should be rebuilt from the reviewed source tree.

Before building a new image:

```bash id="x0m7r4"
cd /opt/lums-public
```

Run the automated test suite:

```bash id="4gk1dp"
./.venv-test/bin/pytest -q
```

Only proceed when the test result is understood.

Build the new image using a distinct temporary tag:

```bash id="m8q3vz"
sudo docker build -t lums:new .
```

A temporary tag allows the currently running image to remain identifiable during the replacement process.

---

## 92. Image Verification

After building a new image, verify that the image exists:

```bash id="h6s2we"
sudo docker image inspect lums:new
```

Review the image configuration before deployment.

Where appropriate, verify:

* image digest
* base image
* application files
* installed dependencies
* image size
* exposed ports
* configured user

The image should be deployed only after the build and test results have been reviewed.

---

## 93. Controlled Container Replacement

Container replacement should be performed deliberately.

Before replacing the production container:

```text id="m3z8qk"
[ ] Tests passed
[ ] New image exists
[ ] Database backup available
[ ] Active jobs reviewed
[ ] Current image recorded
[ ] Persistent volume confirmed
[ ] Secret available
[ ] TLS configuration available
[ ] Rollback image identified
```

Stop the existing container only after these conditions have been considered.

The production container should retain the hardened runtime configuration.

Example:

```bash id="n8q2kf"
sudo docker stop lums
sudo docker rename lums lums-before-upgrade
```

Then start the new image with the established hardened configuration:

```bash id="c7w4md"
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

Do not remove `lums-before-upgrade` until the new deployment has been validated.

---

## 94. Post-Upgrade Validation

Immediately after replacing the container, verify:

```bash id="b4m7tz"
sudo docker ps --filter name=lums
```

Then inspect the logs:

```bash id="v5n2ra"
sudo docker logs --tail 100 lums
```

Verify HTTPS:

```bash id="w9x1kf"
curl -kI https://127.0.0.1/
```

Then verify the application through the normal administrative interface.

---

## 95. Persistent Data After Upgrade

Container replacement must not remove the persistent Docker volume.

Verify:

```bash id="j4p8sx"
sudo docker inspect lums \
    --format '{{json .Mounts}}'
```

Confirm that:

```text id="m7z3kc"
/var/lib/lums
```

is backed by the expected persistent volume.

Then verify:

* users still exist
* roles remain correct
* clients remain registered
* job history remains available
* audit information remains available
* migrations completed successfully

---

## 96. Security Baseline After Upgrade

After deploying a new image, verify the hardened runtime again.

Check:

```bash id="q6c3xv"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

Expected baseline:

```text id="s0r8jm"
lums true false
```

Also verify:

```text id="g4m2vx"
CapDrop = ALL
SecurityOpt = no-new-privileges:true
```

and that:

```text id="c3p9rw"
127.0.0.1:5050 → container:5000
```

remains the application exposure.

A successful application upgrade must not silently weaken the security baseline.

---

## 97. Client Communication After Upgrade

After a server upgrade, verify that managed clients can still communicate.

Check at least one representative client first.

Verify:

```text id="x8h5qk"
[ ] Client authentication succeeds
[ ] Client report is accepted
[ ] Installed software is available
[ ] Available updates are available
[ ] Update jobs can be created
[ ] Agent results are accepted
```

If multiple client platforms are deployed, verify representative systems from each supported platform.

---

## 98. Update Execution After Upgrade

Do not immediately perform a large production update after replacing the LUMS server.

First perform a controlled functional test.

A suitable test should verify the complete path:

```text id="y7k2fd"
Web UI
  ↓
API
  ↓
Update Job
  ↓
Agent
  ↓
Package Manager
  ↓
Result
  ↓
Database
  ↓
Web UI
```

Only after the controlled test succeeds should normal maintenance operations resume.

---

## 99. Rollback

Rollback should be possible when a new image causes an unexpected production problem.

Preserve:

* previous working image
* persistent data
* database backup
* previous configuration
* previous TLS material
* relevant logs

If the new container is not usable:

1. stop the new container
2. preserve it for investigation when practical
3. stop further administrative changes
4. restore the previously known-good image
5. reuse the existing persistent volume
6. start the hardened runtime
7. verify the application
8. verify clients
9. verify job state
10. investigate the failed image separately

Do not delete the persistent volume as part of a normal rollback.

---

## 100. Rollback Validation

After rollback, verify:

```text id="z1j8md"
[ ] LUMS starts
[ ] HTTPS works
[ ] Users can authenticate
[ ] Roles are correct
[ ] Clients are present
[ ] Client authentication works
[ ] Job history is available
[ ] Audit information is available
[ ] Package inventory is available
[ ] Update jobs can be tracked
[ ] Security baseline is intact
```

A rollback is complete only after the application and client communication path have been verified.

---

## 101. Emergency Administration

Emergency administration should preserve evidence and persistent state whenever possible.

Examples include:

* repeated application crashes
* database integrity errors
* widespread client authentication failures
* unexpected package-job behavior
* suspected credential exposure
* broken upgrades
* TLS failures affecting all users

The preferred sequence is:

```text id="f8k3wz"
Preserve
   ↓
Observe
   ↓
Isolate
   ↓
Recover
   ↓
Verify
   ↓
Document
```

Avoid deleting logs, databases, containers, or client records merely because they appear to be part of the problem.

---

## 102. Administrative Change Principle

Every significant production change should have three clearly defined states:

### Before

The current production state is known and recoverable.

### During

The change is performed using the documented procedure.

### After

The resulting state is verified against the expected baseline.

This makes administrative work reproducible and reduces accidental configuration drift.

---

## 103. Controlled Deinstallation

Deinstallation is a destructive administrative operation.

It should only be performed when the LUMS deployment is intentionally being removed.

Before removing LUMS:

```text id="u5r2nc"
[ ] All managed clients identified
[ ] Active update jobs reviewed
[ ] Required job history exported or preserved
[ ] Required audit information preserved
[ ] Database backup created
[ ] Backup verified
[ ] TLS material preserved if required
[ ] Application secret preserved if required
[ ] Documentation preserved
[ ] Reinstallation requirements documented
```

Do not remove persistent data before confirming that it is no longer required.

---

## 104. Removing the Container

To remove the application container after the deployment has been decommissioned:

```bash id="n2x7kc"
sudo docker stop lums
sudo docker rm lums
```

The Docker volume is intentionally **not** removed by these commands.

This allows the application data to remain available for later inspection or recovery.

---

## 105. Removing Persistent Data

Removing the LUMS Docker volume is a separate destructive operation.

Only perform this after confirming that the database and all stored application state are no longer required.

Example:

```bash id="r8w3mz"
sudo docker volume rm lums-data
```

This permanently removes the persistent application data stored in that volume.

Do not execute this command during a normal upgrade or rollback.

---

## 106. Removing Client Components

When a managed client is permanently removed from LUMS, uninstall or disable its Agent components according to the client operating-system procedure.

The client should no longer report to the LUMS server after decommissioning.

Preserve relevant job and audit information before removing the client if historical records are required.

---

## 107. Final Administrative Checklist

### User Administration

```text id="p5z8cv"
[ ] Users have appropriate roles
[ ] Administrator access is limited
[ ] Disabled accounts are reviewed
[ ] Credentials are protected
```

### Client Administration

```text id="q2m7xd"
[ ] Clients are correctly registered
[ ] Client tokens are protected
[ ] Disabled clients are reviewed
[ ] Token rotation is performed when required
[ ] Client reporting is healthy
```

### Update Administration

```text id="h6v9kt"
[ ] Available updates are reviewed
[ ] Update jobs are monitored
[ ] Failed jobs are investigated
[ ] Package operations are verified
[ ] Reboot requirements are checked
[ ] Job history is retained
```

### Server Administration

```text id="r3c8wn"
[ ] Container is running
[ ] Persistent volume is attached
[ ] SQLite integrity is healthy
[ ] HTTPS is working
[ ] TLS material is valid
[ ] Application secret is protected
[ ] Backups are available
```

### Security

```text id="v7m4qx"
[ ] RBAC remains enforced
[ ] Viewer restrictions remain intact
[ ] Client authentication works
[ ] Container remains hardened
[ ] Application port remains localhost-only
[ ] No credentials are exposed
[ ] Logs contain no unexplained sensitive information
```

---

## 108. Operational Baseline

A healthy LUMS installation should satisfy the following baseline:

```text id="d4k9sy"
Application
    ├── HTTPS available
    ├── Authentication available
    └── RBAC enforced

Server
    ├── Hardened container
    ├── Persistent database
    └── Valid migrations

Clients
    ├── Authenticated
    ├── Reporting
    ├── Software inventory available
    └── Update information available

Operations
    ├── Update jobs executable
    ├── Results recorded
    ├── Recovery supported
    └── Reboot state reported

Security
    ├── Secrets protected
    ├── Tokens protected
    ├── Audit information retained
    └── Network exposure restricted

Recovery
    ├── Backups available
    ├── Restore path known
    └── Rollback path known
```

---

## 109. Administration Complete

LUMS administration should always prioritize controlled, observable, and reversible changes.

The administrative lifecycle is:

```text id="w6f1pa"
Plan
  ↓
Observe
  ↓
Change
  ↓
Verify
  ↓
Document
  ↓
Maintain
```

The most important operational principles are:

> **Use the least privilege necessary.**

> **Preserve persistent data.**

> **Do not change state without understanding the current state.**

> **Verify the result of every significant operation.**

> **Keep a tested recovery path.**

For installation procedures, see `installation.md`.

For security architecture and audit results, see `security.md`.

For diagnosis and recovery procedures, see `troubleshooting.md`.

---

## 110. Final Administration Principle

LUMS is intended to make Linux update management predictable and observable.

Administrative work should therefore not be based on assumptions or blind repetition.

When something changes:

**Observe first. Change second. Verify third.**

When something breaks:

**Preserve evidence. Identify the failure layer. Recover deliberately.**

When something works:

**Record the result and keep the known-good baseline.**
