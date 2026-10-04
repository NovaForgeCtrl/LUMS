# LUMS

## Linux Update Management Server

> **Linux Update Management without the noise.**

LUMS is a lightweight Linux update management platform for small labs, test environments, and infrastructure projects.

It provides centralized client management, software and update inventory, authenticated agent communication, controlled package execution, job tracking, recovery handling, and role-based administration without requiring a large management stack.

LUMS is designed around a simple principle:

> **Centralize the management. Keep execution controlled.**

---

## What is LUMS?

LUMS provides a central management layer for Linux systems while leaving actual package management to the operating system.

The LUMS server manages:

* Linux client inventory
* Installed software information
* Available updates
* Client authentication
* Client tokens
* Update jobs
* Package-management operations
* Job execution state
* Execution results
* Administrative users
* Role-based access control
* Audit information
* Job recovery and checkpoint state

The LUMS Agent handles operations on the managed client:

* system reporting
* package inventory
* update inventory
* idle-state detection
* update-job execution
* package installation
* package removal
* package updates
* system updates
* result reporting
* recovery of interrupted execution

The native operating-system package manager remains responsible for the actual package operation.

```text
                 LUMS
                   │
          Central Management
                   │
                   ▼
             Managed Client
                   │
                   ▼
        Native Package Manager
                   │
          ┌────────┴────────┐
          │                 │
         APT              pacman
          │                 │
       Debian/           Arch Linux
       Ubuntu
```

LUMS therefore does not attempt to replace APT, dpkg, or pacman.

It provides a controlled management and execution layer around them.

---

# Why LUMS?

LUMS was built around a practical question:

> **How can Linux updates be centrally managed without hiding what actually happens on the systems being managed?**

The project therefore focuses on:

* simple architecture
* transparent operation
* minimal dependencies
* authenticated clients
* controlled execution
* explicit job states
* auditable changes
* recovery after interruption
* container hardening
* role-based access control
* automated testing
* documentation-first development

The goal is not to create another opaque management platform.

The goal is to make the complete execution path understandable:

```text
What should happen?
        │
        ▼
Which client is affected?
        │
        ▼
Which job was created?
        │
        ▼
What was executed?
        │
        ▼
What did the package manager report?
        │
        ▼
What result reached the server?
        │
        ▼
What is the final client state?
```

---

# Core Features

## Client Management

LUMS maintains a central inventory of registered Linux clients.

Client information can include:

* hostname
* IP address
* operating system
* architecture
* kernel
* package count
* available updates
* Agent version
* last report
* client status

Each managed client has its own authentication token.

---

## Software Inventory

The LUMS Agent reports installed software to the server.

This allows administrators and operators to inspect client software centrally without directly replacing or modifying the native package-management database.

The installed-software view also provides local filtering for already reported packages.

---

## Update Inventory

Managed clients report available software updates.

LUMS can therefore provide a central view of update state across registered Linux systems.

Update information is generated on the client using the native package-management tools.

---

## Package Management

LUMS provides centralized package-management operations.

Supported actions include:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

The actual operation is executed by the LUMS Agent.

Current package-management backends include:

```text
Debian / Ubuntu
    APT / dpkg

Arch Linux
    pacman
```

LUMS also provides a package-search function that is separate from the locally displayed installed-software filter.

```text
Installed Software
    │
    └── Filter reported inventory

Package Management
    │
    └── Search package repositories
```

---

## Update Jobs

Mutating operations are represented as update jobs.

A job provides a controlled execution path between the LUMS server and the managed client.

Conceptually:

```text
Web Interface
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
      ▼
Package Manager
      │
      ▼
Execution Result
      │
      ▼
LUMS
```

Supported job actions include:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Jobs are tracked through their execution lifecycle and their resulting state is reported back to the server.

---

## Controlled Execution

LUMS does not execute every available update automatically.

Update execution is controlled through:

* authenticated clients
* role-based authorization
* update jobs
* idle-aware execution
* atomic job claiming
* package-level checkpointing
* execution result validation
* recovery handling

This provides a clear distinction between:

```text
An update is available
```

and:

```text
An authorized update job should be executed
```

---

## Idle-Aware Execution

The Agent can check whether the client is currently idle before executing update work.

The current Linux idle-detection implementation uses:

```text
systemd-logind
      │
      ▼
   loginctl
      │
      ▼
 Idle state
```

The current idle threshold is:

```text
300 seconds
```

When supported, the Agent reports the detection source and capability to LUMS.

If idle state cannot be determined safely, automatic execution does not assume that the client is idle.

---

## Job Recovery

LUMS includes recovery handling for interrupted update execution.

Package operations are tracked individually so that successful work is not blindly repeated after an interruption.

Conceptually:

```text
Update Job
    │
    ├── Package A → SUCCESS
    ├── Package B → SUCCESS
    ├── Package C → interrupted
    └── Package D → PENDING
```

Recovery uses the recorded execution state to determine which work remains.

This is particularly important when a client disappears, the Agent is interrupted, or a system reboot occurs during maintenance.

---

## Client Authentication

Each managed client uses its own Bearer token when communicating with the LUMS server.

```http
Authorization: Bearer <CLIENT_TOKEN>
```

The server does not need to store the original client token.

Instead, the token is represented by a SHA-256 hexadecimal digest:

```text
Client Token
      │
      ▼
    SHA-256
      │
      ▼
Token Digest
      │
      ▼
   Database
```

Client authentication is separate from web-user authentication.

```text
Web User
    │
    └── Session + Role

Managed Client
    │
    └── Bearer Token
```

---

## Token Rotation

Client tokens can be rotated administratively.

A token rotation:

1. generates a new client token
2. stores its digest
3. invalidates the previous token
4. records the operation in the audit log
5. exposes the new token only through the appropriate administrative workflow

The plaintext token is not written to the audit log.

After rotation:

```text
Old token → invalid
New token → valid
```

---

## Job State

LUMS tracks update execution through explicit job states.

The exact state sequence depends on the operation and execution conditions, but the central lifecycle distinguishes between work that is:

```text
pending
running
successful
failed
```

Additional execution and recovery state may be recorded when required.

A successful API request does not by itself mean that the package operation succeeded.

The package-manager result reported by the Agent is the relevant execution result.

---

## Design Principle

LUMS intentionally keeps the execution chain visible:

```text
LUMS
  │
  ▼
Authorized Job
  │
  ▼
Authenticated Client
  │
  ▼
LUMS Agent
  │
  ▼
Native Package Manager
  │
  ▼
Result
```

> **LUMS manages the operation. The operating system performs it.**

# Architecture

LUMS is intentionally built from a small number of clearly separated components.

```text
                         HTTPS / TLS
                              │
                              ▼
                     ┌────────────────┐
                     │     Nginx      │
                     │    :443        │
                     └───────┬────────┘
                             │
                      localhost only
                             │
                             ▼
                    ┌─────────────────┐
                    │   Docker: lums  │
                    │                 │
                    │    Gunicorn     │
                    │       ↓         │
                    │     Flask       │
                    │      :5000      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    lums-data    │
                    │                 │
                    │ SQLite / lums.db│
                    └─────────────────┘
```

The server application listens on port:

```text
5000
```

inside the container.

The host exposes the application only through:

```text
127.0.0.1:5050
```

Nginx provides the external HTTPS endpoint.

The application port is therefore not intended to be directly accessible from the network.

---

# Server Components

The LUMS server consists primarily of:

```text
Nginx
   │
   ▼
Docker
   │
   ▼
Gunicorn
   │
   ▼
Flask
   │
   ▼
SQLite
```

Each component has a distinct responsibility.

### Nginx

Provides:

* HTTPS termination
* TLS handling
* external HTTP/HTTPS access
* reverse proxying to the local LUMS application

### Docker

Provides:

* application isolation
* controlled runtime configuration
* persistent-volume separation
* container-level hardening

### Gunicorn

Runs the Flask application through a production WSGI server.

### Flask

Provides:

* web interface
* API
* authentication
* authorization
* client management
* update-job management
* package-management operations
* audit functionality

### SQLite

Stores persistent application state.

The database is stored in:

```text
/var/lib/lums/lums.db
```

inside the persistent Docker volume.

---

# Container Security

The production LUMS container is intentionally hardened.

The current runtime baseline includes:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=ALL
SecurityOpt=no-new-privileges:true
```

Temporary writable storage is provided through restricted tmpfs mounts.

The application secret is mounted read-only:

```text
Host:
    /etc/lums/secrets/lums_secret

Container:
    /run/secrets/lums_secret
```

Persistent application data is provided separately:

```text
lums-data
    │
    ▼
/var/lib/lums
```

This separates:

```text
Application image
        ≠
Runtime container
        ≠
Persistent application data
```

Replacing the application container therefore does not inherently remove the application database.

---

# Persistent Storage

LUMS stores persistent application state in the Docker volume:

```text
lums-data
```

The database is:

```text
/var/lib/lums/lums.db
```

The persistent volume contains application state such as:

* users
* clients
* update jobs
* package-related state
* audit information
* migration state

The volume should be treated as critical application data.

Removing the container and removing the persistent volume are separate operations.

```text
docker rm lums
        │
        └── does not remove lums-data

docker volume rm lums-data
        │
        └── removes persistent application data
```

---

# Client Architecture

The LUMS client side is split into two main execution paths:

```text
                 Linux Client
                      │
             ┌────────┴────────┐
             │                 │
          Reporting         Execution
             │                 │
             ▼                 ▼
       lums-agent          watcher
```

This separation prevents periodic inventory reporting from being tightly coupled to update execution.

---

# Reporting Path

The reporting path uses systemd:

```text
lums-agent.timer
        │
        ▼
lums-agent.service
        │
        ▼
     agent.py
        │
        ▼
      HTTPS
        │
        ▼
    LUMS API
```

The reporting path collects information such as:

```text
System information
       ↓
Operating system
       ↓
Kernel
       ↓
Architecture
       ↓
Installed packages
       ↓
Available updates
       ↓
Agent information
       ↓
Client status
```

The collected information is sent to the LUMS server over HTTPS.

---

# Execution Path

Update execution is handled separately by the execution watcher:

```text
lums-agent-watcher.timer
        │
        ▼
lums-agent-watcher.service
        │
        ▼
      watcher.py
        │
        ▼
   Idle detection
        │
        ▼
 Running-job recovery
        │
        ▼
   Pending job lookup
        │
        ▼
    Atomic claim
        │
        ▼
 Package manager
        │
        ▼
    Result report
```

The watcher is responsible for controlling when pending work can be executed.

---

# Atomic Job Claiming

A pending job must be claimed before execution.

Conceptually:

```text
Pending
   │
   ▼
Claim
   │
   ├── success → execute
   │
   └── rejected → do not execute
```

This prevents multiple execution paths from accidentally processing the same job simultaneously.

The claim operation is part of the server-side execution workflow.

---

# Job Execution

Once a job has been claimed by the appropriate client, the Agent performs the requested operation.

```text
Authorized Job
      │
      ▼
Authenticated Client
      │
      ▼
Agent
      │
      ▼
Package Manager
      │
      ▼
Command Execution
      │
      ▼
