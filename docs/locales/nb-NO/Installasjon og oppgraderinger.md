# LUMS-installasjonsveiledning

## Linux Update Management Server

**Prosjekt:** LUMS
**Slagord:** Linux Update Management without the noise.
**Repositorium:** `NovaForgeCtrl/LUMS`

---

## Kom i gang: forstå installasjonen før du begynner

Denne veiledningen dekker en komplett serverinstallasjon, inkludert avanserte
vedlikeholds- og verifiseringsprosedyrer. Den er **ikke** et enkelt skript som
skal kjøres uten gjennomgang: servernavn, TLS-sertifikat, hemmelighetsfil,
sikkerhetskopimål, nettverk og database varierer mellom installasjoner.

### Hva blir installert?

* **LUMS-server:** webgrensesnittet og API-et, som kjører i en Docker-container.
* **Nginx:** tar imot eksterne HTTPS-tilkoblinger og videresender dem lokalt
  til containeren.
* **Datavolum:** inneholder SQLite-databasen. Dette volumet må overleve
  oppgraderinger og må aldri slettes ved et vanlig containerbytte.
* **Hemmelighetsfil:** beskytter blant annet applikasjonsøkter. Legg den aldri
  i Git-repositoriet, et Docker-bilde eller en chatmelding.
* **LUMS Agent og Watcher:** installeres separat på administrerte Linux-klienter.
  En fungerende server alene oppdaterer ingen klienter.

| Begrep | Betydning |
| --- | --- |
| Terminal / skall | Et tekstvindu der du skriver Linux-kommandoer. |
| `sudo` | Kjører kommandoen som følger med administratorrettigheter. Linux kan be om passordet ditt. |
| Vert | Linux-maskinen som kjører Docker og LUMS-serveren. |
| Container | En isolert prosess som kjører LUMS-webapplikasjonen. |
| Bilde (image) | En ferdig mal Docker bruker til å starte en container. |
| Volum | Vedvarende Docker-lagring som blir værende når en container byttes ut. |
| Plassholder | Tekst som `LUMS-SERVER` som må erstattes med din faktiske verdi. |

### Kjør bare tester (dette installerer ingen server)

Disse trinnene egner seg for Debian 13 for å hente ut kildekoden og kjøre tester
lokalt. De oppretter **ikke** en produksjonsserver som er tilgjengelig over
nettverket, og installerer ikke en agent på en annen datamaskin. `sudo` trengs
bare for å installere Debian-pakker.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
git clone https://github.com/NovaForgeCtrl/LUMS.git ~/LUMS
cd ~/LUMS
python3 -m venv .venv-test
./.venv-test/bin/python -m pip install -r server/requirements.txt -r requirements-dev.txt
./.venv-test/bin/pytest -q
```

`apt update` oppdaterer pakkelistene; den oppgraderer ikke all installert
programvare. Det virtuelle Python-miljøet `.venv-test` holder testavhengighetene
atskilt fra resten av systemet. En vellykket testkjøring avsluttes med kode
`0`; antall tester kan endre seg etter hvert som prosjektet vokser. Hvis
opprettingen av miljøet mislykkes, kontroller at `python3-venv` er installert.
Hvis en test feiler, lagre hele feilmeldingen og les
[feilsøkingsveiledningen](Feilsøking.md); ikke slett produksjonsdata.

For en reell installasjon fortsetter du med de nummererte kapitlene og leser
først instruksjonene om sikkerhet og sikkerhetskopiering. Hvis LUMS allerede
kjører, bruker du oppgraderingsprosedyren i
[`administration.md`](../../../administration.md), ikke prosedyren for
førstegangsinstallasjon.

---

# 1. Oversikt

LUMS er en sentralisert plattform for Linux-oppdateringsstyring for kontrollert distribusjon av oppdateringer, klientrapportering, pakkehåndtering, kjøring av oppdateringsjobber, validering av resultater og sporbar administrasjon.

Den nåværende arkitekturen skiller administrasjonsserveren fra de administrerte Linux-klientene.

Serveren tilbyr:

* Nettbasert administrasjon
* Klientadministrasjon
* Klientautentisering
* Pakkeinventar
* Rapportering av tilgjengelige oppdateringer
* Pakkesøk
* Installasjon og fjerning av pakker
* Administrasjon av oppdateringsjobber
* Validering av jobbresultater
* Oppdateringshistorikk
* Rollebasert tilgangskontroll
* Revisjonslogging
* SQLite-basert vedvarende tilstand

Linux-klienter tilbyr:

* Systeminformasjon
* Inventar over installerte pakker
* Oppdagelse av tilgjengelige oppdateringer
* Pakkeoperasjoner
* Kjøring av oppdateringsjobber
* Registrering av hviletilstand
* Jobbsjekkpunkter og gjenoppretting
* Registrering av omstartsbehov
* Resultatrapportering

Den nåværende implementasjonen støtter:

```text
Debian / Ubuntu
    └── APT / dpkg

Arch Linux
    └── pacman
```

---

# 2. Arkitektur

Produksjonsarkitekturen er:

```text
                         LUMS Server
                              │
                              │ HTTPS :443
                              ▼
                       ┌──────────────┐
                       │    Nginx     │
                       │  TLS / Proxy │
                       └──────┬───────┘
                              │
                              │ HTTP
                              ▼
                       127.0.0.1:5050
                              │
                              ▼
                    ┌───────────────────┐
                    │   Docker: lums    │
                    │                   │
                    │   Gunicorn        │
                    │   Flask :5000     │
                    │   SQLite          │
                    └─────────┬─────────┘
                              │
                              ▼
                         lums-data
                              │
                              ▼
                   /var/lib/lums/lums.db


        Linux Client
              │
              │ HTTPS + Bearer Token
              ▼
         LUMS API
              │
              ├── Report
              ├── Package Search
              ├── Job Retrieval
              └── Job Result
```

LUMS-applikasjonen er **ikke ment å eksponeres direkte mot nettverket**.

Applikasjonscontaineren er bundet til:

```text
127.0.0.1:5050 → container:5000
```

Nginx er det eksterne HTTPS-inngangspunktet.

Port `5000` publiseres ikke direkte.

Port `5050` må forbli kun tilgjengelig på localhost.

---

# 3. Applikasjonskomponenter

En komplett LUMS-installasjon består av flere komponenter.

## 3.1 LUMS-server

Serveren inneholder:

```text
Flask
Gunicorn
SQLite
Web UI
REST API
Authentication
RBAC
Audit logging
Job management
Package management
```

Applikasjonen kjører i Docker-containeren:

```text
lums
```

Den vedvarende databasen lagres utenfor containerens skrivbare applikasjonsfilsystem:

```text
lums-data:/var/lib/lums/lums.db
```

---

## 3.2 Nginx

Nginx tilbyr:

```text
HTTPS termination
TLS certificate handling
HTTP → HTTPS redirect
Reverse proxy
External network entry point
```

Den tiltenkte forespørselsveien er:

```text
Browser
   │
   │ HTTPS
   ▼
Nginx
   │
   │ localhost HTTP
   ▼
127.0.0.1:5050
   │
   ▼
LUMS
```

Flask/Gunicorn-applikasjonen bør ikke eksponeres direkte mot LAN.

---

## 3.3 Linux-agent

LUMS Agent kjører på hver administrerte Linux-klient.

Den nåværende agentversjonen er:

```text
1.7.0
```

Agenten er ansvarlig for:

```text
System information
Installed packages
Available updates
Client reporting
Job retrieval
Job claiming
Package operations
Result reporting
Reboot detection
```

Agenten kommuniserer med LUMS-serveren via HTTPS og et klientspesifikt Bearer-token.

---

## 3.4 Utføringsovervåker (Watcher)

Utføringsovervåkeren er ansvarlig for kontrollert kjøring av oppdateringsjobber.

Den nåværende Watcher-versjonen er:

```text
1.2.1
```

Watcher håndterer:

```text
Pending-job detection
Idle-state checks
Atomic job claiming
Update execution
Checkpoint handling
Interrupted-job recovery
Result processing
```

Watcher er bevisst adskilt fra vanlig klientrapportering.

---

# 4. Sikkerhetsmodell

Installasjonen må bevare LUMS' sikkerhetsgrunnlinje.

Produksjonsserveren bruker:

```text
HTTPS
Bearer-token client authentication
Role-based web authorization
CSRF protection
Audit logging
Read-only container root filesystem
Dropped Linux capabilities
no-new-privileges
Non-root application user
Localhost-only application port
Persistent Docker volume
Read-only secret mount
```

Docker-containeren kjører som den uprivilegerte brukeren:

```text
lums
```

med UID:

```text
10001
```

Containeren må ikke kjøre i privilegert modus.

Rotfilsystemet må forbli skrivebeskyttet.

Applikasjonen må ikke kreve skrivetilgang til applikasjonskatalogen sin.

Vedvarende applikasjonsdata lagres via det dedikerte Docker-volumet.

---

# 5. Nåværende RBAC-modell

LUMS tilbyr for øyeblikket tre webroller:

```text
administrator
operator
viewer
```

## Administrator

Administratorer kan utføre administrative operasjoner, blant annet:

```text
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
```

---

## Operator

Operatører kan utføre operativ administrasjon:

```text
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
```

Operatører har ikke tilgang til:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

---

## Viewer

Visere har bevisst begrenset tilgang.

En Viewer har tilgang til:

```text
Clients
Installed software
```

Følgende administrasjonsområder er skjult i Viewer-grensesnittet og beskyttet på serversiden:

```text
Available updates
Update Jobs
Update History
Package Management
System Maintenance
```

Skjuling i brukergrensesnittet er derfor ikke sikkerhetsgrensen.

Autorisasjon på serversiden er fortsatt obligatorisk.

---

# 6. Installasjonskrav

## 6.1 LUMS-server

Den nåværende distribusjonen krever en Linux-vert med:

```text
Docker Engine
Git
Nginx
OpenSSL
Network connectivity
Persistent storage
```

Serveren må ha nok lagringsplass til:

```text
Docker images
SQLite database
Application data
Logs
Backups
```

Selve LUMS-applikasjonen kjører i Docker.

---

## 6.2 Linux-klienter

Administrerte Linux-klienter krever:

```text
Python 3
systemd
Supported package manager
Network connectivity to the LUMS server
Valid client token
Trusted TLS certificate
```

Støttede pakkehåndteringsfamilier:

```text
Debian / Ubuntu
    APT / dpkg

Arch Linux
    pacman
```

Klienten må kunne nå LUMS' HTTPS-endepunkt.

---

# 7. Anbefalt katalogstruktur

Den anbefalte plasseringen av repositoriet på serveren er:

```text
/opt/lums-public/
```

Repositoriet inneholder applikasjonskildekoden, agentkildekoden og tester.

En typisk installasjon bruker:

```text
/opt/lums-public/
    ├── agent/
    ├── server/
    ├── tests/
    ├── Dockerfile
    ├── requirements.txt
    └── requirements-dev.txt
```

Konfigurasjon på verten holdes utenfor repositoriet:

```text
/etc/lums/
    ├── secrets/
    │   └── lums_secret
    └── tls/
        ├── lums.crt
        └── lums.key
```

Vedvarende applikasjonsdata lagres i:

```text
lums-data:/var/lib/lums
```

SQLite-databasen er:

```text
/var/lib/lums/lums.db
```

Databasen må aldri lagres inne i Git-arbeidstreet.

Hemmeligheter og privat TLS-materiale må også forbli utenfor repositoriet.

---

# 8. Klargjøring av repositoriet

Klon repositoriet inn i den tiltenkte installasjonskatalogen:

```bash
sudo mkdir -p /opt
cd /opt

sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public
```

Gå inn i repositoriet:

```bash
cd /opt/lums-public
```

Kontroller arbeidstreet:

```bash
git status
```

Inspiser den gjeldende revisjonen:

```bash
git log -1 --oneline --decorate
```

For kontrollerte distribusjoner bør den nøyaktige commit-en som brukes til installasjonen, dokumenteres.

Ikke bygg produksjonsbilder fra et ukjent eller ubekreftet arbeidstre.

---

# 9. Sikkerhetskontroll av repositoriet

Før du bygger produksjonsbildet, kontroller at ingen sensitive filer er plassert i repositoriet.

Gjennomgå arbeidstreet:

```bash
git status --short
```

Gjennomgå ignorerte filer der det er hensiktsmessig:

```bash
git status --ignored --short
```

Repositoriet må ikke inneholde:

```text
Production database files
Private TLS keys
Application secrets
Client tokens
Credential dumps
Backup databases
Runtime logs
Temporary backup files
```

Prosjektet bruker ignoreringsregler i repositoriet for å hindre at vanlige sikkerhetskopiartefakter ved et uhell blir sporet.

Før du committer endringer, inspiser listen over stagede filer nøye.

---

# 10. Klargjør konfigurasjonskataloger på verten

Opprett de nødvendige katalogene på verten:

```bash
sudo install -d -m 700 /etc/lums
sudo install -d -m 700 /etc/lums/secrets
sudo install -d -m 700 /etc/lums/tls
```

Hemmelighetskatalogen inneholder applikasjonshemmeligheten.

TLS-katalogen inneholder TLS-sertifikatet og den private nøkkelen.

Beskyttelse av disse katalogene reduserer risikoen for utilsiktet avsløring.

Verifiser:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums \
    /etc/lums/secrets \
    /etc/lums/tls
```

---

# 11. Opprett applikasjonshemmeligheten

LUMS' applikasjonshemmelighet lagres på verten i stedet for å bygges direkte inn i Docker-bildet.

Stien til produksjonshemmeligheten er:

```text
/etc/lums/secrets/lums_secret
```

