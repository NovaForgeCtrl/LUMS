# LUMS Feilsøking

Denne veiledningen gir feilsøkingsprosedyrer for LUMS-serveren, Linux-agenter, kjøringsovervåkeren, oppdateringsjobber, autentisering, pakkeadministrasjon, databasen og Docker-distribusjonen.

Feilsøkingsprosessen bør alltid begynne med **observasjon før endring**.

Målet er å identifisere den første komponenten der forventet atferd stopper, uten å unødvendig endre konfigurasjon, databasetilstand, legitimasjon eller sikkerhetskontroller.

---

## Kom i gang: Feilsøk trygt

Hvis du er ny til Linux, betyr ikke en feil automatisk at data er tapt. Ikke endre flere ting samtidig. Start med sjekkene nedenfor og noter **når** problemet oppstår og **hvilken handling** som skjedde umiddelbart før det.

### Første sjekker på LUMS-serveren

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t

docker ps -a viser også stoppede containere. docker logs leser nylige applikasjonsmeldinger. systemctl status viser om Nginx kjører; nginx -t sjekker konfigurasjonen uten å endre den. Hvis nginx -t feiler, ikke last Nginx på nytt før årsaken er rettet.
Første sjekker på en administrert klient
bash

sudo systemctl status lums-agent.service --no-pager
sudo journalctl -u lums-agent.service -n 100 --no-pager
sudo systemctl status lums-agent-watcher.service --no-pager
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager

Agenten og overvåkeren er separate tjenester: en vellykket agentrapport beviser ikke at overvåkeren kan kjøre oppdateringsjobber. For en oneshot-tjeneste kan inactive være normalt etter en vellykket kjøring; sjekk også resultatet og loggmeldingene.
Før du deler kommando utdata

Sjekk logger og konfigurasjon for passord, klienttokener, økt- eller API-nøkler, private nøkler og personlig informasjon. Del aldri innholdet i hemmelighetsfiler eller komplette miljøvariabelverdier. Hvis du trenger hjelp, del bare de relevante feilmeldingene etter å ha fjernet sensitiv informasjon.

Ikke start med å slette databasen eller Docker-volumet, kjøre containeren som privilegert, deaktivere sikkerhetsvalg, fjerne pakkebehandlerlåsefiler eller rotere tokener. Disse handlingene kan skade data, slette bevis eller gjøre problemet verre. Hvis en sjekk feiler, lagre utdataene og fortsett til relevant avsnitt nedenfor.
1. Feilsøkingsfilosofi

LUMS består av flere uavhengige komponenter.

En vellykket klientrapport betyr ikke automatisk at oppdateringskjøring fungerer.

Den viktigste driftsbanen er:
text

Linux Client
    │
    ├── LUMS Agent
    │
    └── Execution Watcher
            │
            ▼
          HTTPS
            │
            ▼
        Nginx
            │
            ▼
        LUMS API
            │
            ▼
         SQLite

Oppdateringskjøring legger til pakkeadministrasjonslaget:
text

Browser
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Update Job
   │
   ▼
Execution Watcher
   │
   ▼
LUMS Agent
   │
   ▼
APT / pacman
   │
   ▼
Result
   │
   ▼
LUMS API
   │
   ▼
SQLite

Når du feilsøker, identifiser den første sviktende komponenten.

For eksempel:
text

Agent report fails
    ↓
Check agent service
    ↓
Check network
    ↓
Check TLS
    ↓
Check client token
    ↓
Check LUMS API

Ikke umiddelbart:

    endre databasen

    slett Docker-volumet

    installer agenten på nytt

    roter legitimasjon

    fjern pakkebehandlerlåsefiler

    deaktiver sikkerhetskontroller

    gjør containeren privilegert

Disse handlingene kan ødelegge nyttig diagnostisk informasjon eller skape flere problemer.
2. Diagnostisk baseline

Før du undersøker et spesifikt problem, fastslå gjeldende tilstand for hovedkomponentene.

Produksjons-LUMS-distribusjonen bruker:
text

Application port: 127.0.0.1:5050
External access: HTTPS through Nginx
Database: /var/lib/lums/lums.db
Docker volume: lums-data
Agent: 1.7.0
Watcher: 1.2.1

Produksjonscontaineren er herdet med:
text

Read-only root filesystem
No Linux capabilities
no-new-privileges
Non-root application user
Protected secret mount
Dedicated persistent data volume

Applikasjonsporten er bevisst bundet kun til den lokale verten.

Den forventede nettverksbanen er:
text

Client / Browser
       │
       ▼
     HTTPS
       │
       ▼
    Nginx :443
       │
       ▼
127.0.0.1:5050
       │
       ▼
 Docker container
       │
       ▼
    LUMS :5000

3. Første diagnostiske sjekker
3.1 Sjekk LUMS-containeren

På LUMS-serveren:
bash

sudo docker ps

lums-containeren skal kjøre.

For en fullstendig containeroversikt:
bash

sudo docker ps -a \
    --filter name=lums

Ikke fjern stoppede containere før du har undersøkt dem.

Eldre reservecontainere kan inneholde nyttig informasjon når du undersøker et distribusjonsproblem.
3.2 Sjekk nylige applikasjonslogger

Inspiser de nyeste LUMS-loggene:
bash

sudo docker logs \
    --tail 100 \
    lums

For direkte utdata:
bash

sudo docker logs \
    -f \
    lums

Når du undersøker en spesifikk forespørsel eller jobb, start logginspeksjonen før du reproduserer problemet der det er mulig.

Dette gjør det lettere å korrelere klienthandlingen med den tilsvarende hendelsen på serversiden.
3.3 Sjekk Nginx

Sjekk den omvendte proxyen:
bash

sudo systemctl status nginx \
    --no-pager

Valider konfigurasjonen:
bash

sudo nginx -t

En vellykket konfigurasjonstest skal rapportere:
text

syntax is ok
test is successful

Hvis Nginx ikke kjører, vil HTTPS-tilgang til LUMS normalt mislykkes selv når Docker-containeren selv er sunn.
3.4 Sjekk agenten

På en administrert Linux-klient:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

Inspiser nylige agentutdata:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

For en Type=oneshot-tjeneste kan en inaktiv tilstand etter en vellykket kjøring være normal.

Den viktige informasjonen er kjøringsresultatet.

En vellykket kjøring skal avsluttes med:
text

status=0/SUCCESS

3.5 Sjekk kjøringsovervåkeren

Overvåkeren er en separat komponent fra rapporteringsagenten.

Sjekk den uavhengig:
bash

sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager

Inspiser nylige utdata:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager

En vellykket agentrapport beviser derfor ikke at kjøringsovervåkeren fungerer korrekt.
3.6 Sjekk LUMS-timere

Sjekk alle relevante timere:
bash

sudo systemctl list-timers \
    --all | grep lums

De forventede timere inkluderer agent- og overvåkerplanleggingsmekanismene.

Hvis en timer mangler eller er inaktiv, inspiser den tilsvarende enheten før du endrer noe.
4. LUMS-containeren kjører ikke

Hvis lums-containeren ikke kjører, ikke gjenopprett den umiddelbart.

Inspiser først tilstanden:
bash

sudo docker ps -a \
    --filter name=lums

Inspiser deretter containeren:
bash

sudo docker inspect lums

Sjekk de nylige loggene:
bash

sudo docker logs \
    --tail 200 \
    lums

Sjekk avslutningstilstanden:
bash

sudo docker inspect \
    --format '{{.State.Status}} {{.State.ExitCode}}' \
    lums

Resultatet kan hjelpe med å skille mellom:
text

Normal shutdown
Application failure
Configuration failure
Container runtime failure
Health/startup problem

Hvis containeren avsluttet uventet, bevar loggene og containertilstanden før du erstatter den.
5. Containeren starter, men LUMS er ikke tilgjengelig

LUMS-applikasjonen er ikke ment å nås direkte gjennom Docker-applikasjonsporten fra nettverket.

Produksjonsapplikasjonen er bundet til:
text

127.0.0.1:5050

Verifiser portbindingen:
bash

sudo docker port lums

Sjekk også vertens lyttere:
bash

sudo ss -lntp | grep -E ':443|:5050'

Den forventede arkitekturen er:
text

HTTPS :443
    │
    ▼
  Nginx
    │
    ▼
127.0.0.1:5050
    │
    ▼
Docker
    │
    ▼
LUMS :5000

Hvis containeren kjører, men HTTPS feiler, undersøk lagene individuelt:

    Docker-container

    Lokal applikasjonsport

    Nginx-konfigurasjon

    TLS

    Brannmur/nettverksbane

Ikke eksponer port 5050 offentlig som en feilsøkingssnarvei.
6. Nginx returnerer en feil

Sjekk tjenesten:
bash

sudo systemctl status nginx \
    --no-pager

Valider konfigurasjonen:
bash

sudo nginx -t

Inspiser nylige Nginx-meldinger:
bash

sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager

Verifiser deretter at LUMS-containeren faktisk kjører:
bash

sudo docker ps

En feil fra den omvendte proxyen betyr ikke automatisk at LUMS-applikasjonen selv er ødelagt.

Mulige feilplasseringer inkluderer:
text

Browser
   ↓
TLS
   ↓
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker
   ↓
LUMS

Test lagene separat i stedet for å endre flere komponenter samtidig.
7. HTTPS / TLS-problemer

Test først HTTPS-endepunktet:
bash

curl -I https://LUMS-SERVER/

Hvis sertifikatvalidering feiler, avgjør om problemet er:
text

Certificate
Certificate chain
Hostname
Trust store
Nginx configuration
Client CA configuration

Valider Nginx:
bash

