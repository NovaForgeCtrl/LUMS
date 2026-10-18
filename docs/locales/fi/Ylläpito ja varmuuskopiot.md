# LUMS — Hallintaopas

> **Linux-päivitysten hallinta ilman turhaa kohinaa.**

Tämä opas kuvaa LUMSin päivittäistä hallintaa ja toimintaa palvelimen ja asiakkaiden asentamisen jälkeen.

Se keskittyy LUMSin verkkokäyttöliittymän kautta suoritettaviin hallintatehtäviin sekä LUMS-palvelimen ja hallinnoitujen asiakkaiden hallittuihin operatiivisiin tehtäviin.

Asennusmenettelyt on dokumentoitu erikseen tiedostossa `install.md`.

Vianmääritysmenettelyt on dokumentoitu erikseen tiedostossa `troubleshooting.md`.

Turvallisuusarkkitehtuuri ja tarkastustiedot on dokumentoitu erikseen tiedostossa `security.md`.

---

## Aloittaminen: Päivittäinen hallinta

Tämä opas on tarkoitettu henkilölle, joka vastaa olemassa olevasta LUMS-asennuksesta.
Yksityiskohtaiset tekniset osiot ylläpidetään englanniksi. Aloita näistä termeistä:

* **Käyttäjätili:** määrittää, mitä henkilö voi tehdä LUMSin verkkokäyttöliittymässä.
  Älä jaa tilejä; anna jokaiselle henkilölle oma tili.
* **Asiakas:** hallinnoitu Linux-tietokone. Sen asiakastunniste on salaisuus, eikä se ole
  sama kuin verkkotilin salasana.
* **Päivitystyö:** pyydetty toimenpide, jonka agentti noutaa ja suorittaa
  APT:n tai pacmanin avulla kohdetietokoneella. Tarkista kohde ja paketit
  ennen aloittamista.
* **Varmuuskopio:** erillinen, varmennettu kopio tietokannasta. Kopio samassa
  Docker-taltiossa ei suojaa kyseisen taltion menetykseltä.
* **Päivitys:** korvaa kontin version, ei tietokantaa. Normaali
  päivitys ei saa poistaa tai luoda uudelleen `lums-data`-taltiota.

### Turvallinen tarkistuslista ennen muutoksen tekemistä

1. Tarkista, onko päivitystöitä käynnissä ja tarvitaanko huoltoikkuna.
2. Varmista, että tuore, käyttökelpoinen tietokannan varmuuskopio on olemassa.
3. Kirjaa käynnissä oleva kuva, kontin asetukset ja datapolut.
4. Rakenna ja testaa uusi kuva ennen aktiivisen kontin pysäyttämistä.
5. Korvaa kontti samoilla data-, salaisuus- ja varmuuskopioliitoksilla sekä
   samoilla turva-asetuksilla.
6. Tarkista kontin tila, lokit, HTTPS-kirjautuminen ja tiedot käynnistyksen jälkeen.
7. Pidä vanha kontti palautusvaihtoehtona, kunnes uusi versio on
   varmennettu.

**Älä suorita** `docker volume rm lums-data`, `docker system prune --volumes`
tai muita poistokomentoja osana normaalia päivitystä. Ne voivat pysyvästi
poistaa tietoja. Jos et ole varma, mikä kontti tai polku on aktiivinen, pysähdy ja
tarkista nykyinen kokoonpano ensin; älä kopioi esimerkkikomentoa tarkistamatta sitä.

---

## 1. Hallinnan yleiskatsaus

LUMS tarjoaa keskitetyn hallinnan Linux-ohjelmistoluettelolle, saatavilla oleville päivityksille, pakettitoiminnoille, päivitystöille, hallinnoiduille asiakkaille, käyttäjille ja toimintahistorialle.

Hallintakäyttöliittymä tarjoaa kolme roolimallia:

* **Administrator**
* **Operator**
* **Viewer**

Kun tili luodaan, valittu rooli täyttää suositellun joukon
oikeuksia. Ylläpitäjät voivat säätää näitä oikeuksia käyttäjäkohtaisesti; tallennetut
oikeudet, eivät roolitunniste, määrittävät pääsyn.

LUMS erottaa myös palvelinpuolen hallintatoiminnot asiakaspuolen pakettien suorituksesta.

Normaali toimintavirta on:

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

LUMS-palvelin ei suorita paketinhallintakomentoja suoraan hallinnoiduilla asiakkaille.

Pakettitoiminnot suorittaa hallinnoituun järjestelmään asennettu LUMS-agentti.
2. Hallinnolliset vastuut

LUMS-hallinta voidaan jakaa useisiin alueisiin.
Käyttäjähallinta

Ylläpitäjät hallinnoivat:

    LUMS-käyttäjiä

    käyttäjärooleja

    tilin tilaa

    hallinnollista pääsyä

Käyttäjähallinta vaatii users.manage-oikeuden.

Administrator-malli sisältää tämän oikeuden oletuksena.

Operaattorit ja Viewerit eivät saa sitä oletuksena.
Asiakashallinta

Ylläpitäjät hallinnoivat:

    rekisteröityjä asiakkaita

    asiakkaan tilaa

    asiakastodennusta

    asiakastunnisteita

    tunnisteen vaihtoa

    asiakkaan käyttöönottoa ja käytöstä poistoa

Asiakashallinta vaatii clients.manage-oikeuden, koska asiakastodennus
määrittää, mitkä järjestelmät saavat raportoida LUMSille.
Päivityshallinta

Administrator- ja Operator-mallit myöntävät oikeudet:

    tarkastella saatavilla olevia päivityksiä

    luoda päivitystöitä

    suorittaa pakettitoimintoja

    tarkastella päivityshistoriaa

    hallita yksittäisiä paketteja

    suorittaa järjestelmäpäivityksiä

Viewer-malli on vain luku -tilassa eikä voi suorittaa päivitystoimintoja.
Paketinhallinta

LUMS tukee paketinhallintatoimintoja asiakkaan natiivin paketinhallinnan kautta.

Nykyiset tuetut paketinhallinnan taustajärjestelmät ovat:

    APT/dpkg Debian-pohjaisille järjestelmille

    pacman Arch Linuxille

LUMS ei korvaa käyttöjärjestelmän paketinhallintaa.

Sen sijaan LUMS tarjoaa keskitetyn käyttöliittymän pakettitoimintojen pyytämiseen ja seuraamiseen.
Operatiivinen hallinta

Ylläpitäjät ja operaattorit voivat joutua seuraamaan:

    käynnissä olevia päivitystöitä

    epäonnistuneita töitä

    suoritettuja töitä

    asiakasraportointia

    uudelleenkäynnistysvaatimuksia

    paketinhallinnan virheitä

    valvontatoimintaa

Näiden tilanteiden yksityiskohtaiset vianmääritysmenettelyt on dokumentoitu tiedostossa troubleshooting.md.
3. Hallinnolliset roolit

LUMS tarjoaa tällä hetkellä kolme roolia.
Rooli	Tarkoitus
Administrator	Täysi hallinnollinen valvonta
Operator	Päivittäinen operatiivinen hallinta
Viewer	Vain luku -näkyvyys asiakkaisiin ja ohjelmistoihin

Jokainen rooli on oikeusmalli. Tilin yksilöllisesti tallennetut
oikeudet valvotaan palvelinpuolella.

Käyttöliittymäelementin piilottamista ei siis pidetä itsessään turvakontrollina.

Palvelimen on myös hylättävä luvattomat API-toiminnot.
4. Administrator

Administrator-malli tarjoaa oletuksena täyden joukon LUMS-sovelluksen
oikeuksia.

Ylläpitäjät voivat:

    tarkastella hallinnoituja asiakkaita

    tarkastella asennettuja ohjelmistoja

    tarkastella saatavilla olevia päivityksiä

    luoda ja suorittaa päivitystöitä

    tarkastella päivityshistoriaa

    suorittaa paketinhallintatoimintoja

    suorittaa järjestelmän ylläpitoa

    luoda asiakkaita

    poistaa asiakkaita käytöstä

    vaihtaa asiakastunnisteita

    luoda ja hallita LUMS-käyttäjiä

    määrittää roolimalleja ja yksittäisiä oikeuksia

Täydet Administrator-mallin oikeudet tulisi myöntää vain käyttäjille, jotka
tarvitsevat niitä.

Hallinnollisia tilejä ei tulisi käyttää rutiininomaiseen vain luku -seurantaan, kun Operator- tai Viewer-tili riittää.
5. Operator

Operator-malli on tarkoitettu päivittäiseen päivitys- ja järjestelmän
hallintaan.

Operaattorit voivat:

    tarkastella hallinnoituja asiakkaita

    tarkastella asennettuja ohjelmistoja

    tarkastella saatavilla olevia päivityksiä

    luoda ja suorittaa päivitystöitä

    tarkastella päivityshistoriaa

    suorittaa paketinhallintatoimintoja

    suorittaa järjestelmän ylläpitoa

Operator-malli ei myönnä:

    LUMS-käyttäjien luontia tai hallintaa

    käyttäjäroolien määrittämistä

    asiakkaiden luontia tai käytöstä poistoa

    asiakastunnisteiden vaihtoa

Tämä oletuserottelu sallii rutiininomaiset päivitystoiminnot ilman
tili- ja asiakashallintaoikeuksia. Yksittäisiä oikeuksia voi muuttaa
käyttäjä, jolla on users.manage-oikeus.
6. Viewer

Viewer-malli tarjoaa vain luku -näkyvyyden.

Viewerit voivat:

    tarkastella hallinnoituja asiakkaita

    tarkastella asennettuja ohjelmistoja

Viewer-malli ei myönnä seuraavia hallintotoimintoja:

    saatavilla olevien päivitysten hallinta

    päivitystöiden luonti

    päivitystöiden suoritus

    päivityshistoria

    paketinhallinta

    järjestelmän ylläpito

    käyttäjähallinta

    asiakashallinta

    tunnisteen vaihto

Vastaavat mutatoivat API-toiminnot on myös suojattu palvelinpuolella.

Viewerin pääsy on siis tarkoitettu käyttäjille, jotka tarvitsevat näkyvyyttä ilman operatiivista valvontaa.
7. Roolin valinnan ohjeet

Käytä pienintä roolia, joka tarjoaa tarvittavat toiminnot.
Administrator

