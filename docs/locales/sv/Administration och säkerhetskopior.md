
# LUMS — Administrationshandbok

> **Linux-uppdateringshantering utan bruset.**

Den här handboken beskriver den dagliga administrationen och driften av LUMS efter det att servern och klienterna har installerats.

Den fokuserar på administrativa uppgifter som utförs via LUMS webbgränssnitt samt på kontrollerade driftuppgifter på LUMS-servern och hanterade klienter.

Installationsprocedurer dokumenteras separat i `install.md`.

Felsökningsprocedurer dokumenteras separat i `troubleshooting.md`.

Säkerhetsarkitektur och revisionsinformation dokumenteras separat i `security.md`.

---

## Komma igång: Daglig administration

Den här handboken riktar sig till den person som ansvarar för en befintlig LUMS-installation.
De detaljerade tekniska avsnitten är underhållna på engelska. Börja med dessa
termer:

* **Användarkonto:** bestämmer vad en person kan göra i LUMS webbgränssnitt.
  Dela inte konton; ge varje person ett eget konto.
* **Klient:** en hanterad Linux-dator. Dess klienttoken är en hemlighet och är inte
  samma sak som ett lösenord för webbkontot.
* **Uppdateringsjobb:** en begärd åtgärd som agenten hämtar och kör
  med APT eller pacman på måldatorn. Kontrollera målet och paketen
  innan du startar det.
* **Säkerhetskopia:** en separat, verifierad kopia av databasen. En kopia i samma
  Docker-volym skyddar inte mot förlust av den volymen.
* **Uppgradering:** ersätter containerversionen, inte databasen. En normal
  uppgradering får inte ta bort eller återskapa `lums-data`.

### Säker checklista före en ändring

1. Kontrollera om uppdateringsjobb körs och om ett underhållsfönster behövs.
2. Bekräfta att en färsk, användbar säkerhetskopia av databasen finns.
3. Dokumentera den körande avbilden, containerinställningarna och datasökvägarna.
4. Bygg och testa den nya avbilden innan du stoppar den aktiva containern.
5. Ersätt containern med samma data-, hemlighets- och säkerhetskopieringsmonteringar samt
   samma säkerhetsalternativ.
6. Kontrollera containerstatus, loggar, HTTPS-inloggning och data efter start.
7. Behåll den gamla containern som återställningsalternativ tills den nya versionen har
   verifierats.

**Kör inte** `docker volume rm lums-data`, `docker system prune --volumes`
eller andra raderingskommandon som en del av en normal uppgradering. De kan permanent
ta bort data. Om du är osäker på vilken container eller sökväg som är aktiv, stanna och
inspektera den aktuella installationen först; kopiera inte ett exempelkommando utan att
kontrollera det.

---

## 1. Administrationsöversikt

LUMS tillhandahåller centraliserad administration av Linux-programvaruinventering, tillgängliga uppdateringar, paketoperationer, uppdateringsjobb, hanterade klienter, användare och drifthistorik.

Administrationsgränssnittet tillhandahåller tre rollmallar:

* **Administratör**
* **Operatör**
* **Läsare**

När ett konto skapas fyller den valda rollen i en rekommenderad uppsättning
behörigheter. Administratörer kan justera dessa behörigheter per användare; de sparade
behörigheterna, snarare än rollens etikett, avgör åtkomsten.

LUMS separerar också server-sidans administrativa operationer från klientsidans paketkörning.

Det normala driftflödet är:

```text
Administratör / Operatör
        │
        ▼
   LUMS webbgränssnitt
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
   Hanterad klient
        │
        ▼
 APT / pacman / system
        │
        ▼
      Resultat
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
```
* Webbgränssnitt

LUMS-servern kör inte pakethanteringskommandon direkt på hanterade klienter.

Paketoperationer utförs av LUMS-agenten som är installerad på det hanterade systemet.
## 2. Administrativa ansvarsområden

LUMS-administration kan delas in i flera områden.
Användaradministration

Administratörer hanterar:

* LUMS-användare

* användarroller

* kontostatus

* administrativ åtkomst

Användarhantering kräver behörigheten users.manage.

Administratörsmallen inkluderar denna behörighet som standard.

Operatörer och läsare får den inte som standard.
Klientadministration

Administratörer hanterar:

* registrerade klienter

* klientstatus

* klientautentisering

* klienttoken

* tokenrotation

* aktivering och inaktivering av klienter

Klientadministration kräver behörigheten clients.manage eftersom klientautentisering
avgör vilka system som tillåts rapportera till LUMS.
Uppdateringsadministration

Administratörs- och operatörsmallarna ger behörigheter att:

* visa tillgängliga uppdateringar

* skapa uppdateringsjobb

* köra paketoperationer

* granska uppdateringshistorik

* hantera enskilda paket

* utföra systemuppdateringar

Läsarmallen är skrivskyddad och kan inte utföra uppdateringsoperationer.
Paketadministration

LUMS stöder pakethanteringsoperationer via klientens inbyggda pakethanterare.

Nuvarande pakethanteringsbackends som stöds inkluderar:

* APT/dpkg för Debian-baserade system

* pacman för Arch Linux

LUMS ersätter inte operativsystemets pakethanterare.

Istället tillhandahåller LUMS ett centraliserat gränssnitt för att begära och spåra paketoperationer.
Driftadministration

Administratörer och operatörer kan behöva övervaka:

* pågående uppdateringsjobb

* misslyckade jobb

* slutförda jobb

* klientrapportering

* omstartskrav

* pakethanteringsfel

* revisionsaktivitet

De detaljerade felsökningsprocedurerna för dessa tillstånd dokumenteras i troubleshooting.md.
## 3. Administrativa roller

LUMS tillhandahåller för närvarande tre roller.
| Roll | Syfte |
| --- | --- |
| Administratör | Fullständig administrativ kontroll |
| Operatör | Daglig operativ hantering |
| Läsare | Skrivskyddad klient- och programvarusyn |

Varje roll är en behörighetsmall. Kontots individuellt sparade
behörigheter tillämpas på serversidan.

Att dölja ett gränssnittselement anses därför inte i sig vara en säkerhetskontroll.

Obehöriga API-operationer måste också avvisas av servern.
## 4. Administratör

Administratörsmallen tillhandahåller som standard hela uppsättningen av LUMS applikationsbehörigheter.

Administratörer kan:

* visa hanterade klienter

* visa installerad programvara

* visa tillgängliga uppdateringar

* skapa och köra uppdateringsjobb

* granska uppdateringshistorik

* utföra pakethanteringsoperationer

* utföra systemunderhåll

* skapa klienter

* inaktivera klienter

* rotera klienttoken

* skapa och hantera LUMS-användare

* tilldela rollmallar och individuella behörigheter

Fullständiga behörigheter enligt administratörsmallen bör endast beviljas användare som
behöver dem.

Administrativa konton bör inte användas för rutinmässig skrivskyddad övervakning när ett operatörs- eller läsarkonto är tillräckligt.
## 5. Operatör

Operatörsmallen är avsedd för daglig uppdaterings- och systemadministration.

Operatörer kan:

* visa hanterade klienter

* visa installerad programvara

* visa tillgängliga uppdateringar

* skapa och köra uppdateringsjobb

* granska uppdateringshistorik

* utföra pakethanteringsoperationer

* utföra systemunderhåll

Operatörsmallen ger inte:

* skapa eller hantera LUMS-användare

* tilldela användarroller

* skapa eller inaktivera klienter

* rotera klienttoken

Denna standardseparering möjliggör rutinmässiga uppdateringsoperationer utan att bevilja
konto- och klienthanteringsprivilegier. Individuella beviljanden kan ändras av
en användare med users.manage.
## 6. Läsare

Läsarmallen tillhandahåller skrivskyddad insyn.

Läsare kan:

* visa hanterade klienter

* visa installerad programvara

Läsarmallen ger inte följande administrativa funktioner:

* hantering av tillgängliga uppdateringar

* skapande av uppdateringsjobb

* körning av uppdateringsjobb

* uppdateringshistorik

* pakethantering

* systemunderhåll

* användarhantering

* klienthantering

* tokenrotation

Motsvarande muterande API-operationer skyddas också på serversidan.

Läsaråtkomst är därför avsedd för användare som behöver insyn utan operativ kontroll.
## 7. Riktlinjer för rollval

Använd den minsta roll som ger den funktionalitet som krävs.
Administratör

Används när användaren måste hantera:

* användare

* roller

* klienter

* klientautentisering

* token

* uppdateringar

* paket

* systemoperationer

Operatör

Används när användaren behöver utföra rutinmässigt operativt arbete såsom:

* kontrollera uppdateringar

* installera paket

* ta bort paket

* uppdatera paket

* köra uppdateringsjobb

* granska jobbhistorik

Läsare

Används när användaren endast behöver insyn i:

* klienter

* installerad programvara

## 8. Administrativ säkerhetsprincip

LUMS-administration följer principen om minsta behörighet.

Administrativ åtkomst bör begränsas till den funktionalitet som krävs för användarens uppgift.

I synnerhet:

* använd inte administratörskonton för rutinmässig visning

* dela inte konton mellan administratörer

* dela inte klienttoken

* placera inte autentiseringsuppgifter i dokumentation

* exponera inte klienttoken i skärmdumpar eller loggar

* kringgå inte LUMS webbgränssnitt genom att ändra databasen direkt om inte en dokumenterad återställningsprocedur uttryckligen kräver det

När en administrativ operation misslyckas, undersök orsaken innan du ändrar beständigt tillstånd.

Använd principen:

* Observera först. Ändra sedan. Verifiera sist.

## 9. Administrativt arbetsflöde

Ett normalt administrativt arbetsflöde bör följa denna sekvens:
text

