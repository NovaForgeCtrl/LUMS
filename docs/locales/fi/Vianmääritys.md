# LUMS Vianmääritys

Tämä opas tarjoaa vianmääritysmenettelyt LUMS-palvelimelle, Linux-agenteille, suorituksen valvojalle, päivitystöille, todentamiselle, paketinhallinnalle, tietokannalle ja Docker-käyttöönotolle.

Vianmääritysprosessin tulee aina alkaa **havainnoinnilla ennen muutosta**.

Tavoitteena on tunnistaa ensimmäinen komponentti, jossa odotettu toiminta lakkaa, ilman tarpeetonta konfiguraation, tietokannan tilan, tunnistetietojen tai turvakontrollien muuttamista.

---

## Aloittaminen: Vianmääritys turvallisesti

Jos olet uusi Linuxissa, virhe ei automaattisesti tarkoita, että tietoja on
hävinnyt. Älä muuta useita asioita kerralla. Aloita alla olevista tarkistuksista
ja kirjaa **milloin** ongelma ilmenee ja **mikä toiminto** tapahtui välittömästi
ennen sitä.

### Ensimmäiset tarkistukset LUMS-palvelimella

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t

docker ps -a näyttää myös pysäytetyt kontit. docker logs lukee viimeisimmät
sovellusviestit. systemctl status näyttää, onko Nginx käynnissä;
nginx -t tarkistaa sen konfiguraation muuttamatta sitä. Jos nginx -t epäonnistuu,
älä lataa Nginxiä uudelleen ennen kuin syy on korjattu.
Ensimmäiset tarkistukset hallinnoidulla asiakkaalla
bash

sudo systemctl status lums-agent.service --no-pager
sudo journalctl -u lums-agent.service -n 100 --no-pager
sudo systemctl status lums-agent-watcher.service --no-pager
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager

Agentti ja valvoja ovat erillisiä palveluita: onnistunut agenttiraportti ei
todista, että valvoja voi suorittaa päivitystöitä. oneshot-palvelulle
inactive voi olla normaalia onnistuneen suorituksen jälkeen; tarkista myös
tulos ja lokiviestit.
Ennen komentotulosteen jakamista

Tarkista lokit ja konfiguraatio salasanojen, asiakastunnisteiden, istunto- tai API-
avainten, yksityisten avainten ja henkilötietojen varalta. Älä koskaan jaa salaisuustiedoston sisältöä
tai täydellisiä ympäristömuuttujien arvoja. Jos tarvitset apua, jaa vain
asiaankuuluvat virheilmoitukset poistettuasi arkaluonteiset tiedot.

Älä aloita poistamalla tietokantaa tai Docker-taltiota, ajamalla
konttia etuoikeutetusti, poistamalla turva-asetuksia käytöstä, poistamalla paketinhallinnan
lukkotiedostoja tai vaihtamalla tunnisteita. Nämä toimet voivat vahingoittaa tietoja, poistaa todisteita
tai pahentaa ongelmaa. Jos tarkistus epäonnistuu, tallenna sen tuloste ja jatka
asiaankuuluvaan osioon alla.
1. Vianmäärityksen filosofia

LUMS koostuu useista riippumattomista komponenteista.

Onnistunut asiakasraportti ei automaattisesti tarkoita, että päivityksen suoritus toimii.

Pääasiallinen toimintapolku on:
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

Päivityksen suoritus lisää paketinhallintakerroksen:
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

Vianmäärityksessä tunnista ensimmäinen epäonnistuva komponentti.

Esimerkiksi:
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

Älä heti:

    muokkaa tietokantaa

    poista Docker-taltiota

    asenna agenttia uudelleen

    vaihda tunnistetietoja

    poista paketinhallinnan lukkotiedostoja

    poista turvakontrolleja käytöstä

    tee kontista etuoikeutettua

Nämä toimet voivat tuhota hyödyllistä diagnostista tietoa tai luoda lisäongelmia.
2. Diagnostinen perustaso

Ennen tietyn ongelman tutkimista selvitä pääkomponenttien nykyinen tila.

Tuotannon LUMS-käyttöönotto käyttää:
text

Application port: 127.0.0.1:5050
External access: HTTPS through Nginx
Database: /var/lib/lums/lums.db
Docker volume: lums-data
Agent: 1.7.0
Watcher: 1.2.1

Tuotantokontti on kovennettu seuraavasti:
text

Read-only root filesystem
No Linux capabilities
no-new-privileges
Non-root application user
Protected secret mount
Dedicated persistent data volume

Sovellusportti on tarkoituksella sidottu vain paikalliseen isäntään.

Odotettu verkkopolku on:
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

3. Ensimmäiset diagnostiset tarkistukset
3.1 Tarkista LUMS-kontti

LUMS-palvelimella:
bash

sudo docker ps

lums-kontin pitäisi olla käynnissä.

Täydellinen konttiyleiskatsaus:
bash

sudo docker ps -a \
    --filter name=lums

Älä poista pysäytettyjä kontteja ennen niiden tutkimista.

Vanhemmat varakontit voivat sisältää hyödyllistä tietoa käyttöönotto-ongelman tutkimisessa.
3.2 Tarkista viimeisimmät sovelluslokit

Tarkista viimeisimmät LUMS-lokit:
bash

sudo docker logs \
    --tail 100 \
    lums

Live-tuloste:
bash

sudo docker logs \
    -f \
    lums

Kun tutkit tiettyä pyyntöä tai työtä, aloita lokien tarkastelu ennen ongelman toistamista mahdollisuuksien mukaan.

Tämä helpottaa asiakastoiminnon korreloimista vastaavaan palvelinpuolen tapahtumaan.
3.3 Tarkista Nginx

Tarkista käänteisvälityspalvelin:
bash

sudo systemctl status nginx \
    --no-pager

Validoi konfiguraatio:
bash

sudo nginx -t

Onnistunut konfiguraatiotesti ilmoittaa:
text

syntax is ok
test is successful

Jos Nginx ei ole käynnissä, HTTPS-pääsy LUMSiin yleensä epäonnistuu, vaikka Docker-kontti itsessään olisi kunnossa.
3.4 Tarkista agentti

Hallinnoidulla Linux-asiakkaalla:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

Tarkista viimeisimmät agentin tulosteet:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Type=oneshot-palvelulle inaktiivinen tila onnistuneen suorituksen jälkeen voi olla normaalia.

Tärkeä tieto on suorituksen tulos.

Onnistunut suoritus päättyy:
text

status=0/SUCCESS

3.5 Tarkista suorituksen valvoja

Valvoja on erillinen komponentti raportointiagentista.

Tarkista se itsenäisesti:
bash

sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager

Tarkista viimeisimmät tulosteet:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager

Onnistunut agenttiraportti ei siis todista, että suorituksen valvoja toimii oikein.
3.6 Tarkista LUMS-ajastimet

Tarkista kaikki asiaankuuluvat ajastimet:
bash

sudo systemctl list-timers \
    --all | grep lums

Odotetut ajastimet sisältävät agentin ja valvojan ajoitusmekanismit.

Jos ajastin puuttuu tai on inaktiivinen, tarkista vastaava yksikkö ennen minkään muuttamista.
4. LUMS-kontti ei ole käynnissä

Jos lums-kontti ei ole käynnissä, älä heti luo sitä uudelleen.

Tarkista ensin sen tila:
bash

sudo docker ps -a \
    --filter name=lums

Tarkista sitten kontti:
bash

sudo docker inspect lums

Tarkista viimeisimmät lokit:
bash

sudo docker logs \
    --tail 200 \
    lums

Tarkista poistumistila:
bash

sudo docker inspect \
    --format '{{.State.Status}} {{.State.ExitCode}}' \
    lums

Tulos voi auttaa erottamaan:
text

Normal shutdown
Application failure
Configuration failure
Container runtime failure
Health/startup problem

Jos kontti poistui odottamatta, säilytä lokit ja kontin tila ennen sen korvaamista.
5. Kontti käynnistyy, mutta LUMS ei ole tavoitettavissa

LUMS-sovellusta ei ole tarkoitettu käytettäväksi suoraan Docker-sovellusportin kautta verkosta.

Tuotantosovellus on sidottu:
text

127.0.0.1:5050

Varmista porttisidonta:
bash

sudo docker port lums

Tarkista myös isännän kuuntelijat:
bash

sudo ss -lntp | grep -E ':443|:5050'

Odotettu arkkitehtuuri on:
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

Jos kontti on käynnissä, mutta HTTPS epäonnistuu, tutki kerroksia erikseen:

    Docker-kontti

    Paikallinen sovellusportti

    Nginx-konfiguraatio

    TLS

    Palomuuri/verkkopolku

Älä altista porttia 5050 julkisesti vianmäärityksen oikotienä.
6. Nginx palauttaa virheen

Tarkista palvelu:
bash

sudo systemctl status nginx \
    --no-pager

Validoi konfiguraatio:
bash

sudo nginx -t

Tarkista viimeisimmät Nginx-viestit:
bash

sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager

Varmista sitten, että LUMS-kontti on todella käynnissä:
bash

sudo docker ps

Käänteisvälityspalvelimen virhe ei automaattisesti tarkoita, että LUMS-sovellus itsessään on rikki.

Mahdollisia vikakohteita ovat:
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

Testaa kerrokset erikseen sen sijaan, että muuttaisit useita komponentteja kerralla.
7. HTTPS / TLS-ongelmat

Testaa ensin HTTPS-päätepiste:
bash

curl -I https://LUMS-SERVER/

Jos varmenteen validointi epäonnistuu, selvitä, onko ongelma:
text

Certificate
Certificate chain
Hostname
Trust store
Nginx configuration
Client CA configuration

Validoi Nginx:
bash

sudo nginx -t

