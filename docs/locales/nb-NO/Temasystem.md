# LUMS – valgfritt temasystem

> **Én LUMS · mange grensesnitt · samme backend**

LUMS tilbyr et valgfritt, klientbasert temasystem som lar brukergrensesnittet endre sitt visuelle uttrykk uten å endre den underliggende funksjonaliteten i LUMS.

Temaer er bare et presentasjonslag. De erstatter, endrer eller omgår ikke LUMS-backenden, autentisering, autorisasjon, oppdateringskjøring, pakkeadministrasjon, klientadministrasjon, jobbhåndtering eller sikkerhetskontroller.

Temasystemet gjør LUMS tilpasningsdyktig til ulike visuelle preferanser, samtidig som selve applikasjonen forblir konsistent.

## Implementasjonsstatus og fasit

Den gjeldende nettleserimplementasjonen ligger i `server/static/theme.js`. Den støtter `standard`, `LUMSStadium`, `golf`, `nerd`, `geek` og `admin`; lagrer valget i nettleserens `localStorage` under `lums-theme`; og går tilbake til `standard` hvis den lagrede identifikatoren mangler eller er ugyldig. Temaet `nerd` starter matriseeffekten, og `geek` starter nettverkseffekten. Temavalget er en nettleserpreferanse, ikke en kontoinnstilling eller en autorisasjonstilstand på serveren.

Denne referansen inneholder også designkrav og konseptuelle eksempler. Formuleringer som «bør», «må» eller «framtidig» beskriver arkitekturveiledning, og beviser ikke at en bestemt visuell funksjon eller tilgjengelighetsatferd er implementert. Kontroller gjeldende atferd i kildekoden før du behandler et konsept som en levert funksjon.

---

## 1. Oversikt

Det valgfrie temasystemet lar LUMS-nettgrensesnittet tilby flere visuelle miljøer samtidig som det bruker den samme applikasjonsbackenden.

Et tema kan endre:

* farger
* typografi
* bakgrunner
* dekorative elementer
* visuell vektlegging
* navigasjonsutseende
* animasjoner
* valgfrie visuelle effekter
* presentasjon av enkeltsider

Et tema må ikke endre:

* brukertillatelser
* tilgjengelige API-endepunkter
* autentiseringsatferd
* autorisasjonsavgjørelser
* CSRF-beskyttelse
* klientautentisering
* oppdateringskjøring
* tillatelser for pakkeadministrasjon
* håndtering av jobbtilstand
* revisjonslogging
* databaseatferd
* sikkerhetsgrenser

Prinsippet er enkelt:

> **Temaer endrer hvordan LUMS ser ut, ikke hva LUMS har lov til å gjøre.**

---

## 2. Designprinsipper

Temasystemet følger flere prinsipper.

### 2.1 Valgfritt

Temaer er en valgfri frontend-funksjon.

LUMS skal fortsatt fungere fullt ut uten at et ekstra tema er valgt.

Standardutseendet til LUMS fungerer som standardpresentasjon.

---

### 2.2 Klientbasert

Temavalget hører hjemme i frontend.

Et temabytte skal ikke kreve endringer i applikasjonstilstanden på serversiden.

Et valgt tema er derfor en presentasjonspreferanse, ikke en kontotillatelse eller en backend-konfigurasjon.

---

### 2.3 Uavhengig av backend

Alle temaer bruker den samme LUMS-backenden.

Følgende områder forblir uavhengige av valgt tema:

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

Backenden forblir autoritativ for alle beslutninger som påvirker sikkerhet og drift.

---

### 2.4 Temaer gir ikke sikkerhet

Et tema må aldri brukes som en sikkerhetsmekanisme.

Hvis en handling skjules i grensesnittet, betyr ikke det at en tillatelse gis eller trekkes tilbake.

Hvis en bruker ikke har tillatelse til en operasjon, må serveren avvise den uansett hvilket tema som er aktivt.

Dette sikrer at frontend-presentasjonen ikke blir en autorisasjonsgrense.

---

### 2.5 Myk tilbakefallsatferd

Temasystemet bør alltid tilby et gyldig reservevalg.

Hvis:

* ingen temaer er valgt,
* et lagret tema ikke lenger er tilgjengelig,
* en temaidentifikator er ugyldig,
* en temafil ikke kan lastes,

bør LUMS gå tilbake til standardpresentasjonen i stedet for å gjøre grensesnittet ubrukelig.

---

## 3. Konseptuell arkitektur

Temasystemet kan betraktes som et eget presentasjonslag rundt den eksisterende LUMS-applikasjonen.

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

Den viktige grensen går mellom **presentasjon** og **applikasjonslogikk**.

Temaer hører hjemme over denne grensen.

---

## 4. Temats livssyklus

Konseptuelt følger valg av tema denne sekvensen:

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

Selve valget oppretter ikke et nytt LUMS-miljø.

Det finnes fortsatt bare én LUMS-applikasjon, én backend og én sikkerhetsmodell.

---

## 5. Temaidentifikatorer

Temaer bør bruke stabile interne identifikatorer i stedet for å være avhengige av visningsnavnene.

For eksempel:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

Identifikatoren er en implementasjonsdetalj.

Det synlige temanavnet kan endres uavhengig uten at backend eller applikasjonsarkitektur må endres.

Hvis en temaidentifikator fjernes eller endres, bør temasystemet tilby et reservevalg for brukere som fortsatt har den gamle identifikatoren lagret lokalt.

---

## 6. Ansvarsdeling

Temasystemet har med hensikt et snevert ansvarsområde.

### Temalag

Ansvarlig for:

* visuell presentasjon
* temavalg
* temaspesifikk utforming
* valgfrie visuelle effekter
* temaspesifikke dekorasjoner i frontend
* presentasjonsatferd knyttet til tilgjengelighet

### Felles frontend

Ansvarlig for:

* visning av applikasjonsdata
* kall til LUMS-API-er
* gjengivelse av jobber og programvareinformasjon
* håndtering av brukerinteraksjon
* synlighet i presentasjonslaget

### Backend

Ansvarlig for:

* autentisering
* autorisasjon
* RBAC
* CSRF-beskyttelse
* klientautentisering
* oppretting av jobber
* jobbkjøring
* pakkeadministrasjon
* databaseoperasjoner
* revisjonslogging
* sikkerhetsavgjørelser

Dette skillet er grunnleggende for utformingen.

---

## 7. Sikkerhetsgrense

Temasystemet er **ikke klarert kode for autorisasjonsformål**.

Selv om et tema endrer eller skjuler et grensesnittelement, er backenden fortsatt ansvarlig for å validere den forespurte operasjonen.

Konseptuelt:

```text
Frontend visibility
        ≠
Backend permission
```

For eksempel:

```text
Viewer
  │
  ├── Theme may display no package-management controls
  │
  └── Backend still rejects unauthorized package operations
```

Det samme prinsippet gjelder administratorfunksjoner, oppdateringsjobber, klientadministrasjon og alle andre privilegerte operasjoner.

---

## 8. Driftsprinsipp

Temasystemet bør være usynlig for LUMS-driftsarkitektur.

Et temabytte må ikke kreve:

* nybygging av databasen
* endring av klientkonfigurasjon
* endring av klienttokener
* omstart av oppdateringsagenter
* endring av oppdateringsjobber
* endring av RBAC
* endring av nettverkskonfigurasjon
* endring av pakkeadministrasjonsatferd

Temaet er en presentasjonspreferanse, ikke en driftskonfigurasjon.

---

