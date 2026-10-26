# LUMS-helseoversikt

## Formål og omfang

Den autentiserte oversikten på `/health` gir operatøren en rask oversikt over utvalgt LUMS- og klientparkstatus:

- databasestatus slik applikasjonen vurderer den;
- samlet antall klienter og antall tilkoblet, ukjent og frakoblet;
- nylig CPU-, minne- og nettverkstelemetri for en aktivert klient når telemetri er installert og prøver finnes;
- nylig CPU-, minne- og nettverkstelemetri for aktiverte klienter når telemetri er installert og prøver finnes;
- varslingshistorikk og registrerte avbrudd i telemetrien;
- om den konfigurerte katalogen for sikkerhetskopier kan undersøkes og den nyeste sikkerhetskopifilen applikasjonen gjenkjenner, samt siste vellykkede opprettelse av sikkerhetskopi registrert i revisjonsloggen;
- valgfrie statusrader for Wazuh- og Suricata-systemd-tjenester når dette er konfigurert.

Detaljerte verts- og nettverksmålinger per klient, temperaturer, tilstander for tjenester og beholdere samt sammendrag av sikkerhetshendelser finnes på den separate `/monitoring`-siden. Telemetrienheten har skrivebeskyttet tilgang til systemjournalen for hendelsessammendrag; den sender ikke rå loggmeldinger, brukernavn eller kildeadresser. Beholderdetaljer er utilgjengelige med mindre telemetritjenestekontoen kan inspisere kjøremiljøet uten ekstra privilegier. Disse sidene beviser ikke at verten, Docker-daemonen, omvendt proxy, nettverket eller alle administrerte klienter er i orden. En oppført sikkerhetskopi beviser ikke at den kan gjenopprettes; gjennomfør jevnlig en kontrollert gjenopprettingstest.

## Tilgangskontroll

`/health`-siden krever en pålogget bruker med tillatelsen `clients.view`. Tilgangen følger applikasjonens vanlige autentiserings- og autorisasjonskontroller. Ikke gjør oversikten offentlig ved å omgå innloggingen eller kontrollene for omvendt proxy.

Det separate `GET /api/health`-endepunktet gir et enkelt livstegn. Et vellykket svar betyr at ruten kan svare; det er ikke en fullstendig vurdering av database, sikkerhetskopier eller klienthelse.

## Tolkning av klientstatus

Oversikten klassifiserer klienter etter tidspunktet de sist rapporterte:

| Status | Alder på tidsstempelet |
| --- | --- |
| Online | 120 sekunder eller mindre |
| Unknown | Mer enn 120 og opptil 600 sekunder, manglende/ugyldig tidsstempel eller tidsstempel i fremtiden |
| Offline | Mer enn 600 sekunder |

Disse grensene beskriver hvor nylig klienten rapporterte, ikke om en maskin er slått på eller alle tjenestene fungerer. Nettverksforsinkelser, maskiner i hvilemodus, en stoppet agent eller rapporteringsfeil kan påvirke resultatet. Behandle `unknown` som utilstrekkelig informasjon, ikke som bevis på feil.

## CPU- og minnetelemetri

Telemetri er valgfritt og atskilt fra Reporting Agent og Watcher for kjøring. Telemetritjenesten sender en prøve omtrent hvert femte sekund når systemd-timeren er aktivert og klienten kan nå serveren.

Oversikten tilbyr historikk for 1 time, 24 timer og 7 dager og oppdaterer klientparkens telemetri hvert femte sekund. Detaljerte vertsdata på `/monitoring` er det sist rapporterte øyeblikksbildet; båndbredde per grensesnitt beregnes fra påfølgende øyeblikksbilder. Historikkspørringer begrenses til 1–168 timer og kan nedprøves til maksimalt 1 000 punkter. Prøver som er eldre enn sju dager, fjernes når nye telemetriinnsendinger behandles; hvis alle innsendinger stopper, må du ikke anta at oppryddingen av lagrede data kjører uavhengig.

