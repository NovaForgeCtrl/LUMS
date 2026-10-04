# LUMS

**Linux Update Management without the noise.**

LUMS is a Linux update management server designed to provide controlled, auditable, and secure software and update management for Linux clients.

Instead of relying on uncontrolled client-side update activity, LUMS provides a central management layer for software inventory, update detection, package operations, update jobs, execution monitoring, and result reporting.

LUMS is designed for environments where updates should be **visible, controlled, traceable, and recoverable**.

---

## What is LUMS?

LUMS (**Linux Update Management Server**) consists of a central server and lightweight Linux clients.

The server provides the management interface, API, authentication, authorization, job management, audit logging, and persistent state.

The client-side agent performs local package-manager operations and reports the results back to the server.

The basic architecture is:

```text
                    ┌──────────────────────┐
                    │      Web Browser      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     LUMS Server      │
                    │                      │
                    │ Web UI / API         │
                    │ Authentication       │
                    │ RBAC                 │
                    │ Job Management       │
                    │ Audit Logging        │
                    │ SQLite               │
                    └──────────┬───────────┘
                               │
                         HTTPS / API
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
      ┌─────────────────┐             ┌─────────────────┐
      │   Linux Client  │             │   Linux Client  │
      │                 │             │                 │
      │ LUMS Agent      │             │ LUMS Agent      │
      │ Package Manager │             │ Package Manager │
      │ Watcher         │             │ Watcher         │
      └─────────────────┘             └─────────────────┘
```

---

## Why LUMS?

Linux systems already provide excellent package-management tools.

LUMS does not attempt to replace them.

Instead, LUMS provides a management layer around those tools so that administrators can centrally answer questions such as:

* Which clients exist?
* Which software is installed?
* Which updates are available?
* Which packages should be installed or removed?
* Which update jobs are running?
* What happened during an update?
* Did the client successfully report the result?
* Was a reboot required?
* Can an interrupted job recover safely?
* Who initiated an administrative action?

The goal is not to hide the underlying Linux package manager.

The goal is to make its operation **manageable and auditable**.

---

## Core Features

### Client Management

LUMS maintains registered Linux clients and their authentication state.

Each client receives an individual authentication token.

Client tokens are not stored as plaintext credentials. The server stores a SHA-256 digest and validates incoming client authentication against that digest.

Administrators can:

* register clients
* disable clients
* rotate client tokens
* inspect client status
* monitor client reporting

---

### Software Inventory

Clients report their installed software to the LUMS server.

The server stores the inventory and exposes it through the management interface.

The installed-software view is intentionally separate from package-management search.

This allows administrators and read-only users to inspect installed software without automatically exposing package-management operations.

---

### Update Inventory

Clients periodically determine whether package updates are available.

The server stores the reported update information and makes it available to authorized users.

Update information can be used as the basis for controlled update jobs.

---

### Package Management

LUMS provides package-management operations through the client agent.

Supported package operations include:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

The package-management layer abstracts the underlying package manager.

Current supported package-manager families are:

* **Debian / Ubuntu:** APT / dpkg
* **Arch Linux:** pacman

Package search is also available through LUMS.

Search requests are sent to the target client, executed using the local package manager, and returned to the server for display.

---

### Update Jobs

Update operations are represented as persistent jobs.

A job can contain one or more package operations and maintains a server-side execution state.

The general lifecycle is:

```text
PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► SUCCESS
   │
   └──────────────► FAILED
```

Package-level results are tracked independently so that interrupted jobs can be recovered without unnecessarily repeating operations that already completed successfully.

---

### Controlled Execution

LUMS does not execute arbitrary shell commands supplied by the web interface.

The server creates structured jobs using validated actions and package names.

The client agent maps those actions to the appropriate local package-manager operation.

This creates a deliberate boundary between:

```text
Web UI
   ↓
API
   ↓
Validated Job
   ↓
Agent
   ↓
Package Manager
```

---

### Idle-Aware Execution

LUMS can defer update execution while a client is considered active.

The current idle threshold is **300 seconds**.

Where supported, the agent uses the local system's session/idle information through `loginctl`.

If idle detection is unavailable, LUMS does not pretend that the client is idle.

This distinction is important because **unknown idle state is not the same as confirmed idle state**.

---

### Job Recovery

Update jobs are designed to survive interruptions.

The server maintains persistent job and package-item state.

During recovery, already successful package items are not unnecessarily executed again.

This provides a checkpoint-like execution model for multi-package operations.

The goal is:

> **Recover the job, not blindly restart the entire job.**

---

### Reboot Detection

Some package operations can require a system reboot.

LUMS therefore treats reboot detection as part of update-result handling rather than assuming that a successful package-manager exit always means that the system is fully operational.

The client reports the detected reboot requirement back to the server.

---

### Client Authentication

Client communication is authenticated using per-client tokens.

Tokens are:

