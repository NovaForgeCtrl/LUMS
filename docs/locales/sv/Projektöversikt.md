# LUMS

**Linux-uppdateringshantering utan bruset.**

## Komma igång

LUMS hanterar Linux-uppdateringar centralt. En server visar klienter, installerad
programvara och tillgängliga uppdateringar. En agent på varje hanterat Linux-system utför
godkända paketåtgärder med systemets pakethanterare. LUMS ersätter inte
APT på Debian/Ubuntu eller pacman på Arch Linux.

**Använder du bara en befintlig LUMS-installation?** Öppna adressen som din
administratör tillhandahåller och logga in med ditt eget konto. Om en funktion saknas
kanske ditt konto inte har behörighet att använda den. Fråga din administratör om
hjälp; dela inte konton och använd inte en klienttoken som webbplatslösenord.

**Installerar eller driftar du LUMS?** Börja med
[installationsguiden](<Installation och uppgraderingar.md>), läs sedan
[administrationsguiden](<Administration och säkerhetskopior.md>). Om något går fel, använd
[felsökningsguiden](Felsökning.md). Översatta guider finns också, men deras
omfattning kan skilja sig från de engelska tekniska originalen. I
[dokumentationsindexet](../../README.md) listas tillgängliga språkversioner.

En testkörning eller en framgångsrikt byggd Docker-avbildning är **inte** en produktionsinstallation.
En produktionsdistribution behöver också HTTPS, en skyddad programhemlighet, beständig data,
verifierade säkerhetskopior och en härdad container. Kopiera inte produktionskommandon
förrän du har kontrollerat deras platshållare och lagringsplatser mot din egen installation.

### Språk i webbgränssnittet

Webbgränssnittet erbjuder tyska, engelska (US och UK), franska, spanska,
förenklad kinesiska, japanska, polska, svenska, norskt bokmål och finska.
Välj ett språk i det övre högra hörnet på inloggningssidan. Om du inte
väljer ett försöker LUMS använda webbläsarens språk; efter inloggning har ett språk
sparat på ditt konto företräde. Viss teknisk eller dynamisk text kan
förbli på sitt originalspråk när en översättning inte är tillgänglig. Markdown-
guider är separata från webbgränssnittet och översätts inte automatiskt.

---

LUMS är en Linux-uppdateringshanteringsserver designad för att tillhandahålla kontrollerad, granskningsbar och säker programvaru- och uppdateringshantering för Linux-klienter.

Istället för att förlita sig på okontrollerad uppdateringsaktivitet på klientsidan tillhandahåller LUMS ett centralt hanteringslager för programvaruinventering, uppdateringsdetektering, paketåtgärder, uppdateringsjobb, övervakning av körning och resultatrapportering.

LUMS är designat för miljöer där uppdateringar ska vara **synliga, kontrollerade, spårbara och återställbara**.

---

## Vad är LUMS?

LUMS (**Linux Update Management Server**) består av en central server och lättvikts-Linux-klienter.

Servern tillhandahåller hanteringsgränssnittet, API, autentisering, auktorisering, jobbhantering, granskningsloggning och beständigt tillstånd.

Klientagenten utför lokala pakethanteraroperationer och rapporterar resultaten tillbaka till servern.

Den grundläggande arkitekturen är:

```text
                    ┌──────────────────────┐
                    │      Webbläsare       │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     LUMS-server      │
                    │                      │
                    │ Webbgränssnitt / API │
                    │ Autentisering        │
                    │ RBAC                 │
                    │ Jobbhantering        │
                    │ Granskningsloggning  │
                    │ SQLite               │
                    └──────────┬───────────┘
                               │
                         HTTPS / API
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
      ┌─────────────────┐             ┌─────────────────┐
      │  Linux-klient   │             │  Linux-klient   │
      │                 │             │                 │
      │ LUMS-agent      │             │ LUMS-agent      │
      │ Pakethanterare  │             │ Pakethanterare  │
      │ Watcher         │             │ Watcher         │
      └─────────────────┘             └─────────────────┘
```

---

## Varför LUMS?

Linux-system tillhandahåller redan utmärkta verktyg för pakethantering.

LUMS försöker inte ersätta dem.

Istället tillhandahåller LUMS ett hanteringslager runt dessa verktyg så att administratörer centralt kan svara på frågor som:

* Vilka klienter finns?
* Vilken programvara är installerad?
* Vilka uppdateringar är tillgängliga?
* Vilka paket ska installeras eller tas bort?
* Vilka uppdateringsjobb körs?
* Vad hände under en uppdatering?
* Rapporterade klienten resultatet framgångsrikt?
* Krävdes en omstart?
* Kan ett avbrutet jobb återställas säkert?
* Vem initierade en administrativ åtgärd?

Målet är inte att dölja den underliggande Linux-pakethanteraren.

Målet är att göra dess drift **hanterbar och granskningsbar**.

---

## Huvudfunktioner

### Klienthantering

LUMS underhåller registrerade Linux-klienter och deras autentiseringstillstånd.

Varje klient får en individuell autentiseringstoken.

Klienttoken lagras inte som klartextuppgifter. Servern lagrar en SHA-256-sammanfattning och validerar inkommande klientautentisering mot den sammanfattningen.

Administratörer kan:

* registrera klienter
* inaktivera klienter
* rotera klienttoken
* inspektera klientstatus
* övervaka klientrapportering

---

### Programvaruinventering

Klienter rapporterar sin installerade programvara till LUMS-servern.

Servern lagrar inventeringen och exponerar den via hanteringsgränssnittet.

Vyn för installerad programvara är avsiktligt separat från pakethanteringssökning.

Detta gör det möjligt för administratörer och skrivskyddade användare att inspektera installerad programvara utan att automatiskt exponera pakethanteringsåtgärder.

---

### Uppdateringsinventering

Klienter bestämmer regelbundet om paketuppdateringar är tillgängliga.

Servern lagrar den rapporterade uppdateringsinformationen och gör den tillgänglig för behöriga användare.

Uppdateringsinformation kan användas som grund för kontrollerade uppdateringsjobb.

---

### Pakethantering

LUMS tillhandahåller pakethanteringsåtgärder via klientagenten.

Paketåtgärder som stöds inkluderar:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Pakethanteringslagret abstraherar den underliggande pakethanteraren.

Nuvarande pakethanterarfamiljer som stöds är:

* **Debian / Ubuntu:** APT / dpkg
* **Arch Linux:** pacman

Paketsökning är också tillgänglig via LUMS.

Sökförfrågningar skickas till målklienten, körs med den lokala pakethanteraren och returneras till servern för visning.

---

### Uppdateringsjobb

Uppdateringsåtgärder representeras som beständiga jobb.

Ett jobb kan innehålla en eller flera paketåtgärder och upprätthåller ett körningstillstånd på serversidan.

Den allmänna livscykeln är:

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

Resultat på paketnivå spåras oberoende så att avbrutna jobb kan återställas utan att onödigtvis upprepa operationer som redan slutförts framgångsrikt.

---

### Kontrollerad körning

LUMS utför inte godtyckliga skalkommandon som tillhandahålls av webbgränssnittet.

Servern skapar strukturerade jobb med validerade åtgärder och paketnamn.

Klientagenten mappar dessa åtgärder till lämplig lokal pakethanteraroperation.

Detta skapar en avsiktlig gräns mellan:

```text
Webbgränssnitt
   ↓
API
   ↓
Validerat jobb
   ↓
Agent
   ↓
Pakethanterare
```

---

### Inaktivitetsmedveten körning

