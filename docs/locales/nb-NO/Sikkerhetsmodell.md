# LUMS Sikkerhetsdokumentasjon

**LUMS — Linux Update Management Server**

Dette dokumentet beskriver gjeldende sikkerhetsarkitektur, implementerte sikkerhetskontroller, resultater fra sikkerhetsrevisjonen, driftsbegrensninger og sikkerhetsrelaterte designbeslutninger i LUMS.

Dokumentet gjenspeiler **den nåværende implementerte systemtilstanden**. Planlagte eller fremtidige forbedringer er eksplisitt identifisert som sådan.

---

# Sikkerhetsprinsipper

LUMS følger en dybdeforsvarstilnærming for Linux-oppdateringsadministrasjon.

Sikkerhetsmodellen skiller administrativ autentisering, klientautentisering, autorisasjon, kontrollert oppdateringskjøring og revisjonslogging.

De primære sikkerhetsmålene er:

* autentisert administrativ tilgang
* rollebasert autorisasjon
* autentisert klientkommunikasjon
* kontrollert oppdateringskjøring
* beskyttelse mot samtidig jobbkjøring
* gjenopprettbare oppdateringsjobber
* beskyttede hemmeligheter
* kontrollert containerkjøring
* reviderbare sikkerhetsfølsomme operasjoner
* forutsigbar feilhåndtering
* sikkerhetsregresjonstesting

LUMS er først og fremst ment for kontrollerte infrastruktur-, laboratorie- og interne nettverksmiljøer.

Det bør ikke eksponeres direkte mot det offentlige internett uten en ekstra sikkerhetsgjennomgang og passende nettverkskontroller.

---

# Sikkerhetsarkitektur

LUMS består av følgende sikkerhetsrelevante komponenter:

* Web-administrasjonsgrensesnitt
* REST API
* SQLite-database
* LUMS Agent på administrerte klienter
* APT- og pacman-pakkebehandlerbackender
* Oppdateringsjobb- og gjenopprettingsmekanismer
* Nginx HTTPS omvendt proxy
* Herdet Docker-container

Den grunnleggende administrasjonsflyten er:

Browser → HTTPS/Nginx → LUMS API → SQLite → LUMS Agent → Package Manager → Result → SQLite → Web UI

Autentisering og autorisasjon er bevisst atskilt.

En gyldig autentisert økt gir ikke automatisk tilgang til hver administrativ operasjon.

Autorisasjon håndheves på serversiden. Webgrensesnittet skjuler i tillegg funksjoner som ikke er tilgjengelige for gjeldende rolle, men UI-synlighet behandles aldri som en sikkerhetsgrense.

---

## Administrativ autentisering

Administrative brukere autentiserer seg gjennom LUMS-webgrensesnittet.

Passord lagres aldri i klartekst. LUMS bruker Argon2-basert passordhashing for passordlagring.

Administrative økter bruker:

* autentisert økthåndtering på serversiden
* øktutløp
* øktregenerering
* CSRF-beskyttelse for tilstandsendrende nettleserforespørsler
* hastighetsbegrensning for innlogging
* øktugyldiggjøring under utlogging
* server-side rollevalidering

Autentisering og autorisasjon forblir separate sikkerhetskontroller.

En vellykket autentisert bruker må fortsatt ha den nødvendige tillatelsen
for beskyttede operasjoner.

---

# Rollebasert tilgangskontroll

LUMS støtter for tiden tre web-brukerroller:

* `administrator`
* `operator`
* `viewer`

Rollemaler lagres i `users.role`; individuelle tillatelser lagres
på serversiden i `user_permissions`.

Serveren laster de effektive tillatelsene for hver autentiserte konto.
Informasjon om klienttillatelser styrer bare presentasjonen og erstatter
aldri autorisasjon på serversiden.

## Administrator

Administratorer har full administrativ og operativ tilgang.

De kan:

* vise klienter
* opprette klienter
* deaktivere klienter
* rotere klienttokener
* vise installerte pakker og tilgjengelige oppdateringer
* opprette oppdateringsjobber
* utføre støttede oppdateringsoperasjoner
* vise oppdateringsjobhistorikk
* bruke pakkeadministrasjon
* bruke systemvedlikeholdsfunksjoner
* administrere brukere
* administrere brukerroller
* få tilgang til administrative funksjoner

## Operator

Operatorer kan utføre operative oppdateringsadministrasjonsoppgaver.

De kan:

* vise klienter
* vise installerte pakker og tilgjengelige oppdateringer
* opprette oppdateringsjobber
* utføre støttede oppdateringsoperasjoner
* vise oppdateringsjobhistorikk
* bruke pakkeadministrasjon
* bruke systemvedlikeholdsfunksjoner

Operatorer kan ikke:

* administrere brukere
* endre brukerroller
* opprette klienter
* deaktivere klienter
* rotere klienttokener

## Viewer

Viewers har begrenset skrivebeskyttet tilgang.

De kan:

* vise klienter
* vise installert programvare

Følgende administrasjonsområder er skjult for Viewer-kontoer:

* Oppdateringer
* Oppdateringsjobber
* Oppdateringshistorikk
* Pakkeadministrasjon
* Systemvedlikehold

Viewer-kontoer kan ikke utføre tilstandsendrende oppdateringsadministrasjonsoperasjoner.

Serveren håndhever disse begrensningene uavhengig gjennom autentisering
og tillatelseskontroller per bruker.

---

# Klientautentisering

Hver administrert LUMS-klient bruker et individuelt Bearer-token.

Autentiseringsmekanismen følger modellen:

`Authorization: Bearer <CLIENT_TOKEN>`

Serveren lagrer ikke klienttokener som klartekstverdier.

I stedet lagrer LUMS et SHA-256 heksadesimalt sammendrag av klienttokenet.

Autentiseringsflyten er:

Client Token → SHA-256 → Token Digest → SQLite

Klientautentisering verifiserer det autentiserte tokenet mot den registrerte klienten og sjekker i tillegg den relevante klienttilstanden.

Sikkerhetsmodellen bruker ikke en kilde-IP-adresse som eneste bevis på klientidentitet.

Dette lar LUMS operere i:

* private laboratorienettverk
* isolert infrastruktur
* NAT-baserte nettverk
* offline-miljøer
* nettverk der klientadresser kan endre seg

Klienttokener kan roteres av autoriserte administratorer.

En tokenrotasjon genererer et erstatningstoken, lagrer bare sammendraget, ugyldiggjør det forrige tokenet, registrerer den administrative handlingen i revisjonsloggen og presenterer erstatningstokenet én gang.

