# LUMS

**Linux-oppdateringsadministrasjon uten støyen.**

## Kom i gang

LUMS administrerer Linux-oppdateringer sentralt. En server viser klienter, installert programvare og tilgjengelige oppdateringer. En agent på hvert administrerte Linux-system utfører godkjente pakkehandlinger ved hjelp av systemets pakkebehandler. LUMS erstatter ikke APT på Debian/Ubuntu eller pacman på Arch Linux.

**Bruker du bare en eksisterende LUMS-installasjon?** Åpne adressen du har fått av administratoren din, og logg inn med din egen konto. Hvis en funksjon mangler, kan det hende at kontoen din ikke har tillatelse til å bruke den. Spør administratoren din om hjelp; ikke del kontoer eller bruk en klienttoken som nettpåloggingspassord.

**Installerer eller drifter du LUMS?** Start med [installasjonsveiledningen](Installasjon og oppgraderinger.md), og les deretter [administrasjonsveiledningen](Administrasjon og sikkerhetskopier.md). Hvis noe går galt, bruk [feilsøkingsveiledningen](Feilsøking.md). Oversatte veiledninger finnes også, men de kan dekke mindre enn de engelske tekniske originalene. [Dokumentasjonsoversikten](../../README.md) viser tilgjengelige språkversjoner.

En testkjøring eller et vellykket bygget Docker-bilde er **ikke** en produksjonsinstallasjon. En produksjonsdistribusjon trenger også HTTPS, en beskyttet applikasjonshemmelighet, vedvarende data, verifiserte sikkerhetskopier og en herdet container. Ikke kopier produksjonskommandoer før du har kontrollert plassholderne og lagringsbanene mot din egen installasjon.

### Språk i nettgrensesnittet

Nettgrensesnittet tilbyr tysk, engelsk (US og UK), fransk, spansk, forenklet kinesisk, japansk, polsk, svensk, norsk bokmål og finsk. Velg et språk øverst til høyre på påloggingssiden. Hvis du ikke velger ett, prøver LUMS å bruke nettleserens språk; etter innlogging har et språk som er lagret på kontoen din, forrang. Noe teknisk eller dynamisk tekst kan forbli på originalspråket når en oversettelse ikke er tilgjengelig. Markdown-guider er atskilt fra nettgrensesnittet og oversettes ikke automatisk.

---

LUMS er en server for administrasjon av Linux-oppdateringer, utformet for å gi kontrollert, reviderbar og sikker programvare- og oppdateringsadministrasjon for Linux-klienter.

I stedet for å stole på ukontrollert oppdateringsaktivitet på klientsiden, gir LUMS et sentralt administrasjonslag for programvareinventar, oppdateringsregistrering, pakkeoperasjoner, oppdateringsjobber, kjøringsovervåking og resultatrapportering.

LUMS er utformet for miljøer der oppdateringer skal være **synlige, kontrollerte, sporbare og gjenopprettbare**.

---

## Hva er LUMS?

LUMS (**Linux Update Management Server**) består av en sentral server og lette Linux-klienter.

Serveren tilbyr administrasjonsgrensesnittet, API, autentisering, autorisasjon, jobadministrasjon, revisjonslogging og vedvarende tilstand.

Agenten på klientsiden utfører lokale pakkebehandleroperasjoner og rapporterer resultatene tilbake til serveren.

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

Hvorfor LUMS?

Linux-systemer tilbyr allerede utmerkede verktøy for pakkeadministrasjon.

LUMS forsøker ikke å erstatte dem.

I stedet gir LUMS et administrasjonslag rundt disse verktøyene, slik at administratorer sentralt kan svare på spørsmål som:

* Hvilke klienter finnes?

* Hvilken programvare er installert?

* Hvilke oppdateringer er tilgjengelige?

* Hvilke pakker skal installeres eller fjernes?

* Hvilke oppdateringsjobber kjører?

* Hva skjedde under en oppdatering?

* Rapporterte klienten resultatet vellykket?

* Krevdes det omstart?

* Kan en avbrutt jobb gjenopprettes trygt?

* Hvem startet en administrativ handling?

Målet er ikke å skjule den underliggende Linux-pakkebehandleren.

Målet er å gjøre driften av den håndterbar og reviderbar.
Kjernefunksjoner
Klientadministrasjon

LUMS vedlikeholder registrerte Linux-klienter og deres autentiseringstilstand.

Hver klient får et individuelt autentiseringstoken.

Klienttokener lagres ikke som klartekstpåloggingsinformasjon. Serveren lagrer et SHA-256-sammendrag og validerer innkommende klientautentisering mot dette sammendraget.

Administratorer kan:

* registrere klienter

* deaktivere klienter

* rotere klienttokener

* inspisere klientstatus

* overvåke klientrapportering

Programvareinventar

Klienter rapporterer installert programvare til LUMS-serveren.

Serveren lagrer inventaret og eksponerer det gjennom administrasjonsgrensesnittet.

Visningen for installert programvare er bevisst atskilt fra pakkeadministrasjonssøk.

Dette lar administratorer og skrivebeskyttede brukere inspisere installert programvare uten automatisk å eksponere pakkeadministrasjonsoperasjoner.
Oppdateringsinventar

Klienter fastslår periodisk om pakkeoppdateringer er tilgjengelige.

Serveren lagrer den rapporterte oppdateringsinformasjonen og gjør den tilgjengelig for autoriserte brukere.

Oppdateringsinformasjon kan brukes som grunnlag for kontrollerte oppdateringsjobber.
Pakkeadministrasjon

LUMS tilbyr pakkeadministrasjonsoperasjoner gjennom klientagenten.

Støttede pakkeoperasjoner inkluderer:

* INSTALL_PACKAGE

* REMOVE_PACKAGE

* UPDATE_PACKAGE

* UPDATE_SYSTEM

Pakkeadministrasjonslaget abstraherer den underliggende pakkebehandleren.

Gjeldende støttede pakkebehandlerfamilier er:

* Debian / Ubuntu: APT / dpkg

* Arch Linux: pacman

Pakkesøk er også tilgjengelig gjennom LUMS.

Søkeforespørsler sendes til målklienten, utføres med den lokale pakkebehandleren og returneres til serveren for visning.
Oppdateringsjobber

Oppdateringsoperasjoner representeres som vedvarende jobber.

En jobb kan inneholde én eller flere pakkeoperasjoner og vedlikeholder en kjøringstilstand på serversiden.

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
Kontrollert kjøring

