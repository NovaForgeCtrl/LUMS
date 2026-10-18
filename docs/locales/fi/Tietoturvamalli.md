# LUMS Turvallisuusdokumentaatio

**LUMS — Linux Update Management Server**

Tämä asiakirja kuvaa LUMSin nykyisen turvallisuusarkkitehtuurin, toteutetut turvakontrollit, turvallisuustarkastuksen tulokset, toiminnalliset rajoitukset ja turvallisuuteen liittyvät suunnittelupäätökset.

Asiakirja heijastaa **tällä hetkellä toteutettua järjestelmän tilaa**. Suunnitellut tai tulevat parannukset on nimenomaisesti merkitty sellaisiksi.

---

# Turvallisuusperiaatteet

LUMS noudattaa syvyyspuolustusmenetelmää Linux-päivitysten hallinnassa.

Turvallisuusmalli erottaa hallinnollisen todentamisen, asiakastodentamisen, valtuutuksen, hallitun päivityksen suorituksen ja valvontalokituksen.

Ensisijaiset turvallisuustavoitteet ovat:

* todennettu hallinnollinen pääsy
* roolipohjainen valtuutus
* todennettu asiakasviestintä
* hallittu päivityksen suoritus
* suojaus samanaikaista työn suoritusta vastaan
* palautettavat päivitystyöt
* suojatut salaisuudet
* hallittu kontin suoritus
* valvottavat turvallisuuskriittiset toiminnot
* ennustettava virheenkäsittely
* turvallisuusregressiotestaus

LUMS on ensisijaisesti tarkoitettu hallittuun infrastruktuuri-, laboratorio- ja sisäverkkoympäristöön.

Sitä ei tule altistaa suoraan julkiseen internetiin ilman lisäturvallisuuskatsausta ja asianmukaisia verkkokontrolleja.

---

# Turvallisuusarkkitehtuuri

LUMS koostuu seuraavista turvallisuuden kannalta merkityksellisistä komponenteista:

* Web-hallintakäyttöliittymä
* REST API
* SQLite-tietokanta
* LUMS-agentti hallinnoiduilla asiakkaille
* APT- ja pacman-paketinhallinnan taustajärjestelmät
* Päivitystyö- ja palautusmekanismit
* Nginx HTTPS -käänteisvälityspalvelin
* Kovennettu Docker-kontti

Perushallintavirta on:

Selain → HTTPS/Nginx → LUMS API → SQLite → LUMS Agent → Paketinhallinta → Tulos → SQLite → Web UI

Todentaminen ja valtuutus on tarkoituksella erotettu toisistaan.

Kelvollinen todennettu istunto ei automaattisesti myönnä pääsyä jokaiseen hallinnolliseen toimintoon.

Valtuutus valvotaan palvelinpuolella. Verkkokäyttöliittymä piilottaa lisäksi toimintoja, jotka eivät ole käytettävissä nykyiselle roolille, mutta käyttöliittymän näkyvyyttä ei koskaan pidetä turvarajana.

---

## Hallinnollinen todentaminen

Hallinnolliset käyttäjät todentavat itsensä LUMSin verkkokäyttöliittymän kautta.

Salasanoja ei koskaan tallenneta selkokielisinä. LUMS käyttää Argon2-pohjaista salasanatiivistystä salasanojen tallentamiseen.

Hallinnolliset istunnot käyttävät:

* todennettua palvelinpuolen istunnonhallintaa
* istunnon vanhenemista
* istunnon uudelleengenerointia
* CSRF-suojausta tilaa muuttaville selainpyynnöille
* kirjautumisen nopeusrajoitusta
* istunnon mitätöintiä uloskirjautumisen aikana
* palvelinpuolen roolivalidointia

Todentaminen ja valtuutus pysyvät erillisinä turvakontrolleina.

Onnistuneesti todennetulla käyttäjällä on silti oltava vaadittu oikeus
suojattuihin toimintoihin.

---

# Roolipohjainen käyttöoikeushallinta

LUMS tukee tällä hetkellä kolmea web-käyttäjäroolia:

* `administrator`
* `operator`
* `viewer`

Roolimallit tallennetaan `users.role`-kenttään; yksittäiset oikeudet tallennetaan
palvelinpuolelle `user_permissions`-tauluun.

Palvelin lataa kunkin todennetun tilin tehokkaat oikeudet.
Asiakaspuolen oikeustiedot ohjaavat vain esitystä eivätkä koskaan
korvaa palvelinpuolen valtuutusta.

## Administrator

Ylläpitäjillä on täysi hallinnollinen ja operatiivinen pääsy.

He voivat:

* tarkastella asiakkaita
* luoda asiakkaita
* poistaa asiakkaita käytöstä
* vaihtaa asiakastunnisteita
* tarkastella asennettuja paketteja ja saatavilla olevia päivityksiä
* luoda päivitystöitä
* suorittaa tuettuja päivitystoimintoja
* tarkastella päivitystyöhistoriaa
* käyttää paketinhallintaa
* käyttää järjestelmän ylläpitotoimintoja
* hallita käyttäjiä
* hallita käyttäjärooleja
* käyttää hallinnollisia toimintoja

## Operator

Operaattorit voivat suorittaa operatiivisia päivityshallintatehtäviä.

He voivat:

* tarkastella asiakkaita
* tarkastella asennettuja paketteja ja saatavilla olevia päivityksiä
* luoda päivitystöitä
* suorittaa tuettuja päivitystoimintoja
* tarkastella päivitystyöhistoriaa
* käyttää paketinhallintaa
* käyttää järjestelmän ylläpitotoimintoja

Operaattorit eivät voi:

* hallita käyttäjiä
* muuttaa käyttäjärooleja
* luoda asiakkaita
* poistaa asiakkaita käytöstä
* vaihtaa asiakastunnisteita

## Viewer

Viewereillä on rajoitettu vain luku -pääsy.

He voivat:

* tarkastella asiakkaita
* tarkastella asennettuja ohjelmistoja

Seuraavat hallinta-alueet on piilotettu Viewer-tileiltä:

* Päivitykset
* Päivitystyöt
* Päivityshistoria
* Paketinhallinta
* Järjestelmän ylläpito

Viewer-tilit eivät voi suorittaa tilaa muuttavia päivityshallintatoimintoja.

Palvelin valvoo näitä rajoituksia itsenäisesti todentamisen
ja käyttäjäkohtaisten oikeustarkistusten kautta.

---

# Asiakastodennus

Jokainen hallinnoitu LUMS-asiakas käyttää yksilöllistä Bearer-tunnistetta.

Todentamismekanismi noudattaa mallia:

`Authorization: Bearer <CLIENT_TOKEN>`

Palvelin ei tallenna asiakastunnisteita selkokielisinä arvoina.

Sen sijaan LUMS tallentaa asiakastunnisteen SHA-256-heksadesimaalitiivisteen.

Todentamisvirta on:

Client Token → SHA-256 → Token Digest → SQLite

Asiakastodennus varmistaa todennetun tunnisteen rekisteröityä asiakasta vasten ja tarkistaa lisäksi asiaankuuluvan asiakastilan.

Turvallisuusmalli ei käytä lähde-IP-osoitetta ainoana todisteena asiakkaan identiteetistä.

Tämä mahdollistaa LUMSin toiminnan:

* yksityisissä laboratorioverkoissa
* eristetyssä infrastruktuurissa
* NAT-pohjaisissa verkoissa
* offline-ympäristöissä
* verkoissa, joissa asiakasosoitteet voivat muuttua

