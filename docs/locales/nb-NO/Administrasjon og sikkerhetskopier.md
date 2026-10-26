# LUMS — Administrasjonsveiledning

> **Linux-oppdateringsadministrasjon uten støyen.**

Denne veiledningen beskriver den daglige administrasjonen og driften av LUMS etter at serveren og klientene er installert.

Den fokuserer på administrative oppgaver som utføres gjennom LUMS' webgrensesnitt og på kontrollerte driftsopgaver på LUMS-serveren og administrerte klienter.

Installasjonsprosedyrer er dokumentert separat i `install.md`.

Feilsøkingsprosedyrer er dokumentert separat i `troubleshooting.md`.

Sikkerhetsarkitektur og revisjonsinformasjon er dokumentert separat i `security.md`.

---

## Kom i gang: Daglig administrasjon

Denne veiledningen er for personen som er ansvarlig for en eksisterende LUMS-installasjon.
De detaljerte tekniske avsnittene vedlikeholdes på engelsk. Start med disse begrepene:

* **Brukerkonto:** bestemmer hva en person kan gjøre i LUMS' webgrensesnitt.
  Ikke del kontoer; gi hver person sin egen konto.
* **Klient:** en administrert Linux-datamaskin. Klienttokenet er en hemmelighet og
  er ikke det samme som et webkontopassord.
* **Oppdateringsjobb:** en forespurt operasjon som agenten henter og kjører
  ved hjelp av APT eller pacman på mål datamaskinen. Sjekk målet og pakkene
  før du starter den.
* **Sikkerhetskopi:** en separat, verifisert kopi av databasen. En kopi i samme
  Docker-volum beskytter ikke mot tap av det volumet.
* **Oppgradering:** erstatter containerversjonen, ikke databasen. En normal
  oppgradering må ikke slette eller gjenopprette `lums-data`.

### Sikker sjekkliste før du gjør en endring

1. Sjekk om oppdateringsjobber kjører og om et vedlikeholdsvindu er nødvendig.
2. Bekreft at en nylig, brukbar databasesikkerhetskopi eksisterer.
3. Registrer det kjørende bildet, containerinnstillingene og databanene.
4. Bygg og test det nye bildet før du stopper den aktive containeren.
5. Erstatt containeren med de samme data-, hemmelighets- og sikkerhetskopimonteringene og de
   samme sikkerhetsvalgene.
6. Sjekk containerstatus, logger, HTTPS-innlogging og data etter oppstart.
7. Behold den gamle containeren som et tilbakerullingsalternativ til den nye versjonen er
   verifisert.

**Ikke kjør** `docker volume rm lums-data`, `docker system prune --volumes`,
eller andre slettekommandoer som en del av en normal oppgradering. De kan permanent
fjerne data. Hvis du er usikker på hvilken container eller bane som er aktiv, stopp og
inspiser gjeldende oppsett først; ikke kopier en eksempelkommando uten
å sjekke den.

---

## 1. Administrasjonsoversikt

LUMS tilbyr sentralisert administrasjon av Linux-programvareinventar, tilgjengelige oppdateringer, pakkeoperasjoner, oppdateringsjobber, administrerte klienter, brukere og driftshistorikk.

Administrasjonsgrensesnittet tilbyr tre rollemaler:

* **Administrator**
* **Operator**
* **Viewer**

Når en konto opprettes, fyller den valgte rollen inn et anbefalt sett med
tillatelser. Administratorer kan justere disse tillatelsene per bruker; de lagrede
tillatelsene, snarere enn rolletiketten, bestemmer tilgangen.

LUMS skiller også mellom administrative operasjoner på serversiden og pakkekjøring på klientsiden.

Den normale driftsflyten er:

```text
Administrator / Operator
        │
        ▼
   LUMS Web UI
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
   Managed Client
        │
        ▼
 APT / pacman / system
        │
        ▼
      Result
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
    Web Interface
```

LUMS-serveren utfører ikke pakkeadministrasjonskommandoer direkte på administrerte klienter.

Pakkeoperasjoner utføres av LUMS-agenten installert på det administrerte systemet.
## 2. Administrative ansvarsområder

LUMS-administrasjon kan deles inn i flere områder.
Brukeradministrasjon

Administratorer administrerer:

* LUMS-brukere

* brukerroller

* kontostatus

* administrativ tilgang

Brukeradministrasjon krever tillatelsen users.manage.

Administratormalen inkluderer denne tillatelsen som standard.

Operatorer og Viewers mottar den ikke som standard.
Klientadministrasjon

Administratorer administrerer:

* registrerte klienter

* klientstatus

* klientautentisering

* klienttokener

* tokenrotasjon

* aktivering og deaktivering av klienter

Klientadministrasjon krever tillatelsen clients.manage fordi klientautentisering
bestemmer hvilke systemer som har tillatelse til å rapportere til LUMS.
Oppdateringsadministrasjon

Administrator- og Operatørmalene gir tillatelser til å:

* vise tilgjengelige oppdateringer

* opprette oppdateringsjobber

* utføre pakkeoperasjoner

* gjennomgå oppdateringshistorikk

* administrere individuelle pakker

* utføre systemoppdateringer

Viewer-malen er skrivebeskyttet og kan ikke utføre oppdateringsoperasjoner.
Pakkeadministrasjon

LUMS støtter pakkeadministrasjonsoperasjoner gjennom klientens native pakkebehandler.

Gjeldende støttede pakkeadministrasjonsbackender inkluderer:

* APT/dpkg for Debian-baserte systemer

* pacman for Arch Linux

LUMS erstatter ikke operativsystemets pakkebehandler.

I stedet tilbyr LUMS et sentralt grensesnitt for å forespørre og spore pakkeoperasjoner.
Driftsadministrasjon

Administratorer og Operatorer kan trenge å overvåke:

* kjørende oppdateringsjobber

* mislykkede jobber

* fullførte jobber

* klientrapportering

* omstartskrav

* pakkebehandlerfeil

* revisjonsaktivitet

De detaljerte feilsøkingsprosedyrene for disse tilstandene er dokumentert i troubleshooting.md.
## 3. Administrative roller

LUMS tilbyr for tiden tre roller.
| Rolle | Formål |
| --- | --- |
| Administrator | Full administrativ kontroll |
| Operator | Daglig operativ administrasjon |
| Viewer | Skrivebeskyttet klient- og programvaresynlighet |

Hver rolle er en tillatelsesmal. Kontoens individuelt lagrede
tillatelser håndheves på serversiden.

Å skjule et grensesnittelement anses derfor ikke som en sikkerhetskontroll i seg selv.

Uautoriserte API-operasjoner må også avvises av serveren.
## 4. Administrator

Administratormalen gir som standard det fullstendige settet med LUMS-applikasjonstillatelser.

Administratorer kan:

* vise administrerte klienter

* vise installert programvare

* vise tilgjengelige oppdateringer

* opprette og utføre oppdateringsjobber

* gjennomgå oppdateringshistorikk

* utføre pakkeadministrasjonsoperasjoner

* utføre systemvedlikehold

* opprette klienter

* deaktivere klienter

* rotere klienttokener

* opprette og administrere LUMS-brukere

* tildele rollemaler og individuelle tillatelser

Fullstendige Administratormaltillatelser bør bare gis til brukere som
trenger dem.

Administrative kontoer bør ikke brukes til rutinemessig skrivebeskyttet overvåking når en Operator- eller Viewer-konto er tilstrekkelig.
5. Operator

Operatørmalen er ment for daglig oppdaterings- og systemadministrasjon.

Operatorer kan:

* vise administrerte klienter

* vise installert programvare

* vise tilgjengelige oppdateringer

* opprette og utføre oppdateringsjobber

* gjennomgå oppdateringshistorikk

* utføre pakkeadministrasjonsoperasjoner

* utføre systemvedlikehold

Operatørmalen gir ikke:

* opprette eller administrere LUMS-brukere

* tildele brukerroller

* opprette eller deaktivere klienter

* rotere klienttokener

Denne standardseparasjonen tillater rutinemessige oppdateringsoperasjoner uten å gi
konto- og klientadministrasjonsprivilegier. Individuelle tildelinger kan endres av
en bruker med users.manage.
6. Viewer

Viewer-malen gir skrivebeskyttet synlighet.

Viewers kan:

* vise administrerte klienter

* vise installert programvare

Viewer-malen gir ikke følgende administrative funksjoner:

* administrasjon av tilgjengelige oppdateringer

* opprettelse av oppdateringsjobber

* kjøring av oppdateringsjobber

* oppdateringshistorikk

* pakkeadministrasjon

* systemvedlikehold

* brukeradministrasjon

* klientadministrasjon

* tokenrotasjon

De tilsvarende muterende API-operasjonene er også beskyttet på serversiden.

Viewer-tilgang er derfor ment for brukere som trenger synlighet uten operativ kontroll.
7. Retningslinjer for valg av rolle

Bruk den minste rollen som gir den nødvendige funksjonaliteten.
Administrator

Bruk når brukeren må administrere:

* brukere

* roller

* klienter

* klientautentisering

* tokener

* oppdateringer

* pakker

* systemoperasjoner

## Operator

Bruk når brukeren trenger å utføre rutinemessig operativt arbeid som:

* sjekke oppdateringer

* installere pakker

* fjerne pakker

* oppdatere pakker

* utføre oppdateringsjobber

* gjennomgå jobbhistorikk

## Viewer

Bruk når brukeren bare trenger synlighet i:

* klienter

* installert programvare

8. Administrativt sikkerhetsprinsipp

LUMS-administrasjon følger prinsippet om minste privilegium.

Administrativ tilgang bør begrenses til funksjonaliteten som kreves for brukerens oppgave.

Spesielt:

* ikke bruk Administrator-kontoer til rutinemessig visning

* ikke del kontoer mellom administratorer

* ikke del klienttokener

* ikke plasser legitimasjon i dokumentasjon

* ikke eksponer klienttokener i skjermbilder eller logger