* individually assigned
* rotatable
* stored server-side only as SHA-256 digests
* validated before accepting client reports

Token rotation allows an administrator to invalidate a previously issued client credential without recreating the client.

---

### Auditability

Administrative and security-relevant actions are recorded through the LUMS audit-log system.

The audit trail is intended to answer:

```text
Who?
What?
When?
Against which object?
With which result?
```

This includes security-sensitive operations such as authentication-related actions, client management, user management, and update-job creation.

---

## Design Principle

LUMS follows a simple principle:

> **Make Linux update management visible, controlled, recoverable, and auditable — without hiding the Linux tools underneath.**

## Architecture

LUMS separates management, execution, and persistence into clearly defined components.

The server is responsible for orchestration and policy.

The client is responsible for local system interaction.

The package manager remains responsible for actually installing, removing, or updating software.

This separation is intentional.

```text
Browser
   │
   │ HTTPS
   ▼
┌──────────────────────────────────────────┐
│                LUMS Server                │
│                                          │
│  Web UI                                  │
│  Authentication / Sessions               │
│  RBAC                                    │
│  API                                     │
│  Client Management                       │
│  Package Search                          │
│  Update Job Management                   │
│  Audit Logging                            │
│  SQLite Persistence                       │
└───────────────────┬──────────────────────┘
                    │
                    │ HTTPS / Client API
                    ▼
┌──────────────────────────────────────────┐
│               LUMS Agent                  │
│                                          │
│  Authentication                          │
│  Inventory Reporting                     │
│  Update Detection                        │
│  Package Search                          │
│  Job Execution                           │
│  Result Reporting                        │
│  Reboot Detection                        │
│  Idle Detection                          │
└───────────────────┬──────────────────────┘
                    │
                    ▼
          ┌────────────────────┐
          │ Package Manager    │
          │                    │
          │ APT / dpkg         │
          │ pacman             │
          └────────────────────┘
```

---

## Server Components

The LUMS server provides the central management layer.

### Web Application

The web application provides the administrative interface for:

* client management
* software inventory
* update information
* update jobs
* package management
* update history
* user management
* system maintenance

The interface respects the current user's RBAC role.

Frontend visibility is therefore adapted to the user's permissions, but authorization is always enforced server-side as well.

---

### API

The API connects the web interface and Linux clients to the server-side application logic.

It handles operations such as:

* client registration and management
* client reports
* package searches
* package-search results
* update jobs
* job results
* user management
* audit events

API endpoints validate their input before performing state-changing operations.

---

### Authentication and Sessions

Administrative users authenticate through the LUMS web application.

Sessions are server-controlled and support explicit session revocation.

Authentication security includes:

* password hashing using Argon2
* session management
* session revocation
* login rate limiting
* CSRF protection
* role-based authorization

Client authentication is separate from administrative authentication.

---

### RBAC

LUMS uses role-based access control.

The current roles are:

```text
Administrator
Operator
Viewer
```

Authorization is enforced on the server.

The frontend additionally hides functionality that the current role cannot use.

This means that hiding a button is never treated as a security boundary.

---

### SQLite Persistence

LUMS uses SQLite for persistent application state.

The database stores information such as:

* users
* sessions
* clients
* client authentication state
* software inventory
* available updates
* update jobs
* package-level job results
* package-search requests and results
* audit information

The application explicitly enables SQLite foreign-key enforcement for database connections.

The current production SQLite baseline is:

```text
journal_mode = delete
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

LUMS does not rely on SQLite WAL mode in the current production configuration.

---

## Container Architecture

The LUMS server is deployed as a hardened Docker container.

The application container is intentionally treated as disposable.

Persistent application state is stored in the dedicated Docker volume:

```text
lums-data
```

The production container uses a read-only root filesystem.

Writable locations are deliberately restricted to required runtime and persistent storage paths.

The production security baseline includes:

```text
read-only root filesystem
all Linux capabilities dropped
no-new-privileges
restricted /tmp
restricted /run
read-only secret mount
dedicated persistent data volume
non-root application user
```

The application is exposed internally through:

```text
127.0.0.1:5050
```

External HTTPS access is provided through the reverse proxy.

---

## Persistent and Disposable Components

LUMS separates persistent state from replaceable runtime components.

```text
Persistent
├── SQLite database
├── client state
├── user state
├── job state
└── audit state

Disposable
├── Docker container
├── application process
└── generated runtime state
```

Replacing the application container therefore does not inherently remove the LUMS database.

This separation is important for upgrades and recovery.

---

## Client Architecture

The Linux client consists of several cooperating components.

### LUMS Agent

The agent is responsible for interaction with the LUMS server and the local Linux system.

Current agent version:

```text
1.7.0
```

The agent handles:

* authentication
* inventory collection
* update detection
* package search
* package operations
* update-job execution
* result reporting
* reboot detection
* idle-state handling

---

### Package Manager Layer

The package-manager layer provides a controlled abstraction around the native Linux package manager.

The agent does not require LUMS to replace the package manager.

Instead:

```text
LUMS Action
     │
     ▼
