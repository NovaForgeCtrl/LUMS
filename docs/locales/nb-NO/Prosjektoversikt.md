# LUMS

**Linux-oppdateringshåndtering uten støy.**

## Kom i gang

LUMS administrerer Linux-oppdateringer sentralt. A server displays clients, installed
software, and available updates. An agent on each managed Linux system performs
approved package actions using that system's package manager. LUMS does not
replace APT on Debian/Ubuntu or pacman on Arch Linux.

**Only using an existing LUMS installation?** Open the address provided by
your administrator and sign in with your own account. If a feature is missing,
your account may not have permission to use it. Ask your administrator for
help; do not share accounts or use a client token as a web password.

**Installing or operating LUMS?** Start with the
[installation guide](install.md), then read the
[administration guide](administration.md). If something goes wrong, use the
[troubleshooting guide](troubleshooting.md). These detailed technical guides
are maintained in English; translated guides are listed in
[`docs/README.md`](docs/README.md). Translation coverage can vary, so use the
English source when a localized procedure is incomplete or differs.

A test run or a successfully built Docker image is **not** a production
installation. A production deployment also needs HTTPS, a protected application
secret, persistent data, verified backups, and a hardened container. Do not
copy production commands until you have checked their placeholders and storage
paths against your own installation.

### Web interface languages

The web interface offers German, English (US and UK), French, Spanish,
Simplified Chinese, Japanese, Polish, Swedish, Norwegian Bokmål, and Finnish.
Choose a language from the upper-right corner of the login page. If you do not
choose one, LUMS tries to use the browser language; after sign-in, a language
saved to your account takes precedence. Some technical or dynamic text may
remain in its original language when a translation is not available. Markdown
guides are separate from the web interface and are not translated
automatically.
LUMS administrerer Linux-oppdateringer sentralt. En server viser klienter,
installert programvare og tilgjengelige oppdateringer. En agent på hvert
administrerte Linux-system utfører godkjente pakkehandlinger ved hjelp av
systemets pakkebehandler. LUMS erstatter ikke APT på Debian/Ubuntu eller pacman
på Arch Linux.

**Bruker du bare en eksisterende LUMS-installasjon?** Åpne adressen du har fått
av administratoren din, og logg inn med din egen konto. Hvis en funksjon mangler,
kan det hende at kontoen din ikke har tillatelse til å bruke den. Be
administratoren din om hjelp; ikke del kontoer og ikke bruk et klienttoken som
passord for nettpålogging.

**Installerer eller drifter du LUMS?** Start med
[installasjonsveiledningen](<Installasjon og oppgraderinger.md>), og les deretter
[administrasjonsveiledningen](<Administrasjon og sikkerhetskopier.md>). Hvis noe
går galt, bruk [feilsøkingsveiledningen](Feilsøking.md). Lokaliserte bruker- og
administratorveiledninger er oppført i [`docs/README.md`](../../README.md). De
engelske rotveiledningene er fortsatt den tekniske kilden til sannhet; hvis en
oversatt prosedyre virker ufullstendig eller avviker, følger du den engelske
kilden.

En testkjøring eller et vellykket bygget Docker-bilde er **ikke** en
produksjonsinstallasjon. En produksjonsdistribusjon trenger også HTTPS, en
beskyttet applikasjonshemmelighet, vedvarende data, verifiserte sikkerhetskopier
og en herdet container. Ikke kopier produksjonskommandoer før du har kontrollert
plassholderne og lagringsbanene mot din egen installasjon.

### Språk i nettgrensesnittet

Nettgrensesnittet tilbyr tysk, engelsk (US og UK), fransk, spansk, forenklet
kinesisk, japansk, polsk, svensk, norsk bokmål og finsk. Velg språk øverst til
høyre på påloggingssiden. Hvis du ikke velger noe, prøver LUMS å bruke
nettleserens språk; etter innlogging har et språk som er lagret på kontoen din,
forrang. Noe teknisk eller dynamisk tekst kan forbli på originalspråket når en
oversettelse ikke er tilgjengelig. Markdown-veiledninger er atskilt fra
nettgrensesnittet og oversettes ikke automatisk. Oversatte Markdown-veiledninger
vedlikeholdes separat; bruk dokumentasjonsoversikten for å finne tilgjengelig
dekning per språk.

---

LUMS is a Linux update management server designed to provide controlled, auditable, and secure software and update management for Linux clients.

Instead of relying on uncontrolled client-side update activity, LUMS provides a central management layer for software inventory, update detection, package operations, update jobs, execution monitoring, and result reporting.
I stedet for å stole på ukontrollert oppdateringsaktivitet på klientsiden gir LUMS et sentralt administrasjonslag for programvareinventar, oppdateringsregistrering, pakkeoperasjoner, oppdateringsjobber, overvåking av kjøringer og rapportering av resultater.

LUMS is designed for environments where updates should be **visible, controlled, traceable, and recoverable**.

---

Hva er LUMS?

LUMS (**Linux Update Management Server**) consists of a central server and lightweight Linux clients.

The server provides the management interface, API, authentication, authorization, job management, audit logging, and persistent state.

The client-side agent performs local package-manager operations and reports the results back to the server.
Serveren tilbyr administrasjonsgrensesnittet, API-et, autentisering, autorisasjon, jobbadministrasjon, revisjonslogging og vedvarende tilstand.

Agenten på klientsiden utfører lokale operasjoner i pakkebehandleren og rapporterer resultatene tilbake til serveren.

The basic architecture is:

```text
                    ┌──────────────────────┐
                    │      Web Browser      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     LUMS Server      │
                    │                      │
                    │ Web UI / API         │
                    │ Authentication       │
                    │ RBAC                 │
                    │ Job Management       │
                    │ Audit Logging        │
                    │ SQLite               │
                    └──────────┬───────────┘
                               │
                         HTTPS / API
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
      ┌─────────────────┐             ┌─────────────────┐
      │   Linux Client  │             │   Linux Client  │
      │                 │             │                 │
      │ LUMS Agent      │             │ LUMS Agent      │
      │ Package Manager │             │ Package Manager │
      │ Watcher         │             │ Watcher         │
      └─────────────────┘             └─────────────────┘
```

---

Hvorfor LUMS?

Linux systems already provide excellent package-management tools.

LUMS does not attempt to replace them.

Instead, LUMS provides a management layer around those tools so that administrators can centrally answer questions such as:
## Hvorfor LUMS?

Linux-systemer har allerede utmerkede verktøy for pakkeadministrasjon.

* Which clients exist?
* Which software is installed?
* Which updates are available?
* Which packages should be installed or removed?
* Which update jobs are running?
* What happened during an update?
* Did the client successfully report the result?
* Was a reboot required?
* Can an interrupted job recover safely?
* Who initiated an administrative action?

The goal is not to hide the underlying Linux package manager.

The goal is to make its operation **manageable and auditable**.

---

## Kjernefunksjoner

### Klientadministrasjon

LUMS maintains registered Linux clients and their authentication state.

Each client receives an individual authentication token.

Client tokens are not stored as plaintext credentials. The server stores a SHA-256 digest and validates incoming client authentication against that digest.

Administrators can:

* register clients
* disable clients
* rotate client tokens
* inspect client status
* monitor client reporting
* view client telemetry (CPU, memory, network when telemetry is enabled)

---

### Software Inventory

Clients report their installed software to the LUMS server.
* Hvilke klienter finnes?
* Hvilken programvare er installert?
* Hvilke oppdateringer er tilgjengelige?
* Hvilke pakker bør installeres eller fjernes?
* Hvilke oppdateringsjobber kjører?
* Hva skjedde under en oppdatering?
* Rapporterte klienten resultatet vellykket?
* Var en omstart nødvendig?
* Kan en avbrutt jobb gjenopprettes trygt?
* Hvem startet en administrativ handling?

The server stores the inventory and exposes it through the management interface.

The installed-software view is intentionally separate from package-management search.

This allows administrators and read-only users to inspect installed software without automatically exposing package-management operations.
Målet er å gjøre driften av den **håndterbar og reviderbar**.

---

## Kjernefunksjoner

### Klientadministrasjon

LUMS holder oversikt over registrerte Linux-klienter og deres autentiseringstilstand.

---

### Fleet Telemetry and Health Dashboard
Klienttokener lagres ikke som legitimasjon i klartekst. Serveren lagrer en SHA-256-digest og validerer innkommende klientautentisering mot denne digesten.

The optional telemetry system monitors CPU utilization, memory utilization, and network traffic across the fleet.

The `/health` dashboard provides:

* Real-time client status (online, unknown, offline)
* CPU and memory utilization charts (line, area, or current-value gauges)
* Network traffic monitoring (receive/transmit bytes per second)
* 1-hour, 24-hour, and 7-day historical views
* Client filtering (by status, stale telemetry, high load)
* Searchable client list with sortable columns
* Automatic data refresh every 5 seconds
* Latest backup status

Telemetry data is retained for 7 days. Telemetry submission occurs approximately every 5 seconds when the agent's systemd timer is enabled and the client can reach the server.

---

### Theme System

LUMS includes an optional theme system providing six visual themes:
* registrere klienter
* deaktivere klienter
* rotere klienttokener
* inspisere klientstatus
* overvåke klientrapportering

---

### Programvareinventar

* **standard** - default LUMS interface
* **LUMSStadium** - alternative corporate theme
* **golf** - calming aesthetic
* **nerd** - developer-focused theme
* **geek** - technical theme
* **admin** - administrator-specific theme

Themes are visual presentation only and do not modify authentication, authorization, update execution, or security controls. Theme preference is stored in browser local storage and persists across sessions.

---

### Update Inventory

Clients periodically determine whether package updates are available.
Serveren lagrer inventaret og viser det gjennom administrasjonsgrensesnittet.

Visningen av installert programvare er bevisst atskilt fra pakkesøk i pakkeadministrasjonen.

Dette gjør at administratorer og brukere med skrivebeskyttet tilgang kan inspisere installert programvare uten at pakkeadministrasjonsoperasjoner automatisk blir eksponert.

---

### Oppdateringsinventar

Klienter fastslår jevnlig om pakkeoppdateringer er tilgjengelige.

The server stores the reported update information and makes it available to authorized users.

Update information can be used as the basis for controlled update jobs.

---

### Package Management

LUMS provides package-management operations through the client agent.

Supported package operations include:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

The package-management layer abstracts the underlying package manager.
Oppdateringsinformasjon kan brukes som grunnlag for kontrollerte oppdateringsjobber.

---

### Pakkeadministrasjon

LUMS tilbyr pakkeadministrasjonsoperasjoner gjennom klientagenten.

Støttede pakkeoperasjoner omfatter:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Current supported package-manager families are:

* **Debian / Ubuntu:** APT / dpkg
* **Arch Linux:** pacman

Package search is also available through LUMS.

Search requests are sent to the target client, executed using the local package manager, and returned to the server for display.
Pakkebehandlerfamiliene som støttes i dag, er:

* **Debian / Ubuntu:** APT / dpkg
* **Arch Linux:** pacman

---

### Update Jobs
Søkeforespørsler sendes til målklienten, utføres med den lokale pakkebehandleren og returneres til serveren for visning.

---

### Oppdateringsjobber

Update operations are represented as persistent jobs.

A job can contain one or more package operations and maintains a server-side execution state.
En jobb kan inneholde én eller flere pakkeoperasjoner og har en kjøringstilstand på serversiden.

The general lifecycle is:

```text
PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► SUCCESS
   │
   └──────────────► FAILED
```