1. Autentisera
* │
* ▼
2. Verifiera roll
* │
* ▼
3. Välj klient / operation
* │
* ▼
4. Granska aktuellt tillstånd
* │
* ▼
5. Utför nödvändig operation
* │
* ▼
6. Övervaka jobb
* │
* ▼
7. Verifiera resultat
* │
* ▼
8. Granska historik / revisionsinformation

Administrativa åtgärder bör alltid verifieras efter utförandet.

En lyckad API-begäran bevisar inte i sig att den begärda paket- eller systemoperationen slutfördes framgångsrikt.

Det slutliga tillståndet som rapporteras av den hanterade klienten är det relevanta operativa resultatet.
## 10. Uppdelning av dokumentation

LUMS dokumentationsuppsättning är avsiktligt uppdelad i separata drifthandböcker.
| Dokument | Syfte |
| --- | --- |
| install.md | Installation och initial driftsättning |
| administration.md | Daglig administration |
| security.md | Säkerhetsarkitektur och revisionsresultat |
| troubleshooting.md | Diagnos och återställning |

Den här handboken bör därför undvika att duplicera detaljerade installations- och felsökningsprocedurer.

Istället beskriver den vad administratörer kan hantera, vad varje operation innebär och hur normala administrativa arbetsflöden utförs.
## 11. Användarhantering

Användarhantering är tillgänglig för användare med behörigheten users.manage.

Administratörer kan skapa och hantera LUMS applikationskonton via det dedikerade användarhanteringsgränssnittet.

Användarkonton är separata från autentisering av hanterade klienter.

En LUMS-användare autentiserar sig mot webbapplikationen med ett applikationskonto.

En hanterad klient autentiserar sig mot LUMS API med en klienttoken.

Dessa autentiseringsmekanismer får inte förväxlas.
text

LUMS-användare
* │
* │ användarnamn + lösenord
* ▼
Webbgränssnitt
* │
* ▼
LUMS-applikation

Hanterad klient
* │
* │ klienttoken
* ▼
LUMS API

## 12. Skapa användare

Användare med users.manage kan skapa nya LUMS-användare.

När en användare skapas anger administratören:

* användarnamn

* lösenord

* en rolletikett, med en rollmall tillgänglig för senare behörighetstilldelning

Tillgängliga rollmallar är:

## administrator

## operator

## viewer

Servern validerar de angivna värdena innan kontot skapas.

Nya konton startar utan behörigheter. Efter skapandet kan administratörer
tilldela individuella kryssrutor eller tillämpa en av rollmallarna. Att tillämpa en
mall förväljer dess standardbehörigheter, som sedan kan anpassas.
Tillgängliga behörigheter är:
| Behörighet | Åtkomst som beviljas |
| --- | --- |
| clients.view | Visa klientlistan och systeminformation |
| software.view | Visa installerad programvara |
| updates.view | Visa uppdateringar, jobb och uppdateringshistorik |
| packages.search | Sök i paketförråd |
| jobs.manage | Skapa paketoperationer och uppdateringsjobb |
| clients.manage | Registrera/ta bort klienter och rotera klienttoken |
| users.manage | Skapa användare och hantera roller, behörigheter och interna anteckningar |
| backups.manage | Skapa och inspektera databassäkerhetskopior |

Klientrelaterade behörigheter kräver clients.view; jobs.manage kräver också
updates.view. LUMS förhindrar att det sista aktiva kontot med
users.manage tas bort, så att administratörer inte av misstag låser sig ute.

Lösenord lagras inte i klartext.

LUMS använder Argon2-baserad lösenordshashning för applikationsuppgifter.

Efter skapandet, verifiera att:

* användarnamnet visas i användarlistan

* rollmallen och de individuella behörigheterna är korrekta

* kontot är aktiverat

* användaren kan autentisera sig framgångsrikt

Skicka inte lösenord via dokumentation, ärenden, skärmdumpar eller andra osäkra kanaler.
Databassäkerhetskopieringsgränssnitt

Användare med behörigheten backups.manage kan skapa SQLite-säkerhetskopior från
Datenbank-Backups. Administratörskonton får denna behörighet genom
migration 005-backup-permission; nya konton får den genom att tillämpa
Administratörsmallen eller kan beviljas den uttryckligen.

Gränssnittet stöder inbyggda .db- och komprimerade .db.gz-filer. Det använder
SQLites online-backup-API, validerar den färdiga databasen och lagrar filer
med endast ägarbehörighet. Användargränssnittet listar de tio nyaste filerna. Säkerhetskopior
krypteras inte, raderas inte automatiskt, schemaläggs inte, laddas inte ner och återställs inte av
LUMS; administratörer med backups.manage kan radera enskilda säkerhetskopior från
listan efter bekräftelse. Skydda destinationen i enlighet med detta.

Basmålkatalogen är fastställd av serverns LUMS_BACKUP_DIR-inställning. Gränssnittet tillåter val av en relativ underkatalog under denna
bas och skapar den vid behov; absoluta sökvägar, överordnad traversering och
symboliska länkade underkataloger avvisas. Värdens sökvägar måste monteras in i Docker
av serveradministratören. För en Docker-driftsättning, skapa en separat värdkatalog
skrivbar av containerns UID/GID 10001:

```bash
sudo install -d -o 10001 -g 10001 -m 0700 /var/backups/lums
```

Lägg till dessa alternativ i LUMS containerkonfiguration:

```bash
-v /var/backups/lums:/var/backups/lums \
-e LUMS_BACKUP_DIR=/var/backups/lums \
```

Använd en separat disk eller fjärrlagring för motståndskraft mot värd fel.
Till exempel, montera en NAS på Debian-värden först och använd sedan den monterade sökvägen
som vänster sida av Docker-bindmonteringen. Säkerhetskopieringsgränssnittet visar
container-sidans baskatalog; den valda relativa sökvägen ligger under den.
Säkerhetskopieringsdestinationen måste vara tillgänglig och skrivbar inuti containern;
annars rapporterar gränssnittet att säkerhetskopieringslagring är otillgänglig.

För återställningssteg, se server/static/backup-restore.md.
## 13. Användarroller

Välj en rollmall enligt minsta nödvändiga behörighet, granska sedan
de individuella behörigheterna för varje konto.
| Rollmall | Användarhantering | Klienthantering | Uppdateringar | Pakethantering | Skrivskyddad åtkomst |
| --- | --- | --- | --- | --- | --- |
| Administratör | Ja | Ja | Ja | Ja | Ja |
| Operatör | Nej | Nej | Ja | Ja | Ja |
| Läsare | Nej | Nej | Nej | Nej | Ja |

Dessa är standardvärden, inte fasta gränser. Administratörer kan anpassa varje
användares behörighetsuppsättning. Rolltillämpning sker på servern genom
de resulterande per-användarbehörigheterna.

Webbgränssnittet återspeglar den tilldelade rollen, men servern förblir den auktoritativa säkerhetsgränsen.
## 14. Inaktivera användarkonton

När ett konto inte längre ska tillåtas komma åt LUMS, inaktivera kontot istället för att dela eller återanvända autentiseringsuppgifterna.

Exempel inkluderar:

* en administratör som lämnar projektet

* en operatör som inte längre behöver åtkomst

* tillfälligt borttagande av administrativ åtkomst

* säkerhetsåtgärd vid ett komprometterat konto

Efter inaktivering av ett konto, verifiera att autentisering avvisas.

Befintliga autentiserade sessioner bör också beaktas vid kontosäkerhetsutredningar.

Ändra inte users-tabellen manuellt om inte en dokumenterad återställningsprocedur uttryckligen kräver databasnivåingripande.
## 15. Lösenordsadministration

Lösenord är applikationsuppgifter och måste behandlas som känslig information.

Administratörer bör säkerställa att:

* lösenord inte delas

* lösenord inte lagras i Git

* lösenord inte placeras i dokumentation

* lösenord inte ingår i skärmdumpar

* lösenord inte skrivs in i skalkhistoriken i onödan

* användare får sina autentiseringsuppgifter via en lämplig säker kanal

LUMS lagrar lösenordshashar istället för klartextlösenord.

Om ett lösenord misstänks vara komprometterat, ersätt det genom lämplig kontohanteringsprocedur istället för att försöka återställa det ursprungliga lösenordet.
## 16. Sessioner

LUMS använder autentiserade applikationssessioner för webbåtkomst.

Sessionshantering är en del av applikationens säkerhetsgräns.

Administratörer bör behandla en oväntad autentiserad session som en säkerhetshändelse om det associerade kontot inte längre bör ha åtkomst.

Relevanta situationer inkluderar:

* inaktiverat konto som fortfarande verkar aktivt

* oväntad administrativ åtkomst

* misstänkt kompromettering av autentiseringsuppgifter

* oväntad webbläsarsession

* säkerhetsutredning

För detaljerad felsökning av sessioner och autentisering, se troubleshooting.md.
## 17. Inloggningshastighetsbegränsning

LUMS tillämpar hastighetsbegränsning för upprepade misslyckade inloggningsförsök.

Den aktuella utvecklingen är:
| Misslyckade försök | Låsning |
| --- | --- |
| 5 | 30 sekunder |
| 6 | 60 sekunder |
| 7 | 120 sekunder |
| 8+ | 300 sekunder |

Hastighetsbegränsningstillståndet lagras i SQLite.

En framgångsrik inloggning rensar det tillämpliga tillståndet för misslyckade försök.

Upprepade autentiseringsmisslyckanden bör undersökas istället för att kringgå hastighetsbegränsaren.

Möjliga orsaker inkluderar:

* felaktiga autentiseringsuppgifter

* föråldrade sparade autentiseringsuppgifter

* en automatiserad klient som använder felaktiga autentiseringsuppgifter

* upprepade manuella inloggningsförsök

* en möjlig attack mot autentiseringsuppgifter

## 18. Klienthantering

Hanterade klienter är Linux-system som kör LUMS-agenten.

En klient förser LUMS med information såsom:

* klientidentitet

* installerad programvara

* tillgängliga uppdateringar