## 9. Dokumentasjonsomfang

Dette dokumentet beskriver selve det valgfrie LUMS-temasystemet.

Generelle LUMS-emner er dokumentert separat:

* Installasjon og distribusjon → `install.md`
* Administrasjon og vedlikehold → `administration.md`
* Feilsøking → `troubleshooting.md`
* Sikkerhetsarkitektur og revisjoner → `security.md`
* Generell prosjektoversikt → `README.md`

Når ansvarsområdene holdes adskilt, blir temadokumentasjonen ikke en ekstra installasjons- eller administrasjonsmanual.

---

## 10. Grunnprinsipp

Det valgfrie temasystemet kan derfor oppsummeres slik:

> **Én LUMS. Én backend. Én sikkerhetsmodell. Mange mulige grensesnitt.**

# LUMS – valgfritt temasystem

## Del 2 – Temastruktur og valg

## 11. Temastruktur

Det valgfrie temasystemet skiller temavalget fra selve den visuelle presentasjonen.

Et tema består konseptuelt av tre lag:

```text
Theme Identifier
       │
       ▼
Theme Selection
       │
       ▼
Theme Presentation
```

Identifikatoren angir hvilket tema som er valgt.

Valgmekanismen avgjør hvilket tema som skal være aktivt for øyeblikket.

Presentasjonslaget bruker den tilhørende visuelle konfigurasjonen på LUMS-grensesnittet.

Dette skillet gjør det mulig å legge til eller fjerne temaer uten å endre den grunnleggende LUMS-applikasjonsarkitekturen.

---

## 12. Temavalg

Temavalget håndteres av frontend.

Det valgte temaet behandles som en lokal presentasjonspreferanse, ikke som en kontoeiendom på serversiden.

Konseptuelt:

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

Backenden trenger ikke å vite hvilket visuelt tema som er valgt for øyeblikket.

Det betyr også at et temabytte ikke påvirker andre brukere.

To brukere kan bruke den samme LUMS-instansen med helt forskjellige visuelle temaer.

---

## 13. Lokal temapreferanse

Nettleseren kan lagre det valgte temaet lokalt.

Formålet med lokal lagring er å gjøre bruken enklere:

```text
Browser
   │
   ├── Theme preference
   │
   └── LUMS application
```

Et lagret temavalg skal derfor behandles som en ikke-klarert klienttilstand.

Serveren må aldri tolke det som:

* en rolle
* en tillatelse
* en autentiseringstilstand
* en sikkerhetsinnstilling
* en administrativ preferanse

Nettleseren kan velge utseendet, men styrer ikke autorisasjonen.

---

## 14. Temainitialisering

Når LUMS-grensesnittet lastes inn, avgjør frontend hvilket tema som skal være aktivt.

Den konseptuelle sekvensen er:

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

Hvis ingen preferanse finnes, bør standardpresentasjonen for LUMS brukes.

Hvis en lagret identifikator ikke lenger støttes, bør samme tilbakefallsatferd brukes.

Dette hindrer at en utdatert lokal preferanse ødelegger grensesnittet.

---

## 15. Standardtema

Standardtemaet for LUMS er grunnpresentasjonen.

Det gir referanseutseendet som valgfrie temaer defineres opp mot.

Standardtemaet bør derfor være:

* funksjonelt
* lett å lese
* tilgjengelig
* visuelt komplett
* uavhengig av valgfrie dekorative ressurser

Valgfrie temaer må ikke bli en forutsetning for normal LUMS-drift.

---

## 16. Bruk av tema

Frontend kan representere det aktive temaet i en felles applikasjonstilstand eller som et temaattributt på rotnivå.

Konseptuelt:

```html
<html data-theme="theme-id">
```

Den nøyaktige implementasjonen kan endres etter hvert som frontend utvikler seg.

Det viktige arkitekturkravet er at det aktive temaet kan identifiseres konsekvent av frontendens stilmekanisme.

Dette gjør det mulig å holde temaspesifikk utforming atskilt fra den felles applikasjonsstrukturen.

---

## 17. Temaspesifikk utforming

Temastiler bør primært implementeres med CSS i stedet for ved å duplisere applikasjonsoppmerking.

Konseptuelt:

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

Da kan de samme applikasjonskomponentene være tilgjengelige i alle temaer.

En klienttabell er for eksempel fortsatt en klienttabell uansett hvilket tema som er aktivt.

Bare presentasjonen endres.

---

## 18. Delte applikasjonskomponenter

Temaer bør ikke opprette egne versjoner av LUMS-sidene.

Følgende prinsipp bør opprettholdes:

```text
One component
       │
       ├── Theme A
       ├── Theme B
       ├── Theme C
       └── Theme D
```

I stedet for:

```text
Theme A → separate page
Theme B → separate page
Theme C → separate page
```

Duplisering av sider vil gjøre vedlikeholdet betydelig vanskeligere og kan føre til ulik atferd mellom temaene.

Et tema bør derfor dekorere det felles grensesnittet i stedet for å erstatte selve applikasjonen.

---

## 19. Temafiler

Temaer kan bruke flere frontend-ressurser der det er hensiktsmessig.

Mulige ressurser omfatter:

* bakgrunnsbilder
* dekorativ grafikk
* ikoner
* animasjoner
* visuelle overlegg
* temaspesifikke illustrasjoner

Ressursene er fortsatt en del av frontendens presentasjonslag.

De må ikke inneholde:

* legitimasjon
* klienttokener
* hemmelige nøkler
* databasefiler
* autentiseringsmateriale
* private driftsdata

Temafiler skal behandles som offentlige frontend-ressurser.

---

## 20. Valgfrie visuelle effekter

Noen temaer kan tilby ekstra visuelle effekter.

Eksempler:

* animerte bakgrunner
* dekorative nettverkseffekter
* stemningsskapende bevegelser
* tematiserte grensesnittelementer
* dynamisk visuell dekorasjon

Slike effekter må være valgfrie.

De må aldri være nødvendige for at LUMS skal fungere.

---

## 21. Redusert bevegelse

Visuelle effekter bør ta hensyn til brukere som foretrekker redusert bevegelse.

Når animerte eller kontinuerlig skiftende elementer brukes, bør temasystemet tilby egnet atferd med redusert bevegelse.

Konseptuelt:

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

Tilgjengelighet har forrang foran dekorative animasjoner.

Et tema skal fortsatt kunne brukes når visuelle effekter er slått av.

---

## 22. Temauavhengighet

Temabytte må ikke utløse driftsmessige bieffekter.

For eksempel:

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

Temasystemet er derfor med hensikt isolert fra LUMS' driftslivssyklus.

---

## 23. Håndtering av temafeil

Et tema bør feile på en trygg måte.

Hvis en temaspesifikk ressurs eller presentasjonskomponent ikke kan lastes, bør det felles LUMS-grensesnittet fortsatt kunne brukes.

Foretrukket gjenopprettingsbane:

```text
Theme error
    │
    ▼
Fallback to standard presentation
    │
    ▼
LUMS remains usable
```

Et visuelt problem må ikke bli et problem med applikasjonstilgjengeligheten.

---

## 24. Legge til et nytt tema

Et nytt tema bør følge det eksisterende skillet mellom applikasjonsatferd og presentasjon.

Konseptuelt:

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

Et nytt tema er først fullført når eksisterende LUMS-funksjonalitet forblir uendret.

---

## 25. Fjerne et tema

Fjerning av et tema bør også håndteres på en skånsom måte.

