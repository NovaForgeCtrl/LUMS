# LUMS-asennusopas

## Linux-päivitysten hallintapalvelin

**Projekti:** LUMS
**Slogan:** Linux-päivitysten hallinta ilman turhaa kohinaa.
**Arkisto:** `NovaForgeCtrl/LUMS`

---

## Aloittaminen: Ymmärrä asennus ennen kuin aloitat

Tämä opas kattaa täydellisen palvelinasennuksen, mukaan lukien edistyneet
ylläpito- ja varmistusmenettelyt. Se **ei** ole yksi skripti, jonka voi suorittaa
ilman tarkistusta: palvelimen nimi, TLS-varmenne, salaisuustiedosto, varmuuskopion
kohde, verkko ja tietokanta vaihtelevat asennusten välillä.

### Mitä asennetaan?

* **LUMS-palvelin:** verkkokäyttöliittymä ja API, jotka toimivat Docker-kontissa.
* **Nginx:** vastaanottaa ulkoiset HTTPS-yhteydet ja välittää ne paikallisesti
  konttiin.
* **Datataltio:** sisältää SQLite-tietokannan. Tämän taltion on kestettävä
  päivitykset, eikä sitä saa koskaan poistaa normaalin kontin vaihdon yhteydessä.
* **Salaisuustiedosto:** suojaa muun muassa sovellusistuntoja. Älä koskaan
  laita sitä Git-arkistoon, Docker-kuvaan tai chat-viestiin.
* **LUMS-agentti ja -valvoja:** asennetaan erikseen hallinnoituihin Linux-asiakkaisiin.
  Pelkkä toimiva palvelin ei päivitä asiakkaita.

| Termi | Merkitys |
| --- | --- |
| Pääte / komentotulkki | Teksti-ikkuna, johon syötät Linux-komentoja. |
| `sudo` | Suorittaa seuraavan komennon järjestelmänvalvojan oikeuksilla. Linux voi kysyä salasanasi. |
| Isäntä | Linux-tietokone, joka ajaa Dockeria ja LUMS-palvelinta. |
| Kontti | Eristetty prosessi, joka ajaa LUMS-verkkosovellusta. |
| Kuva | Valmisteltu malli, jota Docker käyttää kontin käynnistämiseen. |
| Taltio | Pysyvä Docker-tallennustila, joka säilyy, kun kontti korvataan. |
| Paikkamerkki | Teksti, kuten `LUMS-SERVER`, joka on korvattava todellisella arvollasi. |

### Suorita vain testit (tämä ei asenna palvelinta)

Nämä vaiheet sopivat Debian 13:lle lähdekoodin noutamiseen ja testien
suorittamiseen paikallisesti. Ne **eivät** luo verkon kautta tavoitettavaa
tuotantopalvelinta eivätkä asenna agenttia toiselle tietokoneelle. `sudo` tarvitaan
vain Debian-pakettien asentamiseen.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
git clone https://github.com/NovaForgeCtrl/LUMS.git ~/LUMS
cd ~/LUMS
python3 -m venv .venv-test
./.venv-test/bin/python -m pip install -r server/requirements.txt -r requirements-dev.txt
./.venv-test/bin/pytest -q

apt update päivittää pakettiluettelot; se ei päivitä kaikkia asennettuja
ohjelmistoja. .venv-test-Python-virtuaaliympäristö pitää testiriippuvuudet
erillään muusta järjestelmästä. Onnistunut testiajo päättyy koodiin
0; testien määrä voi muuttua projektin kasvaessa. Jos ympäristön luominen
epäonnistuu, tarkista, että python3-venv on asennettu. Jos testi epäonnistuu,
tallenna täydellinen virhe ja lue
vianmääritysopas; älä poista tuotantotietoja.

Todellista asennusta varten jatka numeroituihin osioihin ja lue
turvallisuus- ja varmuuskopiointiohjeet ensin. Jos LUMS on jo käynnissä, käytä
administration.md-tiedoston päivitysmenettelyä, älä
ensiasennusmenettelyä.
1. Yleiskatsaus

LUMS on keskitetty Linux-päivitysten hallinta-alusta hallittuun päivitysten jakeluun, asiakasraportointiin, paketinhallintaan, päivitystöiden suoritukseen, tulosten validointiin ja valvottavaan hallintaan.

Nykyinen arkkitehtuuri erottaa hallintapalvelimen hallinnoiduista Linux-asiakkaista.

Palvelin tarjoaa:

    Verkkopohjainen hallinta

    Asiakashallinta

    Asiakastodennus

    Pakettiluettelo

    Saatavilla olevien päivitysten raportointi

    Pakettihaku

    Paketin asennus ja poisto

    Päivitystöiden hallinta

    Työtulosten validointi

    Päivityshistoria

    Roolipohjainen käyttöoikeushallinta

    Valvontalokitus

    SQLite-pohjainen pysyvä tila

Linux-asiakkaat tarjoavat:

    Järjestelmätiedot

    Asennettujen pakettien luettelo

    Saatavilla olevien päivitysten tunnistus

    Pakettitoiminnot

    Päivitystöiden suoritus

    Lepotilan tunnistus

    Töiden tarkistuspisteet ja palautus

    Uudelleenkäynnistyksen tunnistus

    Tulosten raportointi

Nykyinen toteutus tukee:
text

Debian / Ubuntu
    └── APT / dpkg

Arch Linux
    └── pacman

2. Arkkitehtuuri

Tuotantoarkkitehtuuri on:
text

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

LUMS-sovellusta ei ole tarkoitettu altistettavaksi suoraan verkolle.

Sovelluskontti on sidottu:
text

127.0.0.1:5050 → container:5000

Nginx on ulkoinen HTTPS-sisääntulopiste.

Porttia 5000 ei julkaista suoraan.

Portin 5050 on pysyttävä vain localhostissa.
3. Sovelluksen komponentit

Täydellinen LUMS-asennus koostuu useista komponenteista.
3.1 LUMS-palvelin

Palvelin sisältää:
text

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

Sovellus toimii Docker-kontissa:
text

lums

Pysyvä tietokanta tallennetaan kontin kirjoitettavan sovellustiedostojärjestelmän ulkopuolelle:
text

lums-data:/var/lib/lums/lums.db

3.2 Nginx

Nginx tarjoaa:
text

HTTPS termination
TLS certificate handling
HTTP → HTTPS redirect
Reverse proxy
External network entry point

Aiottu pyyntöpolku on:
text

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

Flask/Gunicorn-sovellusta ei pitäisi altistaa suoraan LAN-verkkoon.
3.3 Linux-agentti

LUMS-agentti toimii jokaisella hallinnoidulla Linux-asiakkaalla.

Nykyinen agenttiversio on:
text

1.7.0

Agentti vastaa:
text

System information
Installed packages
Available updates
Client reporting
Job retrieval
Job claiming
Package operations
Result reporting
Reboot detection

Agentti kommunikoi LUMS-palvelimen kanssa HTTPS:n ja asiakaskohtaisen Bearer-tunnisteen avulla.
3.4 Suorituksen valvoja

Suorituksen valvoja vastaa hallitusta päivitystöiden suorituksesta.

Nykyinen valvojan versio on:
text

1.2.1

Valvoja käsittelee:
text

Pending-job detection
Idle-state checks
Atomic job claiming
Update execution
Checkpoint handling
Interrupted-job recovery
Result processing

Valvoja on tarkoituksella erotettu tavallisesta asiakasraportoinnista.
4. Turvallisuusmalli

Asennuksen on säilytettävä LUMSin turvallisuusperustaso.

Tuotantopalvelin käyttää:
text

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

Docker-kontti toimii ei-etuoikeutetun käyttäjänä:
text

lums

UID:llä:
text

10001

Kontti ei saa toimia etuoikeutetussa tilassa.

Juuritiedostojärjestelmän on pysyttävä vain luku -tilassa.

Sovellus ei saa vaatia kirjoitusoikeutta sovellushakemistoonsa.

Pysyvät sovellustiedot tallennetaan erillisen Docker-taltion kautta.
5. Nykyinen RBAC-malli

LUMS tarjoaa tällä hetkellä kolme verkkoroolia:
text

administrator
operator
viewer

Administrator

Ylläpitäjät voivat suorittaa ylläpitotoimenpiteitä, mukaan lukien:
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

Operator

Operaattorit voivat suorittaa operatiivista hallintaa:
text

View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance

Operaattoreilla ei ole pääsyä:
text

User management
Role management
Client creation/disabling
Client-token rotation

Viewer

Viewereillä on tarkoituksella rajoitettu pääsy.

Viewer voi käyttää:
text

Clients
Installed software

Seuraavat hallinta-alueet on piilotettu Viewer-käyttöliittymästä ja suojattu palvelinpuolella:
text

Available updates
Update Jobs
Update History
Package Management
System Maintenance

Käyttöliittymän piilottaminen ei siis ole turvaraja.

Palvelinpuolen valtuutus on edelleen pakollinen.
6. Asennusvaatimukset
6.1 LUMS-palvelin

Nykyinen käyttöönotto vaatii Linux-isännän, jossa on:
text

Docker Engine
Git
Nginx
OpenSSL
Network connectivity
Persistent storage

Palvelimella on oltava riittävästi tallennustilaa:
text

Docker images
SQLite database
Application data
Logs
Backups

LUMS-sovellus itse toimii Dockerin sisällä.
6.2 Linux-asiakkaat

Hallinnoidut Linux-asiakkaat vaativat:
text

Python 3
systemd
Supported package manager
Network connectivity to the LUMS server
Valid client token
Trusted TLS certificate

Tuetut paketinhallintaperheet:
text

Debian / Ubuntu
    APT / dpkg

Arch Linux
    pacman

Asiakkaan on voitava tavoittaa LUMSin HTTPS-päätepiste.
7. Suositeltu hakemistorakenne

Suositeltu palvelinpuolen arkiston sijainti on:
text

/opt/lums-public/

Arkisto sisältää sovelluksen lähdekoodin, agentin lähdekoodin ja testit.

Tyypillinen asennus käyttää:
text

/opt/lums-public/
    ├── agent/
    ├── server/
    ├── tests/
    ├── Dockerfile
    ├── requirements.txt
    └── requirements-dev.txt

Isäntäpuolen kokoonpano pidetään arkiston ulkopuolella:
text

/etc/lums/
    ├── secrets/
    │   └── lums_secret
    └── tls/
        ├── lums.crt
        └── lums.key

Pysyvät sovellustiedot tallennetaan:
text

lums-data:/var/lib/lums

SQLite-tietokanta on:
text

/var/lib/lums/lums.db

Tietokantaa ei saa koskaan tallentaa Git-työpuuhun.

Salaisuudet ja yksityinen TLS-materiaali on myös pidettävä arkiston ulkopuolella.
8. Arkiston valmistelu

Kloonaa arkisto aiottuun asennushakemistoon:
bash

sudo mkdir -p /opt
cd /opt

sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public

Siirry arkistoon:
bash

cd /opt/lums-public

Tarkista työpuu:
bash

git status

Tarkista nykyinen revisio:
bash

git log -1 --oneline --decorate

Hallittuja käyttöönottoja varten asennukseen käytetty tarkka commit on tallennettava.

Älä rakenna tuotantokuvia tuntemattomasta tai varmistamattomasta työpuusta.
9. Arkiston turvallisuustarkistus

Ennen tuotantokuvan rakentamista varmista, että arkistoon ei ole sijoitettu arkaluonteisia tiedostoja.

Tarkista työpuu:
bash