Käytä, kun käyttäjän on hallittava:

    käyttäjiä

    rooleja

    asiakkaita

    asiakastodennusta

    tunnisteita

    päivityksiä

    paketteja

    järjestelmätoimintoja

Operator

Käytä, kun käyttäjän on suoritettava rutiininomaista operatiivista työtä, kuten:

    päivitysten tarkistaminen

    pakettien asentaminen

    pakettien poistaminen

    pakettien päivittäminen

    päivitystöiden suorittaminen

    työhistorian tarkastelu

Viewer

Käytä, kun käyttäjä tarvitsee vain näkyvyyden:

    asiakkaisiin

    asennettuihin ohjelmistoihin

8. Hallinnollinen turvallisuusperiaate

LUMS-hallinta noudattaa vähimmän oikeuden periaatetta.

Hallinnollinen pääsy tulisi rajoittaa käyttäjän tehtävään tarvittaviin toimintoihin.

Erityisesti:

    älä käytä Administrator-tilejä rutiininomaiseen katseluun

    älä jaa tilejä ylläpitäjien kesken

    älä jaa asiakastunnisteita

    älä tallenna tunnistetietoja dokumentaatioon

    älä paljasta asiakastunnisteita kuvakaappauksissa tai lokeissa

    älä ohita LUMSin verkkokäyttöliittymää muokkaamalla tietokantaa suoraan, ellei dokumentoitu palautusmenettely nimenomaisesti vaadi sitä

Kun hallinnollinen toimenpide epäonnistuu, tutki syy ennen pysyvän tilan muuttamista.

Käytä periaatetta:

    Havaitse ensin. Muuta toiseksi. Varmista kolmanneksi.

9. Hallinnollinen työnkulku

Normaalin hallinnollisen työnkulun tulisi noudattaa tätä järjestystä:
text

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

Hallinnolliset toimenpiteet on aina varmennettava suorituksen jälkeen.

Onnistunut API-pyyntö ei itsessään todista, että pyydetty paketti- tai järjestelmätoiminto suoritettiin onnistuneesti.

Hallinnoidun asiakkaan raportoima lopullinen tila on olennainen toiminnallinen tulos.
10. Dokumentaation erottelu

LUMS-dokumentaatiosarja on tarkoituksella jaettu erillisiin toimintaoppaisiin.
Asiakirja	Tarkoitus
install.md	Asennus ja ensimmäinen käyttöönotto
administration.md	Päivittäinen hallinta
security.md	Turvallisuusarkkitehtuuri ja tarkastustulokset
troubleshooting.md	Diagnoosi ja palautus

Tämän oppaan tulisi siksi välttää yksityiskohtaisten asennus- ja vianmääritysmenettelyjen toistamista.

Sen sijaan se kuvaa, mitä ylläpitäjät voivat hallita, mitä kukin toimenpide tarkoittaa ja miten normaaleja hallinnollisia työnkulkuja suoritetaan.
11. Käyttäjähallinta

Käyttäjähallinta on saatavilla käyttäjille, joilla on users.manage-oikeus.

Ylläpitäjät voivat luoda ja hallita LUMS-sovellustilejä erillisen käyttäjähallintakäyttöliittymän kautta.

Käyttäjätilit ovat erillisiä hallinnoitujen asiakkaiden todentamisesta.

LUMS-käyttäjä todentaa itsensä verkkosovellukseen sovellustilillä.

Hallinnoitu asiakas todentaa itsensä LUMS-API:iin asiakastunnisteella.

Näitä todentamismekanismeja ei saa sekoittaa.
text

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

12. Käyttäjien luominen

Käyttäjät, joilla on users.manage, voivat luoda uusia LUMS-käyttäjiä.

Kun käyttäjä luodaan, ylläpitäjä määrittää:

    käyttäjänimen

    salasanan

    roolitunnisteen, ja roolimalli on saatavilla myöhempää oikeuksien määrittämistä varten

Saatavilla olevat roolimallit ovat:

    administrator

    operator

    viewer

Palvelin validoi annetut arvot ennen tilin luomista.

Uudet tilit alkavat ilman oikeuksia. Luomisen jälkeen ylläpitäjät voivat
määrittää yksittäisiä valintaruutuja tai soveltaa yhtä roolimalleista. Mallin
soveltaminen esivalitsee sen oletusoikeudet, joita voidaan sitten mukauttaa.
Saatavilla olevat oikeudet ovat:
Oikeus	Myönnetty pääsy
clients.view	Tarkastele asiakasluetteloa ja järjestelmätietoja
software.view	Tarkastele asennettuja ohjelmistoja
updates.view	Tarkastele päivityksiä, töitä ja päivityshistoriaa
packages.search	Hae pakettivarastoista
jobs.manage	Luo pakettitoimintoja ja päivitystöitä
clients.manage	Rekisteröi/poista asiakkaita ja vaihda asiakastunnisteita
users.manage	Luo käyttäjiä ja hallitse rooleja, oikeuksia ja sisäisiä muistiinpanoja
backups.manage	Luo ja tarkastele tietokannan varmuuskopioita

Asiakkaisiin liittyvät oikeudet edellyttävät clients.view-oikeutta; jobs.manage edellyttää myös
updates.view-oikeutta. LUMS estää viimeisen aktiivisen tilin poistamisen, jolla on
users.manage-oikeus, joten ylläpitäjät eivät voi vahingossa lukita itseään ulos.

Salasanoja ei tallenneta selkokielisinä.

LUMS käyttää Argon2-pohjaista salasanatiivistystä sovelluksen tunnistetiedoille.

Luomisen jälkeen varmista, että:

    käyttäjänimi näkyy käyttäjäluettelossa

    roolimalli ja yksittäiset oikeudet ovat oikein

    tili on käytössä

    käyttäjä voi todentaa itsensä onnistuneesti

Älä siirrä salasanoja dokumentaation, tukipyyntöjen, kuvakaappausten tai muiden turvattomien kanavien kautta.
Tietokannan varmuuskopiointikäyttöliittymä

Käyttäjät, joilla on backups.manage-oikeus, voivat luoda SQLite-varmuuskopioita
Datenbank-Backups-osiosta. Ylläpitäjätilit saavat tämän oikeuden
migraation 005-backup-permission kautta; uudet tilit saavat sen soveltamalla
Administrator-mallia tai se voidaan myöntää erikseen.

Käyttöliittymä tukee natiiveja .db- ja pakattuja .db.gz-tiedostoja. Se käyttää
SQLiten online-varmuuskopiointirajapintaa, validoi valmiin tietokannan ja tallentaa tiedostot
vain omistajan oikeuksin. Käyttöliittymä listaa kymmenen uusinta tiedostoa. Varmuuskopioita
ei salata, poisteta automaattisesti, ajasteta, ladata tai palauteta LUMSin toimesta;
ylläpitäjät, joilla on backups.manage, voivat poistaa yksittäisiä varmuuskopioita
luettelosta vahvistuksen jälkeen. Suojaa kohde vastaavasti.

Peruskohdehakemisto on kiinteä palvelinpuolen LUMS_BACKUP_DIR-asetuksella.
Käyttöliittymä sallii suhteellisen alihakemiston valitsemisen tämän
perustan alapuolelta ja luo sen tarvittaessa; absoluuttiset polut, ylätason läpikulku ja
symlinkitetyt alihakemistot hylätään. Isäntäpolut on liitettävä Dockeriin
palvelimen ylläpitäjän toimesta. Docker-käyttöönotossa luo erillinen isäntähakemisto,
johon kontin UID/GID 10001 voi kirjoittaa:
bash

sudo install -d -o 10001 -g 10001 -m 0700 /var/backups/lums

Lisää nämä vaihtoehdot LUMS-kontin kokoonpanoon:
bash

-v /var/backups/lums:/var/backups/lums \
-e LUMS_BACKUP_DIR=/var/backups/lums \

Käytä erillistä levyä tai etätallennusta isäntävian sietokyvyn parantamiseksi.
Esimerkiksi liitä NAS ensin Debian-isäntään ja käytä sitten kyseistä liitettyä polkua
Docker-bind-liitoksen vasemmalla puolella. Varmuuskopiointikäyttöliittymä näyttää
kontin puolen perushakemiston; valittu suhteellinen polku on sen alapuolella.
Varmuuskopiointikohteen on oltava käytettävissä ja kirjoitettavissa kontin sisällä;
muuten käyttöliittymä ilmoittaa, että varmuuskopiointitallennus ei ole käytettävissä.

Palautusohjeet ovat tiedostossa server/static/backup-restore.md.
13. Käyttäjäroolit

Valitse roolimalli vähimmän vaaditun oikeuden mukaan ja tarkista
sitten kunkin tilin yksittäiset oikeudet.
Roolimalli	Käyttäjähallinta	Asiakashallinta	Päivitykset	Paketinhallinta	Vain luku -pääsy
Administrator	Kyllä	Kyllä	Kyllä	Kyllä	Kyllä
Operator	Ei	Ei	Kyllä	Kyllä	Kyllä
Viewer	Ei	Ei	Ei	Ei	Kyllä

Nämä ovat oletuksia, eivät kiinteitä rajoja. Ylläpitäjät voivat mukauttaa kunkin
käyttäjän oikeusjoukkoa. Roolin valvonta tapahtuu palvelimella
tuloksena olevien käyttäjäkohtaisten oikeuksien kautta.

Verkkokäyttöliittymä heijastaa määritettyä roolia, mutta palvelin on edelleen ensisijainen turvaraja.
14. Käyttäjätilien poistaminen käytöstä

Kun tilin ei enää pitäisi päästä LUMSiin, poista tili käytöstä sen sijaan, että jakaisit tai käyttäisit tunnistetietoja uudelleen.

Esimerkkejä:

    ylläpitäjä lähtee projektista

    operaattori ei enää tarvitse pääsyä

    hallinnollisen pääsyn väliaikainen poisto

    turvallisuusvaste vaarantuneelle tilille

Kun tili on poistettu käytöstä, varmista, että todentaminen hylätään.

Olemassa olevat todennetut istunnot on myös otettava huomioon tilin turvallisuustutkinnassa.

Älä muokkaa users-taulukkoa manuaalisesti, ellei dokumentoitu palautusmenettely nimenomaisesti vaadi tietokantatason toimenpiteitä.
15. Salasanahallinta

