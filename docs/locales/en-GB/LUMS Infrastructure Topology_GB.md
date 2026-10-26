# LUMS Infrastructure Topology

## Purpose

The authenticated `/infrastructure` page brings registered LUMS clients and
manually maintained infrastructure into one dependency view. It is an
inventory and relationship map, not an automatic network-discovery or
configuration-management system.

## Data sources and ownership

- Registered LUMS clients are read from the existing client registry and
  appear automatically, including their reported hostname, IP address,
  operating system and enabled/reporting status. Disabled clients remain
  visible so existing relationships stay understandable. These entries are
  read-only in the topology page; manage a client through the normal
  client-management workflow.
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

The map arranges nodes by category and draws each recorded relationship with
a directional edge. A **shared dependency** is a node that at least two
other nodes point to using `depends on`. This is a useful review signal for
a potential central failure point, not a complete availability or impact
analysis. The map does not account for redundancy, failover, capacity,
network segmentation or unrecorded dependencies.

Use the inventory and relationship tables for the exact hostname, IP
address, role, location and relationship details. The topology uses the
currently selected LUMS theme and works with the shared collapsible sidebar.
The English source is
[LUMS_Infrastructure_Topology.md](../../../LUMS_Infrastructure_Topology.md).