git status --short

Tarkista tarvittaessa ohitetut tiedostot:
bash

git status --ignored --short

Arkisto ei saa sisältää:
text

Production database files
Private TLS keys
Application secrets
Client tokens
Credential dumps
Backup databases
Runtime logs
Temporary backup files

Projekti käyttää arkiston ohitussääntöjä estääkseen yleisten varmuuskopioartefaktien tahattoman seuraamisen.

Ennen muutosten commitoimista tarkista lavastettujen tiedostojen luettelo huolellisesti.
10. Valmistele isännän kokoonpanohakemistot

Luo tarvittavat isäntäpuolen hakemistot:
bash

sudo install -d -m 700 /etc/lums
sudo install -d -m 700 /etc/lums/secrets
sudo install -d -m 700 /etc/lums/tls

Salaisuushakemisto sisältää sovelluksen salaisuuden.

TLS-hakemisto sisältää TLS-varmenteen ja yksityisen avaimen.

Näiden hakemistojen suojaaminen vähentää tahattoman paljastumisen riskiä.

Varmista:
bash

sudo stat -c '%a %U:%G %n' \
    /etc/lums \
    /etc/lums/secrets \
    /etc/lums/tls

11. Luo sovelluksen salaisuus

LUMS-sovelluksen salaisuus tallennetaan isännälle sen sijaan, että se upotettaisiin suoraan Docker-kuvaan.

Tuotantosalaisuuden polku on:
text

/etc/lums/secrets/lums_secret

Luo satunnainen salaisuus:
bash

sudo sh -c 'umask 077 && openssl rand -hex 32 > /etc/lums/secrets/lums_secret'

Suojaa syntyvä tiedosto:
bash

sudo chmod 600 \
    /etc/lums/secrets/lums_secret

Varmista oikeudet paljastamatta salaisuutta:
bash

sudo stat -c '%a %U:%G %n' \
    /etc/lums/secrets/lums_secret

Odotettu:
text

600

Salaisuus ei saa koskaan olla:
text

Committed to Git
Printed into logs
Included in the Docker image
Placed into screenshots
Published in issues
Included in documentation

Kontti vastaanottaa salaisuuden vain luku -sidontaliitoksen kautta.
12. Valmistele TLS-materiaali

LUMS käyttää HTTPS:ää ulkoiseen käyttöön.

Suositellut isäntäpuolen sijainnit ovat:
text

/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key

Asenna asianmukainen varmenne ja yksityinen avain ennen Nginx-asetusten määrittämistä.

Suojaa yksityinen avain:
bash

sudo chmod 600 \
    /etc/lums/tls/lums.key

Varmenne voi olla Nginx-palvelun luettavissa:
bash

sudo chmod 644 \
    /etc/lums/tls/lums.crt

Varmista:
bash

sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key

Yksityistä avainta ei saa koskaan committoida Gitiin tai sisällyttää Docker-kuvaan.
13. Asennusperiaate

Asennus on suoritettava hallituissa vaiheissa:
text

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

Älä yhdistä tuotantoasiakkaita ennen kuin palvelin on läpäissyt omat varmistustarkistuksensa.

Seuraavat osiot jatkavat Docker-kuvan rakentamisella ja kovennetulla tuotantokäyttöönotolla.
14. Rakenna LUMS Docker -kuva

Ennen tuotantokuvan rakentamista varmista, että arkisto on aiotussa tilassa.

Siirry arkistoon:
bash

cd /opt/lums-public

Suorita testisarja ennen tuotantokuvan luomista:
bash

./.venv-test/bin/pytest -q

Testien määrän odotetaan kasvavan projektin kehittyessä.

Tärkeä vaatimus on, että asiaankuuluva testisarja suoritetaan onnistuneesti ennen käyttöönottoa.

Rakenna Docker-kuva:
bash

sudo docker build \
    -t lums:latest \
    .

Varmista, että kuva on olemassa:
bash

sudo docker image ls lums

Tarkista kuva:
bash

sudo docker image inspect lums:latest

Tuotantokuva perustuu kiinnitettyyn Python 3.13 slim -peruskuvaan.

Dockerfile käyttää myös kiinnitettyjä tuotantoriippuvuuksia tarvittaessa.
15. Tarkista Docker-koonti

Ennen kuvan käyttöönottoa tarkista koontituloste odottamattomien virheiden tai varoitusten varalta.

Tarkista syntyvä kuva:
bash

sudo docker inspect \
    lums:latest

Varmista määritetty sovelluskäyttäjä:
bash

sudo docker image inspect \
    lums:latest \
    --format '{{.Config.User}}'

Sovellus on tarkoitettu suoritettavaksi käyttäjänä:
text

lums

Sovellus ei saa vaatia root-oikeuksia normaalin suorituksen aikana.

Tarkista Dockerfile, kun muutat koontiprosessia:
bash

sed -n '1,240p' Dockerfile

Älä lisää salaisuuksia, varmenteita tai tuotantotietokantoja Docker-koontikontekstiin.

Arkisto sisältää .dockerignore-tiedoston, joka vähentää ajonaikaisten artefaktien tahattoman sisällyttämisen riskiä kuvaan.
16. Luo pysyvä Docker-taltio

Luo pysyvä LUMS-datataltio:
bash

sudo docker volume create lums-data

Varmista:
bash

sudo docker volume inspect lums-data

Taltio tallentaa pysyvät sovellustiedot:
text

lums-data
    ↓
/var/lib/lums
    ↓
/var/lib/lums/lums.db

Kontin tiedostojärjestelmää ei saa käsitellä pysyvänä sovellustallennustilana.

Siksi tietokanta säilyy kontin vaihdon yli niin kauan kuin lums-data-taltio säilytetään.

    [!IMPORTANT]
    Älä koskaan poista lums-data-taltiota normaalin sovelluspäivityksen aikana.

Taltion poistaminen poistaa siihen tallennetun SQLite-tietokannan.
17. Varmista pysyvä taltio

Ennen LUMSin käynnistämistä varmista, että taltio on olemassa:
bash

sudo docker volume inspect \
    lums-data

Taltio voidaan tarkistaa myös Dockerin kautta:
bash

sudo docker volume ls | grep lums-data

Äskettäin luotu taltio ei yleensä sisällä vielä tietokantaa.

LUMS-sovellus alustaa tietokannan käyttöönoton aikana.
18. Tuotantokontin kokoonpano

Tuotantokontti käyttää useita turvakontrolleja samanaikaisesti.

Odotettu ajonaikainen perustaso on:
text

Non-root user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges
No privileged mode
Localhost-only application binding
Read-only application-secret mount
Persistent writable data volume
Dedicated /tmp tmpfs

Sovellusportti julkaistaan vain localhostiin:
text

127.0.0.1:5050 → container:5000

Ulkoinen HTTPS-päätepiste tarjotaan Nginxillä.
19. Käynnistä kovennettu LUMS-kontti

Ennen uuden tuotantokontin käynnistämistä varmista, että toinen lums-niminen kontti ei ole jo käynnissä:
bash

sudo docker ps \
    --filter name=lums

Jos olemassa oleva käyttöönotto korvataan, säilytä olemassa oleva kontti, kunnes uusi kuva on validoitu.

Käynnistä kovennettu kontti:
bash

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

Sovelluksen salaisuus liitetään vain luku -tilassa.

SQLite-tietokanta tallennetaan pysyvään taltioon.

Juuritiedostojärjestelmä on vain luku -tilassa.

Kaikki Linux-kyvykkyydet poistetaan.

no-new-privileges-turvavalinta estää kontin sisäisiä prosesseja saamasta lisäoikeuksia.
20. Varmista kontin tila

Tarkista käynnissä oleva kontti:
bash

sudo docker ps \
    --filter name=lums

Odotettu tila:
text

Up ...

Tarkista kontin tila suoraan:
bash

sudo docker inspect \
    --format '{{.State.Status}}' \
    lums

Odotettu:
text

running

Tarkista viimeisimmät lokit:
bash

sudo docker logs \
    --tail 100 \
    lums

Sovelluksen käynnistysvirheet on ratkaistava ennen asennuksen jatkamista.
21. Varmista kontin turvallisuus

Tarkista tehokas ajonaikainen turvakokoonpano:
bash

sudo docker inspect lums \
    --format='User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}'

Odotettu perustaso on:
text

User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]

Docker-tulosteen tarkka muotoilu voi vaihdella.

Tehokas kokoonpano on ratkaiseva.
22. Varmista sovellusportti

Tarkista julkaistu Docker-portti:
bash

sudo docker port lums

Odotettu:
text

5000/tcp -> 127.0.0.1:5050

Seuraava ei ole hyväksyttävää tuotantosovellukselle:
text

0.0.0.0:5050

tai:
text

0.0.0.0:5000

Sovellus on tarkoituksella käytettävissä vain paikallisen käänteisvälityspalvelinpolun kautta.

Tarkista kuuntelevat pistokkeet:
bash

sudo ss -lntp | grep -E ':5050|:5000'

Vain localhost-sovellussidonta saa olla läsnä.
23. Varmista salaisuuden liitos

Vahvista, että salaisuus on liitetty:
bash

sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Source "->" .Destination "RW=" .RW}}{{end}}'

Sovelluksen salaisuuden pitäisi näkyä samankaltaisena kuin:
text

/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false

Tarkka tuloste voi sisältää lisää liitostietoja.

Tärkeä ominaisuus on:
text

RW=false

Älä koskaan tulosta salaisuuden sisältöä.

Suora luettavuustesti riittää:
bash

sudo docker exec lums \
    sh -c 'test -r /run/secrets/lums_secret && echo "secret mount: OK"'

Odotettu:
text

secret mount: OK

24. Varmista pysyvän taltion liitos

Tarkista kontin liitokset:
bash

sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Type .Source "->" .Destination "RW=" .RW}}{{end}}'

LUMS-datataltio on liitettävä kohtaan:
text

/var/lib/lums

ja sen on oltava kirjoitettava:
text

RW=true

Odotettu suhde on:
text

lums-data
    ↓
/var/lib/lums

Juuritiedostojärjestelmä pysyy vain luku -tilassa, kun taas erillinen datataltio tarjoaa tarvittavan pysyvän kirjoitusoikeuden.
25. Varmista vain luku -juuritiedostojärjestelmä

Sovelluksen juuritiedostojärjestelmän on oltava vain luku -tilassa.

Kontin ajonaikaisen ympäristön pitäisi raportoida:
text

ReadonlyRootfs=true

Kontin sisällä voidaan suorittaa hallittu kirjoitustesti.

Esimerkiksi:
bash

sudo docker exec lums \
    sh -c 'touch /app/.write-test'

Komennon pitäisi epäonnistua, koska /app on osa vain luku -kontin tiedostojärjestelmää.

Älä poista vain luku -juuritiedostojärjestelmää käytöstä vain siksi, että jokin sovelluskomponentti yrittää kirjoittaa määritettyjen kirjoitettavien sijaintien ulkopuolelle.

Jos sovellus vaatii pysyviä tietoja, käytä asianmukaista taltiota tai ajonaikaista tiedostojärjestelmää sen sijaan.
26. Varmista kirjoitettava väliaikainen tiedostojärjestelmä

Kontti tarjoaa erillisen /tmp-tmpfs-tiedostojärjestelmän.

Varmista:
bash

sudo docker exec lums \
    sh -c 'touch /tmp/lums-write-test && rm -f /tmp/lums-write-test && echo "tmpfs: OK"'

Odotettu:
text