Salasanat ovat sovelluksen tunnistetietoja, ja niitä on kohdeltava arkaluonteisina tietoina.

Ylläpitäjien on varmistettava, että:

    salasanoja ei jaeta

    salasanoja ei tallenneta Gitiin

    salasanoja ei sijoiteta dokumentaatioon

    salasanoja ei sisällytetä kuvakaappauksiin

    salasanoja ei kirjoiteta tarpeettomasti komentotulkin historiaan

    käyttäjät saavat tunnistetietonsa asianmukaisen turvallisen kanavan kautta

LUMS tallentaa salasanatiivisteitä selkokielisten salasanojen sijaan.

Jos salasanan epäillään vaarantuneen, vaihda se asianmukaisen tilinhallintamenettelyn kautta sen sijaan, että yrittäisit palauttaa alkuperäisen salasanan.
16. Istunnot

LUMS käyttää todennettuja sovellusistuntoja verkkopääsyyn.

Istunnon käsittely on osa sovelluksen turvarajaa.

Ylläpitäjien on kohdeltava odottamatonta todennettua istuntoa turvallisuustapahtumana, jos siihen liittyvällä tilillä ei enää pitäisi olla pääsyä.

Asiaankuuluvia tilanteita ovat:

    käytöstä poistettu tili, joka näyttää edelleen aktiiviselta

    odottamaton hallinnollinen pääsy

    epäilty tunnistetietojen vaarantuminen

    odottamaton selainistunto

    turvallisuustutkinta

Yksityiskohtaiset istunto- ja todentamisvianmääritysohjeet ovat tiedostossa troubleshooting.md.
17. Kirjautumisen nopeusrajoitus

LUMS soveltaa nopeusrajoitusta toistuviin epäonnistuneisiin kirjautumisyrityksiin.

Nykyinen eteneminen on:
Epäonnistuneet yritykset	Lukitus
5	30 sekuntia
6	60 sekuntia
7	120 sekuntia
8+	300 sekuntia

Nopeusrajoituksen tila tallennetaan SQLiteen.

Onnistunut kirjautuminen tyhjentää sovellettavan epäonnistumistilan.

Toistuvat todentamisepäonnistumiset tulisi tutkia sen sijaan, että ohittaisit nopeusrajoittimen.

Mahdollisia syitä ovat:

    virheelliset tunnistetiedot

    vanhentuneet tallennetut tunnistetiedot

    automatisoitu asiakas, joka käyttää virheellisiä tunnistetietoja

    toistuvat manuaaliset kirjautumisyritykset

    mahdollinen tunnistetietohyökkäys

18. Asiakashallinta

Hallinnoidut asiakkaat ovat Linux-järjestelmiä, joissa LUMS-agentti on käynnissä.

Asiakas tarjoaa LUMSille tietoja, kuten:

    asiakkaan identiteetti

    asennettu ohjelmisto

    saatavilla olevat päivitykset

    paketinhallinnan tulokset

    päivitystöiden tulokset

    uudelleenkäynnistystila

    toiminnallinen tila

LUMS-palvelin tallentaa asiakkaan tilan ja tarjoaa sen verkkokäyttöliittymän kautta.

Asiakas suorittaa varsinaiset paketinhallintatoiminnot paikallisesti.
19. Asiakastodennus

Jokainen hallinnoitu asiakas todentaa itsensä LUMSiin asiakastunnisteella.

Tunniste toimii hallinnoidun asiakkaan tunnistetietona.

Käsittele asiakastunnisteita yhtä huolellisesti kuin salasanoja.

Älä koskaan:

    committoi tunnisteita Gitiin

    sijoita tunnisteita julkiseen dokumentaatioon

    sisällytä tunnisteita kuvakaappauksiin

    liitä tunnisteita ongelmaseurantaan

    paljasta tunnisteita diagnostiikkatulosteissa

    jaa yhden asiakkaan tunnistetta toiselle asiakkaalle

Tunniste tulisi asentaa vain asiakkaalle, jolle se on myönnetty.
20. Asiakkaan rekisteröinti

Uusi asiakas on ensin rekisteröitävä LUMSiin.

Rekisteröintiprosessi luo asiakkaan identiteetin ja todentamistunnistetiedot palvelinpuolelle.

Rekisteröinnin jälkeen:

    asenna LUMS-agentti

    määritä asiakastunniste

    määritä LUMS-palvelimen päätepiste

    luo TLS-luottamus

    suorita agentin alustava ajo

    varmista, että asiakas raportoi onnistuneesti

    vahvista, että asiakas näkyy LUMS-käyttöliittymässä

Asiakasta ei pidä pitää toiminnallisena vain siksi, että agenttipalvelu käynnistyy onnistuneesti.

Palvelimen on vastaanotettava ja hyväksyttävä kelvollinen asiakasraportti.
21. Asiakkaan tila

Asiakasnäkymää tulee käyttää eri toimintatilojen erottamiseen.

Esimerkkejä:

    asiakas rekisteröity, mutta ei raportoi

    asiakas raportoi normaalisti

    asiakas raportoi vanhentuneita tietoja

    asiakas poistettu käytöstä

    asiakastodennuksen epäonnistuminen

    asiakaspuolen paketinhallinnan epäonnistuminen

Kun asiakas lopettaa raportoinnin, selvitä ensin, onko ongelma:

    verkkoyhteydessä

    TLS-luottamuksessa

    asiakastodennuksessa

    agentin suorituksessa

    palvelimen saatavuudessa

    palvelinpuolen käsittelyssä

Vältä asiakastunnistetietojen muuttamista ennen kuin olet selvittänyt, mikä kerros todella epäonnistuu.
22. Asiakastunnisteen vaihto

Asiakastunnisteita voidaan vaihtaa tarvittaessa.

Tyypillisiä syitä ovat:

    epäilty tunnisteen paljastuminen

    tunnistetietojen vaihtokäytäntö

    hallinnollinen ylläpito

    asiakaskokoonpanon korvaaminen

    turvallisuuspoikkeaman vastatoimi

Tunnisteen vaihto muuttaa asiakkaalle hyväksyttävää tunnistetta.

Vaihdon jälkeen:

    hanki uusi asiakastunniste

    päivitä asiakaskokoonpano

    suorita agentti

    varmista onnistunut todentaminen

    varmista tuloksena oleva asiakasraportti

    vahvista, että normaali raportointi jatkuu

Älä poista vanhaa asiakaskokoonpanoa ennen kuin uusi todentamispolku on varmennettu.
23. Asiakkaan poistaminen käytöstä

Asiakas voidaan poistaa käytöstä, kun sen ei enää pitäisi osallistua LUMS-toimintoihin.

Esimerkkejä:

    järjestelmän käytöstä poisto

    väliaikainen ylläpito

    asiakkaan vaihto

    epäilty tunnistetietojen vaarantuminen

Ennen asiakkaan poistamista käytöstä tarkista, onko siihen liittyviä aktiivisia päivitystöitä.

Käytöstä poistamisen jälkeen:

    varmista, että asiakasta ei enää käsitellä toiminnallisena

    tarkista asiaankuuluva päivitystyöhistoria

    säilytä tutkintaan tarvittavat valvontatiedot

Älä poista pysyviä asiakastietoja vain siksi, että asiakas on tilapäisesti offline-tilassa.
24. Asiakashallinnan tarkistuslista

Kun lisäät tai muutat asiakasta, varmista koko ketju:
text

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

Asiakas on toiminnallinen vain, kun koko raportointi- ja todentamisketju toimii.
25. Hallinnollinen periaate

Käyttäjähallinnan ja asiakashallinnan tulisi pysyä erillään.

LUMS-sovellustili määrittää, mitä henkilö saa tehdä.

Asiakastunniste määrittää, mikä hallinnoitu järjestelmä saa kommunikoida LUMSin kanssa.
text

Application User
      │
      └── Role / Permissions

Managed Client
      │
      └── Client Token / Identity

Älä käytä yhtä mekanismia toisen korvikkeena.
26. Ohjelmistoluettelo

LUMS ylläpitää hallinnoitujen asiakkaiden raportoimia ohjelmistotietoja.

Ohjelmistoluettelo antaa ylläpitäjille ja operaattoreille mahdollisuuden selvittää, mitkä paketit on asennettu asiakkaalle.

LUMS-agentti kerää luettelon ja raportoi sen palvelimelle.

Palvelin tarjoaa raportoidut tiedot asiakaskäyttöliittymän kautta.

Luetteloa tulee pitää tilannekuvana asiakkaan raportoimasta tilasta.

Se ei korvaa natiivia paketinhallintaa.
27. Asennettu ohjelmisto

Asennettu ohjelmisto -osio näyttää valitun asiakkaan raportoimat paketit.

Ylläpitäjät ja operaattorit voivat käyttää paikallista pakettisuodatinta näytetyn luettelon rajaamiseen.

Asennettujen ohjelmistojen suodatin on paikallinen käyttöliittymätoiminto.

Se on erillään paketinhallinnan hausta.

Tämä ero on tärkeä:
text

Installed Software
    │
    └── Filter already reported package inventory

Package Management
    │
    └── Search the client's package repositories

Asennettu paketti ei siksi välttämättä näy paketinhallinnan haussa, jos se ei ole enää saatavilla määritetyssä varastossa.
28. Saatavilla olevat päivitykset

LUMS kerää myös tietoja paketeista, joille on saatavilla päivityksiä.

Saatavilla olevien päivitysten tiedot luodaan hallinnoidulla asiakkaalla sen natiivin paketinhallintajärjestelmän avulla.

Raportoituja tietoja voidaan käyttää sellaisten pakettien tunnistamiseen, jotka vaativat huomiota.

Ennen päivitystyön luomista tarkista:

    asiakkaan identiteetti

    paketin nimi

    tällä hetkellä asennettu versio

    saatavilla oleva versio

    paketin tila

    onko asiakas tällä hetkellä tavoitettavissa

Älä oleta, että jokainen saatavilla oleva päivitys tulisi asentaa välittömästi.

Toiminnalliset vaatimukset, huoltoikkunat, sovellusriippuvuudet ja asiakkaan tila on otettava huomioon ennen suoritusta.
29. Paketinhallinta

LUMS tarjoaa keskitettyjä paketinhallintatoimintoja tuetuille Linux-asiakkaille.