Package Manager Abstraction
     │
     ├── Debian / Ubuntu → APT / dpkg
     │
     └── Arch Linux      → pacman
```

This keeps distribution-specific package handling inside the client.

---

### Execution Watcher

The watcher monitors update-job execution on the client.

Current watcher version:

```text
1.2.1
```

The watcher works together with the agent and the server-side job state.

Its purpose is to ensure that jobs which are expected to execute do not remain indefinitely unprocessed.

---

## Reporting Path

Normal client reporting follows this direction:

```text
Linux Client
    │
    │ inventory / update information
    ▼
LUMS API
    │
    ▼
SQLite
    │
    ▼
Web UI
```

For example, an update check performed by the client produces information that is reported to the server and stored as the client's current update state.

The browser does not directly query the client's package manager.

---

## Package Search Path

Package search follows a different request/response flow:

```text
Browser
   │
   │ search request
   ▼
LUMS Server
   │
   │ package-search request
   ▼
Linux Client
   │
   │ APT / pacman search
   ▼
Linux Client
   │
   │ search result
   ▼
LUMS Server
   │
   ▼
Browser
```

The server therefore does not need to maintain a complete remote package repository index for every client.

The search is performed using the client's own package-management environment.

---

## Update Execution Path

An update job follows the general architecture:

```text
Browser
   │
   │ create job
   ▼
LUMS API
   │
   │ validate request
   ▼
SQLite
   │
   │ persistent job
   ▼
Linux Client
   │
   │ execute action
   ▼
APT / dpkg / pacman
   │
   │ result
   ▼
Linux Client
   │
   │ validated result
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Browser
```

This creates the central LUMS execution chain:

> **Browser → API → SQLite → Agent → Package Manager → Result → SQLite → UI**

---

## Atomic Job Claiming

Update jobs are persistent server-side objects.

Before execution, the agent must obtain a job that is eligible for execution.

Job claiming is performed atomically so that the same pending job is not unintentionally claimed by multiple execution paths.

This is particularly important when timers, retries, recovery, or multiple client-side processes are involved.

---

## Job Execution

The server creates structured jobs.

The client agent interprets the supported job actions and executes the corresponding local operation.

The supported package actions are:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Package names are validated before a package job is created.

The agent does not treat package names as arbitrary shell fragments.

---

## Package Management Abstraction

Package operations are deliberately implemented behind a package-manager abstraction.

This keeps the higher-level LUMS job model independent from distribution-specific commands.

For example:

```text
INSTALL_PACKAGE
       │
       ├── Debian / Ubuntu → APT
       │
       └── Arch Linux      → pacman
```

The same principle applies to removal and package updates.

---

## Debian / Ubuntu

On Debian-family systems, LUMS uses the native APT/dpkg tooling.

Typical responsibilities include:

* package search
* package metadata lookup
* package installation
* package removal
* package updates
* system updates
* update detection

The LUMS agent does not replace APT.

It provides controlled orchestration around it.

---

## Arch Linux

On Arch Linux systems, LUMS uses the native pacman package manager.

Typical responsibilities include:

* package search
* package metadata lookup
* package installation
* package removal
* package updates
* system updates
* update detection

Distribution-specific behavior remains inside the package-manager layer.

---

## Package Search

Package search is separate from the installed-software inventory.

This distinction is important:

```text
Installed Software
        │
        └── What is already installed?

Package Management Search
        │
        └── What package can the client currently find?
```

Search results may contain package information such as:

* package name
* version
* description
* repository information where available

Search results are returned to the LUMS server and displayed in the Package Management interface.

---

## Package Management Permissions

Package management is a privileged operation.

The current permission model is:

```text
Administrator → allowed
Operator      → allowed
Viewer        → not allowed
```

A Viewer can still inspect installed software.

The Package Management interface itself is hidden for Viewers, and corresponding server-side mutation endpoints enforce authorization independently.

---

## Update Result Handling

LUMS treats the result of an update operation as structured state rather than simply displaying raw command output.

Relevant information can include:

* success or failure
* package-level result
* execution state
* error information
* reboot requirement
* completion timestamps

This allows the server to maintain a meaningful update history.

---

## Reboot Detection

After package operations, the client checks whether the operation indicates that a reboot is required.

The result is reported to the server as part of the job result.

A reboot requirement therefore remains associated with the update operation instead of being lost in a client-side terminal session.

---

## Client Authentication Boundary

The client API uses a separate authentication mechanism from administrative web sessions.

```text
Administrative User
        │
        ▼
 Web Authentication
        │
        ▼
    LUMS Server

Linux Client
        │
        ▼
 Client Token
        │
        ▼
    LUMS Server