Hvert journaloppslag på overvåkingssiden begrenses til 500 treff; et vist antall på `500+` betyr at det faktiske antallet kan være høyere. Inn-/utloggingshistorikken begrenses til 20 hendelser og oppstartshistorikken til 10 oppføringer. Helseoversikten har fast oppsett og bruker den eksisterende CPU-, RAM- og diskgrensen per bruker (standard 90 %). Terskeloverskridelser og avbrudd i telemetri utledes av lagret prøvehistorikk; endringer i tjenestetilstand og nye rapporterte SSH-feil registreres som tidsstemplede hendelser i opptil sju dager. CSV-/JSON-eksport inneholder alle prøver for det valgte tidsrommet; de interaktive diagrammene begrenses til 1 000 punkter.

Wazuh- og Suricata-rader er valgfrie og rapporterer bare systemd-tjenestetilstander. De krever at den tilhørende installerte enheten er inkludert i `LUMS_MONITORED_SERVICES`; de kobler ikke til Wazuh- eller Suricata-API-er og importerer ikke varslingsstrømmene deres. Tidsstempelet for sikkerhetskopieringen kommer fra revisjonsloggen og er ikke en separat gjenopprettingsverifisering.

Telemetri krever klientautentisering. Eksterne agenttilkoblinger krever HTTPS; vanlig HTTP godtas bare for loopback-adresser. Konfigurer en CA-fil hvis serveren bruker en privat sertifikatutsteder. Se [Telemetri](Telemetri.md), [Installasjon og oppgraderinger](Installasjon%20og%20oppgraderinger.md) og de engelske kildene [telemetry.md](../../../telemetry.md) og [install.md](../../../install.md).

## Status for sikkerhetskopilagring

Sikkerhetskopidelen viser hva applikasjonen kan undersøke i den konfigurerte katalogen for sikkerhetskopier, og den nyeste sikkerhetskopifilen den gjenkjenner. Den kontrollerer ikke uavhengig innholdet i hver sikkerhetskopi, bekrefter ikke replikering til en annen vert og beviser ikke at en database kan gjenopprettes.

Anbefalt driftsrutine:

1. Kontroller at den viste datoen for sikkerhetskopien er ny nok for gjenopprettingsmålet ditt.
2. Se etter feil i sikkerhetskopijobben og applikasjonsloggene.
3. Kontroller at sikkerhetskopien kopieres til et egnet, beskyttet mål.
4. Test jevnlig gjenoppretting på et separat, kontrollert sted.

Ikke slett eller overskriv den aktive databasen eller sikkerhetskopifiler som en snarvei ved feilsøking. Se [Gjenoppretting av sikkerhetskopi](Gjenoppretting%20av%20sikkerhetskopi.md) og den engelske kilden [backup-restore.md](../../../server/static/backup-restore.md).

## Anbefalte kontroller når statusen ser feil ut

1. Kontroller LUMS-beholderen og nylige logger.
2. Kontroller omvendt proxy og TLS-konfigurasjon hvis siden eller API-et ikke kan nås.
3. For en klient merket ukjent/frakoblet: undersøk Reporting Agent- og Watcher-timerne og nylige journaloppføringer.
4. Hvis telemetri mangler, kontroller `lums-telemetry.timer`, `lums-telemetry.service` og klient-/serverkonfigurasjonen.
5. Ved varsler om sikkerhetskopier kontrollerer du konfigurert bane, filsystemtillatelser, tilgjengelig plass og nylige sikkerhetskopilogger.
6. Noter observert status og tidsstempler før du gjør endringer.

Se [Feilsøking](Feilsøking.md) for diagnosekommandoer og [Administrasjon og sikkerhetskopier](Administrasjon%20og%20sikkerhetskopier.md) for rutinemessig vedlikehold og sikkerhetskopiprosedyrer. Engelske kilder: [troubleshooting.md](../../../troubleshooting.md) og [administration.md](../../../administration.md).