Hvis en bruker har lagret et fjernet tema lokalt, bør frontend oppdage at identifikatoren ikke lenger er tilgjengelig og gå tilbake til standardtemaet.

Fjerning av et visuelt tema må derfor ikke gjøre brukerens LUMS-grensesnitt ubrukelig.

---

## 26. Navngiving av temaer

Temanavn bør skille tydelig mellom:

* intern identifikator
* visningsnavn
* visuelt konsept

For eksempel:

```text
Internal identifier:  standard
Display name:         Standard LUMS
```

Dette skillet lar synlig tekst utvikle seg uten at den interne implementasjonen må endres unødvendig.

---

## 27. Gjeldende temakonsepter

Det valgfrie LUMS-temasystemet er utformet rundt flere visuelle identiteter, samtidig som applikasjonen forblir felles.

De dokumenterte temakonseptene omfatter:

| Identifikator | Konsept |
| ------------- | ------- |
| `standard` | Standard LUMS |
| `LUMSStadium` | LUMS Stadion |
| `golf` | Golf Club |
| `nerd` | Nerd Mode |
| `geek` | Geek Lab |
| `admin` | Enterprise Admin |

Disse temaene representerer ulike visuelle retninger, ikke ulike LUMS-utgaver.

Alle er del av den samme applikasjonen.

---

## 28. Én backend, mange grensesnitt

Forholdet kan oppsummeres slik:

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

Temalaget slutter ved presentasjonsgrensen.

Alt under denne grensen er felles for alle temaer.

# LUMS – valgfritt temasystem

## Del 3 – Temakonsepter

## 29. Standard LUMS

Standard LUMS-temaet er referansepresentasjonen for applikasjonen.

Formålet er å tilby et tydelig og funksjonelt grensesnitt uten å kreve et bestemt visuelt konsept.

Standardtemaet bør prioritere:

* lesbarhet
* tydelig informasjonshierarki
* forutsigbar navigasjon
* tilgjengelighet
* få visuelle distraksjoner
* konsistent presentasjon av komponenter

Det er temasystemets reservepresentasjon.

Standard LUMS-temaet bør derfor kunne brukes selv om ingen av de valgfrie visuelle temaene er tilgjengelige.

---

## 30. LUMS Stadion

**LUMS Stadion** er en mer uttrykksfull visuell tolkning av LUMS-grensesnittet.

Konseptet kombinerer systemadministrasjon med en visuell identitet inspirert av et stadion.

Mulige designelementer:

* informasjonspaneler inspirert av resultattavler
* tydeligere visuelle statusindikatorer
* presentasjon orientert rundt hendelser
* tematiserte bakgrunner
* visuell vektlegging av driftsstatuser
* dekorative stadionelementer

Temaet er funksjonelt identisk med Standard LUMS.

En vellykket oppdatering er fortsatt en vellykket oppdatering.

En mislykket jobb er fortsatt en mislykket jobb.

Det er bare presentasjonen som endres.

---

## 31. Golf Club

Temaet **Golf Club** har en bevisst annerledes visuell identitet.

I stedet for et tradisjonelt server- eller infrastrukturlignende uttrykk bruker grensesnittet et roligere fritidskonsept.

Den visuelle retningen kan vektlegge:

* rene flater
* dempet dekorasjon
* elementer inspirert av golf
* visuelle metaforer fra golfbaner
* rolig statuspresentasjon
* lette tematiske aksenter

Konseptet viser at LUMS ikke trenger å ligne en tradisjonell administrasjonskonsoll visuelt for å være funksjonelt.

Backend- og applikasjonsatferden forblir uendret.

---

## 32. Nerd Mode

**Nerd Mode** er rettet mot en mer teknisk og leken presentasjon.

Konseptet kan fremheve den tekniske karakteren til LUMS gjennom elementer som:

* utforming inspirert av terminaler
* teknisk terminologi
* systemorienterte visuelle elementer
* presentasjon i utviklerstil
* diagnostisk estetikk
* bevisst teknisk dekorasjon

Temaet må fortsatt ha et tydelig informasjonshierarki.

Et lekent grensesnitt skal ikke gjøre driftsinformasjon vanskeligere å forstå.

---

## 33. Geek Lab

**Geek Lab** representerer et mer eksperimentelt teknisk miljø.

Det visuelle konseptet kan kombinere:

* laboratorieestetikk
* teknisk eksperimentering
* infrastruktursvisualisering
* systemdiagrammer
* elementer inspirert av vitenskap og ingeniørfag
* eksperimentelle visuelle effekter

Temaet skal få grensesnittet til å føles som et infrastrukturlaboratorium, samtidig som den samme LUMS-funksjonaliteten ligger under.

Visuell eksperimentering må holdes atskilt fra applikasjonsdriften.

---

## 34. Enterprise Admin

Temaet **Enterprise Admin** representerer et mer konservativt administrasjonsgrensesnitt.

Den visuelle retningen kan vektlegge:

* strukturert informasjon
* kompakte oppsett
* administrative oversikter
* tydelige statusindikatorer
* høy informasjonstetthet
* færre dekorative elementer

Dette temaet passer særlig godt for brukere som foretrekker et tradisjonelt utseende for administrasjonskonsoller.

Det gir ikke ytterligere administrative tillatelser.

Navnet beskriver det visuelle konseptet, ikke et autorisasjonsnivå.

---

## 35. Sammenligning av temaer

Temaene kan sees som ulike visuelle tolkninger av den samme applikasjonen:

| Tema | Visuell retning | Hovedpreg |
| ---------------- | --------------------------- | ------------------- |
| Standard LUMS | Ryddig / funksjonell | Referansegrensesnitt |
| LUMS Stadion | Stadion / arrangement | Uttrykksfullt |
| Golf Club | Fritid / ro | Avslappet |
| Nerd Mode | Teknisk / lekent | Utviklerorientert |
| Geek Lab | Eksperimentelt / teknisk | Laboratorium |
| Enterprise Admin | Strukturert / administrativt | Konservativt |

Tabellen beskriver kun presentasjonskonsepter.

Den beskriver **ikke** forskjeller i:

* tillatelser
* funksjoner
* API-tilgang
* klienttilgang
* jobbkjøring
* pakkeadministrasjon
* sikkerhet

---

## 36. Samme grensesnitt, ulik presentasjon

Et sentralt designmål er at samme applikasjonskomponent forblir gjenkjennelig på tvers av temaer.

For eksempel:

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

De underliggende klientdataene er identiske.

Bare presentasjonen endres.

Det samme gjelder:

* programvareinventar
* tilgjengelige oppdateringer
* oppdateringsjobber
* jobbhistorikk
* brukerinformasjon
* systemstatus
* grensesnitt for pakkeadministrasjon

---

## 37. Driftsstatuser

Temaer kan vektlegge ulike driftstilstander visuelt.

For eksempel:

```text id="5wyy17"
PENDING
RUNNING
SUCCESS
FAILED
```

Et tema kan bruke ulike visuelle uttrykk for disse tilstandene, men den semantiske betydningen må være konsistent.

Temaet må ikke omdefinere applikasjonstilstander.

For eksempel:

```text id="j4i9qd"
SUCCESS ≠ "looks green"

SUCCESS = actual LUMS job state
```

Den visuelle representasjonen er bare en gjengivelse av tilstanden i backend.

---

## 38. Presentasjon av feil

Temaer kan også endre hvordan feil presenteres visuelt.

Feilinformasjonen må likevel være forståelig.

Et tema skal ikke:

* skjule viktig feilinformasjon
* erstatte teknisk informasjon med dekorativ tekst
* gjøre advarsler umulige å skille fra normale tilstander
* undertrykke driftsfeil

Visuell utforming kan forbedre presentasjonen, men må ikke fjerne diagnostisk informasjon som trengs for å forstå et problem.

---

## 39. Konsistente statuser

Den samme statusen skal ha samme semantiske betydning i alle temaer.

For eksempel:

| Tilstand | Betydning |
| ------- | ------------------------- |
| Pending | Venter på kjøring |
| Running | Behandles nå |
| Success | Fullført uten feil |
| Failed | Kjøringen mislyktes |

Et tema kan vise disse tilstandene med ulike farger, ikoner, typografi eller oppsett.

Den underliggende betydningen må være uendret.

---

## 40. Temaspesifikk dekorasjon

Dekorative elementer skal være underordnet driftsinformasjonen.

Eksempler:

* bakgrunner
* mønstre
* illustrasjoner
* stemningseffekter
* tematiserte ikoner
* visuelle ornamenter

Følgende prioriteringsrekkefølge skal opprettholdes:

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

Dekorasjon må aldri prioriteres over informasjon som trengs for å bruke LUMS.

---

## 41. Visuell informasjonstetthet

Ulike temaer kan bruke forskjellig visuell informasjonstetthet.

For eksempel:

* Enterprise Admin kan prioritere informasjonstetthet.
* Standard LUMS kan prioritere balansert lesbarhet.
* Golf Club kan bruke mer luft.
* Nerd Mode kan bruke kompakte tekniske elementer.
* Stadion kan vektlegge store statusområder.
* Geek Lab kan gi mer visuell kontekst.

Dette er valg i presentasjonen.

De endrer ikke mengden eller autoriteten til de underliggende dataene.

---

## 42. Tilgjengelighet på tvers av temaer

Alle temaer må bevare grunnleggende brukervennlighet.

Dette omfatter:

* lesbar tekst
* tilstrekkelig visuelt skille
* kontroller som kan brukes
* forståelige statusindikatorer
* støtte for tastatur
* brukbare fokustilstander
* kompatibilitet med preferanser for redusert bevegelse

Farge skal ikke være den eneste måten å formidle en viktig tilstand på.

En mislykket jobb skal for eksempel ikke bare kunne identifiseres ved at den vises i en bestemt farge.

---

## 43. Temaspesifikke animasjoner

Temaer kan inneholde animasjoner når de bidrar til det visuelle konseptet.

Eksempler:

* diskrete overganger
* animerte bakgrunner
* nettverkseffekter
* statusoverganger
* stemningsdekorasjon

Animasjoner skal være underordnet applikasjonen.

De skal ikke:

* hindre interaksjon
* skjule kontroller
* distrahere kontinuerlig fra driftsdata
* forstyrre tilgjengelighet
* påvirke backend-operasjoner

---

## 44. Det levende nettverket

Noen LUMS-temaer kan bruke et dynamisk visuelt lag inspirert av nettverk.

Konseptet fremstiller LUMS som et levende infrastrukturlandskap:

```text id="7w1v8b"
Client ─────┐
            │
Client ─────┼──── LUMS
            │
Client ─────┘
```

En slik visualisering er dekorativ med mindre den uttrykkelig er koblet til faktiske applikasjonsdata.

En nettverksvisualisering skal derfor aldri tolkes som autoritativ nettverkstopologi med mindre applikasjonen uttrykkelig leverer disse opplysningene.

Dette skillet er viktig:

> **En visuell representasjon er ikke automatisk operasjonell telemetri.**

---

## 45. Dekorative data kontra reelle data

Temaspesifikke visuelle effekter må tydelig holdes atskilt fra reelle LUMS-data.

For eksempel:

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

Dette hindrer at brukerne forveksler en estetisk visualisering med faktisk systeminformasjon.

---

## 46. Temaidentitet

Hvert tema bør ha en gjenkjennelig identitet uten å bli et eget produkt.

Målet er:

```text id="qv1fbe"
Different visual identity
          +
Same LUMS functionality
          =
Optional LUMS Theme
```

Dette gjør temasystemet lekent og fleksibelt, samtidig som applikasjonens tekniske integritet bevares.

---

## 47. Designregel for temaer

Den viktigste designregelen for alle temaer er:

> **Et tema kan være uttrykksfullt, uvanlig, teknisk, lekent eller konservativt – men det må alltid være LUMS.**

Applikasjonen må fortsatt kunne gjenkjennes som det samme systemet uansett hvilken visuell presentasjon som er valgt.

# LUMS – valgfritt temasystem

## Del 4 – Implementering i frontend og tilgjengelighet

## 48. Temalag i frontend

Det valgfrie temasystemet hører utelukkende til LUMS-frontend.

Ansvaret er begrenset til presentasjon og håndtering av brukerens preferanser.

Konseptuelt:

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

Temalaget erstatter ikke den felles frontend-logikken.

I stedet legger det til et ekstra presentasjonslag rundt den.

---

## 49. Temainitialisering

Temainitialisering bør skje som del av den normale oppstartsprosessen i frontend.

Den konseptuelle sekvensen er:

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

Initialiseringen bør være lett og må ikke avhenge av at backend er tilgjengelig.

Brukeren bør kunne laste inn den visuelle presentasjonen selv om et API-kall senere mislykkes.

---

## 50. Tematilstand

Det aktive temaet er frontend-tilstand.

Det bør derfor behandles annerledes enn applikasjonstilstand.

### Tematilstand

Eksempler:

```text
Active visual theme
Reduced-motion preference
Visual presentation preferences
```

### Applikasjonstilstand

Eksempler:

```text
Logged-in user
User role
Client state
Package state
Update state
Job state
Audit state
```

Tematilstand må aldri overskrive eller utgi seg for å være applikasjonstilstand.

---

## 51. Temaattributt på rotnivå

Et attributt på rotnivå er en egnet konseptuell representasjon av det aktive temaet.

For eksempel:

```html
<html data-theme="standard">
```

eller:

```html
<html data-theme="nerd">
```

CSS kan deretter bruke det aktive temaet som en selektor.

Den konkrete implementasjonen kan utvikle seg, men det arkitektoniske målet er det samme:

> **Én applikasjonsstruktur, flere presentasjonsdefinisjoner.**

---

## 52. Organisering av CSS

Temaspesifikk utforming bør være tydelig atskilt fra LUMS' felles stiler.

Konseptuelt:

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

Felles stiler bør definere den funksjonelle strukturen.

Temastiler bør definere den visuelle identiteten.

Dette reduserer duplisering og gjør framtidig temavedlikehold enklere.

---

## 53. CSS-variabler

Temasystemer kan bruke CSS-egendefinerte egenskaper for å skille semantiske verdier fra deres visuelle representasjon.

For eksempel:

```css
:root {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Et tema kan deretter definere sine egne verdier:

```css
[data-theme="example"] {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Det viktige prinsippet er at komponenter, der det er praktisk, bruker semantiske variabler i stedet for å hardkode temaspesifikke verdier.

---

## 54. Delte komponenter

Temasystemet bør style delte komponenter i stedet for å duplisere dem.

Typiske komponenter omfatter:

* navigasjon
* knapper
* skjemaer
* tabeller
* statusindikatorer
* kort
* dialoger
* elementer for pakkeadministrasjon
* elementer for oppdateringsjobber
* klientinformasjon
* systeminformasjon

Den samme komponenten skal være funksjonelt identisk uansett hvilket tema som er aktivt.

---

## 55. Temafiler

Valgfrie temaer kan bruke dedikerte ressurser.

Mulige kategorier:

```text
Images
Icons
Backgrounds
Decorative graphics
Fonts
Animation assets
Visual effects
```

Temafiler skal forbli frontend-ressurser.

De må ikke inneholde sensitiv applikasjonsinformasjon.

Temafiler må særlig aldri inneholde:

* passord
* hemmelige nøkler
* klienttokener
* databaseinnhold
* private sertifikater
* autentiseringsmateriale

---

## 56. Lasting av ressurser

Temafiler bør bare lastes når de trengs.

Et tema bør ikke unødvendig øke ressursbruken på alle LUMS-sider bare fordi temaet finnes.

Der det er praktisk:

```text
Selected theme
      │
      ▼
Required assets
      │
      ▼
Browser
```

i stedet for:

```text
All themes
      │
      ▼
All assets loaded simultaneously
```

Dette blir stadig viktigere etter hvert som flere temaer og visuelle effekter legges til.

---

## 57. Temaytelse

Visuell tilpasning må ikke forringe brukervennligheten til LUMS vesentlig.

Vær særlig oppmerksom på:

* store bakgrunnsbilder
* elementer som animeres kontinuerlig
* canvas-effekter
* gjentatte DOM-oppdateringer
* kostbare visuelle filtre
* unødvendige nettverksforespørsler

Driftssider som klientlister, programvareinventar og visninger av oppdateringsjobber skal fortsatt være responsive.

---

## 58. Dekorativ JavaScript

Et tema kan bruke JavaScript til visuelle effekter.

Eksempler:

* animerte bakgrunner
* nettverksvisualiseringer
* dynamisk dekorasjon
* temaspesifikke interaksjoner

Slik JavaScript-kode bør holdes atskilt fra applikasjonens driftslogikk.

Et dekorativt skript må aldri ha ansvar for:

* autorisasjon
* oppretting av jobber
* pakkeinstallasjon
* pakkefjerning
* oppdateringskjøring
* klientautentisering
* revisjonslogging

Skillet skal være tydelig:

```text
Theme JavaScript
      ≠
LUMS operational JavaScript
```

---

## 59. Nettverksvisualisering

Hvis et tema bruker en nettverkslignende visualisering, bør den behandles som en presentasjonskomponent.

For eksempel:

```text
Canvas / Visual Layer
        │
        ▼
Decorative Network
        │
        ▼
Theme Presentation
```

Med mindre den uttrykkelig er koblet til autoritative LUMS-data, bør visualiseringen ikke gi inntrykk av å vise den faktiske nettverkstilstanden.

Dette hindrer at dekorativ grafikk forveksles med overvåking eller telemetri.

---

## 60. Redusert bevegelse

Temaer med animasjoner bør støtte preferanser for redusert bevegelse.

Foretrukket atferd kan konseptuelt uttrykkes slik:

```text
prefers-reduced-motion: reduce
            │
            ▼
Reduce or disable decorative motion
```

Viktig funksjonalitet må forbli uendret.

Redusert bevegelse skal bare påvirke presentasjonen.

---

## 61. Fokus og tastaturnavigasjon

Temastiler må bevare brukervennlighet med tastatur.

Viktige interaktive elementer skal fortsatt ha tydelige fokustilstander.

Temaer bør ikke fjerne fokusrammer uten å tilby et like tydelig alternativ.

For eksempel:

```text
Keyboard focus
      │
      ▼
Clearly visible control state
```

Dette gjelder:

* navigasjon
* knapper
* lenker
* skjemafelt
* velgere
* dialoger
* kontroller for pakkeadministrasjon

---

## 62. Uavhengighet fra farge

Viktig informasjon må ikke være avhengig av farge alene.

For eksempel:

```text
FAILED
```

skal fortsatt kunne forstås gjennom tekst, ikoner, struktur eller en annen tilgjengelig indikasjon selv om temafargene ikke er tilgjengelige.

Dette er særlig viktig fordi temaer kan bruke svært ulike fargepaletter.

---

## 63. Kontrast

Alle temaer bør ha tilstrekkelig kontrast mellom:

* tekst og bakgrunn
* kontroller og bakgrunn
* statusindikatorer og elementene rundt
* fokuserte elementer og omgivelsene

En visuelt interessant palett erstatter ikke lesbar informasjon.

Når temafarger kommer i konflikt med tilgjengelighetskrav, skal lesbarhet prioriteres.

---

## 64. Grensesnitt for temavalg

Selve temavelgeren er del av det felles LUMS-grensesnittet.

Den bør være forståelig uansett hvilket tema som er aktivt.

Konseptuelt:

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

Valg av et annet tema bør oppdatere presentasjonen uten å endre den gjeldende LUMS-økten eller driftsstatusen.

---

## 65. Uavhengighet fra økten

Temabytte må ikke logge brukeren ut.

Det må ikke:

* ugyldiggjøre økten
* endre rollen
* rotere klienttokener
* endre autentiseringstilstand på serveren

Temapreferansen er separat fra autentisering.

```text
Theme change
     │
     └── Session remains unchanged
```

---

## 66. Uavhengighet fra RBAC

Temaer må forbli uavhengige av RBAC.

For eksempel:

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

Valgt tema endrer ikke disse tillatelsene.

En Viewer som bruker Enterprise Admin, blir ikke administrator.

En Administrator som bruker Nerd Mode, mister ikke administratorrettighetene sine.

Backenden forblir autoritativ i alle tilfeller.

---

## 67. Isolering av feil

Feil i valgfrie visuelle funksjoner bør ikke ødelegge den grunnleggende LUMS-driften.

Hvis en dekorativ animasjon for eksempel mislykkes:

```text
Animation failure
      │
      ▼
Theme remains usable
      │
      ▼
LUMS remains operational
```

Der det er mulig, bør visuelle funksjoner feile uavhengig av applikasjonsfunksjonaliteten.

Dette er spesielt viktig for valgfrie effekter som animerte bakgrunner og nettverksvisualiseringer.

---

## 68. Nettleserkompatibilitet

Temasystemet bør bruke nettleserfunksjoner som støttes av nettleserne i LUMS-distribusjonsmiljøet.

Hvis en visuell funksjon ikke er tilgjengelig, bør grensesnittet degraderes på en skånsom måte i stedet for å bli ubrukelig.

Standardpresentasjonen bør fortsatt være grunnleggende reservevalg.

---

## 69. Implementeringsprinsipp

Implementasjonen kan oppsummeres slik:

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

Følgende områder må holdes utenfor temalaget:

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

Dette skillet gjør temasystemet uttrykksfullt nok uten at det kobles til LUMS' kjerneatferd.

# LUMS – valgfritt temasystem

## Del 5 – Sikkerhet, testing og utvikling

## 70. Sikkerhetsgrense

Temasystemet er en del av frontend og kjører derfor i et ikke-klarert klientmiljø.

Nettleseren styrer presentasjonslaget.

Nettleseren styrer **ikke** LUMS-autorisasjonen.

Sikkerhetsgrensen er fortsatt:

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

Alle sikkerhetsfølsomme avgjørelser må derfor fortsatt tas på serveren.

---

## 71. Temavalg er ikke autorisasjon

Et valgt tema må aldri tolkes som et autorisasjonssignal.

For eksempel:

```text id="8u3r8v"
data-theme="admin"
```

betyr ikke at den gjeldende brukeren er administrator.

Ordet `admin` i en temaidentifikator er rent beskrivende.

Brukerens faktiske rolle må alltid hentes fra den autentiserte applikasjonsøkten og autorisasjonslogikken på serveren.

---

## 72. Synlighet i frontend er ikke sikkerhet

Et tema eller et frontend-skript kan skjule et grensesnittelement.

Dette er nyttig for presentasjonen.

Det er ikke nok til å kontrollere tilgang.

For eksempel:

```text id="7m8c6w"
Hidden button
      ≠
Unauthorized operation prevented
```

Det tilsvarende API-endepunktet må kontrollere brukerens tillatelser uavhengig.

Dette gjelder all privilegert LUMS-funksjonalitet.

---

## 73. Temafiler er offentlige

Frontend-ressurser bør anses som offentlig tilgjengelige for alle som har tilgang til LUMS-nettgrensesnittet.

Temafiler må derfor aldri inneholde hemmeligheter.

Legg aldri følgende i temafiler:

```text id="1zjz7n"
Passwords
API secrets
Client tokens
Private keys
Database files
Session secrets
Authentication credentials
```

Hvis informasjon må holdes konfidensiell, hører den ikke hjemme i en temafil.

---

## 74. Ingen backend-hemmeligheter i temaer

JavaScript for temaer må ikke inneholde serverlegitimasjon eller privilegert API-materiale.

Når et tema trenger data, bør det kommunisere med det eksisterende applikasjonslaget i frontend.

Det må ikke introdusere en alternativ autentiseringsmekanisme.

Følgende prinsipp gjelder:

> **Temaer bruker presentasjonsdata; de oppretter ikke sikkerhetslegitimasjon.**

---

## 75. Cross-Site Request Forgery

Temafunksjonalitet må ikke omgå eksisterende CSRF-beskyttelse.

Hvis et tema tilbyr et grensesnittelement som starter en operasjon som krever en beskyttet forespørsel, må forespørselen følge de samme sikkerhetskravene som det felles LUMS-grensesnittet.

Visuell kode får ikke noe unntak fra dette.

---

## 76. Bruk av API

Et tema bør unngå å implementere egen driftslogikk for API-et direkte.

Når applikasjonsdata trengs, bør temaet bruke de etablerte mekanismene i LUMS-frontend/applikasjonen.

Dette hindrer at flere uavhengige implementasjoner oppstår for:

* autentisering
* API-forespørsler
* feilhåndtering
* antakelser om autorisasjon
* jobbhåndtering

Den felles applikasjonslogikken forblir det autoritative integrasjonslaget i frontend.

---

## 77. Temaisolasjon

Et tema bør kunne fjernes uten å fjerne kjernefunksjonalitet i LUMS.

Konseptuelt:

```text id="3m1o8q"
Remove optional theme
        │
        ▼
Standard LUMS remains
        │
        ▼
Application remains operational
```

Dette gjør valgfrie temaer reelt valgfrie.

---

## 78. Sikkerhetstesting

Sikkerhetstesting bør vise at temabytter ikke endrer LUMS-sikkerhetsmodellen.

Relevante kontroller omfatter:

* at Viewer fortsatt er Viewer
* at Operator fortsatt er Operator
* at Administrator fortsatt er Administrator
* at beskyttede API-endepunkter fortsatt er beskyttet
* at CSRF-beskyttelsen fortsatt er aktiv
* at klientautentisering er uendret
* at tillatelser til oppdateringsjobber er uendret
* at tillatelser til pakkeadministrasjon er uendret
* at revisjonslogging er uendret

Temaet må aldri brukes som bevis på at en operasjon er sikker.

---

## 79. Funksjonell tematesting

Hvert tema bør testes med den felles applikasjonen.

Som et minimum:

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

Nøyaktig hvilke funksjoner som er tilgjengelige, avhenger av den autentiserte brukerens rolle.

Formålet med testen er å sikre at temagjengivelsen ikke ødelegger normal applikasjonsfunksjonalitet.

---

## 80. RBAC-tematesting

Tematesting bør omfatte alle relevante roller.

En grunnleggende matrise er:

| Rolle | Tematesting |
| ------------- | ------------- |
| Administrator | Påkrevd |
| Operator | Påkrevd |
| Viewer | Påkrevd |

For hver rolle må du verifisere at temabytte ikke endrer funksjonaliteten brukeren har tillatelse til.

For eksempel:

```text id="3n5p2m"
Viewer + Nerd Mode
        =
Viewer permissions

Viewer + Enterprise Admin
        =
Viewer permissions
```

Det visuelle temaet må ikke endre resultatet.

---

## 81. Tester for temabytte

Temabytte bør testes gjentatte ganger.

Eksempel på sekvens:

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

Applikasjonen bør kunne brukes gjennom hele sekvensen.

Vær særlig oppmerksom på:

* endringer i oppsett
* tabeller
* navigasjon
* dialoger
* skjemaer
* statusindikatorer
* lang tekst
* responsiv atferd

---

## 82. Testing av lagring

Hvis temapreferansen lagres lokalt, test følgende:

1. Velg et tema.
2. Last siden på nytt.
3. Bekreft at temaet fortsatt er valgt.
4. Lukk nettleseren.
5. Åpne LUMS igjen.
6. Bekreft at preferansen fortsatt håndteres riktig.
7. Fjern eller ugyldiggjør det lagrede temaet.
8. Bekreft at systemet går tilbake til standardtemaet.

Den lagrede verdien må aldri behandles som sikkerhetstilstand for applikasjonen.

---

## 83. Testing av ugyldige temaer

En ugyldig temaidentifikator må ikke ødelegge grensesnittet.

For eksempel:

```text id="4j5cqn"
unknown-theme
```

bør føre til et sikkert reservevalg i stedet for en ubrukelig side.

Ønsket atferd:

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

## 84. Testing av feil i ressurser

Valgfrie ressurser bør også testes med feiltilstander.

Eksempler:

* manglende bilde
* utilgjengelig animasjon
* ugyldig ressursbane
* visuell funksjon som ikke støttes
* JavaScript-feil i valgfri dekorasjon

Den felles applikasjonen bør fortsatt kunne brukes når det er mulig.

---

## 85. Testing av redusert bevegelse

For temaer med animasjon må både normal- og redusert bevegelse testes.

```text id="l1h4nb"
Normal motion
     │
     └── Theme effects available

Reduced motion
     │
     └── Effects reduced or disabled
```

Viktige applikasjonskontroller må fungere fullt ut i begge tilfeller.

---

## 86. Responsiv testing

Temaer bør testes ved ulike visningsstørrelser.

Som et minimum:

* skrivebord
* visning på størrelse med nettbrett
* smal visning på størrelse med mobil

Den visuelle identiteten må ikke gå på bekostning av brukbare kontroller eller lesbare applikasjonsdata.

Vær særlig oppmerksom på:

* navigasjon
* tabeller
* handlingsknapper
* kontroller for pakkeadministrasjon
* statusinformasjon for jobber
* dialoger
* temavelgere

---

## 87. Ytelsestesting

Visuelle effekter bør vurderes med tanke på hvordan de påvirker nettleserytelsen.

Relevante observasjoner omfatter:

* sidelastingstid
* respons ved gjengivelse
* CPU-bruk
* minnebruk
* jevn animasjon
* gjentatte DOM-oppdateringer
* nettverksforespørsler

Temaer bør forbedre presentasjonen, ikke bli en ytelsesflaskehals.

---

## 88. Utviklingsarbeidsflyt

Når det er mulig, bør et nytt tema utvikles uavhengig av backend-endringer.

Anbefalt arbeidsflyt:

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

Backend-endringer bør bare innføres når det finnes et reelt applikasjonsbehov.

Et visuelt tema bør vanligvis ikke kreve endringer i backend.

---

## 89. Utviklingsregler

Når du utvikler et tema:

1. Gjenbruk eksisterende LUMS-komponenter.
2. Unngå å duplisere sider.
3. Isoler temaspesifikke stiler.
4. Hold dekorativ JavaScript atskilt fra driftslogikk.
5. Ikke innfør autentiseringslogikk.
6. Ikke innfør autorisasjonslogikk.
7. Ikke eksponer hemmeligheter.
8. Bevar tilgjengelighet.
9. Bevar atferd for redusert bevegelse.
10. Test alle relevante roller.
11. Test tilbakefall til standardtemaet.
12. Dokumenter nye ressurser og ny atferd.

---

## 90. Verifisering av endringer

Før en temabytteendring anses som fullført, må både presentasjon og funksjonalitet verifiseres.

En nyttig verifiseringssekvens:

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

Et tema er ikke fullført bare fordi det ser riktig ut.

LUMS-atferden må også være uendret.

---

## 91. Regresjonsprinsipp

Utvikling av temaer bør følge det samme overordnede prosjektprinsippet som andre LUMS-endringer:

> **Endre → Test → Verifiser → Dokumenter**

En visuell endring kan likevel føre til funksjonelle regresjoner.

Eksempler:

* skjulte knapper
* uleselig tekst
* ødelagt oppsett
* utilgjengelige kontroller
* JavaScript-konflikter
* manglende ressurser
* feilaktige selektorer
* feil i mobiloppsettet

Testing er derfor en del av temautviklingen, ikke et valgfritt siste trinn.

---

## 92. Feilsøking: Temaet lastes ikke

Hvis det valgte temaet ikke vises:

1. Last siden på nytt.
2. Kontroller om standardtemaet lastes.
3. Kontroller nettleserkonsollen.
4. Kontroller om valgt temaidentifikator er gyldig.
5. Kontroller om nødvendige temafiler er tilgjengelige.
6. Se etter JavaScript-feil.
7. Fjern den lokale temapreferansen om nødvendig.
8. Last siden på nytt og kontroller tilbakefall til standardtemaet.

Ikke endre sikkerhetskonfigurasjonen i backend for å løse et frontend-problem med temaet.

---

## 93. Feilsøking: Temaet ødelegger oppsettet

Hvis et tema fører til problemer med oppsettet:

1. Bytt til Standard LUMS-temaet.
2. Bekreft at det felles grensesnittet fungerer.
3. Finn den berørte komponenten.
4. Undersøk temaspesifikk CSS.
5. Kontroller responsiv atferd.
6. Se etter feil i nettleserkonsollen.
7. Rett temastilen.
8. Test andre temaer på nytt.

Standardtemaet gir et viktig sammenligningsgrunnlag for diagnostikk.

---

## 94. Feilsøking: Temaet fører til JavaScript-feil

Hvis temaspesifikk JavaScript fører til feil:

1. Bytt til standardtemaet.
2. Bekreft normal LUMS-funksjonalitet.
3. Finn skriptet for temaet som feiler.
4. Avgjør om feilen gjelder dekorasjon eller applikasjonsatferd.
5. Fjern den temaspesifikke feilen.
6. Bekreft at felles LUMS-JavaScript ikke er påvirket.
7. Test temabytte på nytt.

Drifts-JavaScript bør ikke endres bare for å kompensere for en dekorativ temafeil.

---

## 95. Feilsøking: Temapreferansen er ugyldig

Hvis et gammelt eller ugyldig tema fortsatt er lagret lokalt:

```text id="b9n8wq"
Invalid stored preference
        │
        ▼
Fallback to Standard
        │
        ▼
Select a valid theme
```

Den foretrukne løsningen er et trygt tilbakefall, ikke manuell inngripen i backend.

---

## 96. Temadokumentasjon

Hvert nytt tema bør dokumentere:

* intern identifikator
* visningsnavn
* visuelt konsept
* nødvendige filer
* valgfrie visuelle effekter
* hensyn til tilgjengelighet
* atferd for redusert bevegelse
* kjente begrensninger

Implementasjonsspesifikk dokumentasjon skal beskrive den faktiske gjeldende koden, ikke antakelser om hvordan temaet kan fungere.

---

## 97. Gjeldende temautvalg

De dokumenterte temakonseptene er for tiden:

```text id="r0w4u5"
standard       → Standard LUMS
LUMSStadium    → LUMS Stadium
golf           → Golf Club
nerd           → Nerd Mode
geek           → Geek Lab
admin          → Enterprise Admin
```

Temautvalget kan utvides.

Flere temaer kan legges til uten å endre den underliggende LUMS-arkitekturen, forutsatt at skillet mellom presentasjon og applikasjonsatferd opprettholdes.

---

## 98. Utviklingsprinsipp

Det valgfrie temasystemet bør forbli en kontrollert frontend-utvidelse.

Formålet er å gjøre LUMS mer uttrykksfullt og tilpasningsdyktig uten å gjøre den driftsmessige applikasjonen mer komplisert.

Den foretrukne arkitekturen er derfor:

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

Den felles applikasjonen forblir grunnlaget.

Temaer forblir valgfrie utvidelser.

# LUMS – valgfritt temasystem

## Del 6 – Vedlikehold, utvidelser og sluttstatus

## 99. Vedlikehold av temaer

Vedlikehold av temaer bør holdes atskilt fra vedlikehold av LUMS-kjernen der det er mulig.

En visuell temaoppdatering bør normalt bare omfatte frontend-ressurser.

Typiske endringer omfatter:

* CSS-justeringer
* visuelle ressurser
* JavaScript som er spesifikt for temaet
* tilgjengelighetsforbedringer
* rettelser for responsivt oppsett
* justeringer av animasjoner
* endringer i temanavn eller presentasjon

En temaoppdatering bør ikke kreve endringer i:

* klientkonfigurasjon
* klienttokener
* databaseskjema
* oppdateringsjobber
* logikk for pakkeadministrasjon
* autentisering
* RBAC
* sikkerhetskontroller på serversiden

Hvis en temaendring uventet krever slike endringer, bør avhengigheten gjennomgås før arbeidet fortsetter.

---

## 100. Temaoppdateringer

Temaoppdateringer bør følge den vanlige utviklingsprosessen for LUMS:

```text id="2p7z9r"
Modify
   ↓
Test
   ↓
Verify
   ↓
Document
```

For større endringer:

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

Et tema skal ikke regnes som ferdig bare fordi det visuelle resultatet ser riktig ut.

---

## 101. Legge til et nytt tema

Et nytt tema kan innføres uten å endre LUMS-backenden.

Anbefalt prosess:

### Trinn 1 – Definer konseptet

Beskriv:

* visuell identitet
* ønsket stil
* typografi
* farger
* dekorative elementer
* valgfrie animasjoner

### Trinn 2 – Definer identifikatoren

Velg en stabil intern identifikator.

### Trinn 3 – Implementer presentasjonen

Legg til nødvendige stiler og ressurser.

### Trinn 4 – Integrer temavalget

Gjør temaet tilgjengelig gjennom den felles temavelgeren.

### Trinn 5 – Test

Kontroller:

* vanlige sider
* interaktive kontroller
* responsive oppsett
* tilgjengelighet
* redusert bevegelse
* alle relevante RBAC-roller
* reserveatferd

### Trinn 6 – Dokumenter

Dokumenter temaet og relevante implementasjonsdetaljer.

---

## 102. Fjerne et tema

Fjerning av et tema bør behandles som en kompatibilitetsendring for brukere som fortsatt kan ha valgt temaet lokalt.

Frontend skal derfor håndtere en foreldet identifikator på en sikker måte.

Foretrukket atferd:

```text id="x4e7p1"
Old theme identifier
       │
       ▼
Theme no longer available
       │
       ▼
Standard LUMS
```

Fjerning av et tema skal aldri kreve en databasemigrering bare for å fjerne en nettleserlagret preferanse.

---

## 103. Gi et tema nytt navn

Et visningsnavn kan vanligvis endres uavhengig av den interne identifikatoren.

For eksempel:

```text id="8q4n1k"
Internal identifier
        │
        └── remains stable

Display name
        │
        └── may change
```

Hvis selve den interne identifikatoren endres, kan det være nødvendig med en migrering eller et kompatibilitetskart for eksisterende lokale preferanser.

Det foretrukne er å holde identifikatorene stabile når det er praktisk mulig.

---

## 104. Temakompatibilitet

Temaer bør forbli kompatible med endringer i det felles LUMS-grensesnittet.

Når en ny delt komponent innføres, bør eksisterende temaer kontrolleres for:

* manglende stil
* ødelagt avstand
* uleselig tekst
* feil farger
* manglende responsiv atferd
* feil fokustilstander
* utilgjengelige kontroller

En ny backend-funksjon krever ikke automatisk en ny temafunksjon.

Den felles applikasjonen forblir fasiten.

---

## 105. Nye LUMS-funksjoner

Når LUMS får en ny funksjon, bør støtte for temaer vanligvis vurderes etter at den felles funksjonen virker.

Anbefalt rekkefølge:

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

Dette hindrer at visuell tilpasning blir en avhengighet for utvikling av kjernefunksjoner.

---

## 106. Stabilitet i tema-API-et

Temasystemet bør unngå å opprette et eget API-lag med mindre det finnes et reelt behov.

Temaer bør helst bruke den samme frontend-applikasjonstilstanden og de samme API-mekanismene som LUMS allerede bruker.

Dette reduserer:

* duplisert forespørselslogikk
* duplisert feilhåndtering
* inkonsekvente antakelser om autorisasjon
* ekstra vedlikeholdsarbeid
* unødvendig angrepsflate

Temasystemet er derfor med hensikt lettvektig.

---

## 107. Sikkerhetsgjennomgang av tema

Ved innføring eller vesentlig endring av et tema bør følgende gjennomgås:

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

Denne gjennomgangen bør utføres selv når endringen ser ut til å være rent visuell.

Frontend-kode er fortsatt kjørbar kode.

---

## 108. Tilgjengelighetsgjennomgang av tema

For hvert tema skal du kontrollere:

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

Tilgjengelighet bør behandles som en del av temakvaliteten, ikke som en valgfri forbedring.

---

## 109. Sjekkliste for temaregresjoner

Før en temaendring godkjennes:

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

Nøyaktig hvilke funksjoner som vises under testen, avhenger av brukerens rolle.

---

## 110. Uavhengighet fra drift

Det valgfrie temasystemet er med hensikt uavhengig av LUMS' driftslivssyklus.

Temabytte skal ikke kreve:

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

Dette gjør at presentasjonslaget kan utvikles uavhengig av infrastrukturlaget.

---

## 111. Uavhengighet fra utrulling

Temaressurser er en del av LUMS-applikasjonens frontend.

Generelle utrullingsprosedyrer er fortsatt dokumentert i hoveddokumentasjonen for installasjon og administrasjon.

Dette dokumentet gjentar med hensikt ikke:

* Docker-utrullingsprosedyrer
* kommandoer for herding av containere
* Nginx-konfigurasjon
* prosedyrer for sikkerhetskopiering av databasen
* prosedyrer for gjenoppretting av serveren
* installasjonsprosedyrer for klienter

Disse emnene hører hjemme i den relevante driftsdokumentasjonen.

Dette skillet hindrer at temadokumentasjonen blir utdatert når utrullingsarkitekturen endres.

---

## 112. Skille mellom kilde og kjøretid

Temasystemet bør forstås som en del av applikasjonens kildekode.

Det er et skille mellom:

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

En temaendring i kildekoden betyr ikke automatisk at en distribusjon som allerede kjører, har mottatt endringen.

Den vanlige bygge- og utrullingsprosessen for LUMS er fortsatt ansvarlig for å levere oppdaterte frontend-ressurser.

---

## 113. Versjonering

Temaer trenger ikke å innføre en separat LUMS-backendversjon.

Et tema kan utvikles som en del av frontend-/applikasjonsversjonen.

Hvis en temaendring medfører kompatibilitetsproblemer, bør disse dokumenteres uttrykkelig.

For eksempel:

```text id="5y1p8f"
Theme change
     │
     ├── visual-only
     │
     └── compatibility-affecting
```

Den siste kategorien krever ekstra regresjonstesting.

---

## 114. Utgivelsesberedskap

Før en LUMS-utgivelse som inneholder temaendringer, skal følgende verifiseres:

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

Temaendringer må ikke få skjule regresjoner i kjerneapplikasjonen.

---

## 115. Gjeldende temasett

De gjeldende dokumenterte temakonseptene er:

| Identifikator | Visningsnavn | Konsept |
| ------------- | ---------------- | --------------------------- |
| `standard` | Standard LUMS | Referansegrensesnitt |
| `LUMSStadium` | LUMS Stadium | Stadion / arrangement |
| `golf` | Golf Club | Rolig / rekreasjon |
| `nerd` | Nerd Mode | Teknisk / lekent |
| `geek` | Geek Lab | Eksperimentelt / teknisk |
| `admin` | Enterprise Admin | Strukturert / administrativt |

Disse temaene deler samme LUMS-applikasjon og backend.

De er visuelle varianter, ikke separate produkter eller tillatelsesnivåer.

---

## 116. Gjeldende status

Det valgfrie temasystemet er en utvidelse av LUMS' frontend-arkitektur.

De tiltenkte egenskapene er:

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

Implementasjonsdetaljer bør alltid holdes synkronisert med den gjeldende frontend-kildekoden.

---

## 117. Framtidige utvidelser

Temasystemet kan utvides i flere retninger uten å endre den underliggende arkitekturen.

Mulige framtidige tillegg omfatter:

* flere temaer
* forbedrede forhåndsvisninger av temaer
* mer detaljerte visuelle preferanser
* flere tilgjengelighetsinnstillinger
* forbedret responsiv atferd
* temaspesifikke dashbordoppsett
* flere valgfrie visualiseringer

Slike utvidelser bør fortsatt følge det samme skillet mellom presentasjon og applikasjonsatferd.

---

## 118. Endelig arkitektur

Det samlede konseptet kan oppsummeres slik:

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
          └──────────────┬──────────────┘
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

Det visuelle laget forblir valgfritt.

Applikasjonslaget forblir autoritativt.

Sikkerhetslaget forblir uavhengig.

---

## 119. Avsluttende prinsipp

Det valgfrie temasystemet finnes for å gjøre LUMS mer personlig, uttrykksfullt og tilpasningsdyktig uten å gå på kompromiss med den tekniske arkitekturen.

Grunnregelen er uendret:

> **Én LUMS · Mange grensesnitt · Samme backend**

Et tema kan endre atmosfæren i LUMS.

Det må aldri endre hva LUMS faktisk har lov til å gjøre.