Klartekstverdier for klienttokener skrives ikke til revisjonsoppføringer.

---

# Sikkerhetsrevisjon

Sikkerhetsrevisjonen utføres trinnvis.

Hvert revisjonsområde gjennomgås mot den faktiske implementasjonen, etterfulgt av automatiserte tester, isolert verifisering eller produksjonsverifisering der det er relevant.

Gjeldende revisjonsområder:

| Revisjon | Område                                   | Status                    |
| -------- | ---------------------------------------- | ------------------------- |
| #01      | SQLite Foreign Keys                      | PASS                      |
| #02      | SQLite Runtime Configuration             | PASS                      |
| #03      | Update Timeout Handling                  | PASS                      |
| #04      | Login Rate Limiting                      | PASS                      |
| #05      | API Input Validation                     | PASS                      |
| #06      | Session Revocation                       | PASS                      |
| #07      | Client Token Rotation                    | PASS                      |
| #08      | IP Address Handling / Offline Networks   | PASS                      |
| #09      | Job Recovery / Checkpointing             | PASS                      |
| #10      | APT Robustness                           | PASS                      |
| #11      | Arch Reboot Detection                    | PASS                      |
| #12      | Unit Tests / API Result Validation       | PASS                      |
| #13      | Simulation Tests                         | PASS                      |
| #14      | Continuous Integration                   | PASS                      |
| #15      | Application / Audit Logging              | PASS                      |
| #16      | Versjonering / utgivelser             | Slå opp gjeldende utgivelser og tagger |
| #17      | Role-Based Access Control                | PASS                      |

Utgivelsesinformasjon er tidsavhengig. Kontroller gjeldende GitHub-utgivelser og Git-tagger i repositoriet i stedet for å utlede status fra denne veiledningen. Sikkerhetsdokumentasjonen skal kontrolleres mot den faktiske implementasjonen og gjeldende konfigurasjon. Skill mellom implementerte kontroller, verifisert produksjonsatferd og planlagte forbedringer, og kontroller relevante tester mot revisjonen som skal distribueres.

# Sikkerhetsrevisjon #01

## SQLite Foreign Keys

SQLite-fremmednøkkelhåndheving er aktivert for applikasjonsdatabaseforbindelser.

Applikasjonen aktiverer eksplisitt:

`PRAGMA foreign_keys = ON`

Dette sikrer at referanseintegritet håndheves for relasjoner mellom relaterte databaseregistreringer.

Revisjonen verifiserte:

* håndheving av fremmednøkler ved kjøring
* fremmednøkkelintegritet
* klientlivssyklusatferd
* klientdeaktiveringsatferd
* bevaring av historisk jobbinformasjon
* bevaring av revisjonsinformasjon

Klienttilstand håndteres konservativt.

Der det er hensiktsmessig, deaktiveres klienter i stedet for å fjernes på en måte som ville ødelegge historisk driftsinformasjon.

**Status: PASS**

---

# Sikkerhetsrevisjon #02

## SQLite Runtime Configuration

Produksjons-SQLite-databasen ble gjennomgått for sin kjøringskonfigurasjon.

Den verifiserte produksjonskonfigurasjonen er:

* `journal_mode`: `wal`
* `busy_timeout`: `5000`
* `synchronous`: `2`

Applikasjonen aktiverer eksplisitt:

`PRAGMA foreign_keys = ON`

Produksjonsdatabasen bruker for øyeblikket WAL-modus.

Databasekonfigurasjonen ble dokumentert basert på den faktiske verifiserte produksjonstilstanden i stedet for den historiske utviklingskonfigurasjonen.

Den konfigurerte busy timeout reduserer umiddelbare databasefeil når en annen transaksjon midlertidig holder databasen.

Innstillingen for fremmednøkler på applikasjonsnivå sikrer referanseintegritet for hver databaseforbindelse.

Revisjonen inkluderte produksjonsverifisering av den aktive SQLite-konfigurasjonen.

**Status: PASS**

---

# Sikkerhetsrevisjon #03

## Update Timeout and Process Handling

Oppdateringskjøring er beskyttet mot pakkebehandlerprosesser som blokkerer på ubestemt tid.

Kjøringsflyten er:

Start process
↓
Read process output
↓
Monitor timeout
↓
Timeout reached?
↓
Terminate process
↓
Grace period
↓
Process still running?
↓
Kill process if required
↓
Complete job

Implementasjonen bruker kontrollert subprocess-håndtering slik at stille prosesser ikke kan blokkere på ubestemt tid mens de venter på utdata.

Tidsavbruddshåndtering ble testet mot:

* stille prosesser
* normal prosessfullføring
* tidsavbruddsforhold
* prosesser som er motstandsdyktige mot normal terminering
* kill-fallback
* tidsavbruddsatferd på integrasjonsnivå

Tidsavbruddsmekanismen forhindrer at en pakkeadministrasjonsoperasjon forblir på ubestemt tid i en aktiv tilstand.

Feil og tidsavbruddsforhold returneres som kontrollerte jobbresultater og registreres i jobbtilstanden.

Den gjeldende dokumenterte LUMS Agent-versjonen er:

`1.7.0`

**Status: PASS**

---

# Sikkerhetsrevisjon #04

## Login Rate Limiting

Administrative innloggingsforsøk er hastighetsbegrenset.

Gjeldende eskaleringspolicy er:

* 5 mislykkede forsøk → 30 sekunder
* 6 mislykkede forsøk → 60 sekunder
* 7 mislykkede forsøk → 120 sekunder
* 8 eller flere mislykkede forsøk → 300 sekunder

Tilstanden for hastighetsbegrensning lagres i SQLite.

Samtidige innloggingsfeil bruker transaksjonell databaselåsing med:

`BEGIN IMMEDIATE`

Dette forhindrer at samtidige autentiseringsfeil omgår den tiltenkte tilstanden for hastighetsbegrensning gjennom race conditions.

En vellykket autentisering sletter gjeldende feiltilstand.

Revisjonen dekket:

* isolert hastighetsbegrensningsatferd
* samtidige autentiseringsfeil
* transaksjonsrollback
* håndtering av databaselås
* tilbakestillingsatferd ved vellykket innlogging
* revisjonshendelser for hastighetsbegrensning
* produksjonsinnloggingsatferd

Hastighetsbegrenseren gir derfor en kontroll på serversiden mot gjentatte autentiseringsforsøk i stedet for å stole på klientsidens atferd.

