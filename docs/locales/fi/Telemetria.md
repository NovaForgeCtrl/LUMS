# LUMS-suorittimen, muistin ja verkon telemetria

## Yleiskatsaus

Valinnainen LUMS-telemetria-agentti kerää hallitusta Linux-järjestelmästä suorittimen ja muistin käyttöasteen, verkkolaskurit sekä rajatun järjestelmätilannekuvan ja lähettää mittaukset LUMS-palvelimelle.

Palvelin tallentaa telemetrianäytteet ja tarjoaa todennetun historiarajapinnan, jota asiakkaan telemetrianäkymä käyttää.

Telemetria on erillinen olemassa olevasta LUMS Reporting Agentista ja Watcherista. Se ei korvaa kumpaakaan eikä suorita pakettipäivityksiä.

## Osat

| Osa | Vastuu |
| --- | --- |
| `agent/telemetry.py` | Kerää suorittimen, muistin, järjestelmän, verkon, antureiden, palveluiden ja säilöjen mittarit |
| `agent/lums-telemetry.service` | Suorittaa telemetria-agenttia rajoitettuna systemd-palveluna |
| `agent/lums-telemetry.timer` | Ajastaa telemetrian keruun toistuvasti |
| `server/app.py` | Todentaa lähetykset, validoi mittarit ja tallentaa näytteet |
| `server/static/telemetry.js` | Näyttää laitejoukon yleiskatsauksen, historiakaaviot ja rengasmittarit |

## Mittaukset

Jokaisessa näytteessä ovat pakollisina kenttinä:

- `cpu_percent`: suorittimen käyttöaste välillä 0–100.
- `memory_percent`: muistin käyttöaste välillä 0–100.
- `memory_total_bytes`: havaittu muistin kokonaismäärä tavuina.
- `memory_available_bytes`: käytettävissä olevan muistin määrä tavuina.

Agentin versio 1.1.0 ja uudemmat lähettävät myös kaksi valinnaista kumulatiivista laskuria:

- `network_rx_bytes`: käynnistyksen jälkeen vastaanotettujen tavujen määrä kaikilla muilla kuin loopback-verkkoliitännöillä.
- `network_tx_bytes`: käynnistyksen jälkeen lähetettyjen tavujen määrä kaikilla muilla kuin loopback-verkkoliitännöillä.

Molemmat laskurit on lähetettävä yhdessä ei-negatiivisina kokonaislukuina. Vanhemmat agentit toimivat edelleen, vaikka ne eivät lähetä niitä; tällöin koontinäyttö ei näytä kyseisen asiakkaan verkkotietoja. Palvelin tallentaa raakalaskurit ja laskee tavua sekunnissa peräkkäisistä näytteistä tietoja haettaessa. Nopeutta ei näytetä ensimmäisestä näytteestä, laskurin nollauduttua (esimerkiksi uudelleenkäynnistyksen jälkeen) eikä silloin, kun näytteiden väli on yli viisi minuuttia.

Agentin versio 1.2.0 ja uudemmat ilmoittavat lisäksi rajatun järjestelmätilannekuvan:

- kuormituksen keskiarvo, käyttöaika, käyttöjärjestelmä, ydin ja juuritiedostojärjestelmän käyttö;
- kunkin verkkoliitännän linkkitila, tavulaskurit, virheet ja pudotukset;
- määritetyt DNS-palvelimet sekä parhaaseen yritykseen perustuvat yhdyskäytävän, DNS:n ja internetin tavoitettavuustiedot;
- lämpötila- ja tuuletinlukemat, jos ydin tarjoaa ne;
- valittujen systemd-palveluiden tilat, käyttöajat ja uudelleenkäynnistysmäärät sekä Docker- ja Podman-säilöjen nimet ja yhdenmukaistetut tilat, kun paikalliset työkalut ja oikeudet sallivat vain luku -tarkastelun;
- levyn käyttöaste jokaisessa telemetrianäytteessä historiakaavioita ja kynnysarvotapahtumien arviointia varten.