Package-level results are tracked independently so that interrupted jobs can be recovered without unnecessarily repeating operations that already completed successfully.

---

### Controlled Execution

LUMS does not execute arbitrary shell commands supplied by the web interface.
Resultater på pakkenivå spores uavhengig, slik at avbrutte jobber kan gjenopprettes uten unødvendig å gjenta operasjoner som allerede er fullført.

---

### Kontrollert kjøring

LUMS kjører ikke vilkårlige shell-kommandoer levert av nettgrensesnittet.

The server creates structured jobs using validated actions and package names.

The client agent maps those actions to the appropriate local package-manager operation.

This creates a deliberate boundary between:
Klientagenten kobler disse handlingene til riktig lokal pakkebehandleroperasjon.

Dette skaper et bevisst skille mellom:

```text
Web UI
   ↓
API
   ↓
Validated Job
   ↓
Agent
   ↓
Package Manager
```

---

### Idle-Aware Execution

LUMS can defer update execution while a client is considered active.

The current idle threshold is **300 seconds**.

Where supported, the agent uses the local system's session/idle information through `loginctl`.

If idle detection is unavailable, LUMS does not pretend that the client is idle.

This distinction is important because **unknown idle state is not the same as confirmed idle state**.

---

### Job Recovery

Update jobs are designed to survive interruptions.

The server maintains persistent job and package-item state.

During recovery, already successful package items are not unnecessarily executed again.

This provides a checkpoint-like execution model for multi-package operations.
### Inaktivitetsbevisst kjøring

LUMS kan utsette kjøring av oppdateringer mens en klient regnes som aktiv.

Den nåværende inaktivitetsgrensen er **300 sekunder**.

Der det støttes, bruker agenten det lokale systemets økt- og inaktivitetsinformasjon via `loginctl`.

Hvis inaktivitetsregistrering ikke er tilgjengelig, later ikke LUMS som om klienten er inaktiv.

Dette skillet er viktig fordi **ukjent inaktivitetstilstand ikke er det samme som bekreftet inaktivitet**.

---

### Jobbgjenoppretting

The goal is:

> **Recover the job, not blindly restart the entire job.**

---

### Reboot Detection

Some package operations can require a system reboot.
Serveren opprettholder vedvarende tilstand for jobber og pakkeelementer.

Under gjenoppretting kjøres pakkeelementer som allerede er vellykket, ikke unødvendig på nytt.

Dette gir en kontrollpunktlignende kjøringsmodell for operasjoner med flere pakker.

LUMS therefore treats reboot detection as part of update-result handling rather than assuming that a successful package-manager exit always means that the system is fully operational.

The client reports the detected reboot requirement back to the server.

---
> **Gjenopprett jobben, ikke start hele jobben blindt på nytt.**

---

### Omstartsregistrering

### Client Authentication

Client communication is authenticated using per-client tokens.

Tokens are:

* individually assigned
* rotatable
* stored server-side only as SHA-256 digests
* validated before accepting client reports

Token rotation allows an administrator to invalidate a previously issued client credential without recreating the client.

---

### Health dashboard

The authenticated health dashboard at `/health` summarizes the database status,
client reporting status, backup-storage visibility, and CPU/memory telemetry
when telemetry is configured. It is a quick operational view, not a substitute
for checking container, reverse-proxy, host, and backup logs or for performing
a restore test. See [LUMS_Health_Dashboard.md](LUMS_Health_Dashboard.md).

---

### Auditability

Administrative and security-relevant actions are recorded through the LUMS audit-log system.

The audit trail is intended to answer:
LUMS behandler derfor omstartsregistrering som en del av håndteringen av oppdateringsresultater, i stedet for å anta at en vellykket avslutning av pakkebehandleren alltid betyr at systemet er fullt operativt.

Klienten rapporterer det registrerte omstartsbehovet tilbake til serveren.

---

### Klientautentisering

Klientkommunikasjon autentiseres med tokener per klient.

Tokenene er:

* individuelt tildelt
* mulige å rotere
* lagret på serversiden kun som SHA-256-digester
* validert før klientrapporter godtas

Tokenrotasjon lar en administrator ugyldiggjøre en tidligere utstedt klientlegitimasjon uten å opprette klienten på nytt.

---

### Helseoversikt

Den autentiserte helseoversikten på `/health` oppsummerer databasestatus,
status for klientrapportering, synlighet av lagring for sikkerhetskopier og
CPU- og minnetelemetri når telemetri er konfigurert. Det er en rask
driftsvisning, ikke en erstatning for å kontrollere logger fra containere,
reverse proxy, vert og sikkerhetskopier, eller for å utføre en
gjenopprettingstest. Se [LUMS-helseoversikt.md](LUMS-helseoversikt.md).

---

### Varsler

LUMS inneholder et API for varslingsadministrasjon og et enkelt dashbord for
lagrede varselposter. Administratorer kan opprette og administrere regler,
utløse et varsel manuelt, og kvittere, løse eller manuelt eskalere et aktivt
varsel. Regelbetingelser og terskler lagres som konfigurasjon; den nåværende
serveren evaluerer dem ikke automatisk mot telemetri. Varslingsintegrasjoner
(e-post, Slack, PagerDuty og generiske webhooks) er ikke tilgjengelige gjennom
API-et, og masseopprydding er deaktivert for å bevare varslingshistorikken. Se
[`docs/LUMS_REALTIME_ALERTING_IMPLEMENTATION.md`](../../LUMS_REALTIME_ALERTING_IMPLEMENTATION.md)
for de implementerte grensene.

---

### Revisjonsevne

Administrative og sikkerhetsrelevante handlinger registreres i LUMS' revisjonsloggsystem.

Revisjonssporet er ment å besvare:

```text
Who?
What?
When?
Against which object?
With which result?
```

This includes security-sensitive operations such as authentication-related actions, client management, user management, and update-job creation.

---

## Design Principle
Dette omfatter sikkerhetssensitive operasjoner som autentiseringsrelaterte handlinger, klientadministrasjon, brukeradministrasjon og opprettelse av oppdateringsjobber.

---

## Designprinsipp

LUMS follows a simple principle:

> **Make Linux update management visible, controlled, recoverable, and auditable — without hiding the Linux tools underneath.**

## Arkitektur

LUMS separates management, execution, and persistence into clearly defined components.
> **Gjør administrasjon av Linux-oppdateringer synlig, kontrollert, gjenopprettbar og reviderbar — uten å skjule Linux-verktøyene under.**

## Arkitektur

LUMS skiller administrasjon, kjøring og persistens i tydelig definerte komponenter.

The server is responsible for orchestration and policy.

The client is responsible for local system interaction.

The package manager remains responsible for actually installing, removing, or updating software.

This separation is intentional.
Pakkebehandleren er fortsatt ansvarlig for selve installasjonen, fjerningen og oppdateringen av programvare.

Denne separasjonen er bevisst.

```text
Browser
   │
   │ HTTPS
   ▼
┌──────────────────────────────────────────┐
│                LUMS Server                │
│                                          │
│  Web UI                                  │
│  Authentication / Sessions               │
│  RBAC                                    │
│  API                                     │
│  Client Management                       │
│  Package Search                          │
│  Update Job Management                   │
│  Audit Logging                            │
│  SQLite Persistence                       │
└───────────────────┬──────────────────────┘
                    │
                    │ HTTPS / Client API
                    ▼
┌──────────────────────────────────────────┐
│               LUMS Agent                  │
│                                          │
│  Authentication                          │
│  Inventory Reporting                     │
│  Update Detection                        │
│  Package Search                          │
│  Job Execution                           │
│  Result Reporting                        │
│  Reboot Detection                        │
│  Idle Detection                          │
└───────────────────┬──────────────────────┘
                    │
                    ▼
          ┌────────────────────┐
          │ Package Manager    │
          │                    │
          │ APT / dpkg         │
          │ pacman             │
          └────────────────────┘
```

---

## Serverkomponenter

The LUMS server provides the central management layer.

### Web Application

The web application provides the administrative interface for:

* client management
* software inventory
* update information
* update jobs
* package management
* update history
* user management
* system maintenance

The interface respects the current user's RBAC role.

Frontend visibility is therefore adapted to the user's permissions, but authorization is always enforced server-side as well.

---

## Serverkomponenter

LUMS-serveren utgjør det sentrale administrasjonslaget.

### Webapplikasjon

Webapplikasjonen tilbyr det administrative grensesnittet for:

* klientadministrasjon
* programvareinventar
* oppdateringsinformasjon
* oppdateringsjobber
* pakkeadministrasjon
* oppdateringshistorikk
* brukeradministrasjon
* systemvedlikehold

Grensesnittet respekterer den gjeldende brukerens RBAC-rolle.

Hva som er synlig i frontend, tilpasses derfor brukerens tillatelser, men autorisasjon håndheves alltid også på serversiden.

---

### API

The API connects the web interface and Linux clients to the server-side application logic.

It handles operations such as:

* client registration and management
* client reports
* package searches
* package-search results
* update jobs
* job results
* user management
* audit events

API endpoints validate their input before performing state-changing operations.

---

### Authentication and Sessions

Administrative users authenticate through the LUMS web application.

Sessions are server-controlled and support explicit session revocation.

Authentication security includes:

* password hashing using Argon2
* session management
* session revocation
* login rate limiting
* CSRF protection
* role-based authorization

Client authentication is separate from administrative authentication.

---

### RBAC

LUMS combines role templates with per-user permissions. The Administrator,
Operator, and Viewer templates provide starting permission sets that can be
customized for each account.

Authorization is enforced on the server using the account's stored permissions.

The frontend additionally hides functionality that the user's permissions do
not allow.
API-et kobler nettgrensesnittet og Linux-klientene til applikasjonslogikken på serversiden.

Det håndterer operasjoner som:

* klientregistrering og -administrasjon
* klientrapporter
* pakkesøk
* resultater av pakkesøk
* oppdateringsjobber
* jobbresultater
* brukeradministrasjon
* revisjonshendelser

API-endepunktene validerer inndata før de utfører tilstandsendrende operasjoner.

---

### Autentisering og økter

Administrative brukere autentiserer seg gjennom LUMS-webapplikasjonen.

Økter kontrolleres av serveren og støtter eksplisitt tilbakekalling av økter.

Autentiseringssikkerheten omfatter:

* passordhashing med Argon2
* øktadministrasjon
* tilbakekalling av økter
* begrensning av påloggingsforsøk
* CSRF-beskyttelse
* rollebasert autorisasjon

Klientautentisering er atskilt fra administrativ autentisering.

---

### RBAC

LUMS kombinerer rollemaler med tillatelser per bruker. Malene Administrator,
Operator og Viewer gir utgangspunkt i sett av tillatelser som kan tilpasses for
hver konto.

Autorisasjon håndheves på serveren ut fra kontoens lagrede tillatelser.

Frontend skjuler i tillegg funksjonalitet som brukerens tillatelser ikke gir
adgang til.

Dette betyr at det å skjule en knapp aldri regnes som en sikkerhetsgrense.

---

### SQLite-persistens

This means that hiding a button is never treated as a security boundary.

---

### SQLite Persistence

LUMS uses SQLite for persistent application state.

The database stores information such as:

* users
* sessions
* clients
* client authentication state
* software inventory
* available updates
* update jobs
* package-level job results
* package-search requests and results
* audit information

The application explicitly enables SQLite foreign-key enforcement for database connections.

The current production SQLite baseline is:
Databasen lagrer informasjon som:

* brukere
* økter
* klienter
* klientenes autentiseringstilstand
* programvareinventar
* tilgjengelige oppdateringer
* oppdateringsjobber
* resultater per pakke i jobber
* forespørsler og resultater for pakkesøk
* revisjonsinformasjon

Applikasjonen aktiverer eksplisitt håndheving av fremmednøkler i SQLite for databasetilkoblinger.

Den nåværende SQLite-grunnlinjen for produksjon er:

```text
journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

LUMS uses SQLite WAL mode in the current production configuration.

---

## Container Architecture
LUMS bruker SQLite WAL-modus i den nåværende produksjonskonfigurasjonen.

---

## Containerarkitektur

The LUMS server is deployed as a hardened Docker container.

The application container is intentionally treated as disposable.

Persistent application state is stored in the dedicated Docker volume:

```text
lums-data
```

The production container uses a read-only root filesystem.

Writable locations are deliberately restricted to required runtime and persistent storage paths.

The production security baseline includes:
Skrivbare plasseringer er bevisst begrenset til nødvendige kjøretids- og lagringsbaner for vedvarende data.

Sikkerhetsgrunnlinjen for produksjon omfatter:

```text
read-only root filesystem
all Linux capabilities dropped
no-new-privileges
restricted /tmp
restricted /run
read-only secret mount
dedicated persistent data volume
non-root application user
```

The application is exposed internally through:

```text
127.0.0.1:5050
```

External HTTPS access is provided through the reverse proxy.

---

## Persistent and Disposable Components

LUMS separates persistent state from replaceable runtime components.
Ekstern HTTPS-tilgang leveres gjennom reverse proxy.

---

## Vedvarende og utskiftbare komponenter

LUMS skiller vedvarende tilstand fra utskiftbare kjøretidskomponenter.

```text
Persistent
├── SQLite database
├── client state
├── user state
├── job state
└── audit state

Disposable
├── Docker container
├── application process
└── generated runtime state
```

Replacing the application container therefore does not inherently remove the LUMS database.

This separation is important for upgrades and recovery.
Å bytte ut applikasjonscontaineren fjerner derfor ikke i seg selv LUMS-databasen.

Denne separasjonen er viktig for oppgraderinger og gjenoppretting.

---

## Klientarkitektur

Linux-klienten består av flere samarbeidende komponenter.

### LUMS-agent

Agenten er ansvarlig for samhandlingen med LUMS-serveren og det lokale Linux-systemet.

---

## Client Architecture

The Linux client consists of several cooperating components.

### LUMS Agent

The agent is responsible for interaction with the LUMS server and the local Linux system.

Current agent version:

```text
1.7.0
```

The agent handles:

* authentication
* inventory collection
* update detection
* package search
* package operations
* update-job execution
* result reporting
* reboot detection
* idle-state handling

---

### Package Manager Layer

The package-manager layer provides a controlled abstraction around the native Linux package manager.
* autentisering
* innsamling av inventar
* oppdateringsregistrering
* pakkesøk
* pakkeoperasjoner
* kjøring av oppdateringsjobber
* rapportering av resultater
* omstartsregistrering
* håndtering av inaktivitetstilstand

---

### Pakkebehandlerlag

The agent does not require LUMS to replace the package manager.

Instead:
I stedet:

```text
LUMS Action
     │
     ▼
Package Manager Abstraction
     │
     ├── Debian / Ubuntu → APT / dpkg
     │
     └── Arch Linux      → pacman
```

This keeps distribution-specific package handling inside the client.

---

### Execution Watcher

The watcher monitors update-job execution on the client.

Current watcher version:
Dette holder distribusjonsspesifikk pakkehåndtering inne i klienten.

---

### Kjøringsvakt (Watcher)

Watcheren overvåker kjøringen av oppdateringsjobber på klienten.

Gjeldende watcher-versjon:

```text
1.2.1
```

The watcher works together with the agent and the server-side job state.

Its purpose is to ensure that jobs which are expected to execute do not remain indefinitely unprocessed.

---

## Reporting Path
Watcheren samarbeider med agenten og jobbtilstanden på serversiden.

Formålet er å sikre at jobber som forventes å bli utført, ikke blir liggende ubehandlet på ubestemt tid.

---

## Rapporteringsvei

Normal client reporting follows this direction:

```text
Linux Client
    │
    │ inventory / update information
    ▼
LUMS API
    │
    ▼
SQLite
    │
    ▼
Web UI
```

For example, an update check performed by the client produces information that is reported to the server and stored as the client's current update state.

The browser does not directly query the client's package manager.

---

## Package Search Path

Package search follows a different request/response flow:
En oppdateringskontroll som klienten utfører, produserer for eksempel informasjon som rapporteres til serveren og lagres som klientens gjeldende oppdateringstilstand.

Nettleseren spør ikke klientens pakkebehandler direkte.

---

## Pakkesøkvei

Pakkesøk følger en annen flyt for forespørsel og svar:

```text
Browser
   │
   │ search request
   ▼
LUMS Server
   │
   │ package-search request
   ▼
Linux Client
   │
   │ APT / pacman search
   ▼
Linux Client
   │
   │ search result
   ▼
LUMS Server
   │
   ▼
Browser
```

The server therefore does not need to maintain a complete remote package repository index for every client.

The search is performed using the client's own package-management environment.

---

## Update Execution Path
Serveren trenger derfor ikke å vedlikeholde en fullstendig ekstern pakkeregisterindeks for hver klient.

Søket utføres i klientens eget pakkeadministrasjonsmiljø.

---

## Veien for oppdateringskjøring

An update job follows the general architecture:

```text
Browser
   │
   │ create job
   ▼
LUMS API
   │
   │ validate request
   ▼
SQLite
   │
   │ persistent job
   ▼
Linux Client
   │
   │ execute action
   ▼
APT / dpkg / pacman
   │
   │ result
   ▼
Linux Client
   │
   │ validated result
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Browser
```

This creates the central LUMS execution chain:

> **Browser → API → SQLite → Agent → Package Manager → Result → SQLite → UI**

---

## Atomic Job Claiming

Update jobs are persistent server-side objects.

Before execution, the agent must obtain a job that is eligible for execution.
Dette skaper den sentrale LUMS-kjøringskjeden:

> **Browser → API → SQLite → Agent → Package Manager → Result → SQLite → UI**

---

## Atomisk jobbtildeling

Job claiming is performed atomically so that the same pending job is not unintentionally claimed by multiple execution paths.

This is particularly important when timers, retries, recovery, or multiple client-side processes are involved.

---

## Job Execution
Før kjøring må agenten få tak i en jobb som er kvalifisert for kjøring.

Jobbtildeling utføres atomisk, slik at den samme ventende jobben ikke utilsiktet tas av flere kjøringsveier.

Dette er spesielt viktig når tidtakere, nye forsøk, gjenoppretting eller flere prosesser på klientsiden er involvert.

---

## Jobbkjøring

The server creates structured jobs.

The client agent interprets the supported job actions and executes the corresponding local operation.

The supported package actions are:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Package names are validated before a package job is created.

The agent does not treat package names as arbitrary shell fragments.

---

## Package Management Abstraction

Package operations are deliberately implemented behind a package-manager abstraction.

This keeps the higher-level LUMS job model independent from distribution-specific commands.
Agenten behandler ikke pakkenavn som vilkårlige shell-fragmenter.

---

## Abstraksjon for pakkeadministrasjon

Pakkeoperasjoner er bevisst implementert bak en abstraksjon for pakkebehandlere.

Dette holder den overordnede LUMS-jobbmodellen uavhengig av distribusjonsspesifikke kommandoer.

For example:

```text
INSTALL_PACKAGE
       │
       ├── Debian / Ubuntu → APT
       │
       └── Arch Linux      → pacman
```

The same principle applies to removal and package updates.

---

## Debian / Ubuntu

On Debian-family systems, LUMS uses the native APT/dpkg tooling.

Typical responsibilities include:

* package search
* package metadata lookup
* package installation
* package removal
* package updates
* system updates
* update detection

The LUMS agent does not replace APT.

It provides controlled orchestration around it.
Det samme prinsippet gjelder fjerning og pakkeoppdateringer.

---

## Debian / Ubuntu

På Debian-baserte systemer bruker LUMS de native verktøyene APT/dpkg.

Typiske ansvarsområder omfatter:

* pakkesøk
* oppslag av pakkemetadata
* pakkeinstallasjon
* pakkefjerning
* pakkeoppdateringer
* systemoppdateringer
* oppdateringsregistrering

---

## Arch Linux

On Arch Linux systems, LUMS uses the native pacman package manager.

Typical responsibilities include:

* package search
* package metadata lookup
* package installation
* package removal
* package updates
* system updates
* update detection

Distribution-specific behavior remains inside the package-manager layer.

---

## Package Search

Package search is separate from the installed-software inventory.

This distinction is important:
Den gir kontrollert orkestrering rundt det.

---

## Arch Linux

På Arch Linux-systemer bruker LUMS den native pakkebehandleren pacman.

Typiske ansvarsområder omfatter:

* pakkesøk
* oppslag av pakkemetadata
* pakkeinstallasjon
* pakkefjerning
* pakkeoppdateringer
* systemoppdateringer
* oppdateringsregistrering

Distribusjonsspesifikk oppførsel forblir inne i pakkebehandlerlaget.

---

## Pakkesøk

Pakkesøk er atskilt fra inventaret over installert programvare.

Dette skillet er viktig:

```text
Installed Software
        │
        └── What is already installed?

Package Management Search
        │
        └── What package can the client currently find?
```

Search results may contain package information such as:

* package name
* version
* description
* repository information where available

Search results are returned to the LUMS server and displayed in the Package Management interface.

---

## Package Management Permissions
Søkeresultater kan inneholde pakkeinformasjon som:

* pakkenavn
* versjon
* beskrivelse
* depotinformasjon der det er tilgjengelig

Søkeresultater returneres til LUMS-serveren og vises i grensesnittet for pakkeadministrasjon.

---

## Tillatelser for pakkeadministrasjon

Package management is a privileged operation.

The current permission model is:
Den nåværende tillatelsesmodellen er:

```text
Administrator → allowed
Operator      → allowed
Viewer        → not allowed
```

A Viewer can still inspect installed software.

The Package Management interface itself is hidden for Viewers, and corresponding server-side mutation endpoints enforce authorization independently.

---

## Update Result Handling

LUMS treats the result of an update operation as structured state rather than simply displaying raw command output.

Relevant information can include:

* success or failure
* package-level result
* execution state
* error information
* reboot requirement
* completion timestamps

This allows the server to maintain a meaningful update history.

---

## Reboot Detection

After package operations, the client checks whether the operation indicates that a reboot is required.

The result is reported to the server as part of the job result.
Selve grensesnittet for pakkeadministrasjon er skjult for Viewers, og tilsvarende endepunkter for endringer på serversiden håndhever autorisasjon uavhengig.

---

## Håndtering av oppdateringsresultater

LUMS behandler resultatet av en oppdateringsoperasjon som strukturert tilstand i stedet for bare å vise rå kommandoutdata.

Relevant informasjon kan omfatte:

* suksess eller feil
* resultat per pakke
* kjøringstilstand
* feilinformasjon
* omstartsbehov
* tidsstempler for fullføring

Dette gjør at serveren kan vedlikeholde en meningsfull oppdateringshistorikk.

---

## Omstartsregistrering

A reboot requirement therefore remains associated with the update operation instead of being lost in a client-side terminal session.

---

## Client Authentication Boundary

The client API uses a separate authentication mechanism from administrative web sessions.
Resultatet rapporteres til serveren som en del av jobbresultatet.

Et omstartsbehov forblir dermed knyttet til oppdateringsoperasjonen i stedet for å gå tapt i en terminaløkt på klientsiden.

---

## Grense for klientautentisering

Klient-API-et bruker en annen autentiseringsmekanisme enn administrative webøkter.

```text
Administrative User
        │
        ▼
 Web Authentication
        │
        ▼
    LUMS Server