**Status: PASS**

---

# Revisjonsstatus etter del 2

De fire første sikkerhetsrevisjonsområdene er fullført:

| Revisjon | Område                            | Status |
| -------- | --------------------------------- | ------ |
| #01      | SQLite Foreign Keys               | PASS   |
| #02      | SQLite Runtime Configuration      | PASS   |
| #03      | Update Timeout / Process Handling | PASS   |
| #04      | Login Rate Limiting               | PASS   |

Følgende revisjonsområder er dokumentert i de påfølgende avsnittene:

* #05 API Input Validation
* #06 Session Revocation
* #07 Client Token Rotation
* #08 IP Address Handling / Offline Networks
* #09 Job Recovery / Checkpointing
* #10 APT Robustness
* #11 Arch Reboot Detection
* #12 Unit Tests / API Result Validation
* #13 Simulation Tests
* #14 Continuous Integration
* #15 Application / Audit Logging
* #16 Versioning / Releases
* #17 Role-Based Access Control

Dokumentasjonen vedlikeholdes løpende mot faktisk implementasjon og konfigurasjon. Opplysninger om utgivelser og tagger må slås opp i repositoriet.

# Sikkerhetsrevisjon #05

## API Input Validation

LUMS validerer sikkerhetsfølsom API-input på serversiden.

Klientleverte verdier er ikke klarert bare fordi de kommer fra det autentiserte webgrensesnittet eller en registrert klient.

Validering brukes på relevante API-parametere, inkludert:

* klientidentifikatorer
* pakkenavn
* oppdateringsjobbhandlinger
* pakkelister
* søkeparametere
* brukeradministrasjonsparametere
* klienttokenoperasjoner
* jobbresultatdata

Pakkenavn valideres før de sendes til pakkeadministrasjonsoperasjoner.

API-et for oppdateringsjobber godtar bare eksplisitt støttede handlinger.

De for øyeblikket støttede pakkerelaterte handlingene er:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Uventede handlinger avvises.

Pakkelister valideres før jobbopprettelse.

For `UPDATE_PACKAGE` må den forespurte pakken også være til stede i klientens informasjon om tilgjengelige oppdateringer.

Databasespørringer bruker parameterisert SQL i stedet for å konstruere SQL-setninger fra uklarert input.

Dette forhindrer at brukerkontrollerte verdier tolkes som SQL-syntaks.

Revisjonen inkluderte negativ inputtesting og SQL-injeksjonsorienterte testtilfeller.

Valideringskontrollene ble også verifisert gjennom det automatiserte testsettet.

**Status: PASS**

---

# Sikkerhetsrevisjon #06

## Session Revocation

LUMS beskytter autentiserte administrative økter mot fortsatt bruk etter utlogging.

Økthåndtering inkluderer:

* autentiserte økter på serversiden
* øktutløp
* øktregenerering
* ugyldiggjøring ved utlogging
* autentiseringskontroller på serversiden
* rollevalidering på serversiden

Utlogging ugyldiggjør den aktive autentiserte økten.

Beskyttede API-endepunkter krever en autentisert økt og er ikke avhengige av klienttilstand for å avgjøre om brukeren fortsatt er autentisert.

Økttilstand evalueres derfor av serveren for beskyttede operasjoner.

Tilstandsendrende nettleserforespørsler krever i tillegg CSRF-beskyttelse.

Revisjonen verifiserte at:

* autentisert tilgang fungerer normalt
* beskyttede endepunkter avviser uautentiserte forespørsler
* utlogging ugyldiggjør den aktive økten
* en tidligere autentisert økt ikke kan fortsette å bruke beskyttet funksjonalitet etter tilbakekalling
* rolleinformasjon evalueres på serversiden

**Status: PASS**

---

# Sikkerhetsrevisjon #07

## Client Token Rotation

Hver administrert LUMS-klient bruker et individuelt autentiseringstoken.

Klienttokener lagres ikke som klartekstverdier.

I stedet lagrer LUMS SHA-256 heksadesimalt sammendrag av klienttokenet.

Autentiseringsmodellen er:

`Authorization: Bearer <CLIENT_TOKEN>`

Serveren hasher det angitte tokenet og sammenligner det resulterende sammendraget med det registrerte klienttokensammendraget.

Autoriserte administratorer kan rotere en klients token.

Tokenrotasjon utfører følgende operasjoner:

1. Generer et erstatningstoken.
2. Beregn dets SHA-256-sammendrag.
3. Erstatt det lagrede klienttokensammendraget.
4. Ugyldiggjør det forrige tokenet.
5. Registrer den administrative handlingen i revisjonsloggen.
6. Presenter erstatningstokenet for administratoren.

Det forrige tokenet kan ikke autentisere etter rotasjon.

Klarteksttokenverdier skrives ikke til revisjonslogger.

Revisjonen verifiserte:

* vellykket tokenautentisering
* lagring av tokensammendrag
* tokenrotasjon
* ugyldiggjøring av det forrige tokenet
* autentisering med erstatningstokenet
* autorisasjonskrav for tokenrotasjon
* revisjonslogging
* beskyttelse mot uautorisert rotasjon

Klienttokenrotasjon er begrenset til administratorer.

Operatorer og viewers kan ikke rotere klienttokener.

**Status: PASS**

---

# Sikkerhetsrevisjon #08

## IP Address Handling and Offline Networks

LUMS bruker ikke en klients kilde-IP-adresse som eneste bevis på klientidentitet.

Klientautentisering er basert på det registrerte klienttokenet.

Dette designet er tilsiktet fordi administrerte klienter kan operere i miljøer der nettverksadressen deres endres.

Støttede distribusjonsscenarier inkluderer:

* private laboratorienettverk
* NAT-baserte nettverk
* isolert infrastruktur
* klienter med dynamisk adressering
* offline-miljøer
* kontrollerte interne nettverk

Serveren skiller derfor:

**Nettverksplassering**

fra:

**Klientidentitet**

Et gyldig klienttoken identifiserer den registrerte klienten.

Klientens nettverksadresse kan fortsatt registreres for drifts- og revisjonsformål, men den behandles ikke som en autentiseringslegitimasjon.

Implementasjonen unngår også antakelser om at en klient må være tilgjengelig fra en fast adresse.

Dette er spesielt viktig for laboratoriemiljøer og infrastruktur der nettverkstopologien kan endres uten å endre den logiske identiteten til det administrerte systemet.

Revisjonen verifiserte klientautentisering uten å stole på en fast kilde-IP-adresse.

