# Kom igång med LUMS — svenska

Den här korta guiden är för dig som är ny på LUMS eller Linux. Den är inte en
fullständig översättning av alla tekniska handböcker; projektets detaljerade
dokumentation underhålls på engelska. [Språkindex](../../README.md).

## Vad är LUMS?

LUMS hanterar Linux-datorer centralt. Servern visar klienter, installerad
programvara och tillgängliga uppdateringar. En agent på varje klient utför
godkända åtgärder med datorns pakethanterare: APT på Debian/Ubuntu och pacman
på Arch Linux. LUMS installerar inte alla uppdateringar automatiskt.

## Om du bara använder LUMS

Öppna webbadressen som administratören har gett dig och logga in med ditt eget
konto. Vilka åtgärder du kan utföra beror på dina behörigheter. Dela inte ditt
konto eller en klienttoken. Välj språk uppe till höger på inloggningssidan;
efter inloggning kan LUMS spara valet på ditt konto.

## Installation och drift

Ett godkänt test innebär inte att en produktionsserver är installerad. En
säker produktionsmiljö behöver bland annat HTTPS, en skyddad applikationshemlighet,
beständig databaslagring och verifierade säkerhetskopior. Servern och
Linux-klienterna konfigureras separat. Följ
[installationsguiden](../../../install.md) noggrant. Ersätt platshållare som
`LUMS-SERVER` och kontrollera varje sökväg innan du kör ett kommando. Om LUMS
redan körs använder du uppgraderingsanvisningarna i
[administrationsguiden](../../../administration.md), inte instruktionerna för
en ny installation.

Ta aldrig bort Docker-volymen `lums-data` vid en vanlig uppgradering; den
innehåller databasen. Behåll befintliga monteringar för hemligheter och
säkerhetskopior samt containerns säkerhetsinställningar. Exempelkommandon
passar inte alla installationer — jämför dem först med den aktiva containern.

## Första kontrollerna när något inte fungerar

På servern visar de här kommandona containerns status, de senaste
programloggarna och Nginx-status:

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

`sudo` kan fråga efter ditt Linux-lösenord. Kontrollerna ändrar inte
konfigurationen. Börja inte med att ta bort databasen eller Docker-volymen,
köra containern med privilegier eller stänga av säkerhetsskydd. Ta bort
lösenord, token, nycklar och personuppgifter innan du delar loggar.

## Detaljerad dokumentation

* [Projektöversikt](Projektöversikt.md)
* [Installation och uppgraderingar](../../../install.md)
* [Administration och säkerhetskopior](../../../administration.md)
* [Felsökning](../../../troubleshooting.md)
* [Säkerhetsmodell](../../../security.md)
