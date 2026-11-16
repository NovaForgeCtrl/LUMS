# LUMS Installasjonsveiledning
# LUMS-installasjonsveiledning

## Linux Update Management Server

**Project:** LUMS
**Slogan:** Linux Update Management without the noise.
**Repository:** `NovaForgeCtrl/LUMS`
**Prosjekt:** LUMS
**Slagord:** Linux Update Management without the noise.
**Repositorium:** `NovaForgeCtrl/LUMS`

---

## Kom i gang: Understand the Installation Before You Begin
## Kom i gang: forstå installasjonen før du begynner

This guide covers a complete server installation, including advanced
maintenance and verification procedures. It is **not** a single script to run
without review: the server name, TLS certificate, secret file, backup
destination, network, and database vary between installations.
Denne veiledningen dekker en komplett serverinstallasjon, inkludert avanserte
vedlikeholds- og verifiseringsprosedyrer. Den er **ikke** et enkelt skript som
skal kjøres uten gjennomgang: servernavn, TLS-sertifikat, hemmelighetsfil,
sikkerhetskopimål, nettverk og database varierer mellom installasjoner.

### Hva blir installert?

* **LUMS server:** the web interface and API, running in a Docker container.
* **Nginx:** accepts external HTTPS connections and forwards them locally to
  the container.
* **Data volume:** contains the SQLite database. This volume must survive
  upgrades and must never be deleted during a normal container replacement.
* **Secret file:** protects application sessions, among other things. Never
  put it in the Git repository, a Docker image, or a chat message.
* **LUMS Agent and Watcher:** installed separately on managed Linux clients. A
  working server alone does not update any clients.
* **LUMS-server:** webgrensesnittet og API-et, som kjører i en Docker-container.
* **Nginx:** tar imot eksterne HTTPS-tilkoblinger og videresender dem lokalt
  til containeren.
* **Datavolum:** inneholder SQLite-databasen. Dette volumet må overleve
  oppgraderinger og må aldri slettes ved et vanlig containerbytte.
* **Hemmelighetsfil:** beskytter blant annet applikasjonsøkter. Legg den aldri
  i Git-repositoriet, et Docker-bilde eller en chatmelding.
* **LUMS Agent og Watcher:** installeres separat på administrerte Linux-klienter.
  En fungerende server alene oppdaterer ingen klienter.

| Term | Meaning |
| --- | --- |
| Terminal / shell | A text window where you enter Linux commands. |
| `sudo` | Runs the command that follows with administrator rights. Linux may ask for your password. |
| Host | The Linux computer running Docker and the LUMS server. |
| Container | An isolated process running the LUMS web application. |
| Image | A prepared template Docker uses to start a container. |
| Volume | Persistent Docker storage that remains when a container is replaced. |
| Placeholder | Text such as `LUMS-SERVER` that must be replaced with your actual value. |
| Terminal / skall | Et tekstvindu der du skriver Linux-kommandoer. |
| `sudo` | Kjører kommandoen som følger med administratorrettigheter. Linux kan be om passordet ditt. |
| Vert | Linux-maskinen som kjører Docker og LUMS-serveren. |
| Container | En isolert prosess som kjører LUMS-webapplikasjonen. |
| Bilde (image) | En ferdig mal Docker bruker til å starte en container. |
| Volum | Vedvarende Docker-lagring som blir værende når en container byttes ut. |
| Plassholder | Tekst som `LUMS-SERVER` som må erstattes med din faktiske verdi. |

### Run tests only (this does not install a server)
### Kjør bare tester (dette installerer ingen server)

These steps are suitable for Debian 13 to check out the source and run tests
locally. They do **not** create a production server reachable over the network
and do not install an agent on another computer. `sudo` is only needed to
install Debian packages.
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

`apt update` refreshes package lists; it does not upgrade all installed
software. The `.venv-test` Python virtual environment keeps test dependencies
separate from the rest of the system. A successful test run exits with code
`0`; the number of tests can change as the project grows. If creating the
environment fails, check that `python3-venv` is installed. If a test fails,
save the complete error and read the
[troubleshooting guide](troubleshooting.md); do not delete production data.

For a real installation, continue with the numbered sections and read the
security and backup instructions first. If LUMS is already running, use the
upgrade procedure in [`administration.md`](administration.md), not the
first-install procedure.
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

LUMS is a centralized Linux update management platform for controlled update distribution, client reporting, package management, update-job execution, result validation and auditable administration.

The current Arkitektur separates the management server from the managed Linux clients.

The server provides:

* Web-based administration
* Client management
* Client authentication
* Package inventory
* Available-update reporting
* Package search
* Package installation and removal
* Update-job management
* Job result validation
* Update history
* Role-based access control
* Audit logging
* SQLite-based persistent state

Linux clients provide:

* System information
* Installed-package inventory
* Available-update detection
* Package operations
* Update-job execution
* Idle-state detection
* Job checkpointing and recovery
* Reboot detection
* Result reporting

The current implementation supports:

```text
Debian / Ubuntu
    â””â”€â”€ APT / dpkg

Arch Linux
    â””â”€â”€ pacman
```
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

The production Arkitektur is:

```text
                         LUMS Server
                              â”‚
                              â”‚ HTTPS :443
                              â–¼
                       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                       â”‚    Nginx     â”‚
                       â”‚  TLS / Proxy â”‚
                       â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚
                              â”‚ HTTP
                              â–¼
                       127.0.0.1:5050
                              â”‚
                              â–¼
                    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                    â”‚   Docker: lums    â”‚
                    â”‚                   â”‚
                    â”‚   Gunicorn        â”‚
                    â”‚   Flask :5000     â”‚
                    â”‚   SQLite          â”‚
                    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚
                              â–¼
                         lums-data
                              â”‚
                              â–¼
```
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
```
                   /var/lib/lums/lums.db


        Linux Client
              â”‚
              â”‚ HTTPS + Bearer Token
              â–¼
         LUMS API
              â”‚
              â”œâ”€â”€ Report
              â”œâ”€â”€ Package Search
              â”œâ”€â”€ Job Retrieval
              â””â”€â”€ Job Result
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

The LUMS application is **not intended to be directly exposed to the network**.

The application container is bound to:

```text
127.0.0.1:5050 â†’ container:5000
```

Nginx is the external HTTPS entry point.

Port `5000` is not published directly.

Port `5050` must remain localhost-only.
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

A complete LUMS installation consists of several components.
En komplett LUMS-installasjon består av flere komponenter.

## 3.1 LUMS Server
## 3.1 LUMS-server

The server contains:
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

The application runs inside the Docker container:
Applikasjonen kjører i Docker-containeren:

```text
lums
```

The persistent database is stored outside the container's writable application filesystem:
Den vedvarende databasen lagres utenfor containerens skrivbare applikasjonsfilsystem:

```text
lums-data:/var/lib/lums/lums.db
```

---

## 3.2 Nginx

Nginx provides:
Nginx tilbyr:

```text
HTTPS termination
TLS certificate handling
HTTP â†’ HTTPS redirect
HTTP → HTTPS redirect
Reverse proxy
External network entry point
```

The intended request path is:

```text
Browser
   â”‚
   â”‚ HTTPS
   â–¼
Nginx
   â”‚
   â”‚ localhost HTTP
   â–¼
127.0.0.1:5050
   â”‚
   â–¼
LUMS
```

The Flask/Gunicorn application should not be exposed directly to the LAN.
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

## 3.3 Linux Agent
## 3.3 Linux-agent

The LUMS Agent runs on every managed Linux client.

The current Agent version is:
LUMS Agent kjører på hver administrerte Linux-klient.

Den nåværende agentversjonen er:

```text
1.7.0
```

The Agent is responsible for:
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

The Agent communicates with the LUMS server using HTTPS and a client-specific Bearer token.
Agenten kommuniserer med LUMS-serveren via HTTPS og et klientspesifikt Bearer-token.

---

## 3.4 Execution Watcher
## 3.4 Utføringsovervåker (Watcher)

The execution watcher is responsible for controlled update-job execution.

The current Watcher version is:
Utføringsovervåkeren er ansvarlig for kontrollert kjøring av oppdateringsjobber.

Den nåværende Watcher-versjonen er:

```text
1.2.1
```

The Watcher handles:
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

The Watcher is intentionally separated from ordinary client reporting.
Watcher er bevisst adskilt fra vanlig klientrapportering.

---

# 4. Sikkerhetsmodell

The installation must preserve the LUMS security baseline.

The production server uses:
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

The Docker container runs as the unprivileged user:
Docker-containeren kjører som den uprivilegerte brukeren:

```text
lums
```

with UID:
med UID:

```text
10001
```

The container must not run in privileged mode.

The root filesystem must remain read-only.

The application must not require write access to its application directory.

Persistent application data is stored through the dedicated Docker volume.
Containeren må ikke kjøre i privilegert modus.

Rotfilsystemet må forbli skrivebeskyttet.

Applikasjonen må ikke kreve skrivetilgang til applikasjonskatalogen sin.

Vedvarende applikasjonsdata lagres via det dedikerte Docker-volumet.

---

# 5. Current RBAC Model
# 5. Nåværende RBAC-modell

LUMS currently provides three web roles:
LUMS tilbyr for øyeblikket tre webroller:

```text
administrator
operator
viewer
```

## Administrator

Administrators can perform administrative operations including:
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

Operators can perform operational management:
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

Operators do not have access to:
Operatører har ikke tilgang til:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

---

## Viewer

Viewers have intentionally restricted access.

A Viewer can access:
Visere har bevisst begrenset tilgang.

En Viewer har tilgang til:

```text
Clients
Installed software
```

The following management areas are hidden from the Viewer interface and protected server-side:
Følgende administrasjonsområder er skjult i Viewer-grensesnittet og beskyttet på serversiden:

```text
Available updates
Update Jobs
Update History
Package Management
System Maintenance
```

UI hiding is therefore not the security boundary.

Server-side authorization remains mandatory.
Skjuling i brukergrensesnittet er derfor ikke sikkerhetsgrensen.

Autorisasjon på serversiden er fortsatt obligatorisk.

---

# 6. Installasjonskrav

## 6.1 LUMS Server
## 6.1 LUMS-server

The current deployment requires a Linux host with:
Den nåværende distribusjonen krever en Linux-vert med:

```text
Docker Engine
Git
Nginx
OpenSSL
Network connectivity
Persistent storage
```

The server must have enough storage for:
Serveren må ha nok lagringsplass til:

```text
Docker images
SQLite database
Application data
Logs
Backups
```

The LUMS application itself runs inside Docker.
Selve LUMS-applikasjonen kjører i Docker.

---

## 6.2 Linux Clients
## 6.2 Linux-klienter

Managed Linux clients require:
Administrerte Linux-klienter krever:

```text
Python 3
systemd
Supported package manager
Network connectivity to the LUMS server
Valid client token
Trusted TLS certificate
```

Supported package-management families:
Støttede pakkehåndteringsfamilier:

```text
Debian / Ubuntu
    APT / dpkg