**Status: PASS**

---

# Revisjonsstatus etter del 3

Følgende sikkerhetsrevisjonsområder er fullført:

| Revisjon | Område                                 | Status |
| -------- | -------------------------------------- | ------ |
| #01      | SQLite Foreign Keys                    | PASS   |
| #02      | SQLite Runtime Configuration           | PASS   |
| #03      | Update Timeout / Process Handling      | PASS   |
| #04      | Login Rate Limiting                    | PASS   |
| #05      | API Input Validation                   | PASS   |
| #06      | Session Revocation                     | PASS   |
| #07      | Client Token Rotation                  | PASS   |
| #08      | IP Address Handling / Offline Networks | PASS   |

Neste avsnitt dekker:

* #09 Job Recovery / Checkpointing
* #10 APT Robustness
* #11 Arch Reboot Detection
* #12 Unit Tests / API Result Validation

# Sikkerhetsrevisjon #09

## Job Recovery and Checkpointing

LUMS-oppdateringsjobber er utformet for å gjenopprette trygt fra avbrutt kjøring.

Oppdateringsjobber vedlikeholder vedvarende tilstand i SQLite-databasen.

Individuelle pakkeoperasjoner spores separat fra den overordnede jobbtilstanden.

Dette lar agenten avgjøre hvilke pakkeoperasjoner som allerede er fullført vellykket før en avbrutt jobb gjenopptas.

Under gjenoppretting utføres ikke allerede vellykkede pakkeoperasjoner på nytt.

Gjenopprettingslogikken følger derfor prinsippet:

`Persistent Job State → Determine Completed Work → Skip Completed Items → Continue Remaining Work`

Dette reduserer risikoen for unødvendige gjentatte pakkeoperasjoner etter:

* agentavbrudd
* prosessterminering
* systemomstart
* midlertidig kommunikasjonsfeil
* containeromstart
* andre kjøringsavbrudd

Revisjonen verifiserte gjenoppretting av avbrutte jobber og sjekkpunktatferd.

Gjenoppretting ble testet med jobber som inneholdt flere pakkeoperasjoner og med tidligere vellykkede pakkeelementer.

Revisjonen bekreftet at fullført arbeid bevares, og at gjenstående arbeid kan fortsette uten unødvendig å gjenta vellykkede operasjoner.

**Status: PASS**

---

# Sikkerhetsrevisjon #10

## APT Robustness

Debian-baserte pakkeoperasjoner utføres gjennom LUMS-pakkebehandlerlaget.

APT-relaterte oppdateringsoperasjoner ble gjennomgått for pålitelig deteksjon av pakkebehandlertilstand og oppdateringsresultater.

Implementasjonen tar høyde for tilfeller der pakkeadministrasjonskommandoer kan returnere vellykket mens de krever ytterligere tolkning av utdataene eller den resulterende systemtilstanden.

APT-oppdateringsdeteksjon ble herdet for å unngå å stole på en enkelt simplistisk kommando-utdata-betingelse.

Revisjonen inkluderte testing av:

* normale APT-operasjoner
* tilgjengelige pakkeoppdateringer
* pakkeinstallasjon
* pakkefjerning
* oppdateringsjobbkjøring
* APT-resultathåndtering
* oppdateringsdeteksjonsatferd

Den tilsvarende herdingen ble committet som:

`c76f331 security: harden apt update detection`

Målet er å sikre at LUMS ikke feilaktig rapporterer pakkeadministrasjonstilstand utelukkende basert på ufullstendige eller tvetydige kommando-utdata.

**Status: PASS**

---

# Sikkerhetsrevisjon #11

## Arch Linux Reboot Detection

Arch Linux-pakkeoperasjoner kan resultere i en systemtilstand der en omstart er nødvendig eller anbefalt.

LUMS evaluerer derfor den resulterende systemtilstanden etter relevante pakkeadministrasjonsoperasjoner.

Agenten skiller normal fullføring av pakkeoperasjonen fra situasjoner der en omstart er nødvendig.

Omstartstilstanden rapporteres tilbake til LUMS-serveren som en del av jobbresultatet.

Dette lar administrasjonsgrensesnittet skille mellom:

* vellykket pakkeoperasjon
* vellykket operasjon med omstartskrav
* mislykket operasjon

Revisjonen verifiserte Arch Linux-omstartsdeteksjon ved hjelp av den faktiske pakkeadministrasjonskjøringsbanen.

Implementasjonen ble testet mot forhold der omstart er nødvendig, og normale fullføringsbetingelser.

**Status: PASS**

---

# Sikkerhetsrevisjon #12

## Unit Tests and API Result Validation

Sikkerhetsfølsom atferd er dekket av automatiserte tester.

Testsettet inkluderer dekning for autentisering, autorisasjon, API-validering, oppdateringsjobber, pakkeadministrasjon, klientautentisering og resultathåndtering.

Agent-til-server-resultatbanen ble spesielt gjennomgått for å sikre at jobbresultater ikke vilkårlig kan endre urelatert servertilstand.

Resultatbehandling validerer den innsendte informasjonen før den bruker tilstandsendringer på den tilsvarende oppdateringsjobben.

Valideringen dekker relevante resultatfelt og forventede jobbrelasjoner.

Dette forhindrer at en autentisert klient fritt kan velge urelaterte jobber eller injisere vilkårlig tilstand i oppdateringsjobbdatabasen.

Sikkerhetstestsettet dekker også negative og uautoriserte tilfeller.

Kjør det fullstendige automatiserte testsettet fra repositoriets rot med
`./.venv-test/bin/pytest -q`. Antallet tester endres over tid; bruk
resultatet av gjeldende kjøring i stedet for et fast antall i dette dokumentet.

De relevante sikkerhetskontrollene ble i tillegg verifisert gjennom fokuserte testkjøringer under revisjonen.

**Status: PASS**

---

# Revisjonsstatus etter del 4

Følgende sikkerhetsrevisjonsområder er fullført:

| Revisjon | Område                                 | Status |
| -------- | -------------------------------------- | ------ |
| #01      | SQLite Foreign Keys                    | PASS   |
| #02      | SQLite Runtime Configuration           | PASS   |
| #03      | Update Timeout / Process Handling      | PASS   |
| #04      | Login Rate Limiting                    | PASS   |
| #05      | API Input Validation                   | PASS   |
| #06      | Session Revocation                     | PASS   |
| #07      | Client Token Rotation                  | PASS   |
| #08      | IP Address Handling / Offline Networks | PASS   |
| #09      | Job Recovery / Checkpointing           | PASS   |
| #10      | APT Robustness                         | PASS   |
| #11      | Arch Reboot Detection                  | PASS   |
| #12      | Unit Tests / API Result Validation     | PASS   |

