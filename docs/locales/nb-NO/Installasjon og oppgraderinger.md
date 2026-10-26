# LUMS-installasjonsveiledning

## Linux Update Management Server

**Prosjekt:** LUMS

**Slagord:** Linux Update Management without the noise.

**Repositorium:** `NovaForgeCtrl/LUMS`

Denne veiledningen beskriver installasjon, sikkerhetskontroller, klientoppsett, verifisering, sikkerhetskopiering, oppgradering og avinstallering av LUMS. Den er ikke et skript som bør kjøres ukritisk: vertsnavn, TLS-sertifikat, hemmelighetsfil, sikkerhetskopimål, nettverk og database varierer fra installasjon til installasjon. Les trinnene, erstatt plassholdere og kontroller lagringsbaner før du utfører kommandoer.

Den engelske originalen er den tekniske kilden og inneholder alle detaljerte kontroller og avsnitt: [install.md](../../../install.md). Følg den engelske originalen hvis en prosedyre her mangler detaljer eller avviker.

## Kom i gang: forstå installasjonen

En komplett installasjon består av:

* **LUMS-server:** webgrensesnitt og API i en Docker-container.
* **Nginx:** tar imot eksterne HTTPS-tilkoblinger og videresender dem lokalt til containeren.
* **Datavolum:** inneholder SQLite-databasen og skal bevares gjennom oppgraderinger.
* **Hemmelighetsfil:** beskytter blant annet applikasjonsøkter. Den skal aldri ligge i Git-repositoriet, et Docker-bilde eller en chatmelding.
* **LUMS Agent og Watcher:** installeres separat på administrerte Linux-klienter. En server alene oppdaterer ikke klienter.

| Begrep | Betydning |
| --- | --- |
| Terminal / skall | Tekstvindu der du skriver Linux-kommandoer. |
| `sudo` | Kjører den etterfølgende kommandoen med administratorrettigheter. Linux kan be om passord. |
| Vert | Linux-maskinen som kjører Docker og LUMS-serveren. |
| Container | Isolert prosess som kjører LUMS-webapplikasjonen. |
| Image | Forberedt mal som Docker bruker for å starte en container. |
| Volum | Vedvarende Docker-lagring som består når en container erstattes. |
| Plassholder | Tekst, for eksempel `LUMS-SERVER`, som må erstattes med den faktiske verdien. |

## Kjør bare testene (installerer ikke en server)

Disse trinnene passer for Debian 13 når du vil hente kildekoden og kjøre testene lokalt. De oppretter **ikke** en produksjonsserver som er tilgjengelig over nettverket, og installerer ikke en agent på en annen maskin. `sudo` trengs bare for å installere Debian-pakker.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
git clone https://github.com/NovaForgeCtrl/LUMS.git ~/LUMS
cd ~/LUMS
python3 -m venv .venv-test
./.venv-test/bin/python -m pip install -r server/requirements.txt -r requirements-dev.txt
./.venv-test/bin/pytest -q
```

`apt update` oppdaterer pakkelistene; den oppgraderer ikke all installert programvare. Det separate Python-miljøet `.venv-test` holder testavhengighetene adskilt fra resten av systemet. En vellykket testkjøring avsluttes med kode `0`; antallet tester kan endres etter hvert som prosjektet vokser. Hvis opprettelsen av miljøet mislykkes, kontroller at `python3-venv` er installert. Ved testfeil må du lagre hele feilmeldingen og lese [feilsøkingsveiledningen](Feilsøking.md); ikke slett produksjonsdata.

For en reell installasjon fortsetter du med prosedyrene nedenfor og leser sikkerhets- og sikkerhetskopiinstruksjonene først. Hvis LUMS allerede kjører, bruker du oppgraderingsprosedyren i [administrasjonsveiledningen](<Administrasjon og sikkerhetskopier.md>), ikke førstegangsinstallasjonen.

## Arkitektur og sikkerhetsmodell

Serveren tilbyr webadministrasjon, klientadministrasjon og autentisering, programvareoversikt, rapportering av tilgjengelige oppdateringer, pakkesøk og pakkeoperasjoner, jobbstyring, resultatkontroll, oppdateringshistorikk, RBAC, revisjonslogging og vedvarende SQLite-data.

Linux-klientene samler systeminformasjon og installerte pakker, oppdager tilgjengelige oppdateringer, utfører pakkeoperasjoner og jobber, håndterer inaktiv tilstand, gjenoppretting av jobber, omstartspåvisning og resultatrapportering. Støttede pakkesystemer:

```text
Debian / Ubuntu
    └── APT / dpkg

