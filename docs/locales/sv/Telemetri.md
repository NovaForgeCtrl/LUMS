# LUMS-telemetri för processor, minne och nätverk

## Översikt

Den valfria LUMS-telemetriagenten samlar in processor- och minnesanvändning, nätverksräknare och en begränsad ögonblicksbild av värden från ett hanterat Linux-system och skickar mätvärdena till LUMS-servern.

Servern lagrar telemetriprov och tillhandahåller ett autentiserat historik-API som används av klientens telemetriöversikt.

Telemetrin är separat från den befintliga LUMS Reporting Agent och Watcher. Den ersätter inte någon av komponenterna och utför inte paketuppdateringar.

## Komponenter

| Komponent | Ansvar |
| --- | --- |
| `agent/telemetry.py` | Samlar in mätvärden för processor, minne, värd, nätverk, sensorer, tjänster och containrar |
| `agent/lums-telemetry.service` | Kör telemetriagenten som en begränsad systemd-tjänst |
| `agent/lums-telemetry.timer` | Schemalägger återkommande telemetriinsamling |
| `server/app.py` | Autentiserar inskickade data, validerar mätvärden och lagrar prover |
| `server/static/telemetry.js` | Visar en översikt över klientflottan, historikdiagram och ringmätare |

## Mätvärden

Varje prov innehåller följande obligatoriska fält:

- `cpu_percent`: processoranvändning från 0 till 100.
- `memory_percent`: minnesanvändning från 0 till 100.
- `memory_total_bytes`: totalt upptäckt minne i byte.
- `memory_available_bytes`: tillgängligt minne i byte.

Agentversion 1.1.0 och senare skickar även två valfria kumulativa räknare:

- `network_rx_bytes`: byte som tagits emot sedan start, summerat över alla gränssnitt utom loopback.
- `network_tx_bytes`: byte som skickats sedan start, summerat över alla gränssnitt utom loopback.

Båda räknarna måste skickas tillsammans som icke-negativa heltal. Äldre agenter fortsätter att fungera om de utelämnar dem; översikten visar då inga nätverksdata för klienten. Servern lagrar råvärdena och beräknar byte per sekund från efterföljande prover när data hämtas. Ingen hastighet visas för det första provet, efter en återställning av räknaren (till exempel en omstart) eller när intervallet mellan två prover överstiger fem minuter.

Agentversion 1.2.0 och senare rapporterar också en begränsad ögonblicksbild av systemet:

- belastningsmedelvärde, drifttid, operativsystem, kärna och användning av rotfilsystemet;
- länkstatus, byteräknare, fel och tappade paket för varje nätverksgränssnitt;
- konfigurerade DNS-servrar och bästa möjliga kontroll av gateway-, DNS- och internettillgänglighet;
- temperatur- och fläktvärden när kärnan tillhandahåller dem;
- status, körtider och omstartsräknare för utvalda systemd-tjänster samt namn och normaliserade statusar för Docker- och Podman-containrar när lokala verktyg och behörigheter tillåter skrivskyddad granskning;
- diskens användningsgrad i varje telemetriprov för historikdiagram och utvärdering av tröskelhändelser.

Agentversion 1.3.0 och senare rapporterar även begränsade sammanfattningar av driftshändelser: antal och tidpunkter för misslyckade SSH-inloggningar, antal nyliga journalvarningar och -fel, tidpunkter för in- och utloggning samt de första och senaste journaltidpunkterna för nyliga starter. Råa journalmeddelanden, användarnamn och källadresser skickas inte. Varje journalfråga begränsas till 500 träffar; översikten visar ett antal på 500 som `500+`. Start- och inloggningshistoriken begränsas till 10 starter och 20 in-/utloggningstillfällen.

Servern beräknar genomströmning per gränssnitt från efterföljande prover. Information om tjänster, containrar, temperatur, fläkt och händelser lagras bara i den senaste ögonblicksbilden och dupliceras inte i varje historikprov. Valfria mätvärden som operativsystemet inte tillhandahåller eller tillåter visas som otillgängliga. Agenten startar, stoppar eller ändrar inte tjänster eller containrar. Agenttjänsten får inte åtkomst till Docker-uttaget; containerinformation är otillgänglig om inte körmiljön redan tillåter tjänstekontot att granska den.