Linux Client
        │
        ▼
 Client Token
        │
        ▼
    LUMS Server
```

This separation prevents administrative browser sessions and client credentials from becoming interchangeable authentication mechanisms.

---

## Audit Trail

Security-relevant and administrative actions are recorded by the server-side audit system.
Denne separasjonen hindrer at administrative nettleserøkter og klientlegitimasjon blir utskiftbare autentiseringsmekanismer.

---

## Revisjonsspor

The audit trail complements normal application logging.

Logging answers questions about application behavior.

Audit logging additionally records important administrative actions and their context.

This distinction is useful when investigating changes to clients, users, authentication state, or update jobs.

---

## Operational Principle

LUMS deliberately separates:
Logging svarer på spørsmål om applikasjonens oppførsel.

Revisjonslogging registrerer i tillegg viktige administrative handlinger og konteksten rundt dem.

Dette skillet er nyttig ved undersøkelse av endringer i klienter, brukere, autentiseringstilstand eller oppdateringsjobber.

---

## Driftsprinsipp

LUMS skiller bevisst mellom:

```text
Management
     │
     ▼
Policy / Authorization
     │
     ▼
Job
     │
     ▼
Client Execution
     │
     ▼
Native Package Manager
```

Each layer has a defined responsibility.

The server manages.

The agent executes.

The package manager performs the actual system change.

The result travels back through the same controlled chain.

## Role-Based Access Control
Pakkebehandleren gjør selve systemendringen.

Resultatet går tilbake gjennom den samme kontrollerte kjeden.

## Rollebasert tilgangskontroll

LUMS uses three administrative roles:

```text
Administrator
Operator
Viewer
```

Authorization is enforced server-side.

The frontend additionally adapts the visible interface to the user's
permissions, but frontend visibility is never considered a security boundary.

### Administrator

Administrators have access to:

* view clients
* view installed software
* view available updates
* create and execute update jobs
* view update history
* use package management
* perform system maintenance
* create and disable clients
* rotate client tokens
* create and manage users
* manage roles and user access

### Operator

Operators have access to:

* view clients
* view installed software
* view available updates
* create and execute update jobs
* view update history
* use package management
* perform system maintenance

Operators do not have access to:

* user management
* role administration
* client creation or disabling
* client-token rotation

### Viewer

Viewers have read-only access to:

* clients
* installed software

The following functionality is unavailable to Viewers:

* available-update management
* update jobs
* update history
* package management
* system maintenance
* other state-changing administrative operations

The server independently enforces these restrictions.

---
Autorisasjon håndheves på serversiden.

Frontend tilpasser i tillegg det synlige grensesnittet til brukerens
tillatelser, men synlighet i frontend regnes aldri som en sikkerhetsgrense.

### Administrator

Administratorer har tilgang til å:

* se klienter
* se installert programvare
* se tilgjengelige oppdateringer
* opprette og kjøre oppdateringsjobber
* se oppdateringshistorikk
* bruke pakkeadministrasjon
* utføre systemvedlikehold
* opprette og deaktivere klienter
* rotere klienttokener
* opprette og administrere brukere
* administrere roller og brukertilgang

### Operator

Operatorer har tilgang til å:

* se klienter
* se installert programvare
* se tilgjengelige oppdateringer
* opprette og kjøre oppdateringsjobber
* se oppdateringshistorikk
* bruke pakkeadministrasjon
* utføre systemvedlikehold

Operatorer har ikke tilgang til:

* brukeradministrasjon
* rolleadministrasjon
* oppretting eller deaktivering av klienter
* rotasjon av klienttokener

### Viewer

Viewere har skrivebeskyttet tilgang til:

* klienter
* installert programvare

Følgende funksjonalitet er utilgjengelig for Viewere:

* administrasjon av tilgjengelige oppdateringer
* oppdateringsjobber
* oppdateringshistorikk
* pakkeadministrasjon
* systemvedlikehold
* andre tilstandsendrende administrative operasjoner

Serveren håndhever disse begrensningene uavhengig.

---

## Brukeradministrasjon

LUMS tilbyr brukeradministrasjon til kontoer med tillatelsen `users.manage`.

Brukere med denne tillatelsen kan opprette kontoer med en rollemal og deretter
tildele tillatelser enkeltvis eller eksplisitt bruke malen. Nye kontoer starter
uten tillatelser; tillatelseseditoren åpnes etter opprettelsen.
Brukeradministratorer kan også lagre private administrative notater som ikke er
synlige for kontoeieren.

Administratorer med `backups.manage` kan opprette validerte
databasesikkerhetskopier i formatene `.db` eller `.db.gz` i en katalog som er
konfigurert på serveren, og velge en trygg undermappe innenfor denne monterte
plasseringen. Se [`administrasjon og sikkerhetskopier`](<Administrasjon og sikkerhetskopier.md>) og
gjenopprettingsveiledningen i Markdown i appen for oppsett av Docker-lagring og
gjenoppretting.

Brukerpassord lagres med Argon2-passordhashing, ikke i klartekst eller med reversibel kryptering.

## User Management

LUMS provides user management to accounts with the `users.manage` permission.

Users with this permission can create accounts using a role template and
then assign permissions individually or explicitly apply that template. New
accounts start without permissions; the permission editor opens after creation.
User managers can also save private administrative notes that are not visible
to the account owner.

Administrators with `backups.manage` can create validated `.db` or `.db.gz`
database backups in a server-configured directory and choose a safe subfolder
within that mounted location. See [`administration.md`](administration.md) and
the in-app Markdown restore guide for Docker storage setup and recovery.

User passwords are stored using Argon2 password hashing rather than plaintext or reversible encryption.

User-management operations are protected by:

* authentication
* permission-based authorization
* CSRF protection
* input validation
* duplicate-user checks
* audit logging

The user-management interface is not exposed without `users.manage`.
* autentisering
* tillatelsesbasert autorisasjon
* CSRF-beskyttelse
* inndatavalidering
* kontroll av duplikate brukere
* revisjonslogging

Brukeradministrasjonsgrensesnittet eksponeres ikke uten `users.manage`.

---

## Øktsikkerhet

---

## Session Security

Administrative authentication uses server-side session handling.

Session security includes:

* authenticated session state
* session revocation
* CSRF protection for state-changing requests
* login rate limiting
* disabled-account enforcement
* role checks

Revoking a session invalidates the corresponding authenticated state rather than merely hiding the user interface.

---

## Login Rate Limiting

Repeated failed login attempts are subject to progressive rate limiting.

The current thresholds are:
Øktsikkerheten omfatter:

* autentisert øktstatus
* tilbakekalling av økter
* CSRF-beskyttelse for tilstandsendrende forespørsler
* begrensning av påloggingsforsøk
* håndheving av deaktiverte kontoer
* rollekontroller

Tilbakekalling av en økt ugyldiggjør den tilsvarende autentiserte tilstanden i stedet for bare å skjule brukergrensesnittet.

---

## Begrensning av påloggingsforsøk

Gjentatte mislykkede påloggingsforsøk er underlagt progressiv begrensning.

De nåværende grensene er:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

The relevant state is persisted in SQLite.

Successful authentication clears the applicable failure state.

This prevents a simple application restart from being used to bypass the login protection.
Den relevante tilstanden lagres vedvarende i SQLite.

Vellykket autentisering fjerner den gjeldende feiltilstanden.

Dette hindrer at en enkel omstart av applikasjonen kan brukes til å omgå påloggingsbeskyttelsen.

---

## Sikkerhet for klienttokener

---

## Client Token Security

Each registered client has its own authentication token.

The server stores the token as a SHA-256 digest.

The original token is not required for normal server-side validation.
Serveren lagrer tokenet som en SHA-256-digest.

Det opprinnelige tokenet er ikke nødvendig for vanlig validering på serversiden.

Token rotation allows administrators to invalidate an existing credential and issue a replacement.

This creates a clear lifecycle:
Dette gir en tydelig livssyklus:

```text
Create
  │
  ▼
Use
  │
  ▼
Rotate
  │
  ▼
Old token invalid
```

---

## API Security

LUMS validates API input before performing state-changing operations.

Security controls include:

* authentication
* per-user permission authorization
* CSRF protection where applicable
* input validation
* package-name validation
* structured job actions
* parameterized database queries
* controlled error handling
## API-sikkerhet

LUMS validerer API-inndata før tilstandsendrende operasjoner utføres.

Sikkerhetskontrollene omfatter:

* autentisering
* autorisasjon med tillatelser per bruker
* CSRF-beskyttelse der det er aktuelt
* inndatavalidering
* validering av pakkenavn
* strukturerte jobbhandlinger
* parameteriserte databasespørringer
* kontrollert feilhåndtering

Applikasjonen bruker ikke brukerleverte pakkenavn som ubegrensede shell-kommandoer.

---

## Beskyttelse mot SQL-injeksjon

The application does not use user-provided package names as unrestricted shell commands.

---
Verdier som brukeren kontrollerer, settes ikke direkte sammen med SQL-spørringer.

## SQL Injection Protection

Database operations use parameterized SQL statements.

User-controlled values are not directly concatenated into SQL queries.

This applies to areas such as:

* authentication
* client management
* user management
* package searches
* update jobs
* audit data
* result reporting

The goal is to keep data values separate from SQL instructions.

---

## SQLite Security Baseline

The current production SQLite configuration is:
* autentisering
* klientadministrasjon
* brukeradministrasjon
* pakkesøk
* oppdateringsjobber
* revisjonsdata
* resultatrapportering

Målet er å holde dataverdier atskilt fra SQL-instruksjoner.

---

## SQLite-sikkerhetsgrunnlinje

Den nåværende SQLite-konfigurasjonen for produksjon er:

```text
journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

Foreign-key enforcement is explicitly enabled by the application for database connections.

The current configuration uses WAL mode.

The database is stored in the persistent Docker volume rather than inside the disposable application container filesystem.

---

## Job Recovery and Checkpointing
Håndheving av fremmednøkler aktiveres eksplisitt av applikasjonen for databasetilkoblinger.

Den nåværende konfigurasjonen bruker WAL-modus.

Databasen lagres i det vedvarende Docker-volumet, ikke i filsystemet til den utskiftbare applikasjonscontaineren.

---

## Jobbgjenoppretting og kontrollpunkter

LUMS treats update jobs as persistent state machines.

A multi-package job may contain several individual package operations.
En jobb med flere pakker kan inneholde flere enkeltstående pakkeoperasjoner.

Each package item can reach its own result state.

If execution is interrupted, recovery can distinguish between:
Hvis kjøringen avbrytes, kan gjenopprettingen skille mellom:

```text
already successful
        │
        └── do not unnecessarily repeat

not completed
        │
        └── eligible for recovery
```

This reduces the risk of blindly repeating completed package operations after an interruption.

---

## Controlled Update Execution

LUMS deliberately limits the actions that can be requested through the update-job API.
Dette reduserer risikoen for å gjenta fullførte pakkeoperasjoner blindt etter et avbrudd.

---

## Kontrollert oppdateringskjøring

LUMS begrenser bevisst handlingene som kan etterspørres gjennom API-et for oppdateringsjobber.