Agentin versio 1.3.0 ja uudemmat ilmoittavat myös rajatut yhteenvetotiedot käyttötapahtumista: epäonnistuneiden SSH-kirjautumisten määrät ja aikaleimat, tuoreet journal-varoitus- ja virhemäärät, kirjautumis- ja uloskirjautumisaikaleimat sekä viimeaikaisten käynnistysten journal-merkintöjen ensimmäiset ja viimeiset aikaleimat. Raakoja journal-viestejä, käyttäjänimiä tai lähdeosoitteita ei lähetetä. Kukin journal-kysely rajataan 500 osuvaan tietueeseen; koontinäyttö näyttää määrän 500 muodossa `500+`. Käynnistys- ja kirjautumishistoria rajataan 10 käynnistykseen ja 20 kirjautumis-/uloskirjautumistapahtumaan.

Palvelin laskee kunkin verkkoliitännän siirtonopeuden peräkkäisistä näytteistä. Palvelu-, säilö-, lämpötila-, tuuletin- ja tapahtumatiedot tallennetaan vain uusimpana tilannekuvana, eikä niitä kopioida jokaiseen historiatietueeseen. Käyttöjärjestelmän tarjoamat tai sallimat valinnaiset mittarit, joita ei ole saatavilla, näytetään puuttuvina. Agentti ei käynnistä, pysäytä eikä muokkaa palveluita tai säilöjä. Agenttipalvelulle ei anneta Docker-socketin käyttöoikeutta; säilötiedot eivät ole saatavilla, ellei suoritusympäristö jo salli palvelutilin tarkastella niitä.

Telemetrian systemd-yksikkö kuuluu ryhmään `systemd-journal` vain luku -journal-käyttöä varten. Tämä antaa pääsyn järjestelmälokeihin, mutta agentti lähettää vain edellä kuvatut rajatut yhteenvedot. Palveluiden oletussallittujen luettelo sisältää LUMS-, Docker- ja SSH-yksiköt. Voit ohittaa sen agentin ympäristötiedostossa pilkuilla erotetulla `LUMS_MONITORED_SERVICES`-arvolla; vain kelvolliset `.service`-yksikköjen nimet hyväksytään.

Yhdyskäytävän tavoitettavuus tarkistetaan yhdellä ping-paketilla, jos ping on käytettävissä. DNS:n tavoitettavuus tarkistetaan lyhyellä `getent`-haulla ja internetin tavoitettavuus lyhyellä TCP-yhteysyrityksellä osoitteeseen `1.1.1.1:443`. Tarkistukset ovat vain suuntaa-antavia, ja tulos voi johtua palomuurikäytännöstä eikä katkoksesta.

Palvelin määrittää näytteen aikaleiman ja hylkää virheelliset hyötykuormat.

Kun palvelin on päivitetty, suorita tietokantamigraatio kerran (`python3 server/security_migration.py`), jotta verkkosarakkeet, uusimman järjestelmätilan taulu ja tapahtumahistoria ovat käytettävissä. Päivitä agentti jokaisessa asiakkaassa, jotta uudet mittarit alkavat tulla. Jos haluat seurata myös LUMS-palvelinta, rekisteröi se asiakkaaksi ja asenna/määritä telemetria-agentti myös kyseiselle isännälle.

## Tietoturva ja yksityisyys

Telemetrian päätepiste edellyttää asiakkaan todennusta määritetyllä LUMS-asiakastunnisteella.

Agentti lähettää pyynnöt HTTPS-yhteydellä etäpalvelimeen. Selväkielinen HTTP sallitaan vain osoitteissa `localhost`, `127.0.0.1` ja `::1`. Yhteydet etäpalvelimeen edellyttävät HTTPS:ää. Varmenteen tarkistukseen voi määrittää CA-tiedoston.

