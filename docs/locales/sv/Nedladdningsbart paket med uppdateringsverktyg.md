# Nedladdningsbart paket med uppdateringsverktyg

När `Tests`-arbetsflödet på `main` har godkänts skapar arbetsflödet `Updater
package` artefakten `lums-update-tools-<commit>.tar.gz` och en SHA-256-
kontrollsumma. Ladda ned dem från avsnittet **Artifacts** i den lyckade
arbetsflödeskörningen. Byggartefakter sparas i 90 dagar.

När en GitHub Release publiceras kör arbetsflödet testsviten mot den utgivna
taggen innan uppdateringsarkivet och ett deterministiskt källkodsarkiv bifogas.
Källkodsarkivet innehåller SHA-256-kontrollsumman och den testade
commit-identifieraren; Update Center visar inte utgåvor förrän alla tre
resurser för källverifiering finns.

Paketet med uppdateringsverktyg är en praktisk nedladdning, inte ett Debian-
paket. Källkodsarkivet installeras inte direkt av webbcontainern. Använd det
inte för att uppdatera produktion förrän en separat installerad
värduppdaterare har klarat driftsättningskontroller och verifierat både
databassäkerhetskopian och återställningsbeteendet för just den installationen.

Engelsk källa: [update-tools-package.md](../../../docs/update-tools-package.md).
