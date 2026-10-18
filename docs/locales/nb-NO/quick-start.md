# Kom i gang med LUMS — norsk bokmål

Denne korte veiledningen er for deg som er ny til LUMS eller Linux. Den er
ikke en fullstendig oversettelse av alle tekniske håndbøker; prosjektets
detaljerte dokumentasjon vedlikeholdes på engelsk.
[Språkoversikt](../../README.md).

## Hva er LUMS?

LUMS administrerer Linux-maskiner sentralt. Serveren viser klienter, installert
programvare og tilgjengelige oppdateringer. En agent på hver klient utfører
godkjente handlinger med maskinens pakkebehandler: APT på Debian/Ubuntu og
pacman på Arch Linux. LUMS installerer ikke alle oppdateringer automatisk.

## Hvis du bare bruker LUMS

Åpne nettadressen du har fått av administratoren, og logg inn med din egen
konto. Tilgjengelige handlinger avhenger av tillatelsene dine. Ikke del kontoen
din eller et klienttoken. Velg språk øverst til høyre på innloggingssiden;
etter innlogging kan LUMS lagre språkvalget på kontoen din.

## Installasjon og drift

En vellykket test betyr ikke at en produksjonsserver er installert. Et sikkert
produksjonsmiljø trenger blant annet HTTPS, en beskyttet applikasjonshemmelighet,
vedvarende databaselagring og verifiserte sikkerhetskopier. Serveren og
Linux-klientene konfigureres hver for seg. Følg
[installasjonsveiledningen](../../../install.md) nøye. Bytt ut plassholdere som
`LUMS-SERVER`, og kontroller hver filbane før du kjører en kommando. Hvis LUMS
allerede kjører, bruker du oppgraderingsprosedyren i
[administrasjonsveiledningen](../../../administration.md), ikke
førstegangsinstallasjonen.

Ikke slett Docker-volumet `lums-data` ved en vanlig oppgradering; det
inneholder databasen. Behold eksisterende monteringer for hemmeligheter og
sikkerhetskopier samt containerens sikkerhetsinnstillinger. Eksempelkommandoer
passer ikke alle installasjoner. Sammenlign dem med containeren som kjører før
du bruker dem.

## Første kontroller når noe går galt

På serveren viser disse kommandoene containerstatus, nylige programlogger og
status for Nginx:

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

`sudo` kan be om Linux-passordet ditt. Kontrollene endrer ikke konfigurasjonen.
Ikke start med å slette databasen eller Docker-volumet, kjøre containeren med
utvidede privilegier eller deaktivere sikkerhetstiltak. Fjern passord, token,
nøkler og personopplysninger før du deler logger.

## Detaljert dokumentasjon

* [Prosjektoversikt](Prosjektoversikt.md)
* [Installasjon og oppgraderinger](../../../install.md)
* [Administrasjon og sikkerhetskopier](../../../administration.md)
* [Feilsøking](../../../troubleshooting.md)
* [Sikkerhetsmodell](../../../security.md)