LUMS utfører ikke vilkårlige skallkommandoer levert fra nettgrensesnittet.

Serveren oppretter strukturerte jobber med validerte handlinger og pakkenavn.

Klientagenten tilordner disse handlingene til den aktuelle lokale pakkebehandleroperasjonen.

Dette skaper en bevisst grense mellom:

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

Inaktivitetssensitiv kjøring

LUMS kan utsette oppdateringskjøring mens en klient anses som aktiv.

Gjeldende inaktivitetsterskel er 300 sekunder.

Der det støttes, bruker agenten det lokale systemets økt-/inaktivitetinformasjon gjennom loginctl.

Hvis inaktivitetsdeteksjon ikke er tilgjengelig, later LUMS ikke som om klienten er inaktiv.

Denne forskjellen er viktig fordi ukjent inaktivitetstilstand ikke er det samme som bekreftet inaktivitetstilstand.
Jobbgjenoppretting

Oppdateringsjobber er utformet for å overleve avbrudd.

Serveren vedlikeholder vedvarende tilstand for jobber og pakkeelementer.

Under gjenoppretting blir pakkeelementer som allerede er vellykkede, ikke unødvendig utført på nytt.

Dette gir en sjekkpunktlignende kjøringsmodell for operasjoner med flere pakker.

Målet er:

* Gjenopprett jobben, ikke start hele jobben blindt på nytt.

Omstartsdeteksjon

Noen pakkeoperasjoner kan kreve omstart av systemet.

LUMS behandler derfor omstartsdeteksjon som en del av håndteringen av oppdateringsresultater, i stedet for å anta at en vellykket avslutning fra pakkebehandleren alltid betyr at systemet er fullt operativt.

Klienten rapporterer det registrerte omstartskravet tilbake til serveren.
Klientautentisering

Klientkommunikasjon autentiseres ved hjelp av tokener per klient.

Tokener er:

* individuelt tildelt

* roterbare

* lagret på serversiden bare som SHA-256-sammendrag

* validert før klientrapporter godtas

Tokenrotasjon lar en administrator ugyldiggjøre en tidligere utstedt klientlegitimasjon uten å opprette klienten på nytt.
Reviderbarhet

Administrative og sikkerhetsrelevante handlinger registreres gjennom LUMS' revisjonsloggsystem.

Revisjonssporet er ment å svare på:

```text
Who?
What?
When?
Against which object?
With which result?
```

Dette inkluderer sikkerhetsfølsomme operasjoner som autentiseringsrelaterte handlinger, klientadministrasjon, brukeradministrasjon og opprettelse av oppdateringsjobber.
Designprinsipp

LUMS følger et enkelt prinsipp:

* Gjør Linux-oppdateringsadministrasjon synlig, kontrollert, gjenopprettbar og reviderbar — uten å skjule Linux-verktøyene under.

Arkitektur

LUMS skiller administrasjon, kjøring og persistens i klart definerte komponenter.

Serveren er ansvarlig for orkestrering og policy.

Klienten er ansvarlig for lokal systeminteraksjon.

Pakkebehandleren forblir ansvarlig for faktisk å installere, fjerne eller oppdatere programvare.

Denne separasjonen er tilsiktet.

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

Serverkomponenter

LUMS-serveren tilbyr det sentrale administrasjonslaget.
Webapplikasjon

Webapplikasjonen tilbyr administrasjonsgrensesnittet for:

* klientadministrasjon

* programvareinventar

* oppdateringsinformasjon

* oppdateringsjobber

* pakkeadministrasjon

* oppdateringshistorikk

* brukeradministrasjon

* systemvedlikehold

Grensesnittet respekterer gjeldende brukers RBAC-rolle.

Synlighet i frontend tilpasses derfor brukerens tillatelser, men autorisasjon håndheves alltid også på serversiden.
### API

API-et kobler nettgrensesnittet og Linux-klientene til applikasjonslogikken på serversiden.

Det håndterer operasjoner som:

* klientregistrering og -administrasjon

* klientrapporter

* pakkesøk

* pakkesøkeresultater

* oppdateringsjobber

* jobresultater

* brukeradministrasjon

* revisjonshendelser

API-endepunkter validerer input før de utfører tilstandsendrende operasjoner.
Autentisering og økter

Administrative brukere autentiseres gjennom LUMS-webapplikasjonen.

Økter kontrolleres av serveren og støtter eksplisitt tilbakekalling av økter.

Autentiseringssikkerhet inkluderer:

* passordhashing med Argon2

* øktadministrasjon

* tilbakekalling av økter

* hastighetsbegrensning for innlogging

* CSRF-beskyttelse

* rollebasert autorisasjon

Klientautentisering er atskilt fra administrativ autentisering.
### RBAC

LUMS kombinerer rollemaler med tillatelser per bruker. Malene Administrator, Operator og Viewer gir startsett med tillatelser som kan tilpasses for hver konto.

Autorisasjon håndheves på serveren ved hjelp av kontoens lagrede tillatelser.

Frontend skjuler i tillegg funksjonalitet som brukerens tillatelser ikke tillater.

Dette betyr at skjuling av en knapp aldri behandles som en sikkerhetsgrense.
SQLite-persistens

LUMS bruker SQLite for vedvarende applikasjonstilstand.

Databasen lagrer informasjon som:

* brukere

* økter

* klienter

* klientautentiseringstilstand

* programvareinventar

* tilgjengelige oppdateringer

* oppdateringsjobber

* jobresultater på pakkenivå

* pakkesøkeforespørsler og -resultater

* revisjonsinformasjon

Applikasjonen aktiverer eksplisitt SQLite-fremmednøkkelhåndheving for databaseforbindelser.