Jos varmennetta tai TLS-konfiguraatiota on muutettu tarkoituksella, lataa Nginx uudelleen:
bash

sudo systemctl reload nginx

Testaa sitten uudelleen:
bash

curl -I https://LUMS-SERVER/

Yksityistä varmentajaa käyttävien asiakkaiden on luotettava asianmukaiseen CA-varmenteeseen.

Älä poista TLS-varmenteen validointia käytöstä pysyvänä kiertotienä.

Onnistunut yhteystesti, joka ohittaa varmenteen validoinnin, ei todista, että tuotannon TLS-konfiguraatio on oikein.
8. Agenttipalvelu epäonnistuu

Tarkista palvelu:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

Lue viimeisin loki:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Käynnistä palvelu uudelleen vasta edellisen tuloksen tarkastamisen jälkeen:
bash

sudo systemctl start \
    lums-agent.service

Tarkista sitten:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

ja:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Etsi:
text

Configuration errors
Missing environment values
TLS errors
Authentication failures
API errors
Python exceptions
Package-manager errors

Älä asenna agenttia uudelleen vain siksi, että yksi suoritus epäonnistui.
9. Agentti raportoi LUMS_TOKEN puuttuvan

Agentti vastaanottaa normaalisti tuotantokonfiguraationsa systemd-palveluympäristönsä kautta.

Jos agentti käynnistetään manuaalisesti komentotulkista, systemd:n EnvironmentFile ei lataudu automaattisesti kyseiseen komentotulkkiin.

Siksi:
bash

sudo /opt/lums-agent/agent.py --version

voi käyttäytyä eri tavalla kuin:
bash

sudo systemctl start \
    lums-agent.service

kun tunniste toimitetaan yksinomaan systemd-konfiguraation kautta.

Tutkiessasi todentamisongelmia testaa ensin varsinainen palvelu:
bash

sudo systemctl start \
    lums-agent.service

Tarkista sitten:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Älä kopioi tuotantotunnisteita komentotulkkikomentoihin tarpeettomasti.

Älä koskaan tulosta tuotantotunnistetta diagnostiseen lokiin.
10. Agentti ei tavoita palvelinta

Aloita verkkoyhteydestä:
bash

ping LUMS-SERVER

Testaa sitten HTTPS:
bash

curl -I https://LUMS-SERVER/

Jos HTTPS toimii, mutta agentti epäonnistuu edelleen, tutki:
text

Client configuration
Client token
TLS trust
API response
Client identity
Agent version

Tarkista agentti:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Tarkista samanaikaisesti palvelin:
bash

sudo docker logs \
    --tail 200 \
    lums

Tämä auttaa selvittämään, saavuttaako pyyntö LUMSin lainkaan.

Jos asiakas näkee yhteysvirheen ja palvelin ei näytä vastaavaa pyyntöä, tutki verkko- tai TLS-polkua ennen sovelluksen konfiguraation muuttamista.
11. Jatka vianmääritystä

Jos perus palvelin-, Docker-, Nginx-, TLS- ja agenttikerrokset toimivat, jatka:
text

Client Authentication
Token Rotation
Update Detection
Execution Watcher
Idle Detection
Pending Jobs

Seuraava osio jatkuu asiakastodennuksella ja tunnisteisiin liittyvillä ongelmilla.
12. Asiakastodennus

LUMS käyttää asiakaskohtaista todennusta agentin viestintään.

Kun asiakas rekisteröidään, asiakas vastaanottaa tunnistetiedot, joita käytetään todennettuun viestintään LUMS-palvelimen kanssa.

Todennusvirheet tulee tutkia paljastamatta asiakastunnistetta.
12.1 LUMS ei hyväksy asiakasta

Jos agentti raportoi todennusvirheen, tarkista ensin agentin loki:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Tarkista sitten LUMS-kontin lokit:
bash

sudo docker logs \
    --tail 100 \
    lums

Etsi:
text

401 Unauthorized
403 Forbidden
Invalid client token
Unknown client
Authentication failure

401-vastaus yleensä osoittaa todennusongelmaa.

403-vastaus voi osoittaa, että todennus onnistui, mutta pyydetty toiminto ei ole sallittu.

Älä heti vaihda tunnistetta.

Selvitä ensin, onko ongelma:
text

Wrong token
Wrong client ID
Disabled client
Incorrect server URL
TLS problem
Malformed request
Server-side authentication failure

12.2 Asiakas on olemassa, mutta todennus epäonnistuu

Varmista, että asiakas on edelleen olemassa LUMS-hallintakäyttöliittymässä.

Älä muokkaa asiakastietuetta vain siksi, että agenttipyyntö epäonnistui.

Jos asiakas on olemassa, vertaa konfiguroitua asiakasidentiteettiä agentin käyttämään identiteettiin.

Itse tuotantotunnistetta ei saa koskaan tulostaa diagnostiseen tulosteeseen.

Käytä vianmäärityksessä konfiguraation metatietoja ja palvelun tilaa tunnistetietojen paljastamisen sijaan.
13. Asiakastunnisteen vaihto

Asiakastunnisteen vaihto mitätöi edellisen tunnisteen ja korvaa sen uudella tunnistetiedolla.

Jos tunniste on vaihdettu tarkoituksella, asianomaisen agentin on vastaanotettava uusi tunniste ennen kuin se voi todentaa itsensä uudelleen.

Odotettu järjestys on:
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

Jos agentti jatkaa vanhan tunnisteen käyttöä, todennus epäonnistuu.
13.1 Tunnisteen vaihdon jälkeen

Tarkista agenttipalvelu:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

Suorita sitten agentti systemdin kautta:
bash

sudo systemctl start \
    lums-agent.service

Tarkista tulos:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Jos todennus epäonnistuu edelleen, tarkista palvelimen lokit:
bash

sudo docker logs \
    --tail 100 \
    lums

Älä vaihda tunnistetta toistuvasti.

Toistuva vaihto voi vaikeuttaa sen selvittämistä, mikä tunniste on tällä hetkellä käytössä asiakkaalla.
14. Asiakas on poistettu käytöstä

Käytöstä poistettua asiakasta ei saa kohdella aktiivisena hallinnoituna asiakkaana.

Jos käytöstä poistettuun asiakkaaseen kuuluva agentti yrittää kommunikoida, tarkista palvelinpuolen todennustulos.

Tarkista:
text

Client identity
Client enabled state
Authentication result
Agent configuration

Älä ota asiakasta uudelleen käyttöön vain saadaksesi virheen katoamaan.

Selvitä ensin, miksi asiakas poistettiin käytöstä.
15. Päivitysten tunnistus

Päivitysten tunnistus koostuu useista itsenäisistä vaiheista.

Agentti:

    suorittaa paketinhallinnan kyselyn

    jäsentää tuloksen

    lähettää tuloksen LUMSille

    LUMSin on validoitava tulos

    LUMSin on tallennettava tulos

    käyttöliittymän on näytettävä nykyinen tila

Virhe missä tahansa vaiheessa voi saada päivitystiedot näyttämään virheellisiltä.

Perusvirta on:
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

15.1 Päivityksiä ei näytetä

Selvitä ensin, raportoiko asiakas todella onnistuneesti.

Tarkista:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager

Tarkista sitten palvelin:
bash

sudo docker logs \
    --tail 100 \
    lums

Jos agentti valmistui onnistuneesti, mutta päivityksiä ei näytetä, tutki API- ja tietokannan tilaa ennen paketinhallinnan muuttamista.
15.2 Debian / Ubuntu -päivitysten tunnistus

Debian-paketinhallinta käyttää APT:ta.

Tutkiessasi APT:hen liittyviä ongelmia varmista ensin, että APT itse toimii:
bash

sudo apt update

Älä automaattisesti suorita pakettipäivityksiä vianmäärityksen aikana.

Tämän testin tarkoitus on selvittää, voidaanko varastometatiedot päivittää onnistuneesti.

Jos APT raportoi varasto-, DNS-, TLS-, allekirjoitus- tai lukkovirheitä, ratkaise taustalla oleva APT-ongelma ennen LUMSin tutkimista.
15.3 Arch Linux -päivitysten tunnistus

Arch Linux käyttää pacman-työkalua.

Tarkista varastometatiedot:
bash

sudo pacman -Sy

Käytä tätä vain, kun varastometatietojen päivitys on todella tarpeen diagnostiikkaa varten.

Älä yhdistä tarpeetonta järjestelmäpäivitystä diagnostiseen testiin.

Paketteihin liittyvissä virheissä tarkista pacman-tuloste ennen konfiguraation muuttamista.
16. Saatavilla olevat päivitykset eroavat LUMSin ja asiakkaan välillä

Päivitystiedot voivat muuttua kahden havainnon välillä.

Esimerkiksi:
text

Client reports updates
        ↓
Repository metadata changes
        ↓
Package is upgraded manually
        ↓
LUMS displays older information

Siksi ota aina huomioon viimeisimmän onnistuneen asiakasraportin aikaleima.

Ero ei automaattisesti osoita tietokantaongelmaa.

Tarkista:
text

Last Agent execution
Last successful report
Package-manager state
Repository metadata
Displayed update state

17. Paketinhallinta

LUMS-paketinhallinta on erillään asiakassivulla näkyvästä asennettujen pakettien suodattimesta.

Paketinhallinnan työnkulku on:
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

Paketin asentaminen, poistaminen tai päivittäminen käyttää normaalia LUMS-työmekanismia.

Odotettu suorituspolku on:
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

17.1 Pakettihaku ei palauta tuloksia

Varmista ensin, että agentti on toiminnassa:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

Tarkista sitten agentin loki:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Debian-pohjaisilla asiakkailla varmista APT-metatiedot.

Arch-pohjaisilla asiakkailla varmista pacman-varaston metatiedot.

Älä oleta, että tyhjä hakutulos tarkoittaa, että LUMS-tietokanta on tyhjä.