Valtuutetut ylläpitäjät voivat vaihtaa asiakastunnisteita.

Tunnisteen vaihto luo korvaavan tunnisteen, tallentaa vain sen tiivisteen, mitätöi edellisen tunnisteen, kirjaa hallinnollisen toimenpiteen valvontalokiin ja esittää korvaavan tunnisteen kerran.

Selkokielisiä asiakastunnistearvoja ei kirjoiteta valvontatietueisiin.

---

# Turvallisuustarkastus

Turvallisuustarkastus suoritetaan vaiheittain.

Jokainen tarkastusalue käydään läpi todellista toteutusta vasten, mitä seuraa automatisoidut testit, eristetty varmistus tai tuotannon varmistus tarpeen mukaan.

Nykyiset tarkastusalueet:

| Tarkastus | Alue                                   | Tila                      |
| --------- | -------------------------------------- | ------------------------- |
| #01       | SQLite Foreign Keys                    | PASS                      |
| #02       | SQLite Runtime Configuration           | PASS                      |
| #03       | Update Timeout Handling                | PASS                      |
| #04       | Login Rate Limiting                    | PASS                      |
| #05       | API Input Validation                   | PASS                      |
| #06       | Session Revocation                     | PASS                      |
| #07       | Client Token Rotation                  | PASS                      |
| #08       | IP Address Handling / Offline Networks | PASS                      |
| #09       | Job Recovery / Checkpointing           | PASS                      |
| #10       | APT Robustness                         | PASS                      |
| #11       | Arch Reboot Detection                  | PASS                      |
| #12       | Unit Tests / API Result Validation     | PASS                      |
| #13       | Simulation Tests                       | PASS                      |
| #14       | Continuous Integration                 | PASS                      |
| #15       | Application / Audit Logging            | PASS                      |
| #16       | Versioning / Releases                  | REVIEWED — OPEN BY DESIGN |
| #17       | Role-Based Access Control              | PASS                      |
| #18       | Documentation Review                   | IN PROGRESS               |

Tarkastus #16 eroaa tarkoituksella yllä olevista teknisistä turvakontrolleista.

LUMSilla ei ole tällä hetkellä virallista vakaata julkaisua, julkaisutunnistetta eikä GitHub-julkaisua. Tämä on tarkoituksellista, koska projekti on edelleen aktiivisessa kehityksessä.

Tarkastus #18 pysyy avoimena, kunnes täydellinen dokumentaatiosarja on tarkastettu ja synkronisoitu nykyisen toteutuksen kanssa.

# Turvallisuustarkastus #01

## SQLite Foreign Keys

SQLite-viiteavainten valvonta on käytössä sovelluksen tietokantayhteyksille.

Sovellus ottaa eksplisiittisesti käyttöön:

`PRAGMA foreign_keys = ON`

Tämä varmistaa, että viite-eheys valvotaan toisiinsa liittyvien tietokantatietueiden välisissä suhteissa.

Tarkastus varmisti:

* viiteavainten valvonnan ajonaikana
* viiteavainten eheyden
* asiakkaan elinkaaren käyttäytymisen
* asiakkaan käytöstä poistamisen käyttäytymisen
* historiallisten työtietojen säilyttämisen
* valvontatietojen säilyttämisen

Asiakastilaa käsitellään konservatiivisesti.

Tarvittaessa asiakkaat poistetaan käytöstä sen sijaan, että ne poistettaisiin tavalla, joka tuhoaisi historialliset toimintatiedot.

**Tila: PASS**

---

# Turvallisuustarkastus #02

## SQLite Runtime Configuration

Tuotannon SQLite-tietokannan ajonaikainen konfiguraatio tarkastettiin.

Varmennettu tuotantokonfiguraatio on:

* `journal_mode`: `wal`
* `busy_timeout`: `5000`
* `synchronous`: `2`

Sovellus ottaa eksplisiittisesti käyttöön:

`PRAGMA foreign_keys = ON`

Tuotantotietokanta käyttää tällä hetkellä WAL-tilaa.

Tietokantakonfiguraatio dokumentoitiin todellisen varmennetun tuotantotilan perusteella historiallisen kehityskonfiguraation sijaan.

Konfiguroitu busy timeout vähentää välittömiä tietokantavirheitä, kun toinen transaktio pitää tietokantaa tilapäisesti.

Sovellustason viiteavainasetus varmistaa viite-eheyden jokaiselle tietokantayhteydelle.

Tarkastus sisälsi aktiivisen SQLite-konfiguraation tuotantovarmistuksen.

**Tila: PASS**

---

# Turvallisuustarkastus #03

## Update Timeout and Process Handling

Päivityksen suoritus on suojattu paketinhallintaprosesseilta, jotka estävät loputtomasti.

Suoritusvirta on:

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

Toteutus käyttää hallittua aliprosessien käsittelyä, jotta hiljaiset prosessit eivät voi estää loputtomasti odottaessaan tulostetta.

Aikakatkaisun käsittely testattiin seuraavissa:

* hiljaiset prosessit
* normaali prosessin valmistuminen
* aikakatkaisutilanteet
* prosessit, jotka vastustavat normaalia lopetusta
* kill-varamenetelmä
* integraatiotason aikakatkaisukäyttäytyminen

Aikakatkaisumekanismi estää paketinhallintatoimintoa pysymästä loputtomasti aktiivisessa tilassa.

Virheet ja aikakatkaisutilanteet palautetaan hallittuina työtuloksina ja tallennetaan työn tilaan.

Nykyinen dokumentoitu LUMS Agent -versio on:

`1.7.0`

**Tila: PASS**

---

# Turvallisuustarkastus #04

## Login Rate Limiting

Hallinnolliset kirjautumisyritykset ovat nopeusrajoitettuja.

Nykyinen eskalaatiokäytäntö on:

* 5 epäonnistunutta yritystä → 30 sekuntia
* 6 epäonnistunutta yritystä → 60 sekuntia
* 7 epäonnistunutta yritystä → 120 sekuntia
* 8 tai enemmän epäonnistunutta yritystä → 300 sekuntia

Nopeusrajoituksen tila tallennetaan SQLiteen.

Samanaikaiset kirjautumisepäonnistumiset käyttävät transaktionaalista tietokantalukitusta:

`BEGIN IMMEDIATE`

Tämä estää samanaikaisia todennusvirheitä ohittamasta aiottua nopeusrajoituksen tilaa kilpailutilanteiden kautta.

Onnistunut todennus tyhjentää sovellettavan epäonnistumistilan.

Tarkastus kattoi:

* eristetyn nopeusrajoituksen käyttäytymisen
* samanaikaiset todennusvirheet
* transaktion peruutuksen
* tietokantalukon käsittelyn
* onnistuneen kirjautumisen nollauskäyttäytymisen
* nopeusrajoituksen valvontatapahtumat
* tuotannon kirjautumiskäyttäytymisen

Nopeusrajoitin tarjoaa siten palvelinpuolen kontrollin toistuvia todennusyrityksiä vastaan sen sijaan, että se luottaisi asiakaspuolen käyttäytymiseen.

**Tila: PASS**

---

# Tarkastuksen tila osan 2 jälkeen

Neljä ensimmäistä turvallisuustarkastusaluetta on valmis:

| Tarkastus | Alue                              | Tila |
| --------- | --------------------------------- | ---- |
| #01       | SQLite Foreign Keys               | PASS |
| #02       | SQLite Runtime Configuration      | PASS |
| #03       | Update Timeout / Process Handling | PASS |
| #04       | Login Rate Limiting               | PASS |