LUMS kan skjuta upp uppdateringskörning medan en klient anses vara aktiv.

Den nuvarande inaktivitetsgränsen är **300 sekunder**.

Där det stöds använder agenten det lokala systemets sessions-/inaktivitetsinformation via `loginctl`.

Om inaktivitetsdetektering inte är tillgänglig låtsas LUMS inte att klienten är inaktiv.

Denna distinktion är viktig eftersom **okänt inaktivitetstillstånd inte är samma sak som bekräftat inaktivitetstillstånd**.

---

### Jobbåterställning

Uppdateringsjobb är designade för att överleva avbrott.

Servern upprätthåller beständigt jobb- och paketobjektstillstånd.

Under återställning körs redan framgångsrika paketobjekt inte onödigtvis igen.

Detta ger en kontrollpunktsliknande körningsmodell för operationer med flera paket.

Målet är:

> **Återställ jobbet, starta inte hela jobbet blint på nytt.**

---

### Omstartsdetektering

Vissa paketåtgärder kan kräva en systemomstart.

LUMS behandlar därför omstartsdetektering som en del av uppdateringsresultathanteringen istället för att anta att en framgångsrik pakethanterarutgång alltid innebär att systemet är fullt funktionsdugligt.

Klienten rapporterar det detekterade omstartsbehovet tillbaka till servern.

---

### Klientautentisering

Klientkommunikation autentiseras med per-klient-token.

Token är:

* individuellt tilldelade
* roterbara
* lagras endast på serversidan som SHA-256-sammanfattningar
* valideras innan klientrapporter accepteras

Tokenrotation gör det möjligt för en administratör att ogiltigförklara en tidigare utfärdad klientuppgift utan att återskapa klienten.


---

### Hälsopanel

Den autentiserade panelen på `/health` sammanfattar databasstatus, klienternas rapporteringsstatus, synlighet för säkerhetskopieringslagring samt CPU-/minnestelemetri om den har konfigurerats. Det är en snabb driftöversikt, inte en ersättning för att granska container-, proxy-, värd- och säkerhetskopieringsloggar eller att testa en återställning. Se [guiden till LUMS-hälsopanelen](LUMS-hälsopanel.md).

---

### Larm

LUMS har ett API för larmhantering och en grundläggande panel för lagrade larmposter. Administratörer kan hantera regler, utlösa larm manuellt samt kvittera, lösa eller manuellt eskalera ett aktivt larm. Villkor och tröskelvärden lagras som konfiguration, men servern utvärderar dem inte automatiskt mot telemetri. E-post-, Slack-, PagerDuty- och generiska webhookintegrationer är inte tillgängliga via API:t, och massradering är avstängd för att bevara historiken. Se [implementationens gränser för larmhantering](Larmhantering.md).

---

### Granskningsbarhet

Administrativa och säkerhetsrelevanta åtgärder registreras via LUMS granskningsloggsystem.

Granskningsspåret är avsett att svara på:

```text
Vem?
Vad?
När?
Mot vilket objekt?
Med vilket resultat?
```

Detta inkluderar säkerhetskänsliga operationer som autentiseringsrelaterade åtgärder, klienthantering, användarhantering och skapande av uppdateringsjobb.

---

## Designprincip

LUMS följer en enkel princip:

> **Gör Linux-uppdateringshantering synlig, kontrollerad, återställbar och granskningsbar — utan att dölja Linux-verktygen under.**

## Arkitektur

LUMS separerar hantering, körning och persistens i tydligt definierade komponenter.

Servern ansvarar för orkestrering och policy.

Klienten ansvarar för lokal systeminteraktion.

Pakethanteraren ansvarar fortfarande för att faktiskt installera, ta bort eller uppdatera programvara.

Denna separation är avsiktlig.

```text
Webbläsare
   │
   │ HTTPS
   ▼
┌──────────────────────────────────────────┐
│                LUMS-server                │
│                                          │
│  Webbgränssnitt                          │
│  Autentisering / Sessioner               │
│  RBAC                                    │
│  API                                     │
│  Klienthantering                         │
│  Paketsökning                            │
│  Uppdateringsjobbshantering              │
│  Granskningsloggning                     │
│  SQLite-persistens                       │
└───────────────────┬──────────────────────┘
                    │
                    │ HTTPS / Klient-API
                    ▼
┌──────────────────────────────────────────┐
│               LUMS-agent                  │
│                                          │
│  Autentisering                           │
│  Inventarierapportering                  │
│  Uppdateringsdetektering                 │
│  Paketsökning                            │
│  Jobbkörning                             │
│  Resultatrapportering                    │
│  Omstartsdetektering                     │
│  Inaktivitetsdetektering                 │
└───────────────────┬──────────────────────┘
                    │
                    ▼
          ┌────────────────────┐
          │ Pakethanterare     │
          │                    │
          │ APT / dpkg         │
          │ pacman             │
          └────────────────────┘
```

---

## Serverkomponenter

LUMS-servern tillhandahåller det centrala hanteringslagret.

### Webbapplikation

Webbapplikationen tillhandahåller det administrativa gränssnittet för:

* klienthantering
* programvaruinventering
* uppdateringsinformation
* uppdateringsjobb
* pakethantering
* uppdateringshistorik
* användarhantering
* systemunderhåll

Gränssnittet respekterar den aktuella användarens RBAC-roll.

Frontend-synlighet anpassas därför till användarens behörigheter, men auktorisering upprätthålls alltid även på serversidan.

---

### API

API:et ansluter webbgränssnittet och Linux-klienterna till applikationslogiken på serversidan.

Det hanterar operationer som:

* klientregistrering och -hantering
* klientrapporter
* paketsökningar
* paketsökresultat
* uppdateringsjobb
* jobbresultat
* användarhantering
* granskningshändelser

API-slutpunkter validerar sin indata innan de utför tillståndsändrande operationer.

---

### Autentisering och sessioner

Administrativa användare autentiserar sig via LUMS webbapplikation.

Sessioner kontrolleras av servern och stöder explicit sessionsåterkallning.

Autentiseringssäkerhet inkluderar:

* lösenordshashning med Argon2
* sessionshantering
* sessionsåterkallning
* inloggningsfrekvensbegränsning
* CSRF-skydd
* rollbaserad auktorisering

Klientautentisering är separat från administrativ autentisering.

---

### RBAC

LUMS kombinerar rollmallar med behörigheter per användare. Mallarna Administrator,
Operator och Viewer tillhandahåller startbehörighetsuppsättningar som kan
anpassas för varje konto.

Auktorisering upprätthålls på servern med hjälp av kontots lagrade behörigheter.

Frontend döljer dessutom funktionalitet som användarens behörigheter inte
tillåter.

Detta innebär att det att dölja en knapp aldrig behandlas som en säkerhetsgräns.

---

### SQLite-persistens

LUMS använder SQLite för beständigt applikationstillstånd.

Databasen lagrar information som:

* användare
* sessioner
* klienter
* klientautentiseringstillstånd
* programvaruinventering
* tillgängliga uppdateringar
* uppdateringsjobb
* jobbresultat på paketnivå
* paketsökförfrågningar och resultat
* granskningsinformation

Applikationen aktiverar uttryckligen SQLite-främmandenyckelkontroll för databasanslutningar.

Den nuvarande produktionsbaslinjen för SQLite är:

