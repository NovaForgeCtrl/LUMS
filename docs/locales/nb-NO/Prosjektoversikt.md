# LUMS

**Linux-oppdateringsadministrasjon uten støyen.**

## Kom i gang

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

LUMS er en server for administrasjon av Linux-oppdateringer, utformet for å gi kontrollert, reviderbar og sikker programvare- og oppdateringsadministrasjon for Linux-klienter.

I stedet for å stole på ukontrollert oppdateringsaktivitet på klientsiden gir LUMS et sentralt administrasjonslag for programvareinventar, oppdateringsregistrering, pakkeoperasjoner, oppdateringsjobber, overvåking av kjøringer og rapportering av resultater.

LUMS er utformet for miljøer der oppdateringer skal være **synlige, kontrollerte, sporbare og gjenopprettbare**.

---

## Hva er LUMS?

LUMS (**Linux Update Management Server**) består av en sentral server og lette Linux-klienter.

Serveren tilbyr administrasjonsgrensesnittet, API-et, autentisering, autorisasjon, jobbadministrasjon, revisjonslogging og vedvarende tilstand.

Agenten på klientsiden utfører lokale operasjoner i pakkebehandleren og rapporterer resultatene tilbake til serveren.

Grunnarkitekturen er:

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

## Hvorfor LUMS?

Linux-systemer har allerede utmerkede verktøy for pakkeadministrasjon.

LUMS forsøker ikke å erstatte dem.

I stedet gir LUMS et administrasjonslag rundt disse verktøyene, slik at administratorer sentralt kan svare på spørsmål som:

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

Målet er ikke å skjule den underliggende Linux-pakkebehandleren.

Målet er å gjøre driften av den **håndterbar og reviderbar**.

---

## Kjernefunksjoner

### Klientadministrasjon

LUMS holder oversikt over registrerte Linux-klienter og deres autentiseringstilstand.

Hver klient får et individuelt autentiseringstoken.

Klienttokener lagres ikke som legitimasjon i klartekst. Serveren lagrer en SHA-256-digest og validerer innkommende klientautentisering mot denne digesten.

Administratorer kan:

* registrere klienter
* deaktivere klienter
* rotere klienttokener
* inspisere klientstatus
* overvåke klientrapportering

---

### Programvareinventar

Klienter rapporterer installert programvare til LUMS-serveren.

Serveren lagrer inventaret og viser det gjennom administrasjonsgrensesnittet.

Visningen av installert programvare er bevisst atskilt fra pakkesøk i pakkeadministrasjonen.

Dette gjør at administratorer og brukere med skrivebeskyttet tilgang kan inspisere installert programvare uten at pakkeadministrasjonsoperasjoner automatisk blir eksponert.

---

### Oppdateringsinventar

Klienter fastslår jevnlig om pakkeoppdateringer er tilgjengelige.

Serveren lagrer den rapporterte oppdateringsinformasjonen og gjør den tilgjengelig for autoriserte brukere.

Oppdateringsinformasjon kan brukes som grunnlag for kontrollerte oppdateringsjobber.

---

### Pakkeadministrasjon

LUMS tilbyr pakkeadministrasjonsoperasjoner gjennom klientagenten.

Støttede pakkeoperasjoner omfatter:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Pakkeadministrasjonslaget abstraherer den underliggende pakkebehandleren.

Pakkebehandlerfamiliene som støttes i dag, er:

* **Debian / Ubuntu:** APT / dpkg
* **Arch Linux:** pacman

Pakkesøk er også tilgjengelig gjennom LUMS.

Søkeforespørsler sendes til målklienten, utføres med den lokale pakkebehandleren og returneres til serveren for visning.

---

### Oppdateringsjobber

Oppdateringsoperasjoner representeres som vedvarende jobber.

En jobb kan inneholde én eller flere pakkeoperasjoner og har en kjøringstilstand på serversiden.

Den generelle livssyklusen er:

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

Resultater på pakkenivå spores uavhengig, slik at avbrutte jobber kan gjenopprettes uten unødvendig å gjenta operasjoner som allerede er fullført.

---

### Kontrollert kjøring

LUMS kjører ikke vilkårlige shell-kommandoer levert av nettgrensesnittet.

Serveren oppretter strukturerte jobber med validerte handlinger og pakkenavn.

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

### Inaktivitetsbevisst kjøring

LUMS kan utsette kjøring av oppdateringer mens en klient regnes som aktiv.