Seuraavat tarkastusalueet on dokumentoitu myöhemmissä osioissa:

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

Tarkastus #18 — Documentation Review — pysyy avoimena, kunnes täydellinen dokumentaatiosarja on tarkastettu ja synkronisoitu nykyisen toteutuksen kanssa.

# Turvallisuustarkastus #05

## API Input Validation

LUMS validoi turvallisuuskriittisen API-syötteen palvelinpuolella.

Asiakkaan toimittamia arvoja ei luoteta vain siksi, että ne tulevat todennetusta verkkokäyttöliittymästä tai rekisteröidystä asiakkaasta.

Validointia sovelletaan asiaankuuluviin API-parametreihin, mukaan lukien:

* asiakastunnisteet
* pakettinimet
* päivitystyötoiminnot
* pakettiluettelot
* hakuparametrit
* käyttäjähallintaparametrit
* asiakastunnistetoiminnot
* työtulostiedot

Pakettinimet validoidaan ennen kuin ne välitetään paketinhallintatoimintoihin.

Päivitystyö-API hyväksyy vain eksplisiittisesti tuetut toiminnot.

Tällä hetkellä tuetut paketteihin liittyvät toiminnot ovat:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Odottamattomat toiminnot hylätään.

Pakettiluettelot validoidaan ennen työn luomista.

`UPDATE_PACKAGE`-toiminnolle pyydetyn paketin on myös oltava läsnä asiakkaan saatavilla olevien päivitysten tiedoissa.

Tietokantakyselyt käyttävät parametroitua SQL:ää sen sijaan, että SQL-lauseita rakennettaisiin epäluotetusta syötteestä.

Tämä estää käyttäjän hallitsemien arvojen tulkitsemisen SQL-syntaksiksi.

Tarkastus sisälsi negatiivisen syötteen testausta ja SQL-injektiosuuntautuneita testitapauksia.

Validointikontrollit varmennettiin myös automatisoidun testisarjan kautta.

**Tila: PASS**

---

# Turvallisuustarkastus #06

## Session Revocation

LUMS suojaa todennettuja hallinnollisia istuntoja jatkokäytöltä uloskirjautumisen jälkeen.

Istunnon käsittely sisältää:

* todennetut palvelinpuolen istunnot
* istunnon vanhenemisen
* istunnon uudelleengeneroinnin
* uloskirjautumisen mitätöinnin
* palvelinpuolen todennustarkistukset
* palvelinpuolen roolivalidoinnin

Uloskirjautuminen mitätöi aktiivisen todennetun istunnon.

Suojatut API-päätepisteet edellyttävät todennettua istuntoa eivätkä luota asiakaspuolen tilaan sen määrittämiseksi, onko käyttäjä edelleen todennettu.

Istunnon tila arvioidaan siten palvelimen toimesta suojatuille toiminnoille.

Tilaa muuttavat selainpyynnöt edellyttävät lisäksi CSRF-suojausta.

Tarkastus varmisti, että:

* todennettu pääsy toimii normaalisti
* suojatut päätepisteet hylkäävät todentamattomat pyynnöt
* uloskirjautuminen mitätöi aktiivisen istunnon
* aiemmin todennettu istunto ei voi jatkaa suojatun toiminnallisuuden käyttöä mitätöinnin jälkeen
* roolitiedot arvioidaan palvelinpuolella

**Tila: PASS**

---

# Turvallisuustarkastus #07

## Client Token Rotation

Jokainen hallinnoitu LUMS-asiakas käyttää yksilöllistä todennustunnistetta.

Asiakastunnisteita ei tallenneta selkokielisinä arvoina.

Sen sijaan LUMS tallentaa asiakastunnisteen SHA-256-heksadesimaalitiivisteen.

Todentamismalli on:

`Authorization: Bearer <CLIENT_TOKEN>`

Palvelin hashaa toimitetun tunnisteen ja vertaa tuloksena olevaa tiivistettä rekisteröidyn asiakastunnisteen tiivisteeseen.

Valtuutetut ylläpitäjät voivat vaihtaa asiakkaan tunnisteen.

Tunnisteen vaihto suorittaa seuraavat toiminnot:

1. Luo korvaava tunniste.
2. Laske sen SHA-256-tiiviste.
3. Korvaa tallennettu asiakastunnisteen tiiviste.
4. Mitätöi edellinen tunniste.
5. Kirjaa hallinnollinen toimenpide valvontalokiin.
6. Esitä korvaava tunniste ylläpitäjälle.

Edellinen tunniste ei voi todentaa vaihdon jälkeen.

Selkokielisiä tunnistearvoja ei kirjoiteta valvontalokeihin.

Tarkastus varmisti:

* onnistuneen tunnistetodennuksen
* tunnistetiivisteen tallennuksen
* tunnisteen vaihdon
* edellisen tunnisteen mitätöinnin
* todennuksen korvaavalla tunnisteella
* tunnisteen vaihdon valtuutusvaatimukset
* valvontalokituksen
* suojauksen luvatonta vaihtoa vastaan

Asiakastunnisteen vaihto on rajoitettu ylläpitäjille.

Operaattorit ja viewerit eivät voi vaihtaa asiakastunnisteita.

**Tila: PASS**

---

# Turvallisuustarkastus #08

## IP Address Handling and Offline Networks

LUMS ei käytä asiakkaan lähde-IP-osoitetta ainoana todisteena asiakkaan identiteetistä.

Asiakastodennus perustuu rekisteröityyn asiakastunnisteeseen.

Tämä suunnittelu on tarkoituksellista, koska hallinnoidut asiakkaat voivat toimia ympäristöissä, joissa niiden verkko-osoite muuttuu.

Tuetut käyttöönottoskenaariot sisältävät:

* yksityiset laboratorioverkot
* NAT-pohjaiset verkot
* eristetyn infrastruktuurin
* dynaamisesti osoitetut asiakkaat
* offline-ympäristöt
* hallitut sisäverkot

Palvelin erottaa siten:

**Verkkosijainti**

seuraavasta:

**Asiakasidentiteetti**

Kelvollinen asiakastunniste identifioi rekisteröidyn asiakkaan.

Asiakkaan verkko-osoite voidaan edelleen tallentaa toiminnallisiin ja valvontatarkoituksiin, mutta sitä ei kohdella todennusmääritteenä.

Toteutus välttää myös oletuksia siitä, että asiakkaan on oltava tavoitettavissa kiinteästä osoitteesta.

Tämä on erityisen tärkeää laboratorioympäristöille ja infrastruktuurille, joissa verkkotopologia voi muuttua muuttamatta hallinnoidun järjestelmän loogista identiteettiä.

Tarkastus varmisti asiakastodennuksen ilman kiinteään lähde-IP-osoitteeseen luottamista.

**Tila: PASS**

---

# Tarkastuksen tila osan 3 jälkeen

Seuraavat turvallisuustarkastusalueet on suoritettu:

| Tarkastus | Alue                                   | Tila |
| --------- | -------------------------------------- | ---- |
| #01       | SQLite Foreign Keys                    | PASS |
| #02       | SQLite Runtime Configuration           | PASS |
| #03       | Update Timeout / Process Handling      | PASS |
| #04       | Login Rate Limiting                    | PASS |
| #05       | API Input Validation                   | PASS |
| #06       | Session Revocation                     | PASS |
| #07       | Client Token Rotation                  | PASS |
| #08       | IP Address Handling / Offline Networks | PASS |

Seuraava osio kattaa:

* #09 Job Recovery / Checkpointing
* #10 APT Robustness
* #11 Arch Reboot Detection
* #12 Unit Tests / API Result Validation

# Turvallisuustarkastus #09

## Job Recovery and Checkpointing

LUMS-päivitystyöt on suunniteltu palautumaan turvallisesti keskeytyneestä suorituksesta.

Päivitystyöt ylläpitävät pysyvää tilaa SQLite-tietokannassa.

Yksittäiset pakettitoiminnot seurataan erikseen kokonaistyön tilasta.

Tämä antaa agentille mahdollisuuden määrittää, mitkä pakettitoiminnot on jo suoritettu onnistuneesti ennen keskeytyneen työn jatkamista.

Palautuksen aikana onnistuneesti suoritettuja pakettitoimintoja ei suoriteta uudelleen.

Palautuslogiikka noudattaa siten periaatetta:

`Persistent Job State → Determine Completed Work → Skip Completed Items → Continue Remaining Work`

Tämä vähentää tarpeettomien toistettujen pakettitoimintojen riskiä seuraavien jälkeen:

* agentin keskeytys
* prosessin lopetus
* järjestelmän uudelleenkäynnistys
* tilapäinen viestintävirhe
* kontin uudelleenkäynnistys
* muut suorituksen keskeytykset

Tarkastus varmisti keskeytyneen työn palautuksen ja tarkistuspistekäyttäytymisen.

Palautus testattiin töillä, jotka sisälsivät useita pakettitoimintoja ja aiemmin onnistuneita pakettikohteita.

Tarkastus vahvisti, että suoritettu työ säilytetään ja jäljellä oleva työ voi jatkua toistamatta tarpeettomasti onnistuneita toimintoja.

**Tila: PASS**

---

# Turvallisuustarkastus #10

## APT Robustness

Debian-pohjaiset pakettitoiminnot suoritetaan LUMS-paketinhallintakerroksen kautta.

APT:hen liittyvät päivitystoiminnot tarkastettiin paketinhallinnan tilan ja päivitystulosten luotettavan tunnistamisen varalta.

Toteutus huomioi tapaukset, joissa paketinhallintakomennot voivat palauttaa onnistuneesti, mutta vaativat lisätulkintaa tulosteestaan tai tuloksena olevasta järjestelmän tilasta.

APT-päivitysten tunnistusta kovennettiin välttämään yhden yksinkertaistetun komentotulosteen ehdon varassa.

Tarkastus sisälsi testausta seuraavissa:

* normaalit APT-toiminnot
* saatavilla olevat pakettipäivitykset
* paketin asennus
* paketin poisto
* päivitystyön suoritus
* APT-tuloksen käsittely
* päivitysten tunnistuskäyttäytyminen

Vastaava koventaminen committoitiin seuraavasti:

`c76f331 security: harden apt update detection`

Tavoitteena on varmistaa, että LUMS ei virheellisesti raportoi paketinhallinnan tilaa pelkästään puutteellisen tai epäselvän komentotulosteen perusteella.

**Tila: PASS**

---

# Turvallisuustarkastus #11

## Arch Linux Reboot Detection

Arch Linux -pakettitoiminnot voivat johtaa järjestelmän tilaan, jossa uudelleenkäynnistys on tarpeen tai suositeltavaa.

Siksi LUMS arvioi tuloksena olevan järjestelmän tilan asiaankuuluvien paketinhallintatoimintojen jälkeen.

Agentti erottaa pakettitoiminnon normaalin valmistumisen tilanteista, joissa uudelleenkäynnistys vaaditaan.

Uudelleenkäynnistystila raportoidaan takaisin LUMS-palvelimelle osana työn tulosta.

Tämä antaa hallintakäyttöliittymän erottaa:

* onnistunut pakettitoiminto
* onnistunut toiminto, jossa on uudelleenkäynnistysvaatimus
* epäonnistunut toiminto

Tarkastus varmisti Arch Linux -uudelleenkäynnistyksen tunnistuksen käyttäen todellista paketinhallinnan suorituspolkua.

Toteutus testattiin uudelleenkäynnistysvaatimustilanteita ja normaalin valmistumisen ehtoja vasten.

**Tila: PASS**

---

# Turvallisuustarkastus #12

## Unit Tests and API Result Validation

Turvallisuuskriittinen käyttäytyminen on katettu automatisoiduilla testeillä.

Testisarja sisältää kattavuuden todentamiselle, valtuutukselle, API-validoinnille, päivitystöille, paketinhallinnalle, asiakastodennukselle ja tulosten käsittelylle.

Agentti-palvelin-tulos polku tarkastettiin erityisesti sen varmistamiseksi, että työtulokset eivät voi mielivaltaisesti muuttaa liittymätöntä palvelinpuolen tilaa.

Tulosten käsittely validoi toimitetut tiedot ennen tilamuutosten soveltamista vastaavaan päivitystyöhön.

Validointi kattaa asiaankuuluvat tuloskentät ja odotetut työsuhteet.

Tämä estää todennettua asiakasta vapaasti valitsemasta liittymättömiä töitä tai injektoimasta mielivaltaista tilaa päivitystyötietokantaan.

Turvallisuustestisarja kattaa myös negatiiviset ja luvattomat tapaukset.

Suorita täydellinen automatisoitu testisarja arkiston juuresta komennolla
`./.venv-test/bin/pytest -q`. Testien määrä muuttuu ajan myötä; käytä
nykyisen ajon tulosta tässä asiakirjassa mainitun kiinteän määrän sijaan.

Asiaankuuluvat turvakontrollit varmennettiin lisäksi kohdennetuilla testiajoilla tarkastuksen aikana.

**Tila: PASS**

---

# Tarkastuksen tila osan 4 jälkeen

Seuraavat turvallisuustarkastusalueet on suoritettu:

| Tarkastus | Alue                                   | Tila |
| --------- | -------------------------------------- | ---- |
| #01       | SQLite Foreign Keys                    | PASS |
| #02       | SQLite Runtime Configuration           | PASS |
| #03       | Update Timeout / Process Handling      | PASS |
| #04       | Login Rate Limiting                    | PASS |
| #05       | API Input Validation                   | PASS |
| #06       | Session Revocation                     | PASS |
| #07       | Client Token Rotation                  | PASS |
| #08       | IP Address Handling / Offline Networks | PASS |
| #09       | Job Recovery / Checkpointing           | PASS |
| #10       | APT Robustness                         | PASS |
| #11       | Arch Reboot Detection                  | PASS |
| #12       | Unit Tests / API Result Validation     | PASS |

Seuraava osio kattaa:

* #13 Simulation Tests
* #14 Continuous Integration
* #15 Application / Audit Logging
* #16 Versioning / Releases

# Turvallisuustarkastus #13

## Simulation Tests

LUMS tarjoaa simulaatiomekanismin päivityshallinnan työnkulkujen testaamiseen suorittamatta vastaavaa paketinhallintatoimintoa hallinnoidussa järjestelmässä.

Simulaatio on toteutettu agentin suorituskerroksessa.

Kun simulaatio on käytössä, paketinhallintatoiminnot esitetään ja käsitellään ilman pyydetyn pakettimuutoksen soveltamista käyttöjärjestelmään.

Tämä mahdollistaa päivitystyön käyttäytymisen testaamisen ilman hallinnoidun järjestelmän tarkoituksellista muuttamista.

Simulaatiotestit kattavat asiaankuuluvat päivityshallinnan polut, mukaan lukien:

* paketin asennus
* paketin poisto
* pakettipäivitykset
* järjestelmäpäivitykset
* työn suoritus
* tulosten raportointi
* onnistunut valmistuminen
* virheenkäsittely