Result Validation
      │
      ▼
Server Result
```

The Agent does not blindly trust the requested operation.

Supported actions are explicitly recognized by the application and package-management layer.

---

# Package Manager Abstraction

The Agent separates package-management operations from the higher-level job system.

```text
                 LUMS Job
                    │
                    ▼
           Package Manager Layer
                /         \
               /           \
             APT          pacman
              │              │
              ▼              ▼
         Debian/Ubuntu   Arch Linux
```

This allows the server-side job workflow to remain independent from the package manager used by the client.

---

# Debian / Ubuntu

On Debian-based systems, the Agent uses the native package-management tools.

Relevant components include:

```text
apt
apt-get
apt-cache
dpkg-query
```

The package-management layer handles operations such as:

```text
Package search
Package inventory
Update detection
Package installation
Package removal
Package updates
System updates
```

The native package manager remains responsible for the actual package transaction.

---

# Arch Linux

On Arch Linux, the Agent uses:

```text
pacman
```

The package-management layer supports operations including:

```text
pacman -Q
pacman -Qu
pacman -S
pacman -R
pacman -Syu
```

The same LUMS job model is used regardless of whether the underlying client uses APT or pacman.

---

# Package Search

Package search is separate from the installed-software filter.

The installed-software view works with package information already reported by the client.

Package management can request a repository search from the client.

```text
Installed Software
       │
       └── Local reported inventory

Package Management
       │
       └── Repository search
```

Search results can include:

```text
Package
Version
Description
Repository
Status
Available action
```

The actual package-management operation is still performed by the native package manager.

---

# Package Management Permissions

Package management is subject to the authenticated web user's role.

The current model is:

```text
Administrator
    │
    └── Package management

Operator
    │
    └── Package management

Viewer
    │
    └── No package-management actions
```

The restriction exists at both the interface and server authorization layers.

Hiding a button in the web interface is therefore not the security boundary.

The API authorization is the actual enforcement layer.

---

# Update Result Handling

After an operation completes, the Agent reports the result to the server.

The result can contain information such as:

```text
Job
Client
Action
Package
Execution state
Exit status
Output
Error information
Reboot requirement
```

The server validates the reported result before applying it to the corresponding job state.

This prevents an arbitrary client-side response from automatically becoming trusted application state.

---

# Reboot Detection

Some package operations can require a system reboot.

LUMS therefore tracks reboot-related state separately from the package command result.

The client can report that a reboot is required after an update operation.

For supported workflows, reboot detection is also handled for Arch Linux systems.

The reboot state is used as operational information and does not itself mean that LUMS will automatically reboot the machine.

---

# Client Authentication Boundary

There are two separate authentication domains:

```text
Web User
    │
    ├── Session
    ├── Password
    ├── CSRF protection
    └── RBAC role


Managed Client
    │
    └── Bearer token
```

A web user's permissions do not replace client authentication.

Likewise, a client token does not provide access to the administrative web interface.

This separation is intentional.

---

# Audit Trail

Administrative and security-sensitive operations are recorded through application audit logging.

Relevant operations include areas such as:

* authentication
* user management
* client management
* token rotation
* update-job operations
* security-sensitive administrative actions

The audit trail is intended to answer:

```text
Who performed the action?
        ↓
What action was performed?
        ↓
Which object was affected?
        ↓
When did it happen?
        ↓
What was the result?
```

Sensitive credentials such as plaintext client tokens are not written to the audit log.

---

# Logging

LUMS separates operational logging from persistent application state.

Logs are useful for diagnosing:

* application startup
* authentication failures
* API errors
* update-job processing
* Agent communication
* migration problems
* unexpected runtime behavior

Logs should be treated as diagnostic information.

They should not be used as a replacement for the database or audit trail.

Administrators should also ensure that sensitive credentials are not exposed when sharing logs for troubleshooting.

---

# Documentation Architecture

The project maintains separate documentation for different operational purposes.

```text
README.md
    │
    └── Project overview and entry point

installation.md
    │
    └── Installation and deployment

administration.md
    │
    └── Day-to-day administration

security.md
    │
    └── Security architecture and audit

troubleshooting.md
    │
    └── Diagnosis and recovery
```

The README intentionally remains an overview.

Detailed operational procedures belong in the dedicated documentation.

---

# Operational Principle

The complete LUMS execution path can be summarized as:

```text
             Management
                  │
                  ▼
               LUMS API
                  │
                  ▼
             Update Job
                  │
                  ▼
          Authenticated Client
                  │
                  ▼
             LUMS Agent
                  │
                  ▼
         Native Package Manager
                  │
                  ▼
              Result
                  │
                  ▼
             LUMS Server
                  │
                  ▼
          Auditable State