Neste avsnitt dekker:

* #13 Simulation Tests
* #14 Continuous Integration
* #15 Application / Audit Logging
* #16 Versioning / Releases

# Sikkerhetsrevisjon #13

## Simulation Tests

LUMS tilbyr en simuleringsmekanisme for testing av oppdateringsadministrasjonsarbeidsflyter uten å utføre den tilsvarende pakkeadministrasjonsoperasjonen på det administrerte systemet.

Simulering er implementert på agentens kjøringslag.

Når simulering er aktivert, representeres og behandles pakkeadministrasjonsoperasjoner uten å bruke den forespurte pakkeendringen på operativsystemet.

Dette lar oppdateringsjobbatferd testes uten å bevisst endre det administrerte systemet.

Simuleringstestene dekker relevante oppdateringsadministrasjonsbaner, inkludert:

* pakkeinstallasjon
* pakkefjerning
* pakkeoppdateringer
* systemoppdateringer
* jobbkjøring
* resultatrapportering
* vellykket fullføring
* feilhåndtering

Simuleringsmekanismen ble brukt under sikkerhetsrevisjonen for å verifisere jobbopprettelse, agentkjøring, resultathåndtering og tilstandsoverganger på serversiden uavhengig av reelle pakkeendringer.

Simuleringsmodus er en testmekanisme og erstatter ikke autorisasjonskontrollene for normale oppdateringsoperasjoner.

**Status: PASS**

---

# Sikkerhetsrevisjon #14

## Continuous Integration

LUMS bruker automatisert testing for å oppdage sikkerhets- og funksjonelle regresjoner før endringer anses som fullstendige.

CI-prosessen kjører det automatiserte testsettet mot prosjektet.

Testmiljøet verifiserer applikasjonen og sikkerhetsfølsom funksjonalitet uavhengig av produksjonscontaineren.

CI-prosessen inkluderer validering av:

* autentisering
* autorisasjon
* RBAC
* API-atferd
* håndtering av oppdateringsjobber
* pakkeadministrasjonsatferd
* klientautentisering
* validering av jobbresultater
* sikkerhetsfølsom feilhåndtering

CI-revisjonen ble gjennomgått etter sikkerhetsherdingsendringene.

Det endelige verifiserte testsettet ble fullført vellykket.

Testantallet endres etter hvert som prosjektet utvikler seg. CI gir en automatisert
regresjonsbarriere for sikkerhetsrelevante applikasjonsendringer.

**Status: PASS**

---

# Sikkerhetsrevisjon #15

## Application and Audit Logging

LUMS registrerer sikkerhetsfølsomme administrative og operative hendelser gjennom revisjonslogging på applikasjonsnivå.

Revisjonslogging er utformet for å gi en driftshistorikk uten å lagre sensitiv legitimasjon.

Relevante sikkerhetsfølsomme handlinger inkluderer hendelser som:

* autentiseringsrelaterte sikkerhetshendelser
* administrative handlinger
* klientadministrasjon
* klienttokenoperasjoner
* opprettelse av oppdateringsjobb
* kjøring av oppdateringsjobb
* sikkerhetsrelevante feil

Sensitivt legitimasjonsmateriale er utelatt fra revisjonsoppføringer.

Spesielt:

* passord logges ikke
* klartekst klienttokener logges ikke
* hemmelige verdier skrives ikke bevisst til revisjonsoppføringer

Revisjonsoppføringer er knyttet til relevant administrativ eller operativ kontekst der det er aktuelt.

Implementasjonen av revisjonslogging ble gjennomgått for:

* dekning av sikkerhetsfølsomme hendelser
* utelatelse av legitimasjon
* administrativ sporbarhet
* feilhåndtering
* bevaring av relevant revisjonsinformasjon

Loggesystemet er ment å støtte både operativ feilsøking og sikkerhetsundersøkelser.

**Status: PASS**

---

# Sikkerhetsrevisjon #16

## Versjonering og utgivelser

Versjonering og utgivelseshåndtering er gjennomgått som en del av sikkerhetsarbeidet. Utgivelsesstatus er tidsavhengig; slå opp gjeldende GitHub-utgivelser og Git-tagger i repositoriet i stedet for å utlede status fra denne veiledningen.

Gjeldende komponentversjoner inkluderer:

* LUMS Agent: `1.7.0`
* LUMS Watcher: `1.2.1`

Ikke anta at versjoner som er oppført her, eller sikkerhetsbaselinen ellers i dokumentet, beviser at en bestemt distribusjon har aktivert kontrollene. Operatører må verifisere sitt eget miljø.

---

# Revisjonsstatus etter del 5

Følgende sikkerhetsrevisjonsområder er fullført:

| Revisjon | Område                                 | Status                    |
| -------- | -------------------------------------- | ------------------------- |
| #01      | SQLite Foreign Keys                    | PASS                      |
| #02      | SQLite Runtime Configuration           | PASS                      |
| #03      | Update Timeout / Process Handling      | PASS                      |
| #04      | Login Rate Limiting                    | PASS                      |
| #05      | API Input Validation                   | PASS                      |
| #06      | Session Revocation                     | PASS                      |
| #07      | Client Token Rotation                  | PASS                      |
| #08      | IP Address Handling / Offline Networks | PASS                      |
| #09      | Job Recovery / Checkpointing           | PASS                      |
| #10      | APT Robustness                         | PASS                      |
| #11      | Arch Reboot Detection                  | PASS                      |
| #12      | Unit Tests / API Result Validation     | PASS                      |
| #13      | Simulation Tests                       | PASS                      |
| #14      | Continuous Integration                 | PASS                      |
| #15      | Application / Audit Logging            | PASS                      |
| #16      | Versjonering / utgivelser             | Slå opp gjeldende utgivelser og tagger |

De nummererte tekniske revisjonsområdene dekker kontrollene som er oppført i tabellen. Dokumentasjon vedlikeholdes løpende mot faktisk implementasjon og konfigurasjon. Opplysninger om utgivelser kontrolleres i repositoriets gjeldende utgivelser og tagger.

# Sikkerhetsrevisjon #17

## Role-Based Access Control

LUMS kombinerer rollemaler med individuelt tildelte tillatelser. De
støttede malene er `administrator`, `operator` og `viewer`; valg av en
mal velger dens standardtillatelser, som en administrator kan tilpasse
for hver konto.