Arch Linux
    └── pacman
```

Produksjonsserveren bruker Nginx som HTTPS-inngang og en herdet Docker-container. Flask/Gunicorn-applikasjonen skal ikke eksponeres direkte på LAN-et. Containeren er tilgjengelig bare på `127.0.0.1:5050` og videresender til containerport `5000`; Nginx håndterer eksterne tilkoblinger på port `443`.

Sikkerhetsgrunnlaget omfatter HTTPS, klientautentisering med bearer-token, rollebasert tilgangskontroll, CSRF-beskyttelse, revisjonslogging, skrivebeskyttet rotfilsystem, droppede Linux-capabilities, `no-new-privileges`, ikke-root-applikasjonsbruker, localhost-binding, vedvarende Docker-volum og skrivebeskyttet montering av hemmeligheten. Containeren skal ikke kjøre i privileged-modus. Applikasjonsbrukeren er `lums` med UID `10001`.

### Roller

LUMS tilbyr rollene `administrator`, `operator` og `viewer`. Administratorer kan administrere brukere, roller, klienter og token i tillegg til operativ drift. Operatører utfører oppdaterings- og systemarbeid, men administrerer ikke brukere eller klientregistrering som standard. Visere har begrenset, skrivebeskyttet tilgang til klienter og installert programvare. Serveren håndhever de lagrede tillatelsene; skjuling av brukergrensesnittelementer er ikke en sikkerhetsgrense.

## Krav

### LUMS-server

Linux-vert med:

```text
Docker Engine
Git
Nginx
OpenSSL
Nettverkstilkobling
Vedvarende lagring
```

Det må være nok lagringsplass til Docker-images, SQLite-database, applikasjonsdata, logger og sikkerhetskopier.

### Linux-klienter

Administrerte klienter trenger:

```text
Python 3
systemd
Støttet pakkebehandler
Nettverkstilgang til LUMS-serveren
Gyldig klienttoken
Betrodd TLS-sertifikat
```

Klienten må nå serverens HTTPS-endepunkt. Kontroller klientens distribusjon med `cat /etc/os-release`, arkitektur med `uname -m` og systemd med `systemctl --version`.

## Forbered serververten

Anbefalt plassering av repositoriet:

```text
/opt/lums-public/
```

Eksempel på kloning og kontroll av arbeidsområdet:

```bash
sudo mkdir -p /opt
cd /opt
sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public
cd /opt/lums-public
git status
git log -1 --oneline --decorate
```

Registrer den nøyaktige committen som brukes. Ikke bygg produksjonsimages fra et ukjent eller ubekreftet arbeidsområde.

Kontroller før bygging at repositoriet ikke inneholder produksjonsdatabaser, private TLS-nøkler, applikasjonshemmeligheter, klienttoken, sikkerhetskopier eller kjøretidslogger:

```bash
git status --short
git status --ignored --short
```

Gjennomgå også de stagede filene nøye før en endring committes.

Opprett konfigurasjonskatalogene utenfor repositoriet:

```bash
sudo install -d -m 700 /etc/lums
sudo install -d -m 700 /etc/lums/secrets
sudo install -d -m 700 /etc/lums/tls
```

Generer applikasjonshemmeligheten på verten, ikke i Docker-imaget:

```bash
sudo sh -c 'umask 077 && openssl rand -hex 32 > /etc/lums/secrets/lums_secret'
```

Hemmelighetsfilen ligger på `/etc/lums/secrets/lums_secret`. TLS-materialet ligger under `/etc/lums/tls/`; sertifikatbanen er `/etc/lums/tls/lums.crt`, og den private nøkkelen er `/etc/lums/tls/lums.key`. Beskytt kataloger og filer, og skriv aldri ut privatnøkkelens innhold.

## Bygg server-imaget og opprett datavolumet

Kjør testene før du bygger produksjonsimaget:

```bash
cd /opt/lums-public
./.venv-test/bin/pytest -q
```

Bygg og undersøk imaget:

```bash
sudo docker build \
    -t lums:latest \
    .
sudo docker image ls lums
sudo docker image inspect lums:latest
sudo docker image inspect \
    lums:latest \
    --format '{{.Config.User}}'