tmpfs: OK

Väliaikainen tiedostojärjestelmä on määritetty:
text

noexec
nosuid

ja kokorajoituksella.

Tämä tarjoaa väliaikaisen kirjoitettavan tallennustilan tekemättä kontin juuritiedostojärjestelmästä kirjoitettavaa.
27. Varmista sovelluksen datahakemisto

LUMS-sovellus vaatii kirjoitusoikeuden pysyvään datahakemistoonsa.

Testaa:
bash

sudo docker exec lums \
    sh -c 'touch /var/lib/lums/.write-test && rm -f /var/lib/lums/.write-test && echo "data volume: OK"'

Odotettu:
text

data volume: OK

Tämä vahvistaa, että erillinen kirjoitettava taltio on käytettävissä, kun taas muu osa kontista pysyy vain luku -tilassa.
28. Varmista sovelluskäyttäjä

Vahvista tehokas ajonaikainen käyttäjä:
bash

sudo docker exec lums \
    id

Prosessin pitäisi toimia ei-etuoikeutetun LUMS-käyttäjänä.

Odotettu identiteetti sisältää:
text

uid=10001(lums)

Tarkat ryhmätiedot voivat vaihdella kuvakokoonpanon mukaan.

Kontti ei saa toimia käyttäjänä:
text

root

normaalin toiminnan aikana.
29. Tietokannan alustus

Kun kontti on käynnistynyt, tarkista, onko tietokanta olemassa:
bash

sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db

Jos sovellus on alustanut onnistuneesti, tietokannan pitäisi olla läsnä.

Tietokanta sijaitsee:
text

/var/lib/lums/lums.db

kontin sisällä ja säilyy fyysisesti:
text

lums-data

kautta.

Tietokantaa ei saa kopioida kohtaan:
text

/opt/lums-public

tai committoida Gitiin.
30. Varmista SQLite-ajonaikainen kokoonpano

Nykyinen LUMS-tuotannon perustaso käyttää:
text

journal_mode = wal
busy_timeout = 5000 ms
synchronous = 2
foreign_keys = ON

Sovellus ottaa eksplisiittisesti käyttöön viiteavainten valvonnan tietokantayhteyksille.

Tietokanta käyttää WAL-tilaa normaaliin tuotantokäyttöön.

Ajonaikainen kokoonpano voidaan tarkistaa sovelluksen tietokannasta.

Esimerkiksi:
bash

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

Odotetut arvot vastaavat:
text

journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0

Sovellus ottaa viiteavaimet käyttöön eksplisiittisesti.
31. Varmista tietokannan eheys

Suorita SQLite-eheystarkistus:
bash

sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
result = db.execute("PRAGMA integrity_check").fetchone()[0]
print(result)
db.close()
PY

Odotettu:
text

ok

Älä jatka käyttöönottoa, jos eheystarkistus raportoi tietokannan korruptiosta.
32. Varmista tietokantamigraatiot

LUMS käyttää sovellusmigraatioita tietokantaskeeman muutoksiin.

Tarkista migraatioon liittyvät tiedostot:
bash

