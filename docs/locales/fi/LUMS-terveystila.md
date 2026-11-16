# LUMS-terveystilan koontinäyttö

## Tarkoitus ja soveltamisala

Todennettu `/health`-koontinäyttö antaa ylläpitäjälle nopean yleiskuvan valituista LUMS- ja laitejoukon tilatiedoista:

- tietokannan tila sovelluksen arvion mukaan;
- asiakkaiden kokonaismäärä sekä verkossa olevien, tuntemattomien ja offline-asiakkaiden määrät;
- viimeaikainen suorittimen, muistin ja verkon telemetria käytössä olevalta asiakkaalta, jos telemetria on asennettu ja näytteitä on saatavilla;
- viimeaikainen suorittimen, muistin ja verkon telemetria käytössä olevilta asiakkailta, jos telemetria on asennettu ja näytteitä on saatavilla;
- hälytyshistoria ja havaitut telemetriakatkot;
- tieto siitä, voidaanko määritettyä varmuuskopiohakemistoa tarkastella, sovelluksen tunnistama uusin varmuuskopiotiedosto sekä auditointilokiin kirjattu viimeisin onnistunut varmuuskopion luonti;
- valinnaiset Wazuh- ja Suricata-systemd-palvelutilarivit, jos ne on määritetty.

Yksittäisen asiakkaan tarkat isäntä- ja verkkotiedot, lämpötilat, palveluiden ja säilöjen tilat sekä tietoturvatapahtumien yhteenvedot ovat erillisellä `/monitoring`-sivulla. Telemetriayksiköllä on vain luku -oikeus järjestelmäjournaliin tapahtumayhteenvetoja varten; raakoja lokiviestejä, käyttäjänimiä tai lähdeosoitteita ei lähetetä. Säilötietoja ei saada, ellei telemetriapalvelun tili voi tarkastella suoritusympäristöä ilman lisäoikeuksia. Nämä sivut eivät todista, että isäntä, Docker-daemon, käänteinen välityspalvelin, verkko tai jokainen hallittu asiakas toimii moitteettomasti. Näkyvä varmuuskopio ei todista, että sen voi palauttaa; tee säännöllisesti hallittu palautustesti.

## Käyttöoikeuksien valvonta

`/health`-sivu edellyttää kirjautunutta käyttäjää, jolla on `clients.view`-oikeus. Käyttöä valvovat sovelluksen tavanomaiset todennus- ja valtuutustarkistukset. Älä tee koontinäytöstä julkista ohittamalla kirjautumisen tai käänteisen välityspalvelimen suojauksia.

Erillinen `GET /api/health`-päätepiste on kevyt elossaolovastaus. Onnistunut vastaus kertoo vain, että reitti pystyy vastaamaan; se ei ole kattava arvio tietokannasta, varmuuskopioista tai asiakkaiden kunnosta.

## Asiakkaan tilan tulkinta

Koontinäyttö luokittelee asiakkaat viimeksi ilmoitetun aikaleiman perusteella:

| Tila | Aikaleiman ikä |
| --- | --- |
| Online | Enintään 120 sekuntia |
| Unknown | Yli 120 ja enintään 600 sekuntia, puuttuva/virheellinen aikaleima tai tulevaisuuteen sijoittuva aikaleima |
| Offline | Yli 600 sekuntia |

Kynnysarvot kuvaavat ilmoituksen tuoreutta, eivät sitä, onko tietokone päällä tai toimiiko jokainen sen palvelu. Verkkoviiveet, lepotilassa olevat tietokoneet, pysähtynyt agentti tai ilmoitusongelmat voivat vaikuttaa tulokseen. Käsittele `unknown`-tilaa puutteellisina tietoina, älä todisteena viasta.

## Suorittimen ja muistin telemetria

Telemetria on valinnainen ja erillinen Reporting Agentista ja suoritusvahtina toimivasta Watcherista. Telemetriapalvelu lähettää näytteen noin viiden sekunnin välein, kun systemd-ajastin on käytössä ja asiakas saa yhteyden palvelimeen.

Koontinäytössä on 1 tunnin, 24 tunnin ja 7 päivän historiavälit, ja laitejoukon telemetria päivittyy viiden sekunnin välein. `/monitoring`-sivun tarkat isäntätiedot ovat viimeisin ilmoitettu tilannekuva; liitäntäkohtainen kaistanleveys lasketaan peräkkäisistä tilannekuvista. Historiakyselyiden aikaväli on 1–168 tuntia, ja tulokset voidaan harventaa enintään 1 000 pisteeseen. Yli seitsemän päivää vanhat näytteet poistetaan uusia telemetrialähetyksiä käsiteltäessä; jos lähetykset loppuvat kokonaan, älä oleta, että säilytyksen siivous toimii erillään niistä.

