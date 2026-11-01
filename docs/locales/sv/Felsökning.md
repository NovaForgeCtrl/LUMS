# LUMS Felsökning

Den här guiden beskriver felsökningsprocedurer för LUMS-servern, Linux-agenter, exekveringswatchern, uppdateringsjobb, autentisering, pakethantering, databasen och Docker-distribution.

Felsökningsprocessen ska alltid börja med **observation före ändring**.

Målet är att identifiera den första komponenten där det förväntade beteendet upphör, utan att i onödan ändra konfiguration, databastillstånd, autentiseringsuppgifter eller säkerhetskontroller.

---

## Kom igång: Felsök säkert

Om du är ny på Linux innebär ett fel inte automatiskt att data har gått förlorad. Ändra inte flera saker samtidigt. Börja med kontrollerna nedan och notera **när** problemet inträffar och **vilken åtgärd** som hände omedelbart före det.

### Första kontroller på LUMS-servern

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

docker ps -a visar även stoppade containrar. docker logs läser senaste applikationsmeddelanden. systemctl status visar om Nginx körs; nginx -t kontrollerar dess konfiguration utan att ändra den. Om nginx -t misslyckas ska du inte ladda om Nginx förrän orsaken har åtgärdats.
Första kontroller på en hanterad klient

```bash
sudo systemctl status lums-agent.service --no-pager
sudo journalctl -u lums-agent.service -n 100 --no-pager
sudo systemctl status lums-agent-watcher.service --no-pager
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager
```

Agenten och Watchern är separata tjänster: en lyckad Agent-rapport bevisar inte att Watchern kan köra uppdateringsjobb. För en oneshot-tjänst kan inactive vara normalt efter en lyckad körning; kontrollera även resultatet och loggmeddelandena.
Innan du delar kommandoutdata

Kontrollera loggar och konfiguration för lösenord, klienttoken, sessions- eller API-nycklar, privata nycklar och personuppgifter. Dela aldrig innehållet i hemliga filer eller fullständiga miljövariabelvärden. Om du behöver hjälp, dela endast relevanta felmeddelanden efter att du tagit bort känslig information.

Börja inte med att radera databasen eller Docker-volymen, köra containern som privilegierad, inaktivera säkerhetsalternativ, ta bort pakethanterarens låsfiler eller rotera tokens. Dessa åtgärder kan skada data, radera bevis eller förvärra problemet. Om en kontroll misslyckas, spara dess utdata och fortsätt till relevant avsnitt nedan.
# 1. Felsökningsfilosofi

LUMS består av flera oberoende komponenter.

En lyckad klientrapport innebär inte automatiskt att uppdateringsexekvering fungerar.

Den huvudsakliga operativa vägen är:
text

Linux-klient
```text
    │
    ├── LUMS Agent
    │
    └── Execution Watcher
            │
            ▼
          HTTPS
            │
            ▼
        Nginx
            │
            ▼
        LUMS API
            │
            ▼
         SQLite
```

Uppdateringsexekvering lägger till pakethanteringslagret:
text

Webbläsare
```text
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Uppdateringsjobb
   │
   ▼
Execution Watcher
   │
   ▼
LUMS Agent
   │
   ▼
APT / pacman
   │
   ▼
Resultat
   │
   ▼
LUMS API
   │
   ▼
SQLite
```

När du felsöker, identifiera den första felande komponenten.

Till exempel:
text

Agent-rapport misslyckas
* ↓
Kontrollera agenttjänsten
* ↓
Kontrollera nätverket
* ↓
Kontrollera TLS
* ↓
Kontrollera klienttoken
* ↓
Kontrollera LUMS API

Gör inte omedelbart följande:

* ändra databasen

* radera Docker-volymen

* installera om Agenten

* rotera autentiseringsuppgifter

* ta bort pakethanterarens låsfiler

* inaktivera säkerhetskontroller

* göra containern privilegierad

Dessa åtgärder kan förstöra användbar diagnostisk information eller skapa ytterligare problem.
# 2. Diagnostisk baslinje

Innan du undersöker ett specifikt problem, fastställ det aktuella tillståndet för huvudkomponenterna.

Produktionsdistributionen av LUMS använder:
text

Applikationsport: 127.0.0.1:5050
Extern åtkomst: HTTPS via Nginx
Databas: /var/lib/lums/lums.db
Docker-volym: lums-data
```text
Agent: 1.7.0
Watcher: 1.2.1
```

Produktionscontainern är härdad med:
text

Skrivskyddat rotfilsystem
Inga Linux-kapabiliteter
no-new-privileges
Icke-root applikationsanvändare
Skyddad hemlig montering
Dedikerad beständig datavolym

Applikationsporten är avsiktligt bunden endast till den lokala värden.

Den förväntade nätverksvägen är:
text

Klient / Webbläsare
```text
       │
       ▼
     HTTPS
       │
       ▼
    Nginx :443
       │
       ▼
127.0.0.1:5050
       │
       ▼
 Docker-container
       │
       ▼
    LUMS :5000
```

# 3. Första diagnostiska kontroller
3.1 Kontrollera LUMS-containern

På LUMS-servern:

```bash
sudo docker ps
```

Containern lums ska köra.

För en fullständig containeröversikt:

```bash
sudo docker ps -a \
    --filter name=lums
```

Ta inte bort stoppade containrar innan du undersökt dem.

Äldre reservcontainrar kan innehålla användbar information när du undersöker ett distributionsproblem.
3.2 Kontrollera senaste applikationsloggar

Inspektera de senaste LUMS-loggarna:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

För live-utdata:

```bash
sudo docker logs \
    -f \
    lums
```

När du undersöker en specifik begäran eller ett jobb, starta logginspektionen innan du återskapar problemet där det är möjligt.

Det gör det lättare att korrelera klientåtgärden med motsvarande händelse på serversidan.
3.3 Kontrollera Nginx

Kontrollera omvänd proxy:

```bash
sudo systemctl status nginx \
    --no-pager
```

Validera konfigurationen:

```bash
sudo nginx -t
```

Ett lyckat konfigurationstest ska rapportera:

```text
syntax is ok
test is successful
```

Om Nginx inte körs kommer HTTPS-åtkomst till LUMS normalt att misslyckas även om Docker-containern själv är frisk.
3.4 Kontrollera Agenten

På en hanterad Linux-klient:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Inspektera senaste Agent-utdata:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

För en Type=oneshot-tjänst kan ett inaktivt tillstånd efter en lyckad körning vara normalt.

Den viktiga informationen är körningsresultatet.

En lyckad körning ska sluta med:

```text
status=0/SUCCESS
```

3.5 Kontrollera Execution Watcher

Watchern är en separat komponent från rapporterande Agent.

Kontrollera den oberoende:

```bash
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Inspektera senaste utdata:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

En lyckad Agent-rapport bevisar därför inte att exekveringswatchern fungerar korrekt.
3.6 Kontrollera LUMS-timers

Kontrollera alla relevanta timers:

```bash
sudo systemctl list-timers \
    --all | grep lums
```

De förväntade timers inkluderar Agentens och watcherns schemaläggningsmekanismer.

Om en timer saknas eller är inaktiv, inspektera motsvarande enhet innan du ändrar något.
# 4. LUMS-containern körs inte

Om containern lums inte körs ska du inte omedelbart återskapa den.

Inspektera först dess tillstånd:

```bash
sudo docker ps -a \
    --filter name=lums
```

Inspektera sedan containern:

```bash
sudo docker inspect lums
```

Kontrollera de senaste loggarna:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Kontrollera utgångstillståndet:

```bash
sudo docker inspect \
    --format '{{.State.Status}} {{.State.ExitCode}}' \
    lums
```

Resultatet kan hjälpa till att skilja mellan:
text

Normal avstängning
Applikationsfel
Konfigurationsfel
Container runtime-fel
Hälsa-/startproblem

Om containern avslutades oväntat, bevara loggarna och containertillståndet innan du ersätter den.
# 5. Containern startar men LUMS går inte att nå

LUMS-applikationen är inte avsedd att nås direkt via Docker-applikationsporten från nätverket.

Produktionsapplikationen är bunden till:

```text
127.0.0.1:5050
```

Verifiera portbindningen:

```bash
sudo docker port lums
```

Kontrollera även värdens lyssnare:

```bash
sudo ss -lntp | grep -E ':443|:5050'
```

Den förväntade arkitekturen är:

```text
HTTPS :443
    │
    ▼
  Nginx
    │
    ▼
127.0.0.1:5050
    │
    ▼
Docker
    │
    ▼
LUMS :5000
```

Om containern körs men HTTPS misslyckas, undersök lagren individuellt:

* Docker-container

* Lokal applikationsport

* Nginx-konfiguration

4. TLS

* Brandvägg/nätverksväg

Exponera inte port 5050 offentligt som en felsökningsgenväg.
# 6. Nginx returnerar ett fel

Kontrollera tjänsten:

```bash
sudo systemctl status nginx \
    --no-pager
```

Validera konfigurationen:

```bash
sudo nginx -t
```

Inspektera senaste Nginx-meddelanden:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Verifiera sedan att LUMS-containern faktiskt körs:

```bash
sudo docker ps
```

Ett omvänd proxy-fel innebär inte automatiskt att LUMS-applikationen själv är trasig.

Möjliga felplatser inkluderar:
text

Webbläsare
```text
   ↓
TLS
   ↓
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker
   ↓
LUMS
```

Testa lagren separat istället för att ändra flera komponenter samtidigt.
# 7. HTTPS / TLS-problem

Testa först HTTPS-slutpunkten:

```bash
curl -I https://LUMS-SERVER/
```

Om certifikatverifiering misslyckas, avgör om problemet är:
text

Certifikat
Certifikatkedja
Värdnamn
Trust store
Nginx-konfiguration
Klient-CA-konfiguration

Validera Nginx:

```bash
sudo nginx -t
```

Om certifikatet eller TLS-konfigurationen avsiktligt ändrades, ladda om Nginx:

```bash
sudo systemctl reload nginx
```

Testa sedan igen:

```bash
curl -I https://LUMS-SERVER/
```

Klienter som använder en privat certifikatutfärdare måste lita på lämpligt CA-certifikat.

Inaktivera inte TLS-certifikatverifiering som en permanent lösning.

Ett lyckat anslutningstest som kringgår certifikatvalidering bevisar inte att produktions-TLS-konfigurationen är korrekt.
# 8. Agenttjänsten misslyckas

Kontrollera tjänsten:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Läs den senaste journalen:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Starta tjänsten igen endast efter att ha inspekterat det tidigare resultatet:

```bash
sudo systemctl start \
    lums-agent.service
```

Kontrollera sedan:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

och:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Leta efter:
text

Konfigurationsfel
Saknade miljövärden
TLS-fel
Autentiseringsfel
API-fel
Python-undantag
Pakethanteringsfel

Installera inte om Agenten bara för att en enskild körning misslyckades.
# 9. Agenten rapporterar att LUMS_TOKEN saknas

Agenten får normalt sin produktionskonfiguration via sin systemd-tjänstemiljö.

Om Agenten startas manuellt från ett skal laddas systemd EnvironmentFile inte automatiskt in i det skalet.

Därför:

```bash
sudo /opt/lums-agent/agent.py --version
```

kan bete sig annorlunda än:

```bash
sudo systemctl start \
    lums-agent.service