Gjeldende produksjonsbaseline for SQLite er:
```text

journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

LUMS bruker SQLite WAL-modus i gjeldende produksjonskonfigurasjon.
Containerarkitektur

LUMS-serveren distribueres som en herdet Docker-container.

Applikasjonscontaineren behandles bevisst som engangs.

Vedvarende applikasjonstilstand lagres i det dedikerte Docker-volumet:

```text
lums-data
```

Produksjonscontaineren bruker et skrivebeskyttet rotfilsystem.

Skrivbare plasseringer er bevisst begrenset til nødvendige kjørings- og vedvarende lagringsbaner.

Produksjonens sikkerhetsbaseline inkluderer:

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

Ekstern HTTPS-tilgang leveres gjennom omvendt proxy.
Vedvarende og engangskomponenter

LUMS skiller vedvarende tilstand fra utskiftbare kjøringskomponenter.

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

Å erstatte applikasjonscontaineren fjerner derfor ikke automatisk LUMS-databasen.

Denne separasjonen er viktig for oppgraderinger og gjenoppretting.
Klientarkitektur

Linux-klienten består av flere samarbeidende komponenter.
LUMS-agent

Agenten er ansvarlig for interaksjon med LUMS-serveren og det lokale Linux-systemet.

Gjeldende agentversjon:

```text
1.7.0
```

Agenten håndterer:

* autentisering

* inventarinnsamling

* oppdateringsdeteksjon

* pakkesøk

* pakkeoperasjoner

* kjøring av oppdateringsjobber

* resultatrapportering

* omstartsdeteksjon

* håndtering av inaktivitetstilstand

Pakkebehandlerlag

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
Kjøringsovervåker

Overvåkeren overvåker kjøring av oppdateringsjobber på klienten.

Gjeldende overvåker-versjon:

```text
1.2.1
```

Overvåkeren samarbeider med agenten og jobbtilstanden på serversiden.

Formålet er å sikre at jobber som forventes utført, ikke blir liggende ubehandlet på ubestemt tid.
Rapporteringsbane

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

For eksempel produserer en oppdateringssjekk utført av klienten informasjon som rapporteres til serveren og lagres som klientens gjeldende oppdateringstilstand.

Nettleseren spør ikke direkte klientens pakkebehandler.
Pakkesøkebane

Pakkesøk følger en annen forespørsel/svar-flyt:

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

Serveren trenger derfor ikke å vedlikeholde en fullstendig ekstern pakkerepositoriumindeks for hver klient.

Søket utføres med klientens eget pakkeadministrasjonsmiljø.
Oppdateringskjøringsbane

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

Dette skaper LUMS' sentrale kjøringskjede:

* Browser → API → SQLite → Agent → Package Manager → Result → SQLite → UI

Atomisk jobbkrav

Oppdateringsjobber er vedvarende objekter på serversiden.

Før kjøring må agenten få en jobb som er kvalifisert for kjøring.

Jobbkrav utføres atomisk, slik at den samme ventende jobben ikke utilsiktet blir krevd av flere kjøringsbaner.

Dette er spesielt viktig når timere, nye forsøk, gjenoppretting eller flere prosesser på klientsiden er involvert.
Jobbkjøring

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

Agenten behandler ikke pakkenavn som vilkårlige skallfragmenter.
Abstraksjon for pakkeadministrasjon

Pakkeoperasjoner er bevisst implementert bak en pakkebehandlerabstraksjon.

Dette holder LUMS' overordnede jobbmodell uavhengig av distribusjonsspesifikke kommandoer.

For eksempel:

```text
INSTALL_PACKAGE
       │
       ├── Debian / Ubuntu → APT
       │
       └── Arch Linux      → pacman
```

Det samme prinsippet gjelder for fjerning og pakkeoppdateringer.
## Debian / Ubuntu

På Debian-familiesystemer bruker LUMS den native APT/dpkg-verktøykjeden.

Typiske ansvarsområder inkluderer:

* pakkesøk

* oppslag av pakkemetadata

* pakkeinstallasjon

* pakkefjerning

* pakkeoppdateringer

* systemoppdateringer

* oppdateringsdeteksjon

LUMS-agenten erstatter ikke APT.

Den gir kontrollert orkestrering rundt det.
## Arch Linux

På Arch Linux-systemer bruker LUMS den native pacman-pakkebehandleren.

Typiske ansvarsområder inkluderer:

* pakkesøk

* oppslag av pakkemetadata

* pakkeinstallasjon

* pakkefjerning

* pakkeoppdateringer

* systemoppdateringer

* oppdateringsdeteksjon

Distribusjonsspesifikk atferd forblir inne i pakkebehandlerlaget.
Pakkesøk

Pakkesøk er atskilt fra inventaret for installert programvare.

Denne forskjellen er viktig:
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

* repositoriumsinformasjon der tilgjengelig

Søkeresultater returneres til LUMS-serveren og vises i grensesnittet for pakkeadministrasjon.
Tillatelser for pakkeadministrasjon

Pakkeadministrasjon er en privilegert operasjon.

Gjeldende tillatelsesmodell er:

```text
Administrator → allowed
Operator      → allowed
Viewer        → not allowed
```

En Viewer kan fortsatt inspisere installert programvare.

Selve grensesnittet for pakkeadministrasjon er skjult for Viewers, og tilsvarende endepunkter på serversiden håndhever autorisasjon uavhengig.
Håndtering av oppdateringsresultater

LUMS behandler resultatet av en oppdateringsoperasjon som strukturert tilstand i stedet for bare å vise rå kommandoutdata.

Relevant informasjon kan inkludere:

* suksess eller feil

* resultat på pakkenivå

* kjøringstilstand

* feilinformasjon

* omstartskrav

* fullføringstidsstempler

Dette lar serveren vedlikeholde en meningsfull oppdateringshistorikk.
Omstartsdeteksjon

Etter pakkeoperasjoner kontrollerer klienten om operasjonen indikerer at en omstart er nødvendig.

Resultatet rapporteres til serveren som en del av jobresultatet.

Et omstartskrav forblir derfor knyttet til oppdateringsoperasjonen i stedet for å gå tapt i en terminaløkt på klientsiden.
Autentiseringsgrense for klienter

Klient-API-et bruker en annen autentiseringsmekanisme enn administrative nettsøkter.

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

Denne separasjonen forhindrer at administrative nettleserøkter og klientlegitimasjon blir utbyttbare autentiseringsmekanismer.
Revisjonsspor

Sikkerhetsrelevante og administrative handlinger registreres av revisjonssystemet på serversiden.

Revisjonssporet utfyller vanlig applikasjonslogging.

Logging svarer på spørsmål om applikasjonsatferd.

Revisjonslogging registrerer i tillegg viktige administrative handlinger og deres kontekst.

Denne forskjellen er nyttig når man undersøker endringer i klienter, brukere, autentiseringstilstand eller oppdateringsjobber.
Driftsprinsipp

LUMS skiller bevisst:

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

Pakkebehandleren utfører den faktiske systemendringen.

Resultatet reiser tilbake gjennom den samme kontrollerte kjeden.
Rollebasert tilgangskontroll

LUMS bruker tre administrative roller:

```text
Administrator
Operator
Viewer
```

Autorisasjon håndheves på serversiden.

Frontend tilpasser i tillegg det synlige grensesnittet til brukerens tillatelser, men synlighet i frontend behandles aldri som en sikkerhetsgrense.
### Administrator

Administratorer har tilgang til:

* vise klienter

* vise installert programvare

* vise tilgjengelige oppdateringer

* opprette og kjøre oppdateringsjobber

* vise oppdateringshistorikk

* bruke pakkeadministrasjon

* utføre systemvedlikehold

* opprette og deaktivere klienter

* rotere klienttokener

* opprette og administrere brukere

* administrere roller og brukertilgang

### Operator

Operatorer har tilgang til:

* vise klienter

* vise installert programvare

* vise tilgjengelige oppdateringer

* opprette og kjøre oppdateringsjobber

* vise oppdateringshistorikk

* bruke pakkeadministrasjon

* utføre systemvedlikehold

Operatorer har ikke tilgang til:

* brukeradministrasjon

* rolleadministrasjon

* opprettelse eller deaktivering av klienter

* rotasjon av klienttokener

### Viewer

Viewers har skrivebeskyttet tilgang til:

* klienter

* installert programvare

Følgende funksjonalitet er utilgjengelig for Viewers:

* håndtering av tilgjengelige oppdateringer

* oppdateringsjobber

* oppdateringshistorikk

* pakkeadministrasjon

* systemvedlikehold

* andre tilstandsendrende administrative operasjoner

Serveren håndhever disse begrensningene uavhengig.
Brukeradministrasjon

LUMS tilbyr brukeradministrasjon til kontoer med tillatelsen users.manage.

Brukere med denne tillatelsen kan opprette kontoer ved hjelp av en rollemal og deretter tildele tillatelser individuelt eller eksplisitt bruke malen. Nye kontoer starter uten tillatelser; tillatelseseditoren åpnes etter opprettelsen. Brukeradministratorer kan også lagre private administrative notater som ikke er synlige for kontoeieren.

Administratorer med backups.manage kan opprette validerte .db- eller .db.gz-databasesikkerhetskopier i en serverkonfigurert katalog og velge en sikker undermappe innenfor den monterte plasseringen. Se administration.md og den innebygde Markdown-gjenopprettingsveiledningen for oppsett av Docker-lagring og gjenoppretting.

Brukerpassord lagres med Argon2-passordhashing i stedet for klartekst eller reversibel kryptering.

Brukeradministrasjonsoperasjoner er beskyttet av:

* autentisering

* tillatelsesbasert autorisasjon

* CSRF-beskyttelse

* inputvalidering

* kontroll av dupliserte brukere

* revisjonslogging

Brukeradministrasjonsgrensesnittet eksponeres ikke uten users.manage.
Øktsikkerhet

Administrativ autentisering bruker økthåndtering på serversiden.

Øktsikkerhet inkluderer:

* autentisert økttilstand

* tilbakekalling av økter

* CSRF-beskyttelse for tilstandsendrende forespørsler

* hastighetsbegrensning for innlogging

* håndheving av deaktiverte kontoer

* rollekontroller

Tilbakekalling av en økt ugyldiggjør den tilsvarende autentiserte tilstanden i stedet for bare å skjule brukergrensesnittet.
Hastighetsbegrensning for innlogging

Gjentatte mislykkede innloggingsforsøk er underlagt progressiv hastighetsbegrensning.

Gjeldende terskler er:
```text

