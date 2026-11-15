# Documentación de Seguridad de LUMS

**LUMS — Servidor de Gestión de Actualizaciones de Linux**

Este documento describe la arquitectura de seguridad actual, controles de seguridad implementados, resultados de auditoría de seguridad, limitaciones operacionales, and decisiones de diseño relacionadas con la seguridad of LUMS.

El documento refleja el **estado actual del sistema implementado**. Las mejoras planificadas o futuras se identifican explícitamente como tales.

---

# Principios de Seguridad

LUMS sigue un enfoque de defensa en profundidad para la gestión de actualizaciones de Linux.

El modelo de seguridad separa la autenticación administrativa, la autenticación del cliente, la autorización, la ejecución de actualizaciones controlada y el registro de auditoría.

Los objetivos de seguridad primarios son:

* acceso administrativo autenticado
* autorización basada en roles
* comunicación de cliente autenticada
* ejecución de actualización controlada
* protección contra la ejecución de trabajos concurrentes
* trabajos de actualización recuperables
* secretos protegidos
* ejecución de contenedor controlada
* operaciones sensibles a la seguridad auditables
* manejo predecible de fallos
* pruebas de regresión de seguridad

LUMS está destinado principalmente a entornos de infraestructura controlada, laboratorio y red interna.

No debe exponerse directamente a Internet público sin una revisión de seguridad adicional y controles de red apropiados.

---

# Arquitectura de Seguridad

LUMS consta de los siguientes componentes relevantes para la seguridad:

* Interfaz de administración web
* API REST
* Base de datos SQLite
* Agente de LUMS en clientes gestionados
* Backends de gestión de paquetes APT y pacman
* Mecanismos de trabajo de actualización y recuperación
* Proxy inverso HTTPS de Nginx
* Contenedor Docker reforzado

El flujo de gestión básico es:

Browser → HTTPS/Nginx → LUMS API → SQLite → LUMS Agent → Package Manager → Result → SQLite → Web UI

La autenticación y la autorización están deliberadamente separadas.

Una sesión autenticada válida no otorga automáticamente acceso a todas las operaciones administrativas.

La autorización se aplica en el lado del servidor. La interfaz web además oculta funciones que no están disponibles para la función actual, pero la visibilidad de la interfaz de usuario nunca se trata como un límite de seguridad.

---

## Autenticación Administrativa

Los usuarios administrativos se autentican a través de la interfaz web de LUMS.

Las contraseñas nunca se almacenan en texto plano. LUMS utiliza hash de contraseña basado en Argon2 para el almacenamiento de contraseñas.

Las sesiones administrativas utilizan:

* manejo de sesión autenticado del lado del servidor
* vencimiento de sesión
* regeneración de sesión
* protección CSRF para solicitudes de navegador que cambian el estado
* limitación de velocidad de inicio de sesión
* invalidación de sesión durante el cierre de sesión
* validación de rol del lado del servidor

Authentication and authorization remain separate security controls.

A successfully authenticated user must still possess the required permiso
for protected operations.

---

# Control de Acceso Basado en Roles

LUMS actualmente admite tres funciones de usuario web:

* `administrador`
* `operador`
* `visor`

Las plantillas de funciones se almacenan en `users.role`; individual permisos are stored
server-side in `user_permisos`.

El servidor carga los permisos efectivos para cada cuenta autenticada.
Client-side permiso information controls presentation only and never
replaces server-side authorization.

## Administrator

Los administradores tienen acceso administrativo y operativo completo.

Pueden:

* ver clientes
* crear clientes
* deshabilitar clientes
* rotar tokens de cliente
* ver paquetes instalados y actualizaciones disponibles
* crear trabajos de actualización
* ejecutar operaciones de actualización compatibles
* ver historial de trabajos de actualización
* usar gestión de paquetes
* usar funciones de mantenimiento del sistema
* gestionar usuarios
* gestionar funciones de usuario
* acceder a funciones administrativas

## Operator

Los operadores pueden realizar tareas de gestión de actualizaciones operativas.

Pueden:

* ver clientes
* ver paquetes instalados y actualizaciones disponibles
* crear trabajos de actualización
* ejecutar operaciones de actualización compatibles
* ver historial de trabajos de actualización
* usar gestión de paquetes
* usar funciones de mantenimiento del sistema

Los operadores no pueden:

* gestionar usuarios
* cambiar funciones de usuario
* crear clientes
* deshabilitar clientes
* rotar tokens de cliente

## Viewer

Los espectadores tienen acceso restringido de solo lectura.

Pueden:

* ver clientes
* view installed software

Las siguientes áreas de gestión se ocultan de las cuentas de Viewer:

* Actualizaciones
* Trabajos de Actualización
* Historial de Actualizaciones
* Gestión de Paquetes
* Mantenimiento del Sistema

Las cuentas de Viewer no pueden realizar operaciones de gestión de actualizaciones que cambien el estado.

The server independently enforces these restrictions through authentication
and per-user permiso checks.

---

# Autenticación del Cliente

Cada cliente LUMS gestionado usa un individual Bearer token.

El mecanismo de autenticación sigue el modelo:

`Authorization: Bearer <CLIENT_TOKEN>`

El servidor no almacena tokens de cliente como valores de texto plano.

En su lugar, LUMS almacena un resumen hexadecimal SHA-256 del token del cliente.

El flujo de autenticación es:

Client Token → SHA-256 → Token Digest → SQLite

Client authentication verifies the authenticated token against the registered client and additionally checks the relevant client state.

The security model does not use a source IP address as the sole proof of client identity.

This allows LUMS to operate in:

* private laboratory networks
* isolated infrastructure
* NAT-based networks
* offline environments
* networks where client addresses may change

Client tokens can be rotated by authorized administradors.

Una rotación de token genera un token de reemplazo, almacena solo su resumen, invalida el token anterior, registra la acción administrativa en el registro de auditoría y presenta el token de reemplazo una vez.

Los valores de token de cliente de texto plano no se escriben en registros de auditoría.

---

# Seguridad de Telemetría

Los datos de telemetría (CPU, memoria, métricas de red) están sujetos al mismo modelo de autenticación y autorización que otros componentes del lado del cliente.

## Envío de Telemetría

Las muestras de telemetría se envían a través de `POST /api/telemetry` y requieren:

* Autenticación del cliente usando el mismo token de cliente que el informe de actualización
* HTTPS para conexiones remotas (HTTP simple solo para `127.0.0.1`, `localhost`, `::1`)
* Verificación de certificado CA opcional para autoridades de certificado personalizadas

The telemetry endpoint validates:

* Client token authentication against the stored SHA-256 digest
* Payload structure and field types
* Numeric ranges (CPU and memory 0-100%, bytes non-negative)
* Sample freshness (rejects samples with excessively old or future timestamps)

Invalid payloads are rejected with appropriate HTTP status codes.

The client token is not included in the JSON payload and is not logged in agent output.

## Control de Acceso de Telemetría

Las consultas de historial de telemetría y descripción general de la flota requieren el `clients.view` permiso.

Los siguientes puntos finales requieren autenticación:

* `GET /api/telemetry/history/<client_id>?hours=1-168` - historial del cliente
* `GET /api/telemetry/overview` - resumen de la flota

Las solicitudes no autenticadas o no autorizadas se rechazan.

## Clasificación de Datos de Telemetría

La telemetría contiene solo métricas de recursos del sistema:

* porcentaje de utilización de CPU
* porcentaje de utilización de memoria y bytes
* Contadores de bytes de red (acumulativo, sin datos de carga útil)

La telemetría **no** contiene:

* Operaciones de gestión de paquetes
* Salida de comando o registros
* Actividad del usuario
* Contenidos del archivo
* Datos de paquete de red
* Valores de configuración privada

Esta clasificación de datos limita la telemetría a métricas de utilización de recursos apropiadas para el monitoreo operativo.

## Data Storage and Retention

Telemetry samples are stored in the `telemetry_samples` table with the following schema:

```sql
CREATE TABLE telemetry_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    cpu_percent REAL NOT NULL,
    memory_percent REAL NOT NULL,
    memory_total_bytes INTEGER NOT NULL,
    memory_available_bytes INTEGER NOT NULL,
    network_rx_bytes INTEGER,
    network_tx_bytes INTEGER,
    FOREIGN KEY (client_id) REFERENCES clients(id)
)
```

Data older than 7 days is automatically removed during the processing of new telemetry submissions.

Telemetry data is subject to the same backup and encryption considerations as the rest of the LUMS database.

Backups are not encrypted by LUMS; use host-level encryption or separate backup encryption where required.

---

# Auditoría de Seguridad

La auditoría de seguridad se realiza incrementalmente.

Cada área de auditoría se revisa frente a la implementación real, seguida de pruebas automatizadas, verificación aislada o verificación de producción cuando sea aplicable.

Áreas de auditoría actuales:

| Audit | Area                                   | Status                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | SQLite Foreign Keys                    | APROBADO                      |
| #02   | SQLite Runtime Configuration           | APROBADO                      |
| #03   | Update Timeout Handling                | APROBADO                      |
| #04   | Login Rate Limiting                    | APROBADO                      |
| #05   | API Input Validation                   | APROBADO                      |
| #06   | Session Revocation                     | APROBADO                      |
| #07   | Client Token Rotation                  | APROBADO                      |
| #08   | IP Address Handling / Offline Networks | APROBADO                      |
| #09   | Job Recovery / Checkpointing           | APROBADO                      |
| #10   | APT Robustness                         | APROBADO                      |
| #11   | Arch Reboot Detection                  | APROBADO                      |
| #12   | Unit Tests / API Result Validation     | APROBADO                      |
| #13   | Simulation Tests                       | APROBADO                      |
| #14   | Continuous Integration                 | APROBADO                      |
| #15   | Application / Audit Logging            | APROBADO                      |
| #16   | Versioning / Releases                  | REVISADO — ABIERTO POR DISEÑO |
| #17   | Control de Acceso Basado en Roles              | APROBADO                      |
| #18   | Documentation Review                   | EN PROGRESO               |

Audit #16 is intentionally different from the technical security controls above.

LUMS currently has no official stable release, no release tag, and no GitHub Release. This is intentional because the project remains under active development.

Audit #18 remains open until the complete documentation set has been reviewed and synchronized with the current implementation.

# Auditoría de Seguridad #01

## SQLite Foreign Keys

SQLite foreign-key enforcement is enabled for application database connections.

The application explicitly enables:

`PRAGMA foreign_keys = ON`

This ensures that referential integrity is enforced for relationships between related database records.

The audit verified:

* runtime foreign-key enforcement
* foreign-key integrity
* client lifecycle behavior
* client disable behavior
* preservation of historical job information
* preservation of audit information

Client state is handled conservatively.

Where appropriate, clients are disabled rather than removed in a way that would destroy historical operational information.

**Status: APROBADO**

---

# Auditoría de Seguridad #02

## SQLite Runtime Configuration

The production Base de datos SQLite was reviewed for its runtime configuration.

The verified production configuration is:

* `journal_mode`: `wal`
* `busy_timeout`: `5000`
* `synchronous`: `2`

The application explicitly enables:

`PRAGMA foreign_keys = ON`

The production database currently uses WAL mode.

The database configuration was documented based on the actual verified production state rather than the historical development configuration.

The configured busy timeout reduces immediate database failures when another transaction temporarily holds the database.

The application-level foreign-key setting ensures referential integrity for each database connection.

The audit included production verification of the active SQLite configuration.

**Status: APROBADO**

---

# Auditoría de Seguridad #03

## Update Timeout and Process Handling

Update execution is protected against indefinitely blocking package-manager processes.

The execution flow is:

Start process
↓
Read process output
↓
Monitor timeout
↓
Timeout reached?
↓
Terminate process
↓
Grace period
↓
Process still running?
↓
Kill process if required
↓
Complete job

The implementation uses controlled subprocess handling so that silent processes cannot block indefinitely while waiting for output.

Timeout handling was tested against:

* silent processes
* normal process completion
* timeout conditions
* processes resistant to normal termination
* kill fallback
* integration-level timeout behavior

The timeout mechanism prevents a package-management operation from remaining indefinitely in an active state.

Errors and timeout conditions are returned as controlled job results and are recorded in the job state.

The current documented LUMS Agent version is:

`1.7.0`

**Status: APROBADO**

---

# Auditoría de Seguridad #04

## Login Rate Limiting

Administrative login attempts are rate limited.

The current escalation policy is:

* 5 failed attempts → 30 seconds
* 6 failed attempts → 60 seconds
* 7 failed attempts → 120 seconds
* 8 or more failed attempts → 300 seconds

The rate-limit state is persisted in SQLite.

Concurrent login failures use transactional database locking with:

`BEGIN IMMEDIATE`

This prevents concurrent authentication failures from bypassing the intended rate-limit state through race conditions.

A successful authentication clears the applicable failure state.

The audit covered:

* isolated rate-limit behavior
* concurrent authentication failures
* transaction rollback
* database-lock handling
* successful-login reset behavior
* rate-limit audit events
* production login behavior

The rate limiter therefore provides a server-side control against repeated authentication attempts rather than relying on client-side behavior.

**Status: APROBADO**

---

# Audit Status After Part 2

The first four security audit areas are complete:

| Audit | Area                              | Status |
| ----- | --------------------------------- | ------ |
| #01   | SQLite Foreign Keys               | APROBADO   |
| #02   | SQLite Runtime Configuration      | APROBADO   |
| #03   | Update Timeout / Process Handling | APROBADO   |
| #04   | Login Rate Limiting               | APROBADO   |

The following audit areas are documented in the subsequent sections:

* #05 API Input Validation
* #06 Session Revocation
* #07 Client Token Rotation
* #08 IP Address Handling / Offline Networks
* #09 Job Recovery / Checkpointing
* #10 APT Robustness
* #11 Arch Reboot Detection
* #12 Unit Tests / API Result Validation
* #13 Simulation Tests
* #14 Continuous Integration
* #15 Application / Audit Logging
* #16 Versioning / Releases
* #17 Control de Acceso Basado en Roles

Audit #18 — Documentation Review — remains open until the complete documentation set has been reviewed and synchronized with the current implementation.

# Auditoría de Seguridad #05

## API Input Validation

LUMS validates security-sensitive API input on the server side.

Client-supplied values are not trusted simply because they originate from the authenticated web interface or a registered client.

Validation is applied to relevant API parameters, including:

* client identifiers
* package names
* update-job actions
* package lists
* search parameters
* user-management parameters
* client-token operations
* job-result data

Package names are validated before they are passed to package-management operations.

The update-job API accepts only explicitly supported actions.

The currently supported package-related actions are:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Unexpected actions are rejected.

Package lists are validated before job creation.

For `UPDATE_PACKAGE`, the requested package must also be present in the client's available-update information.

Database queries use SQL parametrizado rather than constructing SQL statements from untrusted input.

This prevents user-controlled values from being interpreted as SQL syntax.

The audit included negative input testing and SQL-injection-oriented test cases.

The validation controls were also verified through the automated test suite.

**Status: APROBADO**

---

# Auditoría de Seguridad #06

## Session Revocation

LUMS protects authenticated administrative sessions against continued use after logout.

Session handling includes:

* authenticated server-side sessions
* vencimiento de sesión
* regeneración de sesión
* logout invalidation
* autenticación del lado del servidor checks
* validación de rol del lado del servidor

Logging out invalidates the active authenticated session.

Protected API endpoints require an authenticated session and do not rely on client-side state to determine whether the user remains authenticated.

Session state is therefore evaluated by the server for protected operations.

State-changing browser requests additionally require protección CSRF.

The audit verified that:

* authenticated access works normally
* protected endpoints reject unauthenticated requests
* logout invalidates the active session
* a previously authenticated session cannot continue using protected functionality after revocation
* role information is evaluated server-side