Arch Linux
    pacman
```

The client must be able to reach the LUMS HTTPS endpoint.
Klienten må kunne nå LUMS' HTTPS-endepunkt.

---

# 7. Anbefalt mappelayout
# 7. Anbefalt katalogstruktur

The recommended server-side repository location is:
Den anbefalte plasseringen av repositoriet på serveren er:

```text
/opt/lums-public/
```

The repository contains the application source, Agent source and tests.

A typical installation uses:

```text
/opt/lums-public/
    â”œâ”€â”€ agent/
    â”œâ”€â”€ server/
    â”œâ”€â”€ tests/
    â”œâ”€â”€ Dockerfile
    â”œâ”€â”€ requirements.txt
    â””â”€â”€ requirements-dev.txt
```

Host-side configuration is kept outside the repository:

```text
/etc/lums/
    â”œâ”€â”€ secrets/
    â”‚   â””â”€â”€ lums_secret
    â””â”€â”€ tls/
        â”œâ”€â”€ lums.crt
        â””â”€â”€ lums.key
```

Persistent application data is stored in:
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

The SQLite database is:
SQLite-databasen er:

```text
/var/lib/lums/lums.db
```

The database must never be stored inside the Git working tree.

Secrets and private TLS material must also remain outside the repository.
Databasen må aldri lagres inne i Git-arbeidstreet.

Hemmeligheter og privat TLS-materiale må også forbli utenfor repositoriet.

---

# 8. Repository Preparation
# 8. Klargjøring av repositoriet

Clone the repository into the intended installation directory:
Klon repositoriet inn i den tiltenkte installasjonskatalogen:

```bash
sudo mkdir -p /opt
cd /opt

sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public
```

Enter the repository:
Gå inn i repositoriet:

```bash
cd /opt/lums-public
```

Check the working tree:
Kontroller arbeidstreet:

```bash
git status
```

Inspect the current revision:
Inspiser den gjeldende revisjonen:

```bash
git log -1 --oneline --decorate
```

For controlled deployments, the exact commit used for the installation should be recorded.

Do not build production images from an unknown or unverified working tree.
For kontrollerte distribusjoner bør den nøyaktige commit-en som brukes til installasjonen, dokumenteres.

Ikke bygg produksjonsbilder fra et ukjent eller ubekreftet arbeidstre.

---

# 9. Repository Security Check
# 9. Sikkerhetskontroll av repositoriet

Before building the production image, verify that sensitive files have not been placed into the repository.

Review the working tree:
Før du bygger produksjonsbildet, kontroller at ingen sensitive filer er plassert i repositoriet.

Gjennomgå arbeidstreet:

```bash
git status --short
```

Review ignored files where appropriate:
Gjennomgå ignorerte filer der det er hensiktsmessig:

```bash
git status --ignored --short
```

The repository must not contain:
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

The project uses repository ignore rules to prevent common backup artifacts from being accidentally tracked.

Before committing changes, inspect the staged file list carefully.
Prosjektet bruker ignoreringsregler i repositoriet for å hindre at vanlige sikkerhetskopiartefakter ved et uhell blir sporet.

Før du committer endringer, inspiser listen over stagede filer nøye.

---

# 10. Prepare Host Configuration Directories
# 10. Klargjør konfigurasjonskataloger på verten

Create the required host-side directories:
Opprett de nødvendige katalogene på verten:

```bash
sudo install -d -m 700 /etc/lums
sudo install -d -m 700 /etc/lums/secrets
sudo install -d -m 700 /etc/lums/tls
```

The secret directory contains the application secret.

The TLS directory contains the TLS certificate and private key.

Protecting these directories reduces the risk of accidental disclosure.

Verify:
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

# 11. Create the Application Secret
# 11. Opprett applikasjonshemmeligheten

The LUMS application secret is stored on the host rather than embedded directly into the Docker image.

The production secret path is:
LUMS' applikasjonshemmelighet lagres på verten i stedet for å bygges direkte inn i Docker-bildet.

Stien til produksjonshemmeligheten er:

```text
/etc/lums/secrets/lums_secret
```

Generate a random secret:
Generer en tilfeldig hemmelighet:

```bash
sudo sh -c 'umask 077 && openssl rand -hex 32 > /etc/lums/secrets/lums_secret'
```

Protect the resulting file:
Beskytt den resulterende filen:

```bash
sudo chmod 600 \
    /etc/lums/secrets/lums_secret
```

Verify the permissions without displaying the secret:
Verifiser tillatelsene uten å vise hemmeligheten:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/secrets/lums_secret
```

Expected:
Forventet:

```text
600
```

The secret must never be:
Hemmeligheten må aldri være:

```text
Committed to Git
Printed into logs
Included in the Docker image
Placed into screenshots
Published in issues
Included in documentation
```

The container receives the secret through a read-only bind mount.
Containeren mottar hemmeligheten gjennom en skrivebeskyttet bind-montering.

---

# 12. Prepare TLS Material
# 12. Klargjør TLS-materiale

LUMS uses HTTPS for external access.

The recommended host-side locations are:
LUMS bruker HTTPS for ekstern tilgang.

De anbefalte plasseringene på verten er:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Install the appropriate certificate and private key before configuring Nginx.

Protect the private key:
Installer riktig sertifikat og privat nøkkel før du konfigurerer Nginx.

Beskytt den private nøkkelen:

```bash
sudo chmod 600 \
    /etc/lums/tls/lums.key
```

The certificate may be readable by the Nginx service:
Sertifikatet kan være lesbart for Nginx-tjenesten:

```bash
sudo chmod 644 \
    /etc/lums/tls/lums.crt
```

Verify:
Verifiser:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

The private key must never be committed to Git or included in the Docker image.
Den private nøkkelen må aldri committes til Git eller inkluderes i Docker-bildet.

---

# 13. Installation Principle
# 13. Installasjonsprinsipp

The installation should proceed in controlled stages:

```text
Repository
    â†“
Host configuration
    â†“
Application secret
    â†“
TLS material
    â†“
Docker image
    â†“
Persistent volume
    â†“
Hardened container
    â†“
Nginx / HTTPS
    â†“
Administrator
    â†“
Server validation
    â†“
Linux clients
```

Do not connect production clients before the server has passed its own validation checks.

The following sections continue with Docker image construction and the hardened production deployment.
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

# 14. Build the LUMS Docker Image
# 14. Bygg LUMS Docker-bildet

Before building the production image, make sure the repository is in the intended state.

Enter the repository:
Før du bygger produksjonsbildet, sørg for at repositoriet er i ønsket tilstand.

Gå inn i repositoriet:

```bash
cd /opt/lums-public
```

Run the test suite before creating a production image:
Kjør testsuiten før du lager et produksjonsbilde:

```bash
./.venv-test/bin/pytest -q
```

The test count is expected to grow as the project evolves.

The important requirement is that the relevant test suite completes successfully before deployment.

Build the Docker image:
Antall tester forventes å vokse etter hvert som prosjektet utvikler seg.

Det viktige kravet er at den relevante testsuiten fullføres uten feil før distribusjon.

Bygg Docker-bildet:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Verify that the image exists:
Verifiser at bildet finnes:

```bash
sudo docker image ls lums
```

Inspect the image:
Inspiser bildet:

```bash
sudo docker image inspect lums:latest
```

The production image is based on a pinned Python 3.13 slim base image.

The Dockerfile also uses pinned production dependencies where required.
Produksjonsbildet er basert på et festet (pinned) Python 3.13 slim-basisbilde.

Dockerfile bruker også festede produksjonsavhengigheter der det er nødvendig.

---

# 15. Review the Docker Build
# 15. Gjennomgå Docker-byggingen

Before deploying the image, review the build output for unexpected errors or warnings.

Check the resulting image:
Før du distribuerer bildet, gjennomgå byggeresultatet for uventede feil eller advarsler.

Kontroller det resulterende bildet:

```bash
sudo docker inspect \
    lums:latest
```

Verify the configured application user:
Verifiser den konfigurerte applikasjonsbrukeren:

```bash
sudo docker image inspect \
    lums:latest \
    --format '{{.Config.User}}'
```

The application is intended to run as:
Applikasjonen er ment å kjøre som:

```text
lums
```

The application must not require root privileges during normal execution.

Review the Dockerfile when changing the build process:
Applikasjonen må ikke kreve root-rettigheter under normal kjøring.

Gjennomgå Dockerfile når byggeprosessen endres:

```bash
sed -n '1,240p' Dockerfile
```

Do not add secrets, certificates or production databases to the Docker build context.

The repository contains a `.dockerignore` file to reduce the risk of accidentally including runtime artifacts in the image.
Ikke legg hemmeligheter, sertifikater eller produksjonsdatabaser i Docker-byggekonteksten.

Repositoriet inneholder en `.dockerignore`-fil for å redusere risikoen for at kjøretidsartefakter ved et uhell havner i bildet.

---

# 16. Create the Persistent Docker Volume
# 16. Opprett det vedvarende Docker-volumet

Create the persistent LUMS data volume:
Opprett det vedvarende LUMS-datavolumet:

```bash
sudo docker volume create lums-data
```

Verify:
Verifiser:

```bash
sudo docker volume inspect lums-data
```

The volume stores persistent application data:

```text
lums-data
    â†“
/var/lib/lums
    â†“
/var/lib/lums/lums.db
```

The container filesystem itself must not be treated as persistent application storage.

The database therefore survives container replacement as long as the `lums-data` volume is preserved.

> [!IMPORTANT]
> Never remove `lums-data` during a normal application upgrade.

Removing the volume removes the SQLite database stored inside it.
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

# 17. Verify the Persistent Volume
# 17. Verifiser det vedvarende volumet

Before starting LUMS, confirm that the volume exists:
Før du starter LUMS, bekreft at volumet finnes:

```bash
sudo docker volume inspect \
    lums-data
```

The volume can also be checked through Docker:
Volumet kan også kontrolleres via Docker:

```bash
sudo docker volume ls | grep lums-data
```

A newly created volume will normally not contain a database yet.

The database is initialized by the LUMS application during deployment.
Et nyopprettet volum inneholder normalt ingen database ennå.

Databasen initialiseres av LUMS-applikasjonen under distribusjonen.

---

# 18. Production Container Configuration
# 18. Konfigurasjon av produksjonscontaineren

The production container uses several security controls simultaneously.

The expected runtime baseline is:
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

The application port is published only to localhost:

```text
127.0.0.1:5050 â†’ container:5000
```

The external HTTPS endpoint is provided by Nginx.
Applikasjonsporten publiseres bare til localhost:

```text
127.0.0.1:5050 → container:5000
```

Det eksterne HTTPS-endepunktet leveres av Nginx.

---

# 19. Start the Hardened LUMS Container
# 19. Start den herdede LUMS-containeren

Before starting a new production container, make sure another container named `lums` is not already running:
Før du starter en ny produksjonscontainer, sørg for at ingen annen container med navnet `lums` allerede kjører:

```bash
sudo docker ps \
    --filter name=lums
```

If an existing deployment is being replaced, preserve the existing container until the new image has been validated.

Start the hardened container:
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

The application secret is mounted read-only.

The SQLite database is stored in the persistent volume.

The root filesystem is read-only.

All Linux capabilities are dropped.

The `no-new-privileges` security option prevents processes inside the container from gaining additional privileges.
Applikasjonshemmeligheten monteres skrivebeskyttet.

SQLite-databasen lagres i det vedvarende volumet.

Rotfilsystemet er skrivebeskyttet.

Alle Linux-capabilities er fjernet.

Sikkerhetsvalget `no-new-privileges` hindrer prosesser i containeren i å oppnå ekstra rettigheter.

---

# 20. Verify the Container State
# 20. Verifiser containerens tilstand

Check the running container:
Kontroller den kjørende containeren:

```bash
sudo docker ps \
    --filter name=lums
```

Expected state:
Forventet tilstand:

```text
Up ...
```

Check the container state directly:
Kontroller containerens tilstand direkte:

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Expected:
Forventet:

```text
running
```

Inspect recent logs:
Inspiser nylige logger:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Application startup errors must be resolved before continuing with the installation.
Oppstartsfeil i applikasjonen må løses før du fortsetter med installasjonen.

---

# 21. Verify Container Security
# 21. Verifiser containersikkerheten

Inspect the effective runtime security configuration:
Inspiser den effektive sikkerhetskonfigurasjonen ved kjøring:

```bash
sudo docker inspect lums \
    --format='User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}'
```

The expected baseline is:
Den forventede grunnlinjen er:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

The exact formatting of the Docker output may vary.

The effective configuration is what matters.
Den nøyaktige formateringen av Docker-utdataene kan variere.

Det er den effektive konfigurasjonen som teller.

---

# 22. Verify the Application Port
# 22. Verifiser applikasjonsporten

Check the published Docker port:
Kontroller den publiserte Docker-porten:

```bash
sudo docker port lums
```

Expected:
Forventet:

```text
5000/tcp -> 127.0.0.1:5050
```

The following is **not** acceptable for the production application:
Følgende er **ikke** akseptabelt for produksjonsapplikasjonen:

```text
0.0.0.0:5050
```

or:
eller:

```text
0.0.0.0:5000
```

The application is intentionally accessible only through the local reverse-proxy path.

Check the listening sockets:
Applikasjonen er bevisst bare tilgjengelig via den lokale omvendte proxy-banen.

Kontroller lyttende sockets:

```bash
sudo ss -lntp | grep -E ':5050|:5000'
```

Only the localhost application binding should be present.
Bare localhost-bindingen for applikasjonen skal være til stede.

---

# 23. Verify the Secret Mount
# 23. Verifiser hemmelighetsmonteringen

Confirm that the secret is mounted:
Bekreft at hemmeligheten er montert:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Source "->" .Destination "RW=" .RW}}{{end}}'
```

The application secret should appear similar to:
Applikasjonshemmeligheten skal se omtrent slik ut:

```text
/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
```

The exact output may contain additional mount information.

The important property is:
De nøyaktige utdataene kan inneholde ytterligere informasjon om monteringen.

Den viktige egenskapen er:

```text
RW=false
```

Never print the secret contents.

A direct readability test is sufficient:
Skriv aldri ut innholdet i hemmeligheten.

En direkte lesbarhetstest er tilstrekkelig:

```bash
sudo docker exec lums \
    sh -c 'test -r /run/secrets/lums_secret && echo "secret mount: OK"'
```

Expected:
Forventet:

```text
secret mount: OK
```

---

# 24. Verify the Persistent Volume Mount
# 24. Verifiser monteringen av det vedvarende volumet

Inspect the container mounts:
Inspiser containerens monteringer:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Type .Source "->" .Destination "RW=" .RW}}{{end}}'
```

The LUMS data volume must be mounted at:
LUMS-datavolumet må være montert på:

```text
/var/lib/lums
```

and must be writable:
og må være skrivbart:

```text
RW=true
```

The expected relationship is:

```text
lums-data
    â†“
/var/lib/lums
```

The root filesystem remains read-only while the dedicated data volume provides the required persistent write access.
Det forventede forholdet er:

```text
lums-data
    ↓
/var/lib/lums
```

Rotfilsystemet forblir skrivebeskyttet, mens det dedikerte datavolumet gir den nødvendige vedvarende skrivetilgangen.

---

# 25. Verify the Read-Only Root Filesystem
# 25. Verifiser det skrivebeskyttede rotfilsystemet

The application root filesystem must be read-only.

The container runtime should report:
Applikasjonens rotfilsystem må være skrivebeskyttet.

Container-kjøretiden skal rapportere:

```text
ReadonlyRootfs=true
```

A controlled write test can be performed inside the container.

For example:
En kontrollert skrivetest kan utføres inne i containeren.

For eksempel:

```bash
sudo docker exec lums \
    sh -c 'touch /app/.write-test'
```

The command should fail because `/app` is part of the read-only container filesystem.

Do not disable the read-only root filesystem merely because an application component attempts to write outside its designated writable locations.

If the application requires persistent data, use the appropriate volume or runtime filesystem instead.
Kommandoen skal feile fordi `/app` er en del av containerens skrivebeskyttede filsystem.

Ikke deaktiver det skrivebeskyttede rotfilsystemet bare fordi en applikasjonskomponent forsøker å skrive utenfor sine angitte skrivbare plasseringer.

Hvis applikasjonen trenger vedvarende data, bruk det aktuelle volumet eller kjøretidsfilsystemet i stedet.

---

# 26. Verify the Writable Temporary Filesystem
# 26. Verifiser det skrivbare midlertidige filsystemet

The container provides a dedicated `/tmp` tmpfs.

Verify:
Containeren har et dedikert `/tmp`-tmpfs.

Verifiser:

```bash
sudo docker exec lums \
    sh -c 'touch /tmp/lums-write-test && rm -f /tmp/lums-write-test && echo "tmpfs: OK"'
```

Expected:
Forventet:

```text
tmpfs: OK
```

The temporary filesystem is configured with:
Det midlertidige filsystemet er konfigurert med:

```text
noexec
nosuid
```

and a size limit.

This provides temporary writable storage without making the container root filesystem writable.
og en størrelsesgrense.

Dette gir midlertidig skrivbar lagring uten at containerens rotfilsystem blir skrivbart.

---

# 27. Verify the Application Data Directory
# 27. Verifiser applikasjonens datakatalog

The LUMS application requires write access to its persistent data directory.
LUMS-applikasjonen krever skrivetilgang til sin vedvarende datakatalog.

Test:

```bash
sudo docker exec lums \
    sh -c 'touch /var/lib/lums/.write-test && rm -f /var/lib/lums/.write-test && echo "data volume: OK"'
```