```

när token endast tillhandahålls via systemd-konfiguration.

När du undersöker autentiseringsproblem, testa den faktiska tjänsten först:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspektera sedan:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Kopiera inte produktions-tokens till skalkommandon i onödan.

Skriv aldrig ut en produktions-token i en diagnostisk logg.
# 10. Agenten kan inte nå servern

Börja med nätverksanslutning:

```bash
ping LUMS-SERVER
```

Testa sedan HTTPS:

```bash
curl -I https://LUMS-SERVER/
```

Om HTTPS fungerar men Agenten fortfarande misslyckas, undersök:
text

Klientkonfiguration
Klienttoken
TLS-förtroende
API-svar
Klientidentitet
Agentversion

Inspektera Agenten:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Inspektera samtidigt servern:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Detta hjälper till att avgöra om begäran når LUMS överhuvudtaget.

Om klienten ser ett anslutningsfel och servern inte visar någon motsvarande begäran, undersök nätverks- eller TLS-vägen innan du ändrar applikationskonfigurationen.
# 11. Fortsätt felsökningen

Om de grundläggande server-, Docker-, Nginx-, TLS- och Agent-lagren fungerar, fortsätt med:
text

Klientautentisering
Tokenrotation
Uppdateringsidentifiering
Execution Watcher
Idle-detektering
Väntande jobb

Nästa avsnitt fortsätter med klientautentisering och tokenrelaterade problem.
# 12. Klientautentisering

LUMS använder klientspecifik autentisering för Agent-kommunikation.

När en klient registreras får klienten autentiseringsuppgifter som används för autentiserad kommunikation med LUMS-servern.

Autentiseringsfel ska undersökas utan att exponera klienttoken.
12.1 Klienten accepteras inte av LUMS

Om en Agent rapporterar ett autentiseringsfel, inspektera först Agent-loggen:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Inspektera sedan LUMS-containerloggarna:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Leta efter:

```text
401 Unauthorized
403 Forbidden
Invalid client token
Unknown client
Authentication failure
```

Ett 401-svar indikerar vanligtvis ett autentiseringsproblem.

Ett 403-svar kan indikera att autentiseringen lyckades men att den begärda åtgärden inte är tillåten.

Rotera inte token omedelbart.

Avgör först om problemet är:
text

Fel token
Fel klient-ID
Inaktiverad klient
Felaktig server-URL
TLS-problem
Felformad begäran
Autentiseringsfel på serversidan

12.2 Klienten finns men autentiseringen misslyckas

Verifiera att klienten fortfarande finns i LUMS administrationsgränssnitt.

Ändra inte klientposten enbart för att en Agent-begäran misslyckades.

Om klienten finns, jämför den konfigurerade klientidentiteten med den identitet som Agenten använder.

Själva produktions-token får aldrig skrivas ut i diagnostisk utdata.

Använd konfigurationsmetadata och tjänstestatus för felsökning istället för att exponera autentiseringsuppgifter.
# 13. Klienttokenrotation

Klienttokenrotation ogiltigförklarar den tidigare token och ersätter den med en ny autentiseringsuppgift.

Om en token avsiktligt har roterats måste den berörda Agenten få den nya token innan den kan autentisera igen.

Den förväntade sekvensen är:
text

Administratör
```text
    │
    ▼
Rotera klienttoken
    │
    ▼
Gammal token blir ogiltig
    │
    ▼
Ny token tilldelas klienten
    │
    ▼
Agentkonfiguration uppdateras
    │
    ▼
```
Agenten rapporterar igen

Om Agenten fortsätter använda den gamla token kommer autentiseringen att misslyckas.
13.1 Efter tokenrotation

Kontrollera Agenttjänsten:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Kör sedan Agenten via systemd:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspektera resultatet:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Om autentiseringen fortfarande misslyckas, inspektera serverloggarna:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Rotera inte token upprepade gånger.

Upprepad rotation kan göra det svårare att avgöra vilken autentiseringsuppgift som för närvarande är distribuerad på klienten.
# 14. Klienten är inaktiverad

En inaktiverad klient får inte behandlas som en aktiv hanterad klient.

Om en Agent som tillhör en inaktiverad klient försöker kommunicera, inspektera autentiseringsresultatet på serversidan.

Kontrollera:
text

Klientidentitet
Klientens aktiverade tillstånd
Autentiseringsresultat
Agentkonfiguration

Aktivera inte klienten bara för att få ett fel att försvinna.

Avgör först varför klienten inaktiverades.
# 15. Uppdateringsidentifiering

Uppdateringsidentifiering består av flera oberoende steg.

Agenten måste:

* köra pakethanterarens fråga

* tolka resultatet

* skicka resultatet till LUMS

* LUMS måste validera resultatet

* LUMS måste spara resultatet

* användargränssnittet måste visa det aktuella tillståndet

Ett fel i något steg kan göra att uppdateringsinformationen verkar felaktig.

Det grundläggande flödet är:

```text
APT / pacman
     │
     ▼
Agent
     │
     ▼
HTTPS
     │
     ▼
LUMS API
     │
     ▼
SQLite
     │
     ▼
```
Webbgränssnitt

15.1 Inga uppdateringar visas

Avgör först om klienten faktiskt rapporterade framgångsrikt.

Kontrollera:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Inspektera sedan servern:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Om Agenten slutfördes framgångsrikt men inga uppdateringar visas, undersök API- och databastillståndet innan du ändrar pakethanteraren.
15.2 Uppdateringsidentifiering för Debian / Ubuntu

Debian-pakethanteraren använder APT.

När du undersöker APT-relaterade problem, verifiera först att APT själv fungerar:

```bash
sudo apt update
```

Kör inte automatiskt paketuppgraderingar under felsökning.

Syftet med detta test är att avgöra om repository-metadata kan uppdateras framgångsrikt.

Om APT rapporterar repository-, DNS-, TLS-, signatur- eller låsningsfel, lös det underliggande APT-problemet innan du undersöker LUMS.
15.3 Uppdateringsidentifiering för Arch Linux

Arch Linux använder pacman.

Kontrollera repository-metadata:

```bash
sudo pacman -Sy
```

Använd detta endast när uppdatering av repository-metadata faktiskt krävs för diagnostiken.

Kombinera inte en onödig systemuppgradering med ett diagnostiskt test.

För paketrelaterade fel, inspektera den exakta pacman-utdata innan du ändrar konfigurationen.
# 16. Tillgängliga uppdateringar skiljer sig mellan LUMS och klienten

Uppdateringsinformation kan ändras mellan två observationer.

Till exempel:
text

Klienten rapporterar uppdateringar
  * ↓
Repository-metadata ändras
  * ↓
Paketet uppgraderas manuellt
  * ↓
LUMS visar äldre information

Tänk därför alltid på tidsstämpeln för den senaste lyckade klientrapporten.

En skillnad indikerar inte automatiskt ett databasproblem.

Kontrollera:
text

Senaste Agent-körning
Senaste lyckade rapport
Pakethanterarens tillstånd
Repository-metadata
Visat uppdateringstillstånd

# 17. Pakethantering

LUMS pakethantering är separat från filtret för installerade paket som visas på klientsidan.

Arbetsflödet för pakethantering är:
text

Användare
```text
 │
 ▼
Paketsökning
 │
 ▼
LUMS API
 │
 ▼
Agent
 │
 ▼
APT / pacman
 │
 ▼
Sökresultat
 │
 ▼
LUMS API
 │
 ▼
```
Webbgränssnitt

Att installera, ta bort eller uppdatera ett paket använder den normala jobbmekanismen i LUMS.

Den förväntade exekveringsvägen är:
text

Paketåtgärd
```text
     │
     ▼
Uppdateringsjobb
     │
     ▼
Execution Watcher
     │
     ▼
Agent
     │
     ▼
APT / pacman
```

17.1 Paketsökning returnerar inga resultat

Verifiera först att Agenten är operativ:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Inspektera sedan Agent-journalen:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

För Debian-baserade klienter, verifiera APT-metadata.

För Arch-baserade klienter, verifiera pacman-repository-metadata.

Anta inte att ett tomt sökresultat betyder att LUMS-databasen är tom.

Sökningen utförs genom klientens pakethanterare.
17.2 Paketsökning fungerar men installationen misslyckas

En lyckad sökning bevisar bara att pakethanteraren kunde hitta paketet.

Det bevisar inte att installationen kommer att lyckas.

Möjliga orsaker inkluderar:
text

Beroendekonflikter
Repository-ändringar
Paketet finns inte längre
Otillräckliga privilegier
Pakethanterarens låsning
Problem med diskutrymme
Nätverksproblem
Pakethanteringsfel

Inspektera motsvarande uppdateringsjobb.

Agent-journalen ska innehålla pakethanterarens resultat.
# 18. Paketinstallationsjobb

Paketinstallation använder den normala infrastrukturen för uppdateringsjobb.

Den relevanta åtgärden är:

```text
INSTALL_PACKAGE
```

Vid felsökning av en installation:

* Kontrollera jobbets tillstånd i LUMS.

* Kontrollera Agentens körning.

* Kontrollera pakethanterarens utdata.

* Kontrollera det slutliga resultatet som rapporterats till LUMS.

Ändra inte jobbstatus manuellt i SQLite.

Den förväntade livscykeln är:
```text

PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

eller:

```text
PENDING
   ↓
RUNNING
   ↓
FAILED
```

En misslyckad paketinstallation ska förbli spårbar genom de normala jobb- och granskningsmekanismerna.
# 19. Paketborttagningsjobb

Paketborttagning följer samma jobblivscykel.

Åtgärden är:

```text
REMOVE_PACKAGE
```

När en borttagning misslyckas, inspektera:
text

Uppdateringsjobb
Agent-journal
Pakethanterarens utdata
Slutligt jobbresultat

Ta inte bort databasposter manuellt för att dölja en misslyckad paketåtgärd.

Ett misslyckat jobb är användbar diagnostisk information.
# 20. Paketuppdateringsjobb

En paketspecifik uppdatering använder:

```text
UPDATE_PACKAGE
```

Paketet måste vara känt av LUMS som having en tillgänglig uppdatering innan jobbet skapas.

Om användargränssnittet inte erbjuder den förväntade paketuppdateringen:

* uppdatera uppdateringsinformationen

* verifiera pakethanterarens tillstånd

* verifiera resultatet för tillgängliga uppdateringar

* inspektera serverloggarna om tillståndet är inkonsekvent

Infoga inte uppdateringsposter manuellt i SQLite.
# 21. Systemuppdateringsjobb

En fullständig systemuppdatering använder:

```text
UPDATE_SYSTEM
```

Detta skiljer sig från:

```text
UPDATE_PACKAGE
```

Systemuppdateringen kan påverka flera paket och kan kräva omstart beroende på operativsystem och resulterande pakettillstånd.

Vid felsökning av en systemuppdatering, avgör om felet inträffade under:
text

Uppdateringsförberedelse
Pakethanterarens körning
Resultatinsamling
Omstartsdetektering
Rapportering efter omstart

# 22. Pakethanterarens låsningar

Pakethanterare kan vägra en åtgärd när en annan pakethanteringsprocess redan körs.

Typiska exempel inkluderar:

```text
APT is already running
dpkg is locked
pacman is locked
```

Identifiera först processen som håller låset.

Ta inte bort låsfiler blint.

En låsfil kan indikera att en annan pakethanteringsprocess är legitimt aktiv.