Haku suoritetaan asiakkaan paketinhallinnan kautta.
17.2 Pakettihaku toimii, mutta asennus epäonnistuu

Onnistunut haku todistaa vain, että paketinhallinta löysi paketin.

Se ei todista, että asennus onnistuu.

Mahdollisia syitä ovat:
text

Dependency conflicts
Repository changes
Package no longer available
Insufficient privileges
Package-manager lock
Disk-space problems
Network problems
Package-manager errors

Tarkista vastaava päivitystyö.

Agenttilokin pitäisi sisältää paketinhallinnan tulos.
18. Paketinasennustyöt

Paketinasennus käyttää normaalia päivitystyöinfrastruktuuria.

Asiaankuuluva toiminto on:
text

INSTALL_PACKAGE

Asennuksen vianmäärityksessä:

    Tarkista työn tila LUMSissa.

    Tarkista agentin suoritus.

    Tarkista paketinhallinnan tuloste.

    Tarkista LUMSille raportoitu lopullinen tulos.

Älä muokkaa työn tilaa manuaalisesti SQLitessä.

Odotettu elinkaari on:
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

Epäonnistuneen paketinasennuksen on pysyttävä jäljitettävissä normaaleilla työ- ja valvontamekanismeilla.
19. Paketinpoistotyöt

Paketin poisto noudattaa samaa työn elinkaarta.

Toiminto on:
text

REMOVE_PACKAGE

Kun poisto epäonnistuu, tarkista:
text

Update job
Agent journal
Package-manager output
Final job result

Älä poista tietokantatietueita manuaalisesti piilottaaksesi epäonnistuneen pakettitoiminnon.

Epäonnistunut työ on hyödyllistä diagnostista tietoa.
20. Pakettipäivitystyöt

Pakettikohtainen päivitys käyttää:
text

UPDATE_PACKAGE

Paketin on oltava LUMSin tiedossa saatavilla olevana päivityksenä ennen työn luomista.

Jos käyttöliittymä ei tarjoa odotettua pakettipäivitystä:

    päivitä päivitystiedot

    varmista paketinhallinnan tila

    varmista saatavilla olevien päivitysten tulos

    tarkista palvelimen lokit, jos tila on epäjohdonmukainen

Älä syötä päivitystietueita manuaalisesti SQLiteen.
21. Järjestelmäpäivitystyöt

Täydellinen järjestelmäpäivitys käyttää:
text

UPDATE_SYSTEM

Tämä eroaa:
text

UPDATE_PACKAGE

Järjestelmäpäivitys voi vaikuttaa useisiin paketteihin ja voi vaatia uudelleenkäynnistyksen käyttöjärjestelmästä ja tuloksena olevasta pakettitilasta riippuen.

Järjestelmäpäivityksen vianmäärityksessä selvitä, tapahtuiko virhe:
text

Update preparation
Package-manager execution
Result collection
Reboot detection
Post-reboot reporting

22. Paketinhallinnan lukot

Paketinhallinnat voivat kieltäytyä toiminnosta, kun toinen paketinhallintaprosessi on jo käynnissä.

Tyypillisiä esimerkkejä:
text

APT is already running
dpkg is locked
pacman is locked

Tunnista ensin lukon pitävä prosessi.

Älä poista lukkotiedostoja sokeasti.

Lukkotiedosto voi osoittaa, että toinen paketinhallintaprosessi on laillisesti aktiivinen.

Sen poistaminen pakettitoiminnon aikana voi vahingoittaa paketinhallinnan tilaa.

Oikea vianmääritysjärjestys on:
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

23. Paketinhallinnan virhe vs. LUMS-virhe

Erota aina paketinhallinnan virhe ja LUMS-virhe.

Esimerkiksi:
text

APT fails
    ↓
Agent reports APT failure
    ↓
LUMS stores FAILED result

Tässä tapauksessa LUMS voi toimia oikein, vaikka työ epäonnistui.

Toisaalta:
text

APT succeeds
    ↓
Agent cannot report result
    ↓
LUMS never receives SUCCESS

Tässä pakettitoiminto on voinut onnistua, kun taas LUMSin raportointipolku epäonnistui.

Paketinhallinnan tulos ja LUMS-työn tulos on siksi tutkittava erikseen.
24. Hyödyllinen diagnostinen erottelu

Kun pakettityö epäonnistuu, luokittele virhe ensin:
text

A. Package-manager failure
B. Agent execution failure
C. Agent reporting failure
D. Server/API failure
E. Database persistence failure
F. UI display problem

Tämä luokittelu estää liittymättömien komponenttien muuttamisen.

Paketinhallinnan virhe ei automaattisesti saisi johtaa Docker-kuvan uudelleenrakentamiseen.

Käyttöliittymän näyttöongelma ei automaattisesti saisi johtaa tietokannan poistamiseen.

Todennusvirhe ei automaattisesti saisi johtaa agentin uudelleenasentamiseen.
25. Seuraava vianmääritysalue

Jos asiakastodennus, päivitysten tunnistus ja paketinhallinta toimivat, seuraava diagnostinen alue on itse suorituksen elinkaari:
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

Seuraava osio kattaa suorituksen valvojan, lepotilan tunnistuksen, työn tilan, palautuksen ja uudelleenkäynnistyksen käsittelyn.
26. Päivitystyön suoritus

LUMS-päivitystyöt suoritetaan asynkronisesti agentin ja suorituksen valvojan kautta.

Normaali suorituspolku on:
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

Käyttöliittymässä näkyvä työ ei välttämättä ole jo suorituksessa.

Selvitä aina ensin työn nykyinen tila.
26.1 Työ on jumittunut PENDING-tilaan

Jos työ pysyy PENDING-tilassa, tarkista suorituksen valvoja ennen agentin tutkimista.

Tarkista valvoja:
bash

sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager

Tarkista viimeisimmät valvojan tulosteet:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Tarkista sitten agentti:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

Odottava työ yleensä osoittaa, että suoritusvaihe ei ole vielä alkanut.

Mahdollisia syitä ovat:
text

Watcher is not running
Watcher timer is not running
Client is offline
Client is not idle
Client has not reported recently
Job is not eligible for execution yet

Älä muuta työn tilaa manuaalisesti SQLitessä.
27. Työ on jumittunut RUNNING-tilaan

RUNNING-työ osoittaa, että suoritus on alkanut.

Selvitä ensin, suorittaako agentti todella työtä.

Tarkista:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Tarkista sitten valvoja:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Käynnissä oleva työ voi kestää jonkin aikaa riippuen:
text

Package count
Repository speed
Network latency
Package-manager operations
System load
Reboot requirements

Älä keskeytä aktiivista pakettitoimintoa vain siksi, että käyttöliittymä ei ole vielä päivittynyt.

Selvitä ensin, onko taustalla oleva prosessi edelleen aktiivinen.
28. Työ on FAILED

Epäonnistunut työ ei välttämättä osoita LUMS-palvelimen virhettä.

Selvitä, mikä kerros tuotti virheen.

Tarkista:
text

Job state
Agent execution result
Package-manager result
Server logs
Agent logs

Pääluokat ovat:
text

Package-manager failure
Agent execution failure
Agent reporting failure
Server/API failure
Authentication failure
Recovery failure

Alkuperäinen virhe on säilytettävä aina kun mahdollista.

Älä korvaa epäonnistunutta työtä manuaalisesti luodulla onnistuneella tietueella.
29. Työ on SUCCESS, mutta paketti ei muuttunut

Onnistunut LUMS-työ tarkoittaa, että pyydetty toiminto valmistui agentin tuloksen mukaisesti.

Jos odotettu paketin tila ei vastaa työn tulosta, varmista asiakas suoraan.

Debian-pohjaisilla järjestelmillä:
bash

dpkg-query -W \
    -f='${Package} ${Version}\n' \
    PACKAGE_NAME

Arch Linuxilla:
bash

pacman -Q \
    PACKAGE_NAME

Korvaa PACKAGE_NAME tutkittavalla paketilla.

Vertaa sitten paikallista paketin tilaa LUMS-tulokseen.

Mahdollisia selityksiä ovat:
text

Package was changed after the job
Package name refers to a virtual/provided package
Package-manager output was interpreted differently than expected
The job result was generated before another local change

Älä muokkaa LUMS-tietokantaa ennen kuin ero on tunnistettu.
30. Suorituksen valvoja

Suorituksen valvoja vastaa sellaisten töiden löytämisestä, jotka ovat kelvollisia suoritettaviksi.

Valvojaa on kohdeltava itsenäisenä komponenttina.

Tarkista sen palvelu:
bash

sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager

Tarkista sen ajastin:
bash

sudo systemctl list-timers \
    --all | grep lums

Tarkista sen loki:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Jos agentti toimii, mutta työt eivät koskaan käynnisty, valvoja on yksi ensimmäisistä tutkittavista komponenteista.
31. Valvoja suoritetaan, mutta ei suorita töitä

Valvojan suoritus ei automaattisesti tarkoita, että työ käynnistetään.

Työn on täytettävä suoritusehdot.

Tarkista:
text

Client exists
Client is enabled
Client is reachable
Client has recent status
Client is eligible
Job is pending
Job is not already completed
Execution conditions are satisfied

Jos asiakas ei ole kelvollinen, valvoja voi oikein jättää työn odottamaan.

Tämä ei välttämättä ole virhe.
32. Lepotilan tunnistus

LUMS voi käyttää asiakkaan lepotilatietoja päättäessään, suoritetaanko työ.

Tarkoitus on välttää ylläpitotoimintojen aloittamista, kun asiakasta käytetään aktiivisesti.

Lepotilapäätöstä on siksi pidettävä ajoitusehtona, ei suoritusvirheenä.

Asiakas voi raportoida onnistuneesti, vaikka sitä pidettäisiin ei-lepotilassa.

