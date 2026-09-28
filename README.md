# LUMS

## Linux Update Management Server

> **Linux Update Management without the noise.**

LUMS is a lightweight Linux update management platform for small labs, test environments and infrastructure projects.

It provides centralized client management, package and update inventory, authenticated agent communication and controlled update execution — without requiring a large management stack.

```text
              ┌─────────────────────────────┐
              │            Nginx            │
              │          HTTPS / TLS        │
              └──────────────┬──────────────┘
                             │
                             │ localhost
                             ▼
              ┌─────────────────────────────┐
              │       Docker: lums          │
              │                             │
              │   Gunicorn → Flask          │
              │          :5000              │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │        lums-data            │
              │                             │
              │      SQLite / lums.db       │
              └─────────────────────────────┘
                       ▲          ▲
                       │          │
                    HTTPS      HTTPS
                       │          │
              ┌────────┴───┐  ┌──┴──────────┐
              │ Linux      │  │ Linux       │
              │ Client     │  │ Client      │
              │ Agent      │  │ Agent       │
              └────────────┘  └─────────────┘
```

---

# What is LUMS?

LUMS centralizes Linux update management without trying to replace the operating system's package manager.

The LUMS server manages:

* Linux client inventory
* Installed packages
* Available updates
* Client authentication
* Client tokens
* Update jobs
* Job execution state
* Execution results
* Administrative auditing
* Running-job recovery
* Role-based access control

The client agent handles:

* System reporting
* Package inventory
* Update inventory
* Idle-state detection
* Authorized update execution
* Result reporting

The operating system remains responsible for the actual package management.

```text
          LUMS
            │
     ┌──────┴───────┐
     │              │
 Management       Execution
     │              │
     ▼              ▼
 What should     What may
 happen?         happen?
     │              │
     └──────┬───────┘
            ▼
      Controlled action
```

---

# Why LUMS?

LUMS follows a simple idea:

> **Centralize the management. Keep execution controlled.**

The project focuses on:

* Simple architecture
* Transparent operation
* Minimal dependencies
* Secure client authentication
* Controlled execution
* Auditable changes
* Explicit recovery
* Container hardening
* Role-based access control
* Automated testing
* Documentation-first development

LUMS is designed to remain understandable.

The goal is not to hide infrastructure behind layers of abstraction.

The goal is to make it possible to see:

```text
What changed?
      ↓
Where did it change?
      ↓
Which client was affected?
      ↓
What was executed?
      ↓
What result was reported?
```

---

# Features

## Client Management

LUMS maintains a central inventory of registered Linux clients.

Client information includes data such as:

* Hostname
* IP address
* Operating system
* Architecture
* Kernel
* Package count
* Available updates
* Agent version
* Last report
* Online state

---

## Package and Update Inventory

The agent reports installed packages and available updates to the LUMS server.

This allows administrators to see the state of clients centrally without replacing the native package manager.

---

## Update Jobs

Authorized users can create controlled update jobs according to their assigned role.

Supported job actions include:

```text
UPDATE_SYSTEM
UPDATE_PACKAGE
INSTALL_PACKAGE
REMOVE_PACKAGE
```

Jobs move through a controlled lifecycle:

```text
pending
   │
   ▼
waiting_for_idle
   │
   ▼
running
   │
   ├── success
   ├── partial
   ├── failed
   └── abandoned
```

Jobs are claimed atomically so that the same job cannot accidentally be executed by multiple clients.

---

# Idle-Aware Execution

LUMS does not blindly execute update jobs as soon as they appear.

The client checks its local activity state before executing an update job.

The current Linux implementation uses:

```text
systemd-logind
     │
     ▼
  loginctl
     │
     ▼
Idle state detection
```

The current idle threshold is:

```text
300 seconds
```

The agent reports the active detection mechanism through:

```text
idle_source=loginctl
idle_supported=True
```

when supported.

If idle detection is unavailable or cannot be determined safely, automatic execution does not proceed.

---

# Running-Job Recovery

A job must not remain permanently stuck in:

```text
running
```

if the client disappears during execution.