* ikke omgå LUMS' webgrensesnitt ved å endre databasen direkte med mindre en dokumentert gjenopprettingsprosedyre eksplisitt krever det

Når en administrativ operasjon mislykkes, undersøk årsaken før du endrer vedvarende tilstand.

Bruk prinsippet:

* Observer først. Endre deretter. Verifiser til slutt.

## 9. Administrativ arbeidsflyt

En normal administrativ arbeidsflyt bør følge denne sekvensen:

```text
1. Authenticate
      │
      ▼
2. Verify role
      │
      ▼
3. Select client / operation
      │
      ▼
4. Review current state
      │
      ▼
5. Perform required operation
      │
      ▼
6. Monitor job
      │
      ▼
7. Verify result
      │
      ▼
8. Review history / audit information
```

Administrative handlinger bør alltid verifiseres etter utførelse.

En vellykket API-forespørsel beviser ikke i seg selv at den forespurte pakke- eller systemoperasjonen ble fullført.

Den endelige tilstanden rapportert av den administrerte klienten er det relevante driftsresultatet.
## 10. Separasjon av dokumentasjon

LUMS-dokumentasjonssettet er bevisst delt inn i separate driftsveiledninger.
| Dokument | Formål |
| --- | --- |
| install.md | Installasjon og førstegangsdistribusjon |
| administration.md | Daglig administrasjon |
| security.md | Sikkerhetsarkitektur og revisjonsresultater |
| troubleshooting.md | Diagnose og gjenoppretting |

Denne veiledningen bør derfor unngå å duplisere detaljerte installasjons- og feilsøkingsprosedyrer.

I stedet beskriver den hva administratorer kan administrere, hva hver operasjon betyr, og hvordan normale administrative arbeidsflyter utføres.
## 11. Brukeradministrasjon

Brukeradministrasjon er tilgjengelig for brukere med tillatelsen users.manage.

Administratorer kan opprette og administrere LUMS-applikasjonskontoer gjennom det dedikerte brukeradministrasjonsgrensesnittet.

Brukerkontoer er separate fra autentisering av administrerte klienter.

En LUMS-bruker autentiserer seg til webapplikasjonen med en applikasjonskonto.

En administrert klient autentiserer seg til LUMS-API-et med et klienttoken.

Disse autentiseringsmekanismene må ikke forveksles.

```text
LUMS User
    │
    │ username + password
    ▼
Web Interface
    │
    ▼
LUMS Application

Managed Client
    │
    │ client token
    ▼
LUMS API
```

## 12. Opprette brukere

Brukere med users.manage kan opprette nye LUMS-brukere.

Når du oppretter en bruker, spesifiserer administratoren:

* brukernavn

* passord

* en rolletikett, med en rollemal tilgjengelig for senere tillatelsestildeling

Tilgjengelige rollemaler er:

* administrator

* operator

* viewer

Serveren validerer de angitte verdiene før kontoen opprettes.

Nye kontoer starter uten tillatelser. Etter opprettelsen kan administratorer
tildele individuelle avkrysningsbokser eller bruke en av rollemalene. Bruk av en
mal forhåndsvelger dens standardtillatelser, som deretter kan tilpasses.
Tilgjengelige tillatelser er:
| Tillatelse | Tilgang gitt |
| --- | --- |
| clients.view | Vise klientlisten og systeminformasjon |
| software.view | Vise installert programvare |
| updates.view | Vise oppdateringer, jobber og oppdateringshistorikk |
| packages.search | Søke i pakkerepositorier |
| jobs.manage | Opprette pakkeoperasjoner og oppdateringsjobber |
| clients.manage | Registrere/fjerne klienter og rotere klienttokener |
| users.manage | Opprette brukere og administrere roller, tillatelser og interne notater |
| backups.manage | Opprette og inspisere databasesikkerhetskopier |

Klientrelaterte tillatelser krever clients.view; jobs.manage krever også
updates.view. LUMS forhindrer fjerning av den siste aktive kontoen med
users.manage, slik at administratorer ikke ved et uhell låser seg ute.

Passord lagres ikke som klartekst.

LUMS bruker Argon2-basert passordhashing for applikasjonslegitimasjon.

Etter opprettelsen, verifiser at:

* brukernavnet vises i brukerlisten

* rollemalen og de individuelle tillatelsene er korrekte

* kontoen er aktivert

* brukeren kan autentisere seg vellykket

Ikke overfør passord gjennom dokumentasjon, saksbehandlingssystemer, skjermbilder eller andre usikre kanaler.
## Database Backup Interface

Brukere med tillatelsen backups.manage kan opprette SQLite-sikkerhetskopier fra
Datenbank-Backups. Administrator-kontoer mottar denne tillatelsen gjennom
migrering 005-backup-permission; nye kontoer mottar den ved å bruke
Administratormalen eller kan få den eksplisitt tildelt.

Grensesnittet støtter native .db og komprimerte .db.gz-filer. Det bruker
SQLites online backup-API, validerer den fullførte databasen og lagrer filer
med kun eierens tillatelser. Grensesnittet viser de ti nyeste filene. Sikkerhetskopier
blir ikke kryptert, automatisk slettet, planlagt, lastet ned eller gjenopprettet av
LUMS; administratorer med backups.manage kan slette individuelle sikkerhetskopier fra
listen etter bekreftelse. Beskytt destinasjonen deretter.

Grunnmålkatalogen er fastsatt av serverinnstillingen LUMS_BACKUP_DIR.
Grensesnittet lar deg velge en relativ underkatalog under denne
basen og oppretter den ved behov; absolutte baner, overordnet gjennomgang og
symbolske underkataloger avvises. Vertssidebaner må monteres inn i Docker
av serveradministratoren. For en Docker-distribusjon, opprett en egen vertskatalog
som kan skrives av containerens UID/GID 10001:

```bash
sudo install -d -o 10001 -g 10001 -m 0700 /var/backups/lums
```

Legg til disse alternativene i LUMS-containerkonfigurasjonen:

```bash
-v /var/backups/lums:/var/backups/lums \
-e LUMS_BACKUP_DIR=/var/backups/lums \
```

Bruk en separat disk eller ekstern lagring for motstandsdyktighet mot vertsfeil.
For eksempel, monter en NAS på Debian-verten først, og bruk deretter den monterte banen
som venstre side av Docker-bind-monteringen. Backup-grensesnittet viser
containerens basekatalog; den valgte relative banen er under den.
Sikkerhetskopimålet må være tilgjengelig og skrivbart inne i containeren;
ellers rapporterer grensesnittet at sikkerhetskopilagring er utilgjengelig.

For gjenopprettingstrinn, se server/static/backup-restore.md.
## 13. Brukerroller

Velg en rollemal i henhold til minste nødvendige privilegium, og gjennomgå
deretter de individuelle tillatelsene for hver konto.
| Rollemal | Brukeradministrasjon | Klientadministrasjon | Oppdateringer | Pakkeadministrasjon | Skrivebeskyttet tilgang |
| --- | --- | --- | --- | --- | --- |
| Administrator | Ja | Ja | Ja | Ja | Ja |
| Operator | Nei | Nei | Ja | Ja | Ja |
| Viewer | Nei | Nei | Nei | Nei | Ja |

Dette er standardverdier, ikke faste grenser. Administratorer kan tilpasse hver
brukers tillatelsessett. Rollehåndheving skjer på serveren gjennom
de resulterende tillatelsene per bruker.

Webgrensesnittet gjenspeiler den tildelte rollen, men serveren forblir den autoritative sikkerhetsgrensen.
## 14. Deaktivere brukerkontoer

Når en konto ikke lenger skal ha tillatelse til å få tilgang til LUMS, deaktiver kontoen i stedet for å dele eller gjenbruke legitimasjonen.

Eksempler inkluderer:

* en administrator som forlater prosjektet

* en operatør som ikke lenger trenger tilgang

* midlertidig fjerning av administrativ tilgang

* sikkerhetsrespons på en kompromittert konto

Etter deaktivering av en konto, verifiser at autentisering avvises.

Eksisterende autentiserte økter bør også vurderes under kontosikkerhetsundersøkelser.

Ikke endre users-tabellen manuelt med mindre en dokumentert gjenopprettingsprosedyre eksplisitt krever databaseinngrep.
## 15. Passordadministrasjon

Passord er applikasjonslegitimasjon og må behandles som sensitiv informasjon.

Administratorer bør sikre at:

* passord ikke deles

* passord ikke lagres i Git

* passord ikke plasseres i dokumentasjon

* passord ikke inkluderes i skjermbilder

* passord ikke skrives inn i skallhistorikken unødvendig

* brukere mottar legitimasjonen sin gjennom en passende sikker kanal

LUMS lagrer passordhasher i stedet for klartekstpassord.

Hvis et passord antas å være kompromittert, erstatt det gjennom den aktuelle kontoadministrasjonsprosedyren i stedet for å forsøke å gjenopprette det opprinnelige passordet.
## 16. Økter

LUMS bruker autentiserte applikasjonsøkter for webtilgang.

Økthåndtering er en del av applikasjonens sikkerhetsgrense.

Administratorer bør behandle en uventet autentisert økt som en sikkerhetshendelse hvis den tilknyttede kontoen ikke lenger skal ha tilgang.

Relevante situasjoner inkluderer:

* deaktivert konto som fortsatt vises som aktiv

* uventet administrativ tilgang

* mistenkt kompromittering av legitimasjon

* uventet nettleserøkt

* sikkerhetsundersøkelse

For detaljert feilsøking av økter og autentisering, se troubleshooting.md.
## 17. Hastighetsbegrensning for innlogging

LUMS bruker hastighetsbegrensning på gjentatte mislykkede innloggingsforsøk.

Gjeldende progresjon er:
| Mislykkede forsøk | Utlåsing |
| --- | --- |
| 5 | 30 sekunder |
| 6 | 60 sekunder |
| 7 | 120 sekunder |
| 8+ | 300 sekunder |