Telemetriens systemd-enhet tillhör `systemd-journal` för skrivskyddad journalåtkomst. Det ger åtkomst till systemloggar, men agenten skickar bara de begränsade sammanfattningar som beskrivs ovan. Standardlistan över tillåtna tjänster omfattar LUMS, Docker och SSH. Åsidosätt den med ett kommaseparerat `LUMS_MONITORED_SERVICES`-värde i agentens miljöfil; endast giltiga `.service`-enhetsnamn godtas.

Gatewayens tillgänglighet kontrolleras med ett enda ping-paket när det finns tillgängligt, DNS-tillgänglighet med en kort `getent`-sökning och internettillgänglighet med ett kort TCP-anslutningsförsök till `1.1.1.1:443`. Kontrollerna är endast indikatorer och kan återspegla brandväggspolicy i stället för ett avbrott.

Servern tilldelar provets tidsstämpel och avvisar ogiltiga nyttolaster.

När servern har uppdaterats kör du databasmigreringen en gång (`python3 server/security_migration.py`) så att nätverkskolumner, tabellen för senaste systemstatus och händelsehistoriken skapas. Uppdatera agenten på varje klient för att börja rapportera de nya mätvärdena. Om du vill övervaka själva LUMS-servern registrerar du den som klient och installerar/konfigurerar telemetriagenten även på den värden.

## Säkerhet och integritet

Telemetriendpunkten kräver klientautentisering med den konfigurerade LUMS-klienttokenen.

Agenten skickar begäranden via HTTPS när den ansluter till en fjärrserver. Okrypterad HTTP tillåts endast för `localhost`, `127.0.0.1` och `::1`. Anslutningar till fjärrservrar kräver HTTPS. En valfri CA-fil kan konfigureras för certifikatverifiering.

Agenten inkluderar inte klienttokenen i JSON-nyttolasten och loggar den inte. systemd-tjänsten använder en begränsad körmiljö och behöver inte root-behörighet för att samla in de dokumenterade mätvärdena.

Telemetrin innehåller systemresurser och driftmetadata, inte paketuppdateringar eller godtyckliga kommandoutdata. Gränssnittsadresser, DNS-servrar, tjänstenamn och containernamn kan vara känsliga infrastrukturuppgifter; åtkomsten till översikten och API:et skyddas av behörigheten `clients.view`.

## Datalagring

Servern tar bort telemetriprov som är äldre än sju dagar när den behandlar nya telemetriinsändningar.

Den autentiserade historikändpunkten accepterar ett tidsintervall från 1 till 168 timmar. Åtkomst kräver relevant behörighet att visa klienter. Stora resultat kan nedsamplas till högst 1 000 prover.

Översikten `/health` erbjuder historikintervallen 1 timme, 24 timmar och 7 dagar och uppdaterar de visade uppgifterna var femte sekund. Den visar processor-, minnes- och diskanvändning samt samlad nätverkshistorik, liksom aktuella disk-, belastnings-, drifttids-, kärn-, operativsystems-, gränssnitts-, anslutnings-, sensor-, tjänste- och containeruppgifter för den valda klienten. Den visar även en översikt över klientflottan (filtrerbar efter status, inaktuell telemetri eller hög belastning, sökbar och sorterbar) och uppgifter per klient. Processor och minne kan visas som linjediagram, ytdiagram eller ringmätare för aktuellt värde; webbläsaren kommer ihåg den valda visningen. Nätverkstrafik visas som nedladdnings- och uppladdningshastigheter. Telemetri som är äldre än två minuter markeras som inaktuell. Översikten över klientflottan använder `/api/telemetry/overview`, som kräver behörighet att visa klienter. Historikbegäranden begränsas till 1–168 timmar och kan nedsamplas till högst 1 000 prover. systemd-timern är konfigurerad att köra engångsagenten var femte sekund; den faktiska provfrekvensen beror på tjänstens körningstid och nätverkstillgänglighet. Översikten visar också nyliga SSH-fel, antal journalvarningar/-fel samt in-/utloggnings- och starthistorik. Tröskelvarningar använder den inloggade användarens konfigurerbara processor-, RAM- och diskgränser. Journalantal omfattar högst 500 träffar per fråga. Tidpunkten för den senaste lyckade säkerhetskopian hämtas från serverns granskningslogg; den är inte ett återställningstest.

