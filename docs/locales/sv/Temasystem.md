# LUMS — Valfritt temasystem

> **Ett LUMS · många gränssnitt · samma backend**

LUMS har ett valfritt klientbaserat temasystem som gör att användargränssnittets visuella utseende kan ändras utan att LUMS underliggande funktionalitet förändras.

Teman är enbart ett presentationslager. De ersätter, ändrar eller kringgår inte LUMS backend, autentisering, auktorisering, uppdateringskörning, pakethantering, klienthantering, jobbhantering eller säkerhetskontroller.

Temasystemet finns för att anpassa LUMS till olika visuella preferenser och samtidigt hålla själva applikationen konsekvent.

## Implementationsstatus och sanningskälla

Den aktuella implementationen i webbläsaren finns i `server/static/theme.js`. Den stöder `standard`, `LUMSStadium`, `golf`, `nerd`, `geek` och `admin`; lagrar valet i webbläsarens `localStorage` under `lums-theme`; och använder `standard` om den sparade identifieraren saknas eller är ogiltig. Temat `nerd` startar matrixeffekten och `geek` startar nätverkseffekten. Temavalet är en webbläsarpreferens, inte en kontoinställning eller ett auktoriseringstillstånd på servern.

Den här referensen innehåller också designkrav och konceptuella exempel. Formuleringar som ”bör”, ”måste” eller ”framtida” beskriver arkitekturvägledning, inte bevis för att en viss visuell funktion eller tillgänglighetsfunktion är implementerad. Kontrollera aktuellt beteende i källkoden innan ett koncept betraktas som en levererad funktion.

---

## 1. Översikt

Det valfria temasystemet gör att LUMS webbgränssnitt kan erbjuda flera visuella miljöer och samtidigt använda samma applikationsbackend.

Ett tema kan ändra:

* färger
* typografi
* bakgrunder
* dekorativa element
* visuell betoning
* navigeringens utseende
* animationer
* valfria visuella effekter
* sidans specifika presentation

Ett tema får inte ändra:

* användarbehörigheter
* tillgängliga API-slutpunkter
* autentiseringsbeteende
* auktoriseringsbeslut
* CSRF-skydd
* klientautentisering
* uppdateringskörning
* behörigheter för pakethantering
* hantering av jobbtillstånd
* granskningsloggning
* databeteende
* säkerhetsgränser

Principen är enkel:

> **Teman ändrar hur LUMS ser ut, inte vad LUMS får göra.**

---

## 2. Designprinciper

Temasystemet följer flera principer.

### 2.1 Valfritt

Teman är en valfri frontend-funktion.

LUMS förblir fullt fungerande utan att något extra tema väljs.

LUMS standardutseende fungerar som standardpresentation.

---

### 2.2 Klientsidigt

Temavalet hör hemma i frontend.

Att byta tema får inte kräva ändringar av applikationens tillstånd på serversidan.

Användarens valda tema är därför en presentationspreferens och inte en kontobehörighet eller backend-konfiguration.

---

### 2.3 Oberoende av backend

Alla teman använder samma LUMS-backend.

Följande är oberoende av det valda temat:

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

Backend förblir den auktoritativa källan för alla beslut som rör säkerhet och drift.

---

### 2.4 Ingen säkerhet genom tema

Ett tema får aldrig användas som säkerhetsmekanism.

Att till exempel dölja en åtgärd i gränssnittet ger eller tar inte bort behörighet.

Om en användare inte har behörighet till en åtgärd måste servern avvisa den oavsett vilket tema som är aktivt.

Det säkerställer att frontendens presentation inte blir en auktoriseringsgräns.

---

### 2.5 Kontrollerad reservlösning

Temasystemet ska alltid ha ett giltigt reservtema.

Om:

* inget tema har valts,
* ett sparat tema inte längre är tillgängligt,
* en temaidentifierare är ogiltig,
* en temaresurs inte kan läsas in,

ska LUMS växla till standardpresentationen i stället för att lämna gränssnittet oanvändbart.

---

## 3. Konceptuell arkitektur

Temasystemet kan betraktas som ett separat presentationslager runt den befintliga LUMS-applikationen.

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

Den viktiga gränsen går mellan **presentation** och **applikationslogik**.

Teman hör hemma ovanför den gränsen.

---

## 4. Temats livscykel

Konceptuellt följer temavalet denna ordning:

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

Själva valet skapar inte en ny LUMS-miljö.

Det finns fortfarande en enda LUMS-applikation, en enda backend och en enda säkerhetsmodell.

---

## 5. Temaidentifierare

Teman bör använda stabila interna identifierare i stället för att förlita sig på visningsnamnen.

Till exempel:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

Identifieraren är en implementeringsdetalj.

Temats synliga namn kan ändras separat utan att backend eller applikationsarkitekturen behöver ändras.

När en temaidentifierare tas bort eller byter namn bör temasystemet ha en reservlösning för användare som fortfarande har den tidigare identifieraren lagrad lokalt.

---

## 6. Ansvarsfördelning

Temasystemets ansvar är avsiktligt begränsat.

### Temalagret

Ansvarar för:

* visuell presentation
* temaval
* tematspecifik formgivning
* valfria visuella effekter
* tematspecifika frontend-dekorationer
* presentationsbeteende kopplat till tillgänglighet

### Gemensam frontend

Ansvarar för:

* att visa applikationsdata
* att anropa LUMS API:er
* att rendera jobb och programvaruinformation
* att hantera användarinteraktion
* att kontrollera synlighet på presentationsnivå

### Backend

Ansvarar för:

* autentisering
* auktorisering
* RBAC
* CSRF-skydd
* klientautentisering
* skapande av jobb
* jobbkörning
* pakethantering
* databasåtgärder
* granskningsloggning
* säkerhetsbeslut

Den här ansvarsfördelningen är grundläggande för designen.

---

## 7. Säkerhetsgräns

Temasystemet är **inte betrodd kod för auktoriseringsändamål**.

Även om ett tema ändrar eller döljer ett gränssnittselement är backend fortfarande ansvarig för att validera den begärda åtgärden.

Konceptuellt:

```text
Frontend visibility
        ≠
Backend permission
```

Till exempel:

```text
Viewer
  │
  ├── Theme may display no package-management controls
  │
  └── Backend still rejects unauthorized package operations
```

Samma princip gäller administrativa funktioner, uppdateringsjobb, klienthantering och alla andra privilegierade åtgärder.

---

## 8. Operativ princip

Temasystemet ska vara osynligt för LUMS operativa arkitektur.

Ett temabyte får inte kräva:

* att databasen byggs om
* att klientkonfiguration ändras
* att klienttoken ändras
* att uppdateringsagenter startas om
* att uppdateringsjobb ändras
* att RBAC ändras
* att nätverkskonfiguration ändras
* att pakethanteringens beteende ändras

Temat är en presentationspreferens, inte en driftkonfiguration.

---

## 9. Dokumentationens omfattning

Det här dokumentet beskriver LUMS valfria temasystem.