Att ta bort den medan en paketåtgärd körs kan skada pakethanterarens tillstånd.

Rätt felsökningssekvens är:
text

Låsfel
   ↓
Identifiera aktiv process
   ↓
Avgör om den är legitim
   ↓
Vänta eller lös processen säkert
   ↓
Försök igen

# 23. Pakethanteringsfel vs. LUMS-fel

Skilj alltid mellan ett pakethanteringsfel och ett LUMS-fel.

Till exempel:
```text

APT misslyckas
    ↓
Agenten rapporterar APT-fel
    ↓
LUMS lagrar FAILED-resultat

I detta fall kan LUMS fungera korrekt även om jobbet misslyckades.

Omvänt:
text

APT lyckas
    ↓
Agenten kan inte rapportera resultat
    ↓
```
LUMS tar aldrig emot SUCCESS

Här kan paketåtgärden ha lyckats medan LUMS rapporteringsväg misslyckades.

Pakethanterarens resultat och LUMS jobbresultat måste därför undersökas separat.
# 24. Användbar diagnostisk separation

När ett paketjobb misslyckas, klassificera felet först:
text

A. Pakethanteringsfel
B. Agentens körningsfel
C. Agentens rapporteringsfel
D. Server-/API-fel
E. Databasbeständighetsfel
F. Problem med användargränssnittet

Denna klassificering förhindrar att orelaterade komponenter ändras.

Ett pakethanteringsfel ska inte automatiskt leda till en Docker-ombyggnad.

Ett problem med användargränssnittet ska inte automatiskt leda till att databasen raderas.

Ett autentiseringsfel ska inte automatiskt leda till att Agenten installeras om.
# 25. Nästa felsökningsområde

Om klientautentisering, uppdateringsidentifiering och pakethantering fungerar är nästa diagnostiska område själva exekveringslivscykeln:
text

Uppdateringsjobb
```text
    ↓
Watcher
    ↓
Agent
    ↓
Exekvering
    ↓
Resultat
    ↓
Checkpoint / Återställning
    ↓
```
Slutligt jobbtillstånd

Nästa avsnitt täcker Execution Watcher, Idle-detektering, jobbtillstånd, återställning och omstarthantering.
# 26. Uppdateringsjobbsexekvering

LUMS uppdateringsjobb körs asynkront via Agenten och Execution Watcher.

Den normala exekveringsvägen är:
text

Användare
```text
 │
 ▼
LUMS API
 │
 ▼
SQLite
 │
 ▼
Väntande jobb
 │
 ▼
Execution Watcher
 │
 ▼
Agent
 │
 ▼
Pakethanterare
 │
 ▼
Resultat
 │
 ▼
LUMS API
 │
 ▼
SQLite
```

Ett jobb som syns i användargränssnittet är inte nödvändigtvis redan under exekvering.

Fastställ alltid det aktuella jobbtillståndet först.
26.1 Jobbet har fastnat i PENDING

Om ett jobb förblir i PENDING, kontrollera Execution Watcher innan du undersöker Agenten.

Kontrollera watchern:

```bash id="wq5h3v"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Inspektera senaste watcher-utdata:

```bash id="8y0v7e"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Kontrollera sedan Agenten:

```bash id="j8x4qm"
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Ett väntande jobb indikerar normalt att exekveringssteget ännu inte har startat.

Möjliga orsaker inkluderar:
text

Watchern körs inte
Watcher-timern körs inte
Klienten är offline
Klienten är inte idle
Klienten har inte rapporterat nyligen
Jobbet är ännu inte kvalificerat för exekvering

Ändra inte jobbtillståndet manuellt i SQLite.
# 27. Jobbet har fastnat i RUNNING

Ett RUNNING-jobb indikerar att exekveringen har startat.

Avgör först om Agenten faktiskt kör jobbet.

Kontrollera:

```bash id="s2z5ek"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Inspektera sedan watchern:

```bash id="x4f6cb"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Ett körande jobb kan ta lite tid beroende på:
text

Antal paket
Repository-hastighet
Nätverksfördröjning
Pakethanterarens operationer
Systembelastning
Omstartskrav

Avsluta inte en aktiv paketoperation enbart för att användargränssnittet inte har uppdaterats ännu.

Avgör först om den underliggande processen fortfarande är aktiv.
# 28. Jobbet är FAILED

Ett misslyckat jobb indikerar inte nödvändigtvis ett LUMS-serverfel.

Avgör vilket lager som producerade felet.

Inspektera:
text

Jobbtillstånd
Agentens körningsresultat
Pakethanterarens resultat
Serverloggar
Agent-loggar

Huvudkategorierna är:
text

Pakethanteringsfel
Agentens körningsfel
Agentens rapporteringsfel
Server-/API-fel
Autentiseringsfel
Återställningsfel

Det ursprungliga felet bör bevaras när det är möjligt.

Ersätt inte ett misslyckat jobb med en manuellt skapad lyckad post.
# 29. Jobbet är SUCCESS men paketet ändrades inte

Ett lyckat LUMS-jobb innebär att den begärda åtgärden slutfördes enligt Agentens resultat.

Om det förväntade pakettillståndet inte matchar jobbresultatet, verifiera klienten direkt.

För Debian-baserade system:

```bash id="gqdbm7"
dpkg-query -W \
    -f='${Package} ${Version}\n' \
    PACKAGE_NAME
```

För Arch Linux:

```bash id="2x9f7v"
pacman -Q \
    PACKAGE_NAME
```

Ersätt PACKAGE_NAME med paketet som undersöks.

Jämför sedan det lokala pakettillståndet med LUMS-resultatet.

Möjliga förklaringar inkluderar:
text

Paketet ändrades efter jobbet
Paketnamnet refererar till ett virtuellt/tillhandahållet paket
Pakethanterarens utdata tolkades annorlunda än förväntat
Jobbresultatet genererades före en annan lokal ändring

Ändra inte LUMS-databasen förrän avvikelsen har identifierats.
# 30. Execution Watcher

Execution Watcher ansvarar för att upptäcka jobb som är kvalificerade för exekvering.

Watchern måste behandlas som en oberoende komponent.

Kontrollera dess tjänst:

```bash id="w5m0c8"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Kontrollera dess timer:

```bash id="3v1x7r"
sudo systemctl list-timers \
    --all | grep lums
```

Inspektera dess journal:

```bash id="d5m0xk"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Om Agenten fungerar men jobb aldrig startar, bör watchern vara en av de första komponenterna att undersöka.
# 31. Watchern körs men utför inga jobb

En watcher-körning innebär inte automatiskt att ett jobb startas.

Jobbet måste uppfylla exekveringsvillkoren.

Kontrollera:
text

Klienten finns
Klienten är aktiverad
Klienten är nåbar
Klienten har aktuell status
Klienten är kvalificerad
Jobbet är väntande
Jobbet är inte redan slutfört
Exekveringsvillkoren är uppfyllda

Om klienten inte är kvalificerad kan watchern korrekt lämna jobbet väntande.

Detta är inte nödvändigtvis ett fel.
# 32. Idle-detektering

LUMS kan använda klientens idle-information när den beslutar om ett jobb ska köras.

Syftet är att undvika att starta underhållsoperationer medan klienten aktivt används.

Idle-beslutet bör därför betraktas som ett schemaläggningsvillkor, inte som ett exekveringsfel.

En klient kan rapportera framgångsrikt men ändå anses vara icke-idle.

Felsökningssekvensen är:
text

Agenten rapporterar
* ↓
Idle-information tillgänglig?
* ↓
Idle-tillstånd acceptabelt?
* ↓
Jobbet kvalificerat?
* ↓
Watchern kör

32.1 Klienten rapporterar men anses inte vara idle

Kontrollera Agent-journalen:

```bash id="5r2q1k"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Leta efter den rapporterade idle-informationen.

Inspektera sedan watchern:

```bash id="2a6v8m"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Den viktiga skillnaden är:
text

Agentkommunikation lyckad

kontra:
text

Klienten kvalificerad för underhållsexekvering

Dessa är separata tillstånd.
# 33. Idle-detektering är otillgänglig

Vissa system kanske inte tillhandahåller all idle-tillståndsinformation.

En otillgänglig idle-mekanism bör inte automatiskt tolkas som en trasig Agent.

Fastställ först den rapporterade kapaciteten.

De relevanta begreppen är:
text

Idle stöds
Idle-källa
Idle-tillstånd
Idle-varaktighet

Om plattformen inte kan tillhandahålla den förväntade idle-informationen, undersök Agentens plattformsspecifika implementering istället för att ändra serverdatabasen.
# 34. Återställning av uppdateringsjobb

LUMS använder checkpointing och återställning för att förhindra att avbrutna uppdateringsjobb behandlas som slutförda.

Ett jobb kan avbrytas på grund av:
text

Agent-omstart
Klientomstart
Nätverksavbrott
Pakethanterarens avbrott
Serveromstart
Watcher-omstart
Systemfel

Återställning måste skilja mellan arbete som redan slutförts och arbete som fortfarande behöver utföras.

Principen är:
text

Slutfört arbete förblir slutfört.
Ofullständigt arbete förblir återställningsbart.

# 35. Avbrutet jobb

Om ett jobb avbröts, inspektera först dess tillstånd.

Inspektera sedan Agenten:

```bash id="3u8d4k"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Inspektera watchern:

```bash id="w4x1b9"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Markera inte jobbet som lyckat manuellt.

Återställningsmekanismen ska avgöra vilka paketposter som redan slutförts.
# 36. Återställning upprepar en paketoperation

När återställning utlöses bör redan lyckade paketposter inte köras igen i onödan.

Återställningsmodellen baseras på tillstånd på postnivå.

Konceptuellt:
text

Jobb
 ├── Paket A → SUCCESS
 ├── Paket B → SUCCESS
 ├── Paket C → FAILED
 └── Paket D → PENDING

Återställning bör bevara de lyckade posterna och fortsätta med återstående arbete.

Om detta beteende verkar felaktigt, inspektera jobb- och paketposthistoriken innan du ändrar databasen.
# 37. Klienten startar om under en uppdatering

En omstart kan avbryta Agent-processen.

Den förväntade återställningsvägen är:
text

Uppdatering startar
* ↓
Paketoperation
* ↓
Klientomstart
* ↓
Agenten startar igen
* ↓
Tillstånd rapporteras
* ↓
LUMS utvärderar återställning

En omstart innebär därför inte automatiskt att jobbet misslyckades permanent.

Inspektera Agenttjänsten efter att klienten återvänt:

```bash id="jjh3u8"
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Inspektera sedan senaste körningarna:

```bash id="h7y5gk"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

# 38. Omstartsdetektering

Omstartsdetektering används för att avgöra om en systemomstart inträffade som en del av en uppdateringsoperation.

Detta är särskilt relevant när en uppdatering ändrar paket som kräver en omstart.

För Arch Linux får omstartsdetektering inte förväxlas med pakethanterarens utgångsstatus.

En paketoperation kan lyckas medan systemet fortfarande kräver en omstart.

Vid felsökning av omstarthantering, jämför:
text

Paketoperationens resultat
Omstartskrav
Faktiskt omstartstillstånd
Agentrapport efter omstart
Slutligt LUMS-jobbtillstånd

# 39. Jobbresultatet rapporterades inte

Om paketoperationen verkar ha slutförts men LUMS inte visar det slutliga resultatet, undersök rapporteringsvägen.

Kontrollera Agenten:

```bash id="t0r8kf"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Kontrollera sedan servern:

```bash id="h5n1xv"
sudo docker logs \
    --tail 200 \
    lums
```

Om Agenten rapporterar ett fel medan själva paketoperationen lyckades, klassificera problemet som ett rapporteringsfel snarare än ett pakethanteringsfel.
# 40. Serveromstart under jobbexekvering

En serveromstart får inte automatiskt behandlas som bevis på att en uppdateringsoperation misslyckades.

Jobbtillståndet måste utvärderas efter att servern är tillgänglig igen.

Kontrollera:
text

Containertillstånd
Databastillgänglighet
Jobbtillstånd
Klienttillstånd
Agentrapport
Watcher-tillstånd

Återställningsmekanismen ansvarar för att avgöra om avbrutet arbete säkert kan fortsätta.

Skriv inte manuellt om jobbtillstånd efter en serveromstart.
# 41. Databasen är tillgänglig men jobbtillståndet verkar fel

Om SQLite är åtkomligt men jobbtillståndet verkar inkonsekvent, inspektera applikations- och granskningsloggarna innan du ändrar databasen.

Användbar information inkluderar:
text

Jobb-ID
Klient-ID
Jobbåtgärd
Jobbets skapandetid
Aktuellt tillstånd
Paketposttillstånd
Agentresultat
Återställningshändelser
Granskningshändelser

Databasen är ett applikationsdatalager, inte ett manuellt reparationsgränssnitt.

Direkta ändringar kan kringgå validering, auktorisering, granskning och återställningslogik.
# 42. Manuella ändringar av jobbtillstånd

Manuella SQL-ändringar av uppdateringsjobbets tillstånd bör inte användas som normal felsökning.

Undvik operationer som:

```sql id="8hbyqv"
UPDATE update_jobs ...
```

eller:

```sql id="n1h7yr"
DELETE FROM update_jobs ...
```

såvida inte en kontrollerad databasåterställningsprocedur uttryckligen kräver dem.

Om en databasreparation på databasnivå verkligen är nödvändig, bevara en säkerhetskopia och dokumentera den exakta ändringen innan den tillämpas.

Normala operativa problem bör lösas genom applikations- och Agent-mekanismerna.
# 43. Diagnostisk matris för Watcher och Agent

Använd följande matris för att identifiera det mest sannolika lagret:
| Symtom | Första komponent att inspektera |
| --- | --- |
| Klienten kan inte autentisera | Agent + LUMS API |
| Klienten rapporterar framgångsrikt men jobbet förblir väntande | Execution Watcher |
| Jobbet blir körande men slutförs inte | Agent + pakethanterare |
| Paketoperationen misslyckas | Pakethanterare |
| Paketoperationen lyckas men resultatet saknas | Agentrapportering |
| Klienten startade om under uppdateringen | Agent + återställning |
| Jobbet förblir inkonsekvent efter omstart | Återställning + databastillstånd |
| Jobbet upptäcks aldrig | Watcher + timer |
| Klienten är inte kvalificerad | Idle / klienttillstånd |
| Användargränssnittet visar inaktuellt tillstånd | API + senaste klientrapport |

Denna matris är en utgångspunkt, inte en ersättning för att inspektera de faktiska loggarna och jobbtillståndet.
# 44. Nästa felsökningsområde

Efter att ha verifierat jobbexekveringen är nästa områden:
text

SQLite och databastillstånd
RBAC och användarhantering
Autentiseringssessioner
Applikations- och granskningsloggning
Containersäkerhet
Tester och CI

Dessa områden bör undersökas separat från paketexekvering.
# 45. Felsökning av SQLite och databasen

LUMS använder SQLite som sin applikationsdatabas.

Produktionsdatabasen lagras i den beständiga Docker-volymen:

```text id="9c6w3e"
/var/lib/lums/lums.db
```

Databasen hanteras av applikationen och får normalt inte ändras manuellt.

När du undersöker databasrelaterade problem, avgör först om problemet är:
text

Databastillgänglighet
Databaslåsning
Applikationskonfiguration
Datakonsistens
Migreringstillstånd
Applikationslogik

# 46. Databasen är inte tillgänglig

Om LUMS rapporterar ett databasfel, kontrollera först om containern körs:

```bash id="0l5q6h"
sudo docker ps
```

Inspektera sedan applikationsloggarna:

```bash id="6j5p8m"
sudo docker logs \
    --tail 200 \
    lums
```

Radera inte Docker-volymen omedelbart.

Den beständiga volymen innehåller produktionsapplikationens data.

Att radera den kan permanent ta bort:
text

Användare
Klienter
Klientkonfiguration
Uppdateringsjobb
Granskningsdata
Applikationstillstånd

# 47. SQLite-databaslåsning

SQLite-låsningsproblem bör undersökas genom applikationsloggarna.

Inspektera:

```bash id="l8f6vk"
sudo docker logs \
    --tail 200 \
    lums
```

Produktionsapplikationen använder:

```text id="2d3m8x"
journal_mode = wal
busy_timeout = 5000
synchronous = 2
```

Applikationen aktiverar också SQLite-främmandenyckeltvingande på sina databasanslutningar.

En databaslåsning innebär inte automatiskt att databasen är korrupt.

Möjliga orsaker inkluderar:
text

Samtidiga skrivningar
Långkörande transaktion
Applikationsprocessen använder fortfarande databasen
Oväntad processavslutning
Filsystemproblem

Ta inte bort SQLite-journalfiler manuellt.
# 48. SQLite-främmandenycklar

LUMS aktiverar uttryckligen SQLite-främmandenyckeltvingande på applikationsnivå.

Detta innebär att relationer mellan databasposter valideras av SQLite när applikationsanslutningen upprättas.

Om ett främmandenyckelrelaterat fel uppstår, inspektera applikationsloggarna först.

Inaktivera inte främmandenyckeltvingande för att få en operation att lyckas.

Ett främmandenyckelfel kan indikera ett applikationslogik- eller dataintegritetsproblem.
# 49. SQLite-databasintegritet

Om databaskorruption misstänks, sluta göra onödiga ändringar först.

Bevara det aktuella tillståndet och inspektera applikationsloggarna.

En kontrollerad integritetskontroll kan utföras mot en kopia av databasen.

Utför inte destruktiva reparationsoperationer direkt mot produktionsdatabasen om inte en dokumenterad återställningsprocedur kräver det.

Den allmänna principen är:
text

Bevara
   ↓
Inspektera
   ↓
Verifiera
   ↓
Återställ
   ↓
Validera

Börja aldrig med:
text

Radera databasen
Återskapa databasen
Återskapa Docker-volymen

# 50. Databasmigreringar

LUMS använder applikationsmigreringar för att införa databasschemändringar.

När ett migreringsproblem uppstår, inspektera containerloggarna:

```bash id="x4h9vf"
sudo docker logs \
    --tail 200 \
    lums
```

Leta efter:
text

Migreringsfel
SQL-fel
Dubblettkolumn
Saknad tabell
Villkorsfel
Migrering redan tillämpad

Redigera inte migreringsposter manuellt om inte migreringssystemet specifikt kräver en kontrollerad återställningsprocedur.

En migrering som redan har tillämpats bör normalt inte köras manuellt igen.
# 51. Databasvolym

LUMS-databasen lagras i den beständiga Docker-volymen:

```text id="p6m3jw"
lums-data
```

Inspektera volymen:

```bash id="v4c7yq"
sudo docker volume inspect \
    lums-data
```

Volymen måste förbli beständig över normal containeråterskapning.

Själva applikationscontainern är disponibel.

Applikationsdata är det inte.

Därför:

```text id="z9f4ws"
Container
    ≠
```
Beständig databas

Att återskapa containern får inte förväxlas med att återskapa datavolymen.
# 52. Databasens diskutrymme

SQLite kräver tillgängligt filsystemutrymme för normal drift.

Kontrollera värdens filsystem:

```bash id="j6k1pt"
df -h
```

Kontrollera även inode-tillgänglighet:

```bash id="q2c5ra"
df -i
```

Lågt diskutrymme kan producera databasfel som initialt ser ut som applikationsproblem.

Om databasen plötsligt blir skrivskyddad eller skrivningar börjar misslyckas, verifiera filsystemskapaciteten innan du ändrar SQLite-konfigurationen.
# 53. Felsökning av RBAC

LUMS använder rollbaserad åtkomstkontroll.

De nuvarande rollerna är:

```text id="k8w5j2"
Administrator
Operator
Viewer
```

Behörigheterna är avsiktligt olika.
## 53.1 Administrator

Administratörer kan:
text

Visa klienter
Visa installerad programvara
Visa tillgängliga uppdateringar
Skapa och köra uppdateringsjobb
Visa uppdateringshistorik
Använda pakethantering
Använda systemunderhåll
Skapa och inaktivera klienter
Rotera klienttokens
Hantera användare
Hantera roller

Administratörsspecifika operationer inkluderar användarhantering och rolladministration.
## 53.2 Operator

Operatorer kan:
text

Visa klienter
Visa installerad programvara
Visa tillgängliga uppdateringar
Skapa och köra uppdateringsjobb
Visa uppdateringshistorik
Använda pakethantering
Använda systemunderhåll

Operatorer kan inte:
text

Hantera användare
Hantera roller
Skapa eller inaktivera klienter
Rotera klienttokens

## 53.3 Viewer

Viewers har avsiktligt begränsad åtkomst.

En Viewer kan:
text

Visa klienter
Visa installerad programvara

Följande funktioner är dolda från Viewer-gränssnittet och blockerade på serversidan:
text

Tillgängliga uppdateringar
Uppdateringsjobb
Uppdateringshistorik
Pakethantering
Systemunderhåll

Detta är en avsiktlig säkerhetskontroll.

Om en Viewer kan komma åt en av dessa funktioner, behandla problemet som ett RBAC-problem snarare än bara ett UI-problem.
# 54. Viewer ser för mycket

Om en Viewer ser funktioner som inte bör vara tillgängliga, kontrollera båda lagren:
text

Webbläsargränssnitt
* +
Auktorisering på serversidan

Att dölja ett element i JavaScript eller HTML är inte tillräcklig säkerhet.

API:et måste också avvisa obehöriga operationer.

Vid undersökning:

* Fastställ den autentiserade användarens roll.

* Identifiera den berörda slutpunkten.

* Kontrollera serverns svar.

* Inspektera applikationsloggarna vid behov.

* Verifiera det relevanta RBAC-testet.

Lös inte ett auktoriseringsproblem genom att bara dölja UI-elementet.
# 55. Viewer kan inte se förväntad data

En Viewer bör fortfarande kunna komma åt den information som uttryckligen tillåts av den aktuella RBAC-modellen.

Om tillåten klientinformation saknas:
text

Verifiera inloggning
   ↓
Verifiera roll
   ↓
Verifiera klientsynlighet
   ↓
Inspektera API-svar
   ↓
Inspektera webbläsarkonsolen vid behov

Bevilja inte ytterligare behörigheter bara för att en sida för närvarande verkar ofullständig.

Avgör först om den saknade informationen är avsiktligt begränsad.
# 56. Operator kan inte utföra en operation

Om en Operator får 403 Forbidden, avgör först om den begärda åtgärden är administratörsspecifik.

Operatoråtkomst inkluderar inte:
text