```text
journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

LUMS använder SQLite WAL-läge i den nuvarande produktionskonfigurationen.

---

## Containerarkitektur

LUMS-servern distribueras som en härdad Docker-container.

Applikationscontainern behandlas avsiktligt som engångs.

Beständigt applikationstillstånd lagras i den dedikerade Docker-volymen:

```text
lums-data
```

Produktionscontainern använder ett skrivskyddat rotfilsystem.

Skrivbara platser är avsiktligt begränsade till nödvändiga körnings- och beständiga lagringsvägar.

Produktionssäkerhetsbaslinjen inkluderar:

```text
skrivskyddat rotfilsystem
alla Linux-kapaciteter borttagna
no-new-privileges
begränsad /tmp
begränsad /run
skrivskyddad hemlighetsmontering
dedikerad beständig datavolym
icke-root-applikationsanvändare
```

Applikationen exponeras internt via:

```text
127.0.0.1:5050
```

Extern HTTPS-åtkomst tillhandahålls via omvänd proxy.

---

## Beständiga och engångskomponenter

LUMS separerar beständigt tillstånd från utbytbara körtidskomponenter.

```text
Beständigt
├── SQLite-databas
├── klienttillstånd
├── användartillstånd
├── jobbtillstånd
└── granskningstillstånd

Engångs
├── Docker-container
├── applikationsprocess
└── genererat körtidstillstånd
```

Att ersätta applikationscontainern tar därför inte automatiskt bort LUMS-databasen.

Denna separation är viktig för uppgraderingar och återställning.

---

## Klientarkitektur

Linux-klienten består av flera samverkande komponenter.

### LUMS-agent

Agenten ansvarar för interaktion med LUMS-servern och det lokala Linux-systemet.

Aktuell agentversion:

```text
1.7.0
```

Agenten hanterar:

* autentisering
* inventeringsinsamling
* uppdateringsdetektering
* paketsökning
* paketåtgärder
* uppdateringsjobbkörning
* resultatrapportering
* omstartsdetektering
* inaktivitetshantering

---

### Pakethanterarlager

Pakethanterarlagret tillhandahåller en kontrollerad abstraktion runt den inbyggda Linux-pakethanteraren.

Agenten kräver inte att LUMS ersätter pakethanteraren.

Istället:

```text
LUMS-åtgärd
     │
     ▼
Pakethanterarabstraktion
     │
     ├── Debian / Ubuntu → APT / dpkg
     │
     └── Arch Linux      → pacman
```

Detta håller distributionsspecifik pakethantering inne i klienten.

---

### Execution Watcher

Watchern övervakar uppdateringsjobbkörning på klienten.

Aktuell watcherversion:

```text
1.2.1
```

Watchern arbetar tillsammans med agenten och jobbtillståndet på serversidan.

Dess syfte är att säkerställa att jobb som förväntas köras inte förblir obearbetade på obestämd tid.

---

## Rapporteringsväg

Normal klientrapportering följer denna riktning:

```text
Linux-klient
    │
    │ inventering / uppdateringsinformation
    ▼
LUMS API
    │
    ▼
SQLite
    │
    ▼
Webbgränssnitt
```

Till exempel producerar en uppdateringskontroll som utförs av klienten information som rapporteras till servern och lagras som klientens aktuella uppdateringstillstånd.

Webbläsaren frågar inte direkt klientens pakethanterare.

---

## Paketsökningsväg

Paketsökning följer ett annat förfrågan/svarsflöde:

```text
Webbläsare
   │
   │ sökförfrågan
   ▼
LUMS-server
   │
   │ paketsökförfrågan
   ▼
Linux-klient
   │
   │ APT / pacman-sökning
   ▼
Linux-klient
   │
   │ sökresultat
   ▼
LUMS-server
   │
   ▼
Webbläsare
```

Servern behöver därför inte underhålla ett komplett fjärrpaketförrådsindex för varje klient.

Sökningen utförs med klientens egen pakethanteringsmiljö.

---

## Uppdateringskörningsväg

Ett uppdateringsjobb följer den allmänna arkitekturen:

```text
Webbläsare
   │
   │ skapa jobb
   ▼
LUMS API
   │
   │ validera förfrågan
   ▼
SQLite
   │
   │ beständigt jobb
   ▼
Linux-klient
   │
   │ utför åtgärd
   ▼
APT / dpkg / pacman
   │
   │ resultat
   ▼
Linux-klient
   │
   │ validerat resultat
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Webbläsare
```

Detta skapar den centrala LUMS-körningskedjan:

> **Webbläsare → API → SQLite → Agent → Pakethanterare → Resultat → SQLite → UI**

---

## Atomisk jobbtilldelning

Uppdateringsjobb är beständiga objekt på serversidan.

Innan körning måste agenten erhålla ett jobb som är kvalificerat för körning.

Jobbtilldelning utförs atomiskt så att samma väntande jobb inte oavsiktligt tilldelas flera körningsvägar.

Detta är särskilt viktigt när timers, återförsök, återställning eller flera klientprocesser är inblandade.

---

## Jobbkörning

Servern skapar strukturerade jobb.

Klientagenten tolkar de åtgärder som stöds och utför motsvarande lokala operation.

Paketåtgärderna som stöds är:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Paketnamn valideras innan ett paketjobb skapas.

Agenten behandlar inte paketnamn som godtyckliga skalfragment.

---

## Pakethanterarabstraktion

Paketåtgärder implementeras avsiktligt bakom en pakethanterarabstraktion.

Detta håller den högre LUMS-jobbmodellen oberoende av distributionsspecifika kommandon.

Till exempel:

```text
INSTALL_PACKAGE
       │
       ├── Debian / Ubuntu → APT
       │
       └── Arch Linux      → pacman
```

Samma princip gäller för borttagning och paketuppdateringar.

---

## Debian / Ubuntu

På Debian-familjens system använder LUMS den inbyggda APT/dpkg-verktygskedjan.

Typiska ansvarsområden inkluderar:

* paketsökning
* paketmetadatauppslag
* paketinstallation
* borttagning av paket
* paketuppdateringar
* systemuppdateringar
* uppdateringsdetektering

LUMS-agenten ersätter inte APT.

Den tillhandahåller kontrollerad orkestrering runt det.

---

## Arch Linux

På Arch Linux-system använder LUMS den inbyggda pacman-pakethanteraren.

Typiska ansvarsområden inkluderar:

* paketsökning
* paketmetadatauppslag
* paketinstallation
* borttagning av paket
* paketuppdateringar
* systemuppdateringar
* uppdateringsdetektering

Distributionsspecifikt beteende förblir inne i pakethanterarlagret.

---

## Paketsökning

Paketsökning är separat från inventeringen av installerad programvara.

Denna distinktion är viktig:

```text
Installerad programvara
        │
        └── Vad är redan installerat?

Pakethanteringssökning
        │
        └── Vilket paket kan klienten för närvarande hitta?
```

Sökresultat kan innehålla paketinformation som:

* paketnamn
* version
* beskrivning
* förrådsinformation där tillgänglig

Sökresultat returneras till LUMS-servern och visas i pakethanteringsgränssnittet.

---

## Behörigheter för pakethantering

Pakethantering är en privilegierad operation.

Den nuvarande behörighetsmodellen är:

```text
Administratör → tillåten
Operator      → tillåten
Viewer        → inte tillåten
```

En Viewer kan fortfarande inspektera installerad programvara.

Själva pakethanteringsgränssnittet är dolt för Viewers, och motsvarande mutationsslutpunkter på serversidan upprätthåller auktorisering oberoende.

---

## Hantering av uppdateringsresultat

LUMS behandlar resultatet av en uppdateringsåtgärd som strukturerat tillstånd istället för att bara visa rå kommandoutdata.

Relevant information kan inkludera:

* framgång eller misslyckande
* resultat på paketnivå
* körningstillstånd
* felinformation
* omstartsbehov
* tidsstämplar för slutförande

Detta gör det möjligt för servern att upprätthålla en meningsfull uppdateringshistorik.

---

## Omstartsdetektering

Efter paketåtgärder kontrollerar klienten om operationen indikerar att en omstart krävs.

Resultatet rapporteras till servern som en del av jobbresultatet.

Ett omstartsbehov förblir därför associerat med uppdateringsoperationen istället för att gå förlorat i en klientsidans terminalsession.

---

## Klientautentiseringsgräns

Klient-API:et använder en separat autentiseringsmekanism från administrativa webbsessioner.

```text
Administrativ användare
        │
        ▼
 Webbautentisering
        │
        ▼
    LUMS-server

