# LUMS — Valinnainen teemajärjestelmä

> **Yksi LUMS · monta käyttöliittymää · sama taustajärjestelmä**

LUMS tarjoaa valinnaisen selainpuolen teemajärjestelmän, jonka avulla käyttöliittymän visuaalista ilmettä voidaan muuttaa LUMSin varsinaista toiminnallisuutta muuttamatta.

Teemat ovat vain esitystaso. Ne eivät korvaa, muuta tai ohita LUMSin taustajärjestelmää, todennusta, valtuutusta, päivitysten suoritusta, paketinhallintaa, asiakashallintaa, töiden käsittelyä tai turvakontrolleja.

Teemajärjestelmän tarkoitus on mukauttaa LUMSia erilaisiin visuaalisiin mieltymyksiin ja pitää sovellus silti yhtenäisenä.

## Toteutuksen tila ja totuuden lähde

Nykyinen selainpuolen toteutus on tiedostossa `server/static/theme.js`. Se tukee teemoja `standard`, `LUMSStadium`, `golf`, `nerd`, `geek` ja `admin`; tallentaa valinnan selaimen `localStorage`-tallennukseen avaimella `lums-theme`; ja käyttää `standard`-teemaa, jos tallennettu tunniste puuttuu tai on virheellinen. `nerd`-teema käynnistää matriisieffektin ja `geek`-teema verkkovaikutelman. Teeman valinta on selainkohtainen asetus, ei tiliasetus tai palvelinpuolen valtuutustila.

Tässä viitteessä kuvataan myös suunnitteluvaatimuksia ja käsitteellisiä esimerkkejä. Ilmaisut kuten ”pitäisi”, ”täytyy” tai ”tulevaisuudessa” kuvaavat arkkitehtuuriohjeita, eivät todisteita siitä, että jokin tietty visuaalinen ominaisuus tai saavutettavuustoiminto olisi toteutettu. Tarkista lähdekoodista nykyinen toiminta ennen kuin käsittelet käsitettä julkaistuna ominaisuutena.

---

## 1. Yleiskatsaus

Valinnaisen teemajärjestelmän avulla LUMSin verkkokäyttöliittymässä voi olla useita visuaalisia ilmeitä, vaikka taustalla käytetään samaa sovelluksen taustajärjestelmää.

Teema voi muuttaa:

* värejä
* typografiaa
* taustoja
* koriste-elementtejä
* visuaalisia korostuksia
* navigoinnin ulkoasua
* animaatioita
* valinnaisia visuaalisia tehosteita
* sivukohtaista esitystapaa

Teema ei saa muuttaa:

* käyttäjien käyttöoikeuksia
* käytettävissä olevia API-päätepisteitä
* todennuksen toimintaa
* valtuutuspäätöksiä
* CSRF-suojausta
* asiakkaiden todennusta
* päivitysten suoritusta
* paketinhallinnan käyttöoikeuksia
* työn tilan käsittelyä
* valvontalokitusta
* tietokannan toimintaa
* turvallisuusrajoja

Periaate on yksinkertainen:

> **Teemat muuttavat sitä, miltä LUMS näyttää, eivät sitä, mitä LUMS saa tehdä.**

---

## 2. Suunnitteluperiaatteet

Teemajärjestelmä noudattaa useita periaatteita.

### 2.1 Valinnaisuus

Teemat ovat valinnainen käyttöliittymäominaisuus.

LUMS toimii täydellisesti, vaikka mitään lisäteemaa ei valittaisi.

LUMSin vakioilme toimii oletusesitystapana.

---

### 2.2 Selainpuolisuus

Teeman valinta kuuluu käyttöliittymään.

Teeman vaihtaminen ei saa edellyttää palvelinpuolen sovellustilan muuttamista.

Käyttäjän valitsema teema on siten esitysmieltymys, ei tilin käyttöoikeus tai taustajärjestelmän määritys.

---

### 2.3 Riippumattomuus taustajärjestelmästä

Kaikki teemat käyttävät samaa LUMSin taustajärjestelmää.

Seuraavat asiat eivät riipu valitusta teemasta:

```text
Authentication
Authorization
RBAC
Client Management
Software Inventory
Update Detection
Package Management
Update Jobs
Job Recovery
Audit Logging
Database Operations
```

Taustajärjestelmä on edelleen kaikkien turvallisuuteen ja operointiin vaikuttavien päätösten auktoritatiivinen lähde.

---

### 2.4 Teema ei ole turvallisuusmekanismi

Teemaa ei saa koskaan käyttää turvallisuusmekanismina.

Esimerkiksi toiminnon piilottaminen käyttöliittymästä ei myönnä eikä peru käyttöoikeutta.

Jos käyttäjällä ei ole lupaa toimintoon, palvelimen on hylättävä se aktiivisesta teemasta riippumatta.

Näin varmistetaan, ettei käyttöliittymän esitystapa voi muodostua valtuutusrajaksi.

---

### 2.5 Hallittu varatoiminta

Teemajärjestelmässä on aina oltava kelvollinen varateema.

Jos:

* teemaa ei ole valittu,
* tallennettu teema ei ole enää saatavilla,
* teematunniste on virheellinen,
* teeman resurssia ei voida ladata,

LUMSin pitäisi siirtyä vakioesitystapaan käyttöliittymän rikkoutumisen sijaan.

---

## 3. Käsitteellinen arkkitehtuuri

Teemajärjestelmää voi tarkastella erillisenä esityskerroksena, joka ympäröi olemassa olevaa LUMS-sovellusta.

```text
┌──────────────────────────────────────┐
│              LUMS UI                 │
│                                      │
│  ┌────────────────────────────────┐  │
│  │        Theme Presentation      │  │
│  │                                │  │
│  │ Standard / Stadium / Golf /    │  │
│  │ Nerd / Geek / Admin / ...      │  │
│  └────────────────────────────────┘  │
│                  │                   │
│                  ▼                   │
│        Common Frontend Logic        │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│             LUMS API                 │
│                                      │
│ Authentication / RBAC / Jobs /       │
│ Clients / Packages / Updates / Logs  │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│          LUMS Backend                │
│                                      │
│ Flask / SQLite / Job Processing /   │
│ Client Communication                 │
└──────────────────────────────────────┘
```

Olennainen raja on **esitystavan** ja **sovelluslogiikan** välillä.

Teemat ovat tämän rajan yläpuolella.

---

## 4. Teeman elinkaari

Käsitteellisesti teeman valinta etenee seuraavasti:

```text
User selects theme
        │
        ▼
Frontend stores selection
        │
        ▼
Theme initialization
        │
        ▼
Theme applied to UI
        │
        ▼
LUMS continues using
the same backend and permissions
```

Valinta ei luo uutta LUMS-ympäristöä.

LUMS-sovellus, taustajärjestelmä ja turvallisuusmalli ovat edelleen samat.

---

## 5. Teematunnisteet

Teemoille pitäisi käyttää vakaita sisäisiä tunnisteita näyttönimien sijaan.

Esimerkiksi:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

Tunniste on toteutuksen yksityiskohta.

Näkyvää teeman nimeä voidaan muuttaa erikseen ilman taustajärjestelmän tai sovellusarkkitehtuurin muutoksia.

Kun teematunniste poistetaan tai nimetään uudelleen, järjestelmän pitäisi tarjota varatoiminta käyttäjille, joiden selaimeen vanha tunniste on yhä tallennettu.

---

## 6. Vastuualueiden erottelu

Teemajärjestelmän vastuualue on tarkoituksella rajattu.

### Teemakerros

Vastuussa:

* visuaalisesta esityksestä
* teeman valinnasta
* teemakohtaisista tyyleistä
* valinnaisista visuaalisista tehosteista
* teemakohtaisista käyttöliittymäkoristeista
* saavutettavuuteen liittyvästä esitystavasta

### Yhteinen käyttöliittymä

Vastuussa:

* sovellustietojen näyttämisestä
* LUMS-APIen kutsumisesta
* töiden ja ohjelmistotietojen renderöinnistä
* käyttäjän vuorovaikutuksen käsittelystä
* näkyvyyden valvonnasta esitystasolla

### Taustajärjestelmä

Vastuussa:

* todennuksesta
* valtuutuksesta
* RBAC:stä
* CSRF-suojauksesta
* asiakkaiden todennuksesta
* töiden luomisesta
* töiden suorituksesta
* paketinhallinnasta
* tietokantatoiminnoista
* valvontalokituksesta
* turvallisuuspäätöksistä

Tämä vastuunjako on suunnittelun perusta.

---

## 7. Turvallisuusraja

Teemajärjestelmä ei ole valtuutuksessa luotettua koodia.

Vaikka teema muuttaisi käyttöliittymän elementtiä tai piilottaisi sen, taustajärjestelmä vastaa pyydetyn toiminnon kelpoisuuden tarkistamisesta.

Käsitteellisesti:

```text
Frontend visibility
        ≠
Backend permission
```

Esimerkiksi:

```text
Viewer
  │
  ├── Theme may display no package-management controls
  │
  └── Backend still rejects unauthorized package operations
```

Sama periaate koskee ylläpitotoimintoja, päivitystöitä, asiakashallintaa ja kaikkia muita etuoikeutettuja toimintoja.

---

## 8. Operatiivinen periaate

Teemajärjestelmän pitäisi olla näkymätön LUMSin operatiiviselle arkkitehtuurille.

Teeman vaihtaminen ei saa vaatia:

* tietokannan uudelleenrakentamista
* asiakasmääritysten muuttamista
* asiakastunnisteiden vaihtamista
* päivitysagenttien uudelleenkäynnistämistä
* päivitystöiden muuttamista
* RBAC:n muokkaamista
* verkkokonfiguraation muuttamista
* paketinhallinnan toiminnan muuttamista

