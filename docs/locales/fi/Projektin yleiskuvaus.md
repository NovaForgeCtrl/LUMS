# LUMS

**Linux-päivitysten hallinta ilman turhaa kohinaa.**

## Aloittaminen

LUMS hallinnoi Linux-päivityksiä keskitetysti. Palvelin näyttää asiakkaat, asennetut ohjelmistot ja saatavilla olevat päivitykset. Jokaisella hallinnoidulla Linux-järjestelmällä oleva agentti suorittaa hyväksytyt pakettitoiminnot kyseisen järjestelmän paketinhallinnalla. LUMS ei korvaa APT:ta Debian/Ubuntu-järjestelmissä eikä pacmania Arch Linuxissa.

**Käytätkö vain olemassa olevaa LUMS-asennusta?** Avaa ylläpitäjän antama osoite ja kirjaudu sisään omalla tililläsi. Jos jokin ominaisuus puuttuu, tililläsi ei ehkä ole oikeutta käyttää sitä. Kysy apua ylläpitäjältä; älä jaa tilejä äläkä käytä asiakastunnistetta verkkosalasanana.

**Asennatko tai ylläpidätkö LUMSia?** Aloita [asennusoppaasta](<Asennus ja päivitykset.md>) ja lue sitten [hallintaopas](<Ylläpito ja varmuuskopiot.md>). Jos jotain menee pieleen, käytä [vianmääritysopasta](Vianmääritys.md). Käännettyjä oppaita on myös saatavilla, mutta niiden kattavuus voi poiketa englanninkielisistä teknisistä alkuperäisversioista. [Dokumentaatiohakemisto](../../README.md) näyttää saatavilla olevat kieliversiot.

Testiajo tai onnistuneesti rakennettu Docker-kuva **ei** ole tuotantoasennus. Tuotantokäyttöönotto vaatii myös HTTPS:n, suojatun sovellussalaisuuden, pysyvät tiedot, varmennetut varmuuskopiot ja kovennetun kontin. Älä kopioi tuotantokomentoja ennen kuin olet tarkistanut niiden paikkamerkit ja tallennuspolut omaa asennustasi vasten.

### Verkkokäyttöliittymän kielet

Verkkokäyttöliittymä tarjoaa saksan, englannin (US ja UK), ranskan, espanjan, yksinkertaistetun kiinan, japanin, puolan, ruotsin, norjan bokmålin ja suomen. Valitse kieli kirjautumissivun oikeasta yläkulmasta. Jos et valitse kieltä, LUMS yrittää käyttää selaimen kieltä; kirjautumisen jälkeen tilillesi tallennettu kieli on ensisijainen. Jotkin tekniset tai dynaamiset tekstit voivat jäädä alkuperäiselle kielelle, jos käännöstä ei ole saatavilla. Markdown-oppaat ovat erillisiä verkkokäyttöliittymästä eikä niitä käännetä automaattisesti.

---

LUMS on Linux-päivitysten hallintapalvelin, joka on suunniteltu tarjoamaan hallittua, valvottavaa ja turvallista ohjelmisto- ja päivityshallintaa Linux-asiakkaille.

Sen sijaan, että luotettaisiin hallitsemattomaan asiakaspuolen päivitystoimintaan, LUMS tarjoaa keskitetyn hallintakerroksen ohjelmistoluettelointia, päivitysten tunnistamista, pakettitoimintoja, päivitystöitä, suorituksen seurantaa ja tulosten raportointia varten.

LUMS on suunniteltu ympäristöihin, joissa päivitysten on oltava **näkyviä, hallittuja, jäljitettäviä ja palautettavia**.

---

## Mikä on LUMS?

LUMS (**Linux Update Management Server**) koostuu keskuspalvelimesta ja kevyistä Linux-asiakkaista.

Palvelin tarjoaa hallintakäyttöliittymän, API:n, todennuksen, valtuutuksen, töiden hallinnan, valvontalokituksen ja pysyvän tilan.

Asiakaspuolen agentti suorittaa paikalliset paketinhallintatoiminnot ja raportoi tulokset takaisin palvelimelle.

Perusarkkitehtuuri on:

```text
                    ┌──────────────────────┐
                    │      Web Browser      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     LUMS Server      │
                    │                      │
                    │ Web UI / API         │
                    │ Authentication       │
                    │ RBAC                 │
                    │ Job Management       │
                    │ Audit Logging        │
                    │ SQLite               │
                    └──────────┬───────────┘
                               │
                         HTTPS / API
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
      ┌─────────────────┐             ┌─────────────────┐
      │   Linux Client  │             │   Linux Client  │
      │                 │             │                 │
      │ LUMS Agent      │             │ LUMS Agent      │
      │ Package Manager │             │ Package Manager │
      │ Watcher         │             │ Watcher         │
      └─────────────────┘             └─────────────────┘
```

Miksi LUMS?

Linux-järjestelmät tarjoavat jo erinomaiset paketinhallintatyökalut.

LUMS ei yritä korvata niitä.

Sen sijaan LUMS tarjoaa hallintakerroksen näiden työkalujen ympärille, jotta ylläpitäjät voivat vastata keskitetysti kysymyksiin, kuten:

* Mitä asiakkaita on olemassa?

* Mitä ohjelmistoja on asennettu?

* Mitä päivityksiä on saatavilla?

* Mitkä paketit pitäisi asentaa tai poistaa?

* Mitkä päivitystyöt ovat käynnissä?

* Mitä päivityksen aikana tapahtui?

* Raportoiko asiakas tuloksen onnistuneesti?

* Vaadittiinko uudelleenkäynnistys?

* Voiko keskeytynyt työ palautua turvallisesti?

* Kuka käynnisti ylläpitotoimenpiteen?

Tavoitteena ei ole piilottaa taustalla olevaa Linux-paketinhallintaa.

Tavoitteena on tehdä sen toiminnasta hallittavaa ja valvottavaa.
Keskeiset ominaisuudet
Asiakashallinta

LUMS ylläpitää rekisteröityjä Linux-asiakkaita ja niiden todennustilaa.

Jokainen asiakas saa yksilöllisen todennustunnisteen.

Asiakastunnisteita ei tallenneta salasanana. Palvelin tallentaa SHA-256-tiivisteen ja validoi saapuvan asiakastodennuksen tätä tiivistettä vasten.

Ylläpitäjät voivat:

* rekisteröidä asiakkaita

* poistaa asiakkaita käytöstä

* vaihtaa asiakastunnisteita

* tarkastella asiakastilaa

* seurata asiakasraportointia

Ohjelmistoluettelointi

Asiakkaat raportoivat asennetut ohjelmistonsa LUMS-palvelimelle.

Palvelin tallentaa luettelon ja tarjoaa sen hallintakäyttöliittymän kautta.

Asennettujen ohjelmistojen näkymä on tarkoituksella erillään paketinhallinnan hausta.

Tämä mahdollistaa ylläpitäjien ja vain luku -käyttäjien tarkastella asennettuja ohjelmistoja ilman, että paketinhallintatoiminnot paljastuvat automaattisesti.
Päivitysluettelointi

Asiakkaat selvittävät säännöllisesti, onko pakettipäivityksiä saatavilla.

Palvelin tallentaa raportoidut päivitystiedot ja tarjoaa ne valtuutetuille käyttäjille.

Päivitystietoja voidaan käyttää hallittujen päivitystöiden perustana.
Paketinhallinta

LUMS tarjoaa paketinhallintatoimintoja asiakasagentin kautta.

Tuetut pakettitoiminnot ovat:

* INSTALL_PACKAGE

* REMOVE_PACKAGE

* UPDATE_PACKAGE

* UPDATE_SYSTEM

Paketinhallintakerros abstraktoi taustalla olevan paketinhallinnan.

Tällä hetkellä tuetut paketinhallintaperheet ovat:

* Debian / Ubuntu: APT / dpkg

* Arch Linux: pacman

Paketinhaku on myös saatavilla LUMSin kautta.

Hakupyynnöt lähetetään kohdeasiakkaalle, suoritetaan paikallisella paketinhallinnalla ja palautetaan palvelimelle näytettäväksi.
Päivitystyöt

Päivitystoiminnot esitetään pysyvinä töinä.

Työ voi sisältää yhden tai useamman pakettitoiminnon ja ylläpitää palvelinpuolen suoritustilaa.

Yleinen elinkaari on:

```text
PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► SUCCESS
   │
   └──────────────► FAILED
```

Pakettitason tuloksia seurataan erikseen, jotta keskeytyneet työt voidaan palauttaa tarpeettomasti toistamatta jo onnistuneesti suoritettuja toimintoja.
Hallittu suoritus