Generer en tilfeldig hemmelighet:

```bash
sudo sh -c 'umask 077 && openssl rand -hex 32 > /etc/lums/secrets/lums_secret'
```

Beskytt den resulterende filen:

```bash
sudo chmod 600 \
    /etc/lums/secrets/lums_secret
```

Verifiser tillatelsene uten å vise hemmeligheten:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/secrets/lums_secret
```

Forventet:

```text
600
```

Hemmeligheten må aldri være:

```text
Committed to Git
Printed into logs
Included in the Docker image
Placed into screenshots
Published in issues
Included in documentation
```

Containeren mottar hemmeligheten gjennom en skrivebeskyttet bind-montering.

---

# 12. Klargjør TLS-materiale

LUMS bruker HTTPS for ekstern tilgang.

De anbefalte plasseringene på verten er:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Installer riktig sertifikat og privat nøkkel før du konfigurerer Nginx.

Beskytt den private nøkkelen:

```bash
sudo chmod 600 \
    /etc/lums/tls/lums.key
```

Sertifikatet kan være lesbart for Nginx-tjenesten:

```bash
sudo chmod 644 \
    /etc/lums/tls/lums.crt
```

Verifiser:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Den private nøkkelen må aldri committes til Git eller inkluderes i Docker-bildet.

---

# 13. Installasjonsprinsipp

Installasjonen bør gjennomføres i kontrollerte trinn:

```text
Repository
    ↓
Host configuration
    ↓
Application secret
    ↓
TLS material
    ↓
Docker image
    ↓
Persistent volume
    ↓
Hardened container
    ↓
Nginx / HTTPS
    ↓
Administrator
    ↓
Server validation
    ↓
Linux clients
```

Ikke koble til produksjonsklienter før serveren har bestått sine egne valideringskontroller.

De følgende kapitlene fortsetter med bygging av Docker-bildet og den herdede produksjonsdistribusjonen.

# 14. Bygg LUMS Docker-bildet

Før du bygger produksjonsbildet, sørg for at repositoriet er i ønsket tilstand.

Gå inn i repositoriet:

```bash
cd /opt/lums-public
```

Kjør testsuiten før du lager et produksjonsbilde:

```bash
./.venv-test/bin/pytest -q
```

Antall tester forventes å vokse etter hvert som prosjektet utvikler seg.

Det viktige kravet er at den relevante testsuiten fullføres uten feil før distribusjon.

Bygg Docker-bildet:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Verifiser at bildet finnes:

```bash
sudo docker image ls lums
```

Inspiser bildet:

```bash
sudo docker image inspect lums:latest
```

Produksjonsbildet er basert på et festet (pinned) Python 3.13 slim-basisbilde.

Dockerfile bruker også festede produksjonsavhengigheter der det er nødvendig.

---

# 15. Gjennomgå Docker-byggingen

Før du distribuerer bildet, gjennomgå byggeresultatet for uventede feil eller advarsler.

Kontroller det resulterende bildet:

```bash
sudo docker inspect \
    lums:latest
```

Verifiser den konfigurerte applikasjonsbrukeren:

```bash
sudo docker image inspect \
    lums:latest \
    --format '{{.Config.User}}'
```

Applikasjonen er ment å kjøre som:

```text
lums
```

Applikasjonen må ikke kreve root-rettigheter under normal kjøring.

Gjennomgå Dockerfile når byggeprosessen endres:

```bash
sed -n '1,240p' Dockerfile
```

Ikke legg hemmeligheter, sertifikater eller produksjonsdatabaser i Docker-byggekonteksten.

Repositoriet inneholder en `.dockerignore`-fil for å redusere risikoen for at kjøretidsartefakter ved et uhell havner i bildet.

---

# 16. Opprett det vedvarende Docker-volumet

Opprett det vedvarende LUMS-datavolumet:

```bash
sudo docker volume create lums-data
```

Verifiser:

```bash
sudo docker volume inspect lums-data
```

Volumet lagrer vedvarende applikasjonsdata:

```text
lums-data
    ↓
/var/lib/lums
    ↓
/var/lib/lums/lums.db
```

Containerens eget filsystem må ikke behandles som vedvarende applikasjonslagring.

Databasen overlever derfor utskifting av containeren så lenge `lums-data`-volumet bevares.

> [!IMPORTANT]
> Fjern aldri `lums-data` under en vanlig applikasjonsoppgradering.

Fjerning av volumet fjerner SQLite-databasen som ligger i det.

---

# 17. Verifiser det vedvarende volumet

Før du starter LUMS, bekreft at volumet finnes:

```bash
sudo docker volume inspect \
    lums-data
```

Volumet kan også kontrolleres via Docker:

```bash
sudo docker volume ls | grep lums-data
```

Et nyopprettet volum inneholder normalt ingen database ennå.

Databasen initialiseres av LUMS-applikasjonen under distribusjonen.

---

# 18. Konfigurasjon av produksjonscontaineren

Produksjonscontaineren bruker flere sikkerhetskontroller samtidig.

Den forventede kjøretidsgrunnlinjen er:

```text
Non-root user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges
No privileged mode
Localhost-only application binding
Read-only application-secret mount
Persistent writable data volume
Dedicated /tmp tmpfs
```

Applikasjonsporten publiseres bare til localhost:

```text
127.0.0.1:5050 → container:5000
```

Det eksterne HTTPS-endepunktet leveres av Nginx.

---

# 19. Start den herdede LUMS-containeren

Før du starter en ny produksjonscontainer, sørg for at ingen annen container med navnet `lums` allerede kjører:

```bash
sudo docker ps \
    --filter name=lums
```

Hvis en eksisterende distribusjon skal erstattes, bevar den eksisterende containeren til det nye bildet er validert.

Start den herdede containeren:

```bash
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
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    lums:latest
```

Applikasjonshemmeligheten monteres skrivebeskyttet.

SQLite-databasen lagres i det vedvarende volumet.

Rotfilsystemet er skrivebeskyttet.

Alle Linux-capabilities er fjernet.

Sikkerhetsvalget `no-new-privileges` hindrer prosesser i containeren i å oppnå ekstra rettigheter.

---

# 20. Verifiser containerens tilstand

Kontroller den kjørende containeren:

```bash
sudo docker ps \
    --filter name=lums
```

Forventet tilstand:

```text
Up ...
```

Kontroller containerens tilstand direkte:

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Forventet:

```text
running
```

Inspiser nylige logger:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Oppstartsfeil i applikasjonen må løses før du fortsetter med installasjonen.

---

# 21. Verifiser containersikkerheten

Inspiser den effektive sikkerhetskonfigurasjonen ved kjøring:

```bash
sudo docker inspect lums \
    --format='User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}'
```

Den forventede grunnlinjen er:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Den nøyaktige formateringen av Docker-utdataene kan variere.

Det er den effektive konfigurasjonen som teller.

---

# 22. Verifiser applikasjonsporten

Kontroller den publiserte Docker-porten:

```bash
sudo docker port lums
```

Forventet:

```text
5000/tcp -> 127.0.0.1:5050
```

Følgende er **ikke** akseptabelt for produksjonsapplikasjonen:

```text
0.0.0.0:5050
```

eller:

```text
0.0.0.0:5000
```

Applikasjonen er bevisst bare tilgjengelig via den lokale omvendte proxy-banen.

Kontroller lyttende sockets:

```bash
sudo ss -lntp | grep -E ':5050|:5000'
```

Bare localhost-bindingen for applikasjonen skal være til stede.

---

# 23. Verifiser hemmelighetsmonteringen

Bekreft at hemmeligheten er montert:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Source "->" .Destination "RW=" .RW}}{{end}}'
```

Applikasjonshemmeligheten skal se omtrent slik ut:

```text
/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
```

De nøyaktige utdataene kan inneholde ytterligere informasjon om monteringen.

Den viktige egenskapen er:

```text
RW=false
```

Skriv aldri ut innholdet i hemmeligheten.

En direkte lesbarhetstest er tilstrekkelig:

```bash
sudo docker exec lums \
    sh -c 'test -r /run/secrets/lums_secret && echo "secret mount: OK"'
```

Forventet:

```text
secret mount: OK
```

---

# 24. Verifiser monteringen av det vedvarende volumet

Inspiser containerens monteringer:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Type .Source "->" .Destination "RW=" .RW}}{{end}}'
```

LUMS-datavolumet må være montert på:

```text
/var/lib/lums
```

og må være skrivbart:

```text
RW=true
```

Det forventede forholdet er:

```text
lums-data
    ↓
/var/lib/lums
```

Rotfilsystemet forblir skrivebeskyttet, mens det dedikerte datavolumet gir den nødvendige vedvarende skrivetilgangen.

---

# 25. Verifiser det skrivebeskyttede rotfilsystemet

Applikasjonens rotfilsystem må være skrivebeskyttet.

Container-kjøretiden skal rapportere:

```text
ReadonlyRootfs=true
```

En kontrollert skrivetest kan utføres inne i containeren.

For eksempel:

```bash
sudo docker exec lums \
    sh -c 'touch /app/.write-test'
```

Kommandoen skal feile fordi `/app` er en del av containerens skrivebeskyttede filsystem.

Ikke deaktiver det skrivebeskyttede rotfilsystemet bare fordi en applikasjonskomponent forsøker å skrive utenfor sine angitte skrivbare plasseringer.

Hvis applikasjonen trenger vedvarende data, bruk det aktuelle volumet eller kjøretidsfilsystemet i stedet.

---

# 26. Verifiser det skrivbare midlertidige filsystemet

Containeren har et dedikert `/tmp`-tmpfs.

Verifiser:

```bash
sudo docker exec lums \
    sh -c 'touch /tmp/lums-write-test && rm -f /tmp/lums-write-test && echo "tmpfs: OK"'
```

Forventet:

```text
tmpfs: OK
```

Det midlertidige filsystemet er konfigurert med:

```text
noexec
nosuid
```

og en størrelsesgrense.

Dette gir midlertidig skrivbar lagring uten at containerens rotfilsystem blir skrivbart.

---

# 27. Verifiser applikasjonens datakatalog

LUMS-applikasjonen krever skrivetilgang til sin vedvarende datakatalog.

Test:

```bash
sudo docker exec lums \
    sh -c 'touch /var/lib/lums/.write-test && rm -f /var/lib/lums/.write-test && echo "data volume: OK"'
```

Forventet:

```text
data volume: OK
```

Dette bekrefter at det dedikerte skrivbare volumet er tilgjengelig mens resten av containeren forblir skrivebeskyttet.

---

# 28. Verifiser applikasjonsbrukeren

Bekreft den effektive kjøretidsbrukeren:

```bash
sudo docker exec lums \
    id
```

Prosessen skal kjøre som den uprivilegerte LUMS-brukeren.

Forventet identitet inneholder:

```text
uid=10001(lums)
```

Den nøyaktige gruppeinformasjonen kan variere avhengig av bildets konfigurasjon.

Containeren må ikke kjøre som:

```text
root
```

under normal drift.

---

# 29. Databaseinitialisering

Etter at containeren har startet, kontroller om databasen finnes:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

Hvis applikasjonen er initialisert, skal databasen være til stede.

Databasen ligger i:

```text
/var/lib/lums/lums.db
```

inne i containeren og er fysisk vedvarende gjennom:

```text
lums-data
```

Databasen må ikke kopieres til:

```text
/opt/lums-public
```

eller committes til Git.

---

# 30. Verifiser SQLite-kjøretidskonfigurasjonen

Den nåværende LUMS-produksjonsgrunnlinjen bruker:

```text
journal_mode = wal
busy_timeout = 5000 ms
synchronous = 2
foreign_keys = ON
```

Applikasjonen aktiverer eksplisitt håndheving av fremmednøkler for databasetilkoblinger.

Databasen bruker WAL-modus i normal produksjonsdrift.

Kjøretidskonfigurasjonen kan inspiseres fra applikasjonsdatabasen.

For eksempel:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for pragma in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    print(f"{pragma}={db.execute(f'PRAGMA {pragma}').fetchone()[0]}")

db.close()
PY
```

Forventede verdier tilsvarer:

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

Applikasjonen aktiverer fremmednøkler eksplisitt.

---

# 31. Verifiser databaseintegriteten