**Status: APROBADO**

---

# Auditoría de Seguridad #07

## Client Token Rotation

Each managed LUMS client uses an individual authentication token.

Client tokens are not stored as plaintext values.

Instead, LUMS stores the SHA-256 hexadecimal digest of the client token.

The authentication model is:

`Authorization: Bearer <CLIENT_TOKEN>`

The server hashes the supplied token and compares the resulting digest with the registered client token digest.

Authorized administradors can rotate a client's token.

Token rotation performs the following operations:

1. Generate a replacement token.
2. Calculate its SHA-256 digest.
3. Replace the stored client-token digest.
4. Invalidate the previous token.
5. Record the administrative action in the audit log.
6. Present the replacement token to the administrador.

The previous token cannot authenticate after rotation.

Plaintext token values are not written to audit logs.

The audit verified:

* successful token authentication
* token digest storage
* token rotation
* invalidation of the previous token
* authentication with the replacement token
* authorization requirements for token rotation
* registro de auditoría
* protection against unauthorized rotation

Client token rotation is restricted to administradors.

Operators and visors cannot rotar tokens de cliente.

**Status: APROBADO**

---

# Auditoría de Seguridad #08

## IP Address Handling and Offline Networks

LUMS does not use a client's source IP address as the sole proof of client identity.

Client authentication is based on the registered client token.

This design is intentional because managed clients may operate in environments where their network address changes.

Supported deployment scenarios include:

* private laboratory networks
* NAT-based networks
* isolated infrastructure
* dynamically addressed clients
* offline environments
* controlled internal networks

The server therefore separates:

**Network location**

from:

**Client identity**

A valid client token identifies the registered client.

The client's network address may still be recorded for operational and audit purposes, but it is not treated as an authentication credential.

The implementation also avoids assumptions that a client must be reachable from a fixed address.

This is particularly important for laboratory environments and infrastructure where network topology may change without changing the logical identity of the managed system.

The audit verified client authentication without relying on a fixed source IP address.

**Status: APROBADO**

---

# Audit Status After Part 3

The following security audit areas are complete:

| Audit | Area                                   | Status |
| ----- | -------------------------------------- | ------ |
| #01   | SQLite Foreign Keys                    | APROBADO   |
| #02   | SQLite Runtime Configuration           | APROBADO   |
| #03   | Update Timeout / Process Handling      | APROBADO   |
| #04   | Login Rate Limiting                    | APROBADO   |
| #05   | API Input Validation                   | APROBADO   |
| #06   | Session Revocation                     | APROBADO   |
| #07   | Client Token Rotation                  | APROBADO   |
| #08   | IP Address Handling / Offline Networks | APROBADO   |

The next section covers:

* #09 Job Recovery / Checkpointing
* #10 APT Robustness
* #11 Arch Reboot Detection
* #12 Unit Tests / API Result Validation

# Auditoría de Seguridad #09

## Job Recovery and Checkpointing

LUMS update jobs are designed to recover safely from interrupted execution.

Update jobs maintain persistent state in the Base de datos SQLite.

Individual package operations are tracked separately from the overall job state.

This allows the Agent to determine which package operations have already completed successfully before an interrupted job is resumed.

During recovery, successfully completed package operations are not executed again.

The recovery logic therefore follows the principle:

`Persistent Job State → Determine Completed Work → Skip Completed Items → Continue Remaining Work`

This reduces the risk of unnecessary repeated package operations after:

* agent interruption
* process termination
* system restart
* temporary communication failure
* container restart
* other execution interruptions

The audit verified interrupted-job recovery and checkpoint behavior.

Recovery was tested with jobs containing multiple package operations and with previously successful package items.

The audit confirmed that completed work is preserved and remaining work can continue without unnecessarily repeating successful operations.

**Status: APROBADO**

---

# Auditoría de Seguridad #10

## APT Robustness

Debian-based package operations are executed through the LUMS package-management layer.

APT-related update operations were reviewed for reliable detection of package-manager state and update results.

The implementation accounts for cases where package-management commands may return successfully while requiring additional interpretation of their output or resulting system state.

APT update detection was hardened to avoid relying on a single simplistic command-output condition.

The audit included testing of:

* normal APT operations
* available package updates
* package installation
* package removal
* update-job execution
* APT result handling
* update detection behavior

The corresponding hardening was committed as:

`c76f331 security: harden apt update detection`

The objective is to ensure that LUMS does not incorrectly report package-management state based solely on incomplete or ambiguous command output.

**Status: APROBADO**

---

# Auditoría de Seguridad #11

## Arch Linux Reboot Detection

Arch Linux package operations can result in a system state where a reboot is required or recommended.

LUMS therefore evaluates the resulting system state after relevant package-management operations.

The Agent distinguishes normal package-operation completion from situations where a reboot is required.

The reboot state is reported back to the LUMS server as part of the job result.

This allows the management interface to distinguish between:

* successful package operation
* successful operation with reboot requirement
* failed operation

The audit verified Arch Linux reboot detection using the actual package-management execution path.

The implementation was tested against reboot-required conditions and normal completion conditions.

**Status: APROBADO**

---

# Auditoría de Seguridad #12

## Unit Tests and API Result Validation

Security-sensitive behavior is covered by automated tests.

