# LUMS-infrastrukturens topologi

## Formål

Den autentiserte `/infrastructure`-siden samler registrerte LUMS-klienter og manuelt vedlikeholdt infrastruktur i én visning av avhengigheter. Den er en oversikt over inventar og relasjoner, ikke et system for automatisk nettverksoppdagelse eller konfigurasjonsstyring.

## Datakilder og eierskap

- Registrerte LUMS-klienter leses fra det eksisterende klientregisteret og vises automatisk med rapportert vertsnavn, IP-adresse, operativsystem og status for aktivert/rapportering. Deaktiverte klienter forblir synlige slik at eksisterende relasjoner fortsatt er forståelige. Oppføringene er skrivebeskyttet på topologisiden; administrer klienter gjennom den vanlige klientarbeidsflyten.
- Servere, virtuelle maskiner, beholdere, nettverksenheter, tjenester og lagring kan legges inn manuelt med vertsnavn, IP-adresse, rolle, plassering og notater.
- Relasjoner vedlikeholdes manuelt. Støttede typer er `depends on`, `hosts`, `connects to` og `runs on`.
- Siden skanner ikke delnett, spør ikke sky-API-er og utleder ikke avhengigheter fra tjeneste- eller beholderkonfigurasjon. Hold manuelt registrert inventar og relasjoner oppdatert.

## Tilgangskontroll og revisjon

Brukere med `clients.view` kan se topologien. Oppretting, redigering og sletting av manuelle oppføringer eller relasjoner er begrenset til administratorer med tillatelsen `infrastructure.manage`. Applikasjonen krever vanlig autentisert økt, CSRF-beskyttelse og revisjonslogging for endringer.

`infrastructure.manage` avhenger av `users.manage` og `clients.view`, og gis til administratorer av databasemigreringen `016-infrastructure-topology`. Når en manuelt administrert node slettes, slettes også relasjonspostene. Når en klient slettes, fjernes relasjoner som viser til klienten.

## Slik leser du kartet

Kartet grupperer noder etter kategori og tegner hver registrerte relasjon som en retningsbestemt kant. En **delt avhengighet** er en node som minst to andre noder peker på med `depends on`. Dette er et nyttig signal om et mulig sentralt feilpunkt, ikke en fullstendig analyse av tilgjengelighet eller konsekvenser. Kartet tar ikke hensyn til redundans, failover, kapasitet, nettverkssegmentering eller uregistrerte avhengigheter.

Bruk inventar- og relasjonstabellene for nøyaktige opplysninger om vertsnavn, IP-adresse, rolle, plassering og relasjoner. Topologien bruker det valgte LUMS-temaet og fungerer med den felles sammenleggbare sidemenyen.

Engelsk kilde: [LUMS_Infrastructure_Topology.md](../../../LUMS_Infrastructure_Topology.md).
