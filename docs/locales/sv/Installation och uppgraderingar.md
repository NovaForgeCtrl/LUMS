
# LUMS Installationsguide

**Linux Update Management Server**

* **Projekt:** LUMS

* **Slogan:** *Linux Update Management without the noise.*

* **Repository:** `NovaForgeCtrl/LUMS`

## Komma igång: Förstå installationen innan du börjar

Den här guiden täcker en komplett serverinstallation, inklusive avancerade underhålls- och verifieringsprocedurer. Det är inte ett enda skript att köra utan granskning: servernamn, TLS-certifikat, hemlighetsfil, säkerhetskopieringsmål, nätverk och databas varierar mellan installationer.

### Vad installeras?

* **LUMS-server:** webbgränssnittet och API:et, som körs i en Docker-container.

* **Nginx:** tar emot externa HTTPS-anslutningar och vidarebefordrar dem lokalt till containern.

* **Datavolym:** innehåller SQLite-databasen. Denna volym måste överleva uppgraderingar och får aldrig raderas vid ett normalt containerbyte.

* **Hemlighetsfil:** skyddar applikationssessioner bland annat. Lägg den aldrig i Git-repositoryt, en Docker-avbildning eller ett chattmeddelande.

* **LUMS Agent och Watcher:** installeras separat på hanterade Linux-klienter. En fungerande server uppdaterar inte några klienter själv.

| Term | Betydelse |
| ----- | ----- |
| **Terminal / skal** | Ett textfönster där du anger Linux-kommandon. |
| **sudo** | Kör kommandot som följer med administratörsrättigheter. Linux kan fråga efter ditt lösenord. |
| **Värd** | Linux-datorn som kör Docker och LUMS-servern. |
| **Container** | En isolerad process som kör LUMS-webbapplikationen. |
| **Avbildning** | En förberedd mall som Docker använder för att starta en container. |
| **Volym** | Beständig Docker-lagring som finns kvar när en container byts ut. |
| **Platshållare** | Text som `LUMS-SERVER` som måste ersättas med ditt faktiska värde. |

### Kör endast tester (detta installerar ingen server)

Dessa steg är lämpliga för Debian 13 för att checka ut källkoden och köra tester lokalt. De skapar ingen produktionsserver nåbar över nätverket och installerar ingen agent på en annan dator. `sudo` behövs endast för att installera Debian-paket.

```
sudo apt update
sudo apt install -y git python3 python3-venv
git clone https://github.com/NovaForgeCtrl/LUMS.git ~/LUMS
cd ~/LUMS
python3 -m venv .venv-test
./.venv-test/bin/python -m pip install -r server/requirements.txt -r requirements-dev.txt
./.venv-test/bin/pytest -q

```

`apt update` uppdaterar paketlistor; det uppgraderar inte all installerad programvara. Den virtuella Python-miljön `.venv-test` håller testberoenden separerade från resten av systemet. En framgångsrik testkörning avslutas med kod 0; antalet tester kan ändras i takt med att projektet växer. Om det misslyckas att skapa miljön, kontrollera att `python3-venv` är installerat. Om ett test misslyckas, spara det fullständiga felet och läs felsökningsguiden; radera inte produktionsdata.

För en riktig installation, fortsätt med de numrerade avsnitten och läs säkerhets- och säkerhetskopieringsinstruktionerna först. Om LUMS redan körs, använd uppgraderingsproceduren i `administration.md`, inte förstagångsinstallationsproceduren.

## 1. Översikt

LUMS är en centraliserad plattform för Linux-uppdateringshantering för kontrollerad uppdateringsdistribution, klientrapportering, pakethantering, körning av uppdateringsjobb, resultatvalidering och granskningsbar administration.

Den nuvarande arkitekturen separerar hanteringsservern från de hanterade Linux-klienterna.

### Servern tillhandahåller:

* Webbanslutst administration

* Klienthantering

* Klientautentisering

* Paketinventering

* Rapportering av tillgängliga uppdateringar

* Paketsökning

* Paketinstallation och borttagning

* Hantering av uppdateringsjobb

* Validering av jobbresultat

* Uppdateringshistorik

* Rollbaserad åtkomstkontroll

* Granskningsloggning

* Beständigt tillstånd baserat på SQLite

### Linux-klienter tillhandahåller:

* Systeminformation

* Inventering av installerade paket

* Detektering av tillgängliga uppdateringar

* Paketoperationer

* Körning av uppdateringsjobb

* Detektering av inaktivitetsläge

* Checkpointing och återställning av jobb

* Omstartsdetektering

* Resultatrapportering

### Den nuvarande implementeringen stöder:

* **Debian / Ubuntu**

  * `└── APT / dpkg`

* **Arch Linux**

  * `└── pacman`

## 2. Arkitektur

Produktionsarkitekturen är:

```
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

LUMS-applikationen är inte avsedd att exponeras direkt mot nätverket.

Applikationscontainern är bunden till:
`127.0.0.1:5050` → container: `5000`

Nginx är den externa HTTPS-ingångspunkten.

Port 5000 publiceras inte direkt.

Port 5050 måste förbli endast localhost.

## 3. Applikationskomponenter

En komplett LUMS-installation består av flera komponenter.

### 3.1 LUMS-server

Servern innehåller:

* Flask

* Gunicorn

* SQLite

* Webbgränssnitt

* REST API

* Autentisering

* RBAC

* Granskningsloggning

* Jobbhantering

* Pakethantering

Applikationen körs inuti Docker-containern:
`lums`

Den beständiga databasen lagras utanför containerns skrivbara applikationsfilsystem:
`lums-data:/var/lib/lums/lums.db`

### 3.2 Nginx

Nginx tillhandahåller:

* HTTPS-terminering

* TLS-certifikathantering

* HTTP → HTTPS-omdirigering

* Omvänd proxy

* Extern nätverksingångspunkt

Den avsedda förfrågningsvägen är:

```
Webbläsare
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

Flask/Gunicorn-applikationen bör inte exponeras direkt mot LAN.

### 3.3 Linux-agent

LUMS-agenten körs på varje hanterad Linux-klient.

Den aktuella agentversionen är: `1.7.0`

Agenten ansvarar för:

* Systeminformation

* Installerade paket

* Tillgängliga uppdateringar

* Klientrapportering

* Jobbhämtning

* Jobbanspråk

* Paketoperationer

* Resultatrapportering

* Omstartsdetektering

Agenten kommunicerar med LUMS-servern via HTTPS och en klientspecifik Bearer-token.

### 3.4 Execution Watcher

Execution watchern ansvarar för kontrollerad körning av uppdateringsjobb.

Den aktuella Watcher-versionen är: `1.2.1`

Watchern hanterar:

* Detektering av väntande jobb

* Inaktivitetskontroller

* Atomiskt jobbanspråk

* Uppdateringskörning

* Checkpointhantering

* Återställning av avbrutna jobb

* Resultatbearbetning

Watchern är avsiktligt separerad från vanlig klientrapportering.

## 4. Säkerhetsmodell

Installationen måste bevara LUMS säkerhetsbaslinje.

Produktionsservern använder:

* HTTPS

* Bearer-token-klientautentisering

* Rollbaserad webbauktorisering

* CSRF-skydd

* Granskningsloggning

* Skrivskyddat containerrotfilsystem

* Borttagna Linux-kapaciteter

* `no-new-privileges`

* Icke-root-applikationsanvändare

* Applikationsport endast localhost

* Beständig Docker-volym

* Skrivskyddad hemlighetsmontering

Docker-containern körs som den oprivilegierade användaren: `lums` med UID: `10001`

Containern får inte köras i privilegierat läge.

Rotfilsystemet måste förbli skrivskyddat.

Applikationen får inte kräva skrivåtkomst till sin applikationskatalog.

Beständig applikationsdata lagras via den dedikerade Docker-volymen.

## 5. Nuvarande RBAC-modell

LUMS tillhandahåller för närvarande tre webbroller:

* `administrator`

* `operator`

* `viewer`

### Administratör

Administratörer kan utföra administrativa operationer inklusive:

* Visa klienter

* Visa installerad programvara

* Visa tillgängliga uppdateringar

* Skapa och köra uppdateringsjobb

* Visa uppdateringshistorik

* Använda pakethantering

* Använda systemunderhåll

* Skapa och inaktivera klienter

* Rotera klienttoken

* Hantera användare

* Hantera roller

### Operator

Operatorer kan utföra operativ hantering:

* Visa klienter

* Visa installerad programvara

* Visa tillgängliga uppdateringar

* Skapa och köra uppdateringsjobb

* Visa uppdateringshistorik

* Använda pakethantering

* Använda systemunderhåll

Operatorer har inte tillgång till:

* Användarhantering

* Rollhantering

* Skapande/inaktivering av klienter

* Rotation av klienttoken

### Viewer

Viewers har avsiktligt begränsad åtkomst. En Viewer kan komma åt:

* Klienter

* Installerad programvara

Följande hanteringsområden är dolda från Viewer-gränssnittet och skyddade på serversidan:

* Tillgängliga uppdateringar

* Uppdateringsjobb

* Uppdateringshistorik

* Pakethantering

* Systemunderhåll

Att dölja i gränssnittet är därför inte säkerhetsgränsen. Auktorisering på serversidan är fortfarande obligatorisk.

## 6. Installationskrav

### 6.1 LUMS-server

Den nuvarande distributionen kräver en Linux-värd med:

* Docker Engine

* Git

* Nginx

* OpenSSL

* Nätverksanslutning

* Beständig lagring

Servern måste ha tillräckligt med lagring för:

* Docker-avbildningar

* SQLite-databas

* Applikationsdata

* Loggar

* Säkerhetskopior

LUMS-applikationen körs själv inuti Docker.

### 6.2 Linux-klienter

Hanterade Linux-klienter kräver:

* Python 3

* systemd

* Pakethanterare som stöds

* Nätverksanslutning till LUMS-servern

* Giltig klienttoken

* Betrott TLS-certifikat

Pakethanteringsfamiljer som stöds:

* **Debian / Ubuntu:** APT / dpkg

* **Arch Linux:** pacman

Klienten måste kunna nå LUMS HTTPS-slutpunkten.

## 7. Rekommenderad katalogstruktur

Den rekommenderade server-sidans repository-plats är: `/opt/lums-public/`

Repositoryt innehåller applikationskällkoden, agentkällkoden och tester.

En typisk installation använder:

```
/opt/lums-public/
    ├── agent/
    ├── server/
    ├── tests/
    ├── Dockerfile
    ├── requirements.txt
    └── requirements-dev.txt

```

Konfiguration på värdsidan hålls utanför repositoryt:

```
/etc/lums/
    ├── secrets/
    │   └── lums_secret
    └── tls/
        ├── lums.crt
        └── lums.key

```

Beständig applikationsdata lagras i: `lums-data:/var/lib/lums`

SQLite-databasen är: `/var/lib/lums/lums.db`

Databasen får aldrig lagras i Git-arbetsträdet. Hemligheter och privat TLS-material måste också förbli utanför repositoryt.

## 8. Förberedelse av repository

Klona repositoryt till den avsedda installationskatalogen:

```
sudo mkdir -p /opt
cd /opt

sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public

```

Gå in i repositoryt:

```
cd /opt/lums-public

```

Kontrollera arbetsträdet:

```
git status

```

Inspektera den aktuella revisionen:

```
git log -1 --oneline --decorate

```

För kontrollerade distributioner bör den exakta commit som används för installationen registreras. Bygg inte produktionsavbildningar från ett okänt eller overifierat arbetsträd.

## 9. Säkerhetskontroll av repository

Innan du bygger produktionsavbildningen, verifiera att känsliga filer inte har placerats i repositoryt.

Granska arbetsträdet:

```
git status --short

```

Granska ignorerade filer där det är lämpligt:

```
git status --ignored --short

```

Repositoryt får inte innehålla:

* Produktionsdatabasfiler

* Privata TLS-nycklar

* Applikationshemligheter

* Klienttoken

* Inloggningsuppgifter

* Säkerhetskopierade databaser

* Körtidsloggar

* Tillfälliga säkerhetskopior

Projektet använder ignore-regler för repositoryt för att förhindra att vanliga säkerhetskopior oavsiktligt spåras. Innan du commitar ändringar, inspektera den staged filförteckningen noggrant.

## 10. Förbered konfigurationskataloger på värden

Skapa de nödvändiga katalogerna på värdsidan:

```
sudo install -d -m 700 /etc/lums
sudo install -d -m 700 /etc/lums/secrets
sudo install -d -m 700 /etc/lums/tls

```

Hemlighetskatalogen innehåller applikationshemligheten. TLS-katalogen innehåller TLS-certifikatet och den privata nyckeln. Att skydda dessa kataloger minskar risken för oavsiktlig exponering.

Verifiera:

```
sudo stat -c '%a %U:%G %n' \
    /etc/lums \
    /etc/lums/secrets \
    /etc/lums/tls

```