Tilstanden for hastighetsbegrensning lagres i SQLite.

En vellykket innlogging sletter gjeldende tilstand for mislykkede forsøk.

Gjentatte autentiseringsfeil bør undersøkes i stedet for å omgå hastighetsbegrenseren.

Mulige årsaker inkluderer:

* feil legitimasjon

* utdatert lagret legitimasjon

* en automatisert klient som bruker feil legitimasjon

* gjentatte manuelle innloggingsforsøk

* et mulig legitimasjonsangrep

## 18. Klientadministrasjon

Administrerte klienter er Linux-systemer som kjører LUMS-agenten.

En klient gir LUMS informasjon som:

* klientidentitet

* installert programvare

* tilgjengelige oppdateringer

* pakkeadministrasjonsresultater

* oppdateringsjobbresultater

* omstartstilstand

* driftstilstand

LUMS-serveren lagrer klienttilstanden og eksponerer den gjennom webgrensesnittet.

Klienten utfører de faktiske pakkeadministrasjonsoperasjonene lokalt.
19. Klientautentisering

Hver administrert klient autentiserer seg til LUMS ved hjelp av et klienttoken.

Tokenet fungerer som legitimasjon for den administrerte klienten.

Behandle klienttokener med samme omhu som passord.

Aldri:

* commit tokener til Git

* plasser tokener i offentlig dokumentasjon

* inkluder tokener i skjermbilder

* lim inn tokener i saksbehandlingssystemer

* eksponer tokener i diagnostisk utdata

* del én klients token med en annen klient

Et token skal bare installeres på klienten det ble utstedt for.
20. Klientregistrering

En ny klient må først registreres med LUMS.

Registreringsprosessen etablerer klientidentiteten og autentiseringslegitimasjonen på serversiden.

Etter registrering:

* installer LUMS-agenten

* konfigurer klienttokenet

* konfigurer LUMS-serverendepunktet

* etabler TLS-tillit

* utfør en første agentkjøring

* verifiser at klienten rapporterer vellykket

* bekreft at klienten vises i LUMS-grensesnittet

En klient skal ikke anses som operativ bare fordi agenttjenesten starter vellykket.

Serveren må motta og godta en gyldig klientrapport.
21. Klientstatus

Klientvisningen bør brukes til å skille mellom forskjellige driftstilstander.

Eksempler inkluderer:

* klient registrert, men rapporterer ikke

* klient rapporterer normalt

* klient rapporterer utdatert informasjon

* klient deaktivert

* klientautentiseringsfeil

* pakkebehandlerfeil på klientsiden

Når en klient slutter å rapportere, avgjør først om problemet er:

* nettverkstilkobling

* TLS-tillit

* klientautentisering

* agentkjøring

* servertilgjengelighet

* behandling på serversiden

Unngå å endre klientlegitimasjon før du har fastslått hvilket lag som faktisk feiler.
22. Rotasjon av klienttoken

Klienttokener kan roteres når det er nødvendig.

Typiske årsaker inkluderer:

* mistenkt eksponering av token

* retningslinjer for legitimasjonsrotasjon

* administrativt vedlikehold

* erstatning av en klientkonfigurasjon

* respons på sikkerhetshendelse

Tokenrotasjon endrer legitimasjonen som godtas for klienten.

Etter rotasjon:

* skaff det nye klienttokenet

* oppdater klientkonfigurasjonen

* kjør agenten

* verifiser vellykket autentisering

* verifiser den resulterende klientrapporten

* bekreft at normal rapportering gjenopptas

Ikke fjern den gamle klientkonfigurasjonen før den nye autentiseringsbanen er verifisert.
23. Deaktivere en klient

En klient kan deaktiveres når den ikke lenger skal delta i LUMS-operasjoner.

Eksempler inkluderer:

* avvikling av system

* midlertidig vedlikehold

* utskifting av klient

* mistenkt kompromittering av legitimasjon

Før du deaktiverer en klient, sjekk om aktive oppdateringsjobber er tilknyttet den.

Etter deaktivering:

* verifiser at klienten ikke lenger behandles som operativ

* gjennomgå relevant oppdateringsjobhistorikk

* bevar revisjonsinformasjon som kreves for undersøkelse

Ikke slett vedvarende klientdata bare fordi en klient er midlertidig frakoblet.
24. Sjekkliste for klientadministrasjon

Når du legger til eller endrer en klient, verifiser hele kjeden:
```text

[ ] Client exists in LUMS
[ ] Client is enabled
[ ] Client token is valid
[ ] TLS trust is valid
[ ] LUMS Agent is installed
[ ] Agent configuration is valid
[ ] Initial report succeeds
[ ] Client appears in the Web UI
[ ] Installed software is reported
[ ] Available updates are reported
[ ] Update jobs can be tracked
[ ] Results are returned correctly
```

En klient er operativ bare når hele rapporterings- og autentiseringskjeden fungerer.
## 25. Administrativt prinsipp

Brukeradministrasjon og klientadministrasjon bør forbli atskilt.

En LUMS-applikasjonskonto bestemmer hva en person har lov til å gjøre.

Et klienttoken bestemmer hvilket administrert system som har lov til å kommunisere med LUMS.

```text
Application User
      │
      └── Role / Permissions

Managed Client
      │
      └── Client Token / Identity
```

Ikke bruk én mekanisme som erstatning for den andre.
## 26. Programvareinventar

LUMS vedlikeholder programvareinformasjon rapportert av administrerte klienter.

Programvareinventaret lar administratorer og operatører fastslå hvilke pakker som er installert på en klient.

Inventaret samles inn av LUMS-agenten og rapporteres til serveren.

Serveren gjør deretter den rapporterte informasjonen tilgjengelig gjennom klientgrensesnittet.

Inventaret bør behandles som et øyeblikksbilde av klientens rapporterte tilstand.

Det erstatter ikke den native pakkebehandleren.
## 27. Installert programvare

Installert programvare-seksjonen viser pakker rapportert av den valgte klienten.

Administratorer og Operatorer kan bruke det lokale pakkefilteret for å begrense det viste inventaret.

Filteret for installert programvare er en lokal grensesnittfunksjon.

Det er atskilt fra pakkeadministrasjonssøket.

Denne forskjellen er viktig:

```text
Installed Software
    │
    └── Filter already reported package inventory

Package Management
    │
    └── Search the client's package repositories
```

En installert pakke vises derfor kanskje ikke i pakkeadministrasjonssøket hvis den ikke lenger er tilgjengelig i et konfigurert repositorium.
## 28. Tilgjengelige oppdateringer

LUMS samler også informasjon om pakker som har tilgjengelige oppdateringer.

Informasjon om tilgjengelige oppdateringer genereres på den administrerte klienten ved hjelp av dens native pakkeadministrasjonssystem.

Den rapporterte informasjonen kan brukes til å identifisere pakker som krever oppmerksomhet.

Før du oppretter en oppdateringsjobb, gjennomgå:

* klientidentitet

* pakkenavn

* nåværende installert versjon

* tilgjengelig versjon

* pakkestatus

* om klienten for øyeblikket er tilgjengelig

Ikke anta at hver tilgjengelig oppdatering umiddelbart bør installeres.

Driftskrav, vedlikeholdsvinduer, applikasjonsavhengigheter og klienttilstand bør vurderes før kjøring.
## 29. Pakkeadministrasjon

LUMS tilbyr sentraliserte pakkeadministrasjonsoperasjoner for støttede Linux-klienter.

Gjeldende pakkeadministrasjonshandlinger inkluderer:

* INSTALL_PACKAGE

* REMOVE_PACKAGE

* UPDATE_PACKAGE

* UPDATE_SYSTEM

Operasjonen forespørres gjennom LUMS, men utføres lokalt av LUMS-agenten.

Agenten delegerer den faktiske pakkeoperasjonen til den native pakkebehandleren.

```text
LUMS Web UI
      │
      ▼
LUMS API
      │
      ▼
Update Job
      │
      ▼
LUMS Agent
      │
      ├── APT / dpkg
      │
      └── pacman
```

LUMS forblir derfor uavhengig av operativsystemets pakkedatabase og pakkeadministrasjonsimplementasjon.
## 30. Pakkesøk

Pakkeadministrasjon-grensesnittet tilbyr et pakkesøk som er atskilt fra filteret for installert programvare.

Søket ber om pakkeinformasjon fra den administrerte klienten.

På Debian-baserte systemer bruker agenten APT-pakkeadministrasjonsverktøyene.

På Arch Linux bruker agenten pacman.

Søkeresultater kan inneholde:

* pakkenavn

* pakkeversjon

* pakkebeskrivelse

* repositoriumsinformasjon der tilgjengelig

Pakkesøk installerer ingenting.

Et søk er derfor en skrivebeskyttet operasjon.
## 31. Installere en pakke

Administratorer og Operatorer kan opprette pakkeinstallasjonsjobber.

Den normale arbeidsflyten er:

* velg den administrerte klienten

* åpne Pakkeadministrasjon

* søk etter den nødvendige pakken

* gjennomgå resultatet

* velg installasjonshandlingen

* opprett jobben

* overvåk kjøringen

* verifiser resultatet

* oppdater eller sjekk installert programvare på nytt

Pakken installeres av agenten ved hjelp av den native pakkebehandleren.

Vellykket opprettelse av jobben betyr ikke at installasjonen allerede er fullført.

Det endelige jobbresultatet må sjekkes.
## 32. Fjerne en pakke

Pakkefjerning følger samme kontrollerte jobbarbeidsflyt.

Før du fjerner en pakke, verifiser:

* riktig klient

* riktig pakke

* tiltenkt operasjon

* om annen programvare er avhengig av pakken

Etter kjøring, verifiser den resulterende jobbstatusen og klientens rapporterte programvaretilstand.

LUMS omgår ikke pakkebehandlerens avhengighetshåndtering.