Supported actions are:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

The server validates the action and relevant package information before creating the job.

The agent then maps the structured action to the appropriate package-manager operation.

This avoids turning the update system into a generic remote-command execution mechanism.

---

## Package Operations

Package operations are executed through the native package manager of the client.

### Installation

A validated package name is passed to the package-manager abstraction for installation.

### Removal

A validated package name is passed to the package-manager abstraction for removal.

### Package Update

A specific package can be updated when the client reports it as an available update.

### System Update

The system update operation delegates the update process to the native package manager.

All operations return structured results to the LUMS server.

---

## Package Manager Safety

LUMS treats the package manager as a privileged local component.

The agent therefore does not attempt to emulate package-manager behavior itself.

Instead, it:

1. validates the requested operation
2. selects the appropriate package-manager implementation
3. executes the controlled operation
4. captures the result
5. reports the result to the server

Distribution-specific behavior remains isolated inside the package-manager layer.

---

## Reboot Handling
Agenten kobler deretter den strukturerte handlingen til riktig pakkebehandleroperasjon.

Dette unngår at oppdateringssystemet blir en generell mekanisme for kjøring av eksterne kommandoer.

---

## Pakkeoperasjoner

Pakkeoperasjoner utføres gjennom klientens native pakkebehandler.

### Installasjon

Et validert pakkenavn sendes til abstraksjonen for pakkebehandlere for installasjon.

### Fjerning

Et validert pakkenavn sendes til abstraksjonen for pakkebehandlere for fjerning.

### Pakkeoppdatering

En bestemt pakke kan oppdateres når klienten rapporterer den som en tilgjengelig oppdatering.

### Systemoppdatering av klient

Systemoppdateringsoperasjonen overlater oppdateringsprosessen til den native pakkebehandleren.

Alle operasjoner returnerer strukturerte resultater til LUMS-serveren.

---

## Sikkerhet for pakkebehandleren

LUMS behandler pakkebehandleren som en privilegert lokal komponent.

Agenten forsøker derfor ikke selv å etterligne pakkebehandlerens oppførsel.

I stedet:

1. validerer den den forespurte operasjonen
2. velger den riktig implementasjon av pakkebehandleren
3. utfører den den kontrollerte operasjonen
4. fanger den opp resultatet
5. rapporterer den resultatet til serveren

Distribusjonsspesifikk oppførsel forblir isolert inne i pakkebehandlerlaget.

---

## Håndtering av omstart

Some package operations may require a reboot.

LUMS records reboot requirements as part of update-job results.

This allows administrators to distinguish between:
LUMS registrerer omstartsbehov som en del av resultatene for oppdateringsjobber.

Dette gjør at administratorer kan skille mellom:

```text
Update completed
```

and:

```text
Update completed
Reboot required
```

The reboot requirement is therefore part of the operational state rather than being treated as an unrelated notification.

---

## Audit Logging

LUMS maintains an application audit trail for important administrative and security-relevant actions.
Omstartsbehovet er dermed en del av den operative tilstanden i stedet for å bli behandlet som en urelatert melding.

---

## Revisjonslogging

LUMS opprettholder et revisjonsspor i applikasjonen for viktige administrative og sikkerhetsrelevante handlinger.

Eksempler omfatter:

* autentiseringsrelaterte hendelser
* klientadministrasjon
* tokenoperasjoner
* brukeradministrasjon
* opprettelse av oppdateringsjobber
* sikkerhetssensitive tilstandsendringer

Examples include:

* authentication-related events
* client management
* token operations
* user management
* update-job creation
* security-sensitive state changes

Audit logging is separate from ordinary diagnostic logging.

Diagnostic logs help troubleshoot the application.

Audit records provide an administrative history of relevant actions.

---

## Security Hardening

The current deployment includes multiple layers of hardening.

### Container Hardening

The production container uses:

* non-root application execution
* read-only root filesystem
* dropped Linux capabilities
* `no-new-privileges`
* restricted temporary filesystems
* read-only secret mount
* dedicated persistent data volume

### Network Hardening

The application container is bound to loopback on the host:
Revisjonsposter gir en administrativ historikk over relevante handlinger.

---

## Sikkerhetsherding

Den nåværende distribusjonen omfatter flere lag med herding.

### Containerherding

Produksjonscontaineren bruker:

* kjøring av applikasjonen som ikke-root
* skrivebeskyttet rotfilsystem
* fjernede Linux-capabilities
* `no-new-privileges`
* begrensede midlertidige filsystemer
* skrivebeskyttet montering av hemmeligheter
* dedikert volum for vedvarende data

### Nettverksherding

Applikasjonscontaineren er bundet til loopback på verten:

```text
127.0.0.1:5050
```

The application port is therefore not directly exposed as a LAN service.

External access is handled through the HTTPS reverse proxy.

The firewall does not expose the internal application port.

### Transport Security

Administrative access is provided through HTTPS.

The reverse proxy handles external TLS termination.

HTTP requests are redirected to HTTPS.

### Secrets and Configuration

Sensitive runtime credentials are kept outside the application source tree.

The production secret is mounted into the container as a read-only secret file.

Repository and Docker build context rules prevent common backup, secret, database, and certificate artifacts from unintentionally entering the image build context.

### Dependency and Build Security

The production Python dependencies are pinned.

The production Python base image is pinned by digest.

The Docker build context is restricted through `.dockerignore`.

These controls improve build reproducibility and reduce accidental inclusion of sensitive files.

---

## Security Audit Status

The LUMS security review has covered the following areas:

* SQLite foreign-key enforcement
* SQLite runtime configuration
* update timeout and process handling
* login rate limiting
* API input validation
* session revocation
* client-token rotation
* offline/IP handling
* job recovery and checkpointing
* APT robustness
* Arch reboot detection
* unit and API result validation
* simulation testing
* continuous integration
* application and audit logging
* versioning and release handling
* RBAC
* session and CSRF security
* credential security
* dependency and build security
* Docker/container hardening
* secrets and build-context protection
* HTTP/transport security
* filesystem/runtime permissions
* network exposure
* repository artifact hygiene

The remaining documentation review is handled separately as part of the final release-readiness process.

---

## Testting og CI

LUMS includes automated tests covering core application behavior and security controls.

Run the complete test suite from the repository root:
Applikasjonsporten eksponeres derfor ikke direkte som en LAN-tjeneste.

Ekstern tilgang håndteres gjennom HTTPS-reverse proxyen.

Brannmuren eksponerer ikke den interne applikasjonsporten.

### Transportsikkerhet

Administrativ tilgang gis gjennom HTTPS.

Reverse proxyen håndterer ekstern TLS-terminering.

HTTP-forespørsler omdirigeres til HTTPS.

### Hemmeligheter og konfigurasjon

Sensitiv kjøretidslegitimasjon holdes utenfor applikasjonens kildetre.

Produksjonshemmeligheten monteres i containeren som en skrivebeskyttet hemmelighetsfil.

Regler for repositoryet og Docker-byggekonteksten hindrer at vanlige sikkerhetskopi-, hemmelighets-, database- og sertifikatartefakter utilsiktet havner i bildebyggets kontekst.

### Sikkerhet for avhengigheter og bygg

Python-avhengighetene for produksjon er festet til bestemte versjoner.

Python-basebildet for produksjon er festet med digest.

Docker-byggekonteksten er begrenset gjennom `.dockerignore`.

Disse kontrollene forbedrer reproduserbarheten av bygg og reduserer utilsiktet inkludering av sensitive filer.

---

## Status for sikkerhetsrevisjon

Sikkerhetsgjennomgangen av LUMS har dekket følgende områder:

* håndheving av fremmednøkler i SQLite
* SQLite-kjøretidskonfigurasjon
* tidsavbrudd og prosesshåndtering ved oppdateringer
* begrensning av påloggingsforsøk
* validering av API-inndata
* tilbakekalling av økter
* rotasjon av klienttokener
* håndtering av frakoblet status og IP-adresser
* jobbgjenoppretting og kontrollpunkter
* robusthet i APT
* registrering av omstart på Arch
* validering av enhets- og API-resultater
* simuleringstesting
* kontinuerlig integrasjon
* applikasjons- og revisjonslogging
* versjonering og utgivelseshåndtering
* RBAC
* økt- og CSRF-sikkerhet
* sikkerhet for legitimasjon
* sikkerhet for avhengigheter og bygg
* herding av Docker/containere
* beskyttelse av hemmeligheter og byggekontekst
* HTTP-/transportsikkerhet
* filsystem- og kjøretidstillatelser
* nettverkseksponering
* hygiene for artefakter i repositoryet

Å holde dokumentasjonen i samsvar med implementeringen er løpende vedlikehold, ikke en separat utgivelsesport.

---

## Testing og CI

LUMS inneholder automatiserte tester som dekker sentral applikasjonsoppførsel og sikkerhetskontroller.

Kjør hele testsuiten fra repositoryets rotkatalog:

```bash
./.venv-test/bin/pytest -q
```

The number of tests changes over time. The required result is that the complete
suite finishes successfully with no failures. The test suite includes coverage
for areas such as:

* authentication
* RBAC
* client management
* user management
* package search
* update jobs
* job-result validation
* security behavior
* API behavior

Continuous integration executes the automated test suite before changes are considered ready.

A successful test run is required, but tests are only one part of the release process.

The release process also requires:
Antallet tester endres over tid. Det påkrevde resultatet er at hele suiten
fullføres vellykket uten feil. Testsuiten inkluderer dekning for områder som:

* autentisering
* RBAC
* klientadministrasjon
* brukeradministrasjon
* pakkesøk
* oppdateringsjobber
* validering av jobbresultater
* sikkerhetsoppførsel
* API-oppførsel

Kontinuerlig integrasjon kjører den automatiserte testsuiten før endringer anses som klare.

En vellykket testkjøring er påkrevd, men tester er bare én del av utgivelsesprosessen.

Utgivelsesprosessen krever også:

```text
Implementation
    ↓
Security Review
    ↓
Documentation Review
    ↓
Full Test Suite
    ↓
CI
    ↓
Version
    ↓
Git Tag
    ↓
GitHub Release
```

---

## Development Status

LUMS is currently in active development.

The core management architecture, client execution model, package management, RBAC, security hardening, and recovery mechanisms are implemented.
## Utviklingsstatus

The project is intentionally not considered a finished release merely because the application is functional.

Release readiness also requires the surrounding documentation and operational procedures to describe the same current system.

This is why documentation consistency is treated as part of the engineering process rather than as an afterthought.
Den sentrale administrasjonsarkitekturen, klientens kjøringsmodell, pakkeadministrasjon, RBAC, sikkerhetsherding og gjenopprettingsmekanismer er implementert.

Prosjektet regnes bevisst ikke som en ferdig utgivelse bare fordi applikasjonen fungerer.

## Støttede systemer

LUMS is designed to manage Linux systems using supported native package managers.

### Debian / Ubuntu

Supported package-management stack:
Derfor behandles dokumentasjonskonsistens som en del av ingeniørprosessen, ikke som en ettertanke.

## Støttede systemer

LUMS er utformet for å administrere Linux-systemer som bruker støttede native pakkebehandlere.

### Debian / Ubuntu

Støttet stack for pakkeadministrasjon:

```text
APT
dpkg
```

The client uses the native Debian package-management tooling for:

* package inventory
* update detection
* package search
* package installation
* package removal
* package updates
* system updates

### Arch Linux

Supported package-management stack:
Klienten bruker de native Debian-verktøyene for pakkeadministrasjon til:

* pakkeinventar
* oppdateringsregistrering
* pakkesøk
* pakkeinstallasjon
* pakkefjerning
* pakkeoppdateringer
* systemoppdateringer

### Arch Linux

Støttet stack for pakkeadministrasjon:

```text
pacman
```

The client uses the native Arch package-management tooling for:

* package inventory
* update detection
* package search
* package installation
* package removal
* package updates
* system updates

---

## Client Requirements

A managed Linux client requires:

* a supported Linux distribution
* the LUMS agent
* network connectivity to the LUMS server
* a registered client token
* a working native package manager
* systemd for the timer/service-based execution components

The client does not require the LUMS server to directly access its package database.

The client performs local package operations and reports the results to the server.

---

## Teknologistakk

Klienten bruker de native Arch-verktøyene for pakkeadministrasjon til:

* pakkeinventar
* oppdateringsregistrering
* pakkesøk
* pakkeinstallasjon
* pakkefjerning
* pakkeoppdateringer
* systemoppdateringer

---

## Klientkrav

En administrert Linux-klient krever:

* en støttet Linux-distribusjon
* LUMS-agenten
* nettverkstilkobling til LUMS-serveren
* et registrert klienttoken
* en fungerende native pakkebehandler
* systemd for de tidtaker-/tjenestebaserte kjøringskomponentene

Klienten krever ikke at LUMS-serveren har direkte tilgang til pakkedatabasen dens.

Klienten utfører lokale pakkeoperasjoner og rapporterer resultatene til serveren.

---

## Teknologistack

### Server

* Python
* Flask
* Gunicorn
* SQLite
* HTML
* CSS
* JavaScript
* Nginx
* Docker

### Authentication and Security

* Argon2 password hashing
* server-side sessions
* CSRF protection
* role templates with per-user permissions
* SHA-256 client-token digests
* HTTPS
* audit logging

### Client
### Autentisering og sikkerhet

* Argon2-passordhashing
* økter på serversiden
* CSRF-beskyttelse
* rollemaler med tillatelser per bruker
* SHA-256-digester av klienttokener
* HTTPS
* revisjonslogging

### Klient

* Python
* systemd
* APT / dpkg
* pacman
* `loginctl` where idle-state information is available
* `loginctl` der informasjon om inaktivitetstilstand er tilgjengelig

---

## Prosjektstruktur

The repository is organized into separate server, client, frontend, and test components.
Repositoryet er organisert i separate komponenter for server, klient, frontend og tester.

A simplified structure is:

```text id="1rq7v7"
LUMS/
├── agent/
│   ├── agent.py
│   └── package_manager.py
│
├── server/
│   ├── app.py
│   ├── migrations/
│   ├── static/
│   ├── templates/
│   └── ...
│
├── tests/
│   ├── test_rbac.py
│   ├── test_package_search.py
│   ├── test_job_result.py
│   └── ...
│
├── Dockerfile
├── docker-entrypoint.sh
├── .dockerignore
├── .gitignore
└── documentation
```

The exact repository layout may evolve as LUMS develops.

The architectural separation between server, agent, package-manager abstraction, frontend, and tests is intentional.

---

## Server Application

The Flask application provides the central LUMS API and web interface.

Its responsibilities include:

* authentication
* authorization
* session handling
* client management
* user management
* software inventory
* update inventory
* package search
* update jobs
* job-result handling
* audit logging
* database persistence

The application is served by Gunicorn inside the container.

Nginx provides the external HTTPS entry point.
Den nøyaktige strukturen i repositoryet kan utvikle seg etter hvert som LUMS utvikles.

Den arkitektoniske separasjonen mellom server, agent, abstraksjon for pakkebehandlere, frontend og tester er bevisst.

---

## Serverapplikasjon

Flask-applikasjonen tilbyr det sentrale LUMS-API-et og nettgrensesnittet.

Ansvarsområdene omfatter:

* autentisering
* autorisasjon
* økthåndtering
* klientadministrasjon
* brukeradministrasjon
* programvareinventar
* oppdateringsinventar
* pakkesøk
* oppdateringsjobber
* håndtering av jobbresultater
* revisjonslogging
* databasepersistens

---

Nginx er det eksterne HTTPS-inngangspunktet.

---

## Agent

The LUMS agent is installed directly on managed Linux clients.

Current agent version:

```text id="w8p4wz"
1.7.0
```

The agent is responsible for the client-side part of the LUMS execution chain.

Its responsibilities include:

* reporting client state
* collecting installed software
* detecting available updates
* searching packages
* executing package operations
* reporting job results
* detecting reboot requirements
* handling idle-state information
* participating in job recovery

The agent does not provide an unrestricted remote shell.

---

## Package Manager Layer

The package-manager implementation isolates distribution-specific behavior from the rest of the agent.
Agenten er ansvarlig for klientsiden av LUMS-kjøringskjeden.

Ansvarsområdene omfatter:

* rapportering av klienttilstand
* innsamling av installert programvare
* registrering av tilgjengelige oppdateringer
* søk etter pakker
* utføring av pakkeoperasjoner
* rapportering av jobbresultater
* registrering av omstartsbehov
* håndtering av informasjon om inaktivitetstilstand
* deltakelse i jobbgjenoppretting

Agenten tilbyr ikke et ubegrenset eksternt shell.

---

## Pakkebehandlerlag

Implementasjonen av pakkebehandleren isolerer distribusjonsspesifikk oppførsel fra resten av agenten.

Conceptually:

```text id="zq8xq3"
Agent
  │
  ▼
Package Manager Interface
  │
  ├── Debian / Ubuntu
  │      └── APT / dpkg
  │
  └── Arch Linux
         └── pacman
```

This allows the higher-level update-job system to work with structured operations without needing to know every distribution-specific command.
Dette lar det overordnede systemet for oppdateringsjobber arbeide med strukturerte operasjoner uten å måtte kjenne hver distribusjonsspesifikke kommando.

---

## Watcher

The LUMS execution watcher monitors jobs that are expected to execute on the client.

Current watcher version:
LUMS-kjøringsvakten (watcher) overvåker jobber som forventes å bli utført på klienten.

Gjeldende watcher-versjon:

```text id="7k6w3s"
1.2.1
```

The watcher operates together with the agent and server-side job state.

This architecture allows LUMS to detect execution situations where a job remains pending or otherwise requires attention.

---

## systemd Integration

The client uses systemd for scheduled and controlled execution.

Relevant components include service and timer units for:

* client reporting
* update detection
* job execution/watching

This provides predictable execution without requiring a continuously running foreground process for every periodic operation.

The client agent can also be executed manually during installation and troubleshooting.
Watcheren fungerer sammen med agenten og jobbtilstanden på serversiden.

Denne arkitekturen gjør at LUMS kan oppdage kjøringssituasjoner der en jobb blir stående som ventende eller på annen måte krever oppmerksomhet.

---

## systemd-integrasjon

Klienten bruker systemd for planlagt og kontrollert kjøring.

Relevante komponenter omfatter service- og timer-enheter for:

* klientrapportering
* oppdateringsregistrering
* jobbkjøring/overvåking

---

## Idle-Aware Execution

Idle-aware execution is designed to reduce interference with active users.

The current idle threshold is:
Klientagenten kan også kjøres manuelt under installasjon og feilsøking.

---

## Inaktivitetsbevisst kjøring

Inaktivitetsbevisst kjøring er utformet for å redusere forstyrrelser for aktive brukere.

Den nåværende inaktivitetsgrensen er:

```text id="g8v0lq"
300 seconds
```

The client determines idle state using the available local session information.

Where supported, `loginctl` is used.
Klienten fastslår inaktivitetstilstand ut fra tilgjengelig lokal øktinformasjon.

Der det støttes, brukes `loginctl`.

The agent distinguishes between:

```text id="6v3m4k"
confirmed idle
active
idle state unavailable
```

An unavailable idle state is not silently interpreted as idle.

This makes the execution decision explicit and diagnosable.

---

## Update Job Lifecycle

The complete lifecycle of an update job can be represented as:
En utilgjengelig inaktivitetstilstand tolkes ikke stilltiende som inaktiv.

Dette gjør kjøringsbeslutningen eksplisitt og mulig å diagnostisere.

---

## Livssyklus for oppdateringsjobber

Den fullstendige livssyklusen til en oppdateringsjobb kan representeres slik:

```text id="h4d9kv"
Create
  │
  ▼
Validate
  │
  ▼
Persist
  │
  ▼
Claim
  │
  ▼
Execute
  │
  ├──────────────► SUCCESS
  │
  ├──────────────► FAILED
  │
  └──────────────► RECOVERY
                         │
                         ▼
                      Execute
```

A job is persisted before execution.

This means the server retains knowledge of the intended operation even if the client or application is interrupted.

---

## Job Types

LUMS currently supports structured update actions including:
En jobb lagres vedvarende før kjøring.

Dette betyr at serveren beholder kunnskap om den tiltenkte operasjonen selv om klienten eller applikasjonen blir avbrutt.

---

## Jobbtyper

LUMS støtter for tiden strukturerte oppdateringshandlinger, blant annet:

```text id="v7r1f8"
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

These actions are intentionally limited.

LUMS is an update-management system, not a general-purpose remote-command framework.

---

## Package-Level Job State

Jobs containing multiple packages can track package-level progress.
LUMS er et system for oppdateringsadministrasjon, ikke et generelt rammeverk for eksterne kommandoer.

---

## Jobbtilstand på pakkenivå

Jobber med flere pakker kan spore fremdrift på pakkenivå.

For example:

```text id="v9w1sh"
Job #42