LUMS ei suorita mielivaltaisia komentotulkkeja verkkokäyttöliittymästä.

Palvelin luo jäsenneltyjä töitä validoitujen toimintojen ja pakettinimien avulla.

Asiakasagentti yhdistää nämä toiminnot asianmukaiseen paikalliseen paketinhallintatoimintoon.

Tämä luo tarkoituksellisen rajan seuraavien välille:

```text
Web UI
   ↓
API
   ↓
Validoitu työ
   ↓
Agentti
   ↓
```
Paketinhallinta

Lepotilatietoinen suoritus

LUMS voi lykätä päivitysten suorittamista, kun asiakas katsotaan aktiiviseksi.

Nykyinen lepotilan kynnysarvo on 300 sekuntia.

Tuettaessa agentti käyttää paikallisen järjestelmän istunto-/lepotilatietoja loginctl:n kautta.

Jos lepotilan tunnistus ei ole käytettävissä, LUMS ei teeskentele, että asiakas on lepotilassa.

Tämä ero on tärkeä, koska tuntematon lepotila ei ole sama kuin vahvistettu lepotila.
Töiden palautus

Päivitystyöt on suunniteltu kestämään keskeytyksiä.

Palvelin ylläpitää pysyvää työ- ja pakettikohdetta.

Palautuksen aikana jo onnistuneita pakettikohteita ei suoriteta tarpeettomasti uudelleen.

Tämä tarjoaa tarkistuspisteitä muistuttavan suoritusmallin monipakettitoiminnoille.

Tavoite on:

* Palauta työ, äläkä käynnistä koko työtä sokeasti uudelleen.

Uudelleenkäynnistyksen tunnistus

Jotkin pakettitoiminnot voivat vaatia järjestelmän uudelleenkäynnistyksen.

Siksi LUMS käsittelee uudelleenkäynnistyksen tunnistuksen osana päivitystuloksen käsittelyä sen sijaan, että olettaisi onnistuneen paketinhallinnan lopetuksen aina tarkoittavan, että järjestelmä on täysin toimintakunnossa.

Asiakas raportoi havaitsemansa uudelleenkäynnistysvaatimuksen takaisin palvelimelle.
Asiakastodennus

Asiakasviestintä todennetaan asiakaskohtaisilla tunnisteilla.

Tunnisteet ovat:

* yksilöllisesti määritettyjä

* vaihdettavissa

* tallennettu palvelinpuolella vain SHA-256-tiivisteinä

* validoitu ennen asiakasraporttien hyväksymistä

Tunnisteen vaihto mahdollistaa ylläpitäjän mitätöidä aiemmin myönnetyn asiakastunnisteen luomatta asiakasta uudelleen.
Valvottavuus

Ylläpitoon ja turvallisuuteen liittyvät toiminnot tallennetaan LUMSin valvontalokijärjestelmän kautta.

Valvontajäljen on tarkoitus vastata:
text

Kuka?
Mitä?
Milloin?
Mitä kohdetta vastaan?
Millä tuloksella?

Tämä kattaa turvallisuuskriittiset toiminnot, kuten todennukseen liittyvät toimet, asiakashallinnan, käyttäjähallinnan ja päivitystöiden luomisen.
Suunnitteluperiaate

LUMS noudattaa yksinkertaista periaatetta:

* Tee Linux-päivitysten hallinnasta näkyvää, hallittua, palautettavaa ja valvottavaa – kuitenkaan piilottamatta alla olevia Linux-työkaluja.

Arkkitehtuuri

LUMS erottaa hallinnan, suorituksen ja pysyvyyden selkeästi määriteltyihin komponentteihin.

Palvelin vastaa orkestroinnista ja käytännöistä.

Asiakas vastaa paikallisesta järjestelmävuorovaikutuksesta.

Paketinhallinta vastaa edelleen ohjelmistojen asentamisesta, poistamisesta tai päivittämisestä.

Tämä erottelu on tarkoituksellinen.

```text
Browser
   │
   │ HTTPS
   ▼
┌──────────────────────────────────────────┐
│                LUMS Server                │
│                                          │
│  Web UI                                  │
│  Authentication / Sessions               │
│  RBAC                                    │
│  API                                     │
│  Client Management                       │
│  Package Search                          │
│  Update Job Management                   │
│  Audit Logging                            │
│  SQLite Persistence                       │
└───────────────────┬──────────────────────┘
                    │
                    │ HTTPS / Client API
                    ▼
┌──────────────────────────────────────────┐
│               LUMS Agent                  │
│                                          │
│  Authentication                          │
│  Inventory Reporting                     │
│  Update Detection                        │
│  Package Search                          │
│  Job Execution                           │
│  Result Reporting                        │
│  Reboot Detection                        │
│  Idle Detection                          │
└───────────────────┬──────────────────────┘
                    │
                    ▼
          ┌────────────────────┐
          │ Package Manager    │
          │                    │
          │ APT / dpkg         │
          │ pacman             │
          └────────────────────┘
```

Palvelinkomponentit

LUMS-palvelin tarjoaa keskitetyn hallintakerroksen.
Verkkosovellus

Verkkosovellus tarjoaa hallintakäyttöliittymän seuraaville:

* asiakashallinta

* ohjelmistoluettelointi

* päivitystiedot

* päivitystyöt

* paketinhallinta

* päivityshistoria

* käyttäjähallinta

* järjestelmän ylläpito

Käyttöliittymä noudattaa nykyisen käyttäjän RBAC-roolia.

Siksi käyttöliittymän näkyvyys mukautetaan käyttäjän oikeuksien mukaan, mutta valtuutus valvotaan aina myös palvelinpuolella.
### API

API yhdistää verkkokäyttöliittymän ja Linux-asiakkaat palvelinpuolen sovelluslogiikkaan.

Se käsittelee toimintoja, kuten:

* asiakasrekisteröinti ja -hallinta

* asiakasraportit

* pakettihaut

* pakettihakujen tulokset

* päivitystyöt

* työtulokset

* käyttäjähallinta

* valvontatapahtumat

API-päätepisteet validoivat syötteensä ennen tilaa muuttavia toimintoja.
Todennus ja istunnot

Ylläpitäjät todennetaan LUMS-verkkosovelluksen kautta.

Istunnot ovat palvelinohjattuja ja tukevat eksplisiittistä istunnon mitätöintiä.

Todennuksen turvallisuus sisältää:

* salasanan tiivistys Argon2:lla

* istunnonhallinta

* istunnon mitätöinti

* kirjautumisen nopeusrajoitus

* CSRF-suojaus

* roolipohjainen valtuutus

Asiakastodennus on erillään ylläpitäjätodennuksesta.
### RBAC

LUMS yhdistää roolimallit käyttäjäkohtaisiin oikeuksiin. Administrator-, Operator- ja Viewer-mallit tarjoavat aloitusoikeudet, joita voidaan mukauttaa jokaiselle tilille.

Valtuutus valvotaan palvelimella käyttäjän tallennettujen oikeuksien perusteella.

Käyttöliittymä piilottaa lisäksi toimintoja, joita käyttäjän oikeudet eivät salli.

Tämä tarkoittaa, että painikkeen piilottamista ei koskaan pidetä turvarajana.
SQLite-pysyvyys

LUMS käyttää SQLitea pysyvään sovellustilaan.

Tietokanta tallentaa tietoja, kuten:

* käyttäjät

* istunnot

* asiakkaat

* asiakastodennustila

* ohjelmistoluettelo

* saatavilla olevat päivitykset

* päivitystyöt

* pakettitason työtulokset

* pakettihakupyynnöt ja -tulokset

* valvontatiedot

Sovellus ottaa eksplisiittisesti käyttöön SQLite-viiteavainten valvonnan tietokantayhteyksille.