Den nåværende inaktivitetsgrensen er **300 sekunder**.

Der det støttes, bruker agenten det lokale systemets økt- og inaktivitetsinformasjon via `loginctl`.

Hvis inaktivitetsregistrering ikke er tilgjengelig, later ikke LUMS som om klienten er inaktiv.

Dette skillet er viktig fordi **ukjent inaktivitetstilstand ikke er det samme som bekreftet inaktivitet**.

---

### Jobbgjenoppretting

Oppdateringsjobber er utformet for å overleve avbrudd.

Serveren opprettholder vedvarende tilstand for jobber og pakkeelementer.

Under gjenoppretting kjøres pakkeelementer som allerede er vellykket, ikke unødvendig på nytt.

Dette gir en kontrollpunktlignende kjøringsmodell for operasjoner med flere pakker.

Målet er:

> **Gjenopprett jobben, ikke start hele jobben blindt på nytt.**

---

### Omstartsregistrering

Noen pakkeoperasjoner kan kreve omstart av systemet.

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

Dette omfatter sikkerhetssensitive operasjoner som autentiseringsrelaterte handlinger, klientadministrasjon, brukeradministrasjon og opprettelse av oppdateringsjobber.

---

## Designprinsipp

LUMS følger et enkelt prinsipp:

> **Gjør administrasjon av Linux-oppdateringer synlig, kontrollert, gjenopprettbar og reviderbar — uten å skjule Linux-verktøyene under.**

## Arkitektur

LUMS skiller administrasjon, kjøring og persistens i tydelig definerte komponenter.

Serveren er ansvarlig for orkestrering og policy.

Klienten er ansvarlig for lokal systeminteraksjon.

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

LUMS bruker SQLite for vedvarende applikasjonstilstand.

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

LUMS bruker SQLite WAL-modus i den nåværende produksjonskonfigurasjonen.

---

## Containerarkitektur

LUMS-serveren distribueres som en herdet Docker-container.

Applikasjonscontaineren behandles bevisst som engangs.

Vedvarende applikasjonstilstand lagres i det dedikerte Docker-volumet:

```text
lums-data
```

Produksjonscontaineren bruker et skrivebeskyttet rotfilsystem.

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

Applikasjonen eksponeres internt gjennom:

```text
127.0.0.1:5050
```

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

Å bytte ut applikasjonscontaineren fjerner derfor ikke i seg selv LUMS-databasen.

Denne separasjonen er viktig for oppgraderinger og gjenoppretting.

---

## Klientarkitektur

Linux-klienten består av flere samarbeidende komponenter.

### LUMS-agent

Agenten er ansvarlig for samhandlingen med LUMS-serveren og det lokale Linux-systemet.

Gjeldende agentversjon:

```text
1.7.0
```

Agenten håndterer:

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

Pakkebehandlerlaget gir en kontrollert abstraksjon rundt den native Linux-pakkebehandleren.

Agenten krever ikke at LUMS erstatter pakkebehandleren.

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

Dette holder distribusjonsspesifikk pakkehåndtering inne i klienten.

---

### Kjøringsvakt (Watcher)

Watcheren overvåker kjøringen av oppdateringsjobber på klienten.

Gjeldende watcher-versjon:

```text
1.2.1
```

Watcheren samarbeider med agenten og jobbtilstanden på serversiden.

Formålet er å sikre at jobber som forventes å bli utført, ikke blir liggende ubehandlet på ubestemt tid.

---

## Rapporteringsvei

Normal klientrapportering følger denne retningen:

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

Serveren trenger derfor ikke å vedlikeholde en fullstendig ekstern pakkeregisterindeks for hver klient.

Søket utføres i klientens eget pakkeadministrasjonsmiljø.

---

## Veien for oppdateringskjøring

En oppdateringsjobb følger den generelle arkitekturen:

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

Dette skaper den sentrale LUMS-kjøringskjeden:

> **Browser → API → SQLite → Agent → Package Manager → Result → SQLite → UI**

---

## Atomisk jobbtildeling

Oppdateringsjobber er vedvarende objekter på serversiden.

Før kjøring må agenten få tak i en jobb som er kvalifisert for kjøring.

Jobbtildeling utføres atomisk, slik at den samme ventende jobben ikke utilsiktet tas av flere kjøringsveier.

Dette er spesielt viktig når tidtakere, nye forsøk, gjenoppretting eller flere prosesser på klientsiden er involvert.

---