```

> **One management layer. Native package execution. Explicit state.**

# Role-Based Access Control

LUMS uses role-based access control (RBAC) for administrative access.

There are three roles:

```text
Administrator
Operator
Viewer
```

Permissions are enforced server-side.

The web interface additionally adapts the visible functionality to the authenticated user's role.

---

## Administrator

Administrators have full administrative access.

They can:

* view managed clients
* view installed software
* view available updates
* create and execute update jobs
* view update history
* use package management
* perform system maintenance
* create clients
* disable clients
* rotate client tokens
* manage users
* manage user roles

Administrator access is intended for trusted administrative users.

---

## Operator

Operators have operational management access.

They can:

* view managed clients
* view installed software
* view available updates
* create and execute update jobs
* view update history
* use package management
* perform system maintenance

Operators cannot:

* manage users
* change user roles
* create or disable clients
* rotate client tokens

This separates day-to-day update operations from higher-level account and client administration.

---

## Viewer

Viewers have read-only client visibility.

They can:

* view managed clients
* view installed software

The following functionality is not available to Viewers:

* available updates
* Update Jobs
* Update History
* Package Management
* System Maintenance

These restrictions are enforced server-side and are not merely interface restrictions.

---

# User Authentication

Administrative users authenticate through the LUMS web application.

The authentication model includes:

* password-based authentication
* secure password hashing
* session-based authentication
* session revocation
* CSRF protection
* login rate limiting
* role-based authorization

Passwords are not stored in plaintext.

LUMS uses Argon2-based password hashing for application users.

---

# Session Security

Authenticated web sessions are treated as revocable application state.

Security controls include:

* secure session handling
* session invalidation
* authentication checks on protected routes
* role checks on privileged routes
* CSRF protection for state-changing operations

A valid session alone does not grant administrative privileges beyond the user's assigned role.

---

# Login Rate Limiting

Repeated failed login attempts are rate-limited.

The current progression is:

```text
5 failed attempts  → 30 seconds
6 failed attempts  → 60 seconds
7 failed attempts  → 120 seconds
8+ failed attempts → 300 seconds
```

Rate-limit state is persisted in SQLite.

Successful authentication clears the applicable failure state.

The implementation uses transactional database handling to avoid inconsistent concurrent updates.

---

# Client Authentication

Managed Linux clients authenticate to the LUMS server using client tokens.

The token is used to authenticate client-side API requests.

Client authentication is separate from web-user authentication.

```text
Web User
    │
    └── Session authentication

Linux Client
    │
    └── Client-token authentication
```

A client token therefore does not provide access to the administrative web interface.

---

# Client Token Security

Client tokens are not treated as ordinary configuration values.

The server stores a cryptographic digest of the token rather than relying on the plaintext token for authentication state.

The authentication flow is therefore conceptually:

```text
Client Token
     │
     ▼
SHA-256
     │
     ▼
Stored Digest
```

Token rotation invalidates the previous token and replaces it with a new credential.

This allows a compromised or otherwise exposed token to be revoked without replacing the client itself.

---

# Security Architecture

LUMS applies several security layers rather than relying on a single control.

```text
TLS
 │
 ▼
Web Authentication
 │
 ▼
Session Security
 │
 ▼
CSRF Protection
 │
 ▼
RBAC
 │
 ▼
API Input Validation
 │
 ▼
Client Authentication
 │
 ▼
Job Authorization
 │
 ▼
Controlled Execution
 │
 ▼
Result Validation
```

The goal is defense in depth.

A UI restriction is therefore never considered sufficient by itself for a security-sensitive operation.

---

# API Security

API endpoints validate their input before performing state-changing operations.

Security controls include:

* authentication requirements
* role checks
* CSRF protection where applicable
* request validation
* package-name validation
* allowed-action validation
* client-state validation
* update availability validation
* result validation
* database constraints and transactional handling

Unexpected or malformed input must not be interpreted as an authorized operation.

---

# SQL Injection Protection

LUMS uses parameterized database operations instead of constructing SQL statements from untrusted input.

User-provided values are therefore passed to SQLite as parameters.

This applies to security-sensitive operations such as:

* authentication
* client lookup
* job creation
* job updates
* package management
* audit logging
* user management

Input validation and parameterized queries are complementary controls.

---

# SQLite Security Baseline

The current production SQLite configuration is intentionally conservative.

The runtime baseline is:

```text
journal_mode = delete
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

Foreign-key enforcement is explicitly enabled by the application for database connections.

LUMS does not currently rely on SQLite WAL mode in production.

The database remains inside the persistent `lums-data` volume.

---

# Job Recovery and Checkpointing

LUMS tracks update-job execution state so interrupted operations can be recovered safely.

Package-level progress is checkpointed.

During recovery, already successful package items are not blindly executed again.

The conceptual flow is:

```text
Job
 │
 ├── Package A → SUCCESS
 ├── Package B → SUCCESS
 ├── Package C → interrupted
 └── Package D → pending
```

After recovery:

```text
Package A → preserved
Package B → preserved
Package C → evaluated for recovery
Package D → remaining work
```

This reduces unnecessary repetition after interruptions.

---

# Controlled Update Execution

Update commands are executed through controlled subprocess handling.

The Agent applies:

* explicit command construction
* supported-action checks
* subprocess timeouts
* process termination handling
* result collection
* result validation

When a process exceeds its configured execution limit, the Agent attempts controlled termination and falls back to a stronger termination mechanism when necessary.

This prevents indefinitely hanging package operations.

---

# Package Operations

LUMS supports the following high-level package actions:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

The server validates that the requested action is supported.

Package names are validated before a job is created.

For package updates, the server also verifies that the requested package is represented in the client's available update information.

---

# Package Manager Safety

The actual package transaction remains under control of the native package manager.

LUMS does not implement its own package installation mechanism.

```text
LUMS
  │
  └── controls requested operation
          │
          ▼
     Native package manager
          │
          ├── APT
          └── pacman
```

This keeps package resolution and dependency handling within the operating system's established package-management system.

---

# Reboot Handling

Some update operations can leave the system in a state where a reboot is required.

LUMS records reboot-related information as part of the update workflow.

The system does not automatically reboot a client merely because an update reports a reboot requirement.

This allows administrators to decide when a reboot should occur.

---

# Audit Logging

LUMS maintains application-level audit information for security-sensitive operations.

The audit trail supports accountability for operations such as:

* login-related events
* user administration
* client administration
* client-token rotation
* update-job operations
* other privileged administrative actions

The purpose is to provide an application-level record of administrative activity.

Audit logging is not intended to replace system logs.