Vianmääritysjärjestys on:
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

32.1 Asiakas raportoi, mutta sitä ei pidetä lepotilassa

Tarkista agentin loki:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Etsi raportoituja lepotilatietoja.

Tarkista sitten valvoja:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Tärkeä ero on:
text

Agent communication successful

vastaan:
text

Client eligible for maintenance execution

Nämä ovat erillisiä tiloja.
33. Lepotilan tunnistus ei ole käytettävissä

Jotkin järjestelmät eivät välttämättä tarjoa kaikkia lepotilatietoja.

Käyttämättömissä olevaa lepotilamekanismia ei pidä automaattisesti tulkita rikkinäiseksi agentiksi.

Selvitä ensin raportoitu ominaisuus.

Asiaankuuluvat käsitteet ovat:
text

Idle supported
Idle source
Idle state
Idle duration

Jos alusta ei voi tarjota odotettuja lepotilatietoja, tutki agentin alustakohtaista toteutusta sen sijaan, että muokkaisit palvelimen tietokantaa.
34. Päivitystyön palautus

LUMS käyttää tarkistuspisteitä ja palautusta estääkseen keskeytyneiden päivitystöiden käsittelemisen valmiina.

Työ voi keskeytyä seuraavista syistä:
text

Agent restart
Client reboot
Network interruption
Package-manager interruption
Server restart
Watcher restart
System failure

Palautuksen on erotettava jo suoritettu työ ja työ, joka on vielä suoritettava.

Periaate on:
text

Completed work remains completed.
Incomplete work remains recoverable.

35. Keskeytynyt työ

Jos työ keskeytyi, tarkista ensin sen tila.

Tarkista sitten agentti:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Tarkista valvoja:
bash

sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager

Älä merkitse työtä manuaalisesti onnistuneeksi.

Palautusmekanismin on määritettävä, mitkä pakettikohteet on jo suoritettu.
36. Palautus toistaa pakettitoiminnon

Kun palautus käynnistetään, jo onnistuneita pakettikohteita ei pitäisi suorittaa uudelleen tarpeettomasti.

Palautusmalli perustuu kohdetason tilaan.

Käsitteellisesti:
text

Job
 ├── Package A → SUCCESS
 ├── Package B → SUCCESS
 ├── Package C → FAILED
 └── Package D → PENDING

Palautuksen pitäisi säilyttää onnistuneet kohteet ja jatkaa jäljellä olevaa työtä.

Jos tämä käyttäytyminen näyttää virheelliseltä, tarkista työn ja pakettikohteiden historia ennen tietokannan muuttamista.
37. Asiakas käynnistyy uudelleen päivityksen aikana

Uudelleenkäynnistys voi keskeyttää agenttiprosessin.

Odotettu palautuspolku on:
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

Uudelleenkäynnistys ei siis automaattisesti tarkoita, että työ epäonnistui pysyvästi.

Tarkista agenttipalvelu, kun asiakas palaa:
bash

sudo systemctl status \
    lums-agent.service \
    --no-pager

Tarkista sitten viimeisimmät suoritukset:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

38. Uudelleenkäynnistyksen tunnistus

Uudelleenkäynnistyksen tunnistusta käytetään selvittämään, tapahtuiko järjestelmän uudelleenkäynnistys osana päivitystoimintoa.

Tämä on erityisen tärkeää, kun päivitys muuttaa paketteja, jotka vaativat uudelleenkäynnistyksen.

Arch Linuxilla uudelleenkäynnistyksen tunnistusta ei saa sekoittaa paketinhallinnan poistumistilaan.

Pakettitoiminto voi onnistua, vaikka järjestelmä vaatii edelleen uudelleenkäynnistyksen.

Uudelleenkäynnistyksen käsittelyn vianmäärityksessä vertaa:
text

Package operation result
Reboot requirement
Actual reboot state
Post-reboot Agent report
Final LUMS job state

39. Työn tulosta ei raportoitu

Jos pakettitoiminto näyttää valmistuneen, mutta LUMS ei näytä lopullista tulosta, tutki raportointipolkua.

Tarkista agentti:
bash

sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager

Tarkista sitten palvelin:
bash

sudo docker logs \
    --tail 200 \
    lums

Jos agentti raportoi virheen, vaikka pakettitoiminto itse onnistui, luokittele ongelma raportointivirheeksi paketinhallintavirheen sijaan.
40. Palvelimen uudelleenkäynnistys työn suorituksen aikana

Palvelimen uudelleenkäynnistystä ei saa automaattisesti pitää todisteena siitä, että päivitystoiminto epäonnistui.

Työn tila on arvioitava, kun palvelin on jälleen saatavilla.

Tarkista:
text

Container state
Database availability
Job state
Client state
Agent report
Watcher state

Palautusmekanismi vastaa siitä, voiko keskeytynyt työ jatkua turvallisesti.

Älä kirjoita työn tiloja manuaalisesti uudelleen palvelimen uudelleenkäynnistyksen jälkeen.
41. Tietokanta on saatavilla, mutta työn tila näyttää väärältä

Jos SQLite on tavoitettavissa, mutta työn tila näyttää epäjohdonmukaiselta, tarkista sovellus- ja valvontalokit ennen tietokannan muuttamista.

Hyödyllisiä tietoja ovat:
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

Tietokanta on sovelluksen tietovarasto, ei manuaalinen korjauskäyttöliittymä.

Suorat muutokset voivat ohittaa validoinnin, valtuutuksen, valvonnan ja palautuslogiikan.
42. Manuaaliset työn tilan muutokset

Manuaalisia SQL-muutoksia päivitystyön tilaan ei tule käyttää normaaliin vianmääritykseen.

Vältä toimintoja, kuten:
sql

UPDATE update_jobs ...

tai:
sql

DELETE FROM update_jobs ...

ellet kontrolloitu tietokannan palautusmenettely nimenomaisesti vaadi niitä.

Jos tietokantatason korjaus on todella tarpeen, säilytä varmuuskopio ja dokumentoi tarkka muutos ennen sen soveltamista.

Normaalit toimintaongelmat tulee ratkaista sovelluksen ja agentin mekanismien kautta.
43. Valvojan ja agentin diagnostinen matriisi

Käytä seuraavaa matriisia tunnistaaksesi todennäköisimmän kerroksen:
Oire	Ensimmäinen tarkistettava komponentti
Asiakas ei voi todentaa	Agent + LUMS API
Asiakas raportoi onnistuneesti, mutta työ pysyy odottavana	Suorituksen valvoja
Työ alkaa suorituksen, mutta ei valmistu	Agent + paketinhallinta
Pakettitoiminto epäonnistuu	Paketinhallinta
Pakettitoiminto onnistuu, mutta tulos puuttuu	Agentin raportointi
Asiakas käynnistyi uudelleen päivityksen aikana	Agent + palautus
Työ pysyy epäjohdonmukaisena uudelleenkäynnistyksen jälkeen	Palautus + tietokannan tila
Työtä ei koskaan löydetä	Valvoja + ajastin
Asiakas ei ole kelvollinen	Lepotila / asiakkaan tila
Käyttöliittymä näyttää vanhentuneen tilan	API + viimeisin asiakasraportti

Tämä matriisi on lähtökohta, ei korvike varsinaisten lokien ja työn tilan tarkistamiselle.
44. Seuraava vianmääritysalue

Kun työn suoritus on varmennettu, seuraavat alueet ovat:
text

SQLite and database state
RBAC and user management
Authentication sessions
Application and audit logging
Container security
Tests and CI

Näitä alueita tulee tutkia erillään pakettien suorituksesta.
45. SQLite- ja tietokantavianmääritys

LUMS käyttää SQLitea sovelluksen tietokantana.

Tuotantotietokanta tallennetaan pysyvään Docker-taltioon:
text

/var/lib/lums/lums.db

Tietokanta on sovelluksen hallinnoima, eikä sitä normaalisti saa muokata manuaalisesti.

Tutkiessasi tietokantaan liittyviä ongelmia selvitä ensin, onko ongelma:
text

Database availability
Database locking
Application configuration
Data consistency
Migration state
Application logic

46. Tietokanta ei ole saatavilla

Jos LUMS raportoi tietokantavirheen, tarkista ensin, onko kontti käynnissä:
bash

sudo docker ps

Tarkista sitten sovelluslokit:
bash

sudo docker logs \
    --tail 200 \
    lums

Älä heti poista Docker-taltiota.

Pysyvä taltio sisältää tuotannon sovellustiedot.

Sen poistaminen voi pysyvästi poistaa:
text

Users
Clients
Client configuration
Update jobs
Audit data
Application state

47. SQLite-tietokannan lukitus

SQLite-lukitusongelmat tulee tutkia sovelluslokien kautta.

Tarkista:
bash

sudo docker logs \
    --tail 200 \
    lums

Tuotantosovellus käyttää:
text

journal_mode = wal
busy_timeout = 5000
synchronous = 2

Sovellus ottaa myös käyttöön SQLite-viiteavainten valvonnan tietokantayhteyksilleen.

Tietokantalukko ei automaattisesti tarkoita, että tietokanta on korruptoitunut.

Mahdollisia syitä ovat:
text

Concurrent writes
Long-running transaction
Application process still using the database
Unexpected process termination
Filesystem problem

Älä poista SQLite-journal-tiedostoja manuaalisesti.
48. SQLite-viiteavaimet

LUMS ottaa eksplisiittisesti käyttöön SQLite-viiteavainten valvonnan sovellustasolla.

Tämä tarkoittaa, että tietokantatietueiden väliset suhteet validoidaan SQLiten toimesta, kun sovellusyhteys muodostetaan.

Jos viiteavainvirhe ilmenee, tarkista ensin sovelluslokit.

Älä poista viiteavainten valvontaa käytöstä saadaksesi toiminnon onnistumaan.

