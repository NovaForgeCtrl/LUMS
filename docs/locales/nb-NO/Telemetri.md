# LUMS-telemetri for CPU, minne og nettverk

## Oversikt

Den valgfrie LUMS-telemetriagenten samler inn CPU- og minnebruk, nettverkstellere og et begrenset systemøyeblikksbilde fra et administrert Linux-system og sender målingene til LUMS-serveren.

Serveren lagrer telemetriprøver og tilbyr et autentisert historikk-API som brukes av klientens telemetrioversikt.

Telemetri er atskilt fra den eksisterende LUMS Reporting Agent og Watcher. Den erstatter ingen av dem og utfører ikke pakkeoppdateringer.

## Komponenter

| Komponent | Ansvar |
| --- | --- |
| `agent/telemetry.py` | Samler inn CPU-, minne-, system-, nettverks-, sensor-, tjeneste- og beholdermålinger |
| `agent/lums-telemetry.service` | Kjører telemetriagenten som en begrenset systemd-tjeneste |
| `agent/lums-telemetry.timer` | Planlegger gjentatt innsamling av telemetri |
| `server/app.py` | Autentiserer innsendinger, validerer målinger og lagrer prøver |
| `server/static/telemetry.js` | Viser en oversikt over klientparken, historikkdiagrammer og ringmålere |

## Målinger

Hver prøve inneholder disse obligatoriske feltene:

- `cpu_percent`: CPU-bruk fra 0 til 100.
- `memory_percent`: minnebruk fra 0 til 100.
- `memory_total_bytes`: totalt registrert minne i byte.
- `memory_available_bytes`: tilgjengelig minne i byte.

Agentversjon 1.1.0 og nyere sender også to valgfrie kumulative tellere:

- `network_rx_bytes`: byte mottatt siden oppstart, summert over alle grensesnitt unntatt loopback.
- `network_tx_bytes`: byte sendt siden oppstart, summert over alle grensesnitt unntatt loopback.

Begge tellerne må sendes sammen som ikke-negative heltall. Eldre agenter fungerer fortsatt når de utelater dem; oversikten viser da ingen nettverksdata for den klienten. Serveren lagrer råtellerne og beregner byte per sekund fra påfølgende prøver når dataene hentes. Ingen hastighet vises for den første prøven, etter en tilbakestilling av telleren (for eksempel en omstart) eller når tidsrommet mellom to prøver overstiger fem minutter.

Agentversjon 1.2.0 og nyere rapporterer også et begrenset systemøyeblikksbilde:

- belastningsgjennomsnitt, oppetid, operativsystem, kjerne og bruk av rotfilsystemet;
- koblingstilstand, byt tellere, feil og tap for hvert nettverksgrensesnitt;
- konfigurerte DNS-servere og beste forsøk på å fastslå tilgjengelighet for gateway, DNS og internett;
- temperatur- og vifteavlesninger når kjernen gjør dem tilgjengelige;
- tilstand, kjøretid og omstartsteller for utvalgte systemd-tjenester, samt navn og normaliserte tilstander for Docker- og Podman-beholdere når lokale verktøy og tillatelser gir mulighet for skrivebeskyttet inspeksjon;
- diskbruk på hver telemetriprøve for historikkdiagrammer og vurdering av terskelhendelser.

Agentversjon 1.3.0 og nyere rapporterer også begrensede sammendrag av driftshendelser: antall og tidspunkter for mislykkede SSH-pålogginger, nylige antall advarsler og feil i journalen, tidspunkter for inn- og utlogging samt de første og siste journal-tidspunktene for nylige oppstarter. Rå journalmeldinger, brukernavn og kildeadresser sendes ikke. Hvert journaloppslag begrenses til 500 treff; oversikten viser et antall på 500 som `500+`. Oppstarts- og påloggingshistorikken begrenses til 10 oppstarter og 20 inn-/utlogginger.

Serveren beregner gjennomstrømming per grensesnitt fra påfølgende prøver. Detaljer om tjenester, beholdere, temperatur, vifte og hendelser lagres bare som det nyeste øyeblikksbildet, ikke i hver historikkprøve. Valgfrie målinger som operativsystemet ikke tilbyr eller tillater, vises som utilgjengelige. Agenten starter, stopper eller endrer ikke tjenester eller beholdere. Agenttjenesten får ikke tilgang til Docker-sokkelen; beholderdetaljer er utilgjengelige med mindre kjøremiljøet allerede lar tjenestekontoen inspisere dem.