## 11. Skapa applikationshemligheten

LUMS applikationshemlighet lagras på värden snarare än att bäddas in direkt i Docker-avbildningen.

Produktionssökvägen för hemligheten är: `/etc/lums/secrets/lums_secret`

Generera en slumpmässig hemlighet:

```
sudo sh -c 'umask 077 && openssl rand -hex 32 > /etc/lums/secrets/lums_secret'

```

Skydda den resulterande filen:

```
sudo chmod 600 \
    /etc/lums/secrets/lums_secret

```

Verifiera behörigheterna utan att visa hemligheten:

```
sudo stat -c '%a %U:%G %n' \
    /etc/lums/secrets/lums_secret

```

*Förväntat:* `600`

Hemligheten får aldrig:

* Commitas till Git

* Skrivas ut i loggar

* Inkluderas i Docker-avbildningen

* Placeras i skärmdumpar

* Publiceras i ärenden

* Inkluderas i dokumentation

Containern tar emot hemligheten via en skrivskyddad bind-montering.

## 12. Förbered TLS-material

LUMS använder HTTPS för extern åtkomst.

De rekommenderade platserna på värdsidan är:

* `/etc/lums/tls/lums.crt`

* `/etc/lums/tls/lums.key`

Installera lämpligt certifikat och privat nyckel innan du konfigurerar Nginx.

Skydda den privata nyckeln:

```
sudo chmod 600 \
    /etc/lums/tls/lums.key

```

Certifikatet kan vara läsbart för Nginx-tjänsten:

```
sudo chmod 644 \
    /etc/lums/tls/lums.crt

```

Verifiera:

```
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key

```

Den privata nyckeln får aldrig committas till Git eller inkluderas i Docker-avbildningen.

## 13. Installationsprincip

Installationen bör fortskrida i kontrollerade steg:

```
Repository
    ↓
Värdkonfiguration
    ↓
Applikationshemlighet
    ↓
TLS-material
    ↓
Docker-avbildning
    ↓
Beständig volym
    ↓
Härdad container
    ↓
Nginx / HTTPS
    ↓
Administratör
    ↓
Servervalidering
    ↓
Linux-klienter

```

Anslut inte produktionsklienter innan servern har klarat sina egna valideringskontroller. Följande avsnitt fortsätter med Docker-avbildningsbygge och den härdade produktionsdistributionen.

## 14. Bygg LUMS Docker-avbildning

Innan du bygger produktionsavbildningen, se till att repositoryt är i avsett tillstånd.

Gå in i repositoryt:

```
cd /opt/lums-public

```

Kör testsviten innan du skapar en produktionsavbildning:

```
./.venv-test/bin/pytest -q

```

Testantalet förväntas växa i takt med att projektet utvecklas. Det viktiga kravet är att den relevanta testsviten slutförs framgångsrikt före distribution.

Bygg Docker-avbildningen:

```
sudo docker build \
    -t lums:latest \
    .

```

Verifiera att avbildningen finns:

```
sudo docker image ls lums

```

Inspektera avbildningen:

```
sudo docker image inspect lums:latest

```

Produktionsavbildningen är baserad på en fastnålad Python 3.13 slim-basavbildning. Dockerfile använder också fastnålade produktionsberoenden där det krävs.

## 15. Granska Docker-bygget

Innan du distribuerar avbildningen, granska byggutdata för oväntade fel eller varningar.

Kontrollera den resulterande avbildningen:

```
sudo docker inspect \
    lums:latest

```

Verifiera den konfigurerade applikationsanvändaren:

```
sudo docker image inspect \
    lums:latest \
    --format '{{.Config.User}}'

```

Applikationen är avsedd att köras som: `lums`. Applikationen får inte kräva root-privilegier under normal körning.

Granska Dockerfile när du ändrar byggprocessen:

```
sed -n '1,240p' Dockerfile

```

Lägg inte till hemligheter, certifikat eller produktionsdatabaser i Docker-byggkontexten. Repositoryt innehåller en `.dockerignore`-fil för att minska risken för att oavsiktligt inkludera körtidsartefakter i avbildningen.

## 16. Skapa den beständiga Docker-volymen

Skapa den beständiga LUMS-datavolymen:

```
sudo docker volume create lums-data

```

Verifiera:

```
sudo docker volume inspect lums-data

```

Volymen lagrar beständig applikationsdata:

```
lums-data
    ↓
/var/lib/lums
    ↓
/var/lib/lums/lums.db

```

Containerfilsystemet självt får inte behandlas som beständig applikationslagring. Databasen överlever därför containerbyte så länge `lums-data`-volymen bevaras.

> \[!IMPORTANT\]
> Ta aldrig bort `lums-data` under en normal applikationsuppgradering. Att ta bort volymen tar bort SQLite-databasen som lagras i den.

## 17. Verifiera den beständiga volymen

Innan du startar LUMS, bekräfta att volymen finns:

```
sudo docker volume inspect \
    lums-data

```

Volymen kan också kontrolleras via Docker:

```
sudo docker volume ls | grep lums-data

```

En nyskapad volym kommer normalt inte att innehålla en databas ännu. Databasen initieras av LUMS-applikationen under distributionen.

## 18. Produktionscontainerkonfiguration

Produktionscontainern använder flera säkerhetskontroller samtidigt.

Den förväntade körtidsbaslinjen är:

* Icke-root-användare

* Skrivskyddat rotfilsystem

* Alla Linux-kapaciteter borttagna

* `no-new-privileges`

* Inget privilegierat läge

* Applikationsbindning endast localhost

* Skrivskyddad montering av applikationshemlighet

* Beständig skrivbar datavolym

* Dedikerad `/tmp` tmpfs

Applikationsporten publiceras endast till localhost: `127.0.0.1:5050` → container: `5000`

Den externa HTTPS-slutpunkten tillhandahålls av Nginx.

## 19. Starta den härdade LUMS-containern

Innan du startar en ny produktionscontainer, se till att en annan container med namnet `lums` inte redan körs:

```
sudo docker ps \
    --filter name=lums

```

Om en befintlig distribution ersätts, bevara den befintliga containern tills den nya avbildningen har validerats.

Starta den härdade containern:

```
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

* Applikationshemligheten monteras skrivskyddat.

* SQLite-databasen lagras i den beständiga volymen.

* Rotfilsystemet är skrivskyddat.

* Alla Linux-kapaciteter är borttagna.

* Säkerhetsalternativet `no-new-privileges` förhindrar processer inuti containern från att få ytterligare privilegier.

## 20. Verifiera containertillståndet

Kontrollera den körande containern:

```
sudo docker ps \
    --filter name=lums

```

*Förväntat tillstånd:* `Up ...`

Kontrollera containertillståndet direkt:

```
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums

```

*Förväntat:* `running`

Inspektera de senaste loggarna:

```
sudo docker logs \
    --tail 100 \
    lums

```

Applikationsstartfel måste åtgärdas innan installationen fortsätter.

## 21. Verifiera containersäkerhet

Inspektera den effektiva körtidssäkerhetskonfigurationen:

```
sudo docker inspect lums \
    --format='User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}'

```

Den förväntade baslinjen är:

```
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]

```

Den exakta formateringen av Docker-utdata kan variera. Det är den effektiva konfigurationen som spelar roll.

## 22. Verifiera applikationsporten

Kontrollera den publicerade Docker-porten:

```
sudo docker port lums

```

*Förväntat:* `5000/tcp -> 127.0.0.1:5050`

Följande är **inte** acceptabelt för produktionsapplikationen: `0.0.0.0:5050` eller `0.0.0.0:5000`

Applikationen är avsiktligt endast tillgänglig via den lokala omvända proxyvägen.

Kontrollera lyssnande sockets:

```
sudo ss -lntp | grep -E ':5050|:5000'

```

Endast localhost-applikationsbindningen ska finnas.

## 23. Verifiera hemlighetsmonteringen

Bekräfta att hemligheten är monterad:

```
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Source "->" .Destination "RW=" .RW}}{{end}}'

```

Applikationshemligheten bör visas liknande:
`/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false`

Den exakta utdata kan innehålla ytterligare monteringsinformation. Den viktiga egenskapen är: `RW=false`

Skriv aldrig ut hemlighetens innehåll. Ett direkt läsbarhetstest är tillräckligt:

```
sudo docker exec lums \
    sh -c 'test -r /run/secrets/lums_secret && echo "secret mount: OK"'

```

*Förväntat:* `secret mount: OK`

## 24. Verifiera monteringen av den beständiga volymen

Inspektera containerns monteringar:

```
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Type .Source "->" .Destination "RW=" .RW}}{{end}}'

```

LUMS datavolym måste monteras på: `/var/lib/lums` och måste vara skrivbar: `RW=true`

Det förväntade förhållandet är:

```
lums-data
    ↓
/var/lib/lums

```

Rotfilsystemet förblir skrivskyddat medan den dedikerade datavolymen tillhandahåller nödvändig beständig skrivåtkomst.

## 25. Verifiera det skrivskyddade rotfilsystemet

Applikationens rotfilsystem måste vara skrivskyddat.

Container-körtiden bör rapportera: `ReadonlyRootfs=true`

Ett kontrollerat skrivtest kan utföras inuti containern. Till exempel:

```
sudo docker exec lums \
    sh -c 'touch /app/.write-test'

```

Kommandot bör misslyckas eftersom `/app` är en del av det skrivskyddade containerfilsystemet.

Inaktivera inte det skrivskyddade rotfilsystemet bara för att en applikationskomponent försöker skriva utanför sina avsedda skrivbara platser. Om applikationen kräver beständig data, använd lämplig volym eller körtidsfilsystem istället.

## 26. Verifiera det skrivbara temporära filsystemet

Containern tillhandahåller en dedikerad `/tmp` tmpfs.

Verifiera:

```
sudo docker exec lums \
    sh -c 'touch /tmp/lums-write-test && rm -f /tmp/lums-write-test && echo "tmpfs: OK"'

```

*Förväntat:* `tmpfs: OK`

Det temporära filsystemet är konfigurerat med: `noexec`, `nosuid` och en storleksgräns. Detta ger tillfällig skrivbar lagring utan att göra containerrotfilsystemet skrivbart.

## 27. Verifiera applikationsdatakatalogen

LUMS-applikationen kräver skrivåtkomst till sin beständiga datakatalog.

Testa:

```
sudo docker exec lums \
    sh -c 'touch /var/lib/lums/.write-test && rm -f /var/lib/lums/.write-test && echo "data volume: OK"'

```

*Förväntat:* `data volume: OK`

Detta bekräftar att den dedikerade skrivbara volymen är tillgänglig medan resten av containern förblir skrivskyddad.

## 28. Verifiera applikationsanvändaren

Bekräfta den effektiva körtidsanvändaren:

```
sudo docker exec lums \
    id

```

Processen bör köras som den oprivilegierade LUMS-användaren. Förväntad identitet inkluderar: `uid=10001(lums)`. Den exakta gruppinformationen kan variera beroende på avbildningskonfigurationen.

Containern får inte köras som `root` under normal drift.

## 29. Databasinitiering

Efter att containern startat, kontrollera om databasen finns:

```
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db

```

Om applikationen har initierats framgångsrikt bör databasen finnas. Databasen finns på `/var/lib/lums/lums.db` inuti containern och kvarstår fysiskt genom `lums-data`.

Databasen får inte kopieras till `/opt/lums-public` eller committas till Git.

## 30. Verifiera SQLite-körtidskonfiguration

Den nuvarande LUMS produktionsbaslinje använder:

* `journal_mode = wal`

* `busy_timeout = 5000 ms`

* `synchronous = 2`

* `foreign_keys = ON`

Applikationen aktiverar uttryckligen främmandenyckelkontroll för databasanslutningar. Databasen använder WAL-läge för normal produktionsdrift.

Körtidskonfigurationen kan inspekteras från applikationsdatabasen. Till exempel:

```
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

Förväntade värden är ekvivalenta med:

```
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0

```

Applikationen aktiverar främmande nycklar uttryckligen.

## 31. Verifiera databasintegritet

Kör en SQLite-integritetskontroll:

```
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
result = db.execute("PRAGMA integrity_check").fetchone()[0]
print(result)
db.close()
PY

```

*Förväntat:* `ok`

Fortsätt inte med distributionen om integritetskontrollen rapporterar databaskorruption.

## 32. Verifiera databasmigreringar

LUMS använder applikationsmigreringar för databasschemändringar.

Inspektera de migreringsrelaterade filerna:

```
ls -lh \
    server/*migration*.py

```

Applikationen utför nödvändiga migreringar under start/distribution enligt den nuvarande implementeringen.

Efter start, inspektera applikationsloggarna:

```
sudo docker logs \
    --tail 200 \
    lums

```