* pakethanteringsresultat

* uppdateringsjobbresultat

* omstartstillstånd

* driftstatus

LUMS-servern lagrar klienttillståndet och exponerar det via webbgränssnittet.

Klienten utför de faktiska pakethanteringsoperationerna lokalt.
## 19. Klientautentisering

Varje hanterad klient autentiserar sig mot LUMS med en klienttoken.

Token fungerar som en autentiseringsuppgift för den hanterade klienten.

Behandla klienttoken med samma omsorg som lösenord.

Gör aldrig:

* checka in token i Git

* placera token i offentlig dokumentation

* inkludera token i skärmdumpar

* klistra in token i ärendespårare

* exponera token i diagnostisk utdata

* dela en klients token med en annan klient

En token bör endast installeras på den klient för vilken den utfärdades.
## 20. Klientregistrering

En ny klient måste först registreras hos LUMS.

Registreringsprocessen etablerar serverns klientidentitet och autentiseringsuppgift.

Efter registreringen:

* installera LUMS-agenten

* konfigurera klienttoken

* konfigurera LUMS-serverns slutpunkt

* etablera TLS-förtroende

* utför en första agentkörning

* verifiera att klienten rapporterar framgångsrikt

* bekräfta att klienten visas i LUMS-gränssnittet

En klient bör inte anses vara i drift bara för att agenttjänsten startar framgångsrikt.

Servern måste ta emot och acceptera en giltig klientrapport.
## 21. Klientstatus

Klientvyn bör användas för att skilja mellan olika drifttillstånd.

Exempel inkluderar:

* klient registrerad men rapporterar inte

* klient rapporterar normalt

* klient rapporterar inaktuell information

* klient inaktiverad

* klientautentiseringsfel

* klientsidans pakethanteringsfel

När en klient slutar rapportera, avgör först om problemet är:

* nätverksanslutning

* TLS-förtroende

* klientautentisering

* agentkörning

* servertillgänglighet

* server-sidans bearbetning

Undvik att ändra klientens autentiseringsuppgifter innan du fastställt vilket lager som faktiskt misslyckas.
## 22. Klienttokenrotation

Klienttoken kan roteras vid behov.

Typiska skäl inkluderar:

* misstänkt tokenexponering

* policy för rotation av autentiseringsuppgifter

* administrativt underhåll

* ersättning av en klientkonfiguration

* säkerhetsincidenthantering

Tokenrotation ändrar den autentiseringsuppgift som accepteras för klienten.

Efter rotation:

* hämta den nya klienttoken

* uppdatera klientkonfigurationen

* kör agenten

* verifiera framgångsrik autentisering

* verifiera den resulterande klientrapporten

* bekräfta att normal rapportering återupptas

Ta inte bort den gamla klientkonfigurationen förrän den nya autentiseringsvägen har verifierats.
## 23. Inaktivera en klient

En klient kan inaktiveras när den inte längre ska delta i LUMS-operationer.

Exempel inkluderar:

* avveckling av system

* tillfälligt underhåll

* klientbyte

* misstänkt kompromettering av autentiseringsuppgifter

Innan du inaktiverar en klient, kontrollera om aktiva uppdateringsjobb är associerade med den.

Efter inaktivering:

* verifiera att klienten inte längre behandlas som i drift

* granska relevant uppdateringsjobbhistorik

* bevara revisionsinformation som krävs för utredning

Ta inte bort beständiga klientdata bara för att en klient tillfälligt är offline.
## 24. Checklista för klientadministration

När du lägger till eller ändrar en klient, verifiera hela kedjan:
text

[ ] Klienten finns i LUMS
[ ] Klienten är aktiverad
[ ] Klienttoken är giltig
[ ] TLS-förtroende är giltigt
[ ] LUMS-agenten är installerad
[ ] Agentkonfigurationen är giltig
[ ] Första rapporten lyckas
[ ] Klienten visas i webbgränssnittet
[ ] Installerad programvara rapporteras
[ ] Tillgängliga uppdateringar rapporteras
[ ] Uppdateringsjobb kan spåras
[ ] Resultat returneras korrekt

En klient är endast i drift när hela rapporterings- och autentiseringskedjan fungerar.
## 25. Administrativ princip

Användaradministration och klientadministration bör förbli separerade.

Ett LUMS-applikationskonto bestämmer vad en person får göra.

En klienttoken bestämmer vilket hanterat system som får kommunicera med LUMS.
text

Applikationsanvändare
* │
* └── Roll / Behörigheter

Hanterad klient
* │
* └── Klienttoken / Identitet

Använd inte en mekanism som ersättning för den andra.
## 26. Programvaruinventering

LUMS underhåller programvaruinformation som rapporteras av hanterade klienter.

Programvaruinventeringen låter administratörer och operatörer avgöra vilka paket som är installerade på en klient.

Inventeringen samlas in av LUMS-agenten och rapporteras till servern.

Servern gör sedan den rapporterade informationen tillgänglig via klientgränssnittet.

Inventeringen bör behandlas som en ögonblicksbild av klientens rapporterade tillstånd.

Den ersätter inte den inbyggda pakethanteraren.
## 27. Installerad programvara

Avsnittet Installerad programvara visar paket som rapporterats av den valda klienten.

Administratörer och operatörer kan använda det lokala paketfiltret för att begränsa den visade inventeringen.

Filtret för installerad programvara är en lokal gränssnittsfunktion.

Det är separat från pakethanteringssökningen.

Denna distinktion är viktig:
```text

Installerad programvara
    │
    └── Filtrera redan rapporterad paketinventering

Pakethantering
    │
```
* └── Sök i klientens paketförråd

Ett installerat paket kanske därför inte visas i pakethanteringssökningen om det inte längre är tillgängligt i ett konfigurerat förråd.
## 28. Tillgängliga uppdateringar

LUMS samlar också in information om paket för vilka uppdateringar är tillgängliga.

Information om tillgängliga uppdateringar genereras på den hanterade klienten med hjälp av dess inbyggda pakethanteringssystem.

Den rapporterade informationen kan användas för att identifiera paket som kräver uppmärksamhet.

Innan du skapar ett uppdateringsjobb, granska:

* klientidentitet

* paketnamn

* för närvarande installerad version

* tillgänglig version

* paketstatus

* om klienten för närvarande är nåbar

Anta inte att varje tillgänglig uppdatering omedelbart bör installeras.

Driftskrav, underhållsfönster, applikationsberoenden och klienttillstånd bör beaktas innan körning.
## 29. Pakethantering

LUMS tillhandahåller centraliserade pakethanteringsoperationer för Linux-klienter som stöds.

Nuvarande pakethanteringsåtgärder inkluderar:

* INSTALL_PACKAGE

* REMOVE_PACKAGE

* UPDATE_PACKAGE

* UPDATE_SYSTEM

Operationen begärs via LUMS men utförs lokalt av LUMS-agenten.

Agenten delegerar den faktiska paketoperationen till den inbyggda pakethanteraren.
text

LUMS webbgränssnitt
```text
      │
      ▼
LUMS API
      │
      ▼
Uppdateringsjobb
      │
      ▼
LUMS-agent
      │
      ├── APT / dpkg
      │
      └── pacman
```

LUMS förblir därför oberoende av operativsystemets paketdatabas och pakethanteringsimplementation.
## 30. Paketsökning

Gränssnittet Pakethantering tillhandahåller en paketsökning som är separat från filtret för installerad programvara.

Sökningen begär paketinformation från den hanterade klienten.

På Debian-baserade system använder agenten APT-pakethanteringsverktygen.

På Arch Linux använder agenten pacman.

Sökresultat kan innehålla:

* paketnamn

* paketversion

* paketbeskrivning

* förrådsinformation där tillgänglig

Paketsökning installerar ingenting.

En sökning är därför en skrivskyddad operation.
## 31. Installera ett paket

Administratörer och operatörer kan skapa paketinstallationsjobb.

Det normala arbetsflödet är:

* välj den hanterade klienten

* öppna Pakethantering

* sök efter det önskade paketet

* granska resultatet

* välj installationsåtgärden

* skapa jobbet

* övervaka körningen

* verifiera resultatet

* uppdatera eller kontrollera den installerade programvaran igen

Paketet installeras av agenten med den inbyggda pakethanteraren.

Att jobbet skapas framgångsrikt betyder inte att installationen redan har slutförts.

Det slutliga jobbresultatet måste kontrolleras.
## 32. Ta bort ett paket

Borttagning av paket följer samma kontrollerade jobbarbetsflöde.

Innan du tar bort ett paket, verifiera:

* rätt klient

* rätt paket

* avsedd operation

* om annan programvara är beroende av paketet

Efter körning, verifiera det resulterande jobbstatusen och klientens rapporterade programvarutillstånd.

LUMS kringgår inte pakethanterarens beroendehantering.

Den inbyggda pakethanteraren ansvarar fortfarande för att lösa operationen.
## 33. Uppdatera ett paket

Ett specifikt paket kan uppdateras när en uppdatering är tillgänglig.

Arbetsflödet är:
```text

Tillgänglig uppdatering
      │
      ▼
Granska paket
      │
      ▼
Skapa UPDATE_PACKAGE-jobb
      │
      ▼
Agentkörning
      │
      ▼
```
Resultatvalidering

LUMS validerar paketinformationen innan det motsvarande uppdateringsjobbet skapas.

Om paketet inte längre listas som uppdateringsbart, bör jobbbegäran inte behandlas som en giltig uppdateringsoperation.

Detta förhindrar att inaktuell uppdateringsinformation körs blint.
## 34. Uppdatera systemet

UPDATE_SYSTEM utför en bredare systemuppdatering med klientens inbyggda pakethanteringsmekanism.

Denna operation påverkar mer än ett paket och bör därför behandlas som en underhållsoperation.

Innan du startar en systemuppdatering, verifiera:

* klienttillgänglighet

