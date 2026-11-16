# LUMS-infrastruktuurin topologia

## Tarkoitus

Todennettu `/infrastructure`-sivu yhdistää rekisteröidyt LUMS-asiakkaat ja manuaalisesti ylläpidetyn infrastruktuurin yhteen riippuvuusnäkymään. Se on luettelo ja yhteyskartta, ei automaattinen verkon etsintä- tai määritystenhallintajärjestelmä.

## Tietolähteet ja omistajuus

- Rekisteröidyt LUMS-asiakkaat luetaan olemassa olevasta asiakasrekisteristä, ja ne näkyvät automaattisesti ilmoitetun isäntänimen, IP-osoitteen, käyttöjärjestelmän ja käytössä/ilmoittaa-tilan kanssa. Myös käytöstä poistetut asiakkaat pysyvät näkyvissä, jotta olemassa olevat suhteet ovat ymmärrettäviä. Nämä merkinnät ovat topologiasivulla vain luku -tilassa; hallitse asiakasta normaalin asiakashallinnan kautta.
- Palvelimet, virtuaalikoneet, säilöt, verkkolaitteet, palvelut ja tallennustila voidaan lisätä manuaalisesti isäntänimen, IP-osoitteen, roolin, sijainnin ja muistiinpanojen avulla.
- Suhteet ylläpidetään manuaalisesti. Tuetut tyypit ovat `depends on`, `hosts`, `connects to` ja `runs on`.
- Sivu ei skannaa aliverkkoja, kysy pilvipalveluiden rajapintoja eikä päättele riippuvuuksia palvelu- tai säilömäärityksistä. Pidä manuaalisesti lisätty luettelo ja suhteet ajan tasalla.

## Käyttöoikeudet ja auditointi

Käyttäjät, joilla on `clients.view`, voivat tarkastella topologiaa. Manuaalisten merkintöjen tai suhteiden luominen, muokkaaminen ja poistaminen on rajattu ylläpitäjille, joilla on `infrastructure.manage`-oikeus. Muutokset edellyttävät sovelluksen normaalia todennettua istuntoa, CSRF-suojausta ja auditointikirjausta.

`infrastructure.manage` riippuu oikeuksista `users.manage` ja `clients.view`, ja se myönnetään ylläpitäjille tietokantamigraatiossa `016-infrastructure-topology`. Manuaalisesti hallitun solmun poistaminen poistaa myös sen suhdetietueet. Asiakkaan poistaminen poistaa siihen viittaavat suhteet.

## Kartan tulkinta

Kartta järjestää solmut luokittain ja piirtää kunkin tallennetun suhteen suunnattuna reunana. **Jaettu riippuvuus** on solmu, johon vähintään kahdesta muusta solmusta osoittaa `depends on` -suhde. Tämä on hyödyllinen merkki mahdollisesta keskitetystä vikakohdasta, ei kattava käytettävyys- tai vaikutusanalyysi. Kartta ei huomioi redundanssia, vikasietoisuutta, kapasiteettia, verkon segmentointia eikä kirjaamattomia riippuvuuksia.

Tarkista tarkat isäntänimi-, IP-osoite-, rooli-, sijainti- ja suhdetiedot luettelo- ja suhdetaulukoista. Topologia käyttää valittuna olevaa LUMS-teemaa ja toimii yhteisen kokoontaitettavan sivupalkin kanssa.

Englanninkielinen lähde: [LUMS_Infrastructure_Topology.md](../../../LUMS_Infrastructure_Topology.md).