---

# Security Hardening

The production container uses multiple runtime hardening controls.

The current baseline includes:

```text
Non-root application user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges
Restricted temporary filesystems
Read-only secret mount
Dedicated persistent data volume
Localhost-only application port
```

The Docker image also uses a pinned base-image digest for reproducible dependency provenance.

Build context is restricted through `.dockerignore`.

---

# Network Exposure

The LUMS application is not intended to expose its Gunicorn port directly to the network.

The host binding is:

```text
127.0.0.1:5050
```

External access is provided through Nginx.

The intended path is:

```text
Client / Browser
       │
       ▼
     HTTPS
       │
       ▼
     Nginx
       │
       ▼
127.0.0.1:5050
       │
       ▼
 LUMS container
```

Firewall rules additionally restrict unnecessary network exposure.

---

# Transport Security

Administrative and client communication is designed to use HTTPS/TLS.

Nginx provides the external TLS endpoint.

The LUMS application itself is therefore not required to terminate external TLS directly.

Clients must trust the certificate authority or certificate used by the LUMS server.

---

# Secrets and Configuration

Sensitive credentials are kept outside the application image.

The production application secret is provided through a protected host file and mounted read-only into the container.

The application reads the secret through:

```text
LUMS_SECRET_KEY_FILE
```

This avoids embedding the secret directly into the Docker image.

Secret material should never be committed to the repository.

---

# Dependency and Build Security

Production dependencies are pinned.

The container base image is pinned by digest.

Build context is restricted using `.dockerignore`.

The project also uses automated tests through the repository's CI workflow.

The goal is to reduce accidental dependency drift and prevent unrelated local files from entering the container build context.

---

# Security Audit Status

Security work is performed incrementally and documented in `security.md`.

The completed audit areas include:

* database integrity and runtime configuration
* timeout and process handling
* login rate limiting
* API validation
* session handling
* client-token rotation
* IP handling
* job recovery
* APT robustness
* Arch reboot detection
* automated tests
* simulation tests
* CI
* application and audit logging
* RBAC
* password and credential security
* dependency and build security
* Docker/container hardening
* secrets and build-context protection
* transport security
* API and SQL-injection protections
* filesystem and runtime permissions
* network exposure

The release/versioning stage remains intentionally separate from the implementation and security-hardening work.

LUMS does not currently claim to be a finalized stable release.

---

# Testing and Continuous Integration

LUMS uses automated tests for application and security-sensitive functionality.

The test suite covers areas including:

* authentication
* RBAC
* user management
* client management
* package management
* update-job creation
* update-job result validation
* job recovery
* API validation
* security controls

The current full-suite baseline is:

```text
155 passed
```

The test suite is also executed through the project's CI workflow.

Testing is considered part of the implementation process rather than a final optional step.

---

# Development Status

LUMS is an actively developed project.

The current implementation already includes:

* web-based administration
* Linux client management
* software inventory
* update detection
* package management
* update-job execution
* idle-aware execution
* job recovery
* reboot detection
* user management
* RBAC
* client-token rotation
* audit logging
* hardened container deployment
* automated tests and CI

The project is still undergoing documentation and release preparation.

No stable version tag or formal GitHub Release is claimed at this stage.

---

# Versioning and Releases

LUMS currently does not use a formal overall project version.

Individual components have their own versions where applicable.

Current component versions include:

```text
Agent   1.7.0
Watcher 1.2.1
```

A formal release will be created only after:

```text
Implementation
     ↓
Security review
     ↓
Documentation review
     ↓
Full test suite
     ↓
CI verification
     ↓
Version assignment
     ↓
Git tag
     ↓
GitHub Release
```

This keeps the first official release separate from ongoing development snapshots.

---

# Release Philosophy

The project follows a simple principle:

> **A feature is not finished merely because it works.**

Before a release, functionality must also be:

* tested
* documented
* reviewed
* reproducible
* operationally understandable
* security-reviewed

This is particularly important for software that performs administrative package operations on Linux systems.

---

# Current Project Direction

The current development focus is:

```text
Complete implementation
        ↓
Complete security review
        ↓
Complete documentation review
        ↓
Final consistency check
        ↓
Full regression testing
        ↓
Release preparation
```

The documentation set is being kept aligned with the actual implementation rather than with older development snapshots.

---

# Security Principle

LUMS follows the principle:

> **Trust as little as necessary, validate explicitly, and keep execution controlled.**

The system therefore separates:

```text
Authentication
Authorization
Validation
Execution
Result handling
Persistence
Auditability
```

This separation is intended to make both normal operation and failure analysis easier to understand.

# Supported Systems

LUMS is designed for Linux-based managed clients.

The currently supported package-management backends are:

| Operating System | Package Manager | Supported |
| ---------------- | --------------- | --------- |
| Debian           | APT / dpkg      | Yes       |
| Ubuntu           | APT / dpkg      | Yes       |
| Arch Linux       | pacman          | Yes       |

The server itself runs as a Dockerized Linux application.

Support is intentionally based on the capabilities of the implemented Agent and package-management layer rather than on a generic claim of compatibility with every Linux distribution.

---

# Client Requirements

A managed client requires:

* Linux
* systemd
* network connectivity to the LUMS server
* a supported package manager
* the LUMS Agent
* a valid client token
* trusted TLS communication with the server

The client must be able to execute the required package-management operations with the privileges necessary for system updates.

---

# Technology Stack

## Server

The server-side application uses:

```text
Python
Flask
Gunicorn
SQLite
```

The web interface uses:

```text
HTML
CSS
JavaScript
```

Nginx provides the external HTTPS endpoint.

---

## Client