Migreringsfel måste utredas innan du skapar användare eller ansluter klienter. Ändra inte produktions-SQLite-schemat manuellt om inte projektdokumentationen uttryckligen kräver det.

## 33. Lokal applikationsvalidering

Innan du konfigurerar Nginx, bekräfta att applikationen svarar lokalt.

Docker-applikationen är bunden till: `127.0.0.1:5050`

En lokal förfrågan kan testas med:

```
curl -I \
    http://127.0.0.1:5050/

```

Det exakta HTTP-svaret beror på den aktuella applikationsrutten och autentiseringstillståndet. Det viktiga kravet är att förfrågan nås den körande LUMS-applikationen.

Om anslutningen misslyckas, inspektera:

```
sudo docker ps \
    --filter name=lums

```

och:

```
sudo docker logs \
    --tail 200 \
    lums

```

Exponera inte port 5050 externt som en felsökningslösning.

## 34. Initial serverkontrollpunkt

I detta skede bör servern uppfylla:

* \[ \] Repository klonat

* \[ \] Arbetsträd granskat

* \[ \] Produktionstester slutförda

* \[ \] Docker-avbildning byggd

* \[ \] Beständig `lums-data`-volym finns

* \[ \] Härdad container körs

* \[ \] Container körs som `lums`

* \[ \] Rotfilsystem är skrivskyddat

* \[ \] Alla kapaciteter är borttagna

* \[ \] `no-new-privileges` är aktiverat

* \[ \] Privilegierat läge är inaktiverat

* \[ \] Hemlighet monterad skrivskyddat

* \[ \] Beständig datavolym monterad

* \[ \] Port 5050 är endast localhost

* \[ \] SQLite-databas finns

* \[ \] SQLite-integritetskontroll lyckas

* \[ \] Främmande nycklar är aktiverade

* \[ \] Lokal applikationsslutpunkt svarar

Anslut inte produktionsklienter ännu. Nästa steg konfigurerar Nginx, HTTPS och den externa LUMS-slutpunkten.

## 35. Konfigurera Nginx

Nginx tillhandahåller den externa HTTPS-ingångspunkten för LUMS.

Applikationen själv förblir bunden till: `127.0.0.1:5050`

Den avsedda förfrågningsvägen är:

```
Klient
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

Skapa Nginx-platskonfigurationen:

```
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

Ersätt `LUMS-SERVER` med det värdnamn eller den adress som används av installationen. Använd inte den bokstavliga platshållaren i en produktionskonfiguration.

## 36. Aktivera LUMS Nginx-konfiguration

Skapa den aktiverade platslänken:

```
sudo ln -s \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums

```

Om standard Nginx-platsen inte behövs, ta bort den:

```
sudo rm -f \
    /etc/nginx/sites-enabled/default

```

Ta inte bort andra Nginx-konfigurationer som tillhör orelaterade applikationer.

## 37. Validera Nginx-konfigurationen

Testa alltid konfigurationen innan du laddar om Nginx:

```
sudo nginx -t

```

*Förväntat:*

```
syntax is ok
test is successful

```

Endast efter ett framgångsrikt konfigurationstest bör Nginx laddas om:

```
sudo systemctl reload nginx

```

Verifiera tjänsten:

```
sudo systemctl status \
    nginx \
    --no-pager

```

Nginx måste köras innan HTTPS-valideringen fortsätter.

## 38. Verifiera TLS-certifikatfiler

Bekräfta att de konfigurerade certifikatfilerna finns:

```
sudo ls -lh \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key

```

Verifiera behörigheter:

```
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key

```

Den privata nyckeln bör normalt vara `600`. Certifikatet kan normalt vara `644`.

Skriv aldrig ut den privata nyckelns innehåll.

## 39. Verifiera HTTPS-slutpunkten

Testa HTTPS lokalt:

```
curl -I \
    https://LUMS-SERVER/

```

Ersätt `LUMS-SERVER` med det värdnamn som täcks av serverns TLS-certifikat. Använd inte `-k` för rutinmässig verifiering; det hoppar över certifikatvalidering.

När certifikatet är betrott av systemet, använd certifikatverifiering:

```
curl -I \
    https://LUMS-SERVER/

```

Ett framgångsrikt svar bekräftar att förfrågan når Nginx HTTPS-slutpunkten. Den exakta HTTP-statusen beror på den begärda rutten och autentiseringstillståndet. Det viktiga kravet är att TLS-anslutningen lyckas och förfrågan når LUMS.

## 40. Verifiera HTTP till HTTPS-omdirigering

HTTP-lyssnaren måste omdirigera klienter till HTTPS.

Testa:

```
curl -I \
    http://LUMS-SERVER/

```

*Förväntat beteende:*

```
HTTP/1.1 301 ...
Location: https://...

```

LUMS-applikationen bör inte drivas via en okrypterad HTTP-anslutning. Konfigurera inte klienter permanent med certifikatverifiering inaktiverad bara för att det initiala certifikatet inte är betrott. Åtgärda förtroendekonfigurationen istället.

## 41. Verifiera den externa nätverksvägen

Inspektera lyssnande sockets:

```
sudo ss -lntp | grep -E ':80|:443|:5050|:5000'

```

Den avsedda arkitekturen är:

```
80
 │
 └── HTTP-omdirigering
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

Port 5050 får inte exponeras mot LAN. Port 5000 får inte exponeras direkt. Docker-applikationsporten är en intern omvänd proxy-slutpunkt.

## 42. Verifiera säkerhetsrubriker

Inspektera HTTPS-svarsrubrikerna:

```
curl -I \
    https://LUMS-SERVER/

```

Granska de returnerade rubrikerna istället för att anta att säkerhetskonfigurationen är aktiv. Relevanta säkerhetsrubriker kan inkludera:

* `X-Content-Type-Options`

* `X-Frame-Options`

* `Referrer-Policy`

* `Content-Security-Policy`

De exakta rubrikerna beror på den aktuella LUMS-applikationen och Nginx-konfigurationen.

Om en nödvändig rubrik saknas, inspektera den effektiva Nginx-konfigurationen:

```
sudo nginx -T

```

och applikationskonfigurationen:

```
sudo docker logs \
    --tail 100 \
    lums

```

Lägg inte till säkerhetsrubriker blint utan att kontrollera vilket lager som redan ansvarar för dem.

## 43. Verifiera värdhantering

Produktionsdistributionen bör inte exponera applikationen via en oavsiktlig standard Nginx-plats.

Granska den aktiva konfigurationen:

```
sudo nginx -T

```

Kontrollera de aktiverade platserna:

```
ls -la \
    /etc/nginx/sites-enabled/

```

Den avsedda LUMS-värden bör finnas. Standardplatsen bör inte oväntat betjäna LUMS-applikationen.

När du använder en IP-adress som LUMS-slutpunkt, se till att den konfigurerade `server_name` och certifikatet matchar den faktiska distributionsmodellen.

## 44. Verifiera Docker-exponering igen

Efter att Nginx konfigurerats, bekräfta att applikationen fortfarande är endast localhost:

```
sudo docker port lums

```

*Förväntat:* `5000/tcp -> 127.0.0.1:5050`

Den omvända proxyn kräver inte att Docker-bindningen ändras. Ändra den inte till `0.0.0.0:5050` bara för att Nginx lyssnar på nätverket. Nginx och Docker har avsiktligt separata exponeringsgränser.

## 45. Skapa den initiala administratören

Den initiala administratören måste skapas med det aktuella repositoryts administratörsinitieringsmekanism.

Innan du kör ett initieringskommando, inspektera den tillgängliga repository-implementationen:

```
cd /opt/lums-public

```

Granska de säkerhetsrelaterade initieringsfilerna:

```
find server \
    -maxdepth 1 \
    -type f \
    -iname '*security*' \
    -o -iname '*migration*'

```

Inspektera sedan den aktuella migrerings-/initieringsimplementationen innan du kör den. Till exempel:

```
sed -n '1,260p' \
    server/security_migration.py

```

Använd initieringsproceduren som tillhandahålls av den exakta repository-revision som distribueras.

> \[!IMPORTANT\]
> Kopiera inte ett administratörslösenord till skalhistorik eller dokumentation.

Den initiala administratören måste få: `role = administrator`

Administratörskontot krävs för den första webbinloggningen och efterföljande klientadministration.

## 46. Verifiera administratörskontot

Efter administratörsinitiering, verifiera kontot utan att exponera autentiseringsmaterial.

En databasinspektion kan utföras från containern:

```
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

Förväntade administratörsegenskaper inkluderar:

* `enabled = 1`

* `role = administrator`

Skriv inte ut:

* lösenordshashar

* sessionsdata

* klienttoken

* applikationshemligheter

## 47. Administratörslösenord

Använd ett unikt administratörslösenord. Lösenordet bör inte återanvändas från:

* andra servrar

* Linux-konton

* GitHub-konton

* e-postkonton

* nätverksenheter

* andra LUMS-installationer

LUMS-applikationen lagrar lösenord med den konfigurerade lösenordshashningsmekanismen. Försök inte ersätta applikationens lösenordshash manuellt i SQLite.

Om administratörslösenordet måste ändras, använd den stödda applikationsmekanismen.

## 48. Första webbinloggning

Öppna LUMS HTTPS-slutpunkten: `https://LUMS-SERVER/`

Logga in med administratörskontot. Efter autentisering bör administratören ha tillgång till det administrativa gränssnittet.

Administratörsgränssnittet bör ge tillgång till de områden som tillåts av den nuvarande RBAC-implementationen. Åtminstone bör administratören kunna komma åt:

* Klienter

* Installerad programvara

* Tillgängliga uppdateringar

* Uppdateringsjobb

* Uppdateringshistorik

* Pakethantering

* Systemunderhåll

* Användarhantering

## 49. Verifiera administratörens RBAC

Efter inloggning, verifiera att administrativa funktioner är tillgängliga. Administratören bör kunna komma åt användarhantering. Administratören bör också kunna utföra klienthanteringsoperationer som tillåts av den nuvarande implementationen.

Auktorisering på serversidan förblir säkerhetsgränsen. Webbläsargränssnittet är inte betrott bara för att ett element är synligt eller dolt.

## 50. Skapa en operator

Efter att administratörskontot har verifierats, skapa ett operatörskonto via LUMS användarhanteringsgränssnitt.

Operatörsrollen är avsedd för operativ uppdateringshantering. En operator kan komma åt:

* Klienter

* Installerad programvara

* Tillgängliga uppdateringar

* Uppdateringsjobb

* Uppdateringshistorik

* Pakethantering

* Systemunderhåll

En operator får inte kunna utföra endast-administratörsfunktioner som:

* Användarhantering

* Rollhantering

* Skapande/inaktivering av klienter

* Rotation av klienttoken

Verifiera behörigheterna med applikationsgränssnittet och, där det är lämpligt, API-auktoriseringsbeteendet.

## 51. Skapa en Viewer

Ett Viewer-konto kan skapas när skrivskyddad åtkomst krävs.

Viewer-rollen är avsiktligt begränsad. En Viewer kan komma åt:

* Klienter

* Installerad programvara

Följande områden får inte vara tillgängliga för en Viewer:

* Tillgängliga uppdateringar

* Uppdateringsjobb

* Uppdateringshistorik

* Pakethantering

* Systemunderhåll

Dessa begränsningar upprätthålls på serversidan. Gränssnittet kan dessutom dölja otillgängliga funktioner.

## 52. Verifiera Viewer-isolering

Logga in med ett Viewer-konto och verifiera det synliga gränssnittet. Viewern bör inte få hanteringskontroller. Viewern får inte kunna kringgå gränssnittet och anropa skyddade slutpunkter direkt.

Ett auktoriseringsfel bör returneras för skyddade operationer.

Den förväntade principen är:

```
UI-begränsning
     +
auktorisering på serversidan
     =
RBAC-gräns

```

Förlita dig aldrig på JavaScript eller dolda HTML-element som den enda auktoriseringsmekanismen.

## 53. Verifiera sessions- och CSRF-skydd

Efter den första framgångsrika inloggningen, verifiera att applikationen använder sina konfigurerade sessions- och CSRF-skydd.

Installationen bör inte inaktivera CSRF-skydd för att få API-förfrågningar eller webbläsaråtgärder att fungera. Om en legitim förfrågan misslyckas med ett CSRF-fel, inspektera applikationsflödet istället för att inaktivera skyddet.

Sessionsrelaterat beteende dokumenteras i `docs/security.md`.

## 54. Verifiera inloggningsfrekvensbegränsning

Det nuvarande inloggningsskyddet använder beständig spårning av misslyckanden.

Den konfigurerade progressionen är:

* **5 försök:** 30 sekunder

* **6 försök:** 60 sekunder

* **7 försök:** 120 sekunder

* **8+ försök:** 300 sekunder

Framgångsrik autentisering rensar det tillämpliga feltillståndet. Utlös inte upprepade misslyckade autentiseringar mot en produktionsinstallation bara för att testa mekanismen. Använd den befintliga testsviten för upprepad automatisk validering.

