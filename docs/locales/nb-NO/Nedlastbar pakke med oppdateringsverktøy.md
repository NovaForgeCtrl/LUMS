# Nedlastbar pakke med oppdateringsverktøy

Når `Tests`-arbeidsflyten på `main` lykkes, oppretter `Updater package`-
arbeidsflyten et `lums-update-tools-<commit>.tar.gz`-artefakt og en SHA-256-
kontrollsum. Last dem ned fra **Artifacts**-delen av den vellykkede
arbeidsflytkjøringen. Byggeartefakter oppbevares i 90 dager.

Når en GitHub Release publiseres, kjører arbeidsflyten testserien mot den
utgitte taggen før oppdateringsarkivet og et deterministisk kildearkiv legges
ved. Kildearkivet inneholder SHA-256-kontrollsummen og den testede
commit-identifikatoren; Update Center viser ikke utgivelser før alle tre
ressursene for kildeverifisering er tilgjengelige.

Pakken med oppdateringsverktøy er en praktisk nedlasting, ikke en Debian-pakke.
Kildearkivet installeres ikke direkte av webbeholderen. Ikke bruk det til å
oppdatere produksjon før en separat installert oppdaterer på verten har bestått
utrullingskontrollene og verifisert både databasesikkerhetskopi og
tilbakerullingsatferd for den aktuelle installasjonen.

Engelsk kilde: [update-tools-package.md](../../../docs/update-tools-package.md).