systemd-enheten for telemetri er medlem av `systemd-journal` for skrivebeskyttet journaltilgang. Dette gir tilgang til systemlogger, men agenten sender bare de begrensede sammendragene som er beskrevet ovenfor. Standardlisten over tjenester omfatter LUMS, Docker og SSH. Overstyr den med en kommaseparert `LUMS_MONITORED_SERVICES`-verdi i agentens miljøfil; bare gyldige `.service`-enhetsnavn godtas.

Gateway-tilgjengelighet kontrolleres med én ping-pakke når dette er tilgjengelig, DNS-tilgjengelighet med et kort `getent`-oppslag og internettilgjengelighet med et kort TCP-tilkoblingsforsøk til `1.1.1.1:443`. Kontrollene er bare indikatorer og kan gjenspeile brannmurregler i stedet for et avbrudd.

Serveren angir prøvens tidsstempel og avviser ugyldige nyttelaster.

Etter at serveren er oppdatert, kjører du databasemigreringen én gang (`python3 server/security_migration.py`) slik at nettverkskolonnene, tabellen for nyeste systemtilstand og hendelseshistorikken blir opprettet. Oppdater agenten på hver klient for å begynne å rapportere de nye målingene. Hvis LUMS-serveren også skal overvåkes, registrerer du den som klient og installerer/konfigurerer telemetriagenten på den verten.

## Sikkerhet og personvern

Telemetriendepunktet krever klientautentisering med det konfigurerte LUMS-klienttokenet.

Agenten sender forespørsler over HTTPS når den kobler til en ekstern server. Vanlig HTTP tillates bare for `localhost`, `127.0.0.1` og `::1`. Tilkoblinger til eksterne servere krever HTTPS. En valgfri CA-fil kan konfigureres for sertifikatkontroll.

Agenten inkluderer ikke klienttokenet i JSON-nyttelasten eller i logger. systemd-tjenesten bruker et begrenset kjøremiljø og trenger ikke root-privilegier for å samle inn de beskrevne målingene.

Telemetrien inneholder systemressurser og driftsmetadata, ikke pakkeoppdateringer eller vilkårlig kommandoutdata. Grensesnittadresser, DNS-servere, tjenestenavn og beholdernavn kan være sensitive infrastrukturopplysninger; tilgang til oversikten og API-et er beskyttet av tillatelsen `clients.view`.

## Datalagring

Serveren fjerner telemetriprøver som er eldre enn sju dager, når den behandler nye telemetriinnsendinger.

Det autentiserte historikkendepunktet godtar et tidsrom fra 1 til 168 timer. Tilgang krever den aktuelle visningstillatelsen for klienter. Store resultatsett kan nedprøves til maksimalt 1 000 prøver.

`/health`-oversikten tilbyr historikk for 1 time, 24 timer og 7 dager og oppdaterer de viste dataene hvert femte sekund. Den viser CPU-, minne- og diskbruk samt samlet nettverkshistorikk, i tillegg til direkte disk-, belastnings-, oppetids-, kjerne-, operativsystem-, grensesnitt-, tilkoblings-, sensor-, tjeneste- og beholderdetaljer for den valgte klienten. Den viser også en oversikt over klientparken (kan filtreres etter status, foreldet telemetri eller høy belastning, søkes og sorteres) og detaljer per klient. CPU og minne kan vises som linjediagram, arealdiagram eller ringmåler for gjeldende verdi; nettleseren husker visningen som er valgt. Nettverkstrafikk vises som nedlastings- og opplastingshastighet. Telemetri som er eldre enn to minutter, merkes som foreldet. Oversikten over klientparken bruker endepunktet `/api/telemetry/overview`, som krever visningstillatelse for klienter. Historikkforespørsler begrenses til 1–168 timer og kan nedprøves til maksimalt 1 000 prøver. systemd-timeren er konfigurert til å kjøre engangsagenten hvert femte sekund; den faktiske prøvefrekvensen avhenger av tjenestens kjøretid og nettverkstilgjengelighet. Oversikten viser også nylige SSH-feil, antall journaladvarsler/-feil og inn-/utloggings- og oppstartshistorikk. Terskelvarsler bruker brukerens konfigurerbare CPU-, RAM- og diskgrenser. Journalantall omfatter maksimalt 500 treff per oppslag. Tidspunktet for siste vellykkede sikkerhetskopi leses fra serverens revisjonslogg; det er ikke en gjenopprettingstest.

