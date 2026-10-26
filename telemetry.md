# LUMS CPU and Memory Telemetry

## Overview

The optional LUMS telemetry agent collects CPU and memory utilization from a
managed Linux client and sends measurements to the LUMS server.

The server stores telemetry samples and exposes an authenticated history API
used by the client telemetry dashboard.

Telemetry is separate from the existing LUMS reporting Agent and Watcher.
It does not replace either component or perform package updates.

## Components

| Component | Responsibility |
| --- | --- |
| `agent/telemetry.py` | Collects CPU and memory metrics and sends samples |
| `agent/lums-telemetry.service` | Runs the telemetry agent as a restricted systemd service |
| `agent/lums-telemetry.timer` | Schedules recurring telemetry collection |
| `server/app.py` | Authenticates submissions, validates metrics and stores samples |
| `server/static/telemetry.js` | Displays CPU and memory history |

## Measurements

Each sample contains exactly four fields:

- `cpu_percent`: CPU utilization from 0 to 100.
- `memory_percent`: memory utilization from 0 to 100.
- `memory_total_bytes`: total detected memory in bytes.
- `memory_available_bytes`: available memory in bytes.

The server assigns the sample timestamp and rejects invalid payloads.

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
refreshes its displayed data every five seconds. History requests are limited
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

For the dashboard's status thresholds and the limits of its backup-storage
indicator, see [health-dashboard.md](health-dashboard.md). For general guidance,
see [install.md](install.md) and [troubleshooting.md](troubleshooting.md).