The test suite includes coverage for authentication, authorization, API validation, update jobs, package management, client authentication, and result handling.

The Agent-to-server result path was specifically reviewed to ensure that job results cannot arbitrarily alter unrelated server-side state.

Result processing validates the submitted information before applying state changes to the corresponding update job.

The validation covers relevant result fields and expected job relationships.

This prevents an authenticated client from freely selecting unrelated jobs or injecting arbitrary state into the update-job database.

The security test suite also covers negative and unauthorized cases.

Run the complete automated test suite from the repository root with
`./.venv-test/bin/pytest -q`. The number of tests changes over time; use the
result of the current run rather than a fixed count in this document.

The relevant security controls were additionally verified through focused test runs during the audit.

**Status: APROBADO**

---

# Audit Status After Part 4

The following security audit areas are complete:

| Audit | Area                                   | Status |
| ----- | -------------------------------------- | ------ |
| #01   | SQLite Foreign Keys                    | APROBADO   |
| #02   | SQLite Runtime Configuration           | APROBADO   |
| #03   | Update Timeout / Process Handling      | APROBADO   |
| #04   | Login Rate Limiting                    | APROBADO   |
| #05   | API Input Validation                   | APROBADO   |
| #06   | Session Revocation                     | APROBADO   |
| #07   | Client Token Rotation                  | APROBADO   |
| #08   | IP Address Handling / Offline Networks | APROBADO   |
| #09   | Job Recovery / Checkpointing           | APROBADO   |
| #10   | APT Robustness                         | APROBADO   |
| #11   | Arch Reboot Detection                  | APROBADO   |
| #12   | Unit Tests / API Result Validation     | APROBADO   |

The next section covers:

* #13 Simulation Tests
* #14 Continuous Integration
* #15 Application / Audit Logging
* #16 Versioning / Releases

# Auditoría de Seguridad #13

## Simulation Tests

LUMS provides a simulation mechanism for testing update-management workflows without performing the corresponding package-management operation on the managed system.

Simulation is implemented at the Agent execution layer.

When simulation is enabled, package-management operations are represented and processed without applying the requested package change to the operating system.

This allows update-job behavior to be tested without intentionally modifying the managed system.

The simulation tests cover relevant update-management paths, including:

* package installation
* package removal
* package updates
* system updates
* job execution
* result reporting
* successful completion
* failure handling

The simulation mechanism was used during the security audit to verify job creation, Agent execution, result handling, and server-side state transitions independently from real package modifications.

Simulation mode is a testing mechanism and does not replace the authorization controls of normal update operations.

**Status: APROBADO**

---

# Auditoría de Seguridad #14

## Continuous Integration

LUMS uses automated testing to detect security and functional regressions before changes are considered complete.

The CI process executes the automated test suite against the project.

The test environment verifies the application and security-sensitive functionality independently from the production container.

The CI process includes validation of:

* authentication
* authorization
* RBAC
* API behavior
* update-job handling
* package-management behavior
* client authentication
* job-result validation
* security-sensitive error handling

The CI audit was reviewed after the security hardening changes.

The final verified test suite completed successfully.

The test count changes as the project evolves. CI provides an automated
regression barrier for security-relevant application changes.

**Status: APROBADO**

---

# Auditoría de Seguridad #15

## Application and Audit Logging

LUMS records security-sensitive administrative and operational events through application-level registro de auditoría.

Audit logging is designed to provide an operational history without storing sensitive credentials.

Relevant security-sensitive actions include events such as:

* authentication-related security events
* administrative actions
* client management
* client-token operations
* update-job creation
* update-job execution
* security-relevant failures

Sensitive credential material is excluded from audit records.

In particular:

* passwords are not logged
* plaintext client tokens are not logged
* secret values are not intentionally written to audit records

Audit records are associated with the relevant administrative or operational context where applicable.

The registro de auditoría implementation was reviewed for:

* security-sensitive event coverage
* credential exclusion
* administrative traceability
* failure handling
* persistence of relevant audit information

The logging system is intended to support both operational troubleshooting and security investigation.

**Status: APROBADO**

---

# Auditoría de Seguridad #16

## Versioning and Releases

Versioning and release management were reviewed as part of the security audit.

LUMS is currently under active development and does not yet have an official stable release.

The current repository state therefore intentionally has:

* no official stable release version
* no release tag
* no GitHub Release

The current component versions include:

* LUMS Agent: `1.7.0`
* LUMS Watcher: `1.2.1`

There is currently no single formal version number representing the complete LUMS application.

This is an intentional project-state decision rather than an accidental omission.

The planned release process is:

1. Complete implementation work.
2. Complete the security review.
3. Review and synchronize the documentation.
4. Complete the full automated test suite.
5. Verify CI.
6. Define the release version.
7. Create the corresponding Git tag.
8. Publish the GitHub Release.
9. Preserve the release as the documented baseline.

No official release is created solely because the security audit reaches a particular audit number.

Release creation will take place only after the remaining implementation and documentation work has been completed.

**Status: REVISADO — ABIERTO POR DISEÑO**

---

# Audit Status After Part 5

The following security audit areas are complete:

| Audit | Area                                   | Status                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | SQLite Foreign Keys                    | APROBADO                      |
| #02   | SQLite Runtime Configuration           | APROBADO                      |
| #03   | Update Timeout / Process Handling      | APROBADO                      |
| #04   | Login Rate Limiting                    | APROBADO                      |
| #05   | API Input Validation                   | APROBADO                      |
| #06   | Session Revocation                     | APROBADO                      |
| #07   | Client Token Rotation                  | APROBADO                      |
| #08   | IP Address Handling / Offline Networks | APROBADO                      |
| #09   | Job Recovery / Checkpointing           | APROBADO                      |
| #10   | APT Robustness                         | APROBADO                      |
| #11   | Arch Reboot Detection                  | APROBADO                      |
| #12   | Unit Tests / API Result Validation     | APROBADO                      |
| #13   | Simulation Tests                       | APROBADO                      |
| #14   | Continuous Integration                 | APROBADO                      |
| #15   | Application / Audit Logging            | APROBADO                      |
| #16   | Versioning / Releases                  | REVISADO — ABIERTO POR DISEÑO |

The remaining numbered technical audit area is:

* #17 Control de Acceso Basado en Roles

The documentation review is tracked separately as:

* #18 Documentation Review — EN PROGRESO

# Auditoría de Seguridad #17

## Control de Acceso Basado en Roles

LUMS combines role templates with individually assigned permisos. The
supported templates are `administrador`, `operador`, and `visor`; choosing a
template selects its default permisos, which an administrador can customize
for each account.

The role remains account metadata. Protected routes authorize against the
account's server-stored permiso set, not the role label. The interface hides
unavailable functions for usability, while the server remains the security
boundary.

---

## RBAC Permission Model

| Permission        | Access granted |
| ----------------- | -------------- |
| `clients.view`    | View clients and system information |
| `software.view`   | View installed software |
| `updates.view`    | View available updates, jobs, and history |
| `packages.search` | Search package repositories |
| `jobs.manage`     | Create package operations and update jobs |
| `clients.manage`  | Register/remove clients and rotar tokens de cliente |
| `users.manage`    | Create users and manage roles and permisos |

The default role templates are:

| Template        | Default permisos |
| --------------- | ------------------- |
| `administrador` | All permisos |
| `operador`      | Client/software/update visibility, package search, and job management |
| `visor`        | Client visibility and installed-software visibility |

Client-related permisos require `clients.view`. `jobs.manage` also requires
`updates.view`. The UI loads permisos for the authenticated account and
omits controls the user cannot use; server-side checks independently enforce
the same grants.

---

## Authorization Enforcement

Protected operations use autenticación del lado del servidor and permiso checks.

The authorization model follows the principle:

`Authenticate → Load User Permissions → Authorize Operation → Execute`

Authentication alone is not sufficient to access privileged operations.

State-changing operations additionally require protección CSRF where applicable.

Examples of protected administrative operations include:

* update-job creation
* package installation
* package removal
* package updates
* system updates
* package-management operations
* client creation
* client disabling
* client-token rotation
* user creation
* user-management functions

Protected endpoints explicitly define the permiso required for the
corresponding operation.

A missing permiso is rejected by the server even if the user manually
constructs the corresponding HTTP request.

This prevents bypassing the RBAC model by directly calling an API endpoint that is hidden in the web interface.

---

## Viewer Restrictions

The Viewer template is intentionally restricted by its default permiso set.

For accounts without the corresponding grants, the client interface does not expose:

* Actualizaciones
* Trabajos de Actualización
* Historial de Actualizaciones
* Gestión de Paquetes
* Mantenimiento del Sistema

The server additionally prevents accounts without the corresponding grants
from performing protected operations.

The JavaScript interface does not load update-management data without
`updates.view`.

This reduces unnecessary exposure of operational information while maintaining server-side authorization as the actual security control.

Installed software remains available to Viewer accounts as a read-only information function.

---

## Administrative User Management

User management requires the `users.manage` permiso.

Users with that permiso can create accounts without permisos and then
assign individual grants or apply a role template in the permiso editor.
Role templates have descriptions explaining their default grants.

Authorized user managers can save an internal note per account. Notes are
limited to 2,000 characters, are not included in audit-log details, and are
not visible to the account owner.

User creation includes:

* username validation
* role validation
* password validation
* hash de contraseña Argon2
* duplicate-user detection
* registro de auditoría
* protección CSRF
* server-side authorization

User-management endpoints are not accessible without `users.manage`.

The server rejects unknown permisos and invalid dependency combinations.
At least one active account must retain `users.manage`; changes that would
remove the last user manager are rejected.

Las contraseñas nunca se almacenan en texto plano.

---

## RBAC Database Migration

Role-template information remains in the user database record. Individual
grants are stored in the `user_permisos` table with a foreign key to the
user account. Migration `003-user-permisos` creates that table and seeds
existing accounts from their current role template, preserving their access
during the transition. Migration `004-user-admin-notes` adds the private
`users.admin_note` field; existing accounts receive an empty note. Migration
`005-backup-permiso` grants `backups.manage` to existing Administrator
accounts.

Database backup creation requires `backups.manage`; the Administrator
template includes this permiso by default. The server writes SQLite online
backups only to the server-configured `LUMS_BACKUP_DIR`; it does not accept
filesystem paths from the browser. Backup files are created with owner-only
permisos and are integrity-checked before publication.

---

## RBAC Security Testing

RBAC behavior is covered by automated tests.

The tests include:

* Administrator authorization
* Operator authorization
* Viewer restrictions
* protected API access
* unauthorized operations
* client-management restrictions
* update-job restrictions
* user-management restrictions
* client-page visibility
* permiso-specific interface behavior

RBAC tests cover role-template defaults, custom permisos, permiso
dependencies, and server-side authorization. Production verification should
include accounts with customized permisos as well as the default
Administrator, Operator, and Viewer templates.

---

## RBAC Security Result

The RBAC implementation provides layered authorization:

1. Authentication establishes the user identity.
2. The server loads the user's permisos.
3. Protected routes enforce the required permiso.
4. protección CSRF applies to relevant browser state changes.
5. The web interface hides unavailable functionality.
6. Automated tests verify authorization boundaries.

The interface therefore does not provide the authorization mechanism by itself.

The server remains the authoritative security boundary.

**Status: APROBADO**

# Auditoría de Seguridad #18

## Documentation Review

The security documentation is reviewed against the currently implemented LUMS system.

The purpose of this review is to ensure that security documentation describes the actual implementation rather than an earlier development state.

The review covers:

* authentication
* authorization
* RBAC
* client authentication
* token handling
* session handling
* protección CSRF
* rate limiting
* SQLite configuration
* update execution
* job recovery
* package management
* container hardening
* network exposure
* secrets handling
* dependency and build security
* filesystem permisos
* application and registro de auditoría
* versioning and release handling
* pruebas de seguridad automatizadas

Documentation must distinguish between:

* implemented controls
* verified production behavior
* planned improvements
* intentionally open project decisions

Historical implementation details must not be presented as current production configuration.

In particular, the documentation reflects the current SQLite production configuration rather than the current WAL configuration.

The current production runtime is documented as:

* `journal_mode = wal`
* `busy_timeout = 5000`
* `synchronous = 2`
* application-level `PRAGMA foreign_keys = ON`

The current Viewer-RBAC behavior is also documented according to the implemented production interface.

Viewer users have access to:

* client information
* installed software

Viewer users do not have access to:

* Actualizaciones
* Trabajos de Actualización
* Historial de Actualizaciones
* Gestión de Paquetes
* Mantenimiento del Sistema

The documentation review also removes or replaces outdated references to earlier test counts, migration states, deployment configurations, and development-only behavior.

**Status: EN PROGRESO**

---

# Additional Security Hardening

The numbered security audit covers the primary application security controls.

Additional hardening was performed after the original audit sequence and is part of the current security baseline.

These controls are documented here because they represent important security properties of the current deployment.

---

## Container Hardening

The production LUMS container runs with a hardened Docker configuration.

The production container uses:

* non-root application user
* read-only root filesystem
* dropped Linux capabilities
* `no-new-privileges`
* restricted temporary filesystems
* read-only secret mount
* dedicated persistent application-data volume
* restart policy
* loopback-only host publication of the application port

The application root filesystem is therefore not writable during normal operation.

Writable locations are explicitly limited to the locations required by the application.

The production container was independently inspected to verify the effective runtime configuration.

The hardened runtime was also tested by verifying that:

* application filesystem writes fail
* `/tmp` remains available where required
* `/var/lib/lums` remains writable
* the secret file remains read-only
* the application remains operational

---

## Network Exposure

The LUMS application port is not directly exposed to the LAN.

The Docker application port is bound to the loopback interface:

`127.0.0.1:5050`

External access is provided through Nginx.

The production host exposes the intended network services through the firewall and reverse proxy.

The deployment was verified to prevent direct remote access to the internal Docker application port.

The firewall uses a default-deny model for incoming and routed traffic.

The intended externally reachable services are:

* SSH
* HTTP
* HTTPS

HTTP requests are redirected to HTTPS by the web server.

The default Nginx site was removed so that unrelated default content is not exposed.

---

## Transport Security

Administrative web access is provided through HTTPS.

HTTP is redirected to HTTPS.

The TLS endpoint is handled by Nginx rather than the Flask/Gunicorn application directly.

This keeps transport security and application serving separated.

The internal Gunicorn application port is therefore not intended to be a public HTTP endpoint.

The current deployment is intended for controlled internal infrastructure.

A future deployment with direct public-Internet exposure would require an additional security review.

---

## Secrets and Configuration

Production secrets are not stored in the application source tree.

The LUMS secret key is supplied through a protected secret file.

The production container receives the secret through:

`/run/secrets/lums_secret`

The secret file is mounted read-only.

The application reads the secret through the configured secret-file mechanism.

Repository and Docker build-context handling was reviewed to prevent accidental inclusion of:

* database files
* backup files
* secret files
* private keys
* certificates
* runtime logs
* local backup artifacts

The repository also ignores common temporary backup patterns used during development.

---

## Dependency and Build Security

The production Docker image uses a pinned Python base-image digest.

The production runtime dependencies are explicitly version-pinned.

The current production dependency set includes:

* Flask `3.1.3`
* argon2-cffi `25.1.0`
* Gunicorn `23.0.0`

The Docker build context is restricted through `.dockerignore`.

Repeated production builds were compared during the audit.

The relevant dependency and package metadata remained consistent between repeated builds, apart from expected generated Python bytecode differences.

This provides a reproducible baseline for the production image while keeping the build context limited.

---

## Filesystem and Runtime Permissions

The production application runs as the dedicated `lums` user rather than root.

Persistent application data is stored in the dedicated LUMS data volume.

The application root filesystem is read-only.