Nykyinen tuotannon SQLite-perustaso on:
```text

journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

LUMS käyttää SQLite WAL -tilaa nykyisessä tuotantokokoonpanossa.
Konttiarkkitehtuuri

LUMS-palvelin otetaan käyttöön kovennettuna Docker-konttina.

Sovelluskonttia kohdellaan tarkoituksella kertakäyttöisenä.

Pysyvä sovellustila tallennetaan erilliseen Docker-taltioon:

```text
lums-data
```

Tuotantokontti käyttää vain luku -juuritiedostojärjestelmää.

Kirjoitettavat sijainnit on tarkoituksella rajoitettu vaadittuihin ajonaikaisiin ja pysyviin tallennuspolkuihin.

Tuotannon turvallisuusperustaso sisältää:

```text
read-only root filesystem
all Linux capabilities dropped
no-new-privileges
restricted /tmp
restricted /run
read-only secret mount
dedicated persistent data volume
non-root application user
```

Sovellus on sisäisesti saatavilla osoitteessa:

```text
127.0.0.1:5050
```

Ulkoinen HTTPS-käyttö tarjotaan käänteisen välityspalvelimen kautta.
Pysyvät ja kertakäyttöiset komponentit

LUMS erottaa pysyvän tilan korvattavista ajonaikaisista komponenteista.
text

Pysyvä
├── SQLite-tietokanta
├── asiakastila
├── käyttäjätila
├── työtila
└── valvontatila

Kertakäyttöinen
├── Docker-kontti
├── sovellusprosessi
└── luotu ajonaikainen tila

Siksi sovelluskontin korvaaminen ei itsessään poista LUMS-tietokantaa.

Tämä erottelu on tärkeä päivityksille ja palautukselle.
Asiakasarkkitehtuuri

Linux-asiakas koostuu useista yhteistyötä tekevistä komponenteista.
LUMS-agentti

Agentti vastaa vuorovaikutuksesta LUMS-palvelimen ja paikallisen Linux-järjestelmän kanssa.

Nykyinen agenttiversio:

```text
1.7.0
```

Agentti käsittelee:

* todennus

* luettelointi

* päivitysten tunnistus

* pakettihaku

* pakettitoiminnot

* päivitystöiden suoritus

* tulosten raportointi

* uudelleenkäynnistyksen tunnistus

* lepotilan käsittely

Paketinhallintakerros

Paketinhallintakerros tarjoaa hallitun abstraktion natiivin Linux-paketinhallinnan ympärille.

Agentti ei vaadi LUMSia korvaamaan paketinhallintaa.

Sen sijaan:
```text

LUMS-toiminto
     │
     ▼
Paketinhallinnan abstraktio
     │
     ├── Debian / Ubuntu → APT / dpkg
     │
     └── Arch Linux      → pacman
```

Tämä pitää jakelukohtaisen pakettikäsittelyn asiakkaan sisällä.
Suorituksen valvoja

Valvoja seuraa päivitystöiden suoritusta asiakkaalla.

Nykyinen valvojan versio:

```text
1.2.1
```

Valvoja työskentelee yhdessä agentin ja palvelinpuolen työtilan kanssa.

Sen tarkoitus on varmistaa, että työt, joiden odotetaan suoritettavan, eivät jää loputtomasti käsittelemättä.
Raportointipolku

Normaali asiakasraportointi noudattaa tätä suuntaa:
text

Linux-asiakas
```text
    │
    │ luettelo / päivitystiedot
    ▼
LUMS API
    │
    ▼
SQLite
    │
    ▼
Web UI
```

Esimerkiksi asiakkaan suorittama päivitystarkistus tuottaa tiedot, jotka raportoidaan palvelimelle ja tallennetaan asiakkaan nykyiseksi päivitystilaksi.

Selain ei kysy suoraan asiakkaan paketinhallinnasta.
Pakettihaun polku

Pakettihaku noudattaa erilaista pyyntö/vastaus-virtaa:
text

Selain
```text
   │
   │ hakupyyntö
   ▼
LUMS-palvelin
   │
   │ pakettihakupyyntö
   ▼
Linux-asiakas
   │
   │ APT / pacman -haku
   ▼
Linux-asiakas
   │
   │ hakutulos
   ▼
LUMS-palvelin
   │
   ▼
```
Selain

Siksi palvelimen ei tarvitse ylläpitää täydellistä etäpakettivarastoindeksiä jokaiselle asiakkaalle.

Haku suoritetaan asiakkaan omalla paketinhallintaympäristöllä.
Päivityksen suorituspolku

Päivitystyö noudattaa yleistä arkkitehtuuria:
text

Selain
```text
   │
   │ luo työ
   ▼
LUMS API
   │
   │ validoi pyyntö
   ▼
SQLite
   │
   │ pysyvä työ
   ▼
Linux-asiakas
   │
   │ suorita toiminto
   ▼
APT / dpkg / pacman
   │
   │ tulos
   ▼
Linux-asiakas
   │
   │ validoitu tulos
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
```
Selain

Tämä luo LUMSin keskeisen suoritusketjun:

* Selain → API → SQLite → Agentti → Paketinhallinta → Tulos → SQLite → Käyttöliittymä

Atominen työn varaus

Päivitystyöt ovat pysyviä palvelinpuolen objekteja.

Ennen suoritusta agentin on saatava työ, joka on kelvollinen suoritettavaksi.

Työn varaus suoritetaan atomisesti, jotta sama odottava työ ei tule vahingossa useiden suorituspolkujen varaamaksi.

Tämä on erityisen tärkeää, kun mukana on ajastimia, uudelleenyrityksiä, palautusta tai useita asiakaspuolen prosesseja.
Työn suoritus

Palvelin luo jäsenneltyjä töitä.

Asiakasagentti tulkitsee tuetut työtoiminnot ja suorittaa vastaavan paikallisen toiminnon.

Tuetut pakettitoiminnot ovat:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Pakettinimet validoidaan ennen pakettityön luomista.

Agentti ei käsittele pakettinimiä mielivaltaisina komentotulkin osina.
Paketinhallinnan abstraktio

Pakettitoiminnot on tarkoituksella toteutettu paketinhallinnan abstraktion taakse.

Tämä pitää korkeamman tason LUMS-työmallin riippumattomana jakelukohtaisista komennoista.

Esimerkiksi:

```text
INSTALL_PACKAGE
       │
       ├── Debian / Ubuntu → APT
       │
       └── Arch Linux      → pacman
```

Sama periaate pätee poistamiseen ja pakettipäivityksiin.
## Debian / Ubuntu

Debian-perheen järjestelmissä LUMS käyttää natiivia APT/dpkg-työkaluja.

Tyypillisiä vastuita ovat:

* pakettihaku

* pakettimetatietojen haku

* paketin asennus

* paketin poisto

* pakettipäivitykset

* järjestelmäpäivitykset

* päivitysten tunnistus

LUMS-agentti ei korvaa APT:ta.

Se tarjoaa hallitun orkestroinnin sen ympärille.
## Arch Linux

Arch Linux -järjestelmissä LUMS käyttää natiivia pacman-paketinhallintaa.

Tyypillisiä vastuita ovat:

* pakettihaku

* pakettimetatietojen haku

* paketin asennus

* paketin poisto

* pakettipäivitykset

* järjestelmäpäivitykset

* päivitysten tunnistus

Jakelukohtainen käyttäytyminen pysyy paketinhallintakerroksen sisällä.
Pakettihaku

Pakettihaku on erillään asennettujen ohjelmistojen luettelosta.

Tämä ero on tärkeä:
```text

Asennetut ohjelmistot
        │
        └── Mitä on jo asennettu?

Paketinhallinnan haku
        │
```
  * └── Minkä paketin asiakas voi tällä hetkellä löytää?

Hakutulokset voivat sisältää pakettitietoja, kuten:

* paketin nimi

* versio

* kuvaus

* varastotiedot, jos saatavilla

Hakutulokset palautetaan LUMS-palvelimelle ja näytetään Paketinhallinta-käyttöliittymässä.
Paketinhallinnan oikeudet

Paketinhallinta on etuoikeutettu toiminto.

Nykyinen oikeusmalli on:
text

Administrator → sallittu
Operator      → sallittu
Viewer        → ei sallittu

Viewer voi silti tarkastella asennettuja ohjelmistoja.

Paketinhallinnan käyttöliittymä on piilotettu Viewereiltä, ja vastaavat palvelinpuolen mutaatiopäätepisteet valvovat valtuutusta itsenäisesti.
Päivitystuloksen käsittely

LUMS käsittelee päivitystoiminnon tuloksen jäsenneltynä tilana sen sijaan, että se yksinkertaisesti näyttäisi raakakomentojen tulosteen.

Olennaiset tiedot voivat sisältää:

* onnistuminen tai epäonnistuminen

* pakettitason tulos

* suoritustila

* virhetiedot

* uudelleenkäynnistysvaatimus

* valmistumisaikaleimat

Tämä mahdollistaa palvelimen ylläpitää merkityksellistä päivityshistoriaa.
Uudelleenkäynnistyksen tunnistus

Pakettitoimintojen jälkeen asiakas tarkistaa, viittaako toiminto uudelleenkäynnistyksen tarpeeseen.

Tulos raportoidaan palvelimelle osana työtulosta.

Uudelleenkäynnistysvaatimus pysyy siksi liitettynä päivitystoimintoon sen sijaan, että se katoaisi asiakaspuolen pääteistuntoon.
Asiakastodennuksen raja

Asiakas-API käyttää erillistä todennusmekanismia kuin ylläpitäjän verkkosessiot.
text

Ylläpitäjä
```text
        │
        ▼
 Verkkotodennus
        │
        ▼
    LUMS-palvelin