Den native pakkebehandleren forblir ansvarlig for å løse operasjonen.
33. Oppdatere en pakke

En spesifikk pakke kan oppdateres når en oppdatering er tilgjengelig.

Arbeidsflyten er:
```text

Available Update
      │
      ▼
Review Package
      │
      ▼
Create UPDATE_PACKAGE Job
      │
      ▼
Agent Execution
      │
      ▼
Result Validation
```

LUMS validerer pakkeinformasjonen før den oppretter den tilsvarende oppdateringsjobben.

Hvis pakken ikke lenger er oppført som oppdaterbar, bør jobbforespørselen ikke behandles som en gyldig oppdateringsoperasjon.

Dette forhindrer at utdatert oppdateringsinformasjon blindt utføres.
## 34. Oppdatere systemet

UPDATE_SYSTEM utfører en bredere systemoppdatering ved hjelp av klientens native pakkeadministrasjonsmekanisme.

Denne operasjonen påvirker mer enn én pakke og bør derfor behandles som en vedlikeholdsoperasjon.

Før du starter en systemoppdatering, verifiser:

* klienttilgjengelighet

* vedlikeholdsvindu

* for øyeblikket kjørende jobber

* pakkebehandlertilstand

* tilgjengelig diskplass der det er relevant

* om en omstart kan være nødvendig

Etter oppdateringen, verifiser:

* jobbresultat

* klientrapport

* installert programvare

* tilgjengelige oppdateringer

* omstartstilstand

35. Oppdateringsjobber

Alle muterende pakke- og oppdateringsoperasjoner representeres som LUMS-oppdateringsjobber.

Dette gir en felles kjørings- og sporingsmodell.

Typisk jobblivssyklus:
```text

PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► FAILED
   │
   ▼
SUCCESS
```

En jobb kan også kreve ytterligere håndtering når klienten blir utilgjengelig eller kjøringen avbrytes.

Jobbhistorikken bør brukes som den autoritative driftsregistreringen i stedet for å stole utelukkende på gjeldende klientvisning.
## 36. Opprettelse av jobb

Før du oppretter en oppdateringsjobb, verifiser den tiltenkte operasjonen nøye.

Sjekk:

* klient

* handling

* pakke

* målversjon der det er relevant

* nåværende pakketilstand

* vedlikeholdskrav

Støttede handlinger inkluderer:
| Handling | Formål |
| --- | --- |
| INSTALL_PACKAGE | Installer en pakke |
| REMOVE_PACKAGE | Fjern en pakke |
| UPDATE_PACKAGE | Oppdater en spesifikk pakke |
| UPDATE_SYSTEM | Utfør en systemomfattende oppdatering |

Opprettelse av oppdateringsjobber er begrenset til Administrator- og Operator-rollene.

Viewers kan ikke opprette oppdateringsjobber.
## 37. Jobbkjøring

Etter opprettelsen behandles jobben av LUMS-agenten.

Agenten mottar jobben og utfører den forespurte operasjonen lokalt.

Serveren sporer den resulterende tilstanden.

Agenten behandler ikke en vellykket HTTP-forespørsel som bevis på at pakkeoperasjonen lyktes.

I stedet returneres det faktiske pakkebehandlerresultatet til LUMS.

Denne forskjellen er viktig:

```text
API request accepted
        ≠
Package operation successful
```

Det endelige kjøringsresultatet må derfor alltid sjekkes.
## 38. Jobbresultater

En fullført jobb skal inneholde et eksplisitt resultat.

Relevante utfall inkluderer:

* vellykket kjøring

* mislykket kjøring

* pakkebehandlerfeil

* avbrutt kjøring

* gjenopprettingsrelatert tilstand

* omstartsrelatert tilstand der det er relevant

Administratorer og Operatorer bør inspisere resultatet når en jobb mislykkes i stedet for umiddelbart å gjenta samme operasjon.

Gjentatt kjøring uten å forstå den opprinnelige feilen kan gjøre diagnose vanskeligere.
## 39. Jobbhistorikk

Oppdateringshistorikken gir en driftsregistrering av tidligere oppdateringsaktivitet.

Bruk den til å svare på spørsmål som:

* Ble denne pakken allerede oppdatert?

* Hvilken klient utførte operasjonen?

* Når ble jobben opprettet?

* Når begynte kjøringen?

* Når ble kjøringen fullført?

* Lyktes operasjonen?

* Rapporterte pakkebehandleren en feil?

Historisk jobbinformasjon er spesielt viktig når man undersøker gjentatte feil eller avbrutte vedlikeholdsoperasjoner.
## 40. Mislykkede jobber

Når en jobb mislykkes:

* registrer klienten og jobb-ID-en

* inspiser jobbresultatet

* avgjør om feilen oppstod på serveren eller klienten

* inspiser relevante agentlogger

* inspiser den native pakkebehandlerens tilstand

* rett opp det underliggende problemet

* prøv på nytt først etter at årsaken er forstått

Vanlige årsaker inkluderer:

* utilgjengelige repositorier

* pakkebehandlerlåser

* nettverksproblemer

* ugyldige pakkeforespørsler

* avhengighetskonflikter

* utilstrekkelig diskplass

* avbrutte pakkeoperasjoner

* problemer med klientautentisering eller kommunikasjon

Detaljerte diagnostiske prosedyrer er dokumentert i troubleshooting.md.
41. Pakkebehandlerlåser

APT og pacman kan forhindre samtidige pakkeoperasjoner.

Hvis en pakkeadministrasjonsoperasjon mislykkes fordi pakkebehandleren allerede er i bruk:

* identifiser den aktive pakkeadministrasjonsprosessen

* avgjør hvilken operasjon som kjører

* vent på at den legitime operasjonen fullføres når det er hensiktsmessig

* prøv LUMS-operasjonen på nytt etterpå

Ikke slett pakkebehandlerlåsefiler blindt mens pakkebehandleren kjører.

Fjerning av en låsefil løser ikke den underliggende samtidige operasjonen og kan skade pakkeadministrasjonstilstanden.
42. Inaktivitetssensitiv kjøring

LUMS kan bruke klientens inaktivitetinformasjon når den avgjør om en oppdateringsjobb skal kjøres.

Denne mekanismen er ment å unngå å avbryte aktiv interaktiv bruk av et administrert system.

Inaktivitetsdeteksjon utføres av agenten på klienten.

Hvis inaktivitetsinformasjon er utilgjengelig, må agenten rapportere den tilstanden i stedet for å oppfinne en inaktivitetstilstand.

Administratorer bør skille mellom:

* klienten er inaktiv

* klienten er aktiv

* inaktivitetsdeteksjon utilgjengelig

* klienten er utilgjengelig

Disse tilstandene har forskjellige driftsmessige betydninger.
43. Overvåking av oppdateringskjøring

Under vedlikehold, overvåk:

* jobbtilstand

* klienttilkobling

* agentaktivitet

* pakkebehandlerresultat

* omstartskrav

Ikke anta at en jobb som forblir i RUNNING på ubestemt tid betyr at pakkebehandleren fortsatt arbeider.

Hvis kjøringen ser ut til å ha stoppet, undersøk klienten og agenttilstanden før du oppretter en ny jobb.
44. Omstartskrav

Noen pakke- og systemoppdateringer kan kreve omstart.

LUMS sporer omstartsrelatert tilstand rapportert av den administrerte klienten.

Etter en systemoppdatering:

* inspiser rapportert omstartstilstand

* avgjør om en omstart er nødvendig

* utfør omstarten i et passende vedlikeholdsvindu

* la agenten rapportere igjen

* verifiser at klienten går tilbake til normal drift

Et omstartskrav bør ikke automatisk tolkes som en oppdateringsfeil.
45. Driftssjekkliste for oppdatering

For rutinemessig pakkevedlikehold:
```text

[ ] Correct client selected
[ ] Client is reachable
[ ] Current software state reviewed
[ ] Available updates reviewed
[ ] Correct package/action selected
[ ] Maintenance requirements checked
[ ] Update job created
[ ] Job execution monitored
[ ] Job result verified
[ ] Installed software verified
[ ] Available updates rechecked
[ ] Reboot state checked
[ ] Job history reviewed if required
```

Operasjonen er fullført først etter at den resulterende klienttilstanden er verifisert.
## 46. Prinsipp for pakkeadministrasjon

LUMS tilbyr sentralisert orkestrering og synlighet.

Det administrerte operativsystemet forblir ansvarlig for faktisk pakkeadministrasjon.

Derfor:

* LUMS forespør og sporer operasjonen. Den native pakkebehandleren utfører den.

Denne separasjonen lar LUMS administrere forskjellige Linux-systemer samtidig som den bevarer pakkeadministrasjonssemantikken til hvert operativsystem.
## 47. Jobbgjenoppretting

LUMS er utformet for å håndtere avbrutte oppdateringsjobber uten å blindt gjenta operasjoner som allerede er fullført.

Oppdateringskjøring bruker sjekkpunktinformasjon for å spore fremdrift.

Dette er spesielt viktig når:

* agenten avbrytes

* klienten starter på nytt

* serveren starter på nytt

* nettverkskommunikasjon midlertidig er utilgjengelig

* en pakkeoperasjon fullføres før resultatet rapporteres

Gjenopprettingsmekanismen bruker den registrerte jobbtilstanden til å avgjøre hvilket arbeid som fortsatt må utføres.
## 48. Sjekkpunkter på pakkenivå

Jobber som inneholder flere pakkeoperasjoner, behandles individuelt.

En vellykket pakkeoperasjon registreres før agenten går videre til neste operasjon.

Konseptuelt:

```text
Job
 │
 ├── Package A → SUCCESS
 │
 ├── Package B → SUCCESS
 │
 ├── Package C → interrupted
 │
 └── Package D → PENDING
```

Etter gjenoppretting bør allerede fullførte pakkeoperasjoner ikke utføres unødvendig på nytt.

Det gjenværende arbeidet kan deretter fortsette fra den registrerte tilstanden.