## 55. Servervalideringskontrollpunkt

I detta skede, verifiera:

* \[ \] Nginx körs

* \[ \] Nginx-konfigurationen klarar `nginx -t`

* \[ \] TLS-certifikat är installerat

* \[ \] TLS-privat nyckel är skyddad

* \[ \] HTTPS fungerar

* \[ \] HTTP omdirigerar till HTTPS

* \[ \] Docker förblir endast localhost

* \[ \] Port 5000 är inte externt exponerad

* \[ \] Säkerhetsrubriker finns som konfigurerat

* \[ \] Standard Nginx-plats betjänar inte oavsiktligt LUMS

* \[ \] Administratörskonto finns

* \[ \] Administratör kan logga in

* \[ \] Administratörs-RBAC fungerar

* \[ \] Operatörsroll kan skapas

* \[ \] Viewer-roll kan skapas

* \[ \] Viewer-begränsningar upprätthålls på serversidan

* \[ \] CSRF-skydd förblir aktiverat

* \[ \] Sessionsskydd förblir aktiverat

Först efter att servern klarar dessa kontroller bör Linux-klienter installeras. Nästa avsnitt täcker Linux-agenten, klientkonfiguration, TLS-förtroende och systemd-integration.

## 56. Installation av Linux-klient

LUMS-klienter är Linux-system som hanteras av LUMS-servern.

En klientinstallation består av:

```
Linux-system
    ↓
LUMS-agent
    ↓
Klientkonfiguration
    ↓
Klienttoken
    ↓
TLS-förtroende
    ↓
systemd-tjänst
    ↓
Rapporteringstimer

```

Uppdateringskörning hanteras separat av execution watchern.

Den aktuella agentversionen är: `1.7.0`

Den aktuella Watcher-versionen är: `1.2.1`

## 57. Linux-klienter som stöds

De nuvarande pakethanteringsimplementationerna stöder:

* **Debian / Ubuntu**

  * `└── APT / dpkg`

* **Arch Linux**

  * `└── pacman`

Verifiera operativsystemet innan du installerar klienten:

```
cat /etc/os-release

```

Verifiera arkitekturen:

```
uname -m

```

Verifiera systemd:

```
systemctl --version

```

Klienten kräver en fungerande systemd-installation.

## 58. Nätverkskrav för klient

Klienten måste kunna nå LUMS HTTPS-slutpunkten.

Testa grundläggande nätverksanslutning:

```
ping LUMS-SERVER

```

En framgångsrik ping krävs inte när ICMP blockeras. Det viktiga kravet är HTTPS-anslutning.

Testa LUMS-slutpunkten:

```
curl -I \
    https://LUMS-SERVER/

```

Om servern använder en privat CA måste klienten lita på den CA innan du fortsätter. Inaktivera inte TLS-verifiering som en permanent lösning.

## 59. Hämta LUMS-agenten

Agentens källkod ingår i LUMS-repositoryt.

På klienten, hämta repositoryt eller överför de nödvändiga agentfilerna på annat sätt via den godkända distributionsmetoden.

De relevanta filerna är:

* `agent/agent.py`

* `agent/watcher.py`

* `agent/package_manager.py`

Den rekommenderade installationskatalogen är: `/opt/lums-agent`

Skapa den:

```
sudo install -d -m 755 \
    /opt/lums-agent

```

## 60. Installera agentfilerna

Från LUMS-repositoryt:

```
cd /opt/lums-public

```

Installera agenten:

```
sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py

```

Installera Watchern:

```
sudo cp \
    agent/watcher.py \
    /opt/lums-agent/watcher.py

```

Installera pakethanterarabstraktionen:

```
sudo cp \
    agent/package_manager.py \
    /opt/lums-agent/package_manager.py

```

Verifiera:

```
ls -lh \
    /opt/lums-agent/

```

Katalogen bör innehålla de installerade agentkomponenterna.

## 61. Verifiera agentversioner

Verifiera den installerade agentversionen:

```
grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/agent.py

```

Den aktuella versionen är: `1.7.0`

Verifiera Watchern:

```
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py

```

Den aktuella versionen är: `1.2.1`

Om de installerade versionerna inte matchar den avsedda distributionsrevisionen, stoppa och verifiera att rätt repository-revision används.

## 62. Installera systemd-tjänstefiler

Agenten och Watchern använder separata systemd-tjänster.

Installera agenttjänsten:

```
sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service

```

Installera Watcher-tjänsten:

```
sudo cp \
    agent/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent-watcher.service

```

Installera rapporteringstimern:

```
sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer

```

Installera Watcher-timern:

```
sudo cp \
    agent/lums-agent-watcher.timer \
    /etc/systemd/system/lums-agent-watcher.timer

```

Ladda om systemd:

```
sudo systemctl daemon-reload

```

## 63. Verifiera systemd-enheterna

Inspektera agenttjänsten:

```
systemctl cat \
    lums-agent.service

```

Inspektera Watcher-tjänsten:

```
systemctl cat \
    lums-agent-watcher.service

```

Inspektera agenttimern:

```
systemctl cat \
    lums-agent.timer

```

Inspektera Watcher-timern:

```
systemctl cat \
    lums-agent-watcher.timer

```

Enheterna bör referera till de installerade filerna under `/opt/lums-agent/`.

Aktivera inte timers förrän klientkonfigurationen och autentiseringen har slutförts.

## 64. Skapa klientkonfigurationen

Klientkonfigurationen lagras utanför Git-repositoryt.

Använd: `/etc/default/lums-agent`

Skapa filen:

```
sudo install -m 600 /dev/null \
    /etc/default/lums-agent

```

Konfigurationen innehåller LUMS-serverändpunkten och klienttoken. Exempelstruktur:

```
LUMS_BASE=https://LUMS-SERVER
LUMS_TOKEN=<CLIENT-TOKEN>

```

Ersätt `LUMS-SERVER` med den faktiska LUMS-serverändpunkten.

Ersätt `<CLIENT-TOKEN>` med den token som tilldelats denna klient.

Skydda konfigurationen:

```
sudo chmod 600 \
    /etc/default/lums-agent

```

Verifiera utan att visa innehållet:

```
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent

```

*Förväntat:* `600`

## 65. Klienttoken

Varje LUMS-klient har sin egen autentiseringstoken. Token används som:
`Authorization: Bearer <CLIENT-TOKEN>`

Servern behöver inte det ursprungliga tokenvärdet efter etablering. Servern lagrar en kryptografisk representation av token för validering. Detta innebär att klientuppgifter ska behandlas som lösenord.

Placera aldrig en riktig token i:

* Git

* dokumentation

* skärmdumpar

* ärenderapporter

* skalhistorik

* offentlig konfiguration

## 66. Etablera klienttoken

Skapa eller etablera klienten från LUMS administratörsgränssnitt enligt det aktuella klienthanteringsarbetsflödet.

Den resulterande klienttoken måste överföras till den avsedda klienten via en säker kanal. Lagra den endast i `/etc/default/lums-agent` på klienten.

Återanvänd inte en klienttoken på flera maskiner.

Det avsedda förhållandet är:

```
Client A -> Token A
Client B -> Token B
Client C -> Token C

```

En komprometterad token bör därför endast identifiera sin associerade klient.

## 67. Rotation av klienttoken

Klienttoken kan roteras av en administratör.

Rotationsflödet är:

```
Nuvarande token
     ↓
Administratör roterar token
     ↓
Gammal token ogiltigförklaras
     ↓
Ny token utfärdas
     ↓
Klientkonfiguration uppdateras

```

Efter uppdatering av klientkonfigurationen, kör agenten manuellt för att verifiera att autentiseringen lyckas. En roterad token får inte fortsätta att accepteras på obestämd tid.

## 68. TLS-förtroende

LUMS-agenten kommunicerar med servern över HTTPS. Certifikatverifiering måste förbli aktiverad.

För ett offentligt betrott certifikat är operativsystemets normala förtroendelager tillräckligt. För en privat laboratorie-CA, installera CA-certifikatet på klienten.

Lös inte certifikatproblem genom att inaktivera verifiering. Den korrekta lösningen är att få klienten att lita på den avsedda certifikatutfärdaren.

## 69. Debian / Ubuntu TLS-förtroende

På Debian-familjens system kan en privat CA installeras i systemets förtroendelager.

Kopiera CA-certifikatet:

```
sudo cp \
    lums-ca.crt \
    /usr/local/share/ca-certificates/lums-ca.crt

```

Uppdatera förtroendelagret:

```
sudo update-ca-certificates

```

Verifiera att certifikatet accepteras:

```
curl -I \
    https://LUMS-SERVER/

```

Om kommandot lyckas utan `-k` fungerar systemets förtroendekonfiguration.

## 70. Arch Linux TLS-förtroende

På Arch Linux, installera den privata CA med systemets konfigurerade förtroendelagringsmekanism.

Efter installation av CA, uppdatera förtroendedatabasen enligt den aktiva förtroendelagringskonfigurationen.

Verifiera:

```
curl -I \
    https://LUMS-SERVER/

```

Anslutningen bör lyckas utan `-k`. Konfigurera inte agenten permanent att ignorera certifikatverifiering.

## 71. Verifiera pakethanteraren

Agenten detekterar den pakethanteringsfamilj som stöds.

### För Debian/Ubuntu:

```
command -v apt
command -v dpkg-query

```

Verifiera installerade paket:

```
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    | head

```

Verifiera tillgängliga uppdateringar:

```
apt list --upgradable

```

### För Arch Linux:

```
command -v pacman

```

Verifiera installerade paket:

```
pacman -Q | head

```

Verifiera tillgängliga uppdateringar:

```
pacman -Qu

```

Pakethanterarabstraktionen använder automatiskt lämplig implementation.

## 72. Verifiera agentbehörigheter

Inspektera installationskatalogen:

```
ls -ld \
    /opt/lums-agent

```

Inspektera de installerade filerna:

```
ls -lh \
    /opt/lums-agent/

```

Agenten behöver inte skrivåtkomst till sin egen källkatalog.

Klientkonfigurationen förblir skyddad separat:

```
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent

```

*Förväntat:* `600`

Agenten kräver tillräckliga systemprivilegier för att inspektera pakettillstånd och utföra paketoperationer. De exakta körtidsprivilegierna definieras av den installerade systemd-tjänsten.

## 73. Verifiera agentkonfigurationen

Innan du startar tjänsten, verifiera att konfigurationsfilen finns:

```
sudo test -r \
    /etc/default/lums-agent \
    && echo "agent configuration: OK"

```

Skriv inte ut innehållet i konfigurationsfilen.

Verifiera att de nödvändiga variablerna finns utan att exponera token:

```
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

Själva tokenvärdet får inte skrivas ut.

## 74. Testa agenten manuellt

Innan du aktiverar timern, kör agenten en gång manuellt:

```
sudo systemctl start \
    lums-agent.service

```

Kontrollera resultatet:

```
sudo systemctl status \
    lums-agent.service \
    --no-pager

```

Agenten är en one-shot-tjänst. Efter framgångsrikt slutförande kan den visa: `Active: inactive (dead)`. Detta är normalt. Det viktiga resultatet är: `status=0/SUCCESS`.

Inspektera journalen:

```
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

```

## 75. Verifiera den första klientrapporten

En framgångsrik agentkörning bör rapportera klienten till LUMS-servern.

Den fullständiga vägen är:

```
Agent
   ↓
HTTPS
   ↓
Nginx
   ↓
LUMS API
   ↓
Bearer-autentisering
   ↓
Klientuppslagning
   ↓
Rapport accepterad

```

Inspektera serverloggarna vid behov:

```
sudo docker logs \
    --tail 100 \
    lums

```

Klienten bör visas i LUMS webbgränssnitt efter en framgångsrik rapport. Att den lokala tjänsten lyckas är inte tillräckligt i sig. Servern måste acceptera rapporten.

## 76. Verifiera klienten i webbgränssnittet

Logga in som administratör eller operator. Öppna klientöversikten.

Den nya klienten bör rapportera information som:

* Värdnamn

* IP-adress

* Operativsystem

* Arkitektur

* Agentversion

* Senaste rapport

* Installerade paket

* Tillgängliga uppdateringar

Den rapporterade informationen tillhör den klienten. En klient får inte kunna komma åt en annan klients resurser.

## 77. Aktivera rapporteringstimern

Först efter att den manuella agentkörningen lyckas bör rapporteringstimern aktiveras:

```
sudo systemctl enable --now \
    lums-agent.timer

```

Kontrollera:

```
sudo systemctl status \
    lums-agent.timer \
    --no-pager

```

Inspektera schemat:

```
systemctl list-timers \
    lums-agent.timer \
    --no-pager