* underhållsfönster

* för närvarande körande jobb

* pakethanterarens tillstånd

* tillgängligt diskutrymme där det är relevant

* om en omstart kan krävas

Efter uppdateringen, verifiera:

* jobbresultat

* klientrapport

* installerad programvara

* tillgängliga uppdateringar

* omstartstillstånd

## 35. Uppdateringsjobb

Alla muterande paket- och uppdateringsoperationer representeras som LUMS-uppdateringsjobb.

Detta ger en gemensam körnings- och spårningsmodell.

Typisk jobblivscykel:
```text

PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► FAILED
   │
   ▼
SUCCESS
```

Ett jobb kan också kräva ytterligare hantering när klienten blir otillgänglig eller körningen avbryts.

Jobbhistoriken bör användas som den auktoritativa operativa posten snarare än att enbart förlita sig på den aktuella klientvyn.
## 36. Skapa jobb

Innan du skapar ett uppdateringsjobb, verifiera den avsedda operationen noggrant.

Kontrollera:

* klient

* åtgärd

* paket

* målversion där tillämpligt

* aktuellt pakettillstånd

* underhållskrav

Åtgärder som stöds inkluderar:
| Åtgärd | Syfte |
| --- | --- |
| INSTALL_PACKAGE | Installera ett paket |
| REMOVE_PACKAGE | Ta bort ett paket |
| UPDATE_PACKAGE | Uppdatera ett specifikt paket |
| UPDATE_SYSTEM | Utför en systemomfattande uppdatering |

Skapande av uppdateringsjobb är begränsat till Administratör- och Operatör-roller.

Läsare kan inte skapa uppdateringsjobb.
## 37. Jobbkörning

Efter skapandet bearbetas jobbet av LUMS-agenten.

Agenten tar emot jobbet och utför den begärda operationen lokalt.

Servern spårar det resulterande tillståndet.

Agenten behandlar inte en framgångsrik HTTP-begäran som bevis på att paketoperationen lyckades.

Istället returneras det faktiska pakethanteringsresultatet till LUMS.

Denna distinktion är viktig:
text

API-begäran accepterad
  * ≠
Paketoperation framgångsrik

Det slutliga körningsresultatet måste därför alltid kontrolleras.
## 38. Jobbresultat

Ett slutfört jobb bör innehålla ett explicit resultat.

Relevanta utfall inkluderar:

* framgångsrik körning

* misslyckad körning

* pakethanteringsfel

* avbruten körning

* återställningsrelaterat tillstånd

* omstartsrelaterat tillstånd där tillämpligt

Administratörer och operatörer bör inspektera resultatet när ett jobb misslyckas istället för att omedelbart upprepa samma operation.

Upprepad körning utan att förstå det ursprungliga felet kan göra diagnosen svårare.
## 39. Jobbhistorik

Uppdateringshistoriken tillhandahåller en operativ post över tidigare uppdateringsaktivitet.

Använd den för att besvara frågor som:

* Har detta paket redan uppdaterats?

* Vilken klient utförde operationen?

* När skapades jobbet?

* När började körningen?

* När avslutades körningen?

* Lyckades operationen?

* Rapporterade pakethanteraren ett fel?

Historisk jobbinformation är särskilt viktig vid utredning av upprepade fel eller avbrutna underhållsoperationer.
## 40. Misslyckade jobb

När ett jobb misslyckas:

* registrera klienten och jobb-ID

* inspektera jobbresultatet

* avgör om felet uppstod på servern eller klienten

* inspektera relevanta agentloggar

* inspektera den inbyggda pakethanterarens tillstånd

* åtgärda det underliggande problemet

* försök igen först efter att orsaken är förstådd

Vanliga orsaker inkluderar:

* otillgängliga förråd

* pakethanterarens lås

* nätverksproblem

* ogiltiga paketbegäranden

* beroendekonflikter

* otillräckligt diskutrymme

* avbrutna paketoperationer

* klientautentiserings- eller kommunikationsproblem

Detaljerade diagnostiska procedurer dokumenteras i troubleshooting.md.
## 41. Pakethanterarens lås

APT och pacman kan förhindra samtidiga paketoperationer.

Om en pakethanteringsoperation misslyckas eftersom pakethanteraren redan används:

* identifiera den aktiva pakethanteringsprocessen

* avgör vilken operation som körs

* vänta på att den legitima operationen slutförs när det är lämpligt

* försök igen med LUMS-operationen efteråt

Ta inte bort pakethanterarens låsfiler blint medan pakethanteraren körs.

Att ta bort en låsfil löser inte den underliggande samtidiga operationen och kan skada pakethanteringstillståndet.
## 42. Inaktivitetsmedveten körning

LUMS kan använda klientens inaktiv information när det avgörs om ett uppdateringsjobb ska köras.

Denna mekanism är avsedd att undvika att avbryta aktiv interaktiv användning av ett hanterat system.

Inaktivitetsdetektering utförs av agenten på klienten.

Om inaktivitetsinformation inte är tillgänglig måste agenten rapportera det tillståndet istället för att hitta på ett inaktivt tillstånd.

Administratörer bör skilja mellan:

* klienten är inaktiv

* klienten är aktiv

* inaktivitetsdetektering otillgänglig

* klienten onåbar

Dessa tillstånd har olika operativ betydelse.
## 43. Övervakning av uppdateringskörning

Under underhåll, övervaka:

* jobbstatus

* klientanslutning

* agentaktivitet

* pakethanteringsresultat

* omstartskrav

Anta inte att ett jobb som förblir i RUNNING på obestämd tid betyder att pakethanteraren fortfarande arbetar.

Om körningen verkar fastna, undersök klientens och agentens tillstånd innan du skapar ett nytt jobb.
## 44. Omstartskrav

Vissa paket- och systemuppdateringar kan kräva en omstart.

LUMS spårar omstartsrelaterat tillstånd som rapporteras av den hanterade klienten.

Efter en systemuppdatering:

* inspektera det rapporterade omstartstillståndet

* avgör om en omstart krävs

* utför omstarten under ett lämpligt underhållsfönster

* låt agenten rapportera igen

* verifiera att klienten återgår till normal drift

Ett omstartskrav bör inte automatiskt tolkas som ett uppdateringsfel.
## 45. Checklista för operativa uppdateringar

För rutinmässigt paketunderhåll:
text

[ ] Rätt klient vald
[ ] Klienten är nåbar
[ ] Aktuellt programvarutillstånd granskat
[ ] Tillgängliga uppdateringar granskade
[ ] Rätt paket/åtgärd vald
[ ] Underhållskrav kontrollerade
[ ] Uppdateringsjobb skapat
[ ] Jobbkörning övervakad
[ ] Jobbresultat verifierat
[ ] Installerad programvara verifierad
[ ] Tillgängliga uppdateringar kontrollerade igen
[ ] Omstartstillstånd kontrollerat
[ ] Jobbhistorik granskad vid behov

Operationen är endast slutförd efter att det resulterande klienttillståndet har verifierats.
## 46. Princip för pakethantering

LUMS tillhandahåller centraliserad orkestrering och insyn.

Det hanterade operativsystemet ansvarar fortfarande för den faktiska pakethanteringen.

Därför:

* LUMS begär och spårar operationen. Den inbyggda pakethanteraren utför den.

Denna separation gör det möjligt för LUMS att hantera olika Linux-system samtidigt som pakethanteringens semantik för varje operativsystem bevaras.
## 47. Jobbåterställning

LUMS är utformat för att hantera avbrutna uppdateringsjobb utan att blint upprepa operationer som redan har slutförts framgångsrikt.

Uppdateringskörning använder kontrollpunktsinformation för att spåra framsteg.

Detta är särskilt viktigt när:

* agenten avbryts

* klienten startar om

* servern startas om

* nätverkskommunikationen tillfälligt är otillgänglig

* en paketoperation slutförs innan resultatet rapporteras

Återställningsmekanismen använder det registrerade jobbtillståndet för att avgöra vilket arbete som fortfarande behöver utföras.
## 48. Kontrollpunkter på paketnivå

Jobb som innehåller flera paketoperationer bearbetas individuellt.

En framgångsrik paketoperation registreras innan agenten fortsätter till nästa operation.

Konceptuellt:
text

Jobb
 │
 ├── Paket A → SUCCESS
 │
 ├── Paket B → SUCCESS
 │
 ├── Paket C → avbruten
 │
 └── Paket D → PENDING

Efter återställning bör redan slutförda paketoperationer inte köras igen i onödan.

Det återstående arbetet kan sedan fortsätta från det registrerade tillståndet.

Detta minskar risken för att upprepa paketoperationer efter ett avbrott.
## 49. Avbrutna jobb

När ett uppdateringsjobb avbryts, skapa inte omedelbart ett ersättningsjobb.

Avgör först:

* vilket jobb som avbröts

* vilken paketoperation som var aktiv

* vilka paketoperationer som redan lyckades

* om pakethanteraren slutförde operationen

* om agenten återställde jobbet automatiskt

* om klienten kräver en omstart

Den befintliga jobbhistoriken och agentloggarna bör inspekteras innan manuellt ingripande.
## 50. Agentåterställning

Agenten ansvarar för att fortsätta återställbart arbete efter ett avbrott.

Återställning bör bevara framgångsrika paketresultat där det är möjligt.

Om en paketoperation redan är registrerad som framgångsrik får återställningen inte blint köra samma operation igen.

Om återställningen inte säkert kan fastställa tillståndet för en operation, bör tillståndet behandlas som ett operativt problem och undersökas.

Ändra inte jobbstatusar manuellt i databasen bara för att få ett jobb att verka slutfört.
## 51. Serveromstart under ett jobb

En omstart av LUMS-servern betyder inte nödvändigtvis att klientsidans paketoperation avbröts.

Servern och klienten har separata körningstillstånd.

Efter en serveromstart:

* verifiera att LUMS-containern körs