Agentti ei sisällytä asiakastunnistetta JSON-hyötykuormaan eikä kirjaa sitä lokiin. systemd-palvelu käyttää rajoitettua suoritusympäristöä eikä tarvitse pääkäyttäjän oikeuksia kuvattujen mittareiden keräämiseen.

Telemetria sisältää järjestelmäresursseja ja käyttötietoja, ei pakettipäivityksiä eikä mielivaltaisten komentojen tulosteita. Liitäntäosoitteet, DNS-palvelimet, palveluiden nimet ja säilöjen nimet voivat olla arkaluonteisia infrastruktuuritietoja; koontinäytön ja rajapinnan käyttö on suojattu `clients.view`-oikeudella.

## Tietojen säilytys

Palvelin poistaa yli seitsemän päivää vanhat telemetrianäytteet käsitellessään uusia telemetrialähetyksiä.

Todennettu historiapäätepiste hyväksyy aikavälin 1–168 tuntia. Käyttö edellyttää asianmukaista asiakkaiden katseluoikeutta. Suuret tulosjoukot voidaan harventaa enintään 1 000 näytteeseen.

`/health`-koontinäyttö tarjoaa 1 tunnin, 24 tunnin ja 7 päivän historiavälit sekä päivittää näytetyt tiedot viiden sekunnin välein. Se näyttää suorittimen, muistin ja levyn käyttöasteen sekä yhteenlasketun verkkohistorian lisäksi valitun asiakkaan reaaliaikaiset levy-, kuormitus-, käyttöaika-, ydin-, käyttöjärjestelmä-, liitäntä-, yhteys-, anturi-, palvelu- ja säilötiedot. Se näyttää myös laitejoukon yleiskatsauksen (suodatettavissa tilan, vanhentuneen telemetrian tai suuren kuormituksen mukaan, haettavissa ja lajiteltavissa) sekä asiakaskohtaiset tiedot. Suorittimen ja muistin voi esittää viivakaaviona, aluekaaviona tai nykyarvon rengasmittarina; selain muistaa valitun esitystavan. Verkkoliikenne esitetään lataus- ja lähetysnopeuksina. Yli kaksi minuuttia vanha telemetria merkitään vanhentuneeksi. Laitejoukon yleiskatsaus käyttää `/api/telemetry/overview`-päätepistettä, joka edellyttää asiakkaiden katseluoikeutta. Historiapyynnöt rajataan 1–168 tuntiin ja ne voidaan harventaa enintään 1 000 näytteeseen. systemd-ajastin suorittaa kertaluonteisen agentin viiden sekunnin välein; todellinen näytteenottoväli riippuu palvelun suorituksen kestosta ja verkkoyhteydestä. Koontinäyttö näyttää myös viimeaikaiset SSH-epäonnistumiset, journal-varoitus- ja virhemäärät sekä kirjautumis-/uloskirjautumis- ja käynnistyshistorian. Kynnysarvovaroitukset käyttävät kirjautuneen käyttäjän määritettäviä suorittimen, RAM-muistin ja levyn rajoja. Journal-määrät kattavat enintään 500 osuvaa tietuetta kyselyä kohden. Viimeisin onnistunut varmuuskopion luonti luetaan palvelimen auditointilokista; se ei ole palautustesti.

Jokainen käyttäjä voi tallentaa omat suorittimen, RAM-muistin ja levyn kynnysarvonsa väliltä 50–99 %. Oletusarvo on 90 %. Kynnysarvojen ylitykset ja yli kahden minuutin telemetriakatkot näkyvät tapahtumahistoriassa. Kynnysarvohälytykset johdetaan säilytetyistä näytteistä ja ne käyttävät kirjautuneen käyttäjän rajoja; palvelun tilasiirtymät ja uudet SSH-epäonnistumisaikaleimat kirjataan tietoja vastaanotettaessa. Tapahtumia säilytetään enintään seitsemän päivää, ja tapahtumapäätepiste palauttaa enintään 500 merkintää.