Användarhantering
Rolladministration
Klientkapande/inaktivering
Klienttokenrotation

Om operationen bör tillåtas för Operatorer, inspektera slutpunktens auktoriseringsdekorator och motsvarande RBAC-tester.

Befordra inte tillfälligt användaren till Administrator som en diagnostisk genväg.
# 57. Administrator kan inte utföra en operation

En Administrator bör ha åtkomst till alla för närvarande stödda administrativa operationer.

Om en Administrator får ett auktoriseringsfel:
text

Verifiera autentiserad session
```text id="3h6q8f"
        ↓
Verifiera aktuell roll
        ↓
Verifiera slutpunktsauktorisering
        ↓
Inspektera CSRF-krav
        ↓
```
Inspektera applikationsloggar

För tillståndsändrande operationer kan en giltig session ensam inte vara tillräcklig.

CSRF-skydd måste också uppfyllas där det krävs.
# 58. Användarhantering

Användarhantering är begränsad till Administratörer.

Arbetsflödet för användarhantering är:
text

Administratör
```text id="x4j6pw"
    │
    ▼
Användarhantering
    │
```
* ├── Skapa användare
* ├── Tilldela roll
* └── Aktivera / inaktivera användare

När en användare inte kan skapas, kontrollera:
text

Aktuell roll
Användarnamnsvalidering
Rollvalidering
Dubblettanvändarnamn
Lösenordsvalidering
CSRF-skydd
Applikationsloggar

Skapa inte användare direkt i SQLite.

Direkt databasinsättning kringgår lösenordshashning, validering, auktorisering och granskningsloggning.
# 59. Användarskapande misslyckas

Om användarskapande misslyckas, inspektera webbläsarens svar och serverloggarna.

API:et bör validera:
text

Användarnamn
Roll
Lösenordskrav
Dubblettkonto
Autentiserad administratör
CSRF-token

Om begäran avvisas, avgör vilken valideringsregel som utlöstes.

Försvaga inte valideringen bara för att få en kontoskapandebegäran att lyckas.
# 60. Lösenordsproblem

LUMS lagrar användarlösenord med en lösenordshashningsmekanism snarare än klartextlösenord.

Om en användare inte kan logga in:
text

Verifiera användarnamn
   ↓
Verifiera kontots aktiverade tillstånd
   ↓
Verifiera lösenord
   ↓
Kontrollera inloggningshastighetsbegränsning
   ↓
Inspektera autentiseringsloggar

Lagra eller logga aldrig klartextlösenord.

Kopiera inte lösenord till diagnostiska kommandon eller loggfiler.
# 61. Inaktiverat användarkonto

Ett inaktiverat konto får inte behandlas som ett aktivt inloggningskonto.

Om en inaktiverad användare fortfarande kan autentisera, undersök:
text

Aktuellt kontotillstånd
Autentiseringsuppslag
Sessionstillstånd
Sessionsåterkallelse
Webbläsarsession
Auktorisering på serversidan

Ta inte bara bort kontot.

Att bevara kontot kan vara viktigt för granskningshistoriken.
# 62. Sessionsproblem

LUMS använder sessionshantering på serversidan.

När en användare verkar ha inaktuell eller oväntad åtkomst, logga först ut och upprätta en ny session.

Om problemet kvarstår, undersök:
text

Kontotillstånd
Roll
Sessionstillstånd
Sessionsåterkallelse
Cookie-konfiguration
CSRF-skydd

Inaktivera inte sessionssäkerhetskontroller för att kringgå ett inloggningsproblem.
# 63. Sessionsåterkallelse

Sessionsåterkallelse är relevant när:
text

Ett lösenord ändras
En användare inaktiveras
En roll ändras
En session måste ogiltigförklaras
En säkerhetshändelse kräver påtvingad utloggning

Om en användare verkar behålla åtkomst efter en kontoändring, avgör om den befintliga sessionen ogiltigförklarades korrekt.

Testa med en ny webbläsarsession först efter att ha bekräftat kontotillståndet.

Anta inte att enbart radering av webbläsarcookies bevisar att sessionsåterkallelse på serversidan fungerar.
# 64. Inloggningshastighetsbegränsning

LUMS tillämpar inloggningshastighetsbegränsning för upprepade misslyckade autentiseringsförsök.

Det nuvarande beteendet använder ökande utelåsningsintervall:
text

5 försök  → 30 sekunder
6 försök  → 60 sekunder
7 försök  → 120 sekunder
8+ försök → 300 sekunder

Feltillståndet persistieras i SQLite.

Om inloggningsförsök oväntat blockeras, inspektera autentiseringstillståndet innan du ändrar databasen.

Ett hastighetsbegränsningssvar är inte automatiskt ett autentiseringsfel.

Det kan indikera att kontot har nått den konfigurerade tröskeln för misslyckade försök.
# 65. Inloggning fungerar men API returnerar 403

En lyckad inloggning bevisar autentisering, inte auktorisering.

Ett 403 Forbidden-svar kan indikera:
text

Otillräcklig roll
Saknat CSRF-skydd
Otillåten operation
Inaktiverad funktion

Identifiera den exakta slutpunkten innan du ändrar något.

Den korrekta felsökningsfrågan är:
text

"Är denna användare autentiserad?"

följt av:
text

"Är denna autentiserade användare auktoriserad för denna operation?"

Dessa är separata säkerhetskontroller.
# 66. CSRF-fel

Tillståndsändrande webbläsarbegäranden skyddas mot cross-site request forgery.

Om en tillståndsändrande begäran oväntat misslyckas:
text

Verifiera autentiserad session
```text id="9w3r5b"
        ↓
Verifiera CSRF-token
        ↓
Verifiera begärandemetod
        ↓
Verifiera slutpunkt
        ↓
```
Inspektera serversvar

Inaktivera inte CSRF-skydd som en felsökningslösning.

En misslyckad CSRF-kontroll är en säkerhetskontroll som fungerar som avsett.
# 67. Webbläsargränssnitt och API är oense

Om användargränssnittet visar att en åtgärd är tillgänglig men API:et avvisar den:
text

Webbläsargränssnitt
   ↓
Visad roll/tillstånd
   ↓
API-begäran
   ↓
Auktorisering på serversidan

Resultatet på serversidan är auktoritativt.

Användargränssnittet kan innehålla inaktuellt tillstånd efter:
text

Rolländringar
Sessionsändringar
Klientändringar
Sidan har varit öppen länge

Ladda om sidan och upprätta en ny session innan du antar att auktoriseringen på serversidan är felaktig.
# 68. Diagnostisk RBAC-matris
| Symtom | Första komponent att inspektera |
| --- | --- |
| Viewer ser management-UI | Klientsidans rollhantering |
| Viewer API-begäran lyckas | RBAC på serversidan |
| Operator får 403 | Slutpunktens behörighetsmodell |
| Administrator får 403 | Session / CSRF / slutpunktsauktorisering |
| Användare kan inte skapas | Adminroll + validering |
| Inaktiverad användare kan logga in | Kontotillstånd + sessionshantering |
| Inloggning tillfälligt blockerad | Hastighetsbegränsning |
| Tillståndsändrande begäran avvisas | CSRF / session |
| UI och API är oense | Webbläsartillstånd + serverauktorisering |

Resultatet av auktoriseringen på serversidan är alltid viktigare än huruvida ett gränssnittselement är synligt.
# 69. Nästa felsökningsområde

Nästa diagnostiska områden är:
text

Applikations- och granskningsloggning
Containersäkerhet
Filsystemsbehörigheter
Docker runtime-konfiguration
Tester och CI
Diagnostiska ögonblicksbilder
Slutlig återställningschecklista

Dessa områden bör undersökas utan att försvaga säkerhetsbaslinjen.
# 70. Applikationsloggning

LUMS använder applikationsloggning för att tillhandahålla diagnostisk information utan att exponera känsliga autentiseringsuppgifter.

När du undersöker ett applikationsproblem, börja med de senaste loggarna:

```bash id="f6m2qa"
sudo docker logs \
    --tail 200 \
    lums
```

För kontinuerlig övervakning:

```bash id="x3v8kp"
sudo docker logs \
    -f \
    lums
```

Återskapa problemet medan du övervakar loggarna när det är möjligt.

Det gör det lättare att korrelera:
text

Användaråtgärd
* ↓
HTTP-begäran
* ↓
Applikationshändelse
* ↓
Databasoperation
* ↓
Agentinteraktion

# 71. Applikationsloggar innehåller ett fel

Identifiera först komponenten som producerade meddelandet.

Typiska källor inkluderar:
text

Flask-applikation
Gunicorn
Databaslager
Autentisering
Auktorisering
Pakethantering
Jobbexekvering
Klientrapportering

Anta inte att det sista loggmeddelandet är rotorsaken.

Leta efter det första relevanta felet i händelsesekvensen.

Korrelera när det är möjligt:
text

Tidsstämpel
Klient
Begäran
Jobb-ID
Fel
Resultat

# 72. Granskningsloggning

LUMS registrerar säkerhetsrelevanta applikationsåtgärder i granskningsloggen.

Granskningsloggning är användbar när du undersöker:
text

Användarändringar
Autentiseringshändelser
Administrativa åtgärder
Klienthantering
Tokenoperationer
Skapande av uppdateringsjobb
Säkerhetsrelevanta tillståndsändringar

En granskningshändelse bör behandlas som bevis på en applikationshändelse, inte som en ersättning för systemloggar.

Använd applikationsloggar för tekniska körningsdetaljer och granskningsloggar för säkerhetsrelevanta applikationsåtgärder.
# 73. Granskningshändelse saknas

Om en förväntad granskningshändelse saknas:

* Identifiera den exakta åtgärden.

* Identifiera API-slutpunkten.

* Verifiera att åtgärden faktiskt nådde servern.

* Inspektera applikationsloggarna.

* Avgör om åtgärden avvisades innan granskningshändelsen borde ha skapats.

Infoga inte manuellt granskningsposter bara för att få en granskningskedja att verka komplett.

En granskningspost bör motsvara en verklig applikationshändelse.
# 74. Granskningslogg och applikationslogg skiljer sig

De två loggsystemen har olika syften.

Till exempel:
text

Applikationslogg
→ teknisk körningsinformation

Granskningslogg
→ säkerhetsrelevant applikationshändelse

Ett pakethanteringsfel kan därför förekomma i applikations- eller Agent-loggen utan att representera en separat administrativ granskningshändelse.

Omvänt bör en användarhanteringsåtgärd producera en granskningsbar applikationshändelse även om operationen i sig är tekniskt enkel.
# 75. Känslig information i loggar

Placera aldrig avsiktligt följande i diagnostisk utdata:
text

Klienttokens
Applikationshemliga nycklar
Lösenord
Sessionshemligheter
Privata nycklar
TLS-privat material

Om ett diagnostiskt kommando skulle exponera ett av dessa värden, använd en redigerad eller metadatabaserad kontroll istället.

När du delar loggar för felsökning, granska dem för hemligheter innan du kopierar dem till ärenden, dokumentation, GitHub-ärenden eller chatt.
# 76. Docker-containersäkerhet

Produktionscontainern för LUMS är avsiktligt härdad.

De förväntade säkerhetsegenskaperna inkluderar:
text

Icke-root applikationsanvändare
Skrivskyddat rotfilsystem
Alla Linux-kapabiliteter borttagna
no-new-privileges aktiverat
Inget privilegierat läge
Dedikerad skrivbar datavolym
Skrivskyddad hemlig montering
Begränsade temporära filsystem

