# Tuote

<!-- impeccable:product-schema 1 -->

## Alusta

web

## Käyttäjät

Linux-järjestelmänvalvojat ja IT-tiimit, jotka vastaavat useiden Linux-järjestelmien keskitetystä hallinnasta ja pitämisestä ajan tasalla. Tuotteen tulee soveltua myös yksittäiselle järjestelmänvalvojalle, pienelle IT-tiimille ja tarkoituksenmukaisiin hallittujen palveluiden ympäristöihin.

## Tuotteen tarkoitus

LUMS tarjoaa keskitetyn näkymän hallittuihin asiakkaisiin, asennettuihin ohjelmistoihin, saatavilla oleviin päivityksiin ja päivitystöiden suoritukseen. Se auttaa järjestelmänvalvojia käynnistämään työt harkitusti ja varmistamaan niiden tulokset sen sijaan, että päivityksiä sovellettaisiin sokkona kaikkiin järjestelmiin.

## Käyttöympäristö

Järjestelmänvalvojat käyttävät LUMSia päivittäisessä työssä laitekannan kunnon, telemetrian, ohjelmistojen ja päivitysten tarkasteluun; kohdennettujen päivitystöiden käynnistämiseen; suoritushistorian tarkasteluun; sekä käyttäjien käyttöoikeuksien, valvontatietojen ja tietokannan varmuuskopioiden ylläpitoon. Infrastruktuurin topologiaan voidaan yhdistää rekisteröityjä LUMS-asiakkaita sekä manuaalisesti ylläpidettyjä järjestelmiä ja niiden välisiä suhteita.

## Ominaisuudet ja rajoitukset

- Rooli- ja käyttöoikeuspohjainen pääsynhallinta, valvontalokitus, tietokannan varmuuskopiointi, pakettien näkyvyys ja asiakkaiden päivitystyöt ovat keskeisiä operatiivisia ominaisuuksia.
- Järjestelmäpäivitysten on oltava hallittuja ja jäljitettävissä, ja virheistä on ilmoitettava totuudenmukaisesti. Älä anna ymmärtää päivityksen onnistuneen, elleivät sen tarkistukset läpäise.
- Rekisteröidyt asiakkaat ja niiden raportoimat tiedot ovat käytettävissä oleva automaattisesti tuotavan infrastruktuuriluettelon lähde. Muu infrastruktuuri ja suhteet on lisättävä nimenomaisesti manuaalisesti, ellei tulevaa integraatiota ole vahvistettu.
- Infrastruktuuriluettelon muokkaaminen on sallittu vain järjestelmänvalvojille.
- Älä anna ymmärtää, että LUMS etsii automaattisesti mielivaltaisia virtuaalikoneita, kontteja, verkkolaitteita tai riippuvuuksia.

## Brändisitoumukset

- Säilytä LUMS-nimi ja nykyinen logo.
- Käyttäjä kutsuu stadionteemaa nimellä “LUMS-Stadion” ja pyysi käyttämään nykyistä stadiontaustakuvaa järjestelmän tilan koontinäytössä ja reaaliaikaisessa seurannassa.

## Käytettävissä oleva näyttö

- Nykyinen tuotekäyttöliittymä ja teemaresurssit: `server/static/style.css`, `server/static/images/LUMS_Logo.jpg` ja `server/static/images/lumsstadium.jpg`.
- Rekisteröityjen asiakkaiden, telemetrian, päivitystöiden, RBAC:n, valvonnan ja varmuuskopioinnin toteutukset ovat `server/`-paketissa.
- Vahvistettuja asiakasväitteitä, tuotteen suorituskykymittareita tai automaattista infrastruktuurin etsintäintegraatiota ei ole toimitettu.

## Tuoteperiaatteet

- Pidä järjestelmänvalvojat järjestelmämuutosten ohjaksissa.
- Tee toiminnan tila ja päivitysten tulokset todennettaviksi.
- Valvo käyttöoikeuksia palvelimella, älä pelkästään käyttöliittymässä.
- Erota asiakkaiden raportoimat tosiasiat manuaalisesti ylläpidetystä luettelosta.