```

Applikasjonen skal kjøre som `lums`, uten root-rettigheter i normal drift. Produksjonsimaget bygger på et låst Python 3.13 slim-baseimage og bruker låste produksjonsavhengigheter der det er nødvendig. Ikke legg hemmeligheter, sertifikater eller produksjonsdatabaser i Docker-byggkonteksten.

Opprett og kontroller det vedvarende datavolumet:

```bash
sudo docker volume create lums-data
sudo docker volume inspect lums-data
sudo docker volume ls | grep lums-data
```

Volumet monteres på `/var/lib/lums`, der databasen ligger på `/var/lib/lums/lums.db`. Containerfilsystemet er ikke vedvarende lagring. **Fjern aldri `lums-data` under en normal applikasjonsoppgradering.**

## Start den herdede servercontaineren

Kontroller først at det ikke allerede kjører en container med navnet `lums`:

```bash
sudo docker ps \
    --filter name=lums
```

Start containeren med produksjonens sikkerhetsinnstillinger:

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

Hemmeligheten monteres skrivebeskyttet, SQLite-databasen lagres i det vedvarende volumet, rotfilsystemet er skrivebeskyttet, alle Linux-capabilities droppes, og `no-new-privileges` hindrer prosesser i å skaffe seg flere privilegier.

Kontroller containeren og loggene:

```bash
sudo docker ps \
    --filter name=lums
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
sudo docker logs \
    --tail 100 \
    lums
```

Forventet tilstand er `running`. Undersøk oppstartsfeil før du fortsetter.

Kontroller den effektive sikkerhetskonfigurasjonen:

```bash
sudo docker inspect lums \
    --format='User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}'
```

Forventet grunnlag:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Kontroller porten:

```bash
sudo docker port lums
sudo ss -lntp | grep -E ':5050|:5000'
```

Port `5000` må ikke publiseres direkte, og `5050` skal ikke bindes til `0.0.0.0`. Bare localhost-porten `127.0.0.1:5050` er forventet.

## Initialiser administratorkontoen

Initialiseringsmekanismen kan variere med repositorierevisjonen. Før du kjører et initierings- eller migreringskommando, gå til `/opt/lums-public`, undersøk de gjeldende sikkerhets- og migreringsfilene og følg instruksjonene i nøyaktig den revisjonen som skal distribueres:

```bash
cd /opt/lums-public
find server \
    -maxdepth 1 \
    -type f \
    -iname '*security*' \
    -o -iname '*migration*'
sed -n '1,260p' \
    server/security_migration.py
```

Ikke kopier et administratørpassord inn i skallhistorikken eller dokumentasjonen. Den første kontoen skal ha `role = administrator`, være aktivert og kunne logge inn via Web UI. Kontroller kontoen uten å vise passordhash, sesjonsdata, klienttoken eller applikasjonshemmeligheter. Bruk et unikt administratorpassord.

## Konfigurer Nginx og HTTPS

Nginx er den eksterne HTTPS-inngangen. Trafikken går slik:

```text
Klient → HTTPS :443 → Nginx → HTTP localhost → 127.0.0.1:5050 → LUMS-container :5000
```

Opprett `/etc/nginx/sites-available/lums` med konfigurasjon av denne typen. Erstatt `LUMS-SERVER` med sertifikatet dekket vertsnavn eller adresse:

```nginx
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
```

Aktiver nettstedet, fjern bare standardnettstedet hvis det ikke trengs, og test konfigurasjonen før omlasting:

```bash
sudo ln -s \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
sudo rm -f \
    /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status \
    nginx \
    --no-pager
```

Ikke fjern andre Nginx-konfigurasjoner for urelaterte applikasjoner. Kontroller at sertifikatfilene finnes:

```bash
sudo ls -lh \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Den private nøkkelen skal normalt ha modus `600`, og sertifikatet normalt `644`. Ikke vis nøkkelinnholdet. Test TLS og HTTP-viderekobling:

```bash
curl -I \
    https://LUMS-SERVER/
curl -I \
    http://LUMS-SERVER/
sudo ss -lntp | grep -E ':80|:443|:5050|:5000'
```

HTTPS skal fungere uten `-k`; dette flagget hopper over sertifikatvalidering og skal ikke brukes som permanent løsning. HTTP skal viderekoble med status `301` til HTTPS. Den eksterne trafikkbanen bruker port `443`; applikasjonsportene `5050` og `5000` skal ikke eksponeres eksternt.

## Installer en Linux-klient