Linux-asiakas
        │
        ▼
 Asiakastunniste
        │
        ▼
```
* LUMS-palvelin

Tämä erottelu estää ylläpitäjän selainsessioiden ja asiakastunnisteiden muuttumisen keskenään vaihdettaviksi todennusmekanismeiksi.
Valvontajälki

Turvallisuuteen ja ylläpitoon liittyvät toiminnot tallennetaan palvelinpuolen valvontajärjestelmään.

Valvontajälki täydentää normaalia sovelluslokitusta.

Lokitus vastaa kysymyksiin sovelluksen käyttäytymisestä.

Valvontalokitus tallentaa lisäksi tärkeät ylläpitotoimenpiteet ja niiden kontekstin.

Tämä ero on hyödyllinen tutkittaessa asiakkaiden, käyttäjien, todennustilan tai päivitystöiden muutoksia.
Toimintaperiaate

LUMS erottaa tarkoituksella:
text

Hallinta
```text
     │
     ▼
Käytäntö / valtuutus
     │
     ▼
Työ
     │
     ▼
Asiakkaan suoritus
     │
     ▼
```
Natiivi paketinhallinta

Jokaisella kerroksella on määritelty vastuu.

Palvelin hallinnoi.

Agentti suorittaa.

Paketinhallinta tekee varsinaisen järjestelmämuutoksen.

Tulos kulkee takaisin saman hallitun ketjun kautta.
Roolipohjainen käyttöoikeushallinta

LUMS käyttää kolmea ylläpitoroolia:

```text
Administrator
Operator
Viewer
```

Valtuutus valvotaan palvelinpuolella.

Käyttöliittymä mukauttaa lisäksi näkyvää käyttöliittymää käyttäjän oikeuksien mukaan, mutta käyttöliittymän näkyvyyttä ei koskaan pidetä turvarajana.
### Administrator

Ylläpitäjillä on pääsy:

* tarkastella asiakkaita

* tarkastella asennettuja ohjelmistoja

* tarkastella saatavilla olevia päivityksiä

* luoda ja suorittaa päivitystöitä

* tarkastella päivityshistoriaa

* käyttää paketinhallintaa

* suorittaa järjestelmän ylläpitoa

* luoda ja poistaa asiakkaita käytöstä

* vaihtaa asiakastunnisteita

* luoda ja hallita käyttäjiä

* hallita rooleja ja käyttäjien käyttöoikeuksia

### Operator

Operaattoreilla on pääsy:

* tarkastella asiakkaita

* tarkastella asennettuja ohjelmistoja

* tarkastella saatavilla olevia päivityksiä

* luoda ja suorittaa päivitystöitä

* tarkastella päivityshistoriaa

* käyttää paketinhallintaa

* suorittaa järjestelmän ylläpitoa

Operaattoreilla ei ole pääsyä:

* käyttäjähallintaan

* roolien hallintaan

* asiakkaiden luomiseen tai poistamiseen käytöstä

* asiakastunnisteiden vaihtoon

### Viewer

Viewereillä on vain luku -pääsy:

* asiakkaisiin

* asennettuihin ohjelmistoihin

Seuraavat toiminnot eivät ole Viewereiden käytettävissä:

* saatavilla olevien päivitysten hallinta

* päivitystyöt

* päivityshistoria

* paketinhallinta

* järjestelmän ylläpito

* muut tilaa muuttavat ylläpitotoiminnot

Palvelin valvoo näitä rajoituksia itsenäisesti.
Käyttäjähallinta

LUMS tarjoaa käyttäjähallinnan tileille, joilla on users.manage-oikeus.

Käyttäjät, joilla on tämä oikeus, voivat luoda tilejä roolimallin avulla ja sitten määrittää oikeuksia yksilöllisesti tai soveltaa kyseistä mallia. Uudet tilit alkavat ilman oikeuksia; oikeuseditori avautuu luomisen jälkeen. Käyttäjähallinnoijat voivat myös tallentaa yksityisiä ylläpitomuistiinpanoja, jotka eivät näy tilin omistajalle.

Ylläpitäjät, joilla on backups.manage, voivat luoda validoituja .db- tai .db.gz-tietokantavarmuuskopioita palvelimen määrittämään hakemistoon ja valita turvallisen alikansion kyseisestä liitetystä sijainnista. Katso administration.md ja sovelluksen sisäinen Markdown-palautusopas Docker-tallennuksen asetuksia ja palautusta varten.

Käyttäjien salasanat tallennetaan Argon2-salasanatiivistyksellä eikä selkokielisenä tai palautuvasti salattuna.

Käyttäjähallinnan toiminnot on suojattu:

* todennuksella

* oikeuspohjaisella valtuutuksella

* CSRF-suojauksella

* syötteen validoinnilla

* päällekkäisten käyttäjien tarkistuksella

* valvontalokituksella

Käyttäjähallinnan käyttöliittymää ei paljasteta ilman users.manage-oikeutta.
Istunnon turvallisuus

Ylläpitäjätodennus käyttää palvelinpuolen istunnonhallintaa.

Istunnon turvallisuus sisältää:

* todennettu istuntotila

* istunnon mitätöinti

* CSRF-suojaus tilaa muuttaville pyynnöille

* kirjautumisen nopeusrajoitus

* poistettujen tilien valvonta

* roolitarkistukset

Istunnon mitätöinti mitätöi vastaavan todennetun tilan sen sijaan, että se vain piilottaisi käyttöliittymän.
Kirjautumisen nopeusrajoitus

Toistuvat epäonnistuneet kirjautumisyritykset ovat asteittaisen nopeusrajoituksen alaisia.

Nykyiset kynnysarvot ovat:
text

5 yritystä  → 30 sekuntia
6 yritystä  → 60 sekuntia
7 yritystä  → 120 sekuntia
8+ yritystä → 300 sekuntia

Asiaankuuluva tila tallennetaan SQLiteen.

Onnistunut todennus tyhjentää sovellettavan epäonnistumistilan.

Tämä estää pelkän sovelluksen uudelleenkäynnistyksen käytön kirjautumissuojan ohittamiseen.
Asiakastunnisteen turvallisuus

Jokaisella rekisteröidyllä asiakkaalla on oma todennustunnisteensa.

Palvelin tallentaa tunnisteen SHA-256-tiivisteenä.

Alkuperäistä tunnistetta ei tarvita normaaliin palvelinpuolen validointiin.

Tunnisteen vaihto mahdollistaa ylläpitäjien mitätöidä olemassa olevan tunnisteen ja myöntää korvaava.

Tämä luo selkeän elinkaaren:
text

Luo
```text
  │
  ▼
Käytä
  │
  ▼
Vaihda
  │
  ▼
```
Vanha tunniste mitätön

API-turvallisuus

LUMS validoi API-syötteen ennen tilaa muuttavia toimintoja.

Turvakontrollit sisältävät:

* todennus

* käyttäjäkohtainen oikeusvaltuutus

* CSRF-suojaus tarvittaessa

* syötteen validointi

* pakettinimien validointi

* jäsennellyt työtoiminnot

* parametroidut tietokantakyselyt

* hallittu virheenkäsittely

Sovellus ei käytä käyttäjän antamia pakettinimiä rajoittamattomina komentotulkkeina.
SQL-injektiosuojaus

Tietokantatoiminnot käyttävät parametroituja SQL-lauseita.

Käyttäjän hallitsemia arvoja ei yhdistetä suoraan SQL-kyselyihin.

Tämä koskee alueita, kuten:

* todennus

* asiakashallinta

* käyttäjähallinta

* pakettihaut

* päivitystyöt

* valvontatiedot

* tulosten raportointi

Tavoitteena on pitää data-arvot erillään SQL-ohjeista.
SQLite-turvallisuusperustaso

Nykyinen tuotannon SQLite-kokoonpano on:
```text

journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

Sovellus ottaa eksplisiittisesti käyttöön viiteavainten valvonnan tietokantayhteyksille.

Nykyinen kokoonpano käyttää WAL-tilaa.

Tietokanta tallennetaan pysyvään Docker-taltioon eikä kertakäyttöisen sovelluskontin tiedostojärjestelmään.
Töiden palautus ja tarkistuspisteet

LUMS käsittelee päivitystöitä pysyvinä tilakoneina.

Monipakettityö voi sisältää useita yksittäisiä pakettitoimintoja.

Jokainen pakettikohde voi saavuttaa oman tulos tilansa.