```

Timern startar periodiskt: `lums-agent.service`. Tjänsten själv förblir en one-shot-enhet. Därför är det normalt att tjänsten återgår till `inactive (dead)` mellan timer-körningarna.

## 78. Verifiera schemalagd rapportering

Efter aktivering av timern, inspektera nästa schemalagda körning:

```
systemctl list-timers \
    --all \
    --no-pager | grep lums-agent

```

Efter att timern har kört, inspektera:

```
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

```

Verifiera motsvarande klientrapport i LUMS.

En frisk rapporteringscykel är:

```
Timer
  ↓
Agenttjänst
  ↓
Systeminventering
  ↓
Paketinventering
  ↓
Uppdateringsdetektering
  ↓
HTTPS-rapport
  ↓
LUMS-databas

```

## 79. Kontrollpunkt för klientinstallation

Innan du installerar execution watchern, verifiera:

* \[ \] Linux-distribution som stöds

* \[ \] Python 3 tillgängligt

* \[ \] systemd tillgängligt

* \[ \] Pakethanterare tillgänglig

* \[ \] Agent installerad

* \[ \] Agentversion verifierad

* \[ \] Watcher-filer installerade

* \[ \] Klientkonfiguration finns

* \[ \] Klienttoken skyddad

* \[ \] TLS-certifikat betrott

* \[ \] Agenttjänst lyckas

* \[ \] Klientrapport accepterad

* \[ \] Klient synlig i LUMS

* \[ \] Rapporteringstimer aktiverad

* \[ \] Schemalagd rapportering verifierad

Fortsätt inte till uppdateringsjobbtestning förrän rapporteringsvägen fungerar. Nästa avsnitt installerar och validerar execution watchern.

## 80. Installera execution watchern

LUMS execution watcher ansvarar för att upptäcka och köra väntande uppdateringsjobb på klienten.

Arkitekturen separerar rapportering från körning:

```
Rapportering
    │
    ▼
lums-agent.service
    │
    └── systeminventering / uppdateringsdetektering

Körning
    │
    ▼
lums-agent-watcher.service
    │
    └── väntande uppdateringsjobb

```

Denna separation gör att vanlig klientrapportering kan fortsätta oberoende av uppdateringskörning.

## 81. Verifiera Watcher-installationen

Verifiera att Watchern finns:

```
ls -lh \
    /opt/lums-agent/watcher.py

```

Verifiera den installerade versionen:

```
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py

```

Den aktuella Watcher-versionen är: `1.2.1`

## 82. Verifiera Watcher-tjänsten

Inspektera systemd-enheten:

```
systemctl cat \
    lums-agent-watcher.service

```

Tjänsten måste referera till: `/opt/lums-agent/watcher.py`

Verifiera att enheten är känd för systemd:

```
systemctl status \
    lums-agent-watcher.service \
    --no-pager

```

Tjänsten kan vara inaktiv när ingen körning har utlösts. Detta är inte i sig ett fel.

## 83. Verifiera Watcher-timern

Innan du aktiverar Watcher-timern, verifiera att:

1. `/etc/default/lums-agent` finns och innehåller korrekt klientkonfiguration.

2. LUMS-serverändpunkten och klienttoken är korrekt konfigurerade.

3. En manuell agentkörning lyckades och servern accepterade klientrapporten.

4. Båda Watcher-enhetsfilerna installerades från repositoryt.

Aktivera inte timern medan autentisering eller rapportering misslyckas.

Inspektera timern:

```
systemctl cat \
    lums-agent-watcher.timer

```

Aktivera timern först efter att ha verifierat alla förutsättningar ovan:

```
sudo systemctl enable --now \
    lums-agent-watcher.timer

```

Verifiera:

```
systemctl status \
    lums-agent-watcher.timer \
    --no-pager

```

Inspektera nästa schemalagda körning:

```
systemctl list-timers \
    lums-agent-watcher.timer \
    --no-pager

```

## 84. Förstå inaktivitetsmedveten körning

Watchern kan använda klientens inaktivitetsinformation innan den kör uppdateringsjobb.

Det avsedda flödet är:

```
Väntande jobb
    │
    ▼
Watcher
    │
    ▼
Inaktivitetsdetektering
    │
    ├── inaktivitetstillstånd tillgängligt
    │       │
    │       ▼
    │   inaktivitetsgräns
    │       │
    │       ▼
    │   kör när tillåtet
    │
    └── inaktivitetstillstånd otillgängligt
            │
            ▼
        använd konfigurerat
        reservbeteende

```

Inaktivitetsdetektering får aldrig tolkas som autentisering eller auktorisering. Det är endast en mekanism för körningsschemaläggning.

## 85. Verifiera inaktivitetsdetektering

Kör inaktivitetsdetekteringsvägen manuellt genom den installerade Agent/Watcher-implementationen.

Inspektera den resulterande tjänstjournalen:

```
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager

```

Om plattformen inte tillhandahåller den nödvändiga inaktivitetsinformationen kan klienten rapportera inaktivitetsdetektering som otillgänglig. Detta är inte automatiskt ett fel.

Den viktiga distinktionen är: `idle_supported = available` versus `idle_supported = unavailable`.

Klienten får inte antas vara inaktiv bara för att ingen inaktivitetsinformation returnerades.

## 86. Skapa ett kontrollerat testuppdateringsjobb

Börja inte installationstestningen med en stor systemuppdatering. Använd ett litet, känt paket för det första testet.

Paketet bör:

* finnas i det konfigurerade repositoryt

* vara säkert att installera

* kunna tas bort igen

* inte krävas av operativsystemet

Exempel på testpaket: `sl`

Innan du skapar jobbet, verifiera om det redan är installerat:

```
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true

```

För Arch Linux, använd ett paket som är tillgängligt i de konfigurerade repositoryna och lämpligt för ett reversibelt test. Använd inte blint `sl` på varje distribution.

## 87. Verifiera paketsökning

Använd LUMS pakethanteringsgränssnitt för att söka efter det valda paketet.

Sökflödet är:

```
Webbläsare
   ↓
LUMS API
   ↓
Paketsökförfrågan
   ↓
Klient
   ↓
APT / pacman
   ↓
Paketsökresultat
   ↓
LUMS API
   ↓
Webbläsare

```

Verifiera att resultatet innehåller förväntad information:

* Paket

* Version

* Beskrivning

* Status

* Åtgärd

För Arch Linux kan även repositoryinformation returneras.

## 88. Behörigheter för pakethantering

Pakethantering begränsas av RBAC.

* **Administratör:** Tillåten

* **Operator:** Tillåten

* **Viewer:** Inte tillåten

En Viewer får inte kunna köra paketinstallation eller borttagning genom att anropa API:et direkt. Att webbläsargränssnittet döljer funktionen är endast en ytterligare användbarhetsbegränsning. Auktoriseringen på serversidan är den faktiska säkerhetsgränsen.

## 89. Testa paketinstallation

Skapa ett installationsjobb via LUMS-gränssnittet.

Den logiska operationen är: `INSTALL_PACKAGE`

Jobbet lagras i LUMS-databasen innan agenten kör det.

Det förväntade flödet är:

```
Skapa jobb
   ↓
PENDING
   ↓
Watcher upptäcker jobb
   ↓
RUNNING
   ↓
Pakethanterare
   ↓
SUCCESS

```

Övervaka jobbet i LUMS-gränssnittet. Ändra inte databasen manuellt för att tvinga fram ett jobbtillstånd.

## 90. Verifiera installationsresultatet

Efter att jobbet rapporterat framgång, verifiera paketet lokalt.

På Debian/Ubuntu:

```
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    sl

```

Verifiera att pakethanteraren instämmer:

```
apt-cache policy \
    sl

```

Paketet måste faktiskt vara installerat. Ett LUMS `SUCCESS`-tillstånd måste motsvara en framgångsrik klientsidig operation.

## 91. Verifiera jobbresultatet

Inspektera LUMS jobbhistorik.

Verifiera:

* Åtgärd

* Paket

* Klient

* Starttid

* Slutförandetid

* Resultat

Resultatet som returneras av klienten måste valideras av servern. Ogiltig eller ofullständig resultatdata får inte tyst omvandlas till ett framgångsrikt jobb. Denna validering är en del av LUMS säkerhets- och tillförlitlighetsmodell.

## 92. Testa borttagning av paket

Efter verifiering av installation, skapa ett borttagningsjobb: `REMOVE_PACKAGE`

Övervaka:

```
PENDING
   ↓
RUNNING
   ↓
SUCCESS

```

Efter slutförande:

```
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true

```

Paketet bör inte längre vara installerat.

Om paketet inte var installerat före testet, behandla inte frånvaron som bevis på en framgångsrik borttagningsoperation.

## 93. Testa paketuppdatering

Paketuppdateringar använder: `UPDATE_PACKAGE`

Servern validerar att det begärda paketet är en tillgänglig uppdatering innan motsvarande jobb skapas.

Det allmänna flödet är:

```
Klient rapporterar tillgängliga uppdateringar
       ↓
Användare väljer paket
       ↓
Servern validerar paketet
       ↓
Uppdateringsjobb skapas
       ↓
Watcher kör
       ↓
Resultat rapporteras

```

Konstruera inte manuellt uppdateringsförfrågningar som kringgår den normala valideringsvägen.

## 94. Testa systemuppdatering

En komplett systemuppdatering använder: `UPDATE_SYSTEM`

Denna operation påverkar klientens pakethanterartillstånd bredare än en enstaka paketoperation.

För det första systemuppdateringstestet:

* Använd en testklient

* Använd en aktuell säkerhetskopia

* Övervaka konsolen

* Övervaka LUMS-jobbet

* Avbryt inte pakethanteraren

Använd inte produktionsservern själv som det första systemuppdateringstestmålet.

## 95. Pakethanterarens lås

APT och pacman kan använda pakethanterarlås.

När en operation misslyckas eftersom en annan pakethanteringsprocess är aktiv, inspektera de körande processerna innan du vidtar åtgärder.

Debian/Ubuntu:

```
ps aux | grep -E \
    '[a]pt|[d]pkg|[u]nattended'

```

Arch Linux:

```
ps aux | grep -E \
    '[p]acman|[p]ar'

```

Ta inte bort pakethanterarens låsfiler medan pakethanteraren faktiskt körs. Ett lås skyddar normalt mot samtidiga paketoperationer.

## 96. Skilj LUMS-fel från pakethanterarfel

När ett jobb misslyckas, avgör vilket lager som misslyckades.

```
LUMS API
   │
   ├── Jobbskapandefel
   │
   ▼
LUMS-databas
   │
   ├── Tillstånds-/persistensproblem
   │
   ▼
Watcher
   │
   ├── Körningsproblem
   │
   ▼
Pakethanterare
   │
   ├── APT / pacman-fel
   │
   ▼
Operativsystem

```

Inspektera klientjournalen:

```
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

```

Inspektera LUMS-containern:

```
sudo docker logs \
    --tail 200 \
    lums

```

Försök inte omedelbart igen med ett misslyckat jobb utan att först avgöra varför det misslyckades.

## 97. Verifiera jobbcheckpointing

LUMS spårar jobb- och paketobjektstillstånd. För paketbaserade jobb kan enskilda paketobjekt checkpointas.

Det avsedda beteendet är:

```
Paket A → SUCCESS
Paket B → SUCCESS
Paket C → RUNNING
             │
             ▼
          avbrott
             │
             ▼
          återställning
             │
             ▼
Paket A → upprepas inte
Paket B → upprepas inte
Paket C → återupptas / hanteras

```

Detta förhindrar att slutförda paketoperationer onödigtvis upprepas efter ett avbrott.

## 98. Testa kontrollerad jobbåterställning

Använd ett icke-kritiskt testjobb. Starta jobbet och observera dess tillstånd: `PENDING` sedan `RUNNING`.

Avbryt inte avsiktligt en produktionsuppdatering. För återställningstestning, använd en dedikerad testklient och en kontrollerad paketoperation.

Efter ett avbrott eller simulerat fel, starta om Watchern:

```
sudo systemctl restart \
    lums-agent-watcher.timer

```

Inspektera sedan:

```
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

```

Verifiera att redan framgångsrika paketobjekt inte onödigtvis körs igen.

## 99. Verifiera omstartsdetektering

Vissa paketoperationer kan kräva en omstart. Agenten/Watchern rapporterar omstartsbehov till LUMS.

Det allmänna flödet är:

```
Paketoperation
      ↓
Omstartsbehov upptäckt
      ↓
Resultat rapporterat
      ↓
LUMS registrerar omstartstillstånd

```

Efter en testoperation som legitimt kräver en omstart, verifiera motsvarande jobbresultat i LUMS-gränssnittet. Starta inte om en produktionsklient bara för att testa mekanismen om inte systemet är avsett för det testet.

## 100. Verifiera rapportering efter omstart

När en testklient har startats om, verifiera att:

```
systemd
   ↓
LUMS Agent timer
   ↓