Om en av dessa egenskaper oväntat ändras, behandla det som konfigurationsdrift.

Försvaga inte containern för att lösa ett applikationsproblem om inte säkerhetspåverkan har utvärderats uttryckligen.
# 77. Verifiera container runtime-säkerhet

Inspektera containern:

```bash id="b8x5jq"
sudo docker inspect lums
```

För en fokuserad runtime-kontroll:

```bash id="r3n7cw"
sudo docker inspect \
    --format='ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}' \
    lums
```

De förväntade värdena inkluderar:

```text id="k5m2zr"
ReadonlyRootfs=true
Privileged=false
CapDrop=[ALL]
SecurityOpt=[no-new-privileges:true]
```

Det exakta formatet kan variera mellan Docker-versioner.

Det är säkerhetsegenskaperna i sig som är viktiga.
# 78. Containern körs som root

LUMS-applikationen bör köras som sin dedikerade oprivilegierade applikationsanvändare.

Om containern oväntat körs som root, inspektera först avbildningen och runtime-konfigurationen:

```bash id="p6x4nz"
sudo docker inspect \
    --format='{{.Config.User}}' \
    lums
```

Inspektera sedan Dockerfile.

Lös inte applikationsbehörighetsproblem genom att byta produktionscontainern till root.

Om en katalog kräver skrivåtkomst, identifiera den exakta sökvägen och avgör om den ska vara beständig applikationsdata eller temporär data.
# 79. Skrivskyddat rotfilsystem

Produktionscontainern använder ett skrivskyddat rotfilsystem.

Detta skyddar applikationsavbildningen från onödig runtime-modifiering.

Om applikationen rapporterar:

```text id="y5k8mc"
Read-only filesystem
Permission denied
Cannot create file
Cannot write temporary data
```

avgör först var applikationen försöker skriva.

Förväntade skrivbara platser är avsiktligt begränsade.

Beständig applikationsdata hör hemma i:

```text id="q9m3xr"
/var/lib/lums
```

Temporär runtime-data kan använda de konfigurerade temporära filsystemen.

Inaktivera inte --read-only bara för att en applikationssökväg oväntat är skrivbar.
# 80. /tmp är inte skrivbart

Om applikationen kräver tillfällig lagring, verifiera det temporära filsystemet:

```bash id="a7w4vn"
sudo docker inspect \
    --format='{{json .HostConfig.Tmpfs}}' \
    lums
```

Produktionscontainern tillhandahåller en begränsad /tmp.

Det temporära filsystemet är endast avsett för transient data.

Beständig data får inte lagras där.
# 81. Problem med hemlig montering

LUMS applikationshemlighet tillhandahålls genom en skyddad filmontering.

Hemligheten bör inte bäddas in direkt i avbildningen.

Om LUMS rapporterar en saknad hemlighet, inspektera först runtime-konfigurationen:

```bash id="j4p7zx"
sudo docker inspect \
    lums
```

Kontrollera att den hemliga monteringen finns och är skrivskyddad.

Skriv inte ut innehållet i hemligheten.

En användbar diagnostik är att verifiera att filen finns och har förväntade behörigheter utan att visa dess innehåll.
# 82. Hemlig fil saknas

Om den hemliga filen saknas på värden och ingen reservvariabel `LUMS_SECRET_KEY` har angetts misslyckas applikationen omedelbart vid start med `RuntimeError: LUMS secret is not configured. Provide LUMS_SECRET_KEY_FILE or LUMS_SECRET_KEY.` (`server/app.py`). Detta är ett startfel, inte bara ett autentiseringssymtom. Se avsnitt 114 för reservbeteendet mellan fil och variabel.

Kontrollera att sökvägen finns. Återskapa inte hemligheten slumpmässigt; en ersättning kan ogiltigförklara sessioner eller annat kryptografiskt tillstånd och måste behandlas som en kontrollerad säkerhetsåtgärd.

# 83. Beständig volym är inte skrivbar

Om LUMS inte kan skriva applikationsdata, inspektera volymen:

```bash id="y6c2mt"
sudo docker volume inspect \
    lums-data
```

Inspektera sedan containerns monteringar:

```bash id="e5w8rq"
sudo docker inspect \
    --format='{{json .Mounts}}' \
    lums
```

Applikationsdatabasen måste finnas på den beständiga skrivbara volymen.

Gör inte hela containerfilsystemet skrivbart som en lösning.

Den korrekta lösningen är att identifiera den specifika sökväg som kräver persistens.
# 84. Docker-containern startar men applikationen misslyckas

Om containern startar och omedelbart avslutas:

```bash id="t7x3mp"
sudo docker ps -a \
    --filter name=lums
```

Inspektera sedan:

```bash id="n4q6vz"
sudo docker logs \
    --tail 200 \
    lums
```

Vanliga orsaker inkluderar:
text

Applikationsstartfel
Saknad hemlighet
Databasinitieringsfel
Migreringsfel
Ogiltig miljökonfiguration
Behörighetsproblem
Beroendeproblem

Bygg inte om avbildningen omedelbart.

Avgör om problemet finns i avbildningen, runtime-konfigurationen, beständig data eller extern konfiguration.
# 85. Docker-avbildning vs. containerkonfiguration

En fungerande avbildning kan fortfarande misslyckas på grund av felaktig runtime-konfiguration.

Skilj alltid mellan:
text

Docker-avbildning
* +
Container runtime-konfiguration
* +
Beständig volym
* +
Hemlighet/konfiguration

Till exempel:
text

Avbildningen är giltig
* +
Fel volym
* =
Applikationsfel

eller:
text

Avbildningen är giltig
```text id="s7q2mj"
      +
```
Saknad hemlighet
* =
Applikationsstartfel

Bygg inte om en annars giltig avbildning för att åtgärda ett runtime-konfigurationsproblem.
# 86. Docker-byggproblem

Om en ny avbildning inte kan byggas, inspektera Dockerfile först.

Kontrollera basavbildningen och beroendedefinitionerna.

Produktions-Dockerfile använder en fastställd Python-basavbildningssammanfattning.

Detta ger reproducerbarhet och förhindrar att bygget tyst flyttas till en orelaterad basavbildningsrevision.

Om ett bygge plötsligt ändrar beteende, jämför:
text

Dockerfile
Basavbildningens sammanfattning
Krav
Applikationskälla
Byggkontext

# 87. Problem med .dockerignore

Docker-byggkontexten bör inte innehålla onödiga lokala filer eller känsligt material.

Repositoryt använder .dockerignore för att utesluta filer som:
text

Lokala säkerhetskopior
Tillfälliga filer
Redigeringsartefakter
Säkerhetskopior
Annat onödigt runtime-material

Om ett bygge oväntat innehåller en fil som inte bör finnas, inspektera:

```bash id="q5m8cz"
cat .dockerignore
```

Lös inte byggkontextproblem genom att kopiera känsliga filer till avbildningen.
# 88. Filsystemsbehörighetsproblem

Om LUMS rapporterar behörighetsfel, identifiera den exakta sökvägen först.

Användbar information:

```bash id="p4r7yn"
sudo docker inspect \
    lums
```

och:

```bash id="n8v2km"
sudo docker logs \
    --tail 200 \
    lums
```

Den viktiga skillnaden är:
text

Applikationsdata
Temporär data
Applikationskälla
Hemligt material
Värdkonfiguration

Var och en har olika förväntade behörigheter.

Ändra inte rekursivt äganderätt eller behörigheter över hela filsystemet som en felsökningsgenväg.
# 89. Produktionskonfigurationsdrift

Konfigurationsdrift uppstår när den körande miljön inte längre matchar den avsedda säkerhetsbaslinjen.

Exempel inkluderar:
text

Containern körs som root
Port 5050 exponeras externt
Skrivskyddat filsystem inaktiverat
Kapabiliteter återställda
Privilegierat läge aktiverat
Hemlighet monterad läs-skriv
Oväntad container körs

Om drift upptäcks:

* Registrera det aktuella tillståndet.

* Avgör när det ändrades.

* Identifiera den ansvariga konfigurationen.

* Korrigera konfigurationen avsiktligt.

* Kör om relevant säkerhetsverifiering.

Gör inte flera orelaterade ändringar samtidigt.
# 90. Oväntad nätverksexponering

Applikationsporten bör förbli lokal:

```text id="n7w4cp"
127.0.0.1:5050
```

Kontrollera lyssnare:

```bash id="y2m6vk"
sudo ss -lntp
```

Om 5050 exponeras på en icke-loopback-adress, undersök Docker-portmappningen omedelbart.

Exponera inte applikationsporten bara för att Nginx verkar svår att diagnostisera.

Den avsedda arkitekturen är:
text

Nätverk
```text id="h3x8qm"
   ↓
Nginx :443
   ↓
127.0.0.1:5050
   ↓
LUMS
```

# 91. Oväntade Docker-containrar

Lista alla containrar:

```bash id="c6w9rz"
sudo docker ps -a
```

Oväntade containrar bör identifieras innan de tas bort.

Kontrollera:
text

Containernamn
Avbildning
Skapandetid
Portar
Volymer
Omstartspolicy

Ta inte bort en okänd container utan att först avgöra om den är en del av LUMS-distributionen eller en nödvändig reservmiljö.
# 92. Docker-volymen får inte raderas under normal felsökning

Följande operation är destruktiv:

```bash id="q7v3mc"
sudo docker volume rm lums-data
```

Den får inte användas som ett allmänt felsökningssteg.

Att radera volymen kan ta bort applikationsdatabasen och associerat beständigt tillstånd.

Om en ren installation avsiktligt krävs, behandla det som en separat migrerings- eller återställningsoperation och verifiera säkerhetskopior först.
# 93. Säkerhetsbaslinje efter runtime-ändringar

Efter att ha ändrat produktions-Docker-konfigurationen, verifiera säkerhetsbaslinjen igen.

Verifiera minst:
text

Containern körs som avsedd användare
Rotfilsystemet är skrivskyddat
Kapabiliteter är borttagna
Privilegierat läge är inaktiverat
no-new-privileges är aktiverat
Hemlig montering är skrivskyddad
Databasvolymen är skrivbar
Applikationsporten är endast loopback

En konfiguration som får applikationen att fungera men försvagar dessa egenskaper bör inte betraktas som en lyckad åtgärd.
# 94. Nästa felsökningsområde

De återstående felsökningsämnena är:
text

Tester och CI
Diagnostiska ögonblicksbilder
Vanliga felkombinationer
Återställningsprinciper
Slutlig felsökningschecklista

De sista avsnitten tillhandahåller en kompakt procedur för att samla tillräckligt med information för att diagnostisera ett problem utan att i onödan ändra produktionsmiljön.
# 95. Tester och CI

Automatiserade tester är en viktig del av felsökningen av LUMS.

Innan du undersöker ett produktionsproblem som en applikationsdefekt, verifiera om det relevanta beteendet redan täcks av testsviten.

Den aktuella fullständiga testsviten ska passera innan en release anses redo.

Kör den fullständiga testsviten från repositoryt:

```bash id="m4x8kp"
./.venv-test/bin/pytest -q
```

En lyckad körning ska rapportera alla tester som godkända.

Antalet tester ändras när ytterligare tester läggs till. Det viktiga villkoret är att den fullständiga testsviten lyckas snarare än att förlita sig på ett fast testantal.
# 96. Ett testfel innebär inte automatiskt att produktionen är trasig