5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

Den relevante tilstanden lagres i SQLite.

Vellykket autentisering sletter gjeldende feiltilstand.

Dette forhindrer at en enkel applikasjonsomstart kan brukes til å omgå innloggingsbeskyttelsen.
Sikkerhet for klienttokener

Hver registrerte klient har sitt eget autentiseringstoken.

Serveren lagrer tokenet som et SHA-256-sammendrag.

Det opprinnelige tokenet er ikke nødvendig for normal validering på serversiden.

Tokenrotasjon lar administratorer ugyldiggjøre en eksisterende legitimasjon og utstede en erstatning.

Dette skaper en klar livssyklus:

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

API-sikkerhet

LUMS validerer API-input før tilstandsendrende operasjoner utføres.

Sikkerhetskontroller inkluderer:

* autentisering

* autorisasjon per brukertillatelse

* CSRF-beskyttelse der det er aktuelt

* inputvalidering

* validering av pakkenavn

* strukturerte jobbhandlinger

* parameteriserte databasespørringer

* kontrollert feilhåndtering

Applikasjonen bruker ikke brukerleverte pakkenavn som ubegrensede skallkommandoer.
SQL-injeksjonsbeskyttelse

Databaseoperasjoner bruker parameteriserte SQL-setninger.

Brukerkontrollerte verdier settes ikke direkte sammen med SQL-spørringer.

Dette gjelder områder som:

* autentisering

* klientadministrasjon

* brukeradministrasjon

* pakkesøk

* oppdateringsjobber

* revisjonsdata

* resultatrapportering

Målet er å holde dataverdier atskilt fra SQL-instruksjoner.
Sikkerhetsbaseline for SQLite

Gjeldende produksjonskonfigurasjon for SQLite er:
```text

journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

Fremmednøkkelhåndheving aktiveres eksplisitt av applikasjonen for databaseforbindelser.

Gjeldende konfigurasjon bruker WAL-modus.

Databasen lagres i det vedvarende Docker-volumet i stedet for inne i applikasjonscontainerens engangsfilsystem.
Jobbgjenoppretting og sjekkpunkter

LUMS behandler oppdateringsjobber som vedvarende tilstandsmaskiner.

En jobb med flere pakker kan inneholde flere individuelle pakkeoperasjoner.

Hvert pakkeelement kan nå sin egen resultattilstand.

Hvis kjøringen avbrytes, kan gjenoppretting skille mellom:

```text
already successful
        │
        └── do not unnecessarily repeat

not completed
        │
        └── eligible for recovery