Simulaatiomekanismia käytettiin turvallisuustarkastuksen aikana työn luonnin, agentin suorituksen, tulosten käsittelyn ja palvelinpuolen tilasiirtymien varmistamiseen riippumattomasti todellisista pakettimuutoksista.

Simulaatiotila on testausmekanismi eikä korvaa normaalin päivitystoiminnan valtuutuskontrolleja.

**Tila: PASS**

---

# Turvallisuustarkastus #14

## Continuous Integration

LUMS käyttää automatisoitua testausta turvallisuus- ja toiminnallisten regressioiden havaitsemiseksi ennen kuin muutokset katsotaan valmiiksi.

CI-prosessi suorittaa automatisoidun testisarjan projektia vasten.

Testiympäristö varmistaa sovelluksen ja turvallisuuskriittisen toiminnallisuuden riippumattomasti tuotantokontista.

CI-prosessi sisältää validoinnin seuraaville:

* todentaminen
* valtuutus
* RBAC
* API:n käyttäytyminen
* päivitystyön käsittely
* paketinhallinnan käyttäytyminen
* asiakastodennus
* työtuloksen validointi
* turvallisuuskriittinen virheenkäsittely

CI-tarkastus katsottiin turvallisuuden koventamismuutosten jälkeen.

Lopullinen varmennettu testisarja valmistui onnistuneesti.

Testien määrä muuttuu projektin kehittyessä. CI tarjoaa automatisoidun
regressioesteen turvallisuuskriittisille sovellusmuutoksille.

**Tila: PASS**

---

# Turvallisuustarkastus #15

## Application and Audit Logging

LUMS tallentaa turvallisuuskriittiset hallinnolliset ja operatiiviset tapahtumat sovellustason valvontalokituksen kautta.

Valvontalokitus on suunniteltu tarjoamaan toiminnallinen historia tallentamatta arkaluonteisia tunnistetietoja.

Asiaankuuluvat turvallisuuskriittiset toiminnot sisältävät tapahtumia, kuten:

* todentamiseen liittyvät turvallisuustapahtumat
* hallinnolliset toimet
* asiakashallinta
* asiakastunnistetoiminnot
* päivitystyön luominen
* päivitystyön suoritus
* turvallisuuteen liittyvät virheet

Arkaluonteinen tunnistusmateriaali on suljettu pois valvontatietueista.

Erityisesti:

* salasanoja ei kirjata
* selkokielisiä asiakastunnisteita ei kirjata
* salaisia arvoja ei tarkoituksella kirjoiteta valvontatietueisiin

Valvontatietueet liitetään asiaankuuluvaan hallinnolliseen tai toiminnalliseen kontekstiin tarpeen mukaan.

Valvontalokituksen toteutus tarkastettiin seuraavien osalta:

* turvallisuuskriittisten tapahtumien kattavuus
* tunnistetietojen poissulkeminen
* hallinnollinen jäljitettävyys
* virheenkäsittely
* asiaankuuluvien valvontatietojen säilyttäminen

Lokitusjärjestelmä on tarkoitettu tukemaan sekä operatiivista vianmääritystä että turvallisuustutkintaa.

**Tila: PASS**

---

# Turvallisuustarkastus #16

## Versioning and Releases

Versiointi ja julkaisujen hallinta tarkastettiin osana turvallisuustarkastusta.

LUMS on tällä hetkellä aktiivisessa kehityksessä eikä sillä ole vielä virallista vakaata julkaisua.

Nykyisessä arkiston tilassa on siksi tarkoituksella:

* ei virallista vakaata julkaisuversiota
* ei julkaisutunnistetta
* ei GitHub-julkaisua

Nykyiset komponenttiversiot ovat:

* LUMS Agent: `1.7.0`
* LUMS Watcher: `1.2.1`

Tällä hetkellä ei ole yhtä muodollista versionumeroa, joka edustaisi koko LUMS-sovellusta.

Tämä on tarkoituksellinen projektin tilaa koskeva päätös eikä vahingossa tapahtunut laiminlyönti.

Suunniteltu julkaisuprosessi on:

1. Suorita toteutustyö loppuun.
2. Suorita turvallisuuskatsaus loppuun.
3. Tarkista ja synkronisoi dokumentaatio.
4. Suorita täydellinen automatisoitu testisarja.
5. Varmista CI.
6. Määritä julkaisuversio.
7. Luo vastaava Git-tunniste.
8. Julkaise GitHub-julkaisu.
9. Säilytä julkaisu dokumentoituna perustasona.

Virallista julkaisua ei luoda vain siksi, että turvallisuustarkastus saavuttaa tietyn tarkastusnumeron.

Julkaisun luominen tapahtuu vasta, kun jäljellä oleva toteutus- ja dokumentaatiotyö on suoritettu.

**Tila: REVIEWED — OPEN BY DESIGN**

---

# Tarkastuksen tila osan 5 jälkeen

Seuraavat turvallisuustarkastusalueet on suoritettu:

| Tarkastus | Alue                                   | Tila                      |
| --------- | -------------------------------------- | ------------------------- |
| #01       | SQLite Foreign Keys                    | PASS                      |
| #02       | SQLite Runtime Configuration           | PASS                      |
| #03       | Update Timeout / Process Handling      | PASS                      |
| #04       | Login Rate Limiting                    | PASS                      |
| #05       | API Input Validation                   | PASS                      |
| #06       | Session Revocation                     | PASS                      |
| #07       | Client Token Rotation                  | PASS                      |
| #08       | IP Address Handling / Offline Networks | PASS                      |
| #09       | Job Recovery / Checkpointing           | PASS                      |
| #10       | APT Robustness                         | PASS                      |
| #11       | Arch Reboot Detection                  | PASS                      |
| #12       | Unit Tests / API Result Validation     | PASS                      |
| #13       | Simulation Tests                       | PASS                      |
| #14       | Continuous Integration                 | PASS                      |
| #15       | Application / Audit Logging            | PASS                      |
| #16       | Versioning / Releases                  | REVIEWED — OPEN BY DESIGN |

Jäljellä oleva numeroitu tekninen tarkastusalue on:

* #17 Role-Based Access Control

Dokumentaation tarkastus seurataan erikseen:

* #18 Documentation Review — IN PROGRESS

# Turvallisuustarkastus #17

## Role-Based Access Control

LUMS yhdistää roolimallit yksilöllisesti määritettyihin oikeuksiin. Tuetut
mallit ovat `administrator`, `operator` ja `viewer`; mallin valitseminen
valitsee sen oletusoikeudet, joita ylläpitäjä voi mukauttaa
jokaiselle tilille.

Rooli pysyy tilin metatietona. Suojatut reitit valtuuttavat
tilin palvelinpuolelle tallennettua oikeusjoukkoa vasten, ei roolitunnistetta vasten. Käyttöliittymä piilottaa
käyttämättömissä olevat toiminnot käytettävyyden vuoksi, kun taas palvelin pysyy turvarajana.

---

## RBAC Permission Model

| Oikeus            | Myönnetty pääsy |
| ----------------- | --------------- |
| `clients.view`    | Tarkastele asiakkaita ja järjestelmätietoja |
| `software.view`   | Tarkastele asennettuja ohjelmistoja |
| `updates.view`    | Tarkastele saatavilla olevia päivityksiä, töitä ja historiaa |
| `packages.search` | Hae pakettivarastoista |
| `jobs.manage`     | Luo pakettitoimintoja ja päivitystöitä |
| `clients.manage`  | Rekisteröi/poista asiakkaita ja vaihda asiakastunnisteita |
| `users.manage`    | Luo käyttäjiä ja hallitse rooleja ja oikeuksia |