Expected:
Forventet:

```text
data volume: OK
```

This confirms that the dedicated writable volume is available while the rest of the container remains read-only.
Dette bekrefter at det dedikerte skrivbare volumet er tilgjengelig mens resten av containeren forblir skrivebeskyttet.

---

# 28. Verify the Application User
# 28. Verifiser applikasjonsbrukeren

Confirm the effective runtime user:
Bekreft den effektive kjøretidsbrukeren:

```bash
sudo docker exec lums \
    id
```

The process should run as the unprivileged LUMS user.

Expected identity includes:
Prosessen skal kjøre som den uprivilegerte LUMS-brukeren.

Forventet identitet inneholder:

```text
uid=10001(lums)
```

The exact group information may vary according to the image configuration.

The container must not run as:
Den nøyaktige gruppeinformasjonen kan variere avhengig av bildets konfigurasjon.

Containeren må ikke kjøre som:

```text
root
```

during normal operation.
under normal drift.

---

# 29. Database Initialization
# 29. Databaseinitialisering

After the container starts, check whether the database exists:
Etter at containeren har startet, kontroller om databasen finnes:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

If the application has initialized successfully, the database should be present.

The database is located at:
Hvis applikasjonen er initialisert, skal databasen være til stede.

Databasen ligger i:

```text
/var/lib/lums/lums.db
```

inside the container and physically persists through:
inne i containeren og er fysisk vedvarende gjennom:

```text
lums-data
```

The database must not be copied into:
Databasen må ikke kopieres til:

```text
/opt/lums-public
```

or committed to Git.
eller committes til Git.

---

# 30. Verify SQLite Runtime Configuration
# 30. Verifiser SQLite-kjøretidskonfigurasjonen

The current LUMS production baseline uses:
Den nåværende LUMS-produksjonsgrunnlinjen bruker:

```text
journal_mode = wal
busy_timeout = 5000 ms
synchronous = 2
foreign_keys = ON
```

The application explicitly enables foreign-key enforcement for database connections.

The database uses WAL mode for normal production operation.

The runtime configuration can be inspected from the application database.

For example:
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

Expected values are equivalent to:
Forventede verdier tilsvarer:

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

The application enables foreign keys explicitly.
Applikasjonen aktiverer fremmednøkler eksplisitt.

---

# 31. Verify Database Integrity
# 31. Verifiser databaseintegriteten

Run an SQLite integrity check:
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

Expected:
Forventet:

```text
ok
```

Do not continue with deployment if the integrity check reports database corruption.
Ikke fortsett med distribusjonen hvis integritetskontrollen melder om databaseskade.

---

# 32. Verify Database Migrations
# 32. Verifiser databasemigreringer

LUMS uses application migrations for database schema changes.

Inspect the migration-related files:
LUMS bruker applikasjonsmigreringer for endringer i databaseskjemaet.

Inspiser de migreringsrelaterte filene:

```bash
ls -lh \
    server/*migration*.py
```

The application performs required migrations during startup/deployment according to the current implementation.

After startup, inspect the application logs:
Applikasjonen utfører nødvendige migreringer under oppstart/distribusjon i henhold til den gjeldende implementasjonen.

Etter oppstart, inspiser applikasjonsloggene:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Migration errors must be investigated before creating users or connecting clients.

Do not manually modify the production SQLite schema unless the project documentation explicitly requires it.
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

# 33. Local Application Validation
# 33. Lokal applikasjonsvalidering

Before configuring Nginx, confirm that the application responds locally.

The Docker application is bound to:
Før du konfigurerer Nginx, bekreft at applikasjonen svarer lokalt.

Docker-applikasjonen er bundet til:

```text
127.0.0.1:5050
```

A local request can be tested with:
En lokal forespørsel kan testes med:

```bash
curl -I \
    http://127.0.0.1:5050/
```

The exact HTTP response depends on the current application route and authentication state.

The important requirement is that the request reaches the running LUMS application.

If the connection fails, inspect:
Det nøyaktige HTTP-svaret avhenger av den gjeldende applikasjonsruten og autentiseringstilstanden.

Det viktige kravet er at forespørselen når den kjørende LUMS-applikasjonen.

Hvis tilkoblingen mislykkes, inspiser:

```bash
sudo docker ps \
    --filter name=lums
```

and:
og:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Do not expose port `5050` externally as a troubleshooting workaround.
Ikke eksponer port `5050` eksternt som en omvei ved feilsøking.

---

# 34. Initial Server Checkpoint
# 34. Første serversjekkpunkt

At this stage, the server should satisfy:
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

Do not connect production clients yet.

The next stage configures Nginx, HTTPS and the external LUMS endpoint.
Ikke koble til produksjonsklienter ennå.

Neste trinn konfigurerer Nginx, HTTPS og det eksterne LUMS-endepunktet.

# 35. Configure Nginx
# 35. Konfigurer Nginx

Nginx provides the external HTTPS entry point for LUMS.

The application itself remains bound to:
Nginx er det eksterne HTTPS-inngangspunktet for LUMS.

Selve applikasjonen forblir bundet til:

```text
127.0.0.1:5050
```

The intended request path is:

```text
Client
   â”‚
   â”‚ HTTPS
   â–¼
Nginx :443
   â”‚
   â”‚ HTTP localhost
   â–¼
127.0.0.1:5050
   â”‚
   â–¼
LUMS container :5000
```

Create the Nginx site configuration:
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

Replace:
Erstatt:

```text
LUMS-SERVER
```

with the hostname or address used by the installation.

Do not use the literal placeholder in a production configuration.
med vertsnavnet eller adressen som brukes i installasjonen.

Ikke bruk den bokstavelige plassholderen i en produksjonskonfigurasjon.

---

# 36. Enable the LUMS Nginx Configuration
# 36. Aktiver LUMS' Nginx-konfigurasjon

Create the enabled-site link:
Opprett lenken til det aktiverte nettstedet:

```bash
sudo ln -s \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

If the default Nginx site is not required, remove it:
Hvis standard Nginx-nettstedet ikke er nødvendig, fjern det:

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/default
```

Do not remove other Nginx configurations belonging to unrelated applications.
Ikke fjern andre Nginx-konfigurasjoner som tilhører urelaterte applikasjoner.

---

# 37. Validate the Nginx Configuration
# 37. Valider Nginx-konfigurasjonen

Always test the configuration before reloading Nginx:
Test alltid konfigurasjonen før du laster Nginx på nytt:

```bash
sudo nginx -t
```

Expected:
Forventet:

```text
syntax is ok
test is successful
```

Only after a successful configuration test should Nginx be reloaded:
Først etter en vellykket konfigurasjonstest skal Nginx lastes på nytt:

```bash
sudo systemctl reload nginx
```

Verify the service:
Verifiser tjenesten:

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

Nginx must be running before continuing with HTTPS validation.
Nginx må kjøre før du fortsetter med HTTPS-valideringen.

---

# 38. Verify TLS Certificate Files
# 38. Verifiser TLS-sertifikatfilene

Confirm that the configured certificate files exist:
Bekreft at de konfigurerte sertifikatfilene finnes:

```bash
sudo ls -lh \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Verify permissions:
Verifiser tillatelsene:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

The private key should normally be:
Den private nøkkelen skal normalt ha:

```text
600
```

The certificate can normally be:
Sertifikatet kan normalt ha:

```text
644
```

Never print the private-key contents.
Skriv aldri ut innholdet i den private nøkkelen.

---

# 39. Verify the HTTPS Endpoint
# 39. Verifiser HTTPS-endepunktet

Test HTTPS locally:
Test HTTPS lokalt:

```bash
curl -I \
    https://LUMS-SERVER/
```

Replace `LUMS-SERVER` with the hostname covered by the server's TLS
certificate. Do not use `-k` for routine verification; it skips certificate
validation.

When the certificate is trusted by the system, use certificate verification:
Erstatt `LUMS-SERVER` med vertsnavnet som dekkes av serverens TLS-sertifikat.
Ikke bruk `-k` ved rutinemessig verifisering; det hopper over sertifikatvalidering.

Når sertifikatet er klarert av systemet, bruk sertifikatverifisering:

```bash
curl -I \
    https://LUMS-SERVER/
```

A successful response confirms that the request reaches the Nginx HTTPS endpoint.

The exact HTTP status depends on the requested route and authentication state.

The important requirement is that the TLS connection succeeds and the request reaches LUMS.
Et vellykket svar bekrefter at forespørselen når Nginx' HTTPS-endepunkt.

Den nøyaktige HTTP-statusen avhenger av den forespurte ruten og autentiseringstilstanden.

Det viktige kravet er at TLS-tilkoblingen lykkes og at forespørselen når LUMS.

---

# 40. Verify HTTP to HTTPS Redirect
# 40. Verifiser omdirigering fra HTTP til HTTPS

The HTTP listener must redirect clients to HTTPS.
HTTP-lytteren må omdirigere klienter til HTTPS.

Test:

```bash
curl -I \
    http://LUMS-SERVER/
```

Expected behavior:
Forventet oppførsel:

```text
HTTP/1.1 301 ...
Location: https://...
```

The LUMS application should not be operated through an unencrypted HTTP connection.

Do not permanently configure clients with certificate verification disabled merely because the initial certificate is not trusted.

Fix the trust configuration instead.
LUMS-applikasjonen bør ikke brukes over en ukryptert HTTP-tilkobling.

Ikke konfigurer klienter permanent med deaktivert sertifikatverifisering bare fordi det første sertifikatet ikke er klarert.

Rett heller opp klareringskonfigurasjonen.

---

# 41. Verify the External Network Path
# 41. Verifiser den eksterne nettverksbanen

Inspect the listening sockets:
Inspiser lyttende sockets:

```bash
sudo ss -lntp | grep -E ':80|:443|:5050|:5000'
```

The intended Arkitektur is:

```text
80
 â”‚
 â””â”€â”€ HTTP redirect
        â”‚
        â–¼