Jos suoritus keskeytyy, palautus voi erottaa:
text

jo onnistunut
  * │
  * └── älä toista tarpeettomasti

ei valmis
  * │
  * └── kelvollinen palautukseen

Tämä vähentää riskiä toistaa sokeasti suoritettuja pakettitoimintoja keskeytyksen jälkeen.
Hallittu päivityksen suoritus

LUMS rajoittaa tarkoituksella toimintoja, joita voidaan pyytää päivitystyö-API:n kautta.

Tuetut toiminnot ovat:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Palvelin validoi toiminnon ja asiaankuuluvat pakettitiedot ennen työn luomista.

Agentti sitten yhdistää jäsennellyn toiminnon asianmukaiseen paketinhallintatoimintoon.

Tämä estää päivitysjärjestelmän muuttumisen yleiseksi etäkomentojen suoritusmekanismiksi.
Pakettitoiminnot

Pakettitoiminnot suoritetaan asiakkaan natiivin paketinhallinnan kautta.
Asennus

Validoitu paketin nimi välitetään paketinhallinnan abstraktiolle asennusta varten.
Poisto

Validoitu paketin nimi välitetään paketinhallinnan abstraktiolle poistoa varten.
Pakettipäivitys

Tietty paketti voidaan päivittää, kun asiakas raportoi sen saatavilla olevaksi päivitykseksi.
Järjestelmäpäivitys

Järjestelmäpäivitystoiminto delegoi päivitysprosessin natiiville paketinhallinnalle.

Kaikki toiminnot palauttavat jäsenneltyjä tuloksia LUMS-palvelimelle.
Paketinhallinnan turvallisuus

LUMS kohtelee paketinhallintaa etuoikeutettuna paikallisena komponenttina.

Siksi agentti ei yritä jäljitellä paketinhallinnan käyttäytymistä itse.

Sen sijaan se:

* validoi pyydetyn toiminnon

* valitsee asianmukaisen paketinhallintatoteutuksen

* suorittaa hallitun toiminnon

* tallentaa tuloksen

* raportoi tuloksen palvelimelle

Jakelukohtainen käyttäytyminen pysyy eristettynä paketinhallintakerroksen sisällä.
Uudelleenkäynnistyksen käsittely

Jotkin pakettitoiminnot voivat vaatia uudelleenkäynnistyksen.

LUMS tallentaa uudelleenkäynnistysvaatimukset osana päivitystyön tuloksia.

Tämä mahdollistaa ylläpitäjien erottaa:
text

Päivitys valmis

ja:
text

Päivitys valmis
Uudelleenkäynnistys vaaditaan

Uudelleenkäynnistysvaatimus on siksi osa toimintatilaa sen sijaan, että sitä kohdeltaisiin erillisenä ilmoituksena.
Valvontalokitus

LUMS ylläpitää sovelluksen valvontajälkeä tärkeistä ylläpitoon ja turvallisuuteen liittyvistä toiminnoista.

Esimerkkejä ovat:

* todennukseen liittyvät tapahtumat

* asiakashallinta

* tunnistetoiminnot

* käyttäjähallinta

* päivitystöiden luonti

* turvallisuuskriittiset tilamuutokset

Valvontalokitus on erillään tavallisesta diagnostiikkalokituksesta.

Diagnostiikkalokit auttavat sovelluksen vianmäärityksessä.

Valvontatietueet tarjoavat hallinnollisen historian relevanteista toiminnoista.
Turvallisuuden koventaminen

Nykyinen käyttöönotto sisältää useita koventamistasoja.
Kontin koventaminen

Tuotantokontti käyttää:

* ei-root-sovelluksen suoritus

* vain luku -juuritiedostojärjestelmä

* poistetut Linux-kyvykkyydet

* no-new-privileges

* rajoitetut väliaikaiset tiedostojärjestelmät

* vain luku -salaisuuden liitos

* erillinen pysyvä datataltio

Verkon koventaminen

Sovelluskontti on sidottu isäntäkoneen loopback-osoitteeseen:

```text
127.0.0.1:5050
```

Siksi sovellusporttia ei ole suoraan altistettu LAN-palveluna.

Ulkoinen käyttö hoidetaan HTTPS-käänteisvälityspalvelimen kautta.

Palomuuri ei altista sisäistä sovellusporttia.
Kuljetuksen turvallisuus

Ylläpitäjän pääsy tarjotaan HTTPS:n kautta.

Käänteisvälityspalvelin hoitaa ulkoisen TLS-päättämisen.

HTTP-pyynnöt ohjataan HTTPS:ään.
Salaisuudet ja kokoonpano

Arkaluonteiset ajonaikaiset tunnistetiedot pidetään sovelluksen lähdekoodipuun ulkopuolella.

Tuotantosalaisuus liitetään konttiin vain luku -salaisuustiedostona.

Arkiston ja Docker-koontikontekstin säännöt estävät yleisten varmuuskopio-, salaisuus-, tietokanta- ja varmenneartefaktien tahattoman pääsyn kuvakoontikontekstiin.
Riippuvuuksien ja koontien turvallisuus

Tuotannon Python-riippuvuudet on kiinnitetty.

Tuotannon Python-peruskuva on kiinnitetty tiivisteellä.

Docker-koontikonteksti on rajoitettu .dockerignore-tiedoston kautta.

Nämä kontrollit parantavat koontien toistettavuutta ja vähentävät arkaluonteisten tiedostojen tahatonta sisällyttämistä.
Turvallisuustarkastuksen tila

LUMSin turvallisuuskatsaus on kattanut seuraavat alueet:

* SQLite-viiteavainten valvonta

* SQLite-ajonaikainen kokoonpano

* päivityksen aikakatkaisu ja prosessien käsittely

* kirjautumisen nopeusrajoitus

* API-syötteen validointi

* istunnon mitätöinti

* asiakastunnisteen vaihto

* offline/IP-käsittely

* töiden palautus ja tarkistuspisteet

* APT-robustisuus

* Arch-uudelleenkäynnistyksen tunnistus

* yksikkö- ja API-tulosten validointi

* simulaatiotestaus

* jatkuva integraatio

* sovellus- ja valvontalokitus

* versiointi ja julkaisujen käsittely

* RBAC

* istunto- ja CSRF-turvallisuus

* tunnistetietojen turvallisuus

* riippuvuuksien ja koontien turvallisuus

* Docker-/kontin koventaminen

* salaisuuksien ja koontikontekstin suojaus

* HTTP-/kuljetuksen turvallisuus

* tiedostojärjestelmän/ajonaikaiset oikeudet

* verkon altistuminen

* arkiston artefaktihygienia

Jäljellä oleva dokumentaation tarkistus käsitellään erikseen osana lopullista julkaisukelpoisuusprosessia.
Testaus ja CI

LUMS sisältää automatisoidut testit, jotka kattavat sovelluksen ydin käyttäytymisen ja turvakontrollit.

Suorita täydellinen testisarja arkiston juuresta:
```bash

./.venv-test/bin/pytest -q
```

Testien määrä muuttuu ajan myötä. Vaadittu tulos on, että koko sarja päättyy onnistuneesti ilman epäonnistumisia. Testisarja kattaa alueita, kuten:

* todennus

* RBAC

* asiakashallinta

* käyttäjähallinta

* pakettihaku

* päivitystyöt

* työtulosten validointi

* turvallisuuskäyttäytyminen

* API-käyttäytyminen

Jatkuva integraatio suorittaa automatisoidun testisarjan ennen kuin muutokset katsotaan valmiiksi.

Onnistunut testiajo vaaditaan, mutta testit ovat vain yksi osa julkaisuprosessia.

Julkaisuprosessi vaatii myös:
```text

Toteutus
    ↓
Turvallisuuskatsaus
    ↓
Dokumentaation tarkistus
    ↓
Täydellinen testisarja
    ↓
CI
    ↓
Versio
    ↓
Git-tunniste
    ↓
```
GitHub-julkaisu

Kehityksen tila

LUMS on tällä hetkellä aktiivisessa kehityksessä.

Ydin hallinta-arkkitehtuuri, asiakassuoritusmalli, paketinhallinta, RBAC, turvallisuuden koventaminen ja palautusmekanismit on toteutettu.

Projektia ei tarkoituksella pidetä valmiina julkaisuna vain siksi, että sovellus on toimiva.

Julkaisuvalmius edellyttää myös, että ympäröivä dokumentaatio ja toimintamenettelyt kuvaavat samaa nykyistä järjestelmää.

Siksi dokumentaation johdonmukaisuutta pidetään osana suunnitteluprosessia eikä jälkikäteen lisättävänä asiana.
Tuetut järjestelmät

