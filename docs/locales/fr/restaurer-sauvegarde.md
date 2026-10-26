# Restaurer une sauvegarde de la base de données LUMS

Ce guide permet de restaurer une sauvegarde `.db` ou `.db.gz` dans un
déploiement Docker. La restauration remplace la base de données active.
Procédez avec précaution et exécutez les étapes sur l’hôte Debian.

## Prérequis

Vous avez besoin :

* du chemin hôte vers le stockage des sauvegardes, par exemple `/mnt/lums-nas-backups`
* du sous-dossier sélectionné dans l’interface de sauvegarde LUMS, le cas échéant
* du nom du fichier de sauvegarde
* du nom du volume de base de données, généralement `lums-data`
* de l’image LUMS à utiliser pour le conteneur de restauration ponctuel

Utilisez la même version d’image que l’installation en cours. Pour connaître
le nom de l’image configurée, exécutez :

```bash
sudo docker inspect lums --format '{{.Config.Image}}'
```

Remplacez ci-dessous `lums:SET-TO-ACTIVE-IMAGE-TAG` par ce nom d’image exact.
N’utilisez pas une ancienne balise d’image simplement parce qu’elle est encore
présente sur l’hôte.

Le montage du NAS/système de fichiers doit être disponible. Vérifiez-le avant
la restauration :

```bash
mountpoint /mnt/lums-nas-backups
ls -lh /mnt/lums-nas-backups
```

Adaptez `/mnt/lums-nas-backups` au chemin hôte réel. LUMS affiche le chemin du
conteneur ; le côté gauche du montage Docker est le chemin hôte.

## Restauration

Définissez les variables selon votre installation. `BACKUP_FILE` doit désigner
un fichier situé dans le montage des sauvegardes. Si l’interface utilise un
sous-dossier, ajoutez-le au chemin, par exemple
`week-end/lums-backup-....db.gz`.

```bash
BACKUP_ROOT=/mnt/lums-nas-backups
BACKUP_FILE=lums-backup-DATEINAME.db.gz
LUMS_VOLUME=lums-data
LUMS_IMAGE=lums:SET-TO-ACTIVE-IMAGE-TAG
```

Arrêtez LUMS et sauvegardez la base de données actuelle comme protection de
secours supplémentaire :

```bash
sudo docker stop lums
sudo docker cp lums:/var/lib/lums/lums.db \
  "/root/lums-before-restore-$(date +%F-%H%M%S).db"
```

Restaurez la sauvegarde sélectionnée à l’aide d’un conteneur auxiliaire
ponctuel. Le script vérifie l’intégrité de la base de données avant de la
remplacer et rétablit la propriété du fichier pour l’utilisateur d’exécution
LUMS :

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

Redémarrez LUMS et vérifiez les migrations et le service :

```bash
sudo docker start lums
sudo docker logs --tail 100 lums
curl -s -o /dev/null -w 'GET /login: %{http_code}\n' \
  http://127.0.0.1:5050/login
```

Vérifiez ensuite la connexion, les utilisateurs, les clients et les tâches. Si
la sauvegarde restaurée est antérieure à la version actuelle de l’application,
LUMS peut exécuter des migrations de base de données au démarrage.

## En cas d’échec de la restauration

Ne laissez pas la base de données défaillante en production. Arrêtez de nouveau
LUMS. Définissez `BACKUP_ROOT=/root` et attribuez à `BACKUP_FILE` le nom
complet du fichier `lums-before-restore-....db` sauvegardé précédemment.
Réexécutez ensuite la même commande du conteneur auxiliaire indiquée dans la
section de restauration. Ne redémarrez LUMS qu’une fois la vérification
d’intégrité réussie.

[Documentation source en anglais](../../../server/static/backup-restore.md).
