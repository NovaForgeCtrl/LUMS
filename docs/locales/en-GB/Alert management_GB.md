# LUMS Alert Management: Current Implementation

This note describes the alert-management code currently present in LUMS. It
is a code reference, not a feature roadmap or a promise that every visible
control is operational. The implementation is centered on
`server/alerts.py` and `server/alerts_routes.py`.

## What is implemented

LUMS persists alert rules, alert records and alert state history in SQLite.
The Flask blueprint creates a request-scoped `AlertManager` using the
application's database connection factory. The manager loads rules and
unresolved alerts from the database for each request.

The current API supports:

- listing, creating, updating and deleting alert rules;
- manually triggering an alert for an existing enabled rule;
- viewing active alerts and paginated alert history;
- acknowledging, resolving and manually escalating an active alert.

The alert severity values are `critical`, `warning` and `info`. The stored
alert states are `triggered`, `acknowledged`, `resolved` and `escalated`.
Acknowledgement, resolution and escalation changes are written to
`alert_history`. Resolved alerts are removed from the manager's active-alert
collection but remain in the database.

## Important limits

The rule model stores a condition, threshold, severity, escalation path,
grouping flag and deduplication flag. The current server does **not** evaluate
conditions against telemetry or other measurements. A rule does not trigger
automatically: an authenticated caller must invoke `POST /alerts/trigger`.
Grouping and deduplication values are stored but are not applied. When an alert
is triggered, the manager attempts to send it through providers named in the
rule's escalation path. The web application creates each manager with an empty
provider map, and its integration endpoints cannot configure providers, so
application-triggered alerts currently have no notification delivery.

The `AlertManager` defines email, Slack, PagerDuty and generic webhook provider
classes, but these classes are not configured through the application. The
integration API deliberately reports integrations as unavailable and returns
`501 Not Implemented` for configuration, test and deletion requests. No
notification delivery should be expected. `POST /alerts/clear-all` also
returns `501` so that alert history cannot be removed through that endpoint.

The `/alerts/` page is a basic server-rendered overview. Its rule, history and
integration tab controls and alert-action buttons are not a complete
interactive management interface. Use the documented API behaviour as the
source of truth rather than assuming that a visible button performs an action.
The current implementation does not provide real-time push or WebSocket
updates.

## Routes and access control

All routes require an authenticated web session.

| Method | Route | Permission | Current behaviour |
| --- | --- | --- | --- |
| `GET` | `/alerts/` | `alerts.view` | Renders the basic alert overview |
| `GET` | `/alerts/rules` | `alerts.view` | Lists stored rules |
| `POST` | `/alerts/rules` | `alerts.manage` | Creates a validated rule |
| `PUT` | `/alerts/rules/<rule_id>` | `alerts.manage` | Updates a stored rule |
| `DELETE` | `/alerts/rules/<rule_id>` | `alerts.manage` | Deletes a rule when database constraints allow |
| `GET` | `/alerts/current` | `alerts.view` | Returns active alerts |
| `GET` | `/alerts/history` | `alerts.view` | Returns alert history |
| `POST` | `/alerts/trigger` | `alerts.manage` | Manually creates an alert for an enabled rule |
| `POST` | `/alerts/<alert_id>/acknowledge` | `alerts.manage` | Records an acknowledgement |
| `POST` | `/alerts/<alert_id>/resolve` | `alerts.manage` | Resolves an active alert |
| `POST` | `/alerts/<alert_id>/escalate` | `alerts.manage` | Manually increments its escalation count |
| `POST` | `/alerts/clear-all` | `alerts.manage` | Disabled; returns `501` |
| `GET` | `/alerts/integrations` | `alerts.view` | Returns an empty list and `available: false` |
| `POST` / `DELETE` | `/alerts/integrations/...` | `alerts.manage` | Disabled; returns `501` |

Mutating routes require CSRF protection as well as the relevant permission.
Permission checks are enforced on the server. `alerts.manage` depends on
`alerts.view`; role grants are maintained by the security migration and
permission configuration.

## Persistent tables

`AlertManager` initializes these tables when it is created:

- `alert_rules`: rule definitions and their configured values;
- `alerts`: alert records and current lifecycle state;
- `alert_history`: acknowledgement, resolution and escalation history;
- `notification_integrations`: reserved integration configuration schema;
- `alert_notifications_log`: reserved delivery-log schema.

The final two tables do not mean integrations are available. The HTTP
integration endpoints remain disabled until secure persistent configuration
and delivery behaviour are implemented.

## Verification

Alert routes, permission enforcement, payload validation, persistence and
lifecycle behaviour are covered by `tests/test_alerts.py`. Re-run the relevant
tests against the revision being deployed. A passing test suite does not turn
disabled integration routes or unevaluated rules into available features.

## Related code

- `server/alerts.py`
- `server/alerts_routes.py`
- `server/security.py`
- `server/security_migration.py`
- `tests/test_alerts.py`