```

This separation prevents administrative browser sessions and client credentials from becoming interchangeable authentication mechanisms.

---

## Audit Trail

Security-relevant and administrative actions are recorded by the server-side audit system.

The audit trail complements normal application logging.

Logging answers questions about application behavior.

Audit logging additionally records important administrative actions and their context.

This distinction is useful when investigating changes to clients, users, authentication state, or update jobs.

---

## Operational Principle

LUMS deliberately separates:

```text
Management
     │
     ▼
Policy / Authorization
     │
     ▼
Job
     │
     ▼
Client Execution
     │
     ▼
Native Package Manager
```

Each layer has a defined responsibility.

The server manages.

The agent executes.

The package manager performs the actual system change.

The result travels back through the same controlled chain.

## Role-Based Access Control

LUMS uses three administrative roles:

```text
Administrator
Operator
Viewer
```

Authorization is enforced server-side.

The frontend additionally adapts the visible interface to the current role, but frontend visibility is never considered a security boundary.

### Administrator

Administrators have access to:

* view clients
* view installed software
* view available updates
* create and execute update jobs
* view update history
* use package management
* perform system maintenance
* create and disable clients
* rotate client tokens
* create and manage users
* manage roles and user access

### Operator

Operators have access to:

* view clients
* view installed software
* view available updates
* create and execute update jobs
* view update history
* use package management
* perform system maintenance

Operators do not have access to:

* user management
* role administration
* client creation or disabling
* client-token rotation

### Viewer

Viewers have read-only access to:

* clients
* installed software

The following functionality is unavailable to Viewers:

* available-update management
* update jobs
* update history
* package management
* system maintenance
* other state-changing administrative operations

The server independently enforces these restrictions.

---

## User Management

LUMS provides administrator-only user management.

Administrators can create users and assign their role.

User passwords are stored using Argon2 password hashing rather than plaintext or reversible encryption.

User-management operations are protected by:

* authentication
* administrator-only authorization
* CSRF protection
* input validation
* duplicate-user checks
* audit logging

The user-management interface is not exposed to Operators or Viewers.

---

## Session Security

Administrative authentication uses server-side session handling.

Session security includes:

* authenticated session state
* session revocation
* CSRF protection for state-changing requests
* login rate limiting
* disabled-account enforcement
* role checks

Revoking a session invalidates the corresponding authenticated state rather than merely hiding the user interface.

---

## Login Rate Limiting

Repeated failed login attempts are subject to progressive rate limiting.

The current thresholds are:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

The relevant state is persisted in SQLite.

Successful authentication clears the applicable failure state.

This prevents a simple application restart from being used to bypass the login protection.

---

## Client Token Security

Each registered client has its own authentication token.

The server stores the token as a SHA-256 digest.

The original token is not required for normal server-side validation.

Token rotation allows administrators to invalidate an existing credential and issue a replacement.

This creates a clear lifecycle:

```text
Create
  │
  ▼
Use
  │
  ▼
Rotate
  │
  ▼
Old token invalid
```

---

## API Security

LUMS validates API input before performing state-changing operations.

Security controls include:

* authentication
* role authorization
* CSRF protection where applicable
* input validation
* package-name validation
* structured job actions
* parameterized database queries
* controlled error handling

The application does not use user-provided package names as unrestricted shell commands.

---

## SQL Injection Protection

Database operations use parameterized SQL statements.

User-controlled values are not directly concatenated into SQL queries.

This applies to areas such as:

* authentication
* client management
* user management
* package searches
* update jobs
* audit data
* result reporting

The goal is to keep data values separate from SQL instructions.

---

## SQLite Security Baseline

The current production SQLite configuration is:

```text
journal_mode = delete
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

Foreign-key enforcement is explicitly enabled by the application for database connections.

The current configuration does not use WAL mode.

The database is stored in the persistent Docker volume rather than inside the disposable application container filesystem.

---

## Job Recovery and Checkpointing

LUMS treats update jobs as persistent state machines.

A multi-package job may contain several individual package operations.

Each package item can reach its own result state.

If execution is interrupted, recovery can distinguish between:

```text
already successful
        │
        └── do not unnecessarily repeat

not completed
        │
        └── eligible for recovery
```

This reduces the risk of blindly repeating completed package operations after an interruption.

---

## Controlled Update Execution

LUMS deliberately limits the actions that can be requested through the update-job API.

Supported actions are:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

The server validates the action and relevant package information before creating the job.

The agent then maps the structured action to the appropriate package-manager operation.

This avoids turning the update system into a generic remote-command execution mechanism.

---

## Package Operations

Package operations are executed through the native package manager of the client.

### Installation

A validated package name is passed to the package-manager abstraction for installation.

### Removal

A validated package name is passed to the package-manager abstraction for removal.

### Package Update

A specific package can be updated when the client reports it as an available update.

### System Update

The system update operation delegates the update process to the native package manager.

All operations return structured results to the LUMS server.

---

## Package Manager Safety

