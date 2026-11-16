# LUMSin hälytysten hallinta: nykyinen toteutus

Tässä muistiossa kuvataan LUMSissa nykyisin oleva hälytysten hallintakoodi. Se on koodiviite, ei ominaisuuksien tiekartta eikä lupaus siitä, että kaikki näkyvät käyttöliittymän ohjaimet toimivat. Toteutus keskittyy tiedostoihin `server/alerts.py` ja `server/alerts_routes.py`.

## Toteutetut ominaisuudet

LUMS tallentaa hälytyssäännöt, hälytystiedot ja hälytystilojen historian SQLite-tietokantaan. Flask-blueprint luo pyyntökohtaisen `AlertManager`-olion sovelluksen tietokantayhteystehtaalla. Hallintaolio lataa säännöt ja ratkaisemattomat hälytykset tietokannasta jokaista pyyntöä varten.

Nykyinen API tukee seuraavia toimintoja:

- hälytyssääntöjen luettelointi, luominen, päivittäminen ja poistaminen;
- olemassa olevan käytössä olevan säännön hälytyksen manuaalinen käynnistäminen;
- aktiivisten hälytysten ja sivutettavan hälytyshistorian tarkastelu;
- aktiivisen hälytyksen kuittaaminen, ratkaiseminen ja manuaalinen eskalointi.

Hälytysten vakavuusarvot ovat `critical`, `warning` ja `info`. Tallennetut hälytystilat ovat `triggered`, `acknowledged`, `resolved` ja `escalated`. Kuittaus-, ratkaisu- ja eskalointimuutokset kirjataan `alert_history`-tauluun. Ratkaistut hälytykset poistetaan hallintaolion aktiivisten hälytysten kokoelmasta, mutta ne säilyvät tietokannassa.

## Tärkeät rajoitukset

Sääntömalliin tallennetaan ehto, kynnysarvo, vakavuus, eskalointipolku, ryhmittelyasetus ja deduplikointiasetus. Nykyinen palvelin **ei** arvioi ehtoja telemetriaa tai muita mittauksia vasten. Sääntö ei laukea automaattisesti: todennetun kutsujan on lähetettävä pyyntö `POST /alerts/trigger`-päätepisteeseen. Ryhmittely- ja deduplikointiasetukset tallennetaan, mutta niitä ei sovelleta. Kun hälytys käynnistetään, hallintaolio yrittää lähettää sen sääntöön määritetyn eskalointipolun palveluntarjoajille. Verkkosovellus luo kunkin hallintaolion tyhjällä palveluntarjoajakartalla, eivätkä integraatiopäätepisteet voi määrittää palveluntarjoajia; siksi sovelluksen kautta käynnistetyille hälytyksille ei tällä hetkellä toimiteta ilmoituksia.

`AlertManager` määrittelee sähköposti-, Slack-, PagerDuty- ja yleisen webhook-palveluntarjoajan luokat, mutta niitä ei määritetä sovelluksen kautta. Integraatio-API ilmoittaa tarkoituksella, etteivät integraatiot ole käytettävissä, ja palauttaa tilan `501 Not Implemented` määritys-, testaus- ja poistopyynnöille. Ilmoitusten toimitusta ei pidä olettaa. Myös `POST /alerts/clear-all` palauttaa `501`-vastauksen, jotta hälytyshistoriaa ei voi poistaa kyseisen päätepisteen kautta.

`/alerts/`-sivu on yksinkertainen palvelinpuolella renderöity yleisnäkymä. Sen sääntö-, historia- ja integraatiovälilehtien ohjaimet sekä hälytystoimintojen painikkeet eivät muodosta täydellistä vuorovaikutteista hallintaliittymää. Käytä dokumentoitua API-käyttäytymistä totuuden lähteenä sen sijaan, että olettaisit näkyvän painikkeen suorittavan toiminnon. Nykyinen toteutus ei tarjoa reaaliaikaisia push- tai WebSocket-päivityksiä.