LUMS on suunniteltu hallitsemaan Linux-järjestelmiä, jotka käyttävät tuettuja natiiveja paketinhallintoja.
### Debian / Ubuntu

Tuetut paketinhallintapinot:

```text
APT
dpkg
```

Asiakas käyttää natiiveja Debian-paketinhallintatyökaluja seuraaviin:

* pakettiluettelo

* päivitysten tunnistus

* pakettihaku

* paketin asennus

* paketin poisto

* pakettipäivitykset

* järjestelmäpäivitykset

### Arch Linux

Tuetut paketinhallintapinot:

```text
pacman
```

Asiakas käyttää natiiveja Arch-paketinhallintatyökaluja seuraaviin:

* pakettiluettelo

* päivitysten tunnistus

* pakettihaku

* paketin asennus

* paketin poisto

* pakettipäivitykset

* järjestelmäpäivitykset

Asiakasvaatimukset

Hallinnoitu Linux-asiakas vaatii:

* tuetun Linux-jakelun

* LUMS-agentin

* verkkoyhteyden LUMS-palvelimeen

* rekisteröidyn asiakastunnisteen

* toimivan natiivin paketinhallinnan

* systemd:n ajastin-/palvelupohjaisille suorituskomponenteille

Asiakas ei vaadi, että LUMS-palvelin pääsee suoraan sen pakettitietokantaan.

Asiakas suorittaa paikalliset pakettitoiminnot ja raportoi tulokset palvelimelle.
Teknologiapino
Palvelin

* Python

* Flask

* Gunicorn

* SQLite

* HTML

* CSS

* JavaScript

* Nginx

* Docker

Todennus ja turvallisuus

* Argon2-salasanatiivistys

* palvelinpuolen istunnot

* CSRF-suojaus

* roolimallit käyttäjäkohtaisilla oikeuksilla

* SHA-256-asiakastunnisteiden tiivisteet

* HTTPS

* valvontalokitus

Asiakas

* Python

* systemd

* APT / dpkg

* pacman

* loginctl, jos lepotilatiedot ovat saatavilla

Projektin rakenne

Arkisto on organisoitu erillisiin palvelin-, asiakas-, frontend- ja testikomponentteihin.

Yksinkertaistettu rakenne on:

```text id="1rq7v7"
LUMS/
├── agent/
│   ├── agent.py
│   └── package_manager.py
│
├── server/
│   ├── app.py
│   ├── migrations/
│   ├── static/
│   ├── templates/
│   └── ...
│
├── tests/
│   ├── test_rbac.py
│   ├── test_package_search.py
│   ├── test_job_result.py
│   └── ...
│
├── Dockerfile
├── docker-entrypoint.sh
├── .dockerignore
├── .gitignore
└── documentation
```

Arkiston tarkka asettelu voi kehittyä LUMSin kehittyessä.

Arkkitehtoninen erottelu palvelimen, agentin, paketinhallinnan abstraktion, frontendin ja testien välillä on tarkoituksellinen.
Palvelinsovellus

Flask-sovellus tarjoaa keskitetyn LUMS-API:n ja verkkokäyttöliittymän.

Sen vastuisiin kuuluvat:

* todennus

* valtuutus

* istunnon käsittely

* asiakashallinta

* käyttäjähallinta

* ohjelmistoluettelo

* päivitysluettelo

* pakettihaku

* päivitystyöt

* työtulosten käsittely

* valvontalokitus

* tietokannan pysyvyys

Sovellus tarjoillaan Gunicornilla kontin sisällä.

Nginx tarjoaa ulkoisen HTTPS-sisääntulopisteen.
Agentti

LUMS-agentti asennetaan suoraan hallinnoituihin Linux-asiakkaisiin.

Nykyinen agenttiversio:

```text id="w8p4wz"
1.7.0
```

Agentti vastaa LUMSin suoritusketjun asiakaspuolen osasta.

Sen vastuisiin kuuluvat:

* asiakastilan raportointi

* asennettujen ohjelmistojen kerääminen

* saatavilla olevien päivitysten tunnistus

* pakettien haku

* pakettitoimintojen suoritus

* työtulosten raportointi

* uudelleenkäynnistysvaatimusten tunnistus

* lepotilatietojen käsittely

* osallistuminen töiden palautukseen

Agentti ei tarjoa rajoittamatonta etäkomentotulkia.
Paketinhallintakerros

Paketinhallinnan toteutus eristää jakelukohtaisen käyttäytymisen agentin muusta osasta.

Käsitteellisesti:
text

Agentti
```text id="zq8xq3"
  │
  ▼
Paketinhallintaliittymä
  │
  ├── Debian / Ubuntu
  │      └── APT / dpkg
  │
  └── Arch Linux
         └── pacman
```

Tämä mahdollistaa korkeamman tason päivitystyöjärjestelmän työskennellä jäsenneltyjen toimintojen kanssa tietämättä jokaista jakelukohtaista komentoa.
Valvoja

LUMSin suorituksen valvoja seuraa töitä, joiden odotetaan suoritettavan asiakkaalla.

Nykyinen valvojan versio:

```text id="7k6w3s"
1.2.1
```

Valvoja toimii yhdessä agentin ja palvelinpuolen työtilan kanssa.

Tämä arkkitehtuuri mahdollistaa LUMSin havaita suoritustilanteita, joissa työ jää odottamaan tai vaatii muuten huomiota.
systemd-integraatio

Asiakas käyttää systemd:tä ajastettuun ja hallittuun suoritukseen.

Asiaankuuluvat komponentit sisältävät palvelu- ja ajastinyksiköt seuraaviin:

* asiakasraportointi

* päivitysten tunnistus

* työn suoritus/valvonta

Tämä tarjoaa ennustettavan suorituksen ilman, että jokainen säännöllinen toiminto vaatii jatkuvasti käynnissä olevaa taustaprosessia.

Asiakasagentti voidaan myös suorittaa manuaalisesti asennuksen ja vianmäärityksen aikana.
Lepotilatietoinen suoritus

Lepotilatietoinen suoritus on suunniteltu vähentämään häiriöitä aktiivisille käyttäjille.

Nykyinen lepotilan kynnysarvo on:
text

300 sekuntia

Asiakas määrittää lepotilan käytettävissä olevien paikallisten istuntotietojen avulla.

Tuettaessa käytetään loginctl:ää.

Agentti erottaa:
text

vahvistettu lepotila
aktiivinen
lepotila ei saatavilla

Lepotilaa, joka ei ole saatavilla, ei tulkita hiljaisesti lepotilaksi.

Tämä tekee suorituspäätöksestä eksplisiittisen ja diagnosoitavan.
Päivitystyön elinkaari

Päivitystyön täydellinen elinkaari voidaan esittää seuraavasti:
text

Luo
```text id="h4d9kv"
  │
  ▼
Validoi
  │
  ▼
Tallenna
  │
  ▼
Varaa
  │
  ▼
Suorita
  │
  ├──────────────► ONNISTUI
  │
  ├──────────────► EPÄONNISTUI
  │
  └──────────────► PALAUTUS
                         │
                         ▼
```
        * Suorita

Työ tallennetaan ennen suoritusta.

Tämä tarkoittaa, että palvelin säilyttää tiedon aiotusta toiminnosta, vaikka asiakas tai sovellus keskeytyisi.
Tyypit

LUMS tukee tällä hetkellä jäsenneltyjä päivitystoimintoja, mukaan lukien:

```text id="v7r1f8"
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Nämä toiminnot on tarkoituksella rajoitettu.

LUMS on päivitysten hallintajärjestelmä, ei yleiskäyttöinen etäkomentokehys.
Pakettitason työtila

Useita paketteja sisältävät työt voivat seurata pakettitason edistymistä.

Esimerkiksi:
text

Työ #42

package-a → ONNISTUI
package-b → ONNISTUI
package-c → EPÄONNISTUI
package-d → ODOTTAA

Siksi palautus voi toimia työn keskeneräisissä osissa sen sijaan, että se toistaisi sokeasti onnistuneita pakettitoimintoja.
Töiden palautus

Palautus on suunniteltu pysyvien tarkistuspisteiden ympärille.

Palvelin ylläpitää työtilaa.

Asiakas raportoi pakettitason tulokset.

Jos suoritus keskeytyy, palvelin voi määrittää, mikä työ on jo suoritettu ja mikä työ on edelleen kelvollinen palautukseen.

Aiottu palautusperiaate on:

* Jatka tunnetusta tilasta sen sijaan, että olettaisit, ettei mitään tapahtunut.

Tulosten validointi

Asiakastyötulokset validoidaan ennen kuin ne hyväksytään pysyvään palvelintilaan.

Tämä suojaa työtilaa virheellisiltä tai puutteellisilta tuloslähetyksiltä.

Validointia sovelletaan asiaankuuluviin kenttiin, kuten:

* työn identiteetti

* suoritustila

* pakettituloksen tiedot

* virhetiedot

* uudelleenkäynnistystiedot

Tulostenkäsittelykerros toimii siksi toisena rajana todennetun asiakkaan ja pysyvän palvelintilan välillä.
Käyttäjähallinta

Käyttäjähallinta vaatii users.manage-oikeuden.

Valtuutetut käyttäjät voivat luoda käyttäjiä roolimallista ja mukauttaa kullekin tilille määritettyjä yksittäisiä oikeuksia.

Nykyiset roolit ovat:

```text id="2xqv79"
Administrator
Operator
Viewer
```

Käyttäjähallinnan toiminnot todennetaan, oikeustarkistetaan, validoidaan, suojataan CSRF:ltä tarvittaessa ja tallennetaan valvontajälkeen.
Asiakashallinta

Ylläpitäjät voivat hallita rekisteröityjä asiakkaita.

Asiakashallinnan toiminnot sisältävät:

* rekisteröinti

* käytöstä poisto

* tunnisteen vaihto

* asiakastilan tarkastus

Asiakastodennus on riippumaton jokaiselle rekisteröidylle asiakkaalle.

Asiakkaan poistaminen käytöstä estää sitä jatkamasta normaalia todennettua viestintää palvelimen kanssa.
Päivityshistoria

LUMS ylläpitää pysyvää päivitystyötilaa, jotta suoritetut ja epäonnistuneet toiminnot pysyvät näkyvinä suorituksen jälkeen.

Valtuutetut käyttäjät voivat tarkastella päivitystoimintojen historiaa roolinsa mukaisesti.

Historian on tarkoitus tarjota toiminnallista kontekstia eikä vain näyttää viimeisintä pakettiluetteloa.
Valvottavuus

LUMS ylläpitää kahta toisiinsa liittyvää mutta erillistä toiminnallisen tiedon muotoa:
Sovelluslokit

Käytetään ensisijaisesti:

* diagnostiikka

* virheet

* ajonaikainen käyttäytyminen

* vianmääritys

Valvontalokit

Käytetään ensisijaisesti:

* ylläpitotoimenpiteet

* turvallisuuteen liittyvät tapahtumat

* tärkeän tilan muutokset

* vastuuvelvollisuus

Näiden käsitteiden erottaminen toisistaan helpottaa vianmääritystä ja hallinnollista tarkastelua.
Testausstrategia

LUMSin testisarja kattaa sovelluksen useita kerroksia.
Todennus

Testit kattavat todennuskäyttäytymisen, istunnon käsittelyn ja turvakontrollit.
### RBAC

Testit varmistavat, että:

* Ylläpitäjät voivat suorittaa ylläpitotoimenpiteitä

* Operaattorit saavat sallitut hallintatoimintonsa

* Viewerit pysyvät vain luku -tilassa

Paketinhallinta

Testit kattavat pakettihaun käyttäytymisen ja paketinhallintaan liittyvän API-käsittelyn.
Päivitystyöt

Testit kattavat:

* työn luonti

* validointi

* tilasiirtymät

* tulosten käsittely

* palautuskäyttäytyminen

Turvallisuus

Testit kattavat turvallisuuskriittisen sovelluskäyttäytymisen ja regressiotapaukset.
Täydellinen sarja

Suorita täydellinen testisarja arkiston juuresta:
```bash

./.venv-test/bin/pytest -q
```

Testien määrä muuttuu projektin kehittyessä; luota komennon tulokseen, ei tässä asiakirjassa tulostettuun kiinteään määrään.
Jatkuva integraatio

Projekti käyttää jatkuvaa integraatiota automaattisten tarkistusten suorittamiseen muutoksille.

CI-putki auttaa havaitsemaan regressiot ennen kuin muutokset katsotaan julkaisuvalmiiksi.

Kehitystyönkulku on siksi:
text

Muutos
```text id="v3n9k8"
  ↓
Testi
  ↓
Turvallisuuskatsaus
  ↓
Dokumentaation tarkistus
  ↓
CI
  ↓
```
Julkaisun valmistelu

Onnistunut CI-ajo ei korvaa manuaalista turvallisuus- tai dokumentaatiokatsausta.
Dokumentaatio

LUMS ylläpitää erillistä dokumentaatiota eri toiminnallisille alueille.
### README.md

Projektin yleiskatsaus, arkkitehtuuri, ominaisuudet, turvallisuusperustaso, kehityksen tila ja projektin suunta.
### install.md

Asennus, käyttöönotto, asiakasasetukset, validointi, päivitys ja poistomenettelyt.
### administration.md

Rutiininomainen ylläpito, huolto, varmuuskopiot, päivitykset, toimintamenettelyt ja hätätilanteiden hallinta.
### security.md

Turvallisuusarkkitehtuuri, turvakontrollit, tarkastushavainnot, koventaminen ja julkaisuvalmiuden turvallisuustiedot.
### troubleshooting.md

Diagnostiikkamenettelyt palvelimen, asiakkaan, töiden, paketinhallinnan, todennuksen, tietokannan, kontin ja verkon ongelmiin.
### LUMS_Optional_Theme_System.md

Arkkitehtuuri- ja ylläpito-opas valinnaisille LUMS-frontend-teemoille.

Dokumentaatio on tarkoituksella erotettu vastuualueittain, jotta toimintaohjeet eivät sekoitu turvallisuussuunnitteluun tai visuaaliseen mukauttamiseen.
Dokumentaatioperiaate

Dokumentaatiota pidetään osana järjestelmää.

Ominaisuutta ei pidetä täysin valmiina, kun koodi toimii mutta dokumentaatio kuvaa edelleen vanhempaa arkkitehtuuria.

Aiottu suhde on:
text

Toteutus
```text id="0m1m5u"
      │
      ├── Testit
      ├── Turvallisuuskatsaus
      └── Dokumentaatio
               │
               ▼
```
  * Julkaisuvalmis

Tämä on erityisen tärkeää turvallisuuskriittisissä käyttöönotto- ja hallintamenettelyissä.
Nykyinen tila

LUMS on aktiivisesti kehitetty Linux-päivitysten hallintapalvelin.

Nykyinen toteutus sisältää:

* keskitetty asiakashallinta

* ohjelmistoluettelo

* päivitysten tunnistus

* pakettihaku

* paketin asennus ja poisto

* pakettikohtaiset päivitykset

* järjestelmäpäivitykset

* pysyvät päivitystyöt

* pakettitason työtila

* töiden palautus

* uudelleenkäynnistyksen tunnistus

* lepotilatietoinen suoritus

* asiakastunnistetodennus

* tunnisteen vaihto

* ylläpitäjätodennus

* roolipohjainen käyttöoikeushallinta

* käyttäjähallinta

* valvontalokitus

* kontin koventaminen

* HTTPS-kuljetus

* automatisoitu testaus

* jatkuva integraatio

Projekti on tällä hetkellä viimeisessä dokumentaatio- ja julkaisuvalmiusvaiheessa.
Turvallisuuden tila

Tärkeimmät turvallisuuskatsauksen alueet on toteutettu ja katsastettu.

Nykyinen turvallisuusperustaso sisältää:
```text

Todennus
    ├── Argon2-salasanatiivistys
    ├── istunnon käsittely
    ├── istunnon mitätöinti
    └── kirjautumisen nopeusrajoitus

Valtuutus
    ├── Administrator
    ├── Operator
    └── Viewer

Asiakasturvallisuus
    ├── asiakaskohtaiset tunnisteet
    ├── SHA-256-tunnistetiivisteet
    └── tunnisteen vaihto

API-turvallisuus
    ├── syötteen validointi
    ├── CSRF-suojaus
    ├── RBAC-valvonta
    └── parametroitu SQL

Ajonaikainen turvallisuus
    ├── ei-root-kontti
    ├── vain luku -juuritiedostojärjestelmä
    ├── poistetut kyvykkyydet
    ├── no-new-privileges
    ├── rajoitetut väliaikaiset tiedostojärjestelmät
    └── suojattu salaisuuden liitos

Verkon turvallisuus
    ├── HTTPS
