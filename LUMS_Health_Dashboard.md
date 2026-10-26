# LUMS Health Dashboard

## Purpose and scope

The authenticated dashboard at `/health` gives an operator a quick view of
selected LUMS state:

- database status as determined by the application;
- total, online, unknown, and offline client counts;
- recent CPU and memory telemetry for an enabled client, when telemetry is
  installed and samples exist;
- whether the configured backup directory can be inspected and the latest
  backup file that the application recognizes.

This page is an operational overview, not a full monitoring or alerting system.
It does not prove that the host, Docker daemon, reverse proxy, network, or every
managed client is healthy. A listed backup is not proof that the backup is
restorable; periodically perform a controlled restore test.

## Access control

The `/health` page requires a signed-in user with the `clients.view` permission.
Access is subject to the application's normal authentication and authorization
checks. Do not make the dashboard public by bypassing the login or reverse
proxy controls.

The separate `GET /api/health` endpoint is a lightweight liveness response.
A successful response means that the route can answer; it is not a complete
database, backup, or client-health assessment.

## Client status interpretation

The dashboard classifies clients using their last reported timestamp:

| Status | Timestamp age |
| --- | --- |
| Online | 120 seconds or less |
| Unknown | More than 120 seconds and up to 600 seconds, missing/invalid timestamp, or a timestamp in the future |
| Offline | More than 600 seconds |

These thresholds describe reporting recency, not whether a machine is powered
on or whether every service on it is working. Network delays, suspended
machines, a stopped agent, or reporting failures can all affect the result.
Treat `unknown` as insufficient information rather than as proof of failure.

## CPU and memory telemetry

Telemetry is optional and is separate from the reporting Agent and execution
Watcher. The telemetry service submits a sample approximately every five
seconds when its systemd timer is enabled and the client can reach the server.

The dashboard provides 1-hour, 24-hour, and 7-day history ranges and refreshes
the displayed data every five seconds. History queries are limited to 1–168
hours and may be downsampled to at most 1,000 points. Samples older than seven
days are removed during processing of new telemetry submissions; if all
submissions stop, do not assume that retention cleanup runs independently.

Telemetry requires client authentication. Remote agent connections require
HTTPS; plain HTTP is accepted only for loopback addresses. Configure a CA file
when the server uses a private certificate authority. For setup details, see
[telemetry.md](telemetry.md) and [install.md](install.md).

## Backup-storage status

The backup section reflects what the application can inspect in its configured
backup directory and the latest backup file it recognizes. It does not
independently verify the contents of every backup, confirm off-host replication,
or prove that a database restore will succeed.

A sensible operational routine is to:

1. confirm the displayed backup date is recent enough for your recovery target;
2. inspect the backup job and application logs for errors;
3. verify that the backup is copied to an appropriate protected destination;
4. periodically test restoration in a separate, controlled location.

Do not delete or overwrite the live database or backup files as a troubleshooting
shortcut.

## Recommended checks when a status looks wrong

1. Check the LUMS container and recent logs.
2. Check the reverse proxy and TLS configuration if the page or API is
   unreachable.
3. For a client marked unknown/offline, inspect its reporting Agent and
   Watcher timers and recent journal entries.
4. For missing telemetry, inspect `lums-telemetry.timer`,
   `lums-telemetry.service`, and the client/server configuration.
5. For backup warnings, verify the configured backup path, filesystem
   permissions, available space, and recent backup logs.
6. Record the observed status and timestamps before making changes.

See [troubleshooting.md](troubleshooting.md) for diagnostic commands and
[administration.md](administration.md) for routine maintenance and backup
procedures.