## Reitit ja käyttöoikeuksien valvonta

Kaikki reitit edellyttävät todennettua verkkosovellusistuntoa.

| Menetelmä | Reitti | Käyttöoikeus | Nykyinen toiminta |
| --- | --- | --- | --- |
| `GET` | `/alerts/` | `alerts.view` | Renderöi hälytysten yleisnäkymän |
| `GET` | `/alerts/rules` | `alerts.view` | Luettelee tallennetut säännöt |
| `POST` | `/alerts/rules` | `alerts.manage` | Luo validoidun säännön |
| `PUT` | `/alerts/rules/<rule_id>` | `alerts.manage` | Päivittää tallennetun säännön |
| `DELETE` | `/alerts/rules/<rule_id>` | `alerts.manage` | Poistaa säännön, jos tietokantarajoitukset sallivat sen |
| `GET` | `/alerts/current` | `alerts.view` | Palauttaa aktiiviset hälytykset |
| `GET` | `/alerts/history` | `alerts.view` | Palauttaa hälytyshistorian |
| `POST` | `/alerts/trigger` | `alerts.manage` | Luo manuaalisesti hälytyksen käytössä olevalle säännölle |
| `POST` | `/alerts/<alert_id>/acknowledge` | `alerts.manage` | Kirjaa kuittauksen |
| `POST` | `/alerts/<alert_id>/resolve` | `alerts.manage` | Ratkaisee aktiivisen hälytyksen |
| `POST` | `/alerts/<alert_id>/escalate` | `alerts.manage` | Kasvattaa eskalointilaskuria manuaalisesti |
| `POST` | `/alerts/clear-all` | `alerts.manage` | Poistettu käytöstä; palauttaa `501` |
| `GET` | `/alerts/integrations` | `alerts.view` | Palauttaa tyhjän luettelon ja `available: false` |
| `POST` / `DELETE` | `/alerts/integrations/...` | `alerts.manage` | Poistettu käytöstä; palauttaa `501` |

Tilaa muuttavat reitit edellyttävät CSRF-suojausta ja asianmukaista käyttöoikeutta. Käyttöoikeudet tarkistetaan palvelimella. `alerts.manage` edellyttää `alerts.view`-käyttöoikeutta; roolien käyttöoikeuksia ylläpidetään tietoturvamigraatiolla ja käyttöoikeusmäärityksillä.

## Pysyvät taulut

`AlertManager` alustaa seuraavat taulut luonnin yhteydessä:

- `alert_rules`: sääntöjen määritelmät ja määritetyt arvot;
- `alerts`: hälytystiedot ja niiden nykyinen elinkaaritila;
- `alert_history`: kuittaus-, ratkaisu- ja eskalointihistoria;
- `notification_integrations`: varattu integraatioiden määritysmalli;
- `alert_notifications_log`: varattu ilmoitusten toimituslokin malli.

Kaksi viimeistä taulua eivät tarkoita, että integraatiot olisivat käytettävissä. HTTP-integraatiopäätepisteet pysyvät poissa käytöstä, kunnes turvallinen pysyvä määritys ja ilmoitusten toimitus on toteutettu.

## Varmennus

Hälytysreitit, käyttöoikeuksien valvonta, pyynnön sisältöjen validointi, pysyvä tallennus ja elinkaaren toiminta testataan tiedostossa `tests/test_alerts.py`. Suorita asiaankuuluvat testit uudelleen käyttöön otettavaa versiota vasten. Testisarjan läpäisy ei tee käytöstä poistetuista integraatioreiteistä tai arvioimattomista säännöistä käytettävissä olevia ominaisuuksia.

## Aiheeseen liittyvä koodi

- `server/alerts.py`
- `server/alerts_routes.py`
- `server/security.py`
- `server/security_migration.py`
- `tests/test_alerts.py`