Linux-klient
        │
        ▼
 Klienttoken
        │
        ▼
    LUMS-server
```

Denna separation förhindrar att administrativa webbläsarsessioner och klientuppgifter blir utbytbara autentiseringsmekanismer.

---

## Granskningsspår

Säkerhetsrelevanta och administrativa åtgärder registreras av granskningssystemet på serversidan.

Granskningsspåret kompletterar normal applikationsloggning.

Loggning svarar på frågor om applikationsbeteende.

Granskningsloggning registrerar dessutom viktiga administrativa åtgärder och deras sammanhang.

Denna distinktion är användbar vid utredning av ändringar i klienter, användare, autentiseringstillstånd eller uppdateringsjobb.

---

## Driftsprincip

LUMS separerar avsiktligt:

```text
Hantering
     │
     ▼
Policy / Auktorisering
     │
     ▼
Jobb
     │
     ▼
Klientkörning
     │
     ▼
Inbyggd pakethanterare
```

Varje lager har ett definierat ansvar.

Servern hanterar.

Agenten utför.

Pakethanteraren utför den faktiska systemändringen.

Resultatet färdas tillbaka genom samma kontrollerade kedja.

## Rollbaserad åtkomstkontroll

LUMS använder tre administrativa roller:

```text
Administratör
Operator
Viewer
```

Auktorisering upprätthålls på serversidan.

Frontend anpassar dessutom det synliga gränssnittet till användarens
behörigheter, men frontend-synlighet betraktas aldrig som en säkerhetsgräns.

### Administratör

Administratörer har tillgång till:

* visa klienter
* visa installerad programvara
* visa tillgängliga uppdateringar
* skapa och köra uppdateringsjobb
* visa uppdateringshistorik
* använda pakethantering
* utföra systemunderhåll
* skapa och inaktivera klienter
* rotera klienttoken
* skapa och hantera användare
* hantera roller och användaråtkomst

### Operator

Operatorer har tillgång till:

* visa klienter
* visa installerad programvara
* visa tillgängliga uppdateringar
* skapa och köra uppdateringsjobb
* visa uppdateringshistorik
* använda pakethantering
* utföra systemunderhåll

Operatorer har inte tillgång till:

* användarhantering
* rolladministration
* skapande eller inaktivering av klienter
* rotation av klienttoken

### Viewer

Viewers har skrivskyddad åtkomst till:

* klienter
* installerad programvara

Följande funktionalitet är otillgänglig för Viewers:

* hantering av tillgängliga uppdateringar
* uppdateringsjobb
* uppdateringshistorik
* pakethantering
* systemunderhåll
* andra tillståndsändrande administrativa operationer

Servern upprätthåller dessa begränsningar oberoende.

---

## Användarhantering

LUMS tillhandahåller användarhantering för konton med behörigheten `users.manage`.

Användare med denna behörighet kan skapa konton med en rollmall och
sedan tilldela behörigheter individuellt eller uttryckligen tillämpa den mallen. Nya
konton börjar utan behörigheter; behörighetsredigeraren öppnas efter skapandet.
Användarhanterare kan också spara privata administrativa anteckningar som inte är synliga
för kontoinnehavaren.

Administratörer med `backups.manage` kan skapa validerade `.db`- eller `.db.gz`-
databassäkerhetskopior i en serverkonfigurerad katalog och välja en säker undermapp
inom den monterade platsen. Se [`administration.md`](<Administration och säkerhetskopior.md>) och
den inbyggda Markdown-återställningsguiden för Docker-lagringsinställning och återställning.

Användarlösenord lagras med Argon2-lösenordshashning snarare än klartext eller reversibel kryptering.

Användarhanteringsoperationer skyddas av:

* autentisering
* behörighetsbaserad auktorisering
* CSRF-skydd
* inmatningsvalidering
* dubblettanvändarkontroller
* granskningsloggning

Användarhanteringsgränssnittet exponeras inte utan `users.manage`.

---

## Sessionssäkerhet

Administrativ autentisering använder sessionshantering på serversidan.

Sessionssäkerhet inkluderar:

* autentiserat sessionstillstånd
* sessionsåterkallning
* CSRF-skydd för tillståndsändrande förfrågningar
* inloggningsfrekvensbegränsning
* tvång för inaktiverade konton
* rollkontroller

Att återkalla en session ogiltigförklarar motsvarande autentiserade tillstånd istället för att bara dölja användargränssnittet.

---

## Inloggningsfrekvensbegränsning

Upprepade misslyckade inloggningsförsök är föremål för progressiv frekvensbegränsning.

De nuvarande tröskelvärdena är:

```text
5 försök  → 30 sekunder
6 försök  → 60 sekunder
7 försök  → 120 sekunder
8+ försök → 300 sekunder
```

Det relevanta tillståndet lagras i SQLite.

Framgångsrik autentisering rensar det tillämpliga feltillståndet.

Detta förhindrar att en enkel applikationsomstart används för att kringgå inloggningsskyddet.

---

## Klientsäkerhet för token

Varje registrerad klient har sin egen autentiseringstoken.

Servern lagrar tokenet som en SHA-256-sammanfattning.

Det ursprungliga tokenet krävs inte för normal validering på serversidan.

Tokenrotation gör det möjligt för administratörer att ogiltigförklara en befintlig uppgift och utfärda en ersättning.

Detta skapar en tydlig livscykel:

```text
Skapa
  │
  ▼
Använd
  │
  ▼
Rotera
  │
  ▼
Gammalt token ogiltigt
```

---

## API-säkerhet

LUMS validerar API-indata innan tillståndsändrande operationer utförs.

Säkerhetskontroller inkluderar:

* autentisering
* behörighetsauktorisering per användare
* CSRF-skydd där tillämpligt
* inmatningsvalidering
* paketnamnsvalidering
* strukturerade jobbåtgärder
* parametriserade databasfrågor
* kontrollerad felhantering

Applikationen använder inte användartillhandahållna paketnamn som obegränsade skalkommandon.

---

## SQL-injektionsskydd

Databasoperationer använder parametriserade SQL-satser.

Användarkontrollerade värden sammanfogas inte direkt i SQL-frågor.

Detta gäller områden som:

* autentisering
* klienthantering
* användarhantering
* paketsökningar
* uppdateringsjobb
* granskningsdata
* resultatrapportering

Målet är att hålla datavärden separerade från SQL-instruktioner.

---

## SQLite-säkerhetsbaslinje

Den nuvarande produktionskonfigurationen för SQLite är:

```text
journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

Främmandenyckelkontroll aktiveras uttryckligen av applikationen för databasanslutningar.

Den nuvarande konfigurationen använder WAL-läge.

Databasen lagras i den beständiga Docker-volymen snarare än i det engångsmässiga applikationscontainerfilsystemet.

---