Viiteavainvirhe voi osoittaa sovelluslogiikan tai datan eheyden ongelmaa.
49. SQLite-tietokannan eheys

Jos tietokannan korruptiota epäillään, lopeta tarpeettomien muutosten tekeminen ensin.

Säilytä nykyinen tila ja tarkista sovelluslokit.

Kontrolloitu eheystarkistus voidaan suorittaa tietokannan kopiolle.

Älä suorita tuhoavia korjaustoimenpiteitä suoraan tuotantotietokantaa vastaan, ellei dokumentoitu palautusmenettely vaadi sitä.

Yleinen periaate on:
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

Älä koskaan aloita:
text

Delete database
Recreate database
Recreate Docker volume

50. Tietokantamigraatiot

LUMS käyttää sovellusmigraatioita tietokantaskeeman muutosten tuomiseen.

Kun migraatio-ongelma ilmenee, tarkista kontin lokit:
bash

sudo docker logs \
    --tail 200 \
    lums

Etsi:
text

Migration failure
SQL error
Duplicate column
Missing table
Constraint error
Migration already applied

Älä muokkaa migraatiotietueita manuaalisesti, ellei migraatiojärjestelmä nimenomaisesti vaadi kontrolloitua palautusmenettelyä.

Jo sovellettua migraatiota ei normaalisti tule suorittaa manuaalisesti uudelleen.
51. Tietokantataltio

LUMS-tietokanta tallennetaan pysyvään Docker-taltioon:
text

lums-data

Tarkista taltio:
bash

sudo docker volume inspect \
    lums-data

Taltion on pysyttävä pysyvänä normaalin kontin uudelleenluonnin yli.

Itse sovelluskontti on kertakäyttöinen.

Sovellustiedot eivät ole.

Siksi:
text

Container
    ≠
Persistent database

Kontin uudelleenluontia ei saa sekoittaa datataltion uudelleenluontiin.
52. Tietokannan levytila

SQLite vaatii käytettävissä olevaa tiedostojärjestelmätilaa normaaliin toimintaan.

Tarkista isännän tiedostojärjestelmä:
bash

df -h

Tarkista myös inode-saatavuus:
bash

df -i

Vähäinen levytila voi tuottaa tietokantavirheitä, jotka aluksi näyttävät sovellusongelmilta.

Jos tietokanta yhtäkkiä muuttuu vain luku -tilaan tai kirjoitukset alkavat epäonnistua, varmista tiedostojärjestelmän kapasiteetti ennen SQLite-konfiguraation muuttamista.
53. RBAC-vianmääritys

LUMS käyttää roolipohjaista käyttöoikeushallintaa.

Nykyiset roolit ovat:
text

Administrator
Operator
Viewer

Oikeudet ovat tarkoituksella erilaisia.
53.1 Administrator

Ylläpitäjät voivat:
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

Vain ylläpitäjälle tarkoitetut toiminnot sisältävät käyttäjähallinnan ja roolien hallinnan.
53.2 Operator

Operaattorit voivat:
text

View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance

Operaattorit eivät voi:
text

Manage users
Manage roles
Create or disable clients
Rotate client tokens

53.3 Viewer

Viewereillä on tarkoituksella rajoitettu pääsy.

Viewer voi:
text

View clients
View installed software

Seuraava toiminnallisuus on piilotettu Viewer-käyttöliittymästä ja estetty palvelinpuolella:
text

Available Updates
Update Jobs
Update History
Package Management
System Maintenance

Tämä on tarkoituksellinen turvakontrolli.

Jos Viewer voi käyttää jotakin näistä toiminnoista, käsittele ongelmaa RBAC-ongelmana eikä pelkästään käyttöliittymäongelmana.
54. Viewer näkee liikaa

Jos Viewer näkee toiminnallisuutta, joka ei saisi olla saatavilla, tarkista molemmat kerrokset:
text

Browser UI
    +
Server-side authorization

Elementin piilottaminen JavaScriptissä tai HTML:ssä ei ole riittävä turvallisuus.

API:n on myös hylättävä luvattomat toiminnot.

Tutkiessasi:

    Selvitä todennetun käyttäjän rooli.

    Tunnista asianomainen päätepiste.

    Tarkista palvelimen vastaus.

    Tarkista sovelluslokit tarvittaessa.

    Varmista asiaankuuluva RBAC-testi.

Älä ratkaise valtuutusongelmaa vain piilottamalla käyttöliittymäelementtiä.
55. Viewer ei näe odotettuja tietoja

Viewerin pitäisi silti päästä käsiksi tietoihin, jotka nykyinen RBAC-malli nimenomaisesti sallii.

Jos sallitut asiakastiedot puuttuvat:
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

Älä myönnä lisäoikeuksia vain siksi, että sivu näyttää tällä hetkellä puutteelliselta.

Selvitä ensin, onko puuttuva tieto tarkoituksella rajoitettua.
56. Operaattori ei voi suorittaa toimintoa

Jos operaattori saa 403 Forbidden -vastauksen, selvitä ensin, onko pyydetty toiminto vain ylläpitäjälle tarkoitettu.

Operaattorin pääsy ei sisällä:
text

User management
Role administration
Client creation/deactivation
Client token rotation

Jos toiminto pitäisi sallia operaattoreille, tarkista päätepisteen valtuutusdekiraattori ja vastaavat RBAC-testit.

Älä tilapäisesti ylennä käyttäjää ylläpitäjäksi diagnostisena oikotienä.
57. Ylläpitäjä ei voi suorittaa toimintoa

Ylläpitäjällä pitäisi olla pääsy kaikkiin tällä hetkellä tuettuihin hallinnollisiin toimintoihin.

Jos ylläpitäjä saa valtuutusvirheen:
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

Tilaa muuttaville toiminnoille pelkkä kelvollinen istunto ei välttämättä riitä.

CSRF-suojaus on myös täytettävä tarvittaessa.
58. Käyttäjähallinta

Käyttäjähallinta on rajoitettu ylläpitäjille.

Käyttäjähallinnan työnkulku on:
text

Administrator
    │
    ▼
User Management
    │
    ├── Create user
    ├── Assign role
    └── Enable / disable user

Kun käyttäjää ei voi luoda, tarkista:
text

Current role
Username validation
Role validation
Duplicate username
Password validation
CSRF protection
Application logs

Älä luo käyttäjiä suoraan SQLiteen.

Suora tietokantalisäys ohittaa salasanatiivistyksen, validoinnin, valtuutuksen ja valvontalokituksen.
59. Käyttäjän luominen epäonnistuu

Jos käyttäjän luominen epäonnistuu, tarkista selaimen vastaus ja palvelimen lokit.

API:n pitäisi validoida:
text

Username
Role
Password requirements
Duplicate account
Authenticated administrator
CSRF token

Jos pyyntö hylätään, selvitä, mikä validointisääntö laukesi.

Älä heikennä validointia vain saadaksesi yhden tilinluontipyynnön onnistumaan.
60. Salasanaongelmat

LUMS tallentaa käyttäjien salasanat salasanatiivistysmekanismilla selkokielisten salasanojen sijaan.

Jos käyttäjä ei voi kirjautua sisään:
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

Älä koskaan tallenna tai kirjaa selkokielisiä salasanoja.

Älä kopioi salasanoja diagnostisiin komentoihin tai lokitiedostoihin.
61. Käytöstä poistettu käyttäjätili

Käytöstä poistettua tiliä ei saa kohdella aktiivisena kirjautumistilinä.

Jos käytöstä poistettu käyttäjä voi silti todentaa itsensä, tutki:
text

Current account state
Authentication lookup
Session state
Session revocation
Browser session
Server-side authorization

Älä yksinkertaisesti poista tiliä.

Tilin säilyttäminen voi olla tärkeää valvontahistorian kannalta.
62. Istunto-ongelmat

LUMS käyttää palvelinpuolen istunnonhallintaa.

Kun käyttäjällä näyttää olevan vanhentunut tai odottamaton pääsy, kirjaudu ensin ulos ja muodosta uusi istunto.

Jos ongelma jatkuu, tutki:
text

Account state
Role
Session state
Session revocation
Cookie configuration
CSRF protection

Älä poista istunnon turvakontrolleja käytöstä kirjautumisongelman ohittamiseksi.
63. Istunnon mitätöinti

Istunnon mitätöinti on merkityksellinen, kun:
text

A password changes
A user is disabled
A role changes
A session must be invalidated
A security event requires forced logout

Jos käyttäjällä näyttää olevan pääsy tilimuutoksen jälkeen, selvitä, mitätöitiinkö olemassa oleva istunto oikein.

Testaa tuoreella selainistunnolla vasta vahvistettuasi tilin tilan.

Älä oleta, että pelkkä selaimen evästeiden poistaminen todistaa, että palvelinpuolen istunnon mitätöinti toimii.
64. Kirjautumisen nopeusrajoitus

LUMS soveltaa kirjautumisen nopeusrajoitusta toistuviin epäonnistuneisiin todennusyrityksiin.

Nykyinen käyttäytyminen käyttää kasvavia lukitusvälejä:
text

5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds

Epäonnistumistila tallennetaan SQLiteen.

Jos kirjautumisyritykset estetään odottamatta, tarkista todennuksen tila ennen tietokannan muuttamista.

Nopeusrajoitusvaste ei automaattisesti ole todennusvirhe.

Se voi osoittaa, että tili on saavuttanut määritetyn epäonnistuneiden yritysten kynnyksen.
65. Kirjautuminen toimii, mutta API palauttaa 403

Onnistunut kirjautuminen todistaa todennuksen, ei valtuutusta.

403 Forbidden -vastaus voi osoittaa:
text

Insufficient role
Missing CSRF protection
Disallowed operation
Disabled functionality

Tunnista tarkka päätepiste ennen minkään muuttamista.