LUMS treats the package manager as a privileged local component.

The agent therefore does not attempt to emulate package-manager behavior itself.

Instead, it:

1. validates the requested operation
2. selects the appropriate package-manager implementation
3. executes the controlled operation
4. captures the result
5. reports the result to the server

Distribution-specific behavior remains isolated inside the package-manager layer.

---

## Reboot Handling

Some package operations may require a reboot.

LUMS records reboot requirements as part of update-job results.

This allows administrators to distinguish between:

```text
Update completed
```

and:

```text
Update completed
Reboot required
```

The reboot requirement is therefore part of the operational state rather than being treated as an unrelated notification.

---

## Audit Logging

LUMS maintains an application audit trail for important administrative and security-relevant actions.

Examples include:

* authentication-related events
* client management
* token operations
* user management
* update-job creation
* security-sensitive state changes

Audit logging is separate from ordinary diagnostic logging.

Diagnostic logs help troubleshoot the application.

Audit records provide an administrative history of relevant actions.

---

## Security Hardening

The current deployment includes multiple layers of hardening.

### Container Hardening

The production container uses:

* non-root application execution
* read-only root filesystem
* dropped Linux capabilities
* `no-new-privileges`
* restricted temporary filesystems
* read-only secret mount
* dedicated persistent data volume

### Network Hardening

The application container is bound to loopback on the host:

```text
127.0.0.1:5050
```

The application port is therefore not directly exposed as a LAN service.

External access is handled through the HTTPS reverse proxy.

The firewall does not expose the internal application port.

### Transport Security

Administrative access is provided through HTTPS.

The reverse proxy handles external TLS termination.

HTTP requests are redirected to HTTPS.

### Secrets and Configuration

Sensitive runtime credentials are kept outside the application source tree.

The production secret is mounted into the container as a read-only secret file.

Repository and Docker build context rules prevent common backup, secret, database, and certificate artifacts from unintentionally entering the image build context.

### Dependency and Build Security

The production Python dependencies are pinned.

The production Python base image is pinned by digest.

The Docker build context is restricted through `.dockerignore`.

These controls improve build reproducibility and reduce accidental inclusion of sensitive files.

---

## Security Audit Status

The LUMS security review has covered the following areas:

* SQLite foreign-key enforcement
* SQLite runtime configuration
* update timeout and process handling
* login rate limiting
* API input validation
* session revocation
* client-token rotation
* offline/IP handling
* job recovery and checkpointing
* APT robustness
* Arch reboot detection
* unit and API result validation
* simulation testing
* continuous integration
* application and audit logging
* versioning and release handling
* RBAC
* session and CSRF security
* credential security
* dependency and build security
* Docker/container hardening
* secrets and build-context protection
* HTTP/transport security
* filesystem/runtime permissions
* network exposure
* repository artifact hygiene

The remaining documentation review is handled separately as part of the final release-readiness process.

---

## Testing and CI

LUMS includes automated tests covering core application behavior and security controls.

The current full test baseline is:

```text
155 passed
```

The test suite includes coverage for areas such as:

* authentication
* RBAC
* client management
* user management
* package search
* update jobs
* job-result validation
* security behavior
* API behavior

Continuous integration executes the automated test suite before changes are considered ready.

A successful test run is required, but tests are only one part of the release process.

The release process also requires:

```text
Implementation
    ↓
Security Review
    ↓
Documentation Review
    ↓
Full Test Suite
    ↓
CI
    ↓
Version
    ↓
Git Tag
    ↓
GitHub Release
```

---

## Development Status

LUMS is currently in active development.

The core management architecture, client execution model, package management, RBAC, security hardening, and recovery mechanisms are implemented.

The project is intentionally not considered a finished release merely because the application is functional.

Release readiness also requires the surrounding documentation and operational procedures to describe the same current system.

This is why documentation consistency is treated as part of the engineering process rather than as an afterthought.

## Supported Systems

LUMS is designed to manage Linux systems using supported native package managers.

### Debian / Ubuntu

Supported package-management stack:

```text
APT
dpkg
```

The client uses the native Debian package-management tooling for:

* package inventory
* update detection
* package search
* package installation
* package removal
* package updates
* system updates

### Arch Linux

Supported package-management stack:

```text
pacman
```

The client uses the native Arch package-management tooling for:

* package inventory
* update detection
* package search
* package installation
* package removal
* package updates
* system updates

---

## Client Requirements

A managed Linux client requires:

* a supported Linux distribution
* the LUMS agent
* network connectivity to the LUMS server
* a registered client token
* a working native package manager
* systemd for the timer/service-based execution components

The client does not require the LUMS server to directly access its package database.

The client performs local package operations and reports the results to the server.

---

## Technology Stack

### Server

* Python
* Flask
* Gunicorn
* SQLite
* HTML
* CSS
* JavaScript
* Nginx
* Docker

### Authentication and Security

