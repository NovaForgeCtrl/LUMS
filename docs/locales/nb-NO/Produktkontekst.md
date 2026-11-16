# Produktkontekst

<!-- impeccable:product-schema 1 -->

## Plattform

Web

## Brukere

Linux-systemadministratorer og IT-team som har ansvar for sentralisert administrasjon og oppdatering av flere Linux-systemer. Produktet bør også passe for én administrator, et lite IT-team og egnede miljøer for administrerte tjenester.

## Produktets formål

LUMS gir en sentral oversikt over administrerte klienter, installert programvare, tilgjengelige oppdateringer og kjøring av oppdateringsjobber. Det hjelper administratorer med å starte målrettet arbeid med hensikt og kontrollere resultatet, i stedet for å installere oppdateringer ukritisk på alle systemer.

## Driftskontekst

Administratorer bruker LUMS i det daglige arbeidet til å undersøke systemparkens tilstand, telemetri, programvare og oppdateringer; starte målrettede oppdateringsjobber; gjennomgå kjøringshistorikk; og vedlikeholde brukertilgang, revisjonsposter og sikkerhetskopier av databasen. Infrastrukturtopologien kan kombinere registrerte LUMS-klienter med systemer og relasjoner som vedlikeholdes manuelt.

## Funksjoner og begrensninger

- Rolle- og tillatelsesbasert tilgangskontroll, revisjonslogging, sikkerhetskopiering av databasen, pakkeoversikt og oppdateringsjobber for klienter er sentrale driftsfunksjoner.
- Systemoppdateringer skal være kontrollerte og sporbare, og rapportere feil korrekt. Ikke antyd at en oppdatering lyktes med mindre kontrollene bekrefter dette.
- Registrerte klienter og dataene de rapporterer, er kilden til infrastrukturinventar som importeres automatisk. Ytterligere infrastruktur og relasjoner må legges inn eksplisitt manuelt, med mindre en framtidig integrasjon er bekreftet.
- Det er bare administratorer som kan redigere infrastrukturinventaret.
- Ikke antyd at vilkårlige virtuelle maskiner, containere, nettverksenheter eller avhengigheter oppdages automatisk.

## Merkevareforpliktelser

- Behold navnet LUMS og den eksisterende logoen.
- Brukeren omtaler stadiontemaet uttrykkelig som «LUMS-Stadion» og har bedt om at det eksisterende stadionbakgrunnsbildet brukes på systemstatusoversikten og i sanntidsovervåkingen.

## Dokumentasjon

- Eksisterende produktgrensesnitt og temabilder: `server/static/style.css`, `server/static/images/LUMS_Logo.jpg` og `server/static/images/lumsstadium.jpg`.
- Implementasjoner for registrerte klienter, telemetri, oppdateringsjobber, RBAC, revisjonslogging og sikkerhetskopiering finnes i pakken `server/`.
- Det er ikke levert verifiserte kundepåstander, produktmålinger eller integrasjon for automatisk infrastrukturoppdagelse.

## Produktprinsipper

- Administratorer skal ha kontroll over systemendringer.
- Driftsstatus og oppdateringsresultater skal kunne verifiseres.
- Tilgangsregler skal håndheves på serveren, ikke bare i grensesnittet.
- Skill mellom rapporterte klientfakta og inventar som vedlikeholdes manuelt.