Kjør en SQLite-integritetskontroll:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
result = db.execute("PRAGMA integrity_check").fetchone()[0]
print(result)
db.close()
PY
```

Forventet:

```text
ok
```

Ikke fortsett med distribusjonen hvis integritetskontrollen melder om databaseskade.

---

# 32. Verifiser databasemigreringer

LUMS bruker applikasjonsmigreringer for endringer i databaseskjemaet.

Inspiser de migreringsrelaterte filene:

```bash
ls -lh \
    server/*migration*.py
```

Applikasjonen utfører nødvendige migreringer under oppstart/distribusjon i henhold til den gjeldende implementasjonen.

Etter oppstart, inspiser applikasjonsloggene:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Migreringsfeil må undersøkes før du oppretter brukere eller kobler til klienter.

Ikke endre produksjons-SQLite-skjemaet manuelt med mindre prosjektdokumentasjonen uttrykkelig krever det.

Vertsoppdateringsprogrammet støtter for øyeblikket bare kontroller av repositoriet og distribusjonen.
Det oppdaterer ikke utsjekkingen, bygger ikke et bilde, tar ikke sikkerhetskopi av
produksjonsdatabasen, bytter ikke ut containeren og utfører ikke automatisk
tilbakerulling. Utskifting i produksjon er bevisst deaktivert inntil sikkerhetskopiering,
migreringssikkerhet og gjenoppretting er testet mot den faktiske distribusjonskonfigurasjonen.

Kontroller om utsjekkingen samsvarer med `origin/main`:

```bash
bash scripts/update-lums.sh --check-repository
```

For den gjeldende oppførselen og begrensningene ved distribusjonsvalidering, se
[administration.md](../../../administration.md#91-docker-image-maintenance).

---

# 33. Lokal applikasjonsvalidering

Før du konfigurerer Nginx, bekreft at applikasjonen svarer lokalt.

Docker-applikasjonen er bundet til:

```text
127.0.0.1:5050
```

En lokal forespørsel kan testes med:

```bash
curl -I \
    http://127.0.0.1:5050/
```

Det nøyaktige HTTP-svaret avhenger av den gjeldende applikasjonsruten og autentiseringstilstanden.

Det viktige kravet er at forespørselen når den kjørende LUMS-applikasjonen.

Hvis tilkoblingen mislykkes, inspiser:

```bash
sudo docker ps \
    --filter name=lums
```

og:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Ikke eksponer port `5050` eksternt som en omvei ved feilsøking.

---

# 34. Første serversjekkpunkt

På dette stadiet skal serveren oppfylle:

```text
[ ] Repository cloned
[ ] Working tree reviewed
[ ] Production tests completed
[ ] Docker image built
[ ] Persistent lums-data volume exists
[ ] Hardened container running
[ ] Container runs as lums
[ ] Root filesystem is read-only
[ ] All capabilities are dropped
[ ] no-new-privileges is enabled
[ ] Privileged mode is disabled
[ ] Secret is mounted read-only
[ ] Persistent data volume is mounted
[ ] Port 5050 is localhost-only
[ ] SQLite database exists
[ ] SQLite integrity check succeeds
[ ] Foreign keys are enabled
[ ] Local application endpoint responds
```

Ikke koble til produksjonsklienter ennå.

Neste trinn konfigurerer Nginx, HTTPS og det eksterne LUMS-endepunktet.

# 35. Konfigurer Nginx

Nginx er det eksterne HTTPS-inngangspunktet for LUMS.

Selve applikasjonen forblir bundet til:

```text
127.0.0.1:5050
```

Den tiltenkte forespørselsveien er:

```text
Client
   │
   │ HTTPS
   ▼
Nginx :443
   │
   │ HTTP localhost
   ▼
127.0.0.1:5050
   │
   ▼
LUMS container :5000
```

Opprett Nginx-sitekonfigurasjonen:

```bash
sudo tee /etc/nginx/sites-available/lums > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;

    server_name LUMS-SERVER;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name LUMS-SERVER;

    ssl_certificate     /etc/lums/tls/lums.crt;
    ssl_certificate_key /etc/lums/tls/lums.key;

    location / {
        proxy_pass http://127.0.0.1:5050;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

Erstatt:

```text
LUMS-SERVER
```

med vertsnavnet eller adressen som brukes i installasjonen.

Ikke bruk den bokstavelige plassholderen i en produksjonskonfigurasjon.

---

# 36. Aktiver LUMS' Nginx-konfigurasjon

Opprett lenken til det aktiverte nettstedet:

```bash
sudo ln -s \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

Hvis standard Nginx-nettstedet ikke er nødvendig, fjern det:

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/default
```

Ikke fjern andre Nginx-konfigurasjoner som tilhører urelaterte applikasjoner.

---

# 37. Valider Nginx-konfigurasjonen

Test alltid konfigurasjonen før du laster Nginx på nytt:

```bash
sudo nginx -t
```

Forventet:

```text
syntax is ok
test is successful
```

Først etter en vellykket konfigurasjonstest skal Nginx lastes på nytt:

```bash
sudo systemctl reload nginx
```

Verifiser tjenesten:

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

Nginx må kjøre før du fortsetter med HTTPS-valideringen.

---

# 38. Verifiser TLS-sertifikatfilene

Bekreft at de konfigurerte sertifikatfilene finnes:

```bash
sudo ls -lh \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Verifiser tillatelsene:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Den private nøkkelen skal normalt ha:

```text
600
```

Sertifikatet kan normalt ha:

```text
644
```

Skriv aldri ut innholdet i den private nøkkelen.

---

# 39. Verifiser HTTPS-endepunktet

Test HTTPS lokalt:

```bash
curl -I \
    https://LUMS-SERVER/
```

Erstatt `LUMS-SERVER` med vertsnavnet som dekkes av serverens TLS-sertifikat.
Ikke bruk `-k` ved rutinemessig verifisering; det hopper over sertifikatvalidering.

Når sertifikatet er klarert av systemet, bruk sertifikatverifisering:

```bash
curl -I \
    https://LUMS-SERVER/
```

Et vellykket svar bekrefter at forespørselen når Nginx' HTTPS-endepunkt.

Den nøyaktige HTTP-statusen avhenger av den forespurte ruten og autentiseringstilstanden.

Det viktige kravet er at TLS-tilkoblingen lykkes og at forespørselen når LUMS.

---

# 40. Verifiser omdirigering fra HTTP til HTTPS

HTTP-lytteren må omdirigere klienter til HTTPS.

Test:

```bash
curl -I \
    http://LUMS-SERVER/
```

Forventet oppførsel:

```text
HTTP/1.1 301 ...
Location: https://...
```

LUMS-applikasjonen bør ikke brukes over en ukryptert HTTP-tilkobling.

Ikke konfigurer klienter permanent med deaktivert sertifikatverifisering bare fordi det første sertifikatet ikke er klarert.

Rett heller opp klareringskonfigurasjonen.

---

# 41. Verifiser den eksterne nettverksbanen

Inspiser lyttende sockets:

```bash
sudo ss -lntp | grep -E ':80|:443|:5050|:5000'
```

Den tiltenkte arkitekturen er:

```text
80
 │
 └── HTTP redirect
        │
        ▼
443
 │
 └── Nginx
        │
        ▼
127.0.0.1:5050
        │
        ▼
Docker :5000
```

Port `5050` må ikke eksponeres mot LAN.

Port `5000` må ikke eksponeres direkte.

Docker-applikasjonsporten er et internt endepunkt for den omvendte proxyen.

---

# 42. Verifiser sikkerhetshoder

Inspiser HTTPS-svarhodene:

```bash
curl -I \
    https://LUMS-SERVER/
```

Gjennomgå de returnerte hodene i stedet for å anta at sikkerhetskonfigurasjonen er aktiv.

Relevante sikkerhetshoder kan omfatte:

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Content-Security-Policy
```

De nøyaktige hodene avhenger av den gjeldende LUMS-applikasjonen og Nginx-konfigurasjonen.

Hvis et påkrevd hode mangler, inspiser den effektive Nginx-konfigurasjonen:

```bash
sudo nginx -T
```

og applikasjonskonfigurasjonen:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Ikke legg til sikkerhetshoder blindt uten å sjekke hvilket lag som allerede er ansvarlig for dem.

---

# 43. Verifiser vertshåndtering

Produksjonsdistribusjonen skal ikke eksponere applikasjonen via et utilsiktet standard Nginx-nettsted.

Gjennomgå den aktive konfigurasjonen:

```bash
sudo nginx -T
```

Kontroller de aktiverte nettstedene:

```bash
ls -la \
    /etc/nginx/sites-enabled/
```

Den tiltenkte LUMS-virtuelle verten skal være til stede.

Standardnettstedet skal ikke uventet servere LUMS-applikasjonen.

Når en IP-adresse brukes som LUMS-endepunkt, sørg for at den konfigurerte `server_name` og sertifikatet samsvarer med den faktiske distribusjonsmodellen.

---

# 44. Verifiser Docker-eksponeringen på nytt

Etter at Nginx er konfigurert, bekreft at applikasjonen fortsatt kun er tilgjengelig på localhost:

```bash
sudo docker port lums
```

Forventet:

```text
5000/tcp -> 127.0.0.1:5050
```

Den omvendte proxyen krever ingen endring av Docker-bindingen.

Ikke endre den til:

```text
0.0.0.0:5050
```

bare fordi Nginx lytter på nettverket.

Nginx og Docker har bevisst adskilte eksponeringsgrenser.

---

# 45. Opprett den første administratoren

Den første administratoren må opprettes med initialiseringsmekanismen for administratorer i det gjeldende repositoriet.

Før du kjører en initialiseringskommando, inspiser den tilgjengelige implementasjonen i repositoriet:

```bash
cd /opt/lums-public
```

Gjennomgå de sikkerhetsrelaterte initialiseringsfilene:

```bash
find server \
    -maxdepth 1 \
    -type f \
    -iname '*security*' \
    -o -iname '*migration*'
```

Inspiser deretter den gjeldende migrerings-/initialiseringsimplementasjonen før du kjører den.

For eksempel:

```bash
sed -n '1,260p' \
    server/security_migration.py
```

Bruk initialiseringsprosedyren som følger med den nøyaktige repositoriorevisjonen som distribueres.

> [!IMPORTANT]
> Ikke kopier et administratorpassord inn i skallhistorikk eller dokumentasjon.

Den første administratoren må få:

```text
role = administrator
```

Administratorkontoen kreves for den første webinnloggingen og den videre klientadministrasjonen.

---

# 46. Verifiser administratorkontoen

Etter initialisering av administratoren, verifiser kontoen uten å eksponere autentiseringsmateriale.

En databaseinspeksjon kan utføres fra containeren:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

rows = db.execute(
    """
    SELECT id, username, enabled, role
    FROM users
    ORDER BY id
    """
).fetchall()

for row in rows:
    print(row)

db.close()
PY
```

Forventede egenskaper for administratoren er blant annet:

```text
enabled = 1
role = administrator
```

Ikke skriv ut:

```text
password hashes
session data
client tokens
application secrets
```

---

# 47. Administratorpassord

Bruk et unikt administratorpassord.

Passordet bør ikke gjenbrukes fra:

```text
other servers
Linux accounts
GitHub accounts
email accounts
network devices
other LUMS installations
```

LUMS-applikasjonen lagrer passord ved hjelp av den konfigurerte mekanismen for passordhashing.

Ikke forsøk å erstatte applikasjonens passordhash manuelt i SQLite.

Hvis administratorpassordet må endres, bruk den støttede applikasjonsmekanismen.

---

# 48. Første webinnlogging

Åpne LUMS' HTTPS-endepunkt:

```text
https://LUMS-SERVER/
```

Logg inn med administratorkontoen.

Etter autentisering skal administratoren ha tilgang til administrasjonsgrensesnittet.

Administratorgrensesnittet skal gi tilgang til områdene som den gjeldende RBAC-implementasjonen tillater.

Som et minimum skal administratoren ha tilgang til:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management
```

---

# 49. Verifiser administrator-RBAC

Etter innlogging, verifiser at de administrative funksjonene er tilgjengelige.

Administratoren skal ha tilgang til brukeradministrasjon.

Administratoren skal også kunne utføre klientadministrasjonsoperasjoner som den gjeldende implementasjonen tillater.

Autorisasjon på serversiden er fortsatt sikkerhetsgrensen.

Nettlesergrensesnittet er ikke pålitelig bare fordi et element er synlig eller skjult.

---

# 50. Opprett en operatør

Etter at administratorkontoen er verifisert, opprett en operatørkonto via LUMS' brukeradministrasjonsgrensesnitt.

Operatørrollen er ment for operativ oppdateringsstyring.

En operatør har tilgang til:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
```

En operatør skal ikke kunne utføre funksjoner som bare er forbeholdt administratorer, for eksempel:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

Verifiser tillatelsene via applikasjonsgrensesnittet og, der det er hensiktsmessig, via autorisasjonsoppførselen i API-et.

---

# 51. Opprett en Viewer

En Viewer-konto kan opprettes når det kreves skrivebeskyttet tilgang.

Viewer-rollen er bevisst begrenset.

En Viewer har tilgang til:

```text
Clients
Installed software
```

Følgende områder skal ikke være tilgjengelige for en Viewer:

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

Disse begrensningene håndheves på serversiden.

Grensesnittet kan i tillegg skjule utilgjengelige funksjoner.

---

# 52. Verifiser Viewer-isolasjon

Logg inn med en Viewer-konto og verifiser det synlige grensesnittet.

Viewer skal ikke få administrasjonskontroller.

Viewer må ikke kunne omgå brukergrensesnittet og kalle beskyttede endepunkter direkte.

En autorisasjonsfeil skal returneres for beskyttede operasjoner.

Det forventede prinsippet er:

```text
UI restriction
     +
server-side authorization
     =
RBAC boundary
```

Stol aldri på JavaScript eller skjulte HTML-elementer som eneste autorisasjonsmekanisme.

---

# 53. Verifiser økt- og CSRF-beskyttelse

Etter den første vellykkede innloggingen, verifiser at applikasjonen bruker sine konfigurerte økt- og CSRF-beskyttelser.

Installasjonen skal ikke deaktivere CSRF-beskyttelse for å få API-forespørsler eller nettleserhandlinger til å fungere.

Hvis en legitim forespørsel feiler med en CSRF-feil, undersøk applikasjonsflyten i stedet for å deaktivere beskyttelsen.

Øktrelatert oppførsel er dokumentert i:

```text
docs/security.md
```

---

# 54. Verifiser rategrense for innlogging

Den nåværende innloggingsbeskyttelsen bruker vedvarende sporing av mislykkede forsøk.

Den konfigurerte progresjonen er:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

Vellykket autentisering nullstiller den aktuelle feiltilstanden.

Ikke utløs gjentatte mislykkede autentiseringer mot en produksjonsinstallasjon bare for å teste mekanismen.

Bruk den eksisterende testsuiten for gjentatt automatisert validering.

---

# 55. Serverens valideringssjekkpunkt

På dette stadiet, verifiser:

```text
[ ] Nginx is running
[ ] Nginx configuration passes nginx -t
[ ] TLS certificate is installed
[ ] TLS private key is protected
[ ] HTTPS works
[ ] HTTP redirects to HTTPS
[ ] Docker remains localhost-only
[ ] Port 5000 is not externally exposed
[ ] Security headers are present as configured
[ ] Default Nginx site is not unintentionally serving LUMS
[ ] Administrator account exists
[ ] Administrator can log in
[ ] Administrator RBAC works
[ ] Operator role can be created
[ ] Viewer role can be created
[ ] Viewer restrictions are enforced server-side
[ ] CSRF protection remains enabled
[ ] Session protection remains enabled
```

Først når serveren har bestått disse kontrollene, bør Linux-klienter installeres.

Neste kapittel dekker Linux-agenten, klientkonfigurasjon, TLS-klarering og systemd-integrasjon.

# 56. Installasjon av Linux-klient

LUMS-klienter er Linux-systemer som administreres av LUMS-serveren.

En klientinstallasjon består av:

```text
Linux system
    ↓
LUMS Agent
    ↓
Client configuration
    ↓
Client token
    ↓
TLS trust
    ↓
systemd service
    ↓
Reporting timer
```

Kjøring av oppdateringer håndteres separat av utføringsovervåkeren (Watcher).

Den nåværende agentversjonen er:

```text
1.7.0
```

Den nåværende Watcher-versjonen er:

```text
1.2.1
```

---

# 57. Støttede Linux-klienter

De nåværende implementasjonene av pakkehåndtering støtter:

```text
Debian / Ubuntu
    ↓
APT / dpkg

Arch Linux
    ↓
pacman
```

Verifiser operativsystemet før du installerer klienten:

```bash
cat /etc/os-release
```

Verifiser arkitekturen:

```bash
uname -m
```

Verifiser systemd:

```bash
systemctl --version
```

Klienten krever en fungerende systemd-installasjon.

---

# 58. Nettverkskrav for klienten

Klienten må kunne nå LUMS' HTTPS-endepunkt.

Test grunnleggende nettverkstilkobling:

```bash
ping LUMS-SERVER
```

En vellykket ping er ikke påkrevd når ICMP er blokkert.

Det viktige kravet er HTTPS-tilkobling.

Test LUMS-endepunktet:

```bash
curl -I \
    https://LUMS-SERVER/
```

Hvis serveren bruker en privat CA, må klienten stole på denne CA-en før du fortsetter.

Ikke deaktiver TLS-verifisering som en permanent omvei.

---

# 59. Hent LUMS Agent

Agentens kildekode følger med i LUMS-repositoriet.

På klienten, hent repositoriet eller overfør de nødvendige agentfilene på annen måte via den godkjente distribusjonsmetoden.

De relevante filene er:

```text
agent/agent.py
agent/watcher.py
agent/package_manager.py
```

Den anbefalte installasjonskatalogen er:

```text
/opt/lums-agent
```

Opprett den:

```bash
sudo install -d -m 755 \
    /opt/lums-agent
```

---

# 60. Installer agentfilene

Fra LUMS-repositoriet:

```bash
cd /opt/lums-public
```

Installer agenten:

```bash
sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py
```

Installer Watcher:

```bash
sudo cp \
    agent/watcher.py \
    /opt/lums-agent/watcher.py
```

Installer pakkehåndteringsabstraksjonen:

```bash
sudo cp \
    agent/package_manager.py \
    /opt/lums-agent/package_manager.py
```

Verifiser:

```bash
ls -lh \
    /opt/lums-agent/
```

Katalogen skal inneholde de installerte agentkomponentene.

---

# 61. Verifiser agentversjonene

Verifiser den installerte agentversjonen:

```bash
grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/agent.py
```

Den nåværende versjonen er:

```text
1.7.0
```

Verifiser Watcher:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

Den nåværende versjonen er:

```text
1.2.1
```

Hvis de installerte versjonene ikke samsvarer med den tiltenkte distribusjonsrevisjonen, stopp og verifiser at riktig repositoriorevisjon brukes.

---

# 62. Installer systemd-tjenestefiler

Agenten og Watcher bruker separate systemd-tjenester.

Installer agenttjenesten:

```bash
sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
```

Installer Watcher-tjenesten:

```bash
sudo cp \
    agent/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent-watcher.service
```

Installer rapporteringstimeren:

```bash
sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer
```

Installer Watcher-timeren:

```bash
sudo cp \
    agent/lums-agent-watcher.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Last systemd på nytt:

```bash
sudo systemctl daemon-reload
```

---

# 63. Verifiser systemd-enhetene

Inspiser agenttjenesten:

```bash
systemctl cat \
    lums-agent.service
```

Inspiser Watcher-tjenesten:

```bash
systemctl cat \
    lums-agent-watcher.service
```

Inspiser agenttimeren:

```bash
systemctl cat \
    lums-agent.timer
```

Inspiser Watcher-timeren:

```bash
systemctl cat \
    lums-agent-watcher.timer
```

Enhetene skal referere til de installerte filene under:

```text
/opt/lums-agent/
```

Ikke aktiver timerne før klientkonfigurasjonen og autentiseringen er fullført.

---

# 64. Opprett klientkonfigurasjonen

Klientkonfigurasjonen lagres utenfor Git-repositoriet.

Bruk:

```text
/etc/default/lums-agent
```

Opprett filen:

```bash
sudo install -m 600 /dev/null \
    /etc/default/lums-agent
```

Konfigurasjonen inneholder LUMS-serverens endepunkt og klienttokenet.

Eksempelstruktur:

```text
LUMS_BASE=https://LUMS-SERVER
LUMS_TOKEN=<CLIENT-TOKEN>
```

Erstatt:

```text
LUMS-SERVER
```

med det faktiske LUMS-serverendepunktet.

Erstatt:

```text
<CLIENT-TOKEN>
```

med tokenet som er tildelt denne klienten.

Beskytt konfigurasjonen:

```bash
sudo chmod 600 \
    /etc/default/lums-agent
```

Verifiser uten å vise innholdet:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Forventet:

```text
600
```

---

# 65. Klienttokener

Hver LUMS-klient har sitt eget autentiseringstoken.

Tokenet brukes som:

```text
Authorization: Bearer <CLIENT-TOKEN>
```

Serveren trenger ikke den opprinnelige tokenverdien etter klargjøringen.

Serveren lagrer en kryptografisk representasjon av tokenet for validering.

Dette betyr at klientlegitimasjon bør behandles som passord.

Legg aldri et ekte token inn i:

```text
Git
documentation
screenshots
issue reports
shell history
public configuration
```

---

# 66. Klargjør klienttokenet

Opprett eller klargjør klienten fra LUMS' administratorgrensesnitt i henhold til den gjeldende arbeidsflyten for klientadministrasjon.

Det resulterende klienttokenet må overføres til den tiltenkte klienten via en sikker kanal.

Lagre det bare i:

```text
/etc/default/lums-agent
```

på klienten.

Ikke gjenbruk ett klienttoken på flere maskiner.

Det tiltenkte forholdet er:

```text
Client A
    ↓
Token A

Client B
    ↓
Token B

Client C
    ↓
Token C
```

Et kompromittert token skal derfor bare identifisere den tilhørende klienten.

---

# 67. Rotasjon av klienttoken

Klienttokener kan roteres av en administrator.

Rotasjonsforløpet er:

```text
Current token
     ↓
Administrator rotates token
     ↓
Old token invalidated
     ↓
New token issued
     ↓
Client configuration updated
```

Etter at klientkonfigurasjonen er oppdatert, kjør agenten manuelt for å verifisere at autentiseringen lykkes.

Et rotert token skal ikke fortsette å bli akseptert på ubestemt tid.

---

# 68. TLS-klarering

LUMS Agent kommuniserer med serveren over HTTPS.

Sertifikatverifisering må forbli aktivert.

For et offentlig klarert sertifikat er operativsystemets vanlige klareringslager tilstrekkelig.

For en privat laboratorie-CA, installer CA-sertifikatet på klienten.

Ikke løs sertifikatproblemer ved å deaktivere verifisering.

Den riktige løsningen er å få klienten til å stole på den tiltenkte sertifiseringsinstansen.

---

# 69. TLS-klarering på Debian / Ubuntu

På Debian-baserte systemer kan en privat CA installeres i systemets klareringslager.

Kopier CA-sertifikatet:

```bash
sudo cp \
    lums-ca.crt \
    /usr/local/share/ca-certificates/lums-ca.crt
```

Oppdater klareringslageret:

```bash
sudo update-ca-certificates
```

Verifiser at sertifikatet blir akseptert:

```bash
curl -I \
    https://LUMS-SERVER/
```

Hvis kommandoen lykkes uten `-k`, fungerer systemets klareringskonfigurasjon.

---

# 70. TLS-klarering på Arch Linux

På Arch Linux installerer du den private CA-en via systemets konfigurerte mekanisme for klareringslager.

Etter at CA-en er installert, oppdater klareringsdatabasen i henhold til den aktive konfigurasjonen av klareringslageret.

Verifiser:

```bash
curl -I \
    https://LUMS-SERVER/
```

Tilkoblingen skal lykkes uten:

```text
-k
```

Ikke konfigurer agenten permanent til å ignorere sertifikatverifisering.

---

# 71. Verifiser pakkehåndtereren

Agenten oppdager den støttede pakkehåndteringsfamilien.

For Debian/Ubuntu:

```bash
command -v apt
```

og:

```bash
command -v dpkg-query
```

Verifiser installerte pakker:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    | head
```

Verifiser tilgjengelige oppdateringer:

```bash
apt list --upgradable
```

For Arch Linux:

```bash
command -v pacman
```

Verifiser installerte pakker:

```bash
pacman -Q | head
```

Verifiser tilgjengelige oppdateringer:

```bash
pacman -Qu
```

Pakkehåndteringsabstraksjonen bruker automatisk riktig implementasjon.

---

# 72. Verifiser agenttillatelser

Inspiser installasjonskatalogen:

```bash
ls -ld \
    /opt/lums-agent
```

Inspiser de installerte filene:

```bash
ls -lh \
    /opt/lums-agent/
```

Agenten trenger ikke skrivetilgang til sin egen kildekatalog.

Klientkonfigurasjonen forblir beskyttet separat:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Forventet:

```text
600
```

Agenten krever tilstrekkelige systemrettigheter for å inspisere pakketilstand og utføre pakkeoperasjoner.

De nøyaktige kjøretidsrettighetene er definert av den installerte systemd-tjenesten.

---

# 73. Verifiser agentkonfigurasjonen

Før du starter tjenesten, verifiser at konfigurasjonsfilen finnes:

```bash
sudo test -r \
    /etc/default/lums-agent \
    && echo "agent configuration: OK"
```

Ikke skriv ut innholdet i konfigurasjonsfilen.

Verifiser at de nødvendige variablene finnes uten å eksponere tokenet:

```bash
sudo sh -c '
set -a
. /etc/default/lums-agent
set +a

test -n "$LUMS_BASE" &&
echo "LUMS_BASE: configured"

test -n "$LUMS_TOKEN" &&
echo "LUMS_TOKEN: configured"
'
```

Selve tokenverdien må ikke skrives ut.

---

# 74. Test agenten manuelt

Før du aktiverer timeren, kjør agenten én gang manuelt:

```bash
sudo systemctl start \
    lums-agent.service
```

Kontroller resultatet:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Agenten er en engangstjeneste (one-shot).

Etter vellykket fullføring kan den vise:

```text
Active: inactive (dead)
```

Dette er normalt.

Det viktige resultatet er:

```text
status=0/SUCCESS
```

Inspiser journalen:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 75. Verifiser den første klientrapporten

En vellykket agentkjøring skal rapportere klienten til LUMS-serveren.

Hele banen er:

```text
Agent
   ↓
HTTPS
   ↓
Nginx
   ↓
LUMS API
   ↓
Bearer authentication
   ↓
Client lookup
   ↓
Report accepted
```

Inspiser serverloggene ved behov:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Klienten skal vises i LUMS' webgrensesnitt etter en vellykket rapport.

At den lokale tjenesten lykkes er ikke tilstrekkelig i seg selv.

Serveren må godta rapporten.

---

# 76. Verifiser klienten i webgrensesnittet

Logg inn som administrator eller operatør.

Åpne klientoversikten.

Den nye klienten skal rapportere informasjon som:

```text
Hostname
IP address
Operating system
Architecture
Agent version
Last report
Installed packages
Available updates
```

Den rapporterte informasjonen tilhører den klienten.

En klient må ikke kunne få tilgang til en annen klients ressurser.

---

# 77. Aktiver rapporteringstimeren

Først etter at den manuelle agentkjøringen er vellykket, skal rapporteringstimeren aktiveres:

```bash
sudo systemctl enable --now \
    lums-agent.timer
```

Kontroller:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Inspiser timeplanen:

```bash
systemctl list-timers \
    lums-agent.timer \
    --no-pager
```

Timeren starter periodisk:

```text
lums-agent.service
```

Selve tjenesten forblir en engangsenhet.

Det er derfor normalt at tjenesten går tilbake til:

```text
inactive (dead)
```

mellom timerkjøringene.

---

# 78. Verifiser planlagt rapportering

Etter at timeren er aktivert, inspiser neste planlagte kjøring:

```bash
systemctl list-timers \
    --all \
    --no-pager | grep lums-agent
```

Etter at timeren har kjørt, inspiser:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Verifiser den tilsvarende klientrapporten i LUMS.

En sunn rapporteringssyklus er:

```text
Timer
  ↓
Agent service
  ↓
System inventory
  ↓
Package inventory
  ↓
Update detection
  ↓
HTTPS report
  ↓
LUMS database
```

---

# 79. Sjekkpunkt for klientinstallasjon

Før du installerer utføringsovervåkeren, verifiser:

```text
[ ] Supported Linux distribution
[ ] Python 3 available
[ ] systemd available
[ ] Package manager available
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher files installed
[ ] Client configuration exists
[ ] Client token protected
[ ] TLS certificate trusted
[ ] Agent service succeeds
[ ] Client report accepted
[ ] Client visible in LUMS
[ ] Reporting timer enabled
[ ] Scheduled reporting verified
```

Ikke gå videre til testing av oppdateringsjobber før rapporteringsbanen fungerer.

Neste kapittel installerer og validerer utføringsovervåkeren.

# 80. Installer utføringsovervåkeren (Watcher)

LUMS' utføringsovervåker er ansvarlig for å oppdage og utføre ventende oppdateringsjobber på klienten.

Arkitekturen skiller rapportering fra utføring:

```text
Reporting
    │
    ▼
lums-agent.service
    │
    └── system inventory / update detection

Execution
    │
    ▼
lums-agent-watcher.service
    │
    └── pending update jobs
```

Denne adskillelsen lar vanlig klientrapportering fortsette uavhengig av kjøringen av oppdateringer.

---

# 81. Verifiser Watcher-installasjonen

Verifiser at Watcher er til stede:

```bash
ls -lh \
    /opt/lums-agent/watcher.py
```

Verifiser den installerte versjonen:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

Den nåværende Watcher-versjonen er:

```text
1.2.1
```

---

# 82. Verifiser Watcher-tjenesten

Inspiser systemd-enheten:

```bash
systemctl cat \
    lums-agent-watcher.service
```

Tjenesten må referere til:

```text
/opt/lums-agent/watcher.py
```

Verifiser at enheten er kjent for systemd:

```bash
systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Tjenesten kan være inaktiv når ingen kjøring er utløst.

Dette er ikke i seg selv en feil.

---

# 83. Verifiser Watcher-timeren

Før du aktiverer Watcher-timeren, verifiser at:

- `/etc/default/lums-agent` finnes og inneholder riktig klientkonfigurasjon.
- LUMS-serverendepunktet og klienttokenet er riktig konfigurert.
- En manuell agentkjøring lyktes og serveren godtok klientrapporten.
- Begge Watcher-enhetsfilene er installert fra repositoriet.

Ikke aktiver timeren mens autentisering eller rapportering feiler.


Inspiser timeren:

```bash
systemctl cat \
    lums-agent-watcher.timer
```

Aktiver timeren først etter at alle forutsetningene ovenfor er verifisert:

```bash
sudo systemctl enable --now \
    lums-agent-watcher.timer
```

Verifiser:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Inspiser neste planlagte kjøring:

```bash
systemctl list-timers \
    lums-agent-watcher.timer \
    --no-pager
```

---

# 84. Forstå hviletilstandsbevisst kjøring

Watcher kan bruke informasjon om klientens hviletilstand (idle) før oppdateringsjobber kjøres.

Den tiltenkte flyten er:

```text
Pending job
    │
    ▼
Watcher
    │
    ▼
Idle detection
    │
    ├── idle state available
    │       │
    │       ▼
    │   idle threshold
    │       │
    │       ▼
    │   execute when allowed
    │
    └── idle state unavailable
            │
            ▼
        use configured
        fallback behavior
```

Registrering av hviletilstand må aldri tolkes som autentisering eller autorisasjon.

Det er utelukkende en mekanisme for planlegging av kjøring.

---

# 85. Verifiser registrering av hviletilstand

Kjør banen for hviletilstandsregistrering manuelt gjennom den installerte Agent-/Watcher-implementasjonen.

Inspiser den resulterende tjenestejournalen:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

Hvis plattformen ikke gir den nødvendige informasjonen om hviletilstand, kan klienten rapportere at registrering av hviletilstand er utilgjengelig.

Dette er ikke automatisk en feil.

Den viktige forskjellen er:

```text
idle_supported = available
```

versus:

```text
idle_supported = unavailable
```

Klienten må ikke antas å være i hviletilstand bare fordi ingen informasjon om hviletilstand ble returnert.

---

# 86. Opprett en kontrollert testoppdateringsjobb

Ikke begynn installasjonstestingen med en stor systemoppdatering.

Bruk en liten, kjent pakke til den første testen.

Pakken bør:

```text
exist in the configured repository
be safe to install
be removable again
not be required by the operating system
```

Eksempel på testpakke:

```text
sl
```

Før du oppretter jobben, verifiser om den allerede er installert:

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

For Arch Linux, bruk en pakke som er tilgjengelig i de konfigurerte repositoriene og egner seg for en reversibel test.

Ikke bruk `sl` blindt på alle distribusjoner.

---

# 87. Verifiser pakkesøk

Bruk LUMS' pakkehåndteringsgrensesnitt (Package Management) til å søke etter den valgte pakken.

Søkeflyten er:

```text
Browser
   ↓
LUMS API
   ↓
Package Search Request
   ↓
Client
   ↓
APT / pacman
   ↓
Package Search Result
   ↓
LUMS API
   ↓
Browser
```

Verifiser at resultatet inneholder den forventede informasjonen:

```text
Package
Version
Description
Status
Action
```

For Arch Linux kan repositorieinformasjon også bli returnert.

---

# 88. Tillatelser for pakkehåndtering

Pakkehåndtering er begrenset av RBAC.

Administrator:

```text
Allowed
```

Operatør:

```text
Allowed
```

Viewer:

```text
Not allowed
```

En Viewer må ikke kunne utføre pakkeinstallasjon eller -fjerning ved å kalle API-et direkte.

At nettlesergrensesnittet skjuler funksjonen er bare en ekstra brukervennlighetsbegrensning.

Autorisasjon på serversiden er den faktiske sikkerhetsgrensen.

---

# 89. Test pakkeinstallasjon

Opprett en installasjonsjobb via LUMS-grensesnittet.

Den logiske operasjonen er:

```text
INSTALL_PACKAGE
```

Jobben lagres i LUMS-databasen før agenten utfører den.

Den forventede flyten er:

```text
Create job
   ↓
PENDING
   ↓
Watcher detects job
   ↓
RUNNING
   ↓
Package manager
   ↓
SUCCESS
```

Overvåk jobben i LUMS-grensesnittet.

Ikke endre databasen manuelt for å tvinge fram en jobbtilstand.

---

# 90. Verifiser installasjonsresultatet

Etter at jobben melder suksess, verifiser pakken lokalt.

På Debian/Ubuntu:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    sl
```

Verifiser at pakkehåndtereren er enig:

```bash
apt-cache policy \
    sl
```

Pakken må faktisk være installert.

En LUMS-tilstand `SUCCESS` må tilsvare en vellykket operasjon på klientsiden.

---

# 91. Verifiser jobbresultatet

Inspiser LUMS' jobbhistorikk.

Verifiser:

```text
Action
Package
Client
Start time
Completion time
Result
```

Resultatet som klienten returnerer, må valideres av serveren.

Ugyldige eller ufullstendige resultatdata må ikke i det stille bli til en vellykket jobb.

Denne valideringen er en del av LUMS' sikkerhets- og pålitelighetsmodell.

---

# 92. Test fjerning av pakke

Etter at installasjonen er verifisert, opprett en fjerningsjobb:

```text
REMOVE_PACKAGE
```

Overvåk:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

Etter fullføring:

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

Pakken skal ikke lenger være installert.

Hvis pakken ikke var installert før testen, må fraværet ikke behandles som bevis på en vellykket fjerningsoperasjon.

---

# 93. Test pakkeoppdatering

Pakkeoppdateringer bruker:

```text
UPDATE_PACKAGE
```

Serveren validerer at den forespurte pakken er en tilgjengelig oppdatering før den oppretter den tilsvarende jobben.

Den generelle flyten er:

```text
Client reports available updates
       ↓
User selects package
       ↓
Server validates package
       ↓
Update job created
       ↓
Watcher executes
       ↓
Result reported
```

Ikke konstruer oppdateringsforespørsler manuelt som omgår den normale valideringsbanen.

---

# 94. Test systemoppdatering

En fullstendig systemoppdatering bruker:

```text
UPDATE_SYSTEM
```

Denne operasjonen påvirker klientens pakkehåndteringstilstand bredere enn en operasjon på én enkelt pakke.

For den første testen av systemoppdatering:

```text
Use a test client
Use a current backup
Monitor the console
Monitor the LUMS job
Do not interrupt the package manager
```

Ikke bruk selve produksjonsserveren som første testmål for systemoppdatering.

---

# 95. Pakkehåndtererlåser

APT og pacman kan bruke pakkehåndtererlåser.

Når en operasjon feiler fordi en annen pakkehåndteringsprosess er aktiv, inspiser de kjørende prosessene før du gjør noe.

Debian/Ubuntu:

```bash
ps aux | grep -E \
    '[a]pt|[d]pkg|[u]nattended'
```

Arch Linux:

```bash
ps aux | grep -E \
    '[p]acman|[p]ar'
```

Ikke slett låsfiler for pakkehåndtereren mens pakkehåndtereren faktisk kjører.

En lås beskytter normalt mot samtidige pakkeoperasjoner.

---

# 96. Skille LUMS-feil fra pakkehåndtererfeil

Når en jobb feiler, avgjør hvilket lag som sviktet.

```text
LUMS API
   │
   ├── Job creation failure
   │
   ▼
LUMS database
   │
   ├── State / persistence problem
   │
   ▼
Watcher
   │
   ├── Execution problem
   │
   ▼
Package manager
   │
   ├── APT / pacman failure
   │
   ▼
Operating system
```

Inspiser klientjournalen:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Inspiser LUMS-containeren:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Ikke prøv en mislykket jobb på nytt umiddelbart uten å finne ut hvorfor den feilet.

---

# 97. Verifiser jobbsjekkpunkter

LUMS sporer tilstanden til jobber og pakkeelementer.

For pakkebaserte jobber kan individuelle pakkeelementer sjekkpunktfestes.

Den tiltenkte oppførselen er:

```text
Package A → SUCCESS
Package B → SUCCESS
Package C → RUNNING
             │
             ▼
          interruption
             │
             ▼
          recovery
             │
             ▼
Package A → not repeated
Package B → not repeated
Package C → resumed / handled
```

Dette forhindrer at fullførte pakkeoperasjoner unødvendig gjentas etter et avbrudd.

---

# 98. Test kontrollert jobbgjenoppretting

Bruk en ikke-kritisk testjobb.

Start jobben og observer tilstanden:

```text
PENDING
```

deretter:

```text
RUNNING
```

Ikke avbryt en produksjonsoppdatering med vilje.

For gjenopprettingstesting, bruk en dedikert testklient og en kontrollert pakkeoperasjon.

Etter et avbrudd eller en simulert feil, start Watcher på nytt:

```bash
sudo systemctl restart \
    lums-agent-watcher.timer
```

Inspiser deretter:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Verifiser at pakkeelementer som allerede er vellykkede, ikke utføres på nytt unødvendig.

---

# 99. Verifiser registrering av omstartsbehov

Enkelte pakkeoperasjoner kan kreve omstart.

Agenten/Watcher rapporterer omstartskrav til LUMS.

Den generelle flyten er:

```text
Package operation
      ↓
Reboot requirement detected
      ↓
Result reported
      ↓
LUMS records reboot state
```

Etter en testoperasjon som legitimt krever omstart, verifiser det tilsvarende jobbresultatet i LUMS-grensesnittet.

Ikke start en produksjonsklient på nytt bare for å teste mekanismen, med mindre systemet er ment for den testen.

---

# 100. Verifiser rapportering etter omstart

Når en testklient startes på nytt, verifiser at:

```text
systemd
   ↓
LUMS Agent timer
   ↓
Agent report
   ↓
LUMS server
```

fortsetter å fungere.

Kontroller:

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

og:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Inspiser deretter den nyeste rapporten i LUMS-grensesnittet.

---

# 101. Verifiser oppdagelse av oppdateringer

Kjør agenten manuelt:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspiser:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Klienten skal rapportere:

```text
Installed packages
Available updates
Agent status
```

Serveren skal oppdatere klientens gjeldende tilstand.

Ikke forveksle:

```text
available updates
```

med:

```text
installed packages
```

De representerer ulike datasett.

---

# 102. Verifiser installert programvare

Åpne klientens seksjon for installert programvare i LUMS.

Pakkelisten skal samsvare med pakkehåndtereren på klientsiden.

For Debian/Ubuntu:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n'
```

For Arch:

```bash
pacman -Q
```

LUMS-inventaret er kun informativt inntil en jobb eksplisitt opprettes.

Filteret for installerte pakker endrer ikke selv klienten.

---

# 103. Verifiser pakkesøk separat

Søket i pakkehåndtering (Package Management) er separat fra filteret for installerte pakker.

Forskjellen er:

```text
Installed Package Filter
    ↓
Searches the package inventory already reported by the client

Package Management Search
    ↓
Requests package information from the client's package manager
```

Ikke behandle de to søkefunksjonene som utbyttbare.

En pakke kan være tilgjengelig via APT eller pacman uten å være installert.

---

# 104. Verifiser Viewer-isolasjon for pakker

Logg inn som Viewer.

Verifiser at pakkehåndteringsgrensesnittet ikke er tilgjengelig.

Verifiser deretter begrensningen på serversiden ved å forsøke en uautorisert pakkehåndteringsforespørsel via en godkjent testmetode.

Forespørselen må avvises.

Viewer-tilgang må forbli skrivebeskyttet.

---

# 105. Verifiser pakkehåndtering for Operator

Logg inn som Operator.

Verifiser tilgang til:

```text
Package Search
Package Installation
Package Removal
Package Updates
Update Jobs
Update History
```

Operatøren må ikke få tilgang til brukeradministrasjonsfunksjoner som er forbeholdt administratorer.

---

# 106. Verifiser pakkehåndtering for administrator

Logg inn som Administrator.

Verifiser de samme pakkehåndteringsfunksjonene som for Operator.

Verifiser i tillegg tilgang til:

```text
User Management
Client Management
Client Token Rotation
```

Administratorrettigheter må forbli håndhevet på serversiden.

---

# 107. Første ende-til-ende-pakketest

Den første komplette testen av pakkehåndtering bør følge denne sekvensen:

```text
1. Client reports successfully
2. Package search succeeds
3. Package result is displayed
4. Administrator/Operator creates INSTALL_PACKAGE job
5. Job becomes PENDING
6. Watcher detects the job
7. Job becomes RUNNING
8. Package manager executes
9. Client reports result
10. Server validates result
11. Job becomes SUCCESS
12. Installed package is verified locally
13. Package is visible in LUMS inventory
```

Først etter at denne sekvensen lykkes, bør bredere oppdateringstesting begynne.

---

# 108. Sjekkpunkt for klientkjøring

Verifiser:

```text
[ ] Watcher installed
[ ] Watcher version verified
[ ] Watcher timer enabled
[ ] Idle detection works or reports unavailable correctly
[ ] Package search works
[ ] Package installation works
[ ] Package removal works
[ ] Package update works
[ ] System update path is available
[ ] Job states transition correctly
[ ] Job results are validated
[ ] Package checkpointing works
[ ] Reboot detection works
[ ] Reporting continues after reboot
[ ] Viewer cannot mutate package state
[ ] Operator can manage packages
[ ] Administrator can manage packages
```

På dette tidspunktet er den sentrale kjøringsbanen for LUMS-klienter installert og validert.

Neste kapittel dekker full ende-til-ende-validering, RBAC-verifisering, sikkerhetskopiering/gjenoppretting, vedlikehold, oppgraderinger og endelige installasjonskontroller.

# 109. Full ende-til-ende-validering

Etter at serveren og minst én Linux-klient er konfigurert, utfør en komplett ende-til-ende-validering.

Den komplette LUMS-banen er:

```text
Browser
   │
   ▼
Nginx / HTTPS
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Client Agent
   │
   ▼
Package Manager
   │
   ▼
Update Result
   │
   ▼
SQLite
   │
   ▼
Web Interface
```

Ikke anse installasjonen som fullført bare fordi webgrensesnittet åpnes.

Alle viktige lag må verifiseres.

---

# 110. Serverhelsekontroll

Verifiser LUMS-containeren:

```bash
sudo docker ps \
    --filter name=lums
```

Verifiser containerens tilstand:

```bash
sudo docker inspect \
    lums \
    --format '{{.State.Status}}'
```

Forventet:

```text
running
```

Inspiser nylige logger:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Loggene skal ikke inneholde en aktiv oppstarts- eller migreringsfeil.

---

# 111. Containersikkerhetskontroll

Verifiser sikkerhetskonfigurasjonen ved kjøring:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Forventet grunnlinje:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Verifiser nettverksbindingen:

```bash
sudo docker port \
    lums
```

Forventet:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 112. Kontroll av vedvarende lagring

Verifiser LUMS-volumet:

```bash
sudo docker volume inspect \
    lums-data
```

Verifiser at applikasjonsdatabasen finnes:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Databasen må ligge i vedvarende lagring.

Ikke lagre produksjonsdatabasen bare i containerens filsystem.

---

# 113. SQLite-helsekontroll

Inspiser den gjeldende SQLite-kjøretidskonfigurasjonen:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for name in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    value = db.execute(
        f"PRAGMA {name}"
    ).fetchone()[0]
    print(f"{name}={value}")

db.close()
PY
```

Den gjeldende grunnlinjen er:

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

Applikasjonen aktiverer håndheving av fremmednøkler eksplisitt.

---

# 114. SQLite-integritetskontroll

Kjør:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

result = db.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

print(result)

db.close()
PY
```

Forventet:

```text
ok
```

Ikke fortsett med en ny produksjonsutrulling hvis integritetskontrollen melder om skade.

---

# 115. Verifiser databasemigreringer

Inspiser migreringstilstanden:

```bash
sudo docker logs \
    --tail 200 \
    lums | grep -i migration
```

Applikasjonen må fullføre sine konfigurerte migreringer før normal drift.

Ikke endre migreringstilstandstabellen manuelt med mindre den gjeldende LUMS-migreringsprosedyren uttrykkelig krever det.

---

# 116. Kjør den automatiserte testsuiten

I LUMS' utviklings-/testmiljø:

```bash
cd /opt/lums-public
```

Kjør:

```bash
./.venv-test/bin/pytest -q
```

Antall tester endrer seg etter hvert som prosjektet utvikler seg; stol på
kommandoens resultat, ikke på et fast antall i dette dokumentet.

Det viktige kravet er:

```text
all tests pass
```

Ikke ignorer feilende tester fordi produksjonswebgrensesnittet ser ut til å fungere.

---

# 117. Verifiser RBAC

Den gjeldende rollemodellen er:

| Funksjon               | Administrator | Operatør | Viewer |
| ---------------------- | ------------: | -------: | -----: |
| Vise klienter          |            Ja |       Ja |     Ja |
| Installert programvare |            Ja |       Ja |     Ja |
| Tilgjengelige oppdateringer |       Ja |       Ja |    Nei |
| Opprette/kjøre jobber  |            Ja |       Ja |    Nei |
| Oppdateringshistorikk  |            Ja |       Ja |    Nei |
| Pakkehåndtering        |            Ja |       Ja |    Nei |
| Systemvedlikehold      |            Ja |       Ja |    Nei |
| Opprette/deaktivere klienter |      Ja |     Nei |    Nei |
| Rotere klienttokener   |            Ja |      Nei |    Nei |
| Brukeradministrasjon   |            Ja |      Nei |    Nei |
| Rolleadministrasjon    |            Ja |      Nei |    Nei |

Grensesnittet skal gjenspeile disse tillatelsene.

Enda viktigere er at API-et må håndheve dem uavhengig.

---

# 118. Verifiser administratortilgang

Logg inn som Administrator.

Verifiser tilgang til:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management
```

Verifiser funksjoner for klientadministrasjon:

```text
Create client
Disable client
Rotate client token
```

Administratoren skal kunne utføre disse operasjonene.

---

# 119. Verifiser operatørtilgang

Logg inn som Operator.

Verifiser tilgang til:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
```

Verifiser at funksjonalitet som er forbeholdt administratorer ikke er tilgjengelig:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

Stol ikke bare på skjulte UI-elementer.

Beskyttede API-operasjoner må avvise uautoriserte forespørsler.

---

# 120. Verifiser Viewer-tilgang

Logg inn som Viewer.

Viewer skal ha tilgang til:

```text
Clients
Installed software
```

Følgende må ikke være tilgjengelig:

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

Viewer må ikke kunne endre klienttilstand.

---

# 121. Verifiser klientautentisering

Bekreft at hver klient bruker sitt eget Bearer-token.

Den forventede modellen er:

```text
Client A → Token A
Client B → Token B
Client C → Token C
```

Ikke del tokener mellom klienter.

Verifiser at et rotert eller tilbakekalt token ikke lenger blir akseptert.

Legg aldri ekte tokener inn i testutdata eller dokumentasjon.

---

# 122. Verifiser oppdagelse av oppdateringer

På en testklient:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspiser:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Verifiser deretter klienten i LUMS-grensesnittet.

Den rapporterte informasjonen skal omfatte gjeldende pakkeinventar og oppdateringsinformasjon der det støttes.

---

# 123. Verifiser opprettelse av oppdateringsjobb

Opprett en kontrollert oppdateringsjobb via LUMS-grensesnittet.

Jobben skal først vises som:

```text
PENDING
```

Watcher behandler deretter jobben:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

eller:

```text
PENDING
   ↓
RUNNING
   ↓
FAILED
```

avhengig av det faktiske operasjonsresultatet.

Ikke endre databasetilstanden manuelt.

---

# 124. Verifiser jobbkjøring

Inspiser klientens Watcher:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Inspiser LUMS-serveren:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Sammenlign jobbtilstanden på serversiden med kjøreresultatet på klientsiden.

De to må stemme overens.

---

# 125. Verifiser validering av pakkeresultater

En jobb må ikke bli vellykket bare fordi klienten sendte inn et syntaktisk gyldig svar.

Serveren validerer det returnerte resultatet.

Verifiser dette via de automatiserte testene for resultatvalidering:

```bash
./.venv-test/bin/pytest -q \
    tests/test_job_result.py
```

Et vellykket resultat må ha den forventede strukturen og gyldig jobbkontekst.

Misformede eller inkonsistente resultater må avvises.

---

# 126. Verifiser jobbgjenoppretting

Bruk en dedikert testklient for gjenopprettingstesting.

Gjenopprettingsmodellen er:

```text
Job
 │
 ├── package item A → SUCCESS
 ├── package item B → SUCCESS
 └── package item C → interrupted
                       │
                       ▼
                    recovery
                       │
                       ▼
                  resume safely
```

Etter gjenoppretting må tidligere vellykkede pakkeelementer ikke gjentas unødvendig.

Inspiser:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Verifiser deretter den endelige jobbtilstanden i LUMS.

---

# 127. Verifiser registrering av omstartsbehov

For en kontrollert testoppdatering som krever omstart, verifiser at klienten rapporterer omstartskravet.

Etter omstart:

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

og:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Klienten må gjenoppta normal rapportering etter oppstart.

---

# 128. Verifiser revisjonslogging

Utfør en kontrollert administrativ handling, og inspiser deretter LUMS' revisjonslogg.

Relevante operasjoner omfatter:

```text
Login
User creation
Client creation
Client-token rotation
Job creation
Package management
```

Revisjonsoppføringer skal gi nok informasjon til å rekonstruere den administrative handlingen uten å eksponere hemmeligheter.

Ikke logg:

```text
Passwords
Client tokens
Application secrets
Private keys
Session secrets
```

---

# 129. Verifiser skjuling av sensitive data i logger

Inspiser nylige logger:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Inspiser klientlogger:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

og:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Autentiseringslegitimasjon og hemmeligheter må ikke vises i normale diagnostiske utdata.

Hvis en diagnostikkommando ville eksponere en hemmelighet, ikke lim utdataene inn i en sak (issue), en commit eller dokumentasjon.

---

# 130. Verifiser nettverkseksponering

Inspiser lyttende porter:

```bash
sudo ss -lntp
```

LUMS-applikasjonsporten skal forbli:

```text
127.0.0.1:5050
```

Nginx leverer den eksterne tjenesten:

```text
:80
:443
```

Applikasjonen må ikke eksponeres direkte via:

```text
0.0.0.0:5050
```

eller:

```text
0.0.0.0:5000
```

---

# 131. Verifiser brannmurkonfigurasjonen

Hvis en vertsbrannmur er aktivert, inspiser den:

```bash
sudo ufw status verbose
```

Distribusjonen skal bare eksponere tjenestene som verten trenger.

Ikke opprett en brannmurregel for port `5050` bare fordi Docker bruker denne porten internt.

Den tiltenkte arkitekturen er:

```text
LAN
 │
 ▼
443
 │
 ▼
Nginx
 │
 ▼
127.0.0.1:5050
 │
 ▼
LUMS
```

---

# 132. Sikkerhetskopistrategi

LUMS' SQLite-database er vedvarende applikasjonstilstand.

Sikkerhetskopier bør som et minimum beskytte:

```text
LUMS database
TLS material
LUMS application secret
Deployment configuration
```

Sikkerhetskopier må lagres utenfor den aktive LUMS-containeren.

Ikke lagre sikkerhetskopier i:

```text
/app
```

og ikke stol på containerens filsystem.

Docker-volumet:

```text
lums-data
```

inneholder vedvarende applikasjonsdata, men et Docker-volum er ikke i seg selv en sikkerhetskopi.

---

# 133. Databasesikkerhetskopi

Før du tar sikkerhetskopi av databasen, identifiser databasefilen:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

En databasesikkerhetskopi bør utføres med en konsistent SQLite-sikkerhetskopimekanisme.

Ikke kopier en levende SQLite-database blindt mens den endres, hvis sikkerhetskopiprosedyren ikke kan garantere konsistens.

Etter at du har opprettet en sikkerhetskopi, verifiser at sikkerhetskopifilen finnes og er beskyttet.

---

# 134. Konfigurasjonssikkerhetskopi

Beskytt følgende distribusjonsmateriale:

```text
/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums
```

Ikke publiser disse filene.

Følgende filer er særlig sensitive:

```text
/etc/lums/secrets/lums_secret
/etc/lums/tls/lums.key
```

Beskytt tillatelsene til sikkerhetskopiene tilsvarende.

---

# 135. Planlegging av gjenoppretting

En gjenoppretting bør testes på et system som ikke er i produksjon, før den trengs ved katastrofegjenoppretting.

Gjenopprettingssekvensen er konseptuelt:

```text
Backup
  ↓
Verify backup integrity
  ↓
Prepare clean LUMS host
  ↓
Restore secret/configuration
  ↓
Restore database
  ↓
Restore TLS material
  ↓
Start LUMS
  ↓
Run integrity checks
  ↓
Validate users/clients/jobs
```

Ikke overskriv en produksjonsdatabase uten først å bevare den eksisterende tilstanden.

---

# 136. Verifiser en databasegjenoppretting

Etter at en database er gjenopprettet, kjør:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

print(
    db.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]
)

db.close()
PY
```

Forventet:

```text
ok
```

Verifiser deretter:

```text
users
clients
update jobs
package data
audit data
```

Ikke anta at en vellykket SQLite-integritetskontroll beviser at hele applikasjonstilstanden er korrekt.

---

# 137. Vedlikeholdsprinsipper

Rutinemessig vedlikehold bør følge:

```text
Observe
   ↓
Back up
   ↓
Change
   ↓
Verify
```

Ikke utfør urelatert vedlikehold under en aktiv oppdateringsjobb.

Før vedlikehold:

```bash
sudo docker ps \
    --filter name=lums
```

Kontroller aktive jobber i LUMS-grensesnittet.

Hvis en oppdatering kjører, la den bli ferdig med mindre vedlikeholdsoperasjonen uttrykkelig krever avbrudd.

---

# 138. Containervedlikehold

Inspiser det kjørende bildet:

```bash
sudo docker inspect \
    lums \
    --format '{{.Config.Image}}'
```

Inspiser containeren:

```bash
sudo docker ps \
    --filter name=lums
```

Inspiser nylige logger:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Ikke fjern det vedvarende volumet under vanlig containervedlikehold.

Volumet inneholder applikasjonstilstand.

---

# 139. Bildevedlikehold

Før du erstatter produksjonsbildet:

```bash
cd /opt/lums-public
```

Kjør de automatiserte testene:

```bash
./.venv-test/bin/pytest -q
```

Bygg det nye bildet:

```bash
sudo docker build \
    -t lums:new \
    .
```

Ikke erstatt den kjørende containeren før bildet har bestått den nødvendige valideringen.

Behold den nåværende fungerende containeren tilgjengelig til erstatningen er verifisert.

---

# 140. Kontrollert utskifting av container

Når produksjonscontaineren skal erstattes:

```text
Current container
       │
       ▼
Backup / checkpoint
       │
       ▼
Build new image
       │
       ▼
Validate image
       │
       ▼
Stop old container
       │
       ▼
Start new container
       │
       ▼
Validate runtime
       │
       ▼
Validate HTTPS
       │
       ▼
Validate application
```

Det vedvarende volumet må forbli:

```text
lums-data
```

Hemmelighetsmonteringen må forbli skrivebeskyttet.

Applikasjonsporten må forbli kun tilgjengelig på localhost.

---

# 141. Verifiser kjøretidssikkerhet etter utskifting

Gjenta etter hver containerutskifting:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Verifiser:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Verifiser også:

```bash
sudo docker port \
    lums
```

Forventet:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 142. Verifiser vedvarende data etter utskifting

Etter at erstatningscontaineren er startet:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Deretter:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY
```

Forventet:

```text
ok
```

Verifiser til slutt at eksisterende brukere og klienter fortsatt finnes via LUMS-grensesnittet.

---

# 143. Sjekkpunkt etter fullført vedlikehold

Etter vedlikehold, verifiser:

```text
[ ] Container running
[ ] Runtime hardening intact
[ ] Persistent volume mounted
[ ] Database accessible
[ ] SQLite integrity check passes
[ ] Nginx running
[ ] HTTPS working
[ ] Login working
[ ] Existing users present
[ ] Existing clients present
[ ] Agent reporting working
[ ] Watcher working
[ ] Update jobs working
[ ] Audit logging working
```

Først etter disse kontrollene er vedlikeholdsoperasjonen fullført.

---

# 144. Installasjonstilstand på dette tidspunktet

Et korrekt installert LUMS-miljø består nå av:

```text
                    ┌──────────────────────┐
                    │       Browser        │
                    └──────────┬───────────┘
                               │ HTTPS
                               ▼
                    ┌──────────────────────┐
                    │        Nginx         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    LUMS Container    │
                    │                      │
                    │ Flask / Gunicorn     │
                    │ RBAC                 │
                    │ CSRF                 │
                    │ Audit Logging        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │       SQLite         │
                    │     lums-data        │
                    └──────────┬───────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
        ┌──────────────┐              ┌──────────────┐
        │ LUMS Agent   │              │ LUMS Watcher │
        │ 1.7.0        │              │ 1.2.1        │
        └──────┬───────┘              └──────┬───────┘
               │                             │
               ▼                             ▼
        Inventory / Report             Update Jobs
               │                             │
               └──────────────┬──────────────┘
                              ▼
                       APT / pacman
```

Dette er den tiltenkte driftsarkitekturen.

Neste kapittel dekker oppgraderinger, avinstallasjon og den endelige installasjonssjekklisten.

# 145. Oppgraderingsprosedyre

LUMS-oppgraderinger bør utføres i kontrollerte trinn.

Den anbefalte sekvensen er:

```text
Review
   ↓
Backup
   ↓
Test
   ↓
Build
   ↓
Deploy
   ↓
Validate
```

Ikke oppgrader produksjonsinstallasjonen bare fordi en ny Git-revisjon finnes.

Etter at arbeidsflyten `Tests` består på `main`, er et nedlastbart arkiv med
oppdateringsverktøy tilgjengelig under **Artifacts** for den arbeidsflytkjøringen.
Publiserte GitHub Releases får også et versjonert arkiv etter at utgivelsesrevisjonen
har bestått testsuiten. Se [pakkeveiledningen](<Nedlastbar pakke med oppdateringsverktøy.md>).

Gjennomgå endringene først:

```bash
cd /opt/lums-public

git status
git log --oneline -10
```

Gjennomgå de relevante endringene i applikasjonen, agenten og migreringene før distribusjon.

---

# 146. Opprett en sikkerhetskopi før oppgradering

Før du erstatter produksjonscontaineren, opprett en gjeldende sikkerhetskopi av den vedvarende LUMS-tilstanden.

Verifiser det aktive volumet:

```bash
sudo docker inspect \
    lums \
    --format '{{json .Mounts}}'
```

Bekreft at:

```text
lums-data
```

fortsatt er montert på:

```text
/var/lib/lums
```

Beskytt også den eksterne konfigurasjonen:

```text
/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/
```

Ikke fortsett med en oppgradering hvis den nødvendige sikkerhetskopien ikke kan verifiseres.

---

# 147. Unngå unødvendige endringer under en oppgradering

Før oppgradering, inspiser aktive jobber i LUMS-grensesnittet.

Unngå å erstatte applikasjonen mens en kritisk oppdateringsjobb kjører aktivt.

Om nødvendig, vent til jobben når en sluttilstand:

```text
SUCCESS
```

eller:

```text
FAILED
```

Ikke endre en jobb manuelt fra `RUNNING` til `SUCCESS` eller `FAILED` bare for å få gjennomført en oppgradering.

---

# 148. Oppdater repositoriet

Gå til repositoriet:

```bash
cd /opt/lums-public
```

Inspiser den gjeldende tilstanden:

```bash
git status
```

Oppdater repositoriet med den vanlige prosjektarbeidsflyten.

Etter oppdateringen:

```bash
git log --oneline -5
```

Verifiser at den tiltenkte revisjonen er utsjekket.

Ikke distribuer et repositorium som inneholder utilsiktede lokale endringer.

Hvis lokale endringer finnes:

```bash
git status
```

Gjennomgå dem før du fortsetter.

---

# 149. Kjør testsuiten før bygging

Kjør:

```bash
./.venv-test/bin/pytest -q
```

Alle tester må bestå.

Et endret antall tester er ikke automatisk et problem. Kravet er at
hele suiten fullføres uten feil.

---

# 150. Bygg det oppdaterte bildet

Bygg et nytt bilde uten å erstatte den kjørende containeren umiddelbart:

```bash
sudo docker build \
    -t lums:new \
    .
```

Verifiser bildet:

```bash
sudo docker image inspect \
    lums:new
```

Byggingen må fullføres uten feil.

Ikke bruk et mislykket eller delvis bygget bilde til produksjonsdistribusjon.

---

# 151. Verifiser det oppdaterte bildet

Gjennomgå bildets metadata:

```bash
sudo docker image inspect \
    lums:new \
    --format '
User={{.Config.User}}
Entrypoint={{json .Config.Entrypoint}}
Cmd={{json .Config.Cmd}}
'
```

Bildet må bevare den forventede modellen med ikke-privilegert applikasjonsbruker.

Produksjonskjøringen må fortsatt gi:

```text
read-only root filesystem
dropped Linux capabilities
no-new-privileges
read-only secret mount
persistent application volume
localhost-only application port
```

---

# 152. Erstatt produksjonscontaineren

Når det nye bildet har bestått valideringen, erstatt den kjørende containeren med den etablerte herdede konfigurasjonen.

Stopp den eksisterende containeren:

```bash
sudo docker stop \
    lums
```

Fjern bare containeren:

```bash
sudo docker rm \
    lums
```

Fjern **ikke**:

```text
lums-data
```

Start erstatningen med den herdede kjøretiden:

```bash
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
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    lums:new
```

---

# 153. Verifiser erstatningscontaineren

Kontroller:

```bash
sudo docker ps \
    --filter name=lums
```

Deretter:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Verifiser kjøretiden:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Forventet:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

---

# 154. Verifiser applikasjonstilgjengelighet

Kontroller det lokale applikasjonsendepunktet:

```bash
curl -I \
    http://127.0.0.1:5050/
```

Test deretter den offentlige HTTPS-banen:

```bash
curl -I \
    https://LUMS-SERVER/
```

Verifiser innlogging via nettleseren.

Ikke anse oppgraderingen som fullført før den eksterne HTTPS-banen også er testet.

---

# 155. Verifiser vedvarende tilstand etter oppgradering

Kontroller databasen:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

Kjør:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY
```

Forventet:

```text
ok
```

Verifiser via webgrensesnittet at:

```text
users
clients
jobs
audit history
package information
```

fortsatt er tilgjengelige.

---

# 156. Verifiser klientkommunikasjon etter oppgradering

Kjør agenten på en testklient:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspiser:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Verifiser at serveren godtar rapporten.

Verifiser deretter klienten i LUMS-grensesnittet.

---

# 157. Verifiser oppdateringskjøring etter oppgradering

Opprett en kontrollert testjobb.

Verifiser:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

eller en forventet tilstand:

```text
FAILED
```

når operasjonen faktisk feiler.

Inspiser Watcher:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Dette bekrefter at oppgraderingen ikke ødela kjøringsbanen.

---

# 158. Verifiser sikkerhetsgrunnlinjen etter oppgradering

Hver produksjonsoppgradering må bevare sikkerhetsgrunnlinjen.

Verifiser:

```text
[ ] HTTPS
[ ] Bearer client authentication
[ ] RBAC
[ ] CSRF protection
[ ] Audit logging
[ ] Non-root container
[ ] Read-only root filesystem
[ ] Capabilities dropped
[ ] no-new-privileges
[ ] Protected secret mount
[ ] Persistent data volume
[ ] Localhost-only Docker port
[ ] Firewall policy
```

En funksjonell oppgradering som svekker disse egenskapene regnes ikke som fullført.

---

# 159. Tilbakerullingsprosedyre

Hvis den nye containeren feiler valideringen, ikke ødelegg umiddelbart informasjonen om den forrige distribusjonen.

Inspiser først:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Hvis det forrige bildet fortsatt er tilgjengelig:

```bash
sudo docker images
```

gjenopprett det tidligere validerte bildet med samme herdede containerkonfigurasjon.

Det vedvarende volumet forblir:

```text
lums-data
```

Ikke gjenopprett en databasesikkerhetskopi bare fordi applikasjonscontaineren ble byttet ut.

Gjenopprett databasen bare når selve databasen må gjenopprettes.

---

# 160. Forberedelse til avinstallasjon

Før du avinstallerer LUMS, avgjør om de vedvarende applikasjonsdataene skal beholdes.

Følgende er separate ressurser:

```text
Container
Image
Persistent volume
Configuration
TLS material
Nginx configuration
Client installations
```

Fjerning av containeren fjerner ikke Docker-volumet.

Dette skillet er bevisst.

---

# 161. Fjern LUMS-containeren

Stopp containeren:

```bash
sudo docker stop \
    lums
```

Fjern den:

```bash
sudo docker rm \
    lums
```

Verifiser:

```bash
sudo docker ps -a \
    --filter name=lums
```

Det vedvarende volumet finnes fortsatt med mindre det fjernes eksplisitt.

---

# 162. Fjern LUMS Docker-bildet

List bilder:

```bash
sudo docker images \
    'lums*'
```

Fjern bare bilder som ikke lenger trengs:

```bash
sudo docker rmi \
    lums:new
```

Gjenta for andre foreldede lokale LUMS-bilder etter behov.

Ikke fjern bildet som trengs for en tilbakerulling før installasjonen er fullstendig tatt ut av drift.

---

# 163. Fjern det vedvarende volumet

Utfør dette trinnet bare når LUMS-databasen ikke lenger trengs.

Verifiser:

```bash
sudo docker volume inspect \
    lums-data
```

Opprett en siste sikkerhetskopi om nødvendig.

Fjern deretter:

```bash
sudo docker volume rm \
    lums-data
```

Dette fjerner permanent de vedvarende applikasjonsdataene som ligger i dette volumet.

Ikke kjør denne kommandoen under vanlige oppgraderinger.

---

# 164. Fjern LUMS-serverkonfigurasjon

Når serveren tas permanent ut av drift, fjern den LUMS-spesifikke konfigurasjonen:

```text
/etc/lums/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums
```

Fjern Nginx-nettstedet:

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/lums
```

Fjern konfigurasjonen:

```bash
sudo rm -f \
    /etc/nginx/sites-available/lums
```

Valider deretter Nginx:

```bash
sudo nginx -t
```

Last på nytt:

```bash
sudo systemctl reload nginx
```

Fjern `/etc/lums/` først etter at du har verifisert at ingen annen applikasjon avhenger av den.

---

# 165. Fjern klientinstallasjoner

LUMS-klienter må tas ut av drift hver for seg.

Deaktiver agenttimeren:

```bash
sudo systemctl disable --now \
    lums-agent.timer
```

Deaktiver Watcher-timeren:

```bash
sudo systemctl disable --now \
    lums-agent-watcher.timer
```

Stopp eventuelle gjenværende tjenester:

```bash
sudo systemctl stop \
    lums-agent.service \
    lums-agent-watcher.service
```

Fjern de installerte systemd-enhetene:

```bash
sudo rm -f \
    /etc/systemd/system/lums-agent.service \
    /etc/systemd/system/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Last systemd på nytt:

```bash
sudo systemctl daemon-reload
```

Fjern agentinstallasjonen:

```bash
sudo rm -rf \
    /opt/lums-agent
```

Fjern klientkonfigurasjonen:

```bash
sudo rm -f \
    /etc/default/lums-agent
```

Utfør disse trinnene bare når klienten faktisk fjernes fra LUMS-administrasjon.

---

# 166. Endelig sjekkliste for serverinstallasjon

En fullført LUMS-installasjon skal oppfylle alt av følgende:

```text
SERVER
[ ] Debian/Linux host prepared
[ ] Docker installed
[ ] Nginx installed
[ ] Repository deployed
[ ] Application secret generated
[ ] TLS material installed
[ ] LUMS image built
[ ] Persistent volume created
[ ] Hardened container deployed
[ ] Container runs as non-root
[ ] Root filesystem is read-only
[ ] Linux capabilities dropped
[ ] no-new-privileges enabled
[ ] Secret mounted read-only
[ ] Persistent data volume mounted
[ ] Application bound to 127.0.0.1:5050
[ ] Nginx HTTPS configured
[ ] HTTP redirects to HTTPS
[ ] TLS verified
[ ] Database initialized
[ ] SQLite integrity check passes
[ ] Migrations complete
```

---

# 167. Endelig sjekkliste for klientinstallasjon

```text
CLIENT
[ ] Supported Linux distribution
[ ] systemd available
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher installed
[ ] Watcher version verified
[ ] Client configuration protected
[ ] Unique client token configured
[ ] TLS trust configured
[ ] Agent manual run succeeds
[ ] Initial report accepted
[ ] Client visible in LUMS
[ ] Reporting timer enabled
[ ] Watcher timer enabled
[ ] Idle detection verified
[ ] Package inventory verified
[ ] Update detection verified
```

---

# 168. Endelig funksjonell sjekkliste

```text
FUNCTIONALITY
[ ] Administrator login works
[ ] Operator login works
[ ] Viewer login works
[ ] Administrator RBAC verified
[ ] Operator RBAC verified
[ ] Viewer RBAC verified
[ ] Client authentication verified
[ ] Token rotation verified
[ ] Package search verified
[ ] Package installation verified
[ ] Package removal verified
[ ] Package update verified
[ ] System update path verified
[ ] Update jobs verified
[ ] Job result validation verified
[ ] Job recovery verified
[ ] Reboot detection verified
[ ] Audit logging verified
[ ] Logs contain no secrets
[ ] End-to-end reporting verified
[ ] End-to-end update execution verified
```

---

# 169. Endelig sikkerhetssjekkliste

```text
SECURITY
[ ] HTTPS enforced
[ ] Client Bearer authentication enabled
[ ] RBAC enforced server-side
[ ] CSRF protection enabled
[ ] Session protection enabled
[ ] Login rate limiting enabled
[ ] Password hashing enabled
[ ] Client token hashing enabled
[ ] Client token rotation available
[ ] Audit logging enabled
[ ] Secrets outside Git
[ ] Secrets outside Docker image
[ ] TLS private key protected
[ ] Docker root filesystem read-only
[ ] Linux capabilities dropped
[ ] no-new-privileges enabled
[ ] Container runs as non-root
[ ] Persistent data isolated in volume
[ ] Application port localhost-only
[ ] Firewall reviewed
[ ] Default Nginx site removed or controlled
[ ] Backup procedure defined
[ ] Restore procedure tested
```

---

# 170. Endelig testsjekkliste

Kjør hele den automatiserte testsuiten:

```bash
cd /opt/lums-public

./.venv-test/bin/pytest -q
```

Installasjonen bør bare anses som fullført når hele testsuiten består.

Verifiser deretter produksjonskjøringen manuelt:

```bash
sudo docker ps \
    --filter name=lums
```

```bash
sudo docker logs \
    --tail 100 \
    lums
```

```bash
curl -I \
    https://LUMS-SERVER/
```

```bash
sudo ss -lntp
```

---

# 171. Endelig dokumentasjonskontroll

Før du erklærer installasjonen som fullført, verifiser at dokumentasjonen samsvarer med den faktiske distribusjonen.

Gjennomgå som et minimum:

```text
install.md
security.md
troubleshooting.md
administration.md
docs/README.md
```

De tekniske veiledningene på rotnivå vedlikeholdes på engelsk og er
sannhetskilden. Lokaliserte manualer og hurtigstarter er oppført i
[`docs/README.md`](../../README.md); oversettelsesdekningen kan variere, så bruk
den engelske kilden når en lokalisert prosedyre er ufullstendig eller avviker.

Dokumentasjonen må ikke inneholde:

```text
old container commands
obsolete image names
obsolete RBAC rules
obsolete test counts
obsolete service paths
obsolete authentication mechanisms
real secrets
real client tokens
private keys
```

Hvis distribusjonen endres, oppdater dokumentasjonen sammen med implementasjonen.

---

# 172. Utgivelsesklarhet

En vellykket installasjon betyr ikke automatisk at LUMS har en offisiell utgivelse.

Den nåværende prosjekttilstanden skiller bevisst mellom:

```text
Working implementation
Security audit
Documentation review
Release preparation
Versioning
Git tag
GitHub Release
```

En offisiell LUMS-utgivelse bør først opprettes etter at hele implementasjonen, sikkerhetsgjennomgangen, dokumentasjonsgjennomgangen og den endelige valideringen er fullført.

Inntil da bør repositoriet behandles som et prosjekt under aktiv utvikling.

---

# 173. Driftsgrunnlinje

Den nåværende dokumenterte grunnlinjen er:

```text
LUMS Server
    Docker
    Nginx
    HTTPS
    SQLite
    RBAC
    CSRF
    Audit Logging
    Hardened Container

LUMS Agent
    Version 1.7.0

LUMS Watcher
    Version 1.2.1

Database
    journal_mode=wal
    busy_timeout=5000
    synchronous=2
    foreign_keys=ON (application connections)

Container
    non-root
    read-only root filesystem
    CapDrop=ALL
    no-new-privileges
    localhost-only application port

Roles
    Administrator
    Operator
    Viewer
```

Denne grunnlinjen bør behandles som referansetilstanden for feilsøking og fremtidig vedlikehold.

---

# 174. Installasjonen er fullført

Installasjonen er fullført når:

```text
Server
  │
  ├── HTTPS works
  ├── Authentication works
  ├── RBAC works
  ├── Database is healthy
  ├── Container is hardened
  └── Persistent storage is verified
       │
       ▼
Client
  │
  ├── Agent reports
  ├── Watcher executes
  ├── Package manager works
  ├── Jobs complete
  ├── Results are validated
  └── Recovery works
       │
       ▼
Operations
  │
  ├── Backup exists
  ├── Restore is understood
  ├── Troubleshooting documentation is available
  └── Security baseline is maintained
```

Det grunnleggende driftsprinsippet i LUMS er:

```text
Observe first.
Change second.
Verify third.
Document last.
```

For produksjonsendringer utvides dette til:

```text
Backup
   ↓
Change
   ↓
Verify
   ↓
Document
```

En LUMS-installasjon bør alltid forbli reproduserbar, sporbar og gjenopprettbar.


---

## Valgfri CPU- og minnetelemetriagent

For en oversikt over telemetrimålinger, sikkerhet, datalagring og feilsøking, se [telemetry.md](Telemetri.md).

Telemetriagenten er separat fra den eksisterende rapporteringsagenten og Watcher.
Den sender CPU- og minnemålinger til det autentiserte endepunktet
`POST /api/telemetry`. Dashbordet leser målingene via det autentiserte
klienttelemetri-API-et.

### Installasjonsfiler

Gjennomgå disse repositoriefilene før installasjon:

- `agent/telemetry.py`
- `agent/lums-telemetry.service`
- `agent/lums-telemetry.timer`
- `scripts/install-telemetry-agent.sh`
- `tests/test_telemetry_agent.py`

Etter at `/etc/default/lums-agent` er konfigurert som beskrevet nedenfor, oppdater
repositoriets utsjekking på Debian-klienten og kjør dette fra roten:

```sh
sudo bash scripts/install-telemetry-agent.sh
```

Installasjonsprogrammet verifiserer at `LUMS_BASE` og `LUMS_TOKEN` finnes uten å
skrive ut verdiene. Det installerer eller oppdaterer samleren og systemd-enhetene,
aktiverer timeren på fem sekunder og kjører én umiddelbar prøve for å verifisere
tilkoblingen. Hvis tjenesten feiler, skriver det ut nylige logger fra telemetritjenesten.
Tokenet blir værende i den eksisterende klientkonfigurasjonen og kopieres ikke til
en annen fil.

Installer telemetriskriptet som
`/usr/local/lib/lums-telemetry/telemetry.py`, eid av root og ikke skrivbart
for tjenestekontoen. Installer tjenesten og timeren som
`/etc/systemd/system/lums-telemetry.service` og
`/etc/systemd/system/lums-telemetry.timer`.

Tjenesten bruker `DynamicUser=yes`, kjører med begrensede rettigheter og er
lagt til i gruppen `systemd-journal` for skrivebeskyttet tilgang til systemets
hendelseslogger. Dette muliggjør dashbordets avgrensede sikkerhets- og innloggingssammendrag;
rå loggmeldinger sendes ikke til serveren.
Det er en engangstjeneste (one-shot) som planlegges av en separat timer; den erstatter
ikke den eksisterende LUMS Agent eller Watcher.

At en vanlig LUMS-klient er online, betyr ikke at denne separate telemetritimeren
er installert eller aktivert. Siden `/monitoring` forklarer om den valgte
klienten ikke har sendt noen prøver, bare sender grunnleggende målinger, eller har
foreldede detaljerte data.

### Konfigurasjon og TLS

Konfigurer `/etc/default/lums-agent` med server-URL-en og det individuelle
klienttokenet:

```sh
LUMS_BASE=https://lums.example.invalid
LUMS_TOKEN=REPLACE_WITH_THIS_CLIENTS_TOKEN
LUMS_CA_FILE=/etc/ssl/certs/lums-ca.crt
```

Erstatt eksempel-URL-en og tokenet med de faktiske verdiene for miljøet.
Beskytt konfigurasjonsfilen slik at bare root kan lese den, for eksempel med
modus `0600`. Commit aldri et ekte token til kildekodekontroll og del det ikke mellom
klienter.

Valgfritt kan du velge hvilke systemd-tjenesteenheter som skal rapporteres, med en
kommaseparert tillatelsesliste:

```sh
LUMS_MONITORED_SERVICES=lums-agent.service,lums-telemetry.service,ssh.service,wazuh-agent.service,suricata.service
```

Hvis den ikke er satt, bruker agenten sin innebygde liste over LUMS-, Docker- og SSH-tjenester.
Wazuh og Suricata er valgfrie: legg bare til tjenesteenheter som er installert på
klienten, og aktiver deretter statusradene deres i `/health`-dashbordet. Dette rapporterer
bare systemd-tilstand; det krever eller lagrer ikke API-legitimasjon og henter ikke
sikkerhetsvarselstrømmer.

Hvis en privat sertifiseringsinstans kreves, installer dens sertifikat på
en sti som kan leses av tjenesteprosessen, for eksempel
`/etc/ssl/certs/lums-ca.crt`, og sett `LUMS_CA_FILE` tilsvarende. Ikke
deaktiver sertifikatverifisering. Når `LUMS_CA_FILE` ikke er satt, bruker agenten operativsystemets
standard CA-klareringslager. Hvis en privat CA kreves, sett eksplisitt
`LUMS_CA_FILE` til en eksisterende CA-sertifikatfil som kan leses av tjenesteprosessen.
En eksplisitt konfigurert, men manglende eller uleselig CA-fil får agenten til å feile
i stedet for stille å falle tilbake til et annet klareringslager.
Ikke deaktiver sertifikatverifisering og ikke svekk katalogtillatelser for å
omgå problemer med sertifikatkonfigurasjonen.

### Validering før aktivering

Kjør først prosjekttestene og verifiser enhetsfilene:

```sh
.venv/bin/python -m pytest -q tests/test_telemetry.py tests/test_telemetry_agent.py
systemd-analyze verify agent/lums-telemetry.service agent/lums-telemetry.timer
```

På en testklient, installer filene og konfigurasjonen, last systemd på nytt og
kjør tjenesten manuelt før du aktiverer timeren. Bekreft vellykket
autentisering og innkommende prøver i dashbordet. Aktiver først deretter
timeren på den testklienten. Ikke aktiver den på produksjonsklienter før
utgivelsen på serversiden er gjennomgått og godkjent.

Agenten rapporterer hvert femte sekund. Serveren beholder målinger i
sju dager, og dashbord-API-et returnerer høyst 1 000 jevnt fordelte prøver
per forespurt historikkvindu, med bevaring av den første og den nyeste prøven.