* verifiera databastillgänglighet

* verifiera att klienten kan kommunicera med LUMS

* inspektera berörda uppdateringsjobb

* kontrollera agentrapporter

* verifiera det slutliga pakettillståndet

Klientsidans körningsresultat förblir den viktiga källan till sanning för paketoperationen.
## 52. Klientomstart under ett jobb

En klientomstart kan avbryta agentkörningen eller inträffa eftersom uppdateringen själv kräver en omstart.

Dessa situationer måste särskiljas.
Förväntad omstart

Uppdateringen slutfördes och systemet kräver en omstart.
Oväntat avbrott

Systemet startade om innan operationen slutfördes eller innan resultatet kunde rapporteras.

Efter att klienten återvänder:

* låt agenten starta normalt

* verifiera kommunikation med LUMS

* inspektera det berörda jobbet

* verifiera pakettillståndet

* kontrollera omstartstillståndet

* låt återställningen fortsätta när det är tillämpligt

## 53. Omstartsdetektering

LUMS kan spåra omstartskrav som rapporteras av den hanterade klienten.

Omstartsdetektering är inte samma sak som att upptäcka om maskinen för närvarande är nåbar.

Dessa är separata tillstånd:
text

Klienten nåbar
  * │
  * ├── omstart krävs inte
  * │
  * └── omstart krävs

Klienten onåbar
  * │
  * └── aktuellt tillstånd kan inte bekräftas

Administratörer bör därför undvika att behandla en onåbar klient som bevis på att en omstart krävs.
## 54. Verifiering efter omstart

Efter en nödvändig omstart:

* vänta tills operativsystemet blir tillgängligt

* verifiera agenttjänsten eller timern

* verifiera klientautentisering

* verifiera klientrapporten

* inspektera det berörda uppdateringsjobbet

* verifiera installerade paketversioner

* verifiera tillgängliga uppdateringar

* kontrollera om ytterligare en omstart krävs

En omstart bör endast anses operativt slutförd efter att klienten har rapporterat framgångsrikt igen.
## 55. Övervakning av uppdateringsjobb

Administratörer och operatörer bör övervaka jobb under planerat underhåll.

Viktiga tillstånd inkluderar:
| Tillstånd | Betydelse |
| --- | --- |
| PENDING | Jobbet finns men körningen har inte startat |
| RUNNING | Jobbkörning pågår |
| SUCCESS | Körningen slutfördes framgångsrikt |
| FAILED | Körningen slutfördes med ett fel |

Ett jobbtillstånd bör alltid tolkas tillsammans med dess resultatinformation.

Till exempel bör ett FAILED-jobb undersökas med hjälp av dess registrerade resultat istället för att bara försöka igen.
## 56. Execution Watcher

LUMS-agenten inkluderar en dedikerad execution watcher.

Watchern ansvarar för att övervaka uppdateringsjobbkörning på klienten.

Dess syfte är att stödja tillförlitlig körningshantering oberoende av rapporteringsarbetsflödet.

Den aktuella watcher-versionen är:

Watcher 1.2.1

Agentversionen är:

Agent 1.7.0

Dessa versioner bör verifieras efter klientuppgraderingar.
## 57. Watcher-övervakning

Administratörer kan inspektera watchern via systemd på den hanterade klienten.

Användbara kontroller inkluderar:

```bash
systemctl status lums-agent-watcher.service --no-pager
```

och:

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

Timern kan inspekteras med:

```bash
systemctl status lums-agent-watcher.timer --no-pager
```

Det exakta aktiva/inaktiva tillståndet för en oneshot-tjänst bör tolkas tillsammans med dess timer och journal.

Ett inactive (dead)-tillstånd är inte automatiskt ett fel för en oneshot-tjänst.
## 58. Rapporterings- och körningstimers

LUMS separerar regelbunden klientrapportering från körningsövervakning.

Rapporteringstimern ansvarar för schemalagd agentkörning.

Watcher-timern ansvarar för schemalagd watcher-körning.

Inspektera båda vid diagnos av klientsidans schemaläggningsproblem:

```bash
systemctl list-timers --all | grep lums-agent
```

Förväntade enheter inkluderar:

```text
lums-agent.timer
lums-agent-watcher.timer
```

Om en timer inte körs, inspektera:

```bash
systemctl status lums-agent.timer --no-pager
systemctl status lums-agent-watcher.timer --no-pager
```

Inspektera sedan motsvarande journalposter.
## 59. Revisionsloggning

LUMS registrerar viktiga administrativa och säkerhetsrelevanta applikationsåtgärder i revisionsloggen.

Revisionsinformation kan hjälpa till att fastställa:

* vilken operation som inträffade

* vilken användare som initierade den

* vilken klient som påverkades

* när operationen inträffade

* om operationen accepterades

* vilken administrativ åtgärd som utfördes

Revisionsinformation bör behandlas som operativt bevis.

Den bör inte vårdslöst raderas eller ändras.
## 60. Administrativa revisionsevenemang

Relevant administrativ aktivitet inkluderar operationer såsom:

* användarskapande

* rolltilldelning

* klienthantering

* tokenrotation

* skapande av uppdateringsjobb

* pakethanteringsoperationer

* autentiseringsrelaterade säkerhetshändelser

De exakta händelsedata beror på operationen.

Administratörer bör använda revisionsinformation tillsammans med jobbhistorik vid utredning av oväntad aktivitet.
## 61. Hantering av revisionsloggar

Revisionsloggar bör hanteras försiktigt.

Gör inte:

* ändra historiska revisionsposter för att dölja en operation

* exponera känsliga autentiseringsuppgifter i exporterade loggar

* publicera loggar som innehåller klienttoken

* publicera lösenord eller autentiseringsmaterial

* kopiera känslig loggutdata till offentliga ärendespårare

Om loggar måste delas för felsökning, redigera bort autentiseringsuppgifter och annan känslig information först.
## 62. Applikationsloggar

Applikationsloggar beskriver den interna driften av LUMS-servern.

Användbara källor inkluderar:
```bash

sudo docker logs --tail 100 lums
```

För live-övervakning:

```bash
sudo docker logs -f lums
```

Vid utredning av ett problem, begränsa tidsfönstret där det är möjligt.

Dumpa inte automatiskt hela produktionsloggen när ett mindre relevant avsnitt är tillräckligt.
## 63. Agentloggar

Klientsidans agentaktivitet kan inspekteras via systemd:

```bash
journalctl -u lums-agent.service --no-pager -n 100
```

För watcher-aktivitet:

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

För ett specifikt tidsfönster kan systemd-journalfiltrering användas.

Exempel:

```bash
journalctl -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Loggar bör korreleras med det berörda jobb-ID:t när det är möjligt.
## 64. Loggkorrelation

Vid utredning av ett uppdateringsproblem, korrelera information över hela systemet:
text

Webbgränssnitt
```text id="jv3j7c"
  │
  ├── Jobb-ID
  │
  ▼
LUMS API / Applikationslogg
  │
  ▼
Uppdateringsjobb
  │
  ▼
Agent
  │
  ▼
```
Inbyggd pakethanterare

Detta förhindrar det vanliga misstaget att anta att ett problem som observerats i ett lager härstammade från samma lager.
## 65. Checklista för administrativ övervakning

Under normal drift, verifiera regelbundet:
text

[ ] LUMS-containern körs
[ ] HTTPS-slutpunkten är tillgänglig
[ ] Databasen är åtkomlig
[ ] Klienter rapporterar
[ ] Inga oväntade misslyckade jobb
[ ] Inga oförklarade autentiseringsfel
[ ] Agenttimers är aktiva
[ ] Watcher-timers är aktiva
[ ] Pakethanteringsoperationer slutförs normalt
[ ] Revisionsaktivitet är tillgänglig
[ ] Loggar innehåller inga oförklarade återkommande fel

Frekvensen för dessa kontroller bör matcha den operativa betydelsen av LUMS-driftsättningen.
## 66. Återställningsprincip

När ett uppdateringsproblem uppstår är det säkraste administrativa tillvägagångssättet:
text

Observera
```text
   │
   ▼
Identifiera berört jobb/klient
   │
   ▼
Inspektera tillstånd och loggar
   │
   ▼
Fastställ faktisk felpunkt
   │
   ▼
Åtgärda underliggande problem
   │
   ▼
Tillåt återställning eller nytt försök
   │
   ▼
Verifiera slutligt tillstånd
   │
   ▼
```
Dokumentera betydande incidenter

Undvik destruktiva återställningsåtgärder om inte det faktiska feltillståndet är förstått.

I synnerhet, radera inte manuellt jobb, databasposter, pakethanterarens lås eller beständiga klientdata bara för att återställa ett rent gränssnitt.

* Bevara bevis först. Reparera tillstånd sedan. Verifiera resultatet sist.

## 67. Databasadministration

LUMS använder SQLite som sin applikationsdatabas.

Produktionsdatabasen lagras inuti den beständiga Docker-volymen:

```text
/var/lib/lums/lums.db
```

Databasen är beständig över containerersättning så länge Docker-volymen bevaras.

Databasen innehåller applikationstillstånd såsom:

* användare

* hanterade klienter

* uppdateringsjobb

* paketinformation

* revisionsinformation

* autentiseringsrelaterat tillstånd

* migreringstillstånd

Administratörer bör behandla databasen som kritiska applikationsdata.
## 68. SQLite-körningskonfiguration

Den aktuella produktionsbaslinjen för SQLite är:
| Inställning | Värde |
| --- | --- |
| journal_mode | wal |
| busy_timeout | 5000 |
| synchronous | 2 |
| foreign_keys | aktiveras av applikationen |

Applikationen aktiverar uttryckligen SQLite-främmande nyckel-tillämpning för databasanslutningar.

Administratörer bör inte ändra dessa inställningar vårdslöst.

Ändringar av databasens körningskonfiguration bör testas innan de införs i produktion.
## 69. Databasintegritet

Databasintegritet bör kontrolleras när det finns indikationer på databaskorruption eller oväntat applikationsbeteende.

En typisk SQLite-integritetskontroll är:

```bash id="f0g8sl"
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

