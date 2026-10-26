# Gjenopprett LUMS-databasen fra sikkerhetskopi

Denne veiledningen gjenoppretter en `.db`- eller `.db.gz`-sikkerhetskopi i en
Docker-installasjon. Gjenoppretting erstatter den aktive databasen. Arbeid
nøye, og utfør trinnene på Debian-verten.

## Forutsetninger

Du trenger:

* vertsbanen til sikkerhetskopilagringen, for eksempel `/mnt/lums-nas-backups`
* valgt undermappe fra LUMS-sikkerhetskopigrensesnittet, hvis den brukes
* navnet på sikkerhetskopifilen
* navnet på databasevolumet, vanligvis `lums-data`
* LUMS-imaget som skal brukes for engangsbeholderen til gjenoppretting

Bruk samme image-versjon som den kjørende installasjonen. Hent det konfigurerte
image-navnet slik:

```bash
sudo docker inspect lums --format '{{.Config.Image}}'
```

Erstatt `lums:SET-TO-ACTIVE-IMAGE-TAG` nedenfor med nøyaktig dette image-
navnet. Ikke bruk en eldre image-tag bare fordi den fortsatt finnes på verten.

NAS-/filsystemmonteringen må være tilgjengelig. Kontroller den før
gjenoppretting:

```bash
mountpoint /mnt/lums-nas-backups
ls -lh /mnt/lums-nas-backups
```

Tilpass `/mnt/lums-nas-backups` til den faktiske vertsstien. LUMS viser
beholderstien; venstre side av Docker-monteringen er vertsstien.

## Gjenoppretting

Angi variablene etter installasjonen din. `BACKUP_FILE` må vise til et
filnavn i sikkerhetskopimonteringen. Hvis grensesnittet bruker en undermappe,
tar du den med i banen, for eksempel `wochenende/lums-backup-....db.gz`.

```bash
BACKUP_ROOT=/mnt/lums-nas-backups
BACKUP_FILE=lums-backup-DATEINAME.db.gz
LUMS_VOLUME=lums-data
LUMS_IMAGE=lums:SET-TO-ACTIVE-IMAGE-TAG
```

Stopp LUMS og ta en ekstra sikkerhetskopi av den gjeldende databasen:

```bash
sudo docker stop lums
sudo docker cp lums:/var/lib/lums/lums.db \
  "/root/lums-before-restore-$(date +%F-%H%M%S).db"
```

Gjenopprett den valgte sikkerhetskopien i en midlertidig hjelpebeholder.
Skriptet kontrollerer databaseintegriteten før utskifting og setter fileieren
tilbake til LUMS-kjøretidsbrukeren:

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

Start LUMS igjen, og kontroller migreringene og tjenesten:

```bash
sudo docker start lums
sudo docker logs --tail 100 lums
curl -s -o /dev/null -w 'GET /login: %{http_code}\n' \
  http://127.0.0.1:5050/login
```

Kontroller deretter pålogging, brukere, klienter og jobber. Hvis den
gjenopprettede sikkerhetskopien er eldre enn den gjeldende applikasjonsversjonen,
kan LUMS kjøre databasemigreringer ved oppstart.

## Hvis gjenopprettingen mislykkes

Ikke la den ugyldige databasen fortsette som produksjonsdata. Stopp LUMS på
nytt. Sett `BACKUP_ROOT=/root` og `BACKUP_FILE` til hele filnavnet på
sikkerhetskopien du tok tidligere, `lums-before-restore-....db`. Kjør deretter
den samme hjelpebeholderkommandoen fra delen Gjenoppretting på nytt. Start
først LUMS etter at integritetskontrollen er bestått.

Engelsk kilde: [backup-restore.md](../../../server/static/backup-restore.md).