sudo nginx -t

Hvis sertifikatet eller TLS-konfigurasjonen ble endret med vilje, last Nginx på nytt:
bash

sudo systemctl reload nginx

Test deretter igjen:
bash

curl -I https://LUMS-SERVER/

Klienter som bruker en privat sertifikatmyndighet, må stole på riktig CA-sertifikat.

Ikke deaktiver TLS-sertifikatvalidering som en permanent løsning.

En vellykket tilkoblingstest som omgår sertifikatvalidering beviser ikke at produksjons-TLS-konfigurasjonen er korrekt.
8. Agenttjenesten feiler

Sjekk tjenesten:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

Les den nylige journalen:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Start tjenesten på nytt bare etter å ha inspisert det forrige resultatet:
bash

sudo systemctl start \
    lums-agent.service

Sjekk deretter:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

og:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Se etter:
text

Configuration errors
Missing environment values
TLS errors
Authentication failures
API errors
Python exceptions
Package-manager errors

Ikke installer agenten på nytt bare fordi én enkelt kjøring mislyktes.
9. Agenten rapporterer at LUMS_TOKEN mangler

Agenten mottar normalt sin produksjonskonfigurasjon gjennom sin systemd-tjenestemiljø.

Hvis agenten startes manuelt fra et skall, lastes ikke systemd EnvironmentFile automatisk inn i det skallet.

Derfor:
bash

sudo /opt/lums-agent/agent.py --version

kan oppføre seg annerledes enn:
bash

sudo systemctl start \
    lums-agent.service

når tokenet utelukkende leveres gjennom systemd-konfigurasjon.

Når du undersøker autentiseringsproblemer, test den faktiske tjenesten først:
bash

sudo systemctl start \
    lums-agent.service

Inspiser deretter:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Ikke kopier produksjonstokener inn i skallkommandoer unødvendig.

Skriv aldri ut et produksjonstoken i en diagnostisk logg.
10. Agenten kan ikke nå serveren

Start med nettverkstilkobling:
bash

ping LUMS-SERVER

Test deretter HTTPS:
bash

curl -I https://LUMS-SERVER/

Hvis HTTPS fungerer, men agenten fortsatt feiler, undersøk:
text

Client configuration
Client token
TLS trust
API response
Client identity
Agent version

Inspiser agenten:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Inspiser samtidig serveren:
bash

sudo docker logs \
    --tail 200 \
    lums

Dette hjelper med å avgjøre om forespørselen når LUMS i det hele tatt.

Hvis klienten ser en tilkoblingsfeil og serveren ikke viser en tilsvarende forespørsel, undersøk nettverks- eller TLS-banen før du endrer applikasjonskonfigurasjonen.
11. Fortsett feilsøking

Hvis de grunnleggende server-, Docker-, Nginx-, TLS- og agentlagene fungerer, fortsett med:
text

Client Authentication
Token Rotation
Update Detection
Execution Watcher
Idle Detection
Pending Jobs

Neste avsnitt fortsetter med klientautentisering og tokenrelaterte problemer.
12. Klientautentisering

LUMS bruker klientspesifikk autentisering for agentkommunikasjon.

Når en klient registreres, mottar klienten legitimasjon som brukes for autentisert kommunikasjon med LUMS-serveren.

Autentiseringsfeil bør undersøkes uten å eksponere klienttokenet.
12.1 Klienten godtas ikke av LUMS

Hvis en agent rapporterer en autentiseringsfeil, inspiser først agentloggen:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Inspiser deretter LUMS-containerloggene:
bash

sudo docker logs \
    --tail 100 \
    lums

Se etter:
text

401 Unauthorized
403 Forbidden
Invalid client token
Unknown client
Authentication failure

En 401-respons indikerer generelt et autentiseringsproblem.

En 403-respons kan indikere at autentiseringen lyktes, men at den forespurte operasjonen ikke er tillatt.

Ikke roter tokenet umiddelbart.

Avgjør først om problemet er:
text

Wrong token
Wrong client ID
Disabled client
Incorrect server URL
TLS problem
Malformed request
Server-side authentication failure

12.2 Klienten eksisterer, men autentisering feiler

Verifiser at klienten fortsatt eksisterer i LUMS-administrasjonsgrensesnittet.

Ikke endre klientregistreringen bare fordi en agentforespørsel mislyktes.

Hvis klienten eksisterer, sammenlign den konfigurerte klientidentiteten med identiteten agenten bruker.

Selve produksjonstokenet må aldri skrives ut i diagnostiske utdata.

Bruk konfigurasjonsmetadata og tjenestestatus for feilsøking i stedet for å eksponere legitimasjon.
13. Rotasjon av klienttoken

Rotasjon av klienttoken ugyldiggjør det forrige tokenet og erstatter det med en ny legitimasjon.

Hvis et token ble rotert med vilje, må den berørte agenten motta det nye tokenet før den kan autentisere seg igjen.

Den forventede sekvensen er:
text

Administrator
    │
    ▼
Rotate client token
    │
    ▼
Old token becomes invalid
    │
    ▼
New token assigned to client
    │
    ▼
Agent configuration updated
    │
    ▼
Agent reports again

Hvis agenten fortsetter å bruke det gamle tokenet, vil autentiseringen mislykkes.
13.1 Etter tokenrotasjon

Sjekk agenttjenesten:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

Kjør deretter agenten gjennom systemd:
bash

sudo systemctl start \
    lums-agent.service

Inspiser resultatet:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Hvis autentiseringen fortsatt mislykkes, inspiser serverloggene:
bash

sudo docker logs \
    --tail 100 \
    lums

Ikke roter tokenet gjentatte ganger.

Gjentatt rotasjon kan gjøre det vanskeligere å avgjøre hvilken legitimasjon som for øyeblikket er distribuert på klienten.
14. Klienten er deaktivert

En deaktivert klient må ikke behandles som en aktiv administrert klient.

Hvis en agent som tilhører en deaktivert klient, forsøker kommunikasjon, inspiser autentiseringsresultatet på serversiden.

Sjekk:
text

Client identity
Client enabled state
Authentication result
Agent configuration

Ikke reaktiver klienten bare for å få en feil til å forsvinne.

Avgjør først hvorfor klienten ble deaktivert.
15. Oppdateringsdeteksjon

Oppdateringsdeteksjon består av flere uavhengige trinn.

Agenten må:

    utføre pakkebehandlerspørringen

    parse resultatet

    sende resultatet til LUMS

    LUMS må validere resultatet

    LUMS må lagre resultatet

    grensesnittet må vise gjeldende tilstand

En feil i et hvilket som helst trinn kan få oppdateringsinformasjonen til å se feil ut.

Den grunnleggende flyten er:
text

APT / pacman
     │
     ▼
Agent
     │
     ▼
HTTPS
     │
     ▼
LUMS API
     │
     ▼
SQLite
     │
     ▼
Web UI

15.1 Ingen oppdateringer vises

Avgjør først om klienten faktisk rapporterte vellykket.

Sjekk:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Inspiser deretter serveren:
bash

sudo docker logs \
    --tail 100 \
    lums

Hvis agenten fullførte vellykket, men ingen oppdateringer vises, undersøk API- og databasetilstanden før du endrer pakkebehandleren.
15.2 Debian / Ubuntu oppdateringsdeteksjon

Debian-pakkebehandleren bruker APT.

Når du undersøker APT-relaterte problemer, verifiser først at APT selv fungerer:
bash

sudo apt update

Ikke kjør pakkeoppgraderinger automatisk under feilsøking.

Formålet med denne testen er å avgjøre om repositoriummetadata kan oppdateres vellykket.

Hvis APT rapporterer repositorium-, DNS-, TLS-, signatur- eller låsefeil, løs det underliggende APT-problemet før du undersøker LUMS.
15.3 Arch Linux oppdateringsdeteksjon

Arch Linux bruker pacman.

Sjekk repositoriummetadata:
bash

sudo pacman -Sy

Bruk dette bare når oppdatering av repositoriummetadata faktisk er nødvendig for diagnostikken.

Ikke kombiner en unødvendig systemoppgradering med en diagnostisk test.

For pakkerelaterte feil, inspiser den nøyaktige pacman-utdataen før du endrer konfigurasjonen.
16. Tilgjengelige oppdateringer avviker mellom LUMS og klienten

Oppdateringsinformasjon kan endre seg mellom to observasjoner.

For eksempel:
text

Client reports updates
        ↓
Repository metadata changes
        ↓
Package is upgraded manually
        ↓
LUMS displays older information

Vurder derfor alltid tidsstempelet for den siste vellykkede klientrapporten.

En forskjell indikerer ikke automatisk et databaseproblem.

Sjekk:
text

Last Agent execution
Last successful report
Package-manager state
Repository metadata
Displayed update state

17. Pakkeadministrasjon

LUMS-pakkeadministrasjon er atskilt fra filteret for installerte pakker som vises på klientsiden.

Arbeidsflyten for pakkeadministrasjon er:
text

User
 │
 ▼
Package Search
 │
 ▼
LUMS API
 │
 ▼
Agent
 │
 ▼
APT / pacman
 │
 ▼
Search Result
 │
 ▼
LUMS API
 │
 ▼
Web UI

Installasjon, fjerning eller oppdatering av en pakke bruker den normale LUMS-jobb-mekanismen.

Den forventede kjøringsbanen er:
text

Package Action
     │
     ▼
Update Job
     │
     ▼
Execution Watcher
     │
     ▼
Agent
     │
     ▼
APT / pacman

17.1 Pakkesøk returnerer ingen resultater

Verifiser først at agenten er operativ:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

Inspiser deretter agentjournalen:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

