# LUMS-Datenbank-Backup wiederherstellen

Diese Anleitung stellt eine `.db`- oder `.db.gz`-Sicherung in einem Docker-
Deployment wieder her. Beim Wiederherstellen wird die aktive Datenbank ersetzt.
Arbeite sorgfältig und führe die Schritte auf dem Debian-Host aus.

## Voraussetzungen

Du brauchst:

* den Host-Pfad des Backup-Speichers, zum Beispiel `/mnt/lums-nas-backups`
* den ausgewählten Unterordner aus der LUMS-Backup-Oberfläche, falls verwendet
* den Namen der Sicherungsdatei
* den Namen des Datenbank-Volumes, üblicherweise `lums-data`
* das LUMS-Image, das für den einmaligen Restore-Container verwendet wird

Verwende dieselbe Image-Version wie die laufende Installation. Den konfigurierten
Image-Namen kannst du so abfragen:

```bash
sudo docker inspect lums --format '{{.Config.Image}}'
```

Ersetze `lums:SET-TO-ACTIVE-IMAGE-TAG` unten durch genau diesen Image-Namen.
Verwende kein altes Image-Tag, nur weil es noch auf dem Host vorhanden ist.

Der NAS-/Dateisystem-Mount muss verfügbar sein. Prüfe ihn vor dem Restore:

```bash
mountpoint /mnt/lums-nas-backups
ls -lh /mnt/lums-nas-backups
```

Passe `/mnt/lums-nas-backups` an den tatsächlichen Host-Pfad an. LUMS zeigt
den Container-Pfad an; die linke Seite des Docker-Mounts ist der Host-Pfad.

## Wiederherstellung

Setze die Variablen passend zu deiner Installation. `BACKUP_FILE` muss auf
einen Dateinamen im Backup-Mount zeigen. Bei einem UI-Unterordner ergänze ihn
im Pfad, beispielsweise `wochenende/lums-backup-....db.gz`.

```bash
BACKUP_ROOT=/mnt/lums-nas-backups
BACKUP_FILE=lums-backup-DATEINAME.db.gz
LUMS_VOLUME=lums-data
LUMS_IMAGE=lums:SET-TO-ACTIVE-IMAGE-TAG
```

Stoppe LUMS und sichere die aktuelle Datenbank als zusätzliche Rückfallebene:

```bash
sudo docker stop lums
sudo docker cp lums:/var/lib/lums/lums.db \
  "/root/lums-before-restore-$(date +%F-%H%M%S).db"
```

Stelle die ausgewählte Sicherung in einem einmaligen Hilfscontainer wieder her.
Das Skript prüft die Datenbankintegrität vor dem Ersetzen und setzt den
Dateibesitzer auf den LUMS-Laufzeitbenutzer zurück:

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

Starte LUMS wieder und prüfe die Migrationen und den Dienst:

```bash
sudo docker start lums
sudo docker logs --tail 100 lums
curl -s -o /dev/null -w 'GET /login: %{http_code}\n' \
  http://127.0.0.1:5050/login
```

Prüfe anschließend Anmeldung, Benutzer, Clients und Jobs. Wenn die
wiederhergestellte Sicherung älter als der aktuelle Anwendungsstand ist, kann
LUMS beim Start Datenbankmigrationen ausführen.

## Falls der Restore fehlschlägt

Lass die fehlerhafte Datenbank nicht als produktiven Zustand weiterlaufen.
Stoppe LUMS erneut. Setze `BACKUP_ROOT=/root` und `BACKUP_FILE` auf den
vollständigen Dateinamen der vorher gesicherten
`lums-before-restore-....db`-Datei. Führe danach den gleichen Hilfscontainer-
Befehl aus der Wiederherstellungssektion erneut aus. Starte LUMS erst wieder,
nachdem die Integritätsprüfung erfolgreich war.