## Jobbåterställning och kontrollpunkter

LUMS behandlar uppdateringsjobb som beständiga tillståndsmaskiner.

Ett jobb med flera paket kan innehålla flera individuella paketåtgärder.

Varje paketobjekt kan nå sitt eget resultattillstånd.

Om körningen avbryts kan återställning skilja mellan:

```text
redan framgångsrik
        │
        └── upprepa inte i onödan

inte slutförd
        │
        └── kvalificerad för återställning
```

Detta minskar risken för att blint upprepa slutförda paketåtgärder efter ett avbrott.

---

## Kontrollerad uppdateringskörning

LUMS begränsar avsiktligt de åtgärder som kan begäras via uppdateringsjobb-API:et.

Åtgärder som stöds är:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Servern validerar åtgärden och relevant paketinformation innan jobbet skapas.

Agenten mappar sedan den strukturerade åtgärden till lämplig pakethanteraroperation.

Detta undviker att göra uppdateringssystemet till en generisk mekanism för fjärrkommandokörning.

---

## Paketåtgärder

Paketåtgärder utförs genom klientens inbyggda pakethanterare.

### Installation

Ett validerat paketnamn skickas till pakethanterarabstraktionen för installation.

### Borttagning

Ett validerat paketnamn skickas till pakethanterarabstraktionen för borttagning.

### Paketuppdatering

Ett specifikt paket kan uppdateras när klienten rapporterar det som en tillgänglig uppdatering.

### Systemuppdatering

Systemuppdateringsåtgärden delegerar uppdateringsprocessen till den inbyggda pakethanteraren.

Alla operationer returnerar strukturerade resultat till LUMS-servern.

---

## Pakethanterarens säkerhet

LUMS behandlar pakethanteraren som en privilegierad lokal komponent.

Agenten försöker därför inte efterlikna pakethanterarens beteende själv.

Istället:

1. validerar den begärda åtgärden
2. väljer lämplig pakethanterarimplementation
3. utför den kontrollerade operationen
4. fångar resultatet
5. rapporterar resultatet till servern

Distributionsspecifikt beteende förblir isolerat inne i pakethanterarlagret.

---

## Omstartshantering

Vissa paketåtgärder kan kräva en omstart.

LUMS registrerar omstartsbehov som en del av uppdateringsjobbresultaten.

Detta gör det möjligt för administratörer att skilja mellan:

```text
Uppdatering slutförd
```

och:

```text
Uppdatering slutförd
Omstart krävs
```

Omstartsbehovet är därför en del av driftstillståndet snarare än att behandlas som en orelaterad avisering.

---

## Granskningsloggning

LUMS upprätthåller ett applikationsgranskningsspår för viktiga administrativa och säkerhetsrelevanta åtgärder.

Exempel inkluderar:

* autentiseringsrelaterade händelser
* klienthantering
* tokenoperationer
* användarhantering
* skapande av uppdateringsjobb
* säkerhetskänsliga tillståndsändringar

Granskningsloggning är separat från vanlig diagnostisk loggning.

Diagnostiska loggar hjälper till att felsöka applikationen.

Granskningsposter tillhandahåller en administrativ historik över relevanta åtgärder.

---

## Säkerhetshärdning

Den nuvarande distributionen inkluderar flera lager av härdning.

### Containerhärdning

Produktionscontainern använder:

* icke-root-applikationskörning
* skrivskyddat rotfilsystem
* borttagna Linux-kapaciteter
* `no-new-privileges`
* begränsade temporära filsystem
* skrivskyddad hemlighetsmontering
* dedikerad beständig datavolym

### Nätverkshärdning

Applikationscontainern är bunden till loopback på värden:

```text
127.0.0.1:5050
```

Applikationsporten är därför inte direkt exponerad som en LAN-tjänst.

Extern åtkomst hanteras via HTTPS-omvänd proxy.

Brandväggen exponerar inte den interna applikationsporten.

### Transportskydd

Administrativ åtkomst tillhandahålls via HTTPS.

Den omvända proxyn hanterar extern TLS-terminering.

HTTP-förfrågningar omdirigeras till HTTPS.

### Hemligheter och konfiguration

Känsliga körtidsuppgifter hålls utanför applikationens källträd.

Produktionshemligheten monteras i containern som en skrivskyddad hemlighetsfil.

Regler för repository och Docker-byggkontext förhindrar att vanliga säkerhetskopior, hemligheter, databaser och certifikatartefakter oavsiktligt kommer in i avbildningsbyggkontexten.

### Beroende- och byggsäkerhet

Produktions-Python-beroendena är fastnålade.

Produktions-Python-basavbildningen är fastnålad med sammanfattning.

Docker-byggkontexten begränsas genom `.dockerignore`.

Dessa kontroller förbättrar byggbarheten och minskar risken för att känsliga filer oavsiktligt inkluderas.

---

## Status för säkerhetsgranskning

LUMS säkerhetsgranskning har täckt följande områden:

* SQLite-främmandenyckelkontroll
* SQLite-körtidskonfiguration
* uppdateringstidsgräns och processhantering
* inloggningsfrekvensbegränsning
* API-indatavalidering
* sessionsåterkallning
* klienttokenrotation
* offline/IP-hantering
* jobbåterställning och kontrollpunkter
* APT-robusthet
* Arch-omstartsdetektering
* enhets- och API-resultatvalidering
* simuleringstestning
* kontinuerlig integration
* applikations- och granskningsloggning
* versions- och utgivningshantering
* RBAC
* sessions- och CSRF-säkerhet
* uppgiftssäkerhet
* beroende- och byggsäkerhet
* Docker/containerhärdning
* hemlighets- och byggkontextskydd
* HTTP/transportskydd
* filsystem/körtidsbehörigheter
* nätverksexponering
* repository-artefakthygien

Den återstående dokumentationsgranskningen hanteras separat som en del av den slutliga utgivningsberedskapsprocessen.

---

## Testning och CI

LUMS inkluderar automatiska tester som täcker kärnapplikationsbeteende och säkerhetskontroller.

Kör den fullständiga testsviten från repositoryts rot:

```bash
./.venv-test/bin/pytest -q
```

Antalet tester ändras över tid. Det önskade resultatet är att den fullständiga
sviten slutförs framgångsrikt utan fel. Testsuiten inkluderar täckning
för områden som:

* autentisering
* RBAC
* klienthantering
* användarhantering
* paketsökning
* uppdateringsjobb
* jobbresultatvalidering
* säkerhetsbeteende
* API-beteende

Kontinuerlig integration kör den automatiska testsviten innan ändringar anses redo.

En framgångsrik testkörning krävs, men tester är bara en del av utgivningsprocessen.

Utgivningsprocessen kräver också:

```text
Implementering
    ↓
Säkerhetsgranskning
    ↓
Dokumentationsgranskning
    ↓
Fullständig testsvit
    ↓
CI
    ↓
Version
    ↓
Git-tagg
    ↓
GitHub-utgivning
```

---

## Utvecklingsstatus

LUMS är för närvarande under aktiv utveckling.

Kärnhanteringsarkitekturen, klientkörningsmodellen, pakethantering, RBAC, säkerhetshärdning och återställningsmekanismer är implementerade.

Projektet anses avsiktligt inte vara en färdig utgåva bara för att applikationen är funktionell.

Utgivningsberedskap kräver också att den omgivande dokumentationen och driftprocedurerna beskriver samma aktuella system.

Det är därför dokumentationskonsekvens behandlas som en del av ingenjörsprocessen snarare än som en eftertanke.

## Stödda system