For Debian-baserte klienter, verifiser APT-metadata.

For Arch-baserte klienter, verifiser pacman-repositoriummetadata.

Ikke anta at et tomt søkeresultat betyr at LUMS-databasen er tom.

Søket utføres gjennom klientens pakkebehandler.
17.2 Pakkesøk fungerer, men installasjon mislykkes

Et vellykket søk beviser bare at pakkebehandleren kunne finne pakken.

Det beviser ikke at installasjonen vil lykkes.

Mulige årsaker inkluderer:
text

Dependency conflicts
Repository changes
Package no longer available
Insufficient privileges
Package-manager lock
Disk-space problems
Network problems
Package-manager errors

Inspiser den tilsvarende oppdateringsjobben.

Agentjournalen skal inneholde pakkebehandlerresultatet.
18. Pakkeinstallasjonsjobber

Pakkeinstallasjon bruker den normale infrastrukturen for oppdateringsjobber.

Den relevante handlingen er:
text

INSTALL_PACKAGE

Når du feilsøker en installasjon:

    Sjekk jobbtilstanden i LUMS.

    Sjekk agentkjøringen.

    Sjekk pakkebehandlerutdataen.

    Sjekk det endelige resultatet rapportert til LUMS.

Ikke endre jobbstatusen manuelt i SQLite.

Den forventede livssyklusen er:
text

PENDING
   ↓
RUNNING
   ↓
SUCCESS

eller:
text

PENDING
   ↓
RUNNING
   ↓
FAILED

En mislykket pakkeinstallasjon skal forbli sporbar gjennom de normale jobb- og revisjonsmekanismene.
19. Pakkefjerningsjobber

Pakkefjerning følger samme jobblivssyklus.

Handlingen er:
text

REMOVE_PACKAGE

Når en fjerning mislykkes, inspiser:
text

Update job
Agent journal
Package-manager output
Final job result

Ikke fjern databaseregistreringer manuelt for å skjule en mislykket pakkeoperasjon.

En mislykket jobb er nyttig diagnostisk informasjon.
20. Pakkeoppdateringsjobber

En pakkespesifikk oppdatering bruker:
text

UPDATE_PACKAGE

Pakken må være kjent for LUMS som å ha en tilgjengelig oppdatering før jobben opprettes.

Hvis grensesnittet ikke tilbyr den forventede pakkeoppdateringen:

    oppdater oppdateringsinformasjonen

    verifiser pakkebehandlertilstanden

    verifiser resultatet for tilgjengelige oppdateringer

    inspiser serverloggene hvis tilstanden er inkonsistent

Ikke sett inn oppdateringsregistreringer manuelt i SQLite.
21. Systemoppdateringsjobber

En fullstendig systemoppdatering bruker:
text

UPDATE_SYSTEM

Dette er forskjellig fra:
text

UPDATE_PACKAGE

Systemoppdateringen kan påvirke flere pakker og kan kreve omstart avhengig av operativsystemet og den resulterende pakketilstanden.

Når du feilsøker en systemoppdatering, avgjør om feilen oppstod under:
text

Update preparation
Package-manager execution
Result collection
Reboot detection
Post-reboot reporting

22. Pakkebehandlerlåser

Pakkebehandlere kan nekte en operasjon når en annen pakkeadministrasjonsprosess allerede kjører.

Typiske eksempler inkluderer:
text

APT is already running
dpkg is locked
pacman is locked

Identifiser først prosessen som holder låsen.

Ikke slett låsefiler blindt.

En låsefil kan indikere at en annen pakkeadministrasjonsprosess legitimit er aktiv.

Fjerning av den mens en pakkeoperasjon kjører kan skade pakkeadministrasjonstilstanden.

Den riktige feilsøkingssekvensen er:
text

Lock error
   ↓
Identify active process
   ↓
Determine whether it is legitimate
   ↓
Wait or resolve the process safely
   ↓
Retry operation

23. Pakkebehandlerfeil vs. LUMS-feil

Skill alltid mellom en pakkebehandlerfeil og en LUMS-feil.

For eksempel:
text

APT fails
    ↓
Agent reports APT failure
    ↓
LUMS stores FAILED result

I dette tilfellet kan LUMS fungere korrekt selv om jobben mislyktes.

Motsatt:
text

APT succeeds
    ↓
Agent cannot report result
    ↓
LUMS never receives SUCCESS

Her kan pakkeoperasjonen ha lyktes mens LUMS' rapporteringsbane feilet.

Pakkebehandlerresultatet og LUMS-jobbresultatet må derfor undersøkes separat.
24. Nyttig diagnostisk separasjon

Når en pakkejobb mislykkes, klassifiser feilen først:
text

A. Package-manager failure
B. Agent execution failure
C. Agent reporting failure
D. Server/API failure
E. Database persistence failure
F. UI display problem

Denne klassifiseringen forhindrer at urelaterte komponenter endres.

En pakkebehandlerfeil bør ikke automatisk føre til en Docker-ombygging.

Et UI-visningsproblem bør ikke automatisk føre til sletting av databasen.

En autentiseringsfeil bør ikke automatisk føre til reinstallering av agenten.
25. Neste feilsøkingsområde

Hvis klientautentisering, oppdateringsdeteksjon og pakkeadministrasjon fungerer, er det neste diagnostiske området selve kjøringslivssyklusen:
text

Update Job
    ↓
Watcher
    ↓
Agent
    ↓
Execution
    ↓
Result
    ↓
Checkpoint / Recovery
    ↓
Final Job State

Neste avsnitt dekker kjøringsovervåker, inaktivitetsdeteksjon, jobbtilstand, gjenoppretting og omstartshåndtering.
26. Kjøring av oppdateringsjobb

LUMS-oppdateringsjobber utføres asynkront gjennom agenten og kjøringsovervåkeren.

Den normale kjøringsbanen er:
text

User
 │
 ▼
LUMS API
 │
 ▼
SQLite
 │
 ▼
Pending Job
 │
 ▼
Execution Watcher
 │
 ▼
Agent
 │
 ▼
Package Manager
 │
 ▼
Result
 │
 ▼
LUMS API
 │
 ▼
SQLite

En jobb som er synlig i grensesnittet, er ikke nødvendigvis allerede under utførelse.

Fastslå alltid gjeldende jobbtilstand først.
26.1 Jobben sitter fast i PENDING

Hvis en jobb forblir i PENDING, sjekk kjøringsovervåkeren før du undersøker agenten.

Sjekk overvåkeren:
bash

sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager

Inspiser nylige overvåkerutdata:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Sjekk deretter agenten:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

En ventende jobb indikerer normalt at kjøringsfasen ennå ikke har startet.

Mulige årsaker inkluderer:
text

Watcher is not running
Watcher timer is not running
Client is offline
Client is not idle
Client has not reported recently
Job is not eligible for execution yet

Ikke endre jobbstatusen manuelt i SQLite.
27. Jobben sitter fast i RUNNING

En RUNNING-jobb indikerer at kjøringen har startet.

Avgjør først om agenten faktisk utfører jobben.

Sjekk:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Inspiser deretter overvåkeren:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

En kjørende jobb kan ta litt tid avhengig av:
text

Package count
Repository speed
Network latency
Package-manager operations
System load
Reboot requirements

Ikke avslutt en aktiv pakkeoperasjon bare fordi grensesnittet ikke er oppdatert ennå.

Avgjør først om den underliggende prosessen fortsatt er aktiv.
28. Jobben er FAILED

En mislykket jobb indikerer ikke nødvendigvis en LUMS-serverfeil.

Avgjør hvilket lag som produserte feilen.

Inspiser:
text

Job state
Agent execution result
Package-manager result
Server logs
Agent logs

Hovedkategoriene er:
text

Package-manager failure
Agent execution failure
Agent reporting failure
Server/API failure
Authentication failure
Recovery failure

Den opprinnelige feilen bør bevares når det er mulig.

Ikke erstatt en mislykket jobb med en manuelt opprettet vellykket registrering.
29. Jobben er SUCCESS, men pakken ble ikke endret

En vellykket LUMS-jobb betyr at den forespurte operasjonen ble fullført i henhold til agentresultatet.

Hvis den forventede pakketilstanden ikke samsvarer med jobbresultatet, verifiser klienten direkte.

For Debian-baserte systemer:
bash

dpkg-query -W \
    -f='${Package} ${Version}\n' \
    PACKAGE_NAME

For Arch Linux:
bash

pacman -Q \
    PACKAGE_NAME

Erstatt PACKAGE_NAME med pakken som undersøkes.

Sammenlign deretter den lokale pakketilstanden med LUMS-resultatet.

Mulige forklaringer inkluderer:
text

Package was changed after the job
Package name refers to a virtual/provided package
Package-manager output was interpreted differently than expected
The job result was generated before another local change

Ikke endre LUMS-databasen før avviket er identifisert.
30. Kjøringsovervåker

Kjøringsovervåkeren er ansvarlig for å oppdage jobber som er kvalifisert for kjøring.

Overvåkeren må behandles som en uavhengig komponent.

Sjekk tjenesten:
bash

sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager

Sjekk timeren:
bash

sudo systemctl list-timers \
    --all | grep lums

Inspiser journalen:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Hvis agenten fungerer, men jobber aldri starter, bør overvåkeren være en av de første komponentene som undersøkes.
31. Overvåkeren kjører, men utfører ikke jobber

En overvåkerkjøring betyr ikke automatisk at en jobb vil bli startet.

Jobben må oppfylle kjøringsbetingelsene.

Sjekk:
text

Client exists
Client is enabled
Client is reachable
Client has recent status
Client is eligible
Job is pending
Job is not already completed
Execution conditions are satisfied

