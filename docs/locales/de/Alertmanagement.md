# LUMS-Alertmanagement: aktuelle Implementierung

Diese Notiz beschreibt den derzeit in LUMS vorhandenen Code für das Alertmanagement. Sie ist eine Code-Referenz und weder eine Funktions-Roadmap noch ein Versprechen, dass jedes sichtbare Bedienelement funktionsfähig ist. Die Implementierung konzentriert sich auf `server/alerts.py` und `server/alerts_routes.py`.

## Implementierte Funktionen

LUMS speichert Alert-Regeln, Alert-Datensätze und den Verlauf der Alert-Zustände in SQLite. Das Flask-Blueprint erstellt für jede Anfrage einen `AlertManager` anhand der Datenbank-Verbindungsfactory der Anwendung. Der Manager lädt für jede Anfrage Regeln und nicht aufgelöste Alerts aus der Datenbank.

Die aktuelle API unterstützt:

- Alert-Regeln aufzulisten, zu erstellen, zu aktualisieren und zu löschen;
- für eine vorhandene aktivierte Regel manuell einen Alert auszulösen;
- aktive Alerts und paginierten Alert-Verlauf anzuzeigen;
- einen aktiven Alert zu bestätigen, aufzulösen und manuell hochzustufen.

Die Alert-Schweregrade sind `critical`, `warning` und `info`. Die gespeicherten Alert-Zustände sind `triggered`, `acknowledged`, `resolved` und `escalated`. Änderungen durch Bestätigung, Auflösung und Eskalation werden in `alert_history` geschrieben. Aufgelöste Alerts werden aus der Sammlung aktiver Alerts des Managers entfernt, bleiben aber in der Datenbank erhalten.

## Wichtige Einschränkungen

Das Regelmodell speichert eine Bedingung, einen Schwellenwert, den Schweregrad, einen Eskalationspfad sowie Kennzeichen für Gruppierung und Deduplizierung. Der aktuelle Server **wertet Bedingungen nicht anhand von Telemetrie oder anderen Messwerten aus**. Eine Regel löst nicht automatisch aus: Ein authentifizierter Aufrufer muss `POST /alerts/trigger` aufrufen. Beim Auslösen eines Alerts versucht der Manager, ihn über die im Eskalationspfad der Regel genannten Provider zu versenden. Die Webanwendung erstellt jeden Manager jedoch mit einer leeren Provider-Zuordnung, und ihre Integrationsendpunkte können keine Provider konfigurieren; daher wird bei Alerts, die über die Anwendung ausgelöst werden, derzeit keine Benachrichtigung zugestellt. Gruppierung und Deduplizierung werden lediglich gespeichert und nicht angewendet.

Der `AlertManager` definiert Provider-Klassen für E-Mail, Slack, PagerDuty und generische Webhooks. Diese Klassen werden jedoch nicht über die Anwendung konfiguriert. Die Integrations-API meldet Integrationen ausdrücklich als nicht verfügbar und antwortet auf Konfigurations-, Test- und Löschanfragen mit `501 Not Implemented`. Es ist keine Benachrichtigungszustellung zu erwarten. Auch `POST /alerts/clear-all` antwortet mit `501`, damit der Alert-Verlauf nicht über diesen Endpunkt gelöscht werden kann.

Die Seite `/alerts/` ist eine einfache serverseitig gerenderte Übersicht. Die Bedienelemente der Tabs für Regeln, Verlauf und Integrationen sowie die Aktionsschaltflächen für Alerts bilden keine vollständige interaktive Verwaltungsoberfläche. Maßgeblich ist das dokumentierte API-Verhalten; es darf nicht angenommen werden, dass eine sichtbare Schaltfläche eine Aktion ausführt. Die aktuelle Implementierung bietet keine Echtzeit-Push- oder WebSocket-Aktualisierungen.

## Routen und Zugriffskontrolle

Alle Routen erfordern eine authentifizierte Websitzung.

| Methode | Route | Berechtigung | Aktuelles Verhalten |
| --- | --- | --- | --- |
| `GET` | `/alerts/` | `alerts.view` | Rendert die einfache Alert-Übersicht |
| `GET` | `/alerts/rules` | `alerts.view` | Listet gespeicherte Regeln auf |
| `POST` | `/alerts/rules` | `alerts.manage` | Erstellt eine validierte Regel |
| `PUT` | `/alerts/rules/<rule_id>` | `alerts.manage` | Aktualisiert eine gespeicherte Regel |
| `DELETE` | `/alerts/rules/<rule_id>` | `alerts.manage` | Löscht eine Regel, sofern Datenbankbedingungen dies zulassen |
| `GET` | `/alerts/current` | `alerts.view` | Gibt aktive Alerts zurück |
| `GET` | `/alerts/history` | `alerts.view` | Gibt den Alert-Verlauf zurück |
| `POST` | `/alerts/trigger` | `alerts.manage` | Erstellt manuell einen Alert für eine aktivierte Regel |
| `POST` | `/alerts/<alert_id>/acknowledge` | `alerts.manage` | Protokolliert eine Bestätigung |
| `POST` | `/alerts/<alert_id>/resolve` | `alerts.manage` | Löst einen aktiven Alert auf |
| `POST` | `/alerts/<alert_id>/escalate` | `alerts.manage` | Erhöht manuell den Eskalationszähler |
| `POST` | `/alerts/clear-all` | `alerts.manage` | Deaktiviert; gibt `501` zurück |
| `GET` | `/alerts/integrations` | `alerts.view` | Gibt eine leere Liste und `available: false` zurück |
| `POST` / `DELETE` | `/alerts/integrations/...` | `alerts.manage` | Deaktiviert; gibt `501` zurück |

Mutierende Routen erfordern neben der jeweiligen Berechtigung auch CSRF-Schutz. Berechtigungsprüfungen werden auf dem Server durchgesetzt. `alerts.manage` setzt `alerts.view` voraus; Rollenzuweisungen werden durch die Sicherheitsmigration und die Berechtigungskonfiguration verwaltet.

## Persistente Tabellen

`AlertManager` initialisiert bei seiner Erstellung die folgenden Tabellen:

- `alert_rules`: Regeldefinitionen und konfigurierte Werte;
- `alerts`: Alert-Datensätze und aktueller Lebenszyklusstatus;
- `alert_history`: Verlauf von Bestätigungen, Auflösungen und Eskalationen;
- `notification_integrations`: reserviertes Schema für Integrationskonfigurationen;
- `alert_notifications_log`: reserviertes Schema für Zustellungsprotokolle.

Die letzten beiden Tabellen bedeuten nicht, dass Integrationen verfügbar sind. Die HTTP-Endpunkte für Integrationen bleiben deaktiviert, bis eine sichere persistente Konfiguration und ein Zustellungsverhalten implementiert sind.

## Verifizierung

Die Alert-Routen, Berechtigungsdurchsetzung, Payload-Validierung, Persistenz und der Lebenszyklus werden durch `tests/test_alerts.py` abgedeckt. Führe die relevanten Tests für die bereitzustellende Revision erneut aus. Eine erfolgreiche Testsuite macht deaktivierte Integrationsrouten oder nicht ausgewertete Regeln nicht zu verfügbaren Funktionen.

## Zugehöriger Code

- `server/alerts.py`
- `server/alerts_routes.py`
- `server/security.py`
- `server/security_migration.py`
- `tests/test_alerts.py`