Hver bruker kan lagre egne CPU-, RAM- og diskgrenser fra 50 % til 99 %. Standardverdien er 90 %. Terskeloverskridelser og telemetrigap på over to minutter vises i hendelseshistorikken. Terskelvarsler utledes fra lagrede prøver og bruker grensene til den påloggede brukeren; endringer i tjenestetilstand og nye tidspunkter for SSH-feil registreres når dataene mottas. Hendelser lagres i opptil sju dager, og hendelsesendepunktet returnerer maksimalt 500 oppføringer.

CSV- og JSON-eksport er tilgjengelig for valgt klient og tidsrom. Historikknedlastinger inkluderer alle lagrede prøver for tidsrommet; diagrammene begrenses fortsatt til maksimalt 1 000 punkter. Eksport krever `clients.view` og bufres ikke av nettleseren.

Wazuh og Suricata kan aktiveres som valgfrie statusrader per bruker i oversikten. Radene viser bare tilstanden til konfigurerte systemd-tjenester; LUMS kobler ikke til API-ene deres eller samler inn varslene deres. Hvis en tjeneste skal rapporteres, legger du dens installerte enhet, for eksempel `wazuh-agent.service`, `wazuh-manager.service` eller `suricata.service`, til agentens tillatelsesliste `LUMS_MONITORED_SERVICES`. LUMS krever eller lagrer ingen integrasjonslegitimasjon.

## Konfigurasjon

Telemetriagenten bruker miljøvariablene `LUMS_BASE`, `LUMS_TOKEN` og den valgfrie `LUMS_CA_FILE`. Eksterne servertilkoblinger krever HTTPS. Se [Installasjon og oppgraderinger](Installasjon%20og%20oppgraderinger.md) og den engelske kilden [install.md](../../../install.md) for installasjons- og konfigurasjonsinstruksjoner.

## Installasjon og drift

Telemetritjenesten er separat fra den vanlige LUMS-klienten. På Debian oppdaterer du først LUMS-arkivkopien på klienten og kjører `sudo bash scripts/install-telemetry-agent.sh` fra rotmappen. Installeringsprogrammet kontrollerer at `/etc/default/lums-agent` definerer `LUMS_BASE` og `LUMS_TOKEN`, installerer gjeldende innsamler og systemd-enheter, aktiverer timeren og sender en testprøve. Det skriver aldri ut tokenet.

Kontroller timeren og tjenesten med `systemctl status lums-telemetry.timer` og `systemctl status lums-telemetry.service`. Se nylige tjenestelogger med `journalctl -u lums-telemetry.service -n 30 --no-pager`. En inaktiv engangstjeneste mellom planlagte kjøringer er ikke nødvendigvis en feil; kontroller også timeren og de siste loggene.

`/monitoring`-siden skiller mellom manglende prøver, grunnleggende telemetri uten detaljerte øyeblikksbilder og et foreldet øyeblikksbilde, og viser disse kontrollene på klientsiden. Ikke lim inn eller del tokenet under feilsøking.

## Feilsøking

- **Ingen prøver vises:** Kontroller serveradressen, klienttokenet og autentiseringen.
- **TLS-feil:** Kontroller serversertifikatet og den konfigurerte CA-filen.
- **Tjenestefeil:** Undersøk tjenestens journal.
- **Historikk mangler:** Kontroller visningstillatelsene for klienter og det forespurte tidsrommet (1–168 timer).

Se [LUMS-helseoversikt](LUMS-helseoversikt.md) for statusgrenser og begrensningene ved indikatoren for sikkerhetskopilagring. Engelske kilder: [telemetry.md](../../../telemetry.md) og [LUMS_Health_Dashboard.md](../../../LUMS_Health_Dashboard.md). Se også [Feilsøking](Feilsøking.md), [Installasjon og oppgraderinger](Installasjon%20og%20oppgraderinger.md) og [troubleshooting.md](../../../troubleshooting.md).