Hvis klienten ikke er kvalifisert, kan overvåkeren korrekt la jobben forbli ventende.

Dette er ikke nødvendigvis en feil.
32. Inaktivitetsdeteksjon

LUMS kan bruke klientens inaktivitetinformasjon når den avgjør om en jobb skal kjøres.

Formålet er å unngå å starte vedlikeholdsoperasjoner mens klienten aktivt brukes.

Inaktivitetsbeslutningen bør derfor behandles som en planleggingsbetingelse, ikke som en kjøringsfeil.

En klient kan rapportere vellykket mens den fortsatt anses som ikke-inaktiv.

Feilsøkingssekvensen er:
text

Agent reports
     ↓
Idle information available?
     ↓
Idle state acceptable?
     ↓
Job eligible?
     ↓
Watcher executes

32.1 Klienten rapporterer, men anses ikke som inaktiv

Sjekk agentjournalen:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Se etter den rapporterte inaktivitetinformasjonen.

Inspiser deretter overvåkeren:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Den viktige forskjellen er:
text

Agent communication successful

versus:
text

Client eligible for maintenance execution

Dette er separate tilstander.
33. Inaktivitetsdeteksjon er utilgjengelig

Noen systemer gir kanskje ikke all inaktivitetstilstandsinformasjon.

En utilgjengelig inaktivitetsmekanisme bør ikke automatisk tolkes som en ødelagt agent.

Fastslå den rapporterte funksjonaliteten først.

De relevante konseptene er:
text

Idle supported
Idle source
Idle state
Idle duration

Hvis plattformen ikke kan gi den forventede inaktivitetinformasjonen, undersøk agentens plattformspesifikke implementasjon i stedet for å endre serverdatabasen.
34. Gjenoppretting av oppdateringsjobb

LUMS bruker sjekkpunkter og gjenoppretting for å forhindre at avbrutte oppdateringsjobber behandles som fullførte.

En jobb kan avbrytes på grunn av:
text

Agent restart
Client reboot
Network interruption
Package-manager interruption
Server restart
Watcher restart
System failure

Gjenoppretting må skille mellom arbeid som allerede er fullført, og arbeid som fortsatt må utføres.

Prinsippet er:
text

Completed work remains completed.
Incomplete work remains recoverable.

35. Avbrutt jobb

Hvis en jobb ble avbrutt, inspiser tilstanden først.

Inspiser deretter agenten:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Inspiser overvåkeren:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Ikke marker jobben som vellykket manuelt.

Gjenopprettingsmekanismen skal avgjøre hvilke pakkeelementer som allerede er fullført.
36. Gjenoppretting gjentar en pakkeoperasjon

Når gjenoppretting utløses, bør allerede vellykkede pakkeelementer ikke utføres unødvendig på nytt.

Gjenopprettingsmodellen er basert på tilstand på elementnivå.

Konseptuelt:
text

Job
 ├── Package A → SUCCESS
 ├── Package B → SUCCESS
 ├── Package C → FAILED
 └── Package D → PENDING

Gjenoppretting bør bevare de vellykkede elementene og fortsette med det gjenværende arbeidet.

Hvis denne atferden ser ut til å være feil, inspiser jobb- og pakkeelementhistorikken før du endrer databasen.
37. Klienten starter på nytt under en oppdatering

En omstart kan avbryte agentprosessen.

Den forventede gjenopprettingsbanen er:
text

Update starts
    ↓
Package operation
    ↓
Client reboot
    ↓
Agent starts again
    ↓
State is reported
    ↓
LUMS evaluates recovery

En omstart betyr derfor ikke automatisk at jobben mislyktes permanent.

Inspiser agenttjenesten etter at klienten kommer tilbake:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

Inspiser deretter nylige kjøringer:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

38. Omstartsdeteksjon

Omstartsdeteksjon brukes til å avgjøre om en systemomstart skjedde som en del av en oppdateringsoperasjon.

Dette er spesielt relevant når en oppdatering endrer pakker som krever en omstart.

For Arch Linux må omstartsdeteksjon ikke forveksles med pakkebehandlerens avslutningsstatus.

En pakkeoperasjon kan lykkes mens systemet fortsatt krever omstart.

Når du feilsøker omstartshåndtering, sammenlign:
text

Package operation result
Reboot requirement
Actual reboot state
Post-reboot Agent report
Final LUMS job state

39. Jobbresultatet ble ikke rapportert

Hvis pakkeoperasjonen ser ut til å ha fullført, men LUMS ikke viser det endelige resultatet, undersøk rapporteringsbanen.

Sjekk agenten:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Sjekk deretter serveren:
bash

sudo docker logs \
    --tail 200 \
    lums

Hvis agenten rapporterer en feil mens pakkeoperasjonen selv lyktes, klassifiser problemet som en rapporteringsfeil snarere enn en pakkeadministrasjonsfeil.
40. Serveromstart under jobbkjøring

En serveromstart må ikke automatisk behandles som bevis på at en oppdateringsoperasjon mislyktes.

Jobbtilstanden må evalueres etter at serveren blir tilgjengelig igjen.

Sjekk:
text

Container state
Database availability
Job state
Client state
Agent report
Watcher state

Gjenopprettingsmekanismen er ansvarlig for å avgjøre om avbrutt arbeid trygt kan fortsette.

Ikke skriv om jobbtilstander manuelt etter en serveromstart.
41. Databasen er tilgjengelig, men jobbtilstanden ser feil ut

Hvis SQLite er tilgjengelig, men jobbtilstanden virker inkonsistent, inspiser applikasjons- og revisjonsloggene før du endrer databasen.

Nyttig informasjon inkluderer:
text

Job ID
Client ID
Job action
Job creation time
Current state
Package-item states
Agent result
Recovery events
Audit events

Databasen er et applikasjonsdatalager, ikke et manuelt reparasjonsgrensesnitt.

Direkte endringer kan omgå validering, autorisasjon, revisjon og gjenopprettingslogikk.
42. Manuelle endringer av jobbtilstand

Manuelle SQL-endringer av oppdateringsjobbtilstand bør ikke brukes som normal feilsøking.

Unngå operasjoner som:
sql

UPDATE update_jobs ...

eller:
sql

DELETE FROM update_jobs ...

med mindre en kontrollert databasegjenopprettingsprosedyre eksplisitt krever det.

Hvis en databasegjennomgang virkelig er nødvendig, bevar en sikkerhetskopi og dokumenter den nøyaktige endringen før du bruker den.

Normale driftsproblemer bør løses gjennom applikasjons- og agentmekanismene.
43. Diagnostisk matrise for overvåker og agent

Bruk følgende matrise for å identifisere det mest sannsynlige laget:
Symptom	Første komponent å inspisere
Klienten kan ikke autentisere	Agent + LUMS API
Klienten rapporterer, men jobben forblir ventende	Kjøringsovervåker
Jobben blir kjørende, men fullføres ikke	Agent + pakkebehandler
Pakkeoperasjonen mislykkes	Pakkebehandler
Pakkeoperasjonen lykkes, men resultatet mangler	Agentrapportering
Klienten startet på nytt under oppdatering	Agent + gjenoppretting
Jobben forblir inkonsistent etter omstart	Gjenoppretting + databasetilstand
Jobben oppdages aldri	Overvåker + timer
Klienten er ikke kvalifisert	Inaktivitet / klienttilstand
Grensesnittet viser utdatert tilstand	API + siste klientrapport

Denne matrisen er et utgangspunkt, ikke en erstatning for å inspisere de faktiske loggene og jobbtilstanden.
44. Neste feilsøkingsområde

Etter å ha verifisert jobbkjøring, er de neste områdene:
text

SQLite and database state
RBAC and user management
Authentication sessions
Application and audit logging
Container security
Tests and CI

Disse områdene bør undersøkes separat fra pakkekjøring.
45. SQLite- og databasefeilsøking

LUMS bruker SQLite som applikasjonsdatabase.

Produksjonsdatabasen lagres inne i det vedvarende Docker-volumet:
text

/var/lib/lums/lums.db

Databasen administreres av applikasjonen og må normalt ikke endres manuelt.

Når du undersøker databaserelaterte problemer, avgjør først om problemet er:
text

Database availability
Database locking
Application configuration
Data consistency
Migration state
Application logic

46. Databasen er ikke tilgjengelig

Hvis LUMS rapporterer en databasefeil, sjekk først om containeren kjører:
bash

sudo docker ps

Inspiser deretter applikasjonsloggene:
bash

sudo docker logs \
    --tail 200 \
    lums

Ikke slett Docker-volumet umiddelbart.

Det vedvarende volumet inneholder produksjonsapplikasjonsdataene.

Sletting kan permanent fjerne:
text

Users
Clients
Client configuration
Update jobs
Audit data
Application state

47. SQLite-database låsing

SQLite-låseproblemer bør undersøkes gjennom applikasjonsloggene.

Inspiser:
bash

sudo docker logs \
    --tail 200 \
    lums

Produksjonsapplikasjonen bruker:
text

journal_mode = wal
busy_timeout = 5000
synchronous = 2

Applikasjonen aktiverer også SQLite-fremmednøkkelhåndheving på databaseforbindelsene.

En databaselås betyr ikke automatisk at databasen er korrupt.

Mulige årsaker inkluderer:
text

Concurrent writes
Long-running transaction
Application process still using the database
Unexpected process termination
Filesystem problem

Ikke slett SQLite-journalfiler manuelt.
48. SQLite-fremmednøkler

LUMS aktiverer eksplisitt SQLite-fremmednøkkelhåndheving på applikasjonsnivå.

Dette betyr at relasjoner mellom databaseregistreringer valideres av SQLite når applikasjonsforbindelsen etableres.