package-a → SUCCESS
package-b → SUCCESS
package-c → FAILED
package-d → PENDING
```

Recovery can therefore operate on the incomplete portions of the job rather than blindly repeating successful package operations.

---

## Job Recovery

Recovery is designed around persistent checkpoints.
Gjenoppretting kan dermed virke på de ufullførte delene av jobben i stedet for å gjenta vellykkede pakkeoperasjoner blindt.

---

## Jobbgjenoppretting

Gjenoppretting er utformet rundt vedvarende kontrollpunkter.

Serveren opprettholder jobbtilstanden.

The server maintains the job state.

The client reports package-level results.
Hvis kjøringen avbrytes, kan serveren avgjøre hvilket arbeid som allerede er fullført, og hvilket som fortsatt er kvalifisert for gjenoppretting.

If execution is interrupted, the server can determine which work has already completed and which work remains eligible for recovery.

The intended recovery principle is:

> **Continue from known state instead of assuming that nothing happened.**

---
> **Fortsett fra kjent tilstand i stedet for å anta at ingenting skjedde.**

---

## Resultatvalidering

Klientens jobbresultater valideres før de godtas i den vedvarende serverstatus.

## Result Validation

Client job results are validated before being accepted into persistent server state.

This protects the job state from malformed or incomplete result submissions.

Validation is applied to relevant fields such as:

* job identity
* execution state
* package result data
* error information
* reboot information

The result-processing layer therefore acts as another boundary between an authenticated client and persistent server state.

---

## User Management

User management requires the `users.manage` permission.

Authorized users can create users from a role template and customize the
individual permissions assigned to each account.

The current roles are:
* jobbidentitet
* kjøringstilstand
* resultatdata per pakke
* feilinformasjon
* omstartsinformasjon

Resultatbehandlingslaget fungerer dermed som enda en grense mellom en autentisert klient og vedvarende serverstatus.

---

## Brukeradministrasjon

Brukeradministrasjon krever tillatelsen `users.manage`.

Autoriserte brukere kan opprette brukere fra en rollemal og tilpasse de
individuelle tillatelsene som er tildelt hver konto.

De nåværende rollene er:

```text id="2xqv79"
Administrator
Operator
Viewer
```

User-management actions are authenticated, permission-checked, validated,
protected against CSRF where applicable, and recorded in the audit trail.

---

## Client Management

Administrators can manage registered clients.

Client-management functions include:

* registration
* disabling
* token rotation
* client status inspection
Handlinger i brukeradministrasjonen autentiseres, tillatelseskontrolleres,
valideres, beskyttes mot CSRF der det er aktuelt, og registreres i
revisjonssporet.

---

## Klientadministrasjon

Administratorer kan administrere registrerte klienter.

Funksjoner for klientadministrasjon omfatter:

* registrering
* deaktivering
* tokenrotasjon
* inspeksjon av klientstatus

Client authentication is independent for every registered client.

Disabling a client prevents it from continuing normal authenticated communication with the server.

---

## Update History

LUMS maintains persistent update-job state so that completed and failed operations remain visible after execution.

Authorized users can inspect the history of update operations according to their role.

The history is intended to provide operational context rather than merely showing the latest package inventory.

---

## Auditability

LUMS maintains two related but distinct forms of operational information:

### Application Logs

Used primarily for:

* diagnostics
* errors
* runtime behavior
* troubleshooting

### Audit Logs

Used primarily for:

* administrative actions
* security-relevant events
* changes to important state
* accountability

Keeping these concepts separate makes troubleshooting and administrative review easier.

---

## Testing Strategy

The LUMS test suite covers multiple layers of the application.

### Authentication

Tests cover authentication behavior, session handling, and security controls.

### RBAC

Tests verify that:

* Administrators can perform administrative actions
* Operators receive their permitted management functions
* Viewers remain read-only

### Package Management

Tests cover package-search behavior and package-management-related API handling.

### Update Jobs

Tests cover:

* job creation
* validation
* state transitions
* result handling
* recovery behavior

### Security

Tests cover security-sensitive application behavior and regression cases.

### Full Suite

Run the complete test suite from the repository root:
Deaktivering av en klient hindrer den i å fortsette normal autentisert kommunikasjon med serveren.

---

## Oppdateringshistorikk

LUMS opprettholder vedvarende tilstand for oppdateringsjobber slik at fullførte og mislykkede operasjoner forblir synlige etter kjøring.

Autoriserte brukere kan inspisere historikken over oppdateringsoperasjoner i samsvar med rollen sin.

Historikken er ment å gi driftskontekst, ikke bare vise det siste pakkeinventaret.

---

## Revisjonsevne

LUMS opprettholder to beslektede, men atskilte former for driftsinformasjon:

### Applikasjonslogger

Brukes først og fremst til:

* diagnostikk
* feil
* kjøretidsoppførsel
* feilsøking

### Revisjonslogger

Brukes først og fremst til:

* administrative handlinger
* sikkerhetsrelevante hendelser
* endringer i viktig tilstand
* ansvarlighet

Å holde disse begrepene atskilt gjør feilsøking og administrativ gjennomgang enklere.

---

## Teststrategi

LUMS-testsuiten dekker flere lag av applikasjonen.

### Autentisering

Testene dekker autentiseringsoppførsel, økthåndtering og sikkerhetskontroller.

### RBAC

Testene verifiserer at:

* Administratorer kan utføre administrative handlinger
* Operatorer får de administrasjonsfunksjonene de har tillatelse til
* Viewere forblir skrivebeskyttet

### Pakkeadministrasjon

Testene dekker oppførsel for pakkesøk og API-håndtering knyttet til pakkeadministrasjon.

### Oppdateringsjobber

Testene dekker:

* opprettelse av jobber
* validering
* tilstandsoverganger
* resultathåndtering
* gjenopprettingsoppførsel

### Sikkerhet

Testene dekker sikkerhetssensitiv applikasjonsoppførsel og regresjonstilfeller.

### Hele suiten

Kjør hele testsuiten fra repositoryets rotkatalog:

```bash
./.venv-test/bin/pytest -q
```

The test count changes as the project evolves; rely on the command's result,
not a fixed number printed in this document.

---

## Continuous Integration

The project uses continuous integration to run automated checks against changes.

The CI pipeline helps detect regressions before changes are treated as release-ready.
Antallet tester endres etter hvert som prosjektet utvikler seg; stol på
kommandoens resultat, ikke på et fast tall i dette dokumentet.

---

## Kontinuerlig integrasjon

Prosjektet bruker kontinuerlig integrasjon for å kjøre automatiserte kontroller mot endringer.

CI-pipelinen hjelper med å oppdage regresjoner før endringer behandles som klare for utgivelse.

The development workflow is therefore:

```text id="v3n9k8"
Change
  ↓
Test
  ↓
Security Review
  ↓
Documentation Review
  ↓
CI
  ↓
Release Preparation
```

A successful CI run does not replace manual security or documentation review.

---

## Documentation
En vellykket CI-kjøring erstatter ikke manuell sikkerhets- eller dokumentasjonsgjennomgang.

---

## Dokumentasjon

LUMS opprettholder separat dokumentasjon for ulike driftsbehov.

### `README.md`

Prosjektoversikt, arkitektur, funksjoner, sikkerhetsgrunnlinje, utviklingsstatus og prosjektets retning.

### `install.md`

Prosedyrer for installasjon, distribusjon, klientoppsett, validering, oppgradering og fjerning.

### `administration.md`

Rutinemessig administrasjon, vedlikehold, sikkerhetskopier, oppgraderinger, driftsprosedyrer og nødadministrasjon.

### `security.md`

Sikkerhetsarkitektur, sikkerhetskontroller, revisjonsfunn, herding og sikkerhetsinformasjon om utgivelsesklarhet.

### `telemetry.md`

Valgfri telemetri for CPU, minne, disk, nettverk, vert og drift, agentkonfigurasjon,
datalagring, sikkerhet og feilsøking.

### `LUMS_Health_Dashboard.md`

Hva den autentiserte helseoversikten rapporterer, hvordan klientstatus klassifiseres, telemetribegrensninger, tolkning av lagring for sikkerhetskopier og driftskontroller.

### `LUMS_Infrastructure_Topology.md`

Hvordan LUMS importerer registrerte klienter, administrerer infrastruktur og avhengigheter, beskytter topologiendringer og identifiserer mulige felles feilpunkter.

### `server/static/backup-restore.md`

Forsiktig Docker-basert gjenoppretting av en verifisert SQLite-sikkerhetskopi,
inkludert integritetskontroller og en reservekopi av den aktive databasen.

### `docs/update-tools-package.md`

Hva den nedlastbare artefakten med oppdateringsverktøy inneholder, hvordan CI
publiserer den, og kontrollene som kreves før produksjonsbruk.

### `troubleshooting.md`

Diagnostiske prosedyrer for problemer med server, klient, jobber, pakkeadministrasjon, autentisering, database, container og nettverk.

### `LUMS_Optional_Theme_System.md`

Arkitektur og vedlikeholdsveiledning for valgfrie LUMS-frontend-temaer.

Dokumentasjonen er bevisst delt opp etter ansvarsområde, slik at driftsinstruksjoner ikke blandes med sikkerhetsdesign eller visuell tilpasning.

---

## Dokumentasjonsprinsipp

Dokumentasjon behandles som en del av systemet.

En funksjon regnes ikke som helt ferdig når koden fungerer, men dokumentasjonen fortsatt beskriver en eldre arkitektur.

LUMS maintains separate documentation for different operational concerns.

### `README.md`

Project overview, architecture, features, security baseline, development status, and project direction.

### `install.md`

Installation, deployment, client setup, validation, upgrade, and removal procedures.

### `administration.md`

Routine administration, maintenance, backups, upgrades, operational procedures, and emergency administration.

### `security.md`

Security architecture, security controls, audit findings, hardening, and release-readiness security information.

### `telemetry.md`

Optional CPU and memory telemetry, agent configuration, data retention, security, and troubleshooting.

### `LUMS_Health_Dashboard.md`

What the authenticated health dashboard reports, how client status is classified, telemetry limits, backup-storage interpretation, and operational checks.

### `troubleshooting.md`

Diagnostic procedures for server, client, jobs, package management, authentication, database, container, and network problems.

### `LUMS_Optional_Theme_System.md`

Architecture and maintenance guidance for optional LUMS frontend themes.

The documentation is intentionally separated by responsibility so that operational instructions do not become mixed with security design or visual customization.

---

## Documentation Principle

Documentation is treated as part of the system.

A feature is not considered completely finished when the code works but the documentation still describes an older architecture.

The intended relationship is:

```text id="0m1m5u"
Implementation
      │
      ├── Tests
      ├── Security Review
      └── Documentation
               │
               ▼
          Release Ready
```

This is particularly important for security-sensitive deployment and administration procedures.

## Current Status

LUMS is an actively developed Linux update-management platform.

The current implementation includes:

* centralized client management
* software inventory
* update detection
* package search
* package installation and removal
* package-specific updates
* system updates
* persistent update jobs
* package-level job state
* job recovery
* reboot detection
* idle-aware execution
* client-token authentication
* token rotation
* administrative authentication
* role-based access control
* user management
* audit logging
* container hardening
* HTTPS transport
* automated testing
* continuous integration

The project is currently in the final documentation and release-readiness phase.

---

## Security Status

The major security-review areas have been implemented and reviewed.

The current security baseline includes:
Dette er spesielt viktig for sikkerhetssensitive distribusjons- og administrasjonsprosedyrer.

## Gjeldende status

LUMS er en aktivt utviklet plattform for administrasjon av Linux-oppdateringer.

Den nåværende implementeringen omfatter:

* sentralisert klientadministrasjon
* programvareinventar
* oppdateringsregistrering
* pakkesøk
* pakkeinstallasjon og -fjerning
* pakkespesifikke oppdateringer
* systemoppdateringer
* vedvarende oppdateringsjobber
* jobbtilstand på pakkenivå
* jobbgjenoppretting
* omstartsregistrering
* inaktivitetsbevisst kjøring
* klientautentisering med token
* tokenrotasjon
* administrativ autentisering
* rollebasert tilgangskontroll
* brukeradministrasjon
* revisjonslogging
* containerherding
* HTTPS-transport
* automatisert testing
* kontinuerlig integrasjon
* valgfri telemetri for CPU, minne, disk, nettverk, vert og hendelser
* infrastrukturtopologi fra registrerte klienter og manuelt vedlikeholdt inventar
* vedvarende varselposter og endepunkter for regeladministrasjon, med begrensningene

  dokumentert i `docs/LUMS_REALTIME_ALERTING_IMPLEMENTATION.md`

Denne listen er en oversikt på høyt nivå, ikke en påstand om funksjonskomplett
eller utgivelsesklar status. Valgfrie komponenter kan kreve separat installasjon
og konfigurasjon, og enkeltfunksjoner har dokumenterte begrensninger. Sjekk
kilderevisjonen og testene for oppførselen til en bestemt utgivelse.

---

## Sikkerhetsgrunnlinje

Sikkerhetsmodellen er implementert i applikasjonen og dokumentert i
[`security.md`](Sikkerhetsmodell.md). Kontrollene og verifikasjonsstatusen er
revisjonsspesifikke; se testene og distribusjonskontrollene for den nøyaktige
kilderevisjonen som brukes. Dette dokumentet er ikke en sikkerhetssertifisering.

Den nåværende sikkerhetsgrunnlinjen omfatter:

```text
Authentication
    ├── Argon2 password hashing
    ├── session handling
    ├── session revocation
    └── login rate limiting

