# LUMS CPU, memory and network telemetry

## Overview

The optional LUMS telemetry agent collects CPU utilisation, memory utilisation,
network counters and a bounded host snapshot from a managed Linux system, then
sends measurements to the LUMS server.

The server stores telemetry samples and exposes an authenticated history API
used by the client telemetry dashboard.

Telemetry is separate from the existing LUMS reporting Agent and Watcher. It
does not replace either component or perform package updates.

## Components

| Component | Responsibility |
| --- | --- |
| `agent/telemetry.py` | Collects CPU, memory, host, network, sensor, service and container metrics |
| `agent/lums-telemetry.service` | Runs the telemetry agent as a restricted systemd service |
| `agent/lums-telemetry.timer` | Schedules recurring telemetry collection |
| `server/app.py` | Authenticates submissions, validates metrics and stores samples |
| `server/static/telemetry.js` | Displays the fleet overview, history charts and donut gauges |

## Measurements

Each sample contains these required fields:

- `cpu_percent`: CPU utilisation from 0 to 100.
- `memory_percent`: memory utilisation from 0 to 100.
- `memory_total_bytes`: total detected memory in bytes.
- `memory_available_bytes`: available memory in bytes.

Agent version 1.1.0 and later also sends two optional cumulative counters:

- `network_rx_bytes`: bytes received since boot, summed over all non-loopback
  interfaces.
- `network_tx_bytes`: bytes sent since boot, summed over all non-loopback
  interfaces.

Both counters must be sent together as non-negative integers. Older agents
that omit them keep working; the dashboard then shows no network data for
that client. The server stores the raw counters and calculates bytes per
second from consecutive samples when the data is requested. No rate is shown
for the first sample, after a counter reset (for example, a reboot), or when
the gap between two samples exceeds five minutes.

Agent version 1.2.0 and later also reports a bounded system snapshot:

- load average, uptime, operating system, kernel and root filesystem usage;
- link state, byte counters, errors and drops for each network interface;
- configured DNS servers and best-effort gateway, DNS and internet reachability;
- thermal and fan readings when exposed by the kernel;
- selected systemd service states, run times and restart counts, plus Docker
  and Podman container names and normalised states when local tools and
  permissions allow read-only inspection;
- disk utilisation percentage on each telemetry sample for historical charts
  and threshold-event evaluation.

Agent version 1.3.0 and later also reports bounded operational-event
summaries: failed SSH login counts and timestamps, recent journal warning and
error counts, login/logout timestamps, and the first and last journal
timestamps for recent boots. Raw journal messages, usernames and source
addresses are not sent. Each journal query is limited to 500 matching records;
the dashboard marks a count of 500 as `500+`. Boot history is capped at 10
boots and login/logout history at 20 events.

The server derives per-interface throughput from consecutive samples.
Service, container, temperature, fan and event details are stored as the most
recent snapshot only, not duplicated into every historical sample. Optional
metrics that are not exposed or permitted by the operating system are shown
as unavailable. The agent does not start, stop or modify services or
containers. Access to the Docker socket is not granted to the agent service;
container details remain unavailable unless the runtime already permits the
service account to inspect them.

The telemetry systemd unit belongs to `systemd-journal` for read-only journal
access. This grants access to system logs, but the agent only sends the
bounded summaries described above. The default service allowlist includes
LUMS, Docker and SSH units. Override it with a comma-separated
`LUMS_MONITORED_SERVICES` value in the agent environment file; only valid
`.service` unit names are accepted.

Gateway reachability uses a one-packet ping when available, DNS reachability
uses a short `getent` lookup, and internet reachability is a short TCP
connection attempt to `1.1.1.1:443`. These checks are indicators only and may
reflect firewall policy rather than an outage.

The server assigns the sample timestamp and rejects invalid payloads.

After updating the server, run the database migration once
(`python3 server/security_migration.py`) so the network columns, latest
system-state table, dashboard settings and event history exist. Update the
agent on each client to start reporting the new metrics. To monitor the LUMS
server itself, register it as a client and install and configure the telemetry
agent on that host as well.

## Security and privacy

The telemetry endpoint requires client authentication using the configured
LUMS client token.

The agent sends requests over HTTPS when connecting to a remote server.
Plain HTTP is permitted only for `localhost`, `127.0.0.1` and `::1`. Remote
server connections require HTTPS. An optional CA file can be configured for
certificate verification.

The agent does not include the client token in the JSON payload or log it.
The systemd service uses a restricted execution environment and does not
require root privileges to collect the documented metrics.