Hvis en fremmednøkkelrelatert feil oppstår, inspiser applikasjonsloggene først.

Ikke deaktiver fremmednøkkelhåndheving for å få en operasjon til å lykkes.

En fremmednøkkelfeil kan indikere et problem med applikasjonslogikk eller dataintegritet.
49. SQLite-databaseintegritet

Hvis databasekorrupsjon mistenkes, stopp med å gjøre unødvendige endringer først.

Bevar gjeldende tilstand og inspiser applikasjonsloggene.

En kontrollert integritetskontroll kan utføres mot en kopi av databasen.

Ikke utfør destruktive reparasjonsoperasjoner direkte mot produksjonsdatabasen med mindre en dokumentert gjenopprettingsprosedyre krever det.

Det generelle prinsippet er:
text

Preserve
   ↓
Inspect
   ↓
Verify
   ↓
Recover
   ↓
Validate

Start aldri med:
text

Delete database
Recreate database
Recreate Docker volume

50. Databasemigreringer

LUMS bruker applikasjonsmigreringer for å introdusere endringer i databaseskjemaet.

Når et migreringsproblem oppstår, inspiser containerloggene:
bash

sudo docker logs \
    --tail 200 \
    lums

Se etter:
text

Migration failure
SQL error
Duplicate column
Missing table
Constraint error
Migration already applied

Ikke rediger migreringsregistreringer manuelt med mindre migreringssystemet spesifikt krever en kontrollert gjenopprettingsprosedyre.

En migrering som allerede er brukt, bør normalt ikke kjøres manuelt igjen.
51. Databasevolum

LUMS-databasen lagres i det vedvarende Docker-volumet:
text

lums-data

Inspiser volumet:
bash

sudo docker volume inspect \
    lums-data

Volumet må forbli vedvarende på tvers av normal containerombygging.

Selve applikasjonscontaineren er engangs.

Applikasjonsdataene er det ikke.

Derfor:
text

Container
    ≠
Persistent database

Å gjenopprette containeren må ikke forveksles med å gjenopprette datavolumet.
52. Database diskplass

SQLite krever tilgjengelig filsystemplass for normal drift.

Sjekk vertens filsystem:
bash

df -h

Sjekk også inode-tilgjengelighet:
bash

df -i

Lav diskplass kan produsere databasefeil som først ser ut som applikasjonsproblemer.

Hvis databasen plutselig blir skrivebeskyttet eller skriving begynner å mislykkes, verifiser filsystemkapasiteten før du endrer SQLite-konfigurasjonen.
53. RBAC-feilsøking

LUMS bruker rollebasert tilgangskontroll.

Gjeldende roller er:
text

Administrator
Operator
Viewer

Tillatelsene er bevisst forskjellige.
53.1 Administrator

Administratorer kan:
text

View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
Create and disable clients
Rotate client tokens
Manage users
Manage roles

Administratorbare operasjoner inkluderer brukeradministrasjon og rolleadministrasjon.
53.2 Operator

Operatorer kan:
text

View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance

Operatorer kan ikke:
text

Manage users
Manage roles
Create or disable clients
Rotate client tokens

53.3 Viewer

Viewers har bevisst begrenset tilgang.

En Viewer kan:
text

View clients
View installed software

Følgende funksjonalitet er skjult for Viewer-grensesnittet og blokkert på serversiden:
text

Available Updates
Update Jobs
Update History
Package Management
System Maintenance

Dette er en tilsiktet sikkerhetskontroll.

Hvis en Viewer kan få tilgang til en av disse funksjonene, behandle problemet som et RBAC-problem snarere enn bare et UI-problem.
54. Viewer ser for mye

Hvis en Viewer ser funksjonalitet som ikke skal være tilgjengelig, sjekk begge lag:
text

Browser UI
    +
Server-side authorization

Å skjule et element i JavaScript eller HTML er ikke tilstrekkelig sikkerhet.

API-et må også avvise uautoriserte operasjoner.

Når du undersøker:

    Fastslå den autentiserte brukerens rolle.

    Identifiser det berørte endepunktet.

    Sjekk serverresponsen.

    Inspiser applikasjonsloggene om nødvendig.

    Verifiser den relevante RBAC-testen.

Ikke løs et autorisasjonsproblem ved bare å skjule UI-elementet.
55. Viewer kan ikke se forventede data

En Viewer skal fortsatt kunne få tilgang til informasjonen som eksplisitt er tillatt av gjeldende RBAC-modell.

Hvis tillatt klientinformasjon mangler:
text

Verify login
   ↓
Verify role
   ↓
Verify client visibility
   ↓
Inspect API response
   ↓
Inspect browser console if necessary

Ikke gi flere tillatelser bare fordi en side for øyeblikket ser ufullstendig ut.

Avgjør først om den manglende informasjonen er tilsiktet begrenset.
56. Operator kan ikke utføre en operasjon

Hvis en Operator mottar 403 Forbidden, avgjør først om den forespurte handlingen er Administrator-bare.

Operatørtilgang inkluderer ikke:
text

User management
Role administration
Client creation/deactivation
Client token rotation

Hvis operasjonen skal være tillatt for Operatorer, inspiser endepunktets autorisasjonsdekoratør og tilsvarende RBAC-tester.

Ikke forfrem brukeren midlertidig til Administrator som en diagnostisk snarvei.
57. Administrator kan ikke utføre en operasjon

En Administrator skal ha tilgang til alle for øyeblikket støttede administrative operasjoner.

Hvis en Administrator mottar en autorisasjonsfeil:
text

Verify authenticated session
        ↓
Verify current role
        ↓
Verify endpoint authorization
        ↓
Inspect CSRF requirements
        ↓
Inspect application logs

For tilstandsendrende operasjoner er det kanskje ikke tilstrekkelig med en gyldig økt alene.

CSRF-beskyttelse må også oppfylles der det er nødvendig.
58. Brukeradministrasjon

Brukeradministrasjon er begrenset til Administratorer.

Arbeidsflyten for brukeradministrasjon er:
text

Administrator
    │
    ▼
User Management
    │
    ├── Create user
    ├── Assign role
    └── Enable / disable user

Når en bruker ikke kan opprettes, sjekk:
text

Current role
Username validation
Role validation
Duplicate username
Password validation
CSRF protection
Application logs

Ikke opprett brukere direkte i SQLite.

Direkte databaseinnsetting omgår passordhashing, validering, autorisasjon og revisjonslogging.
59. Opprettelse av bruker mislykkes

Hvis opprettelse av bruker mislykkes, inspiser nettleserresponsen og serverloggene.

API-et skal validere:
text

Username
Role
Password requirements
Duplicate account
Authenticated administrator
CSRF token

Hvis forespørselen avvises, avgjør hvilken valideringsregel som ble utløst.

Ikke svekk valideringen bare for å få én kontoopprettelsesforespørsel til å lykkes.
60. Passordproblemer

LUMS lagrer brukerpassord ved hjelp av en passordhashingsmekanisme i stedet for klartekstpassord.

Hvis en bruker ikke kan logge inn:
text

Verify username
   ↓
Verify account enabled state
   ↓
Verify password
   ↓
Check login rate limiting
   ↓
Inspect authentication logs

Lagre eller logg aldri klartekstpassord.

Ikke kopier passord inn i diagnostiske kommandoer eller loggfiler.
61. Deaktivert brukerkonto

En deaktivert konto må ikke behandles som en aktiv innloggingskonto.

Hvis en deaktivert bruker fortsatt kan autentisere seg, undersøk:
text

Current account state
Authentication lookup
Session state
Session revocation
Browser session
Server-side authorization

Ikke bare slett kontoen.

Å bevare kontoen kan være viktig for revisjonshistorikken.
62. Øktproblemer

LUMS bruker økthåndtering på serversiden.

Når en bruker ser ut til å ha utdatert eller uventet tilgang, logg ut først og etabler en ny økt.

Hvis problemet vedvarer, undersøk:
text

Account state
Role
Session state
Session revocation
Cookie configuration
CSRF protection

Ikke deaktiver øktsikkerhetskontroller for å omgå et innloggingsproblem.
63. Tilbakekalling av økt

Tilbakekalling av økt er relevant når:
text

A password changes
A user is disabled
A role changes
A session must be invalidated
A security event requires forced logout

Hvis en bruker ser ut til å beholde tilgang etter en kontoendring, avgjør om den eksisterende økten ble korrekt ugyldiggjort.

Test med en fersk nettleserøkt først etter å ha bekreftet kontotilstanden.

Ikke anta at sletting av nettlesercookies alene beviser at tilbakekalling av økt på serversiden fungerer.
64. Hastighetsbegrensning for innlogging

LUMS bruker hastighetsbegrensning på gjentatte mislykkede autentiseringsforsøk.

Gjeldende atferd bruker økende utlåsingsintervaller:
text

5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds

Feiltilstanden lagres i SQLite.

Hvis innloggingsforsøk uventet blokkeres, inspiser autentiseringstilstanden før du endrer databasen.

En hastighetsbegrensningsrespons er ikke automatisk en autentiseringsfeil.

Det kan indikere at kontoen har nådd den konfigurerte terskelen for mislykkede forsøk.
65. Innlogging fungerer, men API returnerer 403

En vellykket innlogging beviser autentisering, ikke autorisasjon.

En 403 Forbidden-respons kan indikere:
text

Insufficient role
Missing CSRF protection
Disallowed operation
Disabled functionality

Identifiser det nøyaktige endepunktet før du endrer noe.

Det riktige feilsøkingsspørsmålet er:
text

"Is this user authenticated?"

etterfulgt av:
text

