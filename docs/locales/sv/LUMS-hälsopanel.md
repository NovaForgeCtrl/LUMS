# LUMS-hälsopanel

## Syfte och omfattning

Den autentiserade panelen på `/health` ger operatören en snabb överblick över utvalda LUMS- och klientflottetillstånd:

- databasstatus enligt applikationens bedömning;
- totalt antal klienter och antal online, okända respektive offline;
- nyliga processor-, minnes- och nätverkstelemetridata för en aktiverad klient när telemetri är installerad och prover finns;
- nyliga processor-, minnes- och nätverkstelemetridata för aktiverade klienter när telemetri är installerad och prover finns;
- aviseringshistorik och upptäckta telemetriavbrott;
- om den konfigurerade katalogen för säkerhetskopior kan granskas och den senaste säkerhetskopian som applikationen känner igen, samt den senaste lyckade säkerhetskopieringen som registrerats i granskningsloggen;
- valfria statusrader för Wazuh- och Suricata-systemd-tjänster när de har konfigurerats.

Detaljerade värd- och nätverksvärden per klient, temperaturer, tjänste- och containerstatus samt sammanfattningar av säkerhetshändelser finns på den separata sidan `/monitoring`. Telemetrienheten har skrivskyddad åtkomst till systemjournalen för händelsesammanfattningar; den skickar inte råa loggmeddelanden, användarnamn eller källadresser. Containeruppgifter är inte tillgängliga om inte telemetritjänstens konto kan granska körmiljön utan ytterligare behörighet. Sidorna bevisar inte att värden, Docker-daemonen, omvänd proxy, nätverket eller varje hanterad klient fungerar korrekt. En listad säkerhetskopia är inget bevis på att den går att återställa; utför regelbundet ett kontrollerat återställningstest.

## Åtkomstkontroll

Sidan `/health` kräver en inloggad användare med behörigheten `clients.view`. Åtkomsten omfattas av applikationens vanliga autentiserings- och auktoriseringskontroller. Gör inte panelen offentlig genom att kringgå inloggningen eller skyddet för omvänd proxy.

Den separata ändpunkten `GET /api/health` ger ett lättviktigt livstecken. Ett lyckat svar innebär att rutten kan svara; det är inte en fullständig bedömning av databas, säkerhetskopior eller klienthälsa.

## Tolkning av klientstatus

Panelen klassificerar klienter utifrån tidpunkten för deras senaste rapport:

| Status | Tidsstämpelns ålder |
| --- | --- |
| Online | 120 sekunder eller mindre |
| Unknown | Mer än 120 och upp till 600 sekunder, saknad/ogiltig tidsstämpel eller en tidsstämpel i framtiden |
| Offline | Mer än 600 sekunder |

Gränserna beskriver hur nyligen klienten rapporterade, inte om en dator är påslagen eller om alla dess tjänster fungerar. Nätverksfördröjningar, datorer i viloläge, en stoppad agent eller rapporteringsfel kan påverka resultatet. Behandla `unknown` som otillräcklig information, inte som ett bevis på fel.

## Processor- och minnestelemetri

Telemetri är valfri och separat från Reporting Agent och Watcher för körning. Telemetritjänsten skickar ett prov ungefär var femte sekund när systemd-timern är aktiverad och klienten kan nå servern.

Panelen erbjuder historikintervallen 1 timme, 24 timmar och 7 dagar och uppdaterar klientflottans telemetri var femte sekund. Detaljerade värduppgifter på `/monitoring` är den senast rapporterade ögonblicksbilden; bandbredd per gränssnitt beräknas från efterföljande ögonblicksbilder. Historikfrågor begränsas till 1–168 timmar och kan nedsamplas till högst 1 000 punkter. Prover som är äldre än sju dagar tas bort när nya telemetriinsändningar behandlas; om alla insändningar upphör ska du inte anta att rensningen av lagrade data körs oberoende.

Varje journalfråga på övervakningssidan begränsas till 500 träffar; ett visat antal `500+` kan betyda att det faktiska antalet är större. In-/utloggningshistoriken begränsas till 20 händelser och starthistoriken till 10 poster. Hälsopanelen har en fast layout och använder befintliga processor-, RAM- och diskgränser per användare (standard 90 %). Tröskelöverskridanden och telemetriavbrott härleds från den sparade provhistoriken; ändringar av tjänststatus och nya rapporterade SSH-fel registreras som tidsstämplade händelser i upp till sju dagar. CSV-/JSON-exporter innehåller alla prover för det valda intervallet; de interaktiva diagrammen begränsas till 1 000 punkter.

Wazuh- och Suricata-rader är valfria och rapporterar endast systemd-tjänsternas status. Motsvarande installerade enhet måste läggas till i `LUMS_MONITORED_SERVICES`; raderna ansluter inte till Wazuh- eller Suricata-API:er och importerar inte deras aviseringar. Tidsstämpeln för säkerhetskopieringen hämtas från granskningsloggen och är ingen oberoende verifiering av återställning.

Telemetri kräver klientautentisering. Fjärranslutningar från agenter kräver HTTPS; okrypterad HTTP accepteras endast för loopback-adresser. Konfigurera en CA-fil om servern använder en privat certifikatutfärdare. Se [Telemetri](Telemetri.md), [Installation och uppgraderingar](Installation%20och%20uppgraderingar.md) och de engelska källorna [telemetry.md](../../../telemetry.md) och [install.md](../../../install.md).

## Status för säkerhetskopiering

Avsnittet för säkerhetskopior visar vad applikationen kan granska i den konfigurerade katalogen och den senaste säkerhetskopian den känner igen. Det verifierar inte självständigt innehållet i alla säkerhetskopior, bekräftar inte replikering till en annan värd och bevisar inte att en databas kan återställas.

Rekommenderade rutiner:

1. Kontrollera att det visade säkerhetskopieringsdatumet är tillräckligt aktuellt för ditt återställningsmål.
2. Granska säkerhetskopieringsjobbet och applikationsloggarna efter fel.
3. Verifiera att säkerhetskopian kopieras till en lämplig, skyddad plats.
4. Testa regelbundet återställning på en separat, kontrollerad plats.

Ta inte bort eller skriv över den aktiva databasen eller säkerhetskopior som en genväg vid felsökning. Se [Återställning av säkerhetskopia](Återställning%20av%20säkerhetskopia.md) och den engelska källan [backup-restore.md](../../../server/static/backup-restore.md).

## Rekommenderade kontroller när en status verkar felaktig

1. Kontrollera LUMS-containern och de senaste loggarna.
2. Kontrollera omvänd proxy och TLS-konfiguration om sidan eller API:et inte går att nå.
3. För en klient som markerats som okänd/offline: granska Reporting Agent- och Watcher-timrarna och de senaste journalposterna.
4. Om telemetri saknas kontrollerar du `lums-telemetry.timer`, `lums-telemetry.service` och klient-/serverkonfigurationen.
5. Vid varningar om säkerhetskopior kontrollerar du den konfigurerade sökvägen, filsystembehörigheter, tillgängligt utrymme och de senaste säkerhetskopieringsloggarna.
6. Anteckna observerad status och tidsstämplar innan du gör ändringar.

Se [Felsökning](Felsökning.md) för diagnostikkommandon och [Administration och säkerhetskopior](Administration%20och%20säkerhetskopior.md) för löpande underhåll och säkerhetskopieringsrutiner. Engelska källor: [troubleshooting.md](../../../troubleshooting.md) och [administration.md](../../../administration.md).
