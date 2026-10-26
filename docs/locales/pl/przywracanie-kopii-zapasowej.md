# Przywracanie kopii zapasowej bazy danych LUMS

Ten przewodnik opisuje przywracanie kopii `.db` lub `.db.gz` we wdrożeniu
Docker. Przywrócenie zastępuje aktywną bazę danych. Wykonuj te czynności
ostrożnie na hoście Debian.

## Wymagania wstępne

Potrzebne będą:

* ścieżka hosta do magazynu kopii zapasowych, na przykład
  `/mnt/lums-nas-backups`
* wybrany podkatalog z interfejsu kopii zapasowych LUMS, jeśli jest używany
* nazwa pliku kopii
* nazwa woluminu bazy danych, zwykle `lums-data`
* obraz LUMS używany do uruchomienia jednorazowego kontenera przywracania

Użyj tej samej wersji obrazu co w działającej instalacji. Skonfigurowaną nazwę
obrazu można odczytać następującym poleceniem:

```bash
sudo docker inspect lums --format '{{.Config.Image}}'
```

Zastąp `lums:SET-TO-ACTIVE-IMAGE-TAG` poniżej dokładnie tą nazwą obrazu. Nie
używaj starego tagu obrazu tylko dlatego, że nadal znajduje się na hoście.

Upewnij się, że punkt montowania NAS/systemu plików jest dostępny. Sprawdź go
przed przywracaniem:

```bash
mountpoint /mnt/lums-nas-backups
ls -lh /mnt/lums-nas-backups
```

Dostosuj `/mnt/lums-nas-backups` do rzeczywistej ścieżki na hoście. LUMS
wyświetla ścieżkę kontenera; lewa strona podłączenia Docker jest ścieżką
hosta.

## Przywracanie

Ustaw zmienne odpowiednio do swojej instalacji. `BACKUP_FILE` musi wskazywać
plik w podłączonym magazynie kopii. Jeśli używasz podkatalogu wybranego w
interfejsie, uwzględnij go w ścieżce, na przykład
`weekend/lums-backup-....db.gz`.

```bash
BACKUP_ROOT=/mnt/lums-nas-backups
BACKUP_FILE=lums-backup-DATEINAME.db.gz
LUMS_VOLUME=lums-data
LUMS_IMAGE=lums:SET-TO-ACTIVE-IMAGE-TAG
```

Zatrzymaj LUMS i utwórz dodatkową kopię zapasową bieżącej bazy danych jako
zabezpieczenie na wypadek konieczności wycofania zmian:

```bash
sudo docker stop lums
sudo docker cp lums:/var/lib/lums/lums.db \
  "/root/lums-before-restore-$(date +%F-%H%M%S).db"
```

Przywróć wybraną kopię w jednorazowym kontenerze pomocniczym. Skrypt sprawdza
integralność bazy danych przed jej zastąpieniem i przywraca właściciela pliku
na użytkownika uruchomieniowego LUMS:

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

Uruchom ponownie LUMS i sprawdź migracje oraz usługę:

```bash
sudo docker start lums
sudo docker logs --tail 100 lums
curl -s -o /dev/null -w 'GET /login: %{http_code}\n' \
  http://127.0.0.1:5050/login
```

Następnie sprawdź logowanie, użytkowników, klientów i zadania. Jeśli
przywrócona kopia jest starsza niż aktualna wersja aplikacji, LUMS może
wykonać migracje bazy danych podczas uruchamiania.

## Jeśli przywracanie się nie powiedzie

Nie pozostawiaj uszkodzonej bazy jako działającego środowiska produkcyjnego.
Ponownie zatrzymaj LUMS. Ustaw `BACKUP_ROOT=/root`, a `BACKUP_FILE` na pełną
nazwę wcześniej utworzonego pliku
`lums-before-restore-....db`. Następnie ponownie uruchom to samo polecenie
kontenera pomocniczego z sekcji przywracania. Uruchom LUMS dopiero po
pomyślnym przejściu kontroli integralności.

Źródło: [oryginał po angielsku](../../../server/static/backup-restore.md).