"Is this authenticated user authorized for this operation?"

Dette er separate sikkerhetskontroller.
66. CSRF-feil

Tilstandsendrende nettleserforespørsler er beskyttet mot cross-site request forgery.

Hvis en tilstandsendrende forespørsel uventet mislykkes:
text

Verify authenticated session
        ↓
Verify CSRF token
        ↓
Verify request method
        ↓
Verify endpoint
        ↓
Inspect server response

Ikke deaktiver CSRF-beskyttelse som en feilsøkingsløsning.

En mislykket CSRF-kontroll er en sikkerhetskontroll som fungerer som tiltenkt.
67. Nettleserens UI og API er uenige

Hvis UI viser at en handling er tilgjengelig, men API avviser den:
text

Browser UI
   ↓
Displayed role/state
   ↓
API request
   ↓
Server-side authorization

Resultatet på serversiden er autoritativt.

UI kan inneholde utdatert tilstand etter:
text

Role changes
Session changes
Client changes
Page remains open for a long time

Last siden på nytt og etabler en ny økt før du antar at autorisasjonen på serversiden er feil.
68. RBAC diagnostisk matrise
Symptom	Første komponent å inspisere
Viewer ser administrasjonsgrensesnitt	Håndtering av rolle på klientsiden
Viewer API-forespørsel lykkes	RBAC på serversiden
Operator mottar 403	Endepunktets tillatelsesmodell
Administrator mottar 403	Økt / CSRF / endepunktautorisation
Bruker kan ikke opprettes	Administratorrolle + validering
Deaktivert bruker kan logge inn	Kontotilstand + økthåndtering
Innlogging midlertidig blokkert	Hastighetsbegrensning
Tilstandsendrende forespørsel avvist	CSRF / økt
UI og API er uenige	Nettlesertilstand + serverautorisasjon

Resultatet av autorisasjonen på serversiden er alltid viktigere enn om et grensesnittelement er synlig.
69. Neste feilsøkingsområde

De neste diagnostiske områdene er:
text

Application and audit logging
Container security
Filesystem permissions
Docker runtime configuration
Tests and CI
Diagnostic snapshots
Final recovery checklist

Disse områdene bør undersøkes uten å svekke sikkerhetsbaselinen.
70. Applikasjonslogging

LUMS bruker applikasjonslogging for å gi diagnostisk informasjon uten å eksponere sensitiv legitimasjon.

Når du undersøker et applikasjonsproblem, start med de nyeste loggene:
bash

sudo docker logs \
    --tail 200 \
    lums

For kontinuerlig overvåking:
bash

sudo docker logs \
    -f \
    lums

Når det er mulig, reproduser problemet mens du overvåker loggene.

Dette gjør det lettere å korrelere:
text

User action
    ↓
HTTP request
    ↓
Application event
    ↓
Database operation
    ↓
Agent interaction

71. Applikasjonslogger inneholder en feil

Identifiser først komponenten som produserte meldingen.

Typiske kilder inkluderer:
text

Flask application
Gunicorn
Database layer
Authentication
Authorization
Package management
Job execution
Client reporting

Ikke anta at den siste loggmeldingen er rotårsaken.

Se etter den første relevante feilen i hendelsessekvensen.

Når det er mulig, korreler:
text

Timestamp
Client
Request
Job ID
Error
Result

72. Revisjonslogging

LUMS registrerer sikkerhetsrelevante applikasjonshandlinger i revisjonsloggen.

Revisjonslogging er nyttig når du undersøker:
text

User changes
Authentication events
Administrative actions
Client management
Token operations
Update-job creation
Security-relevant state changes

En revisjonshendelse bør behandles som bevis på en applikasjonshendelse, ikke som en erstatning for systemlogger.

Bruk applikasjonslogger for tekniske kjøringsdetaljer og revisjonslogger for sikkerhetsrelevante applikasjonshandlinger.
73. Revisjonshendelse mangler

Hvis en forventet revisjonshendelse mangler:

    Identifiser den nøyaktige handlingen.

    Identifiser API-endepunktet.

    Verifiser at handlingen faktisk nådde serveren.

    Inspiser applikasjonsloggene.

    Avgjør om handlingen ble avvist før revisjonshendelsen skulle ha blitt opprettet.

Ikke sett inn revisjonsoppføringer manuelt bare for å få et revisjonsspor til å se komplett ut.

En revisjonsoppføring skal tilsvare en reell applikasjonshendelse.
74. Revisjonslogg og applikasjonslogg avviker

De to loggsystemene har forskjellige formål.

For eksempel:
text

Application log
→ technical execution information

Audit log
→ security-relevant application event

En pakkebehandlerfeil kan derfor vises i applikasjons- eller agentloggen uten å representere en separat administrativ revisjonshendelse.

Omvendt bør en brukeradministrasjonshandling produsere en reviderbar applikasjonshendelse selv om operasjonen i seg selv er teknisk enkel.
75. Sensitiv informasjon i logger

Plasser aldri følgende med vilje i diagnostiske utdata:
text

Client tokens
Application secret keys
Passwords
Session secrets
Private keys
TLS private material

Hvis en diagnostisk kommando vil eksponere en av disse verdiene, bruk en redigert eller kun-metadata-sjekk i stedet.

Når du deler logger for feilsøking, gjennomgå dem for hemmeligheter før du kopierer dem til saksbehandlingssystemer, dokumentasjon, GitHub-saker eller chat.
76. Docker-containersikkerhet

Produksjons-LUMS-containeren er bevisst herdet.

De forventede sikkerhetsegenskapene inkluderer:
text

Non-root application user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges enabled
No privileged mode
Dedicated writable data volume
Read-only secret mount
Restricted temporary filesystems

Hvis en av disse egenskapene endres uventet, behandle det som konfigurasjonsdrift.

Ikke svekk containeren for å løse et applikasjonsproblem med mindre sikkerhetspåvirkningen er eksplisitt vurdert.
77. Verifiser kjøringssikkerhet for containeren

Inspiser containeren:
bash

sudo docker inspect lums

For en fokusert kjøringssjekk:
bash

sudo docker inspect \
    --format='ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}' \
    lums

De forventede verdiene inkluderer:
text

ReadonlyRootfs=true
Privileged=false
CapDrop=[ALL]
SecurityOpt=[no-new-privileges:true]

Den nøyaktige formateringen kan variere mellom Docker-versjoner.

Selve sikkerhetsegenskapene er det som teller.
78. Containeren kjører som root

LUMS-applikasjonen skal kjøre som sin dedikerte uprivilegerte applikasjonsbruker.

Hvis containeren uventet kjører som root, inspiser først bildet og kjøringskonfigurasjonen:
bash

sudo docker inspect \
    --format='{{.Config.User}}' \
    lums

Inspiser deretter Dockerfile.

Ikke løs applikasjonstillatelsesproblemer ved å bytte produksjonscontaineren til root.

Hvis en katalog krever skrivetilgang, identifiser den nøyaktige banen og avgjør om den skal være vedvarende applikasjonsdata eller midlertidige data.
79. Skrivebeskyttet rotfilsystem

Produksjonscontaineren bruker et skrivebeskyttet rotfilsystem.

Dette beskytter applikasjonsbildet mot unødvendig kjøringsmodifisering.

Hvis applikasjonen rapporterer:
text

Read-only filesystem
Permission denied
Cannot create file
Cannot write temporary data

avgjør først hvor applikasjonen prøver å skrive.

Forventede skrivbare plasseringer er bevisst begrenset.

Vedvarende applikasjonsdata tilhører:
text

/var/lib/lums

Midlertidige kjøringsdata kan bruke de konfigurerte midlertidige filsystemene.

Ikke deaktiver --read-only bare fordi en applikasjonsbane uventet er skrivbar.
80. /tmp er ikke skrivbar

Hvis applikasjonen krever midlertidig lagring, verifiser det midlertidige filsystemet:
bash

sudo docker inspect \
    --format='{{json .HostConfig.Tmpfs}}' \
    lums

Produksjonscontaineren tilbyr en begrenset /tmp.

Det midlertidige filsystemet er kun ment for forbigående data.

Vedvarende data må ikke lagres der.
81. Problemer med hemmelighetsmontering

LUMS-applikasjonshemmeligheten leveres gjennom en beskyttet filmontering.

Hemmeligheten skal ikke bygges direkte inn i bildet.

Hvis LUMS rapporterer en manglende hemmelighet, inspiser først kjøringskonfigurasjonen:
bash

sudo docker inspect \
    lums

Sjekk at hemmelighetsmonteringen eksisterer og er skrivebeskyttet.

Ikke skriv ut innholdet i hemmeligheten.

En nyttig diagnostikk er å verifisere at filen eksisterer og har forventede tillatelser uten å vise innholdet.
82. Hemmelighetsfilen mangler

Hvis hemmelighetsfilen ikke eksisterer på verten, kan ikke containeren autentisere eller initialisere korrekt.

Avgjør først om den forventede hemmelighetsbanen eksisterer.

Ikke gjenopprett hemmeligheten tilfeldig.

En erstatningshemmelighet kan ugyldiggjøre eksisterende økter eller annen kryptografisk tilstand avhengig av hvordan applikasjonen bruker den.

Enhver tilsiktet hemmelighetserstatning må derfor behandles som en kontrollert sikkerhetsoperasjon.
83. Vedvarende volum er ikke skrivbart

Hvis LUMS ikke kan skrive applikasjonsdata, inspiser volumet:
bash

sudo docker volume inspect \
    lums-data

Inspiser deretter containermonteringene:
bash

sudo docker inspect \
    --format='{{json .Mounts}}' \
    lums