Gjeldende versjoner i dokumentasjonen:

```text
Agent: 1.7.0
Watcher: 1.2.1
```

Klienten må kunne nå HTTPS-endepunktet. Ping er ikke påkrevd dersom ICMP er blokkert; HTTPS-tilkobling er avgjørende. Ikke deaktiver TLS-verifisering. For et privat CA-sertifikat må CA-et installeres i klientens systemlager.

På Debian/Ubuntu kan CA-et installeres slik:

```bash
sudo cp \
    lums-ca.crt \
    /usr/local/share/ca-certificates/lums-ca.crt
sudo update-ca-certificates
curl -I \
    https://LUMS-SERVER/
```

På Arch Linux installerer du CA-et gjennom systemets konfigurerte tillitslager og kontrollerer tilkoblingen med `curl -I https://LUMS-SERVER/`. Ikke bruk `-k` som permanent løsning.

Installer klientfilene i `/opt/lums-agent` fra LUMS-repositoriet:

```bash
sudo install -d -m 755 \
    /opt/lums-agent
cd /opt/lums-public
sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py
sudo cp \
    agent/watcher.py \
    /opt/lums-agent/watcher.py
sudo cp \
    agent/package_manager.py \
    /opt/lums-agent/package_manager.py
```

Kontroller at installerte versjoner samsvarer med revisjonen som distribueres. Hvis de ikke gjør det, stopp og kontroller repositorierevisjonen.

Installer separate systemd-enheter for rapportering og jobbutførelse:

```bash
sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
sudo cp \
    agent/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent-watcher.service
sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer
sudo cp \
    agent/lums-agent-watcher.timer \
    /etc/systemd/system/lums-agent-watcher.timer
sudo systemctl daemon-reload
```

Kontroller enhetsfilene med `systemctl cat` og bekreft at de viser til filer under `/opt/lums-agent/`. Ikke aktiver timerne før klientkonfigurasjon og autentisering er på plass.

Opprett klientkonfigurasjonen utenfor Git-repositoriet:

```bash
sudo install -m 600 /dev/null \
    /etc/default/lums-agent
```

Filen skal inneholde serverendepunktet og det unike tokenet for klienten:

```text
LUMS_BASE=https://LUMS-SERVER
LUMS_TOKEN=<CLIENT-TOKEN>
```

Erstatt plassholderne med de faktiske verdiene. Beskytt filen med modus `600`; ikke skriv ut eller del tokenet. Serveren lagrer en kryptografisk representasjon av tokenet. Hvert system skal ha sitt eget token. Token kan roteres av en administrator; den gamle verdien skal ugyldiggjøres, og klientens konfigurasjon oppdateres sikkert.

Sjekk pakkehåndtereren på klienten:

```bash
command -v apt
command -v dpkg-query
command -v pacman
```

Debian/Ubuntu bruker APT/dpkg, og Arch Linux bruker pacman. Klienten må ha rettigheter til å undersøke pakker og utføre pakkeoperasjoner. Agentkatalogen trenger ikke være skrivbar for Agent-prosessen. Klientkonfigurasjonen må være lesbar, men ikke vis innholdet ved kontroll.

Kjør Agenten manuelt før du aktiverer timeren:

```bash
sudo systemctl start \
    lums-agent.service
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Kontroller at serveren mottok første klientrapport og at klienten vises i Web UI. Aktiver først deretter rapporteringstimeren og kontroller tidsplanlagte rapporter. Se logger ved behov med `journalctl`.

## Execution Watcher og oppdateringskontroll

Reporting Agent og Execution Watcher er separate: Agenten rapporterer system-/pakkeinformasjon og oppdager oppdateringer, mens Watcher henter og utfører ventende oppdateringsjobber. Kontroller installert Watcher, systemd-enhet og timer før du aktiverer den.

Aktiver Watcher-timeren først etter at klientkonfigurasjonen er riktig, autentisering fungerer, manuell Agent-kjøring er vellykket og enhetsfilene er installert:

```bash
sudo systemctl enable --now \
    lums-agent-watcher.timer
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
systemctl list-timers \
    lums-agent-watcher.timer \
    --no-pager
