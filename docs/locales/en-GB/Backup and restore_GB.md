# Restore a LUMS database backup

This guide restores a `.db` or `.db.gz` backup in a Docker deployment. A
restore replaces the active database. Work carefully and run these steps on
the Debian host.

## Prerequisites

You need:

* the host path of the backup storage, for example `/mnt/lums-nas-backups`
* the selected subdirectory from the LUMS backup interface, if used
* the backup filename
* the database volume name, usually `lums-data`
* the LUMS image to use for the one-off restore container

Use the same image version as the running installation. You can check the
configured image name with:

```bash
sudo docker inspect lums --format '{{.Config.Image}}'
```

Replace `lums:SET-TO-ACTIVE-IMAGE-TAG` below with exactly that image name. Do
not use an old image tag just because it is still present on the host.

The NAS/filesystem mount must be available. Check it before the restore:

```bash
mountpoint /mnt/lums-nas-backups
ls -lh /mnt/lums-nas-backups
```

Adjust `/mnt/lums-nas-backups` to the actual host path. LUMS shows the
container path; the left-hand side of the Docker mount is the host path.

## Restore

Set the variables to match your installation. `BACKUP_FILE` must refer to a
filename in the backup mount. If the UI subdirectory is used, include it in
the path, for example `weekend/lums-backup-....db.gz`.

```bash
BACKUP_ROOT=/mnt/lums-nas-backups
BACKUP_FILE=lums-backup-DATEINAME.db.gz
LUMS_VOLUME=lums-data
LUMS_IMAGE=lums:SET-TO-ACTIVE-IMAGE-TAG
```

Stop LUMS and save the current database as an additional fallback:

```bash
sudo docker stop lums
sudo docker cp lums:/var/lib/lums/lums.db \
  "/root/lums-before-restore-$(date +%F-%H%M%S).db"
```

Restore the selected backup in a one-off helper container. The script checks
database integrity before replacing the database and resets the file owner
to the LUMS runtime user:

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

Start LUMS again and check the migrations and service:

```bash
sudo docker start lums
sudo docker logs --tail 100 lums
curl -s -o /dev/null -w 'GET /login: %{http_code}\n' \
  http://127.0.0.1:5050/login
```

Then check sign-in, users, clients and jobs. If the restored backup is older
than the current application state, LUMS may run database migrations at
startup.

## If the restore fails

Do not leave the failed database running as the production state. Stop LUMS
again. Set `BACKUP_ROOT=/root` and set `BACKUP_FILE` to the complete filename
of the previously saved `lums-before-restore-....db` file. Then run the same
helper-container command from the Restore section again. Do not start LUMS
until the integrity check succeeds. The English source is
[backup-restore.md](../../../server/static/backup-restore.md).