Oletusarvoiset roolimallit ovat:

| Malli           | Oletusoikeudet |
| --------------- | -------------- |
| `administrator` | Kaikki oikeudet |
| `operator`      | Asiakas-/ohjelmisto-/päivitysnäkyvyys, pakettihaku ja työnhallinta |
| `viewer`        | Asiakasnäkyvyys ja asennettujen ohjelmistojen näkyvyys |

Asiakkaisiin liittyvät oikeudet edellyttävät `clients.view`-oikeutta. `jobs.manage` edellyttää myös
`updates.view`-oikeutta. Käyttöliittymä lataa todennetun tilin oikeudet ja
jättää pois kontrollit, joita käyttäjä ei voi käyttää; palvelinpuolen tarkistukset valvovat itsenäisesti
samoja myönnytyksiä.

---

## Authorization Enforcement

Suojatut toiminnot käyttävät palvelinpuolen todentamista ja oikeustarkistuksia.

Valtuutusmalli noudattaa periaatetta:

`Authenticate → Load User Permissions → Authorize Operation → Execute`

Pelkkä todentaminen ei riitä etuoikeutettujen toimintojen käyttämiseen.

Tilaa muuttavat toiminnot edellyttävät lisäksi CSRF-suojausta tarpeen mukaan.

Esimerkkejä suojatuista hallinnollisista toiminnoista ovat:

* päivitystyön luominen
* paketin asennus
* paketin poisto
* pakettipäivitykset
* järjestelmäpäivitykset
* paketinhallintatoiminnot
* asiakkaan luominen
* asiakkaan käytöstä poistaminen
* asiakastunnisteen vaihto
* käyttäjän luominen
* käyttäjähallintatoiminnot

Suojatut päätepisteet määrittävät eksplisiittisesti vastaavaan toimintoon vaadittavan oikeuden.

Puuttuva oikeus hylätään palvelimen toimesta, vaikka käyttäjä manuaalisesti
rakentaisi vastaavan HTTP-pyynnön.

Tämä estää RBAC-mallin ohittamisen kutsumalla suoraan API-päätepistettä, joka on piilotettu verkkokäyttöliittymässä.

---

## Viewer Restrictions

Viewer-malli on tarkoituksella rajoitettu sen oletusoikeusjoukon mukaisesti.

Tileille, joilla ei ole vastaavia myönnytyksiä, asiakaskäyttöliittymä ei paljasta:

* Päivitykset
* Päivitystyöt
* Päivityshistoria
* Paketinhallinta
* Järjestelmän ylläpito

Palvelin estää lisäksi tilejä, joilla ei ole vastaavia myönnytyksiä,
suorittamasta suojattuja toimintoja.

JavaScript-käyttöliittymä ei lataa päivityshallintatietoja ilman
`updates.view`-oikeutta.

Tämä vähentää toiminnallisten tietojen tarpeetonta altistumista samalla kun palvelinpuolen valtuutus säilyy varsinaisena turvakontrollina.

Asennettu ohjelmisto on edelleen Viewer-tilien käytettävissä vain luku -tietotoimintona.

---

## Administrative User Management

Käyttäjähallinta edellyttää `users.manage`-oikeutta.

Käyttäjät, joilla on kyseinen oikeus, voivat luoda tilejä ilman oikeuksia ja sitten
määrittää yksittäisiä myönnytyksiä tai soveltaa roolimallia oikeuseditorissa.
Roolimalleilla on kuvaukset, jotka selittävät niiden oletusmyönnytykset.

Valtuutetut käyttäjähallinnoijat voivat tallentaa sisäisen muistiinpanon tiliä kohden. Muistiinpanot on
rajoitettu 2 000 merkkiin, niitä ei sisällytetä valvontalokin tietoihin eikä
ne ole näkyvissä tilin omistajalle.

Käyttäjän luominen sisältää:

* käyttäjänimen validointi
* roolin validointi
* salasanan validointi
* Argon2-salasanatiivistys
* päällekkäisten käyttäjien tunnistus
* valvontalokitus
* CSRF-suojaus
* palvelinpuolen valtuutus

Käyttäjähallinnan päätepisteet eivät ole käytettävissä ilman `users.manage`-oikeutta.

Palvelin hylkää tuntemattomat oikeudet ja virheelliset riippuvuusyhdistelmät.
Ainakin yhdellä aktiivisella tilillä on säilytettävä `users.manage`-oikeus; muutokset, jotka
poistaisivat viimeisen käyttäjähallinnoijan, hylätään.

Salasanoja ei koskaan tallenneta selkokielisinä.

---

## RBAC Database Migration

Roolimallitiedot säilyvät käyttäjätietokannan tietueessa. Yksittäiset
myönnytykset tallennetaan `user_permissions`-tauluun viiteavaimella
käyttäjätiliin. Migraatio `003-user-permissions` luo kyseisen taulun ja täyttää
olemassa olevat tilit niiden nykyisestä roolimallista säilyttäen niiden pääsyn
siirtymän aikana. Migraatio `004-user-admin-notes` lisää yksityisen
`users.admin_note`-kentän; olemassa olevat tilit saavat tyhjän muistiinpanon. Migraatio
`005-backup-permission` myöntää `backups.manage`-oikeuden olemassa oleville Administrator-
tileille.

Tietokannan varmuuskopion luominen edellyttää `backups.manage`-oikeutta; Administrator-
malli sisältää tämän oikeuden oletuksena. Palvelin kirjoittaa SQLite-online-
varmuuskopiot vain palvelinkonfiguroituun `LUMS_BACKUP_DIR`-hakemistoon; se ei hyväksy
tiedostojärjestelmäpolkuja selaimesta. Varmuuskopiotiedostot luodaan vain omistajan
oikeuksin ja niiden eheys tarkistetaan ennen julkaisua.

---

## RBAC Security Testing

RBAC-käyttäytyminen on katettu automatisoiduilla testeillä.

Testit sisältävät:

* Administrator-valtuutus
* Operator-valtuutus
* Viewer-rajoitukset
* suojattu API-pääsy
* luvattomat toiminnot
* asiakashallinnan rajoitukset
* päivitystyön rajoitukset
* käyttäjähallinnan rajoitukset
* asiakassivun näkyvyys
* oikeuskohtainen käyttöliittymäkäyttäytyminen

RBAC-testit kattavat roolimallien oletukset, mukautetut oikeudet, oikeus-
riippuvuudet ja palvelinpuolen valtuutuksen. Tuotantovarmistuksen tulisi
sisältää tilejä, joilla on mukautetut oikeudet, sekä oletusarvoiset
Administrator-, Operator- ja Viewer-mallit.

---

## RBAC Security Result

RBAC-toteutus tarjoaa kerroksittaisen valtuutuksen:

1. Todentaminen vahvistaa käyttäjän identiteetin.
2. Palvelin lataa käyttäjän oikeudet.
3. Suojatut reitit valvovat vaadittua oikeutta.
4. CSRF-suojaus koskee asiaankuuluvia selaimen tilamuutoksia.
5. Verkkokäyttöliittymä piilottaa käyttämättömissä olevan toiminnallisuuden.
6. Automatisoidut testit varmistavat valtuutusrajat.

Käyttöliittymä ei siten itsessään tarjoa valtuutusmekanismia.

Palvelin pysyy ensisijaisena turvarajana.