Teema on esitysmieltymys, ei operatiivinen määritys.

---

## 9. Dokumentaation rajaus

Tässä asiakirjassa kuvataan valinnainen LUMS-teemajärjestelmä.

LUMSin yleiset aiheet on dokumentoitu erikseen:

* Asennus ja käyttöönotto → `install.md`
* Hallinta ja ylläpito → `administration.md`
* Vianmääritys → `troubleshooting.md`
* Turvallisuusarkkitehtuuri ja tarkastukset → `security.md`
* Projektin yleiskuvaus → `README.md`

Vastuiden erottelu estää teemadokumentaatiota muuttumasta toiseksi asennus- tai hallintaoppaaksi.

---

## 10. Ydinperiaate

Valinnaisen teemajärjestelmän voi tiivistää näin:

> **Yksi LUMS. Yksi taustajärjestelmä. Yksi turvallisuusmalli. Monta mahdollista**

# LUMS — Valinnainen teemajärjestelmä

## Osa 2 — Teeman rakenne ja valinta

## 11. Teeman rakenne

Valinnaisessa teemajärjestelmässä teeman valinta erotetaan varsinaisesta visuaalisesta esityksestä.

Teema koostuu käsitteellisesti kolmesta kerroksesta:

```text
Theme Identifier
       │
       ▼
Theme Selection
       │
       ▼
Theme Presentation
```

Tunniste määrittää, mikä teema on valittu.

Valintamekanismi ratkaisee, minkä teeman pitäisi olla aktiivinen.

Esityskerros soveltaa vastaavaa visuaalista kokoonpanoa LUMS-käyttöliittymään.

Erottelu mahdollistaa teemojen lisäämisen ja poistamisen muuttamatta LUMS-sovelluksen perusarkkitehtuuria.

---

## 12. Teeman valinta

Teeman valinta käsitellään käyttöliittymässä.

Valittua teemaa pidetään paikallisena esitysmieltymyksenä, ei palvelimella tallennettavana tilin ominaisuutena.

Käsitteellisesti:

```text
User
 │
 ▼
Theme Selector
 │
 ▼
Selected Theme Identifier
 │
 ▼
Frontend Theme Initialization
 │
 ▼
Active Theme
```

Taustajärjestelmän ei tarvitse tietää, mikä visuaalinen teema on parhaillaan valittuna.

Teeman vaihtaminen ei näin vaikuta muihin käyttäjiin.

Kaksi käyttäjää voi käyttää samaa LUMS-instanssia täysin erilaisilla visuaalisilla teemoilla.

---

## 13. Paikallinen teemamieltymys

Selain voi tallentaa valitun teeman paikallisesti.

Paikallisen tallennuksen tarkoitus on käyttömukavuus:

```text
Browser
   │
   ├── Theme preference
   │
   └── LUMS application
```

Selaimeen tallennettua teemavalintaa on siis pidettävä epäluotettavana asiakaspuolen tilana.

Palvelin ei saa koskaan tulkita sitä seuraaviksi:

* rooliksi
* käyttöoikeudeksi
* todennustilaksi
* turvallisuusasetukseksi
* ylläpitoasetukseksi

Selain voi valita ulkoasun, mutta se ei ohjaa valtuutusta.

---

## 14. Teeman alustus

Kun LUMS-käyttöliittymä ladataan, käyttöliittymä ratkaisee, minkä teeman pitäisi olla aktiivinen.

Käsitteellinen järjestys:

```text
Page Load
   │
   ▼
Read Stored Theme
   │
   ▼
Is Theme Valid?
   │
   ├── Yes ──────► Apply Theme
   │
   └── No ───────► Use Standard Theme
```

Jos teemamieltymystä ei ole tallennettu, käytetään LUMSin vakioesitystapaa.

Jos tallennettu tunniste ei ole enää tuettu, käytetään samaa varatoimintaa.

Näin vanhentunut paikallinen asetus ei riko käyttöliittymää.

---

## 15. Oletusteema

LUMSin vakioteema on perusesitystapa.

Se toimii viiteilmeenä, johon valinnaisia teemoja verrataan.

Vakioteeman pitäisi siksi olla:

* toimiva
* luettava
* saavutettava
* visuaalisesti valmis
* riippumaton valinnaisista koristeellisista resursseista

Valinnaiset teemat eivät saa olla normaalin LUMS-käytön edellytyksiä.

---

## 16. Teeman soveltaminen

Käyttöliittymä voi ilmaista aktiivisen teeman jaetun sovellustilan tai juuritason teema-attribuutin avulla.

Käsitteellisesti:

```html
<html data-theme="theme-id">
```

Tarkka toteutus voi muuttua käyttöliittymän kehittyessä.

Arkkitehtuurin olennainen vaatimus on, että aktiivinen teema voidaan tunnistaa käyttöliittymän tyylijärjestelmässä yhdenmukaisesti.

Näin teemakohtaiset tyylit pysyvät erillään sovelluksen yhteisestä rakenteesta.

---

## 17. Teemakohtaiset tyylit

Teemojen tyylit pitäisi toteuttaa ensisijaisesti CSS:llä sovellusmerkintöjen monistamisen sijaan.

Käsitteellisesti:

```text
Common HTML
     │
     ├── Standard styling
     ├── Stadium styling
     ├── Golf styling
     ├── Nerd styling
     ├── Geek styling
     └── Admin styling
```

Näin samat sovelluskomponentit ovat käytettävissä kaikissa teemoissa.

Esimerkiksi asiakastaulukko on asiakastaulukko aktiivisesta teemasta riippumatta.

Vain sen esitystapa muuttuu.

---

## 18. Jaetut sovelluskomponentit

Teemoille ei pidä luoda erillisiä LUMS-sivujen versioita.

Seuraavaa periaatetta on noudatettava:

```text
One component
       │
       ├── Theme A
       ├── Theme B
       ├── Theme C
       └── Theme D
```

Ei näin:

```text
Theme A → separate page
Theme B → separate page
Theme C → separate page
```

Sivujen monistaminen vaikeuttaisi ylläpitoa huomattavasti ja voisi aiheuttaa teemojen välisiä toiminnallisia eroja.

Teeman pitää siis koristaa yhteistä käyttöliittymää sovelluksen korvaamisen sijaan.

---

## 19. Teemojen resurssit

Teemat voivat tarvittaessa käyttää muita käyttöliittymäresursseja.

Mahdollisia resursseja ovat:

* taustakuvat
* koristegrafiikka
* kuvakkeet
* animaatiot
* visuaaliset peittokuvat
* teemakohtaiset kuvitukset

Resurssit kuuluvat käyttöliittymän esityskerrokselle.

Ne eivät saa sisältää:

* tunnistetietoja
* asiakastunnisteita
* salaisia avaimia
* tietokantatiedostoja
* todennusaineistoa
* yksityisiä operatiivisia tietoja

Teemojen resursseja on käsiteltävä julkisina käyttöliittymäresursseina.

---

## 20. Valinnaiset visuaaliset tehosteet

Jotkin teemat voivat tarjota lisätehosteita.

Esimerkkejä:

* animoidut taustat
* koristeelliset verkkotehosteet
* tunnelmaa luova liike
* teemoitetut käyttöliittymäelementit
* dynaamiset visuaaliset koristeet

Tehosteiden on pysyttävä valinnaisina.

Ne eivät saa koskaan olla tarpeen LUMSin toiminnalle.

---

## 21. Vähennetty liike

Visuaalisten tehosteiden pitäisi huomioida käyttäjät, jotka suosivat vähäisempää liikettä.

Animoitujen tai jatkuvasti muuttuvien elementtien yhteydessä teemajärjestelmän pitäisi tarjota sopiva toiminta vähennetyn liikkeen tilassa.

Käsitteellisesti:

```text
Normal motion
     │
     ├── animations enabled
     └── visual effects enabled

Reduced motion
     │
     ├── animations reduced or disabled
     └── essential interface remains functional
```

Saavutettavuus on koristeellisia animaatioita tärkeämpää.

Teeman pitää olla käytettävissä, vaikka visuaaliset tehosteet olisi poistettu käytöstä.

---

## 22. Teeman riippumattomuus

Teeman vaihtaminen ei saa aiheuttaa operatiivisia sivuvaikutuksia.

Esimerkiksi:

```text
Theme change
     │
     ├── No client restart
     ├── No agent restart
     ├── No job cancellation
     ├── No database migration
     ├── No token rotation
     └── No permission change
```

Teemajärjestelmä on siis tarkoituksella eristetty LUMSin operatiivisesta elinkaaresta.

---

## 23. Teemavirheiden käsittely

Teeman virhetilanteen pitäisi olla turvallinen.

Jos teemakohtaista resurssia tai esityskomponenttia ei voida ladata, LUMSin yhteisen käyttöliittymän pitäisi pysyä käytettävissä.

Suositeltu palautumispolku:

```text
Theme error
    │
    ▼
Fallback to standard presentation
    │
    ▼
LUMS remains usable
```

Visuaalisesta ongelmasta ei saa tulla sovelluksen saatavuusongelmaa.

---

## 24. Uuden teeman lisääminen

Uuden teeman pitää noudattaa sovelluksen toiminnan ja esitystavan nykyistä erottelua.

Käsitteellisesti:

```text
1. Define theme identifier
2. Define visual design
3. Add theme styling
4. Add optional assets
5. Add theme to selection mechanism
6. Test normal pages
7. Test different RBAC roles
8. Test reduced-motion behavior
9. Test fallback behavior
10. Verify no backend behavior changed
```

Uusi teema on valmis vasta, kun LUMSin olemassa oleva toiminnallisuus pysyy ennallaan.

---

## 25. Teeman poistaminen