```
* ├── käänteisvälityspalvelin
* ├── sovelluksen loopback-sidonta
* └── palomuurirajoitukset

Turvallisuutta pidetään jatkuvana suunnitteluvastuuna eikä kertaluonteisena tarkistuslistana.
Julkaisun tila

LUMS ei tällä hetkellä väitä olevansa vakaa tuotantojulkaisuversio.

Tällä hetkellä ei ole:

* lopullista semanttista versiota

* vakaata julkaisutunnistetta

* GitHub-julkaisua

Projekti noudattaa tarkoituksella julkaisujärjestystä:
text

Toteutus
```text id="f3c4y9"
      ↓
Turvallisuuskatsaus
      ↓
Dokumentaation tarkistus
      ↓
Täydellinen testisarja
      ↓
CI
      ↓
Version määritys
      ↓
Git-tunniste
      ↓
```
GitHub-julkaisu

Ensimmäinen virallinen julkaisu tulisi luoda vasta, kun nykyinen toteutus, turvallisuuskatsaus, dokumentaatio ja regressiotestaus on katsottu valmiiksi.
Tiekartta

Tiekartta keskittyy tarkoituksella vakauteen ja ylläpidettävyyteen sen sijaan, että lisättäisiin ominaisuuksia ilman olemassa olevan perustan viimeistelyä.
Nykyinen vaihe

* suorita dokumentaation tarkistus loppuun

* poista jäljellä olevat dokumentaation epäjohdonmukaisuudet

* sulje dokumentaation tarkastustyö

* suorita lopullinen täydellinen testiajo

* varmista CI

* valmistele julkaisuversio

* luo ensimmäinen virallinen Git-tunniste

* julkaise ensimmäinen GitHub-julkaisu

Tuleva kehitys

Mahdollinen tuleva työ voi sisältää:

* lisää Linux-jakeluja

* lisää paketinhallinnan taustajärjestelmiä

* käyttöliittymän parannuksia

* lisää raportointiominaisuuksia

* laajennettua toiminnan automatisointia

* lisää turvakontrolleja

* lisää testikattavuutta

Tulevien ominaisuuksien tulisi säilyttää olemassa olevat arkkitehtoniset rajat.
Mitä LUMS ei ole

LUMS ei ole tarkoituksella suunniteltu:

* yleiskäyttöiseksi etäkomentotulkiksi

* APT:n, dpkg:n tai pacmanin korvaajaksi

* täydelliseksi konfiguraationhallintaympäristöksi

* päätepisteiden hallintaratkaisuksi kaikille käyttöjärjestelmille

* vain pilvipalveluksi

* hallitsemattomaksi komennon suorituskehykseksi

LUMS keskittyy kapeampaan ongelmaan:

* Hallittu Linux-ohjelmistojen ja päivitysten hallinta, jossa on pysyvä tila ja valvottavuus.

Kehitysfilosofia

LUMS noudattaa yksinkertaista kehityssykliä:
text

Rakenna
```text id="8a0mve"
  ↓
Testaa
  ↓
Turvaa
  ↓
```
Dokumentoi

Ominaisuutta ei pidetä valmiina vain siksi, että se toimii kehittäjäympäristössä.

Sen tulisi myös olla:

* testattu

* turvallisuuskatsastettu

* dokumentoitu

* toistettavissa

* ymmärrettävä

* palautettavissa tarvittaessa

Muutosfilosofia

Muutokset tulisi tehdä harkitusti.

Tyypillisen muutoksen tulisi vastata:

* Minkä ongelman tämä ratkaisee?

* Minkä komponentin tulisi omistaa muutos?

* Vaikuttaako muutos turvallisuuteen?

* Vaikuttaako se pysyvään tilaan?

* Vaikuttaako se asiakkaisiin?

* Vaatiiko se dokumentaatiomuutoksia?

* Mitkä testit osoittavat, että olemassa oleva toiminnallisuus toimii edelleen?

Tämä vähentää riskiä korjata järjestelmän yksi osa samalla kun toinen osa rikkoutuu hiljaisesti.
Kehitystyönkulku

Ensisijainen kehitystyönkulku on:
text

Ymmärrä
```text id="r8u6o1"
   ↓
Toteuta
   ↓
Testaa
   ↓
Tarkasta
   ↓
Koveta
   ↓
Dokumentoi
   ↓
```
Regressiotesti

Turvallisuuskriittiset muutokset saavat lisävarmennuksen ennen kuin ne katsotaan valmiiksi.
Arkisto

Projektin arkisto sijaitsee GitHubissa:

NovaForgeCtrl/LUMS

Arkisto sisältää sovelluksen lähdekoodin, asiakaskomponentit, testit, konttikokoonpanon ja projektidokumentaation.
Dokumentaatiosarja

Nykyinen dokumentaatiosarja koostuu:

```text id="0xw7cy"
README.md
install.md
administration.md
security.md
troubleshooting.md
LUMS_Optional_Theme_System.md
```

Jokaisella asiakirjalla on määritelty tarkoitus.

README tarjoaa projektitason yleiskatsauksen.

Asennusopas selittää käyttöönoton.

Hallintaopas selittää jatkuvan toiminnan.

Turvallisuusopas dokumentoi turvallisuusarkkitehtuurin ja tarkastuksen tilan.

Vianmääritysopas tarjoaa diagnostiikkamenettelyt.

Valinnaisten teemojen asiakirja kattaa frontend-teemojen arkkitehtuurin.
Lisenssi

LUMS on julkaistu MIT-lisenssillä.

Lisenssin tarkoitus on pitää projekti avoimena ja saavutettavana samalla kun se sallii käytön, muokkaamisen ja uudelleenjakelun lisenssin ehtojen mukaisesti.

Katso arkiston lisenssitiedostosta täydellinen oikeudellinen teksti.
Yhteisö ja panokset

LUMS on avoimen lähdekoodin projekti ja panokset ovat tervetulleita.

Hyödyllisiä panoksia voivat olla:

* virheraportit

* turvallisuusraportit

* dokumentaation parannukset

* testit

* paketinhallinnan tuki

* frontend-parannukset

* backend-parannukset

* käyttöönoton parannukset

Panosten tulisi säilyttää projektin arkkitehtoniset ja turvallisuusperiaatteet.
Turvallisuusraportit

Turvallisuusongelmia ei tulisi käsitellä tavallisina ominaisuuspyyntöinä.

Kun raportoit turvallisuusongelmasta, anna riittävät tiedot ongelman toistamiseksi ja ymmärtämiseksi ilman tarpeetonta arkaluonteisten tietojen paljastamista.

Turvallisuuteen liittyvät muutokset tulisi katsastaa huolellisesti ennen yhdistämistä.
Projektin identiteetti

LUMS on rakennettu yksinkertaisen idean ympärille:

* Linux-päivitysten hallinta ilman turhaa kohinaa.

Projekti ei yritä piilottaa monimutkaisuutta teeskentelemällä, että Linux-paketinhallinta on yksinkertaista.

Sen sijaan se tekee olennaisen tilan näkyväksi:
text

Mitä on asennettu?
  * ↓
Mitä voidaan päivittää?
  * ↓
Mitä pitäisi muuttaa?
  * ↓
Kuka sen pyysi?
  * ↓
Mitä todella tapahtui?
  * ↓
Mikä tila jää jäljelle?

Nämä tiedot ovat hallitun päivitysten hallinnan perusta.
Lopullinen arkkitehtuuri

Korkeimmalla tasollaan LUMS voidaan ymmärtää viitenä kerroksena:

```text id="7b4p6n"
┌───────────────────────────────────────────────┐
│                    UI                         │
│       Ihmisen vuorovaikutus ja näkyvyys       │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    API                        │
│    Todennus, valtuutus, validointi            │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                  Pysyvyys                     │
│       Työt, asiakkaat, käyttäjät, tulokset,   │
│       valvonta                                │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    Agentti                    │
│      Paikallinen suoritus ja järjestelmän     │
│      raportointi                              │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│              Natiivit Linux-työkalut          │
│              APT / dpkg / pacman              │
└───────────────────────────────────────────────┘
```

Jokaisella kerroksella on erityinen vastuu.

Käyttöliittymä tarjoaa vuorovaikutuksen.

API valvoo käytäntöä.

SQLite tarjoaa pysyvän tilan.

Agentti suorittaa hallitun asiakaspuolen suorituksen.

Natiivi paketinhallinta tekee varsinaisen järjestelmämuutoksen.
Lopullinen periaate

LUMS on rakennettu yhden keskeisen periaatteen ympärille:

* Havaitse järjestelmä. Hallitse muutosta. Kirjaa tulos.

Tämä periaate pätee ohjelmistoarkkitehtuuriin, päivitysten suoritukseen, turvallisuusmalliin, palautusmekanismeihin ja dokumentaatioon.

Linux-päivitysten hallinta ilman turhaa kohinaa.