Agentrapport
   ↓
LUMS-server

```

fortsätter att fungera.

Kontrollera:

```
systemctl status \
    lums-agent.timer \
    --no-pager

```

och:

```
systemctl status \
    lums-agent-watcher.timer \
    --no-pager

```

Inspektera sedan den senaste rapporten i LUMS-gränssnittet.

## 101. Verifiera uppdateringsdetektering

Kör agenten manuellt:

```
sudo systemctl start \
    lums-agent.service

```

Inspektera:

```
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

```

Klienten bör rapportera:

* Installerade paket

* Tillgängliga uppdateringar

* Agentstatus

Servern bör uppdatera klientens aktuella tillstånd.

Blanda inte ihop `tillgängliga uppdateringar` med `installerade paket`. De representerar olika datamängder.

## 102. Verifiera installerad programvara

Öppna klientens avsnitt för installerad programvara i LUMS. Paketlistan bör motsvara den klientsidiga pakethanteraren.

För Debian/Ubuntu:

```
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n'

```

För Arch:

```
pacman -Q

```

LUMS-inventeringen är informativ tills ett jobb uttryckligen skapas. Filtret för installerade paket ändrar inte klienten själv.

## 103. Verifiera paketsökning separat

Pakethanteringssökningen är separat från filtret för installerade paket.

Distinktionen är:

* **Filter för installerade paket:** Söker i paketinventeringen som redan rapporterats av klienten.

* **Pakethanteringssökning:** Begär paketinformation från klientens pakethanterare.

Behandla inte de två sökfunktionerna som utbytbara. Ett paket kan vara tillgängligt via APT eller pacman utan att vara installerat.

## 104. Verifiera Viewer-paketisolering

Logga in som Viewer. Verifiera att pakethanteringsgränssnittet inte är tillgängligt.

Verifiera sedan serverbegränsningen genom att försöka en obehörig pakethanteringsförfrågan via en godkänd testmetod. Förfrågan måste avvisas.

Viewer-åtkomst måste förbli skrivskyddad.

## 105. Verifiera operatorpakethantering

Logga in som Operator.

Verifiera åtkomst till:

* Paketsökning

* Paketinstallation

* Borttagning av paket

* Paketuppdateringar

* Uppdateringsjobb

* Uppdateringshistorik

Operatören får inte få åtkomst till endast-administratörsfunktioner för användarhantering.

## 106. Verifiera administratörspakethantering

Logga in som Administrator.

Verifiera samma pakethanteringsfunktioner som Operatorn. Verifiera dessutom åtkomst till:

* Användarhantering

* Klienthantering

* Rotation av klienttoken

Administratörsbehörigheter måste förbli upprätthållna på serversidan.

## 107. Första end-to-end-pakettest

Det första kompletta pakethanteringstestet bör följa denna sekvens:

 1. Klienten rapporterar framgångsrikt

 2. Paketsökning lyckas

 3. Paketresultat visas

 4. Administratör/Operator skapar `INSTALL_PACKAGE`-jobb

 5. Jobbet blir `PENDING`

 6. Watchern upptäcker jobbet

 7. Jobbet blir `RUNNING`

 8. Pakethanteraren kör

 9. Klienten rapporterar resultat

10. Servern validerar resultat

11. Jobbet blir `SUCCESS`

12. Installerat paket verifieras lokalt

13. Paketet är synligt i LUMS-inventeringen

Först efter att denna sekvens lyckas bör bredare uppdateringstestning börja.

## 108. Kontrollpunkt för klientkörning

Verifiera:

* \[ \] Watcher installerad

* \[ \] Watcher-version verifierad

* \[ \] Watcher-timer aktiverad

* \[ \] Inaktivitetsdetektering fungerar eller rapporterar otillgänglig korrekt

* \[ \] Paketsökning fungerar

* \[ \] Paketinstallation fungerar

* \[ \] Borttagning av paket fungerar

* \[ \] Paketuppdatering fungerar

* \[ \] Systemuppdateringsväg är tillgänglig

* \[ \] Jobbtillstånd övergår korrekt

* \[ \] Jobbresultat valideras

* \[ \] Paketcheckpointing fungerar

* \[ \] Omstartsdetektering fungerar

* \[ \] Rapportering fortsätter efter omstart

* \[ \] Viewer kan inte ändra pakettillstånd

* \[ \] Operator kan hantera paket

* \[ \] Administratör kan hantera paket

Vid detta lag är LUMS kärnkörningsväg för klienten installerad och validerad. Nästa avsnitt täcker fullständig end-to-end-validering, RBAC-verifiering, säkerhetskopiering/återställning, underhåll, uppgraderingar och slutliga installationskontroller.

## 109. Fullständig end-to-end-validering

Efter att servern och minst en Linux-klient har konfigurerats, utför en fullständig end-to-end-validering.

Den fullständiga LUMS-vägen är:

```
Webbläsare
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
Klientagent
   │
   ▼
Pakethanterare
   │
   ▼
Uppdateringsresultat
   │
   ▼
SQLite
   │
   ▼
Webbgränssnitt

```

Anse inte installationen som komplett bara för att webbgränssnittet öppnas. Alla huvudlager måste verifieras.

## 110. Serverhälsokontroll

Verifiera LUMS-containern:

```
sudo docker ps \
    --filter name=lums

```

Verifiera containertillståndet:

```
sudo docker inspect \
    lums \
    --format '{{.State.Status}}'

```

*Förväntat:* `running`

Inspektera de senaste loggarna:

```
sudo docker logs \
    --tail 100 \
    lums

```

Loggarna bör inte innehålla ett aktivt start- eller migreringsfel.

## 111. Containersäkerhetskontroll

Verifiera körtidssäkerhetskonfigurationen:

```
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'

```

Förväntad baslinje:

```
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]

```

Verifiera nätverksbindningen:

```
sudo docker port \
    lums

```

*Förväntat:* `5000/tcp -> 127.0.0.1:5050`

## 112. Kontroll av beständig lagring

Verifiera LUMS-volymen:

```
sudo docker volume inspect \
    lums-data

```

Verifiera att applikationsdatabasen finns:

```
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db

```

Databasen måste finnas i beständig lagring. Lagra inte produktionsdatabasen endast inuti containerfilsystemet.

## 113. SQLite-hälsokontroll

Inspektera den aktuella SQLite-körtidskonfigurationen:

```
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

Den nuvarande baslinjen är:

```
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0

```

Applikationen aktiverar uttryckligen främmandenyckelkontroll.

## 114. SQLite-integritetskontroll

Kör:

```
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

*Förväntat:* `ok`

Fortsätt inte med en ny produktionsutrullning om integritetskontrollen rapporterar korruption.

## 115. Verifiera databasmigreringar

Inspektera migreringstillståndet:

```
sudo docker logs \
    --tail 200 \
    lums | grep -i migration

```

Applikationen måste slutföra sina konfigurerade migreringar innan normal drift. Ändra inte manuellt migreringstillståndstabellen om inte den aktuella LUMS-migreringsproceduren uttryckligen kräver det.

## 116. Kör den automatiska testsviten

På LUMS utvecklings-/testmiljö:

```
cd /opt/lums-public

```

Kör:

```
./.venv-test/bin/pytest -q

```

Antalet tester ändras i takt med att projektet utvecklas; förlita dig på kommandots resultat, inte ett fast antal i detta dokument.

Det viktiga kravet är: **alla tester godkänns**. Ignorera inte misslyckade tester för att produktionswebbgränssnittet verkar fungera.

## 117. Verifiera RBAC

Den nuvarande rollmodellen är:

| Funktion | Administratör | Operator | Viewer |
| ----- | ----- | ----- | ----- |
| **Visa klienter** | Ja | Ja | Ja |
| **Installerad programvara** | Ja | Ja | Ja |
| **Tillgängliga uppdateringar** | Ja | Ja | Nej |
| **Skapa/köra jobb** | Ja | Ja | Nej |
| **Uppdateringshistorik** | Ja | Ja | Nej |
| **Pakethantering** | Ja | Ja | Nej |
| **Systemunderhåll** | Ja | Ja | Nej |
| **Skapa/inaktivera klienter** | Ja | Nej | Nej |
| **Rotera klienttoken** | Ja | Nej | Nej |
| **Användarhantering** | Ja | Nej | Nej |
| **Rollhantering** | Ja | Nej | Nej |

Gränssnittet bör återspegla dessa behörigheter. Ännu viktigare, API:et måste upprätthålla dem oberoende.

## 118. Verifiera administratörsåtkomst

Logga in som Administrator.

Verifiera åtkomst till:

* Klienter

* Installerad programvara

* Tillgängliga uppdateringar

* Uppdateringsjobb

* Uppdateringshistorik

* Pakethantering

* Systemunderhåll

* Användarhantering

Verifiera klienthanteringsfunktioner:

* Skapa klient

* Inaktivera klient

* Rotera klienttoken

Administratören bör kunna utföra dessa operationer.

## 119. Verifiera operatoråtkomst

Logga in som Operator.

Verifiera åtkomst till:

* Klienter

* Installerad programvara

* Tillgängliga uppdateringar

* Uppdateringsjobb

* Uppdateringshistorik

* Pakethantering

* Systemunderhåll

Verifiera att endast-administratörsfunktioner är otillgängliga:

* Användarhantering

* Rollhantering

* Skapande/inaktivering av klienter

* Rotation av klienttoken

Förlita dig inte bara på dolda UI-element. Skyddade API-operationer måste avvisa obehöriga förfrågningar.

## 120. Verifiera Viewer-åtkomst

Logga in som Viewer. Viewern bör kunna komma åt:

* Klienter

* Installerad programvara

Följande får inte vara tillgängliga:

* Tillgängliga uppdateringar

* Uppdateringsjobb

* Uppdateringshistorik

* Pakethantering

* Systemunderhåll

Viewern får inte kunna ändra klienttillstånd.

## 121. Verifiera klientautentisering

Bekräfta att varje klient använder sin egen Bearer-token.

Den förväntade modellen är:

```
Client A → Token A
Client B → Token B
Client C → Token C

```

Dela inte token mellan klienter. Verifiera att en roterad eller återkallad token inte längre accepteras.

Placera aldrig riktiga token i testutdata eller dokumentation.

## 122. Verifiera uppdateringsdetektering

På en testklient:

```
sudo systemctl start \
    lums-agent.service

```

Inspektera:

```
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

```

Verifiera sedan klienten i LUMS-gränssnittet. Den rapporterade informationen bör innehålla aktuell paketinventering och uppdateringsinformation där det stöds.

## 123. Verifiera skapande av uppdateringsjobb

Skapa ett kontrollerat uppdateringsjobb via LUMS-gränssnittet.

Jobbet bör initialt visas som: `PENDING`

Watchern bearbetar sedan jobbet:

```
PENDING
   ↓
RUNNING
   ↓
SUCCESS

```

eller:

```
PENDING
   ↓
RUNNING
   ↓
FAILED

```

beroende på det faktiska operationsresultatet. Ändra inte databastillståndet manuellt.

## 124. Verifiera jobbkörning

Inspektera klientens Watcher:

```
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

```

Inspektera LUMS-servern:

```
sudo docker logs \
    --tail 200 \
    lums

```

Jämför jobbtillståndet på serversidan med körningsresultatet på klientsidan. De två måste stämma överens.

## 125. Verifiera validering av paketresultat

Ett jobb får inte bli framgångsrikt bara för att klienten skickade ett syntaktiskt giltigt svar. Servern validerar det returnerade resultatet.

Verifiera detta genom de automatiska resultatvalideringstesterna:

```
./.venv-test/bin/pytest -q \
    tests/test_job_result.py

```

Ett framgångsrikt resultat måste innehålla förväntad struktur och giltig jobbkontext. Felaktiga eller inkonsekventa resultat måste avvisas.

## 126. Verifiera jobbåterställning

Använd en dedikerad testklient för återställningstestning.

Återställningsmodellen är:

```
Jobb
 │
 ├── paketobjekt A → SUCCESS
 ├── paketobjekt B → SUCCESS
 └── paketobjekt C → avbrutet
                       │
                       ▼
                    återställning
                       │
                       ▼
                  återuppta säkert

```

Efter återställning får tidigare framgångsrika paketobjekt inte onödigtvis upprepas.

Inspektera:

```
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

```

Verifiera sedan det slutliga jobbtillståndet i LUMS.

## 127. Verifiera omstartsdetektering

För en kontrollerad testuppdatering som kräver omstart, verifiera att klienten rapporterar omstartsbehovet.

Efter omstart:

```
systemctl status \
    lums-agent.timer \
    --no-pager

```

och:

```
systemctl status \
    lums-agent-watcher.timer \
    --no-pager

