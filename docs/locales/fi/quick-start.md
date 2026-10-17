# LUMSin pikaopas — suomi

Tämä lyhyt opas on tarkoitettu LUMSin tai Linuxin uusille käyttäjille. Se ei
ole kaikkien teknisten käsikirjojen täydellinen käännös; projektin yksityiskohtaisia
ohjeita ylläpidetään englanniksi. [Kielihakemisto](../../README.md).

## Mikä LUMS on?

LUMS hallitsee Linux-tietokoneita keskitetysti. Palvelin näyttää asiakkaat,
asennetut ohjelmistot ja saatavilla olevat päivitykset. Kunkin asiakkaan Agent
suorittaa hyväksytyt toiminnot tietokoneen omalla paketinhallinnalla: Debianissa
ja Ubuntussa APT:llä sekä Arch Linuxissa pacmanilla. LUMS ei asenna kaikkia
päivityksiä automaattisesti.

## Jos käytät vain LUMSia

Avaa ylläpitäjältä saamasi verkko-osoite ja kirjaudu sisään omalla
käyttäjätililläsi. Käytettävissä olevat toiminnot riippuvat käyttöoikeuksistasi.
Älä jaa tiliäsi tai asiakkaan tunnistetta muiden kanssa. Valitse kieli
kirjautumissivun oikeasta yläkulmasta; sisäänkirjautumisen jälkeen LUMS voi
tallentaa valinnan käyttäjätilillesi.

## Asennus ja ylläpito

Testin läpäisy ei tarkoita, että tuotantopalvelin olisi asennettu.
Turvallinen tuotantoympäristö tarvitsee muun muassa HTTPS-yhteyden, suojatun
sovellussalaisuuden, pysyvän tietokantatallennuksen ja tarkistetut varmuuskopiot.
Palvelin ja Linux-asiakkaat määritetään erikseen. Noudata
[asennusohjetta](../../../install.md) huolellisesti. Korvaa paikkamerkit, kuten
`LUMS-SERVER`, todellisilla arvoilla ja tarkista jokainen polku ennen komennon
suorittamista. Jos LUMS on jo käytössä, noudata
[ylläpito-ohjeen](../../../administration.md) päivitysohjetta äläkä
ensiasennuksen vaiheita.

Älä koskaan poista Docker-taltiota `lums-data` tavallisen päivityksen aikana:
se sisältää tietokannan. Säilytä myös salaisuuden ja varmuuskopioiden nykyiset
liitokset sekä kontin suojausasetukset. Esimerkkikomennot eivät sovi kaikkiin
ympäristöihin; vertaa niitä ensin käynnissä olevan kontin asetuksiin.

## Ensimmäiset tarkistukset ongelmatilanteessa

Palvelimella nämä komennot näyttävät kontin tilan, viimeaikaiset sovelluslokit
ja Nginxin tilan:

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

`sudo` voi pyytää Linux-käyttäjäsi salasanaa. Tarkistukset eivät muuta
asetuksia. Älä aloita poistamalla tietokantaa tai Docker-taltiota,
käynnistämällä konttia pääkäyttäjän oikeuksilla tai poistamalla suojauksia.
Poista salasanat, tunnisteet, avaimet ja henkilötiedot ennen lokien
jakamista.

## Yksityiskohtaiset ohjeet

* [Projektin yleiskuvaus](../../../README.md)
* [Asennus ja päivitykset](../../../install.md)
* [Ylläpito ja varmuuskopiot](../../../administration.md)
* [Vianmääritys](../../../troubleshooting.md)
* [Tietoturvamalli](../../../security.md)
