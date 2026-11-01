# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Linux system administrators and IT teams responsible for centrally managing and keeping multiple Linux systems up to date. The product should also suit a single administrator, small IT team, and appropriate managed-service environments.

## Product Purpose

LUMS provides a central view of managed clients, installed software, available updates, and update-job execution. It helps administrators deliberately initiate work and verify its outcome rather than blindly applying updates across every system.

## Operating Context

Administrators use LUMS in day-to-day operations to inspect fleet health, telemetry, software, and updates; initiate targeted update jobs; review execution history; and maintain user access, audit records, and database backups. The infrastructure topology can combine registered LUMS clients with manually maintained systems and relationships.

## Capabilities and Constraints

- Role- and permission-based access controls, audit logging, database backup, package visibility, and client update jobs are core operational capabilities.
- System update operations must be controlled, auditable, and fail honestly; do not imply that an update succeeded unless its checks pass.
- Registered clients and their reported data are the available source of automatically imported infrastructure inventory. Additional infrastructure and relationships require explicit manual entry unless a future integration is confirmed.
- Editing infrastructure inventory is restricted to administrators.
- Do not imply automatic discovery of arbitrary VMs, containers, network devices, or dependencies.

## Brand Commitments

- Preserve the LUMS name and existing logo.
- The user explicitly calls the stadium theme “LUMS-Stadion” and requested its existing stadium background image on the system-status dashboard and live monitoring.

## Evidence on Hand

- Existing product interface and theme assets: `server/static/style.css`, `server/static/images/LUMS_Logo.jpg`, and `server/static/images/lumsstadium.jpg`.
- Existing registered-client, telemetry, update-job, RBAC, audit, and backup implementations are in the `server/` package.
- No verified customer claims, product benchmarks, or automatic infrastructure-discovery integration have been provided.

## Product Principles

- Keep administrators in control of system changes.
- Make operational status and update outcomes verifiable.
- Enforce access rules on the server, not only in the interface.
- Distinguish reported client facts from manually maintained inventory.