En frisk databas bör returnera:

```text
ok
```

Om integritetskontrollen rapporterar fel, fortsätt inte att ändra applikationstillståndet blint.

Bevara den berörda databasen och undersök orsaken.
## 70. Databasmigreringar

LUMS använder applikationsmigreringar för att införa databasändringar.

Migreringar bör tillåtas köras genom applikationens normala start- och migreringsmekanism.

Administratörer bör inte manuellt ändra migreringstillståndet bara för att kringgå ett fel.

Efter en applikationsuppdatering, verifiera:

* att containern startar framgångsrikt

* att migreringar slutförs

* att applikationen är nåbar

* att befintliga användare förblir tillgängliga

* att befintliga klienter förblir tillgängliga

* att befintlig jobbhistorik förblir tillgänglig

## 71. Beständig Docker-volym

Docker-volymen som innehåller LUMS applikationsdata är en kritisk beständig resurs.

Produktionsvolymen är:
```text

lums-data
```

Inspektera den med:

```bash id="f3z2kd"
sudo docker volume inspect lums-data
```

Volymen måste förbli ansluten när LUMS-containern ersätts.

Att ta bort containern tar inte bort volymen automatiskt.

Att ta bort volymen tar dock permanent bort de beständiga applikationsdata om inte en separat säkerhetskopia finns.
## 72. Containeradministration

LUMS-applikationen körs inuti en härdad Docker-container.

Produktionssäkerhetsbaslinjen inkluderar:

* icke-root-applikationsanvändare

* skrivskyddat rotfilsystem

* borttagna Linux-kapabiliteter

* no-new-privileges

* begränsade temporära filsystem

* skrivskyddad hemlighetsmontering

* dedikerad beständig datavolym

* applikationsport endast på localhost

Containern bör inte startas med svagare säkerhetsinställningar bara för att felsökning blir bekvämare.
## 73. Containerstatus

Kontrollera det aktuella containertillståndet med:

```bash id="4n6p2v"
sudo docker ps --filter name=lums
```

Inspektera den fullständiga körningskonfigurationen med:

```bash id="k1q4z8"
sudo docker inspect lums
```

Viktiga egenskaper inkluderar:

* körtillstånd

* omstartspolicy

* användare

* skrivskyddat rotfilsystem

* kapabiliteter

* säkerhetsalternativ

* portbindningar

* volymmonteringar

## 74. Verifiering av containersäkerhet

Den härdade körningen bör fortsätta att tillhandahålla de förväntade egenskaperna.

Till exempel:

```bash id="0u7x3n"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

Den förväntade baslinjen är likvärdig med:

```text
lums true false
```

Kapabiliteter bör förbli borttagna:

```bash id="k5n8ae"
sudo docker inspect lums \
    --format '{{json .HostConfig.CapDrop}}'
```

Förväntat:

```text
["ALL"]
```

Säkerhetsalternativ bör inkludera:

```text
no-new-privileges:true
```

## 75. Applikationsport

LUMS-applikationen lyssnar på värden genom loopback-gränssnittet.

Den förväntade mappningen är:

```text
127.0.0.1:5050 → container:5000
```

Verifiera det med:

```bash id="b6v2w0"
sudo docker port lums
```

Applikationsporten bör inte exponeras direkt mot LAN.

Extern åtkomst tillhandahålls via Nginx över HTTPS.
## 76. Nginx och HTTPS

Nginx tillhandahåller den externa HTTPS-ingångspunkten för LUMS.

Den normala begärandevägen är:
text

Klientwebbläsare
```text
      │
      ▼
HTTPS :443
      │
      ▼
Nginx
      │
      ▼
127.0.0.1:5050
      │
      ▼
```
LUMS-container

Docker-applikationsporten bör förbli bunden till localhost.

Administratörer bör därför undvika att exponera port 5050 direkt genom brandväggen eller Docker-konfigurationen.
## 77. HTTPS-verifiering

Efter Nginx-ändringar, validera alltid konfigurationen innan du laddar om:

```bash id="7f1h9m"
sudo nginx -t
```

Om konfigurationen är giltig:

```bash id="4g5s2w"
sudo systemctl reload nginx
```

Verifiera sedan HTTPS:

```bash id="2w8v6c"
curl -I https://LUMS-SERVER/
```

Ersätt LUMS-SERVER med det värdnamn som serverens TLS-certifikat täcker. Använd inte -k för rutinmässig verifiering; det hoppar över certifikatvalidering.

Ett framgångsrikt HTTPS-svar bekräftar att Nginx kan nå LUMS-applikationen.

Certifikatvalidering bör också testas med det värdnamn eller den adress som administratörer normalt använder.

Inaktivera inte certifikatvalidering permanent med -k.
## 78. HTTP-omdirigering

HTTP-slutpunkten bör omdirigera klienter till HTTPS.

Verifiera:

```bash id="w5q0rx"
curl -I http://127.0.0.1/
```

Det förväntade beteendet är en HTTP-omdirigering till HTTPS-slutpunkten.

Administrativ åtkomst bör använda HTTPS.
## 79. Underhåll av TLS-certifikat

TLS-certifikat och privata nycklar är externa i förhållande till Docker-avbilden.

Typiska platser är:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Privata nycklar måste förbli skyddade.

Innan du ersätter ett certifikat:

* verifiera det nya certifikatet

* verifiera den matchande privata nyckeln

* verifiera filbehörigheter

* validera Nginx-konfigurationen

* ladda om Nginx

* verifiera HTTPS

* verifiera applikationsinloggning

Placera aldrig privata TLS-nycklar i Git-förrådet eller Docker-avbilden.
## 80. Hemlighetshantering

Applikationshemligheten lagras utanför containeravbilden.

Produktionshemligheten monteras skrivskyddat in i containern:
```text

/etc/lums/secrets/lums_secret
        │
        ▼
/run/secrets/lums_secret
```

Applikationen tar emot hemligheten genom:

```text
LUMS_SECRET_KEY_FILE
```

Administratörer får aldrig:

* checka in hemligheten

* skriva ut hemligheten

* inkludera hemligheten i dokumentation

* exponera den i skärmdumpar

* placera den i ett avbildslager

Om hemligheten misstänks vara exponerad, behandla den som komprometterad och följ lämplig procedur för hemlighetsrotation.
## 81. Säkerhetskopieringsstrategi

LUMS-data bör säkerhetskopieras före betydande administrativa ändringar.

Som minimum, överväg att skydda:

* SQLite-applikationsdata

* applikationskonfiguration

* TLS-material

* applikationshemligheter

* klientkonfigurationsinformation

* relevant driftdokumentation

Säkerhetskopior bör lagras separat från produktionscontainern och dess beständiga Docker-volym.

En säkerhetskopia som endast finns på samma värd eller Docker-volym ger inte tillräckligt skydd mot förlust av den värden eller volymen.
## 82. Databassäkerhetskopiering

SQLite-databasen bör säkerhetskopieras med en SQLite-medveten metod snarare än att bara kopiera en aktivt modifierad databasfil utan hänsyn till dess tillstånd.

Innan du utför en säkerhetskopiering:

* identifiera produktionsdatabasen

* säkerställ att säkerhetskopieringsdestinationen är tillgänglig

* skapa säkerhetskopian med en lämplig SQLite-säker metod

* verifiera att säkerhetskopian finns

* registrera när den skapades

Anta inte att en framgångsrik filkopiering automatiskt betyder att en giltig återställbar databassäkerhetskopia finns.
## 83. Verifiering av säkerhetskopior

En säkerhetskopia anses inte tillförlitlig förrän den har testats.

Verifiera regelbundet att en säkerhetskopia kan:

* läsas

* öppnas som SQLite-data

* kontrolleras för integritet

* återställas till en isolerad testmiljö

Till exempel kan en extraherad testkopia kontrolleras med:

```bash id="p3v7cx"
sqlite3 /path/to/test-copy.db \
    "PRAGMA integrity_check;"