LUMS är designat för att hantera Linux-system med stödda inbyggda pakethanterare.

### Debian / Ubuntu

Pakethanteringsstack som stöds:

```text
APT
dpkg
```

Klienten använder Debian inbyggda pakethanteringsverktyg för:

* paketinventering
* uppdateringsdetektering
* paketsökning
* paketinstallation
* borttagning av paket
* paketuppdateringar
* systemuppdateringar

### Arch Linux

Pakethanteringsstack som stöds:

```text
pacman
```

Klienten använder Arch inbyggda pakethanteringsverktyg för:

* paketinventering
* uppdateringsdetektering
* paketsökning
* paketinstallation
* borttagning av paket
* paketuppdateringar
* systemuppdateringar

---

## Klientkrav

En hanterad Linux-klient kräver:

* en Linux-distribution som stöds
* LUMS-agenten
* nätverksanslutning till LUMS-servern
* ett registrerat klienttoken
* en fungerande inbyggd pakethanterare
* systemd för de timer-/tjänstbaserade körningskomponenterna

Klienten kräver inte att LUMS-servern direkt kommer åt dess paketdatabas.

Klienten utför lokala paketåtgärder och rapporterar resultaten till servern.

---

## Teknikstack

### Server

* Python
* Flask
* Gunicorn
* SQLite
* HTML
* CSS
* JavaScript
* Nginx
* Docker

### Autentisering och säkerhet

* Argon2-lösenordshashning
* sessioner på serversidan
* CSRF-skydd
* rollmallar med behörigheter per användare
* SHA-256-klienttokensammanfattningar
* HTTPS
* granskningsloggning

### Klient

* Python
* systemd
* APT / dpkg
* pacman
* `loginctl` där inaktivitetsinformation är tillgänglig

---

## Projektstruktur

Repositoryt är organiserat i separata server-, klient-, frontend- och testkomponenter.

En förenklad struktur är:

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
└── dokumentation
```

Den exakta repositorylayouten kan utvecklas i takt med att LUMS utvecklas.

Den arkitektoniska separationen mellan server, agent, pakethanterarabstraktion, frontend och tester är avsiktlig.

---

## Serverapplikation

Flask-applikationen tillhandahåller det centrala LUMS-API:et och webbgränssnittet.

Dess ansvarsområden inkluderar:

* autentisering
* auktorisering
* sessionshantering
* klienthantering
* användarhantering
* programvaruinventering
* uppdateringsinventering
* paketsökning
* uppdateringsjobb
* jobbresultathantering
* granskningsloggning
* databaspersistens

Applikationen serveras av Gunicorn inuti containern.

Nginx tillhandahåller den externa HTTPS-ingångspunkten.

---

## Agent

LUMS-agenten installeras direkt på hanterade Linux-klienter.

Aktuell agentversion:

```text id="w8p4wz"
1.7.0
```

Agenten ansvarar för klientsidans del av LUMS-körningskedjan.

Dess ansvarsområden inkluderar:

* rapportering av klienttillstånd
* insamling av installerad programvara
* detektering av tillgängliga uppdateringar
* sökning av paket
* utförande av paketåtgärder
* rapportering av jobbresultat
* detektering av omstartsbehov
* hantering av inaktivitetsinformation
* deltagande i jobbåterställning

Agenten tillhandahåller inte ett obegränsat fjärrskal.

---

## Pakethanterarlager

Pakethanterarimplementationen isolerar distributionsspecifikt beteende från resten av agenten.

Konceptuellt:

```text id="zq8xq3"
Agent
  │
  ▼
Pakethanterargränssnitt
  │
  ├── Debian / Ubuntu
  │      └── APT / dpkg
  │
  └── Arch Linux
         └── pacman
```

Detta gör det möjligt för det högre uppdateringsjobbsystemet att arbeta med strukturerade operationer utan att behöva känna till varje distributionsspecifikt kommando.

---

## Watcher

LUMS execution watcher övervakar jobb som förväntas köras på klienten.

Aktuell watcherversion:

```text id="7k6w3s"
1.2.1
```

Watchern arbetar tillsammans med agenten och jobbtillståndet på serversidan.

Denna arkitektur gör det möjligt för LUMS att upptäcka körningssituationer där ett jobb förblir väntande eller på annat sätt kräver uppmärksamhet.

---

## systemd-integration

Klienten använder systemd för schemalagd och kontrollerad körning.

Relevanta komponenter inkluderar tjänste- och timerenheter för:

* klientrapportering
* uppdateringsdetektering
* jobbkörning/övervakning

Detta ger förutsägbar körning utan att kräva en kontinuerligt körande förgrundsprocess för varje periodisk operation.

Klientagenten kan också köras manuellt under installation och felsökning.

---

## Inaktivitetsmedveten körning

Inaktivitetsmedveten körning är utformad för att minska störningar för aktiva användare.

Den nuvarande inaktivitetsgränsen är:

```text id="g8v0lq"
300 sekunder
```

Klienten bestämmer inaktivitetstillstånd med hjälp av tillgänglig lokal sessionsinformation.

Där det stöds används `loginctl`.

Agenten skiljer mellan:

```text id="6v3m4k"
bekräftat inaktiv
aktiv
inaktivitetstillstånd otillgängligt
```

Ett otillgängligt inaktivitetstillstånd tolkas inte tyst som inaktivt.

Detta gör körningsbeslutet explicit och diagnostiserbart.

---

## Livscykel för uppdateringsjobb

Den fullständiga livscykeln för ett uppdateringsjobb kan representeras som:

```text id="h4d9kv"
Skapa
  │
  ▼
Validera
  │
  ▼
Beständiggör
  │
  ▼
Gör anspråk
  │
  ▼
Kör
  │
  ├──────────────► SUCCESS
  │
  ├──────────────► FAILED
  │
  └──────────────► RECOVERY
                         │
                         ▼
                      Kör
```

Ett jobb beständiggörs före körning.

Detta innebär att servern behåller kunskap om den avsedda operationen även om klienten eller applikationen avbryts.

---

## Jobbtyper

LUMS stöder för närvarande strukturerade uppdateringsåtgärder inklusive:

```text id="v7r1f8"
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Dessa åtgärder är avsiktligt begränsade.

LUMS är ett uppdateringshanteringssystem, inte ett generellt ramverk för fjärrkommandon.

---

## Jobbtillstånd på paketnivå

Jobb som innehåller flera paket kan spåra framsteg på paketnivå.

Till exempel:

```text id="v9w1sh"
Jobb #42

package-a → SUCCESS
package-b → SUCCESS
package-c → FAILED
package-d → PENDING
```

Återställning kan därför arbeta på de ofullständiga delarna av jobbet istället för att blint upprepa framgångsrika paketåtgärder.

---

## Jobbåterställning

Återställning är utformad kring beständiga kontrollpunkter.

Servern upprätthåller jobbtillståndet.

Klienten rapporterar resultat på paketnivå.

Om körningen avbryts kan servern avgöra vilket arbete som redan slutförts och vilket arbete som återstår kvalificerat för återställning.

Den avsedda återställningsprincipen är:

> **Fortsätt från känt tillstånd istället för att anta att ingenting hände.**

---

## Resultatvalidering

Klientjobbresultat valideras innan de accepteras i beständigt servertillstånd.

Detta skyddar jobbtillståndet från felaktiga eller ofullständiga resultatinlämningar.

Validering tillämpas på relevanta fält som:

* jobbidentitet
* körningstillstånd
* paketresultatdata
* felinformation
* omstartsinformation