Nykyiset paketinhallintatoiminnot ovat:

    INSTALL_PACKAGE

    REMOVE_PACKAGE

    UPDATE_PACKAGE

    UPDATE_SYSTEM

Toiminto pyydetään LUMSin kautta, mutta LUMS-agentti suorittaa sen paikallisesti.

Agentti delegoi varsinaisen pakettitoiminnon natiiville paketinhallinnalle.
text

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

LUMS pysyy siten riippumattomana käyttöjärjestelmän pakettitietokannasta ja paketinhallintatoteutuksesta.
30. Pakettihaku

Paketinhallinta-käyttöliittymä tarjoaa pakettihaun, joka on erillään asennettujen ohjelmistojen suodattimesta.

Haku pyytää pakettitietoja hallinnoidulta asiakkaalta.

Debian-pohjaisissa järjestelmissä agentti käyttää APT-paketinhallintatyökaluja.

Arch Linuxissa agentti käyttää pacman-työkalua.

Hakutulokset voivat sisältää:

    paketin nimi

    paketin versio

    paketin kuvaus

    varastotiedot, jos saatavilla

Pakettihaku ei asenna mitään.

Haku on siten vain luku -toiminto.
31. Paketin asentaminen

Ylläpitäjät ja operaattorit voivat luoda paketinasennustöitä.

Normaali työnkulku on:

    valitse hallinnoitu asiakas

    avaa Paketinhallinta

    hae tarvittava paketti

    tarkista tulos

    valitse asennustoiminto

    luo työ

    seuraa suoritusta

    varmista tulos

    päivitä tai tarkista asennettu ohjelmisto uudelleen

Agentti asentaa paketin natiivin paketinhallinnan avulla.

Työn onnistunut luominen ei tarkoita, että asennus on jo valmis.

Lopullinen työtulos on tarkistettava.
32. Paketin poistaminen

Paketin poistaminen noudattaa samaa hallittua työnkulkua.

Ennen paketin poistamista varmista:

    oikea asiakas

    oikea paketti

    aiottu toimenpide

    onko muut ohjelmistot riippuvaisia paketista

Suorituksen jälkeen varmista tuloksena oleva työn tila ja asiakkaan raportoima ohjelmistotila.

LUMS ei ohita paketinhallinnan riippuvuuksien käsittelyä.

Natiivi paketinhallinta vastaa edelleen toimenpiteen ratkaisemisesta.
33. Paketin päivittäminen

Tietty paketti voidaan päivittää, kun päivitys on saatavilla.

Työnkulku on:
text

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

LUMS validoi pakettitiedot ennen vastaavan päivitystyön luomista.

Jos pakettia ei enää ole listattu päivitettäväksi, työpyyntöä ei tule pitää kelvollisena päivitystoimintona.

Tämä estää vanhentuneiden päivitystietojen sokean suorittamisen.
34. Järjestelmän päivittäminen

UPDATE_SYSTEM suorittaa laajemman järjestelmäpäivityksen asiakkaan natiivin paketinhallintamekanismin avulla.

Tämä toimenpide vaikuttaa useampaan kuin yhteen pakettiin, joten sitä tulee pitää ylläpitotoimenpiteenä.

Ennen järjestelmäpäivityksen aloittamista varmista:

    asiakkaan saatavuus

    huoltoikkuna

    tällä hetkellä käynnissä olevat työt

    paketinhallinnan tila

    saatavilla oleva levytila tarvittaessa

    tarvitaanko mahdollisesti uudelleenkäynnistystä

Päivityksen jälkeen varmista:

    työn tulos

    asiakasraportti

    asennettu ohjelmisto

    saatavilla olevat päivitykset

    uudelleenkäynnistystila

35. Päivitystyöt

Kaikki mutatoivat paketti- ja päivitystoiminnot esitetään LUMS-päivitystöinä.

Tämä tarjoaa yhteisen suoritus- ja seurantamallin.

Tyypillinen työn elinkaari:
text

PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► FAILED
   │
   ▼
SUCCESS

Työ voi vaatia lisäkäsittelyä, kun asiakas tulee tavoittamattomaksi tai suoritus keskeytyy.

Työhistoriaa tulee käyttää ensisijaisena toiminnallisena tietueena sen sijaan, että luotettaisiin pelkästään nykyiseen asiakasnäkymään.
36. Työn luominen

Ennen päivitystyön luomista varmista aiottu toimenpide huolellisesti.

Tarkista:

    asiakas

    toiminto

    paketti

    kohdeversio tarvittaessa

    nykyinen paketin tila

    ylläpitovaatimukset

Tuetut toiminnot ovat:
Toiminto	Tarkoitus
INSTALL_PACKAGE	Asenna paketti
REMOVE_PACKAGE	Poista paketti
UPDATE_PACKAGE	Päivitä tietty paketti
UPDATE_SYSTEM	Suorita järjestelmänlaajuinen päivitys

Päivitystyön luominen on rajoitettu Administrator- ja Operator-rooleille.

Viewerit eivät voi luoda päivitystöitä.
37. Työn suoritus

Luomisen jälkeen LUMS-agentti käsittelee työn.

Agentti vastaanottaa työn ja suorittaa pyydetyn toimenpiteen paikallisesti.

Palvelin seuraa tuloksena olevaa tilaa.

Agentti ei pidä onnistunutta HTTP-pyyntöä todisteena siitä, että pakettitoiminto onnistui.

Sen sijaan todellinen paketinhallinnan tulos palautetaan LUMSille.

Tämä ero on tärkeä:
text

API request accepted
        ≠
Package operation successful

Lopullinen suoritustulos on siksi aina tarkistettava.
38. Työn tulokset

Valmiin työn tulee sisältää eksplisiittinen tulos.

Asiaankuuluvia tuloksia ovat:

    onnistunut suoritus

    epäonnistunut suoritus

    paketinhallinnan virhe

    keskeytynyt suoritus

    palautukseen liittyvä tila

    uudelleenkäynnistykseen liittyvä tila tarvittaessa

Ylläpitäjien ja operaattorien tulee tarkastaa tulos, kun työ epäonnistuu, sen sijaan että he välittömästi toistaisivat saman toimenpiteen.

Toistuva suoritus ilman alkuperäisen epäonnistumisen ymmärtämistä voi vaikeuttaa diagnoosia.
39. Työhistoria

Päivityshistoria tarjoaa toiminnallisen tietueen aiemmasta päivitystoiminnasta.

Käytä sitä vastaamaan kysymyksiin, kuten:

    Onko tämä paketti jo päivitetty?

    Mikä asiakas suoritti toimenpiteen?

    Milloin työ luotiin?

    Milloin suoritus alkoi?

    Milloin suoritus päättyi?

    Onnistuiko toimenpide?

    Raportoiko paketinhallinta virheestä?

Historialliset työtiedot ovat erityisen tärkeitä tutkittaessa toistuvia epäonnistumisia tai keskeytyneitä ylläpitotoimenpiteitä.
40. Epäonnistuneet työt

Kun työ epäonnistuu:

    kirjaa asiakas ja työn tunniste

    tarkista työn tulos

    selvitä, tapahtuiko epäonnistuminen palvelimella vai asiakkaalla

    tarkista asiaankuuluvat agenttilokit

    tarkista natiivin paketinhallinnan tila

    korjaa taustalla oleva ongelma

    yritä uudelleen vasta, kun syy on ymmärretty

Yleisiä syitä ovat:

    tavoittamattomat varastot

    paketinhallinnan lukot

    verkko-ongelmat

    virheelliset pakettipyynnöt

    riippuvuusristiriidat

    riittämätön levytila

    keskeytyneet pakettitoiminnot

    asiakastodennuksen tai viestinnän ongelmat

Yksityiskohtaiset diagnostiikkamenettelyt on dokumentoitu tiedostossa troubleshooting.md.
41. Paketinhallinnan lukot

APT ja pacman voivat estää samanaikaiset pakettitoiminnot.

Jos paketinhallintatoiminto epäonnistuu, koska paketinhallinta on jo käytössä:

    tunnista aktiivinen paketinhallintaprosessi

    selvitä, mikä toiminto on käynnissä

    odota laillisen toiminnon päättymistä tarvittaessa

    yritä LUMS-toimintoa uudelleen sen jälkeen

Älä poista paketinhallinnan lukkotiedostoja sokeasti, kun paketinhallinta on käynnissä.

Lukkotiedoston poistaminen ei ratkaise taustalla olevaa samanaikaista toimintoa ja voi vahingoittaa paketinhallinnan tilaa.
42. Lepotilatietoinen suoritus

LUMS voi käyttää asiakkaan lepotilatietoja määrittäessään, tulisiko päivitystyö suorittaa.

Tämän mekanismin tarkoitus on välttää keskeyttämästä hallinnoidun järjestelmän aktiivista interaktiivista käyttöä.

Lepotilan tunnistus suoritetaan agentin toimesta asiakkaalla.

Jos lepotilatiedot eivät ole saatavilla, agentin on raportoitava tämä tila sen sijaan, että se keksisi lepotilan.

Ylläpitäjien tulee erottaa:

    asiakas on lepotilassa

    asiakas on aktiivinen

    lepotilan tunnistus ei ole käytettävissä

    asiakas ei ole tavoitettavissa

Näillä tiloilla on erilaiset toiminnalliset merkitykset.
43. Päivityksen suorituksen seuranta

Ylläpidon aikana seuraa:

    työn tila

    asiakkaan yhteys

    agentin toiminta

    paketinhallinnan tulos

    uudelleenkäynnistysvaatimus

Älä oleta, että työ, joka pysyy RUNNING-tilassa loputtomasti, tarkoittaa, että paketinhallinta työskentelee edelleen.

Jos suoritus näyttää jumittuneen, tutki asiakkaan ja agentin tilaa ennen uuden työn luomista.
44. Uudelleenkäynnistysvaatimukset

Jotkin paketti- ja järjestelmäpäivitykset voivat vaatia uudelleenkäynnistyksen.

LUMS seuraa hallinnoidun asiakkaan raportoimaa uudelleenkäynnistystilaa.

Järjestelmäpäivityksen jälkeen:

    tarkista raportoitu uudelleenkäynnistystila

    selvitä, vaaditaanko uudelleenkäynnistys

    suorita uudelleenkäynnistys asianmukaisen huoltoikkunan aikana

    anna agentin raportoida uudelleen

    varmista, että asiakas palaa normaaliin toimintaan

