# LUMS Säkerhetsdokumentation

**LUMS — Linux Update Management Server**

Detta dokument beskriver den aktuella säkerhetsarkitekturen, implementerade säkerhetskontroller, resultat från säkerhetsgranskningen, operativa begränsningar och säkerhetsrelaterade designbeslut för LUMS.

Dokumentet återspeglar **det för närvarande implementerade systemtillståndet**. Planerade eller framtida förbättringar identifieras uttryckligen som sådana.

---

# Säkerhetsprinciper

LUMS följer en strategi med försvar på djupet för Linux-uppdateringshantering.

Säkerhetsmodellen separerar administrativ autentisering, klientautentisering, auktorisering, kontrollerad uppdateringsexekvering och granskningsloggning.

De primära säkerhetsmålen är:

* autentiserad administrativ åtkomst
* rollbaserad auktorisering
* autentiserad klientkommunikation
* kontrollerad uppdateringsexekvering
* skydd mot samtidig jobbexekvering
* återställningsbara uppdateringsjobb
* skyddade hemligheter
* kontrollerad containerexekvering
* granskningsbara säkerhetskänsliga operationer
* förutsägbar felhantering
* testning av säkerhetsregressioner

LUMS är avsett främst för kontrollerade infrastruktur-, laboratorie- och interna nätverksmiljöer.

Det bör inte exponeras direkt mot det publika Internet utan ytterligare en säkerhetsgranskning och lämpliga nätverkskontroller.

---

# Säkerhetsarkitektur

LUMS består av följande säkerhetsrelevanta komponenter:

* Webbadministrationsgränssnitt
* REST API
* SQLite-databas
* LUMS Agent på hanterade klienter
* APT- och pacman-pakethanteringsbackend
* Uppdateringsjobb- och återställningsmekanismer
* Nginx HTTPS omvänd proxy
* Härdad Docker-container

Det grundläggande hanteringsflödet är:

Browser → HTTPS/Nginx → LUMS API → SQLite → LUMS Agent → Pakethanterare → Resultat → SQLite → Webbgränssnitt

Autentisering och auktorisering är avsiktligt separerade.

En giltig autentiserad session ger inte automatiskt åtkomst till varje administrativ operation.

Auktorisering upprätthålls på serversidan. Webbgränssnittet döljer dessutom funktioner som inte är tillgängliga för den aktuella rollen, men UI-synlighet behandlas aldrig som en säkerhetsgräns.

---

## Administrativ autentisering

Administrativa användare autentiserar sig via LUMS webbgränssnitt.

Lösenord lagras aldrig i klartext. LUMS använder Argon2-baserad lösenordshashning för lösenordslagring.

Administrativa sessioner använder:

* autentiserad sessionshantering på serversidan
* sessionens utgång
* sessionsregenerering
* CSRF-skydd för tillståndsändrande webbläsarbegäranden
* inloggningshastighetsbegränsning
* sessionsogiltigförklaring vid utloggning
* rollvalidering på serversidan

Autentisering och auktorisering förblir separata säkerhetskontroller.

En framgångsrikt autentiserad användare måste fortfarande inneha den nödvändiga behörigheten för skyddade operationer.

---

# Rollbaserad åtkomstkontroll

LUMS stöder för närvarande tre webbanvändarroller:

* `administrator`
* `operator`
* `viewer`

Rollmallar lagras i `users.role`; individuella behörigheter lagras på serversidan i `user_permissions`.

Servern laddar de effektiva behörigheterna för varje autentiserat konto. Behörighetsinformation på klientsidan styr endast presentationen och ersätter aldrig auktorisering på serversidan.

## Administrator

Administratörer har full administrativ och operativ åtkomst.

De kan:

* visa klienter
* skapa klienter
* inaktivera klienter
* rotera klienttokens
* visa installerade paket och tillgängliga uppdateringar
* skapa uppdateringsjobb
* köra stödda uppdateringsoperationer
* visa uppdateringsjobbshistorik
* använda pakethantering
* använda systemunderhållsfunktioner
* hantera användare
* hantera användarroller
* komma åt administrativa funktioner

## Operator

Operatorer kan utföra operativa uppdateringshanteringsuppgifter.

De kan:

* visa klienter
* visa installerade paket och tillgängliga uppdateringar
* skapa uppdateringsjobb
* köra stödda uppdateringsoperationer
* visa uppdateringsjobbshistorik
* använda pakethantering
* använda systemunderhållsfunktioner

Operatorer kan inte:

* hantera användare
* ändra användarroller
* skapa klienter
* inaktivera klienter
* rotera klienttokens

## Viewer

Viewers har begränsad skrivskyddad åtkomst.

De kan:

* visa klienter
* visa installerad programvara

Följande hanteringsområden är dolda för Viewer-konton:

* Uppdateringar
* Uppdateringsjobb
* Uppdateringshistorik
* Pakethantering
* Systemunderhåll

Viewer-konton kan inte utföra tillståndsändrande uppdateringshanteringsoperationer.

Servern upprätthåller dessa begränsningar oberoende genom autentisering och behörighetskontroller per användare.

---

# Klientautentisering

Varje hanterad LUMS-klient använder en individuell Bearer-token.

Autentiseringsmekanismen följer modellen:

`Authorization: Bearer <CLIENT_TOKEN>`

Servern lagrar inte klienttokens som klartextvärden.

Istället lagrar LUMS en SHA-256-hexdigest av klienttoken.

Autentiseringsflödet är:

Client Token → SHA-256 → Token Digest → SQLite

Klientautentisering verifierar den autentiserade token mot den registrerade klienten och kontrollerar dessutom relevant klienttillstånd.

Säkerhetsmodellen använder inte en käll-IP-adress som enda bevis på klientidentitet.

Detta gör att LUMS kan fungera i:

* privata laboratorienätverk
* isolerad infrastruktur
* NAT-baserade nätverk
* offline-miljöer
* nätverk där klientadresser kan ändras

Klienttokens kan roteras av behöriga administratörer.

En tokenrotation genererar en ersättningstoken, lagrar endast dess digest, ogiltigförklarar den tidigare token, registrerar den administrativa åtgärden i granskningsloggen och presenterar ersättningstoken en gång.

Klartextvärden för klienttokens skrivs inte till granskningsposter.

---

# Säkerhetsgranskning

Säkerhetsgranskningen utförs stegvis.

Varje granskningsområde granskas mot den faktiska implementeringen, följt av automatiserade tester, isolerad verifiering eller produktionsverifiering där det är tillämpligt.