Ett misslyckat test kan orsakas av:
text

Applikationsregression
Testregression
Beroendeändring
Miljöproblem
Saknat testberoende
Felaktig testkonfiguration

Inspektera först den fullständiga felutdata.

Ändra inte produktionskonfigurationen bara för att ett lokalt test misslyckas.

Den korrekta sekvensen är:
text

Testfel
* ↓
Läs fullständigt fel
* ↓
Identifiera påverkad komponent
* ↓
Reproducera lokalt
* ↓
Fastställ rotorsak
* ↓
Tillämpa kontrollerad åtgärd
* ↓
Kör relevanta tester
* ↓
Kör fullständig testsvit

# 97. RBAC-testfel

När du undersöker auktoriseringsproblem, kör RBAC-testerna först:

```bash id="k6w2pv"
./.venv-test/bin/pytest -q tests/test_rbac.py
```

Testerna täcker rollspecifikt beteende och auktoriseringsgränser.

Om problemet gäller klientsidan, använd relevant delmängd när det är lämpligt:

```bash id="z5n8rc"
./.venv-test/bin/pytest -q \
    tests/test_rbac.py -k client_page
```

Försvaga inte auktoriseringen för att få ett test att passera.

Ett misslyckat auktoriseringstest kan indikera en säkerhetsregression.
# 98. Testfel för paketsökning

Pakethanteringsfunktionalitet har dedikerad testtäckning.

När du undersöker paketsökningsbeteende:

```bash id="b7x3mf"
./.venv-test/bin/pytest -q \
    tests/test_package_search.py
```

Om felet involverar paketexekvering eller jobbresultat, inspektera även relevanta jobbresultattester.

Testsviten bör användas för att skilja mellan:
text

Applikationslogikproblem
Paketsökningsproblem
Agentproblem
Integrationsproblem

# 99. Tester för validering av jobbresultat

Hantering av jobbresultat är säkerhetskänslig eftersom servern inte blint får lita på godtycklig klientinmatning.

Kör relevanta tester när du undersöker resultatvalidering:

```bash id="w6q2vz"
./.venv-test/bin/pytest -q \
    tests/test_job_result.py
```

Ett fel här bör behandlas som ett applikationskorrekthets- och säkerhetsproblem.

Kringgå inte resultatvalidering för att få en klientrapport att lyckas.
# 100. CI-fel

LUMS använder kontinuerlig integration för att verifiera projektet innan ändringar accepteras.

Om CI misslyckas:

* Identifiera det misslyckade jobbet.

* Läs det fullständiga felet.

* Avgör om felet är kod-, beroende-, test- eller miljörelaterat.

* Reproducera lokalt där det är möjligt.

* Åtgärda rotorsaken.

* Kör relevanta tester.

* Kör den fullständiga testsviten.

Ignorera inte CI-fel bara för att produktionsmiljön för närvarande verkar funktionell.
# 101. Diagnostisk ögonblicksbild

När du ber om hjälp med ett LUMS-problem, samla en minimal diagnostisk ögonblicksbild.

Målet är att tillhandahålla tillräckligt med information för att identifiera den felande komponenten utan att exponera hemligheter.

En användbar ögonblicksbild inkluderar:

```bash id="x8p4qn"
sudo docker ps
```


```bash id="c5m7vz"
sudo docker logs --tail 100 lums
```


```bash id="f2w9yk"
sudo systemctl status nginx --no-pager
```


```bash id="n6r3tx"
sudo systemctl status lums-agent.service --no-pager
```


```bash id="q7v4mc"
sudo systemctl status lums-agent-watcher.service --no-pager
```


```bash id="z3k8wp"
sudo journalctl -u lums-agent.service -n 100 --no-pager
```


```bash id="h5m2rx"
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager
```


```bash id="p9x6kc"
sudo ss -lntp
```

Använd endast de kommandon som är relevanta för problemet.

Dumpa inte hela miljön i en supportförfrågan.
# 102. Diagnostisk ögonblicksbild får inte innehålla hemligheter

Innan du delar diagnostisk utdata, kontrollera efter:
text

Lösenord
Klienttokens
Applikationshemliga nycklar
Sessionshemligheter
Privata nycklar
TLS-privat material
Autentiseringsuppgifter

Redigera känsliga värden innan du delar.

Anta inte att en logg är säker bara för att den kom från en systemtjänst.
# 103. Matris för felkombinationer

Vissa symtom blir lättare att diagnostisera när flera komponenter beaktas tillsammans.
| Symtom | Mest sannolikt område att inspektera först |
| --- | --- |
| Webbläsaren kan inte ansluta | Nginx / TLS / nätverk |
| Nginx fungerar men applikationen misslyckas | Docker / LUMS |
| LUMS fungerar men klienten kan inte rapportera | Agent / TLS / token |
| Klienten rapporterar men jobbet förblir väntande | Watcher / kvalificering |
| Jobbet körs men paketet misslyckas | APT / pacman |
| Paketet lyckas men resultatet saknas | Agentrapportering |
| Resultatet når servern men UI är inaktuellt | API / databas / webbläsartillstånd |
| Viewer kan mutera data | RBAC på serversidan |
| Användaren kan inte logga in | Konto / lösenord / hastighetsbegränsning |
| Inloggning fungerar men åtgärd avvisas | RBAC / CSRF |
| Databasskrivningar misslyckas | SQLite / disk / behörigheter |
| Containern förlorar data efter återskapning | Beständig volymkonfiguration |
| Applikationen skriver till rotfilsystemet | Containerfilsystemkonfiguration |
| Port 5050 är externt nåbar | Docker / brandväggskonfiguration |

Denna tabell identifierar den första platsen att undersöka, inte nödvändigtvis den slutliga rotorsaken.
# 104. Vanliga felsökningsmisstag

Undvik följande genvägar:
Radera inte databasen
text

Radera lums.db
Radera lums-data

kan förstöra beständigt applikationstillstånd.
Inaktivera inte säkerhetskontroller

Inaktivera inte permanent:
text

RBAC
CSRF-skydd
TLS-validering
Containerhärdning
Skrivskyddat filsystem
no-new-privileges
Kapabilitetsbegränsningar

En lösning som tar bort en säkerhetskontroll är inte en slutförd åtgärd.
Kör inte containern som privilegierad

Undvik:

```text id="b3x7mz"
--privileged
```

som en felsökningslösning.

Om applikationen kräver ytterligare åtkomst, avgör exakt vilken åtkomst som krävs.
Exponera inte port 5050

Ändra inte:

```text id="v8n4qr"
127.0.0.1:5050
```

till:

```text id="p2m6wy"
0.0.0.0:5050
```

bara för att kringgå Nginx.

Applikationen är avsiktligt skyddad bakom den omvända proxyn.
Ändra inte jobbtillstånd manuellt

Undvik att direkt ändra:

```text id="r7c5xn"
update_jobs
update_job_packages
```

för att dölja ett operativt problem.

Använd applikations-, Agent-, watcher- och återställningsmekanismerna.
Ta inte bort pakethanterarens lås blint

Ett lås kan indikera en aktiv pakethanteringsprocess.

Identifiera processen först.
Rotera inte autentiseringsuppgifter upprepade gånger

Upprepad token- eller hemlighetsrotation kan skapa ytterligare autentiseringsproblem.

Avgör först vilken autentiseringsuppgift som för närvarande är konfigurerad och vilken autentiseringsuppgift servern förväntar sig.
# 105. Återställningsprinciper

Följande principer gäller för all LUMS-felsökning:
Bevara först

Behåll:
text

Loggar
Jobbtillstånd
Databas
Containertillstånd
Konfiguration
Felmeddelanden

tills problemet är förstått.
Ändra en sak i taget

När flera ändringar görs samtidigt blir den ursprungliga orsaken svårare att identifiera.
Verifiera efter varje ändring

Efter en kontrollerad ändring:
text

Testa igen
Kontrollera loggar
Verifiera tillstånd
Bekräfta säkerhetsegenskaper

Föredra reversibla ändringar

Använd när det är möjligt ändringar som kan återställas utan att förstöra applikationstillståndet.
Håll säkerhetskontroller aktiva

Ett lyckat felsökningsresultat får inte införa en onödig säkerhetsregression.
# 106. Produktionsfelsökningssekvens

För ett allmänt LUMS-produktionsproblem, använd denna ordning:
text

1. Identifiera symtomet
  * ↓
2. Identifiera den påverkade komponenten
  * ↓
3. Inspektera aktuellt tillstånd
  * ↓
4. Inspektera relevanta loggar
  * ↓
5. Reproducera säkert
  * ↓
6. Fastställ det första felande lagret
  * ↓
7. Tillämpa minsta nödvändiga ändring
  * ↓
8. Testa igen
  * ↓
9. Verifiera säkerhetskontroller
  * ↓
10. Dokumentera resultatet

Denna ordning förhindrar att orelaterade komponenter ändras i onödan.
# 107. Fullständig systemdiagnostisk väg

När den påverkade komponenten är okänd, följ den fullständiga vägen:
text

Webbläsare
```text id="u7x3mp"
  │
  ▼
Nginx / HTTPS
  │
  ▼
Docker
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Uppdateringsjobb
  │
  ▼
Watcher
  │
  ▼
Agent
  │
  ▼
APT / pacman
  │
  ▼
Klienttillstånd
  │
  ▼
Agentresultat
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
```
Webbgränssnitt

Vid varje steg, fråga:
text

Nådde begäran denna komponent?

Bearbetade denna komponent den?

Producerade den det förväntade resultatet?

Tog nästa komponent emot det resultatet?

Det första NEJ identifierar normalt det område som kräver undersökning.
# 108. Releasefelsökning

Innan du förbereder en release, verifiera:
text

Fullständig testsvit passerar
CI passerar
Säkerhetsgranskning är slutförd
Dokumentationen är aktuell
Produktionskonfigurationen matchar den dokumenterade baslinjen
Ingen oväntad felsökningskonfiguration kvarstår
Inga hemligheter ingår i repositoryt
Docker-härdning förblir aktiv
RBAC-beteende är korrekt
Pakethantering fungerar
Uppdateringsjobbsexekvering fungerar
Återställningsbeteende är verifierat

En release bör inte skapas bara för att applikationen startar framgångsrikt.
# 109. Felsökningschecklista

Använd denna checklista innan du förklarar ett produktionsproblem löst:
text

[ ] Rotorsak identifierad
[ ] Relevanta loggar inspekterade
[ ] Ingen onödig data raderades
[ ] Inga autentiseringsuppgifter exponerades
[ ] Ingen säkerhetskontroll inaktiverades
[ ] Relevant funktionalitet testad
[ ] Fullständig testsvit beaktad där det är lämpligt
[ ] Docker-säkerhetsbaslinje verifierad
[ ] Nätverksexponering verifierad
[ ] Agenttillstånd verifierat
[ ] Watcher-tillstånd verifierat
[ ] Jobbtillstånd verifierat
[ ] Återställningstillstånd verifierat
[ ] Databastillstånd verifierat där det är relevant
[ ] Dokumentation uppdaterad om beteendet ändrades

# 110. När du ska sluta felsöka

Sluta göra ändringar när:
text

Rotorsaken är identifierad
* OCH
Den korrigerande åtgärden är förstådd
* OCH
Systemet är stabilt
* OCH
Säkerhetskontroller förblir intakta