```

Förväntat resultat:

```text
ok
```

En produktionssäkerhetskopia bör aldrig testas genom att skriva över den aktiva produktionsdatabasen.
## 84. Återställningsprincip

Återställning är en kontrollerad administrativ operation.

Innan återställning:

* identifiera rätt säkerhetskopia

* verifiera dess integritet

* fastställ nödvändig återställningspunkt

* stoppa eller isolera applikationsaktivitet vid behov

* bevara det aktuella produktionstillståndet

* återställ säkerhetskopian

* verifiera databasintegritet

* starta applikationen

* verifiera migreringar

* verifiera användare och klienter

* verifiera jobbhistorik

* verifiera normal klientrapportering

Skriv inte över den enda kopian av produktionsdatabasen under återställning.
## 85. Verifiering efter återställning

Efter en återställning, verifiera minst:
text

[ ] Containern startar
[ ] Databasen öppnas
[ ] SQLite-integritetskontrollen godkänns
[ ] Användare finns
[ ] Roller är korrekta
[ ] Klienter finns
[ ] Klientautentisering fungerar
[ ] Jobbhistorik finns
[ ] Revisionsinformation är tillgänglig
[ ] HTTPS fungerar
[ ] Klienter kan rapportera
[ ] Nya operationer kan skapas

En återställning är endast slutförd efter att applikationen och dess hanterade klienter har verifierats.
## 86. Princip för serversäkerhetskopiering

Den viktigaste administrativa regeln för beständiga LUMS-data är:

* Utför aldrig en destruktiv databas- eller volymoperation utan en verifierad återställningsväg.

I synnerhet, ta inte bort lums-data bara för att containern byggs om eller ersätts.

Containerersättning och radering av beständiga data är separata operationer.
## 87. Checklista för administrativ server

Innan du gör en betydande server-side ändring:
text

[ ] Aktuellt containertillstånd registrerat
[ ] Aktuell avbild registrerad
[ ] Databassäkerhetskopia tillgänglig
[ ] Säkerhetskopians integritet verifierad
[ ] Aktiva jobb granskade
[ ] Klientrapporteringstillstånd granskat
[ ] Konfigurationsändringar dokumenterade
[ ] TLS-material tillgängligt
[ ] Hemlighetshantering verifierad
[ ] Återställningsväg känd

Endast efter att dessa villkor har beaktats bör en betydande produktionsändring fortskrida.
## 88. Princip för serveradministration

LUMS separerar applikationstillstånd från den engångs container.
text

Engångs
└── LUMS-container

Beständig
├── SQLite-databas
└── lums-data-volym

Extern
├── TLS-material
└── Applikationshemlighet

Denna separation gör det möjligt att ersätta applikationscontainern utan att avsiktligt förstöra beständiga applikationsdata.

* Ersätt applikationen vid behov. Bevara data om inte dataradering uttryckligen är avsedd.

## 89. Rutinmässigt underhåll

Rutinmässigt underhåll håller LUMS-installationen tillförlitlig och minskar risken för oväntade driftsproblem.

Typiska underhållsaktiviteter inkluderar:

* granska misslyckade uppdateringsjobb

* kontrollera klientrapportering

* granska applikationsloggar

* granska revisionsaktivitet

* verifiera säkerhetskopior

* kontrollera tillgängligt diskutrymme

* granska Docker-containertillstånd

* kontrollera TLS-certifikatets giltighet

* granska säkerhetsuppdateringar

* verifiera aktuell LUMS-version och avbild

Underhåll bör utföras under ett lämpligt underhållsfönster när ändringar kan påverka produktionsklienter.
## 90. Underhåll före ändringar

Innan du utför underhåll som kan påverka LUMS-servern:

* granska aktiva uppdateringsjobb

* verifiera att klienter inte genomgår oväntat underhåll

* skapa eller verifiera en aktuell säkerhetskopia

* registrera aktuellt container- och avbildstillstånd

* dokumentera den planerade ändringen

* säkerställ att en återställningsväg finns

Börja inte underhållet med att omedelbart stoppa eller radera produktionskomponenter.

Fastställ först det aktuella tillståndet.
## 91. Underhåll av Docker-avbild

LUMS-applikationsavbilder bör byggas om från det granskade källträdet.

För den dokumenterade driftsättningen med en enda container finns ett skyddat uppdateringsskript. Kör det på **LUMS-servervärden**, från dess repositorykopia och med ditt vanliga konto (inte med `sudo`):

```bash
bash scripts/update-lums.sh
```

Skriptet snabbspolar den utcheckade grenen, bygger en ny avbild och kontrollerar att den körande `lums`-containern fortfarande använder de dokumenterade härdade inställningarna och volymen `lums-data`. Det skapar en SQLite-onlinesäkerhetskopia och kontrollerar dess integritet innan containern ersätts. Därefter kontrollerar det den lokala `/login`-sidan och återställer automatiskt den tidigare containern om starten eller kontrollen misslyckas. Säkerhetskopian lagras under `/var/backups/lums-updates`; ange `LUMS_UPDATE_BACKUP_DIR` för att välja en annan absolut värdsökväg. Den tidigare containern behålls under ett tidsstämplat namn för manuell återställning. Ta bort en gammal återställningscontainer efter att uppgraderingen har verifierats med `docker rm` och dess tidsstämplade namn. Lägg aldrig till `-v`.

Uppdateraren avbryter utan att ändra den körande tjänsten om arbetskopian innehåller ändringar, grenen saknar en upstream eller den körande containern avviker från den dokumenterade driftsättningen. Den tar inte bort Docker-volymer. Hämta in uppdateraren till serverns repositorykopia en gång; senare uppdateringar använder samma kommando. Uppdateraren kör inte hela testsviten. Granska containerloggar, HTTPS-inloggning, paneldata och migreringsmeddelanden efter uppdateringen innan du betraktar den som slutförd.

Om återställning behövs ersätter du tidsstämpeln som skrevs ut:

```bash
sudo docker stop lums
sudo docker rm lums
sudo docker rename lums-before-upgrade-<timestamp> lums
sudo docker start lums
```

Innan du bygger en ny avbild:

```bash id="x0m7r4"
cd /opt/lums-public
```

Kör den automatiska testsviten:

```bash id="4gk1dp"
./.venv-test/bin/pytest -q
```

Fortsätt endast när testresultatet är förstått.

Bygg den nya avbilden med en distinkt tillfällig tagg:

```bash id="m8q3vz"
sudo docker build -t lums:new .
```

En tillfällig tagg gör att den för närvarande körande avbilden förblir identifierbar under ersättningsprocessen.
## 92. Avbildsverifiering

Efter att ha byggt en ny avbild, verifiera att avbilden finns:

```bash id="h6s2we"
sudo docker image inspect lums:new
```

Granska avbildskonfigurationen innan driftsättning.

Verifiera där det är lämpligt:

* avbildsdigest

* basavbild

* applikationsfiler

* installerade beroenden

* avbildsstorlek

* exponerade portar

* konfigurerad användare

Avbilden bör endast driftsättas efter att bygg- och testresultaten har granskats.
## 93. Kontrollerad containerersättning

Containerersättning bör utföras medvetet.

Innan du ersätter produktionscontainern:
text

[ ] Tester godkända
[ ] Ny avbild finns
[ ] Databassäkerhetskopia tillgänglig
[ ] Aktiva jobb granskade
[ ] Aktuell avbild registrerad
[ ] Beständig volym bekräftad
[ ] Hemlighet tillgänglig
[ ] TLS-konfiguration tillgänglig
[ ] Återställningsavbild identifierad

Innan du kör exemplet, jämför det med den faktiskt körande containern. Värdena nedan är ett exempel, inte ett kommando som är säkert för varje installation.
I synnerhet måste Docker-bindmonteringens källsökvägar på vänster sida av : matcha din värd, och den gamla containern kan ha ett annat namn.

Visa avbilden, monteringarna, publicerade portar, omstartspolicyn och härdningsinställningarna utan att skriva ut miljövariabelvärden:
```bash