Aktuella granskningsområden:

| Granskning | Område                                   | Status                    |
| ---------- | ---------------------------------------- | ------------------------- |
| #01        | SQLite Foreign Keys                      | PASS                      |
| #02        | SQLite Runtime Configuration             | PASS                      |
| #03        | Update Timeout Handling                  | PASS                      |
| #04        | Login Rate Limiting                      | PASS                      |
| #05        | API Input Validation                     | PASS                      |
| #06        | Session Revocation                       | PASS                      |
| #07        | Client Token Rotation                    | PASS                      |
| #08        | IP Address Handling / Offline Networks   | PASS                      |
| #09        | Job Recovery / Checkpointing             | PASS                      |
| #10        | APT Robustness                           | PASS                      |
| #11        | Arch Reboot Detection                    | PASS                      |
| #12        | Unit Tests / API Result Validation       | PASS                      |
| #13        | Simulation Tests                         | PASS                      |
| #14        | Continuous Integration                   | PASS                      |
| #15        | Application / Audit Logging              | PASS                      |
| #16        | Versioning / Releases                    | Kontrollera aktuella utgåvor och taggar i repositoryt |
| #17        | Role-Based Access Control                | PASS                      |

Den här granskningen behandlar versionshantering och utgåvor separat från de tekniska säkerhetskontrollerna. Tillgängligheten för utgåvor och Git-taggar kan ändras oberoende av den här dokumentationen. Kontrollera aktuell status på repositoryts [utgivningssida](https://github.com/NovaForgeCtrl/LUMS/releases) och bland [taggarna](https://github.com/NovaForgeCtrl/LUMS/tags).

Dokumentationens överensstämmelse med implementationen är ett löpande underhållsarbete, inte en separat numrerad säkerhetskontroll. Indexet över översatta guider finns i [`docs/README.md`](../../README.md).

# Säkerhetsgranskning #01

## SQLite Foreign Keys

SQLite-främmandenyckeltvingande är aktiverat för applikationens databasanslutningar.

Applikationen aktiverar uttryckligen:

`PRAGMA foreign_keys = ON`

Detta säkerställer att referentiell integritet upprätthålls för relationer mellan relaterade databasposter.

Granskningen verifierade:

* tvingande av främmandenycklar vid körning
* främmandenyckelintegritet
* klientlivscykelbeteende
* beteende vid inaktivering av klient
* bevarande av historisk jobbinformation
* bevarande av granskningsinformation

Klienttillstånd hanteras konservativt.

Där det är lämpligt inaktiveras klienter snarare än tas bort på ett sätt som skulle förstöra historisk operativ information.

**Status: PASS**

---

# Säkerhetsgranskning #02

## SQLite Runtime-konfiguration

Produktions-SQLite-databasen granskades för sin runtime-konfiguration.

Den verifierade produktionskonfigurationen är:

* `journal_mode`: `wal`
* `busy_timeout`: `5000`
* `synchronous`: `2`

Applikationen aktiverar uttryckligen:

`PRAGMA foreign_keys = ON`

Produktionsdatabasen använder för närvarande WAL-läge.

Databaskonfigurationen dokumenterades baserat på det faktiska verifierade produktionstillståndet snarare än den historiska utvecklingskonfigurationen.

Den konfigurerade busy-timeouten minskar omedelbara databasfel när en annan transaktion tillfälligt håller databasen.

Inställningen för främmandenycklar på applikationsnivå säkerställer referentiell integritet för varje databasanslutning.

Granskningen inkluderade produktionsverifiering av den aktiva SQLite-konfigurationen.

**Status: PASS**

---

# Säkerhetsgranskning #03

## Uppdateringstimeout och processhantering

Uppdateringsexekvering är skyddad mot oändligt blockerande pakethanterarprocesser.

Exekveringsflödet är:

Starta process
↓
Läs processutdata
↓
Övervaka timeout
↓
Timeout uppnådd?
↓
Avsluta process
↓
Karensperiod
↓
Processen körs fortfarande?
↓
Döda processen om det behövs
↓
Slutför jobbet

Implementeringen använder kontrollerad subprocesshantering så att tysta processer inte kan blockera oändligt medan de väntar på utdata.

Timeout-hantering testades mot:

* tysta processer
* normal processavslutning
* timeout-förhållanden
* processer som är motståndskraftiga mot normal avslutning
* kill-fallback
* timeout-beteende på integrationsnivå

Timeout-mekanismen förhindrar att en pakethanteringsoperation förblir oändligt i ett aktivt tillstånd.

Fel och timeout-förhållanden returneras som kontrollerade jobbresultat och registreras i jobbtillståndet.

Den aktuella dokumenterade LUMS Agent-versionen är:

`1.7.0`

**Status: PASS**

---

# Säkerhetsgranskning #04

## Inloggningshastighetsbegränsning

Administrativa inloggningsförsök är hastighetsbegränsade.

Den nuvarande eskaleringspolicyn är:

* 5 misslyckade försök → 30 sekunder
* 6 misslyckade försök → 60 sekunder
* 7 misslyckade försök → 120 sekunder
* 8 eller fler misslyckade försök → 300 sekunder

Hastighetsbegränsningstillståndet persistieras i SQLite.

Samtidiga inloggningsfel använder transaktionell databaslåsning med:

`BEGIN IMMEDIATE`

Detta förhindrar att samtidiga autentiseringsfel kringgår det avsedda hastighetsbegränsningstillståndet genom race conditions.

En framgångsrik autentisering rensar det tillämpliga feltillståndet.

Granskningen omfattade:

* isolerat hastighetsbegränsningsbeteende
* samtidiga autentiseringsfel
* transaktionsåterställning
* databaslåshanteringsbeteende
* återställningsbeteende vid lyckad inloggning
* granskningshändelser för hastighetsbegränsning
* produktionsinloggningsbeteende

Hastighetsbegränsaren tillhandahåller därför en kontroll på serversidan mot upprepade autentiseringsförsök snarare än att förlita sig på klientsidans beteende.

**Status: PASS**

---

# Granskningsstatus efter del 2

De fyra första säkerhetsgranskningsområdena är slutförda:

| Granskning | Område                              | Status |
| ---------- | ----------------------------------- | ------ |
| #01        | SQLite Foreign Keys                 | PASS   |
| #02        | SQLite Runtime Configuration        | PASS   |
| #03        | Update Timeout / Process Handling   | PASS   |
| #04        | Login Rate Limiting                 | PASS   |

Följande granskningsområden dokumenteras i efterföljande avsnitt:

* #05 API Input Validation
* #06 Session Revocation
* #07 Client Token Rotation
* #08 IP Address Handling / Offline Networks
* #09 Job Recovery / Checkpointing
* #10 APT Robustness
* #11 Arch Reboot Detection
* #12 Unit Tests / API Result Validation
* #13 Simulation Tests
* #14 Continuous Integration
* #15 Application / Audit Logging
* #16 Versioning / Releases
* #17 Role-Based Access Control

Dokumentationens överensstämmelse med implementationen är ett löpande underhållsarbete, inte en separat numrerad säkerhetskontroll. Indexet över översatta guider finns i [`docs/README.md`](../../README.md).

# Säkerhetsgranskning #05

## API-indatavalidering

LUMS validerar säkerhetskänslig API-indata på serversidan.

Klienttillhandahållna värden litas inte på bara för att de kommer från det autentiserade webbgränssnittet eller en registrerad klient.

Validering tillämpas på relevanta API-parametrar, inklusive:

* klientidentifierare
* paketnamn
* uppdateringsjobbåtgärder
* paketlistor
* sökparametrar
* användarhanteringsparametrar
* klienttokenoperationer
* jobbresultatdata

Paketnamn valideras innan de skickas till pakethanteringsoperationer.

Uppdateringsjobb-API:et accepterar endast uttryckligen stödda åtgärder.

De för närvarande stödda paketrelaterade åtgärderna är:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Oväntade åtgärder avvisas.

Paketlistor valideras före jobbskapande.

För `UPDATE_PACKAGE` måste det begärda paketet också finnas i klientens information om tillgängliga uppdateringar.

Databasfrågor använder parametriserad SQL snarare än att konstruera SQL-satser från obetrodd indata.

Detta förhindrar att användarkontrollerade värden tolkas som SQL-syntax.

Granskningen inkluderade negativ indatatesta och SQL-injektionsorienterade testfall.

Valideringskontrollerna verifierades också genom den automatiserade testsviten.

**Status: PASS**

---

# Säkerhetsgranskning #06

## Sessionsogiltigförklaring

LUMS skyddar autentiserade administrativa sessioner mot fortsatt användning efter utloggning.

Sessionshantering inkluderar:

* autentiserade sessioner på serversidan
* sessionens utgång
* sessionsregenerering
* ogiltigförklaring vid utloggning
* autentiseringskontroller på serversidan
* rollvalidering på serversidan

Utloggning ogiltigförklarar den aktiva autentiserade sessionen.

Skyddade API-slutpunkter kräver en autentiserad session och förlitar sig inte på klienttillstånd för att avgöra om användaren fortfarande är autentiserad.

Sessionstillståndet utvärderas därför av servern för skyddade operationer.

Tillståndsändrande webbläsarbegäranden kräver dessutom CSRF-skydd.

Granskningen verifierade att:

* autentiserad åtkomst fungerar normalt
* skyddade slutpunkter avvisar oautentiserade begäranden
* utloggning ogiltigförklarar den aktiva sessionen
* en tidigare autentiserad session inte kan fortsätta använda skyddad funktionalitet efter ogiltigförklaring
* rollinformation utvärderas på serversidan

**Status: PASS**

---

# Säkerhetsgranskning #07

## Klienttokenrotation

Varje hanterad LUMS-klient använder en individuell autentiseringstoken.

Klienttokens lagras inte som klartextvärden.

Istället lagrar LUMS SHA-256-hexdigesten av klienttoken.

Autentiseringsmodellen är:

`Authorization: Bearer <CLIENT_TOKEN>`

Servern hashar den tillhandahållna token och jämför den resulterande digesten med den registrerade klienttoken-digesten.

Behöriga administratörer kan rotera en klients token.

Tokenrotation utför följande operationer:

1. Generera en ersättningstoken.
2. Beräkna dess SHA-256-digest.
3. Ersätt den lagrade klienttoken-digesten.
4. Ogiltigförklara den tidigare token.
5. Registrera den administrativa åtgärden i granskningsloggen.
6. Presentera ersättningstoken för administratören.

Den tidigare token kan inte autentisera efter rotation.

Klartextvärden för token skrivs inte till granskningsloggar.

Granskningen verifierade:

* framgångsrik tokenautentisering
* lagring av token-digest
* tokenrotation
* ogiltigförklaring av den tidigare token
* autentisering med ersättningstoken
* auktoriseringskrav för tokenrotation
* granskningsloggning
* skydd mot obehörig rotation

Klienttokenrotation är begränsad till administratörer.

Operatorer och viewers kan inte rotera klienttokens.

**Status: PASS**

---

# Säkerhetsgranskning #08

## IP-adresshantering och offline-nätverk

LUMS använder inte en klients käll-IP-adress som enda bevis på klientidentitet.

Klientautentisering baseras på den registrerade klienttoken.

Denna design är avsiktlig eftersom hanterade klienter kan verka i miljöer där deras nätverksadress ändras.

Stödda distributionsscenarier inkluderar:

* privata laboratorienätverk
* NAT-baserade nätverk
* isolerad infrastruktur
* dynamiskt adresserade klienter
* offline-miljöer
* kontrollerade interna nätverk

Servern separerar därför:

**Nätverksplats**

från:

**Klientidentitet**

En giltig klienttoken identifierar den registrerade klienten.

Klientens nätverksadress kan fortfarande registreras för operativa och granskningsändamål, men den behandlas inte som en autentiseringsuppgift.

Implementeringen undviker också antaganden om att en klient måste vara nåbar från en fast adress.

Detta är särskilt viktigt för laboratoriemiljöer och infrastruktur där nätverkstopologin kan ändras utan att den logiska identiteten hos det hanterade systemet ändras.

Granskningen verifierade klientautentisering utan att förlita sig på en fast käll-IP-adress.

**Status: PASS**

---

# Granskningsstatus efter del 3

Följande säkerhetsgranskningsområden är slutförda:

| Granskning | Område                                   | Status |
| ---------- | ---------------------------------------- | ------ |
| #01        | SQLite Foreign Keys                      | PASS   |
| #02        | SQLite Runtime Configuration             | PASS   |
| #03        | Update Timeout / Process Handling        | PASS   |
| #04        | Login Rate Limiting                      | PASS   |
| #05        | API Input Validation                     | PASS   |
| #06        | Session Revocation                       | PASS   |
| #07        | Client Token Rotation                    | PASS   |
| #08        | IP Address Handling / Offline Networks   | PASS   |

Nästa avsnitt täcker:

* #09 Job Recovery / Checkpointing
* #10 APT Robustness
* #11 Arch Reboot Detection
* #12 Unit Tests / API Result Validation

# Säkerhetsgranskning #09

## Jobbåterställning och checkpoints

LUMS uppdateringsjobb är utformade för att återställas säkert från avbruten exekvering.

Uppdateringsjobb upprätthåller beständigt tillstånd i SQLite-databasen.

Individuella paketoperationer spåras separat från det övergripande jobbtillståndet.

Detta gör att Agenten kan avgöra vilka paketoperationer som redan har slutförts framgångsrikt innan ett avbrutet jobb återupptas.

Under återställning körs framgångsrikt slutförda paketoperationer inte igen.

Återställningslogiken följer därför principen:

`Persistent Job State → Determine Completed Work → Skip Completed Items → Continue Remaining Work`

Detta minskar risken för onödiga upprepade paketoperationer efter:

* agentavbrott
* processavslutning
* systemomstart
* tillfälligt kommunikationsfel
* containeromstart
* andra exekveringsavbrott

Granskningen verifierade återställning av avbrutna jobb och checkpoint-beteende.

Återställning testades med jobb som innehöll flera paketoperationer och med tidigare framgångsrika paketposter.

Granskningen bekräftade att slutfört arbete bevaras och att återstående arbete kan fortsätta utan att onödigtvis upprepa lyckade operationer.

**Status: PASS**

---

# Säkerhetsgranskning #10

## APT-robusthet

Debian-baserade paketoperationer utförs genom LUMS pakethanteringslager.

APT-relaterade uppdateringsoperationer granskades för tillförlitlig detektering av pakethanterarens tillstånd och uppdateringsresultat.

Implementeringen tar hänsyn till fall där pakethanteringskommandon kan returnera framgångsrikt men kräva ytterligare tolkning av deras utdata eller resulterande systemtillstånd.

APT-uppdateringsdetektering härdades för att undvika att förlita sig på ett enda förenklat kommando-utdatavillkor.

Granskningen inkluderade testning av:

* normala APT-operationer
* tillgängliga paketuppdateringar
* paketinstallation
* paketborttagning
* uppdateringsjobbsexekvering
* APT-resultathantering
* uppdateringsdetekteringsbeteende

Motsvarande härdning committades som:

`c76f331 security: harden apt update detection`

Målet är att säkerställa att LUMS inte felaktigt rapporterar pakethanteringstillstånd enbart baserat på ofullständig eller tvetydig kommando-utdata.

**Status: PASS**

---

# Säkerhetsgranskning #11

## Arch Linux omstartsdetektering

Arch Linux paketoperationer kan resultera i ett systemtillstånd där en omstart krävs eller rekommenderas.

LUMS utvärderar därför det resulterande systemtillståndet efter relevanta pakethanteringsoperationer.

Agenten skiljer mellan normal slutförande av paketoperationen och situationer där en omstart krävs.

Omstartstillståndet rapporteras tillbaka till LUMS-servern som en del av jobbresultatet.

Detta gör att hanteringsgränssnittet kan skilja mellan:

* framgångsrik paketoperation
* framgångsrik operation med omstartskrav
* misslyckad operation

Granskningen verifierade Arch Linux omstartsdetektering med den faktiska pakethanterarens exekveringsväg.

Implementeringen testades mot omstartskrävande förhållanden och normala slutförandeförhållanden.

**Status: PASS**

---

# Säkerhetsgranskning #12

## Enhetstester och API-resultatvalidering

Säkerhetskänsligt beteende täcks av automatiserade tester.

Testsviten inkluderar täckning för autentisering, auktorisering, API-validering, uppdateringsjobb, pakethantering, klientautentisering och resultathantering.

Agent-till-server-resultatvägen granskades specifikt för att säkerställa att jobbresultat inte godtyckligt kan ändra orelaterat servertillstånd.

Resultatbehandling validerar den inskickade informationen innan tillståndsändringar tillämpas på motsvarande uppdateringsjobb.

Valideringen täcker relevanta resultatfält och förväntade jobbrelationer.

Detta förhindrar att en autentiserad klient fritt väljer orelaterade jobb eller injicerar godtyckligt tillstånd i uppdateringsjobbdatabasen.

Säkerhetstestsviten täcker också negativa och obehöriga fall.

Kör den fullständiga automatiserade testsviten från repositoryts rot med
`./.venv-test/bin/pytest -q`. Antalet tester ändras över tid; använd resultatet av den aktuella körningen snarare än ett fast antal i detta dokument.

De relevanta säkerhetskontrollerna verifierades dessutom genom fokuserade testkörningar under granskningen.

**Status: PASS**

---

# Granskningsstatus efter del 4

Följande säkerhetsgranskningsområden är slutförda:

| Granskning | Område                                   | Status |
| ---------- | ---------------------------------------- | ------ |
| #01        | SQLite Foreign Keys                      | PASS   |
| #02        | SQLite Runtime Configuration             | PASS   |
| #03        | Update Timeout / Process Handling        | PASS   |
| #04        | Login Rate Limiting                      | PASS   |
| #05        | API Input Validation                     | PASS   |
| #06        | Session Revocation                       | PASS   |
| #07        | Client Token Rotation                    | PASS   |
| #08        | IP Address Handling / Offline Networks   | PASS   |
| #09        | Job Recovery / Checkpointing             | PASS   |
| #10        | APT Robustness                           | PASS   |
| #11        | Arch Reboot Detection                    | PASS   |
| #12        | Unit Tests / API Result Validation       | PASS   |

Nästa avsnitt täcker:

* #13 Simulation Tests
* #14 Continuous Integration
* #15 Application / Audit Logging
* #16 Versioning / Releases

# Säkerhetsgranskning #13

## Simuleringstester

LUMS tillhandahåller en simuleringsmekanism för att testa uppdateringshanteringsarbetsflöden utan att utföra motsvarande pakethanteringsoperation på det hanterade systemet.

Simulering implementeras på Agentens exekveringslager.

När simulering är aktiverad representeras och bearbetas pakethanteringsoperationer utan att den begärda paketändringen tillämpas på operativsystemet.

Detta gör att uppdateringsjobbets beteende kan testas utan att avsiktligt modifiera det hanterade systemet.

Simuleringstesterna täcker relevanta uppdateringshanteringsvägar, inklusive:

* paketinstallation
* paketborttagning
* paketuppdateringar
* systemuppdateringar
* jobbexekvering
* resultatrapportering
* framgångsrikt slutförande
* felhantering

Simuleringsmekanismen användes under säkerhetsgranskningen för att verifiera jobbskapande, Agent-exekvering, resultathantering och servertillståndsövergångar oberoende av verkliga paketändringar.

Simuleringsläge är en testmekanism och ersätter inte auktoriseringskontrollerna för normala uppdateringsoperationer.

**Status: PASS**

---

# Säkerhetsgranskning #14

## Kontinuerlig integration

LUMS använder automatiserad testning för att upptäcka säkerhets- och funktionella regressioner innan ändringar anses slutförda.

CI-processen kör den automatiserade testsviten mot projektet.

Testmiljön verifierar applikationen och säkerhetskänslig funktionalitet oberoende av produktionscontainern.

CI-processen inkluderar validering av:

* autentisering
* auktorisering
* RBAC
* API-beteende
* uppdateringsjobbhantering
* pakethanteringsbeteende
* klientautentisering
* jobbresultatvalidering
* säkerhetskänslig felhantering

CI-granskningen granskades efter säkerhetshärdningsändringarna.

Den slutliga verifierade testsviten slutfördes framgångsrikt.

Testantalet ändras när projektet utvecklas. CI tillhandahåller en automatiserad regressionsbarriär för säkerhetsrelevanta applikationsändringar.

**Status: PASS**

---

# Säkerhetsgranskning #15

## Applikations- och granskningsloggning

LUMS registrerar säkerhetskänsliga administrativa och operativa händelser genom granskningsloggning på applikationsnivå.

Granskningsloggning är utformad för att tillhandahålla en operativ historik utan att lagra känsliga autentiseringsuppgifter.

Relevanta säkerhetskänsliga åtgärder inkluderar händelser som:

* autentiseringsrelaterade säkerhetshändelser
* administrativa åtgärder
* klienthantering
* klienttokenoperationer
* skapande av uppdateringsjobb
* exekvering av uppdateringsjobb
* säkerhetsrelevanta fel

Känsligt autentiseringsmaterial utesluts från granskningsposter.

I synnerhet:

* lösenord loggas inte
* klartext klienttokens loggas inte
* hemliga värden skrivs inte avsiktligt till granskningsposter

Granskningsposter associeras med relevant administrativ eller operativ kontext där det är tillämpligt.

Implementeringen av granskningsloggning granskades för:

* täckning av säkerhetskänsliga händelser
* uteslutning av autentiseringsuppgifter
* administrativ spårbarhet
* felhantering
* persistens av relevant granskningsinformation

Loggsystemet är avsett att stödja både operativ felsökning och säkerhetsutredning.

**Status: PASS**

---

# Säkerhetsgranskning #16

## Versionshantering och utgåvor

Versionshantering och utgåvor ingår i säkerhetsgranskningen eftersom operatörer måste kunna identifiera exakt vilken kod och vilka artefakter de distribuerar. Tillgängligheten för utgåvor och komponentversioner ändras oberoende av den här guiden. Kontrollera repositoryts [aktuella taggar](https://github.com/NovaForgeCtrl/LUMS/tags) och [utgivningssida](https://github.com/NovaForgeCtrl/LUMS/releases), och granska versionsmetadata i den exakta källrevision som ska distribueras. Behandla inte det här dokumentet som en aktuell katalog över utgåvor.

De komponentversioner som dokumenteras här är LUMS Agent `1.7.0` och LUMS Watcher `1.2.1`.

Den planerade utgivningsprocessen är:

1. Slutför implementeringsarbetet.
2. Slutför säkerhetsgranskningen.
3. Granska och synkronisera dokumentationen.
4. Slutför hela den automatiserade testsviten.
5. Verifiera CI.
6. Fastställ utgåvans version.
7. Skapa motsvarande Git-tagg.
8. Publicera GitHub-utgåvan.
9. Bevara utgåvan som dokumenterad baslinje.

En officiell utgåva skapas inte enbart för att säkerhetsgranskningen når ett visst granskningsnummer.

---

# Granskningsstatus efter del 5

Följande säkerhetsgranskningsområden är slutförda:

| Granskning | Område                                   | Status                    |
| ---------- | ---------------------------------------- | ------------------------- |
| #01        | SQLite Foreign Keys                      | PASS                      |
| #02        | SQLite Runtime Configuration             | PASS                      |
| #03        | Update Timeout / Process Handling        | PASS                      |
| #04        | Login Rate Limiting                      | PASS                      |
| #05        | API Input Validation                     | PASS                      |
| #06        | Session Revocation                       | PASS                      |
| #07        | Client Token Rotation                    | PASS                      |
| #08        | IP Address Handling / Offline Networks   | PASS                      |
| #09        | Job Recovery / Checkpointing             | PASS                      |
| #10        | APT Robustness                           | PASS                      |
| #11        | Arch Reboot Detection                    | PASS                      |
| #12        | Unit Tests / API Result Validation       | PASS                      |
| #13        | Simulation Tests                         | PASS                      |
| #14        | Continuous Integration                   | PASS                      |
| #15        | Application / Audit Logging              | PASS                      |
| #16        | Versioning / Releases                    | Kontrollera aktuella utgåvor och taggar i repositoryt |

Det återstående numrerade tekniska granskningsområdet är:

* #17 Role-Based Access Control

Dokumentationens överensstämmelse med implementationen är ett löpande underhållsarbete, inte en separat numrerad säkerhetskontroll. Indexet över översatta guider finns i [`docs/README.md`](../../README.md).

# Säkerhetsgranskning #17

## Rollbaserad åtkomstkontroll

LUMS kombinerar rollmallar med individuellt tilldelade behörigheter. De
stödda mallarna är `administrator`, `operator` och `viewer`; att välja en
mall väljer dess standardbehörigheter, som en administratör kan anpassa
för varje konto.

Rollen förblir kontometadata. Skyddade rutter auktoriserar mot kontots
serverlagrade behörighetsuppsättning, inte mot rolletiketten. Gränssnittet döljer
otillgängliga funktioner för användbarhet, medan servern förblir säkerhetsgränsen.

---

## RBAC-behörighetsmodell

| Behörighet        | Åtkomst beviljad |
| ----------------- | ---------------- |
| `clients.view`    | Visa klienter och systeminformation |
| `software.view`   | Visa installerad programvara |
| `updates.view`    | Visa tillgängliga uppdateringar, jobb och historik |
| `packages.search` | Sök i paketförråd |
| `jobs.manage`     | Skapa paketoperationer och uppdateringsjobb |
| `clients.manage`  | Registrera/ta bort klienter och rotera klienttokens |
| `users.manage`    | Skapa användare och hantera roller och behörigheter |

Standardrollmallarna är:

| Mall            | Standardbehörigheter |
| --------------- | -------------------- |
| `administrator` | Alla behörigheter |
| `operator`      | Klient-/programvaru-/uppdateringssynlighet, paketsökning och jobbhantering |
| `viewer`        | Klientsynlighet och synlighet för installerad programvara |

Klientrelaterade behörigheter kräver `clients.view`. `jobs.manage` kräver också
`updates.view`. Gränssnittet laddar behörigheter för det autentiserade kontot och
utelämnar kontroller som användaren inte kan använda; kontroller på serversidan upprätthåller oberoende
samma beviljanden.

---

## Auktoriseringstillämpning

Skyddade operationer använder autentisering och behörighetskontroller på serversidan.

Auktoriseringsmodellen följer principen:

`Authenticate → Load User Permissions → Authorize Operation → Execute`

Autentisering ensam är inte tillräcklig för att komma åt privilegierade operationer.

Tillståndsändrande operationer kräver dessutom CSRF-skydd där det är tillämpligt.

Exempel på skyddade administrativa operationer inkluderar:

* skapande av uppdateringsjobb
* paketinstallation
* paketborttagning
* paketuppdateringar
* systemuppdateringar
* pakethanteringsoperationer
* klientskapande
* klientinaktivering
* klienttokenrotation
* användarskapande
* användarhanteringsfunktioner

Skyddade slutpunkter definierar uttryckligen den behörighet som krävs för
motsvarande operation.

En saknad behörighet avvisas av servern även om användaren manuellt
konstruerar motsvarande HTTP-begäran.

Detta förhindrar att RBAC-modellen kringgås genom att direkt anropa en API-slutpunkt som är dold i webbgränssnittet.

---

## Viewer-begränsningar

Viewer-mallen är avsiktligt begränsad av sin standardbehörighetsuppsättning.

För konton utan motsvarande beviljanden exponerar klientgränssnittet inte:

* Uppdateringar
* Uppdateringsjobb
* Uppdateringshistorik
* Pakethantering
* Systemunderhåll

Servern förhindrar dessutom konton utan motsvarande beviljanden
från att utföra skyddade operationer.

JavaScript-gränssnittet laddar inte uppdateringshanteringsdata utan
`updates.view`.

Detta minskar onödig exponering av operativ information samtidigt som auktorisering på serversidan bibehålls som den faktiska säkerhetskontrollen.

Installerad programvara förblir tillgänglig för Viewer-konton som en skrivskyddad informationsfunktion.

---

## Administrativ användarhantering

Användarhantering kräver behörigheten `users.manage`.

Användare med den behörigheten kan skapa konton utan behörigheter och sedan
tilldela individuella beviljanden eller tillämpa en rollmall i behörighetsredigeraren.
Rollmallar har beskrivningar som förklarar deras standardbeviljanden.

Behöriga användarhanterare kan spara en intern anteckning per konto. Anteckningar är
begränsade till 2 000 tecken, ingår inte i granskningsloggens detaljer och
är inte synliga för kontoinnehavaren.

Användarskapande inkluderar:

* användarnamnsvalidering
* rollvalidering
* lösenordsvalidering
* Argon2-lösenordshashning
* dubblettanvändardetektering
* granskningsloggning
* CSRF-skydd
* auktorisering på serversidan

Användarhanteringsslutpunkter är inte tillgängliga utan `users.manage`.

Servern avvisar okända behörigheter och ogiltiga beroendekombinationer.
Minst ett aktivt konto måste behålla `users.manage`; ändringar som skulle
ta bort den sista användarhanteraren avvisas.

Lösenord lagras aldrig i klartext.

---

## RBAC-databasmigrering

Rollmallsinformation finns kvar i användardatabasposten. Individuella
beviljanden lagras i tabellen `user_permissions` med en främmande nyckel till
användarkontot. Migrering `003-user-permissions` skapar den tabellen och seedar
befintliga konton från deras nuvarande rollmall, vilket bevarar deras åtkomst
under övergången. Migrering `004-user-admin-notes` lägger till det privata
fältet `users.admin_note`; befintliga konton får en tom anteckning. Migrering
`005-backup-permission` beviljar `backups.manage` till befintliga Administrator-
konton.

Skapande av databassäkerhetskopior kräver `backups.manage`; Administrator-
mallen inkluderar denna behörighet som standard. Servern skriver SQLite online-
säkerhetskopior endast till den serverkonfigurerade `LUMS_BACKUP_DIR`; den accepterar
inte filsystemsökvägar från webbläsaren. Säkerhetskopiefiler skapas med endast ägarbehörigheter
och integritetskontrolleras före publicering.

---

## RBAC-säkerhetstestning

RBAC-beteende täcks av automatiserade tester.

Testerna inkluderar:

* Administratorauktorisering
* Operatorauktorisering
* Viewer-begränsningar
* skyddad API-åtkomst
* obehöriga operationer
* klienthanteringsbegränsningar
* uppdateringsjobb begränsningar
* användarhanteringsbegränsningar
* klientsidans synlighet
* behörighetsspecifikt gränssnittsbeteende

RBAC-tester täcker rollmallars standardvärden, anpassade behörigheter, behörighetsberoenden
och auktorisering på serversidan. Produktionsverifiering bör
inkludera konton med anpassade behörigheter såväl som standardmallarna
Administrator, Operator och Viewer.

---

## RBAC-säkerhetsresultat

RBAC-implementeringen tillhandahåller skiktad auktorisering:

1. Autentisering fastställer användarens identitet.
2. Servern laddar användarens behörigheter.
3. Skyddade rutter upprätthåller den nödvändiga behörigheten.
4. CSRF-skydd tillämpas på relevanta webbläsartillståndsändringar.
5. Webbgränssnittet döljer otillgänglig funktionalitet.
6. Automatiserade tester verifierar auktoriseringsgränser.

Gränssnittet tillhandahåller därför inte auktoriseringsmekanismen i sig.

Servern förblir den auktoritativa säkerhetsgränsen.

**Status: PASS**

## Dokumentationsgranskning

Säkerhetsdokumentationen granskas mot det för närvarande implementerade LUMS-systemet.

Syftet med denna granskning är att säkerställa att säkerhetsdokumentationen beskriver den faktiska implementeringen snarare än ett tidigare utvecklingstillstånd.

Granskningen omfattar:

* autentisering
* auktorisering
* RBAC
* klientautentisering
* tokenhantering
* sessionshantering
* CSRF-skydd
* hastighetsbegränsning
* SQLite-konfiguration
* uppdateringsexekvering
* jobbåterställning
* pakethantering
* containerhärdning
* nätverksexponering
* hemlighetshantering
* beroende- och byggsäkerhet
* filsystemsbehörigheter
* applikations- och granskningsloggning
* versionshantering och releasehantering
* automatiserad säkerhetstestning

Dokumentationen måste skilja mellan:

* implementerade kontroller
* verifierat produktionsbeteende
* planerade förbättringar
* avsiktligt öppna projektbeslut

Historiska implementeringsdetaljer får inte presenteras som aktuell produktionskonfiguration.

I synnerhet återspeglar dokumentationen den aktuella SQLite-produktionskonfigurationen snarare än den aktuella WAL-konfigurationen.

Den aktuella produktionskörtiden dokumenteras som:

* `journal_mode = wal`
* `busy_timeout = 5000`
* `synchronous = 2`
* applikationsnivå `PRAGMA foreign_keys = ON`

Det aktuella Viewer-RBAC-beteendet dokumenteras också enligt det implementerade produktionsgränssnittet.

Viewer-användare har åtkomst till:

* klientinformation
* installerad programvara

Viewer-användare har inte åtkomst till:

* Uppdateringar
* Uppdateringsjobb
* Uppdateringshistorik
* Pakethantering
* Systemunderhåll

Dokumentationsgranskningen tar också bort eller ersätter föråldrade referenser till tidigare testantal, migreringstillstånd, distributionskonfigurationer och endast utvecklingsbeteende.


---

# Ytterligare säkerhetshärdning

Den numrerade säkerhetsgranskningen täcker de primära applikationssäkerhetskontrollerna.

Ytterligare härdning utfördes efter den ursprungliga granskningssekvensen och är en del av den aktuella säkerhetsbaslinjen.

Dessa kontroller dokumenteras här eftersom de representerar viktiga säkerhetsegenskaper hos den aktuella distributionen.

---

## Containerhärdning

Produktionscontainern för LUMS körs med en härdad Docker-konfiguration.

Produktionscontainern använder:

* icke-root applikationsanvändare
* skrivskyddat rotfilsystem
* borttagna Linux-kapabiliteter
* `no-new-privileges`
* begränsade temporära filsystem
* skrivskyddad hemlig montering
* dedikerad beständig applikationsdatavolym
* omstartspolicy
* loopback-endast värdpublicering av applikationsporten

Applikationens rotfilsystem är därför inte skrivbart under normal drift.

Skrivbara platser är uttryckligen begränsade till de platser som krävs av applikationen.

Produktionscontainern inspekterades oberoende för att verifiera den effektiva runtime-konfigurationen.

Den härdade körtiden testades också genom att verifiera att:

* applikationens filsystemsskrivningar misslyckas
* `/tmp` förblir tillgängligt där det krävs
* `/var/lib/lums` förblir skrivbart
* den hemliga filen förblir skrivskyddad
* applikationen förblir operativ

---

## Nätverksexponering

LUMS applikationsport är inte direkt exponerad mot LAN.

Docker-applikationsporten är bunden till loopback-gränssnittet:

`127.0.0.1:5050`

Extern åtkomst tillhandahålls via Nginx.

Produktionsvärden exponerar de avsedda nätverkstjänsterna genom brandväggen och den omvända proxyn.

Distributionen verifierades för att förhindra direkt fjärråtkomst till den interna Docker-applikationsporten.

Brandväggen använder en default-deny-modell för inkommande och routad trafik.

De avsedda externt nåbara tjänsterna är:

* SSH
* HTTP
* HTTPS

HTTP-begäranden omdirigeras till HTTPS av webbservern.

Standardwebbplatsen för Nginx togs bort så att orelaterat standardinnehåll inte exponeras.

---

## Transportskydd

Administrativ webbåtkomst tillhandahålls via HTTPS.

HTTP omdirigeras till HTTPS.

TLS-slutpunkten hanteras av Nginx snarare än Flask/Gunicorn-applikationen direkt.

Detta håller transportskydd och applikationsservering separerade.

Den interna Gunicorn-applikationsporten är därför inte avsedd att vara en offentlig HTTP-slutpunkt.

Den nuvarande distributionen är avsedd för kontrollerad intern infrastruktur.

En framtida distribution med direkt public-Internet-exponering skulle kräva ytterligare en säkerhetsgranskning.

---

## Hemligheter och konfiguration

Produktionshemligheter lagras inte i applikationens källträd.

LUMS hemliga nyckel tillhandahålls genom en skyddad hemlig fil.

Produktionscontainern tar emot hemligheten genom:

`/run/secrets/lums_secret`

Den hemliga filen monteras skrivskyddad.

Applikationen läser hemligheten genom den konfigurerade hemliga filmekanismen.

Repository- och Docker-byggkontexthantering granskades för att förhindra oavsiktlig inkludering av:

* databasfiler
* säkerhetskopiefiler
* hemliga filer
* privata nycklar
* certifikat
* runtime-loggar
* lokala säkerhetskopieartefakter

Repositoryt ignorerar också vanliga tillfälliga säkerhetskopieringsmönster som används under utveckling.

---

## Beroende- och byggsäkerhet

Produktions-Docker-avbildningen använder en fastställd Python-basavbildningssammanfattning.

Produktionsruntime-beroendena är uttryckligen versionsfästa.

Den aktuella produktionsberoendeuppsättningen inkluderar:

* Flask `3.1.3`
* argon2-cffi `25.1.0`
* Gunicorn `23.0.0`

Docker-byggkontexten begränsas genom `.dockerignore`.

Upprepade produktionsbyggen jämfördes under granskningen.

Relevant beroende- och paketmetadata förblev konsekvent mellan upprepade byggen, förutom förväntade skillnader i genererad Python-bytekod.

Detta ger en reproducerbar baslinje för produktionsavbildningen samtidigt som byggkontexten hålls begränsad.

---

## Filsystem- och runtime-behörigheter

Produktionsapplikationen körs som den dedikerade användaren `lums` snarare än root.

Beständig applikationsdata lagras i den dedikerade LUMS-datavolymen.

Applikationens rotfilsystem är skrivskyddat.

Runtime-skrivåtkomst är begränsad till uttryckligen nödvändiga platser.

Produktionskörtiden verifierades för att avvisa obehöriga skrivningar till applikationens filsystem.

Detta minskar påverkan av oavsiktlig eller skadlig filändring inuti applikationscontainern.

---

# Slutsats av säkerhetsgranskning

Den nuvarande LUMS-implementeringen har genomgått en bred säkerhetsgranskning som täcker:

* autentisering
* auktorisering
* RBAC
* sessionssäkerhet
* CSRF-skydd
* inloggningshastighetsbegränsning
* klienttokensäkerhet
* API-validering
* SQL-injektionsmotstånd
* SQLite-integritet
* uppdateringsexekvering
* timeout-hantering
* jobbåterställning
* pakethanterarens robusthet
* resultatvalidering
* simulering
* kontinuerlig integration
* granskningsloggning
* containerhärdning
* nätverksexponering
* transportskydd
* hemlighetshantering
* filsystemsbehörigheter
* beroende- och byggsäkerhet

De numrerade granskningsresultaten är:

| Granskning | Område                                   | Status                    |
| ---------- | ---------------------------------------- | ------------------------- |
| #01        | SQLite Foreign Keys                      | PASS                      |
| #02        | SQLite Runtime Configuration             | PASS                      |
| #03        | Update Timeout / Process Handling        | PASS                      |
| #04        | Login Rate Limiting                      | PASS                      |
| #05        | API Input Validation                     | PASS                      |
| #06        | Session Revocation                       | PASS                      |
| #07        | Client Token Rotation                    | PASS                      |
| #08        | IP Address Handling / Offline Networks   | PASS                      |
| #09        | Job Recovery / Checkpointing             | PASS                      |
| #10        | APT Robustness                           | PASS                      |
| #11        | Arch Reboot Detection                    | PASS                      |
| #12        | Unit Tests / API Result Validation       | PASS                      |
| #13        | Simulation Tests                         | PASS                      |
| #14        | Continuous Integration                   | PASS                      |
| #15        | Application / Audit Logging              | PASS                      |
| #16        | Versioning / Releases                    | Kontrollera aktuella utgåvor och taggar i repositoryt |
| #17        | Role-Based Access Control                | PASS                      |

De tekniska säkerhetskontrollerna som granskades i granskningarna #01–#15 och #17 klarade de dokumenterade kontrollerna. Resultaten är ingen certifiering och ingen garanti för senare revisioner.

Tillgängligheten för utgåvor och taggar kan ändras; kontrollera repositoryts aktuella [utgivningssida](https://github.com/NovaForgeCtrl/LUMS/releases) och [taggar](https://github.com/NovaForgeCtrl/LUMS/tags).

Inget resultat av säkerhetsgranskningen bör tolkas som en garanti för att LUMS är fritt från sårbarheter.

Säkerhet är en pågående process.

Ändringar i applikationen, Agenten, beroenden, containerkonfiguration, nätverksexponering, autentiseringsmodell eller distributionsarkitektur bör utlösa ytterligare en säkerhetsgranskning av de påverkade kontrollerna.

---

# Säkerhetsbaslinje

Den här baslinjen beskriver kontroller som konfigurerats i källkoden och distributionsvägledningen. Den bevisar inte att en viss installation tillämpar dem; verifiera de faktiska inställningarna i målmiljön.

Baslinjen inkluderar:

* autentisering på serversidan
* RBAC på serversidan
* Argon2-lösenordshashning
* SHA-256 klienttoken-digester
* CSRF-skydd
* inloggningshastighetsbegränsning
* parametriserad SQL
* validerad API-indata
* kontrollerad pakethanterarexekvering
* uppdateringsjobbåterställning
* granskningsloggning
* härdad Docker-runtime
* HTTPS via Nginx
* loopback-endast applikationsportexponering
* brandväggsbegränsningar
* skyddade produktionshemligheter
* fästa produktionsberoenden
* begränsade filsystemsbehörigheter
* automatiserad säkerhetstestning

Framtida ändringar bör bevara dessa egenskaper om inte en avsiktlig arkitektonisk ändring ersätter dem med en likvärdig eller starkare kontroll.

---

# Säkerhetsunderhåll

Säkerhetskontroller bör omvalideras när betydande ändringar införs.

Exempel inkluderar:

* autentiseringsändringar
* nya användarroller
* nya API-slutpunkter
* pakethanteringsändringar
* Agent-exekveringsändringar
* databasmigreringar
* beroendeuppdateringar
* Dockerfile-ändringar
* container-runtime-ändringar
* omvänd proxy-ändringar
* brandväggsändringar
* hemlighetshanteringsändringar
* releaseförberedelse

Säkerhetstestning bör utföras innan en officiell release publiceras.

Säkerhetsdokumentationen bör uppdateras när den verifierade säkerhetsbaslinjen ändras.

---

# Releaseberedskap

Den första officiella LUMS-releasen skapas endast efter:

1. implementeringsarbetet är slutfört
2. säkerhetsgranskningen är slutförd
3. dokumentationsgranskningen är slutförd
4. den fullständiga automatiserade testsviten passerar
5. CI passerar
6. den slutliga versionen definieras
7. Git-taggen skapas
8. GitHub-releasen publiceras

Fram till dess förblir LUMS ett aktivt utvecklat projekt.

---

# Slutlig förklaring

LUMS är utformat som en kontrollerad Linux-uppdateringshanteringsplattform med säkerhet som en central arkitektonisk angelägenhet.

Säkerhetsmodellen förlitar sig inte på en enda skyddsmekanism.

Istället arbetar autentisering, auktorisering, validering, kontrollerad exekvering, persistens, återställning, loggning, containerisolering, nätverksbegränsningar och automatiserad testning tillsammans som skiktade kontroller.

Projektet föredrar avsiktligt explicit upprätthållande på serversidan framför säkerhet-genom-gränssnitt.

Den aktuella säkerhetsbaslinjen dokumenteras enligt det verifierade implementeringstillståndet snarare än historiskt utvecklingsbeteende.

---

**LUMS — Linux Update Management utan bruset.**

`segfault // override`