```

Dette reduserer risikoen for blindt å gjenta fullførte pakkeoperasjoner etter et avbrudd.
Kontrollert oppdateringskjøring

LUMS begrenser bevisst handlingene som kan forespørres gjennom API-et for oppdateringsjobber.

Støttede handlinger er:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Serveren validerer handlingen og relevant pakkeinformasjon før jobben opprettes.

Agenten tilordner deretter den strukturerte handlingen til den aktuelle pakkebehandleroperasjonen.

Dette unngår å gjøre oppdateringssystemet til en generisk mekanisme for ekstern kommandokjøring.
Pakkeoperasjoner

Pakkeoperasjoner utføres gjennom klientens native pakkebehandler.
Installasjon

Et validert pakkenavn sendes til pakkebehandlerabstraksjonen for installasjon.
Fjerning

Et validert pakkenavn sendes til pakkebehandlerabstraksjonen for fjerning.
Pakkeoppdatering

En spesifikk pakke kan oppdateres når klienten rapporterer den som en tilgjengelig oppdatering.
Systemoppdatering

Systemoppdateringsoperasjonen delegerer oppdateringsprosessen til den native pakkebehandleren.

Alle operasjoner returnerer strukturerte resultater til LUMS-serveren.
Sikkerhet for pakkebehandler

LUMS behandler pakkebehandleren som en privilegert lokal komponent.

Agenten forsøker derfor ikke å etterligne pakkebehandlerens atferd selv.

I stedet:

* validerer den den forespurte operasjonen

* velger den passende pakkebehandlerimplementasjon

* utfører den kontrollerte operasjonen

* fanger resultatet

* rapporterer resultatet til serveren

Distribusjonsspesifikk atferd forblir isolert inne i pakkebehandlerlaget.
Omstartshåndtering

Noen pakkeoperasjoner kan kreve omstart.

LUMS registrerer omstartskrav som en del av resultatene for oppdateringsjobber.

Dette lar administratorer skille mellom:

```text
Update completed
```

og:

```text
Update completed
Reboot required
```

Omstartskravet er derfor en del av driftstilstanden i stedet for å behandles som en urelatert varsling.
Revisjonslogging

LUMS vedlikeholder et applikasjonsrevisjonsspor for viktige administrative og sikkerhetsrelevante handlinger.

Eksempler inkluderer:

* autentiseringsrelaterte hendelser

* klientadministrasjon

* tokenoperasjoner

* brukeradministrasjon

* opprettelse av oppdateringsjobber

* sikkerhetsfølsomme tilstandsendringer

Revisjonslogging er atskilt fra vanlig diagnostisk logging.

Diagnostiske logger hjelper med feilsøking av applikasjonen.

Revisjonsoppføringer gir en administrativ historikk over relevante handlinger.
Sikkerhetsherding

Gjeldende distribusjon inkluderer flere lag med herding.
Containerherding

Produksjonscontaineren bruker:

* kjøring som ikke-root

* skrivebeskyttet rotfilsystem

* fjernede Linux-capabilities

* no-new-privileges

* begrensede midlertidige filsystemer

* skrivebeskyttet hemmelighetsmontering

* dedikert vedvarende datavolum

Nettverksherding

Applikasjonscontaineren er bundet til loopback på verten:
```text

127.0.0.1:5050
```

Applikasjonsporten eksponeres derfor ikke direkte som en LAN-tjeneste.

Ekstern tilgang håndteres gjennom HTTPS-omvendt proxy.

Brannmuren eksponerer ikke den interne applikasjonsporten.
Transportssikkerhet

Administrativ tilgang leveres gjennom HTTPS.

Den omvendte proxyen håndterer ekstern TLS-terminering.

HTTP-forespørsler omdirigeres til HTTPS.
Hemmeligheter og konfigurasjon

Følsomme kjøringslegitimasjoner holdes utenfor applikasjonens kildekodetre.

Produksjonshemmeligheten monteres inn i containeren som en skrivebeskyttet hemmelighetsfil.

Regler for repositorium og Docker-byggekontekst forhindrer at vanlige sikkerhetskopi-, hemmelighets-, database- og sertifikatartefakter utilsiktet kommer inn i bildebyggekonteksten.
Avhengighets- og byggesikkerhet

Produksjonens Python-avhengigheter er pinnet.

Produksjonens Python-basebilde er pinnet med digest.

Docker-byggekonteksten er begrenset gjennom .dockerignore.

Disse kontrollene forbedrer byggreproduserbarhet og reduserer utilsiktet inkludering av følsomme filer.
Status for sikkerhetsrevisjon

LUMS' sikkerhetsgjennomgang har dekket følgende områder:

* SQLite-fremmednøkkelhåndheving

* SQLite-kjøringskonfigurasjon

* oppdateringstidsavbrudd og prosesshåndtering

* hastighetsbegrensning for innlogging

* API-inputvalidering

* tilbakekalling av økter

* rotasjon av klienttokener

* offline/IP-håndtering

* jobbgjenoppretting og sjekkpunkter

* APT-robusthet

* Arch-omstartsdeteksjon

* enhets- og API-resultatvalidering

* simuleringstesting

* kontinuerlig integrasjon

* applikasjons- og revisjonslogging

* versjonering og utgivelseshåndtering

* RBAC

* økt- og CSRF-sikkerhet

* legitimasjonssikkerhet

* avhengighets- og byggesikkerhet

* Docker-/containerherding

* beskyttelse av hemmeligheter og byggekontekst

* HTTP-/transportssikkerhet

* filsystem-/kjøringstillatelser

* netteksponering

* repositoriumets artefakthygiene

Den gjenstående dokumentasjonsgjennomgangen håndteres separat som en del av den endelige utgivelsesklarhetsprosessen.
Testing og CI

LUMS inkluderer automatiserte tester som dekker kjerneatferd og sikkerhetskontroller.

Kjør hele testsettet fra repositoriets rot:
```bash