Dette reduserer risikoen for å gjenta pakkeoperasjoner etter et avbrudd.
## 49. Avbrutte jobber

Når en oppdateringsjobb avbrytes, ikke opprett umiddelbart en erstatningsjobb.

Avgjør først:

* hvilken jobb som ble avbrutt

* hvilken pakkeoperasjon som var aktiv

* hvilke pakkeoperasjoner som allerede lyktes

* om pakkebehandleren fullførte operasjonen

* om agenten gjenopprettet jobben automatisk

* om klienten krever omstart

Den eksisterende jobbhistorikken og agentloggene bør inspiseres før manuell inngripen.
## 50. Agentgjenoppretting

Agenten er ansvarlig for å fortsette gjenopprettbart arbeid etter et avbrudd.

Gjenoppretting bør bevare vellykkede pakkeresultater der det er mulig.

Hvis en pakkeoperasjon allerede er registrert som vellykket, må gjenoppretting ikke blindt utføre samme operasjon igjen.

Hvis gjenoppretting ikke trygt kan fastslå tilstanden til en operasjon, bør tilstanden behandles som et driftsproblem og undersøkes.

Ikke endre jobbtilstander manuelt i databasen bare for å få en jobb til å se fullført ut.
## 51. Serveromstart under en jobb

En omstart av LUMS-serveren betyr ikke nødvendigvis at pakkeoperasjonen på klientsiden ble avbrutt.

Serveren og klienten har separate kjøringstilstander.

Etter en serveromstart:

* verifiser at LUMS-containeren kjører

* verifiser databasetilgjengelighet

* verifiser at klienten kan kommunisere med LUMS

* inspiser berørte oppdateringsjobber

* sjekk agentrapporter

* verifiser den endelige pakketilstanden

Kjøringsresultatet på klientsiden forblir den viktige sannhetskilden for pakkeoperasjonen.
## 52. Klientomstart under en jobb

En klientomstart kan avbryte agentkjøring eller oppstå fordi selve oppdateringen krever omstart.

Disse situasjonene må skilles.
Forventet omstart

Oppdateringen ble fullført og systemet krever omstart.
Uventet avbrudd

Systemet startet på nytt før operasjonen ble fullført eller før resultatet kunne rapporteres.

Etter at klienten kommer tilbake:

* la agenten starte normalt

* verifiser kommunikasjon med LUMS

* inspiser den berørte jobben

* verifiser pakketilstand

* sjekk omstartstatus

* la gjenoppretting fortsette når det er relevant

## 53. Omstartsdeteksjon

LUMS kan spore omstartskrav rapportert av den administrerte klienten.

Omstartsdeteksjon er ikke det samme som å oppdage om maskinen for øyeblikket er tilgjengelig.

Dette er separate tilstander:
```text

Client reachable
        │
        ├── reboot not required
        │
        └── reboot required

Client unreachable
        │
        └── current state cannot be confirmed
```

Administratorer bør derfor unngå å behandle en utilgjengelig klient som bevis på at en omstart er nødvendig.
## 54. Verifisering etter omstart

Etter en nødvendig omstart:

* vent til operativsystemet blir tilgjengelig

* verifiser agenttjenesten eller timeren

* verifiser klientautentisering

* verifiser klientrapporten

* inspiser den berørte oppdateringsjobben

* verifiser installerte pakkeversjoner

* verifiser tilgjengelige oppdateringer

* sjekk om en ny omstart er nødvendig

En omstart bør anses som driftsmessig fullført først etter at klienten har rapportert vellykket igjen.
## 55. Overvåking av oppdateringsjobber

Administratorer og Operatorer bør overvåke jobber under planlagt vedlikehold.

Viktige tilstander inkluderer:
| Tilstand | Betydning |
| --- | --- |
| PENDING | Jobben eksisterer, men kjøringen har ikke startet |
| RUNNING | Jobbkjøring pågår |
| SUCCESS | Kjøringen ble fullført vellykket |
| FAILED | Kjøringen ble fullført med en feil |

En jobbtilstand bør alltid tolkes sammen med resultatinformasjonen.

For eksempel bør en FAILED-jobb undersøkes ved hjelp av det registrerte resultatet i stedet for bare å prøve på nytt.
## 56. Kjøringsovervåker

LUMS-agenten inkluderer en dedikert kjøringsovervåker.

Overvåkeren er ansvarlig for å overvåke kjøring av oppdateringsjobber på klienten.

Formålet er å støtte pålitelig kjøringshåndtering uavhengig av rapporteringsarbeidsflyten.

Gjeldende overvåker-versjon er:

Watcher 1.2.1

Agentversjonen er:

Agent 1.7.0

Disse versjonene bør verifiseres etter klientoppgraderinger.
## 57. Overvåking av overvåkeren

Administratorer kan inspisere overvåkeren gjennom systemd på den administrerte klienten.

Nyttige sjekker inkluderer:

```bash
systemctl status lums-agent-watcher.service --no-pager
```

og:

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

Timeren kan inspiseres med:

```bash
systemctl status lums-agent-watcher.timer --no-pager
```

Den nøyaktige aktive/inaktive tilstanden til en oneshot-tjeneste bør tolkes sammen med timeren og journalen.

En inactive (dead)-tilstand er ikke automatisk en feil for en oneshot-tjeneste.
## 58. Timere for rapportering og kjøring

LUMS skiller vanlig klientrapportering fra kjøringsovervåking.

Rapporteringstimeren er ansvarlig for planlagt agentkjøring.

Overvåkertimeren er ansvarlig for planlagt overvåkerkjøring.

Inspiser begge når du diagnostiserer planleggingsproblemer på klientsiden:

```bash
systemctl list-timers --all | grep lums-agent
```

Forventede enheter inkluderer:

```text
lums-agent.timer
lums-agent-watcher.timer
```

Hvis en timer ikke kjører, inspiser:

```bash
systemctl status lums-agent.timer --no-pager
systemctl status lums-agent-watcher.timer --no-pager
```

Inspiser deretter de tilsvarende journaloppføringene.
## 59. Revisjonslogging

LUMS registrerer viktige administrative og sikkerhetsrelevante applikasjonshandlinger i revisjonsloggen.

Revisjonsinformasjon kan hjelpe med å fastslå:

* hvilken operasjon som fant sted

* hvilken bruker som initierte den

* hvilken klient som ble påvirket

* når operasjonen fant sted

* om operasjonen ble godtatt

* hvilken administrativ handling som ble utført

Revisjonsinformasjon bør behandles som driftsbevis.

Den bør ikke slettes eller endres uforsiktig.
## 60. Administrative revisjonshendelser

Relevant administrativ aktivitet inkluderer operasjoner som:

* opprettelse av bruker

* tildeling av rolle

* klientadministrasjon

* tokenrotasjon

* opprettelse av oppdateringsjobb

* pakkeadministrasjonsoperasjoner

* sikkerhetshendelser relatert til autentisering

De nøyaktige hendelsesdataene avhenger av operasjonen.

Administratorer bør bruke revisjonsinformasjon sammen med jobbhistorikk når de undersøker uventet aktivitet.
## 61. Håndtering av revisjonslogger

Revisjonslogger bør håndteres nøye.

Ikke:

* endre historiske revisjonsoppføringer for å skjule en operasjon

* eksponer sensitive legitimasjoner i eksporterte logger

* publiser logger som inneholder klienttokener

* publiser passord eller autentiseringsmateriale

* kopier sensitiv loggutdata til offentlige saksbehandlingssystemer

Hvis logger må deles for feilsøking, rediger bort legitimasjon og annen sensitiv informasjon først.
62. Applikasjonslogger

Applikasjonslogger beskriver den interne driften av LUMS-serveren.

Nyttige kilder inkluderer:
```bash

sudo docker logs --tail 100 lums
```

For direktesporing:

```bash
sudo docker logs -f lums
```

Når du undersøker et problem, begrens tidsvinduet der det er mulig.

Ikke dump automatisk hele produksjonsloggen når en mindre relevant seksjon er tilstrekkelig.
## 63. Agentlogger

Agentaktivitet på klientsiden kan inspiseres gjennom systemd:

```bash
journalctl -u lums-agent.service --no-pager -n 100
```

For overvåkeraktivitet:

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

For et spesifikt tidsvindu kan systemd journal-filtrering brukes.

Eksempel:

```bash
journalctl -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Logger bør korreleres med den berørte jobb-ID-en når det er mulig.
## 64. Loggkorrelasjon

Når du undersøker et oppdateringsproblem, korreler informasjon på tvers av systemet:

```text id="jv3j7c"
Web UI
  │
  ├── Job ID
  │
  ▼
LUMS API / Application Log
  │
  ▼
Update Job
  │
  ▼
Agent
  │
  ▼
Native Package Manager
```

Dette forhindrer den vanlige feilen med å anta at et problem observert i ett lag oppstod i samme lag.
## 65. Sjekkliste for administrativ overvåking

Under normal drift, verifiser periodisk:

```text
[ ] LUMS container is running
[ ] HTTPS endpoint is available
[ ] Database is accessible
[ ] Clients are reporting
[ ] No unexpected failed jobs
[ ] No unexplained authentication failures
[ ] Agent timers are active
[ ] Watcher timers are active
[ ] Package-manager operations complete normally
[ ] Audit activity is available
[ ] Logs contain no unexplained recurring errors
```

Frekvensen av disse sjekkene bør samsvare med den driftsmessige betydningen av LUMS-distribusjonen.
## 66. Gjenopprettingsprinsipp

Når et oppdateringsproblem oppstår, er den sikreste administrative tilnærmingen:

```text
Observe
   │
   ▼
Identify affected job/client
   │
   ▼
Inspect state and logs
   │
   ▼
Determine actual failure point
   │
   ▼
Correct underlying problem
   │
   ▼
Allow recovery or retry
   │
   ▼
Verify final state
   │
   ▼