443
 â”‚
 â””â”€â”€ Nginx
        â”‚
        â–¼
127.0.0.1:5050
        â”‚
        â–¼
Docker :5000
```

Port `5050` must not be exposed to the LAN.

Port `5000` must not be exposed directly.

The Docker application port is an internal reverse-proxy endpoint.
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

# 42. Verify Security Headers
# 42. Verifiser sikkerhetshoder

Inspect the HTTPS response headers:
Inspiser HTTPS-svarhodene:

```bash
curl -I \
    https://LUMS-SERVER/
```

Review the returned headers rather than assuming that the security configuration is active.

Relevant security headers may include:
Gjennomgå de returnerte hodene i stedet for å anta at sikkerhetskonfigurasjonen er aktiv.

Relevante sikkerhetshoder kan omfatte:

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Content-Security-Policy
```

The exact headers depend on the current LUMS application and Nginx configuration.

If a required header is missing, inspect the effective Nginx configuration:
De nøyaktige hodene avhenger av den gjeldende LUMS-applikasjonen og Nginx-konfigurasjonen.

Hvis et påkrevd hode mangler, inspiser den effektive Nginx-konfigurasjonen:

```bash
sudo nginx -T
```

and the application configuration:
og applikasjonskonfigurasjonen:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Do not add security headers blindly without checking which layer is already responsible for them.
Ikke legg til sikkerhetshoder blindt uten å sjekke hvilket lag som allerede er ansvarlig for dem.

---

# 43. Verify Host Handling
# 43. Verifiser vertshåndtering

The production deployment should not expose the application through an unintended default Nginx site.

Review the active configuration:
Produksjonsdistribusjonen skal ikke eksponere applikasjonen via et utilsiktet standard Nginx-nettsted.

Gjennomgå den aktive konfigurasjonen:

```bash
sudo nginx -T
```

Check the enabled sites:
Kontroller de aktiverte nettstedene:

```bash
ls -la \
    /etc/nginx/sites-enabled/
```

The intended LUMS virtual host should be present.

The default site should not unexpectedly serve the LUMS application.

When using an IP address as the LUMS endpoint, ensure that the configured `server_name` and certificate match the actual deployment model.
Den tiltenkte LUMS-virtuelle verten skal være til stede.

Standardnettstedet skal ikke uventet servere LUMS-applikasjonen.

Når en IP-adresse brukes som LUMS-endepunkt, sørg for at den konfigurerte `server_name` og sertifikatet samsvarer med den faktiske distribusjonsmodellen.

---

# 44. Verify Docker Exposure Again
# 44. Verifiser Docker-eksponeringen på nytt

After Nginx is configured, confirm that the application remains localhost-only:
Etter at Nginx er konfigurert, bekreft at applikasjonen fortsatt kun er tilgjengelig på localhost:

```bash
sudo docker port lums
```

Expected:
Forventet:

```text
5000/tcp -> 127.0.0.1:5050
```

The reverse proxy does not require changing the Docker binding.

Do not change it to:
Den omvendte proxyen krever ingen endring av Docker-bindingen.

Ikke endre den til:

```text
0.0.0.0:5050
```

just because Nginx is listening on the network.

Nginx and Docker have deliberately separate exposure boundaries.
bare fordi Nginx lytter på nettverket.

Nginx og Docker har bevisst adskilte eksponeringsgrenser.

---

# 45. Create the Initial Administrator
# 45. Opprett den første administratoren

The initial administrator must be created using the current repository's administrator initialization mechanism.

Before running an initialization command, inspect the available repository implementation:
Den første administratoren må opprettes med initialiseringsmekanismen for administratorer i det gjeldende repositoriet.

Før du kjører en initialiseringskommando, inspiser den tilgjengelige implementasjonen i repositoriet:

```bash
cd /opt/lums-public
```

Review the security-related initialization files:
Gjennomgå de sikkerhetsrelaterte initialiseringsfilene:

```bash
find server \
    -maxdepth 1 \
    -type f \
    -iname '*security*' \
    -o -iname '*migration*'
```

Then inspect the current migration/initialization implementation before executing it.

For example:
Inspiser deretter den gjeldende migrerings-/initialiseringsimplementasjonen før du kjører den.

For eksempel:

```bash
sed -n '1,260p' \
    server/security_migration.py
```

Use the initialization procedure provided by the exact repository revision being deployed.

> [!IMPORTANT]
> Do not copy an administrator password into shell history or documentation.

The initial administrator must receive:
Bruk initialiseringsprosedyren som følger med den nøyaktige repositoriorevisjonen som distribueres.

> [!IMPORTANT]
> Ikke kopier et administratorpassord inn i skallhistorikk eller dokumentasjon.

Den første administratoren må få:

```text
role = administrator
```

The administrator account is required for the first web login and subsequent client administration.
Administratorkontoen kreves for den første webinnloggingen og den videre klientadministrasjonen.

---

# 46. Verify the Administrator Account
# 46. Verifiser administratorkontoen

After administrator initialization, verify the account without exposing authentication material.

A database inspection can be performed from the container:
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

Expected administrator properties include:
Forventede egenskaper for administratoren er blant annet:

```text
enabled = 1
role = administrator
```

Do not print:
Ikke skriv ut:

```text
password hashes
session data
client tokens
application secrets
```

---

# 47. Administrator Password
# 47. Administratorpassord

Use a unique administrator password.

The password should not be reused from:
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

The LUMS application stores passwords using the configured password-hashing mechanism.

Do not attempt to replace the application password hash manually in SQLite.

If the administrator password must be changed, use the supported application mechanism.
LUMS-applikasjonen lagrer passord ved hjelp av den konfigurerte mekanismen for passordhashing.

Ikke forsøk å erstatte applikasjonens passordhash manuelt i SQLite.

Hvis administratorpassordet må endres, bruk den støttede applikasjonsmekanismen.

---

# 48. First Web Login
# 48. Første webinnlogging

Open the LUMS HTTPS endpoint:
Åpne LUMS' HTTPS-endepunkt:

```text
https://LUMS-SERVER/
```

Log in with the administrator account.

After authentication, the administrator should have access to the administrative interface.

The administrator interface should provide access to the areas permitted by the current RBAC implementation.

At minimum, the administrator should be able to access:
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

# 49. Verify Administrator RBAC
# 49. Verifiser administrator-RBAC

After login, verify that administrative functions are available.

The administrator should be able to access user management.

The administrator should also be able to perform client-management operations permitted by the current implementation.

Server-side authorization remains the security boundary.

The browser interface is not trusted merely because an element is visible or hidden.
Etter innlogging, verifiser at de administrative funksjonene er tilgjengelige.

Administratoren skal ha tilgang til brukeradministrasjon.

Administratoren skal også kunne utføre klientadministrasjonsoperasjoner som den gjeldende implementasjonen tillater.

Autorisasjon på serversiden er fortsatt sikkerhetsgrensen.

Nettlesergrensesnittet er ikke pålitelig bare fordi et element er synlig eller skjult.

---

# 50. Create an Operator
# 50. Opprett en operatør

After the administrator account has been verified, create an operator account through the LUMS user-management interface.

The operator role is intended for operational update management.

An operator can access:
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

An operator must not be able to perform administrator-only functions such as:
En operatør skal ikke kunne utføre funksjoner som bare er forbeholdt administratorer, for eksempel:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

Verify the permissions using the application interface and, where appropriate, the API authorization behavior.
Verifiser tillatelsene via applikasjonsgrensesnittet og, der det er hensiktsmessig, via autorisasjonsoppførselen i API-et.

---

# 51. Create a Viewer
# 51. Opprett en Viewer

A Viewer account can be created when read-only access is required.

The Viewer role is intentionally restricted.

A Viewer can access:
En Viewer-konto kan opprettes når det kreves skrivebeskyttet tilgang.

Viewer-rollen er bevisst begrenset.

En Viewer har tilgang til:

```text
Clients
Installed software
```

The following areas must not be available to a Viewer:
Følgende områder skal ikke være tilgjengelige for en Viewer:

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

These restrictions are enforced server-side.

The interface may additionally hide unavailable functions.
Disse begrensningene håndheves på serversiden.

Grensesnittet kan i tillegg skjule utilgjengelige funksjoner.

---

# 52. Verify Viewer Isolation
# 52. Verifiser Viewer-isolasjon

Log in using a Viewer account and verify the visible interface.

The Viewer should not receive management controls.

The Viewer must not be able to bypass the UI and invoke protected endpoints directly.

An authorization failure should be returned for protected operations.

The expected principle is:
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

Never rely on JavaScript or hidden HTML elements as the only authorization mechanism.
Stol aldri på JavaScript eller skjulte HTML-elementer som eneste autorisasjonsmekanisme.

---

# 53. Verify Session and CSRF Protection
# 53. Verifiser økt- og CSRF-beskyttelse

After the first successful login, verify that the application uses its configured session and CSRF protections.

The installation should not disable CSRF protection to make API requests or browser actions work.

If a legitimate request fails with a CSRF error, inspect the application flow rather than disabling the protection.

Session-related behavior is documented in:
Etter den første vellykkede innloggingen, verifiser at applikasjonen bruker sine konfigurerte økt- og CSRF-beskyttelser.