Oikea vianmäärityskysymys on:
text

"Is this user authenticated?"

jota seuraa:
text

"Is this authenticated user authorized for this operation?"

Nämä ovat erillisiä turvatarkistuksia.
66. CSRF-virheet

Tilaa muuttavat selainpyynnöt on suojattu cross-site request forgery -hyökkäyksiltä.

Jos tilaa muuttava pyyntö epäonnistuu odottamatta:
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

Älä poista CSRF-suojausta käytöstä vianmäärityksen kiertotienä.

Epäonnistunut CSRF-tarkistus on turvakontrolli, joka toimii tarkoitetulla tavalla.
67. Selainkäyttöliittymä ja API ovat eri mieltä

Jos käyttöliittymä näyttää, että toiminto on saatavilla, mutta API hylkää sen:
text

Browser UI
   ↓
Displayed role/state
   ↓
API request
   ↓
Server-side authorization

Palvelinpuolen tulos on ratkaiseva.

Käyttöliittymä voi sisältää vanhentunutta tilaa seuraavien jälkeen:
text

Role changes
Session changes
Client changes
Page remains open for a long time

Lataa sivu uudelleen ja muodosta uusi istunto ennen kuin oletat, että palvelinpuolen valtuutus on virheellinen.
68. RBAC-diagnostinen matriisi
Oire	Ensimmäinen tarkistettava komponentti
Viewer näkee hallintakäyttöliittymän	Asiakassivun roolinkäsittely
Viewer-API-pyyntö onnistuu	Palvelinpuolen RBAC
Operaattori saa 403	Päätepisteen oikeusmalli
Ylläpitäjä saa 403	Istunto / CSRF / päätepisteen valtuutus
Käyttäjää ei voi luoda	Ylläpitäjän rooli + validointi
Käytöstä poistettu käyttäjä voi kirjautua	Tilin tila + istunnon käsittely
Kirjautuminen tilapäisesti estetty	Nopeusrajoitus
Tilaa muuttava pyyntö hylätty	CSRF / istunto
Käyttöliittymä ja API eri mieltä	Selaimen tila + palvelimen valtuutus

Palvelinpuolen valtuutustulos on aina tärkeämpi kuin se, onko käyttöliittymäelementti näkyvissä.
69. Seuraava vianmääritysalue

Seuraavat diagnostiset alueet ovat:
text

Application and audit logging
Container security
Filesystem permissions
Docker runtime configuration
Tests and CI
Diagnostic snapshots
Final recovery checklist

Näitä alueita tulee tutkia heikentämättä turvallisuusperustasoa.
70. Sovelluslokitus

LUMS käyttää sovelluslokitusta tarjotakseen diagnostista tietoa paljastamatta arkaluonteisia tunnistetietoja.

Kun tutkit sovellusongelmaa, aloita viimeisimmistä lokeista:
bash

sudo docker logs \
    --tail 200 \
    lums

Jatkuvaan seurantaan:
bash

sudo docker logs \
    -f \
    lums

Toista ongelma mahdollisuuksien mukaan lokeja seuraten.

Tämä helpottaa korrelointia:
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

71. Sovelluslokit sisältävät virheen

Tunnista ensin komponentti, joka tuotti viestin.

Tyypillisiä lähteitä ovat:
text

Flask application
Gunicorn
Database layer
Authentication
Authorization
Package management
Job execution
Client reporting

Älä oleta, että viimeisin lokiviesti on juurisyy.

Etsi tapahtumasarjan ensimmäinen asiaankuuluva virhe.

Korreloi mahdollisuuksien mukaan:
text

Timestamp
Client
Request
Job ID
Error
Result

72. Valvontalokitus

LUMS tallentaa turvallisuuteen liittyvät sovellustoiminnot valvontalokiin.

Valvontalokitus on hyödyllistä tutkittaessa:
text

User changes
Authentication events
Administrative actions
Client management
Token operations
Update-job creation
Security-relevant state changes

Valvontatapahtumaa tulee pitää todisteena sovellustapahtumasta, ei järjestelmälokien korvikkeena.

Käytä sovelluslokeja teknisiin suoritustietoihin ja valvontalokeja turvallisuuteen liittyviin sovellustoimintoihin.
73. Valvontatapahtuma puuttuu

Jos odotettu valvontatapahtuma puuttuu:

    Tunnista tarkka toiminto.

    Tunnista API-päätepiste.

    Varmista, että toiminto todella saavutti palvelimen.

    Tarkista sovelluslokit.

    Selvitä, hylättiinkö toiminto ennen kuin valvontatapahtuma olisi pitänyt luoda.

Älä syötä valvontatietueita manuaalisesti vain saadaksesi valvontajäljen näyttämään täydelliseltä.

Valvontatietueen tulee vastata todellista sovellustapahtumaa.
74. Valvontaloki ja sovellusloki eroavat

Kahdella lokitusjärjestelmällä on eri tarkoitukset.

Esimerkiksi:
text

Application log
→ technical execution information

Audit log
→ security-relevant application event

Paketinhallinnan virhe voi siis näkyä sovellus- tai agenttilokissa ilman, että se edustaa erillistä hallinnollista valvontatapahtumaa.

Toisaalta käyttäjähallintatoiminnon pitäisi tuottaa valvottava sovellustapahtuma, vaikka itse toiminto olisi teknisesti yksinkertainen.
75. Arkaluonteiset tiedot lokeissa

Älä koskaan tarkoituksella sijoita seuraavia diagnostiseen tulosteeseen:
text

Client tokens
Application secret keys
Passwords
Session secrets
Private keys
TLS private material

Jos diagnostinen komento paljastaisi jonkin näistä arvoista, käytä redaktoitua tai vain metatietoihin perustuvaa tarkistusta.

Kun jaat lokeja vianmääritystä varten, tarkista ne salaisuuksien varalta ennen kopioimista tukipyyntöihin, dokumentaatioon, GitHub-ongelmiin tai chattiin.
76. Docker-kontin turvallisuus

Tuotannon LUMS-kontti on tarkoituksella kovennettu.

Odotetut turvaominaisuudet ovat:
text

Non-root application user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges enabled
No privileged mode
Dedicated writable data volume
Read-only secret mount
Restricted temporary filesystems

Jos jokin näistä ominaisuuksista muuttuu odottamatta, käsittele sitä konfiguraation ajautumisena.

Älä heikennä konttia sovellusongelman ratkaisemiseksi, ellei turvavaikutusta ole nimenomaisesti arvioitu.
77. Varmista kontin ajonaikainen turvallisuus

Tarkista kontti:
bash

sudo docker inspect lums

Kohdennettuun ajonaikaiseen tarkistukseen:
bash

sudo docker inspect \
    --format='ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}' \
    lums

Odotetut arvot ovat:
text

ReadonlyRootfs=true
Privileged=false
CapDrop=[ALL]
SecurityOpt=[no-new-privileges:true]

Tarkka muotoilu voi vaihdella Docker-versioiden välillä.

Itse turvaominaisuudet ovat ratkaisevia.
78. Kontti toimii root-käyttäjänä

LUMS-sovelluksen pitäisi toimia omistautuneena ei-etuoikeutettuna sovelluskäyttäjänä.

Jos kontti odottamatta toimii root-käyttäjänä, tarkista ensin kuva ja ajonaikainen konfiguraatio:
bash

sudo docker inspect \
    --format='{{.Config.User}}' \
    lums

Tarkista sitten Dockerfile.

Älä ratkaise sovelluksen käyttöoikeusongelmia vaihtamalla tuotantokontti root-käyttäjäksi.

Jos hakemisto vaatii kirjoitusoikeuden, tunnista tarkka polku ja selvitä, pitäisikö sen olla pysyvää sovellusdataa vai väliaikaista dataa.
79. Vain luku -juuritiedostojärjestelmä

Tuotantokontti käyttää vain luku -juuritiedostojärjestelmää.

Tämä suojaa sovelluskuvaa tarpeettomalta ajonaikaiselta muutokselta.

Jos sovellus raportoi:
text

Read-only filesystem
Permission denied
Cannot create file
Cannot write temporary data

selvitä ensin, minne sovellus yrittää kirjoittaa.

Odotetut kirjoitettavat sijainnit ovat tarkoituksella rajoitettuja.

Pysyvät sovellustiedot kuuluvat:
text

/var/lib/lums

Väliaikainen ajonaikainen data voi käyttää määritettyjä väliaikaisia tiedostojärjestelmiä.

Älä poista --read-only-valintaa käytöstä vain siksi, että jokin sovelluksen polku on odottamatta kirjoitettavissa.
80. /tmp ei ole kirjoitettavissa

Jos sovellus vaatii väliaikaista tallennustilaa, varmista väliaikainen tiedostojärjestelmä:
bash

sudo docker inspect \
    --format='{{json .HostConfig.Tmpfs}}' \
    lums

Tuotantokontti tarjoaa rajoitetun /tmp-hakemiston.

Väliaikainen tiedostojärjestelmä on tarkoitettu vain tilapäiselle datalle.

Pysyviä tietoja ei saa tallentaa sinne.
81. Salaisuuden liitosongelmat

LUMS-sovelluksen salaisuus toimitetaan suojatun tiedostoliitoksen kautta.

Salaisuutta ei pitäisi upottaa suoraan kuvaan.

Jos LUMS raportoi puuttuvan salaisuuden, tarkista ensin ajonaikainen konfiguraatio:
bash

sudo docker inspect \
    lums

Tarkista, että salaisuuden liitos on olemassa ja vain luku -tilassa.

Älä tulosta salaisuuden sisältöä.

Hyödyllinen diagnostinen tarkistus on varmistaa, että tiedosto on olemassa ja sillä on odotetut oikeudet näyttämättä sen sisältöä.
82. Salaisuustiedosto puuttuu