Allmänna LUMS-ämnen dokumenteras separat:

* Installation och driftsättning → `install.md`
* Administration och underhåll → `administration.md`
* Felsökning → `troubleshooting.md`
* Säkerhetsarkitektur och granskningar → `security.md`
* Allmän projektöversikt → `README.md`

När ansvarsområdena hålls åtskilda blir temadokumentationen inte en andra installations- eller administrationshandbok.

---

## 10. Grundprincip

Det valfria temasystemet kan sammanfattas så här:

> **Ett LUMS. En backend. En säkerhetsmodell. Många möjliga**

# LUMS — Valfritt temasystem

## Del 2 — Temats struktur och val

## 11. Temats struktur

Det valfria temasystemet skiljer temavalet från den faktiska visuella presentationen.

Ett tema består konceptuellt av tre lager:

```text
Theme Identifier
       │
       ▼
Theme Selection
       │
       ▼
Theme Presentation
```

Identifieraren anger vilket tema som har valts.

Valmekanismen avgör vilket tema som ska vara aktivt för tillfället.

Presentationslagret tillämpar motsvarande visuella konfiguration på LUMS-gränssnittet.

Den här uppdelningen gör det möjligt att lägga till eller ta bort teman utan att ändra LUMS-applikationens grundläggande arkitektur.

---

## 12. Temaval

Temavalet hanteras av frontend.

Det valda temat behandlas som en lokal presentationspreferens i stället för en kontouppgift på servern.

Konceptuellt:

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

Backend behöver inte känna till vilket visuellt tema som för närvarande är valt.

Det innebär också att ett temabyte inte påverkar andra användare.

Två användare kan använda samma LUMS-instans med helt olika visuella teman.

---

## 13. Lokal temapreferens

Webbläsaren kan spara det valda temat lokalt.

Syftet med lokal lagring är bekvämlighet:

```text
Browser
   │
   ├── Theme preference
   │
   └── LUMS application
```

En sparad temapreferens ska därför betraktas som opålitligt tillstånd på klientsidan.

Servern får aldrig tolka den som:

* en roll
* en behörighet
* ett autentiseringstillstånd
* en säkerhetsinställning
* en administrativ preferens

Webbläsaren kan välja utseende, men styr inte auktoriseringen.

---

## 14. Temainitiering

När LUMS-gränssnittet läses in avgör frontend vilket tema som ska vara aktivt.

Den konceptuella ordningen är:

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

Om ingen preferens finns sparad ska LUMS standardpresentation användas.

Om en sparad identifierare inte längre stöds ska samma reservbeteende användas.

Det hindrar en inaktuell lokal preferens från att förstöra gränssnittet.

---

## 15. Standardtema

LUMS standardtema är grundpresentationen.

Det ger referensutseendet som de valfria temana definieras i förhållande till.

Standardtemat bör därför vara:

* funktionellt
* lättläst
* tillgängligt
* visuellt komplett
* oberoende av valfria dekorativa resurser

Valfria teman får inte bli en förutsättning för normal LUMS-drift.

---

## 16. Tillämpning av tema

Frontend kan representera det aktiva temat med ett gemensamt applikationstillstånd eller ett tema-attribut på rotnivån.

Konceptuellt:

```html
<html data-theme="theme-id">
```

Den exakta implementationen kan ändras när frontend utvecklas.

Det viktiga arkitekturkravet är att det aktiva temat kan identifieras konsekvent av frontendens formgivningssystem.

Det gör att tematspecifika stilar kan hållas åtskilda från applikationens gemensamma struktur.

---

## 17. Tematspecifika stilar

Temastilar bör främst implementeras med CSS i stället för genom att duplicera applikationens markering.

Konceptuellt:

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

På så sätt förblir samma applikationskomponenter tillgängliga i alla teman.

En klienttabell är till exempel fortfarande en klienttabell oavsett vilket tema som är aktivt.

Bara presentationen ändras.

---

## 18. Gemensamma applikationskomponenter

Teman bör inte skapa separata versioner av LUMS-sidor.

Följande princip bör upprätthållas:

```text
One component
       │
       ├── Theme A
       ├── Theme B
       ├── Theme C
       └── Theme D
```

I stället för:

```text
Theme A → separate page
Theme B → separate page
Theme C → separate page
```

Duplicerade sidor skulle göra underhållet betydligt svårare och kunna orsaka beteendeskillnader mellan teman.

Ett tema bör därför dekorera det gemensamma gränssnittet i stället för att ersätta själva applikationen.

---

## 19. Temaresurser

Teman kan använda ytterligare frontend-resurser när det är lämpligt.

Möjliga resurser är:

* bakgrundsbilder
* dekorativ grafik
* ikoner
* animationer
* visuella överlägg
* temaspecifika illustrationer

Resurserna tillhör frontendens presentationslager.

De får inte innehålla:

* inloggningsuppgifter
* klienttoken
* hemliga nycklar
* databasfiler
* autentiseringsmaterial
* privata driftuppgifter

Temaresurser ska betraktas som offentliga frontend-resurser.

---

## 20. Valfria visuella effekter

Vissa teman kan innehålla extra visuella effekter.

Exempel:

* animerade bakgrunder
* dekorativa nätverkseffekter
* stämningsskapande rörelser
* temaanpassade gränssnittselement
* dynamiska visuella dekorationer

Sådana effekter måste vara valfria.

De får aldrig krävas för att LUMS ska fungera.

---

## 21. Reducerad rörelse

Visuella effekter bör ta hänsyn till användare som föredrar reducerad rörelse.

När animerade eller kontinuerligt föränderliga element används bör temasystemet erbjuda ett lämpligt beteende för reducerad rörelse.

Konceptuellt:

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

Tillgänglighet går före dekorativa animationer.

Ett tema ska förbli användbart även när visuella effekter är inaktiverade.

---

## 22. Temats oberoende

Ett temabyte får inte utlösa driftmässiga sidoeffekter.

Till exempel:

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

Temasystemet är alltså avsiktligt isolerat från LUMS operativa livscykel.

---

## 23. Hantering av temafel

Ett tema ska fallera säkert.

Om en temaspecifik resurs eller presentationskomponent inte kan läsas in ska LUMS gemensamma gränssnitt förbli användbart.

Rekommenderad återställningsväg:

```text
Theme error
    │
    ▼
Fallback to standard presentation
    │
    ▼
LUMS remains usable
```

Ett visuellt problem får inte bli ett problem med applikationens tillgänglighet.

---

## 24. Lägga till ett nytt tema

Ett nytt tema bör följa den befintliga uppdelningen mellan applikationsbeteende och presentation.

Konceptuellt:

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

Ett nytt tema är färdigt först när LUMS befintliga funktionalitet förblir oförändrad.

---

## 25. Ta bort ett tema

Även borttagning av teman ska hanteras på ett smidigt sätt.

Om en användare har ett borttaget tema sparat lokalt bör frontend upptäcka att identifieraren inte längre finns och återgå till standardtemat.

Att ta bort ett visuellt tema får alltså inte göra användarens LUMS-gränssnitt oanvändbart.