**Tila: PASS**

# Turvallisuustarkastus #18

## Documentation Review

Turvallisuusdokumentaatio tarkastetaan nykyistä toteutettua LUMS-järjestelmää vasten.

Tämän tarkastuksen tarkoitus on varmistaa, että turvallisuusdokumentaatio kuvaa todellista toteutusta eikä aiempaa kehitystilaa.

Tarkastus kattaa:

* todentaminen
* valtuutus
* RBAC
* asiakastodennus
* tunnisteen käsittely
* istunnon käsittely
* CSRF-suojaus
* nopeusrajoitus
* SQLite-konfiguraatio
* päivityksen suoritus
* työn palautus
* paketinhallinta
* kontin koventaminen
* verkon altistuminen
* salaisuuksien käsittely
* riippuvuuksien ja koontien turvallisuus
* tiedostojärjestelmän käyttöoikeudet
* sovellus- ja valvontalokitus
* versiointi ja julkaisujen käsittely
* automatisoitu turvallisuustestaus

Dokumentaation on erotettava:

* toteutetut kontrollit
* varmennettu tuotantokäyttäytyminen
* suunnitellut parannukset
* tarkoituksella avoimet projektipäätökset

Historiallisia toteutustietoja ei saa esittää nykyisenä tuotantokonfiguraationa.

Erityisesti dokumentaatio heijastaa nykyistä SQLite-tuotantokonfiguraatiota nykyisen WAL-konfiguraation sijaan.

Nykyinen tuotannon ajonaikainen ympäristö on dokumentoitu seuraavasti:

* `journal_mode = wal`
* `busy_timeout = 5000`
* `synchronous = 2`
* sovellustason `PRAGMA foreign_keys = ON`

Nykyinen Viewer-RBAC-käyttäytyminen on myös dokumentoitu toteutetun tuotantokäyttöliittymän mukaisesti.

Viewer-käyttäjillä on pääsy:

* asiakastietoihin
* asennettuun ohjelmistoon

Viewer-käyttäjillä ei ole pääsyä:

* Päivityksiin
* Päivitystöihin
* Päivityshistoriaan
* Paketinhallintaan
* Järjestelmän ylläpitoon

Dokumentaation tarkastus poistaa tai korvaa myös vanhentuneet viittaukset aiempiin testien määriin, migraatiotiloihin, käyttöönottokonfiguraatioihin ja vain kehityksessä käytettyyn käyttäytymiseen.

**Tila: IN PROGRESS**

---

# Lisäturvallisuuden koventaminen

Numeroitu turvallisuustarkastus kattaa ensisijaiset sovelluksen turvakontrollit.

Lisäkoventaminen suoritettiin alkuperäisen tarkastussekvenssin jälkeen, ja se on osa nykyistä turvallisuusperustasoa.

Nämä kontrollit on dokumentoitu tässä, koska ne edustavat nykyisen käyttöönoton tärkeitä turvaominaisuuksia.

---

## Container Hardening

Tuotannon LUMS-kontti toimii kovennetulla Docker-konfiguraatiolla.

Tuotantokontti käyttää:

* ei-root-sovelluskäyttäjä
* vain luku -juuritiedostojärjestelmä
* poistetut Linux-kyvykkyydet
* `no-new-privileges`
* rajoitetut väliaikaiset tiedostojärjestelmät
* vain luku -salaisuuden liitos
* erillinen pysyvä sovellusdatataltio
* uudelleenkäynnistyskäytäntö
* vain loopback -isäntäjulkaisu sovellusportille

Sovelluksen juuritiedostojärjestelmä ei siis ole kirjoitettavissa normaalin toiminnan aikana.

Kirjoitettavat sijainnit on eksplisiittisesti rajoitettu sovelluksen vaatimiin sijainteihin.

Tuotantokontti tarkastettiin itsenäisesti tehokkaan ajonaikaisen konfiguraation varmistamiseksi.

Kovennettu ajonaikainen ympäristö testattiin myös varmistamalla, että:

* sovelluksen tiedostojärjestelmäkirjoitukset epäonnistuvat
* `/tmp` pysyy saatavilla tarvittaessa
* `/var/lib/lums` pysyy kirjoitettavana
* salaisuustiedosto pysyy vain luku -tilassa
* sovellus pysyy toiminnassa

---

## Network Exposure

LUMS-sovellusporttia ei ole suoraan altistettu LAN-verkkoon.

Docker-sovellusportti on sidottu loopback-rajapintaan:

`127.0.0.1:5050`

Ulkoinen pääsy tarjotaan Nginxin kautta.

Tuotantoisäntä altistaa aiotut verkkopalvelut palomuurin ja käänteisvälityspalvelimen kautta.

Käyttöönotto varmennettiin estämään suora etäpääsy sisäiseen Docker-sovellusporttiin.

Palomuuri käyttää oletusarvoisesti kieltävää mallia saapuvalle ja reititetylle liikenteelle.

Aiotut ulkoisesti tavoitettavissa olevat palvelut ovat:

* SSH
* HTTP
* HTTPS

Web-palvelin ohjaa HTTP-pyynnöt HTTPS:ään.

Oletusarvoinen Nginx-sivusto poistettiin, jotta liittymätön oletussisältö ei altistu.

---

## Transport Security

Hallinnollinen verkkopääsy tarjotaan HTTPS:n kautta.

HTTP ohjataan HTTPS:ään.

TLS-päätepisteen hoitaa Nginx eikä Flask/Gunicorn-sovellus suoraan.

Tämä pitää kuljetusturvallisuuden ja sovelluspalvelun erillään.

Sisäinen Gunicorn-sovellusportti ei siis ole tarkoitettu julkiseksi HTTP-päätepisteeksi.

Nykyinen käyttöönotto on tarkoitettu hallittuun sisäiseen infrastruktuuriin.

Tuleva käyttöönotto, jossa on suora julkinen internet-altistus, vaatisi lisäturvallisuuskatsauksen.

---

## Secrets and Configuration

Tuotantosalaisuuksia ei tallenneta sovelluksen lähdekoodipuuhun.

LUMS-salaisuusavain toimitetaan suojatun salaisuustiedoston kautta.

Tuotantokontti vastaanottaa salaisuuden kautta:

`/run/secrets/lums_secret`

Salaisuustiedosto liitetään vain luku -tilassa.

Sovellus lukee salaisuuden konfiguroidun salaisuustiedostomekanismin kautta.

Arkiston ja Docker-koontikontekstin käsittely tarkastettiin tahattoman sisällyttämisen estämiseksi seuraaville:

* tietokantatiedostot
* varmuuskopiotiedostot
* salaisuustiedostot
* yksityiset avaimet
* varmenteet
* ajonaikaiset lokit
* paikalliset varmuuskopioartefaktit

Arkisto myös ohittaa yleiset väliaikaiset varmuuskopiomallit, joita käytetään kehityksen aikana.

---

## Dependency and Build Security

Tuotannon Docker-kuva käyttää kiinnitettyä Python-peruskuvan tiivistettä.

Tuotannon ajonaikaiset riippuvuudet on eksplisiittisesti versiokiinnitetty.

Nykyinen tuotannon riippuvuusjoukko sisältää:

* Flask `3.1.3`
* argon2-cffi `25.1.0`
* Gunicorn `23.0.0`

Docker-koontikonteksti on rajoitettu `.dockerignore`-tiedoston kautta.

Toistuvia tuotantokoontaja verrattiin tarkastuksen aikana.

