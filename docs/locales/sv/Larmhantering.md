# Larmhantering i LUMS: aktuell implementation

Den här anteckningen beskriver larmhanteringskoden som för närvarande finns i LUMS. Det är en kodreferens, inte en funktionsplan eller ett löfte om att alla synliga kontroller fungerar. Implementationen är centrerad kring `server/alerts.py` och `server/alerts_routes.py`.

## Implementerade funktioner

LUMS sparar larmregler, larmposter och historik över larmstatus i SQLite. Flask-blueprinten skapar en begärandespecifik `AlertManager` med applikationens fabrik för databasanslutningar. Hanteraren läser in regler och olösta larm från databasen för varje begäran.

Det aktuella API:t stöder:

- listning, skapande, uppdatering och borttagning av larmregler;
- manuell utlösning av ett larm för en befintlig aktiverad regel;
- visning av aktiva larm och paginerad larmhistorik;
- kvittering, lösning och manuell eskalering av ett aktivt larm.

Larmens allvarlighetsvärden är `critical`, `warning` och `info`. De lagrade larmstatusarna är `triggered`, `acknowledged`, `resolved` och `escalated`. Ändringar av kvittering, lösning och eskalering skrivs till `alert_history`. Lösta larm tas bort från hanterarens samling av aktiva larm men finns kvar i databasen.

## Viktiga begränsningar

Regelmodellen lagrar ett villkor, ett tröskelvärde, en allvarlighetsgrad, en eskaleringsväg, en grupperingsflagga och en dedupliceringsflagga. Den aktuella servern utvärderar **inte** villkor mot telemetri eller andra mätvärden. En regel utlöses inte automatiskt: en autentiserad anropare måste anropa `POST /alerts/trigger`. Gruppering och deduplicering lagras men tillämpas inte. När ett larm utlöses försöker hanteraren skicka det via de leverantörer som anges i regelns eskaleringsväg. Webbappen skapar varje hanterare med en tom leverantörskarta och integrationsgränssnitten kan inte konfigurera leverantörer; därför sker för närvarande ingen avisering när larm utlöses via applikationen.

`AlertManager` definierar leverantörsklasser för e-post, Slack, PagerDuty och generiska webhooks, men dessa konfigureras inte via applikationen. Integrations-API:t rapporterar avsiktligt att integrationer inte är tillgängliga och returnerar `501 Not Implemented` för begäranden om konfiguration, testning och borttagning. Ingen avisering bör förväntas levereras. Även `POST /alerts/clear-all` returnerar `501`, så att larmhistorik inte kan tas bort via den slutpunkten.

Sidan `/alerts/` är en grundläggande serverrenderad översikt. Kontrollerna för flikarna för regler, historik och integrationer samt larmåtgärdsknapparna utgör inte ett fullständigt interaktivt administrationsgränssnitt. Använd det dokumenterade API-beteendet som sanningskälla i stället för att anta att en synlig knapp utför en åtgärd. Den aktuella implementationen stöder inte push- eller WebSocket-uppdateringar i realtid.

## Rutter och åtkomstkontroll

Alla rutter kräver en autentiserad webbsession.

| Metod | Rutt | Behörighet | Aktuellt beteende |
| --- | --- | --- | --- |
| `GET` | `/alerts/` | `alerts.view` | Visar den grundläggande larmöversikten |
| `GET` | `/alerts/rules` | `alerts.view` | Listar lagrade regler |
| `POST` | `/alerts/rules` | `alerts.manage` | Skapar en validerad regel |
| `PUT` | `/alerts/rules/<rule_id>` | `alerts.manage` | Uppdaterar en lagrad regel |
| `DELETE` | `/alerts/rules/<rule_id>` | `alerts.manage` | Tar bort en regel om databasbegränsningarna tillåter det |
| `GET` | `/alerts/current` | `alerts.view` | Returnerar aktiva larm |
| `GET` | `/alerts/history` | `alerts.view` | Returnerar larmhistorik |
| `POST` | `/alerts/trigger` | `alerts.manage` | Skapar manuellt ett larm för en aktiverad regel |
| `POST` | `/alerts/<alert_id>/acknowledge` | `alerts.manage` | Registrerar en kvittering |
| `POST` | `/alerts/<alert_id>/resolve` | `alerts.manage` | Löser ett aktivt larm |
| `POST` | `/alerts/<alert_id>/escalate` | `alerts.manage` | Ökar eskaleringsräknaren manuellt |
| `POST` | `/alerts/clear-all` | `alerts.manage` | Inaktiverad; returnerar `501` |
| `GET` | `/alerts/integrations` | `alerts.view` | Returnerar en tom lista och `available: false` |
| `POST` / `DELETE` | `/alerts/integrations/...` | `alerts.manage` | Inaktiverad; returnerar `501` |

Ändrande rutter kräver CSRF-skydd och relevant behörighet. Behörighetskontroller utförs på servern. `alerts.manage` är beroende av `alerts.view`; rollernas tilldelningar hanteras av säkerhetsmigreringen och behörighetskonfigurationen.

## Beständiga tabeller

`AlertManager` initierar följande tabeller när den skapas:

- `alert_rules`: regeldefinitioner och konfigurerade värden;
- `alerts`: larmposter och aktuellt livscykeltillstånd;
- `alert_history`: historik över kvittering, lösning och eskalering;
- `notification_integrations`: reserverat schema för integrationskonfiguration;
- `alert_notifications_log`: reserverat schema för leveranslogg.

De två sista tabellerna betyder inte att integrationer är tillgängliga. HTTP-integrationsslutpunkterna är fortfarande inaktiverade tills säker beständig konfiguration och leveransfunktionalitet har implementerats.

## Verifiering

Larmrutter, behörighetskontroller, validering av nyttolast, persistens och livscykelbeteende täcks av `tests/test_alerts.py`. Kör relevanta tester på nytt mot den revision som ska distribueras. En godkänd testsvit gör inte inaktiverade integrationsrutter eller otestade regler till tillgängliga funktioner.

## Relaterad kod

- `server/alerts.py`
- `server/alerts_routes.py`
- `server/security.py`
- `server/security_migration.py`
- `tests/test_alerts.py`