---

## 26. Namngivning av teman

Temanamn bör tydligt skilja mellan:

* intern identifierare
* visningsnamn
* visuellt koncept

Till exempel:

```text
Internal identifier:  standard
Display name:         Standard LUMS
```

Den här uppdelningen gör att den synliga texten kan utvecklas utan att den interna implementationen behöver ändras i onödan.

---

## 27. Aktuella temakoncept

Det valfria LUMS-temasystemet är utformat kring flera visuella identiteter och en gemensam applikation.

De aktuella dokumenterade temakoncepten omfattar:

| Identifierare | Koncept |
| --- | --- |
| `standard` | Standard LUMS |
| `LUMSStadium` | LUMS Stadium |
| `golf` | Golf Club |
| `nerd` | Nerd Mode |
| `geek` | Geek Lab |
| `admin` | Enterprise Admin |

Temana representerar olika visuella riktningar, inte olika LUMS-utgåvor.

Alla hör till samma applikation.

---

## 28. En backend, många gränssnitt

Relationen kan sammanfattas så här:

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

Temalagret slutar vid presentationsgränsen.

Allt under den gränsen är gemensamt för alla teman.

# LUMS — Valfritt temasystem

## Del 3 — Temakoncept

## 29. Standard LUMS

Temat Standard LUMS är applikationens referenspresentation.

Syftet är att erbjuda ett tydligt och funktionellt gränssnitt utan krav på ett särskilt visuellt koncept.

Standardtemat bör prioritera:

* läsbarhet
* tydlig informationshierarki
* förutsägbar navigering
* tillgänglighet
* få visuella störningsmoment
* konsekvent presentation av komponenter

Det är temasystemets reservpresentation.

Standardtemat bör därför förbli användbart även om inga valfria visuella teman är tillgängliga.

---

## 30. LUMS Stadium

**LUMS Stadium** är en mer uttrycksfull visuell tolkning av LUMS-gränssnittet.

Konceptet kombinerar systemadministration med en stadioninspirerad visuell identitet.

Möjliga designelement omfattar:

* informationspaneler inspirerade av resultattavlor
* tydligare visuella statusindikatorer
* evenemangsinriktad presentation
* temaanpassade bakgrunder
* visuell betoning av driftstatusar
* dekorativa stadioninslag

Temat är funktionellt identiskt med Standard LUMS.

En lyckad uppdatering är fortfarande en lyckad uppdatering.

Ett misslyckat jobb är fortfarande ett misslyckat jobb.

Bara presentationen förändras.

---

## 31. Golf Club

Temat **Golf Club** har en avsiktligt kontrasterande visuell identitet.

I stället för en traditionell server- eller infrastrukturkänsla använder gränssnittet ett lugnare fritidskoncept.

Den visuella riktningen kan betona:

* rena ytor
* återhållsam dekoration
* golfinspirerade inslag
* visuella metaforer från golfbanor
* lugn statuspresentation
* diskreta tematiska accenter

Konceptet visar att LUMS inte behöver likna en traditionell administrationskonsol för att vara funktionellt.

Backend och applikationsbeteende förblir oförändrade.

---

## 32. Nerd Mode

**Nerd Mode** riktar sig till en mer teknisk och lekfull presentation.

Konceptet kan betona LUMS tekniska karaktär med exempelvis:

* terminalinspirerad formgivning
* teknisk terminologi
* systemorienterade visuella element
* utvecklarinspirerad presentation
* diagnostisk estetik
* medvetet tekniska dekorationer

Temat måste fortfarande ha en tydlig informationshierarki.

Ett lekfullt gränssnitt får inte göra driftinformation svårare att förstå.

---

## 33. Geek Lab

**Geek Lab** representerar en mer experimentell teknisk miljö.

Det visuella konceptet kan kombinera:

* laboratorieestetik
* tekniskt experimenterande
* infrastrukturvisualisering
* systemdiagram
* vetenskaps- eller ingenjörsinspirerade inslag
* experimentella visuella effekter

Temat ska få gränssnittet att kännas som ett infrastrukturlaboratorium och samtidigt bevara samma LUMS-funktionalitet under ytan.

Det visuella experimenterandet måste hållas åtskilt från applikationens drift.

---

## 34. Enterprise Admin

Temat **Enterprise Admin** representerar ett mer återhållsamt administrationsgränssnitt.

Den visuella riktningen kan betona:

* strukturerad information
* kompakta layouter
* administrativa instrumentpaneler
* tydliga statusindikatorer
* hög informationstäthet
* färre dekorativa inslag

Temat passar särskilt användare som föredrar ett traditionellt administrationskonsolutseende.

Det ger inga ytterligare administratörsbehörigheter.

Namnet beskriver det visuella konceptet, inte en auktoriseringsnivå.

---

## 35. Jämförelse mellan teman

Temana kan ses som olika visuella tolkningar av samma applikation:

| Tema | Visuell riktning | Huvudkaraktär |
| --- | --- | --- |
| Standard LUMS | Rent / funktionellt | Referensgränssnitt |
| LUMS Stadium | Stadion / evenemang | Uttrycksfullt |
| Golf Club | Fritid / lugn | Avslappnat |
| Nerd Mode | Tekniskt / lekfullt | Utvecklarorienterat |
| Geek Lab | Experimentellt / tekniskt | Laboratorium |
| Enterprise Admin | Strukturerat / administrativt | Återhållsamt |

Tabellen beskriver endast presentationskoncept.

Den beskriver **inte** skillnader i:

* behörigheter
* funktioner
* API-åtkomst
* klientåtkomst
* jobbkörning
* pakethantering
* säkerhet

---

## 36. Samma gränssnitt, olika presentation

Ett centralt designmål är att samma applikationskomponent ska förbli igenkännbar i alla teman.

Till exempel:

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

Den underliggande klientinformationen förblir densamma.

Bara presentationen förändras.

Samma sak gäller:

* programvaruinventeringar
* tillgängliga uppdateringar
* uppdateringsjobb
* jobbhistorik
* användarinformation
* systemstatus
* gränssnitt för pakethantering

---

## 37. Driftstatusar

Teman kan framhäva olika driftstatusar visuellt.

Till exempel:

```text id="5wyy17"
PENDING
RUNNING
SUCCESS
FAILED
```

Ett tema kan representera dessa statusar visuellt på olika sätt, men den semantiska betydelsen måste vara konsekvent.

Temat får inte omdefiniera applikationens statusar.

Till exempel:

```text id="j4i9qd"
SUCCESS ≠ "looks green"

SUCCESS = actual LUMS job state
```

Den visuella representationen återger bara backendens status.

---

## 38. Felpresentation

Teman kan också ändra hur fel presenteras visuellt.

Felinformationen måste dock förbli begriplig.

Ett tema får inte:

* dölja viktig felinformation
* ersätta teknisk information med dekorativ text
* göra varningar omöjliga att skilja från normala tillstånd
* undertrycka driftfel