## Jobbkjøring

Serveren oppretter strukturerte jobber.

Klientagenten tolker de støttede jobbhandlingene og utfører den tilsvarende lokale operasjonen.

De støttede pakkehandlingene er:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Pakkenavn valideres før en pakkejobb opprettes.

Agenten behandler ikke pakkenavn som vilkårlige shell-fragmenter.

---

## Abstraksjon for pakkeadministrasjon

Pakkeoperasjoner er bevisst implementert bak en abstraksjon for pakkebehandlere.

Dette holder den overordnede LUMS-jobbmodellen uavhengig av distribusjonsspesifikke kommandoer.

For eksempel:

```text
INSTALL_PACKAGE
       │
       ├── Debian / Ubuntu → APT
       │
       └── Arch Linux      → pacman
```

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

LUMS-agenten erstatter ikke APT.

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

Søkeresultater kan inneholde pakkeinformasjon som:

* pakkenavn
* versjon
* beskrivelse
* depotinformasjon der det er tilgjengelig

Søkeresultater returneres til LUMS-serveren og vises i grensesnittet for pakkeadministrasjon.

---

## Tillatelser for pakkeadministrasjon

Pakkeadministrasjon er en privilegert operasjon.

Den nåværende tillatelsesmodellen er:

```text
Administrator → allowed
Operator      → allowed
Viewer        → not allowed
```

En Viewer kan fortsatt inspisere installert programvare.

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

Etter pakkeoperasjoner kontrollerer klienten om operasjonen indikerer at en omstart er nødvendig.

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

Denne separasjonen hindrer at administrative nettleserøkter og klientlegitimasjon blir utskiftbare autentiseringsmekanismer.

---

## Revisjonsspor

Sikkerhetsrelevante og administrative handlinger registreres av revisjonssystemet på serversiden.

Revisjonssporet utfyller vanlig applikasjonslogging.

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

Hvert lag har et definert ansvar.

Serveren administrerer.

Agenten utfører.

Pakkebehandleren gjør selve systemendringen.

Resultatet går tilbake gjennom den samme kontrollerte kjeden.

## Rollebasert tilgangskontroll

LUMS bruker tre administrative roller:

```text
Administrator
Operator
Viewer
```

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

Brukeradministrasjonsoperasjoner er beskyttet av:

* autentisering
* tillatelsesbasert autorisasjon
* CSRF-beskyttelse
* inndatavalidering
* kontroll av duplikate brukere
* revisjonslogging

Brukeradministrasjonsgrensesnittet eksponeres ikke uten `users.manage`.

---

## Øktsikkerhet

Administrativ autentisering bruker økthåndtering på serversiden.

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

Den relevante tilstanden lagres vedvarende i SQLite.

Vellykket autentisering fjerner den gjeldende feiltilstanden.

Dette hindrer at en enkel omstart av applikasjonen kan brukes til å omgå påloggingsbeskyttelsen.

---

## Sikkerhet for klienttokener

Hver registrerte klient har sitt eget autentiseringstoken.

Serveren lagrer tokenet som en SHA-256-digest.

Det opprinnelige tokenet er ikke nødvendig for vanlig validering på serversiden.

Tokenrotasjon lar administratorer ugyldiggjøre en eksisterende legitimasjon og utstede en erstatning.

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

Databaseoperasjoner bruker parameteriserte SQL-setninger.

Verdier som brukeren kontrollerer, settes ikke direkte sammen med SQL-spørringer.

Dette gjelder områder som:

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

Håndheving av fremmednøkler aktiveres eksplisitt av applikasjonen for databasetilkoblinger.

Den nåværende konfigurasjonen bruker WAL-modus.

Databasen lagres i det vedvarende Docker-volumet, ikke i filsystemet til den utskiftbare applikasjonscontaineren.

---

## Jobbgjenoppretting og kontrollpunkter

LUMS behandler oppdateringsjobber som vedvarende tilstandsmaskiner.

En jobb med flere pakker kan inneholde flere enkeltstående pakkeoperasjoner.

Hvert pakkeelement kan nå sin egen resultattilstand.

Hvis kjøringen avbrytes, kan gjenopprettingen skille mellom:

```text
already successful
        │
        └── do not unnecessarily repeat

not completed
        │
        └── eligible for recovery
```

Dette reduserer risikoen for å gjenta fullførte pakkeoperasjoner blindt etter et avbrudd.

---

## Kontrollert oppdateringskjøring

