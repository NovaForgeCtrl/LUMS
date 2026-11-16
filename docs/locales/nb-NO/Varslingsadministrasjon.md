# LUMS-varsler: gjeldende implementasjon

Dette dokumentet beskriver varslingsadministrasjonen som faktisk finnes i LUMS-koden. Det er en kodereferanse, ikke et veikart eller et løfte om at alle synlige kontroller fungerer. Implementasjonen ligger hovedsakelig i `server/alerts.py` og `server/alerts_routes.py`.

## Dette er implementert

LUMS lagrer varslingsregler, varslingsposter og varselhistorikk i SQLite. Flask-blueprintet oppretter en forespørselsspesifikk `AlertManager` ved hjelp av programmets databasekoblingsfabrikk. Behandleren laster regler og uløste varsler fra databasen for hver forespørsel.

Det gjeldende API-et støtter:

- visning, oppretting, oppdatering og sletting av varslingsregler
- manuell utløsing av et varsel for en eksisterende aktivert regel
- visning av aktive varsler og paginert varslingshistorikk
- bekreftelse, løsning og manuell eskalering av et aktivt varsel

Alvorlighetsgradene er `critical`, `warning` og `info`. De lagrede varseltilstandene er `triggered`, `acknowledged`, `resolved` og `escalated`. Bekreftelse, løsning og eskalering registreres i `alert_history`. Løste varsler fjernes fra behandlerens samling av aktive varsler, men beholdes i databasen.

## Viktige begrensninger

Regelmodellen lagrer en betingelse, terskel, alvorlighetsgrad, eskaleringsbane, grupperingsflagg og dedupliseringsflagg. Den gjeldende serveren evaluerer **ikke** betingelser mot telemetri eller andre målinger. En regel utløses ikke automatisk: en autentisert klient må kalle `POST /alerts/trigger`. Gruppering og deduplisering lagres, men brukes ikke. Ved manuell utløsing forsøker behandleren å sende varselet via leverandørene som er angitt i regelens eskaleringsbane. Webapplikasjonen oppretter hver behandler med et tomt leverandørkart, og integrasjonsendepunktene kan ikke konfigurere leverandører. Varsler som utløses via applikasjonen, blir derfor ikke levert.

`AlertManager` definerer leverandørklasser for e-post, Slack, PagerDuty og generiske webhooks, men disse konfigureres ikke gjennom applikasjonen. Integrasjons-API-et oppgir med hensikt at integrasjoner ikke er tilgjengelige og returnerer `501 Not Implemented` for forespørsler om konfigurering, testing og sletting. `POST /alerts/clear-all` returnerer også `501`, slik at varslingshistorikken ikke kan slettes via dette endepunktet.

Siden `/alerts/` er en enkel, serverrendret oversikt. Kontrollene for regel-, historikk- og integrasjonsfaner samt handlingsknappene for varsler utgjør ikke et fullstendig interaktivt administrasjonsgrensesnitt. Bruk den dokumenterte API-atferden som fasit; ikke anta at en synlig knapp utfører en handling. Implementasjonen støtter ikke sanntidsoppdateringer via push eller WebSocket.

## Ruter og tilgangskontroll

Alle rutene krever en autentisert webøkt.

| Metode | Rute | Tillatelse | Gjeldende atferd |
| --- | --- | --- | --- |
| `GET` | `/alerts/` | `alerts.view` | Gjengir den enkle varseloversikten |
| `GET` | `/alerts/rules` | `alerts.view` | Lister lagrede regler |
| `POST` | `/alerts/rules` | `alerts.manage` | Oppretter en validert regel |
| `PUT` | `/alerts/rules/<rule_id>` | `alerts.manage` | Oppdaterer en lagret regel |
| `DELETE` | `/alerts/rules/<rule_id>` | `alerts.manage` | Sletter en regel når databasebegrensningene tillater det |
| `GET` | `/alerts/current` | `alerts.view` | Returnerer aktive varsler |
| `GET` | `/alerts/history` | `alerts.view` | Returnerer varslingshistorikk |
| `POST` | `/alerts/trigger` | `alerts.manage` | Oppretter manuelt et varsel for en aktivert regel |
| `POST` | `/alerts/<alert_id>/acknowledge` | `alerts.manage` | Registrerer en bekreftelse |
| `POST` | `/alerts/<alert_id>/resolve` | `alerts.manage` | Løser et aktivt varsel |
| `POST` | `/alerts/<alert_id>/escalate` | `alerts.manage` | Øker eskaleringsantallet manuelt |
| `POST` | `/alerts/clear-all` | `alerts.manage` | Deaktivert; returnerer `501` |
| `GET` | `/alerts/integrations` | `alerts.view` | Returnerer en tom liste og `available: false` |
| `POST` / `DELETE` | `/alerts/integrations/...` | `alerts.manage` | Deaktivert; returnerer `501` |

Endrende ruter krever CSRF-beskyttelse og den relevante tillatelsen. Tillatelsene håndheves på serveren. `alerts.manage` avhenger av `alerts.view`; rolletildelingene vedlikeholdes av sikkerhetsmigreringen og tillatelseskonfigurasjonen.

## Vedvarende tabeller

`AlertManager` initialiserer følgende tabeller ved opprettelse:

- `alert_rules`: regeldefinisjoner og konfigurerte verdier
- `alerts`: varselposter og gjeldende livssyklustilstand
- `alert_history`: historikk for bekreftelse, løsning og eskalering
- `notification_integrations`: reservert skjema for integrasjonskonfigurasjon
- `alert_notifications_log`: reservert skjema for leveringslogg

De to siste tabellene betyr ikke at integrasjoner er tilgjengelige. HTTP-endepunktene for integrasjoner forblir deaktivert inntil sikker, vedvarende konfigurering og leveringsatferd er implementert.

## Verifisering

Varslingsruter, håndheving av tillatelser, validering av forespørselsdata, lagring og livssyklusatferd dekkes av `tests/test_alerts.py`. Kjør de relevante testene på nytt mot revisjonen som skal distribueres. En bestått testpakke gjør ikke de deaktiverte integrasjonsrutene eller uevaluerte reglene tilgjengelige funksjoner.

## Relatert kode

- `server/alerts.py`
- `server/alerts_routes.py`
- `server/security.py`
- `server/security_migration.py`
- `tests/test_alerts.py`