Visuell formgivning kan förbättra presentationen, men får inte ta bort den diagnostiska information som behövs för att förstå ett problem.

---

## 39. Konsekventa statusar

Samma status ska ha en konsekvent semantisk betydelse i varje tema.

Till exempel:

| Tillstånd | Betydelse |
| --- | --- |
| Pending | Väntar på körning |
| Running | Bearbetas för närvarande |
| Success | Slutfördes utan fel |
| Failed | Körningen misslyckades |

Ett tema kan representera dessa tillstånd med olika färger, ikoner, typografi eller layout.

Den underliggande betydelsen måste förbli oförändrad.

---

## 40. Temaspecifik dekoration

Dekorativa element bör vara underordnade driftinformationen.

Exempel:

* bakgrunder
* mönster
* illustrationer
* stämningseffekter
* temaanpassade ikoner
* visuella utsmyckningar

Följande prioritering ska upprätthållas:

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

Dekoration får aldrig prioriteras över information som krävs för att använda LUMS.

---

## 41. Visuell informationstäthet

Olika teman kan använda olika visuell informationstäthet.

Till exempel:

* Enterprise Admin kan prioritera informationstäthet.
* Standard LUMS kan prioritera balanserad läsbarhet.
* Golf Club kan använda mer tomrum.
* Nerd Mode kan använda kompakta tekniska element.
* Stadium kan betona stora statusytor.
* Geek Lab kan erbjuda mer visuell kontext.

Skillnaderna är val av presentation.

De ändrar inte mängden eller auktoriteten hos den underliggande informationen.

---

## 42. Tillgänglighet i alla teman

Varje tema måste behålla grundläggande användbarhet.

Det omfattar:

* läsbar text
* tillräcklig visuell åtskillnad
* användbara kontroller
* begripliga statusindikatorer
* tangentbordstillgänglighet
* användbara fokustillstånd
* stöd för preferenser om reducerad rörelse

Färg får inte vara det enda sättet att kommunicera ett viktigt tillstånd.

Ett misslyckat jobb ska till exempel inte bara gå att identifiera genom en viss färg.

---

## 43. Temaspecifika animationer

Teman kan innehålla animationer när de förstärker det visuella konceptet.

Exempel:

* subtila övergångar
* animerade bakgrunder
* nätverkseffekter
* statusövergångar
* stämningsskapande dekoration

Animationer ska vara underordnade applikationen.

De får inte:

* hindra interaktion
* skymma kontroller
* ständigt distrahera från driftinformation
* störa tillgängligheten
* påverka backend-operationer

---

## 44. Det levande nätverket

Vissa LUMS-teman kan använda ett dynamiskt, nätverksinspirerat visuellt lager.

Konceptet representerar LUMS som en levande infrastrukturell miljö:

```text id="7w1v8b"
Client ─────┐
            │
Client ─────┼──── LUMS
            │
Client ─────┘
```

En sådan visualisering är dekorativ om den inte uttryckligen kopplas till faktiska applikationsdata.

En visuell nätverksbild får därför aldrig tolkas som auktoritativ nätverkstopologi om inte applikationen uttryckligen tillhandahåller den informationen.

Den här skillnaden är viktig:

> **En visuell representation är inte automatiskt drifttelemetri.**

---

## 45. Dekorativa data jämfört med verkliga data

Temaspecifika visuella effekter måste tydligt hållas åtskilda från verkliga LUMS-data.

Till exempel:

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

Det hindrar användare från att förväxla en estetisk visualisering med faktisk systeminformation.

---

## 46. Temaidentitet

Varje tema bör ha en igenkännbar identitet utan att bli en separat produkt.

Målet är:

```text id="qv1fbe"
Different visual identity
          +
Same LUMS functionality
          =
Optional LUMS Theme
```

Det håller temasystemet lekfullt och flexibelt samtidigt som applikationens tekniska integritet bevaras.

---

## 47. Designregel för teman

Den viktigaste designregeln för alla teman är:

> **Ett tema får vara uttrycksfullt, ovanligt, tekniskt, lekfullt eller återhållsamt — men det måste alltid förbli LUMS.**

Applikationen ska förbli igenkännbar som samma system oavsett vilken visuell presentation som har valts.

# LUMS — Valfritt temasystem

## Del 4 — Frontend-implementation och tillgänglighet

## 48. Frontendens temalager

Det valfria temasystemet tillhör helt LUMS frontend.

Dess ansvar är begränsat till presentation och hantering av användarpreferenser.

Konceptuellt:

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

Temalagret ersätter inte frontendens gemensamma logik.

Det tillför i stället ett presentationslager runt den.

---

## 49. Temainitiering

Temainitieringen bör ske som en del av frontendens normala startprocess.

Den konceptuella ordningen är:

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

Initieringen bör vara lättviktig och får inte vara beroende av att backend är tillgänglig.

Användaren bör kunna läsa in den visuella presentationen även om ett senare API-anrop misslyckas.

---

## 50. Tematillstånd

Det aktiva temat är frontend-tillstånd.

Det bör därför behandlas annorlunda än applikationstillstånd.

### Tematillstånd

Exempel:

```text
Active visual theme
Reduced-motion preference
Visual presentation preferences
```

### Applikationstillstånd

Exempel:

```text
Logged-in user
User role
Client state
Package state
Update state
Job state
Audit state
```

Tematillstånd får aldrig skriva över eller utge sig för att vara applikationstillstånd.

---

## 51. Tema-attribut på rotnivån

Ett attribut på rotnivån är en lämplig konceptuell representation av det aktiva temat.

Till exempel:

```html
<html data-theme="standard">
```

eller:

```html
<html data-theme="nerd">
```

CSS kan sedan använda det aktiva temat som väljare.

Den exakta implementationen kan utvecklas, men arkitekturmålet är detsamma:

> **En applikationsstruktur, flera presentationsdefinitioner.**

---

## 52. Organisering av CSS

Temaspecifika stilar bör gå att skilja från LUMS gemensamma stilar.

Konceptuellt:

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

Gemensamma stilar bör definiera den funktionella strukturen.

Temastilar bör definiera den visuella identiteten.

Det minskar duplicering och gör framtida underhåll av teman enklare.

---

## 53. CSS-variabler

Temasystem kan använda CSS-egenskaper för att skilja semantiska värden från deras visuella representation.

Till exempel:

```css
:root {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Ett tema kan sedan tillhandahålla egna värden:

```css
[data-theme="example"] {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Den viktiga principen är att komponenter använder semantiska variabler i stället för hårdkodade temaspecifika värden när det är praktiskt möjligt.

---

## 54. Gemensamma komponenter

Temasystemet bör formge gemensamma komponenter i stället för att duplicera dem.

Vanliga komponenter är:

* navigering
* knappar
* formulär
* tabeller
* statusindikatorer
* kort
* dialogrutor
* element för pakethantering
* element för uppdateringsjobb
* klientinformation
* systeminformation

Samma komponent ska förbli funktionellt identisk oavsett vilket tema som är aktivt.

---

## 55. Temaresurser

Valfria teman kan använda särskilda resurser.

Möjliga resurskategorier:

```text
Images
Icons
Backgrounds
Decorative graphics
Fonts
Animation assets
Visual effects
```

Temaresurser ska förbli frontend-resurser.

De får inte innehålla känslig applikationsinformation.

Temaresurser får i synnerhet aldrig innehålla:

* lösenord
* hemliga nycklar
* klienttoken
* databasens innehåll
* privata certifikat
* autentiseringsmaterial

---

## 56. Inläsning av resurser

Temaresurser bör bara läsas in när de behövs.

Ett tema bör inte i onödan öka belastningen för varje LUMS-sida bara för att temat finns.

När det är praktiskt möjligt:

```text
Selected theme
      │
      ▼
Required assets
      │
      ▼
Browser
```

i stället för:

```text
All themes
      │
      ▼
All assets loaded simultaneously
```

Det blir allt viktigare när fler teman och visuella effekter läggs till.

---

## 57. Temats prestanda

Visuell anpassning får inte försämra LUMS användbarhet i någon större utsträckning.

Var särskilt uppmärksam på:

* stora bakgrundsbilder
* element som animeras kontinuerligt
* canvas-effekter
* upprepade DOM-uppdateringar
* resurskrävande visuella filter
* onödiga nätverksanrop

Driftsidor som klientlistor, programvaruinventeringar och vyer för uppdateringsjobb ska förbli responsiva.

---

## 58. Dekorativ JavaScript

Ett tema kan använda JavaScript för visuella effekter.

Exempel:

* animerade bakgrunder
* nätverksvisualiseringar
* dynamiska dekorationer
* temaspecifika interaktioner

Sådan JavaScript ska hållas åtskild från applikationens driftlogik.

Ett dekorativt skript får aldrig ansvara för:

* auktorisering
* skapande av jobb
* paketinstallation
* paketborttagning
* uppdateringskörning
* klientautentisering
* granskningsloggning

Skillnaden ska förbli tydlig:

```text
Theme JavaScript
      ≠
LUMS operational JavaScript
```

---

## 59. Nätverksvisualisering

Om ett tema använder en nätverksliknande visualisering ska den betraktas som en presentationskomponent.

Till exempel:

```text
Canvas / Visual Layer
        │
        ▼
Decorative Network
        │
        ▼
Theme Presentation
```

Om visualiseringen inte uttryckligen är kopplad till auktoritativa LUMS-data ska den inte ge intrycket av att representera det faktiska nätverkstillståndet.

Det hindrar dekorativ grafik från att misstas för övervakning eller telemetri.

---

## 60. Reducerad rörelse

Teman som använder animation bör stödja preferenser för reducerad rörelse.

Det önskade beteendet är konceptuellt:

```text
prefers-reduced-motion: reduce
            │
            ▼
Reduce or disable decorative motion
```

Väsentlig funktionalitet måste förbli oförändrad.

Reducerad rörelse ska bara påverka presentationen.

---

## 61. Fokus och tangentbordsnavigering

Temastilar måste bevara användbarhet med tangentbord.

Viktiga interaktiva element ska ha tydliga fokustillstånd.

Teman får inte ta bort fokusmarkeringar utan att ge ett lika tydligt alternativ.

Till exempel:

```text
Keyboard focus
      │
      ▼
Clearly visible control state
```

Detta gäller:

* navigering
* knappar
* länkar
* formulärfält
* väljare
* dialogrutor
* kontroller för pakethantering

---

## 62. Oberoende av färg

Viktig information får inte enbart förmedlas med färg.

Till exempel:

```text
FAILED
```

ska fortfarande kunna förstås genom text, ikoner, struktur eller någon annan tillgänglig indikation även om temats färger inte är tillgängliga.

Detta är särskilt viktigt eftersom teman kan ha mycket olika färgpaletter.

---

## 63. Kontrast

Varje tema bör ha tillräcklig kontrast mellan:

* text och bakgrunder
* kontroller och bakgrunder
* statusindikatorer och omgivande element
* fokuserade element och deras omgivning

En visuellt intressant palett ersätter inte läsbar information.

När temafärger strider mot tillgänglighetskrav går läsbarhet före.

---

## 64. Gränssnitt för temaval

Temaväljaren är en del av LUMS gemensamma gränssnitt.

Den ska förbli begriplig oavsett vilket tema som är aktivt.

Konceptuellt:

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

När ett annat tema väljs ska presentationen uppdateras utan att den aktuella LUMS-sessionen eller drifttillståndet förändras.

---

## 65. Oberoende av sessionen

Att byta tema får inte logga ut användaren.

Det får inte:

* ogiltigförklara sessionen
* ändra rollen
* rotera klienttoken
* ändra autentiseringstillståndet på servern

Temapreferensen är separat från autentiseringen.

```text
Theme change
     │
     └── Session remains unchanged
```

---

## 66. Oberoende av RBAC

Teman måste förbli oberoende av RBAC.

Till exempel:

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

Det valda temat ändrar inte dessa behörigheter.

En Viewer som använder Enterprise Admin blir inte administratör.

En Administrator som använder Nerd Mode förlorar inte sina administratörsbehörigheter.

Backend förblir auktoritativ i samtliga fall.

---

## 67. Isolering av fel

Ett fel i valfri visuell funktion får inte bryta LUMS kärnfunktioner.

Om en dekorativ animation misslyckas:

```text
Animation failure
      │
      ▼
Theme remains usable
      │
      ▼
LUMS remains operational
```

Där det är möjligt bör visuella funktioner fallera separat från applikationens funktionalitet.

Detta är särskilt viktigt för valfria effekter som animerade bakgrunder eller nätverksvisualiseringar.

---

## 68. Webbläsarkompatibilitet

Temasystemet bör använda webbläsarfunktioner som stöds av de webbläsare som används i LUMS driftsmiljöer.

Om en visuell funktion inte är tillgänglig ska gränssnittet försämras på ett kontrollerat sätt i stället för att bli oanvändbart.

Standardpresentationen ska förbli grundläggande reservlösning.

---

## 69. Implementationsprincip

Implementation kan sammanfattas så här:

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

Följande måste hållas utanför temalagret:

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

Denna uppdelning gör temasystemet tillräckligt uttrycksfullt utan att koppla det till LUMS kärnbeteende.

# LUMS — Valfritt temasystem

## Del 5 — Säkerhet, testning och utveckling

## 70. Säkerhetsgräns

Temasystemet är en del av frontend och körs därför i en klientmiljö som inte är betrodd.

Webbläsaren styr presentationslagret.

Webbläsaren styr **inte** LUMS auktorisering.

Säkerhetsgränsen är fortfarande:

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

Alla säkerhetskänsliga beslut måste därför förbli på serversidan.

---

## 71. Temaval är inte auktorisering

Ett valt tema får aldrig tolkas som en auktoriseringssignal.

Till exempel:

```text id="8u3r8v"
data-theme="admin"
```

betyder inte att den aktuella användaren är administratör.

Ordet `admin` i en temaidentifierare är enbart beskrivande.

Användarens faktiska roll måste alltid komma från den autentiserade applikationssessionen och serverns auktoriseringslogik.

---

## 72. Synlighet i frontend är inte säkerhet

Ett tema eller frontend-skript kan dölja ett gränssnittselement.

Det är användbart för presentationen.

Det räcker inte som åtkomstkontroll.

Till exempel:

```text id="7m8c6w"
Hidden button
      ≠
Unauthorized operation prevented
```

Den motsvarande API-slutpunkten måste självständigt validera användarens behörigheter.

Detta gäller alla privilegierade LUMS-funktioner.

---

## 73. Temaresurser är offentliga

Frontend-resurser bör betraktas som offentligt tillgängliga för alla som kan nå LUMS webbgränssnitt.

Temafiler får därför aldrig innehålla hemligheter.

Placera aldrig följande i temaresurser:

```text id="1zjz7n"
Passwords
API secrets
Client tokens
Private keys
Database files
Session secrets
Authentication credentials
```

Om information måste förbli konfidentiell hör den inte hemma i en temaresurs.

---

## 74. Inga backend-hemligheter i teman

Tema-JavaScript får inte innehålla serveruppgifter eller privilegierat API-material.

Ett tema ska vid behov kommunicera via det befintliga frontend-applikationslagret.

Det får inte införa en alternativ autentiseringsmekanism.

Följande princip gäller:

> **Teman använder presentationsdata; de skapar inte säkerhetsuppgifter.**

---

## 75. Förfalskning av förfrågningar mellan webbplatser

Temafunktionalitet får inte kringgå befintligt CSRF-skydd.

Om ett tema har ett gränssnittselement som utlöser en åtgärd som kräver en skyddad begäran måste begäran följa samma säkerhetskrav som LUMS gemensamma gränssnitt.

Visuell kod får inget undantag.

---

## 76. API-användning

Ett tema bör undvika att direkt implementera egen operativ API-logik.

När applikationsdata behövs bör temat använda de etablerade LUMS-mekanismerna i frontend/applikationen.

Det förhindrar flera oberoende implementationer av:

* autentisering
* API-begäranden
* felhantering
* antaganden om auktorisering
* jobbhantering

Den gemensamma applikationslogiken förblir det auktoritativa integrationslagret i frontend.

---

## 77. Temaisolering

Ett tema ska gå att ta bort utan att LUMS kärnfunktionalitet tas bort.

Konceptuellt:

```text id="3m1o8q"
Remove optional theme
        │
        ▼
Standard LUMS remains
        │
        ▼
Application remains operational
```

Det gör valfria teman genuint valfria.

---

## 78. Säkerhetstestning

Säkerhetstester bör bevisa att temaförändringar inte ändrar LUMS säkerhetsmodell.

Relevanta kontroller omfattar:

* Viewer förblir Viewer
* Operator förblir Operator
* Administrator förblir Administrator
* skyddade API-slutpunkter förblir skyddade
* CSRF-skyddet förblir aktivt
* klientautentiseringen är oförändrad
* behörigheter för uppdateringsjobb är oförändrade
* behörigheter för pakethantering är oförändrade
* granskningsloggningen är oförändrad

Temat får aldrig användas som bevis för att en åtgärd är säker.

---

## 79. Funktionell tematestning

Varje tema bör testas mot den gemensamma applikationen.

Minst:

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

Exakt vilka funktioner som är tillgängliga beror på den autentiserade användarens roll.

Testets syfte är att säkerställa att temarendering inte bryter applikationens normala funktioner.

---

## 80. RBAC-testning av teman

Tematestning bör omfatta alla relevanta roller.

En grundläggande matris:

| Roll | Tematestning |
| --- | --- |
| Administrator | Krävs |
| Operator | Krävs |
| Viewer | Krävs |

För varje roll ska du verifiera att temabyte inte ändrar vilka funktioner som är tillåtna.

Till exempel:

```text id="3n5p2m"
Viewer + Nerd Mode
        =
Viewer permissions

Viewer + Enterprise Admin
        =
Viewer permissions
```

Det visuella temat får inte ändra resultatet.

---

## 81. Tester av temabyte

Temabyte bör testas upprepade gånger.

Exempelsekvens:

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

Applikationen ska förbli användbar under hela sekvensen.

Var särskilt uppmärksam på:

* layoutändringar
* tabeller
* navigering
* dialogrutor
* formulär
* statusindikatorer
* långa texter
* responsivt beteende

---

## 82. Persistenstestning

Om temapreferensen sparas lokalt ska du testa följande:

1. Välj ett tema.
2. Läs in sidan igen.
3. Bekräfta att temat fortfarande är valt.
4. Stäng webbläsaren.
5. Öppna LUMS igen.
6. Bekräfta att preferensen fortfarande hanteras korrekt.
7. Ta bort eller ogiltigförklara det sparade temat.
8. Bekräfta återgång till standardtemat.

Det sparade värdet får aldrig betraktas som applikationens säkerhetstillstånd.

---

## 83. Testning av ogiltigt tema

En ogiltig temaidentifierare får inte bryta gränssnittet.

Till exempel:

```text id="4j5cqn"
unknown-theme
```

ska leda till en säker reservlösning i stället för en oanvändbar sida.

Önskat beteende:

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

## 84. Testning av resursfel

Även fel i valfria resurser ska testas.

Exempel:

* bild saknas
* animation är inte tillgänglig
* ogiltig resurssökväg
* visuell funktion stöds inte
* JavaScript-fel i valfri dekoration

Den gemensamma applikationen bör förbli användbar när det är möjligt.

---

## 85. Testning av reducerad rörelse

För teman med animation ska både normal miljö och miljö med reducerad rörelse testas.

```text id="l1h4nb"
Normal motion
     │
     └── Theme effects available

Reduced motion
     │
     └── Effects reduced or disabled
```

Viktiga applikationskontroller måste fungera fullt ut i båda fallen.

---

## 86. Responsiv testning

Teman bör testas vid olika visningsstorlekar.

Minst:

* skrivbord
* surfplattestor visningsyta
* smal eller mobilstor visningsyta

Den visuella identiteten får inte ske på bekostnad av användbara kontroller eller läsbar applikationsinformation.

Var särskilt uppmärksam på:

* navigering
* tabeller
* åtgärdsknappar
* kontroller för pakethantering
* information om jobbstatus
* dialogrutor
* temaväljare

---

## 87. Prestandatestning

Visuella effekters inverkan på webbläsarens prestanda ska utvärderas.

Relevanta observationer omfattar:

* sidans inläsningstid
* renderingsrespons
* CPU-användning
* minnesanvändning
* animationernas jämnhet
* upprepade DOM-uppdateringar
* nätverksbegäranden

Teman ska förbättra presentationen utan att bli en prestandaflaskhals.

---

## 88. Utvecklingsarbetsflöde

Ett nytt tema bör utvecklas oberoende av backend-ändringar när det är möjligt.

Rekommenderat arbetsflöde:

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

Backend-ändringar ska bara införas när det finns ett verkligt applikationskrav.

Ett visuellt tema bör normalt inte kräva ändringar av backend.

---

## 89. Utvecklingsregler

När du utvecklar ett tema:

1. Återanvänd befintliga LUMS-komponenter.
2. Undvik att duplicera sidor.
3. Håll temaspecifika stilar isolerade.
4. Håll dekorativ JavaScript åtskild från driftlogiken.
5. Lägg inte till autentiseringslogik.
6. Lägg inte till auktoriseringslogik.
7. Exponera inga hemligheter.
8. Bevara tillgängligheten.
9. Bevara beteendet för reducerad rörelse.
10. Testa alla relevanta roller.
11. Testa standardreservlösningen.
12. Dokumentera nya resurser och beteenden.

---

## 90. Verifiering av ändringar

Innan en temaförändring betraktas som färdig ska både presentation och funktion verifieras.

En användbar valideringssekvens:

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

Ett tema är inte färdigt bara för att det ser rätt ut.

Det måste också lämna LUMS beteende oförändrat.

---

## 91. Regressionsprincip

Temautveckling bör följa samma allmänna projektprincip som andra LUMS-ändringar:

> **Ändra → testa → verifiera → dokumentera**

Även en visuell ändring kan orsaka funktionella regressioner.

Exempel:

* dolda knappar
* oläsbar text
* trasig layout
* otillgängliga kontroller
* JavaScript-konflikter
* saknade resurser
* felaktiga väljare
* fel i mobil layout

Testning är därför en del av temautvecklingen, inte ett valfritt sista steg.

---

## 92. Felsökning: temat läses inte in

Om det valda temat inte visas:

1. Läs in sidan igen.
2. Kontrollera om standardtemat läses in.
3. Kontrollera webbläsarkonsolen.
4. Kontrollera att den valda temaidentifieraren är giltig.
5. Kontrollera att nödvändiga temaresurser är tillgängliga.
6. Kontrollera om det finns JavaScript-fel.
7. Rensa den lokala temapreferensen vid behov.
8. Läs in sidan igen och verifiera standardreservlösningen.

Ändra inte backendens säkerhetskonfiguration för att lösa ett frontend-problem med ett tema.

---

## 93. Felsökning: temat förstör layouten

Om ett tema orsakar layoutproblem:

1. Byt till Standard LUMS.
2. Bekräfta att det gemensamma gränssnittet fungerar.
3. Identifiera den berörda komponenten.
4. Granska temaspecifik CSS.
5. Kontrollera responsivt beteende.
6. Kontrollera fel i webbläsarkonsolen.
7. Korrigera den temaspecifika formgivningen.
8. Testa övriga teman igen.

Standardtemat ger en viktig diagnostisk jämförelse.

---

## 94. Felsökning: temat orsakar JavaScript-fel

Om temaspecifik JavaScript orsakar fel:

1. Byt till standardtemat.
2. Bekräfta att LUMS fungerar normalt.
3. Identifiera det felande temascriptet.
4. Avgör om felet är dekorativt eller applikationsrelaterat.
5. Åtgärda det temaspecifika felet.
6. Verifiera att LUMS gemensamma JavaScript fortfarande fungerar.
7. Testa temabyte igen.

Ändra inte drift-JavaScript enbart för att kompensera för ett dekorativt temafel.

---

## 95. Felsökning: temapreferensen är ogiltig

Om ett gammalt eller ogiltigt tema fortfarande är sparat lokalt:

```text id="b9n8wq"
Invalid stored preference
        │
        ▼
Fallback to Standard
        │
        ▼
Select a valid theme
```

Den föredragna lösningen är en säker reservlösning, inte ett manuellt ingrepp i backend.

---

## 96. Temadokumentation

Varje nytt tema bör dokumentera:

* intern identifierare
* visningsnamn
* visuellt koncept
* nödvändiga resurser
* valfria visuella effekter
* tillgänglighetsaspekter
* beteende vid reducerad rörelse
* kända begränsningar

Implementationsspecifik dokumentation ska beskriva den faktiska aktuella koden i stället för antaganden om hur temat skulle kunna fungera.

---

## 97. Aktuell temauppsättning

De dokumenterade temakoncepten är för närvarande:

```text id="r0w4u5"
standard       → Standard LUMS
LUMSStadium    → LUMS Stadium
golf           → Golf Club
nerd           → Nerd Mode
geek           → Geek Lab
admin          → Enterprise Admin
```

Temauppsättningen kan utökas.

Fler teman kan läggas till utan att LUMS underliggande arkitektur ändras, förutsatt att uppdelningen mellan presentation och applikationsbeteende bevaras.

---

## 98. Utvecklingsprincip

Det valfria temasystemet bör förbli en kontrollerad frontend-utökning.

Syftet är att göra LUMS mer uttrycksfullt och anpassningsbart utan att göra applikationen mer komplicerad att drifta.

Den föredragna arkitekturen är därför:

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

Den gemensamma applikationen förblir grunden.

Teman förblir valfria utökningar.

# LUMS — Valfritt temasystem

## Del 6 — Underhåll, utökning och slutstatus

## 99. Underhåll av teman

Underhåll av teman bör hållas åtskilt från underhållet av LUMS kärna när det är möjligt.

En uppdatering av ett visuellt tema bör normalt bara omfatta frontend-resurser.

Vanliga ändringar:

* CSS-justeringar
* visuella resurser
* temaspecifik JavaScript
* tillgänglighetsförbättringar
* korrigeringar av responsiv layout
* justeringar av animationer
* ändringar av temanamn eller presentation

En temaändring bör inte kräva ändringar av:

* klientkonfiguration
* klienttoken
* databasschema
* uppdateringsjobb
* pakethanteringslogik
* autentisering
* RBAC
* säkerhetskontroller på serversidan

Om en temaändring oväntat kräver sådana ändringar bör beroendet granskas innan arbetet fortsätter.

---

## 100. Tema uppdateringar

Tema uppdateringar bör följa LUMS normala utvecklingsprocess:

```text id="2p7z9r"
Modify
   ↓
Test
   ↓
Verify
   ↓
Document
```

För större ändringar:

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

Ett tema ska inte betraktas som färdigt enbart för att det visuella resultatet ser rätt ut.

---

## 101. Lägga till ett nytt tema

Ett nytt tema kan införas utan att LUMS backend ändras.

Rekommenderad process:

### Steg 1 — Definiera konceptet

Beskriv:

* visuell identitet
* avsedd stil
* typografi
* färger
* dekorativa element
* valfria animationer

### Steg 2 — Definiera identifieraren

Välj en stabil intern identifierare.

### Steg 3 — Implementera presentationen

Lägg till nödvändiga stilar och resurser.

### Steg 4 — Integrera valet

Gör temat tillgängligt via den gemensamma temaväljaren.

### Steg 5 — Testa

Verifiera:

* normala sidor
* interaktiva kontroller
* responsiva layouter
* tillgänglighet
* reducerad rörelse
* alla relevanta RBAC-roller
* reservbeteende

### Steg 6 — Dokumentera

Dokumentera temat och relevanta implementeringsdetaljer.

---

## 102. Ta bort ett tema

Att ta bort ett tema ska behandlas som en kompatibilitetsändring för användare som fortfarande kan ha temat valt lokalt.

Frontend bör därför hantera en inaktuell identifierare på ett säkert sätt.

Föredraget beteende:

```text id="x4e7p1"
Old theme identifier
       │
       ▼
Theme no longer available
       │
       ▼
Standard LUMS
```

Att ta bort ett tema ska aldrig kräva en databasmigrering enbart för att ta bort en webbläsarpreferens.

---

## 103. Byta namn på ett tema

Ett visningsnamn kan vanligtvis ändras oberoende av den interna identifieraren.

Till exempel:

```text id="8q4n1k"
Internal identifier
        │
        └── remains stable

Display name
        │
        └── may change
```

Om själva den interna identifieraren ändras kan en migrering eller kompatibilitetsmappning behövas för befintliga lokala preferenser.

Det bästa är att hålla identifierarna stabila när det är praktiskt möjligt.

---

## 104. Temakompatibilitet

Teman bör förbli kompatibla med ändringar i LUMS gemensamma gränssnitt.

När en ny gemensam komponent införs bör befintliga teman kontrolleras för:

* saknad formgivning
* trasiga mellanrum
* oläsbar text
* felaktiga färger
* saknat responsivt beteende
* felaktiga fokustillstånd
* otillgängliga kontroller

En ny backend-funktion kräver inte automatiskt en ny temafunktion.

Den gemensamma applikationen förblir sanningskällan.

---

## 105. Nya LUMS-funktioner

När LUMS får en ny funktion bör stöd för teman normalt utvärderas först när den gemensamma funktionen fungerar.

Rekommenderad ordning:

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

Det hindrar visuell anpassning från att bli ett beroende i utvecklingen av kärnfunktioner.

---

## 106. Stabilitet för tema-API

Temasystemet bör undvika ett separat API-lager om det inte finns ett verkligt behov.

Teman bör helst använda samma applikationstillstånd och API-mekanismer i frontend som LUMS redan använder.

Det minskar:

* duplicerad begärandelogik
* duplicerad felhantering
* inkonsekventa antaganden om auktorisering
* ytterligare underhåll
* onödig attackyta

Temasystemet är därför avsiktligt lättviktigt.

---

## 107. Säkerhetsgranskning av teman

När ett tema läggs till eller ändras väsentligt ska följande granskas:

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

Granskningen ska göras även när ändringen verkar enbart visuell.

Frontend-kod är fortfarande körbar kod.

---

## 108. Tillgänglighetsgranskning av teman

För varje tema ska följande verifieras:

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

Tillgänglighet ska ses som en del av temakvaliteten, inte som en valfri förbättring.

---

## 109. Checklista för temaregressioner

Innan en temaändring godkänns:

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

Den exakta uppsättningen funktioner som visas under testet beror på användarens roll.

---

## 110. Operativt oberoende

Det valfria temasystemet är avsiktligt oberoende av LUMS operativa livscykel.

Ett temabyte får inte kräva:

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

Det gör att presentationslagret kan utvecklas oberoende av infrastrukturlagret.

---

## 111. Oberoende av driftsättning

Temaresurser är en del av LUMS applikationsfrontend.

Allmänna driftsättningsprocedurer dokumenteras i huvudguiderna för installation och administration.

Det här dokumentet upprepar avsiktligt inte:

* procedurer för Docker-driftsättning
* kommandon för härdning av containrar
* Nginx-konfiguration
* procedurer för databasbackup
* återställningsprocedurer för servern
* installationsprocedurer för klienter

Dessa ämnen hör hemma i lämplig driftsdokumentation.

Uppdelningen hindrar temadokumentationen från att bli inaktuell när driftsättningsarkitekturen ändras.

---

## 112. Åtskillnad mellan källa och körmiljö

Temasystemet ska förstås som en del av applikationens källkod.

Det finns en skillnad mellan:

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

En temaändring i källkoden innebär inte automatiskt att en redan körande driftsättning har fått ändringen.

LUMS normala bygg- och driftsättningsprocess ansvarar för att leverera uppdaterade frontend-resurser.

---

## 113. Versionshantering

Teman behöver inte införa en separat LUMS-backendversion.

Ett tema kan utvecklas som en del av frontend-/applikationsversionen.

Om en temaändring orsakar kompatibilitetsproblem ska dessa dokumenteras uttryckligen.

Till exempel:

```text id="5y1p8f"
Theme change
     │
     ├── visual-only
     │
     └── compatibility-affecting
```

Den andra kategorin kräver ytterligare regressionstestning.

---

## 114. Utgivningsberedskap

Innan en LUMS-utgåva med temaändringar verifieras:

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

Temaändringar får inte tillåtas dölja regressioner i kärnapplikationen.

---

## 115. Aktuell temauppsättning

De aktuella dokumenterade temakoncepten är:

| Identifierare | Visningsnamn | Koncept |
| --- | --- | --- |
| `standard` | Standard LUMS | Referensgränssnitt |
| `LUMSStadium` | LUMS Stadium | Stadion / evenemang |
| `golf` | Golf Club | Lugn / fritid |
| `nerd` | Nerd Mode | Tekniskt / lekfullt |
| `geek` | Geek Lab | Experimentellt / tekniskt |
| `admin` | Enterprise Admin | Strukturerat / administrativt |

Dessa teman delar samma LUMS-applikation och backend.

De är visuella varianter, inte separata produkter eller behörighetsnivåer.

---

## 116. Aktuell status

Det valfria temasystemet är en utökning av LUMS frontend-arkitektur.

Dess avsedda egenskaper är:

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

Implementationsspecifika detaljer ska alltid hållas synkroniserade med aktuell frontend-källkod.

---

## 117. Framtida utökningar

Temasystemet kan utökas på flera sätt utan att den underliggande arkitekturen ändras.

Möjliga framtida tillägg:

* fler teman
* förbättrade temaförhandsvisningar
* mer detaljerade visuella preferenser
* fler tillgänglighetsinställningar
* förbättrat responsivt beteende
* temaspecifika instrumentpanelslayouter
* ytterligare valfria visualiseringar

Sådana utökningar ska fortsätta respektera samma uppdelning mellan presentation och applikationsbeteende.

---

## 118. Slutlig arkitektur

Hela konceptet kan sammanfattas så här:

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

Det visuella lagret förblir valfritt.

Applikationslagret förblir auktoritativt.

Säkerhetslagret förblir oberoende.

---

## 119. Slutprincip

Det valfria temasystemet finns för att göra LUMS mer personligt, uttrycksfullt och anpassningsbart utan att kompromissa med den tekniska arkitekturen.

Grundregeln är densamma:

> **Ett LUMS · många gränssnitt · samma backend**

Ett tema får ändra LUMS atmosfär.

Det får aldrig ändra vad LUMS faktiskt får göra.