Uudelleenkäynnistysvaatimusta ei tule automaattisesti tulkita päivityksen epäonnistumiseksi.
45. Päivityksen toiminnallinen tarkistuslista

Rutiininomaiseen pakettien ylläpitoon:
text

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

Toimenpide on valmis vasta, kun tuloksena oleva asiakkaan tila on varmennettu.
46. Paketinhallinnan periaate

LUMS tarjoaa keskitetyn orkestroinnin ja näkyvyyden.

Hallinnoitu käyttöjärjestelmä vastaa edelleen varsinaisesta paketinhallinnasta.

Siksi:

    LUMS pyytää ja seuraa toimenpidettä. Natiivi paketinhallinta suorittaa sen.

Tämä erottelu antaa LUMSin hallita erilaisia Linux-järjestelmiä säilyttäen samalla kunkin käyttöjärjestelmän paketinhallinnan semantiikan.
47. Työn palautus

LUMS on suunniteltu käsittelemään keskeytyneitä päivitystöitä toistamatta sokeasti jo onnistuneesti suoritettuja toimintoja.

Päivityksen suoritus käyttää tarkistuspistetietoja edistymisen seuraamiseen.

Tämä on erityisen tärkeää, kun:

    agentti keskeytyy

    asiakas käynnistyy uudelleen

    palvelin käynnistetään uudelleen

    verkkoyhteys on tilapäisesti poissa

    pakettitoiminto valmistuu ennen kuin tulos raportoidaan

Palautusmekanismi käyttää tallennettua työn tilaa määrittääkseen, mitä työtä on vielä suoritettava.
48. Pakettitason tarkistuspisteet

Useita pakettitoimintoja sisältävät työt käsitellään yksitellen.

Onnistunut pakettitoiminto tallennetaan ennen kuin agentti siirtyy seuraavaan toimintoon.

Käsitteellisesti:
text

Job
 │
 ├── Package A → SUCCESS
 │
 ├── Package B → SUCCESS
 │
 ├── Package C → interrupted
 │
 └── Package D → PENDING

Palautuksen jälkeen jo suoritettuja pakettitoimintoja ei tule suorittaa uudelleen tarpeettomasti.

Jäljellä oleva työ voi jatkua tallennetusta tilasta.

Tämä vähentää pakettitoimintojen toistamisen riskiä keskeytyksen jälkeen.
49. Keskeytyneet työt

Kun päivitystyö keskeytyy, älä heti luo korvaavaa työtä.

Selvitä ensin:

    mikä työ keskeytyi

    mikä pakettitoiminto oli aktiivinen

    mitkä pakettitoiminnot jo onnistuivat

    suorittiko paketinhallinta toiminnon loppuun

    palauttiko agentti työn automaattisesti

    vaatiiko asiakas uudelleenkäynnistyksen

Olemassa oleva työhistoria ja agenttilokit tulee tarkistaa ennen manuaalista toimenpidettä.
50. Agentin palautus

Agentti vastaa palautettavan työn jatkamisesta keskeytyksen jälkeen.

Palautuksen tulee säilyttää onnistuneet pakettitulokset aina kun mahdollista.

Jos pakettitoiminto on jo tallennettu onnistuneeksi, palautus ei saa sokeasti suorittaa samaa toimintoa uudelleen.

Jos palautus ei voi turvallisesti määrittää toiminnon tilaa, tila tulee käsitellä toiminnallisena ongelmana ja tutkia.

Älä muuta työn tiloja manuaalisesti tietokannassa vain saadaksesi työn näyttämään valmiilta.
51. Palvelimen uudelleenkäynnistys työn aikana

LUMS-palvelimen uudelleenkäynnistys ei välttämättä tarkoita, että asiakaspuolen pakettitoiminto keskeytyi.

Palvelimella ja asiakkaalla on erilliset suoritustilat.

Palvelimen uudelleenkäynnistyksen jälkeen:

    varmista, että LUMS-kontti on käynnissä

    varmista tietokannan saatavuus

    varmista, että asiakas voi kommunikoida LUMSin kanssa

    tarkista asiaankuuluvat päivitystyöt

    tarkista agenttiraportit

    varmista lopullinen paketin tila

Asiakaspuolen suoritustulos on edelleen tärkein totuuden lähde pakettitoiminnolle.
52. Asiakkaan uudelleenkäynnistys työn aikana

Asiakkaan uudelleenkäynnistys voi keskeyttää agentin suorituksen tai johtua siitä, että päivitys itse vaatii uudelleenkäynnistyksen.

Nämä tilanteet on erotettava toisistaan.
Odotettu uudelleenkäynnistys

Päivitys valmistui ja järjestelmä vaatii uudelleenkäynnistyksen.
Odottamaton keskeytys

Järjestelmä käynnistyi uudelleen ennen toiminnon valmistumista tai ennen kuin tulos voitiin raportoida.

Kun asiakas palaa:

    anna agentin käynnistyä normaalisti

    varmista kommunikointi LUMSin kanssa

    tarkista asiaankuuluva työ

    varmista paketin tila

    tarkista uudelleenkäynnistystila

    anna palautuksen jatkua tarvittaessa

53. Uudelleenkäynnistyksen tunnistus

LUMS voi seurata hallinnoidun asiakkaan raportoimia uudelleenkäynnistysvaatimuksia.

Uudelleenkäynnistyksen tunnistus ei ole sama kuin sen tunnistaminen, onko kone tällä hetkellä tavoitettavissa.

Nämä ovat erillisiä tiloja:
text

Client reachable
        │
        ├── reboot not required
        │
        └── reboot required

Client unreachable
        │
        └── current state cannot be confirmed

Ylläpitäjien tulee siksi välttää tavoittamattoman asiakkaan käsittelemistä todisteena siitä, että uudelleenkäynnistys vaaditaan.
54. Uudelleenkäynnistyksen jälkeinen varmistus

Vaaditun uudelleenkäynnistyksen jälkeen:

    odota, että käyttöjärjestelmä tulee saataville

    varmista agenttipalvelu tai -ajastin

    varmista asiakastodennus

    varmista asiakasraportti

    tarkista asiaankuuluva päivitystyö

    varmista asennetut pakettiversiot

    varmista saatavilla olevat päivitykset

    tarkista, vaaditaanko toinen uudelleenkäynnistys

Uudelleenkäynnistys tulee katsoa toiminnallisesti valmiiksi vasta, kun asiakas on raportoinut onnistuneesti uudelleen.
55. Päivitystyön seuranta

Ylläpitäjien ja operaattorien tulee seurata töitä suunnitellun ylläpidon aikana.

Tärkeitä tiloja ovat:
Tila	Merkitys
PENDING	Työ on olemassa, mutta suoritus ei ole alkanut
RUNNING	Työn suoritus on käynnissä
SUCCESS	Suoritus valmistui onnistuneesti
FAILED	Suoritus valmistui virheellä

Työn tilaa tulee aina tulkita yhdessä sen tulos tietojen kanssa.

Esimerkiksi FAILED-työtä tulee tutkia sen tallennetun tuloksen avulla sen sijaan, että se yksinkertaisesti yritettäisiin uudelleen.
56. Suorituksen valvoja

LUMS-agentti sisältää erillisen suorituksen valvojan.

Valvoja vastaa päivitystöiden suorituksen seuraamisesta asiakkaalla.

Sen tarkoitus on tukea luotettavaa suorituksen käsittelyä erillään raportointityönkulusta.

Nykyinen valvojan versio on:

Watcher 1.2.1

Agenttiversio on:

Agent 1.7.0

Nämä versiot tulee varmistaa asiakaspäivitysten jälkeen.
57. Valvojan seuranta

Ylläpitäjät voivat tarkastaa valvojan systemdin kautta hallinnoidulla asiakkaalla.

Hyödyllisiä tarkistuksia ovat:
bash

systemctl status lums-agent-watcher.service --no-pager

ja:
bash

journalctl -u lums-agent-watcher.service --no-pager -n 100

Ajastin voidaan tarkastaa komennolla:
bash

systemctl status lums-agent-watcher.timer --no-pager

Kertaluontoisen palvelun tarkka aktiivinen/inaktiivinen tila tulee tulkita yhdessä sen ajastimen ja lokin kanssa.

inactive (dead) -tila ei ole automaattisesti virhe kertaluontoiselle palvelulle.
58. Raportointi- ja suoritusajastimet

LUMS erottaa säännöllisen asiakasraportoinnin suorituksen seurannasta.

Raportointiajastin vastaa agentin ajastetusta suorituksesta.

Valvojan ajastin vastaa valvojan ajastetusta suorituksesta.

Tarkista molemmat, kun diagnosoit asiakaspuolen ajoitusongelmia:
bash

systemctl list-timers --all | grep lums-agent

Odotetut yksiköt ovat:
text

lums-agent.timer
lums-agent-watcher.timer

Jos ajastin ei ole käynnissä, tarkista:
bash

systemctl status lums-agent.timer --no-pager
systemctl status lums-agent-watcher.timer --no-pager

Tarkista sitten vastaavat lokimerkinnät.
59. Valvontalokitus

LUMS tallentaa tärkeät hallinnolliset ja turvallisuuteen liittyvät sovellustoiminnot valvontalokiin.

Valvontatiedot voivat auttaa selvittämään:

    mikä toiminto tapahtui

    kuka käyttäjä sen käynnisti

    mikä asiakas oli kyseessä

    milloin toiminto tapahtui

    hyväksyttiinkö toiminto

    mikä hallinnollinen toimenpide suoritettiin

Valvontatietoja tulee pitää toiminnallisena todisteena.

Niitä ei tule poistaa tai muuttaa huolettomasti.
60. Hallinnolliset valvontatapahtumat

Asiaankuuluva hallinnollinen toiminta kattaa toiminnot, kuten:

    käyttäjän luominen

    roolin määrittäminen

    asiakashallinta

    tunnisteen vaihto

    päivitystyön luominen

    paketinhallintatoiminnot

    todentamiseen liittyvät turvallisuustapahtumat

Tarkat tapahtumatiedot riippuvat toiminnosta.

