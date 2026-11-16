# LUMS Infrastructure Topology

<!-- LUMS-POSTGRES-STATUS-2026-11-15 -->
## Deployment topology: PostgreSQL successor status

**Status date: 15 November 2026**

The infrastructure page described above is an application-level inventory and dependency view. It must not be confused with the actual container deployment topology.

The PostgreSQL successor currently runs in an isolated candidate Compose project. Its services include the database, provisioning, migrations, application and worker grant services, the web application and the SOC worker.

The candidate does not currently include a deployed Envoy gateway or a separate collector application service. The planned collector-facing mTLS gateway and its dedicated network boundaries are architectural targets, not active deployment components.

The existing productive SQLite deployment remains separate. The candidate's internal container network and service names must not be interpreted as production network topology.

Update this documentation when the actual Compose configuration and deployed services change. Distinguish planned components from running components and do not infer network reachability from an architectural diagram.

<!-- /LUMS-POSTGRES-STATUS-2026-11-15 -->


## Purpose

The authenticated `/infrastructure` page brings registered LUMS clients and
manually maintained infrastructure into one dependency view. It is an
inventory and relationship map, not an automatic network-discovery or
configuration-management system.

## Data sources and ownership

- Registered LUMS clients are read from the existing client registry and appear
  automatically, including their reported hostname, IP address, operating
  system and enabled/reporting status. Disabled clients remain visible so
  existing relationships stay understandable. These entries are read-only in
  the topology page; manage a client through the normal client-management
  workflow.
- Servers, virtual machines, containers, network devices, services and
  storage can be entered manually with a hostname, IP address, role, location
  and notes.
- Relationships are maintained manually. Supported types are `depends on`,
  `hosts`, `connects to` and `runs on`.
- The page does not scan subnets, query cloud APIs or infer dependencies from
  services or container configuration. Keep manually entered inventory and
  relationships current.

## Access control and audit

Users with `clients.view` can view the topology. Creating, editing and
deleting manual entries or relationships is restricted to administrators
with the `infrastructure.manage` permission. The application requires its
normal authenticated session, CSRF protection and audit logging for changes.

`infrastructure.manage` depends on `users.manage` and `clients.view`, and is
granted to administrators by the `016-infrastructure-topology` database
migration. Removing a manually managed node also removes its relationship
records. Removing a client removes relationships that reference that client.

## Reading the map

The map arranges nodes by category and draws each recorded relationship with a
directional edge. A **shared dependency** is a node that at least two other
nodes point to using `depends on`. This is a useful review signal for a
potential central failure point, not a complete availability or impact
analysis. The map does not account for redundancy, failover, capacity,
network segmentation or unrecorded dependencies.

Use the inventory and relationship tables for the exact hostname, IP address,
role, location and relationship details. The topology uses the currently
selected LUMS theme and works with the shared collapsible sidebar.