LUMS begrenser bevisst handlingene som kan etterspørres gjennom API-et for oppdateringsjobber.

Støttede handlinger er:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Serveren validerer handlingen og relevant pakkeinformasjon før jobben opprettes.

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

Noen pakkeoperasjoner kan kreve omstart.

LUMS registrerer omstartsbehov som en del av resultatene for oppdateringsjobber.

Dette gjør at administratorer kan skille mellom:

```text
Update completed
```

og:

```text
Update completed
Reboot required
```

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

Revisjonslogging er atskilt fra vanlig diagnostisk logging.

Diagnostiske logger hjelper med feilsøking av applikasjonen.

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

## Utviklingsstatus

LUMS er for tiden under aktiv utvikling.

Den sentrale administrasjonsarkitekturen, klientens kjøringsmodell, pakkeadministrasjon, RBAC, sikkerhetsherding og gjenopprettingsmekanismer er implementert.

Prosjektet regnes bevisst ikke som en ferdig utgivelse bare fordi applikasjonen fungerer.

Utgivelsesklarhet krever også at den omkringliggende dokumentasjonen og driftsprosedyrene beskriver det samme gjeldende systemet.

Derfor behandles dokumentasjonskonsistens som en del av ingeniørprosessen, ikke som en ettertanke.

## Støttede systemer

LUMS er utformet for å administrere Linux-systemer som bruker støttede native pakkebehandlere.

### Debian / Ubuntu

Støttet stack for pakkeadministrasjon:

```text
APT
dpkg
```

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
* `loginctl` der informasjon om inaktivitetstilstand er tilgjengelig

---

## Prosjektstruktur

Repositoryet er organisert i separate komponenter for server, klient, frontend og tester.

En forenklet struktur er:

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

Applikasjonen serveres av Gunicorn inne i containeren.

Nginx er det eksterne HTTPS-inngangspunktet.

---

## Agent

LUMS-agenten installeres direkte på administrerte Linux-klienter.

Gjeldende agentversjon:

```text id="w8p4wz"
1.7.0
```

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

Konseptuelt:

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

Dette lar det overordnede systemet for oppdateringsjobber arbeide med strukturerte operasjoner uten å måtte kjenne hver distribusjonsspesifikke kommando.

---

## Watcher

LUMS-kjøringsvakten (watcher) overvåker jobber som forventes å bli utført på klienten.

Gjeldende watcher-versjon:

```text id="7k6w3s"
1.2.1
```

Watcheren fungerer sammen med agenten og jobbtilstanden på serversiden.

Denne arkitekturen gjør at LUMS kan oppdage kjøringssituasjoner der en jobb blir stående som ventende eller på annen måte krever oppmerksomhet.

---

## systemd-integrasjon

Klienten bruker systemd for planlagt og kontrollert kjøring.

Relevante komponenter omfatter service- og timer-enheter for:

* klientrapportering
* oppdateringsregistrering
* jobbkjøring/overvåking

Dette gir forutsigbar kjøring uten å kreve en kontinuerlig kjørende forgrunnsprosess for hver periodiske operasjon.

Klientagenten kan også kjøres manuelt under installasjon og feilsøking.

---

## Inaktivitetsbevisst kjøring

Inaktivitetsbevisst kjøring er utformet for å redusere forstyrrelser for aktive brukere.

Den nåværende inaktivitetsgrensen er:

```text id="g8v0lq"
300 seconds
```

Klienten fastslår inaktivitetstilstand ut fra tilgjengelig lokal øktinformasjon.

Der det støttes, brukes `loginctl`.

Agenten skiller mellom:

```text id="6v3m4k"
confirmed idle
active
idle state unavailable
```

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

Disse handlingene er bevisst begrenset.

LUMS er et system for oppdateringsadministrasjon, ikke et generelt rammeverk for eksterne kommandoer.

---

## Jobbtilstand på pakkenivå

Jobber med flere pakker kan spore fremdrift på pakkenivå.

For eksempel:

```text id="v9w1sh"
Job #42

package-a → SUCCESS
package-b → SUCCESS
package-c → FAILED
package-d → PENDING
```

Gjenoppretting kan dermed virke på de ufullførte delene av jobben i stedet for å gjenta vellykkede pakkeoperasjoner blindt.

---

## Jobbgjenoppretting

Gjenoppretting er utformet rundt vedvarende kontrollpunkter.

Serveren opprettholder jobbtilstanden.