ls -lh \
    server/*migration*.py

Sovellus suorittaa tarvittavat migraatiot käynnistyksen/käyttöönoton aikana nykyisen toteutuksen mukaisesti.

Käynnistyksen jälkeen tarkista sovelluslokit:
bash

sudo docker logs \
    --tail 200 \
    lums

Migraatiovirheet on tutkittava ennen käyttäjien luomista tai asiakkaiden yhdistämistä.

Älä muokkaa tuotannon SQLite-skeemaa manuaalisesti, ellei projektdokumentaatio nimenomaisesti vaadi sitä.
33. Paikallinen sovellusvalidointi

Ennen Nginx-asetusten määrittämistä vahvista, että sovellus vastaa paikallisesti.

Docker-sovellus on sidottu:
text

127.0.0.1:5050

Paikallinen pyyntö voidaan testata seuraavasti:
bash

curl -I \
    http://127.0.0.1:5050/

Tarkka HTTP-vastaus riippuu nykyisestä sovellusreitistä ja todennustilasta.

Tärkeä vaatimus on, että pyyntö saavuttaa käynnissä olevan LUMS-sovelluksen.

Jos yhteys epäonnistuu, tarkista:
bash

sudo docker ps \
    --filter name=lums

ja:
bash

sudo docker logs \
    --tail 200 \
    lums

Älä altista porttia 5050 ulkoisesti vianmäärityksen kiertotienä.
34. Palvelimen alustava tarkistuspiste

Tässä vaiheessa palvelimen on täytettävä:
text

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

Älä yhdistä tuotantoasiakkaita vielä.

Seuraava vaihe määrittää Nginxin, HTTPS:n ja ulkoisen LUMS-päätepisteen.
35. Määritä Nginx

Nginx tarjoaa LUMSin ulkoisen HTTPS-sisääntulopisteen.

Sovellus itse pysyy sidottuna:
text

127.0.0.1:5050

Aiottu pyyntöpolku on:
text

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

Luo Nginx-sivustokokoonpano:
bash

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

Korvaa:
text

LUMS-SERVER

asennuksessa käytetyllä isäntänimellä tai osoitteella.

Älä käytä kirjaimellista paikkamerkkiä tuotantokokoonpanossa.
36. Ota LUMS Nginx -kokoonpano käyttöön

Luo käytössä olevan sivuston linkki:
bash

sudo ln -s \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums

Jos oletusarvoista Nginx-sivustoa ei tarvita, poista se:
bash

sudo rm -f \
    /etc/nginx/sites-enabled/default

Älä poista muita Nginx-kokoonpanoja, jotka kuuluvat liittymättömiin sovelluksiin.
37. Vahvista Nginx-kokoonpano

Testaa kokoonpano aina ennen Nginxin uudelleenlatausta:
bash

sudo nginx -t

Odotettu:
text

syntax is ok
test is successful

Vasta onnistuneen kokoonpanotestin jälkeen Nginx saa latautua uudelleen:
bash

sudo systemctl reload nginx

Varmista palvelu:
bash

sudo systemctl status \
    nginx \
    --no-pager

Nginxin on oltava käynnissä ennen HTTPS-validoinnin jatkamista.
38. Varmista TLS-varmenteet

Vahvista, että määritetyt varmennetiedostot ovat olemassa:
bash

sudo ls -lh \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key

Varmista oikeudet:
bash

sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key

Yksityisen avaimen pitäisi normaalisti olla:
text

600

Varmenne voi normaalisti olla:
text

644

Älä koskaan tulosta yksityisen avaimen sisältöä.
39. Varmista HTTPS-päätepiste

Testaa HTTPS paikallisesti:
bash

curl -I \
    https://LUMS-SERVER/

Korvaa LUMS-SERVER isäntänimellä, jonka palvelimen TLS-varmenne kattaa. Älä käytä -k-valintaa rutiininomaiseen varmistukseen; se ohittaa varmenteen validoinnin.

Kun varmenne on järjestelmän luottama, käytä varmenteen validointia:
bash

curl -I \
    https://LUMS-SERVER/

Onnistunut vastaus vahvistaa, että pyyntö saavuttaa Nginx HTTPS -päätepisteen.

Tarkka HTTP-tila riippuu pyydetystä reitistä ja todennustilasta.

Tärkeä vaatimus on, että TLS-yhteys onnistuu ja pyyntö saavuttaa LUMSin.
40. Varmista HTTP → HTTPS -uudelleenohjaus

HTTP-kuuntelijan on ohjattava asiakkaat HTTPS:ään.

Testaa:
bash

curl -I \
    http://LUMS-SERVER/

Odotettu toiminta:
text

HTTP/1.1 301 ...
Location: https://...

LUMS-sovellusta ei pitäisi käyttää salaamattoman HTTP-yhteyden kautta.

Älä pysyvästi määritä asiakkaita varmenteen validoinnin ollessa poistettu käytöstä vain siksi, että alkuperäinen varmenne ei ole luotettu.

Korjaa sen sijaan luottamuskokoonpano.
41. Varmista ulkoinen verkkopolku

Tarkista kuuntelevat pistokkeet:
bash

sudo ss -lntp | grep -E ':80|:443|:5050|:5000'

Aiottu arkkitehtuuri on:
text

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

Porttia 5050 ei saa altistaa LAN-verkkoon.

Porttia 5000 ei saa altistaa suoraan.

Docker-sovellusportti on sisäinen käänteisvälityspalvelimen päätepiste.
42. Varmista turvaotsakkeet

Tarkista HTTPS-vastauksen otsakkeet:
bash

curl -I \
    https://LUMS-SERVER/

Tarkista palautetut otsakkeet sen sijaan, että olettaisit turvakokoonpanon olevan aktiivinen.

Asiaankuuluvat turvaotsakkeet voivat sisältää:
text

X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Content-Security-Policy

Tarkat otsakkeet riippuvat nykyisestä LUMS-sovelluksesta ja Nginx-kokoonpanosta.

Jos vaadittu otsake puuttuu, tarkista tehokas Nginx-kokoonpano:
bash

sudo nginx -T

ja sovelluskokoonpano:
bash

sudo docker logs \
    --tail 100 \
    lums

Älä lisää turvaotsakkeita sokeasti tarkistamatta, mikä kerros on jo vastuussa niistä.
43. Varmista isäntäkäsittely

Tuotantokäyttöönoton ei pitäisi altistaa sovellusta tahattoman oletusarvoisen Nginx-sivuston kautta.

Tarkista aktiivinen kokoonpano:
bash

sudo nginx -T

Tarkista käytössä olevat sivustot:
bash

ls -la \
    /etc/nginx/sites-enabled/

Aiotun LUMS-virtuaali-isännän pitäisi olla läsnä.

Oletussivusto ei saa odottamatta tarjoilla LUMS-sovellusta.

Kun käytät IP-osoitetta LUMS-päätepisteenä, varmista, että määritetty server_name ja varmenne vastaavat todellista käyttöönoton mallia.
44. Varmista Docker-altistus uudelleen

Kun Nginx on määritetty, vahvista, että sovellus pysyy vain localhostissa:
bash

sudo docker port lums

Odotettu:
text

5000/tcp -> 127.0.0.1:5050

Käänteisvälityspalvelin ei vaadi Docker-sidonnan muuttamista.

Älä muuta sitä muotoon:
text

0.0.0.0:5050

vain siksi, että Nginx kuuntelee verkkoa.

Nginxillä ja Dockerilla on tarkoituksella erilliset altistusrajat.
45. Luo alkuperäinen ylläpitäjä

Alkuperäinen ylläpitäjä on luotava nykyisen arkiston ylläpitäjän alustusmekanismilla.

Ennen alustuskomennon suorittamista tarkista käytettävissä oleva arkistototeutus:
bash

cd /opt/lums-public

Tarkista turvallisuuteen liittyvät alustustiedostot:
bash

find server \
    -maxdepth 1 \
    -type f \
    -iname '*security*' \
    -o -iname '*migration*'

Tarkista sitten nykyinen migraatio-/alustustoteutus ennen sen suorittamista.

Esimerkiksi:
bash

sed -n '1,260p' \
    server/security_migration.py

Käytä käyttöönotettavan tarkan arkistorevision tarjoamaa alustusmenettelyä.

    [!IMPORTANT]
    Älä kopioi ylläpitäjän salasanaa komentotulkin historiaan tai dokumentaatioon.

Alkuperäisen ylläpitäjän on saatava:
text

role = administrator

Ylläpitäjätili tarvitaan ensimmäiseen verkkokirjautumiseen ja myöhempään asiakashallintaan.
46. Varmista ylläpitäjätili

Ylläpitäjän alustuksen jälkeen varmista tili paljastamatta todennusmateriaalia.

Tietokantatarkastus voidaan suorittaa kontista:
bash

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

Odotetut ylläpitäjän ominaisuudet sisältävät:
text

enabled = 1
role = administrator

Älä tulosta:
text

password hashes
session data
client tokens
application secrets

47. Ylläpitäjän salasana

Käytä yksilöllistä ylläpitäjän salasanaa.

Salasanaa ei pidä käyttää uudelleen:
text

other servers
Linux accounts
GitHub accounts
email accounts
network devices
other LUMS installations

LUMS-sovellus tallentaa salasanat määritetyllä salasanatiivistysmekanismilla.

Älä yritä korvata sovelluksen salasanatiivistettä manuaalisesti SQLitessä.

Jos ylläpitäjän salasana on vaihdettava, käytä tuettua sovellusmekanismia.
48. Ensimmäinen verkkokirjautuminen

Avaa LUMSin HTTPS-päätepiste:
text

https://LUMS-SERVER/

Kirjaudu sisään ylläpitäjätilillä.

Todennuksen jälkeen ylläpitäjällä pitäisi olla pääsy hallintakäyttöliittymään.

Ylläpitäjän käyttöliittymän pitäisi tarjota pääsy alueille, jotka nykyinen RBAC-toteutus sallii.

Vähintään ylläpitäjän pitäisi päästä käsiksi:
text

Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management

49. Varmista ylläpitäjän RBAC

Kirjautumisen jälkeen varmista, että hallintotoiminnot ovat käytettävissä.

Ylläpitäjän pitäisi päästä käsiksi käyttäjähallintaan.

Ylläpitäjän pitäisi myös pystyä suorittamaan nykyisen toteutuksen sallimat asiakashallintatoiminnot.

Palvelinpuolen valtuutus on edelleen turvaraja.

Selainkäyttöliittymää ei luoteta vain siksi, että elementti on näkyvissä tai piilotettu.
50. Luo operaattori

Kun ylläpitäjätili on varmistettu, luo operaattoritili LUMSin käyttäjähallintakäyttöliittymän kautta.

Operaattorin rooli on tarkoitettu operatiiviseen päivityshallintaan.

Operaattori voi käyttää:
text

Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance

Operaattori ei saa pystyä suorittamaan vain ylläpitäjälle tarkoitettuja toimintoja, kuten:
text

User management
Role management
Client creation/disabling
Client-token rotation

Varmista oikeudet sovelluskäyttöliittymän ja tarvittaessa API-valtuutuskäyttäytymisen avulla.
51. Luo Viewer

Viewer-tili voidaan luoda, kun vain luku -pääsyä tarvitaan.

Viewer-rooli on tarkoituksella rajoitettu.

Viewer voi käyttää:
text

Clients
Installed software

Seuraavat alueet eivät saa olla Viewerin käytettävissä:
text

Available updates
Update jobs
Update history
Package management
System maintenance

Nämä rajoitukset valvotaan palvelinpuolella.

Käyttöliittymä voi lisäksi piilottaa käyttämättömissä olevat toiminnot.
52. Varmista Viewer-eristys

Kirjaudu sisään Viewer-tilillä ja varmista näkyvä käyttöliittymä.

Viewerin ei pitäisi saada hallintakontrolleja.

Viewer ei saa ohittaa käyttöliittymää ja kutsua suojattuja päätepisteitä suoraan.

Suojatuista toiminnoista pitäisi palauttaa valtuutusvirhe.

Odotettu periaate on:
text

UI restriction
     +
server-side authorization
     =
RBAC boundary

Älä koskaan luota JavaScriptiin tai piilotettuihin HTML-elementteihin ainoana valtuutusmekanismina.
53. Varmista istunto- ja CSRF-suoja

Ensimmäisen onnistuneen kirjautumisen jälkeen varmista, että sovellus käyttää määritettyjä istunto- ja CSRF-suojauksiaan.

Asennuksen ei pitäisi poistaa CSRF-suojausta käytöstä saadakseen API-pyynnöt tai selaintoiminnot toimimaan.

Jos laillinen pyyntö epäonnistuu CSRF-virheellä, tarkista sovellusvirta sen sijaan, että poistaisit suojauksen käytöstä.

Istuntoihin liittyvä käyttäytyminen on dokumentoitu:
text

docs/security.md

54. Varmista kirjautumisen nopeusrajoitus

Nykyinen kirjautumissuoja käyttää pysyvää epäonnistumisseurantaa.

Määritetty eteneminen on:
text

5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds

Onnistunut todennus tyhjentää sovellettavan epäonnistumistilan.

Älä toistuvasti laukaise epäonnistunutta todennusta tuotantoasennusta vastaan vain testataksesi mekanismia.

Käytä olemassa olevaa testisarjaa toistuvaan automatisoituun validointiin.
55. Palvelimen varmistuksen tarkistuspiste

Tässä vaiheessa varmista:
text

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

Vasta kun palvelin läpäisee nämä tarkistukset, Linux-asiakkaat voidaan asentaa.

Seuraava osio kattaa Linux-agentin, asiakaskokoonpanon, TLS-luottamuksen ja systemd-integraation.
56. Linux-asiakkaan asennus

LUMS-asiakkaat ovat Linux-järjestelmiä, joita LUMS-palvelin hallinnoi.

Asiakasasennus koostuu:
text

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

Päivitysten suoritus hoidetaan erikseen suorituksen valvojan toimesta.

Nykyinen agenttiversio on:
text

1.7.0

Nykyinen valvojan versio on:
text

1.2.1

57. Tuetut Linux-asiakkaat

Nykyiset paketinhallintatoteutukset tukevat:
text

Debian / Ubuntu
    ↓
APT / dpkg

Arch Linux
    ↓
pacman

Varmista käyttöjärjestelmä ennen asiakkaan asentamista:
bash

cat /etc/os-release

Varmista arkkitehtuuri:
bash

uname -m

Varmista systemd:
bash

systemctl --version

Asiakas vaatii toimivan systemd-asennuksen.
58. Asiakkaan verkkovatimukset

Asiakkaan on voitava tavoittaa LUMSin HTTPS-päätepiste.

Testaa perusverkkoyhteys:
bash

ping LUMS-SERVER

Onnistunut ping ei ole välttämätön, kun ICMP on estetty.

Tärkeä vaatimus on HTTPS-yhteys.

Testaa LUMS-päätepiste:
bash

curl -I \
    https://LUMS-SERVER/

Jos palvelin käyttää yksityistä CA:ta, asiakkaan on luotettava siihen ennen jatkamista.

Älä poista TLS-validointia käytöstä pysyvänä kiertotienä.
59. Hanki LUMS-agentti

Agenttilähdekoodi sisältyy LUMS-arkistoon.

Hanki asiakkaalla arkisto tai siirrä tarvittavat agenttitiedostot muulla hyväksytyllä käyttöönottomenetelmällä.

Asiaankuuluvat tiedostot ovat:
text

agent/agent.py
agent/watcher.py
agent/package_manager.py

Suositeltu asennushakemisto on:
text

/opt/lums-agent

Luo se:
bash

sudo install -d -m 755 \
    /opt/lums-agent

60. Asenna agenttitiedostot

LUMS-arkistosta:
bash

cd /opt/lums-public

Asenna agentti:
bash

sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py

Asenna valvoja:
bash

sudo cp \
    agent/watcher.py \
    /opt/lums-agent/watcher.py

Asenna paketinhallinnan abstraktio:
bash

sudo cp \
    agent/package_manager.py \
    /opt/lums-agent/package_manager.py

Varmista:
bash

ls -lh \
    /opt/lums-agent/

Hakemiston pitäisi sisältää asennetut agenttikomponentit.
61. Varmista agenttiversiot

Varmista asennettu agenttiversio:
bash

grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/agent.py

Nykyinen versio on:
text

1.7.0

Varmista valvoja:
bash

grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py

Nykyinen versio on:
text

1.2.1

Jos asennetut versiot eivät vastaa aiottua käyttöönoton revisiota, pysähdy ja varmista, että oikeaa arkistorevisiota käytetään.
62. Asenna systemd-palvelutiedostot

Agentti ja valvoja käyttävät erillisiä systemd-palveluita.

Asenna agenttipalvelu:
bash

sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service

Asenna valvojan palvelu:
bash

sudo cp \
    agent/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent-watcher.service

Asenna raportointiajastin:
bash

sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer

Asenna valvojan ajastin:
bash

sudo cp \
    agent/lums-agent-watcher.timer \
    /etc/systemd/system/lums-agent-watcher.timer

Lataa systemd uudelleen:
bash

sudo systemctl daemon-reload

63. Varmista systemd-yksiköt

Tarkista agenttipalvelu:
bash

systemctl cat \
    lums-agent.service

Tarkista valvojan palvelu:
bash

systemctl cat \
    lums-agent-watcher.service

Tarkista agenttiajastin:
bash

systemctl cat \
    lums-agent.timer

Tarkista valvojan ajastin:
bash

systemctl cat \
    lums-agent-watcher.timer

Yksiköiden pitäisi viitata asennettuihin tiedostoihin hakemistossa:
text

/opt/lums-agent/

Älä ota ajastimia käyttöön ennen kuin asiakaskokoonpano ja todennus on suoritettu.
64. Luo asiakaskokoonpano

Asiakaskokoonpano tallennetaan Git-arkiston ulkopuolelle.

Käytä:
text

/etc/default/lums-agent

Luo tiedosto:
bash

sudo install -m 600 /dev/null \
    /etc/default/lums-agent

Kokoonpano sisältää LUMS-palvelimen päätepisteen ja asiakastunnisteen.

Esimerkkirakenne:
text

LUMS_BASE=https://LUMS-SERVER
LUMS_TOKEN=<CLIENT-TOKEN>

Korvaa:
text

LUMS-SERVER

todellisella LUMS-palvelimen päätepisteellä.

Korvaa:
text

<CLIENT-TOKEN>

tälle asiakkaalle määritetyllä tunnisteella.

Suojaa kokoonpano:
bash

sudo chmod 600 \
    /etc/default/lums-agent

Varmista näyttämättä sen sisältöä:
bash

sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent

Odotettu:
text

600

65. Asiakastunnisteet

Jokaisella LUMS-asiakkaalla on oma todennustunnisteensa.

Tunnistetta käytetään seuraavasti:
text

Authorization: Bearer <CLIENT-TOKEN>

Palvelin ei tarvitse alkuperäistä tunnistearvoa valmistelun jälkeen.

Palvelin tallentaa tunnisteen kryptografisen esityksen validointia varten.

Tämä tarkoittaa, että asiakastunnistetietoja on kohdeltava kuin salasanoja.

Älä koskaan laita todellista tunnistetta:
text

Git
documentation
screenshots
issue reports
shell history
public configuration

66. Valmistele asiakastunniste

Luo tai valmistele asiakas LUMSin ylläpitokäyttöliittymästä nykyisen asiakashallintatyönkulun mukaisesti.

Tuloksena oleva asiakastunniste on siirrettävä aiottuun asiakkaaseen turvallisen kanavan kautta.

Tallenna se vain:
text

/etc/default/lums-agent

asiakkaalla.

Älä käytä yhtä asiakastunnistetta uudelleen useilla koneilla.

Aiottu suhde on:
text

Client A
    ↓
Token A

Client B
    ↓
Token B

Client C
    ↓
Token C

Vaarantunut tunniste tunnistaa siksi vain siihen liittyvän asiakkaan.
67. Asiakastunnisteen vaihto

Ylläpitäjät voivat vaihtaa asiakastunnisteita.

Vaihtovirta on:
text

Current token
     ↓
Administrator rotates token
     ↓
Old token invalidated
     ↓
New token issued
     ↓
Client configuration updated

Kun asiakaskokoonpano on päivitetty, suorita agentti manuaalisesti varmistaaksesi, että todennus onnistuu.

Vaihdettua tunnistetta ei saa jatkaa hyväksymistä loputtomiin.
68. TLS-luottamus

LUMS-agentti kommunikoi palvelimen kanssa HTTPS:n kautta.

Varmenteen validoinnin on pysyttävä käytössä.

Julkisesti luotetulle varmenteelle käyttöjärjestelmän normaali luottamusvarasto riittää.

Yksityiselle laboratorio-CA:lle asenna CA-varmenne asiakkaaseen.

Älä ratkaise varmenneongelmia poistamalla validointia käytöstä.

Oikea ratkaisu on saada asiakas luottamaan aiottuun varmentajaan.
69. Debian / Ubuntu TLS-luottamus

Debian-perheen järjestelmissä yksityinen CA voidaan asentaa järjestelmän luottamusvarastoon.

Kopioi CA-varmenne:
bash

sudo cp \
    lums-ca.crt \
    /usr/local/share/ca-certificates/lums-ca.crt

Päivitä luottamusvarasto:
bash

sudo update-ca-certificates

Varmista, että varmenne hyväksytään:
bash

curl -I \
    https://LUMS-SERVER/

Jos komento onnistuu ilman -k-valintaa, järjestelmän luottamuskokoonpano toimii.
70. Arch Linux TLS-luottamus

Arch Linuxissa asenna yksityinen CA järjestelmän määritetyllä luottamusvarastomekanismilla.

Kun CA on asennettu, päivitä luottamustietokanta aktiivisen luottamusvarastokokoonpanon mukaisesti.

Varmista:
bash

curl -I \
    https://LUMS-SERVER/

Yhteyden pitäisi onnistua ilman:
text

-k

Älä pysyvästi määritä agenttia ohittamaan varmenteen validointia.
71. Varmista paketinhallinta

Agentti tunnistaa tuetun paketinhallintaperheen.

Debian/Ubuntu:
bash

command -v apt

ja:
bash

command -v dpkg-query

Varmista asennetut paketit:
bash

dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    | head

Varmista saatavilla olevat päivitykset:
bash

apt list --upgradable

Arch Linux:
bash

command -v pacman

Varmista asennetut paketit:
bash

pacman -Q | head

Varmista saatavilla olevat päivitykset:
bash

pacman -Qu

Paketinhallinnan abstraktio käyttää automaattisesti asianmukaista toteutusta.
72. Varmista agentin oikeudet

Tarkista asennushakemisto:
bash

ls -ld \
    /opt/lums-agent

Tarkista asennetut tiedostot:
bash

ls -lh \
    /opt/lums-agent/

Agentti ei tarvitse kirjoitusoikeutta omaan lähdehakemistoonsa.

Asiakaskokoonpano pysyy suojattuna erikseen:
bash

sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent

Odotettu:
text

600

Agentti vaatii riittävät järjestelmäoikeudet pakettitilan tarkastamiseen ja pakettitoimintojen suorittamiseen.

Tarkat ajonaikaiset oikeudet määritetään asennetussa systemd-palvelussa.
73. Varmista agentin kokoonpano

Ennen palvelun käynnistämistä varmista, että kokoonpanotiedosto on olemassa:
bash

sudo test -r \
    /etc/default/lums-agent \
    && echo "agent configuration: OK"

Älä tulosta kokoonpanotiedoston sisältöä.

Varmista, että tarvittavat muuttujat ovat olemassa paljastamatta tunnistetta:
bash

sudo sh -c '
set -a
. /etc/default/lums-agent
set +a

test -n "$LUMS_BASE" &&
echo "LUMS_BASE: configured"

test -n "$LUMS_TOKEN" &&
echo "LUMS_TOKEN: configured"
'

Itse tunnistearvoa ei saa tulostaa.
74. Testaa agentti manuaalisesti

Ennen ajastimen käyttöönottamista suorita agentti kerran manuaalisesti:
bash

sudo systemctl start \
    lums-agent.service

Tarkista tulos:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

Agentti on kertaluontoinen palvelu.

Onnistuneen suorituksen jälkeen se voi näyttää:
text

Active: inactive (dead)

Tämä on normaalia.

Tärkeä tulos on:
text

status=0/SUCCESS

Tarkista loki:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

75. Varmista ensimmäinen asiakasraportti

Onnistuneen agenttiajon pitäisi raportoida asiakas LUMS-palvelimelle.

Täydellinen polku on:
text

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

Tarkista palvelimen lokit tarvittaessa:
bash

sudo docker logs \
    --tail 100 \
    lums

Asiakkaan pitäisi näkyä LUMS-verkkokäyttöliittymässä onnistuneen raportin jälkeen.

Paikallisen palvelun onnistuminen ei yksinään riitä.

Palvelimen on hyväksyttävä raportti.
76. Varmista asiakas verkkokäyttöliittymässä

Kirjaudu sisään ylläpitäjänä tai operaattorina.

Avaa asiakasyleiskatsaus.

Uuden asiakkaan pitäisi raportoida tietoja, kuten:
text

Hostname
IP address
Operating system
Architecture
Agent version
Last report
Installed packages
Available updates

Raportoidut tiedot kuuluvat kyseiselle asiakkaalle.

Asiakas ei saa päästä toisen asiakkaan resursseihin.
77. Ota raportointiajastin käyttöön

Vasta kun manuaalinen agenttiajo on onnistunut, raportointiajastin voidaan ottaa käyttöön:
bash

sudo systemctl enable --now \
    lums-agent.timer

Tarkista:
bash

sudo systemctl status \
    lums-agent.timer \
    --no-pager

Tarkista aikataulu:
bash

systemctl list-timers \
    lums-agent.timer \
    --no-pager

Ajastin käynnistää säännöllisesti:
text

lums-agent.service

Palvelu itsessään on edelleen kertaluontoinen yksikkö.

Siksi on normaalia, että palvelu palaa tilaan:
text

inactive (dead)

ajastimen suoritusten välillä.
78. Varmista ajastettu raportointi

Kun ajastin on otettu käyttöön, tarkista seuraava ajastettu suoritus:
bash

systemctl list-timers \
    --all \
    --no-pager | grep lums-agent

Kun ajastin on suoritettu, tarkista:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Varmista vastaava asiakasraportti LUMSissa.

Terve raportointisykli on:
text

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

79. Asiakasasennuksen tarkistuspiste

Ennen suorituksen valvojan asentamista varmista:
text

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

Älä siirry päivitystyön testaukseen ennen kuin raportointipolku toimii.

Seuraava osio asentaa ja validoi suorituksen valvojan.
80. Asenna suorituksen valvoja

LUMS-suorituksen valvoja vastaa odottavien päivitystöiden havaitsemisesta ja suorittamisesta asiakkaalla.

Arkkitehtuuri erottaa raportoinnin suorituksesta:
text

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

Tämä erottelu mahdollistaa säännöllisen asiakasraportoinnin jatkamisen itsenäisesti päivitysten suorituksesta.
81. Varmista valvojan asennus

Varmista, että valvoja on läsnä:
bash

ls -lh \
    /opt/lums-agent/watcher.py

Varmista asennettu versio:
bash

grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py

Nykyinen valvojan versio on:
text

1.2.1

82. Varmista valvojan palvelu

Tarkista systemd-yksikkö:
bash

systemctl cat \
    lums-agent-watcher.service

Palvelun on viitattava:
text

/opt/lums-agent/watcher.py

Varmista, että yksikkö on systemdin tiedossa:
bash

systemctl status \
    lums-agent-watcher.service \
    --no-pager

Palvelu voi olla inaktiivinen, kun suoritusta ei ole laukaistu.

Tämä ei itsessään ole virhe.
83. Varmista valvojan ajastin

Ennen valvojan ajastimen käyttöönottamista varmista, että:

    /etc/default/lums-agent on olemassa ja sisältää oikean asiakaskokoonpanon.

    LUMS-palvelimen päätepiste ja asiakastunniste on määritetty oikein.

    Manuaalinen agenttiajo onnistui ja palvelin hyväksyi asiakasraportin.

    Molemmat valvojan yksikkötiedostot asennettiin arkistosta.

Älä ota ajastinta käyttöön, kun todennus tai raportointi epäonnistuu.

Tarkista ajastin:
bash

systemctl cat \
    lums-agent-watcher.timer

Ota ajastin käyttöön vasta, kun kaikki yllä olevat edellytykset on varmistettu:
bash

sudo systemctl enable --now \
    lums-agent-watcher.timer

Varmista:
bash

systemctl status \
    lums-agent-watcher.timer \
    --no-pager

Tarkista seuraava ajastettu suoritus:
bash

systemctl list-timers \
    lums-agent-watcher.timer \
    --no-pager

84. Ymmärrä lepotilatietoinen suoritus

Valvoja voi käyttää asiakkaan lepotilatietoja ennen päivitystöiden suorittamista.

Aiottu virta on:
text

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

Lepotilan tunnistusta ei saa koskaan tulkita todennukseksi tai valtuutukseksi.

Se on vain suorituksen ajoitusmekanismi.
85. Varmista lepotilan tunnistus

Suorita lepotilan tunnistuspolku manuaalisesti asennetun agentin/valvojan toteutuksen kautta.

Tarkista syntyvä palveluloki:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager

Jos alusta ei tarjoa tarvittavia lepotilatietoja, asiakas voi raportoida lepotilan tunnistuksen olevan käyttämättömissä.

Tämä ei automaattisesti ole virhe.

Tärkeä ero on:
text

idle_supported = available

vastaan:
text

idle_supported = unavailable

Asiakasta ei saa olettaa lepotilaan vain siksi, että lepotilatietoja ei palautettu.
86. Luo hallittu testipäivitystyö

Älä aloita asennustestausta suurella järjestelmäpäivityksellä.

Käytä ensimmäisessä testissä pientä, tunnettua pakettia.

Paketin pitäisi:
text

exist in the configured repository
be safe to install
be removable again
not be required by the operating system

Esimerkki testipaketista:
text

sl

Ennen työn luomista varmista, onko se jo asennettu:
bash

dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true

Arch Linuxissa käytä pakettia, joka on saatavilla määritetyissä varastoissa ja sopii palautuvaan testiin.

Älä käytä sl-pakettia sokeasti kaikissa jakeluissa.
87. Varmista pakettihaku

Käytä LUMSin paketinhallintakäyttöliittymää valitun paketin hakemiseen.

Hakuvirta on:
text

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

Varmista, että tulos sisältää odotetut tiedot:
text

Package
Version
Description
Status
Action

Arch Linuxissa myös varastotiedot voidaan palauttaa.
88. Paketinhallinnan oikeudet

Paketinhallintaa rajoitetaan RBAC:lla.

Administrator:
text

Allowed

Operator:
text

Allowed

Viewer:
text

Not allowed

Viewer ei saa pystyä suorittamaan paketin asennusta tai poistoa kutsumalla API:a suoraan.

Selainkäyttöliittymän toiminnon piilottaminen on vain lisäkäytettävyysrajoitus.

Palvelinpuolen valtuutus on todellinen turvaraja.
89. Testaa paketin asennus

Luo asennustyö LUMS-käyttöliittymän kautta.

Looginen toiminto on:
text

INSTALL_PACKAGE

Työ tallennetaan LUMS-tietokantaan ennen kuin agentti suorittaa sen.

Odotettu virta on:
text

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

Seuraa työtä LUMS-käyttöliittymässä.

Älä muokkaa tietokantaa manuaalisesti pakottaaksesi työn tilan.
90. Varmista asennuksen tulos

Kun työ raportoi onnistumisesta, varmista paketti paikallisesti.

Debian/Ubuntu:
bash

dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    sl

Varmista, että paketinhallinta on samaa mieltä:
bash

apt-cache policy \
    sl

Paketti on todella asennettava.

LUMSin SUCCESS-tila vastaa onnistunutta asiakaspuolen toimintoa.
91. Varmista työn tulos

Tarkista LUMSin työhistoria.

Varmista:
text

Action
Package
Client
Start time
Completion time
Result

Asiakkaan palauttama tulos on palvelimen validoitava.

Virheelliset tai puutteelliset tulos tiedot eivät saa hiljaisesti muuttua onnistuneeksi työksi.

Tämä validointi on osa LUMSin turvallisuus- ja luotettavuusmallia.
92. Testaa paketin poisto

Kun asennus on varmistettu, luo poistotyö:
text

REMOVE_PACKAGE

Seuraa:
text

PENDING
   ↓
RUNNING
   ↓
SUCCESS

Kun työ on valmis:
bash

dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true

Pakettia ei pitäisi enää olla asennettuna.

Jos pakettia ei ollut asennettu ennen testiä, älä pidä sen puuttumista todisteena onnistuneesta poistotoiminnosta.
93. Testaa paketin päivitys

Pakettipäivitykset käyttävät:
text

UPDATE_PACKAGE

Palvelin validoi, että pyydetty paketti on saatavilla oleva päivitys, ennen kuin se luo vastaavan työn.

Yleinen virta on:
text

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

Älä rakenna päivityspyyntöjä manuaalisesti, jotka ohittavat normaalin validointipolun.
94. Testaa järjestelmäpäivitys

Täydellinen järjestelmäpäivitys käyttää:
text

UPDATE_SYSTEM

Tämä toiminto vaikuttaa asiakkaan paketinhallintatilaan laajemmin kuin yksittäisen paketin toiminto.

Ensimmäisessä järjestelmäpäivitystestissä:
text

Use a test client
Use a current backup
Monitor the console
Monitor the LUMS job
Do not interrupt the package manager

Älä käytä tuotantopalvelinta itseään ensimmäisenä järjestelmäpäivitystestin kohteena.
95. Paketinhallinnan lukot

APT ja pacman voivat käyttää paketinhallinnan lukkoja.

Kun toiminto epäonnistuu, koska toinen paketinhallintaprosessi on aktiivinen, tarkista käynnissä olevat prosessit ennen toimenpiteisiin ryhtymistä.

Debian/Ubuntu:
bash

ps aux | grep -E \
    '[a]pt|[d]pkg|[u]nattended'

Arch Linux:
bash

ps aux | grep -E \
    '[p]acman|[p]ar'

Älä poista paketinhallinnan lukkotiedostoja, kun paketinhallinta on todella käynnissä.

Lukko suojaa normaalisti samanaikaisilta pakettitoiminnoilta.
96. Erota LUMS-virheet paketinhallinnan virheistä

Kun työ epäonnistuu, määritä mikä kerros epäonnistui.
text

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

Tarkista asiakkaan loki:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Tarkista LUMS-kontti:
bash

sudo docker logs \
    --tail 200 \
    lums

Älä yritä epäonnistunutta työtä uudelleen välittömästi selvittämättä, miksi se epäonnistui.
97. Varmista työn tarkistuspisteet

LUMS seuraa työn ja pakettikohteiden tilaa.

Pakettipohjaisissa töissä yksittäiset pakettikohteet voidaan tarkistaa.

Aiottu toiminta on:
text

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

Tämä estää suoritettujen pakettitoimintojen tarpeettoman toistamisen keskeytyksen jälkeen.
98. Testaa hallittu työn palautus

Käytä ei-kriittistä testityötä.

Käynnistä työ ja tarkkaile sen tilaa:
text

PENDING

sitten:
text

RUNNING

Älä keskeytä tuotantopäivitystä tarkoituksella.

Käytä palautustestaukseen erillistä testiasiakasta ja hallittua pakettitoimintoa.

Keskeytyksen tai simuloidun virheen jälkeen käynnistä valvoja uudelleen:
bash

sudo systemctl restart \
    lums-agent-watcher.timer

Tarkista sitten:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Varmista, että jo onnistuneita pakettikohteita ei suoriteta tarpeettomasti uudelleen.
99. Varmista uudelleenkäynnistyksen tunnistus

Jotkin pakettitoiminnot voivat vaatia uudelleenkäynnistyksen.

Agentti/valvoja raportoi uudelleenkäynnistysvaatimukset LUMSille.

Yleinen virta on:
text

Package operation
      ↓
Reboot requirement detected
      ↓
Result reported
      ↓
LUMS records reboot state

Kun testitoiminto todella vaatii uudelleenkäynnistyksen, varmista vastaava työtulos LUMS-käyttöliittymässä.

Älä käynnistä tuotantoasiakasta uudelleen vain testataksesi mekanismia, ellei järjestelmä ole tarkoitettu kyseiseen testiin.
100. Varmista raportointi uudelleenkäynnistyksen jälkeen

Kun testiasiakas käynnistetään uudelleen, varmista, että:
text

systemd
   ↓
LUMS Agent timer
   ↓
Agent report
   ↓
LUMS server

jatkaa toimintaansa.

Tarkista:
bash

systemctl status \
    lums-agent.timer \
    --no-pager

ja:
bash

systemctl status \
    lums-agent-watcher.timer \
    --no-pager

Tarkista sitten viimeisin raportti LUMS-käyttöliittymästä.
101. Varmista päivitysten tunnistus

Suorita agentti manuaalisesti:
bash

sudo systemctl start \
    lums-agent.service

Tarkista:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Asiakkaan pitäisi raportoida:
text

Installed packages
Available updates
Agent status

Palvelimen pitäisi päivittää asiakkaan nykyinen tila.

Älä sekoita:
text

available updates

ja:
text

installed packages

Ne edustavat eri tietojoukkoja.
102. Varmista asennettu ohjelmisto

Avaa asiakkaan asennettujen ohjelmistojen osio LUMSissa.

Pakettiluettelon pitäisi vastata asiakaspuolen paketinhallintaa.

Debian/Ubuntu:
bash

dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n'

Arch:
bash

pacman -Q

LUMSin luettelo on tiedoksi, kunnes työ luodaan nimenomaisesti.

Asennettujen pakettien suodatin ei itsessään muuta asiakasta.
103. Varmista pakettihaku erikseen

Paketinhallinnan haku on erillään asennettujen pakettien suodattimesta.

Ero on:
text

Installed Package Filter
    ↓
Searches the package inventory already reported by the client

Package Management Search
    ↓
Requests package information from the client's package manager

Älä käsittele kahta hakutoimintoa keskenään vaihdettavina.

Paketti voi olla saatavilla APT:n tai pacmanin kautta ilman, että se on asennettu.
104. Varmista Viewer-paketti eristys

Kirjaudu sisään Viewerinä.

Varmista, että paketinhallintakäyttöliittymä ei ole käytettävissä.

Varmista sitten palvelinpuolen rajoitus yrittämällä luvatonta paketinhallintapyyntöä hyväksytyn testimenetelmän kautta.

Pyyntö on hylättävä.

Viewerin pääsyn on pysyttävä vain luku -tilassa.
105. Varmista operaattorin paketinhallinta

Kirjaudu sisään operaattorina.

Varmista pääsy:
text

Package Search
Package Installation
Package Removal
Package Updates
Update Jobs
Update History

Operaattori ei saa saada pääsyä vain ylläpitäjälle tarkoitettuihin käyttäjähallintatoimintoihin.
106. Varmista ylläpitäjän paketinhallinta

Kirjaudu sisään ylläpitäjänä.

Varmista samat paketinhallintaominaisuudet kuin operaattorilla.

Varmista lisäksi pääsy:
text

User Management
Client Management
Client Token Rotation

Ylläpitäjän oikeudet on pidettävä palvelinpuolella valvottuina.
107. Ensimmäinen end-to-end-pakettitesti

Ensimmäisen täydellisen paketinhallintatestin pitäisi noudattaa tätä järjestystä:
text

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

Vasta kun tämä järjestys onnistuu, laajempi päivitystestaus voi alkaa.
108. Asiakkaan suorituksen tarkistuspiste

Varmista:
text

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

Tässä vaiheessa LUMSin ydinasiakassuorituspolku on asennettu ja validoitu.

Seuraava osio kattaa täydellisen end-to-end-validoinnin, RBAC-varmentamisen, varmuuskopioinnin/palautuksen, ylläpidon, päivitykset ja lopulliset asennustarkistukset.
109. Täydellinen end-to-end-validointi

Kun palvelin ja vähintään yksi Linux-asiakas on määritetty, suorita täydellinen end-to-end-validointi.

Täydellinen LUMS-polku on:
text

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

Älä pidä asennusta valmiina vain siksi, että verkkokäyttöliittymä avautuu.

Kaikki pääkerrokset on varmistettava.
110. Palvelimen kunnon tarkistus

Varmista LUMS-kontti:
bash

sudo docker ps \
    --filter name=lums

Varmista kontin tila:
bash

sudo docker inspect \
    lums \
    --format '{{.State.Status}}'

Odotettu:
text

running

Tarkista viimeisimmät lokit:
bash

sudo docker logs \
    --tail 100 \
    lums

Lokeissa ei pitäisi olla aktiivista käynnistys- tai migraatiovirhettä.
111. Kontin turvallisuustarkistus

Varmista ajonaikainen turvakokoonpano:
bash

sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'

Odotettu perustaso:
text

User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]

Varmista verkkosidonta:
bash

sudo docker port \
    lums

Odotettu:
text

5000/tcp -> 127.0.0.1:5050

112. Pysyvän tallennuksen tarkistus

Varmista LUMS-taltio:
bash

sudo docker volume inspect \
    lums-data

Varmista, että sovelluksen tietokanta on olemassa:
bash

sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db

Tietokannan on sijaittava pysyvässä tallennuksessa.

Älä tallenna tuotantotietokantaa vain kontin tiedostojärjestelmään.
113. SQLite-kunnon tarkistus

Tarkista nykyinen SQLite-ajonaikainen kokoonpano:
bash

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

Nykyinen perustaso on:
text

journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0

Sovellus ottaa viiteavainten valvonnan eksplisiittisesti käyttöön.
114. SQLite-eheystarkistus

Suorita:
bash

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

Odotettu:
text

ok

Älä jatka uuteen tuotantokäyttöönottoon, jos eheystarkistus raportoi korruptiosta.
115. Varmista tietokantamigraatiot

Tarkista migraation tila:
bash

sudo docker logs \
    --tail 200 \
    lums | grep -i migration

Sovelluksen on suoritettava määritetyt migraationsa ennen normaalia toimintaa.

Älä muokkaa migraation tilataulukkoa manuaalisesti, ellei nykyinen LUMS-migraatiomenettely nimenomaisesti vaadi sitä.
116. Suorita automatisoitu testisarja

LUMSin kehitys-/testiympäristössä:
bash

cd /opt/lums-public

Suorita:
bash

./.venv-test/bin/pytest -q

Testien määrä muuttuu projektin kehittyessä; luota komennon tulokseen, ei tässä asiakirjassa mainittuun kiinteään määrään.

Tärkeä vaatimus on:
text

all tests pass

Älä jätä huomiotta epäonnistuneita testejä, koska tuotannon verkkokäyttöliittymä näyttää toimivalta.
117. Varmista RBAC

Nykyinen roolimalli on:
Toiminto	Administrator	Operator	Viewer
View clients	Yes	Yes	Yes
Installed software	Yes	Yes	Yes
Available updates	Yes	Yes	No
Create/execute jobs	Yes	Yes	No
Update history	Yes	Yes	No
Package management	Yes	Yes	No
System maintenance	Yes	Yes	No
Create/disable clients	Yes	No	No
Rotate client tokens	Yes	No	No
User management	Yes	No	No
Role management	Yes	No	No

Käyttöliittymän pitäisi heijastaa näitä oikeuksia.

Vielä tärkeämpää, API:n on valvottava niitä itsenäisesti.
118. Varmista ylläpitäjän pääsy

Kirjaudu sisään ylläpitäjänä.

Varmista pääsy:
text

Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management

Varmista asiakashallintatoiminnot:
text

Create client
Disable client
Rotate client token

Ylläpitäjän pitäisi pystyä suorittamaan nämä toiminnot.
119. Varmista operaattorin pääsy

Kirjaudu sisään operaattorina.

Varmista pääsy:
text

Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance

Varmista, että vain ylläpitäjälle tarkoitetut toiminnot eivät ole käytettävissä:
text

User management
Role management
Client creation/disabling
Client-token rotation

Älä luota vain piilotettuihin käyttöliittymäelementteihin.

Suojattujen API-toimintojen on hylättävä luvattomat pyynnöt.
120. Varmista Viewerin pääsy

Kirjaudu sisään Viewerinä.

Viewerin pitäisi päästä käsiksi:
text

Clients
Installed software

Seuraavat eivät saa olla käytettävissä:
text

Available updates
Update jobs
Update history
Package management
System maintenance

Viewer ei saa pystyä muuttamaan asiakkaan tilaa.
121. Varmista asiakastodennus

Vahvista, että jokainen asiakas käyttää omaa Bearer-tunnistettaan.

Odotettu malli on:
text

Client A → Token A
Client B → Token B
Client C → Token C

Älä jaa tunnisteita asiakkaiden kesken.

Varmista, että vaihdettua tai mitätöityä tunnistetta ei enää hyväksytä.

Älä koskaan laita todellisia tunnisteita testitulosteisiin tai dokumentaatioon.
122. Varmista päivitysten tunnistus

Testiasiakkaalla:
bash

sudo systemctl start \
    lums-agent.service

Tarkista:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Varmista sitten asiakas LUMS-käyttöliittymässä.

Raportoitujen tietojen pitäisi sisältää nykyinen pakettiluettelo ja päivitystiedot tuettaessa.
123. Varmista päivitystyön luonti

Luo hallittu päivitystyö LUMS-käyttöliittymän kautta.

Työn pitäisi aluksi näkyä:
text

PENDING

Valvoja käsittelee työn sitten:
text

PENDING
   ↓
RUNNING
   ↓
SUCCESS

tai:
text

PENDING
   ↓
RUNNING
   ↓
FAILED

riippuen todellisesta toimintotuloksesta.

Älä muuta tietokannan tilaa manuaalisesti.
124. Varmista työn suoritus

Tarkista asiakkaan valvoja:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Tarkista LUMS-palvelin:
bash

sudo docker logs \
    --tail 200 \
    lums

Vertaa palvelinpuolen työn tilaa asiakaspuolen suoritustulokseen.

Näiden on oltava yhtäpitäviä.
125. Varmista pakettituloksen validointi

Työ ei saa tulla onnistuneeksi vain siksi, että asiakas lähetti syntaktisesti kelvollisen vastauksen.

Palvelin validoi palautetun tuloksen.

Varmista tämä automatisoiduilla tulosvalidointitesteillä:
bash

./.venv-test/bin/pytest -q \
    tests/test_job_result.py

Onnistuneen tuloksen on sisällettävä odotettu rakenne ja kelvollinen työkonteksti.

Virheelliset tai epäjohdonmukaiset tulokset on hylättävä.
126. Varmista työn palautus

Käytä palautustestaukseen erillistä testiasiakasta.

Palautusmalli on:
text

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

Palautuksen jälkeen aiemmin onnistuneita pakettikohteita ei saa toistaa tarpeettomasti.

Tarkista:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Varmista sitten lopullinen työn tila LUMSissa.
127. Varmista uudelleenkäynnistyksen tunnistus

Kun kyseessä on hallittu testipäivitys, joka vaatii uudelleenkäynnistyksen, varmista, että asiakas raportoi uudelleenkäynnistysvaatimuksen.

Uudelleenkäynnistyksen jälkeen:
bash

systemctl status \
    lums-agent.timer \
    --no-pager

ja:
bash

systemctl status \
    lums-agent-watcher.timer \
    --no-pager

Asiakkaan on jatkettava normaalia raportointia käynnistyksen jälkeen.
128. Varmista valvontalokitus

Suorita hallittu ylläpitotoimenpide ja tarkista sitten LUMSin valvontaloki.

Relevantit toiminnot ovat:
text

Login
User creation
Client creation
Client-token rotation
Job creation
Package management

Valvontamerkintöjen pitäisi tarjota riittävät tiedot ylläpitotoimenpiteen rekonstruoimiseksi paljastamatta salaisuuksia.

Älä kirjaa:
text

Passwords
Client tokens
Application secrets
Private keys
Session secrets

129. Varmista lokien redaktio

Tarkista viimeisimmät lokit:
bash

sudo docker logs \
    --tail 200 \
    lums

Tarkista asiakaslokit:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

ja:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Todennustietojen ja salaisuuksien ei pidä näkyä normaaleissa diagnostiikkatulosteissa.

Jos diagnostiikkakomento paljastaisi salaisuuden, älä liitä sen tulostetta ongelmaan, commitiin tai dokumentaatioon.
130. Varmista verkon altistuminen

Tarkista kuuntelevat portit:
bash

sudo ss -lntp

LUMS-sovellusportin pitäisi pysyä:
text

127.0.0.1:5050

Nginx tarjoaa ulkoisen palvelun:
text

:80
:443

Sovellusta ei saa altistaa suoraan seuraavien kautta:
text

0.0.0.0:5050

tai:
text

0.0.0.0:5000

131. Varmista palomuurikokoonpano

Jos isäntäpalomuuri on käytössä, tarkista se:
bash

sudo ufw status verbose

Käyttöönoton pitäisi altistaa vain isännän vaatimat palvelut.

Älä luo palomuurisääntöä portille 5050 vain siksi, että Docker käyttää kyseistä porttia sisäisesti.

Aiottu arkkitehtuuri on:
text

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

132. Varmuuskopiointistrategia

LUMS SQLite -tietokanta on pysyvä sovellustila.

Vähintään varmuuskopioiden pitäisi suojata:
text

LUMS database
TLS material
LUMS application secret
Deployment configuration

Varmuuskopiot on tallennettava aktiivisen LUMS-kontin ulkopuolelle.

Älä tallenna varmuuskopioita:
text

/app

äläkä luota kontin tiedostojärjestelmään.

Docker-taltio:
text

lums-data

sisältää pysyvät sovellustiedot, mutta Docker-taltio ei itsessään ole varmuuskopio.
133. Tietokannan varmuuskopiointi

Ennen tietokannan varmuuskopiointia tunnista tietokantatiedosto:
bash

sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db

Tietokannan varmuuskopiointi on suoritettava johdonmukaisella SQLite-varmuuskopiomekanismilla.

Älä kopioi live-SQLite-tietokantaa sokeasti sen ollessa muutoksen kohteena, jos varmuuskopiomenettely ei voi taata johdonmukaisuutta.

Kun varmuuskopio on luotu, varmista, että varmuuskopiotiedosto on olemassa ja suojattu.
134. Kokoonpanon varmuuskopiointi

Suojaa seuraava käyttöönottomateriaali:
text

/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums

Älä julkaise näitä tiedostoja.

Seuraavat tiedostot ovat erityisen arkaluonteisia:
text

/etc/lums/secrets/lums_secret
/etc/lums/tls/lums.key

Suojaa varmuuskopioiden oikeudet vastaavasti.
135. Palautuksen suunnittelu

Palautus on testattava ei-tuotantojärjestelmässä ennen kuin sitä tarvitaan katastrofipalautuksessa.

Palautusjärjestys on käsitteellisesti:
text

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

Älä korvaa tuotantotietokantaa säilyttämättä ensin olemassa olevaa tilaa.
136. Varmista tietokannan palautus

Kun tietokanta on palautettu, suorita:
bash

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

Odotettu:
text

ok

Varmista sitten:
text

users
clients
update jobs
package data
audit data

Älä oleta, että onnistunut SQLite-eheystarkistus todistaa koko sovellustilan olevan oikein.
137. Ylläpidon periaatteet

Rutiininomaisen ylläpidon on noudatettava:
text

Observe
   ↓
Back up
   ↓
Change
   ↓
Verify

Älä suorita liittymättömiä ylläpitotoimenpiteitä aktiivisen päivitystyön aikana.

Ennen ylläpitoa:
bash

sudo docker ps \
    --filter name=lums

Tarkista aktiiviset työt LUMS-käyttöliittymästä.

Jos päivitys on käynnissä, anna sen valmistua, ellei ylläpitotoimenpide nimenomaisesti vaadi keskeytystä.
138. Kontin ylläpito

Tarkista käynnissä oleva kuva:
bash

sudo docker inspect \
    lums \
    --format '{{.Config.Image}}'

Tarkista kontti:
bash

sudo docker ps \
    --filter name=lums

Tarkista viimeisimmät lokit:
bash

sudo docker logs \
    --tail 100 \
    lums

Älä poista pysyvää taltiota tavallisen kontin ylläpidon aikana.

Taltio sisältää sovellustilan.
139. Kuvan ylläpito

Ennen tuotantokuvan korvaamista:
bash

cd /opt/lums-public

Suorita automatisoidut testit:
bash

./.venv-test/bin/pytest -q

Rakenna uusi kuva:
bash

sudo docker build \
    -t lums:new \
    .

Älä korvaa käynnissä olevaa konttia ennen kuin kuva on läpäissyt vaaditun validoinnin.

Pidä nykyinen toimiva kontti saatavilla, kunnes korvaava on varmistettu.
140. Hallittu kontin vaihto

Kun korvaat tuotantokontin:
text

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

Pysyvän taltion on pysyttävä:
text

lums-data

Salaisuuden liitoksen on pysyttävä vain luku -tilassa.

Sovellusportin on pysyttävä vain localhostissa.
141. Varmista ajonaikainen turvallisuus vaihdon jälkeen

Jokaisen kontin vaihdon jälkeen toista:
bash

sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'

Varmista:
text

User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]

Varmista myös:
bash

sudo docker port \
    lums

Odotettu:
text

5000/tcp -> 127.0.0.1:5050

142. Varmista pysyvät tiedot vaihdon jälkeen

Kun korvaava kontti on käynnistetty:
bash

sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db

Sitten:
bash

sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY

Odotettu:
text

ok

Varmista lopuksi, että olemassa olevat käyttäjät ja asiakkaat ovat edelleen läsnä LUMS-käyttöliittymän kautta.
143. Ylläpidon valmistumisen tarkistuspiste

Ylläpidon jälkeen varmista:
text

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

Vasta näiden tarkistusten jälkeen ylläpitotoimenpide on valmis.
144. Asennuksen tila tässä vaiheessa

Oikein asennettu LUMS-ympäristö koostuu nyt:
text

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

Tämä on aiottu toiminnallinen arkkitehtuuri.

Seuraava osio kattaa päivitykset, asennuksen poistamisen ja lopullisen asennuksen tarkistuslistan.
145. Päivitysmenettely

LUMS-päivitykset on suoritettava hallituissa vaiheissa.

Suositeltu järjestys on:
text

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

Älä päivitä tuotantoasennusta vain siksi, että uusi Git-revisio on olemassa.

Tarkista muutokset ensin:
bash

cd /opt/lums-public

git status
git log --oneline -10

Tarkista asiaankuuluvat sovellus-, agentti- ja migraatiomuutokset ennen käyttöönottoa.
146. Luo ennen päivitystä varmuuskopio

Ennen tuotantokontin korvaamista luo ajantasainen varmuuskopio LUMSin pysyvästä tilasta.

Varmista aktiivinen taltio:
bash

sudo docker inspect \
    lums \
    --format '{{json .Mounts}}'

Vahvista, että:
text

lums-data

on edelleen liitetty kohtaan:
text

/var/lib/lums

Suojaa myös ulkoinen kokoonpano:
text

/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/

Älä jatka päivitystä, jos vaadittua varmuuskopiota ei voida varmistaa.
147. Lopeta tarpeettomat muutokset päivityksen aikana

Ennen päivitystä tarkista aktiiviset työt LUMS-käyttöliittymästä.

Vältä sovelluksen korvaamista, kun kriittinen päivitystyö on aktiivisesti käynnissä.

Odota tarvittaessa, kunnes työ saavuttaa lopullisen tilan:
text

SUCCESS

tai:
text

FAILED

Älä muuta työtä manuaalisesti tilasta RUNNING tilaan SUCCESS tai FAILED vain tehdäksesi päivityksen mahdolliseksi.
148. Päivitä arkisto

Siirry arkistoon:
bash

cd /opt/lums-public

Tarkista nykyinen tila:
bash

git status

Päivitä arkisto normaalin projektityönkulun mukaisesti.

Päivityksen jälkeen:
bash

git log --oneline -5

Varmista, että aiottu revisio on check out -tilassa.

Älä ota käyttöön arkistoa, joka sisältää tahattomia paikallisia muutoksia.

Jos paikallisia muutoksia on:
bash

git status

Tarkista ne ennen jatkamista.
149. Suorita testisarja ennen rakentamista

Suorita:
bash

./.venv-test/bin/pytest -q

Kaikkien testien on läpäistävä.

Muuttunut testien määrä ei automaattisesti ole ongelma. Vaatimus on, että
koko sarja päättyy onnistuneesti.
150. Rakenna päivitetty kuva

Rakenna uusi kuva korvaamatta heti käynnissä olevaa konttia:
bash

sudo docker build \
    -t lums:new \
    .

Varmista kuva:
bash

sudo docker image inspect \
    lums:new

Koontien on päätyttävä onnistuneesti.

Älä käytä epäonnistunutta tai osittain rakennettua kuvaa tuotantokäyttöönottoon.
151. Varmista päivitetty kuva

Tarkista kuvan metatiedot:
bash

sudo docker image inspect \
    lums:new \
    --format '
User={{.Config.User}}
Entrypoint={{json .Config.Entrypoint}}
Cmd={{json .Config.Cmd}}
'

Kuvan on säilytettävä odotettu ei-root-sovellusmalli.

Tuotannon ajonaikaisen ympäristön on edelleen tarjottava:
text

read-only root filesystem
dropped Linux capabilities
no-new-privileges
read-only secret mount
persistent application volume
localhost-only application port

152. Korvaa tuotantokontti

Kun uusi kuva on läpäissyt validoinnin, korvaa käynnissä oleva kontti vakiintuneella kovennetulla kokoonpanolla.

Pysäytä olemassa oleva kontti:
bash

sudo docker stop \
    lums

Poista vain kontti:
bash

sudo docker rm \
    lums

Älä poista:
text

lums-data

Käynnistä korvaava kovennetulla ajonaikaisella ympäristöllä:
bash

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

153. Varmista korvaava kontti

Tarkista:
bash

sudo docker ps \
    --filter name=lums

Sitten:
bash

sudo docker logs \
    --tail 100 \
    lums

Varmista ajonaikainen ympäristö:
bash

sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'

Odotettu:
text

User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]

154. Varmista sovelluksen saatavuus

Tarkista paikallinen sovelluspäätepiste:
bash

curl -I \
    http://127.0.0.1:5050/

Testaa sitten julkinen HTTPS-polku:
bash

curl -I \
    https://LUMS-SERVER/

Varmista kirjautuminen selaimen kautta.

Älä pidä päivitystä valmiina ennen kuin myös ulkoinen HTTPS-polku on testattu.
155. Varmista pysyvä tila päivityksen jälkeen

Tarkista tietokanta:
bash

sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db

Suorita:
bash

sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY

Odotettu:
text

ok

Varmista verkkokäyttöliittymän kautta, että:
text

users
clients
jobs
audit history
package information

pysyvät saatavilla.
156. Varmista asiakasviestintä päivityksen jälkeen

Suorita agentti testiasiakkaalla:
bash

sudo systemctl start \
    lums-agent.service

Tarkista:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Varmista, että palvelin hyväksyy raportin.

Varmista sitten asiakas LUMS-käyttöliittymässä.
157. Varmista päivityksen suoritus päivityksen jälkeen

Luo hallittu testityö.

Varmista:
text

PENDING
   ↓
RUNNING
   ↓
SUCCESS

tai odotettu:
text

FAILED

tila, kun toiminto todella epäonnistuu.

Tarkista valvoja:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Tämä vahvistaa, että päivitys ei rikkonut suorituspolkua.
158. Varmista turvallisuusperustaso päivityksen jälkeen

Jokaisen tuotantopäivityksen on säilytettävä turvallisuusperustaso.

Varmista:
text

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

Toiminnallista päivitystä, joka heikentää näitä ominaisuuksia, ei pidetä valmiina.
159. Palautusmenettely

Jos uusi kontti epäonnistuu validoinnissa, älä tuhoa edellisen käyttöönoton tietoja heti.

Tarkista ensin:
bash

sudo docker logs \
    --tail 200 \
    lums

Jos edellinen kuva on edelleen saatavilla:
bash

sudo docker images

palauta aiemmin validoitu kuva käyttäen samaa kovennettua konttikokoonpanoa.

Pysyvä taltio pysyy:
text

lums-data

Älä palauta tietokannan varmuuskopiota vain siksi, että sovelluskontti korvattiin.

Palauta tietokanta vain, kun itse tietokanta on palautettava.
160. Asennuksen poiston valmistelu

Ennen LUMSin poistamista päätä, onko pysyvät sovellustiedot säilytettävä.

Seuraavat ovat erillisiä resursseja:
text

Container
Image
Persistent volume
Configuration
TLS material
Nginx configuration
Client installations

Kontin poistaminen ei poista Docker-taltiota.

Tämä ero on tarkoituksellinen.
161. Poista LUMS-kontti

Pysäytä kontti:
bash

sudo docker stop \
    lums

Poista se:
bash

sudo docker rm \
    lums

Varmista:
bash

sudo docker ps -a \
    --filter name=lums

Pysyvä taltio on edelleen olemassa, ellei sitä nimenomaisesti poisteta.
162. Poista LUMS Docker -kuva

Listaa kuvat:
bash

sudo docker images \
    'lums*'

Poista vain kuvat, joita ei enää tarvita:
bash

sudo docker rmi \
    lums:new

Toista tarvittaessa muille vanhentuneille paikallisille LUMS-kuville.

Älä poista kuvaa, joka tarvitaan parhaillaan palautukseen, ennen kuin asennus on täysin poistettu käytöstä.
163. Poista pysyvä taltio

Suorita tämä vaihe vain, kun LUMS-tietokantaa ei enää tarvita.

Varmista:
bash

sudo docker volume inspect \
    lums-data

Luo tarvittaessa lopullinen varmuuskopio.

Poista sitten:
bash

sudo docker volume rm \
    lums-data

Tämä poistaa pysyvästi kyseiseen taltioon tallennetut pysyvät sovellustiedot.

Älä suorita tätä komentoa normaalin päivityksen aikana.
164. Poista LUMS-palvelimen kokoonpano

Kun palvelin poistetaan pysyvästi käytöstä, poista LUMS-kohtainen kokoonpano:
text

/etc/lums/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums

Poista Nginx-sivusto:
bash

sudo rm -f \
    /etc/nginx/sites-enabled/lums

Poista kokoonpano:
bash

sudo rm -f \
    /etc/nginx/sites-available/lums

Validoi sitten Nginx:
bash

sudo nginx -t

Lataa uudelleen:
bash

sudo systemctl reload nginx

Poista /etc/lums/ vasta, kun olet varmistanut, ettei mikään muu sovellus ole siitä riippuvainen.
165. Poista asiakasasennukset

LUMS-asiakkaat on poistettava käytöstä erikseen.

Poista agentin ajastin käytöstä:
bash

sudo systemctl disable --now \
    lums-agent.timer

Poista valvojan ajastin käytöstä:
bash

sudo systemctl disable --now \
    lums-agent-watcher.timer

Pysäytä mahdolliset jäljellä olevat palvelut:
bash

sudo systemctl stop \
    lums-agent.service \
    lums-agent-watcher.service

Poista asennetut systemd-yksiköt:
bash

sudo rm -f \
    /etc/systemd/system/lums-agent.service \
    /etc/systemd/system/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent.timer \
    /etc/systemd/system/lums-agent-watcher.timer

Lataa systemd uudelleen:
bash

sudo systemctl daemon-reload

Poista agentin asennus:
bash

sudo rm -rf \
    /opt/lums-agent

Poista asiakaskokoonpano:
bash

sudo rm -f \
    /etc/default/lums-agent

Suorita nämä vaiheet vain, kun asiakas todella poistetaan LUMS-hallinnasta.
166. Lopullinen palvelinasennuksen tarkistuslista

Valmiin LUMS-asennuksen on täytettävä kaikki seuraavat:
text

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

167. Lopullinen asiakasasennuksen tarkistuslista
text

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

168. Lopullinen toiminnallinen tarkistuslista
text

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

169. Lopullinen turvallisuustarkistuslista
text

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

170. Lopullinen testitarkistuslista

Suorita täydellinen automatisoitu testisarja:
bash

cd /opt/lums-public

./.venv-test/bin/pytest -q

Asennusta on pidettävä valmiina vasta, kun täydellinen testisarja läpäisee.

Varmista sitten tuotannon ajonaikainen ympäristö manuaalisesti:
bash

sudo docker ps \
    --filter name=lums

bash

sudo docker logs \
    --tail 100 \
    lums

bash

curl -I \
    https://LUMS-SERVER/

bash

sudo ss -lntp

171. Lopullinen dokumentaation tarkistus

Ennen kuin julistat asennuksen valmiiksi, varmista, että dokumentaatio vastaa todellista käyttöönottoa.