```

Watcher kan bruke lokal inaktiv informasjon før jobber kjøres. Dette er bare en planleggingsmekanisme, ikke autentisering eller autorisasjon. Hvis plattformen ikke leverer inaktivitetsinformasjon, må klienten ikke antas å være inaktiv. Kontroller tjenesteloggen:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

Opprett en kontrollert testjobb i LUMS. Test først pakkesøk og deretter en ufarlig pakkeinstallasjon, bekreft resultatet, test fjerning og pakkeoppdatering der det er egnet, og utfør systemoppdatering bare når den er godkjent for testmiljøet. Kontroller jobbstatus, pakkevise resultater, omstartsbehov og revisjonshistorikk. Ikke start en produksjonsoppdatering før mål, pakker, vedlikeholdsvindu og sikkerhetskopi er kontrollert.

Ved avbrudd bruker LUMS varig jobbtilstand og pakkepunktskontroll for å unngå å gjenta allerede vellykkede operasjoner unødvendig. Ikke endre en `RUNNING`-jobb manuelt for å tvinge gjennom en oppgradering. Etter omstart kontrolleres klientrapport, jobbresultat og systemtilstand på nytt.

## Verifisering og testliste

Før installasjonen regnes som fullført, bekreft følgende:

**Server**

* HTTPS og HTTP-viderekobling fungerer.
* Administratorinnlogging og RBAC fungerer.
* Databasen er tilgjengelig, og migreringer er gjennomført.
* Containeren er herdet og kjører ikke som privileged.
* `lums-data` er montert på `/var/lib/lums` og bevart.
* Applikasjonen er bare tilgjengelig gjennom localhost og Nginx.

**Klient**

* Agenten rapporterer med gyldig autentisering.
* Watcher henter og utfører godkjente jobber.
* Pakkebehandleren fungerer.
* Jobbresultater valideres, og gjenoppretting er forstått.
* Klienten rapporterer etter omstart.

Kjør prosjektets automatiserte testsett med den valgte testmiljø-Pythonen. Bekreft RBAC for administrator, operatør og viser; klientautentisering; oppdagelse av oppdateringer; opprettelse og kjøring av jobber; resultatvalidering; gjenoppretting; omstartspåvisning; revisjonslogging; redigering av logger; nettverkseksponering og brannmurregler. For fullstendige testkommandoer følger du [engelsk installasjonsveiledning](../../../install.md).

## Sikkerhetskopiering og gjenoppretting

Sikkerhetskopier minst LUMS-databasen, TLS-materialet, applikasjonshemmeligheten og distribusjonskonfigurasjonen. Lagre sikkerhetskopiene utenfor den aktive containeren. Docker-volumet `lums-data` er vedvarende lagring, men er ikke i seg selv en sikkerhetskopi. Ikke kopier en aktiv SQLite-database ukritisk dersom metoden ikke garanterer konsistens.

Etter sikkerhetskopiering kontrolleres at filen finnes og er beskyttet. Test gjenoppretting i et ikke-produksjonsmiljø før den trengs. Ved gjenoppretting må du bevare gjeldende tilstand, validere sikkerhetskopiens integritet, starte applikasjonen, kjøre integritetskontroller og kontrollere brukere, klienter, jobber og revisjonsdata. En vellykket SQLite integrity check beviser ikke at hele applikasjonstilstanden er korrekt.

## Vedlikehold og oppgradering

Før en oppgradering bør du:

1. undersøke aktive jobber og unngå å erstatte containeren mens en kritisk oppdatering pågår;
2. bekrefte en nylig, brukbar sikkerhetskopi;
3. registrere kjørende image, containerinnstillinger, volum og data-/konfigurasjonsbaner;
4. gjennomgå repoendringer og kjøre testsettet;
5. bygge og kontrollere det nye imaget før produksjonscontaineren stoppes.

Anbefalt rekkefølge:

```text
Gjennomgå → Sikkerhetskopier → Test → Bygg → Distribuer → Valider
```

Oppdater repositoriet gjennom prosjektets vanlige arbeidsflyt. Kontroller `git status` og committen som skal distribueres; ikke bygg fra utilsiktede lokale endringer. Før containeren erstattes, bekreft at `lums-data` fortsatt er montert på `/var/lib/lums`, og beskytt `/etc/lums/secrets/`, `/etc/lums/tls/` og Nginx-konfigurasjonen.

Etter erstatning kontrollerer du containerstatus, logger, applikasjonstilgjengelighet, HTTPS, vedvarende tilstand, klientkommunikasjon, oppdateringsutføring og sikkerhetsgrunnlaget. Hvis den nye containeren ikke fungerer, følg den dokumenterte rollback-prosedyren for nøyaktig denne distribusjonen. Bevar databasen; ikke slett eller opprett volumet på nytt som del av en normal oppgradering eller rollback. Valider databasens skjemakompatibilitet, brukere, klienter og jobber før normal drift gjenopptas.

## Avinstallering

Planlegg avinstalleringen før data slettes. Ta vare på nødvendig database, konfigurasjon, TLS-materiale og hemmelighet. Fjern LUMS-containeren separat fra imaget og det vedvarende volumet. Det å fjerne `lums-data` sletter SQLite-dataene og skal bare gjøres når det er tilsiktet og sikkerhetskopi-/oppbevaringsbehov er avklart. Klientinstallasjoner må fjernes separat, inkludert Agent, Watcher, systemd-tjenester og timer samt eventuell klientkonfigurasjon.

## Valgfri CPU- og minnetelemetri

Telemetriagenten er separat fra vanlig reporting Agent og Watcher. Den sender målinger til det autentiserte `POST /api/telemetry`-endepunktet. Se [telemetriguide](Telemetri.md) for målinger, sikkerhet, oppbevaring og feilsøking.

Gjennomgå følgende filer før installasjon:

* `agent/telemetry.py`
* `agent/lums-telemetry.service`
* `agent/lums-telemetry.timer`
* `scripts/install-telemetry-agent.sh`
* `tests/test_telemetry_agent.py`

Når `/etc/default/lums-agent` er konfigurert, oppdater repo-uttrekket på Debian-klienten og kjør fra repo-roten:

```sh
sudo bash scripts/install-telemetry-agent.sh
```

Installeringsskriptet kontrollerer at `LUMS_BASE` og `LUMS_TOKEN` finnes uten å skrive verdiene ut, installerer eller oppdaterer innsamleren og systemd-enhetene, aktiverer femsekunderstimeren og kjører én umiddelbar prøve. Tokenet blir i den eksisterende klientkonfigurasjonen og kopieres ikke til en annen fil. Tjenesten bruker `DynamicUser=yes`, begrensede rettigheter og gruppen `systemd-journal` for skrivebeskyttet tilgang til systemhendelseslogger. Rå loggmeldinger sendes ikke til serveren.

Konfigurasjonsvariabler:

```sh
LUMS_BASE=https://lums.example.invalid
LUMS_TOKEN=REPLACE_WITH_THIS_CLIENTS_TOKEN
LUMS_CA_FILE=/etc/ssl/certs/lums-ca.crt
```

Erstatt eksempelverdiene med miljøets faktiske server-URL og klienttoken. Beskytt `/etc/default/lums-agent` med modus `0600`. Token skal aldri committes eller deles mellom klienter. `LUMS_CA_FILE` er valgfri, men må peke til en eksisterende CA-fil som tjenesten kan lese dersom den er angitt. Ikke deaktiver sertifikatvalidering eller svekk katalogrettigheter for å omgå TLS-problemer.

Valgfri tjenesteliste er en kommaseparert tillatelsesliste:

```sh
LUMS_MONITORED_SERVICES=lums-agent.service,lums-telemetry.service,ssh.service,wazuh-agent.service,suricata.service
```

Hvis den ikke er angitt, brukes den innebygde listen over LUMS-, Docker- og SSH-tjenester. Legg bare til tjenester som faktisk er installert. Wazuh og Suricata viser kun systemd-status; LUMS henter ikke varsler fra API-ene deres og trenger eller lagrer ingen API-legitimasjon.

Kjør tester og kontroller enhetene før aktivering:

```sh
.venv/bin/python -m pytest -q tests/test_telemetry.py tests/test_telemetry_agent.py
systemd-analyze verify agent/lums-telemetry.service agent/lums-telemetry.timer
```

På en testklient installerer du filene, laster systemd på nytt og kjører tjenesten manuelt før timeren aktiveres. Bekreft autentisering og mottatte prøver i dashbordet. Ikke aktiver timeren på produksjonsklienter før serverutgivelsen er gjennomgått og godkjent.

Installasjonen er først ferdig når serveren har fungerende HTTPS, autentisering, RBAC, database, herdet container og verifisert vedvarende lagring; klienten rapporterer, Watcher utfører jobber, resultater valideres og gjenoppretting er kjent; og sikkerhetskopiering, feilsøkingsdokumentasjon og sikkerhetsgrunnlag er på plass.

```text
Observer først.
Endre deretter.
Verifiser så.
Dokumenter til slutt.
```