* Argon2 password hashing
* server-side sessions
* CSRF protection
* role-based access control
* SHA-256 client-token digests
* HTTPS
* audit logging

### Client

* Python
* systemd
* APT / dpkg
* pacman
* `loginctl` where idle-state information is available

---

## Project Structure

The repository is organized into separate server, client, frontend, and test components.

A simplified structure is:

```text id="1rq7v7"
LUMS/
├── agent/
│   ├── agent.py
│   └── package_manager.py
│
├── server/
│   ├── app.py
│   ├── migrations/
│   ├── static/
│   ├── templates/
│   └── ...
│
├── tests/
│   ├── test_rbac.py
│   ├── test_package_search.py
│   ├── test_job_result.py
│   └── ...
│
├── Dockerfile
├── docker-entrypoint.sh
├── .dockerignore
├── .gitignore
└── documentation
```

The exact repository layout may evolve as LUMS develops.

The architectural separation between server, agent, package-manager abstraction, frontend, and tests is intentional.

---

## Server Application

The Flask application provides the central LUMS API and web interface.

Its responsibilities include:

* authentication
* authorization
* session handling
* client management
* user management
* software inventory
* update inventory
* package search
* update jobs
* job-result handling
* audit logging
* database persistence

The application is served by Gunicorn inside the container.

Nginx provides the external HTTPS entry point.

---

## Agent

The LUMS agent is installed directly on managed Linux clients.

Current agent version:

```text id="w8p4wz"
1.7.0
```

The agent is responsible for the client-side part of the LUMS execution chain.

Its responsibilities include:

* reporting client state
* collecting installed software
* detecting available updates
* searching packages
* executing package operations
* reporting job results
* detecting reboot requirements
* handling idle-state information
* participating in job recovery

The agent does not provide an unrestricted remote shell.

---

## Package Manager Layer

The package-manager implementation isolates distribution-specific behavior from the rest of the agent.

Conceptually:

```text id="zq8xq3"
Agent
  │
  ▼
Package Manager Interface
  │
  ├── Debian / Ubuntu
  │      └── APT / dpkg
  │
  └── Arch Linux
         └── pacman
```

This allows the higher-level update-job system to work with structured operations without needing to know every distribution-specific command.

---

## Watcher

The LUMS execution watcher monitors jobs that are expected to execute on the client.

Current watcher version:

```text id="7k6w3s"
1.2.1
```

The watcher operates together with the agent and server-side job state.

This architecture allows LUMS to detect execution situations where a job remains pending or otherwise requires attention.

---

## systemd Integration

The client uses systemd for scheduled and controlled execution.

Relevant components include service and timer units for:

* client reporting
* update detection
* job execution/watching

This provides predictable execution without requiring a continuously running foreground process for every periodic operation.

The client agent can also be executed manually during installation and troubleshooting.

---

## Idle-Aware Execution

Idle-aware execution is designed to reduce interference with active users.

The current idle threshold is:

```text id="g8v0lq"
300 seconds
```

The client determines idle state using the available local session information.

Where supported, `loginctl` is used.

The agent distinguishes between:

```text id="6v3m4k"
confirmed idle
active
idle state unavailable
```

An unavailable idle state is not silently interpreted as idle.

This makes the execution decision explicit and diagnosable.

---

## Update Job Lifecycle

The complete lifecycle of an update job can be represented as:

```text id="h4d9kv"
Create
  │
  ▼
Validate
  │
  ▼
Persist
  │
  ▼
Claim
  │
  ▼
Execute
  │
  ├──────────────► SUCCESS
  │
  ├──────────────► FAILED
  │
  └──────────────► RECOVERY
                         │
                         ▼
                      Execute
```

A job is persisted before execution.

This means the server retains knowledge of the intended operation even if the client or application is interrupted.

---

## Job Types

LUMS currently supports structured update actions including:

```text id="v7r1f8"
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

These actions are intentionally limited.

LUMS is an update-management system, not a general-purpose remote-command framework.

---

## Package-Level Job State

Jobs containing multiple packages can track package-level progress.

For example:

```text id="v9w1sh"
Job #42