Document significant incidents
```

Unngå destruktive gjenopprettingshandlinger med mindre den faktiske feiltilstanden er forstått.

Spesielt: ikke slett jobber, databaseregistreringer, pakkebehandlerlåser eller vedvarende klientdata manuelt bare for å gjenopprette et rent utseende i grensesnittet.

* Bevar bevis først. Reparer tilstand deretter. Verifiser resultatet til slutt.

## 67. Databaseadministrasjon

LUMS bruker SQLite som applikasjonsdatabase.

Produksjonsdatabasen lagres inne i det vedvarende Docker-volumet:

```text
/var/lib/lums/lums.db
```

Databasen er vedvarende på tvers av containerutskifting så lenge Docker-volumet bevares.

Databasen inneholder applikasjonstilstand som:

* brukere

* administrerte klienter

* oppdateringsjobber

* pakkeinformasjon

* revisjonsinformasjon

* autentiseringsrelatert tilstand

* migreringstilstand

Administratorer bør behandle databasen som kritiske applikasjonsdata.
## 68. SQLite-kjøringskonfigurasjon

Gjeldende produksjonsbaseline for SQLite er:
| Innstilling | Verdi |
| --- | --- |
| journal_mode | wal |
| busy_timeout | 5000 |
| synchronous | 2 |
| foreign_keys | aktivert av applikasjonen |

Applikasjonen aktiverer eksplisitt SQLite-fremmednøkkelhåndheving for databaseforbindelser.

Administratorer bør ikke endre disse innstillingene uforsiktig.

Endringer i databasens kjøringskonfigurasjon bør testes før de introduseres i produksjon.
## 69. Databaseintegritet

Databaseintegritet bør sjekkes når det er indikasjoner på databasekorrupsjon eller uventet applikasjonsatferd.

En typisk SQLite-integritetskontroll er:

```bash id="f0g8sl"
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

En sunn database skal returnere:

```text
ok
```

Hvis integritetskontrollen rapporterer feil, ikke fortsett å endre applikasjonstilstanden blindt.

Bevar den berørte databasen og undersøk årsaken.
## 70. Databasemigreringer

LUMS bruker applikasjonsmigreringer for å introdusere databaseendringer.

Migreringer bør tillates å kjøre gjennom applikasjonens normale oppstarts- og migreringsmekanisme.

Administratorer bør ikke endre migreringstilstanden manuelt bare for å omgå en feil.

Etter en applikasjonsoppdatering, verifiser:

* containeren starter vellykket

* migreringer fullføres

* applikasjonen er tilgjengelig

* eksisterende brukere forblir tilgjengelige

* eksisterende klienter forblir tilgjengelige

* eksisterende jobbhistorikk forblir tilgjengelig

## 71. Vedvarende Docker-volum

Docker-volumet som inneholder LUMS-applikasjonsdata er en kritisk vedvarende ressurs.

Produksjonsvolumet er:
```text

lums-data
```

Inspiser det med:

```bash id="f3z2kd"
sudo docker volume inspect lums-data
```

Volumet må forbli tilkoblet når LUMS-containeren erstattes.

Fjerning av containeren fjerner ikke volumet automatisk.

Fjerning av volumet fjerner imidlertid permanent de vedvarende applikasjonsdataene med mindre en separat sikkerhetskopi eksisterer.
## 72. Containeradministrasjon

LUMS-applikasjonen kjører inne i en herdet Docker-container.

Produksjonens sikkerhetsbaseline inkluderer:

* applikasjonsbruker uten root

* skrivebeskyttet rotfilsystem

* fjernede Linux-capabilities

* no-new-privileges

* begrensede midlertidige filsystemer

* skrivebeskyttet hemmelighetsmontering

* dedikert vedvarende datavolum

* applikasjonsport kun på localhost

Containeren bør ikke startes med svakere sikkerhetsinnstillinger bare fordi feilsøking blir mer praktisk.
## 73. Containerstatus

Sjekk gjeldende containertilstand med:

```bash id="4n6p2v"
sudo docker ps --filter name=lums
```

Inspiser den fullstendige kjøringskonfigurasjonen med:

```bash id="k1q4z8"
sudo docker inspect lums
```

Viktige egenskaper inkluderer:

* kjøringstilstand

* omstartspolicy

* bruker

* skrivebeskyttet rotfilsystem

* capabilities

* sikkerhetsvalg

* portbindinger

* volumbaner

## 74. Verifisering av containersikkerhet

Den herdede kjøringen skal fortsette å gi de forventede egenskapene.

For eksempel:

```bash id="0u7x3n"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

Den forventede baselinen tilsvarer:

```text
lums true false
```

Capabilities skal forbli fjernet:

```bash id="k5n8ae"
sudo docker inspect lums \
    --format '{{json .HostConfig.CapDrop}}'
```

Forventet:

```text
["ALL"]
```

Sikkerhetsvalg skal inkludere:

```text
no-new-privileges:true
```

## 75. Applikasjonsport

LUMS-applikasjonen lytter på verten gjennom loopback-grensesnittet.

Den forventede tilordningen er:

```text
127.0.0.1:5050 → container:5000
```

Verifiser det med:

```bash id="b6v2w0"
sudo docker port lums
```

Applikasjonsporten bør ikke eksponeres direkte mot LAN.

Ekstern tilgang leveres gjennom Nginx over HTTPS.
## 76. Nginx og HTTPS

Nginx gir det eksterne HTTPS-inngangspunktet for LUMS.

Den normale forespørselsbanen er:

```text
Client Browser
      │
      ▼
HTTPS :443
      │
      ▼
Nginx
      │
      ▼
127.0.0.1:5050
      │
      ▼
LUMS Container
```

Docker-applikasjonsporten bør forbli bundet til localhost.

Administratorer bør derfor unngå å eksponere port 5050 direkte gjennom brannmuren eller Docker-konfigurasjonen.
## 77. HTTPS-verifisering

Etter Nginx-endringer, valider alltid konfigurasjonen før du laster på nytt:

```bash id="7f1h9m"
sudo nginx -t
```

Hvis konfigurasjonen er gyldig:

```bash id="4g5s2w"
sudo systemctl reload nginx
```

Verifiser deretter HTTPS:

```bash id="2w8v6c"
curl -I https://LUMS-SERVER/
```

Erstatt LUMS-SERVER med vertsnavnet som dekkes av serverens TLS-sertifikat. Ikke bruk -k for rutinemessig verifisering; det hopper over sertifikatvalidering.

En vellykket HTTPS-respons bekrefter at Nginx kan nå LUMS-applikasjonen.

Sertifikatvalidering bør også testes ved hjelp av vertsnavnet eller adressen som administratorer normalt bruker.

Ikke deaktiver sertifikatvalidering permanent med -k.
## 78. HTTP-omdirigering

HTTP-endepunktet skal omdirigere klienter til HTTPS.

Verifiser:

```bash id="w5q0rx"
curl -I http://127.0.0.1/
```

Den forventede atferden er en HTTP-omdirigering til HTTPS-endepunktet.

Administrativ tilgang bør bruke HTTPS.
## 79. Vedlikehold av TLS-sertifikat

TLS-sertifikater og private nøkler er eksterne i forhold til Docker-bildet.

Typiske plasseringer er:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Private nøkler må forbli beskyttet.

Før du erstatter et sertifikat:

* verifiser det nye sertifikatet

* verifiser den samsvarende private nøkkelen

* verifiser filrettigheter

* valider Nginx-konfigurasjonen

* last Nginx på nytt

* verifiser HTTPS

* verifiser applikasjonsinnlogging

Plasser aldri private TLS-nøkler i Git-repositoriet eller Docker-bildet.
## 80. Håndtering av hemmeligheter

Applikasjonshemmeligheten lagres utenfor containerbildet.

Produksjonshemmeligheten monteres skrivebeskyttet inn i containeren:
```text

/etc/lums/secrets/lums_secret
        │
        ▼
/run/secrets/lums_secret
```

Applikasjonen mottar hemmeligheten gjennom:

```text
LUMS_SECRET_KEY_FILE
```

Administratorer må aldri:

* committe hemmeligheten

* skrive ut hemmeligheten

* inkludere hemmeligheten i dokumentasjon

* eksponere den i skjermbilder

* plassere den i et bildelag

Hvis hemmeligheten antas å være eksponert, behandl den som kompromittert og følg den aktuelle prosedyren for hemmelighetsrotasjon.
## 81. Sikkerhetskopistrategi

LUMS-data bør sikkerhetskopieres før betydelige administrative endringer.

Som et minimum, vurder å beskytte:

* SQLite-applikasjonsdata

* applikasjonskonfigurasjon

* TLS-materiale

* applikasjonshemmeligheter

* klientkonfigurasjonsinformasjon

* relevant driftsdokumentasjon

Sikkerhetskopier bør lagres separat fra produksjonscontaineren og dens vedvarende Docker-volum.

En sikkerhetskopi som bare eksisterer på samme vert eller Docker-volum gir ikke tilstrekkelig beskyttelse mot tap av den verten eller det volumet.
## 82. Databasesikkerhetskopi

SQLite-databasen bør sikkerhetskopieres ved hjelp av en SQLite-bevisst metode i stedet for bare å kopiere en aktivt endret databasefil uten hensyn til tilstanden.

Før du utfører en sikkerhetskopi:

* identifiser produksjonsdatabasen

* sikre at sikkerhetskopimålet er tilgjengelig

* opprett sikkerhetskopien ved hjelp av en passende SQLite-sikker metode

* verifiser at sikkerhetskopien eksisterer

* registrer når den ble opprettet

Ikke anta at en vellykket filkopi automatisk betyr at en gyldig gjenopprettbar databasesikkerhetskopi eksisterer.
83. Verifisering av sikkerhetskopi

En sikkerhetskopi anses ikke som pålitelig før den er testet.

Verifiser periodisk at en sikkerhetskopi kan:

* leses

* åpnes som SQLite-data

* kontrolleres for integritet

* gjenopprettes i et isolert testmiljø

For eksempel kan en utpakket testkopi sjekkes med:

```bash id="p3v7cx"
sqlite3 /path/to/test-copy.db \
    "PRAGMA integrity_check;"