Applikasjonsdatabasen må ligge på det vedvarende skrivbare volumet.

Ikke gjør hele containerfilsystemet skrivbart som en løsning.

Den riktige løsningen er å identifisere den spesifikke banen som krever vedvarende lagring.
84. Docker-containeren starter, men applikasjonen feiler

Hvis containeren starter og umiddelbart avsluttes:
bash

sudo docker ps -a \
    --filter name=lums

Inspiser deretter:
bash

sudo docker logs \
    --tail 200 \
    lums

Vanlige årsaker inkluderer:
text

Application startup error
Missing secret
Database initialization error
Migration failure
Invalid environment configuration
Permission problem
Dependency problem

Ikke bygg bildet på nytt umiddelbart.

Avgjør om problemet er i bildet, kjøringskonfigurasjonen, vedvarende data eller ekstern konfigurasjon.
85. Docker-bilde vs. containerkonfigurasjon

Et fungerende bilde kan fortsatt mislykkes på grunn av feil kjøringskonfigurasjon.

Skill alltid:
text

Docker image
    +
Container runtime configuration
    +
Persistent volume
    +
Secret/configuration

For eksempel:
text

Image is valid
      +
Wrong volume
      =
Application failure

eller:
text

Image is valid
      +
Missing secret
      =
Application startup failure

Ikke bygg et ellers gyldig bilde på nytt for å fikse et kjøringskonfigurasjonsproblem.
86. Problemer med Docker-bygging

Hvis et nytt bilde ikke kan bygges, inspiser Dockerfile først.

Sjekk basisbildet og avhengighetsdefinisjonene.

Produksjons-Dockerfile bruker en pinnet Python-basebilde-digest.

Dette gir reproduserbarhet og forhindrer at bygget stille flytter seg til en urelatert basebilderevisjon.

Hvis et bygg plutselig endrer atferd, sammenlign:
text

Dockerfile
Base-image digest
Requirements
Application source
Build context

87. Problemer med .dockerignore

Docker-byggekonteksten skal ikke inneholde unødvendige lokale filer eller sensitivt materiale.

Repositoriet bruker .dockerignore for å ekskludere filer som:
text

Local backups
Temporary files
Editor artifacts
Backup copies
Other unnecessary runtime material

Hvis et bygg uventet inneholder en fil som ikke skal være der, inspiser:
bash

cat .dockerignore

Ikke løs byggekontekstproblemer ved å kopiere sensitive filer inn i bildet.
88. Problemer med filsystemtillatelser

Hvis LUMS rapporterer tillatelsesfeil, identifiser den nøyaktige banen først.

Nyttig informasjon:
bash

sudo docker inspect \
    lums

og:
bash

sudo docker logs \
    --tail 200 \
    lums

Den viktige forskjellen er:
text

Application data
Temporary data
Application source
Secret material
Host configuration

Hver har forskjellige forventede tillatelser.

Ikke endre eierskap eller tillatelser rekursivt over hele filsystemet som en feilsøkingssnarvei.
89. Konfigurasjonsdrift i produksjon

Konfigurasjonsdrift oppstår når kjøringsmiljøet ikke lenger samsvarer med den tiltenkte sikkerhetsbaselinen.

Eksempler inkluderer:
text

Container runs as root
Port 5050 exposed externally
Read-only filesystem disabled
Capabilities restored
Privileged mode enabled
Secret mounted read-write
Unexpected container running

Hvis drift oppdages:

    Registrer gjeldende tilstand.

    Avgjør når den endret seg.

    Identifiser den ansvarlige konfigurasjonen.

    Rett konfigurasjonen bevisst.

    Kjør den relevante sikkerhetsverifiseringen på nytt.

Ikke gjør flere urelaterte endringer samtidig.
90. Uventet netteksponering

Applikasjonsporten skal forbli lokal:
text

127.0.0.1:5050

Sjekk lyttere:
bash

sudo ss -lntp

Hvis 5050 er eksponert på en ikke-loopback-adresse, undersøk Docker-porttilordningen umiddelbart.

Ikke eksponer applikasjonsporten bare fordi Nginx virker vanskelig å diagnostisere.

Den tiltenkte arkitekturen er:
text

Network
   ↓
Nginx :443
   ↓
127.0.0.1:5050
   ↓
LUMS

91. Uventede Docker-containere

List alle containere:
bash

sudo docker ps -a

Uventede containere bør identifiseres før de fjernes.

Sjekk:
text

Container name
Image
Creation time
Ports
Volumes
Restart policy

Ikke slett en ukjent container uten å avgjøre om den er en del av LUMS-distribusjonen eller et nødvendig reservemiljø.
92. Docker-volumet må ikke slettes under normal feilsøking

Følgende operasjon er destruktiv:
bash

sudo docker volume rm lums-data

Den må ikke brukes som et generelt feilsøkingstrinn.

Sletting av volumet kan fjerne applikasjonsdatabasen og tilhørende vedvarende tilstand.

Hvis en ren installasjon er tilsiktet nødvendig, behandl det som en separat migrerings- eller gjenopprettingsoperasjon og verifiser sikkerhetskopier først.
93. Sikkerhetsbaseline etter kjøringsendringer

Etter endring av produksjons-Docker-konfigurasjon, verifiser sikkerhetsbaselinen på nytt.

Verifiser som et minimum:
text

Container runs as intended user
Root filesystem is read-only
Capabilities are dropped
Privileged mode is disabled
no-new-privileges is enabled
Secret mount is read-only
Database volume is writable
Application port is loopback-only

En konfigurasjon som får applikasjonen til å fungere, men svekker disse egenskapene, bør ikke anses som en vellykket løsning.
94. Neste feilsøkingsområde

De gjenstående feilsøkingstemaene er:
text

Tests and CI
Diagnostic snapshots
Common failure combinations
Recovery principles
Final troubleshooting checklist

De siste avsnittene gir en kompakt prosedyre for å samle nok informasjon til å diagnostisere et problem uten unødvendig å endre produksjonsmiljøet.
95. Tester og CI

Automatiserte tester er en viktig del av feilsøking av LUMS.

Før du undersøker et produksjonsproblem som en applikasjonsdefekt, verifiser om den relevante atferden allerede er dekket av testsettet.

Det gjeldende fullstendige testsettet skal bestå før en utgivelse anses som klar.

Kjør det fullstendige testsettet fra repositoriet:
bash

./.venv-test/bin/pytest -q

En vellykket kjøring skal rapportere alle tester som bestått.

Antallet tester endres etter hvert som flere tester legges til. Den viktige
betingelsen er at det fullstendige testsettet lykkes, snarere enn å stole på et
fast testantall.
96. En testfeil betyr ikke automatisk at produksjonen er ødelagt

En mislykket test kan skyldes:
text

Application regression
Test regression
Dependency change
Environment problem
Missing test dependency
Incorrect test configuration

Inspiser først den fullstendige feilutdataen.

Ikke endre produksjonskonfigurasjonen bare fordi en lokal test mislykkes.

Den riktige sekvensen er:
text

Test failure
    ↓
Read complete error
    ↓
Identify affected component
    ↓
Reproduce locally
    ↓
Determine root cause
    ↓
Apply controlled fix
    ↓
Run relevant tests
    ↓
Run full test suite

97. RBAC-testfeil

Når du undersøker autorisasjonsproblemer, kjør RBAC-testene først:
bash

./.venv-test/bin/pytest -q tests/test_rbac.py

Testene dekker rollespesifikk atferd og autorisasjonsgrenser.

Hvis problemet gjelder klientsiden, bruk den relevante delmengden når det er hensiktsmessig:
bash

./.venv-test/bin/pytest -q \
    tests/test_rbac.py -k client_page

Ikke svekk autorisasjonen for å få en test til å bestå.

En mislykket autorisasjonstest kan indikere en sikkerhetsregresjon.
98. Testfeil for pakkesøk

Pakkeadministrasjonsfunksjonalitet har dedikert testdekning.

Når du undersøker pakkesøkatferd:
bash

./.venv-test/bin/pytest -q \
    tests/test_package_search.py

Hvis feilen involverer pakkekjøring eller jobbresultater, inspiser også de relevante jobbresultattestene.

Testsettet bør brukes til å skille:
text

Application logic problem
Package-search problem
Agent problem
Integration problem

99. Tester for validering av jobbresultat

Håndtering av jobbresultat er sikkerhetsfølsomt fordi serveren ikke blindt må stole på vilkårlige klientinndata.

Kjør de relevante testene når du undersøker resultatvalidering:
bash

./.venv-test/bin/pytest -q \
    tests/test_job_result.py

En feil her bør behandles som et spørsmål om applikasjonskorrekthet og sikkerhet.

Ikke omgå resultatvalidering for å få en klientrapport til å lykkes.
100. CI-feil

LUMS bruker kontinuerlig integrasjon for å verifisere prosjektet før endringer godtas.

Hvis CI feiler:

    Identifiser den mislykkede jobben.

    Les den fullstendige feilen.

    Avgjør om feilen er relatert til kode, avhengigheter, test eller miljø.

    Reproduser lokalt der det er mulig.

    Rett rotårsaken.

    Kjør de relevante testene.

    Kjør det fullstendige testsettet.

Ikke ignorer CI-feil bare fordi produksjonsmiljøet for øyeblikket ser funksjonelt ut.
101. Diagnostisk øyeblikksbilde

Når du ber om hjelp med et LUMS-problem, samle et minimalt diagnostisk øyeblikksbilde.

Målet er å gi nok informasjon til å identifisere den sviktende komponenten uten å eksponere hemmeligheter.

Et nyttig øyeblikksbilde inkluderer:
bash

sudo docker ps

bash