package-a → SUCCESS
package-b → SUCCESS
package-c → FAILED
package-d → PENDING
```

Recovery can therefore operate on the incomplete portions of the job rather than blindly repeating successful package operations.

---

## Job Recovery

Recovery is designed around persistent checkpoints.

The server maintains the job state.

The client reports package-level results.

If execution is interrupted, the server can determine which work has already completed and which work remains eligible for recovery.

The intended recovery principle is:

> **Continue from known state instead of assuming that nothing happened.**

---

## Result Validation

Client job results are validated before being accepted into persistent server state.

This protects the job state from malformed or incomplete result submissions.

Validation is applied to relevant fields such as:

* job identity
* execution state
* package result data
* error information
* reboot information

The result-processing layer therefore acts as another boundary between an authenticated client and persistent server state.

---

## User Management

User management is an administrator-only function.

The server exposes administrative operations for creating users and assigning roles.

The current roles are:

```text id="2xqv79"
Administrator
Operator
Viewer
```

User-management actions are authenticated, authorized, validated, protected against CSRF where applicable, and recorded in the audit trail.

---

## Client Management

Administrators can manage registered clients.

Client-management functions include:

* registration
* disabling
* token rotation
* client status inspection

Client authentication is independent for every registered client.

Disabling a client prevents it from continuing normal authenticated communication with the server.

---

## Update History

LUMS maintains persistent update-job state so that completed and failed operations remain visible after execution.

Authorized users can inspect the history of update operations according to their role.

The history is intended to provide operational context rather than merely showing the latest package inventory.

---

## Auditability

LUMS maintains two related but distinct forms of operational information:

### Application Logs

Used primarily for:

* diagnostics
* errors
* runtime behavior
* troubleshooting

### Audit Logs

Used primarily for:

* administrative actions
* security-relevant events
* changes to important state
* accountability

Keeping these concepts separate makes troubleshooting and administrative review easier.

---

## Testing Strategy

The LUMS test suite covers multiple layers of the application.

### Authentication

Tests cover authentication behavior, session handling, and security controls.

### RBAC

Tests verify that:

* Administrators can perform administrative actions
* Operators receive their permitted management functions
* Viewers remain read-only

### Package Management

Tests cover package-search behavior and package-management-related API handling.

### Update Jobs

Tests cover:

* job creation
* validation
* state transitions
* result handling
* recovery behavior

### Security

Tests cover security-sensitive application behavior and regression cases.

### Full Suite

The current full test baseline is:

```text id="7cn4f6"
155 passed
```

---

## Continuous Integration

The project uses continuous integration to run automated checks against changes.

The CI pipeline helps detect regressions before changes are treated as release-ready.

The development workflow is therefore:

```text id="v3n9k8"
Change
  ↓
Test
  ↓
Security Review
  ↓
Documentation Review
  ↓
CI
  ↓
Release Preparation
```

A successful CI run does not replace manual security or documentation review.

---

## Documentation

LUMS maintains separate documentation for different operational concerns.

### `README.md`

Project overview, architecture, features, security baseline, development status, and project direction.

### `install.md`

Installation, deployment, client setup, validation, upgrade, and removal procedures.

### `administration.md`

Routine administration, maintenance, backups, upgrades, operational procedures, and emergency administration.

### `security.md`

Security architecture, security controls, audit findings, hardening, and release-readiness security information.

### `troubleshooting.md`

Diagnostic procedures for server, client, jobs, package management, authentication, database, container, and network problems.

### `LUMS_Optional_Theme_System.md`

Architecture and maintenance guidance for optional LUMS frontend themes.

The documentation is intentionally separated by responsibility so that operational instructions do not become mixed with security design or visual customization.

---

## Documentation Principle

Documentation is treated as part of the system.

A feature is not considered completely finished when the code works but the documentation still describes an older architecture.

The intended relationship is:

```text id="0m1m5u"
Implementation
      │
      ├── Tests
      ├── Security Review
      └── Documentation
               │
               ▼
          Release Ready
```

This is particularly important for security-sensitive deployment and administration procedures.

## Current Status

LUMS is an actively developed Linux update-management platform.

The current implementation includes:

* centralized client management
* software inventory
* update detection
* package search
* package installation and removal
* package-specific updates
* system updates
* persistent update jobs
* package-level job state
* job recovery
* reboot detection
* idle-aware execution
* client-token authentication
* token rotation
* administrative authentication
* role-based access control
* user management
* audit logging
* container hardening
* HTTPS transport
* automated testing
* continuous integration

The project is currently in the final documentation and release-readiness phase.

---

## Security Status

The major security-review areas have been implemented and reviewed.

The current security baseline includes:

```text
Authentication
    ├── Argon2 password hashing
    ├── session handling
    ├── session revocation
    └── login rate limiting

Authorization
    ├── Administrator
    ├── Operator
    └── Viewer

Client Security
    ├── per-client tokens
    ├── SHA-256 token digests
    └── token rotation

API Security
    ├── input validation
    ├── CSRF protection
    ├── RBAC enforcement
    └── parameterized SQL

Runtime Security
    ├── non-root container
    ├── read-only root filesystem
    ├── dropped capabilities
    ├── no-new-privileges
    ├── restricted temporary filesystems
    └── protected secret mount

Network Security
    ├── HTTPS
    ├── reverse proxy
    ├── loopback application binding
    └── firewall restrictions
```

Security is treated as an ongoing engineering responsibility rather than a one-time checklist.

---

## Release Status

LUMS does not currently claim a stable production release version.

There is currently:

* no final semantic version
* no stable release tag
* no GitHub Release

The project deliberately follows the release sequence:

```text id="f3c4y9"
Implementation
      ↓
Security Review
      ↓
