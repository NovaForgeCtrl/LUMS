# Restaurar una copia de seguridad de la base de datos de LUMS

Esta guía restaura una copia `.db` o `.db.gz` en una implementación de Docker.
La restauración sustituye la base de datos activa. Procede con cuidado y
realiza los pasos en el host Debian.

## Requisitos previos

Necesitas:

* la ruta del host al almacenamiento de copias de seguridad, por ejemplo, `/mnt/lums-nas-backups`
* la subcarpeta seleccionada en la interfaz de copias de seguridad de LUMS, si se utiliza
* el nombre del archivo de copia de seguridad
* el nombre del volumen de la base de datos, normalmente `lums-data`
* la imagen de LUMS que se utilizará para el contenedor de restauración de una sola ejecución

Usa la misma versión de imagen que la instalación en ejecución. Puedes
consultar el nombre de imagen configurado así:

```bash
sudo docker inspect lums --format '{{.Config.Image}}'
```

Sustituye `lums:SET-TO-ACTIVE-IMAGE-TAG` más abajo por ese nombre de imagen
exacto. No uses una etiqueta de imagen antigua solo porque aún exista en el
host.

El montaje del NAS/sistema de archivos debe estar disponible. Compruébalo
antes de restaurar:

```bash
mountpoint /mnt/lums-nas-backups
ls -lh /mnt/lums-nas-backups
```

Adapta `/mnt/lums-nas-backups` a la ruta real del host. LUMS muestra la ruta
del contenedor; el lado izquierdo del montaje Docker es la ruta del host.

## Restauración

Define las variables para que coincidan con tu instalación. `BACKUP_FILE` debe
indicar un nombre de archivo dentro del montaje de copias. Si hay una
subcarpeta de la interfaz, inclúyela en la ruta, por ejemplo
`fin-de-semana/lums-backup-....db.gz`.

```bash
BACKUP_ROOT=/mnt/lums-nas-backups
BACKUP_FILE=lums-backup-DATEINAME.db.gz
LUMS_VOLUME=lums-data
LUMS_IMAGE=lums:SET-TO-ACTIVE-IMAGE-TAG
```

Detén LUMS y guarda la base de datos actual como medida de recuperación
adicional:

```bash
sudo docker stop lums
sudo docker cp lums:/var/lib/lums/lums.db \
  "/root/lums-before-restore-$(date +%F-%H%M%S).db"
```

Restaura la copia seleccionada con un contenedor auxiliar de una sola
ejecución. El script comprueba la integridad de la base de datos antes de
sustituirla y devuelve la propiedad del archivo al usuario de ejecución de LUMS:

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

Vuelve a iniciar LUMS y comprueba las migraciones y el servicio:

```bash
sudo docker start lums
sudo docker logs --tail 100 lums
curl -s -o /dev/null -w 'GET /login: %{http_code}\n' \
  http://127.0.0.1:5050/login
```

Después, comprueba el inicio de sesión, los usuarios, los clientes y los
trabajos. Si la copia restaurada es anterior al estado actual de la aplicación,
LUMS puede ejecutar migraciones de la base de datos al iniciarse.

## Si falla la restauración

No mantengas la base de datos defectuosa como estado de producción. Detén LUMS
de nuevo. Define `BACKUP_ROOT=/root` y asigna a `BACKUP_FILE` el nombre
completo del archivo `lums-before-restore-....db` guardado previamente.
Después, vuelve a ejecutar el mismo comando del contenedor auxiliar de la
sección de restauración. No reinicies LUMS hasta que la comprobación de
integridad se haya realizado correctamente.

[Documentación original en inglés](../../../server/static/backup-restore.md).