```

Klienten måste återuppta normal rapportering efter start.

## 128. Verifiera granskningsloggning

Utför en kontrollerad administrativ åtgärd och inspektera sedan LUMS granskningslogg.

Relevanta operationer inkluderar:

* Inloggning

* Skapande av användare

* Skapande av klient

* Rotation av klienttoken

* Skapande av jobb

* Pakethantering

Granskningsposter bör ge tillräcklig information för att rekonstruera den administrativa åtgärden utan att exponera hemligheter.

Logga inte:

* Lösenord

* Klienttoken

* Applikationshemligheter

* Privata nycklar

* Sessionshemligheter

## 129. Verifiera loggredigering

Inspektera de senaste loggarna:

```
sudo docker logs \
    --tail 200 \
    lums

```

Inspektera klientloggar:

```
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

```

och:

```
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

```

Autentiseringsuppgifter och hemligheter får inte förekomma i normal diagnostisk utdata.

Om ett diagnostiskt kommando skulle exponera en hemlighet, klistra inte in dess utdata i ett ärende, en commit eller dokumentation.

## 130. Verifiera nätverksexponering

Inspektera lyssnande portar:

```
sudo ss -lntp

```

LUMS-applikationsporten bör förbli: `127.0.0.1:5050`

Nginx tillhandahåller den externa tjänsten: `:80`, `:443`

Applikationen får inte exponeras direkt via `0.0.0.0:5050` eller `0.0.0.0:5000`.

## 131. Verifiera brandväggskonfiguration

Om en värdbrandvägg är aktiverad, inspektera den:

```
sudo ufw status verbose

```

Distributionen bör endast exponera de tjänster som krävs av värden. Skapa inte en brandväggsregel för port 5050 bara för att Docker använder den porten internt.

Den avsedda arkitekturen är:

```
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

## 132. Säkerhetskopieringsstrategi

LUMS SQLite-databas är beständigt applikationstillstånd.

Åtminstone bör säkerhetskopior skydda:

* LUMS-databas

* TLS-material

* LUMS applikationshemlighet

* Distributionskonfiguration

Säkerhetskopior måste lagras utanför den aktiva LUMS-containern. Lagra inte säkerhetskopior inuti `/app` eller förlita dig på containerfilsystemet.

Docker-volymen `lums-data` innehåller beständig applikationsdata, men en Docker-volym är inte i sig en säkerhetskopia.

## 133. Databassäkerhetskopiering

Innan du säkerhetskopierar databasen, identifiera databasfilen:

```
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db

```

En databassäkerhetskopiering bör utföras med en konsekvent SQLite-säkerhetskopieringsmekanism. Kopiera inte en live SQLite-databas blint medan den modifieras om säkerhetskopieringsproceduren inte kan garantera konsekvens.

Efter att ha skapat en säkerhetskopia, verifiera att säkerhetskopieringsfilen finns och är skyddad.

## 134. Konfigurationssäkerhetskopiering

Skydda följande distributionsmaterial:

* `/etc/lums/secrets/`

* `/etc/lums/tls/`

* `/etc/nginx/sites-available/lums`

* `/etc/nginx/sites-enabled/lums`

Publicera inte dessa filer. Följande filer är särskilt känsliga:

* `/etc/lums/secrets/lums_secret`

* `/etc/lums/tls/lums.key`

Skydda säkerhetskopieringsbehörigheterna därefter.

## 135. Planering av återställning

En återställning bör testas på ett icke-produktionssystem innan den behövs för katastrofåterställning.

Återställningssekvensen är konceptuellt:

```
Säkerhetskopia
  ↓
Verifiera säkerhetskopians integritet
  ↓
Förbered ren LUMS-värd
  ↓
Återställ hemlighet/konfiguration
  ↓
Återställ databas
  ↓
Återställ TLS-material
  ↓
Starta LUMS
  ↓
Kör integritetskontroller
  ↓
Validera användare/klienter/jobb

```

Skriv inte över en produktionsdatabas utan att först bevara det befintliga tillståndet.

## 136. Verifiera en databasåterställning

Efter återställning av en databas, kör:

```
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

*Förväntat:* `ok`

Verifiera sedan:

* användare

* klienter

* uppdateringsjobb

* paketdata

* granskningsdata

Anta inte att en framgångsrik SQLite-integritetskontroll bevisar att det fullständiga applikationstillståndet är korrekt.

## 137. Underhållsprinciper

Rutinmässigt underhåll bör följa:

```
Observera
   ↓
Säkerhetskopiera
   ↓
Ändra
   ↓
Verifiera

```

Utför inte orelaterat underhåll under ett aktivt uppdateringsjobb.

Före underhåll:

```
sudo docker ps \
    --filter name=lums

```

Kontrollera aktiva jobb i LUMS-gränssnittet. Om en uppdatering körs, låt den slutföras om inte underhållsoperationen specifikt kräver avbrott.

## 138. Containerunderhåll

Inspektera den körande avbildningen:

```
sudo docker inspect \
    lums \
    --format '{{.Config.Image}}'

```

Inspektera containern:

```
sudo docker ps \
    --filter name=lums

```

Inspektera de senaste loggarna:

```
sudo docker logs \
    --tail 100 \
    lums

```

Ta inte bort den beständiga volymen under vanligt containerunderhåll. Volymen innehåller applikationstillstånd.

## 139. Avbildningsunderhåll

Innan du ersätter produktionsavbildningen:

```
cd /opt/lums-public

```

Kör de automatiska testerna:

```
./.venv-test/bin/pytest -q

```

Bygg den nya avbildningen:

```
sudo docker build \
    -t lums:new \
    .

```

Ersätt inte den körande containern förrän avbildningen har klarat den nödvändiga valideringen. Behåll den för närvarande fungerande containern tillgänglig tills ersättningen har verifierats.

## 140. Kontrollerat containerbyte

När du ersätter produktionscontainern:

```
Nuvarande container
       │
       ▼
Säkerhetskopia / kontrollpunkt
       │
       ▼
Bygg ny avbildning
       │
       ▼
Validera avbildning
       │
       ▼
Stoppa gammal container
       │
       ▼
Starta ny container
       │
       ▼
Validera körtid
       │
       ▼
Validera HTTPS
       │
       ▼
Validera applikation

```

Den beständiga volymen måste förbli: `lums-data`

Hemlighetsmonteringen måste förbli skrivskyddad. Applikationsporten måste förbli endast localhost.

## 141. Verifiera körtidssäkerhet efter byte

Efter varje containerbyte, upprepa:

```
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'

```

Verifiera:

```
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]

```

Verifiera också:

```
sudo docker port \
    lums

```

*Förväntat:* `5000/tcp -> 127.0.0.1:5050`

## 142. Verifiera beständig data efter byte

Efter att ha startat ersättningscontainern:

```
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db

```

Sedan:

```
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY

```

*Förväntat:* `ok`

Verifiera slutligen att befintliga användare och klienter fortfarande finns via LUMS-gränssnittet.

## 143. Kontrollpunkt för underhållsavslut

Efter underhåll, verifiera:

* \[ \] Container körs

* \[ \] Körtidshärdning intakt

* \[ \] Beständig volym monterad

* \[ \] Databas tillgänglig

* \[ \] SQLite-integritetskontroll godkänns

* \[ \] Nginx körs

* \[ \] HTTPS fungerar

* \[ \] Inloggning fungerar

* \[ \] Befintliga användare finns

* \[ \] Befintliga klienter finns

* \[ \] Agentrapportering fungerar

* \[ \] Watcher fungerar

* \[ \] Uppdateringsjobb fungerar

* \[ \] Granskningsloggning fungerar

Först efter dessa kontroller är underhållsoperationen klar.

## 144. Installationstillstånd vid denna punkt

En korrekt installerad LUMS-miljö består nu av:

```
                    ┌──────────────────────┐
                    │       Webbläsare     │
                    └──────────┬───────────┘
                               │ HTTPS
                               ▼
                    ┌──────────────────────┐
                    │        Nginx         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    LUMS-container    │
                    │                      │
                    │ Flask / Gunicorn     │
                    │ RBAC                 │
                    │ CSRF                 │
                    │ Granskningsloggning  │
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
        Inventering / Rapport         Uppdateringsjobb
               │                             │
               └──────────────┬──────────────┘
                              ▼
                       APT / pacman

```

Detta är den avsedda operativa arkitekturen. Nästa avsnitt täcker uppgraderingar, avinstallation och den slutliga installationschecklistan.

## 145. Uppgraderingsprocedur

LUMS-uppgraderingar bör utföras i kontrollerade steg.

Den rekommenderade sekvensen är:

```
Granska
   ↓
Säkerhetskopiera
   ↓
Testa
   ↓
Bygg
   ↓
Distribuera
   ↓
Validera

```

Uppgradera inte produktionsinstallationen bara för att en ny Git-revision finns.

Granska ändringarna först:

```
cd /opt/lums-public

git status
git log --oneline -10

```

Granska relevanta applikations-, agent- och migreringsändringar före distribution.

## 146. Skapa en säkerhetskopia före uppgradering

Innan du ersätter produktionscontainern, skapa en aktuell säkerhetskopia av det beständiga LUMS-tillståndet.

Verifiera den aktiva volymen:

```
sudo docker inspect \
    lums \
    --format '{{json .Mounts}}'

```

Bekräfta att `lums-data` fortfarande är monterad på `/var/lib/lums`.

Skydda också den externa konfigurationen:

* `/etc/lums/secrets/`

* `/etc/lums/tls/`

* `/etc/nginx/`

Fortsätt inte med en uppgradering om den nödvändiga säkerhetskopian inte kan verifieras.

## 147. Stoppa onödiga ändringar under en uppgradering

Innan uppgradering, inspektera aktiva jobb i LUMS-gränssnittet. Undvik att ersätta applikationen medan ett kritiskt uppdateringsjobb aktivt körs.

Om nödvändigt, vänta tills jobbet når ett sluttillstånd: `SUCCESS` eller `FAILED`.

Ändra inte manuellt ett jobb från `RUNNING` till `SUCCESS` eller `FAILED` bara för att göra en uppgradering möjlig.

## 148. Uppdatera repositoryt

Gå till repositoryt:

```
cd /opt/lums-public

```

Inspektera det aktuella tillståndet:

```
git status

```

Uppdatera repositoryt med projektets normala arbetsflöde.

Efter uppdatering:

```
git log --oneline -5

```

Verifiera att den avsedda revisionen är utcheckad. Distribuera inte ett repository som innehåller oavsiktliga lokala ändringar.

Om lokala ändringar finns:

```
git status

```

Granska dem innan du fortsätter.

## 149. Kör testsviten före bygge

Kör:

```
./.venv-test/bin/pytest -q

```

Alla tester måste godkännas. Ett ändrat testantal är inte automatiskt ett problem. Kravet är att den fullständiga sviten slutförs framgångsrikt.

## 150. Bygg den uppdaterade avbildningen

Bygg en ny avbildning utan att omedelbart ersätta den körande containern:

```
sudo docker build \
    -t lums:new \
    .

```

Verifiera avbildningen:

```
sudo docker image inspect \
    lums:new

```

Bygget måste slutföras framgångsrikt. Använd inte en misslyckad eller delvis byggd avbildning för produktionsdistribution.

## 151. Verifiera den uppdaterade avbildningen

Granska avbildningens metadata:

```
sudo docker image inspect \
    lums:new \
    --format '
User={{.Config.User}}
Entrypoint={{json .Config.Entrypoint}}
Cmd={{json .Config.Cmd}}
'

```

Avbildningen måste bevara den förväntade icke-root-applikationsmodellen.

Produktionskörtiden måste fortfarande tillhandahålla:

* skrivskyddat rotfilsystem

* borttagna Linux-kapaciteter

* `no-new-privileges`

* skrivskyddad hemlighetsmontering

* beständig applikationsvolym

* applikationsport endast localhost

## 152. Ersätt produktionscontainern

När den nya avbildningen har klarat validering, ersätt den körande containern med den etablerade härdade konfigurationen.

Stoppa den befintliga containern:

```
sudo docker stop \
    lums

```

Ta endast bort containern:

```
sudo docker rm \
    lums

```

*Ta inte bort:* `lums-data`

Starta ersättningen med den härdade körtiden:

```
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

## 153. Verifiera ersättningscontainern

Kontrollera:

```
sudo docker ps \
    --filter name=lums

```

Sedan:

```
sudo docker logs \
    --tail 100 \
    lums

```

Verifiera körtiden:

```
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'

```

Förväntat:

```
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]

```

## 154. Verifiera applikationstillgänglighet

Kontrollera den lokala applikationsslutpunkten:

```
curl -I \
    http://127.0.0.1:5050/

```

Testa sedan den publika HTTPS-vägen:

```
curl -I \
    https://LUMS-SERVER/

```

Verifiera inloggning via webbläsaren. Anse inte uppgraderingen som klar förrän den externa HTTPS-vägen också har testats.

## 155. Verifiera beständigt tillstånd efter uppgradering

Kontrollera databasen:

```
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db

```

Kör:

```
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY

```

*Förväntat:* `ok`

Verifiera via webbgränssnittet att:

* användare

* klienter

* jobb

* granskningshistorik

* paketinformation

fortfarande är tillgängliga.

## 156. Verifiera klientkommunikation efter uppgradering

Kör agenten på en testklient:

```
sudo systemctl start \
    lums-agent.service

```

Inspektera:

```
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

```

Verifiera att servern accepterar rapporten. Verifiera sedan klienten i LUMS-gränssnittet.

## 157. Verifiera uppdateringskörning efter uppgradering

Skapa ett kontrollerat testjobb.

Verifiera:

```
PENDING
   ↓
RUNNING
   ↓
SUCCESS

```

eller ett förväntat `FAILED`-tillstånd när operationen genuint misslyckas.

Inspektera Watchern:

```
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

```

Detta bekräftar att uppgraderingen inte bröt körningsvägen.

## 158. Verifiera säkerhetsbaslinje efter uppgradering

Varje produktionsuppgradering måste bevara säkerhetsbaslinjen.

Verifiera:

* \[ \] HTTPS

* \[ \] Bearer-klientautentisering

* \[ \] RBAC

* \[ \] CSRF-skydd

* \[ \] Granskningsloggning

* \[ \] Icke-root-container

* \[ \] Skrivskyddat rotfilsystem

* \[ \] Borttagna kapaciteter

* \[ \] `no-new-privileges`

* \[ \] Skyddad hemlighetsmontering

* \[ \] Beständig datavolym

* \[ \] Docker-port endast localhost

* \[ \] Brandväggspolicy

En funktionell uppgradering som försvagar dessa egenskaper anses inte vara komplett.

## 159. Återställningsprocedur

Om den nya containern misslyckas med valideringen, förstör inte omedelbart den tidigare distributionsinformationen.

Inspektera först:

```
sudo docker logs \
    --tail 200 \
    lums

```

Om den tidigare avbildningen fortfarande är tillgänglig:

```
sudo docker images

```

återställ den tidigare validerade avbildningen med samma härdade containerkonfiguration.

Den beständiga volymen förblir: `lums-data`

Återställ inte en databassäkerhetskopia bara för att applikationscontainern ersattes. Återställ endast databasen när själva databasen måste återställas.

## 160. Förberedelse för avinstallation

Innan du avinstallerar LUMS, bestäm om den beständiga applikationsdatan måste behållas.

Följande är separata resurser:

* Container

* Avbildning

* Beständig volym

* Konfiguration

* TLS-material

* Nginx-konfiguration

* Klientinstallationer

Att ta bort containern tar inte bort Docker-volymen. Denna distinktion är avsiktlig.

## 161. Ta bort LUMS-containern

Stoppa containern:

```
sudo docker stop \
    lums

```

Ta bort den:

```
sudo docker rm \
    lums

```

Verifiera:

```
sudo docker ps -a \
    --filter name=lums

```

Den beständiga volymen finns fortfarande om den inte uttryckligen tagits bort.

## 162. Ta bort LUMS Docker-avbildning

Lista avbildningar:

```
sudo docker images \
    'lums*'

```

Ta bara bort avbildningar som inte längre behövs:

```
sudo docker rmi \
    lums:new

```

Upprepa för andra föråldrade lokala LUMS-avbildningar efter behov.

Ta inte bort avbildningen som för närvarande krävs för en återställning innan installationen har avvecklats helt.

## 163. Ta bort den beständiga volymen

> \[!CAUTION\]
> Utför endast detta steg när LUMS-databasen inte längre behövs.

Verifiera:

```
sudo docker volume inspect \
    lums-data

```

Skapa en slutlig säkerhetskopia om det behövs.

Ta sedan bort:

```
sudo docker volume rm \
    lums-data

```

Detta tar permanent bort den beständiga applikationsdata som lagras i volymen. Kör inte detta kommando under normala uppgraderingar.

## 164. Ta bort LUMS-serverkonfiguration

När servern permanent avvecklas, ta bort den LUMS-specifika konfigurationen:

* `/etc/lums/`

* `/etc/nginx/sites-available/lums`

* `/etc/nginx/sites-enabled/lums`

Ta bort Nginx-platsen:

```
sudo rm -f \
    /etc/nginx/sites-enabled/lums

```

Ta bort konfigurationen:

```
sudo rm -f \
    /etc/nginx/sites-available/lums

```

Validera sedan Nginx:

```
sudo nginx -t

```

Ladda om:

```
sudo systemctl reload nginx

```

Ta endast bort `/etc/lums/` efter att ha verifierat att ingen annan applikation är beroende av den.

## 165. Ta bort klientinstallationer

LUMS-klienter måste avvecklas separat.

Inaktivera agenttimern:

```
sudo systemctl disable --now \
    lums-agent.timer

```

Inaktivera Watcher-timern:

```
sudo systemctl disable --now \
    lums-agent-watcher.timer

```

Stoppa eventuella kvarvarande tjänster:

```
sudo systemctl stop \
    lums-agent.service \
    lums-agent-watcher.service

```

Ta bort de installerade systemd-enheterna:

```
sudo rm -f \
    /etc/systemd/system/lums-agent.service \
    /etc/systemd/system/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent.timer \
    /etc/systemd/system/lums-agent-watcher.timer

```

Ladda om systemd:

```
sudo systemctl daemon-reload

```

Ta bort agentinstallationen:

```
sudo rm -rf \
    /opt/lums-agent

```

Ta bort klientkonfigurationen:

```
sudo rm -f /etc/default/lums-agent

```

# 166. Slutlig checklista för serverinstallationen

En slutförd LUMS-installation ska uppfylla allt följande:

```text
SERVER
[ ] Debian/Linux-värd förberedd
[ ] Docker installerat
[ ] Nginx installerat
[ ] Repository driftsatt
[ ] Applikationshemlighet skapad
[ ] TLS-material installerat
[ ] LUMS-image byggd
[ ] Beständig volym skapad
[ ] Härdad container driftsatt
[ ] Containern körs som icke-root
[ ] Rotfilsystemet är skrivskyddat
[ ] Linux-funktioner har tagits bort
[ ] no-new-privileges aktiverat
[ ] Hemligheten monterad skrivskyddat
[ ] Beständig datavolym monterad
[ ] Applikationen bunden till 127.0.0.1:5050
[ ] Nginx HTTPS konfigurerat
[ ] HTTP omdirigeras till HTTPS
[ ] TLS verifierat
[ ] Databas initierad
[ ] SQLite-integritetskontroll godkänd
[ ] Migreringar slutförda
```

# 167. Slutlig checklista för klientinstallationen

```text
CLIENT
[ ] Linuxdistribution stöds
[ ] systemd tillgängligt
[ ] Agent installerad
[ ] Agentversion verifierad
[ ] Watcher installerad
[ ] Watcher-version verifierad
[ ] Klientkonfiguration skyddad
[ ] Unik klienttoken konfigurerad
[ ] TLS-förtroende konfigurerat
[ ] Manuell agentkörning lyckas
[ ] Initial rapport godkänd
[ ] Klienten synlig i LUMS
[ ] Rapporteringstimern aktiverad
[ ] Watcher-timern aktiverad
[ ] Inaktivitetsdetektering verifierad
[ ] Programvaruinventering verifierad
[ ] Uppdateringsdetektering verifierad
```

# 168. Slutlig funktionschecklista

```text
FUNCTIONALITY
[ ] Administratörsinloggning fungerar
[ ] Operatörsinloggning fungerar
[ ] Viewer-inloggning fungerar
[ ] Administratörens RBAC verifierad
[ ] Operatörens RBAC verifierad
[ ] Viewers RBAC verifierad
[ ] Klientautentisering verifierad
[ ] Tokenrotation verifierad
[ ] Paketsökning verifierad
[ ] Paketinstallation verifierad
[ ] Paketborttagning verifierad
[ ] Paketuppdatering verifierad
[ ] Sökväg för systemuppdatering verifierad
[ ] Uppdateringsjobb verifierade
[ ] Validering av jobbresultat verifierad
[ ] Jobbåterställning verifierad
[ ] Omstartsdetektering verifierad
[ ] Revisionsloggning verifierad
[ ] Loggar innehåller inga hemligheter
[ ] Rapportering från början till slut verifierad
[ ] Uppdateringskörning från början till slut verifierad
```

# 169. Slutlig säkerhetschecklista

```text
SECURITY
[ ] HTTPS tvingas
[ ] Klientautentisering aktiverad
[ ] RBAC tillämpas på serversidan
[ ] CSRF-skydd aktiverat
[ ] Sessionsskydd aktiverat
[ ] Hastighetsbegränsning för inloggning aktiverad
[ ] Lösenordshashning aktiverad
[ ] Hashning av klienttoken aktiverad
[ ] Rotation av klienttoken tillgänglig
[ ] Granskningsloggning aktiverad
[ ] Hemligheter utanför Git
[ ] Hemligheter utanför Docker-imagen
[ ] TLS-privatnyckel skyddad
[ ] Docker-rotfilsystem skrivskyddat
[ ] Linux-funktioner borttagna
[ ] no-new-privileges aktiverat
[ ] Containern körs som icke-root
[ ] Beständiga data isolerade i volym
[ ] Applikationsporten endast tillgänglig lokalt
[ ] Brandvägg granskad
[ ] Nginx standardwebbplats borttagen eller kontrollerad
[ ] Säkerhetskopieringsprocedur definierad
[ ] Återställningsprocedur testad
```

# 170. Slutlig testchecklista

Kör hela den automatiserade testsviten:

```bash
cd /opt/lums-public

./.venv-test/bin/pytest -q
```

Installationen ska betraktas som slutförd först när hela testsviten har godkänts.

Verifiera sedan produktionsmiljön manuellt:

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

# 171. Slutlig dokumentationskontroll

Innan installationen förklaras slutförd kontrollerar du att dokumentationen motsvarar den faktiska driftsättningen.

Granska minst:

```text
install.md
security.md
troubleshooting.md
administration.md
docs/README.md
```

De tekniska guiderna i roten underhålls på engelska och är den auktoritativa källan. Lokaliserade handböcker och snabbguider listas i [`docs/README.md`](../../README.md); översättningarnas täckning kan variera, så använd den engelska källan om en lokaliserad instruktion är ofullständig eller avviker.

Dokumentationen får inte innehålla:

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

Om driftsättningen ändras ska dokumentationen uppdateras tillsammans med implementationen.

# 172. Releaseberedskap

En lyckad installation innebär inte automatiskt att LUMS har en officiell release.

Projektets aktuella tillstånd skiljer avsiktligt mellan:

```text
Working implementation
Security audit
Documentation review
Release preparation
Versioning
Git tag
GitHub Release
```

En officiell LUMS-release bör skapas först när hela implementationen, säkerhetsgranskningen, dokumentationsgranskningen och den slutliga valideringen är slutförda.

Fram till dess ska repositoryt betraktas som ett aktivt utvecklingsprojekt.

# 173. Operativ baslinje

Den aktuella dokumenterade baslinjen är:

```text
LUMS Server
    Docker
    Nginx
    HTTPS
    SQLite
    RBAC
    CSRF
    Revisionsloggning
    Härdad container

LUMS Agent
    Version 1.7.0

LUMS Watcher
    Version 1.2.1

Databas
    journal_mode=wal
    busy_timeout=5000
    synchronous=2
    foreign_keys=ON (application connections)

Container
    icke-root-användare
    skrivskyddat rotfilsystem
    CapDrop=ALL
    no-new-privileges
    applikationsport endast på localhost

Roles
    Administrator
    Operator
    Viewer
```

Använd den här baslinjen som referenstillstånd vid felsökning och framtida underhåll.

# 174. Installationen är slutförd

Installationen är slutförd när:

```text
Server
  │
  ├── HTTPS fungerar
  ├── Autentisering fungerar
  ├── RBAC fungerar
  ├── Databasen är i gott skick
  ├── Containern är härdad
  └── Beständig lagring är verifierad
       │
       ▼
Klient
  │
  ├── Agenten rapporterar
  ├── Watcher körs
  ├── Pakethanteraren fungerar
  ├── Jobb slutförs
  ├── Resultat valideras
  └── Återställning fungerar
       │
       ▼
Drift
  │
  ├── Säkerhetskopia finns
  ├── Återställningsrutinen är känd
  ├── Felsökningsdokumentation finns
  └── Säkerhetsbaslinjen upprätthålls
```

LUMS grundläggande driftsprincip är:

```text
Observera först.
Ändra sedan.
Verifiera därefter.
Dokumentera sist.
```

För produktionsändringar kompletterar du med:

```text
Säkerhetskopiera
   ↓
Ändra
   ↓
Verifiera
   ↓
Dokumentera
```

En LUMS-installation ska alltid gå att återskapa, granska och återställa.
