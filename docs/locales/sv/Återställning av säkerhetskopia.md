# Återställa LUMS-databas från säkerhetskopia

Den här guiden återställer en `.db`- eller `.db.gz`-säkerhetskopia i en
Docker-installation. Återställningen ersätter den aktiva databasen. Arbeta
försiktigt och utför stegen på Debian-värden.

## Förutsättningar

Du behöver:

* värdsökvägen till säkerhetskopieringen, till exempel `/mnt/lums-nas-backups`
* vald undermapp från LUMS-gränssnittet för säkerhetskopior, om en sådan används
* säkerhetskopiefilens namn
* databasvolymens namn, vanligtvis `lums-data`
* LUMS-imagen som ska användas för engångscontainern för återställning

Använd samma imageversion som den aktiva installationen. Ta reda på det
konfigurerade imagenamnet:

```bash
sudo docker inspect lums --format '{{.Config.Image}}'
```

Ersätt `lums:SET-TO-ACTIVE-IMAGE-TAG` nedan med exakt detta imagenamn. Använd
inte en äldre image-tagg bara för att den fortfarande finns på värden.

NAS-/filsystemmonteringen måste vara tillgänglig. Kontrollera den före
återställningen:

```bash
mountpoint /mnt/lums-nas-backups
ls -lh /mnt/lums-nas-backups
```

Anpassa `/mnt/lums-nas-backups` till den faktiska värdsökvägen. LUMS visar
containersökvägen; den vänstra sidan av Docker-monteringen är värdsökvägen.

## Återställning

Ange variablerna så att de passar din installation. `BACKUP_FILE` måste peka
på ett filnamn i säkerhetskopiemonteringen. Om ett undermappsalternativ i
gränssnittet används lägger du till det i sökvägen, till exempel
`wochenende/lums-backup-....db.gz`.

```bash
BACKUP_ROOT=/mnt/lums-nas-backups
BACKUP_FILE=lums-backup-DATEINAME.db.gz
LUMS_VOLUME=lums-data
LUMS_IMAGE=lums:SET-TO-ACTIVE-IMAGE-TAG
```

Stoppa LUMS och spara en extra kopia av den aktuella databasen:

```bash
sudo docker stop lums
sudo docker cp lums:/var/lib/lums/lums.db \
  "/root/lums-before-restore-$(date +%F-%H%M%S).db"
```

Återställ den valda säkerhetskopian i en tillfällig hjälparcontainer. Skriptet
kontrollerar databasintegriteten innan den aktiva databasen ersätts och återställer
filens ägare till LUMS-körtidsanvändaren:

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

Starta LUMS igen och kontrollera migreringar och tjänst:

```bash
sudo docker start lums
sudo docker logs --tail 100 lums
curl -s -o /dev/null -w 'GET /login: %{http_code}\n' \
  http://127.0.0.1:5050/login
```

Kontrollera därefter inloggning, användare, klienter och jobb. Om den
återställda säkerhetskopian är äldre än den aktuella programversionen kan LUMS
köra databasmigreringar vid start.

## Om återställningen misslyckas

Låt inte den felaktiga databasen fortsätta användas i produktion. Stoppa LUMS
igen. Ange `BACKUP_ROOT=/root` och sätt `BACKUP_FILE` till hela filnamnet för
den tidigare sparade `lums-before-restore-....db`-filen. Kör sedan samma
kommando för hjälparcontainern från avsnittet Återställning igen. Starta inte
LUMS förrän integritetskontrollen har godkänts.

Engelsk källa: [backup-restore.md](../../../server/static/backup-restore.md).