Jos salaisuustiedostoa ei ole isännällä, kontti ei voi todentaa tai alustaa oikein.

Selvitä ensin, onko odotettu salaisuuden polku olemassa.

Älä luo salaisuutta uudelleen satunnaisesti.

Korvaava salaisuus voi mitätöidä olemassa olevat istunnot tai muun kryptografisen tilan riippuen siitä, miten sovellus käyttää sitä.

Kaikki tarkoituksellinen salaisuuden korvaaminen on siksi käsiteltävä kontrolloituna turvatoimenpiteenä.
83. Pysyvä taltio ei ole kirjoitettavissa

Jos LUMS ei voi kirjoittaa sovellustietoja, tarkista taltio:
bash

sudo docker volume inspect \
    lums-data

Tarkista sitten kontin liitokset:
bash

sudo docker inspect \
    --format='{{json .Mounts}}' \
    lums

Sovelluksen tietokannan on sijaittava pysyvässä kirjoitettavassa taltiossa.

Älä tee koko kontin tiedostojärjestelmästä kirjoitettavaa kiertotienä.

Oikea ratkaisu on tunnistaa tarkka polku, joka vaatii pysyvyyttä.
84. Docker-kontti käynnistyy, mutta sovellus epäonnistuu

Jos kontti käynnistyy ja poistuu välittömästi:
bash

sudo docker ps -a \
    --filter name=lums

Tarkista sitten:
bash

sudo docker logs \
    --tail 200 \
    lums

Yleisiä syitä ovat:
text

Application startup error
Missing secret
Database initialization error
Migration failure
Invalid environment configuration
Permission problem
Dependency problem

Älä heti rakenna kuvaa uudelleen.

Selvitä, onko ongelma kuvassa, ajonaikaisessa konfiguraatiossa, pysyvässä datassa vai ulkoisessa konfiguraatiossa.
85. Docker-kuva vs. kontin konfiguraatio

Toimiva kuva voi silti epäonnistua virheellisen ajonaikaisen konfiguraation vuoksi.

Erota aina:
text

Docker image
    +
Container runtime configuration
    +
Persistent volume
    +
Secret/configuration

Esimerkiksi:
text

Image is valid
      +
Wrong volume
      =
Application failure

tai:
text

Image is valid
      +
Missing secret
      =
Application startup failure

Älä rakenna muuten kelvollista kuvaa uudelleen korjataksesi ajonaikaisen konfiguraatio-ongelman.
86. Docker-koontiongelmat

Jos uutta kuvaa ei voi rakentaa, tarkista ensin Dockerfile.

Tarkista peruskuva ja riippuvuusmääritelmät.

Tuotannon Dockerfile käyttää kiinnitettyä Python-peruskuvan tiivistettä.

Tämä tarjoaa toistettavuuden ja estää koontia siirtymästä hiljaisesti liittymättömään peruskuvarevisioon.

Jos koonti yhtäkkiä muuttaa käyttäytymistään, vertaa:
text

Dockerfile
Base-image digest
Requirements
Application source
Build context

87. .dockerignore-ongelmat

Docker-koontikonteksti ei saa sisältää tarpeettomia paikallisia tiedostoja tai arkaluonteista materiaalia.

Arkisto käyttää .dockerignore-tiedostoa sulkeakseen pois tiedostoja, kuten:
text

Local backups
Temporary files
Editor artifacts
Backup copies
Other unnecessary runtime material

Jos koonti odottamatta sisältää tiedoston, jota ei pitäisi olla, tarkista:
bash

cat .dockerignore

Älä ratkaise koontikontekstiongelmia kopioimalla arkaluonteisia tiedostoja kuvaan.
88. Tiedostojärjestelmän käyttöoikeusongelmat

Jos LUMS raportoi käyttöoikeusvirheitä, tunnista ensin tarkka polku.

Hyödyllisiä tietoja:
bash

sudo docker inspect \
    lums

ja:
bash

sudo docker logs \
    --tail 200 \
    lums

Tärkeä ero on:
text

Application data
Temporary data
Application source
Secret material
Host configuration

Jokaisella on erilaiset odotetut käyttöoikeudet.

Älä muuta omistajuutta tai käyttöoikeuksia rekursiivisesti koko tiedostojärjestelmässä vianmäärityksen oikotienä.
89. Tuotannon konfiguraation ajautuminen

Konfiguraation ajautuminen tapahtuu, kun ajonaikainen ympäristö ei enää vastaa aiottua turvallisuusperustasoa.

Esimerkkejä:
text

Container runs as root
Port 5050 exposed externally
Read-only filesystem disabled
Capabilities restored
Privileged mode enabled
Secret mounted read-write
Unexpected container running

Jos ajautuminen havaitaan:

    Kirjaa nykyinen tila.

    Selvitä, milloin se muuttui.

    Tunnista vastuullinen konfiguraatio.

    Korjaa konfiguraatio harkitusti.

    Suorita asiaankuuluva turvallisuuden varmistus uudelleen.

Älä tee useita liittymättömiä muutoksia kerralla.
90. Odottamaton verkon altistuminen

Sovellusportin pitäisi pysyä paikallisena:
text

127.0.0.1:5050

Tarkista kuuntelijat:
bash

sudo ss -lntp

Jos 5050 on altistettu muulla kuin loopback-osoitteella, tutki Docker-portin yhdistämistä välittömästi.

Älä altista sovellusporttia vain siksi, että Nginxin diagnosointi näyttää vaikealta.

Aiottu arkkitehtuuri on:
text

Network
   ↓
Nginx :443
   ↓
127.0.0.1:5050
   ↓
LUMS

91. Odottamattomat Docker-kontit

Listaa kaikki kontit:
bash

sudo docker ps -a

Odottamattomat kontit on tunnistettava ennen niiden poistamista.

Tarkista:
text

Container name
Image
Creation time
Ports
Volumes
Restart policy

Älä poista tuntematonta konttia selvittämättä, onko se osa LUMS-käyttöönottoa tai vaadittua varaympäristöä.
92. Docker-taltiota ei saa poistaa normaalin vianmäärityksen aikana

Seuraava toiminto on tuhoava:
bash

sudo docker volume rm lums-data

Sitä ei saa käyttää yleisenä vianmääritysaskeleena.

Taltion poistaminen voi poistaa sovelluksen tietokannan ja siihen liittyvän pysyvän tilan.

Jos puhdas asennus on tarkoituksella tarpeen, käsittele sitä erillisenä migraatio- tai palautustoimenpiteenä ja varmista varmuuskopiot ensin.
93. Turvallisuusperustaso ajonaikaisten muutosten jälkeen

Kun olet muuttanut tuotannon Docker-konfiguraatiota, varmista turvallisuusperustaso uudelleen.

Varmista vähintään:
text

Container runs as intended user
Root filesystem is read-only
Capabilities are dropped
Privileged mode is disabled
no-new-privileges is enabled
Secret mount is read-only
Database volume is writable
Application port is loopback-only

Konfiguraatiota, joka saa sovelluksen toimimaan mutta heikentää näitä ominaisuuksia, ei tule pitää onnistuneena korjauksena.
94. Seuraava vianmääritysalue

Jäljellä olevat vianmääritysaiheet ovat:
text

Tests and CI
Diagnostic snapshots
Common failure combinations
Recovery principles
Final troubleshooting checklist

Viimeiset osiot tarjoavat tiiviin menettelyn riittävän tiedon keräämiseksi ongelman diagnosoimiseksi ilman tuotantoympäristön tarpeetonta muuttamista.
95. Testit ja CI

Automatisoidut testit ovat tärkeä osa LUMSin vianmääritystä.

Ennen kuin tutkit tuotanto-ongelmaa sovellusvirheenä, varmista, kattaako testisarja jo kyseisen käyttäytymisen.

Nykyisen täydellisen testisarjan pitäisi läpäistä ennen kuin julkaisua pidetään valmiina.

Suorita täydellinen testisarja arkistosta:
bash

./.venv-test/bin/pytest -q

Onnistunut ajo ilmoittaa kaikki testit läpäistyiksi.

Testien määrä muuttuu, kun uusia testejä lisätään. Tärkeä
ehto on, että täydellinen testisarja onnistuu sen sijaan, että luotettaisiin
kiinteään testien määrään.
96. Testin epäonnistuminen ei automaattisesti tarkoita, että tuotanto on rikki

Epäonnistunut testi voi johtua:
text

Application regression
Test regression
Dependency change
Environment problem
Missing test dependency
Incorrect test configuration

Tarkista ensin täydellinen virhetuloste.

Älä muuta tuotantokonfiguraatiota vain siksi, että paikallinen testi epäonnistuu.

Oikea järjestys on:
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

97. RBAC-testien epäonnistumiset

Kun tutkit valtuutusongelmia, suorita ensin RBAC-testit:
bash

./.venv-test/bin/pytest -q tests/test_rbac.py

Testit kattavat roolikohtaisen käyttäytymisen ja valtuutusrajat.

Jos ongelma koskee asiakassivua, käytä asiaankuuluvaa osajoukkoa tarvittaessa:
bash

./.venv-test/bin/pytest -q \
    tests/test_rbac.py -k client_page

Älä heikennä valtuutusta testin läpäisemiseksi.

Epäonnistunut valtuutustesti voi osoittaa turvallisuusregressiota.
98. Pakettihaun testien epäonnistumiset

Paketinhallintatoiminnallisuudella on oma testikattavuus.

Kun tutkit pakettihaun käyttäytymistä:
bash

./.venv-test/bin/pytest -q \
    tests/test_package_search.py

Jos virhe liittyy paketin suoritukseen tai työtuloksiin, tarkista myös asiaankuuluvat työtulostestit.

Testisarjaa tulee käyttää erottamaan:
text

Application logic problem
Package-search problem
Agent problem
Integration problem

99. Työtuloksen validoinnin testit

