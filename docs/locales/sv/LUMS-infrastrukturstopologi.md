# LUMS-infrastrukturstopologi

## Syfte

Den autentiserade sidan `/infrastructure` samlar registrerade LUMS-klienter och manuellt underhållen infrastruktur i en gemensam beroendevy. Den är en inventering och relationskarta, inte ett system för automatisk nätverksidentifiering eller konfigurationshantering.

## Datakällor och ägarskap

- Registrerade LUMS-klienter läses från det befintliga klientregistret och visas automatiskt med rapporterat värdnamn, IP-adress, operativsystem och status för aktiverad/rapporterar. Inaktiverade klienter förblir synliga så att befintliga relationer går att förstå. Poster på topologisidan är skrivskyddade; hantera klienter via det vanliga arbetsflödet för klienthantering.
- Servrar, virtuella maskiner, containrar, nätverksenheter, tjänster och lagring kan läggas till manuellt med värdnamn, IP-adress, roll, plats och anteckningar.
- Relationer underhålls manuellt. Följande typer stöds: `depends on`, `hosts`, `connects to` och `runs on`.
- Sidan skannar inte delnät, frågar inte moln-API:er och härleder inte beroenden från tjänste- eller containerkonfiguration. Håll manuellt inlagd inventering och relationer uppdaterade.

## Åtkomstkontroll och granskning

Användare med `clients.view` kan visa topologin. Det är endast administratörer med behörigheten `infrastructure.manage` som får skapa, redigera och ta bort manuella poster eller relationer. Applikationen kräver normal autentiserad session, CSRF-skydd och granskningsloggning för ändringar.

`infrastructure.manage` är beroende av `users.manage` och `clients.view` och tilldelas administratörer av databasmigreringen `016-infrastructure-topology`. När en manuellt hanterad nod tas bort tas även dess relationsposter bort. När en klient tas bort tas relationer som hänvisar till den klienten bort.

## Läsa kartan

Kartan ordnar noder efter kategori och ritar varje registrerad relation som en riktad kant. Ett **delat beroende** är en nod som minst två andra noder pekar på med `depends on`. Det är en användbar signal om en möjlig central felpunkt, inte en fullständig analys av tillgänglighet eller påverkan. Kartan tar inte hänsyn till redundans, redundansväxling, kapacitet, nätverkssegmentering eller oregistrerade beroenden.

Använd inventerings- och relationstabellerna för exakta uppgifter om värdnamn, IP-adress, roll, plats och relationer. Topologin använder det LUMS-tema som valts och fungerar med den gemensamma hopfällbara sidomenyn.

Engelsk källa: [LUMS_Infrastructure_Topology.md](../../../LUMS_Infrastructure_Topology.md).
