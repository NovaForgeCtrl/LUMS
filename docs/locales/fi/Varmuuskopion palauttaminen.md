# LUMS-tietokannan varmuuskopion palauttaminen

Tässä ohjeessa palautetaan `.db`- tai `.db.gz`-varmuuskopio Docker-
käyttöönottoon. Palautus korvaa aktiivisen tietokannan. Toimi huolellisesti ja
suorita vaiheet Debian-isännällä.

## Edellytykset

Tarvitset:

* varmuuskopiotallennustilan isäntäpolun, esimerkiksi `/mnt/lums-nas-backups`
* valitun alikansion LUMS-varmuuskopionäkymästä, jos sellainen on käytössä
* varmuuskopiotiedoston nimen
* tietokantataltion nimen, yleensä `lums-data`
* LUMS-kuvan, jota käytetään kertaluonteisessa palautussäilössä

Käytä samaa kuva-versiota kuin käynnissä olevassa asennuksessa. Voit tarkistaa
määritetyn kuvan nimen seuraavasti:

```bash
sudo docker inspect lums --format '{{.Config.Image}}'
```

Korvaa alla oleva `lums:SET-TO-ACTIVE-IMAGE-TAG` täsmälleen tällä kuvan
nimellä. Älä käytä vanhaa kuvatunnistetta vain siksi, että se on yhä
isännässä.

NAS-/tiedostojärjestelmäliitännän on oltava käytettävissä. Tarkista se ennen
palautusta:

```bash
mountpoint /mnt/lums-nas-backups
ls -lh /mnt/lums-nas-backups
```

Muuta `/mnt/lums-nas-backups` vastaamaan todellista isäntäpolkua. LUMS näyttää
säilöpolun; Docker-liitännän vasen puoli on isäntäpolku.

## Palautus

Aseta muuttujat asennuksesi mukaisesti. `BACKUP_FILE`-arvon on osoitettava
varmuuskopioliitännässä olevaan tiedostonimeen. Jos käyttöliittymän alikansio
on käytössä, lisää se polkuun, esimerkiksi
`wochenende/lums-backup-....db.gz`.

```bash
BACKUP_ROOT=/mnt/lums-nas-backups
BACKUP_FILE=lums-backup-DATEINAME.db.gz
LUMS_VOLUME=lums-data
LUMS_IMAGE=lums:SET-TO-ACTIVE-IMAGE-TAG
```

Pysäytä LUMS ja tallenna nykyinen tietokanta lisäpalautusvaihtoehdoksi:

```bash
sudo docker stop lums
sudo docker cp lums:/var/lib/lums/lums.db \
  "/root/lums-before-restore-$(date +%F-%H%M%S).db"
```

Palauta valittu varmuuskopio kertakäyttöisessä apusäilössä. Skripti tarkistaa
tietokannan eheyden ennen korvaamista ja palauttaa tiedoston omistajaksi LUMS-
suorituskäyttäjän:

```bash
sudo docker run --rm \
  --user 0:0 \
  --entrypoint python \
  -v "$LUMS_VOLUME:/var/lib/lums" \
  -v "$BACKUP_ROOT:/backups:ro" \
  "$LUMS_IMAGE" \
  -c '
import gzip
import os
import shutil
import sqlite3
import sys
import tempfile

source_path = sys.argv[1]
database_path = "/var/lib/lums/lums.db"
fd, temporary_path = tempfile.mkstemp(
    prefix=".lums-restore-",
    suffix=".db",
    dir="/var/lib/lums",
)
os.close(fd)
try:
    opener = gzip.open if source_path.endswith(".gz") else open
    with opener(source_path, "rb") as source, open(temporary_path, "wb") as target:
        shutil.copyfileobj(source, target)

    database = sqlite3.connect(temporary_path)
    try:
        result = database.execute("PRAGMA integrity_check").fetchone()
    finally:
        database.close()
    if result is None or result[0] != "ok":
        raise RuntimeError("Backup failed SQLite integrity_check")

    for suffix in ("-wal", "-shm"):
        sidecar = database_path + suffix
        if os.path.exists(sidecar):
            os.unlink(sidecar)
    os.chmod(temporary_path, 0o600)
    os.chown(temporary_path, 10001, 10001)
    os.replace(temporary_path, database_path)
    print("Backup restored and integrity_check passed.")
finally:
    if os.path.exists(temporary_path):
        os.unlink(temporary_path)
' "/backups/$BACKUP_FILE"
```

Käynnistä LUMS uudelleen ja tarkista migraatiot sekä palvelu:

```bash
sudo docker start lums
sudo docker logs --tail 100 lums
curl -s -o /dev/null -w 'GET /login: %{http_code}\n' \
  http://127.0.0.1:5050/login
```

Tarkista sitten kirjautuminen, käyttäjät, asiakkaat ja työt. Jos palautettu
varmuuskopio on nykyistä sovellusversiota vanhempi, LUMS saattaa suorittaa
tietokantamigraatioita käynnistyessään.

## Jos palautus epäonnistuu

Älä jätä virheellistä tietokantaa tuotantokäyttöön. Pysäytä LUMS uudelleen.
Aseta `BACKUP_ROOT=/root` ja määritä `BACKUP_FILE` osoittamaan aiemmin
tallennetun varmuuskopion koko tiedostonimeen
`lums-before-restore-....db`. Suorita sitten sama apusäilökomento Palautus-
osiosta uudelleen. Käynnistä LUMS vasta, kun eheystarkistus on onnistunut.

Englanninkielinen lähde: [backup-restore.md](../../../server/static/backup-restore.md).
