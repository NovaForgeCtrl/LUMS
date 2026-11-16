# Produkt

<!-- impeccable:product-schema 1 -->

## Plattform

web

## Användare

Linux-systemadministratörer och IT-team som ansvarar för att centralt hantera och hålla flera Linux-system uppdaterade. Produkten bör även passa en enskild administratör, ett litet IT-team och lämpliga miljöer med hanterade tjänster.

## Produktens syfte

LUMS ger en central överblick över hanterade klienter, installerad programvara, tillgängliga uppdateringar och körning av uppdateringsjobb. Det hjälper administratörer att starta arbeten medvetet och kontrollera resultatet i stället för att blint tillämpa uppdateringar på alla system.

## Användningssammanhang

Administratörer använder LUMS i det dagliga arbetet för att granska flottans hälsa, telemetri, programvara och uppdateringar; starta riktade uppdateringsjobb; granska körningshistorik; samt underhålla användarbehörigheter, granskningsposter och databasbackuper. Infrastrukturstopologin kan kombinera registrerade LUMS-klienter med manuellt underhållna system och relationer.

## Funktioner och begränsningar

- Roll- och behörighetsbaserad åtkomstkontroll, granskningsloggning, databasbackup, paketöversikt och klientuppdateringsjobb är centrala operativa funktioner.
- Systemuppdateringar måste vara kontrollerade och granskningsbara, och fel måste rapporteras korrekt. Ge inte intryck av att en uppdatering lyckades om inte dess kontroller godkändes.
- Registrerade klienter och deras rapporterade data är den tillgängliga källan för automatiskt importerad infrastrukturinventering. Övrig infrastruktur och relationer måste läggas till uttryckligen manuellt, såvida inte en framtida integration har bekräftats.
- Redigering av infrastrukturinventeringen är begränsad till administratörer.
- Ge inte intryck av att godtyckliga virtuella maskiner, containrar, nätverksenheter eller beroenden identifieras automatiskt.

## Varumärkesåtaganden

- Bevara namnet LUMS och den befintliga logotypen.
- Användaren kallar uttryckligen stadiontemat “LUMS-Stadion” och har begärt att den befintliga stadionbakgrunden används på systemstatuspanelen och i liveövervakningen.

## Tillgängligt underlag

- Befintligt produktgränssnitt och temaresurser: `server/static/style.css`, `server/static/images/LUMS_Logo.jpg` och `server/static/images/lumsstadium.jpg`.
- Befintliga implementationer för registrerade klienter, telemetri, uppdateringsjobb, RBAC, granskning och backup finns i paketet `server/`.
- Inga verifierade kundpåståenden, produktmått eller integrationer för automatisk infrastrukturidentifiering har tillhandahållits.

## Produktprinciper

- Låt administratörerna styra systemändringar.
- Gör driftstatus och uppdateringsresultat verifierbara.
- Upprätthåll åtkomstregler på servern, inte bara i gränssnittet.
- Skilj rapporterade klientfakta från manuellt underhållen inventering.