Rollen forblir kontometadata. Beskyttede ruter autoriserer mot
kontoens serverlagrede tillatelsessett, ikke rolletiketten. Grensesnittet skjuler
utilgjengelige funksjoner for brukervennlighet, mens serveren forblir sikkerhetsgrensen.

---

## RBAC Permission Model

| Tillatelse        | Tilgang gitt |
| ----------------- | ------------ |
| `clients.view`    | Vise klienter og systeminformasjon |
| `software.view`   | Vise installert programvare |
| `updates.view`    | Vise tilgjengelige oppdateringer, jobber og historikk |
| `packages.search` | Søke i pakkerepositorier |
| `jobs.manage`     | Opprette pakkeoperasjoner og oppdateringsjobber |
| `clients.manage`  | Registrere/fjerne klienter og rotere klienttokener |
| `users.manage`    | Opprette brukere og administrere roller og tillatelser |

Standard rollemaler er:

| Mal             | Standardtillatelser |
| --------------- | ------------------- |
| `administrator` | Alle tillatelser |
| `operator`      | Klient-/programvare-/oppdateringssynlighet, pakkesøk og jobbadministrasjon |
| `viewer`        | Klientsynlighet og synlighet for installert programvare |

Klientrelaterte tillatelser krever `clients.view`. `jobs.manage` krever også
`updates.view`. UI laster tillatelser for den autentiserte kontoen og
utelater kontroller brukeren ikke kan bruke; kontroller på serversiden håndhever uavhengig
de samme tillatelsene.

---

## Authorization Enforcement

Beskyttede operasjoner bruker autentisering og tillatelseskontroller på serversiden.

Autorisasjonsmodellen følger prinsippet:

`Authenticate → Load User Permissions → Authorize Operation → Execute`

Autentisering alene er ikke tilstrekkelig for å få tilgang til privilegerte operasjoner.

Tilstandsendrende operasjoner krever i tillegg CSRF-beskyttelse der det er aktuelt.

Eksempler på beskyttede administrative operasjoner inkluderer:

* opprettelse av oppdateringsjobb
* pakkeinstallasjon
* pakkefjerning
* pakkeoppdateringer
* systemoppdateringer
* pakkeadministrasjonsoperasjoner
* klientopprettelse
* klientdeaktivering
* klienttokenrotasjon
* brukeropprettelse
* brukeradministrasjonsfunksjoner

Beskyttede endepunkter definerer eksplisitt tillatelsen som kreves for
den tilsvarende operasjonen.

En manglende tillatelse avvises av serveren selv om brukeren manuelt
konstruerer den tilsvarende HTTP-forespørselen.

Dette forhindrer omgåelse av RBAC-modellen ved å kalle et API-endepunkt som er skjult i webgrensesnittet direkte.

---

## Viewer Restrictions

Viewer-malen er bevisst begrenset av sitt standard tillatelsessett.

For kontoer uten de tilsvarende tillatelsene eksponerer klientgrensesnittet ikke:

* Oppdateringer
* Oppdateringsjobber
* Oppdateringshistorikk
* Pakkeadministrasjon
* Systemvedlikehold

Serveren forhindrer i tillegg kontoer uten de tilsvarende tillatelsene
fra å utføre beskyttede operasjoner.

JavaScript-grensesnittet laster ikke oppdateringsadministrasjonsdata uten
`updates.view`.

Dette reduserer unødvendig eksponering av driftsinformasjon samtidig som autorisasjon på serversiden opprettholdes som den faktiske sikkerhetskontrollen.

Installert programvare forblir tilgjengelig for Viewer-kontoer som en skrivebeskyttet informasjonsfunksjon.

---

## Administrative User Management

Brukeradministrasjon krever tillatelsen `users.manage`.

Brukere med den tillatelsen kan opprette kontoer uten tillatelser og deretter
tildele individuelle tillatelser eller bruke en rollemal i tillatelseseditoren.
Rollemaler har beskrivelser som forklarer deres standardtildelinger.

Autoriserte brukeradministratorer kan lagre et internt notat per konto. Notater er
begrenset til 2000 tegn, er ikke inkludert i revisjonsloggdetaljer og er
ikke synlige for kontoeieren.

Brukeropprettelse inkluderer:

* brukernavnvalidering
* rollevalidering
* passordvalidering
* Argon2-passordhashing
* deteksjon av dupliserte brukere
* revisjonslogging
* CSRF-beskyttelse
* autorisasjon på serversiden

Brukeradministrasjonsendepunkter er ikke tilgjengelige uten `users.manage`.

Serveren avviser ukjente tillatelser og ugyldige avhengighetskombinasjoner.
Minst én aktiv konto må beholde `users.manage`; endringer som ville
fjerne den siste brukeradministratoren, avvises.

Passord lagres aldri i klartekst.

---

## RBAC Database Migration

Informasjon om rollemal forblir i brukerdatabaseregistreringen. Individuelle
tillatelser lagres i `user_permissions`-tabellen med en fremmednøkkel til
brukerkontoen. Migrering `003-user-permissions` oppretter den tabellen og fyller
eksisterende kontoer fra deres gjeldende rollemal, og bevarer tilgangen deres
under overgangen. Migrering `004-user-admin-notes` legger til det private
`users.admin_note`-feltet; eksisterende kontoer mottar et tomt notat. Migrering
`005-backup-permission` gir `backups.manage` til eksisterende Administrator-
kontoer.

Opprettelse av databasesikkerhetskopi krever `backups.manage`; Administrator-
malen inkluderer denne tillatelsen som standard. Serveren skriver SQLite online-
sikkerhetskopier bare til den serverkonfigurerte `LUMS_BACKUP_DIR`; den godtar
ikke filsystembaner fra nettleseren. Sikkerhetskopifiler opprettes med kun eierens
tillatelser og kontrolleres for integritet før publisering.

---

## RBAC Security Testing

RBAC-atferd er dekket av automatiserte tester.

Testene inkluderer:

* Administratorautoritasjon
* Operatorautoritasjon
* Viewer-begrensninger
* beskyttet API-tilgang
* uautoriserte operasjoner
* klientadministrasjonsbegrensninger
* oppdateringsjobbebegrensninger
* brukeradministrasjonsbegrensninger
* synlighet på klientsiden
* tillatelsesspesifikk grensesnittatferd