./.venv-test/bin/pytest -q
```

Antallet tester endres over tid. Det nødvendige resultatet er at hele settet fullføres vellykket uten feil. Testsettet inkluderer dekning for områder som:

* autentisering

* RBAC

* klientadministrasjon

* brukeradministrasjon

* pakkesøk

* oppdateringsjobber

* validering av jobresultater

* sikkerhetsatferd

* API-atferd

Kontinuerlig integrasjon kjører det automatiserte testsettet før endringer anses som klare.

En vellykket testkjøring er nødvendig, men tester er bare én del av utgivelsesprosessen.

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

Utviklingsstatus

LUMS er for tiden under aktiv utvikling.

Kjernearkitekturen for administrasjon, klientkjøringsmodellen, pakkeadministrasjon, RBAC, sikkerhetsherding og gjenopprettingsmekanismer er implementert.

Prosjektet anses bevisst ikke som en ferdig utgivelse bare fordi applikasjonen er funksjonell.

Utgivelsesklarhet krever også at den omkringliggende dokumentasjonen og driftsprosedyrene beskriver det samme gjeldende systemet.

Dette er grunnen til at dokumentasjonskonsistens behandles som en del av ingeniørprosessen i stedet for som en ettertanke.
Støttede systemer

LUMS er utformet for å administrere Linux-systemer som bruker støttede native pakkebehandlere.
### Debian / Ubuntu

Støttet pakkeadministrasjonsstakk:

```text
APT
dpkg
```

Klienten bruker den native Debian-pakkeadministrasjonsverktøykjeden for:

* pakkeinventar

* oppdateringsdeteksjon

* pakkesøk

* pakkeinstallasjon

* pakkefjerning

* pakkeoppdateringer

* systemoppdateringer

### Arch Linux

Støttet pakkeadministrasjonsstakk:

```text
pacman
```

Klienten bruker den native Arch-pakkeadministrasjonsverktøykjeden for:

* pakkeinventar

* oppdateringsdeteksjon

* pakkesøk

* pakkeinstallasjon

* pakkefjerning

* pakkeoppdateringer

* systemoppdateringer

Klientkrav

En administrert Linux-klient krever:

* en støttet Linux-distribusjon

* LUMS-agenten

* nettverkstilkobling til LUMS-serveren

* et registrert klienttoken

* en fungerende native pakkebehandler

* systemd for timer-/tjenestebaserte kjøringskomponenter

Klienten krever ikke at LUMS-serveren får direkte tilgang til pakkedatabasen.

Klienten utfører lokale pakkeoperasjoner og rapporterer resultatene til serveren.
Teknologistakk
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

Autentisering og sikkerhet

* Argon2-passordhashing

* økter på serversiden

* CSRF-beskyttelse

* rollemaler med tillatelser per bruker

* SHA-256-sammendrag for klienttokener

* HTTPS

* revisjonslogging

Klient

* Python

* systemd

* APT / dpkg

* pacman

* loginctl der inaktivitetstilstandsinformasjon er tilgjengelig

Prosjektstruktur

Repositoriet er organisert i separate server-, klient-, frontend- og testkomponenter.

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

Den nøyaktige repositoriumslayouten kan utvikle seg etter hvert som LUMS utvikles.

Den arkitektoniske separasjonen mellom server, agent, pakkebehandlerabstraksjon, frontend og tester er tilsiktet.
Serverapplikasjon

Flask-applikasjonen tilbyr det sentrale LUMS-API-et og nettgrensesnittet.

Ansvarsoppgavene inkluderer:

* autentisering

* autorisasjon

* økthåndtering

* klientadministrasjon

* brukeradministrasjon

* programvareinventar

* oppdateringsinventar

* pakkesøk

* oppdateringsjobber

* håndtering av jobresultater

* revisjonslogging

* databasepersistens

Applikasjonen serveres av Gunicorn inne i containeren.

Nginx gir det eksterne HTTPS-inngangspunktet.
## Agent

LUMS-agenten installeres direkte på administrerte Linux-klienter.

Gjeldende agentversjon:

```text id="w8p4wz"
1.7.0
```

Agenten er ansvarlig for klientsidedelen av LUMS' kjøringskjede.

Ansvarsoppgavene inkluderer:

* rapportere klienttilstand

* samle inn installert programvare

* oppdage tilgjengelige oppdateringer

* søke etter pakker

* utføre pakkeoperasjoner

* rapportere jobresultater

* oppdage omstartskrav

* håndtere inaktivitetstilstandsinformasjon

* delta i jobbgjenoppretting

Agenten tilbyr ikke et ubegrenset eksternt skall.
Pakkebehandlerlag

Pakkebehandlerimplementasjonen isolerer distribusjonsspesifikk atferd fra resten av agenten.

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

Dette lar det overordnede oppdateringsjobbsystemet arbeide med strukturerte operasjoner uten å måtte kjenne hver distribusjonsspesifikke kommando.
Overvåker

LUMS-kjøringsovervåkeren overvåker jobber som forventes utført på klienten.

Gjeldende overvåker-versjon:

```text id="7k6w3s"
1.2.1
```

Overvåkeren opererer sammen med agenten og jobbtilstanden på serversiden.

Denne arkitekturen lar LUMS oppdage kjøringssituasjoner der en jobb forblir ventende eller på annen måte krever oppmerksomhet.
systemd-integrasjon

Klienten bruker systemd for planlagt og kontrollert kjøring.

Relevante komponenter inkluderer tjeneste- og timer-enheter for:

* klientrapportering

* oppdateringsdeteksjon

* jobbkjøring/-overvåking

Dette gir forutsigbar kjøring uten å kreve en kontinuerlig kjørende forgrunnsprosess for hver periodiske operasjon.

Klientagenten kan også kjøres manuelt under installasjon og feilsøking.
Inaktivitetssensitiv kjøring

Inaktivitetssensitiv kjøring er utformet for å redusere forstyrrelser for aktive brukere.

Gjeldende inaktivitetsterskel er:

```text id="g8v0lq"
300 seconds
```

Klienten bestemmer inaktivitetstilstand ved hjelp av tilgjengelig lokal øktinformasjon.

Der det støttes, brukes loginctl.

Agenten skiller mellom:

```text id="6v3m4k"
confirmed idle
active
idle state unavailable
```

En utilgjengelig inaktivitetstilstand tolkes ikke stille som inaktiv.

Dette gjør kjøringsbeslutningen eksplisitt og diagnostiserbar.
Livssyklus for oppdateringsjobb

Den fullstendige livssyklusen til en oppdateringsjobb kan representeres som:

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

En jobb lagres før kjøring.

Dette betyr at serveren beholder kunnskap om den tiltenkte operasjonen selv om klienten eller applikasjonen avbrytes.
Jobbtyper

LUMS støtter for tiden strukturerte oppdateringshandlinger inkludert:

```text id="v7r1f8"
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Disse handlingene er bevisst begrenset.

LUMS er et oppdateringsadministrasjonssystem, ikke et generelt rammeverk for ekstern kommandokjøring.
Jobbtilstand på pakkenivå

Jobber som inneholder flere pakker, kan spore fremdrift på pakkenivå.

For eksempel:

```text id="v9w1sh"
Job #42

package-a → SUCCESS
package-b → SUCCESS
package-c → FAILED
package-d → PENDING
```