Authorization
    ├── Administrator
    ├── Operator
    └── Viewer

Client Security
    ├── per-client tokens
    ├── SHA-256 token digests
    └── token rotation

API Security
    ├── input validation
    ├── CSRF protection
    ├── RBAC enforcement
    └── parameterized SQL

Runtime Security
    ├── non-root container
    ├── read-only root filesystem
    ├── dropped capabilities
    ├── no-new-privileges
    ├── restricted temporary filesystems
    └── protected secret mount

Network Security
    ├── HTTPS
    ├── reverse proxy
    ├── loopback application binding
    └── firewall restrictions
```

Security is treated as an ongoing engineering responsibility rather than a one-time checklist.

---

## Release Status

LUMS does not currently claim a stable production release version.

There is currently:

* no final semantic version
* no stable release tag
* no GitHub Release

The project deliberately follows the release sequence:
Sikkerhet behandles som et løpende ingeniøransvar, ikke som en engangssjekkliste.

---

## Utgivelsesprosess

```text id="f3c4y9"
Implementation
      ↓
Security Review
      ↓
Documentation Review
      ↓
Full Test Suite
      ↓
CI
      ↓
Version Assignment
      ↓
Git Tag
      ↓
GitHub Release
```

The first official release should only be created after the current implementation, security review, documentation, and regression testing are considered complete.

---

## Roadmap

The roadmap is intentionally focused on stability and maintainability rather than adding features without completing the existing foundation.

### Current Phase

* complete documentation review
* remove remaining documentation inconsistencies
* close documentation audit work
* perform final full test run
* verify CI
* prepare release version
* create the first official Git tag
* publish the first GitHub Release

### Future Development

Potential future work may include:

* additional Linux distributions
* additional package-manager backends
* further UI improvements
* additional reporting capabilities
* expanded operational automation
* additional security controls
* further test coverage

Future features should preserve the existing architectural boundaries.

---

## What LUMS Is Not

LUMS is intentionally not designed as:

* a general-purpose remote shell
* a replacement for APT, dpkg, or pacman
* a full configuration-management platform
* an endpoint-management suite for every operating system
* a cloud-only service
* an uncontrolled command-execution framework

LUMS focuses on a narrower problem:
Tilgjengelighet av utgivelser og tagger kan endre seg uavhengig av denne dokumentasjonen;
sjekk repositoryets [Releases](https://github.com/NovaForgeCtrl/LUMS/releases)
og [tags](https://github.com/NovaForgeCtrl/LUMS/tags) for gjeldende status.
En utgivelse bør først publiseres når implementeringen, sikkerhetsgjennomgangen,
dokumentasjonen og regresjonstestene for den revisjonen er fullført.

---

## Veikart

Denne veiledningen sporer ikke en grenspesifikk eller tidsbasert prosjektfase.
Mulig fremtidig arbeid, når det er valgt og verifisert, kan omfatte:

* flere Linux-distribusjoner
* flere backend-er for pakkebehandlere
* ytterligere forbedringer av brukergrensesnittet
* flere rapporteringsfunksjoner
* utvidet driftsautomatisering
* flere sikkerhetskontroller
* ytterligere testdekning

Fremtidige funksjoner bør bevare de eksisterende arkitektoniske grensene.

---

## Hva LUMS ikke er

LUMS er bevisst ikke utformet som:

* et generelt eksternt shell
* en erstatning for APT, dpkg eller pacman
* en fullstendig plattform for konfigurasjonsadministrasjon
* en endepunktadministrasjonspakke for alle operativsystemer
* en ren skytjeneste
* et ukontrollert rammeverk for kommandokjøring

> **Controlled Linux software and update management with persistent state and auditability.**

---
> **Kontrollert administrasjon av Linux-programvare og -oppdateringer med vedvarende tilstand og revisjonsevne.**

---

## Development Philosophy
## Utviklingsfilosofi

LUMS follows a simple development cycle:

```text id="8a0mve"
Build
  ↓
Test
  ↓
Secure
  ↓
Document
```

A feature is not considered complete simply because it works in the developer environment.

It should also be:

* tested
* security-reviewed
* documented
* reproducible
* understandable
* recoverable where appropriate

---

## Change Philosophy

Changes should be made deliberately.

A typical change should answer:

1. What problem does this solve?
2. Which component should own the change?
3. Does the change affect security?
4. Does it affect persistent state?
5. Does it affect clients?
6. Does it require documentation changes?
7. Which tests prove that existing functionality still works?

This reduces the risk of fixing one part of the system while silently breaking another.

---

## Development Workflow
En funksjon regnes ikke som fullført bare fordi den fungerer i utviklermiljøet.

Den bør også være:

* testet
* sikkerhetsgjennomgått
* dokumentert
* reproduserbar
* forståelig
* gjenopprettbar der det er hensiktsmessig

---

## Endringsfilosofi

Endringer bør gjøres bevisst.

En typisk endring bør besvare:

1. Hvilket problem løser dette?
2. Hvilken komponent bør eie endringen?
3. Påvirker endringen sikkerheten?
4. Påvirker den vedvarende tilstand?
5. Påvirker den klienter?
6. Krever den dokumentasjonsendringer?
7. Hvilke tester beviser at eksisterende funksjonalitet fortsatt fungerer?

Dette reduserer risikoen for å fikse én del av systemet mens man stilltiende ødelegger en annen.

---

## Utviklingsarbeidsflyt

The preferred development workflow is:

```text id="r8u6o1"
Understand
   ↓
Implement
   ↓
Test
   ↓
Inspect
   ↓
Harden
   ↓
Document
   ↓
Regression Test
```

Security-sensitive changes receive additional verification before being considered complete.
Sikkerhetssensitive endringer får ekstra verifikasjon før de regnes som fullført.

---

## Repository

The project repository is hosted on GitHub:

**NovaForgeCtrl/LUMS**

The repository contains the application source code, client components, tests, container configuration, and project documentation.

---

## Documentation Set

The current documentation set consists of:
Prosjektets repository er vert på GitHub:

**NovaForgeCtrl/LUMS**

Repositoryet inneholder applikasjonens kildekode, klientkomponenter, tester, containerkonfigurasjon og prosjektdokumentasjon.

---

## Dokumentasjonssett

Det nåværende dokumentasjonssettet består av:

```text id="0xw7cy"
README.md
install.md
administration.md
security.md
troubleshooting.md
telemetry.md
LUMS_Health_Dashboard.md
LUMS_Infrastructure_Topology.md
server/static/backup-restore.md
docs/update-tools-package.md
LUMS_Optional_Theme_System.md
PRODUCT.md
docs/LUMS_REALTIME_ALERTING_IMPLEMENTATION.md
docs/README.md
```

Each document has a defined purpose.

The README provides the project-level overview.

The installation guide explains deployment.

The administration guide explains ongoing operation.

The security guide documents the security architecture and audit state.
Administrasjonsveiledningen forklarer den løpende driften.

Sikkerhetsveiledningen dokumenterer sikkerhetsarkitekturen og revisjonsstatusen.

The troubleshooting guide provides diagnostic procedures.

The optional theme document covers frontend theme architecture.
Veiledningene for telemetri, helseoversikt, topologi, gjenoppretting av
sikkerhetskopi og oppdateringspakken dokumenterer disse driftsfunksjonene. Den
valgfrie temareferansen og `PRODUCT.md` er interne design- og
kontekstdokumenter; dokumentet for varslingsadministrasjon beskriver den
gjeldende implementeringen og funksjonene som ikke er tilgjengelige.
[`docs/README.md`](../../README.md) indekserer dokumentasjonen etter språk.

---

## Lisens

---

## License

LUMS is released under the MIT License.

The license is intended to keep the project open and accessible while allowing use, modification, and redistribution under the terms of the license.
Lisensen er ment å holde prosjektet åpent og tilgjengelig samtidig som den tillater bruk, endring og videredistribusjon i henhold til lisensvilkårene.

Se lisensfilen i repositoryet for den fullstendige juridiske teksten.

---

## Fellesskap og bidrag

See the repository license file for the complete legal text.

---

## Community and Contributions

LUMS is an open-source project and contributions are welcome.

Useful contributions can include:

* bug reports
* security reports
* documentation improvements
* tests
* package-manager support
* frontend improvements
* backend improvements
* deployment improvements

Contributions should preserve the project's architectural and security principles.

---

## Security Reports

Security issues should not be treated like ordinary feature requests.

When reporting a security problem, provide enough information to reproduce and understand the issue without unnecessarily exposing sensitive information.
Nyttige bidrag kan omfatte:

* feilrapporter
* sikkerhetsrapporter
* forbedringer av dokumentasjonen
* tester
* støtte for pakkebehandlere
* forbedringer av frontend
* forbedringer av backend
* forbedringer av distribusjon

Bidrag bør bevare prosjektets arkitektoniske og sikkerhetsmessige prinsipper.

---

## Sikkerhetsrapporter

Security-related changes should be reviewed carefully before being merged.

---
Når du rapporterer et sikkerhetsproblem, oppgi nok informasjon til at problemet kan reproduseres og forstås, uten å eksponere sensitiv informasjon unødvendig.

Sikkerhetsrelaterte endringer bør gjennomgås nøye før de slås sammen.

---

## Prosjektidentitet

LUMS is built around a simple idea:

> **Linux update management without the noise.**

The project does not attempt to hide complexity by pretending that Linux package management is simple.
> **Linux-oppdateringsadministrasjon uten støyen.**

Prosjektet forsøker ikke å skjule kompleksitet ved å late som om pakkeadministrasjon i Linux er enkel.

Instead, it makes the relevant state visible:

```text id="q2j5r0"
What is installed?
        ↓
What can be updated?
        ↓
What should change?
        ↓
Who requested it?
        ↓
What actually happened?
        ↓
What state remains?
```

That information is the foundation of controlled update management.

---

## Final Architecture

At its highest level, LUMS can be understood as five layers:
Denne informasjonen er grunnlaget for kontrollert oppdateringsadministrasjon.

---

## Endelig arkitektur

På det høyeste nivået kan LUMS forstås som fem lag:

```text id="7b4p6n"
┌───────────────────────────────────────────────┐
│                    UI                         │
│       Human interaction and visibility        │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    API                        │
│    Authentication, authorization, validation  │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                  Persistence                   │
│       Jobs, clients, users, results, audit   │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    Agent                      │
│      Local execution and system reporting     │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│              Native Linux Tools               │
│              APT / dpkg / pacman             │
└───────────────────────────────────────────────┘
```

Each layer has a specific responsibility.

The UI provides interaction.

The API enforces policy.

SQLite provides persistent state.
UI-et gir interaksjon.

API-et håndhever policy.

The agent performs controlled client-side execution.

The native package manager performs the actual system change.

---

## Final Principle
Den native pakkebehandleren gjør selve systemendringen.

---

## Endelig prinsipp

LUMS is built around one central principle:

> **Observe the system. Control the change. Record the result.**

That principle applies to the software architecture, update execution, security model, recovery mechanisms, and documentation.

**Linux-oppdateringshåndtering uten støy.**
> **Observer systemet. Kontroller endringen. Registrer resultatet.**

Dette prinsippet gjelder programvarearkitekturen, oppdateringskjøring, sikkerhetsmodellen, gjenopprettingsmekanismene og dokumentasjonen.

**Linux-oppdateringsadministrasjon uten støyen.**