Runtime write access is restricted to explicitly required locations.

The production runtime was verified to reject unauthorized writes to the application filesystem.

This reduces the impact of accidental or malicious file modification inside the application container.

---

# Auditoría de Seguridad Conclusion

The current LUMS implementation has undergone a broad security review covering:

* authentication
* authorization
* RBAC
* session security
* protección CSRF
* limitación de velocidad de inicio de sesión
* client-token security
* API validation
* SQL injection resistance
* SQLite integrity
* update execution
* timeout handling
* job recovery
* package-management robustness
* result validation
* simulation
* continuous integration
* registro de auditoría
* container hardening
* network exposure
* transport security
* secrets handling
* filesystem permisos
* dependency and build security

The numbered audit results are:

| Audit | Area                                   | Status                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | SQLite Foreign Keys                    | APROBADO                      |
| #02   | SQLite Runtime Configuration           | APROBADO                      |
| #03   | Update Timeout / Process Handling      | APROBADO                      |
| #04   | Login Rate Limiting                    | APROBADO                      |
| #05   | API Input Validation                   | APROBADO                      |
| #06   | Session Revocation                     | APROBADO                      |
| #07   | Client Token Rotation                  | APROBADO                      |
| #08   | IP Address Handling / Offline Networks | APROBADO                      |
| #09   | Job Recovery / Checkpointing           | APROBADO                      |
| #10   | APT Robustness                         | APROBADO                      |
| #11   | Arch Reboot Detection                  | APROBADO                      |
| #12   | Unit Tests / API Result Validation     | APROBADO                      |
| #13   | Simulation Tests                       | APROBADO                      |
| #14   | Continuous Integration                 | APROBADO                      |
| #15   | Application / Audit Logging            | APROBADO                      |
| #16   | Versioning / Releases                  | REVISADO — ABIERTO POR DISEÑO |
| #17   | Control de Acceso Basado en Roles              | APROBADO                      |
| #18   | Documentation Review                   | EN PROGRESO               |

The technical security controls reviewed in audits #01–#15 and #17 have passed.

Audit #16 remains intentionally open because LUMS has not yet reached its first official stable release.

Audit #18 remains open until the complete project documentation has been reviewed and synchronized with the final implementation state.

No security audit result should be interpreted as a guarantee that LUMS is free from vulnerabilities.

Security is an ongoing process.

Changes to the application, Agent, dependencies, container configuration, network exposure, authentication model, or deployment architecture should trigger another security review of the affected controls.

---

# Línea Base de Seguridad

La línea base de seguridad actual se basa en el estado de implementación y despliegue de producción verificado.

La línea base incluye:

* autenticación del lado del servidor
* RBAC del lado del servidor
* hash de contraseña Argon2
* resúmenes de token de cliente SHA-256
* protección CSRF
* limitación de velocidad de inicio de sesión
* SQL parametrizado
* entrada de API validada
* ejecución controlada del gestor de paquetes
* recuperación de trabajos de actualización
* registro de auditoría
* tiempo de ejecución de Docker reforzado
* HTTPS a través de Nginx
* exposición de puerto de aplicación de solo bucle de retorno
* restricciones de cortafuegos
* secretos de producción protegidos
* dependencias de producción fijadas
* restricted filesystem permisos
* pruebas de seguridad automatizadas

Future changes should preserve these properties unless a deliberate architectural change replaces them with an equivalent or stronger control.

---

# Mantenimiento de Seguridad

Los controles de seguridad deben revalidarse cuando se introducen cambios significativos.

Los ejemplos incluyen:

* cambios de autenticación
* nuevas funciones de usuario
* nuevos puntos finales de API
* cambios de gestión de paquetes
* cambios de ejecución del agente
* migraciones de base de datos
* actualizaciones de dependencia
* cambios de Dockerfile
* cambios de tiempo de ejecución del contenedor
* cambios de proxy inverso
* cambios de cortafuegos
* cambios de gestión de secretos
* preparación del lanzamiento

Las pruebas de seguridad deben realizarse antes de publicar una versión oficial.

La documentación de seguridad debe actualizarse cada vez que cambie la línea base de seguridad verificada.

---

# Preparación del Lanzamiento

La primera versión oficial de LUMS se creará solo después de:

1. el trabajo de implementación está completo
2. la revisión de seguridad está completa
3. la revisión de documentación está completa
4. la suite de pruebas automatizadas completa pasa
5. CI pasa
6. se define la versión final
7. se crea la etiqueta Git
8. se publica la versión de GitHub

Hasta entonces, LUMS sigue siendo un proyecto en desarrollo activo.

---

# Declaración Final

LUMS está diseñado como una plataforma controlada de gestión de actualizaciones de Linux con seguridad como una preocupación arquitectónica central.

El modelo de seguridad no se basa en un único mecanismo protector.

En su lugar, la autenticación, la autorización, la validación, la ejecución controlada, la persistencia, la recuperación, el registro, el aislamiento de contenedores, las restricciones de red y las pruebas automatizadas funcionan juntas como controles en capas.

El proyecto deliberadamente favorece la aplicación explícita del lado del servidor sobre la seguridad por interfaz.

La línea base de seguridad actual se documenta de acuerdo con el estado de implementación verificado en lugar del comportamiento de desarrollo histórico.

---

**LUMS — Linux Update Management without the noise.**

`segfault // override`