Ylläpitäjien tulee käyttää valvontatietoja yhdessä työhistorian kanssa tutkiessaan odottamatonta toimintaa.
61. Valvontalokien käsittely

Valvontalokeja tulee käsitellä huolellisesti.

Älä:

    muokkaa historiallisia valvontamerkintöjä piilottaaksesi toiminnon

    paljasta arkaluonteisia tunnistetietoja viedyissä lokeissa

    julkaise lokeja, jotka sisältävät asiakastunnisteita

    julkaise salasanoja tai todentamismateriaalia

    kopioi arkaluonteisia lokitulosteita julkisiin ongelmaseurantoihin

Jos lokit on jaettava vianmääritystä varten, poista tunnistetiedot ja muut arkaluonteiset tiedot ensin.
62. Sovelluslokit

Sovelluslokit kuvaavat LUMS-palvelimen sisäistä toimintaa.

Hyödyllisiä lähteitä ovat:
bash

sudo docker logs --tail 100 lums

Live-seurantaan:
bash

sudo docker logs -f lums

Kun tutkit ongelmaa, rajaa aikaväliä mahdollisuuksien mukaan.

Älä automaattisesti tulosta koko tuotantolokia, kun pienempi asiaankuuluva osa riittää.
63. Agenttilokit

Asiakaspuolen agentin toimintaa voidaan tarkastaa systemdin kautta:
bash

journalctl -u lums-agent.service --no-pager -n 100

Valvojan toimintaan:
bash

journalctl -u lums-agent-watcher.service --no-pager -n 100

Tietyn aikavälin osalta voidaan käyttää systemd-journal-suodatusta.

Esimerkki:
bash

journalctl -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager

Lokit tulee korreloida asiaankuuluvan työn tunnisteen kanssa aina kun mahdollista.
64. Lokien korrelaatio

Kun tutkit päivitysongelmaa, korreloi tietoja järjestelmän eri osista:
text

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

Tämä estää yleisen virheen olettaa, että yhdessä kerroksessa havaittu ongelma sai alkunsa samasta kerroksesta.
65. Hallinnollisen seurannan tarkistuslista

Normaalin toiminnan aikana tarkista säännöllisesti:
text

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

Näiden tarkistusten tiheyden tulee vastata LUMS-käyttöönoton toiminnallista merkitystä.
66. Palautusperiaate

Kun päivitysongelma ilmenee, turvallisin hallinnollinen lähestymistapa on:
text

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

Vältä tuhoavia palautustoimenpiteitä, ellet ymmärrä todellista vikatilaa.

Erityisesti: älä poista töitä, tietokantatietueita, paketinhallinnan lukkoja tai pysyviä asiakastietoja manuaalisesti vain palauttaaksesi siistin näköisen käyttöliittymän.

    Säilytä todisteet ensin. Korjaa tila toiseksi. Varmista tulos kolmanneksi.

67. Tietokannan hallinta

LUMS käyttää SQLitea sovelluksen tietokantana.

Tuotantotietokanta tallennetaan pysyvään Docker-taltioon:
text

/var/lib/lums/lums.db

Tietokanta on pysyvä kontin vaihdon yli niin kauan kuin Docker-taltio säilytetään.

Tietokanta sisältää sovelluksen tilan, kuten:

    käyttäjät

    hallinnoidut asiakkaat

    päivitystyöt

    pakettitiedot

    valvontatiedot

    todentamiseen liittyvä tila

    migraation tila

Ylläpitäjien tulee kohdella tietokantaa kriittisenä sovellustietona.
68. SQLite-ajonaikainen kokoonpano

Nykyinen tuotannon SQLite-perustaso on:
Asetus	Arvo
journal_mode	wal
busy_timeout	5000
synchronous	2
foreign_keys	sovellus ottaa käyttöön

Sovellus ottaa eksplisiittisesti käyttöön SQLite-viiteavainten valvonnan tietokantayhteyksille.

Ylläpitäjien ei tule muuttaa näitä asetuksia huolettomasti.

Tietokannan ajonaikaisen kokoonpanon muutokset tulee testata ennen tuotantoon viemistä.
69. Tietokannan eheys

Tietokannan eheys tulee tarkistaa, kun on viitteitä tietokannan korruptiosta tai odottamattomasta sovelluskäyttäytymisestä.

Tyypillinen SQLite-eheystarkistus on:
bash

sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"

Terveen tietokannan pitäisi palauttaa:
text

ok

Jos eheystarkistus raportoi virheitä, älä jatka sovelluksen tilan muuttamista sokeasti.

Säilytä asianomainen tietokanta ja tutki syy.
70. Tietokantamigraatiot

LUMS käyttää sovellusmigraatioita tietokantamuutosten tuomiseen.

Migraatioiden tulee antaa suorittaa sovelluksen normaalin käynnistys- ja migraatiomekanismin kautta.

Ylläpitäjien ei tule muokata migraation tilaa manuaalisesti vain ohittaakseen virheen.

Sovelluspäivityksen jälkeen varmista:

    kontti käynnistyy onnistuneesti

    migraatiot valmistuvat

    sovellus on tavoitettavissa

    olemassa olevat käyttäjät pysyvät saatavilla

    olemassa olevat asiakkaat pysyvät saatavilla

    olemassa oleva työhistoria pysyy saatavilla

71. Pysyvä Docker-taltio

LUMS-sovellustiedot sisältävä Docker-taltio on kriittinen pysyvä resurssi.

Tuotantotaltio on:
text

lums-data

Tarkista se komennolla:
bash

sudo docker volume inspect lums-data

Taltion on pysyttävä liitettynä, kun LUMS-kontti korvataan.

Kontin poistaminen ei poista taltiota automaattisesti.

Taltion poistaminen kuitenkin poistaa pysyvästi pysyvät sovellustiedot, ellei erillistä varmuuskopiota ole olemassa.
72. Kontin hallinta

LUMS-sovellus toimii kovennetussa Docker-kontissa.

Tuotannon turvallisuusperustaso sisältää:

    ei-root-sovelluskäyttäjä

    vain luku -juuritiedostojärjestelmä

    poistetut Linux-kyvykkyydet

    no-new-privileges

    rajoitetut väliaikaiset tiedostojärjestelmät

    vain luku -salaisuuden liitos

    erillinen pysyvä datataltio

    vain localhost -sovellusportti

Konttia ei tule käynnistää heikommilla turva-asetuksilla vain siksi, että vianmääritys helpottuu.
73. Kontin tila

Tarkista kontin nykyinen tila komennolla:
bash

sudo docker ps --filter name=lums

Tarkista täydellinen ajonaikainen kokoonpano komennolla:
bash

sudo docker inspect lums

Tärkeitä ominaisuuksia ovat:

    käynnissä oleva tila

    uudelleenkäynnistyskäytäntö

    käyttäjä

    vain luku -juuritiedostojärjestelmä

    kyvykkyydet

    turva-asetukset

    porttisidonnat

    taltioliitokset

74. Kontin turvallisuuden varmistus

Kovennetun ajonaikaisen ympäristön tulee edelleen tarjota odotetut ominaisuudet.

Esimerkiksi:
bash

sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'

Odotettu perustaso vastaa:
text

lums true false

Kyvykkyydet tulee pitää poistettuina:
bash

sudo docker inspect lums \
    --format '{{json .HostConfig.CapDrop}}'

Odotettu:
text

["ALL"]

Turva-asetusten tulee sisältää:
text

no-new-privileges:true

75. Sovellusportti

LUMS-sovellus kuuntelee isäntää loopback-rajapinnan kautta.

Odotettu yhdistäminen on:
text

127.0.0.1:5050 → container:5000

Varmista se komennolla:
bash

sudo docker port lums

Sovellusporttia ei tule altistaa suoraan LAN-verkkoon.

Ulkoinen pääsy tarjotaan Nginxin kautta HTTPS:llä.
76. Nginx ja HTTPS

Nginx tarjoaa LUMSin ulkoisen HTTPS-sisääntulopisteen.

Normaali pyyntöpolku on:
text

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

Docker-sovellusportin tulee pysyä sidottuna localhostiin.

Ylläpitäjien tulee siksi välttää portin 5050 altistamista suoraan palomuurin tai Docker-kokoonpanon kautta.
77. HTTPS-varmentaminen

Nginx-muutosten jälkeen validoi kokoonpano aina ennen uudelleenlatausta:
bash

sudo nginx -t

Jos kokoonpano on kelvollinen:
bash

sudo systemctl reload nginx

Varmista sitten HTTPS:
bash

curl -I https://LUMS-SERVER/

Korvaa LUMS-SERVER isäntänimellä, jonka palvelimen TLS-varmenne kattaa. Älä käytä -k-valintaa rutiininomaiseen varmistukseen; se ohittaa varmenteen validoinnin.

Onnistunut HTTPS-vastaus vahvistaa, että Nginx tavoittaa LUMS-sovelluksen.

Varmenteen validointi tulee myös testata käyttäen isäntänimeä tai osoitetta, jota ylläpitäjät normaalisti käyttävät.

Älä poista varmenteen validointia pysyvästi käytöstä -k-valinnalla.
78. HTTP-uudelleenohjaus

HTTP-päätepisteen tulee ohjata asiakkaat HTTPS:ään.

Varmista:
bash

curl -I http://127.0.0.1/

Odotettu toiminta on HTTP-uudelleenohjaus HTTPS-päätepisteeseen.

Hallinnollisen pääsyn tulee käyttää HTTPS:ää.
79. TLS-varmenteen ylläpito

TLS-varmenteet ja yksityiset avaimet ovat Docker-kuvan ulkopuolella.

Tyypilliset sijainnit ovat:
text

/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key

Yksityiset avaimet on pidettävä suojattuina.

Ennen varmenteen korvaamista:

    varmista uusi varmenne

    varmista vastaava yksityinen avain

    varmista tiedoston oikeudet

    validoi Nginx-kokoonpano

    lataa Nginx uudelleen

    varmista HTTPS

    varmista sovelluksen kirjautuminen

Älä koskaan sijoita yksityisiä TLS-avaimia Git-arkistoon tai Docker-kuvaan.
80. Salaisuuksien hallinta

Sovelluksen salaisuus tallennetaan konttikuvan ulkopuolelle.

Tuotantosalaisuus liitetään vain luku -tilassa konttiin:
text

/etc/lums/secrets/lums_secret
        │
        ▼