RBAC-tester dekker rollemalstandarder, tilpassede tillatelser, tillatelses-
avhengigheter og autorisasjon på serversiden. Produksjonsverifisering bør
inkludere kontoer med tilpassede tillatelser samt standardmalene
Administrator, Operator og Viewer.

---

## RBAC Security Result

RBAC-implementasjonen gir lagdelt autorisasjon:

1. Autentisering etablerer brukeridentiteten.
2. Serveren laster brukerens tillatelser.
3. Beskyttede ruter håndhever den nødvendige tillatelsen.
4. CSRF-beskyttelse gjelder for relevante nettlesertilstandsendringer.
5. Webgrensesnittet skjuler utilgjengelig funksjonalitet.
6. Automatiserte tester verifiserer autorisasjonsgrenser.

Grensesnittet gir derfor ikke autorisasjonsmekanismen i seg selv.

Serveren forblir den autoritative sikkerhetsgrensen.

**Status: PASS**

## Dokumentasjonsgjennomgang

Sikkerhets- og driftsdokumentasjonen skal kontrolleres mot den faktiske implementasjonen og gjeldende konfigurasjon. Skill tydelig mellom implementerte kontroller, verifisert produksjonsatferd og planlagte forbedringer. Kontroller relevante tester mot revisjonen som skal distribueres.

Opplysninger om versjoner og utgivelser er tidsavhengige. Kontroller gjeldende GitHub-utgivelser og Git-tagger i repositoriet i stedet for å utlede status fra denne veiledningen.

# Ekstra sikkerhetsherding

Den nummererte sikkerhetsrevisjonen dekker de primære applikasjonssikkerhetskontrollene.

Ekstra herding ble utført etter den opprinnelige revisjonssekvensen og er en del av gjeldende sikkerhetsbaseline.

Disse kontrollene er dokumentert her fordi de representerer viktige sikkerhetsegenskaper ved gjeldende distribusjon.

---

## Containerherding

Produksjons-LUMS-containeren kjører med en herdet Docker-konfigurasjon.

Produksjonscontaineren bruker:

* applikasjonsbruker uten root
* skrivebeskyttet rotfilsystem
* fjernede Linux-capabilities
* `no-new-privileges`
* begrensede midlertidige filsystemer
* skrivebeskyttet hemmelighetsmontering
* dedikert vedvarende applikasjonsdatavolum
* omstartspolicy
* kun loopback-publisering av applikasjonsporten på verten

Applikasjonens rotfilsystem er derfor ikke skrivbart under normal drift.

Skrivbare plasseringer er eksplisitt begrenset til plasseringene som kreves av applikasjonen.

Produksjonscontaineren ble uavhengig inspisert for å verifisere den effektive kjøringskonfigurasjonen.

Den herdede kjøringen ble også testet ved å verifisere at:

* skriving til applikasjonsfilsystemet mislykkes
* `/tmp` forblir tilgjengelig der det er nødvendig
* `/var/lib/lums` forblir skrivbar
* hemmelighetsfilen forblir skrivebeskyttet
* applikasjonen forblir operativ

---

## Netteksponering

LUMS-applikasjonsporten er ikke direkte eksponert mot LAN.

Docker-applikasjonsporten er bundet til loopback-grensesnittet:

`127.0.0.1:5050`

Ekstern tilgang leveres gjennom Nginx.

Produksjonsverten eksponerer de tiltenkte nettverkstjenestene gjennom brannmuren og den omvendte proxyen.

Distribusjonen ble verifisert for å forhindre direkte ekstern tilgang til den interne Docker-applikasjonsporten.

Brannmuren bruker en standard-nekte-modell for innkommende og rutet trafikk.

De tiltenkte eksternt tilgjengelige tjenestene er:

* SSH
* HTTP
* HTTPS

HTTP-forespørsler omdirigeres til HTTPS av webserveren.

Standard Nginx-området ble fjernet slik at urelatert standardinnhold ikke eksponeres.

---

## Transportssikkerhet

Administrativ webtilgang leveres gjennom HTTPS.

HTTP omdirigeres til HTTPS.

TLS-endepunktet håndteres av Nginx i stedet for Flask/Gunicorn-applikasjonen direkte.

Dette holder transportssikkerhet og applikasjonsservering atskilt.

Den interne Gunicorn-applikasjonsporten er derfor ikke ment å være et offentlig HTTP-endepunkt.

Gjeldende distribusjon er ment for kontrollert intern infrastruktur.

En fremtidig distribusjon med direkte offentlig internett-eksponering vil kreve en ekstra sikkerhetsgjennomgang.

---

## Hemmeligheter og konfigurasjon

Produksjonshemmeligheter lagres ikke i applikasjonens kildekodetre.

LUMS-hemmelighetsnøkkelen leveres gjennom en beskyttet hemmelighetsfil.

Produksjonscontaineren mottar hemmeligheten gjennom:

`/run/secrets/lums_secret`

Hemmelighetsfilen monteres skrivebeskyttet.

Applikasjonen leser hemmeligheten gjennom den konfigurerte hemmelighetsfilmekanismen.

Håndtering av repositorium og Docker-byggekontekst ble gjennomgått for å forhindre utilsiktet inkludering av:

* databasefiler
* sikkerhetskopifiler
* hemmelighetsfiler
* private nøkler
* sertifikater
* kjøringslogger
* lokale sikkerhetskopiartefakter

Repositoriet ignorerer også vanlige midlertidige sikkerhetskopimønstre som brukes under utvikling.

---

## Avhengighets- og byggesikkerhet

Produksjons-Docker-bildet bruker en pinnet Python-basebilde-digest.

Produksjonskjøringsavhengighetene er eksplisitt versjonspinnet.

Det gjeldende produksjonsavhengighetssettet inkluderer:

* Flask `3.1.3`
* argon2-cffi `25.1.0`
* Gunicorn `23.0.0`

Docker-byggekonteksten er begrenset gjennom `.dockerignore`.

Gjentatte produksjonsbygg ble sammenlignet under revisjonen.

De relevante avhengighets- og pakkemetadataene forble konsistente mellom gjentatte bygg, bortsett fra forventede genererte Python-bytecode-forskjeller.

Dette gir en reproduserbar baseline for produksjonsbildet samtidig som byggekonteksten holdes begrenset.

---

## Filsystem- og kjøringstillatelser

Produksjonsapplikasjonen kjører som den dedikerte `lums`-brukeren i stedet for root.

Vedvarende applikasjonsdata lagres i det dedikerte LUMS-datavolumet.

Applikasjonens rotfilsystem er skrivebeskyttet.