Valitusta asiakkaasta ja aikavälistä voi viedä CSV- ja JSON-tiedostoja. Historialataukset sisältävät kaikki kyseisen aikavälin säilytetyt näytteet; kaavioiden pisteiden määrä on enintään 1 000. Vienti edellyttää `clients.view`-oikeutta, eikä selain tallenna sitä välimuistiin.

Wazuh ja Suricata voidaan ottaa käyttöön valinnaisina käyttäjäkohtaisina tilariveinä koontinäytössä. Rivien tiedot kuvaavat vain määritettyjen systemd-palveluiden tilaa; LUMS ei yhdistä niiden rajapintoihin eikä kerää niiden hälytyksiä. Lisää raportoitava palvelu, kuten `wazuh-agent.service`, `wazuh-manager.service` tai `suricata.service`, agentin `LUMS_MONITORED_SERVICES`-sallittujen luetteloon. LUMS ei tarvitse eikä tallenna integraatiotunnuksia.

## Määritys

Telemetria-agentti käyttää ympäristömuuttujia `LUMS_BASE`, `LUMS_TOKEN` ja valinnaisesti `LUMS_CA_FILE`. Etäpalvelinyhteydet edellyttävät HTTPS:ää. Katso asennus- ja määritysohjeet tiedostosta [Asennus ja päivitykset](Asennus%20ja%20päivitykset.md) sekä englanninkielisestä [install.md](../../../install.md).

## Asennus ja käyttö

Telemetriapalvelu on erillinen tavallisesta LUMS-asiakasagentista. Päivitä Debianissa ensin asiakkaan LUMS-arkistokopio ja suorita sen juurihakemistosta `sudo bash scripts/install-telemetry-agent.sh`. Asennusohjelma tarkistaa, että `/etc/default/lums-agent` määrittää `LUMS_BASE`- ja `LUMS_TOKEN`-arvot, asentaa nykyisen kerääjän ja systemd-yksiköt, ottaa ajastimen käyttöön ja lähettää testinäytteen. Se ei koskaan tulosta tunnistetta.

Tarkista ajastin ja palvelu komennoilla `systemctl status lums-telemetry.timer` ja `systemctl status lums-telemetry.service`. Tarkastele tuoreita palvelulokeja komennolla `journalctl -u lums-telemetry.service -n 30 --no-pager`. Kertaluonteisen palvelun passiivinen tila ajastettujen suoritusten välillä ei välttämättä ole virhe; tarkista myös ajastin ja viimeaikaiset lokit.

`/monitoring`-sivu erottaa näytteen puuttumisen, yksityiskohtaisia tilannekuvia sisältämättömän perustelemetrian ja vanhentuneen tilannekuvan toisistaan sekä näyttää nämä asiakkaan puolen tarkistukset. Älä liitä tai jaa tunnistetta vianmäärityksen yhteydessä.

## Vianmääritys

- **Näytteitä ei näy:** Tarkista palvelimen URL-osoite, asiakkaan tunniste ja todennus.
- **TLS-virheitä:** Tarkista palvelimen varmenne ja määritetty CA-tiedosto.
- **Palveluhäiriöt:** Tarkastele palvelun journalia.
- **Historia puuttuu:** Tarkista asiakkaiden katseluoikeudet ja pyydetty aikaväli (1–168 tuntia).

Koontinäytön tilakynnyksistä ja varmuuskopiotilan ilmaisimen rajoituksista kerrotaan ohjeessa [LUMS-terveystila](LUMS-terveystila.md), jonka englanninkielinen lähde on [LUMS_Health_Dashboard.md](../../../LUMS_Health_Dashboard.md). Katso myös [Vianmääritys](Vianmääritys.md), [Asennus ja päivitykset](Asennus%20ja%20päivitykset.md) sekä englanninkielinen [troubleshooting.md](../../../troubleshooting.md).