Työtuloksen käsittely on turvallisuuskriittistä, koska palvelin ei saa sokeasti luottaa mielivaltaiseen asiakassyötteeseen.

Suorita asiaankuuluvat testit, kun tutkit tulosvalidointia:
bash

./.venv-test/bin/pytest -q \
    tests/test_job_result.py

Virhe tässä tulee käsitellä sovelluksen oikeellisuus- ja turvallisuusongelmana.

Älä ohita tulosvalidointia saadaksesi asiakasraportin onnistumaan.
100. CI-epäonnistumiset

LUMS käyttää jatkuvaa integraatiota projektin varmentamiseen ennen muutosten hyväksymistä.

Jos CI epäonnistuu:

    Tunnista epäonnistunut työ.

    Lue täydellinen virhe.

    Selvitä, liittyykö virhe koodiin, riippuvuuteen, testiin vai ympäristöön.

    Toista paikallisesti mahdollisuuksien mukaan.

    Korjaa juurisyy.

    Suorita asiaankuuluvat testit.

    Suorita täydellinen testisarja.

Älä jätä CI-epäonnistumisia huomiotta vain siksi, että tuotantoympäristö näyttää tällä hetkellä toimivalta.
101. Diagnostinen tilannekuva

Kun pyydät apua LUMS-ongelmaan, kerää minimaalinen diagnostinen tilannekuva.

Tavoitteena on tarjota riittävät tiedot epäonnistuvan komponentin tunnistamiseksi paljastamatta salaisuuksia.

Hyödyllinen tilannekuva sisältää:
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

Käytä vain ongelmaan liittyviä komentoja.

Älä dumppaa koko ympäristöä tukipyyntöön.
102. Diagnostinen tilannekuva ei saa sisältää salaisuuksia

Ennen diagnostisen tulosteen jakamista tarkista:
text

Passwords
Client tokens
Application secret keys
Session secrets
Private keys
TLS private material
Credentials

Redaktoi arkaluonteiset arvot ennen jakamista.

Älä oleta, että loki on turvallinen vain siksi, että se tuli järjestelmäpalvelusta.
103. Vikayhdistelmämatriisi

Jotkin oireet on helpompi diagnosoida, kun useita komponentteja tarkastellaan yhdessä.
Oire	Todennäköisin ensisijainen tarkistusalue
Selain ei voi muodostaa yhteyttä	Nginx / TLS / verkko
Nginx toimii, mutta sovellus epäonnistuu	Docker / LUMS
LUMS toimii, mutta asiakas ei voi raportoida	Agentti / TLS / tunniste
Asiakas raportoi, mutta työ pysyy odottavana	Valvoja / kelpoisuus
Työ käynnistyy, mutta paketti epäonnistuu	APT / pacman
Paketti onnistuu, mutta tulos puuttuu	Agentin raportointi
Tulos saavuttaa palvelimen, mutta käyttöliittymä on vanhentunut	API / tietokanta / selaimen tila
Viewer voi muuttaa dataa	Palvelinpuolen RBAC
Käyttäjä ei voi kirjautua sisään	Tili / salasana / nopeusrajoitus
Kirjautuminen toimii, mutta toiminto hylätään	RBAC / CSRF
Tietokantakirjoitukset epäonnistuvat	SQLite / levy / käyttöoikeudet
Kontti menettää dataa uudelleenluonnin jälkeen	Pysyvän taltion konfiguraatio
Sovellus kirjoittaa juuritiedostojärjestelmään	Kontin tiedostojärjestelmän konfiguraatio
Portti 5050 on ulkoisesti tavoitettavissa	Docker / palomuurikonfiguraatio

Tämä taulukko tunnistaa ensimmäisen tutkittavan paikan, ei välttämättä lopullista juurisyytä.
104. Yleiset vianmääritysvirheet

Vältä seuraavia oikoteitä:
Älä poista tietokantaa
text

Deleting lums.db
Deleting lums-data

voi tuhota pysyvän sovelluksen tilan.
Älä poista turvakontrolleja käytöstä

Älä poista pysyvästi käytöstä:
text

RBAC
CSRF protection
TLS validation
Container hardening
Read-only filesystem
no-new-privileges
Capability restrictions

Kiertotie, joka poistaa turvakontrollin, ei ole suoritettu korjaus.
Älä aja konttia etuoikeutetusti

Vältä:
text

--privileged

vianmääritysratkaisuna.

Jos sovellus vaatii lisäpääsyä, selvitä tarkalleen, mitä pääsyä tarvitaan.
Älä altista porttia 5050

Älä muuta:
text

127.0.0.1:5050

muotoon:
text

0.0.0.0:5050

vain ohittaaksesi Nginx.

Sovellus on tarkoituksella suojattu käänteisvälityspalvelimen taakse.
Älä muokkaa työn tiloja manuaalisesti

Vältä suoraa muuttamista:
text

update_jobs
update_job_packages

toimintaongelman piilottamiseksi.

Käytä sovelluksen, agentin, valvojan ja palautuksen mekanismeja.
Älä poista paketinhallinnan lukkoja sokeasti

Lukko voi osoittaa aktiivista paketinhallintaprosessia.

Tunnista prosessi ensin.
Älä vaihda tunnistetietoja toistuvasti

Toistuva tunnisteen tai salaisuuden vaihto voi luoda lisää todentamisongelmia.

Selvitä ensin, mikä tunniste on tällä hetkellä konfiguroitu ja mitä tunnistetta palvelin odottaa.
105. Palautusperiaatteet

Seuraavat periaatteet koskevat kaikkea LUMS-vianmääritystä:
Säilytä ensin

Pidä:
text

Logs
Job state
Database
Container state
Configuration
Error messages

kunnes ongelma on ymmärretty.
Muuta yhtä asiaa kerrallaan

Kun useita muutoksia tehdään samanaikaisesti, alkuperäinen syy on vaikeampi tunnistaa.
Varmista jokaisen muutoksen jälkeen

Kontrolloidun muutoksen jälkeen:
text

Re-test
Check logs
Verify state
Confirm security properties

Suosi palautuvia muutoksia

Käytä aina kun mahdollista muutoksia, jotka voidaan peruuttaa tuhoamatta sovelluksen tilaa.
Pidä turvakontrollit aktiivisina

Onnistunut vianmääritystulos ei saa aiheuttaa tarpeetonta turvallisuusregressiota.
106. Tuotannon vianmääritysjärjestys

Yleiseen LUMS-tuotanto-ongelmaan käytä tätä järjestystä:
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

Tämä järjestys estää liittymättömien komponenttien tarpeettoman muuttamisen.
107. Koko järjestelmän diagnostinen polku

Kun asianomainen komponentti on tuntematon, seuraa täydellistä polkua:
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

Kysy jokaisessa vaiheessa:
text

Did the request reach this component?

Did this component process it?

Did it produce the expected result?

Did the next component receive that result?

Ensimmäinen EI yleensä tunnistaa alueen, joka vaatii tutkimista.
108. Julkaisun vianmääritys

Ennen julkaisun valmistelua varmista:
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

Julkaisua ei pidä luoda vain siksi, että sovellus käynnistyy onnistuneesti.
109. Vianmäärityksen tarkistuslista

Käytä tätä tarkistuslistaa ennen kuin julistat tuotanto-ongelman ratkaistuksi:
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

110. Milloin lopettaa vianmääritys

Lopeta muutosten tekeminen, kun:
text

The root cause is identified
    AND
The corrective action is understood
    AND
The system is stable
    AND
Security controls remain intact

Jos juurisyy ei ole ymmärretty, säilytä nykyinen tila sen sijaan, että muuttaisit ympäristöä toistuvasti.

Puhtaasti säilytetty vika on helpompi diagnosoida kuin osittain muokattu järjestelmä.
111. Lopullinen palautusperiaate

Tärkein LUMS-vianmäärityssääntö on:

    Havaitse ensin. Muuta toiseksi. Varmista kolmanneksi.

LUMS sisältää useita itsenäisiä turvallisuus- ja suorituskerroksia.

Yhden kerroksen ongelma ei automaattisesti saisi johtaa muutoksiin toisessa.

Ensisijainen vianmääritystapa on siksi:
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

Tämä pitää vianmäärityksen hallittuna, toistettavana ja LUMSin turvallisuusperustason mukaisena.
112. Dokumentaation ylläpito

Tämä asiakirja tulee päivittää aina, kun dokumentoitu toiminnallinen käyttäytyminen muuttuu.

Dokumentaatiomuutosten tulee pysyä yhdenmukaisina seuraavien kanssa:
text

Security documentation
Deployment documentation
Agent behavior
Watcher behavior
RBAC model
Package-management behavior
Docker runtime configuration
Test baseline

Vanhentuneet vianmääritysohjeet voivat olla vaarallisia, kun ne suosittelevat vanhentuneita komentoja tai turvallisuutta heikentäviä kiertoteitä.

Kun tuotannon käyttäytyminen muuttuu, päivitä asiaankuuluva dokumentaatio ennen kuin vianmääritysmenettelyä pidetään valmiina.
113. Nykyinen perustaso

Tämän vianmääritysoppaan dokumentoima nykyinen LUMS-perustaso sisältää:
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

Tarkka testien määrä voi muuttua projektin kasvaessa.

Turvallisuus- ja arkkitehtuuriominaisuudet ovat tärkeä perustaso.
114. Vianmääritysoppaan loppu

LUMS-vianmäärityksen tulee pysyä todisteisiin perustuvana ja turvallisuustietoisena.

Kun olet epävarma:
text

Preserve the state.
Inspect the evidence.
Identify the failing layer.
Make the smallest safe change.
Verify the result.
Document what happened.

Älä vaihda turvallisuutta tai datan eheyttä nopeaan kiertotiehen.

LUMS-vianmääritysoppaan loppu
