# LUMS CPU, Memory and Network Telemetry

## Overview

The optional LUMS telemetry agent collects CPU utilization, memory utilization and network
byte counters from a managed Linux client and sends measurements to the LUMS server.

The server stores telemetry samples and exposes an authenticated history API
used by the client telemetry dashboard.

Telemetry is separate from the existing LUMS reporting Agent and Watcher.
It does not replace either component or perform package updates.

## Components

| Component | Responsibility |
| --- | --- |
| `agent/telemetry.py` | Collects CPU, memory and network metrics and sends samples |
| `agent/lums-telemetry.service` | Runs the telemetry agent as a restricted systemd service |
| `agent/lums-telemetry.timer` | Schedules recurring telemetry collection |
| `server/app.py` | Authenticates submissions, validates metrics and stores samples |
| `server/static/telemetry.js` | Displays the fleet overview, history charts and donut gauges |

## Measurements

Each sample contains these required fields:

- `cpu_percent`: CPU utilization from 0 to 100, calculated from `/proc/stat`.
- `memory_percent`: memory utilization from 0 to 100, calculated as (total - available) / total.
- `memory_total_bytes`: total detected memory in bytes from `/proc/meminfo`.
- `memory_available_bytes`: available memory in bytes from `/proc/meminfo`.

Agent version 1.1.0 and later also sends two optional cumulative counters:

- `network_rx_bytes`: bytes received since boot, summed over all non-loopback
  interfaces from `/proc/net/dev`.
- `network_tx_bytes`: bytes sent since boot, summed over all non-loopback
  interfaces from `/proc/net/dev`.

Both counters must be sent together as non-negative integers. Older agents
that omit them keep working; the dashboard then shows no network data for
that client. The server stores the raw counters and calculates bytes per
second from consecutive samples when the data is requested. No rate is shown
for the first sample, after a counter reset (for example a reboot), or when
the gap between two samples exceeds five minutes.

The server assigns the sample timestamp and rejects invalid payloads.

Telemetry samples are stored in the `telemetry_samples` table in SQLite:

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

After updating the server, run the database migration once:

```bash
python3 server/security_migration.py
```

This ensures the network columns (`network_rx_bytes`, `network_tx_bytes`) exist.
Update the agent on each client to start reporting traffic.

## Security and privacy

The telemetry endpoint requires client authentication using the configured
LUMS client token.

The agent sends requests over HTTPS when connecting to a remote server.
Plain HTTP is permitted only for `localhost`, `127.0.0.1` and `::1`. Remote server connections require HTTPS. An optional CA file
can be configured for certificate verification.

The agent does not include the client token in the JSON payload or log it.
The systemd service uses a restricted execution environment and does not
require root privileges to collect the documented metrics.

Telemetry contains resource utilization measurements, not package updates
or arbitrary command output.

## Data retention

The server removes telemetry samples older than seven days when processing
new telemetry submissions.

The authenticated history endpoint accepts a time range from 1 to 168 hours.
Access requires the appropriate client-view permission. Large result sets
may be downsampled to a maximum of 1,000 samples.

The `/health` dashboard offers 1-hour, 24-hour, and 7-day history ranges and
refreshes its displayed data every five seconds. It shows a fleet overview
(filterable by status, stale telemetry or high load, searchable and sortable)
and per-client details. CPU and memory can be shown as a line chart, an area
chart or a donut gauge of the current value; the chosen view is remembered in
the browser. Network traffic is shown as download and upload rates. Telemetry
older than two minutes is marked as stale. The fleet overview uses the
`/api/telemetry/overview` endpoint, which requires the client-view permission. History requests are limited
to 1–168 hours and may be downsampled to a maximum of 1,000 samples. The
systemd timer is configured to run the one-shot agent every five seconds; actual
sample frequency depends on service completion and network availability.

## Configuration

The telemetry agent uses `LUMS_BASE`, `LUMS_TOKEN` and the optional `LUMS_CA_FILE` environment variables. Remote server connections require HTTPS. See [install.md](install.md) for installation and configuration instructions.

## Installation and operation

Inspect the timer and service on a managed Linux client with `systemctl status lums-telemetry.timer` and `systemctl status lums-telemetry.service`. Review recent service logs with `journalctl -u lums-telemetry.service`. An inactive one-shot service between scheduled runs is not necessarily an error; check the timer and recent logs as well.

## Troubleshooting

- **No samples appear:** Verify the server URL, client token and authentication.
- **TLS errors:** Check the server certificate and configured CA file.
- **Service failures:** Inspect the service journal.
- **Missing history:** Check client-view permissions and the requested time range (1–168 hours).

## API Reference

### Submit Telemetry Sample

**Endpoint:** `POST /api/telemetry`

**Authentication:** LUMS client token (in `Authorization: Bearer <token>` header)

**Request body:**

```json
{
  "cpu_percent": 45.5,
  "memory_percent": 62.0,
  "memory_total_bytes": 8589934592,
  "memory_available_bytes": 3221225472,
  "network_rx_bytes": 1048576000,
  "network_tx_bytes": 524288000
}
```

**Response:** 204 No Content on success

### Retrieve Telemetry History

**Endpoint:** `GET /api/telemetry/history/<client_id>?hours=24`

**Authentication:** Requires `clients.view` permission

**Query parameters:**
- `hours`: Time range (1–168 hours)

**Response:** Array of telemetry samples with calculated rates

### Fleet Overview

**Endpoint:** `GET /api/telemetry/overview`

**Authentication:** Requires `clients.view` permission

**Response:** Client status summary with latest telemetry

## Agent Implementation

The telemetry agent (`agent/telemetry.py`) is a standalone script that:

1. Reads CPU counters from `/proc/stat`
2. Reads memory information from `/proc/meminfo`
3. Reads network counters from `/proc/net/dev`
4. Submits measurements via HTTPS POST to `/api/telemetry`
5. Runs via systemd timer approximately every 5 seconds

Agent version `1.1.0` adds network byte counting. The agent uses only the Python standard library and requires no root privileges.

Environment variables:

- `LUMS_BASE`: Server URL (e.g., `https://lums.example.com`)
- `LUMS_TOKEN`: Client authentication token
- `LUMS_CA_FILE` (optional): Path to CA certificate for custom certificate authorities

The agent logs to stdout; systemd captures logs in the journal:

```bash
journalctl -u lums-telemetry.service -f
```

### CPU Calculation

The agent samples CPU counters twice with a 0.2-second interval to calculate utilization:

```python
def calculate_cpu_percent(before, after):
    total_delta = after[0] - before[0]
    idle_delta = after[1] - before[1]
    busy = 100.0 * (total_delta - idle_delta) / total_delta
    return round(min(100.0, max(0.0, busy)), 2)
```

### Memory Calculation

Memory utilization is calculated from `/proc/meminfo`:

```
memory_percent = (MemTotal - MemAvailable) / MemTotal * 100
```

---

For the dashboard's status thresholds and the limits of its backup-storage
indicator, see [LUMS_Health_Dashboard.md](LUMS_Health_Dashboard.md). For general guidance,
see [install.md](install.md) and [troubleshooting.md](troubleshooting.md).