Resultatbearbetningslagret fungerar därför som en annan gräns mellan en autentiserad klient och beständigt servertillstånd.

---

## Användarhantering

Användarhantering kräver behörigheten `users.manage`.

Behöriga användare kan skapa användare från en rollmall och anpassa de
individuella behörigheter som tilldelats varje konto.

De nuvarande rollerna är:

```text id="2xqv79"
Administratör
Operator
Viewer
```

Användarhanteringsåtgärder autentiseras, behörighetskontrolleras, valideras,
skyddas mot CSRF där tillämpligt och registreras i granskningsspåret.

---

## Klienthantering

Administratörer kan hantera registrerade klienter.

Klienthanteringsfunktioner inkluderar:

* registrering
* inaktivering
* tokenrotation
* inspektion av klientstatus

Klientautentisering är oberoende för varje registrerad klient.

Att inaktivera en klient förhindrar den från att fortsätta normal autentiserad kommunikation med servern.

---

## Uppdateringshistorik

LUMS upprätthåller beständigt uppdateringsjobbtillstånd så att slutförda och misslyckade operationer förblir synliga efter körning.

Behöriga användare kan inspektera historiken över uppdateringsoperationer enligt sin roll.

Historiken är avsedd att ge operativt sammanhang snarare än att bara visa den senaste paketinventeringen.

---

## Granskningsbarhet

LUMS upprätthåller två relaterade men distinkta former av operativ information:

### Applikationsloggar

Används främst för:

* diagnostik
* fel
* körtidsbeteende
* felsökning

### Granskningsloggar

Används främst för:

* administrativa åtgärder
* säkerhetsrelevanta händelser
* ändringar av viktigt tillstånd
* ansvarsskyldighet

Att hålla dessa begrepp separerade gör felsökning och administrativ granskning enklare.

---

## Teststrategi

LUMS testsvit täcker flera lager av applikationen.

### Autentisering

Tester täcker autentiseringsbeteende, sessionshantering och säkerhetskontroller.

### RBAC

Tester verifierar att:

* Administratörer kan utföra administrativa åtgärder
* Operatorer får sina tillåtna hanteringsfunktioner
* Viewers förblir skrivskyddade

### Pakethantering

Tester täcker paketsökningsbeteende och API-hantering relaterad till pakethantering.

### Uppdateringsjobb

Tester täcker:

* jobbskapande
* validering
* tillståndsövergångar
* resultathantering
* återställningsbeteende

### Säkerhet

Tester täcker säkerhetskänsligt applikationsbeteende och regressionsfall.

### Fullständig svit

Kör den fullständiga testsviten från repositoryts rot:

```bash
./.venv-test/bin/pytest -q
```

Testantalet ändras i takt med att projektet utvecklas; förlita dig på kommandots resultat,
inte ett fast antal som tryckts i detta dokument.

---

## Kontinuerlig integration

Projektet använder kontinuerlig integration för att köra automatiska kontroller mot ändringar.

CI-pipelinen hjälper till att upptäcka regressioner innan ändringar behandlas som utgivningsklara.

Utvecklingsarbetsflödet är därför:

```text id="v3n9k8"
Ändring
  ↓
Test
  ↓
Säkerhetsgranskning
  ↓
Dokumentationsgranskning
  ↓
CI
  ↓
Utgivningsförberedelse
```

En framgångsrik CI-körning ersätter inte manuell säkerhets- eller dokumentationsgranskning.

---

## Dokumentation

LUMS underhåller separat dokumentation för olika operativa angelägenheter.

### `README.md`

Projektöversikt, arkitektur, funktioner, säkerhetsbaslinje, utvecklingsstatus och projektriktning.

### `install.md`

Installation, distribution, klientinstallation, validering, uppgradering och borttagningsprocedurer.

### `administration.md`

Rutinmässig administration, underhåll, säkerhetskopior, uppgraderingar, operativa procedurer och nödadministration.

### `security.md`

Säkerhetsarkitektur, säkerhetskontroller, granskningsresultat, härdning och säkerhetsinformation för utgivningsberedskap.

### `troubleshooting.md`

Diagnostiska procedurer för server-, klient-, jobb-, pakethanterings-, autentiserings-, databas-, container- och nätverksproblem.

### `LUMS_Optional_Theme_System.md`

Arkitektur och underhållsvägledning för valfria LUMS-frontendteman.

Dokumentationen är avsiktligt separerad efter ansvar så att operativa instruktioner inte blandas med säkerhetsdesign eller visuell anpassning.

---

## Dokumentationsprincip

Dokumentation behandlas som en del av systemet.

En funktion anses inte helt färdig när koden fungerar men dokumentationen fortfarande beskriver en äldre arkitektur.

Det avsedda förhållandet är:

```text id="0m1m5u"
Implementering
      │
      ├── Tester
      ├── Säkerhetsgranskning
      └── Dokumentation
               │
               ▼
          Utgivningsklar
```

Detta är särskilt viktigt för säkerhetskänsliga distributions- och administrationsprocedurer.

## Aktuell status

LUMS är en Linux-plattform för uppdateringshantering under aktiv utveckling.

Den nuvarande implementationen omfattar:

* centraliserad klienthantering
* programvaruinventering
* uppdateringsdetektering
* paketsökning
* paketinstallation och borttagning
* paketspecifika uppdateringar
* systemuppdateringar
* beständiga uppdateringsjobb
* jobbtillstånd på paketnivå
* jobbåterställning
* omstartsdetektering
* inaktivitetsmedveten körning
* klienttokenautentisering och tokenrotation
* administrativ autentisering
* roll- och behörighetsbaserad åtkomstkontroll
* användarhantering
* granskningsloggning
* containerhärdning och HTTPS-transport
* automatiserad testning och kontinuerlig integration
* valfri CPU-, minnes-, disk-, nätverks-, värd- och händelsetelemetri
* infrastrukturstopologi från registrerade klienter och manuellt underhållet inventarium
* beständiga larmuppgifter och gränssnitt för regelhantering, med de begränsningar som dokumenteras för implementationen

Listan är en översikt, inte ett påstående om fullständiga funktioner eller utgivningsberedskap. Valfria komponenter kan behöva installeras och konfigureras separat, och enskilda funktioner har dokumenterade begränsningar. Kontrollera källrevisionen och dess tester för beteendet i en viss utgåva.

Larmregler och deras villkor och tröskelvärden lagras, men servern utvärderar dem inte automatiskt mot telemetri. Larm utlöses manuellt. Leverantörer som anges i eskaleringsvägen kan anropas vid manuell utlösning, men webbappen skapar hanteraren med en tom leverantörskarta och integrationsgränssnitten kan inte konfigurera leverantörer. Gruppering och deduplicering lagras men tillämpas inte. Se de implementerade gränserna i `docs/LUMS_REALTIME_ALERTING_IMPLEMENTATION.md`.

---

## Säkerhetsstatus

De viktigaste säkerhetsgranskningsområdena har implementerats och granskats.

Den nuvarande säkerhetsbaslinjen inkluderar:

```text
Autentisering
    ├── Argon2-lösenordshashning
    ├── sessionshantering
    ├── sessionsåterkallning
    └── inloggningsfrekvensbegränsning

Auktorisering
    ├── Administratör
    ├── Operator
    └── Viewer

Klientsäkerhet
    ├── per-klient-token
    ├── SHA-256-tokensammanfattningar
    └── tokenrotation

API-säkerhet
    ├── inmatningsvalidering
    ├── CSRF-skydd
    ├── RBAC-upprätthållande
    └── parametriserad SQL

Körtidssäkerhet
    ├── icke-root-container
    ├── skrivskyddat rotfilsystem
    ├── borttagna kapaciteter
    ├── no-new-privileges
    ├── begränsade temporära filsystem
    └── skyddad hemlighetsmontering

Nätverkssäkerhet
    ├── HTTPS
    ├── omvänd proxy
    ├── loopback-applikationsbindning
    └── brandväggsbegränsningar
```