Installasjonen skal ikke deaktivere CSRF-beskyttelse for å få API-forespørsler eller nettleserhandlinger til å fungere.

Hvis en legitim forespørsel feiler med en CSRF-feil, undersøk applikasjonsflyten i stedet for å deaktivere beskyttelsen.

Øktrelatert oppførsel er dokumentert i:

```text
docs/security.md
```

---

# 54. Verify Login Rate Limiting
# 54. Verifiser rategrense for innlogging

The current login protection uses persistent failure tracking.

The configured progression is:

```text
5 attempts  â†’ 30 seconds
6 attempts  â†’ 60 seconds
7 attempts  â†’ 120 seconds
8+ attempts â†’ 300 seconds
```

Successful authentication clears the applicable failure state.

Do not repeatedly trigger failed authentication against a production installation simply to test the mechanism.

Use the existing test suite for repeated automated validation.
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

# 55. Server Validation Checkpoint
# 55. Serverens valideringssjekkpunkt

At this stage, verify:
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

Only after the server passes these checks should Linux clients be installed.

The next section covers the Linux Agent, client configuration, TLS trust and systemd integration.
Først når serveren har bestått disse kontrollene, bør Linux-klienter installeres.

Neste kapittel dekker Linux-agenten, klientkonfigurasjon, TLS-klarering og systemd-integrasjon.

# 56. Linux Client Installation
# 56. Installasjon av Linux-klient

LUMS clients are Linux systems managed by the LUMS server.

A client installation consists of:

```text
Linux system
    â†“
LUMS Agent
    â†“
Client configuration
    â†“
Client token
    â†“
TLS trust
    â†“
systemd service
    â†“
Reporting timer
```

Update execution is handled separately by the execution watcher.

The current Agent version is:
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

The current Watcher version is:
Den nåværende Watcher-versjonen er:

```text
1.2.1
```

---

# 57. Supported Linux Clients
# 57. Støttede Linux-klienter

The current package-management implementations support:

```text
Debian / Ubuntu
    â†“
APT / dpkg

Arch Linux
    â†“
pacman
```

Verify the operating system before installing the client:
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

Verify the Arkitektur:
Verifiser arkitekturen:

```bash
uname -m
```

Verify systemd:
Verifiser systemd:

```bash
systemctl --version
```

The client requires a functioning systemd installation.
Klienten krever en fungerende systemd-installasjon.

---

# 58. Client Network Requirements
# 58. Nettverkskrav for klienten

The client must be able to reach the LUMS HTTPS endpoint.

Test basic network connectivity:
Klienten må kunne nå LUMS' HTTPS-endepunkt.

Test grunnleggende nettverkstilkobling:

```bash
ping LUMS-SERVER
```

A successful ping is not required when ICMP is blocked.

The important requirement is HTTPS connectivity.

Test the LUMS endpoint:
En vellykket ping er ikke påkrevd når ICMP er blokkert.

Det viktige kravet er HTTPS-tilkobling.

Test LUMS-endepunktet:

```bash
curl -I \
    https://LUMS-SERVER/
```

If the server uses a private CA, the client must trust that CA before continuing.

Do not disable TLS verification as a permanent workaround.
Hvis serveren bruker en privat CA, må klienten stole på denne CA-en før du fortsetter.

Ikke deaktiver TLS-verifisering som en permanent omvei.

---

# 59. Obtain the LUMS Agent
# 59. Hent LUMS Agent

The Agent source is included in the LUMS repository.

On the client, obtain the repository or otherwise transfer the required Agent files through the approved deployment method.

The relevant files are:
Agentens kildekode følger med i LUMS-repositoriet.

På klienten, hent repositoriet eller overfør de nødvendige agentfilene på annen måte via den godkjente distribusjonsmetoden.

De relevante filene er:

```text
agent/agent.py
agent/watcher.py
agent/package_manager.py
```

The recommended installation directory is:
Den anbefalte installasjonskatalogen er:

```text
/opt/lums-agent
```

Create it:
Opprett den:

```bash
sudo install -d -m 755 \
    /opt/lums-agent
```

---

# 60. Install the Agent Files
# 60. Installer agentfilene

From the LUMS repository:
Fra LUMS-repositoriet:

```bash
cd /opt/lums-public
```

Install the Agent:
Installer agenten:

```bash
sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py
```

Install the Watcher:
Installer Watcher:

```bash
sudo cp \
    agent/watcher.py \
    /opt/lums-agent/watcher.py
```

Install the package-manager abstraction:
Installer pakkehåndteringsabstraksjonen:

```bash
sudo cp \
    agent/package_manager.py \
    /opt/lums-agent/package_manager.py
```

Verify:
Verifiser:

```bash
ls -lh \
    /opt/lums-agent/
```

The directory should contain the installed Agent components.
Katalogen skal inneholde de installerte agentkomponentene.

---

# 61. Verify Agent Versions
# 61. Verifiser agentversjonene

Verify the installed Agent version:
Verifiser den installerte agentversjonen:

```bash
grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/agent.py
```

The current version is:
Den nåværende versjonen er:

```text
1.7.0
```

Verify the Watcher:
Verifiser Watcher:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

The current version is:
Den nåværende versjonen er:

```text
1.2.1
```

If the installed versions do not match the intended deployment revision, stop and verify that the correct repository revision is being used.
Hvis de installerte versjonene ikke samsvarer med den tiltenkte distribusjonsrevisjonen, stopp og verifiser at riktig repositoriorevisjon brukes.

---

# 62. Install systemd Service Files
# 62. Installer systemd-tjenestefiler

The Agent and Watcher use separate systemd services.

Install the Agent service:
Agenten og Watcher bruker separate systemd-tjenester.

Installer agenttjenesten:

```bash
sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
```

Install the Watcher service:
Installer Watcher-tjenesten:

```bash
sudo cp \
    agent/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent-watcher.service
```

Install the reporting timer:
Installer rapporteringstimeren:

```bash
sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer
```

Install the Watcher timer:
Installer Watcher-timeren:

```bash
sudo cp \
    agent/lums-agent-watcher.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Reload systemd:
Last systemd på nytt:

```bash
sudo systemctl daemon-reload
```

---

# 63. Verify the systemd Units
# 63. Verifiser systemd-enhetene

Inspect the Agent service:
Inspiser agenttjenesten:

```bash
systemctl cat \
    lums-agent.service
```

Inspect the Watcher service:
Inspiser Watcher-tjenesten:

```bash
systemctl cat \
    lums-agent-watcher.service
```

Inspect the Agent timer:
Inspiser agenttimeren:

```bash
systemctl cat \
    lums-agent.timer
```

Inspect the Watcher timer:
Inspiser Watcher-timeren:

```bash
systemctl cat \
    lums-agent-watcher.timer
```

The units should reference the installed files under:
Enhetene skal referere til de installerte filene under:

```text
/opt/lums-agent/
```

Do not enable the timers until the client configuration and authentication have been completed.
Ikke aktiver timerne før klientkonfigurasjonen og autentiseringen er fullført.

---

# 64. Create the Client Configuration
# 64. Opprett klientkonfigurasjonen

The client configuration is stored outside the Git repository.

Use:
Klientkonfigurasjonen lagres utenfor Git-repositoriet.

Bruk:

```text
/etc/default/lums-agent
```

Create the file:
Opprett filen:

```bash
sudo install -m 600 /dev/null \
    /etc/default/lums-agent
```

The configuration contains the LUMS server endpoint and the client token.

Example structure:
Konfigurasjonen inneholder LUMS-serverens endepunkt og klienttokenet.

Eksempelstruktur:

```text
LUMS_BASE=https://LUMS-SERVER
LUMS_TOKEN=<CLIENT-TOKEN>
```

Replace:
Erstatt:

```text
LUMS-SERVER
```

with the actual LUMS server endpoint.

Replace:
med det faktiske LUMS-serverendepunktet.

Erstatt:

```text
<CLIENT-TOKEN>
```

with the token assigned to this client.

Protect the configuration:
med tokenet som er tildelt denne klienten.

Beskytt konfigurasjonen:

```bash
sudo chmod 600 \
    /etc/default/lums-agent
```

Verify without displaying its contents:
Verifiser uten å vise innholdet:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Expected:
Forventet:

```text
600
```

---

# 65. Client Tokens
# 65. Klienttokener

Each LUMS client has its own authentication token.

The token is used as:
Hver LUMS-klient har sitt eget autentiseringstoken.

Tokenet brukes som:

```text
Authorization: Bearer <CLIENT-TOKEN>
```

The server does not need the original token value after provisioning.

The server stores a cryptographic representation of the token for validation.

This means that client credentials should be treated like passwords.

Never place a real token into:
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

# 66. Provision the Client Token
# 66. Klargjør klienttokenet

Create or provision the client from the LUMS administrator interface according to the current client-management workflow.

The resulting client token must be transferred to the intended client through a secure channel.

Store it only in:
Opprett eller klargjør klienten fra LUMS' administratorgrensesnitt i henhold til den gjeldende arbeidsflyten for klientadministrasjon.

Det resulterende klienttokenet må overføres til den tiltenkte klienten via en sikker kanal.

Lagre det bare i:

```text
/etc/default/lums-agent
```

on the client.

Do not reuse one client token across multiple machines.

The intended relationship is:

```text
Client A
    â†“
Token A

Client B
    â†“
Token B

Client C
    â†“
Token C
```

A compromised token should therefore identify only its associated client.
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

# 67. Client Token Rotation
# 67. Rotasjon av klienttoken

Client tokens can be rotated by an administrator.

The rotation flow is:

```text
Current token
     â†“