Klienten rapporterer resultater på pakkenivå.

Hvis kjøringen avbrytes, kan serveren avgjøre hvilket arbeid som allerede er fullført, og hvilket som fortsatt er kvalifisert for gjenoppretting.

Det tiltenkte gjenopprettingsprinsippet er:

> **Fortsett fra kjent tilstand i stedet for å anta at ingenting skjedde.**

---

## Resultatvalidering

Klientens jobbresultater valideres før de godtas i den vedvarende serverstatus.

Dette beskytter jobbtilstanden mot ugyldige eller ufullstendige resultatinnsendinger.

Validering brukes på relevante felt som:

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

Klientautentisering er uavhengig for hver registrerte klient.

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

Antallet tester endres etter hvert som prosjektet utvikler seg; stol på
kommandoens resultat, ikke på et fast tall i dette dokumentet.

---

## Kontinuerlig integrasjon

Prosjektet bruker kontinuerlig integrasjon for å kjøre automatiserte kontroller mot endringer.

CI-pipelinen hjelper med å oppdage regresjoner før endringer behandles som klare for utgivelse.

Utviklingsarbeidsflyten er derfor:

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

Det tiltenkte forholdet er:

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

LUMS fokuserer på et smalere problem:

> **Kontrollert administrasjon av Linux-programvare og -oppdateringer med vedvarende tilstand og revisjonsevne.**

---

## Utviklingsfilosofi

LUMS følger en enkel utviklingssyklus:

```text id="8a0mve"
Build
  ↓
Test
  ↓
Secure
  ↓
Document
```

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

Den foretrukne utviklingsarbeidsflyten er:

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

Sikkerhetssensitive endringer får ekstra verifikasjon før de regnes som fullført.

---

## Repository

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

Hvert dokument har et definert formål.

README gir prosjektoversikten på overordnet nivå.

Installasjonsveiledningen forklarer distribusjon.

Administrasjonsveiledningen forklarer den løpende driften.

Sikkerhetsveiledningen dokumenterer sikkerhetsarkitekturen og revisjonsstatusen.

Feilsøkingsveiledningen gir diagnostiske prosedyrer.

Veiledningene for telemetri, helseoversikt, topologi, gjenoppretting av
sikkerhetskopi og oppdateringspakken dokumenterer disse driftsfunksjonene. Den
valgfrie temareferansen og `PRODUCT.md` er interne design- og
kontekstdokumenter; dokumentet for varslingsadministrasjon beskriver den
gjeldende implementeringen og funksjonene som ikke er tilgjengelige.
[`docs/README.md`](../../README.md) indekserer dokumentasjonen etter språk.

---

## Lisens

LUMS er utgitt under MIT-lisensen.

Lisensen er ment å holde prosjektet åpent og tilgjengelig samtidig som den tillater bruk, endring og videredistribusjon i henhold til lisensvilkårene.

Se lisensfilen i repositoryet for den fullstendige juridiske teksten.

---

## Fellesskap og bidrag

LUMS er et åpen kildekode-prosjekt, og bidrag er velkomne.

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

Sikkerhetsproblemer bør ikke behandles som vanlige funksjonsforespørsler.

Når du rapporterer et sikkerhetsproblem, oppgi nok informasjon til at problemet kan reproduseres og forstås, uten å eksponere sensitiv informasjon unødvendig.

Sikkerhetsrelaterte endringer bør gjennomgås nøye før de slås sammen.

---

## Prosjektidentitet

LUMS er bygget rundt en enkel idé:

> **Linux-oppdateringsadministrasjon uten støyen.**

Prosjektet forsøker ikke å skjule kompleksitet ved å late som om pakkeadministrasjon i Linux er enkel.

I stedet gjør det den relevante tilstanden synlig:

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

Hvert lag har et spesifikt ansvar.

UI-et gir interaksjon.

API-et håndhever policy.

SQLite gir vedvarende tilstand.

Agenten utfører kontrollert kjøring på klientsiden.

Den native pakkebehandleren gjør selve systemendringen.

---

## Endelig prinsipp

LUMS er bygget rundt ett sentralt prinsipp:

> **Observer systemet. Kontroller endringen. Registrer resultatet.**

Dette prinsippet gjelder programvarearkitekturen, oppdateringskjøring, sikkerhetsmodellen, gjenopprettingsmekanismene og dokumentasjonen.

**Linux-oppdateringsadministrasjon uten støyen.**