Varje användare kan spara egna processor-, RAM- och diskgränser från 50 % till 99 %. Standardvärdet är 90 %. Tröskelöverskridanden och telemetriglapp på över två minuter visas i händelsehistoriken. Tröskelvarningar härleds från lagrade prover och använder den inloggade användarens gränser; ändringar av tjänststatus och nya tidpunkter för SSH-fel registreras när data tas emot. Händelser lagras i upp till sju dagar och händelseändpunkten returnerar högst 500 poster.

CSV- och JSON-exporter finns för vald klient och tidsintervall. Historiknedladdningar innehåller alla lagrade prover för intervallet; diagrammen begränsas fortfarande till högst 1 000 punkter. Export kräver `clients.view` och cachelagras inte av webbläsaren.

Wazuh och Suricata kan aktiveras som valfria statusrader per användare i översikten. Raderna visar endast status för konfigurerade systemd-tjänster; LUMS ansluter inte till deras API:er och samlar inte in deras aviseringar. Om en tjänst ska rapporteras lägger du till dess installerade enhet, till exempel `wazuh-agent.service`, `wazuh-manager.service` eller `suricata.service`, i agentens tillåtelselista `LUMS_MONITORED_SERVICES`. LUMS kräver eller lagrar inga autentiseringsuppgifter för integrationer.

## Konfiguration

Telemetriagenten använder miljövariablerna `LUMS_BASE`, `LUMS_TOKEN` och den valfria `LUMS_CA_FILE`. Anslutningar till fjärrservrar kräver HTTPS. Se [Installation och uppgraderingar](Installation%20och%20uppgraderingar.md) och den engelska källan [install.md](../../../install.md) för installations- och konfigurationsanvisningar.

## Installation och drift

Telemetritjänsten är separat från den vanliga LUMS-klienten. På Debian uppdaterar du först LUMS-arkivkopian på klienten och kör `sudo bash scripts/install-telemetry-agent.sh` från dess rot. Installationsprogrammet kontrollerar att `/etc/default/lums-agent` definierar `LUMS_BASE` och `LUMS_TOKEN`, installerar den aktuella insamlaren och systemd-enheterna, aktiverar timern och skickar ett testprov. Det skriver aldrig ut tokenen.

Granska timern och tjänsten med `systemctl status lums-telemetry.timer` och `systemctl status lums-telemetry.service`. Läs de senaste tjänsteloggarna med `journalctl -u lums-telemetry.service -n 30 --no-pager`. Att en engångstjänst är inaktiv mellan schemalagda körningar är inte nödvändigtvis ett fel; kontrollera även timern och de senaste loggarna.

Sidan `/monitoring` skiljer mellan inga prover, grundläggande telemetri utan detaljerade ögonblicksbilder och en inaktuell ögonblicksbild, och visar dessa kontroller på klientsidan. Klistra inte in eller dela tokenen vid felsökning.

## Felsökning

- **Inga prover visas:** Kontrollera serverns URL, klienttokenen och autentiseringen.
- **TLS-fel:** Kontrollera servercertifikatet och den konfigurerade CA-filen.
- **Tjänstfel:** Granska tjänstens journal.
- **Historik saknas:** Kontrollera behörigheten att visa klienter och det begärda tidsintervallet (1–168 timmar).

Se [LUMS-hälsopanel](LUMS-hälsopanel.md) för statusgränser och begränsningar hos indikatorn för säkerhetskopiering. Engelska källor: [telemetry.md](../../../telemetry.md) och [LUMS_Health_Dashboard.md](../../../LUMS_Health_Dashboard.md). Se även [Felsökning](Felsökning.md), [Installation och uppgraderingar](Installation%20och%20uppgraderingar.md) och [troubleshooting.md](../../../troubleshooting.md).