Administrator rotates token
     â†“
Old token invalidated
     â†“
New token issued
     â†“
Client configuration updated
```

After updating the client configuration, run the Agent manually to verify that authentication succeeds.

A rotated token must not continue to be accepted indefinitely.
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

# 68. TLS Trust
# 68. TLS-klarering

The LUMS Agent communicates with the server over HTTPS.

Certificate verification must remain enabled.

For a publicly trusted certificate, the normal operating-system trust store is sufficient.

For a private laboratory CA, install the CA certificate on the client.

Do not solve certificate problems by disabling verification.

The correct solution is to make the client trust the intended certificate authority.
LUMS Agent kommuniserer med serveren over HTTPS.

Sertifikatverifisering må forbli aktivert.

For et offentlig klarert sertifikat er operativsystemets vanlige klareringslager tilstrekkelig.

For en privat laboratorie-CA, installer CA-sertifikatet på klienten.

Ikke løs sertifikatproblemer ved å deaktivere verifisering.

Den riktige løsningen er å få klienten til å stole på den tiltenkte sertifiseringsinstansen.

---

# 69. Debian / Ubuntu TLS Trust
# 69. TLS-klarering på Debian / Ubuntu

On Debian-family systems, a private CA can be installed into the system trust store.

Copy the CA certificate:
På Debian-baserte systemer kan en privat CA installeres i systemets klareringslager.

Kopier CA-sertifikatet:

```bash
sudo cp \
    lums-ca.crt \
    /usr/local/share/ca-certificates/lums-ca.crt
```

Update the trust store:
Oppdater klareringslageret:

```bash
sudo update-ca-certificates
```

Verify that the certificate is accepted:
Verifiser at sertifikatet blir akseptert:

```bash
curl -I \
    https://LUMS-SERVER/
```

If the command succeeds without `-k`, the system trust configuration is working.
Hvis kommandoen lykkes uten `-k`, fungerer systemets klareringskonfigurasjon.

---

# 70. Arch Linux TLS Trust
# 70. TLS-klarering på Arch Linux

On Arch Linux, install the private CA using the system's configured trust-store mechanism.

After installing the CA, update the trust database according to the active trust-store configuration.

Verify:
På Arch Linux installerer du den private CA-en via systemets konfigurerte mekanisme for klareringslager.

Etter at CA-en er installert, oppdater klareringsdatabasen i henhold til den aktive konfigurasjonen av klareringslageret.

Verifiser:

```bash
curl -I \
    https://LUMS-SERVER/
```

The connection should succeed without:
Tilkoblingen skal lykkes uten:

```text
-k
```

Do not permanently configure the Agent to ignore certificate verification.
Ikke konfigurer agenten permanent til å ignorere sertifikatverifisering.

---

# 71. Verify the Package Manager
# 71. Verifiser pakkehåndtereren

The Agent detects the supported package-management family.
Agenten oppdager den støttede pakkehåndteringsfamilien.

For Debian/Ubuntu:

```bash
command -v apt
```

and:
og:

```bash
command -v dpkg-query
```

Verify installed packages:
Verifiser installerte pakker:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    | head
```

Verify available updates:
Verifiser tilgjengelige oppdateringer:

```bash
apt list --upgradable
```

For Arch Linux:

```bash
command -v pacman
```

Verify installed packages:
Verifiser installerte pakker:

```bash
pacman -Q | head
```

Verify available updates:
Verifiser tilgjengelige oppdateringer:

```bash
pacman -Qu
```

The package-manager abstraction uses the appropriate implementation automatically.
Pakkehåndteringsabstraksjonen bruker automatisk riktig implementasjon.

---

# 72. Verify Agent Permissions
# 72. Verifiser agenttillatelser

Inspect the installation directory:
Inspiser installasjonskatalogen:

```bash
ls -ld \
    /opt/lums-agent
```

Inspect the installed files:
Inspiser de installerte filene:

```bash
ls -lh \
    /opt/lums-agent/
```

The Agent does not need write access to its own source directory.

The client configuration remains protected separately:
Agenten trenger ikke skrivetilgang til sin egen kildekatalog.

Klientkonfigurasjonen forblir beskyttet separat:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Expected:
Forventet:

```text
600
```

The Agent requires sufficient system privileges to inspect package state and perform package operations.

The exact runtime privileges are defined by the installed systemd service.
Agenten krever tilstrekkelige systemrettigheter for å inspisere pakketilstand og utføre pakkeoperasjoner.

De nøyaktige kjøretidsrettighetene er definert av den installerte systemd-tjenesten.

---

# 73. Verify the Agent Configuration
# 73. Verifiser agentkonfigurasjonen

Before starting the service, verify that the configuration file exists:
Før du starter tjenesten, verifiser at konfigurasjonsfilen finnes:

```bash
sudo test -r \
    /etc/default/lums-agent \
    && echo "agent configuration: OK"
```

Do not print the contents of the configuration file.

Verify that the required variables exist without exposing the token:
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

The token value itself must not be printed.
Selve tokenverdien må ikke skrives ut.

---

# 74. Test the Agent Manually
# 74. Test agenten manuelt

Before enabling the timer, execute the Agent once manually:
Før du aktiverer timeren, kjør agenten én gang manuelt:

```bash
sudo systemctl start \
    lums-agent.service
```

Check the result:
Kontroller resultatet:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

The Agent is a one-shot service.

After successful completion, it may show:
Agenten er en engangstjeneste (one-shot).

Etter vellykket fullføring kan den vise:

```text
Active: inactive (dead)
```

This is normal.

The important result is:
Dette er normalt.

Det viktige resultatet er:

```text
status=0/SUCCESS
```

Inspect the journal:
Inspiser journalen:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 75. Verify the First Client Report
# 75. Verifiser den første klientrapporten

A successful Agent run should report the client to the LUMS server.

The complete path is:

```text
Agent
   â†“
HTTPS
   â†“
Nginx
   â†“
LUMS API
   â†“
Bearer authentication
   â†“
Client lookup
   â†“
Report accepted
```

Inspect the server logs when required:
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

The client should appear in the LUMS web interface after a successful report.

The local service being successful is not sufficient by itself.

The server must accept the report.
Klienten skal vises i LUMS' webgrensesnitt etter en vellykket rapport.

At den lokale tjenesten lykkes er ikke tilstrekkelig i seg selv.

Serveren må godta rapporten.

---

# 76. Verify the Client in the Web Interface
# 76. Verifiser klienten i webgrensesnittet

Log in as an administrator or operator.

Open the client Oversikt.

The new client should report information such as:
Logg inn som administrator eller operatør.

Åpne klientoversikten.

Den nye klienten skal rapportere informasjon som:

```text
Hostname
IP address
Operating system
Arkitektur
Architecture
Agent version
Last report
Installed packages
Available updates
```

The reported information belongs to that client.

A client must not be able to access another client's resources.
Den rapporterte informasjonen tilhører den klienten.

En klient må ikke kunne få tilgang til en annen klients ressurser.

---

# 77. Enable the Reporting Timer
# 77. Aktiver rapporteringstimeren

Only after the manual Agent run succeeds should the reporting timer be enabled:
Først etter at den manuelle agentkjøringen er vellykket, skal rapporteringstimeren aktiveres:

```bash
sudo systemctl enable --now \
    lums-agent.timer
```

Check:
Kontroller:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Inspect the schedule:
Inspiser timeplanen:

```bash
systemctl list-timers \
    lums-agent.timer \
    --no-pager
```

The timer periodically starts:
Timeren starter periodisk:

```text
lums-agent.service
```

The service itself remains a one-shot unit.

Therefore, it is normal for the service to return to:
Selve tjenesten forblir en engangsenhet.

Det er derfor normalt at tjenesten går tilbake til:

```text
inactive (dead)
```

between timer executions.
mellom timerkjøringene.

---

# 78. Verify Scheduled Reporting
# 78. Verifiser planlagt rapportering

After enabling the timer, inspect the next scheduled execution:
Etter at timeren er aktivert, inspiser neste planlagte kjøring:

```bash
systemctl list-timers \
    --all \
    --no-pager | grep lums-agent
```

After the timer has executed, inspect:
Etter at timeren har kjørt, inspiser:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Verify the corresponding client report in LUMS.

A healthy reporting cycle is:

```text
Timer
  â†“
Agent service
  â†“
System inventory
  â†“
Package inventory
  â†“
Update detection
  â†“
HTTPS report
  â†“
LUMS database
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

# 79. Client Installation Checkpoint
# 79. Sjekkpunkt for klientinstallasjon

Before installing the execution watcher, verify:
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

Do not proceed to update-job testing until the reporting path is working.

The next section installs and validates the execution watcher.
Ikke gå videre til testing av oppdateringsjobber før rapporteringsbanen fungerer.

Neste kapittel installerer og validerer utføringsovervåkeren.

# 80. Install the Execution Watcher
# 80. Installer utføringsovervåkeren (Watcher)

The LUMS execution watcher is responsible for detecting and executing pending update jobs on the client.

The Arkitektur separates reporting from execution:

```text
Reporting
    â”‚
    â–¼
lums-agent.service
    â”‚
    â””â”€â”€ system inventory / update detection

Execution
    â”‚
    â–¼
lums-agent-watcher.service
    â”‚
    â””â”€â”€ pending update jobs
```

This separation allows regular client reporting to continue independently from update execution.
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

# 81. Verify the Watcher Installation
# 81. Verifiser Watcher-installasjonen

Verify that the Watcher is present:
Verifiser at Watcher er til stede:

```bash
ls -lh \
    /opt/lums-agent/watcher.py