Telemetry contains system resource and operational metadata, not package
updates or arbitrary command output. Interface addresses, DNS servers,
service names and container names can be sensitive infrastructure details;
access to the dashboard and API remains protected by the `clients.view`
permission.

## Data retention

The server removes telemetry samples older than seven days when processing
new telemetry submissions.

The authenticated history endpoint accepts a time range from 1 to 168 hours.
Access requires the appropriate client-view permission. Large result sets
may be downsampled to a maximum of 1,000 samples.

The `/health` dashboard offers 1-hour, 24-hour and 7-day history ranges and
refreshes its displayed data every five seconds. It shows CPU, memory, disk
utilisation and aggregate network history, plus live disk, load, uptime,
kernel, operating system, interface, connectivity, sensor, service and
container details for the selected client. It also shows a fleet overview
(filterable by status, stale telemetry or high load, searchable and sortable)
and per-client details. CPU and memory can be shown as a line chart, an area
chart or a donut gauge of the current value; the chosen view is remembered in
the browser. Network traffic is shown as download and upload rates. Telemetry
older than two minutes is marked as stale. The fleet overview uses the
`/api/telemetry/overview` endpoint, which requires the client-view permission.
History requests are limited to 1–168 hours and may be downsampled to a
maximum of 1,000 samples. The systemd timer is configured to run the one-shot
agent every five seconds; actual sample frequency depends on service
completion and network availability. The dashboard also displays recent SSH
failures, journal warning/error counts, login/logout history and boot
history. Threshold warnings use the logged-in user's configurable CPU, RAM
and disk limits. Journal counts cover at most 500 matching records per query.
The last successful backup creation is read from the server's audit log; it
is not a restore test.

The health dashboard has a fixed layout. Each user can set independent CPU,
RAM and disk thresholds from 50% to 99%; the default is 90%. Threshold
crossings and telemetry gaps over two minutes appear in the event history.
Threshold alerts are derived from retained samples and use the logged-in
user's thresholds; service state transitions and new SSH failure timestamps
are recorded during ingestion. Events are retained for up to seven days and
the event endpoint returns at most 500 entries.

CSV and JSON exports are available for the selected client and time range.
History downloads include all retained samples for that range; charts remain
downsampled to at most 1,000 points. Exports require `clients.view` and are
not cached by the browser.

Wazuh and Suricata can be enabled as optional per-user status rows. These rows
display configured systemd service state only; LUMS does not connect to their
APIs or collect their alerts. To report a service, include its installed unit
(for example `wazuh-agent.service`, `wazuh-manager.service` or
`suricata.service`) in the agent's `LUMS_MONITORED_SERVICES` allowlist. No
integration credentials are required or stored by LUMS.

## Configuration

The telemetry agent uses `LUMS_BASE`, `LUMS_TOKEN` and the optional
`LUMS_CA_FILE` environment variables. Remote server connections require
HTTPS. See [Installation and upgrades](<Installation and upgrades.md>) for
installation and configuration instructions.

## Installation and operation

The telemetry service is separate from the normal LUMS client. On Debian,
first update the LUMS repository checkout on the client and run
`sudo bash scripts/install-telemetry-agent.sh` from its root. The installer
checks that `/etc/default/lums-agent` defines `LUMS_BASE` and `LUMS_TOKEN`,
installs the current collector and systemd units, enables the timer, and
sends a test sample. It never prints the token.

Inspect the timer and service with `systemctl status lums-telemetry.timer` and
`systemctl status lums-telemetry.service`. Review recent service logs with
`journalctl -u lums-telemetry.service -n 30 --no-pager`. An inactive one-shot
service between scheduled runs is not necessarily an error; check the timer
and recent logs as well.

The `/monitoring` page distinguishes between no samples, basic telemetry
without detailed snapshots, and an outdated snapshot, and shows these
client-side checks. Do not paste or share the token when troubleshooting.

## Troubleshooting

- **No samples appear:** Verify the server URL, client token and authentication.
- **TLS errors:** Check the server certificate and configured CA file.
- **Service failures:** Inspect the service journal.
- **Missing history:** Check client-view permissions and the requested time
  range (1–168 hours).

For the dashboard's status thresholds and the limits of its backup-storage
indicator, see [LUMS Health Dashboard](<LUMS Health Dashboard.md>). For
general guidance, see [Installation and upgrades](<Installation and upgrades.md>)
and [Troubleshooting](Troubleshooting.md). The English source is
[telemetry.md](../../../telemetry.md).