sudo docker logs --tail 100 lums

bash

sudo systemctl status nginx --no-pager

bash

sudo systemctl status lums-agent.service --no-pager

bash

sudo systemctl status lums-agent-watcher.service --no-pager

bash

sudo journalctl -u lums-agent.service -n 100 --no-pager

bash

sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager

bash

sudo ss -lntp

Bruk bare kommandoene som er relevante for problemet.

Ikke dump hele miljøet inn i en støtteforespørsel.
102. Diagnostisk øyeblikksbilde må ikke inneholde hemmeligheter

Før du deler diagnostiske utdata, sjekk for:
text

Passwords
Client tokens
Application secret keys
Session secrets
Private keys
TLS private material
Credentials

Rediger sensitive verdier før deling.

Ikke anta at en logg er trygg bare fordi den kommer fra en systemtjeneste.
103. Matrise for feilkombinasjoner

Noen symptomer blir lettere å diagnostisere når flere komponenter vurderes sammen.
Symptom	Mest sannsynlig område å inspisere først
Nettleseren kan ikke koble til	Nginx / TLS / nettverk
Nginx fungerer, men applikasjonen feiler	Docker / LUMS
LUMS fungerer, men klienten kan ikke rapportere	Agent / TLS / token
Klienten rapporterer, men jobben forblir ventende	Overvåker / kvalifisering
Jobben kjører, men pakken feiler	APT / pacman
Pakken lykkes, men resultatet mangler	Agentrapportering
Resultatet når serveren, men UI er utdatert	API / database / nettlesertilstand
Viewer kan endre data	RBAC på serversiden
Bruker kan ikke logge inn	Konto / passord / hastighetsbegrensning
Innlogging fungerer, men handling avvises	RBAC / CSRF
Databaseskriving feiler	SQLite / disk / tillatelser
Containeren mister data etter gjenoppretting	Konfigurasjon av vedvarende volum
Applikasjonen skriver til rotfilsystemet	Konfigurasjon av containerfilsystem
Port 5050 er eksternt tilgjengelig	Docker / brannmurkonfigurasjon

Denne tabellen identifiserer det første stedet å undersøke, ikke nødvendigvis den endelige rotårsaken.
104. Vanlige feilsøkingsfeil

Unngå følgende snarveier:
Ikke slett databasen
text

Deleting lums.db
Deleting lums-data

kan ødelegge vedvarende applikasjonstilstand.
Ikke deaktiver sikkerhetskontroller

Ikke deaktiver permanent:
text

RBAC
CSRF protection
TLS validation
Container hardening
Read-only filesystem
no-new-privileges
Capability restrictions

En løsning som fjerner en sikkerhetskontroll, er ikke en fullført rettelse.
Ikke kjør containeren som privilegert

Unngå:
text

--privileged

som en feilsøkingsløsning.

Hvis applikasjonen krever ekstra tilgang, avgjør nøyaktig hvilken tilgang som kreves.
Ikke eksponer port 5050

Ikke endre:
text

127.0.0.1:5050

til:
text

0.0.0.0:5050

bare for å omgå Nginx.

Applikasjonen er bevisst beskyttet bak den omvendte proxyen.
Ikke endre jobbtilstander manuelt

Unngå å endre direkte:
text

update_jobs
update_job_packages

for å skjule et driftsproblem.

Bruk applikasjons-, agent-, overvåker- og gjenopprettingsmekanismene.
Ikke slett pakkebehandlerlåser blindt

En lås kan indikere en aktiv pakkebehandlerprosess.

Identifiser prosessen først.
Ikke roter legitimasjon gjentatte ganger

Gjentatt token- eller hemmelighetsrotasjon kan skape flere autentiseringsproblemer.

Avgjør først hvilken legitimasjon som for øyeblikket er konfigurert, og hvilken legitimasjon serveren forventer.
105. Gjenopprettingsprinsipper

Følgende prinsipper gjelder for all LUMS-feilsøking:
Bevar først

Behold:
text

Logs
Job state
Database
Container state
Configuration
Error messages

til problemet er forstått.
Endre én ting om gangen

Når flere endringer gjøres samtidig, blir den opprinnelige årsaken vanskeligere å identifisere.
Verifiser etter hver endring

Etter en kontrollert endring:
text

Re-test
Check logs
Verify state
Confirm security properties

Foretrekk reversible endringer

Når det er mulig, bruk endringer som kan tilbakestilles uten å ødelegge applikasjonstilstanden.
Hold sikkerhetskontroller aktive

Et vellykket feilsøkingsresultat må ikke introdusere en unødvendig sikkerhetsregresjon.
106. Feilsøkingssekvens for produksjon

For et generelt LUMS-produksjonsproblem, bruk denne rekkefølgen:
text

1. Identify the symptom
        ↓
2. Identify the affected component
        ↓
3. Inspect current state
        ↓
4. Inspect relevant logs
        ↓
5. Reproduce safely
        ↓
6. Determine the first failing layer
        ↓
7. Apply the smallest required change
        ↓
8. Re-test
        ↓
9. Verify security controls
        ↓
10. Document the result

Denne rekkefølgen forhindrer at urelaterte komponenter endres unødvendig.
107. Full systemdiagnostisk bane

Når den berørte komponenten er ukjent, følg hele banen:
text

Browser
  │
  ▼
Nginx / HTTPS
  │
  ▼
Docker
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Update Job
  │
  ▼
Watcher
  │
  ▼
Agent
  │
  ▼
APT / pacman
  │
  ▼
Client state
  │
  ▼
Agent result
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Web UI

Spør ved hvert trinn:
text

Did the request reach this component?

Did this component process it?

Did it produce the expected result?

Did the next component receive that result?

Det første NEI identifiserer normalt området som krever undersøkelse.
108. Feilsøking av utgivelse

Før du forbereder en utgivelse, verifiser:
text

Full test suite passes
CI passes
Security audit is complete
Documentation is current
Production configuration matches the documented baseline
No unexpected debug configuration remains
No secrets are included in the repository
Docker hardening remains active
RBAC behavior is correct
Package management works
Update-job execution works
Recovery behavior is verified

En utgivelse bør ikke opprettes bare fordi applikasjonen starter vellykket.
109. Feilsøkingssjekkliste

Bruk denne sjekklisten før du erklærer et produksjonsproblem løst:
text

[ ] Root cause identified
[ ] Relevant logs inspected
[ ] No unnecessary data was deleted
[ ] No credentials were exposed
[ ] No security control was disabled
[ ] Relevant functionality tested
[ ] Full test suite considered where appropriate
[ ] Docker security baseline verified
[ ] Network exposure verified
[ ] Agent state verified
[ ] Watcher state verified
[ ] Job state verified
[ ] Recovery state verified
[ ] Database state verified where relevant
[ ] Documentation updated if behavior changed

110. Når du bør slutte å feilsøke

Slutt å gjøre endringer når:
text

The root cause is identified
    AND
The corrective action is understood
    AND
The system is stable
    AND
Security controls remain intact

Hvis rotårsaken ikke er forstått, bevar gjeldende tilstand i stedet for gjentatte ganger å endre miljøet.

En rent bevart feil er lettere å diagnostisere enn et delvis modifisert system.
111. Endelig gjenopprettingsprinsipp

Den viktigste LUMS-feilsøkingsregelen er:

    Observer først. Endre deretter. Verifiser til slutt.

LUMS inneholder flere uavhengige sikkerhets- og kjøringslag.

Et problem i ett lag bør ikke automatisk føre til endringer i et annet.

Den foretrukne feilsøkingstilnærmingen er derfor:
text

Observe
   ↓
Classify
   ↓
Isolate
   ↓
Correct
   ↓
Verify
   ↓
Document

Dette holder feilsøkingen kontrollert, reproduserbar og kompatibel med LUMS' sikkerhetsbaseline.
112. Vedlikehold av dokumentasjon

Dette dokumentet bør oppdateres når en dokumentert driftsatferd endres.

Dokumentasjonsendringer bør være konsistente med:
text

Security documentation
Deployment documentation
Agent behavior
Watcher behavior
RBAC model
Package-management behavior
Docker runtime configuration
Test baseline

Utdaterte feilsøkingsinstruksjoner kan være farlige når de anbefaler utdaterte kommandoer eller sikkerhetssvekkende løsninger.

Når en produksjonsatferd endres, oppdater den relevante dokumentasjonen før feilsøkingsprosedyren anses som fullført.
113. Gjeldende baseline

Den gjeldende LUMS-baselinen dokumentert av denne feilsøkingsveiledningen inkluderer:
text

Agent version: 1.7.0
Watcher version: 1.2.1

Application port:
127.0.0.1:5050

Database:
SQLite

SQLite journal mode:
delete

SQLite busy timeout:
5000 ms

SQLite synchronous:
2

SQLite foreign keys:
Enabled by the application

Container:
Non-root
Read-only root filesystem
Capabilities dropped
no-new-privileges enabled
Privileged mode disabled

RBAC:
Administrator
Operator
Viewer

Viewer:
Clients + Installed Software only

Full test suite:
Passing baseline

Det nøyaktige testantallet kan endres etter hvert som prosjektet vokser.

Sikkerhets- og arkitekturegenskapene er den viktige baselinen.
114. Slutt på feilsøkingsveiledningen

LUMS-feilsøking bør forbli evidensdrevet og sikkerhetsbevisst.

Når du er i tvil:
text

Preserve the state.
Inspect the evidence.
Identify the failing layer.
Make the smallest safe change.
Verify the result.
Document what happened.

Ikke bytt sikkerhet eller dataintegritet mot en rask løsning.

Slutt på LUMS feilsøkingsveiledning