```

Forventet resultat:

```text
ok
```

En produksjonssikkerhetskopi bør aldri testes ved å overskrive den aktive produksjonsdatabasen.
## 84. Gjenopprettingsprinsipp

Gjenoppretting er en kontrollert administrativ operasjon.

Før gjenoppretting:

* identifiser riktig sikkerhetskopi

* verifiser integriteten

* fastslå nødvendig gjenopprettingspunkt

* stopp eller isoler applikasjonsaktivitet etter behov

* bevar gjeldende produksjonstilstand

* gjenopprett sikkerhetskopien

* verifiser databaseintegritet

* start applikasjonen

* verifiser migreringer

* verifiser brukere og klienter

* verifiser jobbhistorikk

* verifiser normal klientrapportering

Ikke overskriv den eneste kopien av produksjonsdatabasen under gjenoppretting.
85. Verifisering av gjenoppretting

Etter en gjenoppretting, verifiser som et minimum:

```text id="q6r2yh"
[ ] Container starts
[ ] Database opens
[ ] SQLite integrity check passes
[ ] Users are present
[ ] Roles are correct
[ ] Clients are present
[ ] Client authentication works
[ ] Job history is present
[ ] Audit information is available
[ ] HTTPS works
[ ] Clients can report
[ ] New operations can be created
```

En gjenoppretting er fullført først etter at applikasjonen og dens administrerte klienter er verifisert.
## 86. Prinsipp for serversikkerhetskopi

Den viktigste administrative regelen for vedvarende LUMS-data er:

* Utfør aldri en destruktiv database- eller volumoperasjon uten en verifisert gjenopprettingsbane.

Spesielt: ikke fjern lums-data bare fordi containeren bygges på nytt eller erstattes.

Containerutskifting og sletting av vedvarende data er separate operasjoner.
## 87. Sjekkliste for administrativ server

Før du gjør en betydelig endring på serversiden:

```text id="7h3m0p"
[ ] Current container state recorded
[ ] Current image recorded
[ ] Database backup available
[ ] Backup integrity verified
[ ] Active jobs reviewed
[ ] Client reporting state reviewed
[ ] Configuration changes documented
[ ] TLS material available
[ ] Secret handling verified
[ ] Rollback path known
```

Først etter at disse forholdene er vurdert, bør en betydelig produksjonsendring fortsette.
## 88. Prinsipp for serveradministrasjon

LUMS skiller applikasjonstilstand fra den engangs applikasjonscontaineren.

```text
Disposable
└── LUMS Container

Persistent
├── SQLite Database
└── lums-data Volume