/run/secrets/lums_secret

Sovellus vastaanottaa salaisuuden kautta:
text

LUMS_SECRET_KEY_FILE

Ylläpitäjät eivät saa koskaan:

    committoida salaisuutta

    tulostaa salaisuutta

    sisällyttää salaisuutta dokumentaatioon

    paljastaa sitä kuvakaappauksissa

    sijoittaa sitä kuvakerrokseen

Jos salaisuuden epäillään paljastuneen, käsittele sitä vaarantuneena ja noudata asianmukaista salaisuuden vaihtomenettelyä.
81. Varmuuskopiointistrategia

LUMS-tiedot tulee varmuuskopioida ennen merkittäviä hallinnollisia muutoksia.

Vähintään ota huomioon seuraavien suojaaminen:

    SQLite-sovellustiedot

    sovelluksen kokoonpano

    TLS-materiaali

    sovelluksen salaisuudet

    asiakaskokoonpanotiedot

    asiaankuuluva toiminnallinen dokumentaatio

Varmuuskopiot tulee tallentaa erilleen tuotantokontista ja sen pysyvästä Docker-taltiosta.

Varmuuskopio, joka on vain samalla isännällä tai Docker-taltiossa, ei tarjoa riittävää suojaa kyseisen isännän tai taltion menetykseltä.
82. Tietokannan varmuuskopiointi

SQLite-tietokanta tulee varmuuskopioida SQLite-tietoisella menetelmällä sen sijaan, että yksinkertaisesti kopioitaisiin aktiivisesti muokattavaa tietokantatiedostoa ottamatta huomioon sen tilaa.

Ennen varmuuskopion suorittamista:

    tunnista tuotantotietokanta

    varmista, että varmuuskopion kohde on saatavilla

    luo varmuuskopio asianmukaisella SQLite-turvallisella menetelmällä

    varmista, että varmuuskopio on olemassa

    kirjaa, milloin se luotiin

Älä oleta, että onnistunut tiedostokopio automaattisesti tarkoittaa kelvollisen palautettavan tietokannan varmuuskopion olemassaoloa.
83. Varmuuskopion varmentaminen

Varmuuskopiota ei pidetä luotettavana ennen kuin se on testattu.

Varmista säännöllisesti, että varmuuskopio voidaan:

    lukea

    avata SQLite-datana

    tarkistaa eheyden varalta

    palauttaa eristettyyn testiympäristöön

Esimerkiksi purettu testikopio voidaan tarkistaa komennolla:
bash

sqlite3 /path/to/test-copy.db \
    "PRAGMA integrity_check;"

Odotettu tulos:
text

ok

Tuotannon varmuuskopiota ei saa koskaan testata korvaamalla aktiivinen tuotantotietokanta.
84. Palautusperiaate

Palautus on hallittu hallinnollinen toimenpide.

Ennen palautusta:

    tunnista oikea varmuuskopio

    varmista sen eheys

    määritä tarvittava palautuspiste

    pysäytä tai eristä sovelluksen toiminta tarpeen mukaan

    säilytä nykyinen tuotantotila

    palauta varmuuskopio

    varmista tietokannan eheys

    käynnistä sovellus

    varmista migraatiot

    varmista käyttäjät ja asiakkaat

    varmista työhistoria

    varmista normaali asiakasraportointi

Älä korvaa tuotantotietokannan ainoaa kopiota palautuksen aikana.
85. Palautuksen varmentaminen

Palautuksen jälkeen varmista vähintään:
text

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

Palautus on valmis vasta, kun sovellus ja sen hallinnoidut asiakkaat on varmennettu.
86. Palvelimen varmuuskopiointiperiaate

Tärkein hallinnollinen sääntö pysyville LUMS-tiedoille on:

    Älä koskaan suorita tuhoavaa tietokanta- tai taltiotoimenpidettä ilman varmennettua palautuspolkua.

Erityisesti: älä poista lums-data-taltiota vain siksi, että kontti rakennetaan uudelleen tai korvataan.

Kontin korvaaminen ja pysyvien tietojen poistaminen ovat erillisiä toimenpiteitä.
87. Palvelimen hallinnollinen tarkistuslista

Ennen merkittävän palvelinpuolen muutoksen tekemistä:
text

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

Vasta kun nämä ehdot on otettu huomioon, merkittävä tuotantomuutos voidaan suorittaa.
88. Palvelimen hallintaperiaate

LUMS erottaa sovelluksen tilan kertakäyttöisestä sovelluskontista.
text

Disposable
└── LUMS Container

Persistent
├── SQLite Database
└── lums-data Volume

External
├── TLS Material
└── Application Secret

Tämä erottelu antaa sovelluskontin korvaamisen ilman, että pysyvät sovellustiedot tuhotaan tarkoituksella.

    Korvaa sovellus tarvittaessa. Säilytä tiedot, ellei tietojen poistaminen ole nimenomaisesti tarkoitettu.

89. Rutiininomainen ylläpito

Rutiininomainen ylläpito pitää LUMS-asennuksen luotettavana ja vähentää odottamattomien toimintaongelmien riskiä.

Tyypillisiä ylläpitotoimintoja ovat:

    epäonnistuneiden päivitystöiden tarkastelu

    asiakasraportoinnin tarkistaminen

    sovelluslokien tarkastelu

    valvontatoiminnan tarkastelu

    varmuuskopioiden varmentaminen

    saatavilla olevan levytilan tarkistaminen

    Docker-kontin tilan tarkastelu

    TLS-varmenteen voimassaolon tarkistaminen

    turvapäivitysten tarkastelu

    nykyisen LUMS-version ja kuvan varmentaminen

Ylläpito tulee suorittaa asianmukaisen huoltoikkunan aikana, kun muutokset voivat vaikuttaa tuotantoasiakkaisiin.
90. Ylläpito ennen muutoksia

Ennen ylläpitoa, joka voi vaikuttaa LUMS-palvelimeen:

    tarkista aktiiviset päivitystyöt

    varmista, että asiakkaat eivät ole odottamattomassa ylläpidossa

    luo tai varmista ajantasainen varmuuskopio

    kirjaa nykyinen kontin ja kuvan tila

    dokumentoi suunniteltu muutos

    varmista, että palautuspolku on olemassa

Älä aloita ylläpitoa pysäyttämällä tai poistamalla tuotantokomponentteja välittömästi.

Selvitä ensin nykyinen tila.
91. Docker-kuvan ylläpito

LUMS-sovelluskuvat tulee rakentaa uudelleen tarkastetusta lähdekoodipuusta.

Ennen uuden kuvan rakentamista:
bash

cd /opt/lums-public

Suorita automatisoitu testisarja:
bash

./.venv-test/bin/pytest -q

Jatka vain, kun testitulos on ymmärretty.

Rakenna uusi kuva erillisellä väliaikaisella tunnisteella:
bash

sudo docker build -t lums:new .

Väliaikainen tunniste antaa käynnissä olevan kuvan pysyä tunnistettavana korvausprosessin aikana.
92. Kuvan varmentaminen

Uuden kuvan rakentamisen jälkeen varmista, että kuva on olemassa:
bash

sudo docker image inspect lums:new

Tarkista kuvan kokoonpano ennen käyttöönottoa.

Varmista tarvittaessa:

    kuvan tiiviste

    peruskuva

    sovellustiedostot

    asennetut riippuvuudet

    kuvan koko

    altistetut portit

    määritetty käyttäjä

Kuva tulee ottaa käyttöön vasta, kun koontien ja testien tulokset on tarkastettu.
93. Hallittu kontin vaihto

Kontin vaihto tulee suorittaa harkitusti.

Ennen tuotantokontin korvaamista:
text

[ ] Tests passed
[ ] New image exists
[ ] Database backup available
[ ] Active jobs reviewed
[ ] Current image recorded
[ ] Persistent volume confirmed
[ ] Secret available
[ ] TLS configuration available
[ ] Rollback image identified

Ennen esimerkin suorittamista vertaa sitä todella käynnissä olevaan konttiin. Alla olevat arvot ovat esimerkki, eivätkä ne ole turvallinen komento jokaiseen asennukseen. Erityisesti Docker-bind-liitoksen lähdepolut :-merkin vasemmalla puolella on vastattava isäntääsi, ja vanhalla kontilla voi olla eri nimi.

Näytä kuva, liitokset, julkaistut portit, uudelleenkäynnistyskäytäntö ja koventamisasetukset tulostamatta ympäristömuuttujien arvoja:
bash