Skrivetilgang under kjøring er begrenset til eksplisitt nødvendige plasseringer.

Produksjonskjøringen ble verifisert for å avvise uautoriserte skrivinger til applikasjonsfilsystemet.

Dette reduserer effekten av utilsiktet eller ondsinnet filmodifisering inne i applikasjonscontaineren.

---

# Konklusjon for sikkerhetsrevisjon

Den nåværende LUMS-implementasjonen har gjennomgått en bred sikkerhetsgjennomgang som dekker:

* autentisering
* autorisasjon
* RBAC
* øktsikkerhet
* CSRF-beskyttelse
* hastighetsbegrensning for innlogging
* klienttokensikkerhet
* API-validering
* SQL-injeksjonsmotstand
* SQLite-integritet
* oppdateringskjøring
* tidsavbruddshåndtering
* jobbgjenoppretting
* pakkeadministrasjonsrobusthet
* resultatvalidering
* simulering
* kontinuerlig integrasjon
* revisjonslogging
* containerherding
* netteksponering
* transportssikkerhet
* håndtering av hemmeligheter
* filsystemtillatelser
* avhengighets- og byggesikkerhet

De nummererte revisjonsresultatene er:

| Revisjon | Område                                 | Status                    |
| -------- | -------------------------------------- | ------------------------- |
| #01      | SQLite Foreign Keys                    | PASS                      |
| #02      | SQLite Runtime Configuration           | PASS                      |
| #03      | Update Timeout / Process Handling      | PASS                      |
| #04      | Login Rate Limiting                    | PASS                      |
| #05      | API Input Validation                   | PASS                      |
| #06      | Session Revocation                     | PASS                      |
| #07      | Client Token Rotation                  | PASS                      |
| #08      | IP Address Handling / Offline Networks | PASS                      |
| #09      | Job Recovery / Checkpointing           | PASS                      |
| #10      | APT Robustness                         | PASS                      |
| #11      | Arch Reboot Detection                  | PASS                      |
| #12      | Unit Tests / API Result Validation     | PASS                      |
| #13      | Simulation Tests                       | PASS                      |
| #14      | Continuous Integration                 | PASS                      |
| #15      | Application / Audit Logging            | PASS                      |
| #16      | Versjonering / utgivelser             | Slå opp gjeldende utgivelser og tagger |
| #17      | Role-Based Access Control              | PASS                      |

De tekniske sikkerhetskontrollene gjennomgått i revisjonene #01–#15 og #17 har bestått.

Resultater for tekniske sikkerhetskontroller gjelder den verifiserte revisjonen og er ikke en garanti for senere versjoner eller for en bestemt distribusjon. Operatører må kontrollere at sikkerhetskontrollene faktisk er aktivert i sitt eget miljø, og verifisere relevante tester og konfigurasjon ved distribusjon. Opplysninger om utgivelser og tagger må slås opp i repositoriet.

Ingen sikkerhetsrevisjonsresultat bør tolkes som en garanti for at LUMS er fri for sårbarheter.

Sikkerhet er en pågående prosess.

Endringer i applikasjonen, agenten, avhengigheter, containerkonfigurasjon, netteksponering, autentiseringsmodell eller distribusjonsarkitektur bør utløse en ny sikkerhetsgjennomgang av de berørte kontrollene.

---

# Sikkerhetsbaseline

Gjeldende sikkerhetsbaseline er basert på den verifiserte implementasjonen og produksjonsdistribusjonstilstanden.

Baselinen inkluderer:

* autentisering på serversiden
* RBAC på serversiden
* Argon2-passordhashing
* SHA-256 klienttokensammendrag
* CSRF-beskyttelse
* hastighetsbegrensning for innlogging
* parameterisert SQL
* validert API-input
* kontrollert pakkebehandlerkjøring
* gjenoppretting av oppdateringsjobber
* revisjonslogging
* herdet Docker-kjøring
* HTTPS gjennom Nginx
* kun loopback-eksponering av applikasjonsporten
* brannmurrestriksjoner
* beskyttede produksjonshemmeligheter
* pinnede produksjonsavhengigheter
* begrensede filsystemtillatelser
* automatisert sikkerhetstesting

Fremtidige endringer bør bevare disse egenskapene med mindre en bevisst arkitektonisk endring erstatter dem med en tilsvarende eller sterkere kontroll.

---

# Sikkerhetsvedlikehold

Sikkerhetskontroller bør revalideres når betydelige endringer introduseres.

Eksempler inkluderer:

* autentiseringsendringer
* nye brukerroller
* nye API-endepunkter
* pakkeadministrasjonsendringer
* agentkjøringsendringer
* databasemigreringer
* avhengighetsoppdateringer
* Dockerfile-endringer
* containerkjøringsendringer
* omvendt proxy-endringer
* brannmurendringer
* hemmelighetshåndteringsendringer
* utgivelsesforberedelse

Sikkerhetstesting bør utføres før publisering av en offisiell utgivelse.

Sikkerhetsdokumentasjonen bør oppdateres når den verifiserte sikkerhetsbaselinen endres.

---

# Oppslag av utgivelsesstatus

Utgivelsesstatus er tidsavhengig. Kontroller gjeldende GitHub-utgivelser og Git-tagger i repositoriet i stedet for å utlede status fra denne veiledningen. Sikkerhetsbaselinen dokumenterer implementasjonen som ble gjennomgått, men beviser ikke at kontrollene er aktivert i en bestemt distribusjon. Operatører må verifisere sitt eget miljø.

---

# Endelig uttalelse

LUMS er utformet som en kontrollert plattform for Linux-oppdateringsadministrasjon med sikkerhet som en kjerne-arkitektonisk bekymring.

Sikkerhetsmodellen er ikke avhengig av en enkelt beskyttelsesmekanisme.

I stedet fungerer autentisering, autorisasjon, validering, kontrollert kjøring, persistens, gjenoppretting, logging, containerisolasjon, nettverksrestriksjoner og automatisert testing sammen som lagdelte kontroller.

Prosjektet foretrekker bevisst eksplisitt håndheving på serversiden fremfor sikkerhet gjennom grensesnitt.

Gjeldende sikkerhetsbaseline er dokumentert i henhold til den verifiserte implementasjonstilstanden i stedet for historisk utviklingsatferd. Den er ikke en garanti for en bestemt distribusjon; operatører må verifisere miljøet sitt.

---

**LUMS — Linux-oppdateringsadministrasjon uten støyen.**

`segfault // override`