Säkerhet behandlas som ett pågående ingenjörsansvar snarare än en engångskontrolllista.

---

## Utgivningsstatus

Projektet följer avsiktligt utgivningssekvensen:

```text id="f3c4y9"
Implementering
      ↓
Säkerhetsgranskning
      ↓
Dokumentationsgranskning
      ↓
Fullständig testsvit
      ↓
CI
      ↓
Versionstilldelning
      ↓
Git-tagg
      ↓
GitHub-utgivning
```

Tillgängligheten för utgåvor och taggar kan ändras oberoende av dokumentationen. Kontrollera den aktuella statusen på repositoryts [utgivningssida](https://github.com/NovaForgeCtrl/LUMS/releases) och bland [taggarna](https://github.com/NovaForgeCtrl/LUMS/tags). En utgåva bör publiceras först när implementationen, säkerhetsgranskningen, dokumentationen och regressionstesterna för den revisionen är färdiga.

---

## Färdplan

Färdplanen är avsiktligt inriktad på stabilitet och underhållbarhet snarare än att lägga till funktioner utan att slutföra den befintliga grunden.

### Framtida utveckling

Potentiellt framtida arbete kan inkludera:

* ytterligare Linux-distributioner
* ytterligare pakethanterarbackends
* ytterligare UI-förbättringar
* ytterligare rapporteringsmöjligheter
* utökad operativ automatisering
* ytterligare säkerhetskontroller
* ytterligare testtäckning

Framtida funktioner bör bevara de befintliga arkitektoniska gränserna.

---

## Vad LUMS inte är

LUMS är avsiktligt inte designat som:

* ett generellt fjärrskal
* en ersättning för APT, dpkg eller pacman
* en fullständig plattform för konfigurationshantering
* en endpoint-hanteringssvit för alla operativsystem
* en molnbaserad tjänst
* ett okontrollerat ramverk för kommandokörning

LUMS fokuserar på ett smalare problem:

> **Kontrollerad hantering av Linux-programvara och uppdateringar med beständigt tillstånd och granskningsbarhet.**

---

## Utvecklingsfilosofi

LUMS följer en enkel utvecklingscykel:

```text id="8a0mve"
Bygg
  ↓
Testa
  ↓
Säkra
  ↓
Dokumentera
```

En funktion anses inte vara komplett bara för att den fungerar i utvecklarens miljö.

Den bör också vara:

* testad
* säkerhetsgranskad
* dokumenterad
* reproducerbar
* förståelig
* återställbar där så är lämpligt

---

## Ändringsfilosofi

Ändringar bör göras avsiktligt.

En typisk ändring bör svara på:

1. Vilket problem löser detta?
2. Vilken komponent bör äga ändringen?
3. Påverkar ändringen säkerheten?
4. Påverkar den beständigt tillstånd?
5. Påverkar den klienter?
6. Kräver den dokumentationsändringar?
7. Vilka tester bevisar att befintlig funktionalitet fortfarande fungerar?

Detta minskar risken för att fixa en del av systemet medan en annan del tyst går sönder.

---

## Utvecklingsarbetsflöde

Det föredragna utvecklingsarbetsflödet är:

```text id="r8u6o1"
Förstå
   ↓
Implementera
   ↓
Testa
   ↓
Inspektera
   ↓
Härda
   ↓
Dokumentera
   ↓
Regressionstesta
```

Säkerhetskänsliga ändringar får ytterligare verifiering innan de anses slutförda.

---

## Repository

Projektets repository finns på GitHub:

**NovaForgeCtrl/LUMS**

Repositoryt innehåller applikationens källkod, klientkomponenter, tester, containerkonfiguration och projektdokumentation.

---

## Dokumentationsuppsättning

Den nuvarande dokumentationsuppsättningen består av:

```text id="0xw7cy"
README.md
install.md
administration.md
security.md
troubleshooting.md
LUMS_Optional_Theme_System.md
```

Varje dokument har ett definierat syfte.

README ger projektöversikten.

Installationsguiden förklarar distribution.

Administrationsguiden förklarar löpande drift.

Säkerhetsguiden dokumenterar säkerhetsarkitekturen och granskningsstatusen.

Felsökningsguiden tillhandahåller diagnostiska procedurer.

Dokumentet om valfria teman täcker frontendtemaarkitektur.

---

## Licens

LUMS släpps under MIT-licensen.

Licensen är avsedd att hålla projektet öppet och tillgängligt samtidigt som den tillåter användning, modifiering och redistribution enligt licensvillkoren.

Se repositoryts licensfil för den fullständiga juridiska texten.

---

## Community och bidrag

LUMS är ett öppen källkods-projekt och bidrag är välkomna.

Användbara bidrag kan inkludera:

* felrapporter
* säkerhetsrapporter
* dokumentationsförbättringar
* tester
* pakethanterarstöd
* frontendförbättringar
* backendförbättringar
* distributionsförbättringar

Bidrag bör bevara projektets arkitektoniska och säkerhetsmässiga principer.

---

## Säkerhetsrapporter

Säkerhetsproblem bör inte behandlas som vanliga funktionsförfrågningar.

När du rapporterar ett säkerhetsproblem, tillhandahåll tillräckligt med information för att reproducera och förstå problemet utan att onödigtvis exponera känslig information.

Säkerhetsrelaterade ändringar bör granskas noggrant innan de slås samman.

---

## Projektidentitet

LUMS är byggt kring en enkel idé:

> **Linux-uppdateringshantering utan bruset.**

Projektet försöker inte dölja komplexitet genom att låtsas att Linux-pakethantering är enkelt.

Istället gör det relevant tillstånd synligt:

```text id="q2j5r0"
Vad är installerat?
        ↓
Vad kan uppdateras?
        ↓
Vad bör ändras?
        ↓
Vem begärde det?
        ↓
Vad hände faktiskt?
        ↓
Vilket tillstånd kvarstår?
```

Den informationen är grunden för kontrollerad uppdateringshantering.

---

## Slutlig arkitektur

På sin högsta nivå kan LUMS förstås som fem lager:

```text id="7b4p6n"
┌───────────────────────────────────────────────┐
│                    UI                         │
│       Mänsklig interaktion och synlighet      │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    API                        │
│    Autentisering, auktorisering, validering   │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                  Persistens                    │
│       Jobb, klienter, användare, resultat,    │
│       granskning                              │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    Agent                      │
│      Lokal körning och systemrapportering     │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│              Inbyggda Linux-verktyg           │
│              APT / dpkg / pacman              │
└───────────────────────────────────────────────┘
```

Varje lager har ett specifikt ansvar.

UI:t tillhandahåller interaktion.

API:et upprätthåller policy.

SQLite tillhandahåller beständigt tillstånd.

Agenten utför kontrollerad klientsidig körning.

Den inbyggda pakethanteraren utför den faktiska systemändringen.

---

## Slutlig princip

LUMS är byggt kring en central princip:

> **Observera systemet. Kontrollera ändringen. Registrera resultatet.**

Den principen gäller för programvaruarkitekturen, uppdateringskörningen, säkerhetsmodellen, återställningsmekanismerna och dokumentationen.

**Linux-uppdateringshantering utan bruset.**