The execution watcher checks for existing running jobs before claiming new work.

```text
Running Job
     │
     ▼
Client interruption
     │
     ▼
Watcher detects state
     │
     ▼
Recovery
     │
     ├── Safe recovery
     │
     └── Abandoned
```

Recovery is associated with the authenticated client and uses ownership and state checks to avoid unsafe races.

This prevents a failed recovery from silently producing a second active execution.

---

# Client Authentication

Every client uses its own Bearer token.

```http
Authorization: Bearer <CLIENT_TOKEN>
```

Tokens are not stored as plaintext values.

LUMS stores a SHA-256 hexadecimal digest of the client token.

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

This means the server does not need to store the original token in order to authenticate the client.

---

# Token Rotation

Client tokens can be rotated from the administration interface.

A rotation:

1. Generates a new token.
2. Stores its digest.
3. Invalidates the previous token.
4. Records the operation in the audit log.
5. Displays the new token once.

After rotation:

```text
Old token → invalid
New token → valid
```

Plaintext tokens are not written to the audit log.

---

# Role-Based Access Control

LUMS provides role-based access control for administrative users.

The current roles are:

```text
administrator
operator
viewer
```

### Administrator

Administrators have full administrative access, including:

* Client management
* Token rotation
* Client removal
* Update job management
* User and security administration where implemented

### Operator

Operators can perform operational update-management tasks, including:

* View clients
* View package and update information
* View jobs and history
* Create and execute update jobs

Operators cannot perform administrator-only client or token management actions.

### Viewer

Viewers have read-only access to management information, including:

* Clients
* Packages
* Updates
* Jobs
* History

Viewers cannot create update jobs or perform administrative changes.

Client agents remain independently authenticated through their own Bearer tokens. Agent communication is therefore separate from the web application's user-role authorization.

---

# Security

LUMS includes several security and hardening mechanisms.

### Application

* Argon2 password hashing
* Session handling
* CSRF protection
* Security headers
* Client authentication
* Client-specific authorization
* Bearer token authentication
* Token rotation
* Login rate limiting
* Role-based access control
* Audit logging
* Input validation
* Update result validation
* Session revocation
* Recovery and execution safeguards

### Database

SQLite is configured with:

```text
foreign_keys = ON
busy_timeout = 5000
journal_mode = WAL
```

Database integrity and foreign-key checks are part of the security verification workflow.

### Container

The production container runs:

```text
User=lums
read-only root filesystem
CapDrop=ALL
Privileged=false
```

The container only receives the writable locations it actually needs.

Temporary storage is provided through a restricted `/tmp` tmpfs:

```text
rw,nosuid,nodev,noexec
```

The Flask secret is provided through a read-only secret file rather than a normal environment variable.

```text
Host:
    /etc/lums/secrets/lums_secret

Container:
    /run/secrets/lums_secret
```

The production application uses:

```text
LUMS_SECRET_KEY_FILE
```

instead of exposing the secret as:

```text
LUMS_SECRET_KEY
```

in the normal container environment.

---

# Security Audit Status

The security audit has completed the following areas:

```text
[x] SQLite Foreign Keys
[x] SQLite WAL / Busy Timeout
[x] Update Timeout / Process Termination
[x] Login Rate Limiting
[x] API Input Validation
[x] Session Revocation
[x] Token Rotation
[x] get_ip() / Offline-Network Handling
[x] Job Recovery / Checkpointing
[x] APT Robustness
[x] Arch Reboot Detection
[x] Unit Tests / Test Coverage
[x] Simulation Tests
[x] Continuous Integration
[x] Logging
[x] RBAC
```

The project currently has automated test coverage for the implemented security and application behavior.

The current test suite passes:

```text
79 passed
```

The update execution timeout uses:

```text
timeout
   ↓
terminate()
   ↓
10-second grace period
   ↓
kill() fallback
```

Login rate limiting currently escalates through:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

Versioning and release management have been reviewed as part of the audit, but release/versioning infrastructure has deliberately not yet been implemented. The project is still under active development and is not being presented as a finished release.

The remaining documentation work is tracked separately as the final audit area.