Asiaankuuluvat riippuvuus- ja pakettimetatiedot pysyivät yhdenmukaisina toistuvien koontien välillä odotettuja generoitujen Python-bytekoodierojen lisäksi.

Tämä tarjoaa toistettavan perustason tuotantokuvalle samalla kun koontikonteksti pidetään rajoitettuna.

---

## Filesystem and Runtime Permissions

Tuotantosovellus toimii omistautuneena `lums`-käyttäjänä root-käyttäjän sijaan.

Pysyvät sovellustiedot tallennetaan erilliseen LUMS-datataltioon.

Sovelluksen juuritiedostojärjestelmä on vain luku -tilassa.

Ajonaikainen kirjoitusoikeus on rajoitettu eksplisiittisesti vaadittuihin sijainteihin.

Tuotannon ajonaikainen ympäristö varmennettiin hylkäämään luvattomat kirjoitukset sovelluksen tiedostojärjestelmään.

Tämä vähentää tahattoman tai haitallisen tiedostomuokkauksen vaikutusta sovelluskontin sisällä.

---

# Turvallisuustarkastuksen johtopäätös

Nykyinen LUMS-toteutus on käynyt läpi laajan turvallisuuskatsauksen, joka kattaa:

* todentaminen
* valtuutus
* RBAC
* istunnon turvallisuus
* CSRF-suojaus
* kirjautumisen nopeusrajoitus
* asiakastunnisteen turvallisuus
* API-validointi
* SQL-injektioresistenssi
* SQLite-eheys
* päivityksen suoritus
* aikakatkaisun käsittely
* työn palautus
* paketinhallinnan robustisuus
* tulosvalidointi
* simulaatio
* jatkuva integraatio
* valvontalokitus
* kontin koventaminen
* verkon altistuminen
* kuljetusturvallisuus
* salaisuuksien käsittely
* tiedostojärjestelmän käyttöoikeudet
* riippuvuuksien ja koontien turvallisuus

Numeroidut tarkastustulokset ovat:

| Tarkastus | Alue                                   | Tila                      |
| --------- | -------------------------------------- | ------------------------- |
| #01       | SQLite Foreign Keys                    | PASS                      |
| #02       | SQLite Runtime Configuration           | PASS                      |
| #03       | Update Timeout / Process Handling      | PASS                      |
| #04       | Login Rate Limiting                    | PASS                      |
| #05       | API Input Validation                   | PASS                      |
| #06       | Session Revocation                     | PASS                      |
| #07       | Client Token Rotation                  | PASS                      |
| #08       | IP Address Handling / Offline Networks | PASS                      |
| #09       | Job Recovery / Checkpointing           | PASS                      |
| #10       | APT Robustness                         | PASS                      |
| #11       | Arch Reboot Detection                  | PASS                      |
| #12       | Unit Tests / API Result Validation     | PASS                      |
| #13       | Simulation Tests                       | PASS                      |
| #14       | Continuous Integration                 | PASS                      |
| #15       | Application / Audit Logging            | PASS                      |
| #16       | Versioning / Releases                  | REVIEWED — OPEN BY DESIGN |
| #17       | Role-Based Access Control              | PASS                      |
| #18       | Documentation Review                   | IN PROGRESS               |

Tarkastuksissa #01–#15 ja #17 tarkastetut tekniset turvakontrollit ovat läpäisseet.

Tarkastus #16 pysyy tarkoituksella avoimena, koska LUMS ei ole vielä saavuttanut ensimmäistä virallista vakaata julkaisuaan.

Tarkastus #18 pysyy avoimena, kunnes koko projektidokumentaatio on tarkastettu ja synkronisoitu lopullisen toteutustilan kanssa.

Mitään turvallisuustarkastuksen tulosta ei pidä tulkita takeeksi siitä, että LUMS on vapaa haavoittuvuuksista.

Turvallisuus on jatkuva prosessi.

Muutokset sovellukseen, agenttiin, riippuvuuksiin, kontin konfiguraatioon, verkon altistumiseen, todentamismalliin tai käyttöönottoarkkitehtuuriin tulisi laukaista uusi turvallisuuskatsaus asianomaisille kontrolleille.

---

# Turvallisuusperustaso

Nykyinen turvallisuusperustaso perustuu varmennettuun toteutukseen ja tuotannon käyttöönoton tilaan.

Perustaso sisältää:

* palvelinpuolen todentaminen
* palvelinpuolen RBAC
* Argon2-salasanatiivistys
* SHA-256-asiakastunnisteiden tiivisteet
* CSRF-suojaus
* kirjautumisen nopeusrajoitus
* parametroitu SQL
* validoitu API-syöte
* hallittu paketinhallinnan suoritus
* päivitystyön palautus
* valvontalokitus
* kovennettu Docker-ajonaikainen ympäristö
* HTTPS Nginxin kautta
* vain loopback -sovellusportin altistuminen
* palomuurirajoitukset
* suojatut tuotantosalaisuudet
* kiinnitetyt tuotantoriippuvuudet
* rajoitetut tiedostojärjestelmän käyttöoikeudet
* automatisoitu turvallisuustestaus

Tulevien muutosten tulisi säilyttää nämä ominaisuudet, ellei tarkoituksellinen arkkitehtoninen muutos korvaa niitä vastaavalla tai vahvemmalla kontrollilla.

---

# Turvallisuuden ylläpito

Turvakontrollit tulee validoida uudelleen, kun merkittäviä muutoksia otetaan käyttöön.

Esimerkkejä:

* todentamismuutokset
* uudet käyttäjäroolit
* uudet API-päätepisteet
* paketinhallintamuutokset
* agentin suoritusmuutokset
* tietokantamigraatiot
* riippuvuuspäivitykset
* Dockerfile-muutokset
* kontin ajonaikaiset muutokset
* käänteisvälityspalvelinmuutokset
* palomuurimuutokset
* salaisuuksien hallinnan muutokset
* julkaisun valmistelu

Turvallisuustestaus tulee suorittaa ennen virallisen julkaisun julkaisemista.

Turvallisuusdokumentaatio tulee päivittää aina, kun varmennettu turvallisuusperustaso muuttuu.

---

# Julkaisuvalmius

Ensimmäinen virallinen LUMS-julkaisu luodaan vasta, kun:

1. toteutustyö on valmis
2. turvallisuuskatsaus on valmis
3. dokumentaation tarkastus on valmis
4. täydellinen automatisoitu testisarja läpäisee
5. CI läpäisee
6. lopullinen versio on määritetty
7. Git-tunniste on luotu
8. GitHub-julkaisu on julkaistu

Siihen asti LUMS pysyy aktiivisesti kehitettynä projektina.

---

# Loppulausunto

LUMS on suunniteltu hallituksi Linux-päivityshallinta-alustaksi, jossa turvallisuus on keskeinen arkkitehtoninen huolenaihe.

Turvallisuusmalli ei luota yhteen suojamekanismiin.

Sen sijaan todentaminen, valtuutus, validointi, hallittu suoritus, pysyvyys, palautus, lokitus, konttieristys, verkko-rajoitukset ja automatisoitu testaus toimivat yhdessä kerroksellisina kontrolleina.

Projekti suosii tarkoituksella eksplisiittistä palvelinpuolen valvontaa käyttöliittymän kautta tapahtuvan turvallisuuden sijaan.

Nykyinen turvallisuusperustaso on dokumentoitu varmennetun toteutustilan mukaisesti historiallisen kehityskäyttäytymisen sijaan.

---

**LUMS — Linux-päivitysten hallinta ilman turhaa kohinaa.**

`segfault // override`