External
├── TLS Material
└── Application Secret
```

Denne separasjonen lar applikasjonscontaineren erstattes uten å bevisst ødelegge vedvarende applikasjonsdata.

* Erstatt applikasjonen når det er nødvendig. Bevar dataene med mindre sletting av data er eksplisitt tilsiktet.

## 89. Rutinemessig vedlikehold

Rutinemessig vedlikehold holder LUMS-installasjonen pålitelig og reduserer risikoen for uventede driftsproblemer.

Typiske vedlikeholdsaktiviteter inkluderer:

* gjennomgang av mislykkede oppdateringsjobber

* sjekk av klientrapportering

* gjennomgang av applikasjonslogger

* gjennomgang av revisjonsaktivitet

* verifisering av sikkerhetskopier

* sjekk av tilgjengelig diskplass

* gjennomgang av Docker-containertilstand

* sjekk av TLS-sertifikatets gyldighet

* gjennomgang av sikkerhetsoppdateringer

* verifisering av gjeldende LUMS-versjon og -bilde

Vedlikehold bør utføres i et passende vedlikeholdsvindu når endringer kan påvirke produksjonsklienter.
90. Vedlikehold før endringer

Før du utfører vedlikehold som kan påvirke LUMS-serveren:

* gjennomgå aktive oppdateringsjobber

* verifiser at klienter ikke gjennomgår uventet vedlikehold

* opprett eller verifiser en gjeldende sikkerhetskopi

* registrer gjeldende container- og bildetilstand

* dokumenter den planlagte endringen

* sikre at en tilbakerullingsbane eksisterer

Ikke start vedlikehold med å umiddelbart stoppe eller slette produksjonskomponenter.

Fastslå først gjeldende tilstand.
91. Vedlikehold av Docker-bilde

LUMS-applikasjonsbilder bør bygges på nytt fra det gjennomgåtte kildetreet.

Før du bygger et nytt bilde:

```bash id="x0m7r4"
cd /opt/lums-public
```

Kjør det automatiserte testsettet:

```bash id="4gk1dp"
./.venv-test/bin/pytest -q
```

Fortsett bare når testresultatet er forstått.

Bygg det nye bildet med en distinkt midlertidig tag:

```bash id="m8q3vz"
sudo docker build -t lums:new .
```

En midlertidig tag lar det kjørende bildet forbli identifiserbart under erstatningsprosessen.
## 92. Bildeverifisering

Etter bygging av et nytt bilde, verifiser at bildet eksisterer:

```bash id="h6s2we"
sudo docker image inspect lums:new
```

Gå gjennom bildekonfigurasjonen før distribusjon.

Der det er relevant, verifiser:

* bildets digest

* basebilde

* applikasjonsfiler

* installerte avhengigheter

* bildestørrelse

* eksponerte porter

* konfigurert bruker

Bildet bør bare distribueres etter at bygge- og testresultatene er gjennomgått.
## 93. Kontrollert containerutskifting

Containerutskifting bør utføres bevisst.

Før du erstatter produksjonscontaineren:

```text id="m3z8qk"
[ ] Tests passed
[ ] New image exists
[ ] Database backup available
[ ] Active jobs reviewed
[ ] Current image recorded
[ ] Persistent volume confirmed
[ ] Secret available
[ ] TLS configuration available
[ ] Rollback image identified
```

Før du kjører eksempelet, sammenlign det med den faktisk kjørende containeren. Verdiene nedenfor er et eksempel, ikke en kommando som er trygg for hver installasjon. Spesielt må Docker bind-mount kildebaner på venstre side av : samsvare med verten din, og den gamle containeren kan ha et annet navn.

Vis bildet, monteringene, publiserte porter, omstartspolicy og herdingsinnstillinger uten å skrive ut miljøvariabelverdier:

```bash
sudo docker inspect lums --format 'Image={{.Config.Image}}
Mounts={{json .Mounts}}
Ports={{json .HostConfig.PortBindings}}
Restart={{json .HostConfig.RestartPolicy}}
Readonly={{.HostConfig.ReadonlyRootfs}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
Tmpfs={{json .HostConfig.Tmpfs}}'
```

Lagre utdataene et privat sted og bruk dem til å sjekke at den nye containeren beholder samme databasevolum, hemmelighetsfil, sikkerhetskopikatalog, lokal portbinding og sikkerhetsvalg. Ikke lim inn hemmelighetsinnhold eller miljøverdier i notater eller meldinger.

Stopp den eksisterende containeren først etter at disse forholdene er vurdert.

Produksjonscontaineren bør beholde den herdede kjøringskonfigurasjonen.

Eksempel:

```bash id="n8q2kf"
sudo docker stop lums
sudo docker rename lums lums-before-upgrade
```

Start deretter det nye bildet med den etablerte herdede konfigurasjonen:

```bash id="c7w4md"
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /run:rw,noexec,nosuid,size=16m \
    -p 127.0.0.1:5050:5000 \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -v /var/backups/lums:/var/backups/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -e LUMS_BACKUP_DIR=/var/backups/lums \
    lums:new
```

Ikke fjern lums-before-upgrade før den nye distribusjonen er validert.
## 94. Validering etter oppgradering

Umiddelbart etter at containeren er erstattet, verifiser:

```bash id="b4m7tz"
sudo docker ps --filter name=lums
```

Inspiser deretter loggene:

```bash id="v5n2ra"
sudo docker logs --tail 100 lums
```

Verifiser HTTPS:

```bash id="w9x1kf"
curl -I https://LUMS-SERVER/
```

Erstatt LUMS-SERVER med vertsnavnet som dekkes av serverens TLS-sertifikat. Ikke bruk -k for rutinemessig verifisering; det hopper over sertifikatvalidering.

Verifiser deretter applikasjonen gjennom det normale administrasjonsgrensesnittet.

Sjekk at eksisterende brukere, klienter og nylig historikk fortsatt er til stede.
Gå gjennom loggene for oppstarts- eller migreringsfeil. En kjørende container alene
beviser ikke at applikasjonen eller databasen er sunn.
Rull tilbake hvis den nye containeren ikke fungerer

Behold den gamle containeren til den nye versjonen har bestått validering. Hvis den
nye containeren er ubrukelig og du har bekreftet at den gamle containeren heter
lums-before-upgrade, stopp og fjern bare den nye containeren, og
gi den gamle nytt navn og start den på nytt:

```bash
sudo docker stop lums
sudo docker rm lums
sudo docker rename lums-before-upgrade lums
sudo docker start lums
```

docker rm lums uten -v fjerner containeren, ikke lums-data-volumet. Legg aldri til -v i denne tilbakerullingskommandoen. Hvis containernavnet avviker,
eller du ikke er sikker på hvilken container som er gammel versus ny, ikke kjør disse
kommandoene; inspiser gjeldende tilstand eller spør en administrator om hjelp. Etter
tilbakerulling, inspiser logger og verifiser at webgrensesnittet og dataene er
tilgjengelige.
## 95. Vedvarende data etter oppgradering

Containerutskifting må ikke fjerne det vedvarende Docker-volumet.

Verifiser:

```bash id="j4p8sx"
sudo docker inspect lums \
    --format '{{json .Mounts}}'
```

Bekreft at:

```text id="m7z3kc"
/var/lib/lums
```

er støttet av det forventede vedvarende volumet.

Verifiser deretter:

* brukere eksisterer fortsatt

* roller forblir korrekte

* klienter forblir registrerte

* jobbhistorikk forblir tilgjengelig

* revisjonsinformasjon forblir tilgjengelig

* migreringer ble fullført vellykket

## 96. Sikkerhetsbaseline etter oppgradering

Etter distribusjon av et nytt bilde, verifiser den herdede kjøringen igjen.

Sjekk:

```bash id="q6c3xv"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

Forventet baseline:

```text id="s0r8jm"
lums true false
```

Verifiser også:

```text id="g4m2vx"
CapDrop = ALL
SecurityOpt = no-new-privileges:true
```

og at:

```text id="c3p9rw"
127.0.0.1:5050 → container:5000
```

forblir applikasjonseksponeringen.

En vellykket applikasjonsoppgradering må ikke stille svekke sikkerhetsbaselinen.
## 97. Klientkommunikasjon etter oppgradering

Etter en serveroppgradering, verifiser at administrerte klienter fortsatt kan kommunisere.

Sjekk minst én representativ klient først.

Verifiser:

```text id="x8h5qk"
[ ] Client authentication succeeds
[ ] Client report is accepted
[ ] Installed software is available
[ ] Available updates are available
[ ] Update jobs can be created
[ ] Agent results are accepted
```

Hvis flere klientplattformer er distribuert, verifiser representative systemer fra hver støttede plattform.
## 98. Oppdateringskjøring etter oppgradering

Ikke utfør umiddelbart en stor produksjonsoppdatering etter at LUMS-serveren er erstattet.

Utfør først en kontrollert funksjonell test.

En passende test bør verifisere hele banen:

```text id="y7k2fd"
Web UI
  ↓
API
  ↓
Update Job
  ↓
Agent
  ↓
Package Manager
  ↓
Result
  ↓
Database
  ↓
Web UI
```

Først etter at den kontrollerte testen lykkes, bør normale vedlikeholdsoperasjoner gjenopptas.
## 99. Tilbakerulling

Tilbakerulling bør være mulig når et nytt bilde forårsaker et uventet produksjonsproblem.

Bevar:

* forrige fungerende bilde

* vedvarende data

* databasesikkerhetskopi

* forrige konfigurasjon

* forrige TLS-materiale

* relevante logger

Hvis den nye containeren ikke er brukbar:

* stopp den nye containeren

* bevar den for undersøkelse når det er praktisk

* stopp ytterligere administrative endringer

* gjenopprett det tidligere kjente gode bildet

* gjenbruk det eksisterende vedvarende volumet

* start den herdede kjøringen

* verifiser applikasjonen

* verifiser klienter

* verifiser jobbtilstand

* undersøk det mislykkede bildet separat

Ikke slett det vedvarende volumet som en del av en normal tilbakerulling.
100. Validering av tilbakerulling

Etter tilbakerulling, verifiser:

```text id="z1j8md"
[ ] LUMS starts
[ ] HTTPS works
[ ] Users can authenticate
[ ] Roles are correct
[ ] Clients are present
[ ] Client authentication works
[ ] Job history is available
[ ] Audit information is available
[ ] Package inventory is available
[ ] Update jobs can be tracked
[ ] Security baseline is intact
```

En tilbakerulling er fullført først etter at applikasjonen og klientkommunikasjonsbanen er verifisert.
## 101. Nødadministrasjon

Nødadministrasjon bør bevare bevis og vedvarende tilstand når det er mulig.

Eksempler inkluderer:

* gjentatte applikasjonskrasj

* databaseintegritetsfeil

* omfattende klientautentiseringsfeil

* uventet pakkejobbatferd

* mistenkt eksponering av legitimasjon

* ødelagte oppgraderinger

* TLS-feil som påvirker alle brukere

Den foretrukne sekvensen er:

```text id="f8k3wz"
Preserve
   ↓
Observe
   ↓
Isolate
   ↓
Recover
   ↓
Verify
   ↓
Document
```

Unngå å slette logger, databaser, containere eller klientregistreringer bare fordi de ser ut til å være en del av problemet.
## 102. Prinsipp for administrativ endring

Hver betydelig produksjonsendring bør ha tre klart definerte tilstander:
Før

Gjeldende produksjonstilstand er kjent og gjenopprettbar.
Under

Endringen utføres ved hjelp av den dokumenterte prosedyren.
Etter

Den resulterende tilstanden verifiseres mot den forventede baselinen.

Dette gjør administrativt arbeid reproduserbart og reduserer utilsiktet konfigurasjonsdrift.
## 103. Kontrollert avinstallering

Avinstallering er en destruktiv administrativ operasjon.

Den bør bare utføres når LUMS-distribusjonen bevisst fjernes.

Før du fjerner LUMS:

```text id="u5r2nc"
[ ] All managed clients identified
[ ] Active update jobs reviewed
[ ] Required job history exported or preserved
[ ] Required audit information preserved
[ ] Database backup created
[ ] Backup verified
[ ] TLS material preserved if required
[ ] Application secret preserved if required
[ ] Documentation preserved
[ ] Reinstallation requirements documented
```

Ikke fjern vedvarende data før du bekrefter at de ikke lenger er nødvendige.
## 104. Fjerne containeren

For å fjerne applikasjonscontaineren etter at distribusjonen er avviklet:

```bash id="n2x7kc"
sudo docker stop lums
sudo docker rm lums
```

Docker-volumet fjernes bevisst ikke av disse kommandoene.

Dette lar applikasjonsdataene forbli tilgjengelige for senere inspeksjon eller gjenoppretting.
## 105. Fjerne vedvarende data

Fjerning av LUMS Docker-volumet er en separat destruktiv operasjon.

Utfør bare dette etter å ha bekreftet at databasen og all lagret applikasjonstilstand ikke lenger er nødvendig.

Eksempel:

```bash id="r8w3mz"
sudo docker volume rm lums-data
```

Dette fjerner permanent de vedvarende applikasjonsdataene som er lagret i det volumet.

Ikke utfør denne kommandoen under en normal oppgradering eller tilbakerulling.
## 106. Fjerne klientkomponenter

Når en administrert klient permanent fjernes fra LUMS, avinstaller eller deaktiver agentkomponentene i henhold til klientens operativsystemprosedyre.

Klienten skal ikke lenger rapportere til LUMS-serveren etter avvikling.

Bevar relevant jobb- og revisjonsinformasjon før du fjerner klienten hvis historiske registreringer er nødvendige.
## 107. Endelig administrativ sjekkliste
Brukeradministrasjon

```text id="p5z8cv"
[ ] Users have appropriate roles
[ ] Administrator access is limited
[ ] Disabled accounts are reviewed
[ ] Credentials are protected
```

Klientadministrasjon

```text id="q2m7xd"
[ ] Clients are correctly registered
[ ] Client tokens are protected
[ ] Disabled clients are reviewed
[ ] Token rotation is performed when required
[ ] Client reporting is healthy
```

Oppdateringsadministrasjon

```text id="h6v9kt"
[ ] Available updates are reviewed
[ ] Update jobs are monitored
[ ] Failed jobs are investigated
[ ] Package operations are verified
[ ] Reboot requirements are checked
[ ] Job history is retained
```

Serveradministrasjon

```text id="r3c8wn"
[ ] Container is running
[ ] Persistent volume is attached
[ ] SQLite integrity is healthy
[ ] HTTPS is working
[ ] TLS material is valid
[ ] Application secret is protected
[ ] Backups are available
```

Sikkerhet

```text id="v7m4qx"
[ ] RBAC remains enforced
[ ] Viewer restrictions remain intact
[ ] Client authentication works
[ ] Container remains hardened
[ ] Application port remains localhost-only
[ ] No credentials are exposed
[ ] Logs contain no unexplained sensitive information
```

## 108. Driftsbaseline

En sunn LUMS-installasjon skal oppfylle følgende baseline:

```text id="d4k9sy"
Application
    ├── HTTPS available
    ├── Authentication available
    └── RBAC enforced

Server
    ├── Hardened container
    ├── Persistent database
    └── Valid migrations

Clients
    ├── Authenticated
    ├── Reporting
    ├── Software inventory available
    └── Update information available

Operations
    ├── Update jobs executable
    ├── Results recorded
    ├── Recovery supported
    └── Reboot state reported

Security
    ├── Secrets protected
    ├── Tokens protected
    ├── Audit information retained
    └── Network exposure restricted

Recovery
    ├── Backups available
    ├── Restore path known
    └── Rollback path known
```

## 109. Administrasjon fullført

LUMS-administrasjon bør alltid prioritere kontrollerte, observerbare og reversible endringer.

Administrasjonslivssyklusen er:

```text id="w6f1pa"
Plan
  ↓
Observe
  ↓
Change
  ↓
Verify
  ↓
Document
  ↓
Maintain
```

De viktigste driftsprinsippene er:

* Bruk minst mulig privilegium som er nødvendig.

* Bevar vedvarende data.

* Ikke endre tilstand uten å forstå gjeldende tilstand.

* Verifiser resultatet av hver betydelig operasjon.

* Hold en testet gjenopprettingsbane.

For installasjonsprosedyrer, se install.md.

For sikkerhetsarkitektur og revisjonsresultater, se security.md.

For diagnose- og gjenopprettingsprosedyrer, se troubleshooting.md.
## 110. Endelig administrasjonsprinsipp

LUMS er ment å gjøre Linux-oppdateringsadministrasjon forutsigbar og observerbar.

Administrativt arbeid bør derfor ikke være basert på antakelser eller blind gjentakelse.

Når noe endres:

Observer først. Endre deretter. Verifiser til slutt.

Når noe går i stykker:

Bevar bevis. Identifiser feillaget. Gjenopprett bevisst.

Når noe fungerer:

Registrer resultatet og behold den kjente gode baselinen.
text