The Linux client uses:

```text
Python
systemd
APT / dpkg
or
pacman
```

The client consists primarily of:

```text
Agent
Watcher
Package Manager
systemd timers/services
```

---

## Container

The server is deployed as a Docker container.

The production container uses:

```text
Python 3.13
Docker
Gunicorn
Flask
SQLite
```

The container runs with a dedicated non-root application user.

---

# Project Structure

The repository is organized according to the main application components.

A simplified structure is:

```text
LUMS/
├── agent/
│   ├── agent.py
│   └── package_manager.py
│
├── server/
│   ├── app.py
│   ├── package_search_migration.py
│   ├── static/
│   └── templates/
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
│
├── README.md
├── installation.md
├── administration.md
├── security.md
└── troubleshooting.md
```

The exact repository contents may evolve as development continues.

The structure above describes the major functional areas rather than every individual file.

---

# Server Application

The main server application is located in:

```text
server/app.py
```

It provides the central Flask application and handles functionality such as:

* authentication
* sessions
* RBAC
* client management
* update jobs
* package search
* package-management job creation
* user management
* audit logging
* API endpoints
* database interaction

The server is intentionally kept separate from the client execution code.

---

# Agent

The Linux Agent is located in:

```text
agent/agent.py
```

The Agent is responsible for communication between the managed Linux system and the LUMS server.

Its responsibilities include:

* client authentication
* system information reporting
* package inventory
* update detection
* package operations
* job execution
* result reporting
* reboot-related state
* execution recovery

The Agent does not replace the operating system's package manager.

---

# Package Manager Layer

Package-manager-specific functionality is separated into:

```text
agent/package_manager.py
```

This layer provides a common interface for supported package-management operations.

The higher-level Agent can therefore work with operations such as:

```text
search
inventory
updates
install
remove
update
system update
```

without having to duplicate the entire job workflow for every supported Linux distribution.

---

# Watcher

The execution watcher controls the processing of pending update jobs.

Its responsibilities include:

* checking for pending work
* respecting idle-aware execution
* recovering interrupted work
* claiming jobs
* starting execution
* handling execution results

This separates scheduling and execution control from the regular inventory/reporting path.

---

# Systemd Integration

The Linux client uses systemd to schedule recurring operations.

The conceptual structure is:

```text
Reporting
    │
    ▼
lums-agent.timer
    │
    ▼
lums-agent.service
    │
    ▼
agent.py
```

and:

```text
Execution
    │
    ▼
Watcher timer
    │
    ▼
Watcher service
    │
    ▼
watcher.py
```

This allows reporting and update execution to remain independent.

---

# Idle-Aware Execution

LUMS can defer update execution when a system is actively being used.

The current idle threshold is:

```text
300 seconds
```

The client uses the available systemd-logind information for idle detection.

The intent is to avoid starting potentially disruptive update operations while the system is actively being used.

If idle information is unavailable, the client reports that state rather than pretending that idle detection succeeded.

---

# Update Job Lifecycle

A typical update job follows this lifecycle:

```text
Created
   │
   ▼
PENDING
   │
   ▼
Claimed
   │
   ▼
RUNNING
   │
   ├───────────────┐
   │               │
   ▼               ▼
SUCCESS          FAILED
```

Interrupted work can additionally enter a recovery path.

The server remains the authoritative source for the recorded job state.

---

# Job Types

LUMS currently supports the following high-level update operations:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Package-specific operations can contain one or more package items.

The job system records the requested operation and its execution state.

---

# Job Recovery

Job execution is designed to survive interruptions such as:

* client restart
* Agent interruption
* system restart
* server restart
* interrupted package operations

Recovery uses the recorded execution state to determine which work still needs to be processed.

Already successful package items are preserved where the recovery logic can establish that they have completed successfully.

---

# Result Validation

Client-reported results are validated by the server before being applied to persistent job state.

This provides an additional boundary between:

```text
Client-side execution
```

and:

```text
Server-side application state
```

The server does not simply trust arbitrary result data because it originated from a managed client.

---

# User Management

Administrators can manage LUMS web users.

The user-management functionality includes:

* creating users
* assigning roles
* enabling or disabling accounts
* viewing user information

User management is restricted to Administrators.

The available roles are:

```text
Administrator
Operator
Viewer
```

Passwords are securely hashed before being stored.

---

# Client Management

Administrators can manage the clients registered with LUMS.

Client administration includes functionality such as:

* viewing clients
* creating clients
* disabling clients
* rotating client tokens

Client administration is separate from package-management operations.

This prevents routine update work from automatically granting client-administration privileges.

---

# Update History

LUMS records update-job information so administrators can inspect previous operations.

The history provides operational visibility into:

* which client was targeted
* which operation was requested
* execution state
* package-related information
* execution results
* timestamps

Access to update history follows the RBAC model.

Viewers do not receive access to update history.

---

# Auditability

LUMS distinguishes between:

```text
Update History
```

and:

```text
Audit Logging
```

Update history describes update-job activity.

Audit logging describes security-sensitive administrative activity.

The distinction makes it possible to answer different operational questions.

For example:

```text
Update History:
"What happened to this update job?"

Audit Log:
"Who performed this administrative action?"
```

---

# Testing Strategy

Testing is performed at multiple levels.

## Unit and API Tests

Individual application components and API behavior are tested independently.

Examples include:

* RBAC
* user management
* package search
* job-result validation
* authentication
* input validation

---

## Integration Testing

Integration-oriented tests verify that multiple components work together correctly.

Examples include:

* update-job creation
* client communication
* package-management workflows
* job recovery
* result processing

---

## Simulation Testing