sudo docker inspect lums --format 'Image={{.Config.Image}}
Mounts={{json .Mounts}}
Ports={{json .HostConfig.PortBindings}}
Restart={{json .HostConfig.RestartPolicy}}
Readonly={{.HostConfig.ReadonlyRootfs}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
Tmpfs={{json .HostConfig.Tmpfs}}'

Tallenna tuloste yksityiseen paikkaan ja käytä sitä varmistaaksesi, että uusi kontti säilyttää saman tietokantataltion, salaisuustiedoston, varmuuskopiohakemiston, vain paikallisen porttisidonnan ja turva-asetukset. Älä liitä salaisuuksien sisältöä tai ympäristömuuttujien arvoja muistiinpanoihin tai viesteihin.

Pysäytä olemassa oleva kontti vasta, kun nämä ehdot on otettu huomioon.

Tuotantokontin tulee säilyttää kovennettu ajonaikainen kokoonpano.

Esimerkki:
bash

sudo docker stop lums
sudo docker rename lums lums-before-upgrade

Käynnistä sitten uusi kuva vakiintuneella kovennetulla kokoonpanolla:
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
    -v /var/backups/lums:/var/backups/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -e LUMS_BACKUP_DIR=/var/backups/lums \
    lums:new

Älä poista lums-before-upgrade-konttia ennen kuin uusi käyttöönotto on validoitu.
94. Päivityksen jälkeinen validointi

Heti kontin korvaamisen jälkeen varmista:
bash

sudo docker ps --filter name=lums

Tarkista sitten lokit:
bash

sudo docker logs --tail 100 lums

Varmista HTTPS:
bash

curl -I https://LUMS-SERVER/

Korvaa LUMS-SERVER isäntänimellä, jonka palvelimen TLS-varmenne kattaa. Älä käytä -k-valintaa rutiininomaiseen varmistukseen; se ohittaa varmenteen validoinnin.

Varmista sitten sovellus normaalin hallintakäyttöliittymän kautta.

Tarkista, että olemassa olevat käyttäjät, asiakkaat ja viimeaikainen historia ovat edelleen läsnä.
Tarkista lokeista käynnistys- tai migraatiovirheet. Pelkkä käynnissä oleva kontti
ei todista, että sovellus tai sen tietokanta on kunnossa.
Rullaa takaisin, jos uusi kontti ei toimi

Pidä vanha kontti, kunnes uusi versio on läpäissyt validoinnin. Jos
uusi kontti on käyttökelvoton ja olet vahvistanut, että vanha kontti on
nimeltään lums-before-upgrade, pysäytä ja poista vain uusi kontti, sitten
nimeä vanha uudelleen ja käynnistä se:
bash

sudo docker stop lums
sudo docker rm lums
sudo docker rename lums-before-upgrade lums
sudo docker start lums

docker rm lums ilman -v-valintaa poistaa kontin, ei lums-data-taltiota. Älä koskaan lisää -v-valintaa tähän palautuskomentoon. Jos kontin nimi eroaa
tai et ole varma, kumpi kontti on vanha ja kumpi uusi, älä suorita näitä
komentoja; tarkista nykyinen tila tai kysy apua ylläpitäjältä. Palautuksen jälkeen
tarkista lokit ja varmista, että verkkokäyttöliittymä ja tiedot ovat
käytettävissä.
95. Pysyvät tiedot päivityksen jälkeen

Kontin vaihto ei saa poistaa pysyvää Docker-taltiota.

Varmista:
bash

sudo docker inspect lums \
    --format '{{json .Mounts}}'

Vahvista, että:
text

/var/lib/lums

on odotetun pysyvän taltion tukema.

Varmista sitten:

    käyttäjät ovat edelleen olemassa

    roolit pysyvät oikeina

    asiakkaat pysyvät rekisteröityinä

    työhistoria pysyy saatavilla

    valvontatiedot pysyvät saatavilla

    migraatiot valmistuivat onnistuneesti

96. Turvallisuusperustaso päivityksen jälkeen

Uuden kuvan käyttöönoton jälkeen varmista kovennettu ajonaikainen ympäristö uudelleen.

Tarkista:
bash

sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'

Odotettu perustaso:
text

lums true false

Varmista myös:
text

CapDrop = ALL
SecurityOpt = no-new-privileges:true

ja että:
text

127.0.0.1:5050 → container:5000

pysyy sovelluksen altistuksena.

Onnistunut sovelluspäivitys ei saa hiljaisesti heikentää turvallisuusperustasoa.
97. Asiakasviestintä päivityksen jälkeen

Palvelinpäivityksen jälkeen varmista, että hallinnoidut asiakkaat voivat edelleen kommunikoida.

Tarkista ensin ainakin yksi edustava asiakas.

Varmista:
text

[ ] Client authentication succeeds
[ ] Client report is accepted
[ ] Installed software is available
[ ] Available updates are available
[ ] Update jobs can be created
[ ] Agent results are accepted

Jos useita asiakasalustoja on käytössä, varmista edustavat järjestelmät jokaiselta tuetulta alustalta.
98. Päivityksen suoritus päivityksen jälkeen

Älä suorita heti suurta tuotantopäivitystä LUMS-palvelimen korvaamisen jälkeen.

Suorita ensin hallittu toiminnallinen testi.

Sopivan testin tulisi varmistaa koko polku:
text

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

Vasta kun hallittu testi onnistuu, normaalit ylläpitotoimenpiteet voivat jatkua.
99. Palautus

Palautus tulee olla mahdollista, kun uusi kuva aiheuttaa odottamattoman tuotanto-ongelman.

Säilytä:

    edellinen toimiva kuva

    pysyvät tiedot

    tietokannan varmuuskopio

    edellinen kokoonpano

    edellinen TLS-materiaali

    asiaankuuluvat lokit

Jos uusi kontti ei ole käyttökelpoinen:

    pysäytä uusi kontti

    säilytä se tutkintaa varten mahdollisuuksien mukaan

    lopeta muut hallinnolliset muutokset

    palauta aiemmin tunnettu toimiva kuva

    käytä uudelleen olemassa olevaa pysyvää taltiota

    käynnistä kovennettu ajonaikainen ympäristö

    varmista sovellus

    varmista asiakkaat

    varmista työn tila

    tutki epäonnistunut kuva erikseen

Älä poista pysyvää taltiota osana normaalia palautusta.
100. Palautuksen validointi

Palautuksen jälkeen varmista:
text

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

Palautus on valmis vasta, kun sovellus ja asiakasviestintäpolku on varmennettu.
101. Hätätilanteiden hallinta

Hätätilanteiden hallinnan tulisi säilyttää todisteet ja pysyvä tila aina kun mahdollista.

Esimerkkejä:

    toistuvat sovelluksen kaatumiset

    tietokannan eheysvirheet

    laajat asiakastodennuksen epäonnistumiset

    odottamaton pakettityön käyttäytyminen

    epäilty tunnistetietojen paljastuminen

    rikkoutuneet päivitykset

    TLS-virheet, jotka vaikuttavat kaikkiin käyttäjiin

Ensisijainen järjestys on:
text

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

Vältä lokien, tietokantojen, konttien tai asiakastietueiden poistamista vain siksi, että ne näyttävät olevan osa ongelmaa.
102. Hallinnollisen muutoksen periaate

Jokaisella merkittävällä tuotantomuutoksella tulisi olla kolme selkeästi määriteltyä tilaa:
Ennen

Nykyinen tuotantotila on tiedossa ja palautettavissa.
Aikana

Muutos suoritetaan dokumentoidun menettelyn mukaisesti.
Jälkeen

Tuloksena oleva tila varmennetaan odotettua perustasoa vasten.

Tämä tekee hallinnollisesta työstä toistettavaa ja vähentää tahatonta kokoonpanon ajautumista.
103. Hallittu asennuksen poisto

Asennuksen poisto on tuhoava hallinnollinen toimenpide.

Se tulee suorittaa vain, kun LUMS-käyttöönotto poistetaan tarkoituksella.

Ennen LUMSin poistamista:
text

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

Älä poista pysyviä tietoja ennen kuin olet vahvistanut, ettei niitä enää tarvita.
104. Kontin poistaminen

Poista sovelluskontti käytöstä poistamisen jälkeen:
bash

sudo docker stop lums
sudo docker rm lums

Docker-taltiota ei tarkoituksella poisteta näillä komennoilla.

Tämä antaa sovellustietojen pysyä saatavilla myöhempää tarkastusta tai palautusta varten.
105. Pysyvien tietojen poistaminen

LUMS Docker-taltion poistaminen on erillinen tuhoava toimenpide.

Suorita tämä vain, kun olet vahvistanut, ettei tietokantaa ja kaikkea tallennettua sovellustilaa enää tarvita.

Esimerkki:
bash

sudo docker volume rm lums-data

Tämä poistaa pysyvästi kyseiseen taltioon tallennetut pysyvät sovellustiedot.

Älä suorita tätä komentoa normaalin päivityksen tai palautuksen aikana.
106. Asiakaskomponenttien poistaminen

Kun hallinnoitu asiakas poistetaan pysyvästi LUMSista, poista sen agenttikomponentit tai poista ne käytöstä asiakkaan käyttöjärjestelmämenettelyn mukaisesti.

Asiakkaan ei tule enää raportoida LUMS-palvelimelle käytöstä poistamisen jälkeen.

Säilytä asiaankuuluvat työ- ja valvontatiedot ennen asiakkaan poistamista, jos historialliset tietueet vaaditaan.
107. Lopullinen hallinnollinen tarkistuslista
Käyttäjähallinta
text

[ ] Users have appropriate roles
[ ] Administrator access is limited
[ ] Disabled accounts are reviewed
[ ] Credentials are protected

Asiakashallinta
text

[ ] Clients are correctly registered
[ ] Client tokens are protected
[ ] Disabled clients are reviewed
[ ] Token rotation is performed when required
[ ] Client reporting is healthy

Päivityshallinta
text

[ ] Available updates are reviewed
[ ] Update jobs are monitored
[ ] Failed jobs are investigated
[ ] Package operations are verified
[ ] Reboot requirements are checked
[ ] Job history is retained

Palvelimen hallinta
text

[ ] Container is running
[ ] Persistent volume is attached
[ ] SQLite integrity is healthy
[ ] HTTPS is working
[ ] TLS material is valid
[ ] Application secret is protected
[ ] Backups are available

Turvallisuus
text

[ ] RBAC remains enforced
[ ] Viewer restrictions remain intact
[ ] Client authentication works
[ ] Container remains hardened
[ ] Application port remains localhost-only
[ ] No credentials are exposed
[ ] Logs contain no unexplained sensitive information

108. Toiminnallinen perustaso

Terveen LUMS-asennuksen tulisi täyttää seuraava perustaso:
text

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

109. Hallinta valmis

LUMS-hallinnassa tulisi aina priorisoida hallittuja, havaittavia ja palautuvia muutoksia.

Hallinnollinen elinkaari on:
text

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

Tärkeimmät toimintaperiaatteet ovat:

    Käytä vähimmän tarpeellisen oikeuden periaatetta.

    Säilytä pysyvät tiedot.

    Älä muuta tilaa ymmärtämättä nykyistä tilaa.

    Varmista jokaisen merkittävän toimenpiteen tulos.

    Pidä testattu palautuspolku.

Asennusmenettelyt: katso install.md.

Turvallisuusarkkitehtuuri ja tarkastustulokset: katso security.md.

Diagnoosi- ja palautusmenettelyt: katso troubleshooting.md.
110. Lopullinen hallintaperiaate

LUMS on tarkoitettu tekemään Linux-päivitysten hallinnasta ennustettavaa ja havaittavaa.

Hallinnollisen työn ei siksi tulisi perustua oletuksiin tai sokeaan toistamiseen.

Kun jokin muuttuu:

Havaitse ensin. Muuta toiseksi. Varmista kolmanneksi.

Kun jokin menee rikki:

Säilytä todisteet. Tunnista vikakerros. Palauta harkitusti.

Kun jokin toimii:

Kirjaa tulos ja pidä yllä tunnettua toimivaa perustasoa.