```

Verify the installed version:
Verifiser den installerte versjonen:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

The current Watcher version is:
Den nåværende Watcher-versjonen er:

```text
1.2.1
```

---

# 82. Verify the Watcher Service
# 82. Verifiser Watcher-tjenesten

Inspect the systemd unit:
Inspiser systemd-enheten:

```bash
systemctl cat \
    lums-agent-watcher.service
```

The service must reference:
Tjenesten må referere til:

```text
/opt/lums-agent/watcher.py
```

Verify the unit is known to systemd:
Verifiser at enheten er kjent for systemd:

```bash
systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

The service may be inactive when no execution has been triggered.

This is not by itself an error.
Tjenesten kan være inaktiv når ingen kjøring er utløst.

Dette er ikke i seg selv en feil.

---

# 83. Verify the Watcher Timer
# 83. Verifiser Watcher-timeren

Before enabling the Watcher timer, verify that:

- `/etc/default/lums-agent` exists and contains the correct client configuration.
- The LUMS server endpoint and client token are configured correctly.
- A manual Agent run succeeded and the server accepted the client report.
- Both Watcher unit files were installed from the repository.

Do not enable the timer while authentication or reporting is failing.


Inspect the timer:
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

Enable the timer only after verifying all prerequisites above:
Aktiver timeren først etter at alle forutsetningene ovenfor er verifisert:

```bash
sudo systemctl enable --now \
    lums-agent-watcher.timer
```

Verify:
Verifiser:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Inspect the next scheduled execution:
Inspiser neste planlagte kjøring:

```bash
systemctl list-timers \
    lums-agent-watcher.timer \
    --no-pager
```

---

# 84. Understand Idle-Aware Execution
# 84. Forstå hviletilstandsbevisst kjøring

The Watcher can use client idle information before executing update jobs.

The intended flow is:

```text
Pending job
    â”‚
    â–¼
Watcher
    â”‚
    â–¼
Idle detection
    â”‚
    â”œâ”€â”€ idle state available
    â”‚       â”‚
    â”‚       â–¼
    â”‚   idle threshold
    â”‚       â”‚
    â”‚       â–¼
    â”‚   execute when allowed
    â”‚
    â””â”€â”€ idle state unavailable
            â”‚
            â–¼
        use configured
        fallback behavior
```
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

Idle detection must never be interpreted as authentication or authorization.

It is an execution scheduling mechanism only.
Registrering av hviletilstand må aldri tolkes som autentisering eller autorisasjon.

Det er utelukkende en mekanisme for planlegging av kjøring.

---

# 85. Verify Idle Detection
# 85. Verifiser registrering av hviletilstand

Run the idle detection path manually through the installed Agent/Watcher implementation.

Inspect the resulting service journal:
Kjør banen for hviletilstandsregistrering manuelt gjennom den installerte Agent-/Watcher-implementasjonen.

Inspiser den resulterende tjenestejournalen:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

If the platform does not provide the required idle information, the client may report idle detection as unavailable.

This is not automatically a failure.

The important distinction is:
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

The client must not be assumed to be idle merely because no idle information was returned.

---

# 86. Optional Telemetry System Installation

Telemetry is an optional component that collects CPU, memory, and network metrics from managed clients.

It is completely separate from the Agent and Watcher and is not required for update management.

Telemetry uses the same client authentication (LUMS_TOKEN) as the Agent but submits to a different endpoint.

If telemetry is not needed, proceed directly to section 87.

---

# 87. Install the Telemetry Agent

The telemetry agent is included in the LUMS repository.

From the repository:

```bash
cd /opt/lums-public
```

Install the telemetry agent:

```bash
sudo cp \
    agent/telemetry.py \
    /opt/lums-agent/telemetry.py
```

Verify:

```bash
ls -lh \
    /opt/lums-agent/telemetry.py
```

Verify the Agent version:

```bash
grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/telemetry.py
```

The current telemetry agent version is:

```text
1.1.0
```

The telemetry agent requires only the Python 3 standard library.

---

# 88. Install Telemetry systemd Units

Install the telemetry service:

```bash
sudo cp \
    agent/lums-telemetry.service \
    /etc/systemd/system/lums-telemetry.service
```

Install the telemetry timer:

```bash
sudo cp \
    agent/lums-telemetry.timer \
    /etc/systemd/system/lums-telemetry.timer
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Verify the units:

```bash
systemctl cat \
    lums-telemetry.service
```

```bash
systemctl cat \
    lums-telemetry.timer
```

---

# 89. Telemetry Configuration

The telemetry agent uses environment variables from the same `/etc/default/lums-agent` file.

The required variables are:

* `LUMS_BASE`: Server URL (already configured for the main Agent)
* `LUMS_TOKEN`: Client token (already configured for the main Agent)

Optional variable:

* `LUMS_CA_FILE`: Path to CA certificate (only needed if using a private CA)

The telemetry agent reuses the same client authentication as the main Agent.

No additional credentials are required.

Verify the configuration exists:

```bash
sudo test -r \
    /etc/default/lums-agent \
    && echo "configuration: OK"
```

For a private certificate authority, install and configure the CA certificate:

```bash
export LUMS_CA_FILE=/etc/lums/ca.crt
sudo sh -c "echo 'LUMS_CA_FILE=$LUMS_CA_FILE' >> /etc/default/lums-agent"
```

Then copy the CA certificate:

```bash
sudo cp \
    /path/to/ca.crt \
    /etc/lums/ca.crt
```

Protect the file:

```bash
sudo chmod 644 \
    /etc/lums/ca.crt
```

---

# 90. Test the Telemetry Agent Manually

Before enabling the timer, execute the telemetry agent once:

```bash
sudo systemctl start \
    lums-telemetry.service
```

Check the result:

```bash
sudo systemctl status \
    lums-telemetry.service \
    --no-pager
```

Inspect the journal:

```bash
sudo journalctl \
    -u lums-telemetry.service \
    -n 50 \
    --no-pager
```

Look for successful submission messages or any error details.

A successful submission shows a `204 No Content` response.

---

# 91. Enable the Telemetry Timer

Only after the manual telemetry run succeeds, enable the timer:

```bash
sudo systemctl enable --now \
    lums-telemetry.timer
```

Verify:

```bash
sudo systemctl status \
    lums-telemetry.timer \
    --no-pager
```

Inspect the schedule:

```bash
systemctl list-timers \
    lums-telemetry.timer \
    --no-pager
```

The timer is configured to execute approximately every 5 seconds.

---

# 92. Verify Telemetry Submission

After the timer is running, check for successful submissions:

```bash
sudo journalctl \
    -u lums-telemetry.service \
    -n 100 \
    --no-pager
```

Then verify that samples appear in the LUMS `/health` dashboard:

1. Log in to LUMS
2. Navigate to `/health` or the Fleet Health Dashboard
3. Find this client in the client list
4. Verify that CPU, memory, and (if available) network data appears

If samples do not appear, inspect:

* Server logs: `sudo docker logs --tail 100 lums`
* Telemetry service logs: `sudo journalctl -u lums-telemetry.service -n 200 --no-pager`
* Network connectivity to server
* Client authentication token
* TLS certificate trust

For detailed telemetry troubleshooting, see `troubleshooting.md` section 11.5.

---

# 93. Optional Telemetry Checkpoint

If telemetry is installed, verify:

```text
[ ] Telemetry agent installed
[ ] Telemetry service unit installed
[ ] Telemetry timer unit installed
[ ] Configuration variables exist
[ ] Manual telemetry test succeeds
[ ] Telemetry timer enabled
[ ] Telemetry submissions appear in logs
[ ] Samples visible in /health dashboard
[ ] CPU data displayed correctly
[ ] Memory data displayed correctly
[ ] Network data displayed (if enabled)
```

If telemetry is not needed, proceed directly to section 94.

---

# 94. Create a Controlled Test Update Job

Do not begin installation testing with a large system update.

Use a small, known package for the first test.

The package should:
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

Example test package:
Eksempel på testpakke:

```text
sl
```

Before creating the job, verify whether it is already installed:
Før du oppretter jobben, verifiser om den allerede er installert:

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

For Arch Linux, use a package that is available in the configured repositories and is suitable for a reversible test.

Do not blindly use `sl` on every distribution.
For Arch Linux, bruk en pakke som er tilgjengelig i de konfigurerte repositoriene og egner seg for en reversibel test.

Ikke bruk `sl` blindt på alle distribusjoner.

---

# 87. Verify Package Search
# 87. Verifiser pakkesøk

Use the LUMS Package Management interface to search for the selected package.

The search flow is:

```text
Browser
   â†“
LUMS API
   â†“
Package Search Request
   â†“
Client
   â†“
APT / pacman
   â†“
Package Search Result
   â†“
LUMS API
   â†“
Browser
```

Verify that the result contains the expected information:
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

For Arch Linux, repository information may also be returned.
For Arch Linux kan repositorieinformasjon også bli returnert.

---

# 88. Package Management Permissions
# 88. Tillatelser for pakkehåndtering

Package management is restricted by RBAC.
Pakkehåndtering er begrenset av RBAC.

Administrator:

```text
Allowed
```

Operator:
Operatør:

```text
Allowed
```

Viewer:

```text
Not allowed
```

A Viewer must not be able to execute package installation or removal by directly calling the API.

The browser interface hiding the feature is only an additional usability restriction.

The server-side authorization is the actual security boundary.

---

# 89. Test Package Installation

Create an installation job through the LUMS interface.

The logical operation is:
En Viewer må ikke