Simulation tests are used for workflows where executing a real package transaction would be undesirable or unnecessary.

This allows execution logic to be tested without requiring an actual system update.

---

## End-to-End Testing

End-to-end validation follows the complete workflow:

```text
Web Interface
      │
      ▼
API
      │
      ▼
SQLite
      │
      ▼
Client
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
SQLite
      │
      ▼
Web Interface
```

This verifies that the individual components still work together after changes.

---

# Continuous Integration

The project uses CI to execute the automated test suite.

CI provides an additional verification layer before changes are considered ready for further integration.

The current test baseline is:

```text
155 passed
```

The exact number may increase as additional tests are introduced.

The important requirement is that the complete test suite remains successful.

---

# Documentation

The project maintains separate documentation for different audiences.

### README

Provides the project overview and explains the architecture, features and current status.

### installation.md

Contains the installation and deployment procedure.

### administration.md

Contains operational administration procedures.

### security.md

Documents the security architecture, audit areas and hardening baseline.

### troubleshooting.md

Contains diagnostic procedures and recovery guidance.

The README should remain concise enough to serve as the project's entry point.

Detailed operational instructions belong in the dedicated documentation.

---

# Documentation Principle

Documentation is maintained against the actual implementation.

Older development assumptions should not be carried forward merely because they existed in an earlier version of the documentation.

In particular, documentation should reflect the current:

* RBAC model
* database configuration
* container security baseline
* package-management workflow
* testing baseline
* deployment model

This is important because LUMS is an infrastructure-management application where incorrect documentation can itself become an operational risk.

---

# Development Workflow

The project follows a deliberate development sequence:

```text
Build
  ↓
Test
  ↓
Secure
  ↓
Document
```

Changes should first work correctly.

They should then be tested.

Security-sensitive behavior is reviewed and hardened.

Finally, the documentation is updated to reflect the actual implementation.

---

# Change Verification

Before a significant change is considered complete, the relevant layers should be checked.

```text
Code
 │
 ├── Tests
 │
 ├── Runtime
 │
 ├── Security
 │
 └── Documentation
```

A successful code change is therefore not automatically considered a completed project change.

---

# Operational Philosophy

LUMS is designed around explicit state and controlled operations.

The system should make it possible to determine:

```text
What was requested?
        ↓
Who requested it?
        ↓
Which client was targeted?
        ↓
Was it authorized?
        ↓
Was it executed?
        ↓
What was the result?
        ↓
What state was persisted?
```

This approach is particularly important when software is used to manage package updates remotely.

---

# Project Scope

LUMS is intentionally focused on Linux update management.

It is not intended to become:

* a general endpoint-management platform
* a full configuration-management system
* a replacement for enterprise patch-management suites
* a general-purpose remote shell
* a monitoring platform

Its primary purpose is:

> **Controlled Linux update management with clear state, explicit authorization and understandable operations.**

# Current Status

LUMS is currently in active development and in the final stages of implementation, security review and documentation alignment.

The core management workflow is implemented:

```text
Client Registration
       ↓
Client Authentication
       ↓
Inventory
       ↓
Update Detection
       ↓
Update Job
       ↓
Authorization
       ↓
Client Execution
       ↓
Result Validation
       ↓
Persistent State
       ↓
Audit / History
```

The current implementation includes:

* Linux client management
* software inventory
* update detection
* package search
* package installation
* package removal
* package updates
* system updates
* update-job execution
* idle-aware execution
* job recovery
* reboot detection
* user management
* role-based access control
* client-token rotation
* audit logging
* container hardening
* HTTPS/TLS
* automated testing
* continuous integration

The project is not yet presented as a stable final release.

---

# Security Status

Security hardening has been performed across the main application, API, client and deployment layers.

Completed areas include:

* authentication security
* session handling
* CSRF protection
* RBAC
* client-token handling
* API input validation
* SQL-injection protection
* job authorization
* result validation
* job recovery
* package-manager robustness
* password security
* dependency and build security
* Docker hardening
* filesystem and runtime permissions
* network exposure
* transport security
* secrets handling
* audit logging

The detailed security status and audit history are documented in:

```text
security.md
```

The release/versioning stage remains intentionally separate from the completed hardening work.

---

# Release Status

LUMS currently has no formal overall release version.

There is no stable Git tag or official GitHub Release yet.

This is intentional.

The first official release is planned only after the remaining implementation, documentation and verification work has been completed.

The intended release sequence is:

```text
Implementation
      ↓
Security Review
      ↓
Documentation Review
      ↓
Full Regression Test
      ↓
CI Verification
      ↓
Version
      ↓
Git Tag
      ↓
GitHub Release
```

Development snapshots should therefore not be confused with a stable release.

---

# Roadmap

The roadmap focuses on completing and consolidating the existing system before expanding its scope.

## Near Term

* complete documentation consistency review
* complete remaining implementation checks
* perform final regression testing
* verify deployment documentation against the current runtime
* verify security documentation against the current implementation
* prepare the first formal version

## Release Preparation

* assign the initial project version
* create the first Git tag
* create the first GitHub Release
* publish release notes
* freeze the corresponding release documentation

## Future Development

Potential future work may include:

* additional Linux distribution support
* further package-management improvements
* additional operational visibility
* expanded testing coverage
* additional administrative tooling
* further security hardening

Future features remain subject to the project's scope and maintenance goals.

---

# What LUMS Is Not

LUMS deliberately avoids trying to solve every infrastructure-management problem.

It is not intended to replace:

* enterprise endpoint-management platforms
* configuration-management systems
* SIEM platforms
* vulnerability scanners
* monitoring systems
* general remote-administration tools

LUMS focuses specifically on Linux update management.