sudo docker inspect lums --format 'Image={{.Config.Image}}
Mounts={{json .Mounts}}
Ports={{json .HostConfig.PortBindings}}
Restart={{json .HostConfig.RestartPolicy}}
Readonly={{.HostConfig.ReadonlyRootfs}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
Tmpfs={{json .HostConfig.Tmpfs}}'
```

Spara utdata någonstans privat och använd den för att kontrollera att den nya containern
behåller samma databasvolym, hemlighetsfil, säkerhetskopieringskatalog, lokal portbindning och säkerhetsalternativ. Klistra inte in hemlighetsinnehåll eller miljövariabelvärden i anteckningar eller meddelanden.

Stoppa den befintliga containern först efter att dessa villkor har beaktats.

Produktionscontainern bör behålla den härdade körningskonfigurationen.

Exempel:

```bash id="n8q2kf"
sudo docker stop lums
sudo docker rename lums lums-before-upgrade
```

Starta sedan den nya avbilden med den etablerade härdade konfigurationen:

```bash id="c7w4md"
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /run:rw,noexec,nosuid,size=16m \
    -p 127.0.0.1:5050:5000 \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -v /var/backups/lums:/var/backups/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -e LUMS_BACKUP_DIR=/var/backups/lums \
    lums:new
```

Ta inte bort lums-before-upgrade förrän den nya driftsättningen har validerats.
## 94. Validering efter uppgradering

Omedelbart efter att ha ersatt containern, verifiera:

```bash id="b4m7tz"
sudo docker ps --filter name=lums
```

Inspektera sedan loggarna:

```bash id="v5n2ra"
sudo docker logs --tail 100 lums
```

Verifiera HTTPS:

```bash id="w9x1kf"
curl -I https://LUMS-SERVER/
```

Ersätt LUMS-SERVER med det värdnamn som serverens TLS-certifikat täcker. Använd inte -k för rutinmässig verifiering; det hoppar över certifikatvalidering.

Verifiera sedan applikationen via det normala administrativa gränssnittet.

Kontrollera att befintliga användare, klienter och senaste historik fortfarande finns.
Granska loggarna efter start- eller migreringsfel. En körande container ensam
bevisar inte att applikationen eller dess databas är frisk.
Rulla tillbaka om den nya containern inte fungerar

Behåll den gamla containern tills den nya versionen har godkänts vid validering. Om
den nya containern är oanvändbar och du har bekräftat att den gamla containern heter
lums-before-upgrade, stoppa och ta bort endast den nya containern, byt sedan namn på och starta om den gamla:

```bash
sudo docker stop lums
sudo docker rm lums
sudo docker rename lums-before-upgrade lums
sudo docker start lums
```

docker rm lums utan -v tar bort containern, inte lums-data-volymen. Lägg aldrig till -v i detta återställningskommando. Om containernamnet skiljer sig,
eller du inte är säker på vilken container som är gammal respektive ny, kör inte dessa
kommandon; inspektera det aktuella tillståndet eller fråga en administratör om hjälp. Efter
återställning, inspektera loggar och verifiera att webbgränssnittet och data är
tillgängliga.
## 95. Beständiga data efter uppgradering

Containerersättning får inte ta bort den beständiga Docker-volymen.

Verifiera:

```bash id="j4p8sx"
sudo docker inspect lums \
    --format '{{json .Mounts}}'
```

Bekräfta att:

```text id="m7z3kc"
/var/lib/lums
```

backas upp av den förväntade beständiga volymen.

Verifiera sedan:

* användare finns fortfarande

* roller förblir korrekta

* klienter förblir registrerade

* jobbhistorik finns fortfarande

* revisionsinformation finns fortfarande

* migreringar slutfördes framgångsrikt

## 96. Säkerhetsbaslinje efter uppgradering

Efter driftsättning av en ny avbild, verifiera den härdade körningen igen.

Kontrollera:

```bash id="q6c3xv"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

Förväntad baslinje:

```text id="s0r8jm"
lums true false
```

Verifiera också:

```text id="g4m2vx"
CapDrop = ALL
SecurityOpt = no-new-privileges:true
```

och att:

```text id="c3p9rw"
127.0.0.1:5050 → container:5000
```

förblir applikationsexponeringen.

En framgångsrik applikationsuppgradering får inte tyst försvaga säkerhetsbaslinjen.
## 97. Klientkommunikation efter uppgradering

Efter en serveruppgradering, verifiera att hanterade klienter fortfarande kan kommunicera.

Kontrollera minst en representativ klient först.

Verifiera:
text

[ ] Klientautentisering lyckas
[ ] Klientrapport accepteras
[ ] Installerad programvara är tillgänglig
[ ] Tillgängliga uppdateringar är tillgängliga
[ ] Uppdateringsjobb kan skapas
[ ] Agentresultat accepteras

Om flera klientplattformar är driftsatta, verifiera representativa system från varje plattform som stöds.
## 98. Uppdateringskörning efter uppgradering

Utför inte omedelbart en stor produktionsuppdatering efter att ha ersatt LUMS-servern.

Utför först ett kontrollerat funktionstest.

Ett lämpligt test bör verifiera hela vägen:
text

Webbgränssnitt
```text id="y7k2fd"
  ↓
API
  ↓
Uppdateringsjobb
  ↓
Agent
  ↓
Pakethanterare
  ↓
Resultat
  ↓
Databas
  ↓
```
Webbgränssnitt

Endast efter att det kontrollerade testet lyckas bör normala underhållsoperationer återupptas.
## 99. Återställning

Återställning bör vara möjlig när en ny avbild orsakar ett oväntat produktionsproblem.

Bevara:

* tidigare fungerande avbild

* beständiga data

* databassäkerhetskopia

* tidigare konfiguration

* tidigare TLS-material

* relevanta loggar

Om den nya containern inte är användbar:

* stoppa den nya containern

* bevara den för utredning när det är praktiskt

* stoppa ytterligare administrativa ändringar

* återställ den tidigare kända fungerande avbilden

* återanvänd den befintliga beständiga volymen

* starta den härdade körningen

* verifiera applikationen

* verifiera klienter

* verifiera jobbtillstånd

* undersök den misslyckade avbilden separat

Ta inte bort den beständiga volymen som en del av en normal återställning.
## 100. Validering efter återställning

Efter återställning, verifiera:
text

[ ] LUMS startar
[ ] HTTPS fungerar
[ ] Användare kan autentisera sig
[ ] Roller är korrekta
[ ] Klienter finns
[ ] Klientautentisering fungerar
[ ] Jobbhistorik finns
[ ] Revisionsinformation finns
[ ] Paketinventering finns
[ ] Uppdateringsjobb kan spåras
[ ] Säkerhetsbaslinjen är intakt

En återställning är endast slutförd efter att applikationen och klientkommunikationsvägen har verifierats.
## 101. Nödadministration

Nödadministration bör bevara bevis och beständigt tillstånd när det är möjligt.

Exempel inkluderar:

* upprepade applikationskrascher

* databasintegritetsfel

* omfattande klientautentiseringsfel

* oväntat paketjobbeteende

* misstänkt exponering av autentiseringsuppgifter

* trasiga uppgraderingar

* TLS-fel som påverkar alla användare

Den föredragna sekvensen är:
text

Bevara
```text id="f8k3wz"
   ↓
Observera
   ↓
Isolera
   ↓
Återställ
   ↓
Verifiera
   ↓
```
Dokumentera

Undvik att radera loggar, databaser, containrar eller klientposter bara för att de verkar vara en del av problemet.
## 102. Princip för administrativa ändringar

Varje betydande produktionsändring bör ha tre tydligt definierade tillstånd:
Före

Det aktuella produktionstillståndet är känt och återställbart.
Under

Ändringen utförs med den dokumenterade proceduren.
Efter

Det resulterande tillståndet verifieras mot den förväntade baslinjen.

Detta gör administrativt arbete reproducerbart och minskar oavsiktlig konfigurationsdrift.
## 103. Kontrollerad avinstallation

Avinstallation är en destruktiv administrativ operation.

Den bör endast utföras när LUMS-driftsättningen avsiktligt tas bort.

Innan du tar bort LUMS:
text

[ ] Alla hanterade klienter identifierade
[ ] Aktiva uppdateringsjobb granskade
[ ] Nödvändig jobbhistorik exporterad eller bevarad
[ ] Nödvändig revisionsinformation bevarad
[ ] Databassäkerhetskopia skapad
[ ] Säkerhetskopia verifierad
[ ] TLS-material bevarat vid behov
[ ] Applikationshemlighet bevarad vid behov
[ ] Dokumentation bevarad
[ ] Återinstallationskrav dokumenterade

Ta inte bort beständiga data innan du bekräftar att de inte längre behövs.
## 104. Ta bort containern

För att ta bort applikationscontainern efter att driftsättningen har avvecklats:

```bash id="n2x7kc"
sudo docker stop lums
sudo docker rm lums
```

Docker-volymen tas avsiktligt inte bort av dessa kommandon.

Detta gör att applikationsdata förblir tillgängliga för senare inspektion eller återställning.
## 105. Ta bort beständiga data

Att ta bort LUMS Docker-volymen är en separat destruktiv operation.

Utför endast detta efter att ha bekräftat att databasen och all lagrad applikationstillstånd inte längre behövs.

Exempel:

```bash id="r8w3mz"
sudo docker volume rm lums-data
```

Detta tar permanent bort de beständiga applikationsdata som lagras i den volymen.

Kör inte detta kommando under en normal uppgradering eller återställning.
## 106. Ta bort klientkomponenter

När en hanterad klient permanent tas bort från LUMS, avinstallera eller inaktivera dess agentkomponenter enligt klientoperativsystemets procedur.

Klienten bör inte längre rapportera till LUMS-servern efter avveckling.

Bevara relevant jobb- och revisionsinformation innan du tar bort klienten om historiska poster krävs.
## 107. Slutlig administrativ checklista
Användaradministration
text

[ ] Användare har lämpliga roller
[ ] Administratörsåtkomst är begränsad
[ ] Inaktiverade konton granskas
[ ] Autentiseringsuppgifter skyddas

Klientadministration
text

[ ] Klienter är korrekt registrerade
[ ] Klienttoken skyddas
[ ] Inaktiverade klienter granskas
[ ] Tokenrotation utförs vid behov
[ ] Klientrapportering är frisk

Uppdateringsadministration
text

[ ] Tillgängliga uppdateringar granskas
[ ] Uppdateringsjobb övervakas
[ ] Misslyckade jobb undersöks
[ ] Paketoperationer verifieras
[ ] Omstartskrav kontrolleras
[ ] Jobbhistorik bevaras

Serveradministration
text

[ ] Containern körs
[ ] Beständig volym är ansluten
[ ] SQLite-integritet är frisk
[ ] HTTPS fungerar
[ ] TLS-material är giltigt
[ ] Applikationshemlighet skyddas
[ ] Säkerhetskopior är tillgängliga

Säkerhet
text

[ ] RBAC förblir tillämpat
[ ] Läsarbegränsningar förblir intakta
[ ] Klientautentisering fungerar
[ ] Containern förblir härdad
[ ] Applikationsporten förblir endast localhost
[ ] Inga autentiseringsuppgifter exponeras
[ ] Loggar innehåller ingen oförklarad känslig information

## 108. Operativ baslinje

En frisk LUMS-installation bör uppfylla följande baslinje:
text

Applikation
* ├── HTTPS tillgängligt
* ├── Autentisering tillgänglig
* └── RBAC tillämpat

```text id="d4k9sy"
Server
```
* ├── Härdad container
* ├── Beständig databas
* └── Giltiga migreringar

Klienter
* ├── Autentiserade
* ├── Rapporterande
* ├── Programvaruinventering tillgänglig
* └── Uppdateringsinformation tillgänglig

Operationer
* ├── Uppdateringsjobb körbara
* ├── Resultat registrerade
* ├── Återställning stöds
* └── Omstartstillstånd rapporterat

Säkerhet
* ├── Hemligheter skyddade
* ├── Token skyddade
* ├── Revisionsinformation bevarad
* └── Nätverksexponering begränsad

Återställning
* ├── Säkerhetskopior tillgängliga
* ├── Återställningsväg känd
* └── Återställningsväg känd

## 109. Administration klar

LUMS-administration bör alltid prioritera kontrollerade, observerbara och reversibla ändringar.

Den administrativa livscykeln är:
text

Planera
  ↓
Observera
  ↓
Ändra
  ↓
Verifiera
  ↓
Dokumentera
  ↓
Underhåll

De viktigaste operativa principerna är:

* Använd minsta nödvändiga behörighet.

* Bevara beständiga data.

* Ändra inte tillstånd utan att förstå det aktuella tillståndet.

* Verifiera resultatet av varje betydande operation.

* Behåll en testad återställningsväg.

För installationsprocedurer, se install.md.

För säkerhetsarkitektur och revisionsresultat, se security.md.

För diagnos och återställningsprocedurer, se troubleshooting.md.
## 110. Slutlig administrationsprincip

LUMS är avsett att göra Linux-uppdateringshantering förutsägbar och observerbar.

Administrativt arbete bör därför inte baseras på antaganden eller blind upprepning.

När något ändras:

Observera först. Ändra sedan. Verifiera sist.

När något går sönder:

Bevara bevis. Identifiera fellingen. Återställ medvetet.

När något fungerar:

Registrera resultatet och behåll den kända fungerande baslinjen.