Valvontasivun kukin journal-kysely kattaa enintään 500 osuvaa tietuetta; näytetty `500+` tarkoittaa, että määrä voi olla tätä suurempi. Kirjautumis-/uloskirjautumishistoria rajataan 20 tapahtumaan ja käynnistyshistoria 10 merkintään. Terveystilan koontinäytön asettelu on kiinteä, ja se käyttää käyttäjän olemassa olevia suorittimen, RAM-muistin ja levyn kynnysarvoja (oletus 90 %). Kynnysarvojen ylitykset ja telemetriakatkot päätellään säilytetyistä näytteistä; palvelun tilasiirtymät ja uudet SSH-epäonnistumiset tallennetaan aikaleimallisina tapahtumina enintään seitsemäksi päiväksi. CSV-/JSON-viennit sisältävät kaikki valitun aikavälin näytteet; vuorovaikutteiset kaaviot rajataan 1 000 pisteeseen.

Wazuh- ja Suricata-rivit ovat valinnaisia ja ilmoittavat vain systemd-palveluiden tilan. Ne edellyttävät vastaavan asennetun yksikön lisäämistä `LUMS_MONITORED_SERVICES`-muuttujaan. Ne eivät yhdistä Wazuhin tai Suricatan rajapintoihin eivätkä tuo niiden hälytyssyötteitä. Varmuuskopioajon aikaleima tulee auditointilokista eikä ole erillinen palautuksen varmennus.

Telemetria edellyttää asiakkaan todennusta. Etäagenttiyhteydet edellyttävät HTTPS:ää; selväkielinen HTTP hyväksytään vain loopback-osoitteissa. Määritä CA-tiedosto, jos palvelin käyttää yksityistä varmennevarmentajaa. Määritysohjeet ovat tiedostoissa [Telemetria](Telemetria.md) ja [Asennus ja päivitykset](Asennus%20ja%20päivitykset.md); englanninkieliset lähteet ovat [telemetry.md](../../../telemetry.md) ja [install.md](../../../install.md).

## Varmuuskopiotilan tila

Varmuuskopio-osio kuvaa sitä, mitä sovellus pystyy tarkastelemaan määritetyssä varmuuskopiohakemistossa, sekä uusinta tunnistamaansa varmuuskopiotiedostoa. Se ei tarkista itsenäisesti kaikkien varmuuskopioiden sisältöä, varmista muualla olevaa kopiota eikä todista, että tietokannan palautus onnistuisi.

Suositeltu käytäntö:

1. varmista, että näytetty varmuuskopion päivämäärä täyttää palautustavoitteesi;
2. tarkista varmuuskopiointityö ja sovelluslokit virheiden varalta;
3. varmista, että varmuuskopio kopioidaan asianmukaiseen suojattuun kohteeseen;
4. testaa palautus säännöllisesti erillisessä, hallitussa sijainnissa.

Älä poista tai korvaa käytössä olevaa tietokantaa tai varmuuskopiotiedostoja vianmäärityksen oikotienä. Palautusohjeet ovat tiedostossa [Varmuuskopion palauttaminen](Varmuuskopion%20palauttaminen.md) ja englanninkielisessä lähteessä [backup-restore.md](../../../server/static/backup-restore.md).

## Suositellut tarkistukset, kun tila vaikuttaa virheelliseltä

1. Tarkista LUMS-säilö ja viimeaikaiset lokit.
2. Jos sivu tai rajapinta ei ole tavoitettavissa, tarkista käänteinen välityspalvelin ja TLS-määritys.
3. Jos asiakas on merkitty tuntemattomaksi tai offline-tilaan, tarkista sen Reporting Agentin ja Watcherin ajastimet sekä tuoreet journal-merkinnät.
4. Jos telemetria puuttuu, tarkista `lums-telemetry.timer`, `lums-telemetry.service` sekä asiakkaan ja palvelimen määritykset.
5. Jos varmuuskopioista varoitetaan, tarkista määritetty polku, tiedostojärjestelmän oikeudet, vapaa tila ja viimeaikaiset varmuuskopiolokit.
6. Kirjaa havaittu tila ja aikaleimat ennen muutosten tekemistä.

Katso diagnostiikkakomennot ohjeesta [Vianmääritys](Vianmääritys.md) ja säännölliset ylläpito- sekä varmuuskopiointiohjeet ohjeesta [Ylläpito ja varmuuskopiot](Ylläpito%20ja%20varmuuskopiot.md). Englanninkieliset lähteet: [troubleshooting.md](../../../troubleshooting.md) ja [administration.md](../../../administration.md).
