# Ladattava päivitystyökalupaketti

Kun `main`-haaran `Tests`-työnkulku onnistuu, `Updater package` -työnkulku
luo `lums-update-tools-<commit>.tar.gz`-artefaktin ja SHA-256-tarkistussumman.
Lataa ne onnistuneen työnkulkusuorituksen **Artifacts**-osiosta.
Koontiartifakteja säilytetään 90 päivää.

Kun GitHub Release julkaistaan, työnkulku suorittaa testit julkaistua tunnistetta
vasten ennen päivittäjäarkiston ja deterministisen lähdekoodiarkiston
liittämistä julkaisuun. Lähdearkisto sisältää SHA-256-tarkistussumman ja
testatun commit-tunnisteen; Update Center listaa julkaisut vasta, kun kaikki
kolme lähteen varmennusartefaktia ovat saatavilla.

Päivitystyökalupaketti on käytännöllinen ladattava paketti, ei Debian-paketti.
Lähdearkistoa ei asenneta suoraan verkkosäilöön. Älä käytä sitä tuotannon
päivittämiseen, ennen kuin erikseen asennettu isäntäkoneen päivittäjä on
läpäissyt käyttöönoton tarkistukset ja varmistanut tietokannan varmuuskopiointi-
ja palautusmenettelyn juuri kyseiselle käyttöönotolle.

Englanninkielinen lähde: [update-tools-package.md](../../../docs/update-tools-package.md).