Teeman poistamisenkin pitää tapahtua hallitusti.

Jos käyttäjän selaimeen on tallennettu paikallisesti poistettu teema, käyttöliittymän pitäisi havaita, ettei tunniste ole enää saatavilla, ja siirtyä vakioteemaan.

Visuaalisen teeman poistaminen ei saa tehdä käyttäjän LUMS-käyttöliittymästä käyttökelvotonta.

---

## 26. Teeman nimeäminen

Teeman nimissä pitäisi erottaa selvästi:

* sisäinen tunniste
* näyttönimi
* visuaalinen konsepti

Esimerkiksi:

```text
Internal identifier:  standard
Display name:         Standard LUMS
```

Erottelu mahdollistaa näkyvän tekstin muuttamisen ilman, että sisäistä toteutusta tarvitsee muuttaa tarpeettomasti.

---

## 27. Nykyiset teemakonseptit

Valinnainen LUMS-teemajärjestelmä on suunniteltu tarjoamaan useita visuaalisia ilmeitä yhteisessä sovelluksessa.

Tässä dokumentoidut teemakonseptit:

| Tunniste | Konsepti |
| --- | --- |
| `standard` | LUMSin vakioteema |
| `LUMSStadium` | LUMS Stadium |
| `golf` | Golf Club |
| `nerd` | Nerd Mode |
| `geek` | Geek Lab |
| `admin` | Enterprise Admin |

Teemat edustavat erilaisia visuaalisia suuntauksia, eivät eri LUMS-versioita.

Kaikki ovat osa samaa sovellusta.

---

## 28. Yksi taustajärjestelmä, monta käyttöliittymää

Suhde voidaan tiivistää näin:

```text
                     ┌── Standard
                     ├── Stadium
                     ├── Golf
                     ├── Nerd
                     ├── Geek
                     └── Admin
                           │
                           ▼
                    Common LUMS UI
                           │
                           ▼
                       LUMS API
                           │
                           ▼
                     LUMS Backend
```

Teemakerros päättyy esitystavan rajalle.

Kaikki tämän rajan alapuolella on yhteistä kaikille teemoille.

# LUMS — Valinnainen teemajärjestelmä

## Osa 3 — Teemakonseptit

## 29. LUMSin vakioteema

LUMSin vakioteema on sovelluksen viite-esitystapa.

Sen tarkoitus on tarjota selkeä ja toimiva käyttöliittymä, joka ei edellytä tiettyä visuaalista konseptia.

Vakioteemassa pitäisi painottaa:

* luettavuutta
* selkeää tietohierarkiaa
* ennakoitavaa navigointia
* saavutettavuutta
* vähäisiä visuaalisia häiriötekijöitä
* komponenttien yhdenmukaista esitystapaa

Se on teemajärjestelmän varateema.

Vakioteeman pitäisi siksi pysyä käytettävänä, vaikka valinnaisia visuaalisia teemoja ei olisi saatavilla.

---

## 30. LUMS Stadium

**LUMS Stadium** on LUMS-käyttöliittymän ilmaisuvoimaisempi visuaalinen tulkinta.

Konsepti yhdistää järjestelmänhallinnan stadionhenkiseen visuaaliseen ilmeeseen.

Mahdollisia suunnitteluelementtejä ovat:

* tulostaulusta vaikutteita saaneet tietopaneelit
* selkeämmät visuaaliset tilailmaisimet
* tapahtumakeskeinen esitystapa
* teemoitetut taustat
* operatiivisten tilojen visuaaliset korostukset
* stadionaiheiset koriste-elementit

Teeman toiminnallisuus on sama kuin LUMSin vakioteemassa.

Onnistunut päivitys on edelleen onnistunut päivitys.

Epäonnistunut työ on edelleen epäonnistunut työ.

Vain esitystapa muuttuu.

---

## 31. Golf Club

**Golf Club** -teema tarjoaa tarkoituksella vastakkaisen visuaalisen ilmeen.

Perinteisen palvelin- tai infrastruktuuri-ilmeen sijaan käyttöliittymässä käytetään rauhallisempaa vapaa-ajan konseptia.

Visuaalisessa suunnassa voidaan painottaa:

* selkeitä pintoja
* hillittyjä koristeita
* golfista vaikutteita saaneita elementtejä
* golfkentän kaltaisia visuaalisia vertauksia
* rauhallista tilojen esitystä
* kevyitä teemakorostuksia

Konsepti osoittaa, ettei LUMSin tarvitse näyttää perinteiseltä hallintakonsolilta ollakseen toimiva.

Taustajärjestelmä ja sovelluksen toiminta eivät muutu.

---

## 32. Nerd Mode

**Nerd Mode** on suunnattu teknisempään ja leikkisämpään esitystapaan.

Konsepti voi korostaa LUMSin teknistä luonnetta esimerkiksi seuraavilla elementeillä:

* päätetyylistä vaikutteita saaneet tyylit
* tekninen terminologia
* järjestelmälähtöiset visuaaliset elementit
* kehittäjätyylinen esitystapa
* diagnostiikasta vaikutteita saaneet visuaalit
* tarkoituksella tekniset koristeet

Teeman on silti säilytettävä selkeä tietohierarkia.

Leikkisä käyttöliittymä ei saa vaikeuttaa operatiivisten tietojen ymmärtämistä.

---

## 33. Geek Lab

**Geek Lab** edustaa kokeellisempaa teknistä ympäristöä.

Visuaaliseen konseptiin voi kuulua:

* laboratoriomainen ilme
* tekninen kokeellisuus
* infrastruktuurin visualisointi
* järjestelmäkaaviot
* tieteestä tai tekniikasta vaikutteita saaneet elementit
* kokeelliset visuaaliset tehosteet

Teeman tarkoitus on saada käyttöliittymä tuntumaan infrastruktuurilaboratoriolta ja säilyttää samalla LUMSin sama toiminnallisuus taustalla.

Visuaalinen kokeellisuus on pidettävä erillään sovelluksen operatiivisesta toiminnasta.

---

## 34. Enterprise Admin

**Enterprise Admin** edustaa hillitympää hallintakäyttöliittymää.

Visuaalisessa suunnassa voidaan painottaa:

* jäsenneltyä tietoa
* tiiviitä asetteluja
* hallintakoontinäyttöjä
* selkeitä tilailmaisimia
* operatiivista tietotiheyttä
* vähäisempiä koriste-elementtejä

Teema sopii erityisesti käyttäjille, jotka suosivat perinteistä hallintakonsolin ulkoasua.

Se ei lisää hallintaoikeuksia.

Nimi kuvaa visuaalista konseptia, ei valtuutustasoa.

---

## 35. Teemojen vertailu

Teemat ovat saman sovelluksen erilaisia visuaalisia tulkintoja:

| Teema | Visuaalinen suunta | Pääluonne |
| --- | --- | --- |
| Standard LUMS | Selkeä / toiminnallinen | Viitekäyttöliittymä |
| LUMS Stadium | Stadion / tapahtuma | Ilmaisuvoimainen |
| Golf Club | Vapaa-aika / rauhallinen | Rentouttava |
| Nerd Mode | Tekninen / leikkisä | Kehittäjälähtöinen |
| Geek Lab | Kokeellinen / tekninen | Laboratoriomainen |
| Enterprise Admin | Jäsennelty / hallinnollinen | Hillitty |

Taulukossa kuvataan vain esityskonsepteja.

Siinä **ei** kuvata eroja seuraavissa:

* käyttöoikeudet
* ominaisuudet
* API-käyttö
* asiakaskäyttö
* töiden suoritus
* paketinhallinta
* turvallisuus

---

## 36. Sama käyttöliittymä, eri esitystapa

Keskeinen suunnittelutavoite on, että sama sovelluskomponentti säilyy tunnistettavana kaikissa teemoissa.

Esimerkiksi:

```text id="5dhlf7"
Client List
   │
   ├── Standard presentation
   ├── Stadium presentation
   ├── Golf presentation
   ├── Nerd presentation
   ├── Geek presentation
   └── Enterprise presentation
```

Asiakastiedot pysyvät samoina.

Vain niiden esitystapa muuttuu.

Sama pätee seuraaviin:

* ohjelmistoluettelot
* saatavilla olevat päivitykset
* päivitystyöt
* töiden historia
* käyttäjätiedot
* järjestelmän tila
* paketinhallinnan käyttöliittymät

---

## 37. Operatiiviset tilat

Teemat voivat korostaa eri operatiivisia tiloja visuaalisesti.

Esimerkiksi:

```text id="5wyy17"
PENDING
RUNNING
SUCCESS
FAILED
```

Teema voi käyttää tiloille erilaisia visuaalisia esitystapoja, mutta niiden semanttisen merkityksen on säilyttävä samana.

Teema ei saa määritellä sovelluksen tiloja uudelleen.

Esimerkiksi:

```text id="j4i9qd"
SUCCESS ≠ "looks green"

SUCCESS = actual LUMS job state
```

Visuaalinen esitys vain renderöi taustajärjestelmän tilan.

---

## 38. Virheiden esittäminen

Teemat voivat muuttaa myös virheiden visuaalista esitystapaa.

Virhetietojen on kuitenkin pysyttävä ymmärrettävinä.

Teema ei saa:

* piilottaa tärkeitä virhetietoja
* korvata teknisiä tietoja koristeellisella tekstillä
* tehdä varoituksista erottamattomia normaalitiloista
* vaientaa operatiivisia virheitä

Visuaalinen muotoilu voi parantaa esitystapaa, mutta se ei saa poistaa ongelman ymmärtämiseen tarvittavia diagnostiikkatietoja.

---

## 39. Tilojen yhdenmukaisuus

Saman tilan semanttisen merkityksen on oltava yhdenmukainen kaikissa teemoissa.