Gjenoppretting kan derfor operere på de ufullstendige delene av jobben i stedet for blindt å gjenta vellykkede pakkeoperasjoner.
Jobbgjenoppretting

Gjenoppretting er utformet rundt vedvarende sjekkpunkter.

Serveren vedlikeholder jobbtilstanden.

Klienten rapporterer resultater på pakkenivå.

Hvis kjøringen avbrytes, kan serveren fastslå hvilket arbeid som allerede er fullført, og hvilket arbeid som fortsatt er kvalifisert for gjenoppretting.

Det tiltenkte gjenopprettingsprinsippet er:

* Fortsett fra kjent tilstand i stedet for å anta at ingenting skjedde.

Resultatvalidering

Klientjobresultater valideres før de godtas i vedvarende servertilstand.

Dette beskytter jobbtilstanden mot ugyldige eller ufullstendige resultatinnsendinger.

Validering brukes på relevante felt som:

* jobbidentitet

* kjøringstilstand

* pakkeresultatdata

* feilinformasjon

* omstartsinformasjon

Resultatbehandlingslaget fungerer derfor som en annen grense mellom en autentisert klient og vedvarende servertilstand.
Brukeradministrasjon

Brukeradministrasjon krever tillatelsen users.manage.

Autoriserte brukere kan opprette brukere fra en rollemal og tilpasse de individuelle tillatelsene som er tildelt hver konto.

Gjeldende roller er:

```text id="2xqv79"
Administrator
Operator
Viewer
```

Brukeradministrasjonshandlinger autentiseres, tillatelseskontrolleres, valideres, beskyttes mot CSRF der det er aktuelt, og registreres i revisjonssporet.
Klientadministrasjon

Administratorer kan administrere registrerte klienter.

Klientadministrasjonsfunksjoner inkluderer:

* registrering

* deaktivering

* tokenrotasjon

* inspeksjon av klientstatus

Klientautentisering er uavhengig for hver registrerte klient.

Deaktivering av en klient forhindrer den fra å fortsette normal autentisert kommunikasjon med serveren.
Oppdateringshistorikk

LUMS vedlikeholder vedvarende tilstand for oppdateringsjobber, slik at fullførte og mislykkede operasjoner forblir synlige etter kjøring.

Autoriserte brukere kan inspisere historikken for oppdateringsoperasjoner i henhold til sin rolle.

Historikken er ment å gi driftskontekst i stedet for bare å vise det nyeste pakkeinventaret.
Reviderbarhet

LUMS vedlikeholder to relaterte, men atskilte former for driftsinformasjon:
Applikasjonslogger

Brukes primært til:

* diagnostikk

* feil

* kjøringsadvferd

* feilsøking

Revisjonslogger

Brukes primært til:

* administrative handlinger

* sikkerhetsrelevante hendelser

* endringer i viktig tilstand

* ansvarlighet

Å holde disse konseptene atskilt gjør feilsøking og administrativ gjennomgang enklere.
Teststrategi

LUMS-testsettet dekker flere lag av applikasjonen.
Autentisering

Tester dekker autentiseringsatferd, økthåndtering og sikkerhetskontroller.
### RBAC

Tester verifiserer at:

* Administratorer kan utføre administrative handlinger

* Operatorer får sine tillatte administrasjonsfunksjoner

* Viewers forblir skrivebeskyttede

Pakkeadministrasjon

Tester dekker pakkesøkatferd og API-håndtering relatert til pakkeadministrasjon.
Oppdateringsjobber

Tester dekker:

* jobbopprettelse

* validering

* tilstandsoverganger

* resultathåndtering

* gjenopprettingsatferd

Sikkerhet

Tester dekker sikkerhetsfølsom applikasjonsatferd og regresjonstilfeller.
Fullt sett

Kjør hele testsettet fra repositoriets rot:
```bash

./.venv-test/bin/pytest -q
```

Testantallet endres etter hvert som prosjektet utvikler seg; stol på kommandoresultatet, ikke et fast antall trykket i dette dokumentet.
Kontinuerlig integrasjon

Prosjektet bruker kontinuerlig integrasjon til å kjøre automatiserte kontroller mot endringer.

CI-pipelinen hjelper med å oppdage regresjoner før endringer behandles som utgivelsesklare.

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
Dokumentasjon

LUMS vedlikeholder separat dokumentasjon for forskjellige driftsområder.
### README.md

Prosjektoversikt, arkitektur, funksjoner, sikkerhetsbaseline, utviklingsstatus og prosjektretning.
### install.md

Installasjon, distribusjon, klientoppsett, validering, oppgradering og fjerning.
### administration.md

Rutinemessig administrasjon, vedlikehold, sikkerhetskopier, oppgraderinger, driftsprosedyrer og nødadministrasjon.
### security.md

Sikkerhetsarkitektur, sikkerhetskontroller, revisjonsfunn, herding og sikkerhetsinformasjon for utgivelsesklarhet.
### troubleshooting.md

Diagnostiske prosedyrer for server, klient, jobber, pakkeadministrasjon, autentisering, database, container og nettverksproblemer.
### LUMS_Optional_Theme_System.md

Arkitektur og vedlikeholdsveiledning for valgfrie LUMS-frontendtemaer.

Dokumentasjonen er bevisst atskilt etter ansvar, slik at driftsinstruksjoner ikke blandes sammen med sikkerhetsdesign eller visuell tilpasning.
Dokumentasjonsprinsipp

Dokumentasjon behandles som en del av systemet.

En funksjon anses ikke som fullstendig ferdig når koden fungerer, men dokumentasjonen fortsatt beskriver en eldre arkitektur.

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

Dette er spesielt viktig for sikkerhetsfølsomme distribusjons- og administrasjonsprosedyrer.
Gjeldende status

LUMS er en aktivt utviklet plattform for Linux-oppdateringsadministrasjon.

Gjeldende implementasjon inkluderer:

* sentralisert klientadministrasjon

* programvareinventar

* oppdateringsdeteksjon

* pakkesøk

* pakkeinstallasjon og -fjerning

* pakkespesifikke oppdateringer

* systemoppdateringer

* vedvarende oppdateringsjobber

* jobbtilstand på pakkenivå

* jobbgjenoppretting

* omstartsdeteksjon

* inaktivitetssensitiv kjøring

* klienttokenautentisering

* tokenrotasjon

* administrativ autentisering

* rollebasert tilgangskontroll

* brukeradministrasjon

* revisjonslogging

* containerherding

* HTTPS-transport