This narrow scope is intended to keep the system understandable and maintainable.

---

# Design Philosophy

The project is built around a few simple principles.

## Understandability

The system should remain understandable without requiring a large external platform.

## Explicit State

Important operations should have a visible and persistent state.

## Controlled Execution

Package operations should be executed through explicit, validated workflows.

## Separation of Responsibilities

Authentication, authorization, execution, persistence and auditing should remain distinct concerns.

## Native Tools

LUMS should use the operating system's native package-management mechanisms instead of replacing them.

## Security by Layers

Security should not depend on a single control.

## Documentation as Part of the System

Documentation should describe what the software actually does.

---

# Development Principle

LUMS follows:

> **Build → Test → Secure → Document**

The project intentionally treats documentation and security review as part of implementation rather than as activities performed only immediately before release.

---

# Repository

The project source code is maintained in the Git repository:

```text
NovaForgeCtrl/LUMS
```

The repository contains:

* server application
* Linux Agent
* package-management layer
* web interface
* automated tests
* Docker configuration
* deployment configuration
* project documentation

The repository is the authoritative source for the implementation.

---

# Documentation Set

The main documentation files are:

```text
README.md
installation.md
administration.md
security.md
troubleshooting.md
```

Their responsibilities are intentionally separated.

```text
README
   │
   ├── What is LUMS?
   ├── Architecture
   ├── Features
   ├── Security overview
   └── Project status
          │
          ├── installation.md
          │      └── Deployment
          │
          ├── administration.md
          │      └── Operations
          │
          ├── security.md
          │      └── Security
          │
          └── troubleshooting.md
                 └── Diagnosis
```

---

# License

LUMS is released under the:

```text
MIT License
```

See the repository's `LICENSE` file for the complete license text.

The license applies to the project according to the terms defined in that file.

---

# Community and Contributions

LUMS is developed as an open-source project.

Contributions, issue reports and technical discussion are welcome.

Useful contributions include:

* bug reports
* reproducible problem reports
* documentation improvements
* tests
* security findings
* package-management improvements
* Linux distribution support
* code improvements

When reporting a problem, include enough technical information to reproduce it while removing secrets, tokens and other sensitive information.

---

# Security Reports

Security-related findings should be handled responsibly.

Do not publish:

* client tokens
* passwords
* application secrets
* private keys
* authentication cookies
* database copies containing sensitive information

in public issue reports.

Provide a clear description of:

```text
Affected component
       ↓
Observed behavior
       ↓
Expected behavior
       ↓
Reproduction steps
       ↓
Security impact
```

Sensitive information should be redacted before sharing logs or configuration.

---

# Contributing Principle

Contributions should preserve the project's core goals:

```text
Simple
Understandable
Tested
Secure
Documented
```

A change that adds functionality but makes the system significantly harder to understand should be evaluated carefully.

---

# Project Identity

LUMS stands for:

> **Linux Update Management Server**

The project slogan is:

> **Linux Update Management without the noise.**

The name reflects the project's central goal:

```text
Linux
  +
Update Management
  +
Controlled Execution
  +
Clear State
```

---

# Final Architecture Overview

The complete system can be summarized as:

```text
                         ┌───────────────────┐
                         │   Administrator   │
                         │     Operator      │
                         │      Viewer       │
                         └─────────┬─────────┘
                                   │
                              HTTPS / TLS
                                   │
                                   ▼
                         ┌───────────────────┐
                         │       Nginx       │
                         └─────────┬─────────┘
                                   │
                            localhost:5050
                                   │
                                   ▼
                         ┌───────────────────┐
                         │    LUMS Server    │
                         │                   │
                         │ Flask / Gunicorn  │
                         └─────────┬─────────┘
                                   │
                              SQLite DB
                                   │
                                   ▼
                         ┌───────────────────┐
                         │    lums-data      │
                         └───────────────────┘
                                   ▲
                                   │
                              HTTPS / TLS
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
             ┌──────────────┐              ┌──────────────┐
             │ Linux Client │              │ Linux Client │
             │              │              │              │
             │    Agent     │              │    Agent     │
             │   Watcher    │              │   Watcher    │
             │   Package    │              │   Package    │
             │   Manager    │              │   Manager    │
             └──────┬───────┘              └──────┬───────┘
                    │                             │
                    ▼                             ▼
                 APT/dpkg                    pacman
                    │                             │
                    ▼                             ▼
                 Debian/                     Arch Linux
                 Ubuntu
```

---

# Final Principle

LUMS is built around a straightforward idea:

> **Manage Linux updates centrally without hiding what is happening underneath.**

The server manages state and authorization.

The client performs the actual system operation.

The operating system's package manager remains responsible for package handling.

The result is reported back and persisted.

Security controls protect each boundary.

Documentation explains the system.

That separation is the foundation of LUMS.

---

# Status at a Glance

```text
Core Update Management       ✓
Client Management            ✓
Software Inventory           ✓
Update Detection             ✓
Package Management           ✓
Update Jobs                 ✓
Idle-Aware Execution         ✓
Job Recovery                 ✓
Reboot Detection             ✓
User Management              ✓
RBAC                         ✓
Client Token Rotation        ✓
Audit Logging                ✓
Container Hardening          ✓
HTTPS / TLS                  ✓
Automated Tests              ✓
CI                           ✓
Documentation Review         In Progress
Formal Release               Not Yet
```

---

# Closing

LUMS is intentionally being developed step by step.

The goal is not simply to produce a system that can install updates.

The goal is to produce a system where update management is:

```text
Controlled
Auditable
Understandable
Recoverable
Secure
```

> **Linux Update Management without the noise.**