Esimerkiksi:

| Tila | Merkitys |
| --- | --- |
| Pending | Odottaa suoritusta |
| Running | Käsitellään parhaillaan |
| Success | Suoritus onnistui |
| Failed | Suoritus epäonnistui |

Teema voi esittää tilat eri väreillä, kuvakkeilla, typografialla tai asettelulla.

Niiden merkitystä ei saa muuttaa.

---

## 40. Teemakohtaiset koristeet

Koriste-elementtien pitäisi pysyä operatiivisten tietojen toissijaisina.

Esimerkkejä:

* taustat
* kuviot
* kuvitukset
* tunnelmatehosteet
* teemoitetut kuvakkeet
* visuaaliset koristeet

Seuraava tärkeysjärjestys on säilytettävä:

```text id="3m08d7"
Operational Information
        │
        ▼
Application Usability
        │
        ▼
Accessibility
        │
        ▼
Visual Decoration
```

Koristeet eivät saa koskaan olla LUMSin käyttöön tarvittavia tietoja tärkeämpiä.

---

## 41. Visuaalinen tietotiheys

Eri teemoissa voidaan käyttää eri visuaalista tietotiheyttä.

Esimerkiksi:

* Enterprise Admin voi painottaa tietotiheyttä.
* LUMSin vakioteema voi painottaa tasapainoista luettavuutta.
* Golf Club voi käyttää enemmän tyhjää tilaa.
* Nerd Mode voi käyttää tiiviitä teknisiä elementtejä.
* Stadium voi korostaa suuria tila-alueita.
* Geek Lab voi tarjota enemmän visuaalista kontekstia.

Nämä erot ovat esitystapaa koskevia valintoja.

Ne eivät muuta pohjana olevan tiedon määrää tai auktoritatiivisuutta.

---

## 42. Saavutettavuus eri teemoissa

Jokaisen teeman on säilytettävä käytettävyyden perustaso.

Tähän kuuluvat:

* luettava teksti
* riittävä visuaalinen erottuvuus
* käytettävät ohjaimet
* ymmärrettävät tilailmaisimet
* näppäimistökäytettävyys
* käytettävät kohdistustilat
* yhteensopivuus vähennetyn liikkeen asetuksen kanssa

Tärkeän tilan viestintään ei saa käyttää pelkkää väriä.

Esimerkiksi epäonnistunutta työtä ei pidä voida tunnistaa vain sen tietyn värisestä esityksestä.

---

## 43. Teemakohtaiset animaatiot

Teemoissa voi olla animaatioita, kun ne tukevat visuaalista konseptia.

Esimerkkejä:

* hienovaraiset siirtymät
* animoidut taustat
* verkkotehosteet
* tilasiirtymät
* tunnelmaa luovat koristeet

Animaatioiden pitää pysyä sovelluksen toissijaisina.

Ne eivät saa:

* estää vuorovaikutusta
* peittää ohjaimia
* jatkuvasti viedä huomiota operatiivisilta tiedoilta
* haitata saavutettavuutta
* vaikuttaa taustajärjestelmän toimintoihin

---

## 44. Elävä verkko

Joissakin LUMS-teemoissa voidaan käyttää dynaamista, verkosta vaikutteita saanutta visuaalista kerrosta.

Konsepti kuvaa LUMSin elävänä infrastruktuuriympäristönä:

```text id="7w1v8b"
Client ─────┐
            │
Client ─────┼──── LUMS
            │
Client ─────┘
```

Visualisointi on koristeellinen, ellei sitä ole nimenomaisesti yhdistetty sovelluksen varsinaisiin tietoihin.

Visuaalista verkkoa ei siis saa tulkita auktoritatiiviseksi verkkotopologiaksi, ellei sovellus nimenomaisesti tarjoa kyseistä tietoa.

Erottelu on tärkeä:

> **Visuaalinen esitys ei automaattisesti ole operatiivista telemetriaa.**

---

## 45. Koristetiedot ja oikeat tiedot

Teemakohtaisten visuaalisten tehosteiden on pysyttävä selvästi erillään oikeista LUMS-tiedoista.

Esimerkiksi:

```text id="z6i5j0"
Decorative node
    ≠
Real client

Animated connection
    ≠
Real network connection

Visual status effect
    ≠
Backend job state
```

Näin käyttäjä ei sekoita esteettistä visualisointia varsinaiseen järjestelmätietoon.

---

## 46. Teeman identiteetti

Jokaisella teemalla pitäisi olla tunnistettava ilme muuttumatta erilliseksi tuotteeksi.

Tavoite:

```text id="qv1fbe"
Different visual identity
          +
Same LUMS functionality
          =
Optional LUMS Theme
```

Näin teemajärjestelmä pysyy leikkisänä ja joustavana ja sovelluksen tekninen eheys säilyy.

---

## 47. Teeman suunnittelusääntö

Kaikkien teemojen tärkein suunnittelusääntö on:

> **Teema voi olla ilmaisuvoimainen, epätavallinen, tekninen, leikkisä tai hillitty — mutta sen on aina pysyttävä LUMSina.**

Sovelluksen on pysyttävä tunnistettavasti samana järjestelmänä valitusta visuaalisesta esitystavasta riippumatta.

# LUMS — Valinnainen teemajärjestelmä

## Osa 4 — Käyttöliittymän toteutus ja saavutettavuus

## 48. Käyttöliittymän teemakerros

Valinnainen teemajärjestelmä kuuluu kokonaan LUMSin käyttöliittymään.

Sen vastuu rajoittuu esitystapaan ja käyttäjämieltymysten käsittelyyn.

Käsitteellisesti:

```text
┌─────────────────────────────────┐
│          LUMS Frontend          │
│                                 │
│  Common Application Logic       │
│              │                  │
│              ▼                  │
│       Theme Presentation        │
│              │                  │
│              ▼                  │
│       Browser Rendering         │
└─────────────────────────────────┘
```

Teemakerros ei korvaa käyttöliittymän yhteistä logiikkaa.

Sen sijaan se lisää sen ympärille esityskerroksen.

---

## 49. Teeman alustus

Teema alustetaan osana käyttöliittymän normaalia käynnistystä.

Käsitteellinen järjestys:

```text
Frontend starts
      │
      ▼
Theme system initializes
      │
      ▼
Stored preference is evaluated
      │
      ▼
Theme availability is checked
      │
      ├── Valid → selected theme
      │
      └── Invalid → standard theme
      │
      ▼
LUMS interface rendered
```

Alustuksen pitäisi olla kevyt, eikä se saa riippua taustajärjestelmän saatavuudesta.

Käyttäjän pitäisi voida ladata visuaalinen käyttöliittymä, vaikka myöhempi API-pyyntö epäonnistuisi.

---

## 50. Teematila

Aktiivinen teema on käyttöliittymän tilaa.

Sitä on siksi käsiteltävä eri tavalla kuin sovellustilaa.

### Teematila

Esimerkkejä:

```text
Active visual theme
Reduced-motion preference
Visual presentation preferences
```

### Sovellustila

Esimerkkejä:

```text
Logged-in user
User role
Client state
Package state
Update state
Job state
Audit state
```

Teematila ei saa koskaan korvata sovellustilaa tai esiintyä senä.

---

## 51. Juuritason teema-attribuutti

Aktiivisen teeman voi käsitteellisesti kuvata juuritason attribuutilla.

Esimerkiksi:

```html
<html data-theme="standard">
```

tai:

```html
<html data-theme="nerd">
```

CSS voi tällöin käyttää aktiivista teemaa valitsimena.

Toteutus voi kehittyä, mutta arkkitehtuurin tavoite pysyy samana:

> **Yksi sovellusrakenne, useita esitysmäärittelyjä.**

---

## 52. CSS:n organisointi

Teemakohtaiset tyylit pitäisi voida erottaa LUMSin yhteisistä tyyleistä.

Käsitteellisesti:

```text
Common styles
│
├── Layout
├── Forms
├── Tables
├── Navigation
├── Status elements
└── Shared components

Theme styles
│
├── Standard
├── Stadium
├── Golf
├── Nerd
├── Geek
└── Admin
```

Yhteisten tyylien pitäisi määrittää toiminnallinen rakenne.

Teemat määrittävät visuaalisen ilmeen.

Tämä vähentää monistamista ja helpottaa teemojen myöhempää ylläpitoa.

---

## 53. CSS-muuttujat

Teemajärjestelmissä voidaan erottaa semanttiset arvot niiden visuaalisesta esityksestä CSS:n mukautettujen ominaisuuksien avulla.

Esimerkiksi:

```css
:root {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Teema voi määrittää niille omat arvonsa:

```css
[data-theme="example"] {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Olennainen periaate on, että komponentit käyttävät semanttisia muuttujia eivätkä kovakoodattuja teemakohtaisia arvoja aina, kun se on käytännöllistä.

---

## 54. Jaetut komponentit

Teemajärjestelmän pitäisi tyylitellä jaettuja komponentteja niiden monistamisen sijaan.

Tyypillisiä komponentteja:

* navigointi
* painikkeet
* lomakkeet
* taulukot
* tilailmaisimet
* kortit
* valintaikkunat
* paketinhallinnan elementit
* päivitystyön elementit
* asiakastiedot
* järjestelmätiedot

Komponentin toiminnallisuuden on oltava sama aktiivisesta teemasta riippumatta.

---

## 55. Teemojen resurssit

Valinnaisissa teemoissa voidaan käyttää omia resursseja.

Mahdollisia resurssiluokkia:

```text
Images
Icons
Backgrounds
Decorative graphics
Fonts
Animation assets
Visual effects
```

Teemojen resurssien on pysyttävä käyttöliittymäresursseina.

Ne eivät saa sisältää arkaluonteisia sovellustietoja.

Teemojen resursseihin ei saa missään tapauksessa lisätä:

* salasanoja
* salaisia avaimia
* asiakastunnisteita
* tietokannan sisältöä
* yksityisiä varmenteita
* todennusaineistoa

---

## 56. Resurssien lataaminen

Teemojen resurssit pitäisi ladata vain tarvittaessa.

Kaikki LUMS-sivut eivät saa hidastua tarpeettomasti vain siksi, että teema on olemassa.

Jos mahdollista:

```text
Selected theme
      │
      ▼
Required assets
      │
      ▼
Browser
```

sen sijaan, että:

```text
All themes
      │
      ▼
All assets loaded simultaneously
```

Tämä korostuu, kun teemoja ja visuaalisia tehosteita lisätään.

---

## 57. Teeman suorituskyky

Visuaalinen mukautus ei saa heikentää LUMSin käytettävyyttä merkittävästi.

Erityisesti on huomioitava:

* suuret taustakuvat
* jatkuvasti animoidut elementit
* canvas-tehosteet
* toistuvat DOM-päivitykset
* raskaat visuaaliset suodattimet
* tarpeettomat verkkopyynnöt

Asiakastietoluetteloiden, ohjelmistoluetteloiden ja päivitystyönäkymien kaltaisten operatiivisten sivujen on pysyttävä responsiivisina.

---

## 58. Koristeellinen JavaScript

Teema voi käyttää JavaScriptiä visuaalisiin tehosteisiin.

Esimerkkejä:

* animoidut taustat
* verkkovisualisoinnit
* dynaamiset koristeet
* teemakohtaiset vuorovaikutukset

Tällainen JavaScript on pidettävä erillään sovelluksen operatiivisesta logiikasta.

Koristeellinen komentosarja ei saa koskaan vastata seuraavista:

* valtuutus
* työn luominen
* paketin asentaminen
* paketin poistaminen
* päivityksen suoritus
* asiakkaan todennus
* valvontalokitus

Erottelun on pysyttävä selkeänä:

```text
Theme JavaScript
      ≠
LUMS operational JavaScript
```

---

## 59. Verkkovisualisointi

Jos teemassa käytetään verkkotyylistä visualisointia, sitä on käsiteltävä esityskomponenttina.

Esimerkiksi:

```text
Canvas / Visual Layer
        │
        ▼
Decorative Network
        │
        ▼
Theme Presentation
```

Ellei visualisointia ole nimenomaisesti yhdistetty auktoritatiivisiin LUMS-tietoihin, sen ei pitäisi antaa ymmärtää kuvaavansa todellista verkkotilaa.

Näin koristegrafiikkaa ei sekoiteta valvontaan tai telemetriaan.

---

## 60. Vähennetty liike

Animaatioita käyttävien teemojen pitäisi tukea vähennetyn liikkeen asetuksia.

Suositeltu toiminta käsitteellisesti:

```text
prefers-reduced-motion: reduce
            │
            ▼
Reduce or disable decorative motion
```

Olennainen toiminnallisuus ei saa muuttua.

Vähennetyn liikkeen on vaikutettava vain esitystapaan.

---

## 61. Kohdistus ja näppäimistönavigointi

Teeman tyylien on säilytettävä näppäimistökäytettävyys.

Tärkeiden vuorovaikutteisten elementtien kohdistustilan on oltava näkyvä.

Teema ei saa poistaa kohdistusreunuksia tarjoamatta yhtä selkeää vaihtoehtoa.

Esimerkiksi:

```text
Keyboard focus
      │
      ▼
Clearly visible control state
```

Tämä koskee seuraavia:

* navigointi
* painikkeet
* linkit
* lomakekentät
* valitsimet
* valintaikkunat
* paketinhallinnan ohjaimet

---

## 62. Väristä riippumattomuus

Tärkeä tieto ei saa perustua yksinomaan väriin.

Esimerkiksi:

```text
FAILED
```

tilan on oltava ymmärrettävä tekstin, kuvakkeiden, rakenteen tai muun saavutettavan osoittimen avulla, vaikka teeman värit eivät olisi käytettävissä.

Tämä on erityisen tärkeää, koska teemoissa voi olla hyvin erilaiset väripaletit.

---

## 63. Kontrasti

Kaikissa teemoissa pitäisi säilyttää riittävä kontrasti seuraavien välillä:

* teksti ja tausta
* ohjaimet ja tausta
* tilailmaisimet ja niitä ympäröivät elementit
* kohdistetut elementit ja niiden ympäristö

Visuaalisesti kiinnostava paletti ei korvaa luettavuutta.

Kun teemavärit ovat ristiriidassa saavutettavuusvaatimusten kanssa, luettavuus asetetaan etusijalle.

---

## 64. Teeman valintakäyttöliittymä

Teeman valitsin on osa LUMSin yhteistä käyttöliittymää.

Sen pitää olla ymmärrettävä aktiivisesta teemasta riippumatta.

Käsitteellisesti:

```text
Theme selector
      │
      ├── Standard LUMS
      ├── LUMS Stadium
      ├── Golf Club
      ├── Nerd Mode
      ├── Geek Lab
      └── Enterprise Admin
```

Toisen teeman valinnan pitäisi muuttaa esitystapaa muuttamatta nykyistä LUMS-istuntoa tai operatiivista tilaa.

---

## 65. Riippumattomuus istunnosta

Teeman vaihtaminen ei saa kirjata käyttäjää ulos.

Se ei saa:

* mitätöidä istuntoa
* muuttaa roolia
* vaihtaa asiakastunnisteita
* muuttaa palvelinpuolen todennustilaa

Teemamieltymys on erillinen todennuksesta.

```text
Theme change
     │
     └── Session remains unchanged
```

---

## 66. Riippumattomuus RBAC:stä

Teemojen on pysyttävä riippumattomina RBAC:stä.

Esimerkiksi:

```text
Administrator
     │
     └── sees functionality permitted to administrators

Operator
     │
     └── sees functionality permitted to operators

Viewer
     │
     └── sees functionality permitted to viewers
```

Valittu teema ei muuta näitä käyttöoikeuksia.

Enterprise Admin -teemaa käyttävä Viewer ei muutu järjestelmänvalvojaksi.

Nerd Mode -teemaa käyttävä Administrator ei menetä ylläpito-oikeuksiaan.

Taustajärjestelmä on auktoritatiivinen kaikissa tapauksissa.

---

## 67. Virheiden eristäminen

Valinnaisen visuaalisen toiminnon virhe ei saa rikkoa LUMSin ydintoimintoja.

Jos esimerkiksi koristeanimaatio epäonnistuu:

```text
Animation failure
      │
      ▼
Theme remains usable
      │
      ▼
LUMS remains operational
```

Visuaalisten ominaisuuksien pitäisi mahdollisuuksien mukaan epäonnistua sovelluksen toiminnallisuudesta riippumatta.

Tämä on erityisen tärkeää valinnaisille tehosteille, kuten animoiduille taustoille ja verkkovisualisoinneille.

---

## 68. Selainyhteensopivuus

Teemajärjestelmän pitäisi käyttää selainominaisuuksia, joita LUMS-käyttöönoton kohdeympäristön selaimet tukevat.

Jos visuaalinen ominaisuus ei ole käytettävissä, käyttöliittymän pitäisi mukautua hallitusti eikä muuttua käyttökelvottomaksi.

Vakiototeaman pitää säilyä perusvarateemana.

---

## 69. Toteutusperiaate

Toteutuksen voi tiivistää näin:

```text
Common HTML
     +
Common LUMS JavaScript
     +
Theme selection
     +
Theme-specific CSS/assets
     =
Optional visual layer
```

Seuraavien on pysyttävä teemakerroksen ulkopuolella:

```text
Authentication
Authorization
Database
Jobs
Package management
Client authentication
Audit logging
Security decisions
```

Erottelu pitää teemajärjestelmän riittävän ilmaisuvoimaisena ilman, että se kytkeytyy LUMSin ydintoimintaan.

# LUMS — Valinnainen teemajärjestelmä

## Osa 5 — Turvallisuus, testaus ja kehitys

## 70. Turvallisuusraja

Teemajärjestelmä kuuluu käyttöliittymään ja toimii siksi epäluotetussa asiakasympäristössä.

Selain ohjaa esityskerrosta.

Selain **ei** ohjaa LUMSin valtuutusta.

Turvallisuusraja on edelleen:

```text id="h8e2ks"
Browser
   │
   │ untrusted presentation
   ▼
LUMS API
   │
   │ authoritative validation
   ▼
LUMS Backend
```

Kaikkien turvallisuuteen vaikuttavien päätösten on siis pysyttävä palvelinpuolella.

---

## 71. Teeman valinta ei ole valtuutus

Valittua teemaa ei saa koskaan tulkita valtuutussignaaliksi.

Esimerkiksi:

```text id="8u3r8v"
data-theme="admin"
```

ei tarkoita, että nykyinen käyttäjä olisi järjestelmänvalvoja.

Sana `admin` teematunnisteessa on vain kuvaileva.

Käyttäjän varsinainen rooli tulee aina todennetusta sovellusistunnosta ja palvelinpuolen valtuutuslogiikasta.

---

## 72. Käyttöliittymän näkyvyys ei ole turvallisuutta

Teema tai käyttöliittymän komentosarja voi piilottaa käyttöliittymäelementin.

Se on hyödyllistä esitystavan kannalta.

Se ei kuitenkaan riitä käyttöoikeuksien valvontaan.

Esimerkiksi:

```text id="7m8c6w"
Hidden button
      ≠
Unauthorized operation prevented
```

Vastaavan API-päätepisteen on tarkistettava käyttäjän käyttöoikeudet itsenäisesti.

Tämä koskee kaikkia LUMSin etuoikeutettuja toimintoja.

---

## 73. Teemojen resurssit ovat julkisia

Käyttöliittymäresursseja on pidettävä julkisesti saatavilla olevina kaikille, joilla on pääsy LUMSin verkkokäyttöliittymään.

Teematiedostot eivät siis saa koskaan sisältää salaisuuksia.

Älä lisää teemojen resursseihin seuraavia:

```text id="1zjz7n"
Passwords
API secrets
Client tokens
Private keys
Database files
Session secrets
Authentication credentials
```

Jos tiedon on pysyttävä luottamuksellisena, se ei kuulu teeman resurssiin.

---

## 74. Ei taustajärjestelmän salaisuuksia teemoihin

Teemojen JavaScript-koodi ei saa sisältää palvelintunnistetietoja tai etuoikeutettua API-aineistoa.

Tarvittaessa teeman pitää käyttää olemassa olevaa käyttöliittymän sovelluskerrosta viestintään.

Se ei saa tuoda vaihtoehtoista todennusmekanismia.

Seuraava periaate pätee:

> **Teemat käyttävät esitystietoja; ne eivät luo turvallisuustunnistetietoja.**

---

## 75. Sivustojen välinen pyyntöjen väärentäminen

Teeman toiminnallisuus ei saa ohittaa olemassa olevaa CSRF-suojausta.

Jos teema tarjoaa ohjaimen suojattua pyyntöä edellyttävään toimintoon, pyynnön on noudatettava samoja turvallisuusvaatimuksia kuin LUMSin yhteisessä käyttöliittymässä.

Visuaalinen koodi ei saa poikkeusta.

---

## 76. API:n käyttö

Teeman pitäisi välttää oman operatiivisen API-logiikan toteuttamista suoraan.

Jos tarvitaan sovellustietoja, teeman pitäisi käyttää LUMSin vakiintuneita käyttöliittymä- ja sovellusmekanismeja.

Näin vältetään useita erillisiä toteutuksia seuraavista:

* todennus
* API-pyynnöt
* virheiden käsittely
* valtuutusta koskevat oletukset
* töiden käsittely

Yhteinen sovelluslogiikka pysyy auktoritatiivisena käyttöliittymäintegraation kerroksena.

---

## 77. Teemojen eristys

Teeman on oltava poistettavissa poistamatta LUMSin ydintoimintoja.

Käsitteellisesti:

```text id="3m1o8q"
Remove optional theme
        │
        ▼
Standard LUMS remains
        │
        ▼
Application remains operational
```

Näin valinnaiset teemat ovat aidosti valinnaisia.

---

## 78. Turvallisuustestaus

Turvallisuustestauksessa pitäisi osoittaa, etteivät teemamuutokset muuta LUMSin turvallisuusmallia.

Asiaankuuluvia tarkistuksia ovat:

* Viewer pysyy Viewer-käyttäjänä
* Operator pysyy Operator-käyttäjänä
* Administrator pysyy Administrator-käyttäjänä
* suojatut API-päätepisteet pysyvät suojattuina
* CSRF-suojaus pysyy käytössä
* asiakkaiden todennus ei muutu
* päivitystöiden käyttöoikeudet eivät muutu
* paketinhallinnan käyttöoikeudet eivät muutu
* valvontalokitus ei muutu

Teemaa ei saa käyttää todisteena toiminnon turvallisuudesta.

---

## 79. Teemojen toiminnallinen testaus

Jokainen teema pitää testata yhteistä sovellusta vasten.

Vähintään:

```text id="9w6h1m"
Login
Client list
Client details
Installed software
Available updates
Update jobs
Job history
Package management
User management
System maintenance
Logout
```

Käytettävissä olevat toiminnot riippuvat todennetun käyttäjän roolista.

Testauksen tarkoituksena on varmistaa, ettei teeman renderöinti riko sovelluksen normaalia toiminnallisuutta.

---

## 80. RBAC-teemojen testaus

Teematestaukseen pitää sisällyttää kaikki asiaankuuluvat roolit.

Perusmatriisi:

| Rooli | Teematestaus |
| --- | --- |
| Administrator | Pakollinen |
| Operator | Pakollinen |
| Viewer | Pakollinen |

Varmista jokaisella roolilla, ettei teeman vaihtaminen muuta sallittuja toimintoja.

Esimerkiksi:

```text id="3n5p2m"
Viewer + Nerd Mode
        =
Viewer permissions

Viewer + Enterprise Admin
        =
Viewer permissions
```

Visuaalinen teema ei saa muuttaa lopputulosta.

---

## 81. Teemanvaihdon testit

Teemanvaihto pitäisi testata toistuvasti.

Esimerkkijärjestys:

```text id="gk2j7m"
Standard
   ↓
Stadium
   ↓
Golf
   ↓
Nerd
   ↓
Geek
   ↓
Admin
   ↓
Standard
```

Sovelluksen on pysyttävä käytettävissä koko vaihdon ajan.

Erityistä huomiota pitää kiinnittää seuraaviin:

* asettelun muutokset
* taulukot
* navigointi
* valintaikkunat
* lomakkeet
* tilailmaisimet
* pitkät tekstit
* responsiivinen toiminta

---

## 82. Pysyvyyden testaus

Jos teemamieltymys tallennetaan paikallisesti, testaa seuraavaa:

1. Valitse teema.
2. Lataa sivu uudelleen.
3. Varmista, että teema on yhä valittuna.
4. Sulje selain.
5. Avaa LUMS uudelleen.
6. Varmista, että mieltymys käsitellään oikein.
7. Poista tai mitätöi tallennettu teema.
8. Varmista, että järjestelmä palaa vakioteemaan.

Tallennettua arvoa ei saa koskaan luottaa sovelluksen turvallisuustilana.

---

## 83. Virheellisen teeman testaus

Virheellinen teematunniste ei saa rikkoa käyttöliittymää.

Esimerkiksi:

```text id="4j5cqn"
unknown-theme
```

pitäisi johtaa turvalliseen varateemaan käyttökelvottoman sivun sijaan.

Toivottu toiminta:

```text id="5x9h2f"
Invalid theme
     │
     ▼
Standard theme
     │
     ▼
LUMS remains usable
```

---

## 84. Resurssivirheiden testaus

Myös valinnaisten resurssien virhetilanteet pitää testata.

Esimerkkejä:

* puuttuva kuva
* animaatio ei ole saatavilla
* virheellinen resurssipolku
* visuaalinen ominaisuus, jota selain ei tue
* JavaScript-virhe valinnaisessa koristeessa

Yhteisen sovelluksen pitäisi pysyä käytettävissä aina kun mahdollista.

---

## 85. Vähennetyn liikkeen testaus

Animaatioita sisältävät teemat testataan sekä normaalissa että vähennetyn liikkeen ympäristössä.

```text id="l1h4nb"
Normal motion
     │
     └── Theme effects available

Reduced motion
     │
     └── Effects reduced or disabled
```

Tärkeiden sovellusohjaimien on toimittava täysin kummassakin tilassa.

---

## 86. Responsiivisuuden testaus

Teemat pitäisi testata erikokoisilla näkymäalueilla.

Vähintään:

* työpöytänäkymä
* tabletin kokoinen näkymäalue
* kapea tai mobiilin kokoinen näkymäalue

Visuaalinen ilme ei saa heikentää ohjaimien käytettävyyttä tai sovellustietojen luettavuutta.

Erityistä huomiota pitää kiinnittää seuraaviin:

* navigointi
* taulukot
* toimintopainikkeet
* paketinhallinnan ohjaimet
* työn tilatiedot
* valintaikkunat
* teemavalitsimet

---

## 87. Suorituskyvyn testaus

Visuaalisten tehosteiden vaikutusta selaimen suorituskykyyn arvioidaan.

Asiaankuuluvia havaintoja:

* sivun latausaika
* renderöinnin responsiivisuus
* suorittimen käyttö
* muistin käyttö
* animaation sujuvuus
* toistuvat DOM-päivitykset
* verkkopyynnöt

Teemojen on parannettava esitystapaa muodostumatta suorituskyvyn pullonkaulaksi.

---

## 88. Kehitystyönkulku

Uusi teema pitäisi mahdollisuuksien mukaan kehittää taustajärjestelmän muutoksista erillään.

Suositeltu työnkulku:

```text id="1i8qz6"
Design
   ↓
Frontend implementation
   ↓
Theme selector integration
   ↓
Accessibility review
   ↓
Functional testing
   ↓
RBAC testing
   ↓
Fallback testing
   ↓
Performance review
   ↓
Documentation
```

Taustajärjestelmään tehdään muutoksia vain silloin, kun niille on todellinen sovellusvaatimus.

Visuaalisen teeman ei normaalisti pitäisi vaatia taustajärjestelmän muutoksia.

---

## 89. Kehityssäännöt

Teemaa kehitettäessä:

1. Käytä olemassa olevia LUMS-komponentteja uudelleen.
2. Vältä sivujen monistamista.
3. Eristä teemakohtaiset tyylit.
4. Pidä koristeellinen JavaScript erillään operatiivisesta logiikasta.
5. Älä lisää todennuslogiikkaa.
6. Älä lisää valtuutuslogiikkaa.
7. Älä paljasta salaisuuksia.
8. Säilytä saavutettavuus.
9. Säilytä vähennetyn liikkeen toiminta.
10. Testaa kaikki asiaankuuluvat roolit.
11. Testaa vakioteeman varatoiminta.
12. Dokumentoi uudet resurssit ja toiminta.

---

## 90. Muutoksen varmentaminen

Ennen kuin teeman muutos katsotaan valmiiksi, varmennetaan sekä esitystapa että toiminnallisuus.

Hyödyllinen tarkistusjärjestys:

```text id="i1v9yb"
Theme changed
      │
      ▼
Visual inspection
      │
      ▼
Page functionality
      │
      ▼
Role behavior
      │
      ▼
API behavior
      │
      ▼
Browser console
      │
      ▼
Regression tests
```

Teema ei ole valmis vain siksi, että se näyttää oikealta.

Sen on myös säilytettävä LUMSin toiminta muuttumattomana.

---

## 91. Regressioperiaate

Teemojen kehityksessä noudatetaan samaa yleistä periaatetta kuin muissa LUMS-muutoksissa:

> **Muuta → testaa → varmista → dokumentoi**

Visuaalinen muutoskin voi aiheuttaa toiminnallisia regressioita.

Esimerkkejä:

* piilotetut painikkeet
* lukukelvoton teksti
* rikkoutunut asettelu
* ohjaimet, joita ei voi käyttää saavutettavasti
* JavaScript-ristiriidat
* puuttuvat resurssit
* virheelliset valitsimet
* mobiiliasettelun virheet

Testaus kuuluu siis teemojen kehitykseen eikä ole valinnainen viimeinen vaihe.

---

## 92. Vianmääritys: teema ei lataudu

Jos valittu teema ei näy:

1. Lataa sivu uudelleen.
2. Tarkista, latautuuko vakioteema.
3. Tarkista selaimen konsoli.
4. Tarkista, onko valitun teeman tunniste kelvollinen.
5. Tarkista, ovatko tarvittavat teemaresurssit saatavilla.
6. Tarkista JavaScript-virheet.
7. Tyhjennä paikallinen teemamieltymys tarvittaessa.
8. Lataa sivu uudelleen ja varmista siirtyminen vakioteemaan.

Älä muuta taustajärjestelmän turvallisuusasetuksia käyttöliittymäteeman ongelman ratkaisemiseksi.

---

## 93. Vianmääritys: teema rikkoo asettelun

Jos teema aiheuttaa asetteluongelmia:

1. Vaihda LUMSin vakioteemaan.
2. Varmista, että yhteinen käyttöliittymä toimii.
3. Tunnista ongelmallinen komponentti.
4. Tarkista teemakohtainen CSS.
5. Tarkista responsiivinen toiminta.
6. Tarkista selaimen konsolivirheet.
7. Korjaa teemakohtainen tyylitys.
8. Testaa muut teemat uudelleen.

Vakioteema tarjoaa tärkeän vertailukohdan diagnostiikalle.

---

## 94. Vianmääritys: teema aiheuttaa JavaScript-virheitä

Jos teemakohtainen JavaScript aiheuttaa virheitä:

1. Vaihda vakioteemaan.
2. Varmista LUMSin normaali toiminta.
3. Tunnista virheen aiheuttava teemakomentosarja.
4. Selvitä, onko virhe koristeellinen vai sovellukseen liittyvä.
5. Korjaa teemakohtainen virhe.
6. Varmista, että yhteinen LUMS-JavaScript toimii edelleen.
7. Testaa teemanvaihto uudelleen.

Operatiivista JavaScriptiä ei pidä muuttaa vain koristeellisen teemavirheen kiertämiseksi.

---

## 95. Vianmääritys: teemamieltymys on virheellinen

Jos selaimeen on yhä tallennettu vanha tai virheellinen teema:

```text id="b9n8wq"
Invalid stored preference
        │
        ▼
Fallback to Standard
        │
        ▼
Select a valid theme
```

Suositeltu ratkaisu on turvallinen varatoiminta, ei palvelimen manuaalinen muokkaaminen.

---

## 96. Teeman dokumentointi

Jokaisesta uudesta teemasta dokumentoidaan:

* sisäinen tunniste
* näyttönimi
* visuaalinen konsepti
* tarvittavat resurssit
* valinnaiset visuaaliset tehosteet
* saavutettavuuteen liittyvät seikat
* vähennetyn liikkeen toiminta
* tunnetut rajoitukset

Toteutuskohtaisessa dokumentaatiossa kuvataan todellinen nykyinen koodi sen sijaan, että oletettaisiin, miten teema voisi toimia.

---

## 97. Nykyiset teemat

Tässä dokumentoidut teemakonseptit ovat:

```text id="r0w4u5"
standard       → Standard LUMS
LUMSStadium    → LUMS Stadium
golf           → Golf Club
nerd           → Nerd Mode
geek           → Geek Lab
admin          → Enterprise Admin
```

Teemavalikoimaa voidaan laajentaa.

Lisäteemoja voidaan lisätä muuttamatta LUMSin pohja-arkkitehtuuria, kunhan esitystavan ja sovelluksen toiminnan erottelu säilytetään.

---

## 98. Kehitysperiaate

Valinnaisen teemajärjestelmän pitäisi pysyä hallittuna käyttöliittymälaajennuksena.

Sen tarkoitus on tehdä LUMSista ilmaisuvoimaisempi ja mukautuvampi vaikeuttamatta sovelluksen operointia.

Suositeltu arkkitehtuuri:

```text id="l2e8o9"
Common LUMS
     │
     ├── Common functionality
     ├── Common security
     ├── Common backend
     └── Common application state
              │
              ▼
       Optional Theme Layer
              │
       ┌──────┼──────┐
       ▼      ▼      ▼
    Theme A Theme B Theme C
```

Yhteinen sovellus on perusta.

Teemat pysyvät valinnaisina laajennuksina.

# LUMS — Valinnainen teemajärjestelmä

## Osa 6 — Ylläpito, laajentaminen ja lopputila

## 99. Teemojen ylläpito

Teemojen ylläpito pitäisi mahdollisuuksien mukaan pitää erillään LUMSin ydinylläpidosta.

Visuaalisen teeman päivitys koskee tavallisesti vain käyttöliittymäresursseja.

Tyypillisiä muutoksia:

* CSS-säädöt
* visuaaliset resurssit
* teemakohtainen JavaScript
* saavutettavuuden parannukset
* responsiivisen asettelun korjaukset
* animaatioiden säädöt
* teemojen nimeämiseen tai esitystapaan liittyvät muutokset

Teeman päivitys ei saa edellyttää muutoksia seuraaviin:

* asiakasmääritykset
* asiakastunnisteet
* tietokannan skeema
* päivitystyöt
* paketinhallinnan logiikka
* todennus
* RBAC
* palvelinpuolen turvakontrollit

Jos teemamuutos odottamatta edellyttää tällaisia muutoksia, riippuvuus on arvioitava ennen jatkamista.

---

## 100. Teemojen päivitykset

Teemojen päivityksissä noudatetaan normaalia LUMS-kehitysprosessia:

```text id="2p7z9r"
Modify
   ↓
Test
   ↓
Verify
   ↓
Document
```

Laajemmissa muutoksissa:

```text id="p7l5me"
Design
   ↓
Implementation
   ↓
Functional testing
   ↓
Accessibility testing
   ↓
RBAC regression testing
   ↓
Performance review
   ↓
Documentation
```

Teemaa ei pidä katsoa valmiiksi vain siksi, että visuaalinen lopputulos näyttää oikealta.

---

## 101. Uuden teeman lisääminen

Uuden teeman voi ottaa käyttöön muuttamatta LUMSin taustajärjestelmää.

Suositeltu prosessi:

### Vaihe 1 — Määrittele konsepti

Kuvaile:

* visuaalinen identiteetti
* tavoiteltu tyyli
* typografia
* värit
* koriste-elementit
* valinnaiset animaatiot

### Vaihe 2 — Määrittele tunniste

Valitse vakaa sisäinen tunniste.

### Vaihe 3 — Toteuta esitystapa

Lisää tarvittavat tyylit ja resurssit.

### Vaihe 4 — Yhdistä valintaan

Tee teema käytettäväksi yhteisessä teemavalitsimessa.

### Vaihe 5 — Testaa

Varmista seuraavat:

* normaalit sivut
* vuorovaikutteiset ohjaimet
* responsiiviset asettelut
* saavutettavuus
* vähennetty liike
* kaikki asiaankuuluvat RBAC-roolit
* varatoiminta

### Vaihe 6 — Dokumentoi

Kirjaa teema ja siihen liittyvät toteutustiedot.

---

## 102. Teeman poistaminen

Teeman poistamista on käsiteltävä yhteensopivuusmuutoksena, koska käyttäjillä voi olla kyseinen teema vielä paikallisesti valittuna.

Käyttöliittymän on siis käsiteltävä vanhentunutta tunnistetta turvallisesti.

Suositeltu toiminta:

```text id="x4e7p1"
Old theme identifier
       │
       ▼
Theme no longer available
       │
       ▼
Standard LUMS
```

Teeman poistaminen ei saa koskaan edellyttää tietokantamigraatiota vain selainpuolen mieltymyksen poistamiseksi.

---

## 103. Teeman nimen muuttaminen

Näyttönimeä voi tavallisesti muuttaa sisäisestä tunnisteesta riippumatta.

Esimerkiksi:

```text id="8q4n1k"
Internal identifier
        │
        └── remains stable

Display name
        │
        └── may change
```

Jos itse sisäinen tunniste muuttuu, olemassa oleville paikallisille asetuksille voidaan tarvita migraatio tai yhteensopivuuskartoitus.

Tunnisteet kannattaa pitää vakaina aina, kun se on käytännöllistä.

---

## 104. Teemojen yhteensopivuus

Teemojen pitäisi pysyä yhteensopivina LUMSin yhteisen käyttöliittymän muutosten kanssa.

Kun käyttöön lisätään uusi jaettu komponentti, olemassa olevista teemoista tarkistetaan:

* puuttuvat tyylit
* rikkoutuneet välit
* lukukelvoton teksti
* virheelliset värit
* puuttuva responsiivisuus
* virheelliset kohdistustilat
* saavuttamattomat ohjaimet

Uusi taustajärjestelmän ominaisuus ei automaattisesti edellytä uutta teemaominaisuutta.

Yhteinen sovellus on totuuden lähde.

---

## 105. Uudet LUMS-ominaisuudet

Kun LUMSiin lisätään uusi ominaisuus, teematuen tarvetta arvioidaan tavallisesti sen jälkeen, kun yhteinen ominaisuus toimii.

Suositeltu järjestys:

```text id="z4b7jx"
New LUMS feature
       │
       ▼
Common implementation
       │
       ▼
Functional tests
       │
       ▼
Theme compatibility
       │
       ▼
Theme-specific refinement
```

Näin visuaalisista mukautuksista ei tule ydintoimintojen kehityksen riippuvuutta.

---

## 106. Teema-API:n vakaus

Teemajärjestelmän ei pitäisi luoda erillistä API-kerrosta, ellei sille ole todellista tarvetta.

Teemojen pitäisi käyttää ensisijaisesti samaa käyttöliittymän sovellustilaa ja API-mekanismeja kuin muu LUMS.

Tämä vähentää:

* pyyntölogiikan monistamista
* virheenkäsittelyn monistamista
* ristiriitaisia oletuksia valtuutuksesta
* lisäylläpitoa
* tarpeetonta hyökkäyspintaa

Teemajärjestelmä on siis tarkoituksella kevyt.

---

## 107. Teeman turvallisuusarviointi

Uutta teemaa lisättäessä tai muutettaessa merkittävästi tarkistetaan seuraavat:

```text id="3eq4w6"
[ ] No credentials in assets
[ ] No client tokens in assets
[ ] No private keys
[ ] No authentication bypass
[ ] No authorization logic
[ ] No CSRF bypass
[ ] No direct security decisions
[ ] No unintended API endpoints
[ ] No sensitive information in frontend assets
[ ] Decorative scripts remain isolated
```

Arviointi tehdään myös silloin, kun muutos vaikuttaa pelkästään visuaaliselta.

Käyttöliittymän koodi on silti suoritettavaa koodia.

---

## 108. Teeman saavutettavuusarviointi

Jokaisesta teemasta tarkistetaan:

```text id="1y9xw6"
[ ] Text remains readable
[ ] Contrast remains sufficient
[ ] Focus states are visible
[ ] Keyboard navigation works
[ ] Controls remain usable
[ ] Statuses are not color-only
[ ] Reduced motion is respected
[ ] Responsive layout remains usable
[ ] Decorative effects do not obscure information
```

Saavutettavuus on osa teeman laatua, ei valinnainen parannus.

---

## 109. Teemamuutoksen regressiotarkistuslista

Ennen teeman muutoksen hyväksymistä:

```text id="8j6x4e"
[ ] Standard theme works
[ ] Changed theme works
[ ] Other themes still work
[ ] Theme switching works
[ ] Stored preference works
[ ] Invalid preference falls back safely
[ ] Login works
[ ] Logout works
[ ] Client views work
[ ] Software views work
[ ] Update views work
[ ] Package-management views work
[ ] User-management views work where authorized
[ ] Job information remains readable
[ ] Error messages remain understandable
[ ] RBAC remains unchanged
[ ] Backend behavior remains unchanged
```

Testissä näkyvien ominaisuuksien tarkka joukko riippuu käyttäjän roolista.

---

## 110. Operatiivinen riippumattomuus

Valinnainen teemajärjestelmä on tarkoituksella riippumaton LUMSin operatiivisesta elinkaaresta.

Teeman vaihtaminen ei saa edellyttää seuraavia:

```text id="b2i1k4"
Agent restart
Watcher restart
Database restart
Client re-registration
Token rotation
Job cancellation
Package-manager changes
Network changes
```

Näin esityskerros voi kehittyä infrastruktuurikerroksesta riippumatta.

---

## 111. Riippumattomuus käyttöönotosta

Teemojen resurssit kuuluvat LUMS-sovelluksen käyttöliittymään.

Yleiset käyttöönottomenettelyt on dokumentoitu pääasiallisissa asennus- ja hallintaohjeissa.

Tässä asiakirjassa ei tarkoituksella toisteta seuraavia:

* Docker-käyttöönoton menettelyt
* kontin kovennuskomennot
* Nginx-määritys
* tietokannan varmuuskopiointimenettelyt
* palvelimen palautusmenettelyt
* asiakkaan asennusmenettelyt

Nämä aiheet kuuluvat asianmukaiseen operatiiviseen dokumentaatioon.

Erottelu estää teemadokumentaation vanhenemisen käyttöönottoarkkitehtuurin muuttuessa.

---

## 112. Lähteen ja suoritusympäristön erottelu

Teemajärjestelmä on osa sovelluksen lähdekoodia.

Seuraavien välillä on ero:

```text id="b6q7jv"
Source
   │
   ├── Theme definitions
   ├── CSS
   ├── JavaScript
   └── Assets

Runtime
   │
   ├── Built LUMS image
   └── Running LUMS application
```

Lähdekoodiin tehty teemamuutos ei automaattisesti tarkoita, että jo käynnissä oleva käyttöönotto olisi saanut sen.

Päivitettyjen käyttöliittymäresurssien toimittamisesta vastaa LUMSin normaali koonti- ja käyttöönottoprosessi.

---

## 113. Versiointi

Teemat eivät edellytä LUMSin taustajärjestelmälle erillistä versiota.

Teema voi kehittyä osana käyttöliittymän tai sovelluksen versiota.

Jos teeman muutos aiheuttaa yhteensopivuusongelmia, ne dokumentoidaan nimenomaisesti.

Esimerkiksi:

```text id="5y1p8f"
Theme change
     │
     ├── visual-only
     │
     └── compatibility-affecting
```

Jälkimmäinen luokka edellyttää laajempaa regressiotestausta.

---

## 114. Julkaisuvalmius

Ennen teemamuutoksia sisältävää LUMS-julkaisua varmennetaan:

```text id="v2h3f7"
Theme rendering
Theme selection
Theme fallback
Accessibility
Reduced motion
Responsive layout
RBAC behavior
API behavior
Security boundaries
Regression tests
Documentation
```

Teemamuutosten ei saa antaa peittää ydinsovelluksen regressioita.

---

## 115. Nykyiset teemat

Dokumentoidut teemakonseptit tällä hetkellä:

| Tunniste | Näyttönimi | Konsepti |
| --- | --- | --- |
| `standard` | Standard LUMS | Viitekäyttöliittymä |
| `LUMSStadium` | LUMS Stadium | Stadion / tapahtuma |
| `golf` | Golf Club | Rauhallinen / vapaa-aika |
| `nerd` | Nerd Mode | Tekninen / leikkisä |
| `geek` | Geek Lab | Kokeellinen / tekninen |
| `admin` | Enterprise Admin | Jäsennelty / hallinnollinen |

Kaikki teemat käyttävät samaa LUMS-sovellusta ja taustajärjestelmää.

Ne ovat visuaalisia vaihtoehtoja, eivät erillisiä tuotteita tai käyttöoikeustasoja.

---

## 116. Nykyinen tila

Valinnainen teemajärjestelmä laajentaa LUMSin käyttöliittymäarkkitehtuuria.

Sen tavoitellut ominaisuudet:

```text id="2xq1w8"
[✓] Optional
[✓] Client-side presentation
[✓] Common backend
[✓] Common security model
[✓] Common RBAC model
[✓] Standard fallback
[✓] Theme-specific visual identity
[✓] Reduced-motion consideration
[✓] Accessibility consideration
[✓] No theme-based authorization
```

Toteutuskohtaiset tiedot on aina pidettävä ajan tasalla käyttöliittymän lähdekoodin kanssa.

---

## 117. Tulevat laajennukset

Teemajärjestelmää voidaan laajentaa useisiin suuntiin taustalla olevaa arkkitehtuuria muuttamatta.

Mahdollisia tulevia lisäyksiä:

* lisäteemat
* teemojen esikatselun parantaminen
* tarkemmat visuaaliset asetukset
* lisäasetukset saavutettavuuteen
* responsiivisen toiminnan parantaminen
* teemakohtaiset koontinäyttöasettelut
* valinnaiset lisävisualisoinnit

Laajennuksissa on edelleen kunnioitettava esitystavan ja sovelluksen toiminnan erottelua.

---

## 118. Lopullinen arkkitehtuuri

Koko konseptin voi tiivistää näin:

```text id="x8j7z2"
                    LUMS
                     │
          ┌──────────┴──────────┐
          │                     │
     Application             Theme Layer
          │                     │
          │             ┌───────┼────────┐
          │             │       │        │
          │          Standard Stadium  Golf
          │
          │             Nerd   Geek   Admin
          │
          └──────────────┬────────────┘
                         │
                         ▼
                  Common Backend
                         │
             ┌───────────┼───────────┐
             │           │           │
          Security      Jobs       Clients
             │           │           │
             └───────────┼───────────┘
                         ▼
                      SQLite
```

Visuaalinen kerros on edelleen valinnainen.

Sovelluskerros on auktoritatiivinen.

Turvallisuuskerros pysyy riippumattomana.

---

## 119. Lopullinen periaate

Valinnaisen teemajärjestelmän tarkoitus on tehdä LUMSista henkilökohtaisempi, ilmaisuvoimaisempi ja mukautuvampi vaarantamatta teknistä arkkitehtuuria.

Perussääntö pysyy samana:

> **Yksi LUMS · monta käyttöliittymää · sama taustajärjestelmä**

Teema voi muuttaa LUMSin tunnelmaa.

Se ei saa koskaan muuttaa sitä, mitä LUMS saa tehdä.
