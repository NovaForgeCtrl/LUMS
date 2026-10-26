# LUMS Installasjonsveiledning

## Linux Update Management Server

**Prosjekt:** LUMS
**Slogan:** Linux-oppdateringsadministrasjon uten støyen.
**Repositorium:** `NovaForgeCtrl/LUMS`

---

## Kom i gang: Forstå installasjonen før du begynner

Denne veiledningen dekker en komplett serverinstallasjon, inkludert avanserte vedlikeholds- og verifiseringsprosedyrer. Det er **ikke** et enkelt skript som skal kjøres uten gjennomgang: servernavn, TLS-sertifikat, hemmelighetsfil, sikkerhetskopimål, nettverk og database varierer mellom installasjoner.

### Hva blir installert?

* **LUMS-server:** webgrensesnittet og API-et, som kjører i en Docker-container.
* **Nginx:** mottar eksterne HTTPS-tilkoblinger og videresender dem lokalt til containeren.
* **Datavolum:** inneholder SQLite-databasen. Dette volumet må overleve oppgraderinger og må aldri slettes under en normal containerutskifting.
* **Hemmelighetsfil:** beskytter applikasjonsøkter blant annet. Legg den aldri i Git-repositoriet, et Docker-bilde eller en chatmelding.
* **LUMS Agent og Watcher:** installeres separat på administrerte Linux-klienter. En fungerende server alene oppdaterer ingen klienter.

| Begrep | Betydning |
| --- | --- |
| Terminal / skall | Et tekstvindu der du skriver inn Linux-kommandoer. |
| `sudo` | Kjører kommandoen som følger med administratorrettigheter. Linux kan spørre om passordet ditt. |
| Vert | Linux-datamaskinen som kjører Docker og LUMS-serveren. |
| Container | En isolert prosess som kjører LUMS-webapplikasjonen. |
| Image | En forberedt mal Docker bruker for å starte en container. |
| Volum | Vedvarende Docker-lagring som forblir når en container erstattes. |
| Plassholder | Tekst som `LUMS-SERVER` som må erstattes med din faktiske verdi. |

### Kjør bare tester (dette installerer ikke en server)

Disse trinnene passer for Debian 13 for å sjekke ut kildekoden og kjøre tester lokalt. De oppretter **ikke** en produksjonsserver som er tilgjengelig over nettverket, og installerer ikke en agent på en annen datamaskin. `sudo` trengs bare for å installere Debian-pakker.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
git clone https://github.com/NovaForgeCtrl/LUMS.git ~/LUMS
cd ~/LUMS
python3 -m venv .venv-test
./.venv-test/bin/python -m pip install -r server/requirements.txt -r requirements-dev.txt
./.venv-test/bin/pytest -q
```

Dette er bare en lokal test av kildekoden; kommandoene installerer ikke en
produksjonsserver eller en agent på en klient. Den fullstendige
installasjonsveiledningen og oppgraderingsprosedyren vedlikeholdes foreløpig
på engelsk: [installasjon](../../../install.md) og
[administrasjon og oppgraderinger](../../../administration.md). Ved feil, se
[feilsøkingsveiledningen](../../../troubleshooting.md). Ikke bruk disse
testkommandoene som en produksjonsinstallasjon.