Om rotorsaken inte är förstådd, bevara det aktuella tillståndet snarare än att upprepade gånger ändra miljön.

Ett rent bevarat fel är lättare att diagnostisera än ett delvis modifierat system.
# 111. Slutlig återställningsprincip

Den viktigaste LUMS-felsökningsregeln är:

* Observera först. Ändra sedan. Verifiera sist.

LUMS innehåller flera oberoende säkerhets- och exekveringslager.

Ett problem i ett lager bör inte automatiskt leda till ändringar i ett annat.

Den föredragna felsökningsmetoden är därför:
text

Observera
   ↓
Klassificera
   ↓
Isolera
   ↓
Korrigera
   ↓
Verifiera
   ↓
Dokumentera

Detta håller felsökningen kontrollerad, reproducerbar och kompatibel med LUMS säkerhetsbaslinje.
# 112. Dokumentationsunderhåll

Detta dokument bör uppdateras när ett dokumenterat operativt beteende ändras.

Dokumentationsändringar bör förbli konsekventa med:
text

Säkerhetsdokumentation
Distributionsdokumentation
Agentbeteende
Watcher-beteende
RBAC-modell
Pakethanteringsbeteende
Docker runtime-konfiguration
Testbaslinje

Föråldrade felsökningsinstruktioner kan vara farliga när de rekommenderar utfasade kommandon eller säkerhetsförsvagande lösningar.

När ett produktionsbeteende ändras, uppdatera relevant dokumentation innan felsökningsproceduren anses slutförd.
# 113. Aktuell baslinje

Den aktuella LUMS-baslinjen som dokumenteras i den här felsökningsguiden omfattar:

```text
Agent version: 1.7.0
Watcher version: 1.2.1

Application port:
127.0.0.1:5050

Database:
SQLite

SQLite journal mode:
WAL (enabled by server/init_db.py; verify on your database with
sqlite3 <db> "pragma journal_mode;")

SQLite busy timeout:
5000 ms

SQLite synchronous:
2

SQLite foreign keys:
Enabled by the application

Container:
Non-root
Read-only root filesystem
Capabilities dropped
no-new-privileges enabled
Privileged mode disabled

RBAC:
Administrator
Operator
Viewer

Viewer:
Clients + Installed Software only

Full test suite:
Run on Linux (the CI reference is Ubuntu with Python 3.13). Some tests
assume Linux features such as os.geteuid() or an installed apt/pacman and
can fail on Windows; check the CI result for the revision you deploy.
```

Behandla inte baslinjen som bevis för att en viss installation är frisk; verifiera varje värde på målsystemet.

Turvallisuus- ja arkkitehtuuriominaisuudet ovat tärkeä perustaso.

# 114. Fallgropar i startkonfigurationen

**Symtom:** Containern avslutas omedelbart eller använder en annan databas/säkerhetskopieringskatalog än Docker-volymen antyder.

**Fakta från koden (`server/app.py`):**

- Utan hemlighet utlöser applikationen `RuntimeError: LUMS secret is not configured. Provide LUMS_SECRET_KEY_FILE or LUMS_SECRET_KEY.`
- Om filen i `LUMS_SECRET_KEY_FILE` saknas används `LUMS_SECRET_KEY` som reserv. Endast en saknad fil hanteras så; en oläsbar fil kan orsaka filsystemfel.
- `LUMS_DB_PATH` och `LUMS_BACKUP_DIR` åsidosätter `/var/lib/lums/lums.db` och `/var/backups/lums`. En inaktuell åsidosättning kan peka LUMS bort från den monterade volymen.

**Kontrollera (skrivskyddat):**

```text
docker compose logs lums | grep "LUMS secret"
docker inspect lums --format '{{range .Config.Env}}{{println .}}{{end}}'
ls -l <secret file>   # permissions only; never print the contents
```

Korrigera hemlig sökväg/behörigheter eller ta bort inaktuella åsidosättningar. Skapa inte en ersättningshemlighet lättvindigt (avsnitt 82).

---

# 115. Agenten startar inte på grund av kontroller vid import

`lums-agent` kan misslyckas före tokenläsning, exempelvis med `RuntimeError: No supported package manager found. Supported package managers: apt, pacman` eller SSL-fel om CA-filen. `agent/agent.py` identifierar pakethanterare och skapar TLS-kontext vid import. Värdar utan `apt`/`pacman` eller med saknad/oläsbar `LUMS_CA_FILE` misslyckas vid start; samma gäller Windows-testmiljöer. Använd stödd distribution och kontrollera tjänstens `PATH` och CA-filens läsbehörighet.

```text
systemctl status lums-agent --no-pager
journalctl -u lums-agent -n 50 --no-pager
```

---

# 116. Agenten använder fel serveradress (port 5000 jämfört med 5050)

Agentens standard är `LUMS_BASE=http://127.0.0.1:5000`, men containern publiceras på `127.0.0.1:5050`. Exemplen med `5050` gäller serverns publicerade port, inte agentens standard.

```text
systemctl show lums-agent --property=Environment
ss -lntp | grep -E ':5000|:5050'
```

Ange `LUMS_BASE` som den faktiska slutpunkt klienten når (vanligen HTTPS-URL:en). Exponera inte port `5050` offentligt.

---

# 117. Watchern avslutas med status 1

Watchern kan logga `CLIENT LOOKUP FAILED`, `RUNNING JOB LOOKUP FAILED`, `JOB LOOKUP FAILED`, `IDLE CHECK FAILED`, `JOB CLAIM FAILED` eller `UPDATE EXECUTION FAILED`. Den körs en gång: loggar fel, avslutas med status 1 och försöker inte igen förrän nästa timerstart. Endast jobb med exakt status `running` återupptas; annars söks väntande jobb. `NO UPDATE JOB // SYSTEM CLEAN` är normalt.

```text
journalctl -u lums-watcher -n 100 --no-pager
systemctl status lums-watcher lums-watcher.timer
```

Åtgärda API-, token-, inaktivitets- eller pakethanterarlåsproblem. Granska jobb via gränssnitt/API; redigera aldrig SQLite manuellt.

---

# 118. Värduppdateraren loggar heartbeat-fel

`lums-host-updater` fångar loopfel och försöker igen. Vanliga orsaker (`host_updater/agent.py`): tokenfil saknas eller är under 32 tecken (`Host-updater token is missing or too short`); fel loopback-URL (`Only a loopback LUMS endpoint is permitted`: `http`/`https`, exakt värd `127.0.0.1`, port krävs, inga autentiseringsuppgifter/fråga/fragment, t.ex. `http://127.0.0.1:5050`); HTTP `401` / `host_updater_authentication_required` = ogiltig Bearer-token; HTTP `503` / `host_updater_not_configured` = servertoken saknas. Om svaret inte uttryckligen anger `update_execution_enabled: false` avslutas tjänsten med `Unexpected update-execution state; stopping` (status 1); kontrollera versionsmatchning.

```text
journalctl -u lums-host-updater -n 100 --no-pager
systemctl show lums-host-updater --property=Environment
stat /etc/lums-host-updater/token
```

Visa inte tokenen. Korrigera filägarskap/läge och URL, starta sedan om tjänsten en gång.

---

# 119. Begäranden till larmintegrationer returnerar 501

E-post-, Slack-, PagerDuty- eller webhookkonfiguration/test/borttagning returnerar `501` med `Notification integrations are disabled pending secure persistent configuration`. Detta är avsiktligt (`server/alerts_routes.py`): integrationer saknas, `POST /alerts/clear-all` returnerar också `501` och regler utvärderas inte automatiskt. Försök inte igen och ange inga leverantörshemligheter.

Routningarna kräver `alerts.manage` och CSRF. Saknad/felaktig CSRF-token ger först `403` med `csrf_validation_failed`. Inaktivera inte CSRF. Se `docs/LUMS_REALTIME_ALERTING_IMPLEMENTATION.md`.

---

# 120. Inloggningsfel: CSRF, hastighetsbegränsning och låsning

Ett giltigt lösenord kan avvisas efter flera försök; loggen kan visa `login.rate_limit`. Försök begränsas per användarnamn och källa och lagras i SQLite (`login_rate_limits`, `locked_until`) även efter omstart. `/login` undantas från CSRF-kontrollen; kontrollera autentiseringsuppgifter, cookies och begränsningen.

```text
sqlite3 /var/lib/lums/lums.db "select rate_limit_key, locked_until from login_rate_limits;"
```

Vänta tills låsningen upphör och åtgärda orsaken. Radera inte rader manuellt och överbelasta inte inloggningen för test.

---

# 121. SQLite är upptagen eller migreringar träffar fel databas

Skrivningar kan misslyckas vid konkurrens, eller så kan en migrering lyckas utan att servern får nya tabeller/funktioner. `PRAGMA busy_timeout = 5000` väntar högst fem sekunder. Databasen använder WAL (`server/init_db.py`); `-wal` och `-shm` är normala. Migreringar läser sin egen `LUMS_DB_PATH` och kan ändra en annan fil.

```text
sqlite3 /var/lib/lums/lums.db "pragma busy_timeout; pragma journal_mode;"
docker inspect lums --format '{{range .Config.Env}}{{println .}}{{end}}'
```

Stoppa konkurrerande process, behåll WAL/SHM och rikta migreringsmiljön rätt. Radera aldrig sidofilerna.

---

# 122. Återställningen vägrar köra (WAL/SHM finns)

Återställningen avbryts med `Restore verweigert: SQLite-WAL/SHM-Datei vorhanden.` (meddelandet är tyskt i koden). `server/database_backup.py` avbryter säkert när måldatabasens sidofiler finns, så att gammal och ny data inte blandas.

Kontrollera: `find /var/lib/lums -maxdepth 1 -type f -name 'lums.db*'`

Stoppa/pausa applikationen och använd dokumenterad återställning. Ta aldrig bort sidofiler manuellt.

---

# 123. Fel vid ögonblicksbild och releaseverifiering

(`scripts/volume_snapshot.py`, `scripts/release_verification.py`)

| Meddelande | Betydelse |
| --- | --- |
| `Could not create or publish the snapshot.` | Målet finns redan eller kan inte skrivas; ögonblicksbilder skrivs inte över. |
| `Source tree changed during snapshot creation.` | Filer ändrades under kopiering; pausa skrivningar och försök igen. |
| `Invalid snapshot filename.` / `Invalid restore target.` | Osäker sökväg eller filnamn avvisades. |
| `Duplicate restore target: ...` | Arkivet har dubbla poster; använd arkiv från det stödda verktyget. |
| Kontrollsummedata får releaseverifieringen att misslyckas | Metadata är högst 4096 byte; hämta officiell kontrollsummefil i stället för att kringgå verifiering. |

Återställning utan root tillämpar inte godtyckligt arkiverat ägarskap. Kör som avsedd tjänsteanvändare, inte som root. Lista arkivet med `tar -tf` utan att extrahera.

# 124. Slut på felsökningsguiden

LUMS-felsökning bör förbli evidensbaserad och säkerhetsmedveten.

Om du är osäker:

```text
Preserve the state.
Inspect the evidence.
Identify the failing layer.
Make the smallest safe change.
Verify the result.
Document what happened.
```

Kompromissa inte med säkerhet eller dataintegritet för en snabb lösning.

Slut på LUMS felsökningsguide