Documentation Review
      ↓
Full Test Suite
      ↓
CI
      ↓
Version Assignment
      ↓
Git Tag
      ↓
GitHub Release
```

The first official release should only be created after the current implementation, security review, documentation, and regression testing are considered complete.

---

## Roadmap

The roadmap is intentionally focused on stability and maintainability rather than adding features without completing the existing foundation.

### Current Phase

* complete documentation review
* remove remaining documentation inconsistencies
* close documentation audit work
* perform final full test run
* verify CI
* prepare release version
* create the first official Git tag
* publish the first GitHub Release

### Future Development

Potential future work may include:

* additional Linux distributions
* additional package-manager backends
* further UI improvements
* additional reporting capabilities
* expanded operational automation
* additional security controls
* further test coverage

Future features should preserve the existing architectural boundaries.

---

## What LUMS Is Not

LUMS is intentionally not designed as:

* a general-purpose remote shell
* a replacement for APT, dpkg, or pacman
* a full configuration-management platform
* an endpoint-management suite for every operating system
* a cloud-only service
* an uncontrolled command-execution framework

LUMS focuses on a narrower problem:

> **Controlled Linux software and update management with persistent state and auditability.**

---

## Development Philosophy

LUMS follows a simple development cycle:

```text id="8a0mve"
Build
  ↓
Test
  ↓
Secure
  ↓
Document
```

A feature is not considered complete simply because it works in the developer environment.

It should also be:

* tested
* security-reviewed
* documented
* reproducible
* understandable
* recoverable where appropriate

---

## Change Philosophy

Changes should be made deliberately.

A typical change should answer:

1. What problem does this solve?
2. Which component should own the change?
3. Does the change affect security?
4. Does it affect persistent state?
5. Does it affect clients?
6. Does it require documentation changes?
7. Which tests prove that existing functionality still works?

This reduces the risk of fixing one part of the system while silently breaking another.

---

## Development Workflow

The preferred development workflow is:

```text id="r8u6o1"
Understand
   ↓
Implement
   ↓
Test
   ↓
Inspect
   ↓
Harden
   ↓
Document
   ↓
Regression Test
```

Security-sensitive changes receive additional verification before being considered complete.

---

## Repository

The project repository is hosted on GitHub:

**NovaForgeCtrl/LUMS**

The repository contains the application source code, client components, tests, container configuration, and project documentation.

---

## Documentation Set

The current documentation set consists of:

```text id="0xw7cy"
README.md
install.md
administration.md
security.md
troubleshooting.md
LUMS_Optional_Theme_System.md
```

Each document has a defined purpose.

The README provides the project-level overview.

The installation guide explains deployment.

The administration guide explains ongoing operation.

The security guide documents the security architecture and audit state.

The troubleshooting guide provides diagnostic procedures.

The optional theme document covers frontend theme architecture.

---

## License

LUMS is released under the MIT License.

The license is intended to keep the project open and accessible while allowing use, modification, and redistribution under the terms of the license.

See the repository license file for the complete legal text.

---

## Community and Contributions

LUMS is an open-source project and contributions are welcome.

Useful contributions can include:

* bug reports
* security reports
* documentation improvements
* tests
* package-manager support
* frontend improvements
* backend improvements
* deployment improvements

Contributions should preserve the project's architectural and security principles.

---

## Security Reports

Security issues should not be treated like ordinary feature requests.

When reporting a security problem, provide enough information to reproduce and understand the issue without unnecessarily exposing sensitive information.

Security-related changes should be reviewed carefully before being merged.

---

## Project Identity

LUMS is built around a simple idea:

> **Linux update management without the noise.**

The project does not attempt to hide complexity by pretending that Linux package management is simple.

Instead, it makes the relevant state visible:

```text id="q2j5r0"
What is installed?
        ↓
What can be updated?
        ↓
What should change?
        ↓
Who requested it?
        ↓
What actually happened?
        ↓
What state remains?
```

That information is the foundation of controlled update management.

---

## Final Architecture

At its highest level, LUMS can be understood as five layers:

```text id="7b4p6n"
┌───────────────────────────────────────────────┐
│                    UI                         │
│       Human interaction and visibility        │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    API                        │
│    Authentication, authorization, validation  │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                  Persistence                   │
│       Jobs, clients, users, results, audit   │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    Agent                      │
│      Local execution and system reporting     │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│              Native Linux Tools               │
│              APT / dpkg / pacman             │
└───────────────────────────────────────────────┘
```

Each layer has a specific responsibility.

The UI provides interaction.

The API enforces policy.

SQLite provides persistent state.

The agent performs controlled client-side execution.

The native package manager performs the actual system change.

---

## Final Principle

LUMS is built around one central principle:

> **Observe the system. Control the change. Record the result.**

That principle applies to the software architecture, update execution, security model, recovery mechanisms, and documentation.

**Linux Update Management without the noise.**