* automatisert testing

* kontinuerlig integrasjon

Prosjektet er for tiden i den endelige dokumentasjons- og utgivelsesklarhetsfasen.
Sikkerhetsstatus

Hovedområdene for sikkerhetsrevisjonen er implementert og gjennomgått.

Gjeldende sikkerhetsbaseline inkluderer:
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

Sikkerhet behandles som et pågående ingeniøransvar i stedet for en engangs-sjekkliste.
Utgivelsesstatus

LUMS hevder for tiden ikke en stabil produksjonsutgivelsesversjon.

Det finnes for tiden:

* ingen endelig semantisk versjon

* ingen stabil utgivelsestag

* ingen GitHub-utgivelse

Prosjektet følger bevisst utgivelsessekvensen:

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

Den første offisielle utgivelsen bør bare opprettes etter at gjeldende implementasjon, sikkerhetsrevisjon, dokumentasjon og regresjonstesting anses som fullstendige.
Veikart

Veikartet er bevisst fokusert på stabilitet og vedlikeholdbarhet i stedet for å legge til funksjoner uten å fullføre det eksisterende fundamentet.
Gjeldende fase

* fullfør dokumentasjonsgjennomgangen

* fjern gjenværende dokumentasjonsinkonsistenser

* avslutt dokumentasjonsrevisjonsarbeidet

* utfør en siste full testkjøring

* verifiser CI

* forbered utgivelsesversjon

* opprett den første offisielle Git-taggen

* publiser den første GitHub-utgivelsen

Fremtidig utvikling

Potensielt fremtidig arbeid kan inkludere:

* flere Linux-distribusjoner

* flere pakkebehandlerbackender

* ytterligere UI-forbedringer

* ytterligere rapporteringsmuligheter

* utvidet driftsautomatisering

* ytterligere sikkerhetskontroller

* ytterligere testdekning

Fremtidige funksjoner bør bevare de eksisterende arkitektoniske grensene.
Hva LUMS ikke er

LUMS er bevisst ikke utformet som:

* et generelt eksternt skall

* en erstatning for APT, dpkg eller pacman

* en fullstendig konfigurasjonsadministrasjonsplattform

* en endepunktsadministrasjonspakke for alle operativsystemer

* en skybasert tjeneste

* et ukontrollert rammeverk for kommandokjøring

LUMS fokuserer på et smalere problem:

* Kontrollert Linux-programvare- og oppdateringsadministrasjon med vedvarende tilstand og reviderbarhet.

Utviklingsfilosofi

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

En funksjon anses ikke som fullstendig bare fordi den fungerer i utviklermiljøet.

Den bør også være:

* testet

* sikkerhetsgjennomgått

* dokumentert

* reproduserbar

* forståelig

* gjenopprettbar der det er aktuelt

Endringsfilosofi

Endringer bør gjøres bevisst.

En typisk endring bør svare på:

* Hvilket problem løser dette?

* Hvilken komponent bør eie endringen?

* Påvirker endringen sikkerheten?

* Påvirker den vedvarende tilstand?

* Påvirker den klienter?

* Krever den dokumentasjonsendringer?

* Hvilke tester beviser at eksisterende funksjonalitet fortsatt fungerer?

Dette reduserer risikoen for å fikse én del av systemet mens man stille ødelegger en annen.
Utviklingsarbeidsflyt

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

Sikkerhetsfølsomme endringer får ekstra verifisering før de anses som fullstendige.
Repositorium

Prosjektrepositoriet ligger på GitHub:

NovaForgeCtrl/LUMS

Repositoriet inneholder applikasjonskildekoden, klientkomponenter, tester, containerkonfigurasjon og prosjektdokumentasjon.
Dokumentasjonssett

Det gjeldende dokumentasjonssettet består av:

```text id="0xw7cy"
README.md
install.md
administration.md
security.md
troubleshooting.md
LUMS_Optional_Theme_System.md
```

Hvert dokument har et definert formål.

README gir prosjektoversikten på overordnet nivå.

Installasjonsveiledningen forklarer distribusjon.

Administrasjonsveiledningen forklarer løpende drift.

Sikkerhetsveiledningen dokumenterer sikkerhetsarkitekturen og revisjonsstatus.

Feilsøkingsveiledningen gir diagnostiske prosedyrer.

Dokumentet om valgfrie temaer dekker frontendtemaarkitektur.
Lisens

LUMS er utgitt under MIT-lisensen.

Lisensen er ment å holde prosjektet åpent og tilgjengelig samtidig som den tillater bruk, modifisering og videredistribusjon under lisensvilkårene.

Se repositoriets lisensfil for den fullstendige juridiske teksten.
Fellesskap og bidrag

LUMS er et åpen kildekode-prosjekt, og bidrag er velkomne.

Nyttige bidrag kan inkludere:

* feilrapporter

* sikkerhetsrapporter

* dokumentasjonsforbedringer

* tester

* pakkebehandlerstøtte

* frontendforbedringer

* backendforbedringer

* distribusjonsforbedringer

Bidrag bør bevare prosjektets arkitektoniske og sikkerhetsmessige prinsipper.
Sikkerhetsrapporter

Sikkerhetsproblemer bør ikke behandles som vanlige funksjonsforespørsler.

Når du rapporterer et sikkerhetsproblem, gi nok informasjon til å reprodusere og forstå problemet uten unødvendig å eksponere følsom informasjon.

Sikkerhetsrelaterte endringer bør gjennomgås nøye før de slås sammen.
Prosjektidentitet

LUMS er bygget rundt en enkel idé:

* Linux-oppdateringsadministrasjon uten støyen.

Prosjektet forsøker ikke å skjule kompleksitet ved å late som om Linux-pakkeadministrasjon er enkelt.

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
Endelig arkitektur

På sitt høyeste nivå kan LUMS forstås som fem lag:

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

UI gir interaksjon.

API håndhever policy.

SQLite gir vedvarende tilstand.

Agenten utfører kontrollert kjøring på klientsiden.

Den native pakkebehandleren utfører den faktiske systemendringen.
Endelig prinsipp

LUMS er bygget rundt ett sentralt prinsipp:

* Observer systemet. Kontroller endringen. Registrer resultatet.

Dette prinsippet gjelder for programvarearkitekturen, oppdateringskjøring, sikkerhetsmodellen, gjenopprettingsmekanismene og dokumentasjonen.

Linux-oppdateringsadministrasjon uten støyen.
